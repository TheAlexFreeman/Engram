from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from harness.tools.fs import WorkspaceScope
from harness.tools.git import Git, GitCommit, GitDiff, GitLog, GitStatus


def _git(repo: Path, *args: str) -> None:
    git = shutil.which("git")
    assert git is not None, "git must be installed to run these tests"
    subprocess.run(
        [git, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")
    _git(tmp_path, "add", "hello.txt")
    _git(tmp_path, "commit", "-q", "-m", "seed commit")
    return tmp_path


@pytest.fixture()
def scope(repo: Path) -> WorkspaceScope:
    return WorkspaceScope(root=repo)


def test_git_status_clean(scope: WorkspaceScope) -> None:
    out = GitStatus(scope).run({})
    assert "exit code: 0" in out
    assert "## main" in out


def test_git_status_dirty(scope: WorkspaceScope, repo: Path) -> None:
    (repo / "hello.txt").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")
    out = GitStatus(scope).run({})
    assert "exit code: 0" in out
    assert " M hello.txt" in out
    assert "?? new.txt" in out


def test_git_diff_unstaged_and_staged(scope: WorkspaceScope, repo: Path) -> None:
    (repo / "hello.txt").write_text("changed\n", encoding="utf-8")

    unstaged = GitDiff(scope).run({})
    assert "exit code: 0" in unstaged
    assert "-hello" in unstaged and "+changed" in unstaged

    staged_empty = GitDiff(scope).run({"staged": True})
    assert "exit code: 0" in staged_empty
    assert "-hello" not in staged_empty

    _git(repo, "add", "hello.txt")
    staged = GitDiff(scope).run({"staged": True})
    assert "+changed" in staged


def test_git_diff_rev_range(scope: WorkspaceScope, repo: Path) -> None:
    (repo / "hello.txt").write_text("v2\n", encoding="utf-8")
    _git(repo, "commit", "-aq", "-m", "second")
    out = GitDiff(scope).run({"rev_range": "HEAD~1..HEAD"})
    assert "exit code: 0" in out
    assert "+v2" in out


def test_git_diff_rev_range_rejects_bad_tokens(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="forbidden token"):
        GitDiff(scope).run({"rev_range": "HEAD; rm -rf /"})


def test_git_diff_stat(scope: WorkspaceScope, repo: Path) -> None:
    (repo / "hello.txt").write_text("changed\n", encoding="utf-8")
    out = GitDiff(scope).run({"stat": True})
    assert "hello.txt" in out
    assert "1 file changed" in out or "insertion" in out or "deletion" in out


def test_git_log_default_oneline(scope: WorkspaceScope) -> None:
    out = GitLog(scope).run({})
    assert "exit code: 0" in out
    assert "seed commit" in out


def test_git_log_max_count(scope: WorkspaceScope, repo: Path) -> None:
    (repo / "hello.txt").write_text("v2\n", encoding="utf-8")
    _git(repo, "commit", "-aq", "-m", "second")
    out = GitLog(scope).run({"max_count": 1})
    assert "second" in out
    assert "seed commit" not in out


def test_git_log_full_format(scope: WorkspaceScope) -> None:
    out = GitLog(scope).run({"oneline": False})
    assert "Author:" in out
    assert "Date:" in out


def test_git_commit_happy_path(scope: WorkspaceScope, repo: Path) -> None:
    (repo / "new.txt").write_text("n\n", encoding="utf-8")
    _git(repo, "add", "new.txt")
    out = GitCommit(scope).run({"message": "add new"})
    assert "exit code: 0" in out
    log = GitLog(scope).run({"max_count": 1})
    assert "add new" in log


def test_git_commit_rejects_empty_message(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        GitCommit(scope).run({"message": "   "})


def test_git_commit_all_flag(scope: WorkspaceScope, repo: Path) -> None:
    (repo / "hello.txt").write_text("modified\n", encoding="utf-8")
    out = GitCommit(scope).run({"message": "modify tracked", "all": True})
    assert "exit code: 0" in out
    log = GitLog(scope).run({"max_count": 1})
    assert "modify tracked" in log


def test_git_commit_amend(scope: WorkspaceScope, repo: Path) -> None:
    out = GitCommit(scope).run({"message": "seed commit (amended)", "amend": True, "allow_empty": True})
    assert "exit code: 0" in out
    log = GitLog(scope).run({"max_count": 1})
    assert "seed commit (amended)" in log


def test_generic_git_show(scope: WorkspaceScope) -> None:
    out = Git(scope).run({"subcommand": "show", "args": ["--stat", "HEAD"]})
    assert "exit code: 0" in out
    assert "seed commit" in out


def test_generic_git_rejects_unknown_subcommand(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        Git(scope).run({"subcommand": "push"})


def test_generic_git_rejects_force_flag(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        Git(scope).run({"subcommand": "branch", "args": ["--force", "main"]})


def test_generic_git_rejects_dash_f(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        Git(scope).run({"subcommand": "checkout", "args": ["-f", "main"]})


def test_generic_git_rejects_force_with_lease_eq(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        Git(scope).run({"subcommand": "branch", "args": ["--force-with-lease=main"]})


def test_generic_git_rejects_injection_tokens(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="forbidden token"):
        Git(scope).run({"subcommand": "show", "args": ["$(whoami)"]})


def test_generic_git_requires_subcommand(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="subcommand"):
        Git(scope).run({"subcommand": ""})


def test_generic_git_args_must_be_list_of_strings(scope: WorkspaceScope) -> None:
    with pytest.raises(ValueError, match="args must be an array"):
        Git(scope).run({"subcommand": "status", "args": "not-a-list"})
    with pytest.raises(ValueError, match=r"args\[0\]"):
        Git(scope).run({"subcommand": "status", "args": [123]})
