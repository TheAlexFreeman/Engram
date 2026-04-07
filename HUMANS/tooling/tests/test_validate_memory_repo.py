from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "validate_memory_repo.py"

SPEC = importlib.util.spec_from_file_location("validate_memory_repo", VALIDATOR_PATH)
assert SPEC is not None
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)

INSPECTOR_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "inspect_compact_budget.py"
INSPECTOR_SPEC = importlib.util.spec_from_file_location("inspect_compact_budget", INSPECTOR_PATH)
assert INSPECTOR_SPEC is not None
inspector = importlib.util.module_from_spec(INSPECTOR_SPEC)
assert INSPECTOR_SPEC.loader is not None
sys.modules[INSPECTOR_SPEC.name] = inspector
INSPECTOR_SPEC.loader.exec_module(inspector)

PROMPT_START_LINE = validator.PROMPT_START_LINE
PROMPT_ROUTE_LINE = validator.PROMPT_ROUTE_LINE
PROMPT_MCP_LINE = validator.PROMPT_MCP_LINE
LIVE_CONFIG_LINE = validator.LIVE_CONFIG_LINE
ADAPTER_ROUTING_LINE = validator.ADAPTER_ROUTING_PHRASE
ADAPTER_MCP_LINE = validator.ADAPTER_MCP_PHRASE
FIRST_RUN_MCP_LINE = validator.FIRST_RUN_MCP_PHRASE
SESSION_CHECKLISTS_MCP_LINE = validator.SESSION_CHECKLISTS_MCP_PHRASE
SKILLS_SUMMARY_MCP_LINE = validator.SKILLS_SUMMARY_MCP_PHRASE
ONBOARDING_SKILL_MCP_LINE = validator.ONBOARDING_SKILL_MCP_PHRASE
SESSION_START_SKILL_MCP_LINE = validator.SESSION_START_SKILL_MCP_PHRASE
SESSION_SYNC_SKILL_MCP_LINE = validator.SESSION_SYNC_SKILL_MCP_PHRASE
SESSION_WRAPUP_SKILL_MCP_LINE = validator.SESSION_WRAPUP_SKILL_MCP_PHRASE
README_START_LINE = validator.README_START_PHRASE
README_ARCHITECTURE_LINE = validator.README_ARCHITECTURE_PHRASE
SETUP_GUIDANCE_LINE = "live routing in `core/INIT.md`"


VALID_QUICK_REFERENCE = (REPO_ROOT / "core" / "INIT.md").read_text(encoding="utf-8")

VALID_BOOTSTRAP_MANIFEST = (REPO_ROOT / "agent-bootstrap.toml").read_text(encoding="utf-8")

