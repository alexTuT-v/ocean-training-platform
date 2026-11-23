from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .dates import to_local
from .db import connect, initialize_database


SEED_INSTANT = datetime(2026, 1, 10, 13, 30, tzinfo=timezone.utc)
SEED_INSTANT_TEXT = "2026-01-10T13:30:00Z"


def _tenant(conn: sqlite3.Connection, name: str, timezone_name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO tenants (name, timezone) VALUES (?, ?)", (name, timezone_name))
    return conn.execute("SELECT id FROM tenants WHERE name = ?", (name,)).fetchone()[0]


def _person_or_course(conn: sqlite3.Connection, table: str, tenant_id: int, column: str, value: str) -> int:
    row = conn.execute(f"SELECT id FROM {table} WHERE tenant_id = ? AND {column} = ? ORDER BY id LIMIT 1", (tenant_id, value)).fetchone()
    if row:
        return row[0]
    return conn.execute(f"INSERT INTO {table} (tenant_id, {column}) VALUES (?, ?)", (tenant_id, value)).lastrowid


def seed_demo_data(path: Path) -> None:
    initialize_database(path)
    conn = connect(path)
    try:
        with conn:
            for tenant_name, zone, admin_email, names, certified_name, serial in (
                ("East", "Australia/Sydney", "alice@east.test", ("Alex Lee", "Beth Stone", "Casey Wong"), "Casey Wong", "EAST-SEED-001"),
                ("West", "Australia/Perth", "bob@west.test", ("Alex Lee", "Blake Stone", "Casey Wong"), "Casey Wong", "WEST-SEED-001"),
            ):
                tenant_id = _tenant(conn, tenant_name, zone)
                conn.execute("INSERT OR IGNORE INTO admins (tenant_id, email) VALUES (?, ?)", (tenant_id, admin_email))
                actor_id = conn.execute("SELECT id FROM admins WHERE email = ?", (admin_email,)).fetchone()[0]
                course_id = _person_or_course(conn, "courses", tenant_id, "title", "Safety 101")
                learner_ids = {
                    name: _person_or_course(conn, "learners", tenant_id, "name", name)
                    for name in names
                }
                for index, name in enumerate(names):
                    status = "INCOMPLETE" if index == 1 else "COMPLETED"
                    conn.execute(
                        "INSERT OR IGNORE INTO enrollments (tenant_id, course_id, learner_id, status, completed_at_utc) VALUES (?, ?, ?, ?, ?)",
                        (tenant_id, course_id, learner_ids[name], status, SEED_INSTANT_TEXT if status == "COMPLETED" else None),
                    )
                local_date, _ = to_local(SEED_INSTANT, zone)
                conn.execute(
                    "INSERT OR IGNORE INTO certificates (tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')",
                    (tenant_id, course_id, learner_ids[certified_name], serial, SEED_INSTANT_TEXT, local_date),
                )
                certificate = conn.execute("SELECT id FROM certificates WHERE serial_number = ?", (serial,)).fetchone()
                if certificate:
                    conn.execute(
                        "INSERT OR IGNORE INTO audit_events (tenant_id, certificate_id, actor_id, event_type, occurred_at_utc) "
                        "VALUES (?, ?, ?, 'ISSUED', ?)",
                        (tenant_id, certificate[0], actor_id, SEED_INSTANT_TEXT),
                    )
    finally:
        conn.close()
