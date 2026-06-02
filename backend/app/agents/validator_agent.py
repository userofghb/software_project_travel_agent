from typing import Any

from app.agents.state import PlanningState
from app.services.providers import validate_and_repair_plan


def run_validator_agent(state: PlanningState) -> dict[str, Any]:
    final_plan, validator_warnings = validate_and_repair_plan(
        plan=dict(state.final_plan),
        request=state.request,
        hotel=state.final_plan.get("hotel") or state.hotels,
    )
    errors = state.errors
    if validator_warnings:
        errors = [*errors, *[f"validator repaired: {item}" for item in validator_warnings]]
    return {
        "final_plan": final_plan,
        "errors": errors,
        "progress_events": [*state.progress_events, "validator"],
    }
