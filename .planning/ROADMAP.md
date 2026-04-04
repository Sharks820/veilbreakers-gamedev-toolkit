# Roadmap: VeilBreakers GameDev Toolkit

**Updated:** 2026-04-04 (v10.0 Phase 46 planned)
**Updated:** 2026-03-31 (v7.0 planning in progress)

## Milestones

- [x] **v1.0 Foundation & Full Pipeline** - Phases 1-8 (shipped 2026-03-19)
- [x] **v2.0 Complete Unity Game Development Coverage** - Phases 9-17 (shipped 2026-03-21)
- [x] **v3.0 AAA Mesh Quality + Professional Systems** - Phases 18-24 (shipped 2026-03-21)
- [ ] **v10.0 Total Quality: Zero Gaps Remaining** - Phases 39-48 (in progress)
- [ ] **v7.0 AAA Procedural City Production** - Phases 30-38 (planning in progress)

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

- [x] **Phase 18: Procedural Mesh Integration + Terrain Depth** - Wire 267 procedural meshes into worldbuilding/environment, add cliff/cave/waterfall/bridge/multi-biome terrain features, LOD variants (3/3 plans complete)
- [x] **Phase 19: Character Excellence** - Body proportion validation, hair card generation, face/hand/foot topology validation, character-aware LOD retopology, armor seam hiding, Unity cloth physics, SSS skin shader, parallax eye shader, micro-detail normals (3/3 plans complete)
- [x] **Phase 20: Advanced Animation + FromSoft Combat Feel** - Combat timing system (anticipation/active/recovery), animation events, blend trees, additive layers, root motion refinement, AI motion, cinematic sequences (3/3 plans complete)
- [x] **Phase 21: Audio Middleware Architecture** - Spatial audio propagation/occlusion, layered sound design, audio event chains, dynamic music (re-sequencing/stingers), portal propagation, audio LOD, VO pipeline, procedural foley (1/1 plan complete, 8 AUDM requirements, 157 tests)
- [x] **Phase 22: AAA Dark Fantasy UI/UX Polish** - Procedural ornate UI frames, 3D icon render pipeline, dark fantasy cursors, rich tooltips, radial menus, notification toasts, loading screens, UI material shaders (1/1 plan complete, 8 UIPOL requirements, 204 tests)
- [x] **Phase 23: VFX Mastery** - Flipbook textures, VFX Graph node composition, projectile VFX chains, AoE VFX, per-brand status effects, environmental VFX depth, directional hit VFX, boss phase transitions (1/1 plan complete, 8 VFX3 requirements, 177 tests)
- [x] **Phase 24: Production Pipeline** - Compile error auto-recovery, asset conflict detection, multi-tool pipeline orchestration, art style consistency validation, build verification smoke tests

**Delivered:** 37 MCP tools (15 Blender + 22 Unity), 350 actions (41 new), 8,473+ tests (1,154 new), 56 requirements across 8 categories. FromSoft combat timing, Wwise-level spatial audio, Diablo 4 VFX, AAA dark fantasy UI, production pipeline automation.
</details>

## Phase Details

<details>
<summary>v1.0 Phase Details (Phases 1-8) - SHIPPED</summary>

### Phase 1: Foundation & Server Architecture
**Goal**: Claude can connect to Blender, dispatch validated commands, and receive visual proof of every mutation -- the entire MCP communication layer works end-to-end
**Depends on**: Nothing (first phase)
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06, ARCH-07, ARCH-08
**Success Criteria** (what must be TRUE):
  1. Claude can invoke a compound tool that dispatches multiple Blender operations in a single call and receives a single structured response with all results
  2. A Blender operation (e.g., create cube, move object) triggered from Claude returns a viewport screenshot proving the mutation happened
  3. Sending a malformed or dangerous command returns a structured error with recovery suggestion -- no raw Python exec ever reaches Blender
  4. The contact sheet system renders a multi-angle/multi-frame composite image of any Blender scene object and returns it to Claude
  5. The Blender addon survives rapid sequential tool calls without main-thread deadlocks or dropped commands
**Plans**: 3 plans
Plans:
- [x] 01-01-PLAN.md -- Foundation scaffold (uv project, TCP client, MCP server entry point)
- [x] 01-02-PLAN.md -- Compound tools and Blender addon handler framework
- [x] 01-03-PLAN.md -- Visual feedback system (screenshots, contact sheets)

### Phase 2: Mesh, UV & Topology Pipeline
**Goal**: Claude can analyze any mesh for game-readiness, perform surgical edits, auto-repair topology issues, and produce clean UV layouts -- all with visual verification
**Depends on**: Phase 1 (Blender bridge required)
**Requirements**: MESH-01, MESH-02, MESH-03, MESH-04, MESH-05, MESH-06, MESH-07, MESH-08, UV-01, UV-02, UV-03, UV-04, UV-05
**Success Criteria** (what must be TRUE):
  1. Claude can request a topology analysis of any mesh and receive an A-F grade with specific issue counts (n-gons, non-manifold edges, poles) and a visual overlay
  2. Claude can select geometry by material slot or vertex group and perform surgical edits (smooth, extrude, boolean) on just that selection, with before/after screenshots
  3. Auto-repair fixes common issues (doubles, normals, holes, loose geo) and the mesh passes game-readiness check afterward
  4. UV unwrapping produces islands with uniform texel density, no overlaps, and the UV layout is returned as a visual image for review
  5. A mesh that enters as raw AI output (e.g., from Tripo3D) exits as a game-ready asset passing all validation checks (poly budget, UVs, materials, naming)
**Plans**: 3 plans
Plans:
- [x] 02-01-PLAN.md -- Mesh analysis, auto-repair, and game-readiness check (blender_mesh tool)
- [x] 02-02-PLAN.md -- UV analysis, xatlas unwrapping, packing, lightmap, density equalization (blender_uv tool)
- [x] 02-03-PLAN.md -- Mesh editing, selection engine, booleans, retopology, sculpt operations

### Phase 3: Texturing & Asset Generation
**Goal**: Claude can generate 3D models from text, create PBR texture sets, perform surgical texture edits with seamless blending, and run the full pipeline from AI generation through Unity-ready export
**Depends on**: Phase 2 (needs meshes with UVs for texturing)
**Requirements**: TEX-01, TEX-02, TEX-03, TEX-04, TEX-05, TEX-06, TEX-07, TEX-08, TEX-09, TEX-10, PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, CONC-01, CONC-02, CONC-03
**Success Criteria** (what must be TRUE):
  1. Claude can describe a creature or prop in text and receive a 3D model (via Tripo3D) that passes mesh validation with PBR textures applied
  2. Claude can request a full PBR material set (albedo, normal, roughness, metallic, AO) from a text description and apply it to a UV-mapped mesh with visual verification
  3. Claude can mask a specific UV region of a textured model and apply targeted edits (recolor armor trim, inpaint a belt detail, blend seams) without affecting the rest
  4. The asset pipeline produces Unity-optimized FBX with LOD chains, and re-import validation confirms correct scale, orientation, bones, and materials
  5. Claude can generate concept art from text descriptions and extract color palettes for art direction consistency
**Plans**: 4 plans
Plans:
- [x] 03-01-PLAN.md -- PBR texturing, texture baking, and validation handlers (Blender-side)
- [x] 03-02-PLAN.md -- Surgical texture editing with seamless blending (MCP-side Pillow)
- [x] 03-03-PLAN.md -- Asset pipeline, AI 3D generation, LOD, catalog, export validation
- [x] 03-04-PLAN.md -- Concept art, compound MCP tool wiring, integration

### Phase 4: Rigging
**Goal**: Claude can rig any creature type for game animation -- from humanoid to amorphous -- with deformation-tested weights, facial controls, and secondary motion physics
**Depends on**: Phase 2 (clean meshes), Phase 3 (textured models for full visual validation)
**Requirements**: RIG-01, RIG-02, RIG-03, RIG-04, RIG-05, RIG-06, RIG-07, RIG-08, RIG-09, RIG-10, RIG-11, RIG-12, RIG-13
**Success Criteria** (what must be TRUE):
  1. Claude can analyze a mesh and receive a rig template recommendation, then apply the appropriate Rigify-based template (from 10 creature types) with automatic weight painting
  2. A rigged creature passes deformation testing at 8 standard poses -- the contact sheet shows clean deformation with no vertex bleeding, collapsed geometry, or weight artifacts
  3. Facial rig controls work for monster-specific expressions (snarl, hiss, roar) and shape keys drive visible expression/damage state changes in the viewport
  4. Spring/jiggle bones produce visible secondary motion on tails, hair, capes, and chains during a simple animation test
  5. Rig validation reports zero critical issues (unweighted verts, broken symmetry, invalid bone rolls) and ragdoll auto-setup generates correct colliders and joint limits
