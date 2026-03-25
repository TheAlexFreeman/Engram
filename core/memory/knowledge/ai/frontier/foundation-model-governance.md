---
created: 2026-03-20
domain: ai/frontier
last_verified: '2026-03-21'
origin_session: core/memory/activity/2026/03/20/chat-001
related:
  - memory/knowledge/literature/cs-lewis-abolition-of-man.md
  - memory/knowledge/ai/frontier/alignment/frontier-alignment-research.md
  - memory/knowledge/literature/sons-of-man-covenant.md
  - memory/knowledge/ai/frontier-synthesis.md
  - memory/knowledge/self/engram-governance-model.md
source: external-research
tags:
- governance
- regulation
- eu-ai-act
- safety-frameworks
- compute-thresholds
- frontier-ai
- model-cards
trust: medium
type: knowledge
---

# Foundation Model Governance: Regulation, Safety Frameworks, and Open Debates

The governance of frontier AI systems has shifted from voluntary norms to
binding law between 2024 and 2026, with the EU AI Act as the first comprehensive
statutory framework and a growing set of national and international instruments
filling in around it. The central tension running through all of it is the same
one Lewis identified in *The Abolition of Man*: who are the Conditioners, and by
what authority do they decide?

---

## The regulatory landscape as of early 2026

### EU AI Act — the statutory anchor

The EU AI Act reached full enforceability in August 2026 (staggered rollout from
February 2025). It is the world's first comprehensive binding AI law and will
govern any organization operating in the EU regardless of headquarters location.

**Risk classification:** The Act uses a four-tier risk hierarchy.
- *Unacceptable risk* (prohibited): biometric mass surveillance, social scoring,
  subliminal manipulation, certain predictive policing uses. Enforceable from
  February 2025.
- *High risk*: AI in critical infrastructure, hiring, credit, law enforcement,
  education, healthcare. Requires conformity assessments, transparency, human
  oversight, and registration.
- *Limited risk*: Chatbots and emotion recognition require disclosure.
- *Minimal risk*: Spam filters, recommender systems — no requirements.

**GPAI (General-Purpose AI) model provisions:** Foundation models capable of a
broad range of tasks face specific obligations. The thresholds:
- **10²³ FLOPs** (training compute): classification as a GPAI model triggers
  documentation, capability evaluations, copyright compliance requirements,
  and systemic risk assessment.
- **10²⁵ FLOPs**: *systemic risk* classification. Providers must notify the
  European AI Office within two weeks of reaching or foreseeing this threshold.
  Additional obligations: adversarial testing, incident reporting, cybersecurity
  measures, energy consumption reporting.

The compute threshold approach is imprecise but tractable — compute is the one
dimension of AI capability development that can be measured externally. Its
limitation is that efficient training (better algorithms, better data) can achieve
high capabilities below the threshold, while some high-compute models may pose
little systemic risk.

**Penalties:** Up to €35 million or 7% of global annual turnover, whichever is
higher, for violations of prohibited practices. €15M / 3% for other violations.

### US regulatory approach — voluntary with increasing structure

The US has not passed comprehensive AI legislation. The current federal framework
is:

- **NIST AI Risk Management Framework (AI RMF 1.0):** Voluntary. Organized around
  Govern, Map, Measure, Manage functions. Provides process guidance rather than
  technical requirements. The de facto standard for federal procurement.
- **OMB M-26-04 (March 2026):** Requires federal agencies purchasing LLMs to
  obtain model cards, evaluation artifacts, and acceptable use policies. The first
  federal purchasing mandate with teeth.
- **White House Executive Order (December 2025):** Strengthened coordination of
  federal AI governance across agencies. Represents a shift toward structured
  federal engagement without statutory authority.
- **State-level:** California, Texas, and several other states have enacted or are
  debating AI disclosure and accountability laws. California's AI safety bills
  have been the most contested, with SB 1047 vetoed in 2024 but successor
  legislation advancing.

The US approach remains lighter-touch than the EU — industry-led standards with
government coordination rather than prescriptive mandates. The tension between
the EU's precautionary approach and the US's innovation-first posture is the
dominant geopolitical frame for AI governance debates.

### International coordination infrastructure

- **OECD AI Principles:** Adopted by 46 countries, providing the normative
  foundation most national frameworks draw from.
- **G7 Hiroshima AI Process:** Voluntary commitments from major economies.
  Produced the International Code of Conduct for Advanced AI Systems in 2023.
- **International AI Safety Report (2026):** Published by an independent
  international panel, providing the scientific consensus assessment of AI risks
  analogous to IPCC reports for climate. Designed to inform but not bind
  regulators.
- **Singapore IMDA (January 2026):** Released the world's first Model AI
  Governance Framework specifically addressing *agentic* AI — covering
  autonomous decision-making, tool use, and multi-step task execution.

---

## Frontier AI Safety Frameworks

Distinct from external regulation, major frontier labs have published voluntary
internal *Frontier AI Safety Frameworks* (FASFs) describing how they will manage
risks as capabilities scale. By 2025, 12 companies had published or updated such
frameworks.

