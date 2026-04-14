---
type: project-note
project: rate-my-set
topic: better-base-roadmap
created: 2026-04-14
depends-on: roadmap.md
status: draft
---

# Better Base → Rate My Set — concrete build roadmap

A phased plan for turning the Better Base scaffold into the Rate My Set v1 product. Each phase builds on the previous one and ends in a testable, demonstrable state. Phases are roughly week-scale; real elapsed time depends on available hours.

## What Better Base gives us for free

Better Base is not empty boilerplate. These pieces are production-grade and can carry straight into v1 with branding changes only:

| Layer | What exists | v1 reuse plan |
|-------|-------------|---------------|
| **Auth** | Full custom DRF auth: signup, login, email verify, password reset, change-email, change-password. Session-based, Argon2 hashing. | Keep as-is. Reviewer accounts are just Users. |
| **Accounts & memberships** | Multi-tenant account model, memberships, role-based access, invitations with token lifecycle. | Repurpose: a "moderation team" is an Account with team memberships. Personal accounts become reviewer profiles. |
| **API infra** | DRF + drf-spectacular, camelCase middleware, CORS, OpenAPI generation, orjson rendering. | Keep. All new endpoints follow the same patterns. |
| **Frontend shell** | React 19, TanStack Router/Query, Chakra UI v3, Jotai, Sentry, Vite 8, file-based routing. | Keep. New product screens slot into the existing route tree. |
| **Ops pattern** | Business logic in `ops.py` / `ops/` modules, validate-then-act. | Adopt for all Rate My Set domain logic. |
| **DevOps** | Docker Compose (dev/ci/prod/stage), Taskfile, GitHub Actions CI, Render deploy config. | Keep. Add Rate My Set–specific env vars. |
| **Testing** | pytest + factory-boy + respx + network blocking + xdist + coverage. | Keep. New domain tests follow existing patterns. |
| **Code quality** | ruff, mypy, oxlint, oxfmt, ESLint, tsgo, djlint, pre-commit/prek. | Keep. |

## What needs building

Everything below the auth/account layer is new. The existing codebase has zero Rate My Set domain code — no productions, no reviews, no scorecards, no moderation queue.

---

## Phase 0 — Fork, rebrand, validate toolchain

**Goal:** A running local dev environment with Rate My Set branding, passing CI, no Better Base marketing copy left.

### Tasks

1. **Fork or copy** the Better Base repo into the Rate My Set project repo.
2. **Rebrand strings:**
   - `config/settings/base.py`: Spectacular title/description, `DEFAULT_FROM_EMAIL`, support email, site name.
   - `backend/accounts/models/invitations.py`: email headline copy.
   - Root `README.md`: replace cookiecutter boilerplate.
   - `AGENTS.md`: update project context.
   - Email templates under `backend/templates/` and `emails/`.
   - Logo SVGs in `frontend/components/logos/`.
3. **Validate toolchain** on your machine:
   - `task build` → Docker images build cleanly.
   - `uv sync` → venv works with Python 3.14+.
   - `task back` → Postgres + Redis + Mailpit running.
   - `python manage.py migrate` → clean.
   - `bun install && bun dev` → frontend serves at `:4020`.
   - `task tcovdb` → existing tests pass.
   - `task mp` → mypy clean.
   - `bun run lint && bun run tscheck` → frontend clean.
4. **Decide account-model mapping** (see design decision below).
5. **Push initial commit** with CI green.

### Design decision: account model mapping

Better Base's Account/Membership model is designed for SaaS team workspaces. Rate My Set's trust model separates reviewers, moderators, and readers. Two reasonable mappings:

**Option A — Lightweight (recommended for v1):**
- Every reviewer is a User with a personal Account.
- The moderation team is a single team Account. Moderators are Members of that account with a `moderator` role.
- No reviewer-facing "team" features. Hide team UI for personal accounts.
- Public/unauthenticated readers don't have accounts at all; they see the public aggregate surface.

**Option B — Heavier multi-tenant:**
- Model each "production company" or "union local" as an Account.
- Workers can belong to multiple.
- Adds structural overhead that v1 doesn't need; useful if v2 union credentialing requires institutional accounts.

Recommend **Option A** and revisit at v2.

---

## Phase 1 — Domain models and admin

**Goal:** The core data model exists, is migrated, has admin interfaces, and has factory-boy factories for testing.