VALID_TASK_READINESS_MANIFEST = (
    REPO_ROOT / "HUMANS" / "tooling" / "agent-task-readiness.toml"
).read_text(encoding="utf-8")
VALID_CAPABILITIES_MANIFEST = (
    REPO_ROOT / "HUMANS" / "tooling" / "agent-memory-capabilities.toml"
).read_text(encoding="utf-8")
README_TEXT = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
PROVENANCE_GUIDANCE = (REPO_ROOT / "core" / "governance" / "update-guidelines.md").read_text(
    encoding="utf-8"
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def git_available() -> bool:
    return shutil.which("git") is not None


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def build_minimal_repo(root: Path) -> None:
    write(root / "agent-bootstrap.toml", VALID_BOOTSTRAP_MANIFEST)
    write(
        root / "HUMANS" / "tooling" / "agent-task-readiness.toml",
        VALID_TASK_READINESS_MANIFEST,
    )
    write(
        root / "HUMANS" / "tooling" / "scripts" / "resolve_task_readiness.py",
        "#!/usr/bin/env python3\n",
    )
    write(
        root / "HUMANS" / "tooling" / "agent-memory-capabilities.toml", VALID_CAPABILITIES_MANIFEST
    )
    write(root / "core" / "tools" / "__init__.py", "\n")
    write(root / "core" / "tools" / "memory_mcp.py", "#!/usr/bin/env python3\n")
    write(
        root / "README.md",
        textwrap.dedent(
            f"""\
            # README

            {README_START_LINE}
            When you need the live operating contract, {README_ARCHITECTURE_LINE}.
            When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation.
            """
        ),
    )
    write(root / "CHANGELOG.md", "# Changelog\n")
    write(
        root / "setup.sh",
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            exec bash "$(pwd)/HUMANS/setup/setup.sh" "$@"
            """
        ),
    )
    write(
        root / "setup.html",
        '<!DOCTYPE html><html><body><a href="HUMANS/views/setup.html">HUMANS/views/setup.html</a></body></html>\n',
    )
    write(
        root / "HUMANS" / "setup" / "setup.sh",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            {PROMPT_START_LINE}
            {PROMPT_ROUTE_LINE}
            {PROMPT_MCP_LINE}
            {LIVE_CONFIG_LINE}
            {SETUP_GUIDANCE_LINE}
            """
        ),
    )
    write(
        root / "HUMANS" / "views" / "setup.html",
        textwrap.dedent(
            f"""\
            <!DOCTYPE html>
            <html>
            <body>
            <p>{PROMPT_START_LINE}</p>
            <p>{PROMPT_ROUTE_LINE}</p>
            <p>{PROMPT_MCP_LINE}</p>
            <p>{LIVE_CONFIG_LINE}</p>
            git remote setup stays manual
            </body>
            </html>
            """
        ),
    )
    write(
        root / "AGENTS.md",
        (
            "# Engram\n\n"
            f"This repository is a persistent AI memory system. At the start of every session, {ADAPTER_ROUTING_LINE}. "
            f"{ADAPTER_MCP_LINE}; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation. "
            "Do not duplicate the full rule list here — `README.md` and `core/governance/` are the single source of truth.\n"
        ),
    )
    write(root / "CLAUDE.md", (root / "AGENTS.md").read_text(encoding="utf-8"))
    write(root / ".cursorrules", (root / "AGENTS.md").read_text(encoding="utf-8"))

    (root / "HUMANS" / "docs").mkdir(parents=True, exist_ok=True)
    write(
        root / "HUMANS" / "docs" / "QUICKSTART.md",
        textwrap.dedent(
            f"""\
            # Quickstart

            ```bash
            bash setup.sh
            ```

            Open `setup.html` in any browser. Git remote setup stays manual.

            {PROMPT_START_LINE}
            {PROMPT_ROUTE_LINE}
            {PROMPT_MCP_LINE}
            {LIVE_CONFIG_LINE}
            {SETUP_GUIDANCE_LINE}

            | Session mode | Typical token cost | When |
            | --- | --- | --- |
            | First-run onboarding bootstrap | ~15,000–20,000 | Fresh model instantiation on a blank or template-backed repo |
            | Returning compact session | ~3,000–7,000 | Normal day-to-day use via the compact returning manifest in `core/INIT.md` |
            | Full bootstrap / periodic review | ~18,000–25,000 | Fresh model on a returning system, or sessions that reopen the full governance stack and review artifacts |
            """
        ),
    )
    write(
        root / "HUMANS" / "tooling" / "onboard-export-template.md",
        textwrap.dedent(
            """\
            # Onboarding Export

            Save it to a file and run `bash HUMANS/tooling/scripts/onboard-export.sh <file>`.
            """
        ),
    )

    write(root / "core" / "INIT.md", VALID_QUICK_REFERENCE)
    write(
        root / "core" / "governance" / "first-run.md",
        "# First run\n",
    )
    write(
        root / "core" / "governance" / "curation-policy.md",
        "# Curation Policy\nUse `core/INIT.md` for live thresholds.\n",
    )
    write(
        root / "core" / "governance" / "update-guidelines.md",
        "# Update Guidelines\nRead-only operation is documented here.\n",
    )
    write(
        root / "core" / "governance" / "session-checklists.md",
        (
            "# Session checklists\n"
            "Load on demand when you need more detail than the compact manifest in `core/INIT.md`.\n\n"
        ),
    )
    write(
        root / "core" / "governance" / "review-queue.md",
        "# Review Queue\n\n_No pending items._\n",
    )
    write(root / "core" / "governance" / "system-maturity.md", "# System maturity\n")
    write(root / "core" / "governance" / "belief-diff-log.md", "# Belief diff log\n")
    write(
        root / "core" / "governance" / "content-boundaries.md",
        "# Content Boundaries\nTrust-weighted retrieval and instruction containment.\n",
    )
    write(
        root / "core" / "governance" / "security-signals.md",
        "# Security Signals\nTemporal decay, anomaly detection, drift, governance feedback.\n",
    )

    write(root / "core" / "memory" / "users" / "ACCESS.jsonl", "")
    write(root / "core" / "memory" / "knowledge" / "ACCESS.jsonl", "")
    write(root / "core" / "memory" / "skills" / "ACCESS.jsonl", "")
    write(root / "core" / "memory" / "activity" / "ACCESS.jsonl", "")
    write(root / "core" / "memory" / "working" / "projects" / "ACCESS.jsonl", "")
    write(
        root / "core" / "memory" / "working" / "projects" / "SUMMARY.md",
        textwrap.dedent(
            """\
            ---
            type: projects-navigator
            generated: 2026-03-16
            project_count: 1
            ---

            # Projects

            | Project | Status | Mode | Open Qs | Focus | Last activity |
            | --- | --- | --- | --- | --- | --- |
            | seed-project | completed | verification | 0 | Baseline fixture | 2026-03-16 |
            """
        ),
    )
    write(
        root / "core" / "memory" / "working" / "projects" / "seed-project" / "SUMMARY.md",
        "# Seed project\n\nFixture content.\n",
    )

    write(
        root / "core" / "memory" / "users" / "SUMMARY.md",
        "# Users Summary\n\nNo portrait yet.\n\nDrill-down: [profile.md](profile.md)\n",
    )
    write(
        root / "core" / "memory" / "users" / "profile.md",
        textwrap.dedent(
            """\
            ---
            source: template
            origin_session: setup
            created: 2026-03-16
            trust: medium
            ---

            # Profile
            """
        ),
    )
    write(
        root / "core" / "memory" / "activity" / "SUMMARY.md",
        textwrap.dedent(
            """\
            ---
            source: system
            origin_session: setup
            created: 2026-03-16
            trust: high
            ---

            # Activity Summary

            ## Live themes

            No recurring live themes yet.

            ## Recent continuity

            No session history yet.

            ## Retrieval guide

            Load dated summaries when you need session continuity beyond this compact surface.

            ## Drill-down paths

            - core/memory/activity/2026/03/16/chat-001/SUMMARY.md
            """
        ),
    )
    write(
        root / "core" / "memory" / "activity" / "2026" / "03" / "16" / "chat-001" / "SUMMARY.md",
        "# Chat Summary\n\nSession notes.\n",
    )
    write(
        root / "core" / "memory" / "activity" / "2026" / "03" / "16" / "chat-001" / "reflection.md",
        "## Session reflection\n\nFixture reflection note.\n",
    )

    write(
        root / "core" / "memory" / "HOME.md",
        "# Home\n\n_Nothing here yet._\n",
    )

    write(
        root / "core" / "memory" / "skills" / "SUMMARY.md",
        "# Skills summary\n",
    )
    write(
        root / "core" / "memory" / "skills" / "onboarding" / "SKILL.md",
        textwrap.dedent(
            """\
            ---
            source: user-stated
            origin_session: manual
            created: 2026-03-16
            last_verified: 2026-03-16
            trust: high
            ---

            # Onboarding
            """
        ),
    )
    write(
        root / "core" / "memory" / "skills" / "session-sync" / "SKILL.md",
        textwrap.dedent(
            """\
            ---
            source: user-stated
            origin_session: manual
            created: 2026-03-16
            last_verified: 2026-03-16
            trust: high
            ---

            # Session sync
            """
        ),
    )

    write(
        root / "core" / "memory" / "working" / "USER.md",
        "# User notes\n\n_Nothing here yet. Add any context you'd like the agent to pick up at session start._\n",
    )
    write(
        root / "core" / "memory" / "working" / "CURRENT.md",
        "# Agent working notes\n\n## Active threads\n\n_None_\n\n## Immediate next actions\n\n_None_\n\n## Open questions\n\n_None_\n\n## Drill-down refs\n\n- core/memory/working/projects/SUMMARY.md\n",
    )


