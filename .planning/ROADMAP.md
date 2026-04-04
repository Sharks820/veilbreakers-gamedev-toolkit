# Roadmap: VeilBreakers GameDev Toolkit

**Created:** 2026-03-18
**Updated:** 2026-04-04 (v10.0 roadmap created, Phase 39 planned)

## Milestones

- [x] **v1.0 Foundation & Full Pipeline** - Phases 1-8 (shipped 2026-03-19)
- [x] **v2.0 Complete Unity Game Development Coverage** - Phases 9-17 (shipped 2026-03-21)
- [x] **v3.0 AAA Mesh Quality + Professional Systems** - Phases 18-24 (shipped 2026-03-21)
- [ ] **v10.0 Total Quality: Zero Gaps Remaining** - Phases 39-48

## Phases

<details>
<summary>v1.0 Foundation & Full Pipeline (Phases 1-8) - SHIPPED 2026-03-19</summary>

- [x] **Phase 1: Foundation & Server Architecture** - MCP server skeleton, compound tool pattern, Blender socket bridge, async job queue, visual feedback
- [x] **Phase 2: Mesh, UV & Topology Pipeline** - Mesh analysis/editing/repair, UV unwrapping/packing, game-readiness validation
- [x] **Phase 3: Texturing & Asset Generation** - PBR textures, AI 3D generation, concept art, asset pipeline processing, export validation
- [x] **Phase 4: Rigging** - Creature rig templates, facial rigging, IK chains, spring bones, weight painting, ragdoll, shape keys
- [x] **Phase 5: Animation** - Procedural gaits, combat animations, contact sheet preview, root motion, AI motion, batch export
- [x] **Phase 6: Environment & World Building** - Terrain, caves, buildings, dungeons, vegetation, interiors, modular kits, props
- [x] **Phase 7: VFX, Audio, UI & Unity Scene** - Particle VFX, shaders, audio generation, UI screens, scene setup, Gemini visual review
- [x] **Phase 8: Gameplay AI & Performance** - Mob AI controllers, spawn systems, profiling, LOD, lightmaps, build pipeline

**Delivered:** 22 MCP tools, 86 Blender handlers, 153 capabilities, 2,740 tests, 55 bugs fixed.

</details>

<details>
<summary>v2.0 Complete Unity Game Development Coverage (Phases 9-17) - SHIPPED 2026-03-21</summary>

- [x] **Phase 9: Unity Editor Deep Control** - Prefabs, components, hierarchy, physics, project settings, packages, import configuration, asset operations
- [x] **Phase 10: C# Programming Framework** - General-purpose code generation, script modification, editor tooling, test framework, architecture patterns
- [x] **Phase 11: Data Architecture & Asset Pipeline** - ScriptableObjects, JSON config, localization, game data tools, Git LFS, normal map baking, sprite atlasing
- [x] **Phase 12: Core Game Systems** - Save/load, health/damage, character controller, Input System, settings menu, VeilBreakers combat systems
- [x] **Phase 13: Content & Progression Systems** - Inventory, dialogue, quests, loot tables, crafting, skill trees, combat balancing, equipment systems
- [x] **Phase 14: Camera, Cinematics & Scene Management** - Cinemachine, Timeline, cutscenes, scene loading, lighting, probes, terrain detail, world design, RPG world systems
- [x] **Phase 15: Game UX & Encounter Design** - Minimap, tutorials, damage numbers, interaction prompts, encounter scripting, AI director
- [x] **Phase 16: Quality Assurance & Testing** - Unity TCP bridge, test runner, automated play, profiling, memory leaks, static analysis, crash reporting, live inspection
- [x] **Phase 17: Build & Deploy Pipeline** - Multi-platform builds, Addressables, CI/CD, versioning, platform configs, shader stripping, store metadata

**Delivered:** 37 MCP tools (15 Blender + 22 Unity), 309 actions, 7,182 tests, 135 bugs fixed.

</details>

<details>
<summary>v3.0 AAA Mesh Quality + Professional Systems (Phases 18-24) - SHIPPED 2026-03-21</summary>

