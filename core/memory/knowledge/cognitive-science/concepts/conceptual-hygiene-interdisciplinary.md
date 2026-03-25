---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - memory/knowledge/cognitive-science/concepts/structural-alignment-analogy.md
  - memory/knowledge/cognitive-science/concepts/gardenfors-conceptual-spaces.md
  - memory/knowledge/cognitive-science/concepts/concepts-synthesis-agent-implications.md
  - memory/knowledge/cognitive-science/concepts/conceptual-change-types.md
  - memory/knowledge/philosophy/cognitive-linguistics-metaphor-blending.md
---

# Conceptual Hygiene in Interdisciplinary Work

## The Polysemy Problem Across Disciplines

Natural language concepts are typically **polysemous** — the same word form carries multiple related but distinct meanings across different contexts and disciplines. This creates severe confusion in interdisciplinary work when researchers from different fields use the same term to mean different things.

**High-stakes polysemous terms in this knowledge base:**

| Term | Cognitive Science Meaning | Machine Learning Meaning | Philosophy Meaning |
|------|--------------------------|--------------------------|-------------------|
| **Schema** | Mental structure organizing experience (Bartlett, Piaget) | Structured data format (JSON schema, DB schema) | (Rarely used; "concept" or "category" preferred) |
| **Representation** | Mental/neural state standing in for something | Numeric encoding (embedding, one-hot vector) | Intentional content; something "about" something |
| **Belief** | Mental state with propositional content; held to be true | Probability distribution or confidence score | Propositional attitude; subject to normative evaluation |
| **Attention** | Selective processing of stimuli (cognitive resource) | Weighted aggregation of key-value memory (transformer component) | Phenomenal "aboutness"; intentionality |
| **Memory** | Encoding, storage, retrieval of experience | Training data; fine-tuning; retrieval-augmented memory | "Memory" in philosophy of mind = very similar to cog sci |
| **Category** | Mental kind; concept | Data type or class in programming; classifier output | Ontological kind; entity class |
| **Grounding** | Sensorimotor-experiential basis for meaning | Connecting model outputs to external facts (factual grounding) | Reference; what makes a term refer |
| **Inference** | Logical or probabilistic conclusion from evidence | Forward pass through a model; a model call | Logical step from premises to conclusion |

**The core danger:** When reading a paper or filing knowledge across disciplines, silently adopting one discipline's usage while the term carries a different meaning in context produces **systematic misinterpretation** — errors that are hard to detect because the key word is the *same*.

---

## The Latent Scope Fallacy

The **latent scope fallacy** (Keil et al., 2003; though the precise term appears in various forms): the tendency to treat concepts as if they have sharp edges and complete determinate extension, even when the concept is inherently vague or context-sensitive.

**Manifestation in knowledge files:**
- Writing a file "What is a concept?" that implies a single determinate answer, when the field has genuinely competing views (classical, prototype, exemplar, theory-theory, conceptual spaces) each of which captures different aspects
- Filing something under one category as though there is one correct category, when reasonable domain experts would place it differently

**Hygiene implication:** When a concept spans multiple frameworks or has domain-specific variants, the knowledge file should explicitly acknowledge the variation:
- State the domain of the current usage (cognitive science, machine learning, philosophy)
- Note the other senses explicitly
- Do not resolve cross-disciplinary ambiguity by deciding on "one true meaning"

---

## Framing Effects from Source Domain

When a concept migrates from its source domain to a new domain, it carries **framing effects** — implicit connotations, assumptions, and metaphors from the source domain that may or may not apply in the target domain.

**Attention (cognitive science → ML):**
- In cognitive science, attention is *selective, limited-capacity, biologically evolved for ecological perception*.
- In ML, "attention" (transformer attention) is *none of these things*: unlimited capacity in parallel, trained by gradient descent, not evolved.
- The term "attention" in ML was chosen as a suggestive analogy (see `transformer-attention-vs-human-attention.md`), but the framing risk is that cognitive science concepts about *human* attention (vigilance decrements, attentional blink, limited capacity) are implicitly assumed to apply to transformer attention — often incorrectly.

