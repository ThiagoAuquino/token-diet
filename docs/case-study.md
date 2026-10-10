# Case study: a 5-hour limit gone in 11 minutes

Real sessions of one developer using OpenAI Codex (VS Code extension) with a
multi-agent development framework (product owner, spec, engineer, reviewer
roles; extensive specs and rules) on a Laravel/React CRM, October 2026.
Numbers below are the output of `analyze_sessions.py` on the session logs,
plus the plan-limit percentage the tool showed. Logs are not published.

## Before

| Session | Model / effort | Input tokens | Context per call | Result |
|---|---|---|---|---|
| T-02 attempt | top model / high | 13.0M in the session file (~10.3M in the 11 minutes of the attempt), 97% cached | avg 151k, peak 201k | 5-hour limit 0 → 100%, task unfinished |

What the log showed:

- Several tasks in one long thread: context never went below ~170k (TD-01).
- The executor read the whole framework (standards, workflow, enforcement)
  before coding (TD-03, TD-04).
- 9 polls/sleeps waiting for commands and a subagent (TD-05).
- `service_tier = "priority"` (Fast mode, documented at 2.5x plan usage) and
  `approvals_reviewer = auto_review`: 22 escalations, each reviewed by a
  model (TD-07, TD-09).
- Subagents and review sessions: several hundred thousand tokens each (TD-08).

## Changes

1. One task per session, started from a task brief (context pack) that names
   the files, rules and commands needed (TD-01, TD-04).
2. Always-loaded instructions cut to a ~7 KB map; long docs split into
   sections read on demand; rules as plain `.md` usable by any tool (TD-03).
3. Executor model changed to a cheaper one at medium effort; the top model is
   kept for planning/spec work (TD-10).
4. Fast mode off; approvals reviewed by the user (TD-07).
5. Waits longer than the command; environment commands recorded in project
   notes (TD-05, TD-11).
6. Session guard: closed task or budget reached → next prompt asks for a new
   session (TD-01, TD-02).

## After

| Session | Model / effort | Duration | Plan limit | Input tokens | Context avg / peak | Result |
|---|---|---|---|---|---|---|
| T-02 | cheaper / medium | 10 min | 0 → 8% | 2.4M | 61k / 77k | approved by review |
| T-03 | cheaper / medium | 24 min | 8 → 21% | 4.1M (+ model reviewer ~1.2M) | 56k / 98k (1 compaction) | done |
| T-03 re-review | cheaper / medium | 2 min | +2 pts | 0.3M | — | approved |
| T-04 | cheaper / medium | 16 min | +10 pts | 2.9M (+ reviewer 0.3M) | — | approved |

- Per task: from "whole 5-hour limit, unfinished" to 8–13 points of it.
- Polling went from 10–11 waits per task to 4 after TD-05.
- The model approval reviewer disappeared from the logs once the IDE setting
  (which overrode the config file) was changed.

## Limits of this evidence

- One developer, one project, one tool. The direction is clear; the exact
  percentages will differ elsewhere.
- Several changes landed together, so the gain is not attributed to each
  change separately. The model/effort change and one-task-per-session had the
  largest visible effect on context size.
- Plan-limit percentages are what the tool displayed; vendors do not publish
  the exact metering formula.
