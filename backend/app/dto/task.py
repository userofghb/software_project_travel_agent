from datetime import datetime

from pydantic import BaseModel


class PlanTaskCreateResponse(BaseModel):
    task_id: int
    status: str


class PlanTaskStatusResponse(BaseModel):
    id: int
    plan_id: int | None
    status: str
    progress: int
    result_version_id: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskLogItem(BaseModel):
    step: str
    status: str
    message: str
    progress: int
    timestamp: datetime


class TaskLogsResponse(BaseModel):
    task_id: int
    status: str
    progress: int
    logs: list[TaskLogItem]
