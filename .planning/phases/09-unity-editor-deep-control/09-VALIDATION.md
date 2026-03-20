---
phase: 9
slug: unity-editor-deep-control
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | Tools/mcp-toolkit/pyproject.toml |
| **Quick run command** | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `cd Tools/mcp-toolkit && python -m pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `cd Tools/mcp-toolkit && python -m pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | EDIT-01 | unit | `pytest tests/test_unity_hierarchy.py -k prefab` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | EDIT-02 | unit | `pytest tests/test_unity_hierarchy.py -k component` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | EDIT-03 | unit | `pytest tests/test_unity_hierarchy.py -k hierarchy` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | EDIT-04 | unit | `pytest tests/test_unity_settings.py -k physics` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 1 | EDIT-05 | unit | `pytest tests/test_unity_settings.py -k player` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 1 | EDIT-06 | unit | `pytest tests/test_unity_settings.py -k build` | ❌ W0 | ⬜ pending |
| 09-02-04 | 02 | 1 | EDIT-07 | unit | `pytest tests/test_unity_settings.py -k quality` | ❌ W0 | ⬜ pending |
| 09-02-05 | 02 | 1 | EDIT-08 | unit | `pytest tests/test_unity_settings.py -k package` | ❌ W0 | ⬜ pending |
| 09-02-06 | 02 | 1 | EDIT-09 | unit | `pytest tests/test_unity_settings.py -k tag` | ❌ W0 | ⬜ pending |
| 09-02-07 | 02 | 1 | EDIT-11 | unit | `pytest tests/test_unity_settings.py -k time_graphics` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 2 | EDIT-10 | unit | `pytest tests/test_unity_assets.py -k asset_ops` | ❌ W0 | ⬜ pending |
| 09-03-02 | 03 | 2 | EDIT-12 | unit | `pytest tests/test_unity_assets.py -k fbx_import` | ❌ W0 | ⬜ pending |
| 09-03-03 | 03 | 2 | EDIT-13 | unit | `pytest tests/test_unity_assets.py -k texture_import` | ❌ W0 | ⬜ pending |
| 09-03-04 | 03 | 2 | EDIT-14 | unit | `pytest tests/test_unity_assets.py -k material_remap` | ❌ W0 | ⬜ pending |
| 09-03-05 | 03 | 2 | EDIT-15 | unit | `pytest tests/test_unity_assets.py -k asmdef` | ❌ W0 | ⬜ pending |
| 09-03-06 | 03 | 2 | IMP-01 | unit | `pytest tests/test_unity_assets.py -k guid` | ❌ W0 | ⬜ pending |
| 09-03-07 | 03 | 2 | IMP-02 | unit | `pytest tests/test_unity_assets.py -k material_remap` | ❌ W0 | ⬜ pending |
| 09-03-08 | 03 | 2 | PIPE-09 | unit | `pytest tests/test_unity_assets.py -k preset` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_unity_hierarchy.py` — stubs for EDIT-01, EDIT-02, EDIT-03, PHYS-01, PHYS-02, EQUIP-02
- [ ] `tests/test_unity_settings.py` — stubs for EDIT-04 through EDIT-09, EDIT-11
- [ ] `tests/test_unity_assets.py` — stubs for EDIT-10, EDIT-12 through EDIT-15, IMP-01, IMP-02, PIPE-09

*Existing test infrastructure (pytest, conftest.py) covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prefab opens in Prefab Mode | EDIT-01 | Requires live Unity Editor | Open generated .prefab in Unity, verify Prefab Mode loads |
| Hierarchy changes persist after scene save | EDIT-03 | Requires live Unity Editor | Save scene, reopen, verify hierarchy |
| Unity reflects Player/Quality settings | EDIT-05/07 | Requires live Unity Editor | Check Project Settings window |
| Package installs via UPM | EDIT-08 | Requires live Unity Editor | Check Package Manager window |
| FBX reimports correctly | EDIT-12 | Requires live Unity Editor | Import FBX, check Inspector |

*All manual verifications require a running Unity Editor instance.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
