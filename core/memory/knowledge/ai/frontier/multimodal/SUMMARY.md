---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-005
source: agent-generated
trust: medium
related: clip-contrastive-vision-language-pretraining.md, generative-vision-models-dalle-stable-diffusion.md, vision-language-models-gpt4v-gemini-llava.md, audio-language-models-whisper-speech.md, embodied-ai-rt2-gato-saycan.md, multimodal-rag-retrieval-patterns.md, multimodal-synthesis-agent-implications.md
---

# Multimodal AI — Subdomain Summary

This subdomain (`ai/frontier/multimodal/`) covers the development and theory of AI systems that process and generate across multiple modalities (text, image, audio, video, action), from contrastive foundation models to embodied agents and multimodal retrieval.

**Prerequisites**: General familiarity with transformer architecture and language model pretraining (`../architectures/`); RAG fundamentals (`../retrieval-memory/rag-architecture.md`).

---

## Files in This Subdomain

| File | One-Line Description |
|------|----------------------|
| `clip-contrastive-vision-language-pretraining.md` | CLIP's contrastive pretraining on 400M image-text pairs; zero-shot transfer; alignment as a transferable capability |
| `generative-vision-models-dalle-stable-diffusion.md` | DALL-E and Stable Diffusion: latent diffusion architecture, text-to-image generation, and the denoising formalism |
| `vision-language-models-gpt4v-gemini-llava.md` | VLMs: GPT-4V, Gemini, LLaVA; connecting vision encoders to language models; emergent visual reasoning capabilities |
| `audio-language-models-whisper-speech.md` | Whisper encoder-decoder ASR, AudioLM hierarchical tokenisation, MusicGen, and GPT-4o native audio |
| `embodied-ai-rt2-gato-saycan.md` | SayCan affordance scoring, GATO unified tokenisation, RT-2 vision-language-action models, and emergent robot generalization |
| `multimodal-rag-retrieval-patterns.md` | Retrieval over heterogeneous corpora: late-interaction multimodal retrieval, cross-modal query expansion, hybrid pipelines, ViDoRe |
| `multimodal-synthesis-agent-implications.md` | Full synthesis: pipeline vs native architectures; cross-modal alignment; implications for multimodal memory and agent perception-action loops |

---

## Recommended Reading Order

**Understanding multimodal foundations**:
1. `clip-contrastive-vision-language-pretraining.md` — the alignment paradigm
2. `generative-vision-models-dalle-stable-diffusion.md` — generative side
3. `vision-language-models-gpt4v-gemini-llava.md` — joint reasoning

**Understanding multimodal at the frontier**:
4. `audio-language-models-whisper-speech.md` — beyond vision
5. `embodied-ai-rt2-gato-saycan.md` — action as a modality
6. `multimodal-rag-retrieval-patterns.md` — retrieval in multimodal settings
7. `multimodal-synthesis-agent-implications.md` — full synthesis

---

## Cross-References

**Upstream** (prerequisites):
- `../retrieval-memory/rag-architecture.md` — text RAG foundation for multimodal RAG
- `../retrieval-memory/colpali-visual-document-retrieval.md` — ColPali visual retrieval (prerequisite for `multimodal-rag-retrieval-patterns.md`)
- `../architectures/scaling-laws-chinchilla.md` — scaling laws apply across modalities

**Downstream** (files that build on this subdomain):
- `../governance/model-cards-datasheets-transparency-artefacts.md` — multimodal models have additional transparency requirements
- `../../cognitive-science/emotion/affective-computing-emotion-ai-systems.md` — affective computing uses multimodal signals
