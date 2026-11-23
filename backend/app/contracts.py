from typing import Literal

from pydantic import BaseModel


class AdminInfo(BaseModel):
    id: int
    email: str


class TenantInfo(BaseModel):
    id: int
    name: str
    timezone: str


class MeResponse(BaseModel):
    admin: AdminInfo
    tenant: TenantInfo


class Course(BaseModel):
    id: int
    title: str


class CoursesResponse(BaseModel):
    items: list[Course]


class Enrollment(BaseModel):
    learner_id: int
    learner_name: str
    status: Literal["COMPLETED", "INCOMPLETE"]
    active_certificate_id: int | None


class EnrollmentsResponse(BaseModel):
    course: Course
    items: list[Enrollment]
