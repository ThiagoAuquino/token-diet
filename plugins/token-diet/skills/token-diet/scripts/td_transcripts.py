"""Shared transcript parsing for token-diet (Claude Code and OpenAI Codex).

Both tools write one JSONL file per session. Neither format is a stable public
interface, so every parser here is defensive: unknown lines are skipped and a
file that cannot be parsed yields an empty result instead of an exception.

Formats handled (as observed in 2026):

- Claude Code: ~/.claude/projects/<project-slug>/<session-id>.jsonl
  Assistant entries carry message.usage with input_tokens,
  cache_creation_input_tokens, cache_read_input_tokens and output_tokens.
  One API request can be split across several entries with the same
  requestId, so usage is de-duplicated by requestId (or message.id).
- Codex: ${CODEX_HOME:-~/.codex}/sessions/YYYY/MM/DD/rollout-*.jsonl
  event_msg entries of type token_count carry info.last_token_usage (the call
  just made) and info.total_token_usage (running session total).
"""
import json
import os

POLL_TOOL_NAMES = {'wait', 'wait_agent', 'BashOutput', 'TaskOutput'}


def detect_tool(path):
    """Return 'codex', 'claude' or None by sniffing the first lines."""
    try:
        with open(path, encoding='utf-8') as fh:
            for i, line in enumerate(fh):
                if i > 50:
                    break
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get('type') in ('session_meta', 'turn_context', 'event_msg', 'response_item'):
                    return 'codex'
                if 'sessionId' in obj or obj.get('type') in ('user', 'assistant', 'summary'):
                    return 'claude'
    except OSError:
        return None
    return None


def _new_session(path, tool):
    return {
        'file': path, 'tool': tool, 'cwd': None, 'start': None, 'end': None,
        'models': set(), 'is_subagent': False, 'calls': [],
        'tool_calls': 0, 'polls': 0, 'sleeps': 0, 'escalations': 0,
        'approvals_reviewer': None, 'service_tier': None, 'session_total_input': None,
    }


def parse_codex(path):
    s = _new_session(path, 'codex')
    try:
        fh = open(path, encoding='utf-8')
    except OSError:
        return s
    with fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            ts = obj.get('timestamp')
            if ts:
                s['start'] = s['start'] or ts
                s['end'] = ts
            t = obj.get('type')
            p = obj.get('payload') or {}
            pt = p.get('type')
            if t == 'session_meta':
                s['cwd'] = p.get('cwd') or s['cwd']
                src = p.get('source')
                if isinstance(src, dict) and 'subagent' in src:
                    s['is_subagent'] = True
            elif t == 'turn_context':
                if p.get('model'):
                    s['models'].add(p.get('model'))
            elif t == 'event_msg' and pt == 'thread_settings_applied':
                ts_ = p.get('thread_settings') or {}
                s['approvals_reviewer'] = ts_.get('approvals_reviewer') or s['approvals_reviewer']
                s['service_tier'] = ts_.get('service_tier') or s['service_tier']
            elif t == 'event_msg' and pt == 'token_count' and p.get('info'):
                info = p['info']
                last = info.get('last_token_usage') or {}
                total = info.get('total_token_usage') or {}
                call = {
                    'context': last.get('input_tokens') or 0,
                    'cached': last.get('cached_input_tokens') or 0,
                    'output': last.get('output_tokens') or 0,
                }
                # token_count can repeat for the same call; keep only changes.
                if total.get('input_tokens') != s['session_total_input']:
                    s['calls'].append(call)
                    s['session_total_input'] = total.get('input_tokens')
            elif t == 'response_item' and pt in ('custom_tool_call', 'function_call'):
                s['tool_calls'] += 1
                name = p.get('name') or ''
                args = str(p.get('input') or p.get('arguments') or '')
                if name in POLL_TOOL_NAMES or ('write_stdin' in args and 'chars:""' in args and 'exec_command' not in args):
                    s['polls'] += 1
                if 'sleep ' in args or name == 'sleep':
                    s['sleeps'] += 1
                if 'require_escalated' in args:
                    s['escalations'] += 1
    return s


def parse_claude(path):
    s = _new_session(path, 'claude')
    seen = set()
    try:
        fh = open(path, encoding='utf-8')
    except OSError:
        return s
    with fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            ts = obj.get('timestamp')
            if ts:
                s['start'] = s['start'] or ts
                s['end'] = ts
            s['cwd'] = s['cwd'] or obj.get('cwd')
            if obj.get('isSidechain'):
                s['is_subagent'] = True
            if obj.get('type') != 'assistant':
                continue
            msg = obj.get('message') or {}
            if msg.get('model'):
                s['models'].add(msg['model'])
            for block in msg.get('content') or []:
                if isinstance(block, dict) and block.get('type') == 'tool_use':
                    s['tool_calls'] += 1
                    name = block.get('name') or ''
                    cmd = json.dumps(block.get('input') or {})
                    if name in POLL_TOOL_NAMES:
                        s['polls'] += 1
                    if name == 'Bash' and 'sleep ' in cmd:
                        s['sleeps'] += 1
            usage = msg.get('usage')
            key = obj.get('requestId') or msg.get('id')
            if not usage or key in seen:
                continue
            seen.add(key)
            ctx = (usage.get('input_tokens') or 0) + (usage.get('cache_creation_input_tokens') or 0) \
                + (usage.get('cache_read_input_tokens') or 0)
            s['calls'].append({
                'context': ctx,
                'cached': usage.get('cache_read_input_tokens') or 0,
                'output': usage.get('output_tokens') or 0,
            })
    return s


def parse(path, tool=None):
    tool = tool or detect_tool(path)
    if tool == 'codex':
        return parse_codex(path)
    if tool == 'claude':
        return parse_claude(path)
    return None


def summarize(s):
    """Numbers per session. Context = tokens sent in one model call."""
    calls = s['calls']
    ctxs = [c['context'] for c in calls]
    total_in = sum(ctxs)
    cached = sum(c['cached'] for c in calls)
    compactions = sum(1 for a, b in zip(ctxs, ctxs[1:]) if a > 30000 and b < a * 0.6)
    return {
        'file': s['file'], 'tool': s['tool'], 'cwd': s['cwd'],
        'start': s['start'], 'end': s['end'],
        'models': sorted(s['models']), 'subagent': s['is_subagent'],
        'calls': len(calls), 'input_tokens': total_in,
        'cached_pct': round(100.0 * cached / total_in, 1) if total_in else 0.0,
        'output_tokens': sum(c['output'] for c in calls),
        'ctx_first': ctxs[0] if ctxs else 0,
        'ctx_avg': int(total_in / len(ctxs)) if ctxs else 0,
        'ctx_peak': max(ctxs) if ctxs else 0,
        'compactions': compactions,
        'tool_calls': s['tool_calls'], 'polls': s['polls'], 'sleeps': s['sleeps'],
        'escalations': s['escalations'],
        'approvals_reviewer': s['approvals_reviewer'], 'service_tier': s['service_tier'],
    }


def session_input_total(path):
    """Fast path used by the session guard: (total input tokens, last context)."""
    s = parse(path)
    if not s or not s['calls']:
        return None, None
    return sum(c['context'] for c in s['calls']), s['calls'][-1]['context']


def default_roots():
    roots = []
    claude = os.path.expanduser('~/.claude/projects')
    codex = os.path.join(os.environ.get('CODEX_HOME', os.path.expanduser('~/.codex')), 'sessions')
    if os.path.isdir(claude):
        roots.append(('claude', claude))
    if os.path.isdir(codex):
        roots.append(('codex', codex))
    return roots
