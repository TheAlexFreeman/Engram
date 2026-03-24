---
source: agent-generated
type: knowledge
created: 2026-03-19
trust: low
related:
  - later-wittgenstein-ordinary-language.md
  - philosophy-of-mind-language.md
  - ../nineteenth/pragmatism-schopenhauer.md
origin_session: unknown
---

# Analytic Foundations: Frege, Russell, Early Wittgenstein, and the Logical Positivists (1879–1950)

Analytic philosophy is the dominant tradition in academic philosophy in the English-speaking world and increasingly globally. Its origins lie in the technical revolutions in logic achieved by Frege and Russell at the turn of the 20th century, and in the philosophical programs built on those technical achievements — Russell's logical atomism, early Wittgenstein's picture theory of meaning, and the Vienna Circle's logical positivism. The tradition is defined less by a single doctrine than by a methodological commitment: careful analysis of language and argument, use of formal logic, and rejection of vague metaphysical speculation in favor of precise philosophical problems with, ideally, precise solutions.

---

## 1. Frege: Logic, Sense, and Reference

**Gottlob Frege** (1848–1925) is the founding figure of modern logic and of the analytic tradition's philosophy of language. His three technical achievements are among the most important in the history of thought:

### Quantificational Logic

Frege's *Begriffsschrift* ("Concept-Script," 1879) invents **modern quantificational logic** — the formal system in which propositions about all things and some things (quantifiers: ∀ and ∃), individual objects, properties, and relations can be expressed and analyzed with mathematical precision. This supersedes Aristotelian syllogistic (which had dominated logic for 2000 years) and makes possible the formalization of mathematical reasoning, the analysis of complex argument structure, the development of formal semantics, and ultimately the mathematical theory of computation.

