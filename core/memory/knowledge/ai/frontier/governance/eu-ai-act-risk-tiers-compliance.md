---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: foundation-model-governance.md, us-ai-policy-executive-orders-nist.md, global-ai-regulatory-comparison.md
---

# EU AI Act: Risk Tiers, Obligations, and Compliance

The **EU Artificial Intelligence Act** (Regulation 2024/1689, entered into force August 2024) is the world's first comprehensive binding AI law. It applies a product-safety risk-based architecture borrowed from EU consumer law, distinguishing four tiers of AI system risk and assigning escalating pre-market and post-market obligations accordingly.

---

## Legislative Architecture

### Legal Form and Scope

The AI Act is an **EU Regulation** (directly applicable in all 27 member states without transposition), building on the General Product Safety Directive and CE-marking machinery:

- **Territorial scope:** applies to AI systems placed on the EU market or used in the EU, regardless of provider's country of origin — extraterritorial reach analogous to GDPR
- **Ratione materiae:** covers "AI systems" defined as machine-based systems that infer from inputs to generate outputs (predictions, recommendations, decisions, content, actions); the definition deliberately avoids committing to any specific technical architecture
- **Ratione personae:** obligations fall on *providers* (developers who place on market), *deployers* (organisations using AI in professional context), and *importers/distributors*

### AI System vs. GPAI Model

The Act draws a critical distinction:

| Category | Definition | Primary Obligation Carrier |
|----------|-----------|---------------------------|
| AI system | Purpose-built for specific task(s) | Provider/deployer |
| GPAI model | Trained on large data, capable of broad range of tasks (foundation model) | Provider of GPAI model |
| GPAI system | GPAI model deployed as AI system | Both model provider + system deployer |

---

## The Four Risk Tiers

### Tier 1 — Unacceptable Risk (Prohibited)

Applications banned outright as incompatible with fundamental rights (Article 5):

1. **Subliminal manipulation** — techniques exploiting subconscious to distort behaviour causing harm
2. **Vulnerability exploitation** — targeting children, elderly, or disabled persons through manipulative techniques
3. **Social scoring by public authorities** — general-purpose scoring of individuals' behaviour leading to detrimental treatment in unrelated contexts
4. **Real-time remote biometric identification (RBI)** in publicly accessible spaces by law enforcement — with three narrow exceptions (targeted search for missing persons, prevention of imminent terrorist threat, prosecution of certain serious crimes; each requiring judicial/administrative authorisation)
5. **Emotion recognition in workplace and education** — inference of emotional states of workers/students
6. **AI-powered predictive policing** — profiling individuals solely based on personality traits to predict criminal behaviour
7. **Untargeted scraping of facial images** from internet or CCTV to build recognition databases

### Tier 2 — High Risk

High-risk AI systems must undergo **conformity assessment** before market placement. The tier is defined via Annex III (critical infrastructure applications) and Annex II (products already subject to EU product safety law — medical devices, machinery, vehicles):

**Annex III categories:**
1. Biometric identification and categorisation (except prohibited real-time RBI)
2. Management/operation of critical infrastructure (electricity, water, gas, transport, internet)
3. Education and vocational training (access to, advancement, evaluation)
4. Employment and worker management (recruitment, CV screening, task allocation, monitoring)
5. Access to essential private and public services (credit scoring, benefits, emergency services dispatch)
6. Law enforcement (risk assessment, evidence reliability, crime analytics, polygraphs)
7. Migration, asylum, and border control
8. Administration of justice and democratic processes

#### High-Risk Obligations

Providers of high-risk AI systems must:

| Obligation | Requirement |
|------------|-------------|
| **Risk management system** | Continuous iterative process throughout lifecycle (Art. 9) |
| **Data governance** | Training data documentation, representativeness, bias assessment (Art. 10) |
| **Technical documentation** | Detailed pre-market record sufficient for conformity assessment (Art. 11, Annex IV) |
| **Record-keeping/logging** | Automatic logging of events to ensure traceability (Art. 12) |
| **Transparency** | Users informed they are interacting with / output of high-risk AI (Art. 13) |
| **Human oversight** | Design must allow human monitoring and intervention (Art. 14) |
| **Accuracy and robustness** | Performance metrics, adversarial robustness, fallback modes (Art. 15) |
| **Conformity assessment** | Either internal (Annex VI) or third-party notified body (Annex VII), resulting in CE mark |
| **Post-market monitoring** | Continuous data collection post-deployment, incident reporting to authorities |
| **Registration** | Entry in EU AI database (public for high-risk in Annex III, non-public for Annex II) |

