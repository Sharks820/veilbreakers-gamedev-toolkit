---
phase: 35
plan: "01"
subsystem: tripo-pipeline
tags: [glb, texture-extraction, post-processing, pipeline-fix, blender-handlers]
dependency_graph:
  requires: [32-01, 33-01]
  provides: [tripo-texture-pipeline, glb-extractor, post-processor, texture-wiring-handlers]
  affects: [asset_pipeline, blender_texture, pipeline_runner]
tech_stack:
  added:
    - glb_texture_extractor.py (pygltflib primary + struct fallback)
    - tripo_post_processor.py (delight+validate+score pipeline)
  patterns:
    - dual-backend GLB parsing (pygltflib / struct+JSON fallback)
    - ORM channel split via Blender Separate RGB node (not on disk)
    - delit albedo preference over raw albedo throughout
    - idempotent weathering mix node insertion
key_files:
  created:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/glb_texture_extractor.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/tripo_post_processor.py
    - Tools/mcp-toolkit/tests/test_glb_texture_extractor.py
    - Tools/mcp-toolkit/tests/test_tripo_post_processor.py
    - Tools/mcp-toolkit/tests/test_texture_wiring.py
    - Tools/mcp-toolkit/tests/test_pipeline_integration.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/texture.py (appended handle_load_extracted_textures)
    - Tools/mcp-toolkit/blender_addon/handlers/weathering.py (appended handle_mix_weathering_over_texture)
    - Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py (new actions, generate_3d post-process, cleanup wiring)
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/pipeline_runner.py (has_extracted_textures param + conditional step 7)
decisions:
  - "ORM channels split in Blender shader (Separate RGB node) not pre-split to disk -- avoids creating 3 extra files per model"
  - "albedo_delit_path takes precedence over albedo_path everywhere -- ensures de-lighted version is always used when available"
  - "post_process_tripo_model runs inside generate_3d loop non-fatally -- failure logged but import continues"
  - "cleanup action falls back to texture_create_pbr when texture_channels=None -- preserves backward compatibility"
metrics:
  duration_minutes: ~95
  completed: "2026-04-01T01:43:00Z"
  tasks_completed: 5
  tasks_total: 5
  new_tests: 24
  files_created: 6
  files_modified: 4
---

# Phase 35 Plan 01: Tripo Texture Pipeline Summary

Closes the Tripo AI blank-texture gap by building a complete GLB texture extraction, de-lighting, validation, scoring, and Blender wiring pipeline.

## One-Liner

GLB texture extractor (pygltflib + struct fallback) + post-processor (delight/validate/score) + Blender wiring handlers (load extracted textures + weathering overlay) + pipeline_runner blank-texture bug fix.

## What Was Built

### Task 1 -- GLB Texture Extractor (`glb_texture_extractor.py`)

Dual-backend GLB parser that extracts PBR channel maps (albedo, orm, normal, ao, emissive) from a GLB binary blob to standalone PNG/JPG files on disk.

