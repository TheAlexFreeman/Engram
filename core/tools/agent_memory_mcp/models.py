"""
Return types for all write tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .response_envelope import envelope_tool_result

if TYPE_CHECKING:
    from .session_state import SessionState


@dataclass
class MemoryWriteResult:
    """Structured result returned by every write tool.

    Attributes:
        files_changed:  Repo-relative paths of all files written or staged.
        commit_sha:     Commit SHA if the operation auto-committed; None for
                        Tier 2 staged-only tools (call memory_commit to seal).
        commit_message: The commit message used, or None.
        new_state:      Operation-specific fields — eliminates read-after-write.
                        Examples:
                          mark_plan_item_complete → next_action, phase_progress, plan_progress, status
                          promote_knowledge       → new_path, trust
                          write                   → version_token
        warnings:       Non-fatal issues (e.g. SUMMARY.md section not found,
                        unrecognised commit prefix).
        publication:    Publication metadata for committed operations.
    """

    files_changed: list[str]
    commit_sha: str | None
    commit_message: str | None
    new_state: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    publication: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None

    @classmethod
    def from_commit(
        cls,
        *,
        files_changed: list[str],
        commit_result: Any,
        commit_message: str,
        new_state: dict[str, Any],
        warnings: list[str] | None = None,
        preview: dict[str, Any] | None = None,
    ) -> "MemoryWriteResult":
        publication = commit_result.to_dict()
        combined_warnings = list(warnings or []) + list(publication.get("warnings", []))
        return cls(
            files_changed=files_changed,
            commit_sha=commit_result.sha,
            commit_message=commit_message,
            new_state=new_state,
            warnings=combined_warnings,
            publication=publication,
            preview=preview,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "files_changed": self.files_changed,
            "commit_sha": self.commit_sha,
            "commit_message": self.commit_message,
            "new_state": self.new_state,
            "warnings": self.warnings,
            "publication": self.publication,
        }
        if self.preview is not None:
            payload["preview"] = self.preview
        return payload

    def to_json(
        self,
        indent: int = 2,
        *,
        session_state: "SessionState | None" = None,
    ) -> str:
        payload: dict[str, Any] = self.to_dict()
        if session_state is not None:
            payload = envelope_tool_result(payload, session_state)
        return json.dumps(payload, indent=indent)
