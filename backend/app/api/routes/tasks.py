from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.dto.plan import TripPlanVersionResponse
from app.dto.task import PlanTaskStatusResponse, TaskLogsResponse
from app.services.task_service import TaskService

router = APIRouter()


@router.get("/{task_id}", response_model=PlanTaskStatusResponse)
def get_task_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PlanTaskStatusResponse:
    return TaskService(session).get_status(task_id, current_user)


@router.get("/{task_id}/result", response_model=TripPlanVersionResponse)
def get_task_result(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripPlanVersionResponse:
    return TaskService(session).get_result(task_id, current_user)


@router.get("/{task_id}/logs", response_model=TaskLogsResponse)
def get_task_logs(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TaskLogsResponse:
    return TaskService(session).get_logs(task_id, current_user)
