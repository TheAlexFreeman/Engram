---

created: '2026-03-20'
origin_session: unknown
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - gestalt-productive-thinking-functional-fixedness.md
  - relevance-realization-synthesis.md
  - convergent-partial-theories-attention-salience.md
---

# The Frame Problem: Minsky, Dreyfus, and the Limits of Formalized Relevance

## The Frame Problem as a Window onto Relevance

The frame problem — initially a narrow technical puzzle in AI planning — turned out to be one of the deepest unsolved problems in cognitive science and philosophy of mind. At its core it asks: *how can any finite system, in real time, determine which aspects of its situation are relevant to a given action without explicitly checking everything?* Vervaeke's Theory of Relevance Realization names this the **relevance problem** and treats the frame problem as its computational instantiation. Understanding the frame problem illuminates why relevance is genuinely hard — and why current AI systems have not solved it.

---

## McCarthy and Hayes (1969): The Technical Frame Problem

John McCarthy and Patrick Hayes introduced the frame problem in "Some Philosophical Problems from the Standpoint of Artificial Intelligence" (1969). Their concern was narrow: how to represent in a formal logical system *what remains constant* when an action is performed.

**Example**: If a robot picks up a block, the block's position changes. But what else? The color of the block stays the same. The number of objects in the room stays the same (modulo the pick-up). The robot's location stays the same (perhaps). A formal situation calculus description requires *explicit axioms* stating what each action *does not* change — "frame axioms". For a world with $n$ objects and $m$ actions, the number of required frame axioms is $O(n \times m)$: for every action, state which properties of every object it leaves invariant.

**The explosion**: Even for simple toy worlds, the number of frame axioms becomes unmanageable. Real-world environments involve millions of objects and unboundedly many possible actions. Writing frame axioms for each — even if possible in principle — is not how biological systems handle the problem, and it does not scale.

---

## Minsky's Frames: A First Attempt at Mechanizing Relevance

Marvin Minsky's "A Framework for Representing Knowledge" (1975) proposed **frames** as a data structure for encoding typical, schematized knowledge about recurring situations:

- A "chair frame" encodes default assumptions: has-seat, has-legs, made-for-sitting, located-in-room, etc.
- When a new situation is recognized as a chair situation, the frame is instantiated, and all defaults are inherited unless explicitly overridden
- Frames are hierarchically organized: the chair frame inherits from the furniture frame which inherits from the physical-object frame

**What frames accomplish**: They dramatically reduce the need for explicit inference. If I am in a restaurant, activating the restaurant frame provides default assumptions about the surrounding structure (tables, menu, waiter, bill) without computing them from scratch. The frame is a cached relevance assignment for recurring situation-types.

**The frame-selection problem**: But which frame should be activated for a given situation? The world arrives as raw perceptual data; recognizing it as a "restaurant situation" already requires knowing which features of the data are relevant to frame selection. Frame selection presupposes a prior relevance judgment. A program that selects frames based on recognized features requires other frames — or rules, or heuristics — for recognizing those features. This is the beginning of an infinite regress:

> To determine which frame is relevant, you need a relevance criterion. To apply that criterion, you need to know which features are relevant to applying it. To determine that, you need another relevance criterion...

Minsky's frames ameliorate the frame-axiom explosion but do not solve the underlying problem — they push it back one level.

---

## Dreyfus's Critique: The Frame Problem as a Fundamental Impossibility for Disembodied AI

Hubert Dreyfus's *What Computers Can't Do* (1972) and its successor *What Computers Still Can't Do* (1992) argued that the frame problem exposed a fundamental architectural limitation of classical (symbolic) AI, not merely a technical difficulty awaiting a better solution.

**The phenomenological diagnosis**: Drawing on Heidegger, Merleau-Ponty, and the Gestalt psychologists, Dreyfus argued that human beings are never "disembodied" perceivers surveying a neutral world and deciding what is relevant. They are *already* engaged with the world; their embodied, socially situated, goal-oriented being-in-the-world means that relevance is given prereflectively — it is structured into perception itself before explicit deliberation begins.

