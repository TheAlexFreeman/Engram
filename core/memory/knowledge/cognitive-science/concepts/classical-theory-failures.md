---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: prototype-theory-rosch.md, theory-theory-knowledge-based-view.md, exemplar-theory-hybrid-models.md
---

# The Classical Theory of Concepts and Its Failures

## The Classical View

The classical (also: definitional, Aristotelian) theory of concepts holds that:

1. Every concept is defined by a set of **necessary and sufficient conditions** — features that every member of the category must have (necessary) and that together guarantee membership (sufficient).
2. **Membership is all-or-nothing**: something either satisfies the conditions or it doesn't; there are no degrees of membership.
3. **All instances are equal**: once membership is established, no instance is "a better example" than another.
4. **The definition is known** (implicitly or explicitly) to competent concept users — having the concept entails knowing the defining conditions.

**Domain of success:** Mathematical concepts fit the classical view well. *Triangle* is defined by: a closed plane figure with exactly three straight sides and three interior angles summing to 180°. Every triangle satisfies these conditions; nothing that satisfies them is not a triangle; no triangle is "more triangular" than another; membership is all-or-nothing.

The classical view was the dominant account of concepts in philosophy and psychology through most of the 20th century, implicitly assumed in formal logic, set theory, and early AI (where concepts were treated as feature lists with Boolean membership).

---

## Wittgenstein's Family Resemblance

Ludwig Wittgenstein (*Philosophical Investigations*, 1953) challenged the classical view through the concept of **family resemblance**.

**The example: "game"**

Wittgenstein asked: what do all games have in common? Attempt to specify:
- Card games (Solitaire, Poker) — but board games have no cards
- Board games (Chess, Checkers) — but ring-around-the-rosy is not on a board
- Competitive games (chess, football) — but solitaire has no opponent
- Games with winners and losers — but ring-around-the-rosy has none
- Games involving skill — but games of chance don't require skill
- Games involving amusement — but chess players may not be amused

No single feature runs through all games. But there are **overlapping, criss-crossing similarities**: Poker shares features with Bridge; Bridge shares features with Chess; Chess shares features with ring-around-the-rosy (loosely); ring-around-the-rosy shares features with other children's games. Like family resemblance — a family where members share same reddish nose, but not all; same build, but not all; same eyes, but not all — the resemblance crisscrosses without any single feature being universal.

**Wittgenstein's conclusion:** Many everyday concepts cannot be defined by necessary and sufficient conditions. The conceptual boundary is indeterminate and context-sensitive. This is not a defect of these concepts to be remedied — it is their natural structure. The demand for a definition is a philosophical craving that reality does not satisfy.

**Implication:** The classical theory works for formal/mathematical concepts but fails as a general theory of ordinary concepts.

---

## Putnam's Natural Kinds

Hilary Putnam (*"The Meaning of 'Meaning'"*, 1975) attacked the classical view from a different angle: the **natural kind argument**.

**The scenario:** Suppose there is a planet "Twin Earth" exactly like Earth except that what they call "water" is chemically XYZ (not H₂O) — it looks, tastes, and behaves just like water, but is a fundamentally different substance.

In 1750, before the discovery of chemical composition, an Earthling and a Twin-Earthling who both call their local liquid "water" have identical psychological states — the same mental representation, by every criterion. Yet their words mean different things: Earth "water" refers to H₂O, Twin Earth "water" refers to XYZ.

**Putnam's conclusion:** Meaning is not "in the head." The reference of natural kind terms like "water," "gold," "tiger" is fixed by the **actual nature of the substance in the world**, not by the mental concepts users associate with the word. Experts (chemists, biologists) determine the extension of natural kind terms — ordinary users defer to expert extension.

**Challenge to the classical view:**
- Users of "water" do not know H₂O is necessary (pre-Lavoisier, no one did) — yet they correctly used the term.
- The necessary and sufficient conditions are not known by ordinary concept users — they are determined by the world and expert investigation.
- The classical view's assumption that concept definition is mentally represented by competent users is systematically false for natural kinds.

**Consequence:** Natural kind concepts (substances, biological species, natural phenomena) have their extensions determined externally and may resist complete definition by any finite set of features available to ordinary users.

---

## Waismann's Open Texture

Friedrich Waismann introduced **open texture** (Offenheit/Porösität) to describe the essential incompleteness of empirical concepts:

Any empirical concept has borderline cases that weren't anticipated when the concept was formed and that the existing concept specification does not clearly resolve.

**Example:** "Cat" — we know what cats normally are. But suppose:
- An animal is discovered with catlike appearance but alien biology — is it a cat?
- A robot is constructed that perfectly simulates cat behavior — is it a cat?
- A cat is discovered that lacks the usual feline genome — is it still a cat?

For none of these cases does the existing concept "cat" provide a definitive verdict. This is not a gap to be filled — new empirical discoveries always have the potential to generate new borderline cases that current conceptual specifications don't cover. Empirical concepts are inherently open to revision by novel cases.

**Contrast with mathematics:** Mathematical concepts are not open-textured. "Triangle" does not become unclear upon discovery of a new geometric figure. Open texture is a feature of concepts that refer to contingent, empirically discoverable things.

---

## Implications for Knowledge Base Organization

The classical view implicitly governs the knowledge base's folder structure: `philosophy/`, `cognitive-science/`, `mathematics/` function as classical categories with implied necessary and sufficient membership conditions.

But Wittgenstein predicts:
- **Borderline files:** There will be files that resist clean categorization — a file on conceptual spaces (cognitive science? philosophy? mathematics?) may have family resemblance to all three without clear necessary conditions for any.
- **Family resemblance organization:** The knowledge base's cross-references are more like family resemblance links than classical category memberships — files are related by overlapping topic clusters, not by strict hierarchy.

Putnam predicts:
- **Natural kind knowledge is expert-indexed:** Files about natural kinds (biological, chemical, physical phenomena) should be treated as potentially requiring expert-determined correct extension. The agent's "internal representation" of what "water" or "protein" refers to may be wrong in ways the agent cannot detect.

Open texture predicts:
- **Conceptual revision under novel input:** Knowledge files represent the current specification of a concept, but novel evidence or perspectives may generate cases that the existing specifications don't resolve. Files should be revisable, not fixed.

The appropriate design response: embrace the Wittgensteinian insight that the folder structure is a convenience, not a classification truth. Cross-references are primary; folder membership is secondary. Files should be tagged with multiple relevant clusters, not assigned exclusively to one.
