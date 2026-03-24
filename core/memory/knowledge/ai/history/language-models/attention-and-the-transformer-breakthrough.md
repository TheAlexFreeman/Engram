---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-005
type: knowledge
domain: ai-history
tags: [transformer, attention, self-attention, vaswani, bahdanau, bert, gpt, nlp, parallelization, positional-encoding, multi-head-attention, layer-norm]
trust: medium
created: 2026-03-18
last_verified: 2026-03-19
related: ../../../cognitive-science/attention/transformer-attention-vs-human-attention.md, ../../../cognitive-science/attention/attention-synthesis-agent-implications.md, bert-gpt-and-the-scaling-laws-era.md
---

# Attention and the Transformer Breakthrough

## The bottleneck

By 2016, the seq2seq architecture with Bahdanau attention was the dominant approach to machine translation and many other sequence-to-sequence tasks. It was good — competitive with or better than phrase-based statistical MT — and it was improving as LSTM capacity and training data grew. But it had a structural bottleneck that was becoming increasingly visible as the field tried to scale it to harder tasks and longer sequences.

**The recurrent bottleneck.** An LSTM processes sequences one step at a time. The hidden state at step *t* depends on the hidden state at step *t-1*, which depends on step *t-2*, and so on. This sequential dependency means you cannot parallelize the computation over the time dimension during training. Training on a sequence of length n requires n sequential steps, regardless of how many GPUs you have. For long sequences — documents rather than sentences, long-form generation — this sequential constraint made training slow and made the architecture hard to scale.

**Compression through recurrence.** Even with attention, the LSTM encoder still compressed each sequence through a series of hidden state updates. The hidden state at each position was influenced by everything before it but had a finite capacity. Long-range dependencies could be addressed by attention — the decoder could attend directly to any encoder position — but the encoder's representation of each position was still mediated by the recurrent dynamics. Earlier positions had been partially overwritten by later updates, so the attention mechanism was attending to compressed representations rather than raw positions.

**Depth limits from sequential composition.** Stacking more LSTM layers helped, but each additional layer added another sequential depth that gradients had to traverse. Very deep LSTMs were harder to train and offered diminishing returns in practice.

The transformer, introduced in "Attention Is All You Need" (Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin, 2017), eliminated recurrence entirely and replaced it with self-attention. The result was a model that was easier to parallelize, more effective at long-range dependencies, and — unexpectedly — better suited for scaling to the data and compute regimes that would define the LLM era.

---

## The insight: self-attention over the whole sequence

### From cross-attention to self-attention

Bahdanau attention was cross-attention: the decoder attended to the encoder's output positions while generating the target sequence. The query was the decoder's current state; the keys and values were the encoder's hidden states.

Self-attention applies the same mechanism to a single sequence attending to itself. Every position in the sequence simultaneously computes a weighted sum over all other positions, where the weights reflect pairwise relevance. This means any token can directly attend to any other token in the sequence, regardless of their distance apart, in a single operation.

Formally, given a sequence of input vectors, self-attention computes three projections for each position: a query **Q**, a key **K**, and a value **V**. Attention weights are computed by taking the dot product of each query with all keys, dividing by the square root of the key dimension (for numerical stability), and applying softmax. The output is the weighted sum of values:

`Attention(Q, K, V) = softmax(QK^T / √d_k) V`

The critical properties:

1. **O(1) depth for any-distance dependency.** Any pair of positions interacts in a single self-attention operation. Distance is irrelevant — a token can attend to a token 500 positions away just as easily as to its immediate neighbor. This is fundamentally different from LSTMs, where long-range dependencies require information to survive through many sequential hidden state updates.

2. **Fully parallelizable over the sequence.** All positions attend to all other positions simultaneously. There is no sequential dependency across positions. Given sufficient hardware, a sequence of length n can be processed in O(1) sequential operations (over the length dimension), compared to O(n) for recurrent networks. Training on modern GPU clusters was therefore dramatically faster for the same sequence length.