- [x] **Phase 18: Procedural Mesh Integration + Terrain Depth** - Wire 267 procedural meshes into worldbuilding/environment, add cliff/cave/waterfall/bridge/multi-biome terrain features, LOD variants
- [x] **Phase 19: Character Excellence** - Body proportion validation, hair card generation, face/hand/foot topology validation, character-aware LOD retopology, armor seam hiding, Unity cloth physics, SSS skin shader, parallax eye shader, micro-detail normals
- [x] **Phase 20: Advanced Animation + FromSoft Combat Feel** - Combat timing system (anticipation/active/recovery), animation events, blend trees, additive layers, root motion refinement, AI motion, cinematic sequences
- [x] **Phase 21: Audio Middleware Architecture** - Spatial audio propagation/occlusion, layered sound design, audio event chains, dynamic music, portal propagation, audio LOD, VO pipeline, procedural foley
- [x] **Phase 22: AAA Dark Fantasy UI/UX Polish** - Procedural ornate UI frames, 3D icon render pipeline, dark fantasy cursors, rich tooltips, radial menus, notification toasts, loading screens, UI material shaders
- [x] **Phase 23: VFX Mastery** - Flipbook textures, VFX Graph node composition, projectile VFX chains, AoE VFX, per-brand status effects, environmental VFX depth, directional hit VFX, boss phase transitions
- [x] **Phase 24: Production Pipeline** - Compile error auto-recovery, asset conflict detection, multi-tool pipeline orchestration, art style consistency validation, build verification smoke tests

**Delivered:** 37 MCP tools, 350 actions, 8,473+ tests, 56 requirements across 8 categories.
</details>

<details>
<summary>v7.0 AAA Procedural City Production (Phases 30-38) - SUPERSEDED by v10.0</summary>

Phases 30-38 were planned for v7.0 but superseded by the comprehensive v9.0 audit findings that revealed systemic issues requiring a deeper overhaul. v10.0 replaces this milestone with full gap closure.

</details>

### v10.0 Total Quality: Zero Gaps Remaining (Phases 39-48)

**Milestone Goal:** Close EVERY gap, bug, and finding from the 53-agent v9.0 audit. Transform every procedural generator from PLACEHOLDER/BASIC to AAA-grade visual quality. Wire all existing dead code, fix all broken generators, overhaul all mesh generation. Mandatory Opus verification scan after every phase until clean.

- [ ] **Phase 39: Pipeline & Systemic Fixes** - Fix dispatch bugs, Z=0 placements, deprecated API, Y-axis bugs, smart planner wiring, smootherstep utility, rectangular terrain
- [ ] **Phase 40: Material & Texture Wiring** - Wire 52-material library into all generators, fix Base Color gaps, HeightBlend, biome palettes, dark fantasy palette enforcement
- [ ] **Phase 41: Broken Generator Fixes** - Fix 5 crashed creature generators, vegetation_tree, leaf_cards, boss arena API break, town crash, orientation and proportion bugs
- [ ] **Phase 42: Dead Code Wiring** - Wire vegetation generators, modular building kit, settlement generator, AAA water, spline deformation, L-system trees, interiors, atmospheric volumes, coastline, MST roads
- [ ] **Phase 43: Geometry Quality Overhaul (Weapons, Armor, Creatures)** - Weapon silhouette redesign, armor anatomical fit, creature anatomy overhaul with musculature and proportions
- [ ] **Phase 44: Geometry Quality Overhaul (Props, Clothing, Environments)** - Prop detail geometry, clothing cloth-sim topology, interior furniture, dungeon/cave height, castle walls, terrain micro-detail, building detail
- [ ] **Phase 45: Data Safety & Integrity** - Tripo texture overwrite, checkpoint atomicity, compose_interior binding, multi-floor semantics, settlement scaling, scene hierarchy scoping
- [ ] **Phase 46: Export Pipeline Completion** - FBX export, texture bake, LOD generation, game_check validation, collision mesh, vegetation serialization, splatmap export, screenshot fix, group export fix
- [ ] **Phase 47: Unity Integration & Regression** - 16 missing bridge handlers, live Blender integration testing, v8.0 regression verification
- [ ] **Phase 48: Starter City Generation & Final Verification** - Full terrain generation, Hearthvale city, walkable interiors, environmental assets, Tripo integration, zai visual verification, full pipeline execution

