---
source: agent-generated
type: incident-report
domain: system-operations
created: 2026-03-19
trust: low
tags: [incident, data-loss, tmp, git, session-hygiene, pwr, engram, lessons-learned]
origin_session: core/memory/activity/2026/03/19/chat-002
related:
  - memory/knowledge/self/_archive/2026-03-20-git-session-followup.md
  - memory/knowledge/self/_archive/session-2026-03-20.md
  - memory/knowledge/self/_archive/2026-03-21-architecture-audit-and-knowledge-migration.md
  - memory/knowledge/self/_archive/codex-mcp-timeouts-git-stdin.md
---

# Incident Report: /tmp Data Loss — 2026-03-19

## Summary

Nine git commits produced during the 2026-03-19 Cowork session were lost when
the `/tmp/work-repo5` clone was cleaned up by the sandbox environment before the
commits could be pushed to the GitHub remote. All content was successfully
recreated from session context, but the incident is worth documenting in full
because it directly illustrates a class of risk the Engram system is being
designed to mitigate — and because it reveals a gap in the current session
workflow that should be closed.

---

## What happened

### Session context

The session was a continuation of prior work on the `live-test--maiden` branch.
At session start, `/tmp/work-repo5` (a clone of the local workspace) was present
from a previous context window and had 9 local commits ahead of the remote and
was 4 commits behind it — a diverged state that had not yet been reconciled.

### The work performed (all subsequently lost)

The following commits were made to `/tmp/work-repo5` during this session:

| Commit (original hash) | Description |
|---|---|
| `5f1f0e9` | promote `knowledge/_unverified/ai-history` → `knowledge/ai-history` (11 files, frontmatter fixes, SUMMARY updates) |
| `b019344` | research: Axial Revolution — ancient philosophy knowledge file |
| `b97bc19` | brainstorm: PWR interaction-tracking protocol (initial notes) |
| `d15a70b` | brainstorm: add self-optimization loop to PWR notes |
| `996dfd1` | brainstorm: add goals layer to PWR notes |
| `45e73d8` | brainstorm: add naming section to PWR notes (Engram selected) |
| `4302248` | research: McLuhan and media theory |
| `42b0568` | research: Nick Land — accelerationism and techno-capital |
| `43da540` | brainstorm: add structural honesty section to PWR notes |

Total: 9 commits, ~1,800 lines of new content across 14 files.

### The failure mode

When the user issued "please ensure you have the latest version of this branch
from the remote," a fresh clone was required because `/tmp/work-repo5` was no
longer present — the sandbox `/tmp` directory had been reset between tool calls.
The fresh clone (`/tmp/work-repo6`) reflected only the GitHub remote state at
`4c0cd1c`, which predated all nine commits. The commits existed nowhere except
in the cleaned-up `/tmp/work-repo5` and in the session's active context window.

### Recovery

All nine commits were recreated in `/tmp/work-repo6` from context during the
same session. No content was permanently lost because the session had not ended.
Had the session ended before recovery, the content would have been unrecoverable.

---

## Root cause analysis

### Immediate cause

The agent's git workflow used `/tmp/` as working storage for git clones. The
sandbox environment periodically resets `/tmp/`, and no push to the remote
(GitHub or the local workspace) was performed before the reset occurred.

### Contributing factors

**1. No push after commit.** The established workflow was: clone to `/tmp/`,
make changes, commit, then advise the user to `git pull && git push` from their
local machine. This created a window between commit and durability during which
a `/tmp` reset would lose all work. In this session, that window lasted for
nine commits and several hours of conversation.

**2. Diverged branch state.** The branch was already diverged (local ahead,
remote ahead) before session work began. This meant a push from `/tmp/` would
have required a pull-then-push sequence that the agent cannot perform without
GitHub credentials. The credential gap forced a "advise user to push" workflow
that deferred durability to an action outside the agent's control.

**3. No durability checkpoint.** There was no mechanism to write completed work
to the persistent workspace folder (`/sessions/.../mnt/agent-memory-seed`) as a
checkpoint short of a full push. The workspace folder IS the git repo root — it
could have been updated by copying files into it directly, providing partial
durability even without a commit.

