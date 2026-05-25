from sqlmodel import Session

from app.core.time import utc_now
from app.db.models import User, UserProfile
from app.dto.profile import (
    InterestTagsResponse,
    InterestTagsUpdateRequest,
    UserProfileBase,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.repositories.profile_repo import ProfileRepository


TRAVEL_STYLE_LABELS = {
    "leisure": "轻松休闲",
    "relaxed":"休闲放松",
    "adventure": "探索冒险",
    "culture": "人文体验",
    "family": "亲子出行",
    "foodie": "美食优先",
    "shopping": "购物打卡",
}

BUDGET_LEVEL_LABELS = {
    "low": "偏节省",
    "medium": "适中",
    "high": "偏宽裕",
}

TRANSPORT_LABELS = {
    "public_transit": "公共交通优先",
    "walk_or_nearby": "公共交通 + 步行",
    "mixed_walk": "步行友好",
    "private_transport": "私密交通优先",
}

ACCOMMODATION_LABELS = {
    "comfort": "舒适型住宿",
    "homestay": "特色民宿",
    "hotel_with_breakfast": "酒店含早",
    "homestay_with_breakfast": "民宿含早",
}

PACE_LABELS = {
    "relaxed": "轻松",
    "balanced": "适中",
    "intensive": "紧凑",
}

RISK_LABELS = {
    "low": "低",
    "medium": "中",
    "high": "高",
}


def _to_zh(value: str, mapping: dict[str, str]) -> str:
    key = (value or "").strip().lower()
    if key in mapping:
        return mapping[key]
    return value or "-"


def build_profile_summary(profile: UserProfileBase) -> str:
    tags = "、".join(profile.interest_tags) if profile.interest_tags else "暂无"
    travel_style = _to_zh(profile.travel_style, TRAVEL_STYLE_LABELS)
    budget_level = _to_zh(profile.budget_level, BUDGET_LEVEL_LABELS)
    transport = _to_zh(profile.transport_preference, TRANSPORT_LABELS)
    accommodation = _to_zh(profile.accommodation_preference, ACCOMMODATION_LABELS)
    pace = _to_zh(profile.pace_preference, PACE_LABELS)
    risk = _to_zh(profile.risk_sensitivity, RISK_LABELS)
    return (
        f"旅行风格：{travel_style}；预算：{budget_level}；兴趣标签：{tags}；"
        f"交通偏好：{transport}；住宿偏好：{accommodation}；"
        f"行程节奏：{pace}；天气敏感度：{risk}。"
    )


class ProfileService:
    def __init__(self, session: Session) -> None:
        self.repo = ProfileRepository(session)

    def get_or_create(self, user: User) -> UserProfileResponse:
        existing = self.repo.get_by_user_id(user.id)
        if not existing:
            default_profile = UserProfileBase()
            existing = self.repo.save(
                UserProfile(
                    user_id=user.id,
                    profile_json=default_profile.model_dump(),
                    profile_summary=build_profile_summary(default_profile),
                    updated_at=utc_now(),
                )
            )
        profile_obj = UserProfileBase(**existing.profile_json)
        summary = build_profile_summary(profile_obj)
        return UserProfileResponse(
            user_id=user.id,
            profile=profile_obj,
            profile_summary=summary,
            updated_at=existing.updated_at,
        )

    def update(self, user: User, payload: UserProfileUpdateRequest) -> UserProfileResponse:
        existing = self.repo.get_by_user_id(user.id)
        if not existing:
            existing = UserProfile(user_id=user.id)
        existing.profile_json = payload.model_dump()
        existing.profile_summary = build_profile_summary(UserProfileBase(**existing.profile_json))
        existing.updated_at = utc_now()
        saved = self.repo.save(existing)
        return UserProfileResponse(
            user_id=user.id,
            profile=UserProfileBase(**saved.profile_json),
            profile_summary=saved.profile_summary,
            updated_at=saved.updated_at,
        )

    def get_interest_tags(self, user: User) -> InterestTagsResponse:
        profile = self.get_or_create(user)
        return InterestTagsResponse(
            user_id=profile.user_id,
            interest_tags=profile.profile.interest_tags,
            profile_summary=profile.profile_summary,
            updated_at=profile.updated_at,
        )

    def update_interest_tags(self, user: User, payload: InterestTagsUpdateRequest) -> InterestTagsResponse:
        existing = self.repo.get_by_user_id(user.id)
        if not existing:
            profile = UserProfileBase(interest_tags=payload.interest_tags)
        else:
            current = UserProfileBase(**existing.profile_json)
            profile = current.model_copy(update={"interest_tags": payload.interest_tags})

        updated = self.update(user, UserProfileUpdateRequest(**profile.model_dump()))
        return InterestTagsResponse(
            user_id=updated.user_id,
            interest_tags=updated.profile.interest_tags,
            profile_summary=updated.profile_summary,
            updated_at=updated.updated_at,
        )
