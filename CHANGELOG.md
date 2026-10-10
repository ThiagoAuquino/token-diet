# Changelog

## 0.1.0 — 2026-10-10

First public version.

- `analyze_sessions.py`: per-session report for Claude Code and Codex logs
  with TD-rule findings.
- `audit_context.py`: always-loaded instruction audit (AGENTS.md, CLAUDE.md +
  imports, `.claude/rules`, `.cursor/rules`, skills).
- `session_guard.py`: opt-in one-task-per-session guard and token budget
  (Claude Code plugin hooks; Codex hooks template).
- Playbook TD-01…TD-12, improvement loop, case study and sources.
