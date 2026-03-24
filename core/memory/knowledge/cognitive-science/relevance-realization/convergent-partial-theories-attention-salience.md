---

created: '2026-03-20'
origin_session: unknown
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - opponent-processing-self-organizing-dynamics.md
  - frame-problem-minsky-dreyfus.md
  - ../attention/attention-synthesis-agent-implications.md
---

# Convergent Partial Theories: Attention and Salience Before Vervaeke

## The Pattern: Partial Accounts with a Shared Blind Spot

Before Vervaeke's Theory of Relevance Realization, multiple research programs converged on the problem of how cognitive systems identify what matters. Attention research, salience modeling, schema theory, and affordance theory each addressed part of the problem. Each is genuinely illuminating within its domain. But each takes some level of relevance as already solved and builds a selection mechanism on top. None accounts for the circular bootstrapping by which agents *develop* relevance sensitivity in the first place, or for the dynamic *revision* of relevance assignments when they fail.

Understanding these partial theories makes Vervaeke's synthesis legible: RR theory is not continuous with these accounts but a qualitative step back to ask the prior question each evades.

---

## Attention as Spatial-Temporal Relevance Selection

**Spotlight and zoom-lens models**: Posner (1980) and Eriksen & St. James (1986) proposed that attention operates like a spotlight (discrete beam) or a zoom lens (variable-resolution beam) over a spatial array. The metaphor captures real phenomena: attended locations are processed with greater acuity, faster, and with less noise. Attention *selects* a region of space as relevant.

**What this leaves unexplained**: The spotlight model explains *how* selection across space works once a region has been targeted. It does not explain *what determines which region is targeted*. In a simple lab task, the experimenter provides the cue. In the real world, what provides it? The spotlight/zoom-lens model presupposes that something outside it answers the relevance question ("attend here") and it implements the selection. RR theory asks: what is that "something"?

**Late and early selection**: Whether semantic analysis occurs before or after attentional selection (the Broadbent–Treisman–Deutsch debate) determines the *stage* of relevance selection, not its *basis*. Even late-selection models, which allow full semantic processing of unattended channels, still require an explanation of how task goals modulate what subsequently gets into awareness. Task-goal representation is already a relevance commitment.

---

## Salience Maps: Bottom-Up Relevance Without a Knower

**Itti & Koch's computational saliency model** (2000): A bottom-up salience map is computed over a visual scene by combining feature contrast across channels (color, orientation, luminance, motion). Each location receives a salience score based on how different it is from its neighbors in each feature dimension. Attention is directed to the locations of maximum salience.

**Real explanatory power**: The model explains a significant portion of human fixation locations on natural images (gaze data matching). It captures the intuition that outliers (objects that pop out) are attended before objects that blend in — a genuine, automatic relevance signal.

**What it leaves unexplained**: Salience maps compute relevance as *feature-contrast*, which is a task-independent, context-free measure. Feature-contrast determines where a predator or a food object will likely be found — it is an ecologically calibrated bottom-up signal. But much of human attention is *task-modulated top-down*: when searching for a red apple, red features become relevant even at low feature-contrast. The salience map model requires supplementation by a top-down relevance-weighting mechanism. That mechanism — which features should be upweighted for the current task — is itself a relevance problem. The model has no account of how top-down relevance commitments are formed or revised.

---

## Feature Integration Theory: Relevance as Binding

Treisman's **Feature Integration Theory** (FIT, 1980) proposes that visual features (color, shape, orientation, motion) are registered automatically and in parallel in separate "feature maps". Attention acts as a "glue" that binds the features at a given spatial location into a unified object representation.

**Relevance aspect**: Pre-attentive (automatic) feature detection implements a form of relevance — certain feature contrasts drive pop-out without deliberate attention. But which features are detected in the feature maps is determined by the feature-map architecture, which is fixed by evolution and development. FIT operates within a fixed relevance vocabulary (the set of primitives encoded in feature maps). It does not account for how the vocabulary itself is selected or revised.

**The conjunction-search problem**: When target identification requires conjunction of features (a red vertical bar among red horizontals and green verticals), search is slow and serial, requiring focused attention to each location. The serial search is an attention-allocation process guided by... what? By a task specification that tells the attentional system which feature conjunctions constitute a target. The task-specification is a relevance frame that FIT does not generate — it must be supplied from outside.

