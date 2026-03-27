---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: vision-language-models-gpt4v-gemini-llava.md, clip-contrastive-vision-language-pretraining.md, audio-language-models-whisper-speech.md
---

# Embodied AI: RT-2, GATO, and SayCan

**Embodied AI** addresses one of the most significant gaps between language model capability and real-world generality: the ability to perceive physical environments and execute physical actions. Over 2022–2023, three landmark systems — **SayCan**, **GATO**, and **RT-2** — established that large pretrained vision-language and language models can be repurposed as robot controllers, with emergent capabilities for instruction-following, task generalisation, and multi-step planning far exceeding prior robot learning approaches.

---

## SayCan: Grounding LLM Planning in Robot Affordances

### Core Idea

**SayCan** (Ahn et al., Google/Everyday Robots, 2022) addresses a fundamental problem: LLMs can reason about what to do but don't know what is *physically feasible*. SayCan combines:

1. **LLM planner:** A large language model that generates candidate action proposals (scored by probability) given the task description
2. **Robot affordance model:** A learned value function that estimates the probability of successfully executing each candidate action in the current environment

The joint scoring:

$$\text{Action}^* = \arg\max_a \underbrace{P_{LLM}(a \mid \text{task, history})}_{\text{LLM score}} \cdot \underbrace{P_{afford}(\text{success} \mid a, \text{state})}_{\text{affordance score}}$$

**"Say" what to do × "Can" you do it.** The LLM provides semantic plausibility; the affordance function provides physical feasibility. The product selects physically viable plans.

### Implementation

- **LLM:** PaLM (540B parameters) — prompted with task description and list of primitive skills; generates likelihood scores for each skill
- **Affordance function:** Trained as a binary success predictor per skill; uses visual observation of the environment
- **Primitive skills:** ~550 pretrained robot skills (pick up X, put X in Y, open drawer, etc.) that the affordance function can evaluate individually
- **Robot:** Mobile manipulation robot (Hello Robot Stretch variant)

### Results and Significance

- Outperforms LLM planning alone (which ignores feasibility) and affordance-only selection (which ignores task coherence) on long-horizon tasks
- Successfully executes 10+ step tasks ("make me a snack using only items that are not salty, but provide some nutritional value")
- **Emergent generalisation:** The LLM generates plans for novel task descriptions not seen during affordance training

**Limitation:** The pipeline is modular — LLM and affordance model are separate; failures in one cascade. The skill library is fixed; novel actions cannot be invented.

---

## GATO: A Generalist Agent

### Multi-Task, Multi-Embodiment Architecture

**GATO** (Reed et al., DeepMind, 2022) is a single Transformer network that performs 604 distinct tasks across multiple modalities and embodiments — simultaneously functioning as a game-playing agent, a robot arm controller, an image captioner, and a chat agent.

**Core insight:** Tokenise *everything* into sequences, train with next-token prediction.

### Tokenisation

GATO flattens all inputs and outputs into a single sequence of tokens:

| Data Type | Tokenisation |
|-----------|-------------|
| Text | BPE text tokens (standard LLM) |
| Images | ViT-style image patch encodings, then discretised to tokens |
| Continuous actions (joint positions, velocities) | Discretised into 1024 bins; each bin = one token |
| Discrete game actions | Direct token |
| Image observations in games | Patch encodings |
| Proprioceptive observations | Discretised continuous values |

**Sequence structure:** Observations from environment alternated with actions taken; the Transformer predicts the next token whether it's a text word, pixel patch ID, or robot joint position.

### Scale and Tasks

- **Parameters:** 1.2B (multiple sizes tested; 1.2B = best reported version)
- **Task domains:** Atari games, simulated robot arm stacking, language-image captioning, natural language question-answering, real robot manipulation
- **Single checkpoint:** All tasks from one model — no task-specific components

### Results and Limitations

**Results:**
- Competent on many tasks (better than specialised expert policies on some Atari games with few-shot prompting)
- Substantially below state-of-the-art on most individual tasks
- Showed task-family patterns: language tasks > game-playing > physical robot tasks

**"Gato is not impressive enough" controversy:** GATO's task performance was below specialised models on nearly every benchmark. DeepMind framed it as a proof-of-concept for generalist agents; critics argued 1.2B parameters cannot be simultaneously expert-level across 600+ tasks.

**Key contribution:** GATO established the *unified tokenisation* paradigm — that heterogeneous action spaces and observation modalities can all be cast into a single sequence prediction problem, with a single model that (partially) handles all.

---

## RT-2: Vision-Language-Action Models

### Architecture: VLA

**RT-2** (Brohan et al., Google DeepMind, 2023) is a **Vision-Language-Action** (VLA) model — a vision-language model directly fine-tuned to output robot actions:

