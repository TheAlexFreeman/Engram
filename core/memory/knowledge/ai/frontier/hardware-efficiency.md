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
- hardware
- gpu
- tpu
- efficiency
- scaling
- chips
title: AI Hardware and Efficiency Trends
trust: medium
related: inference-time-compute.md, foundation-model-governance.md, agentic-frameworks.md, memetic-security-capability-robustness.md, ../frontier-synthesis.md
---

# AI Hardware and Efficiency Trends

Hardware is the physical substrate of everything else in this knowledge base — it determines
what model sizes are feasible, what inference latency is achievable, and ultimately what
the economics of AI deployment look like. This file surveys the hardware landscape through
early 2026, with attention to efficiency trends that matter for practitioners rather than
chip architecture minutiae.

---

## The Memory Wall: The Central Problem

The dominant constraint in LLM inference is **memory bandwidth**, not raw compute (FLOPS).
A GPU's tensor cores can perform arithmetic far faster than the HBM (High Bandwidth Memory)
can supply the weights and KV-cache values those operations need. The ratio of compute to
memory bandwidth — the *arithmetic intensity* — determines whether a workload is compute-bound
or memory-bandwidth-bound.

For autoregressive token generation:
- A 70B-parameter model in FP16 requires ~140 GB of memory just for weights.
- Each forward pass for a single token reads most of that memory once.
- Even at H100 HBM3 bandwidth (3.35 TB/s), reading 140 GB takes ~42 ms — meaning single-token
  generation is bounded at roughly 24 tokens/sec per GPU *regardless* of FLOP count.

This is why techniques like quantization (halving weight size doubles this limit) and
speculative decoding (amortizing the weight reads across multiple tokens) dominate
production optimization — they address the actual bottleneck.

---

## NVIDIA: The Incumbent

### H100 (Hopper, 2022–present)

The H100 SXM5 remains the workhorse of frontier AI as of early 2026:
- **FP8 tensor cores**: 3,958 TFLOPS FP8, first time FP8 was native in NVIDIA hardware —
  enabling production FP8 inference with quantization-aware training.
- **HBM3**: 3.35 TB/s bandwidth, 80 GB capacity (SXM5 variant).
- **NVLink 4.0**: 900 GB/s GPU-to-GPU bandwidth enabling tight multi-GPU coupling.
- **Transformer Engine**: Hardware-level mixed-precision management (FP8/BF16 selection
  per tensor per operation) with software/hardware co-design.

H100 clusters (8× per node via NVLink, nodes connected via InfiniBand or NVLink Switch)
are the standard unit of frontier training infrastructure. Microsoft Azure, AWS, GCP, and
Oracle Cloud all offer H100 instances; demand continues to exceed supply as of Q1 2026.

### H200 (2024–present)

H200 is an H100 die with upgraded HBM3e memory:
- **HBM3e**: 4.8 TB/s bandwidth, 141 GB capacity — 43% more bandwidth, 76% more capacity.
- Same compute as H100 (same die).
- Memory-bound workloads (inference) benefit substantially; training less so.
- H200 effectively doubles the maximum model size that fits on a single GPU in FP16.

### Blackwell Architecture (B100/B200, 2025–present)

Blackwell is NVIDIA's 2025 architecture and the most significant generational leap since
Hopper:
- **B200 SXM**: 20 PFLOPS FP4, 10 PFLOPS FP8, 4 TB HBM3e, 8 TB/s bandwidth.
- **FP4 support**: First native FP4 tensor cores; enables 4× the inference throughput of
  FP8 for models trained with FP4 quantization awareness.
- **NVLink 5.0**: 1.8 TB/s GPU-to-GPU bandwidth.
- **GB200 NVL72**: The flagship system — 72 Blackwell GPUs + 36 Grace CPUs in a single
  rack, connected via NVLink Switch. 1.4 exaFLOPS FP8, 13.5 TB HBM3e. Microsoft,
  Google, Meta, and xAI placed early GB200 NVL72 orders; deployment accelerating through 2025.
- **Disaggregated memory pooling**: NVLink Switch allows any GPU in the rack to access
  any other GPU's memory, enabling logical single-GPU programming across physically
  distributed HBM.

NVIDIA's Blackwell supply constraints eased somewhat in late 2025 as TSMC N4P yields
improved. Still heavily oversubscribed by hyperscalers.

### H100 vs. B200 Inference Performance (Rough)

| Metric | H100 SXM5 | B200 SXM |
|---|---|---|
| HBM Bandwidth | 3.35 TB/s | 8 TB/s |
| HBM Capacity | 80 GB | 192 GB |
| FP8 TFLOPS | ~4,000 | ~18,000 |
| FP4 TFLOPS | — | ~36,000 |
| Power (TDP) | 700W | 1,000W |

