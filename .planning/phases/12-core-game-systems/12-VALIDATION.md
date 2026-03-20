---
phase: 12
slug: core-game-systems
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 12 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Quick run command** | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd Tools/mcp-toolkit && python -m pytest tests/ -v` |
| **Estimated runtime** | ~25 seconds |

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Max feedback latency:** 30 seconds

## Wave 0 Requirements

- [ ] `tests/test_game_templates.py` — stubs for GAME-01, GAME-05 through GAME-08, MEDIA-02, VB-01 through VB-07, RPG-03

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Feedback latency < 30s

**Approval:** pending
