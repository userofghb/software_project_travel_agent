from __future__ import annotations

import argparse
import copy
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.db import session as db_session
from app.db.session import get_engine
from app.main import create_app
from app.services.providers import (
    get_attraction_provider,
    get_hotel_provider,
    get_planner_provider,
    get_route_provider,
    get_weather_provider,
)


CITY = "\u4e0a\u6d77"
PASSWORD = "secret123"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    required: bool = True


class FullIntegrationRunner:
    def __init__(self, *, strict_external: bool = False) -> None:
        self.strict_external = strict_external
        self.checks: list[Check] = []
        self.suffix = int(time.time())
        self.alice = f"it_fullsuite_alice_{self.suffix}"
        self.bob = f"it_fullsuite_bob_{self.suffix}"

    def record(self, name: str, ok: bool, detail: str = "", *, required: bool = True) -> None:
        status = "PASS" if ok else ("FAIL" if required else "WARN")
        print(f"{status} {name} {detail}".rstrip())
        self.checks.append(Check(name=name, ok=ok, detail=detail, required=required))

    def assert_status(self, name: str, response: Any, expected: int | set[int]) -> None:
        ok = response.status_code == expected if isinstance(expected, int) else response.status_code in expected
        detail = f"status={response.status_code} expected={expected}"
        self.record(name, ok, detail)
        if not ok:
            raise AssertionError(f"{name}: {detail}; body={response.text[:500]}")

    def external(
        self,
        name: str,
        fn: Callable[[], Any],
        predicate: Callable[[Any], bool] = bool,
        detail: Callable[[Any], str] = lambda value: str(value)[:120],
    ) -> Any | None:
        required = self.strict_external
        try:
            value = fn()
            ok = predicate(value)
            self.record(name, ok, detail(value), required=required)
            if required and not ok:
                raise AssertionError(name)
            return value
        except Exception as exc:
            self.record(name, False, f"{type(exc).__name__}: {str(exc)[:180]}", required=required)
            if required:
                raise
            return None

    def run(self) -> None:
        get_settings.cache_clear()
        db_session._engine = None

        settings = get_settings()
        self.record(
            "config.real_database_url_present",
            settings.database_url.startswith("mysql"),
            settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url[:30],
        )
        self.record("config.openai_key_present", bool(settings.openai_api_key))
        self.record("config.amap_key_present", bool(settings.amap_api_key))
        self.record(
            "provider.planner_is_openai",
            type(get_planner_provider()).__name__ == "OpenAIPlannerProvider",
            type(get_planner_provider()).__name__,
        )

        engine = get_engine()
        with engine.connect() as conn:
            self.record("mysql.select_1", conn.execute(text("SELECT 1")).scalar() == 1)

        attractions = self.external(
            "amap.attraction_search",
            lambda: get_attraction_provider().search(CITY, ["history", "food"]),
            lambda value: isinstance(value, list) and len(value) > 0,
            lambda value: f"count={len(value)} first={value[0].get('name') if value else None}",
        )
        hotel = self.external(
            "amap.hotel_search",
            lambda: get_hotel_provider().search(CITY, "medium", "comfort"),
            lambda value: isinstance(value, dict) and bool(value.get("name")),
            lambda value: f"name={value.get('name')}",
        )
        weather = self.external(
            "amap.weather_forecast",
            lambda: get_weather_provider().forecast(date(2026, 6, 10), date(2026, 6, 10), CITY),
            lambda value: isinstance(value, list) and len(value) == 1,
            lambda value: f"count={len(value)} first={value[0] if value else None}",
        )

        if attractions and hotel:
            self.external(
                "amap.route_build",
                lambda: get_route_provider().build_routes(
                    days=[
                        {
                            "date": "2026-06-10",
                            "activities": [
                                {
                                    "title": attractions[0].get("name"),
                                    "poi_id": attractions[0].get("id"),
                                    "location": attractions[0].get("location"),
                                }
                            ],
                        }
                    ],
                    hotel=hotel,
                    attractions=attractions[:1],
                    transport_preference="public_transit",
                    city=CITY,
                ),
                lambda value: isinstance(value, dict) and "points" in value and "routes" in value,
                lambda value: f"points={len(value.get('points', []))} routes={len(value.get('routes', []))}",
            )
        else:
            self.record("amap.route_build", False, "skipped because attraction/hotel failed", required=False)

        if attractions and hotel:
            self.external(
                "openai.planner_direct_smoke",
                lambda: get_planner_provider().generate_plan(
                    request={
                        "title": f"it_fullsuite direct planner {self.suffix}",
                        "city": CITY,
                        "start_date": "2026-06-10",
                        "end_date": "2026-06-10",
                        "budget_range": "medium",
                        "transport_preference": "public_transit",
                        "accommodation_preference": "comfort",
                        "notes": "Direct full integration smoke test for real planner provider.",
                    },
                    user_profile={"interest_tags": ["museum", "food"]},
                    attractions=attractions[:3],
                    weather_info=weather or [],
                    hotel=hotel,
                    profile_summary="Prefers museums, local food, and balanced pace.",
                ),
                lambda value: isinstance(value, dict) and bool(value.get("days")) and bool(value.get("budget")),
                lambda value: f"days={len(value.get('days', []))} total={value.get('budget', {}).get('estimated_total')}",
            )

        self.run_api_flow(engine)
        self.summarize()

    def run_api_flow(self, engine: Any) -> None:
        app = create_app()
        with TestClient(app) as client:
            self.assert_status("api.health", client.get("/health"), 200)
            self.assert_status("security.unauth_plans_rejected", client.get("/api/plans"), 401)
            self.assert_status(
                "security.invalid_token_rejected",
                client.get("/api/plans", headers={"Authorization": "Bearer invalid.token.value"}),
                401,
            )

            self.assert_status("auth.register.alice", self.register(client, self.alice), 201)
            self.assert_status("auth.register.bob", self.register(client, self.bob), 201)

            alice_headers = self.login(client, self.alice, "auth.login.alice")
            bob_headers = self.login(client, self.bob, "auth.login.bob")

            me = client.get("/api/auth/me", headers=alice_headers)
            self.assert_status("auth.me", me, 200)
            self.record("auth.me.username", me.json().get("username") == self.alice, me.json().get("username"))

            duplicate = client.post(
                "/api/auth/register",
                json={"username": self.alice, "email": f"dupe_{self.suffix}@example.com", "password": PASSWORD},
            )
            self.assert_status("auth.duplicate_rejected", duplicate, 400)
            self.assert_status(
                "auth.bad_login_rejected",
                client.post("/api/auth/login", json={"username": self.alice, "password": "wrong"}),
                401,
            )

            self.assert_status(
                "validation.end_before_start_rejected",
                client.post(
                    "/api/plans",
                    headers=alice_headers,
                    json={
                        "title": "bad date",
                        "city": CITY,
                        "start_date": "2026-06-12",
                        "end_date": "2026-06-10",
                        "budget_range": "medium",
                    },
                ),
                422,
            )
            self.assert_status(
                "validation.long_title_rejected",
                client.post(
                    "/api/plans",
                    headers=alice_headers,
                    json={
                        "title": "x" * 101,
                        "city": CITY,
                        "start_date": "2026-06-10",
                        "end_date": "2026-06-10",
                        "budget_range": "medium",
                    },
                ),
                422,
            )

            self.assert_status(
                "profile.update",
                client.put(
                    "/api/profile/me",
                    headers=alice_headers,
                    json={
                        "travel_style": "depth",
                        "budget_level": "high",
                        "interest_tags": ["museum", "food", "citywalk"],
                        "transport_preference": "public_transit",
                        "accommodation_preference": "comfort",
                        "risk_sensitivity": "high",
                        "pace_preference": "balanced",
                    },
                ),
                200,
            )

            create = client.post(
                "/api/plans",
                headers=alice_headers,
                json={
                    "title": f"it_fullsuite Shanghai real LLM plan {self.suffix}",
                    "city": CITY,
                    "start_date": "2026-06-10",
                    "end_date": "2026-06-10",
                    "budget_range": "medium",
                    "transport_preference": "public_transit",
                    "accommodation_preference": "comfort",
                    "notes": "Use real LLM planner if configured. Prefer museums, local food, and realistic transit.",
                },
            )
            self.assert_status("plan.create_real_llm_task", create, 200)

            task_id = create.json()["task_id"]
            task = client.get(f"/api/tasks/{task_id}", headers=alice_headers)
            self.assert_status("task.status_success", task, 200)
            task_json = task.json()
            self.record(
                "task.completed",
                task_json.get("status") == "success" and task_json.get("progress") == 100,
                str(task_json),
            )
            if task_json.get("status") != "success":
                raise AssertionError(task_json)

            plan_id = task_json["plan_id"]
            version_id = task_json["result_version_id"]

            self.assert_status("task.logs", client.get(f"/api/tasks/{task_id}/logs", headers=alice_headers), 200)
            result = client.get(f"/api/tasks/{task_id}/result", headers=alice_headers)
            self.assert_status("task.result", result, 200)

            content = result.json()["content_json"]
            self.record("llm.plan_schema.days", isinstance(content.get("days"), list) and len(content["days"]) >= 1)
            self.record(
                "llm.plan_schema.budget",
                isinstance(content.get("budget"), dict) and (content["budget"].get("estimated_total") or 0) > 0,
                f"total={content.get('budget', {}).get('estimated_total')}",
            )
            self.record(
                "llm.plan_schema.map",
                isinstance(content.get("map"), dict) and len(content.get("map", {}).get("points", [])) >= 1,
                f"points={len(content.get('map', {}).get('points', []))}",
            )
            self.record(
                "llm.plan_schema.food",
                any(
                    activity.get("type") == "food"
                    for day in content.get("days", [])
                    for activity in day.get("activities", [])
                ),
            )

            for name, response in [
                ("plan.get", client.get(f"/api/plans/{plan_id}", headers=alice_headers)),
                ("plan.summary", client.get(f"/api/plans/{plan_id}/summary", headers=alice_headers)),
                ("versions.list_v1", client.get(f"/api/plans/{plan_id}/versions", headers=alice_headers)),
                ("warnings.current", client.get(f"/api/plans/{plan_id}/warnings", headers=alice_headers)),
            ]:
                self.assert_status(name, response, 200)

            pdf = client.get(f"/api/plans/{plan_id}/versions/{version_id}/export", headers=alice_headers)
            self.assert_status("pdf.export", pdf, 200)
            self.record("pdf.magic", pdf.content[:4] == b"%PDF", str(pdf.content[:4]))

            for name, path in [
                ("permission.bob_get_plan", f"/api/plans/{plan_id}"),
                ("permission.bob_versions", f"/api/plans/{plan_id}/versions"),
                ("permission.bob_pdf", f"/api/plans/{plan_id}/versions/{version_id}/export"),
                ("permission.bob_warnings", f"/api/plans/{plan_id}/warnings"),
            ]:
                self.assert_status(name, client.get(path, headers=bob_headers), 404)

            edited = copy.deepcopy(content)
            edited["title"] = f"it_fullsuite edited high risk {self.suffix}"
            edited["weather_info"] = [{"date": "2026-06-10", "city": CITY, "condition": "heavy_rain", "risk_score": -6}]
            edited["warnings"] = []
            edit = client.put(
                f"/api/plans/{plan_id}/versions/{version_id}",
                headers=alice_headers,
                json={
                    "title": f"it_fullsuite edited high risk {self.suffix}",
                    "change_summary": "integration high risk edit",
                    "content": edited,
                },
            )
            self.assert_status("versions.edit_v2", edit, 200)
            v2 = edit.json()
            self.record("versions.v2_parent", v2.get("parent_version_id") == version_id)

            high_risk = client.get("/api/plans?risk_level=high", headers=alice_headers)
            self.assert_status("plans.filter_high_risk", high_risk, 200)
            self.record(
                "plans.filter_high_risk_contains_plan",
                any(item.get("id") == plan_id for item in high_risk.json()),
                f"returned={len(high_risk.json())}",
            )

            restore = client.post(f"/api/plans/{plan_id}/versions/{version_id}/restore", headers=alice_headers)
            self.assert_status("versions.restore_v3", restore, 200)
            v3 = restore.json()
            self.record("versions.v3_parent", v3.get("parent_version_id") == version_id)

            self.assert_status(
                "permission.bob_restore",
                client.post(f"/api/plans/{plan_id}/versions/{version_id}/restore", headers=bob_headers),
                404,
            )

            regenerate = client.post(
                f"/api/plans/{plan_id}/versions/{v3['id']}/regenerate",
                headers=alice_headers,
                json={
                    "title": f"it_fullsuite regenerated Shanghai real LLM plan {self.suffix}",
                    "city": CITY,
                    "start_date": "2026-06-11",
                    "end_date": "2026-06-11",
                    "budget_range": "high",
                    "transport_preference": "taxi",
                    "accommodation_preference": "luxury",
                    "notes": "Regenerate with real LLM. Prefer indoor attractions and comfortable pacing.",
                },
            )
            self.assert_status("versions.regenerate_task", regenerate, 200)
            regenerate_task = client.get(f"/api/tasks/{regenerate.json()['task_id']}", headers=alice_headers)
            self.assert_status("versions.regenerate_status", regenerate_task, 200)
            self.record("versions.regenerate_success", regenerate_task.json().get("status") == "success", str(regenerate_task.json()))

            self.assert_status(
                "permission.bob_regenerate",
                client.post(
                    f"/api/plans/{plan_id}/versions/{v3['id']}/regenerate",
                    headers=bob_headers,
                    json={
                        "title": "bob forbidden",
                        "city": CITY,
                        "start_date": "2026-06-11",
                        "end_date": "2026-06-11",
                        "budget_range": "high",
                    },
                ),
                404,
            )

            final_versions = client.get(f"/api/plans/{plan_id}/versions", headers=alice_headers)
            self.assert_status("versions.list_final", final_versions, 200)
            rows = final_versions.json()
            self.record("versions.chain_count", len(rows) >= 4, f"count={len(rows)}")
            self.record(
                "versions.source_types",
                {row.get("source_type") for row in rows}.issuperset({"created", "edited", "restored", "regenerated"}),
                str([row.get("source_type") for row in rows]),
            )

        with engine.connect() as conn:
            user_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE username LIKE 'it_fullsuite_%'")).scalar()
            plan_count = conn.execute(text("SELECT COUNT(*) FROM trip_plans WHERE title LIKE 'it_fullsuite%'")).scalar()
            version_count = conn.execute(text("SELECT COUNT(*) FROM trip_plan_versions WHERE content_json IS NOT NULL")).scalar()
            self.record("mysql.test_users_persisted", user_count >= 2, f"it_fullsuite_users={user_count}")
            self.record("mysql.test_plans_persisted", plan_count >= 1, f"it_fullsuite_plans={plan_count}")
            self.record("mysql.json_versions_exist", version_count >= 1, f"versions_with_json={version_count}")

    def register(self, client: TestClient, username: str) -> Any:
        return client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": PASSWORD,
                "profile": {
                    "travel_style": "depth",
                    "budget_level": "medium",
                    "interest_tags": ["history", "food"],
                    "transport_preference": "public_transit",
                    "accommodation_preference": "comfort",
                    "risk_sensitivity": "medium",
                    "pace_preference": "balanced",
                },
            },
        )

    def login(self, client: TestClient, username: str, check_name: str) -> dict[str, str]:
        response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
        self.assert_status(check_name, response, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def summarize(self) -> None:
        failed_required = [check for check in self.checks if check.required and not check.ok]
        warnings = [check for check in self.checks if not check.required and not check.ok]
        passed = len([check for check in self.checks if check.ok])
        print(f"SUMMARY passed={passed} failed={len(failed_required)} warnings={len(warnings)}")
        if warnings:
            print("WARNINGS " + ", ".join(check.name for check in warnings))
        if failed_required:
            raise SystemExit("FAILED: " + ", ".join(check.name for check in failed_required))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full manual integration test suite.")
    parser.add_argument(
        "--strict-external",
        action="store_true",
        help="Treat direct external provider failures as fatal instead of warnings.",
    )
    args = parser.parse_args()
    FullIntegrationRunner(strict_external=args.strict_external).run()


if __name__ == "__main__":
    main()
