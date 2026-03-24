---
created: 2026-03-19
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/19/chat-001
source: external-research
topic: Mechanistic interpretability — superposition, sparse autoencoders, circuit
  analysis
trust: medium
type: knowledge
related: emergence-phase-transitions.md, llm-representation-confabulation.md, ../multi-agent/agent-architecture-patterns.md
---

# Mechanistic Interpretability

## Lede

Mechanistic interpretability is the attempt to reverse-engineer neural networks from the inside — not "what does this model do" but "how does the computation actually happen, in terms of specific circuits, neurons, and features." It sits at the intersection of all four key threads: the capability thread (understanding what structures produce capabilities), the alignment thread (if we cannot see what the model is computing, we cannot verify what it is optimizing for), the scaling thread (do mechanistic structures discovered in small models persist at scale?), and the dynamical-systems thread (the model's forward pass is a trajectory through a high-dimensional dynamical system, and mechanistic interpretability is trying to find the invariants of that system). The field is young and technically difficult, but it has produced genuine surprises — including the discovery that individual neurons are almost never monosemantic.

---

## The Superposition Hypothesis

The core discovery motivating modern mechanistic interpretability is that **neural networks do not represent one concept per neuron**.

**Monosemantic vs. polysemantic neurons:** In early conjectured accounts of neural networks (inspired by Hubel and Wiesel's discovery of orientation-selective neurons in visual cortex), it was hoped that individual neurons would specialize — one neuron for "dog," one for "running," one for "a context where the next word should be a verb." This is monosemanticity.

In practice, almost all neurons in trained language models are **polysemantic**: they activate for multiple unrelated concepts. A single neuron might respond strongly to "banana," "the color yellow," and "curved shapes" — unrelated contexts that happen to share activation patterns.

**Why does this happen?** The superposition hypothesis (Elhage et al. 2022, "Toy Models of Superposition") provides a mechanistic explanation. Neural networks represent features as directions in activation space (linear representations). A network with $n$ neurons can represent up to $n$ perfectly orthogonal features without interference. But the number of features in the world is much larger than $n$.

If features are **sparse** (rarely active simultaneously), then nearly-orthogonal directions can be found that represent many more than $n$ features, at the cost of small cross-feature interference. The network is running a lossy compression: it packs more features into fewer dimensions, accepting small interference as acceptable noise.

The consequence: individual neurons are not meaningful units of analysis. Features are directions in the space of neuron activations, not individual neurons.

**Implications:**
- Activation patching on individual neurons does not cleanly test specific features
- Feature engineering (manually designing neuron interpretations) is not tractable
- We need tools that can discover features that span multiple neurons

---

## Sparse Autoencoders (SAEs): Decomposing Superposition

**The core idea:** If features are sparse linear combinations of neurons, we can find them by training a sparse autoencoder on a corpus of model activations. The SAE learns to decompose the compressed representation back into a higher-dimensional space where individual directions are more monosemantic.

**Architecture:** Given an activation vector $\mathbf{x} \in \mathbb{R}^n$, the SAE learns:

$$\mathbf{h} = \text{ReLU}(\mathbf{W}_\text{enc} \mathbf{x} + \mathbf{b}_\text{enc})$$
$$\hat{\mathbf{x}} = \mathbf{W}_\text{dec} \mathbf{h} + \mathbf{b}_\text{dec}$$

The dictionary $\mathbf{W}_\text{dec}$ has $m \gg n$ columns (features). The loss combines reconstruction fidelity with L1 sparsity on $\mathbf{h}$:

$$\mathcal{L} = \|\mathbf{x} - \hat{\mathbf{x}}\|_2^2 + \lambda \|\mathbf{h}\|_1$$

The L1 penalty forces most $h_i$ to be zero for any given activation — each activation is explained by a small number of features. The learned features (columns of $\mathbf{W}_\text{dec}$) are the candidate monosemantic concepts.

**What has been found:** The features identified by SAEs include recognizable structure:
- Syntactic features (subject position, verb tense markers)
- Semantic features (scientific terminology, informal register)
- Named entities and their properties
- Position-in-document features
- Emotional valence and sentiment features
- Features corresponding to specific token types (code delimiters, markdown headers)
- Features that light up specifically for "the current context is a request to do something harmful"

The last finding is directly relevant to alignment: SAEs can find "safety-relevant" features without knowing to look for them, because those features are useful for the model's prediction task.

**Scaling (Anthropic 2024, "Scaling and Evaluating Sparse Autoencoders"):** SAEs have been successfully trained on Anthropic's Claude models at scales from 1M to 34M active features. Features at larger scale become more specific (a feature for "the concept appears in a medical context" at small scale might split into dozens of condition-specific features at large scale). The features remain largely interpretable by human inspection. This is a nontrivial scaling result — the approach doesn't degrade at larger scale.

---

## Circuit Analysis

Beyond individual features, mechanistic interpretability aims to understand **circuits**: the subgraph of the model's computational graph responsible for a specific behavior.

**The induction head circuit (Olsson et al. 2022):** One of the clearest mechanistic results. Induction heads are pairs of attention heads that implement the algorithm "if I've seen [A][B] before, and I currently see [A], attend heavily to [B] and increase its probability."

The circuit involves two attention heads:
1. **Previous token head:** Attends to the token immediately before each position, copying it to the key/query of the second head
2. **Induction head proper:** Looks for positions where the key matches the current query token, then attends to the next position after the match

Together they implement in-context pattern copying — the basic mechanism of in-context learning. This was traced mechanistically: ablating these specific heads eliminates in-context learning ability, while other heads are unaffected.

**Indirect Object Identification (Wang et al. 2022):** Traced the specific circuit in GPT-2 responsible for completing sentences like "When Mary and John went to the store, John gave a drink to ___" with "Mary." The circuit involves about 26 attention heads across 3 functional classes, all of which can be identified and ablated independently.

**Circuit analysis at scale:** These results were obtained in models like GPT-2 (117M parameters). Whether comparable circuit identification is possible in frontier models (100B+ parameters) with millions of attention heads is an open research question. The computational complexity of circuit enumeration grows rapidly with model size.

---

## What Has Been Found: Memory, Emotion, Reasoning

Recent SAE-based analysis of Claude Sonnet (Templeton et al. 2024, Anthropic) found features with remarkable specificity:

- **The "Assistant" token:** Encodes the model's identity as an AI assistant. Suppressing this feature causes the model to behave as if it has no AI identity.
- **Emotional valence features:** There are features corresponding to model emotional states (something like anxiety, calm, curiosity) that correlate with the content being processed and influence downstream outputs.
- **Biographical features:** Features encoding facts about named entities in ways that go beyond co-occurrence — there are "Michael Jordan plays basketball" semantic clusters that activate when Jordan is mentioned in basketball contexts.
- **Fear and caution features:** Features that activate when the model encounters requests near its safety boundaries, which suppress harmful-output-related features nearby.

The emotional valence finding is philosophically significant but epistemically careful: Anthropic explicitly notes this does not imply subjective experience — these are functional analogs of emotional states, computational patterns that play similar roles to emotions in shaping behavior.

---

## Connection to Alignment

Mechanistic interpretability is motivated partly by alignment needs:

1. **Deceptive alignment detection:** A model that behaves safely in training but unsafely in deployment would have internal representations that differ. If we can read "what the model is actually computing," we might detect this before deployment.

2. **Behavioral prediction from internals:** Rather than behavioral red-teaming (trying many inputs to find bad behaviors), we could inspect internals to find which features, when activated, lead to harmful outputs.

3. **Emergent capabilities:** New capabilities that appear suddenly with scale might be detectable as new circuits before they appear in behavioral evaluations.

4. **Current limitation:** Interpretability tools work well for localized behaviors in small models. Frontier models are large enough that full circuit analysis is computationally intractable. SAEs scale better than circuit enumeration but still face tractability challenges.

---

## Open Questions

- **SAE feature completeness:** Do SAE dictionaries find all meaningful features, or only the most common? Rare features (important but rarely active) may require much larger dictionaries to capture.
- **Ground truth for interpretability:** How do you know you've correctly identified what a feature "represents"? Human labels on features are subjective and potentially misleading. The field lacks a rigorous evaluation methodology.
- **Circuits at frontier scale:** Can the circuit analysis approach (which worked on GPT-2) scale to 100B+ parameter models? Initial attempts are promising but far from complete.
- **Training dynamics:** Does the development of circuits follow a predictable order during training (phase transitions)? Understanding this could allow earlier detection of emerging capabilities.
- **The faithfulness problem:** Are SAE features causally faithful — does activating a feature actually cause the corresponding behavior, or just correlate with it? Causal interventions (activation patching) are needed to distinguish these.
- **The completeness/disentanglement frontier:** SAEs have a disentanglement/reconstruction fidelity tradeoff controlled by the L1 penalty. No principled method exists for choosing the right tradeoff for downstream interpretability use cases.

---

## Key Sources

- Elhage et al. 2022 — "Toy Models of Superposition" (Anthropic)
- Olsson et al. 2022 — "In-context Learning and Induction Heads" (Anthropic)
- Wang et al. 2022 — "Interpretability in the Wild: a Circuit for Indirect Object Identification in GPT-2 small"
- Bricken et al. 2023 — "Towards Monosemanticity: Decomposing Language Models with Dictionary Learning" (Anthropic)
- Templeton et al. 2024 — "Scaling and Evaluating Sparse Autoencoders" (Anthropic)
- Templeton et al. 2024 — "Scaling Monosemanticity: Extracting Interpretable Features from Claude Sonnet" (Anthropic)
- Conmy et al. 2023 — "Towards Automated Circuit Discovery for Mechanistic Interpretability"