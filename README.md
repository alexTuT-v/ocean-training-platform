# Ocean Training Platform

Multi-tenant certificate administration demo. The React UI and FastAPI API are served from one origin with SQLite storage.

## Start the complete app

Requires Python 3.11+ and Node.js/npm. From the repository root, run one command:

```bash
./run.sh
```

The script installs declared Python and frontend dependencies, builds the frontend, initializes the database and repeatable demo data, then starts `http://127.0.0.1:8000`. It reuses an existing `.venv`. If the shell's default Python is older, set `TRAINING_PYTHON=/path/to/python3.11-or-newer` for this same command. Set `TRAINING_DB_PATH=/path/to/database.sqlite3` to use an isolated database.

New demo and performance seed rows use the UTC time at script execution; certificate local dates are calculated in the tenant's timezone. Seed scripts preserve existing rows on repeat runs, including their original timestamps. Use a fresh database path when you need newly generated rows with a new timestamp.

The UI has two demo actors: Alice (`alice@east.test`, East, `Australia/Sydney`) and Bob (`bob@west.test`, West, `Australia/Perth`). API requests identify an actor with `X-Actor-Email`; the backend resolves the tenant on every request. This header can be impersonated and is not production authentication. No client-supplied tenant ID grants access.

The course enrollment API uses server-side pagination: `GET /api/courses/{id}/enrollments?page=1&page_size=20` (default page size 20, maximum 100). Its response includes the current page of `items`, `page`, `page_size`, `total`, and whole-course `summary` counts for completed, incomplete, and actively certified learners. The course page requests only the visible page. Admins can select eligible learners across pages; **全选本页** selects eligible learners on the visible page only. The selected count is retained across pages.

Bulk issue requires an explicit JSON body such as `{"learner_ids":[1,3]}`. An empty or omitted selection never issues to the whole course. Every ID must belong to the current tenant and course; a learner who becomes ineligible before execution receives a skipped outcome. Saved uncertain requests replay the original body and idempotency key.

To revoke an active certificate, use **撤销** in its certificate-list row, or choose **查看并撤销证书** for a learner on the course completion page. Both paths show a confirmation dialog. The revoked certificate remains in the list, and the learner becomes eligible for a new certificate.

## Verify

```bash
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Tests use temporary databases and do not change `data/training.sqlite3`. For the examples below, use a fresh demo database; the seed certificate IDs are East `1` and West `2`, and each tenant has a `Safety 101` course (IDs `1` and `2`). Scenario tests in `backend/tests/` independently create fresh databases when the examples modify state.

## Reproduce A1–A7

Set `BASE=http://127.0.0.1:8000` after starting the app. Commands below use `curl`; inspect the JSON/CSV and status codes. Run the relevant named test file for database count and concurrent-request assertions.

**A1 — tenant isolation.** Bob sees only West rows. East certificate detail and East course bulk issue return 404 to Bob and create no East write or audit:

```bash
curl -sS -H 'X-Actor-Email: bob@west.test' "$BASE/api/certificates"
curl -sS -H 'X-Actor-Email: bob@west.test' "$BASE/api/certificates/export"
curl -i -H 'X-Actor-Email: bob@west.test' "$BASE/api/certificates/1"
curl -i -X POST -H 'X-Actor-Email: bob@west.test' -H 'Idempotency-Key: a1-cross' -H 'Content-Type: application/json' -d '{"learner_ids":[1]}' "$BASE/api/courses/1/bulk-issue"
.venv/bin/python -m pytest backend/tests/test_actor_courses.py backend/tests/test_idempotency_revoke.py -q
```

**A2 — retry safety.** Send the same operation key twice; `operation_id` and full result stay the same. The test also sends concurrent requests and checks certificates and ISSUED audit counts:

```bash
curl -sS -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a2-same' -H 'Content-Type: application/json' -d '{"learner_ids":[1,2,3]}' "$BASE/api/courses/1/bulk-issue"
curl -sS -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a2-same' -H 'Content-Type: application/json' -d '{"learner_ids":[1,2,3]}' "$BASE/api/courses/1/bulk-issue"
.venv/bin/python -m pytest backend/tests/test_bulk_issue.py -q
```

**A3 — key misuse.** After A2, reuse that key for a different course or payload. Both return 409 without changing the stored A2 result:

