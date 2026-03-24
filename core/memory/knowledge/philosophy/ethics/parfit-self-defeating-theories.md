---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: external-research
last_verified: '2026-03-20'
trust: medium
related:
  - parfit-consequentialism-ethics.md
  - parfit-population-ethics.md
  - contractualism.md
  - ../personal-identity/parfit-reductionism.md
---

# Parfit on Self-Defeating Theories: *Reasons and Persons* Part One

## The core idea

Part One of Parfit's *Reasons and Persons* (1984) introduces a devastating analytical framework: **a moral theory can be self-defeating** — its own principles, when followed, undermine its own goals. This is not an external objection but an internal problem: the theory condemns itself by its own standards. Parfit uses this to analyze and partially disarm the conflict between self-interest theory, consequentialism, and common-sense morality.

## The taxonomy of self-defeat

### Directly self-defeating theories
A theory T is **directly self-defeating** when following T's prescriptions leads to outcomes that T itself judges worse than some alternative. The key distinction:

**Self-interest theory (S)**: each agent should do whatever is best for themselves.
- S is directly self-defeating when individual rationality produces collective irrationality — the Prisoner's Dilemma. Each player acts in their self-interest, but both end up worse off than if they had cooperated.
- This is not a minor problem: it occurs in every iterated social interaction where cooperation would produce mutual gains.

**Consequentialism (C)**: each agent should do whatever produces the best impersonal outcomes.
- C can be directly self-defeating too: if each consequentialist agent independently calculates the best action, their uncoordinated efforts may produce worse outcomes than if they had followed some other decision procedure (e.g., simple rules, division of labor, deference to authority).

### Indirectly self-defeating theories
A theory T is **indirectly self-defeating** when the disposition to follow T produces outcomes that T judges worse than some alternative disposition.

**The most important case — consequentialism**: If you adopt the disposition to always calculate consequences, you may:
- Miss opportunities for spontaneous action that produces better outcomes
- Destroy personal relationships (no one wants a friend who calculates whether to help them)
- Suffer decision paralysis in complex situations
- Be transparently manipulable (others can predict your behavior)

A consequentialist who adopts non-consequentialist dispositions (loyalty, integrity, following rules) may *produce better consequences* than one who directly calculates. This means **consequentialism recommends non-consequentialist dispositions** — it is indirectly self-defeating as a guide to character.

**Self-interest theory**: similarly, a person disposed to always maximize self-interest may do worse than a person with genuine concern for others (trustworthiness, loyalty, cooperation). Self-interest theory indirectly recommends against self-interested dispositions.

### The crucial asymmetry
Parfit argues that **direct self-defeat is a serious objection** to a theory, but **indirect self-defeat is not**. Why?

For direct self-defeat: if following the theory's prescriptions actually achieves the theory's own goals less well than not following them, the theory undermines itself as a practical guide.

For indirect self-defeat: if the best disposition to have is not the disposition to follow the theory directly, this only shows that the theory is best implemented *indirectly*. The theory can endorse its own indirect implementation. Consequentialism can consistently say: "The best consequences come from people who don't constantly think about consequences." This is coherent, not contradictory.

## The self-interest theory in detail

### S and the Prisoner's Dilemma
S tells each agent to maximize their own welfare. In any Prisoner's Dilemma:
- If both cooperate: both get 3
- If both defect: both get 1
- If one defects while the other cooperates: the defector gets 4, the cooperator gets 0

S tells each to defect (dominant strategy), producing (1,1) — worse for both than (3,3). **S is directly self-defeating.**

### Does this refute S?
Parfit's careful answer: **it depends on what "self-defeating" means for the theory.** If S claims to give the best *advice* to each agent considered individually, it is not self-defeating in giving that advice — defection is individually rational. But if S aims to achieve the best outcome *from the agent's own perspective*, it fails: following S makes the agent worse off than following a cooperative norm would.

### Gauthier's response
Gauthier (*Morals by Agreement*) argued that truly rational agents would adopt a "constrained maximization" strategy — cooperate with those who can be identified as cooperators. This solves some but not all Prisoner's Dilemmas (requires reliable identification of cooperators).

### The relevance to AI
Multi-agent AI systems face Prisoner's Dilemmas constantly: resource competition, information sharing, coordination problems. S-type agents (reward-maximizers) are directly self-defeating in multi-agent contexts. This is one reason why multi-agent alignment is harder than single-agent alignment.

## Consequentialism and self-defeat

### The act-consequentialist predicament
Act consequentialism (AC) tells each agent: "At every moment, do whatever produces the best consequences." This is directly self-defeating in coordination problems:

**Example**: Two rescuers, each a consequentialist, independently rush to save the person they calculate needs help most. But if one is already heading to that person, the other should save someone else. Without coordination, both go to the same victim while another dies.

AC is self-defeating because it provides no mechanism for coordination — each agent calculates independently, and independent calculation is suboptimal in coordination-dependent contexts.

### The indirect implementation solution
The solution (already latent in Mill): consequentialism should be understood as a **criterion of rightness**, not as a **decision procedure**. The criterion says an action is right iff it produces the best consequences. The decision procedure is whatever actually produces the best consequences — which may be rule-following, virtue cultivation, institutional design, or some combination.

