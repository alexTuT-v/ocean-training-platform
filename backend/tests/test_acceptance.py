import csv
from io import StringIO

from fastapi.testclient import TestClient

from backend.app.db import connect
from backend.app.main import create_app


ALICE = {"X-Actor-Email": "alice@east.test"}
BOB = {"X-Actor-Email": "bob@west.test"}


def test_end_to_end_actor_issue_revoke_export(seeded_db):
    client = TestClient(create_app(seeded_db))
    assert client.get("/api/me", headers=ALICE).json()["tenant"]["name"] == "East"
    assert client.get("/api/courses", headers=ALICE).json()["items"] == [{"id": 1, "title": "Safety 101"}]
    eligible = client.get("/api/courses/1/enrollments", headers=ALICE).json()["items"]
    assert {row["learner_name"]: row["active_certificate_id"] for row in eligible}["Alex Lee"] is None

    issued = client.post("/api/courses/1/bulk-issue", headers={**ALICE, "Idempotency-Key": "e2e-issue"}, json={})
    assert issued.status_code == 200
    assert issued.json()["summary"] == {"issued": 1, "skipped": 2, "failed": 0}
    alex = next(row for row in issued.json()["outcomes"] if row["learner_name"] == "Alex Lee")
    certificate_id = alex["certificate_id"]
    assert certificate_id is not None
    assert client.get("/api/certificates", headers=ALICE).json()["total"] == 2
    assert client.get(f"/api/certificates/{certificate_id}", headers=ALICE).json()["status"] == "ACTIVE"

    revoke_headers = {**ALICE, "Idempotency-Key": "e2e-revoke"}
    first = client.post(f"/api/certificates/{certificate_id}/revoke", headers=revoke_headers, json={})
    replay = client.post(f"/api/certificates/{certificate_id}/revoke", headers=revoke_headers, json={})
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["changed"] is True
    assert client.get(f"/api/certificates/{certificate_id}", headers=ALICE).json()["status"] == "REVOKED"
    assert client.get(f"/api/certificates?search={alex['serial_number']}", headers=ALICE).json()["items"][0]["status"] == "REVOKED"
    exported = client.get(f"/api/certificates/export?search={alex['serial_number']}", headers=ALICE)
    csv_rows = list(csv.reader(StringIO(exported.text)))
    assert exported.status_code == 200
    assert len(csv_rows) == 2
    assert csv_rows[1][:3] == ["Alex Lee", "Safety 101", alex["serial_number"]]

    assert client.get("/api/me", headers=BOB).json()["tenant"]["name"] == "West"
    assert [row["serial_number"] for row in client.get("/api/certificates", headers=BOB).json()["items"]] == ["WEST-SEED-001"]
    assert "EAST" not in client.get("/api/certificates/export", headers=BOB).text
    cross = client.post("/api/courses/1/bulk-issue", headers={**BOB, "Idempotency-Key": "e2e-cross"}, json={})
    assert cross.status_code == 404
    with connect(seeded_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM idempotency_records").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE event_type = 'REVOKED'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE event_type = 'ISSUED'").fetchone()[0] == 3


def test_unexpected_database_error_has_safe_json_envelope(tmp_path):
    uninitialized = tmp_path / "uninitialized.sqlite3"
    client = TestClient(create_app(uninitialized), raise_server_exceptions=False)
    response = client.get("/api/me", headers=ALICE)
    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL_ERROR", "message": "服务暂时不可用"}


def test_me_rejects_client_tenant_override(seeded_db):
    client = TestClient(create_app(seeded_db))
    response = client.get("/api/me?tenant_id=2", headers=ALICE)
    assert response.status_code == 422
    assert set(response.json()) == {"code", "message"}


def test_bulk_issue_rejects_invalid_write_requests_without_side_effects(seeded_db):
    client = TestClient(create_app(seeded_db))
    with connect(seeded_db) as conn:
        before = tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("certificates", "audit_events", "idempotency_records")
        )
    for key, body in ((None, {}), (" ", {}), ("x" * 129, {}), ("invalid-body", [])):
        headers = {**ALICE, **({"Idempotency-Key": key} if key is not None else {})}
        response = client.post("/api/courses/1/bulk-issue", headers=headers, json=body)
        assert response.status_code == 422
        assert set(response.json()) == {"code", "message"}
    with connect(seeded_db) as conn:
        after = tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("certificates", "audit_events", "idempotency_records")
        )
    assert after == before