```bash
curl -i -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a2-same' -H 'Content-Type: application/json' -d '{"learner_ids":[1,2,3]}' "$BASE/api/courses/999/bulk-issue"
curl -i -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a2-same' -H 'Content-Type: application/json' -d '{"learner_ids":[1]}' "$BASE/api/courses/1/bulk-issue"
```

**A4 — learner outcomes.** On a fresh demo database, course `1` has eligible Alex, incomplete Beth, and already certified Casey. Explicitly selecting all three gives one `issued` and two `skipped` outcomes with reasons:

```bash
curl -sS -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a4-first' -H 'Content-Type: application/json' -d '{"learner_ids":[1,2,3]}' "$BASE/api/courses/1/bulk-issue"
.venv/bin/python -m pytest backend/tests/test_bulk_issue.py -q
```

**A5 — tenant-local date.** New seed certificates share the UTC time at seed execution; East and West details display that instant in their respective tenant timezones. Compare list dates and CSV. The automated test fixture uses a fixed instant to assert exact date conversion:

```bash
curl -sS -H 'X-Actor-Email: alice@east.test' "$BASE/api/certificates/1"
curl -sS -H 'X-Actor-Email: bob@west.test' "$BASE/api/certificates/2"
curl -sS -H 'X-Actor-Email: alice@east.test' "$BASE/api/certificates/export?sort=issued_local_date&direction=desc"
.venv/bin/python -m pytest backend/tests/test_certificate_reads.py -q
```

**A6 — 100,000-row CSV.** Generate a separate performance database; do not modify the quick-start database. Start the API against it in another terminal, then issue the same sorted/search export twice while requesting the list. The automated test checks full CSV contents, stable order, concurrency and a 60-second limit for each download:

```bash
.venv/bin/python -m backend.scripts.seed_performance --db data/performance.sqlite3 --tenant East --count 100000
TRAINING_DB_PATH=data/performance.sqlite3 TRAINING_FRONTEND_DIST=frontend/dist .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
curl -sS -H 'X-Actor-Email: alice@east.test' "$BASE/api/certificates/export?search=Perf%20Learner&sort=issued_local_date&direction=desc" -o data/ocean-export-1.csv &
curl -sS -H 'X-Actor-Email: alice@east.test' "$BASE/api/certificates?page=1&page_size=20"
wait
curl -sS -H 'X-Actor-Email: alice@east.test' "$BASE/api/certificates/export?search=Perf%20Learner&sort=issued_local_date&direction=desc" -o data/ocean-export-2.csv
.venv/bin/python -m pytest backend/tests/test_export_performance.py -q
```

Use a free port or stop the quick-start server before starting the performance server. The automated test creates its own free port.

**A7 — revocation audit.** On a fresh demo database, the first revoke changes status and writes one REVOKED audit; same-key replay and a new-key no-op leave that count at one:

```bash
curl -sS -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a7-first' -H 'Content-Type: application/json' -d '{}' "$BASE/api/certificates/1/revoke"
curl -sS -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a7-first' -H 'Content-Type: application/json' -d '{}' "$BASE/api/certificates/1/revoke"
curl -sS -X POST -H 'X-Actor-Email: alice@east.test' -H 'Idempotency-Key: a7-new' -H 'Content-Type: application/json' -d '{}' "$BASE/api/certificates/1/revoke"
.venv/bin/python -m pytest backend/tests/test_idempotency_revoke.py -q
```

## Known limits and submission materials

The identity header is an assessment demo, not a security boundary against an untrusted client. CSV is streamed by the server; the browser frontend currently holds the downloaded Blob in memory. The 100,000-row performance check is measured by the automated test on the host where it runs, and should be rerun on the reviewer's machine.

Known edge cases after the final review: a bookmarked certificate page beyond the last page can display an empty state without pagination; an extremely large page number can make SQLite reject the offset and return 500; and a JSON string containing an escaped unpaired surrogate can fail idempotency fingerprint encoding with 500. These are deferred low-impact inputs. Browser drills for a response lost after commit and for switching actors during a still-running export have not been performed manually; automated tests cover their retry and tenant-scoping logic.

Assessment submission materials such as complete AI session exports, the session index, decision log and personal written answers are separate from this product code. Their completeness is tracked in `docs/superpowers/checklists/2026-11-23-training-platform-backend.md`; do not mark them complete without the actual artifacts.
