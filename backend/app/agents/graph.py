from collections.abc import Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.attraction_agent import run_attraction_agent
from app.agents.hotel_agent import run_hotel_agent
from app.agents.planner_agent import run_planner_agent
from app.agents.profile_agent import run_profile_agent
from app.agents.route_agent import run_route_agent
from app.agents.state import PlanningState
from app.agents.validator_agent import run_validator_agent
from app.agents.warning_agent import run_warning_agent
from app.agents.weather_agent import run_weather_agent


def build_planning_graph():
    graph = StateGraph(PlanningState)
    graph.add_node("profile", run_profile_agent)
    graph.add_node("attraction", run_attraction_agent)
    graph.add_node("weather_lookup", run_weather_agent)
    graph.add_node("hotel", run_hotel_agent)
    graph.add_node("planner", run_planner_agent)
    graph.add_node("route", run_route_agent)
    graph.add_node("validator", run_validator_agent)
    graph.add_node("alert_check", run_warning_agent)

    graph.add_edge(START, "profile")
    graph.add_edge("profile", "attraction")
    graph.add_edge("attraction", "weather_lookup")
    graph.add_edge("weather_lookup", "hotel")
    graph.add_edge("hotel", "planner")
    graph.add_edge("planner", "route")
    graph.add_edge("route", "validator")
    graph.add_edge("validator", "alert_check")
    graph.add_edge("alert_check", END)
    return graph.compile()


planning_graph = build_planning_graph()


def run_planning_graph(state: PlanningState) -> PlanningState:
    result = planning_graph.invoke(state)
    return _coerce_state(result)


def _coerce_state(result: PlanningState | Mapping[str, Any]) -> PlanningState:
    if isinstance(result, PlanningState):
        return result
    return PlanningState(**dict(result))
