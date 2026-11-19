"""Typed Socrata feed boundary; archived records deliberately remain eligible."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Annotated, ClassVar, Final

import httpx2
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .state import IncidentId  # noqa: TC001 -- Pydantic resolves this field at runtime.

if TYPE_CHECKING:
    from .config import Settings


class Incident(BaseModel):
    """Incident identity and the metadata exposed to Home Assistant."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)
    traffic_report_id: Annotated[IncidentId, Field(min_length=1)]
    published_date: str | None = None
    issue_reported: str | None = None
    address: str | None = None
    traffic_report_status: str | None = None


INCIDENTS: Final = TypeAdapter(tuple[Incident, ...])


def client(settings: Settings) -> httpx2.AsyncClient:
    """Bounded HTTP/2 client; connection retries apply only to feed GETs."""
    transport = httpx2.AsyncHTTPTransport(
        http2=True,
        retries=3,
        limits=httpx2.Limits(
            max_connections=200, max_keepalive_connections=40, keepalive_expiry=30
        ),
        socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
    )
    return httpx2.AsyncClient(
        transport=transport,
        timeout=httpx2.Timeout(
            connect=5, read=settings.io_timeout_seconds, write=10, pool=10
        ),
        follow_redirects=True,
        headers={
            "Accept": "application/json",
            "User-Agent": "austin-fire-controller/1",
        },
    )


async def fetch(http: httpx2.AsyncClient, url: str) -> tuple[Incident, ...]:
    """Reject an entire malformed batch without consuming any IDs."""
    response = await http.get(
        url,
        params={
            "$select": "traffic_report_id,published_date,issue_reported,address,traffic_report_status",  # noqa: E501
            "$where": "issue_reported IN('DUMP - Dumpster Fire','TRASH - Trash Fire')",
            "$order": "published_date DESC",
            "$limit": "25",
        },
    )
    _ = response.raise_for_status()
    return INCIDENTS.validate_json(response.content)
