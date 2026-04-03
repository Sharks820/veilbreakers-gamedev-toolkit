# VeilBreakers Master Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform VeilBreakers MCP toolkit from prototype to AAA-quality game development studio through systematic bug fixes, terrain overhaul, modular architecture system, performance optimization, and cross-system integration.

**Architecture:** Phased approach: (1) Critical bug fixes, (2) Terrain overhaul, (3) Modular building system with CGA grammar, (4) Interior system upgrade with CSP solver, (5) Performance architecture, (6) Shader & VFX completion, (7) Cross-system integration, (8) Game systems wiring, (9) Polish & validation.

**Tech Stack:** Python 3.11+, numpy, Blender 4.x bpy API, Unity 6 URP 17, C# 12, Shader Graph, Forward+ rendering

**Research Base:** 61 agent missions, 26 bug scans, 75+ research documents (~3.5MB), 330+ bugs identified, 138+ gaps mapped

---

## Phase 1: Critical Bug Fixes (CRASH and HIGH Severity)

**Dependencies:** None (this is first)
**Estimated Tasks:** 72
**Bugs Fixed:** BUG-001 through BUG-052, BUG-175 through BUG-181, TQ-001 through TQ-004
**Gaps Closed:** None directly (enables all subsequent phases)

**Testing Strategy:**
- Run full test suite (`pytest`) after each sub-batch
- Verify CRASH fixes with targeted unit tests
- Verify HIGH fixes with assertions in existing tests
- Add regression tests for each CRASH bug

### 1.1 CRASH Bugs -- Blender Server (BUG-001 through BUG-003)

> **Status note:** BUG-001 and BUG-002 appear to have been partially fixed in recent commits (session_token parameter is correct, TripoStudioClient is imported in generate_prop). BUG-003 `pipeline_state` import of `bpy` is now inside `emit_scene_hierarchy()` only. Verify these are truly resolved before moving on.

- [ ] **1.1.1** Verify BUG-001 fix: `blender_server.py:2590` -- confirm `session_token=` is used (not `jwt_token=`) in all 3 TripoStudioClient instantiation sites (lines ~2233, ~2473, ~2590)
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py`
  - Test: `pytest tests/ -k tripo`

- [ ] **1.1.2** Verify BUG-002 fix: confirm `from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient` exists before each use in `generate_prop` action (~line 2589)
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py`

- [ ] **1.1.3** Verify BUG-003 fix: `pipeline_state.py` no longer has module-level `import bpy`. Confirm `import bpy` only exists inside `emit_scene_hierarchy()` function (line 269)
  - File: `Tools/mcp-toolkit/blender_addon/handlers/pipeline_state.py`
  - Validate: `from blender_addon.handlers.pipeline_state import load_pipeline_checkpoint` must work without bpy

### 1.2 CRASH Bugs -- Terrain Reshape (BUG-004 through BUG-007)

All four bugs share the same root cause: heightmap reshape assumes square grid (`side = int(len(verts)**0.5)`).

- [ ] **1.2.1** Fix BUG-004: `terrain_advanced.py` `flatten_layers` -- use mesh dimensions instead of sqrt
  - File: `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py`
  - Fix: Replace `side = int(math.sqrt(len(verts)))` with proper grid dimension detection from mesh x/y vertex ranges or `mesh.loops` dimensions. Add validation: `if side * side != len(verts): raise ValueError("non-grid mesh")`
  - Test: Add test with 65x129 (non-square) heightmap

- [ ] **1.2.2** Fix BUG-005: `environment.py` `handle_carve_river` -- same reshape fix
  - File: `Tools/mcp-toolkit/blender_addon/handlers/environment.py`

- [ ] **1.2.3** Fix BUG-006: `environment.py` `handle_generate_road` -- same reshape fix
  - File: `Tools/mcp-toolkit/blender_addon/handlers/environment.py`

- [ ] **1.2.4** Fix BUG-007: `terrain_advanced.py` `handle_erosion_paint` -- same reshape fix
  - File: `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py`

- [ ] **1.2.5** Create helper function `_get_grid_dimensions(vertices) -> tuple[int,int]` to share across all 4 sites
  - File: New helper in `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` or a shared util

### 1.3 CRASH Bugs -- Material/LOD/Vegetation (BUG-008 through BUG-011)

- [ ] **1.3.1** Fix BUG-008: `terrain_materials.py` -- `ruined_fortress` biome `slopes` referencing `"moss"` key. Verify MATERIAL_LIBRARY fallback resolves to semantically correct terrain material. If not, add explicit `"terrain_moss"` entry.
  - File: `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py`

- [ ] **1.3.2** Fix BUG-009: `lod_pipeline.py` `_generate_billboard_quad` -- billboard faces +Z (horizontal). Must face camera (-Y or +Y depending on convention). 
  - File: `Tools/mcp-toolkit/blender_addon/handlers/lod_pipeline.py` (~line 588)
  - Fix: Rotate billboard vertices so quad normal faces +Y (vertical) instead of +Z. The quad should stand upright. Change vertex generation from XY-plane to XZ-plane:
    ```python
    # BEFORE (broken): vertices in XY plane, normal +Z (flat on ground)
    # AFTER (fixed): vertices in XZ plane, normal +Y (upright billboard)
    verts = [
        (cx - hw, cy, cz - hh),  # bottom-left
        (cx + hw, cy, cz - hh),  # bottom-right
        (cx + hw, cy, cz + hh),  # top-right
        (cx - hw, cy, cz + hh),  # top-left
    ]
    ```
  - Test: Fix TQ-004 test that asserts coplanar-Z (which was asserting the WRONG orientation)

- [ ] **1.3.3** Fix BUG-010: `vegetation_system.py` -- seasonal `color_tint` values can push RGB below 0. Add `max(0.0, ...)` clamping after tint application.
  - File: `Tools/mcp-toolkit/blender_addon/handlers/vegetation_system.py`

- [ ] **1.3.4** Fix BUG-011: depends on BUG-009 fix. Once billboard faces correctly, LOD ratio 0.0 billboard generation works.

### 1.4 CRASH Bugs -- Animation/Dungeon/Settlement (BUG-012 through BUG-015)

- [ ] **1.4.1** Fix BUG-012: `animation_monster.py` -- `DEF-jaw` bone name mismatch. Facial rig creates `jaw` without `DEF-` prefix. Either rename bone creation to `DEF-jaw` or update animation references.
  - File: `Tools/mcp-toolkit/blender_addon/handlers/animation_monster.py`
  - Related: Check `rigging.py` or facial rig setup for bone naming

- [ ] **1.4.2** Fix BUG-013: `settlement_generator.py` `_furnish_interior` -- `rng.uniform(a, b)` with swapped bounds in small rooms. Add `min/max` guard: `rng.uniform(min(a,b), max(a,b))`
  - File: `Tools/mcp-toolkit/blender_addon/handlers/settlement_generator.py`

- [ ] **1.4.3** Fix BUG-014: `gemini_client.py` -- REST fallback `data["candidates"][0]` without bounds check. Add `if not data.get("candidates"): return {"error": "empty response"}`
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/gemini_client.py`

- [ ] **1.4.4** Fix BUG-015: `_dungeon_gen.py` `_place_spawn_points` -- `rng.randint(room.x+1, room.x2-2)` ValueError on tiny rooms. Add guard: `if room.width < 4: skip or use center`
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_dungeon_gen.py`

### 1.5 CRASH Bugs -- Unity Templates (BUG-016, BUG-017)

- [ ] **1.5.1** Fix BUG-016: `gameplay_templates.py` -- Add `if (agent.isOnNavMesh)` guard before all 8 `NavMeshAgent.SetDestination()` call sites in generated C# code
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/gameplay_templates.py`

- [ ] **1.5.2** Fix BUG-017: `combat_vfx_templates.py` -- Add null check after `Shader.Find()` before `new Material()` in all 8+ generated sites. Pattern: `var shader = Shader.Find("..."); if (shader == null) { Debug.LogError(...); return; }`
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/combat_vfx_templates.py`

### 1.6 HIGH Bugs -- Terrain & Environment (BUG-018 through BUG-026)

- [ ] **1.6.1** Fix BUG-018: `environment.py` carve_river division by max height -- guard against zero/negative max: `max_h = max(heightmap.max(), 1e-6)`
- [ ] **1.6.2** Fix BUG-019: `terrain_features.py` -- replace global mutable `_features_gen`/`_features_seed` with function-local RNG instances
- [ ] **1.6.3** Fix BUG-020: `environment.py` road path grid index bounds check -- clamp `r0, c0` to `[0, side-1]`
- [ ] **1.6.4** Fix BUG-021: `environment.py` water mesh double-height -- remove `obj.location = (0, 0, water_level)` since vertices already include water_level Z offset (line ~1026)
- [ ] **1.6.5** Fix BUG-022: `terrain_advanced.py` erosion paint row-major assumption -- use mesh vertex indices directly instead of assuming order
- [ ] **1.6.6** Fix BUG-023: `vegetation_lsystem.py` leaf card tilt -- re-orthogonalize after tilt modification using Gram-Schmidt
- [ ] **1.6.7** Fix BUG-024: `texture_quality.py` -- set dielectric materials (chitin, obsidian, ice, crystal) metallic to 0.0
- [ ] **1.6.8** Fix BUG-025: `terrain_materials.py` -- set terrain dielectrics (crystal_surface, prismatic_rock, crystal_wall) metallic to 0.0
- [ ] **1.6.9** Fix BUG-026: `vegetation_system.py` `_sample_terrain` default return -- return `None` instead of `(0.5, 0.0)` and handle None in caller (skip placement)

