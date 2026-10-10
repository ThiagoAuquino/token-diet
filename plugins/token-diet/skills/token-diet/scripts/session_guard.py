#!/usr/bin/env python3
"""token-diet session guard: one task per session, with a token budget.

Hook for Claude Code and OpenAI Codex, events UserPromptSubmit and Stop.

- Stop: if a line of the agent's last answer starts with a close marker
  (default: "Next step — Git"), the session is marked closed. A marker quoted
  mid-sentence (e.g. in a plan) does not count. If the session went over
  its token budget and has not closed, the agent is asked ONCE to write a
  checkpoint and close.
- UserPromptSubmit: a new prompt in a closed or over-budget session is blocked
  with "open a new session". Including the bypass token (default "#same-session")
  in the prompt lets it through.

OPT-IN: the guard does nothing until a config file with "enabled": true exists:
  1. .token-diet.json in the session's working directory or any parent, or
  2. $TOKEN_DIET_CONFIG, or ~/.config/token-diet/config.json (global).
The first file found wins. Keys not set fall back to DEFAULTS.

FAIL-OPEN: any error lets the prompt/turn through. A guard bug must never stop
someone's work. Transcript formats are not stable interfaces; if they change,
token measurement stops and only close markers keep working.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import td_transcripts  # noqa: E402

DEFAULTS = {
    'enabled': False,
    'max_session_input_tokens': 3500000,
    'max_context_tokens': None,
    'block_after_close': True,
    'close_markers': ['Next step — Git'],
    'bypass_token': '#same-session',
}
LOCAL_NAME = '.token-diet.json'


def state_dir():
    base = os.environ.get('TOKEN_DIET_STATE') or os.path.join(
        os.environ.get('XDG_STATE_HOME', os.path.expanduser('~/.local/state')), 'token-diet')
    return os.path.join(base, 'sessions')


def find_config(cwd):
    d = os.path.realpath(cwd or os.getcwd())
    while True:
        p = os.path.join(d, LOCAL_NAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    for p in (os.environ.get('TOKEN_DIET_CONFIG'),
              os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
                           'token-diet', 'config.json')):
        if p and os.path.isfile(p):
            return p
    return None


def load_config(cwd):
    cfg = dict(DEFAULTS)
    path = find_config(cwd)
    if not path:
        return cfg
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        guard = data.get('session_guard', data)
        cfg.update({k: v for k, v in guard.items() if not k.startswith('_')})
    except Exception:
        cfg['enabled'] = False
    return cfg


def state_path(session_id):
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', session_id or 'no-id')
    return os.path.join(state_dir(), safe + '.json')


def load_state(session_id):
    try:
        with open(state_path(session_id), encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_state(session_id, state):
    try:
        os.makedirs(state_dir(), exist_ok=True)
        with open(state_path(session_id), 'w', encoding='utf-8') as fh:
            json.dump(state, fh)
    except Exception:
        pass


def fmt(n):
    return f'{n:,}'


def over_budget(cfg, total, ctx):
    reasons = []
    limit = cfg.get('max_session_input_tokens')
    if limit and total is not None and total >= limit:
        reasons.append(f'session input tokens {fmt(total)} >= limit {fmt(limit)}')
    climit = cfg.get('max_context_tokens')
    if climit and ctx is not None and ctx >= climit:
        reasons.append(f'current context {fmt(ctx)} >= limit {fmt(climit)}')
    return reasons


def last_assistant_text(data):
    """Claude Code and Codex send last_assistant_message on Stop; fall back to the transcript."""
    msg = data.get('last_assistant_message')
    if isinstance(msg, str) and msg:
        return msg
    path = data.get('transcript_path')
    text = ''
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                if '"assistant"' not in line:
                    continue
                obj = json.loads(line)
                if obj.get('type') != 'assistant':
                    continue
                parts = [b.get('text', '') for b in (obj.get('message') or {}).get('content') or []
                         if isinstance(b, dict) and b.get('type') == 'text']
                if parts:
                    text = '\n'.join(parts)
    except Exception:
        pass
    return text


def marker_pattern(marker):
    """Marcador como regex; o separador " — " aceita também –, - e : (com ou sem espaços)."""
    parts = re.split(r'\s*[—–]\s*', marker)
    return r'\s*[—–:-]\s*'.join(re.escape(x) for x in parts)


def closes_task(msg, markers):
    """True if a line of the answer starts with a close marker (heading, bold or plain).

    Mentioning the marker mid-sentence ("at the end I'll add the Next step — Git block")
    does not close the session; only the block itself, starting a line, does.
    """
    for m in markers or []:
        if m and re.search(r'(?m)^[ \t]*(?:#{1,6}[ \t]+|>[ \t]*)?(?:\*\*|__)?' + marker_pattern(m), msg):
            return True
    return False


def handle(data):
    """Return the JSON object to print, or None to print nothing."""
    event = data.get('hook_event_name')
    cfg = load_config(data.get('cwd'))
    if not cfg.get('enabled'):
        return {} if event == 'Stop' else None

    sid = data.get('session_id')
    state = load_state(sid)
    total = ctx = None
    if data.get('transcript_path'):
        total, ctx = td_transcripts.session_input_total(data['transcript_path'])

    if event == 'Stop':
        msg = last_assistant_text(data)
        if closes_task(msg, cfg.get('close_markers')):
            state['closed'] = True
            save_state(sid, state)
            return {}
        reasons = over_budget(cfg, total, ctx)
        if reasons and not data.get('stop_hook_active') and not state.get('checkpoint_requested'):
            state['checkpoint_requested'] = True
            save_state(sid, state)
            marker = (cfg.get('close_markers') or ['Next step'])[0]
            return {
                'decision': 'block',
                'reason': (
                    'token-diet: session budget reached (' + '; '.join(reasons) + '). '
                    'Do not start new work. Write a checkpoint to the project memory/notes '
                    '(current state, what is left, next step), end your answer with the "'
                    + marker + '" block, and tell the user to continue in a new session.'
                ),
            }
        return {}

    if event == 'UserPromptSubmit':
        prompt = data.get('prompt') or ''
        bypass = cfg.get('bypass_token')
        if bypass and bypass in prompt:
            return None
        reasons = []
        if cfg.get('block_after_close') and state.get('closed'):
            reasons.append('the task in this session is already closed')
        reasons += over_budget(cfg, total, ctx)
        if reasons:
            return {
                'decision': 'block',
                'reason': (
                    'token-diet session guard: ' + '; '.join(reasons) + '. '
                    'Start a new session for the next request; it resumes from your project notes. '
                    'To force it here, include ' + (bypass or '#same-session') + ' in the prompt.'
                ),
            }
    return None


def main():
    try:
        data = json.load(sys.stdin)
        out = handle(data)
    except Exception:
        out = None
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
