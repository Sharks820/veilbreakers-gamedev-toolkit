# Requirements: VeilBreakers GameDev Toolkit

**Defined:** 2026-03-18
**Core Value:** Every tool returns structured validation data and visual proof so Claude never works blind

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation / Architecture

- [ ] **ARCH-01**: MCP servers use compound action pattern (max 26 tool definitions total across all servers)
- [ ] **ARCH-02**: Blender addon uses async job queue with bpy.app.timers dispatch (no main-thread violations)
- [ ] **ARCH-03**: No raw exec() — all Blender commands dispatched through validated command handlers
- [ ] **ARCH-04**: Every mutation tool returns viewport screenshot as visual proof
- [ ] **ARCH-05**: Structured error responses with recovery suggestions on all tool failures
- [ ] **ARCH-06**: FastMCP 3.0 server skeleton with stdio transport for all three servers
- [ ] **ARCH-07**: Blender TCP socket bridge with timeout handling and reconnection
- [ ] **ARCH-08**: Contact sheet rendering system (multiple frames/angles in single image)

### Mesh Topology & Editing

- [ ] **MESH-01**: Full topology analysis with A-F grading (non-manifold, n-gons, poles, edge flow, loose geo)
- [ ] **MESH-02**: Auto-repair (remove doubles, fix normals, fill holes, remove loose, dissolve degenerate)
- [ ] **MESH-03**: Surgical mesh editing — select by material slot, vertex group, loose parts, face normal
- [ ] **MESH-04**: Sculpt operations on selections (smooth, inflate, flatten, crease)
- [ ] **MESH-05**: Boolean operations (add, subtract, intersect) for geometry modification
- [ ] **MESH-06**: Extrude, inset, mirror, separate, join operations
- [ ] **MESH-07**: Retopology with target face count preserving hard edges
- [ ] **MESH-08**: Game-readiness check (poly budget, UV, materials, bones, naming)

### UV Mapping

- [ ] **UV-01**: UV quality analysis (stretch, overlap, island count, texel density, seam placement)
- [ ] **UV-02**: Automatic UV unwrapping via xatlas with configurable quality
- [ ] **UV-03**: UV island packing optimization
- [ ] **UV-04**: Lightmap UV (UV2) generation for Unity
- [ ] **UV-05**: Texel density equalization across islands

### Texturing

- [ ] **TEX-01**: PBR material creation from text description (albedo, normal, roughness, metallic, AO)
- [ ] **TEX-02**: Surgical texture editing — mask UV/material region, apply changes to region only
- [ ] **TEX-03**: AI texture inpainting on masked region (fix belt, change armor trim, etc.)
- [ ] **TEX-04**: HSV adjustment on masked texture regions
- [ ] **TEX-05**: Texture seam blending between UV islands
- [ ] **TEX-06**: Procedural wear/damage map generation (convex=worn, concave=dirty, edges=chipped)
- [ ] **TEX-07**: Texture baking high-poly to low-poly (normal, AO, curvature, thickness)
- [ ] **TEX-08**: AI texture upscaling via Real-ESRGAN (2x/4x)
- [ ] **TEX-09**: Seamless tileable texture generation
- [ ] **TEX-10**: Texture validation (resolution, format, UV coverage, compression suitability)

### Rigging

- [ ] **RIG-01**: Mesh analysis for rigging (joint detection, symmetry, proportions, template recommendation)
- [ ] **RIG-02**: 10 Rigify-based creature rig templates (humanoid, quadruped, bird, insect, serpent, floating, dragon, multi-armed, arachnid, amorphous)
- [ ] **RIG-03**: Custom creature rig builder (configurable limbs, wings, tail, jaw, appendages)
- [ ] **RIG-04**: Facial rigging system (jaw, lips, eyelids, eyebrows, cheeks — monster variants: snarl, hiss, roar)
- [ ] **RIG-05**: IK chain setup (2-bone, spline for tails/tentacles, multi-target, rotation limits)
- [ ] **RIG-06**: Spring/jiggle bone system for secondary motion (hair, capes, tails, chains)
- [ ] **RIG-07**: Auto weight painting with immediate deformation testing
- [ ] **RIG-08**: Deformation test at 8 standard poses with contact sheet output
- [ ] **RIG-09**: Comprehensive rig validation (unweighted verts, bleeding, bone rolls, symmetry, constraints)
- [ ] **RIG-10**: Weight mirror (L↔R) and auto-fix (normalize, clean zeros, smooth)
- [ ] **RIG-11**: Ragdoll auto-setup from existing rig (colliders + joints + muscle limits)
- [ ] **RIG-12**: Rig retargeting between different body types
- [ ] **RIG-13**: Shape keys for expressions and damage states

### Animation

