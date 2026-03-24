---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-005
type: knowledge
domain: ai-history
tags: [convnets, cnn, rnn, lstm, gru, lenet, inductive-bias, spatial-structure, sequence-modeling, hochreiter, schmidhuber, lecun]
trust: medium
created: 2026-03-18
last_verified: 2026-03-19
related: ../../../mathematics/information-theory/inductive-bias-no-free-lunch.md, ../../../rationalist-community/origins/heuristics-biases-bayes-and-bounded-rationality.md, gpus-imagenet-and-the-deep-learning-turn.md
---

# ConvNets, RNNs, and LSTM: The Case for Inductive Bias

## The bottleneck

Backpropagation solved credit assignment. But it left a critical question unanswered: *what should the architecture look like?* In principle, a generic multi-layer network with enough hidden units can approximate any continuous function. In practice, generic is the problem. A fully connected network applied to a 256×256 image has to learn from scratch that nearby pixels tend to be related, that the same edge pattern matters regardless of where it appears in the image, and that a cat in the upper left corner and a cat in the lower right corner are both cats. None of this structure is built in. All of it has to be re-learned from data, and learning it requires far more data and far more parameters than tasks of realistic complexity can support.

The same problem arises for sequences. A generic network applied to a sentence has to learn from scratch that word order matters, that a word's meaning is affected by its context, that a reference made five words ago is still relevant now. Again, nothing is built in. The network has to rediscover structure that is obvious from the nature of the data.

Architecture design is the art of building in structure that you already know is there. The two most important 1980s–1990s innovations in this direction were convolutional networks and recurrent networks. Each solved a different structural problem. Each also left behind a characteristic bottleneck that the next generation of work would have to address.

---

## Convolutional networks: locality and weight sharing

### The insight

Yann LeCun's convolutional network work, developed at Bell Labs through the late 1980s and consolidated in the 1998 paper "Gradient-Based Learning Applied to Document Recognition" (with Bottou, Bengio, and Haffner), built two inductive biases directly into the architecture:

**Locality.** A convolution filter examines only a small local patch of the input at a time — typically 3×3 or 5×5 pixels. This encodes the prior that features are local: an edge, a corner, a texture pattern is defined by the relationship among nearby pixels, not between pixels at opposite corners of the image. A fully connected layer ignores this.

**Weight sharing (translation equivariance).** The same filter is applied everywhere across the image. The same set of weights that detects a vertical edge in the upper-left corner is used to detect a vertical edge in the lower-right corner. This dramatically reduces the number of free parameters — instead of learning separate weights for each position, you learn one set of weights that is reused at all positions. It also encodes the prior that the same feature can appear anywhere in the image: a cat-detector should not have to be separately trained for cats in each possible location.

Stacking multiple convolutional layers with nonlinearities between them builds up a hierarchy of features: early layers detect edges and blobs, middle layers detect corners and textures, later layers detect object parts and eventually object categories. This hierarchical feature learning is what makes deep convolutional networks so effective on visual tasks: each layer's output is a more abstract and spatially compressed representation of the input.

**Pooling** layers (typically max pooling) downsample the spatial dimensions between convolutional layers, giving the network a degree of translation invariance (nearby features are treated as equivalent) and controlling the number of parameters in subsequent layers.

### What LeCun demonstrated

LeNet-5 (1998) had seven trainable layers: two convolutional, two subsampling, two fully connected, and a final output layer. Trained on handwritten digits, it matched or exceeded all previous methods. It was deployed in real systems: by the late 1990s, LeNet-based systems were reading checks and ZIP codes in the United States Postal Service and banking systems. This was applied AI at industrial scale, and it worked — not by hand-engineering features but by learning them from labeled examples through backpropagation.

The key lesson was not "use this exact architecture" but rather "the architecture should reflect the structure of the data." For images, that structure is locality and translation equivariance. For other data types, different biases would be appropriate.

### Why ConvNets did not immediately dominate

LeNet worked convincingly on small, clean, controlled images. It did not scale to the larger and messier images of natural photographs in the early 2000s. Several reasons:

**Compute.** Training a deeper or wider convolutional network on larger images required more computation than was readily available before GPU acceleration.

**Data.** Large labeled image datasets for general object recognition did not exist before ImageNet (2009). Training on small datasets, even a convolutional architecture with good inductive biases tends to overfit.

**Competition.** Support vector machines (SVMs) with kernel methods were excellent at handling moderate-dimensional input with limited data, had strong theoretical guarantees, and produced sparse solutions. In the late 1990s and early 2000s, SVMs frequently outperformed neural networks on benchmark tasks. The mainstream of the machine learning community in that era treated SVMs as the reliable, well-understood option and neural networks as an interesting but unstable alternative.

