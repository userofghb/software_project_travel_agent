from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


def now_utc() -> datetime:
    return utc_now()


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    profile_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    profile_summary: str = ""
    updated_at: datetime = Field(default_factory=now_utc)


class TripPlan(SQLModel, table=True):
    __tablename__ = "trip_plans"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="users.id", index=True)
    title: str
    city: str = Field(index=True)
    start_date: date
    end_date: date
    budget_range: str
    current_version_id: int | None = Field(default=None, foreign_key="trip_plan_versions.id")
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TripPlanVersion(SQLModel, table=True):
    __tablename__ = "trip_plan_versions"

    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="trip_plans.id", index=True)
    parent_version_id: int | None = Field(default=None, foreign_key="trip_plan_versions.id", index=True)
    owner_user_id: int = Field(foreign_key="users.id", index=True)
    version_no: int
    source_type: str
    content_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    change_summary: str = ""
    created_at: datetime = Field(default_factory=now_utc)


class PlanTask(SQLModel, table=True):
    __tablename__ = "plan_tasks"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    plan_id: int | None = Field(default=None, foreign_key="trip_plans.id", index=True)
    task_type: str = Field(default="generate_plan")
    request_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending", index=True)
    progress: int = Field(default=0)
    result_version_id: int | None = Field(default=None, foreign_key="trip_plan_versions.id")
    error_message: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
