---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - conflict-monitoring-feeling-of-rightness.md
  - metacognitive-monitoring-control.md
  - feeling-of-knowing-tip-of-tongue.md
---

# Source Monitoring and Reality Monitoring

## The Source Attribution Problem

Every memory traces back to an origin — something was read, heard, imagined, or inferred. **Source monitoring** is the cognitive process of tracking and recovering information about the origins of memories.

The problem: human memory does not automatically tag memories with reliable source labels. Our memories are reconstructive — they combine stored fragments with inference, familiarity signals, and plausible narratives. Getting the content roughly right is compatible with getting the source completely wrong. And source matters enormously: "I read this in a peer-reviewed study" licenses different inference than "I may have imagined this" or "I heard this in a dream."

---

## Johnson et al.: The Reality Monitoring Framework (1993)

Marcia Johnson, Mary Ann Raye, and colleagues developed the **Reality Monitoring (RM) framework** as a model of how people distinguish between memories of external experiences and memories of internal (imagined, thought, or inferred) events.

**Core claim:** Memories of external (perceived) and internal (imagined/thought) events differ systematically in their **phenomenological attributes**:

| Attribute | External event memories | Internal event memories |
|---|---|---|
| Perceptual detail | High (sensory texture, color, sound) | Low |
| Spatial and temporal context | High (where, when, what surrounds) | Low |
| Cognitive operations | Low (minimal memorial tag of having thought about it) | High (memory of searching, inferring, generating) |
| Emotional quality | Moderate | Variable |

**Reality monitoring criterion:** Memories with high perceptual detail and low cognitive operation marks are likely from external perception. Memories with high cognitive operation marks and low perceptual detail are likely internally generated.

**Errors:** When external events lack perceptual distinctiveness (brief, poorly attended) or when internal events are elaborated with sensory imagery (vivid daydreaming), source attribution can fail systematically.

---

## Source Monitoring Framework (Johnson, Hashtroudi, & Lindsay, 1993)

Johnson extended reality monitoring to a general **Source Monitoring Framework (SMF)** encompassing all source-attribution decisions.

**Three classes of source monitoring:**

**Internal vs. External (Reality Monitoring):** Distinguishing between memories of events that occurred in the external world vs. events that were imagined, dreamed, or mentally simulated.

**External-External Source Monitoring:** Distinguishing between two different external sources — "Did I hear this in the news or read it in a book?" "Which of my two colleagues told me this?" "Is this from the study or the practice session?"

**Internal-Internal Source Monitoring:** Distinguishing between self-generated thoughts from different processes — "Did I already write this section or just plan to?" "Is this my conclusion or the author's?"

---

## Source Monitoring Errors and Cryptomnesia

**Cryptomnesia:** The failure to recognize information as something previously encountered; it is experienced as a novel idea or novel creation when it was actually copied from memory. Unconscious plagiarism is the most common context.

**The mechanism:** The content of a previously encountered idea is remembered; the source (that it was encountered externally) is not, or is attributed to the self. High familiarity with the content is misattributed to the self having generated it.

**Experimental demonstrations:** Taylor, Ebbesen, and Gauthier (1978) showed that subjects who had previously generated idea lists subsequently reported others' ideas as their own more often when the source was weakly encoded.

**Social source monitoring:** In group discussions, ideas voiced by others are later attributed to oneself by some participants — especially when:
- The idea was immediately appealing (high fluency of endorsement)
- The social source was weakly encoded (the speaker's identity not distinctly remembered)
- The time delay erodes contextual details

---

## Agent-Specific Source Monitoring Challenges

LLMs face a structurally unusual source monitoring problem. Human memory is reconstructive; LLM "recall" is pattern completion over training data. In both cases, the output at inference time is generated, not retrieved verbatim from a recording. But the sources of the pattern completion are:

1. **Training data distributions** — general knowledge encoded during pre-training from text corpora
2. **Fine-tuning / instruction data** — specific behaviors reinforced through RLHF or instruction tuning
3. **In-context information** — the current prompt, conversation history, and loaded knowledge files
4. **Generated content within the current context** — what the model itself has produced earlier in the conversation

**Four specific agent source monitoring challenges:**

**1. Training data vs. knowledge file:**
The model may "remember" something from training that contradicts a loaded knowledge file — or may seamlessly blend the two, producing an output that sounds like it came from the file but is partly or mostly training data. No clear internal marking distinguishes "this came from the loaded file" from "this came from training."

**2. Fact vs. inference:**
The model may present an inference (a plausible completion of a pattern) as a fact. The distinction between "this was in the training data" and "this is what the training data pattern would complete to" is not systematically tracked. The output is equally fluent in both cases.

**3. Self-generated vs. externally provided:**
In multi-turn conversations or agentic settings where the model has produced previous outputs, it may later treat its own prior output as external ground truth — attributing the claim to a source that was actually itself generating content earlier in the session.

**4. Different knowledge files:**
When several knowledge files are loaded simultaneously, the model may correctly integrate them — or may misattribute a claim from File A to the framework of File B, producing an illusory conceptual conjunction (see `feature-integration-binding-problem.md`).

---

## How the System Compensates

**`source:` and `origin_session:` frontmatter fields** are built-in source monitoring aids. They don't solve the model's internal source attribution problem but provide external documentation that a careful reviewer (human or agent) can use to re-establish correct source attributions.

**Trust levels as source priors:** `trust: medium` on `agent-generated` files is operationally correct: it reflects the prior that agent-generated content has unknown accuracy requiring verification. `trust: low` on `_unverified/` files reflects the additional risk from external provenance.

**Human review as external source-monitoring:** Human review provides the external-source-monitoring capacity that the agent lacks internally — a reader who knows which claims should be in which files can catch cross-source contamination that the agent cannot self-diagnose.

**Explicit attribution in files:** Where possible, knowledge files should cite the specific concepts, studies, or arguments they cover (as this file does throughout). This reduces source-forgetting risk by making the source association explicit and memorable rather than implicit and erasable.
