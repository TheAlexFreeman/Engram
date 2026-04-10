"""Trigger-based skill routing for explicit skill dispatch."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .errors import ValidationError
from .frontmatter_utils import read_with_frontmatter
from .path_policy import validate_slug
from .skill_trigger import SKILL_TRIGGER_EVENTS, summarize_skill_trigger, validate_skill_trigger

_APPLICABLE_TOOL_EVENTS = frozenset({"pre-tool-use", "post-tool-use"})
_LIFECYCLE_EVENTS = frozenset({"session-start", "session-checkpoint", "session-end"})
_SUPPORTED_CONTEXT_KEYS = frozenset(
    {"tool_name", "project_id", "interval", "condition", "conditions", "query", "skill_slug"}
)
_TRUST_ORDER = {"high": 2, "medium": 1, "low": 0}


def _require_optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string when provided")
    return value.strip()


def _maybe_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _normalize_trigger_entries(trigger_value: object) -> list[dict[str, Any]]:
    validate_skill_trigger(trigger_value, context="trigger")
    items = trigger_value if isinstance(trigger_value, list) else [trigger_value]
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"event": item, "matcher": None, "priority": 0, "raw": item})
            continue
        matcher = item.get("matcher")
        normalized.append(
            {
                "event": item["event"],
                "matcher": dict(matcher) if isinstance(matcher, Mapping) else None,
                "priority": item.get("priority", 0),
                "raw": dict(item),
            }
        )
    return normalized


def _string_or_regex_matches(pattern: str, value: str) -> bool:
    if pattern == value:
        return True
    try:
        return re.fullmatch(pattern, value) is not None
    except re.error:
        return pattern == value


@dataclass(frozen=True, slots=True)
class RouteContext:
    tool_name: str | None = None
    project_id: str | None = None
    interval: str | None = None
    conditions: tuple[str, ...] = ()
    query: str | None = None
    skill_slug: str | None = None

    @classmethod
    def from_mapping(cls, context: Mapping[str, object] | None) -> "RouteContext":
        if context is None:
            return cls()
        unknown = sorted(set(context) - _SUPPORTED_CONTEXT_KEYS)
        if unknown:
            raise ValidationError(f"context contains unsupported keys: {', '.join(unknown)}")

        single_condition = _require_optional_string(
            context.get("condition"),
            field_name="context.condition",
        )
        raw_conditions = context.get("conditions")
        normalized_conditions: list[str] = []
        if raw_conditions is not None:
            if not isinstance(raw_conditions, list) or not raw_conditions:
                raise ValidationError("context.conditions must be a non-empty array when provided")
            for index, item in enumerate(raw_conditions):
                if not isinstance(item, str) or not item.strip():
                    raise ValidationError(f"context.conditions[{index}] must be a non-empty string")
                normalized_conditions.append(item.strip())
        if single_condition is not None:
            normalized_conditions.append(single_condition)

        skill_slug = _require_optional_string(
            context.get("skill_slug"),
            field_name="context.skill_slug",
        )
        if skill_slug is not None:
            skill_slug = validate_slug(skill_slug, field_name="context.skill_slug")

        return cls(
            tool_name=_require_optional_string(
                context.get("tool_name"), field_name="context.tool_name"
            ),
            project_id=_require_optional_string(
                context.get("project_id"), field_name="context.project_id"
            ),
            interval=_require_optional_string(
                context.get("interval"), field_name="context.interval"
            ),
            conditions=tuple(sorted(set(normalized_conditions))),
            query=_require_optional_string(context.get("query"), field_name="context.query"),
            skill_slug=skill_slug,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "project_id": self.project_id,
            "interval": self.interval,
            "conditions": list(self.conditions),
            "query": self.query,
            "skill_slug": self.skill_slug,
        }


@dataclass(frozen=True, slots=True)
class SkillRecord:
    slug: str
    title: str
    description: str | None
    source: str
    trust: str | None
    enabled: bool
    archived: bool
    path: str
    trigger: object | None
    trigger_source: str | None
    trigger_summary: str | None


@dataclass(frozen=True, slots=True)
class SkillRouteMatch:
    slug: str
    title: str
    description: str | None
    source: str
    trust: str | None
    enabled: bool
    archived: bool
    path: str
    dispatch_tier: str
    match_reason: str
    priority: int | None
    catalog_score: int | None
    matcher_applied: bool
    trigger_source: str | None
    trigger: object | None
    trigger_summary: str | None
    _sort_key: tuple[int, int, int, int, str]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "trust": self.trust,
            "enabled": self.enabled,
            "archived": self.archived,
            "path": self.path,
            "dispatch_tier": self.dispatch_tier,
            "match_reason": self.match_reason,
            "matcher_applied": self.matcher_applied,
        }
        if self.priority is not None:
            payload["priority"] = self.priority
        if self.catalog_score is not None:
            payload["catalog_score"] = self.catalog_score
        if self.trigger_source is not None:
            payload["trigger_source"] = self.trigger_source
        if self.trigger is not None:
            payload["trigger"] = self.trigger
        if self.trigger_summary is not None:
            payload["trigger_summary"] = self.trigger_summary
        return payload


class TriggerRouter:
    """Resolve skill candidates for a trigger event and optional routing context."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.skills_dir = self.repo_root / "core" / "memory" / "skills"

    def route(
        self,
        event: str,
        context: Mapping[str, object] | None = None,
        *,
        include_catalog_fallback: bool = True,
        include_archived: bool = False,
        include_disabled: bool = False,
        max_results: int = 20,
    ) -> dict[str, Any]:
        if event not in SKILL_TRIGGER_EVENTS:
            raise ValidationError(f"event must be one of {sorted(SKILL_TRIGGER_EVENTS)}")
        if max_results < 0:
            raise ValidationError("max_results must be >= 0")
        if not self.skills_dir.is_dir():
            raise ValidationError(f"Skills directory not found: {self.skills_dir}")

        route_context = RouteContext.from_mapping(context)
        records = self._load_skill_records(include_archived=include_archived)

        matches: list[SkillRouteMatch] = []
        explicit_slugs: set[str] = set()
        for record in records:
            if not include_disabled and not record.enabled:
                continue
            explicit_match = self._match_explicit(record, event=event, context=route_context)
            if explicit_match is None:
                continue
            matches.append(explicit_match)
            explicit_slugs.add(record.slug)

        if include_catalog_fallback and (route_context.query or route_context.skill_slug):
            for record in records:
                if not include_disabled and not record.enabled:
                    continue
                if record.slug in explicit_slugs:
                    continue
                catalog_match = self._match_catalog(record, context=route_context)
                if catalog_match is not None:
                    matches.append(catalog_match)

        matches.sort(key=lambda item: item._sort_key)
        total_count = len(matches)
        if max_results > 0:
            matches = matches[:max_results]

        dispatch_mode = "all" if event in _LIFECYCLE_EVENTS else "first-match"
        return {
            "event": event,
            "context": route_context.to_dict(),
            "matches": [match.to_dict() for match in matches],
            "total_count": total_count,
            "dispatch_policy": {
                "mode": dispatch_mode,
                "include_catalog_fallback": include_catalog_fallback,
                "include_archived": include_archived,
                "include_disabled": include_disabled,
                "selected_count": len(matches) if dispatch_mode == "all" else min(1, len(matches)),
            },
        }

    def _load_skill_records(self, *, include_archived: bool) -> list[SkillRecord]:
        manifest_data = self._read_manifest()
        manifest_skills_raw = manifest_data.get("skills")
        manifest_skills = manifest_skills_raw if isinstance(manifest_skills_raw, dict) else {}

        records: list[SkillRecord] = []
        for child in sorted(self.skills_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            manifest_entry = manifest_skills.get(child.name)
            records.append(
                self._build_skill_record(
                    skill_md,
                    slug=child.name,
                    archived=False,
                    manifest_entry=manifest_entry,
                )
            )

        if include_archived:
            archive_dir = self.skills_dir / "_archive"
            if archive_dir.is_dir():
                for child in sorted(archive_dir.iterdir()):
                    if not child.is_dir():
                        continue
                    skill_md = child / "SKILL.md"
                    if not skill_md.is_file():
                        continue
                    records.append(
                        self._build_skill_record(
                            skill_md,
                            slug=child.name,
                            archived=True,
                            manifest_entry=None,
                        )
                    )
        return records

    def _read_manifest(self) -> dict[str, Any]:
        manifest_path = self.skills_dir / "SKILLS.yaml"
        if not manifest_path.is_file():
            return {}
        with manifest_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data if isinstance(data, dict) else {}

    def _build_skill_record(
        self,
        skill_md: Path,
        *,
        slug: str,
        archived: bool,
        manifest_entry: object,
    ) -> SkillRecord:
        frontmatter, _ = read_with_frontmatter(skill_md)
        manifest_mapping = manifest_entry if isinstance(manifest_entry, Mapping) else {}

        trigger_source: str | None = None
        trigger_value: object | None = None
        if "trigger" in frontmatter:
            trigger_source = "frontmatter"
            trigger_value = frontmatter["trigger"]
        elif "trigger" in manifest_mapping:
            trigger_source = "manifest"
            trigger_value = manifest_mapping["trigger"]
        if trigger_value is not None:
            validate_skill_trigger(trigger_value, context=f"skill trigger for {skill_md}")

        return SkillRecord(
            slug=slug,
            title=str(frontmatter.get("name") or slug),
            description=(
                str(frontmatter.get("description"))
                if frontmatter.get("description") is not None
                else _maybe_string(manifest_mapping.get("description"))
            ),
            source=str(manifest_mapping.get("source") or "local"),
            trust=(
                str(frontmatter.get("trust"))
                if frontmatter.get("trust") is not None
                else _maybe_string(manifest_mapping.get("trust"))
            ),
            enabled=bool(manifest_mapping.get("enabled", True)),
            archived=archived,
            path=skill_md.relative_to(self.repo_root).as_posix(),
            trigger=trigger_value,
            trigger_source=trigger_source,
            trigger_summary=summarize_skill_trigger(trigger_value)
            if trigger_value is not None
            else None,
        )

    def _match_explicit(
        self,
        record: SkillRecord,
        *,
        event: str,
        context: RouteContext,
    ) -> SkillRouteMatch | None:
        if record.trigger is None:
            return None
        if context.skill_slug is not None and record.slug != context.skill_slug:
            return None

        best_match: SkillRouteMatch | None = None
        for entry in _normalize_trigger_entries(record.trigger):
            if entry["event"] != event:
                continue
            matches, details = self._matcher_matches(
                event=event,
                matcher=entry["matcher"],
                context=context,
            )
            if not matches:
                continue
            matcher_applied = bool(details)
            reason = f"trigger {event} matched"
            if details:
                reason += f" ({', '.join(details)})"
            candidate = SkillRouteMatch(
                slug=record.slug,
                title=record.title,
                description=record.description,
                source=record.source,
                trust=record.trust,
                enabled=record.enabled,
                archived=record.archived,
                path=record.path,
                dispatch_tier="explicit-trigger",
                match_reason=reason,
                priority=int(entry["priority"]),
                catalog_score=None,
                matcher_applied=matcher_applied,
                trigger_source=record.trigger_source,
                trigger=entry["raw"],
                trigger_summary=record.trigger_summary,
                _sort_key=self._sort_key(
                    tier_rank=2,
                    matcher_rank=1 if matcher_applied else 0,
                    priority=int(entry["priority"]),
                    trust=record.trust,
                    slug=record.slug,
                ),
            )
            if best_match is None or candidate._sort_key < best_match._sort_key:
                best_match = candidate
        return best_match

    def _match_catalog(
        self,
        record: SkillRecord,
        *,
        context: RouteContext,
    ) -> SkillRouteMatch | None:
        if record.trigger is not None:
            return None
        score, reason = self._catalog_score(record, context=context)
        if score <= 0:
            return None
        return SkillRouteMatch(
            slug=record.slug,
            title=record.title,
            description=record.description,
            source=record.source,
            trust=record.trust,
            enabled=record.enabled,
            archived=record.archived,
            path=record.path,
            dispatch_tier="catalog-match",
            match_reason=reason,
            priority=None,
            catalog_score=score,
            matcher_applied=False,
            trigger_source=None,
            trigger=None,
            trigger_summary=None,
            _sort_key=self._sort_key(
                tier_rank=1,
                matcher_rank=0,
                priority=score,
                trust=record.trust,
                slug=record.slug,
            ),
        )

    def _matcher_matches(
        self,
        *,
        event: str,
        matcher: Mapping[str, object] | None,
        context: RouteContext,
    ) -> tuple[bool, list[str]]:
        if not matcher:
            return True, []
        details: list[str] = []

        tool_name = matcher.get("tool_name")
        if isinstance(tool_name, str) and event in _APPLICABLE_TOOL_EVENTS:
            if context.tool_name is None or not _string_or_regex_matches(
                tool_name, context.tool_name
            ):
                return False, []
            details.append(f"tool_name={tool_name}")

        project_id = matcher.get("project_id")
        if isinstance(project_id, str) and event == "project-active":
            if context.project_id != project_id:
                return False, []
            details.append(f"project_id={project_id}")

        condition = matcher.get("condition")
        if isinstance(condition, str):
            if condition not in context.conditions:
                return False, []
            details.append(f"condition={condition}")

        interval = matcher.get("interval")
        if isinstance(interval, str) and event == "periodic":
            if context.interval != interval:
                return False, []
            details.append(f"interval={interval}")

        return True, details

    def _catalog_score(self, record: SkillRecord, *, context: RouteContext) -> tuple[int, str]:
        score = 0
        reasons: list[str] = []

        if context.skill_slug is not None:
            if record.slug != context.skill_slug:
                return 0, ""
            score += 300
            reasons.append(f"slug={context.skill_slug}")

        query = context.query
        if query is not None:
            lowered_query = query.lower()
            slug_lower = record.slug.lower()
            title_lower = record.title.lower()
            description_lower = (record.description or "").lower()

            if lowered_query == slug_lower:
                score += 250
                reasons.append("query exact slug")
            elif lowered_query in slug_lower:
                score += 180
                reasons.append("query in slug")

            if lowered_query == title_lower:
                score += 220
                reasons.append("query exact title")
            elif lowered_query in title_lower:
                score += 160
                reasons.append("query in title")

            if description_lower and lowered_query in description_lower:
                score += 120
                reasons.append("query in description")

            token_hits = 0
            if lowered_query:
                combined = f"{slug_lower} {title_lower} {description_lower}"
                for token in re.split(r"[^a-z0-9]+", lowered_query):
                    if token and token in combined:
                        token_hits += 1
                if token_hits:
                    score += token_hits * 10
                    reasons.append(f"token_overlap={token_hits}")

        if score <= 0:
            return 0, ""
        return score, f"catalog fallback matched ({', '.join(reasons)})"

    def _sort_key(
        self,
        *,
        tier_rank: int,
        matcher_rank: int,
        priority: int,
        trust: str | None,
        slug: str,
    ) -> tuple[int, int, int, int, str]:
        trust_rank = _TRUST_ORDER.get((trust or "").lower(), -1)
        return (-tier_rank, -matcher_rank, -priority, -trust_rank, slug)


__all__ = ["RouteContext", "SkillRouteMatch", "SkillRecord", "TriggerRouter"]
