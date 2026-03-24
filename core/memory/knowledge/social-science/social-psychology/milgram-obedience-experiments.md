---

created: '2026-03-21'
last_verified: '2026-03-21'
origin_session: manual
source: agent-generated
trust: low
related:
  - zimbardo-stanford-prison-situation.md
  - ../../philosophy/ethics/moral-epistemology.md
---

# Milgram: Obedience to Authority

## Overview

Stanley Milgram's obedience experiments (Yale University, 1961–1962) are the most famous and most disturbing experiments in the history of social psychology. Milgram designed a paradigm in which ordinary adult volunteers were instructed by a scientific authority to administer what they believed were increasingly severe electric shocks to another person (actually a confederate who was not actually shocked). The core finding: **65% of participants administered what they believed was the maximum shock of 450 volts**, even as the "victim" screamed in pain, demanded to stop, and eventually fell silent. The experiment demonstrates the extraordinary power of situational authority to override individual moral judgment, with profound implications for understanding how atrocities occur, how hierarchical institutions function, and how transmission biases mediated by authority work in cultural evolution.

## The Experimental Design

### Setup

Participants (randomly drawn from the general New Haven population by newspaper advertisement) arrived at a Yale laboratory. They met a mild-mannered confederate ("the learner") and drew lots to determine roles — ostensibly random, but rigged so the confederate was always the "learner" and the participant was always the "teacher."

The teacher watched the learner be strapped to a chair with electrodes attached. The teacher then went to an adjacent room and sat before a shock generator — a large, imposing machine with 30 switches labeled from 15V to 450V in 15V increments, with labels ranging from "Slight shock" through "Danger: Severe shock" to simply "XXX."

The teacher administered "shocks" for each wrong answer in a word-pair memory test, escalating by 15V with each error. The learner (Confederate) responded with scripted vocalizations: complaints at 75V, demands to stop at 150V, screamed pleas and silence beyond 300V.

When participants hesitated, the experimenter in a grey lab coat said: "Please continue." / "The experiment requires that you continue." / "It is absolutely essential that you continue." / "You have no other choice, you must go on."

### Results

- **65%** of participants administered the maximum 450V shock
- Nearly all participants showed visible stress (sweating, trembling, nervous laughter) but continued
- No participant stopped before 300V
- Extensive post-experimental interviews and follow-up showed most participants found the experience deeply distressing

Milgram had predicted that only 1-2% of participants would go to the maximum. Virtually every expert consulted before the experiment predicted minimal obedience. The results were shocking to researchers and to the public.

## The Agentic State

Milgram's theoretical explanation for the results: the **agentic state**. Under ordinary conditions, people see themselves as autonomous moral agents responsible for their own actions. But when they enter a hierarchical authority structure — taking orders from a legitimate authority — they shift into an "agentic state": they act as agents of the authority rather than as autonomous individuals, and transfer moral responsibility upward.

In the agentic state:
- Moral judgment is suspended; the question becomes "am I doing my job correctly?" not "is this right?"
- Responsibility is experienced as belonging to the authority, not the individual
- The individual feels they cannot be blamed for following orders

This is not a defense of "just following orders" — Milgram was explicitly investigating the mechanisms behind the Holocaust. The agentic state is a description of how ordinary people become capable of participating in extraordinary evil through institutional embedding, not an excuse.

## Situational Determinants

Milgram ran 19 variations of the experiment to identify which factors influenced obedience:

| Variation | Obedience Rate |
|-----------|---------------|
| Baseline (voice feedback only) | 62.5% |
| Learner in same room (proximity) | 40% |
| Experimenter leaves room, gives orders by phone | 20.5% |
| Two additional "teachers" who refuse (rebel peers) | 10% |
| Yale campus vs. run-down commercial office | 47.5% vs. 65% |
| Experimenter and victim switch roles | Obedience drops sharply |

Key findings from variations:
1. **Physical proximity to the victim** decreases obedience — when participants could see and touch the victim, fewer continued
2. **Authority figure's proximity** matters — when the experimenter left the room, many participants reduced shocks or stopped, even while claiming to administer shocks
3. **Rebel peers** dramatically reduce obedience — analogous to Asch's "one ally" finding; social unanimity behind disobedience is as powerful as unanimity behind obedience
4. **Institutional legitimacy** matters — Yale yielded higher obedience than a commercial office building (reduced institutional authority)

## Ethical Controversies

Milgram's experiments are the classic case study in research ethics:

- Participants were **deceived** about the nature of the experiment (they thought they were shocking a real person)
- Participants experienced significant **psychological distress** during the experiment
- The potential for long-term psychological harm was debated
- Milgram obtained informed consent only after debriefing (not before)

These concerns led directly to the development of modern institutional review board (IRB) requirements for psychological research. Milgram defended his methods by pointing to the extensive debriefing, the low rate of reported long-term distress in follow-up studies, and the importance of the findings.

Recent meta-analyses: obedience rates in partial replications (stopping before maximum shock) remain high and show relative stability across decades and cultures, suggesting the fundamental mechanism is robust.

## Connection to Cultural Evolution

Milgram's results illuminate two transmission biases:

### Prestige and Authority Bias

Boyd and Richerson's "prestige bias" and "authority bias" predict that individuals defer to high-status or authoritative figures. Milgram demonstrates this is not merely copying behavior (as in a skill-learning context) but includes *submitting to authority even when it violates one's own moral judgment.*

The authority of a scientist in a lab coat, operating in an institutional setting (Yale), was sufficient to override strong moral inhibitions. The same mechanism explains why people accept claims from authoritative sources (renowned scientists, high-status community leaders) even when the claims are not well-evidenced.

### Hierarchical Transmission

Milgram's agentic state describes a mode of cultural transmission where the hierarchy, rather than individual evaluation, determines what actions/beliefs are accepted. This is "transmission by command" — a mechanism that produces high fidelity, low evaluation, and potential for error propagation.

In AI terms: when systems are trained on feedback from authoritative sources (internal labelers, expert raters, company guidelines) without individual-level epistemic autonomy, agentic-state dynamics may corrupt the training signal.

## Related

- `asch-conformity-experiments.md` — Peer conformity; Milgram addresses hierarchical authority rather than horizontal social pressure
- `zimbardo-stanford-prison-situation.md` — Role effects and situational power; complements Milgram's authority demonstrations
- `group-polarization-groupthink.md` — When group dynamics amplify rather than correct authority pressure
- `social-psychology-transmission-biases-synthesis.md` — Milgram → authority/prestige bias mapping
- `knowledge/social-science/cultural-evolution/transmission-biases-cognitive-attractors.md` — Authority bias in cultural transmission
- `knowledge/social-science/sociology-of-knowledge/merton-scientific-norms.md` — How CUDOS norms are designed to resist authority-based distortion
