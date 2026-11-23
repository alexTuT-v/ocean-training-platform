from collections.abc import Callable
from hashlib import sha256
import json
import sqlite3

from .actor import ActorContext
from .dates import utc_now_text
from .errors import ApiError


def validate_key(key: str | None) -> str:
    if key is None or not 1 <= len(key) <= 128 or any(not 33 <= ord(char) <= 126 for char in key):
        raise ApiError(422, "INVALID_IDEMPOTENCY_KEY", "幂等键无效")
    return key


def parse_write_body(raw: bytes) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ApiError(422, "INVALID_REQUEST", "请求体必须是 JSON 对象") from None
    if not isinstance(value, dict):
        raise ApiError(422, "INVALID_REQUEST", "请求体必须是 JSON 对象")
    return value


def fingerprint(method: str, route_template: str, target_id: int, body: dict) -> str:
    canonical = json.dumps(
        {"method": method, "route": route_template, "target_id": target_id, "body": body},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def execute_write(
    conn: sqlite3.Connection,
    actor: ActorContext,
    key: str,
    request_fingerprint: str,
    operation_type: str,
    validate_new_request: Callable[[], None],
    perform: Callable[[int], tuple[int, dict]],
) -> tuple[int, dict]:
    try:
        conn.execute("BEGIN IMMEDIATE")
        record = conn.execute(
            "SELECT request_fingerprint, response_status, response_body_json FROM idempotency_records "
            "WHERE tenant_id = ? AND actor_id = ? AND idempotency_key = ?",
            (actor.tenant_id, actor.admin_id, key),
        ).fetchone()
        if record is not None:
            if record["request_fingerprint"] != request_fingerprint:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "此操作键已用于另一请求")
            if record["response_status"] is None or record["response_body_json"] is None:
                raise ApiError(503, "OPERATION_PENDING", "操作尚未完成，请用原键重试")
            result = record["response_status"], json.loads(record["response_body_json"])
            conn.commit()
            return result

        validate_new_request()
        record_id = conn.execute(
            "INSERT INTO idempotency_records "
            "(tenant_id, actor_id, idempotency_key, request_fingerprint, operation_type, created_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (actor.tenant_id, actor.admin_id, key, request_fingerprint, operation_type, utc_now_text()),
        ).lastrowid
        status, body = perform(record_id)
        conn.execute(
            "UPDATE idempotency_records SET response_status = ?, response_body_json = ?, completed_at_utc = ? WHERE id = ?",
            (status, json.dumps(body, ensure_ascii=False, separators=(",", ":")), utc_now_text(), record_id),
        )
        conn.commit()
        return status, body
    except sqlite3.OperationalError as error:
        conn.rollback()
        if "locked" in str(error).lower() or "busy" in str(error).lower():
            raise ApiError(503, "DATABASE_BUSY", "服务暂时繁忙，请用原操作重试") from error
        raise
    except Exception:
        conn.rollback()
        raise
