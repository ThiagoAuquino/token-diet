# Continuous improvement loop

Goal: every lesson about token usage becomes a measured change in the place
where it costs least and is most likely to be followed.

## 1. Baseline

Run `scripts/analyze_sessions.py` on the sessions that show the problem and
note: input tokens, first/avg/peak context, polls, compactions, % of the plan
limit if the tool shows it. Run `scripts/audit_context.py` if the change is
about instructions.

## 2. Classify the lesson

| Class | Example | Destination |
|---|---|---|
| Temporary | "this test is flaky today" | Task notes / handoff only |
| Project-specific | "tests need `docker compose up db` first" | Project notes (environment commands, TD-11) |
| Shareable | "polling a 2-min gate with 1 s waits burns context" | Framework or global instructions |

Shareable text has no product name, ticket number or repo-specific path.

## 3. Choose the destination (cheapest that works)

| Kind | Destination | Cost per session |
|---|---|---|
| Must hold even if the agent forgets | Hook / script (e.g. session guard) | ~0 |
| Procedure used sometimes | Skill (`SKILL.md` + `references/`) | name + description |
| Rule with detail | Rule/doc read on demand, ID referenced | 0 until read |
| Obligation for every session | One line in AGENTS.md / CLAUDE.md | every call |
| Tool-specific setting | Tool config + a note in your tooling docs | 0 |

If a rule already exists and still failed, do not repeat the sentence:
make it checkable (a script, a hook, a checklist item in the brief).

## 4. Propose, then apply

Present: class → destination → exact text/diff → bytes added to
always-loaded context. Apply only after approval. Commit by path.

## 5. Re-measure

On the next comparable task, run the same commands and record before/after
next to the change (commit message, changelog or notes). Keep changes that
moved the numbers; revert the ones that did not.

## Sharing back

If the lesson is general and measured, open an issue or pull request in the
token-diet repository with the before/after numbers (no private logs).
