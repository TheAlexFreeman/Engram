---
source: agent-generated
origin_session: core/memory/activity/2026/03/27/chat-001
created: 2026-03-27
trust: medium
type: scope-note
plan: ai-governance-policy-research
phase: orientation
---

# AI Governance & Policy Research — Scope Note

## Purpose

Define the boundaries, target files, and cross-reference map for a new `ai/frontier/governance/` subdomain covering the regulatory landscape, technical governance mechanisms, and governance theory.

## Existing coverage audit

### What already touches governance

1. **Foundation model governance** (`ai/frontier/foundation-model-governance.md`): comprehensive survey of the regulatory landscape as of early 2026 — EU AI Act risk tiers, GPAI model provisions (10²³/10²⁵ FLOP thresholds), US executive orders, voluntary commitments, open-source governance debates. Trust: medium. This file is a strong single-file treatment that the new governance/ subdomain should extend in depth, not repeat. Boundary: the existing file provides the overview; the new files provide depth treatments of individual frameworks, technical mechanisms, and governance theory.

2. **Collective action synthesis** (`social-science/collective-action/collective-action-synthesis-ai-governance.md`): maps Olson, Ostrom, North, and Acemoglu/Robinson onto AI governance as collective action problems (public goods, common-pool resources, coordination). Trust: low. The governance theory file should cross-reference this as the social-science underpinning rather than re-explain institutional theory.

3. **Rationalist AI discourse** (`rationalist-community/ai-discourse/`): covers alignment theory, corrigibility, value-loading — the technical safety motivation for governance. The governance files should treat this as the "why governance is needed" background without duplicating alignment theory.

4. **Industry influence files** (`rationalist-community/ai-discourse/industry-influence/`): cover the rationalist community's analysis of lab incentive structures, safety-washing, and regulatory capture. The governance files should have a distinct voice — empirical and institutional rather than community-discourse-oriented.

### What does NOT already exist

- No file on the EU AI Act's implementation mechanics (compliance, conformity assessment, enforcement)
- No file on US AI policy in detail (Biden EO, NIST AI RMF, Trump reversal, Congressional inaction)
- No file on comparative global AI regulation
- No file on model cards, datasheets, and transparency artefacts as governance tools
- No file on red-teaming standards and eval frameworks as governance mechanisms
- No file on responsible scaling policies (Anthropic ASL, OpenAI Preparedness)
- No governance theory synthesis connecting institutional economics to AI governance

## Boundary decisions

| Boundary | Decision | Rationale |
|---|---|---|
| governance/ vs. foundation-model-governance.md | The existing file is the overview/survey. Governance/ files provide depth on individual regulatory frameworks, technical mechanisms, and theory. The existing file is not superseded — it remains the entry point. | Overview vs. depth split. |
| governance/ vs. social-science/collective-action/ | Governance/ files describe AI-specific regulatory and technical frameworks. Collective-action/ provides the game-theoretic and institutional foundations. Cross-reference, no duplication. | Applied vs. theoretical split. |
| governance/ vs. rationalist-community/ai-discourse/ | Governance/ covers formal institutions, regulatory frameworks, and technical standards. Rationalist discourse covers safety ideology, alignment theory, and community analysis. Different audiences and registers. | Institutional/empirical vs. ideological/community split. |
| Red-teaming depth | The governance red-teaming file covers the standardization angle (MITRE ATLAS, NIST, AISI pre-deployment). It cross-references the existing behavioral-testing-and-red-teaming.md for technique basics. | Avoiding duplication of testing-focused content. |

## Clear boundary with foundation-model-governance.md

The existing file covers:
- EU AI Act overview (risk tiers, GPAI provisions, timelines)
- US EOs and voluntary commitments (high-level summary)
- Open-source governance debate
- Safety frameworks (overview)
- C.S. Lewis framing of governance authority

The new files go deeper on:
- **EU AI Act**: compliance mechanics, conformity assessment procedures, national enforcement, GPAI code of practice details, timeline to full applicability, practical compliance checklists
- **US policy**: NIST AI RMF structure in detail, AI Safety Institute mandate, Congressional action/inaction, 2025 course correction
- **Global comparison**: jurisdictional comparison table (EU/UK/China/Canada/OECD), Brussels Effect, regulatory arbitrage
- **Technical mechanisms**: model cards/datasheets as compliance artefacts, eval framework standards, red-teaming standards
- **RSPs**: detailed ASL level analysis, OpenAI Preparedness Framework scorecard, DeepMind Frontier Safety Framework
- **Governance theory**: principal-agent analysis of AI governance, beyond collective-action framing

