"""Skill-oriented semantic tools."""

from __future__ import annotations

import importlib.util
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ...frontmatter_policy import validate_frontmatter_metadata
from ...path_policy import resolve_repo_path, validate_session_id, validate_slug
from ...preview_contract import (
    attach_approval_requirement,
    build_governed_preview,
    preview_target,
    require_approval_token,
)
from ...skill_distributor import (
    BUILTIN_TARGETS,
    SkillDistributor,
    normalize_distribution_targets,
    resolve_skill_distribution_targets,
)
from ...skill_gitignore import (
    DEPLOYMENT_MODES,
    SkillGitignoreManager,
    resolve_skill_deployment_mode,
)
from ...skill_hash import compute_content_hash, get_dir_stats
from ...skill_resolver import SkillResolver, parse_skill_source
from ...skill_trigger import summarize_skill_trigger, validate_skill_trigger
from ...skill_trigger_router import TriggerRouter
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


def _resolve_skill_markdown_path(repo: Any, slug: str) -> tuple[str, Path]:
    """Resolve memory/skills/{slug}/SKILL.md when present, else legacy {slug}.md."""
    nested_rel, nested_abs = resolve_repo_path(repo, f"memory/skills/{slug}/SKILL.md")
    flat_rel, flat_abs = resolve_repo_path(repo, f"memory/skills/{slug}.md")
    if nested_abs.exists():
        return nested_rel, nested_abs
    if flat_abs.exists():
        return flat_rel, flat_abs
    return nested_rel, nested_abs


def _distribution_target_state(item: dict[str, Any], *, status: str) -> dict[str, Any]:
    state: dict[str, Any] = {"status": status}
    for key in ("target", "profile", "outputs", "index_path", "transport"):
        value = item.get(key)
        if value is not None:
            state[key] = value
    if status == "issue":
        state["issues"] = list(item.get("issues", []))
    if status == "failed":
        if item.get("reason") is not None:
            state["reason"] = item["reason"]
        if item.get("detail") is not None:
            state["detail"] = item["detail"]
    return state


