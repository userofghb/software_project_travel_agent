from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlmodel import Session
from pydantic import BaseModel
import re
from datetime import date, timedelta

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.dto.plan import (
    PlanSummaryResponse,
    TripPlanCreateRequest,
    TripPlanEditRequest,
    TripPlanResponse,
    TripPlanVersionResponse,
)
from app.dto.task import PlanTaskCreateResponse
from app.dto.warning import WeatherWarningResponse
from app.services.plan_service import PlanService
from fastapi.responses import StreamingResponse
from io import BytesIO

router = APIRouter()


UNSPECIFIED_CITY = "目的地待确认"
KNOWN_CITIES = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "成都",
    "重庆",
    "杭州",
    "南京",
    "苏州",
    "西安",
    "武汉",
    "长沙",
    "厦门",
    "青岛",
    "大理",
    "桂林",
    "三亚",
    "天津",
    "香港",
    "澳门",
    "台北",
    "昆明",
    "丽江",
    "拉萨",
    "哈尔滨",
    "沈阳",
    "郑州",
    "合肥",
    "宁波",
    "无锡",
    "乌鲁木齐",
)
PLACE_PATTERN = r"[\u4e00-\u9fa5A-Za-z0-9]{2,20}?"
PLACE_END_PATTERN = r"(?=玩|旅行|旅游|游|出差|自由行|[一二两三四五六七八九十\d]+\s*[日天]|预算|，|,|。|\.|\s|$)"
CN_NUMBER_MAP = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


class ParseRequest(BaseModel):
    text: str


