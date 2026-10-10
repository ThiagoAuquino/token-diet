# token-diet

Measure and cut the token consumption of AI coding agents (Claude Code,
OpenAI Codex, Cursor and other AGENTS.md tools) without lowering quality.

[Português (Brasil)](README.pt-BR.md)

> Every model call resends the whole session context. The cost of an action
> is the size of the context at that moment, not the size of the action.

In the [case study](docs/case-study.md), a 5-hour Codex limit was used up in
11 minutes on one unfinished task. After the changes in this repo, the same
kind of task took 8–13% of the limit and passed review.

## What's inside

| Piece | What it does |
|---|---|
| `analyze_sessions.py` | Reads local Claude Code and Codex session logs. Shows input tokens, context size per call (first/avg/peak), compactions, polling, fast-mode and model-reviewer settings, and labels each finding with a rule |
| `audit_context.py` | Lists what every session loads before work starts (AGENTS.md chain, CLAUDE.md + @imports, always-on rules, skill descriptions), with sizes and over-cap findings |
| `session_guard.py` | Hook for Claude Code and Codex: one task per session plus a token budget. Opt-in, fails open |
| [Playbook](plugins/token-diet/skills/token-diet/references/playbook.md) | 12 tool-agnostic rules (TD-01…TD-12), each tied to evidence |
| [Improvement loop](plugins/token-diet/skills/token-diet/references/improvement-loop.md) | How to turn a new lesson into a measured change: baseline → classify → cheapest destination → apply → re-measure |
| `token-diet` skill | Wraps it all for the agent: modes `diagnose`, `audit`, `improve`, `guard` |

Everything runs locally with Python 3.8+ and no dependencies. Nothing is sent anywhere.

## Install

### Claude Code (plugin)

```bash
claude plugin marketplace add ThiagoAuquino/token-diet
claude plugin install token-diet@token-diet
```

Then ask: "use token-diet to diagnose my last sessions".

### Codex, Cursor and other tools (skill)

```bash
git clone https://github.com/ThiagoAuquino/token-diet.git ~/token-diet
mkdir -p ~/.agents/skills
ln -s ~/token-diet/plugins/token-diet/skills/token-diet ~/.agents/skills/token-diet
```

Codex reads skills from `~/.agents/skills` and `.agents/skills`. For tools
without skills, copy the short forms from the playbook into your `AGENTS.md`.

### Scripts only

```bash
S=~/token-diet/plugins/token-diet/skills/token-diet/scripts
python3 $S/analyze_sessions.py --last 10
python3 $S/audit_context.py path/to/project
```

## Session guard (optional)

Off until a config file enables it. Create `.token-diet.json` in a project
(or `~/.config/token-diet/config.json` for all projects):

```json
{ "session_guard": { "enabled": true, "max_session_input_tokens": 3500000,
  "close_markers": ["Next step — Git"], "bypass_token": "#same-session" } }
```

- The agent ends a finished task with the close marker → the next prompt in
  that session is blocked with "start a new session".
- Over the budget → the agent is asked once to checkpoint and close; new
  prompts are blocked.
- `#same-session` in a prompt lets it through (e.g. "write the commit message").
- Claude Code: hooks come with the plugin. Codex: see
  [adapters/codex](adapters/codex/README.md) (needs `/hooks` trust).

Calibrate the budget with `analyze_sessions.py` on your own finished tasks.
The default (3.5M input tokens) comes from the case study and is a starting point.

## Example output

```
start             tool   model        calls   input cached ctx 1st    avg   peak cmp polls
2026-10-08T22:46  codex  top-model       86   13.0M    97%   25.3k 151.4k 201.3k   0     9
    TD-07: service tier 'priority' (fast mode) — billed at a multiple of the normal rate
    TD-01: context peaked at 201,285 tokens — one task per session, checkpoint earlier
    TD-05: 7 polls + 2 sleeps — each wait resends the whole context
2026-10-10T11:35  codex  cheaper-model   39    2.4M    97%   19.9k  60.6k  76.9k   0    10
```

## Limits

- Session log formats are not public, stable interfaces. Parsers skip what
  they do not understand; if a format changes, open an issue with a redacted
  sample.
- Hooks are documented for the Codex CLI; check that they run in your IDE extension.
- No vendor publishes its exact plan-metering formula. Compare sessions of
  the same tool with each other.

## Related work and sources

See [docs/research.md](docs/research.md) for vendor docs, studies, user
reports and similar projects (ccusage, claude-context-optimizer and others).

## Contributing

Lessons with before/after numbers are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE). You can use, change and redistribute this
freely, including commercially. Redistributions must keep the [NOTICE](NOTICE)
file with the author's attribution. The license grants users a patent license
from contributors and ends it for anyone who sues over patents in this work.

Created by **Thiago Auquino** ([Auquitech](https://github.com/ThiagoAuquino)).
