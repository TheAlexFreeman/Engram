---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: external-research
last_verified: '2026-03-20'
trust: medium
related:
  - responsibility-attribution-ai.md
  - moral-status-ai-welfare.md
  - utilitarianism-bentham-to-singer.md
---

# Algorithmic Fairness: Justice in Automated Decision-Making

## The core problem

Algorithmic decision-making systems — used in hiring, lending, criminal justice, healthcare, education, content recommendation — affect millions of lives. These systems can perpetuate, amplify, or create **unfair discrimination** along lines of race, gender, socioeconomic status, and other protected characteristics. Algorithmic fairness asks: **what does it mean for an automated decision-making system to be fair, and how can fairness be achieved?**

## The landscape of unfairness

### Sources of algorithmic bias

**Historical bias**: training data reflects historical patterns of discrimination. A hiring algorithm trained on past hiring decisions inherits the biases of past human hirers. A recidivism prediction model trained on arrest data inherits the biases of policing patterns.

**Representation bias**: the training data underrepresents certain groups. A facial recognition system trained primarily on light-skinned faces performs worse on dark-skinned faces — not because of algorithmic malice but because of unrepresentative data.

**Measurement bias**: the proxy variables used to measure outcomes are themselves biased. "Success" measured by income disadvantages groups that face wage discrimination; "recidivism" measured by rearrest reflects policing patterns, not actual criminal behavior.

**Aggregation bias**: a model that performs well on average may perform poorly on subgroups. A medical diagnostic system that is 95% accurate overall may be 99% accurate on the majority group and 70% accurate on a minority group.

**Deployment bias**: a system developed for one context is deployed in another where its biases have different impacts. A risk assessment tool developed for low-level offenses is used for high-stakes sentencing.

### Real-world cases

**COMPAS** (Correctional Offender Management Profiling for Alternative Sanctions): ProPublica (2016) found that the COMPAS recidivism prediction algorithm had significantly different false-positive and false-negative rates for Black and white defendants. Black defendants were disproportionately labeled high-risk when they did not reoffend; white defendants were disproportionately labeled low-risk when they did.

**Amazon's hiring algorithm** (2018): Amazon developed an ML-based resume screening tool that was biased against women — it penalized resumes containing the word "women's" and favored patterns correlated with male candidates, because it was trained on a decade of predominantly male hiring data.

**Healthcare algorithms** (Obermeyer et al., 2019): a widely used algorithm for identifying patients needing extra care systematically underestimated the needs of Black patients. The algorithm used healthcare spending as a proxy for healthcare needs — but Black patients had historically less access to healthcare, so their lower spending reflected discrimination, not lower needs.

## Formal fairness criteria

### The three main families

Mathematical fairness criteria formalize intuitions about what it means for an algorithm to treat groups fairly:

#### 1. Group fairness (demographic parity / statistical parity)
**Definition**: the algorithm's positive outcome rates are equal across groups. P(Ŷ=1 | A=0) = P(Ŷ=1 | A=1), where A is the protected attribute.

**Intuition**: if the algorithm selects 30% of male applicants, it should select 30% of female applicants.

**Strengths**: simple, easy to audit, directly addresses disparate impact.

**Weaknesses**: ignores whether group members actually differ in the target variable. If 40% of group A qualifies and 30% of group B qualifies, statistical parity either over-selects from B or under-selects from A. This can reduce overall accuracy and may constitute unfairness to individuals.

#### 2. Equalized odds / predictive equality
**Definition**: the algorithm's error rates are equal across groups. P(Ŷ=1 | Y=1, A=0) = P(Ŷ=1 | Y=1, A=1) (equal true positive rates) and P(Ŷ=1 | Y=0, A=0) = P(Ŷ=1 | Y=0, A=1) (equal false positive rates).

**Intuition**: among people who actually qualify, the selection rate should be equal across groups; among people who don't qualify, the false alarm rate should be equal.

**Strengths**: respects individual qualification while ensuring equal treatment conditional on merit.

**Weaknesses**: requires a reliable ground truth Y — which is often contaminated by historical bias. If the ground truth itself reflects discrimination, equalizing errors relative to it perpetuates injustice.

