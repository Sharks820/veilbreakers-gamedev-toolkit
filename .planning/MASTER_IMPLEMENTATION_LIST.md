# MASTER IMPLEMENTATION LIST — VeilBreakers MCP Toolkit v8.0
## 750+ Bugs, Gaps, and Issues — Complete Catalog
**Compiled:** 2026-04-03 | **Source:** 50 Opus scan agents | **Status:** UNFIXED

---

## EXECUTION INSTRUCTIONS (READ THIS FIRST)

### Autonomous Execution Protocol
1. **5+ Sonnet agents running at ALL TIMES** for implementation
2. **Haiku agent** for commits, pushes, memory updates, plan % tracking after each confirmed task
3. **After EVERY phase**: Opus + Gemini verification scan — if ANY bug found, re-scan until CLEAN on first pass
4. **No stopping to ask questions** — fully autonomous
5. **Phase order**: Fix tests first → camera → checkpoints → critical pipeline → quality → export → final sweep
6. **Model allocation**: Sonnet for code fixes, Opus for verification/review, Haiku for git ops/bookkeeping

### Phase Execution Order (dependency-aware)
- **Phase 1**: Test suite overhaul (fix 63% false confidence FIRST — can't verify anything without real tests)
- **Phase 2**: Camera system (AI needs eyes before verifying visual fixes)
- **Phase 3**: Checkpoint system (atomic writes, scene validation, skip guards — crash resilience)
- **Phase 4**: Core pipeline CRASH/CRITICAL bugs (terrain flatten, material_ids, LOD rename, compose_interior)
- **Phase 5**: Materials & PBR correctness (metallic binary, missing material keys, auto-bake)
- **Phase 6**: Building architecture quality (rafters, glass, doors, timber frames, grounding)
- **Phase 7**: Interior system overhaul (wire zones, fix rotations, consolidate duplicate systems)
- **Phase 8**: Style enforcement & weathering (Tripo prompts, fal.ai, Unity defaults, torch temperature)
- **Phase 9**: Animation, rigging & export/import (bone names, roughness→smoothness, LODGroup, colliders)
- **Phase 10**: City mapping, props, terrain gen & final sweep (prop placement, scatter, terrain erosion)

---

## PHASE 1: TEST SUITE OVERHAUL (~80 items)

### Critical Test Gaps
- [ ] TEST-001: unity_server.py has ZERO dedicated tests (22 tools, 258 actions)
- [ ] TEST-002: tripo_studio_client.py has only 2 tests (JWT parsing only)
- [ ] TEST-003: model_vault.py has ZERO tests
- [ ] TEST-004: No compose_map integration test
- [ ] TEST-005: No compose_interior integration test
- [ ] TEST-006: blender_server.py only has 11 registration tests, zero action tests
- [ ] TEST-007: vb_code_reviewer.py has only 7 tests for 201 rules

### Weak Assertion Fixes
- [ ] TEST-008: 7,289 tests with weak-only assertions need real correctness checks
- [ ] TEST-009: 46 tests with ZERO assertions need assertions added or removal
- [ ] TEST-010: 11 tests that assert on mock return values need rewriting
- [ ] TEST-011: 4,817 `assert "key" in result` need value verification
- [ ] TEST-012: 5,276 generator tests need geometry/dimension/material checks
- [ ] TEST-013: 520 helper-delegated tests need domain correctness checks

### Missing Integration Tests (write new)
- [ ] TEST-014: compose_map full pipeline test (terrain→water→roads→locations→vegetation)
- [ ] TEST-015: compose_interior full pipeline test (rooms→doors→furniture→props)
- [ ] TEST-016: Tripo→import→process pipeline test
- [ ] TEST-017: Export→reimport roundtrip test
- [ ] TEST-018: Building→interior→furnishing end-to-end test
- [ ] TEST-019: Checkpoint save→crash→resume test (verify data preservation)
- [ ] TEST-020: Name collision resilience test (Blender .001 suffix handling)
- [ ] TEST-021: Furniture rotation correctness test (front faces room, not wall)
- [ ] TEST-022: Terrain flatten parameter matching test
- [ ] TEST-023: material_ids per-face application test
- [ ] TEST-024: LOD rename → downstream reference test
- [ ] TEST-025: Building grounding Z-position test
- [ ] TEST-026: PBR metallic binary validation test
- [ ] TEST-027: Dark fantasy palette compliance test

### Test Reliability
- [ ] TEST-028: 13 non-deterministic random usages need seeds
- [ ] TEST-029: 55 hardcoded /tmp/ paths need cross-platform fixes
- [ ] TEST-030: 3 test files with external service dependencies need skip markers

---

## PHASE 2: CAMERA SYSTEM (~45 items)

### Critical Blind Spots
- [ ] CAM-001: `_with_screenshot()` must accept `object_name` and auto-frame camera before capture
- [ ] CAM-002: `compose_interior` returns json.dumps with ZERO screenshots — change to `_with_screenshot`
- [ ] CAM-003: `generate_3d` returns raw JSON — add screenshot
- [ ] CAM-004: `generate_building` returns raw JSON — add screenshot
- [ ] CAM-005: `generate_prop` returns raw JSON — add screenshot
- [ ] CAM-006: `generate_and_process` returns raw JSON — add screenshot
- [ ] CAM-007: `smart_material`/`trim_sheet`/`macro_variation` return raw JSON — add screenshot

### Camera Positioning Bugs
- [ ] CAM-008: Auto-frame azimuth hardcoded to 35° — make parameterizable
- [ ] CAM-009: Contact sheet default angles wrong order (right/back/left/front, should be front first)
- [ ] CAM-010: Contact sheet distance uses `max(dimensions)*2.5` not bounding sphere — inconsistent
- [ ] CAM-011: ContactSheet_Camera never cleaned up from scene
- [ ] CAM-012: Ground plane Z assumes origin at center — broken for base-origin objects
- [ ] CAM-013: `compute_camera_distance` ignores focal length/FOV

### Missing Camera Modes
- [ ] CAM-014: Add interior camera mode (eye height 1.7m inside room bounds)
- [ ] CAM-015: Add walkthrough camera (player-height path through room)
- [ ] CAM-016: Add detail camera (zoom to sub-region of object)
- [ ] CAM-017: Add orthographic views (front/side/top engineering views)
- [ ] CAM-018: Add quick 256px preview resolution tier for fast checks

### Visual Validation Fixes
- [ ] CAM-019: Visual scoring brightness ideal 120 penalizes dark fantasy — change to 30-80 range
- [ ] CAM-020: Add magenta/missing-texture detection (pink pixel scan)
- [ ] CAM-021: Add color palette match verification against dark fantasy palette
- [ ] CAM-022: Floating geometry detection fails on dark backgrounds — fix algorithm
- [ ] CAM-023: Contact sheet missing bottom view angle
- [ ] CAM-024: Screenshot diff noise threshold 10 too aggressive for dark scenes

### Gemini Integration
- [ ] CAM-025: Wire Gemini review into post-generation quality gate (currently disconnected)
- [ ] CAM-026: Add furniture-specific Gemini review prompt template
- [ ] CAM-027: Add material/color consistency Gemini review prompt
- [ ] CAM-028: Add dark fantasy mood assessment Gemini prompt

### Unity Camera Gaps
- [ ] CAM-029: Only Game View captured, never Scene View — add SceneView screenshot
- [ ] CAM-030: Screenshots saved to disk but NOT returned as image data to Claude
- [ ] CAM-031: Bridge screenshot returns "pending" with no follow-up read
- [ ] CAM-032: No "execute and screenshot" composite action
- [ ] CAM-033: No Scene View camera focus on specific GameObject
- [ ] CAM-034: No Unity equivalent of Blender contact_sheet
- [ ] CAM-035: No gizmo toggle for clean screenshots

### Visual Verification System (NEW)
- [ ] CAM-036: Create `prop_quality.py` with 7 automated checks
- [ ] CAM-037: Implement ground contact validation (raycast per prop)
- [ ] CAM-038: Implement wall intersection detection (BVHTree overlap)
- [ ] CAM-039: Implement orientation validation (front face vs room center)
- [ ] CAM-040: Implement right-side-up check (local Z vs world Z)
- [ ] CAM-041: Implement semantic placement logic (room-type affinity rules)
- [ ] CAM-042: Implement per-prop triangle budget enforcement
- [ ] CAM-043: Wire validation into `_furnish_interior` and `compose_interior`

---

## PHASE 3: CHECKPOINT SYSTEM (~14 items)

- [ ] CKP-001: Fix `interior_results = []` unconditional wipe (line 3071) — move inside if block
- [ ] CKP-002: Make checkpoint writes atomic (temp file + rename)
- [ ] CKP-003: Add Blender scene validation on resume (verify objects exist)
- [ ] CKP-004: Save `steps_failed` to checkpoint
- [ ] CKP-005: Add skip guards for water steps (rivers + water plane)
- [ ] CKP-006: Add skip guards for vegetation scatter
- [ ] CKP-007: Add skip guards for prop scatter
- [ ] CKP-008: Add skip guards for biome paint + lighting
- [ ] CKP-009: Add skip guards for heightmap export
- [ ] CKP-010: Add checkpoint support to `compose_interior`
- [ ] CKP-011: Add checkpoint support to `full_asset_pipeline`
- [ ] CKP-012: Add checkpoint support to `cleanup_ai_model`
- [ ] CKP-013: Expand `params_snapshot` to include biome, vegetation, water, roads
- [ ] CKP-014: Add checkpoint compatibility validation for all params

---

## PHASE 4: CORE PIPELINE CRASH/CRITICAL BUGS (~60 items)

### Terrain Flatten (ROOT CAUSE of floating buildings)
- [ ] PIPE-001: Fix terrain_spline_deform param names (terrain_name→object_name, points→spline_points, strength→falloff, falloff_distance→width)
- [ ] PIPE-002: Add Z coordinate to flatten spline points (anchor_z)
- [ ] PIPE-003: Replace spline-based flatten with area-based `flatten_terrain_zone` for building footprints
- [ ] PIPE-004: Fix foundation side_heights wrong corner indices

### Material Pipeline (ROOT CAUSE of single-material buildings)
- [ ] PIPE-005: Implement `material_ids` handling in `mesh_from_spec` (_mesh_bridge.py)
- [ ] PIPE-006: Create material slots per unique material_id
- [ ] PIPE-007: Assign faces to correct material slots based on material_ids array
- [ ] PIPE-008: Add auto-bake procedural materials before export
- [ ] PIPE-009: Add material manifest JSON export alongside FBX/GLB

### LOD Pipeline (breaks all downstream steps)
- [ ] PIPE-010: Fix LOD rename breaking visual_gate + export in full_asset_pipeline
- [ ] PIPE-011: Fix LOD rename breaking re-validation in _enforce_world_quality
- [ ] PIPE-012: Add UV transfer/re-projection after LOD decimation
- [ ] PIPE-013: Fix retopo target_faces = poly_budget (face vs tri confusion — models 2x overbudget)
- [ ] PIPE-014: Wire per-asset-type budgets into game_check (not flat 50K default)
- [ ] PIPE-015: Unify 3 inconsistent budget tables into one canonical source

### compose_interior (fundamentally broken)
- [ ] PIPE-016: Fix duplicate room shell creation (Step 1 and Step 2 both create shells)
- [ ] PIPE-017: Fix all floors stacking at Z=0 (floor index ignored)
- [ ] PIPE-018: Fix storytelling props defaulting to 4x4m area (room dimensions not passed)
- [ ] PIPE-019: Fix door corridor clearance assuming front wall (actual door positions not passed)
- [ ] PIPE-020: Fix door-to-room linking by array index not by name
- [ ] PIPE-021: Fix same seed for all room storytelling props
- [ ] PIPE-022: Fix lighting probe positions wrong for non-south doors
- [ ] PIPE-023: Fix bounds_overlap padding logic inverted
- [ ] PIPE-024: Fix tavern_hall missing from shell style_map

### Object Name Handling (ROOT CAUSE of invisible buildings)
- [ ] PIPE-025: Return actual Blender object name from generators (handle .001 suffix)
- [ ] PIPE-026: Fix `_position_generated_object` to use returned name, not requested name
- [ ] PIPE-027: Fix `_sample_terrain_height` to handle renamed terrain
- [ ] PIPE-028: Fix `_normalize_map_point` coordinate corruption heuristic
- [ ] PIPE-029: Fix `_normalize_scale` passing zero scale through
- [ ] PIPE-030: Fix `execute_code` return value not captured (import_model gets wrong name)

### Server Bugs
- [ ] PIPE-031: Fix 3 CRASH bugs — Tripo param mismatch (BUG-001), missing import (BUG-002), bpy import outside Blender (BUG-003)
- [ ] PIPE-032: Fix compose_map swallowed exceptions (BUG-177/178/195/204)
- [ ] PIPE-033: Fix async event loop blocking (time.sleep in retry — BUG-183/184)
- [ ] PIPE-034: Fix SQLite thread safety (BUG-186)
- [ ] PIPE-035: Fix pipeline checkpoint atomicity (BUG-185)
- [ ] PIPE-036: Fix httpx.HTTPStatusError not caught (BUG-180/181/202)
- [ ] PIPE-037: Fix code injection via unsanitized mesh_name (BUG-041)
- [ ] PIPE-038: Fix socket timeout mismatch 30s vs 300s (BUG-120)
- [ ] PIPE-039: Add httpx to pyproject.toml dependencies (BUG-092)
- [ ] PIPE-040: Fix generate_map_package silently swallows game_check + LOD + export failures

### Missing Material Keys (Runtime KeyError)
- [ ] PIPE-041: Add `stone_dark` to MATERIAL_LIBRARY
- [ ] PIPE-042: Add `stone_fortified` to MATERIAL_LIBRARY
- [ ] PIPE-043: Add `stone_heavy` to MATERIAL_LIBRARY
- [ ] PIPE-044: Add `stone_slab` to MATERIAL_LIBRARY
- [ ] PIPE-045: Add `stone_parapet` to MATERIAL_LIBRARY
- [ ] PIPE-046: Add `landmark_corrupted` and `landmark_clean` to MATERIAL_LIBRARY

### Stubbed Systems
- [ ] PIPE-047: asset-pipeline/server.py — 5 AI endpoints completely stubbed (not_yet_implemented)
- [ ] PIPE-048: performance_budget_check handler is a non-functional stub

---

## PHASE 5: MATERIALS & PBR CORRECTNESS (~50 items)

### Metallic Binary Fixes (ALL metals must be 1.0, ALL dielectrics must be 0.0)
- [ ] MAT-001: material_tiers.py — iron 0.85→1.0, steel 0.90→1.0, silver 0.95→1.0, gold 0.95→1.0, mithril 0.98→1.0, adamantine 0.99→1.0, orichalcum 0.92→1.0
- [ ] MAT-002: material_tiers.py — obsidian 0.3→0.0, dragonbone 0.4→0.0, ironwood 0.15→0.0, dragon_leather 0.15→0.0
- [ ] MAT-003: procedural_materials.py — rusted_iron 0.85→1.0, tarnished_bronze 0.90→1.0, chain_metal 0.95→1.0, glass 0.05→0.0
- [ ] MAT-004: texture_quality.py — rusted_armor 0.95→1.0, tarnished_gold 0.95→1.0, aged_bronze 0.90→1.0, rusted_iron 0.85→1.0, ice 0.02→0.0
- [ ] MAT-005: texture_quality.py trim — metal_strap 0.90→1.0, metal_nail_row 0.85→1.0, chain_link 0.92→1.0
- [ ] MAT-006: terrain_materials.py — ice 0.02→0.0, prismatic_rock 0.20→0.0, crystal_wall 0.30→0.0

### Material Pipeline Fixes
- [ ] MAT-007: Fix material_assign overwrites slot 0 (destroys multi-material)
- [ ] MAT-008: Add PBR value clamping on material create/modify (metallic 0/1, roughness 0.04-0.96)
- [ ] MAT-009: Add albedo sRGB range validation (30-240)
- [ ] MAT-010: Add normal map unit-length validation
- [ ] MAT-011: Add sRGB↔linear conversion utility function
- [ ] MAT-012: Add MCP action for procedural/smart materials (currently must use blender_execute)
- [ ] MAT-013: Add emission/SSS/transmission support to basic material handler
- [ ] MAT-014: Fix polished_steel wear_intensity 0.05 (pristine) → minimum 0.15

### Texture Pipeline
- [ ] MAT-015: Add ORM channel packing to bake pipeline (R=AO, G=Roughness, B=Metallic)
- [ ] MAT-016: Add per-asset-type texture resolution policy (props 512, characters 2048, etc.)
- [ ] MAT-017: Fix de-lighting uint8 quantization (use float32 for Gaussian blur)
- [ ] MAT-018: Fix wood grain color unclamped (can exceed 1.0)
- [ ] MAT-019: Fix fabric material assumes UV exists (should fallback to Object coords)
- [ ] MAT-020: Fix roughness MULTIPLY_ADD unclamped (enable use_clamp on Math node)

---

## PHASE 6: BUILDING ARCHITECTURE QUALITY (~40 items)

### Exterior Geometry
- [ ] ARCH-001: Fix rafters not angled to roof pitch (flat at z=0)
- [ ] ARCH-002: Add glass pane material with amber emission to gothic windows
- [ ] ARCH-003: Generate door leaf as separate animatable mesh
- [ ] ARCH-004: Complete timber frames on all 4 sides (currently front-only)
- [ ] ARCH-005: Fix flying buttress arch (stepped boxes → smooth curve)
- [ ] ARCH-006: Add base course to stone walls (1.3-1.5x taller bottom blocks)
- [ ] ARCH-007: Fix diagonal braces (axis-aligned boxes → rotated beams)
- [ ] ARCH-008: Fix roof overhang applied twice (0.6m instead of 0.3m)
- [ ] ARCH-009: Fix roof Y-position double-offset
- [ ] ARCH-010: Fix arrow slits additive geometry → subtractive holes
- [ ] ARCH-011: Fix gable end triangle doesn't reach ridge line
- [ ] ARCH-012: Fix shutters clip through adjacent wall surface
- [ ] ARCH-013: Fix no ceiling slabs between floors (only 8cm thin slab)
- [ ] ARCH-014: Fix battlement merlons don't align at wall corners
- [ ] ARCH-015: Fix no foundation ever generated (defaults to 0 height)
- [ ] ARCH-016: Fix corner stone overlap/z-fighting between adjacent walls
- [ ] ARCH-017: Add iron strap hinges to doorways
- [ ] ARCH-018: Add threshold stones to doorways
- [ ] ARCH-019: Add gutter/drip edge to roofs
- [ ] ARCH-020: Add soffit under roof overhang

### Building-on-Terrain
- [ ] ARCH-021: Wire `flatten_terrain_zone` into compose_map (replace broken spline approach)
- [ ] ARCH-022: Fix castle walls floating on slopes (no terrain adaptation)
- [ ] ARCH-023: Fix perimeter walls placed at Z=0 (no terrain sampling)
- [ ] ARCH-024: Fix settlement roads are pure 2D (no terrain interaction)
- [ ] ARCH-025: Fix vegetation exclusion zone too small for large buildings (3m fixed buffer)
- [ ] ARCH-026: Add vegetation density gradient near buildings
- [ ] ARCH-027: Add ground treatment around buildings (dirt apron, cobblestone)
- [ ] ARCH-028: Fix `_sample_scene_height` hits buildings not terrain when terrain_name=None
- [ ] ARCH-029: Fix town buildings single-point height sampling → multi-point + foundation

### Multi-Story
- [ ] ARCH-030: Add jettying (upper floor overhang) for medieval style
- [ ] ARCH-031: Add string courses between floors on exterior
- [ ] ARCH-032: Place staircases between floors
- [ ] ARCH-033: Add vertical window alignment constraint across floors

### Modular Kit
- [ ] ARCH-034: Fix modular kit UV XZ-projection stretching on Y-facing faces
- [ ] ARCH-035: Fix modular wall_corner_inner doubled geometry at corner

---

## PHASE 7: INTERIOR SYSTEM OVERHAUL (~60 items)

### Furniture Rotation (THE 180-degree bug)
- [ ] INT-001: Fix _pick_wall_position rotations ALL 180° wrong in _building_grammar.py
- [ ] INT-002: Fix _furnish_interior rotations ALL 180° wrong in settlement_generator.py
- [ ] INT-003: Fix cluster face_anchor formula off by 180° (chairs face away from tables)
- [ ] INT-004: Fix center items near-zero rotation (desks/anvils always face same direction)
- [ ] INT-005: Fix corner items hardcoded rotation=0 regardless of corner position
- [ ] INT-006: Establish and enforce forward-axis convention across all furniture generators

### Wire Dead Code
- [ ] INT-007: Wire ROOM_ACTIVITY_ZONES into generate_interior_layout (250 lines of dead code)
- [ ] INT-008: Wire quality_tier/occupied_state through settlement generation (never passed from callers)
- [ ] INT-009: Consolidate duplicate furniture systems (remove _furnish_interior, use generate_interior_layout exclusively)

### Layout Intelligence
- [ ] INT-010: Add furniture count scaling with room area
- [ ] INT-011: Add 2-3 template variants per room type (small/medium/large)
- [ ] INT-012: Add 2D room subdivision (L-shapes, T-shapes instead of strips)
- [ ] INT-013: Add internal doors between rooms
- [ ] INT-014: Position rugs under furniture clusters (not random center)
- [ ] INT-015: Align chandeliers over tables
- [ ] INT-016: Add "near_door" wall preference for weapon racks
- [ ] INT-017: Add "same_wall" constraint for barracks beds and library bookshelves
- [ ] INT-018: Add building-face-road logic (buildings face streets, not center)

### Missing Furniture Generators (25 types)
- [ ] INT-019: nightstand, desk, bar_counter, long_table, large_table
- [ ] INT-020: throne (non-bone), pew, weapon_rack, armor_stand
- [ ] INT-021: cooking_fire, bellows, tool_rack, quench_trough
- [ ] INT-022: serving_table, bunk_bed, map_display, trophy_mount
- [ ] INT-023: carpet, coin_pile, display_case, locked_chest, safe
- [ ] INT-024: shelf_with_bottles, herb_rack, distillation_apparatus
- [ ] INT-025: bench (communal seating — critical for taverns/halls/chapels)
- [ ] INT-026: stool (taverns/workshops need stools not just chairs)

### Missing Room Types
- [ ] INT-027: Add bath_house room config + spatial graph + clutter
- [ ] INT-028: Add stable room config + spatial graph + clutter
- [ ] INT-029: Add observatory room config + spatial graph + clutter
- [ ] INT-030: Add cellar room config + spatial graph + clutter
- [ ] INT-031: Add market room config (proper, not just flat list)

### Room Spatial Graphs (10 types missing)
- [ ] INT-032: Add spatial graphs for tavern_hall, guard_barracks, treasury, manor, guild_hall, study, storage, barracks, guard_post, torture_chamber

### Missing Clutter (9 room types)
- [ ] INT-033: Add clutter for dining_hall, war_room, great_hall, barracks, guard_post, treasury, study, torture_chamber, smithy

### Furniture Size Fixes
- [ ] INT-034: Throne 1.5×1.2 → 1.0×0.8
- [ ] INT-035: Bookshelf 2.0×0.5 → 1.2×0.35
- [ ] INT-036: Anvil 0.7×0.5 → 0.5×0.35

### Prop Placement
- [ ] INT-037: Fix table/shelf surface props floating in mid-air (scatter at random XY, not ON furniture)
- [ ] INT-038: Fix prop_density furniture collision check AVOIDS furniture (opposite of what table props need)

---

## PHASE 8: STYLE ENFORCEMENT & WEATHERING (~25 items)

- [ ] STY-001: Add VB_STYLE_PREFIX to all Tripo generate_from_text prompts
- [ ] STY-002: Change fal.ai default style "fantasy" → "dark fantasy, weathered Gothic medieval, desaturated"
- [ ] STY-003: Add negative prompts to fal.ai ("bright, colorful, pristine, clean, modern, vibrant")
- [ ] STY-004: Change Unity default time_of_day "noon" → "dusk"
- [ ] STY-005: Create Soulsborne lighting preset (single dominant + warm islands + cold ambient)
- [ ] STY-006: Add leaded_glass_amber material preset (translucent, amber emission)
- [ ] STY-007: Change apply_moss_growth default direction "bottom" → "north"
- [ ] STY-008: Change torch color temperature 2800K → 2200K
- [ ] STY-009: Hardcode generate_roof default material to "slate_tiles"
- [ ] STY-010: Increase Unity fog density 0.01 → 0.025
- [ ] STY-011: Add corruption actual light emitters (purple/green spot lights)
- [ ] STY-012: Force minimum wear_intensity 0.15 on ALL metal presets
- [ ] STY-013: Fix moss north-facing direction stubbed (uses constant 0.5 instead of normal check)
- [ ] STY-014: Fix rain staining direction (darkest at top instead of below ledges)
- [ ] STY-015: Auto-apply weathering to standalone buildings/castles/settlements
- [ ] STY-016: Fix wear map lookup uses wrong name pattern (always fails silently)

---

## PHASE 9: ANIMATION, RIGGING & EXPORT/IMPORT (~50 items)

### Bone Name Fixes
- [ ] RIG-001: Fix BLOB_PSEUDOPOD_BONES references nonexistent bones (pseudopod→tentacle)
- [ ] RIG-002: Fix DEF-jaw used in 5+ animations but only serpent/dragon have jaw
- [ ] RIG-003: Fix monster animations hardcode biped bone names (silent on non-biped rigs)
- [ ] RIG-004: Add bone existence filter to ALL animation handlers (not just walk)
- [ ] RIG-005: Fix DEF-spine.003/.004 absent from floating/amorphous templates

### Missing Animations
- [ ] RIG-006: Add bird-specific gait animation
- [ ] RIG-007: Add insect/arachnid attack animations
- [ ] RIG-008: Add floating creature locomotion
- [ ] RIG-009: Fix amorphous animations (only idle works)

### Rigging Pipeline
- [ ] RIG-010: Fix rig_auto_weight param object_name vs expected mesh_name
- [ ] RIG-011: Fix foot contact detection hardcodes DEF-foot.L/R (non-biped gets zero events)

### Export Fixes
- [ ] EXP-001: Add roughness→smoothness inversion + metallic-smoothness channel packing for Unity URP
- [ ] EXP-002: Fix LODGroup component never created in Unity bridge (detects but doesn't instantiate)
- [ ] EXP-003: Fix collision mesh naming _COL → add Unity-side consumer that creates MeshCollider
- [ ] EXP-004: Add importTangents to generate_fbx_import_script
- [ ] EXP-005: Add explicit vertex color export flag to FBX export
- [ ] EXP-006: Fix vertex color linear/sRGB space mismatch
- [ ] EXP-007: Add UV2 lightmap layer ordering enforcement before export
- [ ] EXP-008: Add custom properties export (use_custom_props=True for FBX, export_extras=True for GLB)
- [ ] EXP-009: Add texture embedding/path configuration for FBX
- [ ] EXP-010: Add automated Blender→Unity file copy + import + verify pipeline
- [ ] EXP-011: Fix scene hierarchy missing parent-child, materials, collections
- [ ] EXP-012: Add texture type auto-detection on Unity import (normal maps, metallic maps)
- [ ] EXP-013: Add mipmap streaming configuration for Unity
- [ ] EXP-014: Fix add_leaf_bones for Humanoid avatar types

---

## PHASE 10: CITY MAPPING, PROPS, TERRAIN & FINAL SWEEP (~80 items)

### Terrain Generation
- [ ] TERR-001: Fix gradient recomputed inside per-cluster loop (50x slowdown)
- [ ] TERR-002: Fix wind erosion 40% mass loss (0.05 removed, 0.03 deposited)
- [ ] TERR-003: Fix MAX/MIN blend modes (compare result+lh instead of result vs lh)
- [ ] TERR-004: Fix compute_slope_map ignores cell spacing
- [ ] TERR-005: Fix thermal erosion brush talus inversely proportional to weight
- [ ] TERR-006: Fix duplicate ridged_multifractal definitions (first is dead code)

### City/Town Layout
- [ ] CITY-001: Fix Voronoi town roads are Bresenham pixel lines → smooth curves
- [ ] CITY-002: Fix buildings face settlement center not nearest road
- [ ] CITY-003: Fix uniform 2m building gap → per-district density variation
- [ ] CITY-004: Add alley geometry between building plots
- [ ] CITY-005: Enforce building plot road frontage
- [ ] CITY-006: Add road loops (MST-only creates tree network)
- [ ] CITY-007: Fix generate_location_spec has zero terrain awareness
- [ ] CITY-008: Add natural landmarks to world graph

### Prop Placement
- [ ] PROP-001: Fix table/shelf props placed at random XY, not ON furniture surfaces
- [ ] PROP-002: Add functional relationship enforcement (tools near workbench)
- [ ] PROP-003: Add LOD chains for non-tree scatter (bushes, rocks)
- [ ] PROP-004: Fix vegetation exclusion has ZERO zones in scatter_biome_vegetation

### World Generation Bugs
- [ ] WORLD-001: Fix billboard quads face +Z (flat on ground) — vegetation LOD3 invisible
- [ ] WORLD-002: Fix concentric_organic layout falls through to random scatter
- [ ] WORLD-003: Fix water mesh double-height (vertex Z + obj.location both set to water_level)
- [ ] WORLD-004: Fix non-square mesh crashes in 4 locations
- [ ] WORLD-005: Fix floor height hardcoded 3.5m but buildings range 3.4-6.0m
- [ ] WORLD-006: Fix wind vertex color incompatibility between two functions
- [ ] WORLD-007: Fix BMesh memory leaks (free not called in exception paths)

### Remaining Server/Client Bugs
- [ ] MISC-001: Fix FAL_KEY env var race condition between concurrent calls
- [ ] MISC-002: Fix Gemini REST fallback hardcodes image/png MIME type
- [ ] MISC-003: Fix ElevenLabs rate limit detection fragile string matching
- [ ] MISC-004: Fix ElevenLabs time.sleep blocks event loop
- [ ] MISC-005: Fix asset_catalog.py full-table SELECT * on every query
- [ ] MISC-006: Fix config.py relative path defaults break on OneDrive
- [ ] MISC-007: Fix GLB reader loads entire file into memory
- [ ] MISC-008: Fix model_vault grows unboundedly with no pruning
- [ ] MISC-009: Fix xatlas UV fallback broken index math (assigns wrong UVs)
- [ ] MISC-010: Fix boolean cleanup passes BMElemSeq not list (crash risk)
- [ ] MISC-011: Fix 5mm vertex weld tolerance destroys small prop detail
- [ ] MISC-012: Fix _enhance_mesh_detail forces 500 vert minimum on all props
- [ ] MISC-013: Fix deprecated mesh.vertex_colors in terrain_materials.py
- [ ] MISC-014: Fix hardcoded /tmp/veilbreakers_exports breaks on Windows
- [ ] MISC-015: Fix aaa_verify temp directory leaked
- [ ] MISC-016: Fix missing encoding="utf-8" on file writes
- [ ] MISC-017: Fix tempfile.mktemp race condition in _tool_runner.py
- [ ] MISC-018: Fix _LOC_HANDLERS missing settlement/interior/hearthvale types
- [ ] MISC-019: Fix ZeroDivisionError in worldbuilding_layout.py target_area=0
- [ ] MISC-020: Fix L-system oak at 8 iterations = 4.7M vertices (freeze Blender)

### Architecture Research Items (implement from research docs)
- [ ] RES-001: Implement 10-phase interior generation pipeline (from AAA_INTERIOR_DESIGN_BEST_PRACTICES.md)
- [ ] RES-002: Implement scene vignettes (20+ templates from research)
- [ ] RES-003: Implement density curves for prop placement
- [ ] RES-004: Implement segmented gate doors (portcullis, drawbridge, double doors)
- [ ] RES-005: Implement Generate→Verify→Fix visual feedback loop
- [ ] RES-006: Implement circuit breaker + per-command timeout scaling
- [ ] RES-007: Implement chunked settlement generation (break monolithic handlers)
- [ ] RES-008: Implement mesh instance caching for repeated props
- [ ] RES-009: Add progress reporting for long-running handlers

### Loop Prevention (from architecture design)
- [ ] LOOP-001: Implement mandatory auto-checkpoint for compose_map
- [ ] LOOP-002: Implement circuit breaker (fingerprint tracking, 3-failure threshold)
- [ ] LOOP-003: Implement per-command timeout scaling
- [ ] LOOP-004: Implement progressive complexity reduction on failure
- [ ] LOOP-005: Implement heartbeat protocol for long operations
- [ ] LOOP-006: Truncate compose_map response JSON (summary only, not full nested results)
- [ ] LOOP-007: Skip screenshots on intermediate orchestration steps

---

## REFERENCE: Research Documents on Disk
1. `.planning/research/MEDIEVAL_BUILDING_INTERIORS_REFERENCE.md` (2,776 lines)
2. `.planning/research/MEDIEVAL_TOWN_CASTLE_ARCHITECTURE.md`
3. `.planning/research/castle_terrain_medieval_landscape_research.md`
4. `.planning/research/AAA_INTERIOR_DESIGN_BEST_PRACTICES.md`
5. `.planning/research/AAA_PROCEDURAL_QUALITY_RESEARCH.md`
6. `.planning/research/visual_feedback_loop_design.md`
7. `.planning/research/DESIGN_loop_prevention.md`
8. `.planning/research/MASTER_BUG_LIST.md` + `MASTER_FINDINGS_COMPLETE.md`

## REFERENCE: Integration Tests Written
- `tests/test_integration_pipelines.py` (62 tests, all passing)
