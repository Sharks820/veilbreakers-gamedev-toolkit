---
phase: 16-quality-assurance-testing
plan: 03
subsystem: testing
tags: [sentry, analytics, telemetry, live-inspector, imgui, reflection, crash-reporting]

requires:
  - phase: 16-01
    provides: QA template module with bridge generators, _wrap_namespace, _sanitize_cs_string helpers
provides:
  - generate_crash_reporting_script: Sentry SDK init with DSN, breadcrumbs, fallback logging
  - generate_analytics_script: singleton event tracker with JSON flush and typed methods
  - generate_live_inspector_script: IMGUI EditorWindow with Reflection-based Play Mode inspection
affects: [16-04-tool-wiring]

tech-stack:
  added: [sentry-unity-sdk, json-file-logging]
  patterns: [sentry-sdk-init-pattern, singleton-monobehaviour-analytics, reflection-based-inspector]

key-files:
  created: []
  modified:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/qa_templates.py
    - Tools/mcp-toolkit/tests/test_qa_templates.py

key-decisions:
  - "SENTRY_AVAILABLE preprocessor guard for conditional Sentry SDK usage"
  - "Empty DSN triggers fallback console logging instead of runtime errors"
  - "Typed convenience methods generated from event_names list with PascalCase naming"
  - "Reflection-based field enumeration with BindingFlags.Public | BindingFlags.Instance"
  - "FSM state detection via currentState/_state field name convention"

patterns-established:
  - "Sentry conditional compilation: #if SENTRY_AVAILABLE wraps all SentrySdk calls"
  - "Analytics singleton: MonoBehaviour with DontDestroyOnLoad and Instance property"
  - "Event method generation: snake_case event names to PascalCase Track* methods"
  - "Live inspector polling: EditorApplication.update with frame counter interval"

requirements-completed: [QA-06, QA-07, QA-08]

duration: 19min
completed: 2026-03-20
---

# Phase 16 Plan 03: Crash Reporting, Analytics, and Live Inspector Summary

**Sentry crash reporting with DSN fallback, singleton analytics with typed event tracking and JSON flush, IMGUI live inspector with Reflection-based Play Mode component field polling**

## Performance

- **Duration:** 19 min
- **Started:** 2026-03-20T22:09:13Z
- **Completed:** 2026-03-20T22:29:23Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Crash reporting generator: Sentry SDK init with RuntimeInitializeOnLoadMethod, breadcrumbs via logMessageReceived, helper methods (CaptureException, CaptureMessage, SetTag, SetUser), empty DSN fallback
- Analytics generator: singleton MonoBehaviour with event buffering, JSON file flush, ISO 8601 timestamps, session management via Guid, typed convenience methods for 7 default events
- Live inspector generator: IMGUI EditorWindow with Reflection enumeration of public fields/properties, pinned object comparison, search filter, FSM state detection, Vector3/Color/bool formatting
- 78 new tests added (23 crash reporting, 24 analytics, 31 live inspector), 229 total passing in test_qa_templates.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Crash reporting, analytics, and live inspector generators** - `73c797a` (feat)

**Plan metadata:** `0113f05` (docs: complete plan)

## Files Created/Modified
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/qa_templates.py` - Added 3 new generator functions: generate_crash_reporting_script, generate_analytics_script, generate_live_inspector_script
- `Tools/mcp-toolkit/tests/test_qa_templates.py` - Added 78 new tests across TestCrashReporting, TestAnalytics, TestLiveInspector classes

## Decisions Made
- Used `#if SENTRY_AVAILABLE` preprocessor guard so generated C# compiles without Sentry package installed
- Empty DSN triggers fallback to Debug.Log/Debug.LogError instead of SentrySdk calls -- prevents runtime crashes when Sentry not configured
- Analytics uses typed convenience method generation from event_names list, converting snake_case to PascalCase (e.g., "enemy_killed" -> "TrackEnemyKilled")
- Live inspector uses BindingFlags.Public | BindingFlags.Instance for field/property enumeration, matching Unity's public field serialization convention
- FSM state detection uses field name convention ("currentState" or "_state") rather than interface/attribute matching

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Transient syntax error during test file creation caused by linter modifying imports between tool calls. Resolved by writing the complete file with all imports and test classes in a single Write operation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 3 observability generators ready for tool wiring in Plan 04
- Crash reporting, analytics, and live inspector complete the QA template generator suite
- Phase 16 ready for final tool wiring plan

## Self-Check: PASSED

- FOUND: qa_templates.py
- FOUND: test_qa_templates.py
- FOUND: 16-03-SUMMARY.md
- FOUND: commit 73c797a

---
*Phase: 16-quality-assurance-testing*
*Completed: 2026-03-20*
