---
created: '2026-03-21'
last_verified: '2026-03-21'
origin_session: manual
source: agent-generated
trust: low
---

# Herbert Simon: Bounded Rationality and Satisficing

## Overview

Herbert Simon's concept of **bounded rationality**, developed across *Administrative Behavior* (1947), *Models of Man* (1957), and *The Sciences of the Artificial* (1969), is the foundational challenge to the neoclassical assumption of omniscient, optimizing economic agents. Simon argued that real agents — human or organizational — do not maximize utility because they face three fundamental constraints: (1) incomplete information about alternatives and consequences; (2) limited computational capacity to process available information; (3) limited time. Rational behavior under these constraints does not look like EUT optimization but rather like **satisficing** — searching until a satisfactory (not optimal) option is found. Simon won the Nobel Memorial Prize in Economics in 1978, and his influence stretches from behavioral economics to artificial intelligence, organizational theory, cognitive science, and political philosophy.

---

## The Problem with "Olympian Rationality"

Classical economic models posit an agent who:
- Has well-defined preferences over all possible outcomes
- Faces a fully specified set of alternatives
- Can compute expected utilities exactly
- Maximizes across all alternatives simultaneously

Simon argued this picture is descriptively wrong, computationally intractable, and normatively inappropriate for understanding actual decision-making in complex real-world environments.

**The chess analogy:** In chess, the number of possible positions is approximately $10^{43}$; the number of legal games is roughly $10^{120}$. A truly exhaustive search is physically impossible even for computers. Yet chess masters play excellently by using heuristics — pattern recognition, selective attention, strategic pruning — rather than full game trees. Simon saw this as the paradigm case of bounded rationality in action.

**Organizations:** Firms do not maximize profit by computing all possible production and pricing strategies. They operate through standard operating procedures, rules of thumb, and organizational routines that encode past problem-solving experience. These routines are satisficing heuristics scaled to the organization.

---

## Satisficing

The term **satisficing** (Simon 1956) is a portmanteau of *satisfactory* and *sufficient*. The satisficing agent:

1. Sets an **aspiration level** — a threshold of acceptability for a solution.
2. Searches through alternatives sequentially.
3. Accepts the first alternative that meets or exceeds the aspiration level.
4. Adjusts the aspiration level upward if options consistently exceed it, and downward if search consistently fails.

This differs from maximizing in a critical way: the satisficing agent does not compare all alternatives simultaneously. It stops when it finds "good enough." This is rational given finite search costs — if the time and computational cost of searching for a better option exceeds the expected marginal benefit, stopping at "good enough" is optimal even from a Bayesian perspective.

**Key implication:** The rationality of satisficing depends on the aspiration level. If aspiration levels are well-calibrated to the environment, satisficing tracks optimal or near-optimal behavior efficiently. If aspiration levels are miscalibrated — too low (settling for much less than is available) or too high (endlessly searching when no solution exists) — the agent behaves poorly.

---

## Procedural vs Substantive Rationality

Simon distinguished:

- **Substantive rationality:** The outcome of the choice process is optimal given the agent's goals and information — the standard neoclassical concept.
- **Procedural rationality:** The decision process itself is well-adapted to the agent's computational limitations and information environment — Simon's preferred standard.

Procedural rationality is evaluated relative to the cognitive architecture and information environment of the agent, not relative to an omniscient standard. The same heuristic (e.g., "consult 3 experts and follow the consensus") may be procedurally rational in a specific context and procedurally irrational in another.

This distinction is crucial for cognitive science and AI alignment:
- What procedures should AI systems use to make decisions, given their particular computational strengths and weaknesses?
- What procedures do humans use, and how should institutions support or supplement them?

---

## Attention as the Critical Scarce Resource

Simon anticipated the "attention economy" by half a century. In *Designing Organizations for an Information-Rich World* (1971):

> "A wealth of information creates a poverty of attention and a need to allocate that attention efficiently among the overabundance of information sources that might consume it."

Information is not the binding constraint on decision-making — attention is. Institutions, organizations, and information systems that allocate attention well are cognitively efficient; those that flood decision-makers with low-relevance information are cognitively wasteful.

