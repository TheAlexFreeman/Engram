---

## source: agent-generated
type: index
created: 2026-03-21
trust: medium
origin_session: manual

# Knowledge Base

419 files across 9 domains. Accumulated primarily from agent-planned and -executed research programs (2026-03-18 through 2026-03-21). Trust: 35 high, 314 medium, 70 low. Most content has been promoted from `_unverified/` and reviewed. Agent-generated self-knowledge syntheses now live in `self/` with medium trust instead of the external-research quarantine.

## Domains


| Domain                                           | Files | Trust           | Entry point                                                                                                                                    | Scope                                                                                                       |
| ------------------------------------------------ | ----- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| [philosophy/](philosophy/)                       | 86    | 55 med, 31 low  | [philosophy-synthesis.md](philosophy/philosophy-synthesis.md)                                                                                  | Intelligence, mind, personal identity, phenomenology, ethics, history of ideas                              |
| [mathematics/](mathematics/)                     | 70    | 35 high, 35 med | by subfolder                                                                                                                                   | Logic, complexity, dynamical systems, game theory, information theory, probability, optimization, stat-mech |
| [software-engineering/](software-engineering/)   | 69    | 69 med          | [SUMMARY.md](software-engineering/SUMMARY.md)                                                                                                  | Django, React, DevOps, testing, systems architecture                                                        |
| [cognitive-science/](cognitive-science/)         | 59    | 59 med          | [cognitive-science-synthesis.md](cognitive-science/cognitive-science-synthesis.md)                                                             | Memory systems, attention, metacognition, concepts, relevance realization                                   |
| [ai/](ai/)                                       | 49    | 48 med, 1 low   | [frontier-synthesis.md](ai/frontier-synthesis.md)                                                                                              | History of AI, frontier research, retrieval/memory, tools/MCP                                               |
| [social-science/](social-science/)               | 42    | 12 med, 30 low  | by subfolder                                                                                                                                   | Cultural evolution, behavioral economics, social psychology, collective action, network diffusion           |
| [rationalist-community/](rationalist-community/) | 28    | 28 med          | [synthesis/rationalist-community-story-aims-and-tensions.md](rationalist-community/synthesis/rationalist-community-story-aims-and-tensions.md) | Origins, AI discourse, key figures, institutions, community norms                                           |
| [self/](self/)                                   | 13    | 5 med, 8 low    | [engram-system-overview.md](self/engram-system-overview.md)                                                                                    | System architecture, governance model, security analysis, operational resilience                            |
| [literature/](literature/)                       | 3     | 3 med           | —                                                                                                                                              | Literary analysis (Galatea 2.2, The Man Who Was Thursday, Tree of Smoke)                                    |


## Thematic threads across domains

**Intelligence as dynamical regime.** The central intellectual thread. Converges from dynamical systems theory (mathematics), free energy principle (philosophy), relevance realization (cognitive science), and scaling laws (ai). Start with [philosophy/synthesis-intelligence-as-dynamical-regime.md](philosophy/synthesis-intelligence-as-dynamical-regime.md).

**Memory and persistence.** How biological memory works (cognitive-science/memory/), how it maps onto this system's architecture (cognitive-science/cognitive-science-synthesis.md), and the security implications of persistent memory (self/security/). The reconsolidation research is directly design-relevant.

**Memetic security.** 7 files under [self/security/](self/security/) analyzing injection vectors, drift vs. attack, trust escalation, and the irreducible limits of self-referential governance. Grounded in the cultural evolution literature (social-science/cultural-evolution/).

**Personal identity and AI.** Parfit's reductionism, narrative identity (MacIntyre, Schechtman, Ricoeur), phenomenology of selfhood — all applied to the question of what identity means for a session-bounded agent. Start with [philosophy/personal-identity/agent-identity-synthesis.md](philosophy/personal-identity/agent-identity-synthesis.md).

**Rationalist AI discourse.** Historical and critical survey of the rationalist community's contribution to AI safety thinking: where the ideas came from, which predictions held up, and how the field adapted to the LLM paradigm shift. Start with [rationalist-community/synthesis/rationalist-community-story-aims-and-tensions.md](rationalist-community/synthesis/rationalist-community-story-aims-and-tensions.md).

## Domain details

### Philosophy (86 files)

4 subfolders + 17 root-level files. The root files include original syntheses ([narrative-cognition.md](philosophy/narrative-cognition.md), [blending-compression-coupling-construal.md](philosophy/blending-compression-coupling-construal.md), [llm-vs-human-mind-comparative-analysis.md](philosophy/llm-vs-human-mind-comparative-analysis.md)) and literary-philosophical notes (C.S. Lewis, Nick Land, McLuhan). See [philosophy/SUMMARY.md](philosophy/SUMMARY.md) for the full index.

