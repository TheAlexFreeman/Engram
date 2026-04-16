"""Runtime bootstrap for the enhanced agent-memory MCP server."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from datetime import timezone
from pathlib import Path, PurePosixPath

from mcp.server.fastmcp import FastMCP

from .errors import StagingError
from .git_repo import GitRepo
from .path_policy import namespace_session_id, validate_session_id, validate_slug
from .session_state import create_session_state
from .tools import read_tools, semantic, write_tools

DeletePermissionHook = Callable[[str], None]


def _env_flag_enabled(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _resolve_user_id() -> str | None:
    raw_user_id = os.environ.get("MEMORY_USER_ID", "").strip()
    if not raw_user_id:
        return None
    return validate_slug(raw_user_id, field_name="MEMORY_USER_ID")


_CURRENT_SESSION_SENTINEL = PurePosixPath("memory/activity/CURRENT_SESSION")


def _current_session_sentinel_paths(user_id: str | None) -> list[PurePosixPath]:
    if user_id is None:
        return [_CURRENT_SESSION_SENTINEL]
    return [
        PurePosixPath("memory/activity") / user_id / "CURRENT_SESSION",
        _CURRENT_SESSION_SENTINEL,
    ]


def _resolve_startup_session_id(content_root: Path, user_id: str | None) -> str | None:
    env_session_id = os.environ.get("MEMORY_SESSION_ID", "").strip()
    if env_session_id:
        return namespace_session_id(validate_session_id(env_session_id), user_id=user_id)

    for sentinel_rel in _current_session_sentinel_paths(user_id):
        sentinel_path = content_root / sentinel_rel
        if not sentinel_path.exists():
            continue
        sentinel_session_id = sentinel_path.read_text(encoding="utf-8").strip()
        if not sentinel_session_id:
            continue
        return namespace_session_id(validate_session_id(sentinel_session_id), user_id=user_id)

    return None


def _startup_session_branch_name(
    *,
    user_id: str,
    session_start,
    resolved_session_id: str | None,
) -> str:
    if resolved_session_id is not None:
        parts = resolved_session_id.split("/")
        if len(parts) == 8:
            year, month, day, chat_slug = parts[4:]
        else:
            year, month, day, chat_slug = parts[3:]
        suffix = f"{year}-{month}-{day}-{chat_slug}"
    else:
        started_at = session_start.astimezone(timezone.utc)
        suffix = started_at.strftime("start-%Y%m%dt%H%M%Sz")
    return f"engram/sessions/{user_id}/{suffix}"


def _maybe_enable_session_branching(repo: GitRepo, session_state) -> None:
    if not _env_flag_enabled("MEMORY_ENABLE_SESSION_BRANCHES"):
        return
    if session_state.user_id is None:
        return

    resolved_session_id = _resolve_startup_session_id(repo.content_root, session_state.user_id)
    session_branch = _startup_session_branch_name(
        user_id=session_state.user_id,
        session_start=session_state.session_start,
        resolved_session_id=resolved_session_id,
    )
    session_branch_ref = f"refs/heads/{session_branch}"
    persisted_metadata = repo.load_session_branch_metadata(session_branch)
    if persisted_metadata is not None:
        session_state.publication_base_branch = persisted_metadata["base_branch"]
        session_state.publication_base_ref = persisted_metadata["base_ref"]

    if repo.current_branch_name() == session_branch:
        if persisted_metadata is None:
            raise StagingError(
                "Session branch isolation found an existing session branch checkout without persisted base metadata. "
                "Switch back to the original base branch and re-enable MEMORY_ENABLE_SESSION_BRANCHES, or recreate the session branch."
            )
        session_state.publication_session_branch = session_branch
        session_state.publication_session_branch_ref = session_branch_ref
        return

    if session_state.publication_base_branch is None or session_state.publication_base_ref is None:
        raise StagingError(
            "Session branch isolation requires an attached base branch at startup. "
            "Attach the worktree to a branch before enabling MEMORY_ENABLE_SESSION_BRANCHES."
        )

    checked_out_ref, _created = repo.ensure_branch_checked_out(
        session_branch,
        start_point=session_state.publication_base_ref,
    )
    persisted_metadata = repo.ensure_session_branch_metadata(
        session_branch,
        base_branch=session_state.publication_base_branch,
        base_ref=session_state.publication_base_ref,
    )
    session_state.publication_base_branch = persisted_metadata["base_branch"]
    session_state.publication_base_ref = persisted_metadata["base_ref"]
    session_state.publication_session_branch = session_branch
    session_state.publication_session_branch_ref = checked_out_ref


def resolve_repo_root(explicit_root: str | Path | None = None) -> Path:
    """Resolve the memory repo root, supporting old and new env var names."""
    if explicit_root is not None:
        root = Path(explicit_root).resolve()
        if root.is_dir():
            return root

        existing_parent = root
        while not existing_parent.exists() and existing_parent != existing_parent.parent:
            existing_parent = existing_parent.parent
        if existing_parent.is_dir():
            return existing_parent
        raise ValueError(f"Repository root is not a directory: {root}")

    for env_var in ("MEMORY_REPO_ROOT", "AGENT_MEMORY_ROOT"):
        env_value = os.environ.get(env_var)
        if not env_value:
            continue
        root = Path(env_value).resolve()
        if root.is_dir():
            return root
        print(
            f"Warning: {env_var}='{env_value}' is not a directory; falling back to"
            " file-relative detection.",
            file=sys.stderr,
        )

    return Path(__file__).resolve().parents[2]


def _build_delete_permission_hook(root: Path) -> DeletePermissionHook | None:
    """Build an optional delete-permission helper from the environment.

    If MEMORY_DELETE_PERMISSION_HELPER is set, it is executed with the target
    repo-relative path as its first argument before memory_delete removes the
    file. A non-zero exit status blocks the delete.
    """
    helper = os.environ.get("MEMORY_DELETE_PERMISSION_HELPER")
    if not helper:
        return None

    helper_path = Path(helper).expanduser()
    helper_cmd = str(helper_path if helper_path.is_absolute() else helper)

    def _grant(path: str) -> None:
        result = subprocess.run(
            [helper_cmd, path],
            cwd=str(root),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip() or (
                f"{helper_cmd} exited with {result.returncode}"
            )
            raise RuntimeError(message)

    return _grant


def _validate_repo_identity(repo: GitRepo) -> None:
    """Warn loudly if the resolved repo doesn't look like the expected Engram instance.

    Checks two signals:
    1. MEMORY_REPO_IDENTITY env var, if set, must match the repo's git remote or root name.
    2. The repo must contain core/INIT.md (Engram's routing entrypoint) — a lightweight
       structural fingerprint that catches stale worktrees and wrong-repo misconfigurations.
    """
    # Structural check: does this look like an Engram memory repo?
    init_md = repo.content_root / "INIT.md"
    if not init_md.is_file():
        print(
            f"WARNING: MCP repo at {repo.root} does not contain "
            f"{repo.content_prefix + '/' if repo.content_prefix else ''}INIT.md. "
            "This may not be a valid Engram memory repository.",
            file=sys.stderr,
        )

    # Identity check: does the repo origin match what's expected?
    expected_identity = os.environ.get("MEMORY_REPO_IDENTITY", "").strip()
    if not expected_identity:
        return

    # Check remote URL
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(repo.root),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        origin_url = result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        origin_url = ""

    repo_name = repo.root.name
    if expected_identity not in origin_url and expected_identity != repo_name:
        print(
            f"WARNING: MEMORY_REPO_IDENTITY='{expected_identity}' does not match "
            f"repo at {repo.root} (origin: {origin_url or '(none)'}, "
            f"dir: {repo_name}). The MCP server may be pointed at a stale or "
            f"wrong repository. Check MEMORY_REPO_ROOT in your MCP config.",
            file=sys.stderr,
        )


def create_mcp(
    repo_root: str | Path | None = None,
    delete_permission_hook: DeletePermissionHook | None = None,
    enable_raw_write_tools: bool | None = None,
) -> tuple[FastMCP, dict[str, object], Path, GitRepo]:
    """Create the FastMCP app, register tools, and expose their callables."""
    root = resolve_repo_root(repo_root)
    content_prefix = os.environ.get("MEMORY_CORE_PREFIX", "core")
    repo = GitRepo(root, content_prefix=content_prefix)
    _validate_repo_identity(repo)
    root = repo.root
    mcp = FastMCP("agent_memory_mcp")
    delete_permission_hook = (
        delete_permission_hook
        if delete_permission_hook is not None
        else _build_delete_permission_hook(root)
    )

    def get_repo() -> GitRepo:
        return repo

    def get_root() -> Path:
        return repo.content_root

    session_state = create_session_state(
        user_id=_resolve_user_id(),
        publication_base_branch=repo.current_branch_name(),
        publication_base_ref=repo.current_branch_ref(),
        publication_worktree_root=str(repo.root),
        publication_git_common_dir=str(repo.git_common_dir),
    )
    _maybe_enable_session_branching(repo, session_state)
    tools: dict[str, object] = {}
    tools.update(read_tools.register(mcp, get_repo, get_root, session_state=session_state))
    raw_write_tools_enabled = (
        enable_raw_write_tools
        if enable_raw_write_tools is not None
        else _env_flag_enabled("MEMORY_ENABLE_RAW_WRITE_TOOLS")
    )
    if raw_write_tools_enabled:
        tools.update(
            write_tools.register(
                mcp,
                get_repo,
                get_root,
                grant_delete_permission=delete_permission_hook,
            )
        )
    tools.update(semantic.register(mcp, get_repo, get_root, session_state=session_state))
    return mcp, tools, root, repo


_created: tuple | None = None


def _ensure_created() -> tuple:
    global _created
    if _created is None:
        _created = create_mcp()
        globals().update(_created[1])
    return _created


def __getattr__(name: str):
    """Defer create_mcp() until first attribute access."""
    _mcp, _tools, _root, _repo = _ensure_created()
    if name == "mcp":
        return _mcp
    if name == "TOOLS":
        return _tools
    if name == "REPO_ROOT":
        return _root
    if name == "GIT_REPO":
        return _repo
    if name in _tools:
        return _tools[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["GIT_REPO", "REPO_ROOT", "TOOLS", "create_mcp", "mcp"]  # noqa: F822


if __name__ == "__main__":
    _ensure_created()
    _created[0].run()  # type: ignore[index]
