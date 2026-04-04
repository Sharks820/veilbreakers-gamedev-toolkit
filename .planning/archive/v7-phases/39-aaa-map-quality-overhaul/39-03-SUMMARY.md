---
phase: 39-pipeline-systemic-fixes
plan: 03
subsystem: animation
tags: [smoothstep, interpolation, easing, animation-quality, s-curve]
dependency_graph:
  requires:
    - phase: 39-01
      provides: "_shared_utils.py smoothstep function (missing -- created as deviation)"
  provides:
    - smoothstep blending in all 5 animation handler files
    - _shared_utils.py with Hermite smoothstep function
  affects: [animation_gaits.py, animation_combat.py, animation_monster.py, animation_environment.py, animation_locomotion.py]
tech_stack:
  added: []
  patterns:
    - "Central smoothstep() import from _shared_utils for S-curve blending"
    - "Replace inline t*t*(3-2*t) with smoothstep(t) function calls"
    - "Replace linear * t blend weights with smoothstep(t) for natural easing"
key_files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/animation_gaits.py
    - Tools/mcp-toolkit/blender_addon/handlers/animation_combat.py
    - Tools/mcp-toolkit/blender_addon/handlers/animation_monster.py
    - Tools/mcp-toolkit/blender_addon/handlers/animation_environment.py
    - Tools/mcp-toolkit/blender_addon/handlers/animation_locomotion.py
key-decisions:
  - "Created _shared_utils.py as deviation (Rule 3) since Plan 01 did not create it"
  - "Replaced 37 sites total (exceeds target of 35) including inline smoothstep patterns"
  - "Used smoothstep for blend weights only, preserved sin/cos oscillation patterns"
patterns-established:
  - "All animation interpolation uses smoothstep() from _shared_utils for S-curve easing"
requirements-completed: [PIPE-06]
duration: 8min
completed: "2026-04-04"
---

# Phase 39 Plan 03: Smoothstep Animation Interpolation Summary

**Replaced 37 linear interpolation sites across 5 animation handlers with smoothstep() for natural ease-in-ease-out blending, all 1146 animation tests pass.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-04T12:10:51Z
- **Completed:** 2026-04-04T12:19:49Z
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- All 5 animation handler files now import and use smoothstep() from _shared_utils
- 37 interpolation sites replaced (target was 35): linear `* t`, quadratic `t*t`, cubic `t*t*t`, and inline `t*t*(3-2*t)` patterns
- Animations now have natural ease-in-ease-out S-curve blending instead of robotic linear interpolation
- All 1146 animation tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace linear interpolations in gaits, combat, monster** - `75488f0` (feat)
2. **Task 2: Replace linear interpolations in environment, locomotion** - `9253dec` (feat)

## Files Created/Modified

- `Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py` - New module with Hermite smoothstep function (3t^2 - 2t^3, clamped)
- `Tools/mcp-toolkit/blender_addon/handlers/animation_gaits.py` - 6 smoothstep usage sites (phase blending, hit reactions, bell curves)
- `Tools/mcp-toolkit/blender_addon/handlers/animation_combat.py` - 7 smoothstep usage sites (violent fall, explosive thigh/arm decay)
- `Tools/mcp-toolkit/blender_addon/handlers/animation_monster.py` - 4 smoothstep usage sites (scatter damping, converge, phase shift vanish/appear)
- `Tools/mcp-toolkit/blender_addon/handlers/animation_environment.py` - 8 smoothstep usage sites (door slam/creak, gate raise/lower, drawbridge, trap, chest)
- `Tools/mcp-toolkit/blender_addon/handlers/animation_locomotion.py` - 12 smoothstep usage sites (jump, land, knockdown, getup, dodge roll, weapon draw/sheathe, plunge)

## Decisions Made

- Created `_shared_utils.py` as a deviation (Rule 3: blocking issue) because Plan 01 did not create the file despite the plan referencing it
- Replaced 37 sites instead of 35: found 2 additional inline smoothstep patterns that should use the function call for consistency
- Applied smoothstep only to blend weights and easing curves, preserved sin/cos oscillation frequencies and damping envelopes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created missing _shared_utils.py module**
- **Found during:** Task 1 (before any replacements)
- **Issue:** Plan references `from ._shared_utils import smoothstep` but the file did not exist (Plan 01 was supposed to create it)
- **Fix:** Created `_shared_utils.py` with the smoothstep() Hermite function as specified in the plan interface section
- **Files created:** Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py
- **Verification:** All imports resolve, all tests pass
- **Committed in:** 75488f0 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for task execution. No scope creep.

## Issues Encountered

None.

## Known Stubs

None - all smoothstep replacements are complete and functional.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All animation handlers now use consistent smoothstep blending
- The _shared_utils.py module is available for future shared utilities
- Ready for remaining Phase 39 plans (39-04)

## Self-Check: PASSED

- All 7 files verified present on disk
- Both task commits (75488f0, 9253dec) found in git history

---
*Phase: 39-pipeline-systemic-fixes*
*Completed: 2026-04-04*