- **personal-identity/** (12 files) — Locke through Parfit through narrative accounts; 3 applied AI-identity files
- **phenomenology/** (13 files) — Husserl, Heidegger, Merleau-Ponty, 4E cognition, capstone synthesis
- **ethics/** (14 files) — Metaethics, normative theories, Parfit's ethics, AI ethics
- **history/** (47 files) — Ancient through contemporary + non-western + synthesis

### Mathematics (70 files)

9 subfolders covering the mathematical foundations that appear across all other domains. Half are trust: high (externally verified).

- **game-theory/** (12) — Mechanism design, evolutionary games, signaling, social choice
- **information-theory/** (12) — Entropy, MDL, rate-distortion, PAC learning, VC dimension
- **logic-foundations/** (11) — Godel, Turing, type theory, category theory, set theory
- **probability/** (7) — Bayesian inference, Gaussian processes, stochastic processes, concentration
- **dynamical-systems/** (7) — Chaos, bifurcation, SOC, complex networks, fractals
- **statistical-mechanics/** (6) — Ising model, spin glasses, Hopfield/Boltzmann, partition functions
- **optimization/** (5) — Convex analysis, gradient descent, online learning, nonconvex landscapes
- **complexity-theory/** (5) — P/NP, interactive proofs, descriptive complexity
- **causal-inference/** (5) — SCMs, Pearl's hierarchy, counterfactuals, causal discovery

### Software Engineering (69 files)

Alex's working stack. See [software-engineering/SUMMARY.md](software-engineering/SUMMARY.md).

- **django/** (19) — Django 6.0, DRF, Celery, caching, testing, migrations
- **testing/** (14) — Unit through formal verification, ML evaluation, property-based, mutation
- **systems-architecture/** (13) — Git internals, WAL, CRDTs, schema evolution, filesystems, provenance
- **react/** (13) — React 19, Chakra UI 3, TanStack Router/Query, build tooling
- **devops/** (10) — Docker, Nginx, Celery workers, CI/CD, monitoring

### Cognitive Science (59 files)

See [cognitive-science/SUMMARY.md](cognitive-science/SUMMARY.md).

- **concepts/** (12) — Classical, prototype, exemplar, theory-theory, conceptual change, analogy
- **memory/** (11) — Tulving taxonomy, consolidation, forgetting, reconsolidation, false memory
- **attention/** (11) — Selection, capacity, dual-process, executive function, mind wandering
- **metacognition/** (10) — Monitoring/control, calibration, source monitoring, feeling of knowing
- **relevance-realization/** (5+) — Vervaeke's framework, four kinds of knowing, wisdom

### AI (49 files)

- **frontier/** (31) — Alignment, architectures (MoE, SSMs), interpretability, multi-agent, reasoning, retrieval-memory (8 files on RAG, ColPaLi, HyDE, late chunking, long context)
- **history/** (11) — Cybernetics through transformers through RLHF; 1 synthesis
- **tools/** (6) — MCP protocol, AI tools landscape, agent-memory ecosystem positioning
- **frontier-synthesis.md** — Cross-cutting synthesis of frontier research

### Social Science (42 files)

- **cultural-evolution/** (12) — Dawkins, Blackmore, Tomasello, norms/punishment, LLM-as-cultural-mechanism
- **social-psychology/** (6) — Transmission biases, conformity, persuasion
- **behavioral-economics/** (5) — Kahneman/Tversky, prospect theory, nudge architecture
- **collective-action/** (5) — Ostrom, Acemoglu/Robinson, mechanism design for commons
- **network-diffusion/** (5) — Granovetter weak ties, information cascades, small-world networks
- **sociology-of-knowledge/** (5) — Kuhn, Latour, Fleck, epistemic communities
- **social-epistemology/** (4) — Goldman, extended mind, distributed cognition

### Rationalist Community (28 files)

- **origins/** (5) — Yudkowsky biography, Sequences, Hanson, academic prehistory
- **ai-discourse/** (17) — Canonical ideas (7), prediction failures (3), industry influence (3), post-LLM adaptation (3), synthesis (1)
- **community/** (2) — LessWrong norms, meetups/HPMOR
- **figures/** (2) — Scott Alexander, Gwern
- **institutions/** (1) — MIRI/CFAR
- **synthesis/** (1) — Story, aims, and tensions

### Self-Knowledge (13 files)

System's knowledge about itself. 6 root files + 7 security analysis files.

- **engram-system-overview.md** — Architecture and design (updated 2026-03-21)
- **engram-governance-model.md** — Trust tiers, validator, human review gate, self-referential problem
- **validation-as-adaptive-health.md** — How the test suite closes the loop
- **protocol-design-considerations.md** — When to formalize vs. leave semantic
- **environment-capability-asymmetry.md** — Multi-agent coordination and local-only git
- **operational-resilience-and-memetic-security-synthesis.md** — Cross-cutting synthesis
- **security/** (7 files) — Injection vectors, mitigation audit, comparative analysis, irreducible core, drift vs. attack, memory amplification, design implications