3. **Direct, content-based routing.** The attention weights are determined by the learned query-key dot products — by the content of the representations, not by their position. The model learns to attend to positions that are semantically relevant to the current query, not just to positions that are nearby. This is a more flexible routing mechanism than the locality bias of convolutions or the positional bias of recurrence.

### Multi-head attention

Rather than computing a single set of attention weights, the transformer computes attention multiple times in parallel with different learned projections — each "head" can attend to different types of relationships simultaneously. The outputs of all heads are concatenated and linearly projected back to the model dimension.

Multi-head attention captures richer relational structure than single-head attention. Different heads tend to specialize: some attend to syntactic structure (subject-verb agreement, coreferent pronouns), others to semantic relationships (argument structure, entity types), others to positional proximity. This division of representational labor happens through training, without explicit supervision.

### Positional encoding

Self-attention is permutation-equivariant: if you shuffle the positions of the input tokens, the attention mechanism produces the same outputs, just shuffled. This means it has no inherent sense of order. For sequence tasks, position matters, so position must be explicitly encoded.

The original transformer used sinusoidal positional encodings: for each position *pos* and each dimension *i*, the encoding is sin(pos/10000^(2i/d)) or cos(pos/10000^(2i/d)), alternating. These sinusoids at different frequencies produce a unique vector for each position that varies smoothly across adjacent positions and across all dimensions, allowing the model to attend to relative positions through the attention mechanism.

Later work replaced sinusoidal encodings with learned positional embeddings (BERT, GPT) or relative position encodings (T5, ALiBi, RoPE). The choice of positional encoding scheme has become one of the more technically active areas of transformer design, particularly as context lengths have grown from 512 tokens (original BERT) to millions of tokens in recent systems.

---

## The full transformer architecture

The original transformer was an encoder-decoder architecture for machine translation, with both encoder and decoder stacks of identical blocks.

**Encoder block:** Each encoder block contains two sublayers — a multi-head self-attention layer and a position-wise feedforward network (two linear projections with a ReLU in between, applied identically to each position). Both sublayers use residual connections (x + sublayer(x)) and layer normalization (applied before or after the sublayer, with post-norm in the original paper and pre-norm becoming more common in later implementations). Layer normalization replaced batch normalization, which is poorly suited to variable-length sequences.

**Decoder block:** Each decoder block contains three sublayers: a masked self-attention layer (masking out future positions, so the decoder at position *t* can only attend to positions ≤ *t*), a cross-attention layer (attending to the encoder output), and a feedforward layer. The masking ensures that generation at each step depends only on previously generated tokens — the autoregressive property.

**No recurrence, no convolution.** The transformer's name for its paper was exact: attention is all it uses for sequence interaction. There are no recurrent connections across time steps. There are no convolutional filters. Every token attends to every other token (subject to masking in the decoder) in every layer. The feedforward sublayer operates independently on each position.

### Training results

On WMT 2014 English-to-German translation, the transformer achieved 28.4 BLEU — more than 2 BLEU higher than all previous systems, including those with ensembles. It achieved 41.0 BLEU on English-to-French, establishing a new state of the art. It trained in 3.5 days on 8 P100 GPUs — faster than the best previous LSTM-based systems that required weeks.

The speed advantage came from parallelization. The sequential bottleneck of recurrence was gone. GPU clusters could be used efficiently during training because all positions in the sequence could be processed in parallel. As GPU memory and throughput scaled, transformer training scaled with it in a way that LSTM training did not.

---

## Why the transformer was more than a better translation model

### An unexpected general-purpose architecture

The transformer's authors expected it to be adopted for NLP sequence tasks. They did not anticipate it becoming the dominant architecture for nearly every task in machine learning within a decade. Its generality was a product of properties that only became apparent as scale increased.

