import sqlite3


SORT_COLUMNS = {
    "issued_local_date": "certificates.issued_local_date",
    "learner_name": "learners.name COLLATE NOCASE",
    "course_title": "courses.title COLLATE NOCASE",
    "serial_number": "certificates.serial_number COLLATE NOCASE",
}
FROM_CERTIFICATES = (
    "FROM certificates "
    "JOIN learners ON learners.id = certificates.learner_id AND learners.tenant_id = certificates.tenant_id "
    "JOIN courses ON courses.id = certificates.course_id AND courses.tenant_id = certificates.tenant_id "
)
SUMMARY_COLUMNS = (
    "certificates.id, certificates.serial_number, learners.name AS learner_name, "
    "courses.title AS course_title, certificates.issued_local_date, certificates.status"
)


def certificate_where(tenant_id: int, search: str) -> tuple[str, tuple]:
    if not search:
        return "WHERE certificates.tenant_id = ?", (tenant_id,)
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    term = f"%{escaped}%"
    return (
        "WHERE certificates.tenant_id = ? AND "
        "(learners.name LIKE ? ESCAPE '\\' COLLATE NOCASE OR "
        "certificates.serial_number LIKE ? ESCAPE '\\' COLLATE NOCASE)",
        (tenant_id, term, term),
    )


def certificate_order(sort: str, direction: str) -> str:
    return f"ORDER BY {SORT_COLUMNS[sort]} {direction.upper()}, certificates.id ASC"


def list_certificates(
    conn: sqlite3.Connection,
    tenant_id: int,
    search: str,
    sort: str,
    direction: str,
    page: int,
    page_size: int,
) -> dict:
    where, params = certificate_where(tenant_id, search)
    conn.execute("BEGIN")
    try:
        total = conn.execute(f"SELECT COUNT(*) {FROM_CERTIFICATES} {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {SUMMARY_COLUMNS} {FROM_CERTIFICATES} {where} "
            f"{certificate_order(sort, direction)} LIMIT ? OFFSET ?",
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}


def get_certificate(conn: sqlite3.Connection, tenant_id: int, certificate_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT {SUMMARY_COLUMNS}, certificates.issued_at_utc {FROM_CERTIFICATES} "
        "WHERE certificates.tenant_id = ? AND certificates.id = ?",
        (tenant_id, certificate_id),
    ).fetchone()
    return dict(row) if row else None


def create_certificate(
    conn: sqlite3.Connection,
    tenant_id: int,
    course_id: int,
    learner_id: int,
    serial_number: str,
    issued_at_utc: str,
    issued_local_date: str,
) -> int:
    return conn.execute(
        "INSERT INTO certificates "
        "(tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')",
        (tenant_id, course_id, learner_id, serial_number, issued_at_utc, issued_local_date),
    ).lastrowid