For memory-bandwidth-bound inference, B200 delivers roughly 2.4× the throughput of H100
per GPU (bandwidth ratio), before considering batching improvements from larger HBM.

---

## Google: TPUs

Google's Tensor Processing Units are custom ASICs designed co-evolutionarily with
TensorFlow/JAX and the transformer architecture. Not commercially available (Google Cloud
offers access via TPU Pods).

### TPU v5e and v5p (2023–present)

- **v5e** ("efficiency"): Optimized for inference and mid-scale training. 393 TFLOPS BF16,
  16 GB HBM2, 819 GB/s bandwidth. Low cost per chip; scales via mesh topology.
- **v5p** ("performance"): Optimized for large-scale training. 459 TFLOPS BF16,
  95 GB HBM3, 2.76 TB/s bandwidth. Used for Gemini training.
- **Interconnect**: ICI (Inter-Chip Interconnect) at 1,600 Gbps per chip in a 3D torus —
  all-to-all bandwidth that NVIDIA NVLink can only achieve within a single server node.

### TPU v6 / Trillium (2024–present)

- 4.7× improvement in training performance per chip over v5e.
- Used for Gemini 2.0 and Gemini 2.5 training (announced 2024–2025).
- 2× HBM capacity vs. v5e; improved sparsity support.

### TPU Architectural Philosophy

TPUs make different tradeoffs than GPUs:
- **Matrix multiply units (MXUs)** instead of general CUDA cores — highly specialized but
  extremely efficient for dense matrix operations.
- **SRAM scratchpad** instead of L2 cache hierarchy — software controls data placement,
  enabling XLA/JAX to optimize memory access patterns at compile time.
- **Soft errors**: TPU clusters experience higher transient error rates than GPU clusters;
  Google's training infrastructure includes checkpoint-and-resume logic tuned for this.
- **Vendor lock-in**: TPU code (JAX/XLA) is not portable to NVIDIA hardware without
  significant porting effort. A strategic risk for organizations using TPUs.

### TPU vs. GPU for LLMs

Google's internal research suggests TPUs deliver 1.2–1.5× better price-performance for
large-batch training workloads. For inference, the gap is smaller and workload-dependent.
The ecosystem (tooling, pre-quantized models, serving frameworks) heavily favors NVIDIA.

---

## AMD: The Challenger

AMD's MI300X (2023) and MI300A (APU variant) represent the most credible NVIDIA
competition as of 2026:

- **MI300X**: 192 GB HBM3, 5.3 TB/s bandwidth, 1,307 TFLOPS FP16. The HBM capacity
  advantage is substantial — a 140B-parameter FP16 model fits in a *single* MI300X vs.
  requiring two H100s. This is decisive for inference serving large models with small batch sizes.
- **ROCm software stack**: AMD's GPU computing platform has historically lagged NVIDIA's
  CUDA in software maturity. ROCm 6.x (2024) significantly closed the gap; vLLM, PyTorch,
  and TensorFlow have first-class MI300X support. Triton (the GPU kernel language) now
  targets ROCm. Remaining gaps: less mature profiling tools, fewer optimized fused kernels.
- **Adoption**: Microsoft Azure (ND MI300X v5 instances), Meta (MI300X for inference
  serving), and Oracle all deployed MI300X at scale in 2024–2025. The HBM capacity
  advantage drove adoption specifically for large-model inference.

AMD's MI350X (Blackwell generation response) is expected H2 2025; specs not yet public
at knowledge cutoff but rumored to close the bandwidth gap with B200.

---

## Custom Silicon: Hyperscaler ASICs

Every major hyperscaler is building custom AI inference silicon:

### Google TPU (above)

### AWS Trainium / Inferentia

- **Inferentia 2 (2023)**: AWS's inference chip; 190 TFLOPS FP16, 32 GB HBM2e. Deployed
  across many AWS managed ML services. INF2 instances offer competitive price-performance
  for certain inference workloads but lag H100 on raw throughput.
- **Trainium 2 (2024)**: Training chip; 3× Trainium 1 performance. Used for Amazon's
  internal model training. AWS claims price-performance advantages for long training runs
  but third-party validation is limited.

### Meta MTIA

- **MTIA v1 (2023)**: Meta's first inference accelerator, deployed for recommendation
  models. 102 TOPS INT8. Primarily for ad ranking and recommendation, not transformer LLMs.
- **MTIA v2 (2025, rumored)**: Expected to target LLM inference at scale, reducing
  Meta's dependence on NVIDIA.

