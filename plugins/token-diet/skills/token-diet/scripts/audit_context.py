#!/usr/bin/env python3
"""How much instruction text is loaded into EVERY session of a project?

Always-loaded text is paid on every model call of every session (TD-03). This
script lists the instruction files the common tools load at session start for
a given folder, follows @imports, and flags files over the size caps.

Covered (only files that exist are reported):
  - AGENTS.md chain: from the git root (or the folder) down to the folder,
    plus ~/.codex/AGENTS.md            (Codex, Cursor, many others)
  - CLAUDE.md / CLAUDE.local.md chain + ~/.claude/CLAUDE.md, with @imports
    followed recursively                (Claude Code)
  - .claude/rules/*.md without a `paths:` frontmatter (always loaded)
  - .cursor/rules/*.mdc with `alwaysApply: true`
  - Skill frontmatter (name + description): only this part is loaded until a
    skill is used, so it is measured separately.

Token figures are ESTIMATES (bytes / 4). They are good for comparing before
and after a change, not for billing.

Usage: audit_context.py [folder] [--json] [--max-always KB]
"""
import argparse
import glob
import json
import os
import re
import sys

CAPS = {'instruction_file': 8 * 1024, 'skill_md_lines': 500, 'description_chars': 1024}
IMPORT_RE = re.compile(r'(?:^|\s)@((?:~|\.{1,2})?/?[\w./-]+\.md)\b')


def git_root(d):
    cur = d
    while True:
        if os.path.exists(os.path.join(cur, '.git')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return d
        cur = parent


def chain(root, folder):
    """Directories from root down to folder (inclusive)."""
    rel = os.path.relpath(folder, root)
    dirs = [root]
    if rel != '.':
        cur = root
        for part in rel.split(os.sep):
            cur = os.path.join(cur, part)
            dirs.append(cur)
    return dirs


def size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def follow_imports(path, seen, depth=0):
    """Claude Code @imports, followed up to 5 levels deep."""
    out = []
    if depth > 5:
        return out
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return out
    text = re.sub(r'```.*?```', '', text, flags=re.S)  # imports inside code blocks are not evaluated
    for m in IMPORT_RE.finditer(text):
        ref = os.path.expanduser(m.group(1))
        target = ref if os.path.isabs(ref) else os.path.normpath(os.path.join(os.path.dirname(path), ref))
        if os.path.isfile(target) and target not in seen:
            seen.add(target)
            out.append((target, 'import of ' + os.path.basename(path)))
            out += follow_imports(target, seen, depth + 1)
    return out


def frontmatter(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return {}, ''
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ':' in line and not line.startswith(' '):
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip().strip('"\'')
    return fm, text


def collect(folder):
    folder = os.path.realpath(folder)
    root = git_root(folder)
    home = os.path.expanduser('~')
    items = {'codex/agents': [], 'claude': [], 'cursor': []}
    seen = set()

    def add(group, path, why):
        rp = os.path.realpath(path)
        if os.path.isfile(rp) and (group, rp) not in seen:
            seen.add((group, rp))
            items[group].append({'path': path, 'why': why, 'bytes': size(rp)})
            return True
        return False

    codex_home = os.environ.get('CODEX_HOME', os.path.join(home, '.codex'))
    for name in ('AGENTS.override.md', 'AGENTS.md'):
        if add('codex/agents', os.path.join(codex_home, name), 'global'):
            break
    for d in chain(root, folder):
        for name in ('AGENTS.override.md', 'AGENTS.md'):
            if add('codex/agents', os.path.join(d, name), 'project chain'):
                break

    claude_files = [(os.path.join(home, '.claude', 'CLAUDE.md'), 'global')]
    for d in chain(root, folder):
        for name in ('CLAUDE.md', os.path.join('.claude', 'CLAUDE.md'), 'CLAUDE.local.md'):
            claude_files.append((os.path.join(d, name), 'project chain'))
    imp_seen = set()
    for path, why in claude_files:
        if add('claude', path, why):
            for target, w in follow_imports(path, imp_seen):
                add('claude', target, w)
    for p in sorted(glob.glob(os.path.join(root, '.claude', 'rules', '**', '*.md'), recursive=True)):
        fm, _ = frontmatter(p)
        if 'paths' not in fm:
            add('claude', p, 'rule without paths:')

    for p in sorted(glob.glob(os.path.join(root, '.cursor', 'rules', '**', '*.mdc'), recursive=True)):
        fm, _ = frontmatter(p)
        if fm.get('alwaysApply', '').lower() == 'true':
            add('cursor', p, 'alwaysApply: true')
    add('cursor', os.path.join(root, '.cursorrules'), 'legacy .cursorrules')

    skills = []
    skill_dirs = [os.path.join(root, '.claude', 'skills'), os.path.join(root, '.agents', 'skills'),
                  os.path.join(home, '.claude', 'skills'), os.path.join(home, '.agents', 'skills')]
    sk_seen = set()
    for sd in skill_dirs:
        for p in sorted(glob.glob(os.path.join(sd, '*', 'SKILL.md'))):
            rp = os.path.realpath(p)
            if rp in sk_seen:
                continue
            sk_seen.add(rp)
            fm, text = frontmatter(p)
            skills.append({'path': p, 'name': fm.get('name', ''), 'description_chars': len(fm.get('description', '')),
                           'lines': text.count('\n') + 1, 'bytes': size(rp)})
    return {'folder': folder, 'root': root, 'always_loaded': items, 'skills': skills}


def problems(report, max_always):
    out = []
    for group, files in report['always_loaded'].items():
        total = sum(f['bytes'] for f in files)
        if total > max_always:
            out.append(f'{group}: {total // 1024} KB loaded in every session (target <= {max_always // 1024} KB) — move detail to skills or on-demand docs (TD-03)')
        for f in files:
            if f['bytes'] > CAPS['instruction_file']:
                out.append(f"{f['path']}: {f['bytes'] // 1024} KB (cap {CAPS['instruction_file'] // 1024} KB)")
    for s in report['skills']:
        if s['lines'] > CAPS['skill_md_lines']:
            out.append(f"{s['path']}: {s['lines']} lines (Agent Skills guidance: < {CAPS['skill_md_lines']}) — split into references/")
        if not s['name'] or not s['description_chars']:
            out.append(f"{s['path']}: missing name or description in frontmatter")
        elif s['description_chars'] > CAPS['description_chars']:
            out.append(f"{s['path']}: description {s['description_chars']} chars (max {CAPS['description_chars']})")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder', nargs='?', default='.')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--max-always', type=int, default=16, help='KB of always-loaded text per tool (default 16)')
    a = ap.parse_args(argv)
    rep = collect(a.folder)
    rep['problems'] = problems(rep, a.max_always * 1024)
    if a.json:
        json.dump(rep, sys.stdout, indent=2)
        print()
        return 0
    print(f"Folder: {rep['folder']}  (repo root: {rep['root']})\n")
    for group, files in rep['always_loaded'].items():
        if not files:
            continue
        total = sum(f['bytes'] for f in files)
        print(f'[{group}] always loaded: {total:,} bytes ≈ {total // 4:,} tokens (estimate)')
        for f in files:
            print(f"  {f['bytes']:>8,}  {f['path']}  ({f['why']})")
        print()
    if rep['skills']:
        desc = sum(s['description_chars'] for s in rep['skills'])
        print(f"[skills] {len(rep['skills'])} skills; descriptions ≈ {desc // 4:,} tokens always visible, bodies load on use")
        print()
    if rep['problems']:
        print('Findings:')
        for p in rep['problems']:
            print('  - ' + p)
    else:
        print('No size findings.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
