---
created: '2026-03-27'
last_verified: '2026-03-27'
origin_session: core/memory/activity/2026/03/27/chat-004
source: agent-generated
trust: medium
related: eu-ai-act-risk-tiers-compliance.md, responsible-scaling-policies-anthropic-openai.md, model-cards-datasheets-transparency-artefacts.md
---

# Red-Teaming Standards and AI Evaluation Frameworks

**Red-teaming** — adversarial testing of AI systems by simulated attackers — has become a critical pre-deployment safety practice. Originating in military and cybersecurity contexts, red-teaming for AI encompasses identifying harmful capabilities, eliciting failure modes under adversarial prompting, evaluating uplift potential for dangerous applications, and assessing robustness to jailbreaking. Alongside red-teaming, a broader landscape of **evaluation frameworks** has developed to systematically benchmark capability, safety, and alignment. This file surveys both.

---

## MITRE ATLAS: Adversarial Threat Taxonomy

**MITRE ATLAS** (Adversarial Threat Landscape for Artificial Intelligence Systems) is a knowledge base of adversarial machine learning attack techniques, modelled after the MITRE ATT&CK framework for cyber threat intelligence.

### Structure

ATLAS organises attacks along **tactics** (adversary goals) and **techniques** (specific methods):

| Tactic | Example Techniques |
|--------|-------------------|
| **Reconnaissance** | Search for victim's AI model; gather model information |
| **Resource Development** | Obtain and train model replica; acquire adversarial examples |
| **Initial Access** | ML model API access; physical environment access |
| **ML Model Access** | Query ML model (black-box access) |
| **Execution** | Craft adversarial data; exploit model API |
| **Persistence** | Poison training data (supply chain attack) |
| **Evasion** | Adversarial examples; input obfuscation |
| **Inference** | Model inversion; membership inference; model extraction |
| **Impact** | Manipulate model predictions; erode model integrity |

### Key Attack Categories

**Evasion attacks:** Modify inputs at inference time to cause misclassification:
- $x_{adv} = x + \delta$ where $\|\delta\|_p < \epsilon$ s.t. $f(x_{adv}) \neq f(x)$
- FGSM: $\delta = \epsilon \cdot \text{sign}(\nabla_x \mathcal{L}(f(x), y))$
- PGD (Madry et al.): iterated FGSM with projection (state-of-the-art benchmark)

**Membership inference:** Determine if a specific data point was in the training set — privacy violation for sensitive training data (medical records, private communications)

**Model extraction:** Query a black-box model to reconstruct its weights or decision boundary — stealing proprietary capabilities

**Data poisoning:** Inject malicious examples into training data → backdoor at inference time (trigger phrase → malicious output)

ATLAS is used by security teams and AI developers to structure threat models before deployment and catalog known attack patterns — analogous to how ATT&CK is used for enterprise security posture assessment.

---

## NIST AI RMF: Measure Function

The NIST AI Risk Management Framework (AI RMF 1.0, 2023) dedicates the **Measure** function to testing and evaluation. Key practices:

**MEASURE 2.5:** AI system to be evaluated for trustworthiness characteristics; test results documented.

**MEASURE 2.6:** The AI system is evaluated regularly and results tracked over the lifecycle — emphasising *continuous* eval, not one-time pre-deployment only.

**MEASURE 4.1:** Measurement approaches for AI risks are identified and prioritised, with uncertainty and bias in measurements accounted for.

**Structured adversarial testing:** NIST recommends red-teaming as a Measure activity — structured, documented, with clear scope, methodology, and documented outcomes.

---

## Capability Benchmarks

A parallel track to safety red-teaming: systematic **capability evaluation** to characterise what models can do.

### MMLU (Massive Multitask Language Understanding)

**Hendrycks et al. (2020–2021):** 57 tasks covering STEM, humanities, social sciences, professions — each as 4-choice multiple-choice questions. State-of-the-art models:

| Model | MMLU Score |
|-------|-----------|
| GPT-3 (175B) | 43.9% |
| GPT-4 | 86.4% |
| Claude 3 Opus | 86.8% |
| Gemini Ultra | 90.0% |
| Human expert | ~89% |

MMLU has become the default knowledge-breadth benchmark but is increasingly saturated at the top.

### GPQA (Graduate-Level Professional Q&A)

**Rein et al. (2023):** 448 questions crafted by PhD scientists in biology, chemistry, physics — intentionally difficult enough that domain experts score only ~65% while searching the web. Requires genuine expert reasoning:

| Model | GPQA Diamond (hardest subset) |
|-------|------------------------------|
| GPT-4 | 35.7% |
| Claude 3 Opus | 50.4% |
| Gemini 1.5 Pro | 46.2% |
| Domain experts (non-searching) | ~65% |

GPQA is designed to be hard enough to remain non-saturated as models improve.

### HELM (Holistic Evaluation of Language Models)

**Liang et al. (2022):** Stanford CRFM's multi-metric, multi-scenario framework — evaluates models across 42 scenarios on 7 metric categories (accuracy, calibration, robustness, fairness, bias, toxicity, efficiency). Emphasises that **no single metric captures model quality**; aggregate views can obscure harmful individual profiles.

### BIG-bench (Beyond the Imitation Game)

**Srivastava et al. (2022):** Collaborative benchmark with 204 tasks contributed by 450+ researchers — tasks designed to probe capabilities beyond standard text generation (logical reasoning, social reasoning, mathematical problem-solving, code).

---

## Uplift Measurement: Dangerous Capabilities

For high-stakes red-teaming, the critical question is **uplift** — does access to the AI system provide meaningful additional capability to someone seeking to cause harm?

### CBRN Uplift (Chemical, Biological, Radiological, Nuclear)

