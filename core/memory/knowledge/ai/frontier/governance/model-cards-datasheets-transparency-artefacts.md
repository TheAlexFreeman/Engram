---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: eu-ai-act-risk-tiers-compliance.md, responsible-scaling-policies-anthropic-openai.md, red-teaming-standards-and-eval-frameworks.md
---

# Model Cards, Datasheets, and AI Transparency Artefacts

**Documentation artefacts** — model cards, datasheets for datasets, and system cards — emerged from the period 2018–2022 as practical instruments for communicating AI system properties to downstream users, auditors, and affected communities. They sit at the intersection of technical practice and governance: voluntary when introduced, increasingly mandated by frameworks such as the EU AI Act. This file examines the core artefacts, their design rationale, and the persistent tension between formal compliance and substantive transparency.

---

## Model Cards

### Mitchell et al. (2019): Original Proposal

**Margaret Mitchell**, **Timnit Gebru**, and colleagues at Google introduced model cards in a 2019 paper as short documents accompanying trained ML models. A model card answers:

1. **Model details:** Architecture, training date, version, contact
2. **Intended use:** Primary use cases, users, out-of-scope uses
3. **Factors:** Relevant demographic, environmental, or technical factors affecting performance
4. **Metrics:** Performance measures used, disaggregation by subgroup
5. **Evaluation data:** Benchmarks used for evaluation
6. **Training data:** Description (may be limited if proprietary)
7. **Quantitative analyses:** Disaggregated performance results
8. **Ethical considerations:** Dataset biases, potential harm scenarios, mitigation strategies
9. **Caveats and recommendations:** Usage limitations, recommendations for downstream users

**The key innovation:** **Disaggregated evaluation** — reporting performance across subgroups (race, gender, geographic region) rather than aggregate accuracy. Aggregate accuracy hides performance gaps that are central to fairness evaluation.

### Disaggregation in Practice

In computer vision face recognition, disaggregated reporting reveals patterns like:

| Group | System A Accuracy | System B Accuracy |
|-------|-------------------|-------------------|
| Lighter-skin male | 98.8% | 99.0% |
| Lighter-skin female | 97.3% | 98.5% |
| Darker-skin male | 93.1% | 94.2% |
| Darker-skin female | 79.6% | 86.7% |

Aggregate accuracy (~97%) obscures the 18-percentage-point gap on darker-skin females — the *real* safety-relevant performance information.

### Adoption and Evolution

- **Industry adoption:** Google, Hugging Face (model hub card format), Microsoft Azure, IBM FactSheets
- **Hugging Face format:** YAML frontmatter + markdown body; now standard for open-source models on Hub
- **Evolution:** Model cards have grown longer, more standardised, and more template-driven — increasing consistency but risking checkbox compliance

---

## Datasheets for Datasets

### Gebru et al. (2018/2021): The Original Proposal

**Timnit Gebru** and colleagues proposed datasheets for datasets by analogy to electronics component datasheets — every electronic component has a standardised datasheet; every dataset should too.

A datasheet answers:

**Motivation:** Why was the dataset created? Who funded it?

**Composition:**
- What do instances represent (text, audio, images, people)?
- How many instances? What is the label distribution?
- Does it contain personal information? Does it contain sensitive data?

**Collection process:**
- How was data collected? What mechanisms (scraping, survey, annotation)?
- Who collected it? Over what timeframe?
- Were subjects aware of collection?

**Preprocessing / cleaning / labelling:**
- What preprocessing was done? What was excluded?
- How were labels generated? IRR (inter-rater reliability)?

**Uses:**
- What tasks was it used for? What has it been used for?
- Inappropriate uses?

**Distribution:**
- How is it distributed? Under what license?

**Maintenance:**
- Who maintains it? Will it be updated?

### Why Datasheets Matter

Many documented harms from AI systems trace back to **training data properties not disclosed**:
- **Crawl-derived web data:** Contains biases, toxicity, copyright material, PII — poorly documented
- **Face datasets:** Many assembled from unconsenting public figures' photos (LFW, MS-Celeb-1M, etc.) — no consent documented
- **Label imbalance:** Datasets with class imbalance create systematic prediction errors that aggregate metrics don't reveal

---

## System Cards

**System cards** extend model cards to describe a **complete deployed AI system**, including:
- All model components (base model + fine-tuning + safety filters)
- Integration architecture (API, guardrails, retrieval)
- Testing performed (red-teaming, scenario testing)
- Known limitations of the full system
- Deployment context and constraints

