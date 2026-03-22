"""Shared preview-envelope helpers for governed write tools."""

from __future__ import annotations

from typing import Any


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


__all__ = ["build_governed_preview", "preview_target"]
