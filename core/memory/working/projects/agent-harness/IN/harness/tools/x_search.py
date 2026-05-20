from __future__ import annotations

from .search.tool import WebSearch
from .search.x import XSearchBackend


class XSearch(WebSearch):
    """Dedicated tool for searching X (formerly Twitter).

    Returns recent posts, threads, user activity, trends, and discussions.
    Results include titles (often usernames + post text), direct X URLs, and rich snippets.

    When using Grok (grok-4.20-reasoning etc.), the model also has access to xAI's
    native server-side x_search tool for even fresher real-time data and citations.

    Configuration:
    - Set BRAVE_API_KEY (used under the hood).
    - HARNESS_SEARCH_DISABLED=1 to disable.
    - Query can include X operators: from:username, @user, #hashtag, since:2025-01-01, etc.
    """

    name = "x_search"
    description = (
        "Search X (Twitter) for posts, threads, users, and real-time discussions. "
        "Excellent for current events, public sentiment, expert commentary, and breaking news. "
        "Returns ranked posts with direct links. Use for queries about what people are saying "
        "on X right now. Supports advanced operators (from:user, @user, #hashtag, since:YYYY-MM-DD, "
        "min_faves:N, min_replies:N, etc.). When using Grok models, native x_search is also available."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query. Can include X/Twitter advanced search operators.",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1–10). Default 5.",
            },
            "timeout_sec": {
                "type": "integer",
                "description": "HTTP timeout in seconds (5–60). Default 30.",
            },
        },
        "required": ["query"],
    }

    def __init__(self):
        # Use the specialized X backend instead of generic web search
        super().__init__(backend=XSearchBackend())
