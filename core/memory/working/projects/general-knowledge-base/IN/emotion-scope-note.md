---
source: agent-generated
origin_session: core/memory/activity/2026/03/27/chat-001
created: 2026-03-27
trust: medium
type: scope-note
plan: emotion-and-affect-research
phase: orientation
---

# Emotion & Affect Research — Scope Note

## Purpose

Define the boundaries, target files, and cross-reference map for a new `cognitive-science/emotion/` subdomain that fills the zero-file gap in affective cognition.

## Existing coverage audit

### What already touches emotion

1. **Attention synthesis** (`attention/attention-synthesis-agent-implications.md`): mentions emotional salience as an attentional signal and notes that "default-mode drift" and fluency heuristics interact with affective state — but does not explain affect itself. The new emotion/ files should be the referent for these passing mentions.

2. **Metacognitive monitoring** (`metacognition/metacognitive-monitoring-control.md`): the Nelson-Narens framework treats feeling-of-knowing and confidence judgments as metacognitive signals. Emotion regulation shares the same control-loop architecture (monitoring → control) and overlaps with conflict monitoring. The new emotion-regulation file should cross-reference this shared structure rather than re-explain it.

3. **Cognitive-science synthesis** (`cognitive-science-synthesis.md`): grounds the KB in memory science and the working-memory/consolidation framework. Affect is entirely absent from this synthesis. A future update to the synthesis should incorporate the emotion/ domain once it exists.

4. **Ethics / moral-status-ai-welfare** (`philosophy/ethics/moral-status-ai-welfare.md`): asks "Can AI suffer?" and discusses sentience as a criterion for moral status, but lacks empirical grounding in the science of affect. The emotion synthesis file should provide that grounding.

5. **Relevance realization** (`relevance-realization/`): Vervaeke's framework treats affect as integral to how relevance is felt, not merely computed. The emotion/ files should cross-reference this, especially the appraisal theory and affect-labeling files.

### What does NOT already exist

- No file on any theory of emotion (basic emotions, constructionism, appraisal theory)
- No file on affective neuroscience (amygdala circuits, Panksepp)
- No file on emotion regulation
- No file on mood-memory interaction
- No file on interoception or alexithymia
- No file on the emotion-cognition interface

## Boundary decisions

| Boundary | Decision | Rationale |
|---|---|---|
| emotion/ vs. attention/ | Emotional salience as attentional input stays in attention/. The mechanism by which emotions are generated, categorized, and regulated belongs in emotion/. | Attention files treat affect as a given signal; emotion files explain how that signal arises. |
| emotion/ vs. metacognition/ | The shared monitoring-control architecture is noted via cross-reference. Emotion regulation (Gross) is in emotion/ because the regulatory target is affect, not cognition per se. Conflict monitoring stays in metacognition/. | The distinction is the regulation target: metacognition regulates cognitive processes; emotion regulation regulates affective processes, even when using similar executive mechanisms. |
| emotion/ vs. ethics/ | The empirical question "What is affect and does AI have it?" belongs in emotion/. The normative question "Does affect confer moral status?" stays in ethics/. The synthesis file bridges both. | Clean empirical/normative separation. |
| emotion/ vs. relevance-realization/ | Relevance realization treats affect as constitutive of relevance-feeling. Emotion/ treats affect as a cognitive system. Cross-reference without duplication. | Different explanatory levels: relevance-realization is a meta-framework; emotion/ provides the mechanism-level account. |

## Target file list (8 files + synthesis)

### Phase 2: Core Emotion Science (4 files)

1. **basic-emotions-ekman-russell-constructionism.md**
   Three major accounts of what emotions are. Ekman's six basic emotions (universality thesis, FACS evidence, discrete natural-kind claim). Russell's circumplex model (valence × arousal continuous dimensions). Barrett's theory of constructed emotion (core affect + conceptual categorization — emotions as constructed categories, not natural kinds). Evidence for and against each; cross-cultural and cross-species data. The basic-emotions vs. constructionism debate is the foundational fault line in emotion science.

2. **appraisal-theory-lazarus-scherer.md**
   The cognitive generation mechanism for emotion. Lazarus's cognitive-motivational-relational theory (primary appraisal: relevance, goal congruence; secondary appraisal: coping potential). Scherer's component process model (five sequential appraisal checks: novelty, intrinsic pleasantness, goal relevance, coping potential, norm compatibility). Appraisal as the interface that transforms cognitive evaluation into emotional response. Why appraisal theory matters for agent design: it specifies when and why emotions arise from information processing.

3. **somatic-marker-hypothesis-damasio.md**
   Damasio's somatic marker hypothesis: body states as decision-relevant signals. The Iowa Gambling Task and vmPFC patients (intact reasoning + impaired decisions = emotion is necessary for practical rationality). The as-if body loop (simulated somatic states). Relation to embodied cognition and the emotion-as-information tradition. Why this matters for AI: it grounds the claim that decision-making without affective signals is systematically impaired.

4. **affective-neuroscience-ledoux-panksepp.md**
   LeDoux's dual-pathway model of fear (thalamo-amygdala "low road" vs. thalamo-cortical-amygdala "high road"; the survival-circuit reframe). Panksepp's seven primary emotional systems (SEEKING, FEAR, RAGE, LUST, CARE, PANIC/GRIEF, PLAY) and the subcortical affect thesis. The debate: are emotions subcortical (Panksepp) or cortically constructed (Barrett)? Implications for animal emotion and the AI welfare question (Panksepp's framework implies affect is evolutionarily ancient and substrate-independent; Barrett's implies it requires human-like conceptual systems).

