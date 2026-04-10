<#
.SYNOPSIS
    Migrate the agent-memory MCP from a stale worktree/repo to a branch
    on the current Engram checkout.

.DESCRIPTION
    This script:
    1. Merges plan-state history from the old MCP repo into your working branch
    2. Removes the old worktree (or disconnects the old repo)
    3. Creates a new worktree on your current branch
    4. Updates MCP configs to point to the new worktree

.PARAMETER EngramRoot
    Path to your main Engram checkout. Default: C:\Users\Owner\code\personal\Engram

.PARAMETER OldMcpRoot
    Path to the old MCP repo/worktree. Default: C:\Users\Owner\code\personal\agent-memory-seed

.PARAMETER TargetBranch
    Branch the new worktree should track. Default: alex

.PARAMETER NewWorktreePath
    Where to create the new worktree. Default: <EngramRoot>\.engram

.EXAMPLE
    .\migrate-worktree-to-branch.ps1
    .\migrate-worktree-to-branch.ps1 -TargetBranch main
#>

param(
    [string]$EngramRoot = "C:\Users\Owner\code\personal\Engram",
    [string]$OldMcpRoot = "C:\Users\Owner\code\personal\agent-memory-seed",
    [string]$TargetBranch = "alex",
    [string]$NewWorktreePath = ""
)

$ErrorActionPreference = "Stop"

if (-not $NewWorktreePath) {
    $NewWorktreePath = Join-Path $EngramRoot ".engram"
}

Write-Host "`n=== Engram MCP Worktree Migration ===" -ForegroundColor Cyan
Write-Host "Engram root:      $EngramRoot"
Write-Host "Old MCP root:     $OldMcpRoot"
Write-Host "Target branch:    $TargetBranch"
Write-Host "New worktree:     $NewWorktreePath"
Write-Host ""

# -- Pre-flight checks ---------------------------------------------------

if (-not (Test-Path (Join-Path $EngramRoot ".git"))) {
    throw "Not a git repo: $EngramRoot"
}

Push-Location $EngramRoot
$branchExists = git branch --list $TargetBranch 2>&1
if (-not $branchExists) {
    throw "Branch '$TargetBranch' does not exist in $EngramRoot"
}
Pop-Location

# -- Step 0: Stop MCP server ---------------------------------------------

Write-Host "`n[!] IMPORTANT: Stop the MCP server before continuing." -ForegroundColor Yellow
Write-Host "    Close Claude Desktop, Cowork, or any client using agent-memory."
Write-Host ""
$confirm = Read-Host "Have you stopped the MCP server? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Aborting. Stop the MCP server first." -ForegroundColor Red
    exit 1
}

# -- Step 1: Check if old repo has commits to preserve --------------------

$hasOldCommits = $false
$oldBranch = ""
if (Test-Path (Join-Path $OldMcpRoot ".git")) {
    Write-Host "`n[1/5] Checking old MCP repo for commits to preserve..." -ForegroundColor Green
    Push-Location $OldMcpRoot
    $oldBranch = git rev-parse --abbrev-ref HEAD 2>&1
    $commitCount = git rev-list --count HEAD 2>&1
    Write-Host "  Old repo branch: $oldBranch ($commitCount commits)"
    Pop-Location
    $hasOldCommits = $true
}
else {
    Write-Host "`n[1/5] Old MCP root not found or not a repo -- skipping merge." -ForegroundColor Yellow
}

# -- Step 2: Merge old history into target branch -------------------------

