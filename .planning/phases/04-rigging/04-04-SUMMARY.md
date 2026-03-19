---
phase: 04-rigging
plan: 04
status: complete
completed: 2026-03-19
tests_passed: 0 new (482 total suite)
tool_count: 11 -> 12
handler_count: 56 (unchanged -- already registered in 04-03)
---

## What was built

### blender_server.py (modified)
- Added `blender_rig` compound MCP tool with 13 actions:
  - `analyze_mesh` -> `rig_analyze` (RIG-01): Returns JSON analysis, no screenshot
  - `apply_template` -> `rig_apply_template` (RIG-02): Returns screenshot
  - `build_custom` -> `rig_build_custom` (RIG-03): Returns screenshot
  - `setup_facial` -> `rig_setup_facial` (RIG-04): Returns screenshot
  - `setup_ik` -> `rig_setup_ik` (RIG-05): Returns screenshot
  - `setup_spring_bones` -> `rig_setup_spring_bones` (RIG-06): Returns screenshot
  - `auto_weight` -> `rig_auto_weight` (RIG-07): Returns screenshot
  - `test_deformation` -> `rig_test_deformation` (RIG-08): Always captures screenshot (contact sheet)
  - `validate` -> `rig_validate` (RIG-09): Returns JSON only, no screenshot
  - `fix_weights` -> `rig_fix_weights` (RIG-10): Returns screenshot
  - `setup_ragdoll` -> `rig_setup_ragdoll` (RIG-11): Returns screenshot
  - `retarget` -> `rig_retarget` (RIG-12): Returns JSON only, no screenshot
  - `add_shape_keys` -> `rig_add_shape_keys` (RIG-13): Returns screenshot
- Tool follows existing compound tool pattern (blender_mesh, blender_texture, etc.)
- No return type annotation (per project decision -- Pydantic cannot serialize MCP Image class)

### handlers/__init__.py (verified)
- All 13 rig handlers were already registered in COMMAND_HANDLERS from Plans 01-03
- 3 import blocks present: rigging (3 handlers), rigging_weights (4 handlers), rigging_advanced (6 handlers)
- Total COMMAND_HANDLERS: 56 entries (unchanged)

### test_blender_server_tools.py (modified)
- Updated tool count assertion from 11 to 12
- Added `test_blender_rig_registered` test verifying `blender_rig` is in MCP tool registry

## Key decisions
- Read-only actions (analyze_mesh, validate, retarget) return `json.dumps` only -- no screenshot overhead
- Mutation actions return `_with_screenshot` for visual verification
- `test_deformation` always captures screenshot (forces `capture_viewport=True`) since the contact sheet is its primary output
- All 13 dispatch keys match between blender_server.py send_command calls and __init__.py COMMAND_HANDLERS keys
