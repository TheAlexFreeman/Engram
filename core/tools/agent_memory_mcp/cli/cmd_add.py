"""Implementation of the ``engram add`` subcommand."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..errors import ValidationError
from ..git_repo import GitRepo
from ..knowledge_ingestion import (
    apply_prepared_knowledge_add,
    build_knowledge_add_preview,
    knowledge_add_new_state,
    prepare_knowledge_add,
    slugify_filename_stem,
    summary_entry_from_content,
)
from ..models import MemoryWriteResult
from ..tools.semantic.session_tools import (
    _access_jsonl_for,
    _append_access_entries,
    _resolve_access_session_id,
)
from .formatting import render_governed_preview, render_write_result


def register_add(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "add",
        help="Add external knowledge into memory/knowledge/_unverified with generated provenance.",
        parents=parents or [],
    )
    parser.add_argument(
        "namespace",
        help="Knowledge namespace or explicit destination path, such as knowledge/react or memory/knowledge/_unverified/react/note.md.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Markdown file to ingest. Omit or use '-' to read from stdin.",
    )
    parser.add_argument(
        "--name",
        help="Optional filename stem when reading from stdin or when overriding the source filename.",
    )
    parser.add_argument(
        "--source",
        default="external-research",
        help="Provenance string stored in frontmatter (default: external-research).",
    )
    parser.add_argument(
        "--session-id",
        help="Canonical memory/activity/YYYY/MM/DD/chat-NNN id. Defaults to MEMORY_SESSION_ID or memory/activity/CURRENT_SESSION when available.",
    )
    parser.add_argument(
        "--summary-entry",
        help="Optional summary text inserted into memory/knowledge/_unverified/SUMMARY.md.",
    )
    parser.add_argument(
        "--expires",
        help="Optional ISO date (YYYY-MM-DD) stored in frontmatter for time-bound knowledge.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show the governed preview envelope without writing or committing.",
    )
    parser.set_defaults(handler=run_add)
    return parser


def _content_prefix(repo_root: Path, content_root: Path) -> str:
    try:
        return content_root.relative_to(repo_root).as_posix()
    except ValueError:
        return ""


def _read_input(raw_input: str | None) -> tuple[str, str | None]:
    if raw_input is None or raw_input == "-":
        return sys.stdin.read(), None

    input_path = Path(raw_input).expanduser().resolve()
    try:
        return input_path.read_text(encoding="utf-8"), str(input_path)
    except OSError as exc:
        raise ValueError(f"Could not read input file: {raw_input}") from exc


def _derive_filename(content: str, *, input_path: str | None, name: str | None) -> str:
    if name:
        return f"{slugify_filename_stem(Path(name).stem)}.md"
    if input_path:
        return f"{slugify_filename_stem(Path(input_path).stem)}.md"

    summary_entry = summary_entry_from_content(content, "stdin")
    if summary_entry == "stdin":
        raise ValueError("--name is required when reading stdin without an H1 heading")
    return f"{slugify_filename_stem(summary_entry)}.md"


def _normalize_destination(namespace: str, *, filename: str) -> str:
    normalized = namespace.replace("\\", "/").strip().strip("/")
    if normalized.startswith("core/"):
        normalized = normalized[len("core/") :]
    if not normalized:
        raise ValueError("namespace must not be empty")

    if normalized.startswith("memory/knowledge/_unverified/"):
        base = normalized
    elif normalized == "memory/knowledge/_unverified":
        base = normalized
    elif normalized.startswith("memory/knowledge/"):
        suffix = normalized[len("memory/knowledge/") :]
        if suffix.startswith("_unverified/"):
            base = f"memory/knowledge/{suffix}"
        elif suffix:
            base = f"memory/knowledge/_unverified/{suffix}"
        else:
            base = "memory/knowledge/_unverified"
    elif normalized == "knowledge":
        base = "memory/knowledge/_unverified"
    elif normalized.startswith("knowledge/"):
        suffix = normalized[len("knowledge/") :]
        if suffix.startswith("_unverified/"):
            base = f"memory/knowledge/{suffix}"
        elif suffix:
            base = f"memory/knowledge/_unverified/{suffix}"
        else:
            base = "memory/knowledge/_unverified"
    else:
        raise ValueError(
            "namespace must point under knowledge/, memory/knowledge/, or memory/knowledge/_unverified/"
        )

    if base.endswith(".md"):
        return base
    return f"{base.rstrip('/')}/{filename}"


def _build_access_entries(path: str, *, source: str) -> list[dict[str, object]]:
    return [
        {
            "file": path,
            "task": "engram add",
            "helpfulness": 1.0,
            "note": f"Created via engram add from source {source}",
            "mode": "create",
            "estimator": "cli",
        }
    ]


def run_add(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    content, input_path = _read_input(getattr(args, "input", None))
    filename = _derive_filename(content, input_path=input_path, name=getattr(args, "name", None))
    destination = _normalize_destination(args.namespace, filename=filename)

    repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
    resolved_session_id = _resolve_access_session_id(
        content_root, getattr(args, "session_id", None), user_id=None
    )
    if resolved_session_id is None:
        raise ValidationError(
            "session_id is required when MEMORY_SESSION_ID and memory/activity/CURRENT_SESSION are unset"
        )

    prepared = prepare_knowledge_add(
        repo,
        content_root,
        path=destination,
        content=content,
        source=args.source,
        session_id=resolved_session_id,
        trust="low",
        summary_entry=getattr(args, "summary_entry", None),
        expires=getattr(args, "expires", None),
    )
    access_jsonl = _access_jsonl_for(prepared.path)
    preview_payload = build_knowledge_add_preview(
        prepared,
        mode="preview" if args.preview else "apply",
        access_jsonl=access_jsonl,
        access_log_exists=bool(access_jsonl and (content_root / access_jsonl).exists()),
        include_access_log=True,
    )

    if args.preview:
        result = MemoryWriteResult(
            files_changed=[prepared.path],
            commit_sha=None,
            commit_message=None,
            new_state=knowledge_add_new_state(prepared, access_jsonl=access_jsonl),
            warnings=prepared.warnings,
            preview=preview_payload,
        )
        if args.json:
            print(result.to_json())
        else:
            print(render_governed_preview(preview_payload))
        return 0

    files_changed = apply_prepared_knowledge_add(repo, prepared)
    access_files, _scan_entry_count = _append_access_entries(
        repo,
        content_root,
        _build_access_entries(prepared.path, source=prepared.source),
        session_id=resolved_session_id,
        user_id=None,
    )
    files_changed.extend(path for path in access_files if path not in files_changed)
    commit_result = repo.commit(prepared.commit_message)
    version_token = repo.hash_object(prepared.path)
    result = MemoryWriteResult.from_commit(
        files_changed=files_changed,
        commit_result=commit_result,
        commit_message=prepared.commit_message,
        new_state=knowledge_add_new_state(
            prepared,
            version_token=version_token,
            access_jsonl=access_jsonl,
        ),
        warnings=prepared.warnings,
        preview=preview_payload,
    )

    if args.json:
        print(result.to_json())
    else:
        print(render_write_result(result.to_dict()))
    return 0
