import csv
from io import StringIO
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .certificate_repo import FROM_CERTIFICATES, certificate_order, certificate_where
from .db import register_unicode_search


CSV_HEADER = ("learner_name", "course_title", "serial_number", "issued_local_date")
CSV_COLUMNS = (
    "learners.name AS learner_name, courses.title AS course_title, "
    "certificates.serial_number, certificates.issued_local_date"
)


def stream_certificates(path: Path, tenant_id: int, search: str, sort: str, direction: str):
    uri = f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30, check_same_thread=False)
    try:
        register_unicode_search(conn)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        where, params = certificate_where(tenant_id, search)
        cursor = conn.execute(
            f"SELECT {CSV_COLUMNS} {FROM_CERTIFICATES} {where} {certificate_order(sort, direction)}",
            params,
        )
        buffer = StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(CSV_HEADER)
        yield buffer.getvalue()
        while rows := cursor.fetchmany(1000):
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerows(rows)
            yield buffer.getvalue()
        conn.commit()
    finally:
        conn.close()
