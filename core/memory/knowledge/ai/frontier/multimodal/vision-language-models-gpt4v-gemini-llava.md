---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: clip-contrastive-vision-language-pretraining.md, generative-vision-models-dalle-stable-diffusion.md, audio-language-models-whisper-speech.md, ../retrieval-memory/colpali-visual-document-retrieval.md
---

# Vision-Language Models: GPT-4V, Gemini, LLaVA

**Vision-language models (VLMs)** are systems that accept both visual and textual input and produce textual output. Unlike image generators (text → image), VLMs perform **understanding and reasoning** over visual content. As of 2025-2026, VLMs are deployed widely in document analysis, scientific figure interpretation, chart question-answering, and general visual reasoning.

---

## The VLM Architecture Paradigm

### The Core Pattern

Most VLMs follow a **modular architecture**:

```
Image → [Image Encoder] → Visual Tokens → [Fusion Layer] → [LLM Backbone] → Text Output
Text  ────────────────────────────────────────────────────────────────────→
```

**Three interchangeable components**:
1. **Image encoder**: Converts image to intermediate visual representation (CLIP ViT, SigLIP, ConvNext)
2. **Projection/fusion**: Aligns visual tokens with the LLM's token space (linear projection, Q-Former, cross-attention layer)
3. **LLM backbone**: Generates text conditioned on fused vision-language context (Vicuna, LLaMA, Mistral, Gemma, Qwen)

The practical benefits of this modular design:
- Frozen pretrained components can be combined efficiently
- Instruction tuning can be applied at the fusion layer + LLM only (cheap)
- Different encoders can be swapped for domain performance

---

## GPT-4V and GPT-4o

### GPT-4V (OpenAI, 2023)

GPT-4V added visual input capability to GPT-4. The architecture is not fully disclosed, but from behavioral evaluation:

**Visual input processing**:
- Images are tiled into non-overlapping patches (high-resolution images into 512px tiles)
- Each tile is processed by a ViT-based encoder
- Visual tokens are interleaved with text tokens in the Transformer's input sequence

**Capabilities demonstrated**:
- Chart and diagram understanding: reading bar charts, pie charts, scientific plots
- Document analysis: OCR, form field extraction, table comprehension
- Mathematical reasoning from images: solving geometry problems with diagrams
- Medical imaging: though with appropriate disclaimers about clinical use
- Code debugging from screenshots

**Benchmarks** (MMMU, ScienceQA, TextVQA):
| Benchmark | GPT-4V | Best open source (at release) |
|-----------|--------|-------------------------------|
| MMMU (multi-discipline) | 56.8% | ~35-40% |
| ScienceQA (multimodal science) | 82.1% | ~70% |
| TextVQA (text in images) | 78.0% | ~65% |

### GPT-4o (OpenAI, 2024)

GPT-4o ("omni") introduced **native multimodality** — a single model handling text, image, and audio in a unified architecture, rather than separate modality-specific encoders patched together:

- **Lower latency**: Visual processing is no longer a separate pipeline; response times for visual queries dropped from ~5s to ~1s
- **Better modal integration**: Fine-grained interplay between visual and textual reasoning is improved when modalities are natively fused
- **Real-time vision**: Audio-visual simultaneous processing enables real-time conversation with visual context (demonstrated in live demos)

---

## Google Gemini

### Native Multimodality from Pretraining

Google DeepMind's Gemini (2023 / 1.5 2024 / 2.0 2025) was designed with **multimodality from the beginning** — unlike GPT-4V which added visual capability post-hoc. The model processes images, video, audio, and text in a unified architecture using a **Mixture of Experts** (see `../architectures/mixture-of-experts.md`) backbone.

**Key architectural properties**:
- Input: interleaved text, images, video frames, audio tokens, code, structured data
- Long-context: Gemini 1.5 demonstrated **1 million token context** (sufficient for one hour of video or several hours of audio)
- Multi-modal reasoning at scale: video understanding, multi-page document analysis, and code debugging from visual output

### Gemini 1.5 and Video Understanding

Gemini 1.5 Pro's 1M context window enables **direct video understanding**:
- Process all video frames as a sequence of image tokens
- No need for separate frame sampling or summarization pipelines
- Demonstrated: finding a specific moment in a 3-hour film from a text description; analyzing an entire scientific paper including all figures

**Benchmark performance (MMMU)**: Gemini Ultra (flagship) reported 62.4% on MMMU (multi-discipline multimodal understanding), surpassing GPT-4V's 56.8% at the time.

---

## Open-Source VLMs: LLaVA, InstructBLIP, Idefics

### LLaVA (Large Language and Vision Assistant)

**LLaVA** (Liu et al., 2023) demonstrated that simple CLIP + LLM fusion with instruction tuning produces competitive VLMs:

