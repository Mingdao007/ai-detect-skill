# Redundancy Historical Signals

This file summarizes the confirmed user-facing redundancy patterns that justify
the dedicated `redundancy` subskill under `ai-detect`.

## 1. Empty-information contrast should be flagged

Evidence:

- 2026-04-14: user explicitly rejected `We organize this part as a sequence of repair choices, not as a list of unrelated papers.`
- 2026-04-14: user described this class as `废话检查`, especially when the second clause adds little beyond the first

Working rule:

- flag contrast clauses whose right-hand side adds only generic nouns or generic modifiers
- prefer direct content naming over a weak `not X but Y` scaffold when `Y` adds no real distinction

## 2. Sequencer scaffolds should not stand in for content

Evidence:

- 2026-04-14: user rejected slide questions led by `First --`, `Then --`, and `Finally --`
- this extends naturally to Chinese scaffolds such as `首先` / `然后` / `最后` when they replace the actual content label

Working rule:

- flag headings or slide prompts that rely on sequence scaffolds rather than naming the content directly

## 3. Adjacent restatement should be flagged

Evidence:

- 2026-04-14: user explicitly wanted `废话检查` to catch later sentences that mostly restate earlier ones with negligible information gain

Working rule:

- when two adjacent prose units heavily overlap and the later one contributes almost no new information, flag the weaker one for merge-or-delete

## 4. Repeated comparison-axis labels should be flagged

Evidence:

- 2026-04-21: user explicitly pointed out that repeating the same low-information label such as `不同` across a short parallel comparison list raises redundancy without improving meaning

Working rule:

- in a short comparison block, front-load the shared comparison axis once and then name the substantive differences directly
- flag repeated low-information axis markers such as `不同`, `区别在于`, `respectively`, or `in contrast` when they are used as repeated scaffolds instead of content