## Target file list (7 files + synthesis)

### Phase 2: Regulatory Landscape (3 files)

1. **eu-ai-act-risk-tiers-compliance.md**
   Full treatment of the EU AI Act (2024). Risk-tier framework: unacceptable (prohibited applications — social scoring, biometric mass surveillance, subliminal manipulation, predictive policing), high (conformity assessment, transparency, human oversight, logging mandates for critical infrastructure, hiring, credit, law enforcement, education, healthcare), limited (chatbot and emotion-recognition disclosure), minimal (no requirements). GPAI model obligations: documentation, capability evaluations, copyright compliance. Systemic risk threshold (10²⁵ FLOPs): additional requirements including adversarial testing, incident reporting, energy consumption disclosure. Enforcement: national market surveillance authorities + EU AI Office. Staggered timeline (Feb 2025 → Aug 2026). Compliance implications for software engineering teams: what changes in a development workflow.

2. **us-ai-policy-executive-orders-nist.md**
   Biden EO 14110 (Oct 2023): dual-use foundation model safety reporting (10²⁶ FLOP threshold), NIST AI Safety Institute establishment, watermarking directives, immigration for AI talent. NIST AI Risk Management Framework (AI RMF 1.0): four core functions (Govern, Map, Measure, Manage), tiers, profiles, and how organizations adopt it. July 2023 White House voluntary commitments from major labs (pre-deployment safety testing, information sharing, watermarking). Trump EO 14179 (Jan 2025): rollback of Biden reporting requirements, emphasis on "advancing AI innovation." Congressional landscape: no comprehensive federal AI legislation as of 2026; sector-specific bills (healthcare AI, deepfakes, child safety). Federal agency divergence: FDA, SEC, FTC each developing separate AI guidance. Comparison with EU approach: sectoral vs. comprehensive, voluntary vs. mandatory, ex-post vs. ex-ante.

3. **global-ai-regulatory-comparison.md**
   Comparative analysis across jurisdictions. EU: risk-based ex-ante comprehensive framework. UK: sector-led principles-based approach (no single AI law; regulators apply existing sectoral authority). China: algorithm recommendation regulations (2021), deep synthesis rules (2022), generative AI measures (2023) — CAC as primary regulator; content control emphasis. Canada: AIDA (Artificial Intelligence and Data Act) — companion to CPPA; delayed and uncertain status. OECD AI Principles: baseline international consensus (human-centered, transparency, accountability, robustness). Regulatory arbitrage risks: companies choosing jurisdiction to minimize compliance burden. The Brussels Effect: whether the EU AI Act becomes the de facto global standard (as GDPR did for data privacy). Race-to-the-bottom vs. coordination equilibria. WTO implications for model access as trade in services.

### Phase 3: Technical Governance Mechanisms (3 files)

4. **model-cards-datasheets-transparency-artefacts.md**
   The transparency artefact ecosystem. Mitchell et al. (2019) model cards: intended use, performance metrics disaggregated by group, limitations, ethical considerations. Gebru et al. (2021) datasheets for datasets: motivation, composition, collection process, preprocessing, uses, distribution, maintenance. Meta system cards: deployment-level documentation including usage policies, safety testing results, monitoring plans. Transparency reports as ongoing governance compliance. When disclosure is substantive vs. performative: the "checklist compliance" critique (Raji et al.). Connection to EU AI Act transparency obligations and NIST AI RMF documentation requirements. The gap between model cards as research outputs and model cards as compliance artefacts.

