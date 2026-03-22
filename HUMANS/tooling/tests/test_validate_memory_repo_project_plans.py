from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "HUMANS" / "tooling" / "tests" / "test_validate_memory_repo.py"

SPEC = importlib.util.spec_from_file_location("validate_memory_repo_fixtures", FIXTURE_PATH)
assert SPEC is not None
fixtures = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules.setdefault("validate_memory_repo_fixtures", fixtures)
SPEC.loader.exec_module(fixtures)


class ValidateMemoryRepoProjectPlanTests(unittest.TestCase):
    def test_project_scoped_plan_with_required_fields_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            fixtures.build_minimal_repo(root)
            fixtures.write(
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
                    next_action: Implement phase 1
                    ---

                    # Roadmap
                    """
                ),
            )

            result = fixtures.validator.validate_repo(root)
            self.assertEqual(result.errors, [], "\n".join(result.errors))

    def test_project_scoped_plan_missing_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            fixtures.build_minimal_repo(root)
            fixtures.write(
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
                    next_action: Implement phase 1
                    ---

                    # Roadmap
                    """
                ),
            )

            result = fixtures.validator.validate_repo(root)
            self.assertTrue(
                any(
                    "plan files must define frontmatter key 'status'" in error
                    for error in result.errors
                )
            )


if __name__ == "__main__":
    unittest.main()
