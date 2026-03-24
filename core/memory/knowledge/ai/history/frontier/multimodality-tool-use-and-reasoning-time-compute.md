---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-005
type: knowledge
domain: ai-history
tags: [multimodal, tool-use, rag, reasoning, chain-of-thought, gpt-4, gemini, mixture-of-experts, open-weights, agents, o1, reinforcement-learning, inference-time-compute]
trust: medium
created: 2026-03-18
last_verified: 2026-03-19
related: ../../frontier/reasoning/test-time-compute-scaling.md, ../../frontier/inference-time-compute.md, ../../frontier/reasoning/reasoning-models.md
---

# Multimodality, Tool Use, and Reasoning-Time Compute

## The bottleneck

By late 2022, the RLHF-tuned chat model represented a genuine product: a conversational interface to a large pretrained language model, capable of following diverse instructions, generating useful text, and refusing clearly harmful requests. But the category of tasks it did well was narrower than it appeared. Text generation, summarization, paraphrase, simple Q&A, and code explanation worked. More demanding tasks exposed structural limitations:

**Factual grounding.** Chat models produced confident-sounding answers regardless of whether the answer was grounded in reliable knowledge. For questions with time-sensitive or obscure answers, the model had no mechanism to verify what it said. The training corpus had a cutoff date and was unevenly sampled across domains. Retrieval — looking something up before answering — was not built in.

**Multi-step reasoning reliability.** Chain-of-thought prompting improved reasoning accuracy substantially, but the model's reasoning steps were still generated as plausible-sounding completions rather than as verified logical inferences. Long arithmetic chains accumulated errors. Mathematical proofs drifted into false steps. Code generation produced syntactically plausible but sometimes semantically wrong programs. The model had no mechanism to verify its own outputs or to catch errors before producing them.

**Modality restrictions.** Language models operated on text. The world does not. An enormous fraction of useful information is in images, charts, diagrams, audio, video, tables, and code — formats that text-only models could not directly process. Users had to manually describe images or transcribe audio; the model could not see or hear.

**Execution gap.** A language model could write Python code, but it could not run it. It could propose a web search, but it could not perform one. The outputs of the model were text representations of actions, not actions themselves. Bridging from language model outputs to real-world effects required external tooling.

The frontier era, running roughly from 2023 onward, addressed these bottlenecks in parallel along four lines: multimodal inputs and outputs, retrieval augmentation, tool use and agents, and reasoning-time compute.

---

## Multimodal models

### Vision-language models

The path to vision-language models had two precursors. First, CLIP (Radford, Kim, Hallacy et al., OpenAI, 2021) showed that a contrastive loss trained on 400 million (image, text caption) pairs from the internet could produce image and text encoders whose embedding spaces were aligned: semantically related images and texts ended up nearby in embedding space. CLIP representations were immediately useful for zero-shot image classification (compare an image embedding to text embeddings of class labels) and as image feature extractors for downstream tasks.

Second, the visual question answering (VQA) task had been a benchmark since 2015: given an image and a natural language question about it, produce a natural language answer. VQA required jointly processing image and text, and prior work had shown that convolutional features concatenated with text representations worked to some degree — but the resulting models were fragile and narrow.

The breakthrough was connecting a pretrained vision encoder (CLIP-style or a convolutional backbone) to a pretrained language model via an alignment layer, and fine-tuning the combined system on image-text interleaved data. Flamingo (Alayrac, Donahue et al., DeepMind, 2022) used cross-attention layers inserted between the frozen language model's layers to inject visual features from a pretrained vision encoder, trained on large-scale image-text data. It showed strong few-shot visual question answering and image captioning.

LLaVA (Liu, Li, Wu, Lee, 2023), InstructBLIP (Dai et al., 2023), and GPT-4V (OpenAI, 2023) followed, with GPT-4V representing the first frontier-quality vision-language model deployed at scale. The approach: pretrain the language model and vision encoder separately, connect them with a small adapter, and fine-tune on instruction-following data that included images.

GPT-4V demonstrated capabilities qualitatively beyond earlier vision-language models: reading text in images (OCR), understanding charts and diagrams, parsing spatial relationships in photographs, interpreting handwritten notes, reasoning about image content in combination with factual knowledge. The gap between describing an image and reasoning about it was substantially closed.

### Audio, video, and multimodal generation

