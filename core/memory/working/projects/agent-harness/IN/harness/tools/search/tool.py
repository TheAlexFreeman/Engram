from __future__ import annotations

from .backends import WebSearchBackend
from .factory import load_backend_from_env
from .types import SearchHit

_MAX_OUTPUT_CHARS = 80_000
_DEFAULT_MAX_RESULTS = 5
_MIN_RESULTS = 1
_MAX_RESULTS = 10
_DEFAULT_TIMEOUT = 30.0
_MIN_TIMEOUT = 5.0
_MAX_TIMEOUT = 60.0


def _sanitize_text(s: str) -> str:
    return "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 32)


def _format_hits(hits: list[SearchHit]) -> str:
    parts: list[str] = []
    for i, h in enumerate(hits, start=1):
        title = _sanitize_text(h.title)
        url = _sanitize_text(h.url)
        snippet = _sanitize_text(h.snippet)
        parts.append(f"### {i}. {title}\nURL: {url}\n{snippet}\n")
    return "\n".join(parts).strip() + ("\n" if parts else "")


class WebSearch:
    name = "web_search"
    description = (
        "Search the public web and return titles, URLs, and snippets. "
        "Results are third-party summaries and may be incomplete or outdated; cite URLs when stating facts. "
        "Configuration: set HARNESS_SEARCH_PROVIDER to brave (default), tavily, or bing. "
        "Set BRAVE_API_KEY, TAVILY_API_KEY, or AZURE_BING_SEARCH_KEY (+ optional AZURE_BING_SEARCH_ENDPOINT for Bing). "
        "Set HARNESS_SEARCH_DISABLED=1 to disable live search (tool still available; returns guidance)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string.",
            },
            "max_results": {
                "type": "integer",
                "description": f"Number of results to return ({_MIN_RESULTS}–{_MAX_RESULTS}). Default {_DEFAULT_MAX_RESULTS}.",
            },
            "timeout_sec": {
                "type": "integer",
                "description": f"HTTP timeout in seconds ({int(_MIN_TIMEOUT)}–{int(_MAX_TIMEOUT)}). Default {int(_DEFAULT_TIMEOUT)}.",
            },
        },
        "required": ["query"],
    }

    def __init__(self, backend: WebSearchBackend | None = None):
        self._injected = backend
        self._lazy_backend: WebSearchBackend | None = None

    def _get_backend(self) -> WebSearchBackend:
        if self._injected is not None:
            return self._injected
        if self._lazy_backend is None:
            self._lazy_backend = load_backend_from_env()
        return self._lazy_backend

    def run(self, args: dict) -> str:
        query = (args.get("query") or "").strip()
        if not query:
            raise ValueError("query must be a non-empty string")

        raw_max = args.get("max_results", _DEFAULT_MAX_RESULTS)
        try:
            max_results = int(raw_max)
        except (TypeError, ValueError) as e:
            raise ValueError("max_results must be an integer") from e
        max_results = max(_MIN_RESULTS, min(max_results, _MAX_RESULTS))

        raw_timeout = args.get("timeout_sec", _DEFAULT_TIMEOUT)
        try:
            timeout_sec = float(raw_timeout)
        except (TypeError, ValueError) as e:
            raise ValueError("timeout_sec must be a number") from e
        timeout_sec = max(_MIN_TIMEOUT, min(timeout_sec, _MAX_TIMEOUT))

        hits = self._get_backend().search(query, max_results=max_results, timeout_sec=timeout_sec)
        text = _format_hits(hits)
        if not text.strip():
            return "(no results)\n"
        if len(text) > _MAX_OUTPUT_CHARS:
            text = text[:_MAX_OUTPUT_CHARS] + f"\n\n[output truncated to {_MAX_OUTPUT_CHARS} characters]\n"
        return text
