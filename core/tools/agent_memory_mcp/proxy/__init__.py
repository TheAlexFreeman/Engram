"""HTTP proxy core for the optional Engram session-management proxy."""

from .auto_checkpoint import (
    AutoCheckpointConfig,
    AutoCheckpointMonitor,
    AutoCheckpointResult,
    AutoCheckpointToolCaller,
    ResponseInspection,
    build_checkpoint_content,
    inspect_response_body,
)
from .compaction import (
    ApproximateTokenCounter,
    CompactionConfig,
    CompactionMonitor,
    CompactionResult,
    TiktokenTokenCounter,
    TokenCounter,
    build_default_token_counter,
    build_flush_summary,
)
from .formats import (
    APIFormat,
    ObservedToolCall,
    RequestInspection,
    adapter_for_format,
    detect_api_format,
)
from .injection import ContextInjectionResult, ContextInjector, InjectionConfig
from .server import ProxyConfig, ProxyLogEntry, ProxyObservation, ProxyServer

__all__ = [
    "APIFormat",
    "ApproximateTokenCounter",
    "AutoCheckpointConfig",
    "AutoCheckpointMonitor",
    "AutoCheckpointResult",
    "AutoCheckpointToolCaller",
    "ResponseInspection",
    "CompactionConfig",
    "CompactionMonitor",
    "CompactionResult",
    "ContextInjectionResult",
    "ContextInjector",
    "InjectionConfig",
    "ObservedToolCall",
    "ProxyConfig",
    "ProxyLogEntry",
    "ProxyObservation",
    "ProxyServer",
    "RequestInspection",
    "TokenCounter",
    "TiktokenTokenCounter",
    "adapter_for_format",
    "build_checkpoint_content",
    "build_default_token_counter",
    "build_flush_summary",
    "detect_api_format",
    "inspect_response_body",
]
