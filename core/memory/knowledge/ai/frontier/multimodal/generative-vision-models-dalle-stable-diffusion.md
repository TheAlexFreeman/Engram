---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: clip-contrastive-vision-language-pretraining.md, vision-language-models-gpt4v-gemini-llava.md, ../architectures/mixture-of-experts.md
---

# Generative Vision Models: DALL-E, Stable Diffusion, Imagen

Generative vision models take text descriptions as input and produce photorealistic or stylistically diverse images as output. The three major paradigms are: **discrete token-based generation** (DALL-E 1), **diffusion models** (DALL-E 2, Stable Diffusion, Imagen), and **latent diffusion** combining compressed representation with diffusion in a learned compact space. By 2025-2026, diffusion-based text-to-image generation is the dominant paradigm for both research and commercial deployment.

---

## DALL-E 1: Discrete Visual Tokens + Autoregressive Transformer

### Architecture

DALL-E 1 (OpenAI, 2021) combined two components:

**Stage 1: dVAE (discrete Variational Autoencoder)**
- Encodes images into a grid of discrete visual tokens (32×32 = 1024 tokens from a vocabulary of 8192 visual "words")
- Decoder reconstructs images from this discrete code
- Enables treating image generation as a sequence modeling problem over visual tokens

**Stage 2: Transformer language model**
- Input: 256 BPE text tokens + 1024 image tokens (concatenated)
- Output: next-token prediction over the joint vocabulary
- At generation: sample text tokens autoregressively, then sample image tokens conditioned on the text

**Inference**:
1. Encode text prompt → 256 BPE tokens
2. Autoregressively sample 1024 image tokens
3. Decode image tokens via dVAE decoder to pixel space
4. CLIP reranking: generate $k$ candidates, rank by CLIP text-image similarity, return top-k

### Limitations of DALL-E 1
- Discrete tokenization loses image detail (low-frequency artifacts)
- Autoregressive generation is slow (sequential token sampling)
- No explicit guidance mechanism for conditioning strength

---

## DALL-E 2: CLIP Embeddings + Diffusion Decoder

### Architecture

DALL-E 2 (OpenAI, 2022; Ramesh et al.) uses a two-stage cascade:

**Stage 1: Prior**
- Maps text → CLIP image embedding
- Text → CLIP text embedding (via CLIP text encoder)
- A **diffusion prior** or autoregressive prior maps the text embedding to the corresponding image embedding in CLIP space
- This is the "prior" step: generate the semantic content of the intended image

**Stage 2: Decoder (unCLIP)**
- Maps CLIP image embedding → pixel-space image via a **diffusion model**
- Conditions on both the CLIP image embedding (semantic content) and a CLIP text embedding (style/detail)
- Uses classifier-free guidance (see below)

### The Inpainting/Variations Capability

DALL-E 2's architecture naturally supports:
- **Inpainting**: replace a masked image region by conditioning the decoder on an unmasked region + text
- **Image variations**: encode a real image via CLIP, then generate variations by sampling different decodings of the same CLIP embedding
- **Interpolation**: linearly interpolate between two CLIP embeddings, then decode — produces semantic morphs between pairs of images

### Classifier-Free Guidance (CFG)

**CFG** (Ho & Salimans 2021) is the key technique enabling high-quality conditional generation across all modern diffusion models:

During training: randomly drop the conditioning signal (text/CLIP embedding) with probability $p$ — training both a conditional model $p(x|c)$ and unconditional model $p(x)$ simultaneously.

During inference: interpolate between conditional and unconditional score estimates:

$$\hat{s}_\theta(x_t, c) = s_\theta(x_t, \emptyset) + w \cdot (s_\theta(x_t, c) - s_\theta(x_t, \emptyset))$$

where:
- $s_\theta(x_t, c)$: score (gradient of log-likelihood) with conditioning
- $s_\theta(x_t, \emptyset)$: unconditional score
- $w > 1$: guidance scale (typically 7-15)

**Higher $w$** = images more closely matched to prompt, but less diverse and sometimes over-saturated. **Lower $w$** = more diverse, potentially off-prompt.

---

## Stable Diffusion: Latent Diffusion at Scale

### The Latent Diffusion Idea (Rombach et al. 2022)

Full pixel-space diffusion is computationally expensive: a 512×512 image has 786,432 pixels. **Latent diffusion** separates:

1. **Perception compression** (VAE): Train an autoencoder to compress images into a much smaller latent space. Typical compression ratio: 8× spatial (512px → 64px latent).
2. **Diffusion in latent space**: Train the diffusion model in the compressed latent space (64×64×4 = 16,384 dimensions vs 786,432 for pixels). Far cheaper to train and sample.

### Stable Diffusion Architecture

**VAE (Variational Autoencoder)**:
- Encoder $\mathcal{E}$: image $x \in \mathbb{R}^{H \times W \times 3}$ → latent $z \in \mathbb{R}^{h \times w \times c}$ (with $h = H/8$, $w = W/8$, $c = 4$)
- Decoder $\mathcal{D}$: latent $z$ → reconstructed image $\tilde{x}$
- KL regularization keeps the latent space Gaussian

**U-Net denoiser** (the core model):
- Takes noisy latent $z_t$ and timestep $t$ as input
- Conditions on text via **cross-attention** with CLIP/BLIP text encoder
- Predicts the noise $\epsilon$ added at step $t$ (or equivalently, predicts the clean latent $z_0$)
- Architecture: hierarchical encoder-decoder with skip connections; attention layers at each resolution

