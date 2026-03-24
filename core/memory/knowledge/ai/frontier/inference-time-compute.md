---
category: knowledge
confidence: high
created: 2026-03-20
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-001
source: external-research
status: active
tags:
- ai/frontier
- inference
- serving
- efficiency
- quantization
- speculative-decoding
- vllm
title: Inference-Time Compute Infrastructure
trust: medium
related: reasoning/test-time-compute-scaling.md, ../history/frontier/multimodality-tool-use-and-reasoning-time-compute.md, ../../mathematics/probability/bayesian-inference-priors-posteriors.md
---

# Inference-Time Compute Infrastructure

The locus of ML engineering competition shifted decisively in 2024–2026 from training
throughput to *inference efficiency*. As frontier models stabilize (GPT-4-class capability
is widely accessible), the differentiating question is: how cheaply and quickly can that
capability be served at scale? This file surveys the infrastructure layer — serving
frameworks, decoding strategies, and compression techniques — that answers that question.

---

## Why Inference Economics Matter Now

Training a frontier model costs tens to hundreds of millions of dollars and happens once.
Inference runs billions of times per day across an entire user base. Even a 10% throughput
improvement at inference time translates directly to 10% lower cost per token or 10% more
headroom for additional users. OpenAI's stated 99% cost-per-token reduction from GPT-4
launch (2023) to early 2025 was driven almost entirely by inference optimization, not
model downsizing.

The compute profile of inference also differs sharply from training:

- **Memory-bandwidth bound, not compute-bound**: generating tokens sequentially reads
  KV-cache and weights repeatedly; the GPU's arithmetic units are often idle waiting
  for memory transfers.
- **Latency vs. throughput tradeoff**: interactive use-cases need low first-token latency;
  batch workloads want maximum tokens/second/dollar. Serving systems must satisfy both.
- **Heterogeneous request mix**: short prompts, long documents, multi-turn conversations,
  and tool-use chains arrive unpredictably; static batching wastes capacity.

---

## vLLM

vLLM (UC Berkeley, open-sourced May 2023) is the de-facto standard open-source LLM
serving framework as of early 2026. Its central innovation is **PagedAttention**, which
treats the KV-cache as virtual memory pages rather than pre-allocated contiguous tensors.

### PagedAttention

In standard attention, each sequence reserves a contiguous block of GPU memory for its
KV-cache, sized to the *maximum possible* output length. This causes 60–80% memory
waste (internal fragmentation + pre-allocation headroom). PagedAttention:

1. Divides KV-cache into fixed-size pages (blocks), similar to OS virtual memory.
2. Maps logical KV positions to physical pages non-contiguously.
3. Allows pages to be shared across sequences (prefix caching) and allocated on demand.

Result: 2–4× higher GPU memory utilization → 2–4× more concurrent sequences → proportionally
higher throughput at the same hardware cost.

### Continuous Batching

vLLM uses continuous (iteration-level) batching rather than static request batching.
New requests join the batch as soon as a sequence finishes, without waiting for the
entire batch to complete. This dramatically improves GPU utilization under variable-length
workloads and reduces mean queue time.

### Prefix Caching / Prompt Caching

Repeated system prompts, RAG context preambles, or multi-turn conversation prefixes can
be cached as pre-computed KV pages and reused across requests. Anthropic (claude.ai),
OpenAI, and Google (Gemini) all offer API-level prompt caching with significant discounts
(50–90% cost reduction on cached tokens). vLLM implements this natively for self-hosted
deployments.

### Distributed Serving

vLLM supports tensor parallelism (splitting weight matrices across GPUs), pipeline
parallelism (splitting transformer layers across GPU nodes), and combined strategies for
very large models. The `LLMEngine` API exposes these as configuration parameters,
abstracting the distributed complexity.

### vLLM Ecosystem (2025–2026)

- **Production adoption**: Adopted by Anyscale (Ray Serve), Modal, Together AI, Fireworks,
  and most major inference API providers as the underlying engine.
- **Speculative decoding integration**: vLLM added native support for speculative decoding
  (see below) in late 2024.
- **Multi-modal support**: Vision-language models (LLaVA, Qwen-VL, etc.) are first-class.
- **LoRA serving**: Multiple LoRA adapters can share a single base model in memory,
  enabling fine-tuned model serving without per-adapter GPU allocation.
- **Alternatives**: SGLang (Stanford, optimized for structured generation and multi-call
  programs), TensorRT-LLM (NVIDIA, highest raw throughput on A100/H100 with CUDA
  graph optimization), DeepSpeed-FastGen (Microsoft, disaggregated prefill/decode).

---

## Speculative Decoding

Autoregressive decoding generates one token per forward pass — the fundamental throughput
bottleneck. Speculative decoding breaks this constraint by parallelizing verification.

### Mechanism

1. A small **draft model** (e.g., 7B parameters) generates K candidate tokens rapidly.
2. The large **target model** evaluates all K tokens in a *single* parallel forward pass.
3. Tokens that match the target model's distribution are accepted; the first mismatch
   triggers rejection and the target model supplies the correct token.
