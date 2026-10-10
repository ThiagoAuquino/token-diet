# Tool-specific notes

Only settings confirmed in vendor documentation (links in `docs/research.md`).
Check your tool version: keys change.

## Codex (CLI, IDE extension, app)

`~/.codex/config.toml`, top-level keys before the first `[table]`:

```toml
model_reasoning_effort = "medium"          # TD-10
model_auto_compact_token_limit = 100000    # safety net for TD-02
approvals_reviewer = "user"                # TD-07: no model-reviewed approvals
# service_tier = "priority"                # avoid: Fast mode uses plan limits at 2.5x

[agents]
default_subagent_reasoning_effort = "medium"   # TD-08
max_concurrent_threads_per_session = 1
```

- The IDE extension can override `approvals_reviewer`; the effective value is
  in the session log (`analyze_sessions.py` flags it).
- Instructions: `~/.codex/AGENTS.md` (global) + the `AGENTS.md` chain of the
  project. Skills: `.agents/skills/` (repo) and `~/.agents/skills/`.
- Exec waits (TD-05): give long commands a wait longer than their duration.

### Codex hooks (session guard)

Copy `adapters/codex/hooks.json` from the repository to `~/.codex/hooks.json`
(merge if you have one), replacing `{{TOKEN_DIET}}` with the absolute path of
`plugins/token-diet/skills/token-diet`. Hooks run only after you trust them:
open the Codex CLI and use `/hooks`. Any change to the hook asks for trust
again. Hooks are documented for the CLI; confirm they fire in the IDE
extension on your setup.

## Claude Code

- Instructions: `~/.claude/CLAUDE.md`, project `CLAUDE.md`, `@path` imports,
  `.claude/rules/*.md` (with `paths:` they load only for matching files).
  To share one file with other tools, put `@AGENTS.md` in `CLAUDE.md`.
- Skills: `.claude/skills/<name>/SKILL.md`, `~/.claude/skills/`, or plugins.
- The token-diet plugin registers `UserPromptSubmit` and `Stop` hooks; the
  guard stays inactive until a `.token-diet.json` enables it.
- `/compact` and `/clear` exist; a new session per task is still the cheapest
  reset.

## Cursor and other AGENTS.md tools

- Cursor reads `AGENTS.md` and `.cursor/rules/*.mdc`. Rules with
  `alwaysApply: true` are always loaded; prefer globs or agent-requested rules.
- No session-guard hook here: TD-01/TD-02 apply as instructions only.
- `audit_context.py` reports always-applied `.mdc` rules.
