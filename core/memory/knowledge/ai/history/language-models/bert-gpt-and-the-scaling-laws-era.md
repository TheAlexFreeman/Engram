---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-005
type: knowledge
domain: ai-history
tags: [gpt-3, bert, scaling-laws, in-context-learning, few-shot, chinchilla, pretraining, language-model, openai, kaplan, hoffmann]
trust: medium
created: 2026-03-18
last_verified: 2026-03-19
related: ../../frontier/reasoning/test-time-compute-scaling.md, attention-and-the-transformer-breakthrough.md, ../../frontier/reasoning/reasoning-models.md, statistical-nlp-word-embeddings-and-seq2seq.md, ../synthesis/how-the-current-ai-paradigm-formed.md
---

# BERT, GPT-3, and the Scaling Laws Era

## The bottleneck

The transformer architecture (2017) and the BERT/GPT pretraining paradigm (2018) demonstrated that large pretrained language models could transfer well to a wide range of NLP tasks. But they left a fundamental question unanswered: how much does scale matter, and in what direction?

The empirical picture heading into 2019 was suggestive but unclear. Larger models generally performed better. More training data generally helped. But the relationship was not well-characterized. How should you allocate a fixed compute budget — toward a larger model, more data, longer training? Did the returns to scale diminish sharply, or were they sustained? Was there a point at which scale would produce qualitatively new capabilities rather than quantitative improvements?

These were not idle theoretical questions. The answers determined research strategy for every lab with serious compute: Google, OpenAI, Microsoft, Facebook AI Research, DeepMind, Baidu. If returns diminished quickly, the field should focus on architectural innovation and efficiency. If returns were sustained, the rational strategy was to keep scaling while improving efficiency on the side. The scaling laws work gave the field its first systematic, quantitative answer — and the answer validated a significant bet on continued scaling.

---

## GPT-3 and the emergence of in-context learning

### Scale and the surprise of few-shot behavior

GPT-3 (Brown et al., "Language Models are Few-Shot Learners," NeurIPS 2020) was a 175-billion-parameter autoregressive language model trained by OpenAI on roughly 300 billion tokens of text: a mix of Common Crawl, WebText2, Books1, Books2, and English Wikipedia. At the time of release, it was the largest publicly described language model by a wide margin — GPT-2 had 1.5B parameters; the jump to GPT-3 was nearly two orders of magnitude.

The central finding was not about benchmark scores but about a qualitative capability: **in-context learning**. Without any gradient updates, without fine-tuning, the model could perform tasks by conditioning on a handful of input-output examples embedded in the prompt. Show it three examples of sentiment classification followed by a new sentence, and it classifies the new sentence. Show it three arithmetic problems with solutions, and it solves a new one. Show it three translation pairs, and it translates a new sentence.

This was behaviorally surprising. The model had not been trained to do few-shot learning. It had been trained to predict the next token. The few-shot capability emerged as a consequence of scale — it was essentially absent in GPT-2 and appeared as a more reliable capability only at the 175B parameter scale. Smaller GPT-3 variants (1.3B, 6.7B, 13B) showed the capability in degraded form; the full 175B model showed it substantially.

The mechanism is not fully understood, but the working hypothesis is that pretraining at scale causes the model to implicitly learn many tasks as sub-patterns of text prediction. A sentiment classification task looks, in the training corpus, like a review followed by a summary that includes evaluative language. A translation task looks like bilingual text. A code task looks like documentation followed by implementation. At sufficient scale, the model learns the statistical structure of all these task formats and can activate the relevant "mode" given a few examples in context.

### What in-context learning changed

In-context learning shifted the paradigm for how pretrained models were used. The BERT paradigm required fine-tuning: adjust the model's weights on labeled examples for each specific task. In-context learning required no weight updates — just prompt engineering. A user with access to the GPT-3 API could perform novel tasks without any ML infrastructure for fine-tuning.

This was the beginning of prompt engineering as a discipline. Researchers and practitioners discovered that the format, phrasing, and ordering of examples in the prompt had significant effects on GPT-3's outputs. Some formats reliably elicited better performance; others caused the model to produce confident-sounding errors. Understanding how to communicate task intent through context became a distinct skill.

It also created a new research program: understanding when and why in-context learning works, what its limits are, and how it compares to fine-tuning. The answers, roughly: in-context learning is more sample-efficient for distributional shifts, less reliable than fine-tuning on tasks requiring precise output formats, and degrades for tasks requiring many demonstration examples (limited by context length). Fine-tuning remains more effective when labeled data is available; in-context learning is invaluable when it is not.

### Chain-of-thought prompting