Deployers of high-risk systems must: verify provider compliance, implement human oversight, not use for purposes beyond provider's instructions, report serious incidents.

### Tier 3 — Limited Risk (Transparency Obligations)

AI systems that interact with or generate content involving humans face disclosure requirements:

- **Chatbots/conversational AI** — users must be informed they are interacting with an AI (unless obvious)
- **Deep fakes** — synthetic audio/video content must be labelled as AI-generated
- **AI-generated text about public interest matters** — must be machine-readable disclosure (e.g., watermarking schemes; Article 50 delegates technical standards to ETSI/CEN)
- **Emotion recognition and biometric categorisation systems** (not prohibited) — disclosure to exposed persons

No pre-market conformity assessment required, but supervisory authority may penalise non-disclosure.

### Tier 4 — Minimal Risk

All other AI systems (spam filters, video games, AI-powered recommendation systems outside high-risk categories).

**No mandatory obligations**, though providers are encouraged to follow voluntary codes of conduct. The Commission may publish templates for such codes.

---

## GPAI Model Obligations (Title VIII)

General-purpose AI models — large neural network models trained on large-scale data and capable of performing a wide range of tasks — are regulated separately regardless of whether they constitute "AI systems" by themselves.

### Classification by Systemic Risk

The threshold for **systemic risk** classification is based on training compute:

$$\text{FLOP threshold (systemic risk)} = 10^{25} \text{ floating-point operations}$$

This aligns roughly with GPT-4 scale (approximately $10^{24}$–$10^{25}$ FLOP) as a boundary. Models below a lower threshold ($10^{23}$ FLOP, or models with limited capabilities) may be exempt from GPAI obligations entirely under Commission delegated acts.

| GPAI Tier | Threshold | Additional Obligations |
|-----------|-----------|----------------------|
| All GPAI models | — | Technical documentation; copyright-compliant training (Art. 53); machine-readable summary of training data; cooperate with downstream providers |
| **GPAI with systemic risk** | ≥ 10²⁵ FLOP (or Commission designation) | + Model evaluation (red-teaming, adversarial testing); + Serious incident reporting; + Cybersecurity measures; + Energy consumption reporting |

For systemic-risk GPAI models, providers must conduct or commission **adversarial testing** before first deployment and annually thereafter, reporting methodology and findings to the AI Office.

### GPAI Codes of Practice

The **AI Office** (Commission body, not agency) coordinates development of voluntary-but-influential codes of practice for GPAI providers. Compliance with a code creates a presumption of conformity with GPAI obligations. GPAI providers who were consulted in code development but choose not to join must demonstrate equivalent compliance by other means.

---

## Enforcement Architecture

### Supervisory Bodies

| Level | Body | Mandate |
|-------|------|---------|
| National | **Market Surveillance Authority (MSA)** | Oversees Annex III high-risk systems; investigates complaints |
| National | **Notified Bodies** | Third-party conformity assessors; must be accredited |
| EU | **AI Office** (within Commission) | GPAI oversight; cross-border enforcement coordination; maintains EU AI database |
| EU | **European AI Board** | Member state representatives + Commission; coordinates supervisory approach |
| EU | **Scientific Panel of Independent Experts** | Technical advisory for GPAI; flags systemic risks |

### Penalties

| Violation | Maximum Fine |
|-----------|-------------|
| Prohibited practices (Tier 1) | €35M or 7% of global annual turnover (higher) |
| Other obligations violations | €15M or 3% |
| Misleading supervisory authorities | €7.5M or 1.5% |
| SMEs and micro-enterprises | Lower caps apply (capped at whichever applies) |