### 1.7 HIGH Bugs -- Unity Code Generation Safety (BUG-027, BUG-028, BUG-044)

- [ ] **1.7.1** Fix BUG-027: `unity_tools/vfx.py` -- sanitize `name` parameter in file paths using `_safe_namespace()` or regex `[^a-zA-Z0-9_]`
- [ ] **1.7.2** Fix BUG-028: `camera.py`, `world.py` -- sanitize `name` across all 32 unsanitized call sites
- [ ] **1.7.3** Fix BUG-044: `scene_templates.py` `prefab_paths` -- escape backslashes and quotes in generated C# string arrays. Use `path.replace("\\", "/").replace("\"", "\\\"")`

### 1.8 HIGH Bugs -- Animation/Rigging (BUG-029, BUG-030)

- [ ] **1.8.1** Fix BUG-029: `animation_blob.py` -- either create `DEF-pseudopod_*` bones in blob rig template or update animation to use correct bone names
- [ ] **1.8.2** Fix BUG-030: `rigging_advanced.py` -- update ragdoll preset to use `DEF-spine.005` instead of `DEF-head` for head bone reference

### 1.9 HIGH Bugs -- Pipeline/Tripo (BUG-031 through BUG-034)

- [ ] **1.9.1** Fix BUG-031: `pipeline_runner.py` `full_asset_pipeline` -- add explicit `bpy.context.view_layer.objects.active = obj; obj.select_set(True)` before export
- [ ] **1.9.2** Fix BUG-032: `pipeline_runner.py` -- handle multi-material texture channels (`albedo_mat0`, `albedo_mat1`) in pipeline wiring
- [ ] **1.9.3** Fix BUG-033: `tripo_post_processor.py` -- iterate ALL materials in multi-material models, not just first
- [ ] **1.9.4** Fix BUG-034: `blender_server.py` `generate_building`/`generate_prop` -- apply same post-processing and Blender import that `generate_3d` performs

### 1.10 HIGH Bugs -- Settlement/Worldbuilding (BUG-035 through BUG-052)

- [ ] **1.10.1** Fix BUG-035: Foundation `side_heights` corner index correction
- [ ] **1.10.2** Fix BUG-036: `vegetation_system.py` -- convert between LOCAL mesh and WORLD space coordinates properly
- [ ] **1.10.3** Fix BUG-037: `performance_templates.py` -- Unity LOD expects children via `transform.Find()` but Blender creates siblings. Generate LOD meshes as children of a parent empty.
- [ ] **1.10.4** Fix BUG-038: Add material property transfer utility (Blender PBR values -> JSON -> Unity material setup)
- [ ] **1.10.5** Fix BUG-039: Wire `building_interior_binding.py` into production code or remove dead code
- [ ] **1.10.6** Fix BUG-040: `worldbuilding.py` BMesh `free()` leak -- wrap in try/finally blocks
- [ ] **1.10.7** Fix BUG-041: `blender_server.py` `mesh_name` injection -- sanitize names before f-string code injection
- [ ] **1.10.8** Fix BUG-042: `socket_server.py` frozen handler timeout -- add per-client timeout isolation
- [ ] **1.10.9** Fix BUG-043: `_dungeon_gen.py` multi-floor RNG desync -- use single RNG state for positions and transitions
- [ ] **1.10.10** Fix BUG-045: `settlement_generator.py` concentric_organic layout -- this appears to be handled now (grep shows `if config.get("layout_pattern") == "concentric_organic"` at line 2477). Verify the fallthrough is eliminated.
- [ ] **1.10.11** Fix BUG-046: Room type vocabulary mismatch between `building_interior_binding.py` and `settlement_generator.py` -- unify to single vocabulary
- [ ] **1.10.12** Fix BUG-047: Add missing `VB_BUILDING_PRESETS` for 8 building types (tavern, blacksmith, temple, general_store, house, guard_barracks, manor, guild_hall)
- [ ] **1.10.13** Fix BUG-048: Replace hardcoded 3.5m floor height with preset `wall_height` in `building_interior_binding.py`
- [ ] **1.10.14** Fix BUG-049: Unify `_DISTRICT_BUILDING_TYPES` and `SETTLEMENT_TYPES` vocabularies
- [ ] **1.10.15** Fix BUG-050: Hearthvale temple shrine detection -- check for both `"shrine"` and `"temple"` substrings
- [ ] **1.10.16** Fix BUG-051: Add `"market"` room type to `_ROOM_CONFIGS`
- [ ] **1.10.17** Fix BUG-052: Add `"prison"` room type to `_ROOM_CONFIGS`

### 1.11 HIGH Bugs -- Error Handling & Concurrency (BUG-175 through BUG-181)

- [ ] **1.11.1** Fix BUG-175: `fal_client.py`, `texture_ops.py` -- `os.environ["FAL_KEY"]` race. Use thread-local storage or pass key as parameter instead of mutating env.
- [ ] **1.11.2** Fix BUG-176: `prop_density.py` -- wall/floor/ceiling prop rotation output in degrees. Convert to radians before returning, or document the contract clearly and convert in consumer.
- [ ] **1.11.3** Fix BUG-177: `blender_server.py` compose_map `game_check` -- replace `except Exception: pass` with logging and failure counting
- [ ] **1.11.4** Fix BUG-178: `blender_server.py` compose_map FBX export -- replace `except Exception: pass` with logging
- [ ] **1.11.5** Fix BUG-179: `blender_server.py` `_collect_mesh_targets` -- return error indicator (not empty list) on connection failure so caller can distinguish from "nothing to validate"
- [ ] **1.11.6** Fix BUG-180: `fal_client.py` -- catch `httpx.HTTPStatusError` in addition to existing exceptions
- [ ] **1.11.7** Fix BUG-181: `gemini_client.py` -- catch `httpx.HTTPStatusError` in `_call_gemini`

### 1.12 Dependency & Config Fixes

- [ ] **1.12.1** Fix BUG-092: Add `httpx` to `pyproject.toml` dependencies (used directly in 4 files but undeclared)
  - File: `Tools/mcp-toolkit/pyproject.toml`

- [ ] **1.12.2** Verify Google AI SDK package name matches import (check `google-generativeai` vs `google-genai` in pyproject.toml vs import statements)

### 1.13 Test Quality Fixes (TQ-001 through TQ-004)

- [ ] **1.13.1** Fix TQ-002: `test_dungeon_gen.py` `test_loot_points_include_secret_rooms` -- add actual assertion on computed result
- [ ] **1.13.2** Fix TQ-003: `test_gameplay_templates.py` -- replace 18 `assert result is not None` with meaningful structure/content assertions
- [ ] **1.13.3** Fix TQ-004: `test_lod_pipeline.py` billboard test -- assert vertical orientation (XZ plane), not horizontal (XY plane)

---

## Phase 2: Terrain Overhaul

**Dependencies:** Phase 1 (CRASH bugs fixed, especially BUG-004 through BUG-007 terrain reshape)
**Estimated Tasks:** 38
**Bugs Fixed:** BUG-056, BUG-061, BUG-088, BUG-090, BUG-190, BUG-193, BUG-211
**Gaps Closed:** GAP-07, GAP-08, GAP-10, GAP-11, GAP-13, GAP-15, GAP-39
**Testing Strategy:** Unit tests for each algorithm, integration test for full terrain pipeline, visual verification in Blender

### 2.1 Replace scipy Dependency with Pure numpy (GAP-15)

- [ ] **2.1.1** Implement pure numpy Gaussian blur kernel
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py`
  - Implementation: `def gaussian_blur_numpy(heightmap, sigma, passes=3)` using separable 1D convolution with `np.convolve`
  - Kernel: `k = np.exp(-0.5 * (np.arange(-radius, radius+1) / sigma)**2); k /= k.sum()`
  - Apply X then Y (separable) for each pass

- [ ] **2.1.2** Implement bilateral filter in pure numpy
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py`
  - Smooths flats while preserving cliff edges
  - Spatial weight: Gaussian based on distance
  - Range weight: Gaussian based on height difference

### 2.2 Grid-Based Hydraulic Erosion (Mei et al. 2007)

- [ ] **2.2.1** Implement grid-based hydraulic erosion engine
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py`
  - Per-cell state arrays: terrain height (b), water height (d), sediment (s), outflow flux (fL,fR,fT,fB)
  - 7-step iteration loop fully vectorized with `np.roll` for neighbor access
  - Parameters: rain_rate, evaporation, capacity_coeff, dissolving_const, deposition_const

- [ ] **2.2.2** Multi-pass erosion pipeline (Gaea-style)
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py`
  - Pass 1: Thermal pre-pass (30 iterations) -- natural talus
  - Pass 2: Hydraulic macro (low detail, high water volume) -- drainage networks
  - Pass 3: Hydraulic detail (high downcutting, low volume) -- deep gullies
  - Pass 4: Homogenization pass (light erosion) -- blend everything
  - Fix BUG-061: Ensure wind erosion conserves mass (deposit amount = erode amount)

### 2.3 Noise Generation Improvements

- [ ] **2.3.1** Increase domain warp strength 0.4 -> 0.7 with 2-octave warp
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py`

- [ ] **2.3.2** Add per-octave random offset jittering

- [ ] **2.3.3** Replace single 3x3 box blur with multi-pass Gaussian (using 2.1.1)

- [ ] **2.3.4** Add coordinate jittering to break grid alignment

### 2.4 Data-Driven Terrain Texturing

- [ ] **2.4.1** Compute slope map with cell spacing (fixes BUG-056, BUG-190)
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py`
  - Fix: `np.gradient(heightmap, cell_size)` -- pass actual cell spacing, not default 1.0

