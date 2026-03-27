---
source: agent-generated
trust: medium
created: 2026-03-26
origin_session: memory/activity/2026/03/26/chat-002
title: "Phase 5 Design: Structured HITL"
---

# Phase 5 Design: Structured Human-in-the-Loop

## Motivation

The harness report emphasizes: "Operationalize HITL as an interrupt/resume mechanism with serialized run state." Engram already has pieces:

- `requires_approval` phase flag (Phase 1) — signals that a human should approve before proceeding.
- `review-queue.md` — collects proposed/protected changes for triage.
- Change-class system — routes file-level changes through approval tiers.

What's missing is the **workflow**: a structured mechanism to request approval, serialize the pending action, pause the plan, notify the human, and resume after resolution. Currently, `requires_approval` surfaces an `approval_required: true` flag in the response, but the agent must improvise the actual approval-seeking behavior.

---

## Extension 1: Approval workflow lifecycle

### Problem

There's no formal lifecycle for approval requests. The agent knows it needs approval but has no protocol for requesting, tracking, or receiving it.

### Design

Approval lifecycle: **request → pending → resolve → resume**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Request    │────>│   Pending   │────>│   Resolve   │────>│   Resume    │
│ (agent asks) │     │ (awaiting)  │     │ (human acts)│     │ (plan cont.)│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                          │ (timeout)          │ (reject)
                          v                    v
                    ┌─────────────┐     ┌─────────────┐
                    │   Expired   │     │  Rejected   │
                    └─────────────┘     └─────────────┘
```

### Approval states

| State | Meaning | Trigger |
|---|---|---|
| `pending` | Waiting for human review | Agent calls `memory_request_approval` |
| `approved` | Human approved; plan may resume | Human calls `memory_resolve_approval` with approve |
| `rejected` | Human rejected; phase cannot proceed as-is | Human calls `memory_resolve_approval` with reject |
| `expired` | Approval not received within deadline | Automatic on read if past expiry |

---

## Extension 2: Approval storage — `working/approvals/`

### Problem

Pending approvals need a durable, inspectable home.

### Design

New directory: `core/memory/working/approvals/`

```
core/memory/working/approvals/
├── SUMMARY.md                      # Approval queue navigator
├── pending/                        # Active approval requests
│   └── {plan_id}--{phase_id}.yaml  # One file per pending approval
└── resolved/                       # Completed approvals (recent history)
    └── {plan_id}--{phase_id}.yaml  # Moved here after resolution
```

### Approval document schema

```yaml
# pending/verification-phase-2--verify-tool-design.yaml
plan_id: verification-phase-2
phase_id: verify-tool-design
project_id: harness-expansion
status: pending
requested: '2026-04-05T14:30:00Z'
expires: '2026-04-12T14:30:00Z'    # 7 days default
context:
  phase_title: "Design the memory_plan_verify MCP tool"
  phase_summary: |
    This phase decides the tool interface for postcondition verification.
    Sources indicate PostconditionSpec already has type/target fields.
    Decision: what to auto-verify vs. leave as manual.
  sources:
    - core/tools/agent_memory_mcp/plan_utils.py
    - core/memory/working/projects/harness-expansion/IN/phase-2-verification-design.md
  changes:
    - path: core/memory/working/projects/harness-expansion/IN/phase-2-verification-design.md
      action: update
      description: Record tool interface decision
  change_class: proposed
  budget_status:
    sessions_used: 2
    max_sessions: 6
    days_remaining: 26
resolution: null                    # Populated on resolve
reviewer: null
resolved_at: null
comment: null
```

### Resolution

When resolved, the document is updated then moved to `resolved/`:

```yaml
status: approved               # or: rejected, expired
resolution: approve            # approve | reject
reviewer: "user"               # who resolved (from session context)
resolved_at: '2026-04-05T15:00:00Z'
comment: "Looks good, proceed with the conservative allowlist approach."
```

### Expiry

- Default expiry: 7 days from request. Configurable per plan via budget or per request.
- Expired approvals are detected on read: if `status: pending` and `expires < now`, status transitions to `expired`.
- Expired approvals block the plan. They do not auto-approve.

---

## Extension 3: MCP tools — `memory_request_approval` and `memory_resolve_approval`

### `memory_request_approval`

```
Parameters:
  plan_id: str
  phase_id: str
  project_id: str | null    — inferred from plan if unambiguous
  context: str | null        — additional context for the reviewer (appended to auto-generated context)
  expires_days: int = 7      — days until expiry

Returns: MemoryWriteResult with new_state containing:
  approval_file: str         — path to the pending approval document
  status: "pending"
  expires: str               — expiry timestamp
  plan_status: "paused"      — plan was paused
```

Behavior:
1. Validates the plan and phase exist; phase must be `pending` or `in-progress`.
2. Creates approval document in `working/approvals/pending/` with phase context auto-populated from plan.
3. Sets plan status to `paused` (new plan status — see Extension 4).
4. Regenerates `working/approvals/SUMMARY.md`.
5. Commits to git.

### `memory_resolve_approval`

```
Parameters:
  plan_id: str
  phase_id: str
  resolution: str            — "approve" | "reject"
  comment: str | null        — optional reviewer comment

