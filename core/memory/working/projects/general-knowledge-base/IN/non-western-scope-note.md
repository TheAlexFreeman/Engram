---
source: agent-generated
origin_session: core/memory/activity/2026/03/27/chat-001
created: 2026-03-27
trust: medium
type: scope-note
plan: non-western-philosophy-research
phase: orientation
---

# Non-Western Philosophy Research — Scope Note

## Purpose

Define the boundaries, target files, and cross-reference map for a new `philosophy/non-western/` subdomain with depth coverage of Indian and Chinese philosophical traditions.

## Existing coverage audit

### What already exists for non-Western philosophy

1. **Indian philosophy survey** (`history/non-western/indian-philosophy.md`): comprehensive survey covering Vedic/Upanishadic foundations, all six orthodox schools (Nyāya, Vaiśeṣika, Sāṃkhya-Yoga, Mīmāṃsā, Vedānta), Buddhism (Madhyamaka, Yogācāra), Jainism, Cārvāka, and modern Indian philosophy. Trust: low. This is a strong orientation file — substantial in scope but survey-level in depth. The new files should go substantially deeper on selected traditions.

2. **Chinese philosophy survey** (`history/non-western/chinese-philosophy.md`): covers Confucius, Mencius, Xunzi, Laozi, Zhuangzi, Mohism, Legalism, Neo-Confucianism, and the modern encounter with the West. Trust: low. Same assessment: excellent orientation, but each tradition deserves its own depth treatment.

3. **Islamic/modern philosophy** (`history/non-western/islamic-modern-philosophy.md`): covers later classical Islamic philosophy (Suhrawardi, Mulla Sadra, Ibn Arabi), the modern encounter with Western thought, Islamic modernism. Trust: low. This is more substantial than the other two surveys — it includes genuine philosophical depth on Mulla Sadra's ontology and Suhrawardi's illuminationism.

4. **Moral status / AI welfare** (`ethics/moral-status-ai-welfare.md`): discusses sentience, rationality, interests, and relational criteria for moral status. The anattā treatment in the Buddhist logic file should provide an empirical-philosophical contrast to the Western substance-based personal identity assumed here.

5. **Parfit reductionism** (`personal-identity/parfit-reductionism.md`): Parfit's reductionist view of personal identity (no further fact). The Buddhist anattā (no-self) doctrine is the closest pre-modern analog — the cross-reference here is philosophically significant.

6. **4E cognition** (`phenomenology/embedded-enacted-ecological-4e.md`): embodied/enacted/embedded/ecological cognition. Daoist wu-wei and Buddhist process philosophy have structural similarities to 4E's rejection of Cartesian internalism. The synthesis should note these convergences.

### What does NOT already exist

- No depth file on Advaita Vedānta (non-dualism, māyā, Brahman-ātman identity)
- No depth file on Buddhist logic (Dignāga, Dharmakīrti — epistemology, apoha theory)
- No depth file on Nyāya-Vaiśeṣika epistemology and ontology
- No depth file on Jain epistemology (anekāntavāda, syādvāda)
- No depth file on Confucian moral psychology (Mencius vs. Xunzi on human nature)
- No depth file on Daoist metaphysics (Zhuangzi, wu-wei, process philosophy)
- No depth file on Wang Yangming's unity of knowledge and action
- No cross-tradition synthesis connecting non-Western philosophy to existing domains

## Decision on Islamic philosophy scope

**Decision: Exclude Islamic philosophy from this plan.** The existing islamic-modern-philosophy.md already provides substantial philosophical depth on Suhrawardi, Mulla Sadra, and Ibn Arabi — more than the Indian and Chinese surveys provide for their respective traditions. Islamic philosophy depth files would be valuable but represent a lower marginal gap. This plan focuses on the Indian and Chinese traditions where the gap is most acute. Islamic philosophy depth can be addressed in a future wave.

## Boundary decisions

