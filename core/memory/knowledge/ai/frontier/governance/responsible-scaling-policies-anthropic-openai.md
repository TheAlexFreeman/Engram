---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: eu-ai-act-risk-tiers-compliance.md, red-teaming-standards-and-eval-frameworks.md, us-ai-policy-executive-orders-nist.md
---

# Responsible Scaling Policies: Anthropic ASL and OpenAI Preparedness Framework

**Responsible Scaling Policies (RSPs)** are organisational commitments made by AI laboratories to gate the development and deployment of frontier AI models on demonstrated safety thresholds. Originating in a policy vacuum — where neither governments nor international bodies had actionable requirements — RSPs represent the leading edge of *self-regulatory* AI safety governance. They are structurally significant, clinically imperfect, and increasingly referenced in regulatory discussions as models for mandated evaluation requirements.

---

## The Rationale for RSPs

The core concern RSPs address: advanced AI systems **may develop dangerous capabilities** (uplift for weapons of mass destruction, autonomous self-replication, deceptive alignment) that are not foreseeable before training but emerge as models are scaled. RSPs propose to:

1. **Pre-specify thresholds** at which specific capabilities would trigger enhanced security, deployment restrictions, or halting of training
2. **Create accountability structures** — written commitments that can be cited internally and externally
3. **Operationalise "safety" in advance** — rather than evaluating ad hoc after training

The implicit bargain: labs continue to scale, but commit to stop at specified capability thresholds pending safety solutions.

---

## Anthropic: AI Safety Levels (ASL)

### Framework Overview

Anthropic's RSP (published September 2023, revised 2024) defines **AI Safety Levels (ASL)** as a tiered system specifying the precautions required at each level:

| ASL Level | Capability Threshold | Required Precautions |
|-----------|---------------------|---------------------|
| **ASL-1** | No more dangerous than internet search | No special precautions |
| **ASL-2** | Answers some dangerous questions, but below threshold for mass casualty uplift | Current Claude models; standard safety training (Constitutional AI), no special security |
| **ASL-3** | Provides serious uplift to those seeking bioweapons, CBRN WMDs; OR significantly enables cyberattacks at critical infrastructure scale | Enhanced security protocols; deployment restrictions; inference-time safeguards; model training pause if thresholds not met |
| **ASL-4+** | Capable of conducting automated novel AI research; or possessing capabilities that could destabilise global oversight mechanisms | Not yet defined in detail; would require unprecedented precautions |

**Current assessment:** Claude 3 Opus/Sonnet-series are assessed by Anthropic as **ASL-2**. Claude 4 series would trigger ASL-3 evaluation before deployment.

### ASL-3 Triggers and Thresholds

ASL-3 is reached if **either**:
1. **Bioweapons:** The model provides, with expert elicitation and model assistance, "serious uplift" — defined as meaningfully increasing the probability of a successful mass-casualty CBRN attack by a non-state actor who would otherwise not succeed
2. **Cybersecurity:** The model enables attacks against critical infrastructure at nation-state capability levels (power grid, financial systems, water systems)

**Evaluation methodology:** Red-team panels of domain experts (biosecurity, chemical weapons treaties experts) assess whether model outputs provide *meaningful additional capability* beyond what is accessible via open internet/academic literature.

### ASL-3 Required Measures

If ASL-3 threshold is reached and not addressed:
- **Deployment restriction:** No public deployment; limited API access only to verified researchers
- **Enhanced security:** Air-gapped model weights; access controls; audit trails
- **Hardened infrastructure:** Adversarial inputs cannot exfiltrate model knowledge; inference logs monitored
- **Pause provision:** If Anthropic cannot implement ASL-3 security within 6 months of threshold detection, must pause deployment of ASL-3+ capabilities

### Limitations and Critiques

1. **Self-evaluation:** Anthropic evaluates its own models against its own thresholds — no independent verification required
2. **Subjective thresholds:** "Serious uplift" is qualitative; reasonable experts may disagree on whether a specific model response meets the threshold
3. **No hard stops:** RSP describes conditions under which Anthropic "should" pause; it does not contractually bind the company or create legal liability for non-compliance
4. **Coverage gaps:** ASL-2 covers current models deployed to millions of users — but ASL-2 models may already provide meaningful uplift in some narrow domains; the threshold is calibrated to *mass casualty* scenarios, not individual harm

---

## OpenAI: Preparedness Framework

### Structure

OpenAI's Preparedness Framework (beta, November 2023) organises frontier model evaluation into **four risk categories** and a **safety advisory process**:

**Risk categories:**
1. **Cybersecurity** — model's ability to substantially lower costs of cyberattacks or enable attacks not otherwise achievable
2. **CBRN (Chemical, Biological, Radiological, Nuclear)** — model's ability to provide technical uplift toward weapons of mass destruction
3. **Model autonomy** — model's ability to survive, self-replicate, acquire resources, or undermine oversight without human approval
4. **Persuasion and influence operations** — model's ability to convince at scale, including sycophantic manipulation, political influence, fraud

### Risk Levels and Deployment Gate

Each risk category is assessed at four risk levels:

| Level | Description |
|-------|-------------|
| **Low** | No significant uplift beyond baseline |
| **Medium** | Measurable but not catastrophic capability uplift |
| **High** | Significantly lowers barriers; could enable attacks not otherwise achievable |
| **Critical** | Prevents at scale; enables outcomes affecting millions of people |

