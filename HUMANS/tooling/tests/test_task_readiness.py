from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RESOLVER_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "resolve_task_readiness.py"

SPEC = importlib.util.spec_from_file_location("resolve_task_readiness", RESOLVER_PATH)
assert SPEC is not None
resolver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = resolver
SPEC.loader.exec_module(resolver)


def ok(stdout: str = "") -> dict[str, object]:
    return {"returncode": 0, "stdout": stdout, "stderr": ""}


def fail(stderr: str, returncode: int = 1) -> dict[str, object]:
    return {"returncode": returncode, "stdout": "", "stderr": stderr}


def make_command_runner(
    responses: dict[tuple[str, ...], dict[str, object] | str],
) -> Callable[[Path, list[str], int], object]:
    def runner(repo_root: Path, command: list[str], timeout: int) -> object:
        del repo_root, timeout
        key = tuple(command)
        if key not in responses:
            raise AssertionError(f"Unexpected command: {key!r}")
        response = responses[key]
        if response == "missing":
            return resolver.CommandProbeResult(command=command, returncode=127, missing=True)
        return resolver.CommandProbeResult(command=command, **response)

    return runner


def make_network_runner(
    responses: dict[tuple[str, int], object],
) -> Callable[[str, int, int], object]:
    def runner(host: str, port: int, timeout: int) -> object:
        del timeout
        key = (host, port)
        if key not in responses:
            raise AssertionError(f"Unexpected network probe: {key!r}")
        return responses[key]

    return runner


