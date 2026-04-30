"""Outer StateGraph wiring."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import OuterState, execute_node, persist_node, plan_node, reflect_node


def build_app():
    """Build and compile the outer StateGraph.

    The SkillStore is injected per-invocation via
    ``app.invoke(state, config={"configurable": {"skill_store": store}})``.
    """
    graph = StateGraph(OuterState)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("persist", persist_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "reflect")
    graph.add_edge("reflect", "persist")
    graph.add_edge("persist", END)

    return graph.compile()