## Phase Details

<details>
<summary>v1.0 Phase Details (Phases 1-8) - SHIPPED</summary>

### Phase 1: Foundation & Server Architecture
**Goal**: Claude can connect to Blender, dispatch validated commands, and receive visual proof of every mutation
**Depends on**: Nothing (first phase)
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06, ARCH-07, ARCH-08
**Success Criteria** (what must be TRUE):
  1. Claude can invoke a compound tool that dispatches multiple Blender operations in a single call
  2. A Blender operation triggered from Claude returns a viewport screenshot proving the mutation happened
  3. Sending a malformed command returns a structured error with recovery suggestion
  4. The contact sheet system renders a multi-angle composite image of any Blender scene object
  5. The Blender addon survives rapid sequential tool calls without deadlocks
**Plans**: 3 plans (complete)

### Phase 2: Mesh, UV & Topology Pipeline
**Goal**: Claude can analyze, repair, UV unwrap, and validate any 3D mesh for game readiness
**Depends on**: Phase 1
**Requirements**: MESH-01 through MESH-08 (v1.0 scope)
**Success Criteria** (what must be TRUE):
  1. Mesh repair removes doubles, fixes normals, fills holes on any imported model
  2. UV unwrapping produces non-overlapping islands with configurable margin
  3. Game readiness check catches poly count, UV, and normal issues before export
**Plans**: 3 plans (complete)

### Phase 3: Texturing & Asset Generation
**Goal**: Claude can create PBR textures, generate 3D models via AI, and process assets through a validated pipeline
**Depends on**: Phase 2
**Requirements**: TEX-01 through TEX-06
**Success Criteria** (what must be TRUE):
  1. PBR texture creation produces albedo, normal, roughness, metallic maps
  2. AI 3D generation (Tripo) returns a processed, UV-unwrapped model
  3. Asset pipeline processes import through export with validation at each step
**Plans**: 4 plans (complete)

### Phase 4: Rigging
**Goal**: Claude can rig any character or creature with production-quality deformation
**Depends on**: Phase 3
**Requirements**: RIG-01 through RIG-08
**Success Criteria** (what must be TRUE):
  1. Rigify-based rig templates work for humanoid and quadruped characters
  2. Auto weight painting produces clean deformation on standard body types
  3. Facial rigging, IK chains, and spring bones can be applied to any rigged character
**Plans**: 4 plans (complete)

### Phase 5: Animation
**Goal**: Claude can generate, preview, and export production-quality animations
**Depends on**: Phase 4
**Requirements**: ANIM-01 through ANIM-06
**Success Criteria** (what must be TRUE):
  1. Procedural walk/run/idle animations work on any rigged humanoid
  2. Combat animations include anticipation, active, and recovery phases
  3. Contact sheet preview shows multi-frame animation in a single image
**Plans**: 4 plans (complete)

### Phase 6: Environment & World Building
**Goal**: Claude can generate complete game environments with terrain, buildings, vegetation, and interiors
**Depends on**: Phase 5
**Requirements**: ENV-01 through ENV-10
**Success Criteria** (what must be TRUE):
  1. Terrain generation produces heightmap-based landscapes with multiple biomes
  2. Building generation creates multi-floor structures with interior layout
  3. Vegetation scatter populates terrain with appropriate density and variety
**Plans**: 4 plans (complete)

### Phase 7: VFX, Audio, UI & Unity Scene
**Goal**: Claude can set up complete Unity scenes with VFX, audio, and UI systems
**Depends on**: Phase 6
**Requirements**: VFX-01 through VFX-04, AUD-01 through AUD-03, UI-01 through UI-03, SCENE-01 through SCENE-03
**Success Criteria** (what must be TRUE):
  1. Particle VFX and shaders work in Unity URP
  2. Audio generation produces spatial sound with proper attenuation
  3. UI screens render correctly with UI Toolkit
