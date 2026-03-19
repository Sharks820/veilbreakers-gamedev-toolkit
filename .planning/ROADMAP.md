# Roadmap: VeilBreakers GameDev Toolkit

**Created:** 2026-03-18
**Depth:** Standard (5-8 phases)
**Coverage:** 128/128 v1 requirements mapped

## Phases

- [ ] **Phase 1: Foundation & Server Architecture** - MCP server skeleton, compound tool pattern, Blender socket bridge, async job queue, visual feedback
- [ ] **Phase 2: Mesh, UV & Topology Pipeline** - Mesh analysis/editing/repair, UV unwrapping/packing, game-readiness validation
- [ ] **Phase 3: Texturing & Asset Generation** - PBR textures, AI 3D generation, concept art, asset pipeline processing, export validation
- [ ] **Phase 4: Rigging** - Creature rig templates, facial rigging, IK chains, spring bones, weight painting, ragdoll, shape keys
- [ ] **Phase 5: Animation** - Procedural gaits, combat animations, contact sheet preview, root motion, AI motion, batch export
- [ ] **Phase 6: Environment & World Building** - Terrain, caves, buildings, dungeons, vegetation, interiors, modular kits, props
- [ ] **Phase 7: VFX, Audio, UI & Unity Scene** - Particle VFX, shaders, audio generation, UI screens, scene setup, Gemini visual review
- [ ] **Phase 8: Gameplay AI & Performance** - Mob AI controllers, spawn systems, profiling, LOD, lightmaps, build pipeline

## Phase Details

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
- [ ] 02-02-PLAN.md -- UV analysis, xatlas unwrapping, packing, lightmap, density equalization (blender_uv tool)
- [ ] 02-03-PLAN.md -- Mesh editing, selection engine, booleans, retopology, sculpt operations

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
- [ ] 03-02-PLAN.md -- Surgical texture editing with seamless blending (MCP-side Pillow)
- [ ] 03-03-PLAN.md -- Asset pipeline, AI 3D generation, LOD, catalog, export validation
- [ ] 03-04-PLAN.md -- Concept art, compound MCP tool wiring, integration

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
- [ ] 04-01-PLAN.md -- Core rig templates (10 creatures), mesh analysis, custom rig builder
- [ ] 04-02-PLAN.md -- Weight painting, deformation testing, rig validation, weight fix
- [ ] 04-03-PLAN.md -- Advanced features: facial rig, IK, spring bones, ragdoll, retarget, shape keys
- [ ] 04-04-PLAN.md -- Handler registration and blender_rig compound MCP tool wiring

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
- [ ] 05-01-PLAN.md -- Pure-logic keyframe engine, gait configs, attack/reaction generators
- [ ] 05-02-PLAN.md -- Blender animation handlers: walk/fly/idle/attack/reaction/custom (ANIM-01 to ANIM-06)
- [ ] 05-03-PLAN.md -- Export handlers: preview, secondary motion, root motion, retarget, AI stub, batch export (ANIM-07 to ANIM-12)
- [ ] 05-04-PLAN.md -- Handler registration and blender_animation compound MCP tool wiring

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
- [ ] 06-01-PLAN.md -- Terrain generation, erosion, biome painting, rivers/roads, water, heightmap export
- [ ] 06-02-PLAN.md -- BSP dungeon, cellular automata caves, town layout generation
- [ ] 06-03-PLAN.md -- Building grammar, castle/tower/bridge, ruins, interiors, modular kit
- [ ] 06-04-PLAN.md -- Vegetation/prop scatter, handler registration, compound MCP tool wiring

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
- [ ] 07-01-PLAN.md -- Unity MCP server foundation, auto-recompile/editor tools, Gemini review, Settings
- [ ] 07-02-PLAN.md -- VFX system: particle templates, brand VFX, shaders, post-processing, screen effects
- [ ] 07-03-PLAN.md -- Audio system: ElevenLabs AI generation, footstep/adaptive/mixer/pool C# templates
- [ ] 07-04-PLAN.md -- UI system: UXML/USS generation, WCAG contrast, layout validation, screenshot diff
- [ ] 07-05-PLAN.md -- Scene setup: terrain, scatter, lighting, NavMesh, animator, avatar, animation rigging

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
- [ ] 08-01-PLAN.md -- Gameplay templates: mob controller, aggro, patrol, spawn, behavior tree, combat ability, projectile (MOB-01 to MOB-07)
- [ ] 08-02-PLAN.md -- Performance templates: scene profiler, LOD setup, lightmap baking, asset audit, build automation (PERF-01 to PERF-05)
- [ ] 08-03-PLAN.md -- Compound tool wiring: unity_gameplay + unity_performance in unity_server.py

## Progress

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Foundation & Server Architecture | 3/3 | Complete | 2026-03-19 |
| 2. Mesh, UV & Topology Pipeline | 3/3 | Complete | 2026-03-19 |
| 3. Texturing & Asset Generation | 1/4 | In Progress | - |
| 4. Rigging | 0/4 | Planned | - |
| 5. Animation | 0/4 | Planned | - |
| 6. Environment & World Building | 0/4 | Planned | - |
| 7. VFX, Audio, UI & Unity Scene | 0/5 | Planned | - |
| 8. Gameplay AI & Performance | 0/3 | Planned | - |

---
*Roadmap created: 2026-03-18*
*Last updated: 2026-03-19*