4. The process repeats from the accepted prefix.

Because the target model's forward pass is memory-bandwidth bound (not compute bound),
verifying K tokens in parallel costs roughly the same wall-clock time as verifying 1 —
so accepting 3–4 tokens per round gives 3–4× throughput improvement with **identical
output distribution** (mathematically guaranteed, not approximate).

### Draft Model Strategies

- **Separate small model**: A 7B or smaller model from the same family (e.g., Llama 3 8B
  drafting for Llama 3 70B). Requires maintaining two model weights in memory.
- **Self-speculative / layer skipping**: The target model drafts using early transformer
  layers, then verifies with the full network. No extra model weights; lower draft quality.
- **Medusa heads**: Multiple linear heads attached to the target model predict several
  future tokens simultaneously. Simple, but draft quality is lower than a separate model.
- **EAGLE (Efficient Autoregressive Generation with Lookahead)**: Uses a single autoregressive
  head with access to hidden states; achieves high draft acceptance rates (~80%) with
  minimal overhead. Adopted by several production systems in 2025.
- **SpecInfer / tree-based speculation**: Generates a *tree* of candidate token sequences
  rather than a single chain; verifies multiple branches in one pass, accepting the
  longest consistent prefix. Higher GPU utilization, more complex implementation.

### Practical Acceptance Rates

Acceptance rates (average tokens per draft accepted) depend heavily on:
- Task type: repetitive/predictable text (code, structured data) → higher acceptance
- Domain match between draft and target models
- Sampling temperature: greedy decoding → near-100% acceptance; high temperature → lower

Typical acceptance rates: 2–4 tokens per round in practice, translating to 1.5–3× wall-clock speedup.

### When Speculative Decoding Helps (and Doesn't)

**Helps**: Latency-sensitive interactive use, code generation, structured outputs, low-to-medium temperature sampling, hardware where the target model's forward pass is bandwidth-bound.

**Doesn't help (much)**: Very high-temperature creative sampling, prompt-heavy/short-response workloads (prefill dominates), systems bottlenecked on data I/O rather than GPU.

---

## Quantization

Quantization reduces the numerical precision of model weights (and sometimes activations)
from the training default (BF16 / FP16, 16-bit) to 8-bit, 4-bit, or lower. This shrinks
model size and increases effective memory bandwidth, at some quality cost.

### Why It Works (and Its Limits)

Neural network weights follow approximately Gaussian distributions; most values are small,
with occasional outliers. Low-bit formats can represent these distributions with acceptable
fidelity if outliers are handled separately. The hard constraint: quantization is lossy —
perplexity increases, and for some tasks (math, multi-step reasoning) quality degrades
noticeably before inference throughput gains justify the tradeoff.

### Weight-Only Quantization (Post-Training)

Weights are quantized after training; activations remain in FP16 during inference. This
is the most widely deployed approach because it:
- Requires no retraining or calibration data
- Is straightforward to implement (quantize weights, dequantize on the fly)
- Delivers 2× memory reduction (INT8) or 4× (INT4) with modest quality loss

Key methods:
- **GPTQ** (Frantar et al., 2022): Layer-wise quantization using second-order gradient
  information. State of the art for weight-only INT4; widely supported in llama.cpp, vLLM.
- **AWQ** (Lin et al., 2023): Activation-aware weight quantization — identifies and protects
  the ~1% of weights corresponding to large activations. Better quality than GPTQ at INT4,
  especially for instruction-following tasks.
- **GGUF / llama.cpp**: Format used for CPU and edge deployment; supports K-quants (e.g.,
  Q4_K_M) that mix precision per layer. Powers most local LLM use on consumer hardware.

### Weight + Activation Quantization (INT8)

Both weights and activations quantized to INT8. Enables use of INT8 tensor cores (faster
than FP16 on some hardware). More complex because activation distributions shift at
runtime.

- **LLM.int8()** (Dettmers et al., 2022): Handles outlier activations with mixed-precision
  decomposition. First practical W8A8 method; now largely superseded.
- **SmoothQuant** (Xiao et al., 2022): Migrates quantization difficulty from activations
  to weights via a mathematically equivalent transformation. Standard for W8A8 in
  production (TensorRT-LLM, DeepSpeed).

### Sub-4-bit and Extreme Quantization

- **QuIP# / QuaRot (2024)**: Achieve 2-bit quantization through incoherence processing
  (random rotation of weight space before quantization). Competitive quality at 2-bit;
  not yet production-standard but technically impressive.
- **1-bit models (BitNet b1.58, 2024)**: Microsoft Research trained models natively with
  ternary weights {-1, 0, +1}. At scale (>3B parameters) competitive with FP16 baselines
  on many benchmarks. Inference uses XNOR-popcount operations — potentially order-of-magnitude
  efficiency gains on specialized hardware. Not yet deployed in frontier products (2026).

### KV-Cache Quantization

