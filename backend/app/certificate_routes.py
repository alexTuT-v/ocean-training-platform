import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from .actor import ActorContext, get_actor, get_connection
from .certificate_service import certificate_detail, certificates_for_actor
from .contracts import CertificateDetail, CertificateListResponse
from .errors import ApiError


router = APIRouter(prefix="/api/certificates")
Sort = Literal["issued_local_date", "learner_name", "course_title", "serial_number"]
Direction = Literal["asc", "desc"]


@router.get("", response_model=CertificateListResponse)
def certificates(
    request: Request,
    search: str = "",
    sort: Sort = "issued_local_date",
    direction: Direction = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    actor: ActorContext = Depends(get_actor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> dict:
    if set(request.query_params) - {"search", "sort", "direction", "page", "page_size"}:
        raise ApiError(422, "INVALID_REQUEST", "不支持的查询参数")
    return certificates_for_actor(conn, actor, search, sort, direction, page, page_size)


@router.get("/{certificate_id}", response_model=CertificateDetail)
def detail(
    certificate_id: int,
    request: Request,
    actor: ActorContext = Depends(get_actor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> dict:
    if request.query_params:
        raise ApiError(422, "INVALID_REQUEST", "不支持的查询参数")
    return certificate_detail(conn, actor, certificate_id)
