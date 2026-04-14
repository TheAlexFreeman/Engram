@echo off
setlocal

uv sync --group dev

call ".venv\Scripts\activate.bat"

REM Use `AGENTS.md` instead of `CLAUDE.md`.
REM Create a symlink only if `CLAUDE.md` doesn't already exist.
if not exist "CLAUDE.md" (
    mklink "CLAUDE.md" "AGENTS.md"
    if errorlevel 1 (
        echo Failed to create symlink. Try running in an elevated prompt.
    ) else (
        echo Created symlink: CLAUDE.md ^> AGENTS.md
    )
) else (
    echo Skipping symlink creation: CLAUDE.md already exists
)

echo(
echo Development environment setup complete!
echo Virtual environment activated. You can now run your Python scripts.
endlocal