def init_host_git_repo(root: Path) -> None:
    git(root, "init", "--initial-branch=core")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.com")
    write(root / "src" / "app.py", "print('host repo')\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "host init")


def add_host_repo_root(manifest_path: Path, host_root: Path) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    host_line = f'host_repo_root = "{host_root.as_posix()}"'
    if re.search(r'^host_repo_root = ".*"$', text, flags=re.MULTILINE):
        text = re.sub(r'^host_repo_root = ".*"$', host_line, text, count=1, flags=re.MULTILINE)
    else:
        text = text.replace(
            'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]',
            'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\n' + host_line,
            1,
        )
    manifest_path.write_text(text, encoding="utf-8")


def normalize_worktree_bootstrap_manifest(manifest_path: Path) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    for block in (
        '[[modes.full_bootstrap.steps]]\npath = "CHANGELOG.md"\nrole = "system-history"\nrequired = true\ncost = "medium"\n',
        '[[modes.periodic_review.steps]]\npath = "CHANGELOG.md"\nrole = "system-history"\nrequired = true\ncost = "medium"\n',
    ):
        text = text.replace(block, "")
    manifest_path.write_text(text, encoding="utf-8")


def write_host_adapter_files(host_root: Path, *, duplicate_from: Path | None = None) -> None:
    for relative_path in ("AGENTS.md", "CLAUDE.md", ".cursorrules"):
        target = host_root / relative_path
        if duplicate_from is not None:
            target.write_text(
                (duplicate_from / relative_path).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            target.write_text(
                f"# Host adapter\n\nThis host repo stores memory in a separate worktree. ({relative_path})\n",
                encoding="utf-8",
            )


def build_worktree_repo(
    host_root: Path,
    memory_root: Path,
    *,
    orphan_branch: bool = True,
    include_host_repo_root: bool = True,
) -> None:
    if not git_available():
        raise unittest.SkipTest("git is not available in this environment")

    init_host_git_repo(host_root)
    temp_worktree = host_root / ".git" / "validator-memory-temp"

    if orphan_branch:
        git(host_root, "worktree", "add", "--detach", str(temp_worktree), "HEAD")
        git(temp_worktree, "checkout", "--orphan", "agent-memory")
    else:
        git(host_root, "worktree", "add", "-b", "agent-memory", str(temp_worktree), "core")

    subprocess.run(
        ["git", "rm", "-rf", "--ignore-unmatch", "."],
        cwd=temp_worktree,
        check=True,
        capture_output=True,
        text=True,
    )

    build_minimal_repo(temp_worktree)
    if include_host_repo_root:
        add_host_repo_root(temp_worktree / "agent-bootstrap.toml", host_root)
        normalize_worktree_bootstrap_manifest(temp_worktree / "agent-bootstrap.toml")
    write_host_adapter_files(host_root)

    git(temp_worktree, "add", "--all")
    git(temp_worktree, "commit", "-m", "seed memory")
    git(host_root, "worktree", "remove", "--force", str(temp_worktree))
    git(host_root, "worktree", "add", str(memory_root), "agent-memory")
    if include_host_repo_root:
        add_host_repo_root(memory_root / "agent-bootstrap.toml", host_root)
        normalize_worktree_bootstrap_manifest(memory_root / "agent-bootstrap.toml")


def strip_standalone_only_files(root: Path) -> None:
    for relative_path in (
        Path("CHANGELOG.md"),
        Path("setup.sh"),
        Path("setup.html"),
        Path("setup"),
        Path("HUMANS"),
    ):
        target = root / relative_path
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    normalize_worktree_bootstrap_manifest(root / "agent-bootstrap.toml")


class ValidateMemoryRepoTests(unittest.TestCase):
    def assert_no_non_coverage_warnings(self, result: object) -> None:
        warnings = list(getattr(result, "warnings"))
        unexpected = [warning for warning in warnings if not warning.startswith("CoverageGap:")]
        self.assertEqual(unexpected, [], "\n".join(unexpected))

    def test_current_seed_repo_passes_validation(self) -> None:
        result = validator.validate_repo(REPO_ROOT)
        self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_access_entries_with_and_without_session_id_and_unknown_source_pass(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "example.md",
                textwrap.dedent(
                    """\
                    ---
                    source: unknown
                    origin_session: unknown
                    created: 2026-03-16
                    trust: medium
                    ---

                    # Example
                    """
                ),
            )
            write(
                root / "core" / "memory" / "skills" / "ACCESS.jsonl",
                "\n".join(
                    (
                        '{"file":"core/memory/skills/example.md","date":"2026-03-16","task":"test","helpfulness":0.7,"note":"used"}',
                        '{"file":"core/memory/skills/example.md","date":"2026-03-16","task":"test","helpfulness":0.8,"note":"used","session_id":"core/memory/activity/2026/03/16/chat-001"}',
                    )
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_runtime_validator_and_docs_share_provenance_vocabulary(self) -> None:
        from core.tools.agent_memory_mcp.frontmatter_policy import (
            ALLOWED_SOURCE_VALUES as runtime_sources,
        )
        from core.tools.agent_memory_mcp.frontmatter_policy import (
            ALLOWED_TRUST_VALUES as runtime_trust,
        )

        self.assertEqual(set(runtime_sources), set(validator.ALLOWED_SOURCE_VALUES))
        self.assertEqual(set(runtime_trust), set(validator.ALLOWED_TRUST_VALUES))

        docs_text = README_TEXT + "\n" + PROVENANCE_GUIDANCE
        for source in runtime_sources:
            self.assertIn(source, docs_text)
        for trust in runtime_trust:
            self.assertIn(trust, docs_text)

    def test_missing_bootstrap_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            (root / "agent-bootstrap.toml").unlink()

            result = validator.validate_repo(root)
            self.assertTrue(any("missing bootstrap manifest" in error for error in result.errors))

    def test_missing_mcp_entrypoint_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            (root / "core" / "tools" / "memory_mcp.py").unlink()

            result = validator.validate_repo(root)
            self.assertTrue(
                any("missing MCP entrypoint script" in error for error in result.errors)
            )

    def test_legacy_tools_runtime_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            (root / "tools").mkdir(parents=True, exist_ok=True)

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "legacy tools/ runtime directory must not exist" in error
                    for error in result.errors
                )
            )

    def test_capabilities_manifest_with_wrong_mcp_entrypoint_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "HUMANS" / "tooling" / "agent-memory-capabilities.toml",
                VALID_CAPABILITIES_MANIFEST.replace(
                    'mcp_entrypoint = "core/tools/memory_mcp.py"',
                    'mcp_entrypoint = "HUMANS/tooling/scripts/memory_mcp.py"',
                    1,
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "mcp_entrypoint must be 'core/tools/memory_mcp.py'" in error
                    for error in result.errors
                )
            )

    def test_missing_task_readiness_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            (root / "HUMANS" / "tooling" / "agent-task-readiness.toml").unlink()

            result = validator.validate_repo(root)
            self.assertTrue(
                any("missing task-readiness manifest" in error for error in result.errors)
            )

    def test_task_readiness_manifest_with_wrong_default_profile_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "HUMANS" / "tooling" / "agent-task-readiness.toml",
                VALID_TASK_READINESS_MANIFEST.replace(
                    'default_profile = "workspace_general"',
                    'default_profile = "pull_request"',
                    1,
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "task_detection.default_profile must be 'workspace_general'" in error
                    for error in result.errors
                )
            )

    def test_task_readiness_manifest_with_unknown_check_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "HUMANS" / "tooling" / "agent-task-readiness.toml",
                VALID_TASK_READINESS_MANIFEST.replace(
                    'checks = [\n  "git_cli",\n  "git_remote",\n  "git_push_dry_run",\n  "gh_auth",\n  "remote_network",\n]',
                    'checks = ["git_cli", "missing_check"]',
                    1,
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("references unknown check 'missing_check'" in error for error in result.errors)
            )

    def test_bootstrap_manifest_with_wrong_router_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "agent-bootstrap.toml",
                VALID_BOOTSTRAP_MANIFEST.replace(
                    'router = "core/INIT.md"',
                    'router = "README.md"',
                    1,
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("router must be 'core/INIT.md'" in error for error in result.errors)
            )

    def test_bootstrap_manifest_with_wrong_returning_order_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "agent-bootstrap.toml",
                VALID_BOOTSTRAP_MANIFEST.replace(
                    'path = "core/memory/users/SUMMARY.md"',
                    'path = "core/memory/knowledge/SUMMARY.md"',
                    1,
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("modes.returning.steps must load" in error for error in result.errors)
            )

    def test_bootstrap_manifest_with_relative_host_repo_root_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "agent-bootstrap.toml",
                VALID_BOOTSTRAP_MANIFEST.replace(
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]',
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\nhost_repo_root = "../host-repo"',
                    1,
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("host_repo_root must be an absolute path" in error for error in result.errors)
            )

    def test_valid_worktree_bootstrap_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            host_root = Path(tempdir) / "host"
            memory_root = Path(tempdir) / "memory"
            host_root.mkdir(parents=True, exist_ok=True)
            build_worktree_repo(host_root, memory_root)

            result = validator.validate_repo(memory_root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assert_no_non_coverage_warnings(result)

    def test_worktree_without_host_repo_root_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            host_root = Path(tempdir) / "host"
            memory_root = Path(tempdir) / "memory"
            host_root.mkdir(parents=True, exist_ok=True)
            build_worktree_repo(host_root, memory_root, include_host_repo_root=False)

            result = validator.validate_repo(memory_root)
            self.assertTrue(
                any(
                    "host_repo_root is required when validating a git worktree checkout" in error
                    for error in result.errors
                )
            )

    def test_worktree_host_repo_root_inside_memory_root_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            host_root = Path(tempdir) / "host"
            memory_root = Path(tempdir) / "memory"
            host_root.mkdir(parents=True, exist_ok=True)
            build_worktree_repo(host_root, memory_root)
            add_host_repo_root(
                memory_root / "agent-bootstrap.toml", memory_root / "core" / "memory" / "knowledge"
            )

            result = validator.validate_repo(memory_root)
            self.assertTrue(
                any(
                    "host_repo_root must not point inside the memory repo root" in error
                    for error in result.errors
                )
            )

    def test_worktree_shared_history_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            host_root = Path(tempdir) / "host"
            memory_root = Path(tempdir) / "memory"
            host_root.mkdir(parents=True, exist_ok=True)
            build_worktree_repo(host_root, memory_root, orphan_branch=False)

            result = validator.validate_repo(memory_root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertTrue(
                any(
                    "shares history with host default branch" in warning
                    for warning in result.warnings
                )
            )

    def test_worktree_duplicate_host_adapters_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            host_root = Path(tempdir) / "host"
            memory_root = Path(tempdir) / "memory"
            host_root.mkdir(parents=True, exist_ok=True)
            build_worktree_repo(host_root, memory_root)
            write_host_adapter_files(host_root, duplicate_from=memory_root)

            result = validator.validate_repo(memory_root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertTrue(
                any("duplicates host-root adapter file" in warning for warning in result.warnings)
            )

    def test_deployed_worktree_profile_skips_standalone_only_contract_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            host_root = Path(tempdir) / "host"
            memory_root = Path(tempdir) / "memory"
            host_root.mkdir(parents=True, exist_ok=True)
            build_worktree_repo(host_root, memory_root)
            strip_standalone_only_files(memory_root)

            result = validator.validate_repo(memory_root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_compact_startup_budget_overrun_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "working" / "CURRENT.md",
                "# Agent working notes\n\n"
                + "## Active threads\n\n- "
                + ("very long note " * 800)
                + "\n\n## Immediate next actions\n\n- Trim this file\n\n## Open questions\n\n- How much is too much?\n\n## Drill-down refs\n\n- core/memory/working/projects/compact-bootstrap-efficiency.md\n",
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "compact startup file uses ~" in error
                    or "compact returning startup uses ~" in error
                    for error in result.errors
                )
            )

    def test_chats_summary_with_chat_by_chat_heading_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "activity" / "SUMMARY.md",
                textwrap.dedent(
                    """\
                    # Chats Summary

                    ## Live themes

                    - Theme

                    ## Recent continuity

                    - Continuity

                    ## Retrieval guide

                    - Load dated summaries when needed.

                    ### chat-001

                    Too much narrative.
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "chat-by-chat narrative headings are too detailed" in error
                    for error in result.errors
                )
            )

    def test_projects_summary_without_rows_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "working" / "projects" / "SUMMARY.md",
                textwrap.dedent(
                    """\
                    ---
                    type: projects-navigator
                    generated: 2026-03-16
                    project_count: 1
                    ---

                    # Projects

                    | Project | Status | Mode | Open Qs | Focus | Last activity |
                    | --- | --- | --- | --- | --- | --- |
                    | broken-project | active | execution | 2 | Missing date cell |
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "navigator must contain at least one project row" in error
                    for error in result.errors
                )
            )

    def test_bootstrap_manifest_missing_optional_skip_rule_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            broken_manifest = re.sub(
                r'(\[\[modes\.returning\.steps\]\]\npath = "core/memory/activity/SUMMARY\.md"\nrole = "activity-summary"\nrequired = false\n)skip_if = "placeholder_or_empty"\n(cost = "light")',
                r"\1\2",
                VALID_BOOTSTRAP_MANIFEST,
                count=1,
            )
            write(
                root / "agent-bootstrap.toml",
                broken_manifest,
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("must use skip_if = 'placeholder_or_empty'" in error for error in result.errors)
            )

    def test_compact_budget_inspector_reports_file_breakdown(self) -> None:
        report = inspector.build_report(REPO_ROOT)

        self.assertIn("status", report)
        self.assertIn("total_tokens", report)
        self.assertIn("files", report)
        self.assertTrue(any(entry["path"] == "core/INIT.md" for entry in report["files"]))
        self.assertEqual(
            report["budget_limit"],
            validator.COMPACT_RETURNING_BUDGET,
        )

    def test_access_entry_with_malformed_session_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "example.md",
                textwrap.dedent(
                    """\
                    ---
                    source: unknown
                    origin_session: unknown
                    created: 2026-03-16
                    trust: medium
                    ---

                    # Example
                    """
                ),
            )
            write(
                root / "core" / "memory" / "skills" / "ACCESS.jsonl",
                '{"file":"core/memory/skills/example.md","date":"2026-03-16","task":"test","helpfulness":0.8,"note":"used","session_id":"chat-001"}',
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "session_id must match core/memory/activity/YYYY/MM/DD/chat-NNN" in error
                    for error in result.errors
                )
            )

    def test_coverage_gap_warns_for_monitored_folder_without_recent_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)

            result = validator.validate_repo(root)

            self.assertTrue(
                any(
                    warning.startswith("CoverageGap: core/memory/skills/")
                    and f"last {validator.DEFAULT_ACCESS_COVERAGE_WINDOW_DAYS} days" in warning
                    for warning in result.warnings
                )
            )

    def test_coverage_gap_does_not_warn_for_folder_with_recent_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "ACCESS.jsonl",
                json.dumps(
                    {
                        "file": "core/memory/skills/onboarding/SKILL.md",
                        "date": date.today().isoformat(),
                        "task": "validator coverage",
                        "helpfulness": 0.8,
                        "note": "recent skill access",
                        "session_id": "core/memory/activity/2026/03/20/chat-001",
                    }
                )
                + "\n",
            )

            result = validator.validate_repo(root)

            self.assertFalse(
                any(
                    warning.startswith("CoverageGap: core/memory/skills/")
                    for warning in result.warnings
                )
            )

    def test_invalid_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "example.md",
                textwrap.dedent(
                    """\
                    ---
                    source: generated
                    origin_session: unknown
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: medium
                    ---

                    # Example
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(any("invalid source" in error for error in result.errors))

    def test_template_source_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: template
                    origin_session: setup
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: medium
                    ---

                    # Profile
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_agent_generated_plan_with_required_fields_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root
                / "core"
                / "memory"
                / "working"
                / "projects"
                / "seed-project"
                / "plans"
                / "roadmap.md",
                textwrap.dedent(
                    """\
                    ---
                    source: agent-generated
                    type: implementation-plan
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: medium
                    status: active
                    next_action: "Implement phase 1"
                    ---

                    # Roadmap
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_plan_missing_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root
                / "core"
                / "memory"
                / "working"
                / "projects"
                / "seed-project"
                / "plans"
                / "roadmap.md",
                textwrap.dedent(
                    """\
                    ---
                    source: agent-generated
                    type: implementation-plan
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: medium
                    next_action: "Implement phase 1"
                    ---

                    # Roadmap
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "plan files must define frontmatter key 'status'" in error
                    for error in result.errors
                )
            )

    def test_missing_optional_last_verified_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    trust: high
                    ---

                    # Profile
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assert_no_non_coverage_warnings(result)

    def test_invalid_optional_last_verified_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    last_verified: not-a-date
                    trust: high
                    ---

                    # Profile
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "last_verified must be a valid YYYY-MM-DD date" in error
                    for error in result.errors
                )
            )

    def test_malformed_access_jsonl_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "ACCESS.jsonl",
                '{"file":"core/memory/skills/example.md","date":"2026-03-16","task":"test"',
            )

            result = validator.validate_repo(root)
            self.assertTrue(any("malformed JSON" in error for error in result.errors))

    def test_missing_frontmatter_key_fails_when_frontmatter_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "example.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    ---

                    # Example
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("missing required frontmatter keys" in error for error in result.errors)
            )

    def test_canonical_origin_session_path_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: high
                    ---

                    # Profile
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assert_no_non_coverage_warnings(result)

    def test_legacy_origin_session_warns_but_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: high
                    ---

                    # Profile
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertTrue(any("legacy origin_session" in warning for warning in result.warnings))

    def test_malformed_origin_session_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: core/memory/activity/2026/chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: high
                    ---

                    # Profile
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(any("origin_session must be" in error for error in result.errors))

    def test_runtime_guidance_pointing_to_system_maturity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "governance" / "curation-policy.md",
                "# Curation Policy\nCheck the current maturity stage in `core/governance/system-maturity.md`.\n",
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("forbidden runtime guidance pattern" in error for error in result.errors)
            )

    def test_session_start_skill_with_readme_bootstrap_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "session-start" / "SKILL.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: manual
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: high
                    ---

                    Run at the beginning of every session after the bootstrap sequence completes (i.e., after README.md has been read and the agent is oriented).

                    - Read `core/governance/review-queue.md`. Are there pending proposals the user hasn't reviewed?
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("forbidden startup-skill pattern" in error for error in result.errors)
            )

    def test_session_start_skill_with_compact_manifest_guidance_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "session-start" / "SKILL.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: manual
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: high
                    ---

                    For normal returning sessions, follow the compact returning manifest in `core/INIT.md`, then use `core/memory/HOME.md` as the session entry point. Load `core/governance/session-checklists.md` only when you want more detail than that compact path.

                    Run at the beginning of returning sessions after the compact returning manifest in `core/INIT.md` has oriented the agent.

                    - Use metadata-first maintenance checks. If `core/governance/review-queue.md` still contains only its placeholder, skip it. Load it only when there are real pending items or the user asks about them.
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_session_wrapup_skill_with_stale_checklist_default_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "session-wrapup" / "SKILL.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: manual
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: high
                    ---

                    For normal sessions, the compact checklist in `core/governance/session-checklists.md` is sufficient.
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("forbidden wrapup-skill pattern" in error for error in result.errors)
            )

    def test_session_wrapup_skill_with_on_demand_guidance_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "session-wrapup" / "SKILL.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: manual
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: high
                    ---

                    Load `core/governance/session-checklists.md` only when you want the shorter session-end runbook there.
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_setup_guidance_with_bootstrap_sequence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "HUMANS" / "setup" / "setup.sh",
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    {PROMPT_START_LINE}
                    {PROMPT_ROUTE_LINE}
                    {LIVE_CONFIG_LINE}
                    follow the bootstrap sequence
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("forbidden setup-guidance pattern" in error for error in result.errors)
            )

    def test_onboarding_export_template_with_stale_script_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "HUMANS" / "tooling" / "onboard-export-template.md",
                "# Onboarding Export\n\nRun `bash scripts/onboard-export.sh <file>`.\n",
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("forbidden onboarding-export pattern" in error for error in result.errors)
            )

    def test_quarantine_file_with_wrong_trust_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "knowledge" / "_unverified" / "suspect.md",
                textwrap.dedent(
                    """\
                    ---
                    source: external-research
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: medium
                    ---

                    # Suspect
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("quarantine file must have trust: low" in error for error in result.errors)
            )

    def test_quarantine_file_with_last_verified_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "knowledge" / "_unverified" / "suspect.md",
                textwrap.dedent(
                    """\
                    ---
                    source: external-research
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    last_verified: 2026-03-16
                    trust: low
                    ---

                    # Suspect
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any("quarantine file must omit last_verified" in error for error in result.errors)
            )

    def test_quarantine_file_with_correct_trust_and_source_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "knowledge" / "_unverified" / "legit.md",
                textwrap.dedent(
                    """\
                    ---
                    source: external-research
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    trust: low
                    ---

                    # Legit external content
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assert_no_non_coverage_warnings(result)

    def test_quarantine_file_with_wrong_source_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "knowledge" / "_unverified" / "odd-source.md",
                textwrap.dedent(
                    """\
                    ---
                    source: agent-inferred
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    trust: low
                    ---

                    # Odd source in quarantine
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertTrue(
                any(
                    "quarantine file expected source: external-research" in w
                    for w in result.warnings
                )
            )

    def test_system_note_quarantine_file_allows_agent_generated_source(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root
                / "core"
                / "memory"
                / "knowledge"
                / "_unverified"
                / "system-notes"
                / "incident.md",
                textwrap.dedent(
                    """\
                    ---
                    source: agent-generated
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    trust: low
                    ---

                    # Incident
                    """
                ),
            )

            result = validator.validate_repo(root)

            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertFalse(
                any(
                    "quarantine file expected source: external-research" in w
                    for w in result.warnings
                )
            )

    def test_brainstorm_quarantine_file_allows_agent_generated_source(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root
                / "core"
                / "memory"
                / "knowledge"
                / "_unverified"
                / "brainstorm-pwr-protocol.md",
                textwrap.dedent(
                    """\
                    ---
                    source: agent-generated
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    trust: low
                    ---

                    # Brainstorm
                    """
                ),
            )

            result = validator.validate_repo(root)

            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertFalse(
                any(
                    "quarantine file expected source: external-research" in w
                    for w in result.warnings
                )
            )

    def test_single_quoted_frontmatter_dates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "users" / "profile.md",
                textwrap.dedent(
                    """\
                    ---
                    source: 'user-stated'
                    origin_session: manual
                    created: '2026-03-16'
                    last_verified: '2026-03-16'
                    trust: high
                    ---

                    # Profile
                    """
                ),
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assert_no_non_coverage_warnings(result)

    def test_access_entry_with_path_traversal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "ACCESS.jsonl",
                '{"file":"../core/memory/users/profile.md","date":"2026-03-16","task":"test","helpfulness":0.7,"note":"used"}',
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "file must be a repo-relative path inside the memory repo" in error
                    for error in result.errors
                )
            )

    def test_access_entry_with_missing_live_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "ACCESS.jsonl",
                '{"file":"core/memory/skills/missing.md","date":"2026-03-16","task":"test","helpfulness":0.7,"note":"used"}',
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "file references missing target 'core/memory/skills/missing.md'" in error
                    for error in result.errors
                )
            )

    def test_access_archive_missing_target_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "ACCESS.archive.jsonl",
                '{"file":"core/memory/skills/missing.md","date":"2026-03-16","task":"test","helpfulness":0.7,"note":"used"}',
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertTrue(
                any(
                    "file references missing target 'core/memory/skills/missing.md'" in warning
                    for warning in result.warnings
                )
            )

    def test_access_entry_with_estimator_field_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root / "core" / "memory" / "skills" / "example.md",
                textwrap.dedent(
                    """\
                    ---
                    source: user-stated
                    origin_session: core/memory/activity/2026/03/16/chat-001
                    created: 2026-03-16
                    trust: high
                    ---

                    # Example
                    """
                ),
            )
            write(
                root / "core" / "memory" / "skills" / "ACCESS.jsonl",
                '{"file":"core/memory/skills/example.md","date":"2026-03-16","task":"test","helpfulness":0.7,"note":"used","estimator":"sidecar"}',
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assert_no_non_coverage_warnings(result)

    def test_chat_leaf_missing_reflection_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            (
                root
                / "core"
                / "memory"
                / "activity"
                / "2026"
                / "03"
                / "16"
                / "chat-001"
                / "reflection.md"
            ).unlink()
            write(
                root
                / "core"
                / "memory"
                / "activity"
                / "2026"
                / "03"
                / "16"
                / "chat-001"
                / "SUMMARY.md",
                "# Chat Summary\n\nSession notes.\n",
            )

            result = validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))
            self.assertTrue(
                any("missing session reflection note" in warning for warning in result.warnings)
            )

    def test_chat_leaf_summary_without_heading_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            build_minimal_repo(root)
            write(
                root
                / "core"
                / "memory"
                / "activity"
                / "2026"
                / "03"
                / "16"
                / "chat-001"
                / "SUMMARY.md",
                "# Chat Log\n\nSession notes.\n",
            )

            result = validator.validate_repo(root)
            self.assertTrue(
                any(
                    "chat leaf summaries must begin with '# Chat Summary'" in error
                    for error in result.errors
                )
            )

    def test_setup_copy_uses_quick_reference_routing_language(self) -> None:
        for path in (
            REPO_ROOT / "HUMANS" / "setup" / "setup.sh",
            REPO_ROOT / "HUMANS" / "views" / "setup.html",
            REPO_ROOT / "HUMANS" / "docs" / "QUICKSTART.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn(PROMPT_START_LINE, text)
            self.assertIn(PROMPT_ROUTE_LINE, text)
            self.assertIn(LIVE_CONFIG_LINE, text)

        self.assertNotIn(
            "start with README.md and follow its routing rules",
            (REPO_ROOT / "HUMANS" / "setup" / "setup.sh").read_text(encoding="utf-8"),
        )
        self.assertNotIn(
            "start with README.md and follow its routing rules",
            (REPO_ROOT / "HUMANS" / "views" / "setup.html").read_text(encoding="utf-8"),
        )
        self.assertNotIn(
            "follow the bootstrap sequence",
            (REPO_ROOT / "HUMANS" / "setup" / "setup.sh").read_text(encoding="utf-8"),
        )

    def test_adapter_files_point_to_quick_reference(self) -> None:
        for path in (
            REPO_ROOT / "AGENTS.md",
            REPO_ROOT / "CLAUDE.md",
            REPO_ROOT / ".cursorrules",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("core/INIT.md", text)
            self.assertIn(ADAPTER_ROUTING_LINE, text)
            self.assertNotIn("follow the bootstrap sequence and rules in README.md", text)

    def test_root_setup_entrypoints_exist_and_target_canonical_impl(self) -> None:
        wrapper = (REPO_ROOT / "setup.sh").read_text(encoding="utf-8")
        wrapper_html = (REPO_ROOT / "setup.html").read_text(encoding="utf-8")

        self.assertIn("HUMANS/setup/setup.sh", wrapper)
        self.assertIn("HUMANS/views/setup.html", wrapper_html)

    def test_browser_setup_copy_no_longer_claims_remote_parity(self) -> None:
        quickstart = (REPO_ROOT / "HUMANS" / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")
        setup_html = (REPO_ROOT / "HUMANS" / "views" / "setup.html").read_text(encoding="utf-8")

        self.assertIn("Git remote setup stays manual.", quickstart)
        self.assertIn("git remote setup stays manual", setup_html)
        self.assertNotIn("Either path walks you through three choices", quickstart)
        self.assertNotIn("follow the bootstrap sequence", quickstart)

    def test_onboarding_export_template_uses_canonical_import_command(self) -> None:
        text = (REPO_ROOT / "HUMANS" / "tooling" / "onboard-export-template.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("bash HUMANS/tooling/scripts/onboard-export.sh <file>", text)
        self.assertNotIn("bash scripts/onboard-export.sh <file>", text)

    def test_session_start_skill_defaults_to_quick_reference_and_uses_checklists_on_demand(
        self,
    ) -> None:
        text = (REPO_ROOT / "core" / "memory" / "skills" / "session-start" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "For normal returning sessions, follow the compact returning manifest in `core/INIT.md`",
            text,
        )
        self.assertIn("`core/memory/HOME.md` as the session entry point", text)
        self.assertIn(
            "Load `core/governance/session-checklists.md` only when you want more detail",
            text,
        )
        self.assertNotIn(
            "For normal returning sessions, the compact checklist in `core/governance/session-checklists.md` is sufficient",
            text,
        )

    def test_session_wrapup_skill_uses_on_demand_session_checklists_language(
        self,
    ) -> None:
        text = (REPO_ROOT / "core" / "memory" / "skills" / "session-wrapup" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Load `core/governance/session-checklists.md` only when you want",
            text,
        )
        self.assertIn("session-end runbook", text)
        self.assertNotIn(
            "For normal sessions, the compact checklist in `core/governance/session-checklists.md` is sufficient",
            text,
        )

    def test_quickstart_describes_template_backed_first_run_and_conditional_import_commit(
        self,
    ) -> None:
        text = (REPO_ROOT / "HUMANS" / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")

        self.assertIn(
            "rm -rf .git && git init --initial-branch=core",
            text,
        )
        self.assertIn(
            "rm -rf .git && git init && git symbolic-ref HEAD refs/heads/core",
            text,
        )
        self.assertIn(
            "fresh system (blank-slate or template-backed onboarding, with no recorded chat history yet)",
            text,
        )
        self.assertIn(
            "auto-commits the imported files when git author identity is configured",
            text,
        )
        self.assertIn(
            "stages them and prints the manual commit command",
            text,
        )

    def test_compact_manifest_excludes_readme_and_session_checklists(self) -> None:
        quick_reference = (REPO_ROOT / "core" / "INIT.md").read_text(encoding="utf-8")
        compact_row = validator.extract_manifest_row(quick_reference, "Compact returning")

        assert compact_row is not None
        self.assertNotIn("README.md", compact_row)
        self.assertNotIn("session-checklists", compact_row)
        self.assertIn("core/memory/HOME.md", compact_row)
        self.assertIn("core/memory/users/SUMMARY.md", compact_row)
        self.assertIn("core/memory/activity/SUMMARY.md", compact_row)
        self.assertIn("core/memory/working/projects/SUMMARY.md", compact_row)
        self.assertIn("core/memory/knowledge/SUMMARY.md", compact_row)
        self.assertIn("core/memory/skills/SUMMARY.md", compact_row)

    def test_context_budget_copy_uses_canonical_ranges(self) -> None:
        required_phrases = (
            "First-run onboarding bootstrap",
            "~15,000–20,000",
            "Returning compact session",
            "~3,000–7,000",
            "Full bootstrap / periodic review",
            "~18,000–25,000",
        )
        for path in (
            REPO_ROOT / "README.md",
            REPO_ROOT / "HUMANS" / "docs" / "QUICKSTART.md",
            REPO_ROOT / "core" / "INIT.md",
        ):
            text = path.read_text(encoding="utf-8")
            for phrase in required_phrases:
                self.assertIn(phrase, text)

    def test_seed_compact_context_budget_fits_published_upper_bound(self) -> None:
        compact_paths = [
            REPO_ROOT / "core" / "INIT.md",
            REPO_ROOT / "core" / "memory" / "users" / "SUMMARY.md",
            REPO_ROOT / "core" / "memory" / "working" / "projects" / "SUMMARY.md",
            REPO_ROOT / "core" / "memory" / "working" / "USER.md",
            REPO_ROOT / "core" / "memory" / "working" / "CURRENT.md",
        ]
        chats_summary = REPO_ROOT / "core" / "memory" / "activity" / "SUMMARY.md"
        chats_text = chats_summary.read_text(encoding="utf-8")
        if "*No conversations yet.*" not in chats_text:
            compact_paths.append(chats_summary)

        approx_tokens = round(
            sum(len(path.read_text(encoding="utf-8")) for path in compact_paths) / 4.0
        )
        self.assertLessEqual(approx_tokens, 7000)


if __name__ == "__main__":
    unittest.main()
