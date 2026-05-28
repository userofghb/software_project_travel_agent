from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class TripPlanCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    origin: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    budget_range: str
    transport_preference: str = "public_transit"
    accommodation_preference: str = "comfort"
    notes: str = ""
    duration: str | None = None  # e.g., "3天"

    @model_validator(mode="after")
    def validate_dates(self) -> "TripPlanCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        return self


class TripPlanEditRequest(BaseModel):
    title: str | None = None
    change_summary: str = "edited manually"
    content: dict[str, Any]


class TripPlanVersionResponse(BaseModel):
    id: int
    plan_id: int
    parent_version_id: int | None
    owner_user_id: int
    version_no: int
    source_type: str
    change_summary: str
    content_json: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class TripPlanResponse(BaseModel):
    id: int
    owner_user_id: int
    title: str
    origin: str | None = None
    city: str
    start_date: date
    end_date: date
    budget_range: str
    current_version_id: int | None
    created_at: datetime
    updated_at: datetime
    current_version: TripPlanVersionResponse | None = None

    model_config = {"from_attributes": True}


class PlanSummaryResponse(BaseModel):
    plan_id: int
    title: str
    origin: str | None = None
    city: str
    start_date: date
    end_date: date
    budget_range: str
    current_version_id: int
    current_version_no: int
    estimated_total: int | None
    risk_level: str
    pace: str
    warning_count: int
    updated_at: datetime