**Plans**: 5 plans (complete)

### Phase 8: Gameplay AI & Performance
**Goal**: Claude can implement gameplay AI, spawn systems, and optimize scene performance
**Depends on**: Phase 7
**Requirements**: AI-01 through AI-04, PERF-01 through PERF-03
**Success Criteria** (what must be TRUE):
  1. Mob AI controllers navigate and engage in combat
  2. Spawn systems manage enemy populations with difficulty scaling
  3. Scene profiling identifies and reports performance bottlenecks
**Plans**: 3 plans (complete)

</details>

<details>
<summary>v2.0 Phase Details (Phases 9-17) - SHIPPED</summary>

### Phase 9: Unity Editor Deep Control
**Goal**: Claude has full control over Unity Editor operations
**Depends on**: Phase 8
**Requirements**: EDIT-01 through EDIT-08
**Plans**: 3 plans (complete)

### Phase 10: C# Programming Framework
**Goal**: Claude can generate, modify, and test any C# code in the Unity project
**Depends on**: Phase 9
**Requirements**: CODE-01 through CODE-06
**Plans**: 4 plans (complete)

### Phase 11: Data Architecture & Asset Pipeline
**Goal**: Claude can create and manage all game data assets
**Depends on**: Phase 10
**Requirements**: DATA-01 through DATA-06
**Plans**: 4 plans (complete)

### Phase 12: Core Game Systems
**Goal**: All fundamental game systems work end-to-end
**Depends on**: Phase 11
**Requirements**: SYS-01 through SYS-06
**Plans**: 3 plans (complete)

### Phase 13: Content & Progression Systems
**Goal**: All content and progression systems are functional
**Depends on**: Phase 12
**Requirements**: CONT-01 through CONT-08
**Plans**: 3 plans (complete)

### Phase 14: Camera, Cinematics & Scene Management
**Goal**: Camera, cinematics, and scene management work at AAA level
**Depends on**: Phase 13
**Requirements**: CAM-01 through CAM-08
**Plans**: 5 plans (complete)

### Phase 15: Game UX & Encounter Design
**Goal**: Game UX and encounter design systems are complete
**Depends on**: Phase 14
**Requirements**: UX-01 through UX-06
**Plans**: 4 plans (complete)

### Phase 16: Quality Assurance & Testing
**Goal**: QA and testing infrastructure catches issues automatically
**Depends on**: Phase 15
**Requirements**: QA-01 through QA-08
**Plans**: 4 plans (complete)

### Phase 17: Build & Deploy Pipeline
**Goal**: Build and deploy pipeline handles multi-platform releases
**Depends on**: Phase 16
**Requirements**: BUILD-01 through BUILD-06
**Plans**: 3 plans (complete)

</details>

<details>
<summary>v3.0 Phase Details (Phases 18-24) - SHIPPED</summary>

### Phase 18: Procedural Mesh Integration + Terrain Depth
**Goal**: All 267 procedural meshes wired into worldbuilding with terrain features
**Depends on**: Phase 17
**Requirements**: MESH3-01 through MESH3-10
**Plans**: 3 plans (complete)

### Phase 19: Character Excellence
**Goal**: Characters meet AAA quality standards
**Depends on**: Phase 18
**Requirements**: CHAR-01 through CHAR-06
**Plans**: 3 plans (complete)

### Phase 20: Advanced Animation + FromSoft Combat Feel
**Goal**: Animation system delivers FromSoft-quality combat timing
**Depends on**: Phase 19
**Requirements**: ANIM3-01 through ANIM3-07
**Plans**: 3 plans (complete)

### Phase 21: Audio Middleware Architecture
**Goal**: Audio systems match Wwise-level spatial quality
**Depends on**: Phase 20
**Requirements**: AUDM-01 through AUDM-08
**Plans**: 1 plan (complete)