This is why the "deep learning revolution" dates to 2012 rather than 1998, even though the essential architecture was already in place. The missing ingredients were GPU compute and a large labeled dataset — covered in the next file.

---

## Recurrent networks: encoding sequential structure

### The insight

A convolutional network handles spatial structure. It does not handle sequences of variable length in which the relevant context at position *t* depends on events at positions *t−1*, *t−2*, ..., *t−k*. Language, speech, time series, and video all have this character.

A recurrent neural network (RNN) handles sequences by maintaining a hidden state vector that is updated at each time step. At step *t*, the network receives the current input *x_t* and its hidden state from the previous step *h_{t−1}*, computes a new hidden state *h_t = f(x_t, h_{t−1})*, and optionally produces an output *y_t*. The same weight matrices are used at every step — analogous to weight sharing in a ConvNet. This gives the RNN:

1. **Variable-length sequence handling.** You can process sequences of any length because the same weights are applied at each step.
2. **Memory.** The hidden state carries information forward from earlier steps. In principle, the network can remember anything that happened earlier in the sequence, as long as that information was retained in the hidden state.

The recurrent architecture was known before backpropagation. What the PDP era added was training via backpropagation through time (BPTT): unroll the recurrent network across all time steps, treating each step as a layer in a very deep feedforward network, and apply standard backpropagation to the unrolled computation graph. This gave a principled way to train RNNs on sequence prediction tasks.

### The vanishing gradient problem in recurrences

BPTT created a problem that was worse for recurrent networks than for feedforward networks: the vanishing gradient problem was not just deep-but-fixed, it was deep-and-proportional-to-sequence-length. For a sequence of 100 tokens, the gradient had to pass backward through 100 steps of repeated multiplication. If the weight matrix has eigenvalues smaller than 1 — which is the typical case — the gradient shrinks exponentially. The network could not learn dependencies that spanned more than about 10–20 time steps. For longer-range dependencies — a pronoun referring to a noun mentioned 50 words ago, a melody pattern recurring after 100 beats — vanilla RNNs were effectively blind.

Bengio, Simard, and Frasconi made this problem precise in a 1994 paper that showed why learning long-term dependencies with gradient descent is fundamentally difficult for standard recurrent architectures. The paper did not immediately solve the problem, but it crystallized it as the central bottleneck for sequence modeling.

---

## LSTM: gating as the solution to long-range dependencies

### The insight

Sepp Hochreiter and Jürgen Schmidhuber's 1997 paper "Long Short-Term Memory" is one of the most important papers in the history of sequence modeling. The key idea was to replace the simple hidden state of an RNN with a memory cell that had explicit gates controlling what information was read in, retained, and written out.

An LSTM cell has four components:

**Cell state (*c_t*).** A separate vector that flows forward through time with additive, not multiplicative, updates. Because the cell state is updated additively rather than through repeated matrix multiplication, gradients can flow backward through it without shrinking exponentially. This is the architectural key to LSTM's ability to learn long-range dependencies.

**Forget gate.** A sigmoid-activated gate that decides what fraction of the previous cell state to retain. At each step, the network can choose to forget some of its stored information.

**Input gate.** A gate that decides how much of a candidate update (derived from the current input and previous hidden state) to write into the cell state.

**Output gate.** A gate that decides how much of the cell state to expose as the current hidden state *h_t*.

The gates are all learned from data. The network learns when to forget, what to remember, and what to read out, based on the task. This is radically different from the vanilla RNN, where the hidden state update function is fixed and the same operation is applied at every step regardless of content.

The additive cell state update is the mathematical core of the solution. When you differentiate the LSTM equations with respect to cell state at an earlier time step, the gradient does not vanish in the way it does through repeated matrix multiplications. Information can, in principle, be retained in the cell state for hundreds or thousands of steps with essentially no gradient decay — limited only by the forget gate's learned behavior.

### What LSTM enabled

The immediate applications were sequence modeling tasks where long-range context mattered:

- **Speech recognition.** An LSTM reading a speech signal could learn to capture phoneme patterns that span many time steps, including the influence of earlier phonemes on later pronunciations (coarticulation).
- **Handwriting recognition.** Graves, Liwicki, Fernández, Bertolami, Bunke, and Schmidhuber (2009) used a bidirectional LSTM with a connectionist temporal classification (CTC) output layer to achieve state-of-the-art performance on offline handwriting recognition. This was a significant benchmark result.
- **Language modeling.** RNNs and LSTMs trained on text could predict the next word better than n-gram language models for longer contexts.
- **Machine translation.** By the early 2010s, LSTM-based encoder-decoder systems (seq2seq) would demonstrate that machine translation could be done end-to-end with a single trained neural network — covered in the next file.

