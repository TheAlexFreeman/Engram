# Engram

This repository is a persistent AI memory system. Start with `README.md` for the architectural contract, then continue to `core/INIT.md` for live routing and thresholds. When local agent-memory MCP tools are available, prefer them for memory reads, search, and governed writes; fall back to direct file access only when the MCP surface is unavailable or lacks the needed operation. Do not duplicate the full rule list here — `README.md` and `core/governance/` are the single source of truth.