**The feedforward layer as a content-addressable memory.** Each position-wise feedforward sublayer has two linear projections with a ReLU. The first projects to a higher dimension (typically 4× the model dimension), the ReLU creates a sparse activation pattern, and the second projects back. Research beginning around 2020 (Geva et al., "Transformer Feed-Forward Layers Are Key-Value Memories") showed that the feedforward layers function as associative memories: the first layer acts as key detection (does the input activate this memory?), and the second layer retrieves the stored value. This means the transformer stores factual associations in its feedforward weights and retrieves them via attention-guided key matching. Understanding this mechanism partially explains why larger transformers "know more" — they have more memory capacity.

**Scale amplifies attention.** The self-attention mechanism's expressiveness grows with the number of heads, the model dimension, and the number of layers. More heads can specialize more finely. More layers allow hierarchical composition of attended relationships. Wider models allow more complex query-key-value projections. When you scale up a transformer, you are scaling up a mechanism that can in principle represent any pairwise relationship in the sequence — and the representational quality grows smoothly with scale. This smooth scaling behavior (which RNNs did not exhibit as clearly) was a precondition for the scaling law work that followed.

**Pretraining compatibility.** The self-attention mechanism is equally suited to two different training objectives: predicting the next token (causal language modeling, which requires masking future positions) and predicting masked tokens from context (masked language modeling, which allows bidirectional attention). The same architecture supports both. BERT uses bidirectional attention with masked language modeling. GPT uses causal (left-to-right) attention with next-token prediction. The architecture was thus suitable for two distinct pretraining strategies, both of which turned out to be powerful.

---

## BERT and GPT: two uses of the transformer

The transformer appeared in mid-2017. By late 2018, two systems built on transformer components had demonstrated that pretraining a large transformer on raw text produced representations that dramatically improved performance on a wide range of downstream NLP tasks.

### BERT (October 2018)

Devlin, Chang, Lee, and Toutanova at Google published BERT ("Bidirectional Encoder Representations from Transformers"). BERT used only the transformer encoder stack — no decoder. It was pretrained on two tasks simultaneously:

- **Masked language modeling (MLM):** 15% of tokens are randomly masked; the model predicts the masked tokens from the surrounding context. Unlike next-token prediction, MLM allows the model to attend in both directions, producing deeply bidirectional representations.
- **Next sentence prediction (NSP):** Given two sentences, predict whether they are consecutive in the original document. (NSP was later found to be less important than MLM and was dropped in RoBERTa.)

Pretrained on BooksCorpus and English Wikipedia (~3.3B words), BERT was then fine-tuned on downstream tasks with a single additional task-specific output layer. The BERT-base model (110M parameters) and BERT-large model (340M parameters) achieved state-of-the-art results on 11 NLP tasks at once: question answering (SQuAD), sentiment analysis (SST), natural language inference (MNLI), named entity recognition, and more. The breadth of transfer was unprecedented — a single pretrained model, fine-tuned with minimal additional data, beat purpose-built systems across a diverse benchmark suite.

BERT established the fine-tuning paradigm for NLP: pretrain a large encoder on raw text, then fine-tune the whole model (or just a classification head) on task-specific data. The key insight was that pretraining captured enough of the structure of language that task-specific labeled data served primarily to specialize the representations rather than to build them from scratch.

### GPT (June 2018) and GPT-2 (February 2019)

Radford, Narasimhan, Salimans, and Sutskever at OpenAI published GPT ("Improving Language Understanding by Generative Pre-Training") slightly before BERT. GPT used only the transformer decoder stack (without cross-attention) with causal masking. It was pretrained on next-token prediction on BooksCorpus (~800M words) and fine-tuned with a linear classifier on top.

GPT established the autoregressive pretraining paradigm: train a transformer to predict the next token, left to right, across billions of words of text. The resulting model learns the statistical structure of language in impressive depth.

GPT-2 (2019) scaled this up: 1.5B parameters, trained on 40GB of text scraped from Reddit outbound links (WebText). GPT-2 demonstrated qualitatively new behaviors at this scale. It generated coherent long-form text, translated between languages without explicit translation training, summarized documents, and answered reading comprehension questions — none of which it was explicitly fine-tuned for. OpenAI released GPT-2 in stages due to concern about misuse, which itself became a news event.

