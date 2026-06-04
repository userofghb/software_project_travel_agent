from sqlmodel import Session, select

from app.db.models import TripPlanVersion


class VersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, version: TripPlanVersion) -> TripPlanVersion:
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)
        return version

    def get_by_id(self, version_id: int) -> TripPlanVersion | None:
        return self.session.get(TripPlanVersion, version_id)

    def list_by_plan_id(self, plan_id: int) -> list[TripPlanVersion]:
        statement = select(TripPlanVersion).where(TripPlanVersion.plan_id == plan_id).order_by(TripPlanVersion.version_no.asc())
        return list(self.session.exec(statement).all())

    def delete_for_plan(self, plan_id: int) -> None:
        for version in reversed(self.list_by_plan_id(plan_id)):
            self.session.delete(version)

    def get_latest_for_plan(self, plan_id: int) -> TripPlanVersion | None:
        statement = (
            select(TripPlanVersion)
            .where(TripPlanVersion.plan_id == plan_id)
            .order_by(TripPlanVersion.version_no.desc())
        )
        return self.session.exec(statement).first()