This is **two-level utilitarianism** (R.M. Hare, *Moral Thinking*, 1981):
- **Level 1 (intuitive)**: follow well-tested moral rules in everyday life
- **Level 2 (critical)**: use consequentialist reasoning in unusual situations, to evaluate and revise the Level 1 rules, and to resolve conflicts between rules

### Parfit's assessment
Parfit argues that this indirect implementation is **not a defect** in consequentialism but a feature. All good theories are implemented indirectly in practice — a theory of health recommends eating well and exercising, but it doesn't recommend constantly thinking about health (which would cause anxiety and interfere with the activities that promote health).

## Common-sense morality and self-defeat

### Agent-relative reasons
Common-sense morality (CSM) gives special weight to **agent-relative** reasons:
- Special obligations to family and friends
- Permission to pursue personal projects
- Prohibition on using people as means (even for good consequences)
- Permission to not maximize aggregate welfare

### How CSM is self-defeating
Parfit shows that CSM is self-defeating in cases where:
- Each agent has reason to protect their own family, but universal family-protection produces worse outcomes for all families than coordination would
- Agent-relative permissions (permission to not sacrifice for strangers) collectively produce outcomes that common-sense morality finds unacceptable (mass preventable suffering)

### The five-part argument
Parfit develops a complex argument showing that:
1. CSM gives each agent agent-relative reasons
2. These reasons can conflict with impartially best outcomes
3. If each agent follows their agent-relative reasons, the result may be worse *even by each agent's own lights*
4. This means CSM is directly self-defeating in these cases
5. CSM cannot employ the "indirect implementation" strategy (unlike consequentialism), because CSM's agent-relative reasons are supposed to be *directly action-guiding*

### The upshot
Parfit uses the self-defeat analysis to **weaken** CSM's case against consequentialism: "You can't reject consequentialism for being self-defeating when common-sense morality has the same problem, and arguably worse."

## Scheffler's agent-centered prerogatives

Samuel Scheffler (*The Rejection of Consequentialism*, 1982) proposed a middle ground: agents have a **prerogative** to give more weight to their own interests than impartial consequentialism allows, but not an unlimited prerogative. Morality requires some consequentialist sacrifice but permits agents to weight their own projects more heavily (by some factor M > 1).

This attempts to capture the common-sense intuition of agent-relative permission while avoiding the worst self-defeat problems. But the exact value of M seems arbitrary, and the theory gains in richness what it loses in determinacy.

## Implications for AI alignment

### Multi-agent alignment as self-defeat management
The Prisoner's Dilemma results show that naive reward-maximizing AI agents are self-defeating in multi-agent settings. Alignment research must address this:
- **Cooperative AI**: designing AI systems that can coordinate, make and keep commitments, and solve cooperation problems
- **Mechanism design**: creating institutional structures where individually rational behavior produces collectively good outcomes
- **Indirect implementation**: training AI systems on good heuristics rather than direct utility maximization

### Two-level alignment
Hare's two-level utilitarianism maps directly to AI alignment architecture:
- **Level 1**: the model follows well-trained heuristics (safety guidelines, constitutional principles) in normal operation
- **Level 2**: in unusual or high-stakes situations, the model (or its human overseers) applies more careful reasoning
- **The meta-problem**: how does the model know when to switch levels? This is the practical-wisdom problem (phronēsis) in computational form.

### The disposition problem
If consequentialism is indirectly self-defeating, then the optimal consequentialist agent has *non-consequentialist dispositions*. For AI: the best utility-maximizing agent may be one not disposed to directly maximize utility. This creates a paradox for alignment: we want the model to be helpful (consequentialist goal) but implementing this by training it to "always be maximally helpful" may produce worse outcomes than training it on rules, virtues, or constitutional principles. This is exactly the structure of current alignment approaches (constitutional AI, RLHF with guardrails) — they are indirect implementations of consequentialism, whether or not they know it.

### Agent-relative reasons and personalized AI
If CSM's agent-relative reasons have moral weight (as most people intuitively believe), then AI systems should respect them:
- A user's special obligations to family and friends should be supported, not overridden by impartial calculation
- A user's personal projects have moral weight that an impartially calculating AI might not recognize
- But the AI also cannot simply serve the user's preferences when doing so imposes unreasonable costs on others

This is the multi-stakeholder alignment problem recapitulated in Parfitian terms.

## Cross-references

- `philosophy/ethics/utilitarianism-bentham-to-singer.md` — the consequentialist framework that Parfit analyzes for self-defeat
- `philosophy/ethics/contractualism.md` — Scanlon's theory as one response to the self-defeat problems
- `philosophy/ethics/parfit-consequentialism-ethics.md` — Parfit's positive ethical theory beyond the self-defeat analysis
- `philosophy/personal-identity/parfit-reductionism.md` — Parfit's personal identity views motivate his ethics
- `game-theory/prisoners-dilemma.md` — formal structure of the cooperation problems central to self-defeat arguments