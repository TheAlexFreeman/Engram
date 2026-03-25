---
created: '2026-03-21'
last_verified: '2026-03-21'
origin_session: manual
source: agent-generated
trust: low
related: latour-actor-network-theory.md, mannheim-sociology-of-knowledge.md, merton-scientific-norms.md, social-construction-of-scientific-knowledge.md, ../../../philosophy/history/contemporary/philosophy-of-science.md
---

# Kuhn: Paradigms and Scientific Revolutions

## Overview

Thomas Kuhn's *The Structure of Scientific Revolutions* (1962, 2nd ed. 1970) is the most cited and most debated book in the history and philosophy of science. Its central argument: **science does not progress by steady accumulation of knowledge but by discontinuous revolutions.** Between revolutions, science operates in "normal science" mode under a shared paradigm; revolutions are episodes in which the paradigm itself is overthrown and replaced. The book introduced the word "paradigm" into popular currency and fundamentally reshaped how scientists, philosophers, and historians think about scientific change. It is directly relevant to understanding AI paradigm genealogy and to the cultural evolution of technical ideas.

## Normal Science

### The Paradigm

A **paradigm** (Kuhn's most famous and most contested concept) is an exemplary achievement — typically a canonical piece of scientific work like Newton's *Principia*, Lavoisier's chemical revolution, or Maxwell's electrodynamics — that defines:

1. **What the important problems are** — the field's research agenda
2. **What a good solution looks like** — the standards of acceptable explanation
3. **What evidence counts** — which observations matter and how to interpret them
4. **What assumptions are background** — what can be taken for granted rather than questioned

A paradigm is not just a theory; it is an entire constellation of commitments shared by a community — methodological, ontological, and evaluative. Kuhn later distinguished **"disciplinary matrix"** (the broader constellation) from **"exemplar"** (the concrete puzzle-solutions that students, by learning to solve analogous problems, acquire as tacit knowledge).

### Puzzle-Solving

Under a paradigm, science is **puzzle-solving.** Scientists are not testing the paradigm; they are applying and extending it to new domains. A puzzle is a problem that the paradigm promises can be solved by someone skillful enough. The paradigm provides both the problem specification and the expectation that a solution exists.

This is why normal science is conservative: anomalies (phenomena that don't fit the paradigm) are typically set aside, attributed to instrument error, experimental failure, or insufficient skill, rather than taken as refutations of the paradigm. Blaming the individual investigator rather than the theory is the normal response to anomaly.

Normal science is highly productive: by narrowing researchers' focus to paradigm-defined puzzles, it allows deep investigation of a bounded space. The efficiency gain is real. But it also makes the scientific community resistant to fundamental change — that is the point.

## Crisis and Revolution

### Anomalies

When anomalies accumulate — when the same phenomena persistently resists paradigmatic explanation despite serious investigation — a **crisis** develops. The scientific community becomes aware that something is fundamentally wrong. Trust in the paradigm erodes. Speculative proposals multiply. The field becomes temporarily more like philosophy than normal science.

Important: crisis does not automatically produce revolution. A paradigm is never abandoned until a replacement paradigm is available. Scientists do not give up a framework just because it has problems — they need somewhere else to go.

### Scientific Revolution

A revolution occurs when a new paradigm is sufficiently developed to attract a community of supporters who abandon the old paradigm in favor of the new one. This is not a purely rational process:

- The new paradigm typically solves some of the crisis-inducing anomalies but cannot answer all the questions the old paradigm could answer
- The paradigms are **incommensurable** — they do not share enough of their conceptual framework for their claims to be directly compared on a common standard
- The shift therefore involves something like a **Gestalt switch** (Kuhn's analogy): the same phenomena look different under the two paradigms, and the choice between them cannot be fully adjudicated by logic and evidence alone

### Incommensurability

**Incommensurability** is Kuhn's most philosophically controversial claim. Two scientific communities operating under different paradigms:

1. **Disagree about which problems matter** — so evidence in favor of new paradigm may simply not register as relevant to defenders of the old
2. **Use the same terms differently** — "mass," "planet," "element" all changed meaning across paradigm shifts; apparent agreement may mask genuine disagreement
3. **Cannot appeal to a neutral method** — there is no paradigm-independent methodology that could adjudicate between competing paradigms

Incommensurability does not mean scientists cannot communicate across paradigm divides; it means that communication is *difficult* and that rational debate alone cannot decide paradigm choice. Non-epistemic factors (sociology, rhetoric, generational turnover) play a role.

## Why Paradigm Shifts Are Not Purely Rational

Kuhn's account of how paradigm shifts happen is explicitly sociological and psychological, not just logical:

1. **Generational turnover:** Max Planck is supposed to have remarked that science advances "one funeral at a time." New paradigms often win because the old generation dies and the new generation is trained in the new framework. This is a cultural transmission mechanism, not a rational inference.

2. **Social network effects:** Paradigm adoption spreads through scientific communities via persuasion, authority, and social influence — the same mechanisms as any cultural transmission. High-prestige early adopters matter.

3. **Non-rational persuasion:** Kuhn describes paradigm change using the language of conversion, persuasion, and Gestalt switch. The arguments offered by paradigm-changers (like Copernicus or Lavoisier) are never conclusive by themselves; they make the new paradigm seem promising, attractive, and worth betting on.

This is deeply connected to cultural evolution's analysis of prestige bias, conformist bias, and authority bias. Scientific paradigm change is a case study in how high-stakes cultural evolution works under the pressures of an institutionalized community.

## Connection to AI Paradigm Genealogy

The AI history in `knowledge/ai-history/` traces a series of paradigm shifts:

- **Symbolic AI / GOFAI** (1956–1980s): the paradigm that intelligent behavior requires explicit symbolic representation and rule-based manipulation
- **Connectionionism** (first wave 1950s–1969, second wave 1986–1990s): the paradigm that intelligence emerges from distributed representations and learning
- **Deep learning** (2012–present): the current dominant paradigm centered on large neural networks trained end-to-end on data

Each transition exhibits Kuhnian features:
- Anomaly accumulation (symbolic AI could not scale; early neural nets could not learn deep representations)
- Crisis (the AI winters)
- Revolution following a key breakthrough (backprop, GPUs + ImageNet, transformers)
- Incommensurability in vocabulary and research priorities

Kuhn's framework helps explain why the transition from symbolic to connectionist AI was so culturally and institutionally difficult — not just a technical upgrade but a genuine paradigm shift.

## Critiques and Extensions

### Popper's Objection

Karl Popper argued that Kuhn's model made science look irrational and sociologically determined. For Popper, science's distinguishing mark is **falsifiability** — a commitment to abandoning theories when evidence refutes them. Kuhn's scientists protect the paradigm from refutation; this looks like dogmatism, not science.

Kuhn's response: Popper's model describes how science *should* work in an idealized moment of test; Kuhn describes how science *actually* works as a social institution over time. Both are useful. Normal science's conservatism is not a failure; it's what allows deep exploration of a framework.

### Lakatos's Research Programmes

Imre Lakatos tried to reconcile Kuhn and Popper with his concept of **research programmes** — coherent programs with a "hard core" of protected assumptions and a "protective belt" of auxiliaries that can be revised when anomalies arise. A programme is progressive when it yields novel predictions; it is degenerating when it only makes ad hoc adjustments. This gives a rational criterion for paradigm choice that Kuhn's account lacks.

### Feminist Philosophy of Science

Sandra Harding, Donna Haraway, and Helen Longino argued that Kuhn's framework is still too autonomous from social critique. The *content* of science — not just its social organization — reflects the interests and perspectives of dominant groups. Paradigms encode not just methodological but political choices.

## Implications for the Engram System

Kuhn's framework applies directly to the Engram system's knowledge curation mission:

- The `ai-history/` and `philosophy/` knowledge bases document paradigm transitions; Kuhn provides the conceptual vocabulary for narrating them
- The system's own development involves choices about what counts as "good" memory (paradigm-like commitments about trust, promotion, and curation)
- Awareness of incommensurability warns against assuming that knowledge organized under one paradigm (e.g., cognitive science's computational model) can be directly translated into another (e.g., dynamical systems models)
- The `ai-paradigm-genealogy-research (historical plan reference)` plan is explicitly a Kuhnian project

## Related

- `mannheim-sociology-of-knowledge.md` — The social situatedness of knowledge that paradigms institutionalize
- `merton-scientific-norms.md` — Merton's competing vision of how science maintains truth-tracking
- `latour-actor-network-theory.md` — Extends Kuhn: the assembly of actors that stabilizes a paradigm
- `social-construction-of-scientific-knowledge.md` — SSK's radicalization of Kuhn
- `knowledge/ai-history/synthesis/how-the-current-ai-paradigm-formed.md` — Kuhnian analysis of AI paradigm history
- `knowledge/social-science/cultural-evolution/prestige-cascades-llm-adoption.md` — Paradigm adoption as prestige cascade
- `knowledge/philosophy/history/scientific-revolutions-and-progress.md` — If present; philosophy of science background
