---
phase: 15-game-ux-encounter-design
plan: 01
subsystem: ui
tags: [minimap, damage-numbers, primetween, textmeshpro, interaction-prompts, input-system, object-pool]

requires:
  - phase: 12-core-game-systems
    provides: "Input System config, PrimeTween patterns"
  - phase: 14-camera-cinematics-scene
    provides: "Camera templates pattern, world templates structure"
provides:
  - "6 UX template generators: minimap, damage numbers, interaction prompts, PrimeTween sequences, TMP font asset, TMP component"
  - "Orthographic camera + RenderTexture minimap with 1:1 positional tracking"
  - "PrimeTween UI animation utility with 8 presets (zero DOTween)"
  - "Object-pooled damage numbers with 10 VeilBreakers brand colors"
  - "Input System rebind-aware interaction prompts"
affects: [15-game-ux-encounter-design, 16-testing-integration, 17-polish-optimization]

tech-stack:
  added: [ux_templates.py]
  patterns: [PrimeTween-only animation, ObjectPool damage numbers, orthographic minimap camera, Input System GetBindingDisplayString]

key-files:
  created:
    - "Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/ux_templates.py"
    - "Tools/mcp-toolkit/tests/test_ux_templates.py"
  modified: []

key-decisions:
  - "PrimeTween-only policy enforced across all 6 generators (zero DOTween references)"
  - "10 VeilBreakers brand damage colors as static dictionary in generated C#"
  - "Minimap uses orthographic camera + RenderTexture + RawImage for true 1:1 positional accuracy"
  - "Interaction prompts use InputAction.GetBindingDisplayString() for dynamic rebind display"

patterns-established:
  - "PrimeTween UI animation: Sequence.Create().Group().Chain() for compound animations"
  - "ObjectPool<GameObject> pre-warming pattern for damage number recycling"
  - "World-to-viewport marker positioning for minimap POI icons"
  - "Billboard LookAt for world-space UI prompts"

requirements-completed: [UIX-01, UIX-03, UIX-04, SHDR-04, PIPE-10]

duration: 9min
completed: 2026-03-20
---

# Phase 15 Plan 01: UX Templates Summary

**6 UX template generators with PrimeTween animations, orthographic minimap camera, ObjectPool damage numbers, Input System rebind prompts, and TMP font asset/component setup (93 tests, 5611 total)**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-20T19:36:15Z
- **Completed:** 2026-03-20T19:45:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created ux_templates.py with 6 generators (1177 lines) following established line-based concatenation pattern
- Minimap generator produces orthographic camera + RenderTexture with 1:1 positional tracking, world-space markers, optional compass
- Damage numbers generator uses ObjectPool + PrimeTween Sequence.Create() with 10 VeilBreakers brand colors
- Interaction prompts use Input System GetBindingDisplayString() for dynamic rebind display with PrimeTween fade
- PrimeTween sequence generator provides 8 animation presets (panel entrance/exit, button hover, notification popup, screen shake, damage flash, item pickup, level up) with zero DOTween contamination
- TMP font asset and component setup generators with SDFAA rendering and fallback chain support
- 93 comprehensive tests covering all generators with DOTween contamination checks

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ux_templates.py with 6 core UX generators** - `8802af9` (feat)
2. **Task 2: Create test_ux_templates.py with tests for all 6 generators** - `5b78154` (test)

## Files Created/Modified
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/ux_templates.py` - 6 UX template generators (minimap, damage numbers, interaction prompts, PrimeTween sequences, TMP font asset, TMP component)
- `Tools/mcp-toolkit/tests/test_ux_templates.py` - 93 tests across 6 test classes

## Decisions Made
- PrimeTween-only policy: all generated C# uses Tween.*/Sequence.Create() exclusively, never DOTween
- 10 VeilBreakers brand damage colors defined as static dict (IRON gray, VENOM green, SURGE blue, DREAD purple, BLAZE orange, FROST cyan, VOID dark purple, HOLY gold, NATURE forest green, SHADOW dark gray)
- Minimap follows player with exact position (target.x, target.z) rather than smoothed/interpolated
- Interaction prompts include OnRebindComplete callback for rebinding integration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- UX template module ready for tool wiring in subsequent plans
- All 6 generators tested and verified against acceptance criteria
- PrimeTween-only policy enforced and tested (no DOTween contamination possible)

## Self-Check: PASSED

All files found, all commits verified.

---
*Phase: 15-game-ux-encounter-design*
*Completed: 2026-03-20*
