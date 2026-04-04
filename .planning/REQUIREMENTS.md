# Requirements: v10.0 — Total Quality: Zero Gaps Remaining

**Source:** V9_MASTER_FINDINGS.md (sections 1-19), visual audit scorecard, cross-session findings, user directives
**Verification:** Every phase scanned by Opus until CLEAN. zai visual verification required for AAA grade.
**Protocol:** After EVERY phase -> Opus scan -> fix round if ANY bugs/gaps -> re-scan -> repeat until CLEAN. Only then advance.

---

## PIPE — Pipeline & Systemic Fixes

- [ ] **PIPE-01**: Fix 3 pipeline dispatch bugs (asset_pipeline COMMAND_HANDLERS, _LOC_HANDLERS settlement routing, param shape mismatches)
- [ ] **PIPE-02**: Fix 42 Z=0 hardcoded placements across 9 files with safe_place_object() utility
- [ ] **PIPE-03**: Fix 6 deprecated Blender 5.0 API calls (group.inputs.new -> interface.new_socket, Musgrave -> Noise, cap_fill)
- [ ] **PIPE-04**: Fix Y-axis vertical bugs (full codebase grep, terrain_features cliff outcrop)
- [ ] **PIPE-05**: Wire compose_world_map smart planner into compose_map Step 5
- [ ] **PIPE-06**: Create smootherstep() shared utility, replace 35 linear interpolation sites
- [ ] **PIPE-07**: Fix all square-terrain assumptions (6+ files: chunking, scatter, road, export, sculpt, layers)
- [ ] **PIPE-08**: Fix rectangular terrain bugs (heightmap export squash, road warp, scatter drift)

## MAT — Material & Texture Wiring

- [ ] **MAT-01**: Wire material library (52 materials + 6 procedural generators) into ALL generators post-mesh
- [ ] **MAT-02**: Fix 6 material creation sites that never set Base Color on Principled BSDF
- [ ] **MAT-03**: Wire HeightBlend node group (currently DEAD CODE) into biome terrain materials
- [ ] **MAT-04**: Wire 14 biome palettes (BIOME_PALETTES_V2) into terrain generation
- [ ] **MAT-05**: Fix castle roughness textures (ALL BLACK -> correct values)
- [ ] **MAT-06**: Create wet rock material (referenced but never implemented)
- [ ] **MAT-07**: Add curvature-driven wear to all materials
- [ ] **MAT-08**: Add micro-detail normal maps
- [ ] **MAT-09**: Enforce dark fantasy palette (Saturation <40%, Value 10-50%) on all generators
- [ ] **MAT-10**: Fix terrain material duplication on repeated runs

## GEN — Broken Generator Fixes

- [ ] **GEN-01**: Fix 5 crashed creature part generators (creature_mouth/eyelid/paw/wing/serpent -- tuple error)
- [ ] **GEN-02**: Fix vegetation_tree (returns raw vertex data, never creates Blender object)
- [ ] **GEN-03**: Fix vegetation_leaf_cards (generates 0 vertices, 0 cards)
- [ ] **GEN-04**: Fix boss arena generator (cap_fill Blender 5.0 API break)
- [ ] **GEN-05**: Fix town generator (crashes Blender even at building_count=3)
- [ ] **GEN-06**: Fix orientation bugs (wolf upside-down, door lying flat, shield horizontal)
- [ ] **GEN-07**: Fix proportion bugs (shield half-size, axe paper-thin, mace head undersized, merlons undersized)

## WIRE — Dead Code Wiring

- [ ] **WIRE-01**: Wire VEGETATION_GENERATOR_MAP (15+ real generators) replacing placeholder cubes
- [ ] **WIRE-02**: Wire modular building kit (260 pieces, 52 core x 5 styles) into building/castle generation
- [ ] **WIRE-03**: Wire settlement_generator (15 types) -- route castle through it instead of box generator
- [ ] **WIRE-04**: Wire AAA water handler (spline-following mesh + flow vertex colors) correctly in compose_map
- [ ] **WIRE-05**: Wire spline-terrain deformation for rivers and roads
- [ ] **WIRE-06**: Wire L-system trees (4 species: oak/birch/twisted/dead) replacing lollipop meshes
- [ ] **WIRE-07**: Wire interior binding (14 room types) into settlement generation
- [ ] **WIRE-08**: Wire atmospheric volumes, light integration LIGHT_PROP_MAP, prop density/quality
- [ ] **WIRE-09**: Wire coastline generator + 7 dead-code terrain features
- [ ] **WIRE-10**: Wire MST road network replacing simple paths
- [ ] **WIRE-11**: Wire building_interior_binding.py (currently NOT IMPORTED in __init__.py)

