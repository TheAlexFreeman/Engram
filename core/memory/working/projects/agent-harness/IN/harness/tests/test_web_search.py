from __future__ import annotations

import httpx
import pytest

from harness.tools.search.brave import BraveBackend
from harness.tools.search.factory import load_backend_from_env
from harness.tools.search.tool import WebSearch
from harness.tools.search.types import SearchHit


class StaticBackend:
    def __init__(self, hits: list[SearchHit]):
        self.hits = hits

    def search(self, query: str, *, max_results: int, timeout_sec: float) -> list[SearchHit]:
        return self.hits[:max_results]


def test_load_backend_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_SEARCH_DISABLED", "1")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    b = load_backend_from_env()
    hits = b.search("anything", max_results=5, timeout_sec=10.0)
    assert len(hits) == 1
    assert "disabled" in hits[0].title.lower()


def test_load_backend_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_SEARCH_PROVIDER", "nope")
    monkeypatch.delenv("HARNESS_SEARCH_DISABLED", raising=False)
    with pytest.raises(ValueError, match="Unknown HARNESS_SEARCH_PROVIDER"):
        load_backend_from_env()


def test_load_backend_brave_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_SEARCH_PROVIDER", "brave")
    monkeypatch.delenv("HARNESS_SEARCH_DISABLED", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="BRAVE_API_KEY"):
        load_backend_from_env()


def test_load_backend_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.delenv("HARNESS_SEARCH_DISABLED", raising=False)
    b = load_backend_from_env()
    assert type(b).__name__ == "TavilyBackend"


def test_web_search_formats_and_truncates() -> None:
    long_snip = "x" * 100_000
    hits = [SearchHit(title="A", url="https://a.example", snippet=long_snip)]
    out = WebSearch(StaticBackend(hits)).run({"query": "q", "max_results": 1})
    assert "https://a.example" in out
    assert "[output truncated" in out


def test_web_search_empty_query() -> None:
    with pytest.raises(ValueError, match="query"):
        WebSearch(StaticBackend([])).run({"query": "  "})


def test_brave_http_error_short_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unauthorized"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def _client(**kwargs: object) -> httpx.Client:
        timeout = kwargs.get("timeout", 5.0)
        return real_client(transport=transport, timeout=timeout)  # type: ignore[arg-type]

    monkeypatch.setattr("harness.tools.search.brave.httpx.Client", _client)
    backend = BraveBackend(api_key="dummy")
    with pytest.raises(ValueError, match="Brave search failed: HTTP 401"):
        backend.search("q", max_results=3, timeout_sec=10.0)


def test_brave_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "web": {
            "results": [
                {"title": "T1", "url": "https://one.example", "description": "D1"},
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "q=hello" in str(request.url) or request.url.params.get("q") == "hello"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def _client(**kwargs: object) -> httpx.Client:
        timeout = kwargs.get("timeout", 5.0)
        return real_client(transport=transport, timeout=timeout)  # type: ignore[arg-type]

    monkeypatch.setattr("harness.tools.search.brave.httpx.Client", _client)
    backend = BraveBackend(api_key="k")
    hits = backend.search("hello", max_results=5, timeout_sec=10.0)
    assert len(hits) == 1
    assert hits[0].url == "https://one.example"
    assert hits[0].snippet == "D1"
