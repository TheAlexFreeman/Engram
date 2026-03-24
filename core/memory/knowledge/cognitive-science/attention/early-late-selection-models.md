---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: ../concepts/exemplar-theory-hybrid-models.md, ../../software-engineering/systems-architecture/concurrency-models-for-local-state.md, transformer-attention-vs-human-attention.md
---

# Early, Late, and Attenuation Models of Attentional Selection

## The Central Problem

Perception delivers far more information than the cognitive system can process fully. The question addressed by attentional selection models is: **at what stage does the bottleneck occur?** Does the system discard irrelevant information early (before semantic analysis) or late (after full processing)?

The debate was sparked by Cherry's (1953) **dichotic listening paradigm**: participants wearing headphones hear two different messages simultaneously — one in each ear — and are asked to shadow (repeat aloud) one channel while ignoring the other. Subjects can track the attended message fluently but report almost nothing about the content of the unattended message, though they do notice physical changes (gender shift, replacement by pure tones).

---

## Broadbent's Filter Theory (Early Selection)

Donald Broadbent (1958) proposed the first systematic model in *Perception and Communication*. The model has three components:

1. **Sensory store:** All incoming stimuli are briefly held in parallel in a pre-attentive buffer (now identified with iconic/echoic memory).
2. **Selective filter:** A bottleneck filter selects one channel on the basis of **physical features** (spatial location, pitch, intensity) and passes that channel for full processing. The unattended channel is blocked — it never reaches semantic analysis.
3. **Limited-capacity channel:** The selected channel's information proceeds to higher-level (semantic) processing.

**Prediction:** Information from the unattended ear should be entirely lost — no semantic content should be detectable from the unattended channel.

**Evidence for:** Subjects in dichotic listening cannot recall content from the shadowed channel; they are unaware of language changes in the unattended ear.

**Challenge: The cocktail party effect.** Cherry's paradigm revealed a critical failure: subjects *do* notice their own name in the unattended channel. Moray (1959) showed that ~33% of subjects noticed their name even when it was in the unattended ear. Broadbent's blocking filter cannot explain this — the name must have been semantically processed to the point where it triggered salience.

---

## Treisman's Attenuation Model

Anne Treisman (1960) modified Broadbent's model to accommodate the cocktail-party effect:

The filter does not **block** the unattended channel but **attenuates** it — reduces its signal strength. Semantic analysis proceeds on both channels, but the unattended channel is processed at a reduced activation level.

**Dictionary units** (semantic representations) have activation thresholds. High-frequency, personally significant, or contextually relevant words have **lower thresholds** — they can be activated even by an attenuated signal. Low-salience words require a stronger signal and are lost when attenuated.

This explains the cocktail party effect: one's own name has a very low threshold (it has been deeply associated with self-relevance) and can be detected even from an attenuated, unattended channel.

**Treisman's empirical test:** Subjects shadowing a message that abruptly switches ears (the target sentence continues on the other ear) spontaneously follow the message across ears — demonstrating that semantic content, not just physical location, guides attention. This is incompatible with pure physical filtering.

---

## Deutsch-Norman Late Selection

Deutsch and Deutsch (1963), revised by Norman (1968), proposed the most extreme alteration: **selection occurs after full semantic processing**.

All stimuli are fully analyzed semantically and activate their dictionary units to a degree proportional to **pertinence** (importance given current goals). Selection for conscious awareness and response is governed by this pertinence weighting — not by early gating.

**Prediction:** Even unattended words are fully processed; only the subsequent selection stage limits what reaches awareness and memory.

**Evidence:** Newstead and Dennis (1979) showed semantic priming from unattended words — an unattended word "money" facilitated responses to semantically related targets — suggesting full processing before selection occurs. Johnston and Heinz (1978) found that attentional selectivity depends on task demands (physical vs. semantic discrimination), consistent with flexible selection timing.

**Problem:** Late selection models seem metabolically wasteful — why apply full semantic processing to everything? They had limited empirical traction in explaining the strong selectivity of attentional filtering.

---

## Lavie's Perceptual Load Theory (Synthesis)

Lavie (1995) reconciled the debate with **perceptual load theory**:

- When the attended task imposes **high perceptual load** (uses up the processing capacity of the perceptual system), little capacity remains for unattended stimuli — effectively early selection.
- When the attended task imposes **low perceptual load**, spare capacity automatically processes unattended stimuli — effectively late selection.

This means both early and late selection occur, but under different conditions. The filtering stage is flexible, not fixed.

**Empirical test:** Distractors produce interference (cost to target discrimination) when perceptual load is low but not when it is high. This has been replicated across hundreds of studies.

---

## Synthesis: What the Debate Established

| Model | Filter stage | Mechanism | Unattended processing |
|---|---|---|---|
| Broadbent (early) | Physical features, pre-semantic | Block | None |
| Treisman (attenuation) | Semantic, but weakened | Attenuate | Partial (threshold-dependent) |
| Deutsch-Norman (late) | Post-semantic response selection | Pertinence weighting | Full |
| Lavie (load theory) | Variable | Capacity allocation | Load-dependent |

The enduring insight: attention is not an all-or-nothing gating system. Unattended information is processed to varying degrees depending on the processing demands of the attended task and the salience/pertinence of the unattended information.

---

## Agent Implications

**Context loading as selective attention:** When the agent loads multiple knowledge files into context, not all content in those files receives equal "processing." Files that are most relevant to the current query (low threshold, high pertinence) effectively receive more processing depth. Peripheral content in a file may be attenuated — present in the context window but not effectively integrated into the response.

**The cocktail party phenomenon for agents:** Even within a dominantly attended knowledge file, highly salient unexpected content — strong contradictions, directly relevant proper names, surprising statistics — will capture processing even when that content is in a less-attended portion of the context. Designing attention-grabbing structural cues (formatted alerts, explicit headers) exploits this.

**Load-dependent context quality:** When a query is highly complex (high load), peripheral context is automatically filtered out even if nominally present. High-complexity tasks benefit from *narrower* context (fewer files, more relevant content) rather than broader context that overwhelms capacity.
