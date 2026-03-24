---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: external-research
last_verified: '2026-03-20'
trust: medium
related:
  - utilitarianism-bentham-to-singer.md
  - parfit-self-defeating-theories.md
  - parfit-population-ethics.md
---

# Parfit on Consequentialism: *Reasons and Persons* Part One (continued)

## Context

This file covers Parfit's analysis of consequentialism's internal structure and the implications he draws for ethics after the self-defeat analysis. While the self-defeating theories file covers the *diagnostic* framework, this file covers Parfit's *constructive* conclusions about what consequentialism can and should become.

## The theory hierarchy

Parfit distinguishes several forms of consequentialism, ranked by their vulnerability to self-defeat:

### Act consequentialism (AC)
"At every moment, do whatever would make the outcome best."
- **Directly self-defeating** in coordination problems (see self-defeating theories file)
- **Indirectly self-defeating**: the disposition to always calculate produces worse outcomes than alternative dispositions
- Still correct as a **criterion of rightness**: an act is right iff it produces the best outcome

### Rule consequentialism (RC)
"Follow the set of rules whose general acceptance would produce the best outcomes."
- Solves many coordination problems (rules enable coordination)
- Less directly self-defeating than AC
- But faces the **rule-worship** objection: why follow the rule when you know that breaking it would produce better outcomes in this case?
- Parfit's response: the rule-worship objection has force only against a simplistic version of RC. A sophisticated RC includes meta-rules about when rules may be broken.

### Collective consequentialism
"Act as part of the collective pattern of behavior that would make the outcome best."
- Solves coordination problems more effectively than AC
- But requires agents to know what others will do — an information problem
- In practice, approaches RC as coordinated behavior defaults to following shared rules

### Two-level consequentialism (Hare)
- Level 1: intuitive moral thinking using reliable rules and dispositions
- Level 2: critical thinking using consequentialist calculation, reserved for unusual cases and rule evaluation
- This is Parfit's favored resolution: consequentialism is the correct *criterion*, implemented through non-consequentialist *procedures*

## Parfit's key moves

### The separation of criterion and procedure
The most important conceptual move in Part One: **separate the criterion of rightness from the decision procedure.** A theory can be:
- Correct as a criterion (telling you what counts as right)
- Incorrect as a decision procedure (calculating from the criterion at every decision point produces worse outcomes than following rules)

This insight applies beyond consequentialism: Kantian deontology faces the same issue (applying the categorical imperative to every decision is impractical), as does virtue ethics (deliberating about virtues interrupts the spontaneous excellence that constitutes virtue).

### Blameworthiness vs. wrongness
Parfit follows consequentialism in separating **wrongness** from **blameworthiness**:
- An action is **wrong** if it fails to produce the best outcome (criterion)
- An agent is **blameworthy** only if they acted from a disposition that they should have corrected, given available evidence
- Therefore: an agent can do wrong without being blameworthy (acted in good faith on reasonable evidence) and blameworthy without doing wrong (acted recklessly but got lucky)

For AI: this distinction maps to the difference between **alignment** (the model's actions are right) and **evaluation** (the model's dispositions are well-calibrated). A model can produce harmful outputs without being "badly aligned" if the situation was genuinely unpredictable.

### The convergence thesis
Parfit argues that the three major ethical traditions — consequentialism, Kantian deontology, and contractualism — are **converging** on the same conclusions in practice, even if they start from different premises:
- Consequentialism recommends rules and virtues (indirect implementation)
- Kantian universalizability tests converge with consequentialist outcomes in most cases
- Scanlonian contractualism produces similar results to rule consequentialism
- All three condemn the same core wrongs: gratuitous cruelty, exploitation, deception, injustice

This convergence thesis received its fullest treatment in Parfit's later work, *On What Matters* (2011), but was foreshadowed in *Reasons and Persons*.

## The problem of future generations

### The non-identity problem
One of Parfit's most influential contributions: **policies that affect which people will exist cannot be evaluated by their effects on any particular individual.** If a government chooses an energy policy that causes some pollution but also changes the timing and manner of millions of conceptions, the people who exist under this policy are *different people* from those who would have existed under the alternative. The polluted-world people cannot complain that they were harmed — without the pollution, they wouldn't exist at all.

This is devastating for person-affecting principles ("an act is wrong only if it is worse for someone"):
- The pollution policy makes no one worse off (the people who exist under it are different from those who would have existed otherwise)
- But it seems clearly wrong to choose a policy that produces worse lives when you could have chosen one that produces better lives

