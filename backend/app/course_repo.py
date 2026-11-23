import sqlite3


def list_courses(conn: sqlite3.Connection, tenant_id: int) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT id, title FROM courses WHERE tenant_id = ? ORDER BY id", (tenant_id,)
    )]


def get_course(conn: sqlite3.Connection, tenant_id: int, course_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, title FROM courses WHERE tenant_id = ? AND id = ?", (tenant_id, course_id)
    ).fetchone()
    return dict(row) if row else None


def list_enrollments(conn: sqlite3.Connection, tenant_id: int, course_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT learners.id AS learner_id, learners.name AS learner_name, enrollments.status, "
        "certificates.id AS active_certificate_id "
        "FROM enrollments JOIN learners ON learners.id = enrollments.learner_id AND learners.tenant_id = enrollments.tenant_id "
        "LEFT JOIN certificates ON certificates.tenant_id = enrollments.tenant_id "
        "AND certificates.course_id = enrollments.course_id AND certificates.learner_id = enrollments.learner_id "
        "AND certificates.status = 'ACTIVE' "
        "WHERE enrollments.tenant_id = ? AND enrollments.course_id = ? ORDER BY learners.id",
        (tenant_id, course_id),
    )
    return [dict(row) for row in rows]


def page_enrollments(conn: sqlite3.Connection, tenant_id: int, course_id: int, page: int, page_size: int) -> dict:
    joins = (
        "FROM enrollments "
        "JOIN learners ON learners.id = enrollments.learner_id AND learners.tenant_id = enrollments.tenant_id "
        "LEFT JOIN certificates ON certificates.tenant_id = enrollments.tenant_id "
        "AND certificates.course_id = enrollments.course_id AND certificates.learner_id = enrollments.learner_id "
        "AND certificates.status = 'ACTIVE' "
        "WHERE enrollments.tenant_id = ? AND enrollments.course_id = ?"
    )
    conn.execute("BEGIN")
    try:
        counts = conn.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(enrollments.status = 'COMPLETED'), 0) AS completed, "
            "COALESCE(SUM(certificates.id IS NOT NULL), 0) AS active_certificates " + joins,
            (tenant_id, course_id),
        ).fetchone()
        offset = (page - 1) * page_size
        rows = [] if offset >= counts["total"] else conn.execute(
            "SELECT learners.id AS learner_id, learners.name AS learner_name, enrollments.status, "
            "certificates.id AS active_certificate_id " + joins +
            " ORDER BY learners.id LIMIT ? OFFSET ?",
            (tenant_id, course_id, page_size, offset),
        ).fetchall()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    total = counts["total"]
    completed = counts["completed"]
    return {
        "items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total,
        "summary": {"completed": completed, "incomplete": total - completed, "active_certificates": counts["active_certificates"]},
    }