#### 3. Calibration / predictive parity
**Definition**: among those given a particular risk score, the actual outcome rate is equal across groups. P(Y=1 | Ŷ=s, A=0) = P(Y=1 | Ŷ=s, A=1).

**Intuition**: when the algorithm says "this person has a 70% chance of recidivism," that should mean 70% for both Black and white defendants.

**Strengths**: ensures scores are equally meaningful across groups; supports decision-making under uncertainty.

**Weaknesses**: can coexist with very different error rates across groups (as the COMPAS case showed).

### The impossibility theorem (Chouldechova, 2017; Kleinberg, Mullainathan, Raghavan, 2016)
**When base rates differ across groups, no algorithm can simultaneously achieve calibration and equalized odds** (except in trivial cases). This is mathematically proven: if group A has a higher base rate of the target variable than group B, then any well-calibrated algorithm will necessarily have unequal false-positive or false-negative rates.

This is the fairness equivalent of Arrow's impossibility theorem or Arrhenius's population ethics impossibility: you cannot satisfy all reasonable fairness criteria at once. Trade-offs are mathematically unavoidable.

## Philosophical foundations

### Rawlsian justice and algorithmic fairness
Rawls's difference principle: inequalities are permissible only if they benefit the least-advantaged. Applied to algorithms: an algorithm may treat groups differently only if doing so benefits the worst-off group. This motivates:
- Giving priority to the interests of historically disadvantaged groups
- Evaluating fairness from the perspective of the most affected, most vulnerable users
- Designing systems behind a "veil of ignorance" about one's own group membership