| Boundary | Decision | Rationale |
|---|---|---|
| non-western/ vs. history/non-western/ | The existing survey files stay in history/non-western/ as orientation. The new depth files go in non-western/ (a peer of ethics/, phenomenology/, personal-identity/). | Survey-level history vs. substantive philosophical treatment. |
| non-western/ vs. personal-identity/ | Anattā appears in the Buddhist logic file as an epistemological position. The Buddhist challenge to personal identity is noted via cross-reference to Parfit, not duplicated in personal-identity/. | The philosophical context determines location: Buddhist logic is epistemology first, personal-identity implications second. |
| non-western/ vs. ethics/ | Confucian moral psychology is an ethics topic but housed in non-western/ because the primary interest is the tradition, not the Western ethical taxonomy. Cross-reference to virtue-ethics.md. | Tradition-first organization for coherence of the non-Western domain. |
| Depth selection | 4 Indian + 3 Chinese = 7 depth files. Indian philosophy gets one more because the diversity of schools (6 orthodox + 3 heterodox) creates more distinct philosophical positions requiring separate treatment. | Proportional to philosophical diversity, not cultural favoritism. |

## Target file list (7 files + synthesis)

### Phase 2: Indian Philosophy Depth (4 files)

1. **advaita-vedanta-shankara-nonduality.md**
   Śaṅkara's Advaita Vedānta (8th c. CE). Core positions: Brahman as the sole reality; ātman-Brahman identity; māyā as the power of appearance (not mere illusion but a lower ontological status); avidyā (ignorance) and adhyāsa (superimposition) as the mechanism of apparent multiplicity. Three levels of reality: pāramārthika (ultimate — only Brahman), vyāvahārika (conventional — the empirical world), prātibhāsika (illusory — dreams, errors). The two-truths doctrine. Post-Śaṅkara: Rāmānuja's Viśiṣṭādvaita (qualified non-dualism — Brahman has real attributes and real parts), Madhva's Dvaita (genuine dualism — souls are eternally distinct from Brahman). Relevance to consciousness debates: Advaita's claim that consciousness is fundamental (not emergent) maps onto current debates about IIT, panpsychism, and the hard problem. Cross-reference to emergence-consciousness-iit.md.

2. **buddhist-logic-dignaga-dharmakirti.md**
   The Buddhist epistemological tradition. Dignāga (5th c.): only two valid pramāṇas — perception (pratyakṣa: non-conceptual, momentary, causally grounded) and inference (anumāna: conceptual, based on logical relations). The apoha (exclusion) theory of meaning: concepts don't refer to positive universals (contra Nyāya realism) but to the exclusion of what they are not — "cow" means "not-non-cow." Dharmakīrti (7th c.) elaboration: the causal theory of perception (only real particulars cause perception), svabhāvahetu and kāryahetu (identity and causation as the two valid inferential relations), the three-aspect criterion (pakṣadharmatva, anvaya, vyatireka). Buddhist phenomenology: nirvikalpaka pratyakṣa (non-conceptual first-moment perception) vs. savikalpaka pratyakṣa (conceptual/constructed perception). Influence on later Tibetan logic (Tsongkhapa). Comparison with Nyāya: realism about universals vs. Buddhist nominalism; the cross-school debate that sharpened both epistemologies.

3. **nyaya-vaisheshika-epistemology.md**
   Nyāya epistemology: four pramāṇas — perception, inference, analogy (upamāna), testimony (śabda). The five-membered syllogism (pratijñā, hetu, udāharaṇa, upanaya, nigamana) vs. the Aristotelian three-membered syllogism. Vyāpti (invariable concomitance) and the problem of establishing universal relations from finite observations — the Indian problem of induction. Navya-Nyāya: Gaṅgeśa's formal metalanguage for analyzing inference and property-relations — arguably the most technically sophisticated logic before Frege. Vaiśeṣika ontology: seven categories (padārthas) including substance, quality, action, generality, particularity, inherence, absence. Atomic theory: eternal, partless atoms for each element. Udayana's proofs for God's existence (cosmological, teleological). The Nyāya-Buddhist debate: realism about universals (Nyāya) vs. nominalism (Buddhist apoha). Connection to Western analytic philosophy: Nyāya's concerns with inference, universals, and existence are directly comparable to Frege, Russell, and Quine.

