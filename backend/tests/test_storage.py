from datetime import datetime, timezone
import importlib
import sqlite3

import pytest


def storage():
    return importlib.import_module("backend.app.db"), importlib.import_module("backend.app.seed")


def test_schema_rejects_cross_tenant_links_and_duplicate_active_certificate(tmp_path):
    db, seed = storage()
    path = tmp_path / "training.sqlite3"
    db.initialize_database(path)
    seed.seed_demo_data(path)

    with db.connect(path) as conn:
        east = conn.execute("SELECT id FROM tenants WHERE name = 'East'").fetchone()[0]
        west_learner = conn.execute(
            "SELECT learners.id FROM learners JOIN tenants ON tenants.id = learners.tenant_id "
            "WHERE tenants.name = 'West' LIMIT 1"
        ).fetchone()[0]
        east_course = conn.execute("SELECT id FROM courses WHERE tenant_id = ? LIMIT 1", (east,)).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO enrollments (tenant_id, course_id, learner_id, status) VALUES (?, ?, ?, 'COMPLETED')",
                (east, east_course, west_learner),
            )

        active = conn.execute(
            "SELECT tenant_id, course_id, learner_id FROM certificates WHERE status = 'ACTIVE' LIMIT 1"
        ).fetchone()
        assert active is not None
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO certificates (tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date, status) "
                "VALUES (?, ?, ?, 'DUPLICATE-1', '2026-01-10T13:30:00Z', '2026-01-11', 'ACTIVE')",
                tuple(active),
            )


def test_seed_is_repeatable_and_preserves_existing_business_data(tmp_path):
    db, seed = storage()
    path = tmp_path / "training.sqlite3"
    db.initialize_database(path)
    seed.seed_demo_data(path)
    with db.connect(path) as conn:
        counts_before = tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("tenants", "admins", "courses", "learners", "enrollments", "certificates", "audit_events")
        )
        assert conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM courses WHERE title = 'Safety 101'").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM learners WHERE name = 'Alex Lee'").fetchone()[0] == 2
        assert {row[0] for row in conn.execute("SELECT DISTINCT status FROM enrollments")} == {"COMPLETED", "INCOMPLETE"}
        certificate_id = conn.execute("SELECT id FROM certificates ORDER BY id LIMIT 1").fetchone()[0]
        conn.execute("UPDATE certificates SET status = 'REVOKED' WHERE id = ?", (certificate_id,))

    seed.seed_demo_data(path)
    with db.connect(path) as conn:
        counts_after = tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("tenants", "admins", "courses", "learners", "enrollments", "certificates", "audit_events")
        )
        assert counts_after == counts_before
        assert conn.execute("SELECT status FROM certificates WHERE id = ?", (certificate_id,)).fetchone()[0] == "REVOKED"


def test_sydney_perth_local_dates():
    dates = importlib.import_module("backend.app.dates")
    instant = datetime(2026, 1, 10, 13, 30, tzinfo=timezone.utc)
    assert dates.to_local(instant, "Australia/Sydney") == ("2026-01-11", "2026-01-11 00:30")
    assert dates.to_local(instant, "Australia/Perth") == ("2026-01-10", "2026-01-10 21:30")
