from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from .actor import ActorContext
from .audit_repo import record_event
from .certificate_repo import create_certificate
from .course_repo import get_course, list_courses, list_enrollments, page_enrollments
from .dates import to_local
from .db import connect
from .errors import ApiError
from .idempotency import execute_write, fingerprint


def courses_for_actor(conn: sqlite3.Connection, actor: ActorContext) -> dict:
    return {"items": list_courses(conn, actor.tenant_id)}


def enrollments_for_course(conn: sqlite3.Connection, actor: ActorContext, course_id: int, page: int, page_size: int) -> dict:
    course = get_course(conn, actor.tenant_id, course_id)
    if course is None:
        raise ApiError(404, "NOT_FOUND", "资源不存在")
    return {"course": course, **page_enrollments(conn, actor.tenant_id, course_id, page, page_size)}


def bulk_issue_course(path: Path, actor: ActorContext, course_id: int, key: str, body: dict) -> tuple[int, dict]:
    conn = connect(path)
    try:
        request_fingerprint = fingerprint("POST", "/api/courses/{course_id}/bulk-issue", course_id, body)
        selected_enrollments: list[dict] = []

        def validate_new_request() -> None:
            nonlocal selected_enrollments
            if set(body) != {"learner_ids"} or not isinstance(body["learner_ids"], list) or not body["learner_ids"]:
                raise ApiError(422, "INVALID_REQUEST", "请选择至少一名学员")
            learner_ids = body["learner_ids"]
            if any(type(learner_id) is not int or not 1 <= learner_id <= 2**63 - 1 for learner_id in learner_ids) or len(set(learner_ids)) != len(learner_ids):
                raise ApiError(422, "INVALID_REQUEST", "学员 ID 无效或重复")
            if get_course(conn, actor.tenant_id, course_id) is None:
                raise ApiError(404, "NOT_FOUND", "资源不存在")
            selected_enrollments = list_enrollments(conn, actor.tenant_id, course_id, learner_ids)
            if len(selected_enrollments) != len(learner_ids):
                raise ApiError(422, "INVALID_REQUEST", "所选学员不属于当前课程")

        def perform(record_id: int) -> tuple[int, dict]:
            outcomes = []
            for enrollment in selected_enrollments:
                common = {
                    "learner_id": enrollment["learner_id"],
                    "learner_name": enrollment["learner_name"],
                    "certificate_id": None,
                    "serial_number": None,
                }
                if enrollment["status"] != "COMPLETED":
                    outcomes.append({**common, "result": "skipped", "reason": "课程未完成"})
                    continue
                if enrollment["active_certificate_id"] is not None:
                    outcomes.append({**common, "result": "skipped", "reason": "已有有效证书"})
                    continue

                issued_at = datetime.now(timezone.utc)
                issued_text = issued_at.isoformat(timespec="seconds").replace("+00:00", "Z")
                local_date, _ = to_local(issued_at, actor.timezone)
                serial = f"CERT-{uuid4().hex.upper()}"
                conn.execute("SAVEPOINT learner_issue")
                try:
                    certificate_id = create_certificate(
                        conn, actor.tenant_id, course_id, enrollment["learner_id"], serial, issued_text, local_date
                    )
                    record_event(conn, actor.tenant_id, certificate_id, actor.admin_id, "ISSUED", issued_text, record_id)
                except sqlite3.IntegrityError:
                    conn.execute("ROLLBACK TO SAVEPOINT learner_issue")
                    conn.execute("RELEASE SAVEPOINT learner_issue")
                    outcomes.append({**common, "result": "failed", "reason": "证书颁发失败"})
                else:
                    conn.execute("RELEASE SAVEPOINT learner_issue")
                    outcomes.append({**common, "result": "issued", "reason": None, "certificate_id": certificate_id, "serial_number": serial})

            summary = {name: sum(row["result"] == name for row in outcomes) for name in ("issued", "skipped", "failed")}
            return 200, {"operation_id": record_id, "status": "COMPLETED", "summary": summary, "outcomes": outcomes}

        return execute_write(conn, actor, key, request_fingerprint, "BULK_ISSUE", validate_new_request, perform)
    finally:
        conn.close()
