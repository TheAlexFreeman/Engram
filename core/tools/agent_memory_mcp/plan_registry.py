"""Tool registry and policy enforcement helpers.

Extracted from plan_utils to keep that module focused on plan/phase schema
logic while tool-registry CRUD, summary generation, and policy evaluation
live here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

from .errors import ValidationError
from .path_policy import validate_slug

if TYPE_CHECKING:
    from .plan_utils import PlanBudget, PlanPhase

# ── Constants ────────────────────────────────────────────────────────────────

COST_TIERS: frozenset[str] = frozenset({"free", "low", "medium", "high"})

_CONTENT_PREFIXES = ("core",)

_RATE_LIMIT_PERIODS = {"minute": 60, "hour": 3600, "day": 86400}
_RATE_LIMIT_RE = re.compile(r"^(\d+)\s*/\s*(minute|hour|day|session)$", re.IGNORECASE)


# ── ToolDefinition ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class ToolDefinition:
    """Metadata and policy for an external tool.

    Stored in ``memory/skills/tool-registry/<provider>.yaml``.  Engram does not
    execute these tools; it stores metadata so agents and orchestrators can
    respect constraints before invoking them.
    """

    name: str
    description: str
    provider: str
    schema: dict[str, Any] | None = None
    approval_required: bool = False
    cost_tier: str = "free"
    rate_limit: str | None = None
    timeout_seconds: int = 30
    tags: list[str] = field(default_factory=list)
    notes: str | None = None

    def __post_init__(self) -> None:
        self.name = validate_slug(self.name, field_name="tool name")
        self.provider = validate_slug(self.provider, field_name="provider")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValidationError("tool description must be a non-empty string")
        self.description = self.description.strip()
        if self.cost_tier not in COST_TIERS:
            raise ValidationError(
                f"cost_tier must be one of {sorted(COST_TIERS)}: {self.cost_tier!r}"
            )
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds < 1:
            raise ValidationError("timeout_seconds must be an integer >= 1")
        if self.schema is not None and not isinstance(self.schema, dict):
            raise ValidationError("schema must be a dict or null")
        validated_tags: list[str] = []
        for tag in self.tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ValidationError("tags must be non-empty strings")
            validated_tags.append(tag.strip())
        self.tags = validated_tags
        if self.notes is not None:
            self.notes = str(self.notes).strip() or None
        if self.rate_limit is not None:
            self.rate_limit = str(self.rate_limit).strip() or None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "approval_required": self.approval_required,
            "cost_tier": self.cost_tier,
            "timeout_seconds": self.timeout_seconds,
        }
        if self.schema is not None:
            payload["schema"] = self.schema
        if self.rate_limit is not None:
            payload["rate_limit"] = self.rate_limit
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.notes is not None:
            payload["notes"] = self.notes
        return payload


# ── Tool Registry helpers ────────────────────────────────────────────────────


def registry_file_path(provider: str) -> str:
    """Content-relative path to a provider's YAML registry file."""
    validated = validate_slug(provider, field_name="provider")
    return f"memory/skills/tool-registry/{validated}.yaml"


def registry_summary_path() -> str:
    """Content-relative path to the tool registry SUMMARY.md."""
    return "memory/skills/tool-registry/SUMMARY.md"


def _find_registry_root(root: Path) -> Path:
    """Resolve the absolute path to memory/skills/tool-registry/, tolerating root variants."""
    direct = root / "memory/skills/tool-registry"
    if direct.exists():
        return direct
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix / "memory/skills/tool-registry"
        if candidate.exists():
            return candidate
    return direct


def _coerce_tool(raw: Any, provider: str) -> ToolDefinition:
    if not isinstance(raw, dict):
        raise ValidationError(f"tool entry must be a mapping, got {type(raw).__name__}")
    tags_raw = raw.get("tags") or []
    if not isinstance(tags_raw, list):
        tags_raw = [str(tags_raw)]
    schema = raw.get("schema")
    if schema is not None and not isinstance(schema, dict):
        schema = None
    try:
        timeout = int(raw.get("timeout_seconds", 30))
    except (TypeError, ValueError):
        timeout = 30
    return ToolDefinition(
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        provider=provider,
        schema=schema,
        approval_required=bool(raw.get("approval_required", False)),
        cost_tier=str(raw.get("cost_tier", "free")),
        rate_limit=str(raw["rate_limit"]) if raw.get("rate_limit") else None,
        timeout_seconds=timeout,
        tags=[str(t) for t in tags_raw],
        notes=str(raw["notes"]) if raw.get("notes") else None,
    )


