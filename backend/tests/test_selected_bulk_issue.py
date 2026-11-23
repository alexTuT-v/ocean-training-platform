from fastapi.testclient import TestClient

from backend.app.db import connect
from backend.app.main import create_app
from backend.scripts.seed_performance import seed_performance


ALICE = {"X-Actor-Email": "alice@east.test"}


def learner_ids(path):
    with connect(path) as conn:
        return {
            (row["tenant"], row["name"]): row["id"]
            for row in conn.execute(
                "SELECT tenants.name AS tenant, learners.name, learners.id "
                "FROM learners JOIN tenants ON tenants.id = learners.tenant_id"
            )
        }


def counts(path):
    with connect(path) as conn:
        return tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("certificates", "audit_events", "idempotency_records"))


def test_issues_only_selected_learners_and_reports_stale_eligibility(seeded_db):
    ids = learner_ids(seeded_db)
    alex = ids["East", "Alex Lee"]
    casey = ids["East", "Casey Wong"]
    client = TestClient(create_app(seeded_db))
    response = client.post(
        "/api/courses/1/bulk-issue",
        headers={**ALICE, "Idempotency-Key": "selected-subset"},
        json={"learner_ids": [casey, alex]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {"issued": 1, "skipped": 1, "failed": 0}
    assert [row["learner_id"] for row in body["outcomes"]] == [alex, casey]
    assert [row["result"] for row in body["outcomes"]] == ["issued", "skipped"]
    assert body["outcomes"][1]["reason"] == "已有有效证书"
    assert counts(seeded_db) == (3, 3, 1)


def test_invalid_or_out_of_scope_selections_write_nothing(seeded_db):
    ids = learner_ids(seeded_db)
    alex = ids["East", "Alex Lee"]
    west_alex = ids["West", "Alex Lee"]
    with connect(seeded_db) as conn:
        east_id = conn.execute("SELECT id FROM tenants WHERE name = 'East'").fetchone()[0]
        second_course = conn.execute("INSERT INTO courses (tenant_id, title) VALUES (?, 'Other Course')", (east_id,)).lastrowid
        wrong_course_learner = conn.execute("INSERT INTO learners (tenant_id, name) VALUES (?, 'Other Learner')", (east_id,)).lastrowid
        conn.execute("INSERT INTO enrollments (tenant_id, course_id, learner_id, status) VALUES (?, ?, ?, 'COMPLETED')", (east_id, second_course, wrong_course_learner))
    client = TestClient(create_app(seeded_db))
    before = counts(seeded_db)
    for index, body in enumerate((
        {}, {"learner_ids": []}, {"learner_ids": [True]},
        {"learner_ids": [alex, alex]}, {"learner_ids": [0]}, {"learner_ids": [2**64]},
        {"learner_ids": [999999]}, {"learner_ids": [west_alex]}, {"learner_ids": [wrong_course_learner]},
        {"learner_ids": [alex], "extra": True},
    )):
        response = client.post(
            "/api/courses/1/bulk-issue",
            headers={**ALICE, "Idempotency-Key": f"invalid-selection-{index}"},
            json=body,
        )
        assert response.status_code == 422
        assert set(response.json()) == {"code", "message"}
    assert counts(seeded_db) == before


def test_same_key_replays_selected_body_and_rejects_changed_selection(seeded_db):
    ids = learner_ids(seeded_db)
    alex = ids["East", "Alex Lee"]
    casey = ids["East", "Casey Wong"]
    client = TestClient(create_app(seeded_db))
    url = "/api/courses/1/bulk-issue"
    headers = {**ALICE, "Idempotency-Key": "selected-replay"}
    first = client.post(url, headers=headers, json={"learner_ids": [alex]})
    replay = client.post(url, headers=headers, json={"learner_ids": [alex]})
    changed = client.post(url, headers=headers, json={"learner_ids": [casey]})
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert changed.status_code == 409
    assert counts(seeded_db) == (3, 3, 1)


def test_large_course_request_returns_only_selected_outcomes(tmp_path):
    path = tmp_path / "large-course.sqlite3"
    seed_performance(path, tenant="East", count=100_000)
    client = TestClient(create_app(path))
    course_id = client.get("/api/courses", headers=ALICE).json()["items"][0]["id"]
    response = client.post(
        f"/api/courses/{course_id}/bulk-issue",
        headers={**ALICE, "Idempotency-Key": "large-subset"},
        json={"learner_ids": [1_100_000, 1_000_001]},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == {"issued": 0, "skipped": 2, "failed": 0}
    assert [row["learner_id"] for row in response.json()["outcomes"]] == [1_000_001, 1_100_000]