### Phase 22: AAA Dark Fantasy UI/UX Polish
**Goal**: UI matches dark fantasy AAA standards
**Depends on**: Phase 21
**Requirements**: UIPOL-01 through UIPOL-08
**Plans**: 1 plan (complete)

### Phase 23: VFX Mastery
**Goal**: VFX match Diablo 4 quality standards
**Depends on**: Phase 22
**Requirements**: VFX3-01 through VFX3-08
**Plans**: 1 plan (complete)

### Phase 24: Production Pipeline
**Goal**: Production pipeline automates quality enforcement
**Depends on**: Phase 23
**Requirements**: PROD-01 through PROD-05
**Plans**: 1 plan (complete)

</details>

### Phase 39: Pipeline & Systemic Fixes
**Goal**: Every systemic pipeline bug is eliminated so all downstream phases build on a clean foundation
**Depends on**: Nothing (first phase of v10.0)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, PIPE-08, TEST-01, TEST-04
**Success Criteria** (what must be TRUE):
  1. compose_map dispatches correctly to settlement generator for castles, hearthvale routes to full pipeline, and param shapes match all handlers
  2. No object in the entire codebase is placed at hardcoded Z=0 -- safe_place_object() samples terrain height for every placement call
  3. All Blender 5.0 deprecated API calls (group.inputs.new, Musgrave, cap_fill) are replaced with current equivalents and run without warnings
  4. Grepping the entire Blender codebase for Y-axis vertical usage returns zero false positives -- all vertical operations use Z
  5. Rectangular terrain (non-square) generates correctly for heightmap export, road placement, scatter distribution, chunking, sculpt layers, and erosion
  6. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: 5 plans
Plans:
- [ ] 39-01-PLAN.md — Utilities foundation (smoothstep, safe_place_object), dispatch fixes, deprecated API replacement
- [ ] 39-02-PLAN.md — Z=0 hardcoded placement bulk replacement (42+ sites) and Y-axis vertical bug fixes
- [ ] 39-03-PLAN.md — Smoothstep bulk replacement across 5 animation handler files (35 sites)
- [ ] 39-04-PLAN.md — Smart planner wiring: merge compose_world_map into compose_map (ONE pipeline)
- [ ] 39-05-PLAN.md — Rectangular terrain fixes (chunking, scatter, export, roads, sculpt) + full test validation

### Phase 40: Material & Texture Wiring
**Goal**: Every procedural generator produces fully-textured assets with dark fantasy PBR materials instead of blank white meshes
**Depends on**: Phase 39
**Requirements**: MAT-01, MAT-02, MAT-03, MAT-04, MAT-05, MAT-06, MAT-07, MAT-08, MAT-09, MAT-10, TEST-04
**Success Criteria** (what must be TRUE):
  1. Every generator that creates a Blender object also applies appropriate PBR materials from the 52-material library or 6 procedural generators -- zero white/untextured assets
  2. Terrain renders with HeightBlend node group producing smooth rock-through-grass transitions, driven by the 14 BIOME_PALETTES_V2 entries
  3. All materials follow dark fantasy palette constraints (Saturation <40%, Value 10-50%) with visible weathering, moss on north-facing surfaces, and rust patina on metal
  4. Castle surfaces show correct roughness textures (not all-black), wet rock material renders on appropriate surfaces, and curvature-driven wear is visible on all hard-surface assets
  5. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

### Phase 41: Broken Generator Fixes
**Goal**: Every generator that currently crashes or produces no output runs successfully and creates valid Blender objects
**Depends on**: Phase 40
**Requirements**: GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, GEN-06, GEN-07, TEST-04
**Success Criteria** (what must be TRUE):
  1. All 5 creature part generators (mouth, eyelid, paw, wing, serpent) produce valid mesh objects without tuple errors
  2. vegetation_tree creates a visible Blender object (not raw vertex data), and vegetation_leaf_cards generates non-zero vertices forming card geometry
  3. Boss arena generates without API errors, town generator runs at building_count=3+ without crashing Blender
  4. Wolf generates right-side-up, door generates vertical, shield generates upright and at correct scale (~1m), axe has 3D blade thickness, mace head is correctly sized, merlons are historical dimensions
  5. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

