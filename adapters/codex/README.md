# Codex adapter

## Skill

```bash
mkdir -p ~/.agents/skills
ln -s <repo>/plugins/token-diet/skills/token-diet ~/.agents/skills/token-diet
```

## Session guard hooks

1. Merge `hooks.json` from this folder into `~/.codex/hooks.json`, replacing
   `{{TOKEN_DIET}}` with the absolute path of
   `<repo>/plugins/token-diet/skills/token-diet`:

   ```bash
   SKILL="$HOME/token-diet/plugins/token-diet/skills/token-diet"
   sed "s|{{TOKEN_DIET}}|$SKILL|g" hooks.json > ~/.codex/hooks.json   # only if you have no hooks.json yet
   ```

2. Trust the hooks: open the Codex CLI and run `/hooks`. Untrusted hooks do
   not run; changing the hook file asks for trust again.
3. Enable the guard with a `.token-diet.json` (see the main README).
4. Tell your `AGENTS.md` to end each finished task with the close marker
   (default: a block titled `Next step — Git`).

Check that the hooks fire in your surface (CLI, IDE extension, app): run one
short task, end it with the marker, then send another prompt — it should be
blocked. Hook docs: https://learn.chatgpt.com/docs/hooks.md

## Recommended config

See `references/tools.md` in the skill (`model_reasoning_effort`,
`approvals_reviewer`, Fast mode, subagent settings).