Member states may impose additional penalties for GDPR-adjacent violations through data protection authorities.

---

## Implementation Timeline

| Date | Milestone |
|------|-----------|
| **August 2024** | Act enters into force |
| **February 2025** | Prohibited practices (Tier 1) apply |
| **August 2025** | GPAI obligations apply; AI Office operational; Member states designate MSAs |
| **August 2026** | High-risk Annex III systems (plus notified body conformity assessment) apply |
| **August 2027** | High-risk Annex II (product-embedded) systems apply; full Act applies |

---

## Compliance Implications for Development Teams

### For AI System Providers

1. **Tier determination first:** Establish early whether the system falls under Annex III or a prohibited category — this determines whether any EU deployment is possible and what pre-launch timeline is required
2. **Documentation-by-design:** Technical documentation requirements (Annex IV) must be kept current from early development stages; retroactive reconstruction is penalised and practically difficult
3. **Training data records:** Maintain provenance, bias assessments, and data governance records. Copyright-compliant data sourcing is a GPAI obligation (relevant if building on or fine-tuning foundation models)
4. **Human oversight architecture:** High-risk systems must be designable for override; autonomy features that prevent human intervention may disqualify a design
5. **Post-market monitoring:** Build telemetry and incident detection into deployment architecture; the Act mandates a data feedback loop analogous to medical device vigilance

### For GPAI / Foundation Model Providers

1. **Compute tracking:** Maintain audit trail of training compute; if approaching $10^{23}$ FLOP boundary, engage Commission for classification guidance
2. **Red-teaming programs:** Systematic adversarial evaluation is mandatory for systemic-risk models; document methodology, scope, and results
3. **Downstream transparency:** Provide downstream AI system builders with technical documentation sufficient for them to fulfil their own compliance obligations
4. **Code of Practice participation:** Joining GPAI codes of practice creates legal presumption of compliance — lower compliance cost than demonstrating equivalent measures independently

### Cross-Cutting Considerations

- **GDPR interaction:** Many high-risk AI use cases process personal data; the GDPR's data minimisation and purpose limitation principles apply alongside AI Act requirements. Not all data protection officers are AI Act experts — cross-functional coordination required
- **Extraterritorial reach:** Providers based outside the EU must appoint an EU authorised representative (analogous to GDPR representatives)
- **Product liability:** AI Act obligations interact with the revised Product Liability Directive (2024/2853), extending liability to AI-embedded products

---

## Critical Perspectives

**Risk-category design critiques:**
- The Annex III list is enumerated, not principle-based — specific applications can be restructured to fall outside scope. Critics argue a principles-based approach (as in UK's pro-innovation framework) is more durable
- The $10^{25}$ FLOP threshold for systemic risk is technically arbitrary and may require frequent revision as compute costs fall (analogous to revising encryption key length thresholds)

**Innovation concerns:**
- Conformity assessment costs and documentation burdens may disadvantage EU-based SMEs relative to large US/Chinese players with compliance infrastructure
- The Brussels Effect depends on international actors choosing EU compliance over regulatory arbitrage — not guaranteed for B2B services delivered remotely

**Enforcement gap:**
- MSAs lack in-house ML expertise in most member states; the AI Office's Scientific Panel aims to fill this gap but is a thin layer over a wide regulatory surface

---

## References

1. Regulation (EU) 2024/1689 of the European Parliament and of the Council on Artificial Intelligence (EU AI Act) — OJ L 2024/1689
2. European Commission, "AI Office" — <https://digital-strategy.ec.europa.eu/en/policies/ai-office>
3. Veale, M. & Borgesius, F.Z. (2021). "Demystifying the Draft EU Artificial Intelligence Act." *Computer Law Review International*, 22(4)
4. Floridi, L. et al. (2021). "An Ethical Framework for a Good AI Society." *Minds and Machines*
5. Laux, J., Wachter, S., & Mittelstadt, B. (2024). "Three Pathways for Standardisation and Ethical Disclosure for Foundation Models." *Nature Machine Intelligence*
6. Engler, A. (2023). *The EU AI Act's Governance Structure*. Brookings Institution
