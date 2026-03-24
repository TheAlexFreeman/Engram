---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: conceptual-hygiene-interdisciplinary.md, gardenfors-conceptual-spaces.md, ../relevance-realization/representational-change-theory-ohlsson.md
---

# Conceptual Change: Types and Mechanisms

## The Problem of Learning That Breaks Old Frameworks

Not all learning is additive. Some learning requires not merely adding new information to existing schemas but **restructuring or replacing prior conceptual frameworks**. This is *conceptual change* — learning that breaks, repairs, or replaces prior representational structures.

Conceptual change is crucially important for:
- Science education (getting students past misconceptions)
- Expert development (novice → expert restructuring)
- Scientific progress (paradigm shifts)
- Knowledge base maintenance (updating incorrect or superseded claims)

Three main theoretical traditions are covered here: Chi's ontological category analysis, Vosniadou's framework theory approach, and Kuhn's paradigm-shift model.

---

## Chi's Taxonomy: Accretion, Revision, and Kind-Shift

**Michelene Chi** (1992, 2005, 2008) proposes that conceptual change comes in three types based on what is required:

### 1. Accretion
**Definition:** Adding new facts, examples, or concepts to an existing schema, with no structural change to the underlying categorical framework.

- **Example:** Learning that titanium is a metal (adding a new instance to a pre-existing "metals" category)
- **Mechanism:** Simple encoding; no conflict with prior knowledge
- **Difficulty:** Low — standard learning
- **Most knowledge acquisition is accretion**

### 2. Revision (Within-Category)
**Definition:** Changing specific features or properties attributed to a concept or category, without changing the ontological kind the concept belongs to.

- **Example:** Learning that the Earth is not the exact centre of the solar system, but rather both Earth and Sun orbit a common centre of mass (though the sun is very close to that centre). This revises orbital mechanics without changing the ontological category (both objects remain "physical bodies under gravity").
- **Mechanism:** Updating specific feature values in a schema; requires noticing a conflict and correcting it
- **Difficulty:** Medium — requires detecting inconsistency

### 3. Category (Kind) Shift — Ontological Re-categorization
**Definition:** The concept must be moved from one ontological category to another — a *kind* change, not just a feature change.

- **Example:** **Heat is not a substance (caloric fluid); heat is a process (kinetic energy of molecular motion).** Prior to 19th-century thermodynamics, heat was categorized as *matter* — a substance that flows from hot objects to cold ones (caloric theory). The correct ontology categorizes heat as a *process* — energy transfer — not a substance at all.
- **Example 2:** **Electricity is not a flowing substance; it is a flow of charge carriers.** Early "fluid" models of electricity were ontologically wrong — electricity is not like water.
- **Example 3:** **Light is not a particle or a wave; it is a quantum object that exhibits both wave-like and particle-like behaviors depending on measurement context.** No classical object category fits.

**Mechanism:** Requires noticing that current category assignment generates systematic contradictions, and constructing a new ontological category or reassigning to a different existing one.

**Difficulty:** High — hardest form of conceptual change, most resistant to teaching, most likely to fail.

**Chi's ontological tree:** Chi proposes that concepts are organized in an **ontological tree** — a hierarchy of kinds:
- MATTER (substances, objects, materials)
- PROCESSES (events, causes, mechanisms)
- MENTAL STATES (intentions, emotions, representations)

Category shifts involve moving a concept from one major branch to another. Since the branches have different constraints, causal properties, and features, this reorganization propagates throughout the conceptual system.

---

## Vosniadou's Framework Theory Approach

**Stella Vosniadou** (1992, 2008) uses a two-tier architecture:

**Framework theories:** Deeply held, often implicit background assumptions about a domain that are acquired early and form the scaffolding for subsequent knowledge acquisition.

- "Objects fall toward the ground"
- "Objects are solid and bounded"
- "Space is absolute"
- "Time flows uniformly"

**Specific theories:** More explicit, revisable beliefs built within the framework theory's constraints.

**The key insight:** When children learn new scientific concepts, they often **assimilate them into the wrong framework theory**, producing **synthetic models** — coherent-seeming hybrid models that blend scientific vocabulary with pre-scientific ontological constraints.

**Example — The Earth's shape:**
- Adult scientific model: The Earth is a sphere floating in space; "down" is toward Earth's center.
- Children know the Earth is "round" (taught in school) but also *know from experience* that the ground is flat and "down" is a fixed direction.
- Synthetic models produced: The Earth is a flat disc with a round shape. / The Earth is hollow inside with people living on the flat inside surface. / The Earth is round, but people live on the flat part on top.

These are not pure ignorance — they are semi-sophisticated attempts to reconcile new scientific information with the prior framework theory about flat ground and absolute down. The framework theory acts as a filter.

**Implications for teaching:** Surface correction ("the Earth is round") is insufficient when the framework theory is incompatible with the correct concept. Deep framework change requires sustained engagement that makes the framework theory explicit and contradictory.

---

## Kuhnian Paradigm Shifts: Conceptual Change at Scale

**Thomas Kuhn** (1962, *The Structure of Scientific Revolutions*) described **scientific revolutions** as macro-level conceptual changes in research communities:

**Normal science:** Research conducted within an accepted paradigm — a shared framework of assumptions, exemplars, instruments, and problems. Puzzles are solved within the paradigm.

**Anomalies:** Observations that resist solution within the current paradigm accumulate. Most anomalies are initially set aside or explained away.

**Crisis:** Sustained failure to solve important anomalies triggers a crisis in the scientific community — growing awareness that the paradigm is inadequate.

**Scientific revolution:** A new paradigm is proposed that can solve the crisis anomalies. The old paradigm is abandoned (or relegated to a special case) and the new one is adopted — but not by logical proof. The paradigm shift is partly sociological (new generation of scientists trained in the new framework).

**Incommensurability:** Kuhn's most controversial claim — old and new paradigms are not fully translatable into each other. "Mass" means something different in Newtonian vs. Einsteinian physics. Scientists in different paradigms partly talk past each other because their conceptual frameworks carve reality differently.

**Connection to Chi's kind-shift:** Kuhnian paradigm shifts are, at the individual level, ontological kind-shifts applied across an entire domain simultaneously.

---

## Agent Knowledge Base Implications

**Classification of knowledge updates by type:**

Most knowledge additions to the agent memory system are **accretion** — they add new files, new facts, new examples. These are low-risk and low-conflict.

Some knowledge updates are **revisions** — a more careful analysis replaces a previously filed claim. These should be logged explicitly (note what was changed and why) in the updated file's frontmatter.

The most dangerous knowledge events are **kind-shifts** — when a concept filed in one ontological category needs to be reassigned. These are rare but high-stakes:
- A filed *fact* turns out to be a *simplification* (revision is usually sufficient)
- A filed *mechanism* turns out to be the wrong kind of mechanism (may require kind-shift)
- A core categorization assumption (e.g., "all model uncertainty is epistemic") turns out to be ontologically wrong (requires restructuring many cross-references)

**Detecting needed kind-shifts:** Signs that a kind-shift may be required:
1. Accumulated exceptions and special cases that keep requiring patches
2. Cross-reference conflicts — two files claim incompatible things about the same phenomenon
3. A new theoretical framework is adopted that classifies the phenomenon differently

**Handling kind-shifts:** When a kind-shift is detected, the correct process is:
1. Identify which files make claims from the old ontological framework
2. Create a new file representing the correct framework
3. Update each affected file with a note: "Prior categorization was as [X]; this is now revised to [Y]"
4. Update SUMMARY.md to reflect the change
5. Flag for human review (trust level: reconsidering)