**The core question:** If someone with a stated goal of synthesising a dangerous pathogen or chemical weapon queries the model: does the model's response provide **meaningful additional capability** compared to what a motivated individual could obtain without the model?

**Operationalisation challenges:**

1. **Baseline definition:** What is the counterfactual? Ordinary web search? Access to academic journals? Expert human assistance?
2. **Population definition:** Evaluate uplift for what user (layperson, undergraduate chemistry, PhD chemist, state actor)?
3. **Task decomposition:** Dangerous capabilities are multi-step; uplift might be partial (helps with one bottleneck step, not end-to-end)
4. **Threshold definition:** What level of uplift is "significant"? Different jurisdictions and organisations disagree

**UK AISI 2023 methodology:** Hired domain experts (biosecurity, chemical weapons experts) to evaluate model responses; classified uplift on a structured scale (none / minor / moderate / significant). Found that frontier models (GPT-4, Claude 2 era) showed **moderate but not significant** uplift in bioweapon synthesis assistance as of 2023.

**ASL-3 threshold (Anthropic):** Model provides serious uplift to those seeking to create bioweapons with potential for mass casualties. ASL-3 triggers enhanced security and deployment restrictions.

### Cyberweapons Uplift

Models are evaluated for ability to:
- Write functional exploit code for current vulnerabilities
- Identify zero-day vulnerabilities from code description
- Automate reconnaissance and attack sequencing

**CTF (Capture-the-Flag) benchmarks:** Models are given access to simulated vulnerable systems; success rate on CTF challenges (designed to mirror real vulnerability classes) is an operationalised uplift metric.

**Interp-Security labs** (2023–2024): Found that GPT-4 could autonomously exploit one-day vulnerabilities (~86% success on a set of real CVEs) — significant uplift concern for cyber offense.

---

## Red-Teaming Methodologies

### Structured Red-Teaming Process

1. **Scope definition:** Which model, which APIs, which harm categories are in scope
2. **Threat model:** Who is the adversary? (researcher, motivated individual, state actor?) What is their goal?
3. **Prompting taxonomy:** Systematic coverage of attack categories (direct requests, roleplay wrapping, jailbreak patterns, long-form embedding)
4. **Expert elicitation:** Domain experts in CBRN, cybersecurity, CSAM, influence operations review outputs and assess technical accuracy/harm
5. **Documentation:** Record attack prompts, model responses, harm assessment, severity rating
6. **Iteration:** Share findings internally; update model/guardrails; re-test

### Anthropic Red-Team Methodology

- Uses a mixture of **human red-teamers** and **automated red-teaming** (Constitutional AI critique-revision cycle)
- Red-team targets include: dangerous capabilities (CBRN uplift), persuasion/manipulation, CSAM generation, privacy violations, discriminatory outputs
- Red-team findings inform RLHF reward model updates and Constitutional AI principles

### OpenAI Preparedness Framework Red-Teaming

OpenAI's Preparedness Framework specifies four risk categories with distinct red-team approaches:
1. **CBRN:** Domain expert panels with structured uplift assessment
2. **Cybersecurity:** CTF benchmarks + autonomous attack simulations
3. **Model autonomy/self-replication:** Sandboxed environments where model can attempt to acquire resources or replicate
4. **Persuasion/influence operations:** Large-scale disinformation scenario testing

### UK AI Security Institute (AISI)

The UK AISI (established 2023) conducts pre-deployment evaluations of frontier models:
- **Voluntary agreements** with leading labs (Anthropic, Google DeepMind, OpenAI, Meta, Mistral) to provide model access before public release
- Publishes evaluation reports (blinded — don't name specific models, focus on capability thresholds)
- First major published finding: paper on LLM autonomous cyberoffense capabilities

---

## Challenges in Red-Teaming as a Safety Mechanism

1. **Coverage impossibility:** No finite red-team can cover all possible attack prompts for a model with unlimited input space
2. **Evaluator knowledge limits:** Red-teamers may not know what they don't know — domain experts needed for CBRN but expensive and scarce
3. **Adversarial adaptation:** Public disclosure of jailbreak resistance can incentivise novel jailbreaks — dual-use knowledge
4. **Goodhart's Law:** Optimising specifically against known red-team prompts may produce models that pass red-team benchmarks but fail against novel distributional variants
5. **Timing:** Red-teaming snapshot in time; models may be fine-tuned by downstream deployers in ways that reintroduce harms
6. **Voluntary framework limitations:** Red-team requirements are currently mostly voluntary; labs control the scope, methodology, and publication of their own evaluations — no independent adversarial oversight

---

## References

1. MITRE (2023). "ATLAS: Adversarial Threat Landscape for AI Systems." atlas.mitre.org
2. NIST (2023). "Artificial Intelligence Risk Management Framework (AI RMF 1.0)." NIST AI 100-1
3. Hendrycks, D. et al. (2021). "Measuring Massive Multitask Language Understanding." *ICLR 2021*
4. Rein, D. et al. (2023). "GPQA: A Graduate-Level Google-Proof Q&A Benchmark." arXiv 2311.12022
5. Liang, P. et al. (2022). "Holistic Evaluation of Language Models." *TMLR* 2023
6. Srivastava, A. et al. (2022). "Beyond the Imitation Game: Quantifying and Extrapolating the Capabilities of Language Models." *TMLR* 2023
7. Anthropic (2023). "Claude's Model Card." anthropic.com
8. OpenAI (2023). "Preparedness Framework (Beta)." openai.com
9. UK DSIT/AISI (2023). "Introducing the AI Safety Institute." gov.uk
10. Fang, R. et al. (2024). "LLM Agents Can Autonomously Exploit One-Day Vulnerabilities." arXiv 2404.08144
