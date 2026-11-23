from fastapi.testclient import TestClient

from backend.app.main import create_app


ALICE = {"X-Actor-Email": "alice@east.test"}


def test_all_json_shapes_match_frontend_contract(seeded_db):
    client = TestClient(create_app(seeded_db))
    me = client.get("/api/me", headers=ALICE)
    assert set(me.json()) == {"admin", "tenant"}
    assert set(me.json()["admin"]) == {"id", "email"}
    assert set(me.json()["tenant"]) == {"id", "name", "timezone"}

    courses = client.get("/api/courses", headers=ALICE).json()
    assert set(courses) == {"items"}
    assert set(courses["items"][0]) == {"id", "title"}
    enrollments = client.get("/api/courses/1/enrollments", headers=ALICE).json()
    assert set(enrollments) == {"course", "items", "page", "page_size", "total", "summary"}
    assert enrollments["summary"] == {"completed": 2, "incomplete": 1, "active_certificates": 1}
    assert set(enrollments["items"][0]) == {"learner_id", "learner_name", "status", "active_certificate_id"}

    listed = client.get("/api/certificates", headers=ALICE).json()
    assert set(listed) == {"items", "page", "page_size", "total"}
    certificate = listed["items"][0]
    assert set(certificate) == {"id", "serial_number", "learner_name", "course_title", "issued_local_date", "status"}
    detail = client.get(f"/api/certificates/{certificate['id']}", headers=ALICE).json()
    assert set(detail) == set(certificate) | {"issued_local_datetime"}

    issued = client.post("/api/courses/1/bulk-issue", headers={**ALICE, "Idempotency-Key": "contract-bulk"}, json={"learner_ids": [1, 2, 3]})
    assert issued.status_code == 200
    assert set(issued.json()) == {"operation_id", "status", "summary", "outcomes"}
    assert set(issued.json()["summary"]) == {"issued", "skipped", "failed"}
    assert set(issued.json()["outcomes"][0]) == {"learner_id", "learner_name", "result", "reason", "certificate_id", "serial_number"}
    assert issued.json()["status"] == "COMPLETED"

    revoked = client.post(f"/api/certificates/{certificate['id']}/revoke", headers={**ALICE, "Idempotency-Key": "contract-revoke"}, json={})
    assert revoked.status_code == 200
    assert set(revoked.json()) == {"operation_id", "certificate_id", "status", "changed"}
    assert revoked.json()["status"] == "REVOKED"


def test_get_after_committed_write_reads_new_state(seeded_db):
    client = TestClient(create_app(seeded_db))
    before = client.get("/api/certificates", headers=ALICE)
    assert before.headers["cache-control"] == "no-store"
    assert before.json()["total"] == 1
    assert client.post("/api/courses/1/bulk-issue", headers={**ALICE, "Idempotency-Key": "fresh-bulk"}, json={"learner_ids": [1]}).status_code == 200
    after_issue = client.get("/api/certificates", headers=ALICE)
    assert after_issue.json()["total"] == 2
    certificate_id = after_issue.json()["items"][0]["id"]
    assert client.post(f"/api/certificates/{certificate_id}/revoke", headers={**ALICE, "Idempotency-Key": "fresh-revoke"}, json={}).status_code == 200
    assert client.get(f"/api/certificates/{certificate_id}", headers=ALICE).json()["status"] == "REVOKED"
