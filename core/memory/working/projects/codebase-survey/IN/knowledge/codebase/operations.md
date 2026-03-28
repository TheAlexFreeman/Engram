---
source: agent-generated
origin_session: manual
created: 2026-03-23
last_verified: 2026-03-26
trust: medium
related:
  - pyproject.toml
  - HUMANS/setup/setup.sh
  - HUMANS/tooling/scripts/validate_memory_repo.py
  - HUMANS/tooling/agent-memory-capabilities.toml
  - core/tools/tests
  - HUMANS/tooling/tests
  - HUMANS/tooling/tests-js
---

# Operations — Engram

## Local development

### Install

```bash
# Base (format layer only, zero deps):
pip install -e .

# With MCP server runtime:
pip install -e ".[server]"

# Full dev (includes ruff, pytest, pre-commit):
pip install -e ".[dev]"
```

Python ≥ 3.10 required. Git CLI must be available on PATH.

### Run the MCP server

```bash
engram-mcp                          # installed CLI
python -m engram_mcp.agent_memory_mcp.server_main  # module invocation
python core/tools/memory_mcp.py     # repo-local fallback (no install needed)
```

The server reads `MEMORY_REPO_ROOT` or falls back to file-relative detection. Set `MEMORY_ENABLE_RAW_WRITE_TOOLS=1` to enable Tier 2 tools.

### Post-clone setup (new users)

```bash
bash HUMANS/setup/setup.sh          # interactive; personalizes templates
bash setup.sh                       # top-level compatibility wrapper
```

Options: `--non-interactive`, `--remote <url>`, `--platform <name>`, `--profile <name>`, `--user-name`, `--user-context`. Profiles: software-developer, researcher, project-manager, writer, student, educator, designer. Platforms: codex, claude-code, cursor, chatgpt, generic.

Browser-based alternative: open `HUMANS/views/setup.html` in a browser.

### Worktree mode

For using Engram as a memory layer in an existing codebase, use `HUMANS/setup/init-worktree.sh`. Sets `host_repo_root` in `agent-bootstrap.toml`.

## Test and validation

### Python tests

```bash
pytest                              # runs both test directories
pytest HUMANS/tooling/tests/        # integration/validation tests
pytest core/tools/tests/            # MCP tool unit tests
```

Test paths configured in `pyproject.toml` under `[tool.pytest.ini_options]`.

**Core tool tests** (`core/tools/tests/`, 7 files):
- `test_memory_mcp.py` — MCP server and read tool tests
- `test_agent_memory_mcp_write_tools.py` — Tier 2 write tool tests
- `test_graph_tools.py` — Graph analysis tool tests
- `test_link_scoring.py`, `test_link_tools_engine.py` — Link scoring and reference extraction
- `test_surface_unlinked.py` — Unlinked file detection
- `test_core_boundary.py` — Core package import boundary tests

**Integration tests** (`HUMANS/tooling/tests/`, 8 files):
- `test_validate_memory_repo.py`, `test_validate_memory_repo_project_plans.py` — Repository structure validation
- `test_memory_capabilities.py` — Capabilities manifest validation
- `test_setup_flows.py` — Setup script flow tests
- `test_bootstrap_resolver.py` — Bootstrap manifest resolution
- `test_task_readiness.py` — Task readiness resolver
- `test_access_logging_batch.py` — Batch access logging
- `test_onboard_export.py` — Onboard export template

### JavaScript tests (`HUMANS/tooling/tests-js/`, 5 files)

Browser view unit tests: `engram-utils.test.js`, `dashboard-utils.test.js`, `setup-utils.test.js`, `graph.test.js`, `view-smoke.test.js`.

### Lint and type check

```bash
ruff check .                        # linting (configured in pyproject.toml)
ruff format --check .               # format check
```

Ruff config: `line-length = 100`, `target-version = "py310"`, selects E/F/W/I, ignores E501.

### Repository validation script

```bash
python HUMANS/tooling/scripts/validate_memory_repo.py
```

Checks: directory structure, frontmatter schema compliance, ACCESS.jsonl format, SUMMARY.md presence, link health, and cross-reference integrity.

### Other scripts

- `HUMANS/tooling/scripts/resolve_bootstrap_manifest.py` — resolves/validates the bootstrap TOML
- `HUMANS/tooling/scripts/resolve_memory_capabilities.py` — resolves the capabilities manifest
- `HUMANS/tooling/scripts/resolve_task_readiness.py` — evaluates task readiness against capability requirements
- `HUMANS/tooling/scripts/inspect_compact_budget.py` — audits compact-path token budget compliance
- `HUMANS/tooling/scripts/onboard-export.sh` — export tool for onboarding
- `extract_names.py` (repo root) — standalone NAMES.md generator
- `prune_links.py` (repo root) — standalone link pruning script

## Deployment and release

- No formal deployment pipeline — Engram is a personal memory repo, not a hosted service.
- Distribution: clone/fork the template repo, run `setup.sh`, start the MCP server.
- MCP client configuration: see `HUMANS/tooling/mcp-config-example.json` for a sample config.
- The `agent-memory-capabilities.toml` manifest declares contract versions (frontmatter v1, access v1, mcp v1, etc.).
- Versioned as `0.1.0` in `pyproject.toml`.

## Debugging and observability

- `memory_diff` (Tier 0) — shows working tree status (staged, unstaged, untracked).
- `memory_git_log` (Tier 0) — recent commit history.
- `memory_validate` (Tier 0) — structural and schema validation of the repo.
- `memory_session_health_check` (Tier 0) — ACCESS aggregation triggers, review queue status.
- `memory_audit_trust` (Tier 0) — trust decay audit across all memory files.
- `memory_scan_frontmatter_health` (Tier 0) — frontmatter and heading health scan.
- Git stderr is captured in `StagingError.stderr` when git operations fail.
- Write lock contention surfaces as a timeout after 5 seconds (`agent-memory-write.lock`).
- The `ENGRAM_MAX_FILE_SIZE` env var (default 512 KB) prevents runaway file growth.

## Open questions

_None at this time._
