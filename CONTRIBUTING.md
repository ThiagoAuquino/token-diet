# Contributing

Thanks for helping people spend fewer tokens.

## What we accept

- **New or better rules (TD-xx):** include the evidence — before/after numbers
  from `analyze_sessions.py` or `audit_context.py`, tool and model, and what
  changed. A vendor doc link counts as evidence for tool settings.
- **Parser fixes for new log formats:** include a small **synthetic or
  redacted** sample as a test fixture. Never commit real session logs: they
  contain code, paths and prompts.
- **New tools** (adapters, notes in `references/tools.md`): only settings
  confirmed in the tool's official docs, with the link.

## Rules

- No invented numbers or sources.
- Keep `SKILL.md` short (Agent Skills guidance: under 500 lines); detail goes
  to `references/`.
- Scripts: Python 3.8+, standard library only, fail-open in hooks.
- Run `python3 -m unittest discover -s tests` and `claude plugin validate .`
  (if you have Claude Code) before opening a pull request.

## License of contributions

By contributing you agree that your contribution is licensed under the
Apache License 2.0 (section 5 of the LICENSE).
