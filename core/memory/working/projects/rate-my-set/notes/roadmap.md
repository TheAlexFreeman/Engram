---
type: project-note
project: rate-my-set
topic: roadmap
created: 2026-04-14
session: memory/activity/2026/04/14/chat-001
status: draft
source: agent-generated
origin_session: memory/activity/2026/04/14/chat-001
trust: medium
---

# Rate My Set — roadmap

A provisional staging of work from the anonymity-vs-verification discussion. The goal of v1 is **shippable with no partner dependencies**; later milestones add leverage that requires outside cooperation.

## Design pillar (applies to every milestone)

**Verification and publication are different layers.** Verification controls who can submit. Publication controls what the review leaks about its author. Both are needed; weakening either collapses the trust model.

## v1 — shippable starting point

Goal: a public site a vulnerable cast/crew member can trust to protect them, with no dependency on unions, credential issuers, or third-party partners.

**Verification layer — moderator-escrow**
- Reviewer uploads booking confirmation (call sheet, voucher, deal memo).
- Small trained moderator team verifies presence, keyed to production + date.
- Upload destroyed within 24 hours of verification; platform retains only a signed attestation record with no pointer back to the reviewer's identity.
- Paired-mod review (two mods must independently see each upload) to mitigate rogue-insider risk.
- Per-production-per-person limit — one verified attestation per reviewer per production, preventing retaliation-farming.

**Publication layer — k-anon, delay, sanitization**
- Reviews on a show are not rendered individually until k=5 verified reviews exist.
- 60-day publication lag from wrap date (so retaliation can't target an active production).
- Content sanitization pass: strip department, role, specific dates, wardrobe/trailer/call-time details that enable content-inference deanon. Ideally paraphrase via LLM to defeat stylometric attribution. Preserve substantive claims.
- Notes fields published only after sanitization; numeric scores aggregate without text.

**Asymmetric reader model**
- Public surface: aggregate scorecards only, k≥10 + 90-day delay, no individual review text.
- Verified-member "lounge": individual review text visible at k=3 + 30-day delay, logged-in verified workers only.
- Production view: aggregate scorecards only, no more than the public sees. Productions cannot request or pay for more access.

**Harassment/discrimination fields**
- Published publicly only as aggregate counts ("N members reported harassment on this production"), never as individual text.
- Individual claims routed separately — see v2 identity-escrow item below.
- Platform does not itself investigate; offers a link-out to appropriate reporting channels (union grievance, EEOC, NDA-free reporting services, etc.).

**Questionnaire amendments before v1**
- Resolve the "switch on set with in holding" editing note — split safety/comfort questions by role (principal / day player / background / crew-department).
- Use the union/non-union flag for score segmentation, not just data capture.
- Add two new dimensions the current draft is missing:
  - **Compensation & hours** — paycheck timing, kit fee disputes, turnaround violations, hours worked vs. contracted.
  - **Role context** — reviewer selects department (camera / grip / electric / AD / cast-background / cast-principal / etc.), which then weights which questions apply.
- Consider raising the rating scale from 3-point (sad/neutral/happy) to 5-point or a flag-based model to preserve variance at scale.

**Operational & legal prereqs**
- Retain a media/entertainment attorney before launch — specifically for defamation exposure on the harassment-count field and for subpoena-response playbook.
- Draft moderator NDA, bonding, training curriculum.
- Publish a transparency page: what the platform keeps, for how long, what it does under subpoena, who the moderators are.
- Publish a clear editorial statement that the platform rates **productions**, not **individuals**, and refuse to host named-person accusations.

## v2 — first expansion (6–12 months post-v1)

**Union credentialing (partner-dependent)**
- First conversation: SAG-AFTRA background performers — most vulnerable cohort with existing institutional overlap.
- Next: IATSE Local 600 (cinematographers), Local 80 (grips), Teamsters 399 (transport/location).
- Integration: signed credential attests "worked ≥N days on production Y" without revealing the worker; credentials are per-production-scoped to prevent farming.
- Non-union fallback stays on moderator-escrow; no workers lose access.

**Identity-escrow layer, narrow scope**
- Applied only to harassment/discrimination individual claims.
- Reviewer's identity sealed with split-key HSM escrow; release only under court order.
- Purpose: gives the reviewer a real legal backstop (platform can credibly say "we don't hand this over without a judge") and gives productions confidence that baseless accusations carry identifiable authorship.
- Optional per-claim; reviewer can file anonymously (counted in aggregate only) or with sealed identity (counted and available for formal reporting).

## v3 and beyond — parallel tracks

**Federated whisper network pilot**
- Parallel product, not a replacement for the public site.
- One city, one trusted coordinator, one vetted member cohort (~50 people).
- Worth building as a hedge for the highest-sensitivity cases where the public-review model is the wrong tool.
- See `federated-whisper.md` for protocol sketch.

**Production response mechanism**
- Productions can post a factual response to their scorecard (not to individual reviews).
- Moderated; response must address concrete claims, not ad hominem.
- Doesn't change the score; sits adjacent to it.

**Aggregate research / press tier**
- Scorecards plus historical data exposed via API to journalists, academic researchers, union research desks.
- Rate-limited; credentialed access; no individual review text.
- Feeds accountability-journalism use case without putting reviewer safety at risk.

## What v1 deliberately excludes

- Rankings, top-10 lists, "worst productions" leaderboards. These increase legal surface disproportionate to user value.
- Named-person accusations, even by consent. Product is about productions as employers, not about individuals.
- Production-facing features (dashboards, paid tiers, PR response tools). Any feature where the production is the customer changes the trust model.
- Integration with job-posting sites (ProductionHub, Staff Me Up) at launch. Useful eventually but raises new complications.

## Open design questions this roadmap does not resolve

Tracked in `questions.md`. The two most load-bearing are (a) publisher vs. connector legal posture — which changes whether the platform is making the scorecard claim or just hosting inputs — and (b) first cohort — which determines whether union-credentialing is a realistic v2 or a speculative one.
