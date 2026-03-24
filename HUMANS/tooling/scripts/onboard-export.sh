#!/usr/bin/env bash
set -euo pipefail

# Engram — Onboarding Export
# Imports a structured onboarding export file into the memory repo.
#
# Usage:
#   bash HUMANS/tooling/scripts/onboard-export.sh <export-file>
#   bash HUMANS/tooling/scripts/onboard-export.sh < export-file
#   <agent output> | bash HUMANS/tooling/scripts/onboard-export.sh
#
# The export file should follow the format in HUMANS/tooling/onboard-export-template.md,
# with top-level session metadata and four sections: "## Identity Profile",
# "## Session Transcript", "## Session Summary", and "## Session Reflection".

usage() {
    echo "Usage: onboard-export.sh [<export-file>]"
    echo ""
    echo "Imports an onboarding export into the memory repo."
    echo ""
    echo "The export file follows the template in HUMANS/tooling/onboard-export-template.md."
    echo "If no file is given, reads from stdin."
    echo ""
    echo "Options:"
    echo "  --dry-run    Show what would be written without making changes"
    echo "  -h, --help   Show this help message"
}

DRY_RUN=false
INPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "Unknown option: $1"; usage; exit 1 ;;
        *)
            if [[ -n "$INPUT_FILE" ]]; then
                echo "Error: multiple input files specified."
                usage; exit 1
            fi
            INPUT_FILE="$1"; shift ;;
    esac
done

# Validate we're in the right directory
if [[ ! -f "README.md" ]] || [[ ! -d "meta" ]]; then
    echo "Error: onboard-export.sh must be run from the root of the Engram repository."
    exit 1
fi

# Read input
if [[ -n "$INPUT_FILE" ]]; then
    if [[ ! -f "$INPUT_FILE" ]]; then
        echo "Error: file not found: $INPUT_FILE"
        exit 1
    fi
    INPUT=$(cat "$INPUT_FILE")
else
    if [[ -t 0 ]]; then
        echo "Error: no input file specified and stdin is a terminal."
        echo "Provide an export file as an argument, or pipe input via stdin."
        usage
        exit 1
    fi
    INPUT=$(cat)
fi

# --- Parse frontmatter + sections ---
# Canonical exports include top-level YAML frontmatter with session metadata.
# Legacy exports (pre-migration) omit that frontmatter and the transcript section.

