import os

from app.agents.graph import build_planning_graph, run_planning_graph
from app.agents.route_agent import run_route_agent
from app.agents.state import PlanningState
from app.core.config import get_settings
from app.services import providers
from app.services.providers import MockAttractionProvider, RuleBasedPlannerProvider


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
    assert "routes" not in state.final_plan["map"]
    for day in state.final_plan["days"]:
        activities = day["activities"]
        periods = {activity.get("period") for activity in activities}
        assert len(activities) >= 4
        assert day.get("nodes")
        assert {"morning", "afternoon", "evening"}.issubset(periods)
        assert any(activity.get("type") == "food" for activity in activities)
        meal_periods = {
            activity.get("period")
            for activity in activities
            if activity.get("type") == "food"
        }
        # Should have at least some meal periods (morning and/or lunch and/or evening)
        assert len(meal_periods) > 0
        assert meal_periods.issubset({"morning", "lunch", "evening"})
        assert any(activity.get("type") == "transport" for activity in activities)
        assert all(activity.get("time") != "--:--" for activity in activities if activity.get("type") == "transport")
        assert all("duration" in activity and "budget" in activity for activity in activities)
        assert not any("本地午餐" in activity.get("title", "") for activity in activities)
        for node in day["nodes"]:
            assert _minutes(node["start_time"]) < 24 * 60
            assert _minutes(node["end_time"]) <= 24 * 60
            if node.get("type") == "food" and ("晚餐" in str(node.get("title")) or _minutes(node["start_time"]) >= 17 * 60):
                assert _minutes(node["start_time"]) <= 19 * 60 + 30
    assert any(
        activity.get("type") == "hotel"
        for day in state.final_plan["days"][:-1]
        for activity in day["activities"]
    )
    budget = state.final_plan["budget"]
    transport_activity_total = sum(
        activity["budget"]
        for day in state.final_plan["days"]
        for activity in day["activities"]
        if activity.get("type") == "transport"
    )
    assert budget["estimated_total"] > 0
    assert {item["key"] for item in budget["breakdown"]} >= {
        "lodging",
        "meals",
        "transport",
        "tickets",
    }
    assert budget["estimated_total"] == sum(item["value"] for item in budget["breakdown"])
    assert next(item["value"] for item in budget["breakdown"] if item["key"] == "transport") == transport_activity_total
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
        "validator",
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
    assert any(
        activity.get("type") == "intercity_transport"
        for day in state.final_plan["days"]
        for activity in day["activities"]
    )
    assert all(day.get("nodes") for day in state.final_plan["days"])
    first_intercity = next(
        activity
        for activity in state.final_plan["days"][0]["activities"]
        if activity.get("type") == "intercity_transport"
    )
    # Time could be a range like "06:30-09:00" or a specific time
    time_val = first_intercity["time"]
    assert time_val is not None and time_val != "--:--"
    assert any(item["key"] == "intercity" for item in state.final_plan["budget"]["breakdown"])
    assert state.final_plan["budget"]["estimated_total"] == sum(
        item["value"] for item in state.final_plan["budget"]["breakdown"]
    )
    assert all(
        activity.get("location")
        for day in state.final_plan["days"]
        for activity in day["activities"]
        if activity.get("type") == "food"
    )
    # Verify there are activities with various types
    activity_types = {
        activity.get("type")
        for day in state.final_plan["days"]
        for activity in day["activities"]
    }
    assert len(activity_types) > 0
    map_point_ids = {str(point.get("node_id") or point.get("id")) for point in state.final_plan["map"]["points"]}
    day_node_ids = {
        str(node.get("id") or node.get("source_id"))
        for day in state.final_plan["days"]
        for node in day.get("nodes", [])
        if node.get("type") != "transport" and node.get("location")
    }
    assert map_point_ids <= day_node_ids
    last_day_nodes = state.final_plan["days"][-1]["nodes"]
    previous_end = -1
    for node in last_day_nodes:
        start = _minutes(node["start_time"])
        end = _minutes(node["end_time"])
        assert start >= previous_end
        assert end > start
        previous_end = end
    return_node = next(node for node in last_day_nodes if node.get("type") == "intercity_transport" and node.get("direction") == "return")
    # Return journey should have a valid time
    assert return_node["end_time"] is not None


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

    assert len(map_data["points"]) >= 2
    assert any(point["id"] == "poi-1" for point in map_data["points"])
    assert "routes" not in map_data
    assert any(
        activity.get("type") == "transport"
        for day in result["final_plan"]["days"]
        for activity in day.get("activities", [])
    )


