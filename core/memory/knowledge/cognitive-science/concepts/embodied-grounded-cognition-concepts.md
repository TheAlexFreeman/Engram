---

created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - concepts-synthesis-agent-implications.md
  - basic-level-categories-asymmetry.md
  - ../../philosophy/phenomenology/varela-thompson-rosch-embodied-mind.md
---

# Embodied and Grounded Cognition: Concepts and the Body

## The Grounding Problem

Classical cognitive science assumed that concepts can be fully specified as abstract symbol structures manipulated by formal rules, with no necessary connection to sensory-motor experience. This generates the **symbol grounding problem** (Harnad, 1990):

> How do abstract symbols acquire meaning if they are defined only in terms of other abstract symbols?

A dictionary definition of "red" using words like "a colour similar to blood" requires knowing what blood looks like, what similarity is, etc. You cannot ground all meanings purely in other symbols without eventually requiring symbols to connect with something non-symbolic — typically perception and action.

**Embodied cognition** (the broad research program) argues that cognition is grounded not in abstract, disembodied representations but in the sensorimotor systems of a body interacting with an environment.

---

## Barsalou's Perceptual Symbol Systems (1999)

Lawrence Barsalou's most influential theoretical proposal is that **perceptual symbol systems** form the basis of all conceptual representation.

**Core claims:**
1. **Perceptual simulations constitute symbols:** When you perceive a hammer, multimodal neural states are activated (visual form, weight sensation, grip affordance, anticipated motion). A **perceptual symbol** is a schematic record of such neural states — a partial re-activation of the original perceptual pattern.
2. **Concepts are simulators:** A concept is a collection of perceptual symbols plus a simulator that can run imaginative simulations using those symbols. The concept "hammer" is a simulator that activates visual, haptic, proprioceptive, and action-motor patterns.
3. **Thinking is running simulations:** To think about a hammer being used to drive a nail, you run a perceptual simulation — a "mental movie" involving sensorimotor scripts.
4. **Abstract concepts are grounded in bodily states too:** Even abstract concepts like "justice" or "freedom" are grounded in emotional/bodily states, social scenarios, and spatial metaphors (e.g., "justice is balance," "freedom is open space").

**Evidence for perceptual symbol systems:**
- **Imagery effects:** Mental rotation of abstract shapes activates visual cortex in proportion to rotation angle.
- **Conceptual cueing of perception:** Hearing the word "eagle" speeds detection of eagle-like shapes; hearing "dog" slows it (conceptual preparatory simulation affects visual processing).
- **Affordance-based classification:** People judge objects that share an action affordance (e.g., both gripped with the right hand) as more similar, even when controlling for perceptual features.

---

## Glenberg and Kaschak: Action Compatibility Effects

**Glenberg & Kaschak (2002)** demonstrated the **Action-sentence Compatibility Effect (ACE):**

Subjects read sentences like:
- "Randy delivered the pizza to you" (action toward subject — toward body)
- "You delivered the pizza to Randy" (action away from body)

Then judged whether the sentence made sense by moving their hand toward or away from them. Reading comprehension was **faster when the response movement direction matched the sentence direction** (toward-toward; away-away).

**Interpretation:** Understanding the sentence requires simulating the described action, which partially activates the motor program for the described movement. This motor simulation facilitates (or interferes with) the physical response depending on compatibility.

**What this shows:** Sentence comprehension is not purely symbolic; it involves sensorimotor simulation. This was replicated many times and extended to more abstract language.

---

## Strong vs. Weak Embodied Cognition

The field has moved to distinguish positions:

**Strong (radical) embodiment:**
- Cognition cannot be separated from the body and environment.
- All concepts are perceptually grounded.
- There are no amodal abstract representations whatsoever.
- The brain is only a mediator between body and environment; "mind" is the whole system.

**Weak (moderate) embodiment:**
- Embodied representations are an important component of cognition, but not the whole story.
- Abstract concepts may involve metaphorical mappings from embodied domains, but there may also be genuinely amodal representations.
- The motor system and somatosensory cortex participate in conceptual processing without fully constituting it.

Most of the empirical work supports a weak embodied cognition claim. There is substantial evidence for sensorimotor involvement in conceptual tasks, but also evidence for abstract, amodal representations (especially in language tasks with heavy syntactic demands).

---

## The Grounding Gap in Language Models

LLMs represent a case study in **disembodied cognition:**

- **Input is purely linguistic:** Training data is text. The model has never seen, touched, or manipulated any object.
- **No sensorimotor states:** There is no body, no proprioception, no visual cortex, no motor cortex.
- **No simulation capacity (in the embodied sense):** The model cannot "run a simulation" of what it would feel like to grip a hammer.

**What this implies for LLM conceptual knowledge:**
- LLMs can capture **distributional** properties of concepts — how words about hammers co-occur with words about striking, nails, carpentry, force, handle.
- LLMs cannot capture **phenomenal** properties — what a hammer *feels* like when you grip it, the tactile feedback, the resistance of the nail, the visual-motor coordination.
- In domains where phenomenal/sensorimotor knowledge is essential (procedural skills, haptic tasks, navigation, cooking, surgery), LLM concept representations are systematically impoverished even when linguistic outputs appear fluent.

**The fluency-grounding dissociation:** An LLM can produce perfectly fluent descriptions of how to bake bread without having any sensorimotor grounding for "kneading," "stickiness," "spring," or "crust." This creates a category of *systematic blind spots* that users and the model itself cannot easily detect because the linguistic output appears calibrated.

This connects to the illusion of explanatory depth (see `metacognition/illusion-of-knowing-explanatory-depth.md`): fluent language production may mask absence of grounded understanding.

---

## Implications for Agent Knowledge Files

**Marking the grounding gap:** Knowledge files about physical, procedural, or perceptual domains should note explicitly where sensorimotor grounding would be required for complete understanding. For example:

> "Note: This description of surgical technique draws on textual accounts only. The proprioceptive and tactile dimensions of performing the procedure are not represented."

**Abstract vs. embodied concept partitioning:** Embodied cognition research suggests that the distinction between "abstract" and "concrete" concepts maps onto grounding depth:
- Concrete concepts (chair, running, touching) have rich sensorimotor grounding (in humans).
- Abstract concepts (justice, probability, entropy) are grounded more in language and metaphor, less in direct sensorimotor experience.

LLM representations of abstract concepts may therefore be *relatively more complete* than representations of concrete-procedural concepts, because both humans and LLMs are approximating them primarily through language anyway.

**Trust level implications:** Files drawing on perceptually or procedurally grounded knowledge warrant an additional caveat noting that the agent's understanding is linguistically mediated and may lack crucial sensorimotor detail.