**Plans**: 4 plans
Plans:
- [x] 04-01-PLAN.md -- Core rig templates (10 creatures), mesh analysis, custom rig builder
- [x] 04-02-PLAN.md -- Weight painting, deformation testing, rig validation, weight fix
- [x] 04-03-PLAN.md -- Advanced features: facial rig, IK, spring bones, ragdoll, retarget, shape keys
- [x] 04-04-PLAN.md -- Handler registration and blender_rig compound MCP tool wiring

### Phase 5: Animation
**Goal**: Claude can generate, preview, and export game-ready animations for any rigged creature -- procedural gaits, combat moves, and AI-generated motion clips
**Depends on**: Phase 4 (needs rigged models)
**Requirements**: ANIM-01, ANIM-02, ANIM-03, ANIM-04, ANIM-05, ANIM-06, ANIM-07, ANIM-08, ANIM-09, ANIM-10, ANIM-11, ANIM-12
**Success Criteria** (what must be TRUE):
  1. Claude can generate a walk cycle for any creature type (biped, quadruped, hexapod, arachnid, serpent) and the animation contact sheet shows correct gait with proper foot placement
  2. Combat animations (attack, death, hit, spawn) are generated from text descriptions and play back correctly on rigged models with secondary motion (jiggle) visible
  3. Root motion is correctly extracted and animation events are placed at contact frames (footsteps, hit impacts) -- verified by data in the export
  4. AI-generated motion (HY-Motion/MotionGPT) can be retargeted onto custom rigs and Mixamo animations map correctly to creature bone structures
  5. Batch export produces separate Unity animation clips (.anim) with correct naming, and the contact sheet preview shows all clips in a review-friendly layout
**Plans**: 4 plans
Plans:
- [x] 05-01-PLAN.md -- Pure-logic keyframe engine, gait configs, attack/reaction generators
- [x] 05-02-PLAN.md -- Blender animation handlers: walk/fly/idle/attack/reaction/custom (ANIM-01 to ANIM-06)
- [x] 05-03-PLAN.md -- Export handlers: preview, secondary motion, root motion, retarget, AI stub, batch export (ANIM-07 to ANIM-12)
- [x] 05-04-PLAN.md -- Handler registration and blender_animation compound MCP tool wiring

### Phase 6: Environment & World Building
**Goal**: Claude can generate complete game environments -- terrain, buildings, dungeons, vegetation, interiors -- from text descriptions, all textured and export-ready
**Depends on**: Phase 1 (Blender bridge), Phase 3 (texturing pipeline for environment materials)
**Requirements**: ENV-01, ENV-02, ENV-03, ENV-04, ENV-05, ENV-06, ENV-07, ENV-08, ENV-09, ENV-10, ENV-11, ENV-12, ENV-13, ENV-14, ENV-15, ENV-16
**Success Criteria** (what must be TRUE):
  1. Claude can generate terrain with configurable features (mountains, canyons, cliffs) including erosion, and auto-paint textures based on slope/altitude/moisture biome rules
  2. Building generation produces AAA-quality structures (castle, tower, tavern, bridge) with interior detail (furniture, wall decorations, lighting) from text descriptions
  3. Dungeon/cave systems generate connected rooms with corridors, doors, spawn points, and loot placement -- the layout is navigable and architecturally coherent
  4. Vegetation scatter respects biome rules (tree types by altitude, grass density by slope) and props are context-aware (barrels near taverns, crates near docks)
  5. Modular architecture pieces snap together correctly (walls, floors, corners, doors, windows) and ruins generation convincingly damages existing structures
**Plans**: 4 plans
Plans:
- [x] 06-01-PLAN.md -- Terrain generation, erosion, biome painting, rivers/roads, water, heightmap export
- [x] 06-02-PLAN.md -- BSP dungeon, cellular automata caves, town layout generation
- [x] 06-03-PLAN.md -- Building grammar, castle/tower/bridge, ruins, interiors, modular kit
- [x] 06-04-PLAN.md -- Vegetation/prop scatter, handler registration, compound MCP tool wiring

### Phase 7: VFX, Audio, UI & Unity Scene
**Goal**: Claude can set up complete Unity scenes with VFX, audio, UI screens, lighting, NavMesh, and animation controllers -- with Gemini-powered visual quality review at every step
**Depends on**: Phase 1 (server architecture), Phase 5 (animated models for scene population), Phase 6 (environments for scene context)
**Requirements**: VFX-01, VFX-02, VFX-03, VFX-04, VFX-05, VFX-06, VFX-07, VFX-08, VFX-09, VFX-10, AUD-01, AUD-02, AUD-03, AUD-04, AUD-05, AUD-06, AUD-07, AUD-08, AUD-09, AUD-10, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, SCENE-01, SCENE-02, SCENE-03, SCENE-04, SCENE-05, SCENE-06, SCENE-07
**Success Criteria** (what must be TRUE):
  1. Claude can describe a VFX effect in text ("fire + sparks + smoke") and a VFX Graph particle system is generated in Unity, with per-brand variants (IRON sparks, VENOM drip, SURGE crackle) and corruption shader scaling
  2. AI-generated SFX, music loops, voice lines, and ambient soundscapes play correctly through the Unity Audio Mixer with proper group routing, pooling, and adaptive layers that respond to game state
  3. UI screens generated from text descriptions (UXML + USS) pass layout validation (no overlaps, zero-size, overflow) and WCAG contrast checks across 5 resolutions, with Gemini confirming visual quality
  4. Unity scenes import terrain heightmaps, scatter objects, configure lighting/fog/post-processing, bake NavMesh with agent settings, and set up Animator Controllers with blend trees
  5. Screenshot comparison detects visual regressions between scene versions, and Gemini visual review provides actionable quality assessments at every visual checkpoint
**Plans**: 5 plans
Plans:
- [x] 07-01-PLAN.md -- Unity MCP server foundation, auto-recompile/editor tools, Gemini review, Settings
- [x] 07-02-PLAN.md -- VFX system: particle templates, brand VFX, shaders, post-processing, screen effects
- [x] 07-03-PLAN.md -- Audio system: ElevenLabs AI generation, footstep/adaptive/mixer/pool C# templates
- [x] 07-04-PLAN.md -- UI system: UXML/USS generation, WCAG contrast, layout validation, screenshot diff
- [x] 07-05-PLAN.md -- Scene setup: terrain, scatter, lighting, NavMesh, animator, avatar, animation rigging

### Phase 8: Gameplay AI & Performance
**Goal**: Claude can generate complete mob AI systems and optimize game performance -- the final integration layer that makes environments feel alive and the game run smoothly
**Depends on**: Phase 7 (needs scenes, VFX, audio to integrate with gameplay)
**Requirements**: MOB-01, MOB-02, MOB-03, MOB-04, MOB-05, MOB-06, MOB-07, PERF-01, PERF-02, PERF-03, PERF-04, PERF-05
**Success Criteria** (what must be TRUE):
  1. Generated mob controllers exhibit correct state machine behavior (patrol with waypoints, aggro on detection, chase, attack, flee) with configurable parameters and leash distance
  2. Combat ability prefabs combine animation + VFX + hitbox + damage + sound into a single working unit, and projectile systems follow correct trajectories with trail VFX
  3. Spawn systems respect max count, respawn timers, area bounds, and conditions -- mobs appear in the world at designated spawn points
  4. Scene profiling reports frame time, draw calls, batches, triangle count, and memory usage -- with actionable recommendations for optimization
  5. Auto-generated LOD chains, lightmap baking, and asset audit (unused assets, oversized textures) produce measurable performance improvements verified by before/after profiling data
**Plans**: 3 plans
Plans:
- [x] 08-01-PLAN.md -- Gameplay templates: mob controller, aggro, patrol, spawn, behavior tree, combat ability, projectile (MOB-01 to MOB-07)
- [x] 08-02-PLAN.md -- Performance templates: scene profiler, LOD setup, lightmap baking, asset audit, build automation (PERF-01 to PERF-05)
- [x] 08-03-PLAN.md -- Compound tool wiring: unity_gameplay + unity_performance in unity_server.py

</details>

<details>
<summary>v2.0 Phase Details (Phases 9-17) - SHIPPED</summary>

### Phase 9: Unity Editor Deep Control
**Goal**: Claude has complete programmatic control over the Unity Editor -- prefabs, components, hierarchy, physics, project settings, packages, and asset import configuration
**Depends on**: Phase 8 (v1.0 Unity server foundation)
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-05, EDIT-06, EDIT-07, EDIT-08, EDIT-09, EDIT-10, EDIT-11, EDIT-12, EDIT-13, EDIT-14, EDIT-15, IMP-01, IMP-02, PHYS-01, PHYS-02, PIPE-09, EQUIP-02
**Success Criteria** (what must be TRUE):
  1. Claude can create a nested prefab variant, add components with configured properties, and the resulting .prefab asset opens correctly in Unity's Prefab Mode
  2. Claude can reparent GameObjects, set layers/tags, enable/disable objects, and the hierarchy changes persist after scene save
  3. Claude can modify Player Settings, Quality Settings, Physics settings, and Time/Graphics settings, and Unity reflects the changes without manual Editor interaction
  4. Claude can install a UPM package, configure import settings on an FBX (scale, compression, rig type) and a texture (max size, platform compression, sRGB), and the assets reimport correctly
  5. Claude can move/rename/delete assets while preserving .meta file GUID integrity, and material remapping on FBX import resolves to existing project materials
