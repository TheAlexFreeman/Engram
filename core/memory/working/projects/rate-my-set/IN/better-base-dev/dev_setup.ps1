$ErrorActionPreference = "Stop"

uv sync --group dev

$activatePath = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activatePath) {
    . $activatePath
} else {
    Write-Host "Virtual environment activation script not found at $activatePath" -ForegroundColor Yellow
}

# Use `AGENTS.md` instead of `CLAUDE.md`.
# Create a symlink only if `CLAUDE.md` doesn't already exist.
$claudePath = Join-Path $PSScriptRoot "CLAUDE.md"
$agentsPath = Join-Path $PSScriptRoot "AGENTS.md"
if (-not (Test-Path $claudePath)) {
    try {
        New-Item -ItemType SymbolicLink -Path $claudePath -Target $agentsPath | Out-Null
        Write-Host "Created symlink: CLAUDE.md -> AGENTS.md"
    } catch {
        Write-Host "Failed to create symlink (try running elevated): $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping symlink creation: CLAUDE.md already exists"
}

Write-Host ""
Write-Host "Development environment setup complete!"
Write-Host "Virtual environment activated. You can now run your Python scripts."
