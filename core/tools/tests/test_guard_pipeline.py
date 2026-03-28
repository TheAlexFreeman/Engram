"""Tests for the guard pipeline: Guard interface, built-in guards, and pipeline execution."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from engram_mcp.agent_memory_mcp.guard_pipeline import (
    ContentSizeGuard,
    FrontmatterGuard,
    Guard,
    GuardContext,
    GuardPipeline,
    GuardResult,
    TrustBoundaryGuard,
    default_pipeline,
)


def _ctx(path: str = "memory/working/notes/test.md", **overrides: Any) -> GuardContext:
    defaults: dict[str, Any] = {
        "path": path,
        "operation": "write",
        "root": Path(tempfile.gettempdir()),
        "content": "hello world",
    }
    defaults.update(overrides)
    return GuardContext(**defaults)


def _md_with_frontmatter(**fm_fields: Any) -> str:
    import yaml

    fm = yaml.dump(fm_fields, sort_keys=False)
    return f"---\n{fm}---\n\nBody content.\n"


class _AlwaysPassGuard(Guard):
    name = "AlwaysPass"

    def check(self, context: GuardContext) -> GuardResult:
        return GuardResult(status="pass", guard_name=self.name, message="")


class _AlwaysBlockGuard(Guard):
    name = "AlwaysBlock"

    def check(self, context: GuardContext) -> GuardResult:
        return GuardResult(status="block", guard_name=self.name, message="blocked")


class _AlwaysWarnGuard(Guard):
    name = "AlwaysWarn"

    def check(self, context: GuardContext) -> GuardResult:
        return GuardResult(status="warn", guard_name=self.name, message="heads up")


# ── Pipeline execution ───────────────────────────────────────────────────────


class TestGuardPipeline(unittest.TestCase):
    def test_empty_pipeline_allows(self):
        pipeline = GuardPipeline([])
        result = pipeline.run(_ctx())
        self.assertTrue(result.allowed)
        self.assertEqual(result.results, [])

    def test_all_pass(self):
        pipeline = GuardPipeline([_AlwaysPassGuard(), _AlwaysPassGuard()])
        result = pipeline.run(_ctx())
        self.assertTrue(result.allowed)
        self.assertEqual(len(result.results), 2)
        self.assertIsNone(result.blocked_by)

    def test_short_circuit_on_block(self):
        pipeline = GuardPipeline(
            [
                _AlwaysPassGuard(),
                _AlwaysBlockGuard(),
                _AlwaysPassGuard(),
            ]
        )
        result = pipeline.run(_ctx())
        self.assertFalse(result.allowed)
        self.assertEqual(result.blocked_by, "AlwaysBlock")
        self.assertEqual(len(result.results), 2)

    def test_warnings_accumulated(self):
        pipeline = GuardPipeline([_AlwaysWarnGuard(), _AlwaysWarnGuard()])
        result = pipeline.run(_ctx())
        self.assertTrue(result.allowed)
        self.assertEqual(len(result.warnings), 2)

    def test_warn_then_block(self):
        pipeline = GuardPipeline([_AlwaysWarnGuard(), _AlwaysBlockGuard()])
        result = pipeline.run(_ctx())
        self.assertFalse(result.allowed)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.blocked_by, "AlwaysBlock")

    def test_pipeline_result_to_dict(self):
        pipeline = GuardPipeline([_AlwaysPassGuard()])
        result = pipeline.run(_ctx())
        d = result.to_dict()
        self.assertIn("allowed", d)
        self.assertIn("results", d)
        self.assertIn("duration_ms", d)

    def test_duration_ms_is_set(self):
        pipeline = GuardPipeline([_AlwaysPassGuard()])
        result = pipeline.run(_ctx())
        self.assertIsInstance(result.duration_ms, int)
        self.assertGreaterEqual(result.duration_ms, 0)


# ── ContentSizeGuard ─────────────────────────────────────────────────────────


class TestContentSizeGuard(unittest.TestCase):
    def test_small_content_passes(self):
        guard = ContentSizeGuard()
        result = guard.check(_ctx(content="small"))
        self.assertEqual(result.status, "pass")

    def test_no_content_passes(self):
        guard = ContentSizeGuard()
        result = guard.check(_ctx(content=None, operation="delete"))
        self.assertEqual(result.status, "pass")

    def test_oversized_content_blocks(self):
        guard = ContentSizeGuard()
        big = "x" * 600_000
        result = guard.check(_ctx(content=big))
        self.assertEqual(result.status, "block")
        self.assertIn("exceeds", result.message)

    def test_env_override(self):
        guard = ContentSizeGuard()
        with mock.patch.dict("os.environ", {"ENGRAM_MAX_FILE_SIZE": "10"}):
            result = guard.check(_ctx(content="twelve chars"))
        self.assertEqual(result.status, "block")


# ── FrontmatterGuard ─────────────────────────────────────────────────────────


class TestFrontmatterGuard(unittest.TestCase):
    def test_valid_frontmatter_passes(self):
        guard = FrontmatterGuard()
        content = _md_with_frontmatter(
            source="agent-generated",
            trust="medium",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
        )
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "pass")

    def test_non_markdown_skipped(self):
        guard = FrontmatterGuard()
        result = guard.check(_ctx(path="memory/working/notes/test.json", content="{}"))
        self.assertEqual(result.status, "pass")

    def test_no_frontmatter_passes(self):
        guard = FrontmatterGuard()
        result = guard.check(_ctx(content="Just a plain markdown file.\n"))
        self.assertEqual(result.status, "pass")

    def test_invalid_source_blocks(self):
        guard = FrontmatterGuard()
        content = _md_with_frontmatter(
            source="invalid-source",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
            trust="medium",
        )
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "block")
        self.assertIn("invalid-source", result.message.lower())

    def test_invalid_trust_blocks(self):
        guard = FrontmatterGuard()
        content = _md_with_frontmatter(
            source="agent-generated",
            trust="ultra",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
        )
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "block")

    def test_missing_required_provenance_blocks(self):
        guard = FrontmatterGuard()
        content = _md_with_frontmatter(trust="medium")
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "block")
        self.assertIn("source", result.message)

    def test_source_unknown_is_allowed(self):
        guard = FrontmatterGuard()
        content = _md_with_frontmatter(
            source="unknown",
            trust="medium",
            created="2026-03-27",
            origin_session="unknown",
        )
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "pass")

    def test_malformed_yaml_blocks(self):
        guard = FrontmatterGuard()
        content = "---\n{bad: [yaml:\n---\n\nBody.\n"
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "block")


# ── TrustBoundaryGuard ───────────────────────────────────────────────────────


class TestTrustBoundaryGuard(unittest.TestCase):
    def test_trust_high_user_stated_passes(self):
        guard = TrustBoundaryGuard()
        content = _md_with_frontmatter(
            source="user-stated",
            trust="high",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
        )
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "pass")

    def test_trust_high_agent_requires_approval(self):
        guard = TrustBoundaryGuard()
        content = _md_with_frontmatter(
            source="agent-inferred",
            trust="high",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
        )
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "require_approval")

    def test_trust_medium_passes(self):
        guard = TrustBoundaryGuard()
        content = _md_with_frontmatter(
            source="agent-generated",
            trust="medium",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
        )
        result = guard.check(_ctx(content=content))
        self.assertEqual(result.status, "pass")

    def test_no_frontmatter_passes(self):
        guard = TrustBoundaryGuard()
        result = guard.check(_ctx(content="No frontmatter here.\n"))
        self.assertEqual(result.status, "pass")

    def test_non_markdown_skipped(self):
        guard = TrustBoundaryGuard()
        result = guard.check(_ctx(path="data.json", content='{"trust":"high"}'))
        self.assertEqual(result.status, "pass")


# ── default_pipeline ─────────────────────────────────────────────────────────


class TestDefaultPipeline(unittest.TestCase):
    def test_without_repo(self):
        pipeline = default_pipeline()
        self.assertEqual(len(pipeline.guards), 3)

    def test_valid_write_passes(self):
        pipeline = default_pipeline()
        content = _md_with_frontmatter(
            source="agent-generated",
            trust="medium",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
        )
        result = pipeline.run(_ctx(content=content))
        self.assertTrue(result.allowed)

    def test_oversized_blocks(self):
        pipeline = default_pipeline()
        result = pipeline.run(_ctx(content="x" * 600_000))
        self.assertFalse(result.allowed)
        self.assertEqual(result.blocked_by, "ContentSizeGuard")

    def test_trust_high_agent_blocks(self):
        pipeline = default_pipeline()
        content = _md_with_frontmatter(
            source="agent-generated",
            trust="high",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-001",
        )
        result = pipeline.run(_ctx(content=content))
        self.assertFalse(result.allowed)
        self.assertEqual(result.blocked_by, "TrustBoundaryGuard")


# ── GuardResult ──────────────────────────────────────────────────────────────


class TestGuardResult(unittest.TestCase):
    def test_to_dict(self):
        r = GuardResult(
            status="block", guard_name="TestGuard", message="nope", metadata={"key": "val"}
        )
        d = r.to_dict()
        self.assertEqual(d["status"], "block")
        self.assertEqual(d["metadata"]["key"], "val")


if __name__ == "__main__":
    unittest.main()
