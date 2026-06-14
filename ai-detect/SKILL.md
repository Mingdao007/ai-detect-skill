---
name: ai-detect
description: "Audit drafts, slides, reports, homework, and sendable external messages for AI-smelling wording using Mingdao's historical session feedback. Use when the user asks whether a deliverable has 'AI味', sounds unnatural, has high entropy, uses placeholder titles, over-explains, contains process filler, or does not sound like a normal human wrote it."
---

# AI Detect

## Purpose

Audit drafts, slides, reports, homework, and sendable external messages for AI-smelling wording using Mingdao's historical session feedback. Use when the user asks whether a deliverable has 'AI味', sounds unnatural, has high entropy, uses placeholder titles, over-explains, contains process filler, or does not sound like a normal human wrote it.

Keep this `SKILL.md` as a concise routing and execution entrypoint. Do not load
long examples, command catalogs, detailed checklists, or edge-case policy until
the current task needs them.

## Workflow

1. Confirm the user request matches this skill's frontmatter description.
2. Bind the concrete target: source file, artifact, repo, device, document,
   dataset, or user-facing deliverable.
3. Use the smallest relevant workflow from this entrypoint first.
4. Before scanning a deliverable, applying historical rules, running bundled
   scripts, rewriting high-risk wording, or reporting AI-smell status, read
   `references/entrypoint-details.md`.
5. Preserve local owner boundaries: route to a narrower skill or repo-specific
   workflow when the detailed reference indicates a more specific owner.

## Detailed Reference

Read `references/entrypoint-details.md` for:

- Overview
- Trigger Conditions
- Canonical Workflow
- Seeded Confirmed Rules
- User Evidence Base
- Bundled Scripts
- Quick Start
- Output Expectations
- Guardrails
- Validation And Checkpoints

## Validation

- Use the skill-specific validation or acceptance checks from the detailed
  reference before declaring completion.
- When editing this skill, run `quick_validate.py` on the skill directory and
  verify all referenced files still exist.