def _distribution_states_by_slug(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    def ensure(slug: str) -> dict[str, Any]:
        return grouped.setdefault(slug, {"status": "healthy", "targets": [], "issue_count": 0})

    for item in report.get("verified", []):
        slug = item.get("slug")
        if isinstance(slug, str):
            ensure(slug)["targets"].append(_distribution_target_state(item, status="ok"))

    for item in report.get("issues", []):
        slug = item.get("slug")
        if not isinstance(slug, str):
            continue
        state = ensure(slug)
        if state["status"] != "failed":
            state["status"] = "needs_attention"
        state["issue_count"] += max(1, len(item.get("issues", [])))
        state["targets"].append(_distribution_target_state(item, status="issue"))

    for item in report.get("failed", []):
        slug = item.get("slug")
        if not isinstance(slug, str):
            continue
        state = ensure(slug)
        state["status"] = "failed"
        state["issue_count"] += 1
        state["targets"].append(_distribution_target_state(item, status="failed"))

    for state in grouped.values():
        state["targets"].sort(
            key=lambda target: (str(target.get("target") or ""), target["status"])
        )

    return grouped


def _distribution_issue_details(report: dict[str, Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []

    for item in report.get("issues", []):
        issue_messages = []
        for issue in item.get("issues", []):
            if not isinstance(issue, dict):
                continue
            detail = issue.get("detail")
            if isinstance(detail, str):
                issue_messages.append(detail)
        details.append(
            {
                "type": "distribution_issue",
                "slug": item.get("slug"),
                "target": item.get("target"),
                "issue": "; ".join(issue_messages) or "distribution output requires repair",
            }
        )

    for item in report.get("failed", []):
        details.append(
            {
                "type": "distribution_failure",
                "slug": item.get("slug"),
                "target": item.get("target"),
                "issue": item.get("detail")
                or item.get("reason")
                or "distribution validation failed",
            }
        )

    return details


def _distribution_preview_targets(report: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in report.get("issues", []):
        for path in list(item.get("outputs", [])) + [item.get("index_path")]:
            if not isinstance(path, str) or not path or path in seen:
                continue
            seen.add(path)
            targets.append(preview_target(path, "update"))
    return targets


_KNOWN_SKILL_FRONTMATTER_FIELDS = frozenset(
    {
        "name",
        "description",
        "compatibility",
        "source",
        "origin_session",
        "created",
        "last_verified",
        "trust",
        "superseded_by",
        "trigger",
    }
)


def _is_skill_frontmatter_field(section: str, frontmatter: dict[str, Any]) -> bool:
    return section in frontmatter or section in _KNOWN_SKILL_FRONTMATTER_FIELDS


def _require_string_section_content(section: str, content: object) -> str:
    from ...errors import ValidationError

    if not isinstance(content, str):
        raise ValidationError(f"Skill section {section!r} requires string content")
    return content


def _update_skill_frontmatter_field(
    frontmatter: dict[str, Any], section: str, content: object, mode: str
) -> None:
    from ...errors import ValidationError

    if section == "trigger":
        if mode == "append":
            existing = frontmatter.get(section)
            if existing is None:
                frontmatter[section] = list(content) if isinstance(content, list) else [content]
            elif isinstance(existing, list):
                frontmatter[section] = (
                    [*existing, *content] if isinstance(content, list) else [*existing, content]
                )
            else:
                frontmatter[section] = (
                    [existing, *content] if isinstance(content, list) else [existing, content]
                )
        else:
            frontmatter[section] = content
        validate_skill_trigger(frontmatter[section], context="trigger")
        return

    if not isinstance(content, str):
        raise ValidationError(f"Frontmatter field {section!r} requires string content")
    normalized = content.strip()
    if mode == "append" and section in frontmatter and frontmatter[section] not in (None, ""):
        frontmatter[section] = f"{frontmatter[section]}\n{normalized}"
        return
    frontmatter[section] = normalized


_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate_skill_kebab_slug(slug: str) -> None:
    from ...errors import ValidationError

    if not _SLUG_PATTERN.match(slug):
        raise ValidationError(f"slug must be kebab-case: {slug}")


def _load_generate_skill_catalog_module(repo_root: Path) -> Any:
    from ...errors import ValidationError

    script = repo_root / "HUMANS" / "tooling" / "scripts" / "generate_skill_catalog.py"
    if not script.is_file():
        raise ValidationError(f"generate_skill_catalog.py not found: {script}")
    spec = importlib.util.spec_from_file_location("_engram_generate_skill_catalog", script)
    if spec is None or spec.loader is None:
        raise ValidationError("failed to load generate_skill_catalog module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _regenerate_skill_tree_content(repo_root: Path) -> str:
    mod = _load_generate_skill_catalog_module(repo_root)
    return mod.regenerate_skill_tree_markdown(repo_root, log_missing_frontmatter=False)


def _append_skill_summary_bullet(repo_root: Path, slug: str, description: str) -> str | None:
    summary_path = repo_root / "core" / "memory" / "skills" / "SUMMARY.md"
    if not summary_path.is_file():
        return None
    text = summary_path.read_text(encoding="utf-8")
    if f"({slug}/SKILL.md)" in text:
        return text
    line = f"- **[{slug}/]({slug}/SKILL.md)** — {description.strip()}\n"
    anchor = "\n\n## Scenario suites"
    if anchor in text:
        return text.replace(anchor, f"\n{line}{anchor}", 1)
    return text.rstrip() + "\n" + line + "\n"


def _remove_skill_summary_bullet(content: str, slug: str) -> str:
    needle = f"({slug}/SKILL.md)"
    lines = [ln for ln in content.splitlines() if needle not in ln]
    out = "\n".join(lines)
    if content.endswith("\n"):
        out += "\n"
    return out


def _append_archive_index_row(
    repo_root: Path, slug: str, archive_reason: str | None
) -> tuple[str, str]:
    path = repo_root / "core" / "memory" / "skills" / "_archive" / "ARCHIVE_INDEX.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reason = (archive_reason or "").replace("|", "\\|").replace("\n", " ")
    row = f"| `{slug}` | {ts} | {reason} |\n"
    if path.is_file():
        text = path.read_text(encoding="utf-8").rstrip() + "\n" + row
    else:
        text = (
            "# Skill archive index\n\n"
            "Skills moved out of the active catalog by `memory_skill_remove`.\n\n"
            "| Slug | Archived at | Reason |\n"
            "| --- | --- | --- |\n"
            f"{row}"
        )
    return "core/memory/skills/_archive/ARCHIVE_INDEX.md", text


def _rebuild_skills_lock_data(
    manifest_skills: dict[str, Any],
    skills_dir: Path,
    prior_lock: dict[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild SKILLS.lock ``entries`` from manifest + on-disk skill directories."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    old_entries_raw = (prior_lock or {}).get("entries") or {}
    old_entries: dict[str, Any] = old_entries_raw if isinstance(old_entries_raw, dict) else {}
    new_entries: dict[str, Any] = {}
    for slug, mentry in sorted(manifest_skills.items()):
        if not isinstance(mentry, dict):
            continue
        if mentry.get("enabled", True) is False:
            continue
        skill_dir = skills_dir / slug
        if not (skill_dir / "SKILL.md").is_file():
            continue
        prev = old_entries.get(slug, {})
        if not isinstance(prev, dict):
            prev = {}
        src = prev.get("source") or mentry.get("source") or "local"
        rpath = prev.get("resolved_path") or f"core/memory/skills/{slug}/"
        content_hash = compute_content_hash(skill_dir)
        fc, tb = get_dir_stats(skill_dir)
        new_entries[slug] = {
            "source": src,
            "resolved_path": rpath,
            "content_hash": content_hash,
            "locked_at": ts,
            "file_count": fc,
            "total_bytes": tb,
            **(
                {"requested_ref": prev.get("requested_ref")}
                if isinstance(prev.get("requested_ref"), str)
                else {"requested_ref": mentry.get("ref")}
                if isinstance(mentry.get("ref"), str)
                else {}
            ),
            **(
                {"resolved_ref": prev.get("resolved_ref")}
                if isinstance(prev.get("resolved_ref"), str)
                else {}
            ),
        }
    lv = (prior_lock or {}).get("lock_version", 1)
    return {
        "lock_version": lv,
        "locked_at": ts,
        "entries": new_entries,
    }


_SKILL_GITIGNORE_MANAGER = SkillGitignoreManager()


def _manifest_defaults(manifest_data: dict[str, Any]) -> dict[str, Any]:
    defaults_raw = manifest_data.get("defaults") or {}
    return defaults_raw if isinstance(defaults_raw, dict) else {}


def _render_skill_gitignore(repo_root: Path, manifest_data: dict[str, Any]) -> tuple[str, bool]:
    gitignore_path = repo_root / "core" / "memory" / "skills" / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.is_file() else None
    rendered = _SKILL_GITIGNORE_MANAGER.render(
        existing,
        _SKILL_GITIGNORE_MANAGER.patterns_for_manifest(manifest_data),
    )
    return rendered, existing != rendered


def _default_install_trust(frontmatter: dict[str, Any], source_type: str) -> str:
    source = frontmatter.get("source")
    if source_type in {"local", "path"} and source == "user-stated":
        return "high"
    return "medium"


def _prepare_installed_skill_frontmatter(
    frontmatter: dict[str, Any],
    *,
    slug: str,
    source_type: str,
    trust_override: str | None,
) -> tuple[dict[str, Any], str, str, bool]:
    from ...errors import ValidationError

    normalized = dict(frontmatter)
    normalized["name"] = slug

    description = normalized.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValidationError(
            "Installed skill SKILL.md must define a non-empty frontmatter description"
        )

    effective_trust = trust_override.strip() if isinstance(trust_override, str) else None
    if effective_trust is not None:
        if effective_trust not in SKILL_CREATE_TRUST_LEVELS:
            raise ValidationError(
                f"trust must be one of {sorted(SKILL_CREATE_TRUST_LEVELS)}: {effective_trust}"
            )
        normalized["trust"] = effective_trust
    else:
        existing_trust = normalized.get("trust")
        if isinstance(existing_trust, str) and existing_trust in SKILL_CREATE_TRUST_LEVELS:
            effective_trust = existing_trust
        else:
            effective_trust = _default_install_trust(normalized, source_type)
            normalized["trust"] = effective_trust

    return normalized, description.strip(), effective_trust, normalized != frontmatter


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
        content: Any,
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
        rel_path, abs_path = _resolve_skill_markdown_path(repo, file)
        today = today_str()
        file_exists = abs_path.exists()

        if file_exists:
            repo.check_version_token(rel_path, version_token)
            fm_dict, body = read_with_frontmatter(abs_path)
        else:
            if not create_if_missing:
                flat_rel, _ = resolve_repo_path(repo, f"memory/skills/{file}.md")
                raise NotFoundError(f"Skill file not found: {rel_path} (or legacy path {flat_rel})")
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
        if _is_skill_frontmatter_field(section, fm_dict):
            _update_skill_frontmatter_field(fm_dict, section, content, mode)
        elif section_heading in body:
            string_content = _require_string_section_content(section, content)
            updated_body = (
                _append_markdown_section(body, section, string_content)
                if mode == "append"
                else _replace_markdown_section(body, section, string_content)
            )
            if updated_body is None:
                raise ValidationError(f"Skill section not found: {section_heading}")
            body = updated_body
        else:
            string_content = _require_string_section_content(section, content)
            body = body.rstrip() + f"\n\n{section_heading}\n\n{string_content.strip()}\n"

        fm_dict["last_verified"] = today

        if "trigger" in fm_dict:
            validate_skill_trigger(fm_dict["trigger"], context=f"skill trigger for {rel_path}")

        validate_frontmatter_metadata(fm_dict, context=f"skill frontmatter for {rel_path}")
        commit_msg = f"[skill] Update {section} in {rel_path}"
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
            summary=f"Update skill section {section} in {rel_path}.",
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
        abs_path.parent.mkdir(parents=True, exist_ok=True)
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
        import json

        import yaml  # type: ignore[import-untyped]

        from ...errors import NotFoundError

        repo = get_repo()
        manifest_path = repo.root / "core" / "memory" / "skills" / "SKILLS.yaml"
        lockfile_path = repo.root / "core" / "memory" / "skills" / "SKILLS.lock"

        if not manifest_path.exists():
            raise NotFoundError("Skill manifest not found: core/memory/skills/SKILLS.yaml")

        with open(manifest_path, "r") as f:
            manifest_data: dict[str, Any] = yaml.safe_load(f) or {}
        manifest_defaults = _manifest_defaults(manifest_data)

        lock_data: dict[str, Any] = {}
        if lockfile_path.exists():
            with open(lockfile_path, "r") as f:
                lock_data = yaml.safe_load(f) or {}

        lock_entries = lock_data.get("entries", {})
        skills_list = manifest_data.get("skills", {})
        enriched_skills = {}

        for slug, skill_data in skills_list.items():
            enriched = dict(skill_data) if isinstance(skill_data, dict) else {}
            lock_entry = lock_entries.get(slug, {})
            enriched["effective_deployment_mode"] = resolve_skill_deployment_mode(
                enriched,
                manifest_defaults,
            )

            # Determine lock status
            lock_status = "unlocked"
            if lock_entry:
                skill_dir = repo.root / "core" / "memory" / "skills" / slug
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

        return json.dumps({"result": result_data})

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
        targets: list[str] | None = None,
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
        - targets (optional): distribution targets override; [] disables external projections
        - enabled (optional): true or false (default: true)
        - preview (bool): When true, return preview without writing
        - approval_token (string): Required for apply mode (non-preview)
        """
        import yaml  # type: ignore[import-untyped]

        from ...errors import ValidationError
        from ...guard_pipeline import require_guarded_write_pass
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
            raise ValidationError(f"trust must be one of {sorted(valid_trusts)}: {trust}")

        parse_skill_source(source, ref=ref)

        # Validate description is non-empty
        if not description or not description.strip():
            raise ValidationError("description must be non-empty")

        manifest_path = repo.root / "core" / "memory" / "skills" / "SKILLS.yaml"
        manifest_preview_rel = "core/memory/skills/SKILLS.yaml"
        manifest_stage_rel = "memory/skills/SKILLS.yaml"
        gitignore_preview_rel = "core/memory/skills/.gitignore"
        gitignore_stage_rel = "memory/skills/.gitignore"

        if not manifest_path.exists():
            raise ValidationError("Skill manifest not found: core/memory/skills/SKILLS.yaml")

        with open(manifest_path, "r") as f:
            manifest_data: dict[str, Any] = yaml.safe_load(f) or {}
        manifest_defaults = _manifest_defaults(manifest_data)

        skills_raw = manifest_data.get("skills", {})
        skills: dict[str, Any] = skills_raw if isinstance(skills_raw, dict) else {}

        # Build skill entry
        if deployment_mode is not None and deployment_mode not in DEPLOYMENT_MODES:
            raise ValidationError(
                f"deployment_mode must be one of {sorted(DEPLOYMENT_MODES)}: {deployment_mode}"
            )
        normalized_targets = (
            normalize_distribution_targets(targets, field_name="targets")
            if targets is not None
            else None
        )

        skill_entry: dict[str, Any] = {
            "source": source,
            "trust": trust,
            "description": description.strip(),
        }
        if ref:
            skill_entry["ref"] = ref
        if deployment_mode is not None:
            skill_entry["deployment_mode"] = deployment_mode
        if normalized_targets is not None:
            skill_entry["targets"] = normalized_targets
        if enabled is not None:
            skill_entry["enabled"] = enabled
        effective_deployment_mode = resolve_skill_deployment_mode(skill_entry, manifest_defaults)
        effective_targets = resolve_skill_distribution_targets(
            skill_entry,
            manifest_defaults,
            slug=slug,
        )

        preview_manifest = dict(manifest_data)
        preview_skills = dict(skills)
        preview_skills[slug] = skill_entry
        preview_manifest["skills"] = preview_skills
        _, gitignore_changed = _render_skill_gitignore(repo.root, preview_manifest)

        # Check if this is a new skill
        is_new = slug not in skills

        commit_msg = (
            f"[skill-manifest] Add skill {slug}"
            if is_new
            else f"[skill-manifest] Update skill {slug}"
        )
        operation_arguments = {
            "slug": slug,
            "source": source,
            "trust": trust,
            "description": description,
            "ref": ref,
            "deployment_mode": deployment_mode,
            "targets": targets,
            "enabled": enabled,
        }

        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"{'Add' if is_new else 'Update'} skill entry {slug} in SKILLS.yaml.",
            reasoning="Skill manifest updates are protected because they affect skill resolution and catalog generation.",
            target_files=[
                preview_target(manifest_preview_rel, "create" if is_new else "update"),
                *([preview_target(gitignore_preview_rel, "update")] if gitignore_changed else []),
            ],
            invariant_effects=[
                f"{'Creates a new' if is_new else 'Updates the'} skill entry '{slug}' with source={source}, trust={trust}.",
                f"Effective deployment_mode resolves to {effective_deployment_mode}.",
                f"Effective distribution targets resolve to {effective_targets or []}.",
                "Preserves all other skill entries and manifest structure.",
                (
                    "Refreshes the managed core/memory/skills/.gitignore block to match the manifest."
                    if gitignore_changed
                    else "Leaves the managed core/memory/skills/.gitignore block unchanged."
                ),
                "Does not modify SKILLS.lock (lock freshness is checked at read time).",
            ],
            commit_message=commit_msg,
            resulting_state={
                "slug": slug,
                "source": source,
                "trust": trust,
                "effective_deployment_mode": effective_deployment_mode,
                "effective_targets": effective_targets,
            },
        )

        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_skill_manifest_write",
            operation_arguments=operation_arguments,
        )

        if preview:
            result = MemoryWriteResult(
                files_changed=[
                    manifest_preview_rel,
                    *([gitignore_preview_rel] if gitignore_changed else []),
                ],
                commit_sha=None,
                commit_message=None,
                new_state={
                    "slug": slug,
                    "effective_deployment_mode": effective_deployment_mode,
                    "effective_targets": effective_targets,
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

        manifest_yaml = yaml.dump(
            ordered_manifest,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
        require_guarded_write_pass(
            path=manifest_preview_rel,
            operation="write",
            root=repo.root,
            content=manifest_yaml,
        )
        manifest_path.write_text(manifest_yaml, encoding="utf-8")

        files_changed = [manifest_stage_rel]
        gitignore_content, gitignore_changed = _render_skill_gitignore(repo.root, manifest_data)
        if gitignore_changed:
            require_guarded_write_pass(
                path=gitignore_preview_rel,
                operation="write",
                root=repo.root,
                content=gitignore_content,
            )
            (repo.root / "core" / "memory" / "skills" / ".gitignore").write_text(
                gitignore_content,
                encoding="utf-8",
            )
            files_changed.append(gitignore_stage_rel)

        for rel_path in files_changed:
            repo.add(rel_path)
        commit_result = repo.commit(commit_msg)

        result = MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "slug": slug,
                "source": source,
                "trust": trust,
                "effective_deployment_mode": effective_deployment_mode,
                "effective_targets": effective_targets,
            },
            preview=preview_payload,
        )
        return result.to_json()

    @mcp.tool(
        name="memory_skill_route",
        annotations=_tool_annotations(
            title="Route Skill Triggers",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_skill_route(
        event: str,
        context: dict[str, Any] | None = None,
        include_catalog_fallback: bool = True,
        include_archived: bool = False,
        include_disabled: bool = False,
        max_results: int = 20,
    ) -> str:
        """Resolve explicit skill triggers for an event and return ordered matches.

        Read-only trigger router per skill-trigger-spec.md.
        Frontmatter trigger metadata takes precedence over manifest trigger
        fallback. Catalog fallback contributes triggerless skills only when the
        caller supplies a query or skill_slug in context.

        Parameters:
        - event: Trigger event name (session-start, session-end, etc.)
        - context: Optional routing context with tool_name, project_id,
          interval, condition/conditions, query, and skill_slug keys
        - include_catalog_fallback: Include triggerless catalog matches when
          query or skill_slug is provided
        - include_archived: Include archived skills from _archive/
        - include_disabled: Include skills disabled in SKILLS.yaml
        - max_results: Maximum matches to return (0 = unlimited)
        """
        import json

        repo = get_repo()
        router = TriggerRouter(repo.root)
        result = router.route(
            event,
            context,
            include_catalog_fallback=include_catalog_fallback,
            include_archived=include_archived,
            include_disabled=include_disabled,
            max_results=max_results,
        )
        return json.dumps({"result": result})

    @mcp.tool(
        name="memory_skill_list",
        annotations=_tool_annotations(
            title="List Skills",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_skill_list(
        trust_level: str | None = None,
        source_type: str | None = None,
        enabled: bool | None = None,
        archived: bool = False,
        include_lock_info: bool = True,
        max_results: int = 100,
    ) -> str:
        """Query installed skills with metadata, trust, lock status, and filtering.

        Read-only discovery interface per skill-lifecycle-spec.md.
        Reads SKILLS.yaml manifest and SKILLS.lock to enrich results.
        Falls back to SKILL.md frontmatter for orphan skills (on disk but
        not in manifest).

        Parameters (all optional):
        - trust_level: filter by trust (high, medium, low)
        - source_type: filter by source (local, github, git, path)
        - enabled: filter by enabled state (true/false), omit for all
        - archived: include archived skills from _archive/ (default false)
        - include_lock_info: include content hash and freshness (default true)
        - max_results: limit results (default 100, 0 = unlimited)
        """
        import json

        import yaml

        from ...errors import ValidationError
        from ...frontmatter_utils import read_with_frontmatter

        repo = get_repo()
        skills_dir = repo.root / "core" / "memory" / "skills"

        if not skills_dir.exists():
            raise ValidationError(f"Skills directory not found: {skills_dir}")

        # Validate filter inputs
        if trust_level and trust_level not in {"high", "medium", "low"}:
            raise ValidationError(f"trust_level must be one of high, medium, low: {trust_level}")
        if source_type and source_type not in {"local", "github", "git", "path", "remote"}:
            raise ValidationError(
                f"source_type must be one of local, github, git, path, remote: {source_type}"
            )

        # Load manifest and lock data
        manifest_path = skills_dir / "SKILLS.yaml"
        lockfile_path = skills_dir / "SKILLS.lock"
        has_manifest = manifest_path.exists()

        manifest_data: dict[str, Any] = {}
        if has_manifest:
            with open(manifest_path, "r") as f:
                manifest_data = yaml.safe_load(f) or {}
        manifest_defaults = _manifest_defaults(manifest_data)
        resolve_skill_distribution_targets(None, manifest_defaults)
        distribution_states = (
            _distribution_states_by_slug(SkillDistributor(repo.root).inspect_all())
            if has_manifest
            else {}
        )

        lock_data: dict[str, Any] = {}
        if lockfile_path.exists():
            with open(lockfile_path, "r") as f:
                lock_data = yaml.safe_load(f) or {}

        lock_entries = lock_data.get("entries", {})
        manifest_skills = manifest_data.get("skills", {})

        def _build_skill_entry(skill_dir_path: Path, slug: str, is_archived: bool) -> dict | None:
            """Build a skill entry dict from disk + manifest + lock data."""
            skill_md = skill_dir_path / "SKILL.md"
            if not skill_md.exists():
                return None

            try:
                fm_dict, _ = read_with_frontmatter(skill_md)
            except Exception:
                return None

            manifest_entry_raw = manifest_skills.get(slug, {})
            manifest_entry = manifest_entry_raw if isinstance(manifest_entry_raw, dict) else {}
            lock_entry = lock_entries.get(slug, {})

            # Core fields from frontmatter, enriched by manifest
            entry: dict = {
                "slug": slug,
                "title": fm_dict.get("name", slug),
                "description": (manifest_entry.get("description") or fm_dict.get("description")),
                "source": manifest_entry.get("source", "local"),
                "trust": fm_dict.get("trust", manifest_entry.get("trust")),
                "enabled": manifest_entry.get("enabled", True),
                "archived": is_archived,
                "created": fm_dict.get("created"),
                "last_verified": fm_dict.get("last_verified"),
            }
            if manifest_entry:
                entry["deployment_mode"] = manifest_entry.get("deployment_mode")
                entry["effective_deployment_mode"] = resolve_skill_deployment_mode(
                    manifest_entry,
                    manifest_defaults,
                )
                if "targets" in manifest_entry:
                    entry["targets"] = normalize_distribution_targets(
                        manifest_entry.get("targets"),
                        field_name=f"skills.{slug}.targets",
                    )
                entry["effective_targets"] = resolve_skill_distribution_targets(
                    manifest_entry,
                    manifest_defaults,
                    slug=slug,
                )
                distribution_state = distribution_states.get(slug)
                external_targets = [
                    target for target in entry["effective_targets"] if target != "engram"
                ]
                entry["distribution"] = (
                    distribution_state
                    if distribution_state is not None
                    else (
                        {"status": "needs_attention", "targets": [], "issue_count": 0}
                        if external_targets
                        else {"status": "not_requested", "targets": [], "issue_count": 0}
                    )
                )
            trigger_value = fm_dict.get("trigger")
            if trigger_value is not None:
                entry["trigger"] = trigger_value
                trigger_summary = summarize_skill_trigger(trigger_value)
                if trigger_summary:
                    entry["trigger_summary"] = trigger_summary

            # File stats
            file_count, total_bytes = get_dir_stats(skill_dir_path)
            entry["file_count"] = file_count
            entry["total_bytes"] = total_bytes

            # Lock info (potentially expensive — hash computation)
            if include_lock_info and lock_entry:
                locked_hash = lock_entry.get("content_hash", "")
                current_hash = compute_content_hash(skill_dir_path)
                hash_fresh = bool(current_hash and current_hash == locked_hash)
                entry["lock_info"] = {
                    "locked_at": lock_entry.get("locked_at"),
                    "content_hash": locked_hash,
                    "hash_fresh": hash_fresh,
                    "resolved_ref": lock_entry.get("resolved_ref"),
                }
            elif include_lock_info:
                # No lock entry — skill is unlocked
                entry["lock_info"] = None
            # When include_lock_info=False, omit lock_info entirely

            return entry

        # Collect all skills
        all_skills: list[dict] = []

        # Active skills from disk
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue
            entry = _build_skill_entry(child, child.name, is_archived=False)
            if entry:
                all_skills.append(entry)

        # Also check for manifest entries with missing directories
        if has_manifest:
            for slug in manifest_skills:
                if not any(s["slug"] == slug for s in all_skills):
                    # Manifest entry but no directory — report as missing
                    manifest_entry = manifest_skills[slug]
                    entry = {
                        "slug": slug,
                        "title": slug,
                        "description": manifest_entry.get("description"),
                        "source": manifest_entry.get("source", "local"),
                        "trust": manifest_entry.get("trust"),
                        "deployment_mode": manifest_entry.get("deployment_mode"),
                        "effective_deployment_mode": resolve_skill_deployment_mode(
                            manifest_entry,
                            manifest_defaults,
                        ),
                        "effective_targets": resolve_skill_distribution_targets(
                            manifest_entry,
                            manifest_defaults,
                            slug=slug,
                        ),
                        "enabled": manifest_entry.get("enabled", True),
                        "archived": False,
                        "created": None,
                        "last_verified": None,
                        "file_count": 0,
                        "total_bytes": 0,
                        "_missing_directory": True,
                    }
                    if isinstance(manifest_entry, dict) and "targets" in manifest_entry:
                        entry["targets"] = normalize_distribution_targets(
                            manifest_entry.get("targets"),
                            field_name=f"skills.{slug}.targets",
                        )
                    external_targets = [
                        target for target in entry["effective_targets"] if target != "engram"
                    ]
                    distribution_state = distribution_states.get(slug)
                    entry["distribution"] = (
                        distribution_state
                        if distribution_state is not None
                        else (
                            {"status": "needs_attention", "targets": [], "issue_count": 0}
                            if external_targets
                            else {"status": "not_requested", "targets": [], "issue_count": 0}
                        )
                    )
                    if include_lock_info:
                        entry["lock_info"] = None
                    all_skills.append(entry)

        # Archived skills
        if archived:
            archive_dir = skills_dir / "_archive"
            if archive_dir.exists():
                for child in sorted(archive_dir.iterdir()):
                    if not child.is_dir():
                        continue
                    entry = _build_skill_entry(child, child.name, is_archived=True)
                    if entry:
                        all_skills.append(entry)

        # Apply filters
        filtered = all_skills

        if trust_level:
            filtered = [s for s in filtered if s.get("trust") == trust_level]

        if source_type:
            if source_type == "remote":
                filtered = [s for s in filtered if s.get("source") != "local"]
            elif source_type == "local":
                filtered = [s for s in filtered if s.get("source") == "local"]
            else:
                # Match source prefix: github, git, path
                filtered = [s for s in filtered if s.get("source", "").startswith(source_type)]

        if enabled is not None:
            filtered = [s for s in filtered if s.get("enabled") == enabled]

        # Apply max_results
        total_count = len(filtered)
        if max_results > 0:
            filtered = filtered[:max_results]

        return json.dumps(
            {
                "result": {
                    "skills": filtered,
                    "total_count": total_count,
                    "filters_applied": {
                        "trust_level": trust_level,
                        "source_type": source_type,
                        "enabled": enabled,
                        "archived": archived,
                    },
                }
            }
        )

    @mcp.tool(
        name="memory_skill_add",
        annotations=_tool_annotations(
            title="Add Skill",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_skill_add(
        slug: str,
        title: str,
        description: str,
        source: str,
        trust: str,
        origin_session: str,
        ref: str | None = None,
        enabled: bool | None = None,
        deployment_mode: str | None = None,
        targets: list[str] | None = None,
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Create a new skill directory, register it in SKILLS.yaml, refresh SKILLS.lock and indexes.

        Supported `source` values:
        - `template` — empty scaffold with valid frontmatter under core/memory/skills/{slug}/.
        - `path:./relative/path` — copy an existing skill directory from the repo (must contain SKILL.md).

        Remote installs (`github:`, `git:`) are not implemented yet; use template or path sources.

        Uses the governed preview-then-apply pattern (protected tier).
        """
        import json

        import yaml

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
        _validate_skill_kebab_slug(slug)
        validate_session_id(origin_session)

        if trust not in SKILL_CREATE_TRUST_LEVELS:
            raise ValidationError(
                f"trust must be one of {sorted(SKILL_CREATE_TRUST_LEVELS)}: {trust}"
            )
        if not title.strip():
            raise ValidationError("title must be non-empty")
        if not description.strip():
            raise ValidationError("description must be non-empty")
        if deployment_mode is not None and deployment_mode not in DEPLOYMENT_MODES:
            raise ValidationError(
                f"deployment_mode must be one of {sorted(DEPLOYMENT_MODES)}: {deployment_mode}"
            )
        normalized_targets = (
            normalize_distribution_targets(targets, field_name="targets")
            if targets is not None
            else None
        )

        src = source.strip()
        if src in ("github:", "git:") or src.startswith("github:") or src.startswith("git:"):
            raise ValidationError(
                "memory_skill_add does not install from remote sources yet; "
                "use source='template' or path:./..."
            )
        if ref:
            raise ValidationError(
                "ref is not supported until remote installs are implemented; omit ref for template/path sources."
            )

        manifest_path = repo.root / "core" / "memory" / "skills" / "SKILLS.yaml"
        lock_path = repo.root / "core" / "memory" / "skills" / "SKILLS.lock"
        skills_dir = repo.root / "core" / "memory" / "skills"
        skill_dir = skills_dir / slug
        skill_rel = f"core/memory/skills/{slug}"
        skill_md_rel = f"{skill_rel}/SKILL.md"
        skill_content_rel = f"memory/skills/{slug}"
        skill_md_content_rel = f"{skill_content_rel}/SKILL.md"
        manifest_stage_rel = "memory/skills/SKILLS.yaml"
        lock_stage_rel = "memory/skills/SKILLS.lock"
        tree_stage_rel = "memory/skills/SKILL_TREE.md"
        summary_stage_rel = "memory/skills/SUMMARY.md"
        gitignore_preview_rel = "core/memory/skills/.gitignore"
        gitignore_stage_rel = "memory/skills/.gitignore"

        if not manifest_path.is_file():
            raise NotFoundError("Skill manifest not found: core/memory/skills/SKILLS.yaml")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data: dict[str, Any] = yaml.safe_load(f) or {}
        manifest_defaults = _manifest_defaults(manifest_data)
        skills_raw = manifest_data.get("skills", {})
        skills_map: dict[str, Any] = skills_raw if isinstance(skills_raw, dict) else {}
        if slug in skills_map:
            raise ValidationError(
                f"Skill slug already registered in manifest: {slug}. "
                "Remove or rename the existing entry first."
            )
        if skill_dir.exists():
            raise ValidationError(
                f"Skill directory already exists: {skill_rel}/. "
                "Choose a different slug or remove the directory first."
            )

        manifest_source = "local"
        lock_source = "local"
        today = today_str()

        if src == "template":
            body = (
                f"# {title.strip()}\n\n"
                "## When to use this skill\n\n"
                "(To be written.)\n\n"
                "## Steps\n\n"
                "(To be written.)\n\n"
                "## Examples\n\n"
                "(To be written.)\n"
            )
            fm_dict: dict[str, Any] = {
                "name": slug,
                "description": description.strip(),
                "source": "template",
                "origin_session": origin_session,
                "created": today,
                "last_verified": today,
                "trust": trust,
            }
        elif re.match(r"^path:\./.+$", src):
            rel = src[len("path:") :].lstrip("./")
            src_dir = (repo.root / rel).resolve()
            try:
                src_dir.relative_to(repo.root.resolve())
            except ValueError as e:
                raise ValidationError(f"path source must stay within the repository: {src}") from e
            if not src_dir.is_dir():
                raise NotFoundError(f"path source directory not found: {src}")
            skill_md = src_dir / "SKILL.md"
            if not skill_md.is_file():
                raise ValidationError(f"path source must contain SKILL.md: {src}")
            fm_existing, _ = read_with_frontmatter(skill_md)
            fm_trust = fm_existing.get("trust")
            if fm_trust != trust:
                raise ValidationError(
                    f"path skill SKILL.md trust is {fm_trust!r} but trust parameter is {trust!r}; "
                    "they must match."
                )
            manifest_source = src
            lock_source = src
        else:
            raise ValidationError(
                f"Unsupported source {source!r}. Use 'template' or path:./relative/path under the repo."
            )

        enabled_flag = True if enabled is None else enabled
        skill_entry: dict[str, Any] = {
            "source": manifest_source,
            "trust": trust,
            "description": description.strip(),
            "enabled": enabled_flag,
        }
        if deployment_mode is not None:
            skill_entry["deployment_mode"] = deployment_mode
        if normalized_targets is not None:
            skill_entry["targets"] = normalized_targets
        effective_deployment_mode = resolve_skill_deployment_mode(skill_entry, manifest_defaults)
        effective_targets = resolve_skill_distribution_targets(
            skill_entry,
            manifest_defaults,
            slug=slug,
        )

        preview_manifest = dict(manifest_data)
        preview_skills = dict(skills_map)
        preview_skills[slug] = skill_entry
        preview_manifest["skills"] = preview_skills
        _, gitignore_changed = _render_skill_gitignore(repo.root, preview_manifest)

        operation_arguments: dict[str, Any] = {
            "slug": slug,
            "title": title,
            "description": description,
            "source": source,
            "trust": trust,
            "origin_session": origin_session,
            "ref": ref,
            "enabled": enabled,
            "deployment_mode": deployment_mode,
            "targets": targets,
        }

        target_files = [
            preview_target(skill_md_rel, "create"),
            preview_target("core/memory/skills/SKILLS.yaml", "update"),
            preview_target("core/memory/skills/SKILLS.lock", "update"),
            preview_target("core/memory/skills/SKILL_TREE.md", "update"),
        ]
        if gitignore_changed:
            target_files.append(preview_target(gitignore_preview_rel, "update"))
        summary_updated = False
        summary_preview = _append_skill_summary_bullet(repo.root, slug, description)
        if summary_preview is not None:
            target_files.append(preview_target("core/memory/skills/SUMMARY.md", "update"))
            summary_updated = True

        commit_msg = f"[skill] Add skill {slug}"
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"Create skill {slug} and register it in the skill manifest.",
            reasoning="Skill directories and manifests are protected-tier procedural assets.",
            target_files=target_files,
            invariant_effects=[
                f"Creates {skill_rel}/ with SKILL.md and adds manifest entry.",
                f"Effective deployment_mode resolves to {effective_deployment_mode}.",
                f"Effective distribution targets resolve to {effective_targets or []}.",
                "Refreshes SKILLS.lock, SKILL_TREE.md"
                + (
                    ", SUMMARY.md, and the managed core/memory/skills/.gitignore block."
                    if summary_updated and gitignore_changed
                    else ", SUMMARY.md."
                    if summary_updated
                    else ", and the managed core/memory/skills/.gitignore block."
                    if gitignore_changed
                    else "."
                ),
                (
                    f"Leaves {skill_rel}/ local-only when deployment_mode resolves to gitignored."
                    if effective_deployment_mode == "gitignored"
                    else f"Stages {skill_rel}/ for commit when deployment_mode resolves to checked."
                ),
            ],
            commit_message=commit_msg,
            resulting_state={
                "slug": slug,
                "source": source,
                "effective_deployment_mode": effective_deployment_mode,
                "effective_targets": effective_targets,
            },
        )
        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_skill_add",
            operation_arguments=operation_arguments,
        )

        if preview:
            return MemoryWriteResult(
                files_changed=[
                    skill_md_rel,
                    "core/memory/skills/SKILLS.yaml",
                    "core/memory/skills/SKILLS.lock",
                    "core/memory/skills/SKILL_TREE.md",
                    *([gitignore_preview_rel] if gitignore_changed else []),
                    *(["core/memory/skills/SUMMARY.md"] if summary_updated else []),
                ],
                commit_sha=None,
                commit_message=None,
                new_state={
                    "slug": slug,
                    "effective_deployment_mode": effective_deployment_mode,
                    "effective_targets": effective_targets,
                    "approval_token": protected_token,
                },
                preview=preview_payload,
            ).to_json()

        require_approval_token(
            repo,
            tool_name="memory_skill_add",
            operation_arguments=operation_arguments,
            approval_token=approval_token,
        )

        # --- apply ---
        skill_dir.mkdir(parents=True, exist_ok=True)
        if src == "template":
            if "trigger" in fm_dict:
                validate_skill_trigger(
                    fm_dict["trigger"], context=f"skill trigger for {skill_md_rel}"
                )
            validate_frontmatter_metadata(fm_dict, context=f"skill frontmatter for {skill_md_rel}")
            rendered = render_with_frontmatter(fm_dict, body)
            require_guarded_write_pass(
                path=skill_md_rel,
                operation="write",
                root=repo.root,
                content=rendered,
            )
            write_with_frontmatter(skill_dir / "SKILL.md", fm_dict, body)
        else:
            shutil.copytree(src_dir, skill_dir, dirs_exist_ok=False)
            fm_disk, _body_disk = read_with_frontmatter(skill_dir / "SKILL.md")
            if "trigger" in fm_disk:
                validate_skill_trigger(
                    fm_disk["trigger"], context=f"skill trigger for {skill_md_rel}"
                )
            validate_frontmatter_metadata(fm_disk, context=f"skill frontmatter for {skill_md_rel}")

        skills_map[slug] = skill_entry
        manifest_data["skills"] = skills_map
        ordered_manifest: dict[str, Any] = {}
        for key in ("schema_version", "defaults", "skills"):
            if key in manifest_data:
                ordered_manifest[key] = manifest_data[key]
        manifest_yaml = yaml.dump(
            ordered_manifest, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        require_guarded_write_pass(
            path="core/memory/skills/SKILLS.yaml",
            operation="write",
            root=repo.root,
            content=manifest_yaml,
        )
        manifest_path.write_text(manifest_yaml, encoding="utf-8")

        gitignore_content, gitignore_changed = _render_skill_gitignore(repo.root, manifest_data)
        if gitignore_changed:
            require_guarded_write_pass(
                path=gitignore_preview_rel,
                operation="write",
                root=repo.root,
                content=gitignore_content,
            )
            (skills_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        lock_data: dict[str, Any] = {}
        if lock_path.is_file():
            with open(lock_path, "r", encoding="utf-8") as f:
                lock_data = yaml.safe_load(f) or {}
        entries = lock_data.setdefault("entries", {})
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        content_hash = compute_content_hash(skill_dir)
        fc, tb = get_dir_stats(skill_dir)
        entries[slug] = {
            "source": lock_source,
            "resolved_path": f"core/memory/skills/{slug}/",
            "content_hash": content_hash,
            "locked_at": ts,
            "file_count": fc,
            "total_bytes": tb,
        }
        lock_data["lock_version"] = lock_data.get("lock_version", 1)
        lock_data["locked_at"] = ts
        lock_yaml = yaml.dump(
            lock_data, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        require_guarded_write_pass(
            path="core/memory/skills/SKILLS.lock",
            operation="write",
            root=repo.root,
            content=lock_yaml,
        )
        lock_path.write_text(lock_yaml, encoding="utf-8")

        tree_content = _regenerate_skill_tree_content(repo.root)
        require_guarded_write_pass(
            path="core/memory/skills/SKILL_TREE.md",
            operation="write",
            root=repo.root,
            content=tree_content,
        )
        (repo.root / "core" / "memory" / "skills" / "SKILL_TREE.md").write_text(
            tree_content, encoding="utf-8"
        )

        if src == "template":
            local_skill_artifacts = [skill_md_content_rel]
        else:
            local_skill_artifacts = [
                str(f.relative_to(repo.content_root)).replace("\\", "/")
                for f in sorted(skill_dir.rglob("*"))
                if f.is_file()
            ]
        staged_skill_files = (
            [] if effective_deployment_mode == "gitignored" else list(local_skill_artifacts)
        )
        files_to_commit = [
            *staged_skill_files,
            manifest_stage_rel,
            lock_stage_rel,
            tree_stage_rel,
        ]
        artifacts_updated = [*local_skill_artifacts, *files_to_commit]
        if gitignore_changed:
            files_to_commit.append(gitignore_stage_rel)
            artifacts_updated.append(gitignore_stage_rel)
        if summary_preview is not None:
            require_guarded_write_pass(
                path="core/memory/skills/SUMMARY.md",
                operation="write",
                root=repo.root,
                content=summary_preview,
            )
            (repo.root / "core" / "memory" / "skills" / "SUMMARY.md").write_text(
                summary_preview, encoding="utf-8"
            )
            files_to_commit.append(summary_stage_rel)
            artifacts_updated.append(summary_stage_rel)

        for rel in sorted(set(files_to_commit)):
            repo.add(rel)
        commit_result = repo.commit(commit_msg)

        lock_entry = entries[slug]
        result_body = {
            "slug": slug,
            "status": "created",
            "location": f"{skill_rel}/",
            "manifest_entry": skill_entry,
            "effective_deployment_mode": effective_deployment_mode,
            "effective_targets": effective_targets,
            "lock_entry": lock_entry,
            "artifacts_updated": sorted(set(artifacts_updated)),
        }
        mw = MemoryWriteResult.from_commit(
            files_changed=sorted(set(files_to_commit)),
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "slug": slug,
                "effective_deployment_mode": effective_deployment_mode,
                "effective_targets": effective_targets,
            },
            preview=preview_payload,
        )
        out = mw.to_dict()
        out["result"] = result_body
        return json.dumps(out, indent=2)

    @mcp.tool(
        name="memory_skill_install",
        annotations=_tool_annotations(
            title="Install Skill",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_skill_install(
        source: str,
        slug: str | None = None,
        ref: str | None = None,
        trust: str | None = None,
        enabled: bool | None = None,
        targets: list[str] | None = None,
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Resolve and install a skill from local, path, git, or GitHub sources.

        Uses SkillResolver to discover the source, copies the resolved skill into
        core/memory/skills/{slug}/ when needed, then updates SKILLS.yaml,
        SKILLS.lock, SKILL_TREE.md, and SUMMARY.md under the protected
        preview-then-apply flow.

        Parameters:
        - source: Source string (local, path:./..., path:../..., github:owner/repo, git:url)
        - slug: Optional installed skill slug override. Required for source=local.
        - ref: Optional git/github ref pin.
        - trust: Optional trust override written into the installed SKILL.md and manifest.
        - enabled: Optional manifest enabled flag (default true).
        - preview: When true, return the governed preview envelope.
        - approval_token: Fresh preview-issued approval receipt for apply mode.
        """
        import json

        import yaml  # type: ignore[import-untyped]

        from ...errors import NotFoundError, ValidationError
        from ...frontmatter_utils import (
            read_with_frontmatter,
            render_with_frontmatter,
            write_with_frontmatter,
        )
        from ...guard_pipeline import require_guarded_write_pass
        from ...models import MemoryWriteResult

        repo = get_repo()
        if slug is not None:
            _validate_skill_kebab_slug(slug)
        if trust is not None and trust not in SKILL_CREATE_TRUST_LEVELS:
            raise ValidationError(
                f"trust must be one of {sorted(SKILL_CREATE_TRUST_LEVELS)}: {trust}"
            )
        normalized_targets = (
            normalize_distribution_targets(targets, field_name="targets")
            if targets is not None
            else None
        )

        manifest_path = repo.root / "core" / "memory" / "skills" / "SKILLS.yaml"
        lock_path = repo.root / "core" / "memory" / "skills" / "SKILLS.lock"
        skills_dir = repo.root / "core" / "memory" / "skills"

        if not manifest_path.is_file():
            raise NotFoundError("Skill manifest not found: core/memory/skills/SKILLS.yaml")

        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest_data: dict[str, Any] = yaml.safe_load(handle) or {}
        manifest_defaults = _manifest_defaults(manifest_data)
        manifest_skills_raw = manifest_data.get("skills") or {}
        skills_map: dict[str, Any] = (
            manifest_skills_raw if isinstance(manifest_skills_raw, dict) else {}
        )

        lock_data: dict[str, Any] = {}
        if lock_path.is_file():
            with open(lock_path, "r", encoding="utf-8") as handle:
                lock_data = yaml.safe_load(handle) or {}
        lock_entries_raw = lock_data.get("entries") or {}
        lock_entries: dict[str, Any] = (
            lock_entries_raw if isinstance(lock_entries_raw, dict) else {}
        )

        resolver = SkillResolver(repo.root)
        existing_lock_entry = lock_entries.get(slug) if isinstance(slug, str) else None
        resolved = resolver.resolve(source, slug=slug, ref=ref, lock_entry=existing_lock_entry)

        target_slug = slug or resolved.slug
        _validate_skill_kebab_slug(target_slug)
        if target_slug in skills_map:
            raise ValidationError(
                f"Skill slug already registered in manifest: {target_slug}. "
                "Remove or rename the existing entry first."
            )

        skill_dir = skills_dir / target_slug
        skill_rel = f"core/memory/skills/{target_slug}"
        skill_md_rel = f"{skill_rel}/SKILL.md"
        if resolved.source_type != "local" and skill_dir.exists():
            raise ValidationError(
                f"Skill directory already exists: {skill_rel}/. Choose a different slug or remove the directory first."
            )

        source_skill_md = resolved.skill_dir / "SKILL.md"
        fm_dict, body = read_with_frontmatter(source_skill_md)
        normalized_fm, manifest_description, effective_trust, frontmatter_changed = (
            _prepare_installed_skill_frontmatter(
                fm_dict,
                slug=target_slug,
                source_type=resolved.source_type,
                trust_override=trust,
            )
        )
        if "trigger" in normalized_fm:
            validate_skill_trigger(
                normalized_fm["trigger"], context=f"skill trigger for {skill_md_rel}"
            )
        validate_frontmatter_metadata(
            normalized_fm, context=f"skill frontmatter for {skill_md_rel}"
        )

        enabled_flag = True if enabled is None else enabled
        skill_entry: dict[str, Any] = {
            "source": resolved.normalized_source,
            "trust": effective_trust,
            "description": manifest_description,
            "enabled": enabled_flag,
        }
        if ref:
            skill_entry["ref"] = ref
        if normalized_targets is not None:
            skill_entry["targets"] = normalized_targets
        effective_deployment_mode = resolve_skill_deployment_mode(skill_entry, manifest_defaults)
        effective_targets = resolve_skill_distribution_targets(
            skill_entry,
            manifest_defaults,
            slug=target_slug,
        )

        preview_manifest = dict(manifest_data)
        preview_skills = dict(skills_map)
        preview_skills[target_slug] = skill_entry
        preview_manifest["skills"] = preview_skills
        _, gitignore_changed = _render_skill_gitignore(repo.root, preview_manifest)

        summary_preview = _append_skill_summary_bullet(repo.root, target_slug, manifest_description)
        preview_targets = [
            preview_target("core/memory/skills/SKILLS.yaml", "update"),
            preview_target("core/memory/skills/SKILLS.lock", "update"),
            preview_target("core/memory/skills/SKILL_TREE.md", "update"),
        ]
        if gitignore_changed:
            preview_targets.append(preview_target("core/memory/skills/.gitignore", "update"))
        if resolved.source_type == "local":
            if frontmatter_changed:
                preview_targets.insert(0, preview_target(skill_md_rel, "update"))
        else:
            preview_targets.insert(0, preview_target(skill_md_rel, "create"))
        if summary_preview is not None:
            preview_targets.append(preview_target("core/memory/skills/SUMMARY.md", "update"))

        operation_arguments: dict[str, Any] = {
            "source": source,
            "slug": slug,
            "ref": ref,
            "trust": trust,
            "enabled": enabled,
            "targets": targets,
        }
        commit_msg = f"[skill] Install skill {target_slug}"
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"Install skill {target_slug} from {resolved.normalized_source}.",
            reasoning="Installing skills mutates protected skill directories, the manifest, and the lockfile.",
            target_files=preview_targets,
            invariant_effects=[
                (
                    f"Registers {target_slug} in SKILLS.yaml with source={resolved.normalized_source} "
                    f"and effective deployment_mode={effective_deployment_mode}."
                ),
                f"Effective distribution targets resolve to {effective_targets or []}.",
                "Refreshes SKILLS.lock, SKILL_TREE.md"
                + (
                    ", SUMMARY.md, and the managed core/memory/skills/.gitignore block."
                    if summary_preview is not None and gitignore_changed
                    else ", SUMMARY.md."
                    if summary_preview is not None
                    else ", and the managed core/memory/skills/.gitignore block."
                    if gitignore_changed
                    else "."
                ),
                (
                    f"Copies resolved skill contents from {resolved.source_type} source into {skill_rel}/."
                    if resolved.source_type != "local"
                    else f"Uses the existing local skill directory {skill_rel}/."
                ),
                (
                    f"Leaves {skill_rel}/ local-only when deployment_mode resolves to gitignored."
                    if effective_deployment_mode == "gitignored"
                    else f"Stages {skill_rel}/ for commit when deployment_mode resolves to checked."
                ),
            ],
            commit_message=commit_msg,
            resulting_state={
                "slug": target_slug,
                "source": resolved.normalized_source,
                "resolved_ref": resolved.resolved_ref,
                "effective_deployment_mode": effective_deployment_mode,
                "effective_targets": effective_targets,
            },
        )
        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_skill_install",
            operation_arguments=operation_arguments,
        )

        if preview:
            preview_files = [
                *([skill_md_rel] if resolved.source_type != "local" or frontmatter_changed else []),
                "core/memory/skills/SKILLS.yaml",
                "core/memory/skills/SKILLS.lock",
                "core/memory/skills/SKILL_TREE.md",
                *(["core/memory/skills/.gitignore"] if gitignore_changed else []),
                *(["core/memory/skills/SUMMARY.md"] if summary_preview is not None else []),
            ]
            return MemoryWriteResult(
                files_changed=preview_files,
                commit_sha=None,
                commit_message=None,
                new_state={
                    "slug": target_slug,
                    "effective_targets": effective_targets,
                    "approval_token": protected_token,
                },
                preview=preview_payload,
            ).to_json()

        require_approval_token(
            repo,
            tool_name="memory_skill_install",
            operation_arguments=operation_arguments,
            approval_token=approval_token,
        )

        installed_skill_dir = resolved.skill_dir if resolved.source_type == "local" else skill_dir
        if resolved.source_type != "local":
            shutil.copytree(
                resolved.skill_dir,
                installed_skill_dir,
                dirs_exist_ok=False,
                ignore=shutil.ignore_patterns(".git", ".svn", ".hg"),
            )

        installed_skill_md = installed_skill_dir / "SKILL.md"
        if resolved.source_type != "local" or frontmatter_changed:
            rendered = render_with_frontmatter(normalized_fm, body)
            require_guarded_write_pass(
                path=skill_md_rel,
                operation="write",
                root=repo.root,
                content=rendered,
            )
            write_with_frontmatter(installed_skill_md, normalized_fm, body)

        skills_map[target_slug] = skill_entry
        manifest_data["skills"] = skills_map
        ordered_manifest: dict[str, Any] = {}
        for key in ("schema_version", "defaults", "skills"):
            if key in manifest_data:
                ordered_manifest[key] = manifest_data[key]
        manifest_yaml = yaml.dump(
            ordered_manifest, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        require_guarded_write_pass(
            path="core/memory/skills/SKILLS.yaml",
            operation="write",
            root=repo.root,
            content=manifest_yaml,
        )
        manifest_path.write_text(manifest_yaml, encoding="utf-8")

        gitignore_content, gitignore_changed = _render_skill_gitignore(repo.root, manifest_data)
        if gitignore_changed:
            require_guarded_write_pass(
                path="core/memory/skills/.gitignore",
                operation="write",
                root=repo.root,
                content=gitignore_content,
            )
            (skills_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        content_hash = compute_content_hash(installed_skill_dir)
        file_count, total_bytes = get_dir_stats(installed_skill_dir)
        lock_entries[target_slug] = {
            "source": resolved.normalized_source,
            "resolved_path": f"core/memory/skills/{target_slug}/",
            "content_hash": content_hash,
            "locked_at": ts,
            "file_count": file_count,
            "total_bytes": total_bytes,
            **({"requested_ref": resolved.requested_ref} if resolved.requested_ref else {}),
            **({"resolved_ref": resolved.resolved_ref} if resolved.resolved_ref else {}),
        }
        lock_data["entries"] = lock_entries
        lock_data["lock_version"] = lock_data.get("lock_version", 1)
        lock_data["locked_at"] = ts
        lock_yaml = yaml.dump(
            lock_data, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        require_guarded_write_pass(
            path="core/memory/skills/SKILLS.lock",
            operation="write",
            root=repo.root,
            content=lock_yaml,
        )
        lock_path.write_text(lock_yaml, encoding="utf-8")

        tree_content = _regenerate_skill_tree_content(repo.root)
        require_guarded_write_pass(
            path="core/memory/skills/SKILL_TREE.md",
            operation="write",
            root=repo.root,
            content=tree_content,
        )
        (repo.root / "core" / "memory" / "skills" / "SKILL_TREE.md").write_text(
            tree_content, encoding="utf-8"
        )

        skill_content_rel = f"memory/skills/{target_slug}"
        skill_md_content_rel = f"{skill_content_rel}/SKILL.md"
        local_skill_artifacts: list[str]
        if resolved.source_type != "local":
            local_skill_artifacts = [
                str(path.relative_to(repo.content_root)).replace("\\", "/")
                for path in sorted(installed_skill_dir.rglob("*"))
                if path.is_file()
            ]
        elif frontmatter_changed:
            local_skill_artifacts = [skill_md_content_rel]
        else:
            local_skill_artifacts = []

        staged_skill_files: list[str]
        if effective_deployment_mode == "gitignored":
            if (
                resolved.source_type == "local"
                and frontmatter_changed
                and repo.is_tracked(skill_md_content_rel)
            ):
                staged_skill_files = [skill_md_content_rel]
            else:
                staged_skill_files = []
        elif resolved.source_type != "local":
            staged_skill_files = list(local_skill_artifacts)
        elif frontmatter_changed:
            staged_skill_files = [skill_md_content_rel]
        else:
            staged_skill_files = []

        files_to_commit = [
            *staged_skill_files,
            "memory/skills/SKILLS.yaml",
            "memory/skills/SKILLS.lock",
            "memory/skills/SKILL_TREE.md",
        ]
        artifacts_updated = [*local_skill_artifacts, *files_to_commit]
        if gitignore_changed:
            files_to_commit.append("memory/skills/.gitignore")
            artifacts_updated.append("memory/skills/.gitignore")

        if summary_preview is not None:
            require_guarded_write_pass(
                path="core/memory/skills/SUMMARY.md",
                operation="write",
                root=repo.root,
                content=summary_preview,
            )
            (repo.root / "core" / "memory" / "skills" / "SUMMARY.md").write_text(
                summary_preview, encoding="utf-8"
            )
            files_to_commit.append("memory/skills/SUMMARY.md")
            artifacts_updated.append("memory/skills/SUMMARY.md")

        for rel_path in sorted(set(files_to_commit)):
            repo.add(rel_path)
        commit_result = repo.commit(commit_msg)

        result_body = {
            "slug": target_slug,
            "status": "installed",
            "location": f"{skill_rel}/",
            "manifest_entry": skill_entry,
            "effective_deployment_mode": effective_deployment_mode,
            "effective_targets": effective_targets,
            "lock_entry": lock_entries[target_slug],
            "resolution": {
                "source": resolved.normalized_source,
                "source_type": resolved.source_type,
                "requested_ref": resolved.requested_ref,
                "resolved_ref": resolved.resolved_ref,
                "resolution_mode": resolved.resolution_mode,
                "lock_verification": (
                    {
                        "checked": resolved.lock_verification.checked,
                        "usable": resolved.lock_verification.usable,
                        "source_matches": resolved.lock_verification.source_matches,
                        "hash_matches": resolved.lock_verification.hash_matches,
                        "ref_matches": resolved.lock_verification.ref_matches,
                    }
                    if resolved.lock_verification is not None
                    else None
                ),
            },
            "artifacts_updated": sorted(set(artifacts_updated)),
        }
        mw = MemoryWriteResult.from_commit(
            files_changed=sorted(set(files_to_commit)),
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "slug": target_slug,
                "resolved_ref": resolved.resolved_ref,
                "effective_deployment_mode": effective_deployment_mode,
                "effective_targets": effective_targets,
            },
            preview=preview_payload,
        )
        out = mw.to_dict()
        out["result"] = result_body
        return json.dumps(out, indent=2)

    @mcp.tool(
        name="memory_skill_remove",
        annotations=_tool_annotations(
            title="Archive Skill",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_skill_remove(
        slug: str,
        archive_reason: str | None = None,
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Archive a skill to _archive/, remove manifest and lock entries, refresh indexes.

        Uses the governed preview-then-apply pattern (protected tier).
        """
        import json

        import yaml

        from ...errors import NotFoundError, ValidationError
        from ...guard_pipeline import require_guarded_write_pass
        from ...models import MemoryWriteResult

        repo = get_repo()
        _validate_skill_kebab_slug(slug)

        manifest_path = repo.root / "core" / "memory" / "skills" / "SKILLS.yaml"
        lock_path = repo.root / "core" / "memory" / "skills" / "SKILLS.lock"
        skills_dir = repo.root / "core" / "memory" / "skills"
        skill_dir = skills_dir / slug
        archive_parent = skills_dir / "_archive"
        archive_dir = archive_parent / slug
        skill_preview_rel = f"core/memory/skills/{slug}"
        archive_preview_rel = f"core/memory/skills/_archive/{slug}"
        skill_stage_rel = f"memory/skills/{slug}"
        archive_stage_rel = f"memory/skills/_archive/{slug}"
        manifest_preview_rel = "core/memory/skills/SKILLS.yaml"
        manifest_stage_rel = "memory/skills/SKILLS.yaml"
        lock_preview_rel = "core/memory/skills/SKILLS.lock"
        lock_stage_rel = "memory/skills/SKILLS.lock"
        tree_preview_rel = "core/memory/skills/SKILL_TREE.md"
        tree_stage_rel = "memory/skills/SKILL_TREE.md"
        summary_preview_rel = "core/memory/skills/SUMMARY.md"
        summary_stage_rel = "memory/skills/SUMMARY.md"
        gitignore_preview_rel = "core/memory/skills/.gitignore"
        gitignore_stage_rel = "memory/skills/.gitignore"

        if not manifest_path.is_file():
            raise NotFoundError("Skill manifest not found: core/memory/skills/SKILLS.yaml")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data: dict[str, Any] = yaml.safe_load(f) or {}
        skills_raw = manifest_data.get("skills", {})
        skills_map: dict[str, Any] = skills_raw if isinstance(skills_raw, dict) else {}
        in_manifest = slug in skills_map
        had_dir = skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file()

        if not in_manifest and not had_dir:
            raise NotFoundError(
                f"Skill not found in manifest or on disk: {slug}. "
                "Use memory_skill_list to list installed skills."
            )

        if had_dir and archive_dir.exists():
            raise ValidationError(
                f"Archive target already exists: {archive_preview_rel}/. "
                "Remove or rename the archived copy first."
            )

        removed_manifest = skills_map.get(slug)
        preview_manifest = dict(manifest_data)
        preview_skills = dict(skills_map)
        if slug in preview_skills:
            del preview_skills[slug]
        preview_manifest["skills"] = preview_skills
        _, gitignore_changed = _render_skill_gitignore(repo.root, preview_manifest)
        operation_arguments: dict[str, Any] = {
            "slug": slug,
            "archive_reason": archive_reason,
        }

        target_files: list[dict[str, Any]] = []
        if had_dir:
            target_files.extend(
                [
                    preview_target(skill_preview_rel, "move_from"),
                    preview_target(
                        archive_preview_rel,
                        "move_to",
                        from_path=skill_preview_rel,
                    ),
                ]
            )
        if in_manifest:
            target_files.append(preview_target(manifest_preview_rel, "update"))
        lock_has_slug = False
        if lock_path.is_file():
            with open(lock_path, "r", encoding="utf-8") as lf:
                lock_preview = yaml.safe_load(lf) or {}
            lock_has_slug = slug in (lock_preview.get("entries") or {})
        if lock_has_slug:
            target_files.append(preview_target(lock_preview_rel, "update"))
        target_files.append(preview_target(tree_preview_rel, "update"))
        summary_path = repo.root / "core" / "memory" / "skills" / "SUMMARY.md"
        summary_changed = summary_path.is_file() and f"({slug}/SKILL.md)" in summary_path.read_text(
            encoding="utf-8"
        )
        if summary_changed:
            target_files.append(preview_target(summary_preview_rel, "update"))
        if gitignore_changed:
            target_files.append(preview_target(gitignore_preview_rel, "update"))
        if had_dir:
            target_files.append(
                preview_target("core/memory/skills/_archive/ARCHIVE_INDEX.md", "update")
            )

        commit_msg = f"[skill] Archive skill {slug}"
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"Archive skill {slug} and remove manifest entry.",
            reasoning="Archival changes the active skill catalog and manifest; protected tier.",
            target_files=target_files,
            invariant_effects=[
                f"Moves {skill_preview_rel}/ to {archive_preview_rel}/ when a skill directory exists.",
                "Removes manifest and lock entries for the slug when present.",
                (
                    "Refreshes the managed core/memory/skills/.gitignore block to match the manifest."
                    if gitignore_changed
                    else "Leaves the managed core/memory/skills/.gitignore block unchanged."
                ),
                "Regenerates SKILL_TREE.md; updates archive index when a directory is archived.",
            ],
            commit_message=commit_msg,
            resulting_state={
                "slug": slug,
                "deployment_gitignore_refreshed": gitignore_changed,
            },
        )
        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_skill_remove",
            operation_arguments=operation_arguments,
        )

        preview_files: list[str] = [tree_preview_rel]
        if in_manifest:
            preview_files.append(manifest_preview_rel)
        if lock_has_slug:
            preview_files.append(lock_preview_rel)
        if had_dir:
            preview_files = [skill_preview_rel, archive_preview_rel, *preview_files]
        if summary_changed:
            preview_files.append(summary_preview_rel)
        if gitignore_changed:
            preview_files.append(gitignore_preview_rel)
        if had_dir:
            preview_files.append("core/memory/skills/_archive/ARCHIVE_INDEX.md")

        if preview:
            return MemoryWriteResult(
                files_changed=preview_files,
                commit_sha=None,
                commit_message=None,
                new_state={"slug": slug, "approval_token": protected_token},
                preview=preview_payload,
            ).to_json()

        require_approval_token(
            repo,
            tool_name="memory_skill_remove",
            operation_arguments=operation_arguments,
            approval_token=approval_token,
        )

        if had_dir:
            archive_parent.mkdir(parents=True, exist_ok=True)
            repo.mv(skill_stage_rel, archive_stage_rel)

        if in_manifest:
            del skills_map[slug]
            manifest_data["skills"] = skills_map
            ordered_manifest: dict[str, Any] = {}
            for key in ("schema_version", "defaults", "skills"):
                if key in manifest_data:
                    ordered_manifest[key] = manifest_data[key]
            manifest_yaml = yaml.dump(
                ordered_manifest, default_flow_style=False, sort_keys=False, allow_unicode=True
            )
            require_guarded_write_pass(
                path=manifest_preview_rel,
                operation="write",
                root=repo.root,
                content=manifest_yaml,
            )
            manifest_path.write_text(manifest_yaml, encoding="utf-8")

        gitignore_content, gitignore_changed = _render_skill_gitignore(repo.root, manifest_data)
        if gitignore_changed:
            require_guarded_write_pass(
                path=gitignore_preview_rel,
                operation="write",
                root=repo.root,
                content=gitignore_content,
            )
            (skills_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        wrote_lock = False
        if lock_path.is_file():
            with open(lock_path, "r", encoding="utf-8") as f:
                lock_data = yaml.safe_load(f) or {}
            entries = lock_data.get("entries", {})
            if slug in entries:
                del entries[slug]
                lock_data["entries"] = entries
                ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                lock_data["locked_at"] = ts
                lock_yaml = yaml.dump(
                    lock_data, default_flow_style=False, sort_keys=False, allow_unicode=True
                )
                require_guarded_write_pass(
                    path=lock_preview_rel,
                    operation="write",
                    root=repo.root,
                    content=lock_yaml,
                )
                lock_path.write_text(lock_yaml, encoding="utf-8")
                wrote_lock = True

        tree_content = _regenerate_skill_tree_content(repo.root)
        require_guarded_write_pass(
            path=tree_preview_rel,
            operation="write",
            root=repo.root,
            content=tree_content,
        )
        (repo.root / "core" / "memory" / "skills" / "SKILL_TREE.md").write_text(
            tree_content, encoding="utf-8"
        )

        files_changed: list[str] = []
        paths_needing_add: list[str] = []
        if had_dir:
            files_changed.extend([skill_stage_rel, archive_stage_rel])
        if in_manifest:
            files_changed.append(manifest_stage_rel)
            paths_needing_add.append(manifest_stage_rel)
        if gitignore_changed:
            files_changed.append(gitignore_stage_rel)
            paths_needing_add.append(gitignore_stage_rel)
        if wrote_lock:
            files_changed.append(lock_stage_rel)
            paths_needing_add.append(lock_stage_rel)
        files_changed.append(tree_stage_rel)
        paths_needing_add.append(tree_stage_rel)

        if summary_changed:
            new_summary = _remove_skill_summary_bullet(
                summary_path.read_text(encoding="utf-8"), slug
            )
            require_guarded_write_pass(
                path=summary_preview_rel,
                operation="write",
                root=repo.root,
                content=new_summary,
            )
            summary_path.write_text(new_summary, encoding="utf-8")
            files_changed.append(summary_stage_rel)
            paths_needing_add.append(summary_stage_rel)

        if had_dir:
            arch_rel, arch_text = _append_archive_index_row(repo.root, slug, archive_reason)
            require_guarded_write_pass(
                path=arch_rel,
                operation="write",
                root=repo.root,
                content=arch_text,
            )
            (repo.root / arch_rel).write_text(arch_text, encoding="utf-8")
            archive_index_stage_rel = str(Path(arch_rel).relative_to("core")).replace("\\", "/")
            files_changed.append(archive_index_stage_rel)
            paths_needing_add.append(archive_index_stage_rel)

        unique_changed = sorted(set(files_changed))
        for rel in sorted(set(paths_needing_add)):
            repo.add(rel)
        commit_result = repo.commit(commit_msg)

        result_body = {
            "slug": slug,
            "status": "archived",
            "previous_location": f"{skill_preview_rel}/" if had_dir else None,
            "archive_location": f"{archive_preview_rel}/" if had_dir else None,
            "archive_reason": archive_reason,
            "manifest_entry_removed": removed_manifest,
            "deployment_gitignore_refreshed": gitignore_changed,
            "artifacts_updated": unique_changed,
        }
        mw = MemoryWriteResult.from_commit(
            files_changed=unique_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={
                "slug": slug,
                "deployment_gitignore_refreshed": gitignore_changed,
            },
            preview=preview_payload,
        )
        out = mw.to_dict()
        out["result"] = result_body
        return json.dumps(out, indent=2)

    @mcp.tool(
        name="memory_skill_sync",
        annotations=_tool_annotations(
            title="Sync Skill Manifest",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_skill_sync(
        check_only: bool = False,
        fix_stale_locks: bool = True,
        archive_orphans: bool = False,
        remove_missing_entries: bool = False,
        verify_symlinks: bool = True,
        regenerate_indexes: bool = True,
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Reconcile SKILLS.yaml, SKILLS.lock, and skill directories; refresh SKILL_TREE / SUMMARY.

        When ``check_only`` is true, returns a report only (no writes).

        Destructive options ``archive_orphans`` and ``remove_missing_entries`` use the
        governed preview + ``approval_token`` flow. Non-destructive refresh (lock
        rebuild, index regeneration) does not require an approval token.

        ``verify_symlinks`` verifies the current external distribution projections and,
        in write mode, repairs stale outputs and removes obsolete target entries.
        """
        import json

        import yaml

        from ...errors import NotFoundError, ValidationError
        from ...guard_pipeline import require_guarded_write_pass
        from ...models import MemoryWriteResult

        repo = get_repo()
        mod = _load_generate_skill_catalog_module(repo.root)
        manifest_path = repo.root / "core" / "memory" / "skills" / "SKILLS.yaml"
        lock_path = repo.root / "core" / "memory" / "skills" / "SKILLS.lock"
        skills_dir = repo.root / "core" / "memory" / "skills"

        if not manifest_path.is_file():
            raise NotFoundError("Skill manifest not found: core/memory/skills/SKILLS.yaml")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f) or {}
        manifest_defaults = _manifest_defaults(manifest_data)
        resolve_skill_distribution_targets(None, manifest_defaults)
        skills_map: dict[str, Any] = manifest_data.get("skills", {})
        if not isinstance(skills_map, dict):
            skills_map = {}

        for slug, manifest_entry in skills_map.items():
            if not isinstance(manifest_entry, dict):
                continue
            resolve_skill_distribution_targets(manifest_entry, manifest_defaults, slug=slug)

        disk_slugs = set(mod.iter_disk_skill_slugs(skills_dir))
        manifest_keys = set(skills_map.keys())
        orphans = sorted(disk_slugs - manifest_keys)

        missing_dir_slugs: list[str] = []
        for slug, mentry in skills_map.items():
            if not isinstance(mentry, dict):
                continue
            if mentry.get("enabled", True) is False:
                continue
            if not (skills_dir / slug / "SKILL.md").is_file():
                missing_dir_slugs.append(slug)

        lock_data: dict[str, Any] = {}
        if lock_path.is_file():
            with open(lock_path, "r", encoding="utf-8") as lf:
                lock_data = yaml.safe_load(lf) or {}
        lock_entries: dict[str, Any] = lock_data.get("entries", {})
        if not isinstance(lock_entries, dict):
            lock_entries = {}

        stale_lock_count = 0
        missing_lock_count = 0
        details: list[dict[str, Any]] = []

        for slug, mentry in skills_map.items():
            if not isinstance(mentry, dict):
                continue
            if mentry.get("enabled", True) is False:
                continue
            sd = skills_dir / slug
            if not (sd / "SKILL.md").is_file():
                continue
            if slug not in lock_entries:
                missing_lock_count += 1
                details.append(
                    {
                        "type": "missing_lock_entry",
                        "slug": slug,
                        "issue": "manifest skill with directory has no lock entry",
                    }
                )

        for slug, lock_entry in sorted(lock_entries.items()):
            if not isinstance(lock_entry, dict):
                continue
            sd = skills_dir / slug
            if not (sd / "SKILL.md").is_file():
                continue
            expected = lock_entry.get("content_hash", "")
            actual = compute_content_hash(sd)
            if expected and actual and expected != actual:
                stale_lock_count += 1
                details.append(
                    {
                        "type": "stale_lock",
                        "slug": slug,
                        "issue": "content hash mismatch",
                    }
                )

        for slug in missing_dir_slugs:
            details.append(
                {
                    "type": "missing_directory",
                    "slug": slug,
                    "issue": "manifest entry but no SKILL.md on disk",
                }
            )

        for slug in orphans:
            details.append(
                {
                    "type": "orphaned_skill",
                    "slug": slug,
                    "issue": "directory on disk not listed in manifest",
                }
            )

        distribution_report: dict[str, Any] | None = None
        distributor = SkillDistributor(repo.root)
        distribution_issue_count = 0
        distribution_failure_count = 0
        if verify_symlinks:
            distribution_report = distributor.inspect_all()
            distribution_issue_count = int(distribution_report["issue_count"])
            distribution_failure_count = int(distribution_report["failure_count"])
            details.extend(_distribution_issue_details(distribution_report))

        symlink_issues = distribution_issue_count + distribution_failure_count

        _, gitignore_changed = _render_skill_gitignore(repo.root, manifest_data)
        if gitignore_changed:
            details.append(
                {
                    "type": "deployment_gitignore_drift",
                    "slug": None,
                    "issue": "managed core/memory/skills/.gitignore block does not match manifest deployment modes",
                }
            )

        issues_found = {
            "stale_locks": stale_lock_count,
            "orphaned_skills": len(orphans),
            "missing_directories": len(missing_dir_slugs),
            "missing_lock_entries": missing_lock_count,
            "symlink_errors": symlink_issues,
            "distribution_errors": distribution_issue_count,
            "distribution_failures": distribution_failure_count,
            "deployment_gitignore_drift": 1 if gitignore_changed else 0,
        }

        healthy = (
            stale_lock_count == 0
            and len(orphans) == 0
            and len(missing_dir_slugs) == 0
            and missing_lock_count == 0
            and symlink_issues == 0
            and not gitignore_changed
        )
        sync_status = "healthy" if healthy else "needs_attention"

        report_base = {
            "sync_status": sync_status,
            "timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "issues_found": issues_found,
            "distribution_verification": {
                "status": distribution_report["status"] if distribution_report else "skipped",
                "verified_count": distribution_report["verified_count"]
                if distribution_report
                else 0,
                "issue_count": distribution_issue_count,
                "failure_count": distribution_failure_count,
            },
            "details": details,
            "check_only": check_only,
        }

        if check_only:
            report_base["actions_taken"] = {
                "locks_refreshed": False,
                "orphans_archived": 0,
                "missing_entries_removed": 0,
                "symlinks_repaired": 0,
                "distribution_repaired": 0,
                "indexes_regenerated": False,
            }
            report_base["approval_required"] = False
            report_base["artifacts_updated"] = []
            return json.dumps({"result": report_base})

        destructive = (archive_orphans and bool(orphans)) or (
            remove_missing_entries and bool(missing_dir_slugs)
        )
        operation_arguments: dict[str, Any] = {
            "check_only": check_only,
            "fix_stale_locks": fix_stale_locks,
            "archive_orphans": archive_orphans,
            "remove_missing_entries": remove_missing_entries,
            "verify_symlinks": verify_symlinks,
            "regenerate_indexes": regenerate_indexes,
        }

        files_changed: list[str] = []
        commit_msg = "[skill] Sync skill manifest and lockfile"
        external_distribution_roots = tuple(
            f"{config['root_relpath']}/"
            for target_id, config in BUILTIN_TARGETS.items()
            if target_id != "engram"
        )

        def _stage_changed_path(rel_path: str) -> None:
            if rel_path.startswith(external_distribution_roots):
                abs_path = repo.root / rel_path
                if not (
                    abs_path.exists() or abs_path.is_symlink() or repo.is_git_path_tracked(rel_path)
                ):
                    return
                repo.add_git_paths(rel_path)
                return
            repo.add(rel_path)

        def _apply_lock_and_indexes(
            skills_map_local: dict[str, Any],
            manifest_data_local: dict[str, Any],
        ) -> None:
            nonlocal files_changed
            gitignore_content, should_update_gitignore = _render_skill_gitignore(
                repo.root,
                manifest_data_local,
            )
            if should_update_gitignore:
                require_guarded_write_pass(
                    path="core/memory/skills/.gitignore",
                    operation="write",
                    root=repo.root,
                    content=gitignore_content,
                )
                (skills_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")
                if "memory/skills/.gitignore" not in files_changed:
                    files_changed.append("memory/skills/.gitignore")

            if fix_stale_locks:
                prior: dict[str, Any] = {}
                if lock_path.is_file():
                    with open(lock_path, "r", encoding="utf-8") as lf:
                        prior = yaml.safe_load(lf) or {}
                rebuilt = _rebuild_skills_lock_data(skills_map_local, skills_dir, prior)
                lock_yaml = yaml.dump(
                    rebuilt, default_flow_style=False, sort_keys=False, allow_unicode=True
                )
                require_guarded_write_pass(
                    path="core/memory/skills/SKILLS.lock",
                    operation="write",
                    root=repo.root,
                    content=lock_yaml,
                )
                lock_path.write_text(lock_yaml, encoding="utf-8")
                if "memory/skills/SKILLS.lock" not in files_changed:
                    files_changed.append("memory/skills/SKILLS.lock")

            if regenerate_indexes:
                tree_content = mod.regenerate_skill_tree_markdown(
                    repo.root, log_missing_frontmatter=False
                )
                require_guarded_write_pass(
                    path="core/memory/skills/SKILL_TREE.md",
                    operation="write",
                    root=repo.root,
                    content=tree_content,
                )
                (skills_dir / "SKILL_TREE.md").write_text(tree_content, encoding="utf-8")
                if "memory/skills/SKILL_TREE.md" not in files_changed:
                    files_changed.append("memory/skills/SKILL_TREE.md")

                new_summary = mod.regenerate_skills_summary_markdown(repo.root)
                if new_summary is not None:
                    require_guarded_write_pass(
                        path="core/memory/skills/SUMMARY.md",
                        operation="write",
                        root=repo.root,
                        content=new_summary,
                    )
                    (skills_dir / "SUMMARY.md").write_text(new_summary, encoding="utf-8")
                    if "memory/skills/SUMMARY.md" not in files_changed:
                        files_changed.append("memory/skills/SUMMARY.md")

        def _apply_distribution_repairs() -> tuple[dict[str, Any] | None, int]:
            nonlocal files_changed
            if not verify_symlinks:
                return None, 0

            current_report = distributor.inspect_all()
            repairable_issue_count = int(current_report["issue_count"])
            changed_paths: list[str] = []

            if repairable_issue_count:
                distribution_apply = distributor.distribute_all(dry_run=False)
                for item in distribution_apply["distributed"]:
                    if item.get("changed", True):
                        for output in item.get("outputs", []):
                            if isinstance(output, str):
                                changed_paths.append(output)
                    index_path = item.get("index_path")
                    if isinstance(index_path, str):
                        changed_paths.append(index_path)

                prune_result = distributor.prune_obsolete_distributions(
                    cast(dict[str, list[str]], current_report.get("expected_by_target", {}))
                )
                changed_paths.extend(prune_result["files_changed"])

            for rel_path in sorted(set(changed_paths)):
                if rel_path not in files_changed:
                    files_changed.append(rel_path)

            post_report = distributor.inspect_all()
            repaired_count = max(0, repairable_issue_count - int(post_report["issue_count"]))
            return post_report, repaired_count

        if destructive:
            target_files: list[dict[str, Any]] = []
            move_staged_paths: set[str] = set()
            if archive_orphans and orphans:
                for slug in orphans:
                    dest = skills_dir / "_archive" / slug
                    if dest.exists():
                        continue
                    skill_rel = f"core/memory/skills/{slug}"
                    archive_rel = f"core/memory/skills/_archive/{slug}"
                    target_files.extend(
                        [
                            preview_target(skill_rel, "move_from"),
                            preview_target(archive_rel, "move_to", from_path=skill_rel),
                        ]
                    )
            if remove_missing_entries and missing_dir_slugs:
                target_files.append(preview_target("core/memory/skills/SKILLS.yaml", "update"))
            if fix_stale_locks:
                target_files.append(preview_target("core/memory/skills/SKILLS.lock", "update"))
            if regenerate_indexes:
                target_files.append(preview_target("core/memory/skills/SKILL_TREE.md", "update"))
                if (skills_dir / "SUMMARY.md").is_file():
                    target_files.append(preview_target("core/memory/skills/SUMMARY.md", "update"))
            if gitignore_changed or (remove_missing_entries and bool(missing_dir_slugs)):
                target_files.append(preview_target("core/memory/skills/.gitignore", "update"))
            if archive_orphans and orphans:
                target_files.append(
                    preview_target("core/memory/skills/_archive/ARCHIVE_INDEX.md", "update")
                )
            if distribution_report:
                target_files.extend(_distribution_preview_targets(distribution_report))

            preview_payload = build_governed_preview(
                mode="preview" if preview else "apply",
                change_class="protected",
                summary="Sync skills: archive orphans and/or drop manifest entries, then refresh lock and indexes.",
                reasoning="Destructive sync changes manifest paths or move skill directories; protected tier.",
                target_files=target_files,
                invariant_effects=[
                    "Optional: move orphan skill dirs into _archive/.",
                    "Optional: remove manifest rows with no on-disk SKILL.md.",
                    "Refreshes the managed core/memory/skills/.gitignore block to match effective deployment modes.",
                    "Repairs stale external skill projections and prunes obsolete distribution entries when verify_symlinks=true.",
                    "Rebuild SKILLS.lock when fix_stale_locks=true.",
                    "Regenerate SKILL_TREE.md / SUMMARY.md when regenerate_indexes=true.",
                ],
                commit_message=commit_msg,
                resulting_state={"destructive": True},
            )
            preview_payload, protected_token = attach_approval_requirement(
                preview_payload,
                repo,
                tool_name="memory_skill_sync",
                operation_arguments=operation_arguments,
            )

            preview_files = sorted(
                {
                    str(t.get("path", ""))
                    for t in target_files
                    if isinstance(t.get("path"), str) and t.get("path")
                }
            )
            if preview:
                return MemoryWriteResult(
                    files_changed=preview_files or ["core/memory/skills/SKILLS.yaml"],
                    commit_sha=None,
                    commit_message=None,
                    new_state={
                        "approval_token": protected_token,
                        "report": {**report_base, "preview": True},
                    },
                    preview=preview_payload,
                ).to_json()

            require_approval_token(
                repo,
                tool_name="memory_skill_sync",
                operation_arguments=operation_arguments,
                approval_token=approval_token,
            )

            orphans_archived = 0
            if archive_orphans:
                archive_parent = skills_dir / "_archive"
                archive_parent.mkdir(parents=True, exist_ok=True)
                for slug in list(orphans):
                    dest = archive_parent / slug
                    if dest.exists():
                        raise ValidationError(
                            f"Cannot archive orphan {slug}: {dest} already exists."
                        )
                    skill_rel = f"memory/skills/{slug}"
                    archive_rel = f"memory/skills/_archive/{slug}"
                    repo.mv(skill_rel, archive_rel)
                    files_changed.extend([skill_rel, archive_rel])
                    move_staged_paths.update({skill_rel, archive_rel})
                    arch_rel, arch_text = _append_archive_index_row(
                        repo.root, slug, "orphaned (memory_skill_sync)"
                    )
                    require_guarded_write_pass(
                        path=arch_rel,
                        operation="write",
                        root=repo.root,
                        content=arch_text,
                    )
                    (repo.root / arch_rel).write_text(arch_text, encoding="utf-8")
                    arch_content_rel = str(Path(arch_rel).relative_to("core")).replace("\\", "/")
                    if arch_content_rel not in files_changed:
                        files_changed.append(arch_content_rel)
                    orphans_archived += 1

            removed_missing = 0
            if remove_missing_entries and missing_dir_slugs:
                for slug in missing_dir_slugs:
                    if slug in skills_map:
                        del skills_map[slug]
                        removed_missing += 1
                manifest_data["skills"] = skills_map
                ordered_manifest: dict[str, Any] = {}
                for key in ("schema_version", "defaults", "skills"):
                    if key in manifest_data:
                        ordered_manifest[key] = manifest_data[key]
                manifest_yaml = yaml.dump(
                    ordered_manifest,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
                require_guarded_write_pass(
                    path="core/memory/skills/SKILLS.yaml",
                    operation="write",
                    root=repo.root,
                    content=manifest_yaml,
                )
                manifest_path.write_text(manifest_yaml, encoding="utf-8")
                if "memory/skills/SKILLS.yaml" not in files_changed:
                    files_changed.append("memory/skills/SKILLS.yaml")

            _apply_lock_and_indexes(skills_map, manifest_data)
            _, distribution_repaired = _apply_distribution_repairs()

            for rel in files_changed:
                if rel in move_staged_paths:
                    continue
                _stage_changed_path(rel)
            commit_result = repo.commit(commit_msg)

            result_body = {
                **report_base,
                "sync_status": "repaired",
                "actions_taken": {
                    "locks_refreshed": fix_stale_locks,
                    "orphans_archived": orphans_archived,
                    "missing_entries_removed": removed_missing,
                    "symlinks_repaired": distribution_repaired,
                    "distribution_repaired": distribution_repaired,
                    "deployment_gitignore_refreshed": "memory/skills/.gitignore" in files_changed,
                    "indexes_regenerated": regenerate_indexes,
                },
                "approval_required": True,
                "artifacts_updated": sorted(set(files_changed)),
            }
            mw = MemoryWriteResult.from_commit(
                files_changed=sorted(set(files_changed)),
                commit_result=commit_result,
                commit_message=commit_msg,
                new_state={"destructive": True},
                preview=preview_payload,
            )
            out = mw.to_dict()
            out["result"] = result_body
            return json.dumps(out, indent=2)

        # Non-destructive sync
        if (
            not fix_stale_locks
            and not regenerate_indexes
            and not gitignore_changed
            and distribution_issue_count == 0
        ):
            result_body = {
                **report_base,
                "actions_taken": {
                    "locks_refreshed": False,
                    "orphans_archived": 0,
                    "missing_entries_removed": 0,
                    "symlinks_repaired": 0,
                    "distribution_repaired": 0,
                    "deployment_gitignore_refreshed": False,
                    "indexes_regenerated": False,
                },
                "approval_required": False,
                "artifacts_updated": [],
            }
            if preview:
                preview_idle = build_governed_preview(
                    mode="preview",
                    change_class="automatic",
                    summary="No lock or index refresh requested.",
                    reasoning="fix_stale_locks and regenerate_indexes are both false.",
                    target_files=[],
                    invariant_effects=["No files will be modified."],
                    commit_message=None,
                    resulting_state={},
                )
                return MemoryWriteResult(
                    files_changed=[],
                    commit_sha=None,
                    commit_message=None,
                    new_state={"report": {**result_body, "preview": True}},
                    preview=preview_idle,
                ).to_json()
            return json.dumps({"result": result_body})

        if preview:
            nd_targets: list[dict[str, Any]] = []
            if fix_stale_locks:
                nd_targets.append(preview_target("core/memory/skills/SKILLS.lock", "update"))
            if regenerate_indexes:
                nd_targets.append(preview_target("core/memory/skills/SKILL_TREE.md", "update"))
                if (skills_dir / "SUMMARY.md").is_file():
                    nd_targets.append(preview_target("core/memory/skills/SUMMARY.md", "update"))
            if gitignore_changed:
                nd_targets.append(preview_target("core/memory/skills/.gitignore", "update"))
            if distribution_report:
                nd_targets.extend(_distribution_preview_targets(distribution_report))
            preview_payload_nd = build_governed_preview(
                mode="preview",
                change_class="automatic",
                summary="Refresh SKILLS.lock, the managed skills .gitignore block, skill indexes, and/or stale external projections (non-destructive).",
                reasoning="Derived lock, gitignore, catalog, and distribution artifacts are automatic-tier.",
                target_files=nd_targets,
                invariant_effects=[
                    "Refreshes the managed core/memory/skills/.gitignore block when deployment-mode drift is detected.",
                    "Repairs stale external skill projections and prunes obsolete distribution entries when verify_symlinks=true.",
                    "Rebuilds lock entries from manifest + on-disk skills when fix_stale_locks=true.",
                    "Regenerates SKILL_TREE.md and SUMMARY.md when regenerate_indexes=true.",
                ],
                commit_message=commit_msg,
                resulting_state={"destructive": False},
            )
            return MemoryWriteResult(
                files_changed=[
                    t.get("path", "") for t in nd_targets if isinstance(t.get("path"), str)
                ],
                commit_sha=None,
                commit_message=None,
                new_state={"report": {**report_base, "preview": True}},
                preview=preview_payload_nd,
            ).to_json()

        _apply_lock_and_indexes(skills_map, manifest_data)
        _, distribution_repaired = _apply_distribution_repairs()
        unique_changed = sorted(set(files_changed))
        if not unique_changed:
            result_body = {
                **report_base,
                "sync_status": sync_status,
                "actions_taken": {
                    "locks_refreshed": False,
                    "orphans_archived": 0,
                    "missing_entries_removed": 0,
                    "symlinks_repaired": 0,
                    "distribution_repaired": 0,
                    "deployment_gitignore_refreshed": False,
                    "indexes_regenerated": False,
                },
                "approval_required": False,
                "artifacts_updated": [],
            }
            return json.dumps({"result": result_body})

        for rel in unique_changed:
            _stage_changed_path(rel)
        commit_result = repo.commit(commit_msg)

        result_body = {
            **report_base,
            "sync_status": "repaired" if fix_stale_locks or regenerate_indexes else sync_status,
            "actions_taken": {
                "locks_refreshed": fix_stale_locks,
                "orphans_archived": 0,
                "missing_entries_removed": 0,
                "symlinks_repaired": distribution_repaired,
                "distribution_repaired": distribution_repaired,
                "deployment_gitignore_refreshed": gitignore_changed,
                "indexes_regenerated": regenerate_indexes,
            },
            "approval_required": False,
            "artifacts_updated": unique_changed,
        }
        mw = MemoryWriteResult.from_commit(
            files_changed=unique_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state={"destructive": False},
            preview=None,
        )
        out = mw.to_dict()
        out["result"] = result_body
        return json.dumps(out, indent=2)

    return {
        "memory_update_skill": memory_update_skill,
        "memory_skill_manifest_read": memory_skill_manifest_read,
        "memory_skill_manifest_write": memory_skill_manifest_write,
        "memory_skill_route": memory_skill_route,
        "memory_skill_list": memory_skill_list,
        "memory_skill_install": memory_skill_install,
        "memory_skill_add": memory_skill_add,
        "memory_skill_remove": memory_skill_remove,
        "memory_skill_sync": memory_skill_sync,
    }


__all__ = ["register_tools"]