A critical follow-on to GPT-3's in-context learning was the discovery (Wei et al., "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models," 2022, at Google Brain) that asking a model to produce reasoning steps before the final answer dramatically improved performance on multi-step reasoning tasks. Instead of providing `problem → answer` examples, you provide `problem → reasoning → answer` examples. The model then produces its own reasoning steps for new problems before the final answer.

This was not obvious. Naively, producing intermediate text should not improve the final answer — the answer is scored regardless of what intermediate text was generated. But empirically, chain-of-thought prompting substantially improved accuracy on arithmetic, symbolic reasoning, and commonsense reasoning benchmarks. The explanation is that the intermediate steps constrain the completion space: a model that has produced `"3 × 4 = 12; 12 + 7 = 19"` is far more likely to produce `"19"` as the final answer than one that went directly from the problem statement to the answer.

Chain-of-thought prompting also revealed that emergent reasoning capabilities appeared primarily in very large models (>100B parameters) and were largely absent in smaller ones. This was additional evidence that scaling produced qualitatively new capabilities rather than just quantitative improvements on existing ones.

---

## Scaling laws: the quantitative case for continued scaling

### Kaplan et al. (2020)

Jared Kaplan, Sam McCandlish, Tom Henighan, Tom Brown, Benjamin Chess, Rewon Child, Scott Gray, Alec Radford, Jeffrey Wu, and Ilya Sutskever published "Scaling Laws for Neural Language Models" (OpenAI, January 2020). This was empirical research: train many language models of different sizes, on different amounts of data, for different numbers of steps, and characterize how test loss depends on each factor.

The main findings:

**Power law scaling.** Language model test loss decreases as a power law in model parameters, dataset size, and compute, over many orders of magnitude. The relationship is log-linear: doubling the model or the data or the compute produces a fixed fractional improvement in loss. The laws held across 7+ orders of magnitude in parameters, from ~10K to ~1B parameters at the time of the study.

**Bottlenecking behavior.** If you fix two factors and scale the third, the improvement follows the power law until the fixed factors become the bottleneck. A model trained on too little data relative to its size will underfit its capacity; a model trained for too few steps relative to its size similarly. Conversely, there is no point training a small model on vastly more data than it can absorb.

**Model size is the most efficient lever.** The Kaplan et al. paper concluded that, for a fixed compute budget, it was better to train a larger model on less data than a smaller model on more data. This was a specific, actionable claim that influenced how labs allocated compute: when budgets were set, they favored large models with relatively early stopping.

**Sample efficiency of large models.** Larger models learn faster per token: for the same number of training tokens, a larger model achieves lower loss than a smaller model. You are not throwing away capacity on a large model; you are using the capacity more efficiently.

These findings gave the field something it had lacked: a principled basis for planning compute expenditure. You could predict, roughly, what test loss you would achieve for a given compute budget and choose the model-size/data-size allocation that minimized loss per FLOP. Research investment could be directed at scaling rather than at architectural search.

### Chinchilla and compute-optimal training (Hoffmann et al., 2022)

The Kaplan scaling laws were influential but turned out to have a flaw: the compute-optimal recommendation to train large models for fewer tokens was based on training runs that did not fix the compute budget adequately across all variables. When DeepMind's Hoffmann, Borgeaud, Mensch, Buchatskaia, Clark, Casas, Driessche, Engelmann, Pope, Bellegarda, et al. ("Training Compute-Optimal Large Language Models," 2022) re-examined the question with better-controlled experiments — training over 400 models ranging from 70M to 16B parameters on datasets from 5B to 500B tokens — they arrived at a different conclusion.

The Chinchilla finding: **for a fixed compute budget, model size and training tokens should scale in equal proportion.** Specifically, for each doubling of the compute budget, you should double both the number of parameters and the number of training tokens. The Kaplan law had underweighted data relative to model size.

The practical implication: existing large models including GPT-3 (175B) and Gopher (280B, DeepMind) were significantly undertrained. They had been trained on roughly 300–400B tokens — far less than the Chinchilla-optimal amount for their parameter counts. A 70B-parameter model trained on 1.4 trillion tokens (Chinchilla itself) matched or exceeded GPT-3's performance on many benchmarks while using roughly 4× less compute at inference time.

This was consequential for deployment. Inference costs dominate at scale — a model runs once per training run but millions of times in production. Chinchilla-optimal models were cheaper to run for the same quality. The open-source Llama models (Meta AI, 2023), which trained smaller models on more tokens than previous practice, were partly motivated by the Chinchilla findings and achieved competitive performance with larger models at lower inference cost.

### The scaling hypothesis and its stakes