- [ ] **2.4.2** Compute curvature map (Laplacian filter)
  - Concave = moss/dirt, convex = exposed rock/snow

- [ ] **2.4.3** Compute flow map from hydraulic erosion sediment transport paths

- [ ] **2.4.4** Compute wear map (erosion removal locations) and deposit map (sediment settling)

- [ ] **2.4.5** Replace hardcoded slope thresholds with smoothstep transitions (5-10 degree zones)

- [ ] **2.4.6** Add per-material angle-of-repose (sand 30-35deg, grass 40-50deg, mud 15-25deg, rock unlimited)
  - File: `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py`

### 2.5 Splatmap Export Pipeline (GAP-07)

- [ ] **2.5.1** Export vertex color splatmap as PNG image from Blender
  - File: New function in `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py`
  - Render vertex colors to texture image, export as PNG RGBA (4 channels = 4 terrain layers)

- [ ] **2.5.2** Add splatmap import path in Unity scene setup
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/scene_templates.py`
  - Read PNG, convert to float[,,] array, call `SetAlphamaps()`

### 2.6 Chunk Boundary Stitching (GAP-08)

- [ ] **2.6.1** Implement shared-edge constraint in terrain chunking
  - File: `Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py`
  - Neighboring chunks must share identical edge vertex heights
  - Add edge-matching validation after chunk generation

- [ ] **2.6.2** Add skirt mesh generation for LOD transitions between chunks

### 2.7 Heightmap Resolution Validation (GAP-39)

- [ ] **2.7.1** Add validation assertion that heightmap is (2^n+1) at export time
  - File: `Tools/mcp-toolkit/blender_addon/handlers/environment.py`
  - Fix BUG-088: Add NaN/Inf guard on heightmap data before export

### 2.8 Terrain Deformation Integration (GAP-10, GAP-11, GAP-13)

- [ ] **2.8.1** Road terrain deformation -- flatten terrain under road segments, taper at edges
  - File: `Tools/mcp-toolkit/blender_addon/handlers/road_network.py`
  - Run road deformation BEFORE final erosion pass

- [ ] **2.8.2** Building terrain terracing -- flatten terrain under building plots, create foundation geometry
  - File: `Tools/mcp-toolkit/blender_addon/handlers/settlement_generator.py`

- [ ] **2.8.3** Water body terrain integration -- carve river channels into heightmap, set water level planes
  - File: `Tools/mcp-toolkit/blender_addon/handlers/environment.py`

### 2.9 Additional Terrain Systems

- [ ] **2.9.1** River meander simulation (~20 lines addition to erosion loop, momentum-based)
- [ ] **2.9.2** Flood-fill lake generation from terrain depressions
- [ ] **2.9.3** Smooth biome boundary blending (interpolate between adjacent biome palettes)
- [ ] **2.9.4** Fix BUG-090: `_terrain_depth.py` -- cache `np.gradient` result outside per-cluster loop
- [ ] **2.9.5** Fix BUG-193: `_terrain_depth.py` -- cliff meshes rotated perpendicular to slope (off by 90 deg)
- [ ] **2.9.6** Fix BUG-211: `environment_scatter.py` -- use central differences instead of forward differences for terrain slope

---

## Phase 3: Modular Building System with CGA Grammar

**Dependencies:** Phase 1 (settlement bugs fixed), Phase 2 (terrain deformation for building plots)
**Estimated Tasks:** 28
**Bugs Fixed:** BUG-130, BUG-192, BUG-157, BUG-158, BUG-159, BUG-160, BUG-161
**Gaps Closed:** GAP-20, toolkit gaps #1 (collision mesh), #39 (offline prop fallback)
**Testing Strategy:** Grammar derivation unit tests, assembly validation tests (loopback, stack, gap), visual verification

### 3.1 CGA Split Grammar Engine

- [ ] **3.1.1** Implement Shape class with scope (position, rotation, size) and geometry reference
  - File: New `Tools/mcp-toolkit/blender_addon/handlers/_cga_grammar.py`
  - ~260-400 lines core engine

- [ ] **3.1.2** Implement `split(axis, segments)` operation -- divide shape along axis into sub-shapes
  - Support absolute, relative (`'0.5`), and floating (`~3.0`) size types
  - Support repeat operator (`*`) for filling remaining space

- [ ] **3.1.3** Implement `comp(faces)` operation -- extract faces from 3D shape as 2D shapes
  - Face selectors: front, back, left, right, top, bottom, side, all

- [ ] **3.1.4** Implement scope manipulation operations: translate, rotate, scale

- [ ] **3.1.5** Implement stochastic rule selection (`30% : A | 70% : B`) using seeded RNG

- [ ] **3.1.6** Implement conditional rule selection (`case cond : A else : B`)

### 3.2 Gothic Building Type Rulesets

- [ ] **3.2.1** Tavern ruleset -- ground floor bar area + upper floor rooms, timber-framed facade
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_cga_grammar.py` (rulesets dict)

- [ ] **3.2.2** Castle tower ruleset -- cylindrical base, crenellated top, arrow slits, machicolations

- [ ] **3.2.3** Cathedral/chapel ruleset -- nave, aisles, rose window, flying buttresses (using Gothic proportions from `gothic_architecture_rules_research.md`)
  - Ad quadratum: height = width * 1.0-1.414
  - Pointed arch: offset = 0.3 * half_span

- [ ] **3.2.4** House ruleset -- 2-story stone-timber, steep roof, dormer windows

- [ ] **3.2.5** Gatehouse ruleset -- portcullis, drawbridge pivot, flanking towers

### 3.3 Snap Connector System

- [ ] **3.3.1** Define SnapPoint dataclass: `{anchor_position, anchor_normal, compatible_tags, size_class}`
  - File: New addition to `Tools/mcp-toolkit/blender_addon/handlers/modular_building_kit.py`

- [ ] **3.3.2** Implement alignment algorithm: find compatible snap points, transform piece to align

- [ ] **3.3.3** Apply Bethesda naming convention to all kit pieces:
  - Format: `[Tileset][Type][Size][PieceKind][ExitType][Variant]`
  - Example: `VBRmSmWallSideExSm01`
  - File: `Tools/mcp-toolkit/blender_addon/handlers/modular_building_kit.py`

### 3.4 Missing Gothic Kit Pieces

- [ ] **3.4.1** Add flying buttress piece generator (using research proportions: angle 35-60deg, every bay)
- [ ] **3.4.2** Add portcullis mechanism piece
- [ ] **3.4.3** Add gargoyle piece (waterspout + ornamental)
- [ ] **3.4.4** Add rose window piece (8/12/16 radiating spokes, 0.5-0.7x facade width)
- [ ] **3.4.5** Add pointed arch doorway piece (equilateral: H:W = 1.73:1)
- [ ] **3.4.6** Add crenellation piece (merlon:crenel ratio 2:1 to 3:2, merlon height 1.5-2.0m)

### 3.5 Assembly & Validation

- [ ] **3.5.1** Trim sheet material system -- 1-2 materials per kit using shared trim sheet texture atlas
  - File: `Tools/mcp-toolkit/blender_addon/handlers/modular_building_kit.py`

- [ ] **3.5.2** Assembly validation tests: loopback (pieces connect back to start), stack (multi-floor), gap detection

- [ ] **3.5.3** Add connection metadata to all 175 existing kit piece variants

- [ ] **3.5.4** Corruption grammar modifications -- rules that distort geometry at Veil-affected buildings

- [ ] **3.5.5** Define assembly recipe schema: `{piece_id, position, rotation, snap_point, material_override}` (closes GAP-20)

- [ ] **3.5.6** Fix BUG-130: `_building_grammar.py` duplicate dict keys in `_DETAIL_TYPE_MATERIAL_CATEGORY`
- [ ] **3.5.7** Fix BUG-192: `_building_grammar.py` mixed rotation formats (scalar vs 3-tuple)
- [ ] **3.5.8** Fix BUG-157 through BUG-161: settlement prop generators missing -- add offline fallback geometry for `portcullis_gate`, `planter`, `brazier`, `torch_post`, `milestone`, `rock_small`, `debris_pile`, `bone_scatter`

---

## Phase 4: Interior System Upgrade

**Dependencies:** Phase 3 (building system provides room shells)
**Estimated Tasks:** 22
**Bugs Fixed:** BUG-048, BUG-169, BUG-170, BUG-194, BUG-108
**Gaps Closed:** GAP-14, GAP-17, toolkit gap #5 (furniture), #37 (cave decoration)
**Testing Strategy:** CSP solver unit tests with known-solvable room configurations, integration tests for multi-floor buildings

### 4.1 CSP Furniture Placement Solver

- [ ] **4.1.1** Implement CSP solver core (~300 lines)
  - File: New `Tools/mcp-toolkit/blender_addon/handlers/_csp_solver.py`
  - Grid discretization at 0.1m resolution
  - Backtracking search with constraint propagation (AC-3/MAC)
  - MRV (Most Constrained First) variable ordering
  - Rotation discretized to 4 values (0, pi/2, pi, 3*pi/2)

- [ ] **4.1.2** Define hard constraints: no overlap (AABB), in bounds, door clearance (1.2m), window clearance (0.8m)

- [ ] **4.1.3** Define soft constraints (scoring): wall adjacency preference, facing direction, activity zone matching, functional grouping

- [ ] **4.1.4** Wire CSP solver as drop-in replacement for `generate_interior_layout()` using same input/output format
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py`

