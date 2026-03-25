---
created: '2026-03-21'
last_verified: '2026-03-21'
origin_session: manual
source: agent-generated
trust: low
related: group-polarization-groupthink.md, asch-conformity-experiments.md, bystander-effect-diffusion-responsibility.md, milgram-obedience-experiments.md, zimbardo-stanford-prison-situation.md, ../cultural-evolution/transmission-biases-cognitive-attractors.md, ../behavioral-economics/behavioral-economics-rationality-synthesis.md, ../behavioral-economics/bounded-rationality-simon.md, ../behavioral-economics/kahneman-tversky-heuristics-biases.md
---

# Social Psychology and Transmission Biases: A Synthesis

## Overview

This synthesis file maps the classic social psychology experiments — Asch (conformity), Milgram (obedience), Zimbardo (situational role effects), Latané-Darley (bystander effect), and group polarization — onto the cultural evolution framework of Boyd, Richerson, and Henrich. The argument: **social psychology is the laboratory science of the mechanisms that cultural evolution theorizes.** Cultural evolution identifies transmission biases — conformist, prestige, authority, content — as the mechanisms driving cultural change. Social psychology provides controlled experimental evidence for how these biases operate in human behavior. The mapping enriches both frameworks: cultural evolution gains empirical grounding; social psychology gains evolutionary theoretical traction.

## The Mapping

### Asch → Conformist Bias

**Cultural evolution prediction:** Individuals disproportionately adopt the most common behavior in the population — more than frequency-weighted copying would predict.

**Asch's experimental demonstration:** In unambiguous perceptual tasks, 37% of responses shifted to wrong majority answers. The conformity is frequency-triggered (unanimous majority), not informationally-justified (the answer is obvious). This is conformist bias operating under conditions where it is clearly epistemically counterproductive.

**Mechanism:** Normative social influence — conforming to avoid social exclusion and gain social approval. The mechanism is independent of the informational value of the majority signal.

**When conformist bias is adaptive vs. maladaptive:**
- *Adaptive:* In genuinely uncertain environments where majority behavior reflects accumulated experience (traditional subsistence, novel social situations). Following the majority is a cheap, reliable heuristic for learning from the collective.
- *Maladaptive:* In Asch-like situations where the majority behavior is demonstrably wrong, or where majority behavior is the product of prior conformity cascades rather than genuine independent experience. Pluralistic ignorance, echo chambers, and norm maintenance all reflect the maladaptive range.

**For AI:** Training systems on human feedback in polarized communities embeds the conformist biases of those communities. If annotators systematically produce conformist answers (to avoid appearing heterodox to colleagues or supervisors), the training signal inherits conformist distortion.

---

### Milgram → Authority Bias / Prestige Bias

