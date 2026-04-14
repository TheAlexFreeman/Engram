---
type: project-inbox
project: rate-my-set
source: user-upload
uploaded: 2026-04-14
trust: medium
---

# Rate My Set — inbox

Initial artifacts from Alex describing an entertainment-industry forum where cast/crew can post honest reviews of on-set experiences without fear of retaliation.

## Contents

- `workflow.pdf` — sitemap / information architecture diagram, split across Front End, Back End, and HQ tiers.
- `questionnaire.pdf` — draft survey users fill out after a booking.

## Summary of workflow.pdf

Three tiers of surface:

**Front End (public)**
- Home: quick blurb; search bar (default by show name, also by showrunner or code name); "See full list"; Sign In/Sign Up.
- Results: list of shows matching the search; "Don't see your set?" escape hatch.
- Reviews: show-level review page.
- Lists: full browsable list; "Add a show" requires sign-in and at least one review.

**HQ (authenticated user area)**
- See reviews.
- Rate a set — links to the Survey/Questionnaire flow.

**Accounts**
- Sign in / sign up. Connects to Account creation on the back end.

**Back End**
- Account creation.
- Data collection (from the questionnaire).
- Moderator review: if a user self-enters a show name that isn't in the DB, a moderator checks whether it really is missing; otherwise it gets folded into the matching existing show.

## Summary of questionnaire.pdf

Sections, each using a red / yellow / green smiley-face scale unless otherwise noted:

**Header**
- Date, Production, Producer.
- Union or Non-Union.
- Upload confirmation of booking (with identifying info blacked out).

**Professionalism**
1. Was the job as advertised? (e.g., surprise exteriors, undisclosed tiling.)
2. Were you treated respectfully? (incl. appearance/grooming being critiqued irrelevantly.)
3. Did you experience or notice harassment? (No/Yes — Yes implicitly flags the entry.)
4. If reported, how well was it handled?
5. Did you experience or notice discrimination? (No/Yes.)
6. If reported, how well was it handled?
- Anonymous reporting link offered for harassment/discrimination.
- Notes field.

**Food**
1. Crafty quality.
2. Walkaway meal? (Yes flags negative.)
3. Meal quality (variety, nutrition, enough left after crew/union).
- Notes field.

**Safety**
1. Was the set physically safe?
2. Was anyone injured? (Yes flags negative.)
3. Temperature on set (note: "switch 'on set' with 'in holding'" — appears to be an editing TODO to reframe this for background talent in holding).
4. If extreme temps, was water/shelter/clothing provided? (with N/A.)
5. Accommodation for disability/aid needs? (with N/A.)
6. Hazardous conditions (pyro, smoke, flashing lights) — appropriate precautions? (with N/A.)
- Notes field.

**Green Production** (yes/no questions rather than the three-face scale)
- Advertised as eco-friendly?
- Compostable plates?
- Compost bin available?
- Recycling bin available?
- Designated staff to sort waste?

**Overall**
- Overall experience (red/yellow/green).

**Scorecard** (generated output)
- Overall score, Professionalism score, Safety score, Food score.
- Number of members who have reported harassment or discrimination.

## Observations for brainstorming

- Search by **code name** plus the "Don't see your set?" flow implies the product should handle unannounced / covert productions.
- A review is required before you can request adding a show — good spam-control primitive, but couples "new show creation" to "at least one person being willing to post".
- The scorecard surfaces a **count of harassment/discrimination reports** — this is more lawsuit-adjacent than star ratings and needs its own trust/legal design track.
- The questionnaire is strong on working-conditions signal (safety, food, green) but currently has no dimensions for compensation/payment issues, crew hours, or production-specific roles (background vs principal vs crew department).
- "Are you Union or Non-Union" is captured but not yet used — it could segment scores so non-union set experience isn't drowned out by union averages.
- Upload of booking confirmation is the verification primitive; the whole anonymity model depends on how that upload is handled.