### 4.2 Room Types & Floor Plans

- [ ] **4.2.1** Add spatial graphs for remaining 13 room types (closes BUG-170)
  - File: `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py`
  - Room types: armory, workshop, library, bedroom, kitchen, pantry, cellar, treasury, chapel, throne, barracks, stable, dungeon_cell

- [ ] **4.2.2** BSP/treemap floor plan generator for building subdivision
  - File: New addition to `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py`

- [ ] **4.2.3** Add `"generic"` room type to `_ROOM_CONFIGS` (closes BUG-169)

### 4.3 Multi-Floor & Staircase

- [ ] **4.3.1** Multi-floor staircase generation with correct rotation per floor
  - Fix BUG-194: `worldbuilding.py` stairs `rotation_euler` -- compute from actual connection direction instead of hardcoded `(pi/2, 0, 0)`

- [ ] **4.3.2** Exterior-interior door alignment for all cardinal directions
  - Fix BUG-108: `worldbuilding_layout.py` -- handle east/west facing doors, not just south

### 4.4 Interior Mapping Shader (for non-walkable buildings)

- [ ] **4.4.1** Interior mapping shader for Unity URP -- parallax cubemap technique
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py`
  - Renders fake interior through windows using raycasting against cubemap
  - SRP Batcher compatible

### 4.5 Storytelling & Integration

- [ ] **4.5.1** Storytelling vignette system -- post-CSP placement of narrative environmental props
  - Readable notes, corpse poses, item arrangements that imply events
  - File: New integration in compose_map after interior generation

- [ ] **4.5.2** Fix BUG-048: Replace hardcoded 3.5m floor height with per-building preset `wall_height`

- [ ] **4.5.3** Interior streaming connection points (GAP-14) -- define door anchor points in building recipe, auto-generate DoorTrigger components linked to interior scene names
  - File: `Tools/mcp-toolkit/blender_addon/handlers/building_interior_binding.py`

---

## Phase 5: Performance Architecture

**Dependencies:** Phase 2 (terrain system), Phase 3 (building system for LOD/collision)
**Estimated Tasks:** 30
**Bugs Fixed:** BUG-037, BUG-095, BUG-096, BUG-104, BUG-109, BUG-117, BUG-186
**Gaps Closed:** GAP-02, GAP-04, GAP-09, GAP-21, GAP-22, GAP-24, GAP-25, GAP-26, GAP-28, GAP-37, toolkit gaps #7, #42, #45, #47
**Testing Strategy:** Performance profiling before/after, memory budget validation, LOD visual regression tests

### 5.1 4-Tier Quality System

- [ ] **5.1.1** Implement `ASSET_BUDGETS` config dict as single source of truth for all triangle/texture/LOD budgets
  - File: New `Tools/mcp-toolkit/blender_addon/handlers/_asset_budgets.py`
  - Per-asset triangle limits from `model_size_budgets_research.md`
  - 4 tiers: Low (2GB VRAM), Medium (4GB), High (8GB), Ultra (16GB)

- [ ] **5.1.2** Wire `game_check` validation to read from `ASSET_BUDGETS` config
  - File: `Tools/mcp-toolkit/blender_addon/handlers/mesh.py`

- [ ] **5.1.3** Create Unity quality settings template for all 4 tiers
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/quality_templates.py`
  - Render scale, shadow distance/cascades, LOD bias, vegetation density, terrain pixel error, MSAA/TAA, SSAO, volumetric fog, mipmap streaming budget

### 5.2 LOD Chain Export to Unity (GAP-09)

- [ ] **5.2.1** Export LOD levels as child objects under parent empty (named `LOD0`, `LOD1`, etc.)
  - File: `Tools/mcp-toolkit/blender_addon/handlers/lod_pipeline.py`
  - Fix BUG-037: Create LOD meshes as children, not siblings
  - Fix BUG-095: Transfer screen percentage values from Blender presets
  - Fix BUG-096: Actually use `export_dir` parameter
  - Fix BUG-104: Billboard quad returns full bounding box extent (including Z height)

- [ ] **5.2.2** Generate Unity LODGroup setup script
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/performance_templates.py`
  - Fix BUG-109: Apply LODGroup only to objects with actual LOD children, not indiscriminately

- [ ] **5.2.3** Define crossfade settings per asset type (band 10-15%, duration 0.5s, hysteresis 5%)
  - Closes GAP-28: LOD pop-in on vegetation solved with dithered crossfade

### 5.3 Collision Mesh Strategy (GAP-02)

- [ ] **5.3.1** Implement compound primitive collider generation for buildings (6-12 BoxColliders each)
  - File: New utility in `Tools/mcp-toolkit/blender_addon/handlers/mesh.py`
  - Analyze building geometry, fit oriented bounding boxes to wall/floor/roof segments

- [ ] **5.3.2** Implement convex decomposition fallback for complex shapes (V-HACD algorithm)

### 5.4 Rendering Setup (GAP-21, GAP-22)

- [ ] **5.4.1** Forward+ rendering configuration template
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/performance_templates.py`
  - Required for GPU Resident Drawer; include fallback to SRP Batcher + GPU Instancing

- [ ] **5.4.2** GPU Resident Drawer setup (optional enhancement, not requirement)

- [ ] **5.4.3** HLOD generation for distant objects (83% draw call reduction)

- [ ] **5.4.4** Adaptive Probe Volumes configuration template
  - 1m min brick size for settlements, 27m max for open terrain
  - Replace legacy LightProbeGroup grid generation in `world_templates.py`

### 5.5 Terrain Streaming (GAP-37)

- [ ] **5.5.1** `TerrainStreamingManager` Unity script generation
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/scene_templates.py`
  - Reads chunk metadata JSON from terrain_chunking.py output
  - Manages 3x3 active window of additive scenes
  - Async load/unload based on player position
  - Each tile = one additive scene (terrain + vegetation + buildings + props + triggers)

- [ ] **5.5.2** `NavMeshSurface` per terrain tile with auto-stitching between adjacent tiles

### 5.6 GPU Instancing & Vegetation Performance (GAP-26)

- [ ] **5.6.1** GPU instancing shader setup for vegetation and rocks
  - Intentionally SRP-incompatible (GPU instancing path)

- [ ] **5.6.2** `DrawMeshInstancedIndirect` compute shader template for grass (10M+ instances)

- [ ] **5.6.3** Distance-based density falloff: full within 100m, 50% at 200m, billboard at 400m, cull beyond 600m

- [ ] **5.6.4** Mipmap streaming budget configuration per quality tier

### 5.7 Additional Performance Fixes

- [ ] **5.7.1** Fix BUG-117: `combat_vfx_templates.py` -- use `renderer.sharedMaterial` instead of `renderer.material` to prevent GPU memory leak per combo hit
- [ ] **5.7.2** Fix BUG-186: `asset_catalog.py` -- use connection pool with thread safety for SQLite
- [ ] **5.7.3** Occlusion culling data generation (GAP-04) -- mark large opaque meshes as Static Occluders, smaller props as Occludees

---

## Phase 6: Shader & VFX Completion

**Dependencies:** Phase 5 (rendering setup, Forward+ configuration)
**Estimated Tasks:** 22
**Bugs Fixed:** BUG-062, BUG-093, BUG-172
**Gaps Closed:** GAP-18, toolkit gaps #7, #9, #14
**Testing Strategy:** SRP Batcher compatibility validation for every shader, visual regression tests

### 6.1 Fix Existing Shader Bugs

- [ ] **6.1.1** Validate all custom shaders for SRP Batcher compatibility (all properties in single `CBUFFER_START(UnityPerMaterial)`)
- [ ] **6.1.2** Fix duplicate ShadowCaster passes in generated shaders
- [ ] **6.1.3** Add missing DepthNormals pass to all lit shaders
- [ ] **6.1.4** Fix BUG-062: Unify wind vertex color functions -- single consistent channel semantic (R=radial, G=height, B=branch)
- [ ] **6.1.5** Fix BUG-093: Add linear-to-sRGB color conversion utility for Blender->Unity material transfer

### 6.2 Missing Shaders (6)

- [ ] **6.2.1** Building weathering shader (moss growth, moisture darkening, patina)
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py`
  - World-space noise-driven moss on north-facing surfaces
  - Height-based moisture darkening at base
  - SRP Batcher compatible

- [ ] **6.2.2** Weapon/armor rune emission shader (emissive patterns, damage states)

- [ ] **6.2.3** Cloth/fabric shader (wind animation, subsurface scattering)

- [ ] **6.2.4** VFX fire/smoke shader (proper flame particles + heat distortion)

- [ ] **6.2.5** Height fog renderer feature (exponential height fog per biome)
  - URP ScriptableRendererFeature

- [ ] **6.2.6** Decal system shader with pool management

### 6.3 Shader Upgrades

- [ ] **6.3.1** Corruption/Veil world-space dissolve shader
  - Global `_CorruptionRadius` and `_CorruptionOrigin` parameters
  - Spreads across ANY surface organically
  - 4-stage visual: Taint -> Spread -> Transformation -> Consumed

- [ ] **6.3.2** Vegetation wind shader (GPU instancing compatible)
  - Vertex color channels: R=radial distance, G=height, B=branch level

- [ ] **6.3.3** Water shader upgrade: Gerstner waves (4 at ~0.2ms), depth coloring, foam, caustics, flow maps, refraction
  - Requires Depth Texture + Opaque Texture enabled in URP

- [ ] **6.3.4** Triplanar mapping shader for cliff faces (eliminates UV stretching) -- closes GAP-18

