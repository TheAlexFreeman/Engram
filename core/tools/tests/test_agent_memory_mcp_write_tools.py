from __future__ import annotations

import asyncio
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, ClassVar, Coroutine, cast
from unittest.mock import patch

import time_machine
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
ToolCallable = Callable[..., Coroutine[Any, Any, str]]


def load_server_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("core.tools.agent_memory_mcp.server")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"agent_memory_mcp dependencies unavailable: {exc.name}") from exc


class AgentMemoryWriteToolTests(unittest.TestCase):
    server: ClassVar[ModuleType]
    errors: ClassVar[ModuleType]
    frontmatter_utils: ClassVar[Any]
    git_repo_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = load_server_module()
        cls.errors = importlib.import_module("core.tools.agent_memory_mcp.errors")
        cls.git_repo_module = importlib.import_module("core.tools.agent_memory_mcp.git_repo")
        try:
            cls.frontmatter_utils = importlib.import_module(
                "core.tools.agent_memory_mcp.frontmatter_utils"
            )
        except ModuleNotFoundError as exc:
            raise unittest.SkipTest(
                f"semantic write tool dependencies unavailable: {exc.name}"
            ) from exc

    def setUp(self) -> None:
        # Every test gets a fresh TemporaryDirectory; it's auto-deleted on teardown.
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _init_repo(
        self,
        files: dict[str, str],
        *,
        initial_commit_date: str | None = None,
    ) -> Path:
        temp_root = Path(self._tmpdir.name) / (f"repo_{id(files)}")
        temp_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=temp_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )

        for rel_path, content in files.items():
            target_rel_path = rel_path
            if rel_path.startswith("governance/"):
                target_rel_path = f"core/{rel_path}"
            elif rel_path.startswith("memory/"):
                target_rel_path = f"core/{rel_path}"
            target = temp_root / target_rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "add", "."], cwd=temp_root, check=True, capture_output=True, text=True
        )
        commit_env = None
        if initial_commit_date is not None:
            commit_env = {
                **os.environ,
                "GIT_AUTHOR_DATE": initial_commit_date,
                "GIT_COMMITTER_DATE": initial_commit_date,
            }
        subprocess.run(
            ["git", "commit", "-m", "seed"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
            env=commit_env,
        )
        content_root = temp_root / "core"
        return content_root if content_root.is_dir() else temp_root

    def _init_repo_with_file(self, rel_path: str) -> Path:
        return self._init_repo({rel_path: "# temp\n"})

    def _git_root(self, repo_root: Path) -> Path:
        git_root = repo_root if (repo_root / ".git").exists() else repo_root.parent
        return git_root

    def _repo_file_path(self, repo_root: Path, rel_path: str) -> Path:
        git_root = self._git_root(repo_root)
        if rel_path.startswith("core/"):
            return git_root / rel_path
        if rel_path.startswith(("memory/", "governance/")) and (git_root / "core").is_dir():
            return git_root / "core" / rel_path
        return git_root / rel_path

    def _assert_same_path(self, left: Path, right: Path) -> None:
        self.assertTrue(
            left.samefile(right),
            msg=f"Expected paths to reference the same location: {left!r} != {right!r}",
        )

    def _create_tools(
        self,
        repo_root: Path,
        delete_permission_hook=None,
        *,
        enable_raw_write_tools: bool = False,
    ) -> dict[str, ToolCallable]:
        _, tools, _, _ = self.server.create_mcp(
            repo_root=repo_root,
            delete_permission_hook=delete_permission_hook,
            enable_raw_write_tools=enable_raw_write_tools,
        )
        return cast(dict[str, ToolCallable], tools)

    def _preview_tool(
        self,
        tools: dict[str, ToolCallable],
        tool_name: str,
        *,
        preview_argument: str = "preview",
        **kwargs: Any,
    ) -> dict[str, Any]:
        preview_kwargs = dict(kwargs)
        preview_kwargs[preview_argument] = True
        return self._load_tool_payload(asyncio.run(tools[tool_name](**preview_kwargs)))

    def _load_tool_payload(self, raw: str) -> Any:
        payload = cast(dict[str, Any], json.loads(raw))
        if "_session" in payload and "result" in payload:
            return payload["result"]
        return payload

    def _approval_token_for(
        self,
        tools: dict[str, ToolCallable],
        tool_name: str,
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        preview = self._preview_tool(tools, tool_name, **kwargs)
        return cast(str, preview["new_state"]["approval_token"]), preview

    def _preview_token_for(
        self,
        tools: dict[str, ToolCallable],
        tool_name: str,
        *,
        preview_argument: str = "preview",
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        preview = self._preview_tool(
            tools,
            tool_name,
            preview_argument=preview_argument,
            **kwargs,
        )
        return cast(str, preview["new_state"]["preview_token"]), preview

    def _policy_contract_seed_files(self) -> dict[str, str]:
        return {
            "HUMANS/tooling/agent-memory-capabilities.toml": """version = 1
kind = \"agent-memory-capabilities\"

[tool_sets]
read_support = [\"memory_get_capabilities\", \"memory_get_policy_state\", \"memory_route_intent\"]
raw_fallback = [\"memory_write\"]
semantic_extensions = [\"memory_plan_create\", \"memory_plan_execute\", \"memory_promote_knowledge\", \"memory_update_skill\", \"memory_log_access\"]
declared_gaps = []

[change_classes.automatic]
approval = \"none\"
user_awareness = \"not_required\"
ui_affordance = \"apply_and_report\"
read_only_behavior = \"defer_and_emit_summary\"

[change_classes.proposed]
approval = \"explicit_user_awareness\"
user_awareness = \"required_before_write\"
ui_affordance = \"preview_and_wait\"
read_only_behavior = \"defer_and_queue_review_or_summary\"

[change_classes.protected]
approval = \"explicit_user_approval\"
user_awareness = \"required_before_write\"
ui_affordance = \"block_until_approved\"
read_only_behavior = \"defer_and_report_blocked\"

[raw_fallback_policy]
preview_required_for = [\"proposed\", \"protected\"]

[fallback_behavior.uninterpretable_target]
result = \"defer_with_contract_warning\"

[fallback_behavior.preview_only]
result = \"return_preview_without_writing\"

[fallback_behavior.read_only]
result = \"return_deferred_action_summary\"

[desktop_operations.create_plan]
status = \"implemented\"
tool = \"memory_plan_create\"
tier = \"semantic\"
operation_group = \"plan\"
change_class = \"proposed\"
preview_support = true
preview_mode = "preview"
preview_argument = "preview"

[desktop_operations.execute_plan]
status = \"implemented\"
tool = \"memory_plan_execute\"
tier = \"semantic\"
operation_group = \"plan\"
change_class = \"proposed\"
preview_support = true
preview_mode = "preview"
preview_argument = "preview"

[desktop_operations.promote_knowledge]
status = \"implemented\"
tool = \"memory_promote_knowledge\"
tier = \"semantic\"
operation_group = \"knowledge\"
change_class = \"proposed\"
preview_support = true
preview_mode = "preview"
preview_argument = "preview"

[desktop_operations.append_access_entry]
status = \"implemented\"
tool = \"memory_log_access\"
tier = \"semantic\"
operation_group = \"chat\"
change_class = \"automatic\"

[desktop_operations.update_skill]
status = \"implemented\"
tool = \"memory_update_skill\"
tier = \"semantic\"
operation_group = \"skill\"
change_class = \"protected\"
notes = \"Protected governed path for skill updates.\"
preview_support = true
preview_mode = "preview"
preview_argument = "preview"
""",
            "core/governance/update-guidelines.md": """## Proposed changes (require user awareness)

- Adding, modifying, or removing files in `memory/users/`.

## Protected changes (require explicit approval)

- Creating, modifying, or removing files in `memory/skills/`.
- Any modification to files in `governance/`.
- Any modification to `README.md`.
""",
            "core/governance/curation-policy.md": """## Trust-weighted retrieval

- Trust: low — Inform only; never instruct.
""",
        }

    def test_create_mcp_accepts_git_subdirectory_root(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/README.md": "# Knowledge\n",
                "memory/knowledge/topic/note.md": "# Note\n",
            }
        )
        _, tools, resolved_root, repo = self.server.create_mcp(
            repo_root=repo_root / "memory" / "knowledge",
            enable_raw_write_tools=True,
        )

        self._assert_same_path(resolved_root, repo_root.parent)
        self._assert_same_path(repo.root, repo_root.parent)
        payload = self._load_tool_payload(
            asyncio.run(tools["memory_read_file"](path="memory/knowledge/topic/note.md"))
        )
        self.assertTrue(payload["inline"])
        self.assertIn("# Note", payload["content"])

    def test_memory_read_file_returns_pagination_metadata_on_full_read(self) -> None:
        body = "A" * 20_100
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/large.md": f"---\ncreated: 2026-03-20\nsource: test\ntrust: medium\n---\n\n{body}",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_read_file"](path="memory/knowledge/topic/large.md"))
        )

        # New behavior: inline by default (threshold raised to 64 KB), content
        # present, pagination metadata populated, no temp_file.
        self.assertEqual(payload["path"], "memory/knowledge/topic/large.md")
        self.assertTrue(payload["inline"])
        self.assertGreater(payload["size_bytes"], 20_000)
        self.assertEqual(payload["total_bytes"], payload["size_bytes"])
        self.assertEqual(payload["offset_bytes"], 0)
        self.assertEqual(payload["returned_bytes"], payload["size_bytes"])
        self.assertFalse(payload["has_more"])
        self.assertIsNone(payload["next_call_hint"])
        self.assertIn("content", payload)
        self.assertNotIn("temp_file", payload)

    def test_memory_read_file_paginates_when_limit_bytes_is_set(self) -> None:
        body = "A" * 200_000
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/oversize.md": body,
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_read_file"](
                    path="memory/knowledge/topic/oversize.md", limit_bytes=50_000
                )
            )
        )

        self.assertTrue(payload["inline"])
        self.assertEqual(payload["total_bytes"], 200_000)
        self.assertEqual(payload["offset_bytes"], 0)
        self.assertEqual(payload["returned_bytes"], 50_000)
        self.assertTrue(payload["has_more"])
        self.assertEqual(payload["next_call_hint"], {"offset_bytes": 50_000, "limit_bytes": 50_000})
        # Paginated reads do not populate frontmatter — slice may not cover it.
        self.assertIsNone(payload["frontmatter"])
        self.assertEqual(len(payload["content"]), 50_000)

        # Follow-up paginated call using next_call_hint finishes the file.
        follow_up = self._load_tool_payload(
            asyncio.run(
                tools["memory_read_file"](
                    path="memory/knowledge/topic/oversize.md",
                    offset_bytes=payload["next_call_hint"]["offset_bytes"],
                    limit_bytes=payload["next_call_hint"]["limit_bytes"] * 4,
                )
            )
        )
        self.assertEqual(follow_up["offset_bytes"], 50_000)
        self.assertEqual(follow_up["returned_bytes"], 150_000)
        self.assertFalse(follow_up["has_more"])
        self.assertIsNone(follow_up["next_call_hint"])

    def test_memory_read_file_prefer_temp_file_returns_temp_path(self) -> None:
        body = "B" * 80_000
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/huge.md": body,
            }
        )
        tools = self._create_tools(repo_root)

        old_val = os.environ.pop("AGENT_MEMORY_CROSS_FILESYSTEM", None)
        try:
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_read_file"](
                        path="memory/knowledge/topic/huge.md", prefer_temp_file=True
                    )
                )
            )
        finally:
            if old_val is not None:
                os.environ["AGENT_MEMORY_CROSS_FILESYSTEM"] = old_val

        self.assertTrue(payload["inline"])
        self.assertIn("temp_file", payload)
        temp_path = Path(payload["temp_file"])
        try:
            self.assertTrue(temp_path.exists())
            self.assertEqual(temp_path.read_bytes(), body.encode("utf-8"))
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    def test_memory_read_file_suppresses_temp_file_when_cross_filesystem(self) -> None:
        body = "C" * 80_000
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/cross-fs.md": body,
            }
        )
        tools = self._create_tools(repo_root)

        old_val = os.environ.get("AGENT_MEMORY_CROSS_FILESYSTEM")
        os.environ["AGENT_MEMORY_CROSS_FILESYSTEM"] = "1"
        try:
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_read_file"](
                        path="memory/knowledge/topic/cross-fs.md", prefer_temp_file=True
                    )
                )
            )
        finally:
            if old_val is None:
                os.environ.pop("AGENT_MEMORY_CROSS_FILESYSTEM", None)
            else:
                os.environ["AGENT_MEMORY_CROSS_FILESYSTEM"] = old_val

        self.assertTrue(payload["inline"])
        self.assertNotIn("temp_file", payload)

    def test_memory_read_file_rejects_invalid_pagination_args(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/small.md": "hello",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_read_file"](path="memory/knowledge/topic/small.md", offset_bytes=-1)
            )
        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_read_file"](path="memory/knowledge/topic/small.md", limit_bytes=0)
            )
        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_read_file"](
                    path="memory/knowledge/topic/small.md", limit_bytes=10_000_000
                )
            )

    def test_memory_list_folder_preview_returns_frontmatter_and_preview_for_markdown(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/note.md": """---
title: Preview Note
source: agent-generated
created: 2026-03-20
trust: low
---

This is the preview body for the markdown note.
""",
                "memory/knowledge/topic/plain.txt": "plain text file\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_list_folder"](path="memory/knowledge/topic", preview_chars=20)
            )
        )

        note_entry = next(entry for entry in payload["entries"] if entry["name"] == "note.md")
        text_entry = next(entry for entry in payload["entries"] if entry["name"] == "plain.txt")

        self.assertEqual(payload["path"], "memory/knowledge/topic")
        self.assertEqual(payload["preview_chars"], 20)
        self.assertEqual(note_entry["frontmatter"]["title"], "Preview Note")
        self.assertEqual(note_entry["preview"], "This is the preview")
        self.assertNotIn("preview", text_entry)

    def test_memory_list_folder_default_output_omits_preview_fields(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/note.md": "# Note\n",
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(tools["memory_list_folder"](path="memory/knowledge/topic"))

        self.assertIn("📄 note.md", output)
        self.assertNotIn('"preview"', output)

    def test_memory_review_unverified_groups_files_and_flags_expired_entries(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/math/chaos.md": """---
source: external-research
created: 2025-01-01
trust: low
---

Chaos theory studies sensitive dependence on initial conditions in nonlinear systems.
""",
                "memory/knowledge/_unverified/philosophy/mind.md": """---
source: agent-generated
created: 2026-03-10
trust: medium
---

Philosophy of mind studies consciousness intentionality and representation.
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_review_unverified"](
                    folder_path="memory/knowledge/_unverified",
                    max_extract_words=5,
                )
            )
        )

        math_entry = payload["groups"]["math"][0]
        philosophy_entry = payload["groups"]["philosophy"][0]

        self.assertEqual(payload["total_files"], 2)
        self.assertEqual(payload["expired_count"], 1)
        self.assertEqual(payload["trust_counts"]["low"], 1)
        self.assertEqual(payload["trust_counts"]["medium"], 1)
        self.assertTrue(math_entry["expired"])
        self.assertFalse(philosophy_entry["expired"])
        self.assertEqual(
            math_entry["extract"],
            "Chaos theory studies sensitive dependence",
        )

    def _write_and_commit(
        self,
        repo_root: Path,
        files: dict[str, str],
        message: str,
        *,
        commit_date: str | None = None,
    ) -> str:
        for rel_path, content in files.items():
            target = self._repo_file_path(repo_root, rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "add", "."],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
            env=(
                {
                    **os.environ,
                    "GIT_AUTHOR_DATE": commit_date,
                    "GIT_COMMITTER_DATE": commit_date,
                }
                if commit_date is not None
                else None
            ),
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _init_host_repo(
        self, files: dict[str, str], *, initial_commit_date: str | None = None
    ) -> Path:
        temp_root = Path(self._tmpdir.name) / (f"host_{id(files)}")
        temp_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=temp_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "Host User"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "host@example.com"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        for rel_path, content in files.items():
            target = temp_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "add", "."], cwd=temp_root, check=True, capture_output=True, text=True
        )
        commit_env = None
        if initial_commit_date is not None:
            commit_env = {
                **os.environ,
                "GIT_AUTHOR_DATE": initial_commit_date,
                "GIT_COMMITTER_DATE": initial_commit_date,
            }
        subprocess.run(
            ["git", "commit", "-m", "host seed"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
            env=commit_env,
        )
        return temp_root

    def test_memory_delete_uses_permission_hook_for_allowed_paths(self) -> None:
        repo_root = self._init_repo_with_file("memory/working/projects/delete-me.md")
        calls: list[str] = []

        def hook(path: str) -> None:
            calls.append(path)

        _, tools, _, _ = self.server.create_mcp(
            repo_root=repo_root,
            delete_permission_hook=hook,
            enable_raw_write_tools=True,
        )

        asyncio.run(tools["memory_delete"](path="memory/working/projects/delete-me.md"))

        self.assertEqual(calls, ["memory/working/projects/delete-me.md"])
        self.assertFalse((repo_root / "memory" / "working" / "projects" / "delete-me.md").exists())
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn("D\tcore/memory/working/projects/delete-me.md", staged)

    def test_memory_delete_blocks_when_permission_hook_rejects(self) -> None:
        repo_root = self._init_repo_with_file("memory/working/notes/delete-me.md")

        def hook(path: str) -> None:
            raise RuntimeError(f"blocked {path}")

        _, tools, _, _ = self.server.create_mcp(
            repo_root=repo_root,
            delete_permission_hook=hook,
            enable_raw_write_tools=True,
        )

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(tools["memory_delete"](path="memory/working/notes/delete-me.md"))

        self.assertTrue((repo_root / "memory" / "working" / "notes" / "delete-me.md").exists())

    def test_memory_plan_execute_completes_phase_and_updates_navigation(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": """---
type: projects-navigator
generated: 2026-03-21
project_count: 1
---

# Projects

_No active or ongoing projects._
""",
                "memory/working/projects/example/SUMMARY.md": """---
source: agent-generated
origin_session: manual
created: 2026-03-21
trust: medium
type: project
status: active
cognitive_mode: exploration
open_questions: 0
active_plans: 1
last_activity: 2026-03-21
current_focus: Ship the first project milestone.
---

# Project: Example
""",
                "memory/working/projects/example/plans/test-plan.yaml": "id: test-plan\nproject: example\ncreated: 2026-03-17\norigin_session: memory/activity/2026/03/17/chat-001\nstatus: active\npurpose:\n  summary: Test plan\n  context: Validate structured plan execution.\n  questions: []\nwork:\n  phases:\n    - id: phase-a\n      title: Do first step\n      status: pending\n      commit: null\n      blockers: []\n      changes:\n        - path: memory/working/projects/example/notes/first.md\n          action: create\n          description: Create the first artifact.\n    - id: phase-b\n      title: Do second step\n      status: pending\n      commit: null\n      blockers: []\n      changes:\n        - path: memory/working/projects/example/notes/second.md\n          action: create\n          description: Create the second artifact.\nreview: null\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="test-plan",
                project_id="example",
                phase_id="phase-a",
                action="complete",
                session_id="memory/activity/2026/03/19/chat-001",
                commit_sha="abc1234",
            )
        )
        payload = self._load_tool_payload(raw)
        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "test-plan.yaml"
            ).read_text(encoding="utf-8")
        )
        project_frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory" / "working" / "projects" / "example" / "SUMMARY.md"
        )
        summary = (repo_root / "memory" / "working" / "projects" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["new_state"]["next_action"]["title"], "Do second step")
        self.assertEqual(payload["new_state"]["next_action"]["id"], "phase-b")
        self.assertEqual(payload["new_state"]["plan_progress"], [1, 2])
        self.assertEqual(plan_body["work"]["phases"][0]["status"], "completed")
        self.assertEqual(plan_body["work"]["phases"][0]["commit"], "abc1234")
        self.assertEqual(project_frontmatter["active_plans"], 1)
        self.assertIn(
            "| example | active | exploration | 0 | Ship the first project milestone. |", summary
        )

    def test_promote_knowledge_updates_frontmatter_and_both_summaries(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/literature/test-note.md": """---
title: Test Note
source: agent-generated
created: 2026-03-17
last_verified: 2026-03-17
trust: low
origin_session: manual
---

# Test Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: literature -->
### Literature
- **[test-note.md](memory/knowledge/_unverified/literature/test-note.md)** — Test Note

---
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: literature -->
### Literature

---
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_promote_knowledge"](
                source_path="memory/knowledge/_unverified/literature/test-note.md",
                trust_level="high",
            )
        )
        payload = self._load_tool_payload(raw)
        target_path = repo_root / "memory" / "knowledge" / "literature" / "test-note.md"
        old_path = (
            repo_root / "memory" / "knowledge" / "_unverified" / "literature" / "test-note.md"
        )
        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(target_path)
        unverified_summary = (
            repo_root / "memory" / "knowledge" / "_unverified" / "SUMMARY.md"
        ).read_text(encoding="utf-8")
        verified_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            payload["new_state"]["new_path"], "memory/knowledge/literature/test-note.md"
        )
        self.assertEqual(payload["new_state"]["trust"], "high")
        self.assertFalse(old_path.exists())
        self.assertTrue(target_path.exists())
        self.assertEqual(frontmatter["trust"], "high")
        self.assertEqual(str(frontmatter["last_verified"]), str(date.today()))
        self.assertNotIn("memory/knowledge/_unverified/literature/test-note.md", unverified_summary)
        self.assertIn("memory/knowledge/literature/test-note.md", verified_summary)

    def test_promote_knowledge_with_summary_entry_creates_missing_target_section(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mathematics/test-note.md": """---
title: Test Note
source: agent-generated
created: 2026-03-17
last_verified: 2026-03-17
trust: low
origin_session: manual
---

# Test Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: mathematics -->
### Mathematics
- **[test-note.md](memory/knowledge/_unverified/mathematics/test-note.md)** — Test Note

---
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: literature -->
### Literature

---
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge"](
                    source_path="memory/knowledge/_unverified/mathematics/test-note.md",
                    trust_level="high",
                    summary_entry="- [test-note.md](memory/knowledge/mathematics/test-note.md) — Custom summary entry",
                )
            )
        )

        verified_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["warnings"], [])
        self.assertIn("<!-- section: mathematics -->", verified_summary)
        self.assertIn("### Mathematics", verified_summary)
        self.assertIn(
            "- [test-note.md](memory/knowledge/mathematics/test-note.md) — Custom summary entry",
            verified_summary,
        )

    def test_promote_knowledge_rejects_target_path_outside_knowledge_surface(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/literature/test-note.md": """---
title: Test Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Test Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_promote_knowledge"](
                    source_path="memory/knowledge/_unverified/literature/test-note.md",
                    trust_level="medium",
                    target_path="memory/users/test-note.md",
                )
            )

        self.assertTrue(
            (repo_root / "memory/knowledge/_unverified/literature/test-note.md").exists()
        )
        self.assertFalse((repo_root / "memory/users/test-note.md").exists())

    def test_promote_knowledge_batch_single_file_matches_single_promotion_behavior(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/literature/test-note.md": """---
title: Test Note
source: agent-generated
created: 2026-03-17
last_verified: 2026-03-17
trust: low
origin_session: manual
---

# Test Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: literature -->
### Literature
- **[test-note.md](memory/knowledge/_unverified/literature/test-note.md)** — Test Note

---
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: literature -->
### Literature

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge_batch"](
                    source_paths='["memory/knowledge/_unverified/literature/test-note.md"]',
                    trust_level="high",
                )
            )
        )

        target_path = repo_root / "memory" / "knowledge" / "literature" / "test-note.md"
        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(target_path)
        verified_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["new_state"]["promoted_count"], 1)
        self.assertEqual(payload["new_state"]["target_folder"], "memory/knowledge/literature")
        self.assertEqual(payload["new_state"]["trust"], "high")
        self.assertEqual(payload["new_state"]["promoted_files"], ["test-note.md"])
        self.assertIn("memory/knowledge/SUMMARY.md", payload["new_state"]["summary_updates"])
        self.assertEqual(frontmatter["trust"], "high")
        self.assertEqual(str(frontmatter["last_verified"]), str(date.today()))
        self.assertIn("memory/knowledge/literature/test-note.md", verified_summary)

    def test_promote_knowledge_batch_creates_missing_target_section(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mathematics/test-note.md": """---
title: Test Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Test Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: mathematics -->
### Mathematics
- **[test-note.md](memory/knowledge/_unverified/mathematics/test-note.md)** — Test Note

---
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: literature -->
### Literature

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge_batch"](
                    source_paths='["memory/knowledge/_unverified/mathematics/test-note.md"]',
                    trust_level="high",
                )
            )
        )

        verified_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["warnings"], [])
        self.assertIn("<!-- section: mathematics -->", verified_summary)
        self.assertIn("### Mathematics", verified_summary)
        self.assertIn("memory/knowledge/mathematics/test-note.md", verified_summary)

    def test_promote_knowledge_batch_folder_expansion_promotes_multiple_files(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mcp/a-note.md": """---
title: A Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# A Note
""",
                "memory/knowledge/_unverified/mcp/b-note.md": """---
title: B Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# B Note
""",
                "memory/knowledge/_unverified/mcp/SUMMARY.md": "# MCP folder\n",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: mcp -->
### MCP
- **[a-note.md](memory/knowledge/_unverified/mcp/a-note.md)** — A Note
- **[b-note.md](memory/knowledge/_unverified/mcp/b-note.md)** — B Note

---
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: tooling -->
### Tooling

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge_batch"](
                    source_paths="memory/knowledge/_unverified/mcp/",
                    trust_level="medium",
                    target_folder="memory/knowledge/tooling",
                )
            )
        )

        self.assertEqual(payload["new_state"]["promoted_count"], 2)
        self.assertEqual(payload["new_state"]["target_folder"], "memory/knowledge/tooling")
        self.assertTrue((repo_root / "memory" / "knowledge" / "tooling" / "a-note.md").exists())
        self.assertTrue((repo_root / "memory" / "knowledge" / "tooling" / "b-note.md").exists())
        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "_unverified" / "mcp" / "a-note.md").exists()
        )
        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "_unverified" / "mcp" / "b-note.md").exists()
        )

    def test_promote_knowledge_batch_validation_failure_rejects_entire_batch(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/literature/test-note.md": """---
title: Test Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Test Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_promote_knowledge_batch"](
                    source_paths='["memory/knowledge/_unverified/literature/test-note.md", "memory/working/projects/test-plan.md"]',
                    trust_level="medium",
                )
            )

        self.assertTrue(
            (
                repo_root / "memory" / "knowledge" / "_unverified" / "literature" / "test-note.md"
            ).exists()
        )
        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "literature" / "test-note.md").exists()
        )

    def test_promote_knowledge_batch_rejects_target_folder_outside_knowledge_surface(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/literature/test-note.md": """---
title: Test Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Test Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_promote_knowledge_batch"](
                    source_paths='["memory/knowledge/_unverified/literature/test-note.md"]',
                    trust_level="medium",
                    target_folder="memory/users",
                )
            )

        self.assertTrue(
            (repo_root / "memory/knowledge/_unverified/literature/test-note.md").exists()
        )
        self.assertFalse((repo_root / "memory/users/test-note.md").exists())

    def test_promote_knowledge_batch_rejects_oversized_batch(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/literature/test-note.md": "# Test\n",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root)

        oversized = json.dumps(
            ["memory/knowledge/_unverified/literature/test-note.md" for _ in range(51)]
        )
        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_promote_knowledge_batch"](
                    source_paths=oversized,
                    trust_level="medium",
                )
            )

    def test_promote_knowledge_subtree_dry_run_reports_moves_without_changes(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mcp/a-note.md": """---
title: A Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# A Note
""",
                "memory/knowledge/_unverified/mcp/nested/b-note.md": """---
title: B Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# B Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root)

        before_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge_subtree"](
                    source_folder="memory/knowledge/_unverified/mcp",
                    dest_folder="memory/knowledge/tooling",
                    trust_level="medium",
                    dry_run=True,
                )
            )
        )

        after_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertTrue(payload["new_state"]["dry_run"])
        self.assertEqual(payload["new_state"]["promoted_count"], 2)
        self.assertIn("preview_token", payload["new_state"])
        self.assertEqual(before_count, after_count)
        self.assertEqual(status, "")
        self.assertTrue(
            (repo_root / "memory" / "knowledge" / "_unverified" / "mcp" / "a-note.md").exists()
        )
        self.assertFalse((repo_root / "memory" / "knowledge" / "tooling" / "a-note.md").exists())
        self.assertIn(
            {
                "source_path": "memory/knowledge/_unverified/mcp/nested/b-note.md",
                "target_path": "memory/knowledge/tooling/nested/b-note.md",
            },
            payload["new_state"]["planned_moves"],
        )

    def test_promote_knowledge_subtree_moves_nested_files_in_single_commit(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mcp/a-note.md": """---
title: A Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# A Note
""",
                "memory/knowledge/_unverified/mcp/nested/b-note.md": """---
title: B Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# B Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: mcp -->
### MCP
- **[a-note.md](memory/knowledge/_unverified/mcp/a-note.md)** — A Note
- **[b-note.md](memory/knowledge/_unverified/mcp/nested/b-note.md)** — B Note

---
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: tooling -->
### Tooling

---
""",
            }
        )
        tools = self._create_tools(repo_root)
        preview_token, _ = self._preview_token_for(
            tools,
            "memory_promote_knowledge_subtree",
            preview_argument="dry_run",
            source_folder="memory/knowledge/_unverified/mcp",
            dest_folder="memory/knowledge/tooling",
            trust_level="medium",
        )

        before_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge_subtree"](
                    source_folder="memory/knowledge/_unverified/mcp",
                    dest_folder="memory/knowledge/tooling",
                    trust_level="medium",
                    preview_token=preview_token,
                )
            )
        )

        after_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        verified_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        target_path = repo_root / "memory" / "knowledge" / "tooling" / "nested" / "b-note.md"
        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(target_path)

        self.assertEqual(after_count, before_count + 1)
        self.assertEqual(payload["new_state"]["promoted_count"], 2)
        self.assertEqual(payload["new_state"]["target_folder"], "memory/knowledge/tooling")
        self.assertTrue((repo_root / "memory" / "knowledge" / "tooling" / "a-note.md").exists())
        self.assertTrue(target_path.exists())
        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "_unverified" / "mcp" / "a-note.md").exists()
        )
        self.assertEqual(frontmatter["trust"], "medium")
        self.assertEqual(str(frontmatter["last_verified"]), str(date.today()))
        self.assertIn("memory/knowledge/tooling/a-note.md", verified_summary)
        self.assertIn("memory/knowledge/tooling/nested/b-note.md", verified_summary)

    def test_promote_knowledge_subtree_creates_missing_target_section(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mcp/a-note.md": """---
title: A Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# A Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: mcp -->
### MCP
- **[a-note.md](memory/knowledge/_unverified/mcp/a-note.md)** — A Note

---
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: literature -->
### Literature

---
""",
            }
        )
        tools = self._create_tools(repo_root)
        preview_token, _ = self._preview_token_for(
            tools,
            "memory_promote_knowledge_subtree",
            preview_argument="dry_run",
            source_folder="memory/knowledge/_unverified/mcp",
            dest_folder="memory/knowledge/tooling",
            trust_level="medium",
        )

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge_subtree"](
                    source_folder="memory/knowledge/_unverified/mcp",
                    dest_folder="memory/knowledge/tooling",
                    trust_level="medium",
                    preview_token=preview_token,
                )
            )
        )

        verified_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["warnings"], [])
        self.assertIn("<!-- section: tooling -->", verified_summary)
        self.assertIn("### Tooling", verified_summary)
        self.assertIn("memory/knowledge/tooling/a-note.md", verified_summary)

    def test_promote_knowledge_subtree_warns_missing_source_section_as_non_actionable(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mcp/a-note.md": """---
title: A Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# A Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: tooling -->
### Tooling

---
""",
            }
        )
        tools = self._create_tools(repo_root)
        preview_token, _ = self._preview_token_for(
            tools,
            "memory_promote_knowledge_subtree",
            preview_argument="dry_run",
            source_folder="memory/knowledge/_unverified/mcp",
            dest_folder="memory/knowledge/tooling",
            trust_level="medium",
        )

        payload = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge_subtree"](
                    source_folder="memory/knowledge/_unverified/mcp",
                    dest_folder="memory/knowledge/tooling",
                    trust_level="medium",
                    preview_token=preview_token,
                )
            )
        )

        self.assertEqual(payload["new_state"]["promoted_count"], 1)
        self.assertIn("No action required", payload["warnings"][0])

    def test_promote_knowledge_subtree_rejects_dest_folder_outside_knowledge_surface(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/mcp/a-note.md": """---
title: A Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# A Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_promote_knowledge_subtree"](
                    source_folder="memory/knowledge/_unverified/mcp",
                    dest_folder="memory/skills",
                    trust_level="medium",
                )
            )

        self.assertTrue((repo_root / "memory/knowledge/_unverified/mcp/a-note.md").exists())
        self.assertFalse((repo_root / "memory/skills/a-note.md").exists())

    def test_memory_mark_reviewed_appends_jsonl_entry(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/topic/note.md": """---
title: Note
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Note
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(
            asyncio.run(
                tools["memory_mark_reviewed"](
                    path="memory/knowledge/_unverified/topic/note.md",
                    verdict="approve",
                    reviewer_notes="Looks good.",
                    session_id="memory/activity/2026/03/20/chat-003",
                )
            )
        )
        log_path = repo_root / "memory" / "knowledge" / "_unverified" / "REVIEW_LOG.jsonl"
        log_lines = [
            line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        entry = json.loads(log_lines[-1])

        self.assertEqual(payload["new_state"]["verdict"], "approve")
        self.assertEqual(entry["path"], "memory/knowledge/_unverified/topic/note.md")
        self.assertEqual(entry["verdict"], "approve")
        self.assertEqual(entry["reviewer_notes"], "Looks good.")
        self.assertEqual(entry["session_id"], "memory/activity/2026/03/20/chat-003")
        self.assertEqual(entry["reviewed_by"], "agent")
        self.assertTrue(entry["timestamp"].endswith("Z"))

    def test_memory_list_pending_reviews_uses_latest_verdict_per_file(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/topic/alpha.md": """---
title: Alpha
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Alpha
""",
                "memory/knowledge/_unverified/topic/beta.md": """---
title: Beta
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Beta
""",
            }
        )
        tools = self._create_tools(repo_root)

        asyncio.run(
            tools["memory_mark_reviewed"](
                path="memory/knowledge/_unverified/topic/alpha.md",
                verdict="approve",
            )
        )
        asyncio.run(
            tools["memory_mark_reviewed"](
                path="memory/knowledge/_unverified/topic/alpha.md",
                verdict="defer",
                reviewer_notes="Need another pass.",
            )
        )
        asyncio.run(
            tools["memory_mark_reviewed"](
                path="memory/knowledge/_unverified/topic/beta.md",
                verdict="reject",
            )
        )

        payload = json.loads(asyncio.run(tools["memory_list_pending_reviews"]()))

        self.assertEqual(payload["counts"]["approve"], 0)
        self.assertEqual(payload["counts"]["defer"], 1)
        self.assertEqual(payload["counts"]["reject"], 1)
        self.assertEqual(payload["defer"][0]["path"], "memory/knowledge/_unverified/topic/alpha.md")
        self.assertEqual(payload["defer"][0]["reviewer_notes"], "Need another pass.")
        self.assertEqual(payload["reject"][0]["path"], "memory/knowledge/_unverified/topic/beta.md")

    def test_memory_list_pending_reviews_skips_files_no_longer_in_unverified(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/topic/keep.md": """---
title: Keep
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Keep
""",
                "memory/knowledge/_unverified/topic/promote.md": """---
title: Promote
source: agent-generated
created: 2026-03-17
trust: low
origin_session: manual
---

# Promote
""",
                "memory/knowledge/_unverified/SUMMARY.md": "# Unverified Knowledge\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root)

        asyncio.run(
            tools["memory_mark_reviewed"](
                path="memory/knowledge/_unverified/topic/keep.md",
                verdict="defer",
            )
        )
        asyncio.run(
            tools["memory_mark_reviewed"](
                path="memory/knowledge/_unverified/topic/promote.md",
                verdict="approve",
            )
        )
        asyncio.run(
            tools["memory_promote_knowledge"](
                source_path="memory/knowledge/_unverified/topic/promote.md",
                trust_level="high",
                target_path="memory/knowledge/topic/promote.md",
            )
        )

        payload = json.loads(asyncio.run(tools["memory_list_pending_reviews"]()))

        self.assertEqual(payload["counts"]["approve"], 0)
        self.assertEqual(payload["counts"]["defer"], 1)
        self.assertEqual(payload["defer"][0]["path"], "memory/knowledge/_unverified/topic/keep.md")

    def test_memory_delete_blocks_protected_identity_paths(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
created: 2026-03-17
last_verified: 2026-03-17
trust: high
---

# Profile
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(tools["memory_delete"](path="memory/users/profile.md"))

        self.assertTrue((repo_root / "memory" / "users" / "profile.md").exists())

    def test_memory_plan_execute_complete_requires_commit_sha(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": """---
type: projects-navigator
generated: 2026-03-21
project_count: 1
---

# Projects

_No active or ongoing projects._
""",
                "memory/working/projects/example/SUMMARY.md": """---
source: agent-generated
origin_session: manual
created: 2026-03-21
trust: medium
type: project
status: active
cognitive_mode: exploration
open_questions: 0
active_plans: 1
last_activity: 2026-03-21
current_focus: Example project.
---

# Project: Example
""",
                "memory/working/projects/example/plans/test-plan.yaml": "id: test-plan\nproject: example\ncreated: 2026-03-17\norigin_session: memory/activity/2026/03/17/chat-001\nstatus: active\npurpose:\n  summary: Test plan\n  context: Validate completion guardrails.\n  questions: []\nwork:\n  phases:\n    - id: phase-a\n      title: Original next action\n      status: in-progress\n      commit: null\n      blockers: []\n      changes:\n        - path: memory/working/projects/example/notes/first.md\n          action: create\n          description: Create the first artifact.\nreview: null\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_plan_execute"](
                    plan_id="test-plan",
                    project_id="example",
                    phase_id="phase-a",
                    action="complete",
                    session_id="memory/activity/2026/03/19/chat-001",
                )
            )

    def test_raw_write_tools_are_disabled_by_default(self) -> None:
        repo_root = self._init_repo_with_file("memory/working/projects/delete-me.md")
        tools = self._create_tools(repo_root)

        self.assertNotIn("memory_delete", tools)
        self.assertNotIn("memory_move", tools)
        self.assertIn("memory_plan_execute", tools)

    def test_raw_write_tools_can_be_enabled_explicitly(self) -> None:
        repo_root = self._init_repo_with_file("memory/working/projects/delete-me.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        self.assertIn("memory_delete", tools)
        self.assertIn("memory_move", tools)
        self.assertIn("memory_update_frontmatter_bulk", tools)

    def test_memory_update_frontmatter_bulk_stages_single_file_with_version_token(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/test-plan.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
status: active
next_action: Ship it
last_verified: 2026-03-17
---

# Test Plan
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        read_payload = self._load_tool_payload(
            asyncio.run(tools["memory_read_file"](path="memory/working/projects/test-plan.md"))
        )
        payload = json.loads(
            asyncio.run(
                tools["memory_update_frontmatter_bulk"](
                    updates=[
                        {
                            "path": "memory/working/projects/test-plan.md",
                            "fields": {"status": "complete"},
                            "version_token": read_payload["version_token"],
                        }
                    ]
                )
            )
        )

        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory/working/projects/test-plan.md"
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()

        self.assertEqual(payload["files_changed"], ["memory/working/projects/test-plan.md"])
        self.assertEqual(payload["new_state"]["updated_count"], 1)
        self.assertEqual(payload["new_state"]["skipped_count"], 0)
        self.assertEqual(payload["new_state"]["transaction_state"], "staged")
        self.assertEqual(frontmatter["status"], "complete")
        self.assertIn("core/memory/working/projects/test-plan.md", staged)

    def test_memory_update_frontmatter_bulk_stages_multiple_files_and_commit_finalizes(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/one.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
status: active
---

# One
""",
                "memory/working/projects/two.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
status: active
---

# Two
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        payload = json.loads(
            asyncio.run(
                tools["memory_update_frontmatter_bulk"](
                    updates=[
                        {
                            "path": "memory/working/projects/one.md",
                            "fields": {"status": "complete"},
                        },
                        {
                            "path": "memory/working/projects/two.md",
                            "fields": {"status": "complete"},
                        },
                    ]
                )
            )
        )
        commit_payload = json.loads(
            asyncio.run(tools["memory_commit"](message="[system] Bulk update frontmatter"))
        )

        self.assertEqual(payload["new_state"]["updated_count"], 2)
        self.assertEqual(
            sorted(commit_payload["files_changed"]),
            ["memory/working/projects/one.md", "memory/working/projects/two.md"],
        )
        self.assertIsNotNone(commit_payload["commit_sha"])

    def test_memory_update_frontmatter_bulk_skips_missing_keys_when_disabled(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/test-plan.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
status: active
---

# Test Plan
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        payload = json.loads(
            asyncio.run(
                tools["memory_update_frontmatter_bulk"](
                    updates=[
                        {
                            "path": "memory/working/projects/test-plan.md",
                            "fields": {"status": "complete", "next_action": "Later"},
                        }
                    ],
                    create_missing_keys=False,
                )
            )
        )

        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory/working/projects/test-plan.md"
        )
        self.assertEqual(payload["new_state"]["updated_count"], 1)
        self.assertEqual(frontmatter["status"], "complete")
        self.assertNotIn("next_action", frontmatter)

    def test_memory_update_frontmatter_bulk_rejects_invalid_path_before_staging(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/test-plan.md": """---
status: active
---

# Test Plan
""",
                "README.md": "# Root\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.ValidationError) as exc_info:
            asyncio.run(
                tools["memory_update_frontmatter_bulk"](
                    updates=[
                        {
                            "path": "memory/working/projects/test-plan.md",
                            "fields": {"status": "complete"},
                        },
                        {"path": "README.md", "fields": {"title": "Blocked"}},
                    ]
                )
            )

        self.assertIn("README.md", str(exc_info.exception))
        self.assertEqual(
            subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "",
        )

    def test_memory_update_frontmatter_bulk_rolls_back_on_stage_failure(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/one.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
status: active
---

# One
""",
                "memory/working/projects/two.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
status: active
---

# Two
""",
            }
        )
        _, tools, _, repo = self.server.create_mcp(
            repo_root=repo_root,
            enable_raw_write_tools=True,
        )
        tools = cast(dict[str, ToolCallable], tools)
        original_add = repo.add
        calls = {"count": 0}

        def flaky_add(*rel_paths: str) -> None:
            calls["count"] += 1
            if calls["count"] == 2:
                raise self.errors.StagingError("simulated git add failure")
            original_add(*rel_paths)

        repo.add = flaky_add  # type: ignore[method-assign]
        self.addCleanup(setattr, repo, "add", original_add)

        with self.assertRaises(self.errors.StagingError):
            asyncio.run(
                tools["memory_update_frontmatter_bulk"](
                    updates=[
                        {
                            "path": "memory/working/projects/one.md",
                            "fields": {"status": "complete"},
                        },
                        {
                            "path": "memory/working/projects/two.md",
                            "fields": {"status": "complete"},
                        },
                    ]
                )
            )

        one_frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory/working/projects/one.md"
        )
        two_frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory/working/projects/two.md"
        )
        self.assertEqual(one_frontmatter["status"], "active")
        self.assertEqual(two_frontmatter["status"], "active")
        self.assertEqual(
            subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "",
        )

    def test_memory_update_frontmatter_bulk_rejects_oversized_batch(self) -> None:
        repo_root = self._init_repo_with_file("memory/working/projects/test-plan.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        oversized = [
            {"path": "memory/working/projects/test-plan.md", "fields": {"status": "complete"}}
            for _ in range(101)
        ]
        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_update_frontmatter_bulk"](updates=oversized))

    def test_memory_update_frontmatter_rejects_invalid_source_without_mutation(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
---

# Topic
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_update_frontmatter"](
                    path="memory/knowledge/topic.md",
                    updates='{"source": "invalid-source"}',
                )
            )

        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory/knowledge/topic.md"
        )
        self.assertEqual(frontmatter["source"], "unknown")
        self.assertEqual(
            subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "",
        )

    def test_memory_update_frontmatter_rejects_malformed_existing_frontmatter(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": "---\nsource: [broken\n---\n\n# Topic\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_update_frontmatter"](
                    path="memory/knowledge/topic.md",
                    updates='{"origin_session": "unknown"}',
                )
            )

        self.assertEqual(
            subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "",
        )

    def test_memory_update_frontmatter_backfill_does_not_set_last_verified(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": """---
source: unknown
created: 2026-03-17
trust: medium
---

# Topic
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_update_frontmatter"](
                path="memory/knowledge/topic.md",
                updates='{"origin_session": "unknown"}',
            )
        )

        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory/knowledge/topic.md"
        )
        self.assertEqual(frontmatter["origin_session"], "unknown")
        self.assertNotIn("last_verified", frontmatter)

    def test_memory_update_frontmatter_noop_skips_staging_when_values_match(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
status: active
---

# Topic
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        payload = json.loads(
            asyncio.run(
                tools["memory_update_frontmatter"](
                    path="memory/knowledge/topic.md",
                    updates='{"status": "active"}',
                )
            )
        )

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(payload["files_changed"], [])
        self.assertFalse(payload["new_state"]["changed"])
        self.assertEqual(payload["new_state"]["frontmatter"]["status"], "active")
        self.assertEqual(staged, "")

    def test_memory_update_frontmatter_bulk_rejects_invalid_trust_without_staging(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/test-plan.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
---

# Test Plan
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_update_frontmatter_bulk"](
                    updates=[
                        {
                            "path": "memory/working/projects/test-plan.md",
                            "fields": {"trust": "ultra"},
                        }
                    ]
                )
            )

        self.assertEqual(
            subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "",
        )

    def test_memory_update_frontmatter_bulk_rejects_missing_required_provenance(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/test-plan.md": """---
source: unknown
origin_session: unknown
created: 2026-03-17
trust: medium
---

# Test Plan
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_update_frontmatter_bulk"](
                    updates=[
                        {
                            "path": "memory/working/projects/test-plan.md",
                            "fields": {"origin_session": None},
                        }
                    ]
                )
            )

    def test_memory_update_frontmatter_bulk_backfill_does_not_set_last_verified(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/test-plan.md": """---
source: unknown
created: 2026-03-17
trust: medium
---

# Test Plan
""",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_update_frontmatter_bulk"](
                updates=[
                    {
                        "path": "memory/working/projects/test-plan.md",
                        "fields": {"origin_session": "unknown"},
                    }
                ]
            )
        )

        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory/working/projects/test-plan.md"
        )
        self.assertEqual(frontmatter["origin_session"], "unknown")
        self.assertNotIn("last_verified", frontmatter)

    def test_memory_get_capabilities_returns_parseable_json(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/agent-memory-capabilities.toml": """version = 1
kind = \"agent-memory-capabilities\"

[contract_versions]
frontmatter = 1
access = 1
mcp = 1
capabilities = 1

[tool_sets]
read_support = [\"memory_get_capabilities\", \"memory_read_file\"]
raw_fallback = [\"memory_write\"]
semantic_extensions = [\"memory_plan_create\"]
declared_gaps = []
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_get_capabilities"]()))

        self.assertEqual(payload["kind"], "agent-memory-capabilities")
        self.assertEqual(payload["contract_versions"]["capabilities"], 1)
        self.assertEqual(payload["summary"]["declared_total_tools"], 4)
        self.assertGreaterEqual(payload["summary"]["total_tools"], 4)
        self.assertEqual(
            payload["summary"]["runtime_total_tools"], payload["summary"]["total_tools"]
        )
        self.assertEqual(payload["summary"]["read_tools"], 2)
        self.assertEqual(payload["summary"]["semantic_tools"], 1)

    def test_memory_plan_schema_returns_parseable_json(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_plan_schema"]()))
        failure_result_item = payload["properties"]["phases"]["items"]["properties"]["failures"][
            "items"
        ]["properties"]["verification_results"]["items"]["anyOf"][0]

        self.assertEqual(payload["tool_name"], "memory_plan_create")
        self.assertIn("phases", payload["properties"])
        self.assertEqual(
            payload["properties"]["phases"]["items"]["properties"]["sources"]["items"][
                "properties"
            ]["type"]["x-aliases"]["code"],
            "internal",
        )
        self.assertEqual(
            payload["properties"]["phases"]["items"]["properties"]["changes"]["items"][
                "properties"
            ]["action"]["x-aliases"]["modify"],
            "update",
        )
        self.assertEqual(
            failure_result_item["properties"]["status"]["enum"],
            ["error", "fail", "pass", "skip"],
        )

    def test_memory_tool_schema_returns_parseable_json(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        plan_payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_plan_create"))
        )
        access_payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_log_access_batch"))
        )
        legacy_payload = self._load_tool_payload(asyncio.run(tools["memory_plan_schema"]()))

        self.assertEqual(plan_payload, legacy_payload)
        self.assertEqual(access_payload["tool_name"], "memory_log_access_batch")
        self.assertIn("access_entries", access_payload["properties"])
        self.assertEqual(
            access_payload["properties"]["access_entries"]["items"]["properties"]["mode"]["enum"],
            ["create", "read", "update", "write"],
        )

    def test_memory_tool_schema_returns_raw_frontmatter_batch_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_update_frontmatter_bulk"))
        )

        self.assertEqual(payload["tool_name"], "memory_update_frontmatter_bulk")
        self.assertEqual(payload["properties"]["updates"]["maxItems"], 100)
        self.assertEqual(payload["properties"]["updates"]["items"]["required"], ["path", "fields"])
        self.assertTrue(payload["properties"]["create_missing_keys"]["default"])

    def test_memory_tool_schema_returns_raw_frontmatter_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_update_frontmatter"))
        )

        self.assertEqual(payload["tool_name"], "memory_update_frontmatter")
        self.assertEqual(payload["required"], ["path", "updates"])
        self.assertEqual(payload["properties"]["updates"]["contentMediaType"], "application/json")

    def test_memory_tool_schema_returns_trace_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_record_trace"))
        )
        recommended_cost = payload["properties"]["cost"]["anyOf"][0]

        self.assertEqual(payload["tool_name"], "memory_record_trace")
        self.assertEqual(
            payload["properties"]["span_type"]["enum"],
            [
                "guardrail_check",
                "plan_action",
                "policy_violation",
                "retrieval",
                "tool_call",
                "verification",
            ],
        )
        self.assertTrue(payload["properties"]["metadata"]["oneOf"][0]["additionalProperties"])
        self.assertEqual(recommended_cost["required"], ["tokens_in", "tokens_out"])
        self.assertEqual(recommended_cost["properties"]["tokens_in"]["minimum"], 0)

    def test_memory_tool_schema_returns_register_tool_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_register_tool"))
        )

        self.assertEqual(payload["tool_name"], "memory_register_tool")
        self.assertEqual(payload["required"], ["name", "description", "provider"])
        self.assertEqual(
            payload["properties"]["cost_tier"]["enum"],
            ["free", "high", "low", "medium"],
        )
        self.assertEqual(payload["properties"]["timeout_seconds"]["minimum"], 1)
        self.assertEqual(payload["properties"]["schema"]["oneOf"][0]["type"], "object")
        self.assertEqual(payload["allOf"][0]["then"]["required"], ["approval_token"])
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_periodic_review_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_record_periodic_review"))
        )
        apply_guard = payload["allOf"][0]
        active_stage = payload["properties"]["active_stage"]["oneOf"][0]

        self.assertEqual(payload["tool_name"], "memory_record_periodic_review")
        self.assertEqual(
            payload["required"],
            ["review_date", "assessment_summary", "belief_diff_entry"],
        )
        self.assertEqual(
            active_stage["enum"],
            ["Calibration", "Consolidation", "Exploration"],
        )
        self.assertEqual(payload["properties"]["review_date"]["format"], "date")
        self.assertEqual(apply_guard["then"]["required"], ["approval_token"])
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_revert_commit_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_revert_commit"))
        )

        self.assertEqual(payload["tool_name"], "memory_revert_commit")
        self.assertEqual(payload["required"], ["sha"])
        self.assertEqual(payload["properties"]["sha"]["pattern"], r"^[0-9a-fA-F]{4,64}$")
        self.assertFalse(payload["properties"]["confirm"]["default"])
        self.assertEqual(payload["allOf"][0]["then"]["required"], ["preview_token"])
        self.assertEqual(payload["properties"]["preview_token"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_promote_knowledge_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_promote_knowledge"))
        )

        self.assertEqual(payload["tool_name"], "memory_promote_knowledge")
        self.assertEqual(payload["required"], ["source_path"])
        self.assertEqual(payload["properties"]["trust_level"]["enum"], ["high", "medium"])
        self.assertEqual(payload["properties"]["trust_level"]["default"], "high")
        self.assertEqual(payload["properties"]["target_path"]["oneOf"][1]["type"], "null")
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_promote_subtree_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_promote_knowledge_subtree"))
        )

        self.assertEqual(payload["tool_name"], "memory_promote_knowledge_subtree")
        self.assertEqual(payload["required"], ["source_folder", "dest_folder"])
        self.assertEqual(payload["properties"]["trust_level"]["default"], "medium")
        self.assertEqual(payload["properties"]["reason"]["default"], "")
        self.assertFalse(payload["properties"]["dry_run"]["default"])
        self.assertEqual(payload["allOf"][0]["then"]["required"], ["preview_token"])
        self.assertEqual(payload["properties"]["preview_token"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_reorganize_path_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_reorganize_path"))
        )

        self.assertEqual(payload["tool_name"], "memory_reorganize_path")
        self.assertEqual(payload["required"], ["source", "dest"])
        self.assertTrue(payload["properties"]["dry_run"]["default"])

    def test_memory_tool_schema_returns_update_names_index_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_update_names_index"))
        )

        self.assertEqual(payload["tool_name"], "memory_update_names_index")
        self.assertEqual(payload["properties"]["path"]["default"], "memory/knowledge")
        self.assertEqual(payload["properties"]["version_token"]["oneOf"][1]["type"], "null")
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_demote_knowledge_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_demote_knowledge"))
        )

        self.assertEqual(payload["tool_name"], "memory_demote_knowledge")
        self.assertEqual(payload["required"], ["source_path"])
        self.assertEqual(payload["properties"]["reason"]["oneOf"][1]["type"], "null")
        self.assertEqual(payload["properties"]["version_token"]["oneOf"][1]["type"], "null")
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_archive_knowledge_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_archive_knowledge"))
        )

        self.assertEqual(payload["tool_name"], "memory_archive_knowledge")
        self.assertEqual(payload["required"], ["source_path"])
        self.assertEqual(payload["properties"]["reason"]["oneOf"][1]["type"], "null")
        self.assertEqual(payload["properties"]["version_token"]["oneOf"][1]["type"], "null")
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_add_knowledge_file_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_add_knowledge_file"))
        )

        self.assertEqual(payload["tool_name"], "memory_add_knowledge_file")
        self.assertEqual(payload["required"], ["path", "content", "source", "session_id"])
        self.assertEqual(payload["properties"]["trust"]["enum"], ["low"])
        self.assertEqual(payload["properties"]["trust"]["default"], "low")
        self.assertEqual(payload["properties"]["expires"]["oneOf"][0]["format"], "date")
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_checkpoint_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_checkpoint"))
        )

        self.assertEqual(payload["tool_name"], "memory_checkpoint")
        self.assertEqual(payload["required"], ["content"])
        self.assertEqual(payload["properties"]["label"]["default"], "")
        self.assertEqual(payload["properties"]["session_id"]["oneOf"][1]["const"], "")

    def test_memory_tool_schema_returns_append_scratchpad_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_append_scratchpad"))
        )

        self.assertEqual(payload["tool_name"], "memory_append_scratchpad")
        self.assertEqual(payload["required"], ["target", "content"])
        self.assertEqual(payload["properties"]["target"]["oneOf"][0]["enum"], ["user", "current"])
        self.assertEqual(payload["properties"]["section"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_record_chat_summary_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_record_chat_summary"))
        )

        self.assertEqual(payload["tool_name"], "memory_record_chat_summary")
        self.assertEqual(payload["required"], ["session_id", "summary"])
        self.assertEqual(payload["properties"]["key_topics"]["default"], "")

    def test_memory_tool_schema_returns_record_reflection_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_record_reflection"))
        )

        self.assertEqual(payload["tool_name"], "memory_record_reflection")
        self.assertEqual(
            payload["required"],
            [
                "session_id",
                "memory_retrieved",
                "memory_influence",
                "outcome_quality",
                "gaps_noticed",
            ],
        )
        self.assertEqual(payload["properties"]["system_observations"]["default"], "")

    def test_memory_tool_schema_returns_resolve_review_item_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_resolve_review_item"))
        )

        self.assertEqual(payload["tool_name"], "memory_resolve_review_item")
        self.assertEqual(payload["required"], ["item_id"])
        self.assertEqual(payload["properties"]["version_token"]["oneOf"][1]["type"], "null")
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_plan_resume_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_plan_resume"))
        )

        self.assertEqual(payload["tool_name"], "memory_plan_resume")
        self.assertEqual(payload["required"], ["plan_id", "session_id"])
        self.assertEqual(payload["properties"]["max_context_chars"]["default"], 8000)
        self.assertEqual(payload["properties"]["max_context_chars"]["minimum"], 0)

    def test_memory_tool_schema_returns_plan_review_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_plan_review"))
        )

        self.assertEqual(payload["tool_name"], "memory_plan_review")
        self.assertEqual(payload["required"], ["project_id"])
        self.assertEqual(payload["allOf"][0]["then"]["required"], ["session_id"])
        self.assertFalse(payload["properties"]["preview"]["default"])

    def test_memory_tool_schema_returns_read_file_pagination_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_read_file"))
        )

        self.assertEqual(payload["tool_name"], "memory_read_file")
        self.assertEqual(payload["required"], ["path"])
        self.assertEqual(payload["properties"]["offset_bytes"]["minimum"], 0)
        self.assertFalse(payload["properties"]["prefer_temp_file"]["default"])
        self.assertEqual(payload["properties"]["limit_bytes"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_stage_external_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_stage_external"))
        )

        self.assertEqual(payload["tool_name"], "memory_stage_external")
        self.assertEqual(
            payload["required"],
            ["project", "filename", "content", "source_url", "fetched_date", "source_label"],
        )
        self.assertEqual(payload["properties"]["fetched_date"]["format"], "date")
        self.assertFalse(payload["properties"]["dry_run"]["default"])
        reflects_schema = payload["properties"]["reflects_upstream_as_of"]
        self.assertEqual(reflects_schema["oneOf"][0]["type"], "string")
        self.assertEqual(reflects_schema["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_run_eval_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_run_eval"))
        )

        self.assertEqual(payload["tool_name"], "memory_run_eval")
        self.assertEqual(payload["required"], ["session_id"])
        self.assertEqual(payload["properties"]["scenario_id"]["oneOf"][1]["type"], "null")
        self.assertEqual(payload["properties"]["tag"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_eval_report_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_eval_report"))
        )

        self.assertEqual(payload["tool_name"], "memory_eval_report")
        self.assertEqual(payload["properties"]["date_from"]["oneOf"][0]["format"], "date")
        self.assertEqual(payload["properties"]["scenario_id"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_log_access_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_log_access"))
        )

        self.assertEqual(payload["tool_name"], "memory_log_access")
        self.assertEqual(payload["required"], ["file", "task", "helpfulness", "note"])
        self.assertEqual(payload["properties"]["helpfulness"]["maximum"], 1.0)
        self.assertEqual(payload["properties"]["mode"]["oneOf"][1]["type"], "null")
        self.assertEqual(payload["properties"]["min_helpfulness"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_run_aggregation_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_run_aggregation"))
        )

        self.assertEqual(payload["tool_name"], "memory_run_aggregation")
        self.assertEqual(
            payload["properties"]["folders"]["oneOf"][0]["items"]["enum"],
            [
                "memory/users",
                "memory/knowledge",
                "memory/knowledge/_unverified",
                "memory/skills",
                "memory/working/projects",
                "memory/activity",
            ],
        )
        self.assertTrue(payload["properties"]["dry_run"]["default"])

    def test_memory_tool_schema_returns_session_flush_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_session_flush"))
        )

        self.assertEqual(payload["tool_name"], "memory_session_flush")
        self.assertEqual(payload["required"], ["summary"])
        self.assertEqual(payload["properties"]["label"]["default"], "")
        self.assertEqual(payload["properties"]["trigger"]["default"], "context_pressure")
        self.assertEqual(payload["properties"]["session_id"]["oneOf"][1]["const"], "")

    def test_memory_tool_schema_returns_reset_session_state_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_reset_session_state"))
        )

        self.assertEqual(payload["tool_name"], "memory_reset_session_state")
        self.assertEqual(payload["properties"], {})
        self.assertFalse("required" in payload)

    def test_memory_tool_schema_returns_prune_redundant_links_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_prune_redundant_links"))
        )

        self.assertEqual(payload["tool_name"], "memory_prune_redundant_links")
        self.assertEqual(payload["properties"]["path"]["default"], "")
        self.assertTrue(payload["properties"]["dry_run"]["default"])

    def test_memory_tool_schema_returns_audit_link_density_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_audit_link_density"))
        )

        self.assertEqual(payload["tool_name"], "memory_audit_link_density")
        self.assertEqual(payload["properties"]["path"]["default"], "")
        self.assertEqual(payload["properties"]["degree_threshold"]["default"], 6)
        self.assertEqual(payload["properties"]["clustering_threshold"]["default"], 0.5)

    def test_memory_tool_schema_returns_prune_weak_links_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_prune_weak_links"))
        )

        self.assertEqual(payload["tool_name"], "memory_prune_weak_links")
        self.assertEqual(payload["properties"]["scope"]["default"], "")
        self.assertEqual(
            payload["properties"]["signal"]["enum"], ["access", "combined", "structural"]
        )
        self.assertEqual(payload["properties"]["signal"]["default"], "structural")
        self.assertTrue(payload["properties"]["dry_run"]["default"])

    def test_memory_tool_schema_returns_analyze_graph_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_analyze_graph"))
        )

        self.assertEqual(payload["tool_name"], "memory_analyze_graph")
        self.assertEqual(payload["properties"]["path"]["default"], "")
        self.assertFalse(payload["properties"]["include_details"]["default"])

    def test_memory_tool_schema_returns_list_pending_reviews_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_list_pending_reviews"))
        )

        self.assertEqual(payload["tool_name"], "memory_list_pending_reviews")
        self.assertEqual(
            payload["properties"]["folder_path"]["default"],
            "memory/knowledge/_unverified",
        )

    def test_memory_tool_schema_returns_update_user_trait_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_update_user_trait"))
        )

        self.assertEqual(payload["tool_name"], "memory_update_user_trait")
        self.assertEqual(payload["required"], ["file", "key", "value"])
        self.assertEqual(payload["properties"]["mode"]["default"], "upsert")
        self.assertFalse(payload["properties"]["preview"]["default"])
        self.assertEqual(payload["allOf"][0]["then"]["required"], ["preview_token"])
        self.assertEqual(payload["properties"]["preview_token"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_update_skill_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_update_skill"))
        )

        self.assertEqual(payload["tool_name"], "memory_update_skill")
        self.assertEqual(payload["required"], ["file", "section", "content"])
        self.assertEqual(
            payload["allOf"][0]["then"]["required"], ["source", "trust", "origin_session"]
        )
        self.assertEqual(payload["allOf"][1]["then"]["required"], ["approval_token"])
        trigger_content_schema = payload["allOf"][2]["then"]["properties"]["content"]

        self.assertEqual(payload["allOf"][2]["if"]["properties"]["section"]["const"], "trigger")
        self.assertEqual(trigger_content_schema["oneOf"][0]["type"], "string")
        self.assertEqual(trigger_content_schema["oneOf"][1]["type"], "object")
        self.assertEqual(trigger_content_schema["oneOf"][2]["type"], "array")
        self.assertEqual(payload["allOf"][3]["then"]["properties"]["content"]["type"], "string")
        self.assertFalse(payload["properties"]["create_if_missing"]["default"])

    def test_memory_tool_schema_returns_list_plans_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_list_plans"))
        )

        self.assertEqual(payload["tool_name"], "memory_list_plans")
        self.assertEqual(payload["properties"]["status"]["oneOf"][1]["type"], "null")
        self.assertEqual(payload["properties"]["project_id"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_plan_verify_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_plan_verify"))
        )

        self.assertEqual(payload["tool_name"], "memory_plan_verify")
        self.assertEqual(payload["required"], ["plan_id", "phase_id"])
        self.assertEqual(payload["properties"]["project_id"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_query_traces_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_query_traces"))
        )

        self.assertEqual(payload["tool_name"], "memory_query_traces")
        self.assertEqual(payload["properties"]["limit"]["default"], 100)
        self.assertEqual(payload["properties"]["date_from"]["oneOf"][0]["format"], "date")
        self.assertEqual(payload["properties"]["status"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_plan_briefing_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_plan_briefing"))
        )

        self.assertEqual(payload["tool_name"], "memory_plan_briefing")
        self.assertEqual(payload["required"], ["plan_id"])
        self.assertEqual(payload["properties"]["max_context_chars"]["default"], 8000)
        self.assertTrue(payload["properties"]["include_sources"]["default"])
        self.assertTrue(payload["properties"]["include_traces"]["default"])
        self.assertTrue(payload["properties"]["include_approval"]["default"])

    def test_memory_tool_schema_returns_scan_drop_zone_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_scan_drop_zone"))
        )

        self.assertEqual(payload["tool_name"], "memory_scan_drop_zone")
        self.assertEqual(payload["properties"]["project_filter"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_get_tool_policy_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_get_tool_policy"))
        )

        self.assertEqual(payload["tool_name"], "memory_get_tool_policy")
        self.assertEqual(len(payload["allOf"]), 1)
        self.assertEqual(
            payload["properties"]["cost_tier"]["oneOf"][0]["enum"],
            ["free", "high", "low", "medium"],
        )
        self.assertEqual(payload["properties"]["tags"]["oneOf"][1]["type"], "null")

    def test_memory_tool_schema_returns_semantic_search_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_semantic_search"))
        )

        self.assertEqual(payload["tool_name"], "memory_semantic_search")
        self.assertEqual(payload["required"], ["query"])
        self.assertEqual(payload["properties"]["limit"]["default"], 10)
        self.assertEqual(payload["properties"]["limit"]["maximum"], 50)
        self.assertEqual(payload["properties"]["vector_weight"]["default"], 0.4)
        self.assertEqual(payload["properties"]["bm25_weight"]["default"], 0.3)

    def test_memory_tool_schema_returns_reindex_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_reindex"))
        )

        self.assertEqual(payload["tool_name"], "memory_reindex")
        self.assertFalse(payload["properties"]["force"]["default"])

    def test_memory_tool_schema_rejects_unknown_tool(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError) as ctx:
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_not_real"))

        self.assertIn("Unsupported tool schema", str(ctx.exception))

    def test_memory_get_capabilities_returns_structured_error_for_malformed_toml(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/agent-memory-capabilities.toml": "version = 1\nkind = [\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_get_capabilities"]()))

        self.assertIn("error", payload)
        self.assertIn("Could not parse capability manifest", payload["error"])
        self.assertEqual(payload["path"], "HUMANS/tooling/agent-memory-capabilities.toml")
        self.assertIn("kind = [", payload["raw"])

    def test_memory_get_policy_state_reports_manifest_policy_for_create_plan(self) -> None:
        repo_root = self._init_repo(self._policy_contract_seed_files())
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_get_policy_state"](operation="create_plan"))
        )

        self.assertEqual(payload["operation"], "create_plan")
        self.assertEqual(payload["tool"], "memory_plan_create")
        self.assertEqual(payload["change_class"], "proposed")
        self.assertTrue(payload["approval_required"])
        self.assertTrue(payload["preview_required"])
        self.assertTrue(payload["preview_available"])
        self.assertEqual(payload["preview_argument"], "preview")

    def test_memory_get_policy_state_flags_protected_meta_surface(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["core/INIT.md"] = "# Init\n"
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_get_policy_state"](path="INIT.md"))
        )

        self.assertEqual(payload["change_class"], "protected")
        self.assertTrue(payload["path_policy"]["protected_surface"])
        self.assertIn(
            "Governance and top-level architecture files require explicit approval.",
            payload["path_policy"]["reasons"],
        )

    def test_memory_route_intent_recommends_knowledge_promotion(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["memory/knowledge/_unverified/topic/note.md"] = "# Note\n"
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](
                    intent="promote this unverified knowledge file to verified knowledge",
                    path="memory/knowledge/_unverified/topic/note.md",
                )
            )
        )

        self.assertEqual(payload["recommended_operation"]["operation"], "promote_knowledge")
        self.assertIn("memory_promote_knowledge", payload["workflow_hint"])
        self.assertEqual(payload["policy_state"]["change_class"], "proposed")
        self.assertTrue(payload["policy_state"]["approval_required"])

    def test_memory_route_intent_adds_subtree_workflow_hint_for_nested_folder(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["memory/knowledge/_unverified/topic/sub/a.md"] = "# A\n"
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](
                    intent="promote this unverified knowledge subtree",
                    path="memory/knowledge/_unverified/topic",
                )
            )
        )

        self.assertEqual(payload["recommended_operation"]["operation"], "promote_knowledge_subtree")
        self.assertIn("dry_run=True", payload["workflow_hint"])

    def test_memory_route_intent_briefing_routes_to_context_project(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["memory/working/projects/rate-my-set/SUMMARY.md"] = "# Rate My Set\n"
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](
                    intent=(
                        "I am cold-starting work on the rate-my-set project and need a "
                        "briefing on its current state"
                    ),
                )
            )
        )

        recommended = payload["recommended_operation"]
        self.assertIsNotNone(recommended)
        self.assertEqual(recommended["operation"], "memory_context_project")
        self.assertEqual(recommended["arguments"], {"project": "rate-my-set"})
        self.assertFalse(payload["ambiguous"])

    def test_memory_route_intent_list_projects_routes_to_navigator(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["memory/working/projects/SUMMARY.md"] = "# Projects\n"
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](intent="what projects are active right now"),
            )
        )

        recommended = payload["recommended_operation"]
        self.assertIsNotNone(recommended)
        self.assertEqual(recommended["operation"], "memory_read_file")
        self.assertEqual(
            recommended["arguments"],
            {"path": "memory/working/projects/SUMMARY.md"},
        )

    def test_memory_route_intent_resume_routes_to_session_bootstrap(self) -> None:
        repo_root = self._init_repo(self._policy_contract_seed_files())
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](intent="resume work where I left off"),
            )
        )

        recommended = payload["recommended_operation"]
        self.assertIsNotNone(recommended)
        self.assertEqual(recommended["operation"], "memory_session_bootstrap")

    def test_memory_route_intent_briefing_without_project_falls_back_to_bootstrap(self) -> None:
        repo_root = self._init_repo(self._policy_contract_seed_files())
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](intent="get me up to speed on the current work"),
            )
        )

        recommended = payload["recommended_operation"]
        self.assertIsNotNone(recommended)
        self.assertEqual(recommended["operation"], "memory_session_bootstrap")

    def test_memory_route_intent_recommends_plan_creation(self) -> None:
        repo_root = self._init_repo(self._policy_contract_seed_files())
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](
                    intent="create a new implementation plan for MCP ergonomics",
                )
            )
        )

        self.assertEqual(payload["recommended_operation"]["operation"], "create_plan")
        self.assertEqual(payload["policy_state"]["change_class"], "proposed")
        self.assertTrue(payload["policy_state"]["preview_required"])

    def test_memory_find_references_finds_markdown_and_frontmatter_paths(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/target.md": "# Target\n",
                "memory/working/projects/reference-plan.md": """---
related:
  - memory/knowledge/topic/target.md
domain: memory/knowledge/topic/target.md
---

# Reference Plan

See [target](../knowledge/topic/target.md).
""",
                "HUMANS/README.md": "See [target](memory/knowledge/topic/target.md).\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_find_references"]("memory/knowledge/topic/target.md"))
        )

        self.assertEqual(payload["query"], "memory/knowledge/topic/target.md")
        self.assertEqual(payload["total"], 3)
        self.assertEqual(
            [match["ref_type"] for match in payload["matches"]],
            ["frontmatter_path", "frontmatter_path", "markdown_link"],
        )
        self.assertTrue(
            all(
                match["from_path"] == "memory/working/projects/reference-plan.md"
                for match in payload["matches"]
            )
        )
        self.assertEqual(
            payload["matches"][-1]["resolved_path"],
            "memory/knowledge/topic/target.md",
        )

    def test_memory_resolve_link_reports_resolution_and_missing_anchor(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/target.md": "# Target\n\n## Details\n",
                "memory/knowledge/topic/note.md": "# Note\n",
            }
        )
        tools = self._create_tools(repo_root)

        ok_payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_resolve_link"](
                    path="memory/knowledge/topic/note.md",
                    target="target.md#details",
                )
            )
        )
        broken_payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_resolve_link"](
                    path="memory/knowledge/topic/note.md",
                    target="target.md#missing",
                )
            )
        )

        self.assertEqual(ok_payload["resolved_path"], "memory/knowledge/topic/target.md")
        self.assertTrue(ok_payload["exists"])
        self.assertIsNone(ok_payload["reason"])
        self.assertEqual(broken_payload["reason"], "anchor not found: #missing")

    def test_memory_scan_frontmatter_health_reports_yaml_and_related_issues(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/good.md": "---\nsource: test\ncreated: 2026-01-01\ntrust: low\nrelated:\n  - target.md\n---\n\n# Good\n",
                "memory/knowledge/topic/target.md": "# Target\n",
                "memory/knowledge/topic/bad.md": "---\nsource: test\ncreated: not-a-date\ntrust: low\nrelated: target.md, missing.md\n--- Broken\n# Bad\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_scan_frontmatter_health"]("memory/knowledge/topic"))
        )

        self.assertEqual(payload["files_scanned"], 3)
        self.assertGreaterEqual(payload["files_with_issues"], 1)
        self.assertIn("yaml_parse_error", payload["issue_counts"])
        self.assertIn("malformed_frontmatter_close", payload["issue_counts"])

    def test_memory_find_references_include_body_scans_path_like_strings(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/target.md": "# Target\n",
                "memory/knowledge/topic/note.md": "# Note\n\nSee memory/knowledge/topic/target.md for context.\n",
            }
        )
        tools = self._create_tools(repo_root)

        without_body = self._load_tool_payload(
            asyncio.run(
                tools["memory_find_references"](
                    "memory/knowledge/topic/target.md",
                    include_body=False,
                )
            )
        )
        with_body = self._load_tool_payload(
            asyncio.run(
                tools["memory_find_references"](
                    "memory/knowledge/topic/target.md",
                    include_body=True,
                )
            )
        )

        self.assertEqual(without_body["total"], 0)
        self.assertEqual(with_body["total"], 1)
        self.assertEqual(with_body["matches"][0]["ref_type"], "body_path")
        self.assertEqual(with_body["matches"][0]["from_path"], "memory/knowledge/topic/note.md")

    def test_memory_validate_links_reports_broken_targets_and_missing_anchors(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/target.md": "# Target\n\n## Details\n",
                "memory/knowledge/topic/note.md": """---
related:
  - missing.md
---

# Note

See [target](target.md#details).
See [broken anchor](target.md#absent).
See [missing](missing.md).
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_validate_links"]("memory/knowledge/topic"))
        )

        self.assertEqual(payload["scope"], "memory/knowledge/topic")
        self.assertEqual(payload["checked"], 4)
        self.assertEqual(payload["ok_count"], 1)
        self.assertEqual(len(payload["broken"]), 3)
        self.assertIn(
            {
                "from_path": "memory/knowledge/topic/note.md",
                "ref_type": "frontmatter_path",
                "target": "missing.md",
                "resolved_path": "memory/knowledge/topic/missing.md",
                "reason": "target not found",
                "line": 3,
            },
            payload["broken"],
        )
        self.assertIn(
            {
                "from_path": "memory/knowledge/topic/note.md",
                "ref_type": "markdown_link",
                "target": "target.md#absent",
                "resolved_path": "memory/knowledge/topic/target.md",
                "reason": "anchor not found: #absent",
                "line": 4,
            },
            payload["broken"],
        )

    def test_memory_validate_links_handles_cross_folder_relative_paths(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/target.md": "# Topic Target\n",
                "memory/working/projects/demo.md": """---
related:
  - ../knowledge/topic/target.md
---

# Demo

See [topic](../knowledge/topic/target.md).
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_validate_links"]("plans")))

        self.assertEqual(payload["scope"], "plans")
        self.assertEqual(payload["checked"], 2)
        self.assertEqual(payload["ok_count"], 2)
        self.assertEqual(payload["broken"], [])

    def test_memory_suggest_links_returns_structured_candidates(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "---\nsource: test\ncreated: 2026-01-01\ntrust: low\n---\n\n# Compression\n\nCompression relates to gardenfors conceptual spaces.\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors Conceptual Spaces\n",
                "memory/knowledge/philosophy/other.md": "# Other\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_suggest_links"](
                    path="memory/knowledge/philosophy/compression.md",
                    max_suggestions=5,
                )
            )
        )

        self.assertEqual(payload["path"], "memory/knowledge/philosophy/compression.md")
        self.assertGreaterEqual(payload["total_suggestions"], 1)
        self.assertIn("target", payload["suggestions"][0])
        self.assertIn("score", payload["suggestions"][0])

    def test_memory_suggest_links_can_filter_cross_domain_candidates(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nGardenfors conceptual spaces and reasoning both matter here.\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors Conceptual Spaces\n",
                "memory/knowledge/philosophy/reasoning.md": "# Reasoning\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_suggest_links"](
                    path="memory/knowledge/philosophy/compression.md",
                    max_suggestions=5,
                    domain_mode="cross",
                )
            )
        )

        self.assertEqual(payload["domain_mode"], "cross")
        self.assertGreaterEqual(payload["total_suggestions"], 1)
        self.assertTrue(all(not item["is_same_domain"] for item in payload["suggestions"]))
        self.assertEqual(
            payload["suggestions"][0]["target_domain"],
            "cognitive-science",
        )

    def test_memory_suggest_links_can_filter_by_min_score(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nGardenfors conceptual spaces and reasoning both matter here.\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors Conceptual Spaces\n",
                "memory/knowledge/philosophy/reasoning.md": "# Reasoning\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_suggest_links"](
                    path="memory/knowledge/philosophy/compression.md",
                    max_suggestions=5,
                    domain_mode="all",
                    min_score=5.0,
                )
            )
        )

        self.assertEqual(payload["min_score"], 5.0)
        self.assertGreaterEqual(payload["total_suggestions"], 1)
        self.assertTrue(all(item["score"] >= 5.0 for item in payload["suggestions"]))
        self.assertTrue(
            all(
                item["target"]
                != "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md"
                for item in payload["suggestions"]
            )
        )

    def test_memory_cross_domain_links_summarizes_pairs(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n\nSee [Compression](../philosophy/compression.md).\n",
                "memory/knowledge/ai/frontier.md": "# Frontier\n\nSee [Compression](../philosophy/compression.md).\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_cross_domain_links"]("memory/knowledge"))
        )

        self.assertGreaterEqual(payload["domain_count"], 3)
        self.assertGreaterEqual(len(payload["directional_pairs"]), 1)
        self.assertIn("bridge_files", payload)

    def test_memory_cross_domain_links_can_filter_results(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\nSee [AI](../ai/frontier.md).\n",
                "memory/knowledge/philosophy/logic.md": "# Logic\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n",
                "memory/knowledge/ai/frontier.md": "# Frontier\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_cross_domain_links"](
                    "memory/knowledge",
                    "philosophy",
                    "cognitive-science",
                    2,
                )
            )
        )

        self.assertEqual(payload["source_domain_filter"], "philosophy")
        self.assertEqual(payload["target_domain_filter"], "cognitive-science")
        self.assertEqual(payload["min_edge_count"], 2)
        self.assertEqual(payload["cross_domain_edge_total"], 2)
        self.assertEqual(len(payload["directional_pairs"]), 1)
        self.assertEqual(payload["directional_pairs"][0]["source_domain"], "philosophy")
        self.assertEqual(payload["directional_pairs"][0]["target_domain"], "cognitive-science")

    def test_memory_link_delta_reports_working_tree_edge_changes(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n",
            }
        )
        tools = self._create_tools(repo_root)
        note_path = self._repo_file_path(repo_root, "memory/knowledge/philosophy/compression.md")
        note_path.write_text(
            "# Compression\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
            encoding="utf-8",
        )

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_link_delta"]("memory/knowledge", "HEAD"))
        )

        self.assertEqual(payload["base_ref"], "HEAD")
        self.assertGreaterEqual(len(payload["added_edges"]), 1)
        self.assertIn("graph_stats_delta", payload)
        self.assertIn("added_domain_pairs", payload)
        self.assertIn("impacted_files_detail", payload)
        self.assertIn("changed_category_counts", payload)

    def test_memory_link_delta_can_filter_to_cross_domain_changes(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n",
                "memory/knowledge/philosophy/logic.md": "# Logic\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n",
            }
        )
        tools = self._create_tools(repo_root)
        note_path = self._repo_file_path(repo_root, "memory/knowledge/philosophy/compression.md")
        note_path.write_text(
            "# Compression\n\nSee [Logic](logic.md).\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
            encoding="utf-8",
        )

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_link_delta"](
                    "memory/knowledge",
                    "HEAD",
                    True,
                )
            )
        )

        self.assertTrue(payload["cross_domain_only"])
        self.assertEqual(len(payload["added_edges"]), 1)
        self.assertEqual(payload["added_domain_pairs"][0]["source_domain"], "philosophy")
        self.assertEqual(payload["added_domain_pairs"][0]["target_domain"], "cognitive-science")

    def test_memory_link_delta_can_filter_by_transition(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/compression.md": "# Compression\n",
                "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md": "# Gardenfors\n",
            }
        )
        tools = self._create_tools(repo_root)
        note_path = self._repo_file_path(repo_root, "memory/knowledge/philosophy/compression.md")
        note_path.write_text(
            "# Compression\n\nSee [Spaces](../cognitive-science/gardenfors-conceptual-spaces.md).\n",
            encoding="utf-8",
        )

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_link_delta"](
                    "memory/knowledge",
                    "HEAD",
                    False,
                    "isolated->sink",
                )
            )
        )

        self.assertEqual(payload["transition_filter"], "isolated->sink")
        self.assertEqual(payload["changed_category_counts"], {"isolated->sink": 1})
        self.assertEqual(len(payload["impacted_files_detail"]), 1)
        self.assertEqual(
            payload["impacted_files_detail"][0]["path"],
            "memory/knowledge/cognitive-science/gardenfors-conceptual-spaces.md",
        )

    def test_memory_reorganize_preview_includes_moves_reference_updates_and_summary_targets(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai-frontier/alpha.md": "# Alpha\n",
                "memory/knowledge/ai-frontier/alignment/beta.md": "# Beta\n",
                "memory/knowledge/ai/SUMMARY.md": "# AI\n",
                "memory/working/projects/reorg.md": """---
related:
  - memory/knowledge/ai-frontier/alpha.md
---

# Reorg

See [alpha](../knowledge/ai-frontier/alpha.md).
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_reorganize_preview"](
                    "memory/knowledge/ai-frontier",
                    "memory/knowledge/ai/frontier",
                )
            )
        )

        self.assertEqual(payload["source"], "memory/knowledge/ai-frontier")
        self.assertEqual(payload["dest"], "memory/knowledge/ai/frontier")
        self.assertEqual(
            payload["files_to_move"],
            [
                "memory/knowledge/ai-frontier/alignment/beta.md",
                "memory/knowledge/ai-frontier/alpha.md",
            ],
        )
        self.assertEqual(
            payload["summary_updates"],
            ["memory/knowledge/SUMMARY.md", "memory/knowledge/ai/SUMMARY.md"],
        )
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(len(payload["files_with_references"]), 1)
        refs = payload["files_with_references"][0]["refs"]
        self.assertEqual(
            payload["files_with_references"][0]["path"], "memory/working/projects/reorg.md"
        )
        self.assertEqual(
            {(ref["old"], ref["new"]) for ref in refs},
            {
                ("memory/knowledge/ai-frontier/alpha.md", "memory/knowledge/ai/frontier/alpha.md"),
                ("../knowledge/ai-frontier/alpha.md", "../../knowledge/ai/frontier/alpha.md"),
            },
        )

    def test_memory_reorganize_preview_warns_on_destination_conflicts(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai-frontier/alpha.md": "# Alpha\n",
                "memory/knowledge/ai/frontier/alpha.md": "# Existing Alpha\n",
                "memory/knowledge/ai/SUMMARY.md": "# AI\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_reorganize_preview"](
                    "memory/knowledge/ai-frontier",
                    "memory/knowledge/ai/frontier",
                )
            )
        )

        self.assertIn(
            "Destination already exists: memory/knowledge/ai/frontier", payload["warnings"]
        )
        self.assertIn(
            "Destination conflict: memory/knowledge/ai/frontier/alpha.md", payload["warnings"]
        )

    def test_memory_reorganize_path_dry_run_returns_governed_preview(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai-frontier/alpha.md": "# Alpha\n",
                "memory/knowledge/ai/SUMMARY.md": "# AI\n",
                "memory/working/projects/reorg.md": "See [alpha](../knowledge/ai-frontier/alpha.md).\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(
            asyncio.run(
                tools["memory_reorganize_path"](
                    source="memory/knowledge/ai-frontier",
                    dest="memory/knowledge/ai/frontier",
                )
            )
        )

        self.assertIsNone(payload["commit_sha"])
        self.assertTrue(payload["new_state"]["dry_run"])
        self.assertTrue(payload["new_state"]["would_commit"])
        self.assertEqual(payload["preview"]["mode"], "preview")
        self.assertTrue((repo_root / "memory/knowledge/ai-frontier/alpha.md").exists())
        self.assertFalse((repo_root / "memory/knowledge/ai/frontier/alpha.md").exists())

    def test_memory_reorganize_path_applies_move_and_reference_updates(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/shared/guide.md": "# Guide\n",
                "memory/knowledge/ai-frontier/alpha.md": "# Alpha\n",
                "memory/knowledge/ai-frontier/alignment/beta.md": """---
related:
  - ../../shared/guide.md
---

# Beta

See [alpha](../alpha.md).
""",
                "memory/knowledge/SUMMARY.md": "- [alpha](ai-frontier/alpha.md)\n",
                "memory/knowledge/ai/SUMMARY.md": "# AI\n",
                "memory/working/projects/reorg.md": "See [alpha](../knowledge/ai-frontier/alpha.md).\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(
            asyncio.run(
                tools["memory_reorganize_path"](
                    source="memory/knowledge/ai-frontier",
                    dest="memory/knowledge/ai/frontier",
                    dry_run=False,
                )
            )
        )

        self.assertIsNotNone(payload["commit_sha"])
        self.assertFalse(payload["new_state"]["dry_run"])
        self.assertTrue((repo_root / "memory/knowledge/ai/frontier/alpha.md").exists())
        self.assertTrue((repo_root / "memory/knowledge/ai/frontier/alignment/beta.md").exists())
        self.assertFalse((repo_root / "memory/knowledge/ai-frontier/alpha.md").exists())
        self.assertFalse((repo_root / "memory/knowledge/ai-frontier").exists())
        beta_text = (repo_root / "memory/knowledge/ai/frontier/alignment/beta.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("../../../shared/guide.md", beta_text)
        self.assertIn("../alpha.md", beta_text)
        summary_text = (repo_root / "memory/knowledge/SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn("ai/frontier/alpha.md", summary_text)
        plan_text = (repo_root / "memory/working/projects/reorg.md").read_text(encoding="utf-8")
        self.assertIn("../knowledge/ai/frontier/alpha.md", plan_text)

    def test_memory_update_names_index_preview_returns_generated_content(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/simone-weil.md": """---
source: test
created: 2026-03-20
trust: medium
---

# Simone Weil: attention and obligation

Primary body.
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(
            asyncio.run(tools["memory_update_names_index"](path="memory/knowledge", preview=True))
        )

        self.assertIsNone(payload["commit_sha"])
        self.assertEqual(payload["new_state"]["output_path"], "memory/knowledge/NAMES.md")
        self.assertEqual(payload["preview"]["mode"], "preview")
        self.assertIn("### Simone Weil", payload["preview"]["content_preview"])
        self.assertFalse((repo_root / "memory/knowledge/NAMES.md").exists())

    def test_memory_update_names_index_applies_and_commits_output(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/simone-weil.md": """---
source: test
created: 2026-03-20
trust: medium
---

# Simone Weil: attention and obligation

Primary body.
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(asyncio.run(tools["memory_update_names_index"]()))

        self.assertIsNotNone(payload["commit_sha"])
        self.assertEqual(payload["new_state"]["output_path"], "memory/knowledge/NAMES.md")
        self.assertIn("version_token", payload["new_state"])
        names_index = (repo_root / "memory/knowledge/NAMES.md").read_text(encoding="utf-8")
        self.assertIn("### Simone Weil", names_index)

    def test_memory_update_names_index_rejects_non_knowledge_paths(self) -> None:
        repo_root = self._init_repo({"memory/users/profile.md": "# Profile\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_update_names_index"](path="memory/users", preview=True))

    def test_memory_reorganize_path_blocks_existing_destination_without_mutation(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai-frontier/alpha.md": "# Alpha\n",
                "memory/knowledge/ai/frontier/alpha.md": "# Existing\n",
                "memory/knowledge/ai/SUMMARY.md": "# AI\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_reorganize_path"](
                    source="memory/knowledge/ai-frontier",
                    dest="memory/knowledge/ai/frontier",
                    dry_run=False,
                )
            )

        self.assertTrue((repo_root / "memory/knowledge/ai-frontier/alpha.md").exists())
        self.assertTrue((repo_root / "memory/knowledge/ai/frontier/alpha.md").exists())

    def test_memory_reorganize_path_rejects_destination_outside_knowledge_surface(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai-frontier/alpha.md": "# Alpha\n",
                "memory/knowledge/ai/SUMMARY.md": "# AI\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_reorganize_path"](
                    source="memory/knowledge/ai-frontier",
                    dest="memory/users/ai-frontier",
                    dry_run=False,
                )
            )

        self.assertTrue((repo_root / "memory/knowledge/ai-frontier/alpha.md").exists())
        self.assertFalse((repo_root / "memory/users/ai-frontier/alpha.md").exists())

    def test_memory_suggest_structure_detects_orphan_topics(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai/SUMMARY.md": "# AI\n\n- [overview](overview.md)\n",
                "memory/knowledge/ai/overview.md": "# Overview\n",
                "memory/knowledge/ai/lone-topic/note.md": "# Note\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_suggest_structure"]("memory/knowledge/ai"))
        )

        self.assertEqual(payload["scope"], "memory/knowledge/ai")
        self.assertTrue(
            any(
                item["heuristic"] == "orphan_topics"
                and "memory/knowledge/ai/lone-topic" in item["affected_paths"]
                for item in payload["suggestions"]
            )
        )

    def test_memory_suggest_structure_detects_naming_inconsistency(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai-frontier/topic.md": "# Topic\n",
                "memory/knowledge/ai/frontier/other.md": "# Other\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_suggest_structure"](
                    "knowledge",
                    heuristics=["naming_inconsistency"],
                )
            )
        )

        self.assertEqual(payload["heuristics"], ["naming_inconsistency"])
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["suggestions"][0]["heuristic"], "naming_inconsistency")
        self.assertEqual(
            set(payload["suggestions"][0]["affected_paths"]),
            {"memory/knowledge/ai-frontier", "memory/knowledge/ai/frontier"},
        )

    def test_memory_suggest_structure_returns_no_suggestions_for_consistent_layout(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ai/SUMMARY.md": "# AI\n\n- [topic](topic.md)\n",
                "memory/knowledge/ai/topic.md": "# Topic\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_suggest_structure"](
                    "memory/knowledge/ai",
                    heuristics=["orphan_topics", "naming_inconsistency", "summary_drift"],
                )
            )
        )

        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["suggestions"], [])

    def test_memory_route_intent_recommends_automatic_access_logging(self) -> None:
        repo_root = self._init_repo(self._policy_contract_seed_files())
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](
                    intent="log access for this retrieval",
                )
            )
        )

        self.assertEqual(payload["recommended_operation"]["operation"], "append_access_entry")
        self.assertEqual(payload["policy_state"]["change_class"], "automatic")
        self.assertFalse(payload["policy_state"]["approval_required"])

    def test_memory_route_intent_reports_uninterpretable_target_fallback(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["docs/random.txt"] = "hello\n"
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_route_intent"](
                    intent="edit this random file",
                    path="docs/random.txt",
                )
            )
        )

        self.assertIsNone(payload["recommended_operation"])
        self.assertTrue(payload["ambiguous"])
        self.assertFalse(payload["policy_state"]["semantic_target_supported"])
        self.assertEqual(
            payload["policy_state"]["uninterpretable_target_behavior"],
            "defer_with_contract_warning",
        )

    def test_memory_session_bootstrap_compacts_active_plans_and_review_items(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["core/INIT.md"] = """# Quick Reference

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Aggregation trigger | 15 entries | Exploration |
"""
        seed["governance/review-queue.md"] = """# Review Queue

### [2026-03-20] Review memory/working/projects/a/plans/plan-a.yaml
**Item ID:** review-a
**Type:** proposed
**File:** memory/working/projects/a/plans/plan-a.yaml
**Priority:** high
**Status:** pending

### [2026-03-20] Review memory/working/projects/b/plans/plan-b.yaml
**Item ID:** review-b
**Type:** proposed
**File:** memory/working/projects/b/plans/plan-b.yaml
**Priority:** normal
**Status:** pending
"""
        seed["memory/working/projects/a/plans/plan-a.yaml"] = (
            "id: plan-a\nproject: a\ncreated: 2026-03-20\norigin_session: memory/activity/2026/03/20/chat-001\nstatus: active\npurpose:\n  summary: Plan A\n  context: Finish A\n  questions: []\nwork:\n  phases:\n    - id: phase-a\n      title: Do A\n      status: pending\n      commit: null\n      blockers: []\n      changes:\n        - path: memory/working/projects/a/notes/do-a.md\n          action: create\n          description: Finish A.\nreview: null\n"
        )
        seed["memory/working/projects/b/plans/plan-b.yaml"] = (
            "id: plan-b\nproject: b\ncreated: 2026-03-20\norigin_session: memory/activity/2026/03/20/chat-001\nstatus: active\npurpose:\n  summary: Plan B\n  context: Finish B\n  questions: []\nwork:\n  phases:\n    - id: phase-b\n      title: Do B\n      status: pending\n      commit: null\n      blockers: []\n      changes:\n        - path: memory/working/projects/b/notes/do-b.md\n          action: create\n          description: Finish B.\nreview: null\n"
        )
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_session_bootstrap"](max_active_plans=1, max_review_items=1))
        )

        self.assertEqual(len(payload["active_plans"]), 1)
        self.assertEqual(
            payload["active_plans"][0]["next_action"],
            {
                "id": "phase-a",
                "title": "Do A",
                "requires_approval": False,
                "attempt_number": 1,
                "has_prior_failures": False,
            },
        )
        self.assertEqual(
            payload["active_plans"][0]["resume_context"],
            {
                "tool": "memory_context_project",
                "arguments": {"project": "a"},
            },
        )
        self.assertTrue(payload["response_budget"]["active_plans"]["truncated"])
        self.assertEqual(len(payload["pending_review_items"]), 1)
        self.assertTrue(payload["response_budget"]["review_items"]["truncated"])
        self.assertTrue(payload["recommended_checks"])
        self.assertTrue(
            any(
                'memory_context_project(project="a")' in item
                for item in payload["recommended_checks"]
            )
        )

    def test_memory_prepare_unverified_review_truncates_selected_files(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["core/INIT.md"] = """# Quick Reference

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
"""
        seed["memory/knowledge/_unverified/topic/a.md"] = """---
created: 2026-01-01
source: test
trust: low
---

# A

alpha beta gamma
"""
        seed["memory/knowledge/_unverified/topic/b.md"] = """---
created: 2026-01-02
source: test
trust: low
---

# B

delta epsilon zeta
"""
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_prepare_unverified_review"](
                    folder_path="memory/knowledge/_unverified",
                    max_files=1,
                    max_extract_words=10,
                )
            )
        )

        self.assertEqual(len(payload["selected_files"]), 1)
        self.assertTrue(payload["response_budget"]["files"]["truncated"])
        self.assertIn("single_file", payload["recommended_operations"])

    def test_memory_prepare_unverified_review_paths_only_returns_full_path_list(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["core/INIT.md"] = """# Quick Reference

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
"""
        seed["memory/knowledge/_unverified/topic/a.md"] = """---
created: 2026-01-01
source: test
trust: low
---

# A
"""
        seed["memory/knowledge/_unverified/topic/b.md"] = """---
created: 2026-01-02
source: test
trust: low
---

# B
"""
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_prepare_unverified_review"](
                    folder_path="memory/knowledge/_unverified/topic",
                    max_files=1,
                    max_extract_words=10,
                    paths_only=True,
                )
            )
        )

        self.assertTrue(payload["paths_only"])
        self.assertEqual(
            payload["all_paths"],
            [
                "memory/knowledge/_unverified/topic/a.md",
                "memory/knowledge/_unverified/topic/b.md",
            ],
        )
        self.assertFalse(payload["response_budget"]["paths"]["truncated"])

    def test_memory_prepare_promotion_batch_returns_candidates_and_operation_hint(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["core/INIT.md"] = """# Quick Reference

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
"""
        seed["memory/knowledge/_unverified/topic/a.md"] = """---
created: 2026-01-01
source: test
trust: low
---

# A
"""
        seed["memory/knowledge/_unverified/topic/b.md"] = """---
created: 2026-01-02
source: test
trust: low
---

# B
"""
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_prepare_promotion_batch"](
                    folder_path="memory/knowledge/_unverified/topic",
                    max_files=1,
                )
            )
        )

        self.assertEqual(payload["suggested_operation"], "memory_promote_knowledge_batch")
        self.assertIn("memory_promote_knowledge_batch", payload["workflow_hint"])
        self.assertEqual(len(payload["selected_candidates"]), 1)
        self.assertTrue(payload["response_budget"]["candidates"]["truncated"])

    def test_memory_prepare_promotion_batch_prefers_subtree_for_nested_folder(self) -> None:
        seed = self._policy_contract_seed_files()
        seed["core/INIT.md"] = """# Quick Reference

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
"""
        seed["memory/knowledge/_unverified/topic/sub/a.md"] = """---
created: 2026-01-01
source: test
trust: low
---

# A
"""
        seed["memory/knowledge/_unverified/topic/sub/b.md"] = """---
created: 2026-01-02
source: test
trust: low
---

# B
"""
        repo_root = self._init_repo(seed)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_prepare_promotion_batch"](
                    folder_path="memory/knowledge/_unverified/topic",
                    max_files=2,
                )
            )
        )

        self.assertEqual(payload["suggested_operation"], "memory_promote_knowledge_subtree")
        self.assertTrue(payload["folder_shape"]["has_nested_subdirectories"])
        self.assertEqual(payload["suggested_target_folder"], "memory/knowledge/topic")
        self.assertIn("dry_run=True", payload["workflow_hint"])

    def test_memory_prepare_periodic_review_compacts_deferred_targets(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Quick Reference

## Current active stage: Exploration

_Last assessed: 2026-03-01 — Exploration retained_

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
| Staleness trigger (no access) | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
| Identity churn alarm | 5 traits/session | Exploration |
| Knowledge flooding alarm | 5 files/day | Exploration |
| Task similarity method | Session co-occurrence | Exploration |
| Cluster co-retrieval threshold | 3 sessions | Exploration |

## Active task similarity method

**Method:** Session co-occurrence
""",
                "governance/belief-diff-log.md": "# Belief Diff Log\n",
                "governance/review-queue.md": """# Review Queue

### [2026-03-20] Review memory/working/projects/demo.md
**Item ID:** review-demo
**Type:** governance
**File:** memory/working/projects/demo.md
**Priority:** normal
**Status:** pending
""",
                "memory/knowledge/_unverified/topic/note.md": """---
created: 2025-12-01
source: test
trust: low
---

# Note
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_prepare_periodic_review"](
                    max_queue_items=1,
                    max_deferred_targets=1,
                )
            )
        )

        self.assertIn("write", payload["recommended_operations"])
        self.assertEqual(len(payload["deferred_write_targets"]), 1)
        self.assertTrue(payload["response_budget"]["deferred_targets"]["truncated"])

    def test_memory_search_context_lines_default_output_unchanged(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/test.md": """# Title
alpha
beta match
gamma
""",
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(tools["memory_search"](query="match", path="knowledge"))

        self.assertIn("**memory/knowledge/test.md**", output)
        self.assertIn("  3: beta match", output)
        self.assertNotIn("  2|", output)

    def test_memory_search_context_lines_include_surrounding_lines(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/test.md": """line 1
line 2
line 3 match
line 4
line 5
""",
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(
            tools["memory_search"](
                query="match",
                path="knowledge",
                context_lines=2,
            )
        )

        self.assertIn("  1| line 1", output)
        self.assertIn("  2| line 2", output)
        self.assertIn("  3: line 3 match", output)
        self.assertIn("  4| line 4", output)
        self.assertIn("  5| line 5", output)

    def test_memory_search_rejects_context_lines_over_limit(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/test.md": "match\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_search"](
                    query="match",
                    path="knowledge",
                    context_lines=11,
                )
            )

    def test_memory_search_context_lines_do_not_count_toward_max_results(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/test.md": """line 1
line 2
line 3 match
line 4
line 5
line 6 other match
line 7
""",
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(
            tools["memory_search"](
                query="match",
                path="knowledge",
                max_results=1,
                context_lines=2,
            )
        )

        self.assertIn("  1| line 1", output)
        self.assertIn("  2| line 2", output)
        self.assertIn("  3: line 3 match", output)
        self.assertIn("  4| line 4", output)
        self.assertIn("  5| line 5", output)
        self.assertNotIn("  6: line 6 other match", output)
        self.assertIn("truncated at 1 matches", output)

    def test_memory_check_cross_references_reports_broken_links_and_summary_drift(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/linked.md": "# Linked\n",
                "memory/knowledge/topic/note.md": """# Note
See [linked](linked.md).
See [missing](missing.md).
""",
                "memory/knowledge/topic/orphan.md": "# Orphan\n",
                "memory/knowledge/topic/SUMMARY.md": """# Topic Summary

- [note](note.md)
- [missing](missing.md)
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_check_cross_references"](path="memory/knowledge/topic"))
        )

        self.assertEqual(payload["stats"]["files_scanned"], 4)
        self.assertEqual(payload["stats"]["summaries_checked"], 1)
        self.assertEqual(payload["stats"]["links_checked"], 4)
        self.assertIn(
            {
                "file": "memory/knowledge/topic/note.md",
                "line": 3,
                "target": "memory/knowledge/topic/missing.md",
                "reason": "target not found",
            },
            payload["broken_links"],
        )
        self.assertIn(
            {
                "summary": "memory/knowledge/topic/SUMMARY.md",
                "entry": "missing.md",
                "reason": "target not found",
            },
            payload["stale_summary_entries"],
        )
        self.assertIn(
            {
                "file": "memory/knowledge/topic/orphan.md",
                "folder_summary": "memory/knowledge/topic/SUMMARY.md",
                "reason": "not mentioned in SUMMARY.md",
            },
            payload["orphaned_files"],
        )

    def test_memory_check_cross_references_can_skip_summary_checks(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/demo.md": "See [missing](missing.md).\n",
                "memory/working/projects/SUMMARY.md": "# Plans\n\n- [missing](missing.md)\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_check_cross_references"](
                    path="plans",
                    check_summaries=False,
                )
            )
        )

        self.assertEqual(payload["stats"]["summaries_checked"], 0)
        self.assertEqual(payload["orphaned_files"], [])
        self.assertEqual(payload["stale_summary_entries"], [])
        self.assertEqual(len(payload["broken_links"]), 2)

    def test_memory_check_cross_references_rejects_oversized_scan(self) -> None:
        files = {
            f"memory/knowledge/bulk/file-{idx:03d}.md": f"# File {idx}\n" for idx in range(501)
        }
        repo_root = self._init_repo(files)
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_check_cross_references"](path="memory/knowledge/bulk"))

    def test_memory_generate_summary_returns_standard_draft(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/alpha-note.md": """---
source: agent-generated
trust: medium
created: 2026-03-20
---

# Alpha Note

Alpha is the first concise summary paragraph.

More detail follows here.
""",
                "memory/knowledge/topic/beta-note.md": """---
source: user-stated
trust: high
last_verified: 2026-03-21
---

# Beta Note

Beta captures the second description block.
""",
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(tools["memory_generate_summary"](path="memory/knowledge/topic"))

        self.assertIn("<!-- Generated by memory_generate_summary on ", output)
        self.assertIn("# Topic -- Summary", output)
        self.assertIn("## Files", output)
        self.assertIn(
            "**[alpha-note.md](alpha-note.md)** -- Alpha is the first concise summary paragraph.",
            output,
        )
        self.assertIn("trust: medium", output)
        self.assertIn("source: user-stated", output)
        self.assertIn("<!-- Word count: ", output)

    def test_memory_generate_summary_references_summarized_subfolders(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/root-note.md": "# Root Note\n\nRoot description.\n",
                "memory/knowledge/topic/subtopic/SUMMARY.md": "# Subtopic -- Summary\n",
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(tools["memory_generate_summary"](path="memory/knowledge/topic"))

        self.assertIn("## Subfolders", output)
        self.assertIn("- **subtopic/** -- See [subtopic/SUMMARY.md](subtopic/SUMMARY.md)", output)

    def test_memory_generate_summary_supports_detailed_style(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic/detail-note.md": """---
source: agent-generated
trust: medium
created: 2026-03-20
---

# Detail Note

Detailed descriptions should preserve the first paragraph.
""",
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(
            tools["memory_generate_summary"](path="memory/knowledge/topic", style="detailed")
        )

        self.assertIn("Title: Detail Note.", output)
        self.assertIn(
            "Metadata: trust: medium; source: agent-generated; verified: 2026-03-20.", output
        )

    def test_memory_generate_names_index_returns_structured_payload(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/philosophy/simone-weil.md": """---
source: test
created: 2026-03-20
trust: medium
---

# Simone Weil: attention and obligation

Primary body.

## Reception (Iris Murdoch)

Secondary body.
""",
                "memory/knowledge/philosophy/_unverified/draft.md": "# Draft Person: should not appear\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_generate_names_index"]()))

        self.assertEqual(payload["knowledge_path"], "memory/knowledge")
        self.assertEqual(payload["output_path"], "memory/knowledge/NAMES.md")
        self.assertEqual(payload["files_scanned"], 1)
        self.assertGreaterEqual(payload["names_count"], 2)
        self.assertIn("### Simone Weil", payload["draft"])
        self.assertIn("### Iris Murdoch", payload["draft"])
        self.assertIn("[philosophy/simone-weil.md](philosophy/simone-weil.md)", payload["draft"])

    def test_memory_generate_names_index_rejects_non_knowledge_paths(self) -> None:
        repo_root = self._init_repo({"memory/users/profile.md": "# Profile\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_generate_names_index"](path="memory/users"))

    def test_memory_generate_summary_rejects_unknown_style(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/topic/note.md": "# Note\n\nBody.\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_generate_summary"](path="memory/knowledge/topic", style="compact")
            )

    def test_memory_generate_summary_detects_project_folder(self) -> None:
        """Project folders get the cold-start briefing, not the folder listing."""
        repo_root = self._init_repo(
            {
                "memory/working/projects/sample-project/SUMMARY.md": (
                    "---\n"
                    "active_plans: 1\n"
                    "canonical_source: https://example.com/upstream/repo@abc123\n"
                    "cognitive_mode: planning\n"
                    "created: 2026-03-28\n"
                    "current_focus: Sample focus.\n"
                    "last_activity: 2026-03-28\n"
                    "open_questions: 0\n"
                    "origin_session: memory/activity/2026/03/28/chat-001\n"
                    "plans: 1\n"
                    "source: agent-generated\n"
                    "status: active\n"
                    "trust: medium\n"
                    "type: project\n"
                    "---\n"
                    "\n"
                    "# Project: Sample Project\n"
                    "\n"
                    "## Description\n"
                    "Sample description body.\n"
                ),
                "memory/working/projects/sample-project/plans/main.yaml": (
                    "id: main\nproject: sample-project\nstatus: active\n"
                ),
                "memory/working/projects/sample-project/questions.md": (
                    "---\nopen_questions: 2\n---\n\n## q-001: First?\n## q-002: Second?\n"
                ),
            }
        )
        tools = self._create_tools(repo_root)

        output = asyncio.run(
            tools["memory_generate_summary"](path="memory/working/projects/sample-project")
        )

        # Project-mode output uses the project-briefing layout, not the folder-listing one.
        self.assertIn("# Project: Sample Project", output)
        self.assertIn("## Description", output)
        self.assertIn("## Layout", output)
        self.assertIn("- [IN/](memory/working/projects/sample-project/IN/)", output)
        self.assertIn("## Canonical source", output)
        self.assertIn("- https://example.com/upstream/repo@abc123", output)
        self.assertIn("## How to continue", output)
        self.assertIn(
            "Active plan: [memory/working/projects/sample-project/plans/main.yaml]",
            output,
        )
        self.assertIn(
            "Open questions: [memory/working/projects/sample-project/questions.md]",
            output,
        )
        self.assertIn("(2 open)", output)
        self.assertIn("Last activity: 2026-03-28", output)
        # The generic folder-listing "## Files" section must not appear in project mode.
        self.assertNotIn("## Files", output)

    def test_memory_access_analytics_classifies_policy_buckets(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "file": "memory/knowledge/core.md",
                                "task": "analysis",
                                "helpfulness": 0.8,
                            }
                        )
                        for _ in range(5)
                    ]
                    + [
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "file": "memory/knowledge/retire.md",
                                "task": "analysis",
                                "helpfulness": 0.2,
                            }
                        )
                        for _ in range(4)
                    ]
                    + [
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "file": "memory/knowledge/gem.md",
                                "task": "analysis",
                                "helpfulness": 0.6,
                            }
                        )
                        for _ in range(2)
                    ]
                )
                + "\n",
                "memory/knowledge/core.md": "# Core\n",
                "memory/knowledge/retire.md": "# Retire\n",
                "memory/knowledge/gem.md": "# Gem\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_access_analytics"](folders="knowledge"))
        )

        self.assertEqual(payload["total_entries"], 11)
        self.assertEqual(payload["unique_files"], 3)
        self.assertIn(
            {"file": "memory/knowledge/core.md", "access_count": 5, "mean_helpfulness": 0.8},
            payload["categories"]["core_memory"],
        )
        self.assertIn(
            {"file": "memory/knowledge/retire.md", "access_count": 4, "mean_helpfulness": 0.2},
            payload["categories"]["retirement_candidate"],
        )
        self.assertIn(
            {"file": "memory/knowledge/gem.md", "access_count": 2, "mean_helpfulness": 0.6},
            payload["categories"]["hidden_gem"],
        )
        self.assertIn(
            {
                "file": "memory/knowledge/core.md",
                "action": "enrich_cross_refs",
                "reason": "Core memory: 5 accesses, 0.800 mean helpfulness",
            },
            payload["suggested_actions"],
        )
        self.assertEqual(
            payload["top_accessed"][0], {"file": "memory/knowledge/core.md", "count": 5}
        )
        self.assertEqual(payload["thresholds"]["policy_source"], "governance/curation-policy.md")

    def test_memory_access_analytics_handles_empty_logs(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/ACCESS.jsonl": ""})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_access_analytics"]()))

        self.assertEqual(payload["total_entries"], 0)
        self.assertEqual(payload["unique_files"], 0)
        self.assertEqual(payload["categories"]["core_memory"], [])
        self.assertEqual(payload["top_accessed"], [])
        self.assertEqual(payload["least_accessed"], [])

    def test_memory_diff_branch_reports_branch_divergence(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/base.md": "# Base\n",
            }
        )
        subprocess.run(
            ["git", "branch", "-M", "core"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "feature/curation"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        self._write_and_commit(
            repo_root,
            {
                "memory/knowledge/new-note.md": "# New\n",
                "governance/policy-note.md": "# Policy\n",
                "notes.txt": "plain text\n",
            },
            "feature change",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_diff_branch"](base="core")))

        self.assertEqual(payload["base_branch"], "core")
        self.assertEqual(payload["current_branch"], "feature/curation")
        self.assertEqual(payload["commits_ahead"], 1)
        self.assertEqual(payload["files_changed"], 3)
        self.assertEqual(payload["by_category"]["knowledge"]["added"], 1)
        self.assertEqual(payload["by_category"]["meta"]["added"], 1)
        self.assertEqual(payload["by_category"]["other"]["added"], 1)
        self.assertEqual(payload["recent_commits"][0]["message"], "feature change")

    def test_memory_diff_branch_returns_clear_error_for_missing_base(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/base.md": "# Base\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_diff_branch"](base="missing-base"))
        )

        self.assertIn("error", payload)
        self.assertEqual(payload["base_branch"], "missing-base")
        self.assertIn("could not be fetched from origin", payload["error"])

    def test_memory_delete_rejects_repo_root_files(self) -> None:
        repo_root = self._init_repo_with_file("README.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(tools["memory_delete"](path="README.md"))

    def test_memory_write_rejects_repo_root_files(self) -> None:
        repo_root = self._init_repo_with_file("README.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(tools["memory_write"](path="README.md", content="# Rewritten\n"))

    def test_memory_edit_rejects_repo_root_files(self) -> None:
        repo_root = self._init_repo({"agent-bootstrap.toml": 'router = "README.md"\n'})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_edit"](
                    path="agent-bootstrap.toml",
                    old_string="README.md",
                    new_string="core/INIT.md",
                )
            )

    def test_memory_update_frontmatter_rejects_repo_root_files(self) -> None:
        repo_root = self._init_repo(
            {
                "README.md": "---\ntitle: README\n---\n\n# Project\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_update_frontmatter"](
                    path="README.md",
                    updates='{"title": "Updated"}',
                )
            )

    def test_memory_move_rejects_repo_root_source_files(self) -> None:
        repo_root = self._init_repo_with_file("README.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_move"](
                    source="README.md",
                    dest="memory/knowledge/README.md",
                )
            )

    def test_memory_move_rejects_protected_identity_destination(self) -> None:
        repo_root = self._init_repo_with_file("memory/knowledge/note.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_move"](
                    source="memory/knowledge/note.md",
                    dest="memory/users/note.md",
                )
            )

    def test_memory_move_rejects_protected_meta_destination(self) -> None:
        repo_root = self._init_repo_with_file("memory/working/projects/note.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_move"](
                    source="memory/working/projects/note.md",
                    dest="governance/note.md",
                )
            )

    def test_memory_move_rejects_protected_skills_destination(self) -> None:
        repo_root = self._init_repo_with_file("memory/working/notes/note.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_move"](
                    source="memory/working/notes/note.md",
                    dest="memory/skills/note.md",
                )
            )

    def test_memory_move_rejects_protected_chats_destination(self) -> None:
        repo_root = self._init_repo_with_file("memory/knowledge/note.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_move"](
                    source="memory/knowledge/note.md",
                    dest="memory/activity/2026/03/19/chat-001/note.md",
                )
            )

    def test_memory_move_allows_knowledge_destination(self) -> None:
        repo_root = self._init_repo_with_file("memory/knowledge/old/note.md")
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_move"](
                source="memory/knowledge/old/note.md",
                dest="memory/knowledge/new/note.md",
            )
        )

        self.assertTrue((repo_root / "memory" / "knowledge" / "new" / "note.md").exists())

    def test_memory_delete_handles_dash_prefixed_filename(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/-danger.md": "# Danger\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(tools["memory_delete"](path="memory/knowledge/-danger.md"))

        self.assertFalse((repo_root / "memory" / "knowledge" / "-danger.md").exists())

    def test_memory_move_handles_dash_prefixed_filename(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/-danger.md": "# Danger\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_move"](
                source="memory/knowledge/-danger.md",
                dest="memory/knowledge/archive/safe.md",
            )
        )

        self.assertFalse((repo_root / "memory" / "knowledge" / "-danger.md").exists())
        self.assertTrue((repo_root / "memory" / "knowledge" / "archive" / "safe.md").exists())

    def test_memory_add_knowledge_file_requires_low_trust_and_session_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: django -->
### Django

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_add_knowledge_file"](
                    path="memory/knowledge/_unverified/django/test.md",
                    content="# Test\n",
                    source="external-research",
                    session_id="memory/activity/2026/03/19/chat-001",
                    trust="high",
                )
            )

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_add_knowledge_file"](
                    path="memory/knowledge/_unverified/django/test.md",
                    content="# Test\n",
                    source="external-research",
                    session_id="chat-001",
                )
            )

    def test_memory_add_knowledge_file_writes_unverified_file_and_updates_summary(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: django -->
### Django

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        result = json.loads(
            asyncio.run(
                tools["memory_add_knowledge_file"](
                    path="memory/knowledge/_unverified/django/test.md",
                    content="# Test Note\n\nBody\n",
                    source="external-research",
                    session_id="memory/activity/2026/03/19/chat-001",
                    expires="2026-04-30",
                )
            )
        )

        file_text = (
            repo_root / "memory" / "knowledge" / "_unverified" / "django" / "test.md"
        ).read_text(encoding="utf-8")
        summary_text = (
            repo_root / "memory" / "knowledge" / "_unverified" / "SUMMARY.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(result["commit_message"], "[knowledge] Add test.md")
        self.assertIn("version_token", result["new_state"])
        self.assertIn("source: external-research", file_text)
        self.assertIn("trust: low", file_text)
        self.assertIn("origin_session: memory/activity/2026/03/19/chat-001", file_text)
        self.assertIn("2026-04-30", file_text)
        self.assertIn("# Test Note", file_text)
        self.assertIn(
            "**[test.md](memory/knowledge/_unverified/django/test.md)** — Test Note",
            summary_text,
        )

    def test_memory_add_knowledge_file_preview_returns_governed_preview_without_mutation(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: django -->
### Django

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._preview_tool(
            tools,
            "memory_add_knowledge_file",
            path="memory/knowledge/_unverified/django/test.md",
            content="# Test Note\n\nBody\n",
            source="external-research",
            session_id="memory/activity/2026/03/19/chat-001",
        )

        self.assertIsNone(payload["commit_sha"])
        self.assertEqual(
            payload["new_state"]["path"], "memory/knowledge/_unverified/django/test.md"
        )
        self.assertEqual(payload["preview"]["mode"], "preview")
        self.assertEqual(
            payload["preview"]["target_files"][0]["path"],
            "memory/knowledge/_unverified/django/test.md",
        )
        self.assertIn("# Test Note", payload["preview"]["content_preview"])
        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "_unverified" / "django" / "test.md").exists()
        )

    def test_memory_plan_create_rejects_noncanonical_session_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-21\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-21\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-21\ncurrent_focus: Example project.\n---\n\n# Project: Example\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_plan_create"](
                    plan_id="test-plan",
                    project_id="example",
                    purpose_summary="Test",
                    purpose_context="desc",
                    phases=[
                        {
                            "id": "phase-a",
                            "title": "Do it",
                            "changes": [
                                {
                                    "path": "memory/working/projects/example/notes/step.md",
                                    "action": "create",
                                    "description": "Write the step note.",
                                }
                            ],
                        }
                    ],
                    session_id="chat-001",
                )
            )

    def test_memory_plan_create_uses_purpose_summary_in_project_navigation(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-21\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-21\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-21\ncurrent_focus: Investigate regressions.\n---\n\n# Project: Example\n",
            }
        )
        tools = self._create_tools(repo_root)

        asyncio.run(
            tools["memory_plan_create"](
                plan_id="test-plan",
                project_id="example",
                purpose_summary="Test Plan",
                purpose_context="Investigate regressions",
                phases=[
                    {
                        "id": "phase-a",
                        "title": "Do the first thing",
                        "changes": [
                            {
                                "path": "memory/working/projects/example/notes/first.md",
                                "action": "create",
                                "description": "Capture the first investigation step.",
                            }
                        ],
                    }
                ],
                session_id="memory/activity/2026/03/19/chat-001",
            )
        )

        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "test-plan.yaml"
            ).read_text(encoding="utf-8")
        )
        project_frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory" / "working" / "projects" / "example" / "SUMMARY.md"
        )
        summary = (repo_root / "memory" / "working" / "projects" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(plan_body["purpose"]["summary"], "Test Plan")
        self.assertEqual(project_frontmatter["active_plans"], 1)
        self.assertIn("| example | active | exploration | 0 | Investigate regressions. |", summary)

    def test_memory_plan_create_preview_does_not_write_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-21\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-21\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-21\ncurrent_focus: Preview the plan write.\n---\n\n# Project: Example\n",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_plan_create"](
                    plan_id="preview-plan",
                    project_id="example",
                    purpose_summary="Preview Plan",
                    purpose_context="Preview the plan write",
                    phases=[
                        {
                            "id": "phase-a",
                            "title": "Do the previewed thing",
                            "changes": [
                                {
                                    "path": "memory/working/projects/example/notes/preview.md",
                                    "action": "create",
                                    "description": "Capture the preview step.",
                                }
                            ],
                        }
                    ],
                    session_id="memory/activity/2026/03/19/chat-001",
                    preview=True,
                )
            )
        )

        self.assertFalse(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "preview-plan.yaml"
            ).exists()
        )
        self.assertEqual(preview["preview"]["mode"], "preview")
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            "[plan] Create preview-plan",
        )

        applied = json.loads(
            asyncio.run(
                tools["memory_plan_create"](
                    plan_id="preview-plan",
                    project_id="example",
                    purpose_summary="Preview Plan",
                    purpose_context="Preview the plan write",
                    phases=[
                        {
                            "id": "phase-a",
                            "title": "Do the previewed thing",
                            "changes": [
                                {
                                    "path": "memory/working/projects/example/notes/preview.md",
                                    "action": "create",
                                    "description": "Capture the preview step.",
                                }
                            ],
                        }
                    ],
                    session_id="memory/activity/2026/03/19/chat-001",
                )
            )
        )

        self.assertTrue(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "preview-plan.yaml"
            ).exists()
        )
        self.assertEqual(applied["commit_message"], "[plan] Create preview-plan")
        self.assertEqual(applied["preview"]["mode"], "apply")
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])

    def test_memory_plan_create_preview_returns_structured_validation_feedback(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-21\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-21\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-21\ncurrent_focus: Preview invalid plan input.\n---\n\n# Project: Example\n",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_plan_create"](
                    plan_id="invalid-preview-plan",
                    project_id="example",
                    purpose_summary="Invalid preview",
                    purpose_context="Return structured validation feedback.",
                    phases=[
                        {
                            "id": "phase-a",
                            "title": "Do the thing",
                            "sources": [
                                {
                                    "path": "memory/working/notes/reference.md",
                                    "type": "bogus",
                                    "intent": "Read the reference.",
                                }
                            ],
                            "postconditions": [
                                {"description": "Output exists", "type": "check"},
                            ],
                            "changes": [
                                {
                                    "path": "memory/working/projects/example/notes/output.md",
                                    "action": "bogus",
                                    "description": "Write output note.",
                                }
                            ],
                        }
                    ],
                    session_id="memory/activity/2026/03/19/chat-001",
                    preview=True,
                )
            )
        )

        self.assertEqual(preview["preview"]["mode"], "preview")
        self.assertEqual(preview["files_changed"], [])
        self.assertIsNone(preview["commit_message"])
        self.assertFalse(preview["new_state"]["valid"])
        self.assertEqual(preview["preview"]["resulting_state"]["schema_tool"], "memory_plan_schema")
        self.assertEqual(len(preview["new_state"]["errors"]), 3)
        self.assertTrue(
            any("work.phases[0].sources[0]" in error for error in preview["new_state"]["errors"])
        )
        self.assertTrue(
            any(
                "work.phases[0].postconditions[0]" in error
                for error in preview["new_state"]["errors"]
            )
        )
        self.assertTrue(
            any("work.phases[0].changes[0]" in error for error in preview["new_state"]["errors"])
        )
        self.assertFalse(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "invalid-preview-plan.yaml"
            ).exists()
        )

    def test_memory_plan_create_preview_aggregates_top_level_and_nested_validation_feedback(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-21\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-21\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-21\ncurrent_focus: Preview aggregated validation feedback.\n---\n\n# Project: Example\n",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_plan_create"](
                    plan_id="invalid-preview-plan",
                    project_id="example",
                    purpose_summary="   ",
                    purpose_context="",
                    phases=[
                        {
                            "id": "phase-a",
                            "title": "Do the thing",
                            "postconditions": [
                                {"description": "Output exists", "type": "check"},
                            ],
                            "changes": [
                                {
                                    "path": "memory/working/projects/example/notes/output.md",
                                    "action": "bogus",
                                    "description": "Write output note.",
                                }
                            ],
                        }
                    ],
                    session_id="chat-001",
                    questions=cast(Any, "not-a-list"),
                    budget={"deadline": "April 3, 2026", "max_sessions": "zero"},
                    status="paused",
                    preview=True,
                )
            )
        )

        errors = preview["new_state"]["errors"]

        self.assertFalse(preview["new_state"]["valid"])
        self.assertGreaterEqual(len(errors), 8)
        self.assertTrue(any("session_id" in error for error in errors))
        self.assertTrue(any("memory_plan_create status" in error for error in errors))
        self.assertTrue(any("purpose.summary" in error for error in errors))
        self.assertTrue(any("purpose.context" in error for error in errors))
        self.assertTrue(any("purpose.questions must be a list" in error for error in errors))
        self.assertTrue(any("budget.deadline" in error for error in errors))
        self.assertTrue(any("budget.max_sessions" in error for error in errors))
        self.assertTrue(any("work.phases[0].postconditions[0]" in error for error in errors))
        self.assertTrue(any("work.phases[0].changes[0]" in error for error in errors))

    def test_memory_plan_create_invalid_input_still_raises_without_preview(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-21\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-21\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-21\ncurrent_focus: Reject invalid plan input outside preview.\n---\n\n# Project: Example\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_plan_create"](
                    plan_id="invalid-apply-plan",
                    project_id="example",
                    purpose_summary="Invalid apply",
                    purpose_context="Still strict outside preview.",
                    phases=[
                        {
                            "id": "phase-a",
                            "title": "Do the thing",
                            "postconditions": [
                                {"description": "Output exists", "type": "check"},
                            ],
                            "changes": [
                                {
                                    "path": "memory/working/projects/example/notes/output.md",
                                    "action": "bogus",
                                    "description": "Write output note.",
                                }
                            ],
                        }
                    ],
                    session_id="memory/activity/2026/03/19/chat-001",
                )
            )

    def test_memory_promote_knowledge_preview_does_not_move_file_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/_unverified/django/note.md": """---
created: 2026-03-20
source: test
trust: low
---

# Note
""",
                "memory/knowledge/_unverified/SUMMARY.md": """<!-- section: django -->
### Django
- **[note.md](memory/knowledge/_unverified/django/note.md)** — Note

---
""",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n\n---\n",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge"](
                    source_path="memory/knowledge/_unverified/django/note.md",
                    trust_level="medium",
                    summary_entry="- **[note.md](memory/knowledge/django/note.md)** — Note",
                    preview=True,
                )
            )
        )

        self.assertTrue(
            (repo_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md").exists()
        )
        self.assertFalse((repo_root / "memory" / "knowledge" / "django" / "note.md").exists())
        self.assertEqual(preview["preview"]["mode"], "preview")

        applied = json.loads(
            asyncio.run(
                tools["memory_promote_knowledge"](
                    source_path="memory/knowledge/_unverified/django/note.md",
                    trust_level="medium",
                    summary_entry="- **[note.md](memory/knowledge/django/note.md)** — Note",
                )
            )
        )

        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md").exists()
        )
        self.assertTrue((repo_root / "memory" / "knowledge" / "django" / "note.md").exists())
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            applied["commit_message"],
        )

    def test_memory_demote_knowledge_preview_does_not_move_file_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/django/note.md": """---
created: 2026-03-20
source: test
trust: high
last_verified: 2026-03-20
---

# Note
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: django -->
### Django
- **[note.md](memory/knowledge/django/note.md)** — Note

---
""",
                "memory/knowledge/_unverified/SUMMARY.md": """# Unverified Knowledge

<!-- section: django -->
### Django

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_demote_knowledge"](
                    source_path="memory/knowledge/django/note.md",
                    reason="needs review",
                    preview=True,
                )
            )
        )

        self.assertTrue((repo_root / "memory" / "knowledge" / "django" / "note.md").exists())
        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md").exists()
        )
        self.assertEqual(preview["preview"]["mode"], "preview")

        applied = json.loads(
            asyncio.run(
                tools["memory_demote_knowledge"](
                    source_path="memory/knowledge/django/note.md",
                    reason="needs review",
                )
            )
        )

        demoted_text = (
            repo_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md"
        ).read_text(encoding="utf-8")
        verified_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        unverified_summary = (
            repo_root / "memory" / "knowledge" / "_unverified" / "SUMMARY.md"
        ).read_text(encoding="utf-8")

        self.assertFalse((repo_root / "memory" / "knowledge" / "django" / "note.md").exists())
        self.assertTrue(
            (repo_root / "memory" / "knowledge" / "_unverified" / "django" / "note.md").exists()
        )
        self.assertIn("trust: low", demoted_text)
        self.assertIn("last_verified:", demoted_text)
        self.assertNotIn("memory/knowledge/django/note.md", verified_summary)
        self.assertIn("memory/knowledge/_unverified/django/note.md", unverified_summary)
        self.assertIn("_(demoted)_", unverified_summary)
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            applied["commit_message"],
        )

    def test_memory_archive_knowledge_preview_does_not_move_file_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/django/note.md": """---
