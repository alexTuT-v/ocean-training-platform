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


def test_enrollment_pages_limit_100k_rows_and_keep_course_totals(tmp_path):
    from backend.scripts.seed_performance import seed_performance

    db_path = tmp_path / "large-course.sqlite3"
    seed_performance(db_path, tenant="East", count=100_000)
    seed_performance(db_path, tenant="West", count=1)
    client = client_for(db_path)
    course_id = client.get("/api/courses", headers=ALICE).json()["items"][0]["id"]
    url = f"/api/courses/{course_id}/enrollments"
    first = client.get(url, headers=ALICE)
    assert first.status_code == 200
    assert first.json()["page"] == 1
    assert first.json()["page_size"] == 20
    assert first.json()["total"] == 100_000
    assert first.json()["summary"] == {"completed": 100_000, "incomplete": 0, "active_certificates": 100_000}
    assert len(first.json()["items"]) == 20
    second = client.get(url, params={"page": 2, "page_size": 20}, headers=ALICE)
    assert second.status_code == 200
    assert len(second.json()["items"]) == 20
    assert first.json()["items"][-1]["learner_id"] < second.json()["items"][0]["learner_id"]
    assert second.json()["summary"] == first.json()["summary"]
    assert client.get(url, params={"page": 5001, "page_size": 20}, headers=ALICE).json()["items"] == []
    assert client.get(url, params={"page_size": 101}, headers=ALICE).status_code == 422
    assert client.get(url, params={"tenant_id": 1}, headers=ALICE).status_code == 422
    assert client.get(url, headers=BOB).status_code == 404