Speech recognition had used neural networks since the deep learning turn (deep neural network + HMM, ca. 2012). Whisper (Radford et al., OpenAI, 2022) trained a single end-to-end transformer on 680,000 hours of multilingual audio, achieving state-of-the-art performance across many languages without language-specific fine-tuning. The recipe was the same as for text: self-supervised pretraining at scale, followed by fine-tuning on task data.

Video understanding lagged behind image understanding for architectural reasons: video adds a temporal dimension that requires either 3D convolutions, frame-level attention, or specialized temporal encoders. The compute cost scales with frame count, making long-video understanding expensive. Models that could summarize, classify, or answer questions about video clips appeared by 2023–2024, but fine-grained long-video reasoning remained difficult.

Multimodal *generation* — producing images, audio, or video from text prompts — developed in parallel with multimodal understanding. Diffusion models (DDPM, Denoising Diffusion Probabilistic Models, Ho et al. 2020; DALL-E 2 and Stable Diffusion, 2022) enabled high-quality image generation from text prompts. The architecture was different from transformers — a U-Net denoising network applied iteratively to a noisy latent — but the training paradigm was similar: self-supervised pretraining on large image-text datasets. Text-to-speech synthesis (TTS) using transformers achieved near-human naturalness by 2023. Text-to-video generation appeared at lower quality by the same period.

### What multimodality changed

Multimodal models expanded the interface between AI systems and the world. A model that could see, read, and hear was useful for a far wider range of tasks than a text-only model: medical imaging analysis, document processing, accessibility tools (describing images for blind users), code screenshot understanding, and real-world robotics (vision-to-action control loops). The frontier model was no longer a text processor but a general-purpose perception-and-language system.

---

## Retrieval-augmented generation (RAG)

### The hallucination problem and its structural cause

Language model hallucination — the generation of plausible-sounding but false statements — is a structural consequence of the training objective. The model is trained to predict the next token, maximizing the probability of the correct continuation given the context. When the context does not contain the information needed to answer a question, the model does not produce an error state; it produces a plausible-sounding completion based on patterns in the training distribution. That completion may be wrong.

This is qualitatively different from a database query, which either finds the answer or returns no result. A language model always returns something; it has no "I don't know" state in its raw next-token prediction form. RLHF fine-tuning can train the model to express uncertainty in some situations, but the underlying prediction mechanism is unchanged.

Retrieval-augmented generation addresses this by separating factual storage from linguistic processing. A retrieval system maintains an external knowledge store — a document corpus, a database, a search index. At inference time, the model's query is used to retrieve relevant documents, which are inserted into the context window. The language model then generates its answer conditioned on both the query and the retrieved context. The model's job is to extract and synthesize information from retrieved documents rather than to recall it from weights.

### RAG architectures

The foundational paper was Lewis, Perez et al. ("Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," NeurIPS 2020). It combined a dense passage retriever (DPR, using a BERT-based bi-encoder) with a seq2seq generative model (BART), end-to-end trained so the retrieval and generation components jointly optimized task performance.

Production RAG systems typically use a simpler and more modular pipeline: embed documents and queries into dense vectors using a frozen or separately trained embedding model, store document vectors in a vector database (Pinecone, Weaviate, pgvector), retrieve the top-k most similar documents by cosine or dot-product similarity, and inject the retrieved text into the language model's context. This "naive RAG" pattern does not require joint training and can be applied to any pretrained language model.

More sophisticated variants — reranking retrieved documents, iterative retrieval (retrieve, read, then retrieve more based on what was learned), structured retrieval from databases via generated SQL or SPARQL queries — appeared as the pattern matured. The common theme: the language model's role is synthesis and language generation; external systems handle factual storage and retrieval.

RAG reduced hallucination substantially on knowledge-intensive tasks, made model outputs more verifiable (the retrieved sources can be shown to the user), and enabled language models to access up-to-date information beyond their training cutoff. Its limitations: retrieval quality depends on the quality of the index and embedding model; the model can still misinterpret or misapply retrieved information; and for tasks requiring deep integration of many sources, simple RAG pipelines degrade.

---

## Tool use and agentic systems

### The tool-use paradigm

GPT-4's function calling API (2023) and the tool-use capabilities of Claude, Gemini, and other frontier models formalized a pattern that had been explored in earlier research: the language model can emit structured "tool call" outputs that are executed by external systems, with the results returned to the model's context for further processing.

The basic loop: the model receives a user request, decides which tool to call and with what arguments, emits a structured tool call (in JSON or similar), the surrounding system executes the tool call (a web search, a database query, a Python interpreter, a calculator, an API call), returns the result to the model's context, and the model generates the next step or the final response.

