---
source: agent-generated
origin_session: core/memory/activity/2026/03/27/chat-001
created: 2026-03-27
trust: medium
type: scope-note
plan: multimodal-ai-frontier-research
phase: orientation
---

# Multimodal AI Frontier Research — Scope Note

## Purpose

Define the boundaries, target files, and cross-reference map for a new `ai/frontier/multimodal/` subdomain covering vision-language models, audio-language systems, and embodied AI.

## Existing coverage audit

### What already touches multimodal AI

1. **ColPali** (`retrieval-memory/colpali-visual-document-retrieval.md`): detailed treatment of visual document retrieval using PaliGemma + late interaction. Covers the OCR-bypass paradigm, page-level embedding, MaxSim scoring. This is the only multimodal file in the AI domain. The new multimodal/ files should contextualize ColPali within the broader VLM landscape rather than re-cover it.

2. **Agentic RAG patterns** (`retrieval-memory/agentic-rag-patterns.md`): discusses multi-step retrieval, query decomposition, corrective RAG, and RAGAS evaluation — all text-focused. The multimodal RAG synthesis file should extend this to multimodal retrieval patterns.

3. **Long-context architecture** (`retrieval-memory/long-context-architecture.md`): covers the context-window scaling trajectory (4K → 1M+). The multimodal files should address how visual/audio tokens consume context budget and the implications for multimodal long-context.

4. **Agent architecture patterns** (`multi-agent/agent-architecture-patterns.md`): covers ReAct, reflection, multi-agent coordination — no multimodal perception layer discussed. The embodied AI file should connect to how perceptual grounding changes agent architecture.

5. **Frontier synthesis** (`frontier-synthesis.md`): cross-cutting synthesis of the AI domain's relevance to the memory system. Trust: low. The multimodal synthesis should be referenced as extending this document's scope.

### What does NOT already exist

- No file on CLIP or contrastive vision-language pretraining
- No file on generative vision models (DALL-E, Stable Diffusion, Imagen)
- No file on vision-language models as a class (GPT-4V, Gemini, LLaVA)
- No file on audio-language models (Whisper, AudioLM, GPT-4o audio)
- No file on embodied AI (RT-2, GATO, SayCan)
- No multimodal RAG synthesis connecting retrieval patterns to vision/audio

## Boundary decisions

| Boundary | Decision | Rationale |
|---|---|---|
| multimodal/ vs. retrieval-memory/ | ColPali stays in retrieval-memory/ as the retrieval-specific application. The multimodal/ files cover the foundation models and architectures. The multimodal-RAG synthesis bridges both. | Application vs. foundation split. |
| multimodal/ vs. architectures/ | Model architecture details (MoE, Transformer) stay in architectures/. Multimodal/ covers the modality-specific training paradigms, evaluation, and capabilities. | Architecture is the shared infrastructure; multimodal/ is the application of architecture to non-text modalities. |
| Embodied AI scope | RT-2, GATO, SayCan — the VLM-as-robot-policy paradigm. Not full robotics (motor control, SLAM, manipulation). | Scoped to where LLM/VLM capability meets embodiment. A future robotics domain could extend this. |
| CLIP depth | Full standalone treatment: architecture, training, zero-shot transfer, downstream impact, successors (SigLIP, ALIGN). | CLIP is the foundational paradigm — most VLMs build on contrastive pretraining insights. Deserves depth. |

## Overlap with ColPali

ColPali uses PaliGemma (which builds on SigLIP, a CLIP successor) + late interaction from ColBERT. The new CLIP file should note PaliGemma's SigLIP encoder as a downstream application. The VLM file should reference ColPali as a retrieval application of VLMs. No content duplication — ColPali stays as the retrieval-focused treatment.

## Target file list (6 files + synthesis)

### Phase 2: Vision-Language Models (3 files)

1. **clip-contrastive-vision-language-pretraining.md**
   Radford et al. CLIP (2021): contrastive image-text pretraining. Architecture: dual-tower (image encoder — ViT or ResNet; text encoder — Transformer); contrastive loss (InfoNCE) across a batch of (image, text) pairs. Zero-shot transfer: encode image + encode class descriptions → compare → classify without any task-specific training. Why it works: alignment in a shared embedding space produces robust representations that transfer across tasks. ALIGN (Jia et al.): noisy alt-text at scale. BASIC: scaling CLIP with larger encoders. SigLIP: sigmoid loss replacing softmax (no need for global batch normalization). Downstream: CLIP as the visual backbone for image search, classification, VLM foundations (LLaVA uses CLIP ViT), and generative models (DALL-E 2, Stable Diffusion use CLIP embeddings). Open questions: does contrastive pretraining represent a distinct paradigm from generative multimodal training (DALL-E 3, Gemini native multimodality), or is the distinction collapsing?

2. **generative-vision-models-dalle-stable-diffusion.md**
   Generative image models from text. DALL-E 1 (2021): VQ-VAE discrete codes + autoregressive Transformer. DALL-E 2 (2022): CLIP text embedding → diffusion decoder (unCLIP). DALL-E 3 (2023): T5 text encoder + improved noise scheduling. Stable Diffusion (Rombach et al.): latent diffusion — diffusion process operates in VAE latent space rather than pixel space; U-Net denoiser; classifier-free guidance for prompt adherence. Imagen (Google): cascaded pixel-space diffusion with T5-XXL text encoder; finding that language model scale matters more than visual model scale. The text-to-image paradigm shift and its implications: inpainting, outpainting, image editing (InstructPix2Pix), video generation (Sora). Copyright and aesthetic ownership debates.

