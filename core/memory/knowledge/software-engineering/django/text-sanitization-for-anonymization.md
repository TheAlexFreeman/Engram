---
source: agent-generated
type: knowledge
created: 2026-04-14
last_verified: 2026-04-14
trust: low
related:
  - k-anonymity-and-threshold-aggregation.md
  - ../../software-engineering/django/django-security.md
  - ../../software-engineering/ai-engineering/prompt-engineering-for-code.md
origin_session: memory/activity/2026/04/14/chat-002
---

# Text Sanitization for Anonymization

Free-text fields attached to verified reviews or records are the hardest part of a privacy pipeline. Scores and flags are easy to aggregate; prose carries both intentional signal ("the AD screamed on day 4") and incidental signal ("I was holding sticks for the 35mm B-cam"). Sanitization tries to keep the first while removing the second. This note covers the threat model, the pipeline shape, the libraries to reach for, and the review workflow that catches what automation misses.

---

## 1. Threat model: three layers

### Direct identifiers

Names, emails, phone numbers, addresses, government IDs. These are the easy layer. Regex and named-entity recognition (NER) do most of the work; missed matches are mostly costless to find in review.

### Quasi-identifiers

Role (1st AD, DP, key grip), department, dates worked, production location, union local number, specific equipment or trailer references. Any of these, in combination with background knowledge, narrows the author. This is where most sanitization work lives.

### Stylometric attribution

Writing style — word choice, sentence length distribution, punctuation habits, characteristic misspellings — identifies authors surprisingly well. The Enron corpus and various deanonymization papers show authorship classifiers reaching 70–80%+ accuracy on moderately long prose even with direct identifiers stripped.

For Rate My Set specifically: a production's cast and crew is a small known population. A stylometric classifier trained on a few examples of each crew member's writing (from social media, IMDb profiles, trade press interviews) could plausibly attribute a review to its author. This is the strongest threat in the model and the hardest to defend against with regex alone.

---

## 2. Pipeline shape

A sanitization pipeline should compose in a predictable order, with each stage reducing surface without needing state from a later stage:

```
raw_text
  → stage 1: normalize (unicode NFC, whitespace, casing hints)
  → stage 2: regex strip (emails, phones, URLs, dates, times, production-specific tokens)
  → stage 3: NER strip (PERSON, ORG, GPE, DATE, TIME, MONEY entities)
  → stage 4: domain strip (role/department terms, equipment tokens, trailer numbers)
  → stage 5: LLM paraphrase (stylometric defense; optional, flag-gated)
  → stage 6: human review (moderator approves or edits)
  → sanitized_text
```

Each stage should be auditable: record what was removed, at what offset, by which stage. This supports moderator review and lets you tune stages based on false-positive/false-negative examples.

```python
# productions/ops/sanitize.py
@dataclass
class SanitizationResult:
    input_text: str
    output_text: str
    stages: list["StageResult"]  # per-stage diff and removed tokens
    needs_review: bool           # true if any stage flagged low confidence


@dataclass
class StageResult:
    name: str
    removed: list[tuple[int, int, str]]  # (start, end, category) on the pre-stage text
    notes: str = ""


def sanitize(text: str) -> SanitizationResult:
    stages = []
    current = normalize_unicode(text)

    current, removed = strip_regex_pii(current)
    stages.append(StageResult("regex_pii", removed))

    current, removed = strip_named_entities(current)
    stages.append(StageResult("ner", removed))

    current, removed = strip_domain_tokens(current)
    stages.append(StageResult("domain_terms", removed))

    # LLM paraphrase is opt-in via feature flag
    if settings.SANITIZATION_LLM_ENABLED:
        paraphrased, notes = paraphrase_for_stylometry(current)
        stages.append(StageResult("llm_paraphrase", [], notes=notes))
        current = paraphrased

    needs_review = any(s.removed or s.notes for s in stages)
    return SanitizationResult(text, current, stages, needs_review)
```

---

## 3. Stage 1: regex strip

Regex is fast, predictable, and good at structured identifiers. It's bad at anything positional or semantic. Keep regex patterns in one module, with tests for each.

