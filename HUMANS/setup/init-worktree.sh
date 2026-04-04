#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SEED_REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
SEED_MANIFEST="$SCRIPT_DIR/init-worktree-paths.txt"

INTERACTIVE=true
DRY_RUN=false
PLATFORM=""
PROFILE=""
USER_NAME=""
USER_CONTEXT=""
WORKTREE_PATH=".agent-memory"
BRANCH_NAME="agent-memory"
TODAY="$(date +%Y-%m-%d)"

usage() {
    echo "Usage: init-worktree.sh [OPTIONS]"
    echo ""
    echo "Initialize a dedicated agent-memory orphan branch and worktree inside an existing git repository."
    echo ""
    echo "Options:"
    echo "  --worktree-path <path>  Worktree path relative to the host repo root (default: .agent-memory)"
    echo "  --branch-name <name>    Orphan branch name for the memory store (default: agent-memory)"
    echo "  --platform <name>       AI platform: codex, claude-code, cursor, chatgpt, generic"
    echo "  --profile <name>        Starter profile: software-developer, researcher, project-manager"
    echo "  --user-name <name>      Optional name for template-backed starter summaries"
    echo "  --user-context <text>   Optional AI-use context for template-backed starter summaries"
    echo "  --non-interactive       Skip prompts and use defaults"
    echo "  --dry-run               Print planned git commands without executing them"
    echo "  -h, --help              Show this help message"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --worktree-path)
            if [[ $# -lt 2 ]] || [[ -z "${2-}" ]]; then
                echo "Error: --worktree-path requires a path argument."
                usage
                exit 1
            fi
            WORKTREE_PATH="$2"
            shift 2
            ;;
        --branch-name)
            if [[ $# -lt 2 ]] || [[ -z "${2-}" ]]; then
                echo "Error: --branch-name requires a branch name."
                usage
                exit 1
            fi
            BRANCH_NAME="$2"
            shift 2
            ;;
        --platform)
            if [[ $# -lt 2 ]] || [[ -z "${2-}" ]]; then
                echo "Error: --platform requires a name argument."
                usage
                exit 1
            fi
            PLATFORM="$2"
            shift 2
            ;;
        --profile)
            if [[ $# -lt 2 ]] || [[ -z "${2-}" ]]; then
                echo "Error: --profile requires a name argument."
                usage
                exit 1
            fi
            PROFILE="$2"
            shift 2
            ;;
        --user-name)
            if [[ $# -lt 2 ]] || [[ -z "${2-}" ]]; then
                echo "Error: --user-name requires a value."
                usage
                exit 1
            fi
            USER_NAME="$2"
            shift 2
            ;;
        --user-context)
            if [[ $# -lt 2 ]] || [[ -z "${2-}" ]]; then
                echo "Error: --user-context requires a value."
                usage
                exit 1
            fi
            USER_CONTEXT="$2"
            shift 2
            ;;
        --non-interactive)
            INTERACTIVE=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            INTERACTIVE=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

validate_choice() {
    local value="$1"
    local label="$2"
    shift 2
    local valid
    for valid in "$@"; do
        if [[ "$value" == "$valid" ]]; then
            return 0
        fi
    done
    echo "Error: unknown $label '$value'. Valid options: $*"
    exit 1
}

if [[ -n "$PLATFORM" ]]; then
    validate_choice "$PLATFORM" "platform" codex claude-code cursor chatgpt generic
fi
if [[ -n "$PROFILE" ]]; then
    validate_choice "$PROFILE" "profile" software-developer researcher project-manager
fi

native_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$1"
    else
        printf '%s\n' "$1"
    fi
}

toml_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '%s\n' "$value"
}

json_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '%s\n' "$value"
}

sed_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//&/\\&}"
    value="${value//|/\\|}"
    printf '%s\n' "$value"
}

print_cmd() {
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
}

run_cmd() {
    print_cmd "$@"
    if [[ "$DRY_RUN" == false ]]; then
        "$@"
    fi
}

copy_seed_path() {
    local source_root="$1"
    local destination_root="$2"
    local relative_path="$3"
    local source_path="$source_root/$relative_path"
    local destination_path="$destination_root/$relative_path"

    mkdir -p "$(dirname "$destination_path")"
    if [[ -d "$source_path" ]]; then
        cp -R "$source_path" "$destination_path"
    else
        cp "$source_path" "$destination_path"
    fi
}

write_empty_file() {
    local target="$1"
    mkdir -p "$(dirname "$target")"
    : > "$target"
}

write_text_file() {
    local target="$1"
    shift
    mkdir -p "$(dirname "$target")"
    cat > "$target" <<EOF
$*
EOF
}

write_identity_summary() {
    local worktree_root="$1"
    local summary_path="$worktree_root/core/memory/users/SUMMARY.md"
    {
        echo "# Identity Summary"
        echo
        echo "Template-based profile — pending onboarding confirmation."
        echo
        echo "A starter profile has been installed from a template. During the first"
        echo "session, the onboarding skill will walk through the template traits and"
        echo "confirm, adjust, or remove them."
        echo
        echo "See [profile.md](profile.md) for the current profile."
        if [[ -n "$USER_NAME" ]]; then
            echo
            echo "**User:** $USER_NAME"
        fi
        if [[ -n "$USER_CONTEXT" ]]; then
            echo "**Uses AI for:** $USER_CONTEXT"
        fi
    } > "$summary_path"
}

render_template_file() {
    local template_path="$1"
    local destination_path="$2"
    local project_name="$3"
    local host_root_native="$4"
    local worktree_native="$5"
    local branch_name="$6"

    mkdir -p "$(dirname "$destination_path")"
    sed \
        -e "s|{{PROJECT_NAME}}|$(sed_escape "$project_name")|g" \
        -e "s|{{HOST_REPO_ROOT}}|$(sed_escape "$host_root_native")|g" \
        -e "s|{{MEMORY_WORKTREE_PATH}}|$(sed_escape "$worktree_native")|g" \
        -e "s|{{MEMORY_BRANCH}}|$(sed_escape "$branch_name")|g" \
        -e "s|{{TODAY}}|$(sed_escape "$TODAY")|g" \
        "$template_path" > "$destination_path"
}

ensure_codebase_context() {
    local profile_path="$1"
    local host_root_native="$2"
    local worktree_native="$3"
    local project_name="$4"
    local host_root_for_awk
    local worktree_for_awk

    host_root_for_awk="${host_root_native//\\/\\\\}"
    worktree_for_awk="${worktree_native//\\/\\\\}"

    if grep -q '<!-- CODEBASE_CONTEXT_START -->' "$profile_path"; then
        local temp_path
        temp_path="$(mktemp)"
        awk \
            -v project_name="$project_name" \
            -v host_root_native="$host_root_for_awk" \
            -v worktree_native="$worktree_for_awk" \
            '
                BEGIN { in_block = 0 }
                /<!-- CODEBASE_CONTEXT_START -->/ {
                    print
                    print "- **project_name:** " project_name
                    print "- **tech_stack:** _[To be filled during onboarding or the first survey session]_"
                    print "- **repo_url:** _[Optional - remote URL or canonical repo reference]_"
                    print "- **codebase_root:** " host_root_native
                    print "- **host_repo_root:** " host_root_native
                    print "- **memory_worktree_path:** " worktree_native
                    in_block = 1
                    next
                }
                /<!-- CODEBASE_CONTEXT_END -->/ {
                    in_block = 0
                    print
                    next
                }
                !in_block { print }
            ' "$profile_path" > "$temp_path"
        mv "$temp_path" "$profile_path"
        return
    fi

    cat >> "$profile_path" <<EOF

## Codebase context

- **project_name:** $project_name
- **tech_stack:** _[To be filled during onboarding or the first survey session]_
- **repo_url:** _[Optional - remote URL or canonical repo reference]_
- **codebase_root:** $host_root_native
- **host_repo_root:** $host_root_native
- **memory_worktree_path:** $worktree_native
EOF
}

install_profile() {
    local worktree_root="$1"
    local host_root_native="$2"
    local worktree_native="$3"
    local profile_name="$4"
    local project_name="$5"
    local destination="$worktree_root/core/memory/users/profile.md"

    if [[ -n "$profile_name" ]]; then
        local template_path="$SEED_REPO_ROOT/HUMANS/setup/templates/profiles/${profile_name}.md"
        if [[ ! -f "$template_path" ]]; then
            echo "Error: profile template not found: $template_path"
            exit 1
        fi
        sed "s/YYYY-MM-DD/$TODAY/g" "$template_path" > "$destination"
        write_identity_summary "$worktree_root"
    else
        write_text_file "$destination" "---
source: template
origin_session: setup
created: $TODAY
trust: medium
---

# User Profile

Worktree-backed memory store. Confirm or replace these defaults during onboarding."
        write_text_file "$worktree_root/core/memory/users/SUMMARY.md" "# Identity Summary

No confirmed identity summary yet.

Start onboarding from [profile.md](profile.md) in the memory worktree."
    fi

    ensure_codebase_context "$destination" "$host_root_native" "$worktree_native" "$project_name"
}

write_memory_stubs() {
    local worktree_root="$1"

    mkdir -p \
        "$worktree_root/core/memory/activity" \
        "$worktree_root/core/memory/users" \
        "$worktree_root/core/memory/knowledge/_unverified" \
        "$worktree_root/core/memory/working/projects/OUT" \
        "$worktree_root/core/memory/working/notes"

    write_empty_file "$worktree_root/core/memory/activity/ACCESS.jsonl"
    write_empty_file "$worktree_root/core/memory/users/ACCESS.jsonl"
    write_empty_file "$worktree_root/core/memory/knowledge/ACCESS.jsonl"
    write_empty_file "$worktree_root/core/memory/knowledge/_unverified/ACCESS.jsonl"
    write_empty_file "$worktree_root/core/memory/working/projects/ACCESS.jsonl"

    write_text_file "$worktree_root/core/memory/activity/SUMMARY.md" "# Activity Summary

_Nothing here yet._"
    write_text_file "$worktree_root/core/memory/knowledge/SUMMARY.md" "# Knowledge Summary

No codebase knowledge has been captured yet.

Add compact architecture notes here as the memory worktree learns the host project."
    write_text_file "$worktree_root/core/memory/knowledge/_unverified/SUMMARY.md" "# Unverified Knowledge Summary

Use this area for external research and unverified notes until they are reviewed."
    write_text_file "$worktree_root/core/memory/working/projects/SUMMARY.md" "---
type: projects-navigator
generated: $TODAY 12:00
project_count: 0
---

# Projects

_No active or ongoing projects._"
    write_text_file "$worktree_root/core/memory/working/projects/OUT/SUMMARY.md" "# Project Outbox

_No shipped artifacts yet._"
    write_text_file "$worktree_root/core/memory/working/CURRENT.md" "# Agent working notes

Provisional, agent-authored. Not formal memory.

See \`core/governance/scratchpad-guidelines.md\` for the full write protocol.

---

## Active threads

- **Codebase survey** — Active project. Begin with the entry-point-mapping phase after onboarding completes. See \`core/memory/working/projects/codebase-survey/plans/survey-plan.yaml\`.

## Immediate next actions

- Complete onboarding (first session), then begin entry-point-mapping phase of the codebase survey (second session).

## Open questions

_None_

## Drill-down refs

- \`core/memory/working/projects/SUMMARY.md\` for the project navigator.
- \`core/memory/working/projects/codebase-survey/plans/survey-plan.yaml\` for the survey plan."
    write_text_file "$worktree_root/core/memory/working/USER.md" "# User Scratchpad

User-authored constraints and reminders for this codebase belong here."
}

write_worktree_hygiene_files() {
    local worktree_root="$1"

    write_text_file "$worktree_root/.ignore" "# Hide memory-content folders from host-repo search tools by default.
# When working inside the memory worktree directly, use rg --no-ignore (or the
# equivalent in your editor) if you need to search these folders intentionally.
core/memory/activity/
core/memory/users/
core/memory/knowledge/
core/governance/
core/memory/working/projects/
core/memory/working/notes/
core/memory/skills/"

    write_text_file "$worktree_root/.editorconfig" "root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = false

[*.md]
indent_style = space
indent_size = 2

[*.jsonl]
indent_style = space
indent_size = 2"
}

write_codebase_starters() {
    local worktree_root="$1"
    local host_root_native="$2"
    local worktree_native="$3"
    local branch_name="$4"
    local project_name="$5"
    local template_root="$SEED_REPO_ROOT/HUMANS/setup/templates"
    local template_path

    render_template_file \
        "$template_root/codebase-survey-plan.yaml" \
        "$worktree_root/core/memory/working/projects/codebase-survey/plans/survey-plan.yaml" \
        "$project_name" \
        "$host_root_native" \
        "$worktree_native" \
        "$branch_name"

    mkdir -p \
        "$worktree_root/core/memory/working/projects/codebase-survey/IN" \
        "$worktree_root/core/memory/working/projects/codebase-survey/plans"

    write_text_file "$worktree_root/core/memory/working/projects/codebase-survey/SUMMARY.md" "---
source: template
origin_session: setup
created: $TODAY
trust: medium
type: project
status: active
cognitive_mode: exploration
open_questions: 5
active_plans: 1
last_activity: $TODAY
current_focus: \"Capture the architecture, interfaces, operations, and design rationale for $project_name.\"
---

# Project: Codebase Survey

## Description
Build a durable, codebase-specific map of $project_name so future sessions can orient quickly without re-reading the whole host repository.

## Cognitive mode
Exploration mode fits the initial survey: the goal is to discover stable structure, capture it compactly, and turn low-trust stubs into verified knowledge.

## Artifact flow
- IN/: temporary exploration notes, rough subsystem maps, and open questions that are not ready for durable promotion
- OUT contributions: verified core/memory/knowledge/codebase notes and any reusable operational guidance derived from the host repo

## Notes
Start from \
\`plans/survey-plan.yaml\` and replace the template stubs under \
\`core/memory/knowledge/codebase/\` one by one."

    write_text_file "$worktree_root/core/memory/working/projects/codebase-survey/questions.md" "---
source: template
origin_session: setup
created: $TODAY
trust: medium
type: questions
next_question_id: 6
---

# Open Questions

1. What are the main entry points for this application? \`[entry-point-mapping]\`
2. What build, test, and run commands does this project use? \`[operations-and-delivery]\`
3. What is the primary tech stack (language, framework, database)? \`[subsystem-survey]\`
4. Are there existing architecture docs, ADRs, or CONTRIBUTING guides? \`[decisions-and-history]\`
5. What are the main deployment targets and CI pipelines? \`[operations-and-delivery]\`

---

# Resolved Questions

_None yet._"

    for template_path in "$template_root"/knowledge/codebase/*.md; do
        render_template_file \
            "$template_path" \
            "$worktree_root/core/memory/knowledge/codebase/$(basename "$template_path")" \
            "$project_name" \
            "$host_root_native" \
            "$worktree_native" \
            "$branch_name"
    done

    write_text_file "$worktree_root/core/memory/knowledge/SUMMARY.md" "# Knowledge Summary

Starter codebase notes for $project_name live under [codebase/SUMMARY.md](codebase/SUMMARY.md).

Begin with [codebase/architecture.md](codebase/architecture.md), then fill the
data model, operations, and design-rationale stubs as the survey plan advances.

## Included knowledge bases

- [software-engineering/SUMMARY.md](software-engineering/SUMMARY.md) — Django, React, DevOps, testing, AI engineering, web fundamentals"

    write_text_file "$worktree_root/core/memory/working/projects/SUMMARY.md" "---
type: projects-navigator
generated: $TODAY 12:00
project_count: 1
---

# Projects

| Project | Status | Mode | Open Qs | Focus | Last activity |
|---|---|---|---|---|---|
| codebase-survey | active | exploration | 5 | Capture the architecture, interfaces, operations, and design rationale for $project_name. | $TODAY |"
}

update_bootstrap_file() {
    local bootstrap_path="$1"
    local host_root_native="$2"
    local host_root_toml
    local temp_path
    local normalized_path

    host_root_toml="${host_root_native//\\//}"

    if grep -q '^host_repo_root = ' "$bootstrap_path"; then
        return 0
    fi

    temp_path="$(mktemp)"
    awk \
        -v host_root_toml="$(toml_escape "$host_root_toml")" \
        '
            BEGIN { inserted = 0 }
            /^adapter_files = / && !inserted {
                print
                print "host_repo_root = \"" host_root_toml "\""
                inserted = 1
                next
            }
            { print }
            END {
                if (!inserted) {
                    print "host_repo_root = \"" host_root_toml "\""
                }
            }
        ' "$bootstrap_path" > "$temp_path"
    mv "$temp_path" "$bootstrap_path"

    temp_path="$(mktemp)"
    awk '
        function flush_block() {
            if (!in_step_block) {
                return
            }
            if (!drop_block) {
                printf "%s", block
            }
            block = ""
            drop_block = 0
            in_step_block = 0
        }

        BEGIN {
            block = ""
            drop_block = 0
            in_step_block = 0
        }

        /^\[\[modes\.(full_bootstrap|periodic_review)\.steps\]\]$/ {
            flush_block()
            in_step_block = 1
            block = $0 ORS
            next
        }

        in_step_block {
            if ($0 ~ /^\[\[/ || $0 ~ /^\[/) {
                flush_block()
                print
                next
            }

            block = block $0 ORS
            if ($0 == "path = \"CHANGELOG.md\"") {
                drop_block = 1
            }
            next
        }

        {
            print
        }

        END {
            flush_block()
        }
    ' "$bootstrap_path" > "$temp_path"
    mv "$temp_path" "$bootstrap_path"
}

write_host_codex_config() {
    local host_root="$1"
    local rel_command="$2"
    local rel_arg="$3"
    local worktree_rel="$4"
    local escaped_command
    local escaped_worktree

    escaped_command="$(toml_escape "$rel_command")"
    escaped_worktree="$(toml_escape "$worktree_rel")"

    mkdir -p "$host_root/.codex"
    cat > "$host_root/.codex/config.toml" <<EOF
# Paths are relative to the host repository root.
[mcp_servers.agent_memory]
command = "$escaped_command"
args = [$(if [[ -n "$rel_arg" ]]; then printf '"%s"' "$(toml_escape "$rel_arg")"; fi)]
cwd = "$escaped_worktree"
startup_timeout_sec = 20
tool_timeout_sec = 120
required = false

[mcp_servers.agent_memory.env]
MEMORY_REPO_ROOT = "$escaped_worktree"
HOST_REPO_ROOT = "."
EOF
}

write_host_mcp_example() {
    local host_root="$1"
    local rel_command="$2"
    local rel_arg="$3"
    local worktree_rel="$4"

    cat > "$host_root/mcp-config-example.json" <<EOF
{
  "_comment": "Copy this MCP server entry into your client configuration. Paths are relative to the host repository root.",
  "agent_memory": {
    "command": "$(json_escape "$rel_command")",
    "args": [$(if [[ -n "$rel_arg" ]]; then printf '"%s"' "$(json_escape "$rel_arg")"; fi)],
    "cwd": "$(json_escape "$worktree_rel")",
    "env": {
      "MEMORY_REPO_ROOT": "$(json_escape "$worktree_rel")",
      "HOST_REPO_ROOT": "."
    }
  }
}
EOF
}

write_host_adapter_files() {
    local host_root="$1"
    local worktree_path_display="$2"
    local branch_name="$3"
    local config_hint="$4"
    local quick_reference_path="$worktree_path_display/core/INIT.md"

    cat > "$host_root/AGENTS.md" <<EOF
# Engram

This project uses a dedicated Engram worktree.

- Memory worktree: \
  \
  $worktree_path_display
- Memory branch: $branch_name
- Session router: $quick_reference_path
- MCP config: $config_hint

At the start of every session, route startup through \
`$quick_reference_path` instead of assuming the host repo root is the memory store.
Use the host repository for application code operations and the memory worktree for
memory reads, writes, and governance files.
EOF

    cat > "$host_root/CLAUDE.md" <<EOF
# Engram

This host repository keeps its persistent memory in a separate worktree.

- Memory worktree: $worktree_path_display
- Memory branch: $branch_name
- Session router: $quick_reference_path
- MCP config: $config_hint

Start each session from `$quick_reference_path`. Use the host repository for product
code work, and use the memory worktree for user profiles, knowledge, projects,
activity, scratchpad, skills, and governance.
EOF

    cat > "$host_root/.cursorrules" <<EOF
This host repository uses a dedicated memory worktree at $worktree_path_display on
branch $branch_name. Start every session from $quick_reference_path, use $config_hint
for MCP wiring, operate on host-repo code from the project root, and keep memory
operations inside the worktree.
EOF
}

detect_python_for_worktree() {
    local worktree_root="$1"
    local candidate=""
    for candidate in "$worktree_root/.venv/Scripts/python.exe" "$worktree_root/.venv/bin/python"; do
        if [[ -x "$candidate" ]]; then
            native_path "$candidate"
            return 0
        fi
    done
    if command -v python3 >/dev/null 2>&1; then
        native_path "$(command -v python3)"
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        native_path "$(command -v python)"
        return 0
    fi
    return 1
}

detect_engram_mcp_for_worktree() {
    local worktree_root="$1"
    local candidate=""
    for candidate in \
        "$worktree_root/.venv/Scripts/engram-mcp.exe" \
        "$worktree_root/.venv/Scripts/engram-mcp.cmd" \
        "$worktree_root/.venv/Scripts/engram-mcp.bat" \
        "$worktree_root/.venv/bin/engram-mcp"; do
        if [[ -f "$candidate" ]]; then
            native_path "$candidate"
            return 0
        fi
    done
    if command -v engram-mcp >/dev/null 2>&1; then
        native_path "$(command -v engram-mcp)"
        return 0
    fi
    return 1
}


SERVER_COMMAND=""
SERVER_ARG=""
SERVER_MODE=""
REL_SERVER_COMMAND=""
REL_SERVER_ARG=""

resolve_server_launcher() {
    local worktree_root="$1"
    local memory_script_native

    if SERVER_COMMAND="$(detect_engram_mcp_for_worktree "$worktree_root")"; then
        SERVER_ARG=""
        SERVER_MODE="cli"
        return 0
    fi

    if SERVER_COMMAND="$(detect_python_for_worktree "$worktree_root")"; then
        memory_script_native="$(native_path "$worktree_root/core/tools/memory_mcp.py")"
        SERVER_ARG="$memory_script_native"
        SERVER_MODE="python"
        return 0
    fi

    SERVER_COMMAND="python"
    SERVER_ARG="$(native_path "$worktree_root/core/tools/memory_mcp.py")"
    SERVER_MODE="fallback"
    return 1
}

resolve_relative_server_paths() {
    local worktree_rel="$1"
    local worktree_abs="$2"

    case "$SERVER_MODE" in
        cli)
            # engram-mcp found in worktree venv
            for suffix in ".venv/Scripts/engram-mcp.exe" ".venv/Scripts/engram-mcp.cmd" \
                          ".venv/Scripts/engram-mcp.bat" ".venv/bin/engram-mcp"; do
                if [[ -f "$worktree_abs/$suffix" ]]; then
                    REL_SERVER_COMMAND="$worktree_rel/$suffix"
                    REL_SERVER_ARG=""
                    return 0
                fi
            done
            # engram-mcp is a global command; keep bare name
            REL_SERVER_COMMAND="engram-mcp"
            REL_SERVER_ARG=""
            ;;
        python)
            # Python from worktree venv
            for suffix in ".venv/Scripts/python.exe" ".venv/bin/python"; do
                if [[ -x "$worktree_abs/$suffix" ]]; then
                    REL_SERVER_COMMAND="$worktree_rel/$suffix"
                    REL_SERVER_ARG="$worktree_rel/core/tools/memory_mcp.py"
                    return 0
                fi
            done
            # System python; use bare command name
            REL_SERVER_COMMAND="${SERVER_COMMAND##*/}"
            REL_SERVER_ARG="$worktree_rel/core/tools/memory_mcp.py"
            ;;
        fallback)
            REL_SERVER_COMMAND="python"
            REL_SERVER_ARG="$worktree_rel/core/tools/memory_mcp.py"
            ;;
    esac
}

HOST_REPO_ROOT="$(pwd -P)"
HOST_TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$HOST_TOPLEVEL" ]]; then
    echo "Error: init-worktree.sh must be run from the root of an existing git repository."
    exit 1
fi
HOST_TOPLEVEL="$(cd -- "$HOST_TOPLEVEL" && pwd -P)"
if [[ "$HOST_TOPLEVEL" != "$HOST_REPO_ROOT" ]]; then
    echo "Error: init-worktree.sh must be run from the host repository root."
    echo "       Expected: $HOST_TOPLEVEL"
    echo "       Current:  $HOST_REPO_ROOT"
    exit 1
fi
if [[ ! -f "$SEED_MANIFEST" ]]; then
    echo "Error: missing worktree seed manifest: $SEED_MANIFEST"
    exit 1
fi

if [[ "$INTERACTIVE" == true ]]; then
    if [[ -z "$PROFILE" ]]; then
        echo ""
        echo "Starter profile (optional): software-developer, researcher, project-manager"
        read -rp "Profile [leave blank for default stub]: " PROFILE
        if [[ -n "$PROFILE" ]]; then
            validate_choice "$PROFILE" "profile" software-developer researcher project-manager
        fi
    fi
    if [[ -z "$PLATFORM" ]]; then
        echo ""
        echo "AI platform (optional): codex, claude-code, cursor, chatgpt, generic"
        read -rp "Platform [leave blank for generic example]: " PLATFORM
        if [[ -n "$PLATFORM" ]]; then
            validate_choice "$PLATFORM" "platform" codex claude-code cursor chatgpt generic
        fi
    fi
fi

resolve_under_host_root() {
    local path="$1"
    if [[ "$path" =~ ^[A-Za-z]:[\\/] ]] || [[ "$path" == /* ]]; then
        printf '%s\n' "$path"
    else
        printf '%s\n' "$HOST_REPO_ROOT/$path"
    fi
}

WORKTREE_ABS="$(resolve_under_host_root "$WORKTREE_PATH")"
WORKTREE_NATIVE="$(native_path "$WORKTREE_ABS")"
HOST_ROOT_NATIVE="$(native_path "$HOST_REPO_ROOT")"
PROJECT_NAME="$(basename "$HOST_REPO_ROOT")"
CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || git rev-parse --short HEAD)"
TEMP_WORKTREE="$HOST_REPO_ROOT/.git/engram-tmp-$BRANCH_NAME"
WORKTREE_DISPLAY="$WORKTREE_PATH"

if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    echo "Error: branch '$BRANCH_NAME' already exists in the host repository."
    exit 1
fi
if [[ -e "$WORKTREE_ABS" ]]; then
    echo "Error: worktree path already exists: $WORKTREE_ABS"
    exit 1
fi

if [[ "$DRY_RUN" == true ]]; then
    echo "=== Dry run: init worktree ==="
    print_cmd git worktree add --detach "$TEMP_WORKTREE" HEAD
    print_cmd git -C "$TEMP_WORKTREE" checkout --orphan "$BRANCH_NAME"
    print_cmd git -C "$TEMP_WORKTREE" rm -rf --ignore-unmatch .
    print_cmd git -C "$TEMP_WORKTREE" add --all
    print_cmd git -C "$TEMP_WORKTREE" commit --no-verify -m "[system] Initialize Engram worktree" -m "Seeded from Engram on $TODAY."
    print_cmd git worktree remove "$TEMP_WORKTREE"
    print_cmd git worktree add "$WORKTREE_ABS" "$BRANCH_NAME"
    echo "[dry-run] Worktree initialization commands printed only; no files or git state changed."
    exit 0
fi

cleanup_temp_worktree() {
    if [[ -d "$TEMP_WORKTREE" ]]; then
        git worktree remove --force "$TEMP_WORKTREE" >/dev/null 2>&1 || true
    fi
}
trap cleanup_temp_worktree EXIT

echo "=== Engram Worktree Setup ==="
echo ""

run_cmd git worktree add --detach "$TEMP_WORKTREE" HEAD
run_cmd git -C "$TEMP_WORKTREE" checkout --orphan "$BRANCH_NAME"
run_cmd git -C "$TEMP_WORKTREE" rm -rf --ignore-unmatch .

while IFS= read -r relative_path || [[ -n "$relative_path" ]]; do
    relative_path="${relative_path%$'\r'}"
    if [[ -z "$relative_path" ]] || [[ "$relative_path" == \#* ]]; then
        continue
    fi
    copy_seed_path "$SEED_REPO_ROOT" "$TEMP_WORKTREE" "$relative_path"
done < "$SEED_MANIFEST"

write_memory_stubs "$TEMP_WORKTREE"
install_profile "$TEMP_WORKTREE" "$HOST_ROOT_NATIVE" "$WORKTREE_NATIVE" "$PROFILE" "$PROJECT_NAME"
update_bootstrap_file "$TEMP_WORKTREE/agent-bootstrap.toml" "$HOST_ROOT_NATIVE"
write_worktree_hygiene_files "$TEMP_WORKTREE"
write_codebase_starters "$TEMP_WORKTREE" "$HOST_ROOT_NATIVE" "$WORKTREE_NATIVE" "$BRANCH_NAME" "$PROJECT_NAME"

run_cmd git -C "$TEMP_WORKTREE" add --all
run_cmd git -C "$TEMP_WORKTREE" commit --no-verify -m "[system] Initialize Engram worktree" -m "Seeded from Engram on $TODAY."
run_cmd git worktree remove "$TEMP_WORKTREE"
run_cmd git worktree add "$WORKTREE_ABS" "$BRANCH_NAME"

resolve_server_launcher "$WORKTREE_ABS" || true
resolve_relative_server_paths "$WORKTREE_DISPLAY" "$WORKTREE_ABS"

case "${PLATFORM:-generic}" in
    codex)
        if [[ "$SERVER_MODE" != "fallback" ]]; then
            write_host_codex_config "$HOST_REPO_ROOT" "$REL_SERVER_COMMAND" "$REL_SERVER_ARG" "$WORKTREE_DISPLAY"
            write_host_adapter_files "$HOST_REPO_ROOT" "$WORKTREE_DISPLAY" "$BRANCH_NAME" ".codex/config.toml"
            echo "[ok] Wrote host Codex MCP config to .codex/config.toml"
        else
            echo "[warn] Could not detect a Python interpreter for Codex MCP config"
        fi
        ;;
    *)
        write_host_mcp_example "$HOST_REPO_ROOT" "$REL_SERVER_COMMAND" "$REL_SERVER_ARG" "$WORKTREE_DISPLAY"
        write_host_adapter_files "$HOST_REPO_ROOT" "$WORKTREE_DISPLAY" "$BRANCH_NAME" "mcp-config-example.json"
        echo "[ok] Wrote host MCP example config to mcp-config-example.json"
        ;;
esac

trap - EXIT

echo ""
echo "=== Worktree setup complete ==="
echo ""
echo "Host branch:        $CURRENT_BRANCH"
echo "Memory branch:      $BRANCH_NAME"
echo "Memory worktree:    $WORKTREE_ABS"
echo "Host repo root:     $HOST_REPO_ROOT"
echo ""
echo "Next steps:"
echo "  1. Open the host repository in your agent client."
if [[ "${PLATFORM:-generic}" == "codex" ]]; then
    echo "  2. Ensure .codex/config.toml is trusted so the MCP server loads from the worktree."
else
    echo "  2. Copy mcp-config-example.json into your client-specific MCP configuration."
fi
echo "  3. Start the first codebase-survey or maintenance session against the host repo."
