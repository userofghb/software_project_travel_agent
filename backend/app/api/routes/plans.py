from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session

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

router = APIRouter()


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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[TripPlanResponse]:
    return PlanService(session).list_plans(current_user)


@router.get("/{plan_id}", response_model=TripPlanResponse)
def get_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripPlanResponse:
    return PlanService(session).get_plan(plan_id, current_user)


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
