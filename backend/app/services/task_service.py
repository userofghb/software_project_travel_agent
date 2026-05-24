from fastapi import HTTPException, status
from sqlmodel import Session

from app.db.models import User
from app.dto.plan import TripPlanVersionResponse
from app.dto.task import PlanTaskStatusResponse, TaskLogItem, TaskLogsResponse
from app.repositories.task_repo import TaskRepository
from app.repositories.version_repo import VersionRepository


class TaskService:
    def __init__(self, session: Session) -> None:
        self.tasks = TaskRepository(session)
        self.versions = VersionRepository(session)

    def get_status(self, task_id: int, user: User) -> PlanTaskStatusResponse:
        task = self._get_owned_task(task_id, user)
        return PlanTaskStatusResponse.model_validate(task)

    def get_result(self, task_id: int, user: User) -> TripPlanVersionResponse:
        task = self._get_owned_task(task_id, user)
        if not task.result_version_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result not ready")
        version = self.versions.get_by_id(task.result_version_id)
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result missing")
        return TripPlanVersionResponse.model_validate(version)

    def get_logs(self, task_id: int, user: User) -> TaskLogsResponse:
        task = self._get_owned_task(task_id, user)
        step_defs = [
            ("task_created", "Task created", 0),
            ("queued", "Task queued", 10),
            ("planning", "Planning in progress", 70),
            ("persisting", "Persisting plan and version", 90),
            ("completed", "Task completed", 100),
        ]
        states: list[str] = []
        if task.status == "pending":
            states = ["success", "running", "waiting", "waiting", "waiting"]
        elif task.status == "running":
            if task.progress < 10:
                states = ["success", "running", "waiting", "waiting", "waiting"]
            elif task.progress < 70:
                states = ["success", "success", "running", "waiting", "waiting"]
            elif task.progress < 90:
                states = ["success", "success", "success", "running", "waiting"]
            else:
                states = ["success", "success", "success", "success", "running"]
        elif task.status == "success":
            states = ["success", "success", "success", "success", "success"]
        else:
            states = ["success", "success", "success", "failed", "failed"]

        logs: list[TaskLogItem] = []
        for index, (step, message, progress_point) in enumerate(step_defs):
            status_text = states[index]
            msg = message
            if status_text == "running":
                msg = f"{message}..."
            if status_text == "waiting":
                msg = "Waiting for previous step"
            if task.status == "failed" and index == len(step_defs) - 1 and task.error_message:
                msg = f"Task failed: {task.error_message}"
            timestamp = task.created_at if index <= 1 else task.updated_at
            logs.append(
                TaskLogItem(
                    step=step,
                    status=status_text,
                    message=msg,
                    progress=progress_point,
                    timestamp=timestamp,
                )
            )

        return TaskLogsResponse(
            task_id=task.id,
            status=task.status,
            progress=task.progress,
            logs=logs,
        )

    def _get_owned_task(self, task_id: int, user: User):
        task = self.tasks.get_by_id(task_id)
        if not task or task.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task
