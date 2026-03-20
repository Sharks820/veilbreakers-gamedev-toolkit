---
phase: 11-data-architecture-asset-pipeline
plan: 01
subsystem: data-architecture
tags: [scriptable-object, json-validation, localization, editor-window, unity, c-sharp-codegen]

# Dependency graph
requires:
  - phase: 10-csharp-programming-framework
    provides: "generate_class SO support, EditorWindow generation, _sanitize_cs_string/_sanitize_cs_identifier helpers"
provides:
  - "generate_so_definition: ScriptableObject class definitions with CreateAssetMenu"
  - "generate_asset_creation_script: .asset file instantiation via CreateInstance + CreateAsset"
  - "generate_json_validator_script: JSON config schema validation with required/min/max/pattern checks"
  - "generate_json_loader_script: Typed C# data classes with Resources.Load JSON deserialization"
  - "generate_localization_setup_script: Unity Localization locale assets + string table collections"
  - "generate_localization_entries_script: String table entry population"
  - "generate_data_authoring_window: IMGUI EditorWindow for batch SO asset authoring"
affects: [11-02, 11-03, 11-04, unity_data-tool-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns: [so-definition-template, asset-creation-template, json-validator-template, json-loader-template, localization-setup-template, data-authoring-window-template]

key-files:
  created:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/data_templates.py
    - Tools/mcp-toolkit/tests/test_data_templates.py
  modified: []

key-decisions:
  - "Auto-generate wrapper class when schema provided without explicit wrapper_class to avoid silent no-op validation"
  - "Self-contained data_templates.py with local sanitization copies following established module isolation pattern"
  - "IMGUI (OnGUI) for data authoring windows matching existing VeilBreakers editor tools"

patterns-established:
  - "SO definition template: namespace, CreateAssetMenu, Header/Tooltip attributes, field defaults"
  - "Asset creation template: folder creation, CreateInstance, Undo registration, result JSON"
  - "JSON validator template: schema-driven required/min/max/pattern checks with VB_ValidationResult"
  - "Data authoring window template: asset discovery via FindAssets, inline SerializedObject editing"

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04]

# Metrics
duration: 8min
completed: 2026-03-20
---

# Phase 11 Plan 01: Data Architecture Templates Summary

**7 template generators for SO definitions, JSON validation/loading, Unity Localization setup, and IMGUI data authoring windows with 43 unit tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-20T11:38:42Z
- **Completed:** 2026-03-20T11:47:19Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created data_templates.py with 7 public exports covering all DATA requirements (DATA-01 through DATA-04)
- ScriptableObject definitions generate complete C# classes with CreateAssetMenu, Header/Tooltip attributes, and namespace support
- JSON validator scripts validate required fields, type checks, min/max ranges, and regex patterns with auto-generated wrapper classes
- Localization generators create Unity Localization infrastructure (locale assets, string table collections, entry population)
- Data authoring EditorWindow generates IMGUI-based batch creation/editing tools with asset discovery, inline editing, and delete support
- 43 unit tests across 4 test classes covering all 4 DATA requirements, all passing
- Full test suite: 3546 passed, 0 failed (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create data_templates.py with SO, JSON, localization, and data authoring generators** - `29a8c59` (feat)
2. **Task 2: Create unit tests for DATA-01 through DATA-04** - `70a8215` (test)

## Files Created/Modified
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/data_templates.py` - 7 template generators for data-driven game architecture (SO definitions, asset creation, JSON validation/loading, localization, data authoring)
- `Tools/mcp-toolkit/tests/test_data_templates.py` - 43 unit tests across 4 test classes (TestScriptableObjectAssets, TestJsonConfig, TestLocalization, TestDataAuthoring)

## Decisions Made
- Auto-generate wrapper class name (e.g. MonsterDataWrapper) when schema is provided but no explicit wrapper_class, preventing silent validation skip
- Self-contained module with local _sanitize_cs_string/_sanitize_cs_identifier copies per established pattern (avoids circular imports)
- IMGUI (OnGUI) approach for data authoring windows matching existing VeilBreakers editor tools

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JSON validator skipped schema validation without wrapper class**
- **Found during:** Task 2 (unit testing)
- **Issue:** generate_json_validator_script with schema but no wrapper_class fell through to basic "is empty" check, ignoring all schema validation rules
- **Fix:** Auto-generate wrapper class name when schema provided (e.g. "{config_name}Wrapper")
- **Files modified:** data_templates.py
- **Verification:** test_json_validator_with_schema now passes, validates field names and constraints
- **Committed in:** 70a8215 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- data_templates.py ready for wiring into unity_data compound tool (future plan)
- All 7 generators produce valid C# that can be written to Unity projects
- Template pattern consistent with existing 14 template modules in shared/unity_templates/

## Self-Check: PASSED

- [x] data_templates.py exists
- [x] test_data_templates.py exists
- [x] 11-01-SUMMARY.md exists
- [x] Commit 29a8c59 found (Task 1)
- [x] Commit 70a8215 found (Task 2)

---
*Phase: 11-data-architecture-asset-pipeline*
*Completed: 2026-03-20*
