#!/usr/bin/env bash
# install-worktree.sh — Bootstrap Engram as a worktree inside an existing repo.
#
# Designed to be curl-pipeable from the host repository root:
#
#   curl -fsSL https://raw.githubusercontent.com/TheAlexFreeman/Engram/main/install-worktree.sh \
#       | bash -s -- --platform claude-code --profile software-developer
#
# All arguments are forwarded verbatim to HUMANS/setup/init-worktree.sh.
# Run init-worktree.sh --help (or pass --help here) to see available options.
#
# What this script does:
#   1. Shallow-clones the Engram repo into a temp directory.
#   2. Delegates to HUMANS/setup/init-worktree.sh with your arguments.
#   3. Removes the temp clone on exit (success or failure).
#
# Requirements: git, bash, curl (or any caller that pipes this script).

set -euo pipefail

main() {
    ENGRAM_REPO="${ENGRAM_REPO:-https://github.com/TheAlexFreeman/Engram.git}"
    ENGRAM_BRANCH="${ENGRAM_BRANCH:-main}"

    # Create a temp dir and register cleanup.
    SEED_DIR="$(mktemp -d)"
    cleanup() {
        rm -rf "$SEED_DIR"
    }
    trap cleanup EXIT

    echo "[install-worktree] Fetching Engram seed from ${ENGRAM_REPO} (branch: ${ENGRAM_BRANCH}) ..."
    git clone --depth 1 --branch "$ENGRAM_BRANCH" --quiet "$ENGRAM_REPO" "$SEED_DIR" </dev/null

    echo "[install-worktree] Running init-worktree.sh ..."
    bash "$SEED_DIR/HUMANS/setup/init-worktree.sh" "$@"
}

main "$@"
