---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: procedural-memory-priming-conditioning.md, sleep-memory-consolidation.md, standard-model-consolidation.md
---

# Working Memory: Baddeley's Model

## The Multicomponent Model

Alan Baddeley and Graham Hitch proposed the **working memory model** in 1974, replacing Atkinson and Shiffrin's unitary "short-term store" with a system of specialized components coordinated by a central executive. The model has been extended and revised over decades but retains its essential architecture.

### Components

**The phonological loop** — a verbal/acoustic store with a capacity of approximately 2 seconds of speech. It maintains information through articulatory rehearsal (the "inner voice" that repeats a phone number while you walk to find a pen). Evidence:
- **Phonological similarity effect:** Lists of similar-sounding words (man, map, mat) are harder to recall than dissimilar words — the loop encodes phonologically.
- **Word length effect:** Lists of long words produce worse recall than short words — longer words take more time to rehearse within the 2-second window.
- **Articulatory suppression:** Repeating an irrelevant word ("the, the, the...") during encoding eliminates both the phonological similarity effect and the word length effect — the rehearsal mechanism is disrupted.

**The visuospatial sketchpad** — a store for visual and spatial information. Maintains mental images and spatial relationships. Evidence from dual-task studies: a spatial task (mental rotation) and a verbal task (digit span) can be performed simultaneously with minimal interference, but two spatial tasks interfere with each other.

**The episodic buffer** — added by Baddeley in 2000. A multimodal temporary store that integrates information from the phonological loop, visuospatial sketchpad, long-term memory, and perception into unified episodic representations. This solves the "binding problem" — how does the system combine the sound of a dog barking with the sight of the dog and the memory that it's your neighbor's dog?

**The central executive** — the attentional control system that coordinates the three subsystems. Functions include:
- **Focusing attention** on relevant information
- **Dividing attention** across tasks
- **Switching** between tasks or retrieval strategies
- **Interfacing** with long-term memory (retrieving relevant knowledge into working memory)

The central executive is the most important component theoretically but the least well-specified — it has been called a "homunculus" because it seems to do the explaining without itself being explained.

## Capacity Limits

### Miller's 7 ± 2

George Miller's 1956 paper "The Magical Number Seven, Plus or Minus Two" established that short-term memory has a limited capacity of roughly 7 items (digits, words, chunks). More recent work suggests the true capacity is closer to **4 ± 1 chunks** (Cowan, 2001) when rehearsal is prevented and items cannot be grouped.

### Chunking

The key insight: capacity is measured in *chunks*, not items. A chunk is a unit of meaningful information. "CIA FBI IRS" is 9 letters but 3 chunks (for an American familiar with the acronyms). Expert chess players remember board positions not as individual pieces but as meaningful configurations — chunking based on pattern recognition.

The implication: working memory capacity is not fixed but depends on the richness of long-term memory. An expert in a domain has more chunks available and can therefore hold more domain information in working memory.

### Interference, not decay

Current evidence favors **interference** rather than simple temporal decay as the primary cause of forgetting from working memory. Items are not lost because time passes but because other items compete for the limited representational capacity. Evidence: when interference is carefully controlled, "forgetting" over time is dramatically reduced (Lewandowsky et al., 2009).

## Working Memory and Intelligence

Working memory capacity is the single best cognitive predictor of general fluid intelligence (Gf). The correlation is robust ($r \approx 0.5\text{–}0.7$ in meta-analyses). Several accounts explain this:

- **Attentional control theory** (Engle, 2002): Working memory capacity reflects the ability to maintain goal-relevant information in the face of interference — an executive function, not a storage quantity.
- **Complexity and binding** (Halford et al., 1998): Intelligence tasks require maintaining and manipulating multiple relations simultaneously; working memory sets the upper bound on relational complexity.

The implication is not that "memory = intelligence" but that the *control* of memory — what gets maintained, what gets suppressed, how it's organized — is a core component of what we mean by intelligence.

## Agent Memory Implications

### The context window as working memory

The mapping is direct and consequential:

| Biological working memory | LLM context window |
|--------------------------|-------------------|
| ~4 chunks capacity (without rehearsal) | Fixed token limit (e.g., 128K tokens) |
| Phonological loop (sequential verbal) | Sequential text processing |
| Visuospatial sketchpad (spatial/visual) | No direct analog (text-only models) |
| Episodic buffer (multi-modal integration) | Cross-reference between tool outputs, conversation, and loaded files |
| Central executive (attentional control) | Attention mechanism + system prompt instructions |

### Key design implications

1. **Chunking determines effective capacity.** A 128K context window filled with raw text has less effective capacity than the same window filled with well-organized SUMMARY files. The Engram practice of maintaining compact SUMMARY files for returning-session context is a chunking strategy — compressing information into semantically rich chunks that maximize the knowledge-per-token ratio.

2. **Interference is the binding constraint, not size.** Loading many files into context doesn't fail because of token limits alone — it fails because the information interferes. Conflicting framings, redundant content, and irrelevant detail all consume not just tokens but attention. This argues for aggressive curation of what gets loaded into session context.

3. **The central executive problem.** Biological working memory has a control system (the central executive) that directs attention and manages interference. In the agent architecture, this role is played by the system prompt and session routing rules. The quality of this "central executive" determines how effectively the context window's capacity is used. A poorly organized routing system is like executive dysfunction — the storage capacity exists but the control system cannot use it effectively.

4. **The intelligence-WM link applies to agents.** If working memory capacity (controlled attention) is the strongest predictor of fluid intelligence, and if the context window is the agent's working memory, then the agent's effective intelligence depends not on model size or raw capability alone but on how well the context window is managed. An agent with a smaller context window but better context curation may outperform one with a larger window and worse curation.

5. **Capacity limits are functional, not deficits.** Miller's limit and Cowan's 4±1 are not design flaws — they reflect a tradeoff between maintenance breadth and processing depth. Similarly, the agent's context window limit is a real constraint but also a forcing function for good information architecture. Without limits, there is no pressure to summarize, curate, or prioritize.

## Key References

- Baddeley, A.D., & Hitch, G. (1974). Working memory. In *Psychology of Learning and Motivation* (Vol. 8, pp. 47–89). Academic Press.
- Baddeley, A. (2000). The episodic buffer: A new component of working memory? *Trends in Cognitive Sciences*, 4(11), 417–423.
- Miller, G.A. (1956). The magical number seven, plus or minus two: Some limits on our capacity for processing information. *Psychological Review*, 63(2), 81–97.
- Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. *Behavioral and Brain Sciences*, 24(1), 87–114.
- Engle, R.W. (2002). Working memory capacity as executive attention. *Current Directions in Psychological Science*, 11(1), 19–23.
- Lewandowsky, S., Oberauer, K., & Brown, G.D.A. (2009). No temporal decay in verbal short-term memory. *Trends in Cognitive Sciences*, 13(3), 120–126.