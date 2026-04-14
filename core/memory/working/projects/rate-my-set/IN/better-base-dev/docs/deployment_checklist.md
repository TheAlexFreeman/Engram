# Deployment Checklist

## Dev

- [ ] Repo Cloned
- [ ] `bb_eject.py` (Or New/Different Name for It)
  - [ ] Ensure That's Run Fully to Completion
  - [ ] Ensure New Port Offsets Are All in Place
  - [ ] Ensure "Better Base" or Any Variant of It (e.g. `better_base`) Is Not Present Unless Expected
  - [ ] Ensure "Elyon Tech", "Elyon Technologies", or Any Variant of It (e.g. `elyon`) Is Not Present Unless Expected
- [ ] `uv sync`
- [ ] Ensure Env/Secret Files Properly Populated, and MCP Files As Well
  ```
  cat .envs/.dev/.secrets.template.env >> .envs/.dev/.secrets.env
  cat .envs/.dev/.specific.template.env >> .envs/.dev/.specific.env
  touch .env
  cat .env.local.template >> .env.local
  cat .local.template.env >> .local.env
  cat .taskfile.template.env >> .taskfile.env
  ```
- [ ] `./dev_setup.sh` (Or Windows or Other System Equivalent)
- [ ] `bun i`
- [ ] `bunx dotagents install`
- [ ] `bunx dotagents sync` (If MCP files, symlinks, or gitignore state look out of sync)
- [ ] `prek install`
- [ ] `task build`
- [ ] `task back`
- [ ] `task m && task mm && task m`
- [ ] `bun run emailt && bun run emailh && python manage.py copy_react_email_templates` Works
- [ ] `task tcovdb` Passes
- [ ] `mypy .` Passes
- [ ] `bun run lint:all` Passes
- [ ] `bun run tscheck` Passes
- [ ] `prek run --all-files` Passes
- [ ] `prek run --hook-stage manual django-upgrade` Passes
- [ ] Ensure Claude Code, Codex, OpenCode, Cursor, Etc. (Whatever You Use) MCP Stuff All Working and Authenticated
- [ ] Ensure Figma Connected in MCP, VS Code/Cursor (If Relevant), and Properly Linked In, Etc.
- [ ] (If Relevant) VS Code/Cursor Extensions Installed and Project Saved
- [ ] Any Aliases to Repo Made, Shortcuts Set Up, Etc.
- [ ] Check That All `docs/code_setup.md` Steps Run (May Have Omitted a Few Here)

## Other Misc Dev

- [ ] Logo/Icon/Favicon Replacements:
  - [ ] Replace Email Icon(s)/Logo(s). Add and Commit.
  - [ ] Replace All Favicon(s). Add and Commit.
  - [ ] Replace Frontend Icon(s)/Logo(s). Add and Commit.
  - [ ] Replace Backend Icon(s)/Logo(s). Add and Commit.
- [ ] Ensure All File/Folder Paths in This Project Match Project Name and Not Original BB Template/Scaffolding Stuff

## CI

- [ ] `dev` Set to Default Branch
- [ ] CI Passes All Checks on `dev`
- [ ] CI Passes All Checks on `main`

## Prod

- [ ] Get Domain DNS on Cloudflare
- [ ] Get Temporary Powerful Cloudflare API Key (e.g. 1-3 Day Expiry). Store That in a Secret Location. Can Help for Later Steps.
- [ ] Get Production Mail System Set Up
  - [ ] (If Relevant) Mailgun
    - [ ] Get All Domain DNS Records Set Up
    - [ ] Get API Key, Store in Secret Location
    - [ ] Get Signing Key, Store in Secret Location
  - [ ] (If Relevant) Resend
    - [ ] Get All Domain DNS Records Set Up
    - [ ] Get API Key, Store in Secret Location
    - [ ] (If Relevant) Get Signing Key, Store in Secret Location
    - [ ] Ensure `prod.py` and `anymail` Stuff Points to This As Necessary
  - [ ] (If Relevant) Cloudflare Email Routing/Sending
    - [ ] Get All Domain DNS Records Set Up
    - [ ] Get API Key, Store in Secret Location
    - [ ] (If Relevant) Get Signing Key, Store in Secret Location
    - [ ] Ensure `prod.py` and `anymail` Stuff Points to This As Necessary
  - [ ] Regardless of Provider, Set Up Strict DMARC Record