class TaskReadinessTests(unittest.TestCase):
    def test_seed_manifest_resolves_without_structure_errors(self) -> None:
        resolution = resolver.resolve_task_readiness(REPO_ROOT, include_runtime=False)
        self.assertEqual(resolution["errors"], [], "\n".join(resolution["errors"]))
        self.assertEqual(resolution["ui_feedback"]["status"], "manifest_only")

    def test_malformed_manifest_returns_structured_errors_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest_path = root / "HUMANS" / "tooling" / "agent-task-readiness.toml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                textwrap.dedent(
                    """\
                    version = 1
                    kind = "agent-task-readiness"
                    resolver_entrypoint = "missing.py"
                    manifest_role = "Task readiness contract"
                    task_detection = []
                    profiles = []
                    checks = []
                    cache_policy = []
                    execution = []
                    automation_integration = []
                    ui_feedback = []
                    """
                ),
                encoding="utf-8",
            )

            resolution = resolver.resolve_task_readiness(root, include_runtime=False)

            self.assertTrue(resolution["errors"])
            self.assertEqual(resolution["ui_feedback"]["status"], "manifest_only")
            self.assertEqual(resolution["profile"], "workspace_general")
            self.assertEqual(resolution["required_checks"], [])

    def test_task_text_infers_pull_request_profile(self) -> None:
        manifest = resolver.load_manifest(REPO_ROOT)
        profile, source = resolver.infer_profile(
            manifest,
            {"python": True, "node": False},
            task_text="Open a PR after the fixes land",
        )

        self.assertEqual(profile, "pull_request")
        self.assertEqual(source, "keyword_match")

    def test_validation_task_prefers_repo_hint_over_keyword_bias(self) -> None:
        manifest = resolver.load_manifest(REPO_ROOT)
        profile, source = resolver.infer_profile(
            manifest,
            {"python": False, "node": True},
            task_text="run tests",
        )

        self.assertEqual(profile, "node_validation")
        self.assertEqual(source, "repo_inferred")

    def test_terminal_plan_authoring_task_infers_terminal_plan_profile(self) -> None:
        manifest = resolver.load_manifest(REPO_ROOT)
        profile, source = resolver.infer_profile(
            manifest,
            {"python": True, "node": False},
            task_text="Use engram plan create with preview before applying the plan",
        )

        self.assertEqual(profile, "terminal_plan_authoring")
        self.assertEqual(source, "keyword_match")

    def test_terminal_approval_resolution_task_infers_terminal_plan_profile(self) -> None:
        manifest = resolver.load_manifest(REPO_ROOT)
        profile, source = resolver.infer_profile(
            manifest,
            {"python": True, "node": False},
            task_text="Use engram approval resolve to approve the pending phase",
        )

        self.assertEqual(profile, "terminal_plan_authoring")
        self.assertEqual(source, "keyword_match")

    def test_trace_inspection_defaults_to_workspace_general(self) -> None:
        manifest = resolver.load_manifest(REPO_ROOT)
        profile, source = resolver.infer_profile(
            manifest,
            {"python": True, "node": False},
            task_text="Inspect engram trace output for one session",
        )

        self.assertEqual(profile, "workspace_general")
        self.assertEqual(source, "default")

    def test_pull_request_profile_reports_ready_when_all_checks_pass(self) -> None:
        command_runner = make_command_runner(
            {
                ("git", "remote", "get-url", "origin"): ok("https://github.com/example/repo.git"),
                ("git", "branch", "--show-current"): ok("main"),
                ("git", "--version"): ok("git version 2.47.0"),
                ("git", "ls-remote", "--exit-code", "origin", "HEAD"): ok("ref"),
                (
                    "git",
                    "push",
                    "--dry-run",
                    "--porcelain",
                    "origin",
                    "HEAD:refs/heads/main",
                ): ok("Everything up-to-date"),
                ("gh", "auth", "status"): ok("github.com\n  Logged in"),
            }
        )
        network_runner = make_network_runner(
            {
                ("github.com", 443): resolver.NetworkProbeResult(
                    host="github.com", port=443, reachable=True
                )
            }
        )

        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="pull_request",
            command_runner=command_runner,
            network_runner=network_runner,
        )

        self.assertEqual(resolution["errors"], [], "\n".join(resolution["errors"]))
        self.assertEqual(resolution["ui_feedback"]["status"], "ready")
        self.assertEqual(resolution["blockers"], [])
        self.assertEqual(
            resolution["required_checks"],
            ["git_cli", "git_remote", "git_push_dry_run", "gh_auth", "remote_network"],
        )

    def test_missing_gh_becomes_publish_blocker(self) -> None:
        command_runner = make_command_runner(
            {
                ("git", "remote", "get-url", "origin"): ok("https://github.com/example/repo.git"),
                ("git", "branch", "--show-current"): ok("main"),
                ("git", "--version"): ok("git version 2.47.0"),
                ("git", "ls-remote", "--exit-code", "origin", "HEAD"): ok("ref"),
                (
                    "git",
                    "push",
                    "--dry-run",
                    "--porcelain",
                    "origin",
                    "HEAD:refs/heads/main",
                ): ok("Everything up-to-date"),
                ("gh", "auth", "status"): "missing",
            }
        )
        network_runner = make_network_runner(
            {
                ("github.com", 443): resolver.NetworkProbeResult(
                    host="github.com", port=443, reachable=True
                )
            }
        )

        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="pull_request",
            command_runner=command_runner,
            network_runner=network_runner,
        )

        self.assertEqual(resolution["ui_feedback"]["status"], "blocked")
        blocker = next(
            blocker for blocker in resolution["blockers"] if blocker["check_id"] == "gh_auth"
        )
        self.assertEqual(blocker["classification"], "missing")
        self.assertEqual(
            resolution["ui_feedback"]["fallback_message"],
            "Local work complete, publish blocked.",
        )

    def test_locked_gh_config_is_classified_as_config(self) -> None:
        command_runner = make_command_runner(
            {
                ("git", "remote", "get-url", "origin"): ok("https://github.com/example/repo.git"),
                ("git", "branch", "--show-current"): ok("main"),
                ("git", "--version"): ok("git version 2.47.0"),
                ("git", "ls-remote", "--exit-code", "origin", "HEAD"): ok("ref"),
                (
                    "git",
                    "push",
                    "--dry-run",
                    "--porcelain",
                    "origin",
                    "HEAD:refs/heads/main",
                ): ok("Everything up-to-date"),
                (
                    "gh",
                    "auth",
                    "status",
                ): fail("open C:\\Users\\alex\\.config\\gh\\config.yml: Access is denied."),
            }
        )
        network_runner = make_network_runner(
            {
                ("github.com", 443): resolver.NetworkProbeResult(
                    host="github.com", port=443, reachable=True
                )
            }
        )

        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="pull_request",
            command_runner=command_runner,
            network_runner=network_runner,
        )

        blocker = next(
            blocker for blocker in resolution["blockers"] if blocker["check_id"] == "gh_auth"
        )
        self.assertEqual(blocker["classification"], "config")

    def test_python_validation_blocks_when_runtime_is_missing(self) -> None:
        python_command = resolver.detect_python_command(REPO_ROOT)
        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="python_validation",
            command_runner=make_command_runner(
                {
                    ("git", "remote", "get-url", "origin"): fail("no remote"),
                    ("git", "branch", "--show-current"): ok(""),
                    (python_command, "--version"): "missing",
                    (python_command, "-m", "pytest", "--version"): "missing",
                    (python_command, "-m", "ruff", "--version"): "missing",
                }
            ),
        )

        self.assertEqual(resolution["ui_feedback"]["status"], "blocked")
        first_check = resolution["check_results"][0]
        self.assertEqual(first_check["id"], "python_runtime")
        self.assertEqual(first_check["classification"], "missing")
        self.assertEqual(
            resolution["ui_feedback"]["fallback_message"],
            "Validation skipped because the Python runtime or validation tools are missing.",
        )

    def test_terminal_plan_authoring_profile_reports_ready_when_python_and_git_exist(self) -> None:
        python_command = resolver.detect_python_command(REPO_ROOT)
        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="terminal_plan_authoring",
            command_runner=make_command_runner(
                {
                    ("git", "remote", "get-url", "origin"): ok(
                        "https://github.com/example/repo.git"
                    ),
                    ("git", "branch", "--show-current"): ok("alex"),
                    (python_command, "--version"): ok("Python 3.14.2"),
                    ("git", "--version"): ok("git version 2.47.0"),
                }
            ),
        )

        self.assertEqual(resolution["errors"], [], "\n".join(resolution["errors"]))
        self.assertEqual(resolution["profile"], "terminal_plan_authoring")
        self.assertEqual(resolution["ui_feedback"]["status"], "ready")
        self.assertEqual(resolution["required_checks"], ["python_runtime", "git_cli"])
        self.assertEqual(resolution["blockers"], [])

    def test_reachable_remote_but_unauthenticated_push_is_classified_as_auth(self) -> None:
        command_runner = make_command_runner(
            {
                ("git", "remote", "get-url", "origin"): ok("https://github.com/example/repo.git"),
                ("git", "branch", "--show-current"): ok("main"),
                ("git", "--version"): ok("git version 2.47.0"),
                ("git", "ls-remote", "--exit-code", "origin", "HEAD"): ok("ref"),
                (
                    "git",
                    "push",
                    "--dry-run",
                    "--porcelain",
                    "origin",
                    "HEAD:refs/heads/main",
                ): fail("remote: Permission to example/repo denied to alex."),
            }
        )
        network_runner = make_network_runner(
            {
                ("github.com", 443): resolver.NetworkProbeResult(
                    host="github.com", port=443, reachable=True
                )
            }
        )

        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="publish_branch",
            command_runner=command_runner,
            network_runner=network_runner,
        )

        blocker = next(
            blocker
            for blocker in resolution["blockers"]
            if blocker["check_id"] == "git_push_dry_run"
        )
        self.assertEqual(blocker["classification"], "auth")

    def test_unchanged_publish_blocker_requests_skip_of_repeated_publish_attempts(self) -> None:
        command_runner = make_command_runner(
            {
                ("git", "remote", "get-url", "origin"): ok("https://github.com/example/repo.git"),
                ("git", "branch", "--show-current"): ok("main"),
                ("git", "--version"): ok("git version 2.47.0"),
                ("git", "ls-remote", "--exit-code", "origin", "HEAD"): ok("ref"),
                (
                    "git",
                    "push",
                    "--dry-run",
                    "--porcelain",
                    "origin",
                    "HEAD:refs/heads/main",
                ): fail("remote: Permission to example/repo denied to alex."),
            }
        )
        network_runner = make_network_runner(
            {
                ("github.com", 443): resolver.NetworkProbeResult(
                    host="github.com", port=443, reachable=True
                )
            }
        )
        previous_blockers = [
            {"check_id": "git_push_dry_run", "classification": "auth", "summary": "old"}
        ]

        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="publish_branch",
            previous_blockers=previous_blockers,
            command_runner=command_runner,
            network_runner=network_runner,
        )

        blocker = next(
            blocker
            for blocker in resolution["blockers"]
            if blocker["check_id"] == "git_push_dry_run"
        )
        self.assertTrue(blocker["unchanged_since_previous"])
        self.assertTrue(resolution["automation_integration"]["skip_unchanged_publish_attempts_now"])

    def test_resolved_previous_blocker_surfaces_attention(self) -> None:
        command_runner = make_command_runner(
            {
                ("git", "remote", "get-url", "origin"): ok("https://github.com/example/repo.git"),
                ("git", "branch", "--show-current"): ok("main"),
                ("git", "--version"): ok("git version 2.47.0"),
                ("git", "ls-remote", "--exit-code", "origin", "HEAD"): ok("ref"),
                (
                    "git",
                    "push",
                    "--dry-run",
                    "--porcelain",
                    "origin",
                    "HEAD:refs/heads/main",
                ): ok("Everything up-to-date"),
                ("gh", "auth", "status"): ok("github.com\n  Logged in"),
            }
        )
        network_runner = make_network_runner(
            {
                ("github.com", 443): resolver.NetworkProbeResult(
                    host="github.com", port=443, reachable=True
                )
            }
        )
        previous_blockers = [{"check_id": "gh_auth", "classification": "auth", "summary": "old"}]

        resolution = resolver.resolve_task_readiness(
            REPO_ROOT,
            requested_profile="pull_request",
            previous_blockers=previous_blockers,
            command_runner=command_runner,
            network_runner=network_runner,
        )

        self.assertEqual(resolution["ui_feedback"]["status"], "attention")
        self.assertEqual(len(resolution["resolved_previous_blockers"]), 1)
        self.assertTrue(resolution["warnings"])


if __name__ == "__main__":
    unittest.main()