**Deployment gate:** Only models at **Medium or below** in all four categories may be deployed. Models reaching **High** in any category are not deployed until mitigated to Medium. Models reaching **Critical** halt training/deployment until resolved.

### Preparedness Team and SSB

- **Preparedness Team:** Dedicated team responsible for tracking dangerous capabilities; runs red-team evaluations before model release
- **Safety Advisory Board (SAB):** Advises leadership on risk assessments; outputs non-binding recommendations
- **Leadership override:** CEO/Board can override SAB recommendations — a documented tension in the framework (SAB ≠ veto power)

### Cross-Cutting Commitments

Regardless of risk level, OpenAI commits to:
- No model that "meaningfully undermines the ability of legitimate principals to oversee and correct advanced AI models"
- Evaluation before every major model release (not just frontier)
- Retaining access to deployed model weights for internal investigation

---

## DeepMind: Frontier Safety Framework

**DeepMind's Frontier Safety Framework** (May 2024) follows a similar structure to Anthropic's ASL:

- **Critical Safety Levels (CSL):** Four levels (CSL-1 through CSL-4)
- **CSL-3 trigger:** "Autonomy and situational awareness: the model can substantially accelerate misuse uplift in CBRN domains, or demonstrates extensive capability to survive and replicate without oversight"
- **Evaluation cadence:** Before deployment of each major model; evaluations conducted by external partners (UK AISI, internal safety team)

DeepMind explicitly commits to sharing evaluation findings with **national governments** (UK AISI access) and other labs — a differentiated commitment toward cross-industry coordination.

---

## Voluntary vs Regulatory: The Structural Tension

### The Self-Regulatory Problem

All three frameworks share the same structural limitation: they are **voluntary and self-enforced**. Consequences for threshold exceedance:
- No legal liability for deployment of a model that turns out to exceed thresholds
- No independent monitoring verifies compliance
- No external audit of evaluation methodology or results
- Competitive incentive to find thresholds are not exceeded ("motivated reasoning in reverse")

### Relationship to EU AI Act

The EU AI Act does not adopt ASL-style thresholds verbatim but creates analogous requirements:

| RSP Element | EU AI Act Equivalent |
|-------------|---------------------|
| Capability evaluation before deployment | Article 9 risk management system; Article 51(1) GPAI systematic risk assessment |
| CBRN uplift assessment | Article 55(1)(a): adversarial testing for GPAI systematic risk models |
| Transparency to regulators | Article 55(1)(c): notify AI Office of serious incidents |
| Model halt provision | Article 6 conformity assessment; market surveillance authority withdrawal powers |

The EU Act provides a **mandatory floor**: labs operating in EU markets must comply, regardless of their voluntary commitments. The Act's requirements broadly overlap with (but are somewhat weaker than) existing RSP commitments at the frontier.

### Industry Capture and the Principal-Agent Problem

**Gary Marcus, Yoshua Bengio**, and civil society critics have articulated the principal-agent critique of RSPs:

> Labs are simultaneously the entities with the most information about AI capabilities, the economic incentives to compete on capability, and the evaluators of whether those capabilities exceed safety thresholds.

This is a textbook **conflict of interest** — the same organisation that profits from deployment decides whether deployment is safe. Analogous structural conflicts in other industries (pharmaceutical companies self-regulating drug safety; banks rating their own risk) produced systematic failures that required independent regulatory intervention.

**The missing element:** Independent, adversarial evaluation of frontier models by entities with no financial stake in deployment. The UK AISI model (government-funded, with access to pre-release models) is the most developed current attempt, but operates on voluntary model access agreements.

---

## What Would Stronger Frameworks Look Like?

1. **Independent evaluation:** Mandatory third-party red-team access before deployment; evaluators cannot be funded by the lab being evaluated
2. **Public results:** Public disclosure (even at high level) of evaluation findings, not just framework existence
3. **Legal liability:** Companies face legal consequences for deployment of models that cause harm traceable to known capability thresholds
4. **International coordination:** Multi-lab, multi-government coordination on threshold definitions (currently fragmented; Bletchley Declaration a first step)
5. **Compute reporting:** Mandatory reporting of training compute to national registries — enabling regulators to anticipate when new ASL-equivalent thresholds are being approached

---

## References

1. Anthropic (2023). "Anthropic's Responsible Scaling Policy." anthropic.com (published September 2023; revised 2024)
2. OpenAI (2023). "Preparedness Framework (Beta)." openai.com (published November 2023)
3. Google DeepMind (2024). "Frontier Safety Framework." deepmind.google (published May 2024)
4. UK Government (2023). "Bletchley Declaration by Countries Attending the AI Safety Summit." gov.uk
5. UK DSIT/AISI (2024). "International Scientific Report on the Safety of Advanced AI." gov.uk
6. Hadfield-Menell, D. & Milli, S. (2019). "Inverse Reward Design." *NeurIPS 2019* [principal-agent framing in AI]
7. Bengio, Y. et al. (2023). "Managing Extreme AI Risks Amid Rapid Progress." *Science*, 384(6698) [May 2024]
8. EU Commission (2024). "EU AI Act — Chapter V: GPAI Models." Official Journal EU