- [ ] (If Relevant) Set Up Stripe
  - [ ] (If Relevant) Create Stripe Account
  - [ ] (If Relevant) Get Live Public Key, Store in Secret Location
  - [ ] (If Relevant) Get Live Secret Key, Store in Secret Location
  - [ ] (If Relevant) Get Test Public Key, Store in Secret Location
  - [ ] (If Relevant) Get Test Secret Key, Store in Secret Location
  - [ ] (If Relevant) Add Stripe Keys to Prod Env Files
  - [ ] (If Relevant) Set Proper Product/Price Lookup Keys in the Codebase
  - [ ] (If Relevant) Add Stripe Products and Prices with Appropriate Lookup Keys, Etc.
- [ ] Set Up Sentry Project
  - [ ] Ensure All Sentry and Vite Sentry Env References (Template Ones) Point to Correct Org(s) and Project(s)
  - [ ] Set Up Sentry Django Project. Safely Store DSN for Later.
  - [ ] (If Relevant) Set Up Sentry Prod Slack Channel and Standard Alert to That
    - [ ] Test That the Alert Fires and Sends Properly
    - [ ] Safely Store Relevant Secrets/Channel IDs/Variables for Later
  - [ ] Get a Token and Safely Store It for Doing the Source Maps/Releases
- [ ] Ensure Secrets Set/Stored
  - [ ] Some of This Will Be Above and/or Below, But Just Ensure:
  - [ ] Nice/Unique Django Admin URL
  - [ ] Securely Generate and Set Django Secret Key (e.g. `python -c "import secrets; print(secrets.token_urlsafe(100)[:50])"`)
  - [ ] Pick an SSH Port. Replace `setup_steps.sh` File and Anywhere Else.
  - [ ] Pick a PostgreSQL Port. Replace `setup_steps.sh` File and Anywhere Else.
  - [ ] Pick If You're Going to Expose the PostgreSQL Port or Not
- [ ] (If Relevant) PostgreSQL External Access with SSL/Certbot
  - [ ] (If Relevant) If Exposing PostgreSQL Port Externally, Add Cloudflare Info to `/home/ubuntu/.secrets/certbot/cloudflare.ini`
  - [ ] (If Relevant) Run Certbot Steps from `setup_steps.sh`
  - [ ] (If Relevant) Verify PostgreSQL SSL Certs Are Generated and Working
- [ ] Server Setup
  - [ ] Bare Metal/VPS Route
    - [ ] Create/Set Up the Server. Safely Store All Credentials on Dashlane or Similar.
    - [ ] Create `~/.ssh/...` Setup for It, Keys, Alias, Etc. and Safely Store That on Dashlane or Similar As Well.
    - [ ] Create or Ensure the `ubuntu` or Similar Non-Root User for This Project
    - [ ] Run `scripts/prod/setup_steps.sh` to Completion and Follow Every Step
    - [ ] Safely Store All Backend Secrets to Dashlane or Similar
    - [ ] Remove All Non-Dev (e.g. Stage/Prod) Temporarily Set Secrets File from Local Machine(s)
- [ ] Cloudflare Buckets Setup (Ensure, May Be Partially or Fully Done in Above Step)
  - [ ] Set Up Public Files Bucket
  - [ ] Set Up Private Files Bucket
  - [ ] Set Up Custom Domain for Public Files Bucket
  - [ ] Use Script(s) to Ensure CORS and Stuff Set Properly for All Buckets
  - [ ] Safely Store and Retrieve API Keys for Main App Buckets Stuff
  - [ ] Set Up DB Backup Bucket
  - [ ] Safely Store and Retrieve API Keys for Backup Buckets Stuff
- [ ] Update Hard-Coded Values Marked with `DevOps_Server_Setup_TODO` Comments:
  - [ ] `scripts/prod/setup_steps.sh` - SSH Port, PostgreSQL Port
  - [ ] `scripts/prod/setup_cloudflare_buckets.sh` - Bucket Names, Domain Names
  - [ ] `scripts/prod/server_files/proj/better-base/backup_db_and_fixtures.py` - R2 Endpoint URLs, Bucket Names, Database Name
  - [ ] Add, Commit, and Push All of That
- [ ] Sanity Checks
  - [ ] Does Sign Up Work?
  - [ ] (If Relevant) Does Sign Up Properly Block Non-Allowed Domains?
  - [ ] Does Verify Email Work?
  - [ ] Are We Getting Emails Sent to Us Properly?
  - [ ] https://www.mail-tester.com/ - Do We Get a 10/10? Do We Have Everything Set Up?
    - [ ] Go Deep Into Details Here As Necessary, Get to 10/10 However We Can
  - [ ] Delete Email Test User(s)
  - [ ] Is the Celery Worker Running and Processing Tasks?
