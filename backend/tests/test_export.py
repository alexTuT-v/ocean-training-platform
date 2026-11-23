from concurrent.futures import ThreadPoolExecutor
import csv
from io import StringIO
import importlib

from fastapi.testclient import TestClient

from backend.app.db import connect


ALICE = {"X-Actor-Email": "alice@east.test"}
BOB = {"X-Actor-Email": "bob@west.test"}
HEADER = ["learner_name", "course_title", "serial_number", "issued_local_date"]


def client_for(path):
    return TestClient(importlib.import_module("backend.app.main").create_app(path))


def csv_rows(response):
    return list(csv.reader(StringIO(response.text)))


def test_export_route_precedes_detail(seeded_db):
    client = client_for(seeded_db)
    response = client.get("/api/certificates/export", headers=ALICE)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    assert csv_rows(response) == [HEADER, ["Casey Wong", "Safety 101", "EAST-SEED-001", "2026-01-11"]]
    assert client.get("/api/certificates/export?tenant_id=2", headers=ALICE).status_code == 422


def test_export_filters_sort_and_quotes_csv(seeded_db):
    with connect(seeded_db) as conn:
        east = conn.execute("SELECT id FROM tenants WHERE name = 'East'").fetchone()[0]
        course = conn.execute("SELECT id FROM courses WHERE tenant_id = ?", (east,)).fetchone()[0]
        learner = conn.execute("INSERT INTO learners (tenant_id, name) VALUES (?, ?)", (east, 'Ana, "Q"')).lastrowid
        conn.execute("INSERT INTO enrollments (tenant_id, course_id, learner_id, status) VALUES (?, ?, ?, 'COMPLETED')", (east, course, learner))
        conn.execute(
            "INSERT INTO certificates (tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date, status) "
            "VALUES (?, ?, ?, ?, '2026-01-10T13:30:00Z', '2026-01-11', 'REVOKED')",
            (east, course, learner, 'SERIAL,"LINE\n2'),
        )
    client = client_for(seeded_db)
    searched = client.get("/api/certificates/export?search=ANA&sort=serial_number&direction=desc", headers=ALICE)
    assert searched.status_code == 200
    assert csv_rows(searched) == [HEADER, ['Ana, "Q"', "Safety 101", 'SERIAL,"LINE\n2', "2026-01-11"]]
    all_rows = csv_rows(client.get("/api/certificates/export?sort=serial_number&direction=asc", headers=ALICE))
    assert [row[2] for row in all_rows[1:]] == ["EAST-SEED-001", 'SERIAL,"LINE\n2']


def test_concurrent_export_and_other_actor_list(seeded_db):
    client = client_for(seeded_db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        export_future = pool.submit(client.get, "/api/certificates/export", headers=ALICE)
        list_future = pool.submit(client.get, "/api/certificates", headers=BOB)
        exported, listed = export_future.result(), list_future.result()
    assert exported.status_code == listed.status_code == 200
    assert csv_rows(exported)[1][2] == "EAST-SEED-001"
    assert [item["serial_number"] for item in listed.json()["items"]] == ["WEST-SEED-001"]


def test_unicode_casefold_search_matches_list_and_csv_without_wildcards(seeded_db):
    with connect(seeded_db) as conn:
        east = conn.execute("SELECT id FROM tenants WHERE name = 'East'").fetchone()[0]
        course = conn.execute("SELECT id FROM courses WHERE tenant_id = ?", (east,)).fetchone()[0]
        for name, serial in (("Élodie_100%", "ACCENT-ONE"), ("Élodiex100x", "ACCENT-TWO")):
            learner = conn.execute("INSERT INTO learners (tenant_id, name) VALUES (?, ?)", (east, name)).lastrowid
            conn.execute("INSERT INTO enrollments (tenant_id, course_id, learner_id, status) VALUES (?, ?, ?, 'COMPLETED')", (east, course, learner))
            conn.execute(
                "INSERT INTO certificates (tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date, status) "
                "VALUES (?, ?, ?, ?, '2026-01-10T13:30:00Z', '2026-01-11', 'ACTIVE')",
                (east, course, learner, serial),
            )
    client = client_for(seeded_db)
    response = client.get("/api/certificates", params={"search": "élodie_100%"}, headers=ALICE)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [row["serial_number"] for row in response.json()["items"]] == ["ACCENT-ONE"]
    exported = client.get("/api/certificates/export", params={"search": "élodie_100%"}, headers=ALICE)
    assert exported.status_code == 200
    assert csv_rows(exported) == [HEADER, ["Élodie_100%", "Safety 101", "ACCENT-ONE", "2026-01-11"]]