1. **Base model:** PaLI-X (55B) or PaLM-E (562B) — both large multimodal VLMs pretrained on web-scale text+image data
2. **Action tokenisation:** Robot actions (end-effector pose: x,y,z positions + orientation + gripper open/close) are discretised and represented as **text tokens** — e.g., `"128" "091" "035"` corresponds to a specific position bin
3. **Fine-tuning:** The VLM is fine-tuned on robot demonstration data where the "output" is action tokens; internet pretraining knowledge is retained

**Result:** The robot controller speaks the same token language as the VLM. Reasoning capabilities transfer.

### Emergent Capabilities

RT-2 showed remarkable **emergent generalisation** beyond the training distribution:

| Capability | Example | RT-2 | Prior RT-1 |
|-----------|---------|-------|-----------|
| Novel object recognition | "Pick up the Coke can" (different coloured can than in training) | ✓ | ✗ |
| Semantic reasoning | "Move the extinct animal to the purple block" (dinosaur toy) | ✓ | ✗ |
| Multi-step chain-of-thought reasoning | "If I wanted to use this tool to unscrew something, which would I pick?" | ✓ | ✗ |
| Visual analogy | "Put the fruit that monkeys like next to..." | ✓ | ✗ |

These tasks require knowledge transfer from **web pretraining** — semantic understanding of "extinct animals," "what monkeys eat," etc. — applied to physical robot actions. The model does not merely pattern-match to training demonstrations.

### RT-X and Open-Source Robot Data

Alongside RT-2, Google released the **Open X-Embodiment (RT-X) dataset** — 1 million robot demonstrations across 22 robot embodiments from 21 research institutions, covering diverse tasks, environments, and hardware.

**Significance:** RT-X is the ImageNet of robot learning — a large-scale, heterogeneous dataset enabling cross-embodiment learning and benchmarking.

**Cross-embodiment transfer:** Models trained on RT-X data perform better on unseen robot hardware than models trained only on single-embodiment data — suggesting physical interaction knowledge partially generalises across hardware.

---

## Simulation-to-Real and Distributional Challenges

Despite RT-2's successes, significant challenges remain:

### Sim-to-Real Gap

- Simulation offers cheap, scalable data but differs from reality in visual appearance, physics, and contact dynamics
- **Domain randomisation:** Randomise textures, lighting, physics parameters during simulation training — forces policy to be robust to variation
- **Domain adaptation:** Use visual pipelines (image translation; Gaussian splatting from real images) to make simulation look more realistic
- RT-2 partially sidesteps this by training on real demonstrations — but real robot data remains expensive

### Distribution Shift

- VLA models trained on demonstration data struggle when the test distribution deviates: different clutter, different lighting, reversed object positions
- **Catastrophic forgetting risk:** Fine-tuning a large VLM on robot data can reduce language capabilities — RT-2 mitigates by interleaving internet data during fine-tuning

### Long-Horizon Planning

- RT-2 acts step-by-step (each action token is one time-step); no explicit planning beyond what the Transformer can "think forward"
- **Chain-of-thought robot control:** Prompting VLAs to generate intermediate reasoning steps before generating actions improves multi-step success rates (SayCan + RT-2 style hierarchical planning)

---

## The Scaling Hypothesis for Embodied AI

RT-2 and GATO both support the view that **scaling internet-pretrained models transfers physical intelligence**:

- Larger VLMs → better generalization to novel physical scenarios
- Web-scale pretraining → semantic grounding of physical objects and affordances
- Unified tokenisation → single training objective covers both language and action prediction

**The bottleneck:** Robot data, not model size. High-quality physical interaction data is expensive to collect and does not scale like internet text/images. Active research directions include:
- **Teleoperation scaling** (ALoHA, Mobile ALOHA — ACT policy)
- **Synthetic data from simulation + domain randomisation** (Isaac Gym, Genesis physics sim)
- **Video pre-training for physical understanding** (using internet video as implicit robot data)

---

## References

1. Ahn, M. et al. (2022). "Do As I Can, Not As I Say: Grounding Language in Robotic Affordances." *CoRL 2022* (SayCan)
2. Reed, S. et al. (2022). "A Generalist Agent." *Transactions on Machine Learning Research* (GATO)
3. Brohan, A. et al. (2023). "RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control." *CoRL 2023*
4. Padalkar, A. et al. (2023). "Open X-Embodiment: Robotic Learning Datasets and RT-X Models." arXiv 2310.08864
5. Chi, Z. et al. (2023). "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion." *RSS 2023*
6. Zhao, T.Z. et al. (2023). "Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware." *RSS 2023* (ALOHA/ACT)
7. Driess, D. et al. (2023). "PaLM-E: An Embodied Multimodal Language Model." *ICML 2023*