Returns: MemoryWriteResult with new_state containing:
  approval_file: str         — path to the resolved approval document
  status: str                — "approved" | "rejected"
  plan_status: str           — "active" (if approved) | "blocked" (if rejected)
```

Behavior:
1. Loads the pending approval document. Error if not found or already resolved.
2. Updates status, resolution, reviewer, resolved_at, comment.
3. Moves the file from `pending/` to `resolved/`.
4. If approved: sets plan status back to `active`; phase remains `in-progress` (agent can now proceed).
5. If rejected: sets plan status to `blocked`; records rejection reason.
6. Regenerates `working/approvals/SUMMARY.md`.
7. Commits to git.

---

## Extension 4: Plan pause/resume — new `paused` status

### Problem

Plans currently have five statuses: `draft`, `active`, `blocked`, `completed`, `abandoned`. There's no way to express "waiting for human input" — `blocked` implies a technical dependency, not a human workflow pause.

### Design

Add `paused` to `PLAN_STATUSES`:

```python
PLAN_STATUSES = {"draft", "active", "blocked", "paused", "completed", "abandoned"}
```

Transitions:
- `active` → `paused`: when `memory_request_approval` is called
- `paused` → `active`: when approval is granted via `memory_resolve_approval`
- `paused` → `blocked`: when approval is rejected
- `paused` → `abandoned`: manual (user decides to abandon)

### Integration with `memory_plan_execute`

When plan status is `paused`:
- `inspect` works normally (agents can still read plan state).
- `start` returns an error: "Plan is paused, awaiting approval for phase {phase_id}. Use `memory_resolve_approval` to approve or reject."
- `complete` returns an error: same message.

### Automatic pause on `requires_approval` phases

When `memory_plan_execute` with `action: "start"` encounters a `requires_approval: true` phase:

1. If no pending approval exists for this phase: automatically call `memory_request_approval` internally, pause the plan, and return the approval context in the response.
2. If a pending approval exists: return "awaiting approval" status.
3. If the approval was already granted: proceed normally.
4. If the approval was rejected: return rejection reason and block.

This makes the approval workflow automatic for `requires_approval` phases — the agent doesn't need to manually call `memory_request_approval`.

---

## Extension 5: Approval expiry

### Problem

Pending approvals that are never resolved should not block plans indefinitely.

### Design

- Each approval has an `expires` timestamp (default: 7 days from request).
- On any read of the approval (via `memory_plan_execute`, `memory_resolve_approval`, or the approval UI), check if `expires < now`.
- If expired: transition status to `expired`, move to `resolved/`, set plan to `blocked`.
- Expired approvals require explicit re-request (call `memory_request_approval` again) or plan abandonment.
- Expiry is not a background process — it's checked on read (lazy evaluation).

---

## Extension 6: Approval UI — `HUMANS/views/approvals.html`

### Problem

Humans need a convenient way to see pending approvals and act on them.

### Design

New file: `HUMANS/views/approvals.html`

Features:
- **Pending approvals list:** Shows all pending approvals with phase context, requested date, expiry countdown.
- **Approval detail view:** Full phase context (sources, changes, change_class, budget status), reviewer comment field.
- **Approve/reject buttons:** Calls `memory_resolve_approval` via fetch to the MCP server (or writes the resolution file directly if server access is unavailable).
- **Resolved history:** Recent resolved approvals with outcome and comment.
- **Expired alerts:** Highlight expired approvals that need re-request or plan abandonment.

Implementation:
- Follows existing `HUMANS/views/` patterns.
- Reads approval YAML files via fetch from file system.
- Pure client-side rendering.
- Links to plan context in `projects.html`.

---

## Integration with existing HITL mechanisms

### review-queue.md

The review queue remains for **non-plan changes** — ad-hoc proposed/protected modifications, governance proposals, security flags. Plan-based approval goes through `working/approvals/`.

Relationship:
- `review-queue.md` is a lightweight, text-based queue for one-off items.
- `working/approvals/` is a structured, file-based workflow for plan phases.
- Both are surfaced in the approval UI (different sections).

### Change-class system

The change-class system determines approval requirements from file paths. `requires_approval` adds approval for decisional reasons. The approval workflow handles both:
- A `requires_approval: true` phase triggers the approval workflow regardless of change-class.
- A phase touching protected paths triggers change-class approval (handled by the existing preview envelope + user confirmation). The approval workflow only fires if the phase also has `requires_approval: true`.

This avoids double-gating: the existing change-class system handles file-path-based approval; the new approval workflow handles phase-level decisional approval. They compose but don't overlap.

---

## What this phase does NOT include

- **Notification system.** Approvals are stored as files; there's no push notification (email, Slack, etc.). The approval UI shows pending items, but the human must check it.
- **Multi-reviewer approval.** One reviewer per approval. No quorum or multi-sig patterns.
- **Delegation.** No way to delegate approval to another person or role.
- **Approval templates.** Each approval is auto-generated from phase context. No reusable approval templates.
- **Retroactive approval.** Once expired, an approval must be re-requested. There's no "backfill approval for a completed phase" mechanism.