### Luck egalitarianism
Dworkin, Arneson, Cohen: inequalities are unjust when they result from **bad luck** (circumstances beyond one's control) rather than **bad choices** (exercises of agency). Applied to algorithms: it's unjust for an algorithm to disadvantage someone based on factors they didn't choose (race, gender, socioeconomic background of birth). But it may be acceptable for an algorithm to disadvantage someone based on factors within their control.

**Problem**: the distinction between choice and circumstance is deeply contested, and many "choices" are shaped by unjust circumstances. Redlining creates neighborhoods where "choosing" to live in a high-crime area is not really a choice.

### Capability approach (Sen, Nussbaum)
Amartya Sen and Martha Nussbaum: justice is about ensuring people have the **capabilities** to live a flourishing life — the freedom to achieve well-being in diverse dimensions (health, education, political participation, etc.). Applied to algorithms: fair algorithms are those that do not diminish the capabilities of disadvantaged groups. This shifts focus from equal outcomes or equal treatment to equal opportunity for flourishing.

### Procedural vs. substantive fairness
- **Procedural fairness**: the *process* is fair (unbiased input, transparent algorithm, appealable decisions), regardless of outcomes
- **Substantive fairness**: the *outcomes* are fair (equal distribution, or at least not discriminatory), regardless of process
- Both matter: a procedurally fair algorithm can produce substantively unfair outcomes (if the process encodes historical bias); a substantively fair outcome can result from procedurally unfair means (quota systems)

## Individual vs. group fairness

### The tension
Group fairness criteria (demographic parity, equalized odds) treat groups as the unit of moral concern. But individual fairness demands that **similar individuals be treated similarly**, regardless of group membership.

Dwork et al. (2012): **individual fairness** requires a metric of similarity between individuals, and the algorithm's treatment of individuals should be Lipschitz continuous with respect to this metric — similar individuals get similar outcomes.

**The problem**: the similarity metric encodes substantive moral judgments (which features matter? how much?). There is no neutral metric.

### Intersectionality (Crenshaw)
Kimberlé Crenshaw (1989): discrimination operates not just along single axes (race OR gender) but at **intersections** (race AND gender). A hiring algorithm might be fair to women as a group and fair to Black people as a group while being unfair to Black women specifically (a subgroup that faces unique patterns of discrimination).

**Technical implication**: fairness must be assessed at the level of intersectional subgroups, not just single protected attributes. But the number of intersectional subgroups grows combinatorially, creating computational and statistical challenges.

## Specific domains

### Criminal justice
- Pretrial risk assessment: COMPAS, PSA, Arnold Foundation tools
- Predictive policing: PredPol, HunchLab
- **Key tension**: accuracy vs. equity — risk assessment tools may be more accurate than human judges but replicate systemic biases; eliminating sensitive features (race) doesn't help if other features (zip code, employment) are proxies

### Hiring and employment
- Resume screening, interview scheduling, performance evaluation
- **Key tension**: business necessity (hire the best candidates) vs. equity (don't perpetuate historical exclusion)
- Griggs v. Duke Power (1971): even facially neutral criteria can constitute illegal discrimination if they have disparate impact and don't serve business necessity

### Healthcare
- Diagnostic AI, treatment recommendation, resource allocation
- **Key tension**: evidence-based medicine uses population-level data that may not represent minority populations; optimization for overall accuracy can sacrifice accuracy for subgroups

### Content recommendation
- News feeds, search results, social media algorithms
- **Key tension**: engagement optimization (what users click on) vs. informational fairness (diverse, balanced information exposure)

## Mitigation strategies

### Pre-processing
- Remove or re-weight biased features in training data
- Generate synthetic data to balance group representation
- Use causal models to identify and remove discriminatory causal pathways

### In-processing
- Add fairness constraints to the optimization objective
- Use adversarial debiasing (train a second model to detect group membership from the first model's intermediate representations, then penalize leakage)
- Multi-objective optimization: explicitly trade off accuracy and fairness

### Post-processing
- Adjust decision thresholds per group to equalize error rates
- Calibrate scores per group
- Apply affirmative action in output (ensure minimum representation)

### Structural interventions
- Address root causes: biased training data, biased proxy variables, biased ground truth
- Participatory design: involve affected communities in system design
- Regular auditing and monitoring for disparate impact
- Appeals processes for individuals affected by algorithmic decisions

## Implications for AI alignment

### Fairness as alignment constraint
Fairness is a core alignment property: an AI system that perpetuates unjust discrimination is misaligned with human values, even if it maximizes a narrow utility function. Alignment must include:
- Explicit fairness constraints in training objectives
- Regular fairness audits across protected groups
- Mechanisms for affected individuals to contest decisions

### The impossibility result and alignment
The Chouldechova/KMR impossibility result means that perfect fairness is mathematically impossible when base rates differ. AI alignment must therefore:
- Make explicit which fairness criterion is prioritized and why
- Communicate trade-offs transparently to users and affected parties
- Design for the fairness criterion most appropriate to the deployment context
- Accept moral uncertainty about which fairness criterion is correct

### Rawlsian alignment
The veil of ignorance is a powerful alignment tool: design AI systems as if you don't know which user you'll be. This naturally prioritizes:
- Protecting the most vulnerable users
- Ensuring equitable access and treatment
- Minimizing the worst-case impact

### Reflective fairness
The Engram system's memory of past interactions could enable **reflective fairness**: monitoring one's own behavior for patterns of differential treatment and adjusting. A self-monitoring AI that tracks its own fairness metrics can correct biases as they emerge — a form of ongoing moral calibration.

### The philosophical foundation
No algorithmic fairness criterion is philosophically neutral — each embodies a substantive theory of justice:
- Demographic parity reflects egalitarianism
- Equalized odds reflects meritocracy
- Calibration reflects epistemic accuracy norms
- Individual fairness reflects liberal individualism

AI alignment must make these philosophical commitments explicit rather than hiding them behind technical definitions.

## Cross-references

- `philosophy/ethics/utilitarianism-bentham-to-singer.md` — consequentialist foundations of fairness (maximize total welfare, including distributional effects)
- `philosophy/ethics/kantian-deontology.md` — treating people as ends (not discriminating based on morally irrelevant features)
- `philosophy/ethics/contractualism.md` — Rawlsian justice, veil of ignorance, difference principle applied to algorithms
- `philosophy/ethics/moral-epistemology.md` — how we know which fairness criterion is correct
- `philosophy/ethics/parfit-collective-action.md` — collective-action structure of systemic discrimination
- `philosophy/ethics/responsibility-attribution-ai.md` — who bears responsibility for algorithmic unfairness