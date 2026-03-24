---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: ../../mathematics/information-theory/information-bottleneck-deep-learning.md, ../../mathematics/information-theory/mutual-information-channel-capacity.md, transformer-attention-vs-human-attention.md
---

# The Attentional Bottleneck and Limited Capacity

## Kahneman's Resource Model

Donald Kahneman (1973) proposed that attention is a **limited-capacity resource** — akin to mental energy — that can be allocated across tasks. Unlike Broadbent's filter theory, which imagined a binary gate, Kahneman's model portrays attention as a continuous, divisible resource:

- There is a **single pool** of general cognitive effort.
- The current supply of resources varies with **arousal** (physiological activation) — more resources available when alert; fewer when fatigued or bored.
- Resources are allocated by an **allocation policy**, governed partly by automatic tendencies (salient or alarming events attract resources) and partly by voluntary control.
- Tasks have **capacity demands** — some require more resources than others, and demands fluctuate within a task.
- When total demand exceeds available capacity, performance on one or both tasks deteriorates.

**Predictions:** Performance on a concurrent secondary task provides a continuous measure of the residual demand imposed by the primary task (the **dual-task methodology**). Tasks with high cognitive demand should produce more secondary-task interference.

**Dual-task evidence:** Kerr (1973) showed that mental arithmetic while driving degrades driving performance; secondary probe-reaction-time studies (where a simple tone detection task is used as a "measuring device") reliably track cognitive load in primary tasks.

---

## Multiple Resource Theory (Wickens)

Christopher Wickens (1984, 2002) challenged the single-pool assumption. He proposed that resources are organized into **separate pools** along three dimensions:

1. **Modality:** Visual vs. auditory input
2. **Processing code:** Spatial vs. verbal processing
3. **Stage:** Perceptual/central vs. response processing

**Key prediction:** Tasks sharing the same resource pool (e.g., two verbal tasks) interfere more than tasks drawing on different pools (verbal + spatial). A pilot monitoring an auditory radio transmission (auditory-verbal) while adjusting a spatial display (visual-spatial) will suffer less dual-task cost than a pilot simultaneously processing two verbal messages.

**Practical applications:** Human factors and cockpit design exploit multiple-resource theory. Voice-based instructions interfere less with visual navigation than text-based instructions — they draw on different resource pools.

**Limitations:** The number and boundaries of resource pools are debated; the theory sometimes predicts performance with only post-hoc face-validity.

---

## The Attentional Blink

Visual information presented in **Rapid Serial Visual Presentation (RSVP)** — a stream of stimuli at ~100ms intervals — reveals a striking capacity limit:

When subjects must detect two targets (T1 and T2) in the stream, they successfully detect T1 but show a dramatic **deficit in T2 detection** if T2 follows T1 within approximately **200–500ms** (the "lag 2 to lag 5 window"). This blind spot in time is the **attentional blink** (Raymond, Shapiro, & Arnell, 1992).

**Why it occurs:** Several accounts:
- **Bottleneck model (Chun & Potter, 1995):** T1 occupies limited-capacity consolidation; during consolidation, T2 enters a fragile short-term buffer but decays before the bottleneck frees up.
- **Attentional suppression account:** After T1, the system actively suppresses processing to clear the bottleneck; T2 falls in the suppression window.
- **Boost-and-bounce theory (Di Lollo et al., 2005):** Detection of T1 triggers an attentional boost followed by a refractory suppression that "bounces" the next item.

**The lag-1 sparing exception:** When T2 immediately follows T1 (lag 1, ~100ms), it is frequently detected — apparently entering the attentional episode that T1 opened before the blink begins.

**Implications:** The cognitive system cannot process all information in a fast-moving stream, even over brief intervals. Important information that arrives slightly after initial capture will be missed.

---

## The Psychological Refractory Period (PRP)

When two stimuli (S1, S2) require responses (R1, R2), and S2 follows S1 by a short interval (**stimulus onset asynchrony, SOA**), response to S2 is **delayed** — even if the tasks are conceptually unrelated.

This **psychological refractory period** effect suggests that response selection is a serial bottleneck: the cognitive system can only select one response at a time. While R1 is being selected, S2 is held in a queue and its response selection is deferred.

**Pashler's central bottleneck model (1994):** Three stages:
1. *Perceptual processing*: can overlap for S1 and S2 in parallel.
2. *Response selection*: strictly serial — S2 must wait for R1 selection to complete.
3. *Motor execution*: can overlap.

The PRP is not simply a general capacity limit — it is specifically located at the **response-selection stage**.

**SOA modulation:** As SOA decreases (S2 follows S1 more closely), PRP effect increases — the waiting time for S2 grows. As SOA increases, R2 reaction time returns to baseline.

---

## Comparing Human Attentional Limits to Transformer Self-Attention

Human attention has a bottleneck: capacity is limited, selection is serial at the response-selection stage, and rapid sequences produce blinks and refractory periods.

Transformer self-attention operates fundamentally differently:
- **All-to-all comparison:** Every token in the context attends to every other token simultaneously.
- **No temporal bottleneck:** Attention is computed in parallel — there is no "waiting in queue" while another token is processed.
- **Multi-head attention:** Multiple attention heads run in parallel, each attending to different relational patterns — a partial implementation of something structurally analogous to multiple resource pools.
- **No attentional blink analog:** Transformers do not show sequential degradation at fast stimulus rates; capacity limits manifest differently — through reduced accuracy in long contexts (positional encoding degradation, lost-in-the-middle effects) rather than temporal bottlenecks.

The *lost-in-the-middle* phenomenon (Liu et al., 2023) — models perform worse on information in the middle of long contexts — suggests a structural analog to attentional degradation, but the mechanism is positional encoding softmax rather than a capacity resource limit.

---

## Agent Implications

**Long-context management as bottleneck avoidance:** The attentional blink shows that information arriving just after a cognitively demanding item is most at risk of being missed. In long agent sessions with a large number of files loaded, the cognitive-load-equivalent is high — newly encountered files loaded late in a session may suffer from reduced effective integration. Front-loading the most important context early reduces this risk.

**Dual-task costs in agentic workflows:** When agents interleave reasoning with tool calls, they incur PRP-like costs — the response-selection bottleneck applies metaphorically to any serial central process. Decomposing complex tasks into sequential steps that allow one "central process" to complete before the next begins is consistent with human cognitive design.

**Parallel processing within limits:** Multiple resource theory suggests that tasks combining different modalities (e.g., numerical reasoning + textual synthesis) may suffer less interference than tasks within the same resource pool. Designing agent pipelines that interleave qualitatively different operations may reduce mutual interference.
