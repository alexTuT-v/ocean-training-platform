from pathlib import Path

from .actor import ActorContext
from .audit_repo import record_event
from .db import connect
from .dates import utc_now_text
from .errors import ApiError
from .idempotency import execute_write, fingerprint


def revoke_certificate(path: Path, actor: ActorContext, certificate_id: int, key: str, body: dict) -> tuple[int, dict]:
    conn = connect(path)
    try:
        request_fingerprint = fingerprint("POST", "/api/certificates/{certificate_id}/revoke", certificate_id, body)

        def validate_new_request() -> None:
            if body:
                raise ApiError(422, "INVALID_REQUEST", "请求体不支持额外字段")
            found = conn.execute(
                "SELECT 1 FROM certificates WHERE tenant_id = ? AND id = ?",
                (actor.tenant_id, certificate_id),
            ).fetchone()
            if found is None:
                raise ApiError(404, "NOT_FOUND", "资源不存在")

        def perform(record_id: int) -> tuple[int, dict]:
            now = utc_now_text()
            changed = conn.execute(
                "UPDATE certificates SET status = 'REVOKED', revoked_at_utc = ? "
                "WHERE tenant_id = ? AND id = ? AND status = 'ACTIVE'",
                (now, actor.tenant_id, certificate_id),
            ).rowcount == 1
            if changed:
                record_event(conn, actor.tenant_id, certificate_id, actor.admin_id, "REVOKED", now, record_id)
            return 200, {
                "operation_id": record_id,
                "certificate_id": certificate_id,
                "status": "REVOKED",
                "changed": changed,
            }

        return execute_write(conn, actor, key, request_fingerprint, "REVOKE", validate_new_request, perform)
    finally:
        conn.close()