FRONTMATTER=""
INPUT_BODY="$INPUT"
if printf '%s\n' "$INPUT" | awk 'NR==1 { exit($0 == "---" ? 0 : 1) }'; then
    FRONTMATTER=$(printf '%s\n' "$INPUT" | awk '
        NR == 1 && $0 == "---" { in_fm = 1; next }
        in_fm && $0 == "---" { exit }
        in_fm { print }
    ')
    INPUT_BODY=$(printf '%s\n' "$INPUT" | awk '
        BEGIN { body = 0 }
        NR == 1 && $0 == "---" { in_fm = 1; next }
        in_fm && $0 == "---" { in_fm = 0; body = 1; next }
        !in_fm { print }
    ')
fi

frontmatter_value() {
    local key="$1"
    printf '%s\n' "$FRONTMATTER" | awk -F': *' -v key="$key" '
        $1 == key {
            sub($1 ":[[:space:]]*", "")
            print
            exit
        }
    '
}

# Extract content between the known top-level sections, stripping HTML comments.
# The Identity Profile section may contain its own ## sub-headers (e.g., ## Role and context),
# so we split only on the four known section boundaries.

KNOWN_SECTIONS="^## Identity Profile$|^## Session Transcript$|^## Session Summary$|^## Session Reflection$"

extract_section() {
    local section_name="$1"
    local content="$2"
    # Get everything after "## $section_name" until the next known section or end of file.
    # Then strip HTML comments.
    echo "$content" \
        | awk -v sect="## ${section_name}" -v boundary="${KNOWN_SECTIONS}" '
            BEGIN { found=0 }
            $0 == sect { found=1; next }
            found && $0 ~ boundary { found=0 }
            found { print }
        ' \
        | sed '/^<!--/,/^-->$/d' \
        | sed 's/<!--.*-->//g'
}

IDENTITY_CONTENT=$(extract_section "Identity Profile" "$INPUT_BODY")
SESSION_TRANSCRIPT=$(extract_section "Session Transcript" "$INPUT_BODY")
SESSION_SUMMARY=$(extract_section "Session Summary" "$INPUT_BODY")
SESSION_REFLECTION=$(extract_section "Session Reflection" "$INPUT_BODY")

# Trim leading/trailing blank lines
trim() {
    echo "$1" | sed '/./,$!d' | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}'
}

IDENTITY_CONTENT=$(trim "$IDENTITY_CONTENT")
SESSION_TRANSCRIPT=$(trim "$SESSION_TRANSCRIPT")
SESSION_SUMMARY=$(trim "$SESSION_SUMMARY")
SESSION_REFLECTION=$(trim "$SESSION_REFLECTION")

SESSION_ID=$(trim "$(frontmatter_value "session_id")")
SESSION_DATE=$(trim "$(frontmatter_value "session_date")")
HAS_TRANSCRIPT_HEADER=false
if printf '%s\n' "$INPUT_BODY" | grep -q '^## Session Transcript$'; then
    HAS_TRANSCRIPT_HEADER=true
fi

LEGACY_EXPORT=false
if [[ -z "$SESSION_ID" ]] && [[ -z "$SESSION_DATE" ]] && [[ "$HAS_TRANSCRIPT_HEADER" == false ]]; then
    LEGACY_EXPORT=true
fi

# Validate we got something
if [[ -z "$IDENTITY_CONTENT" ]]; then
    echo "Error: No content found in '## Identity Profile' section."
    echo "Make sure the export file follows the template in HUMANS/tooling/onboard-export-template.md."
    exit 1
fi

if [[ "$LEGACY_EXPORT" == false ]]; then
    if [[ -z "$SESSION_ID" ]] || [[ -z "$SESSION_DATE" ]]; then
        echo "Error: Canonical onboarding exports must include session_id and session_date in top-level frontmatter."
        exit 1
    fi

    if [[ ! "$SESSION_ID" =~ ^core/memory/activity/[0-9]{4}/[0-9]{2}/[0-9]{2}/chat-[0-9]{3}$ ]]; then
        echo "Error: session_id must match core/memory/activity/YYYY/MM/DD/chat-NNN. Got: $SESSION_ID"
        exit 1
    fi

    if [[ ! "$SESSION_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        echo "Error: session_date must use YYYY-MM-DD. Got: $SESSION_DATE"
        exit 1
    fi

    SESSION_PATH_DATE=$(printf '%s\n' "$SESSION_ID" | sed -E 's#^core/memory/activity/([0-9]{4})/([0-9]{2})/([0-9]{2})/chat-[0-9]{3}$#\1-\2-\3#')
    if [[ "$SESSION_PATH_DATE" != "$SESSION_DATE" ]]; then
        echo "Error: session_date ($SESSION_DATE) must match the date encoded in session_id ($SESSION_ID)."
        exit 1
    fi

    if [[ "$HAS_TRANSCRIPT_HEADER" == false ]] || [[ -z "$SESSION_TRANSCRIPT" ]]; then
        echo "Error: Canonical onboarding exports must include a non-empty '## Session Transcript' section."
        exit 1
    fi

    if [[ -z "$SESSION_SUMMARY" ]]; then
        echo "Error: Canonical onboarding exports must include a non-empty '## Session Summary' section."
        exit 1
    fi
else
    echo "[warn] Legacy onboarding export detected — missing session metadata and transcript section."
    echo "       Falling back to today's date and core/memory/activity/YYYY/MM/DD/chat-001."
    if [[ -z "$SESSION_SUMMARY" ]]; then
        echo "[warn] No content found in '## Session Summary' section. Skipping chat record."
    fi
fi

# --- Prepare output ---
IMPORT_DATE=$(date +%Y-%m-%d)
if [[ "$LEGACY_EXPORT" == true ]]; then
    SESSION_DATE="$IMPORT_DATE"
    CHAT_DIR="core/memory/activity/$(date +%Y/%m/%d)/chat-001"
else
    CHAT_DIR="$SESSION_ID"
fi
CHAT_NAME="${CHAT_DIR##*/}"

echo "=== Onboarding Export ==="
echo ""

WRITTEN_PATHS=()

# 1. Write core/memory/users/profile.md
PROFILE_FILE="core/memory/users/profile.md"
PROFILE_CONTENT="---
source: user-stated
origin_session: ${CHAT_DIR}
created: ${SESSION_DATE}
last_verified: ${SESSION_DATE}
trust: high
---

${IDENTITY_CONTENT}"

echo "[plan] Write identity profile to: $PROFILE_FILE"

# 2. Write core/memory/users/SUMMARY.md
SUMMARY_CONTENT="# Identity Summary

User profile created via onboarding export on ${SESSION_DATE}.

See [profile.md](profile.md) for the full portrait."

echo "[plan] Update identity summary: core/memory/users/SUMMARY.md"

# 3. Write chat record (if session summary provided)
if [[ -n "$SESSION_SUMMARY" ]]; then
    echo "[plan] Create chat record: ${CHAT_DIR}/"

    CHAT_SUMMARY_CONTENT="# Session Summary — Onboarding

${SESSION_SUMMARY}"

    if [[ -n "$SESSION_TRANSCRIPT" ]]; then
        TRANSCRIPT_CONTENT="${SESSION_TRANSCRIPT}"
        echo "[plan] Write transcript: ${CHAT_DIR}/transcript.md"
    fi

    if [[ -n "$SESSION_REFLECTION" ]]; then
        REFLECTION_CONTENT="## Session reflection

${SESSION_REFLECTION}"
        echo "[plan] Write reflection: ${CHAT_DIR}/reflection.md"
    fi
fi

# 4. Update core/memory/activity/SUMMARY.md
# Only write when the file is absent or still holds the default placeholder.
# Real history is present when the file exists and does NOT contain the
# "*No conversations yet.*" sentinel that ships with the template repo.
chats_summary_has_history() {
    local f="core/memory/activity/SUMMARY.md"
    [[ -f "$f" ]] && ! grep -q '\*No conversations yet\.' "$f"
}

CHATS_SUMMARY_CONTENT="# Chats Summary

## Overall history

First recorded conversation on ${SESSION_DATE}: **${CHAT_NAME}** — onboarding and initial user profile creation."

if chats_summary_has_history; then
    echo "[plan] SKIP core/memory/activity/SUMMARY.md — existing history detected (would overwrite)"
else
    echo "[plan] Update chat summary: core/memory/activity/SUMMARY.md"
fi
echo ""

# --- Execute or dry-run ---
if [[ "$DRY_RUN" == true ]]; then
    echo "=== Dry run — no files written ==="
    echo ""
    echo "--- ${PROFILE_FILE} ---"
    echo "$PROFILE_CONTENT"
    echo ""
    echo "--- core/memory/users/SUMMARY.md ---"
    echo "$SUMMARY_CONTENT"
    if [[ -n "$SESSION_SUMMARY" ]]; then
        echo ""
        if [[ -n "$SESSION_TRANSCRIPT" ]]; then
            echo "--- ${CHAT_DIR}/transcript.md ---"
            echo "$TRANSCRIPT_CONTENT"
            echo ""
        fi
        echo "--- ${CHAT_DIR}/SUMMARY.md ---"
        echo "$CHAT_SUMMARY_CONTENT"
        if [[ -n "$SESSION_REFLECTION" ]]; then
            echo ""
            echo "--- ${CHAT_DIR}/reflection.md ---"
            echo "$REFLECTION_CONTENT"
        fi
    fi
    echo ""
    if chats_summary_has_history; then
        echo "--- core/memory/activity/SUMMARY.md ---"
        echo "[skip] Existing chat history detected — core/memory/activity/SUMMARY.md will NOT be overwritten."
        echo "       To update it, edit the file manually and add the new entry."
    else
        echo "--- core/memory/activity/SUMMARY.md ---"
        echo "$CHATS_SUMMARY_CONTENT"
    fi
    echo ""
    echo "Run without --dry-run to write these files."
    exit 0
fi

# Write identity profile
printf '%s\n' "$PROFILE_CONTENT" > "$PROFILE_FILE"
WRITTEN_PATHS+=("$PROFILE_FILE")
echo "[ok] Wrote $PROFILE_FILE"

# Write identity summary
printf '%s\n' "$SUMMARY_CONTENT" > "core/memory/users/SUMMARY.md"
WRITTEN_PATHS+=("core/memory/users/SUMMARY.md")
echo "[ok] Updated core/memory/users/SUMMARY.md"

# Write chat record
if [[ -n "$SESSION_SUMMARY" ]]; then
    mkdir -p "$CHAT_DIR"
    if [[ -n "$SESSION_TRANSCRIPT" ]]; then
        printf '%s\n' "$TRANSCRIPT_CONTENT" > "${CHAT_DIR}/transcript.md"
        WRITTEN_PATHS+=("${CHAT_DIR}/transcript.md")
        echo "[ok] Wrote ${CHAT_DIR}/transcript.md"
    fi

    printf '%s\n' "$CHAT_SUMMARY_CONTENT" > "${CHAT_DIR}/SUMMARY.md"
    WRITTEN_PATHS+=("${CHAT_DIR}/SUMMARY.md")
    echo "[ok] Wrote ${CHAT_DIR}/SUMMARY.md"

    if [[ -n "$SESSION_REFLECTION" ]]; then
        printf '%s\n' "$REFLECTION_CONTENT" > "${CHAT_DIR}/reflection.md"
        WRITTEN_PATHS+=("${CHAT_DIR}/reflection.md")
        echo "[ok] Wrote ${CHAT_DIR}/reflection.md"
    fi
fi

# Update core/memory/activity/SUMMARY.md — only when no real history exists yet
if chats_summary_has_history; then
    echo "[skip] core/memory/activity/SUMMARY.md already contains session history — not overwritten."
    echo "       Add the new entry manually:"
    echo "         First recorded conversation on ${SESSION_DATE}: **${CHAT_NAME}** — onboarding and initial user profile creation."
else
    printf '%s\n' "$CHATS_SUMMARY_CONTENT" > "core/memory/activity/SUMMARY.md"
    WRITTEN_PATHS+=("core/memory/activity/SUMMARY.md")
    echo "[ok] Updated core/memory/activity/SUMMARY.md"
fi

# Stage and commit
echo ""
git add -- "${WRITTEN_PATHS[@]}"
GIT_NAME=$(git config user.name 2>/dev/null || true)
GIT_EMAIL=$(git config user.email 2>/dev/null || true)
printf -v WRITTEN_PATH_ARGS '%q ' "${WRITTEN_PATHS[@]}"
WRITTEN_PATH_ARGS="${WRITTEN_PATH_ARGS% }"
if [[ -z "$GIT_NAME" ]] || [[ -z "$GIT_EMAIL" ]]; then
    echo "[warn] Git author identity not configured. Files are staged but not committed."
    echo "       Run: git commit --only -m '[system] Import onboarding profile' -- ${WRITTEN_PATH_ARGS}"
else
    git commit --only -m "[system] Import onboarding profile

Onboarding conducted on a read-only platform. Profile and session
record imported via onboard-export.sh on ${IMPORT_DATE}." -- "${WRITTEN_PATHS[@]}"
    echo "[ok] Committed onboarding import"
fi

echo ""
echo "=== Export complete ==="
echo ""
echo "Your identity profile is now in the repo. On your next AI session,"
echo "the agent will read it and greet you with what it knows."
