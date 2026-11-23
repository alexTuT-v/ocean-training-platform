import csv
from io import StringIO
import importlib
import socket
from threading import Event, Thread
from time import monotonic, sleep

import httpx
import uvicorn


ALICE = {"X-Actor-Email": "alice@east.test"}
BOB = {"X-Actor-Email": "bob@west.test"}


def test_export_100k_repeatable_with_live_list(tmp_path, monkeypatch):
    performance = importlib.import_module("backend.scripts.seed_performance")
    db_path = tmp_path / "performance.sqlite3"
    performance.seed_performance(db_path, tenant="East", count=100_000)
    performance.seed_performance(db_path, tenant="West", count=1)
    routes = importlib.import_module("backend.app.certificate_routes")
    original_stream = routes.stream_certificates
    paused = Event()
    resume = Event()
    first_call = True

    def held_stream(*args):
        nonlocal first_call
        stream = original_stream(*args)
        if first_call:
            first_call = False
            yield next(stream)
            paused.set()
            assert resume.wait(timeout=10)
        yield from stream

    monkeypatch.setattr(routes, "stream_certificates", held_stream)
    app = importlib.import_module("backend.app.main").create_app(db_path)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="off"))
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = monotonic() + 10
        while not server.started and monotonic() < deadline:
            sleep(0.02)
        assert server.started
        url = f"http://127.0.0.1:{port}"
        with httpx.Client(timeout=90) as client:
            start = monotonic()
            with client.stream(
                "GET",
                f"{url}/api/certificates/export?search=Perf%20Learner&sort=issued_local_date&direction=desc",
                headers=ALICE,
            ) as response:
                assert response.status_code == 200
                chunks = response.iter_bytes()
                first_chunk = next(chunks)
                assert paused.wait(timeout=10)
                try:
                    bob_list = client.get(f"{url}/api/certificates?page=1&page_size=20", headers=BOB)
                    list_response = client.get(f"{url}/api/certificates?page=1&page_size=20", headers=ALICE)
                finally:
                    resume.set()
                first_export = first_chunk + b"".join(chunks)
            first_seconds = monotonic() - start
            assert bob_list.status_code == 200
            assert [row["serial_number"] for row in bob_list.json()["items"]] == ["PERF-W-000001"]
            assert list_response.status_code == 200
            assert list_response.json()["total"] == 100_000

            start = monotonic()
            second_response = client.get(
                f"{url}/api/certificates/export?search=Perf%20Learner&sort=issued_local_date&direction=desc",
                headers=ALICE,
            )
            second_seconds = monotonic() - start
            print(f"A6 full downloads: first={first_seconds:.3f}s second={second_seconds:.3f}s")
            assert second_response.status_code == 200
            assert first_seconds < 60 and second_seconds < 60
            assert first_export == second_response.content
            rows = list(csv.reader(StringIO(first_export.decode("utf-8"))))
            assert len(rows) == 100_001
            assert rows[0] == ["learner_name", "course_title", "serial_number", "issued_local_date"]
            assert [row[2] for row in rows[1:]] == [f"PERF-E-{i:06d}" for i in range(1, 100_001)]

            subset_url = f"{url}/api/certificates/export?search=Perf%20Learner%200001&sort=issued_local_date&direction=desc"
            subset_first = client.get(subset_url, headers=ALICE)
            subset_second = client.get(subset_url, headers=ALICE)
            assert subset_first.status_code == subset_second.status_code == 200
            assert subset_first.content == subset_second.content
            subset_rows = list(csv.reader(StringIO(subset_first.text)))
            assert [row[2] for row in subset_rows[1:]] == [f"PERF-E-{i:06d}" for i in range(100, 200)]
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
