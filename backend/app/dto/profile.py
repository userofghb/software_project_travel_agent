from datetime import datetime

from pydantic import BaseModel, Field


class UserProfileBase(BaseModel):
    travel_style: str = "leisure"
    budget_level: str = "medium"
    interest_tags: list[str] = Field(default_factory=list)
    transport_preference: str = "public_transit"
    accommodation_preference: str = "comfort"
    risk_sensitivity: str = "medium"
    pace_preference: str = "balanced"


class UserProfileUpdateRequest(UserProfileBase):
    pass


class UserProfileResponse(BaseModel):
    user_id: int
    profile: UserProfileBase
    profile_summary: str
    updated_at: datetime


class InterestTagsUpdateRequest(BaseModel):
    interest_tags: list[str] = Field(default_factory=list)


class InterestTagsResponse(BaseModel):
    user_id: int
    interest_tags: list[str]
    profile_summary: str
    updated_at: datetime