created: 2026-03-20
source: test
trust: high
last_verified: 2026-03-20
---

# Note
""",
                "memory/knowledge/SUMMARY.md": """# Knowledge

<!-- section: django -->
### Django
- **[note.md](memory/knowledge/django/note.md)** — Note

---
""",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_archive_knowledge"](
                    source_path="memory/knowledge/django/note.md",
                    reason="stale",
                    preview=True,
                )
            )
        )

        self.assertTrue((repo_root / "memory" / "knowledge" / "django" / "note.md").exists())
        self.assertFalse(
            (repo_root / "memory" / "knowledge" / "_archive" / "django" / "note.md").exists()
        )
        self.assertEqual(preview["preview"]["mode"], "preview")

        applied = json.loads(
            asyncio.run(
                tools["memory_archive_knowledge"](
                    source_path="memory/knowledge/django/note.md",
                    reason="stale",
                )
            )
        )

        archived_text = (
            repo_root / "memory" / "knowledge" / "_archive" / "django" / "note.md"
        ).read_text(encoding="utf-8")
        summary_text = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        self.assertFalse((repo_root / "memory" / "knowledge" / "django" / "note.md").exists())
        self.assertTrue(
            (repo_root / "memory" / "knowledge" / "_archive" / "django" / "note.md").exists()
        )
        self.assertIn("status: archived", archived_text)
        self.assertIn("last_verified:", archived_text)
        self.assertNotIn("memory/knowledge/django/note.md", summary_text)
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            applied["commit_message"],
        )

    def test_memory_update_user_trait_rejects_non_slug_filename(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile
""",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_update_user_trait"](
                    file="../README",
                    key="tone",
                    value="direct",
                )
            )

    def test_memory_update_user_trait_replaces_existing_body_section(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile

## tone

Direct and concise.

## workflow

Structured.
""",
            }
        )
        tools = self._create_tools(repo_root)

        preview_token, _ = self._preview_token_for(
            tools,
            "memory_update_user_trait",
            file="profile",
            key="tone",
            value="Even more direct.",
            mode="upsert",
        )
        asyncio.run(
            tools["memory_update_user_trait"](
                file="profile",
                key="tone",
                value="Even more direct.",
                mode="upsert",
                preview_token=preview_token,
            )
        )

        updated = (repo_root / "memory" / "users" / "profile.md").read_text(encoding="utf-8")
        self.assertIn("## tone\n\nEven more direct.", updated)
        self.assertNotIn("Even more direct.\n\nDirect and concise.", updated)
        self.assertNotIn("Direct and concise.", updated)
        self.assertIn("## workflow\n\nStructured.", updated)

    def test_memory_update_user_trait_preview_does_not_write_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile

## tone

Direct and concise.
""",
            }
        )
        tools = self._create_tools(repo_root)

        preview_token, preview = self._preview_token_for(
            tools,
            "memory_update_user_trait",
            file="profile",
            key="tone",
            value="Even more direct.",
        )

        self.assertIn(
            "Direct and concise.",
            (repo_root / "memory" / "users" / "profile.md").read_text(encoding="utf-8"),
        )

        applied = self._load_tool_payload(
            asyncio.run(
                tools["memory_update_user_trait"](
                    file="profile",
                    key="tone",
                    value="Even more direct.",
                    preview_token=preview_token,
                )
            )
        )

        self.assertIn(
            "Even more direct.",
            (repo_root / "memory" / "users" / "profile.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            applied["commit_message"],
        )

    def test_memory_update_user_trait_requires_preview_token_for_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile
""",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError) as ctx:
            asyncio.run(
                tools["memory_update_user_trait"](
                    file="profile",
                    key="tone",
                    value="Even more direct.",
                )
            )

        self.assertIn("preview_token is required", str(ctx.exception))

    def test_memory_update_user_trait_rejects_invalid_provenance_until_repaired(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
foo: bar
---

# Profile
""",
            }
        )
        tools = self._create_tools(repo_root)
        profile_path = repo_root / "memory" / "users" / "profile.md"

        with self.assertRaises(self.errors.ValidationError) as ctx:
            self._preview_tool(
                tools,
                "memory_update_user_trait",
                file="profile",
                key="tone",
                value="Even more direct.",
            )

        self.assertIn("user frontmatter", str(ctx.exception))

        profile_path.write_text(
            """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile

## tone

Direct and concise.
""",
            encoding="utf-8",
        )

        preview_token, _ = self._preview_token_for(
            tools,
            "memory_update_user_trait",
            file="profile",
            key="tone",
            value="Even more direct.",
        )
        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_update_user_trait"](
                    file="profile",
                    key="tone",
                    value="Even more direct.",
                    preview_token=preview_token,
                )
            )
        )

        self.assertIsNotNone(payload["commit_sha"])
        self.assertIn("Even more direct.", profile_path.read_text(encoding="utf-8"))

    def test_memory_record_chat_summary_rejects_noncanonical_session_id(self) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_record_chat_summary"](
                    session_id="../meta/chat-001",
                    summary="# Chat Summary\n",
                )
            )

    def test_memory_record_chat_summary_replay_is_noop_when_content_matches(self) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-20T10:00:00Z", tick=False):
            first = json.loads(
                asyncio.run(
                    tools["memory_record_chat_summary"](
                        session_id="memory/activity/2026/03/20/chat-002",
                        summary="# Session Summary\n\nDid the work.\n",
                        key_topics="semantic-tools,wrapup",
                    )
                )
            )
        with time_machine.travel("2026-03-21T10:00:00Z", tick=False):
            replay = json.loads(
                asyncio.run(
                    tools["memory_record_chat_summary"](
                        session_id="memory/activity/2026/03/20/chat-002",
                        summary="# Session Summary\n\nDid the work.\n",
                        key_topics="semantic-tools,wrapup",
                    )
                )
            )

        session_summary = (
            repo_root / "memory" / "activity" / "2026" / "03" / "20" / "chat-002" / "SUMMARY.md"
        ).read_text(encoding="utf-8")
        log_count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(first["new_state"]["recording_outcome"], "recorded")
        self.assertIsNone(replay["commit_sha"])
        self.assertIsNone(replay["commit_message"])
        self.assertEqual(replay["files_changed"], [])
        self.assertEqual(replay["new_state"]["recording_outcome"], "already_recorded")
        self.assertIn("2026-03-20", session_summary)
        self.assertNotIn("2026-03-21", session_summary)
        self.assertEqual(log_count, "2")

    def test_memory_record_chat_summary_rejects_divergent_replay(self) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-20T10:00:00Z", tick=False):
            asyncio.run(
                tools["memory_record_chat_summary"](
                    session_id="memory/activity/2026/03/20/chat-002",
                    summary="# Session Summary\n\nDid the work.\n",
                    key_topics="semantic-tools,wrapup",
                )
            )

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_record_chat_summary"](
                    session_id="memory/activity/2026/03/20/chat-002",
                    summary="# Session Summary\n\nDid different work.\n",
                    key_topics="semantic-tools,wrapup",
                )
            )

    def test_memory_record_reflection_requires_summary_and_writes_file(self) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_record_reflection"](
                    session_id="memory/activity/2026/03/20/chat-004",
                    memory_retrieved="Referenced the prior summary.",
                    memory_influence="Guided the implementation choice.",
                    outcome_quality="Good outcome.",
                    gaps_noticed="Need better eval coverage.",
                )
            )

        asyncio.run(
            tools["memory_record_chat_summary"](
                session_id="memory/activity/2026/03/20/chat-004",
                summary="# Session Summary\n\nDid the work.\n",
            )
        )
        raw = asyncio.run(
            tools["memory_record_reflection"](
                session_id="memory/activity/2026/03/20/chat-004",
                memory_retrieved="Referenced the prior summary.",
                memory_influence="Guided the implementation choice.",
                outcome_quality="Good outcome.",
                gaps_noticed="Need better eval coverage.",
                system_observations="No tooling surprises.",
            )
        )
        payload = self._load_tool_payload(raw)

        reflection = (
            repo_root / "memory" / "activity" / "2026" / "03" / "20" / "chat-004" / "reflection.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            payload["commit_message"],
            "[chat] Add session reflection for memory/activity/2026/03/20/chat-004",
        )
        self.assertEqual(
            payload["new_state"]["reflection_path"],
            "memory/activity/2026/03/20/chat-004/reflection.md",
        )
        self.assertIn("**Memory retrieved:** Referenced the prior summary.\n", reflection)
        self.assertIn("**System observations:** No tooling surprises.\n", reflection)

    def test_memory_record_session_writes_summary_reflection_and_access_in_one_commit(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_record_session"](
                session_id="memory/activity/2026/03/20/chat-002",
                summary="# Session Summary\n\nDid the work.\n",
                reflection="Observed a cleaner wrap-up path.",
                key_topics="semantic-tools,wrapup",
                access_entries=[
                    {
                        "file": "memory/knowledge/topic.md",
                        "task": "session wrap-up",
                        "helpfulness": 0.8,
                        "note": "Relevant context for summary.",
                    },
                    {
                        "file": "memory/working/projects/demo.md",
                        "task": "session wrap-up",
                        "helpfulness": 0.6,
                        "note": "Referenced current work.",
                    },
                ],
            )
        )
        payload = self._load_tool_payload(raw)

        session_summary = (
            repo_root / "memory" / "activity" / "2026" / "03" / "20" / "chat-002" / "SUMMARY.md"
        ).read_text(encoding="utf-8")
        reflection = (
            repo_root / "memory" / "activity" / "2026" / "03" / "20" / "chat-002" / "reflection.md"
        ).read_text(encoding="utf-8")
        chats_summary = (repo_root / "memory" / "activity" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        knowledge_access = [
            json.loads(line)
            for line in (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        plans_access = [
            json.loads(line)
            for line in (repo_root / "memory" / "working" / "projects" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        log_count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(
            payload["commit_message"], "[chat] Record session memory/activity/2026/03/20/chat-002"
        )
        self.assertEqual(payload["new_state"]["session_id"], "memory/activity/2026/03/20/chat-002")
        self.assertIn("key_topics:", session_summary)
        self.assertIn("semantic-tools", session_summary)
        self.assertIn("## Session reflection\n\nObserved a cleaner wrap-up path.\n", reflection)
        self.assertIn("memory/activity/2026/03/20/chat-002/", chats_summary)
        self.assertEqual(knowledge_access[0]["session_id"], "memory/activity/2026/03/20/chat-002")
        self.assertEqual(plans_access[0]["session_id"], "memory/activity/2026/03/20/chat-002")
        self.assertEqual(log_count, "2")

    def test_memory_record_session_replay_is_noop_when_content_matches(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        tools = self._create_tools(repo_root)

        kwargs = {
            "session_id": "memory/activity/2026/03/20/chat-002",
            "summary": "# Session Summary\n\nDid the work.\n",
            "reflection": "Observed a cleaner wrap-up path.",
            "key_topics": "semantic-tools,wrapup",
            "access_entries": [
                {
                    "file": "memory/knowledge/topic.md",
                    "task": "session wrap-up",
                    "helpfulness": 0.8,
                    "note": "Relevant context for summary.",
                },
                {
                    "file": "memory/working/projects/demo.md",
                    "task": "session wrap-up",
                    "helpfulness": 0.6,
                    "note": "Referenced current work.",
                },
            ],
        }

        with time_machine.travel("2026-03-20T10:00:00Z", tick=False):
            first = json.loads(asyncio.run(tools["memory_record_session"](**kwargs)))
        with time_machine.travel("2026-03-21T10:00:00Z", tick=False):
            replay = json.loads(asyncio.run(tools["memory_record_session"](**kwargs)))

        session_summary = (
            repo_root / "memory" / "activity" / "2026" / "03" / "20" / "chat-002" / "SUMMARY.md"
        ).read_text(encoding="utf-8")
        knowledge_access = [
            json.loads(line)
            for line in (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        plans_access = [
            json.loads(line)
            for line in (repo_root / "memory" / "working" / "projects" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        log_count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(first["new_state"]["recording_outcome"], "recorded")
        self.assertIsNone(replay["commit_sha"])
        self.assertEqual(replay["files_changed"], [])
        self.assertEqual(replay["new_state"]["recording_outcome"], "already_recorded")
        self.assertEqual(len(knowledge_access), 1)
        self.assertEqual(len(plans_access), 1)
        self.assertIn("2026-03-20", session_summary)
        self.assertEqual(log_count, "2")

    def test_memory_record_session_rejects_divergent_replay(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
            }
        )
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-20T10:00:00Z", tick=False):
            asyncio.run(
                tools["memory_record_session"](
                    session_id="memory/activity/2026/03/20/chat-002",
                    summary="# Session Summary\n\nDid the work.\n",
                    reflection="Observed a cleaner wrap-up path.",
                    key_topics="semantic-tools,wrapup",
                    access_entries=[
                        {
                            "file": "memory/knowledge/topic.md",
                            "task": "session wrap-up",
                            "helpfulness": 0.8,
                            "note": "Relevant context for summary.",
                        }
                    ],
                )
            )

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_record_session"](
                    session_id="memory/activity/2026/03/20/chat-002",
                    summary="# Session Summary\n\nDid the work.\n",
                    reflection="Observed a different wrap-up path.",
                    key_topics="semantic-tools,wrapup",
                    access_entries=[
                        {
                            "file": "memory/knowledge/topic.md",
                            "task": "session wrap-up",
                            "helpfulness": 0.8,
                            "note": "Relevant context for summary.",
                        }
                    ],
                )
            )

    def test_memory_record_session_reports_multiple_access_entry_validation_errors(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError) as ctx:
            asyncio.run(
                tools["memory_record_session"](
                    session_id="memory/activity/2026/03/20/chat-003",
                    summary="# Session Summary\n\nDid the work.\n",
                    access_entries=[
                        {
                            "file": "memory/knowledge/topic.md",
                            "task": "",
                            "helpfulness": 0.8,
                            "note": "missing task",
                        },
                        {
                            "file": "memory/working/projects/demo.md",
                            "task": "session wrap-up",
                            "helpfulness": 1.5,
                            "note": "bad helpfulness",
                        },
                    ],
                )
            )

        message = str(ctx.exception)
        self.assertIn("ACCESS entry validation failed", message)
        self.assertIn("memory/knowledge/topic.md", message)
        self.assertIn("memory/working/projects/demo.md", message)
        self.assertFalse(
            (
                repo_root / "memory" / "activity" / "2026" / "03" / "20" / "chat-003" / "SUMMARY.md"
            ).exists()
        )
        self.assertFalse((repo_root / "memory" / "knowledge" / "ACCESS.jsonl").exists())
        self.assertFalse((repo_root / "memory" / "working" / "projects" / "ACCESS.jsonl").exists())

    def test_memory_checkpoint_writes_timestamped_entry_without_commit(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Current\n"})
        tools = self._create_tools(repo_root)
        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        with time_machine.travel("2026-03-29T09:10:00Z", tick=False):
            raw = asyncio.run(
                tools["memory_checkpoint"](
                    content="Decision captured.",
                    label="Decision",
                )
            )
        payload = self._load_tool_payload(raw)

        current = (repo_root / "memory" / "working" / "CURRENT.md").read_text(encoding="utf-8")
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertIsNone(payload["commit_sha"])
        self.assertIsNone(payload["commit_message"])
        self.assertEqual(payload["new_state"]["target"], "memory/working/CURRENT.md")
        self.assertEqual(payload["new_state"]["entry_count"], 1)
        self.assertTrue(payload["new_state"]["staged"])
        self.assertIn("### [2026-03-29T09:10] Decision\nDecision captured.\n", current)
        self.assertEqual(head_after, head_before)
        self.assertEqual(staged.strip(), "core/memory/working/CURRENT.md")

    def test_memory_checkpoint_treats_label_as_optional(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Current\n"})
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-29T09:10:00Z", tick=False):
            asyncio.run(tools["memory_checkpoint"](content="Plain note."))

        current = (repo_root / "memory" / "working" / "CURRENT.md").read_text(encoding="utf-8")

        self.assertIn("### [2026-03-29T09:10]\nPlain note.\n", current)

    def test_memory_checkpoint_includes_session_comment_and_validates_session_id(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Current\n"})
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-29T09:10:00Z", tick=False):
            raw = asyncio.run(
                tools["memory_checkpoint"](
                    content="Recovered parser design.",
                    session_id="memory/activity/2026/03/29/chat-001",
                )
            )
        payload = self._load_tool_payload(raw)
        current = (repo_root / "memory" / "working" / "CURRENT.md").read_text(encoding="utf-8")

        self.assertEqual(
            payload["new_state"]["session_id"],
            "memory/activity/2026/03/29/chat-001",
        )
        self.assertIn(
            "<!-- session_id: memory/activity/2026/03/29/chat-001 -->\nRecovered parser design.\n",
            current,
        )

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_checkpoint"](
                    content="Bad session.",
                    session_id="chat-001",
                )
            )

    def test_memory_checkpoint_accumulates_entries_in_current(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Current\n"})
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-29T09:10:00Z", tick=False):
            asyncio.run(tools["memory_checkpoint"](content="First note.", label="One"))
        with time_machine.travel("2026-03-29T09:15:00Z", tick=False):
            raw = asyncio.run(tools["memory_checkpoint"](content="Second note.", label="Two"))
        payload = self._load_tool_payload(raw)

        current = (repo_root / "memory" / "working" / "CURRENT.md").read_text(encoding="utf-8")
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertEqual(payload["new_state"]["entry_count"], 2)
        self.assertEqual(current.count("### [2026-03-29T09:"), 2)
        self.assertIn("---", current)
        self.assertIn("core/memory/working/CURRENT.md", staged)

    def test_memory_checkpoint_creates_current_and_appends_after_existing_content(self) -> None:
        repo_root = self._init_repo({"memory/working/USER.md": "# User\n"})
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-29T09:10:00Z", tick=False):
            asyncio.run(tools["memory_checkpoint"](content="Created current."))

        created = (repo_root / "memory" / "working" / "CURRENT.md").read_text(encoding="utf-8")
        self.assertIn("### [2026-03-29T09:10]\nCreated current.\n", created)

        repo_root = self._init_repo(
            {"memory/working/CURRENT.md": "# Current\n\nExisting scratchpad note.\n"}
        )
        tools = self._create_tools(repo_root)
        with time_machine.travel("2026-03-29T09:10:00Z", tick=False):
            asyncio.run(tools["memory_checkpoint"](content="Appended note."))

        appended = (repo_root / "memory" / "working" / "CURRENT.md").read_text(encoding="utf-8")
        self.assertIn(
            "Existing scratchpad note.\n\n---\n\n### [2026-03-29T09:10]\nAppended note.\n", appended
        )

    def test_memory_session_flush_writes_checkpoint_and_commits(self) -> None:
        repo_root = self._init_repo({"memory/working/USER.md": "# User\n"})
        tools = self._create_tools(repo_root)
        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        with time_machine.travel("2026-03-29T09:20:00Z", tick=False):
            raw = asyncio.run(
                tools["memory_session_flush"](
                    summary="Decision: enable token-aware compaction monitoring.",
                    session_id="memory/activity/2026/03/29/chat-002",
                    label="Proxy compaction",
                )
            )
        payload = self._load_tool_payload(raw)

        checkpoint = (
            repo_root / "memory" / "activity" / "2026" / "03" / "29" / "chat-002" / "checkpoint.md"
        ).read_text(encoding="utf-8")
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertNotEqual(head_after, head_before)
        self.assertEqual(payload["commit_sha"], head_after)
        self.assertEqual(
            payload["commit_message"], "[chat] Context-pressure flush - Proxy compaction"
        )
        self.assertEqual(
            payload["new_state"]["checkpoint_path"],
            "memory/activity/2026/03/29/chat-002/checkpoint.md",
        )
        self.assertEqual(payload["new_state"]["entry_count"], 1)
        self.assertEqual(payload["new_state"]["trigger"], "context-pressure")
        self.assertIn("### [2026-03-29T09:20] Proxy compaction\n", checkpoint)
        self.assertIn(
            "<!-- session_id: memory/activity/2026/03/29/chat-002 -->\n",
            checkpoint,
        )
        self.assertIn("Decision: enable token-aware compaction monitoring.\n", checkpoint)
        self.assertEqual(staged.strip(), "")

    def test_memory_session_flush_uses_current_session_sentinel_when_missing_session_id(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/USER.md": "# User\n",
                "memory/activity/CURRENT_SESSION": "memory/activity/2026/03/29/chat-003\n",
            }
        )
        tools = self._create_tools(repo_root)

        with patch.dict(os.environ, {"MEMORY_SESSION_ID": ""}):
            with time_machine.travel("2026-03-29T09:25:00Z", tick=False):
                raw = asyncio.run(
                    tools["memory_session_flush"](
                        summary="Recovered the current session via sentinel.",
                    )
                )
        payload = self._load_tool_payload(raw)

        checkpoint = (
            repo_root / "memory" / "activity" / "2026" / "03" / "29" / "chat-003" / "checkpoint.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(payload["new_state"]["session_id"], "memory/activity/2026/03/29/chat-003")
        self.assertIn("Recovered the current session via sentinel.\n", checkpoint)

    def test_memory_session_flush_requires_resolvable_session_id(self) -> None:
        repo_root = self._init_repo({"memory/working/USER.md": "# User\n"})
        tools = self._create_tools(repo_root)

        with patch.dict(os.environ, {"MEMORY_SESSION_ID": ""}):
            with self.assertRaises(self.errors.ValidationError):
                asyncio.run(
                    tools["memory_session_flush"](
                        summary="No active session available.",
                    )
                )

    def test_memory_append_scratchpad_accepts_dated_slug_and_creates_file(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Current\n"})
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_append_scratchpad"](
                target="memory/working/notes/2026-03-20-worklog.md",
                content="Initial note",
                section="Findings",
            )
        )
        payload = json.loads(raw)

        scratchpad = (
            repo_root / "memory" / "working" / "notes" / "2026-03-20-worklog.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            payload["new_state"]["target"],
            "memory/working/notes/2026-03-20-worklog.md",
        )
        self.assertIn("## Findings\n\nInitial note\n", scratchpad)

    def test_memory_append_scratchpad_rejects_invalid_target_format(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Current\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_append_scratchpad"](
                    target="memory/working/notes/not valid.md",
                    content="Invalid",
                )
            )

    def test_memory_flag_for_review_returns_item_id_and_uses_canonical_format(self) -> None:
        repo_root = self._init_repo(
            {
                "governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_flag_for_review"](
                path="memory/working/projects/demo.md",
                reason="Needs human review before promotion.",
                priority="urgent",
            )
        )
        payload = json.loads(raw)
        review_queue = (repo_root / "governance" / "review-queue.md").read_text(encoding="utf-8")

        self.assertEqual(payload["new_state"]["flagged_path"], "memory/working/projects/demo.md")
        self.assertRegex(
            payload["new_state"]["item_id"],
            r"^\d{4}-\d{2}-\d{2}-review-memory-working-projects-demo-md$",
        )
        self.assertIn("### [", review_queue)
        self.assertIn("**Item ID:** ", review_queue)
        self.assertIn("**Type:** proposed", review_queue)
        self.assertNotIn("_No pending items._", review_queue)

    def test_memory_resolve_review_item_moves_entry_to_resolved_section(self) -> None:
        repo_root = self._init_repo(
            {
                "governance/review-queue.md": """# Review Queue

### [2026-03-20] Review memory/working/projects/demo.md
**Item ID:** 2026-03-20-review-memory-working-projects-demo-md
**Type:** proposed
**File:** memory/working/projects/demo.md
**Priority:** normal
**Reason:** Review it.
**Status:** pending
""",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_resolve_review_item"](
                item_id="2026-03-20-review-memory-working-projects-demo-md",
                resolution_note="Handled during maintenance.",
            )
        )
        payload = json.loads(raw)
        review_queue = (repo_root / "governance" / "review-queue.md").read_text(encoding="utf-8")

        self.assertEqual(
            payload["new_state"]["item_id"],
            "2026-03-20-review-memory-working-projects-demo-md",
        )
        self.assertEqual(
            payload["commit_message"],
            "[curation] Resolve review item: 2026-03-20-review-memory-working-projects-demo-md",
        )
        self.assertIn("_No pending items._", review_queue)
        self.assertIn("## Resolved", review_queue)
        self.assertIn(
            "2026-03-20-review-memory-working-projects-demo-md: Handled during maintenance.",
            review_queue,
        )
        self.assertNotIn("**Status:** pending", review_queue)

    def test_memory_resolve_review_item_preview_does_not_write_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "governance/review-queue.md": """# Review Queue

### [2026-03-20] Review memory/working/projects/demo.md
**Item ID:** 2026-03-20-review-memory-working-projects-demo-md
**Type:** proposed
**File:** memory/working/projects/demo.md
**Priority:** normal
**Reason:** Review it.
**Status:** pending
""",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_resolve_review_item"](
                    item_id="2026-03-20-review-memory-working-projects-demo-md",
                    resolution_note="Handled during maintenance.",
                    preview=True,
                )
            )
        )

        self.assertIn(
            "**Status:** pending",
            (repo_root / "governance" / "review-queue.md").read_text(encoding="utf-8"),
        )

        applied = json.loads(
            asyncio.run(
                tools["memory_resolve_review_item"](
                    item_id="2026-03-20-review-memory-working-projects-demo-md",
                    resolution_note="Handled during maintenance.",
                )
            )
        )

        self.assertIn(
            "2026-03-20-review-memory-working-projects-demo-md: Handled during maintenance.",
            (repo_root / "governance" / "review-queue.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            applied["commit_message"],
        )

    def test_memory_update_skill_upserts_existing_section(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-start/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Start

## Steps

Load compact context.
""",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_update_skill",
            file="session-start",
            section="Steps",
            content="Load compact context and active plans.",
        )

        raw = asyncio.run(
            tools["memory_update_skill"](
                file="session-start",
                section="Steps",
                content="Load compact context and active plans.",
                approval_token=approval_token,
            )
        )
        payload = json.loads(raw)
        skill = (repo_root / "memory" / "skills" / "session-start" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["new_state"]["section"], "Steps")
        self.assertIn("## Steps\n\nLoad compact context and active plans.", skill)
        self.assertIn(f"last_verified: '{date.today()}'", skill)

    def test_memory_update_skill_appends_existing_section(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-sync/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Sync

## Steps

Capture a short checkpoint.
""",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_update_skill",
            file="session-sync",
            section="Steps",
            content="Record any open questions.",
            mode="append",
        )

        asyncio.run(
            tools["memory_update_skill"](
                file="session-sync",
                section="Steps",
                content="Record any open questions.",
                mode="append",
                approval_token=approval_token,
            )
        )
        skill = (repo_root / "memory" / "skills" / "session-sync" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Capture a short checkpoint.\nRecord any open questions.", skill)

    def test_memory_update_skill_replaces_existing_section(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-wrapup/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Wrapup

## Steps

Old guidance.
""",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_update_skill",
            file="session-wrapup",
            section="Steps",
            content="Use the governed session recorder when available.",
            mode="replace",
        )

        asyncio.run(
            tools["memory_update_skill"](
                file="session-wrapup",
                section="Steps",
                content="Use the governed session recorder when available.",
                mode="replace",
                approval_token=approval_token,
            )
        )
        skill = (repo_root / "memory" / "skills" / "session-wrapup" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Use the governed session recorder when available.", skill)
        self.assertNotIn("Old guidance.", skill)

    def test_memory_update_skill_raises_for_missing_file_without_creation(self) -> None:
        repo_root = self._init_repo({"memory/skills/SUMMARY.md": "# Skills\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.NotFoundError):
            asyncio.run(
                tools["memory_update_skill"](
                    file="missing-skill",
                    section="Steps",
                    content="Create guidance.",
                )
            )

    def test_memory_update_skill_can_create_missing_file(self) -> None:
        repo_root = self._init_repo({"memory/skills/SUMMARY.md": "# Skills\n"})
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_update_skill",
            file="new-skill",
            section="Steps",
            content="Create the first guidance block.",
            create_if_missing=True,
            source="agent-generated",
            trust="medium",
            origin_session="memory/activity/2026/03/20/chat-001",
        )

        raw = asyncio.run(
            tools["memory_update_skill"](
                file="new-skill",
                section="Steps",
                content="Create the first guidance block.",
                create_if_missing=True,
                source="agent-generated",
                trust="medium",
                origin_session="memory/activity/2026/03/20/chat-001",
                approval_token=approval_token,
            )
        )
        payload = json.loads(raw)
        skill_path = repo_root / "memory" / "skills" / "new-skill" / "SKILL.md"
        skill = skill_path.read_text(encoding="utf-8")

        self.assertEqual(payload["new_state"]["section"], "Steps")
        self.assertTrue(skill_path.exists())
        self.assertIn("source: agent-generated", skill)
        self.assertIn("origin_session: memory/activity/2026/03/20/chat-001", skill)
        self.assertIn("trust: medium", skill)
        self.assertIn("## Steps\n\nCreate the first guidance block.", skill)

    def test_memory_update_skill_adds_trigger_frontmatter_field(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-start/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Start

## Steps

Load compact context.
""",
            }
        )
        tools = self._create_tools(repo_root)
        trigger = {
            "event": "session-start",
            "matcher": {"condition": "returning_session"},
            "priority": 50,
        }
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_update_skill",
            file="session-start",
            section="trigger",
            content=trigger,
        )

        asyncio.run(
            tools["memory_update_skill"](
                file="session-start",
                section="trigger",
                content=trigger,
                approval_token=approval_token,
            )
        )
        skill_path = repo_root / "memory" / "skills" / "session-start" / "SKILL.md"
        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(skill_path)
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertEqual(frontmatter["trigger"], trigger)
        self.assertIn("trigger:", skill_text)
        self.assertNotIn("## trigger", skill_text)

    def test_memory_update_skill_appends_trigger_entries(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-start/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
trigger: session-start
---

# Session Start

## Steps

Load compact context.
""",
            }
        )
        tools = self._create_tools(repo_root)
        new_trigger = {"event": "session-checkpoint", "priority": 50}
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_update_skill",
            file="session-start",
            section="trigger",
            content=new_trigger,
            mode="append",
        )

        asyncio.run(
            tools["memory_update_skill"](
                file="session-start",
                section="trigger",
                content=new_trigger,
                mode="append",
                approval_token=approval_token,
            )
        )
        frontmatter, _ = self.frontmatter_utils.read_with_frontmatter(
            repo_root / "memory" / "skills" / "session-start" / "SKILL.md"
        )

        self.assertEqual(frontmatter["trigger"], ["session-start", new_trigger])

    def test_memory_update_skill_rejects_invalid_trigger_without_mutation(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-start/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Start

## Steps

Load compact context.
""",
            }
        )
        tools = self._create_tools(repo_root)
        skill_path = repo_root / "memory" / "skills" / "session-start" / "SKILL.md"
        before = skill_path.read_text(encoding="utf-8")

        with self.assertRaises(self.errors.ValidationError) as ctx:
            asyncio.run(
                tools["memory_update_skill"](
                    file="session-start",
                    section="trigger",
                    content={"event": "not-a-real-trigger"},
                )
            )

        self.assertIn("must be one of", str(ctx.exception))
        self.assertEqual(skill_path.read_text(encoding="utf-8"), before)

    def test_memory_update_skill_preview_does_not_write_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-start/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Start

## Steps

Load compact context.
""",
            }
        )
        tools = self._create_tools(repo_root)

        preview = json.loads(
            asyncio.run(
                tools["memory_update_skill"](
                    file="session-start",
                    section="Steps",
                    content="Load compact context and active plans.",
                    preview=True,
                )
            )
        )

        original = (repo_root / "memory" / "skills" / "session-start" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Load compact context.", original)
        self.assertEqual(preview["preview"]["mode"], "preview")
        self.assertIn("approval_token", preview["new_state"])

        applied = json.loads(
            asyncio.run(
                tools["memory_update_skill"](
                    file="session-start",
                    section="Steps",
                    content="Load compact context and active plans.",
                    approval_token=preview["new_state"]["approval_token"],
                )
            )
        )

        updated = (repo_root / "memory" / "skills" / "session-start" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Load compact context and active plans.", updated)
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            applied["commit_message"],
        )

    def test_memory_update_skill_requires_approval_token_for_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-start/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Start

## Steps

Load compact context.
""",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_update_skill"](
                    file="session-start",
                    section="Steps",
                    content="Load compact context and active plans.",
                )
            )

    def test_memory_update_skill_rejects_forged_approval_token(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/session-start/SKILL.md": """---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Start

## Steps

Load compact context.
""",
            }
        )
        tools = self._create_tools(repo_root)

        import hashlib

        forged_token = hashlib.sha256(
            json.dumps(
                {
                    "head": subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=self._git_root(repo_root),
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip(),
                    "tool_name": "memory_update_skill",
                    "arguments": {
                        "file": "session-start",
                        "section": "Steps",
                        "content": "Load compact context and active plans.",
                    },
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        with self.assertRaises(self.errors.ValidationError) as ctx:
            asyncio.run(
                tools["memory_update_skill"](
                    file="session-start",
                    section="Steps",
                    content="Load compact context and active plans.",
                    approval_token=forged_token,
                )
            )

        self.assertIn("approval_token is invalid or stale", str(ctx.exception))

    def test_memory_register_tool_preview_requires_token_and_apply_commits(self) -> None:
        repo_root = self._init_repo({"memory/skills/SUMMARY.md": "# Skills\n"})
        tools = self._create_tools(repo_root)

        preview = self._preview_tool(
            tools,
            "memory_register_tool",
            name="browser-search",
            description="Search the web through a governed connector.",
            provider="test-provider",
            tags=["search", "web"],
        )

        registry_path = repo_root / "memory" / "skills" / "tool-registry" / "test-provider.yaml"
        summary_path = repo_root / "memory" / "skills" / "tool-registry" / "SUMMARY.md"

        self.assertFalse(registry_path.exists())
        self.assertFalse(summary_path.exists())
        self.assertEqual(preview["preview"]["mode"], "preview")
        self.assertIn("approval_token", preview["new_state"])

        applied = json.loads(
            asyncio.run(
                tools["memory_register_tool"](
                    name="browser-search",
                    description="Search the web through a governed connector.",
                    provider="test-provider",
                    tags=["search", "web"],
                    approval_token=preview["new_state"]["approval_token"],
                )
            )
        )

        commit_count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(applied["new_state"]["action"], "created")
        self.assertEqual(
            applied["new_state"]["registry_file"], "memory/skills/tool-registry/test-provider.yaml"
        )
        self.assertIsNotNone(applied["commit_sha"])
        self.assertTrue(registry_path.exists())
        self.assertTrue(summary_path.exists())
        self.assertIn("browser-search", registry_path.read_text(encoding="utf-8"))
        self.assertIn("browser-search", summary_path.read_text(encoding="utf-8"))
        self.assertEqual(commit_count, "2")
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])

    def test_memory_register_tool_requires_approval_token_for_apply(self) -> None:
        repo_root = self._init_repo({"memory/skills/SUMMARY.md": "# Skills\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_register_tool"](
                    name="browser-search",
                    description="Search the web through a governed connector.",
                    provider="test-provider",
                )
            )

    def test_memory_run_aggregation_dry_run_previews_without_writing_files(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": "# Topic\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/skills/session-start/SKILL.md": "# Session Start\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n\n## Usage patterns\n\n_No access data yet._\n",
                "memory/working/projects/SUMMARY.md": "# Plans\n\n## Usage patterns\n\n_No access data yet._\n",
                "memory/skills/SUMMARY.md": "# Skills\n\n## Usage patterns\n\n_No access data yet._\n",
                "memory/knowledge/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-18",
                                "session_id": "memory/activity/2026/03/18/chat-001",
                                "file": "memory/knowledge/topic.md",
                                "helpfulness": 0.8,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-19",
                                "session_id": "memory/activity/2026/03/19/chat-001",
                                "file": "memory/knowledge/topic.md",
                                "helpfulness": 0.8,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "session_id": "memory/activity/2026/03/20/chat-001",
                                "file": "memory/knowledge/topic.md",
                                "helpfulness": 0.8,
                            }
                        ),
                    ]
                )
                + "\n",
                "memory/working/projects/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-18",
                                "session_id": "memory/activity/2026/03/18/chat-001",
                                "file": "memory/working/projects/demo.md",
                                "helpfulness": 0.7,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-19",
                                "session_id": "memory/activity/2026/03/19/chat-001",
                                "file": "memory/working/projects/demo.md",
                                "helpfulness": 0.7,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "session_id": "memory/activity/2026/03/20/chat-001",
                                "file": "memory/working/projects/demo.md",
                                "helpfulness": 0.7,
                            }
                        ),
                    ]
                )
                + "\n",
                "memory/skills/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-18",
                                "session_id": "memory/activity/2026/03/18/chat-001",
                                "file": "memory/skills/session-start/SKILL.md",
                                "helpfulness": 0.9,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-19",
                                "session_id": "memory/activity/2026/03/19/chat-001",
                                "file": "memory/skills/session-start/SKILL.md",
                                "helpfulness": 0.9,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "session_id": "memory/activity/2026/03/20/chat-001",
                                "file": "memory/skills/session-start/SKILL.md",
                                "helpfulness": 0.9,
                            }
                        ),
                    ]
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)
        before_access = (repo_root / "memory" / "knowledge" / "ACCESS.jsonl").read_text(
            encoding="utf-8"
        )
        before_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )

        raw = asyncio.run(tools["memory_run_aggregation"]())
        payload = json.loads(raw)

        self.assertIsNone(payload["commit_sha"])
        self.assertEqual(payload["new_state"]["access_scope"], "hot_only")
        self.assertEqual(payload["new_state"]["entries_processed"], 9)
        self.assertEqual(payload["new_state"]["session_groups_processed"], 3)
        self.assertEqual(
            sorted(payload["new_state"]["hot_access_targets"]),
            [
                "memory/knowledge/ACCESS.jsonl",
                "memory/skills/ACCESS.jsonl",
                "memory/working/projects/ACCESS.jsonl",
            ],
        )
        self.assertEqual(
            sorted(payload["new_state"]["summary_materialization_targets"]),
            [
                "memory/knowledge/SUMMARY.md",
                "memory/skills/SUMMARY.md",
                "memory/working/projects/SUMMARY.md",
            ],
        )
        self.assertEqual(len(payload["new_state"]["clusters"]), 1)
        self.assertEqual(
            payload["new_state"]["clusters"][0]["files"],
            [
                "memory/knowledge/topic.md",
                "memory/skills/session-start/SKILL.md",
                "memory/working/projects/demo.md",
            ],
        )
        self.assertEqual(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl").read_text(encoding="utf-8"),
            before_access,
        )
        self.assertEqual(
            (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(encoding="utf-8"),
            before_summary,
        )

    def test_memory_run_aggregation_apply_updates_summaries_and_rotates_archives(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": "# Topic\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/skills/session-start/SKILL.md": "# Session Start\n",
                "memory/knowledge/SUMMARY.md": "# Knowledge\n\n## Usage patterns\n\n_No access data yet._\n",
                "memory/working/projects/SUMMARY.md": "# Plans\n\n## Usage patterns\n\n_No access data yet._\n",
                "memory/skills/SUMMARY.md": "# Skills\n\n## Usage patterns\n\n_No access data yet._\n",
                "memory/knowledge/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-18",
                                "session_id": "memory/activity/2026/03/18/chat-001",
                                "file": "memory/knowledge/topic.md",
                                "helpfulness": 0.8,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-19",
                                "file": "memory/knowledge/topic.md",
                                "helpfulness": 0.8,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "session_id": "memory/activity/2026/03/20/chat-001",
                                "file": "memory/knowledge/topic.md",
                                "helpfulness": 0.8,
                            }
                        ),
                    ]
                )
                + "\n",
                "memory/working/projects/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-18",
                                "session_id": "memory/activity/2026/03/18/chat-001",
                                "file": "memory/working/projects/demo.md",
                                "helpfulness": 0.7,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-19",
                                "file": "memory/working/projects/demo.md",
                                "helpfulness": 0.7,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "session_id": "memory/activity/2026/03/20/chat-001",
                                "file": "memory/working/projects/demo.md",
                                "helpfulness": 0.7,
                            }
                        ),
                    ]
                )
                + "\n",
                "memory/skills/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-18",
                                "session_id": "memory/activity/2026/03/18/chat-001",
                                "file": "memory/skills/session-start/SKILL.md",
                                "helpfulness": 0.9,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-19",
                                "file": "memory/skills/session-start/SKILL.md",
                                "helpfulness": 0.9,
                            }
                        ),
                        json.dumps(
                            {
                                "date": "2026-03-20",
                                "session_id": "memory/activity/2026/03/20/chat-001",
                                "file": "memory/skills/session-start/SKILL.md",
                                "helpfulness": 0.9,
                            }
                        ),
                    ]
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(tools["memory_run_aggregation"](dry_run=False))
        payload = json.loads(raw)

        knowledge_summary = (repo_root / "memory" / "knowledge" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        plans_summary = (repo_root / "memory" / "working" / "projects" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        skills_summary = (repo_root / "memory" / "skills" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        knowledge_archive = (
            repo_root / "memory" / "knowledge" / "ACCESS.archive.2026-03.jsonl"
        ).read_text(encoding="utf-8")
        knowledge_access = (repo_root / "memory" / "knowledge" / "ACCESS.jsonl").read_text(
            encoding="utf-8"
        )
        log_count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(
            payload["commit_message"], f"[curation] Aggregate ACCESS logs ({date.today()})"
        )
        self.assertEqual(payload["new_state"]["access_scope"], "hot_only")
        self.assertEqual(payload["new_state"]["entries_processed"], 9)
        self.assertEqual(payload["new_state"]["legacy_fallback_entries"], 3)
        self.assertEqual(
            sorted(payload["new_state"]["hot_access_reset_targets"]),
            [
                "memory/knowledge/ACCESS.jsonl",
                "memory/skills/ACCESS.jsonl",
                "memory/working/projects/ACCESS.jsonl",
            ],
        )
        self.assertIn(f"- Last aggregation: {date.today()}", knowledge_summary)
        self.assertIn(
            "memory/knowledge/topic.md + memory/skills/session-start/SKILL.md + memory/working/projects/demo.md",
            knowledge_summary,
        )
        self.assertIn(f"- Last aggregation: {date.today()}", plans_summary)
        self.assertIn(f"- Last aggregation: {date.today()}", skills_summary)
        self.assertIn('"file": "memory/knowledge/topic.md"', knowledge_archive)
        self.assertEqual(knowledge_access, "")
        self.assertEqual(log_count, "2")

    def test_memory_get_maturity_signals_ignores_archive_segments_and_reports_hot_scope(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": "# Profile\n",
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/knowledge/ACCESS.jsonl": json.dumps(
                    {
                        "file": "memory/knowledge/lit/foo.md",
                        "date": "2026-03-20",
                        "task": "hot log entry",
                        "helpfulness": 0.8,
                        "note": "hot",
                        "session_id": "memory/activity/2026/03/20/chat-017",
                    }
                )
                + "\n",
                "memory/knowledge/ACCESS.archive.2026-03.jsonl": json.dumps(
                    {
                        "file": "memory/knowledge/lit/foo.md",
                        "date": "2026-03-01",
                        "task": "archived entry",
                        "helpfulness": 0.2,
                        "note": "archived",
                        "session_id": "memory/activity/2026/03/01/chat-001",
                    }
                )
                + "\n",
                "memory/knowledge/ACCESS_SCANS.jsonl": json.dumps(
                    {
                        "file": "memory/knowledge/lit/foo.md",
                        "date": "2026-03-20",
                        "task": "scan entry",
                        "helpfulness": 0.1,
                        "note": "scan",
                        "session_id": "memory/activity/2026/03/20/chat-018",
                    }
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_get_maturity_signals"]()))

        self.assertEqual(payload["access_scope"], "hot_only")
        self.assertEqual(payload["access_density"], 1)
        self.assertEqual(payload["total_sessions"], 1)

    # ------------------------------------------------------------------
    # P0-1: memory_write / memory_edit protected-path enforcement
    # ------------------------------------------------------------------

    def test_memory_write_blocks_protected_identity_path(self) -> None:
        repo_root = self._init_repo({"memory/users/profile.md": "# Profile\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(tools["memory_write"](path="memory/users/profile.md", content="injected\n"))
        self.assertEqual(
            (repo_root / "memory" / "users" / "profile.md").read_text(encoding="utf-8"),
            "# Profile\n",
        )

    def test_memory_write_blocks_protected_skills_path(self) -> None:
        repo_root = self._init_repo({"memory/skills/session-start/SKILL.md": "# Skill\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_write"](
                    path="memory/skills/session-start/SKILL.md", content="injected\n"
                )
            )

    def test_memory_write_blocks_protected_meta_path(self) -> None:
        repo_root = self._init_repo({"governance/curation-policy.md": "# Policy\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_write"](path="governance/curation-policy.md", content="injected\n")
            )

    def test_memory_edit_blocks_protected_identity_path(self) -> None:
        repo_root = self._init_repo({"memory/users/profile.md": "# Profile\noriginal\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.MemoryPermissionError):
            asyncio.run(
                tools["memory_edit"](
                    path="memory/users/profile.md",
                    old_string="original",
                    new_string="injected",
                )
            )
        self.assertIn(
            "original", (repo_root / "memory" / "users" / "profile.md").read_text(encoding="utf-8")
        )

    def test_memory_commit_does_not_include_unrelated_pre_staged_changes(self) -> None:
        repo_root = self._init_repo(
            {
                "README.md": "# Project\n",
                "memory/knowledge/README.md": "# Knowledge\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        self._repo_file_path(repo_root, "README.md").write_text(
            "# Unrelated staged change\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Note\n",
            )
        )
        payload = json.loads(
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))
        )

        head_files = subprocess.run(
            ["git", "show", "--name-only", "--format=%s", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        still_staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertIn("memory/knowledge/_unverified/test.md", head_files)
        self.assertNotIn("README.md", head_files)
        self.assertIn("README.md", still_staged)
        self.assertEqual(payload["publication"]["mode"], "porcelain")
        self.assertFalse(payload["publication"]["degraded"])
        self.assertEqual(payload["publication"]["operation"], "commit")
        self.assertRegex(payload["publication"]["published_at"], r"\+00:00$")
        self.assertRegex(payload["publication"]["parent_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(payload["warnings"], [])

    def test_memory_commit_rejects_unstaged_changes_on_tracked_paths(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Staged version\n",
            )
        )
        (repo_root / "memory" / "knowledge" / "_unverified" / "test.md").write_text(
            "# Unstaged version\n",
            encoding="utf-8",
        )

        with self.assertRaises(self.errors.StagingError):
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))

        head_subject = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(head_subject, "seed")

    def test_memory_commit_falls_back_to_plumbing_for_tracked_paths(self) -> None:
        repo_root = self._init_repo(
            {
                "README.md": "# Project\n",
                "memory/knowledge/README.md": "# Knowledge\n",
            }
        )
        _, tools, _, repo = self.server.create_mcp(
            repo_root=repo_root,
            enable_raw_write_tools=True,
        )

        self._repo_file_path(repo_root, "README.md").write_text(
            "# Unrelated staged change\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Note\n",
            )
        )

        original_run = repo._run
        commit_attempts = {"count": 0}

        def fail_porcelain_commit(
            args: list[str],
            check: bool = True,
            capture: bool = True,
            *,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
        ):
            if args[:2] == ["git", "commit"]:
                commit_attempts["count"] += 1
                raise self.errors.StagingError(
                    "`git commit -m` failed (exit 128): fatal: Unable to create '.git/index.lock': File exists.",
                    stderr="fatal: Unable to create '.git/index.lock': File exists.",
                )
            return original_run(args, check=check, capture=capture, cwd=cwd, env=env)

        repo._run = fail_porcelain_commit
        self.addCleanup(setattr, repo, "_run", original_run)

        payload = json.loads(
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))
        )

        head_files = subprocess.run(
            ["git", "show", "--name-only", "--format=%s", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        still_staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertEqual(commit_attempts["count"], 1)
        self.assertIn("memory/knowledge/_unverified/test.md", head_files)
        self.assertNotIn("README.md", head_files)
        self.assertIn("README.md", still_staged)
        self.assertEqual(payload["publication"]["mode"], "plumbing")
        self.assertTrue(payload["publication"]["degraded"])
        self.assertEqual(payload["publication"]["operation"], "commit")
        self.assertRegex(payload["publication"]["published_at"], r"\+00:00$")
        self.assertRegex(payload["publication"]["parent_sha"], r"^[0-9a-f]{40}$")
        self.assertIn("degraded plumbing path", payload["warnings"][0])

    def test_memory_commit_cleans_stale_head_lock_for_dead_pid(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        _, tools, _, repo = self.server.create_mcp(
            repo_root=repo_root,
            enable_raw_write_tools=True,
        )

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Note\n",
            )
        )

        head_lock_path = repo.git_dir / getattr(self.git_repo_module, "_HEAD_LOCK_NAME")
        head_lock_path.write_text("pid=424242\npurpose=stale\n", encoding="utf-8")
        stale_timestamp = time.time() - 120.0
        os.utime(head_lock_path, (stale_timestamp, stale_timestamp))

        original_is_pid_alive = repo._is_pid_alive
        repo._is_pid_alive = lambda pid: False
        self.addCleanup(setattr, repo, "_is_pid_alive", original_is_pid_alive)

        def cleanup_head_lock() -> None:
            if head_lock_path.exists():
                head_lock_path.unlink()

        self.addCleanup(cleanup_head_lock)

        original_run = repo._run
        commit_attempts = {"count": 0}
        update_ref_attempts = {"count": 0}

        def fail_porcelain_commit(
            args: list[str],
            check: bool = True,
            capture: bool = True,
            *,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
        ):
            if args[:2] == ["git", "commit"]:
                commit_attempts["count"] += 1
                raise self.errors.StagingError(
                    "`git commit -m` failed (exit 128): fatal: Unable to create '.git/index.lock': File exists.",
                    stderr="fatal: Unable to create '.git/index.lock': File exists.",
                )
            if args[:2] == ["git", "update-ref"]:
                update_ref_attempts["count"] += 1
                if head_lock_path.exists():
                    raise self.errors.StagingError(
                        "`git update-ref` failed (exit 128): fatal: could not lock ref head: busy (test simulated).",
                        stderr="fatal: could not lock ref head: busy (test simulated).",
                    )
            return original_run(args, check=check, capture=capture, cwd=cwd, env=env)

        repo._run = fail_porcelain_commit
        self.addCleanup(setattr, repo, "_run", original_run)

        payload = json.loads(
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))
        )

        self.assertEqual(commit_attempts["count"], 1)
        self.assertEqual(update_ref_attempts["count"], 1)
        self.assertFalse(head_lock_path.exists())
        self.assertEqual(payload["publication"]["mode"], "plumbing")
        self.assertTrue(payload["publication"]["degraded"])

    def test_memory_commit_does_not_remove_stale_head_lock_without_pid(self) -> None:
        """HEAD.lock without pid is only left in place when it is not stale (<30s old)."""
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        _, tools, _, repo = self.server.create_mcp(
            repo_root=repo_root,
            enable_raw_write_tools=True,
        )

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Note\n",
            )
        )

        head_lock_path = repo.git_dir / getattr(self.git_repo_module, "_HEAD_LOCK_NAME")
        head_lock_path.write_text("owner=unknown\n", encoding="utf-8")
        fresh_timestamp = time.time() - 5.0
        os.utime(head_lock_path, (fresh_timestamp, fresh_timestamp))

        def cleanup_head_lock() -> None:
            if head_lock_path.exists():
                head_lock_path.unlink()

        self.addCleanup(cleanup_head_lock)

        original_run = repo._run
        update_ref_attempts = {"count": 0}

        def fail_on_lock_errors(
            args: list[str],
            check: bool = True,
            capture: bool = True,
            *,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
        ):
            if args[:2] == ["git", "commit"]:
                raise self.errors.StagingError(
                    "`git commit -m` failed (exit 128): fatal: Unable to create '.git/index.lock': File exists.",
                    stderr="fatal: Unable to create '.git/index.lock': File exists.",
                )
            if args[:2] == ["git", "update-ref"]:
                update_ref_attempts["count"] += 1
                if head_lock_path.exists():
                    raise self.errors.StagingError(
                        "`git update-ref` failed (exit 128): fatal: could not lock ref head: busy (test simulated).",
                        stderr="fatal: could not lock ref head: busy (test simulated).",
                    )
            return original_run(args, check=check, capture=capture, cwd=cwd, env=env)

        repo._run = fail_on_lock_errors
        self.addCleanup(setattr, repo, "_run", original_run)

        with self.assertRaises(self.errors.StagingError):
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))

        self.assertEqual(update_ref_attempts["count"], 1)
        self.assertTrue(head_lock_path.exists())

    def test_memory_commit_does_not_remove_stale_head_lock_for_live_pid(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        _, tools, _, repo = self.server.create_mcp(
            repo_root=repo_root,
            enable_raw_write_tools=True,
        )

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Note\n",
            )
        )

        head_lock_path = repo.git_dir / getattr(self.git_repo_module, "_HEAD_LOCK_NAME")
        head_lock_path.write_text("pid=321\npurpose=live\n", encoding="utf-8")
        stale_timestamp = time.time() - 120.0
        os.utime(head_lock_path, (stale_timestamp, stale_timestamp))

        original_is_pid_alive = repo._is_pid_alive
        repo._is_pid_alive = lambda pid: True
        self.addCleanup(setattr, repo, "_is_pid_alive", original_is_pid_alive)

        def cleanup_head_lock() -> None:
            if head_lock_path.exists():
                head_lock_path.unlink()

        self.addCleanup(cleanup_head_lock)

        original_run = repo._run
        update_ref_attempts = {"count": 0}

        def fail_on_lock_errors(
            args: list[str],
            check: bool = True,
            capture: bool = True,
            *,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
        ):
            if args[:2] == ["git", "commit"]:
                raise self.errors.StagingError(
                    "`git commit -m` failed (exit 128): fatal: Unable to create '.git/index.lock': File exists.",
                    stderr="fatal: Unable to create '.git/index.lock': File exists.",
                )
            if args[:2] == ["git", "update-ref"]:
                update_ref_attempts["count"] += 1
                if head_lock_path.exists():
                    raise self.errors.StagingError(
                        "`git update-ref` failed (exit 128): fatal: could not lock ref head: busy (test simulated).",
                        stderr="fatal: could not lock ref head: busy (test simulated).",
                    )
            return original_run(args, check=check, capture=capture, cwd=cwd, env=env)

        repo._run = fail_on_lock_errors
        self.addCleanup(setattr, repo, "_run", original_run)

        with self.assertRaises(self.errors.StagingError):
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))

        self.assertEqual(update_ref_attempts["count"], 1)
        self.assertTrue(head_lock_path.exists())

    def test_memory_commit_retries_plumbing_once_after_stale_head_lock_cleanup(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        _, tools, _, repo = self.server.create_mcp(
            repo_root=repo_root,
            enable_raw_write_tools=True,
        )

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Note\n",
            )
        )

        original_cleanup_stale_head_lock = repo._try_cleanup_stale_head_lock
        cleanup_calls = {"count": 0}

        def always_cleanup_stale_head_lock() -> bool:
            cleanup_calls["count"] += 1
            return True

        repo._try_cleanup_stale_head_lock = always_cleanup_stale_head_lock
        self.addCleanup(
            setattr, repo, "_try_cleanup_stale_head_lock", original_cleanup_stale_head_lock
        )

        original_run = repo._run
        commit_attempts = {"count": 0}
        update_ref_attempts = {"count": 0}

        def fail_porcelain_and_update_ref(
            args: list[str],
            check: bool = True,
            capture: bool = True,
            *,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
        ):
            if args[:2] == ["git", "commit"]:
                commit_attempts["count"] += 1
                raise self.errors.StagingError(
                    "`git commit -m` failed (exit 128): fatal: Unable to create '.git/index.lock': File exists.",
                    stderr="fatal: Unable to create '.git/index.lock': File exists.",
                )
            if args[:2] == ["git", "update-ref"]:
                update_ref_attempts["count"] += 1
                raise self.errors.StagingError(
                    "`git update-ref` failed (exit 128): fatal: could not lock ref head: busy (test simulated).",
                    stderr="fatal: could not lock ref head: busy (test simulated).",
                )
            return original_run(args, check=check, capture=capture, cwd=cwd, env=env)

        repo._run = fail_porcelain_and_update_ref
        self.addCleanup(setattr, repo, "_run", original_run)

        with self.assertRaises(self.errors.StagingError):
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))

        self.assertEqual(commit_attempts["count"], 1)
        self.assertEqual(update_ref_attempts["count"], 2)
        self.assertGreaterEqual(cleanup_calls["count"], 2)

    def test_memory_commit_blocks_when_single_writer_lock_is_held(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        _, tools, _, repo = self.server.create_mcp(
            repo_root=repo_root,
            enable_raw_write_tools=True,
        )

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test.md",
                content="# Note\n",
            )
        )

        lock_path = repo._write_lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("pid=999\npurpose=test\n", encoding="utf-8")
        original_timeout = getattr(self.git_repo_module, "_WRITE_LOCK_TIMEOUT_SECONDS")
        setattr(self.git_repo_module, "_WRITE_LOCK_TIMEOUT_SECONDS", 0.0)
        self.addCleanup(
            setattr, self.git_repo_module, "_WRITE_LOCK_TIMEOUT_SECONDS", original_timeout
        )
        self.addCleanup(lock_path.unlink)

        with self.assertRaises(self.errors.StagingError) as ctx:
            asyncio.run(tools["memory_commit"](message="[knowledge] Add test note"))

        self.assertIn("Another writer is already publishing changes", str(ctx.exception))

    def test_memory_plan_review_lists_completed_plan_with_human_title(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": """---
type: projects-navigator
generated: 2026-03-21
project_count: 1
---

# Projects

_No active or ongoing projects._
""",
                "memory/working/projects/example/SUMMARY.md": """---
source: agent-generated
origin_session: manual
created: 2026-03-21
trust: medium
type: project
status: active
cognitive_mode: exploration
open_questions: 0
active_plans: 1
last_activity: 2026-03-21
current_focus: Example project.
---

# Project: Example
""",
                "memory/working/projects/example/plans/test-plan.yaml": "id: test-plan\nproject: example\ncreated: 2026-03-17\norigin_session: memory/activity/2026/03/17/chat-001\nstatus: completed\npurpose:\n  summary: Test Plan\n  context: Example project.\n  questions: []\nwork:\n  phases:\n    - id: phase-a\n      title: Original next action\n      status: completed\n      commit: abc1234\n      blockers: []\n      changes:\n        - path: memory/working/projects/example/notes/result.md\n          action: create\n          description: Capture the reviewable output.\nreview:\n  completed: 2026-03-17\n  completed_session: memory/activity/2026/03/17/chat-001\n  outcome: completed\n  purpose_assessment: Completed successfully.\n  unresolved: []\n  follow_up: null\n",
                "memory/working/projects/example/notes/result.md": "# Result\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = json.loads(asyncio.run(tools["memory_plan_review"](project_id="example")))

        self.assertEqual(payload["project_id"], "example")
        self.assertEqual(len(payload["completed_plans"]), 1)
        self.assertEqual(payload["completed_plans"][0]["title"], "Test Plan")
        self.assertIn(
            "memory/working/projects/example/notes/result.md",
            payload["completed_plans"][0]["exportable_artifacts"],
        )

    def test_memory_plan_review_requires_session_id_when_exporting(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": """---
type: projects-navigator
generated: 2026-03-21
project_count: 1
---

# Projects

_No active or ongoing projects._
""",
                "memory/working/projects/example/SUMMARY.md": """---
source: agent-generated
origin_session: manual
created: 2026-03-21
trust: medium
type: project
status: active
cognitive_mode: exploration
open_questions: 0
active_plans: 1
last_activity: 2026-03-21
current_focus: Example project.
---

# Project: Example
""",
                "memory/working/projects/example/plans/test-plan.yaml": "id: test-plan\nproject: example\ncreated: 2026-03-17\norigin_session: memory/activity/2026/03/17/chat-001\nstatus: completed\npurpose:\n  summary: Test Plan\n  context: Example project.\n  questions: []\nwork:\n  phases:\n    - id: phase-a\n      title: Original next action\n      status: completed\n      commit: abc1234\n      blockers: []\n      changes:\n        - path: memory/working/projects/example/notes/result.md\n          action: create\n          description: Capture the reviewable output.\nreview:\n  completed: 2026-03-17\n  completed_session: memory/activity/2026/03/17/chat-001\n  outcome: completed\n  purpose_assessment: Completed successfully.\n  unresolved: []\n  follow_up: null\n",
                "memory/working/projects/example/notes/result.md": "# Result\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError) as ctx:
            asyncio.run(
                tools["memory_plan_review"](
                    project_id="example",
                    plan_id="test-plan",
                )
            )

        self.assertIn("session_id is required", str(ctx.exception))

    def test_memory_write_allows_knowledge_path(self) -> None:
        """Sanity check: memory/knowledge/ writes still work after the policy change."""
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_write"](
                path="memory/knowledge/_unverified/test/note.md", content="# Note\n"
            )
        )
        self.assertTrue(
            (repo_root / "memory" / "knowledge" / "_unverified" / "test" / "note.md").exists()
        )

    def test_memory_write_noop_skips_staging_when_content_matches(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/test.md": "# Note\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        read_payload = self._load_tool_payload(
            asyncio.run(tools["memory_read_file"](path="memory/knowledge/test.md"))
        )
        payload = json.loads(
            asyncio.run(
                tools["memory_write"](
                    path="memory/knowledge/test.md",
                    content="# Note\n",
                )
            )
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(payload["files_changed"], [])
        self.assertFalse(payload["new_state"]["changed"])
        self.assertEqual(payload["new_state"]["version_token"], read_payload["version_token"])
        self.assertEqual(staged, "")

    def test_memory_edit_noop_skips_staging_when_replacement_is_identical(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/test.md": "# Hello\n\nSome text.\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        read_payload = self._load_tool_payload(
            asyncio.run(tools["memory_read_file"](path="memory/knowledge/test.md"))
        )
        payload = json.loads(
            asyncio.run(
                tools["memory_edit"](
                    path="memory/knowledge/test.md",
                    old_string="Some text.",
                    new_string="Some text.",
                )
            )
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(payload["files_changed"], [])
        self.assertFalse(payload["new_state"]["changed"])
        self.assertEqual(payload["new_state"]["replacements"], 0)
        self.assertEqual(payload["new_state"]["version_token"], read_payload["version_token"])
        self.assertEqual(staged, "")

    # ------------------------------------------------------------------
    # P1: File size limits
    # ------------------------------------------------------------------

    def test_memory_write_rejects_oversized_content(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        import os

        # Set a very small limit so we don't actually need a large payload
        original = os.environ.get("ENGRAM_MAX_FILE_SIZE")
        try:
            os.environ["ENGRAM_MAX_FILE_SIZE"] = "10"
            with self.assertRaises(self.errors.ValidationError) as ctx:
                asyncio.run(
                    tools["memory_write"](
                        path="memory/knowledge/_unverified/test.md",
                        content="This content is much longer than ten bytes.",
                    )
                )
            self.assertIn("bytes", str(ctx.exception))
        finally:
            if original is None:
                os.environ.pop("ENGRAM_MAX_FILE_SIZE", None)
            else:
                os.environ["ENGRAM_MAX_FILE_SIZE"] = original

    def test_memory_add_knowledge_file_rejects_oversized_content(self) -> None:
        repo_root = self._init_repo(
            {"memory/knowledge/_unverified/SUMMARY.md": "# Unverified\n\n<!-- section: test -->\n"}
        )
        tools = self._create_tools(repo_root)

        import os

        original = os.environ.get("ENGRAM_MAX_FILE_SIZE")
        try:
            os.environ["ENGRAM_MAX_FILE_SIZE"] = "10"
            with self.assertRaises(self.errors.ValidationError) as ctx:
                asyncio.run(
                    tools["memory_add_knowledge_file"](
                        path="memory/knowledge/_unverified/test/note.md",
                        content="This content is much longer than ten bytes.",
                        source="external-research",
                        session_id="memory/activity/2026/03/19/chat-001",
                    )
                )
            self.assertIn("bytes", str(ctx.exception))
        finally:
            if original is None:
                os.environ.pop("ENGRAM_MAX_FILE_SIZE", None)
            else:
                os.environ["ENGRAM_MAX_FILE_SIZE"] = original

    # ------------------------------------------------------------------
    # P1: memory_log_access
    # ------------------------------------------------------------------

    def test_memory_log_access_appends_valid_entry(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/literature/galatea.md": "# Galatea\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/literature/galatea.md",
                task="User asked about AI literature references",
                helpfulness=0.8,
                note="Core reference, shaped the response framing",
                session_id="memory/activity/2026/03/19/chat-001",
            )
        )
        payload = json.loads(raw)
        self.assertEqual(payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS.jsonl")

        lines = [
            line
            for line in (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["file"], "memory/knowledge/literature/galatea.md")
        self.assertEqual(entry["helpfulness"], 0.8)
        self.assertEqual(entry["session_id"], "memory/activity/2026/03/19/chat-001")
        self.assertIn("task", entry)
        self.assertIn("note", entry)
        self.assertIn("date", entry)

    def test_memory_log_access_uses_unverified_access_jsonl(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/_unverified/django/foo.md": "# Foo\n"})
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/_unverified/django/foo.md",
                task="Django query test",
                helpfulness=0.3,
                note="Near-miss — adjacent topic",
            )
        )
        payload = json.loads(raw)
        self.assertEqual(
            payload["new_state"]["access_jsonl"], "memory/knowledge/_unverified/ACCESS.jsonl"
        )
        self.assertTrue(
            (repo_root / "memory" / "knowledge" / "_unverified" / "ACCESS.jsonl").exists()
        )

    def test_memory_log_access_rejects_invalid_helpfulness(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/lit/foo.md": "# Foo\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_log_access"](
                    file="memory/knowledge/lit/foo.md",
                    task="test",
                    helpfulness=1.5,
                    note="out of range",
                )
            )

    def test_memory_log_access_rejects_noncanonical_session_id(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/lit/foo.md": "# Foo\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_log_access"](
                    file="memory/knowledge/lit/foo.md",
                    task="test",
                    helpfulness=0.5,
                    note="bad session id",
                    session_id="chat-001",
                )
            )

    def test_memory_log_access_rejects_category_without_vocabulary(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/lit/foo.md": "# Foo\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_log_access"](
                    file="memory/knowledge/lit/foo.md",
                    task="test",
                    helpfulness=0.5,
                    note="category should be blocked",
                    category="react-performance",
                )
            )

    def test_memory_log_access_accepts_category_from_controlled_vocabulary(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "governance/task-categories.md": "# Task Categories\n\n- `react-performance`\n- `uncategorized`\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/lit/foo.md",
                task="test",
                helpfulness=0.5,
                note="category should be accepted",
                category="react-performance",
            )
        )
        payload = json.loads(raw)

        entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS.jsonl")
        self.assertEqual(entry["category"], "react-performance")

    def test_memory_log_access_persists_mode_field(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/lit/foo.md",
                task="test",
                helpfulness=0.7,
                note="mode should be persisted",
                mode="write",
            )
        )

        payload = json.loads(raw)
        entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS.jsonl")
        self.assertEqual(entry["mode"], "write")

    def test_memory_log_access_accepts_task_id_from_manifest_vocabulary(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/knowledge/ACCESS.jsonl": "",
                "HUMANS/tooling/agent-memory-capabilities.toml": (
                    '[access_logging]\ntask_ids = ["plan-review", "validation"]\n'
                ),
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/lit/foo.md",
                task="test",
                helpfulness=0.7,
                note="task id should be persisted",
                task_id="plan-review",
            )
        )

        payload = json.loads(raw)
        entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS.jsonl")
        self.assertEqual(entry["task_id"], "plan-review")

    def test_memory_log_access_persists_estimator_field(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/lit/foo.md",
                task="test",
                helpfulness=0.7,
                note="estimator should be persisted",
                estimator="sidecar",
            )
        )

        payload = json.loads(raw)
        entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS.jsonl")
        self.assertEqual(entry["estimator"], "sidecar")

    def test_memory_log_access_routes_low_helpfulness_to_scans_sidecar(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/lit/foo.md",
                task="plan sweep",
                helpfulness=0.4,
                note="below threshold should route to scans",
                min_helpfulness=0.7,
            )
        )

        payload = json.loads(raw)
        self.assertEqual(
            payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS_SCANS.jsonl"
        )
        self.assertEqual(payload["new_state"]["scan_entry_count"], 1)
        self.assertEqual(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl").read_text(encoding="utf-8"), ""
        )

        scan_entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS_SCANS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(scan_entry["file"], "memory/knowledge/lit/foo.md")
        self.assertEqual(scan_entry["helpfulness"], 0.4)

    def test_memory_log_access_rejects_invalid_min_helpfulness(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/lit/foo.md": "# Foo\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_log_access"](
                    file="memory/knowledge/lit/foo.md",
                    task="test",
                    helpfulness=0.7,
                    note="bad threshold",
                    min_helpfulness=1.5,
                )
            )

    def test_memory_log_access_rejects_task_id_outside_manifest_vocabulary(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "HUMANS/tooling/agent-memory-capabilities.toml": (
                    '[access_logging]\ntask_ids = ["plan-review", "validation"]\n'
                ),
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_log_access"](
                    file="memory/knowledge/lit/foo.md",
                    task="test",
                    helpfulness=0.7,
                    note="task id should be rejected",
                    task_id="research-write",
                )
            )

    def test_memory_log_access_uses_environment_session_id_when_missing(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        tools = self._create_tools(repo_root)
        original = os.environ.get("MEMORY_SESSION_ID")

        try:
            os.environ["MEMORY_SESSION_ID"] = "memory/activity/2026/03/20/chat-007"
            raw = asyncio.run(
                tools["memory_log_access"](
                    file="memory/knowledge/lit/foo.md",
                    task="test",
                    helpfulness=0.6,
                    note="session id should come from env",
                )
            )
        finally:
            if original is None:
                os.environ.pop("MEMORY_SESSION_ID", None)
            else:
                os.environ["MEMORY_SESSION_ID"] = original

        payload = json.loads(raw)
        entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS.jsonl")
        self.assertEqual(entry["session_id"], "memory/activity/2026/03/20/chat-007")

    def test_memory_log_access_uses_current_session_sentinel_when_missing(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/knowledge/ACCESS.jsonl": "",
                "memory/activity/CURRENT_SESSION": "memory/activity/2026/03/20/chat-008\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access"](
                file="memory/knowledge/lit/foo.md",
                task="test",
                helpfulness=0.6,
                note="session id should come from sentinel",
            )
        )

        payload = json.loads(raw)
        entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(payload["new_state"]["access_jsonl"], "memory/knowledge/ACCESS.jsonl")
        self.assertEqual(entry["session_id"], "memory/activity/2026/03/20/chat-008")

    def test_memory_log_access_batch_writes_multiple_entries_in_single_commit(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/activity/CURRENT_SESSION": "memory/activity/2026/03/20/chat-009\n",
            }
        )
        tools = self._create_tools(repo_root)
        before_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

        raw = asyncio.run(
            tools["memory_log_access_batch"](
                access_entries=[
                    {
                        "file": "memory/knowledge/lit/foo.md",
                        "task": "batch test",
                        "helpfulness": 0.8,
                        "note": "knowledge entry",
                    },
                    {
                        "file": "memory/working/projects/demo.md",
                        "task": "batch test",
                        "helpfulness": 0.4,
                        "note": "plan entry",
                    },
                ]
            )
        )

        after_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self._git_root(repo_root),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        payload = json.loads(raw)

        knowledge_entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        plan_entry = json.loads(
            (repo_root / "memory" / "working" / "projects" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )

        self.assertEqual(after_count - before_count, 1)
        self.assertEqual(payload["new_state"]["entry_count"], 2)
        self.assertEqual(
            sorted(payload["new_state"]["access_jsonls"]),
            ["memory/knowledge/ACCESS.jsonl", "memory/working/projects/ACCESS.jsonl"],
        )
        self.assertEqual(knowledge_entry["session_id"], "memory/activity/2026/03/20/chat-009")
        self.assertEqual(plan_entry["session_id"], "memory/activity/2026/03/20/chat-009")

    def test_memory_log_access_batch_rejects_empty_entry_list(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/lit/foo.md": "# Foo\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_log_access_batch"](access_entries=[]))

    def test_memory_log_access_batch_routes_low_helpfulness_entries_to_scans_sidecar(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/activity/CURRENT_SESSION": "memory/activity/2026/03/20/chat-016\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access_batch"](
                access_entries=[
                    {
                        "file": "memory/knowledge/lit/foo.md",
                        "task": "batch test",
                        "helpfulness": 0.9,
                        "note": "keep in hot log",
                    },
                    {
                        "file": "memory/working/projects/demo.md",
                        "task": "batch test",
                        "helpfulness": 0.2,
                        "note": "route to scans",
                    },
                ],
                min_helpfulness=0.7,
            )
        )

        payload = json.loads(raw)
        self.assertEqual(payload["new_state"]["scan_entry_count"], 1)
        self.assertEqual(
            sorted(payload["new_state"]["access_jsonls"]),
            ["memory/knowledge/ACCESS.jsonl", "memory/working/projects/ACCESS_SCANS.jsonl"],
        )

        knowledge_entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        plan_scan_entry = json.loads(
            (repo_root / "memory" / "working" / "projects" / "ACCESS_SCANS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )

        self.assertEqual(knowledge_entry["session_id"], "memory/activity/2026/03/20/chat-016")
        self.assertEqual(plan_scan_entry["session_id"], "memory/activity/2026/03/20/chat-016")
        self.assertEqual(plan_scan_entry["helpfulness"], 0.2)

    def test_memory_log_access_batch_reports_multiple_validation_errors(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError) as ctx:
            asyncio.run(
                tools["memory_log_access_batch"](
                    access_entries=[
                        {
                            "file": "memory/knowledge/lit/foo.md",
                            "task": "",
                            "helpfulness": 0.8,
                            "note": "missing task",
                        },
                        {
                            "file": "memory/working/projects/demo.md",
                            "task": "batch test",
                            "helpfulness": 1.4,
                            "note": "bad helpfulness",
                        },
                    ],
                    session_id="memory/activity/2026/03/20/chat-017",
                )
            )

        message = str(ctx.exception)
        self.assertIn("ACCESS entry validation failed", message)
        self.assertIn("memory/knowledge/lit/foo.md", message)
        self.assertIn("memory/working/projects/demo.md", message)
        self.assertFalse((repo_root / "memory" / "knowledge" / "ACCESS.jsonl").exists())
        self.assertFalse((repo_root / "memory" / "working" / "projects" / "ACCESS.jsonl").exists())

    def test_memory_get_maturity_signals_reports_write_sessions(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": "# Profile\n",
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/knowledge/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "date": "2026-03-20",
                                "task": "read test",
                                "helpfulness": 0.8,
                                "note": "baseline read",
                                "session_id": "memory/activity/2026/03/20/chat-010",
                                "mode": "read",
                            }
                        ),
                        json.dumps(
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "date": "2026-03-20",
                                "task": "write test",
                                "helpfulness": 0.9,
                                "note": "knowledge write",
                                "session_id": "memory/activity/2026/03/20/chat-011",
                                "mode": "write",
                            }
                        ),
                    ]
                )
                + "\n",
                "memory/working/projects/ACCESS.jsonl": json.dumps(
                    {
                        "file": "memory/working/projects/demo.md",
                        "date": "2026-03-20",
                        "task": "plan update",
                        "helpfulness": 0.6,
                        "note": "plan updated",
                        "session_id": "memory/activity/2026/03/20/chat-012",
                        "mode": "update",
                    }
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_get_maturity_signals"]()))

        self.assertEqual(payload["total_sessions"], 3)
        self.assertEqual(payload["session_id_coverage_pct"], 100.0)
        self.assertEqual(payload["write_sessions"], 2)
        self.assertEqual(payload["access_density"], 3)
        self.assertNotIn("proxy_sessions", payload)

    def test_memory_get_maturity_signals_groups_access_density_by_task_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": "# Profile\n",
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/knowledge/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "date": "2026-03-20",
                                "task": "plan sweep",
                                "helpfulness": 0.8,
                                "note": "plan review",
                                "session_id": "memory/activity/2026/03/20/chat-013",
                                "task_id": "plan-review",
                            }
                        ),
                        json.dumps(
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "date": "2026-03-20",
                                "task": "validation task",
                                "helpfulness": 0.9,
                                "note": "validation",
                                "session_id": "memory/activity/2026/03/20/chat-014",
                                "task_id": "validation",
                            }
                        ),
                    ]
                )
                + "\n",
                "memory/working/projects/ACCESS.jsonl": json.dumps(
                    {
                        "file": "memory/working/projects/demo.md",
                        "date": "2026-03-20",
                        "task": "legacy task",
                        "helpfulness": 0.6,
                        "note": "no task id",
                        "session_id": "memory/activity/2026/03/20/chat-015",
                    }
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_get_maturity_signals"]()))

        self.assertEqual(
            payload["access_density_by_task_id"],
            {"plan-review": 1, "unspecified": 1, "validation": 1},
        )

    def test_memory_get_maturity_signals_emits_proxy_sessions_when_session_id_coverage_is_low(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": "# Profile\n",
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/knowledge/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "date": "2026-03-20",
                                "task": "with session",
                                "helpfulness": 0.8,
                                "note": "session-backed",
                                "session_id": "memory/activity/2026/03/20/chat-019",
                            }
                        ),
                        json.dumps(
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "date": "2026-03-20",
                                "task_id": "plan-review",
                                "task": "legacy sweep",
                                "helpfulness": 0.7,
                                "note": "legacy one",
                            }
                        ),
                    ]
                )
                + "\n",
                "memory/working/projects/ACCESS.jsonl": "\n".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/working/projects/demo.md",
                                "date": "2026-03-20",
                                "task_id": "plan-review",
                                "task": "legacy sweep",
                                "helpfulness": 0.6,
                                "note": "duplicate proxy bucket",
                            }
                        ),
                        json.dumps(
                            {
                                "file": "memory/working/projects/demo.md",
                                "date": "2026-03-21",
                                "task": "legacy planning",
                                "helpfulness": 0.5,
                                "note": "second proxy bucket",
                            }
                        ),
                    ]
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_get_maturity_signals"]()))

        self.assertEqual(payload["total_sessions"], 1)
        self.assertEqual(payload["session_id_coverage_pct"], 25.0)
        self.assertEqual(payload["proxy_sessions"], 3)
        self.assertIn("session_id coverage below 50%", payload["proxy_session_note"])

    def test_memory_revert_commit_preview_returns_confirmation_metadata(self) -> None:
        repo_root = self._init_repo({"memory/working/projects/demo.md": "# Demo\n\nOriginal\n"})
        target_sha = self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\n\nUpdated\n"},
            "[plan] Update demo plan",
        )
        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tools = self._create_tools(repo_root)

        raw = asyncio.run(tools["memory_revert_commit"](sha=target_sha))
        payload = json.loads(raw)
        new_state = payload["new_state"]

        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertIsNone(payload["commit_sha"])
        self.assertEqual(new_state["mode"], "preview")
        self.assertTrue(new_state["eligible"])
        self.assertEqual(new_state["resolved_sha"], target_sha)
        self.assertIsInstance(new_state["preview_token"], str)
        self.assertNotEqual(new_state["preview_token"], head_before)
        self.assertTrue(new_state["applies_cleanly"])
        self.assertEqual(new_state["conflict_details"], "")
        self.assertIn("memory/working/projects/demo.md", new_state["files_changed"])
        self.assertEqual(payload["preview"]["mode"], "preview")
        self.assertEqual(
            payload["preview"]["target_files"],
            [{"path": "memory/working/projects/demo.md", "change": "revert"}],
        )
        self.assertEqual(payload["preview"]["commit_suggestion"]["message"], f"Revert {target_sha}")
        self.assertEqual(head_after, head_before)

    def test_memory_revert_commit_confirm_requires_preview_token(self) -> None:
        repo_root = self._init_repo({"memory/working/projects/demo.md": "# Demo\n\nOriginal\n"})
        target_sha = self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\n\nUpdated\n"},
            "[plan] Update demo plan",
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_revert_commit"](sha=target_sha, confirm=True))

    def test_memory_revert_commit_confirm_reverts_previewed_commit(self) -> None:
        repo_root = self._init_repo({"memory/working/projects/demo.md": "# Demo\n\nOriginal\n"})
        target_sha = self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\n\nUpdated\n"},
            "[plan] Update demo plan",
        )
        tools = self._create_tools(repo_root)

        preview_raw = asyncio.run(tools["memory_revert_commit"](sha=target_sha))
        preview = json.loads(preview_raw)
        confirm_raw = asyncio.run(
            tools["memory_revert_commit"](
                sha=target_sha,
                confirm=True,
                preview_token=preview["new_state"]["preview_token"],
            )
        )
        payload = json.loads(confirm_raw)

        restored = (repo_root / "memory" / "working" / "projects" / "demo.md").read_text(
            encoding="utf-8"
        )
        log_subject = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(payload["new_state"]["mode"], "confirm")
        self.assertEqual(payload["new_state"]["reverted_sha"], target_sha)
        self.assertIn("Original", restored)
        self.assertNotIn("Updated", restored)
        self.assertTrue(log_subject.startswith("Revert"))
        self.assertEqual(payload["preview"]["mode"], "apply")
        self.assertEqual(payload["preview"]["target_files"], preview["preview"]["target_files"])
        self.assertEqual(payload["publication"]["mode"], "porcelain")
        self.assertFalse(payload["publication"]["degraded"])
        self.assertEqual(payload["publication"]["operation"], "revert")
        self.assertRegex(payload["publication"]["published_at"], r"\+00:00$")
        self.assertRegex(payload["publication"]["parent_sha"], r"^[0-9a-f]{40}$")

    def test_memory_revert_commit_blocks_non_memory_paths_on_confirm(self) -> None:
        repo_root = self._init_repo({"tools/example.py": "print('before')\n"})
        target_sha = self._write_and_commit(
            repo_root,
            {"tools/example.py": "print('after')\n"},
            "[system] Update helper",
        )
        tools = self._create_tools(repo_root)

        preview_raw = asyncio.run(tools["memory_revert_commit"](sha=target_sha))
        preview = json.loads(preview_raw)

        self.assertFalse(preview["new_state"]["eligible"])
        self.assertIn("outside the governed memory surface", preview["warnings"][0])

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_revert_commit"](
                    sha=target_sha,
                    confirm=True,
                    preview_token=preview["new_state"]["preview_token"],
                )
            )

    def test_memory_revert_commit_blocks_system_commit_outside_governance_scope(self) -> None:
        repo_root = self._init_repo({"memory/working/projects/demo.md": "# Demo\n\nOriginal\n"})
        target_sha = self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\n\nUpdated\n"},
            "[system] Update demo plan",
        )
        tools = self._create_tools(repo_root)

        preview_raw = asyncio.run(tools["memory_revert_commit"](sha=target_sha))
        preview = json.loads(preview_raw)

        self.assertFalse(preview["new_state"]["eligible"])
        self.assertIn("[system] commits may only touch governance files", preview["warnings"][0])

    def test_memory_revert_commit_preview_reports_conflict(self) -> None:
        repo_root = self._init_repo({"memory/working/projects/demo.md": "# Demo\n\nOriginal\n"})
        target_sha = self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\n\nFirst update\n"},
            "[plan] Update demo plan",
        )
        self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\n\nSecond update\n"},
            "[plan] Update demo plan again",
        )
        tools = self._create_tools(repo_root)

        preview_raw = asyncio.run(tools["memory_revert_commit"](sha=target_sha))
        preview = json.loads(preview_raw)
        new_state = preview["new_state"]

        self.assertFalse(new_state["applies_cleanly"])
        self.assertFalse(new_state["eligible"])
        self.assertTrue(new_state["conflict_details"])
        self.assertIn("does not apply cleanly", preview["warnings"][0])

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_revert_commit"](
                    sha=target_sha,
                    confirm=True,
                    preview_token=new_state["preview_token"],
                )
            )

    def test_memory_revert_commit_allows_governance_scoped_system_commit(self) -> None:
        repo_root = self._init_repo({"README.md": "# Project\n\nOriginal\n"})
        target_sha = self._write_and_commit(
            repo_root,
            {"README.md": "# Project\n\nUpdated\n"},
            "[system] Update readme guidance",
        )
        tools = self._create_tools(repo_root)

        preview_raw = asyncio.run(tools["memory_revert_commit"](sha=target_sha))
        preview = json.loads(preview_raw)
        preview_state = preview["new_state"]

        self.assertTrue(preview_state["eligible"])
        self.assertTrue(preview_state["applies_cleanly"])
        self.assertIn("README.md", preview_state["files_changed"])

        confirm_raw = asyncio.run(
            tools["memory_revert_commit"](
                sha=target_sha,
                confirm=True,
                preview_token=preview_state["preview_token"],
            )
        )
        payload = json.loads(confirm_raw)

        restored = self._repo_file_path(repo_root, "README.md").read_text(encoding="utf-8")
        self.assertEqual(payload["new_state"]["mode"], "confirm")
        self.assertEqual(payload["new_state"]["reverted_sha"], target_sha)
        self.assertIn("Original", restored)
        self.assertNotIn("Updated", restored)

    def test_memory_log_access_rejects_untracked_root(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Scratch\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_log_access"](
                    file="memory/working/CURRENT.md",
                    task="test",
                    helpfulness=0.5,
                    note="scratchpad is not access-tracked",
                )
            )

    # ------------------------------------------------------------------
    # P0-2: memory_audit_trust frontmatterless files
    # ------------------------------------------------------------------

    def test_memory_audit_trust_flags_overdue_frontmatterless_file(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/legacy.md": "# Legacy\n",
            },
            initial_commit_date="2025-01-01T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
        )

        self.assertEqual(payload["files_checked"], 1)
        self.assertEqual(len(payload["overdue_medium"]), 1)
        self.assertEqual(payload["overdue_medium"][0]["path"], "memory/knowledge/legacy.md")
        self.assertTrue(payload["overdue_medium"][0]["implicit_trust"])

    def test_memory_audit_trust_skips_recent_frontmatterless_file_from_overdue(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/recent.md": "# Recent\n",
            },
            initial_commit_date="2026-02-20T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
        )

        self.assertEqual(payload["files_checked"], 1)
        self.assertEqual(payload["overdue_medium"], [])
        self.assertEqual(payload["approaching"], [])
        self.assertEqual(payload["upcoming_medium"], [])
        self.assertEqual(payload["unevaluable"], [])

    def test_memory_audit_trust_handles_high_trust_without_medium_bucket_contamination(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/high-trust.md": (
                    "---\ntrust: high\nlast_verified: 2025-01-01\n---\n\n# High Trust\n"
                ),
            },
            initial_commit_date="2025-01-01T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
        )

        self.assertEqual(payload["files_checked"], 1)
        self.assertEqual(payload["overdue_medium"], [])
        self.assertEqual(payload["upcoming_medium"], [])
        self.assertEqual(payload["approaching"], [])

    def test_memory_audit_trust_keeps_low_trust_entries_out_of_medium_buckets(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/low-trust.md": (
                    "---\ntrust: low\nlast_verified: 2025-01-01\n---\n\n# Low Trust\n"
                ),
            },
            initial_commit_date="2025-01-01T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
        )

        self.assertEqual(payload["files_checked"], 1)
        self.assertEqual(payload["overdue_medium"], [])
        self.assertEqual(payload["upcoming_medium"], [])
        self.assertGreaterEqual(len(payload["overdue_low"]), 1)
        self.assertEqual(payload["overdue_low"][0]["path"], "memory/knowledge/low-trust.md")

    def test_memory_audit_trust_reports_approaching_bucket_before_upcoming_window(self) -> None:
        # last_verified 2025-10-30 + 180-day medium threshold → overdue 2026-04-28
        # medium_warn window starts at 150 days (2026-03-29 UTC).
        # Freeze time to 2026-03-20 (141 days elapsed) so the file sits firmly
        # in the approaching bucket regardless of when CI runs.
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/approaching.md": (
                    "---\ntrust: medium\nlast_verified: 2025-10-30\n---\n\n# Approaching\n"
                ),
            },
            initial_commit_date="2025-10-30T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-20T12:00:00Z", tick=False):
            payload = self._load_tool_payload(
                asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
            )

        self.assertEqual(payload["overdue_medium"], [])
        self.assertEqual(payload["upcoming_medium"], [])
        self.assertEqual(len(payload["approaching"]), 1)
        entry = payload["approaching"][0]
        self.assertEqual(entry["path"], "memory/knowledge/approaching.md")
        self.assertEqual(entry["trust"], "medium")
        self.assertEqual(entry["action_required"], "review")

    def test_memory_audit_trust_keeps_upcoming_items_out_of_approaching(self) -> None:
        # last_verified 2025-10-05 + 180-day medium threshold → overdue 2026-04-03.
        # medium_warn window starts at 150 days (2026-03-04).
        # Freeze time to 2026-03-14 (160 days elapsed) so the file sits firmly
        # in the upcoming_medium bucket regardless of when CI runs.
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/upcoming.md": (
                    "---\ntrust: medium\nlast_verified: 2025-10-05\n---\n\n# Upcoming\n"
                ),
            },
            initial_commit_date="2025-10-05T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        with time_machine.travel("2026-03-14T12:00:00Z", tick=False):
            payload = self._load_tool_payload(
                asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
            )

        self.assertEqual(payload["overdue_medium"], [])
        self.assertEqual(payload["approaching"], [])
        self.assertEqual(len(payload["upcoming_medium"]), 1)
        self.assertEqual(payload["upcoming_medium"][0]["path"], "memory/knowledge/upcoming.md")

    def test_memory_audit_trust_rejects_invalid_warn_pct(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/any.md": "# Any\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge", warn_pct=1.0))

    def test_memory_audit_trust_reports_untracked_frontmatterless_file_as_unevaluable(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/tracked.md": "# Tracked\n",
            },
            initial_commit_date="2026-02-20T00:00:00+00:00",
        )
        (repo_root / "memory" / "knowledge" / "draft.md").write_text("# Draft\n", encoding="utf-8")
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
        )

        self.assertEqual(payload["files_checked"], 2)
        self.assertEqual(len(payload["unevaluable"]), 1)
        self.assertEqual(payload["unevaluable"][0]["path"], "memory/knowledge/draft.md")
        self.assertEqual(
            payload["unevaluable"][0]["reason"],
            "untracked_without_frontmatter",
        )

    def test_memory_git_log_can_read_configured_host_repo(self) -> None:
        host_root = self._init_host_repo({"src/app.py": "print('host')\n"})
        self._write_and_commit(host_root, {"src/app.py": "print('host v2')\n"}, "host update")
        repo_root = self._init_repo(
            {
                "agent-bootstrap.toml": (
                    "version = 1\n"
                    'router = "core/INIT.md"\n'
                    'default_mode = "returning"\n'
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\n'
                    f'host_repo_root = "{host_root.as_posix()}"\n'
                ),
                "core/INIT.md": "# Quick Reference\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_git_log"](n=1, use_host_repo=True))
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["message"], "host update")
        self.assertIn("src/app.py", payload[0]["files_changed"])

    def test_memory_git_log_default_behavior_includes_recent_commits(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "# Quick Reference\n",
                "memory/users/profile.md": "# Profile\n",
                "memory/working/projects/demo.md": "# Demo\n",
            },
            initial_commit_date="2026-03-01T00:00:00+00:00",
        )
        self._write_and_commit(
            repo_root,
            {"memory/users/profile.md": "# Profile\nupdated\n"},
            "update identity",
            commit_date="2026-03-10T00:00:00+00:00",
        )
        self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\nupdated\n"},
            "update plan",
            commit_date="2026-03-18T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_git_log"](n=2)))

        self.assertEqual(
            [entry["message"] for entry in payload], ["update plan", "update identity"]
        )
        self.assertEqual([entry["truncated"] for entry in payload], [False, False])

    def test_memory_git_log_filters_by_since_with_truncation_flag(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "# Quick Reference\n",
                "memory/users/profile.md": "# Profile\n",
                "memory/working/projects/demo.md": "# Demo\n",
            },
            initial_commit_date="2026-03-01T00:00:00+00:00",
        )
        self._write_and_commit(
            repo_root,
            {"memory/users/profile.md": "# Profile\nupdated\n"},
            "update identity",
            commit_date="2026-03-10T00:00:00+00:00",
        )
        self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\nupdated\n"},
            "update plan",
            commit_date="2026-03-18T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_git_log"](n=1, since="2026-03-01"))
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["message"], "update plan")
        self.assertTrue(payload[0]["truncated"])

    def test_memory_git_log_filters_by_path_and_since(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "# Quick Reference\n",
                "memory/users/profile.md": "# Profile\n",
                "memory/working/projects/demo.md": "# Demo\n",
            },
            initial_commit_date="2026-03-01T00:00:00+00:00",
        )
        self._write_and_commit(
            repo_root,
            {"memory/users/profile.md": "# Profile\nupdated\n"},
            "update identity",
            commit_date="2026-03-10T00:00:00+00:00",
        )
        self._write_and_commit(
            repo_root,
            {"memory/working/projects/demo.md": "# Demo\nupdated\n"},
            "update plan",
            commit_date="2026-03-18T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_git_log"](
                    n=5,
                    since="2026-03-12",
                    path_filter="plans\\demo.md",
                )
            )
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["message"], "update plan")
        self.assertEqual(payload[0]["files_changed"], ["memory/working/projects/demo.md"])
        self.assertFalse(payload[0]["truncated"])

    def test_memory_git_log_rejects_invalid_since(self) -> None:
        repo_root = self._init_repo({"core/INIT.md": "# Quick Reference\n"})
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_git_log"](since="2026-99-99"))

    def test_memory_git_log_rejects_host_repo_inside_memory_worktree(self) -> None:
        repo_root = self._init_repo(
            {
                "agent-bootstrap.toml": (
                    "version = 1\n"
                    'router = "core/INIT.md"\n'
                    'default_mode = "returning"\n'
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\n'
                    'host_repo_root = "./nested-host"\n'
                ),
                "core/INIT.md": "# Quick Reference\n",
            }
        )
        nested_host = repo_root / "nested-host"
        nested_host.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=nested_host, check=True, capture_output=True, text=True)
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(tools["memory_git_log"](use_host_repo=True))

    def test_memory_git_health_reports_empty_repo_with_invalid_index(self) -> None:
        git_root = Path(self._tmpdir.name) / "empty_health_repo"
        git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        repo_root = git_root / "core"
        repo_root.mkdir(parents=True, exist_ok=True)
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_git_health"]()))

        self.assertTrue(payload["repo_valid"])
        self.assertFalse(payload["head_valid"])
        self.assertFalse(payload["index_valid"])
        self.assertTrue(any("HEAD is not valid" in warning for warning in payload["warnings"]))

    def test_memory_check_knowledge_freshness_reports_stale_host_backed_note(self) -> None:
        host_root = self._init_host_repo(
            {"src/app.py": "print('host')\n"},
            initial_commit_date="2026-02-20T00:00:00+00:00",
        )
        initial_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=host_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        updated_head = self._write_and_commit(
            host_root,
            {"src/app.py": "print('host v2')\n"},
            "host update",
            commit_date="2026-03-10T00:00:00+00:00",
        )
        repo_root = self._init_repo(
            {
                "agent-bootstrap.toml": (
                    "version = 1\n"
                    'router = "core/INIT.md"\n'
                    'default_mode = "returning"\n'
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\n'
                    f'host_repo_root = "{host_root.as_posix()}"\n'
                ),
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/app.md": (
                    "---\n"
                    "trust: medium\n"
                    "last_verified: 2026-03-01\n"
                    f"verified_against_commit: {initial_head}\n"
                    "related:\n"
                    "  - src/app.py\n"
                    "---\n\n"
                    "# App\n"
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_check_knowledge_freshness"](paths="memory/knowledge/app.md"))
        )

        self.assertEqual(payload["files_checked"], 1)
        report = payload["reports"][0]
        self.assertEqual(report["path"], "memory/knowledge/app.md")
        self.assertEqual(report["status"], "stale")
        self.assertEqual(report["source_files"], ["src/app.py"])
        self.assertEqual(report["host_changes_since"], 1)
        self.assertEqual(report["current_head"], updated_head)
        self.assertEqual(report["suggested_action"], "reverify")

    def test_memory_check_knowledge_freshness_returns_unknown_without_host_repo(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "# Quick Reference\n",
                "memory/knowledge/app.md": (
                    "---\n"
                    "trust: medium\n"
                    "last_verified: 2026-03-01\n"
                    "related:\n"
                    "  - src/app.py\n"
                    "---\n\n"
                    "# App\n"
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_check_knowledge_freshness"](paths="memory/knowledge/app.md"))
        )

        self.assertEqual(payload["files_checked"], 1)
        report = payload["reports"][0]
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["source_files"], [])
        self.assertIsNone(report["current_head"])
        self.assertEqual(report["suggested_action"], "none")

    def test_memory_audit_trust_flags_recent_medium_note_when_host_sources_changed(self) -> None:
        host_root = self._init_host_repo(
            {"src/app.py": "print('host')\n"},
            initial_commit_date="2026-02-20T00:00:00+00:00",
        )
        initial_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=host_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self._write_and_commit(
            host_root,
            {"src/app.py": "print('host v2')\n"},
            "host update",
            commit_date="2026-03-10T00:00:00+00:00",
        )
        repo_root = self._init_repo(
            {
                "agent-bootstrap.toml": (
                    "version = 1\n"
                    'router = "core/INIT.md"\n'
                    'default_mode = "returning"\n'
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\n'
                    f'host_repo_root = "{host_root.as_posix()}"\n'
                ),
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/app.md": (
                    "---\n"
                    "trust: medium\n"
                    "last_verified: 2026-03-01\n"
                    f"verified_against_commit: {initial_head}\n"
                    "related:\n"
                    "  - src/app.py\n"
                    "---\n\n"
                    "# App\n"
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
        )

        self.assertEqual(payload["overdue_medium"], [])
        self.assertEqual(payload["approaching"], [])
        self.assertEqual(len(payload["upcoming_medium"]), 1)
        entry = payload["upcoming_medium"][0]
        self.assertEqual(entry["path"], "memory/knowledge/app.md")
        self.assertEqual(entry["freshness_status"], "stale")
        self.assertEqual(entry["host_changes_since"], 1)
        self.assertEqual(entry["action_required"], "reverify")

    def test_memory_audit_trust_downgrades_stale_age_when_host_sources_are_unchanged(self) -> None:
        host_root = self._init_host_repo(
            {"src/app.py": "print('host')\n"},
            initial_commit_date="2024-12-20T00:00:00+00:00",
        )
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=host_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        repo_root = self._init_repo(
            {
                "agent-bootstrap.toml": (
                    "version = 1\n"
                    'router = "core/INIT.md"\n'
                    'default_mode = "returning"\n'
                    'adapter_files = ["AGENTS.md", "CLAUDE.md", ".cursorrules"]\n'
                    f'host_repo_root = "{host_root.as_posix()}"\n'
                ),
                "core/INIT.md": (
                    "Low-trust retirement threshold | 120-day\n"
                    "Medium-trust flagging threshold | 180-day\n"
                ),
                "memory/knowledge/legacy.md": (
                    "---\n"
                    "trust: medium\n"
                    "last_verified: 2025-01-01\n"
                    f"verified_against_commit: {current_head}\n"
                    "related:\n"
                    "  - src/app.py\n"
                    "---\n\n"
                    "# Legacy\n"
                ),
            },
            initial_commit_date="2025-01-01T00:00:00+00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_audit_trust"](include_categories="knowledge"))
        )

        self.assertEqual(payload["overdue_medium"], [])
        self.assertEqual(payload["approaching"], [])
        self.assertEqual(len(payload["upcoming_medium"]), 1)
        entry = payload["upcoming_medium"][0]
        self.assertEqual(entry["path"], "memory/knowledge/legacy.md")
        self.assertEqual(entry["freshness_status"], "fresh")
        self.assertEqual(entry["host_changes_since"], 0)
        self.assertEqual(entry["action_required"], "review")

    def test_memory_check_aggregation_triggers_reports_above_and_near_thresholds(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "| Aggregation trigger | 15 entries | Exploration |\n",
                "memory/working/projects/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": f"memory/working/projects/item-{idx}.md",
                            "date": "2026-03-19",
                            "task": "periodic review",
                            "helpfulness": 0.7,
                            "note": "useful",
                            "session_id": f"memory/activity/2026/03/19/chat-{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(15)
                ),
                "memory/knowledge/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": f"memory/knowledge/topic-{idx}.md",
                            "date": "2026-03-19",
                            "task": "research",
                            "helpfulness": 0.5,
                            "note": "context",
                        }
                    )
                    + "\n"
                    for idx in range(12)
                ),
                "memory/users/ACCESS.jsonl": json.dumps(
                    {
                        "file": "memory/users/profile.md",
                        "date": "2026-03-19",
                        "task": "profile lookup",
                        "helpfulness": 0.9,
                        "note": "critical",
                    }
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_check_aggregation_triggers"]()))

        self.assertEqual(payload["aggregation_trigger"], 15)
        self.assertEqual(payload["near_trigger_window"], 3)
        self.assertEqual(payload["above_trigger"], ["memory/working/projects/ACCESS.jsonl"])
        self.assertEqual(payload["near_trigger"], ["memory/knowledge/ACCESS.jsonl"])

        reports = {item["access_file"]: item for item in payload["reports"]}
        self.assertEqual(reports["memory/working/projects/ACCESS.jsonl"]["status"], "above")
        self.assertEqual(reports["memory/working/projects/ACCESS.jsonl"]["remaining_to_trigger"], 0)
        self.assertEqual(reports["memory/knowledge/ACCESS.jsonl"]["status"], "near")
        self.assertEqual(reports["memory/knowledge/ACCESS.jsonl"]["remaining_to_trigger"], 3)
        self.assertEqual(reports["memory/users/ACCESS.jsonl"]["status"], "below")

    def test_memory_check_aggregation_triggers_ignores_invalid_jsonl_lines(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "| Aggregation trigger | 15 entries | Exploration |\n",
                "memory/working/projects/ACCESS.jsonl": (
                    "not-json\n"
                    + json.dumps(
                        {
                            "file": "memory/working/projects/demo.md",
                            "date": "2026-03-19",
                            "task": "planning",
                            "helpfulness": 0.6,
                            "note": "useful",
                        }
                    )
                    + "\n"
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_check_aggregation_triggers"]()))

        self.assertEqual(payload["files_checked"], 1)
        self.assertEqual(payload["reports"][0]["entries"], 1)
        self.assertEqual(payload["reports"][0]["invalid_lines"], 1)
        self.assertEqual(payload["reports"][0]["status"], "below")

    def test_memory_check_aggregation_triggers_ignores_meta_access_logs(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "| Aggregation trigger | 15 entries | Exploration |\n",
                "governance/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": f"governance/note-{idx}.md",
                            "date": "2026-03-19",
                            "task": "governance lookup",
                            "helpfulness": 0.8,
                            "note": "ignored",
                        }
                    )
                    + "\n"
                    for idx in range(20)
                ),
                "memory/working/projects/ACCESS.jsonl": json.dumps(
                    {
                        "file": "memory/working/projects/demo.md",
                        "date": "2026-03-19",
                        "task": "planning",
                        "helpfulness": 0.6,
                        "note": "counted",
                    }
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_check_aggregation_triggers"]()))

        self.assertEqual(payload["files_checked"], 1)
        self.assertEqual(
            [item["access_file"] for item in payload["reports"]],
            ["memory/working/projects/ACCESS.jsonl"],
        )
        self.assertEqual(payload["above_trigger"], [])
        self.assertEqual(payload["near_trigger"], [])

    def test_memory_session_health_check_reports_due_aggregation(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "| Aggregation trigger | 15 entries | Exploration |\n\n"
                    "## Last periodic review\n\n"
                    "**Date:** 2026-03-19\n"
                ),
                "memory/working/projects/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": f"memory/working/projects/item-{idx}.md",
                            "date": "2026-03-19",
                            "task": "planning",
                            "helpfulness": 0.7,
                            "note": "useful",
                        }
                    )
                    + "\n"
                    for idx in range(15)
                ),
                "governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_session_health_check"]()))

        self.assertEqual(payload["aggregation_threshold"], 15)
        self.assertEqual(
            payload["aggregation_due"],
            [
                {
                    "folder": "memory/working/projects/",
                    "entries": 15,
                    "threshold": 15,
                    "overdue": True,
                }
            ],
        )
        self.assertEqual(payload["review_queue_pending"], 0)
        self.assertFalse(payload["periodic_review_due"])

    def test_memory_session_health_check_reports_periodic_review_overdue(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "| Aggregation trigger | 15 entries | Exploration |\n\n"
                    "## Last periodic review\n\n"
                    "**Date:** 2026-01-01\n"
                ),
                "core/governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_session_health_check"]()))

        self.assertEqual(payload["last_periodic_review"], "2026-01-01")
        self.assertTrue(payload["periodic_review_due"])
        self.assertGreater(payload["days_since_review"], 30)

    def test_memory_session_health_check_counts_only_pending_review_queue_items(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": (
                    "| Aggregation trigger | 15 entries | Exploration |\n\n"
                    "## Last periodic review\n\n"
                    "**Date:** 2026-03-19\n"
                ),
                "core/governance/review-queue.md": """# Review Queue

## Format

### [YYYY-MM-DD] Brief title
**Type:** proposed | protected
**Description:** What the agent wants to change and why.
**Status:** pending | approved | rejected | superseded

### [2026-03-20] Real pending item
**Type:** proposed
**Description:** Needs review.
**Status:** pending

### [2026-03-19] Already resolved item
**Type:** proposed
**Description:** Done already.
**Status:** resolved
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_session_health_check"]()))

        self.assertEqual(payload["review_queue_pending"], 1)
        self.assertEqual(payload["aggregation_due"], [])

    def test_memory_aggregate_access_reports_high_low_and_clusters(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "| Aggregation trigger | 15 entries | Exploration |\n",
                "memory/working/projects/ACCESS.jsonl": "".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/working/projects/high-value.md",
                                "date": "2026-03-19",
                                "task": "planning",
                                "helpfulness": 0.9,
                                "note": "core plan",
                                "session_id": f"memory/activity/2026/03/19/chat-{idx:03d}",
                            }
                        )
                        + "\n"
                        for idx in range(5)
                    ]
                    + [
                        json.dumps(
                            {
                                "file": "memory/working/projects/low-value.md",
                                "date": "2026-03-19",
                                "task": "planning",
                                "helpfulness": 0.2,
                                "note": "noise",
                                "session_id": f"memory/activity/2026/03/19/chat-{idx:03d}",
                            }
                        )
                        + "\n"
                        for idx in range(3)
                    ]
                ),
                "memory/knowledge/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": "memory/knowledge/topic-a.md",
                            "date": "2026-03-19",
                            "task": "planning",
                            "helpfulness": 0.8,
                            "note": "paired context",
                            "session_id": f"memory/activity/2026/03/19/chat-{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(3)
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_aggregate_access"]()))

        self.assertEqual(payload["entries_considered"], 11)
        self.assertEqual(payload["files_considered"], 3)
        self.assertEqual(
            payload["high_value_files"][0]["file"], "memory/working/projects/high-value.md"
        )
        self.assertEqual(
            payload["low_value_files"][0]["file"], "memory/working/projects/low-value.md"
        )
        self.assertEqual(
            payload["co_retrieval_clusters"][0]["files"],
            ["memory/knowledge/topic-a.md", "memory/working/projects/high-value.md"],
        )
        self.assertIn(
            "memory/working/projects/SUMMARY.md",
            payload["proposed_outputs"]["summary_update_targets"],
        )
        self.assertIn(
            "memory/knowledge/SUMMARY.md", payload["proposed_outputs"]["summary_update_targets"]
        )
        self.assertEqual(
            payload["proposed_outputs"]["review_queue_candidates"][0]["file"],
            "memory/working/projects/low-value.md",
        )

    def test_memory_aggregate_access_ignores_meta_access_logs(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "| Aggregation trigger | 15 entries | Exploration |\n",
                "governance/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": f"governance/note-{idx}.md",
                            "date": "2026-03-19",
                            "task": "governance lookup",
                            "helpfulness": 0.1,
                            "note": "ignored",
                            "session_id": f"memory/activity/2026/03/19/chat-{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(3)
                ),
                "memory/working/projects/ACCESS.jsonl": json.dumps(
                    {
                        "file": "memory/working/projects/kept.md",
                        "date": "2026-03-19",
                        "task": "planning",
                        "helpfulness": 0.8,
                        "note": "counted",
                        "session_id": "memory/activity/2026/03/19/chat-001",
                    }
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_aggregate_access"]()))

        self.assertEqual(payload["entries_considered"], 1)
        self.assertEqual(payload["files_considered"], 1)
        self.assertEqual(payload["high_value_files"], [])
        self.assertEqual(payload["low_value_files"], [])
        self.assertEqual(payload["co_retrieval_clusters"], [])

    def test_memory_aggregate_access_filters_by_folder_date_and_helpfulness(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": "| Aggregation trigger | 15 entries | Exploration |\n",
                "memory/working/projects/ACCESS.jsonl": "".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/working/projects/in-range.md",
                                "date": "2026-03-10",
                                "task": "planning",
                                "helpfulness": 0.75,
                                "note": "keep",
                                "session_id": "memory/activity/2026/03/10/chat-001",
                            }
                        )
                        + "\n",
                        json.dumps(
                            {
                                "file": "memory/working/projects/too-old.md",
                                "date": "2026-02-01",
                                "task": "planning",
                                "helpfulness": 0.9,
                                "note": "old",
                                "session_id": "memory/activity/2026/02/01/chat-001",
                            }
                        )
                        + "\n",
                    ]
                ),
                "memory/knowledge/ACCESS.jsonl": json.dumps(
                    {
                        "file": "memory/knowledge/out-of-folder.md",
                        "date": "2026-03-10",
                        "task": "research",
                        "helpfulness": 0.8,
                        "note": "other folder",
                    }
                )
                + "\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_aggregate_access"](
                    folder="plans",
                    start_date="2026-03-01",
                    end_date="2026-03-31",
                    min_helpfulness=0.7,
                )
            )
        )

        self.assertEqual(payload["entries_considered"], 1)
        self.assertEqual(payload["files_considered"], 1)
        self.assertEqual(
            payload["file_summaries"][0]["file"], "memory/working/projects/in-range.md"
        )
        self.assertEqual(payload["filters"]["folder"], "plans")
        self.assertEqual(payload["filters"]["start_date"], "2026-03-01")

    def test_memory_run_periodic_review_recommends_stage_transition(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Quick Reference

## Current active stage: Exploration

## Last periodic review

**Date:** 2026-01-01

| Aggregation trigger | 15 entries | Exploration |
""",
                "memory/users/profile.md": """---
source: user-stated
origin_session: memory/activity/2026/01/01/chat-001
created: 2026-01-01
last_verified: 2026-01-01
trust: high
---

Alex profile.
""",
                "memory/working/projects/alpha.md": """---
source: agent-generated
origin_session: memory/activity/2026/03/01/chat-001
created: 2026-03-01
last_verified: 2026-03-01
trust: high
---

Alpha.
""",
                "memory/working/projects/beta.md": """---
source: agent-generated
origin_session: memory/activity/2026/03/01/chat-002
created: 2026-03-01
last_verified: 2026-03-01
trust: high
---

Beta.
""",
                "memory/knowledge/topic-a.md": """---
source: external-research
origin_session: memory/activity/2026/03/01/chat-003
created: 2026-03-01
last_verified: 2026-03-05
trust: high
---

Topic A.
""",
                "memory/knowledge/topic-b.md": """---
source: external-research
origin_session: memory/activity/2026/03/01/chat-004
created: 2026-03-01
last_verified: 2026-03-05
trust: medium
---

Topic B.
""",
                "memory/knowledge/topic-c.md": """---
source: external-research
origin_session: memory/activity/2026/03/01/chat-005
created: 2026-03-01
last_verified: 2026-03-05
trust: medium
---

Topic C.
""",
                "memory/knowledge/topic-d.md": """---
source: external-research
origin_session: memory/activity/2026/03/01/chat-006
created: 2026-03-01
last_verified: 2026-03-05
trust: medium
---

Topic D.
""",
                "memory/skills/session-start/SKILL.md": """---
source: skill-discovery
origin_session: memory/activity/2026/03/01/chat-007
created: 2026-03-01
last_verified: 2026-03-05
trust: medium
---

Skill start.
""",
                "memory/skills/session-sync/SKILL.md": """---
source: skill-discovery
origin_session: memory/activity/2026/03/01/chat-008
created: 2026-03-01
last_verified: 2026-03-05
trust: medium
---

Skill sync.
""",
                "memory/working/projects/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": "memory/working/projects/alpha.md"
                            if idx % 2 == 0
                            else "memory/knowledge/topic-a.md",
                            "date": f"2026-03-{(idx % 20) + 1:02d}",
                            "task": "periodic review",
                            "helpfulness": 0.65,
                            "note": "useful",
                            "session_id": f"memory/activity/2026/03/{(idx % 20) + 1:02d}/chat-{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(30)
                ),
                "memory/knowledge/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": "memory/knowledge/topic-b.md"
                            if idx % 2 == 0
                            else "memory/knowledge/topic-c.md",
                            "date": f"2026-03-{(idx % 20) + 1:02d}",
                            "task": "research",
                            "helpfulness": 0.62,
                            "note": "relevant",
                            "session_id": f"memory/activity/2026/03/{(idx % 20) + 1:02d}/chat-k{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(30)
                ),
            },
            initial_commit_date="2026-01-01T00:00:00",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_run_periodic_review"]()))

        self.assertTrue(payload["review_due"]["due"])
        maturity = payload["ordered_checks"]["maturity_assessment"]
        self.assertEqual(maturity["current_stage"], "Exploration")
        self.assertEqual(maturity["recommended_stage"], "Calibration")
        self.assertTrue(maturity["transition_recommended"])
        self.assertIn(
            "INIT.md",
            payload["proposed_outputs"]["deferred_write_targets"],
        )

    def test_memory_run_periodic_review_collects_review_findings(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Quick Reference

## Current active stage: Exploration

## Last periodic review

**Date:** 2026-03-19

| Low-trust retirement threshold | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
""",
                "governance/review-queue.md": """# Review Queue

### [2026-03-20] Security: Review dormant file spike
**Type:** security
**Trigger:** Sudden access spike on a dormant file.
**File:** memory/knowledge/_unverified/old-note.md
**Recommended action:** Investigate access pattern
**Status:** pending

### [2026-03-20] Aggregate plans access log
**Type:** proposed
**Description:** Aggregate stale plans ACCESS log.
**Status:** pending
""",
                "memory/users/profile.md": """---
source: user-stated
origin_session: memory/activity/2026/01/01/chat-001
created: 2026-01-01
last_verified: 2026-01-01
trust: high
---

Stable profile.
""",
                "memory/knowledge/current.md": """---
source: external-research
origin_session: memory/activity/2026/03/20/chat-001
created: 2026-03-20
trust: medium
---

Current note.
""",
                "memory/knowledge/conflicted.md": """---
source: agent-inferred
origin_session: memory/activity/2026/03/20/chat-001
created: 2026-03-20
trust: medium
---

[CONFLICT] Preference uncertain.
""",
                "memory/knowledge/_unverified/old-note.md": """---
source: external-research
origin_session: memory/activity/2025/10/01/chat-001
created: 2025-10-01
trust: low
---

Old note.
""",
                "memory/working/projects/low-value.md": """---
source: agent-generated
origin_session: memory/activity/2026/03/20/chat-010
created: 2026-03-20
trust: medium
---

Low value plan.
""",
                "memory/knowledge/topic-a.md": """---
source: external-research
origin_session: memory/activity/2026/03/20/chat-011
created: 2026-03-20
trust: medium
---

Topic A.
""",
                "memory/working/projects/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": "memory/working/projects/low-value.md",
                            "date": "2026-03-20",
                            "task": "maintenance",
                            "helpfulness": 0.2,
                            "note": "noise",
                            "session_id": f"memory/activity/2026/03/20/chat-{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(3)
                ),
                "memory/knowledge/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": "memory/knowledge/topic-a.md",
                            "date": "2026-03-20",
                            "task": "maintenance",
                            "helpfulness": 0.8,
                            "note": "pair",
                            "session_id": f"memory/activity/2026/03/20/chat-{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(3)
                ),
                "memory/activity/2026/03/20/chat-001/reflection.md": "## Session reflection\n\nRecurring maintenance theme.\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_run_periodic_review"]()))

        ordered = payload["ordered_checks"]
        self.assertEqual(ordered["security_flags"]["pending_count"], 1)
        self.assertEqual(ordered["review_queue"]["pending_non_security_count"], 1)
        self.assertEqual(ordered["unverified_content"]["overdue_count"], 1)
        self.assertEqual(
            ordered["unverified_content"]["overdue_files"][0]["path"],
            "memory/knowledge/_unverified/old-note.md",
        )
        self.assertEqual(
            ordered["conflict_resolution"]["files"], ["memory/knowledge/conflicted.md"]
        )
        self.assertEqual(ordered["unhelpful_memory"]["count"], 1)
        self.assertEqual(
            ordered["emergent_categorization"]["clusters"][0]["files"],
            ["memory/knowledge/topic-a.md", "memory/working/projects/low-value.md"],
        )
        self.assertEqual(ordered["session_reflection_themes"]["reflection_count"], 1)
        self.assertIn(
            "governance/review-queue.md", payload["proposed_outputs"]["deferred_write_targets"]
        )

    def test_memory_run_periodic_review_handles_missing_session_ids_on_same_date(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Quick Reference

## Current active stage: Exploration

## Last periodic review

**Date:** 2026-03-19

| Low-trust retirement threshold | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
""",
                "memory/knowledge/_unverified/topic.md": """---
source: external-research
origin_session: memory/activity/2026/03/01/chat-001
created: 2026-03-01
trust: low
---

Topic.
""",
                "memory/knowledge/ACCESS.jsonl": "".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/knowledge/_unverified/topic.md",
                                "date": "2026-03-20",
                                "task": "maintenance",
                                "helpfulness": 0.4,
                                "note": "missing session id",
                            }
                        )
                        + "\n",
                        json.dumps(
                            {
                                "file": "memory/knowledge/_unverified/topic.md",
                                "date": "2026-03-20",
                                "task": "maintenance",
                                "helpfulness": 0.5,
                                "note": "has session id",
                                "session_id": "memory/activity/2026/03/20/chat-002",
                            }
                        )
                        + "\n",
                    ]
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(asyncio.run(tools["memory_run_periodic_review"]()))

        self.assertEqual(payload["review_due"]["last_periodic_review"], "2026-03-19")
        self.assertEqual(payload["ordered_checks"]["security_flags"]["pending_count"], 0)

    def test_memory_get_file_provenance_returns_frontmatter_access_and_history(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": """---
source: external-research
origin_session: memory/activity/2026/03/19/chat-001
created: 2026-03-19
trust: low
---

Initial note.
""",
                "memory/knowledge/ACCESS.jsonl": "".join(
                    json.dumps(
                        {
                            "file": "memory/knowledge/topic.md",
                            "date": "2026-03-19",
                            "task": "research",
                            "helpfulness": 0.8,
                            "note": "relevant",
                            "session_id": f"memory/activity/2026/03/19/chat-{idx:03d}",
                        }
                    )
                    + "\n"
                    for idx in range(3)
                ),
            },
            initial_commit_date="2026-03-19T00:00:00",
        )
        self._write_and_commit(
            repo_root,
            {
                "memory/knowledge/topic.md": """---
source: external-research
origin_session: memory/activity/2026/03/19/chat-001
created: 2026-03-19
trust: low
---

Updated note.
"""
            },
            "[knowledge] update topic",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_get_file_provenance"](path="memory/knowledge/topic.md"))
        )

        self.assertEqual(payload["path"], "memory/knowledge/topic.md")
        self.assertEqual(payload["frontmatter"]["source"], "external-research")
        self.assertTrue(payload["requires_provenance_pause"])
        self.assertEqual(payload["access_summary"]["entry_count"], 3)
        self.assertEqual(payload["access_summary"]["session_count"], 3)
        self.assertEqual(payload["latest_commit"]["message"], "[knowledge] update topic")
        self.assertGreaterEqual(len(payload["commit_history"]), 2)
        self.assertIsNotNone(payload["version_token"])
        self.assertIn("provenance_fields", payload)
        self.assertIsNone(payload["provenance_fields"]["origin_commit"])
        self.assertIn("lineage_summary", payload)

    def test_memory_get_file_provenance_surfaces_optional_lineage_fields(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": """---
source: agent-generated
created: 2026-03-20
trust: medium
origin_commit: abc123def456
produced_by: memory_generate_summary
verified_by:
  - memory/knowledge/sources/paper-a.md
  - memory/knowledge/sources/paper-b.md
inputs:
  - memory/activity/2026/03/20/chat-001/summary.md
related_sources:
  - docs/spec.md
verified_against_commit: fedcba654321
---

Structured provenance note.
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_get_file_provenance"](path="memory/knowledge/topic.md"))
        )

        self.assertEqual(payload["provenance_fields"]["origin_commit"], "abc123def456")
        self.assertEqual(payload["provenance_fields"]["produced_by"], "memory_generate_summary")
        self.assertEqual(
            payload["provenance_fields"]["verified_by"],
            ["memory/knowledge/sources/paper-a.md", "memory/knowledge/sources/paper-b.md"],
        )
        self.assertEqual(
            payload["provenance_fields"]["inputs"],
            ["memory/activity/2026/03/20/chat-001/summary.md"],
        )
        self.assertEqual(payload["provenance_fields"]["related_sources"], ["docs/spec.md"])
        self.assertIn(
            "Origin commit recorded for memory/knowledge/topic.md.", payload["lineage_summary"]
        )

    def test_memory_extract_file_returns_outline_sections_and_frontmatter(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": """---
title: Extract Me
source: external-research
created: 2026-03-20
trust: medium
---

# Overview

Intro paragraph.

## Usage

Usage details line one.
Usage details line two.

## Notes

Closing notes.
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_extract_file"](
                    path="memory/knowledge/topic.md",
                    section_headings="Usage",
                    max_sections=2,
                    preview_chars=80,
                )
            )
        )

        self.assertEqual(payload["frontmatter"]["title"], "Extract Me")
        self.assertEqual(payload["selected_headings"], ["Usage"])
        self.assertFalse(payload["delivery"]["uses_temp_file_fallback"])
        self.assertGreaterEqual(payload["available_section_count"], 2)
        self.assertEqual(payload["outline"][0]["heading"], "Overview")
        self.assertEqual(payload["sections"][0]["heading"], "Usage")
        self.assertIn("Usage details line one.", payload["sections"][0]["content"])

    def test_memory_extract_file_handles_plain_markdown_without_frontmatter(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/plain.md": "# Plain Heading\n\nAlpha paragraph.\n\n## Details\n\nBeta paragraph.\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_extract_file"](
                    path="memory/knowledge/plain.md",
                    max_sections=2,
                    preview_chars=40,
                )
            )
        )

        self.assertIsNone(payload["frontmatter"])
        self.assertEqual(payload["outline"][0]["heading"], "Plain Heading")
        self.assertEqual(payload["sections"][0]["heading"], "Plain Heading")
        self.assertIn("Alpha paragraph.", payload["preview"])

    def test_memory_inspect_commit_returns_scope_and_prefix_metadata(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": """---
source: external-research
origin_session: memory/activity/2026/03/19/chat-001
created: 2026-03-19
trust: low
---

Initial note.
"""
            },
            initial_commit_date="2026-03-19T00:00:00",
        )
        commit_sha = self._write_and_commit(
            repo_root,
            {"memory/knowledge/topic.md": "updated\n"},
            "[knowledge] rewrite topic",
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_inspect_commit"](sha=commit_sha[:8]))
        )

        self.assertEqual(payload["requested_sha"], commit_sha[:8])
        self.assertEqual(payload["sha"], commit_sha)
        self.assertEqual(payload["recognized_prefix"], "[knowledge]")
        self.assertEqual(payload["file_count"], 1)
        self.assertEqual(payload["top_level_paths"], ["knowledge"])
        self.assertTrue(payload["is_head"])

    def test_memory_record_periodic_review_updates_meta_outputs(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Home

## Current active stage: Exploration

_Last assessed: 2026-03-01 — Exploration retained_

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
| Staleness trigger (no access) | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
| Identity churn alarm | 5 traits/session | Exploration |
| Knowledge flooding alarm | 5 files/day | Exploration |
| Task similarity method | Session co-occurrence | Exploration |
| Cluster co-retrieval threshold | 3 sessions | Exploration |

## Active task similarity method

**Method:** Session co-occurrence
""",
                "core/governance/belief-diff-log.md": "# Belief Diff Log\n",
                "core/governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_record_periodic_review",
            review_date="2026-03-19",
            assessment_summary="Exploration retained (signals still within bounds)",
            belief_diff_entry=(
                "## [2026-03-19] Periodic review\n\n### Assessment\nExploration retained.\n"
            ),
            review_queue_entries=(
                "### [2026-03-19] Aggregate plans access log\n"
                "**Type:** proposed\n"
                "**Description:** Aggregate memory/working/projects/ACCESS.jsonl.\n"
                "**Status:** pending\n"
            ),
        )

        raw = asyncio.run(
            tools["memory_record_periodic_review"](
                review_date="2026-03-19",
                assessment_summary="Exploration retained (signals still within bounds)",
                belief_diff_entry=(
                    "## [2026-03-19] Periodic review\n\n### Assessment\nExploration retained.\n"
                ),
                review_queue_entries=(
                    "### [2026-03-19] Aggregate plans access log\n"
                    "**Type:** proposed\n"
                    "**Description:** Aggregate memory/working/projects/ACCESS.jsonl.\n"
                    "**Status:** pending\n"
                ),
                approval_token=approval_token,
            )
        )
        payload = json.loads(raw)

        quick_reference = (repo_root / "INIT.md").read_text(encoding="utf-8")
        belief_diff = (repo_root / "governance" / "belief-diff-log.md").read_text(encoding="utf-8")
        review_queue = (repo_root / "governance" / "review-queue.md").read_text(encoding="utf-8")

        self.assertIn("**Date:** 2026-03-19", quick_reference)
        self.assertIn(
            "_Last assessed: 2026-03-19 — Exploration retained (signals still within bounds)_",
            quick_reference,
        )
        self.assertIn("## [2026-03-19] Periodic review", belief_diff)
        self.assertIn("Aggregate plans access log", review_queue)
        self.assertEqual(payload["commit_message"], "[system] Record periodic review 2026-03-19")
        self.assertEqual(payload["new_state"]["review_date"], "2026-03-19")
        self.assertTrue(payload["new_state"]["belief_diff_written"])
        self.assertTrue(payload["new_state"]["review_queue_written"])

    def test_memory_record_periodic_review_updates_stage_thresholds(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Home

## Current active stage: Exploration

_Last assessed: 2026-03-01 — Exploration retained_

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
| Staleness trigger (no access) | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
| Identity churn alarm | 5 traits/session | Exploration |
| Knowledge flooding alarm | 5 files/day | Exploration |
| Task similarity method | Session co-occurrence | Exploration |
| Cluster co-retrieval threshold | 3 sessions | Exploration |

## Active task similarity method

**Method:** Session co-occurrence
""",
                "core/governance/belief-diff-log.md": "# Belief Diff Log\n",
                "core/governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_record_periodic_review",
            review_date="2026-03-19",
            assessment_summary="Calibration selected after majority signal review",
            belief_diff_entry=(
                "## [2026-03-19] Periodic review\n\n### Assessment\nCalibration selected.\n"
            ),
            active_stage="Calibration",
        )

        asyncio.run(
            tools["memory_record_periodic_review"](
                review_date="2026-03-19",
                assessment_summary="Calibration selected after majority signal review",
                belief_diff_entry=(
                    "## [2026-03-19] Periodic review\n\n### Assessment\nCalibration selected.\n"
                ),
                active_stage="Calibration",
                approval_token=approval_token,
            )
        )

        quick_reference = (repo_root / "INIT.md").read_text(encoding="utf-8")
        self.assertIn("## Current active stage: Calibration", quick_reference)
        self.assertIn(
            "| Aggregation trigger | 20 entries | Calibration |",
            quick_reference,
        )
        self.assertIn(
            "| Knowledge flooding alarm | 3 files/day | Calibration |",
            quick_reference,
        )
        self.assertIn("**Method:** Task-string normalization", quick_reference)

    def test_memory_record_periodic_review_preview_does_not_write_and_matches_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Home

## Current active stage: Exploration

_Last assessed: 2026-03-01 — Exploration retained_

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
| Staleness trigger (no access) | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
| Identity churn alarm | 5 traits/session | Exploration |
| Knowledge flooding alarm | 5 files/day | Exploration |
| Task similarity method | Session co-occurrence | Exploration |
| Cluster co-retrieval threshold | 3 sessions | Exploration |

## Active task similarity method

**Method:** Session co-occurrence
""",
                "core/governance/belief-diff-log.md": "# Belief Diff Log\n",
                "core/governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
            }
        )
        tools = self._create_tools(repo_root)
        quick_reference_before = (repo_root / "INIT.md").read_text(encoding="utf-8")

        preview = json.loads(
            asyncio.run(
                tools["memory_record_periodic_review"](
                    review_date="2026-03-19",
                    assessment_summary="Exploration retained after review.",
                    belief_diff_entry="## [2026-03-19] Periodic review\n",
                    review_queue_entries="### [2026-03-19] Follow-up\n**Status:** pending\n",
                    preview=True,
                )
            )
        )

        self.assertEqual(
            (repo_root / "INIT.md").read_text(encoding="utf-8"),
            quick_reference_before,
        )
        self.assertEqual(preview["preview"]["mode"], "preview")
        self.assertIn("approval_token", preview["new_state"])

        applied = json.loads(
            asyncio.run(
                tools["memory_record_periodic_review"](
                    review_date="2026-03-19",
                    assessment_summary="Exploration retained after review.",
                    belief_diff_entry="## [2026-03-19] Periodic review\n",
                    review_queue_entries="### [2026-03-19] Follow-up\n**Status:** pending\n",
                    approval_token=preview["new_state"]["approval_token"],
                )
            )
        )

        self.assertIn(
            "**Date:** 2026-03-19",
            (repo_root / "INIT.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(preview["preview"]["target_files"], applied["preview"]["target_files"])
        self.assertEqual(
            preview["preview"]["commit_suggestion"]["message"],
            applied["commit_message"],
        )

    def test_memory_record_periodic_review_requires_approval_token_for_apply(self) -> None:
        repo_root = self._init_repo(
            {
                "core/INIT.md": """# Home

## Current active stage: Exploration

_Last assessed: 2026-03-01 — Exploration retained_

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
| Staleness trigger (no access) | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
| Identity churn alarm | 5 traits/session | Exploration |
| Knowledge flooding alarm | 5 files/day | Exploration |
| Task similarity method | Session co-occurrence | Exploration |
| Cluster co-retrieval threshold | 3 sessions | Exploration |

## Active task similarity method

**Method:** Session co-occurrence
""",
                "core/governance/belief-diff-log.md": "# Belief Diff Log\n",
                "core/governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_record_periodic_review"](
                    review_date="2026-03-19",
                    assessment_summary="Exploration retained after review.",
                    belief_diff_entry="## [2026-03-19] Periodic review\n",
                )
            )

    # ------------------------------------------------------------------
    # P1: Identity churn alarm + memory_reset_session_state
    # ------------------------------------------------------------------

    def test_memory_update_user_trait_churn_alarm_fires_at_limit(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile
""",
            }
        )
        tools = self._create_tools(repo_root)

        # Make 5 successful updates (at the limit)
        for i in range(5):
            preview_token, _ = self._preview_token_for(
                tools,
                "memory_update_user_trait",
                file="profile",
                key=f"trait_{i}",
                value=f"value_{i}",
            )
            asyncio.run(
                tools["memory_update_user_trait"](
                    file="profile",
                    key=f"trait_{i}",
                    value=f"value_{i}",
                    preview_token=preview_token,
                )
            )

        with self.assertRaises(self.errors.ValidationError) as ctx:
            self._preview_tool(
                tools,
                "memory_update_user_trait",
                file="profile",
                key="trait_6",
                value="value_6",
            )
        self.assertIn("churn alarm", str(ctx.exception).lower())

    def test_memory_reset_session_state_clears_churn_counter(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile
""",
            }
        )
        tools = self._create_tools(repo_root)

        # Exhaust the counter
        for i in range(5):
            preview_token, _ = self._preview_token_for(
                tools,
                "memory_update_user_trait",
                file="profile",
                key=f"trait_{i}",
                value=f"value_{i}",
            )
            asyncio.run(
                tools["memory_update_user_trait"](
                    file="profile",
                    key=f"trait_{i}",
                    value=f"value_{i}",
                    preview_token=preview_token,
                )
            )

        # Reset
        reset_payload = self._load_tool_payload(asyncio.run(tools["memory_reset_session_state"]()))
        self.assertTrue(reset_payload["reset"])
        self.assertEqual(reset_payload["identity_updates_this_session"], 0)

        # Should now succeed
        preview_token, _ = self._preview_token_for(
            tools,
            "memory_update_user_trait",
            file="profile",
            key="trait_after_reset",
            value="allowed",
        )
        asyncio.run(
            tools["memory_update_user_trait"](
                file="profile",
                key="trait_after_reset",
                value="allowed",
                preview_token=preview_token,
            )
        )

    def test_churn_counters_are_independent_per_server_instance(self) -> None:
        """Two separate create_mcp() calls must have independent counters."""
        repo_root = self._init_repo(
            {
                "memory/users/profile.md": """---
source: user-stated
origin_session: manual
created: 2026-03-17
trust: high
---

# Profile
""",
            }
        )

        tools_a = self._create_tools(repo_root)
        tools_b = self._create_tools(repo_root)

        # Exhaust counter on instance A
        for i in range(5):
            preview_token, _ = self._preview_token_for(
                tools_a,
                "memory_update_user_trait",
                file="profile",
                key=f"a_{i}",
                value=f"v{i}",
            )
            asyncio.run(
                tools_a["memory_update_user_trait"](
                    file="profile",
                    key=f"a_{i}",
                    value=f"v{i}",
                    preview_token=preview_token,
                )
            )

        # Instance B counter is independent — should not be affected
        preview_token, _ = self._preview_token_for(
            tools_b,
            "memory_update_user_trait",
            file="profile",
            key="b_0",
            value="independent",
        )
        asyncio.run(
            tools_b["memory_update_user_trait"](
                file="profile",
                key="b_0",
                value="independent",
                preview_token=preview_token,
            )
        )

    # ------------------------------------------------------------------
    # P2: Version-token conflict tests for raw write tools
    # ------------------------------------------------------------------

    def test_memory_write_rejects_stale_version_token(self) -> None:
        """Read a file, modify it out-of-band, then attempt a write with the old token."""
        repo_root = self._init_repo({"memory/knowledge/test.md": "# Original\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        # Get the current token
        read_payload = self._load_tool_payload(
            asyncio.run(tools["memory_read_file"](path="memory/knowledge/test.md"))
        )
        old_token = read_payload["version_token"]

        # Modify the file directly (bypassing the MCP layer)
        (repo_root / "memory" / "knowledge" / "test.md").write_text(
            "# Modified out of band\n", encoding="utf-8"
        )

        # memory_write with stale token must raise ConflictError
        with self.assertRaises(self.errors.ConflictError):
            asyncio.run(
                tools["memory_write"](
                    path="memory/knowledge/test.md",
                    content="# New content\n",
                    version_token=old_token,
                )
            )

    def test_memory_edit_rejects_stale_version_token(self) -> None:
        """Read a file, modify it out-of-band, then attempt an edit with the old token."""
        repo_root = self._init_repo({"memory/knowledge/test.md": "# Hello\n\nSome text.\n"})
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        read_payload = self._load_tool_payload(
            asyncio.run(tools["memory_read_file"](path="memory/knowledge/test.md"))
        )
        old_token = read_payload["version_token"]

        # Modify the file directly
        (repo_root / "memory" / "knowledge" / "test.md").write_text(
            "# Hello\n\nModified out of band.\n", encoding="utf-8"
        )

        # memory_edit with stale token must raise ConflictError
        with self.assertRaises(self.errors.ConflictError):
            asyncio.run(
                tools["memory_edit"](
                    path="memory/knowledge/test.md",
                    old_string="Some text.",
                    new_string="Replaced text.",
                    version_token=old_token,
                )
            )

    # -----------------------------------------------------------------------
    # memory_plan_create: budget and phase fields
    # -----------------------------------------------------------------------

    def test_memory_plan_create_with_budget_stores_and_returns_budget_status(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-26\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-26\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-26\ncurrent_focus: Harness work.\n---\n\n# Project: Example\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_plan_create"](
                plan_id="budget-plan",
                project_id="example",
                purpose_summary="Budget plan",
                purpose_context="Plan with a budget constraint.",
                phases=[
                    {
                        "id": "phase-a",
                        "title": "Do the work",
                        "changes": [
                            {
                                "path": "memory/working/projects/example/notes/output.md",
                                "action": "create",
                                "description": "Write output note.",
                            }
                        ],
                    }
                ],
                session_id="memory/activity/2026/03/26/chat-001",
                budget={"deadline": "2026-04-15", "max_sessions": 8, "advisory": True},
            )
        )
        payload = json.loads(raw)
        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "budget-plan.yaml"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(plan_body["budget"]["deadline"], "2026-04-15")
        self.assertEqual(plan_body["budget"]["max_sessions"], 8)
        self.assertNotIn("advisory", plan_body["budget"])  # True is the default, omitted
        self.assertIn("budget_status", payload["new_state"])
        self.assertEqual(payload["new_state"]["budget_status"]["max_sessions"], 8)
        self.assertEqual(payload["new_state"]["budget_status"]["sessions_used"], 0)

    def test_memory_plan_create_with_phase_sources_and_postconditions(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-26\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
                "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-26\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 0\nlast_activity: 2026-03-26\ncurrent_focus: Schema validation work.\n---\n\n# Project: Example\n",
                "memory/working/notes/reference.md": "# Reference\n",
            }
        )
        tools = self._create_tools(repo_root)

        asyncio.run(
            tools["memory_plan_create"](
                plan_id="rich-plan",
                project_id="example",
                purpose_summary="Rich plan",
                purpose_context="Plan with sources and postconditions.",
                phases=[
                    {
                        "id": "phase-a",
                        "title": "Do it",
                        "sources": [
                            {
                                "path": "memory/working/notes/reference.md",
                                "type": "internal",
                                "intent": "Read the reference notes.",
                            }
                        ],
                        "postconditions": ["Output file exists", "Tests pass"],
                        "requires_approval": True,
                        "changes": [
                            {
                                "path": "memory/working/projects/example/notes/output.md",
                                "action": "create",
                                "description": "Write output note.",
                            }
                        ],
                    }
                ],
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "rich-plan.yaml"
            ).read_text(encoding="utf-8")
        )
        phase = plan_body["work"]["phases"][0]
        self.assertEqual(len(phase["sources"]), 1)
        self.assertEqual(phase["sources"][0]["type"], "internal")
        self.assertEqual(len(phase["postconditions"]), 2)
        self.assertTrue(phase["requires_approval"])

    # -----------------------------------------------------------------------
    # memory_plan_execute: inspect, start, complete with new fields
    # -----------------------------------------------------------------------

    def _plan_yaml_with_budget(self, *, sessions_used: int = 0) -> str:
        return (
            "id: tracked-plan\n"
            "project: example\n"
            "created: 2026-03-26\n"
            "origin_session: memory/activity/2026/03/26/chat-001\n"
            "status: active\n"
            "budget:\n"
            "  deadline: '2099-12-31'\n"
            "  max_sessions: 3\n"
            f"sessions_used: {sessions_used}\n"
            "purpose:\n"
            "  summary: Tracked plan\n"
            "  context: Plan with budget and approval gate.\n"
            "  questions: []\n"
            "work:\n"
            "  phases:\n"
            "    - id: phase-a\n"
            "      title: Gated phase\n"
            "      status: pending\n"
            "      commit: null\n"
            "      blockers: []\n"
            "      sources:\n"
            "        - path: memory/working/notes/ref.md\n"
            "          type: internal\n"
            "          intent: Read reference.\n"
            "      postconditions:\n"
            "        - File exists\n"
            "      requires_approval: true\n"
            "      changes:\n"
            "        - path: memory/working/projects/example/notes/out.md\n"
            "          action: create\n"
            "          description: Write output.\n"
            "review: null\n"
        )

    def _plan_yaml_with_check_postcondition(
        self,
        *,
        requires_approval: bool = False,
        sessions_used: int = 0,
        check_target: str = "memory/working/projects/example/notes/out.md",
    ) -> str:
        requires_approval_yaml = "true" if requires_approval else "false"
        return (
            "id: tracked-plan\n"
            "project: example\n"
            "created: 2026-03-26\n"
            "origin_session: memory/activity/2026/03/26/chat-001\n"
            "status: active\n"
            "budget:\n"
            "  deadline: '2099-12-31'\n"
            "  max_sessions: 3\n"
            f"sessions_used: {sessions_used}\n"
            "purpose:\n"
            "  summary: Verifiable tracked plan\n"
            "  context: Plan with check postcondition for execute verification.\n"
            "  questions: []\n"
            "work:\n"
            "  phases:\n"
            "    - id: phase-a\n"
            "      title: Verifiable phase\n"
            "      status: pending\n"
            "      commit: null\n"
            "      blockers: []\n"
            "      sources:\n"
            "        - path: memory/working/notes/ref.md\n"
            "          type: internal\n"
            "          intent: Read reference.\n"
            "      postconditions:\n"
            "        - description: Output file exists\n"
            "          type: check\n"
            f"          target: {check_target}\n"
            f"      requires_approval: {requires_approval_yaml}\n"
            "      changes:\n"
            "        - path: memory/working/projects/example/notes/out.md\n"
            "          action: create\n"
            "          description: Write output.\n"
            "review: null\n"
        )

    def _eval_scenario_yaml(
        self,
        *,
        scenario_id: str = "basic-plan-lifecycle",
        tags: list[str] | None = None,
    ) -> str:
        payload = {
            "id": scenario_id,
            "description": "Run a basic lifecycle scenario.",
            "tags": tags or ["lifecycle"],
            "setup": {
                "plan": {
                    "id": f"{scenario_id}-plan",
                    "project": "eval-suite",
                    "phases": [
                        {
                            "id": "phase-one",
                            "title": "Create output",
                            "postconditions": [
                                {
                                    "description": "Output exists",
                                    "type": "check",
                                    "target": "memory/working/notes/eval.txt",
                                }
                            ],
                            "changes": [
                                {
                                    "path": "memory/working/notes/eval.txt",
                                    "action": "create",
                                    "description": "Create eval file",
                                }
                            ],
                        }
                    ],
                },
                "files": [
                    {
                        "path": "memory/working/notes/eval.txt",
                        "content": "hello from eval\n",
                    }
                ],
            },
            "steps": [
                {
                    "action": "start_phase",
                    "phase_id": "phase-one",
                    "expect": {"phase_status": "in-progress"},
                },
                {
                    "action": "verify_phase",
                    "phase_id": "phase-one",
                    "expect": {"all_passed": True},
                },
                {
                    "action": "complete_phase",
                    "phase_id": "phase-one",
                    "commit_sha": "eval-001",
                    "verify": True,
                    "expect": {"phase_status": "completed", "plan_status": "completed"},
                },
            ],
            "assertions": [
                {"type": "plan_status", "expected": "completed"},
                {"type": "metric", "name": "task_success", "expected": 1.0},
            ],
        }
        return yaml.dump(payload, sort_keys=False, allow_unicode=False)

    def _plan_repo_files(self, plan_yaml: str) -> dict[str, str]:
        return {
            "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-26\nproject_count: 1\n---\n\n# Projects\n\n_No active or ongoing projects._\n",
            "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-26\ntrust: medium\ntype: project\nstatus: active\ncognitive_mode: exploration\nopen_questions: 0\nactive_plans: 1\nlast_activity: 2026-03-26\ncurrent_focus: Budget plan.\n---\n\n# Project: Example\n",
            "memory/working/projects/example/plans/tracked-plan.yaml": plan_yaml,
            "memory/working/notes/ref.md": "# Ref\n",
        }

    def _phase8_plan_yaml(self, *, completed: bool = False) -> str:
        payload = {
            "id": "tracked-plan",
            "project": "example",
            "created": "2026-03-27",
            "origin_session": "memory/activity/2026/03/27/chat-200",
            "status": "completed" if completed else "active",
            "purpose": {
                "summary": "Phase 8 test plan",
                "context": "Exercise the plan briefing read path.",
            },
            "work": {
                "phases": [
                    {
                        "id": "phase-a",
                        "title": "Briefing phase",
                        "status": "completed" if completed else "pending",
                        "sources": [
                            {
                                "path": "core/context.md",
                                "type": "internal",
                                "intent": "Read the briefing source.",
                            }
                        ],
                        "changes": [
                            {
                                "path": "memory/working/projects/example/notes/out.md",
                                "action": "create",
                                "description": "Create project note.",
                            }
                        ],
                    }
                ]
            },
            "review": None,
        }
        return yaml.dump(payload, sort_keys=False, allow_unicode=False)

    def _phase9_project_files(self) -> dict[str, str]:
        return {
            "memory/working/projects/SUMMARY.md": "---\ntype: projects-navigator\ngenerated: 2026-03-27\nproject_count: 1\n---\n\n# Projects\n",
            "memory/working/projects/example/SUMMARY.md": "---\nsource: agent-generated\norigin_session: manual\ncreated: 2026-03-27\ntrust: medium\ntype: project\nstatus: active\nactive_plans: 0\nplans: 0\nlast_activity: 2026-03-27\ncurrent_focus: External ingestion.\n---\n\n# Project: Example\n",
        }

    def test_memory_plan_execute_inspect_includes_sources_postconditions_budget(self) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="inspect",
            )
        )
        payload = json.loads(raw)

        self.assertIn("sources", payload["phase"])
        self.assertEqual(payload["phase"]["sources"][0]["type"], "internal")
        self.assertIn("postconditions", payload["phase"])
        self.assertEqual(payload["phase"]["postconditions"][0]["description"], "File exists")
        self.assertTrue(payload["phase"]["requires_approval"])
        self.assertIn("budget_status", payload)
        self.assertEqual(payload["budget_status"]["max_sessions"], 3)
        self.assertFalse(payload["budget_status"]["over_budget"])

    def test_memory_plan_execute_start_surfaces_approval_gate_for_requires_approval_phase(
        self,
    ) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        payload = json.loads(raw)

        self.assertEqual(payload["new_state"]["plan_status"], "paused")
        self.assertEqual(payload["new_state"]["phase_id"], "phase-a")
        self.assertIn("approval_file", payload["new_state"])
        self.assertIn("requires human approval", payload["new_state"]["message"])

    def test_memory_plan_execute_start_creates_pending_approval_and_trace(self) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        payload = json.loads(raw)

        approval_path = (
            repo_root
            / "memory"
            / "working"
            / "approvals"
            / "pending"
            / "tracked-plan--phase-a.yaml"
        )
        self.assertEqual(payload["new_state"]["plan_status"], "paused")
        self.assertTrue(approval_path.exists())

        approval_body = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
        self.assertEqual(approval_body["status"], "pending")
        self.assertEqual(approval_body["phase_id"], "phase-a")

        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "tracked-plan.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(plan_body["status"], "paused")

        trace_path = (
            repo_root / "memory" / "activity" / "2026" / "03" / "26" / "chat-001.traces.jsonl"
        )
        trace_spans = [
            json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(any(span["name"] == "approval-requested" for span in trace_spans))
        git_root = self._git_root(repo_root)
        approval_git_path = (
            "core/memory/working/approvals/pending/tracked-plan--phase-a.yaml"
            if (git_root / "core").is_dir()
            else "memory/working/approvals/pending/tracked-plan--phase-a.yaml"
        )
        subprocess.run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                approval_git_path,
            ],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_memory_plan_execute_start_returns_pending_approval_when_already_waiting(self) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        payload = json.loads(raw)

        self.assertEqual(payload["plan_status"], "paused")
        self.assertEqual(payload["phase_id"], "phase-a")
        self.assertIn("awaiting approval", payload["message"].lower())

    def test_memory_plan_execute_complete_while_paused_returns_guard_message(self) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="complete",
                session_id="memory/activity/2026/03/26/chat-001",
                commit_sha="abc1234",
            )
        )
        payload = json.loads(raw)

        self.assertEqual(payload["plan_status"], "paused")
        self.assertEqual(payload["phase_id"], "phase-a")
        self.assertIn("awaiting approval", payload["message"].lower())

        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "tracked-plan.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(plan_body["status"], "paused")
        self.assertEqual(plan_body["work"]["phases"][0]["status"], "pending")

    def test_memory_resolve_approval_reject_blocks_followup_start(self) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        resolve_raw = asyncio.run(
            tools["memory_resolve_approval"](
                plan_id="tracked-plan",
                phase_id="phase-a",
                resolution="reject",
                comment="Need more detail.",
            )
        )
        resolve_payload = json.loads(resolve_raw)

        self.assertEqual(resolve_payload["new_state"]["status"], "rejected")
        self.assertEqual(resolve_payload["new_state"]["plan_status"], "blocked")

        followup_raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        followup_payload = json.loads(followup_raw)

        self.assertEqual(followup_payload["new_state"]["plan_status"], "blocked")
        self.assertEqual(followup_payload["new_state"]["approval_status"], "rejected")
        self.assertIn("re-request", followup_payload["new_state"]["message"])

    def test_memory_plan_execute_start_with_expired_approval_blocks_and_moves_file(self) -> None:
        from core.tools.agent_memory_mcp.plan_utils import ApprovalDocument, save_approval

        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        expired = ApprovalDocument(
            plan_id="tracked-plan",
            phase_id="phase-a",
            project_id="example",
            status="pending",
            requested="2026-03-01T09:00:00Z",
            expires="2026-03-02T09:00:00Z",
            context={"phase_title": "Gated phase"},
        )
        save_approval(repo_root, expired)

        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        payload = json.loads(raw)

        self.assertEqual(payload["new_state"]["plan_status"], "blocked")
        self.assertEqual(payload["new_state"]["approval_status"], "expired")
        self.assertTrue(
            (
                repo_root
                / "memory"
                / "working"
                / "approvals"
                / "resolved"
                / "tracked-plan--phase-a.yaml"
            ).exists()
        )

    def test_memory_resolve_approval_approve_allows_phase_start(self) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        resolve_raw = asyncio.run(
            tools["memory_resolve_approval"](
                plan_id="tracked-plan",
                phase_id="phase-a",
                resolution="approve",
                comment="Looks good.",
            )
        )
        resolve_payload = json.loads(resolve_raw)

        self.assertEqual(resolve_payload["new_state"]["status"], "approved")
        self.assertEqual(resolve_payload["new_state"]["plan_status"], "active")

        approval_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "approvals"
                / "resolved"
                / "tracked-plan--phase-a.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(approval_body["status"], "approved")
        self.assertEqual(approval_body["comment"], "Looks good.")

        resumed_raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        resumed_payload = json.loads(resumed_raw)

        self.assertEqual(resumed_payload["new_state"]["plan_status"], "active")
        self.assertEqual(resumed_payload["new_state"]["phase_status"], "in-progress")
        self.assertTrue(
            (
                repo_root
                / "memory"
                / "working"
                / "approvals"
                / "resolved"
                / "tracked-plan--phase-a.yaml"
            ).exists()
        )
        git_root = self._git_root(repo_root)
        resolved_git_path = (
            "core/memory/working/approvals/resolved/tracked-plan--phase-a.yaml"
            if (git_root / "core").is_dir()
            else "memory/working/approvals/resolved/tracked-plan--phase-a.yaml"
        )
        pending_git_path = (
            "core/memory/working/approvals/pending/tracked-plan--phase-a.yaml"
            if (git_root / "core").is_dir()
            else "memory/working/approvals/pending/tracked-plan--phase-a.yaml"
        )
        subprocess.run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                resolved_git_path,
            ],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        pending_lookup = subprocess.run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                pending_git_path,
            ],
            cwd=git_root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(pending_lookup.returncode, 0)

    def test_memory_resolve_approval_cannot_resolve_twice(self) -> None:
        plan_yaml = self._plan_yaml_with_budget()
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        asyncio.run(
            tools["memory_resolve_approval"](
                plan_id="tracked-plan",
                phase_id="phase-a",
                resolution="approve",
                comment="Looks good.",
            )
        )

        with self.assertRaises(self.errors.ValidationError) as exc_info:
            asyncio.run(
                tools["memory_resolve_approval"](
                    plan_id="tracked-plan",
                    phase_id="phase-a",
                    resolution="reject",
                    comment="Second resolution should fail.",
                )
            )

        self.assertIn("already resolved", str(exc_info.exception))

    def test_memory_plan_execute_complete_with_verify_failure_preserves_phase_state(self) -> None:
        plan_yaml = self._plan_yaml_with_check_postcondition(requires_approval=False)
        repo_root = self._init_repo(self._plan_repo_files(plan_yaml))
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="complete",
                session_id="memory/activity/2026/03/26/chat-001",
                commit_sha="abc1234",
                verify=True,
            )
        )
        payload = json.loads(raw)

        self.assertEqual(payload["status"], "verification_failed")
        self.assertEqual(payload["phase_status"], "in-progress")
        self.assertFalse(payload["all_passed"])

        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "tracked-plan.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(plan_body["status"], "active")
        self.assertEqual(plan_body.get("sessions_used", 0), 0)
        self.assertEqual(plan_body["work"]["phases"][0]["status"], "in-progress")

    def test_memory_plan_execute_complete_with_verify_success_records_warning(self) -> None:
        plan_yaml = self._plan_yaml_with_check_postcondition(requires_approval=False)
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(plan_yaml),
                "memory/working/projects/example/notes/out.md": "done\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="complete",
                session_id="memory/activity/2026/03/26/chat-001",
                commit_sha="abc1234",
                verify=True,
            )
        )
        payload = json.loads(raw)

        self.assertEqual(payload["new_state"]["phase_status"], "completed")
        self.assertEqual(payload["new_state"]["sessions_used"], 1)
        self.assertTrue(any("Verification passed" in warning for warning in payload["warnings"]))

        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "tracked-plan.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(plan_body["work"]["phases"][0]["status"], "completed")
        self.assertEqual(plan_body["sessions_used"], 1)

    def test_memory_plan_execute_complete_increments_sessions_used(self) -> None:
        plan_yaml = self._plan_yaml_with_check_postcondition(
            requires_approval=False, sessions_used=0
        )
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(plan_yaml),
                "memory/working/projects/example/notes/out.md": "done\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        # Start the phase first
        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        # Now complete it
        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="complete",
                session_id="memory/activity/2026/03/26/chat-001",
                commit_sha="abc1234",
            )
        )
        payload = json.loads(raw)
        plan_body = yaml.safe_load(
            (
                repo_root
                / "memory"
                / "working"
                / "projects"
                / "example"
                / "plans"
                / "tracked-plan.yaml"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(payload["new_state"]["sessions_used"], 1)
        self.assertEqual(plan_body.get("sessions_used", 0), 1)
        self.assertIn("budget_status", payload["new_state"])

    def test_memory_plan_execute_complete_warns_when_session_budget_exhausted(self) -> None:
        # sessions_used starts at 2, max_sessions is 3 — completing makes it 3 (exhausted)
        plan_yaml = self._plan_yaml_with_check_postcondition(
            requires_approval=False, sessions_used=2
        )
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(plan_yaml),
                "memory/working/projects/example/notes/out.md": "done\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="start",
                session_id="memory/activity/2026/03/26/chat-001",
            )
        )
        raw = asyncio.run(
            tools["memory_plan_execute"](
                plan_id="tracked-plan",
                project_id="example",
                phase_id="phase-a",
                action="complete",
                session_id="memory/activity/2026/03/26/chat-001",
                commit_sha="abc1234",
            )
        )
        payload = json.loads(raw)

        self.assertTrue(any("session budget" in w.lower() for w in payload["warnings"]))
        self.assertTrue(payload["new_state"]["budget_status"]["over_session_budget"])

    def test_memory_plan_briefing_returns_next_action_phase_packet(self) -> None:
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(self._phase8_plan_yaml()),
                "core/context.md": "Briefing source body\n" * 8,
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_plan_briefing"](
                plan_id="tracked-plan",
                project_id="example",
                max_context_chars=600,
            )
        )
        payload = json.loads(raw)

        self.assertEqual(payload["plan_id"], "tracked-plan")
        self.assertEqual(payload["phase_id"], "phase-a")
        self.assertEqual(payload["phase"]["phase"]["id"], "phase-a")
        self.assertEqual(payload["source_contents"][0]["path"], "core/context.md")
        self.assertIn("context_budget", payload)

    def test_memory_plan_briefing_returns_summary_when_no_actionable_phase(self) -> None:
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(self._phase8_plan_yaml(completed=True)),
                "core/context.md": "Briefing source body\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_plan_briefing"](
                plan_id="tracked-plan",
                project_id="example",
            )
        )
        payload = json.loads(raw)

        self.assertIsNone(payload["phase"])
        self.assertEqual(payload["progress"]["done"], 1)
        self.assertEqual(payload["progress"]["total"], 1)
        self.assertIn("no actionable phase", payload["message"].lower())

    def test_memory_plan_verify_does_not_write_trace_from_memory_session_env(self) -> None:
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(
                    self._plan_yaml_with_check_postcondition(requires_approval=False)
                ),
                "memory/working/projects/example/notes/out.md": "done\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        old_session = os.environ.get("MEMORY_SESSION_ID")
        os.environ["MEMORY_SESSION_ID"] = "memory/activity/2026/03/27/chat-203"
        try:
            raw = asyncio.run(
                tools["memory_plan_verify"](
                    plan_id="tracked-plan",
                    project_id="example",
                    phase_id="phase-a",
                )
            )
        finally:
            if old_session is None:
                os.environ.pop("MEMORY_SESSION_ID", None)
            else:
                os.environ["MEMORY_SESSION_ID"] = old_session

        payload = json.loads(raw)
        trace_path = (
            repo_root / "memory" / "activity" / "2026" / "03" / "27" / "chat-203.traces.jsonl"
        )
        git_status = subprocess.run(
            ["git", "status", "--short"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertTrue(payload["all_passed"])
        self.assertFalse(trace_path.exists())
        self.assertEqual(git_status, "")

    def test_memory_plan_briefing_does_not_write_trace_from_memory_session_env(self) -> None:
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(self._phase8_plan_yaml()),
                "core/context.md": "Briefing source body\n",
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        old_session = os.environ.get("MEMORY_SESSION_ID")
        os.environ["MEMORY_SESSION_ID"] = "memory/activity/2026/03/27/chat-204"
        try:
            asyncio.run(
                tools["memory_plan_briefing"](
                    plan_id="tracked-plan",
                    project_id="example",
                )
            )
        finally:
            if old_session is None:
                os.environ.pop("MEMORY_SESSION_ID", None)
            else:
                os.environ["MEMORY_SESSION_ID"] = old_session

        trace_path = (
            repo_root / "memory" / "activity" / "2026" / "03" / "27" / "chat-204.traces.jsonl"
        )
        git_status = subprocess.run(
            ["git", "status", "--short"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertFalse(trace_path.exists())
        self.assertEqual(git_status, "")

    def test_memory_plan_resume_returns_briefing_without_side_effects(self) -> None:
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(self._phase8_plan_yaml()),
                "core/context.md": "Briefing source body\n" * 4,
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_plan_resume"](
                plan_id="tracked-plan",
                project_id="example",
                session_id="memory/activity/2026/03/27/chat-205",
                max_context_chars=700,
            )
        )
        payload = json.loads(raw)

        trace_path = (
            repo_root / "memory" / "activity" / "2026" / "03" / "27" / "chat-205.traces.jsonl"
        )
        git_status = subprocess.run(
            ["git", "status", "--short"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(payload["plan_id"], "tracked-plan")
        self.assertFalse(payload["has_run_state"])
        self.assertEqual(payload["resumption"]["current_phase_id"], "phase-a")
        self.assertEqual(payload["phase_briefing"]["phase_id"], "phase-a")
        self.assertEqual(payload["phase_briefing"]["phase"]["phase"]["id"], "phase-a")
        self.assertFalse(trace_path.exists())
        self.assertEqual(git_status, "")

    def test_memory_plan_resume_does_not_rewrite_run_state_session(self) -> None:
        repo_root = self._init_repo(
            {
                **self._plan_repo_files(self._phase8_plan_yaml()),
                "core/context.md": "Briefing source body\n" * 2,
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)
        plan_utils = importlib.import_module("core.tools.agent_memory_mcp.plan_utils")

        run_state = plan_utils.RunState(
            plan_id="tracked-plan",
            project_id="example",
            current_phase_id="phase-a",
            current_task="Resume drafting",
            next_action_hint="Continue phase A",
            last_checkpoint="checkpoint-1",
            session_id="memory/activity/2026/03/27/chat-111",
            sessions_consumed=2,
            phase_states={
                "phase-a": plan_utils.RunStatePhase(
                    intermediate_outputs=[
                        {
                            "key": "notes",
                            "value": "carry forward",
                            "timestamp": "2026-03-27T09:15:00Z",
                        }
                    ]
                )
            },
        )
        run_state_path = repo_root / plan_utils.run_state_path("example", "tracked-plan")
        plan_utils.save_run_state(repo_root, run_state)
        subprocess.run(
            ["git", "add", "."],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add run state"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        before = run_state_path.read_text(encoding="utf-8")

        raw = asyncio.run(
            tools["memory_plan_resume"](
                plan_id="tracked-plan",
                project_id="example",
                session_id="memory/activity/2026/03/27/chat-206",
                max_context_chars=700,
            )
        )
        payload = json.loads(raw)
        after = run_state_path.read_text(encoding="utf-8")
        git_status = subprocess.run(
            ["git", "status", "--short"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertTrue(payload["has_run_state"])
        self.assertEqual(
            payload["resumption"]["previous_session"], "memory/activity/2026/03/27/chat-111"
        )
        self.assertEqual(payload["intermediate_outputs"][0]["key"], "notes")
        self.assertEqual(before, after)
        self.assertEqual(git_status, "")

    def test_memory_stage_external_writes_project_inbox_file(self) -> None:
        repo_root = self._init_repo(self._phase9_project_files())
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_stage_external"](
                project="example",
                filename="article.md",
                content="External note\n",
                source_url="https://example.com/article?utm=1#frag",
                fetched_date="2026-03-27",
                source_label="example-article",
            )
        )
        payload = json.loads(raw)

        self.assertTrue(payload["staged"])
        target = repo_root / payload["target_path"]
        self.assertTrue(target.exists())
        body = target.read_text(encoding="utf-8")
        self.assertIn("origin_url: https://example.com/article", body)
        self.assertTrue(
            (
                repo_root / "memory" / "working" / "projects" / "example" / ".staged-hashes.jsonl"
            ).exists()
        )

    def test_memory_stage_external_dry_run_returns_preview_only(self) -> None:
        repo_root = self._init_repo(self._phase9_project_files())
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_stage_external"](
                project="example",
                filename="article.md",
                content="External note\n",
                source_url="https://example.com/article",
                fetched_date="2026-03-27",
                source_label="example-article",
                dry_run=True,
            )
        )
        payload = json.loads(raw)

        self.assertFalse(payload["staged"])
        self.assertFalse((repo_root / payload["target_path"]).exists())

    def test_memory_stage_external_writes_snapshot_freshness_frontmatter(self) -> None:
        repo_root = self._init_repo(self._phase9_project_files())
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_stage_external"](
                project="example",
                filename="snapshot-default.md",
                content="External note\n",
                source_url="https://example.com/snapshot-default",
                fetched_date="2026-03-27",
                source_label="example-article",
            )
        )
        payload = json.loads(raw)

        target = repo_root / payload["target_path"]
        body = target.read_text(encoding="utf-8")
        self.assertIn("snapshot_taken_at: '2026-03-27'", body)
        self.assertNotIn("reflects_upstream_as_of", body)

        preview = payload["frontmatter_preview"]
        self.assertEqual(preview["snapshot_taken_at"], "2026-03-27")
        self.assertNotIn("reflects_upstream_as_of", preview)

    def test_memory_stage_external_records_reflects_upstream_when_provided(self) -> None:
        repo_root = self._init_repo(self._phase9_project_files())
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(
            tools["memory_stage_external"](
                project="example",
                filename="snapshot-upstream.md",
                content="External note with upstream marker\n",
                source_url="https://example.com/snapshot-upstream",
                fetched_date="2026-03-27",
                source_label="example-article",
                reflects_upstream_as_of="abc1234",
            )
        )
        payload = json.loads(raw)

        target = repo_root / payload["target_path"]
        body = target.read_text(encoding="utf-8")
        self.assertIn("snapshot_taken_at: '2026-03-27'", body)
        self.assertIn("reflects_upstream_as_of: abc1234", body)

        preview = payload["frontmatter_preview"]
        self.assertEqual(preview["reflects_upstream_as_of"], "abc1234")

    def test_memory_stage_external_rejects_empty_reflects_upstream(self) -> None:
        repo_root = self._init_repo(self._phase9_project_files())
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        with self.assertRaises(self.errors.ValidationError):
            asyncio.run(
                tools["memory_stage_external"](
                    project="example",
                    filename="snapshot-bad.md",
                    content="External note\n",
                    source_url="https://example.com/snapshot-bad",
                    fetched_date="2026-03-27",
                    source_label="example-article",
                    reflects_upstream_as_of="   ",
                )
            )

    def test_memory_scan_drop_zone_returns_scan_report(self) -> None:
        drop_folder = Path(self._tmpdir.name) / "external-drop"
        drop_folder.mkdir(parents=True, exist_ok=True)
        (drop_folder / "note.md").write_text("drop note\n", encoding="utf-8")
        repo_root = self._init_repo(
            {
                **self._phase9_project_files(),
                "agent-bootstrap.toml": (
                    "version = 1\n"
                    f'[[watch_folders]]\npath = "{drop_folder.as_posix()}"\n'
                    'target_project = "example"\n'
                    'source_label = "external-drop"\n'
                ),
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        raw = asyncio.run(tools["memory_scan_drop_zone"]())
        payload = json.loads(raw)

        self.assertEqual(payload["staged_count"], 1)
        self.assertEqual(payload["duplicate_count"], 0)
        self.assertTrue(
            (repo_root / "memory" / "working" / "projects" / "example" / "IN" / "note.md").exists()
        )

    def test_memory_run_eval_requires_tier2(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/eval-scenarios/basic-plan-lifecycle.yaml": self._eval_scenario_yaml(),
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        old_val = os.environ.pop("ENGRAM_TIER2", None)
        try:
            with self.assertRaises(self.errors.ValidationError) as exc_info:
                asyncio.run(
                    tools["memory_run_eval"](
                        session_id="memory/activity/2026/03/27/chat-201",
                        scenario_id="basic-plan-lifecycle",
                    )
                )
        finally:
            if old_val is not None:
                os.environ["ENGRAM_TIER2"] = old_val

        self.assertIn("ENGRAM_TIER2", str(exc_info.exception))

    def test_memory_run_eval_runs_scenario_and_records_trace(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/eval-scenarios/basic-plan-lifecycle.yaml": self._eval_scenario_yaml(),
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        old_val = os.environ.get("ENGRAM_TIER2")
        os.environ["ENGRAM_TIER2"] = "1"
        try:
            raw = asyncio.run(
                tools["memory_run_eval"](
                    session_id="memory/activity/2026/03/27/chat-202",
                    scenario_id="basic-plan-lifecycle",
                )
            )
        finally:
            if old_val is None:
                os.environ.pop("ENGRAM_TIER2", None)
            else:
                os.environ["ENGRAM_TIER2"] = old_val

        payload = json.loads(raw)
        self.assertEqual(payload["summary"]["passed"], 1)
        self.assertEqual(payload["results"][0]["scenario_id"], "basic-plan-lifecycle")
        self.assertEqual(payload["metrics"]["task_success"], 1.0)

        trace_path = (
            repo_root / "memory" / "activity" / "2026" / "03" / "27" / "chat-202.traces.jsonl"
        )
        trace_spans = [
            json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
        ]
        eval_spans = [span for span in trace_spans if span["name"] == "eval:basic-plan-lifecycle"]
        self.assertEqual(len(eval_spans), 1)
        self.assertEqual(eval_spans[0]["metadata"]["eval_status"], "pass")

    def test_memory_eval_report_returns_runs_for_scenario(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/eval-scenarios/basic-plan-lifecycle.yaml": self._eval_scenario_yaml(),
                "memory/skills/eval-scenarios/secondary-lifecycle.yaml": self._eval_scenario_yaml(
                    scenario_id="secondary-lifecycle",
                    tags=["secondary"],
                ),
            }
        )
        tools = self._create_tools(repo_root, enable_raw_write_tools=True)

        old_val = os.environ.get("ENGRAM_TIER2")
        os.environ["ENGRAM_TIER2"] = "1"
        try:
            with time_machine.travel("2026-03-27T12:00:00Z", tick=False):
                asyncio.run(
                    tools["memory_run_eval"](
                        session_id="memory/activity/2026/03/27/chat-203",
                        tag="lifecycle",
                    )
                )
                raw = asyncio.run(
                    tools["memory_eval_report"](
                        scenario_id="basic-plan-lifecycle",
                        date_from="2026-03-27",
                        date_to="2026-03-27",
                    )
                )
        finally:
            if old_val is None:
                os.environ.pop("ENGRAM_TIER2", None)
            else:
                os.environ["ENGRAM_TIER2"] = old_val

        payload = json.loads(raw)
        self.assertEqual(payload["scenario_id"], "basic-plan-lifecycle")
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["summary"]["passed"], 1)
        self.assertEqual(payload["runs"][0]["scenario_id"], "basic-plan-lifecycle")
        self.assertEqual(payload["metrics"]["task_success"], 1.0)


if __name__ == "__main__":
    unittest.main()
