---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-005
source: agent-generated
trust: medium
related: eu-ai-act-risk-tiers-compliance.md, us-ai-policy-executive-orders-nist.md, global-ai-regulatory-comparison.md, responsible-scaling-policies-anthropic-openai.md, red-teaming-standards-and-eval-frameworks.md, model-cards-datasheets-transparency-artefacts.md, ai-governance-synthesis.md, ../../../../social-science/collective-action/ostrom-governing-the-commons.md
---

# AI Governance Theory: Principal-Agent Problems and AI Auditing

Government regulation of AI and voluntary governance by AI developers share a common structure that can be analyzed through principal-agent theory, mechanism design, and institutional economics. This file provides the theoretical framework for understanding why AI governance is hard and what institutional designs might work.

---

## The Principal-Agent Structure of AI Governance

### The Basic Setup

AI governance involves at least three principals and agents in a nested hierarchy:

```
Society / Public (ultimate principal)
    ↓ delegates monitoring to
Government / Regulators (principal + social agent)
    ↓ attempts to govern
AI Developers (agent with private information)
    ↓ deploy systems to
Users (principal + commercial agent)
    ↓ interact with
AI Systems (technical agent)
```

**Principal-agent problems arise at every level**:

1. **Society → Regulator**: Regulators have their own interests (budget, prestige, capture). Public preferences for AI governance are diffuse and weakly expressed.
2. **Regulator → Developer**: The developer has private information about model capabilities, training data, and safety properties. The regulator cannot directly observe this.
3. **Developer → User**: Developers design systems for average users; individual users have specific, often unrepresented interests.
4. **User → System**: The AI system optimizes for measured outcomes, which may diverge from user intent (Goodhart's Law).

### Information Asymmetry

The central problem is **capability information asymmetry**: developers know far more about their model's capabilities and limitations than any external party. Evaluating model capabilities requires:
- Access to the model (compute, API)
- Expertise to design meaningful evaluations
- Time to run evaluations before deployment

No current regulatory body has all three at scale. This asymmetry creates the fundamental governance challenge: the regulator cannot verify what the developer claims.

---

## Metatransparency

**Metatransparency** (Floridi 2014, later applied to AI by Mittelstadt 2019) proposes a partial solution: rather than requiring developers to disclose all proprietary details to the public, they disclose to a trusted intermediary (regulator, auditor) who certifies compliance. The public benefits from knowing that certification occurred without receiving the commercially sensitive details.

### How It Works

```
Developer → [detailed disclosure] → Auditor
                                        ↓ certifies
Public ← [high-level certification] ← Auditor
```

Metatransparency is the governance model for:
- **Medical device approval** (FDA inspects manufacturing; public sees approval status)
- **Financial auditing** (KPMG audits books; public sees audit opinion)
- **EU AI Act** (conformity assessment bodies certify high-risk AI; public sees CE mark)

**Limitations for AI**: Unlike drug safety or financial accuracy, AI capability evaluations lack agreed-upon standards, and the evaluation problem itself is unsolved for frontier models. A "certified safe" label requires knowing what "safe" means and how to test for it.

---

## AI Auditing Models

### Types of AI Auditing

| Audit Type | What Is Examined | Who Conducts It | Example |
|-----------|-----------------|-----------------|---------|
| **Technical audit** | Model weights, training data, eval results | Technical auditor with model access | NIST AI RMF assessment |
| **Process audit** | Development processes, documentation, governance structures | Quality-system auditor | ISO 42001 certification |
| **Outcome audit** | Deployment effects measured ex post | Investigative body | Algorithmic audit of ad delivery |
| **Red-team audit** | Adversarial capability probing | Security auditor | UK AISI pre-deployment evals |
| **Impact assessment** | Societal effects on defined groups | Social/legal assessor | EU AI Act fundamental rights impact assessment |

### Third-Party Audit Independence

The value of an audit depends on the auditor's independence from the developer. Standard independence requirements from financial auditing:

1. **Independence in fact**: The auditor has no material financial interest in the outcome
2. **Independence in appearance**: Reasonable observers perceive no conflict of interest
3. **Rotation**: Mandatory rotation of audit firms prevents capture through long-term relationship

Applied to AI: third-party evaluators should not be funded primarily by the developers they evaluate, should disclose conflicts of interest, and should be subject to public accountability for their assessments. Current AI evaluation labs (UK AISI, US AISI) are government-funded and publicly accountable; private red-teamers working under NDA are not.

---

## Governance Failure Modes

### 1. Regulatory Capture

Regulatory capture occurs when the regulated industry gains control over the regulatory body, through:
- **Revolving door**: Regulators subsequent employment in regulated industry
- **Information capture**: Regulator depends on industry for expertise
- **Lobbying**: Industry shapes regulatory standards to favor incumbents

AI governance is particularly susceptible because:
- Technical expertise is concentrated in large AI companies
- Government salaries cannot compete with private-sector AI researcher compensation
- Small AI companies lack lobbying resources → regulation shaped by incumbents creates entry barriers

### 2. Goodharting on Evaluation Metrics

When an evaluation metric is used for compliance, it becomes a target and loses validity as a performance measure (Campbell's Law; Goodhart's Law). Applied to AI governance:

- If capability thresholds are based on MMLU scores, developers will optimize for MMLU without genuine capability improvement
- If safety certification requires passing a specific red-team protocol, developers will optimize for that protocol rather than underlying safety properties
- Responsible scaling policies (ASL triggers) face this problem: capability thresholds (e.g., "provides serious uplift in bioweapon synthesis") require evaluation protocols that are themselves gameable

**Theoretical fix**: Metatransparency with randomized evaluation is more robust — if developers do not know in advance what evaluations will be run, they cannot optimize specifically for them.

### 3. Voluntary Commitment Drift

Commitments made voluntarily (responsible scaling policies, voluntary AI safety pledges) are not legally binding and can be unilaterally changed. Historical pattern from financial regulation: voluntary commitments proposed by industry as alternatives to regulation tend to weaken over time as competitive pressure increases.

The analogy is credit rating agencies pre-2008: voluntary commitments to "rate honestly" were eroded by the issuer-pays business model (conflict of interest). For AI: voluntary safety commitments may be eroded by competitive pressure to deploy faster.

### 4. Coverage Gaps

Current governance instruments (EU AI Act, US executive orders, Anthropic RSP, OpenAI Preparedness) cover:
- ✅ High-risk applications in specific sectors (healthcare, finance, law enforcement)
- ✅ Pre-deployment capability evaluation for frontier models above a compute threshold
- ❌ Cumulative societal effects of widely deployed medium-risk models
- ❌ Open-source models that cannot be regulated pre-deployment
- ❌ Multi-system interactions (AI → AI pipelines) where no single system is high-risk but the combination is

---

## Ostrom's Design Principles Applied to AI Governance

Ostrom (1990) identified eight design principles for sustainable commons governance — institutional arrangements that have successfully avoided the tragedy of the commons. Applied to AI safety as a commons:

| Ostrom Principle | AI Governance Application |
|-----------------|--------------------------|
| 1. Clearly defined boundaries | Define which AI systems are subject to which rules (compute threshold, risk tier) |
| 2. Congruence with local conditions | Regulation calibrated to actual capabilities, not hypothetical worst cases |
| 3. Collective choice arrangements | AI developers and affected communities participate in standard-setting |
| 4. Monitoring | Independent evaluation bodies with model access |
| 5. Graduated sanctions | Proportionate penalties; not all-or-nothing |
| 6. Conflict resolution mechanisms | Clear legal process for challenging governance decisions |
| 7. Recognition of rights | Developers have due-process rights; affected parties have standing |
| 8. Nested governance | International coordination + national implementation + company-level policies |

**Where current AI governance falls short**: Principles 3 (affected communities have minimal input into standard-setting), 4 (monitoring lacks independence and resources), and 8 (nested governance is incipient at best).

---

## References

1. Jensen, M. & Meckling, W. (1976). Theory of the Firm: Managerial Behavior, Agency Costs and Ownership Structure. *Journal of Financial Economics*, 3(4), 305–360.
2. Floridi, L. (2014). Distributed Morality in an Information Society. *Science and Engineering Ethics*, 19, 727–743.
3. Mittelstadt, B. (2019). Principles alone cannot guarantee ethical AI. *Nature Machine Intelligence*, 1, 501–507.
4. Ostrom, E. (1990). *Governing the Commons*. Cambridge University Press.
5. Hadfield-Menell, D. & Hadfield, G. (2019). Incomplete Contracting and AI Alignment. *Proceedings of the 2019 AAAI/ACM Conference on AI, Ethics, and Society*.
6. Raji, I. D. et al. (2020). Closing the AI Accountability Gap. *FAccT*.
7. Brundage, M. et al. (2020). Toward Trustworthy AI Development. *arXiv:2004.07213*.
