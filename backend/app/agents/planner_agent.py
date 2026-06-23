from typing import Any

from app.agents.state import PlanningState
from app.services.providers import RuleBasedPlannerProvider, get_planner_provider


def run_planner_agent(state: PlanningState) -> dict[str, Any]:
    provider = get_planner_provider()
    try:
        final_plan = provider.generate_plan(
            request=state.request,
            user_profile=state.user_profile,
            attractions=state.attractions,
            weather_info=state.weather,
            hotel=state.hotels,
            profile_summary=state.profile_summary,
        )
        errors = state.errors
    except Exception as exc:
        # Wrap the rule-based fallback in its own try-except — if the
        # rule-based provider also fails (e.g. because state.request is
        # missing required keys), produce a minimal stub instead of
        # crashing the whole graph.
        try:
            final_plan = RuleBasedPlannerProvider().generate_plan(
                request=state.request,
                user_profile=state.user_profile,
                attractions=state.attractions,
                weather_info=state.weather,
                hotel=state.hotels,
                profile_summary=state.profile_summary,
            )
        except Exception as fallback_exc:
            city = state.request.get("city", "Unknown")
            final_plan = {
                "title": f"{city} Travel Plan (auto-generated)",
                "city": city,
                "days": [],
                "attractions": state.attractions,
                "hotel": state.hotels,
                "weather_info": state.weather,
                "budget": {},
                "warnings": [],
                "overall_suggestions": [],
            }
            errors = [*state.errors, f"planner provider failed: {exc}", f"rule-based fallback also failed: {fallback_exc}"]
            return {
                "final_plan": final_plan,
                "errors": errors,
                "progress_events": [*state.progress_events, "planner"],
            }
        errors = [*state.errors, f"planner provider failed: {exc}"]

    return {
        "final_plan": final_plan,
        "errors": errors,
        "progress_events": [*state.progress_events, "planner"],
    }
