import sqlite3

from .actor import ActorContext
from .course_repo import get_course, list_courses, list_enrollments
from .errors import ApiError


def courses_for_actor(conn: sqlite3.Connection, actor: ActorContext) -> dict:
    return {"items": list_courses(conn, actor.tenant_id)}


def enrollments_for_course(conn: sqlite3.Connection, actor: ActorContext, course_id: int) -> dict:
    course = get_course(conn, actor.tenant_id, course_id)
    if course is None:
        raise ApiError(404, "NOT_FOUND", "资源不存在")
    return {"course": course, "items": list_enrollments(conn, actor.tenant_id, course_id)}
