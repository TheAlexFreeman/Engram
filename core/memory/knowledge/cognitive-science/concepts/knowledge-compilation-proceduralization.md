---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - memory/knowledge/cognitive-science/concepts/theory-theory-knowledge-based-view.md
  - memory/knowledge/cognitive-science/concepts/concepts-synthesis-agent-implications.md
  - memory/knowledge/cognitive-science/attention/cognitive-load-theory-sweller.md
  - memory/knowledge/cognitive-science/concepts/basic-level-categories-asymmetry.md
  - memory/knowledge/cognitive-science/concepts/classical-theory-failures.md
---

# Knowledge Compilation and Proceduralization (ACT* Theory)

## Declarative vs. Procedural Knowledge

A foundational distinction in cognitive science and learning:

**Declarative knowledge:** "Knowing that" — information that can be verbally stated, consciously accessible:
- Historical facts: "The Battle of Hastings was in 1066"
- Conceptual knowledge: "An adverb modifies a verb, adjective, or other adverb"
- Autobiographical memory: "I learned to ride a bike at age 7"

**Procedural knowledge:** "Knowing how" — knowledge that enables skilled performance but may not be accessible to verbal report:
- Riding a bike — you cannot fully describe what you do
- Catching a ball — automatic prediction and motor coordination
- Grammar use — native speakers apply rules they cannot state

**Key property:** Declarative knowledge is often acquired quickly but used slowly (requires deliberate retrieval and application). Procedural knowledge is acquired slowly through practice but executed quickly and automatically (see also: System 1 vs System 2, `dual-process-system1-system2.md`).

---

## Anderson's ACT* Theory

**John Anderson's ACT* (Adaptive Control of Thought, asterisk model, 1983)** and subsequent ACT-R (1993) are the most influential computational models of how declarative knowledge is compiled into procedural knowledge through practice.

**ACT* architecture:**
- **Declarative memory:** A network of chunks (facts, episodes) with associative strength that determines retrieval probability.
- **Procedural memory:** A set of *production rules* — condition-action pairs of the form: "IF [current goal is X and working memory contains Y] THEN [execute action Z]".
- **Working memory:** Currently active declarative memory elements.

**Execution of procedural knowledge:** Production rules fire when their conditions are satisfied in working memory. Firing is fast and parallel. Multiple productions may compete; the highest-strength fired.

---

## Knowledge Compilation: The Core Mechanism

**Knowledge compilation** is the cognitive process by which declarative knowledge is transformed into procedural knowledge through practice. It has two sub-processes:

### 1. Proceduralization
Converting declarative knowledge into production rules that no longer need to explicitly retrieve the declarative information.

**Example:**
- **Before proceduralization (novice):** "To apply the rule 'if p → q' and 'p is true', conclude q ..."
  1. Retrieve the rule from declarative memory
  2. Check if the antecedent (p) is true
  3. Apply it to conclude q
  - This requires multiple declarative retrievals and working memory steps

- **After proceduralization (expert):** The entire IF-THEN pattern is compiled into a single production that fires immediately when p is detected, without conscious retrieval of the rule.

**What is lost:** The compiled procedure no longer requires (or even supports) verbal report about why it works. This is why experts often cannot explain their performance — they have compiled their procedural knowledge and lost access to the declarative scaffold.

### 2. Composition
Collapsing a sequence of production rules into a single chunked rule:

- Step 1: IF [goal is to divide fraction A/B by C/D] THEN [invert the divisor to get D/C]
- Step 2: IF [have A/B and D/C] THEN [multiply numerators and denominators]

After composition, these become a single production: IF [goal is to divide fraction A/B by C/D] THEN [directly compute AD/BC]. The intermediate steps vanish.

---

## Chase and Simon: Chess Chunking

**Chase & Simon (1973)** provided the most celebrated demonstration of chunking in expert performance:

**Method:** Chess masters, intermediate players, and novices were briefly shown (5 seconds) chess board positions, then asked to reconstruct the position from memory.

- **Game positions:** Chess masters reconstructed nearly all pieces (26/26); novices remembered ~4-5.
- **Random positions (not from real games):** All groups were equally poor (~4-5 pieces).

**Interpretation:** Chess masters do not have better visual memory in general. They have compiled **chunks** — familiar positional patterns from thousands of games of study — stored in long-term memory. A "castled king position with a fianchettoed bishop" is one chunk, retrieved with one retrieval. Novices see 16 individual pieces; masters see 6-8 chunks encoding the same information.

**Expert memory as compiled declarative knowledge:** The master's declarative knowledge (every position from thousands of games) has been compiled into a retrieval-efficient chunk structure. Accessing these chunks is proceduralized — the eye falls on a configuration and the chunk is retrieved automatically.

---

## Implications for Agent Knowledge Files

**The `knowledge/` folder as declarative memory:** The agent's knowledge base corresponds to ACT*'s declarative memory — an explicit, verbally statable network of factual and conceptual chunks.

**The `core/memory/skills/` folder as procedural memory:** If the agent system includes procedural files (step-by-step protocols, decision trees, reflexive patterns of behavior), these correspond to compiled production rules — the procedural complement to declarative knowledge files.

**Risk of premature compilation:** In human learning, compiling incorrect declarative knowledge into production rules is a major hazard — the incorrect procedure fires rapidly and automatically, resisting correction precisely because it is no longer running through declarative check steps. The analogous risk for an agent system:
- Frequent patterns of action (treated as "how we always do this") that were based on incorrect or outdated declarative knowledge
- "Compiled habits" in agent behavior that are never surfaced to re-examination because they work smoothly

**Mitigation:** Periodic review (human or automated) that re-examines whether commonly-applied behavioral patterns are still consistent with the current declarative knowledge base. In ACT* terms: periodically "decompile" a procedural pattern (ask: what is the declarative justification for this action?) and verify it against current declarative memory.

**Verification before deep compilation:** Before adding a concept to a high-confidence synthesis file (the closest analog to deeply compiled procedural knowledge), verify it carefully. Files with `trust: high` are analogous to compiled productions — they are used quickly and confidently, but updating them requires special effort.

**Chunking and file granularity:** Chase and Simon's chunking result implies that the agent benefits from files that represent complete coherent chunks — like a chess master seeing patterns — rather than isolated atomic facts. Files that encode a complete theoretical framework with its exemplary applications, evidence, and implications (as the files in this knowledge base attempt to do) are better chunks for retrieval than single-sentence fact files.
