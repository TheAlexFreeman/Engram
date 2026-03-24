---
type: summary
related:
  - origins/cybernetics-perceptrons-and-the-first-connectionist-wave.md
  - deep-learning/gpus-imagenet-and-the-deep-learning-turn.md
---

# AI Paradigm Genealogy — Summary

Narrative history of how the current AI paradigm formed, written for causal understanding rather than encyclopedic completeness. Each file answers: what bottleneck existed, what insight addressed it, what enabling conditions made it practical, what remained hard, and what later work built on it.

Four through-lines tracked across all files:
1. **Representation learning** — from hand-engineered features to learned distributed representations
2. **Optimization and training** — perceptron learning → backprop → better activations/regularization → large-scale stochastic optimization → post-training
3. **Scale and infrastructure** — datasets, GPUs/TPUs, software stacks, benchmarks, economics of training
4. **Sequence modeling and interfaces** — recurrence → attention → pretraining → instruction following → tool use → reasoning-time compute

Trust level: **medium** — reviewed by Alex 2026-03-19. This is inherently interpretive history; primary sources are cited but commentary is agent-synthesized.

## Files

### origins/
| File | Period | Core story |
|---|---|---|
| `cybernetics-perceptrons-and-the-first-connectionist-wave.md` | 1943–1969 | McCulloch-Pitts, Rosenblatt, the first learning optimism, and the limit of linear separability |
| `symbolic-ai-expert-systems-and-the-neural-winter.md` | 1956–1986 | The symbolic turn, expert systems, why neural approaches receded, and what symbolic AI solved and failed to solve |
| `backpropagation-and-the-pdp-revival.md` | 1986 | Rumelhart/Hinton/Williams, the credit assignment unlock, PDP program, and vanishing gradients |

### deep-learning/
| File | Period | Core story |
|---|---|---|
| `gpus-imagenet-and-the-deep-learning-turn.md` | 2009–2012 | ImageNet, CUDA, AlexNet — the data and compute unlock that made deep networks practical |
| `convnets-rnns-and-lstm-inductive-biases.md` | 1989–1997 | ConvNets (LeCun), RNNs, BPTT, and the LSTM's solution to vanishing gradients for sequences |

### language-models/
| File | Period | Core story |
|---|---|---|
| `statistical-nlp-word-embeddings-and-seq2seq.md` | 1990–2016 | N-gram models, Bengio neural LM, word2vec/GloVe, seq2seq, and Bahdanau attention |
| `attention-and-the-transformer-breakthrough.md` | 2017–2018 | The transformer architecture, self-attention, multi-head attention, BERT, and GPT |
| `bert-gpt-and-the-scaling-laws-era.md` | 2018–2022 | GPT-3, in-context learning, Kaplan scaling laws, Chinchilla compute-optimal training |

### frontier/
| File | Period | Core story |
|---|---|---|
| `instruction-tuning-rlhf-and-the-chat-model-turn.md` | 2022 | InstructGPT, RLHF pipeline, Constitutional AI, DPO, ChatGPT launch |
| `multimodality-tool-use-and-reasoning-time-compute.md` | 2022–2026 | Vision-language models, RAG, tool use and agents, MoE, open weights, o1 inference-time compute |

### synthesis/
| File | Topics |
|---|---|
| `how-the-current-ai-paradigm-formed.md` | Full causal synthesis: nine bottleneck-unlock transitions from 1940s to 2025; four through-lines traced end-to-end; what the paradigm assumes and what remains open |

## Source spine

Rosenblatt (1958), Minsky and Papert (1969), Rumelhart/Hinton/Williams (1986), Hochreiter/Schmidhuber (1997), LeCun convnets (1989/1998), AlexNet/Krizhevsky (2012), word2vec (2013), seq2seq/Sutskever (2014), Bahdanau attention (2014), Vaswani et al. Transformer (2017), BERT/Devlin (2018), GPT/Radford (2018), GPT-2 (2019), GPT-3/Brown (2020), Kaplan scaling laws (2020), Chinchilla/Hoffmann (2022), InstructGPT/Ouyang (2022), Constitutional AI/Bai (2022), ChatGPT (2022), LLaMA/Touvron (2023), DPO/Rafailov (2023), o1 (2024), DeepSeek-R1 (2025).