def load_registry(root: Path, provider: str) -> list[ToolDefinition]:
    """Load all tool definitions for a provider. Returns [] if the file doesn't exist."""
    reg_root = _find_registry_root(root)
    abs_path = reg_root / f"{validate_slug(provider, field_name='provider')}.yaml"
    if not abs_path.exists():
        return []
    try:
        raw = yaml.safe_load(abs_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML registry file {abs_path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        return []
    result: list[ToolDefinition] = []
    for entry in raw.get("tools") or []:
        result.append(_coerce_tool(entry, provider))
    return result


def save_registry(root: Path, provider: str, tools: list[ToolDefinition]) -> None:
    """Persist tool definitions for a provider to its YAML file."""
    from .plan_utils import _PlanDumper

    reg_root = _find_registry_root(root)
    abs_path = reg_root / f"{validate_slug(provider, field_name='provider')}.yaml"
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "provider": provider,
        "tools": [t.to_dict() for t in tools],
    }
    text = yaml.dump(payload, Dumper=_PlanDumper, sort_keys=False, allow_unicode=False, width=88)
    abs_path.write_text(text, encoding="utf-8")


def _all_registry_tools(root: Path) -> list[ToolDefinition]:
    """Load all tool definitions from every provider YAML in the registry."""
    reg_root = _find_registry_root(root)
    if not reg_root.exists():
        return []
    tools: list[ToolDefinition] = []
    for yaml_file in sorted(reg_root.glob("*.yaml")):
        try:
            tools.extend(load_registry(root, yaml_file.stem))
        except Exception:  # noqa: BLE001
            continue
    return tools


def regenerate_registry_summary(root: Path) -> None:
    """Rewrite memory/skills/tool-registry/SUMMARY.md from all registered tools."""
    all_tools = _all_registry_tools(root)
    reg_root = _find_registry_root(root)
    reg_root.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Tool Registry",
        "",
        "External tool definitions and policies.",
        "Managed by `memory_register_tool`. Query with `memory_get_tool_policy`.",
        "",
    ]
    if not all_tools:
        lines.append("_No tools registered yet._")
    else:
        by_provider: dict[str, list[ToolDefinition]] = {}
        for t in sorted(all_tools, key=lambda t: (t.provider, t.name)):
            by_provider.setdefault(t.provider, []).append(t)
        for prov, ptools in sorted(by_provider.items()):
            lines += [
                f"## {prov}",
                "",
                "| Tool | Description | Approval | Cost | Timeout | Tags |",
                "|---|---|---|---|---|---|",
            ]
            for t in ptools:
                tags_str = ", ".join(t.tags) if t.tags else "—"
                approval = "yes" if t.approval_required else "no"
                lines.append(
                    f"| {t.name} | {t.description} | {approval} | {t.cost_tier}"
                    f" | {t.timeout_seconds}s | {tags_str} |"
                )
            lines.append("")
    summary_abs = reg_root / "SUMMARY.md"
    summary_abs.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _command_matches_tool(target: str, tool_name: str) -> bool:
    """Return True if a test postcondition target string likely invokes the named tool.

    Strategy:
    1. Direct substring match (slug or space-normalized form).
    2. Extract non-flag, non-path tokens from the target; try all prefix-length
       combinations as hyphenated slugs against the tool name.
    3. If the first segment of the tool name (before the first hyphen-verb) appears
       as a token, treat it as a match (e.g. "pytest" in target → "pytest-run").
    """
    if tool_name in target:
        return True
    if tool_name.replace("-", " ") in target:
        return True
    tokens = [
        t
        for t in target.lower().split()
        if not t.startswith("-") and "/" not in t and "\\" not in t
    ]
    for n in range(len(tokens), 0, -1):
        candidate = "-".join(tokens[:n])
        if candidate == tool_name:
            return True
    first_segment = tool_name.split("-")[0]
    return first_segment in tokens


def _resolve_tool_policies(phase: PlanPhase, root: Path) -> list[dict[str, Any]]:
    """Return tool policy dicts for test postconditions that match registered tools.

    Best-effort: unregistered tools are silently skipped, yielding an empty list.
    """
    test_targets = [pc.target for pc in phase.postconditions if pc.type == "test" and pc.target]
    if not test_targets:
        return []
    all_tools = _all_registry_tools(root)
    if not all_tools:
        return []
    policies: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in sorted(all_tools, key=lambda t: t.name):
        if tool.name in seen:
            continue
        for target in test_targets:
            if _command_matches_tool(target, tool.name):
                policies.append(
                    {
                        "tool_name": tool.name,
                        "approval_required": tool.approval_required,
                        "cost_tier": tool.cost_tier,
                        "timeout_seconds": tool.timeout_seconds,
                    }
                )
                seen.add(tool.name)
                break
    return policies


# ── Policy enforcement ───────────────────────────────────────────────────────


@dataclass(slots=True)
class PolicyCheckResult:
    """Result of a tool policy evaluation."""

    allowed: bool
    reason: str
    tool_name: str = ""
    provider: str = ""
    required_action: str | None = None
    violation_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "tool_name": self.tool_name,
            "provider": self.provider,
            "required_action": self.required_action,
            "violation_type": self.violation_type,
            "details": self.details,
        }


def _parse_rate_limit(rate_limit: str) -> tuple[int, str] | None:
    """Parse ``'N/period'`` into ``(count, period)``.  Returns ``None`` if unparseable."""
    m = _RATE_LIMIT_RE.match(rate_limit.strip())
    if m is None:
        return None
    return int(m.group(1)), m.group(2).lower()


