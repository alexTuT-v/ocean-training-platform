import importlib

from fastapi.testclient import TestClient

from backend.app.db import connect


ALICE = {"X-Actor-Email": "alice@east.test"}
BOB = {"X-Actor-Email": "bob@west.test"}


def client_for(path):
    main = importlib.import_module("backend.app.main")
    return TestClient(main.create_app(path))


def test_me_matches_frontend_contract(seeded_db):
    client = client_for(seeded_db)
    response = client.get("/api/me", headers=ALICE)
    assert response.status_code == 200
    assert response.json() == {
        "admin": {"id": 1, "email": "alice@east.test"},
        "tenant": {"id": 1, "name": "East", "timezone": "Australia/Sydney"},
    }


def test_actor_is_resolved_per_request(seeded_db):
    client = client_for(seeded_db)
    alice_course = client.get("/api/courses", headers=ALICE).json()["items"]
    bob_course = client.get("/api/courses", headers=BOB).json()["items"]
    alice_again = client.get("/api/courses", headers=ALICE).json()["items"]
    assert alice_course == alice_again == [{"id": 1, "title": "Safety 101"}]
    assert bob_course == [{"id": 2, "title": "Safety 101"}]
    assert client.get("/api/me", headers=BOB).json()["tenant"]["name"] == "West"


def test_course_enrollments_show_only_active_certificate(seeded_db):
    client = client_for(seeded_db)
    response = client.get("/api/courses/1/enrollments", headers=ALICE)
    assert response.status_code == 200
    assert response.json()["course"] == {"id": 1, "title": "Safety 101"}
    rows = {item["learner_name"]: item for item in response.json()["items"]}
    assert rows["Alex Lee"]["status"] == "COMPLETED"
    assert rows["Alex Lee"]["active_certificate_id"] is None
    assert rows["Beth Stone"]["status"] == "INCOMPLETE"
    assert rows["Casey Wong"]["active_certificate_id"] is not None
    assert set(rows["Alex Lee"]) == {"learner_id", "learner_name", "status", "active_certificate_id"}

    with connect(seeded_db) as conn:
        conn.execute("UPDATE certificates SET status = 'REVOKED' WHERE serial_number = 'EAST-SEED-001'")
    refreshed = client.get("/api/courses/1/enrollments", headers=ALICE).json()["items"]
    assert {item["learner_name"]: item for item in refreshed}["Casey Wong"]["active_certificate_id"] is None


def test_unknown_actor_and_cross_tenant_course(seeded_db):
    client = client_for(seeded_db)
    for headers in ({}, {"X-Actor-Email": "unknown@example.test"}):
        response = client.get("/api/me", headers=headers)
        assert response.status_code == 401
        assert set(response.json()) == {"code", "message"}

    cross_tenant = client.get("/api/courses/1/enrollments", headers=BOB)
    assert cross_tenant.status_code == 404
    assert set(cross_tenant.json()) == {"code", "message"}
    assert client.get("/api/courses?tenant_id=1", headers=BOB).status_code == 422
