---
name: redundancy
description: "Audit bilingual formal deliverables for low-information repetition, empty contrast, sequencer scaffolds, adjacent restatement, and repeated comparison-axis labels. Use when the user asks whether a draft feels redundant, wordy, low-information, or says the same thing twice."
---

# Redundancy

## Mission

Own `Redundancy diagnostics` for `ai-detect`.

This subskill is the dedicated owner for:

- low-information repetition
- empty contrast
- sequencer scaffolds used in place of content labels
- adjacent restatement
- repeated comparison-axis labels

It is not a general style critic and it does not decide whether text is AI-generated.

## Scope

In scope:

- bilingual formal deliverables
- `.tex`
- `.md`
- `.js` / `.ts` deck-authoring source when the strings are user-visible

Out of scope:

- ordinary chat
- email drafts
- free-form brainstorming notes
- `.jsx` / `.tsx`
- binary `.pptx`
- OCR / image text

## Relationship To `ai-detect`

- `ai-detect` remains the parent owner for overall AI-smell auditing.
- `redundancy` owns only the `Redundancy diagnostics` surface.
- When `ai-detect` scans a file, it should delegate redundancy work to this subskill rather than reimplementing the heuristics inline.

## Detection Categories

Use exactly these categories in v1:

- `redundant_filler`
- `empty_contrast`
- `sequencer_label`
- `adjacent_restatement`
- `axis_repetition`

Do not invent additional category names in v1.

## Confidence Policy

Balanced precision means:

- confirmed rules and high-confidence heuristics go straight to findings
- borderline cases stay in the review queue
- do not silently promote review-queue items into confirmed findings

## Canonical Workflow

### 1. Bind The Surface

Before scanning, bind one surface:

- `tex`
- `md`
- `js`
- `ts`

If the source is unknown:

- infer it from the file suffix
- default pasted text without a file suffix to `md`

### 2. Extract Only User-visible Text

- For `.tex`, scan document-body prose and ignore comments, inline math, display math, macro noise, and structural commands.
- For `.md`, ignore code fences, inline code, and raw URLs; keep headings, lists, and body prose.
- For `.js` / `.ts`, use the bundled AST helper and extract only user-visible string surfaces such as `title`, `subtitle`, `heading`, `caption`, `body`, `text`, `content`, `label`, and `footer`, plus common slide-builder text arguments.
- Do not scan arbitrary string literals, file paths, style keys, or implementation comments.

### 3. Run Three Layers

Run in this order:

1. confirmed rules
2. pending review-queue candidates
3. heuristics

Heuristics must stay category-bounded to the five allowed categories.

### 4. Return Structured Findings

Each confirmed finding should include:

- `kind`
- `line_no`
- optional `end_line_no`
- `surface`
- `language`
- `text`
- optional `next_text`
- `confidence`
- `fix`

Pending review hits should stay separate from confirmed findings.

## CLI

Primary scanner:

```bash
python3 ~/.codex/skills/ai-detect/redundancy/scripts/scan_redundancy.py <file>
python3 ~/.codex/skills/ai-detect/redundancy/scripts/scan_redundancy.py <file> --json
```

The scanner also supports:

- `--text`
- `stdin`
- `--surface`

## References

Load only when needed:

- `references/historical-signals.md`
- `data/rules.json`
- `data/review_queue.jsonl`

## Acceptance Bar

The subskill is ready only when:

- it can run standalone on `.tex`, `.md`, and `.js/.ts`
- `ai-detect` can call it and preserve the `Redundancy diagnostics` section name
- pending redundancy candidates do not leak into confirmed output
- at least one positive and one negative case pass for each supported surface


## Validation And Checkpoints

- Before final handoff, validate the requested artifact or decision against this skill's output contract and report the verification result explicitly.
- Before any local mutation, pass the recoverability gate: create a rollback point when the change is reversible, and request confirmation when backup cannot cover the risk.
- Use an explicit checkpoint when required input is missing, tool evidence conflicts, or repeated attempts fail; wait for approval or route to the named owner instead of guessing.
- For multi-session work, update a progress or HANDOFF artifact with current state, verified result, and next executable step.
