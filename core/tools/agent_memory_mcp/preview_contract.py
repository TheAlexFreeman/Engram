"""Shared preview-envelope helpers for governed write tools."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import ValidationError


def preview_target(
    path: str,
    change: str,
    *,
    from_path: str | None = None,
    details: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": path,
        "change": change,
    }
    if from_path:
        payload["from_path"] = from_path
    if details:
        payload["details"] = details
    return payload


def build_governed_preview(
    *,
    mode: str,
    change_class: str,
    summary: str,
    reasoning: str,
    target_files: list[dict[str, Any]],
    invariant_effects: list[str],
    commit_message: str | None,
    resulting_state: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    commit_suggestion: dict[str, Any] | None = None
    if commit_message:
        commit_suggestion = {"message": commit_message}

    return {
        "mode": mode,
        "change_class": change_class,
        "summary": summary,
        "reasoning": reasoning,
        "target_files": target_files,
        "invariant_effects": invariant_effects,
        "commit_suggestion": commit_suggestion,
        "warnings": list(warnings or []),
        "resulting_state": resulting_state,
    }


def approval_token_for_operation(
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
) -> str:
    """Return a deterministic approval token bound to the current HEAD and tool args."""
    canonical = json.dumps(
        {
            "tool_name": tool_name,
            "head": repo.current_head(),
            "operation_arguments": operation_arguments,
        },
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def attach_approval_requirement(
    preview_payload: dict[str, Any],
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Attach protected-write approval metadata to a governed preview payload."""
    token = approval_token_for_operation(
        repo,
        tool_name=tool_name,
        operation_arguments=operation_arguments,
    )
    head = repo.current_head()
    enriched = dict(preview_payload)
    enriched["approval"] = {
        "required": True,
        "type": "approval_token",
        "tool_name": tool_name,
        "head": head,
        "approval_token": token,
    }
    return enriched, token


def require_approval_token(
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
    approval_token: str | None,
) -> str:
    """Validate that an apply call supplies the fresh preview token for a protected write."""
    if not approval_token:
        raise ValidationError(
            f"approval_token is required for protected apply mode. Call {tool_name} with preview=True first."
        )

    expected = approval_token_for_operation(
        repo,
        tool_name=tool_name,
        operation_arguments=operation_arguments,
    )
    if approval_token != expected:
        raise ValidationError(
            f"approval_token is invalid or stale for {tool_name}. Re-run the preview and apply the reviewed change again."
        )
    return expected


__all__ = [
    "approval_token_for_operation",
    "attach_approval_requirement",
    "build_governed_preview",
    "preview_target",
    "require_approval_token",
]
