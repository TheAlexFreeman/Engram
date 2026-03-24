"""Names-index extraction for knowledge markdown trees.

The engine scans knowledge markdown files, extracts likely person names from
file headings and attributed section headings, and renders a draft NAMES.md
index. It is intentionally read-first: callers can preview the generated
content and decide separately whether to write it.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

SKIP_FILES: frozenset[str] = frozenset({"SUMMARY.md", "ACCESS.jsonl", "NAMES.md"})
SKIP_DIRS: frozenset[str] = frozenset({"_unverified"})

NOT_NAME_TOKENS: frozenset[str] = frozenset(
    {
        "ai",
        "llm",
        "llms",
        "ml",
        "gpt",
        "api",
        "mcp",
        "rl",
        "rlhf",
        "transformer",
        "bert",
        "frontier",
        "scaling",
        "alignment",
        "safety",
        "configuration",
        "integration",
        "engineering",
        "code",
        "software",
        "hardware",
        "network",
        "networks",
        "protocol",
        "protocols",
        "system",
        "systems",
        "tooling",
        "workflow",
        "pipeline",
        "deployment",
        "infrastructure",
        "database",
        "cache",
        "server",
        "client",
        "auth",
        "middleware",
        "async",
        "sync",
        "rest",
        "http",
        "dns",
        "css",
        "dom",
        "html",
        "javascript",
        "js",
        "typescript",
        "ts",
        "react",
        "django",
        "docker",
        "nginx",
        "celery",
        "orm",
        "sql",
        "nosql",
        "git",
        "agent",
        "agents",
        "agentic",
        "assisted",
        "automated",
        "automation",
        "benchmark",
        "evaluation",
        "profiling",
        "monitoring",
        "debugging",
        "testing",
        "migration",
        "refactoring",
        "optimization",
        "algorithmic",
        "fairness",
        "chaos",
        "character",
        "channels",
        "channel",
        "compression",
        "control",
        "counterfactuals",
        "coverage",
        "collapse",
        "concurrency",
        "conflict",
        "detection",
        "collective",
        "bypass",
        "action",
        "actions",
        "combined",
        "commits",
        "commit",
        "completed",
        "concepts",
        "constraint",
        "constraints",
        "convergent",
        "convex",
        "cheap",
        "talk",
        "classic",
        "colleagues",
        "consequence",
        "effect",
        "effects",
        "bounded",
        "differences",
        "difference",
        "wisdom",
        "avoid",
        "book",
        "books",
        "parts",
        "circuit",
        "clusters",
        "complete",
        "completeness",
        "complexity",
        "complex",
        "but",
        "could",
        "would",
        "should",
        "might",
        "biases",
        "bias",
        "proper",
        "tools",
        "tool",
        "tasks",
        "task",
        "space",
        "spaces",
        "bounds",
        "bound",
        "variance",
        "trace",
        "scope",
        "range",
        "limits",
        "limit",
        "border",
        "borders",
        "threads",
        "thread",
        "flows",
        "flow",
        "stream",
        "streams",
        "chains",
        "chain",
        "processes",
        "process",
        "attractors",
        "attractor",
        "curves",
        "curve",
        "lattices",
        "lattice",
        "fields",
        "surfaces",
        "law",
        "laws",
        "rule",
        "rules",
        "inequality",
        "theorem",
        "theorems",
        "lemma",
        "conjecture",
        "property",
        "corollary",
        "postulate",
        "entropy",
        "gradient",
        "gradients",
        "divergence",
        "dimension",
        "fractals",
        "fractal",
        "oscillators",
        "oscillator",
        "eigenvalues",
        "eigenvectors",
        "partitions",
        "partition",
        "angst",
        "sorge",
        "dasein",
        "mitsein",
        "weltanschauung",
        "lebenswelt",
        "urimpression",
        "ruf",
        "des",
        "zum",
        "tode",
        "sein",
        "werden",
        "haben",
        "seine",
        "seiner",
        "logos",
        "eidos",
        "telos",
        "polis",
        "embedded",
        "embodied",
        "enacted",
        "extended",
        "enactive",
        "detailed",
        "mechanically",
        "problematic",
        "recommended",
        "traditional",
        "rough",
        "simplest",
        "intrinsic",
        "extrinsic",
        "motivated",
        "ecological",
        "privileged",
        "grounded",
        "participatory",
        "coordinated",
        "kantian",
        "hegelian",
        "humean",
        "cartesian",
        "darwinian",
        "freudian",
        "marxian",
        "aristotelian",
        "platonic",
        "socratic",
        "nietzschean",
        "spinozist",
        "leibnizian",
        "lockean",
        "hobbesian",
        "python",
        "langchain",
        "pydantic",
        "redis",
        "vite",
        "upstash",
        "sourcegraph",
        "sentry",
        "lesswrong",
        "microsoft",
        "google",
        "openai",
        "anthropic",
        "spotify",
        "princeton",
        "codeium",
        "colpali",
        "imagenet",
        "convnets",
        "perceptrons",
        "huggingface",
        "hott",
        "hyde",
        "moe",
        "dbc",
        "log",
        "logs",
        "append",
        "only",
        "batch",
        "operations",
        "operation",
        "browser",
        "browsers",
        "storage",
        "incident",
        "report",
        "operational",
        "resilience",
        "page",
        "pages",
        "number",
        "numbers",
        "no",
        "not",
        "non",
        "pre",
        "post",
        "meta",
        "sub",
        "super",
        "doom",
        "discourse",
        "feedback",
        "loop",
        "loops",
        "free",
        "energy",
        "workshops",
        "meetups",
        "sandbox",
        "orphan",
        "branches",
        "branch",
        "personnel",
        "policy",
        "predicate",
        "pivotal",
        "crude",
        "discovery",
        "insight",
        "dimensions",
        "deontology",
        "teleology",
        "ontology",
        "epistemology",
        "axiology",
        "phenomenology",
        "hermeneutics",
        "semiotics",
        "dialectics",
        "crime",
        "school",
        "types",
        "type",
        "descent",
        "dilemma",
        "causation",
        "causality",
        "drift",
        "attack",
        "attacks",
        "points",
        "focal",
        "groups",
        "group",
        "latent",
        "prestige",
        "prisoner",
        "prison",
        "spin",
        "glasses",
        "glass",
        "subresource",
        "integrity",
        "router",
        "routers",
        "states",
        "state",
        "calibration",
        "pareto",
        "weak",
        "noise",
        "embeddings",
        "embedding",
        "ahead",
        "yet",
        "sleep",
        "later",
        "dynamics",
        "dynamic",
        "martingale",
        "martingales",
        "markets",
        "market",
        "modal",
        "cursor",
        "metadata",
        "jest",
        "proofs",
        "proof",
        "variables",
        "variable",
        "modals",
        "schuld",
        "la",
        "chair",
        "north",
        "norms",
        "norm",
        "position",
        "positions",
        "trilogy",
        "labs",
        "adjacent",
        "rationalist",
        "price",
        "second",
        "propositional",
        "plan",
        "schema",
        "redesign",
        "timeline",
        "tap",
        "reward",
        "realization",
        "interaction",
        "accumulation",
        "repeated",
        "polarization",
        "ages",
        "middle",
        "jewish",
        "medieval",
        "new",
        "old",
        "early",
        "late",
        "modern",
        "contemporary",
        "classical",
        "formal",
        "natural",
        "social",
        "cognitive",
        "ethical",
        "moral",
        "political",
        "historical",
        "theoretical",
        "practical",
        "applied",
        "general",
        "basic",
        "advanced",
        "critical",
        "empirical",
        "normative",
        "analytic",
        "analytical",
        "behavioral",
        "biological",
        "computational",
        "mathematical",
        "philosophical",
        "psychological",
        "scientific",
        "technical",
        "digital",
        "online",
        "academic",
        "institutional",
        "distributed",
        "generative",
        "adaptive",
        "evolutionary",
        "experimental",
        "recursive",
        "semantic",
        "logical",
        "probabilistic",
        "statistical",
        "quantitative",
        "qualitative",
        "functional",
        "structural",
        "procedural",
        "conceptual",
        "existential",
        "phenomenological",
        "transcendental",
        "aesthetic",
        "heuristic",
        "epistemic",
        "metaphysical",
        "ontological",
        "causal",
        "linguistic",
        "semiotic",
        "hermeneutic",
        "dialectical",
        "evaluative",
        "descriptive",
        "prescriptive",
        "theory",
        "model",
        "framework",
        "approach",
        "method",
        "methods",
        "analysis",
        "synthesis",
        "review",
        "overview",
        "introduction",
        "history",
        "critique",
        "problem",
        "question",
        "issue",
        "case",
        "research",
        "study",
        "survey",
        "assessment",
        "design",
        "architecture",
        "structure",
        "pattern",
        "patterns",
        "mechanism",
        "mechanisms",
        "principle",
        "principles",
        "concept",
        "idea",
        "view",
        "perspective",
        "category",
        "kind",
        "class",
        "form",
        "mode",
        "level",
        "phase",
        "stage",
        "period",
        "era",
        "age",
        "function",
        "role",
        "purpose",
        "goal",
        "aim",
        "objective",
        "community",
        "movement",
        "tradition",
        "culture",
        "society",
        "science",
        "philosophy",
        "logic",
        "ethics",
        "politics",
        "economics",
        "sociology",
        "anthropology",
        "psychology",
        "neuroscience",
        "language",
        "thought",
        "mind",
        "consciousness",
        "intelligence",
        "knowledge",
        "belief",
        "memory",
        "attention",
        "perception",
        "reasoning",
        "inference",
        "learning",
        "training",
        "data",
        "information",
        "evidence",
        "argument",
        "rights",
        "status",
        "identity",
        "agency",
        "autonomy",
        "affordance",
        "failure",
        "failures",
        "success",
        "error",
        "limitation",
        "implication",
        "implications",
        "application",
        "applications",
        "extension",
        "foundation",
        "foundations",
        "basis",
        "analog",
        "parallel",
        "comparison",
        "contrast",
        "distinction",
        "background",
        "context",
        "motivation",
        "summary",
        "conclusion",
        "discussion",
        "results",
        "findings",
        "connections",
        "relations",
        "objections",
        "limitations",
        "notes",
        "references",
        "examples",
        "preface",
        "appendix",
        "modes",
        "welfare",
        "challenges",
        "solutions",
        "strategies",
        "dangers",
        "origins",
        "uncertainty",
        "hypothesis",
        "claim",
        "realism",
        "idealism",
        "dualism",
        "monism",
        "pluralism",
        "pragmatism",
        "positivism",
        "naturalism",
        "rationalism",
        "empiricism",
        "foundationalism",
        "coherentism",
        "determinism",
        "relativism",
        "and",
        "or",
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "at",
        "from",
        "to",
        "with",
        "for",
        "as",
        "by",
        "via",
        "about",
        "into",
        "onto",
        "after",
        "before",
        "during",
        "against",
        "among",
        "over",
        "under",
        "above",
        "below",
        "across",
        "toward",
        "beyond",
        "within",
        "through",
        "between",
        "its",
        "their",
        "our",
        "this",
        "that",
        "these",
        "those",
    }
)

HONORIFIC_RE = re.compile(
    r"^(?:Sir|Dr\.?|Prof\.?|Professor|Saint|St\.|Rev\.?|Lord|Lady)\s+",
    re.IGNORECASE,
)
YEAR_SUFFIX_RE = re.compile(r"\s*\(\d[\d\s–\-BCE\.]*\)\s*$")
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
H2_RE = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
NAME_COLON_RE = re.compile(r"^([A-Z][A-Za-z.,'\u2019\s\-]{1,40}?):\s+")
NAME_AND_RE = re.compile(r"^([A-Z][A-Za-z.,'\u2019\s\-]{1,40}?)\s+and\s+")
PAREN_RE = re.compile(r"\(([A-Z][A-Za-z',.\s\-&]{1,60}?)\)")
PURE_YEAR_RE = re.compile(r"^\d[\d\s–\-BCE\.]*$")

_CONCEPT_SUFFIXES = (
    "ism",
    "isms",
    "ist",
    "ists",
    "ity",
    "ities",
    "ness",
    "tion",
    "tions",
    "ment",
    "ments",
    "ance",
    "ence",
    "ology",
    "ologies",
    "ics",
    "ing",
    "ings",
    "ated",
    "ized",
    "ised",
    "ified",
    "ened",
    "ally",
    "ably",
    "ibly",
    "edly",
    "heit",
    "keit",
    "welt",
    "schaft",
    "esis",
    "osis",
    "asis",
)

_SIGNAL_LABELS: dict[str, str] = {
    "h1_primary": "Primary subject",
    "h1_attributed": "Primary subject (attributed)",
    "h2_attributed": "Section coverage",
}
_SIGNAL_ORDER = ["h1_primary", "h1_attributed", "h2_attributed"]


def strip_frontmatter(content: str) -> tuple[str, str]:
    """Return (frontmatter_block_or_empty, body), handling LF and CRLF files."""
    if not content.startswith("---"):
        return "", content

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", content

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            split_at = sum(len(line) for line in lines[: index + 1])
            return content[:split_at], content[split_at:]
    return "", content


def normalize_name(raw: str) -> list[str]:
    cleaned = raw.strip().replace("*", "").replace("`", "").replace("_", " ").strip()
    cleaned = YEAR_SUFFIX_RE.sub("", cleaned).strip()
    cleaned = HONORIFIC_RE.sub("", cleaned).strip()
    parts: list[str] = []
    for chunk in re.split(r"\s+(?:and|&)\s+|,\s*", cleaned):
        normalized = chunk.strip()
        if normalized:
            parts.append(normalized)
    return parts


def is_likely_name(value: str) -> bool:
    if len(value) < 2 or len(value) > 55:
        return False
    if not value[0].isupper():
        return False
    if not any(char.isalpha() for char in value):
        return False
    if value.replace(".", "").replace("-", "").replace("–", "").isnumeric():
        return False
    if any(char.isdigit() for char in value):
        return False

    letters_only = re.sub(r"[^A-Za-z]", "", value)
    if letters_only.isupper() and len(letters_only) >= 2 and "." not in value:
        return False
    if re.match(r"^[A-Z]{2}", value) and "." not in value:
        return False

    words = value.split()
    if len(words) > 4:
        return False

    tokens_lower: list[str] = []
    for word in words:
        for part in word.replace("-", " ").split():
            tokens_lower.append(part.lower().strip(".,':;!?()*/\""))

    if any(token in NOT_NAME_TOKENS for token in tokens_lower):
        return False
    if any(token.endswith(suffix) for token in tokens_lower for suffix in _CONCEPT_SUFFIXES):
        return False
    return True


def _truncate_snippet(value: str, limit: int = 90) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3]}..."


def extract_h1_names(body: str) -> list[tuple[str, str, str]]:
    match = H1_RE.search(body)
    if not match:
        return []

    heading = match.group(1).strip()
    colon_index = heading.find(":")
    snippet = heading[colon_index + 1 :].strip() if colon_index != -1 else heading
    snippet = _truncate_snippet(snippet)

    results: list[tuple[str, str, str]] = []
    colon_match = NAME_COLON_RE.match(heading)
    if colon_match:
        results.append((colon_match.group(1).strip(), "h1_primary", snippet))
    else:
        and_match = NAME_AND_RE.match(heading)
        if and_match:
            results.append((and_match.group(1).strip(), "h1_primary", snippet))

    for paren_match in PAREN_RE.finditer(heading):
        inner = paren_match.group(1).strip()
        if not PURE_YEAR_RE.match(inner):
            results.append((inner, "h1_attributed", snippet))
    return results


def extract_section_names(body: str) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []
    for match in H2_RE.finditer(body):
        heading = match.group(1).strip()
        snippet = _truncate_snippet(heading)
        for paren_match in PAREN_RE.finditer(heading):
            inner = paren_match.group(1).strip()
            if not PURE_YEAR_RE.match(inner):
                results.append((inner, "h2_attributed", snippet))
    return results


def _empty_index() -> dict[str, dict[str, list[tuple[str, str]]]]:
    return defaultdict(lambda: defaultdict(list))


def generate_names_index(
    root: Path,
    knowledge_path: str = "memory/knowledge",
    output_path: str | None = None,
) -> dict[str, Any]:
    """Return a rendered names-index draft plus extraction stats."""
    knowledge_rel = knowledge_path.replace("\\", "/").strip().rstrip("/")
    if not knowledge_rel:
        raise ValueError("knowledge_path is required")

    resolved_root = root.resolve()
    knowledge_root = (resolved_root / knowledge_rel).resolve()
    try:
        knowledge_root.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("knowledge_path must stay within the repository root") from exc
    if not knowledge_root.is_dir():
        raise ValueError(f"knowledge path not found: {knowledge_rel}")

    target_output = output_path or f"{knowledge_rel}/NAMES.md"
    index = _empty_index()
    files_scanned = 0
    raw_candidate_count = 0

    for current_root, dirs, files in os.walk(knowledge_root):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        dirs.sort()

        for file_name in sorted(files):
            if not file_name.endswith(".md") or file_name in SKIP_FILES:
                continue

            file_path = Path(current_root) / file_name
            rel_path = file_path.relative_to(knowledge_root).as_posix()

            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError:
                continue

            files_scanned += 1
            _, body = strip_frontmatter(content)

            for raw_name, signal, snippet in extract_h1_names(body):
                raw_candidate_count += 1
                for normalized_name in normalize_name(raw_name):
                    if is_likely_name(normalized_name):
                        index[normalized_name][signal].append((rel_path, snippet))

            for raw_name, signal, snippet in extract_section_names(body):
                raw_candidate_count += 1
                for normalized_name in normalize_name(raw_name):
                    if not is_likely_name(normalized_name):
                        continue
                    already_h1 = any(
                        stored_rel == rel_path
                        for stronger_signal in ("h1_primary", "h1_attributed")
                        for stored_rel, _ in index.get(normalized_name, {}).get(stronger_signal, [])
                    )
                    if not already_h1:
                        index[normalized_name][signal].append((rel_path, snippet))

    for name in index:
        for signal in index[name]:
            seen_paths: set[str] = set()
            unique_entries: list[tuple[str, str]] = []
            for rel_path, snippet in index[name][signal]:
                if rel_path in seen_paths:
                    continue
                seen_paths.add(rel_path)
                unique_entries.append((rel_path, snippet))
            index[name][signal] = unique_entries

    sorted_names = sorted(index.keys(), key=lambda item: item.lower())
    rendered = render_names_index(
        sorted_names=sorted_names,
        index=index,
        files_scanned=files_scanned,
        generated_on=date.today().isoformat(),
    )

    signal_counts = {
        signal: sum(len(index[name].get(signal, [])) for name in sorted_names)
        for signal in _SIGNAL_ORDER
    }
    return {
        "knowledge_path": knowledge_rel,
        "output_path": target_output.replace("\\", "/"),
        "files_scanned": files_scanned,
        "raw_candidates": raw_candidate_count,
        "names_count": len(sorted_names),
        "signal_counts": signal_counts,
        "draft": rendered,
    }


def render_names_index(
    *,
    sorted_names: list[str],
    index: dict[str, dict[str, list[tuple[str, str]]]],
    files_scanned: int,
    generated_on: str,
) -> str:
    lines: list[str] = [
        "---",
        "source: agent-generated",
        "type: index",
        f"created: {generated_on}",
        "trust: low",
        "origin_session: manual",
        "---",
        "",
        "<!-- Auto-generated by extract_names.py / memory_generate_names_index. Re-run to refresh. -->",
        "",
        "# Names Index",
        "",
        f"_{len(sorted_names)} names · {files_scanned} source files · extracted {generated_on}_",
        "",
        "**Note:** Rough draft — names are extracted from file headings only, not from prose. "
        "May include false positives (concept phrases) and miss names that appear only in "
        "body text. Human review recommended before treating as authoritative.",
        "",
        "---",
        "",
    ]

    current_letter = ""
    for name in sorted_names:
        first_letter = name[0].upper()
        if first_letter != current_letter:
            current_letter = first_letter
            lines.append(f"## {current_letter}")
            lines.append("")

        lines.append(f"### {name}")
        for signal in _SIGNAL_ORDER:
            entries = index[name].get(signal, [])
            if not entries:
                continue
            lines.append(f"**{_SIGNAL_LABELS[signal]}:**")
            for rel_path, snippet in sorted(entries):
                link = f"[{rel_path}]({rel_path})"
                lines.append(f"- {link} — {snippet}" if snippet else f"- {link}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_names_index(
    root: Path, draft: str, output_path: str = "memory/knowledge/NAMES.md"
) -> Path:
    """Persist a rendered names-index draft under the content root."""
    resolved_root = root.resolve()
    target = (resolved_root / output_path.replace("\\", "/")).resolve()
    try:
        target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("output_path must stay within the repository root") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(draft, encoding="utf-8")
    return target
