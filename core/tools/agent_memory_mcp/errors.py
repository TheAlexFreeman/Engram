"""
Error taxonomy for the agent-memory MCP.

All errors inherit from AgentMemoryError so callers can catch them broadly
or narrowly depending on their needs.
"""


class AgentMemoryError(Exception):
    """Base class for all agent-memory errors."""


class ConflictError(AgentMemoryError):
    """Version token mismatch — file was modified since it was read.

    Attributes:
        current_token: The current hash of the file, so the caller can
            decide whether to re-read and retry.
    """

    def __init__(self, message: str, current_token: str | None = None):
        super().__init__(message)
        self.current_token = current_token


class NotFoundError(AgentMemoryError):
    """File, section, or plan item does not exist."""


class ValidationError(AgentMemoryError):
    """Frontmatter schema violation, broken invariant, or malformed content."""


class DuplicateContentError(AgentMemoryError):
    """Content hash already exists in the staging registry.

    Attributes:
        content_hash: The SHA-256 digest for the duplicate content.
        existing_filename: The previously staged filename tied to this hash.
    """

    def __init__(
        self,
        message: str,
        *,
        content_hash: str = "",
        existing_filename: str = "",
    ):
        super().__init__(message)
        self.content_hash = content_hash
        self.existing_filename = existing_filename


class AlreadyDoneError(AgentMemoryError):
    """Idempotency: the operation is already in the target state.

    Distinct from success so callers can tell the difference between
    'I just did it' and 'it was already done'.
    """


class StagingError(AgentMemoryError):
    """git add/commit/mv/rm failed.

    Attributes:
        stderr: Raw stderr output from git for debugging.
    """

    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


class MemoryPermissionError(AgentMemoryError):
    """Operation is blocked by the directory restriction policy.

    Raised before any filesystem access when the target path is in a
    protected directory (memory/users/, governance/, memory/activity/, memory/skills/).
    Also raised when cowork file-delete permission cannot be obtained.

    Attributes:
        path: The path that triggered the restriction.
    """

    def __init__(self, message: str, path: str = ""):
        super().__init__(message)
        self.path = path
