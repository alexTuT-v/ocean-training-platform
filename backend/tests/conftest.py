from pathlib import Path

import pytest

from backend.app.db import initialize_database
from backend.app.seed import seed_demo_data


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    path = tmp_path / "training.sqlite3"
    initialize_database(path)
    seed_demo_data(path)
    return path
