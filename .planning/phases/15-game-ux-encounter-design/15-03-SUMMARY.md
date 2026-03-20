---
phase: 15-game-ux-encounter-design
plan: 03
subsystem: gameplay
tags: [encounter, ai-director, boss-ai, monte-carlo, fsm, wave-spawning, scriptable-object]

# Dependency graph
requires:
  - phase: 12-core-game-systems
    provides: "gameplay_templates.py mob controller FSM pattern"
  - phase: 13-equipment-content-progression
    provides: "content_templates.py encounter simulator pattern"
provides:
  - "encounter_templates.py with 4 generators for encounter scripting, AI director, simulation, boss AI"
  - "generate_encounter_system_script: SO wave definitions + trigger volume manager"
  - "generate_ai_director_script: AnimationCurve-driven difficulty adjustment"
  - "generate_encounter_simulator_script: Monte Carlo EditorWindow with statistical analysis"
  - "generate_boss_ai_script: multi-phase hierarchical FSM with enrage"
affects: [15-game-ux-encounter-design, tool-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns: [SO-wave-definitions, coroutine-wave-spawning, AnimationCurve-difficulty, Monte-Carlo-simulation, hierarchical-boss-FSM, pending-phase-transition]

key-files:
  created:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/encounter_templates.py
    - Tools/mcp-toolkit/tests/test_encounter_templates.py
  modified: []

key-decisions:
  - "Encounter system returns 2-tuple (wave SO, manager) for separate file output"
  - "AI director uses sliding window of last 5 encounters for moving averages"
  - "Encounter simulator uses EditorApplication.update with per-frame batching for non-blocking Monte Carlo"
  - "Boss AI queues phase transitions via _pendingTransition flag to avoid interrupting attacks"
  - "Phase count clamped to 2-5 range for boss AI generator"
  - "DamageCalculator stub follows VB delegation pattern for boss damage calculation"

patterns-established:
  - "Queued phase transitions: _pendingTransition flag prevents mid-animation state changes"
  - "Per-frame simulation batching: EditorApplication.update += callback for non-blocking editor computation"
  - "Phase attack sets: List<PhaseAttackSet> for per-phase boss attack repertoire"

requirements-completed: [AID-01, AID-02, AID-03, VB-10]

# Metrics
duration: 8min
completed: 2026-03-20
---

# Phase 15 Plan 03: Encounter Templates Summary

**4 encounter/AI generators: SO wave definitions with trigger volume spawning, AnimationCurve-driven AI director, Monte Carlo encounter simulator EditorWindow, and multi-phase boss FSM with HP thresholds + enrage timer**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-20T19:36:28Z
- **Completed:** 2026-03-20T19:44:31Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created encounter_templates.py with 4 generators (1310 lines) for complete encounter/AI system code generation
- Encounter system produces ScriptableObject wave definitions + MonoBehaviour manager with trigger volumes, coroutine spawning, fog gates, and 5 UnityEvents
- AI director tracks deaths, clear time, and damage ratio with sliding window averages; maps difficulty score to AnimationCurve-based spawn rate and stat multipliers
- Monte Carlo simulator runs N configurable encounter simulations with per-frame batching, reports win rate, clear time (mean + std dev), DPS stats, and difficulty recommendation
- Boss AI generates multi-phase hierarchical FSM with configurable phase count (2-5), HP threshold transitions, enrage timer, per-phase attack pattern sets, and DamageCalculator delegation
- Comprehensive test suite with 98 tests across 4 test classes covering all generators

## Task Commits

Each task was committed atomically:

1. **Task 1: Create encounter_templates.py with 4 encounter/AI generators** - `5e228fe` (feat)
2. **Task 2: Create test_encounter_templates.py with tests for all 4 generators** - `b080a00` (test)

## Files Created/Modified
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/encounter_templates.py` - 4 generators: encounter system, AI director, encounter simulator, boss AI
- `Tools/mcp-toolkit/tests/test_encounter_templates.py` - 98 tests across 4 test classes

## Decisions Made
- Encounter system returns 2-tuple (wave SO, manager) following existing multi-file generator pattern (content_templates.py)
- AI director uses sliding window of last 5 encounters for moving averages to smooth difficulty adjustments
- Encounter simulator uses EditorApplication.update with per-frame batching (_batchSize=50) for non-blocking Monte Carlo execution
- Boss AI queues phase transitions via _pendingTransition flag, executing on next idle state to avoid interrupting attack animations
- Phase count clamped to 2-5 range to keep generated code manageable while allowing customization
- DamageCalculator stub follows VB delegation pattern (boss AI delegates damage calculation to static utility class)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- encounter_templates.py ready for tool wiring in 15-04-PLAN.md
- All 4 generators importable and tested with 98 passing tests
- Patterns consistent with existing template modules (line-based concatenation, _sanitize_cs_string, optional namespace)

## Self-Check: PASSED

All files and commits verified:
- encounter_templates.py: FOUND
- test_encounter_templates.py: FOUND
- 15-03-SUMMARY.md: FOUND
- Commit 5e228fe: FOUND
- Commit b080a00: FOUND

---
*Phase: 15-game-ux-encounter-design*
*Completed: 2026-03-20*