### Apple Neural Engine / ANE

- **M4 Neural Engine (2024)**: 38 TOPS, tightly integrated with CPU and GPU on M4 die.
  Apple Intelligence runs 3B on-device models using the ANE; the integration of CPU DRAM
  (up to 128 GB in M4 Max) as model memory is a unique architectural advantage for
  local inference — a MacBook Pro can hold a 70B Q4 model in RAM.
- **Strategic significance**: Apple's vertical integration (silicon + OS + framework +
  application) enables optimizations impossible in the datacenter/cloud model.

### Groq LPU (Language Processing Unit)

- Groq's architecture fundamentally differs from GPU: **deterministic execution** with
  a massive on-chip SRAM (230 MB per chip, 80× more than H100's 50 MB L2). No HBM.
- **No memory latency stalls**: weights live in SRAM, eliminating the HBM bandwidth
  bottleneck for models that fit.
- **Tradeoffs**: Model must fit in SRAM (limits to quantized 7B–34B range for current
  chips); batch size is limited; not suitable for training.
- **Performance**: Groq GroqCloud demonstrates 500–800 tokens/sec for Llama 3 70B Q4 —
  significantly faster than H100 for this workload. Leads speed benchmarks on
  ArtificialAnalysis.ai as of Q1 2026.
- **Scale**: Groq does not yet have hyperscale capacity; primarily used for latency-
  sensitive applications.

### Cerebras Wafer-Scale Engine

- WSE-3 (2024): Single silicon wafer as one chip — 900,000 cores, 44 GB on-chip SRAM,
  125 PB/s memory bandwidth (2,000× H100 HBM bandwidth within-chip).
- Eliminates inter-chip communication for models that fit on one wafer.
- **Practical limitation**: The wafer is a fixed size; models larger than ~frontier GPT-3
  scale require inter-wafer communication, at which point the advantage diminishes.
- **Best for**: Ultra-low-latency inference for mid-size models; some training workloads.
- Cerebras announced partnership with Abu Dhabi's G42 for national AI infrastructure in 2024.

---

## Scaling Laws and Hardware Efficiency

### Chinchilla and Post-Chinchilla Corrections

Hoffman et al.'s Chinchilla (2022) established the compute-optimal training recipe:
training tokens ≈ 20× parameter count. Chinchilla-optimal models (e.g., 70B on 1.4T tokens)
were claimed to outperform over-large under-trained models (GPT-3 175B on 300B tokens).

Post-2023 practice has diverged from Chinchilla-optimal:

- **Inference-optimal training**: If a model will be run inference millions of times, it's
  worth *over-training* (more tokens, smaller model) to get a cheaper-to-serve model with
  the same capability. Llama 3 8B trained on 15T tokens is dramatically over-trained
  relative to Chinchilla but serves much cheaper than a 70B model.
- **Revised exponents**: DeepSeek (2024) and other labs suggest Chinchilla's exponents
  were slightly miscalibrated; optimal token count may be higher than 20×.

### The Efficiency Trendline

A useful rough heuristic: AI inference cost per token falls approximately 50% per year,
driven by a combination of:
1. Hardware generation improvements (H100 → H200 → B200)
2. Quantization adoption (FP16 → FP8 → FP4)
3. Serving framework improvements (PagedAttention, continuous batching, prefix caching)
4. Model architecture improvements (MoE, smaller distilled models)
5. Supply increases (more chips, more competition)

This is not a law — it's an observed trend that could slow if TSMC scaling hits physical
limits or if demand continues to outpace supply.

### Mixture-of-Experts (MoE) as Efficiency Architecture

MoE models activate only a subset of parameters per token (e.g., 2 of 64 expert networks),
allowing a model with 400B total parameters to match a 70B dense model's inference cost
while achieving stronger capability through total parameter count.

- **GPT-4**: Widely believed to be a sparse MoE (8 experts × ~50B parameters = ~400B
  total); each forward pass activates ~2 experts.
- **Mixtral 8×7B / 8×22B (Mistral AI)**: First widely-released open MoE models (2024);
  8 experts, top-2 routing.
- **DeepSeek V2/V3 (2024)**: 236B parameters, 21B active per token, with Multi-Head
  Latent Attention (MLA) reducing KV-cache by 93×. Demonstrated strong performance at
  dramatically lower inference cost than comparable dense models. DeepSeek-V3 cost
  $5.6M to train (claimed) vs. $100M+ for comparable frontier dense models.
- **Tradeoffs**: MoE models have higher total memory requirements (all expert weights
  must reside in memory even if most are inactive per token); expert routing adds overhead;
  load imbalancing is a training challenge.

### Flash Attention and Attention Efficiency

FlashAttention (Dao et al., 2022) and FlashAttention-2/3 (2023–2024) rewrite the attention
computation to be IO-aware — fusing operations and tiling to maximize SRAM reuse and
minimize HBM reads/writes. It computes exact attention (no approximation) with:
- 2–4× speedup over naive attention on H100
- Sub-quadratic memory usage in sequence length (enabling longer contexts)
- Required for practical long-context inference (128K–1M token contexts)

FlashAttention-3 (2024) achieves 75% utilization of H100 FP16 Tensor Core peak throughput,
close to theoretical maximum.

---

## Power and Cooling: The Infrastructure Constraint

The H100 draws 700W; a GB200 NVL72 rack draws 120 kW. A hyperscale AI cluster of 10,000
GPUs requires ~7 MW — equivalent to a small town's electrical load.

**Data center power** has become a primary constraint on AI scaling:
- US data centers consumed ~17 GW in 2024 (EPRI estimate); AI is the fastest-growing
  component.
- New grid connections take 3–7 years to permit and construct; this timeline limits
  the realistic rate of AI compute expansion.
- **Liquid cooling** (direct-to-chip, immersion) is now standard for H100/B200 clusters;
  air cooling is insufficient at 700W+ per GPU.
- **Nuclear power**: Microsoft, Google, Amazon, and Oracle have all signed deals with
  nuclear operators (Three Mile Island restart, NuScale SMRs) for AI data center power.
  Long lead times mean these contributions are mostly post-2028.

This power/cooling infrastructure constraint is arguably the binding limit on frontier
AI scaling in 2026 — more so than chip manufacturing capacity.

---

## TSMC and the Manufacturing Chokepoint

All frontier AI chips (NVIDIA H100/B200, AMD MI300X, Google TPU, Apple ANE) are fabricated
at TSMC's advanced nodes (N4/N4P for Hopper/MI300X, N3 for Blackwell, future N2/A16 for
next-generation). This creates a single-point-of-concentration risk:

