"""Skill-oriented semantic tools."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from ...frontmatter_policy import validate_frontmatter_metadata
from ...path_policy import resolve_repo_path, validate_session_id, validate_slug
from ...preview_contract import (
    attach_approval_requirement,
    build_governed_preview,
    preview_target,
    require_approval_token,
)
from ...tool_schemas import SKILL_CREATE_TRUST_LEVELS, UPDATE_MODES

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


def register_tools(mcp: "FastMCP", get_repo) -> dict[str, object]:
    """Register skill-oriented semantic tools."""

    @mcp.tool(
        name="memory_update_skill",
        annotations=_tool_annotations(
            title="Update Skill File",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_update_skill(
        file: str,
        section: str,
        content: str,
        mode: str = "upsert",
        version_token: str | None = None,
        create_if_missing: bool = False,
        source: str | None = None,
        trust: str | None = None,
        origin_session: str | None = None,
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Update a named section in a skill file, optionally creating the file.

        Unlike identity updates, skill updates do not enforce a per-session churn alarm.
        The protected change class and explicit-review flow are the primary safeguards here.

        mode must be one of "upsert", "append", or "replace".
        When create_if_missing=True, source, trust, and origin_session are required.
        Call memory_tool_schema with tool_name="memory_update_skill" for the
        full create-if-missing and approval-token contract.
        """
        from ...errors import NotFoundError, ValidationError
        from ...frontmatter_utils import (
            read_with_frontmatter,
            render_with_frontmatter,
            today_str,
            write_with_frontmatter,
        )
        from ...guard_pipeline import require_guarded_write_pass
        from ...models import MemoryWriteResult

        repo = get_repo()

        if mode not in UPDATE_MODES:
            raise ValidationError(f"mode must be one of {sorted(UPDATE_MODES)}: {mode}")

        file = validate_slug(file, field_name="file")
        rel_path, abs_path = resolve_repo_path(repo, f"memory/skills/{file}.md")
        today = today_str()
        file_exists = abs_path.exists()

        if file_exists:
            repo.check_version_token(rel_path, version_token)
            fm_dict, body = read_with_frontmatter(abs_path)
        else:
            if not create_if_missing:
                raise NotFoundError(f"Skill file not found: {rel_path}")
            if not source or not source.strip():
                raise ValidationError("source is required when create_if_missing=True")
            if trust not in SKILL_CREATE_TRUST_LEVELS:
                raise ValidationError(
                    "trust must be one of "
                    f"{sorted(SKILL_CREATE_TRUST_LEVELS)} when create_if_missing=True"
                )
            if origin_session is None:
                raise ValidationError("origin_session is required when create_if_missing=True")
            validate_session_id(origin_session)
            fm_dict = {
                "source": source.strip(),
                "origin_session": origin_session,
                "created": today,
                "last_verified": today,
                "trust": trust,
            }
            body = f"# {file.replace('-', ' ').title()}\n"

        section_heading = f"## {section}"
        if section in fm_dict:
            if mode == "append":
                existing = str(fm_dict[section])
                fm_dict[section] = existing + "\n" + content.strip()
            else:
                fm_dict[section] = content
        elif section_heading in body:
            updated_body = (
                _append_markdown_section(body, section, content)
                if mode == "append"
                else _replace_markdown_section(body, section, content)
            )
            if updated_body is None:
                raise ValidationError(f"Skill section not found: {section_heading}")
            body = updated_body
        else:
            body = body.rstrip() + f"\n\n{section_heading}\n\n{content.strip()}\n"

        fm_dict["last_verified"] = today
        validate_frontmatter_metadata(fm_dict, context=f"skill frontmatter for {rel_path}")
        commit_msg = f"[skill] Update {section} in memory/skills/{file}.md"
        new_state = {"section": section, "mode": mode}
        operation_arguments = {
            "file": file,
            "section": section,
            "content": content,
            "mode": mode,
            "version_token": version_token,
            "create_if_missing": create_if_missing,
            "source": source,
            "trust": trust,
            "origin_session": origin_session,
        }
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"Update skill section {section} in memory/skills/{file}.md.",
            reasoning="Skill files are protected because they can directly shape agent procedure.",
            target_files=[preview_target(rel_path, "update" if file_exists else "create")],
            invariant_effects=[
                "Updates the requested skill section using upsert, append, or replace semantics.",
                "Refreshes last_verified in the skill frontmatter.",
                "Protected apply mode requires the approval_token returned by preview mode.",
            ],
            commit_message=commit_msg,
            resulting_state=new_state,
        )
        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_update_skill",
            operation_arguments=operation_arguments,
        )
        if preview:
            result = MemoryWriteResult(
                files_changed=[rel_path],
                commit_sha=None,
                commit_message=None,
                new_state={**new_state, "approval_token": protected_token},
                preview=preview_payload,
            )
            return result.to_json()

        require_approval_token(
            repo,
            tool_name="memory_update_skill",
            operation_arguments=operation_arguments,
            approval_token=approval_token,
        )
        rendered = render_with_frontmatter(fm_dict, body)
        require_guarded_write_pass(
            path=rel_path,
            operation="write",
            root=repo.root,
            content=rendered,
        )
        write_with_frontmatter(abs_path, fm_dict, body)
        repo.add(rel_path)
        commit_result = repo.commit(commit_msg)

        result = MemoryWriteResult.from_commit(
            files_changed=[rel_path],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=new_state,
            preview=preview_payload,
        )
        return result.to_json()

    return {"memory_update_skill": memory_update_skill}


__all__ = ["register_tools"]
