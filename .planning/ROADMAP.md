# Roadmap: VeilBreakers GameDev Toolkit

**Created:** 2026-03-18
**Updated:** 2026-03-20 (Phase 16 planned)

## Milestones

- [x] **v1.0 Foundation & Full Pipeline** - Phases 1-8 (shipped 2026-03-19)
- [ ] **v2.0 Complete Unity Game Development Coverage** - Phases 9-17 (in progress)

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

### v2.0 Complete Unity Game Development Coverage

- [ ] **Phase 9: Unity Editor Deep Control** - Prefabs, components, hierarchy, physics, project settings, packages, import configuration, asset operations
- [ ] **Phase 10: C# Programming Framework** - General-purpose code generation, script modification, editor tooling, test framework, architecture patterns
- [x] **Phase 11: Data Architecture & Asset Pipeline** - ScriptableObjects, JSON config, localization, game data tools, Git LFS, normal map baking, sprite atlasing
- [ ] **Phase 12: Core Game Systems** - Save/load, health/damage, character controller, Input System, settings menu, VeilBreakers combat systems
- [ ] **Phase 13: Content & Progression Systems** - Inventory, dialogue, quests, loot tables, crafting, skill trees, combat balancing, equipment systems
- [ ] **Phase 14: Camera, Cinematics & Scene Management** - Cinemachine, Timeline, cutscenes, scene loading, lighting, probes, terrain detail, world design, RPG world systems
- [ ] **Phase 15: Game UX & Encounter Design** - Minimap, tutorials, damage numbers, interaction prompts, encounter scripting, AI director
- [ ] **Phase 16: Quality Assurance & Testing** - Unity TCP bridge, test runner, automated play, profiling, memory leaks, static analysis, crash reporting, live inspection
- [ ] **Phase 17: Build & Deploy Pipeline** - Multi-platform builds, Addressables, CI/CD, versioning, platform configs

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
- [ ] 16-01-PLAN.md -- Unity TCP bridge foundation: Python UnityConnection client, UnityCommand/UnityResponse models, C# bridge addon template generators (QA-00)
- [ ] 16-02-PLAN.md -- QA template generators batch 1: test runner, automated play sessions, profiler, memory leak detector, static code analyzer (QA-01, QA-02, QA-03, QA-04, QA-05)
- [ ] 16-03-PLAN.md -- QA template generators batch 2: crash reporting (Sentry), analytics/telemetry, live game state inspector (QA-06, QA-07, QA-08)
- [ ] 16-04-PLAN.md -- Compound tool wiring: unity_qa (9 actions) + deep C# syntax tests (all 9 requirements)

### Phase 17: Build & Deploy Pipeline
**Goal**: Claude can orchestrate complete build pipelines -- multi-platform builds, Addressable assets, CI/CD automation, versioning, and platform-specific configuration
**Depends on**: Phase 9 (Build Settings, Player Settings), Phase 16 (tests run as part of CI)
**Requirements**: BUILD-01, BUILD-02, BUILD-03, BUILD-04, BUILD-05, SHDR-03, ACC-02
**Success Criteria** (what must be TRUE):
  1. Claude can trigger builds for multiple platforms (Windows, Mac, Linux, Android, iOS, WebGL) with correct per-platform settings and receive build size reports
  2. Claude can configure Addressable Asset Groups with remote/local paths, content catalogs, and memory management profiles
  3. Claude can generate CI/CD pipeline configs (GitHub Actions, GitLab CI) that automate build, test, and deploy steps for Unity projects
  4. Claude can manage version numbers (semantic versioning), create release branches, and generate changelogs from commit history
  5. Claude can configure platform-specific settings (Android manifest, iOS plist, WebGL template) without manual Editor interaction

**Plans**: TBD

Plans:
- [ ] 17-01: TBD
- [ ] 17-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order. Decimal phases (e.g., 9.1) insert between their surrounding integers.

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
| 16. Quality Assurance & Testing | 3/4 | In Progress|  | - |
| 17. Build & Deploy Pipeline | v2.0 | 0/2 | Not started | - |

---
*Roadmap created: 2026-03-18*
*v2.0 phases added: 2026-03-19*
*Phase 10 planned: 2026-03-20*
*Phase 11 planned: 2026-03-20*
*Phase 11 complete: 2026-03-20*
*Phase 12 planned: 2026-03-20*
*Phase 13 planned: 2026-03-20*
*Phase 14 planned: 2026-03-20*
*Phase 15 planned: 2026-03-20*
*Phase 16 planned: 2026-03-20*