### Phase 42: Dead Code Wiring
**Goal**: All existing but disconnected systems are wired into the live pipeline so that generation uses real assets instead of placeholder cubes
**Depends on**: Phase 41
**Requirements**: WIRE-01, WIRE-02, WIRE-03, WIRE-04, WIRE-05, WIRE-06, WIRE-07, WIRE-08, WIRE-09, WIRE-10, WIRE-11, TEST-04
**Success Criteria** (what must be TRUE):
  1. Vegetation scatter calls VEGETATION_GENERATOR_MAP and produces L-system trees (4 species), shrubs, grass, mushrooms, and rocks instead of placeholder cubes
  2. Castle generation routes through settlement_generator using the 260-piece modular building kit, producing varied wall/tower/gate pieces instead of box primitives
  3. Water in compose_map renders as spline-following mesh with flow vertex colors and proper shoreline, not a flat blue quad
  4. Interior binding (14 room types) is imported, loadable, and automatically furnishes generated buildings during settlement creation
  5. Atmospheric volumes, light integration, coastline generator, and MST road network all execute as part of compose_map pipeline
  6. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

### Phase 43: Geometry Quality Overhaul -- Weapons, Armor, Creatures
**Goal**: Weapons, armor, and creatures have AAA-grade mesh quality with proper silhouettes, anatomical detail, and visual complexity
**Depends on**: Phase 42
**Requirements**: GEOM-01, GEOM-02, GEOM-03, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Weapons have 3-10x more vertices than current, with distinct blade profiles, cross-guard geometry, wrapped grip detail, and pommel shape -- zai visual verification scores DECENT or higher on all 6 weapon types
  2. Armor shows anatomical contouring, layered plate overlap, articulated gauntlet fingers, and material zone separation -- zai visual verification scores DECENT or higher
  3. Creatures display visible musculature topology, skeletal deformation zones at joints, proper proportions (no stick legs or smooth tubes), and species-appropriate features -- zai visual verification scores DECENT or higher
  4. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

### Phase 44: Geometry Quality Overhaul -- Props, Environments, Buildings
**Goal**: Props, clothing, interiors, dungeons, caves, castles, terrain, and buildings have AAA-grade mesh detail replacing all primitive geometry
**Depends on**: Phase 43
**Requirements**: GEOM-04, GEOM-05, GEOM-06, GEOM-07, GEOM-08, GEOM-09, GEOM-10, GEOM-11, GEOM-12, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Props show iron banding on chests, working hinges on doors, rope braid on bridges, carved lettering on signs, and chain links at 80 tris/link -- zai visual verification scores DECENT or higher on all 10 prop types
  2. Dungeon ceilings reach 6-8m+ with stalactites and environmental rock detail; cave ceilings vary 3-20m; castle walls are 2-3m thick with gatehouse arches and historically-sized merlons
  3. Terrain displays 5-15cm/m micro-undulation, smootherstep on all feature transitions, scree/talus at every cliff base, and terrain skirt geometry at edges
  4. Buildings show rubble stone wall detail, timber framing, roof tile variation, shutters, and hanging signs -- zai visual verification scores DECENT or higher
  5. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD
**UI hint**: yes

### Phase 45: Data Safety & Integrity
**Goal**: No pipeline operation can corrupt, overwrite, or silently discard user data or generated assets
**Depends on**: Phase 39 (can run in parallel with Phase 43-44 but logically after pipeline fixes)
**Requirements**: SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-06, TEST-04
**Success Criteria** (what must be TRUE):
  1. Tripo pipeline cleanup preserves embedded textures -- running cleanup after a Tripo import does NOT overwrite texture files with blanks
  2. compose_interior uses atomic writes (temp file + rename) and guards interior_results against mid-pipeline wipe, so a crash at any point leaves the last good checkpoint intact
  3. Multi-floor interiors stack vertically at correct Z heights (not flattened to Z=0), and settlement scaling matches plan counts (village=4-8, city=20-40)
  4. scene_hierarchy.json is scoped to the current map and excludes helper objects, cameras, and unrelated scene items
  5. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

