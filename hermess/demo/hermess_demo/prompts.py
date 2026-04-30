"""Centralized prompt templates for the outer meta-loop.

Everything here is plain string templates with ``.format()`` placeholders.
Kept separate from ``nodes.py`` so prompt tuning doesn't force logic edits.
"""

from __future__ import annotations

# ── plan ──────────────────────────────────────────────────────────────────

PLAN_PROMPT = """\
You are planning how to solve a text-normalization task. Scan the skills
below; if ANY is even partially relevant to the task, include its name in
`load`. Err on the side of loading — it is cheaper to have instructions
you end up not needing than to miss a proven procedure.

Limit `load` to at most 3 skill names. If none are relevant, return an
empty list.

Task:
<<<
{task}
>>>

<available_skills>
{skill_index_block}
</available_skills>

Return a PlanDecision with the selected skill names and a one-line
rationale.
"""


def render_skill_index_block(entries) -> str:
    """Format skill index entries for PLAN_PROMPT.

    ``entries`` is a list of ``SkillIndexEntry`` dataclasses.
    """
    if not entries:
        return "(no skills available yet — this session starts from a blank library)"
    lines = []
    by_category: dict[str | None, list] = {}
    for e in entries:
        by_category.setdefault(e.category, []).append(e)
    for category in sorted(by_category.keys(), key=lambda c: c or ""):
        label = category or "(uncategorized)"
        lines.append(f"  {label}:")
        for e in sorted(by_category[category], key=lambda x: x.name):
            lines.append(f"    - {e.name}: {e.description}")
    return "\n".join(lines)


# ── execute (inner ReAct system prompt) ───────────────────────────────────

EXECUTE_SYSTEM_BASE = """\
You are a text-normalization agent. Your job is to convert the user's
input into the ISO 8601 date/time format they ask for.

Follow these rules strictly:
1. Think step by step.
2. Use the tools available to parse and format — DO NOT guess the output.
3. When you have the final answer, call `submit_final(answer=...)` with
   the normalized string and stop.
4. If a loaded skill tells you which tool sequence to use, follow it.
5. If the task requires something the loaded skill doesn't cover (e.g.
   timezones when the skill only covers dates), extend the procedure
   yourself and note what was missing in your reasoning.
"""

EXECUTE_SKILL_INJECTION = """\

## Loaded Skills

The following skills were pre-loaded by the planner. Treat them as
authoritative procedure for their stated scope:

{skill_bodies}

---
"""


def render_execute_system(loaded_skills) -> str:
    """Compose the inner ReAct system prompt."""
    if not loaded_skills:
        return EXECUTE_SYSTEM_BASE
    bodies = []
    for s in loaded_skills:
        bodies.append(f"### Skill: {s.name}\n\n{s.body.strip()}")
    return EXECUTE_SYSTEM_BASE + EXECUTE_SKILL_INJECTION.format(
        skill_bodies="\n\n".join(bodies)
    )


# ── reflect ───────────────────────────────────────────────────────────────

REFLECT_PROMPT = """\
You just finished a task. Decide whether the skill library needs to be
updated based on how the task was actually solved.

Task:
<<<
{task}
>>>

Loaded skills (names): {loaded_skill_names}

Loaded skill bodies:
<<<
{loaded_bodies}
>>>

Execution trace (compact):
<<<
{trace}
>>>

Final answer: {final_answer}

Decision rules — pick exactly ONE:

1. action="create":
   - Trigger when NO skill was loaded AND the task was solved with a
     reusable, non-trivial procedure (at least 2 tool calls).
   - You must output:
     * name: kebab-case, <=64 chars, e.g. "date-iso-normalize"
     * category: use "text-processing" unless clearly different
     * content: a complete SKILL.md document with YAML frontmatter
       (name, description starting with "Use when", version: 1.0.0,
       author: Hermess Demo, license: MIT, metadata.hermes.tags)
       and body sections: Overview, When to Use, Steps, Verification
       Checklist, Common Pitfalls.
     * The frontmatter `name` MUST equal the top-level `name` field.

2. action="patch":
   - Trigger when a skill WAS loaded BUT the execution trace shows
     steps, parameters, or cases the skill didn't mention (e.g. the
     skill covers dates but the task needed timezone handling).
   - You must output:
     * target_skill: name of the loaded skill to update
     * old_string: verbatim text from the skill body (must be unique
       in the file; copy at least one full line)
     * new_string: replacement text that adds the missing case
   - Prefer extending ONE section (e.g. "## Steps") rather than
     rewriting the whole file.

3. action="none":
   - The skill (if any) fully covered this task, or the task was too
     trivial to merit a skill.

Return a ReflectDecision JSON with the chosen action and all fields
required by that branch.
"""


def compact_execution_trace(messages, max_chars: int = 4000) -> str:
    """Summarize ReAct messages into a compact trace for reflection.

    Keeps tool calls and tool results; trims to ``max_chars``.
    """
    from langchain_core.messages import AIMessage, ToolMessage

    lines = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            for call in tool_calls:
                args = call.get("args", {})
                lines.append(f"[tool_call] {call.get('name')}({args})")
            if msg.content and not tool_calls:
                lines.append(f"[assistant] {msg.content[:400]}")
        elif isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            lines.append(f"[tool_result {msg.name}] {content[:300]}")

    trace = "\n".join(lines)
    if len(trace) > max_chars:
        trace = trace[:max_chars] + "\n...[truncated]"
    return trace or "(empty trace)"