---

## Schema Theory: Relevance as Cached Template

**Bartlett's schemas** (1932): Memory is constructive; recall is guided by prior knowledge structures (schemas). What is remembered is what fits the schema; what is remembered as central is what the schema marks as central; schema-incongruent details are transformed or forgotten. Schema-driven processing is relevance-directed retrieval and reconstruction.

**Piaget's assimilation/accommodation**: Schemas assimilate new experience to existing categories; accommodation revises schemas when assimilation fails. Both processes presuppose that the schema represents "what matters" in the current domain.

**What is not explained**: How is the appropriate schema selected for a new situation? Schema selection requires recognizing which features of the current situation are the "schema-activating" features — i.e., relevant to schema identity. This is the schema-selection problem, which is structurally identical to the frame-selection problem (see `frame-problem-minsky-dreyfus.md`). Schema theory also has no account of schema revision when the activated schema leads to systematic failure — how does the system know that its current schema is wrong in a systematic rather than accidental way?

---

## Affordance Theory: Relevance as Ecological Relationship

Gibson's **ecological psychology** (1966, 1979) proposed that relevance is not computed internally but *perceived directly* in the relational properties between agent and environment — **affordances**. A surface that is flat, rigid, and extended at knee height *affords* sitting for a creature of the right body size. Affordances are real properties of the environment-relative-to-the-animal, not projections of mental representations.

**Genuine advance**: Affordance theory locates relevance in the *action possibilities* of the environment, sidestepping the internal-representation regress. It also explains why different animals perceive different environments: the affordances a tick detects are different from those a human detects, because their bodies and action repertoires differ.

**Limitations**: 
1. Ecological psychology handles routine, well-practiced affordances in evolutionarily familiar environments well. It handles *novel affordances* — seeing a new object as affording an unfamiliar use — poorly. Sultan discovering that boxes afford stacking is not satisfactorily explained by direct perception of an already-tuned affordance; it requires something closer to deliberate insight.
2. Affordances in impoverished environments (formal problems, abstract domains, novel technologies) are not ecologically perceivable. Affordance theory scales down from human insight cases rather than scaling up to them.
3. How new affordances are learned — how an agent expands its "affordance vocabulary" — is not well-specified. This is the learning-of-relevance problem that RR theory must address.

---

## The Shared Limitation: Pre-Solved Relevance

The pattern across all partial theories:

| Theory | What it explains | What it presupposes |
|---|---|---|
| Spotlight/zoom-lens attention | How a targeted location is prioritized | What determines which location to target |
| Salience maps | Bottom-up feature-contrast priority | How task context modulates relevance |
| Feature Integration Theory | How attended features bind into objects | Which features constitute the search target |
| Schema theory | How schemas guide memory and inference | Which schema is relevant to the current situation |
| Affordance theory | How action possibilities are relationally specified | How novel or abstract affordances are perceived |

In each case, the theory takes *some level* of relevance as already solved and builds a selection or binding mechanism on top. The question one level deeper — how does the agent determine what the relevant features are, which schema to activate, which affordance applies — is deferred to the next level. No theory accounts for the ground level: the self-organizing capacity that generates and revises relevance commitments without a fixed, external relevance-specifier.

This is precisely the gap that Vervaeke's Theory of Relevance Realization addresses: not any of these mechanisms individually, but the meta-level self-organizing process that calibrates them and revises them when they systematically fail.

---

## Cross-links

- `frame-problem-minsky-dreyfus.md` — these partial theories face the same regress as Minsky's frame-selection problem
- `opponent-processing-self-organizing-dynamics.md` — Vervaeke's answer to the shared limitation identified here
- `knowledge/cognitive-science/attention/early-late-selection-models.md` — attentional selection in detail
- `knowledge/cognitive-science/attention/feature-integration-binding-problem.md` — FIT in detail
- `knowledge/philosophy/phenomenology/merleau-ponty-embodied-perception.md` — affordance theory's closest philosophical partner; Merleau-Ponty develops Gibson-compatible phenomenology