- [ ] **6.3.5** PSO Tracing shader warmup configuration for Unity 6 (legacy WarmUp broken on DX12/Vulkan)

### 6.4 Post-Processing

- [ ] **6.4.1** Dark fantasy post-processing preset
  - ACES tonemapping, post exposure -0.3 to -0.5
  - Saturation -15 to -25, blue-shifted shadows (hue 220), amber highlights (hue 35)
  - SSAO 1.5-2.5 intensity, bloom threshold 0.9

- [ ] **6.4.2** Fix BUG-172: `veil_crack_zone` terrain metallic 0.50 -> 0.15 (more realistic)

---

## Phase 7: Cross-System Integration

**Dependencies:** Phase 2 (splatmap export), Phase 5 (LOD/streaming), Phase 6 (shaders)
**Estimated Tasks:** 25
**Bugs Fixed:** BUG-094, BUG-098
**Gaps Closed:** GAP-03, GAP-05, GAP-12, GAP-16, GAP-19, GAP-27, GAP-38, toolkit gaps #10, #40, #41, #54, #55, #56, #61, #62, #63, #64
**Testing Strategy:** End-to-end pipeline integration tests, cross-system smoke tests

### 7.1 Blender-to-Unity Transfer Pipeline

- [ ] **7.1.1** Splatmap PNG transfer: Blender export -> Unity `SetAlphamaps()` consumer
  - Wires GAP-07 export (Phase 2) to Unity import

- [ ] **7.1.2** LOD meshes -> Unity LODGroup pipeline
  - Wires Phase 5 LOD export to Unity LODGroup setup

- [ ] **7.1.3** Material property transfer: Blender PBR values -> JSON metadata -> Unity material setup
  - Fix BUG-094: Map biome palette names to Unity terrain layer system
  - Fix BUG-093: Apply linear->sRGB conversion

