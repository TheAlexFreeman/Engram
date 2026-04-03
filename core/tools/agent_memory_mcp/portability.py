"""Shared portability bundle helpers for CLI export/import commands."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml  # type: ignore[import-untyped]

from .errors import ValidationError
from .git_repo import GitRepo
from .models import MemoryWriteResult
from .preview_contract import build_governed_preview, preview_target

PORTABILITY_BUNDLE_KIND = "engram-portability-bundle"
PORTABILITY_BUNDLE_VERSION = 1
DEFAULT_EXPORT_TARGETS = (
    "core/INIT.md",
    "core/governance/review-queue.md",
    "core/memory",
)
_MARKDOWN_FENCE = "````"
_BACKTICK_RUN_RE = re.compile(r"`+")
_MARKDOWN_SECTION_RE = re.compile(
    r"^## File: (?P<path>[^\n]+)\n"
    r"<!-- sha256: (?P<sha>[0-9a-f]{64}) size_bytes: (?P<size>\d+) encoding: (?P<encoding>[a-z0-9-]+) -->\n\n"
    r"(?P<fence>`{4,})[^\n]*\n"
    r"(?P<content>.*?)(?=^(?P=fence)\n?)^(?P=fence)\n?",
    re.MULTILINE | re.DOTALL,
)
_MAX_PREVIEW_TARGETS = 50


@dataclass(frozen=True, slots=True)
class BundleFile:
    path: str
    content: str
    encoding: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_bytes(cls, path: str, content: bytes) -> "BundleFile":
        try:
            rendered_content = content.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            rendered_content = base64.b64encode(content).decode("ascii")
            encoding = "base64"
        return cls(
            path=path,
            content=rendered_content,
            encoding=encoding,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )

    @property
    def raw_bytes(self) -> bytes:
        if self.encoding == "utf-8":
            return self.content.encode("utf-8")
        if self.encoding == "base64":
            return base64.b64decode(self.content.encode("ascii"))
        raise ValidationError(f"Unsupported bundle file encoding: {self.encoding}")

    def to_dict(self, *, include_content: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "encoding": self.encoding,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }
        if include_content:
            payload["content"] = self.content
        return payload


@dataclass(frozen=True, slots=True)
class PortabilityBundle:
    bundle_format: str
    exported_at: str
    source_repo: str
    included_targets: list[str]
    files: list[BundleFile]

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_bytes(self) -> int:
        return sum(file.size_bytes for file in self.files)

    @property
    def root_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for file in self.files:
            root = _bundle_root(file.path)
            counts[root] = counts.get(root, 0) + 1
        return counts

    def manifest(self, *, include_contents: bool) -> dict[str, Any]:
        return {
            "kind": PORTABILITY_BUNDLE_KIND,
            "bundle_version": PORTABILITY_BUNDLE_VERSION,
            "format": self.bundle_format,
            "exported_at": self.exported_at,
            "source_repo": self.source_repo,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "included_targets": list(self.included_targets),
            "root_counts": dict(self.root_counts),
            "files": [file.to_dict(include_content=include_contents) for file in self.files],
        }


def _bundle_root(path: str) -> str:
    if path == "core/INIT.md":
        return path
    if path == "core/governance/review-queue.md":
        return path
    return "core/memory"


def _normalize_bundle_path(raw_path: object) -> str:
    path = str(raw_path or "").replace("\\", "/").strip()
    if not path:
        raise ValidationError("bundle file path must not be empty")
    if path.startswith("/"):
        raise ValidationError(f"bundle file path must be repo-relative: {path}")

    normalized = PurePosixPath(path).as_posix()
    pure = PurePosixPath(normalized)
    if any(part in {".", ".."} for part in pure.parts):
        raise ValidationError(f"bundle file path must not traverse directories: {path}")

    if normalized == "core/INIT.md" or normalized == "core/governance/review-queue.md":
        return normalized
    if normalized.startswith("core/memory/"):
        return normalized

    raise ValidationError(
        f"bundle file path is outside the supported portability roots: {normalized}"
    )


def _content_relative_path(bundle_path: str) -> str:
    normalized = _normalize_bundle_path(bundle_path)
    if not normalized.startswith("core/"):
        raise ValidationError(f"bundle file path must resolve under core/: {bundle_path}")
    return normalized[len("core/") :]


def _language_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".py": "python",
        ".js": "javascript",
        ".html": "html",
        ".css": "css",
        ".txt": "text",
    }.get(suffix, "text")


def _markdown_fence_for_content(content: str) -> str:
    longest_run = max(
        (len(match.group(0)) for match in _BACKTICK_RUN_RE.finditer(content)), default=0
    )
    return "`" * max(len(_MARKDOWN_FENCE), longest_run + 1)


def _read_export_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _decode_bundle_content(content: str, *, encoding: str, path: str) -> bytes:
    try:
        return content.encode("utf-8") if encoding == "utf-8" else base64.b64decode(content)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValidationError(f"Bundle file {path} could not decode its encoded content.") from exc


def _resolve_markdown_content(
    *,
    path: str,
    encoding: str,
    declared_sha: str,
    declared_size: int,
    content: str,
) -> str:
    candidates = [content]
    if content.endswith("\n"):
        candidates.append(content[:-1])

    for candidate in candidates:
        raw_bytes = _decode_bundle_content(candidate, encoding=encoding, path=path)
        if len(raw_bytes) != declared_size:
            continue
        if hashlib.sha256(raw_bytes).hexdigest() == declared_sha:
            return candidate

    return content


def build_portability_bundle(repo_root: Path) -> PortabilityBundle:
    files: dict[str, BundleFile] = {}
    included_targets: list[str] = []

    for target in DEFAULT_EXPORT_TARGETS:
        abs_target = repo_root / target
        if not abs_target.exists():
            continue

        included_targets.append(target)
        if abs_target.is_dir():
            for path in sorted(
                candidate for candidate in abs_target.rglob("*") if candidate.is_file()
            ):
                rel_path = path.relative_to(repo_root).as_posix()
                files[rel_path] = BundleFile.from_bytes(
                    rel_path,
                    _read_export_bytes(path),
                )
            continue

        rel_path = abs_target.relative_to(repo_root).as_posix()
        files[rel_path] = BundleFile.from_bytes(
            rel_path,
            _read_export_bytes(abs_target),
        )

    if not files:
        raise ValidationError("No portability targets were found under the default export roots.")

    return PortabilityBundle(
        bundle_format="json",
        exported_at=datetime.now(timezone.utc).isoformat(),
        source_repo=repo_root.name,
        included_targets=included_targets,
        files=sorted(files.values(), key=lambda item: item.path),
    )


def render_json_bundle(bundle: PortabilityBundle) -> str:
    payload = PortabilityBundle(
        bundle_format="json",
        exported_at=bundle.exported_at,
        source_repo=bundle.source_repo,
        included_targets=bundle.included_targets,
        files=bundle.files,
    ).manifest(include_contents=True)
    return json.dumps(payload, indent=2, sort_keys=False)


def render_markdown_bundle(bundle: PortabilityBundle) -> str:
    header = PortabilityBundle(
        bundle_format="md",
        exported_at=bundle.exported_at,
        source_repo=bundle.source_repo,
        included_targets=bundle.included_targets,
        files=bundle.files,
    )
    frontmatter = yaml.safe_dump(
        {
            "kind": PORTABILITY_BUNDLE_KIND,
            "bundle_version": PORTABILITY_BUNDLE_VERSION,
            "format": "md",
            "exported_at": header.exported_at,
            "source_repo": header.source_repo,
            "file_count": header.file_count,
            "total_bytes": header.total_bytes,
            "included_targets": header.included_targets,
            "root_counts": header.root_counts,
        },
        sort_keys=False,
    ).strip()

    pieces = [
        "---\n",
        frontmatter,
        "\n---\n\n",
        "# Engram Export Bundle\n\n",
        "Generated by `engram export`.\n\n",
        "## Bundle Summary\n\n",
        f"- File count: {header.file_count}\n",
        f"- Total bytes: {header.total_bytes}\n",
        f"- Included targets: {', '.join(header.included_targets)}\n",
    ]

    for file in header.files:
        content = file.content
        fence = _markdown_fence_for_content(content)
        pieces.extend(
            [
                "\n",
                f"## File: {file.path}\n",
                f"<!-- sha256: {file.sha256} size_bytes: {file.size_bytes} encoding: {file.encoding} -->\n\n",
                f"{fence}{_language_for_path(file.path)}\n",
                content,
            ]
        )
        if content and not content.endswith("\n"):
            pieces.append("\n")
        pieces.append(f"{fence}\n")

    return "".join(pieces)


def write_tar_bundle(bundle: PortabilityBundle, output_path: Path) -> dict[str, Any]:
    archive_bundle = PortabilityBundle(
        bundle_format="tar",
        exported_at=bundle.exported_at,
        source_repo=bundle.source_repo,
        included_targets=bundle.included_targets,
        files=bundle.files,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(output_path, "w") as archive:
        manifest_bytes = json.dumps(
            archive_bundle.manifest(include_contents=False),
            indent=2,
            sort_keys=False,
        ).encode("utf-8")
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest_bytes)
        archive.addfile(manifest_info, io.BytesIO(manifest_bytes))

        for file in archive_bundle.files:
            encoded = file.raw_bytes
            info = tarfile.TarInfo(file.path)
            info.size = len(encoded)
            archive.addfile(info, io.BytesIO(encoded))

    return export_summary(archive_bundle, output_path=str(output_path.resolve()))


def export_summary(bundle: PortabilityBundle, *, output_path: str | None) -> dict[str, Any]:
    return {
        "kind": PORTABILITY_BUNDLE_KIND,
        "bundle_version": PORTABILITY_BUNDLE_VERSION,
        "format": bundle.bundle_format,
        "output_path": output_path,
        "file_count": bundle.file_count,
        "total_bytes": bundle.total_bytes,
        "included_targets": list(bundle.included_targets),
        "root_counts": dict(bundle.root_counts),
    }


def write_text_bundle(bundle_text: str, output_path: Path, *, bundle_format: str) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(bundle_text)
    payload = json.loads(bundle_text) if bundle_format == "json" else None
    if isinstance(payload, dict):
        return {
            "kind": payload.get("kind"),
            "bundle_version": payload.get("bundle_version"),
            "format": bundle_format,
            "output_path": str(output_path.resolve()),
            "file_count": payload.get("file_count"),
            "total_bytes": payload.get("total_bytes"),
            "included_targets": payload.get("included_targets"),
            "root_counts": payload.get("root_counts"),
        }

    bundle = load_bundle_from_text(bundle_text, bundle_format=bundle_format)
    return export_summary(bundle, output_path=str(output_path.resolve()))


def load_bundle(source_path: Path) -> PortabilityBundle:
    if not source_path.exists():
        raise ValidationError(f"Bundle source not found: {source_path}")

    if tarfile.is_tarfile(source_path):
        return _load_tar_bundle(source_path)

    try:
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        raise ValidationError(f"Bundle source must be UTF-8 text or tar: {source_path}") from exc

    stripped = text.lstrip()
    if stripped.startswith("{"):
        return load_bundle_from_text(text, bundle_format="json")
    if text.startswith("---\n"):
        return load_bundle_from_text(text, bundle_format="md")

    raise ValidationError(
        "Unsupported bundle source. Expected JSON, markdown, or tar generated by engram export."
    )


def load_bundle_from_text(text: str, *, bundle_format: str) -> PortabilityBundle:
    if bundle_format == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Bundle JSON is invalid: {exc}") from exc
        return _bundle_from_payload(payload, bundle_format="json")

    if bundle_format == "md":
        return _load_markdown_bundle(text)

    raise ValidationError(f"Unsupported bundle text format: {bundle_format}")


def _bundle_from_payload(payload: Any, *, bundle_format: str) -> PortabilityBundle:
    if not isinstance(payload, dict):
        raise ValidationError("Bundle payload must be a JSON object.")

    if payload.get("kind") != PORTABILITY_BUNDLE_KIND:
        raise ValidationError(
            f"Bundle kind must be {PORTABILITY_BUNDLE_KIND!r}, got: {payload.get('kind')!r}"
        )

    raw_bundle_version = payload.get("bundle_version")
    try:
        bundle_version = int(str(raw_bundle_version))
    except (TypeError, ValueError) as exc:
        raise ValidationError("bundle_version must be an integer.") from exc
    if bundle_version != PORTABILITY_BUNDLE_VERSION:
        raise ValidationError(
            f"Unsupported bundle version: {bundle_version}. Expected {PORTABILITY_BUNDLE_VERSION}."
        )

    declared_format = str(payload.get("format") or "")
    if declared_format and declared_format != bundle_format:
        raise ValidationError(
            f"Bundle format mismatch: payload declares {declared_format!r}, expected {bundle_format!r}."
        )

    exported_at = str(payload.get("exported_at") or "").strip()
    if not exported_at:
        raise ValidationError("Bundle exported_at must be present.")

    source_repo = str(payload.get("source_repo") or "").strip()
    included_targets_raw = payload.get("included_targets")
    if included_targets_raw is None:
        included_targets = list(DEFAULT_EXPORT_TARGETS)
    elif isinstance(included_targets_raw, list) and all(
        isinstance(item, str) for item in included_targets_raw
    ):
        included_targets = list(included_targets_raw)
    else:
        raise ValidationError("included_targets must be a list of strings.")

    raw_files = payload.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValidationError("Bundle must contain a non-empty files list.")

    seen_paths: set[str] = set()
    files: list[BundleFile] = []
    for item in raw_files:
        if not isinstance(item, dict):
            raise ValidationError("Each bundle file entry must be an object.")
        path = _normalize_bundle_path(item.get("path"))
        if path in seen_paths:
            raise ValidationError(f"Duplicate bundle file path: {path}")
        seen_paths.add(path)

        content = item.get("content")
        if not isinstance(content, str):
            raise ValidationError(f"Bundle file {path} is missing text content.")

        encoding = str(item.get("encoding") or "utf-8").strip()
        if encoding not in {"utf-8", "base64"}:
            raise ValidationError(f"Bundle file {path} uses an unsupported encoding: {encoding}")

        raw_bytes = _decode_bundle_content(content, encoding=encoding, path=path)

        bundle_file = BundleFile.from_bytes(path, raw_bytes)
        if bundle_file.encoding != encoding:
            bundle_file = BundleFile(
                path=bundle_file.path,
                content=content,
                encoding=encoding,
                sha256=bundle_file.sha256,
                size_bytes=bundle_file.size_bytes,
            )

        declared_sha = str(item.get("sha256") or "").strip()
        if declared_sha and declared_sha != bundle_file.sha256:
            raise ValidationError(f"Bundle file {path} failed sha256 validation.")

        declared_size = item.get("size_bytes")
        if declared_size is not None:
            try:
                size_value = int(declared_size)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    f"Bundle file {path} has an invalid size_bytes value."
                ) from exc
            if size_value != bundle_file.size_bytes:
                raise ValidationError(f"Bundle file {path} failed size_bytes validation.")

        files.append(bundle_file)

    bundle = PortabilityBundle(
        bundle_format=bundle_format,
        exported_at=exported_at,
        source_repo=source_repo,
        included_targets=included_targets,
        files=sorted(files, key=lambda item: item.path),
    )

    expected_count = payload.get("file_count")
    if expected_count is not None and int(expected_count) != bundle.file_count:
        raise ValidationError("Bundle file_count does not match the parsed file entries.")
    expected_total_bytes = payload.get("total_bytes")
    if expected_total_bytes is not None and int(expected_total_bytes) != bundle.total_bytes:
        raise ValidationError("Bundle total_bytes does not match the parsed file entries.")
    return bundle


def _load_markdown_bundle(text: str) -> PortabilityBundle:
    frontmatter_payload, body = _split_markdown_frontmatter(text)
    matches = list(_MARKDOWN_SECTION_RE.finditer(body))
    if not matches:
        raise ValidationError("Markdown bundle does not contain any file sections.")

    files: list[dict[str, Any]] = []
    for match in matches:
        path = match.group("path")
        encoding = match.group("encoding")
        declared_sha = match.group("sha")
        declared_size = int(match.group("size"))
        files.append(
            {
                "path": path,
                "encoding": encoding,
                "sha256": declared_sha,
                "size_bytes": declared_size,
                "content": _resolve_markdown_content(
                    path=path,
                    encoding=encoding,
                    declared_sha=declared_sha,
                    declared_size=declared_size,
                    content=match.group("content"),
                ),
            }
        )

    payload = dict(frontmatter_payload)
    payload["files"] = files
    return _bundle_from_payload(payload, bundle_format="md")


def _split_markdown_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValidationError("Markdown bundle must start with YAML frontmatter.")

    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise ValidationError("Markdown bundle frontmatter is not closed.")

    frontmatter = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1 :])
    try:
        payload = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as exc:
        raise ValidationError(f"Markdown bundle frontmatter is invalid YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Markdown bundle frontmatter must be a mapping.")
    return payload, body


def _load_tar_bundle(source_path: Path) -> PortabilityBundle:
    with tarfile.open(source_path, "r") as archive:
        try:
            manifest_member = archive.getmember("manifest.json")
        except KeyError as exc:
            raise ValidationError("Tar bundle is missing manifest.json.") from exc

        manifest_file = archive.extractfile(manifest_member)
        if manifest_file is None:
            raise ValidationError("Tar bundle manifest.json could not be read.")

        try:
            manifest = json.load(manifest_file)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Tar bundle manifest.json is invalid JSON: {exc}") from exc

        if not isinstance(manifest, dict):
            raise ValidationError("Tar bundle manifest must be a JSON object.")

        raw_files = manifest.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            raise ValidationError("Tar bundle manifest must contain a non-empty files list.")

        hydrated_files: list[dict[str, Any]] = []
        for item in raw_files:
            if not isinstance(item, dict):
                raise ValidationError("Each tar bundle file entry must be an object.")
            path = _normalize_bundle_path(item.get("path"))
            try:
                member = archive.getmember(path)
            except KeyError as exc:
                raise ValidationError(f"Tar bundle is missing file content for {path}.") from exc

            file_object = archive.extractfile(member)
            if file_object is None:
                raise ValidationError(f"Tar bundle could not read file content for {path}.")
            data = file_object.read()
            hydrated_file = BundleFile.from_bytes(path, data)
            encoding = str(item.get("encoding") or hydrated_file.encoding).strip()
            if encoding not in {"utf-8", "base64"}:
                raise ValidationError(
                    f"Tar bundle file {path} uses an unsupported encoding: {encoding}"
                )

            hydrated_files.append(
                {
                    "path": path,
                    "encoding": encoding,
                    "sha256": item.get("sha256"),
                    "size_bytes": item.get("size_bytes"),
                    "content": hydrated_file.content,
                }
            )

        payload = dict(manifest)
        payload["files"] = hydrated_files
        return _bundle_from_payload(payload, bundle_format="tar")


def preview_import_bundle(
    repo_root: Path,
    content_root: Path,
    source_path: Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    del content_root

    bundle = load_bundle(source_path)
    created, conflicting, unchanged = _classify_bundle_files(repo_root, bundle)
    target_files = [
        preview_target(
            file.path,
            "create" if file.path in created else "update",
            details=f"sha256 {file.sha256[:12]} | {file.size_bytes} bytes",
        )
        for file in bundle.files
        if file.path in created or file.path in conflicting
    ]
    warnings: list[str] = []
    if conflicting and not overwrite:
        warnings.append(
            f"{len(conflicting)} existing paths would block apply until you rerun with --overwrite."
        )
    if unchanged:
        warnings.append(f"{len(unchanged)} bundle files already match the current repo state.")
    if len(target_files) > _MAX_PREVIEW_TARGETS:
        omitted = len(target_files) - _MAX_PREVIEW_TARGETS
        target_files = target_files[:_MAX_PREVIEW_TARGETS]
        warnings.append(f"Preview target list truncated; {omitted} additional targets omitted.")

    commit_message = f"[portability] Import {bundle.file_count} files from {source_path.name}"
    new_state = {
        "source": str(source_path.resolve()),
        "format": bundle.bundle_format,
        "file_count": bundle.file_count,
        "total_bytes": bundle.total_bytes,
        "create_count": len(created),
        "update_count": len(conflicting),
        "unchanged_count": len(unchanged),
        "existing_conflicts": sorted(conflicting),
        "overwrite": overwrite,
        "can_apply": overwrite or not conflicting,
    }
    preview_payload = build_governed_preview(
        mode="preview",
        change_class="proposed",
        summary=f"Import {bundle.file_count} files from a portability bundle.",
        reasoning="Import is a proposed durable-memory write because it can create or overwrite persisted repository state under the supported portability roots.",
        target_files=target_files,
        invariant_effects=[
            "Restores only core/INIT.md, core/governance/review-queue.md, and files under core/memory/.",
            "Validates bundle kind, version, file digests, and per-file encodings before any apply step.",
            "Leaves files absent from the bundle untouched; import is additive or overwrite-only, not a destructive sync.",
        ],
        commit_message=commit_message,
        resulting_state=new_state,
        warnings=warnings,
    )
    result = MemoryWriteResult(
        files_changed=sorted(created | conflicting),
        commit_sha=None,
        commit_message=None,
        new_state=new_state,
        warnings=warnings,
        preview=preview_payload,
    )
    return result.to_dict()


def apply_import_bundle(
    repo_root: Path,
    content_root: Path,
    source_path: Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    bundle = load_bundle(source_path)
    created, conflicting, unchanged = _classify_bundle_files(repo_root, bundle)
    if conflicting and not overwrite:
        raise ValidationError(
            "Bundle import would overwrite existing paths. Re-run with --overwrite to allow updates:\n"
            + "\n".join(f"- {path}" for path in sorted(conflicting))
        )

    files_to_write = [
        file for file in bundle.files if file.path in created or file.path in conflicting
    ]
    if not files_to_write:
        raise ValidationError("Bundle import does not introduce any changes to this repository.")

    repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
    warnings: list[str] = []
    preview_dict = preview_import_bundle(
        repo_root,
        content_root,
        source_path,
        overwrite=overwrite,
    )
    preview_payload = preview_dict.get("preview") if isinstance(preview_dict, dict) else None
    preview = preview_payload if isinstance(preview_payload, dict) else None

    files_changed: list[str] = []
    for file in files_to_write:
        abs_path = repo_root / file.path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(file.raw_bytes)
        repo.add(_content_relative_path(file.path))
        files_changed.append(file.path)

    commit_message = f"[portability] Import {bundle.file_count} files from {source_path.name}"
    commit_result = repo.commit(commit_message)
    result = MemoryWriteResult.from_commit(
        files_changed=sorted(files_changed),
        commit_result=commit_result,
        commit_message=commit_message,
        new_state={
            "source": str(source_path.resolve()),
            "format": bundle.bundle_format,
            "file_count": bundle.file_count,
            "total_bytes": bundle.total_bytes,
            "created_paths": sorted(created),
            "updated_paths": sorted(conflicting),
            "unchanged_paths": sorted(unchanged),
            "overwrite": overwrite,
        },
        warnings=warnings,
        preview=preview,
    )
    return result.to_dict()


def _classify_bundle_files(
    repo_root: Path,
    bundle: PortabilityBundle,
) -> tuple[set[str], set[str], set[str]]:
    created: set[str] = set()
    conflicting: set[str] = set()
    unchanged: set[str] = set()

    for file in bundle.files:
        abs_path = repo_root / file.path
        if not abs_path.exists():
            created.add(file.path)
            continue

        if not abs_path.is_file():
            conflicting.add(file.path)
            continue

        current = _read_export_bytes(abs_path)
        if current == file.raw_bytes:
            unchanged.add(file.path)
        else:
            conflicting.add(file.path)

    return created, conflicting, unchanged


def _content_prefix(repo_root: Path, content_root: Path) -> str:
    try:
        return content_root.relative_to(repo_root).as_posix()
    except ValueError:
        return ""
