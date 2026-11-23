from pathlib import Path
import sqlite3


SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def initialize_database(path: Path) -> None:
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    finally:
        conn.close()
