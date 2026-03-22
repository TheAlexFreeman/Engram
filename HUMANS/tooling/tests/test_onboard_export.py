from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "onboard-export.sh"


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


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_repo(root: Path) -> None:
    write(root / "README.md", "# README\n")
    write(root / "meta" / "placeholder.md", "# Meta\n")
    write(root / "core" / "memory" / "users" / "SUMMARY.md", "# Identity Summary\n")
    write(
        root / "core" / "memory" / "activity" / "SUMMARY.md",
        textwrap.dedent(
            """\
            # Chats Summary

            ## Overall history

            *No conversations yet.* This section will develop into a high-level narrative.
            """
        ),
    )


def isolated_env(temp_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(temp_home)
    env["USERPROFILE"] = str(temp_home)
    env["XDG_CONFIG_HOME"] = str(temp_home)
    return env


class OnboardExportTests(unittest.TestCase):
    def run_script(
        self,
        root: Path,
        export_content: str,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
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

        export_path = root / "export.md"
        export_path.write_text(export_content, encoding="utf-8")

        return subprocess.run(
            [bash, str(SCRIPT_PATH), *args, str(export_path)],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_canonical_export_dry_run_preserves_session_path_date_and_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)
            export = textwrap.dedent(
                """\
                ---
                session_id: core/memory/activity/2026/03/12/chat-001
                session_date: 2026-03-12
                ---

                ## Identity Profile

                - **Primary role:** Engineer. [observed]

                ## Session Transcript

                User: Hello
                Agent: Hi there

                ## Session Summary

                First session onboarding summary.

                ## Session Reflection

                **Memory retrieved:** [onboarding.md — helpfulness 0.8]
                """
            )

            result = self.run_script(root, export, "--dry-run")
            stdout = result.stdout

            self.assertIn("--- core/memory/activity/2026/03/12/chat-001/transcript.md ---", stdout)
            self.assertIn("--- core/memory/activity/2026/03/12/chat-001/SUMMARY.md ---", stdout)
            self.assertIn("User profile created via onboarding export on 2026-03-12.", stdout)
            self.assertIn("User: Hello", stdout)
            self.assertIn("Agent: Hi there", stdout)

    def test_canonical_export_writes_profile_transcript_summary_and_reflection(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)
            export = textwrap.dedent(
                """\
                ---
                session_id: core/memory/activity/2026/03/12/chat-001
                session_date: 2026-03-12
                ---

                ## Identity Profile

                - **Primary role:** Engineer. [observed]
                - **Tone:** Direct. [observed]

                ## Session Transcript

                User: Hello
                Agent: Hi there

                ## Session Summary

                First session onboarding summary.

                ## Session Reflection

                **Memory retrieved:** [onboarding.md — helpfulness 0.8]
                **Outcome quality:** Good.
                """
            )

            self.run_script(root, export)

            profile = (root / "core" / "memory" / "users" / "profile.md").read_text(
                encoding="utf-8"
            )
            transcript = (
                root
                / "core"
                / "memory"
                / "activity"
                / "2026"
                / "03"
                / "12"
                / "chat-001"
                / "transcript.md"
            ).read_text(encoding="utf-8")
            summary = (
                root
                / "core"
                / "memory"
                / "activity"
                / "2026"
                / "03"
                / "12"
                / "chat-001"
                / "SUMMARY.md"
            ).read_text(encoding="utf-8")
            reflection = (
                root
                / "core"
                / "memory"
                / "activity"
                / "2026"
                / "03"
                / "12"
                / "chat-001"
                / "reflection.md"
            ).read_text(encoding="utf-8")
            chats_summary = (root / "core" / "memory" / "activity" / "SUMMARY.md").read_text(
                encoding="utf-8"
            )

            self.assertIn("origin_session: core/memory/activity/2026/03/12/chat-001", profile)
            self.assertIn("created: 2026-03-12", profile)
            self.assertEqual(transcript.strip(), "User: Hello\nAgent: Hi there")
            self.assertTrue(summary.startswith("# Session Summary — Onboarding"))
            self.assertIn("First session onboarding summary.", summary)
            self.assertTrue(reflection.startswith("## Session reflection"))
            self.assertIn("**Outcome quality:** Good.", reflection)
            self.assertIn("First recorded conversation on 2026-03-12", chats_summary)

    def test_legacy_export_warns_and_falls_back_to_today_chat_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)
            export = textwrap.dedent(
                """\
                ## Identity Profile

                - **Primary role:** Engineer. [observed]

                ## Session Summary

                Legacy onboarding summary.

                ## Session Reflection

                **Outcome quality:** Good.
                """
            )

            result = self.run_script(root, export, "--dry-run")
            stdout = result.stdout
            today = date.today()
            expected_chat_dir = f"core/memory/activity/{today:%Y/%m/%d}/chat-001"

            self.assertIn("[warn] Legacy onboarding export detected", stdout)
            self.assertIn(expected_chat_dir, stdout)
            self.assertNotIn("transcript.md", stdout)

    def test_auto_commit_excludes_unrelated_pre_staged_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)
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

            write(root / "notes.txt", "keep staged\n")
            subprocess.run(
                ["git", "add", "notes.txt"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            export = textwrap.dedent(
                """\
                ---
                session_id: core/memory/activity/2026/03/12/chat-001
                session_date: 2026-03-12
                ---

                ## Identity Profile

                - **Primary role:** Engineer. [observed]

                ## Session Transcript

                User: Hello
                Agent: Hi there

                ## Session Summary

                First session onboarding summary.

                ## Session Reflection

                **Outcome quality:** Good.
                """
            )
            export_path = root / "export.md"
            export_path.write_text(export, encoding="utf-8")

            subprocess.run(
                [bash, str(SCRIPT_PATH), str(export_path)],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            head_files = subprocess.run(
                ["git", "show", "--name-only", "--pretty=", "HEAD"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            staged_files = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()

            self.assertIn("core/memory/users/profile.md", head_files)
            self.assertIn("core/memory/users/SUMMARY.md", head_files)
            self.assertIn("core/memory/activity/2026/03/12/chat-001/SUMMARY.md", head_files)
            self.assertNotIn("notes.txt", head_files)
            self.assertIn("notes.txt", staged_files)


if __name__ == "__main__":
    unittest.main()