if ($hasOldCommits) {
    Write-Host "`n[2/5] Merging old MCP history into $TargetBranch..." -ForegroundColor Green
    Push-Location $EngramRoot

    # Ensure we are on the target branch before merging
    Write-Host "  Checking out $TargetBranch..."
    git checkout $TargetBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n  Failed to checkout '$TargetBranch'. Ensure it exists and the working tree is clean." -ForegroundColor Red
        Pop-Location
        exit 1
    }

    # Add old repo as a temporary remote
    git remote add old-mcp $OldMcpRoot 2>$null
    git fetch old-mcp 2>&1 | Write-Host

    # Merge with --allow-unrelated-histories (orphan branch)
    Write-Host "  Merging old-mcp/$oldBranch into $TargetBranch..."
    $mergeResult = git merge "old-mcp/$oldBranch" --allow-unrelated-histories --no-edit 2>&1
    Write-Host $mergeResult

    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n  Merge conflict detected. Resolve manually, then re-run." -ForegroundColor Yellow
        Write-Host "  When done: git merge --continue && git remote remove old-mcp"
        Pop-Location
        exit 1
    }

    git remote remove old-mcp
    Write-Host "  Merge complete." -ForegroundColor Green
    Pop-Location
}
else {
    Write-Host "`n[2/5] No merge needed -- skipping." -ForegroundColor Yellow
}

# -- Step 3: Remove old worktree / leave old repo ------------------------

Write-Host "`n[3/5] Cleaning up old MCP location..." -ForegroundColor Green
Push-Location $EngramRoot

# Check if it's a linked worktree of this repo
$worktrees = git worktree list 2>&1
$isWorktree = $worktrees | Select-String ([regex]::Escape($OldMcpRoot))

if ($isWorktree) {
    Write-Host "  Removing linked worktree at $OldMcpRoot..."
    git worktree remove $OldMcpRoot --force
}
else {
    Write-Host "  $OldMcpRoot is a standalone repo (not a worktree of Engram)."
    Write-Host "  You can delete it manually once you've confirmed the merge:"
    Write-Host "    Remove-Item -Recurse -Force '$OldMcpRoot'" -ForegroundColor DarkGray
}
Pop-Location

# -- Step 4: Create new worktree on target branch ------------------------

Write-Host "`n[4/5] Creating new worktree at $NewWorktreePath on branch $TargetBranch..." -ForegroundColor Green
Push-Location $EngramRoot

if (Test-Path $NewWorktreePath) {
    Write-Host "  Path already exists. Removing stale worktree..." -ForegroundColor Yellow
    git worktree remove $NewWorktreePath --force 2>$null
    if (Test-Path $NewWorktreePath) {
        Remove-Item -Recurse -Force $NewWorktreePath
    }
}

git worktree add $NewWorktreePath $TargetBranch
Write-Host "  Worktree created." -ForegroundColor Green
Pop-Location

# -- Step 5: Update MCP configs ------------------------------------------

Write-Host "`n[5/5] Updating MCP configurations..." -ForegroundColor Green

$cursorConfig = Join-Path $EngramRoot ".cursor\mcp.json"
if (Test-Path $cursorConfig) {
    Write-Host "  .cursor/mcp.json -- AGENT_MEMORY_ROOT already uses workspaceFolder, OK."
}

$claudeConfig = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
Write-Host ""
Write-Host "  Update your Claude Desktop / Cowork MCP config at:" -ForegroundColor Yellow
Write-Host "    $claudeConfig"
Write-Host ""
Write-Host "  Set the agent-memory entry to:" -ForegroundColor Yellow
$escapedEngram = $EngramRoot -replace '\\', '/'
$escapedWorktree = $NewWorktreePath -replace '\\', '/'
Write-Host @"
    "agent-memory": {
      "command": "python",
      "args": ["$escapedEngram/core/tools/memory_mcp.py"],
      "env": {
        "MEMORY_REPO_ROOT": "$escapedWorktree",
        "MEMORY_REPO_IDENTITY": "Engram"
      }
    }
"@

# -- Done -----------------------------------------------------------------

Write-Host "`n=== Migration complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Update your Claude Desktop / Cowork MCP config (see above)"
Write-Host "  2. Restart the MCP client"
Write-Host "  3. Verify: git worktree list  (should show .engram on $TargetBranch)"
Write-Host "  4. Both 'git log' in Engram and the MCP now share the $TargetBranch branch"
Write-Host ""
