from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VIEWS_DIR = REPO_ROOT / "HUMANS" / "views"


def extract_inline_script(html_text: str) -> str:
    marker = "<script>"
    start = html_text.rfind(marker)
    if start < 0:
        raise AssertionError("Expected inline <script> block")
    end = html_text.find("</script>", start)
    if end < 0:
        raise AssertionError("Expected closing </script> for inline block")
    return html_text[start + len(marker) : end]


def extract_js_function(source: str, function_name: str) -> str:
    marker = f"function {function_name}("
    start = source.find(marker)
    if start < 0:
        raise AssertionError(f"Could not find function {function_name}")

    brace_start = source.find("{", start)
    if brace_start < 0:
        raise AssertionError(f"Could not find body for function {function_name}")

    depth = 0
    for idx in range(brace_start, len(source)):
        ch = source[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]

    raise AssertionError(f"Unbalanced braces while parsing function {function_name}")


def run_node_script(script: str, env: dict[str, str] | None = None) -> str:
    if shutil.which("node") is None:
        raise unittest.SkipTest("node is required for this test")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        env=merged_env,
    )
    return result.stdout.strip()


class TracesHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (VIEWS_DIR / "traces.html").read_text(encoding="utf-8")

    def test_traces_binds_engram_utilities_before_use(self) -> None:
        self.assertIn("var E = window.Engram;", self.text)
        self.assertIn("var readFile = E && E.readFile;", self.text)
        self.assertIn("var listDir = E && E.listDir;", self.text)
        self.assertIn("var clearNode = E && E.clearNode;", self.text)
        self.assertIn(
            "if (!E || typeof readFile !== 'function' || typeof listDir !== 'function')",
            self.text,
        )

    def test_traces_status_rendering_is_text_only(self) -> None:
        self.assertIn("function buildStatusBadge(rawStatus)", self.text)
        self.assertIn("badge.className = 'badge ' + token;", self.text)
        self.assertIn("badge.textContent = token;", self.text)
        self.assertIn("return KNOWN_STATUSES[v] ? v : 'unknown';", self.text)
        self.assertNotIn("innerHTML", self.text)

    def test_traces_removed_inline_handlers(self) -> None:
        self.assertNotRegex(self.text, r"\bonclick\s*=")
        self.assertNotRegex(self.text, r"\bonchange\s*=")


class GraphLifecycleHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (VIEWS_DIR / "graph.js").read_text(encoding="utf-8")

    def test_graph_uses_disposer_listener_model(self) -> None:
        self.assertIn("var listenerDisposers = [];", self.text)
        self.assertIn("function registerListener(target, type, handler, options)", self.text)
        self.assertIn("function disposeListeners()", self.text)
        self.assertIn("disposeListeners();", self.text)

    def test_graph_startgraph_has_no_untracked_add_event_listener_calls(self) -> None:
        start = self.text.index("function startGraph(graph)")
        end = self.text.index("/* ── Public API")
        body = self.text[start:end]
        # One add/remove pair exists inside registerListener itself.
        self.assertEqual(body.count("addEventListener("), 1, body)
        self.assertEqual(body.count("removeEventListener("), 1, body)

    def test_graph_has_async_stale_result_guards(self) -> None:
        self.assertIn("var previewRequestToken = 0;", self.text)
        self.assertIn("var connectionsRequestToken = 0;", self.text)
        self.assertIn("requestToken !== previewRequestToken", self.text)
        self.assertIn(
            "requestToken !== connectionsRequestToken || previewNodeId !== nodeId", self.text
        )


class ProjectsHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html_text = (VIEWS_DIR / "projects.html").read_text(encoding="utf-8")
        cls.script_text = extract_inline_script(cls.html_text)

    def test_projects_uses_js_yaml_and_sanitized_marker_ids(self) -> None:
        self.assertIn("js-yaml@4.1.0/dist/js-yaml.min.js", self.html_text)
        self.assertIn("var yamlApi = window.jsyaml;", self.script_text)
        self.assertIn("function sanitizeSvgId(value, fallback)", self.script_text)
        self.assertIn("var markerSuffix = sanitizeSvgId", self.script_text)
        self.assertIn(
            "var implicitMarkerId = 'fc-arrow-implicit-' + markerSuffix;", self.script_text
        )
        self.assertIn(
            "var explicitMarkerId = 'fc-arrow-explicit-' + markerSuffix;", self.script_text
        )

    def test_projects_parse_plan_normalizes_to_strict_model(self) -> None:
        function_names = [
            "normalizeString",
            "normalizeToken",
            "normalizePlanStatus",
            "normalizePlanId",
            "normalizeStringList",
            "uniqueList",
            "normalizeChangeEntry",
            "normalizeChangesList",
            "normalizePhaseEntry",
            "normalizePlanModel",
            "parsePlanYaml",
        ]
        function_src = "\n\n".join(
            extract_js_function(self.script_text, name) for name in function_names
        )

        fixture = {
            "id": "quoted-plan",
            "status": "active",
            "purpose": {"summary": 'Fix "quoted" values safely'},
            "work": {
                "phases": [
                    {
                        "id": "phase-1",
                        "title": "Collect data",
                        "status": "completed",
                        "blockers": ["seed"],
                        "changes": [
                            {
                                "path": "core/a.md",
                                "action": "edit",
                                "description": "capture baseline",
                            }
                        ],
                    },
                    {
                        "id": "phase-2",
                        "title": "Ship patch",
                        "status": "in-progress",
                        "blockers": ["phase-1", "other-plan:gate"],
                        "changes": [
                            {"path": "core/b.md", "action": "create", "description": "apply fix"}
                        ],
                    },
                ]
            },
        }

        script = f"""
var yamlApi = {{
  load: function () {{
    return JSON.parse(process.env.FIXTURE_JSON);
  }}
}};
{function_src}
var result = parsePlanYaml('ignored', 'fallback-plan.yaml');
process.stdout.write(JSON.stringify(result));
"""
        output = run_node_script(script, env={"FIXTURE_JSON": json.dumps(fixture)})
        parsed = json.loads(output)

        self.assertEqual(
            set(parsed.keys()),
            {"id", "project", "status", "summary", "phases", "changes", "blockers"},
        )
        self.assertEqual(parsed["id"], "quoted-plan")
        self.assertEqual(parsed["status"], "active")
        self.assertEqual(parsed["summary"], 'Fix "quoted" values safely')
        self.assertEqual(len(parsed["phases"]), 2)
        self.assertEqual(parsed["phases"][1]["id"], "phase-2")
        self.assertIn("other-plan:gate", parsed["blockers"])
        self.assertGreaterEqual(len(parsed["changes"]), 2)


class EngramUtilsLinkSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (VIEWS_DIR / "engram-utils.js").read_text(encoding="utf-8")

    def test_link_safety_helper_exported(self) -> None:
        self.assertIn("function isSafeLinkHref(href)", self.text)
        self.assertIn("isSafeLinkHref: isSafeLinkHref,", self.text)

    def test_link_safety_allows_expected_and_blocks_unsafe_schemes(self) -> None:
        fn_src = extract_js_function(self.text, "isSafeLinkHref")
        script = f"""
{fn_src}
var cases = {{
  'https://example.com': isSafeLinkHref('https://example.com'),
  'http://example.com': isSafeLinkHref('http://example.com'),
  'mailto:test@example.com': isSafeLinkHref('mailto:test@example.com'),
  '#section-1': isSafeLinkHref('#section-1'),
  '/notes/index.md': isSafeLinkHref('/notes/index.md'),
  './local.md': isSafeLinkHref('./local.md'),
  '../parent.md': isSafeLinkHref('../parent.md'),
  'docs/page.md': isSafeLinkHref('docs/page.md'),
  '?q=links': isSafeLinkHref('?q=links'),
  'javascript:alert(1)': isSafeLinkHref('javascript:alert(1)'),
  'data:text/html,<b>x</b>': isSafeLinkHref('data:text/html,<b>x</b>'),
  'file:///tmp/poc': isSafeLinkHref('file:///tmp/poc'),
  'ftp://example.com': isSafeLinkHref('ftp://example.com'),
  '//evil.example': isSafeLinkHref('//evil.example')
}};
process.stdout.write(JSON.stringify(cases));
"""
        out = run_node_script(script)
        data = json.loads(out)

        self.assertTrue(data["https://example.com"])
        self.assertTrue(data["http://example.com"])
        self.assertTrue(data["mailto:test@example.com"])
        self.assertTrue(data["#section-1"])
        self.assertTrue(data["/notes/index.md"])
        self.assertTrue(data["./local.md"])
        self.assertTrue(data["../parent.md"])
        self.assertTrue(data["docs/page.md"])
        self.assertTrue(data["?q=links"])

        self.assertFalse(data["javascript:alert(1)"])
        self.assertFalse(data["data:text/html,<b>x</b>"])
        self.assertFalse(data["file:///tmp/poc"])
        self.assertFalse(data["ftp://example.com"])
        self.assertFalse(data["//evil.example"])


class SkillsUsersMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skills = (VIEWS_DIR / "skills.html").read_text(encoding="utf-8")
        cls.users = (VIEWS_DIR / "users.html").read_text(encoding="utf-8")

    def test_skill_icons_are_unicode_not_entities(self) -> None:
        icon_block_match = re.search(r"var iconMap = \{[\s\S]*?\};", self.skills)
        self.assertIsNotNone(icon_block_match, "Expected iconMap block in skills.html")
        icon_block = icon_block_match.group(0)
        self.assertNotIn("&#", icon_block)
        self.assertIn("return iconMap[name] || '🔧';", self.skills)

    def test_users_low_trust_badge_is_consistent(self) -> None:
        self.assertIn(": trust === 'low' ? 'badge-low' : '';", self.users)
        self.assertIn("var trustToken = String(meta[key]).toLowerCase();", self.users)
        self.assertIn(
            "val.className = 'badge ' + (trustToken === 'high' ? 'badge-high' : trustToken === 'medium' ? 'badge-medium' : 'badge-low');",
            self.users,
        )


if __name__ == "__main__":
    unittest.main()
