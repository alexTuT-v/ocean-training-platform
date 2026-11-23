from pathlib import Path
from datetime import datetime, timezone

import pytest

from backend.app.db import initialize_database
from backend.app import seed


@pytest.fixture
def seeded_db(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "training.sqlite3"
    initialize_database(path)
    monkeypatch.setattr(seed, "utc_now", lambda: datetime(2026, 1, 10, 13, 30, tzinfo=timezone.utc))
    seed.seed_demo_data(path)
    return path
