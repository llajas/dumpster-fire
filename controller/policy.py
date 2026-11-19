"""Serialized durable incident consumption and measured-state toggle policy."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

import anyio

from .device import DeviceUnavailableError
from .state import State
from .status import Status

if TYPE_CHECKING:
    from collections.abc import Callable

    from .config import Settings
    from .device import Device
    from .feed import Incident
    from .state import IncidentId, Store

LOGGER: Final = logging.getLogger("austin_dumpster_fire")


class Controller:
    """Mutable coordinator; one lock serializes polls, deadlines and commands."""

    def __init__(self, settings: Settings, store: Store, device: Device) -> None:
        self.settings: Settings = settings
        self.store: Store = store
        self.device: Device = device
        self.state: State = store.load()
        self.lock: anyio.Lock = anyio.Lock()
        self.clock: Callable[[], datetime] = lambda: datetime.now(UTC)
        self.status: Status = Status(
            initialized=self.state.initialized,
            new_run_id=self.state.new_run_id,
            seen_count=len(self.state.seen),
            activity_deadline=self.state.activity_deadline,
            enabled=settings.enabled,
            timeout_minutes=settings.timeout_minutes,
        )

    async def commit(self, state: State) -> None:
        """Publish in-memory state only after the durable transaction succeeds."""
        await anyio.to_thread.run_sync(self.store.save, state)
        self.state = state
        self.status = self.status.model_copy(
            update={
                "initialized": state.initialized,
                "new_run_id": state.new_run_id,
                "seen_count": len(state.seen),
                "activity_deadline": state.activity_deadline,
            }
        )

    async def consume(self, current: tuple[Incident, ...]) -> None:
        """Seed, deduplicate and persist deadlines before any device command."""
        async with self.lock:
            now = self.clock()
            previous = self.state
            current_ids = frozenset(row.traffic_report_id for row in current)
            fresh: frozenset[IncidentId] = (
                current_ids.difference(previous.seen)
                if previous.initialized and previous.schema_version == 1
                else frozenset()
            )
            cutoff = now - timedelta(hours=48)
            seen = {
                key: stamp
                for key, stamp in previous.seen.items()
                if key in current_ids or stamp >= cutoff
            }
            seen.update({key: now for key in current_ids if key not in seen})
            active_batch = bool(fresh) and self.settings.enabled
            updated = State(
                initialized=True,
                seen=seen,
                new_run_id=previous.new_run_id + bool(fresh),
                schema_version=1,
                activity_deadline=(
                    now + timedelta(minutes=self.settings.timeout_minutes)
                    if active_batch
                    else previous.activity_deadline
                ),
                activation_attempted=False
                if active_batch
                else previous.activation_attempted,
            )
            if updated != previous:
                await self.commit(updated)
            newest = next(
                (row for row in current if row.traffic_report_id in fresh),
                current[0] if current else None,
            )
            self.status = self.status.model_copy(
                update={
                    "poll_ok": True,
                    "error": None,
                    "last_poll": now,
                    "new_incident_count": len(fresh),
                    "new_ids": tuple(sorted(fresh)),
                    "current_count": len(current_ids),
                    "last_incident_id": newest.traffic_report_id if newest else None,
                    "last_issue_reported": newest.issue_reported if newest else None,
                    "last_address": newest.address if newest else None,
                    "last_published_date": newest.published_date if newest else None,
                    "last_status": newest.traffic_report_status if newest else None,
                }
            )
            LOGGER.info(
                "feed.consumed count=%d new=%d run=%d enabled=%s",
                len(current_ids),
                len(fresh),
                updated.new_run_id,
                self.settings.enabled,
            )

    async def reconcile(self) -> None:
        """No state guess, no automatic command retry, no deadline loss offline."""
        async with self.lock:
            state = self.state
            deadline = state.activity_deadline
            if deadline is None:
                return
            expired = self.clock() >= deadline
            if not self.settings.enabled:
                if expired:
                    await self.commit(
                        state.model_copy(update={"activity_deadline": None})
                    )
                return
            if not expired and state.activation_attempted:
                return
            try:
                async with self.device.session() as session:
                    measured = session.flame
                    if measured is None:
                        LOGGER.warning("device.state_missing")
                        return
                    expired = self.clock() >= deadline
                    # Consume the opportunity BEFORE sending a non-idempotent command.
                    # A crash in between intentionally sacrifices delivery, not safety.
                    if expired:
                        await self.commit(
                            state.model_copy(update={"activity_deadline": None})
                        )
                    else:
                        await self.commit(
                            state.model_copy(update={"activation_attempted": True})
                        )
                    flame = session.flame
                    if flame is None:
                        LOGGER.warning("device.disconnected_before_command")
                        return
                    if flame == expired:
                        session.press()
                        LOGGER.info(
                            "device.trigger_submitted desired_on=%s", not expired
                        )
            except DeviceUnavailableError as exc:
                LOGGER.warning("device.unavailable reason=%s", exc)
