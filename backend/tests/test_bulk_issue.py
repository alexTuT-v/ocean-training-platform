from concurrent.futures import ThreadPoolExecutor
import importlib
from threading import Barrier

from fastapi.testclient import TestClient

from backend.app.db import connect


ALICE = {"X-Actor-Email": "alice@east.test"}


def app_for(path):
    return importlib.import_module("backend.app.main").create_app(path)


def issue(client, key, course_id=1, learner_ids=None):
    return client.post(
        f"/api/courses/{course_id}/bulk-issue",
        headers={**ALICE, "Idempotency-Key": key},
        json={"learner_ids": [1, 2, 3] if learner_ids is None else learner_ids},
    )


def count(path, table, condition="1=1"):
    with connect(path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}").fetchone()[0]


def test_completed_incomplete_and_certified_outcomes(seeded_db):
    client = TestClient(app_for(seeded_db))
    result = issue(client, "first-bulk")
    assert result.status_code == 200
    body = result.json()
    assert set(body) == {"operation_id", "status", "summary", "outcomes"}
    assert body["status"] == "COMPLETED"
    assert body["summary"] == {"issued": 1, "skipped": 2, "failed": 0}
    assert [row["learner_id"] for row in body["outcomes"]] == sorted(row["learner_id"] for row in body["outcomes"])
    outcomes = {row["learner_name"]: row for row in body["outcomes"]}
    assert outcomes["Alex Lee"]["result"] == "issued"
    assert outcomes["Alex Lee"]["reason"] is None
    assert outcomes["Alex Lee"]["certificate_id"] is not None
    assert outcomes["Alex Lee"]["serial_number"]
    for name in ("Beth Stone", "Casey Wong"):
        assert outcomes[name]["result"] == "skipped"
        assert outcomes[name]["reason"]
        assert outcomes[name]["certificate_id"] is None
        assert outcomes[name]["serial_number"] is None
    assert count(seeded_db, "certificates") == 3
    assert count(seeded_db, "audit_events", "event_type = 'ISSUED'") == 3


def test_same_key_sequential_and_parallel_bulk_issue(seeded_db):
    app = app_for(seeded_db)
    barrier = Barrier(3)

    def concurrent():
        barrier.wait()
        return issue(TestClient(app), "parallel-bulk")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(concurrent) for _ in range(2)]
        barrier.wait()
        parallel = [future.result() for future in futures]
    assert [response.status_code for response in parallel] == [200, 200]
    assert parallel[0].json() == parallel[1].json()
    assert parallel[0].json()["summary"] == {"issued": 1, "skipped": 2, "failed": 0}
    replay = issue(TestClient(app), "parallel-bulk")
    assert replay.status_code == 200
    assert replay.json() == parallel[0].json()
    assert count(seeded_db, "idempotency_records") == 1
    assert count(seeded_db, "certificates") == 3
    assert count(seeded_db, "audit_events", "event_type = 'ISSUED'") == 3


def test_key_reuse_across_courses_or_write_types_is_409(seeded_db):
    with connect(seeded_db) as conn:
        tenant_id = conn.execute("SELECT id FROM tenants WHERE name = 'East'").fetchone()[0]
        learner_id = conn.execute("SELECT id FROM learners WHERE tenant_id = ? AND name = 'Alex Lee'", (tenant_id,)).fetchone()[0]
        course_id = conn.execute("INSERT INTO courses (tenant_id, title) VALUES (?, 'Second Course')", (tenant_id,)).lastrowid
        conn.execute(
            "INSERT INTO enrollments (tenant_id, course_id, learner_id, status) VALUES (?, ?, ?, 'COMPLETED')",
            (tenant_id, course_id, learner_id),
        )
    client = TestClient(app_for(seeded_db))
    assert issue(client, "shared-key").status_code == 200
    assert issue(client, "shared-key", course_id).status_code == 409
    certificate_id = client.get("/api/certificates?search=EAST-SEED-001", headers=ALICE).json()["items"][0]["id"]
    conflict = client.post(f"/api/certificates/{certificate_id}/revoke", headers={**ALICE, "Idempotency-Key": "shared-key"}, json={})
    assert conflict.status_code == 409
    assert count(seeded_db, "idempotency_records") == 1
    assert count(seeded_db, "certificates", f"course_id = {course_id}") == 0
    assert count(seeded_db, "audit_events", "event_type = 'REVOKED'") == 0


def test_row_failure_rolls_back_only_that_learner(seeded_db):
    with connect(seeded_db) as conn:
        tenant_id = conn.execute("SELECT id FROM tenants WHERE name = 'East'").fetchone()[0]
        course_id = conn.execute("SELECT id FROM courses WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
        alex_id = conn.execute("SELECT id FROM learners WHERE tenant_id = ? AND name = 'Alex Lee'", (tenant_id,)).fetchone()[0]
        dana_id = conn.execute("INSERT INTO learners (tenant_id, name) VALUES (?, 'Dana Li')", (tenant_id,)).lastrowid
        conn.execute(
            "INSERT INTO enrollments (tenant_id, course_id, learner_id, status) VALUES (?, ?, ?, 'COMPLETED')",
            (tenant_id, course_id, dana_id),
        )
        conn.execute(
            f"CREATE TRIGGER reject_alex_certificate BEFORE INSERT ON certificates "
            f"WHEN NEW.learner_id = {alex_id} BEGIN SELECT RAISE(ABORT, 'blocked learner'); END"
        )
    client = TestClient(app_for(seeded_db))
    response = issue(client, "row-failure", learner_ids=[1, 2, 3, dana_id])
    assert response.status_code == 200
    assert response.json()["summary"] == {"issued": 1, "skipped": 2, "failed": 1}
    outcomes = {row["learner_name"]: row for row in response.json()["outcomes"]}
    assert outcomes["Alex Lee"]["result"] == "failed"
    assert outcomes["Alex Lee"]["reason"]
    assert outcomes["Alex Lee"]["certificate_id"] is None
    assert outcomes["Dana Li"]["result"] == "issued"
    assert count(seeded_db, "certificates", f"learner_id = {alex_id}") == 0
    assert count(seeded_db, "certificates", f"learner_id = {dana_id}") == 1
    assert count(seeded_db, "audit_events", "event_type = 'ISSUED'") == 3


def test_reissue_after_revocation_creates_new_serial(seeded_db):
    client = TestClient(app_for(seeded_db))
    old_id = client.get("/api/certificates?search=EAST-SEED-001", headers=ALICE).json()["items"][0]["id"]
    revoked = client.post(f"/api/certificates/{old_id}/revoke", headers={**ALICE, "Idempotency-Key": "revoke-old"}, json={})
    assert revoked.status_code == 200
    result = issue(client, "issue-again")
    assert result.status_code == 200
    outcomes = {row["learner_name"]: row for row in result.json()["outcomes"]}
    assert outcomes["Casey Wong"]["result"] == "issued"
    assert outcomes["Casey Wong"]["certificate_id"] != old_id
    assert outcomes["Casey Wong"]["serial_number"] != "EAST-SEED-001"
    assert client.get(f"/api/certificates/{old_id}", headers=ALICE).json()["status"] == "REVOKED"
    assert count(seeded_db, "audit_events", "event_type = 'REVOKED'") == 1
    assert count(seeded_db, "audit_events", "event_type = 'ISSUED'") == 4