## GEOM — Geometry Quality Overhaul

- [ ] **GEOM-01**: Weapon geometry redesign -- 3-10x more verts, proper blade/guard/pommel silhouettes
- [ ] **GEOM-02**: Armor anatomical fit + layered plate detail + articulated fingers on gauntlet
- [ ] **GEOM-03**: Creature anatomy overhaul -- musculature, skeletal deformation zones, proper proportions
- [ ] **GEOM-04**: Prop detail geometry -- iron banding, locks, hinges, wood grain, rope braid, carved lettering
- [ ] **GEOM-05**: Clothing cloth-sim topology -- proper vertex density for deformation, seams, folds
- [ ] **GEOM-06**: Interior furniture quality -- real mesh shapes replacing cube primitives
- [ ] **GEOM-07**: Dungeon/cave height variation (3m -> 6-8m+), stalactites, environmental detail, rock meshes
- [ ] **GEOM-08**: Castle wall thickness (1.5m -> 2-3m), gatehouse arches, historical merlon sizing
- [ ] **GEOM-09**: Terrain micro-undulation (5-15cm/m), macro variation, terrain skirt geometry
- [ ] **GEOM-10**: Scree/talus at every cliff base, smootherstep on ALL terrain feature transitions
- [ ] **GEOM-11**: Chain poly optimization (288 -> 80 tris/link), flag cloth density increase
- [ ] **GEOM-12**: Building rubble stone detail, timber framing, roof tile variation, shutters/signs

## EXPORT — Export Pipeline Completion

- [ ] **EXPORT-01**: Add FBX export step to compose_map for all non-terrain objects
- [ ] **EXPORT-02**: Add texture bake step to pipeline (diffuse, normal, AO, curvature)
- [ ] **EXPORT-03**: Add LOD generation step with silhouette-preserving decimation
- [ ] **EXPORT-04**: Add game_check validation step before export
- [ ] **EXPORT-05**: Add collision mesh generation (UCX_ prefix)
- [ ] **EXPORT-06**: Vegetation instance serialization (Blender scatter -> Unity TreeInstance)
- [ ] **EXPORT-07**: Splatmap-to-image export for Unity Terrain alphamap
- [ ] **EXPORT-08**: Fix aaa_verify stale screenshot bug (yaw/pitch ignored, old PNGs reused)
- [ ] **EXPORT-09**: Fix generate_map_package broken group export

## SAFE — Data Safety & Integrity

- [ ] **SAFE-01**: Fix Tripo texture overwrite (cleanup overwrites embedded textures with blanks)
- [ ] **SAFE-02**: Fix checkpoint atomicity (interior_results guard + atomic writes via temp+rename)
- [ ] **SAFE-03**: Fix compose_interior discarding binding geometry
- [ ] **SAFE-04**: Fix multi-floor interior semantics (Z=0 flat, not multi-level)
- [ ] **SAFE-05**: Fix settlement scaling mismatch (village=4-8 vs plan=15, city=20-40 vs plan=100+)
- [ ] **SAFE-06**: Fix scene_hierarchy.json not map-scoped (leaks helpers/unrelated objects)

## CITY — Starter City Generation & Verification

- [x] **CITY-01**: Generate full terrain with cliffs, waterfalls, rivers, multi-biome landscape
- [x] **CITY-02**: Generate starter city (Hearthvale) with castle, walls, buildings, roads integrated into terrain
- [x] **CITY-03**: Generate walkable interiors for key buildings (tavern, blacksmith, chapel, keep)
- [x] **CITY-04**: Populate with environmental assets (vegetation, rocks, props, scatter)
- [x] **CITY-05**: Use Tripo for city props, interior furnishing, and environmental assets
- [x] **CITY-06**: zai visual verification -- every area must score AAA or fix+regenerate until it does
- [x] **CITY-07**: Full compose_map pipeline execution with all systems wired

## BRIDGE — Unity Integration

- [ ] **BRIDGE-01**: Add 16 missing Unity bridge handlers for real-time GameObject/component/scene ops
- [ ] **BRIDGE-02**: Live Blender integration testing -- verify all 37 MCP tools function correctly
- [ ] **BRIDGE-03**: Verify v8.0 fixes still working (camera, checkpoints, pipeline, materials, architecture, interiors, animation, export)

## TEST — Quality Assurance

