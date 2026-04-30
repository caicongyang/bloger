"""Entry point — runs the 3-round scenario end to end.

Round 1: 中文纯日期 → skill 尚未存在,期望 plan 不加载、reflect 触发 create。
Round 2: 英文纯日期 → plan 加载上一轮沉淀的 skill,reflect 应该 none。
Round 3: 中文日期 + 时间 + 东八区 → plan 加载 skill,执行时用到 tz_offset,
         reflect 发现 skill 没讲时区,触发 patch。
"""

from __future__ import annotations

import sys
from pathlib import Path

from hermess_demo.graph import build_app
from hermess_demo.skill_store import SkillStore

ROUNDS = [
    {
        "round_id": 1,
        "task": '请将 "2026年4月30日" 标准化为 ISO 8601 格式。只需日期部分。',
    },
    {
        "round_id": 2,
        "task": '请将 "30 April 2026" 标准化为 ISO 8601 格式。只需日期部分。',
    },
    {
        "round_id": 3,
        "task": (
            '请将 "2026年4月30日 14:30 东八区" 标准化为 ISO 8601 格式,'
            "必须包含时间和时区偏移。"
        ),
    },
]


def _divider(title: str, char: str = "═") -> str:
    line = char * 70
    return f"\n{line}\n  {title}\n{line}"


def _print_skill_index(store: SkillStore) -> None:
    entries = store.list()
    if not entries:
        print("  [skill index] (empty)")
        return
    print("  [skill index]")
    for e in entries:
        print(f"    - {e.name}  ({e.category or 'uncategorized'})")
        print(f"      {e.description}")


def _print_plan(decision, loaded) -> None:
    print(f"  [plan] load={decision.load!r}")
    print(f"         rationale: {decision.rationale}")
    if loaded:
        print(f"  [plan] loaded {len(loaded)} skill(s): "
              + ", ".join(s.name for s in loaded))


def _print_execution(answer: str, messages) -> None:
    tool_calls = 0
    for msg in messages:
        if getattr(msg, "tool_calls", None):
            tool_calls += len(msg.tool_calls)
    print(f"  [execute] tool_calls={tool_calls}")
    print(f"  [execute] final_answer: {answer}")


def _print_reflection(decision) -> None:
    print(f"  [reflect] action={decision.action}")
    print(f"            rationale: {decision.rationale}")
    if decision.action == "create":
        print(f"            → new skill '{decision.name}' in '{decision.category}'")
    elif decision.action == "patch":
        print(f"            → patch '{decision.target_skill}'")
        old_preview = (decision.old_string or "")[:80].replace("\n", " ⏎ ")
        new_preview = (decision.new_string or "")[:80].replace("\n", " ⏎ ")
        print(f"            old: {old_preview!r}")
        print(f"            new: {new_preview!r}")


def _print_persist(result: dict) -> None:
    status = result.get("status")
    if status == "noop":
        print(f"  [persist] noop — {result.get('reason', '')}")
    elif status in {"created", "patched"}:
        print(f"  [persist] {status}: {result.get('path')}")
    elif status == "error":
        print(f"  [persist] ERROR: {result.get('error')}")


def main() -> int:
    demo_root = Path(__file__).resolve().parent
    skills_dir = demo_root / "skills"
    store = SkillStore(skills_dir)
    app = build_app()

    print(_divider("Hermess Demo · Skill Lifecycle (3 rounds)"))
    print(f"Skill store: {skills_dir}")

    for round_spec in ROUNDS:
        rid = round_spec["round_id"]
        task = round_spec["task"]
        print(_divider(f"Round {rid}"))
        print(f"Task: {task}")
        _print_skill_index(store)

        final_state = app.invoke(
            {"task": task, "round_id": rid},
            config={"configurable": {"skill_store": store}},
        )

        print()
        _print_plan(final_state["plan_decision"], final_state.get("loaded_skills") or [])
        print()
        _print_execution(
            final_state.get("execution_answer", ""),
            final_state.get("execution_messages") or [],
        )
        print()
        _print_reflection(final_state["reflection"])
        print()
        _print_persist(final_state.get("persist_result") or {})

    print(_divider("Final skill library"))
    for e in store.list():
        print(f"- {e.name}: {e.description}")
        print(f"  {e.path}")

    print(_divider("Done", char="─"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
