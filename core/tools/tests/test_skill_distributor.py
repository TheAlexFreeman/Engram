from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_distributor_module() -> ModuleType:
    try:
        return importlib.import_module("core.tools.agent_memory_mcp.skill_distributor")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"skill_distributor dependencies unavailable: {exc.name}") from exc


class SkillDistributorTests(unittest.TestCase):
    module: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_distributor_module()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo_root = Path(self._tmpdir.name)

    def _write_yaml(self, rel_path: str, data: object) -> None:
        path = self.repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def _write_skill(
        self,
        slug: str,
        *,
        body: str = "## Usage\n\nRun the skill body.\n",
        frontmatter: dict[str, object] | None = None,
        extra_files: dict[str, str] | None = None,
    ) -> None:
        skill_dir = self.repo_root / "core" / "memory" / "skills" / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        metadata: dict[str, object] = {
            "name": "Demo Skill",
            "description": "Ship the canonical instructions.",
            "compatibility": ["claude", "cursor", "codex"],
            "trust": "medium",
        }
        if frontmatter:
            metadata.update(frontmatter)
        skill_text = (
            "---\n"
            + yaml.safe_dump(metadata, sort_keys=False).strip()
            + "\n---\n\n"
            + body.strip()
            + "\n"
        )
        (skill_dir / "SKILL.md").write_text(skill_text, encoding="utf-8")
        for rel_path, content in (extra_files or {}).items():
            target = skill_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def test_build_distribution_report_materializes_builtin_targets(self) -> None:
        slug = "demo-skill"
        self._write_skill(slug)
        self._write_yaml(
            "core/memory/skills/SKILLS.yaml",
            {
                "schema_version": 1,
                "defaults": {"targets": ["engram", "cursor", "codex", "claude"]},
                "skills": {slug: {"source": "local", "enabled": True}},
            },
        )

        report, code = self.module.build_distribution_report(
            self.repo_root,
            dry_run=False,
            prefer_symlink=False,
        )

        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["distributed_count"], 3)
        cursor_path = self.repo_root / ".cursor" / "skills" / f"{slug}.md"
        codex_skill = self.repo_root / ".codex" / "skills" / slug / "SKILL.md"
        codex_metadata = self.repo_root / ".codex" / "skills" / slug / "metadata.json"
        claude_skill = self.repo_root / ".claude" / "skills" / slug / "SKILL.md"
        self.assertTrue(cursor_path.is_file())
        self.assertTrue(codex_skill.is_file())
        self.assertTrue(codex_metadata.is_file())
        self.assertTrue(claude_skill.is_file())

        cursor_text = cursor_path.read_text(encoding="utf-8")
        self.assertTrue(cursor_text.startswith("# Demo Skill\n"))
        self.assertNotIn("source: local", cursor_text)
        self.assertIn("## Compatibility", cursor_text)

        claude_text = claude_skill.read_text(encoding="utf-8")
        self.assertTrue(claude_text.startswith("---\n"))
        metadata = json.loads(codex_metadata.read_text(encoding="utf-8"))
        self.assertEqual(metadata["target"], "codex")
        self.assertEqual(metadata["canonical_path"], f"core/memory/skills/{slug}")

        cursor_index = json.loads(
            (self.repo_root / ".cursor" / "skills" / ".engram-distribution.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            cursor_index["entries"][slug]["canonical_hash"],
            report["distributed"][0]["canonical_hash"],
        )

    def test_build_distribution_report_reports_missing_local_install(self) -> None:
        slug = "remote-skill"
        self._write_yaml(
            "core/memory/skills/SKILLS.yaml",
            {
                "schema_version": 1,
                "skills": {
                    slug: {
                        "source": "git:https://example.com/skills.git",
                        "deployment_mode": "gitignored",
                        "targets": ["cursor"],
                    }
                },
            },
        )

        report, code = self.module.build_distribution_report(self.repo_root)

        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failure_count"], 1)
        self.assertEqual(report["failed"][0]["reason"], "missing_local_install")

    def test_build_distribution_report_rejects_relative_links_for_flat_targets(self) -> None:
        slug = "linked-skill"
        self._write_skill(
            slug,
            body="## Usage\n\nSee [diagram](diagram.png) before running.\n",
            extra_files={"diagram.png": "not really png"},
        )
        self._write_yaml(
            "core/memory/skills/SKILLS.yaml",
            {
                "schema_version": 1,
                "skills": {slug: {"source": "local", "targets": ["cursor"]}},
            },
        )

        report, code = self.module.build_distribution_report(self.repo_root)

        self.assertEqual(code, 1)
        self.assertEqual(report["failed"][0]["reason"], "unsupported_auxiliary_files")

    def test_build_distribution_report_is_idempotent_with_force_copy(self) -> None:
        slug = "stable-skill"
        self._write_skill(slug)
        self._write_yaml(
            "core/memory/skills/SKILLS.yaml",
            {
                "schema_version": 1,
                "defaults": {"targets": ["claude", "cursor", "codex"]},
                "skills": {slug: {"source": "local"}},
            },
        )

        first_report, first_code = self.module.build_distribution_report(
            self.repo_root,
            dry_run=False,
            prefer_symlink=False,
        )
        self.assertEqual(first_code, 0)
        cursor_path = self.repo_root / ".cursor" / "skills" / f"{slug}.md"
        codex_index = self.repo_root / ".codex" / "skills" / ".engram-distribution.json"
        first_cursor = cursor_path.read_text(encoding="utf-8")
        first_index = codex_index.read_text(encoding="utf-8")

        second_report, second_code = self.module.build_distribution_report(
            self.repo_root,
            dry_run=False,
            prefer_symlink=False,
        )

        self.assertEqual(second_code, 0)
        self.assertEqual(second_report["status"], "ok")
        self.assertEqual(cursor_path.read_text(encoding="utf-8"), first_cursor)
        self.assertEqual(codex_index.read_text(encoding="utf-8"), first_index)
        claude_index = json.loads(
            (self.repo_root / ".claude" / "skills" / ".engram-distribution.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(claude_index["entries"][slug]["transport"], "copy")

    def test_inspect_all_reports_stale_rendered_output(self) -> None:
        slug = "inspect-skill"
        self._write_skill(slug, frontmatter={"name": "Inspect Skill"})
        self._write_yaml(
            "core/memory/skills/SKILLS.yaml",
            {
                "schema_version": 1,
                "skills": {slug: {"source": "local", "targets": ["cursor"]}},
            },
        )

        report, code = self.module.build_distribution_report(
            self.repo_root,
            dry_run=False,
            prefer_symlink=False,
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["distributed_count"], 1)

        cursor_path = self.repo_root / ".cursor" / "skills" / f"{slug}.md"
        cursor_path.write_text("# Drifted Skill\n", encoding="utf-8")

        inspection = self.module.SkillDistributor(self.repo_root).inspect_all()

        self.assertEqual(inspection["status"], "needs_attention")
        self.assertEqual(inspection["issue_count"], 1)
        self.assertEqual(inspection["issues"][0]["slug"], slug)
        self.assertEqual(inspection["issues"][0]["target"], "cursor")
        self.assertEqual(inspection["issues"][0]["issues"][0]["reason"], "stale_output")

    def test_inspect_all_reports_unexpected_distribution_entry(self) -> None:
        slug = "opted-out-skill"
        self._write_skill(slug)
        self._write_yaml(
            "core/memory/skills/SKILLS.yaml",
            {
                "schema_version": 1,
                "skills": {slug: {"source": "local", "targets": ["cursor"]}},
            },
        )

        report, code = self.module.build_distribution_report(
            self.repo_root,
            dry_run=False,
            prefer_symlink=False,
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["distributed_count"], 1)

        self._write_yaml(
            "core/memory/skills/SKILLS.yaml",
            {
                "schema_version": 1,
                "skills": {slug: {"source": "local", "targets": ["engram"]}},
            },
        )

        inspection = self.module.SkillDistributor(self.repo_root).inspect_all()

        self.assertEqual(inspection["status"], "needs_attention")
        self.assertEqual(inspection["issue_count"], 1)
        self.assertEqual(
            inspection["issues"][0]["issues"][0]["reason"],
            "unexpected_distribution_entry",
        )
