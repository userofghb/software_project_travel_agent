from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.dto.profile import UserProfileUpdateRequest


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    profile: UserProfileUpdateRequest | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AccountUpdateRequest(BaseModel):
    email: EmailStr | None = None
    current_password: str | None = Field(default=None, min_length=6, max_length=128)
    new_password: str | None = Field(default=None, min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
