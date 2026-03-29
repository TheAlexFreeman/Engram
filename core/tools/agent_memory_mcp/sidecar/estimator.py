"""Heuristics for estimating ACCESS helpfulness from transcript text."""

from __future__ import annotations

import re

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "we",
        "with",
    }
)


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return {(tokens[index], tokens[index + 1]) for index in range(len(tokens) - 1)}


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def estimate_helpfulness(
    retrieved_content: str,
    response_text: str,
    task_description: str,
) -> float:
    """Estimate how much retrieved content influenced the final response.

    Scores intentionally avoid the 0.0-0.1 band because that range is
    reserved for files that should generally not have been logged at all.
    """

    retrieved_tokens = _tokenize(retrieved_content)
    response_tokens = _tokenize(response_text)
    task_tokens = _tokenize(task_description)

    if not retrieved_tokens:
        return 0.2

    retrieved_set = set(retrieved_tokens)
    response_set = set(response_tokens)
    task_set = set(task_tokens)

    response_overlap = retrieved_set & response_set
    task_overlap = retrieved_set & task_set
    coverage = _safe_ratio(len(response_overlap), len(response_set))
    retrieval_reuse = _safe_ratio(len(response_overlap), len(retrieved_set))
    task_alignment = _safe_ratio(len(task_overlap), len(task_set))

    bigram_overlap = len(_bigrams(retrieved_tokens) & _bigrams(response_tokens))

    if coverage >= 0.8 or bigram_overlap >= 2 or (coverage >= 0.45 and bigram_overlap >= 1):
        return 0.85
    if coverage >= 0.5 or retrieval_reuse >= 0.6 or bigram_overlap >= 1:
        return 0.75
    if coverage >= 0.18 or (response_overlap and task_alignment >= 0.2):
        return 0.55
    if task_alignment >= 0.2:
        return 0.35
    return 0.2
