---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: hippocampus-memory-formation.md, sleep-memory-consolidation.md, working-memory-baddeley-model.md
---

# False Memory and the Constructive Nature of Memory

## Memory as Reconstruction, Not Reproduction

The folk model of memory — a recording that captures and replays events faithfully — is wrong. Memory is **constructive**: it assembles an account of the past from fragments, schemas, and current context. The reconstruction feels like playback, but it is an active inferential process that can introduce errors.

This was first demonstrated systematically by **Frederic Bartlett** in 1932.

## Bartlett's Schema Theory (1932)

Bartlett's *Remembering* used the "repeated reproduction" method: British participants read a Native American folk tale ("The War of the Ghosts") and then recalled it at various delays.

### Key findings

- **Leveling:** Stories became shorter and simpler over successive recalls
- **Sharpening:** Certain vivid or emotionally salient details were preserved or exaggerated
- **Rationalization:** Culturally unfamiliar elements were transformed to fit the participants' expectations. Canoes became boats. Supernatural elements were omitted or rationalized.
- **Assimilation to schema:** The story was progressively reshaped to match the participants' cultural schemas — their expectations about how stories work, what is plausible, what happens in conflicts

### The schema concept

Bartlett proposed that memory uses **schemas** — organized knowledge structures that encode expectations about typical events, objects, and sequences. Schemas serve as frameworks for encoding and retrieval: new information is assimilated into existing schemas, and gaps in memory are filled using schema-based expectations.

This means memory errors are not random — they are **systematic** and **directional**, driven by the schemas available to the rememberer.

## Loftus and the Misinformation Effect

Elizabeth Loftus's research program, beginning in the 1970s, demonstrated how post-event information can be incorporated into memory, creating false memories that are experienced as genuine.

### The misinformation paradigm

1. Participants witness an event (e.g., a car accident video)
2. Later, they receive misleading post-event information (e.g., a question containing the word "smashed" instead of "hit")
3. When tested, participants exposed to misleading information report the event differently — they "remember" more damage, higher speeds, details consistent with "smashed" rather than "hit"

### Loftus and Palmer (1974)

The most cited demonstration: participants who heard "How fast were the cars going when they **smashed** into each other?" estimated higher speeds and were more likely to falsely "remember" broken glass than those who heard "**hit**." The post-event language altered not just the verbal estimate but the visual memory.

### The misinformation acceptance mechanism

How does misinformation become memory?
- **Source monitoring failure:** The misinformation is encoded as part of the event memory because the source (a leading question) is not distinguished from the source (the original perception)
- **Trace alteration:** The original trace may be genuinely modified (reconsolidation-compatible) or supplemented with the new information
- **Social demand:** In some cases, participants may report the misinformation not because they believe it but because they want to be consistent with the questioner

The weight of evidence supports a genuine memory alteration account for many cases — participants show physiological indicators of genuine remembering (pupil dilation, hippocampal activation) for false memories they have accepted.

## The DRM Paradigm: False Memory in the Laboratory

Deese (1959), Roediger and McDermott (1995) developed the **DRM paradigm** — the most widely used laboratory method for studying false memory.

### Method

Participants study lists of words that are all associates of an unstudied **critical lure**:
- List: *bed, rest, awake, tired, dream, wake, snooze, blanket, doze, slumber, snore, nap*
- Critical lure (never presented): **sleep**

### Results

- ~40–55% of participants falsely recall the critical lure
- ~75–80% falsely recognize it in a recognition test
- False recall/recognition of the critical lure is accompanied by "Remember" judgments (autonoetic consciousness) at rates comparable to actually studied words
- Participants are typically highly confident in their false memories

### What DRM reveals

False memories are not produced by guessing or demand characteristics. Participants genuinely experience remembering a word that was never presented. The mechanism: **spreading activation** in semantic memory — the presented words collectively activate the critical lure's semantic representation so strongly that it acquires the properties of a studied item.

This means false memories are a natural consequence of how semantic memory works — associative spreading is the same mechanism that enables efficient retrieval from partial cues (pattern completion). The same process that makes memory useful (content-addressable retrieval, semantic association) makes it prone to constructive errors.

