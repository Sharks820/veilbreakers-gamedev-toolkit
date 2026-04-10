---
phase: "38"
status: human_needed
verified: "2026-04-09"
verifier: opus
score: 2/11
---

# Phase 38: Starter Town — Verification

## Must-Have Verification

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | generate_settlement("hearthvale") returns 14 buildings | ✓ PASS | test_hearthvale_generates_14_buildings |
| 2 | All 9 building type registrations | ✓ PASS | test_hearthvale_building_types_all_mapped |
| 3 | Contact sheet zero visual defects | ○ NEEDS BLENDER | Requires Blender viewport |
| 4 | Fortress walls 5-6m | ○ NEEDS BLENDER | Requires visual verification |
| 5 | 5+ Tripo market stalls | ○ NEEDS BLENDER+TRIPO | Requires Tripo API + Blender |
| 6 | Sewer entrance placed | ○ NEEDS BLENDER | Requires Blender placement |
| 7 | All 14 buildings game_check | ○ NEEDS BLENDER | Requires mesh validation |
| 8 | LODs generated | ○ NEEDS BLENDER | Requires LOD pipeline |
| 9 | Per-district FBX exports | ○ NEEDS BLENDER | Requires export pipeline |
| 10 | >= 60fps at 1080p | ○ NEEDS UNITY | Requires Unity profiler |
| 11 | Load time < 5s | ○ NEEDS UNITY | Requires Unity profiler |

## Human Verification Items

The following items require Blender and/or Unity to be running:

1. **Generate Hearthvale in Blender** — Run `blender_worldbuilding action=generate_hearthvale seed=3810`
2. **Generate Tripo market stalls** — 5 stalls + fountain + sewer entrance via `asset_pipeline action=generate_3d`
3. **Visual QA** — Contact sheet at 6 angles, fix floating objects / z-fighting
4. **Game check** — Run `blender_mesh action=game_check` on all 14 buildings
5. **LOD generation** — `asset_pipeline action=generate_lods` for buildings + stalls
6. **Export** — Per-district FBX via `asset_pipeline action=generate_map_package`
7. **Unity import** — `unity_world action=setup_map_streaming` + performance profiling
