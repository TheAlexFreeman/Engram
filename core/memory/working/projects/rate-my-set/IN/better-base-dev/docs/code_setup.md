# Code Setup

- Make sure [taskfile.dev](https://taskfile.dev) is installed
  - Once installed, make sure it's accessible on your path or similar.
  - ☝️ You'll know it's installed if typing `task` and hitting enter in your terminal shows something like:
    ```
    λ task
        task: No tasks with description available. Try --list-all to list all tasks
        task: Task "default" does not exist
    ```
- Make sure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed
  - ☝️ You'll know it's installed if typing `docker -v` and hitting enter in your terminal shows something like:
    ```
    λ docker -v
    Docker version 26.1.1, build 4cf5afa
    ```
  - Similarly, typing `docker compose ls` should show something like:
    ```
    λ docker compose ls
    NAME                STATUS              CONFIG FILES
    ... (if you have anything running stuff that would show here)
    ```
- Make sure [uv](https://docs.astral.sh/uv/) is installed
  - ☝️ You'll know it's installed if typing `uv --version` and hitting enter in your terminal shows something like:
    ```
    λ uv --version
    uv 0.5.7 (3ca155ddd 2024-12-06)
    ```
- Make sure [bun](https://bun.sh/) is installed
  - ☝️ You'll know it's installed if typing `bun --version` and hitting enter in your terminal shows something like:
    ```
    λ bun --version
    1.1.38
    ```
- Populate Environment Files
  1. Option 1 (All Steps at Once, Less Inspection/Instruction)
      ```
      cat .envs/.dev/.secrets.template.env >> .envs/.dev/.secrets.env
      cat .envs/.dev/.specific.template.env >> .envs/.dev/.specific.env
      touch .env
      cat .env.local.template >> .env.local
      cat .local.template.env >> .local.env
      cat .taskfile.template.env >> .taskfile.env
      ```
  2. Option 2 (Step by Step, More Inspection/Instruction)
      - Populate `.envs/.dev/.secrets.env`
        - An easy way to do this is to run:
          - `cat .envs/.dev/.secrets.template.env >> .envs/.dev/.secrets.env`
        - From there, you can change any values as you see fit.
      - Populate `.envs/.dev/.specific.env`
        - An easy way to do this is to run:
          - `cat .envs/.dev/.specific.template.env >> .envs/.dev/.specific.env`
        - From there, you can set any values as you see fit.
      - Populate `.env` (even if it's empty (at the time of writing))
        - An easy way to do this is to run:
          - `touch .env`
        - From there, you can change any values as you see fit.
      - Populate `.env.local` (this is for backend specific local overrides)
        - An easy way to do this is to run:
          - `cat .env.local.template >> .env.local`
        - From there, you can change any values as you see fit.
      - Populate `.local.env` (this is for backend specific local overrides)
        - An easy way to do this is to run:
          - `cat .local.template.env >> .local.env`
        - From there, you can change any values as you see fit.
      - Populate `.taskfile.env`
        - An easy way to do this is to run:
          - `cat .taskfile.template.env >> .taskfile.env`
        - From there, you can change any values as you see fit.
- (Optional) Set up agent skills and MCP support for AI assistants (Claude Code, Codex,
  Cursor, OpenCode, etc.)
  - Install the dotagents-managed config:
    ```
    bunx dotagents install
    ```
  - This generates the shared agent/MCP configuration from `agents.toml`.
  - If agent config or symlink state drifts, run `bunx dotagents sync`.
  - Under dotagents v1, `agents.lock` is local managed state and should stay
    untracked.
  - TanStack docs are now expected through the TanStack CLI (`bunx @tanstack/cli ...`)
    rather than a TanStack MCP server.
  - See `AGENTS.md` for more details on available MCP servers and agent guidance.
- `task build`
  - Depending on your computer speed and internet connection, this can take anywhere from a minute to several minutes.
- Run `uv sync`
- Activate your virtual environment:
  - (On Linux/Mac) - `source .venv/bin/activate`
  - (On Windows) - `.venv\Scripts\activate.bat`
- `task back` (Get the backing services running)
- `python manage.py makemigrations` (Make sure this doesn't generate anything and/or if it does and it's expected, good!)
- `python manage.py migrate` (Make sure this succeeds)
- `bun install`
- Install all the recommended extensions plus any desired extensions for VS Code
  - If you open the extensions panel in VS Code, typing `@recommended` into the search bar should make the "Workspace Recommendations" appear. Those are the ones I typically use and recommend with this codebase.
- Set the virtual environment (associate it) in VS Code
- Set rewrap max width to `88` in VS Code
- Set the Vim `gq` max width to `88` in VS Code
- Make sure Pylance is the VS Code language server (make sure configured that way)
- Make sure `pytest` is enabled and the main testing framework for VS Code
- Make sure `ruff` is enabled and the main formatting provider for Python in VS Code
- `task tcovdb` (Make sure this works - Running `pytest` with a fresh DB with coverage)
- `task mp` (Make sure this works - Running `mypy`)
- `python manage.py runserver 8020` (Make sure this works)
- `bun dev` (Make sure this works. Also make sure that `python manage.py runserver 8020` is running at the same time in a separate terminal)
- `bun run build` (Make sure this works)
- Practice and/or double check that you have `bun dev` running, change a relevant `.css` or `.scss` file, and see the auto-reloading kick in
- Verify frontend tooling works:
  - `bun run tscheck` (TypeScript type checking via tsgo)
  - `bun run lint` (Full linting - runs both oxlint type-aware and eslint)
  - `bun run lint:fast` (Fast linting via oxlint without type awareness)
  - `bun run fmt` (Format code via oxfmt)
  - `bun run fmt:check` (Check formatting without modifying files)
  - `bun run fmt:toml` (Format TOML files via taplo)
- `prek install`
- `prek run --all-files`