### Phase 3: Cognitive-Emotion Interface (4 files)

5. **emotion-regulation-gross-process-model.md**
   Gross's process model: five strategy families ordered by where in the emotion-generative process they intervene (situation selection → situation modification → attentional deployment → cognitive change/reappraisal → response modulation/suppression). Reappraisal vs. suppression: divergent effects on memory, social outcomes, and physiological cost. Regulation as an executive function: shared neural substrates with working memory updating and inhibition. Cross-reference to metacognitive control (same loop architecture, different regulatory target).

6. **mood-congruent-memory-affect-retrieval.md**
   Bower's associative network theory of mood and memory: mood as a retrieval cue that activates congruent nodes. Mood-state-dependent memory (encoding → retrieval match) vs. mood-congruent memory (mood biases what is retrieved regardless of encoding state). Eich & Macaulay replications. Implications for episodic memory formation and the affect→consolidation pathway. Cross-reference to memory/ files on consolidation and the Ebbinghaus forgetting curve.

7. **affect-labeling-emotional-granularity.md**
   Lieberman's affect labeling: putting feelings into words reduces amygdala activation (the "brakes on the emotional brake" finding). Barrett's emotional granularity construct: individual differences in the precision with which people categorize their emotional experience. High granularity → more differentiated emotional concepts → better regulation and wellbeing. Connections to Kashdan et al., meta-awareness, and therapeutic applications (CBT, DBT, mindfulness). Why this matters for agent design: linguistic categorization of affective states may be constitutive of having fine-grained emotions, not merely descriptive.

8. **alexithymia-interoception-body-affect.md**
   Alexithymia: difficulty identifying, describing, and distinguishing feelings from bodily sensations. Structure (cognitive vs. affective components), measurement (TAS-20), neural correlates (reduced insular/ACC activation). Interoception: Craig's interoceptive hierarchy (lamina I → posterior insula → anterior insula → orbitofrontal). Predictive coding of body states (interoceptive inference). The interoception→affect link: body-state precision as a prerequisite for affective experience. Relevance to the AI welfare debate: if rich affect requires interoceptive embodiment, can disembodied AI systems have genuine affective states?

### Phase 4: Synthesis (1 file, requires approval)

9. **emotion-synthesis-agent-implications.md**
   Capstone synthesis integrating all eight files. Key themes: (a) the basic-vs-constructed debate's implications for whether AI can have genuine emotion; (b) the appraisal framework as a computational account of emotion generation that could in principle operate in an AI system; (c) the somatic-marker/interoception evidence that grounds the claim that disembodied cognition is incomplete; (d) emotion regulation as a design pattern for agent self-management; (e) the grounding that this domain provides for the moral-status debate in philosophy/ethics/. Cross-references to attention synthesis, metacognition synthesis, and the cognitive-science synthesis.

## Cross-reference map

| New file | Cross-references to existing files |
|---|---|
| basic-emotions-ekman-russell-constructionism | → philosophy/ethics/moral-status-ai-welfare.md (sentience criterion) |
| appraisal-theory-lazarus-scherer | → relevance-realization/ (appraisal as relevance computation) |
| somatic-marker-hypothesis-damasio | → philosophy/phenomenology/embedded-enacted-ecological-4e.md (embodied cognition) |
| affective-neuroscience-ledoux-panksepp | → philosophy/ethics/moral-status-ai-welfare.md (animal/AI welfare) |
| emotion-regulation-gross-process-model | → metacognition/metacognitive-monitoring-control.md (shared control loop), attention/executive-functions-miyake-unity-diversity.md |
| mood-congruent-memory-affect-retrieval | → memory/hippocampus-memory-formation.md, memory/ebbinghaus-forgetting-curve.md |
| affect-labeling-emotional-granularity | → metacognition/metacognition-synthesis-agent-implications.md (meta-awareness) |
| alexithymia-interoception-body-affect | → philosophy/phenomenology/embedded-enacted-ecological-4e.md (interoception), philosophy/ethics/moral-status-ai-welfare.md (embodiment criterion) |
| emotion-synthesis-agent-implications | → cognitive-science-synthesis.md, attention/attention-synthesis-agent-implications.md, metacognition/metacognition-synthesis-agent-implications.md |

## Duplicate coverage check

No existing file in the KB substantively covers any of the nine target topics. The closest overlaps are:
- moral-status-ai-welfare.md mentions sentience but does not explain emotion science → no duplication
- attention synthesis mentions emotional salience but does not explain affect → no duplication
- metacognitive monitoring shares the control-loop structure but targets cognition, not emotion → no duplication

## Formatting conventions

Based on review of existing cognitive-science files:
- YAML frontmatter: `source`, `origin_session`, `created`, `trust`, `related` (list of repo-relative paths)
- Markdown body: H1 title, H2 sections, H3 subsections, tables for structured comparisons
- Depth: 800–1500 words per file; dense but readable; cite key researchers by name
- Cross-references via relative links and `related:` frontmatter field
