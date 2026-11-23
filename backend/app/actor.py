from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterator

from fastapi import APIRouter, Depends, Header, Request

from .contracts import MeResponse
from .db import connect
from .errors import ApiError


@dataclass(frozen=True)
class ActorContext:
    admin_id: int
    tenant_id: int
    email: str
    tenant_name: str
    timezone: str


def resolve_actor(conn: sqlite3.Connection, email: str) -> ActorContext:
    row = conn.execute(
        "SELECT admins.id AS admin_id, admins.tenant_id, admins.email, tenants.name AS tenant_name, tenants.timezone "
        "FROM admins JOIN tenants ON tenants.id = admins.tenant_id WHERE admins.email = ?",
        (email,),
    ).fetchone()
    if row is None:
        raise ApiError(401, "UNKNOWN_ACTOR", "管理员身份无效")
    return ActorContext(row["admin_id"], row["tenant_id"], row["email"], row["tenant_name"], row["timezone"])


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(Path(request.app.state.db_path))
    try:
        yield conn
    finally:
        conn.close()


def get_actor(
    x_actor_email: str | None = Header(default=None, alias="X-Actor-Email"),
    conn: sqlite3.Connection = Depends(get_connection),
) -> ActorContext:
    if not x_actor_email:
        raise ApiError(401, "UNKNOWN_ACTOR", "管理员身份无效")
    return resolve_actor(conn, x_actor_email)


router = APIRouter(prefix="/api")


@router.get("/me", response_model=MeResponse)
def me(request: Request, actor: ActorContext = Depends(get_actor)) -> dict:
    if request.query_params:
        raise ApiError(422, "INVALID_REQUEST", "不支持的查询参数")
    return {
        "admin": {"id": actor.admin_id, "email": actor.email},
        "tenant": {"id": actor.tenant_id, "name": actor.tenant_name, "timezone": actor.timezone},
    }