## Source Monitoring Framework (Johnson, Hashtroudi, & Lindsay, 1993)

Many memory errors are not about *what* happened but about *where the information came from.* The **source monitoring framework** proposes that memories do not carry automatic source tags — the source (did I see this, read it, imagine it, dream it?) is inferred from the memory's characteristics:

- **Perceptual detail** → external source
- **Vividness** → likely real event
- **Cognitive operations** → internal source (thought, imagined)

When these inference processes fail — when an imagined event has high perceptual detail, or a read description feels vivid — source misattribution occurs. The content is remembered, but the source is wrong.

### Reality monitoring

A special case: distinguishing between memories of real events and memories of imagined events. This is especially relevant when:
- Imagination is vivid and detailed (as in LLM-generated text)
- The real/imagined distinction depends on subtle qualitative features
- Time has passed and perceptual detail has faded, reducing the basis for discrimination

## Agent Memory Implications

### 1. LLM summaries are schema-driven reconstructions

When the agent writes a session summary, it is performing Bartlett's reconstruction: reducing a complex session to a coherent narrative, assimilating details to its existing schemas about what sessions contain, what knowledge looks like, and what is important.

**Predicted distortion patterns:**
- **Leveling:** Subtle nuances and qualifications are lost in favor of clean statements
- **Sharpening:** Salient or surprising findings are overemphasized
- **Rationalization:** Contradictions or unresolved questions are smoothed over
- **Assimilation:** Session content is framed in terms of existing knowledge categories, potentially missing genuinely novel contributions

These are the same distortion patterns Bartlett documented — and they are inherent to the summarization process itself, not bugs that better prompting can fix.

### 2. The DRM analog in knowledge files

When multiple knowledge files on related topics exist, they collectively "activate" concepts that none of them individually states. An agent reading files on memory science, cognitive maps, and consolidation may construct a "memory" of content about reconsolidation even before reading the reconsolidation file — because the associated concepts are so strongly primed.

This is not hallucination in the pejorative sense — it's the same spreading activation that enables useful semantic retrieval. But it means the agent may represent knowledge file contents inaccurately, incorporating associated concepts that are plausible but not actually stated in the files.

### 3. Source monitoring is critical

The agent must distinguish between:
- Information from verified knowledge files (high trust)
- Information from unverified files (low trust)
- Information generated in the current session (unsourced)
- Information from external tool outputs (variable trust)

The source monitoring framework predicts that these sources will be confused, especially after multiple retrieval and reconsolidation cycles. The trust-weighted retrieval spec (memetic-security 4.2) is a source monitoring aid — it makes source information salient at retrieval time, reducing the probability of source misattribution.

### 4. False confidence is the real danger

DRM participants are highly confident in their false memories. The agent analog: the model will express high confidence in reconstructed "memories" that combine genuine file content with schema-driven interpolation. The fact that a model states something confidently does not distinguish genuine from constructed memories.

This argues for **verification over confidence** — when knowledge claims need to be accurate, verify against the source file rather than relying on the agent's "memory" of the file's content.

## Key References

- Bartlett, F.C. (1932). *Remembering: A Study in Experimental and Social Psychology*. Cambridge University Press.
- Loftus, E.F., & Palmer, J.C. (1974). Reconstruction of automobile destruction: An example of the interaction between language and memory. *Journal of Verbal Learning and Verbal Behavior*, 13(5), 585–589.
- Roediger, H.L., & McDermott, K.B. (1995). Creating false memories: Remembering words not presented in lists. *Journal of Experimental Psychology: Learning, Memory, and Cognition*, 21(4), 803–814.
- Johnson, M.K., Hashtroudi, S., & Lindsay, D.S. (1993). Source monitoring. *Psychological Bulletin*, 114(1), 3–28.
- Loftus, E.F. (2005). Planting misinformation in the human mind: A 30-year investigation of the malleability of memory. *Learning & Memory*, 12(4), 361–366.
- Gallo, D.A. (2010). False memories and fantastic beliefs: 15 years of the DRM illusion. *Memory & Cognition*, 38(7), 833–848.