**Architecture**:
- Image encoder: CLIP ViT-L/14 (frozen)
- Projection: a single linear layer projecting visual tokens to LLM embedding dimension
- LLM backbone: LLaMA / Vicuna (instruction-tuned)

**Training (two stages)**:
1. **Feature alignment** (pre-training): Freeze encoder and LLM; train only the projection layer on image-caption pairs (595K CC3M data). Teaches the projection to align visual tokens with LLM space.
2. **Instruction tuning** (fine-tuning): Unfreeze LLM; train on 158K visual instruction-following examples (generated by GPT-4). Teaches the model to follow visual instructions.

**Key insight**: A simple linear projection is sufficient for the fusion step — expensive cross-attention mechanisms (BLIP-2's Q-Former) are not required if upstream encoders are high quality and the LLM is instruction-tuned.

**LLaVA-1.5 and LLaVA-1.6**: subsequent versions used higher resolution (336px tiling), stronger LLM backbones (Mistral, LLaMA-2), and larger instruction datasets. LLaVA-1.6 (LLaVA-NeXT) achieved SOTA among open models on several benchmarks.

### InstructBLIP (Salesforce, 2023)

**InstructBLIP** uses the **Q-Former** from BLIP-2 as its fusion mechanism:
- Q-Former: a lightweight Transformer with learnable "query" tokens that attend to frozen image encoder features via cross-attention
- The 32 query tokens summarize visual information into a fixed-length representation consumed by the LLM
- Instruction-specific query tokens enable conditioning the visual summary on the task instruction

The Q-Former enables efficient training (fewer visual tokens for the LLM), but adds architectural complexity compared to LLaVA's linear projection.

### Idefics (HuggingFace)

**Idefics** is HuggingFace's open reproduction of DeepMind's **Flamingo** model (Alayrac et al. 2022):
- **Flamingo architecture**: frozen CLIP image encoder + frozen large LLM (Chinchilla) + trainable **cross-attention layers** inserted between every transformer block of the LLM
- Cross-attention layers attend to image features at each LLM layer — deep fusion vs. prefix fusion

Flamingo demonstrated **in-context few-shot VLM**: showing examples of image+text pairs in the prompt enables VQA without fine-tuning. The architecture naturally supports **interleaved image-text sequences** (alternating images and text in a single context).

Idefics2 (2024) updated to a modern LLM backbone (Mistral-7B) and improved encoder alignment.

---

## The VLM Evaluation Landscape

### Key Benchmarks

| Benchmark | Task type | What it tests |
|-----------|-----------|---------------|
| **MMMU** | 30-discipline academic questions | Multi-discipline knowledge + visual reasoning |
| **ScienceQA** | Science education MCQ | Multimodal science understanding |
| **TextVQA** | VQA on natural images with text | Text in images (OCR + reasoning) |
| **DocVQA** | Document comprehension | Document layout, tables, forms |
| **ChartQA** | Chart reading | Data extraction from visual plots |
| **SEED-Bench** | 19 image/video subtasks | Diverse capability coverage |
| **MMBench** | 3000 VQA items (structured evaluation) | Standardized capability profiling |
| **ViDoRe** | Visual document retrieval | Multimodal retrieval (→ ColPali) |

### Benchmark Contamination and Saturation

MMMU became partially saturated by 2025 — leading models achieve >70% with frontier-scale compute. Harder successor benchmarks (MMMU-Pro, SWE-bench Multimodal) test more challenging compositional and procedural visual reasoning.

---

## Multi-Image and Video Handling

A key capability distinction among VLMs in 2025-2026:

| Feature | GPT-4V | GPT-4o | Gemini 1.5 | LLaVA-NeXT |
|---------|--------|--------|------------|------------|
| Multi-image support | Limited | Yes | Yes (up to 1M tokens) | Yes (recent) |
| Video understanding | No native | Yes (frames) | Yes (native, long-form) | Limited |
| Audio input | No | Yes | Yes | No |

---

## Key Papers

- Achiam, J., et al. (2023). GPT-4 Technical Report. arxiv:2303.08774. (GPT-4V capabilities reported here)
- Team, G., et al. (2023). Gemini: A family of highly capable multimodal models. arxiv:2312.11805.
- Liu, H., Li, C., Wu, Q., & Lee, Y. J. (2023). Visual instruction tuning. *Advances in NeurIPS*, 36. (LLaVA)
- Dai, W., Li, J., Li, D., et al. (2023). InstructBLIP: Towards general-purpose vision-language models with instruction tuning. *NeurIPS 2023*.
- Alayrac, J. B., Donahue, J., Luc, P., et al. (2022). Flamingo: a visual language model for few-shot learning. *Advances in NeurIPS*, 35.
