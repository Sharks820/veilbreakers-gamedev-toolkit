---
phase: 11
slug: data-architecture-asset-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 11 — Validation Strategy

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
- **Max feedback latency:** 30 seconds

---

## Wave 0 Requirements

- [ ] `tests/test_data_templates.py` — stubs for DATA-01 through DATA-04
- [ ] `tests/test_pipeline_templates.py` — stubs for IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08
- [ ] `tests/test_aaa_templates.py` — stubs for AAA-01 through AAA-04, AAA-06

---

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