- TSMC holds ~90% of global advanced node capacity (sub-5nm).
- Taiwan's geopolitical status introduces supply chain risk that governments and
  corporations are spending tens of billions to mitigate (TSMC Arizona fabs, Samsung
  IDM2.0, Intel Foundry).
- TSMC Arizona (Phoenix) fabs producing N4 since 2024; N2 Arizona fab planned ~2028.
  Arizona fabs cost ~2× per wafer vs. Taiwan (union labor, supply chain immaturity).
- The CHIPS Act (US, 2022) provides $52B in semiconductor incentives, partly aimed at
  this concentration risk.

---

## Key Takeaways for AI Practitioners

1. **Memory bandwidth, not FLOPS, is the inference bottleneck.** Quantization and
   architectural choices (MoE, MLA) that reduce memory pressure compound directly into
   serving economics.

2. **Hardware generational gains are real but lumpy.** B200 is a genuine step change
   (~2.4× inference throughput/GPU vs. H100); not every generation is. Plan model
   serving costs on current-generation hardware, not anticipated future hardware.

3. **Custom silicon is proliferating but niche.** Groq for speed, Cerebras for latency,
   TPUs for Google workloads. NVIDIA maintains ecosystem dominance; AMD is a credible
   alternative specifically where large HBM is the constraint.

4. **Power and cooling are now infrastructure-layer concerns.** Organizations building
   on-premise GPU clusters need dedicated power and liquid cooling infrastructure —
   not just rack space.

5. **The cost curve is steep and ongoing.** A task that cost $1 in GPT-4 API calls in
   2023 costs ~$0.05–0.10 in 2025 equivalents. This has second-order effects: use-cases
   that were uneconomical become viable; products built on "cheap enough" assumptions
   face competitive pressure as the baseline moves.

---

## Engram Relevance

- **Local inference viability**: Apple Silicon M-series (up to 128 GB unified memory)
  makes running 70B Q4 models locally practical, relevant if agent_memory_mcp is extended with
  local inference. MacBook Pro M4 Max is a reasonable development target for self-hosted
  semantic search or generation.
- **Embedding model costs**: Embedding models used for semantic search (see semantic_tools.py)
  are tiny relative to frontier LLMs — BGE-M3 (570M params) runs at thousands of
  requests/sec on a single H100 or comfortably on CPU. Inference cost for embeddings
  is essentially free at agent_memory_mcp's scale.
- **API cost trajectory**: Claude API costs for memory-intensive sessions are on the same
  downward trajectory as the broader market; long-context pricing per token is falling,
  which benefits memory system designs that load many context files per session.
