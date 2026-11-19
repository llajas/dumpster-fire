"""Crash-durable state compatible with the original HA poller's JSON file."""

from __future__ import annotations

import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal, NewType

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Generator

IncidentId = NewType("IncidentId", str)


class State(BaseModel):
    """Persisted deduplication and activity ownership, parsed once at startup."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, strict=True, extra="forbid"
    )
    initialized: bool = False
    seen: dict[IncidentId, AwareDatetime] = Field(default_factory=dict)
    new_run_id: int = Field(default=0, ge=0)
    schema_version: Literal[0, 1] = 0
    activity_deadline: AwareDatetime | None = None
    activation_attempted: bool = True


class Store:
    """Single-writer durable storage; callers hold exclusive() for process lifetime."""

    def __init__(self, path: Path) -> None:
        self.path: Path = path

    @contextmanager
    def exclusive(self) -> Generator[None]:
        """Reject a second controller rather than race toggle commands."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(self.path.suffix + ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def load(self) -> State:
        """Missing means first run; invalid or unreadable state fails closed."""
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return State()
        return State.model_validate_json(raw)

    def save(self, state: State) -> None:
        """Fsync contents, atomically replace, then fsync the parent directory."""
        fd, temporary = tempfile.mkstemp(prefix=".austin-fire-", dir=self.path.parent)
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                _ = stream.write(state.model_dump_json(indent=2))
                stream.flush()
                os.fsync(stream.fileno())
            _ = temporary_path.replace(self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary_path.unlink(missing_ok=True)
