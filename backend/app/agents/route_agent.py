from typing import Any

from app.agents.state import PlanningState
from app.services.providers import (
    MockRouteProvider,
    enrich_meals_with_restaurants,
    enrich_days_with_routes,
    ensure_intercity_transfer_activities,
    ensure_hotel_evening_activities,
    get_route_provider,
    normalize_plan_budget,
)


def run_route_agent(state: PlanningState) -> dict[str, Any]:
    provider = get_route_provider()
    final_plan = dict(state.final_plan)
    route_attractions = _merge_route_attractions(final_plan.get("attractions"), state.attractions)
    final_plan["attractions"] = route_attractions
    final_plan["days"] = enrich_meals_with_restaurants(
        days=final_plan.get("days", []),
        city=state.request["city"],
        budget_range=state.request.get("budget_range", "medium"),
        accommodation_preference=state.request.get("accommodation_preference", ""),
    )
    final_plan["days"] = ensure_intercity_transfer_activities(
        days=final_plan.get("days", []),
        request=state.request,
    )
    final_plan["days"] = ensure_hotel_evening_activities(
        days=final_plan.get("days", []),
        hotel=final_plan.get("hotel") or state.hotels,
    )
    try:
        route_map_data = provider.build_routes(
            days=final_plan.get("days", []),
            hotel=final_plan.get("hotel") or state.hotels,
            attractions=route_attractions,
            transport_preference=state.request.get("transport_preference", "public_transit"),
            city=state.request["city"],
        )
        errors = state.errors
    except Exception as exc:
        route_map_data = MockRouteProvider().build_routes(
            days=final_plan.get("days", []),
            hotel=final_plan.get("hotel") or state.hotels,
            attractions=final_plan.get("attractions") or state.attractions,
            transport_preference=state.request.get("transport_preference", "public_transit"),
            city=state.request["city"],
        )
        errors = [*state.errors, f"route provider failed: {exc}"]

    existing_map = final_plan.get("map") if isinstance(final_plan.get("map"), dict) else {}
    map_data = {"points": route_map_data.get("points") or existing_map.get("points") or []}
    final_plan["map"] = map_data
    final_plan["days"] = enrich_days_with_routes(
        days=final_plan.get("days", []),
        routes=route_map_data.get("routes", []),
        transport_preference=state.request.get("transport_preference", "public_transit"),
        budget_range=state.request.get("budget_range", "medium"),
    )
    final_plan["budget"] = normalize_plan_budget(
        budget=final_plan.get("budget"),
        days=final_plan.get("days", []),
        request=state.request,
        hotel=final_plan.get("hotel") or state.hotels,
    )
    return {
        "final_plan": final_plan,
        "map_data": map_data,
        "routes": [],
        "errors": errors,
        "progress_events": [*state.progress_events, "route"],
    }


def _merge_route_attractions(plan_attractions: Any, state_attractions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index: dict[str, int] = {}

    def keys_for(item: dict[str, Any]) -> list[str]:
        keys = []
        for key in (item.get("id"), item.get("poi_id"), item.get("name")):
            if key:
                keys.append(str(key))
        return keys

    def upsert(item: Any) -> None:
        if not isinstance(item, dict):
            return
        keys = keys_for(item)
        existing_index = next((index[key] for key in keys if key in index), None)
        if existing_index is None:
            record = dict(item)
            if record.get("id") is None and record.get("poi_id"):
                record["id"] = record["poi_id"]
            merged.append(record)
            position = len(merged) - 1
            for key in keys_for(record):
                index[key] = position
            return

        record = merged[existing_index]
        previous_location = record.get("location")
        for key, value in item.items():
            if value not in (None, "", [], {}):
                record[key] = value
        if not record.get("location") and previous_location:
            record["location"] = previous_location
        if record.get("id") is None and record.get("poi_id"):
            record["id"] = record["poi_id"]
        for key in keys_for(record):
            index[key] = existing_index

    for item in state_attractions or []:
        upsert(item)
    for item in plan_attractions or []:
        upsert(item)

    return merged
