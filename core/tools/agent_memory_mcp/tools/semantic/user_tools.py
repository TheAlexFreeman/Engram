"""User-oriented semantic tools."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from ...path_policy import resolve_repo_path, validate_slug
from ...preview_contract import build_governed_preview, preview_target
from ...tool_schemas import UPDATE_MODES
from ._session import (
    SessionState,
    get_identity_churn_limit,
    get_identity_updates,
    increment_identity_updates,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _tool_annotations(**kwargs: object) -> Any:
    return cast(Any, kwargs)


def _replace_markdown_section(body: str, section_name: str, new_value: str) -> str | None:
    section_heading = f"## {section_name}"
    match = re.search(rf"(?m)^##\s+{re.escape(section_name)}\s*$", body)
    if match is None:
        return None

    content_start = match.end()
    next_heading = re.search(r"(?m)^## ", body[content_start:])
    section_end = content_start + next_heading.start() if next_heading else len(body)
    replacement = f"{section_heading}\n\n{new_value.strip()}\n"
    if next_heading:
        replacement += "\n"
    return body[: match.start()] + replacement + body[section_end:]


def _append_markdown_section(body: str, section_name: str, value: str) -> str | None:
    match = re.search(rf"(?m)^##\s+{re.escape(section_name)}\s*$", body)
    if match is None:
        return None

    content_start = match.end()
    next_heading = re.search(r"(?m)^## ", body[content_start:])
    section_end = content_start + next_heading.start() if next_heading else len(body)
    existing = body[content_start:section_end].strip()
    appended = f"{existing}\n{value.strip()}" if existing else value.strip()
    return _replace_markdown_section(body, section_name, appended)


def register_tools(
    mcp: "FastMCP",
    get_repo,
    session_state: SessionState,
) -> dict[str, object]:
    """Register user-oriented semantic tools."""

    @mcp.tool(
        name="memory_update_user_trait",
        annotations=_tool_annotations(
            title="Update User Trait",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_update_user_trait(
        file: str,
        key: str,
        value: str,
        mode: str = "upsert",
        version_token: str | None = None,
        preview: bool = False,
    ) -> str:
        """Update a named field in a user file.

        mode must be one of "upsert", "append", or "replace".
            preview=True returns the governed preview envelope without writing. Call
            memory_tool_schema with tool_name="memory_update_user_trait" for the
            full file/key/version-token contract.
        """
        from ...errors import ValidationError
        from ...frontmatter_utils import read_with_frontmatter, today_str, write_with_frontmatter
        from ...models import MemoryWriteResult

        repo = get_repo()

        if mode not in UPDATE_MODES:
            raise ValidationError(f"mode must be one of {sorted(UPDATE_MODES)}: {mode}")

        if get_identity_updates(session_state) >= get_identity_churn_limit():
            raise ValidationError(
                f"User churn alarm: {get_identity_churn_limit()} trait updates this session — "
                "call memory_reset_session_state to acknowledge and reset the counter, "
                "or restart the MCP server."
            )

        file = validate_slug(file, field_name="file")
        rel_path, abs_path = resolve_repo_path(repo, f"memory/users/{file}.md")
        if not abs_path.exists():
            raise ValidationError(f"User file not found: {rel_path}")

        repo.check_version_token(rel_path, version_token)

        fm_dict, body = read_with_frontmatter(abs_path)
        section_heading = f"## {key}"

        if key in fm_dict or (mode == "upsert" and section_heading not in body):
            if mode == "append" and key in fm_dict:
                existing = str(fm_dict[key])
                fm_dict[key] = existing + "\n" + value
            else:
                fm_dict[key] = value
            fm_dict["last_verified"] = today_str()
        else:
            if section_heading in body:
                if mode in ("replace", "upsert"):
                    updated_body = _replace_markdown_section(body, key, value)
                else:
                    updated_body = _append_markdown_section(body, key, value)
                if updated_body is None:
                    raise ValidationError(f"Identity section not found: {section_heading}")
                body = updated_body
            else:
                body = body.rstrip() + f"\n\n{section_heading}\n\n{value.strip()}\n"

            fm_dict["last_verified"] = today_str()

        commit_msg = f"[user] Update {key} in memory/users/{file}.md"
        predicted_updates = get_identity_updates(session_state) + 1
        new_state = {
            "key": key,
            "mode": mode,
            "identity_updates_this_session": predicted_updates,
        }
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="proposed",
            summary=f"Update user trait {key} in memory/users/{file}.md.",
            reasoning="User updates are proposed durable-memory writes and are rate-limited by the churn alarm.",
            target_files=[preview_target(rel_path, "update")],
            invariant_effects=[
                "Updates the requested user trait using the selected merge mode.",
                "Refreshes last_verified in the user file.",
                "Consumes one identity update from the current session budget on apply.",
            ],
            commit_message=commit_msg,
            resulting_state=new_state,
        )
        if preview:
            result = MemoryWriteResult(
                files_changed=[rel_path],
                commit_sha=None,
                commit_message=None,
                new_state=new_state,
                preview=preview_payload,
            )
            return result.to_json()

        write_with_frontmatter(abs_path, fm_dict, body)
        repo.add(rel_path)
        identity_updates = increment_identity_updates(session_state)
        new_state["identity_updates_this_session"] = identity_updates
        commit_result = repo.commit(commit_msg)

        result = MemoryWriteResult.from_commit(
            files_changed=[rel_path],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=new_state,
            preview=preview_payload,
        )
        return result.to_json()

    return {"memory_update_user_trait": memory_update_user_trait}


__all__ = ["register_tools"]