**OpenAI GPT-4 System Card (2023):** Described safety training procedures, red-teaming methodology, "hazardous chemicals" evaluation, uplift testing for weapons, and known failure modes — published alongside the GPT-4 Technical Report.

**Anthropic Claude model cards:** Include RLHF details, Constitutional AI procedure, safety evaluations structured by harm category, and limitations.

System cards represent a move toward **holistic transparency** — the system as deployed, not just the model weights in isolation.

---

## EU AI Act: Mandatory Technical Documentation

The EU AI Act operationalises documentation requirements (Annex IV) for **high-risk AI systems**:

### Annex IV Requirements for High-Risk Systems

1. **General description:** purpose of the system, version history, hardware/software specs
2. **Design specification and development process:** training methodology, training data description (characteristics, selection criteria, labelling procedures), validation and testing
3. **Information on technical performance:** general performance metrics, performance across demographic groups (required disaggregation)
4. **Design decisions with safety/ethics implications:** choices that affect safety, fairness, or non-discrimination
5. **Instructions for use:** intended deployment conditions, intended user base, contraindications
6. **Notified body involvement:** conformity assessment documentation

### GPAI Model Documentation (Article 53)

For general-purpose AI models (training compute ≥ 10²³ FLOP), providers must maintain technical documentation covering:
- Training data: domain, sources, filtering procedures
- Training procedures and compute used
- Evaluation of capabilities including hazardous/misuse capabilities
- Copyright compliance procedures

This mandatory documentation is structurally similar to model cards and datasheets — but with legal enforceability, audit access, and market-access consequences for non-compliance.

---

## Performative vs Substantive Transparency

The central critique of model cards, datasheets, and system cards: they enable **performative compliance** — producing documents that satisfy formal requirements without providing genuinely useful information.

### Failure Modes

1. **Vagueness:** "The model was trained on diverse internet data" — reveals nothing about actual biases or coverage
2. **Omission of harmful capabilities:** Model cards often list intended uses without disclosing discovered failure modes or red-team findings
3. **Audience mismatch:** Cards written to satisfy lawyers and regulators rather than developers deploying the system
4. **Missing quantitative evaluation:** Qualitative descriptions of "may exhibit bias" without data are unactionable for users
5. **Proprietary data opacity:** Cannot disclose training data composition for competitive/legal reasons → large documentation gaps

### Structural Critique: Who Benefits?

- **Deployers** benefit from model cards that clarify capability and limitation gaps — but only if models are documented honestly
- **Affected communities** may receive little benefit from documentation they cannot access or interpret
- **Regulators** receive documentation that is reviewable but may be unverifiable without audit access
- **Companies** receive legal cover and reputational benefit from publishing cards — incentive misalignment with substantive disclosure

### The Verification Gap

Documentation artefacts can only be verified if auditors have **access to training data and model weights**. Most commercial model cards describe systems whose training data is proprietary and whose weights are not publicly inspectable — creating a gap between stated claims and verifiable facts.

EU AI Act attempts to close this via **notified bodies** (Article 43) and market surveillance authorities — but the capacity of regulatory bodies to actually audit large AI systems remains contested.

---

## Best Practices (Technical)

For organisations producing model cards and datasheets:

1. **Disaggregated benchmarks are non-negotiable:** Publish performance on protected attribute slices; don't bury in appendixes
2. **Document the negative:** Explicitly list known failure modes discovered during evaluation; list tasks the model should not be used for
3. **Link to evaluation artifacts:** Publish evaluation code, benchmark test sets, and evaluation protocols alongside the card
4. **Maintain temporal records:** Version model cards; date evaluations; indicate what has changed across versions
5. **Include red-team findings summary:** At minimum describe methodology and categories tested; ideally include aggregate outcomes without operationalisation details that enable attacks
6. **Use structured formats:** YAML or structured JSON enables machine-readable parsing, comparison across models, and integration into model registries

---

## References

1. Mitchell, M. et al. (2019). "Model Cards for Model Reporting." *FAccT 2019*
2. Gebru, T. et al. (2021). "Datasheets for Datasets." *Communications of the ACM*, 64(12)
3. Bommasani, R. et al. (2021). "On the Opportunities and Risks of Foundation Models." arXiv 2108.07258 (§5 on documentation)
4. OpenAI (2023). "GPT-4 System Card." openai.com
5. European Commission (2024). "The EU Artificial Intelligence Act — Annex IV." Official Journal EU
6. Liang, P. et al. (2022). "Holistic Evaluation of Language Models (HELM)." arXiv 2211.09110
7. Bender, E.M. et al. (2021). "On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?" *FAccT 2021*