**Inference (DDIM sampling)**:
1. Sample random latent noise $z_T \sim \mathcal{N}(0, I)$
2. Iteratively denoise from $z_T$ to $z_0$ via $T$ (typically 20-50) steps, conditioned on text
3. Decode $z_0$ via VAE decoder to pixel space

### Text Conditioning

SD v1.x used **CLIP ViT-L/14** text encoder (frozen); SD v2.x switched to **OpenCLIP** (a larger open-source reimplementation). SDXL uses an **ensemble of text encoders** (OpenCLIP-ViT-G + OpenCLIP-ViT-L in parallel) for richer text representations.

### Stable Diffusion XL (SDXL, 2023)

SDXL increased model scale and introduced:
- Dual text encoder ensemble
- Additional conditioning: image size and crop coordinates passed to U-Net
- Two-stage pipeline: base model (1024×1024) → refiner model (upsamples latent to 4×)
- Result: substantially improved text-image alignment and photorealism

### The Open-Source Ecosystem

Stable Diffusion's open release (weights + model card) enabled a rich ecosystem:
- **ControlNet**: conditioning on spatial constraints (edge maps, depth maps, pose skeletons) → precise spatial control
- **DreamBooth / Textual Inversion**: fine-tuning on 3-30 images of a specific subject → personalized generation
- **LoRA (Low-Rank Adaptation)**: efficient fine-tuning of the U-Net with small adapter matrices
- **AUTOMATIC1111 / ComfyUI**: widely-used inference UIs with extension ecosystems

---

## Imagen: T5 Text Encoder + Cascaded Diffusion

### Approach (Google Brain, 2022)

Imagen (Saharia et al.) departed from CLIP-based conditioning:
- **T5-XXL text encoder** (4.6B parameters, trained on text-only data) instead of CLIP — the hypothesis that language understanding benefits from larger text-only pretraining
- **Cascaded diffusion**: three separate diffusion models at increasing resolution (64×64 → 256×256 → 1024×1024)
- **Efficient U-Net**: improved U-Net architecture with attention at all scales

### Dynamic Thresholding

Imagen introduced **dynamic thresholding** to address CFG saturation:
- At high guidance scales ($w \gg 1$), pixels saturate at maximum or minimum values
- Dynamic thresholding: at each step, clamp the predicted $x_0$ to the percentile of the distribution rather than hard clipping
- Allows much higher guidance scales without saturation

### Text-Image Alignment Quality (DrawBench)

Imagen outperformed DALL-E 2 and Stable Diffusion on the **DrawBench** benchmark (a curated suite of 200 prompts testing compositional, spatial, counting, and stylistic understanding) in human preference evaluations.

---

## The Text-to-Image Landscape (2024-2026)

| Model | Organization | Key Innovation | Strength |
|-------|-------------|---------------|----------|
| DALL-E 3 | OpenAI | Improved T5 + InstructPix2Pix training; captions refined by GPT-4 | text alignment |
| Stability AI SD3 | Stability AI | Diffusion transformer (DiT) replacing U-Net; flow matching | coherent multi-object |
| Midjourney v6 | Midjourney | Proprietary; aesthetic quality | photorealism, style |
| Imagen 2 | Google | Cascaded diffusion + large T5 | text rendering |
| Flux | Black Forest Labs (Stability spinoff) | Rectified flow + transformer | open source quality |

**Diffusion Transformers (DiT)**: replacing the U-Net backbone with a **Transformer** operating on image patches proved superior at scale — the ViT architecture's scalability benefits apply to diffusion backbones.

**Flow Matching**: an alternative to DDPM noise schedules that defines straighter probability paths between noise and data distributions. More efficient inference (fewer steps for similar quality).

---

## Aesthetic, Copyright, and Ethical Dimensions

1. **Training data provenance**: Models trained on LAION-5B include copyrighted images; significant ongoing litigation regarding whether training constitutes infringement.
2. **Style replication**: These models can generate images "in the style of" living artists, raising intellectual property and economic concerns for illustrators.
3. **Photorealistic fake generation**: The same capability used for creative generation enables non-consensual intimate imagery (NCII) generation and disinformation — a major policy concern.
4. **Safety filtering**: Production APIs apply content classifiers to reject NSFW and harmful outputs; open-source models strip these filters.
5. **Watermarking**: C2PA (Content Provenance and Authenticity) standards emerging for machine-generated image disclosure.

---

## Key Papers

- Ramesh, A., Pavlov, M., Goh, G., et al. (2021). Zero-shot text-to-image generation. *ICML 2021*. (DALL-E 1)
- Ramesh, A., Dhariwal, P., Nichol, A., et al. (2022). Hierarchical text-conditional image generation with CLIP latents. arxiv:2204.06125. (DALL-E 2)
- Rombach, R., Blattmann, A., Lorenz, D., et al. (2022). High-resolution image synthesis with latent diffusion models. *CVPR 2022*. (Stable Diffusion)
- Saharia, C., Chan, W., Saxena, S., et al. (2022). Photorealistic text-to-image diffusion models with deep language understanding. *NeurIPS 2022*. (Imagen)
- Ho, J., & Salimans, T. (2022). Classifier-free diffusion guidance. arxiv:2207.12598.
