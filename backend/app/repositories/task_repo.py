from sqlmodel import Session, select

from app.core.time import utc_now
from app.db.models import PlanTask


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, task: PlanTask) -> PlanTask:
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def save(self, task: PlanTask) -> PlanTask:
        task.updated_at = utc_now()
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_by_id(self, task_id: int) -> PlanTask | None:
        return self.session.get(PlanTask, task_id)

    def list_by_user_id(self, user_id: int) -> list[PlanTask]:
        statement = select(PlanTask).where(PlanTask.user_id == user_id).order_by(PlanTask.created_at.desc())
        return list(self.session.exec(statement).all())

    def list_by_plan_id(self, plan_id: int) -> list[PlanTask]:
        statement = select(PlanTask).where(PlanTask.plan_id == plan_id).order_by(PlanTask.created_at.desc())
        return list(self.session.exec(statement).all())

    def delete_for_plan(self, plan_id: int) -> None:
        for task in self.list_by_plan_id(plan_id):
            self.session.delete(task)
