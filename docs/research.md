# Research and sources

Collected in October 2026. Vendor docs change; check the current version.

## Vendor documentation

- Codex — config reference (`approvals_reviewer`, `agents.*`,
  `model_auto_compact_token_limit`): https://learn.chatgpt.com/docs/config-file/config-reference
- Codex — Speed / Fast mode (2.5x plan usage): https://learn.chatgpt.com/docs/agent-configuration/speed.md
- Codex — subagents (inherit model/effort): https://learn.chatgpt.com/docs/agent-configuration/subagents
- Codex — hooks (UserPromptSubmit, Stop, trust via `/hooks`): https://learn.chatgpt.com/docs/hooks.md
- Codex — AGENTS.md: https://learn.chatgpt.com/docs/agent-configuration/agents-md.md
- Codex — skills: https://learn.chatgpt.com/docs/build-skills.md
- Codex rate card (cached input at 10%): https://help.openai.com/en/articles/20001106-codex-rate-card-2
- Claude Code — memory / CLAUDE.md / imports: https://code.claude.com/docs/en/memory
- Claude Code — hooks: https://code.claude.com/docs/en/hooks.md
- Claude Code — skills: https://code.claude.com/docs/en/skills
- Claude Code — plugin manifest and marketplaces:
  https://code.claude.com/docs/en/plugins/manifest-reference.md,
  https://code.claude.com/docs/en/plugin-marketplaces.md
- Cursor rules: https://cursor.com/docs/context/rules
- Agent Skills open standard: https://agentskills.io

## Studies and articles

- "Report: Progressive Disclosure of Agent Skills" (arXiv, 2026): up to
  81.7% fewer tokens than eager loading as the number of skills grows; in one
  configuration (Qwen3-8B, 20 skills) retrieval was worse with progressive
  disclosure. https://arxiv.org/html/2609.35692v1
- 12 Ways to Cut Token Consumption in Claude Code (Firecrawl):
  https://www.firecrawl.dev/blog/claude-code-token-efficiency

## Similar reports (users hitting limits)

- Codex issue #45073 — ~86% of the 5-hour limit in ~26 minutes with 2 prompts: https://github.com/openai/codex/issues/45073
- Codex issue #31127 — usage depleted after a small task with 3 subagents: https://github.com/openai/codex/issues/31127
- Codex issue #29996 — 5-hour limit and subagent bug: https://github.com/openai/codex/issues/29996
- Codex issue #19571 — Pro plan 5-hour limit depleted in ~20 minutes: https://github.com/openai/codex/issues/19571

## Related projects

| Project | What it does | How token-diet differs |
|---|---|---|
| [claude-context-optimizer](https://github.com/egorfedorov/claude-context-optimizer) (MIT) | Claude Code plugin: usage tracking, wasted-context detection, budget alerts, CLAUDE.md analysis | token-diet also covers Codex logs and settings, enforces one task per session, and ships a tool-agnostic playbook and improvement loop |
| [ccusage](https://www.mintlify.com/ryoppippi/ccusage) | Usage/cost reports from Claude Code and Codex logs | Reports totals; token-diet focuses on causes (context per call, polling, multipliers) and fixes |
| [valorisa/Claude-Skills](https://github.com/valorisa/Claude-Skills) | Community skills incl. "rescue-tokens" (verbosity reduction) | Output-side; token-diet targets input/context, which dominates long sessions |

Use them together: ccusage for billing views, token-diet for diagnosis and
session discipline.
