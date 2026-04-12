from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_resolver_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.skill_resolver")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"skill_resolver dependencies unavailable: {exc.name}") from exc


class SkillResolverTests(unittest.TestCase):
    module: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_resolver_module()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_root = Path(self._tmpdir.name)

    def _init_git_repo(self, root: Path, files: dict[str, str]) -> Path:
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

    def _git_head(self, root: Path) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def test_parse_skill_source_accepts_supported_formats(self) -> None:
        parse_skill_source = self.module.parse_skill_source

        local = parse_skill_source("local")
        path = parse_skill_source("path:../shared-skills/demo-skill")
        git_source = parse_skill_source("git:file:///tmp/demo.git", ref="main")
        github = parse_skill_source("github:octocat/shared-skills", ref="v1.2.0")

        self.assertEqual(local.source_type, "local")
        self.assertEqual(path.relative_path, "../shared-skills/demo-skill")
        self.assertEqual(git_source.git_url, "file:///tmp/demo.git")
        self.assertEqual(github.owner, "octocat")
        self.assertEqual(github.repo, "shared-skills")

    def test_resolve_local_source_uses_existing_skill_directory(self) -> None:
        repo_root = self._init_git_repo(
            self.temp_root / "vault",
            {
                "core/memory/skills/local-skill/SKILL.md": "# Local Skill\n",
            },
        )
        resolver = self.module.SkillResolver(repo_root)

        resolved = resolver.resolve("local", slug="local-skill")

        self.assertEqual(resolved.slug, "local-skill")
        self.assertEqual(resolved.resolution_mode, "local")
        self.assertTrue((resolved.skill_dir / "SKILL.md").is_file())
        self.assertIsNone(resolved.resolved_ref)

    def test_resolve_path_source_allows_parent_relative_paths(self) -> None:
        repo_root = self._init_git_repo(self.temp_root / "vault", {"README.md": "# Vault\n"})
        shared_skill = self.temp_root / "shared-skills" / "demo-skill"
        shared_skill.mkdir(parents=True, exist_ok=True)
        (shared_skill / "SKILL.md").write_text("# Shared Skill\n", encoding="utf-8")
        resolver = self.module.SkillResolver(repo_root)

        resolved = resolver.resolve("path:../shared-skills/demo-skill")

        self.assertEqual(resolved.slug, "demo-skill")
        self.assertEqual(resolved.resolution_mode, "path")
        self.assertEqual(resolved.skill_dir.resolve(), shared_skill.resolve())

    def test_resolve_git_file_source_clones_and_discovers_skill(self) -> None:
        source_repo = self._init_git_repo(
            self.temp_root / "source-repo",
            {
                "skills/example-skill/SKILL.md": "# Example Skill\n",
            },
        )
        repo_root = self._init_git_repo(self.temp_root / "vault", {"README.md": "# Vault\n"})
        resolver = self.module.SkillResolver(repo_root)

        resolved = resolver.resolve(f"git:{source_repo.as_uri()}", slug="example-skill")

        self.assertEqual(resolved.slug, "example-skill")
        self.assertEqual(resolved.resolution_mode, "remote")
        self.assertEqual(resolved.resolved_ref, self._git_head(source_repo))
        self.assertTrue((resolved.skill_dir / "SKILL.md").is_file())

    def test_resolve_github_shorthand_uses_clone_url_hook(self) -> None:
        source_repo = self._init_git_repo(
            self.temp_root / "source-repo",
            {
                "skills/example-skill/SKILL.md": "# Example Skill\n",
            },
        )
        repo_root = self._init_git_repo(self.temp_root / "vault", {"README.md": "# Vault\n"})
        resolver = self.module.SkillResolver(repo_root)
        resolver._github_clone_url = lambda owner, repo: source_repo.as_uri()  # type: ignore[method-assign]
        resolved = resolver.resolve("github:team/shared-skills", slug="example-skill")

        self.assertEqual(resolved.source_type, "github")
        self.assertEqual(resolved.resolution_mode, "remote")
        self.assertTrue((resolved.skill_dir / "SKILL.md").is_file())

    def test_resolve_prefers_fresh_locked_copy_for_remote_source(self) -> None:
        repo_root = self._init_git_repo(
            self.temp_root / "vault",
            {
                "core/memory/skills/locked-skill/SKILL.md": "# Locked Skill\n",
            },
        )
        resolver = self.module.SkillResolver(repo_root)
        skill_dir = repo_root / "core" / "memory" / "skills" / "locked-skill"
        content_hash = self.module.compute_content_hash(skill_dir)
        lock_entry = {
            "source": "git:https://invalid.example/shared-skills.git",
            "resolved_path": "core/memory/skills/locked-skill",
            "content_hash": content_hash,
            "resolved_ref": "abc123",
        }

        resolved = resolver.resolve(
            "git:https://invalid.example/shared-skills.git",
            slug="locked-skill",
            lock_entry=lock_entry,
        )

        self.assertEqual(resolved.resolution_mode, "locked")
        self.assertIsNotNone(resolved.lock_verification)
        self.assertTrue(resolved.lock_verification.usable)

    def test_frozen_mode_rejects_remote_source_without_fresh_lock(self) -> None:
        source_repo = self._init_git_repo(
            self.temp_root / "source-repo",
            {
                "skills/example-skill/SKILL.md": "# Example Skill\n",
            },
        )
        repo_root = self._init_git_repo(self.temp_root / "vault", {"README.md": "# Vault\n"})
        resolver = self.module.SkillResolver(repo_root)

        with self.assertRaises(self.module.SkillResolutionError):
            resolver.resolve(
                f"git:{source_repo.as_uri()}",
                slug="example-skill",
                frozen=True,
            )


if __name__ == "__main__":
    unittest.main()
