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

CATALOG_SCRIPT = """def regenerate_skill_tree_markdown(repo_root, log_missing_frontmatter=False):\n    return '# Skill Catalog\\n'\n\ndef regenerate_skills_summary_markdown(repo_root):\n    return '# Skills Summary\\n'\n\ndef iter_disk_skill_slugs(skills_dir):\n    return sorted(\n        child.name\n        for child in skills_dir.iterdir()\n        if child.is_dir() and not child.name.startswith('_') and (child / 'SKILL.md').is_file()\n    )\n"""
TEST_SESSION_ID = "memory/activity/2026/04/15/chat-001"
MANAGED_GITIGNORE_BLOCK = """# BEGIN ENGRAM MANAGED SKILL DEPLOYMENT
# Derived from SKILLS.yaml effective deployment_mode. Edit the manifest, not this block.
/low-skill/
# END ENGRAM MANAGED SKILL DEPLOYMENT
"""


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

    def test_memory_tool_schema_returns_skill_add_contract_with_deployment_mode(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_skill_add"))
        )

        self.assertEqual(payload["tool_name"], "memory_skill_add")
        self.assertIn("deployment_mode", payload["properties"])
        self.assertEqual(
            payload["properties"]["deployment_mode"]["oneOf"][0]["enum"],
            ["checked", "gitignored"],
        )

    def test_memory_skill_install_installs_path_skill_with_slug_override(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
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
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
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
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
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

    def test_memory_skill_install_leaves_gitignored_skill_untracked(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
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
            trust="low",
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_install"](
                    source="path:../shared-skills/demo-skill",
                    slug="installed-demo",
                    trust="low",
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["effective_deployment_mode"], "gitignored")
        installed_skill = self._repo_file(repo_root, "core/memory/skills/installed-demo/SKILL.md")
        self.assertTrue(installed_skill.is_file())

        gitignore_path = self._repo_file(repo_root, "core/memory/skills/.gitignore")
        self.assertIn(
            "/installed-demo/",
            gitignore_path.read_text(encoding="utf-8"),
        )

        tracked = subprocess.run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                "--",
                "core/memory/skills/installed-demo/SKILL.md",
            ],
            cwd=self._git_root(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(tracked.returncode, 0)

    def test_memory_skill_sync_reconciles_managed_gitignore_block(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": """schema_version: 1
defaults: {}
skills:
  high-skill:
    source: local
    trust: high
    description: High trust checked skill.
  low-skill:
    source: local
    trust: low
    description: Low trust gitignored skill.
""",
                "memory/skills/high-skill/SKILL.md": """---
name: high-skill
description: High trust checked skill.
source: user-stated
origin_session: manual
created: 2026-04-09
trust: high
---

# High Skill
""",
                "memory/skills/low-skill/SKILL.md": """---
name: low-skill
description: Low trust local skill.
source: agent-generated
origin_session: manual
created: 2026-04-09
trust: low
---

# Low Skill
""",
            }
        )
        tools = self._create_tools(repo_root)

        first = self._load_payload(
            asyncio.run(
                tools["memory_skill_sync"](
                    fix_stale_locks=False,
                    regenerate_indexes=False,
                )
            )
        )
        self.assertTrue(first["actions_taken"]["deployment_gitignore_refreshed"])

        gitignore_path = self._repo_file(repo_root, "core/memory/skills/.gitignore")
        first_text = gitignore_path.read_text(encoding="utf-8")
        self.assertIn("# BEGIN ENGRAM MANAGED SKILL DEPLOYMENT", first_text)
        self.assertNotIn("/low-skill/", first_text)
        self.assertNotIn("/high-skill/", first_text)

        second = self._load_payload(
            asyncio.run(
                tools["memory_skill_sync"](
                    fix_stale_locks=False,
                    regenerate_indexes=False,
                )
            )
        )
        self.assertFalse(second["actions_taken"]["deployment_gitignore_refreshed"])
        self.assertEqual(first_text, gitignore_path.read_text(encoding="utf-8"))

    def test_memory_skill_add_keeps_local_template_skill_checked_for_fresh_clone(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_add",
            slug="draft-skill",
            title="Draft Skill",
            description="Draft skill.",
            source="template",
            trust="low",
            origin_session=TEST_SESSION_ID,
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_add"](
                    slug="draft-skill",
                    title="Draft Skill",
                    description="Draft skill.",
                    source="template",
                    trust="low",
                    origin_session=TEST_SESSION_ID,
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["effective_deployment_mode"], "checked")
        self.assertTrue(
            self._repo_file(repo_root, "core/memory/skills/draft-skill/SKILL.md").is_file()
        )
        self.assertNotIn(
            "/draft-skill/",
            self._repo_file(repo_root, "core/memory/skills/.gitignore").read_text(encoding="utf-8"),
        )

        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", "core/memory/skills/draft-skill/SKILL.md"],
            cwd=self._git_root(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(tracked.returncode, 0)

    def test_memory_skill_add_rejects_gitignored_template_skill(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaisesRegex(Exception, "cannot be 'gitignored' when source is 'local'"):
            asyncio.run(
                tools["memory_skill_add"](
                    preview=True,
                    slug="draft-skill",
                    title="Draft Skill",
                    description="Draft skill.",
                    source="template",
                    trust="low",
                    origin_session=TEST_SESSION_ID,
                    deployment_mode="gitignored",
                )
            )

    def test_memory_skill_add_allows_checked_override_for_low_trust_skill(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_add",
            slug="checked-low-skill",
            title="Checked Low Skill",
            description="Low trust but checked skill.",
            source="template",
            trust="low",
            origin_session=TEST_SESSION_ID,
            deployment_mode="checked",
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_add"](
                    slug="checked-low-skill",
                    title="Checked Low Skill",
                    description="Low trust but checked skill.",
                    source="template",
                    trust="low",
                    origin_session=TEST_SESSION_ID,
                    deployment_mode="checked",
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["effective_deployment_mode"], "checked")
        self.assertEqual(payload["manifest_entry"]["deployment_mode"], "checked")
        self.assertNotIn(
            "/checked-low-skill/",
            self._repo_file(repo_root, "core/memory/skills/.gitignore").read_text(encoding="utf-8"),
        )

        tracked = subprocess.run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                "--",
                "core/memory/skills/checked-low-skill/SKILL.md",
            ],
            cwd=self._git_root(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(tracked.returncode, 0)

    def test_memory_skill_manifest_write_reconciles_gitignore_for_low_trust_entry(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_manifest_write",
            slug="manifest-only-skill",
            source="local",
            trust="low",
            description="Manifest-only low trust skill.",
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_manifest_write"](
                    slug="manifest-only-skill",
                    source="local",
                    trust="low",
                    description="Manifest-only low trust skill.",
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["new_state"]["effective_deployment_mode"], "checked")
        self.assertIn(
            "memory/skills/.gitignore",
            payload["files_changed"],
        )
        self.assertNotIn(
            "/manifest-only-skill/",
            self._repo_file(repo_root, "core/memory/skills/.gitignore").read_text(encoding="utf-8"),
        )

    def test_memory_skill_manifest_write_rejects_gitignored_local_entry(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
            }
        )
        tools = self._create_tools(repo_root)

        with self.assertRaisesRegex(Exception, "cannot be 'gitignored' when source is 'local'"):
            asyncio.run(
                tools["memory_skill_manifest_write"](
                    preview=True,
                    slug="manifest-only-skill",
                    source="local",
                    trust="low",
                    description="Manifest-only low trust skill.",
                    deployment_mode="gitignored",
                )
            )

    def test_memory_skill_install_keeps_local_skill_checked_for_fresh_clone(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": "schema_version: 1\ndefaults: {}\nskills: {}\n",
                "memory/skills/SUMMARY.md": "# Skills Summary\n",
                "memory/skills/local-skill/SKILL.md": """---
name: local-skill
description: Local skill.
source: user-stated
origin_session: manual
created: 2026-04-15
trust: high
---

# Local Skill
""",
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_install",
            source="local",
            slug="local-skill",
            trust="low",
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_install"](
                    source="local",
                    slug="local-skill",
                    trust="low",
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["effective_deployment_mode"], "checked")
        self.assertNotIn(
            "/local-skill/",
            self._repo_file(repo_root, "core/memory/skills/.gitignore").read_text(encoding="utf-8"),
        )

        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", "core/memory/skills/local-skill/SKILL.md"],
            cwd=self._git_root(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(tracked.returncode, 0)

    def test_memory_skill_remove_reconciles_gitignore_and_archives_skill(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": """schema_version: 1
defaults: {}
skills:
  low-skill:
    source: local
    trust: low
    description: Low trust skill.
""",
                "memory/skills/low-skill/SKILL.md": """---
name: low-skill
description: Low trust skill.
source: agent-generated
origin_session: manual
created: 2026-04-09
trust: low
---

# Low Skill
""",
            }
        )
        gitignore_path = self._repo_file(repo_root, "core/memory/skills/.gitignore")
        gitignore_path.write_text(MANAGED_GITIGNORE_BLOCK, encoding="utf-8")
        subprocess.run(
            ["git", "add", "core/memory/skills/.gitignore"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add managed gitignore"],
            cwd=self._git_root(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_remove",
            slug="low-skill",
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_remove"](
                    slug="low-skill",
                    approval_token=approval_token,
                )
            )
        )

        self.assertTrue(payload["deployment_gitignore_refreshed"])
        self.assertFalse(self._repo_file(repo_root, "core/memory/skills/low-skill").exists())
        self.assertTrue(
            self._repo_file(repo_root, "core/memory/skills/_archive/low-skill").is_dir()
        )
        gitignore_text = gitignore_path.read_text(encoding="utf-8")
        self.assertNotIn("/low-skill/", gitignore_text)
        self.assertIn("# BEGIN ENGRAM MANAGED SKILL DEPLOYMENT", gitignore_text)

    def test_memory_skill_sync_remove_missing_entries_updates_manifest_and_gitignore(self) -> None:
        repo_root = self._init_repo(
            {
                "HUMANS/tooling/scripts/generate_skill_catalog.py": CATALOG_SCRIPT,
                "memory/skills/SKILLS.yaml": """schema_version: 1
defaults: {}
skills:
  low-skill:
    source: local
    trust: low
    description: Low trust skill.
""",
                "memory/skills/.gitignore": MANAGED_GITIGNORE_BLOCK,
            }
        )
        tools = self._create_tools(repo_root)
        approval_token, _ = self._approval_token_for(
            tools,
            "memory_skill_sync",
            archive_orphans=False,
            remove_missing_entries=True,
            fix_stale_locks=False,
            regenerate_indexes=False,
        )

        payload = self._load_payload(
            asyncio.run(
                tools["memory_skill_sync"](
                    archive_orphans=False,
                    remove_missing_entries=True,
                    fix_stale_locks=False,
                    regenerate_indexes=False,
                    approval_token=approval_token,
                )
            )
        )

        self.assertEqual(payload["actions_taken"]["missing_entries_removed"], 1)
        self.assertTrue(payload["actions_taken"]["deployment_gitignore_refreshed"])
        manifest_text = self._repo_file(repo_root, "core/memory/skills/SKILLS.yaml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("low-skill", manifest_text)
        gitignore_text = self._repo_file(repo_root, "core/memory/skills/.gitignore").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("/low-skill/", gitignore_text)

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
