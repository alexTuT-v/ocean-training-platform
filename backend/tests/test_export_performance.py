import csv
from io import StringIO
import importlib
import socket
from threading import Thread
from time import monotonic, sleep

import httpx
import uvicorn


ALICE = {"X-Actor-Email": "alice@east.test"}


def test_export_100k_repeatable_with_live_list(tmp_path):
    performance = importlib.import_module("backend.scripts.seed_performance")
    db_path = tmp_path / "performance.sqlite3"
    performance.seed_performance(db_path, tenant="East", count=100_000)
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
                list_response = client.get(f"{url}/api/certificates?page=1&page_size=20", headers=ALICE)
                first_export = first_chunk + b"".join(chunks)
            first_seconds = monotonic() - start
            assert list_response.status_code == 200
            assert list_response.json()["total"] == 100_000

            start = monotonic()
            second_response = client.get(
                f"{url}/api/certificates/export?search=Perf%20Learner&sort=issued_local_date&direction=desc",
                headers=ALICE,
            )
            second_seconds = monotonic() - start
            assert second_response.status_code == 200
            assert first_seconds < 60 and second_seconds < 60
            assert first_export == second_response.content
            rows = list(csv.reader(StringIO(first_export.decode("utf-8"))))
            assert len(rows) == 100_001
            assert rows[0] == ["learner_name", "course_title", "serial_number", "issued_local_date"]
            assert rows[1][2] == "PERF-E-000001"
            assert rows[-1][2] == "PERF-E-100000"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