The broader significance was that LSTM showed architecture choices could directly address the fundamental bottlenecks of gradient-based training. The vanishing gradient problem was not just an inconvenient artifact of backpropagation that had to be tolerated; it was something that architectural design could mitigate.

### GRU: a simpler gating alternative

Cho, van Merrienboer, and colleagues (2014) introduced the Gated Recurrent Unit (GRU) as a simplified alternative. The GRU merges the cell state and hidden state, replacing the three gates of the LSTM with two: a reset gate and an update gate. It has fewer parameters and often trains faster. In practice, LSTM and GRU perform comparably on most sequence tasks, and both were widely used through the mid-2010s before being largely replaced by transformer architectures.

---

## The general lesson: architecture as prior

The most important abstraction from ConvNets and LSTMs is not the specific details of either architecture. It is the principle that the architecture of a neural network is a statement about the structure you believe is present in the data, and that good inductive biases can dramatically reduce the data and compute required to learn useful functions.

A fully connected network for images is making a very weak prior: all pixels are equally related to all other pixels, and there is no reason to expect similar patterns at different positions. A convolutional network encodes a strong prior: patterns are local, and translation matters. Given this prior is correct for natural images, the convolutional network learns faster, generalizes better, and requires fewer parameters.

A vanilla RNN for sequences makes a similarly weak prior about what information should be retained over time. An LSTM encodes a stronger prior: information should be explicitly managed — stored, forgotten, and read out — with gates that can be trained to match the task's temporal structure.

This framing explains why the deep learning era involved so much architectural innovation rather than purely scaling up generic backpropagation networks: each domain required matching the network's built-in assumptions to the actual structure of the data. It also explains why the transformer eventually superseded both ConvNets and LSTMs for many tasks: attention mechanisms provide a more flexible prior about where relevant information is located, without imposing locality (ConvNets) or strict sequentiality (RNNs). That story comes later.

---

## Remaining bottlenecks

Despite the power of ConvNets and LSTMs, the decade running from roughly 1990 to 2005 remained a frustrating period for their most ambitious practitioners. The bottlenecks were:

**Depth and vanishing gradients in feedforward nets.** Adding more than 4–6 layers to a ConvNet still caused training difficulties due to vanishing gradients. The sigmoid activation function was the main culprit: its derivative saturates near zero for large or small inputs, causing the gradient to vanish in early layers. Solutions would come later: better initialization (Glorot and Bengio, 2010), ReLU activations (Nair and Hinton, 2010; popularized by AlexNet, 2012), and batch normalization (Ioffe and Szegedy, 2015).

**Language: lack of scale.** LSTMs were strong for sequence modeling but language is enormous, noisy, and diverse. Training an LSTM language model required labeled or structured data for supervised tasks, and the richest signal available — raw text — was unsupervised. Extracting useful representations from raw text at scale would require pretraining approaches that only became feasible in the late 2010s.

**Long-range dependencies: attention, not architecture.** Even LSTM with its carefully gated cell state had limits. A very long document, a very long piece of music, or a sentence with complex nested structure could still tax an LSTM's ability to maintain relevant context. The structural solution — attention mechanisms — replaced the RNN bottleneck of fixed-size hidden states with a mechanism for directly attending to any earlier position. This came in 2014–2015 (Bahdanau attention) and reached its full expression in the transformer (2017).

**Lack of pretrained representations.** Each new task required training a network from scratch. The ability to learn useful general-purpose representations from unlabeled data — embeddings, pretraining, transfer learning — was not yet well-developed. This is the subject of the next file: statistical NLP, word embeddings, and sequence-to-sequence models.

---

## Quick reference

| Concept | What it encodes |
|---|---|
| Local connectivity (ConvNet) | Features are spatially local |
| Weight sharing (ConvNet) | Features are translation equivariant |
| Pooling (ConvNet) | Features are approximately translation invariant |
| Recurrent hidden state (RNN) | Sequence context is maintained over time |
| BPTT | Train an RNN by unrolling through time and applying backpropagation |
| Vanishing gradient (RNNs) | Gradients shrink over long sequences; limits learning of long-range dependencies |
| LSTM cell state | Additive updates prevent gradient vanishing; explicit gates manage memory |
| GRU | Simpler two-gate alternative to LSTM |
| Inductive bias | Structural assumption built into an architecture that reduces the hypothesis space |

---

*Sources: LeCun, Bottou, Bengio, Haffner (1998), "Gradient-Based Learning Applied to Document Recognition"; Hochreiter and Schmidhuber (1997), "Long Short-Term Memory"; Bengio, Simard, Frasconi (1994), "Learning Long-Term Dependencies with Gradient Descent is Difficult"; Cho et al. (2014), "Learning Phrase Representations using RNN Encoder-Decoder." Trust level: low — not yet reviewed by Alex.*