### New Django app: `backend/productions`

```
backend/productions/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── productions.py      # Production model
│   ├── reviews.py           # Review model
│   ├── scorecards.py        # Computed scorecard cache
│   └── verifications.py     # Verification attestation records
├── admin/
│   ├── __init__.py
│   ├── productions.py
│   ├── reviews.py
│   └── verifications.py
├── ops/
│   ├── __init__.py
│   ├── submit_review.py
│   ├── verify_review.py
│   ├── compute_scorecard.py
│   └── publish_reviews.py
├── api/
│   ├── __init__.py
│   ├── views/
│   ├── serializers/
│   └── permissions.py
├── factories.py
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_ops.py
    └── test_api.py
```

### Models

**Production**
- `id` (UUIDv7, per project convention)
- `name`, `code_name` (nullable, for covert productions)
- `producer` (text)
- `production_type` (enum: film, tv_series, tv_movie, commercial, music_video, other)
- `union_status` (enum: union, non_union, mixed)
- `wrap_date` (nullable date — known after wrap; controls publication lag)
- `city`, `state` (for geographic filtering)
- `status` (enum: active, wrapped, published)
- `created_by` (FK → User, nullable, the first reviewer who added it)
- `verified_by_moderator` (bool, default False — gates public visibility of new productions added by users)
- Standard `CoreModel` timestamps.

**Review**
- `id` (UUIDv7)
- `production` (FK → Production)
- `reviewer` (FK → User)
- `role_class` (enum: background, day_player, principal, crew, other)
- `department` (enum: camera, grip, electric, ad, cast, wardrobe, hair_makeup, transport, locations, production_office, other)
- `union_member` (bool)
- `dates_worked` (DateRange or start/end pair)
- Scores (1–5 integer each): `professionalism`, `safety`, `food`, `compensation_hours`, `overall`
- Flags (bool): `harassment_observed`, `discrimination_observed`, `injury_observed`
- `professionalism_notes`, `safety_notes`, `food_notes`, `general_notes` (text, nullable)
- `sanitized_notes` (text, nullable — post-sanitization versions for publication)
- `verification_status` (enum: pending, verified, rejected, expired)
- `submitted_at`, `verified_at`, `published_at` (timestamps)
- Unique constraint: one review per (production, reviewer).

**Verification**
- `id` (UUIDv7)
- `review` (OneToOne → Review)
- `moderator_1` (FK → User)
- `moderator_2` (FK → User, nullable — for paired-mod review)
- `upload_hash` (char — hash of the uploaded booking confirmation, for audit; no pointer to the file after destruction)
- `decision` (enum: approved, rejected, needs_info)
- `decision_reason` (text, nullable)
- `upload_destroyed_at` (timestamp, nullable)

**Scorecard** (materialized/cached aggregate)
- `production` (OneToOne → Production)
- `review_count`
- `mean_professionalism`, `mean_safety`, `mean_food`, `mean_compensation_hours`, `mean_overall`
- `harassment_count`, `discrimination_count`, `injury_count`
- `union_review_count`, `non_union_review_count`
- `last_computed_at`

### Phase 1 tasks

1. Create `backend/productions` app, register in `INSTALLED_APPS`.
2. Implement models with migrations.
3. Register all models in Django admin with sensible list displays and filters.
4. Write factory-boy factories for all models.
5. Write model-level tests (constraints, enums, manager methods).
6. Add the app to `AGENTS.md` and any new conventions.

---

## Phase 2 — Core operations (business logic)

**Goal:** The four critical business operations work, are tested, and enforce the roadmap's trust rules.

### `submit_review` op
- Authenticated user submits a review for a production.
- Validates: user hasn't already reviewed this production (unique constraint).
- Creates Review in `pending` verification status.
- Triggers upload handling (see Phase 3 for the file pipeline).

### `verify_review` op
- Moderator reviews the uploaded booking confirmation.
- Paired-mod: first moderator records provisional approval; second moderator independently confirms or rejects.
- On approval: sets `verification_status = verified`, records `upload_hash`, schedules upload destruction (24h async task).
- On rejection: sets `verification_status = rejected`, notifies reviewer, destroys upload immediately.

### `compute_scorecard` op
- Recomputes a Production's scorecard from all verified reviews.
- Handles k-anonymity: scorecard only populated when verified review count ≥ k (configurable, default 5 for member view, 10 for public).
- Separates union/non-union aggregates.
- Triggered after each review verification, and as a periodic Celery task for consistency.