3. **vision-language-models-gpt4v-gemini-llava.md**
   The VLM generation: models that accept both image and text inputs and produce text outputs. GPT-4V/GPT-4o: visual token processing, chart/document/image reasoning, measured benchmarks (MMMU, ScienceQA, MathVista). Google Gemini: "natively multimodal" — trained from the start on interleaved text/image/audio, not post-hoc fusion. Open-source VLMs: LLaVA (CLIP ViT + Vicuna/LLaMA, visual instruction tuning), InstructBLIP (Q-Former bridging frozen vision + language modules), Idefics. Architecture patterns: (a) frozen vision encoder + frozen LLM + trainable connector (LLaVA); (b) fully interleaved pretraining (Gemini); (c) cross-attention injection (Flamingo). The benchmark landscape: MMMU, MM-Bench, POPE (hallucination), ChartQA, DocVQA, ScienceQA.

### Phase 3: Audio and Embodied (2 files)

4. **audio-language-models-whisper-speech.md**
   OpenAI Whisper: encoder-decoder transformer for ASR; multilingual (99 languages); robustness via massively diverse pre-training (680K hours of labeled audio). AudioLM and AudioPaLM (Google): conditional audio generation with semantic + acoustic token hierarchies. MusicGen and AudioCraft (Meta): controllable music/audio generation from text and audio prompts. GPT-4o: native audio modality — real-time voice conversation, emotion detection, speech generation without separate TTS. ASR benchmarks: WER on LibriSpeech, CommonVoice, FLEURS. The speech-language convergence: voice interfaces as multimodal AI's most natural interaction modality.

5. **embodied-ai-rt2-gato-saycan.md**
   Vision-language-action models: using VLM weights as robot policies. RT-2 (Google DeepMind): fine-tuning PaLI-X and PaLM-E on robot trajectories, producing motor actions as text tokens. The insight: VLMs have world knowledge that transfers to physical manipulation ("move the object near the green thing" requires semantic understanding + spatial grounding). GATO (DeepMind): single generalist agent trained across text, images, Atari, robot control — shared tokenization across modalities. SayCan (Google): LLMs for affordance-grounded robot planning; combining language model task decomposition with learned affordance scoring ("I can do this task AND I should do it"). Open Embodiment ecosystem and RT-X dataset. Challenges: sim-to-real transfer gap, distribution shift in physical environments, data scarcity for robot demonstrations.

### Phase 4: Synthesis (1 file, requires approval)

6. **multimodal-synthesis-rag-extension.md**
   Capstone synthesis integrating the five files with the existing retrieval-memory domain. Key themes: (a) CLIP established the paradigm of learning a shared embedding space across modalities — the same insight powers ColPali, VLM training, and audio-language alignment; (b) generative vision models complete the loop from understanding to generation, enabling tool-use patterns for agent systems; (c) multimodal RAG extends text-RAG to visual/audio retrieval, with ColPali as the worked example; (d) embodied AI extends agent architecture to physical action, the last modality frontier; (e) the convergence toward a single model handling all modalities (GPT-4o, Gemini) vs. the modular approach (separate encoders + connector). Updated cross-references to frontier-synthesis.md and retrieval-memory SUMMARY.

## Cross-reference map

| New file | Cross-references to existing files |
|---|---|
| clip-contrastive-vision-language-pretraining | → retrieval-memory/colpali-visual-document-retrieval.md (SigLIP as CLIP successor), architectures/mixture-of-experts.md (scaling) |
| generative-vision-models-dalle-stable-diffusion | → clip (CLIP embeddings for DALL-E 2), history/language-models/attention-and-the-transformer-breakthrough.md (Transformer backbone) |
| vision-language-models-gpt4v-gemini-llava | → retrieval-memory/colpali-visual-document-retrieval.md (PaliGemma), multi-agent/agent-architecture-patterns.md (multimodal agents) |
| audio-language-models-whisper-speech | → clip (shared contrastive pretraining insight) |
| embodied-ai-rt2-gato-saycan | → reasoning/reasoning-models.md (planning), multi-agent/agent-architecture-patterns.md (agent embodiment) |
| multimodal-synthesis-rag-extension | → retrieval-memory/agentic-rag-patterns.md, retrieval-memory/colpali-visual-document-retrieval.md, frontier-synthesis.md |

## Duplicate coverage check

ColPali covers visual document retrieval specifically. No new file duplicates that treatment. The CLIP file contextualizes ColPali's SigLIP encoder; the VLM file references ColPali as a retrieval application. Complementary, not duplicative.

## Formatting conventions

Based on review of existing ai/frontier/ files:
- YAML frontmatter: `source`, `origin_session`, `created`, `trust`, `type`, `related`
- Markdown body: H1 title, H2 sections, H3 subsections, tables for benchmarks and comparisons
- Depth: 1000–1500 words per file; cite specific models, benchmarks, and papers
