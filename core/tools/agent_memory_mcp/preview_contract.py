"""Shared preview-envelope helpers for governed write tools."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from .errors import ValidationError

ReceiptField = Literal["approval_token", "preview_token"]

_RECEIPT_VERSION = 1
_DEFAULT_RECEIPT_TTL_SECONDS = 15 * 60


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


def _receipt_ttl_seconds() -> int:
    raw = os.environ.get("ENGRAM_PREVIEW_RECEIPT_TTL_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_RECEIPT_TTL_SECONDS
    try:
        parsed = int(raw)
    except ValueError:
        return _DEFAULT_RECEIPT_TTL_SECONDS
    return max(60, parsed)


def _receipt_store(repo) -> Path:
    return repo.engram_state_dir("preview-receipts", create=True)


def _receipt_path(repo, token: str) -> Path:
    return _receipt_store(repo) / f"{token}.json"


def _canonical_operation_digest(
    *,
    tool_name: str,
    head: str,
    operation_arguments: dict[str, Any],
    receipt_field: ReceiptField,
) -> str:
    canonical = json.dumps(
        {
            "tool_name": tool_name,
            "head": head,
            "operation_arguments": operation_arguments,
            "receipt_field": receipt_field,
        },
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cleanup_expired_receipts(repo) -> None:
    now = datetime.now(timezone.utc)
    for receipt_file in _receipt_store(repo).glob("*.json"):
        try:
            payload = json.loads(receipt_file.read_text(encoding="utf-8"))
            expires_at = payload.get("expires_at")
            if not isinstance(expires_at, str):
                continue
            expiry = datetime.fromisoformat(expires_at)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if expiry <= now:
            try:
                receipt_file.unlink()
            except OSError:
                continue


def issue_preview_receipt(
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
    receipt_field: ReceiptField,
) -> tuple[str, dict[str, Any]]:
    """Create an opaque single-use receipt bound to HEAD and normalized args."""
    _cleanup_expired_receipts(repo)
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=_receipt_ttl_seconds())
    head = repo.current_head()
    token = secrets.token_hex(24)
    payload = {
        "version": _RECEIPT_VERSION,
        "receipt_field": receipt_field,
        "tool_name": tool_name,
        "head": head,
        "operation_digest": _canonical_operation_digest(
            tool_name=tool_name,
            head=head,
            operation_arguments=operation_arguments,
            receipt_field=receipt_field,
        ),
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    _receipt_path(repo, token).write_text(
        json.dumps(payload, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return token, payload


def _attach_receipt_requirement(
    preview_payload: dict[str, Any],
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
    receipt_field: ReceiptField,
) -> tuple[dict[str, Any], str]:
    token, receipt_payload = issue_preview_receipt(
        repo,
        tool_name=tool_name,
        operation_arguments=operation_arguments,
        receipt_field=receipt_field,
    )
    enriched = dict(preview_payload)
    requirement: dict[str, Any] = {
        "required": True,
        "type": receipt_field,
        "tool_name": tool_name,
        "head": receipt_payload["head"],
        receipt_field: token,
        "expires_at": receipt_payload["expires_at"],
    }
    if receipt_field == "approval_token":
        enriched["approval"] = requirement
    else:
        enriched["preview_requirement"] = requirement
    return enriched, token


def attach_approval_requirement(
    preview_payload: dict[str, Any],
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Attach protected-write approval metadata to a governed preview payload."""
    return _attach_receipt_requirement(
        preview_payload,
        repo,
        tool_name=tool_name,
        operation_arguments=operation_arguments,
        receipt_field="approval_token",
    )


def attach_preview_requirement(
    preview_payload: dict[str, Any],
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Attach preview-before-apply metadata to a governed preview payload."""
    return _attach_receipt_requirement(
        preview_payload,
        repo,
        tool_name=tool_name,
        operation_arguments=operation_arguments,
        receipt_field="preview_token",
    )


def _require_receipt(
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
    receipt_field: ReceiptField,
    token: str | None,
) -> str:
    if not token:
        raise ValidationError(
            f"{receipt_field} is required. Call {tool_name} in preview mode first and apply the reviewed change again."
        )

    receipt_path = _receipt_path(repo, token)
    if not receipt_path.exists():
        raise ValidationError(
            f"{receipt_field} is invalid or stale for {tool_name}. Re-run preview and use the newly issued receipt."
        )

    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(
            f"{receipt_field} is invalid or unreadable for {tool_name}. Re-run preview and retry."
        ) from exc

    expected_head = repo.current_head()
    current_digest = _canonical_operation_digest(
        tool_name=tool_name,
        head=expected_head,
        operation_arguments=operation_arguments,
        receipt_field=receipt_field,
    )

    errors: list[str] = []
    if payload.get("version") != _RECEIPT_VERSION:
        errors.append("receipt version mismatch")
    if payload.get("receipt_field") != receipt_field:
        errors.append("receipt kind mismatch")
    if payload.get("tool_name") != tool_name:
        errors.append("tool mismatch")

    stored_head = payload.get("head")
    if stored_head != expected_head:
        errors.append("repository HEAD changed")

    expires_at = payload.get("expires_at")
    try:
        expiry = datetime.fromisoformat(str(expires_at))
    except ValueError:
        errors.append("receipt expiry is invalid")
        expiry = None
    if expiry is not None and expiry <= datetime.now(timezone.utc):
        errors.append("receipt expired")

    if payload.get("operation_digest") != current_digest:
        errors.append("arguments no longer match preview")

    if errors:
        if "receipt expired" in errors or "repository HEAD changed" in errors:
            try:
                receipt_path.unlink()
            except OSError:
                pass
        raise ValidationError(
            f"{receipt_field} is invalid or stale for {tool_name}: {', '.join(errors)}. Re-run preview and apply the reviewed change again."
        )

    try:
        receipt_path.unlink()
    except OSError as exc:
        raise ValidationError(
            f"{receipt_field} could not be consumed for {tool_name}. Re-run preview and retry."
        ) from exc
    return token


def require_approval_token(
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
    approval_token: str | None,
) -> str:
    """Validate that an apply call supplies a fresh preview-issued approval token."""
    return _require_receipt(
        repo,
        tool_name=tool_name,
        operation_arguments=operation_arguments,
        receipt_field="approval_token",
        token=approval_token,
    )


def require_preview_token(
    repo,
    *,
    tool_name: str,
    operation_arguments: dict[str, Any],
    preview_token: str | None,
) -> str:
    """Validate that an apply call supplies a fresh preview-issued preview token."""
    return _require_receipt(
        repo,
        tool_name=tool_name,
        operation_arguments=operation_arguments,
        receipt_field="preview_token",
        token=preview_token,
    )


__all__ = [
    "attach_approval_requirement",
    "attach_preview_requirement",
    "build_governed_preview",
    "issue_preview_receipt",
    "preview_target",
    "require_approval_token",
    "require_preview_token",
]