### `publish_reviews` op (Celery periodic task)
- Scans productions where `wrap_date` + publication lag has passed.
- For qualifying productions with k ≥ threshold verified reviews:
  - Runs sanitization on review notes (strip department/role/date details that could deanon; LLM paraphrase if configured, else regex-based strip).
  - Sets `published_at` on qualifying reviews.
  - Updates Production `status` to `published`.
  - Recomputes scorecard.

### Phase 2 tasks

1. Implement each op module following the existing ops pattern (validate-then-act).
2. Register Celery tasks for `publish_reviews` (periodic) and `destroy_upload` (one-shot delayed).
3. Write thorough tests: happy path, edge cases (paired-mod disagreement, exactly-k threshold, lag boundary, duplicate review attempt).
4. Test k-anonymity boundaries carefully — this is the core privacy guarantee.

---

## Phase 3 — Upload and destruction pipeline

**Goal:** Reviewers can upload booking confirmations; moderators can view them; uploads are reliably destroyed after verification.

### Design

- Upload goes to a **private S3 bucket** (or local storage in dev) with short-lived pre-signed URLs.
- Files are encrypted at rest (S3 SSE or application-level envelope encryption).
- Moderator views via time-limited pre-signed download URL (expires in 15 minutes).
- After verification approval, a Celery task fires at +24h to delete the S3 object and record `upload_destroyed_at`.
- Fallback: a periodic sweep task catches any uploads older than 48h post-verification that weren't destroyed (belt-and-suspenders).
- The `upload_hash` (SHA-256 of the file) persists as the only audit artifact.

### Phase 3 tasks

1. Configure `django-storages` for a private verification-uploads bucket (separate from general media).
2. Add `VerificationUpload` transient model or handle as a field on Verification with S3 key.
3. Implement pre-signed URL generation (upload and download).
4. Implement destruction Celery task with retry logic.
5. Implement periodic sweep task.
6. Test the full lifecycle: upload → moderator view → approval → 24h destruction → hash persists.
7. Dev environment: use local filesystem with equivalent lifecycle for testing without S3.

---

## Phase 4 — API surface

**Goal:** All CRUD and query endpoints exist for the frontend to build against. OpenAPI schema generated.

### New endpoints (registered in `config/api_router.py`)

