from datetime import datetime
import sqlite3

from .actor import ActorContext
from .certificate_repo import get_certificate, list_certificates
from .dates import to_local
from .errors import ApiError


def certificates_for_actor(
    conn: sqlite3.Connection,
    actor: ActorContext,
    search: str,
    sort: str,
    direction: str,
    page: int,
    page_size: int,
) -> dict:
    return list_certificates(conn, actor.tenant_id, search, sort, direction, page, page_size)


def certificate_detail(conn: sqlite3.Connection, actor: ActorContext, certificate_id: int) -> dict:
    row = get_certificate(conn, actor.tenant_id, certificate_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "资源不存在")
    issued_at = datetime.fromisoformat(row.pop("issued_at_utc").replace("Z", "+00:00"))
    _, local_datetime = to_local(issued_at, actor.timezone)
    return {**row, "issued_local_datetime": local_datetime}
