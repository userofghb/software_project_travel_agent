from fastapi import HTTPException, status
from sqlmodel import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.time import utc_now
from app.db.models import User
from app.dto.auth import LoginRequest, RegisterRequest, TokenResponse
from app.repositories.profile_repo import ProfileRepository
from app.repositories.user_repo import UserRepository
from app.services.profile_service import ProfileService


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.profiles = ProfileRepository(session)

    def register(self, payload: RegisterRequest) -> User:
        if self.users.get_by_username(payload.username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
        if self.users.get_by_email(payload.email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            updated_at=utc_now(),
        )
        user = self.users.create(user)

        profile_service = ProfileService(self.session)
        profile_service.get_or_create(user)
        if payload.profile:
            profile_service.update(user, payload.profile)
        return user

    def login(self, payload: LoginRequest) -> TokenResponse | None:
        user = self.users.get_by_username(payload.username)
        if not user or not verify_password(payload.password, user.password_hash):
            return None
        return TokenResponse(access_token=create_access_token(str(user.id)))