- [ ] Database Backup Verification
  - [ ] Do a One-Off DB Backup Run. Verify You Can See the File in Cloudflare R2.
  - [ ] Set a Reminder for 1 Day to Check on the Backups Again
  - [ ] Set a Reminder for 4+ Days to Verify You Can See Three Different Backups (mod-0, mod-1, mod-2)
- [ ] Come Back to Sentry
  - [ ] (If Relevant) Set Up an Uptime Monitor
  - [ ] (If Relevant) Set Up an Alert for the Uptime Monitor - Email
  - [ ] (If Relevant) Set Up an Alert for the Uptime Monitor - Slack
  - [ ] Hit `/sentry-test` on the Frontend and Verify Everything Works
- [ ] Forward Email (or Similar) Setup
  - [ ] Set Up `help@betterbase.com` to Forward to Stakeholder(s)
    - [ ] Test Email(s) Received
    - [ ] (If Relevant) Test Email(s) Can Be Sent
  - [ ] Set Up `support@betterbase.com` to Forward to Stakeholder(s)
    - [ ] Test Email(s) Received
    - [ ] (If Relevant) Test Email(s) Can Be Sent
  - [ ] (If Relevant) Set Up `info@betterbase.com` to Forward to Stakeholder(s)
    - [ ] Test Email(s) Received
    - [ ] (If Relevant) Test Email(s) Can Be Sent
  - [ ] Set Up `person-1@betterbase.com` to Forward to Relevant Person(s)
    - [ ] Test Email(s) Received
    - [ ] Test Email(s) Can Be Sent
  - [ ] Set Up `person-2@betterbase.com` to Forward to Relevant Person(s)
    - [ ] Test Email(s) Received
    - [ ] Test Email(s) Can Be Sent
  - [ ] Set Up `person-3@betterbase.com` to Forward to Relevant Person(s)
    - [ ] Test Email(s) Received
    - [ ] Test Email(s) Can Be Sent
  - [ ] Set Up Any Remaining People
    - [ ] Test Email(s) Received
    - [ ] Test Email(s) Can Be Sent
- [ ] Browser Bookmarks
  - [ ] To Make Things Easier Later, Bookmark Things Like:
    - [ ] Domain Registrar
    - [ ] Cloudflare Domain
    - [ ] Cloudflare Buckets
    - [ ] (If Relevant) Cloudflare Email
    - [ ] (If Relevant) Cloudflare Worker(s)
    - [ ] Mail System (e.g. Mailgun)
    - [ ] Bare Metal Server/VPS
    - [ ] Sentry
    - [ ] GitHub
    - [ ] (If Relevant) Harvest
    - [ ] (If Relevant) Forward Email or Similar
    - [ ] (If Relevant) Any Other Services
    - [ ] The App Itself
    - [ ] The Django Admin for the App
- [ ] Final Secrets Store
  - [ ] All on Dashlane or Similar, Very/Multi Authenticated
  - [ ] All Prod Backend, Frontend, Shared, Misc, Other, Secrets
  - [ ] (If Relevant) All Stage Backend, Frontend, Shared, Misc, Other, Secrets
  - [ ] (If Relevant) All Dev Backend, Frontend, Shared, Misc, Other, Secrets
  - [ ] (If Relevant) All Agent Backend, Frontend, Shared, Misc, Other, Secrets
  - [ ] (If Relevant) SSH Config and Key(s)
  - [ ] Confirm - All on Dashlane or Similar, Very/Multi Authenticated

## (If Relevant) Stage

- [ ] (If Relevant) Set Up Stage Environment Similarly to Prod Above
- [ ] (If Relevant) Set Up Stage Cloudflare Buckets (`*-stage-public`, `*-stage-private`)
- [ ] (If Relevant) Set Up Stage Domain DNS (e.g. `stage.example.com`)
- [ ] (If Relevant) Populate Stage Env Files from Templates (`.envs/.stage/*`)
- [ ] (If Relevant) Set Up Stage Sentry Project (If Separate from Prod)
- [ ] (If Relevant) Set Up Stage Mail System (If Separate from Prod)
- [ ] (If Relevant) Run Stage Server Setup Steps
- [ ] (If Relevant) Sanity Check Stage Environment
  - [ ] (If Relevant) Does Sign Up Work on Stage?
  - [ ] (If Relevant) Does Email Work on Stage?
  - [ ] (If Relevant) Is the Celery Worker Running on Stage?
- [ ] (If Relevant) Bookmark Stage App and Admin
- [ ] (If Relevant) Anything else from above with Stage.