**Plans**: 3 plans

Plans:
- [x] 09-01-PLAN.md -- Prefab, component, hierarchy, physics joints, NavMesh, bone sockets (unity_prefab tool)
- [x] 09-02-PLAN.md -- Project settings, packages, tags/layers, physics config (unity_settings tool)
- [x] 09-03-PLAN.md -- Asset operations, FBX/texture import, material remap, presets, asmdef (unity_assets tool)

### Phase 10: C# Programming Framework
**Goal**: Claude can generate and modify arbitrary C# code for Unity -- MonoBehaviours, editor tools, tests, and reusable architecture patterns -- not limited to domain-specific templates
**Depends on**: Phase 9 (needs editor control for Assembly Definitions, test runner integration)
**Requirements**: CODE-01, CODE-02, CODE-03, CODE-04, CODE-05, CODE-06, CODE-07, CODE-08, CODE-09, CODE-10, SHDR-01, SHDR-02
**Success Criteria** (what must be TRUE):
  1. Claude can generate any C# class type (MonoBehaviour, plain class, interface, enum, struct, static utility) and the script compiles without errors after AssetDatabase.Refresh
  2. Claude can open an existing C# script, add methods/fields/properties/attributes, and the modified script compiles cleanly with no regressions
  3. Claude can generate custom Editor windows, PropertyDrawers, and Inspector drawers that render correctly in the Unity Editor
  4. Claude can create test assemblies and run EditMode/PlayMode tests through MCP, receiving structured pass/fail results with failure messages
  5. Claude can scaffold architecture patterns (service locator, event bus, object pool, state machine, observer/SO events) that compile and function as reusable frameworks
**Plans**: 4 plans

Plans:
- [x] 10-01-PLAN.md -- Core C# generation engine: class builder, script modifier, editor tools (CODE-01, CODE-02, CODE-03)
- [x] 10-02-PLAN.md -- Shader extensions: arbitrary HLSL/ShaderLab shaders, URP ScriptableRendererFeatures (SHDR-01, SHDR-02)
- [x] 10-03-PLAN.md -- Test framework + architecture patterns: test classes, test runner, service locator, object pool, singleton, state machine, SO events (CODE-04 through CODE-10)
- [x] 10-04-PLAN.md -- Compound tool wiring: unity_code + unity_shader tools, run_tests action in unity_server.py

