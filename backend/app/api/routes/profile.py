from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.dto.profile import (
    InterestTagsResponse,
    InterestTagsUpdateRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserProfileResponse:
    return ProfileService(session).get_or_create(current_user)


@router.put("/me", response_model=UserProfileResponse)
def update_my_profile(
    payload: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserProfileResponse:
    return ProfileService(session).update(current_user, payload)


@router.get("/me/interests", response_model=InterestTagsResponse)
def get_my_interest_tags(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> InterestTagsResponse:
    return ProfileService(session).get_interest_tags(current_user)


@router.put("/me/interests", response_model=InterestTagsResponse)
def update_my_interest_tags(
    payload: InterestTagsUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> InterestTagsResponse:
    return ProfileService(session).update_interest_tags(current_user, payload)