- [ ] **ANIM-01**: Procedural walk/run cycle (biped, quadruped, hexapod, arachnid, serpent gaits)
- [ ] **ANIM-02**: Procedural fly/hover cycle (wing frequency, amplitude, glide ratio)
- [ ] **ANIM-03**: Procedural idle animation (breathing, weight shift, secondary motion)
- [ ] **ANIM-04**: Attack animations (melee swing, thrust, slam, bite, claw, tail whip, wing buffet, breath attack)
- [ ] **ANIM-05**: Death, hit reaction (directional), and spawn animations
- [ ] **ANIM-06**: Custom animation from text description ("rises up, spreads wings, breathes fire")
- [ ] **ANIM-07**: Animation contact sheet preview (every Nth frame, multiple angles)
- [ ] **ANIM-08**: Secondary motion physics (jiggle on tails, ears, capes, hair)
- [ ] **ANIM-09**: Root motion extraction and animation events for Unity
- [ ] **ANIM-10**: Mixamo retargeting to custom rigs
- [ ] **ANIM-11**: AI motion generation via HY-Motion / MotionGPT
- [ ] **ANIM-12**: Batch animation export as separate Unity clips

### Environment / World Building

- [ ] **ENV-01**: Terrain generation (mountains, hills, plains, volcanic, canyon, cliffs) with erosion
- [ ] **ENV-02**: Auto terrain texture painting (slope/altitude/moisture biome rules)
- [ ] **ENV-03**: Cave/dungeon system generation (connected rooms, corridors, natural formations)
- [ ] **ENV-04**: River/stream carving with erosion and flow
- [ ] **ENV-05**: Road/path generation between points with proper grading
- [ ] **ENV-06**: Water body creation (lakes, oceans, ponds with shoreline and depth)
- [ ] **ENV-07**: Biome-aware vegetation scatter (trees, grass, rocks, bushes with slope/altitude rules)
- [ ] **ENV-08**: AAA-quality procedural building generation (configurable style, floors, roof, materials)
- [ ] **ENV-09**: Castle/tower/bridge/fortress generation with architectural detail
- [ ] **ENV-10**: Ruins generation (damage existing structures — broken walls, collapsed roof, overgrown)
- [ ] **ENV-11**: Town/settlement layout (streets, building plots, districts, landmarks)
- [ ] **ENV-12**: Dungeon layout generation (rooms, corridors, doors, spawn points, loot placement)
- [ ] **ENV-13**: Interior generation (furniture, wall decorations, lighting)
- [ ] **ENV-14**: Modular architecture kit (snap-together walls, floors, corners, doors, windows)
- [ ] **ENV-15**: Context-aware prop scatter (barrels near tavern, crates near dock)
- [ ] **ENV-16**: Breakable prop variants and destroyed versions

### VFX

- [ ] **VFX-01**: VFX Graph particle system from text description ("fire + sparks + smoke")
- [ ] **VFX-02**: Per-brand damage VFX (IRON sparks, VENOM drip, SURGE crackle, DREAD shadows, etc.)
- [ ] **VFX-03**: Environmental VFX (dust motes, fireflies, snow, rain, ash, pollen)
- [ ] **VFX-04**: Weapon/projectile trail effects with fade
- [ ] **VFX-05**: Character aura/buff VFX (corruption glow, healing shimmer, power up)
- [ ] **VFX-06**: Corruption shader scaling with corruption percentage (0-100%)
- [ ] **VFX-07**: Shader Graph creation (dissolve, force field, water, foliage, outline, damage overlay)
- [ ] **VFX-08**: Post-processing setup (bloom, color grading, vignette, AO, DOF, motion blur)
- [ ] **VFX-09**: Screen effects (camera shake, damage vignette, low health pulse, poison overlay, heal glow)
- [ ] **VFX-10**: Hero/monster ability VFX with animation integration

### Audio

- [ ] **AUD-01**: AI SFX generation from text description (sword slash, monster growl, portal opening)
- [ ] **AUD-02**: Music loop generation (combat, exploration, boss, town themes)
- [ ] **AUD-03**: Voice line synthesis for NPCs/monsters
- [ ] **AUD-04**: Ambient soundscape generation per biome (layered: wind + birds + water)
- [ ] **AUD-05**: Surface-material-aware footstep system (stone, wood, grass, metal, water)
- [ ] **AUD-06**: Adaptive music layers (add/remove based on combat intensity, exploration, stealth)
- [ ] **AUD-07**: Audio zones (reverb for caves, outdoor open, indoor muffled)
- [ ] **AUD-08**: Unity Audio Mixer with groups (SFX, Music, Voice, Ambient, UI)
- [ ] **AUD-09**: Audio manager with pooling, priority, ducking
- [ ] **AUD-10**: Assign SFX to animation events (footsteps at contact frames, hit sounds)

### Unity Visual Testing & UI

