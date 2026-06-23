import os

import pytest

from app.agents.graph import run_planning_graph
from app.agents.state import PlanningState
from app.core.config import get_settings


def setup_function():
    os.environ["AGENT_PROVIDER_MODE"] = "mock"
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "预算10000，酒店含早，少走路，优先安排地道美食和博物馆。",
            {
                "city": "目的地待确认",
                "duration": "3天",
                "budget_range": "high",
                "transport_preference": "private_transport",
                "accommodation_preference": "hotel_with_breakfast",
            },
        ),
        (
            "预算2000，想省钱，多留休息时间。",
            {
                "city": "目的地待确认",
                "duration": "3天",
                "budget_range": "low",
                "transport_preference": "public_transit",
                "accommodation_preference": "budget",
            },
        ),
        (
            "民宿，步行优先，预算3500。",
            {
                "city": "目的地待确认",
                "duration": "3天",
                "budget_range": "medium",
                "transport_preference": "walking",
                "accommodation_preference": "homestay",
            },
        ),
        (
            "从北京出发去上海玩两天，预算3000。",
            {
                "origin": "北京",
                "city": "上海",
                "duration": "2天",
                "budget_range": "medium",
            },
        ),
        (
            "2026-10-01去西安4日游，预算8000，打车。",
            {
                "city": "西安",
                "duration": "4天",
                "start_date": "2026-10-01",
                "budget_range": "high",
                "transport_preference": "private_transport",
            },
        ),
    ],
)
def test_parse_plan_text_more_preference_cases(client, text, expected):
    response = client.post("/api/plans/parse", json={"text": text})

    assert response.status_code == 200
    data = response.json()
    for key, value in expected.items():
        assert data[key] == value


@pytest.mark.parametrize(
    "plan_request",
    [
        {
            "title": "上海2天旅行方案",
            "origin": "南京",
            "city": "上海",
            "start_date": "2026-09-01",
            "end_date": "2026-09-02",
            "budget_range": "medium",
            "transport_preference": "private_transport",
            "accommodation_preference": "hotel_with_breakfast",
            "notes": "少走路，酒店含早，多安排美食。",
        },
        {
            "title": "西安4天旅行方案",
            "city": "西安",
            "start_date": "2026-10-01",
            "end_date": "2026-10-04",
            "budget_range": "high",
            "transport_preference": "public_transit",
            "accommodation_preference": "luxury",
            "notes": "重点安排历史文化、博物馆和城市街区体验。",
        },
        {
            "title": "杭州1天旅行方案",
            "origin": "杭州",
            "city": "杭州",
            "start_date": "2026-11-11",
            "end_date": "2026-11-11",
            "budget_range": "low",
            "transport_preference": "walking",
            "accommodation_preference": "budget",
            "notes": "轻松慢游，不要太赶。",
        },
    ],
)
def test_generated_plan_more_cases_keep_core_fields_and_schedule_valid(plan_request):
    state = run_planning_graph(
        PlanningState(
            user_id=1,
            request=plan_request,
            user_profile={
                "interest_tags": ["food", "culture"],
                "pace_preference": "relaxed",
                "risk_sensitivity": "medium",
            },
        )
    )
    plan = state.final_plan
    expected_days = _inclusive_days(plan_request["start_date"], plan_request["end_date"])

    assert plan["title"] == plan_request["title"]
    assert plan["city"] == plan_request["city"]
    assert plan["start_date"] == plan_request["start_date"]
    assert plan["end_date"] == plan_request["end_date"]
    assert len(plan["days"]) == expected_days
    assert plan["budget"]["estimated_total"] == sum(item["value"] for item in plan["budget"]["breakdown"])

    for day in plan["days"]:
        meal_periods = {activity.get("period") for activity in day["activities"] if activity.get("type") == "food"}
        assert "lunch" in meal_periods
        assert all(activity.get("time") and activity.get("duration") for activity in day["activities"])
        _assert_nodes_sorted(day.get("nodes", []))

    intercity = [
        activity
        for day in plan["days"]
        for activity in day["activities"]
        if activity.get("type") == "intercity_transport"
    ]
    if plan_request.get("origin") and plan_request["origin"] != plan_request["city"]:
        outbound = next(item for item in intercity if item.get("direction") == "outbound")
        returning = next(item for item in intercity if item.get("direction") == "return")
        assert outbound["time"] >= "08:00"
        assert _time_end(returning["time"]) <= 21 * 60 + 30
    else:
        assert intercity == []


def _inclusive_days(start: str, end: str) -> int:
    from datetime import date

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    return (end_date - start_date).days + 1


def _assert_nodes_sorted(nodes):
    previous_end = -1
    for node in nodes:
        start = _time_start(node["time"])
        end = _time_end(node["time"])
        assert start >= previous_end
        assert end > start
        previous_end = end


def _time_start(value: str) -> int:
    start = value.split("-", 1)[0]
    hour, minute = start.split(":", 1)
    return int(hour) * 60 + int(minute[:2])


def _time_end(value: str) -> int:
    end = value.split("-", 1)[1]
    hour, minute = end.split(":", 1)
    return int(hour) * 60 + int(minute[:2])
