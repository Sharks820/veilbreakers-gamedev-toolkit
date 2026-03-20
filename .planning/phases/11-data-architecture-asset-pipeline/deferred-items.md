# Deferred Items - Phase 11

## Pre-existing Test Failure

- **File:** `tests/test_data_templates.py::TestJsonConfig::test_json_validator_with_schema`
- **Issue:** Test asserts `monster_id` in result but the generated validator does not include it
- **Origin:** Plan 11-01 (data_templates.py)
- **Discovered during:** Plan 11-02 full suite regression check
- **Impact:** Does not affect pipeline_templates functionality
