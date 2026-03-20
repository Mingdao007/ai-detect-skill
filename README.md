# AI Detect Skill

Portable audit skill for spotting template-heavy or AI-smelling wording in drafts, slides, and report-style writing.

## What Ships

- installable skill: [`ai-detect`](./ai-detect)
- bundled public references: [`ai-detect/references/`](./ai-detect/references)
- bundled helper scripts: [`ai-detect/scripts/`](./ai-detect/scripts)
- bundled public data: [`ai-detect/data/`](./ai-detect/data)

## Install / Use

- `Codex App`: install the skill from this repo path `ai-detect`
- GitHub install target:
  - repo: `<owner>/ai-detect-skill`
  - path: `ai-detect`
- Restart `Codex App` after installation so the new skill is discovered.

## Coverage

- confirmed-rule scanning for wording that reads too template-driven
- queue-aware extraction and review workflow for borderline phrasing
- draft auditing for slide decks, reports, homework, and markdown writing

## Trigger Examples

- `Check whether this draft sounds AI-written.`
- `Audit these slide titles for template smell.`
- `Scan this report for wording that feels too process-heavy.`

## Non-Trigger Examples

- `Decide whether a person or model wrote this message.`
- `Rewrite the whole paper from scratch.`
- `Classify a private chat log unrelated to final deliverables.`

## Privacy Boundary

This public repository keeps the workflow generic and reusable.

- Private review queues and local session exports are excluded from the public package.
- The published rules stay generic and do not expose personal memory files or local paths.

## Repository Layout

- `ai-detect/`: installable `Codex App` skill
- `ai-detect/references/`: bundled public references
- `ai-detect/scripts/`: bundled public scripts
- `ai-detect/data/`: bundled public data
- `CHANGELOG.md`: release history
- `LICENSE`: `MIT`

Chinese:

- [README.zh-CN.md](./README.zh-CN.md)
