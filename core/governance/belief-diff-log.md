# Belief Diff Log

This file records periodic snapshots of how the memory system's content has changed over time. Each entry is generated during the 30-day periodic review cycle (see `core/governance/update-guidelines.md`) and provides a concise summary of drift since the previous entry.

## Purpose

The belief diff makes **drift visible**. A single malicious injection might be caught at write time, but slow-burn drift — many small, plausible changes that cumulatively shift agent behavior — is only detectable by comparing snapshots over time. If the user sees unexpected entries in this log, they can investigate and revert the relevant commits.

## Entry format

```
## [YYYY-MM-DD] Periodic review

### New files
- `path/to/file.md` — source: X, trust: Y, summary of content

### Modified files
- `path/to/file.md` — what changed and why

### Retired/archived files
- `path/to/file.md` — reason for retirement

### Trust changes
- `path/to/file.md` — trust: low → medium (reason)

### Security flags
- Summary of any anomalies or boundary violations detected since last review

### Identity drift
- Number of identity traits added/changed/removed
- Whether changes are consistent with observed user behavior

### Assessment
Brief overall assessment: is the system's evolution consistent with legitimate use, or are there patterns that warrant investigation?
```

---