@router.post("/parse", response_model=TripPlanCreateRequest)
def parse_plan_text(payload: ParseRequest) -> TripPlanCreateRequest:
    """Parse a freeform text input and return a TripPlanCreateRequest.

    Simple heuristics to extract origin, destination, dates, days and budget.
    If no explicit start date is found, default to today.
    """
    text = re.sub(r"\s+", " ", (payload.text or "").strip())

    def clean_place(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip(" ，,。.!！?？、")
        cleaned = re.sub(r"^(我想|想|计划|打算|准备|一家人|一家三口|和朋友|周末|五一|国庆|春节)", "", cleaned)
        cleaned = re.sub(r"(出发|启程|前往|旅游|旅行|游玩|自由行|游)$", "", cleaned)
        return cleaned or None

    def route_match(t: str) -> tuple[str | None, str | None]:
        patterns = [
            rf"(?:从|自)(?P<origin>{PLACE_PATTERN})(?:出发|启程)?(?:去|到|前往)(?P<city>{PLACE_PATTERN}){PLACE_END_PATTERN}",
            rf"(?P<origin>{PLACE_PATTERN})(?:出发|启程)(?:去|到|前往)(?P<city>{PLACE_PATTERN}){PLACE_END_PATTERN}",
            rf"(?P<origin>{PLACE_PATTERN})(?:去|到|前往)(?P<city>{PLACE_PATTERN}){PLACE_END_PATTERN}",
        ]
        for pattern in patterns:
            match = re.search(pattern, t)
            if match:
                return clean_place(match.group("origin")), clean_place(match.group("city"))
        return None, None

    def extract_origin(t: str) -> str | None:
        origin, _ = route_match(t)
        if origin:
            return origin
        match = re.search(rf"(?:从|自)?(?P<origin>{PLACE_PATTERN})(?:出发|启程)", t)
        return clean_place(match.group("origin")) if match else None

    def extract_city(t: str, origin: str | None) -> str:
        _, route_city = route_match(t)
        if route_city and route_city != origin:
            return route_city

        mentioned = sorted(
            ((t.find(city), city) for city in KNOWN_CITIES if city in t),
            key=lambda item: item[0],
        )
        for _, city in mentioned:
            if city != origin:
                return city
        if mentioned:
            return mentioned[0][1]

        patterns = [
            rf"(?:去|到|前往)(?P<city>{PLACE_PATTERN}){PLACE_END_PATTERN}",
            rf"(?P<city>{PLACE_PATTERN})(?:[一二两三四五六七八九十\d]+\s*[日天](?:游|行程|旅行|旅游)?|周末(?:游|旅行|旅游)?|自由行|亲子游|美食游|深度游)",
        ]
        for pattern in patterns:
            match = re.search(pattern, t)
            city = clean_place(match.group("city")) if match else None
            if city and city != origin:
                return city
        return UNSPECIFIED_CITY

    def parse_count(raw: str) -> int | None:
        if raw.isdigit():
            return int(raw)
        if raw == "十":
            return 10
        if "十" in raw:
            left, _, right = raw.partition("十")
            tens = CN_NUMBER_MAP.get(left, 1 if not left else 0)
            ones = CN_NUMBER_MAP.get(right, 0) if right else 0
            value = tens * 10 + ones
            return value or None
        return CN_NUMBER_MAP.get(raw)

    def clamp_days(value: int | None) -> int:
        return max(1, min(10, value or 3))

    def extract_days(t: str) -> int:
        range_match = re.search(
            r"(?:(\d{4})[/-])?(\d{1,2})月?(\d{1,2})[日号]?\s*(?:到|至|-|~|—)\s*(?:(\d{1,2})月)?(\d{1,2})[日号]?",
            t,
        )
        if range_match:
            year_text, start_month, start_day, end_month, end_day = range_match.groups()
            year = int(year_text) if year_text else date.today().year
            start_month_int = int(start_month)
            end_month_int = int(end_month or start_month)
            try:
                start_value = date(year, start_month_int, int(start_day))
                end_value = date(year, end_month_int, int(end_day))
                if end_value >= start_value:
                    return clamp_days((end_value - start_value).days + 1)
            except ValueError:
                pass

        for pattern in (
            r"(?<![月/\-.])(\d{1,2})\s*[日天](?:游|行程|旅行|旅游|游玩)?",
            r"(?<!月)([一二两三四五六七八九十]{1,3})\s*[日天](?:游|行程|旅行|旅游|游玩)?",
        ):
            match = re.search(pattern, t)
            if match:
                return clamp_days(parse_count(match.group(1)))
        if "周末" in t:
            return 2
        return 3

    def date_from_month_day(month: int, day: int) -> date | None:
        today = date.today()
        try:
            candidate = date(today.year, month, day)
            if candidate < today:
                candidate = date(today.year + 1, month, day)
            return candidate
        except ValueError:
            return None

    def extract_start_date(t: str) -> date:
        match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", t)
        if match:
            year, month, day = map(int, match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                pass
        match = re.search(r"(\d{1,2})月(\d{1,2})[日号]", t)
        if match:
            parsed = date_from_month_day(int(match.group(1)), int(match.group(2)))
            if parsed:
                return parsed
        if "明天" in t:
            return date.today() + timedelta(days=1)
        if "后天" in t:
            return date.today() + timedelta(days=2)
        if "五一" in t:
            parsed = date_from_month_day(5, 1)
            if parsed:
                return parsed
        if "国庆" in t:
            parsed = date_from_month_day(10, 1)
            if parsed:
                return parsed
        if "周末" in t:
            today = date.today()
            days_until_saturday = (5 - today.weekday()) % 7
            return today + timedelta(days=days_until_saturday)
        return date.today()

    def parse_budget_amount(value: str, unit: str | None) -> int:
        amount = float(value)
        unit_text = (unit or "").lower()
        if unit_text in {"万", "w"}:
            amount *= 10000
        elif unit_text in {"千", "k"}:
            amount *= 1000
        return int(amount)

    def extract_budget(t: str) -> str:
        patterns = [
            r"(?:预算|费用|花费|人均|控制在|不超过|以内|大概|约)[^\d]*(\d+(?:\.\d+)?)\s*(万|w|千|k|元|块)?",
            r"(\d+(?:\.\d+)?)\s*(万|w|千|k|元|块)?\s*(?:预算|以内|左右|上下)",
        ]
        for pattern in patterns:
            match = re.search(pattern, t, flags=re.IGNORECASE)
            if not match:
                continue
            amount = parse_budget_amount(match.group(1), match.group(2))
            if amount <= 2500:
                return "low"
            if amount >= 6000:
                return "high"
            return "medium"
        if any(keyword in t for keyword in ("高端", "品质", "豪华", "舒服一点")):
            return "high"
        if any(keyword in t for keyword in ("省钱", "经济", "低预算", "穷游", "实惠")):
            return "low"
        return "medium"

    def extract_transport(t: str) -> str:
        if any(keyword in t for keyword in ("少走路", "少步行", "不要走太多", "不想走太多", "少折腾")):
            return "private_transport"
        if any(keyword in t for keyword in ("打车", "出租", "网约车", "包车", "自驾")):
            return "private_transport"
        if any(keyword in t for keyword in ("步行", "少坐车")):
            return "walking"
        return "public_transit"

    def extract_accommodation(t: str, budget: str) -> str:
        if any(keyword in t for keyword in ("含早", "早餐", "酒店早餐")):
            return "hotel_with_breakfast"
        if any(keyword in t for keyword in ("民宿", "客栈")):
            return "homestay"
        if budget == "high" or any(keyword in t for keyword in ("高端", "豪华", "品质酒店")):
            return "luxury"
        if budget == "low" or any(keyword in t for keyword in ("经济型", "省钱")):
            return "budget"
        return "comfort"

    origin = extract_origin(text)
    city = extract_city(text, origin)
    days = extract_days(text)
    start = extract_start_date(text)
    end = start + timedelta(days=days-1)
    budget = extract_budget(text)

    payload_dict = {
        'title': f"{city}{days}日旅行方案",
        'origin': origin,
        'city': city,
        'start_date': start,
        'end_date': end,
        'budget_range': budget,
        'transport_preference': extract_transport(text),
        'accommodation_preference': extract_accommodation(text, budget),
        'notes': text,
        'duration': f"{days}天",
    }
    return TripPlanCreateRequest.model_validate(payload_dict)


@router.post("", response_model=PlanTaskCreateResponse)
def create_plan_task(
    payload: TripPlanCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PlanTaskCreateResponse:
    return PlanService(session).create_plan_task(current_user, payload, background_tasks)


@router.get("", response_model=list[TripPlanResponse])
def list_plans(
    search: str | None = None,
    risk_level: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[TripPlanResponse]:
    return PlanService(session).list_plans(current_user, search=search, risk_level=risk_level)


@router.get("/{plan_id}", response_model=TripPlanResponse)
def get_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripPlanResponse:
    return PlanService(session).get_plan(plan_id, current_user)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    PlanService(session).delete_plan(plan_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{plan_id}/summary", response_model=PlanSummaryResponse)
def get_plan_summary(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PlanSummaryResponse:
    return PlanService(session).get_plan_summary(plan_id, current_user)


@router.get("/{plan_id}/versions", response_model=list[TripPlanVersionResponse])
def list_plan_versions(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[TripPlanVersionResponse]:
    return PlanService(session).list_versions(plan_id, current_user)


@router.post("/{plan_id}/versions/{version_id}/regenerate", response_model=PlanTaskCreateResponse)
def regenerate_plan(
    plan_id: int,
    version_id: int,
    payload: TripPlanCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PlanTaskCreateResponse:
    return PlanService(session).regenerate_plan_task(
        current_user,
        plan_id,
        version_id,
        payload,
        background_tasks,
    )


@router.put("/{plan_id}/versions/{version_id}", response_model=TripPlanVersionResponse)
def edit_plan_version(
    plan_id: int,
    version_id: int,
    payload: TripPlanEditRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripPlanVersionResponse:
    return PlanService(session).edit_version(current_user, plan_id, version_id, payload)


@router.post("/{plan_id}/versions/{version_id}/restore", response_model=TripPlanVersionResponse)
def restore_plan_version(
    plan_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripPlanVersionResponse:
    return PlanService(session).restore_version(current_user, plan_id, version_id)


@router.get("/{plan_id}/versions/{version_id}/export")
def export_plan_version_pdf(
    plan_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    pdf_bytes = PlanService(session).export_plan_version_pdf(plan_id, version_id, current_user)
    buffer = BytesIO(pdf_bytes)
    headers = {
        "Content-Disposition": f"attachment; filename=plan-{plan_id}-v{version_id}.pdf"
    }
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)


@router.get("/{plan_id}/warnings", response_model=WeatherWarningResponse)
def get_plan_warnings(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> WeatherWarningResponse:
    return PlanService(session).get_current_warnings(plan_id, current_user)


@router.get("/{plan_id}/versions/{version_id}/warnings", response_model=WeatherWarningResponse)
def get_version_warnings(
    plan_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> WeatherWarningResponse:
    return PlanService(session).get_version_warnings(plan_id, version_id, current_user)
