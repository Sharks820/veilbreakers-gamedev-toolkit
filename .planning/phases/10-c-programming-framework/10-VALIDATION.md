---
phase: 10
slug: c-programming-framework
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | Tools/mcp-toolkit/pyproject.toml |
| **Quick run command** | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd Tools/mcp-toolkit && python -m pytest tests/ -v` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Status |
|---------|------|------|-------------|-----------|--------|
| 10-01-01 | 01 | 1 | CODE-01/02/03 | unit | ⬜ pending |
| 10-01-02 | 01 | 1 | CODE-01/02/03 | unit | ⬜ pending |
| 10-02-01 | 02 | 1 | CODE-04/05/06-10 | unit | ⬜ pending |
| 10-02-02 | 02 | 1 | CODE-04/05/06-10 | unit | ⬜ pending |
| 10-03-01 | 03 | 2 | SHDR-01/02 | unit | ⬜ pending |
| 10-03-02 | 03 | 2 | SHDR-01/02 | unit | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/test_code_templates.py` — stubs for CODE-01 through CODE-10
- [ ] `tests/test_shader_advanced_templates.py` — stubs for SHDR-01, SHDR-02

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Generated C# compiles in Unity | CODE-01 | Requires Unity Editor | Open Unity, check Console for compile errors |
| Editor windows render correctly | CODE-03 | Requires Unity Editor | Open generated window via menu |
| Tests run in Unity Test Runner | CODE-05 | Requires Unity Editor | Run tests in Test Runner window |
| Shaders compile on GPU | SHDR-01 | Requires Unity + GPU | Check shader for pink material |

---

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Sampling continuity maintained
- [ ] Wave 0 covers all MISSING references
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