### Phase 11: Data Architecture & Asset Pipeline
**Goal**: Claude can create data-driven game architecture using ScriptableObjects, JSON configs, and localization -- plus manage the asset pipeline with Git LFS, normal map baking, and sprite atlasing, with AAA quality enforcement for all assets
**Depends on**: Phase 10 (needs C# generation for SO definitions and data tools)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08, AAA-01, AAA-02, AAA-03, AAA-04, AAA-06
**Success Criteria** (what must be TRUE):
  1. Claude can create ScriptableObject C# definitions and instantiate .asset files with populated data fields, usable as item databases or stat tables
  2. Claude can generate, validate, and parse JSON/XML configuration files for game balance, difficulty curves, and progression data
  3. Claude can set up Unity Localization with string tables and locale assets, and localized text appears correctly when switching locales
  4. Claude can configure Git LFS rules and .gitignore for a Unity project, and normal map baking produces correct tangent-space maps from high/low poly pairs
  5. Claude can generate sprite sheets with atlas packing and sprite animation clips from individual frames
**Plans**: 4 plans

Plans:
- [x] 11-01-PLAN.md -- Data architecture: SO definitions, .asset instantiation, JSON validation, localization, data authoring tools (DATA-01, DATA-02, DATA-03, DATA-04)
- [x] 11-02-PLAN.md -- Asset pipeline: Git LFS config, normal map baking, sprite atlas, sprite editor, AssetPostprocessor (IMP-03, IMP-04, BUILD-06, TWO-03, PIPE-08)
- [x] 11-03-PLAN.md -- AAA quality: albedo de-lighting, poly budgets, palette validation, master materials, texture quality (AAA-01, AAA-02, AAA-03, AAA-04, AAA-06)
- [x] 11-04-PLAN.md -- Compound tool wiring: unity_data + unity_quality + unity_pipeline tools, blender_texture extensions, syntax tests

### Phase 12: Core Game Systems
**Goal**: Claude can generate the foundational game systems every Unity project needs -- save/load persistence, health/damage, character movement, input configuration, settings menus, and VeilBreakers combat systems (player combat, abilities, synergy, corruption, XP, currency, damage types)
**Depends on**: Phase 10 (C# generation), Phase 11 (ScriptableObjects for item/config data)
**Requirements**: GAME-01, GAME-05, GAME-06, GAME-07, GAME-08, MEDIA-02, VB-01, VB-02, VB-03, VB-04, VB-05, VB-06, VB-07, RPG-03
**Success Criteria** (what must be TRUE):
  1. Claude can generate a save/load system with JSON serialization, multiple save slots, and data migration support -- saved data round-trips correctly through serialize/deserialize
  2. Claude can generate a health/damage system with HP components, damage number display, death handling, and respawn logic that integrates with existing GameObjects
  3. Claude can generate first-person and third-person character controllers with configurable movement parameters and camera follow behavior
  4. Claude can create Input Action assets with action maps, control schemes, and rebinding support -- player input routes correctly through the Input System
  5. Claude can generate a game settings menu (graphics quality, audio volume, keybindings, accessibility) that persists preferences across sessions
**Plans**: 3 plans

Plans:
- [x] 12-01-PLAN.md -- Core game system templates: save/load, health/damage, character controller, input system, settings menu, HTTP client, interactable objects (GAME-01, GAME-05, GAME-06, GAME-07, GAME-08, MEDIA-02, RPG-03)
- [x] 12-02-PLAN.md -- VeilBreakers combat templates: player combat, ability system, synergy engine, corruption gameplay, XP/leveling, currency, damage types (VB-01, VB-02, VB-03, VB-04, VB-05, VB-06, VB-07)
- [x] 12-03-PLAN.md -- Compound tool wiring: unity_game tool + extended C# syntax tests (all 14 requirements)

### Phase 13: Content & Progression Systems
**Goal**: Claude can generate the higher-level game systems that drive player engagement -- inventory, dialogue, quests, loot, crafting, skill trees, combat balancing tools, equipment mesh generation, and equipment attachment
**Depends on**: Phase 12 (core game systems: save/load for persistence, health/damage for combat integration)
**Requirements**: GAME-02, GAME-03, GAME-04, GAME-09, GAME-10, GAME-11, GAME-12, EQUIP-01, EQUIP-03, EQUIP-04, EQUIP-05, EQUIP-06, VB-08, RPG-01, RPG-05
**Success Criteria** (what must be TRUE):
  1. Claude can generate an inventory system with SO-based item database, drag-and-drop UI slots, equipment system, and storage containers that persist through save/load
  2. Claude can generate a branching dialogue system with dialogue tree data, NPC interaction triggers, and dialogue UI -- compatible with YarnSpinner data format
  3. Claude can generate a quest system with objective tracking, quest giver NPCs, quest log UI, and completion rewards that modify inventory/progression state
  4. Claude can generate loot tables (weighted random with rarity tiers), a crafting/recipe system (ingredients, stations, unlocks), and a skill tree with node dependencies and point allocation
  5. Claude can generate combat balancing tools (DPS calculator, encounter simulator, stat curve editor) that output statistical reports for tuning game difficulty
**Plans**: 3 plans

Plans:
- [x] 13-01-PLAN.md -- Content system templates: inventory, dialogue, quest, loot, crafting, skill tree, balancing tools, shop, journal (GAME-02, GAME-03, GAME-04, GAME-09, GAME-10, GAME-11, GAME-12, VB-08, RPG-01, RPG-05)
- [x] 13-02-PLAN.md -- Blender equipment handlers: weapon generation, character splitting, armor fitting, preview icons (EQUIP-01, EQUIP-03, EQUIP-04, EQUIP-05)
- [x] 13-03-PLAN.md -- Equipment attachment templates + compound tool wiring: unity_content + blender equipment extensions + syntax tests (EQUIP-06, all 15 requirements)

### Phase 14: Camera, Cinematics & Scene Management
**Goal**: Claude can set up Cinemachine cameras, Timeline cutscenes, multi-scene workflows, complete scene lighting/environment configuration, generate explorable world locations, and create RPG world systems (weather, day/night, puzzles, traps, fast travel, NPC placement)
**Depends on**: Phase 9 (editor control for scene/settings manipulation), Phase 10 (C# for custom Timeline tracks)
**Requirements**: CAM-01, CAM-02, CAM-03, CAM-04, SCNE-01, SCNE-02, SCNE-03, SCNE-04, SCNE-05, SCNE-06, TWO-01, TWO-02, MEDIA-01, ANIMA-01, ANIMA-02, ANIMA-03, AAA-05, WORLD-01, WORLD-02, WORLD-03, WORLD-04, WORLD-05, WORLD-06, WORLD-07, WORLD-08, WORLD-09, WORLD-10, RPG-02, RPG-04, RPG-06, RPG-07, RPG-09, RPG-10, RPG-11, RPG-12, RPG-13
**Success Criteria** (what must be TRUE):
  1. Claude can create Cinemachine virtual cameras (FreeLook, follow, state-driven) with configurable blending, and camera shake/zoom/transition effects trigger correctly
  2. Claude can create Timeline assets with animation, audio, activation, and Cinemachine tracks, and Playable Director plays back complete cutscene sequences
  3. Claude can create new scenes, configure single/additive/async loading, and generate a scene transition system with loading screens and fade effects
  4. Claude can set up reflection probes, light probes, HDR skybox, environment reflections, and Global Illumination -- lighting looks correct in baked and mixed modes
  5. Claude can configure occlusion culling (static occluders/occludees, bake data) and paint terrain detail (grass, detail meshes) on Unity Terrain
**Plans**: 5 plans

Plans:
- [x] 14-01-PLAN.md -- Camera + Timeline + animation editing templates: Cinemachine 3.x, Timeline, cutscenes, AnimationClip, Animator, AvatarMask, VideoPlayer (CAM-01, CAM-02, CAM-03, CAM-04, ANIMA-01, ANIMA-02, ANIMA-03, MEDIA-01)
- [x] 14-02-PLAN.md -- Scene management + environment templates: scene creation/loading, transitions, probes, occlusion, skybox/GI, terrain detail, tilemap, 2D physics, time-of-day (SCNE-01, SCNE-02, SCNE-03, SCNE-04, SCNE-05, SCNE-06, TWO-01, TWO-02, WORLD-08)
- [x] 14-03-PLAN.md -- Blender world design extensions: locations, 16 room types, boss arenas, world graph, linked interiors, multi-floor dungeons, furniture scale, overrun variants, easter eggs, storytelling props (WORLD-01, WORLD-02, WORLD-03, WORLD-04, WORLD-05, WORLD-06, WORLD-07, WORLD-09, WORLD-10, AAA-05)
- [x] 14-04-PLAN.md -- RPG world system templates: fast travel, puzzles, traps, spatial loot, weather, day/night cycle, NPC placement, dungeon lighting, terrain-building blending (RPG-02, RPG-04, RPG-06, RPG-07, RPG-09, RPG-10, RPG-11, RPG-12, RPG-13)
- [x] 14-05-PLAN.md -- Compound tool wiring: unity_camera + unity_world tools, blender_worldbuilding extensions, handler registration, deep C# syntax tests (all 36 requirements)

### Phase 15: Game UX & Encounter Design
**Goal**: Claude can generate polished gameplay UX elements and scripted encounter systems with dynamic difficulty adjustment
**Depends on**: Phase 12 (game systems for health/damage integration), Phase 10 (C# framework for AI scripting)
**Requirements**: UIX-01, UIX-02, UIX-03, UIX-04, AID-01, AID-02, AID-03, SHDR-04, ACC-01, PIPE-10, EQUIP-07, EQUIP-08, VB-09, VB-10, RPG-08
**Success Criteria** (what must be TRUE):
  1. Claude can generate a minimap/compass system with world-space markers that track objectives, NPCs, and points of interest
  2. Claude can generate tutorial/onboarding sequences with tooltip overlays and context-sensitive interaction prompts ("Press E to interact") that respond to player proximity
  3. Claude can generate a floating damage number system with configurable fonts, colors per damage type, critical hit scaling, and pooled text objects
  4. Claude can generate an encounter scripting system with trigger zones, wave spawning, win/fail conditions, and AI director hooks
  5. Claude can generate a threat escalation / AI director system that adjusts difficulty dynamically, and encounter simulations produce statistical balance reports
**Plans**: 4 plans

Plans:
- [x] 15-01-PLAN.md -- Core UX templates: minimap (orthographic camera render texture), damage numbers (PrimeTween + pooling), interaction prompts (Input System rebind), PrimeTween sequences, TextMeshPro setup (UIX-01, UIX-03, UIX-04, SHDR-04, PIPE-10)
- [x] 15-02-PLAN.md -- Game screen & visual effect templates: tutorial system, accessibility (colorblind/subtitles/motor), character select, world map, rarity VFX, corruption VFX (UIX-02, ACC-01, VB-09, RPG-08, EQUIP-07, EQUIP-08)
- [x] 15-03-PLAN.md -- Encounter & boss AI templates: encounter scripting (waves/triggers), AI director (DDA), encounter simulator (Monte Carlo EditorWindow), boss AI (multi-phase FSM) (AID-01, AID-02, AID-03, VB-10)
- [x] 15-04-PLAN.md -- Compound tool wiring: unity_ux (12 actions) + unity_gameplay extensions (4 actions) + deep C# syntax tests (all 15 requirements)

### Phase 16: Quality Assurance & Testing
**Goal**: Claude can run tests, profile performance, detect memory leaks, analyze code quality, and inspect live game state -- closing the feedback loop on code correctness and runtime health. Includes Unity TCP bridge addon that enables direct Editor communication.
**Depends on**: Phase 10 (test framework setup), Phase 12 (game systems to test against)
**Requirements**: QA-00, QA-01, QA-02, QA-03, QA-04, QA-05, QA-06, QA-07, QA-08
**Success Criteria** (what must be TRUE):
  1. The VB Unity MCP server communicates directly with Unity Editor over TCP (port 9877), executing commands without mcp-unity dependency
  2. Claude can trigger EditMode and PlayMode test runs through MCP and receive structured results with pass/fail counts, failure messages, and stack traces
  3. Claude can script automated play sessions (navigate to point, interact with object, verify game state) and report whether integration scenarios pass
  4. Claude can capture GPU profiling data and memory snapshots, detecting growing allocations that indicate memory leaks
  5. Claude can run static code analysis to flag common Unity anti-patterns (Update allocations, string concat in hot paths, Camera.main usage)
  6. Claude can set up crash reporting (Sentry), analytics telemetry events, and inspect live Play Mode state (variable values on GameObjects, behavior tree status)
**Plans**: 4 plans

Plans:
- [x] 16-01-PLAN.md -- Unity TCP bridge foundation: Python UnityConnection client, UnityCommand/UnityResponse models, C# bridge addon template generators (QA-00)
- [x] 16-02-PLAN.md -- QA template generators batch 1: test runner, automated play sessions, profiler, memory leak detector, static code analyzer (QA-01, QA-02, QA-03, QA-04, QA-05)
- [x] 16-03-PLAN.md -- QA template generators batch 2: crash reporting (Sentry), analytics/telemetry, live game state inspector (QA-06, QA-07, QA-08)
- [x] 16-04-PLAN.md -- Compound tool wiring: unity_qa (9 actions) + deep C# syntax tests (all 9 requirements)

### Phase 17: Build & Deploy Pipeline
**Goal**: Claude can orchestrate complete build pipelines -- multi-platform builds, Addressable assets, CI/CD automation, versioning, platform-specific configuration, shader variant stripping, and store publishing metadata
**Depends on**: Phase 9 (Build Settings, Player Settings), Phase 16 (tests run as part of CI)
**Requirements**: BUILD-01, BUILD-02, BUILD-03, BUILD-04, BUILD-05, SHDR-03, ACC-02
**Success Criteria** (what must be TRUE):
  1. Claude can trigger builds for multiple platforms (Windows, Mac, Linux, Android, iOS, WebGL) with correct per-platform settings and receive build size reports
  2. Claude can configure Addressable Asset Groups with remote/local paths, content catalogs, and memory management profiles
  3. Claude can generate CI/CD pipeline configs (GitHub Actions, GitLab CI) that automate build, test, and deploy steps for Unity projects
  4. Claude can manage version numbers (semantic versioning), create release branches, and generate changelogs from commit history
  5. Claude can configure platform-specific settings (Android manifest, iOS plist, WebGL template) without manual Editor interaction
**Plans**: 3 plans

Plans:
- [x] 17-01-PLAN.md -- Build template generators batch 1: multi-platform build orchestrator, Addressable Asset Groups, platform configs (Android/iOS/WebGL), shader variant stripping (BUILD-01, BUILD-02, BUILD-05, SHDR-03)
- [x] 17-02-PLAN.md -- Build template generators batch 2: CI/CD pipelines (GitHub Actions, GitLab CI), version management, changelog, store publishing metadata (BUILD-03, BUILD-04, ACC-02)
- [x] 17-03-PLAN.md -- Compound tool wiring: unity_build (7 actions) + deep C# syntax tests (all 7 requirements)

</details>

<details>
<summary>v3.0 Phase Details (Phases 18-24) - SHIPPED 2026-03-21</summary>

### Phase 18: Procedural Mesh Integration + Terrain Depth
**Goal**: Every worldbuilding and environment handler uses real procedural meshes instead of primitive cubes/cones, and terrain generation supports vertical geometry (cliffs, caves, waterfalls, bridges) beyond 2.5D heightmaps
**Depends on**: Phase 6 (environment/worldbuilding handlers to extend), Phase 2 (mesh pipeline for LOD generation)
**Requirements**: MESH3-01, MESH3-02, MESH3-03, MESH3-04, MESH3-05, TERR-01, TERR-02, TERR-03, TERR-04, TERR-05
**Success Criteria** (what must be TRUE):
  1. A generated dungeon contains actual torch sconce meshes, altar meshes, prison door meshes, and trap meshes from the procedural library -- not cubes or cones standing in as placeholders
  2. A generated castle includes real gate, rampart, drawbridge, and fountain meshes, and environment scatter places real rocks, trees, and mushrooms instead of geometric primitives
  3. Claude can generate vertical cliff face geometry that extends beyond heightmap limitations, and cave entrance meshes transition seamlessly from terrain surface into underground space
  4. Claude can generate multi-biome terrain with smooth blend zones (forest-to-swamp, swamp-to-mountain), waterfall/cascade geometry with stepped water mesh, and bridges that span detected rivers or chasms
  5. Every procedural mesh generator produces LOD variants (high/medium/low poly) that respect platform performance budgets, verified by game-readiness checks on each LOD level
**Plans**: 3 plans (all complete)
**Status**: COMPLETE (2026-03-21) -- 71 tests, 10 requirements fulfilled
Plans:
- [x] 18-01-PLAN.md -- Mesh bridge: wire 127 procedural meshes into worldbuilding/environment handlers
- [x] 18-02-PLAN.md -- Terrain depth: cliff faces, cave entrances, multi-biome, waterfalls, bridges
- [x] 18-03-PLAN.md -- Integration: dungeon prop meshes, castle meshes, environment scatter, LOD variants

### Phase 19: Character Excellence
**Goal**: Claude can validate and generate character meshes at ZBrush-level quality -- correct body proportions, proper face topology for deformation, hair card systems, and seamless armor attachment
**Depends on**: Phase 4 (rigging pipeline for deformation testing), Phase 18 (LOD pipeline for character-aware retopology)
**Requirements**: CHAR-01, CHAR-02, CHAR-03, CHAR-04, CHAR-05, CHAR-06, CHAR-07, CHAR-08
**Status**: COMPLETE (3/3 plans, 142 tests, 8 requirements)
**Success Criteria** (what must be TRUE):
  1. Claude can validate a character mesh against game-world scale specs (hero=1.8m, boss=3-6m, NPC=1.7m) and receive a pass/fail report with specific proportion issues (head-to-body ratio, limb lengths, shoulder width)
  2. Claude can generate strip-based hair card meshes with proper UV layout for alpha textures, and the hair cards render correctly with transparency sorting in Blender's viewport
  3. Claude can validate face topology and receive a report identifying whether edge loops exist around eyes, mouth, and nose -- flagging missing loops that would cause deformation artifacts during facial animation
  4. Claude can perform character-aware LOD retopology that preserves face and hand detail while aggressively reducing body/extremity polygon count, and the LOD chain passes deformation testing at each level
  5. Claude can generate armor seam-hiding overlap rings at mesh split points (neck, wrist, ankle) that prevent visible skin gaps when armor pieces are swapped, and validate hand/foot topology for proper finger separation and edge flow
**Plans**: 3 plans (all complete)
**Status**: COMPLETE (2026-03-21) -- 142 tests, 8 requirements fulfilled
Plans:
- [x] 19-01-PLAN.md -- Character validation: body proportions, face topology, hand/foot topology, hair cards
- [x] 19-02-PLAN.md -- Character LOD + armor: character-aware retopology, armor seam overlap rings
- [x] 19-03-PLAN.md -- Unity character: cloth physics setup, SSS skin shader, parallax eye shader, micro-detail normals

### Phase 20: Advanced Animation + FromSoft Combat Feel -- COMPLETE
**Goal**: Claude can configure frame-precise combat animation timing, inject animation events, generate blend trees and additive layers, refine root motion, generate AI-driven motion clips, and create cinematic animation sequences
**Depends on**: Phase 5 (animation generation pipeline), Phase 19 (character meshes for animation testing)
**Requirements**: ANIM3-01, ANIM3-02, ANIM3-03, ANIM3-04, ANIM3-05, ANIM3-06, ANIM3-07 (all complete)
**Plans**: 3/3 complete (20-01 combat timing, 20-02 blend trees, 20-03 AI motion + cinematics)
**Tests**: 198 new (84 + 47 + 67)
**Duration**: 17 minutes

### Phase 21: Audio Middleware Architecture -- COMPLETE
**Goal**: Claude can set up Wwise/FMOD-level audio architecture in Unity without middleware cost -- spatial audio with propagation and occlusion, layered sound design, dynamic music systems, and performance-aware audio LOD
**Depends on**: Phase 7 (existing audio tools foundation), Phase 16 (Unity TCP bridge for audio testing)
**Requirements**: AUDM-01, AUDM-02, AUDM-03, AUDM-04, AUDM-05, AUDM-06, AUDM-07, AUDM-08
**Status**: COMPLETE (2026-03-21) -- 8 generators, 157 tests, 2 files
**Tests**: 157 new
**Duration**: 9 minutes

### Phase 22: AAA Dark Fantasy UI/UX Polish
**Goal**: Claude can generate hand-crafted dark fantasy UI elements that rival Baldur's Gate 3 and Elden Ring -- ornate procedural frames, 3D-rendered item icons, themed cursors, rich tooltips, radial menus, and polished notification systems
**Depends on**: Phase 7 (UI generation foundation), Phase 15 (existing UX templates to extend)
**Requirements**: UIPOL-01, UIPOL-02, UIPOL-03, UIPOL-04, UIPOL-05, UIPOL-06, UIPOL-07, UIPOL-08
**Success Criteria** (what must be TRUE):
  1. Claude can generate procedural UI frames with ornate dark fantasy borders (rune decorations, weathered edges, metal rivets) that tile correctly at any panel size and look hand-crafted
  2. Claude can generate equipment/item icons through a 3D render pipeline (render item mesh -> stylize -> add border/background) that produces consistent, inventory-ready icon images
  3. Claude can generate context-sensitive dark fantasy cursors (default pointer, interact hand, attack crosshair, loot grab) that switch automatically based on what the player is hovering over
  4. Claude can generate a tooltip system with rich content display (item stats with color-coded values, lore text, equipment comparison showing stat deltas) that positions correctly near the cursor without clipping screen edges
  5. Claude can generate a radial menu (ability wheel / quick-select for items and spells), a notification/toast system (quest updates, item pickups, level-up, achievements with auto-dismiss), and a loading screen system (tips, lore text, concept art display with progress bar)
**Plans**: 1 plan (all 8 UIPOL requirements)
**Status**: COMPLETE (2026-03-21, 14min, 204 tests, 8 generators, 2 files created)
**Duration**: 14 minutes

### Phase 23: VFX Mastery
**Goal**: Claude can create Diablo 4 / Path of Exile quality visual effects -- flipbook animations, programmatic VFX Graph composition, full projectile-to-impact VFX chains, per-brand status effects, and environmental atmospheric depth
**Depends on**: Phase 7 (VFX Graph foundation), Phase 10 (C# code generation for VFX scripting)
**Requirements**: VFX3-01, VFX3-02, VFX3-03, VFX3-04, VFX3-05, VFX3-06, VFX3-07, VFX3-08
**Success Criteria** (what must be TRUE):
  1. Claude can generate flipbook texture sheets (animated sprite sequences for fire, smoke, energy effects) and compose VFX Graph nodes programmatically (actual node graph construction, not just parameter tweaking)
  2. Claude can generate complete projectile VFX chains (spawn burst -> travel trail -> impact explosion -> aftermath residue) where each stage triggers the next automatically
  3. Claude can generate area-of-effect VFX (ground circles, expanding domes, cone blasts with brand-appropriate colors) and per-brand status effect VFX for all 10 combat brands (burning, poisoned, frozen, stunned, blessed, cursed, etc.)
  4. Claude can generate environmental VFX with atmospheric depth (volumetric fog, god rays, heat distortion, water caustics) that integrate with the existing scene lighting setup
  5. Claude can generate directional combat hit VFX (blood splatter, sparks, energy bursts matched to damage brand and hit direction) and boss phase transition VFX (corruption wave, power surge, arena transformation) with full particle/shader coordination
**Plans**: 1 plan (complete)
**Status**: COMPLETE (2026-03-21) -- 177 tests, 8 requirements fulfilled
Plans:
- [x] 23-01-PLAN.md -- VFX mastery: flipbook textures, VFX Graph composition, projectile chains, AoE, status effects, environmental VFX, hit VFX, boss transitions

### Phase 24: Production Pipeline
**Goal**: Claude can detect and recover from compilation errors autonomously, prevent asset conflicts before they happen, orchestrate multi-tool pipelines as single commands, validate art style consistency across asset batches, and run build verification smoke tests
**Depends on**: Phase 16 (QA/testing infrastructure), Phase 17 (build pipeline for smoke tests)
**Requirements**: PROD-01, PROD-02, PROD-03, PROD-04, PROD-05
**Success Criteria** (what must be TRUE):
  1. Claude can detect Unity compilation errors, diagnose the root cause, apply a fix, and trigger recompilation -- completing the detect-diagnose-fix-recompile cycle without human intervention
  2. Claude can check for asset and class name conflicts before writing new files, preventing duplicate type compilation errors that would otherwise require manual cleanup
  3. Claude can execute multi-tool pipelines as single orchestrated commands (e.g., "create character" triggers mesh generation -> cleanup -> UV -> texture -> rig -> animate -> export in sequence)
  4. Claude can validate art style consistency across a batch of assets by checking color palette adherence, roughness value distributions, and detail density against project standards -- flagging outliers
  5. Claude can run build verification smoke tests after every build, confirming the build launches, loads a scene, and passes basic sanity checks before the build is considered good
**Plans**: 1 plan (complete)
**Status**: COMPLETE (2026-03-21) -- 205 tests, 5 requirements fulfilled
Plans:
- [x] 24-01-PLAN.md -- Production pipeline: compile recovery, conflict detection, pipeline orchestration, art style validation, build smoke tests

</details>

<details>
<summary>v4.0 AAA Procedural 3D Architecture (Phases 25-29) - ARCHIVED (superseded by v7.0)</summary>

- [ ] **Phase 25: Procedural Mesh Foundation** - 20+ parametric mesh generators, material presets, LOD presets, boolean cleanup pipeline, silhouette validation
- [ ] **Phase 26: Terrain and Environment** - Height-blended splatmap terrain, cliff face mesh overlays, biome noise system, vegetation scatter with LOD, terrain-conforming foundations
- [ ] **Phase 27: Building and Architecture** - Dark fantasy modular kit expansion (300+ pieces), trim sheet authoring, building composition with district parameters, interior room shells, storytelling prop placement, corruption-aware variants
- [ ] **Phase 28: Pipeline Integration and Starter Town** - Multi-backend AI integration, style normalization, starter town generation (10-15 buildings), Addressables streaming setup, state persistence
- [ ] **Phase 29: Research and Polish** - AAA technique documentation, performance optimization, visual quality review against benchmarks

**Status:** ARCHIVED -- v4.0 scope was restructured into v7.0 (Phases 30-38) with expanded scope and detailed requirements.
</details>

### v7.0 AAA Procedural City Production (Phases 30-38)

### Phase 30: Mesh Foundation
**Goal**: Every procedural mesh generator produces game-ready geometry with proper topology, seed-based determinism, material assignment, LOD presets, and visual quality verified by contact sheet -- establishing the quality floor for all subsequent phases
**Depends on**: Phase 24 (production pipeline for quality enforcement)
**Requirements**: MESH-01, MESH-02, MESH-06, MESH-11, MESH-14, MESH-15
**Success Criteria** (what must be TRUE):
  1. Every furniture generator (table, chair, chest, barrel, shelf, bed, bookshelf, crate) produces mesh with >500 vertices, proper edge flow at joints, and contact sheet shows silhouette distinguishable from primitive shapes at 4 viewing angles
  2. All 267 generators use `random.Random(seed)` exclusively -- zero instances of global random state -- and identical seeds produce byte-identical MeshSpec output across runs
  3. Smart material auto-assignment maps each generator category to the appropriate procedural material preset (wood for furniture, stone for architecture, metal for weapons) with roughness driven by noise texture nodes, never a single float value
  4. LOD chain generation produces 3-4 levels per asset type using existing `lod_pipeline.py` presets, with silhouette preservation >85% measured by `compute_silhouette_importance()`, and scene budget validator enforces per-room (50K-150K tris) and per-block (200K-500K tris) budgets
  5. Post-boolean cleanup pipeline (remove doubles at 0.0001, recalculate normals, fix non-manifold, fill holes up to 8 sides) runs automatically after every boolean operation, and no exported mesh contains non-manifold edges
**Plans**: TBD (to be created during plan-phase)

### Phase 31: Terrain & Environment
**Goal**: Terrain generation produces dramatic, eroded landscapes with multi-biome blending, cliff mesh overlays beyond heightmap limitations, and vegetation scattered by Poisson disk sampling -- visually comparable to Skyrim's overworld
**Depends on**: Phase 30 (mesh foundation for vegetation/rock generators)
**Requirements**: MESH-05, MESH-09, MESH-10
**Success Criteria** (what must be TRUE):
  1. Hydraulic erosion runs 50,000+ droplets (up from current 1,000) producing visible river channels, sediment deposits, and cliff faces in the terrain contact sheet -- terrain passes A/B comparison against Skyrim terrain reference
  2. Height-blended splatmap painting assigns terrain layers by slope (>45 degrees = cliff rock), altitude (>80% = snow), moisture (near water = mud/grass), with smooth 5-10m blend zones between biome transitions
  3. Cliff mesh overlays generate vertical geometry that extends beyond heightmap limitations, with proper UV mapping for tileable rock textures and seamless blending at terrain contact edges
  4. Vegetation scatter uses Poisson disk sampling (Bridson's algorithm) with density modulated by biome type, slope angle, and moisture map -- no uniform random distribution, minimum 3 tree species with L-system branching (not sphere-cluster canopies)
  5. Domain warping applied to base noise produces organic, non-repetitive terrain features -- no visible tiling patterns at any viewing distance in the contact sheet
**Plans**: TBD

### Phase 32: Building System
**Goal**: Building generation uses CGA-style split grammar for facade composition, producing architecturally varied structures with proper roofs, window/door cutouts, and modular kit pieces that snap on a consistent grid -- no building is a box with texture
**Depends on**: Phase 30 (mesh quality), Phase 31 (terrain for placement context)
**Requirements**: MESH-04, MESH-07
**Success Criteria** (what must be TRUE):
  1. Building grammar evaluates recursive split rules: footprint -> extrude -> comp(faces) -> split(y, floors) -> split(x, bays) -> fill(window|door|wall), producing facades with aligned windows across floors and stylistically consistent detail
  2. `building_quality.py` generators (stone block grid, arch curves, voussoir blocks, shingle rows) are wired INTO the building grammar pipeline -- wall faces use stone block geometry, openings have arch geometry, roofs have shingle geometry
  3. Roof generation uses straight skeleton algorithm (bpypolyskel) producing correct hip, gable, and mansard roofs from arbitrary building footprints -- no flat-box roof approximations
  4. Modular building kit has 50+ pieces per style (medieval, gothic, fortress, organic) on a 2m snap grid, with trim sheet UV mapping for efficient texture sharing across pieces
  5. Contact sheet comparison of 5 generated buildings shows no two buildings with identical facade layouts -- architectural variation achieved through randomized bay rules, floor counts, and style parameters
**Plans**: 1 plan (COMPLETE)
- Plan 01: Grammar upgrade, quality wiring, roof, variation, kit expansion (6 tasks, 438 tests)

### Phase 33: Interior System
**Goal**: Interior generation produces purpose-driven room layouts with spatially-aware furniture placement, decorative clutter, practical lighting, and occlusion zones -- interiors feel lived-in, not empty boxes
**Depends on**: Phase 30 (furniture generators), Phase 32 (building shells for interior context)
**Requirements**: MESH-03
**Success Criteria** (what must be TRUE):
  1. Room purpose templates define spatial relationship graphs: tavern (bar counter + stools facing it, tables + 2-4 chairs around each, fireplace with seating arc), bedroom (bed + nightstand adjacent, wardrobe against wall, desk facing window), kitchen (stove + counter + storage in work triangle)
  2. Furniture placement uses constraint satisfaction: minimum clearance from walls (0.3m), path to door always clear (1m corridor), items aligned to walls or other furniture, no interpenetration -- validated by collision check
  3. Decorative clutter scatter adds 5-15 props per room: books on shelves, dishes on tables, tools near workbenches, candles on surfaces -- using Poisson disk sampling within surface bounds, with room-purpose-appropriate prop palettes
  4. Lighting placement: torches at doorways and corridor junctions, candles on tables and nightstands, fireplace emissive, window-aligned ambient -- every room has at least 2 light sources with warm color temperature (2700-3500K)
  5. Interior contact sheet shows a furnished tavern, bedroom, and blacksmith workshop with prop density visually comparable to Skyrim interior cells -- assessed by item count per room and surface coverage percentage
**Plans**: TBD

### Phase 34: Multi-biome Terrain
**Goal**: Biome system distributes distinct terrain types across the world map using Voronoi-based zoning with corruption-aware tinting, smooth biome transitions, and terrain-conforming building foundations -- no floating buildings or sharp biome boundaries
**Depends on**: Phase 31 (terrain foundation), Phase 32 (buildings for terrain integration)
**Requirements**: MESH-05, MESH-09, MESH-10
**Success Criteria** (what must be TRUE):
  1. Voronoi-based biome distribution creates 5+ distinct biome regions (thornwood forest, corrupted swamp, mountain pass, volcanic wastes, frozen tundra) from the existing 14 biome palettes, with temperature/moisture/elevation parameters per cell
  2. Biome transition zones span 10-20m with material blending (splatmap alpha gradient), vegetation density fade, and prop palette interpolation -- no hard edges visible in overhead contact sheet
  3. Corruption system tints affected biome regions (purple/black overlay scaling 0-100%), affects vegetation (dead/twisted variants), and modulates material properties (increased roughness, darkened albedo)
  4. Building foundations generate terrain-conforming meshes that flatten terrain in a radius around the building footprint, with material blending at the foundation-terrain contact edge -- zero visible gaps in side-view contact sheet
  5. Multi-biome terrain renders as a single coherent world map (512m x 512m minimum) with 3+ biome types visible, terrain height variation >50m, and at least one river/road cutting across biome boundaries
**Plans**: TBD

### Phase 35: Multi-backend AI Integration
**Goal**: Tripo pipeline produces game-ready hero assets with full post-processing, texture extraction from GLB into standalone PBR maps, and unified art style validation ensuring AI-generated assets match procedural assets visually
**Depends on**: Phase 30 (mesh quality baseline for comparison)
**Requirements**: MESH-12
**Success Criteria** (what must be TRUE):
  1. Tripo-generated models automatically go through: de-lighting -> mesh repair -> retopology -> UV unwrap -> PBR texture EXTRACTION from embedded GLB textures into standalone albedo/normal/roughness/metallic/AO files (not blank images)
  2. Smart material overlay applies procedural weathering (edge wear, cavity dirt, height-based moss) on TOP of Tripo's extracted textures -- AI textures enhanced, not replaced
  3. Art style validation compares Tripo output color palette, roughness distribution, and detail density against project standards -- flagging outliers with specific deviation metrics
  4. 4 variants generated per Tripo request, displayed in Blender grid layout for visual comparison -- best variant selected based on quality scoring (vertex count, UV coverage, material fidelity)
  5. Full pipeline from text prompt to Unity-ready FBX completes in under 10 minutes with zero manual intervention -- validated by end-to-end test with 3 asset types (prop, weapon, character)
**Plans**: TBD

### Phase 36: World Composer
**Goal**: Settlement generation produces complete town layouts with road networks, lot subdivision, district zoning, building placement on lots, and street-level props -- a generated town is walkable and visually coherent from ground level
**Depends on**: Phase 32 (buildings), Phase 33 (interiors), Phase 34 (terrain)
**Requirements**: MESH-08
**Success Criteria** (what must be TRUE):
  1. Road network generation uses L-system or tensor field approach producing organic street layouts with T-junctions, intersections, and varying road widths -- road MESHES have curbs, cobblestone texture, and proper UV mapping (not flat colored boxes)
  2. Lot subdivision from road network creates building plots with street frontage, and EVERY plot has a building generated on it via the building grammar -- no empty marker boxes
  3. District zoning assigns building types by distance from center: market square (shops, tavern) -> civic (temple, town hall) -> residential (houses) -> industrial (blacksmith, tannery) -> outskirts (farms, walls)
  4. Street-level props placed along roads: lamp posts at intersections, benches near buildings, market stalls in commercial districts, wells in residential areas, defensive posts near walls -- using Poisson disk sampling with prop-type-appropriate spacing
  5. Generated town contact sheet (overhead + 4 ground-level angles) shows a coherent settlement that could pass as a Skyrim village -- buildings connected by roads, terrain integrated, vegetation present, no floating objects
**Plans**: TBD

### Phase 37: Pipeline Integration
**Goal**: All procedural systems compose into a single end-to-end map generation pipeline with state persistence, Addressables streaming setup, and runtime occlusion -- a complete map can be generated, exported, and loaded in Unity
**Depends on**: Phase 36 (world composition), Phase 35 (AI asset integration)
**Requirements**: MESH-16, PIPE-01
**Success Criteria** (what must be TRUE):
  1. `asset_pipeline action=compose_map` generates terrain -> roads -> building lots -> buildings -> interiors -> vegetation -> props in sequence, with state persisted to JSON between steps for resumability
  2. Addressables streaming groups generated per district: each building with interior is a separate addressable group, terrain tiles are distance-based groups -- loading zones defined by district boundaries
  3. Occlusion zones generated at doorways and district transitions, with portal geometry for interior/exterior streaming boundary
  4. Full map generation pipeline produces a Unity-importable package: FBX meshes + PBR texture sets + LOD variants + Addressables config + scene hierarchy JSON
  5. Research document (PIPE-01) covers AAA techniques from Skyrim, Fable, AC Valhalla with specific implementation references for each technique adopted in the pipeline
**Plans**: TBD

### Phase 38: Starter Town
**Goal**: Generate a complete, playable starter town with 10-15 buildings, furnished interiors, market area, fortifications, and terrain integration -- the town is the quality benchmark proving the entire pipeline works end-to-end
**Depends on**: Phase 37 (full pipeline), all preceding phases
**Requirements**: MESH-13
**Success Criteria** (what must be TRUE):
  1. Starter town has 10-15 buildings: 1 tavern (interior: bar, tables, rooms), 1 blacksmith (interior: forge, anvils, weapons), 1 temple, 2-3 shops, 4-6 houses, 1 town hall, defensive wall with gate -- each with furnished interior
  2. Market area with 5+ stalls, a central well/fountain, cobblestone ground, and street-level props (crates, barrels, signs, lanterns)
  3. Fortification perimeter: wall sections with walkways, 2+ guard towers, main gate with portcullis geometry, at least 1 secret entrance (sewer/cave)
  4. Every building exterior and interior passes visual QA: contact sheet reviewed, no floating objects, no z-fighting, no missing faces, consistent material quality, prop density comparable to Skyrim
  5. Town exports to Unity as Addressables-ready package, loads in under 5 seconds on PC, maintains 60fps at 1080p with all buildings and terrain visible -- profiled via unity_performance action=profile_scene
**Plans**: 4 plans
Plans:
- [x] 39-01-PLAN.md -- Foundation wiring + AAA visual verification protocol
- [x] 39-02-PLAN.md -- Terrain + water + vegetation overhaul
- [x] 39-03-PLAN.md -- Castle + settlement + combat zones
- [x] 39-04-PLAN.md -- Performance optimization + final verification

**Delivered:** TBD (4 plans created)

## Progress

**Execution Order:**
Phases execute in numeric order. Decimal phases (e.g., 18.1) insert between their surrounding integers.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Server Architecture | v1.0 | 3/3 | Complete | 2026-03-19 |
| 2. Mesh, UV & Topology Pipeline | v1.0 | 3/3 | Complete | 2026-03-19 |
| 3. Texturing & Asset Generation | v1.0 | 4/4 | Complete | 2026-03-19 |
| 4. Rigging | v1.0 | 4/4 | Complete | 2026-03-19 |
| 5. Animation | v1.0 | 4/4 | Complete | 2026-03-19 |
| 6. Environment & World Building | v1.0 | 4/4 | Complete | 2026-03-19 |
| 7. VFX, Audio, UI & Unity Scene | v1.0 | 5/5 | Complete | 2026-03-19 |
| 8. Gameplay AI & Performance | v1.0 | 3/3 | Complete | 2026-03-19 |
| 9. Unity Editor Deep Control | v2.0 | 3/3 | Complete | 2026-03-20 |
| 10. C# Programming Framework | v2.0 | 4/4 | Complete | 2026-03-20 |
| 11. Data Architecture & Asset Pipeline | v2.0 | 4/4 | Complete | 2026-03-20 |
| 12. Core Game Systems | v2.0 | 3/3 | Complete | 2026-03-20 |
| 13. Content & Progression Systems | v2.0 | 3/3 | Complete | 2026-03-20 |
| 14. Camera, Cinematics & Scene Management | v2.0 | 5/5 | Complete | 2026-03-20 |
| 15. Game UX & Encounter Design | v2.0 | 4/4 | Complete | 2026-03-20 |
| 16. Quality Assurance & Testing | v2.0 | 4/4 | Complete | 2026-03-20 |
| 17. Build & Deploy Pipeline | v2.0 | 3/3 | Complete | 2026-03-21 |
| 18. Procedural Mesh Integration + Terrain Depth | v3.0 | 3/3 | Complete | 2026-03-21 |
| 19. Character Excellence | v3.0 | 3/3 | Complete | 2026-03-21 |
| 20. Advanced Animation + FromSoft Combat Feel | v3.0 | 3/3 | Complete | 2026-03-21 |
| 21. Audio Middleware Architecture | v3.0 | 1/1 | Complete | 2026-03-21 |
| 22. AAA Dark Fantasy UI/UX Polish | v3.0 | 1/1 | Complete | 2026-03-21 |
| 23. VFX Mastery | v3.0 | 1/1 | Complete | 2026-03-21 |
| 24. Production Pipeline | v3.0 | 1/1 | Complete | 2026-03-21 |
| 30. Mesh Foundation | v7.0 | 1/1 | Complete    | 2026-03-31 |
| 31. Terrain & Environment | v7.0 | 3/3 | Complete   | 2026-03-31 |
| 32. Building System | v7.0 | 1/1 | Complete    | 2026-03-31 |
| 33. Interior System | v7.0 | 1/1 | Complete    | 2026-03-31 |
| 34. Multi-biome Terrain | v7.0 | 1/1 | Complete    | 2026-03-31 |
| 35. Multi-backend AI Integration | v7.0 | 1/1 | Complete   | 2026-04-01 |
| 36. World Composer | v7.0 | 2/2 | Complete   | 2026-04-01 |
| 37. Pipeline Integration | v7.0 | 0/TBD | Not Started | - |
| 38. Starter Town | v7.0 | 0/TBD | Not Started | - |
| 39. AAA Map Quality Overhaul | v10.0 | 4/4 | Complete    | 2026-04-04 |
| 43. Geometry Overhaul -- Weapons, Armor, Creatures | v10.0 | 0/5 | Complete    | 2026-04-04 |
| 44. Geometry Overhaul -- Props, Environments, Buildings | v10.0 | 0/4 | Complete    | 2026-04-04 |
| 45. Data Safety & Integrity | v10.0 | 0/3 | Complete    | 2026-04-04 |
| 46. Export Pipeline Completion | v10.0 | 0/3 | Planned | - |

### v10.0 Total Quality: Zero Gaps Remaining (Phases 39-48)

### Phase 43: Geometry Overhaul -- Weapons, Armor, Creatures
**Goal**: Upgrade all weapon, armor, and creature generators from PLACEHOLDER/BASIC to DECENT+ quality by increasing vertex density 3-10x, adding anatomical/mechanical detail geometry, fixing orientation bugs, and fixing creature part dispatch crashes
**Depends on**: Phase 39 (pipeline fixes)
**Requirements**: GEOM-01, GEOM-02, GEOM-03, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Every weapon generator (sword, axe, mace, bow, shield, staff) produces 1500-3500 verts with proper cross-sections, component junctions, and style-specific detail
  2. Every armor generator (pauldron, chestplate, gauntlet) produces 1500-4000 verts with layered plates, anatomical contour, and articulated fingers on gauntlet
  3. Every quadruped creature (wolf, bear, lion, horse, deer, boar, rat_giant) produces 4000-15000 verts with anatomical landmarks, correct Z-up orientation, and joint detail
  4. Fantasy creatures (chimera, wyvern, basilisk, etc.) produce 8000-15000 verts with distinct multi-body junction geometry
  5. All 5 crashed creature part generators (mouth, eyelid, paw, wing, serpent) work without tuple error and produce higher-density meshes
**Plans**: 5 plans
Plans:
- [ ] 43-01-PLAN.md -- Test infrastructure + creature part dispatch fix
- [ ] 43-02-PLAN.md -- Weapon geometry: sword, axe, mace
- [ ] 43-03-PLAN.md -- Creature anatomy overhaul: quadruped + fantasy
- [ ] 43-04-PLAN.md -- Weapon geometry: bow, shield, staff + all armor
- [ ] 43-05-PLAN.md -- Final verification + visual checkpoint

### Phase 44: Geometry Overhaul -- Props, Environments, Buildings
**Goal**: Upgrade all prop, environment, and building geometry from PLACEHOLDER/BASIC to DECENT+ quality by adding detail sub-geometry, fixing dimensional accuracy, and increasing vertex density for cloth simulation
**Depends on**: Phase 43 (weapons/armor/creatures geometry), Phase 42 (dead code wiring)
**Requirements**: GEOM-04, GEOM-05, GEOM-06, GEOM-07, GEOM-08, GEOM-09, GEOM-10, GEOM-11, GEOM-12, TEST-03, TEST-04
**Plans**: 4 plans
Plans:
- [ ] 44-01-PLAN.md -- Prop detail geometry + chain optimization + flag cloth density
- [ ] 44-02-PLAN.md -- Terrain micro-undulation, skirt, dungeon/cave height, stalactites, scree, smootherstep
- [ ] 44-03-PLAN.md -- Castle wall thickness, merlons, gatehouse arch, building detail, clothing density, furniture quality
- [ ] 44-04-PLAN.md -- Full test suite verification + human visual verification


### Phase 45: Data Safety & Integrity
**Goal**: Fix six data-loss and data-corruption bugs across the Tripo texture pipeline, compose_interior spatial planning, settlement scaling, and scene hierarchy export
**Depends on**: Phase 39 (pipeline fixes)
**Requirements**: SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-06, TEST-04
**Success Criteria** (what must be TRUE):
  1. Tripo-generated models retain embedded PBR textures after generate_and_process() pipeline
  2. Pipeline checkpoint resume preserves partially-loaded interior_results
  3. compose_interior uses pre-aligned binding geometry when available
  4. Multi-floor rooms get correct Z offsets from floor field
  5. Settlement generator honors building_count_override from map plan
  6. emit_scene_hierarchy only includes map-scoped objects
**Plans**: 3 plans
Plans:
- [ ] 45-01-PLAN.md -- Tripo texture overwrite fix + checkpoint atomicity fix
- [ ] 45-02-PLAN.md -- Interior binding geometry + multi-floor Z + settlement scaling
- [ ] 45-03-PLAN.md -- Scene hierarchy scoping + full test suite verification


### Phase 46: Export Pipeline Completion
**Goal**: Wire all export pipeline steps into compose_map (game_check, texture bake, LOD generation, collision meshes, FBX per-group export), create new modules for vegetation instance serialization and splatmap-to-PNG export, and fix the aaa_verify stale screenshot bug and generate_map_package broken group export
**Depends on**: Phase 39 (pipeline fixes), Phase 45 (data safety)
**Requirements**: EXPORT-01, EXPORT-02, EXPORT-03, EXPORT-04, EXPORT-05, EXPORT-06, EXPORT-07, EXPORT-08, EXPORT-09, TEST-04
**Success Criteria** (what must be TRUE):
  1. compose_map produces per-group FBX files via new Steps 11-16 (game_check, bake, LOD, collision, data export, FBX)
  2. render_angle handler positions camera at specified yaw/pitch (not aliased to viewport screenshot)
  3. derive_addressable_groups populates terrain and interior object lists
  4. export_fbx supports object_names filter for per-group export
  5. Vegetation instances serialized to Unity TreeInstance JSON with correct axis swap
  6. Splatmap vertex colors rasterized to PNG at configurable resolution
**Plans**: 3 plans
Plans:
- [ ] 46-01-PLAN.md -- Bug fixes: render_angle handler, addressable groups, export_fbx object_names
- [ ] 46-02-PLAN.md -- New modules: collision generator, vegetation serializer, splatmap exporter
- [ ] 46-03-PLAN.md -- Wire compose_map Steps 11-16 + integration tests

---
*Roadmap created: 2026-03-18*
*v2.0 phases added: 2026-03-19*
*v2.0 shipped: 2026-03-21*
*v3.0 phases added: 2026-03-21*
*v3.0 shipped: 2026-03-21*
*v7.0 planning started: 2026-03-31*
*v10.0 Phase 44 planned: 2026-04-04*
*v10.0 Phase 43 planned: 2026-04-04*
*v10.0 Phase 45 planned: 2026-04-04*
*v10.0 Phase 46 planned: 2026-04-04*
