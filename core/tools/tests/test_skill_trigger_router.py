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


def load_server_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.server")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"agent_memory_mcp dependencies unavailable: {exc.name}") from exc


class SkillTriggerRouterTests(unittest.TestCase):
    server: ClassVar[ModuleType]
    router_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = load_server_module()
        try:
            cls.router_module = importlib.import_module(
                "engram_mcp.agent_memory_mcp.skill_trigger_router"
            )
        except ModuleNotFoundError as exc:
            raise unittest.SkipTest(
                f"skill trigger router dependencies unavailable: {exc.name}"
            ) from exc

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _init_repo(self, files: dict[str, str]) -> Path:
        temp_root = Path(self._tmpdir.name) / f"repo_{len(files)}"
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

    def _create_tools(self, repo_root: Path) -> dict[str, ToolCallable]:
        _, tools, _, _ = self.server.create_mcp(repo_root=repo_root)
        return cast(dict[str, ToolCallable], tools)

    def _load_tool_payload(self, raw: str) -> Any:
        payload = cast(dict[str, Any], json.loads(raw))
        if "result" in payload:
            return payload["result"]
        return payload

    def test_memory_tool_schema_returns_skill_route_contract(self) -> None:
        repo_root = self._init_repo({"README.md": "# Test\n"})
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(tools["memory_tool_schema"](tool_name="memory_skill_route"))
        )

        self.assertEqual(payload["tool_name"], "memory_skill_route")
        self.assertEqual(payload["required"], ["event"])
        self.assertIn("session-start", payload["properties"]["event"]["enum"])
        self.assertTrue(payload["properties"]["include_catalog_fallback"]["default"])
        context_schema = payload["properties"]["context"]["oneOf"][0]
        self.assertFalse(context_schema["additionalProperties"])
        self.assertIn("conditions", context_schema["properties"])
        self.assertIn("skill_slug", context_schema["properties"])

    def test_memory_skill_route_orders_explicit_matches_before_catalog_fallback(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/SKILLS.yaml": """schema_version: 1
skills:
  session-start:
    source: local
    trust: high
    description: Returning-session startup router.
  session-notes:
    source: local
    trust: medium
    description: Returning session notes and reminders.
""",
                "memory/skills/session-start/SKILL.md": """---
name: session-start
description: Returning-session startup router.
trust: high
trigger:
  event: session-start
  matcher:
    condition: returning_session
  priority: 50
---

# Session Start
""",
                "memory/skills/session-notes/SKILL.md": """---
name: session-notes
description: Returning session notes and reminders.
trust: medium
---

# Session Notes
""",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                tools["memory_skill_route"](
                    event="session-start",
                    context={
                        "conditions": ["returning_session"],
                        "query": "returning session",
                    },
                    max_results=10,
                )
            )
        )

        self.assertEqual(
            [match["slug"] for match in payload["matches"]],
            ["session-start", "session-notes"],
        )
        self.assertEqual(payload["matches"][0]["dispatch_tier"], "explicit-trigger")
        self.assertEqual(payload["matches"][1]["dispatch_tier"], "catalog-match")
        self.assertIn("condition=returning_session", payload["matches"][0]["match_reason"])
        self.assertEqual(payload["dispatch_policy"]["mode"], "all")

    def test_trigger_router_uses_manifest_trigger_when_frontmatter_is_missing(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/SKILLS.yaml": """schema_version: 1
skills:
  codebase-survey:
    source: local
    trust: medium
    description: Project-specific survey.
    trigger:
      event: project-active
      matcher:
        project_id: demo
      priority: 30
""",
                "memory/skills/codebase-survey/SKILL.md": """---
name: codebase-survey
description: Project-specific survey.
trust: medium
---

# Codebase Survey
""",
            }
        )
        router = self.router_module.TriggerRouter(self._git_root(repo_root))

        payload = router.route(
            "project-active",
            {"project_id": "demo"},
            include_catalog_fallback=False,
        )

        self.assertEqual([match["slug"] for match in payload["matches"]], ["codebase-survey"])
        self.assertEqual(payload["matches"][0]["trigger_source"], "manifest")
        self.assertEqual(payload["matches"][0]["priority"], 30)

    def test_trigger_router_prefers_frontmatter_trigger_over_manifest_trigger(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/skills/SKILLS.yaml": """schema_version: 1
skills:
  session-start:
    source: local
    trust: high
    description: Startup helper.
    trigger:
      event: session-start
      matcher:
        condition: first_session
      priority: 10
""",
                "memory/skills/session-start/SKILL.md": """---
name: session-start
description: Startup helper.
trust: high
trigger:
  event: session-start
  matcher:
    condition: returning_session
  priority: 50
---

# Session Start
""",
            }
        )
        router = self.router_module.TriggerRouter(self._git_root(repo_root))

        payload = router.route(
            "session-start",
            {"conditions": ["returning_session"]},
            include_catalog_fallback=False,
        )

        self.assertEqual([match["slug"] for match in payload["matches"]], ["session-start"])
        self.assertEqual(payload["matches"][0]["trigger_source"], "frontmatter")
        self.assertEqual(payload["matches"][0]["priority"], 50)
        self.assertIn("returning_session", payload["matches"][0]["match_reason"])


if __name__ == "__main__":
    unittest.main()
