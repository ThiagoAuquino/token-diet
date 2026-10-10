"""Tests with synthetic transcripts only (no real session logs).

Run: python3 -m unittest discover -s tests
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'plugins', 'token-diet', 'skills', 'token-diet', 'scripts')
sys.path.insert(0, SCRIPTS)

import analyze_sessions  # noqa: E402
import audit_context  # noqa: E402
import session_guard  # noqa: E402
import td_transcripts  # noqa: E402

GUARD = os.path.join(SCRIPTS, 'session_guard.py')


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r) + '\n')


def codex_rows(contexts, cwd='/work/app', tier=None, reviewer='user'):
    rows = [
        {'timestamp': '2026-10-01T10:00:00Z', 'type': 'session_meta', 'payload': {'cwd': cwd, 'source': 'vscode'}},
        {'timestamp': '2026-10-01T10:00:01Z', 'type': 'turn_context', 'payload': {'model': 'model-a'}},
        {'timestamp': '2026-10-01T10:00:01Z', 'type': 'event_msg',
         'payload': {'type': 'thread_settings_applied',
                     'thread_settings': {'approvals_reviewer': reviewer, 'service_tier': tier}}},
    ]
    total = 0
    for i, c in enumerate(contexts):
        total += c
        info = {'last_token_usage': {'input_tokens': c, 'cached_input_tokens': int(c * 0.9), 'output_tokens': 100},
                'total_token_usage': {'input_tokens': total}}
        ev = {'timestamp': f'2026-10-01T10:{i + 1:02d}:00Z', 'type': 'event_msg',
              'payload': {'type': 'token_count', 'info': info}}
        rows += [ev, ev]  # duplicates must be ignored
        rows.append({'timestamp': ev['timestamp'], 'type': 'response_item',
                     'payload': {'type': 'function_call', 'name': 'exec_command', 'arguments': '{"cmd":"sleep 5"}'}})
    return rows


def claude_rows(contexts, text_last='done', cwd='/work/app'):
    rows = [{'type': 'user', 'sessionId': 's1', 'cwd': cwd, 'timestamp': '2026-10-02T09:00:00Z',
             'message': {'role': 'user', 'content': 'hi'}}]
    for i, c in enumerate(contexts):
        for part in range(2):  # one request split in two entries
            rows.append({
                'type': 'assistant', 'sessionId': 's1', 'cwd': cwd, 'requestId': f'req{i}',
                'timestamp': f'2026-10-02T09:{i + 1:02d}:0{part}Z',
                'message': {'id': f'msg{i}', 'model': 'claude-x',
                            'content': [{'type': 'text', 'text': text_last if i == len(contexts) - 1 else 'step'}],
                            'usage': {'input_tokens': 10, 'cache_creation_input_tokens': 1000,
                                      'cache_read_input_tokens': c - 1010, 'output_tokens': 50}}})
    return rows


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_codex_parse_dedupes_and_flags(self):
        p = os.path.join(self.tmp, 'rollout-1.jsonl')
        write_jsonl(p, codex_rows([50000, 120000, 60000], tier='priority', reviewer='auto_review'))
        self.assertEqual(td_transcripts.detect_tool(p), 'codex')
        r = td_transcripts.summarize(td_transcripts.parse(p))
        self.assertEqual(r['calls'], 3)
        self.assertEqual(r['input_tokens'], 230000)
        self.assertEqual(r['ctx_peak'], 120000)
        self.assertEqual(r['compactions'], 1)
        self.assertEqual(r['sleeps'], 3)
        rules = {k for k, _ in analyze_sessions.findings(r, analyze_sessions.DEF)}
        self.assertTrue({'TD-07', 'TD-03', 'TD-02'} <= rules)

    def test_claude_parse_dedupes_request_id(self):
        p = os.path.join(self.tmp, 's1.jsonl')
        write_jsonl(p, claude_rows([20000, 30000]))
        self.assertEqual(td_transcripts.detect_tool(p), 'claude')
        r = td_transcripts.summarize(td_transcripts.parse(p))
        self.assertEqual(r['calls'], 2)
        self.assertEqual(r['input_tokens'], 50000)

    def test_garbage_is_ignored(self):
        p = os.path.join(self.tmp, 'bad.jsonl')
        with open(p, 'w') as fh:
            fh.write('not json\n{}\n')
        self.assertIsNone(td_transcripts.parse(p))
        self.assertEqual(td_transcripts.session_input_total(p), (None, None))

    def test_analyze_cli_json(self):
        p = os.path.join(self.tmp, 'rollout-2.jsonl')
        write_jsonl(p, codex_rows([10000, 20000]))
        buf = io.StringIO()
        with redirect_stdout(buf):
            analyze_sessions.main([p, '--json'])
        data = json.loads(buf.getvalue())
        self.assertEqual(data['sessions'][0]['input_tokens'], 30000)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, 'proj')
        os.makedirs(os.path.join(self.proj, 'sub'))
        self.env = dict(os.environ, TOKEN_DIET_STATE=os.path.join(self.tmp, 'state'),
                        XDG_CONFIG_HOME=os.path.join(self.tmp, 'noconfig'))
        self.transcript = os.path.join(self.tmp, 't.jsonl')
        write_jsonl(self.transcript, codex_rows([100000, 150000]))

    def run_guard(self, payload):
        out = subprocess.run([sys.executable, GUARD], input=json.dumps(payload), text=True,
                             capture_output=True, env=self.env, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def config(self, **kw):
        cfg = {'session_guard': dict({'enabled': True, 'max_session_input_tokens': 1000000}, **kw)}
        with open(os.path.join(self.proj, '.token-diet.json'), 'w') as fh:
            json.dump(cfg, fh)

    def base(self, event, **kw):
        d = {'hook_event_name': event, 'session_id': 'abc', 'cwd': os.path.join(self.proj, 'sub'),
             'transcript_path': self.transcript}
        d.update(kw)
        return d

    def test_disabled_without_config(self):
        self.assertIsNone(self.run_guard(self.base('UserPromptSubmit', prompt='x')))
        self.assertEqual(self.run_guard(self.base('Stop', last_assistant_message='Next step — Git')), {})

    def test_close_then_block_then_bypass(self):
        self.config()
        self.assertIsNone(self.run_guard(self.base('UserPromptSubmit', prompt='task')))
        self.assertEqual(self.run_guard(self.base('Stop', last_assistant_message='...\n## Next step — Git\n...')), {})
        out = self.run_guard(self.base('UserPromptSubmit', prompt='another task'))
        self.assertEqual(out['decision'], 'block')
        self.assertIsNone(self.run_guard(self.base('UserPromptSubmit', prompt='commit it #same-session')))

    def test_budget_asks_checkpoint_once(self):
        self.config(max_session_input_tokens=200000)
        first = self.run_guard(self.base('Stop', last_assistant_message='working'))
        self.assertEqual(first['decision'], 'block')
        self.assertIn('checkpoint', first['reason'])
        again = self.run_guard(self.base('Stop', last_assistant_message='still working'))
        self.assertEqual(again, {})
        blocked = self.run_guard(self.base('UserPromptSubmit', prompt='more'))
        self.assertEqual(blocked['decision'], 'block')

    def test_claude_marker_from_transcript(self):
        self.config()
        t = os.path.join(self.tmp, 'c.jsonl')
        write_jsonl(t, claude_rows([5000], text_last='All green.\nNext step — Git: git add a.py'))
        self.assertEqual(self.run_guard(self.base('Stop', transcript_path=t)), {})
        out = self.run_guard(self.base('UserPromptSubmit', prompt='next', transcript_path=t))
        self.assertEqual(out['decision'], 'block')

    def test_fail_open_on_bad_input(self):
        out = subprocess.run([sys.executable, GUARD], input='not json', text=True,
                             capture_output=True, env=self.env, timeout=30)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), '')

    def test_broken_config_disables(self):
        with open(os.path.join(self.proj, '.token-diet.json'), 'w') as fh:
            fh.write('{broken')
        self.assertIsNone(self.run_guard(self.base('UserPromptSubmit', prompt='x')))


class AuditTests(unittest.TestCase):
    def test_reports_imports_and_caps(self):
        tmp = tempfile.mkdtemp()
        fake_home = tempfile.mkdtemp()
        old = {k: os.environ.get(k) for k in ('HOME', 'CODEX_HOME')}
        os.environ['HOME'] = fake_home
        os.environ.pop('CODEX_HOME', None)
        self.addCleanup(lambda: [os.environ.__setitem__(k, v) if v is not None else os.environ.pop(k, None) for k, v in old.items()])
        os.makedirs(os.path.join(tmp, '.git'))
        os.makedirs(os.path.join(tmp, '.claude', 'skills', 'big'))
        os.makedirs(os.path.join(tmp, '.cursor', 'rules'))
        with open(os.path.join(tmp, 'AGENTS.md'), 'w') as fh:
            fh.write('x' * 9000)
        with open(os.path.join(tmp, 'CLAUDE.md'), 'w') as fh:
            fh.write('See @AGENTS.md\n```\n@ignored.md\n```\n')
        with open(os.path.join(tmp, '.cursor', 'rules', 'a.mdc'), 'w') as fh:
            fh.write('---\nalwaysApply: true\n---\nrule\n')
        with open(os.path.join(tmp, '.claude', 'skills', 'big', 'SKILL.md'), 'w') as fh:
            fh.write('---\nname: big\ndescription: d\n---\n' + 'line\n' * 600)
        rep = audit_context.collect(tmp)
        claude_paths = [os.path.basename(f['path']) for f in rep['always_loaded']['claude']]
        self.assertEqual(claude_paths, ['CLAUDE.md', 'AGENTS.md'])
        self.assertEqual(len(rep['always_loaded']['cursor']), 1)
        probs = '\n'.join(audit_context.problems(rep, 16 * 1024))
        self.assertIn('AGENTS.md', probs)
        self.assertIn('lines', probs)


if __name__ == '__main__':
    unittest.main()
