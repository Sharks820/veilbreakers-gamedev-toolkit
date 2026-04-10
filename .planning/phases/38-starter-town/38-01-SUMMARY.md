---
phase: "38"
plan: "01"
status: partial
started: "2026-04-09"
completed: "2026-04-09"
tests_before: 21301
tests_after: 21301
commits:
  - "7d59438 feat(38): hearthvale settlement perimeter_props wiring + 9 tests"
  - "1533c77 fix(settlement): add building_count_override + shallow-copy config dict"
---

# Phase 38 Plan 01: Hearthvale Starter Town — Summary

## Tasks Completed

### Task 1: Hearthvale Town Profile + Building Type Registration ✓
- Registered "hearthvale" settlement type in SETTLEMENT_TYPES
- All 9 building types mapped in _BUILDING_ROOMS and _BUILDING_FOOTPRINTS
- Fixed generate_concentric_districts to respect perimeter_props config (portcullis_gate bug)
- Added building_count_override param to generate_settlement
- Shallow-copy config dict to prevent global mutation
- 9 tests in TestHearthvale class all passing

### Task 2-5: Require Blender/Unity Runtime ⏳
- Task 2: Generate town via pipeline + market square + sewer entrance — needs Blender
- Task 3: Visual QA pass + issue resolution — needs Blender viewport
- Task 4: Performance profiling + optimization — needs Blender + Unity
- Task 5: Unity export + Addressables packaging — needs Unity

## Success Criteria

- [x] SC-1: generate_settlement("hearthvale", seed=3810) returns 14 buildings
- [x] SC-2: All 9 building type registrations present
- [ ] SC-3: Contact sheet shows zero visual defects (needs Blender)
- [ ] SC-4: Fortress walls imposing 5-6m (needs Blender)
- [ ] SC-5: 5+ Tripo market stalls (needs Blender + Tripo API)
- [ ] SC-6: Sewer entrance placed (needs Blender)
- [ ] SC-7: All 14 buildings pass game_check (needs Blender)
- [ ] SC-8: LODs generated (needs Blender)
- [ ] SC-9: Per-district FBX exports (needs Blender export)
- [ ] SC-10: >= 60fps at 1080p (needs Unity profiler)
- [ ] SC-11: Load time < 5s (needs Unity profiler)