This architecture gave language models access to arbitrary external capabilities: web search for up-to-date information, code execution for reliable computation, calendar APIs for scheduling, file systems for document access, database queries for structured data retrieval. The model's natural language capabilities were combined with the precision of programmatic tools.

The key enabling insight was that language models, once trained to follow instructions, could learn to use tools through in-context examples and fine-tuning on tool-use demonstrations. The model did not need to be retrained for each new tool; it needed only a description of the tool's interface and examples of its use.

### Agents and multi-step planning

A language model making a single tool call is a capability. A language model iteratively planning, executing, observing, and replanning across many tool calls toward a long-horizon goal is an **agent**. The agent paradigm treats the language model as a reasoning engine that interacts with the world through a perception-action loop.

ReAct (Yao, Zhao, Yu et al., 2022) formalized a prompting pattern that interleaved reasoning ("Thought") and action ("Action") steps, with observation ("Observation") steps following each action. The resulting trace — Thought → Action → Observation → Thought → Action → ... — resembled explicit deliberate reasoning and significantly improved performance on knowledge-intensive multi-step tasks over either pure chain-of-thought (no tool use) or pure tool-use (no reasoning).

Subsequent agent frameworks — AutoGPT (open-source, 2023), the Toolformer model (Schick et al., 2023), function-calling-based agents — extended this to real tasks: web research, document summarization, code writing and execution, scheduling, and multi-step data analysis. These systems remained fragile: errors in early steps propagated, replanning was unreliable, and long-horizon coherence was difficult to maintain. But they demonstrated the direction: the frontier model as an autonomous executor of multi-step tasks, not just a one-shot text generator.

### Code execution as grounding

One of the most reliable tool-use patterns was code generation combined with immediate execution. Rather than generating a chain-of-thought reasoning trace in natural language (which could contain errors that were not caught before the answer was produced), the model generated Python code to solve the problem, executed it in an interpreter, and returned the output. This grounded the computation: the code was checked by the interpreter, arithmetic was done by the CPU, and the result was the actual output of a program rather than a plausible-sounding continuation.

The Program-Aided Language model (PAL, Gao et al., 2022) and the Code Interpreter feature in ChatGPT (2023) demonstrated this pattern. For mathematical reasoning, data analysis, and algorithmic problems, code-execution grounding substantially improved accuracy over pure language model generation. It also made the model's reasoning auditable: the generated code was inspectable, not just the output.

---

## Mixture of experts and efficiency

### The architectural challenge of scale

Training a 175B dense transformer means activating all 175B parameters for every forward pass. At inference time, generating a single token requires computing through all 175B parameters. This is expensive in memory and compute. As models grew larger — toward 500B, 1T parameters — the inference cost became prohibitive for high-throughput deployment.

Mixture of Experts (MoE) architectures address this by making only a fraction of the model's parameters active for each forward pass. An MoE transformer replaces some or all of the feedforward sublayers with a "mixture of experts" layer: a set of N independent feedforward networks ("experts") and a routing network ("gating network") that, for each token, selects k of the N experts to activate (typically k=1 or k=2). Only the selected experts compute outputs for that token; the rest are inactive.

The result: a model with N times more total parameters but only a fraction more compute per token than a dense model. A 1T-parameter MoE model with 8 experts and top-2 routing activates roughly 2/8 of its expert parameters per token, achieving closer to 250B-parameter compute while retaining 1T-parameter capacity.

The Switch Transformer (Fedus, Zoph, Dean, 2022) demonstrated that MoE transformers could be trained stably at scale and achieved better loss per FLOP than dense transformers. Mixtral 8x7B (Mistral AI, 2023) demonstrated that an open-weight MoE model could match or exceed dense models roughly twice its size while using similar compute per token.

The trade-off: MoE models require routing infrastructure, can have load imbalance (some experts are overused, others underused, requiring auxiliary losses to encourage balanced routing), and have higher memory requirements (all experts must be loaded even if only a few are active per token). But the efficiency gains at scale made MoE the likely dominant large-model architecture going forward.

---

## Open-weight models and the democratization of the frontier

### LLaMA and the open-weight ecosystem

Prior to 2023, frontier language models were accessible only through APIs. The weights were proprietary. This limited who could study, fine-tune, audit, or deploy frontier-class models. The open-source community had models, but a significant quality gap separated open models from GPT-3-class systems.