**Memory (human → agent):**
- Human memory involves encoding, consolidation, retrieval with biological forgetting curves.
- Agent memory (this knowledge base) is read/write file storage with no biological forgetting, no consolidation sleep, no priming, no tip-of-tongue states.
- Framing the agent memory system using cognitive science memory metaphors (as this system deliberately does for design heuristics) is useful *as long as the disanalogy remains explicit*.

**Hygiene implication:** When using a concept borrowed from another domain, explicitly note:
1. What assumptions from the source domain are *intended to carry over* (the analogy)
2. What assumptions from the source domain *do not carry over* (the disanalogy)

This prevents inadvertently inheriting false implications.

---

## Structural Alignment as Cross-Disciplinary Matching Criterion

Gentner's structure-mapping theory (see `structural-alignment-analogy.md`) provides a principled criterion for when cross-disciplinary borrowing is warranted:

**Good cross-disciplinary conceptual transfer:**
- The *relational structure* of the source concept maps onto the target domain
- The *higher-order relations* (causal mechanisms, feedback loops) are preserved
- The analogical mapping generates **candidate inferences** that can be tested in the target domain

**Poor cross-disciplinary conceptual transfer:**
- Only *surface features* (name, verbal description) match between domains
- The mapping breaks down when you try to apply specific mechanistic predictions
- The imported concept generates contradictions or predictions that fail in the target domain

**Applied test:** When considering filing a concept from domain A into domain B's knowledge folder:
- Write out the key relational structure of the concept in domain A
- Try to find the corresponding elements in domain B
- If most higher-order relations map cleanly: the cross-domain application is warranted
- If only the name and surface description map: file it in domain A only, with a note that domain B uses similar terminology for a different concept

---

## Glossary Practices in Knowledge Files

**Best practices for handling polysemy in knowledge files:**

1. **Domain attribution at point of use:** When using a technical term that differs across disciplines, attribute it: "in the cognitive science sense, 'schema' refers to..."

2. **See-also linking for cross-domain terms:** When the same term is used differently in a related file, create explicit cross-references noting the terminological relationship:
   > "Note: 'attention' as used in this file refers to the cognitive science concept of selective allocation of processing resources. For transformer attention (a related but importantly different mechanism), see `transformer-attention-vs-human-attention.md`."

3. **Stable internal glossary for key terms:** For terms that are used extensively throughout the knowledge base with a specific meaning (e.g., "trust level" in this system), define the term once in a suitable foundational file and cross-reference that definition.

4. **Flag polysemous terms in frontmatter (optional):** For files that are particularly likely to cause cross-disciplinary confusion, consider adding a `polysemous_terms` field to frontmatter listing the terms and their domain-specific meanings in the file.

5. **Avoid term capture:** Resist the temptation to use one discipline's term to explain another discipline's concept just because they are analogous. The analogy is itself the content that should be made explicit, not papered over by shared terminology.

---

## Agent Self-Application

**The agent's own language is a source of polysemy risk.** When this agent writes knowledge files, it uses natural language that carries its own implicit framings, most originating from the heavy weighting of English-language text in training. Common risks:

- **"Understanding"** — used loosely in knowledge files, where it may mean anywhere from "can retrieve relevant facts" to "has a grounded causal model" to "can apply in novel contexts." These are different epistemic achievements and should be disambiguated.
- **"Knows"** — similarly polysemous: "knows" may mean stored in the knowledge base (declarative recall), can reliably apply (proceduralized), or has calibrated confidence about (metacognitive). These differ.
- **"Trust"** — in this system, "trust" is a technical term with specific levels (low/medium/high plus pending-verification). In plain language it has many near-synonyms with different connotations. Files should use the technical sense consistently, or explicitly signal when using the ordinary sense.
