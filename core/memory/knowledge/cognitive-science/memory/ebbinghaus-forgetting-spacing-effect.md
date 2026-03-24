---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
last_verified: '2026-03-20'
trust: medium
related: motivated-forgetting-retrieval-induced.md, ../metacognition/dunning-kruger-effect.md, ../../social-science/social-psychology/bystander-effect-diffusion-responsibility.md
---

# Ebbinghaus Forgetting Curves and the Spacing Effect

## Ebbinghaus (1885): The First Quantitative Study of Forgetting

Hermann Ebbinghaus, working alone as both experimenter and subject, produced the first systematic measurement of forgetting. Using lists of nonsense syllables (to eliminate meaningful associations), he memorized sets to criterion and then tested retention at various delays.

### The Forgetting Curve

Ebbinghaus found that retention decays rapidly at first, then slows:

$$R(t) = e^{-t/S}$$

where $R$ is retention (proportion recalled), $t$ is time since learning, and $S$ is a "stability" parameter reflecting how well the material was learned.

More precisely, modern formulations use a **power law** rather than pure exponential:

$$R(t) = a \cdot t^{-b}$$

where $a$ and $b$ are parameters fitted to data. The power law provides a better fit than exponential across a wide range of retention intervals (Wixted & Ebbesen, 1991).

### Quantitative findings

| Delay | Retention (Ebbinghaus) |
|-------|----------------------|
| 20 minutes | ~58% |
| 1 hour | ~44% |
| 9 hours | ~36% |
| 1 day | ~34% |
| 2 days | ~28% |
| 6 days | ~25% |
| 31 days | ~21% |

The steep initial drop and long slow tail are the signature: most forgetting happens soon after learning; what survives the first day tends to persist.

### Why forgetting curves matter

The forgetting curve is not merely descriptive — it constrains system design. Any memory system with temporal decay should follow an empirically validated decay function.

The Engram curation policy uses a 120-day time-based decay threshold for `_unverified/` files. Ebbinghaus's curves suggest this is conservative: if a file hasn't been accessed in the first 30 days, the probability of its being useful declines steeply. But the curves also show a long tail — a small fraction of information retains its value indefinitely. This argues for a two-stage approach: aggressive filtering in the first 30 days, but preservation of whatever passes that filter.

## The Spacing Effect

One of the most robust and practically important findings in all of memory research: **distributed practice produces better long-term retention than massed practice.**

### The finding

Studying material in multiple short sessions separated by time produces dramatically better long-term retention than studying the same material for the same total time in a single session.

**Example:** Studying vocabulary for 10 minutes on each of 4 days produces far better retention after a week than studying for 40 minutes on a single day.

### The expanding schedule advantage

Retention is optimized when review intervals **expand** over time: first review after 1 day, second after 3 days, third after 7 days, fourth after 21 days. This is the basis of spaced repetition systems (Anki, SuperMemo).

The mathematical principle: **review should occur at the point where the forgetting curve approaches threshold.** Too-early review wastes effort (the memory is still strong); too-late review requires re-learning (the memory has decayed below threshold). The optimal time is at the inflection point.

### Why spacing works: Two accounts

**The retrieval practice effect:** Retrieval itself strengthens memories. Each time you successfully retrieve information, the memory trace is strengthened — the "stability" parameter $S$ in the forgetting curve increases. Spaced practice forces more retrievals than massed practice (because time has passed and the memory has partially decayed, making retrieval effortful).

**The contextual variability account:** Studying in different sessions means studying in different internal and external contexts. Varied contexts produce a more robust, context-independent representation. Massed practice produces representations tightly bound to a single context.

### Desirable difficulties (Bjork, 1994)

The spacing effect is an instance of a broader principle: making learning harder in the short term often improves long-term retention. Other "desirable difficulties" include:
- **Interleaving:** Mixing practice of different skills rather than blocking (e.g., mixing math problem types rather than doing all of one type)
- **Testing effect:** Taking a test (retrieval practice) produces better retention than re-studying, even without feedback
- **Generation:** Generating an answer is better than reading an answer

The common mechanism: difficulty during learning signals that the current representation is inadequate, triggering deeper encoding.

## Agent Memory Implications

### Empirical validation of temporal decay

1. **The decay curve shape validates the curation policy.** Ebbinghaus's exponential/power-law decay means that the value of unretrieved information drops steeply in the first weeks and then flattens. A 120-day threshold is well into the tail — files that haven't been accessed in 120 days are very unlikely to be retrieved in the future. The memetic-security design spec (4.4) proposed a 30-day zero-access archival criterion, which is empirically supported as capturing most of the steep decay while avoiding premature archival of long-tail content.

2. **The decay function could be made empirical.** Rather than using a fixed threshold, the curation policy could use ACCESS.jsonl data to fit an actual forgetting curve for the Engram system — measuring the probability of future access as a function of time since last access. This would produce a data-driven threshold rather than an arbitrary one.

### The spacing effect argues for periodic review

3. **Retrieval strengthens memory.** The spacing/testing-effect literature says that retrieving information makes it more durable. For the agent: files that are periodically accessed are more likely to be accurate and useful than files that are written once and never revisited. This is a case for **scheduled review passes** — not because the file needs updating, but because the act of reviewing it strengthens the system's relationship with the content.

4. **Expanding review intervals.** An optimal review schedule for knowledge files would follow the spaced-repetition pattern: new files reviewed after 1 session, then 3 sessions, then 7, then 21, etc. High-access files naturally get this; low-access files do not. A curation improvement: identify files that have never been reviewed since creation and surface them for a single focused review at the 7-day mark.

5. **The desirable difficulty principle applies to knowledge curation.** Making retrieval harder (by not loading everything into context at session start) may produce deeper engagement with the content that is loaded. The compact SUMMARY approach — forcing the agent to work from summaries rather than full files — is a desirable difficulty that may improve the quality of integration.

## Key References

- Ebbinghaus, H. (1885/1913). *Memory: A Contribution to Experimental Psychology*. Trans. Ruger & Bussenius. Teachers College, Columbia University.
- Wixted, J.T., & Ebbesen, E.B. (1991). On the form of forgetting. *Psychological Science*, 2(6), 409–415.
- Cepeda, N.J., et al. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin*, 132(3), 354–380.
- Bjork, R.A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), *Metacognition: Knowing about Knowing* (pp. 185–205). MIT Press.
- Roediger, H.L., & Butler, A.C. (2011). The critical role of retrieval practice in long-term retention. *Trends in Cognitive Sciences*, 15(1), 20–27.
- Karpicke, J.D., & Roediger, H.L. (2008). The critical importance of retrieval for learning. *Science*, 319(5865), 966–968.