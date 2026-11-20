"""Read-only status interface for Home Assistant and Kubernetes probes."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime  # noqa: TC003 -- Pydantic resolves this field at runtime.
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, ClassVar, Protocol

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict
from typing_extensions import override

from .metrics import REGISTRY

if TYPE_CHECKING:
    from collections.abc import Generator


class Status(BaseModel):
    """A snapshot of controller activity, never a command to the device."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    poll_ok: bool | None = None
    error: str | None = None
    initialized: bool = False
    new_run_id: int = 0
    new_incident_count: int = 0
    new_ids: tuple[str, ...] = ()
    current_count: int = 0
    seen_count: int = 0
    last_poll: datetime | None = None
    last_incident_id: str | None = None
    last_issue_reported: str | None = None
    last_address: str | None = None
    last_published_date: str | None = None
    last_status: str | None = None
    activity_deadline: datetime | None = None
    enabled: bool = False
    timeout_minutes: int = 15


class StatusProvider(Protocol):
    """Expose an immutable snapshot to the HTTP status handler."""

    status: Status


@contextmanager
def serve(controller: StatusProvider) -> Generator[None]:
    """Keep an internal HTTP server alive for the controller process lifetime."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in ("/health", "/status", "/metrics"):
                self.send_error(404)
                return
            if self.path == "/health":
                body = b"ok"
                content_type = "text/plain"
            elif self.path == "/status":
                body = controller.status.model_dump_json().encode("utf-8")
                content_type = "application/json"
            else:
                body = generate_latest(REGISTRY)
                content_type = CONTENT_TYPE_LATEST
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            _ = self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: str) -> None:
            _ = format, args

    with ThreadingHTTPServer(("0.0.0.0", 8080), Handler) as server:  # noqa: S104
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield
        finally:
            server.shutdown()
            thread.join()
