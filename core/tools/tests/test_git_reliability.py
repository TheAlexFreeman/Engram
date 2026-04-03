"""Tests for git reliability: stale lock cleanup, retry logic, and health diagnostics."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from engram_mcp.agent_memory_mcp.errors import StagingError
from engram_mcp.agent_memory_mcp.git_repo import (
    GitRepo,
    _is_transient_failure,
)


class TestTransientFailureDetection(unittest.TestCase):
    def test_lock_errors_are_transient(self):
        err = StagingError("fatal: Unable to create '.git/index.lock'", stderr="index.lock")
        self.assertTrue(_is_transient_failure(err))

    def test_head_lock_is_transient(self):
        err = StagingError("cannot lock ref 'HEAD'", stderr="head.lock")
        self.assertTrue(_is_transient_failure(err))

    def test_another_process_is_transient(self):
        err = StagingError("Another git process seems to be running", stderr="another git process")
        self.assertTrue(_is_transient_failure(err))

    def test_logical_errors_are_not_transient(self):
        err = StagingError("nothing to commit, working tree clean", stderr="nothing to commit")
        self.assertFalse(_is_transient_failure(err))

    def test_empty_stderr_not_transient(self):
        err = StagingError("Unknown error")
        self.assertFalse(_is_transient_failure(err))


class TestStaleLockCleanup(unittest.TestCase):
    def _make_repo(self, tmpdir: Path) -> GitRepo:
        import subprocess

        subprocess.run(["git", "init", str(tmpdir)], capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        (tmpdir / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(tmpdir), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        return GitRepo(tmpdir)

    def test_stale_head_lock_cleaned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            lock = repo.git_dir / "HEAD.lock"
            lock.write_text("pid=999999\n", encoding="utf-8")
            old_time = time.time() - 60
            os.utime(str(lock), (old_time, old_time))
            self.assertTrue(repo._try_cleanup_stale_head_lock())
            self.assertFalse(lock.exists())

    def test_fresh_lock_not_cleaned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            lock = repo.git_dir / "HEAD.lock"
            lock.write_text("pid=999999\n", encoding="utf-8")
            self.assertFalse(repo._try_cleanup_stale_head_lock())
            self.assertTrue(lock.exists())

    def test_index_lock_cleaned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            lock = repo.git_dir / "index.lock"
            lock.write_text("pid=999999\n", encoding="utf-8")
            old_time = time.time() - 60
            os.utime(str(lock), (old_time, old_time))
            self.assertTrue(repo._try_cleanup_stale_index_lock())
            self.assertFalse(lock.exists())

    def test_cleanup_all_stale_locks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            for name in ["HEAD.lock", "index.lock"]:
                lock = repo.git_dir / name
                lock.write_text("pid=999999\n", encoding="utf-8")
                old_time = time.time() - 60
                os.utime(str(lock), (old_time, old_time))
            self.assertTrue(repo._try_cleanup_all_stale_locks())
            self.assertFalse((repo.git_dir / "HEAD.lock").exists())
            self.assertFalse((repo.git_dir / "index.lock").exists())

    def test_no_lock_files_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            self.assertFalse(repo._try_cleanup_all_stale_locks())


class TestHealthCheck(unittest.TestCase):
    def _make_repo(self, tmpdir: Path) -> GitRepo:
        import subprocess

        subprocess.run(["git", "init", str(tmpdir)], capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        (tmpdir / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(tmpdir), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        return GitRepo(tmpdir)

    def _make_empty_repo(self, tmpdir: Path) -> GitRepo:
        import subprocess

        subprocess.run(["git", "init", str(tmpdir)], capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(tmpdir),
            capture_output=True,
        )
        return GitRepo(tmpdir)

    def test_healthy_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            report = repo.health_check()
            self.assertTrue(report["repo_valid"])
            self.assertTrue(report["head_valid"])
            self.assertTrue(report["fs_writable"])
            self.assertEqual(report["warnings"], [])

    def test_stale_lock_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            lock = repo.git_dir / "HEAD.lock"
            lock.write_text("pid=999999\n", encoding="utf-8")
            old_time = time.time() - 60
            os.utime(str(lock), (old_time, old_time))
            report = repo.health_check()
            self.assertIn("HEAD.lock", report["locks"])
            self.assertTrue(report["locks"]["HEAD.lock"]["exists"])
            self.assertTrue(any("Stale" in w for w in report["warnings"]))

    def test_no_lock_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            report = repo.health_check()
            self.assertEqual(report["locks"], {})

    def test_report_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_repo(Path(tmpdir))
            report = repo.health_check()
            self.assertIn("root", report)
            self.assertIn("git_dir", report)
            self.assertIn("locks", report)
            self.assertIn("repo_valid", report)
            self.assertIn("head_valid", report)
            self.assertIn("fs_writable", report)
            self.assertIn("warnings", report)

    def test_empty_repo_marks_index_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = self._make_empty_repo(Path(tmpdir))
            report = repo.health_check()

            self.assertTrue(report["repo_valid"])
            self.assertFalse(report["head_valid"])
            self.assertFalse(report["index_valid"])
            self.assertTrue(any("HEAD is not valid" in warning for warning in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
