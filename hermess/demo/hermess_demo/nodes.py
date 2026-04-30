"""Outer graph nodes: plan / execute / reflect / persist."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .config import build_chat_model
from .prompts import (
    PLAN_PROMPT,
    REFLECT_PROMPT,
    compact_execution_trace,
    render_execute_system,
    render_skill_index_block,
)
from .react_tools import REACT_TOOLS
from .skill_store import (
    LoadedSkill,
    SkillIndexEntry,
    SkillStore,
    _validate_content_size,
    _validate_frontmatter,
)


# ── State ─────────────────────────────────────────────────────────────────


class OuterState(TypedDict, total=False):
    task: str
    round_id: int

    skill_index: list[SkillIndexEntry]
    plan_decision: "PlanDecision"
    loaded_skills: list[LoadedSkill]

    execution_messages: list
    execution_answer: str

    reflection: "ReflectDecision"
    persist_result: dict[str, Any]


# ── Pydantic decision models ──────────────────────────────────────────────


class PlanDecision(BaseModel):
    load: list[str] = Field(
        default_factory=list,
        description="Skill names to load (<=3).",
    )
    rationale: str = Field(
        default="",
        description="Short reason for the loading choice.",
    )


class ReflectDecision(BaseModel):
    action: Literal["none", "create", "patch"]
    rationale: str = ""
    # create branch
    name: str | None = None
    category: str | None = None
    content: str | None = None
    # patch branch
    target_skill: str | None = None
    old_string: str | None = None
    new_string: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_store(config) -> SkillStore:
    """Pull the SkillStore injected via graph config.

    ``config["configurable"]["skill_store"]`` is set when the app is invoked.
    """
    cfg = (config or {}).get("configurable") or {}
    store = cfg.get("skill_store")
    if not isinstance(store, SkillStore):
        raise RuntimeError("SkillStore missing from graph config.")
    return store


# ── Nodes ─────────────────────────────────────────────────────────────────


def plan_node(state: OuterState, config) -> dict[str, Any]:
    store = _get_store(config)
    entries = store.list()
    skill_index_block = render_skill_index_block(entries)

    model = build_chat_model(temperature=0.0)
    planner = model.with_structured_output(PlanDecision)
    prompt = PLAN_PROMPT.format(
        task=state["task"],
        skill_index_block=skill_index_block,
    )
    try:
        decision: PlanDecision = planner.invoke(prompt)
    except Exception as exc:  # structured-output failure → conservative default
        decision = PlanDecision(
            load=[], rationale=f"[planner fallback] {exc}"
        )

    loaded: list[LoadedSkill] = []
    available_names = {e.name for e in entries}
    for name in decision.load[:3]:
        if name not in available_names:
            continue
        skill = store.view(name)
        if skill is not None:
            loaded.append(skill)

    return {
        "skill_index": entries,
        "plan_decision": decision,
        "loaded_skills": loaded,
    }


def execute_node(state: OuterState, config) -> dict[str, Any]:
    loaded_skills: list[LoadedSkill] = state.get("loaded_skills") or []
    system_prompt = render_execute_system(loaded_skills)

    model = build_chat_model(temperature=0.0)
    agent = create_react_agent(
        model=model,
        tools=REACT_TOOLS,
        prompt=system_prompt,
    )

    messages_in = [HumanMessage(content=state["task"])]
    result = agent.invoke(
        {"messages": messages_in},
        config={"recursion_limit": 25},
    )
    messages = result["messages"]

    # Preferred: pull the answer from submit_final's tool_result.
    answer = None
    from langchain_core.messages import ToolMessage

    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name == "submit_final":
            answer = (msg.content if isinstance(msg.content, str) else str(msg.content)).strip()
            break
    if not answer:
        # Fallback: last AI message content.
        for msg in reversed(messages):
            content = getattr(msg, "content", None)
            if isinstance(content, str) and content.strip():
                answer = content.strip()
                break
    if not answer:
        answer = "(no final answer produced)"

    return {
        "execution_messages": messages,
        "execution_answer": answer,
    }


def reflect_node(state: OuterState, config) -> dict[str, Any]:
    loaded_skills: list[LoadedSkill] = state.get("loaded_skills") or []
    loaded_names = [s.name for s in loaded_skills] or ["(none)"]
    loaded_bodies = (
        "\n\n---\n\n".join(
            f"### {s.name}\n{s.body.strip()}" for s in loaded_skills
        )
        or "(none)"
    )
    trace = compact_execution_trace(state.get("execution_messages") or [])

    model = build_chat_model(temperature=0.0)
    reflector = model.with_structured_output(ReflectDecision)
    prompt = REFLECT_PROMPT.format(
        task=state["task"],
        loaded_skill_names=", ".join(loaded_names),
        loaded_bodies=loaded_bodies,
        trace=trace,
        final_answer=state.get("execution_answer", ""),
    )
    try:
        decision: ReflectDecision = reflector.invoke(prompt)
    except Exception as exc:
        decision = ReflectDecision(
            action="none",
            rationale=f"[reflector fallback] {exc}",
        )

    # Local validation for create branch — degrade to none if invalid.
    if decision.action == "create":
        if not (decision.name and decision.content):
            decision = ReflectDecision(
                action="none",
                rationale="create proposed but missing name/content",
            )
        else:
            err = _validate_frontmatter(decision.content) or _validate_content_size(
                decision.content
            )
            if err:
                decision = ReflectDecision(
                    action="none",
                    rationale=f"create content invalid: {err}",
                )

    if decision.action == "patch":
        if not (decision.target_skill and decision.old_string and decision.new_string):
            decision = ReflectDecision(
                action="none",
                rationale="patch proposed but missing target_skill/old_string/new_string",
            )

    return {"reflection": decision}


def persist_node(state: OuterState, config) -> dict[str, Any]:
    store = _get_store(config)
    decision: ReflectDecision = state["reflection"]

    if decision.action == "none":
        return {
            "persist_result": {
                "status": "noop",
                "reason": decision.rationale,
            }
        }

    if decision.action == "create":
        result = store.create(
            name=decision.name or "",
            content=decision.content or "",
            category=decision.category or "text-processing",
        )
        return {"persist_result": result}

    if decision.action == "patch":
        result = store.patch(
            name=decision.target_skill or "",
            old_string=decision.old_string or "",
            new_string=decision.new_string or "",
        )
        return {"persist_result": result}

    return {"persist_result": {"status": "noop", "reason": "unknown action"}}