The KV-cache grows linearly with sequence length and is a major memory bottleneck for long
contexts. Quantizing cached keys/values to INT8 or FP8 reduces this cost with minimal
quality impact. Supported natively in vLLM and TensorRT-LLM for long-context workloads.

### FP8: The Production Sweet Spot (2025–2026)

FP8 (8-bit floating point, two formats: E4M3 and E5M2) offers:
- 2× memory reduction vs. BF16
- Near-BF16 quality (floating point preserves dynamic range better than INT8)
- Native hardware support on H100 (FP8 tensor cores), with significant throughput gains

Meta's Llama 3.1 405B and many other frontier models are served in FP8 in production.
NVIDIA's TensorRT-LLM has first-class FP8 support; vLLM added FP8 in 2024.

---

## Prefill / Decode Disaggregation

A recent architectural trend (2024–2025) in production serving: splitting the inference
pipeline into separate *prefill* and *decode* phases running on different hardware pools.

- **Prefill** (processing the prompt): compute-intensive, parallelizable, benefits from
  high-FLOP hardware.
- **Decode** (generating tokens one-by-one): memory-bandwidth intensive, benefits from
  high-HBM-bandwidth hardware.

Running them together on the same GPU means neither phase gets its ideal hardware profile.
Disaggregation routes each phase to the appropriate resource pool. Google, ByteDance
(MoonCake), and Alibaba have published production disaggregated serving architectures
showing 30–50% throughput improvements. This is the frontier of production inference
systems as of 2026.

---

## Structured Output Generation

When applications require JSON, SQL, or other structured formats, constrained decoding
ensures outputs conform to a grammar without post-hoc filtering.

- **Outlines / lm-format-enforcer**: Python libraries that apply token masks at each decoding
  step, blocking tokens that would violate a given JSON schema or regex. Negligible quality
  loss; ~10–20% throughput overhead.
- **SGLang's RadixAttention**: Optimizes for programs that make multiple sequential LLM
  calls (chain-of-thought, tool use, structured generation loops) by caching and reusing
  KV-states across calls in a single program.
- **OpenAI Structured Outputs API (2024)**: Server-side constrained decoding for JSON Schema;
  now standard across major providers.

---

## Inference at the Edge

Driven by privacy requirements, latency constraints, and the economics of avoiding API calls,
on-device inference has matured rapidly:

- **Apple Intelligence (2025)**: On-device models (3B adapter + 7B base) using the Neural
  Engine; server-side Private Cloud Compute for overflow. Apple's approach of small
  specialized models rather than a single large generalist is influential.
- **Qualcomm AI Hub**: Optimized model deployment for Snapdragon NPUs; supports GPTQ/AWQ
  quantized GGUF models.
- **llama.cpp**: The primary engine for CPU and consumer GPU inference; GGUF format with
  K-quant support enables Llama 3 8B to run on a MacBook Pro at reasonable speed.
- **MLC-LLM**: TVM-based compilation targeting WebGPU, CUDA, Metal, Vulkan, OpenCL —
  enables browser-native LLM inference without plugins.
- **WebLLM**: Browser-based inference using WebGPU; Llama 3 8B runs at ~5–10 tokens/sec
  in Chrome on consumer hardware.

---

## Key Metrics and Benchmarks

| Metric | Definition | Typical frontier target |
|---|---|---|
| TTFT | Time to first token (prefill latency) | <500 ms for interactive |
| TPOT | Time per output token (decode latency) | <50 ms for interactive |
| Throughput | Tokens/second/GPU | Varies widely by model size |
| Cost | $/M tokens (input/output) | Falling ~50% per year |
| Memory efficiency | Usable batch size per GPU | Maximized via PagedAttention + quantization |

The LLM Performance Leaderboard (Artificial Analysis, ArtificialAnalysis.ai) tracks TTFT,
TPOT, throughput, and cost across providers with regular benchmarking. As of Q1 2026,
Groq (LPU hardware) leads on raw token generation speed; Fireworks and Together AI lead
on price-performance for batch workloads.

---

## Engram Relevance

For the agent_memory_mcp system specifically:

- **Self-hosted inference**: If agent_memory_mcp were extended with an embedded inference step
  (e.g., for semantic similarity in `memory_search`), quantized local models (via
  llama.cpp or Ollama) would be the right deployment target given the sandbox constraints.
- **Embedding models**: Sentence-transformers and similar embedding models are already
  small enough (22M–335M parameters) that INT8 quantization is routine. The semantic_tools.py
  similarity search would benefit from an optimized embedding engine.
- **Speculative decoding irrelevance**: As a memory/tool server rather than an inference
  service, agent_memory_mcp is not a primary beneficiary of speculative decoding — but the
  host agent (Claude) benefits, which reduces the cost of memory-intensive sessions.
- **Prompt caching**: Multi-turn conversations that repeatedly load the same memory context
  benefit from API-level prompt caching; the memory system's design (concise frontmatter
  summaries rather than raw document dumps) already minimizes prompt token cost.