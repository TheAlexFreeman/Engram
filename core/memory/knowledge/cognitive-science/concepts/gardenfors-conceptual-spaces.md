---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-004
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related:
  - memory/knowledge/cognitive-science/concepts/structural-alignment-analogy.md
  - memory/knowledge/cognitive-science/concepts/conceptual-hygiene-interdisciplinary.md
  - memory/knowledge/cognitive-science/concepts/prototype-theory-rosch.md
  - memory/knowledge/cognitive-science/concepts/classical-theory-failures.md
  - memory/knowledge/cognitive-science/concepts/concepts-synthesis-agent-implications.md
---

# Gärdenfors' Conceptual Spaces

## Motivation: A Geometry of Meaning

Peter Gärdenfors (2000, *Conceptual Spaces: The Geometry of Thought*) proposed a representational level between the symbolic and the sub-symbolic:

| Level | Examples | Pros | Cons |
|-------|----------|------|------|
| **Symbolic** | Predicate logic, semantic networks, frames | Compositionality, rule-following, explanation | Grounding problem, brittleness, no similarity metric |
| **Sub-symbolic** | Neural networks, connectionist models | Learning, graceful degradation, similarity | Hard to interpret, poor compositionality |
| **Conceptual spaces** | Geometric quality dimensions | Both similarity and compositionality, grounded in perception | Intermediate representation, not a complete theory of language |

The conceptual spaces framework occupies the meso-level: it is **geometric, not symbolic**, but it has structure that admits of rational interpretation and linguistic mapping.

---

## Quality Dimensions and Conceptual Spaces

**Quality dimensions** are the fundamental axes of psychological space. They correspond to measurable or perceivable properties of objects:

**Perceptual quality dimensions:**
- **Hue/saturation/brightness** — the three dimensions of colour space (or hue-chroma-value in HSV)
- **Pitch/loudness/timbre** — dimensions of the auditory space
- **Warmth/temperature** — thermal dimension
- **Weight** — gravitational force dimension

**Derived quality dimensions:**
- **Size** (derived from object-relative spatial dimensions)
- **Age** (temporal property of organisms)
- **Speed** (derived: distance/time)

**Cognitive/social quality dimensions:**
- **Valence/arousal** — the two primary dimensions of the emotion space (Russell, 1980)
- **Dominance/submission** — social dimensions
- **Similarity/difference** — a meta-level dimension

**Conceptual spaces** are built from collections of quality dimensions. The **colour space** (hue × saturation × brightness), the **flavour space** (sweet × sour × salty × bitter × umami), and the **emotion space** (valence × arousal) are examples of conceptual spaces, each formed from a set of quality dimensions.

---

## Concept Representation via Convex Regions

**The convexity constraint:** Gärdenfors' central claim is that natural concepts correspond to **convex regions** in the relevant quality dimensions:

> A region $R$ in a conceptual space is **convex** if, for any two points $x, y \in R$, every point on the line segment between $x$ and $y$ is also in $R$.

**Why convexity matters:**

Non-convex concepts would involve cases like: "x is a cat, y is a cat, but the average of x and y is not a cat." Psychologically, if you find a creature that has some properties between two known cats, you should call it a cat. Convexity captures this.

Many weird counter-examples can be constructed, but Gärdenfors argues that natural, stable, evolved categories are approximately convex. Non-convex categories tend to be either:
- **Disjunctive artificial categories** (defined by enumeration, not properties)
- **Polysemous words** (one word form, multiple non-overlapping conceptual regions — e.g., "bank" splits into two separate convex regions: financial institution and riverside)

**Prototype as centroid:** Within the convex region, the **prototype** of a concept is its centroid (geometric centre). Typicality of an item corresponds to how close it is to the centroid.

- **High typicality** = closer to centroid (central robin in BIRD)
- **Low typicality** = closer to the boundary of the convex region (penguin in BIRD — at the edge, barely inside)

This provides a geometric interpretation of Rosch's prototype effects (see `prototype-theory-rosch.md`) that is more principled than the "summary statistic" prototype.

---

## Similarity as Inverse Distance

