"""Skill source parsing and multi-source resolution helpers."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .path_policy import validate_slug
from .skill_hash import compute_content_hash, get_dir_stats

_GITHUB_OWNER_REPO_RE = r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+"


class SkillResolutionError(ValidationError):
    """Resolution failed with structured context for callers."""

    def __init__(self, source: str, reason: str, suggestions: list[str] | None = None):
        self.source = source
        self.reason = reason
        self.suggestions = list(suggestions or [])
        detail = f"Skill source {source!r} could not be resolved: {reason}"
        if self.suggestions:
            detail += f" Suggestions: {'; '.join(self.suggestions)}"
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "reason": self.reason,
            "suggestions": list(self.suggestions),
        }


@dataclass(frozen=True, slots=True)
class SkillSourceSpec:
    source: str
    source_type: str
    ref: str | None = None
    owner: str | None = None
    repo: str | None = None
    git_url: str | None = None
    relative_path: str | None = None

    @property
    def normalized_source(self) -> str:
        if self.source_type == "github":
            assert self.owner is not None
            assert self.repo is not None
            return f"github:{self.owner}/{self.repo}"
        if self.source_type == "git":
            assert self.git_url is not None
            return f"git:{self.git_url}"
        if self.source_type == "path":
            assert self.relative_path is not None
            return f"path:{self.relative_path}"
        return "local"


@dataclass(frozen=True, slots=True)
class LockVerification:
    checked: bool
    source_matches: bool
    hash_matches: bool | None
    ref_matches: bool | None
    expected_source: str | None
    expected_hash: str | None
    actual_hash: str | None
    expected_ref: str | None
    actual_ref: str | None
    expected_requested_ref: str | None = None
    actual_requested_ref: str | None = None

    @property
    def usable(self) -> bool:
        return (
            self.checked
            and self.source_matches
            and self.hash_matches is True
            and self.ref_matches is not False
        )


@dataclass(frozen=True, slots=True)
class ResolvedSkill:
    slug: str
    source: str
    normalized_source: str
    source_type: str
    requested_ref: str | None
    resolved_ref: str | None
    skill_dir: Path
    resolution_mode: str
    content_hash: str
    file_count: int
    total_bytes: int
    lock_verification: LockVerification | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "slug": self.slug,
            "source": self.source,
            "normalized_source": self.normalized_source,
            "source_type": self.source_type,
            "requested_ref": self.requested_ref,
            "resolved_ref": self.resolved_ref,
            "skill_dir": str(self.skill_dir),
            "resolution_mode": self.resolution_mode,
            "content_hash": self.content_hash,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
        }
        if self.lock_verification is not None:
            payload["lock_verification"] = {
                "checked": self.lock_verification.checked,
                "source_matches": self.lock_verification.source_matches,
                "hash_matches": self.lock_verification.hash_matches,
                "ref_matches": self.lock_verification.ref_matches,
                "expected_source": self.lock_verification.expected_source,
                "expected_hash": self.lock_verification.expected_hash,
                "actual_hash": self.lock_verification.actual_hash,
                "expected_ref": self.lock_verification.expected_ref,
                "actual_ref": self.lock_verification.actual_ref,
                "expected_requested_ref": self.lock_verification.expected_requested_ref,
                "actual_requested_ref": self.lock_verification.actual_requested_ref,
                "usable": self.lock_verification.usable,
            }
        return payload


def parse_skill_source(source: str, *, ref: str | None = None) -> SkillSourceSpec:
    """Validate and parse the supported skill source formats."""

    if not isinstance(source, str) or not source.strip():
        raise ValidationError("source must be a non-empty string")
    normalized_source = source.strip()
    normalized_ref = ref.strip() if isinstance(ref, str) and ref.strip() else None

    if normalized_source == "local":
        if normalized_ref is not None:
            raise ValidationError("ref is only valid with github: or git: sources")
        return SkillSourceSpec(source=normalized_source, source_type="local")

    if normalized_source.startswith("github:"):
        owner_repo = normalized_source[len("github:") :]
        parts = owner_repo.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValidationError(f"source format invalid. Must match github:owner/repo: {source}")
        return SkillSourceSpec(
            source=normalized_source,
            source_type="github",
            ref=normalized_ref,
            owner=parts[0],
            repo=parts[1],
        )

    if normalized_source.startswith("git:"):
        git_url = normalized_source[len("git:") :]
        if not (
            git_url.startswith("https://")
            or git_url.startswith("http://")
            or git_url.startswith("git@")
            or git_url.startswith("file://")
        ):
            raise ValidationError(
                f"source format invalid. Must match git:https://..., git:git@..., or git:file://...: {source}"
            )
        return SkillSourceSpec(
            source=normalized_source,
            source_type="git",
            ref=normalized_ref,
            git_url=git_url,
        )

    if normalized_source.startswith("path:"):
        if normalized_ref is not None:
            raise ValidationError("ref is only valid with github: or git: sources")
        relative_path = normalized_source[len("path:") :]
        if not relative_path.startswith(("./", "../")):
            raise ValidationError(
                f"source format invalid. path: sources must be relative and start with ./ or ../: {source}"
            )
        return SkillSourceSpec(
            source=normalized_source,
            source_type="path",
            relative_path=relative_path,
        )

    raise ValidationError(
        "source format invalid. Must match one of: local, github:owner/repo, git:url, path:./relative or path:../relative"
    )


class SkillResolver:
    """Resolve skill sources from local, relative-path, or git-backed locations."""

    def __init__(self, repo_root: Path, *, cache_dir: Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.git_dir = self._resolve_git_dir(self.repo_root)
        self.cache_dir = cache_dir or (self.git_dir / "engram" / "skill-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve(
        self,
        source: str,
        *,
        slug: str | None = None,
        ref: str | None = None,
        lock_entry: dict[str, Any] | None = None,
        frozen: bool = False,
    ) -> ResolvedSkill:
        spec = parse_skill_source(source, ref=ref)
        if slug is not None:
            validate_slug(slug, field_name="slug")

        if spec.source_type == "local":
            resolved = self._resolve_local(spec, slug=slug)
        elif spec.source_type == "path":
            resolved = self._resolve_path(spec, slug=slug)
        else:
            locked = self._resolve_locked_copy(spec, slug=slug, lock_entry=lock_entry)
            if locked is not None:
                resolved = locked
            elif frozen:
                raise SkillResolutionError(
                    spec.source,
                    "frozen mode requires a fresh lock entry for remote sources",
                    [
                        "Run a non-frozen install or sync to refresh SKILLS.lock first.",
                        "Check that the lock entry source and content hash still match.",
                    ],
                )
            else:
                resolved = self._resolve_remote(spec, slug=slug)

        verification = self.verify_against_lock(resolved, lock_entry)
        if frozen and not verification.usable:
            raise SkillResolutionError(
                spec.source,
                "frozen mode rejected the resolved skill because the lock verification failed",
                [
                    "Refresh SKILLS.lock with a non-frozen sync or install.",
                    "Check that the requested ref matches the lock entry.",
                ],
            )
        if verification.checked:
            return ResolvedSkill(
                slug=resolved.slug,
                source=resolved.source,
                normalized_source=resolved.normalized_source,
                source_type=resolved.source_type,
                requested_ref=resolved.requested_ref,
                resolved_ref=resolved.resolved_ref,
                skill_dir=resolved.skill_dir,
                resolution_mode=resolved.resolution_mode,
                content_hash=resolved.content_hash,
                file_count=resolved.file_count,
                total_bytes=resolved.total_bytes,
                lock_verification=verification,
            )
        return resolved

    def verify_against_lock(
        self, resolved: ResolvedSkill, lock_entry: dict[str, Any] | None
    ) -> LockVerification:
        if not isinstance(lock_entry, dict) or not lock_entry:
            return LockVerification(
                checked=False,
                source_matches=False,
                hash_matches=None,
                ref_matches=None,
                expected_source=None,
                expected_hash=None,
                actual_hash=resolved.content_hash,
                expected_ref=None,
                actual_ref=resolved.resolved_ref,
                expected_requested_ref=None,
                actual_requested_ref=resolved.requested_ref,
            )

        expected_source = lock_entry.get("source")
        expected_hash = lock_entry.get("content_hash")
        expected_ref = lock_entry.get("resolved_ref")
        expected_requested_ref = lock_entry.get("requested_ref")
        source_matches = expected_source == resolved.normalized_source
        hash_matches = (
            expected_hash == resolved.content_hash if isinstance(expected_hash, str) else None
        )
        ref_matches: bool | None = None
        if isinstance(expected_requested_ref, str):
            ref_matches = expected_requested_ref == resolved.requested_ref
        elif isinstance(expected_ref, str):
            ref_matches = expected_ref == resolved.resolved_ref

        return LockVerification(
            checked=True,
            source_matches=source_matches,
            hash_matches=hash_matches,
            ref_matches=ref_matches,
            expected_source=expected_source if isinstance(expected_source, str) else None,
            expected_hash=expected_hash if isinstance(expected_hash, str) else None,
            actual_hash=resolved.content_hash,
            expected_ref=expected_ref if isinstance(expected_ref, str) else None,
            actual_ref=resolved.resolved_ref,
            expected_requested_ref=(
                expected_requested_ref if isinstance(expected_requested_ref, str) else None
            ),
            actual_requested_ref=resolved.requested_ref,
        )

    def _resolve_local(self, spec: SkillSourceSpec, *, slug: str | None) -> ResolvedSkill:
        if slug is None:
            raise SkillResolutionError(
                spec.source,
                "local sources require an explicit slug",
                ["Pass the manifest key or explicit slug when resolving source=local."],
            )
        skill_dir = self.repo_root / "core" / "memory" / "skills" / slug
        return self._build_resolved_skill(
            spec,
            slug=slug,
            skill_dir=skill_dir,
            resolved_ref=None,
            resolution_mode="local",
        )

    def _resolve_path(self, spec: SkillSourceSpec, *, slug: str | None) -> ResolvedSkill:
        assert spec.relative_path is not None
        skill_dir = (self.repo_root / spec.relative_path).resolve()
        resolved_slug = slug or skill_dir.name
        return self._build_resolved_skill(
            spec,
            slug=resolved_slug,
            skill_dir=skill_dir,
            resolved_ref=None,
            resolution_mode="path",
        )

    def _resolve_locked_copy(
        self,
        spec: SkillSourceSpec,
        *,
        slug: str | None,
        lock_entry: dict[str, Any] | None,
    ) -> ResolvedSkill | None:
        if not isinstance(lock_entry, dict) or not lock_entry:
            return None
        if lock_entry.get("source") != spec.normalized_source:
            return None
        resolved_path = lock_entry.get("resolved_path")
        if not isinstance(resolved_path, str) or not resolved_path.strip():
            return None
        skill_dir = (self.repo_root / resolved_path).resolve()
        try:
            skill_dir.relative_to(self.repo_root)
        except ValueError:
            return None
        if not skill_dir.is_dir():
            return None
        resolved_slug = slug or skill_dir.name.rstrip("/")
        resolved = self._build_resolved_skill(
            spec,
            slug=resolved_slug,
            skill_dir=skill_dir,
            resolved_ref=lock_entry.get("resolved_ref")
            if isinstance(lock_entry.get("resolved_ref"), str)
            else None,
            resolution_mode="locked",
        )
        verification = self.verify_against_lock(resolved, lock_entry)
        return resolved if verification.usable else None

    def _resolve_remote(self, spec: SkillSourceSpec, *, slug: str | None) -> ResolvedSkill:
        git_url = self._git_url_for_spec(spec)
        checkout_dir = self._prepare_checkout(spec, git_url)
        resolved_ref = self._checkout_ref(checkout_dir, spec.ref)
        skill_dir = self._discover_remote_skill_dir(checkout_dir, slug=slug)
        resolved_slug = slug or skill_dir.name
        return self._build_resolved_skill(
            spec,
            slug=resolved_slug,
            skill_dir=skill_dir,
            resolved_ref=resolved_ref,
            resolution_mode="remote",
        )

    def _build_resolved_skill(
        self,
        spec: SkillSourceSpec,
        *,
        slug: str,
        skill_dir: Path,
        resolved_ref: str | None,
        resolution_mode: str,
    ) -> ResolvedSkill:
        if not skill_dir.is_dir():
            raise SkillResolutionError(
                spec.source,
                f"skill directory not found: {skill_dir}",
                [
                    "Check the slug or source path.",
                    "Verify that the source contains a SKILL.md file.",
                ],
            )
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            raise SkillResolutionError(
                spec.source,
                f"resolved directory does not contain SKILL.md: {skill_dir}",
                [
                    "Point the source at a single skill directory.",
                    "Add SKILL.md to the source directory.",
                ],
            )
        content_hash = compute_content_hash(skill_dir)
        file_count, total_bytes = get_dir_stats(skill_dir)
        return ResolvedSkill(
            slug=slug,
            source=spec.source,
            normalized_source=spec.normalized_source,
            source_type=spec.source_type,
            requested_ref=spec.ref,
            resolved_ref=resolved_ref,
            skill_dir=skill_dir,
            resolution_mode=resolution_mode,
            content_hash=content_hash,
            file_count=file_count,
            total_bytes=total_bytes,
        )

    def _discover_remote_skill_dir(self, checkout_dir: Path, *, slug: str | None) -> Path:
        candidate_dirs: list[Path] = []
        if slug is not None:
            candidate_dirs.extend(
                [
                    checkout_dir / slug,
                    checkout_dir / "skills" / slug,
                    checkout_dir / "core" / "memory" / "skills" / slug,
                ]
            )
        candidate_dirs.append(checkout_dir)
        for candidate in candidate_dirs:
            if (candidate / "SKILL.md").is_file():
                return candidate

        discovered = [
            path.parent
            for path in sorted(checkout_dir.rglob("SKILL.md"))
            if ".git" not in path.parts
        ]
        if len(discovered) == 1:
            return discovered[0]
        if not discovered:
            raise SkillResolutionError(
                str(checkout_dir),
                "no SKILL.md files were found in the resolved repository",
                [
                    "Check that the repository publishes a skill directory.",
                    "Pass slug=... if the repo contains multiple skills.",
                ],
            )
        raise SkillResolutionError(
            str(checkout_dir),
            "multiple skill directories were found; slug is required to disambiguate",
            [
                "Pass the target skill slug explicitly.",
                "Use a repository that contains only one skill.",
            ],
        )

    def _prepare_checkout(self, spec: SkillSourceSpec, git_url: str) -> Path:
        key = hashlib.sha256(
            f"{spec.normalized_source}\n{spec.ref or ''}".encode("utf-8")
        ).hexdigest()[:16]
        target_dir = self.cache_dir / key
        if not target_dir.exists():
            self._run_git(["clone", git_url, str(target_dir)], cwd=self.repo_root)
        else:
            self._run_git(["fetch", "--all", "--tags", "--prune"], cwd=target_dir)
        return target_dir

    def _checkout_ref(self, checkout_dir: Path, ref: str | None) -> str:
        if ref:
            self._run_git(["checkout", ref], cwd=checkout_dir)
        else:
            self._run_git(["remote", "set-head", "origin", "--auto"], cwd=checkout_dir)
            result = self._run_git(["rev-parse", "origin/HEAD"], cwd=checkout_dir)
            tip = result.stdout.strip()
            self._run_git(["checkout", "--detach", tip], cwd=checkout_dir)
        result = self._run_git(["rev-parse", "HEAD"], cwd=checkout_dir)
        return result.stdout.strip()

    def _git_url_for_spec(self, spec: SkillSourceSpec) -> str:
        if spec.source_type == "git":
            assert spec.git_url is not None
            return spec.git_url
        if spec.source_type == "github":
            assert spec.owner is not None
            assert spec.repo is not None
            return self._github_clone_url(spec.owner, spec.repo)
        raise SkillResolutionError(
            spec.source,
            f"source type {spec.source_type!r} is not git-backed",
            [
                "Use local/path sources directly.",
                "Only github: and git: sources use remote resolution.",
            ],
        )

    def _github_clone_url(self, owner: str, repo: str) -> str:
        return f"https://github.com/{owner}/{repo}.git"

    def _resolve_git_dir(self, repo_root: Path) -> Path:
        result = self._run_git(["rev-parse", "--absolute-git-dir"], cwd=repo_root)
        return Path(result.stdout.strip()).resolve()

    def _run_git(self, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            joined = "git " + " ".join(args)
            raise SkillResolutionError(
                joined,
                result.stderr.strip() or "git command failed",
                [
                    "Verify the repository URL or ref.",
                    "Ensure git is installed and the source is reachable.",
                ],
            )
        return result


__all__ = [
    "LockVerification",
    "ResolvedSkill",
    "SkillResolutionError",
    "SkillResolver",
    "SkillSourceSpec",
    "parse_skill_source",
]
