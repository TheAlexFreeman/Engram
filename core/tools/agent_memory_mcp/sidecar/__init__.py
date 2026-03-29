"""Shared sidecar interfaces and data models."""

from .access_logger import AccessLogger, AccessLoggingResult, build_access_entries
from .estimator import estimate_helpfulness
from .lifecycle import SessionLifecycleManager, SessionLifecycleResult
from .parser import ParsedSession, ToolCall, TranscriptFile, TranscriptParser
from .parsers import ClaudeCodeTranscriptParser

__all__ = [
    "AccessLogger",
    "AccessLoggingResult",
    "ClaudeCodeTranscriptParser",
    "ParsedSession",
    "SessionLifecycleManager",
    "SessionLifecycleResult",
    "ToolCall",
    "TranscriptFile",
    "TranscriptParser",
    "build_access_entries",
    "estimate_helpfulness",
]
