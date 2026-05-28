from datetime import date
import copy
import re

from fastapi import BackgroundTasks, HTTPException, status
from sqlmodel import Session

from app.agents.graph import run_planning_graph
from app.agents.state import PlanningState
from app.core.time import utc_now
from app.db.models import PlanTask, TripPlan, TripPlanVersion, User
from app.db.session import get_session
from app.dto.plan import (
    PlanSummaryResponse,
    TripPlanCreateRequest,
    TripPlanEditRequest,
    TripPlanResponse,
    TripPlanVersionResponse,
)
from app.dto.task import PlanTaskCreateResponse
from app.dto.warning import WeatherWarningResponse
from app.repositories.plan_repo import PlanRepository
from app.repositories.profile_repo import ProfileRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.version_repo import VersionRepository
from app.services.weather_service import WeatherService
from app.services.pdf_service import build_plan_pdf_bytes


class PlanService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.plans = PlanRepository(session)
        self.versions = VersionRepository(session)
        self.tasks = TaskRepository(session)
        self.profiles = ProfileRepository(session)

    def create_plan_task(
        self,
        user: User,
        payload: TripPlanCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> PlanTaskCreateResponse:
        task = self.tasks.create(
            PlanTask(
                user_id=user.id,
                task_type="generate_plan",
                request_json={"mode": "create", **payload.model_dump(mode="json")},
            )
        )
        background_tasks.add_task(process_plan_task, task.id)
        return PlanTaskCreateResponse(task_id=task.id, status=task.status)

    def regenerate_plan_task(
        self,
        user: User,
        plan_id: int,
        version_id: int,
        payload: TripPlanCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> PlanTaskCreateResponse:
        plan = self._get_owned_plan(plan_id, user)
        version = self._get_owned_version(version_id, user)
        if version.plan_id != plan.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found for plan")
        task = self.tasks.create(
            PlanTask(
                user_id=user.id,
                plan_id=plan.id,
                task_type="generate_plan",
                request_json={
                    "mode": "regenerate",
                    "parent_version_id": version_id,
                    **payload.model_dump(mode="json"),
                },
            )
        )
        background_tasks.add_task(process_plan_task, task.id)
        return PlanTaskCreateResponse(task_id=task.id, status=task.status)

    def list_plans(self, user: User, search: str | None = None, risk_level: str | None = None) -> list[TripPlanResponse]:
        plans = self.plans.list_by_user_id(user.id, search=search)
        if risk_level not in {"high", "medium", "low", None, "all"}:
            risk_level = None

        if risk_level in {"high", "medium", "low"}:
            filtered: list[TripPlanResponse] = []
            for plan in plans:
                summary = self.get_plan_summary(plan.id, user)
                if summary.risk_level == risk_level:
                    filtered.append(self._build_plan_response(plan))
            return filtered
        return [self._build_plan_response(plan) for plan in plans]

    def get_plan(self, plan_id: int, user: User) -> TripPlanResponse:
        return self._build_plan_response(self._get_owned_plan(plan_id, user))

    def list_versions(self, plan_id: int, user: User) -> list[TripPlanVersionResponse]:
        plan = self._get_owned_plan(plan_id, user)
        return [self._to_version_response(v) for v in self.versions.list_by_plan_id(plan.id)]

    def edit_version(
        self,
        user: User,
        plan_id: int,
        version_id: int,
        payload: TripPlanEditRequest | dict,
    ) -> TripPlanVersionResponse:
        parsed = payload if isinstance(payload, TripPlanEditRequest) else TripPlanEditRequest.model_validate(payload)
        plan = self._get_owned_plan(plan_id, user)
        version = self._get_owned_version(version_id, user)
        latest = self.versions.get_latest_for_plan(plan.id)
        new_version = TripPlanVersion(
            plan_id=plan.id,
            parent_version_id=version.id,
            owner_user_id=user.id,
            version_no=(latest.version_no if latest else 0) + 1,
            source_type="edited",
            content_json=parsed.content,
            change_summary=parsed.change_summary,
        )
        saved = self.versions.create(new_version)
        plan.current_version_id = saved.id
        plan.title = parsed.title or plan.title
        plan.updated_at = utc_now()
        self.plans.save(plan)
        return self._to_version_response(saved)

    def get_current_warnings(self, plan_id: int, user: User) -> WeatherWarningResponse:
        plan = self._get_owned_plan(plan_id, user)
        version = self._require_current_version(plan)
        return self._warnings_for_version(plan.id, version)

    def get_version_warnings(self, plan_id: int, version_id: int, user: User) -> WeatherWarningResponse:
        plan = self._get_owned_plan(plan_id, user)
        version = self._get_owned_version(version_id, user)
        if version.plan_id != plan.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found for plan")
        return self._warnings_for_version(plan.id, version)

    def restore_version(self, user: User, plan_id: int, version_id: int) -> TripPlanVersionResponse:
        plan = self._get_owned_plan(plan_id, user)
        version = self._get_owned_version(version_id, user)
        if version.plan_id != plan.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found for plan")

        latest = self.versions.get_latest_for_plan(plan.id)
        new_version = TripPlanVersion(
            plan_id=plan.id,
            parent_version_id=version.id,
            owner_user_id=user.id,
            version_no=(latest.version_no if latest else 0) + 1,
            source_type="restored",
            content_json=copy.deepcopy(version.content_json),
            change_summary=f"从版本 v{version.version_no} 恢复",
        )
        saved = self.versions.create(new_version)
        plan.current_version_id = saved.id
        restored_title = saved.content_json.get("title")
        if isinstance(restored_title, str) and restored_title.strip():
            plan.title = restored_title.strip()
        restored_origin = saved.content_json.get("origin")
        if isinstance(restored_origin, str):
            plan.origin = restored_origin.strip() or None
        plan.updated_at = utc_now()
        self.plans.save(plan)
        return self._to_version_response(saved)

    def get_plan_summary(self, plan_id: int, user: User) -> PlanSummaryResponse:
        plan = self._get_owned_plan(plan_id, user)
        version = self._require_current_version(plan)
        content = version.content_json if isinstance(version.content_json, dict) else {}
        budget = content.get("budget") if isinstance(content.get("budget"), dict) else {}
        estimated_total = budget.get("estimated_total")
        if not isinstance(estimated_total, int):
            estimated_total = None

        warnings = self._warnings_for_version(plan.id, version).warnings
        warning_count = len(warnings)
        if any(item.level == "high" for item in warnings):
            risk_level = "high"
        elif warning_count > 0:
            risk_level = "medium"
        else:
            risk_level = "low"

        pace = content.get("pace")
        if not isinstance(pace, str) or not pace.strip():
            pace = self._infer_pace(content)

        return PlanSummaryResponse(
            plan_id=plan.id,
            title=plan.title,
            origin=plan.origin,
            city=plan.city,
            start_date=plan.start_date,
            end_date=plan.end_date,
            budget_range=plan.budget_range,
            current_version_id=version.id,
            current_version_no=version.version_no,
            estimated_total=estimated_total,
            risk_level=risk_level,
            pace=pace,
            warning_count=warning_count,
            updated_at=plan.updated_at,
        )

    def export_plan_version_pdf(self, plan_id: int, version_id: int, user: User) -> bytes:
        plan = self._get_owned_plan(plan_id, user)
        version = self._get_owned_version(version_id, user)
        if version.plan_id != plan.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found for plan")
        return build_plan_pdf_bytes(plan=TripPlanResponse.model_validate(plan), version=TripPlanVersionResponse.model_validate(version))

    def _warnings_for_version(self, plan_id: int, version: TripPlanVersion) -> WeatherWarningResponse:
        weather_info = version.content_json.get("weather_info", [])
        return WeatherService.build_warnings(plan_id, version.id, weather_info)

    def _build_plan_response(self, plan: TripPlan) -> TripPlanResponse:
        current_version = self.versions.get_by_id(plan.current_version_id) if plan.current_version_id else None
        return TripPlanResponse(
            id=plan.id,
            owner_user_id=plan.owner_user_id,
            title=plan.title,
            origin=plan.origin,
            city=plan.city,
            start_date=plan.start_date,
            end_date=plan.end_date,
            budget_range=plan.budget_range,
            current_version_id=plan.current_version_id,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            current_version=self._to_version_response(current_version) if current_version else None,
        )

    def _to_version_response(self, version: TripPlanVersion) -> TripPlanVersionResponse:
        response = TripPlanVersionResponse.model_validate(version)
        response.change_summary = self._localize_change_summary(response.change_summary)
        return response

    def _localize_change_summary(self, summary: str) -> str:
        text = (summary or "").strip()
        if not text:
            return text

        lower = text.lower()
        exact_map = {
            "initial chengdu itinerary": "成都初始行程",
            "updated hotel and attractions": "已更新酒店与景点",
            "edited from plan detail": "来自方案详情页的编辑",
            "regenerated by background task": "由后台任务重生成",
            "created by background task": "由后台任务创建",
            "edited manually": "手动编辑",
        }
        if lower in exact_map:
            return exact_map[lower]

        background_match = re.fullmatch(r"(created|regenerated|edited|restored) by background task", lower)
        if background_match:
            source_type = background_match.group(1)
            source_map = {
                "created": "创建",
                "regenerated": "重生成",
                "edited": "编辑",
                "restored": "恢复",
            }
            return f"由后台任务{source_map.get(source_type, source_type)}"

        restored_match = re.fullmatch(r"restored from version\s+(\d+)", lower)
        if restored_match:
            return f"从版本 v{restored_match.group(1)} 恢复"

        return text

    def _require_current_version(self, plan: TripPlan) -> TripPlanVersion:
        if not plan.current_version_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan has no current version")
        version = self.versions.get_by_id(plan.current_version_id)
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current version not found")
        return version

    def _get_owned_plan(self, plan_id: int, user: User) -> TripPlan:
        plan = self.plans.get_by_id(plan_id)
        if not plan or plan.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        return plan

    def _get_owned_version(self, version_id: int, user: User) -> TripPlanVersion:
        version = self.versions.get_by_id(version_id)
        if not version or version.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        return version

    def _infer_pace(self, content: dict) -> str:
        days = content.get("days")
        if not isinstance(days, list) or not days:
            return "relaxed"

        activity_counts = []
        for day in days:
            if not isinstance(day, dict):
                continue
            activities = day.get("activities")
            if isinstance(activities, list):
                activity_counts.append(len(activities))
        if not activity_counts:
            return "relaxed"

        avg = sum(activity_counts) / len(activity_counts)
        if avg >= 5:
            return "intensive"
        if avg >= 4:
            return "balanced"
        return "relaxed"


def process_plan_task(task_id: int) -> None:
    with get_session() as session:
        tasks = TaskRepository(session)
        plans = PlanRepository(session)
        versions = VersionRepository(session)
        profiles = ProfileRepository(session)

        task = tasks.get_by_id(task_id)
        if not task:
            return

        try:
            task.status = "running"
            task.progress = 10
            tasks.save(task)

            payload = dict(task.request_json)
            profile = profiles.get_by_user_id(task.user_id)
            profile_json = profile.profile_json if profile else {}

            state = PlanningState(
                user_id=task.user_id,
                request=payload,
                user_profile=profile_json,
            )
            state = run_planning_graph(state)

            task.progress = 70
            tasks.save(task)

            mode = payload.get("mode", "create")
            start_date = date.fromisoformat(payload["start_date"]) if isinstance(payload["start_date"], str) else payload["start_date"]
            end_date = date.fromisoformat(payload["end_date"]) if isinstance(payload["end_date"], str) else payload["end_date"]
            origin = payload.get("origin")
            if origin:
                state.final_plan["origin"] = origin

            if mode == "create":
                plan = TripPlan(
                    owner_user_id=task.user_id,
                    title=payload["title"],
                    origin=origin,
                    city=payload["city"],
                    start_date=start_date,
                    end_date=end_date,
                    budget_range=payload["budget_range"],
                )
                plan = plans.create(plan)
                parent_version_id = None
                version_no = 1
                source_type = "created"
            else:
                plan = plans.get_by_id(task.plan_id)
                if not plan:
                    raise ValueError("Plan not found during regeneration")
                latest = versions.get_latest_for_plan(plan.id)
                parent_version_id = payload.get("parent_version_id")
                version_no = (latest.version_no if latest else 0) + 1
                source_type = "regenerated"
                plan.title = payload["title"]
                plan.origin = origin
                plan.city = payload["city"]
                plan.start_date = start_date
                plan.end_date = end_date
                plan.budget_range = payload["budget_range"]
                plan.updated_at = utc_now()
                plans.save(plan)

            warning_response = WeatherService.build_warnings(plan.id, 0, state.final_plan["weather_info"])
            state.final_plan["warnings"] = [item.model_dump() for item in warning_response.warnings]

            version = TripPlanVersion(
                plan_id=plan.id,
                parent_version_id=parent_version_id,
                owner_user_id=task.user_id,
                version_no=version_no,
                source_type=source_type,
                content_json=state.final_plan,
                change_summary="由后台任务创建" if source_type == "created" else "由后台任务重生成",
            )
            version = versions.create(version)
            plan.current_version_id = version.id
            plan.updated_at = utc_now()
            plans.save(plan)

            task.plan_id = plan.id
            task.result_version_id = version.id
            task.status = "success"
            task.progress = 100
            task.error_message = None
            tasks.save(task)
        except Exception as exc:
            session.rollback()
            task.status = "failed"
            task.progress = 100
            task.error_message = str(exc)
            tasks.save(task)
