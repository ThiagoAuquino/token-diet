---
name: token-diet
description: Measure and cut token consumption of AI coding agents (Claude Code, Codex, Cursor, any AGENTS.md tool) without losing quality. Use when usage limits run out fast, sessions feel expensive or slow, the user asks where tokens went, wants to audit always-loaded instructions, install a one-task-per-session guard, or turn a new lesson into a measured improvement.
license: Apache-2.0 (see LICENSE and NOTICE in the repository)
compatibility: Python 3.8+ for the scripts. Reads local Claude Code and Codex session logs; nothing is sent anywhere.
metadata:
  author: Thiago Auquino (Auquitech)
  version: 0.1.0
---

# token-diet

Core fact behind every rule here: **each model call resends the whole session
context.** The cost of an action is the size of the context at that moment,
not the size of the action. A 3-second `sleep` poll in a 180k-token session
costs 180k tokens.

Work in this order and never skip the measurement: no change is proposed
without a number from the user's own logs or files, and no number is invented.

## Modes

| Mode | Use when | Edits files? |
|---|---|---|
| `diagnose` | "Where did my tokens go?", limit hit early | No |
| `audit` | Check what every session loads before work starts | No |
| `improve` | Apply fixes from diagnose/audit, or record a new lesson | Yes, after the user approves |
| `guard` | Enforce one task per session and a token budget | Yes (config only) |

Scripts live in `scripts/` next to this file. Run them with `python3`.

## diagnose

1. `python3 scripts/analyze_sessions.py --last 10` (add `--project <name>` or
   `--since YYYY-MM-DD`, or pass a `.jsonl` path). Codex and Claude Code logs
   are found automatically.
2. Read the table: `input` (sum of tokens sent across calls), `ctx 1st`
   (context of the first call), `peak`, `cmp` (compactions), `polls`.
3. Each finding carries a rule ID (`TD-xx`). Explain the top 3 by tokens, with
   the numbers, and the fix from `references/playbook.md`.
4. If logs are missing or the format changed, say so. Ask the user for the
   session file or the numbers their tool shows; do not estimate silently.

## audit

1. `python3 scripts/audit_context.py <project-folder>` — lists AGENTS.md,
   CLAUDE.md (+ @imports), always-on rules and skill descriptions, with sizes.
2. Anything over the caps, or detail that is not needed in every session,
   is a candidate to move into a skill, a referenced doc or a task brief
   (TD-03, progressive disclosure).
3. Also check tool settings that multiply cost (TD-07): fast/priority tiers,
   model-reviewed approvals, high reasoning effort as default. See
   `references/tools.md`.

## improve

Follow `references/improvement-loop.md`:

1. **Baseline** — numbers from `diagnose`/`audit` for the sessions or files
   involved.
2. **Classify the lesson** — temporary (task notes only), project-specific
   (project docs) or shareable (framework/global instructions).
3. **Pick the cheapest destination** that will actually be followed:
   always-loaded line < on-demand rule/skill < deterministic hook/script.
   Prefer what costs nothing in every session.
4. **Propose** the exact text/diff and its always-loaded cost in bytes. Edit
   only after the user approves.
5. **Re-measure** on the next comparable task and record before/after.

## guard

The session guard is a hook for Claude Code and Codex (`scripts/session_guard.py`).
It is **off until configured**.

1. Create `.token-diet.json` in the project (or `~/.config/token-diet/config.json`
   for all projects) from `references/config.example.json`.
2. Tell the agent's instructions to end a finished task with the close marker
   (default: a block titled `Next step — Git`).
3. Claude Code: the plugin's hooks are active once installed. Codex: see
   `references/tools.md` § Codex hooks (needs `/hooks` trust).
4. Behavior: after the close marker, a new prompt in the same session is
   blocked ("start a new session"); over the budget, the agent is asked once
   to checkpoint and close. `#same-session` in a prompt bypasses it. Errors
   always let work through.

## Rules for this skill

- Measure first; cite the file and numbers. Never invent figures or sources.
- Do not read whole logs into context: run the scripts and read their output.
- Quality is not traded for tokens: tests, reviews and gates stay; only waste
  (repeated context, polling, re-discovery, oversized instructions) is cut.
- The user commits and pushes. End `improve` with the suggested `git add`
  (by path) and commit message.