### Phase 46: Export Pipeline Completion
**Goal**: Any generated scene can be exported to Unity-ready format with textures baked, LODs generated, collisions defined, and validation passing
**Depends on**: Phase 44
**Requirements**: EXPORT-01, EXPORT-02, EXPORT-03, EXPORT-04, EXPORT-05, EXPORT-06, EXPORT-07, EXPORT-08, EXPORT-09, TEST-04
**Success Criteria** (what must be TRUE):
  1. compose_map produces FBX files for all non-terrain objects, with baked diffuse/normal/AO/curvature textures per asset
  2. LOD generation produces 3 levels (LOD0/LOD1/LOD2) with silhouette-preserving decimation, and collision meshes use UCX_ prefix naming convention
  3. Vegetation instances serialize to Unity TreeInstance format, and splatmap exports as an image file compatible with Unity Terrain alphamap
  4. game_check validation runs automatically before any export and blocks export if critical issues found; aaa_verify uses fresh screenshots (no stale PNG reuse)
  5. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

### Phase 47: Unity Integration & Regression
**Goal**: All 37 MCP tools work correctly with live Unity and Blender instances, and v8.0 fixes remain intact
**Depends on**: Phase 46
**Requirements**: BRIDGE-01, BRIDGE-02, BRIDGE-03, TEST-02, TEST-04
**Success Criteria** (what must be TRUE):
  1. 16 new Unity bridge handlers for real-time GameObject/component/scene operations are implemented and responding to TCP commands
  2. All 37 MCP tools (15 Blender + 22 Unity) pass live integration testing against running application instances
  3. v8.0 verified fixes (camera, checkpoints, pipeline, materials, architecture, interiors, animation, export) still function correctly -- no regressions
  4. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

### Phase 48: Starter City Generation & Final Verification
**Goal**: A complete, visually-verified starter city demonstrates every system working together at AAA quality
**Depends on**: Phase 47 (needs ALL other phases complete)
**Requirements**: CITY-01, CITY-02, CITY-03, CITY-04, CITY-05, CITY-06, CITY-07, TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Full terrain generates with cliffs, waterfalls, rivers, and multi-biome landscape -- visible HeightBlend transitions between biomes, micro-undulation across surface
  2. Hearthvale city renders with castle (modular kit pieces), walls, varied buildings, MST road network, and vegetation integrated into terrain with foundation sampling
  3. Key buildings (tavern, blacksmith, chapel, keep) have walkable interiors with real furniture meshes, atmospheric props, and applied materials
  4. zai visual verification scores every area (terrain, city exterior, interiors, vegetation, water) at DECENT or higher -- any area scoring below triggers fix+regenerate cycle
  5. All 19,850+ existing tests pass plus new tests for all fixed generators and wired systems
  6. Opus verification scan returns CLEAN (0 bugs/gaps found)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 39 → 40 → 41 → 42 → 43 → 44 → 45 → 46 → 47 → 48
(Phase 45 can optionally run in parallel with 43-44 if resources allow)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 39. Pipeline & Systemic Fixes | 0/5 | Planned | - |
| 40. Material & Texture Wiring | 0/TBD | Not started | - |
| 41. Broken Generator Fixes | 0/TBD | Not started | - |
| 42. Dead Code Wiring | 0/TBD | Not started | - |
| 43. Geometry Overhaul (Weapons/Armor/Creatures) | 0/TBD | Not started | - |
| 44. Geometry Overhaul (Props/Environments/Buildings) | 0/TBD | Not started | - |
| 45. Data Safety & Integrity | 0/TBD | Not started | - |
| 46. Export Pipeline Completion | 0/TBD | Not started | - |
| 47. Unity Integration & Regression | 0/TBD | Not started | - |
| 48. Starter City Generation & Final Verification | 0/TBD | Not started | - |
