import importlib

from fastapi.testclient import TestClient

from backend.app.db import connect


ALICE = {"X-Actor-Email": "alice@east.test"}
BOB = {"X-Actor-Email": "bob@west.test"}


def client_for(path):
    return TestClient(importlib.import_module("backend.app.main").create_app(path))


def add_east_history(path):
    with connect(path) as conn:
        east = conn.execute("SELECT id FROM tenants WHERE name = 'East'").fetchone()[0]
        course = conn.execute("SELECT id FROM courses WHERE tenant_id = ?", (east,)).fetchone()[0]
        learner = conn.execute("SELECT id FROM learners WHERE tenant_id = ? AND name = 'Casey Wong'", (east,)).fetchone()[0]
        for serial in ("EAST-OLD-002", "EAST-OLD-003"):
            conn.execute(
                "INSERT INTO certificates (tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date, status) "
                "VALUES (?, ?, ?, ?, '2026-01-10T13:30:00Z', '2026-01-11', 'REVOKED')",
                (east, course, learner, serial),
            )


def test_search_sort_page_and_total_share_snapshot(seeded_db):
    add_east_history(seeded_db)
    client = client_for(seeded_db)
    response = client.get("/api/certificates?search=casey&sort=issued_local_date&direction=desc&page=1&page_size=1", headers=ALICE)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    first = response.json()
    assert first["total"] == 3
    assert (first["page"], first["page_size"]) == (1, 1)
    assert first["items"][0]["serial_number"] == "EAST-SEED-001"
    second = client.get("/api/certificates?search=casey&sort=issued_local_date&direction=desc&page=2&page_size=1", headers=ALICE).json()
    assert second["items"][0]["serial_number"] == "EAST-OLD-002"

    serial_search = client.get("/api/certificates?search=east-old-003", headers=ALICE).json()
    assert serial_search["total"] == 1
    assert serial_search["items"][0]["serial_number"] == "EAST-OLD-003"
    assert client.get("/api/certificates?search=", headers=ALICE).json()["total"] == 3
    assert client.get("/api/certificates?page=20&page_size=1", headers=ALICE).json()["items"] == []
    serial_order = client.get("/api/certificates?sort=serial_number&direction=asc", headers=ALICE).json()["items"]
    assert [item["serial_number"] for item in serial_order] == ["EAST-OLD-002", "EAST-OLD-003", "EAST-SEED-001"]
    assert set(first["items"][0]) == {"id", "serial_number", "learner_name", "course_title", "issued_local_date", "status"}


def test_detail_local_datetime_and_revoked_visible(seeded_db):
    client = client_for(seeded_db)
    east_id = client.get("/api/certificates", headers=ALICE).json()["items"][0]["id"]
    west_id = client.get("/api/certificates", headers=BOB).json()["items"][0]["id"]
    east = client.get(f"/api/certificates/{east_id}", headers=ALICE)
    west = client.get(f"/api/certificates/{west_id}", headers=BOB)
    assert east.json()["issued_local_date"] == "2026-01-11"
    assert east.json()["issued_local_datetime"] == "2026-01-11 00:30"
    assert west.json()["issued_local_date"] == "2026-01-10"
    assert west.json()["issued_local_datetime"] == "2026-01-10 21:30"

    with connect(seeded_db) as conn:
        conn.execute("UPDATE certificates SET status = 'REVOKED' WHERE id = ?", (east_id,))
    assert client.get(f"/api/certificates/{east_id}", headers=ALICE).json()["status"] == "REVOKED"
    assert client.get("/api/certificates", headers=ALICE).json()["items"][0]["status"] == "REVOKED"


def test_cross_tenant_detail_is_404(seeded_db):
    client = client_for(seeded_db)
    east_id = client.get("/api/certificates", headers=ALICE).json()["items"][0]["id"]
    hidden = client.get(f"/api/certificates/{east_id}", headers=BOB)
    missing = client.get("/api/certificates/999999", headers=BOB)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json() == {"code": "NOT_FOUND", "message": "资源不存在"}
    assert all("EAST" not in item["serial_number"] for item in client.get("/api/certificates", headers=BOB).json()["items"])


def test_bad_query_and_unknown_tenant_filter_422(seeded_db):
    client = client_for(seeded_db)
    for query in ("sort=invalid", "direction=sideways", "page=0", "page_size=101", "tenant_id=1"):
        response = client.get(f"/api/certificates?{query}", headers=ALICE)
        assert response.status_code == 422, query
        assert set(response.json()) == {"code", "message"}