- [ ] **7.1.4** Terrain heightmap transfer: Blender `export_heightmap` -> Unity `setup_terrain` consumer (toolkit gap #64)

- [ ] **7.1.5** Texture export alongside FBX (toolkit gap #41) -- copy/embed textures with export

### 7.2 Scene Composition Tool (toolkit gap #56)

- [ ] **7.2.1** Build world->scene bridge: take Blender worldbuilding output and auto-setup Unity scene
  - Imported meshes + lighting + navigation + spawn points + audio zones + VFX volumes + trigger zones
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/world.py` (new action)

- [ ] **7.2.2** Cross-tool state persistence (toolkit gap #63) -- shared project database tracking assets, status, relationships

### 7.3 Audio & Spatial Integration

- [ ] **7.3.1** Audio zone generation from building/cave enclosures (GAP-03)
  - Generate `AudioReverbZone` components from enclosed spaces
  - Define ambient audio profiles per biome

- [ ] **7.3.2** Water proximity audio triggers

### 7.4 Vegetation & Environment Integration

- [ ] **7.4.1** Vegetation exclusion zones from buildings/roads (GAP-12, BUG-098)
  - Generate exclusion masks from building footprints, road segments, water bodies
  - Pass to vegetation scatter

- [ ] **7.4.2** Terrain-to-building ground seam fix (GAP-27)
  - Ground decal rings around building footprints
  - Dirt/debris mesh at building perimeter

- [ ] **7.4.3** Cross-chunk entity awareness (GAP-38)
  - 50-100m buffer zone where chunks share entity awareness
  - NavMesh baked across chunk boundaries

### 7.5 Bridge Auto-Install (toolkit gaps #61, #62)

- [ ] **7.5.1** Blender addon auto-install from MCP toolkit + version checking + auto-reconnection

- [ ] **7.5.2** Unity bridge bootstrap command for fresh project setup

### 7.6 End-to-End Pipeline Test (GAP-16)

- [ ] **7.6.1** Create integration test: generate 257x257 terrain -> erode -> compute splatmap -> chunk -> export RAW -> validate dimensions
  - File: `Tools/mcp-toolkit/tests/test_full_pipeline.py`
  - Pure-logic functions, no Blender or Unity required

- [ ] **7.6.2** Minimap/world map data export (GAP-05) -- generate simplified 2D map from terrain + road + building data

- [ ] **7.6.3** Texture compression format strategy (GAP-19) -- BC7 albedo, BC5 normal, ASTC mobile fallback per platform

---

## Phase 8: Game Systems Wiring

**Dependencies:** Phase 6 (Veil shader), Phase 7 (scene composition)
**Estimated Tasks:** 32
**Bugs Fixed:** BUG-016 (extended), BUG-107
**Gaps Closed:** GAP-01, GAP-32, GAP-33, GAP-34, GAP-35, NEW-03, NEW-07, NEW-10, NEW-14, NEW-17, NEW-18, NEW-19, toolkit gaps #27, #31, #32, #33, #35
**Testing Strategy:** Gameplay integration tests in Unity, AI behavior validation, combat system tests

### 8.1 NavMesh Generation Pipeline (GAP-01)

- [ ] **8.1.1** NavMeshSurface bake step per terrain tile
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/prefab_templates.py`
  - Walkable slope 45deg default, adjust per biome
  - Mark water/cliff/void as non-walkable
  - NavMeshLink for gaps/jumps/ladders

- [ ] **8.1.2** Interior NavMesh surfaces separate from exterior

- [ ] **8.1.3** Patrol path auto-generation from NavMesh topology (NEW-11)

### 8.2 Veil Corruption Integration (GAP-32, NEW-17)

- [ ] **8.2.1** Corruption intensity map (0-1) per terrain vertex
  - Additional splatmap channel for corruption material
  - Vertex displacement in corruption zones

- [ ] **8.2.2** Veil boundary VFX trigger volume generation

- [ ] **8.2.3** Dynamic corruption expansion at runtime

- [ ] **8.2.4** Corruption AI behavior modification (NEW-17) -- enemies in corrupted zones are more aggressive, mutated abilities

- [ ] **8.2.5** Negative light sources in corrupted areas (Diablo IV technique)

### 8.3 Boss Arena Terrain Sculpting (GAP-33)

- [ ] **8.3.1** Boss arena terrain stamps -- pre-sculpted heightmap patches that blend into surrounding terrain
- [ ] **8.3.2** Arena material overlays (bloodstained stone, ritual circles)
- [ ] **8.3.3** Phase-specific terrain changes (floor breaking, arena expanding) -- NEW-13

### 8.4 Gameplay Effects Integration (NEW-18, NEW-19)

- [ ] **8.4.1** Weather gameplay effects -- rain slows movement, fog reduces detection range, fire damage reduced in rain
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/gameplay_templates.py`

- [ ] **8.4.2** Day/night gameplay effects -- night spawns stronger enemies, undead rising, increased Veil influence

- [ ] **8.4.3** Terrain slope movement speed modifier (NEW-20)

### 8.5 Enemy AI Archetype Library (NEW-10)

- [ ] **8.5.1** Define enemy archetypes: ranged, shield bearer, suicide rusher, summoner, sniper, ambush predator
  - File: `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/gameplay_templates.py`
  - Each archetype = distinct FSM with unique behavior patterns

- [ ] **8.5.2** Behavior tree node implementations (toolkit gap #31) -- selector, sequence, decorator, action nodes

- [ ] **8.5.3** Group/squad AI behavior (NEW-12) -- pack surround, formation advance, coordinated attacks

### 8.6 Interaction & Loot Systems (GAP-35)

- [ ] **8.6.1** Interaction point placement system -- loot, door, lever, NPC, crafting station
  - Placement rules per building type and biome
  - Export as tagged GameObjects with collider triggers

- [ ] **8.6.2** Destruction -> loot/resource drop wiring (NEW-21)

- [ ] **8.6.3** Quest objective tracking / waypoint integration (NEW-14)

### 8.7 Audio & Animation Wiring

- [ ] **8.7.1** Footstep system terrain splatmap reading (NEW-07)
  - Fix: Read `Terrain.activeTerrain.terrainData.GetAlphamaps()` at player position to determine dominant terrain layer

- [ ] **8.7.2** Animation retargeting with proportional adjustment (NEW-03)
  - Adjust bone translations proportionally for different limb lengths

- [ ] **8.7.3** Combat audio integration template (NEW-08) -- weapon swings, impacts, parry, shield block

- [ ] **8.7.4** Music-to-game-state integration (NEW-09) -- exploration -> combat -> boss -> victory triggers

- [ ] **8.7.5** Additive animation layering for locomotion + upper body (NEW-05) -- attack while moving

### 8.8 Destructible Environment (GAP-34)

- [ ] **8.8.1** Terrain modification events for destruction -- crater stamp, debris scatter, material overlay (scorched earth, rubble)

---

## Phase 9: Polish & Validation

**Dependencies:** All previous phases
**Estimated Tasks:** 45
**Bugs Fixed:** All remaining MEDIUM (BUG-053 through BUG-121, BUG-182 through BUG-205) and LOW (BUG-122 through BUG-174, BUG-206 through BUG-219), TQ-005 through TQ-016
**Gaps Closed:** GAP-06, GAP-23, GAP-29, GAP-30, GAP-31, GAP-36, GAP-40, NEW-04, NEW-06, NEW-15, NEW-16, NEW-22 through NEW-31
**Testing Strategy:** Full regression suite, visual regression testing, performance benchmarks, accessibility audit

### 9.1 MEDIUM Bug Fixes (93 bugs)

Organized by file for efficient batch processing:

- [ ] **9.1.1** `blender_server.py` batch (14 bugs): BUG-053, BUG-054, BUG-075, BUG-081, BUG-082, BUG-084, BUG-086, BUG-122 through BUG-125, BUG-137, BUG-138, BUG-177, BUG-178, BUG-179, BUG-195, BUG-203, BUG-204
  - Primary fixes: replace `except Exception: pass` with logging, add NaN guards, fix checkpoint resume

- [ ] **9.1.2** `environment.py` batch (5 bugs): BUG-055, BUG-058, BUG-088, BUG-214, BUG-215
  - Primary fixes: add NaN/Inf guard, fix silent defaults, log errors instead of swallowing

- [ ] **9.1.3** `settlement_generator.py` batch (6 bugs): BUG-057, BUG-097, BUG-099, BUG-101, BUG-102, BUG-121
  - Primary fixes: relative imports, heightmap type fix, guild_hall armory config, road position consistency

- [ ] **9.1.4** `terrain_materials.py` batch (4 bugs): BUG-060, BUG-064, BUG-093, BUG-094
  - Primary fixes: thornwood mud semantic, deduplicate sandstone, color space conversion

- [ ] **9.1.5** `lod_pipeline.py` batch (4 bugs): BUG-063, BUG-066, BUG-095, BUG-096
  - Primary fixes: Y->Z axis for height detection, degenerate face guard, export_dir implementation

- [ ] **9.1.6** `vegetation_system.py` batch (3 bugs): BUG-062, BUG-065, BUG-098
  - Primary fixes: unify wind vertex colors, explicit radian contract, exclusion zones

- [ ] **9.1.7** `animation_*.py` batch (6 bugs): BUG-069, BUG-070, BUG-071, BUG-072, BUG-105, BUG-149, BUG-150
  - Primary fixes: root motion space, quaternion W component, sway channel filter, phase_ranges recalculation

- [ ] **9.1.8** `unity_templates/*.py` batch (12 bugs): BUG-067, BUG-068, BUG-073, BUG-109, BUG-110, BUG-111, BUG-112, BUG-113, BUG-114, BUG-115, BUG-116, BUG-173
  - Primary fixes: dedup `_CS_RESERVED`, sanitize identifiers, fix heightmap endianness, add resolution validation

- [ ] **9.1.9** `tripo_*.py` batch (5 bugs): BUG-076, BUG-077, BUG-078, BUG-079, BUG-080, BUG-083, BUG-199
  - Primary fixes: log de-lighting errors, verify Content-Length, improve JWT extraction, typed error responses

- [ ] **9.1.10** `worldbuilding*.py` batch (6 bugs): BUG-059, BUG-100, BUG-108, BUG-196, BUG-197, BUG-198, BUG-205
  - Primary fixes: bmesh geom extraction, cache invalidation, directional door offsets, replace `except: pass` with logging

- [ ] **9.1.11** Concurrency/state batch (7 bugs): BUG-182, BUG-183, BUG-184, BUG-185, BUG-186, BUG-187, BUG-188
  - Primary fixes: deduplicate retry commands, async sleep instead of blocking, atomic file writes, BMesh try/finally

- [ ] **9.1.12** Remaining MEDIUM bugs: BUG-089, BUG-091, BUG-103, BUG-106, BUG-107, BUG-118, BUG-119, BUG-120, BUG-189, BUG-191, BUG-200, BUG-201, BUG-202
  - Primary fixes: tempfile race, env var leak, metallic values (rusted metals -> 1.0), rubble Y->Z axis, dungeon brute-force optimization, timeout alignment

### 9.2 LOW Bug Fixes (61 bugs)

- [ ] **9.2.1** Code quality batch (20 bugs): BUG-126 through BUG-135, BUG-142 through BUG-145, BUG-162 through BUG-168
  - Primarily code cleanliness, bias fixes, documentation accuracy, resource leaks

- [ ] **9.2.2** Material/visual batch (5 bugs): BUG-134, BUG-136, BUG-172 through BUG-174
  - Billboard UV coordinates, normal strength clamp, brand color optimization

- [ ] **9.2.3** Settlement/building batch (8 bugs): BUG-157 through BUG-161, BUG-169, BUG-170, BUG-171
  - Missing generators, room configs, biome asset validation

- [ ] **9.2.4** Concurrency/precision batch (10 bugs): BUG-206 through BUG-213
  - Head-of-line blocking, thread safety, active object verification, quaternion stability

- [ ] **9.2.5** Error handling batch (6 bugs): BUG-214 through BUG-219
  - Silent error swallowing -> logging, error dict consistency

- [ ] **9.2.6** Remaining LOW (12 bugs): BUG-146 through BUG-156
  - Audio duration estimation, rate limit detection, cross-platform paths, env var loading

### 9.3 Test Quality Improvements (TQ-005 through TQ-016)

- [ ] **9.3.1** Fix soft assertions: TQ-005 (dungeon elevation 50% -> 10%), TQ-006 (hash noise range), TQ-007 (road connectivity 10% -> 2%)
- [ ] **9.3.2** Replace 85 weak `assert result is not None` with meaningful assertions (TQ-008)
- [ ] **9.3.3** Add integration tests for compose_map pipeline, generate_prop Tripo flow, multi-floor dungeons, LOD-to-Unity, material transfer (TQ-009)
- [ ] **9.3.4** Add east/west door alignment tests (TQ-010)
- [ ] **9.3.5** Fix resource leaks in tests (TQ-011 through TQ-013)
- [ ] **9.3.6** Fix test determinism (TQ-014) and float precision (TQ-015, TQ-016)

### 9.4 Visual Regression Testing (GAP-30)

- [ ] **9.4.1** Define camera path waypoints for automated visual testing
- [ ] **9.4.2** Capture-and-compare screenshot pipeline
- [ ] **9.4.3** Reference image generation for all building types, terrain biomes, vegetation

### 9.5 Performance Benchmark Suite (NEW-26)

- [ ] **9.5.1** Standard camera path through reference scene
- [ ] **9.5.2** Capture frame times/draw calls/memory over 60 seconds
- [ ] **9.5.3** Compare against previous results, flag regressions
- [ ] **9.5.4** Hardware auto-detect for quality presets on first launch (NEW-22)

### 9.6 Game Polish

- [ ] **9.6.1** Animator transition graph validation (NEW-04) -- verify all states reachable, no dead ends
- [ ] **9.6.2** Root motion vs in-place animation flag per clip (NEW-06)
- [ ] **9.6.3** Environmental storytelling intelligent placement (NEW-15) -- narrative-aware prop positioning
- [ ] **9.6.4** Dialogue consequence system (NEW-16) -- choices affect quest state, NPC relationships
- [ ] **9.6.5** Crash recovery / last checkpoint resume (NEW-23)
- [ ] **9.6.6** Tripo generation quality gate and retry logic (GAP-40)
- [ ] **9.6.7** Per-instance variation for props (GAP-29) -- random scale 0.8-1.2, rotation, color tint, weathering
- [ ] **9.6.8** Weather particle interaction with terrain (GAP-06) -- rain splash, snow accumulation
- [ ] **9.6.9** Player traversal aids (GAP-36) -- climbable cliff faces, ladder anchors, bridge connections
- [ ] **9.6.10** Erosion quality metrics (GAP-31) -- height variance, drainage density, slope distribution histogram

### 9.7 Accessibility & Platform (NEW-25)

- [ ] **9.7.1** Complete accessibility: subtitle background, high-contrast mode, assist modes, FOV slider, UI scale
- [ ] **9.7.2** Platform integration: Steam achievements, cloud saves (requires save system fixes from Phase 1)
- [ ] **9.7.3** Controller/gamepad UI navigation (toolkit gap #35)
- [ ] **9.7.4** Input rebinding UI (toolkit gap #60)

### 9.8 Documentation (NEW-29, NEW-30, NEW-31)

- [ ] **9.8.1** MCP Toolkit API documentation for human contributors (NEW-29)
- [ ] **9.8.2** Unity template output documentation for game designers (NEW-30)
- [ ] **9.8.3** Coding style guide / lint configuration (NEW-31)

---

## Appendix A: Complete Bug-to-Phase Mapping

| Bug ID Range | Phase | Count |
|-------------|-------|-------|
| BUG-001 -- BUG-003 | 1.1 | 3 |
| BUG-004 -- BUG-007 | 1.2 | 4 |
| BUG-008 -- BUG-011 | 1.3 | 4 |
| BUG-012 -- BUG-015 | 1.4 | 4 |
| BUG-016 -- BUG-017 | 1.5 | 2 |
| BUG-018 -- BUG-026 | 1.6 | 9 |
| BUG-027 -- BUG-028, BUG-044 | 1.7 | 3 |
| BUG-029 -- BUG-030 | 1.8 | 2 |
| BUG-031 -- BUG-034 | 1.9 | 4 |
| BUG-035 -- BUG-052 | 1.10 | 18 |
| BUG-175 -- BUG-181 | 1.11 | 7 |
| BUG-092 | 1.12 | 1 |
| TQ-001 -- TQ-004 | 1.13 | 4 |
| BUG-056, BUG-061, BUG-088, BUG-090, BUG-190, BUG-193, BUG-211 | 2 | 7 |
| BUG-130, BUG-157 -- BUG-161, BUG-192 | 3 | 8 |
| BUG-048, BUG-108, BUG-169, BUG-170, BUG-194 | 4 | 5 |
| BUG-037, BUG-095, BUG-096, BUG-104, BUG-109, BUG-117, BUG-186 | 5 | 7 |
| BUG-062, BUG-093, BUG-172 | 6 | 3 |
| BUG-094, BUG-098 | 7 | 2 |
| BUG-107 | 8 | 1 |
| BUG-053 -- BUG-091 (remaining) | 9.1 | ~38 |
| BUG-099 -- BUG-121 (remaining) | 9.1 | ~18 |
| BUG-122 -- BUG-174 | 9.2 | ~52 |
| BUG-182 -- BUG-205 (remaining) | 9.1 | ~18 |
| BUG-206 -- BUG-219 | 9.2 | 14 |
| TQ-005 -- TQ-016 | 9.3 | 12 |
| **Total** | | **219 bugs + 16 TQ** |

## Appendix B: Complete Gap-to-Phase Mapping

| Gap ID | Phase | Description |
|--------|-------|-------------|
| GAP-01 | 8.1 | NavMesh generation pipeline |
| GAP-02 | 5.3 | Collision mesh strategy |
| GAP-03 | 7.3 | Audio zone / reverb integration |
| GAP-04 | 5.7 | Occlusion culling data generation |
| GAP-05 | 7.6 | Minimap / world map data export |
| GAP-06 | 9.6 | Weather particle terrain interaction |
| GAP-07 | 2.5 | Splatmap transfer Blender->Unity |
| GAP-08 | 2.6 | Terrain chunk boundary stitching |
| GAP-09 | 5.2 | LOD meshes -> Unity LODGroup |
| GAP-10 | 2.8 | Roads deform terrain |
| GAP-11 | 2.8 | Buildings terrace terrain |
| GAP-12 | 7.4 | Vegetation exclusion zones |
| GAP-13 | 2.8 | Water body terrain integration |
| GAP-14 | 4.5 | Interior streaming connection |
| GAP-15 | 2.1 | scipy replacement with numpy |
| GAP-16 | 7.6 | End-to-end pipeline test |
| GAP-17 | 4 | Tripo model interior hollowing |
| GAP-18 | 6.3 | Texture tiling at close range |
| GAP-19 | 7.6 | Texture compression strategy |
| GAP-20 | 3.5 | Assembly recipe format |
| GAP-21 | 5.4 | GPU Resident Drawer setup |
| GAP-22 | 5.4 | Adaptive Probe Volumes |
| GAP-23 | 9.6 | Tripo credit costs |
| GAP-24 | 5.1 | Low-tier VRAM target |
| GAP-25 | 5.1 | Generation time profiling |
| GAP-26 | 5.6 | Vegetation instance counts |
| GAP-27 | 7.4 | Terrain-to-building seam |
| GAP-28 | 5.2 | LOD pop-in on vegetation |
| GAP-29 | 9.6 | Prop repetition / uniqueness |
| GAP-30 | 9.4 | Visual regression testing |
| GAP-31 | 9.6 | Erosion quality metrics |
| GAP-32 | 8.2 | Veil corruption terrain integration |
| GAP-33 | 8.3 | Boss arena terrain sculpting |
| GAP-34 | 8.8 | Destructible environment terrain |
| GAP-35 | 8.6 | Interaction / loot point placement |
| GAP-36 | 9.6 | Player traversal aids |
| GAP-37 | 5.5 | Terrain streaming Unity-side |
| GAP-38 | 7.4 | Cross-chunk entity awareness |
| GAP-39 | 2.7 | Heightmap resolution validation |
| GAP-40 | 9.6 | Tripo generation quality gate |
| Toolkit #1 | 3 | Collision mesh generation |
| Toolkit #5 | 4 | Procedural furniture/props |
| Toolkit #7 | 6 | Shader Graph templates |
| Toolkit #9 | 6 | Tessellation/displacement |
| Toolkit #10 | 7 | Material transfer Blender->Unity |
| Toolkit #14 | 6 | VFX Graph asset generation |
| Toolkit #27 | 8 | Trigger volume system |
| Toolkit #31 | 8 | Behavior tree implementations |
| Toolkit #32 | 8 | Inventory UI |
| Toolkit #33 | 8 | Dialogue UI |
| Toolkit #35 | 9 | Controller/gamepad navigation |
| Toolkit #37 | 4 | Cave interior decoration |
| Toolkit #39 | 3 | Offline prop fallback |
| Toolkit #40 | 7 | Blender-to-Unity round-trip |
| Toolkit #41 | 7 | Texture export with FBX |
| Toolkit #42 | 5 | Prefab auto-generation |
| Toolkit #45 | 5 | GPU profiling |
| Toolkit #47 | 5 | Runtime performance monitoring |
| Toolkit #54 | 7 | End-to-end character pipeline |
| Toolkit #55 | 7 | Weapon attachment e2e |
| Toolkit #56 | 7 | Scene composition tool |
| Toolkit #61 | 7 | Blender addon auto-install |
| Toolkit #62 | 7 | Unity bridge auto-install |
| Toolkit #63 | 7 | Cross-tool state persistence |
| Toolkit #64 | 7 | Terrain continuity transfer |
| NEW-03 | 8.7 | Animation retargeting |
| NEW-04 | 9.6 | Animator graph validation |
| NEW-05 | 8.7 | Additive animation layering |
| NEW-06 | 9.6 | Root motion per-clip flag |
| NEW-07 | 8.7 | Footstep terrain splatmap |
| NEW-08 | 8.7 | Combat audio integration |
| NEW-09 | 8.7 | Music-game state integration |
| NEW-10 | 8.5 | Enemy archetype library |
| NEW-11 | 8.1 | Patrol path from NavMesh |
| NEW-12 | 8.5 | Group/squad AI |
| NEW-13 | 8.3 | Boss phase environment |
| NEW-14 | 8.6 | Quest tracking/waypoints |
| NEW-15 | 9.6 | Storytelling placement |
| NEW-16 | 9.6 | Dialogue consequences |
| NEW-17 | 8.2 | Corruption AI effects |
| NEW-18 | 8.4 | Weather gameplay effects |
| NEW-19 | 8.4 | Time-of-day gameplay |
| NEW-20 | 8.4 | Slope movement speed |
| NEW-21 | 8.6 | Destruction loot drops |
| NEW-22 | 9.5 | Hardware auto-detect |
| NEW-23 | 9.6 | Crash recovery |
| NEW-24 | -- | Mod support (deferred) |
| NEW-25 | 9.7 | Platform store integration |
| NEW-26 | 9.5 | Performance benchmark suite |
| NEW-27 | -- | Playtest recording (deferred) |
| NEW-28 | -- | In-game bug reporting (deferred) |
| NEW-29 | 9.8 | API documentation |
| NEW-30 | 9.8 | Template output docs |
| NEW-31 | 9.8 | Style guide / lint config |
| Toolkit #57 | -- | Multiplayer networking (deferred) |
| NEW-01 | -- | Streaming multiplayer (deferred) |
| NEW-02 | -- | Network-safe random (deferred) |

## Appendix C: Deferred Items (Not In Scope)

These items are intentionally excluded from this plan as they require product-level decisions or are not critical for initial AAA quality:

1. **Multiplayer networking** (toolkit gap #57, NEW-01, NEW-02) -- fundamental architecture decision, not a toolkit fix
2. **Mod support framework** (NEW-24) -- post-launch feature
3. **Playtest recording/replay** (NEW-27) -- QA tooling, not production
4. **In-game bug reporting** (NEW-28) -- QA tooling
5. **Console platform support** (toolkit gap #52) -- requires platform SDKs
6. **ECS/DOTS support** (toolkit gap #51) -- architectural decision
7. **Photo mode** (toolkit gap #49) -- polish feature

## Appendix D: Key File Reference

| System | Primary Files |
|--------|---------------|
| Blender Server | `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` |
| Unity Server | `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` |
| Terrain Noise | `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` |
| Terrain Erosion | `Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py` |
| Terrain Materials | `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py` |
| Terrain Advanced | `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py` |
| Terrain Chunking | `Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py` |
| Environment | `Tools/mcp-toolkit/blender_addon/handlers/environment.py` |
| Environment Scatter | `Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py` |
| Vegetation System | `Tools/mcp-toolkit/blender_addon/handlers/vegetation_system.py` |
| Vegetation L-System | `Tools/mcp-toolkit/blender_addon/handlers/vegetation_lsystem.py` |
| LOD Pipeline | `Tools/mcp-toolkit/blender_addon/handlers/lod_pipeline.py` |
| Building Grammar | `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` |
| Building Quality | `Tools/mcp-toolkit/blender_addon/handlers/building_quality.py` |
| Building Interior | `Tools/mcp-toolkit/blender_addon/handlers/building_interior_binding.py` |
| Modular Kit | `Tools/mcp-toolkit/blender_addon/handlers/modular_building_kit.py` |
| Settlement Gen | `Tools/mcp-toolkit/blender_addon/handlers/settlement_generator.py` |
| Settlement Grammar | `Tools/mcp-toolkit/blender_addon/handlers/_settlement_grammar.py` |
| Worldbuilding | `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` |
| Worldbuilding Layout | `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py` |
| Dungeon Gen | `Tools/mcp-toolkit/blender_addon/handlers/_dungeon_gen.py` |
| Road Network | `Tools/mcp-toolkit/blender_addon/handlers/road_network.py` |
| Pipeline State | `Tools/mcp-toolkit/blender_addon/handlers/pipeline_state.py` |
| Pipeline Runner | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/pipeline_runner.py` |
| Tripo Client | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/tripo_client.py` |
| Tripo Studio | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/tripo_studio_client.py` |
| Tripo Post-Proc | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/tripo_post_processor.py` |
| Fal Client | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/fal_client.py` |
| Gemini Client | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/gemini_client.py` |
| ElevenLabs Client | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/elevenlabs_client.py` |
| Blender Client | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/blender_client.py` |
| Socket Server | `Tools/mcp-toolkit/blender_addon/socket_server.py` |
| Execute Sandbox | `Tools/mcp-toolkit/blender_addon/handlers/execute.py` |
| Config | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/config.py` |
| Scene Templates | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/scene_templates.py` |
| Shader Templates | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py` |
| Performance Tmpl | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/performance_templates.py` |
| Gameplay Tmpl | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/gameplay_templates.py` |
| Combat VFX Tmpl | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/combat_vfx_templates.py` (actually `vb_combat_templates.py`) |
| Audio Templates | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/audio_templates.py` |
| VFX Templates | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/vfx_templates.py` |
| Prefab Templates | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/prefab_templates.py` |
| World Templates | `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/world.py` |
| Rigging | `Tools/mcp-toolkit/blender_addon/handlers/rigging.py` |
| Rigging Advanced | `Tools/mcp-toolkit/blender_addon/handlers/rigging_advanced.py` |
| Animation | `Tools/mcp-toolkit/blender_addon/handlers/animation.py` |
| Animation Monster | `Tools/mcp-toolkit/blender_addon/handlers/animation_monster.py` |
| Animation Blob | `Tools/mcp-toolkit/blender_addon/handlers/animation_blob.py` |
| Animation Export | `Tools/mcp-toolkit/blender_addon/handlers/animation_export.py` (if exists) |
| Animation Combat | `Tools/mcp-toolkit/blender_addon/handlers/animation_combat.py` |
| Animation Gaits | `Tools/mcp-toolkit/blender_addon/handlers/animation_gaits.py` |
| Destruction | `Tools/mcp-toolkit/blender_addon/handlers/destruction_system.py` |
| Encounter Spaces | `Tools/mcp-toolkit/blender_addon/handlers/encounter_spaces.py` |
| Scatter Engine | `Tools/mcp-toolkit/blender_addon/handlers/_scatter_engine.py` |
| Terrain Depth | `Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py` |
| Texture Quality | `Tools/mcp-toolkit/blender_addon/handlers/texture_quality.py` |
| Texture Ops | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/texture_ops.py` |
| Model Validation | `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/model_validation.py` |
| pyproject.toml | `Tools/mcp-toolkit/pyproject.toml` |
| Tests | `Tools/mcp-toolkit/tests/` |

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total phases | 9 |
| Total tasks | ~264 |
| CRASH bugs fixed | 17 |
| HIGH bugs fixed | 42 |
| MEDIUM bugs fixed | 93 |
| LOW bugs fixed | 61 |
| Design bugs fixed | 6 |
| Test quality issues fixed | 16 |
| **Total bugs fixed** | **235** |
| Terrain gaps closed | 40 |
| Toolkit gaps closed | ~55 |
| Final scan gaps closed | ~25 |
| **Total gaps closed** | **~120** |
| Research documents synthesized | 75+ |
| Deferred items | 7 |

---

## Appendix E: Gemini-Verified Additional Gaps

These architectural gaps were identified by Gemini CLI cross-verification and confirmed as missing from the original plan. Added to Phase 7 and Phase 9.

### E.1 Production Telemetry/Observability (Phase 9)
- [ ] Add structured logging with correlation IDs across MCP server → Blender TCP → handler chain
- [ ] Add timing instrumentation for every pipeline step (terrain gen time, erosion time, scatter time)
- [ ] Add Blender memory usage reporting after expensive operations
- [ ] Add Unity-side performance counters (draw calls, triangle count, VRAM) exportable from profile_scene

### E.2 AI Backend Resilience (Phase 1, added to bug fixes)
- [ ] Standardize retry logic across ALL external API clients (fal, gemini, elevenlabs, tripo)
- [ ] Add `httpx.HTTPStatusError` to every except clause that uses `raise_for_status()` (BUG-EH-12/13)
- [ ] Add circuit breaker pattern: after N consecutive failures, disable client for cooldown period
- [ ] Unify rate limit handling: all clients should detect 429 and backoff consistently

### E.3 Undo/Checkpoint for AI-Driven Changes (Phase 7)
- [ ] Save Blender scene snapshot before destructive MCP operations (terrain gen, erosion, scatter)
- [ ] Implement rollback via `bpy.ops.ed.undo()` if operation fails mid-way
- [ ] Add `checkpoint_before` parameter to compose_map steps so each step can be individually reverted
- [ ] Track Blender object creation per MCP call for selective undo

### E.4 Advanced Game-Readiness Checks (Phase 5)
- [ ] Add draw call estimation to `game_check` action (count unique materials × mesh objects)
- [ ] Add PBR validation: metallic must be 0 or 1 for dielectrics/metals (flag 7 known violations)
- [ ] Add texture budget estimation per scene (sum BC7/BC5 compressed sizes)
- [ ] Add LOD coverage audit: flag any mesh >1000 tris without LOD chain

### E.5 Large-World Streaming Orchestration (Phase 7)
- [ ] Build TerrainStreamingManager C# template (3x3 tile loading, player-position-based)
- [ ] Add tile dependency graph (which tiles share edges, which tiles have cross-tile roads/rivers)
- [ ] Add async tile generation (generate adjacent tiles while player is in current tile)
- [ ] Add impostor mesh generation for tiles beyond the 3x3 active grid

### E.6 Additional Bugs from Latest Scans (Phase 1)

**From bug_scan_compose_map_pipeline.md (19 bugs):**
- [ ] Fix CM-07: River coordinates X/Y swapped (_map_point_to_terrain_cell returns row,col but handlers expect x,y)
- [ ] Fix CM-08: Same coordinate swap in road waypoints
- [ ] Fix CM-11: Heightmap export hardcodes `/tmp/` path (broken on Windows)
- [ ] Fix CM-01: Water/river steps have no checkpoint resume skip
- [ ] Fix CM-24: Location anchors ignore water positions (towns placed underwater)

**From bug_scan_tcp_protocol.md (22 bugs):**
- [ ] Fix timeout mismatch: client and server both at 300s causes duplicate commands
- [ ] Fix 30s idle timeout killing persistent connections
- [ ] Fix PydanticValidationError not caught in _sync_send retry
- [ ] Add BaseException guard in _process_commands to prevent timer death

**From bug_scan_shader_generation.md (17 bugs):**
- [ ] Fix duplicate ShadowCaster passes in corruption/dissolve shaders
- [ ] Fix force field/water ShadowCaster missing struct definitions
- [ ] Add DepthNormals pass to ALL generated shaders (fixes SSAO)
- [ ] Add ShadowCaster pass to generate_arbitrary_shader

**From bug_scan_procedural_generators.md (17 bugs):**
- [ ] Fix 5 creature generators returning tuples instead of dicts (mouth, eyelid, paw, wing, serpent)
- [ ] Fix vegetation_tree/vegetation_leaf_cards never creating Blender objects
- [ ] Fix tree_type vs style parameter mismatch (all trees always oak)
- [ ] Fix 5mm vertex weld destroying 3mm weapon bevels
- [ ] Fix eye mesh Z-up vs armor/clothing Y-up coordinate mismatch

**From bug_scan_unity_template_correctness.md (16 bugs):**
- [ ] Fix waypoint OnTriggerEnter on singleton instead of individual waypoints
- [ ] Fix InteriorStreamingManager.MemoryBudgetMB IndexOutOfRange
- [ ] Fix day/night interpolation midnight boundary wrap
- [ ] Fix Cinemachine namespace (old vs Unity.Cinemachine)
- [ ] Fix settings slider lambda leak causing exponential volume jumps
- [ ] Fix dolly camera Vector3→Vector2 compile error

**From bug_scan_quality_generators.md (15 bugs):**
- [ ] Fix creature generators double-positioning (vertex offset + obj.location = 2x)
- [ ] Fix missing metadata keys blocking material auto-assignment on all riggable props + clothing
- [ ] Fix armor back items flipped normals (X/Z swap without winding reversal)

**From bug_scan_stress_tests.md (16 bugs):**
- [ ] Fix single quotes in object names breaking generated Python code
- [ ] Fix world_size=0 ZeroDivisionError in biome grammar
- [ ] Add upper bound on heightmap/image allocation sizes to prevent OOM
- [ ] Add NaN/Inf guards at terrain pipeline entry points

**From bug_scan_config_packaging.md (8 bugs):**
- [ ] Fix google-genai vs google.generativeai package mismatch in pyproject.toml
- [ ] Add httpx to pyproject.toml dependencies
- [ ] Add pydantic to pyproject.toml dependencies
- [ ] Fix version mismatch (__init__.py 0.1.0 vs pyproject.toml 3.1.0)

---

## Updated Summary Statistics

| Metric | Count |
|--------|-------|
| Total phases | 9 |
| Total tasks | **~347** |
| CRASH bugs fixed | 17 |
| HIGH bugs fixed | 42 |
| MEDIUM bugs fixed | 93 |
| LOW bugs fixed | 61 |
| Design bugs fixed | 6 |
| Test quality issues fixed | 16 |
| Latest scan bugs added | ~113 |
| **Total bugs addressed** | **~348** |
| Terrain gaps closed | 40 |
| Toolkit gaps closed | ~55 |
| Final scan gaps closed | ~25 |
| Gemini-identified gaps | 5 |
| **Total gaps closed** | **~125** |
| Research documents synthesized | 75+ |
| Deferred items | 7 |

---

*Plan compiled from 61 research agent missions, 26 bug scan missions, 75+ research documents totaling ~3.5MB of findings, and Gemini CLI cross-verification. Every identified bug and gap maps to a specific phase and task. Nothing falls through the cracks.*