| Prefix | ViewSet | Key actions |
|--------|---------|-------------|
| `productions` | `ProductionViewSet` | `list` (search, filter by city/type/status), `retrieve`, `create` (authenticated, triggers mod review), `request_addition` (for "don't see your set?" flow) |
| `reviews` | `ReviewViewSet` | `create` (submit review + upload), `retrieve` (own review only pre-publication), `my_reviews` (list user's reviews) |
| `scorecards` | `ScorecardViewSet` | `retrieve` (by production, respects k-anon and publication rules) |
| `verifications` | `VerificationViewSet` | Moderator-only: `list` (pending queue), `retrieve` (with pre-signed download URL), `approve`, `reject` |
| `moderation` | `ModerationViewSet` | Moderator-only: `pending_productions` (new user-submitted productions needing confirmation), `approve_production`, `reject_production` |

### Permission classes

- `IsVerifiedReviewer` — user has verified email and at least one approved review (or: has an active account).
- `IsModerator` — user is a member of the moderation team account with moderator role.
- `IsPublicReader` — unauthenticated, only sees published scorecards at public k-threshold.
- `IsVerifiedMember` — authenticated + verified, sees member-lounge data at lower k-threshold.

### Serializers

- Production: public (name, scores, city, type) vs. detail (includes individual review text for member lounge).
- Review: submission serializer (write) vs. display serializer (read, post-sanitization).
- Scorecard: always computed, never directly writable.
- Verification: moderator-only serializer with upload access.

### Phase 4 tasks

1. Create serializers for all models.
2. Create viewsets with appropriate permission classes.
3. Register in `api_router.py`.
4. Run `task openapi` to generate OpenAPI schema.
5. Run `openapi-typescript` to generate frontend types.
6. Write API tests (permission boundaries are critical — test that public readers can't see below-k data, that non-moderators can't access the verification queue, etc.).

---

## Phase 5 — Frontend: public surface

**Goal:** An unauthenticated user can search for productions and see published aggregate scorecards.

### New routes

| Route | Purpose |
|-------|---------|
| `/` | Landing page: search bar, value proposition, "See full list" |
| `/search?q=...` | Search results (productions matching query) |
| `/productions/:id` | Public scorecard view for a production |
| `/productions` | Browsable list of published productions |

### New components

- `ProductionSearch` — search input with autocomplete (searches by name, code name, producer).
- `ProductionCard` — summary card showing production name, aggregate scores, review count.
- `ScorecardDisplay` — the scorecard visualization (bar/radar chart or structured grid for the five dimensions + flag counts).
- `ProductionList` — paginated list with filters (city, type, union status).
- `LandingHero` — marketing/value-prop section for the home page.

### Phase 5 tasks

1. Create route files under `frontend/routes/`.
2. Build TanStack Query hooks for `productions` and `scorecards` endpoints.
3. Build components.
4. Replace the current `/` redirect-to-settings with a proper landing page for unauthenticated users; keep the redirect for authenticated users.
5. Mobile-responsive layouts (Chakra responsive props).

---

## Phase 6 — Frontend: authenticated reviewer flow

**Goal:** A verified user can submit a review, upload booking confirmation, and track their review status.

### New routes

| Route | Purpose |
|-------|---------|
| `/_auth/reviews/new/:productionId` | Review submission form (questionnaire) |
| `/_auth/reviews` | "My reviews" dashboard |
| `/_auth/reviews/:id` | Review detail / status tracker |

### New components

- `ReviewForm` — the full questionnaire: role/department selection, score sliders (1–5), flag checkboxes, notes fields, upload widget.
- `FileUpload` — booking confirmation uploader with client-side redaction guidance ("black out your name"), progress indicator, pre-signed URL upload.
- `ReviewStatusBadge` — pending / verified / published / rejected states.
- `MyReviewsList` — list of the user's reviews with status.

### Phase 6 tasks

1. Route files and guards (must be authenticated + email-verified).
2. TanStack Query mutations for review submission and file upload.
3. Multi-step form (or single scrollable form with sections matching the questionnaire).
4. Client-side validation matching API constraints.
5. Success/error states with clear next-step messaging ("Your review is pending moderator verification").

---

## Phase 7 — Frontend: moderator dashboard

**Goal:** Moderators can view pending verifications, inspect uploads, approve/reject, and manage the production list.

### New routes

| Route | Purpose |
|-------|---------|
| `/_auth/moderation` | Moderation dashboard (queue overview) |
| `/_auth/moderation/verifications` | Pending verification queue |
| `/_auth/moderation/verifications/:id` | Single verification detail + upload viewer + action buttons |
| `/_auth/moderation/productions` | Pending production additions |

### New components

- `ModerationQueue` — filterable list of pending verifications.
- `VerificationDetail` — shows review metadata (no reviewer identity), embedded document viewer for the upload, approve/reject buttons with reason field.
- `PairedModBadge` — shows first-mod status, prompts second mod if applicable.
- `ProductionModerationQueue` — user-submitted productions needing confirmation.

### Phase 7 tasks

1. Route files with moderator-only guards.
2. TanStack Query hooks for moderation endpoints.
3. Components.
4. Test the paired-mod workflow UX: first mod sees "awaiting second review", second mod sees "first mod approved, confirm?"

---

## Phase 8 — Publication rules and k-anonymity enforcement

**Goal:** The entire read path enforces the publication rules from the roadmap, end to end.

This is less a "build" phase and more a hardening pass. The rules:

| Surface | k-threshold | Delay | Content |
|---------|-------------|-------|---------|
| Public | k ≥ 10 | 90 days post-wrap | Aggregate scorecard only |
| Verified-member lounge | k ≥ 3 | 30 days post-wrap | Individual review text (sanitized) |
| Productions | Same as public | — | No more access than public |

### Tasks

1. API-level enforcement: serializers and viewsets check thresholds and delays before including data in responses.
2. Frontend enforcement: components degrade gracefully ("Not enough reviews yet" / "Available after [date]").
3. Scorecard computation respects union/non-union segmentation.
4. Harassment/discrimination counts shown only in aggregate, never with individual review text.
5. Penetration test the API: verify that below-threshold data is truly absent from responses, not just hidden in the UI.
6. Add integration tests that cover the full lifecycle: submit 4 reviews → scorecard hidden → submit 5th → scorecard appears (for member lounge at k=3+30d, etc.).

---

## Phase 9 — Sanitization pipeline

**Goal:** Review notes are sanitized before publication to reduce deanonymization risk.

### Approach (progressive)

1. **Regex-based stripping (ship first):** Remove dates, times, call times, department names, wardrobe/trailer references, proper nouns not matching production name.
2. **LLM paraphrase (add second):** Send notes through a hosted LLM (OpenAI or local) with a prompt that preserves substantive claims while defeating stylometric attribution. Human moderator reviews the paraphrase before publication.
3. **Moderator override:** Moderator can manually edit sanitized text if automated approaches miss something.

### Tasks

1. Implement `sanitize_review_notes` op with regex pipeline.
2. Add a `SanitizationResult` model or fields tracking what was stripped.
3. Wire into `publish_reviews` Celery task.
4. (Later) Add LLM paraphrase step as an optional feature-flagged enhancement.
5. Test with adversarial examples (notes containing call times, trailer numbers, specific wardrobe descriptions).

---

## Phase 10 — Branding, legal, and launch prep

**Goal:** The product is presentable, legally reviewed, and deployable.

### Tasks

1. **Visual design pass:** Colors, typography, logo, favicon, OG images.
2. **Email templates:** Welcome, verification confirmation, review published, invitation.
3. **Legal pages:**
   - Terms of service (with entertainment attorney).
   - Privacy policy (what's stored, retention, subpoena posture).
   - Transparency page (per roadmap: what the platform keeps, for how long, who moderates).
   - Editorial statement: "We rate productions, not individuals."
4. **SEO basics:** Production pages have proper meta tags for search discoverability.
5. **Error handling:** 404, 500, rate limiting, graceful degradation.
6. **Monitoring:** Sentry (already wired), uptime checks, Celery task monitoring via Flower.
7. **Deployment:** Validate `render.yaml` or equivalent for prod; configure prod Postgres, Redis, S3.
8. **Moderator onboarding:** Training doc, NDA, bonding.

---

## What this roadmap deliberately defers to v2+

Per the product roadmap, these are out of scope for the initial build:

- Union credentialing integration (v2)
- Identity-escrow for harassment claims (v2)
- Federated whisper network (v3 — separate product)
- Production response mechanism (v3)
- Research/press API (v3)
- Rankings or leaderboards (excluded permanently)
- Named-person accusations (excluded permanently)
- Production-facing dashboards (excluded permanently)

---

## Dependency graph (what blocks what)

```
Phase 0 (fork/rebrand)
  └─► Phase 1 (domain models)
        ├─► Phase 2 (core ops)
        │     ├─► Phase 3 (upload pipeline)
        │     │     └─► Phase 4 (API)
        │     │           ├─► Phase 5 (public frontend)
        │     │           ├─► Phase 6 (reviewer frontend)
        │     │           └─► Phase 7 (moderator frontend)
        │     └─► Phase 8 (k-anon enforcement) — can start after Phase 2
        │           └─► Phase 9 (sanitization) — can start after Phase 8
        └─► Phase 10 (launch prep) — runs in parallel with Phases 5–9
```

Phases 5, 6, and 7 are independent of each other and can be built in parallel once the API exists. Phase 10 can begin as soon as Phase 0 is done (legal work) and run alongside everything else.

---

## Risk register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Upload destruction fails silently | Booking confirmations persist, violating core privacy promise | Belt-and-suspenders: Celery task + periodic sweep + monitoring alert if any upload is >48h old |
| k-anonymity threshold bypassed via API | Individual reviews exposed below threshold | API-level enforcement in serializers, not just frontend; penetration testing in Phase 8 |
| Sanitization misses deanonymizing detail | Reviewer identity inferrable from published notes | Progressive approach: regex + LLM + human review; adversarial testing |
| Paired-mod workflow UX is cumbersome | Moderator burnout, slow verification queue | Design the queue well in Phase 7; consider async notification (email/Slack) when a verification needs second review |
| Legal exposure from harassment-count field | Defamation claims against the platform | Retain entertainment attorney before launch (Phase 10); editorial statement; aggregate-only publication |
| Python 3.14+ / Django 6.0 are bleeding-edge | Dependency compatibility issues | Better Base already validates this stack; pin versions in `pyproject.toml` |
