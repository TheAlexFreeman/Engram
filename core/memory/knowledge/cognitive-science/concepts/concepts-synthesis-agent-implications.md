---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - memory/knowledge/cognitive-science/attention/attention-synthesis-agent-implications.md
  - memory/knowledge/cognitive-science/metacognition/metacognition-synthesis-agent-implications.md
  - memory/knowledge/cognitive-science/memory/reconsolidation-agent-design-implications.md
  - memory/knowledge/cognitive-science/concepts/basic-level-categories-asymmetry.md
  - memory/knowledge/cognitive-science/concepts/embodied-grounded-cognition-concepts.md
---

# Concepts and Categorization: Synthesis and Agent Implications

## Overview of the Concepts Research Arc

This file synthesizes the findings from ten files covering the cognitive science of concepts and categorization, deriving design principles for the agent memory system. The files in the cluster are:

| File | Core Contribution |
|------|------------------|
| `classical-theory-failures.md` | Categories are not defined by necessary/sufficient features; family resemblance, natural kinds, open texture |
| `prototype-theory-rosch.md` | Graded membership, typicality effects, basic level as privileged, ad hoc categories |
| `exemplar-theory-hybrid-models.md` | Classification via stored instances (GCM), double dissociation from prototyping, dual-system models |
| `theory-theory-knowledge-based-view.md` | Conceptual coherence comes from causal theory, not similarity; essentialist folk biology; expert reorganization |
| `gardenfors-conceptual-spaces.md` | Geometric representation: quality dimensions, convex regions, prototype as centroid, similarity as distance |
| `embodied-grounded-cognition-concepts.md` | Sensorimotor grounding; Barsalou's simulators; LLM grounding gap; fluency-grounding dissociation |
| `structural-alignment-analogy.md` | Analogy = relational structure mapping; systematicity; candidate inferences; cross-reference quality |
| `conceptual-change-types.md` | Accretion / revision / ontological kind-shift; Vosniadou framework theories; Kuhnian paradigm shifts |
| `knowledge-compilation-proceduralization.md` | ACT* declarative → procedural compilation; chunking; premature compilation risk; decompilation review |
| `basic-level-categories-asymmetry.md` | Basic level is psychologically privileged; info-theoretic optimum; expert shift; file granularity guide |
| `conceptual-hygiene-interdisciplinary.md` | Polysemy risk; framing effects from source domains; structural alignment as cross-domain criterion |

---

## Four Competing Accounts and What Each Gets Right

The classical, prototype, exemplar, and theory-theory accounts are sometimes framed as competitors but more accurately represent **complementary mechanisms** that dominate at different scales and contexts:

| Account | What it captures | Primary domain |
|---------|-----------------|----------------|
| **Classical theory** | Necessary/sufficient definitions; logical category membership | Mathematics, legal definitions, formal systems |
| **Prototype theory** | Graded typicality; first impressions; large-category navigation | Common objects; rapid natural language reference |
| **Exemplar theory** | Specific memory traces; learning from instances; rare-category performance | Early learning; expert classification of specific cases |
| **Theory-theory** | Expert categorical coherence; inductive potency; deep explanation | Scientific concepts; biological kinds; causal reasoning |

**What this implies for the knowledge base:** Different file clusters will be organized according to different conceptual accounts. Mathematical and formal knowledge files (e.g., in `formal-logic/`) benefit from classical-theory thinking — definitions matter, edge cases should be handled. Scientific knowledge files (e.g., in `cognitive-science/`) benefit from theory-theory thinking — files should encode causal-relational structure, not just feature lists. Navigation and retrieval interfaces are best designed with prototype theory in mind — surface typicality cues help orient retrieval.

---

## The Geometry Underneath: Gärdenfors Integration

Gärdenfors' conceptual spaces framework provides a **geometric interpretation** that partially unifies the four accounts:

- **Prototype theory** = concept as centroid of a convex region
- **Exemplar theory** = concept as set of exemplar points; classification by nearest-neighbor distance
- **Boundary behavior** = Voronoi tessellation; boundary items are equidistant from two centroids
- **Theory-theory** = the *dimensions* of the space are not arbitrary; they are determined by causal theories about what distinctions matter

