"""Deployment-mode resolution and managed .gitignore helpers for skills."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .errors import ValidationError

DEPLOYMENT_MODES = frozenset({"checked", "gitignored"})
_TRUST_DEFAULTS = {
    "high": "checked",
    "medium": "checked",
    "low": "gitignored",
}


def _normalize_deployment_mode(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value not in DEPLOYMENT_MODES:
        raise ValidationError(f"{field_name} must be one of {sorted(DEPLOYMENT_MODES)}: {value!r}")
    return value


def _source_type(source: object) -> str | None:
    if not isinstance(source, str):
        return None
    normalized = source.strip()
    if normalized == "local":
        return "local"
    if normalized.startswith("github:"):
        return "github"
    if normalized.startswith("git:"):
        return "git"
    if normalized.startswith("path:"):
        return "path"
    return None


def _recoverable_deployment_mode(
    mode: str,
    *,
    source: object,
    field_name: str,
    strict: bool,
) -> str:
    if _source_type(source) != "local" or mode != "gitignored":
        return mode
    if strict:
        raise ValidationError(
            f"{field_name} cannot be 'gitignored' when source is 'local'; local skills cannot be restored on a fresh clone, so use deployment_mode='checked' or publish the skill via path:, git:, or github:."
        )
    return "checked"


def deployment_mode_for_trust(trust: object) -> str:
    if isinstance(trust, str):
        return _TRUST_DEFAULTS.get(trust.strip(), "checked")
    return "checked"


def resolve_skill_deployment_mode(
    skill_entry: Mapping[str, Any] | None,
    defaults: Mapping[str, Any] | None = None,
) -> str:
    """Resolve a skill's effective deployment mode.

    Precedence matches skill-manifest-spec.md:
    1. skills.{slug}.deployment_mode
    2. defaults.deployment_mode
    3. trust-aware fallback from trust

    Recoverability override:
    - source=local always resolves to checked unless a per-skill override explicitly
      asks for gitignored, which is rejected because fresh-clone recovery would be
      impossible.
    """

    source = skill_entry.get("source") if isinstance(skill_entry, Mapping) else None

    if isinstance(skill_entry, Mapping):
        explicit = skill_entry.get("deployment_mode")
        if explicit is not None:
            return _recoverable_deployment_mode(
                _normalize_deployment_mode(
                    explicit,
                    field_name="skills.{slug}.deployment_mode",
                ),
                source=source,
                field_name="skills.{slug}.deployment_mode",
                strict=True,
            )

    if isinstance(defaults, Mapping):
        default_mode = defaults.get("deployment_mode")
        if default_mode is not None:
            return _recoverable_deployment_mode(
                _normalize_deployment_mode(
                    default_mode,
                    field_name="defaults.deployment_mode",
                ),
                source=source,
                field_name="defaults.deployment_mode",
                strict=False,
            )

    trust = skill_entry.get("trust") if isinstance(skill_entry, Mapping) else None
    return _recoverable_deployment_mode(
        deployment_mode_for_trust(trust),
        source=source,
        field_name="trust-derived deployment_mode",
        strict=False,
    )


class SkillGitignoreManager:
    """Manage the derived block in core/memory/skills/.gitignore."""

    start_marker = "# BEGIN ENGRAM MANAGED SKILL DEPLOYMENT"
    end_marker = "# END ENGRAM MANAGED SKILL DEPLOYMENT"
    note_line = (
        "# Derived from SKILLS.yaml effective deployment_mode. Edit the manifest, not this block."
    )

    def patterns_for_manifest(self, manifest_data: Mapping[str, Any] | None) -> list[str]:
        defaults_raw = manifest_data.get("defaults") if isinstance(manifest_data, Mapping) else None
        defaults = defaults_raw if isinstance(defaults_raw, Mapping) else None
        skills_raw = manifest_data.get("skills") if isinstance(manifest_data, Mapping) else None
        skills = skills_raw if isinstance(skills_raw, Mapping) else {}

        patterns: list[str] = []
        for slug, entry in sorted(skills.items()):
            if not isinstance(slug, str) or not isinstance(entry, Mapping):
                continue
            if entry.get("enabled", True) is False:
                continue
            if resolve_skill_deployment_mode(entry, defaults) == "gitignored":
                patterns.append(f"/{slug}/")
        return patterns

    def render(self, existing_text: str | None, patterns: Iterable[str]) -> str:
        unique_patterns = sorted(
            {pattern.strip() for pattern in patterns if pattern and pattern.strip()}
        )
        block_lines = [self.start_marker, self.note_line, *unique_patterns, self.end_marker]
        block = "\n".join(block_lines)

        if existing_text is None:
            return block + "\n"

        start_count = existing_text.count(self.start_marker)
        end_count = existing_text.count(self.end_marker)
        if start_count == 0 and end_count == 0:
            base = existing_text.rstrip("\n")
            if not base:
                return block + "\n"
            return f"{base}\n\n{block}\n"

        if start_count != 1 or end_count != 1:
            raise ValidationError(
                "core/memory/skills/.gitignore contains multiple or malformed Engram managed blocks"
            )

        text = existing_text if existing_text.endswith("\n") else f"{existing_text}\n"
        block_re = re.compile(
            rf"(?ms)^{re.escape(self.start_marker)}\n.*?^{re.escape(self.end_marker)}\n?"
        )
        if block_re.search(text) is None:
            raise ValidationError(
                "core/memory/skills/.gitignore contains malformed Engram managed block markers"
            )
        return block_re.sub(block + "\n", text, count=1)


__all__ = [
    "DEPLOYMENT_MODES",
    "SkillGitignoreManager",
    "deployment_mode_for_trust",
    "resolve_skill_deployment_mode",
]