The empirical scaling laws gave a specific form to the hypothesis that had been implicit in the GPT-3 result: that intelligence-like capabilities in language models are predictable functions of scale. If the power-law improvement in loss continued indefinitely, and if loss improvement correlated with capability improvement, then a model trained on 10× more compute should predictably be more capable than its predecessor.

This framing had large economic and strategic implications. Building the next frontier model required not an algorithmic breakthrough but a capital expenditure on compute and data. This made AI development increasingly resemble other capital-intensive industries — energy, aerospace, semiconductor manufacturing — rather than academic research. The barriers to entry grew sharply. A lab that could afford to train a 175B-parameter model in 2020 required substantial funding; a lab attempting GPT-4-scale training in 2023 required infrastructure investment that only a handful of organizations in the world could mount.

It also raised a question that dominated AI safety discourse from 2020 onward: if capability scaling continued predictably, and if some capabilities were qualitatively dangerous at sufficient scale, then predicting when those capabilities would emerge — and ensuring they were aligned with human values before they did — became an urgent engineering problem. The scaling laws made capability forecasting more tractable, and that tractability made alignment concerns more concrete.

---

## The benchmark treadmill and emergent capabilities

### The GLUE, SuperGLUE, and BIG-Bench progression

The NLP benchmark landscape evolved rapidly as model performance improved:

BERT (2018) saturated the original GLUE benchmark (General Language Understanding Evaluation) within about two years. By late 2019, models were matching or exceeding human performance on many GLUE tasks. SuperGLUE (Wang et al., 2019) replaced it with harder tasks. SuperGLUE was substantially harder, but large models saturated it by 2021.

BIG-Bench (Srivastava et al., 2022) was an attempt to build a benchmark that would not be immediately saturated: over 200 tasks across diverse reasoning domains, many of which required knowledge, common sense, mathematical reasoning, and code. BIG-Bench tasks were selected specifically because models at the time of benchmark creation performed poorly on them. Even on BIG-Bench, GPT-4-class models showed strong performance on many tasks within a year of the benchmark's publication.

This benchmark treadmill revealed something about the nature of scale-driven progress. Capabilities that appeared to require task-specific fine-tuning or symbolic reasoning emerged in large pretrained models without explicit training on those capabilities. The term "emergent capabilities" (Wei et al., "Emergent Abilities of Large Language Models," 2022) formalized the observation: some capabilities appear suddenly at a threshold scale and are essentially absent below that threshold. Examples include multi-digit arithmetic, word unscrambling, identifying logical fallacies, and chain-of-thought reasoning.

The emergence phenomenon is not fully understood. One explanation (Schaeffer et al., "Are Emergent Abilities of Large Language Models a Mirage?", 2023) argued that emergence is partly a measurement artifact: if you use a discontinuous metric (like exact match on a multi-step problem), smooth improvement in the underlying capability appears as a sudden jump. Under continuous metrics, progress is smooth. The debate remains active, but the practical observation — that large models exhibit qualitatively different behavior from small models on some tasks — is well-established regardless of its theoretical interpretation.

---

## The two pretraining strategies and their implications

The transformer-pretraining era was defined by two strategies, each inherited from BERT and GPT respectively:

**Encoder pretraining (masked language modeling, bidirectional).** The BERT family: RoBERTa (Liu et al., 2019, which showed that BERT was substantially undertrained and that NSP should be removed), ALBERT, DeBERTa, ELECTRA. Encoder models produce rich bidirectional representations and are particularly strong on classification, span prediction, and understanding tasks. They are not suited for open-ended generation because the masked LM objective does not train the model to generate completions.

**Decoder pretraining (causal language modeling, autoregressive).** The GPT family: GPT-2, GPT-3, PaLM (Chowdhery et al., 2022, 540B parameters), Gopher (DeepMind), Chinchilla, LLaMA, Mistral. Decoder models generate text autoregressively — one token at a time, left to right — and are suited for completion, summarization, translation, question answering, and code generation. They lack BERT-style deep bidirectional context during training but compensate with greater flexibility and generalization.

**Encoder-decoder (sequence-to-sequence pretraining).** T5 (Raffel et al., "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer," 2020) proposed treating all NLP tasks as text-to-text: the input is always a text string (including a task prefix like "translate English to German: ...") and the output is always a text string. T5 was pretrained with a span-corruption objective (mask spans of input text, predict them as the output sequence). It performed strongly across diverse tasks and influenced later instruction-following models.

The long-run winner was the decoder-only architecture, primarily because autoregressive generation is the natural output format for general-purpose assistants and because in-context learning required a generative model. But encoder models remained competitive for tasks where bidirectional context was critical and generation was not needed, like embedding-based retrieval and classification.

