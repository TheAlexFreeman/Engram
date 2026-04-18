from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, ClassVar, Coroutine, cast

REPO_ROOT = Path(__file__).resolve().parents[3]
ToolCallable = Callable[..., Coroutine[Any, Any, str]]

CATALOG_SCRIPT = """def regenerate_skill_tree_markdown(repo_root, log_missing_frontmatter=False):\n    return '# Skill Catalog\\n'\n\ndef regenerate_skills_summary_markdown(repo_root):\n    return '# Skills Summary\\n'\n\ndef iter_disk_skill_slugs(skills_dir):\n    return sorted(\n        child.name\n        for child in skills_dir.iterdir()\n        if child.is_dir() and not child.name.startswith('_') and (child / 'SKILL.md').is_file()\n    )\n"""
TEST_SESSION_ID = "memory/activity/2026/04/15/chat-001"


def load_server_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.server")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"agent_memory_mcp dependencies unavailable: {exc.name}") from exc


class SkillDistributionIntegrationTests(unittest.TestCase):
    server: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = load_server_module()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_root = Path(self._tmpdir.name)

    def _init_repo(self, files: dict[str, str]) -> Path:
        temp_root = self.temp_root / f"repo_{len(files)}"
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
        subprocess.run(
            ["git", "commit", "-m", "seed"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        content_root = temp_root / "core"
        return content_root if content_root.is_dir() else temp_root

    def _git_root(self, repo_root: Path) -> Path:
        return repo_root if (repo_root / ".git").exists() else repo_root.parent

    def _repo_file(self, repo_root: Path, rel_path: str) -> Path:
        return self._git_root(repo_root) / rel_path

    def _create_tools(self, repo_root: Path) -> dict[str, ToolCallable]:
        _, tools, _, _ = self.server.create_mcp(repo_root=repo_root)
        return cast(dict[str, ToolCallable], tools)

    def _load_payload(self, raw: str) -> Any:
        payload = cast(dict[str, Any], json.loads(raw))
        if "result" in payload:
            return payload["result"]
        return payload

    def _approval_token_for(
        self,
        tools: dict[str, ToolCallable],
        tool_name: str,
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        preview = self._load_payload(asyncio.run(tools[tool_name](preview=True, **kwargs)))
        return cast(str, preview["new_state"]["approval_token"]), preview

    def test_memory_tool_schema_exposes_targets_for_install_add_and_manifest_write(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        install_schema = self._load_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_skill_install"))
        )
        add_schema = self._load_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_skill_add"))
        )
        manifest_schema = self._load_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_skill_manifest_write"))
        )

        expected_targets = ["claude", "codex", "cursor", "engram", "generic"]
        self.assertEqual(
            install_schema["properties"]["targets"]["oneOf"][0]["items"]["enum"],
            expected_targets,
        )
        self.assertEqual(
            add_schema["properties"]["targets"]["oneOf"][0]["items"]["enum"],
            expected_targets,
        )
        self.assertEqual(
            manifest_schema["properties"]["targets"]["oneOf"][0]["items"]["enum"],
            expected_targets,
        )

    def test_memory_skill_add_records_targets_and_list_reports_effective_targets(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults:\n  targets: [engram, claude]\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_add",
            slug="targeted-skill",
            title="Targeted Skill",
            description="Skill with explicit targets.",
            source="template",
            trust="medium",
            origin_session=TEST_SESSION_ID,
            targets=["cursor", "codex", "cursor"],
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_add"](
                    slug="targeted-skill",
                    title="Targeted Skill",
                    description="Skill with explicit targets.",
                    source="template",
                    trust="medium",
                    origin_session=TEST_SESSION_ID,
                    targets=["cursor", "codex", "cursor"],
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["manifest_entry"]["targets"], ["cursor", "codex"])
        self.assertEqual(payload["effective_targets"], ["cursor", "codex"])

        listed = self._load_payload(asyncio.run(tools["memory_skill_list"]()))
        entry = next(item for item in listed["skills"] if item["slug"] == "targeted-skill")
        self.assertEqual(entry["targets"], ["cursor", "codex"])
        self.assertEqual(entry["effective_targets"], ["cursor", "codex"])

    def test_memory_skill_manifest_write_rejects_unknown_target_name(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaisesRegex(Exception, "unknown target"):
            asyncio.run(
                tools["memory_skill_manifest_write"](
                    preview=True,
                    slug="manifest-only-skill",
                    source="local",
                    trust="medium",
                    description="Manifest-only skill.",
                    targets=["bogus-target"],
                )
            )

    def test_memory_skill_install_records_explicit_targets(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults:\n  targets: [engram, generic]\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
            }
        )
        shared_skill = self.temp_root / "shared-skills" / "demo-skill"
        shared_skill.mkdir(parents=True, exist_ok=True)
        (shared_skill / "SKILL.md").write_text(
            """---
name: demo-skill
description: Shared path skill.
source: user-stated
origin_session: manual
created: "2026-04-09"
trust: high
---

# Demo Skill
""",
            encoding="utf-8",
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_install",
            source="path:../shared-skills/demo-skill",
            slug="installed-demo",
            targets=["claude"],
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_install"](
                    source="path:../shared-skills/demo-skill",
                    slug="installed-demo",
                    targets=["claude"],
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["manifest_entry"]["targets"], ["claude"])
        self.assertEqual(payload["effective_targets"], ["claude"])

    def test_memory_skill_sync_rejects_unknown_target_name_in_manifest(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": """schema_version: 1
defaults:
  targets: [bogus-target]
skills: {}
""",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaisesRegex(Exception, "unknown target"):
            asyncio.run(
                tools["memory_skill_sync"](
                    check_only=True,
                    fix_stale_locks=False,
                    regenerate_indexes=False,
                )
            )

    def test_memory_skill_sync_repairs_distribution_outputs_and_list_reports_distribution_state(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": """schema_version: 1
defaults:
  targets: [cursor]
skills:
  local-skill:
    source: local
    trust: high
    description: Local skill.
""",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
                "memory/skills/local-skill/SKILL.md": """---
name: Local Skill
description: Local skill.
source: user-stated
origin_session: manual
created: "2026-04-16"
trust: high
---

## Usage

Follow the local workflow.
""",
            }
        )
        distributor = importlib.import_module("core.tools.agent_memory_mcp.skill_distributor")
        report, code = distributor.build_distribution_report(
            self._git_root(repo_root),
            dry_run=False,
            prefer_symlink=False,
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["distributed_count"], 1)

        tools = self._create_tools(repo_root)
        listed = self._load_payload(asyncio.run(tools["memory_skill_list"]()))
        entry = next(item for item in listed["skills"] if item["slug"] == "local-skill")
        self.assertEqual(entry["distribution"]["status"], "healthy")

        cursor_path = self._repo_file(repo_root, ".cursor/skills/local-skill.md")
        cursor_path.write_text("# Drifted Skill\n", encoding="utf-8")

        listed = self._load_payload(asyncio.run(tools["memory_skill_list"]()))
        entry = next(item for item in listed["skills"] if item["slug"] == "local-skill")
        self.assertEqual(entry["distribution"]["status"], "needs_attention")

        check_only = self._load_payload(
            asyncio.run(
                tools["memory_skill_sync"](
                    check_only=True,
                    fix_stale_locks=False,
                    regenerate_indexes=False,
                )
            )
        )
        self.assertEqual(check_only["issues_found"]["distribution_errors"], 1)

        repaired = self._load_payload(
            asyncio.run(
                tools["memory_skill_sync"](
                    fix_stale_locks=False,
                    regenerate_indexes=False,
                )
            )
        )
        self.assertEqual(repaired["actions_taken"]["distribution_repaired"], 1)
        self.assertTrue(cursor_path.read_text(encoding="utf-8").startswith("# Local Skill\n"))

        listed = self._load_payload(asyncio.run(tools["memory_skill_list"]()))
        entry = next(item for item in listed["skills"] if item["slug"] == "local-skill")
        self.assertEqual(entry["distribution"]["status"], "healthy")

    def test_memory_skill_sync_prunes_opted_out_distribution_targets(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": """schema_version: 1
defaults:
  targets: [cursor]
skills:
  local-skill:
    source: local
    trust: high
    description: Local skill.
""",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
                "memory/skills/local-skill/SKILL.md": """---
name: Local Skill
description: Local skill.
source: user-stated
origin_session: manual
created: "2026-04-16"
trust: high
---

## Usage

Follow the local workflow.
""",
            }
        )
        distributor = importlib.import_module("core.tools.agent_memory_mcp.skill_distributor")
        report, code = distributor.build_distribution_report(
            self._git_root(repo_root),
            dry_run=False,
            prefer_symlink=False,
        )
        self.assertEqual(code, 0)

        manifest_path = self._repo_file(repo_root, "core/memory/skills/SKILLS.yaml")
        manifest_path.write_text(
            """schema_version: 1
defaults:
  targets: [engram]
skills:
  local-skill:
    source: local
    trust: high
    description: Local skill.
""",
            encoding="utf-8",
        )

        tools = self._create_tools(repo_root)
        listed = self._load_payload(asyncio.run(tools["memory_skill_list"]()))
        entry = next(item for item in listed["skills"] if item["slug"] == "local-skill")
        self.assertEqual(entry["distribution"]["status"], "needs_attention")

        repaired = self._load_payload(
            asyncio.run(
                tools["memory_skill_sync"](
                    fix_stale_locks=False,
                    regenerate_indexes=False,
                )
            )
        )
        self.assertEqual(repaired["actions_taken"]["distribution_repaired"], 1)
        self.assertFalse(self._repo_file(repo_root, ".cursor/skills/local-skill.md").exists())

        listed = self._load_payload(asyncio.run(tools["memory_skill_list"]()))
        entry = next(item for item in listed["skills"] if item["slug"] == "local-skill")
        self.assertEqual(entry["distribution"]["status"], "not_requested")


if __name__ == "__main__":
    unittest.main()
