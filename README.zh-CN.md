# AI Detect Skill

用于检查草稿、幻灯片和报告中模板味或 AI 味表达的可移植审查 skill。

## 提供内容

- 可安装 skill: [`ai-detect`](./ai-detect)
- 公开 references: [`ai-detect/references/`](./ai-detect/references)
- 辅助脚本: [`ai-detect/scripts/`](./ai-detect/scripts)
- 公开数据: [`ai-detect/data/`](./ai-detect/data)

## 安装 / 使用

- `Codex App`：从本仓库路径 `ai-detect` 安装
- GitHub 安装目标：
  - repo：`<owner>/ai-detect-skill`
  - path：`ai-detect`
- 安装后重启 `Codex App`，让新 skill 被发现。

## 覆盖范围

- 支持基于 confirmed rules 的文本扫描，识别模板味表达
- 支持对边界案例做候选提取和复核流程
- 适用于 slide、report、homework 与 markdown 草稿审查

## 触发示例

- `Check whether this draft sounds AI-written.`
- `Audit these slide titles for template smell.`
- `Scan this report for wording that feels too process-heavy.`

## 不触发示例

- `Decide whether a person or model wrote this message.`
- `Rewrite the whole paper from scratch.`
- `Classify a private chat log unrelated to final deliverables.`

## 隐私边界

这个公开仓库只保留可复用、可公开的工作流部分。

- Private review queues and local session exports are excluded from the public package.
- The published rules stay generic and do not expose personal memory files or local paths.

## 仓库结构

- `ai-detect/`: installable `Codex App` skill
- `ai-detect/references/`: bundled public references
- `ai-detect/scripts/`: bundled public scripts
- `ai-detect/data/`: bundled public data
- `CHANGELOG.md`: release history
- `LICENSE`: `MIT`

English:

- [README.md](./README.md)
