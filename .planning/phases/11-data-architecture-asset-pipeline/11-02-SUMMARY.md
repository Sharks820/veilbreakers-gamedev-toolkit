---
phase: 11-data-architecture-asset-pipeline
plan: 02
subsystem: asset-pipeline
tags: [git-lfs, normal-map-baking, sprite-atlas, asset-postprocessor, blender-python, unity-editor-scripts]

# Dependency graph
requires:
  - phase: 09-editor-deep-control
    provides: asset_templates.py module pattern and sanitization helpers
provides:
  - generate_gitlfs_config and generate_gitignore for Unity project setup
  - generate_normal_map_bake_script for Blender high-to-low normal baking
  - generate_sprite_atlas_script and generate_sprite_animation_script for sprite workflows
  - generate_sprite_editor_config_script for pivot, 9-slice, physics shapes
  - generate_asset_postprocessor_script for automated import pipelines
affects: [11-data-architecture-asset-pipeline, unity-assets-tool-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns: [folder-convention-based-import-rules, blender-python-code-generation, v1-spriteatlas-api]

key-files:
  created:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/pipeline_templates.py
    - Tools/mcp-toolkit/tests/test_pipeline_templates.py
  modified: []

key-decisions:
  - "Use .spriteatlas V1 API extension for stable programmatic atlas creation"
  - "Normal map bake generates Blender Python (not C#) for blender_execute execution"
  - "AssetPostprocessor uses OnPreprocess callbacks exclusively to avoid infinite reimport loops"
  - ".asset files excluded from Git LFS tracking since Unity Force Text stores them as YAML"
  - "Folder-convention import rules use assetPath.Contains() for flexible path matching"

patterns-established:
  - "Pipeline template module: same sanitization-copy pattern as asset_templates.py"
  - "AssetPostprocessor always includes GetVersion() override for reimport detection"
  - "C# setting maps: Python dicts map setting names to (property, formatter) tuples for code gen"

requirements-completed: [IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08]

# Metrics
duration: 8min
completed: 2026-03-20
---

# Phase 11 Plan 02: Pipeline Templates Summary

**Git LFS config, normal map baking workflow, SpriteAtlas V1 creation, Sprite Editor configuration, and AssetPostprocessor generation with 72 unit tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-20T11:38:26Z
- **Completed:** 2026-03-20T11:46:46Z
- **Tasks:** 2/2
- **Files created:** 2

## Accomplishments
- Created pipeline_templates.py with 7 public template generators covering 5 requirements
- Git LFS configuration generates .gitattributes (LFS tracking) and .gitignore (Unity standard) with configurable extensions
- Normal map bake generates Blender Python code with cage mesh generation, Cycles setup, and selected-to-active baking
- Sprite workflows: SpriteAtlas V1 creation with packing/texture/platform settings, AnimationClip from frame sprites
- AssetPostprocessor uses OnPreprocess callbacks with GetVersion and configurable folder-convention rules
- 72 unit tests across 5 test classes covering all acceptance criteria

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pipeline_templates.py** - `25c43aa` (feat)
2. **Task 2: Create unit tests** - `4cde464` (test)

## Files Created/Modified
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/pipeline_templates.py` - 7 template generators for asset pipeline automation
- `Tools/mcp-toolkit/tests/test_pipeline_templates.py` - 72 unit tests across 5 test classes
- `.planning/phases/11-data-architecture-asset-pipeline/deferred-items.md` - Pre-existing test failure documentation

## Decisions Made
- Used SpriteAtlas V1 API (.spriteatlas extension) for stable programmatic creation, avoiding V2 native crash issues
- Normal map bake script generates pure Blender Python (bpy/mathutils only) for blender_execute compatibility
- AssetPostprocessor exclusively uses OnPreprocess callbacks to prevent infinite reimport loops
- Excluded .asset files from Git LFS since Unity Force Text serialization stores them as YAML text
- Used assetPath.Contains() for folder pattern matching in postprocessor rules for flexible path conventions
- Setting maps use (property, formatter) tuples enabling clean code generation from Python dicts to C# assignments

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failure in `test_data_templates.py::TestJsonConfig::test_json_validator_with_schema` from plan 11-01. Not related to pipeline_templates changes. Documented in deferred-items.md per scope boundary rules.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Pipeline template module ready for MCP tool wiring in future plans
- All 7 generators importable and tested
- Follows same pattern as asset_templates.py for consistent codebase

## Self-Check: PASSED

- [x] pipeline_templates.py exists
- [x] test_pipeline_templates.py exists
- [x] 11-02-SUMMARY.md exists
- [x] Commit 25c43aa found
- [x] Commit 4cde464 found
- [x] All 72 tests passing
- [x] No regressions in full test suite (excluding pre-existing failure)

---
*Phase: 11-data-architecture-asset-pipeline*
*Completed: 2026-03-20*