```python
import re

PATTERNS = [
    # Emails
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    # US phone numbers (broad)
    (re.compile(r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"), "[PHONE]"),
    # URLs
    (re.compile(r"https?://\S+"), "[URL]"),
    # @handles (Twitter, Instagram)
    (re.compile(r"(?<![\w@])@[A-Za-z0-9_]{2,}"), "[HANDLE]"),
    # Dates: explicit and relative
    (re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?\b"), "[DATE]"),
    (re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"), "[DATE]"),
    # Call times and set times
    (re.compile(r"\b(?:1[0-2]|0?[1-9])(?::[0-5]\d)?\s?(?:AM|PM|am|pm)\b"), "[TIME]"),
    (re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b"), "[TIME]"),
    # Addresses (street-number-like)
    (re.compile(r"\b\d{2,5}\s+[A-Z][A-Za-z]+\s+(?:St|Ave|Blvd|Rd|Dr|Way|Pl|Ln)\b\.?"), "[ADDRESS]"),
    # SSN-like (US)
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Production-coded IDs and trailer numbers
    (re.compile(r"\btrailer\s*#?\s*\d+\b", re.I), "[TRAILER]"),
    (re.compile(r"\bstage\s*#?\s*\d+\b", re.I), "[STAGE]"),
]


def strip_regex_pii(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    removed = []
    offset = 0
    for pattern, placeholder in PATTERNS:
        def repl(match):
            nonlocal offset
            start = match.start() + offset
            removed.append((start, start + len(match.group()), placeholder))
            return placeholder
        text = pattern.sub(repl, text)
    return text, removed
```

Known failure modes: phone number regexes catch flight numbers and invoice IDs; date regexes drop "4th of July" and other non-numeric dates; URL regexes miss markdown-wrapped links. Build up the test corpus as you see real review text.

---

## 4. Stage 2: named-entity recognition

spaCy's NER is the standard starting point. It catches PERSON, ORG, GPE (countries/states/cities), DATE, TIME, MONEY, FACILITY out of the box. Fast enough to run inline on submission.

```python
# pip install "spacy>=3.7"
# python -m spacy download en_core_web_lg   (or _trf for best accuracy, heavier)

import spacy

_NLP = spacy.load("en_core_web_lg")
_STRIP_LABELS = {"PERSON", "ORG", "GPE", "FAC", "LOC", "DATE", "TIME", "MONEY"}


def strip_named_entities(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    doc = _NLP(text)
    # Walk entities in reverse so offsets don't shift during replacement
    out = text
    removed = []
    for ent in sorted(doc.ents, key=lambda e: -e.start_char):
        if ent.label_ in _STRIP_LABELS:
            placeholder = f"[{ent.label_}]"
            out = out[: ent.start_char] + placeholder + out[ent.end_char :]
            removed.append((ent.start_char, ent.end_char, placeholder))
    return out, list(reversed(removed))
```

Accuracy notes:

- `en_core_web_lg` is a good default; `en_core_web_trf` is slower but noticeably better at coreference and rare names.
- NER models are trained on news corpora; industry slang ("the 1st AD", "key grip") is often missed. Supplement with domain stripping (stage 3).
- spaCy will underperform on informal writing (lowercase, misspelled, heavy slang). For review text specifically, consider pre-casing to title case before NER and then restoring original casing on non-entity tokens.

### Microsoft Presidio

Presidio wraps spaCy plus dozens of built-in "recognizers" (credit cards, IBAN, IP addresses, medical license numbers). Good if you want an off-the-shelf PII pipeline:

```python
# pip install presidio-analyzer presidio-anonymizer
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def presidio_anonymize(text: str) -> str:
    results = analyzer.analyze(text=text, language="en")
    return anonymizer.anonymize(text=text, analyzer_results=results).text
```

Presidio is heavier than hand-rolled spaCy+regex but covers more ground for less code. For a review product the custom approach is usually preferable because domain recognizers matter more than breadth.

---

## 5. Stage 3: domain-specific stripping

This is the stage most products underbuild. Load a configurable token list keyed to the domain:

```python
# productions/sanitization/domain_terms.py
FILM_ROLES = {
    "1st ad", "2nd ad", "third ad", "dga trainee",
    "dp", "director of photography", "dop",
    "1st ac", "2nd ac", "focus puller", "loader",
    "key grip", "best boy grip", "dolly grip",
    "gaffer", "best boy electric", "genny op",
    "script supervisor", "scripty",
    "boom op", "sound mixer", "utility sound",
    "key pa", "set pa", "production coordinator", "upm",
    # ...etc
}

FILM_DEPARTMENTS = {
    "camera dept", "grip dept", "electric dept", "g&e",
    "wardrobe", "costumes", "hair and makeup", "h&mu",
    "transportation", "transpo", "locations", "craft services",
    "crafty", "catering", "art department", "set dec", "props",
}

EQUIPMENT_TOKENS = {
    "35mm", "16mm", "alexa", "venice", "red komodo", "arri mini",
    "35mm b-cam", "a-cam", "c-cam", "splinter unit",
}


def strip_domain_tokens(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    """Case-insensitive literal match for domain terms."""
    removed = []
    lowered = text.lower()
    all_terms = sorted(
        FILM_ROLES | FILM_DEPARTMENTS | EQUIPMENT_TOKENS,
        key=len,
        reverse=True,  # longest match wins
    )
    # Build one combined regex for speed
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in all_terms) + r")\b",
        re.IGNORECASE,
    )
    offset_shift = 0
    def repl(m):
        nonlocal offset_shift
        start = m.start() + offset_shift
        removed.append((start, start + len(m.group()), "[ROLE_OR_DEPT]"))
        replacement = "[ROLE_OR_DEPT]"
        offset_shift += len(replacement) - len(m.group())
        return replacement
    return pattern.sub(repl, text), removed
```

Three tradeoffs:

1. **False positives matter.** Replacing every "1st AD" with `[ROLE_OR_DEPT]` strips useful context ("the AD was unprofessional" becomes "the [ROLE_OR_DEPT] was unprofessional" which still works; but "we were the 1st AD team" becomes garbled). Accept some of this; it's the cost of anonymity.
2. **Keep the term lists data, not code.** Load from YAML/JSON/DB so moderators can tune without deploy. Version the lists.
3. **Redacting is better than rewriting.** Replace with a labeled placeholder (`[ROLE]`, `[DATE]`, `[TRAILER]`) so the downstream reader and the moderator both see that something was removed.

---

## 6. Stage 4: LLM paraphrase for stylometric defense

Regex and NER strip identifiers; LLM paraphrase attacks *style*. The idea: send the sanitized text to an LLM with a prompt that preserves meaning while neutralizing voice.

```python
PARAPHRASE_PROMPT = """You are a privacy-preserving editor. Rewrite the following review in neutral, \
plain professional prose. Preserve every factual claim about the production's behavior (safety \
incidents, food quality, hours, compensation, professionalism). Remove anything that reveals the \
author's identity, role, or writing style. Do not add information. Do not soften or strengthen \
claims. Keep roughly the same length.

Review:
---
{text}
---

Rewritten review:"""


def paraphrase_for_stylometry(text: str, client=None) -> tuple[str, str]:
    client = client or get_llm_client()
    response = client.complete(
        prompt=PARAPHRASE_PROMPT.format(text=text),
        temperature=0.3,     # low, but non-zero to break stylometric signatures
        max_tokens=1024,
    )
    notes = f"paraphrased_by={client.model_name}"
    return response.text.strip(), notes
```

Several caveats:

- **LLM paraphrase can change meaning.** Always feed the output into moderator review before publication. A model that turns "I saw the AD hit a PA" into "there was a physical altercation on set" has editorialized away a factual claim.
- **Hallucination risk.** Instruct the model to not add information; test with evaluation sets that include both bland and specific reviews and check for introduced claims.
- **Defense is empirical, not formal.** There's no proof that a given paraphrase defeats stylometric classifiers. Keep an evaluation loop: periodically test whether a classifier trained on known authors can identify paraphrased samples.
- **Provider considerations.** Sending reviews to a third-party LLM means the provider briefly holds unredacted prose. Prefer self-hosted models (Llama, Qwen) for this step, or at minimum a provider with a no-retention agreement.
- **Cost.** Running every review through an LLM adds cost and latency. Gate behind a feature flag and scale deliberately.

A middle path: only paraphrase reviews longer than some threshold (short notes have less stylometric signal), or only paraphrase the long-form "general notes" field, not the structured per-dimension notes.

---

## 7. Human review: the moderator's role

Automated sanitization should feed into moderator review, not replace it. The moderator sees:

- Original text (moderator-only visible, destroyed after verification window)
- Per-stage redactions as a diff
- The final sanitized text, editable
- An "approve for publication" button that commits the sanitized version

