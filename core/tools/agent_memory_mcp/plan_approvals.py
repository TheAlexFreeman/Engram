"""Approval workflow schema and helpers for structured YAML plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .errors import ValidationError
from .path_policy import validate_slug

APPROVAL_STATUSES: frozenset[str] = frozenset({"pending", "approved", "rejected", "expired"})
APPROVAL_RESOLUTIONS: frozenset[str] = frozenset({"approve", "reject"})


def approval_filename(plan_id: str, phase_id: str) -> str:
    """Return the filename (not path) for an approval document: {plan_id}--{phase_id}.yaml."""
    p = validate_slug(plan_id, field_name="plan_id")
    ph = validate_slug(phase_id, field_name="phase_id")
    return f"{p}--{ph}.yaml"


def approvals_summary_path() -> str:
    """Content-relative path to the approvals queue SUMMARY.md."""
    return "memory/working/approvals/SUMMARY.md"


def _find_approvals_root(root: Path) -> Path:
    """Resolve the absolute path to memory/working/approvals/, tolerating root variants."""
    from .plan_utils import _CONTENT_PREFIXES

    direct = root / "memory/working/approvals"
    if direct.exists():
        return direct
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix / "memory/working/approvals"
        if candidate.exists():
            return candidate
    return direct


@dataclass(slots=True)
class ApprovalDocument:
    """A pending or resolved human-in-the-loop approval request for a plan phase.

    Stored in ``memory/working/approvals/pending/{plan_id}--{phase_id}.yaml``
    while awaiting review, and moved to ``resolved/`` after resolution or expiry.
    """

    plan_id: str
    phase_id: str
    project_id: str
    status: str  # pending | approved | rejected | expired
    requested: str  # ISO-8601 UTC timestamp
    expires: str  # ISO-8601 UTC timestamp
    context: dict[str, Any] = field(default_factory=dict)
    resolution: str | None = None  # "approve" | "reject"
    reviewer: str | None = None
    resolved_at: str | None = None
    comment: str | None = None

    def __post_init__(self) -> None:
        self.plan_id = validate_slug(self.plan_id, field_name="plan_id")
        self.phase_id = validate_slug(self.phase_id, field_name="phase_id")
        self.project_id = validate_slug(self.project_id, field_name="project_id")
        if self.status not in APPROVAL_STATUSES:
            raise ValidationError(
                f"approval status must be one of {sorted(APPROVAL_STATUSES)}: {self.status!r}"
            )
        if not isinstance(self.requested, str) or not self.requested.strip():
            raise ValidationError("requested must be a non-empty ISO-8601 timestamp string")
        if not isinstance(self.expires, str) or not self.expires.strip():
            raise ValidationError("expires must be a non-empty ISO-8601 timestamp string")
        if self.resolution is not None and self.resolution not in APPROVAL_RESOLUTIONS:
            raise ValidationError(
                f"resolution must be one of {sorted(APPROVAL_RESOLUTIONS)}: {self.resolution!r}"
            )
        if not isinstance(self.context, dict):
            self.context = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "phase_id": self.phase_id,
            "project_id": self.project_id,
            "status": self.status,
            "requested": self.requested,
            "expires": self.expires,
            "context": self.context,
            "resolution": self.resolution,
            "reviewer": self.reviewer,
            "resolved_at": self.resolved_at,
            "comment": self.comment,
        }


def _coerce_approval(raw: dict[str, Any]) -> ApprovalDocument:
    """Coerce a raw YAML mapping into an ApprovalDocument."""
    context = raw.get("context")
    if not isinstance(context, dict):
        context = {}
    return ApprovalDocument(
        plan_id=str(raw.get("plan_id", "")),
        phase_id=str(raw.get("phase_id", "")),
        project_id=str(raw.get("project_id", "")),
        status=str(raw.get("status", "pending")),
        requested=str(raw.get("requested", "")),
        expires=str(raw.get("expires", "")),
        context=context,
        resolution=str(raw["resolution"]) if raw.get("resolution") else None,
        reviewer=str(raw["reviewer"]) if raw.get("reviewer") else None,
        resolved_at=str(raw["resolved_at"]) if raw.get("resolved_at") else None,
        comment=str(raw["comment"]) if raw.get("comment") else None,
    )


def _check_approval_expiry(approval: ApprovalDocument, root: Path | None = None) -> bool:
    """Check whether a pending approval has passed its expiry deadline.

    Mutates *approval* in memory by updating its status to ``"expired"`` when
    the deadline has passed. This helper is intentionally side-effect free with
    respect to repository state so read paths can safely inspect approvals
    without dirtying the worktree.
    """
    if approval.status != "pending":
        return False
    try:
        expires_dt = datetime.fromisoformat(approval.expires.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now <= expires_dt:
            return False
    except (ValueError, AttributeError):
        return False

    approval.status = "expired"
    return True


def materialize_expired_approval(root: Path, approval: ApprovalDocument) -> bool:
    """Persist an expired approval into the resolved queue.

    Returns ``True`` when the approval is expired and the resolved/pending queue
    transition was materialized (or refreshed) on disk, ``False`` otherwise.
    Callers are responsible for staging and committing the resulting file
    changes alongside any related plan updates.
    """
    if approval.status == "pending" and not _check_approval_expiry(approval):
        return False
    if approval.status != "expired":
        return False

    approvals_root = _find_approvals_root(root)
    filename = approval_filename(approval.plan_id, approval.phase_id)
    pending_path = approvals_root / "pending" / filename
    save_approval(root, approval)
    if pending_path.exists():
        pending_path.unlink()
    return True


def load_approval(root: Path, plan_id: str, phase_id: str) -> ApprovalDocument | None:
    """Load an approval document for a plan/phase pair.

    Checks ``pending/`` first, then ``resolved/``.  If the document is pending
    and past its expiry deadline, returns the document with an in-memory
    ``"expired"`` status while leaving the on-disk queue untouched. Returns
    ``None`` if no approval document exists.
    """
    approvals_root = _find_approvals_root(root)
    filename = approval_filename(plan_id, phase_id)

    pending_path = approvals_root / "pending" / filename
    if pending_path.exists():
        try:
            raw = yaml.safe_load(pending_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValidationError(f"Invalid approval YAML {filename}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValidationError(f"Approval file must be a mapping: {filename}")
        approval = _coerce_approval(raw)
        _check_approval_expiry(approval, root)
        return approval

    resolved_path = approvals_root / "resolved" / filename
    if resolved_path.exists():
        try:
            raw = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValidationError(f"Invalid approval YAML {filename}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValidationError(f"Approval file must be a mapping: {filename}")
        return _coerce_approval(raw)

    return None


def save_approval(root: Path, approval: ApprovalDocument) -> Path:
    """Persist an approval document to the correct subdirectory based on status.

    Pending approvals go to ``pending/``; all others go to ``resolved/``.
    Returns the absolute path where the document was saved.
    """
    from .plan_utils import _PlanDumper

    approvals_root = _find_approvals_root(root)
    filename = approval_filename(approval.plan_id, approval.phase_id)

    if approval.status == "pending":
        target_dir = approvals_root / "pending"
    else:
        target_dir = approvals_root / "resolved"

    target_dir.mkdir(parents=True, exist_ok=True)
    abs_path = target_dir / filename
    text = yaml.dump(
        approval.to_dict(),
        Dumper=_PlanDumper,
        sort_keys=False,
        allow_unicode=False,
        width=88,
    )
    abs_path.write_text(text, encoding="utf-8")
    return abs_path


def list_approval_documents(
    root: Path,
    *,
    include_resolved: bool = False,
) -> list[tuple[str, ApprovalDocument]]:
    """Return approval documents with their content-relative paths.

    Pending approvals are returned with lazy expiry applied in memory, so callers
    can surface expired state without mutating the repository.
    """

    approvals_root = _find_approvals_root(root)
    queue_names = ["pending"]
    if include_resolved:
        queue_names.append("resolved")

    results: list[tuple[str, ApprovalDocument]] = []
    for queue_name in queue_names:
        queue_dir = approvals_root / queue_name
        if not queue_dir.exists():
            continue
        for yaml_file in sorted(queue_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise ValidationError(f"Invalid approval YAML {yaml_file.name}: {exc}") from exc
            if not isinstance(raw, dict):
                raise ValidationError(f"Approval file must be a mapping: {yaml_file.name}")

            approval = _coerce_approval(raw)
            if queue_name == "pending":
                _check_approval_expiry(approval, root)
            rel_path = f"memory/working/approvals/{queue_name}/{yaml_file.name}"
            results.append((rel_path, approval))
    return results


def regenerate_approvals_summary(root: Path) -> None:
    """Rewrite memory/working/approvals/SUMMARY.md from pending and resolved directories."""
    approvals_root = _find_approvals_root(root)
    approvals_root.mkdir(parents=True, exist_ok=True)

    pending_approvals: list[ApprovalDocument] = []
    resolved_approvals: list[ApprovalDocument] = []

    pending_dir = approvals_root / "pending"
    if pending_dir.exists():
        for yaml_file in sorted(pending_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    pending_approvals.append(_coerce_approval(raw))
            except Exception:  # noqa: BLE001
                continue

    resolved_dir = approvals_root / "resolved"
    if resolved_dir.exists():
        for yaml_file in sorted(resolved_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    resolved_approvals.append(_coerce_approval(raw))
            except Exception:  # noqa: BLE001
                continue

    lines: list[str] = [
        "# Approval Queue",
        "",
        "Human-in-the-loop approval requests. "
        "Managed by `memory_request_approval` and `memory_resolve_approval`.",
        "",
    ]

    lines += ["## Pending", ""]
    if not pending_approvals:
        lines.append("_No pending approvals._")
    else:
        lines += ["| Plan | Phase | Requested | Expires |", "|---|---|---|---|"]
        for ap in pending_approvals:
            title = (ap.context or {}).get("phase_title", ap.phase_id)
            lines.append(f"| {ap.plan_id} | {title} | {ap.requested[:10]} | {ap.expires[:10]} |")

    lines += ["", "## Resolved", ""]
    if not resolved_approvals:
        lines.append("_No resolved approvals._")
    else:
        lines += ["| Plan | Phase | Status | Resolved |", "|---|---|---|---|"]
        for ap in sorted(resolved_approvals, key=lambda a: a.resolved_at or "", reverse=True):
            title = (ap.context or {}).get("phase_title", ap.phase_id)
            resolved_str = (ap.resolved_at or "")[:10]
            lines.append(f"| {ap.plan_id} | {title} | {ap.status} | {resolved_str} |")

    lines.append("")
    summary_abs = approvals_root / "SUMMARY.md"
    summary_abs.write_text("\n".join(lines) + "\n", encoding="utf-8")
