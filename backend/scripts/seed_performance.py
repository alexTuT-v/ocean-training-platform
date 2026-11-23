import argparse
from datetime import datetime, timezone
from pathlib import Path

from backend.app.dates import to_local
from backend.app.db import connect, initialize_database


INSTANT = datetime(2026, 1, 10, 13, 30, tzinfo=timezone.utc)
INSTANT_TEXT = "2026-01-10T13:30:00Z"
TENANTS = {
    "East": ("Australia/Sydney", "alice@east.test", "E", 1_000_000),
    "West": ("Australia/Perth", "bob@west.test", "W", 2_000_000),
}


def seed_performance(path: Path, tenant: str = "East", count: int = 100_000) -> None:
    if tenant not in TENANTS or count < 1:
        raise ValueError("tenant must be East or West and count must be positive")
    zone, admin_email, prefix, base_id = TENANTS[tenant]
    local_date, _ = to_local(INSTANT, zone)
    initialize_database(path)
    conn = connect(path)
    try:
        with conn:
            conn.execute("INSERT OR IGNORE INTO tenants (name, timezone) VALUES (?, ?)", (tenant, zone))
            tenant_id = conn.execute("SELECT id FROM tenants WHERE name = ?", (tenant,)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO admins (tenant_id, email) VALUES (?, ?)", (tenant_id, admin_email))
            actor_id = conn.execute("SELECT id FROM admins WHERE email = ?", (admin_email,)).fetchone()[0]
            course = conn.execute(
                "SELECT id FROM courses WHERE tenant_id = ? AND title = 'Performance 100k' ORDER BY id LIMIT 1",
                (tenant_id,),
            ).fetchone()
            course_id = course[0] if course else conn.execute(
                "INSERT INTO courses (tenant_id, title) VALUES (?, 'Performance 100k')", (tenant_id,)
            ).lastrowid

            for start in range(1, count + 1, 1000):
                indices = range(start, min(start + 1000, count + 1))
                conn.executemany(
                    "INSERT OR IGNORE INTO learners (id, tenant_id, name) VALUES (?, ?, ?)",
                    ((base_id + i, tenant_id, f"Perf Learner {i:06d}") for i in indices),
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO enrollments (tenant_id, course_id, learner_id, status, completed_at_utc) "
                    "VALUES (?, ?, ?, 'COMPLETED', ?)",
                    ((tenant_id, course_id, base_id + i, INSTANT_TEXT) for i in indices),
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO certificates "
                    "(tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')",
                    ((tenant_id, course_id, base_id + i, f"PERF-{prefix}-{i:06d}", INSTANT_TEXT, local_date) for i in indices),
                )
            conn.execute(
                "INSERT OR IGNORE INTO audit_events "
                "(tenant_id, certificate_id, actor_id, event_type, occurred_at_utc) "
                "SELECT tenant_id, id, ?, 'ISSUED', issued_at_utc FROM certificates "
                "WHERE tenant_id = ? AND serial_number LIKE ?",
                (actor_id, tenant_id, f"PERF-{prefix}-%"),
            )
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate isolated certificate export performance data")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--tenant", choices=TENANTS, default="East")
    parser.add_argument("--count", type=int, default=100_000)
    args = parser.parse_args()
    seed_performance(args.db, args.tenant, args.count)
    print(f"Seeded {args.count} performance certificates for {args.tenant} in {args.db}")


if __name__ == "__main__":
    main()
