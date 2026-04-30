"""Filesystem-backed skill store — minimal clone of hermes-agent's skill CRUD.

Mirrors the core validation + atomic-write discipline of
``tools/skill_manager_tool.py`` and ``agent/skill_utils.py``:

- ``name`` / ``description`` / body size are hard-capped.
- Frontmatter must open with ``---`` and close with ``\\n---\\n``.
- Writes are atomic via ``tempfile + os.replace``.
- ``create`` refuses name collisions; ``patch`` requires a unique ``old_string``.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_CONTENT_CHARS = 100_000

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class SkillIndexEntry:
    name: str
    description: str
    path: str
    category: str | None = None


@dataclass
class LoadedSkill:
    name: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    path: str = ""
    category: str | None = None


# ── Frontmatter parsing ───────────────────────────────────────────────────


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter; returns (frontmatter_dict, body)."""
    if not content.startswith("---"):
        return {}, content

    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    yaml_content = content[3 : end_match.start() + 3]
    body = content[end_match.end() + 3 :]

    try:
        parsed = yaml.safe_load(yaml_content)
        if isinstance(parsed, dict):
            return parsed, body
    except yaml.YAMLError:
        pass
    return {}, body


# ── Validators ────────────────────────────────────────────────────────────


def _validate_name(name: str) -> str | None:
    if not name:
        return "name must not be empty."
    if len(name) > MAX_NAME_LENGTH:
        return f"name exceeds {MAX_NAME_LENGTH} characters."
    if not _NAME_RE.match(name):
        return (
            "name must be lowercase, start with a letter/digit, and contain only "
            "letters, digits, '.', '_' or '-'."
        )
    return None


def _validate_frontmatter(content: str) -> str | None:
    if not content.startswith("---"):
        return "SKILL.md must start with '---' on the first line."
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return "SKILL.md is missing the closing '---' of the frontmatter block."

    frontmatter, body = parse_frontmatter(content)
    if not isinstance(frontmatter, dict) or not frontmatter:
        return "frontmatter did not parse to a YAML mapping."
    if "name" not in frontmatter:
        return "frontmatter is missing the required 'name' field."
    if "description" not in frontmatter:
        return "frontmatter is missing the required 'description' field."
    desc = frontmatter.get("description", "")
    if not isinstance(desc, str):
        return "'description' must be a string."
    if len(desc) > MAX_DESCRIPTION_LENGTH:
        return f"'description' exceeds {MAX_DESCRIPTION_LENGTH} characters."
    if not body.strip():
        return "SKILL.md must have a non-empty body after the frontmatter."
    return None


def _validate_content_size(content: str) -> str | None:
    if len(content) > MAX_SKILL_CONTENT_CHARS:
        return f"SKILL.md exceeds {MAX_SKILL_CONTENT_CHARS} characters."
    return None


# ── Atomic write ──────────────────────────────────────────────────────────


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp_", dir=str(path.parent), suffix=".md"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ── Store ─────────────────────────────────────────────────────────────────


class SkillStore:
    """Flat, category-aware filesystem store: ``<root>/<category>/<name>/SKILL.md``."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- read paths ----------------------------------------------------

    def _iter_skill_files(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            if "SKILL.md" in filenames:
                yield Path(dirpath) / "SKILL.md"

    def _resolve_skill_dir(self, name: str, category: str | None) -> Path:
        if category:
            return self.root / category / name
        return self.root / name

    def _find(self, name: str) -> Path | None:
        for skill_md in self._iter_skill_files():
            try:
                content = skill_md.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, _ = parse_frontmatter(content)
            if fm.get("name") == name:
                return skill_md
        return None

    def list(self) -> list[SkillIndexEntry]:
        entries: list[SkillIndexEntry] = []
        for skill_md in sorted(self._iter_skill_files()):
            try:
                content = skill_md.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, _ = parse_frontmatter(content)
            name = fm.get("name")
            desc = fm.get("description", "")
            if not name:
                continue
            try:
                relative = skill_md.parent.relative_to(self.root)
                parts = relative.parts
                category = parts[0] if len(parts) > 1 else None
            except ValueError:
                category = None
            entries.append(
                SkillIndexEntry(
                    name=str(name),
                    description=str(desc),
                    path=str(skill_md),
                    category=category,
                )
            )
        return entries

    def view(self, name: str) -> LoadedSkill | None:
        skill_md = self._find(name)
        if skill_md is None:
            return None
        content = skill_md.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(content)
        try:
            relative = skill_md.parent.relative_to(self.root)
            parts = relative.parts
            category = parts[0] if len(parts) > 1 else None
        except ValueError:
            category = None
        return LoadedSkill(
            name=str(fm.get("name", name)),
            frontmatter=fm,
            body=body,
            path=str(skill_md),
            category=category,
        )

    # ---- write paths ---------------------------------------------------

    def create(
        self, name: str, content: str, category: str | None = None
    ) -> dict[str, Any]:
        err = _validate_name(name)
        if err:
            return {"status": "error", "error": err}
        err = _validate_frontmatter(content)
        if err:
            return {"status": "error", "error": err}
        err = _validate_content_size(content)
        if err:
            return {"status": "error", "error": err}

        # Ensure frontmatter.name matches supplied name
        fm, _ = parse_frontmatter(content)
        if fm.get("name") != name:
            return {
                "status": "error",
                "error": (
                    f"frontmatter name '{fm.get('name')}' does not match "
                    f"argument name '{name}'."
                ),
            }

        if self._find(name) is not None:
            return {
                "status": "error",
                "error": f"skill '{name}' already exists.",
            }

        skill_dir = self._resolve_skill_dir(name, category)
        skill_md = skill_dir / "SKILL.md"
        _atomic_write_text(skill_md, content)
        return {
            "status": "created",
            "path": str(skill_md),
            "category": category,
        }

    def patch(
        self, name: str, old_string: str, new_string: str
    ) -> dict[str, Any]:
        if not old_string:
            return {"status": "error", "error": "old_string must not be empty."}
        skill_md = self._find(name)
        if skill_md is None:
            return {"status": "error", "error": f"skill '{name}' not found."}

        original = skill_md.read_text(encoding="utf-8")
        hits = original.count(old_string)
        if hits == 0:
            return {
                "status": "error",
                "error": f"old_string did not match any text in '{name}'.",
            }
        if hits > 1:
            return {
                "status": "error",
                "error": (
                    f"old_string matched {hits} places in '{name}'; "
                    "it must be unique."
                ),
            }

        updated = original.replace(old_string, new_string, 1)
        err = _validate_content_size(updated)
        if err:
            return {"status": "error", "error": err}
        err = _validate_frontmatter(updated)
        if err:
            return {"status": "error", "error": err}

        _atomic_write_text(skill_md, updated)
        diff_lines = abs(
            updated.count("\n") - original.count("\n")
        ) + 1  # rough
        return {
            "status": "patched",
            "path": str(skill_md),
            "diff_lines": diff_lines,
        }
