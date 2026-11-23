import sqlite3

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from .actor import ActorContext, get_actor, get_connection
from .contracts import BulkIssueResponse, CoursesResponse, EnrollmentsResponse
from .course_service import bulk_issue_course, courses_for_actor, enrollments_for_course
from .errors import ApiError
from .idempotency import parse_write_body, validate_key


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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    actor: ActorContext = Depends(get_actor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> dict:
    if set(request.query_params) - {"page", "page_size"}:
        raise ApiError(422, "INVALID_REQUEST", "不支持的查询参数")
    return enrollments_for_course(conn, actor, course_id, page, page_size)


@router.post("/{course_id}/bulk-issue", response_model=BulkIssueResponse)
async def bulk_issue(
    course_id: int,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: ActorContext = Depends(get_actor),
) -> JSONResponse:
    _no_query(request)
    key = validate_key(idempotency_key)
    body = parse_write_body(await request.body())
    status, result = await run_in_threadpool(
        bulk_issue_course, request.app.state.db_path, actor, course_id, key, body
    )
    return JSONResponse(status_code=status, content=result)