```python
# productions/api/views/sanitization.py
class SanitizationReviewView(APIView):
    permission_classes = [IsModerator]

    def get(self, request, review_id):
        review = get_object_or_404(Review, id=review_id, verification_status="verified")
        result = sanitize(review.general_notes or "")
        return Response({
            "original": review.general_notes,
            "stages": [asdict(s) for s in result.stages],
            "sanitized_proposal": result.output_text,
        })

    def post(self, request, review_id):
        review = get_object_or_404(Review, id=review_id, verification_status="verified")
        review.sanitized_notes = request.data["sanitized_notes"]
        review.sanitized_by = request.user
        review.sanitized_at = timezone.now()
        review.save(update_fields=["sanitized_notes", "sanitized_by", "sanitized_at"])
        return Response({"status": "ok"})
```

Moderators should be trained to:

- Remove quasi-identifiers that automation missed.
- Reject or escalate reviews that can't be sanitized without destroying their substantive claim.
- Flag reviews whose content or style suggests the author is in a small-population role (e.g. the only 2nd AC on set).

---

## 8. Adversarial testing

Sanitization is adversarial. Build an evaluation set that includes:

- **Known PII examples** — synthetic reviews with obvious names, phones, addresses. All should be stripped.
- **Subtle quasi-identifier examples** — "on the Tuesday we shot the diner scene at Stage 14, I was in the 3:30am call trailer." All position-specific details should be stripped.
- **Stylometric probe examples** — pairs of reviews from the same author (real or synthetic). Train a simple classifier (e.g. logistic regression on char-n-gram TF-IDF) and measure attribution accuracy pre- and post-paraphrase.
- **Substance-preservation examples** — reviews where removing too much destroys the claim. Confirm sanitization keeps the core allegation intact.

```python
@pytest.mark.sanitization
def test_strips_email_and_phone():
    text = "Contact me at first.last@example.com or 555-123-4567."
    result = sanitize(text)
    assert "[EMAIL]" in result.output_text
    assert "[PHONE]" in result.output_text
    assert "example.com" not in result.output_text
    assert "555-123-4567" not in result.output_text


def test_preserves_safety_claim():
    text = "The gaffer on day 4 told me to ignore the LOTO on the 400A disconnect."
    result = sanitize(text)
    # Must preserve the substantive claim even while stripping identifiers
    assert "LOTO" in result.output_text or "lockout" in result.output_text.lower()


def test_does_not_introduce_new_facts():
    text = "The food was reheated."
    result = sanitize(text)
    # Ground-truth: the only claim is about food. No new claims should appear.
    forbidden = {"harassment", "injury", "discrimination", "unpaid"}
    assert not any(w in result.output_text.lower() for w in forbidden)
```

Run the sanitization suite in CI on every regex/NER/LLM-prompt change. Regressions here are silent privacy failures.

---

## 9. Operational and legal posture

- **Keep the original only as long as strictly needed for verification.** After the moderator publishes the sanitized version, the original should follow the same destruction lifecycle as the verification upload (see `verification-upload-lifecycle.md`).
- **Version the sanitization pipeline.** Record the pipeline version hash on each review. If you later discover a bug in a stage, you can re-sanitize affected reviews or add warnings to the published versions.
- **Document the pipeline publicly.** A transparency page describing "we strip these categories, and we paraphrase for style protection" sets user expectations and constrains moderator discretion.
- **Subpoena posture.** Sanitized text plus the structured fields are all you should retain post-publication. Make sure the moderation audit log records what was stripped *in aggregate* (categories and counts), not *literally* (the stripped content itself), or the log becomes its own retention problem.

---

## 10. Decision summary

- Always start with regex + NER + domain terms. These handle 80% of identifiers cheaply.
- Treat LLM paraphrase as a stylometric-defense layer, not a general sanitization tool.
- Always require moderator review before publication. Automation should reduce the moderator's work, not replace it.
- Build an adversarial test set early and grow it with every real review you see.
- Keep the list of domain terms as tunable data, not hardcoded constants.
- Instrument every stage so you can measure false-positive and false-negative rates.

---

## Sources

- Sweeney, L. "Simple Demographics Often Identify People Uniquely." 2000.
- Narayanan & Shmatikov. "Robust De-anonymization of Large Sparse Datasets." 2008.
- Juola, P. "Authorship Attribution." 2008.
- spaCy entity recognizer: https://spacy.io/usage/linguistic-features#named-entities
- Microsoft Presidio: https://microsoft.github.io/presidio/
- NIST IR 8053 "De-Identification of Personal Information." 2015.
- Mosteller & Wallace. "Inference and Disputed Authorship: The Federalist." 1964. (canonical stylometry reference)

Last updated: 2026-04-14