4. **jain-epistemology-anekantavada.md**
   Jain doctrine of many-sidedness (anekāntavāda): all complex truths have multiple valid aspects; no single perspective captures the complete truth of a complex entity. Syādvāda (conditional predication): the saptabhaṅgī — seven possible predications about any proposition, each qualified by "syāt" (in some respect). Example: fire is hot from the perspective of its nature, not-hot from the perspective of its substrate (fuel is not inherently hot), both hot and not-hot from different aspects simultaneously, and so on through all seven. Nayavāda: partial standpoints (nayas) and rules for their legitimate use. Epistemological implications: formal fallibilism avant la lettre — every perspective is valid within its scope and invalid beyond it. The multiplicity of valid perspectives is not relativism (anything goes) but perspectival realism (each perspective captures a real aspect). Contemporary relevance: anekāntavāda as a model for handling semantic ambiguity, conflicting evidence, and multi-stakeholder disagreements. Connection to Bayesian reasoning (updating beliefs from partial perspectives).

### Phase 3: Chinese Philosophy Depth (3 files)

5. **confucian-moral-psychology-mencius-xunzi.md**
   The foundational debate in Confucian philosophy: is human nature good (Mencius) or bad (Xunzi)? Mencius (372–289 BCE): the four beginnings (sìduān) — compassion, shame, deference, right/wrong discrimination — as innate moral tendencies requiring cultivation. The well-case: anyone who sees a child about to fall into a well feels alarm and compassion, proving innate moral motivation. Moral development as cultivation of what is already present (agriculture metaphor). The political implication: the kingly way (wángdào) — governance through moral persuasion; the right of revolution. Xunzi (~310–220 BCE): human nature inclines toward profit, pleasure, and domination; unchecked nature produces conflict. Virtue is the transformation of nature through ritual (lǐ) — cultural achievement, not natural growth. The Kantian parallel: virtue as rational shaping of inclination. Synthesis: both agree on the importance of lǐ and moral education; they disagree on the starting point (is nature a seed to cultivate or raw material to shape?). Cross-reference to virtue-ethics.md for structural parallels with Aristotle.

6. **daoist-metaphysics-zhuangzi-wuwei.md**
   The Tao Te Ching: the Tao as the ineffable ground of being — not a substance, not a god, but the source and pattern of all things. Wu-wei (non-action/effortless action): acting in accordance with the natural flow rather than forcing outcomes. Not passivity but perfect responsiveness — the analogy of water (yields, flows around obstacles, yet carves canyons). Zhuangzi's philosophical contributions: radical perspectivism (the butterfly dream — am I a man who dreamed he was a butterfly, or a butterfly dreaming he's a man?); the relativity of all distinctions (right/wrong, large/small, life/death) from the perspective of the Tao; the Cook and the Ox parable as the paradigm of wu-wei and skilled embodied cognition. Comparison with: (a) Merleau-Ponty on skilled perception (the body as locus of skill, not the deliberative mind); (b) Dreyfus on expert performance (skill acquisition moves from rule-following to embodied responsiveness — wu-wei as the highest stage); (c) 4E cognition's rejection of Cartesian internalism. The process-ontological dimension: Tao as constant becoming, not static being — parallel to Whitehead's process philosophy and Bergson's durée.

