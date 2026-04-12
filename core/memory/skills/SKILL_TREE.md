# Skill Catalog

_Auto-generated on 2026-04-09 by `generate_skill_catalog.py`. Do not edit manually._

This file is the **tier-1 progressive disclosure surface** — loaded at session start to route skill activation. Each entry is ~50–100 tokens. Full skill instructions are in each directory's `SKILL.md`.

## codebase-survey

**Path:** `codebase-survey/SKILL.md`
**Trust:** medium
**Requires:** Requires agent-memory MCP server for plan management and knowledge search

Systematic host-repo exploration for a new worktree-backed memory store. Use when projects/codebase-
  survey/SUMMARY.md is active or when codebase knowledge files still contain template stubs.
  Supports both initial survey and ongoing deepening rounds.

## flow-trace

**Path:** `flow-trace/SKILL.md`
**Trust:** low
**Requires:** Requires host repo access for code reading; uses agent-memory MCP for knowledge persistence

Trace how operations execute through a codebase — following requests, commands, jobs, or events from
  entry point through every architectural layer, recording boundary crossings, data transformations,
  and implicit couplings. Complements the codebase-survey by mapping what happens rather than what
  exists.

## onboarding

**Path:** `onboarding/SKILL.md`
**Trust:** high
**Requires:** Requires write access for profile persistence; produces export on read-only platforms
**Trigger:** session-start (condition=first_session, priority=100)

First-session user onboarding. Runs a collaborative seed-task session that surfaces the user's role,
  preferences, and working style while demonstrating memory and trust behavior in context.

## session-start

**Path:** `session-start/SKILL.md`
**Trust:** high
**Requires:** Requires agent-memory MCP server with memory_context_home and memory_session_health_check
**Trigger:** session-start (condition=returning_session, priority=50)

Session opener for returning users. Loads recent context, checks pending review items and
  maintenance triggers, greets the user with continuity. Use at the beginning of any returning
  session after initial routing.

## session-sync

**Path:** `session-sync/SKILL.md`
**Trust:** high
**Requires:** Requires agent-memory MCP server with memory_checkpoint
**Trigger:** session-checkpoint (priority=50)

Mid-session checkpoint. Captures decisions, open threads, and key artifacts without ending the
  session. Activate when the user says "sync" or "checkpoint", or when context pressure makes a save
  worthwhile.

## session-wrapup

**Path:** `session-wrapup/SKILL.md`
**Trust:** high
**Requires:** Requires agent-memory MCP server with memory_record_session
**Trigger:** session-end (priority=50)

Session closer. Writes chat summary, reflection note, ACCESS entries, and flags pending system
  maintenance. Produces deferred actions on read-only platforms. Activate when the user ends the
  session or context is running low.

---

**6 skills** indexed. Run `python HUMANS/tooling/scripts/generate_skill_catalog.py` to regenerate.
