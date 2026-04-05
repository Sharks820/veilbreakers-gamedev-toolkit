# Terrain Branch Reviewer Metrics

- Branch: `feature/terrain-world-foundation`
- Base: `origin/master`
- Raw run: `C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit\review_reports\terrain_branch_20260404_rerun_raw.json`

## Summary

| Model | Total | Real | Other | False Positives | Strict Accuracy | Useful Signal |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemini-3.1-flash-lite-preview` | 25 | 4 | 14 | 7 | 16.0% | 72.0% |
| `qwen/qwen3.6-plus:free` | 19 | 4 | 7 | 8 | 21.1% | 57.9% |
| `nvidia/nemotron-3-super-120b-a12b:free` | 0 | 0 | 0 | 0 | n/a | n/a |

## Consensus Findings Shared By Gemini And Qwen

1. `C# Compilation Error in Tiled Terrain Script` in `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/scene_templates.py`
2. `Explicit World Anchors Bypass Boundary Clamping` in `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py`
3. `Brittle source-code-based API parameter verification` in `Tools/mcp-toolkit/tests/test_worldbuilding_handlers.py`

## Other Items

### `gemini-3.1-flash-lite-preview`

- Breakdown: `{'cleanup': 2, 'design_concern': 2, 'maintainability': 1, 'performance': 1, 'test_brittleness': 5, 'test_maintainability': 3}`
- `maintainability`: `Material dedup logic prevents material updates` in `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py`
- `performance`: `Inefficient height sampling in sample_world_height` in `Tools/mcp-toolkit/blender_addon/handlers/_terrain_world.py`
- `cleanup`: `Unused theoretical max amplitude helper` in `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py`
- `design_concern`: `NaÃ¯ve Seed Calculation in Tiled World Loop` in `Tools/mcp-toolkit/blender_addon/handlers/environment.py`
- `design_concern`: `Hard-coded Ray Height Limit in safe_place_object` in `Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py`
- `test_maintainability`: `Inconsistent validate_tile_seams API and Return Formats` in `Tools/mcp-toolkit/tests/test_terrain_chunking.py`
- `test_maintainability`: `Misleading Test Naming in Erosion Suite` in `Tools/mcp-toolkit/tests/test_terrain_erosion.py`
- `cleanup`: `Unused Import in Material Deduplication Test` in `Tools/mcp-toolkit/tests/test_terrain_materials.py`
- `test_maintainability`: `Redundant Category Existence Test` in `Tools/mcp-toolkit/tests/test_aaa_materials.py`
- `test_brittleness`: `Tautological assertions in visual verification tests` in `Tools/mcp-toolkit/tests/test_visual_verification_loop.py`
- `test_brittleness`: `Decoupled location handler validation via local reconstruction` in `Tools/mcp-toolkit/tests/test_city_generation_integration.py`
- `test_brittleness`: `Brittle source-code-based API parameter verification` in `Tools/mcp-toolkit/tests/test_worldbuilding_handlers.py`
- `test_brittleness`: `Hardcoded validation sets in integration tests` in `Tools/mcp-toolkit/tests/test_city_generation_integration.py`
- `test_brittleness`: `Weak validation logic in MST road network test` in `Tools/mcp-toolkit/tests/test_city_generation_integration.py`

### `qwen/qwen3.6-plus:free`

- Breakdown: `{'design_concern': 1, 'intentional_behavior': 1, 'test_brittleness': 4, 'test_gap': 1}`
- `design_concern`: `Silent fallback to default biome masks invalid configuration` in `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py`
- `intentional_behavior`: `Hard failure on unmapped prop types may break existing biome/location specs` in `Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py`
- `test_gap`: `Missing test coverage for new tiled terrain setup and neighbor wiring logic` in `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/scene.py`
- `test_brittleness`: `Ambiguous bounds tuple format assumption in chunk metadata test` in `Tools/mcp-toolkit/tests/test_terrain_chunking.py`
- `test_brittleness`: `Hardcoded routing dictionary bypasses actual source verification` in `Tools/mcp-toolkit/tests/test_city_generation_integration.py`
- `test_brittleness`: `Tautological assertions in visual verification threshold tests` in `Tools/mcp-toolkit/tests/test_visual_verification_loop.py`
- `test_brittleness`: `Brittle regex parsing for Python source code` in `Tools/mcp-toolkit/tests/test_worldbuilding_handlers.py`

### `nvidia/nemotron-3-super-120b-a12b:free`

- None
