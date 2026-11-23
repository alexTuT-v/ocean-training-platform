import sqlite3

from fastapi import APIRouter, Depends, Request

from .actor import ActorContext, get_actor, get_connection
from .contracts import CoursesResponse, EnrollmentsResponse
from .course_service import courses_for_actor, enrollments_for_course
from .errors import ApiError


router = APIRouter(prefix="/api/courses")


def _no_query(request: Request) -> None:
    if request.query_params:
        raise ApiError(422, "INVALID_REQUEST", "不支持的查询参数")


@router.get("", response_model=CoursesResponse)
def courses(request: Request, actor: ActorContext = Depends(get_actor), conn: sqlite3.Connection = Depends(get_connection)) -> dict:
    _no_query(request)
    return courses_for_actor(conn, actor)


@router.get("/{course_id}/enrollments", response_model=EnrollmentsResponse)
def enrollments(
    course_id: int,
    request: Request,
    actor: ActorContext = Depends(get_actor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> dict:
    _no_query(request)
    return enrollments_for_course(conn, actor, course_id)
