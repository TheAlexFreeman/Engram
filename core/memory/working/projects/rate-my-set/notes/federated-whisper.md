---
type: project-note
project: rate-my-set
topic: federated-whisper-network
created: 2026-04-14
session: memory/activity/2026/04/14/chat-001
status: exploration
---

# Federated whisper network — design exploration

A parallel product to the public review site. The whisper model accepts that the industry already shares this information informally — through Signal chats, ADs texting each other, "avoid this show" whispers — and asks what the *lightest* infrastructure is that formalizes that pattern without turning it into a publishing platform.

The design priority is not scale. It is **not leaking**. Everything else — search, discoverability, ranking — is optional and mostly undesirable.

## Roles

**Worker** — a vetted cast or crew member who can both submit observations about productions they have worked on and request information about productions they are considering.

**Coordinator** — a trusted human who maintains a local cohort of vetted workers, receives attestations from that cohort, and answers queries from workers (their own or, under defined conditions, other coordinators' workers). Coordinators are the core trust primitive; the whole system's integrity reduces to coordinator integrity.

**Federation** — the (loose) network of coordinators that exchange attestations and queries across cohorts, under rules each coordinator sets.

Not roles: a platform, a company, an admin. The whole architecture is designed so that no central party exists with aggregate knowledge.

## Core operations

Four primitives cover almost everything:

**ATTEST** — a worker tells their coordinator about a production they worked on. Attestation includes production identifier, dates worked, department/role, and a short structured + freeform report. Attestation is signed (in the PGP or minisign sense) by a key the coordinator issued to that worker.

**QUERY** — a worker asks their coordinator about a production. Coordinator checks their local attestation store; if sufficient attestations exist (k ≥ threshold), coordinator synthesizes a summary. If not, coordinator either (a) returns "insufficient data," (b) forwards the query to federated coordinators who may have attestations, or (c) declines to forward based on sensitivity.

**PROPAGATE** — coordinator-to-coordinator sharing of attestations, summaries, or queries. Always governed by an explicit policy — not automatic. A coordinator may share aggregate signal while withholding individual attestations, or share with some federation peers but not others.

**PURGE** — any attestation can be revoked by its author or expired by policy. Attestations have a default TTL (e.g., 24 months) after which they drop off queries. No permanent archive.

## Trust model

The hard part. Coordinators need to be trusted by workers (to not leak), by each other (to not inject fake attestations), and by the public (to the extent the network has any public-facing surface at all).

Three reasonable starting points for coordinator selection:

**Union-adjacent** — coordinators are nominated by unions or guilds. SAG-AFTRA background reps, IATSE local officers, DGA trainees. Gives an existing institutional trust anchor, at the cost of excluding non-union workers unless a parallel path exists.

**Journalism-adjacent** — coordinators are or work with established entertainment journalists who already handle sensitive industry sources. Gives strong source-protection discipline and existing legal infrastructure (shield laws, attorneys).

**Community-elected** — within an initial seed cohort, members vote up coordinators from among themselves. Slow to bootstrap, but the most legitimate if you can get through the first 6 months.

In practice, v1 is probably a handful of hand-picked coordinators in LA, NY, Atlanta, and maybe Albuquerque — nominated by you, vetted by references, bonded and NDA'd. The federation grows by referral.

Workers trust coordinators via a simple credential: the coordinator issues a signing key to each vetted worker in their cohort. Vetting is in-person or high-bandwidth (video call with ID check against SAG-AFTRA / IATSE / payroll records, plus two references from existing cohort members). The key is the only persistent identifier — no email, no name in the system.

Coordinators trust each other via an explicit federation list: each coordinator publishes a list of peer coordinators whose attestations they accept. The list can be asymmetric — A accepts B's attestations, but B does not accept A's. New coordinators enter by introduction, never by self-assertion.

## Message types (sketch)

An ATTEST message has roughly this shape:

```
---
type: attest
version: 1
key_id: <worker's signing key fingerprint>
coordinator: <coordinator who issued the key>
production:
  identifier: <show name, code name, or union signatory number>
  dates: [<start>, <end>]  # may be approximate
  role_class: background | day-player | principal | crew | other
  department: <optional, only if reviewer chooses to include>
scores:
  professionalism: 1-5
  safety: 1-5
  food: 1-5
  compensation: 1-5
  overall: 1-5
flags:
  harassment_observed: true | false
  discrimination_observed: true | false
  injury_observed: true | false
notes: |
  <freeform, max 500 words, sanitization applied by coordinator before propagation>
ttl: 24mo
signed_at: <timestamp>
signature: <Ed25519 over canonical form>
```

A QUERY message:

```
---
type: query
version: 1
key_id: <worker's signing key fingerprint>
coordinator: <coordinator to query>
production:
  identifier: <show or code name>
  date_range: <optional>
requested_detail: summary | flags_only | aggregate_score
propagate_policy: local_only | federation_ok
signed_at: <timestamp>
signature: <signature>
```

A RESPONSE is deliberately minimal — it preserves only what the requester actually needs:

```
---
type: response
version: 1
in_reply_to: <query signature hash>
coordinator: <responding coordinator>
production: <identifier as queried>
attestation_count: <integer, ≥ threshold or "insufficient">
aggregate:
  professionalism: <mean, only if N ≥ threshold>
  safety: <mean>
  ...
flags:
  harassment_reported: <count if N ≥ threshold, else "redacted">
  discrimination_reported: <count if N ≥ threshold, else "redacted">
summary_text: |
  <coordinator-authored synthesis, optional, only for summary-level queries>
freshness: <most-recent-attestation date, rounded to month>
signed_at: <timestamp>
signature: <coordinator signature>
```

No individual attestations ever cross coordinator boundaries. Only aggregates, and only above k-threshold.

## Propagation policy

Several policies worth naming so they can be chosen per federation-edge:

**Local-only** — the coordinator will answer queries from their own cohort only. Federated queries get "declined." Strongest privacy, lowest coverage.

**Aggregates-out** — the coordinator answers federated queries with aggregate numbers only, never synthesized text. Trades some richness for tight disclosure control.

**Summaries-out** — the coordinator will author and share short synthesized summaries with federation peers, but never raw attestations.

**Peered-trusted** — with a specific peer coordinator, the coordinator will share raw attestations (still signed, still pseudonymous). Used between coordinators who trust each other enough to pool data. Rare; requires explicit agreement.

The default new-federation-edge starts at local-only and escalates by mutual consent.

## Transport

Three viable starting points, in increasing order of sophistication:

**Email-first MVP** — attestations and queries are PGP-signed emails to a dedicated coordinator address. Coordinator maintains a local spreadsheet or SQLite DB. Responses are PGP-signed replies. Requires no platform, no server, no code. A small team of coordinators could bootstrap the network in a weekend using existing tools. The bottleneck is coordinator time, which is honest — the cost is real and visible, and keeps the system from scaling past trust.

**Signal/Matrix group-chat protocol** — each coordinator runs a closed group chat. Members submit attestations as structured messages (a bot parses them). Queries are handled manually by the coordinator. Federation happens by coordinators inviting each other to a cross-coordinator channel. Better UX, same trust model, more moving parts.

**Dedicated federated server (long-term)** — each coordinator runs a small server implementing the message types above. Servers federate peer-to-peer using ActivityPub-style pull, or a custom signed-JSON-over-HTTPS protocol. Offers the smoothest UX and allows structured queries, at the cost of operational complexity and a real attack surface on each server.

I'd start with email-first. The whole point is that this isn't a product — it's a coordination pattern. Making it ugly to use at scale is a feature; it forces the trust model to stay strong.

## Failure modes worth naming

**Rogue coordinator** — leaks their cohort, either maliciously or via compromise. Blast radius: one cohort, typically 30-100 people. Partial mitigation: federation peers can revoke trust quickly; workers can move to a different coordinator. Still the worst single-point failure in the system.

**Slow-drip deanonymization** — attacker submits repeated queries about productions with small crews, cross-references with public call sheets and social media, triangulates. Mitigation: coordinators rate-limit and log queries; federation peers share suspicious-query patterns.

**Coordinator capture** — production PR firm gets a friendly coordinator installed. Mitigation: coordinator selection has to stay out of PR firms' hands; federation trust list visible to members; members can name-and-shame by withdrawing attestations.

**Sybil at the worker layer** — someone obtains multiple worker credentials from different coordinators. Harder to detect than at platform layer because no central registry. Mitigation: coordinator vetting (in-person / video) is the main defense; federation-level de-duplication via fingerprint hashing with hash-collision-resistant canonical identifiers is possible but requires federation cooperation.

**Federation fragmentation** — two coordinators fall out; their cohorts lose visibility into each other. Not really a bug, more a feature — it means trust decisions have real consequences. But it degrades coverage over time if unchecked.

## What this is not

- Not a replacement for the public site. Different user needs.
- Not scalable to millions of users. The cost of vetting and the reliance on coordinator time bound the system at probably 10-20k total participants across the federation.
- Not a whistleblower platform. This is for routine "should I take this job" decisions. Actual harassment/discrimination reporting should go to channels designed for that (union grievance, EEOC, dedicated whistleblower services).
- Not anonymous in a cryptographic-maximalist sense. Coordinators know who their cohort members are. The privacy guarantee is narrow: productions and the public don't know.

## Open questions

- Do coordinators receive compensation? If so, by whom? (Unions, foundations, worker-funded dues?) Any paid-coordinator model introduces capture risk; any volunteer model has sustainability risk.
- Does the network have any legal entity, or is each coordinator independently liable? The former gives shared legal defense; the latter gives smaller attack surface per-coordinator.
- What's the relationship, if any, to the public site? Same-platform with two surfaces, or completely separate products with no shared code?
- Federation as a trust fabric may invite attempts to decentralize further (self-sovereign identity, Web3-style systems). I think that direction is worse on every axis — it weakens the trust model by removing the coordinator-as-human-filter — but it's worth being explicit about rejecting it.