In conceptual space geometry, **similarity is inverse of distance:**

$$\text{sim}(x, y) = f(d(x, y))$$

where $f$ is some monotonically decreasing function and $d$ is the distance in the quality dimension space (typically weighted Minkowski distance).

This directly grounds:
- **Typicality effects:** Typical items are close to the centroid, therefore similar to many other category members.
- **Family resemblance:** Items that are similar to many other members in the space (not to a single prototype per se) are perceived as connected.
- **Category boundaries:** The boundary between two categories is the locus of equal distance to the two centroids — a Voronoi partition of conceptual space.

**Voronoi tessellations:** If concepts are represented as centroids (prototypes), the natural categorization of any arbitrary point in the space is determined by which centroid it is closest to. This produces a **Voronoi tessellation** of the conceptual space — an exhaustive, mutually exclusive partition into regions, each belonging to one concept. This has been validated empirically for colour categories across languages (Regier et al., 2007).

---

## Properties vs. Object Concepts

Gärdenfors distinguishes **property concepts** from **object concepts:**

**Property concepts** are *domains* in conceptual space — they apply along one or more dimensions. "Red" applies in colour space; "heavy" applies in weight dimension; "loud" applies in loudness dimension.

**Object concepts** are regions across multiple domains simultaneously. "Apple" is a region in:
- Colour space (red-green-yellow range)
- Shape space (roundish)
- Taste space (sweet-tart)
- Texture space (firm-crisp)
- Size space (fist-sized)

Object concepts integrate across multiple quality dimension domains. This integration across domains corresponds to the **prototype vector** for the object concept — a multi-domain centroid.

**Metaphor as domain mapping:** Lakoff and Johnson's conceptual metaphors (e.g., "argument is war") are, in Gärdenfors' framework, *structure-preserving mappings between domains*. The geometry of the "war" domain (attack/defense, territory, victory/defeat) is projected onto the "argument" domain. This connects conceptual spaces theory to the structural alignment theory of analogy (see `structural-alignment-analogy.md`).

---

## LLM Embedding Spaces as Approximate Conceptual Spaces

Modern LLMs use high-dimensional embedding spaces (often 768-4096 dimensions or more) in which:
- Words and phrases are represented as vectors
- Semantic similarity correlates with cosine distance
- Analogical relations show parallelogram structure (king - man + woman ≈ queen)

**Gärdenfors' framework as interpretive lens for LLM embeddings:**

| Conceptual Spaces Concept | LLM Embedding Analog |
|--------------------------|---------------------|
| Quality dimensions | Principal components of embedding space |
| Convex region (concept) | Cluster in embedding space |
| Centroid (prototype) | Mean embedding of category tokens |
| Similarity = inverse distance | Cosine similarity |
| Voronoi tessellation | Nearest-centroid classification |
| Property concept | Direction in embedding space |

**Caveats:**
- LLM embedding spaces are not psychologically grounded — dimensions are purely statistical patterns from text co-occurrence, not perceptual quality dimensions.
- Convexity may not hold for all concepts in LLM embedding space — adversarial examples can exploit non-convexities.
- The dimension structure is opaque and not interpretable the way quality dimensions are (brightness, hue, etc.).

Despite these caveats, Gärdenfors' framework provides the most principled geometric interpretation of what LLM embeddings are doing at the conceptual level.

---

## Agent Implications

**Knowledge file distances as conceptual distances:** If knowledge files are embedded and retrieved by semantic similarity, the structure of the knowledge base forms an implicit conceptual space. Files that cluster together in retrieval-embedding space are implicitly forming conceptual categories.

**Cross-reference density as conceptual distance proxy:** Files that cross-reference each other frequently are conceptually close in the knowledge-space sense. Tracking cross-reference network topology provides a rough proxy for conceptual space structure.

**Convexity as a guide for partitioning:** When creating subfolders (e.g., `cognitive-science/concepts/` vs. `cognitive-science/attention/`), the convexity intuition applies: each folder should correspond to a topically convex region such that any file "between" two files in the folder also belongs in that folder, not some other folder.
