import os

from app.agents.graph import build_planning_graph, run_planning_graph
from app.agents.route_agent import run_route_agent
from app.agents.state import PlanningState
from app.core.config import get_settings
from app.services.providers import MockAttractionProvider


def setup_function():
    os.environ["AGENT_PROVIDER_MODE"] = "mock"
    get_settings.cache_clear()


def make_state(**overrides):
    request = {
        "title": "Shanghai spring trip",
        "city": "Shanghai",
        "start_date": "2026-05-01",
        "end_date": "2026-05-04",
        "budget_range": "medium",
        "transport_preference": "public_transit",
        "accommodation_preference": "comfort",
    }
    request.update(overrides.pop("request", {}))
    return PlanningState(
        user_id=1,
        request=request,
        user_profile=overrides.pop("user_profile", {"interest_tags": ["food", "history"]}),
        **overrides,
    )


def test_planning_graph_uses_langgraph_nodes():
    graph = build_planning_graph().get_graph()

    assert {
        "profile",
        "attraction",
        "weather_lookup",
        "hotel",
        "planner",
        "route",
        "alert_check",
    }.issubset(graph.nodes.keys())


def test_planning_graph_builds_final_plan_and_warnings():
    state = run_planning_graph(make_state())

    assert isinstance(state, PlanningState)
    assert state.final_plan["title"] == "Shanghai spring trip"
    assert state.final_plan["city"] == "Shanghai"
    assert state.final_plan["start_date"] == "2026-05-01"
    assert state.final_plan["end_date"] == "2026-05-04"
    assert {"days", "attractions", "hotel", "weather_info", "budget", "warnings"}.issubset(
        state.final_plan.keys()
    )
    assert "map" in state.final_plan
    assert "points" in state.final_plan["map"]
    assert "routes" in state.final_plan["map"]
    for day in state.final_plan["days"]:
        activities = day["activities"]
        periods = {activity.get("period") for activity in activities}
        assert len(activities) >= 4
        assert {"morning", "afternoon", "evening"}.issubset(periods)
        assert any(activity.get("type") == "food" for activity in activities)
        assert all("duration" in activity and "budget" in activity for activity in activities)
    budget = state.final_plan["budget"]
    assert budget["estimated_total"] > 0
    assert {item["key"] for item in budget["breakdown"]} == {
        "lodging",
        "meals",
        "transport",
        "tickets",
        "buffer",
    }
    assert len(budget["per_day"]) == 4
    assert state.warnings == state.final_plan["warnings"]
    assert len(state.final_plan["warnings"]) == 1
    assert state.progress_events == [
        "profile",
        "attraction",
        "weather",
        "hotel",
        "planner",
        "route",
        "alert_check",
    ]


def test_planning_graph_keeps_plan_usable_when_attraction_provider_fails(monkeypatch):
    def fail_search(self, city, interests):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(MockAttractionProvider, "search", fail_search)

    state = run_planning_graph(make_state())

    assert state.final_plan["attractions"] == []
    assert state.final_plan["days"][0]["activities"][0]["title"]
    assert any("attraction provider failed" in error for error in state.errors)


def test_planning_graph_preserves_origin_for_ai_plan_generation():
    state = run_planning_graph(
        make_state(
            request={
                "title": "北京出发上海两日游",
                "origin": "北京",
                "city": "上海",
                "start_date": "2026-05-01",
                "end_date": "2026-05-02",
                "budget_range": "medium",
                "transport_preference": "public_transit",
                "accommodation_preference": "comfort",
            }
        )
    )

    assert state.final_plan["origin"] == "北京"
    assert state.final_plan["city"] == "上海"
    assert any("北京" in suggestion and "上海" in suggestion for suggestion in state.final_plan["overall_suggestions"])


def test_route_agent_uses_activity_locations_when_plan_attractions_are_partial():
    state = make_state(
        hotels={
            "id": "hotel-1",
            "name": "Base Hotel",
            "location": {"lng": 121.49, "lat": 31.23},
        },
        attractions=[
            {
                "id": "poi-1",
                "name": "City Museum",
                "location": {"lng": 121.48, "lat": 31.22},
            }
        ],
        final_plan={
            "hotel": {
                "id": "hotel-1",
                "name": "Base Hotel",
                "location": {"lng": 121.49, "lat": 31.23},
            },
            "attractions": [{"poi_id": "poi-1", "name": "City Museum"}],
            "days": [
                {
                    "date": "2026-05-01",
                    "activities": [
                        {
                            "time": "09:00",
                            "type": "attraction",
                            "title": "City Museum visit",
                            "poi_id": "poi-1",
                            "location": {"lng": 121.48, "lat": 31.22},
                        }
                    ],
                }
            ],
        },
    )

    result = run_route_agent(state)
    map_data = result["final_plan"]["map"]

    assert len(map_data["points"]) == 2
    assert any(point["id"] == "poi-1" for point in map_data["points"])
    assert len(map_data["routes"]) == 1