**Cultural evolution prediction:** Individuals preferentially adopt behaviors, beliefs, and values from high-prestige or high-status models. "Prestige bias" produces both accurate learning (prestigious models are often more skilled) and potential distortion (prestigious models' errors spread as readily as their insights).

**Milgram's experimental demonstration:** 65% of participants administered maximum believed-lethal shocks when instructed by a white-coated researcher in a Yale laboratory. The authority was:
- *Institutional* (Yale as a prestigious setting)
- *Role-based* (a scientist in a lab coat)
- *Epistemically claimed* (the experimenter claimed the study was important)

**Mechanism:** Agentic state — suspension of personal judgment and transfer of moral agency to the authority. This is prestige/authority bias in a high-stakes setting where it is clearly morally counterproductive.

**When authority bias is adaptive vs. maladaptive:**
- *Adaptive:* When authorities genuinely know more and their expertise is relevant (medical treatment, technical skill acquisition). Deferring to an expert doctor saves you from reinventing medicine.
- *Maladaptive:* When authorities are wrong, when their domain expertise doesn't apply, or when obedience produces collective catastrophes. Milgram is the maladaptive extreme; the Holocaust is the historical large-scale parallel.

**For AI:** LLMs trained on high-authority sources (academic papers, established textbooks) may disproportionately weight views from prestigious institutions. AI systems used in institutional settings may trigger agentic state dynamics in users — excessive deference to AI authority.

---

### Zimbardo → Role-Based Situational Transmission

**Cultural evolution prediction:** Cultural evolution transmits not just beliefs but practices, roles, and institutional behaviors. Social roles are powerful encapsulators of cultural content — "behave as a doctor" transmits a large behavioral package.

**Zimbardo's experimental demonstration:** Role assignment alone (despite random selection) produced rapid behavioral differentiation correlated with the assigned role's cultural script: guards became dominant and punitive; prisoners became submissive and distressed.

**Mechanism:** Role internalization — the assigned social role activates an associated behavioral schema, reducing individual variation and increasing role-predicted variance. Role-based cultural transmission is high-fidelity and low-cognition (you don't need to consciously learn each behavior; the role schema supplies it).

**When role-based transmission is adaptive vs. maladaptive:**
- *Adaptive:* Roles allow rapid behavioral acquisition in new situations and coordination within institutions. New medical students need not reinvent medical culture; the role structures it for them.
- *Maladaptive:* Roles can transmit harmful cultural content efficiently. The "guard" role transmitted punitive behavior; professional roles transmit their culture's biases and blind spots.

**For AI:** AI systems are increasingly given roles (assistant, advisor, tutor, therapist). Role assignment may activate role-consistent behavioral schemas in users and in AI systems, shaping interactions in ways that have not been explicitly designed or evaluated.

---

### Latané-Darley → Conformist Inaction / Diffusion of Responsibility

**Cultural evolution prediction:** Conformist bias affects not just belief adoption but behavioral participation. Low frequency of action in a group suppresses individual action below the rate expected from individual-level calculation.

**Latané-Darley experimental demonstration:** The more bystanders present, the lower the probability that any individual helps. Each individual's action probability is reduced by the (real or perceived) actions of others.

**Mechanism:** Two mechanisms: diffusion of responsibility (moral agency is diluted by group presence) and pluralistic ignorance (others' inaction signals inaction is appropriate). Both reflect a conformist process: individual behavior tracks the perceived group behavior.

**For AI and community design:** If AI safety communities observe widespread inaction on a risk, individual researchers may model this as a signal that action is unnecessary (pluralistic ignorance), even if individual concern is high. Creating public first-mover actions (high-profile researchers speaking out, labs publishing safety commitments) can reverse the bystander equilibrium.

---

### Group Polarization → Conformist Bias + Homophily → Echo Chambers

**Cultural evolution prediction:** In homogeneous cultural pools, conformist bias amplifies majority views and suppresses minority views. If populations are segmented into homogeneous groups, each group evolves independently in an increasingly divergent direction.

**Group polarization experimental demonstration:** Group discussion of shared-directional issues moves the group further in the pre-existing direction. Both informational (biased argument pool) and normative (social comparison toward the virtuous extreme) mechanisms operate.

**Mechanism:** Conformist bias in a homogeneous argument pool. When the informational environment is filtered by shared priors, conformist adoption of majority arguments produces systematic extremism.

**For AI:** AI recommendation systems optimized for engagement selectively expose users to content matching their existing views (informational homophily). This creates the biased argument pool that drives polarization, without any explicit malicious intent — purely from conformist-bias-compatible optimization.

---

## The Adaptive Toolkit and Its Failure Modes

Boyd and Richerson argue that conformist bias, prestige bias, and authority bias are generally adaptive heuristics for social learning in environments of genuine uncertainty. Social psychology's experiments demonstrate that these same heuristics produce systematic errors in specific conditions:

| Bias | Adaptive condition | Maladaptive condition (demonstrated by) |
|------|-------------------|-----------------------------------------|
| Conformist bias | Environment genuinely uncertain; majority has better information | Majority is wrong (Asch); majority is in a pluralistic ignorance equilibrium (Latané) |
| Prestige bias | Prestigious model is expert in the relevant domain | Authority's domain doesn't apply (Milgram); authority is wrong |
| Role-based transmission | Role encodes genuinely adaptive behaviors | Role encodes harmful behaviors (Zimbardo) |
| Conformist inaction | Inaction genuinely appropriate; others signal real safety | Diffusion of responsibility; pluralistic ignorance of real danger |

The key insight: the biases evolved for adaptive reasons in specific environments. They go wrong in specific conditions, many of which are artificially constructed in modern settings (institutional authority, online homophily, role assignment by organizations) without the feedback mechanisms (direct experience, reputational consequences) that would have calibrated them in ancestral environments.

## Implications for the Engram System

The Engram system is designed to preserve and transmit knowledge across conversational contexts. The social psychology of transmission biases suggests design cautions:
- **Conformist bias risk:** Knowledge curation that over-weights frequently-cited or "mainstream" views at the expense of accurate minority positions replicates Asch dynamics in epistemic form
- **Authority bias risk:** Knowledge assessed as "high trust" purely because it comes from prestigious sources (journal articles, famous thinkers) may embed prestige bias without epistemic justification
- **Pluralistic ignorance risk:** If Alex never sees critical assessments of views he holds, the Engram system may reinforce those views as "received" even if they are actually contested

The promotion process (from `_unverified/` to main knowledge, with trust assessment) is a structural intervention against these biases — a sociological CUDOS norm for knowledge curation.

## Related

- `asch-conformity-experiments.md` — Conformist bias experimental foundation
- `milgram-obedience-experiments.md` — Authority/prestige bias experimental foundation
- `zimbardo-stanford-prison-situation.md` — Role-based transmission experimental foundation
- `group-polarization-groupthink.md` — Polarization and epistemic community failure
- `bystander-effect-diffusion-responsibility.md` — Conformist inaction experimental foundation
- `knowledge/social-science/cultural-evolution/transmission-biases-cognitive-attractors.md` — Cultural evolution theory of transmission biases
- `knowledge/social-science/cultural-evolution/boyd-richerson-dual-inheritance.md` — Dual inheritance theory
- `knowledge/social-science/sociology-of-knowledge/merton-scientific-norms.md` — Institutional design to counter these biases in science