---

## The software and hardware stack

The scaling era required a software and hardware stack that did not fully exist when GPT-3 was trained. Building it was as consequential as the models themselves:

**PyTorch and JAX.** Theano (the original academic deep learning framework) was discontinued by 2017. TensorFlow, released by Google in 2015, dominated initially. PyTorch (Facebook, 2016) became the dominant research framework by 2019 due to its dynamic computation graph (eager execution) and more Pythonic interface. JAX (Google, 2018) became the preferred framework for large-scale TPU training.

**Distributed training.** Training a 175B-parameter model on a single GPU is impossible — the model weights alone require ~350 GB of memory in float16. Training at scale required distributing the model and computation across thousands of accelerators using tensor parallelism (split each matrix across GPUs), pipeline parallelism (split the model's layers across GPUs), and data parallelism (split the batch across GPUs). Megatron-LM (NVIDIA) and DeepSpeed (Microsoft) provided frameworks for this distribution.

**TPUs.** Google's Tensor Processing Units, custom ASICs designed specifically for matrix multiplication, were 3–5× more compute-efficient and 5–10× more energy-efficient than GPUs for transformer training at the time of their development. Google's ability to train BERT, T5, and PaLM at scale was partly a function of TPU infrastructure that no external lab could access.

**The A100 and then H100.** NVIDIA's A100 GPU (2020) and H100 (2022) substantially increased the compute available per accelerator and improved communication bandwidth across multi-GPU nodes. Each generation enabled either larger models or faster training for the same model size.

---

## What the scaling era did not resolve

### Alignment: raw capability versus behavior

GPT-3, despite its capabilities, was unreliable as a deployed product. It would confidently produce false information, generate harmful content, fail to follow instructions when they conflicted with its prediction objective, and behave inconsistently across similar prompts. These behaviors were not surprising from a training perspective — the model was trained to predict the next token in text, and text on the internet contains false information, harmful content, and inconsistency in abundance. The model's predictions were calibrated to the corpus, not to human preferences.

The gap between raw predictive capability and useful, safe, consistent behavior was the central problem that the post-training era addressed. This is the subject of the next file.

### Long-context and retrieval

GPT-3 had a context window of 2,048 tokens — roughly 1,500 words. Many real tasks require more context: summarizing long documents, maintaining coherent state across a long conversation, processing legal or scientific texts. Extending context windows required either architectural changes (longer positional encodings, more efficient attention) or retrieval augmentation (retrieving relevant passages and inserting them into context). Both became active research directions after GPT-3.

### Reasoning

Despite chain-of-thought improvements, large language models remained unreliable on tasks requiring systematic, multi-step reasoning: long arithmetic, formal logic, combinatorics, planning. The model's "reasoning" was a form of pattern completion over training examples rather than a principled symbol-manipulation process. This limitation would motivate the tool-use and code-execution approaches of the frontier era, and the reinforcement-learning-heavy reasoning systems of 2024–2025.

---

## Quick reference

| Model / Paper | Key contribution |
|---|---|
| GPT-3 (Brown et al., 2020) | 175B parameters; in-context learning without fine-tuning; few-shot task transfer |
| Chain-of-thought (Wei et al., 2022) | Intermediate reasoning steps in prompt improve multi-step accuracy |
| Kaplan scaling laws (2020) | Power-law improvement in loss vs. parameters, data, compute; favored large models |
| Chinchilla (Hoffmann et al., 2022) | Compute-optimal: scale model and data equally; prior models were undertrained |
| T5 (Raffel et al., 2020) | Encoder-decoder; text-to-text framing; span-corruption pretraining |
| RoBERTa (Liu et al., 2019) | BERT is undertrained; remove NSP; train longer on more data |
| Emergent capabilities (Wei et al., 2022) | Some capabilities appear suddenly at scale threshold |
| PaLM (Chowdhery et al., 2022) | 540B parameter GPT-family model; strong chain-of-thought results |
| Megatron-LM / DeepSpeed | Tensor, pipeline, and data parallelism for 100B+ scale training |

---

*Sources: Brown et al. (2020), "Language Models are Few-Shot Learners" (GPT-3), NeurIPS; Kaplan et al. (2020), "Scaling Laws for Neural Language Models," arXiv; Hoffmann et al. (2022), "Training Compute-Optimal Large Language Models" (Chinchilla), NeurIPS; Wei et al. (2022), "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models," NeurIPS; Wei et al. (2022), "Emergent Abilities of Large Language Models," TMLR; Raffel et al. (2020), "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer" (T5), JMLR. Trust level: low — not yet reviewed by Alex.*