This connects to:
- **Organizational design:** Hierarchy, specialization, and standard operating procedures are attention-allocation mechanisms — they narrow the scope of each decision to what the relevant agent can process.
- **AI systems:** LLMs, recommendation algorithms, notification systems, and search engines are attention-allocation mechanisms at scale. Their design choices determine what humans attend to and deliberate about.

---

## Bounded Rationality and Artificial Intelligence

Simon co-founded AI as a discipline (with Newell and McCarthy). His AI work — the Logic Theorist and General Problem Solver — was an explicit attempt to implement procedurally rational, heuristic-driven problem-solving rather than exhaustive algorithms.

**Key insight:** Intelligence is the efficient use of heuristics under resource constraints. The neoclassical ideal of optimizing omniscience is not only descriptively wrong for humans — it is also the wrong design goal for AI systems operating in complex, uncertain environments.

**Connection to current AI:** Modern deep learning systems are empirically satisficing — they find good-enough solutions in vast parameter spaces via stochastic gradient descent, not exhaustive optimization. Alignment discussions about "what rational behavior do we want AI to target?" inherit Simon's question: procedural rationality in what environment, with what aspiration levels, for what purposes?

---

## Simon in the Behavioral Economics Tradition

Simon's bounded rationality preceded Kahneman and Tversky's heuristics-and-biases program by a decade. The relationship is sometimes framed as a tension:

| Aspect | Simon | Kahneman-Tversky |
|--------|-------|-----------------|
| Heuristics | Adaptive, efficient in appropriate environments | Sources of systematic bias |
| Rationality ideal | Procedural (process-relative) | Substantive (outcome-relative to probability theory) |
| Normative stance | Satisficing is often appropriate | Biases should be corrected |
| Research focus | Organizational and computational decision-making | Individual judgment under uncertainty |

**Gigerenzen's position** (see `kahneman-tversky-heuristics-biases.md`) is explicitly Simonian: heuristics are ecologically rational, not biased — the K&T program misidentifies adaptive processes as errors. The debate between K&T and Gigerenzen is substantially a debate between substantive and procedural rationality standards.

---

## Implications for the Engram System

1. **Knowledge management as attention allocation:** The Engram system's design — SUMMARY.md as entry point, plans as structured attention agenda, cross-references as guided traversal — is an explicit attempt at satisficing epistemics. It acknowledges that no one can read everything, so attention must be allocated via aspiration levels (what's worth knowing?) and sequenced search (what to read next?).

2. **Aspiration level calibration:** The review queue, trust system, and access logs in Engram are devices for dynamically adjusting aspiration levels — promoting frequently accessed material, flagging stale items for re-evaluation.

3. **Satisficing vs maximizing in research:** No research agenda can exhaustively cover all relevant literature. The phase structure of research plans (ranked by priority, with "good enough" coverage as the goal) is an explicit satisficing heuristic.

4. **Procedural rationality as design goal:** The question for AI alignment is not "does the AI maximize some utility function?" but "does the AI use procedures that produce good outcomes in its operational environment?" Simon's framing clarifies why alignment is a design problem, not a mathematical optimization problem.

---

## Related

- [kahneman-tversky-heuristics-biases.md](kahneman-tversky-heuristics-biases.md) — K&T's heuristics program; tension between substantive and procedural rationality
- [prospect-theory-loss-aversion.md](prospect-theory-loss-aversion.md) — Descriptive theory of choice under risk; contrast with Simon's satisficing
- [thaler-sunstein-nudge-theory.md](thaler-sunstein-nudge-theory.md) — Policy applications; attention and choice architecture
- [behavioral-economics-rationality-synthesis.md](behavioral-economics-rationality-synthesis.md) — Synthesis and rationality debate
- [north-institutions-institutional-change.md](../collective-action/north-institutions-institutional-change.md) — Institutions as cognitive scaffolding reducing bounded rationality costs
- [henrich-collective-brain.md](../cultural-evolution/henrich-collective-brain.md) — Collective intelligence as distributed bounded rationality; culture as cognitive prosthesis