The geometric framework also bridges to **LLM embedding spaces** — the agent's implicit representational geometry — providing the most principled account of how the agent's approximate conceptual representations relate to human psychological conceptual structures.

---

## Five Key Design Principles Derived from Concepts Research

### Principle 1: File Granularity at Basic Level

Write knowledge files at the **basic level of abstraction** — the level where content is both distinctive and rich. Too-coarse files are vague; too-fine files explode into unmanageable specificity. As the knowledge base grows denser in a domain, the effective basic level shifts down, justifying more specific sub-files.

*Source: `basic-level-categories-asymmetry.md`*

### Principle 2: Organize by Causal Structure, Not Surface Topic

Cross-references and category assignments should track **causal and explanatory relationships**, not just surface topical similarity. A cross-reference should be able to state the relational schema it instantiates (not just "also about cognition").

*Source: `theory-theory-knowledge-based-view.md`, `structural-alignment-analogy.md`*

### Principle 3: Distinguish Knowledge Update Types

Recognize when a knowledge update is **accretion** (add new file), **revision** (update existing file), or **kind-shift** (reconceptualize an ontological category). Kind-shifts require explicit flagging, propagated review of related files, and human validation.

*Source: `conceptual-change-types.md`*

### Principle 4: Compile Carefully; Decompile Periodically

High-trust, frequently accessed declarative knowledge acts like compiled procedural knowledge — fast, automatically applied, resistant to correction. Periodic review should "decompile" key claims by re-asking: what is the declarative justification? Is it current?

*Source: `knowledge-compilation-proceduralization.md`*

### Principle 5: Manage Polysemy Explicitly

When borrowing terms from other disciplines, state the domain-specific sense in the file, note known competing senses, and use structural alignment to assess whether a cross-disciplinary mapping is warranted by shared relational structure.

*Source: `conceptual-hygiene-interdisciplinary.md`*

---

## The Knowledge Base as Conceptual System: Meta-Analysis

**What kind of conceptual system is this knowledge base?**

The knowledge base is a **hybrid prototype-theory / theory-theory system:**
- Files within a folder form a prototype cluster: they share features (same `trust` level, same general topic domain, similar format), and the center of that cluster (the synthesis file, the most typical examples) is most readily accessible.
- Cross-references between files encode theory-like causal-relational structure: the richer the causal and explanatory relations spelled out in cross-references, the more the knowledge base behaves like a folk theory of its domain rather than a feature-based category system.

**The grounding gap as a persistent constraint:** All knowledge in this system is linguistically mediated. Embodied cognition research (see `embodied-grounded-cognition-concepts.md`) establishes that linguistic representations systematically miss sensorimotor-grounded knowledge. This is an intrinsic limitation, not a correctable deficiency.

**The metacognition connection:** The quality of categorical organization in the knowledge base is itself a **metacognitive variable** — a higher-level question about how well the knowledge base represents what it purports to represent. The calibration files (see `metacognition/calibration-overconfidence-hard-easy.md`) apply: the system should have calibrated uncertainty about its categorical organization, not assume it has found the optimal categorization.

---

## Open Questions

1. **How does the effective basic level shift as the knowledge base grows?** Should sub-folder structure be reorganized when depth of coverage crosses a threshold?

2. **Can kind-shifts in the knowledge base be detected automatically?** Indicators: sustained accumulation of revision-patches on one file, semantic clustering analysis of cross-references, flagging by human review.

3. **How should interdisciplinary files be categorized** when they are equally at home in two different subfolders? Current practice: pick one and add a cross-reference from the other relevant folder's SUMMARY.md.

4. **Does the convexity constraint hold for knowledge folder structure?** Is `cognitive-science/concepts/` a convex region — or are there files that belong "between" concepts and the philosophy folder?

---

## Related Files

- `knowledge/cognitive-science/attention/attention-synthesis-agent-implications.md`
- `knowledge/cognitive-science/metacognition/metacognition-synthesis-agent-implications.md`
- `knowledge/cognitive-science/cognitive-science-synthesis.md`
- `knowledge/cognitive-science/memory/working-memory-baddeley-model.md`
- `core/governance/curation-policy.md` (on trust levels and file management)
- `core/governance/update-guidelines.md` (on when to revise vs. create new files)
