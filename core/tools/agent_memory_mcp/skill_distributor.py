"""Skill distribution engine and CLI for built-in target projections."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml  # type: ignore[import-untyped]

from .errors import ValidationError
from .frontmatter_utils import read_with_frontmatter
from .skill_gitignore import resolve_skill_deployment_mode
from .skill_hash import compute_content_hash

BUILTIN_TARGETS: dict[str, dict[str, str]] = {
    "engram": {
        "root_relpath": "core/memory/skills",
        "profile": "canonical-bundle",
    },
    "generic": {
        "root_relpath": ".agents/skills",
        "profile": "flat-markdown",
    },
    "claude": {
        "root_relpath": ".claude/skills",
        "profile": "canonical-bundle",
    },
    "cursor": {
        "root_relpath": ".cursor/skills",
        "profile": "flat-markdown",
    },
    "codex": {
        "root_relpath": ".codex/skills",
        "profile": "prompt-bundle",
    },
}
DEFAULT_TARGETS = ("engram",)
KNOWN_DISTRIBUTION_TARGETS = frozenset(BUILTIN_TARGETS)
_GOVERNANCE_FIELDS = frozenset(
    {
        "source",
        "origin_session",
        "created",
        "last_verified",
        "trust",
        "trigger",
    }
)
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_IGNORED_LINK_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "data:",
    "file://",
    "/",
    "#",
)


def _hash_bytes(raw_bytes: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


def _hash_text(text: str) -> str:
    return _hash_bytes(text.encode("utf-8"))


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def normalize_distribution_targets(raw: object, *, field_name: str) -> list[str]:
    if not isinstance(raw, list):
        raise ValidationError(f"{field_name} must be a list of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(f"{field_name} must be a list of strings")
        target = item.strip()
        if target not in KNOWN_DISTRIBUTION_TARGETS:
            raise ValidationError(f"{field_name} contains unknown target: {target}")
        if target not in seen:
            seen.add(target)
            normalized.append(target)
    return normalized


def resolve_skill_distribution_targets(
    skill_entry: Mapping[str, Any] | None,
    defaults: Mapping[str, Any] | None = None,
    *,
    slug: str | None = None,
) -> list[str]:
    if isinstance(skill_entry, Mapping) and "targets" in skill_entry:
        field_name = f"skills.{slug}.targets" if slug else "skills.{slug}.targets"
        return normalize_distribution_targets(skill_entry.get("targets"), field_name=field_name)
    if isinstance(defaults, Mapping) and "targets" in defaults:
        return normalize_distribution_targets(
            defaults.get("targets"), field_name="defaults.targets"
        )
    return list(DEFAULT_TARGETS)


def _repo_relpath(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _write_text(path, _json_text(payload))


def _string_field(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _canonical_title(frontmatter: Mapping[str, Any], slug: str) -> str:
    return _string_field(frontmatter.get("name")) or slug


def _canonical_description(
    frontmatter: Mapping[str, Any], manifest_entry: Mapping[str, Any]
) -> str | None:
    return _string_field(frontmatter.get("description")) or _string_field(
        manifest_entry.get("description")
    )


def _governance_metadata(frontmatter: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: frontmatter[key]
        for key in _GOVERNANCE_FIELDS
        if key in frontmatter and frontmatter[key] is not None
    }


def _stringify_compatibility_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        rendered = [
            item_text for item in value if (item_text := _stringify_compatibility_value(item))
        ]
        return ", ".join(rendered)
    if isinstance(value, dict):
        rendered = []
        for key, nested in value.items():
            nested_text = _stringify_compatibility_value(nested)
            if nested_text:
                rendered.append(f"{key}={nested_text}")
        return ", ".join(rendered)
    return ""


def _render_compatibility_block(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, list):
        lines = []
        for item in value:
            item_text = _stringify_compatibility_value(item)
            if item_text:
                lines.append(f"- {item_text}")
        return "\n".join(lines) or None
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            item_text = _stringify_compatibility_value(item)
            if item_text:
                lines.append(f"- {key}: {item_text}")
        return "\n".join(lines) or None
    normalized = _stringify_compatibility_value(value)
    return normalized or None


def _relative_markdown_targets(body_markdown: str) -> list[str]:
    seen: set[str] = set()
    targets: list[str] = []
    for match in _MARKDOWN_LINK_RE.finditer(body_markdown):
        raw_target = match.group(1).strip()
        if not raw_target:
            continue
        if raw_target.startswith("<") and raw_target.endswith(">"):
            raw_target = raw_target[1:-1].strip()
        target = raw_target.split(maxsplit=1)[0]
        if not target or target.startswith(_IGNORED_LINK_PREFIXES):
            continue
        if target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


def _render_flat_markdown(
    *,
    slug: str,
    manifest_entry: Mapping[str, Any],
    frontmatter: Mapping[str, Any],
    body_markdown: str,
) -> str:
    parts = [f"# {_canonical_title(frontmatter, slug)}"]
    description = _canonical_description(frontmatter, manifest_entry)
    if description:
        parts.append(description)
    compatibility = _render_compatibility_block(frontmatter.get("compatibility"))
    if compatibility:
        parts.append(f"## Compatibility\n\n{compatibility}")
    body = body_markdown.strip()
    if body:
        parts.append(body)
    return "\n\n".join(parts).rstrip() + "\n"


def _render_prompt_markdown(
    *,
    slug: str,
    manifest_entry: Mapping[str, Any],
    frontmatter: Mapping[str, Any],
    body_markdown: str,
) -> str:
    parts = [f"# {_canonical_title(frontmatter, slug)}"]
    description = _canonical_description(frontmatter, manifest_entry)
    if description:
        parts.append(f"Purpose: {description}")
    compatibility = _render_compatibility_block(frontmatter.get("compatibility"))
    if compatibility:
        parts.append(f"## Compatibility\n\n{compatibility}")
    body = body_markdown.strip()
    if body:
        parts.append(body)
    return "\n\n".join(parts).rstrip() + "\n"


class DistributionFailure(ValidationError):
    def __init__(self, reason: str, detail: str):
        self.reason = reason
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class TransportCapabilities:
    prefer_symlink: bool = True


@dataclass(frozen=True, slots=True)
class DistributionPlan:
    adapter_version: int
    skill_slug: str
    target_id: str
    root_relpath: str
    profile: str
    transport: str
    canonical_dir: Path
    canonical_path: str
    canonical_hash: str
    output_paths: tuple[Path, ...]
    output_relpaths: tuple[str, ...]
    index_relpath: str
    governance_metadata: dict[str, Any]
    rendered_markdown: str | None = None
    rendered_hash: str | None = None
    metadata_payload: dict[str, Any] | None = None
    metadata_hash: str | None = None


class BaseSkillTargetAdapter:
    adapter_version = 1

    def __init__(self, *, target_id: str, root_relpath: str, profile: str) -> None:
        self.target_id = target_id
        self.root_relpath = root_relpath
        self.profile = profile

    @property
    def index_relpath(self) -> str:
        return f"{self.root_relpath}/.engram-distribution.json"

    def _build_plan(
        self,
        *,
        repo_root: Path,
        skill_slug: str,
        canonical_dir: Path,
        canonical_path: str,
        canonical_hash: str,
        output_paths: tuple[Path, ...],
        governance_metadata: dict[str, Any],
        transport: str,
        rendered_markdown: str | None = None,
        rendered_hash: str | None = None,
        metadata_payload: dict[str, Any] | None = None,
        metadata_hash: str | None = None,
    ) -> DistributionPlan:
        return DistributionPlan(
            adapter_version=self.adapter_version,
            skill_slug=skill_slug,
            target_id=self.target_id,
            root_relpath=self.root_relpath,
            profile=self.profile,
            transport=transport,
            canonical_dir=canonical_dir,
            canonical_path=canonical_path,
            canonical_hash=canonical_hash,
            output_paths=output_paths,
            output_relpaths=tuple(_repo_relpath(repo_root, path) for path in output_paths),
            index_relpath=self.index_relpath,
            governance_metadata=governance_metadata,
            rendered_markdown=rendered_markdown,
            rendered_hash=rendered_hash,
            metadata_payload=metadata_payload,
            metadata_hash=metadata_hash,
        )

    def plan(
        self,
        *,
        repo_root: Path,
        skill_slug: str,
        canonical_dir: Path,
        canonical_path: str,
        canonical_hash: str,
        manifest_entry: Mapping[str, Any],
        frontmatter: Mapping[str, Any],
        body_markdown: str,
    ) -> DistributionPlan:
        raise NotImplementedError

    def materialize(
        self,
        plan: DistributionPlan,
        *,
        transport_capabilities: TransportCapabilities,
    ) -> dict[str, Any]:
        raise NotImplementedError


class FlatMarkdownAdapter(BaseSkillTargetAdapter):
    def __init__(self, *, target_id: str, root_relpath: str) -> None:
        super().__init__(target_id=target_id, root_relpath=root_relpath, profile="flat-markdown")

    def plan(
        self,
        *,
        repo_root: Path,
        skill_slug: str,
        canonical_dir: Path,
        canonical_path: str,
        canonical_hash: str,
        manifest_entry: Mapping[str, Any],
        frontmatter: Mapping[str, Any],
        body_markdown: str,
    ) -> DistributionPlan:
        relative_links = _relative_markdown_targets(body_markdown)
        if relative_links:
            raise DistributionFailure(
                "unsupported_auxiliary_files",
                f"{self.target_id} cannot distribute relative links without copying and rewriting auxiliary files: {', '.join(relative_links)}",
            )
        rendered_markdown = _render_flat_markdown(
            slug=skill_slug,
            manifest_entry=manifest_entry,
            frontmatter=frontmatter,
            body_markdown=body_markdown,
        )
        output_path = repo_root / self.root_relpath / f"{skill_slug}.md"
        return self._build_plan(
            repo_root=repo_root,
            skill_slug=skill_slug,
            canonical_dir=canonical_dir,
            canonical_path=canonical_path,
            canonical_hash=canonical_hash,
            output_paths=(output_path,),
            governance_metadata=_governance_metadata(frontmatter),
            transport="render",
            rendered_markdown=rendered_markdown,
            rendered_hash=_hash_text(rendered_markdown),
        )

    def materialize(
        self,
        plan: DistributionPlan,
        *,
        transport_capabilities: TransportCapabilities,
    ) -> dict[str, Any]:
        del transport_capabilities
        output_path = plan.output_paths[0]
        if output_path.is_symlink() or output_path.is_dir():
            _remove_path(output_path)
        assert plan.rendered_markdown is not None
        changed = True
        if (
            output_path.is_file()
            and output_path.read_text(encoding="utf-8") == plan.rendered_markdown
        ):
            changed = False
        _write_text(output_path, plan.rendered_markdown)
        return {
            "changed": changed,
            "mode": "render",
            "rendered_hash": plan.rendered_hash,
        }


class PromptBundleAdapter(BaseSkillTargetAdapter):
    def __init__(self, *, target_id: str, root_relpath: str) -> None:
        super().__init__(target_id=target_id, root_relpath=root_relpath, profile="prompt-bundle")

    def plan(
        self,
        *,
        repo_root: Path,
        skill_slug: str,
        canonical_dir: Path,
        canonical_path: str,
        canonical_hash: str,
        manifest_entry: Mapping[str, Any],
        frontmatter: Mapping[str, Any],
        body_markdown: str,
    ) -> DistributionPlan:
        relative_links = _relative_markdown_targets(body_markdown)
        if relative_links:
            raise DistributionFailure(
                "unsupported_auxiliary_files",
                f"{self.target_id} cannot distribute relative links without bundling auxiliary files: {', '.join(relative_links)}",
            )
        rendered_markdown = _render_prompt_markdown(
            slug=skill_slug,
            manifest_entry=manifest_entry,
            frontmatter=frontmatter,
            body_markdown=body_markdown,
        )
        rendered_hash = _hash_text(rendered_markdown)
        metadata_payload = {
            "slug": skill_slug,
            "target": self.target_id,
            "profile": self.profile,
            "adapter_version": self.adapter_version,
            "canonical_path": canonical_path,
            "canonical_hash": canonical_hash,
            "rendered_hash": rendered_hash,
            "governance": _governance_metadata(frontmatter),
        }
        metadata_hash = _hash_text(_json_text(metadata_payload))
        bundle_root = repo_root / self.root_relpath / skill_slug
        output_paths = (
            bundle_root / "SKILL.md",
            bundle_root / "metadata.json",
        )
        return self._build_plan(
            repo_root=repo_root,
            skill_slug=skill_slug,
            canonical_dir=canonical_dir,
            canonical_path=canonical_path,
            canonical_hash=canonical_hash,
            output_paths=output_paths,
            governance_metadata=_governance_metadata(frontmatter),
            transport="render",
            rendered_markdown=rendered_markdown,
            rendered_hash=rendered_hash,
            metadata_payload=metadata_payload,
            metadata_hash=metadata_hash,
        )

    def materialize(
        self,
        plan: DistributionPlan,
        *,
        transport_capabilities: TransportCapabilities,
    ) -> dict[str, Any]:
        del transport_capabilities
        bundle_root = plan.output_paths[0].parent
        assert plan.rendered_markdown is not None
        assert plan.metadata_payload is not None
        desired_metadata = _json_text(plan.metadata_payload)
        changed = True
        if bundle_root.is_dir() and not bundle_root.is_symlink():
            existing_entries = {child.name for child in bundle_root.iterdir()}
            if existing_entries == {"SKILL.md", "metadata.json"}:
                skill_path, metadata_path = plan.output_paths
                if skill_path.is_file() and metadata_path.is_file():
                    changed = not (
                        skill_path.read_text(encoding="utf-8") == plan.rendered_markdown
                        and metadata_path.read_text(encoding="utf-8") == desired_metadata
                    )
        if changed and (bundle_root.exists() or bundle_root.is_symlink()):
            _remove_path(bundle_root)
        bundle_root.mkdir(parents=True, exist_ok=True)
        _write_text(plan.output_paths[0], plan.rendered_markdown)
        _write_json(plan.output_paths[1], plan.metadata_payload)
        return {
            "changed": changed,
            "mode": "render",
            "rendered_hash": plan.rendered_hash,
            "metadata_hash": plan.metadata_hash,
        }


class CanonicalBundleAdapter(BaseSkillTargetAdapter):
    def __init__(self, *, target_id: str, root_relpath: str) -> None:
        super().__init__(target_id=target_id, root_relpath=root_relpath, profile="canonical-bundle")

    def plan(
        self,
        *,
        repo_root: Path,
        skill_slug: str,
        canonical_dir: Path,
        canonical_path: str,
        canonical_hash: str,
        manifest_entry: Mapping[str, Any],
        frontmatter: Mapping[str, Any],
        body_markdown: str,
    ) -> DistributionPlan:
        del manifest_entry, body_markdown
        output_path = repo_root / self.root_relpath / skill_slug
        return self._build_plan(
            repo_root=repo_root,
            skill_slug=skill_slug,
            canonical_dir=canonical_dir,
            canonical_path=canonical_path,
            canonical_hash=canonical_hash,
            output_paths=(output_path,),
            governance_metadata=_governance_metadata(frontmatter),
            transport="symlink-preferred",
        )

    def materialize(
        self,
        plan: DistributionPlan,
        *,
        transport_capabilities: TransportCapabilities,
    ) -> dict[str, Any]:
        output_path = plan.output_paths[0]
        mode = "copy"
        if transport_capabilities.prefer_symlink:
            if output_path.is_symlink():
                try:
                    if output_path.resolve() == plan.canonical_dir.resolve():
                        return {
                            "changed": False,
                            "mode": "symlink",
                            "bundle_hash": plan.canonical_hash,
                            "transport": "symlink",
                        }
                except OSError:
                    pass
            try:
                self._ensure_symlink(output_path, plan.canonical_dir)
                mode = "symlink"
            except OSError:
                if (
                    output_path.is_dir()
                    and compute_content_hash(output_path) == plan.canonical_hash
                ):
                    return {
                        "changed": False,
                        "mode": "copy",
                        "bundle_hash": plan.canonical_hash,
                        "transport": "copy",
                    }
                self._copy_bundle(plan.canonical_dir, output_path)
        else:
            if output_path.is_dir() and not output_path.is_symlink():
                if compute_content_hash(output_path) == plan.canonical_hash:
                    return {
                        "changed": False,
                        "mode": "copy",
                        "bundle_hash": plan.canonical_hash,
                        "transport": "copy",
                    }
            self._copy_bundle(plan.canonical_dir, output_path)
        return {
            "changed": True,
            "mode": mode,
            "bundle_hash": plan.canonical_hash,
            "transport": mode,
        }

    def _ensure_symlink(self, output_path: Path, canonical_dir: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.is_symlink():
            try:
                if output_path.resolve() == canonical_dir.resolve():
                    return
            except OSError:
                pass
            output_path.unlink()
        elif output_path.exists():
            _remove_path(output_path)
        output_path.symlink_to(canonical_dir, target_is_directory=True)

    def _copy_bundle(self, canonical_dir: Path, output_path: Path) -> None:
        if output_path.exists() or output_path.is_symlink():
            _remove_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            canonical_dir,
            output_path,
            ignore=shutil.ignore_patterns(".git", ".hg", ".svn"),
        )


class SkillDistributor:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.skills_dir = self.repo_root / "core" / "memory" / "skills"
        self.adapters: dict[str, BaseSkillTargetAdapter] = {
            "generic": FlatMarkdownAdapter(target_id="generic", root_relpath=".agents/skills"),
            "claude": CanonicalBundleAdapter(target_id="claude", root_relpath=".claude/skills"),
            "cursor": FlatMarkdownAdapter(target_id="cursor", root_relpath=".cursor/skills"),
            "codex": PromptBundleAdapter(target_id="codex", root_relpath=".codex/skills"),
        }
        self.known_targets = KNOWN_DISTRIBUTION_TARGETS

    def distribute_all(
        self,
        *,
        slugs: list[str] | None = None,
        targets: list[str] | None = None,
        dry_run: bool = True,
        prefer_symlink: bool = True,
    ) -> dict[str, Any]:
        manifest = self._load_manifest()
        defaults = self._manifest_defaults(manifest)
        skills = self._manifest_skills(manifest)
        selected_slugs = self._select_slugs(skills, slugs)
        target_filter = self._normalize_cli_targets(targets) if targets is not None else None
        transport_capabilities = TransportCapabilities(prefer_symlink=prefer_symlink)

        planned: list[dict[str, Any]] = []
        distributed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        index_cache: dict[str, dict[str, Any]] = {}

        for slug in selected_slugs:
            entry = skills.get(slug)
            if not isinstance(entry, Mapping):
                failed.append(
                    {
                        "slug": slug,
                        "reason": "invalid_manifest_entry",
                        "detail": "manifest entry must be a mapping",
                    }
                )
                continue

            if entry.get("enabled", True) is False:
                skipped.append(
                    {
                        "slug": slug,
                        "reason": "disabled",
                        "detail": "disabled skills are not distributed",
                    }
                )
                continue

            effective_targets = self._effective_targets(slug, entry, defaults)
            selected_targets = self._filter_targets(effective_targets, target_filter)
            if not selected_targets:
                skipped.append(
                    {
                        "slug": slug,
                        "reason": "target_filter_excluded",
                        "detail": "no configured distribution targets matched the requested filter",
                    }
                )
                continue

            if "engram" in selected_targets:
                skipped.append(
                    {
                        "slug": slug,
                        "target": "engram",
                        "profile": BUILTIN_TARGETS["engram"]["profile"],
                        "root_relpath": BUILTIN_TARGETS["engram"]["root_relpath"],
                        "reason": "canonical_store",
                        "detail": "engram is the canonical skill store and is not generated",
                    }
                )

            external_targets = [target for target in selected_targets if target != "engram"]
            if not external_targets:
                continue

            try:
                deployment_mode = resolve_skill_deployment_mode(entry, defaults)
            except ValidationError as exc:
                for target in external_targets:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": BUILTIN_TARGETS[target]["profile"],
                            "reason": "invalid_deployment_mode",
                            "detail": str(exc),
                        }
                    )
                continue

            canonical_dir = self.skills_dir / slug
            skill_md = canonical_dir / "SKILL.md"
            if not skill_md.is_file():
                reason = (
                    "missing_local_install"
                    if deployment_mode == "gitignored"
                    else "missing_canonical_skill"
                )
                detail = (
                    "gitignored skill is not installed locally; run install or sync before distribution"
                    if deployment_mode == "gitignored"
                    else "checked skill is missing locally; checked skills must be present before distribution"
                )
                for target in external_targets:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": BUILTIN_TARGETS[target]["profile"],
                            "reason": reason,
                            "detail": detail,
                        }
                    )
                continue

            try:
                frontmatter, body_markdown = read_with_frontmatter(skill_md)
            except Exception as exc:  # pragma: no cover - parser errors are environment-driven
                for target in external_targets:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": BUILTIN_TARGETS[target]["profile"],
                            "reason": "invalid_frontmatter",
                            "detail": str(exc),
                        }
                    )
                continue

            canonical_hash = compute_content_hash(canonical_dir)
            canonical_path = f"core/memory/skills/{slug}"

            for target in external_targets:
                adapter = self.adapters[target]
                try:
                    plan = adapter.plan(
                        repo_root=self.repo_root,
                        skill_slug=slug,
                        canonical_dir=canonical_dir,
                        canonical_path=canonical_path,
                        canonical_hash=canonical_hash,
                        manifest_entry=entry,
                        frontmatter=frontmatter,
                        body_markdown=body_markdown,
                    )
                except DistributionFailure as exc:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": adapter.profile,
                            "reason": exc.reason,
                            "detail": str(exc),
                        }
                    )
                    continue

                if dry_run:
                    planned.append(self._planned_item(plan))
                    continue

                result = adapter.materialize(
                    plan,
                    transport_capabilities=transport_capabilities,
                )
                distributed.append(self._distributed_item(plan, result))
                self._update_index(index_cache, plan, result)

        if not dry_run:
            self._write_indexes(index_cache)

        return {
            "repo_root": str(self.repo_root),
            "status": "ok" if not failed else "failed",
            "dry_run": dry_run,
            "applied": not dry_run,
            "prefer_symlink": prefer_symlink,
            "available_targets": sorted(self.known_targets),
            "skills_selected": selected_slugs,
            "target_filter": list(target_filter) if target_filter is not None else None,
            "planned_count": len(planned),
            "distributed_count": len(distributed),
            "skipped_count": len(skipped),
            "failure_count": len(failed),
            "planned": planned,
            "distributed": distributed,
            "skipped": skipped,
            "failed": failed,
        }

    def _load_manifest(self) -> dict[str, Any]:
        manifest_path = self.skills_dir / "SKILLS.yaml"
        if not manifest_path.is_file():
            raise ValidationError("Skill manifest not found: core/memory/skills/SKILLS.yaml")
        with manifest_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValidationError("Skill manifest must contain a top-level mapping")
        return data

    def _manifest_defaults(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        defaults_raw = manifest.get("defaults") or {}
        if not isinstance(defaults_raw, dict):
            raise ValidationError("defaults must be a mapping when present")
        return defaults_raw

    def _manifest_skills(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        skills_raw = manifest.get("skills") or {}
        if not isinstance(skills_raw, dict):
            raise ValidationError("skills must be a mapping")
        return skills_raw

    def _select_slugs(self, skills: Mapping[str, Any], slugs: list[str] | None) -> list[str]:
        if slugs is None:
            return sorted(skills)
        selected = []
        missing = []
        for slug in slugs:
            if slug in skills:
                if slug not in selected:
                    selected.append(slug)
            else:
                missing.append(slug)
        if missing:
            raise ValidationError(f"Unknown skill slugs: {', '.join(missing)}")
        return selected

    def _normalize_cli_targets(self, targets: list[str]) -> list[str]:
        return normalize_distribution_targets(targets, field_name="targets")

    def _effective_targets(
        self,
        slug: str,
        entry: Mapping[str, Any],
        defaults: Mapping[str, Any],
    ) -> list[str]:
        return resolve_skill_distribution_targets(entry, defaults, slug=slug)

    def _filter_targets(
        self,
        configured_targets: list[str],
        target_filter: list[str] | None,
    ) -> list[str]:
        if target_filter is None:
            return list(configured_targets)
        return [target for target in configured_targets if target in target_filter]

    def _planned_item(self, plan: DistributionPlan) -> dict[str, Any]:
        item = {
            "slug": plan.skill_slug,
            "target": plan.target_id,
            "profile": plan.profile,
            "mode": plan.transport,
            "outputs": list(plan.output_relpaths),
            "canonical_path": plan.canonical_path,
            "canonical_hash": plan.canonical_hash,
            "index_path": plan.index_relpath,
        }
        if plan.rendered_hash is not None:
            item["rendered_hash"] = plan.rendered_hash
        if plan.metadata_hash is not None:
            item["metadata_hash"] = plan.metadata_hash
        return item

    def _distributed_item(
        self, plan: DistributionPlan, result: Mapping[str, Any]
    ) -> dict[str, Any]:
        item = self._planned_item(plan)
        item["mode"] = result.get("mode", plan.transport)
        if "changed" in result:
            item["changed"] = bool(result["changed"])
        if "transport" in result:
            item["transport"] = result["transport"]
        if "bundle_hash" in result:
            item["bundle_hash"] = result["bundle_hash"]
        return item

    def inspect_all(
        self,
        *,
        slugs: list[str] | None = None,
        targets: list[str] | None = None,
    ) -> dict[str, Any]:
        manifest = self._load_manifest()
        defaults = self._manifest_defaults(manifest)
        skills = self._manifest_skills(manifest)
        selected_slugs = self._select_slugs(skills, slugs)
        target_filter = self._normalize_cli_targets(targets) if targets is not None else None

        verified: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        index_cache: dict[str, dict[str, Any]] = {}
        expected_by_target: dict[str, set[str]] = {target: set() for target in self.adapters}

        for slug in selected_slugs:
            entry = skills.get(slug)
            if not isinstance(entry, Mapping):
                failed.append(
                    {
                        "slug": slug,
                        "reason": "invalid_manifest_entry",
                        "detail": "manifest entry must be a mapping",
                    }
                )
                continue

            if entry.get("enabled", True) is False:
                skipped.append(
                    {
                        "slug": slug,
                        "reason": "disabled",
                        "detail": "disabled skills are not distributed",
                    }
                )
                continue

            effective_targets = self._effective_targets(slug, entry, defaults)
            selected_targets = self._filter_targets(effective_targets, target_filter)
            if not selected_targets:
                skipped.append(
                    {
                        "slug": slug,
                        "reason": "target_filter_excluded",
                        "detail": "no configured distribution targets matched the requested filter",
                    }
                )
                continue

            if "engram" in selected_targets:
                skipped.append(
                    {
                        "slug": slug,
                        "target": "engram",
                        "profile": BUILTIN_TARGETS["engram"]["profile"],
                        "root_relpath": BUILTIN_TARGETS["engram"]["root_relpath"],
                        "reason": "canonical_store",
                        "detail": "engram is the canonical skill store and is not generated",
                    }
                )

            external_targets = [target for target in selected_targets if target != "engram"]
            for target in external_targets:
                expected_by_target[target].add(slug)
            if not external_targets:
                continue

            try:
                deployment_mode = resolve_skill_deployment_mode(entry, defaults)
            except ValidationError as exc:
                for target in external_targets:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": BUILTIN_TARGETS[target]["profile"],
                            "reason": "invalid_deployment_mode",
                            "detail": str(exc),
                        }
                    )
                continue

            canonical_dir = self.skills_dir / slug
            skill_md = canonical_dir / "SKILL.md"
            if not skill_md.is_file():
                reason = (
                    "missing_local_install"
                    if deployment_mode == "gitignored"
                    else "missing_canonical_skill"
                )
                detail = (
                    "gitignored skill is not installed locally; run install or sync before distribution"
                    if deployment_mode == "gitignored"
                    else "checked skill is missing locally; checked skills must be present before distribution"
                )
                for target in external_targets:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": BUILTIN_TARGETS[target]["profile"],
                            "reason": reason,
                            "detail": detail,
                        }
                    )
                continue

            try:
                frontmatter, body_markdown = read_with_frontmatter(skill_md)
            except Exception as exc:  # pragma: no cover - parser errors are environment-driven
                for target in external_targets:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": BUILTIN_TARGETS[target]["profile"],
                            "reason": "invalid_frontmatter",
                            "detail": str(exc),
                        }
                    )
                continue

            canonical_hash = compute_content_hash(canonical_dir)
            canonical_path = f"core/memory/skills/{slug}"

            for target in external_targets:
                adapter = self.adapters[target]
                try:
                    plan = adapter.plan(
                        repo_root=self.repo_root,
                        skill_slug=slug,
                        canonical_dir=canonical_dir,
                        canonical_path=canonical_path,
                        canonical_hash=canonical_hash,
                        manifest_entry=entry,
                        frontmatter=frontmatter,
                        body_markdown=body_markdown,
                    )
                except DistributionFailure as exc:
                    failed.append(
                        {
                            "slug": slug,
                            "target": target,
                            "profile": adapter.profile,
                            "reason": exc.reason,
                            "detail": str(exc),
                        }
                    )
                    continue

                inspection = self._inspect_plan(plan, index_cache=index_cache)
                if inspection["status"] == "ok":
                    verified.append(inspection)
                else:
                    issues.append(inspection)

        issues.extend(self._inspect_unexpected_index_entries(expected_by_target, index_cache))

        return {
            "repo_root": str(self.repo_root),
            "status": "ok" if not failed and not issues else "needs_attention",
            "available_targets": sorted(self.known_targets),
            "skills_selected": selected_slugs,
            "target_filter": list(target_filter) if target_filter is not None else None,
            "verified_count": len(verified),
            "issue_count": len(issues),
            "failure_count": len(failed),
            "verified": verified,
            "issues": issues,
            "failed": failed,
            "skipped": skipped,
            "expected_by_target": {
                target: sorted(slugs_for_target)
                for target, slugs_for_target in expected_by_target.items()
                if slugs_for_target
            },
        }

    def prune_obsolete_distributions(
        self,
        expected_by_target: Mapping[str, list[str] | set[str]],
    ) -> dict[str, Any]:
        removed: list[dict[str, Any]] = []
        files_changed: list[str] = []

        for target_id, adapter in self.adapters.items():
            expected = set(expected_by_target.get(target_id, []))
            index = self._load_index_for_target(target_id)
            entries = index["entries"]
            changed = False

            for slug, entry in sorted(list(entries.items())):
                if slug in expected:
                    continue
                outputs = self._entry_outputs(entry)
                for output_rel in outputs:
                    output_path = self.repo_root / Path(output_rel)
                    if output_path.exists() or output_path.is_symlink():
                        _remove_path(output_path)
                    if output_rel not in files_changed:
                        files_changed.append(output_rel)
                del entries[slug]
                changed = True
                removed.append(
                    {
                        "slug": slug,
                        "target": target_id,
                        "profile": adapter.profile,
                        "outputs": outputs,
                        "index_path": adapter.index_relpath,
                    }
                )

            if changed:
                _write_json(self.repo_root / adapter.index_relpath, index)
                if adapter.index_relpath not in files_changed:
                    files_changed.append(adapter.index_relpath)

        return {
            "removed_count": len(removed),
            "removed": removed,
            "files_changed": files_changed,
        }

    def _inspect_plan(
        self,
        plan: DistributionPlan,
        *,
        index_cache: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        item = self._planned_item(plan)
        issues: list[dict[str, str]] = []
        transport = self._inspect_outputs(plan, issues)
        if transport is not None:
            item["transport"] = transport

        index = index_cache.get(plan.target_id)
        if index is None:
            index = self._load_index_for_target(plan.target_id)
            index_cache[plan.target_id] = index

        index_entry = index["entries"].get(plan.skill_slug)
        if not isinstance(index_entry, Mapping):
            issues.append(
                {
                    "reason": "missing_index_entry",
                    "detail": f"distribution index is missing {plan.skill_slug}",
                }
            )
        else:
            self._inspect_index_entry(plan, index_entry, transport, issues)

        if issues:
            item["status"] = "issue"
            item["issues"] = issues
        else:
            item["status"] = "ok"
        return item

    def _inspect_outputs(
        self,
        plan: DistributionPlan,
        issues: list[dict[str, str]],
    ) -> str | None:
        if plan.profile == "canonical-bundle":
            output_path = plan.output_paths[0]
            if output_path.is_symlink():
                try:
                    if output_path.resolve() != plan.canonical_dir.resolve():
                        issues.append(
                            {
                                "reason": "broken_symlink",
                                "detail": f"{plan.output_relpaths[0]} does not resolve to {plan.canonical_path}",
                            }
                        )
                except OSError as exc:
                    issues.append(
                        {
                            "reason": "broken_symlink",
                            "detail": f"{plan.output_relpaths[0]} could not be resolved: {exc}",
                        }
                    )
                return "symlink"
            if output_path.is_dir():
                if compute_content_hash(output_path) != plan.canonical_hash:
                    issues.append(
                        {
                            "reason": "stale_bundle",
                            "detail": f"{plan.output_relpaths[0]} does not match {plan.canonical_path}",
                        }
                    )
                return "copy"
            if output_path.exists():
                issues.append(
                    {
                        "reason": "invalid_output_type",
                        "detail": f"{plan.output_relpaths[0]} is not a directory or symlinked bundle",
                    }
                )
                return None
            issues.append(
                {
                    "reason": "missing_output",
                    "detail": f"{plan.output_relpaths[0]} is missing",
                }
            )
            return None

        if plan.profile == "flat-markdown":
            output_path = plan.output_paths[0]
            if not output_path.is_file():
                issues.append(
                    {
                        "reason": "missing_output",
                        "detail": f"{plan.output_relpaths[0]} is missing",
                    }
                )
                return None
            if plan.rendered_hash is not None and _hash_file(output_path) != plan.rendered_hash:
                issues.append(
                    {
                        "reason": "stale_output",
                        "detail": f"{plan.output_relpaths[0]} does not match the rendered distribution content",
                    }
                )
            return "render"

        bundle_root = plan.output_paths[0].parent
        if bundle_root.is_symlink():
            issues.append(
                {
                    "reason": "invalid_output_type",
                    "detail": f"{_repo_relpath(self.repo_root, bundle_root)} should be a rendered bundle directory",
                }
            )
        for output_path, expected_hash, label in (
            (plan.output_paths[0], plan.rendered_hash, "rendered prompt"),
            (plan.output_paths[1], plan.metadata_hash, "metadata"),
        ):
            if not output_path.is_file():
                issues.append(
                    {
                        "reason": "missing_output",
                        "detail": f"{_repo_relpath(self.repo_root, output_path)} is missing",
                    }
                )
                continue
            if expected_hash is not None and _hash_file(output_path) != expected_hash:
                issues.append(
                    {
                        "reason": "stale_output",
                        "detail": f"{_repo_relpath(self.repo_root, output_path)} does not match the expected {label}",
                    }
                )
        return "render"

    def _inspect_index_entry(
        self,
        plan: DistributionPlan,
        index_entry: Mapping[str, Any],
        transport: str | None,
        issues: list[dict[str, str]],
    ) -> None:
        if index_entry.get("canonical_path") != plan.canonical_path:
            issues.append(
                {
                    "reason": "stale_index",
                    "detail": f"distribution index canonical_path for {plan.skill_slug} is outdated",
                }
            )
        if index_entry.get("canonical_hash") != plan.canonical_hash:
            issues.append(
                {
                    "reason": "stale_index",
                    "detail": f"distribution index canonical_hash for {plan.skill_slug} is outdated",
                }
            )
        if index_entry.get("profile") != plan.profile:
            issues.append(
                {
                    "reason": "stale_index",
                    "detail": f"distribution index profile for {plan.skill_slug} is outdated",
                }
            )
        if self._entry_outputs(index_entry) != list(plan.output_relpaths):
            issues.append(
                {
                    "reason": "stale_index",
                    "detail": f"distribution index outputs for {plan.skill_slug} are outdated",
                }
            )
        if (
            plan.rendered_hash is not None
            and index_entry.get("rendered_hash") != plan.rendered_hash
        ):
            issues.append(
                {
                    "reason": "stale_index",
                    "detail": f"distribution index rendered_hash for {plan.skill_slug} is outdated",
                }
            )
        if (
            plan.metadata_hash is not None
            and index_entry.get("metadata_hash") != plan.metadata_hash
        ):
            issues.append(
                {
                    "reason": "stale_index",
                    "detail": f"distribution index metadata_hash for {plan.skill_slug} is outdated",
                }
            )
        if transport is not None and index_entry.get("transport") not in {None, transport}:
            issues.append(
                {
                    "reason": "stale_index",
                    "detail": f"distribution index transport for {plan.skill_slug} is outdated",
                }
            )

    def _inspect_unexpected_index_entries(
        self,
        expected_by_target: Mapping[str, set[str]],
        index_cache: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for target_id, adapter in self.adapters.items():
            index = index_cache.get(target_id)
            if index is None:
                index = self._load_index_for_target(target_id)
                index_cache[target_id] = index
            expected = expected_by_target.get(target_id, set())
            for slug, entry in sorted(index["entries"].items()):
                if slug in expected:
                    continue
                issues.append(
                    {
                        "slug": slug,
                        "target": target_id,
                        "profile": adapter.profile,
                        "mode": "unexpected",
                        "outputs": self._entry_outputs(entry),
                        "index_path": adapter.index_relpath,
                        "status": "issue",
                        "issues": [
                            {
                                "reason": "unexpected_distribution_entry",
                                "detail": "distribution index contains a skill that is no longer selected for this target",
                            }
                        ],
                    }
                )
        return issues

    def _entry_outputs(self, entry: object) -> list[str]:
        if not isinstance(entry, Mapping):
            return []
        outputs = entry.get("outputs")
        if not isinstance(outputs, list):
            return []
        return [output for output in outputs if isinstance(output, str)]

    def _load_index_for_target(self, target_id: str) -> dict[str, Any]:
        adapter = self.adapters[target_id]
        index_path = self.repo_root / adapter.index_relpath
        if not index_path.is_file():
            return {
                "target": target_id,
                "adapter_version": adapter.adapter_version,
                "entries": {},
            }
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValidationError(f"Distribution index must be a mapping: {adapter.index_relpath}")
        entries = data.get("entries")
        if not isinstance(entries, dict):
            raise ValidationError(
                f"Distribution index entries must be a mapping: {adapter.index_relpath}"
            )
        return {
            "target": target_id,
            "adapter_version": data.get("adapter_version", adapter.adapter_version),
            "entries": dict(entries),
        }

    def _load_index(self, plan: DistributionPlan) -> dict[str, Any]:
        index = self._load_index_for_target(plan.target_id)
        index["adapter_version"] = plan.adapter_version
        return index

    def _update_index(
        self,
        index_cache: dict[str, dict[str, Any]],
        plan: DistributionPlan,
        result: Mapping[str, Any],
    ) -> None:
        index = index_cache.get(plan.target_id)
        if index is None:
            index = self._load_index(plan)
            index_cache[plan.target_id] = index
        entry: dict[str, Any] = {
            "canonical_path": plan.canonical_path,
            "canonical_hash": plan.canonical_hash,
            "outputs": list(plan.output_relpaths),
            "profile": plan.profile,
        }
        if plan.governance_metadata:
            entry["governance"] = plan.governance_metadata
        if plan.rendered_hash is not None:
            entry["rendered_hash"] = plan.rendered_hash
        if plan.metadata_hash is not None:
            entry["metadata_hash"] = plan.metadata_hash
        if "transport" in result:
            entry["transport"] = result["transport"]
        if "bundle_hash" in result:
            entry["bundle_hash"] = result["bundle_hash"]
        index["entries"][plan.skill_slug] = entry

    def _write_indexes(self, index_cache: Mapping[str, Mapping[str, Any]]) -> None:
        for target_id, payload in index_cache.items():
            adapter = self.adapters[target_id]
            index_path = self.repo_root / adapter.index_relpath
            _write_json(index_path, payload)


def _split_cli_values(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    items: list[str] = []
    for value in values:
        for part in value.split(","):
            normalized = part.strip()
            if normalized:
                items.append(normalized)
    return items


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Distribute Engram skills to configured built-in external targets."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to the target Engram repository root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--skill",
        action="append",
        dest="skills",
        help="Limit distribution to one or more skill slugs. Repeat or pass comma-separated values.",
    )
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        help="Limit distribution to one or more built-in targets. Repeat or pass comma-separated values.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write or update external target projections. Default is a dry-run preview.",
    )
    parser.add_argument(
        "--force-copy",
        action="store_true",
        help="Disable symlink attempts for canonical-bundle targets and always copy instead.",
    )
    return parser.parse_args(argv)


def build_distribution_report(
    repo_root: Path,
    *,
    slugs: list[str] | None = None,
    targets: list[str] | None = None,
    dry_run: bool = True,
    prefer_symlink: bool = True,
) -> tuple[dict[str, Any], int]:
    try:
        distributor = SkillDistributor(repo_root)
        report = distributor.distribute_all(
            slugs=slugs,
            targets=targets,
            dry_run=dry_run,
            prefer_symlink=prefer_symlink,
        )
    except ValidationError as exc:
        return (
            {
                "repo_root": str(Path(repo_root).resolve()),
                "status": "error",
                "error": str(exc),
                "dry_run": dry_run,
                "applied": not dry_run,
                "planned_count": 0,
                "distributed_count": 0,
                "skipped_count": 0,
                "failure_count": 0,
                "planned": [],
                "distributed": [],
                "skipped": [],
                "failed": [],
            },
            1,
        )

    return report, 0 if report["status"] == "ok" else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report, code = build_distribution_report(
        repo_root,
        slugs=_split_cli_values(args.skills),
        targets=_split_cli_values(args.targets),
        dry_run=not args.apply,
        prefer_symlink=not args.force_copy,
    )
    print(json.dumps(report, indent=2))
    return code


__all__ = [
    "BUILTIN_TARGETS",
    "DistributionPlan",
    "KNOWN_DISTRIBUTION_TARGETS",
    "SkillDistributor",
    "TransportCapabilities",
    "build_distribution_report",
    "main",
    "normalize_distribution_targets",
    "parse_args",
    "resolve_skill_distribution_targets",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
