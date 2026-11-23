from concurrent.futures import ThreadPoolExecutor
import importlib
from threading import Barrier

from fastapi.testclient import TestClient

from backend.app.db import connect


ALICE = {"X-Actor-Email": "alice@east.test"}
BOB = {"X-Actor-Email": "bob@west.test"}


def app_for(path):
    return importlib.import_module("backend.app.main").create_app(path)


def east_certificate_id(client):
    return client.get("/api/certificates", headers=ALICE).json()["items"][0]["id"]


def table_count(path, table, where="1=1"):
    with connect(path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]


def test_write_validation_and_conflict_order(seeded_db):
    client = TestClient(app_for(seeded_db))
    certificate_id = east_certificate_id(client)
    url = f"/api/certificates/{certificate_id}/revoke"
    before = table_count(seeded_db, "idempotency_records")
    for header, payload in ((None, {}), (" ", {}), ("x" * 129, {}), ("bad-json", []), ("extra", {"unexpected": 1})):
        headers = {**ALICE, **({"Idempotency-Key": header} if header is not None else {})}
        response = client.post(url, headers=headers, json=payload)
        assert response.status_code == 422
        assert set(response.json()) == {"code", "message"}
    assert table_count(seeded_db, "idempotency_records") == before
    assert client.get(url.replace("/revoke", ""), headers=ALICE).json()["status"] == "ACTIVE"

    first = client.post(url, headers={**ALICE, "Idempotency-Key": "first-key"}, json={})
    assert first.status_code == 200
    conflicting_body = client.post(url, headers={**ALICE, "Idempotency-Key": "first-key"}, json={"unexpected": 1})
    conflicting_path = client.post("/api/certificates/999999/revoke", headers={**ALICE, "Idempotency-Key": "first-key"}, json={})
    assert conflicting_body.status_code == conflicting_path.status_code == 409
    assert table_count(seeded_db, "idempotency_records") == before + 1


def test_revoke_lost_response_replays_first_result(seeded_db):
    client = TestClient(app_for(seeded_db))
    certificate_id = east_certificate_id(client)
    url = f"/api/certificates/{certificate_id}/revoke"
    headers = {**ALICE, "Idempotency-Key": "lost-response"}
    first = client.post(url, headers=headers, json={})
    replay = client.post(url, headers=headers, json={})
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json() == {
        "operation_id": first.json()["operation_id"],
        "certificate_id": certificate_id,
        "status": "REVOKED",
        "changed": True,
    }
    assert client.get(f"/api/certificates/{certificate_id}", headers=ALICE).json()["status"] == "REVOKED"
    assert table_count(seeded_db, "idempotency_records") == 1
    assert table_count(seeded_db, "audit_events", "event_type = 'REVOKED'") == 1


def test_new_key_revoke_is_noop_with_one_audit(seeded_db):
    client = TestClient(app_for(seeded_db))
    certificate_id = east_certificate_id(client)
    url = f"/api/certificates/{certificate_id}/revoke"
    first = client.post(url, headers={**ALICE, "Idempotency-Key": "one"}, json={})
    second = client.post(url, headers={**ALICE, "Idempotency-Key": "two"}, json={})
    assert first.json()["changed"] is True
    assert second.status_code == 200
    assert second.json()["changed"] is False
    assert second.json()["operation_id"] != first.json()["operation_id"]
    assert table_count(seeded_db, "idempotency_records") == 2
    assert table_count(seeded_db, "audit_events", "event_type = 'REVOKED'") == 1


def test_cross_tenant_revoke_has_no_record_or_audit(seeded_db):
    client = TestClient(app_for(seeded_db))
    certificate_id = east_certificate_id(client)
    before = table_count(seeded_db, "audit_events")
    hidden = client.post(f"/api/certificates/{certificate_id}/revoke", headers={**BOB, "Idempotency-Key": "bob-cross"}, json={})
    missing = client.post("/api/certificates/999999/revoke", headers={**BOB, "Idempotency-Key": "bob-missing"}, json={})
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    assert table_count(seeded_db, "idempotency_records") == 0
    assert table_count(seeded_db, "audit_events") == before
    assert client.get(f"/api/certificates/{certificate_id}", headers=ALICE).json()["status"] == "ACTIVE"
    valid = client.post(f"/api/certificates/{certificate_id}/revoke", headers={**ALICE, "Idempotency-Key": "alice-valid"}, json={})
    assert valid.status_code == 200
    assert valid.json()["changed"] is True


def test_same_key_parallel_revoke_replays_one_result(seeded_db):
    app = app_for(seeded_db)
    certificate_id = east_certificate_id(TestClient(app))
    barrier = Barrier(3)

    def revoke():
        barrier.wait()
        return TestClient(app).post(
            f"/api/certificates/{certificate_id}/revoke",
            headers={**ALICE, "Idempotency-Key": "parallel-revoke"},
            json={},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(revoke) for _ in range(2)]
        barrier.wait()
        results = [future.result() for future in futures]
    assert [response.status_code for response in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert table_count(seeded_db, "idempotency_records") == 1
    assert table_count(seeded_db, "audit_events", "event_type = 'REVOKED'") == 1
