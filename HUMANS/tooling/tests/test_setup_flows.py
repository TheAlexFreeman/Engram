from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "validate_memory_repo.py"

SPEC = importlib.util.spec_from_file_location("validate_memory_repo", VALIDATOR_PATH)
assert SPEC is not None
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules.setdefault("validate_memory_repo", validator)
SPEC.loader.exec_module(validator)


def find_bash() -> str | None:
    candidates = [
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    bash = shutil.which("bash")
    if bash and "system32\\bash.exe" not in bash.lower():
        return bash
    return None


def isolated_env(temp_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(temp_home)
    env["USERPROFILE"] = str(temp_home)
    env["XDG_CONFIG_HOME"] = str(temp_home)
    return env


def build_setup_repo(root: Path) -> None:
    for filename in (
        "README.md",
        "CHANGELOG.md",
        "agent-bootstrap.toml",
        "pyproject.toml",
        "setup.sh",
        "setup.html",
        "AGENTS.md",
        "CLAUDE.md",
        ".cursorrules",
        ".gitattributes",
        ".gitignore",
    ):
        shutil.copy2(REPO_ROOT / filename, root / filename)

    for dirname in (
        ".codex",
        ".github",
        ".vscode",
        "core",
        "HUMANS",
    ):
        shutil.copytree(
            REPO_ROOT / dirname,
            root / dirname,
            ignore=shutil.ignore_patterns("__pycache__"),
        )


def read_initial_commit_manifest(root: Path) -> list[str]:
    manifest = root / "HUMANS" / "setup" / "initial-commit-paths.txt"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def extract_toml_string(text: str, key: str) -> str:
    match = re.search(rf'^{re.escape(key)} = "(?P<value>.*)"$', text, flags=re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing TOML key: {key}")
    return match.group("value").replace("\\\\", "\\")


def normalize_test_path(value: str | Path) -> str:
    return os.path.normcase(os.path.realpath(str(value)))


class SetupFlowTests(unittest.TestCase):
    def run_setup(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        bash = find_bash()
        if bash is None:
            self.skipTest("bash is not available in this environment")

        env = isolated_env(root / ".home")
        return subprocess.run(
            [bash, str(root / "setup.sh"), *args],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def run_init_worktree(
        self,
        seed_root: Path,
        host_root: Path,
        *args: str,
        env_updates: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        bash = find_bash()
        if bash is None:
            self.skipTest("bash is not available in this environment")

        env = isolated_env(host_root / ".home")
        if env_updates:
            env.update(env_updates)
        return subprocess.run(
            [bash, str(seed_root / "HUMANS" / "setup" / "init-worktree.sh"), *args],
            cwd=host_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def init_host_repo(self, root: Path) -> None:
        subprocess.run(
            ["git", "init", "--initial-branch=core"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("print('host repo')\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "."],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "host init"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_setup_sh_personalization_flags_write_browser_parity_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_setup_repo(root)

            self.run_setup(
                root,
                "--non-interactive",
                "--profile",
                "software-developer",
                "--platform",
                "generic",
                "--user-name",
                "Alex",
                "--user-context",
                "Writing code and debugging",
            )

            summary = (root / "core" / "memory" / "users" / "SUMMARY.md").read_text(
                encoding="utf-8"
            )
            profile = (root / "core" / "memory" / "users" / "profile.md").read_text(
                encoding="utf-8"
            )

            self.assertIn("**User:** Alex", summary)
            self.assertIn("**Uses AI for:** Writing code and debugging", summary)
            self.assertIn("Template-based profile — pending onboarding confirmation.", summary)
            self.assertNotIn("last_verified:", profile)
            self.assertIn("created:", profile)

    def test_setup_initializes_new_repo_on_core_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_setup_repo(root)

            self.run_setup(
                root,
                "--non-interactive",
                "--profile",
                "software-developer",
                "--platform",
                "generic",
            )

            head_result = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            head_branch = head_result.stdout.strip()

            self.assertEqual("core", head_branch)

    def test_setup_rewrites_codex_config_for_current_clone(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_setup_repo(root)

            self.run_setup(
                root,
                "--non-interactive",
                "--profile",
                "software-developer",
                "--platform",
                "codex",
            )

            config_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertEqual(
                normalize_test_path(extract_toml_string(config_text, "cwd")),
                normalize_test_path(root),
            )
            args_match = re.search(r'^args = \["(?P<path>.*)"\]$', config_text, flags=re.MULTILINE)
            self.assertIsNotNone(args_match)
            self.assertEqual(
                normalize_test_path(args_match.group("path")),
                normalize_test_path(root / "core" / "tools" / "memory_mcp.py"),
            )
            self.assertNotIn(str(REPO_ROOT).replace("\\", "\\\\"), config_text)

    def test_setup_codex_portable_writes_portable_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_setup_repo(root)

            self.run_setup(
                root,
                "--non-interactive",
                "--profile",
                "software-developer",
                "--platform",
                "codex",
                "--codex-portable",
            )

            config_text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn('command = "python"', config_text)
            self.assertIn('args = ["core/tools/memory_mcp.py"]', config_text)
            self.assertIn('cwd = "."', config_text)
            self.assertIn("env_vars = [", config_text)
            self.assertNotIn("MEMORY_REPO_ROOT = ", config_text)

    def test_init_worktree_creates_orphan_branch_with_committed_memory_worktree(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as seed_tempdir,
            tempfile.TemporaryDirectory() as host_tempdir,
        ):
            seed_root = Path(seed_tempdir)
            host_root = Path(host_tempdir)
            build_setup_repo(seed_root)
            self.init_host_repo(host_root)

            self.run_init_worktree(
                seed_root,
                host_root,
                "--non-interactive",
                "--profile",
                "software-developer",
                "--platform",
                "codex",
            )

            merge_base = subprocess.run(
                ["git", "merge-base", "core", "agent-memory"],
                cwd=host_root,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, merge_base.returncode)

            worktree_root = host_root / ".agent-memory"
            self.assertTrue(worktree_root.is_dir())

            branch_name = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"],
                cwd=worktree_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual("agent-memory", branch_name)

            profile_text = (worktree_root / "core" / "memory" / "users" / "profile.md").read_text(
                encoding="utf-8"
            )
            projects_summary = (
                worktree_root / "core" / "memory" / "working" / "projects" / "SUMMARY.md"
            ).read_text(encoding="utf-8")
            bootstrap_text = (worktree_root / "agent-bootstrap.toml").read_text(encoding="utf-8")
            self.assertIn("**codebase_root:**", profile_text)
            self.assertIn("**project_name:**", profile_text)
            self.assertIn(host_root.name, profile_text)
            self.assertEqual(
                normalize_test_path(extract_toml_string(bootstrap_text, "host_repo_root")),
                normalize_test_path(host_root),
            )
            self.assertIn("codebase-survey", projects_summary)
            self.assertTrue((worktree_root / ".ignore").is_file())
            self.assertTrue((worktree_root / ".editorconfig").is_file())
            self.assertTrue(
                (
                    worktree_root
                    / "core"
                    / "memory"
                    / "working"
                    / "projects"
                    / "codebase-survey"
                    / "SUMMARY.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    worktree_root
                    / "core"
                    / "memory"
                    / "working"
                    / "projects"
                    / "codebase-survey"
                    / "questions.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    worktree_root
                    / "core"
                    / "memory"
                    / "working"
                    / "projects"
                    / "codebase-survey"
                    / "plans"
                    / "survey-plan.yaml"
                ).is_file()
            )
            self.assertTrue(
                (
                    worktree_root / "core" / "memory" / "knowledge" / "codebase" / "architecture.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    worktree_root / "core" / "memory" / "knowledge" / "codebase" / "data-model.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    worktree_root / "core" / "memory" / "knowledge" / "codebase" / "operations.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    worktree_root / "core" / "memory" / "knowledge" / "codebase" / "decisions.md"
                ).is_file()
            )
            self.assertTrue(
                (
                    worktree_root / "core" / "memory" / "skills" / "codebase-survey" / "SKILL.md"
                ).is_file()
            )

            codex_config = (host_root / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertEqual(
                extract_toml_string(codex_config, "cwd"),
                ".agent-memory",
            )
            self.assertEqual(
                extract_toml_string(codex_config, "MEMORY_REPO_ROOT"),
                ".agent-memory",
            )
            self.assertEqual(
                extract_toml_string(codex_config, "HOST_REPO_ROOT"),
                ".",
            )

            host_agents = (host_root / "AGENTS.md").read_text(encoding="utf-8")
            host_claude = (host_root / "CLAUDE.md").read_text(encoding="utf-8")
            host_cursor = (host_root / ".cursorrules").read_text(encoding="utf-8")
            worktree_agents = (worktree_root / "AGENTS.md").read_text(encoding="utf-8")

            self.assertIn(".agent-memory/core/INIT.md", host_agents)
            self.assertIn(".codex/config.toml", host_agents)
            self.assertIn("agent-memory", host_agents)
            self.assertIn(".agent-memory/core/INIT.md", host_claude)
            self.assertIn(".agent-memory/core/INIT.md", host_cursor)
            self.assertNotEqual(worktree_agents, host_agents)

    def test_init_worktree_end_to_end_validation_passes(self) -> None:
        with (
            tempfile.TemporaryDirectory() as seed_tempdir,
            tempfile.TemporaryDirectory() as host_tempdir,
        ):
            seed_root = Path(seed_tempdir)
            host_root = Path(host_tempdir)
            build_setup_repo(seed_root)
            self.init_host_repo(host_root)

            self.run_init_worktree(
                seed_root,
                host_root,
                "--non-interactive",
                "--profile",
                "software-developer",
                "--platform",
                "codex",
            )

            worktree_root = host_root / ".agent-memory"
            result = validator.validate_repo(worktree_root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_init_worktree_dry_run_prints_commands_without_mutating_repo(self) -> None:
        with (
            tempfile.TemporaryDirectory() as seed_tempdir,
            tempfile.TemporaryDirectory() as host_tempdir,
        ):
            seed_root = Path(seed_tempdir)
            host_root = Path(host_tempdir)
            build_setup_repo(seed_root)
            self.init_host_repo(host_root)

            result = self.run_init_worktree(
                seed_root,
                host_root,
                "--dry-run",
                "--platform",
                "codex",
            )

            self.assertIn("git worktree add --detach", result.stdout)
            self.assertIn("git -C", result.stdout)
            self.assertIn("git worktree add", result.stdout)
            self.assertFalse((host_root / ".agent-memory").exists())

            branches = subprocess.run(
                ["git", "branch", "--list", "agent-memory"],
                cwd=host_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual("", branches)

    def test_init_worktree_prefers_engram_mcp_cli_when_available(self) -> None:
        with (
            tempfile.TemporaryDirectory() as seed_tempdir,
            tempfile.TemporaryDirectory() as host_tempdir,
        ):
            seed_root = Path(seed_tempdir)
            host_root = Path(host_tempdir)
            build_setup_repo(seed_root)
            self.init_host_repo(host_root)

            fake_bin = host_root / "fake-bin"
            fake_bin.mkdir()
            launcher = fake_bin / "engram-mcp"
            launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            launcher.chmod(0o755)

            result = self.run_init_worktree(
                seed_root,
                host_root,
                "--non-interactive",
                "--platform",
                "generic",
                env_updates={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertIn("mcp-config-example.json", result.stdout)

            config_text = (host_root / "mcp-config-example.json").read_text(encoding="utf-8")
            self.assertIn('"command": "engram-mcp"', config_text)
            self.assertIn('"args": []', config_text)
            self.assertIn('"cwd": ".agent-memory"', config_text)

    def test_shell_and_browser_setup_sources_keep_profile_summary_copy_aligned(
        self,
    ) -> None:
        shell_text = (REPO_ROOT / "HUMANS" / "setup" / "setup.sh").read_text(encoding="utf-8")
        # The browser setup is composed of setup.html + setup-utils.js (loaded via <script src>).
        # Profile summary copy was extracted to setup-utils.js; check both files together.
        html_text = (REPO_ROOT / "HUMANS" / "views" / "setup.html").read_text(encoding="utf-8")
        utils_text = (REPO_ROOT / "HUMANS" / "views" / "setup-utils.js").read_text(encoding="utf-8")
        browser_text = html_text + utils_text

        required_phrases = (
            "Template-based profile",
            "pending onboarding confirmation.",
            "A starter profile has been installed from a template. During the first",
            "session, the onboarding skill will walk through the template traits and",
            "confirm, adjust, or remove them.",
            "See [profile.md](profile.md) for the current profile.",
            "**User:**",
            "**Uses AI for:**",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, shell_text)
            self.assertIn(phrase, browser_text)

    def test_browser_setup_uses_local_date_components_for_created_frontmatter(
        self,
    ) -> None:
        # The browser setup is composed of setup.html + setup-utils.js (loaded via <script src>).
        # JS logic including date helpers was extracted to setup-utils.js; check both.
        html_text = (REPO_ROOT / "HUMANS" / "views" / "setup.html").read_text(encoding="utf-8")
        utils_text = (REPO_ROOT / "HUMANS" / "views" / "setup-utils.js").read_text(encoding="utf-8")
        browser_text = html_text + utils_text

        self.assertNotIn("toISOString().slice(0, 10)", browser_text)
        self.assertIn("getFullYear()", browser_text)
        self.assertIn("getMonth() + 1", browser_text)
        self.assertIn("getDate()", browser_text)

    def test_browser_setup_collects_codex_paths_and_generates_config(self) -> None:
        # The browser setup is composed of setup.html + setup-utils.js (loaded via <script src>).
        # JS logic for codex config was extracted to setup-utils.js; check both.
        html_text = (REPO_ROOT / "HUMANS" / "views" / "setup.html").read_text(encoding="utf-8")
        utils_text = (REPO_ROOT / "HUMANS" / "views" / "setup-utils.js").read_text(encoding="utf-8")
        browser_text = html_text + utils_text

        self.assertIn('id="codex-repo-path"', browser_text)
        self.assertIn('id="codex-python-path"', browser_text)
        self.assertIn('id="codex-path-error"', browser_text)
        self.assertIn("function makeCodexConfig", browser_text)
        self.assertIn("makeCodexConfigPortable", browser_text)
        self.assertIn("function isAbsolutePath", browser_text)
        self.assertIn("function setCodexPathError", browser_text)
        self.assertIn("'.codex/config.toml'", browser_text)
        self.assertNotIn("C:\\\\path\\\\to\\\\your\\\\repo", browser_text)
        self.assertNotIn("C:\\\\path\\\\to\\\\python.exe", browser_text)

    def test_initial_commit_manifest_matches_tracked_repo_paths(self) -> None:
        manifest_paths = set(read_initial_commit_manifest(REPO_ROOT))
        tracked_paths = set(
            subprocess.run(
                ["git", "ls-files"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
        )

        expected_seed_paths = tracked_paths | {"HUMANS/setup/initial-commit-paths.txt"}

        self.assertTrue(
            expected_seed_paths.issubset(manifest_paths),
            "initial commit manifest is missing tracked seed paths",
        )

        for relative_path in manifest_paths:
            self.assertTrue(
                (REPO_ROOT / relative_path).exists(),
                f"manifest path does not exist: {relative_path}",
            )

    def test_setup_initial_commit_excludes_unrelated_local_files_and_generated_prompts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_setup_repo(root)
            bash = find_bash()
            if bash is None:
                self.skipTest("bash is not available in this environment")

            env = isolated_env(root / ".home")
            subprocess.run(
                ["git", "init"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            (root / "notes.txt").write_text("leave me out\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "notes.txt"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            subprocess.run(
                [
                    bash,
                    str(root / "setup.sh"),
                    "--non-interactive",
                    "--profile",
                    "software-developer",
                    "--platform",
                    "generic",
                ],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            head_files = set(
                subprocess.run(
                    ["git", "show", "--name-only", "--pretty=", "HEAD"],
                    cwd=root,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.splitlines()
            )
            self.assertIn("HUMANS/setup/initial-commit-paths.txt", head_files)
            self.assertIn("README.md", head_files)
            self.assertIn("core/memory/working/projects/SUMMARY.md", head_files)
            self.assertNotIn("notes.txt", head_files)
            self.assertNotIn("system-prompt.txt", head_files)

    def test_setup_missing_git_identity_stages_only_allowlisted_paths_and_prints_safe_command(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_setup_repo(root)
            bash = find_bash()
            if bash is None:
                self.skipTest("bash is not available in this environment")

            env = isolated_env(root / ".home")
            subprocess.run(
                ["git", "init"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            (root / "notes.txt").write_text("leave me untracked\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "notes.txt"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            result = subprocess.run(
                [
                    bash,
                    str(root / "setup.sh"),
                    "--non-interactive",
                    "--profile",
                    "software-developer",
                    "--platform",
                    "generic",
                ],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn(
                "git add --pathspec-from-file=HUMANS/setup/initial-commit-paths.txt --",
                result.stdout,
            )
            self.assertIn(
                "git commit -m '[system] Initialize Engram' -m 'Created from Engram template on",
                result.stdout,
            )
            self.assertIn("git status --short", result.stdout)
            self.assertNotIn("git add -A", result.stdout)

            staged_files = set(
                subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    cwd=root,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.splitlines()
            )

            self.assertIn("README.md", staged_files)
            self.assertIn("HUMANS/setup/initial-commit-paths.txt", staged_files)
            self.assertIn("core/memory/working/projects/SUMMARY.md", staged_files)
            self.assertNotIn("notes.txt", staged_files)
            self.assertNotIn("system-prompt.txt", staged_files)

    def test_generated_prompt_copy_mentions_semantic_default_and_deferred_file_blind_writes(
        self,
    ) -> None:
        shell_text = (REPO_ROOT / "HUMANS" / "setup" / "setup.sh").read_text(encoding="utf-8")
        browser_text = (REPO_ROOT / "HUMANS" / "views" / "setup.html").read_text(encoding="utf-8")

        required_phrases = (
            "default repo-local runtime is semantic/governed MCP",
            "raw fallback is opt-in via `MEMORY_ENABLE_RAW_WRITE_TOOLS=1`",
            "do not claim that ACCESS logging or governed writes happened; defer them",
            "Identity changes are proposed changes",
            "Plans may guide only their own scoped work",
            "Append-only `CHANGELOG.md` updates are allowed without protected-file approval",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, shell_text)
            self.assertIn(phrase, browser_text)


if __name__ == "__main__":
    unittest.main()
