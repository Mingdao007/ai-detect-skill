# Historical Signals

This file is the human-readable summary for `ai-detect`.

Use it to understand the user's a separate preference-memory workflow.
Do not treat it as the only executable source.

Scope boundary:

- these signals are about the final `.tex` wording that the agent writes into the delivery
- they are not a demand that user plans, detector-maintenance chat, or ordinary working chat must sound non-AI

The machine-readable source now lives in:

- `data/rules.json` for confirmed rules
- `data/review_queue.jsonl` for pending or recently reviewed candidates

## Confirmed Signals

These items already have enough user evidence to be hard rules.

### 1. Workflow titles are suspicious when they replace content titles

Evidence:

- 2026-03-11: user rejected `Final split` for a review slide title.
- 2026-03-11: user rejected `Discussion for the next meeting` because it imported ordinary collaboration or meeting framing into a student-facing `.tex` delivery.
- 2026-03-11: `What this deck is trying to do` was treated as deck-meta narration rather than a student-facing academic title.

Working rule:

- a final deliverable title should name the content, not the workflow stage
- do not turn ordinary interaction context, meeting agenda, or next-step planning into slide or section titles inside a student deliverable
- do not title a slide by narrating what the deck is doing; title it by the actual objective or content

### 2. Template labels should be removed or renamed

Evidence:

- 2026-02-27: `Question 1/2` should become actual subsection names
- 2026-02-27: remove `Answer:`
- 2026-02-27: user rejected `Task 3` and wanted `Convergence speed and robustness`

Working rule:

- replace template labels with the real subsection name
- if the label adds no value, delete it

### 3. Process narration leaks AI smell

Evidence:

- 2026-02-27: user explicitly rejected `Directly answering ...`

Working rule:

- do not narrate that the answer is being given; just give it

### 4. Figure captions should not sound layout-driven

Evidence:

- 2026-02-27: user rejected `Three-column ... comparison` in a figure caption

Working rule:

- describe variables, conditions, or comparisons directly instead of naming the visual layout

### 5. Solutions-template homework titles sound non-human

Evidence:

- 2026-03-06: user rejected `Course Homework 1 Solutions`

Working rule:

- use course title plus assignment subtitle instead of a `Solutions` title

### 6. Transitional filler clauses should not lead a result sentence

Evidence:

- 2026-02-27: `the six cases are:` was replaced with a direct reference to the result table instead of being kept in the report text.

Working rule:

- do not lead a result sentence with filler such as `the six cases are:`
- in report prose, point directly to the table, figure, or result statement

## Pending Review Buckets

These patterns are plausible but should stay in the review queue until the user confirms them:

- `Candidate directions`
- `Discussion for the next meeting`
- `Mainline recent papers and venues`
- `Why this review`
- `Corpus and review pipeline`
- `Recent Literature Review for ...`
- `this slide shows`
- `author synthesis`
- `Methods, Taxonomy, and Candidate Directions`

## Quick Rewrite Patterns

| Bad | Better |
|---|---|
| `Final split` | content-specific title such as `Research direction` |
| `Question 1` | actual subsection name |
| `Answer:` | remove |
| `Task 3` | real task title |
| `Course Homework 1 Solutions` | course title + assignment subtitle |
| `Directly answering ...` | delete and start with the answer |
| `Three-column comparison` | describe variables or conditions directly |
| `What this deck is trying to do` | content title such as `Objectives of this review` |
| `the six cases are:` | direct result sentence or `shown in Table ...` |
