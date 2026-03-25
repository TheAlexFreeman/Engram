from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RESOLVER_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "resolve_bootstrap_manifest.py"
SPEC = importlib.util.spec_from_file_location("resolve_bootstrap_manifest", RESOLVER_PATH)
assert SPEC is not None
resolver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = resolver
SPEC.loader.exec_module(resolver)

BOOTSTRAP_MANIFEST = (REPO_ROOT / "agent-bootstrap.toml").read_text(encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_repo(
    root: Path,
    *,
    first_run: bool = False,
    active_plans: bool = True,
    placeholder_scratchpad: bool = True,
) -> None:
    write(root / "agent-bootstrap.toml", BOOTSTRAP_MANIFEST)

    for path in (
        "core/INIT.md",
        "README.md",
        "core/governance/first-run.md",
        "CHANGELOG.md",
        "core/governance/curation-policy.md",
        "core/governance/update-guidelines.md",
        "core/governance/system-maturity.md",
        "core/governance/belief-diff-log.md",
        "core/governance/review-queue.md",
        "core/governance/session-checklists.md",
        "core/governance/security-signals.md",
        "core/memory/HOME.md",
        "core/memory/users/SUMMARY.md",
        "core/memory/activity/SUMMARY.md",
        "core/memory/working/projects/SUMMARY.md",
    ):
        write(root / path, f"# {Path(path).stem}\n")

    write(
        root / "core" / "memory" / "HOME.md",
        "# Home\n\n_Nothing here yet._\n",
    )

    profile_source = "template" if first_run else "user-stated"
    write(
        root / "core" / "memory" / "users" / "profile.md",
        textwrap.dedent(
            f"""\
            ---
            source: {profile_source}
            origin_session: manual
            created: 2026-03-18
            trust: high
            ---

            # Profile
            """
        ),
    )

    if not first_run:
        write(
            root
            / "core"
            / "memory"
            / "activity"
            / "2026"
            / "03"
            / "18"
            / "chat-001"
            / "SUMMARY.md",
            "# Chat\n",
        )

    projects_summary = (
        "---\ntype: projects-navigator\ngenerated: 2026-03-21 12:00\nproject_count: 1\n---\n\n# Projects\n\n| Project | Status | Mode | Open Qs | Focus | Last activity |\n|---|---|---|---|---|---|\n| example-project | ongoing | exploration | 2 | Example focus | 2026-03-21 |\n"
        if active_plans
        else "---\ntype: projects-navigator\ngenerated: 2026-03-21 12:00\nproject_count: 0\n---\n\n# Projects\n\n_No active or ongoing projects._\n"
    )
    write(root / "core" / "memory" / "working" / "projects" / "SUMMARY.md", projects_summary)

    if placeholder_scratchpad:
        write(
            root / "core" / "memory" / "working" / "USER.md",
            "# User notes\n\n_Nothing here yet. Add any context you'd like the agent to pick up at session start._\n",
        )
        write(
            root / "core" / "memory" / "working" / "CURRENT.md",
            "# Agent working notes\n\n_No current notes._\n",
        )
    else:
        write(
            root / "core" / "memory" / "working" / "USER.md",
            "# User notes\n\nImportant note.\n",
        )
        write(
            root / "core" / "memory" / "working" / "CURRENT.md",
            "# Agent working notes\n\nWorking note.\n",
        )


class BootstrapResolverTests(unittest.TestCase):
    def test_automation_mode_beats_other_detection_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, first_run=True)

            manifest = resolver.read_manifest(root)
            mode, source = resolver.detect_mode(
                root,
                manifest,
                automation=True,
                periodic_review=True,
                fresh_instantiation=True,
                full_bootstrap=True,
            )

            self.assertEqual(mode, "automation")
            self.assertEqual(source, "automation_flag")

    def test_automation_mode_surfaces_detached_worktree_attention(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, placeholder_scratchpad=False)

            resolution = resolver.resolve_startup(
                root,
                automation=True,
                expected_branch="automation/daily-review",
                git_state=resolver.GitState(
                    current_branch=None,
                    detached_head=True,
                    worktree_branch_drift=True,
                    branch_checked_out_elsewhere=False,
                ),
            )

            self.assertEqual(resolution.mode, "automation")
            self.assertEqual(resolution.mode_source, "automation_flag")
            self.assertEqual(resolution.startup_panel.title, "Automation Startup")
            self.assertEqual(resolution.startup_panel.mode_label, "Automation")
            self.assertEqual(resolution.startup_panel.status, "attention")
            self.assertEqual(resolution.startup_panel.loaded_count, 4)
            self.assertEqual(
                [warning.code for warning in resolution.startup_panel.warnings],
                ["detached_head", "worktree_branch_drift"],
            )
            self.assertIsNone(resolution.active_override)
            self.assertIsNone(resolution.startup_panel.active_override)

    def test_first_run_detection_uses_template_identity_and_no_chat_history(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, first_run=True)

            manifest = resolver.read_manifest(root)
            mode, source = resolver.detect_mode(root, manifest)

            self.assertEqual(mode, "first_run")
            self.assertEqual(source, "first_run_heuristic")

    def test_first_run_detection_accepts_single_quoted_template_source(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, first_run=True)
            write(
                root / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: 'template'
                    origin_session: manual
                    created: '2026-03-18'
                    trust: high
                    ---

                    # Profile
                    """
                ),
            )

            manifest = resolver.read_manifest(root)
            mode, source = resolver.detect_mode(root, manifest)

            self.assertEqual(mode, "first_run")
            self.assertEqual(source, "first_run_heuristic")

    def test_returning_trace_skips_placeholders_and_no_active_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, active_plans=False, placeholder_scratchpad=True)
            write(
                root / "agent-bootstrap.toml",
                BOOTSTRAP_MANIFEST.replace(
                    '[[modes.returning.steps]]\npath = "core/memory/working/USER.md"\nrole = "scratchpad-user"\nrequired = false\nskip_if = "placeholder_or_empty"\ncost = "light"',
                    '[[modes.returning.steps]]\npath = "core/memory/working/projects/SUMMARY.md"\nrole = "project-summary"\nrequired = false\nskip_if = "no_active_projects"\ncost = "light"\n\n[[modes.returning.steps]]\npath = "core/memory/working/USER.md"\nrole = "scratchpad-user"\nrequired = false\nskip_if = "placeholder_or_empty"\ncost = "light"',
                    1,
                ),
            )

            resolution = resolver.resolve_startup(root, requested_mode="returning")
            trace_by_path = {step.path: step for step in resolution.trace}

            self.assertEqual(trace_by_path["core/INIT.md"].status, "loaded")
            self.assertEqual(resolution.startup_panel.mode_label, "Returning")
            self.assertEqual(resolution.startup_panel.repo_next_step.path, "core/INIT.md")
            self.assertEqual(resolution.startup_panel.loaded_count, 3)
            self.assertEqual(resolution.startup_panel.skipped_count, 4)
            self.assertEqual(
                trace_by_path["core/memory/working/projects/SUMMARY.md"].status, "skipped"
            )
            self.assertEqual(
                trace_by_path["core/memory/working/projects/SUMMARY.md"].reason,
                "no_active_projects",
            )
            self.assertEqual(trace_by_path["core/memory/working/USER.md"].status, "skipped")
            self.assertEqual(
                trace_by_path["core/memory/working/USER.md"].reason,
                "placeholder_or_empty",
            )
            self.assertEqual(trace_by_path["core/memory/working/CURRENT.md"].status, "skipped")
            self.assertEqual(
                trace_by_path["core/memory/working/CURRENT.md"].reason,
                "placeholder_or_empty",
            )

    def test_duplicate_paths_are_deduplicated_after_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, placeholder_scratchpad=False)
            write(
                root / "agent-bootstrap.toml",
                BOOTSTRAP_MANIFEST.replace(
                    '[[modes.returning.steps]]\npath = "core/memory/users/SUMMARY.md"',
                    '[[modes.returning.steps]]\npath = "./core/memory/users/SUMMARY.md"\nrole = "identity-summary-alias"\nrequired = false\ncost = "light"\n\n[[modes.returning.steps]]\npath = "core/memory/users/SUMMARY.md"',
                    1,
                ),
            )

            resolution = resolver.resolve_startup(root, requested_mode="returning")
            identity_steps = [
                step for step in resolution.trace if step.path == "core/memory/users/SUMMARY.md"
            ]

            self.assertEqual(len(identity_steps), 2)
            self.assertEqual(identity_steps[0].status, "loaded")
            self.assertEqual(identity_steps[1].status, "skipped")
            self.assertEqual(identity_steps[1].reason, "duplicate_path")

    def test_warning_generation_respects_git_state(self) -> None:
        warnings = resolver.resolve_warnings(
            resolver.GitState(
                current_branch="feature/runtime",
                detached_head=True,
                worktree_branch_drift=True,
                branch_checked_out_elsewhere=True,
            ),
            {
                "warn_on_detached_head": True,
                "warn_on_worktree_branch_drift": True,
                "warn_on_branch_checked_out_elsewhere": True,
            },
            expected_branch="main",
        )

        self.assertEqual(
            [warning.code for warning in warnings],
            [
                "detached_head",
                "worktree_branch_drift",
                "branch_checked_out_elsewhere",
            ],
        )
        panel_warnings = [resolver.build_panel_warning(warning) for warning in warnings]
        self.assertEqual(
            [warning.title for warning in panel_warnings],
            [
                "Detached HEAD",
                "Branch Drift",
                "Branch In Another Worktree",
            ],
        )
        self.assertTrue(all(warning.source == "git" for warning in panel_warnings))

    def test_budget_pressure_skips_optional_step_and_updates_budget_state(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, placeholder_scratchpad=False)
            write(
                root / "agent-bootstrap.toml",
                BOOTSTRAP_MANIFEST.replace(
                    "[modes.returning]\ntoken_budget = 7000",
                    "[modes.returning]\ntoken_budget = 1500",
                    1,
                ).replace(
                    '[[modes.returning.steps]]\npath = "core/memory/activity/SUMMARY.md"\nrole = "activity-summary"\nrequired = false\nskip_if = "placeholder_or_empty"\ncost = "light"',
                    '[[modes.returning.steps]]\npath = "docs/heavy-context.md"\nrole = "heavy-context"\nrequired = false\ncost = "medium"\n\n[[modes.returning.steps]]\npath = "core/memory/activity/SUMMARY.md"\nrole = "activity-summary"\nrequired = false\nskip_if = "placeholder_or_empty"\ncost = "light"',
                    1,
                ),
            )
            write(root / "docs" / "heavy-context.md", "# Heavy context\n")

            resolution = resolver.resolve_startup(root, requested_mode="returning")
            trace_by_role = {step.role: step for step in resolution.trace}

            self.assertEqual(trace_by_role["heavy-context"].status, "skipped")
            self.assertEqual(trace_by_role["heavy-context"].reason, "budget_pressure")
            self.assertEqual(trace_by_role["heavy-context"].budget_after, 500)
            self.assertTrue(resolution.budget.pressure)
            self.assertEqual(resolution.budget.limit, 1500)
            self.assertEqual(resolution.budget.reserve, 500)
            self.assertEqual(resolution.budget.estimated_used, 1000)
            self.assertEqual(resolution.budget.estimated_remaining, 500)
            self.assertIn("budget_pressure", [warning.code for warning in resolution.warnings])

    def test_prefer_summaries_skips_transcript_under_budget_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, placeholder_scratchpad=True)
            write(root / "docs" / "topic" / "transcript.md", "# Transcript\n")
            write(root / "docs" / "topic" / "SUMMARY.md", "# Summary\n")
            write(
                root / "agent-bootstrap.toml",
                BOOTSTRAP_MANIFEST.replace(
                    "[modes.returning]\ntoken_budget = 7000",
                    "[modes.returning]\ntoken_budget = 2500",
                    1,
                ).replace(
                    '[[modes.returning.steps]]\npath = "core/memory/activity/SUMMARY.md"\nrole = "activity-summary"\nrequired = false\nskip_if = "placeholder_or_empty"\ncost = "light"',
                    '[[modes.returning.steps]]\npath = "docs/topic/transcript.md"\nrole = "topic-transcript"\nrequired = false\ncost = "light"\n\n[[modes.returning.steps]]\npath = "docs/topic/SUMMARY.md"\nrole = "topic-summary"\nrequired = false\ncost = "light"\n\n[[modes.returning.steps]]\npath = "core/memory/activity/SUMMARY.md"\nrole = "activity-summary"\nrequired = false\nskip_if = "placeholder_or_empty"\ncost = "light"',
                    1,
                ),
            )

            resolution = resolver.resolve_startup(root, requested_mode="returning")
            trace_by_role = {step.role: step for step in resolution.trace}

            self.assertEqual(trace_by_role["topic-transcript"].status, "skipped")
            self.assertEqual(trace_by_role["topic-transcript"].reason, "budget_pressure")
            self.assertEqual(trace_by_role["topic-transcript"].estimated_tokens, 7000)
            self.assertEqual(trace_by_role["topic-summary"].status, "loaded")
            self.assertEqual(trace_by_role["topic-summary"].estimated_tokens, 500)
            self.assertEqual(resolution.preload_access_mode, "startup_trace_only")
            self.assertEqual(resolution.startup_panel.budget_status, "tight")
            self.assertEqual(resolution.startup_panel.status, "attention")

    def test_startup_panel_surfaces_git_and_budget_attention(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, placeholder_scratchpad=False)

            resolution = resolver.resolve_startup(
                root,
                requested_mode="returning",
                expected_branch="main",
                git_state=resolver.GitState(
                    current_branch="feature/runtime",
                    detached_head=False,
                    worktree_branch_drift=True,
                    branch_checked_out_elsewhere=False,
                ),
            )

            self.assertEqual(resolution.startup_panel.title, "Returning Startup")
            self.assertEqual(resolution.startup_panel.status, "attention")
            self.assertEqual(resolution.startup_panel.warning_count, 1)
            self.assertEqual(len(resolution.startup_panel.warnings), 1)
            self.assertEqual(
                resolution.startup_panel.warnings[0].code,
                "worktree_branch_drift",
            )
            self.assertEqual(
                resolution.startup_panel.warnings[0].title,
                "Branch Drift",
            )
            self.assertEqual(
                resolution.startup_panel.warnings[0].source,
                "git",
            )
            self.assertEqual(
                resolution.startup_panel.repo_next_step.reason,
                "Repo-declared router for Returning mode.",
            )

    def test_host_repo_root_surfaces_host_git_state_when_configured(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tempdir,
            tempfile.TemporaryDirectory() as host_tempdir,
        ):
            root = Path(tempdir)
            host_root = Path(host_tempdir)
            build_repo(root, placeholder_scratchpad=False)

            subprocess.run(
                ["git", "init", "--initial-branch=main"],
                cwd=host_root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=host_root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=host_root,
                check=True,
                capture_output=True,
                text=True,
            )
            (host_root / "README.md").write_text("# Host\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "."],
                cwd=host_root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "host init"],
                cwd=host_root,
                check=True,
                capture_output=True,
                text=True,
            )

            write(
                root / "agent-bootstrap.toml",
                BOOTSTRAP_MANIFEST.replace(
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]',
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\nhost_repo_root = "'
                    + host_root.as_posix()
                    + '"',
                    1,
                ),
            )

            resolution = resolver.resolve_startup(root, requested_mode="returning")

            self.assertEqual(resolution.host_repo_root, str(host_root))
            self.assertIsNotNone(resolution.host_git_state)
            assert resolution.host_git_state is not None
            self.assertEqual(resolution.host_git_state.current_branch, "main")
            self.assertEqual(
                resolution.startup_panel.files[0].path,
                "core/INIT.md",
            )

    def test_startup_panel_surfaces_all_branch_and_worktree_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root, placeholder_scratchpad=False)

            resolution = resolver.resolve_startup(
                root,
                requested_mode="returning",
                expected_branch="main",
                git_state=resolver.GitState(
                    current_branch=None,
                    detached_head=True,
                    worktree_branch_drift=True,
                    branch_checked_out_elsewhere=True,
                ),
            )

            self.assertEqual(
                [warning.code for warning in resolution.startup_panel.warnings],
                [
                    "detached_head",
                    "worktree_branch_drift",
                    "branch_checked_out_elsewhere",
                ],
            )
            self.assertEqual(
                [warning.title for warning in resolution.startup_panel.warnings],
                [
                    "Detached HEAD",
                    "Branch Drift",
                    "Branch In Another Worktree",
                ],
            )
            self.assertTrue(
                all(warning.severity == "warning" for warning in resolution.startup_panel.warnings)
            )

    # ------------------------------------------------------------------
    # Manual override controls (Phase 3, item 9)
    # ------------------------------------------------------------------

    def test_override_full_bootstrap_forces_full_bootstrap_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)

            resolution = resolver.resolve_startup(root, user_override="full_bootstrap")

            self.assertEqual(resolution.mode, "full_bootstrap")
            self.assertEqual(resolution.active_override, "full_bootstrap")
            self.assertEqual(resolution.startup_panel.active_override, "full_bootstrap")
            # The active override must appear in available_overrides with active=True;
            # the other two must be inactive.
            overrides_by_id = {o.id: o for o in resolution.startup_panel.available_overrides}
            self.assertIn("full_bootstrap", overrides_by_id)
            self.assertIn("compact_only", overrides_by_id)
            self.assertIn("skip_manifest", overrides_by_id)
            self.assertTrue(overrides_by_id["full_bootstrap"].active)
            self.assertFalse(overrides_by_id["compact_only"].active)
            self.assertFalse(overrides_by_id["skip_manifest"].active)

    def test_override_compact_only_forces_returning_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            # Build a first-run-shaped repo; compact_only should still force returning.
            build_repo(root, first_run=True)

            resolution = resolver.resolve_startup(root, user_override="compact_only")

            self.assertEqual(resolution.mode, "returning")
            self.assertEqual(resolution.active_override, "compact_only")
            self.assertEqual(resolution.startup_panel.active_override, "compact_only")
            overrides_by_id = {o.id: o for o in resolution.startup_panel.available_overrides}
            self.assertTrue(overrides_by_id["compact_only"].active)
            self.assertFalse(overrides_by_id["full_bootstrap"].active)
            self.assertFalse(overrides_by_id["skip_manifest"].active)
            # No manifest_skipped warning — we still used the manifest.
            self.assertNotIn(
                "manifest_skipped",
                [w.code for w in resolution.warnings],
            )

    def test_override_skip_manifest_bypasses_manifest_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)
            write(root / "AGENTS.md", "# Agents\n")

            resolution = resolver.resolve_startup(root, user_override="skip_manifest")

            # Mode source communicates the bypass.
            self.assertEqual(resolution.mode_source, "user_override_skip_manifest")
            self.assertEqual(resolution.active_override, "skip_manifest")

            # A manifest_skipped warning must always be present.
            warning_codes = [w.code for w in resolution.warnings]
            self.assertIn("manifest_skipped", warning_codes)

            # Panel reflects the warning.
            self.assertEqual(resolution.startup_panel.status, "attention")
            panel_warning_codes = [w.code for w in resolution.startup_panel.warnings]
            self.assertIn("manifest_skipped", panel_warning_codes)
            manifest_panel_warning = next(
                w for w in resolution.startup_panel.warnings if w.code == "manifest_skipped"
            )
            self.assertEqual(manifest_panel_warning.source, "user_override")
            self.assertEqual(manifest_panel_warning.title, "Manifest Bypassed")

            # AGENTS.md should have been loaded from the fallback step list.
            trace_by_role = {step.role: step for step in resolution.trace}
            self.assertIn("agents-manifest", trace_by_role)
            self.assertEqual(trace_by_role["agents-manifest"].status, "loaded")

            # Override reflected in available_overrides.
            overrides_by_id = {o.id: o for o in resolution.startup_panel.available_overrides}
            self.assertTrue(overrides_by_id["skip_manifest"].active)
            self.assertFalse(overrides_by_id["full_bootstrap"].active)
            self.assertFalse(overrides_by_id["compact_only"].active)

    def test_override_skip_manifest_with_no_agents_md_falls_back_to_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)
            # No AGENTS.md — only README.md should load.

            resolution = resolver.resolve_startup(root, user_override="skip_manifest")

            trace_by_role = {step.role: step for step in resolution.trace}
            self.assertEqual(trace_by_role["agents-manifest"].status, "missing")
            self.assertEqual(trace_by_role["readme"].status, "loaded")

    def test_no_override_leaves_active_override_none_with_all_controls_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_repo(root)

            resolution = resolver.resolve_startup(root, requested_mode="returning")

            self.assertIsNone(resolution.active_override)
            self.assertIsNone(resolution.startup_panel.active_override)
            overrides = resolution.startup_panel.available_overrides
            self.assertEqual(len(overrides), 3)
            self.assertTrue(all(not o.active for o in overrides))


if __name__ == "__main__":
    unittest.main()