def test_enrich_meals_calls_real_provider_for_breakfast_lunch_and_dinner(monkeypatch):
    calls = []

    def fake_should_use_real(provider):
        return provider == "amap"

    def fake_amap_place_around(city, location, keywords, types, offset):
        calls.append(keywords)
        return [
            {
                "id": f"poi-{len(calls)}",
                "name": f"真实餐馆 {len(calls)}",
                "location": f"{121.48 + len(calls) * 0.001},{31.23 + len(calls) * 0.001}",
                "address": "真实地址",
                "type": "餐饮服务",
            }
        ]

    monkeypatch.setattr(providers, "_should_use_real", fake_should_use_real)
    monkeypatch.setattr(providers, "_amap_place_around", fake_amap_place_around)

    days = [
        {
            "date": "2026-05-01",
            "activities": [
                {
                    "time": "09:00-11:00",
                    "period": "morning",
                    "type": "attraction",
                    "title": "City Museum",
                    "location": {"lng": 121.48, "lat": 31.23},
                }
            ],
        }
    ]

    enriched = providers.enrich_meals_with_restaurants(days, "Shanghai", "medium")
    meals = [activity for activity in enriched[0]["activities"] if activity.get("type") == "food"]

    assert len(meals) == 3
    assert all(meal.get("location") for meal in meals)
    assert any("早餐" in keywords for keywords in calls)
    assert any("午餐" in keywords for keywords in calls)
    assert any("晚餐" in keywords for keywords in calls)


def test_rule_based_planner_uses_profile_pace_and_weather_sensitivity():
    request = {
        "title": "Profile trip",
        "city": "Shanghai",
        "start_date": "2026-05-01",
        "end_date": "2026-05-01",
        "budget_range": "medium",
        "transport_preference": "public_transit",
        "accommodation_preference": "comfort",
    }
    attractions = [
        {"id": "outdoor", "name": "City Park", "category": "公园", "location": {"lng": 121.48, "lat": 31.23}},
        {"id": "museum", "name": "History Museum", "category": "博物馆", "location": {"lng": 121.49, "lat": 31.24}},
        {"id": "mall", "name": "Shopping Mall", "category": "商场", "location": {"lng": 121.50, "lat": 31.25}},
        {"id": "street", "name": "Walking Street", "category": "步行街", "location": {"lng": 121.51, "lat": 31.26}},
    ]
    weather = [{"date": "2026-05-01", "condition": "cloudy", "risk_score": -1}]
    hotel = {"name": "Base Hotel", "price_per_night": 300, "location": {"lng": 121.47, "lat": 31.22}}

    relaxed = RuleBasedPlannerProvider().generate_plan(
        request,
        {"pace_preference": "relaxed", "risk_sensitivity": "high", "travel_style": "culture"},
        attractions,
        weather,
        hotel,
    )
    intensive = RuleBasedPlannerProvider().generate_plan(
        request,
        {"pace_preference": "intensive", "risk_sensitivity": "low", "travel_style": "shopping"},
        attractions,
        weather,
        hotel,
    )

    relaxed_attractions = [item for item in relaxed["days"][0]["activities"] if item.get("type") == "attraction"]
    intensive_attractions = [item for item in intensive["days"][0]["activities"] if item.get("type") == "attraction"]

    assert len(relaxed_attractions) < len(intensive_attractions)
    assert relaxed["days"][0]["weather_suggestion"].startswith("当天存在天气风险")


def test_hotel_breakfast_preference_does_not_call_external_breakfast_provider(monkeypatch):
    calls = []

    def fake_should_use_real(provider):
        return provider == "amap"

    def fake_amap_place_around(city, location, keywords, types, offset):
        calls.append(keywords)
        return [
            {
                "id": f"poi-{len(calls)}",
                "name": f"真实餐馆 {len(calls)}",
                "location": f"{121.48 + len(calls) * 0.001},{31.23 + len(calls) * 0.001}",
                "address": "真实地址",
                "type": "餐饮服务",
            }
        ]

    monkeypatch.setattr(providers, "_should_use_real", fake_should_use_real)
    monkeypatch.setattr(providers, "_amap_place_around", fake_amap_place_around)

    days = [
        {
            "date": "2026-05-01",
            "activities": [
                {
                    "time": "09:00-11:00",
                    "period": "morning",
                    "type": "attraction",
                    "title": "City Museum",
                    "location": {"lng": 121.48, "lat": 31.23},
                }
            ],
        }
    ]

    enriched = providers.enrich_meals_with_restaurants(days, "Shanghai", "medium", "hotel_with_breakfast")
    meals = [activity for activity in enriched[0]["activities"] if activity.get("type") == "food"]

    assert any(meal.get("title") == "酒店早餐" and meal.get("budget") == 0 for meal in meals)
    assert not any("早餐" in keywords for keywords in calls)
    assert any("午餐" in keywords for keywords in calls)
    assert any("晚餐" in keywords for keywords in calls)


def _minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute[:2])