### Same number choices
When the population size is fixed, consequentialism handles future generations straightforwardly: choose the policy that produces better lives.

### Different number choices
When policies affect both the *quality* and *number* of future lives, deep problems arise (see population ethics file). The non-identity problem is a gateway to these harder questions.

### Implications for long-termism
The non-identity problem is foundational for **long-termist** AI safety reasoning: if our choices about AI development determine which future people exist, person-affecting morality cannot evaluate those choices. We need impersonal principles — which is exactly what total consequentialism provides, but at the cost of the Repugnant Conclusion.

## Reasons and moral motivation

### The objectivity of reasons
Parfit develops an account of **objective reasons** — facts that count in favor of actions, independent of the agent's desires. This is **reasons externalism**: you can have a reason to do something even if you don't want to do it or wouldn't want to do it even under ideal reflection.

This opposes **reasons internalism** (Williams, 1981): you have a reason to do X only if X serves some element in your existing motivational set (desires, goals, commitments). Internalism threatens to make morality optional — if you happen not to care about others, you have no reason to help them.

### Parfit's triple theory
In *On What Matters*, Parfit developed the convergence thesis into a "triple theory":
- **Kantian contractualism**: an act is wrong if it would be disallowed by principles that could not be universally willed or that someone could reasonably reject
- This combines Kantian universalizability, Scanlonian contractualism, and consequentialist sensitivity to outcomes
- Parfit argued this captures the overlapping core of the three traditions

## The practical upshot

### What Parfit achieves in Part One
1. **Defangs the self-interest theory**: S is directly self-defeating, so we cannot use it as the foundation of rationality
2. **Rescues consequentialism**: C is only indirectly self-defeating, which is manageable through indirect implementation
3. **Undermines pure common-sense morality**: CSM is directly self-defeating in coordination problems, and it cannot use the indirect implementation escape
4. **Sets up Parts Two–Four**: having shown that S is unstable and C is defensible (as criterion), Parfit moves to personal identity (Part Three) and population ethics (Part Four), using these results to build toward a unified ethical theory

### The relationship to personal identity
Part One's conclusion — that what matters is not the identity of the agent but the pattern of psychological connections — directly feeds into Part Three (personal identity). If what matters is Relation R (psychological continuity and connectedness), then the boundaries between persons are less deep than common-sense morality assumes, and **impersonal consequentialism gains force** relative to agent-relative morality.

## Implications for AI alignment

### Criterion vs. procedure in alignment
Parfit's separation of criterion and procedure is the single most important insight for AI alignment methodology:
- **Criterion**: the AI should produce the best outcomes for all affected parties
- **Procedure**: the AI should follow well-designed constitutional principles, safety guidelines, and behavioral heuristics
- The procedure is justified by the criterion but is not identical to it
- This explains why RLHF + constitutional AI is the current best practice: it implements consequentialism indirectly

### Convergence as alignment hope
If Parfit's convergence thesis is correct, then the choice between utilitarian, deontological, and contractualist alignment frameworks **matters less than we think** in practice. A well-aligned AI trained on any reasonable ethical framework will behave similarly in most situations. This reduces the philosophical burden on alignment researchers.

### Non-identity and AI-generated futures
If AI systems shape which future humans exist (through their effects on technology, economy, reproduction decisions, etc.), the non-identity problem makes person-affecting alignment criteria inadequate. Alignment must include impersonal criteria about the quality of future lives — even though no particular person can claim to have been harmed by AI development choices.

### Reasons externalism and AI motivation
If objective reasons exist independent of desires, then an AI system can have reasons to act well even if it has no "desires" in the human sense. This grounds AI alignment in the rational structure of reasons rather than in simulating human motivation — a more stable foundation.

## Cross-references

- `philosophy/ethics/parfit-self-defeating-theories.md` — the diagnostic framework for self-defeat (this file covers the constructive implications)
- `philosophy/ethics/parfit-population-ethics.md` — the Repugnant Conclusion and population ethics
- `philosophy/ethics/utilitarianism-bentham-to-singer.md` — the consequentialist tradition Parfit refines
- `philosophy/ethics/contractualism.md` — Scanlon's theory as part of Parfit's convergence thesis
- `philosophy/personal-identity/parfit-reductionism.md` — the personal identity arguments that motivate Parfit's ethics
- `philosophy/personal-identity/parfit-what-matters-survival.md` — Relation R and why identity doesn't matter