- [x] **TEST-01**: All existing tests pass (19,850+ baseline)
- [x] **TEST-02**: New tests for all fixed generators and wired systems
- [x] **TEST-03**: Visual regression -- zai before/after for each generator category
- [x] **TEST-04**: Opus verification scan after every phase -- follow-up rounds until CLEAN

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 39 | Pending |
| PIPE-02 | Phase 39 | Pending |
| PIPE-03 | Phase 39 | Pending |
| PIPE-04 | Phase 39 | Pending |
| PIPE-05 | Phase 39 | Pending |
| PIPE-06 | Phase 39 | Pending |
| PIPE-07 | Phase 39 | Pending |
| PIPE-08 | Phase 39 | Pending |
| MAT-01 | Phase 40 | Pending |
| MAT-02 | Phase 40 | Pending |
| MAT-03 | Phase 40 | Pending |
| MAT-04 | Phase 40 | Pending |
| MAT-05 | Phase 40 | Pending |
| MAT-06 | Phase 40 | Pending |
| MAT-07 | Phase 40 | Pending |
| MAT-08 | Phase 40 | Pending |
| MAT-09 | Phase 40 | Pending |
| MAT-10 | Phase 40 | Pending |
| GEN-01 | Phase 41 | Pending |
| GEN-02 | Phase 41 | Pending |
| GEN-03 | Phase 41 | Pending |
| GEN-04 | Phase 41 | Pending |
| GEN-05 | Phase 41 | Pending |
| GEN-06 | Phase 41 | Pending |
| GEN-07 | Phase 41 | Pending |
| WIRE-01 | Phase 42 | Pending |
| WIRE-02 | Phase 42 | Pending |
| WIRE-03 | Phase 42 | Pending |
| WIRE-04 | Phase 42 | Pending |
| WIRE-05 | Phase 42 | Pending |
| WIRE-06 | Phase 42 | Pending |
| WIRE-07 | Phase 42 | Pending |
| WIRE-08 | Phase 42 | Pending |
| WIRE-09 | Phase 42 | Pending |
| WIRE-10 | Phase 42 | Pending |
| WIRE-11 | Phase 42 | Pending |
| GEOM-01 | Phase 43 | Pending |
| GEOM-02 | Phase 43 | Pending |
| GEOM-03 | Phase 43 | Pending |
| GEOM-04 | Phase 44 | Pending |
| GEOM-05 | Phase 44 | Pending |
| GEOM-06 | Phase 44 | Pending |
| GEOM-07 | Phase 44 | Pending |
| GEOM-08 | Phase 44 | Pending |
| GEOM-09 | Phase 44 | Pending |
| GEOM-10 | Phase 44 | Pending |
| GEOM-11 | Phase 44 | Pending |
| GEOM-12 | Phase 44 | Pending |
| SAFE-01 | Phase 45 | Pending |
| SAFE-02 | Phase 45 | Pending |
| SAFE-03 | Phase 45 | Pending |
| SAFE-04 | Phase 45 | Pending |
| SAFE-05 | Phase 45 | Pending |
| SAFE-06 | Phase 45 | Pending |
| EXPORT-01 | Phase 46 | Pending |
| EXPORT-02 | Phase 46 | Pending |
| EXPORT-03 | Phase 46 | Pending |
| EXPORT-04 | Phase 46 | Pending |
| EXPORT-05 | Phase 46 | Pending |
| EXPORT-06 | Phase 46 | Pending |
| EXPORT-07 | Phase 46 | Pending |
| EXPORT-08 | Phase 46 | Pending |
| EXPORT-09 | Phase 46 | Pending |
| BRIDGE-01 | Phase 47 | Pending |
| BRIDGE-02 | Phase 47 | Pending |
| BRIDGE-03 | Phase 47 | Pending |
| CITY-01 | Phase 48 | Complete |
| CITY-02 | Phase 48 | Complete |
| CITY-03 | Phase 48 | Complete |
| CITY-04 | Phase 48 | Complete |
| CITY-05 | Phase 48 | Complete |
| CITY-06 | Phase 48 | Complete |
| CITY-07 | Phase 48 | Complete |
| TEST-01 | Phase 39, 48 | Complete |
| TEST-02 | Phase 47, 48 | Complete |
| TEST-03 | Phase 43, 44, 48 | Complete |
| TEST-04 | Phase 39-48 (all) | Complete |

**Coverage: 67/67 requirements mapped (100%)**

## Out of Scope

- Multiplayer/networking -- single-player game
- Mobile optimization -- PC-first
- Custom engine -- Unity target
- Houdini -- Blender Geometry Nodes covers procedural needs