- [ ] **UI-01**: Game view screenshot capture at specified resolution
- [ ] **UI-02**: UI layout validation (VisualElement tree: overlaps, zero-size, overflow, contrast)
- [ ] **UI-03**: Responsive testing at 5 resolutions (720p, 1080p, 1440p, 4K, mobile)
- [ ] **UI-04**: Gemini visual review integration (send screenshot, get quality assessment)
- [ ] **UI-05**: UI screen generation (UXML + USS from description)
- [ ] **UI-06**: WCAG contrast ratio validation for all text
- [ ] **UI-07**: Screenshot comparison for visual regression testing

### Unity Scene & Gameplay

- [ ] **SCENE-01**: Unity Terrain from heightmap with splatmaps
- [ ] **SCENE-02**: Object scattering with density rules (trees, rocks, props)
- [ ] **SCENE-03**: Lighting setup (directional, ambient, fog, post-processing, time-of-day)
- [ ] **SCENE-04**: NavMesh baking with agent settings and NavMesh Links
- [ ] **SCENE-05**: Animator Controller creation (states, transitions, parameters, blend trees)
- [ ] **SCENE-06**: Avatar configuration (Humanoid/Generic bone mapping)
- [ ] **SCENE-07**: Animation Rigging constraints (Two-Bone IK, Multi-Aim)

### AI / Mob Systems

- [ ] **MOB-01**: Mob controller generation (patrol, chase, attack, flee state machine)
- [ ] **MOB-02**: Aggro system (detection range, decay, threat table, leash distance)
- [ ] **MOB-03**: Patrol routes with waypoints, dwell times, random deviation
- [ ] **MOB-04**: Spawn system (max count, respawn timer, conditions, area bounds)
- [ ] **MOB-05**: Behavior tree scaffolding (ScriptableObject with nodes)
- [ ] **MOB-06**: Combat ability prefab (animation + VFX + hitbox + damage + sound)
- [ ] **MOB-07**: Projectile system (trajectory, trail VFX, impact effect)

### Asset Pipeline

- [ ] **PIPE-01**: Tripo3D API integration for AI 3D model generation
- [ ] **PIPE-02**: AI PBR texture generation (CHORD or fal.ai based)
- [ ] **PIPE-03**: Gaea CLI terrain generation integration
- [ ] **PIPE-04**: PyMeshLab mesh processing (analysis, repair, decimation)
- [ ] **PIPE-05**: Auto LOD chain generation (configurable percentages)
- [ ] **PIPE-06**: Unity-optimized FBX/GLB export with validation
- [ ] **PIPE-07**: Export re-import validation (scale, orientation, bones, materials)

### Performance & Build

- [ ] **PERF-01**: Scene profiling (frame time, draw calls, batches, tris, memory)
- [ ] **PERF-02**: LODGroup auto-generation for scene meshes
- [ ] **PERF-03**: Lightmap baking with progress monitoring
- [ ] **PERF-04**: Asset audit (unused assets, oversized textures, uncompressed audio)
- [ ] **PERF-05**: Build pipeline automation with size report

### Concept / Pre-Production

- [ ] **CONC-01**: Concept art generation from text (character, environment, prop, creature)
- [ ] **CONC-02**: Color palette generation from description or reference
- [ ] **CONC-03**: Silhouette readability testing at game camera distances

## v2 Requirements

Deferred to future release.

### Live Operations
- **LIVE-01**: Analytics integration
- **LIVE-02**: Patch diff generation

### Advanced AI
- **ADV-01**: Play test bot (automated gameplay recording/playback)
- **ADV-02**: Economy simulation (resource generation/consumption over time)
- **ADV-03**: Progression curve validation (XP, level scaling, item power)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multiplayer/networking tools | VeilBreakers is single-player |
| Mobile platform optimization | PC-first development |
| Custom game engine | Unity is the target engine |
| Houdini integration | Cost prohibitive; Blender Geometry Nodes covers procedural needs |
| Real-time collaboration | Solo developer workflow |
| Blender raw exec() | Security vulnerability; all commands via validated handlers |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARCH-01 through ARCH-08 | Phase 1 | Pending |
| MESH-01 through MESH-08 | Phase 2 | Pending |
| UV-01 through UV-05 | Phase 2 | Pending |
| TEX-01 through TEX-10 | Phase 3 | Pending |
| RIG-01 through RIG-13 | Phase 4 | Pending |
| ANIM-01 through ANIM-12 | Phase 5 | Pending |
| ENV-01 through ENV-16 | Phase 6 | Pending |
| VFX-01 through VFX-10 | Phase 7 | Pending |
| AUD-01 through AUD-10 | Phase 7 | Pending |
| UI-01 through UI-07 | Phase 7 | Pending |
| SCENE-01 through SCENE-07 | Phase 7 | Pending |
| MOB-01 through MOB-07 | Phase 8 | Pending |
| PIPE-01 through PIPE-07 | Phase 3 | Pending |
| PERF-01 through PERF-05 | Phase 8 | Pending |
| CONC-01 through CONC-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 120 total
- Mapped to phases: 120
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after research completion*
