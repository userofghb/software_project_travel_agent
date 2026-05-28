from sqlalchemy import or_
from sqlmodel import Session, select

from app.db.models import TripPlan


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, plan: TripPlan) -> TripPlan:
        self.session.add(plan)
        self.session.commit()
        self.session.refresh(plan)
        return plan

    def save(self, plan: TripPlan) -> TripPlan:
        self.session.add(plan)
        self.session.commit()
        self.session.refresh(plan)
        return plan

    def get_by_id(self, plan_id: int) -> TripPlan | None:
        return self.session.get(TripPlan, plan_id)

    def list_by_user_id(self, user_id: int, search: str | None = None) -> list[TripPlan]:
        statement = select(TripPlan).where(TripPlan.owner_user_id == user_id)
        if search:
            statement = statement.where(
                or_(
                    TripPlan.title.contains(search),
                    TripPlan.origin.contains(search),
                    TripPlan.city.contains(search),
                )
            )
        statement = statement.order_by(TripPlan.updated_at.desc())
        return list(self.session.exec(statement).all())
