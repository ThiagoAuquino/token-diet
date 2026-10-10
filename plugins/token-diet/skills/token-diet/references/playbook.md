# token-diet playbook (TD rules)

Tool-agnostic rules. Each one came from a measured session (see
`docs/case-study.md` in the repository) or from vendor documentation (links in
`docs/research.md`). Copy the short form into your AGENTS.md / CLAUDE.md only
if it is not already covered; the detail stays here.

Root fact: **every model call resends the whole session context.**

| ID | Rule | Short form for AGENTS.md / CLAUDE.md |
|---|---|---|
| TD-01 | One task per session | Finish or checkpoint the task, then start a new session for the next one. |
| TD-02 | Session budget | Past the budget (start ~80k context or the session-input cap), write a checkpoint and continue in a new session. |
| TD-03 | Small always-loaded context | Always-loaded instructions are a map, not a manual; detail lives in skills/docs read on demand. |
| TD-04 | Brief before docs, targeted reads | Read the task brief first; open other docs only when cited, and only the section needed (search, line ranges). |
| TD-05 | No polling | Long commands run in one blocking call with a wait longer than the command takes; never loop sleep/wait/tail. |
| TD-06 | Lean command output | Keep logs in files; bring back exit code, failures and last lines only. |
| TD-07 | No hidden multipliers | No fast/priority tier, model-reviewed approvals or high effort by default. |
| TD-08 | Subagents only with real gain | Delegate only independent or clean-context work; one brief in, one result out, no progress chatter. |
| TD-09 | Workspace = project folder | Open the project folder so tests and edits do not need per-command approval. |
| TD-10 | Effort proportional | High reasoning / expensive models for planning, design and risk review; medium for executing a briefed task. |
| TD-11 | Environment recorded | Test/gate commands and prerequisites live in project notes; a new discovery is written there at close. |
| TD-12 | Hot notes stay small | Current-state notes stay short (~4 KB); history is moved to cold files, never deleted. |

## Details and evidence

**TD-01 / TD-02.** In the case study, one session carried several tasks: each
call sent 172k–201k tokens and the 5-hour limit was gone in 11 minutes with
the task unfinished. One task per session with a brief kept the average
context at 55k–61k. Enforce with the session guard (`guard` mode); without
hooks, the rule still applies.

**TD-03.** Always-loaded text is paid on every call. Agent Skills load only
`name` + `description` until used (progressive disclosure). A 2026 study
measured up to 81.7% fewer tokens than eager loading as the number of skills
grows, with one configuration where retrieval got worse (`docs/research.md`).
Measure with `audit_context.py`.

**TD-04.** A task brief ("context pack") names the files, rules and commands
the task needs. The executor starts from it instead of reading the whole
framework "to get oriented".

**TD-05.** Codex's exec tool returns after its wait time even if the command
is still running; a 1 s wait on a 1–2 min quality gate produced repeated
"is it done?" calls, each resending the full context. Set the wait above the
expected duration. Same for background shells in other tools.

**TD-06.** `cmd > /tmp/x.log 2>&1; echo $?; tail -n 40 /tmp/x.log` or a grep for
`FAIL|ERROR`, never the full log.

**TD-07.** Codex documents Fast mode as consuming plan limits at 2.5x. With
`approvals_reviewer = auto_review`, model reviews of escalations cost ~15% of
a day's tokens in the case study. Check the effective value in the session
log: an IDE setting can override the config file.

**TD-08.** Subagents start with their own context and inherit the parent's
model/effort unless configured. Several Codex issues report limits drained by
subagents. Delegate only when work is independent or needs a clean context.

**TD-09.** Each escalation is a round trip (and, with model reviewers, an
extra model call). Open the project folder as the workspace and allow the
notes folder as a writable root if it lives elsewhere.

**TD-10.** In the case study, switching the executor from a top model at high
effort to a cheaper model at medium effort took a task from 100% of the
5-hour limit (unfinished) to 8% (approved by review). Quality gates did not
change.

**TD-11.** Rediscovering PATH, containers and test commands costs several
calls per session. Record them once in project notes.

**TD-12.** A current-state file that grows with history becomes an
always-read file that keeps getting bigger.
