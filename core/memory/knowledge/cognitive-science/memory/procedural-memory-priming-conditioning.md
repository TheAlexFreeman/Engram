---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: sleep-memory-consolidation.md, hippocampus-memory-formation.md, working-memory-baddeley-model.md
---

# Procedural Memory, Priming, and Conditioning

## Procedural Memory

Procedural memory is the system responsible for learning and executing motor skills, cognitive routines, and habitual behaviors. Its defining feature is **implicitness** — procedural knowledge is expressed through performance, not through verbal report. You can ride a bicycle but cannot describe the micro-adjustments of balance that make it possible.

### Neural substrate

Procedural learning is primarily mediated by the **basal ganglia** (especially the striatum) and the **cerebellum**, not the hippocampus. This is the basis for one of the cleanest double dissociations in neuropsychology:

- **Amnesic patients** (hippocampal damage): Cannot form new episodic memories but can acquire new motor skills. H.M. learned mirror drawing over days, improving with practice, despite having no memory of any practice session.
- **Parkinson's disease patients** (basal ganglia degeneration): Intact episodic memory but impaired skill learning and habit formation.

### Habit learning vs. cognitive mapping

Packard and McGaugh (1996) demonstrated a dissociable parallel between two learning systems in rats:

- **Caudate (striatal) system:** Learns stimulus-response associations — habits, routines, "win-stay" behavior. Slow, incremental, reinforcement-dependent.
- **Hippocampal system:** Learns spatial relationships and flexible cognitive maps — "if X then Y is over there" knowledge that supports novel navigation.

Both systems learn simultaneously, but they compete for behavioral control. Early in learning, the hippocampal system tends to dominate (producing flexible, context-sensitive behavior). With practice, the striatal system takes over (producing fast, automatic, but inflexible behavior).

## Priming

**Priming** is a change in the speed, accuracy, or probability of processing a stimulus due to prior exposure to that stimulus or a related stimulus. It is implicit: the subject need not remember (and often does not remember) the prior exposure.

### Types of priming

| Type | Mechanism | Example |
|------|-----------|---------|
| **Repetition priming** | Prior exposure to the same stimulus | Faster word identification after seeing the word before |
| **Semantic priming** | Prior exposure to a related concept | "Doctor" is recognized faster after seeing "nurse" |
| **Perceptual priming** | Prior exposure in the same modality | Completing word fragments is easier for previously seen words |

### Neural basis

Priming is associated with **decreased** activation in sensory and association cortex — a "sharpening" of neural representations. The same computation runs more efficiently with fewer neurons after priming. This is implemented in the cortex, not in the hippocampal system, which is why priming is intact in amnesia.

### Priming as implicit knowledge

Priming demonstrates that the brain stores and uses information without conscious awareness or explicit retrieval. A primed individual will insist they have no memory of the exposure event but will show measurable behavioral change. This is important for theories of memory: the space of what the system "knows" is larger than the space of what the system can report.

## Classical and Instrumental Conditioning

**Classical conditioning** (Pavlov): An initially neutral stimulus (bell) is paired with an unconditioned stimulus (food) until the neutral stimulus alone produces the conditioned response (salivation). This is mediated by the **amygdala** (for fear conditioning) and the **cerebellum** (for motor timing conditioning like eyeblink).

**Instrumental conditioning** (Thorndike, Skinner): Behaviors that produce reinforcement are strengthened; behaviors that produce punishment are weakened. This is mediated by the **basal ganglia** dopamine system — the canonical substrate for reinforcement learning.

Both forms of conditioning are **intact in amnesia**: patients with no ability to form new episodic memories can still be fear-conditioned and can still learn instrumental responses (though they will not remember the conditioning sessions).

## Agent Memory Implications

### Skills as procedural memory

The Engram system's `core/memory/skills/` directory functions as an analog of procedural memory:

| Biological procedural memory | Engram core/memory/skills/ |
|------------------------------|---------------|
| Implicit, unavailable to verbal report | Loaded automatically, executed without explicit reasoning |
| Expressed through performance | Applied during session operations |
| Slow acquisition through practice | Refined over multiple sessions |
| Resistant to interference from episodic damage | Independent of conversation history |
| Inflexible once established | Risk of over-routinization |

### The habit-flexibility tradeoff

The Packard and McGaugh competition between hippocampal (flexible) and striatal (habitual) systems maps to a genuine design tension:

- **Early adoption:** Agent behavior should be hippocampal-like — flexible, context-sensitive, willing to try novel approaches based on the current situation.
- **Mature operations:** Agent behavior tends toward striatal-like — established routines, standard response patterns, efficient but potentially rigid.

The danger: as skills files accumulate and session routines become well-practiced, the agent may become inflexible — following established patterns even when the situation calls for novel response. This is the procedural memory analog of the "expert blind spot."

### Priming effects in context windows

Priming has a direct analog in LLM context windows: text appearing earlier in context primes the model's processing of later text. This is not explicit retrieval but a statistical influence on token generation.

- **Semantic priming:** A knowledge file about topic X makes the agent more likely to generate responses relevant to X, even in subsequently unrelated conversation.
- **Repetition priming:** Repeated exposure to a particular phrasing or concept makes it more likely to appear in generated text.
- **Negative transfer:** Priming with incorrect or misleading information at the beginning of a context window can bias the entire session.

This connects directly to the memetic security concern: context injection works partly *because* it exploits the priming mechanism. Content that appears in context window early has disproportionate priming influence on all subsequent processing.

## Key References

- Cohen, N.J., & Squire, L.R. (1980). Preserved learning and retention of pattern-analyzing skill in amnesia. *Science*, 210(4473), 207–210.
- Packard, M.G., & McGaugh, J.L. (1996). Inactivation of hippocampus or caudate nucleus with lidocaine differentially affects expression of place and response learning. *Neurobiology of Learning and Memory*, 65(1), 65–72.
- Tulving, E., & Schacter, D.L. (1990). Priming and human memory systems. *Science*, 247(4940), 301–306.
- Squire, L.R. (2004). Memory systems of the brain: A brief history and current perspective. *Neurobiology of Learning and Memory*, 82(3), 171–177.
- Wiggs, C.L., & Martin, A. (1998). Properties and mechanisms of perceptual priming. *Current Opinion in Neurobiology*, 8(2), 227–233.