**4. Session-spanning work in a stateless environment.** The Cowork sandbox
does not guarantee `/tmp/` persistence across tool calls within a session,
let alone across sessions. Using `/tmp/` for anything that must survive is
structurally fragile.

---

## What this illustrates about the Engram design

This incident is a concrete instance of the failure mode the PWR protocol was
designed to prevent. The session produced significant intellectual work — research
files, brainstorm notes, a knowledge promotion — that existed only as transient
process state until it was committed to git. Had the session ended before recovery,
the work would have left no durable trace.

### The irony

The brainstorm notes that were lost included significant discussion of:
- **PWR** (Prompt-Work-Response) as an eidetic interaction log for exactly this
  kind of durability
- **The categorical imperative of honesty** in a system with legible memory
- **Engram** as a name for a git-backed memory system that keeps records

The system that was being designed to prevent this class of problem failed to
protect against it during the design session, because the infrastructure
described had not yet been built. This is a perfect illustration of the
bootstrapping problem: the safety properties of a mature Engram depend on the
PWR infrastructure being in place, but that infrastructure has to be built
during sessions that don't yet have it.

---

## Lessons and mitigations

### Immediate (procedural, no code changes required)

**1. Write directly to the workspace folder when possible.** For files that
don't require git history during construction (new knowledge files, brainstorm
notes), write directly to
`/sessions/relaxed-elegant-planck/mnt/agent-memory-seed/` rather than to a
`/tmp/` clone. This provides immediate durability in the persistent workspace,
independent of whether a git commit or push occurs. Git operations (staging,
committing) can be performed on the workspace repo directly if `index.lock`
is not an issue, or via a `/tmp/` clone for the commit step only.

**2. Commit and advise push more frequently.** Rather than accumulating many
commits before advising a push, advise after each logically complete unit of
work. The user can batch the push, but the agent should make the push urgency
visible earlier.

**3. Note the session's unpushed commit count prominently.** When the unpushed
commit count exceeds ~3, flag it explicitly and repeat the push advisory rather
than treating it as background context.

### Medium-term (requires infrastructure)

**4. PWR logging.** If every interaction were logged as a PWR record in the
persistent workspace, the content of this session would have been durable from
the moment it was generated, regardless of whether git commits had been made.
The PWR record is not a git commit — it's a file write to the persistent
folder, which survives `/tmp/` resets. This is precisely the eidetic memory
property the PWR protocol was designed to provide.

**5. The workspace folder as primary write target.** Establish a norm that all
durable agent output is written to the workspace folder first, with git commits
as the secondary durability/versioning layer. The current norm (clone to `/tmp/`,
work there, commit there, advise push) inverts this: git is treated as the
primary, and the workspace folder is treated as a read-only source. Reversing
the norm would eliminate the `/tmp/`-reset failure mode entirely.

**6. Session-end checklist.** A session-closing protocol that verifies: (a) all
significant work is committed, (b) the unpushed commit count is reported to the
user, (c) any `/tmp/`-only state is identified and either recovered or noted as
lost.

### Structural (requires system design)

**7. GitHub credential access.** If the agent could push to GitHub directly,
the "advise user to push" workflow could be replaced with immediate push after
commit. This would close the durability window entirely. The security
considerations (token scope, sandbox isolation) are non-trivial but worth
designing around.

---

## Action items

- [ ] Update the session workflow to write new files directly to the workspace
      folder rather than exclusively to `/tmp/` clones
- [ ] Add a "push advisory" to the session-closing protocol
- [ ] Add a note to `plans/` or `meta/` about the `/tmp/`-reset risk
- [ ] Track PWR protocol implementation as a concrete durability improvement
      (blocked on: `mcp-reorganization.md` per current plan priorities)

---

*This report was written during the recovery session, after all lost content
had been recreated. It is filed in `_unverified/system-notes/` rather than
directly in `meta/` because it has not yet been reviewed by Alex; if approved,
it should be promoted to `meta/` or a dedicated `incidents/` folder.*
