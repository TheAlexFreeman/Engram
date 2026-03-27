---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: clip-contrastive-vision-language-pretraining.md, vision-language-models-gpt4v-gemini-llava.md, embodied-ai-rt2-gato-saycan.md
---

# Audio-Language Models: Whisper, Speech, and Audio Generation

Audio-language models bridge the divide between speech, music, and natural language — enabling transcription, translation, generation, and real-time conversation through architectures that treat audio as a sequence of learnable tokens. The field has seen rapid advancement from simple automatic speech recognition (ASR) systems to multimodal models where speech, text, and audio content exist within a unified representational space. This file surveys the major systems and architectural patterns as of early 2024.

---

## Automatic Speech Recognition: Whisper

### Architecture and Training

**OpenAI Whisper** (Radford et al., 2022) is a large-scale ASR system trained on 680,000 hours of multilingual and multitask supervised audio data scraped from the internet — an order of magnitude larger than prior ASR training sets.

**Architecture:** Encoder-decoder Transformer:
- **Encoder:** Takes mel spectrogram input (log-magnitude mel filterbank features, 80-channel, 25ms windows, 10ms stride); processes audio into contextual representations
- **Decoder:** Autoregressive language model conditioned on encoder outputs; generates text tokens using standard attention mechanism
- **Sequence length:** 30-second audio windows; longer audio split into overlapping chunks

**Model sizes:**

| Model | Parameters | Multilingual | WER (LibriSpeech test-clean) |
|-------|-----------|-------------|------------------------------|
| Tiny | 39M | ✓ | 5.7% |
| Base | 74M | ✓ | 4.2% |
| Small | 244M | ✓ | 3.0% |
| Medium | 769M | ✓ | 2.6% |
| Large-v3 | 1.5B | ✓ | 2.0% |

### Multitask Training

Whisper is trained jointly on multiple tasks specified via **task tokens** appended to the input:

- `<|transcribe|>` — speech to text in source language
- `<|translate|>` — speech to English translation
- `<|en|>`, `<|fr|>`, `<|zh|>`, ... — language identification tokens (99 languages)
- `<|notimestamps|>` vs timestamp mode — with/without word-level timestamps

The unified multitask format means a single model handles all speech tasks — transcription, translation, language detection, and timestamped output — without task-specific fine-tuning.

### Whisper's Performance and Limitations

**Strengths:**
- Near-human performance on clean speech (test-clean LibriSpeech: 2.0% WER vs ~1.7% for top human performers)
- Strong robustness to acoustic variation: noise, accents, recording conditions
- Broad multilingual coverage (99 languages, though performance degrades on low-resource languages)

**Weaknesses:**
- Often "hallucinates" when audio is unintelligible: generates plausible-sounding but fabricated text
- Struggles with proper nouns, technical vocabulary, code-switching
- 30-second window creates challenges for very long-form transcription (drift in overlap regions)
- Latency: not designed for real-time streaming (addressed in newer variants)

---

## Audio Language Modeling: AudioLM

**AudioLM** (Borsos et al., Google, 2022) reframes audio generation as a **language modeling problem in the audio domain** — autoregressively predicting discrete audio tokens rather than raw waveforms or spectrograms.

### Hierarchical Tokenisation

AudioLM uses a **two-stage tokenisation scheme** to separate semantic content from acoustic details:

1. **Semantic tokens:** Extracted from **w2v-BERT** (self-supervised speech model) — capture linguistic/semantic content; coarse temporal resolution
2. **Acoustic tokens:** Extracted from **SoundStream** (neural audio codec) — capture fine-grained acoustic details including speaker identity, prosody, background; hierarchical residual vector quantisation (RVQ) with multiple codebooks (coarse → fine)

**Generation hierarchy:**
1. Language model (Transformer) generates **semantic tokens** — high-level content
2. Coarse acoustic model conditions on semantic tokens to generate **coarse acoustic tokens**
3. Fine acoustic model generates **fine acoustic tokens** conditioned on coarse

$$P(audio) = P(semantic) \cdot P(coarse \mid semantic) \cdot P(fine \mid coarse, semantic)$$

**Key properties:**
- Generated speech is acoustically consistent (same speaker, background, room) even across long continuations
- Can continue arbitrary speech prompts in a convincing way — the "prompt-and-continue" paradigm
- Extends naturally to piano music (AudioLM for music) showing the architecture is not speech-specific

---

## AudioPaLM: Unified Audio-Text Model

**AudioPaLM** (Google, 2023) extends PaLM-2 (a large text LLM) to process and generate both text and audio tokens within a single sequence:

- **Unified vocabulary:** Audio tokens (from USM — Universal Speech Model) and text tokens share a vocabulary; the model interleaves them
- **Architecture:** PaLM-2 backbone with modified embedding layers to handle audio tokens
- Tasks: ASR, speech-to-speech translation, text-to-speech, voice preservation in translation

**Speech-to-speech translation with voice preservation:** When translating speech, AudioPaLM can preserve the speaker's voice characteristics (prosody, timbre) — translating both content and acoustic identity rather than producing generic synthesised speech.

---

## MusicGen and AudioCraft (Meta, 2023)

**AudioCraft** is Meta's unified audio generation framework encompassing:
- **MusicGen:** Text-conditioned music generation
- **AudioGen:** General sound effects / ambient audio
- **EnCodec:** The underlying neural audio codec for tokenisation

### MusicGen Architecture

- **Backbone:** Decoder-only Transformer (similar to GPT)
- **Conditioning:** Text description encoded by T5; melody conditioning (optional) encodes a reference melody and forces harmonic consistency
- **Token prediction:** Uses a "delay pattern" for parallel RVQ codebook decoding — generates multiple codebook levels simultaneously rather than sequentially, reducing inference time

**Melody conditioning mechanism:** A CHROMA feature extractor converts the reference audio to pitch-class vectors; these are injected via cross-attention, giving the model harmonic constraint without forcing verbatim audio copying.

**Training data:** 20,000 hours of licensed music + 390,000 instrument tracks — explicitly licensed to avoid copyright infringement (unlike some competitor systems trained on web-scraped music).

---

## GPT-4o Native Audio

**GPT-4o** (OpenAI, May 2024) is the first OpenAI model with **native audio modality** — processing and generating raw audio rather than routing through a separate ASR/TTS pipeline:

| Approach | GPT-4 + Whisper + TTS | GPT-4o native audio |
|----------|----------------------|---------------------|
| Latency | ~2-3 seconds | ~320ms average |
| Tone/prosody | Fixed (TTS synthesised) | Expressive, responsive to context |
| Interruption | No | Yes |
| Emotional cues | Stripped (only text passed) | Preserved |
| Laughter, breath | Lost | Handled |

**Architectural shift:** By processing audio end-to-end, GPT-4o preserves paralinguistic signals (tone, emotion, pacing) that are destroyed when audio is converted to text. The model can:
- Detect and respond to emotions in voice
- Adjust its spoken tone in response to conversational context
- Handle interruptions natively

**Significance:** End-to-end audio-language models collapse the modular ASR → LLM → TTS pipeline into a single model, reducing latency and preserving full signal richness — a genuine architectural milestone.

---

## Emergent Capabilities and Limitations

### What Audio-Language Models Do Well

- **ASR at human-level:** Whisper achieves near-human word error rates on clean speech
- **Continuation coherence:** AudioLM maintains speaker identity, acoustic consistency over long windows
- **Cross-modal grounding:** AudioPaLM can translate while preserving voice — showing joint audio-text representations work
- **Controlled generation:** MusicGen's melody conditioning demonstrates controllable generative audio with soft harmonic constraints

### Persistent Challenges

1. **Hallucination in ASR:** Whisper hallucinates plausible text for inaudible audio — a systematic, dangerous failure mode in transcription applications
2. **Factual grounding:** Audio language models have no mechanism to verify claims made in or about audio content
3. **Long-form coherence:** Maintaining semantic and discourse coherence across multi-minute audio remains challenging (sentence-level coherence fine; paragraph-level degraded)
4. **Voice cloning misuse:** High-quality voice synthesis systems (including AudioPaLM, AudioCraft TTS) enable voice fraud — an active area of safety concern
5. **Copyright and training data:** Music generation models trained on unlicensed data (several competitors) face legal exposure; Meta's explicit licensing of MusicGen data is a partial mitigation

---

## References

1. Radford, A. et al. (2022). "Robust Speech Recognition via Large-Scale Weak Supervision." OpenAI Technical Report; ICML 2023
2. Borsos, Z. et al. (2022). "AudioLM: A Language Modeling Approach to Audio Generation." *IEEE/ACM Transactions on Audio, Speech, and Language Processing*, 31
3. Rubenstein, P.K. et al. (2023). "AudioPaLM: A Large Language Model That Can Speak and Listen." Google Research arXiv:2306.12925
4. Copet, J. et al. (2023). "Simple and Controllable Music Generation." *NeurIPS 2023* (MusicGen / AudioCraft)
5. OpenAI (2024). "Hello GPT-4o." openai.com/index/hello-gpt-4o
6. Yang, D. et al. (2023). "UniAudio: An Audio Foundation Model Toward Universal Audio Generation." arXiv:2310.00704
