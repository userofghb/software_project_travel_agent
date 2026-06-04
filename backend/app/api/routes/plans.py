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


class ParseRequest(BaseModel):
    text: str


@router.post("/parse", response_model=TripPlanCreateRequest)
def parse_plan_text(payload: ParseRequest) -> TripPlanCreateRequest:
    """Parse a freeform text input and return a TripPlanCreateRequest.

    Simple heuristics to extract origin, destination, dates, days and budget.
    If no explicit start date is found, default to today.
    """
    text = (payload.text or "").strip()

    def extract_origin(t: str) -> str | None:
        m = re.search(r"从([\u4e00-\u9fa5A-Za-z0-9]{2,10})到([\u4e00-\u9fa5A-Za-z0-9]{2,10})", t)
        if m:
            return m.group(1)
        m = re.search(r"(?:从|自)([\u4e00-\u9fa5A-Za-z0-9]{2,10})(?:出发|启程|前往)", t)
        if m:
            return m.group(1)
        m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,10})出发(?:去|到)?", t)
        return m.group(1) if m else None

    def extract_city(t: str, origin: str | None) -> str:
        m = re.search(r"(?:去|到)([\u4e00-\u9fa5A-Za-z0-9]{2,10})(?:玩|旅行|旅游|游|出差|，|,|\s|$)", t)
        if m:
            return m.group(1)
        known = ['北京','上海','广州','深圳','成都','重庆','杭州','南京','苏州','西安','武汉','长沙','厦门','青岛','大理','桂林','三亚']
        for c in known:
            if c in t and c != origin:
                return c
        for c in known:
            if c in t:
                return c
        return '成都'

    def extract_days(t: str) -> int:
        # First try more specific patterns for duration (not date)
        # Match patterns like "去X天", "玩X天", "X天的行程", "X天游", "X日游", "X日游玩"
        m = re.search(r"(?:去|玩|行程|游|游玩)(\d+)\s*[日天]", t)
        if m:
            return max(1, min(10, int(m.group(1))))

        # Match patterns like "X天" or "X日" but NOT "X月X日" (date)
        # Use negative lookbehind to exclude date patterns like "6月1日"
        m = re.search(r'(?<!月)(\d+)\s*[日天](?!出发|去|玩)', t)
        if m:
            return max(1, min(10, int(m.group(1))))

        # Try Chinese numerals with duration context
        cn_map = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7}
        m = re.search(r"(?:去|玩|行程|游)([一二两三四五六七])\s*[日天]", t)
        if m:
            return cn_map.get(m.group(1), 3)

        # Fallback: try any Chinese numeral followed by 日天 (but not in date context)
        m = re.search(r'(?<!月)([一二两三四五六七])\s*[日天]', t)
        return cn_map.get(m.group(1), 3) if m else 3

    def extract_start_date(t: str):
        m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
        if m:
            y,mo,d = map(int, m.groups())
            try:
                return date(y,mo,d)
            except Exception:
                pass
        m = re.search(r"(\d{1,2})月(\d{1,2})日", t)
        if m:
            mo,d = map(int, m.groups())
            y = date.today().year
            try:
                return date(y,mo,d)
            except Exception:
                pass
        return date.today()

    def extract_budget(t: str) -> str:
        m = re.search(r"预算\s*(\d+)", t)
        if m:
            amt = int(m.group(1))
            if amt <= 2000:
                return 'low'
            if amt >= 6000:
                return 'high'
            return 'medium'
        if '高端' in t or '品质' in t:
            return 'high'
        if '省钱' in t or '经济' in t:
            return 'low'
        return 'medium'

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
        'transport_preference': 'public_transit',
        'accommodation_preference': 'comfort',
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