Before Frege, logic was restricted to categorical propositions (all S are P, some S are P, etc.) and their combinations. Frege could express: "Every natural number has a successor" — a claim that requires nested quantification (for every number x, there exists a number y that is x's successor) that Aristotelian logic cannot formalize.

### The Sense/Reference Distinction

*On Sense and Reference* (*Über Sinn und Bedeutung*, 1892): the distinction between the **sense** (*Sinn*) and the **reference** (*Bedeutung*) of a linguistic expression.

Two expressions can have the **same reference** (pick out the same object) while having **different senses** (representing the object in different ways). Classic example: "the morning star" and "the evening star" both refer to Venus, but they express different senses — they present Venus under different descriptions (morning appearance vs. evening appearance). It was a genuine astronomical discovery that they are the same object; this would be trivially uninformative if sense and reference were the same.

The distinction explains:
- **Informativeness of identity statements**: "The morning star is the evening star" is informative because the senses differ even though the references are the same.
- **Propositional attitude contexts**: "John believes the morning star is bright" can be true while "John believes the evening star is bright" is false, even though morning star = evening star. In belief contexts, we substitute sense, not just reference.
- **Empty names**: "Sherlock Holmes is a detective" seems meaningful despite Holmes not existing. Sense is present (Holmes is the fictional detective created by Conan Doyle) even though reference is absent.

These distinctions generate the central problems of 20th-century philosophy of language: how do names refer? (Frege: via sense/description; Kripke: directly, as rigid designators) — and the implications for the philosophy of mind (what do we believe *about* when we have propositional attitudes?).

### The Context Principle

*The Foundations of Arithmetic* (1884): "Never ask for the meaning of a word in isolation, but only in the context of a proposition." The meaning of a word is its contribution to the truth-conditions of sentences in which it appears, not an image or idea "in the mind." This is the first statement of the context principle — the claim that the unit of meaning is the sentence, not the word — which will be central to Frege, Russell, and later Wittgenstein and Quine.

---

## 2. Russell: Logical Atomism and the Theory of Descriptions

**Bertrand Russell** (1872–1970) transformed analytic philosophy through both his technical work (the theory of types, *Principia Mathematica*) and his philosophical programs (logical atomism, the theory of descriptions). He is also the founder of the Anglo-American liberal public intellectual tradition — active in political, ethical, and social commentary throughout his very long life.

### The Theory of Descriptions

The most celebrated single philosophical technique in analytic philosophy: *On Denoting* (1905). The problem: "The present King of France is bald" seems to presuppose that there is a present King of France, but France is a republic. The sentence is neither true (there is no King) nor false in the way "The present King of France has brown hair" would be false if he had black hair. What is the logical form?

Russell's analysis: "The present King of France is bald" is not a simple predication of the form "a is F" (where a is an individual). Its **logical form** is:
"There exists exactly one thing that is presently King of France, and that thing is bald" — which is straightforwardly **false** (there is no such thing).

The definite description ("the present King of France") is an **incomplete symbol** — it looks like a name (a referring expression) but is actually a disguised quantified claim. It has no reference as an expression in isolation; it acquires meaning only in the context of a sentence (Frege's context principle applied).

This technique — **logical analysis** to reveal the true logical form of sentences that mislead us through surface grammar — became the paradigmatic method of analytic philosophy. The idea: philosophical puzzles often arise from mistaking surface grammatical form for logical form; careful analysis dissolves the puzzles.

### Logical Atomism

Russell's metaphysical program (ca. 1918): the world consists of **logical atoms** — simple particulars with simple properties — and **molecular facts** built up from atomic facts by logical operations. Language ideally has the same structure as the world: atomic propositions correspond to atomic facts; molecular propositions are truth-functional combinations.

This program requires a **logically perfect language** — one in which each symbol has a definite reference, no symbol is ambiguous, and the logical form of every proposition is perspicuous. This ideal language is the goal of logical analysis: to replace the vague, ambiguous, grammatically misleading natural language with a precise logical language.

The picture: meaning is constituted by a direct acquaintance relation between the mind and simple entities (sense-data for empirical knowledge, universals for logical knowledge). Russell is the empiricist foundationalist within the analytic tradition — building on direct acquaintance as the incorrigible given.

### Principia Mathematica

With **Alfred North Whitehead** (1861–1947): *Principia Mathematica* (1910–1913) — the attempt to derive all of mathematics from purely logical axioms. This is Frege's **logicist** program (arithmetic is logic applied to abstract objects) reconstructed after Frege's own system was shown to be inconsistent (Russell's Paradox — the set of all sets that don't contain themselves leads to contradiction). Russell's type theory blocks the paradox by sorting entities into a hierarchy of types.

**Gödel's incompleteness theorems** (1931) definitively end the logicist dream: any consistent formal system rich enough to express arithmetic is either incomplete (there are true arithmetic statements that can't be proved in the system) or inconsistent. Mathematics cannot be reduced to logic without remainder; and no formal system can prove its own consistency from within.

---

## 3. Early Wittgenstein: The Tractatus

**Ludwig Wittgenstein** (1889–1951) is the most influential philosopher of the 20th century in the analytic tradition — and probably the most original. He published two works in his lifetime that are so different from each other that they appear to contradict each other: the *Tractatus Logico-Philosophicus* (1921) and *Philosophical Investigations* (1953, posthumous). Both are seminal.

### The Picture Theory of Meaning

The *Tractatus* (full title: *Logisch-philosophische Abhandlung*) presents a theory of language, logic, and the world in aphoristic numbered propositions. The core:

**The world is the totality of facts** (states of affairs that obtain), not things. **Language pictures the world** — a proposition has meaning by sharing a **logical form** with a possible fact; the elements of the proposition stand for elements of reality, and the arrangement of elements in the proposition mirrors (pictures) the arrangement of facts.

The **picturing relation**: a map pictures terrain not by looking like the terrain but by having an isomorphic structure — elements of the map stand for elements of the terrain, and the spatial relations among map-elements represent the spatial relations among terrain-elements. A proposition pictures a possible fact in the same way. A proposition is a model of reality as we imagine it.

The logical structure shared by a proposition and what it pictures — the **logical form** — cannot itself be said; it is shown. This is the critical distinction: what *can* be said are the results of picturing (propositions about facts); what *cannot* be said but only *shown* are the logical scaffolding itself (logical constants, the form of all possible representation), the *limits* of language, and all that lies beyond those limits — ethics, aesthetics, the metaphysical subject, the mystical.

### Whereof One Cannot Speak

The *Tractatus*'s most famous sentence: "What we cannot speak about we must pass over in silence" (7). The subjects passed over in silence include: ethics (there are no ethical facts; ethical sentences are neither true nor false, hence not genuine propositions), aesthetics (the same), the self as metaphysical entity, God, and the meaning of life. These are not answered by the *Tractatus*; they are placed outside the domain of what can be said.

But this is not dismissal: the *Tractatus* says that these things "make themselves manifest" — they are *shown* rather than said. The mystical (*das Mystische*) — the sense that the world *is* — is what shows itself, though it cannot be put into words.

The remarkable final gambit: the propositions of the *Tractatus* itself are **nonsense** (*unsinnig*) — since they try to say what can only be shown (logical form, the limits of language). The reader who has understood the *Tractatus* will recognize this and use it as a ladder to be kicked away. The book dissolves itself.

---

## 4. Logical Positivism: The Vienna Circle

The **Vienna Circle** (Wiener Kreis, active 1920s–1930s) was a discussion group at the University of Vienna including **Moritz Schlick**, **Rudolf Carnap**, **Otto Neurath**, **Friedrich Waismann**, and (from a distance) **A.J. Ayer** in London. They were inspired by Mach's empiricism, Frege and Russell's logic, and early Wittgenstein, and they developed **logical positivism** — the most systematic attempt to apply the tools of modern logic to the project of scientific philosophy.

### The Verification Principle

The logical positivists' central doctrine: a statement is **cognitively meaningful** (capable of being true or false) if and only if it is either:
- **Analytically true** (true by logic and definition: all bachelors are unmarried) or
- **Empirically verifiable** (there is some possible observation that would bear on its truth or falsity)

Any statement that satisfies neither condition is **meaningless** as a cognitive claim — not false, but literally without truth-value. Category of the meaningless: traditional metaphysics ("the Absolute is the ground of all Being"), theology ("God is omnipotent and omniscient"), ethics as traditionally construed.

This is a more radical version of Hume's fork (relations of ideas / matters of fact) and of the pragmatic maxim (meaning = practical consequence). The logical positivists saw themselves as completing the Enlightenment program of rational criticism — eliminating pseudo-problems by exposing their linguistic vacuity.

### The Unified Science Program

Neurath, Carnap, and others pursued the **unified science** program: all genuine scientific knowledge would ultimately be expressible in a single formal language, with physics as the base and all other sciences in principle reducible to it. The *International Encyclopedia of Unified Science* was intended to realize this — ironically, Kuhn's *Structure of Scientific Revolutions* (1962) appeared in this encyclopedia and helped to demolish the foundationalist philosophy of science it was meant to exemplify.

### Carnap's Aufbau

Carnap's *Logical Structure of the World* (*Aufbau*, 1928) was the most ambitious logical positivist construction: a rational reconstruction of all empirical knowledge from a phenomenal base (classes of elementary experiences) using the tools of modern logic. The project is Kantian in ambition (determine the conditions of all possible knowledge) but empiricist in execution (the base is phenomenal, not transcendental).

---

## 5. Quine and the Demolition of Logical Positivism

**Willard Van Orman Quine** (1908–2000): "Two Dogmas of Empiricism" (1951) is the paper that destroyed logical positivism as a viable program — from within the analytic tradition.

The two dogmas:
1. **The analytic/synthetic distinction**: the positivists distinguish sharply between analytic truths (true by meaning, verifiable by logic alone) and synthetic truths (requiring empirical verification). Quine argues there is no principled way to draw this distinction. What makes "all bachelors are unmarried" analytic? Because "bachelor" means "unmarried male." But "synonymy" (same meaning) has no non-circular definition; the notion of analyticity is not philosophically grounded.

2. **Reductionism**: each meaningful statement, taken individually, has a range of confirming/disconfirming experiences. Quine argues against this: statements face experience not individually but as a corporate body — the **Duhem-Quine thesis**. When an observation conflicts with a theory, we can revise the theory anywhere — at the observation, at auxiliary assumptions, at the theory's core. There is no unique "empirical meaning" for a given statement in isolation.

Quine's positive view: **holism** — the web of belief faces experience as a whole. Logic, mathematics, and physics all belong to the same web; none is more "analytic" or immune to revision than any other. The difference between logic and empirical science is a difference in degree of entrenchment, not in kind. And at the periphery: **naturalism** — epistemology should be continuous with natural science (psychology, linguistics) rather than aspiring to a priori foundations.

---

## Four Through-Lines

### Mind, knowledge, and world

The analytic tradition transformed epistemology by making **language** its central focus: the question of knowledge became the question of what sentences mean and when they are true. Frege's sense/reference distinction, Russell's theory of descriptions, and Wittgenstein's picture theory all address the question of how language hooks onto the world.

The epistemological crisis of logical positivism (Quine's demolition) cleared the way for the pragmatist turn in epistemology: knowledge as a coherent web of beliefs shaped by experience (holism), rather than a foundationalist structure built on incorrigible sense-data. Quine's naturalized epistemology and Sellars's critique of the "myth of the given" define the post-positivist analytic epistemology.

### Language and meaning

The analytic tradition's core is a philosophy of language. Frege's sense/reference distinction, Russell's theory of descriptions, Wittgenstein's picture theory, Carnap's formal languages, and Quine's holism all address the central problems: what is the relationship between language and world? What makes a sentence meaningful? What is it for words to refer to things?

The result: the **semantic turn** — the recognition that philosophical problems (about mind, knowledge, ethics, metaphysics) are in large part problems about language and can be addressed through careful attention to how language works. This becomes the dominant methodology of the analytic tradition: philosophical analysis as linguistic analysis.

### Ethics, politics, and the self

Logical positivism's treatment of ethics is the most controversial aspect of the movement. If ethical sentences are empirically unverifiable and not analytically true, they are meaningless as cognitive claims. **Emotivism** (Ayer's *Language, Truth and Logic*, 1936): ethical statements express emotions and prescribe behavior, but do not describe facts. "Murder is wrong" analyzed as "Boo! murder" — an expression of attitude, not a cognitive claim. This seems to make ethics merely subjective and undermines the possibility of rational moral discourse.

Later non-cognitivist positions (Hare's prescriptivism, Gibbard's expressivism, Blackburn's quasi-realism) attempt to develop the emotivist core more rigorously and preserve the normative force of moral discourse. The debate between cognitivism (moral judgments are true or false) and non-cognitivism (they are not) is one of the organizing debates of 20th-century metaethics.

### Science, metaphysics, and religion

Logical positivism is the most aggressive form of scientism in the history of philosophy: all genuine knowledge is scientific knowledge; all other claims are either analytic or meaningless. The history of metaphysics is a history of confusion; theology is unintelligible.

This position is itself philosophically refuted (the verification criterion doesn't verify itself) and practically undercut by the development of the philosophy of science (Kuhn's paradigms, Lakatos's research programs, Feyerabend's "anything goes") which shows that science is not the clean induction machine that logical empiricism assumed. The post-positivist philosophy of science is much more modest about what science achieves and how it achieves it.

But the core aspiration — that philosophy should be rigorous, its problems clearly formulated, and its claims subject to intersubjective scrutiny — remains the methodological commitment of the analytic tradition and accounts for much of its productivity and self-criticism.

---

## The Arc Forward

The technical achievements of Frege, Russell, and early Wittgenstein generate:
- **Model-theoretic semantics** (Tarski, Carnap, Montague): formal truth-definition for artificial and natural languages — the foundation of formal semantics in linguistics.
- **Modal logic** (Lewis, Kripke): the semantics of necessity and possibility using possible worlds — the framework of Kripke's *Naming and Necessity*.
- **Philosophy of language** (Grice, Quine, Kripke, Putnam, Davidson): the post-positivist analytic tradition's central domain.
- **Computational theory and AI**: Turing's formalization of computation emerges directly from the logicist tradition (Gödel, Church, Turing) — the question of what can be formally computed is the question of what can be derived from logical axioms, transformed into a question about machines.

The destruction of logical positivism (Quine, Goodman, later Wittgenstein, Austin) clears the way for:
- A richer account of natural language (Gricean implicature, speech act theory, formal pragmatics)
- A more scientifically informed philosophy of mind and language
- A revival of metaphysics (possible worlds, essentialism, naturalistically-minded ontology)
