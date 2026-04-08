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

    @mcp.tool(
        name="memory_skill_manifest_read",
        annotations=_tool_annotations(
            title="Read Skill Manifest",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_skill_manifest_read(
        skill: str | None = None,
    ) -> str:
        """Read and parse SKILLS.yaml, checking lock status for each skill.

        For each skill entry, verifies if the lock entry exists and is fresh
        (content hash matches current directory).

        Returns structured JSON with: schema_version, defaults, skills
        (each with manifest fields + lock_status: "locked"|"stale"|"unlocked").

        Parameters:
        - skill (optional): Filter to a single skill entry by slug
        """
        import hashlib
        import os
        from pathlib import Path

        import yaml

        from ...errors import NotFoundError, ValidationError
        from ...models import MemoryReadResult

        repo = get_repo()
        manifest_path = Path(repo) / "core" / "memory" / "skills" / "SKILLS.yaml"
        lockfile_path = Path(repo) / "core" / "memory" / "skills" / "SKILLS.lock"

        if not manifest_path.exists():
            raise NotFoundError(f"Skill manifest not found: core/memory/skills/SKILLS.yaml")

        with open(manifest_path, "r") as f:
            manifest_data = yaml.safe_load(f) or {}

        lock_data = {}
        if lockfile_path.exists():
            with open(lockfile_path, "r") as f:
                lock_data = yaml.safe_load(f) or {}

        lock_entries = lock_data.get("entries", {})

        def compute_content_hash(skill_dir: Path) -> str:
            """Compute deterministic content hash for a skill directory."""
            if not skill_dir.exists():
                return ""

            file_hashes = []
            for file_path in sorted(skill_dir.rglob("*")):
                if file_path.is_file():
                    rel_path = file_path.relative_to(skill_dir)
                    rel_path_str = rel_path.as_posix()
                    with open(file_path, "rb") as f:
                        content = f.read()
                    file_hash = hashlib.sha256(
                        rel_path_str.encode() + b"\0" + content
                    ).hexdigest()
                    file_hashes.append(file_hash)

            if not file_hashes:
                return ""

            concatenated = "".join(file_hashes)
            final_hash = hashlib.sha256(concatenated.encode()).hexdigest()
            return f"sha256:{final_hash}"

        skills_list = manifest_data.get("skills", {})
        enriched_skills = {}

        for slug, skill_data in skills_list.items():
            enriched = dict(skill_data) if isinstance(skill_data, dict) else {}
            lock_entry = lock_entries.get(slug, {})

            # Determine lock status
            lock_status = "unlocked"
            if lock_entry:
                skill_dir = Path(repo) / "core" / "memory" / "skills" / slug
                current_hash = compute_content_hash(skill_dir)
                locked_hash = lock_entry.get("content_hash", "")

                if current_hash and current_hash == locked_hash:
                    lock_status = "locked"
                elif locked_hash:
                    lock_status = "stale"

            enriched["lock_status"] = lock_status
            enriched_skills[slug] = enriched

        result_data = {
            "schema_version": manifest_data.get("schema_version", 1),
            "defaults": manifest_data.get("defaults", {}),
            "skills": enriched_skills,
        }

        # Filter to single skill if requested
        if skill:
            if skill not in enriched_skills:
                raise NotFoundError(f"Skill not found in manifest: {skill}")
            result_data["skills"] = {skill: enriched_skills[skill]}

        result = MemoryReadResult(content=result_data, preview=None)
        return result.to_json()

    @mcp.tool(
        name="memory_skill_manifest_write",
        annotations=_tool_annotations(
            title="Write Skill Manifest Entry",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_skill_manifest_write(
        slug: str,
        source: str,
        trust: str,
        description: str,
        ref: str | None = None,
        deployment_mode: str | None = None,
        enabled: bool | None = None,
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Write or update a skill entry in SKILLS.yaml.

        Validates slug (kebab-case), trust level, and source format.
        Uses the governed preview-then-apply pattern.

        Parameters:
        - slug (required): Skill identifier (kebab-case)
        - source (required): Source location (local, github:owner/repo, git:url, path:...)
        - trust (required): Trust level (high, medium, low)
        - description (required): One-line description
        - ref (optional): Version pin for remote sources
        - deployment_mode (optional): checked or gitignored
        - enabled (optional): true or false (default: true)
        - preview (bool): When true, return preview without writing
        - approval_token (string): Required for apply mode (non-preview)
        """
        import re
        from pathlib import Path

        import yaml

        from ...errors import ValidationError
        from ...models import MemoryWriteResult
        from ...preview_contract import (
            attach_approval_requirement,
            build_governed_preview,
            preview_target,
            require_approval_token,
        )

        repo = get_repo()

        # Validate slug (kebab-case)
        slug_pattern = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
        if not re.match(slug_pattern, slug):
            raise ValidationError(f"slug must be kebab-case: {slug}")

        # Validate trust level
        valid_trusts = {"high", "medium", "low"}
        if trust not in valid_trusts:
            raise ValidationError(
                f"trust must be one of {sorted(valid_trusts)}: {trust}"
            )

        # Validate source format
        source_patterns = {
            "local": r"^local$",
            "github": r"^github:[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$",
            "git": r"^git:(https?:\/\/|git@).+$",
            "path": r"^path:\./.+$",
        }
        valid_source = False
        for pattern in source_patterns.values():
            if re.match(pattern, source):
                valid_source = True
                break
        if not valid_source:
            raise ValidationError(
                f"source format invalid. Must match one of: local, github:owner/repo, git:url, path:./relative: {source}"
            )

        # Validate ref only used with remote sources
        if ref and not source.startswith(("github:", "git:")):
            raise ValidationError(f"ref is only valid with github: or git: sources")

        # Validate description is non-empty
        if not description or not description.strip():
            raise ValidationError("description must be non-empty")

        manifest_path = Path(repo) / "core" / "memory" / "skills" / "SKILLS.yaml"

        if not manifest_path.exists():
            raise ValidationError(
                f"Skill manifest not found: core/memory/skills/SKILLS.yaml"
            )

        with open(manifest_path, "r") as f:
            manifest_data = yaml.safe_load(f) or {}

        skills = manifest_data.get("skills", {})

        # Build skill entry
        skill_entry = {
            "source": source,
            "trust": trust,
            "description": description.strip(),
        }
        if ref:
            skill_entry["ref"] = ref
        if deployment_mode:
            skill_entry["deployment_mode"] = deployment_mode
        if enabled is not None:
            skill_entry["enabled"] = enabled

        # Check if this is a new skill
        is_new = slug not in skills

        rel_path = "core/memory/skills/SKILLS.yaml"
        commit_msg = (
            f"[skill-manifest] Add skill {slug}" if is_new
            else f"[skill-manifest] Update skill {slug}"
        )
        operation_arguments = {
            "slug": slug,
            "source": source,
            "trust": trust,
            "description": description,
            "ref": ref,
            "deployment_mode": deployment_mode,
            "enabled": enabled,
        }

        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"{'Add' if is_new else 'Update'} skill entry {slug} in SKILLS.yaml.",
            reasoning="Skill manifest updates are protected because they affect skill resolution and catalog generation.",
            target_files=[preview_target(rel_path, "create" if is_new else "update")],
            invariant_effects=[
                f"{'Creates a new' if is_new else 'Updates the'} skill entry '{slug}' with source={source}, trust={trust}.",
                "Preserves all other skill entries and manifest structure.",
                "Does not modify SKILLS.lock (lock freshness is checked at read time).",
            ],
            commit_message=commit_msg,
            resulting_state={"slug": slug, "source": source, "trust": trust},
        )

        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_skill_manifest_write",
            operation_arguments=operation_arguments,
        )

        if preview:
            result = MemoryWriteResult(
                files_changed=[rel_path],
                commit_sha=None,
                commit_message=None,
                new_state={
                    "slug": slug,
                    "approval_token": protected_token,
                },
                preview=preview_payload,
            )
            return result.to_json()

        require_approval_token(
            repo,
            tool_name="memory_skill_manifest_write",
            operation_arguments=operation_arguments,
            approval_token=approval_token,
        )

        # Write the updated manifest
        skills[slug] = skill_entry
        manifest_data["skills"] = skills

        # Preserve structure: sort top-level keys sensibly
        ordered_manifest = {}
        for key in ["schema_version", "defaults", "skills"]:
            if key in manifest_data:
                ordered_manifest[key] = manifest_data[key]

        with open(manifest_path, "w") as f:
            yaml.dump(ordered_manifest, f, default_flow_style=False, sort_keys=False)

        repo.add(rel_path)
        commit_result = repo.commit(commit_msg)

        result = MemoryWriteResult.from_commit(
            files_changed=[rel_path],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={"slug": slug, "source": source, "trust": trust},
            preview=preview_payload,
        )
        return result.to_json()

    return {
        "memory_update_skill": memory_update_skill,
        "memory_skill_manifest_read": memory_skill_manifest_read,
        "memory_skill_manifest_write": memory_skill_manifest_write,
    }


__all__ = ["register_tools"]