The GPT-2 paper described "zero-shot task transfer": the model could perform tasks by framing them as completions of natural language prompts, without any gradient updates or fine-tuning. Ask it to continue the sentence "The capital of France is ___" and it outputs "Paris." Ask it to continue "Q: What is the sentiment of 'This movie was terrible'? A: ___" and it outputs "negative." This was in-context learning — a capability that would define the GPT-3 era — emerging in a preliminary form.

---

## What the transformer breakthrough unlocked

### The path to foundation models

BERT and GPT showed that a single large transformer pretrained on raw text was a general-purpose linguistic intelligence. The pretraining data was unlabeled — just text, scraped from books and the internet. The pretraining objective was self-supervised — the labels were derived from the data itself (which token is masked, what comes next). No human labeling was required at scale. This meant the pretraining data could be arbitrarily large.

The implications for scale were immediate. If a larger transformer pretrained on more data consistently produced better representations, and if data and compute were the primary constraints rather than algorithmic innovation, then the path to better language models ran through larger models, larger datasets, and more compute. This was the framing of the GPT-3 paper (Brown et al., 2020) and the empirical scaling laws work (Kaplan et al., 2020) that followed. The transformer was the substrate that made scaling a coherent strategy.

### The O(n²) attention cost and its implications

Self-attention computes pairwise interactions between all positions, requiring O(n²) time and memory in sequence length n. For short sequences (512 tokens, as in BERT), this was fine. For longer sequences, the quadratic scaling became expensive. This created a research program in efficient transformers — Longformer, BigBird, Performer, FlashAttention — aimed at reducing the attention cost. FlashAttention (Dao et al., 2022) achieved significant practical speedups by restructuring the attention computation to minimize GPU memory bandwidth, enabling training on longer sequences without approximation.

The O(n²) bottleneck is also a primary motivation for alternative architectures — state space models (Mamba), linear attention variants — that attempt to achieve transformer-quality representations with linear sequence complexity. As context lengths grew from 512 to 128K to millions of tokens, managing the quadratic cost became a central engineering problem.

### The residual stream as the organizing abstraction

A later theoretical framing (Elhage et al., "A Mathematical Framework for Transformer Circuits," 2021) described transformer computation as a series of operations on a shared residual stream. Each layer reads from and writes to the residual stream; the final residual vector at each position is the input to the unembedding step that produces output probabilities. This abstraction clarifies how information flows and accumulates across layers, and became foundational for mechanistic interpretability research — the program of reverse-engineering what transformers compute internally.

---

## Quick reference

| Concept | What it provides |
|---|---|
| Self-attention | O(1) depth for arbitrary-distance pairwise interactions; fully parallelizable |
| Q/K/V projections | Content-based routing: relevance of position *j* to query at position *i* |
| Multi-head attention | Multiple parallel attention computations; specialization across heads |
| Positional encoding | Injects order information into permutation-equivariant attention |
| Residual connections | Gradient highway across depth; same principle as ResNet |
| Layer normalization | Stabilizes training across variable-length sequences |
| Masked self-attention | Restricts decoder attention to past positions; enables autoregressive generation |
| BERT (2018) | Bidirectional transformer encoder; MLM pretraining; fine-tuning paradigm |
| GPT (2018) / GPT-2 (2019) | Causal transformer decoder; next-token pretraining; in-context learning precursor |
| O(n²) attention cost | Quadratic memory/compute in sequence length; motivates efficient attention research |

---

*Sources: Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin (2017), "Attention Is All You Need," NeurIPS; Devlin, Chang, Lee, Toutanova (2018), "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"; Radford, Narasimhan, Salimans, Sutskever (2018), "Improving Language Understanding by Generative Pre-Training"; Radford et al. (2019), "Language Models are Unsupervised Multitask Learners" (GPT-2); Bahdanau, Cho, Bengio (2014), "Neural Machine Translation by Jointly Learning to Align and Translate." Trust level: low — not yet reviewed by Alex.*
