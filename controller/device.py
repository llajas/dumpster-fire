"""Encrypted native API adapter; never retry a fire-and-forget toggle command."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Protocol

import anyio
from aioesphomeapi.client import APIClient
from aioesphomeapi.core import APIConnectionError
from aioesphomeapi.model import (
    BinarySensorInfo,
    BinarySensorState,
    ButtonInfo,
    EntityState,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from contextlib import AbstractAsyncContextManager

    from .config import Settings


class DeviceUnavailableError(Exception):
    """Unavailable feedback; exceptions remain mutable for contextlib tracebacks."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason: str = reason


class Session(Protocol):
    """Live measured state plus one synchronous command on the same connection."""

    @property
    def flame(self) -> bool | None:
        """Return None for missing state or a disconnected device."""
        ...

    def press(self) -> None:
        """Submit one toggle, without acknowledgement or retry."""
        ...


class Device(Protocol):
    """Open a fresh subscription for each policy reconciliation."""

    def session(self) -> AbstractAsyncContextManager[Session]:
        """Yield only after an initial matching state arrives."""
        ...


class NativeSession:
    """Mutable subscriber: newest matching sensor value replaces previous feedback."""

    def __init__(self, api: APIClient, trigger: ButtonInfo) -> None:
        self.api: APIClient = api
        self.trigger: ButtonInfo = trigger
        self.measured: bool | None = None

    @property
    def flame(self) -> bool | None:
        return self.measured if self.api.is_connected else None

    def press(self) -> None:
        self.api.button_command(self.trigger.key, device_id=self.trigger.device_id)


class NativeDevice:
    """Entity discovery fails closed on ambiguous names or object IDs."""

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Session]:
        """Connect independently of HA and await actual Flame State feedback."""
        api = APIClient(
            self.settings.host,
            6053,
            noise_psk=self.settings.api_key.get_secret_value(),
        )
        try:
            with anyio.fail_after(self.settings.io_timeout_seconds):
                await api.connect(login=True)
                entities, _ = await api.list_entities_services()
                sensors = [
                    entity
                    for entity in entities
                    if isinstance(entity, BinarySensorInfo)
                    and (
                        entity.object_id == self.settings.flame_object_id
                        if self.settings.flame_object_id is not None
                        else entity.name == "Flame State"
                    )
                ]
                buttons = [
                    entity
                    for entity in entities
                    if isinstance(entity, ButtonInfo)
                    and (
                        entity.object_id == self.settings.trigger_object_id
                        if self.settings.trigger_object_id is not None
                        else entity.name == "Trigger"
                    )
                ]
                if len(sensors) != 1 or len(buttons) != 1:
                    reason = "Flame State/Trigger missing or ambiguous"
                    raise DeviceUnavailableError(reason)
                sensor = sensors[0]
                session = NativeSession(api, buttons[0])
                ready = anyio.Event()

                def receive(state: EntityState) -> None:
                    if (
                        isinstance(state, BinarySensorState)
                        and state.key == sensor.key
                        and state.device_id == sensor.device_id
                    ):
                        session.measured = None if state.missing_state else state.state
                        ready.set()

                api.subscribe_states(receive)
                await ready.wait()
            yield session
        except (APIConnectionError, TimeoutError) as exc:
            raise DeviceUnavailableError(type(exc).__name__) from exc
        finally:
            with anyio.move_on_after(self.settings.io_timeout_seconds, shield=True):
                await api.disconnect()