Meta AI's LLaMA (Touvron et al., 2023) changed this by releasing weights for a family of 7B to 65B parameter models trained on publicly available data (Common Crawl, Wikipedia, GitHub, books). The key observation, derived from Chinchilla scaling insights: train smaller models on much more data than previous practice, and a 13B LLaMA model could match GPT-3 (175B) on many benchmarks.

The LLaMA weights leaked shortly after the restricted release, and within weeks the open-source community had produced fine-tuned derivatives: Alpaca (Stanford, instruction-tuned on GPT-3.5 outputs), Vicuna, and dozens more. A full open-source fine-tuning pipeline for instruction tuning was demonstrated at costs under $600.

LLaMA 2 (2023, released with permissive license) and LLaMA 3 (2024) continued the series with instruction-tuned variants. Mistral 7B and Mixtral 8x7B (Mistral AI, 2023) showed that small, well-trained open models could be highly competitive with larger models for many tasks. The open-weight ecosystem — including Falcon, Qwen (Alibaba), Gemma (Google), Phi (Microsoft), and many others — made fine-tuning, alignment research, safety evaluation, and specialized deployment accessible without API dependence.

The open vs. closed frontier debate became a significant policy and research question: open models enable research and democratize access but also enable misuse at scale without guardrails. The debate remains unresolved, with different organizations taking different stances based on their threat models and values.

---

## Reasoning-time compute: the o1 paradigm

### The bottleneck that scaling alone did not fix

The scaling laws predicted that more pretraining compute would produce better models. But for a category of tasks — formal mathematics, competitive programming, multi-step logical reasoning, complex planning — the improvement from scaling was real but not sufficient. A model trained on 10× more compute was better, but it was not qualitatively more reliable on hard reasoning tasks. Errors accumulated across long reasoning chains in ways that more parameters did not reliably prevent.

The key insight driving the inference-time compute paradigm was that thinking harder about a problem — spending more compute at inference time — could substitute for or supplement training-time compute. Rather than training a model to produce the correct answer in one forward pass, train a model to search through multiple reasoning paths and select the best one, or to generate extended deliberation before committing to an answer.

### o1 and chain-of-thought reinforcement learning

OpenAI's o1 (September 2024) operationalized this insight. The model was trained using reinforcement learning on a large-scale process reward model — a model that scores not just the final answer but the quality of each reasoning step. This encouraged the model to develop the habit of "thinking" through a problem in an extended internal monologue before producing an answer, and to check and revise its reasoning when it detected errors.

The training signal was different from standard RLHF: rather than preference data collected from human raters evaluating final outputs, the reward signal was derived from verifiable ground truth (correct vs. incorrect final answer in math/code/logic domains) applied over many generated reasoning traces. This allowed scale in the training signal: you could generate millions of (problem, reasoning trace, answer) triples, verify correctness automatically, and use the verification signal to improve the reasoning process.

The results on hard benchmarks were striking. o1 achieved scores on the AIME mathematics competition (the hardest US high-school competition) that had previously been achieved only by the top human competitors. It achieved competitive performance on the Codeforces programming competition. For problems in mathematics and formal reasoning, o1 was substantially better than GPT-4 — not because it had more parameters or more pretraining data, but because it spent more inference-time compute on deliberation.

### The scaling axis shift

o1 introduced a new axis of scale: **inference-time compute**. Prior work had established training-time compute (model size × tokens trained) as the primary scaling axis. o1 showed that at fixed model size and training budget, you could trade inference-time compute for answer quality. The more "thinking tokens" the model generated before answering, the better it performed on hard problems.

This has significant implications for deployment architecture. Generating many thinking tokens per query is expensive — a single hard o1 query can cost 10–100× more in compute than a standard GPT-4 query. Users implicitly pay (in latency and API cost) for the extended deliberation. This created a new design question: for which tasks is extended deliberation worth the cost? For hard mathematics or formal verification, yes. For a casual summarization request, no.

It also reopened questions about the relationship between language model "reasoning" and genuine deliberate thought. Does generating a chain-of-thought constitute reasoning, or is it pattern completion that mimics reasoning? The o1 results do not settle this: the model's extended deliberation produces better answers, but whether the deliberation traces involve genuine inference or sophisticated autocomplete of reasoning-shaped text is unclear. The practical results are unambiguous; the theoretical interpretation is not.

### Reinforcement learning for reasoning