def _count_recent_invocations(
    root: Path,
    tool_name: str,
    period: str,
    *,
    session_id: str | None = None,
) -> int:
    """Count recent trace spans matching *tool_name* within the given window.

    Scans ``tool_call`` spans in reverse chronological order and stops once the
    time window is exceeded.
    """
    from .plan_trace import trace_file_path

    now = datetime.now(timezone.utc)

    if period == "session":
        if not session_id:
            return 0
        trace_path = root / trace_file_path(session_id)
        if not trace_path.exists():
            return 0
        count = 0
        try:
            for raw_line in trace_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    span = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    isinstance(span, dict)
                    and span.get("span_type") == "tool_call"
                    and span.get("name") == tool_name
                ):
                    count += 1
        except OSError:
            pass
        return count

    window_seconds = _RATE_LIMIT_PERIODS.get(period)
    if window_seconds is None:
        return 0
    cutoff = now.timestamp() - window_seconds

    activity_root = root / "memory" / "activity"
    if not activity_root.is_dir():
        return 0

    count = 0
    for trace_file in sorted(activity_root.rglob("*.traces.jsonl"), reverse=True):
        try:
            lines = trace_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw_line in reversed(lines):
            line = raw_line.strip()
            if not line:
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(span, dict):
                continue
            ts_str = span.get("timestamp")
            if not isinstance(ts_str, str):
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            except (ValueError, AttributeError):
                continue
            if ts < cutoff:
                return count
            if span.get("span_type") == "tool_call" and span.get("name") == tool_name:
                count += 1
    return count


def check_tool_policy(
    root: Path,
    tool_name: str,
    provider: str,
    *,
    session_id: str | None = None,
    plan_budget: PlanBudget | None = None,
) -> PolicyCheckResult:
    """Evaluate tool policy and return whether invocation should proceed.

    Pure read — does not create approvals or emit traces.  Callers are
    responsible for acting on the result (creating approvals, emitting
    violation traces, etc.).
    """
    import os

    from .plan_approvals import load_approval
    from .plan_utils import (
        ChangeSpec,
        PlanDocument,
        PlanPhase,
        PlanPurpose,
        budget_status,
    )

    tools = load_registry(root, provider)
    tool_def: ToolDefinition | None = None
    for t in tools:
        if t.name == tool_name:
            tool_def = t
            break
    if tool_def is None:
        return PolicyCheckResult(
            allowed=True,
            reason="no_policy",
            tool_name=tool_name,
            provider=provider,
        )

    if os.environ.get("ENGRAM_EVAL_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return PolicyCheckResult(
            allowed=True,
            reason="eval_bypass",
            tool_name=tool_name,
            provider=provider,
        )

    if tool_def.approval_required:
        approval = load_approval(root, f"tool-{provider}", tool_name)
        if approval is None or approval.status not in {"approved", "pending"}:
            return PolicyCheckResult(
                allowed=False,
                reason=f"Tool '{tool_name}' requires approval before use",
                tool_name=tool_name,
                provider=provider,
                required_action="approval",
                violation_type="approval_required",
                details={"provider": provider},
            )
        if approval.status == "pending":
            return PolicyCheckResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is awaiting approval",
                tool_name=tool_name,
                provider=provider,
                required_action="approval",
                violation_type="approval_required",
                details={"approval_status": "pending", "expires": approval.expires},
            )

    if tool_def.rate_limit:
        parsed = _parse_rate_limit(tool_def.rate_limit)
        if parsed is not None:
            limit, period = parsed
            current = _count_recent_invocations(root, tool_name, period, session_id=session_id)
            if current >= limit:
                return PolicyCheckResult(
                    allowed=False,
                    reason=(
                        f"Rate limit exceeded for '{tool_name}': {current}/{limit} per {period}"
                    ),
                    tool_name=tool_name,
                    provider=provider,
                    required_action="rate_limit_wait",
                    violation_type="rate_limit_exceeded",
                    details={
                        "rate_limit": tool_def.rate_limit,
                        "current_count": current,
                        "limit": limit,
                        "period": period,
                    },
                )

    violation_type: str | None = None
    details: dict[str, Any] = {}
    if tool_def.cost_tier == "high" and plan_budget is not None:
        bs = budget_status(
            PlanDocument(
                id="policy-check",
                project="policy-check",
                created="2000-01-01",
                origin_session="memory/activity/2000/01/01/chat-001",
                status="active",
                purpose=PlanPurpose(summary="policy check stub", context="policy check stub"),
                phases=[
                    PlanPhase(
                        id="stub",
                        title="stub",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/stub.md",
                                action="create",
                                description="stub",
                            )
                        ],
                    )
                ],
                budget=plan_budget,
            )
        )
        if bs is not None and bs.get("over_budget"):
            violation_type = "cost_warning"
            details = {"cost_tier": "high", "budget_status": bs}

    return PolicyCheckResult(
        allowed=True,
        reason="policy_passed",
        tool_name=tool_name,
        provider=provider,
        violation_type=violation_type,
        details=details,
    )
