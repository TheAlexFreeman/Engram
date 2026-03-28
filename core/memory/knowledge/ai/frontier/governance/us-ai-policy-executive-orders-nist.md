---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: eu-ai-act-risk-tiers-compliance.md, global-ai-regulatory-comparison.md, foundation-model-governance.md, red-teaming-standards-and-eval-frameworks.md
---

# US AI Policy: Executive Orders, NIST RMF, and Federal Landscape

The United States has pursued AI governance primarily through **executive action**, **voluntary commitments**, and **standards development** rather than comprehensive binding legislation. This approach reflects both constitutional constraints on federal rulemaking and a deliberate policy preference (across at least two administrations) for preserving US AI competitive advantage while managing risk through non-statutory mechanisms. The landscape is fragmented, politically contested, and evolving rapidly.

---

## Executive Order 14110 (October 2023)

### Overview

**EO 14110: Safe, Secure, and Trustworthy AI** (October 30, 2023) was the Biden administration's primary AI governance instrument. It directed federal agencies to take numerous coordinated actions within 30–365-day windows. While expansive in scope, it created no enforceable rights for third parties and could be rescinded by a subsequent president (which it was, in January 2025).

### Key Provisions

#### Dual-Use Foundation Model Reporting (Section 4.2)

The most legally significant provision invoked the **Defense Production Act** to require developers of "dual-use foundation models" to report to the federal government:

- Safety test results, including red-team findings
- Hardware security measures
- Ownership/foreign control information

**Threshold:** Models trained using more than a threshold quantity of compute (initially $10^{26}$ floating-point operations for training) or models that present serious risk to national security, economic security, or public health and safety.

$$\text{DPA reporting threshold} = 10^{26} \text{ FLOP (training compute)}$$

This was intended to be updated as compute costs fall. The DPA basis gave the order unusual statutory grounding that pure executive directives lack.

#### NIST AI Safety Institute

Section 4.1 directed NIST to establish the **US AI Safety Institute (AISI)** within the National Institute of Standards and Technology. AISI's mandate:

- Develop guidelines for red-teaming, capability evaluation, and incident reporting
- Conduct pre-deployment evaluations of frontier models (voluntary by providers)
- Coordinate with international counterparts (UK AISI, EU AI Office)
- Develop AI safety standards to be incorporated into NIST frameworks

Anthropic, Google, Microsoft, Meta, and OpenAI all signed voluntary agreements to submit frontier models for AISI evaluation before public deployment.

#### Watermarking and Content Authentication

Section 4.5 directed NIST and OSTP to develop standards for **content authentication and watermarking** of AI-generated content:

- Technical standards for watermarking AI-generated images, video, and audio
- Provenance standards (building on C2PA — Coalition for Content Provenance and Authenticity)
- Research into detecting AI-generated text without visible markers

As of 2025, no mandatory watermarking standard has been adopted. C2PA adoption by Adobe, Microsoft, and camera OEMs has proceeded voluntarily.

#### Agency-Specific Directives

EO 14110 directed each major federal agency to:
- Appoint a Chief AI Officer
- Produce an AI use inventory
- Develop risk management frameworks for procurement and internal use
- Issue sector-specific guidance (e.g., HHS for health AI, DOL for employment AI, CFPB for credit AI)

### Revocation (January 2025)

President Trump revoked EO 14110 on January 20, 2025, via EO 14148 ("Unleashing American AI"). The revocation:
- Terminated reporting requirements under the DPA provision
- Directed agencies to revise or rescind AI policy guidance inconsistent with the new administration's "innovation-first" approach
- Directed OMB to review and replace Biden-era AI procurement guidance (M-24-10)

NIST AISI was not formally disbanded but operated under reduced authority and without a fresh White House mandate for its pre-deployment evaluation work.

---

## NIST AI Risk Management Framework (AI RMF 1.0)

### Overview

The **AI RMF 1.0** (released January 2023) is NIST's primary voluntary guidance for AI risk management. Unlike EO 14110, it is framework-based rather than directive-based, meaning it will survive any administration change. It has become the de facto reference for US federal AI procurement requirements and is widely referenced by industry.

### Structure: Govern-Map-Measure-Manage

The AI RMF organises risk management into four core functions, deliberately borrowing the structure of the Cybersecurity Framework (CSF):

#### 1. GOVERN

Establishes the organisational context for AI risk management:

- Policies, processes, and accountabilities for AI risk activities
- Organisational roles: AI risk owners (not just compliance owners), executive accountability
- Culture: psychological safety to surface concerns, incentive alignment
- Third-party / supply chain risk management
- Feedback mechanisms from affected communities

