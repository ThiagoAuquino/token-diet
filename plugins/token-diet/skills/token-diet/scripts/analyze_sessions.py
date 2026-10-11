#!/usr/bin/env python3
"""Where did the tokens go? Per-session report for Claude Code and Codex logs.

Reads local session transcripts (nothing is sent anywhere) and prints, per
session: model, calls, total input tokens, cached share, context size (first /
average / peak), compactions, polling waits, and findings with the matching
playbook rule (TD-xx).

Usage:
  analyze_sessions.py                       # newest 10 sessions from default roots
  analyze_sessions.py --since 2026-10-01 --project my-repo
  analyze_sessions.py path/to/session.jsonl [...]
  analyze_sessions.py --json                # machine-readable
  analyze_sessions.py --last 1 --top 5      # what filled the context (biggest tool outputs)

Default roots: ~/.claude/projects and ${CODEX_HOME:-~/.codex}/sessions.
"Input tokens" = sum over model calls of the tokens sent in that call
(including cached tokens). Each call resends the whole context, so this is the
number that grows when sessions get long. How a plan meters it differs per
vendor (e.g. cached input billed at a discount); compare sessions of the same
tool with each other, not across tools.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import td_transcripts as tt  # noqa: E402

# Thresholds for findings. Defaults come from the measured case study
# (docs/case-study.md); override with flags.
DEF = {'first_ctx': 40000, 'peak_ctx': 150000, 'polls': 5, 'session_input': 3500000}


def find_files(paths, roots):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, '**', '*.jsonl'), recursive=True)
        elif os.path.isfile(p):
            files.append(p)
    if not paths:
        for _, root in roots:
            files += glob.glob(os.path.join(root, '**', '*.jsonl'), recursive=True)
    return files


def findings(r, th):
    out = []
    if r['service_tier'] in ('priority', 'fast'):
        out.append(('TD-07', f"service tier '{r['service_tier']}' (fast mode) — billed at a multiple of the normal rate"))
    if r['approvals_reviewer'] and r['approvals_reviewer'] != 'user':
        out.append(('TD-07', f"approvals reviewed by a model ('{r['approvals_reviewer']}') — every escalation costs a review call"))
    if r['ctx_first'] >= th['first_ctx']:
        out.append(('TD-03', f"first call already {r['ctx_first']:,} tokens — always-loaded instructions/handoff too big, or session reused"))
    if r['ctx_peak'] >= th['peak_ctx']:
        out.append(('TD-01', f"context peaked at {r['ctx_peak']:,} tokens — one task per session, checkpoint earlier"))
    if r['compactions']:
        out.append(('TD-02', f"{r['compactions']} compaction(s) — session ran past its useful size"))
    if r['polls'] + r['sleeps'] >= th['polls']:
        out.append(('TD-05', f"{r['polls']} polls + {r['sleeps']} sleeps — each wait resends the whole context; wait longer than the command takes"))
    if r['input_tokens'] >= th['session_input']:
        out.append(('TD-02', f"session input {r['input_tokens']:,} >= budget {th['session_input']:,}"))
    if r['escalations'] >= 10:
        out.append(('TD-09', f"{r['escalations']} sandbox escalations — open the project folder as the workspace"))
    return out


def human(n):
    for unit, div in (('M', 1e6), ('k', 1e3)):
        if n >= div:
            return f'{n / div:.1f}{unit}'
    return str(n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='*', help='session .jsonl files or folders (default: tool roots)')
    ap.add_argument('--since', help='only sessions starting on/after this ISO date (YYYY-MM-DD)')
    ap.add_argument('--project', help='only sessions whose working directory contains this text')
    ap.add_argument('--last', type=int, default=10, help='newest N sessions (default 10, 0 = all)')
    ap.add_argument('--include-subagents', action='store_true', help='list subagent sessions separately')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--top', type=int, default=0, help='show the N biggest tool outputs per session (what filled the context)')
    for k, v in DEF.items():
        ap.add_argument('--' + k.replace('_', '-'), type=int, default=v, dest=k)
    a = ap.parse_args(argv)

    rows = []
    for f in find_files(a.paths, tt.default_roots()):
        s = tt.parse(f)
        if not s or not s['calls']:
            continue
        r = tt.summarize(s)
        if a.since and (r['start'] or '') < a.since:
            continue
        if a.project and a.project not in (r['cwd'] or ''):
            continue
        rows.append(r)
    rows.sort(key=lambda r: r['start'] or '')
    main_rows = [r for r in rows if a.include_subagents or not r['subagent']]
    sub_total = sum(r['input_tokens'] for r in rows if r['subagent'])
    if a.last:
        main_rows = main_rows[-a.last:]
    th = {k: getattr(a, k) for k in DEF}
    for r in main_rows:
        r['findings'] = [{'rule': k, 'text': t} for k, t in findings(r, th)]

    if a.json:
        json.dump({'sessions': main_rows, 'subagent_input_tokens': sub_total}, sys.stdout, indent=2, default=str)
        print()
        return 0
    if not main_rows:
        print('No sessions found. Pass a .jsonl path or check ~/.claude/projects and ~/.codex/sessions.')
        return 0
    print(f"{'start':<17} {'tool':<6} {'model':<22} {'calls':>5} {'input':>7} {'cached':>6} "
          f"{'ctx 1st':>7} {'avg':>6} {'peak':>6} {'cmp':>3} {'polls':>5}")
    for r in main_rows:
        model = (','.join(r['models']) or '?')[:22]
        sub = '*' if r['subagent'] else ''
        print(f"{(r['start'] or '?')[:16]:<17} {r['tool'] + sub:<6} {model:<22} {r['calls']:>5} "
              f"{human(r['input_tokens']):>7} {r['cached_pct']:>5.0f}% {human(r['ctx_first']):>7} "
              f"{human(r['ctx_avg']):>6} {human(r['ctx_peak']):>6} {r['compactions']:>3} "
              f"{r['polls'] + r['sleeps']:>5}")
        for fd in r['findings']:
            print(f"    {fd['rule']}: {fd['text']}")
        if a.top:
            print(f"    what stays in the context (estimates, chars/4): tool outputs ≈{human(r['tool_output_chars'] // 4)}, "
                  f"tool inputs written by the model (code, edits, commands) ≈{human(r['tool_input_chars'] // 4)}, "
                  f"model output tokens {human(r['output_tokens'])}")
            for title, key in (('biggest tool outputs', 'top_tool_outputs'), ('biggest tool inputs', 'top_tool_inputs')):
                if r[key]:
                    print(f"    {title}:")
                    for o in r[key][:a.top]:
                        print(f"      {human(o['chars'] // 4):>6}  {o['tool']}")
    if sub_total:
        print(f"\nSubagent sessions in range: {human(sub_total)} input tokens (TD-08; --include-subagents to list).")
    print('\nRules: see skills/token-diet/references/playbook.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
