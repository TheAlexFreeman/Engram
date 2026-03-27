# Tool Registry

External tool definitions and policies.
Managed by `memory_register_tool`. Query with `memory_get_tool_policy`.

## shell

| Tool | Description | Approval | Cost | Timeout | Tags |
|---|---|---|---|---|---|
| pre-commit-run | Run pre-commit hooks on all files in the repository | no | free | 60s | lint, format, validate |
| pytest-run | Run the pytest test suite | no | free | 120s | test, validate |
| ruff-check | Run ruff linter and formatter checks on Python source files | no | free | 30s | lint, format |

