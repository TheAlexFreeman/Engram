---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - memory/knowledge/cognitive-science/concepts/conceptual-hygiene-interdisciplinary.md
  - memory/knowledge/cognitive-science/concepts/gardenfors-conceptual-spaces.md
  - memory/knowledge/cognitive-science/concepts/conceptual-change-types.md
  - memory/knowledge/philosophy/cognitive-linguistics-metaphor-blending.md
  - memory/knowledge/cognitive-science/concepts/classical-theory-failures.md
---

# Structural Alignment and Analogy (Gentner's Structure-Mapping Theory)

## Analogy as Cognitive Engine

Analogy — reasoning from one domain to another via structural similarity — is one of the most powerful and pervasive tools in human cognition. It underlies:
- Scientific discovery (the atom as a solar system; electrical circuits as water flow)
- Problem solving (solve a new problem by analogy to a solved one)
- Language (metaphors, conceptual metaphors — "argument is war")
- Learning transfer (understanding fractions by analogy to division)
- Creative design (basing new products on the structure of existing ones)

**Dedre Gentner** developed **Structure-Mapping Theory** (SMT) as the most influential formal account of analogical reasoning.

---

## Structure-Mapping Theory (Gentner, 1983)

**Core claim:** Analogy is the **mapping of relational structure from a source domain to a target domain**, with higher-order relations (relations among relations) taking priority over object attributes.

**Key distinctions:**

| Type | Example (solar system → atom) | Psychological Status |
|-------|-------------------------------|---------------------|
| **Attribute match** | "Both are circular" | NOT analogical; object-level |
| **Relational match** | "Electron revolves around nucleus, as planet revolves around sun" | Analogical |
| **Higher-order relational match** | "The revolution is caused by gravitational attraction (in solar system) = electrical attraction (in atom)" | Deeply analogical |

**The systematicity principle (Gentner, 1983):** When multiple relational structures can be mapped from source to target, humans prefer the mapping that preserves **higher-order relations** — those that form a **connected relational system.** A single isolated relation is less compelling as an analogy than a web of mutually consistent relations.

- "Molecules in a gas are like billiard balls" — compelling because the entire mechanical causal structure (elastic collisions, momentum conservation, force transmission) maps systematically.
- "Molecules and billiard balls are both hard" — just an attribute match; not a real analogy.

---

## The Structure-Mapping Engine (SME)

Falkenhainer, Forbus & Gentner (1989) implemented Structure-Mapping Theory as a computational model: the **Structure-Mapping Engine (SME)**.

**SME algorithm:**
1. **Local match generation:** Find all pairs of predicates (relations, attributes) that can be aligned between source and target.
2. **Coalescence into mappings:** Merge locally consistent matches (structurally consistent, no element mapped to two things) into global interpretations (complete mappings).
3. **Evaluation by structural consistency + systematicity:** Score each global mapping by the number of predicates mapped, the depth of relational structure connected, and the higher-order relations preserved.
4. **Candidate inferences:** Propositions that are true in the source and connected to the matched structure, but not yet known in the target, are **candidate analogical inferences** — predictions made by the analogy.

**Candidate inferences** are crucial: the analogy doesn't just say "these are alike" — it generates new predictions. If the solar system model is matched to the atom, candidate inferences (that electrons have discrete angular momentum — Bohr model) can be tested.

---

## Analogy Failure: Surface vs. Relational Matching

**Novice-expert differences in analogy (Chi et al., 1981 revisited):**
- Novices sort physics problems by surface features (both problems have inclined planes → same category → same solution method)
- Experts sort by underlying relational structure (both problems instantiate conservation of energy → same solution structure)

**Surface matching is the failure mode:** When reasoners map analogies by surface features (both source and target have big round things) rather than by relational structure (force patterns, causal relations), the analogy:
- Generates wrong candidate inferences
- Transfers incorrect heuristics
- Creates false confidence in a faulty model

**Analogy in text:** Metaphors that pick up on only attribute match ("the sun is a golden coin") are decorative. Metaphors that preserve relational structure ("the sun is the star that all other stars orbit around" — no wait, the sun doesn't orbit) are scientifically useful when applied to novel domains.

---

## Cross-Reference Quality as Structural Alignment

A key application of structure-mapping to knowledge organization:

**A cross-reference is good when it preserves relational structure, not merely surface topical similarity.**

**Weak cross-reference (attribute match):**
> "See also: dual-process-system1-system2.md — also a model of human cognition"

This is surface-level (both are cognitive science models) — it does not tell the reader how the concepts structurally relate.

**Strong cross-reference (relational match):**
> "The metacognitive monitoring → control loop (see `metacognitive-monitoring-control.md`) is structurally analogous to the error correction loop in executive function (see `executive-functions-miyake-unity-diversity.md`): in both cases, a monitoring signal (conflict signal / JOL mismatch) triggers a control adjustment (suppression / re-study allocation). The systematic principle is negative-feedback regulation of a higher-level goal."

This cross-reference maps relational structure: monitoring → signal → control → adjustment. It is a structure-mapping between two knowledge areas, and it generates a candidate inference: if something disrupts the monitoring → control link in executive function, it should disrupt analogous calibration processes in metacognition.

**Actionable rule for cross-references:** When writing a cross-reference in a knowledge file, articulate the **shared relational structure** between the two concepts, not just the surface topical overlap.

---

## Structural Alignment and Similarity

Gentner and Markman (1994) extended SMT to ordinary similarity judgments (not just classic analogies):

- **Literal similarity** = high attribute match + high relational match ("My cat and your cat are similar")
- **Analogy** = low attribute match + high relational match ("The atom is like the solar system")
- **Mere appearance match** = high attribute match + low relational match ("Two red chairs look alike")
- **Anomaly/dissimilarity** = low on both ("A banana and a prime number")

This creates a **2×2 space of similarity** with different cognitive roles for each quadrant.

**Structural alignment also reveals differences:** Comparing two nearly-similar things highlights their point of difference — the *alignable difference* (both have eyes; source has blue eyes, target has green eyes → the eye colour gets highlighted). This explains why analogical comparison is a powerful learning tool: it draws attention to systematically important differences.

---

## Agent Implications: Knowledge as Structural Map

**The knowledge base as analogy network:** Files that cross-reference each other with strong structural analogies form a **relational network** — the knowledge-space equivalent of Gärdenfors' conceptual space structure but encoded explicitly in cross-reference prose rather than implicitly in embedding vectors.

**Quality assurance for cross-references:** A useful self-check when writing cross-references: "Can I state the *shared relational schema* between these two files?" If yes, it's a structural alignment cross-reference. If no, it may just be "both are about cognition" (surface match) — still worth linking, but less important.

**Transfer as analogical inference across the knowledge base:** When the agent applies knowledge from one file to solve a problem in a different domain, it is performing analogy. The quality of that transfer depends on whether the structural relations in the source (not just the surface features) are preserved in the mapping to the target problem. This is a key mechanism for the synthesis files (`*-synthesis-agent-implications.md`) within each topic cluster.
