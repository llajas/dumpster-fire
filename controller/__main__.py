r"""Standalone Austin fire controller (no HA, MQTT or live hardware dependency).

Run from repository root::

    AUSTIN_FIRE_HOST=192.0.2.10 AUSTIN_FIRE_API_KEY='<ESPHome Noise PSK>' \
      AUSTIN_FIRE_STATE_PATH=/data/austin_dumpster_fire_state.json \
      uv run --project controller --no-dev python -m controller

Or from controller/: use ``python -m controller`` with the repository root on
PYTHONPATH. Dependencies are declared in controller/pyproject.toml.

Environment (AUSTIN_FIRE_ prefix): HOST and API_KEY required; STATE_PATH defaults
to /data/austin_dumpster_fire_state.json; TIMEOUT_MINUTES=15 (1..240), ENABLED=true,
IO_TIMEOUT_SECONDS=20. Optional FLAME_OBJECT_ID / TRIGGER_OBJECT_ID override name
discovery (Flame State / Trigger). FEED_URL overrides the Socrata URL for a local
feed. Configuration is read at startup; restart to change it. Disabling consumes
incidents without activation; expired timers clear without pressing while disabled.
An in-cluster GET /status endpoint on port 8080 supplies poll and incident
diagnostics to HA, while GET /health supplies a liveness check. Neither accepts
commands and the endpoint must not be exposed outside the trusted cluster.

Migration: stop the old HA policy/poller first. Copy its JSON state to STATE_PATH
or mount that same file; legacy initialized/seen/new_run_id fields are accepted.
HA's timer is not in that file, so it cannot be imported automatically. Run only
one controller and disable HA's toggle automations; HA may retain its ESPHome
integration for visibility/manual control. The state directory must be writable
and backed by a filesystem with atomic replace, fsync and flock support.
Missing state seeds the first successful poll without activation. Corrupt state
fails startup, remains untouched and requires operator recovery; no silent reset.

Only the 25 most recent exact DUMP/TRASH records are fetched every 300 seconds,
regardless of ACTIVE/ARCHIVED status. Outages/bursts can lose incidents beyond
that window. Seen IDs older than 48h are pruned ONLY when absent from this feed;
an ID returning after pruning can be treated as new. Deadlines use UTC wall time;
large system-clock adjustments affect duration. Timer reconciliation runs every
5 seconds independently of feed failures. Offline/missing state retains deadlines.

Trigger is a toggle with NO acknowledgement. Activation attempts are persisted
before submission and are not retried for the same batch, even across restarts.
Expiry clears the deadline BEFORE pressing; a crash/send failure can therefore
lose an action rather than duplicate it. New incidents extend the deadline even
if already lit. Manual-off/stock-auto-off is not continuously overridden after
activation is consumed. No claim of exactly-once physical delivery is possible.
"""

from __future__ import annotations

import logging
import signal
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import anyio
import httpx2
from pydantic import ValidationError

from .config import Settings
from .device import NativeDevice
from .feed import client, fetch
from .policy import LOGGER, Controller
from .state import Store
from .status import serve

if TYPE_CHECKING:
    from anyio import CancelScope


async def poll(controller: Controller, http: httpx2.AsyncClient) -> None:
    """Fetch immediately, then every five minutes; failed feeds mutate nothing."""
    while True:
        started = anyio.current_time()
        try:
            with anyio.fail_after(controller.settings.io_timeout_seconds):
                current = await fetch(http, controller.settings.feed_url)
        except (httpx2.HTTPError, ValidationError, TimeoutError) as exc:
            LOGGER.warning("feed.failed reason=%s", type(exc).__name__)
            controller.status = controller.status.model_copy(
                update={
                    "poll_ok": False,
                    "error": type(exc).__name__,
                    "last_poll": datetime.now(UTC),
                    "new_incident_count": 0,
                    "new_ids": (),
                }
            )
        else:
            await controller.consume(current)
        await anyio.sleep(max(0, 300 - (anyio.current_time() - started)))


async def reconcile(controller: Controller) -> None:
    """Timers remain independent of HTTP availability."""
    while True:
        await controller.reconcile()
        await anyio.sleep(5)


async def stop_on_signal(scope: CancelScope) -> None:
    """Cancel all owned tasks cleanly on container termination."""
    with anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT) as signals:
        async for _ in signals:
            scope.cancel()
            return


async def run() -> None:
    """Own the state lock, HTTP pool and structured worker lifetimes."""
    settings = Settings.model_validate({})
    store = Store(settings.state_path)
    with store.exclusive():
        controller = Controller(settings, store, NativeDevice(settings))
        with serve(controller):
            async with client(settings) as http, anyio.create_task_group() as tasks:
                _ = tasks.start_soon(stop_on_signal, tasks.cancel_scope)
                _ = tasks.start_soon(poll, controller, http)
                _ = tasks.start_soon(reconcile, controller)


def main() -> None:
    """Exit nonzero with a traceback if durable state or startup fails."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    anyio.run(run, backend="asyncio")


if __name__ == "__main__":
    main()
