"""Inner ReAct tools for the text-normalization task.

Design notes
------------
- ``parse_date_string`` does NOT handle Chinese year/month/day markers
  perfectly (dateutil can't parse "2026年4月30日"); the LLM is expected to
  strip those via literal substring logic before calling. This gap is part
  of what lets Round 1's skill teach a concrete sequence.
- ``format_iso`` keeps ``tz_offset`` as a plain string parameter so the
  LLM can pass "+08:00" when the task involves a timezone. Round 1 won't
  mention it (no tz in input); Round 3's task forces its use, exposing
  the gap in the seed skill.
- ``submit_final`` is the terminator. The react agent should stop after
  calling it. If it doesn't, the outer node has a fallback.
"""

from __future__ import annotations

import re
from typing import Any

from dateutil import parser as _dateutil_parser
from langchain_core.tools import tool

_CN_DATE_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
_CN_TIME_RE = re.compile(r"(\d{1,2})[:点时](\d{1,2})?")
_CN_TZ_MAP = {
    "东八区": "+08:00",
    "UTC+8": "+08:00",
    "UTC+08": "+08:00",
    "GMT+8": "+08:00",
    "北京时间": "+08:00",
    "UTC": "+00:00",
}


@tool
def parse_date_string(text: str) -> dict[str, Any]:
    """Parse a natural-language date/time string.

    Tries two strategies:

    1. Regex match of Chinese-style "YYYY年M月D日" + optional "HH:MM" / "HH点MM".
    2. Fallback: ``dateutil.parser.parse`` for English-style inputs
       (e.g. "30 April 2026").

    Returns a dict with keys ``year``, ``month``, ``day`` and optionally
    ``hour``, ``minute``, ``tz_hint``. On failure returns ``{"error": "..."}``.
    """
    if not isinstance(text, str) or not text.strip():
        return {"error": "input must be a non-empty string."}

    result: dict[str, Any] = {}

    cn_date = _CN_DATE_RE.search(text)
    if cn_date:
        year, month, day = cn_date.groups()
        result["year"] = int(year)
        result["month"] = int(month)
        result["day"] = int(day)
        cn_time = _CN_TIME_RE.search(text)
        if cn_time:
            hour, minute = cn_time.groups()
            result["hour"] = int(hour)
            result["minute"] = int(minute) if minute else 0
        for cue, offset in _CN_TZ_MAP.items():
            if cue in text:
                result["tz_hint"] = offset
                break
        return result

    try:
        dt = _dateutil_parser.parse(text, fuzzy=True)
    except (ValueError, TypeError, OverflowError) as exc:
        return {"error": f"could not parse '{text}': {exc}"}

    result = {"year": dt.year, "month": dt.month, "day": dt.day}
    if dt.hour or dt.minute:
        result["hour"] = dt.hour
        result["minute"] = dt.minute
    if dt.tzinfo is not None:
        off = dt.utcoffset()
        if off is not None:
            total_minutes = int(off.total_seconds() // 60)
            sign = "+" if total_minutes >= 0 else "-"
            hh = abs(total_minutes) // 60
            mm = abs(total_minutes) % 60
            result["tz_hint"] = f"{sign}{hh:02d}:{mm:02d}"
    return result


@tool
def format_iso(
    year: int,
    month: int,
    day: int,
    hour: int | None = None,
    minute: int | None = None,
    tz_offset: str | None = None,
) -> str:
    """Format date parts into an ISO 8601 string.

    - Date-only: ``YYYY-MM-DD``
    - With time: ``YYYY-MM-DDTHH:MM``
    - With timezone: ``YYYY-MM-DDTHH:MM+HH:MM`` (tz_offset like ``"+08:00"``)

    The timezone offset is only included when ``tz_offset`` is supplied
    AND both ``hour`` and ``minute`` are also supplied.
    """
    try:
        base = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except (ValueError, TypeError) as exc:
        return f"[format_iso error] invalid date parts: {exc}"

    if hour is None or minute is None:
        return base

    try:
        time_part = f"T{int(hour):02d}:{int(minute):02d}"
    except (ValueError, TypeError) as exc:
        return f"[format_iso error] invalid time parts: {exc}"

    if tz_offset:
        if not re.match(r"^[+-]\d{2}:\d{2}$", tz_offset):
            return (
                f"[format_iso error] tz_offset '{tz_offset}' must look like "
                "'+HH:MM' or '-HH:MM'."
            )
        return f"{base}{time_part}{tz_offset}"

    return f"{base}{time_part}"


@tool
def submit_final(answer: str) -> str:
    """Submit the final normalized answer and terminate the ReAct loop.

    The returned value is the agent's final answer; the outer graph reads
    it from the tool message.
    """
    if not isinstance(answer, str) or not answer.strip():
        return "[submit_final error] answer must be a non-empty string."
    return answer.strip()


REACT_TOOLS = [parse_date_string, format_iso, submit_final]