The training approach behind o1 — using RL with verifiable reward signals to improve step-by-step reasoning — became a research direction in its own right. DeepSeek-R1 (DeepSeek AI, January 2025) reproduced and extended o1-like reasoning capabilities using RL on chain-of-thought traces, with the critical feature of being released as an open-weight model. DeepSeek-R1 demonstrated that the RL-for-reasoning training approach was not proprietary and could be replicated by well-resourced labs outside the US.

The results reignited scaling and efficiency debates: DeepSeek-R1 achieved performance comparable to o1 at a fraction of the reported training cost. Whether this reflected genuine efficiency gains, different accounting of costs, or access to distilled training data from frontier models (using a larger model's outputs to train a smaller one — "distillation") was actively debated.

---

## The current frontier as a system

By early 2026, the frontier AI system is no longer a language model but a compound system:

- A **pretrained transformer** (usually decoder-only, often MoE) trained on trillions of tokens of text, code, and interleaved multimodal data
- An **instruction-tuning and RLHF post-training stage** that aligns outputs to human preferences
- **Multimodal input** (text, image, audio, video, documents) processed through modality-specific encoders connected to the language model backbone
- **Tool use** (web search, code execution, database queries, API calls) executed through structured function-calling interfaces
- **Retrieval augmentation** for tasks requiring up-to-date or domain-specific knowledge
- **Extended reasoning** via chain-of-thought or RL-trained deliberation for hard tasks
- **Very long context windows** (100K–1M+ tokens) for document-level and session-level tasks

The model interacts with the world through this full stack, not just through text generation. The interface has evolved from a completion API to a multi-turn, multi-modal, tool-using agent that can plan and execute multi-step tasks.

The remaining bottlenecks, as of early 2026, are real:

**Systematic generalization.** Models still fail on tasks requiring systematic compositional reasoning that differs from patterns seen in training — novel combinations of familiar operations, formal proofs requiring chaining many steps, arithmetic over large numbers.

**Long-horizon coherence.** Multi-step agentic tasks remain brittle. Errors in early steps compound. Replanning after unexpected tool results is unreliable. The model's sense of task state across many turns degrades.

**Factual calibration.** Even with RAG, models sometimes confabulate. Knowing when to retrieve, what to retrieve, and how to integrate retrieved information with parametric knowledge remains imperfect.

**Alignment at capability frontier.** As capabilities increase — particularly with RL-trained reasoning that produces more autonomous and powerful behavior — ensuring that the system remains reliably aligned with user and societal values becomes harder. The mechanisms that work at current capability levels may not scale to substantially more capable systems.

---

## Quick reference

| Development | What it addressed |
|---|---|
| CLIP (2021) | Aligned image and text embedding spaces; enabled zero-shot image classification |
| Flamingo (2022) | Few-shot vision-language model via cross-attention injection into frozen LM |
| GPT-4V (2023) | Frontier-quality vision-language model; image understanding + language reasoning |
| Whisper (2022) | End-to-end multilingual speech recognition via transformer on 680K hours |
| RAG (Lewis et al., 2020) | Retrieval at inference time; reduces hallucination on knowledge-intensive tasks |
| Function calling / tool use | Structured tool call outputs executed externally; results returned to context |
| ReAct (2022) | Interleaved reasoning and tool-use steps for multi-step tasks |
| MoE / Mixtral | Sparse activation: more parameters, similar compute per token |
| LLaMA / open weights | Frontier-class models accessible for research, fine-tuning, and deployment |
| o1 (2024) | Inference-time compute via RL-trained extended deliberation; hard reasoning gains |
| DeepSeek-R1 (2025) | Open-weight o1-like reasoning; RL-for-reasoning replicated outside OpenAI |

---

*Sources: Radford et al. (2021), "Learning Transferable Visual Models From Natural Language Supervision" (CLIP); Alayrac et al. (2022), "Flamingo: a Visual Language Model for Few-Shot Learning"; Lewis et al. (2020), "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"; Yao et al. (2022), "ReAct: Synergizing Reasoning and Acting in Language Models"; Touvron et al. (2023), "LLaMA: Open and Efficient Foundation Language Models"; Fedus, Zoph, Dean (2022), "Switch Transformers: Scaling to Trillion Parameter Models." Frontier sections (GPT-4, o1, DeepSeek-R1) are based on public technical reports and announcements; details may be incomplete. Trust level: low — not yet reviewed by Alex.*
