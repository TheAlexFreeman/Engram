from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "generate_skill_catalog.py"

SPEC = importlib.util.spec_from_file_location("generate_skill_catalog", SCRIPT_PATH)
assert SPEC is not None
catalog = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = catalog
SPEC.loader.exec_module(catalog)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class GenerateSkillCatalogTests(unittest.TestCase):
    def test_regenerate_skill_tree_includes_trigger_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            write(
                repo_root / "core" / "memory" / "skills" / "onboarding" / "SKILL.md",
                """---
name: onboarding
description: First-session onboarding.
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
trigger:
  event: session-start
  matcher:
    condition: first_session
  priority: 100
---

# Onboarding
""",
            )
            write(
                repo_root / "core" / "memory" / "skills" / "session-sync" / "SKILL.md",
                """---
name: session-sync
description: Mid-session checkpoint.
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
trigger: session-checkpoint
---

# Session Sync
""",
            )

            content = catalog.regenerate_skill_tree_markdown(
                repo_root, log_missing_frontmatter=False
            )

        self.assertIn(
            "**Trigger:** session-start (condition=first_session, priority=100)",
            content,
        )
        self.assertIn("**Trigger:** session-checkpoint", content)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