**Key concept:** Risk tolerance must be explicitly defined — the GOVERN function forces organisations to state what tradeoffs are acceptable before building systems, not after deployment.

#### 2. MAP

Identifies and categorises AI risks in context:

- Intended context of use (user population, deployment environment, failure modes)
- Categories of impact (accuracy, reliability, privacy, bias, security, transparency, explainability)
- Identification of affected groups, third parties, and deployment dependencies
- Risk prioritisation based on probability × impact in the specific context

**Key concept:** The MAP function explicitly asks organisations to identify **beneficial uses and associated risks** — not just risks in isolation — to avoid risk mitigation that destroys value without proportionate benefit reduction.

#### 3. MEASURE

Evaluates and tracks AI risks:

| Measure Category | Examples |
|-----------------|---------|
| Performance metrics | Accuracy, precision, recall, F1; distributional robustness |
| Fairness metrics | Demographic parity, equalised odds, calibration across groups |
| Explainability | Feature attribution, counterfactual explanations, model cards |
| Privacy | Membership inference attack risk, differential privacy guarantees |
| Security | Adversarial robustness, prompt injection, model extraction resistance |
| Reliability | Out-of-distribution detection, calibration, uncertainty quantification |

The MEASURE function calls for metrics to be adapted to the specific task and risk profile — there is no universal metrics suite.

#### 4. MANAGE

Responds to identified and measured risks:

- Risk response strategies (mitigate, transfer, accept, avoid)
- Incident response plans for AI-specific failure modes
- Monitoring and continuous re-evaluation as deployment context evolves
- Documentation of decisions (for accountability and learning)

### AI RMF Profiles and Playbooks

NIST has released supplemental **Profiles** applying the RMF to specific sectors (generative AI, synthetic content, cybersecurity AI) and **Playbooks** providing action steps within each function. The **Generative AI Profile** (NIST AI 600-1, 2024) addresses:

- Hallucination/confabulation risks
- Data poisoning in RLHF pipelines
- Homogenisation risk from model monoculture
- Prompt injection and jailbreaking as security threats

### Relationship to Standards and Procurement

AI RMF is referenced in:
- OMB M-24-10 (Biden: AI use in federal agencies — requires RMF-aligned risk assessments for "rights-impacting" and "safety-impacting" uses)
- CMMC / FedRAMP AI annexes (emerging)
- NIST SP 600-1 (Generative AI Profile)
- DOD AI Principles and Responsible AI Guidelines

Federal contractors are increasingly required to demonstrate RMF alignment in AI-related procurement.

---

## Voluntary Commitments (July and September 2023)

In July 2023, the Biden White House secured voluntary commitments from seven leading AI companies (Amazon, Anthropic, Google, Inflection, Meta, Microsoft, OpenAI) covering:

1. **Internal red-teaming** before deployment of powerful models
2. **Information sharing** about safety risks with governments and academia
3. **Investing in cybersecurity** and insider-threat safeguards
4. **Watermarking** AI-generated content to enable identification
5. **Bias and discrimination research** reporting
6. **Prioritising research** on societal risks (CBRN, disinformation)
7. **Advancing AI safety** research and supporting NIST standards

In September 2023, 15 additional companies joined. These commitments are politically significant but legally non-binding — they create reputational accountability and serve as reference points for future regulation.

---

## Trump Administration (2025): Course Correction

### Executive Order Rescinding EO 14110

The January 2025 revocation directed agencies to:

- Remove restrictions on AI development that "unduly impede" innovation
- Rescind agency guidance that reflected the prior administration's risk framing
- Develop a new **National AI Action Plan** within 180 days

### Executive Order on AI Infrastructure (February 2025)

A subsequent order directed:

- Fast-tracked permitting for AI data center construction
- Federal land availability for energy infrastructure supporting AI
- Export control reviews to ensure US AI hardware dominance

### Policy Trajectory

The Trump approach emphasises:
- **US competitive primacy** over multilateral governance coordination
- **Voluntary** over mandatory disclosure
- **Deregulation** at the agency level (rescinding HHS, CFPB, EEOC AI guidance)
- Continued export controls on advanced chips (Huawei, SMIC restrictions maintained/expanded)
- NIST AISI maintained but renamed and reoriented toward international standards influence rather than domestic pre-deployment evaluation

---

## Federal Agency AI Landscape

### Sector-Specific AI Guidance (Biden Era, Partially Rescinded)

