---
phase: 16-quality-assurance-testing
plan: 02
subsystem: testing
tags: [unity, profiler, test-runner, memory-leak, static-analysis, c-sharp-codegen]

requires:
  - phase: 16-01
    provides: "Unity TCP bridge foundation (qa_templates.py with bridge generators)"
provides:
  - "5 QA template generators: test runner, play session, profiler, memory leak detector, static analysis"
  - "Python-side C# static analysis scanner with 6 anti-pattern rules"
affects: [16-03, 16-04, unity_qa tool wiring]

tech-stack:
  added: [ProfilerRecorder, TestRunnerApi, ICallbacks, NavMeshAgent]
  patterns: [line-based C# template generation, Python regex static analysis, brace-counting method tracking]

key-files:
  created: []
  modified:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/qa_templates.py
    - Tools/mcp-toolkit/tests/test_qa_templates.py

key-decisions:
  - "ProfilerRecorder.StartNew() for frame time/draw calls/memory sampling -- programmatic access vs UnityStats"
  - "Python-side regex static analyzer vs Roslyn DLLs -- simpler, works at code-gen time, no build dependency"
  - "Brace-counting method body tracker for hot method detection -- simple but effective for single-file analysis"
  - "new_allocation pattern regex includes <[ for generic type constructors (new List<int>)"

patterns-established:
  - "ANTI_PATTERNS module-level dict for extensible static analysis rules"
  - "Hot method detection via brace-depth tracking and _HOT_METHODS frozenset"
  - "Memory leak detection via baseline/sample/compare pattern with configurable threshold"

requirements-completed: [QA-01, QA-02, QA-03, QA-04, QA-05]

duration: 23min
completed: 2026-03-20
---

# Phase 16 Plan 02: QA Template Generators Summary

**5 QA generators (test runner, play session, profiler, memory leak detector, static analyzer) with ProfilerRecorder sampling, coroutine-based play sessions, and Python regex anti-pattern detection**

## Performance

- **Duration:** 23 min
- **Started:** 2026-03-20T22:09:01Z
- **Completed:** 2026-03-20T22:32:04Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Test runner handler using TestRunnerApi + ICallbacks with EditMode/PlayMode/Both support and structured JSON output
- Automated play session script with coroutine-based step processing (move_to, interact, wait, verify_state) and NavMeshAgent integration
- GPU/CPU profiler using ProfilerRecorder.StartNew() for 5 metrics over N frames with min/avg/max and budget comparison
- Memory leak detector with managed/native heap baseline snapshots, interval sampling, growth rate computation, and configurable leak threshold
- Python-side static analysis scanner detecting 6 anti-patterns (Camera.main, GetComponent, FindObjectOfType, string concat, LINQ, new allocation) only in hot method bodies

## Task Commits

Each task was committed atomically:

1. **Task 1: Test runner, play session, and profiler generators** - `7b6a903` (feat)
2. **Task 2: Memory leak detector and static analysis scanner** - `82bf1a4` (feat)

## Files Created/Modified
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/qa_templates.py` - Added 5 new generator functions + ANTI_PATTERNS dict + analyze_csharp_static Python function
- `Tools/mcp-toolkit/tests/test_qa_templates.py` - Added 120 new tests across 8 test classes (TestTestRunner, TestTestRunnerPlayMode, TestPlaySession, TestPlaySessionCustomSteps, TestProfiler, TestProfilerCustomBudgets, TestMemoryLeak, TestMemoryLeakCustom, TestStaticAnalysis)

## Decisions Made
- Used ProfilerRecorder.StartNew() instead of UnityStats for profiler -- provides programmatic access to Main Thread, Draw Calls Count, SetPass Calls Count, System Used Memory, and Triangles Count
- Python-side regex scanner instead of Roslyn analyzers -- simpler implementation, works at code-gen time without build toolchain dependency
- Brace-counting approach for detecting which method body a line belongs to -- pragmatic for single-file analysis without full AST parsing
- Fixed new_allocation_in_update regex from `\w+[\[\(]` to `\w+[<\[\(]` to match generic type constructors like `new List<int>()`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing closing paren on lines.extend() call**
- **Found during:** Task 1
- **Issue:** The `lines.extend([` call in generate_test_runner_handler was closed with `]` instead of `])`, causing a SyntaxError
- **Fix:** Changed `]` to `])` to properly close both the list and the function call
- **Files modified:** qa_templates.py
- **Verification:** Python syntax check passes, all tests pass
- **Committed in:** 7b6a903

**2. [Rule 1 - Bug] Fixed new_allocation regex pattern for generic types**
- **Found during:** Task 2
- **Issue:** Pattern `\bnew\s+\w+[\[\(]` did not match `new List<int>(100)` because `<` was not in the character class
- **Fix:** Changed pattern to `\bnew\s+\w+[<\[\(]` to include angle bracket
- **Files modified:** qa_templates.py
- **Verification:** test_new_in_update passes
- **Committed in:** 82bf1a4

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes were necessary for correctness. No scope creep.

## Issues Encountered
- External tool (parallel agent for Plan 03) concurrently modified qa_templates.py and test_qa_templates.py, adding crash reporting/analytics/live inspector generators. This caused temporary import conflicts and added extra test classes. Resolved by accommodating the additional imports since the functions existed in the module.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 5 QA generators ready for tool wiring in Plan 04
- Static analyzer can be invoked directly from Python without Unity connection
- Test runner, play session, profiler, and memory leak generators produce C# scripts for Unity Editor

---
*Phase: 16-quality-assurance-testing*
*Completed: 2026-03-20*