**Common elements:**
- **Capability thresholds:** Define specific capability levels at which additional
  safety measures activate (e.g., "if a model can provide meaningful uplift in
  CBRN weapons synthesis, we will not deploy it").
- **Evaluations:** Standardized capability evaluations (often including red-teaming,
  uplift evaluations, and autonomous replication tests) run before deployment.
- **Responsible Scaling Policies (RSPs):** Anthropic's version, first published
  2023, updated 2024. Links deployment permission to evaluation results.

**The critique:** FASFs are voluntary, self-assessed, and self-published. The
Future of Life Institute's AI Safety Index (Winter 2025) evaluated major labs
and found that most threshold definitions are not operationally specific enough
to be enforced or independently verified. Key findings:
- Thresholds often described in terms of capability categories rather than
  measurable tests.
- Proposed mitigations rarely demonstrated to be implementable in advance.
- Limited third-party verification.

The governance problem this creates parallels Lewis's Conditioner analysis: the
labs are both the entities being governed and the entities defining the
governance standards. The absence of an external authority to arbitrate threshold
disputes means the frameworks provide accountability pressure but not accountability.

---

## Model cards and evaluation artifacts

**Model cards** (Mitchell et al. 2019) are structured documentation accompanying
ML models covering: intended use, out-of-scope uses, factors affecting performance,
metrics, ethical considerations, and caveats. They became an industry norm after
Google's publication of the original framework.

By 2026:
- Model cards are standard practice for academic releases.
- Major labs publish varying degrees of model card information for commercial
  models, with commercial sensitivity limiting disclosure on training data and
  methodology.
- Federal procurement (OMB M-26-04) now requires model cards for government
  purchases.

**The Foundation Model Transparency Index** (Bommasani et al., Stanford HAI,
2024-2025 editions): Annual ranking of major foundation model providers on
~100 transparency dimensions covering upstream (data, compute, labor), model
(architecture, capabilities, evaluations), and downstream (deployment, usage
policies, impact). Consistent finding: transparency is highest on model
capabilities and lowest on training data. No provider scores well on all dimensions.

---

## Compute governance as a technical policy lever

**The compute governance thesis:** Training compute is the most tractable proxy
for AI capability risk. Unlike model architecture or training data, compute is
physically instantiated and can be monitored at the hardware supply chain level.

**Policy instruments being explored:**
- *Know-your-customer (KYC) requirements* for GPU cloud providers, particularly
  for large training runs.
- *Compute thresholds* triggering reporting (EU AI Act approach).
- *Export controls* on high-end AI chips — the US-China chip controls (2022, 2023,
  2025 tightening) are the first large-scale implementation.
- *International compute monitoring* — proposals for a compute registry analogous
  to nuclear material accounting.

**The limitation:** The compute threshold for frontier capability is not fixed.
Algorithmic efficiency gains (Chinchilla scaling laws, then DeepSeek's efficiency
improvements) have repeatedly demonstrated that the compute/capability relationship
shifts. A fixed FLOP threshold becomes less meaningful over time. Moreover,
distributed training across many smaller runs can potentially circumvent compute
thresholds without reducing overall capability.

---

## Open debates and unsettled questions

**What does "general-purpose" mean for regulatory purposes?** The EU GPAI
provisions apply to models with a "broad range of possible uses" — a functional
definition rather than an architectural one. But fine-tuned models derived from
GPAI base models create definitional problems: is a customer service chatbot
fine-tuned from GPT-4 a GPAI model?

**How to govern agentic AI specifically?** Current frameworks were designed for
static model deployments. Agentic systems — where models take extended sequences
of real-world actions, use tools, and operate autonomously — create new
risk categories (irreversible actions, multi-step manipulation, autonomous
replication) that the current regulatory vocabulary doesn't fit well.
Singapore's January 2026 framework is the first serious attempt to address this.

**Liability allocation in multi-model pipelines:** When an agentic system
consisting of an orchestrator model, several subagent models, and multiple
third-party tool providers causes harm, who is liable? Current frameworks
have no clear answer.

**Race dynamics and the unilateral disarmament problem:** Safety investments
have costs. Labs operating under stricter self-governance may lose ground to
competitors operating under looser standards. The most dangerous scenario is
one in which safety-conscious developers slow their deployments while less
cautious actors deploy unrestricted systems. International coordination
mechanisms have not solved this.

**The Conditioner problem:** The most fundamental governance question —
who decides what values AI systems should embed — is not resolved by any
current framework. RLHF embeds the preferences of a specific pool of human
raters; constitutional AI embeds the value judgments of the researchers who
wrote the constitution; RLAIF embeds the outputs of an AI system that itself
was trained on human feedback. All of these are forms of Conditioner authority,
and the frameworks governing them are more developed on process (who reviews,
who approves) than on substance (what values are right). Lewis's point is that
this distinction cannot be dissolved by better process.

---

## Key sources

- [AI Governance Regulatory Landscape 2026 — Prof. Hung-Yi Chen](https://www.hungyichen.com/en/insights/ai-governance-regulatory-landscape-2026)
- [Overview of GPAI Guidelines — EU AI Act](https://artificialintelligenceact.eu/gpai-guidelines-overview/)
- [AI Safety Index Winter 2025 — Future of Life Institute](https://futureoflife.org/ai-safety-index-winter-2025/)
- [Foundation Model Transparency Index 2025 — arXiv](https://arxiv.org/html/2512.10169v1)
- [International AI Safety Report 2026](https://internationalaisafetyreport.org/publication/international-ai-safety-report-2026)
- [How AI Regulation Changed in 2025 — Promptfoo](https://www.promptfoo.dev/blog/ai-regulation-2025/)
- [Credo AI: Latest AI Regulations 2026](https://www.credo.ai/blog/latest-ai-regulations-update-what-enterprises-need-to-know)