- Primary path: `pygltflib` library for clean API access
- Fallback path: raw `struct` + `json.loads` for environments without pygltflib
- Both paths use `bufferViews[i].byteOffset + byteLength` slicing -- handles non-zero offsets correctly (avoids research pitfall #1)
- `extract_glb_textures(glb_path, out_dir) -> dict[str, str]` -- main entry point
- `get_glb_texture_count(glb_path) -> int` -- lightweight count without extracting bytes
- 7 tests covering: albedo extract, ORM extract, missing normal graceful handling, non-zero byteOffset alignment, texture count, empty GLB, and fallback path via `_HAS_PYGLTFLIB = False` mock

### Task 2 -- Tripo Post-Processor (`tripo_post_processor.py`)

Orchestrates the complete post-download chain for a Tripo GLB:

1. Extract PBR channels via `extract_glb_textures`
2. De-light albedo via `delight_albedo` (skipped if no albedo)
3. Validate de-lit albedo against VeilBreakers palette rules via `validate_palette`
4. Validate ORM roughness variation via `validate_roughness_map`
5. Compute 0-100 channel completeness + quality score (25+25+25+15+10)

- `post_process_tripo_model(glb_path, out_dir, asset_type) -> dict` -- async, non-fatal per step
- `score_variants(post_results) -> list` -- sort by `channel_score` desc, ties broken by channel count
- Returns `{channels, albedo_delit, palette_validation, roughness_validation, channel_score, texture_dir}`
- 6 tests: all steps run, delight skipped without albedo, partial result on extraction error, score ordering, score=100 perfect model, palette deviation issues list format

### Task 3 -- Blender Texture Wiring Handlers

**`handle_load_extracted_textures` (texture.py):**
- Wires pre-extracted PNGs into a Principled BSDF node tree without creating blank placeholders
- Loads albedo as sRGB → Base Color socket
- Loads ORM as Non-Color → Separate RGB → G=Roughness, B=Metallic, R=AO multiply before Base Color
- Loads normal as Non-Color → Normal Map node → Normal socket
- Prefers `albedo_delit_path` over `albedo_path` when both provided
- Returns `{status, channels_loaded, warnings}`

**`handle_mix_weathering_over_texture` (weathering.py):**
- Inserts `MixRGB(MULTIPLY)` node labeled "WeatheringMix" between albedo tex and BSDF Base Color
- Sources weathering mask from `ShaderNodeVertexColor` reading "weathering" layer
- Idempotent: checks for existing "WeatheringMix" node, returns `already_wired` if found
- Configurable `weathering_strength` (0.0-1.0, default 0.4)
- Returns `{status, mix_node_created, warnings}`

**`blender_server.py` registration:**
- Added `load_extracted_textures` and `mix_weathering_over_texture` to `blender_texture` Literal
- Added params: `albedo_path`, `albedo_delit_path`, `normal_path`, `orm_path`, `weathering_strength`
- Dispatch blocks send to `texture_load_extracted_textures` and `texture_mix_weathering_over_texture` commands

6 tests using `mock.patch.object(module, "bpy", mock_bpy)` pattern -- no Blender required.

### Task 4 -- Pipeline Blank-Texture Bug Fix

**Root cause:** `pipeline_runner.cleanup_ai_model` step 7 unconditionally called `texture_create_pbr`, creating a blank Principled BSDF and discarding all Tripo-embedded textures.

**Fix in `pipeline_runner.py`:**
- Added `has_extracted_textures: bool = False` parameter
- Added `texture_channels: dict | None = None` parameter
- Step 7 now conditional:
  - `has_extracted_textures=True` AND `texture_channels` provided → `texture_load_extracted_textures`
  - Otherwise → `texture_create_pbr` (backward-compatible fallback)
- Prefers `albedo_delit` key over `albedo` key from channels dict

**`blender_server.py` wiring:**
- `generate_3d` now runs `post_process_tripo_model` on each verified variant GLB before Blender import
- Attaches `texture_channels` to each model in the result for downstream use
- `cleanup` action forwards `has_extracted_textures` + `texture_channels` to `cleanup_ai_model`
- `asset_pipeline` tool signature includes both new params

5 integration tests: create_pbr called without flag, load_extracted called with flag, delit preferred, fallback when channels=None, all standard steps still run.

### Task 5 -- Quality Gate

- 24 new tests: all pass
- 18,576 pre-existing tests: all still pass
- 57 pre-existing failures (test_lighting_placement, test_mesh_bridge): unchanged, out of scope

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None. All implemented functionality is fully wired:
- `post_process_tripo_model` calls real `delight_albedo`, `validate_palette`, `validate_roughness_map`
- `handle_load_extracted_textures` calls real `bpy.data.images.load` and wires real node links
- `cleanup_ai_model` routes to real Blender commands

## Self-Check: PASSED

### Files Verified

| File | Status |
| ---- | ------ |
| Tools/mcp-toolkit/src/veilbreakers_mcp/shared/glb_texture_extractor.py | FOUND |
| Tools/mcp-toolkit/src/veilbreakers_mcp/shared/tripo_post_processor.py | FOUND |
| Tools/mcp-toolkit/tests/test_glb_texture_extractor.py | FOUND |
| Tools/mcp-toolkit/tests/test_tripo_post_processor.py | FOUND |
| Tools/mcp-toolkit/tests/test_texture_wiring.py | FOUND |
| Tools/mcp-toolkit/tests/test_pipeline_integration.py | FOUND |
| Tools/mcp-toolkit/blender_addon/handlers/texture.py | FOUND |
| Tools/mcp-toolkit/blender_addon/handlers/weathering.py | FOUND |
| Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py | FOUND |
| Tools/mcp-toolkit/src/veilbreakers_mcp/shared/pipeline_runner.py | FOUND |

### Commits Verified

| Commit | Description |
| ------ | ----------- |
| b306d20 | feat(35-01): add GLB texture extractor module |
| 060eb8b | feat(35-01): add Tripo post-processor |
| 861cd21 | feat(35-01): add blender texture wiring + weathering overlay handlers |
| 7b8743f | fix(35-01): fix blank-texture bug -- wire extracted textures through cleanup pipeline |