- A chess player does not survey the board neutrally and then compute which squares are relevant. Board perception is trained relevance: certain configurations *look like* threats, opportunities, pressure points — the relevance is in the seeing.
- A cook does not abstract over all properties of the chicken before deciding what cutting action to take. The body knows what to do in a way that bypasses explicit relevance computation.

**The disenchantment of formalization**: For a formal system, *everything must be explicitly represented*. There is no prereflective background — no unarticulated, embodied, situationally-specific sensitivity to what matters. This is precisely what formalisms lack and what human cognition presupposes. Any attempt to reproduce relevance sensitivity in a formal system must enumerate the elements of the background, but the background is by nature resistant to complete enumeration — it is what makes enumeration possible.

**The "what-is-relevant-to-relevance" problem**: Dreyfus pressed the regress: to build a relevance-checker, you need to specify what inputs to the checker are relevant. But what inputs are relevant to a relevance-checker is itself a relevance problem. There is no Archimedean standpoint outside relevance from which to design a relevance module.

---

## The Combinatorial Explosion: Why Exhaustive Search Cannot Solve Relevance

The computational core of the problem:

In a world with $n$ features (size, color, position, temperature, owner, material, age, ...), the number of possible feature-conjunctions is $2^n$. For a real environment, $n$ is effectively unbounded. The number of potentially *relevant* feature-combinations for an action is a subset of $2^n$ — but computing that subset requires evaluating each conjunction for relevance, which requires... solving the relevance problem.

Even with modern compute, exhaustive search over this space is not how organisms operate. Organisms must have a mechanism that generates *candidate relevance judgments* efficiently — that is, that operates on the relevance space in a way that does not explode exponentially. Whatever that mechanism is, it is not explicit rule-following over an enumerated feature space. This is the *existence proof* that relevance is not formalizable in the classical sense.

**Statistical learning as a partial answer**: Modern neural networks learn statistical regularities over large corpora and produce feature representations in learned embedding spaces. These representations *implicitly encode relevance* in the sense that similar-in-the-embedding-space means similar-in-the-inputs-that-matter-for-prediction. But this is relevance relative to the training distribution. Out-of-distribution situations — novel environments, unexpected contexts, adversarial inputs — expose the machinery's failure to generalize relevance judgments correctly. The frame problem reappears as the distribution shift problem.

---

## Vervaeke's Restatement: The Relevance Problem

Vervaeke (following Dreyfus and independently of the technical AI literature) reframes the frame problem as the **relevance problem** — a fundamental puzzle about any cognitive system:

*How does a finite cognitive system, operating in real time in an open-ended environment, identify what matters without either (a) exhaustive search through all possible relevance assignments, or (b) rigid commitment to a fixed relevance template that cannot adapt?*

The frame problem is the relevance problem appearing in formal systems. The insight-block problem is the relevance problem appearing in human problem-solving. The dysrationalia problem is the relevance problem in human judgment. Confirmation bias, hallucination, and LLM distribution shift are all the relevance problem in different registers.

Vervaeke's answer — the opponent-processing, self-organizing account (see `opponent-processing-self-organizing-dynamics.md`) — is intended as a solution to the relevance problem across all its instantiations.

---

## Cross-links

- `gestalt-productive-thinking-functional-fixedness.md` — the empirical precursor: humans exhibit frame-like rigidity (functional fixedness); insight demonstrates natural "frame switching"
- `convergent-partial-theories-attention-salience.md` — attention and salience theories are all partial, frame-relative relevance selectors; they face the same regress at a higher level
- `opponent-processing-self-organizing-dynamics.md` — Vervaeke's positive theory of how biological systems escape the frame problem without exhaustive search
- `knowledge/philosophy/phenomenology/heidegger-being-in-world.md` — Dreyfus's critique draws directly on Heidegger's disclosure/ready-to-hand analysis
- `relevance-realization-synthesis.md` — how the frame problem maps onto AI system limitations today
