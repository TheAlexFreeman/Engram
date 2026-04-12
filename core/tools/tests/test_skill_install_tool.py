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

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
ToolCallable = Callable[..., Coroutine[Any, Any, str]]


def load_server_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.server")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"agent_memory_mcp dependencies unavailable: {exc.name}") from exc


class SkillInstallToolTests(unittest.TestCase):
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

    def test_memory_tool_schema_returns_skill_install_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_skill_install"))
        )

        self.assertEqual(payload["tool_name"], "memory_skill_install")
        self.assertEqual(payload["required"], ["source"])
        self.assertEqual(payload["allOf"][0]["then"]["required"], ["approval_token"])
        self.assertEqual(payload["allOf"][1]["then"]["required"], ["slug"])
        self.assertEqual(payload["properties"]["preview"]["default"], False)

    def test_memory_skill_install_installs_path_skill_with_slug_override(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": """def regenerate_skill_tree_markdown(repo_root, log_missing_frontmatter=False):\n    return '# Skill Catalog\\n'\n""",
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
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
created: 2026-04-09
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
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_install"](
                    source="path:../shared-skills/demo-skill",
                    slug="installed-demo",
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["slug"], "installed-demo")
        installed_skill = self._repo_file(repo_root, "core/memory/skills/installed-demo/SKILL.md")
        self.assertTrue(installed_skill.is_file())
        installed_fm = yaml.safe_load(
            installed_skill.read_text(encoding="utf-8").split("---", 2)[1]
        )
        self.assertEqual(installed_fm["name"], "installed-demo")

        manifest = yaml.safe_load(
            self._repo_file(repo_root, "core/memory/skills/SKILLS.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["skills"]["installed-demo"]["source"],
            "path:../shared-skills/demo-skill",
        )
        self.assertEqual(manifest["skills"]["installed-demo"]["trust"], "high")

        lock_data = yaml.safe_load(
            self._repo_file(repo_root, "core/memory/skills/SKILLS.lock").read_text(encoding="utf-8")
        )
        self.assertEqual(
            lock_data["entries"]["installed-demo"]["resolved_path"],
            "core/memory/skills/installed-demo/",
        )
        self.assertNotIn("resolved_ref", lock_data["entries"]["installed-demo"])

    def test_memory_skill_install_installs_git_file_skill_and_locks_resolved_ref(self) -> None:
        source_repo = self.temp_root / "remote-source"
        self._init_repo(
            {
                "README.md": "# placeholder\n",
            }
        )
        self._init_git_repo_source(
            source_repo,
            {
                "skills/remote-skill/SKILL.md": """---
name: remote-skill
description: Remote git skill.
source: external-research
origin_session: manual
created: 2026-04-09
trust: medium
---

# Remote Skill
""",
            },
        )
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": """def regenerate_skill_tree_markdown(repo_root, log_missing_frontmatter=False):\n    return '# Skill Catalog\\n'\n""",
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_install",
            source=f"git:{source_repo.as_uri()}",
            slug="remote-skill",
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_install"](
                    source=f"git:{source_repo.as_uri()}",
                    slug="remote-skill",
                    approval_token=approval_token,
                )
            )
        )

        manifest = yaml.safe_load(
            self._repo_file(repo_root, "core/memory/skills/SKILLS.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["skills"]["remote-skill"]["source"],
            f"git:{source_repo.as_uri()}",
        )
        self.assertEqual(manifest["skills"]["remote-skill"]["trust"], "medium")

        lock_data = yaml.safe_load(
            self._repo_file(repo_root, "core/memory/skills/SKILLS.lock").read_text(encoding="utf-8")
        )
        resolved_ref = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(lock_data["entries"]["remote-skill"]["resolved_ref"], resolved_ref)
        self.assertEqual(payload["resolution"]["resolution_mode"], "remote")

    def test_memory_skill_install_locks_requested_ref_for_remote_skill(self) -> None:
        source_repo = self.temp_root / "remote-source-ref"
        self._init_repo(
            {
                "README.md": "# placeholder\n",
            }
        )
        self._init_git_repo_source(
            source_repo,
            {
                "skills/remote-skill/SKILL.md": """---
name: remote-skill
description: Remote git skill.
source: external-research
origin_session: manual
created: 2026-04-09
trust: medium
---

# Remote Skill
""",
            },
        )
        requested_ref = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": """def regenerate_skill_tree_markdown(repo_root, log_missing_frontmatter=False):\n    return '# Skill Catalog\\n'\n""",
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_install",
            source=f"git:{source_repo.as_uri()}",
            slug="remote-skill",
            ref=requested_ref,
        )

        asyncio.run(
            tools["memory_skill_install"](
                source=f"git:{source_repo.as_uri()}",
                slug="remote-skill",
                ref=requested_ref,
                approval_token=approval_token,
            )
        )

        lock_data = yaml.safe_load(
            self._repo_file(repo_root, "core/memory/skills/SKILLS.lock").read_text(encoding="utf-8")
        )
        self.assertEqual(lock_data["entries"]["remote-skill"]["requested_ref"], requested_ref)

    def _init_git_repo_source(self, root: Path, files: dict[str, str]) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
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
        for rel_path, content in files.items():
            target = root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", "seed"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return root


if __name__ == "__main__":
    unittest.main()