| Agency | Domain | Key Action |
|--------|--------|-----------|
| **HHS** (ASPE) | Health AI | AI in healthcare guidance (2024); FDA AI/ML software as medical device framework |
| **CFPB** | Credit/Finance | Guidance on adverse action explanations for AI-based credit decisions |
| **EEOC** | Employment | Guidance on AI screening tools and disparate impact under Title VII |
| **NHTSA** | Autonomous vehicles | Automated Vehicle Safety Framework; ADS-specific reporting |
| **DOD** | Defense AI | Responsible AI Guidelines; Project Maven governance; AI Principles (2020) |
| **CISA** | Cybersecurity AI | AI Cybersecurity Roadmap; AI system attack surface guidance |
| **FTC** | Consumer protection | Unfair/deceptive AI marketing enforcement; algorithmic accountability; bias in commercial AI |

The FTC is one agency whose AI oversight authority is less dependent on executive directives: Section 5 of the FTC Act (prohibiting unfair/deceptive acts) applies to AI systems that deceive consumers or cause substantial injury.

### US AI Safety Institute Coordination

AISI coordinates with:
- **UK DSIT/AISI** — bilateral information sharing on frontier model evaluations; published joint evaluation methodology
- **EU AI Office** — observer status in standards activities; information sharing on GPAI systemic risk evaluations
- **G7 Hiroshima AI Process** — co-developed International Guiding Principles and Code of Conduct for Advanced AI

---

## State-Level Activity

Absent comprehensive federal legislation, states have begun acting independently:

| State | Action |
|-------|--------|
| **California** | SB 1047 (2024): Vetoed by Governor Newsom after industry pressure. AB 2013: AI training data transparency. AB 1008: AI and copyright clarifications. |
| **Colorado** | SB 205 (2024): First enacted high-risk AI law; bias audits for consequential decisions |
| **Illinois** | Algorithmic hiring bias law (2021); proposed facial recognition restrictions |
| **Texas** | TX SB 2139 (2025): Texas Responsible AI Governance Act — follows Colorado model |
| **New York City** | Local Law 144 (2023): Bias audits for automated employment decision tools |

The patchwork creates compliance complexity for nationwide AI deployments — one pressure point accelerating calls for federal preemption legislation.

---

## Congressional Activity

As of early 2026, no comprehensive federal AI legislation has been enacted. Active legislative tracks include:

- **Bipartisan Framework for AI Governance** — Senate working group (Schumer-Young) issued Road Map for AI Policy (2023-2024), hosting forums with tech leaders; no binding output
- **AI LEAD Act** — coordination of federal AI standards activities
- **DEFIANCE Act** (2024, enacted) — civil remedies for non-consensual AI-generated intimate imagery
- **NO FAKES Act** — voice/image likeness protection in AI-generated content
- **Open App Markets Act** — app store competition; tangentially relevant to AI distribution

The Senate has not succeeded in passing a comprehensive AI bill, and the 119th Congress (2025–2026) began with Republican majorities more focused on deregulation.

---

## Critical Assessment

**Strengths of US approach:**
- Flexibility allows rapid iterative refinement as technology evolves
- NIST RMF has achieved wide voluntary adoption; it is more technically sophisticated than EU prescriptive rules
- Sectoral approach matches enforcement to domain expertise (FDA for medical AI, FTC for consumer AI)

**Weaknesses:**
- No binding pre-market obligations for high-risk systems (unlike EU)
- Executive action instability — major regulatory infrastructure dissolved between administrations in <90 days
- Patchwork of 50-state requirements creates compliance burden without coherent national standard
- NIST AISI lacks authority to withhold approval or require remediation before deployment

**Comparison note:** The US system places AI regulation largely in a **liability-after-harm** framework (FTC enforcement, tort law) rather than EU's **ex ante obligation** framework. This may be more innovation-friendly but provides weaker protections for affected populations from harms that either don't create individual legal standing or where causation is difficult to prove.

---

## References

1. Executive Order 14110: Safe, Secure, and Trustworthy Development and Use of Artificial Intelligence (Oct. 30, 2023). 88 Fed. Reg. 75191
2. NIST (2023). *AI Risk Management Framework 1.0* (NIST AI 100-1). National Institute of Standards and Technology
3. NIST (2024). *Artificial Intelligence Risk Management Framework: Generative AI Profile* (NIST AI 600-1). Draft
4. Executive Order 14148: Unleashing American AI (Jan. 20, 2025)
5. White House Office of Science and Technology Policy, *National AI R&D Strategic Plan: 2023 Update*
6. Khan, L. (2023). "Protecting the Public from AI-Enabled Deceptive Practices." Federal Trade Commission blog
7. Dafoe, A. (2022). "AI Governance: A Research Agenda." Future of Humanity Institute