7. **wang-yangming-unity-knowledge-action.md**
   Wang Yangming (1472–1529): the most radical Neo-Confucian. Core doctrine: the unity of knowledge and action (zhī xíng hé yī) — genuine knowledge is inseparable from action. If you truly know that filial piety is right, you act filially; if you don't act, you don't truly know. This collapses the Western distinction between theoretical and practical knowledge. Innate moral knowledge (liáng zhī): every person possesses innate knowledge of the good — not as propositional knowledge but as immediate moral perception. The extension of innate knowledge (zhì liáng zhī) as the complete moral program: remove the obscurations (selfish desires) that block innate knowledge, and right action follows naturally. Critique of Zhu Xi's "investigation of things" (gé wù): Wang Yangming argues that studying external things to accumulate knowledge is the wrong method — moral knowledge comes from within. The bamboo anecdote: Wang sat staring at bamboo for seven days trying to "investigate" it and became ill; he concluded that Zhu Xi's method was wrong. Relevance to philosophy of mind: Wang Yangming's position anticipates aspects of enactivism — knowledge is constituted by action, not merely applied to it. Cross-reference to 4E cognition and Dewey's pragmatism.

### Phase 4: Synthesis (1 file, requires approval)

8. **non-western-synthesis-cross-tradition.md**
   Capstone synthesis. Key themes: (a) epistemological diversity — Nyāya realism, Buddhist nominalism, Jain perspectivalism, and Daoist ineffability represent genuinely distinct epistemological frameworks, not minor variations on Western themes; (b) consciousness and non-dualism — Advaita's claim that consciousness is fundamental connects to IIT and the hard problem; Buddhist process philosophy connects to 4E and enactivism; (c) moral psychology — the Mencius/Xunzi debate (nature as seed vs. raw material) parallels and enriches the Aristotelian virtue ethics that dominates the existing ethics domain; (d) knowledge-action unity — Wang Yangming's position independently anticipated central claims of pragmatism and enactivism; (e) the synthesis is modestly comparative, not integrative — these are genuinely different traditions, and premature synthesis would erase the philosophical distinctiveness that makes them valuable. Updated SUMMARY.md and cross-references to existing philosophy domains.

## Cross-reference map

| New file | Cross-references to existing files |
|---|---|
| advaita-vedanta-shankara-nonduality | → emergence-consciousness-iit.md, philosophy-synthesis.md |
| buddhist-logic-dignaga-dharmakirti | → personal-identity/parfit-reductionism.md (anattā vs. reductionism) |
| nyaya-vaisheshika-epistemology | → history/non-western/indian-philosophy.md (survey context) |
| jain-epistemology-anekantavada | → buddhist-logic-dignaga-dharmakirti.md (inter-school debate) |
| confucian-moral-psychology-mencius-xunzi | → ethics/virtue-ethics.md (Aristotelian parallels) |
| daoist-metaphysics-zhuangzi-wuwei | → phenomenology/merleau-ponty-perception-as-skill.md, phenomenology/embedded-enacted-ecological-4e.md |
| wang-yangming-unity-knowledge-action | → phenomenology/embedded-enacted-ecological-4e.md (enactivism parallel) |
| non-western-synthesis-cross-tradition | → philosophy-synthesis.md, emergence-consciousness-iit.md, ethics/virtue-ethics.md, history/non-western/*.md |

## Duplicate coverage check

The three existing survey files provide orientation-level coverage. The new depth files go substantially beyond: each covers a single tradition or school in detail rather than surveying all traditions in one file. For example:
- indian-philosophy.md devotes ~200 words to Nyāya; the new nyaya-vaisheshika file will be 1000–1500 words on Nyāya epistemology alone.
- chinese-philosophy.md covers Mencius and Xunzi together in ~300 words; the new file gives each ~500-700 words plus their debate and comparative analysis.

Complementary, not duplicative. The survey files are prerequisites; the depth files are extensions.

## Formatting conventions

Per existing philosophy/ files:
- YAML frontmatter: `source`, `origin_session`, `created`, `trust`, `type`, `related`
- Markdown body: H1, H2, H3; use diacritical marks for non-English terms (Śaṅkara, not Shankara) with romanized parenthetical on first use
- Depth: 1000–1500 words per file; philosophically rigorous; cite primary texts and key scholars
- Include transliterated terms with translation (e.g., "anekāntavāda (many-sidedness)")