5. **red-teaming-standards-and-eval-frameworks.md**
   Red-teaming as governance mechanism (not just security practice). MITRE ATLAS: adversarial threat landscape taxonomy for AI systems — attack categories, techniques, case studies. The NIST AI RMF "Measure" function: systematic evaluation of AI risks. Eval frameworks: HELM (Stanford CRFM — holistic evaluation across scenarios, metrics, and models), BIG-bench/BIG-bench Hard, MMLU/MMLU-Pro, GPQA (graduate-level questions). Responsible capability evaluation: uplift measurement for CBRN threats, cyberweapons, persuasion/manipulation. The UK AI Safety Institute's pre-deployment evaluation model (Frontier AI Taskforce → AISI). The "eval as governance" thesis: capability evaluations as the technical substrate that makes regulatory thresholds meaningful. Cross-reference to testing/behavioral-testing-and-red-teaming.md for technique basics.

6. **responsible-scaling-policies-anthropic-openai.md**
   Voluntary governance commitments by frontier labs. Anthropic RSP: AI Safety Levels (ASL-1 through ASL-4+) — capability thresholds that trigger escalating mitigations (containment, deployment controls, monitoring). How ASL levels are assessed (capability evaluations for CBRN uplift, autonomous replication, cyberweapons). Anthropic's commitment: pause training or deployment if mitigations don't meet the required ASL level. OpenAI Preparedness Framework: risk scorecard across four domains (CBRN, cyberweapons, persuasion, model autonomy); low/medium/high/critical risk levels; Safety Advisory Group and Board oversight. DeepMind Frontier Safety Framework: critical capability levels, evaluation-triggered mitigations. Google and Meta safety commitments. How voluntary RSPs relate to regulation: preview, substitute, or complement? Track record: cases where RSPs triggered actual changes vs. cases where they didn't.

### Phase 4: Synthesis (1 file, requires approval)

7. **governance-synthesis-institutional-analysis.md**
   Capstone synthesis. Key themes: (a) the regulatory landscape is fragmented — EU comprehensive vs. US sectoral vs. China content-focused — and this fragmentation itself is a governance challenge; (b) technical governance mechanisms (model cards, evals, RSPs) are the connective tissue between regulatory frameworks and actual AI development practice; (c) the principal-agent analysis of AI governance: regulators as principals, labs as agents, information asymmetry as the fundamental challenge (labs know more about model capabilities than regulators); (d) collective action applies at two levels — inter-lab coordination (safety race-to-the-bottom) and inter-state coordination (regulatory arbitrage); (e) the enforcement gap: even the EU AI Act faces challenges of technical capacity, regulatory speed, and extraterritorial enforcement. Cross-references to foundation-model-governance.md, collective-action-synthesis-ai-governance.md, and rationalist discourse on alignment.

## Cross-reference map

| New file | Cross-references to existing files |
|---|---|
| eu-ai-act-risk-tiers-compliance | → foundation-model-governance.md (overview), social-science/collective-action/acemoglu-robinson-inclusive-institutions.md |
| us-ai-policy-executive-orders-nist | → foundation-model-governance.md (US section), testing/behavioral-testing-and-red-teaming.md |
| global-ai-regulatory-comparison | → foundation-model-governance.md, social-science/collective-action/collective-action-synthesis-ai-governance.md |
| model-cards-datasheets-transparency-artefacts | → eu-ai-act (transparency obligations), testing/ml-evaluation-methodology.md |
| red-teaming-standards-and-eval-frameworks | → testing/behavioral-testing-and-red-teaming.md (technique basics), testing/ml-evaluation-methodology.md |
| responsible-scaling-policies-anthropic-openai | → rationalist-community/ai-discourse/canonical-ideas/corrigibility-shutdown-problem-value-loading.md, alignment/frontier-alignment-research.md |
| governance-synthesis-institutional-analysis | → foundation-model-governance.md, collective-action-synthesis-ai-governance.md, frontier-synthesis.md |

## Duplicate coverage check

- foundation-model-governance.md is an overview; new files provide depth. Complementary.
- collective-action-synthesis covers institutional theory; new governance theory synthesis applies it to the specific AI governance domain. Different level of abstraction.
- behavioral-testing-and-red-teaming covers testing technique; new red-teaming file covers standardization and governance dimensions. Different angle.

## Formatting conventions

Per existing ai/frontier/ files:
- YAML frontmatter: `source`, `origin_session`, `created`, `trust`, `type`, `related`
- Markdown body: H1, H2, H3; tables for comparisons and frameworks
- Depth: 1000–1500 words per file; cite specific regulations, frameworks, and organizations
