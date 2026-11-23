import sqlite3


def record_event(
    conn: sqlite3.Connection,
    tenant_id: int,
    certificate_id: int,
    actor_id: int,
    event_type: str,
    occurred_at_utc: str,
    idempotency_record_id: int,
) -> None:
    conn.execute(
        "INSERT INTO audit_events "
        "(tenant_id, certificate_id, actor_id, event_type, occurred_at_utc, idempotency_record_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (tenant_id, certificate_id, actor_id, event_type, occurred_at_utc, idempotency_record_id),
    )
