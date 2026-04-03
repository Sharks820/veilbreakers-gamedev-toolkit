# Phase 40: Test Suite Overhaul

## Goal
Fix the 63% false confidence in the test suite so we can verify all subsequent bug fixes. Without real assertions, fixing 730 bugs means nothing — tests will say PASS regardless.

## Key Stats
- 12,459 total tests, 7,855 (63%) provide false confidence
- 46 tests with zero assertions
- 7,289 tests with weak-only assertions
- 4,817 `assert "key" in result` that never check values
- 5,276 generator tests that never check geometry
- Zero integration tests for compose_map, compose_interior, export roundtrip

## Scope
1. Add real assertions to the most critical weak tests (focus on generators, pipeline, materials)
2. Add integration tests for the 5 critical pipelines
3. Fix 46 zero-assertion tests
4. Add tests that would catch our top 15 bugs
5. Fix test reliability issues (random seeds, hardcoded paths)

## Files
- `Tools/mcp-toolkit/tests/` — all test files
- `Tools/mcp-toolkit/tests/test_integration_pipelines.py` — 62 new tests already written

## Research
- `.planning/MASTER_IMPLEMENTATION_LIST.md` Phase 1 section
- Agent 50 test audit results

## Success Criteria
- All existing tests still pass
- New integration tests pass
- Zero-assertion tests fixed or removed
- Top 15 bugs have dedicated tests
- Tests run in < 60 seconds
