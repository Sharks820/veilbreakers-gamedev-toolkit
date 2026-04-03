# VeilBreakers MCP Toolkit -- Exhaustive Gap Analysis

**Date:** 2026-04-02
**Scope:** Complete audit of 16 Blender tools (162+ actions) + 22 Unity tools (150+ actions)
**Goal:** Identify every remaining gap preventing this from being a true AAA game development studio

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Modeling System](#1-modeling-system)
3. [Material/Shader System](#2-materialshader-system)
4. [Texture System](#3-texture-system)
5. [UV System](#4-uv-system)
6. [VFX System](#5-vfx-system)
7. [Animation System](#6-animation-system)
8. [Rigging System](#7-rigging-system)
9. [Audio System](#8-audio-system)
10. [AI/Gameplay System](#9-aigameplay-system)
11. [UI/UX System](#10-uiux-system)
12. [World/Environment System](#11-worldenvironment-system)
13. [Pipeline/Export System](#12-pipelineexport-system)
14. [Performance/Quality System](#13-performancequality-system)
15. [Camera/Cinematics System](#14-cameracinematics-system)
16. [Code/Data System](#15-codedata-system)
17. [Build/Deploy System](#16-builddeploy-system)
18. [Cross-System Integration Gaps](#17-cross-system-integration-gaps)
19. [Priority Summary](#priority-summary)

---

## Executive Summary

The toolkit is **remarkably comprehensive** for an AI-driven game dev pipeline. It covers modeling, texturing, rigging, animation, worldbuilding, VFX, audio, gameplay AI, UI, performance, and build/deploy across both Blender and Unity. However, several **CRITICAL and HIGH priority gaps** remain that would block or severely hamper shipping a real AAA game.

**Total gaps found: 67**
- CRITICAL: 8 (blocks game development)
- HIGH: 19 (major workaround needed)
- MEDIUM: 24 (nice to have for AAA quality)
- LOW: 16 (polish items)

---

## 1. Modeling System

### What Exists (STRONG)
- Full mesh analysis with A-F topology grading (MESH-01)
- Auto-repair pipeline: remove doubles, fix normals, fill holes (MESH-02)
- Game-readiness check with poly budget per platform (MESH-08)
- Boolean operations: union, difference, intersect (MESH-05)
- Retopology via QuadriFlow (MESH-07)
- Sculpt mode: 32 brush types, dyntopo, voxel remesh, face sets, multires (MESH-04a-f)
- Modular building kit: 175 piece variants (25 types x 5 styles + ruined) (modular_building_kit.py)
- AAA quality generators: swords, axes, maces, bows, shields, staffs, pauldrons, chestplates, gauntlets
- Creature anatomy: mouth interior, eyelids, paws, wings, serpent bodies, quadruped bodies, fantasy chimeras
- Riggable objects: doors, chains, flags, chests, chandeliers, drawbridges, rope bridges, signs, windmills, cages
- Mesh editing: extrude, inset, mirror, separate, join, loop cut, bevel, knife project, bisect
- Advanced modeling: symmetry, loop select, bridge edges, modifiers, circularize, insert mesh, alpha stamp
- Character body generation via skin modifier
- LOD pipeline with silhouette-preserving decimation and per-asset-type presets
- Geometry nodes: scatter, boolean, array along curve, vertex displacement
- Destruction system: 4 damage levels with rubble generation
- Hair system: 12 hair styles + 9 facial hair styles as mesh cards

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 1 | **No Blender-side collision mesh generation** | HIGH | LOD pipeline computes convex hulls in pure Python but no dedicated action to generate simplified collision meshes for Unity physics. Currently relies on Unity-side mesh collider fitting which is expensive at runtime. |
| 2 | **No mesh cleanup for internal faces** | MEDIUM | After boolean operations (e.g., cutting windows into walls), internal/hidden faces are not automatically removed. `post_boolean_cleanup` exists but only handles edge cases -- no full internal face detection. |
| 3 | **No spline/NURBS modeling** | MEDIUM | Only polygon meshes. No NURBS surface creation for smooth architectural elements (arches, moldings, organic surfaces). Curves exist (create, extrude_along) but not NURBS patches. |
| 4 | **No procedural armor fitting to arbitrary body shapes** | HIGH | Armor generators create standalone meshes. `equipment_fit_armor` exists but uses simple vertex shrink-wrapping -- no topology-aware deformation lattice or surface transfer for different body types. Real AAA studios use projection-based fitting. |
| 5 | **Limited procedural furniture/props** | MEDIUM | Riggable objects cover doors/chests/chandeliers but no tables, chairs, beds, shelves, barrels, crates, pottery, food items. These are core interior decoration assets. Settlement generation depends on Tripo AI for props which requires network access. |
| 6 | **No vertex group auto-painting by topology** | LOW | Weight painting exists but no automatic vertex group assignment based on topology analysis (e.g., auto-detect fingers, toes, spine segments from mesh shape). |

---

## 2. Material/Shader System

### What Exists (STRONG)
- **Blender side:**
  - Basic material CRUD (create, assign, modify, list)
  - 45+ procedural material presets (stone, wood, metal, organic, terrain, fabric, special) with full node graphs
  - 22 smart material presets with 5-layer architecture (base, edge wear, cavity dirt, height masks, macro variation)
  - Trim sheet generation
  - Macro variation for tiling breakup
  - Terrain biome materials with multi-layer splatmaps
  - Dark fantasy palette enforcement (saturation cap, value range)
- **Unity side:**
  - Arbitrary HLSL/ShaderLab shader generation (SHDR-01)
  - URP ScriptableRendererFeature generation (SHDR-02)
  - SSS skin shader (CHAR-08)
  - Parallax eye shader (CHAR-08)
  - Micro-detail normal compositing
  - 7 VFX shaders: corruption, dissolve, force field, water, foliage, outline, damage overlay
  - Master material library generation (AAA-04)
  - UI material shaders

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 7 | **No Shader Graph visual template system** | HIGH | `unity_shader` generates raw HLSL/ShaderLab code. No Shader Graph asset (.shadergraph) generation. Most Unity URP workflows use Shader Graph, not hand-written shaders. AAA studios use Shader Graph for artist-editable materials. |
| 8 | **No material instancing/variant system in Blender** | MEDIUM | Procedural materials are created per-object. No material variant system (e.g., "damaged_stone" derived from "stone" with parameter overrides). Every material is a full copy. |
| 9 | **No tessellation/displacement shader** | LOW | Water shader exists but no tessellation-based displacement for terrain close-ups or ocean surfaces in Unity URP. |
| 10 | **No Blender-to-Unity material transfer** | HIGH | Materials created in Blender procedurally do not automatically translate to Unity materials on export. The FBX export embeds basic PBR values but procedural node graphs are lost. Must bake to textures first, but no automated "bake all procedural materials to texture maps for export" workflow. |

---

## 3. Texture System

### What Exists (STRONG)
- PBR material creation with texture maps (albedo, metallic, roughness, normal, AO, emission, alpha, height, subsurface)
- Texture baking (high-to-low poly, self-bake)
- Texture validation (resolution, format, colorspace, UV coverage)
- Wear map generation
- HSV adjustment, seam blending, UV masking
- ESRGAN upscaling (4x with Real-ESRGAN)
- Tileable texture generation
- Delighting (remove baked lighting from albedo)
- Palette validation (dark fantasy rules)
- Channel packing
- ID map baking, thickness map baking, AO baking, curvature baking
- Detail texture overlays
- Bake procedural materials to image textures
- Inpainting via AI

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 11 | **No texture atlas generation in Blender** | MEDIUM | Trim sheet exists for architecture but no general-purpose texture atlas packer that combines multiple object textures into shared atlas sheets (critical for draw call reduction on prop-heavy scenes). Unity has sprite atlas but not for 3D mesh textures. |
| 12 | **No automatic texture size optimization** | LOW | Textures are created at fixed sizes (1024, 2048). No automatic sizing based on object screen-space footprint (e.g., small props should get 256-512, hero assets 2048-4096). |

---

## 4. UV System

### What Exists (STRONG)
- UV analysis with quality metrics (stretch, overlap, density, islands, seams)
- xatlas unwrapping (high quality)
- Blender native unwrap (smart_project, angle_based)
- UV island packing
- Lightmap UV generation (UV2 for Unity)
- Texel density equalization
- UV layout export as PNG
- Active UV layer management
- UDIM support (udim_support.py handler exists)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 13 | **No UV seam placement intelligence** | LOW | xatlas handles seam placement automatically but no tool for manual seam marking based on hard edges/material boundaries. `unwrap_blender` with `smart_project` uses angle-based seams but doesn't account for visual importance. |

---

## 5. VFX System

### What Exists (STRONG)
- **19 Unity VFX actions** covering:
  - Particle VFX creation (VFX-01)
  - Per-brand damage VFX (VFX-02)
  - Environmental VFX: dust, fireflies, snow, rain, ash (VFX-03)
  - Weapon/projectile trails (VFX-04)
  - Character auras/buffs (VFX-05)
  - 7 shaders: corruption, dissolve, force field, water, foliage, outline, damage overlay
  - Post-processing: bloom, color grading, vignette, AO, DOF (VFX-08)
  - Screen effects: camera shake, damage vignette (VFX-09)
  - Ability VFX + animation integration (VFX-10)
  - Flipbook texture sheet generation (VFX3-01)
  - VFX Graph composition (VFX3-02)
  - Projectile VFX chains: spawn -> travel -> impact -> aftermath (VFX3-03)
  - AoE VFX (VFX3-04)
  - Status effect VFX per brand (VFX3-05)
  - Volumetric fog, god rays, heat distortion, caustics (VFX3-06)
  - Directional hit VFX (VFX3-07)
  - Boss phase transition VFX (VFX3-08)
  - Decal system with pool management (VFX-11)
- **Blender side:**
  - Particle systems (emitter, hair) with physics config
  - Hair grooming operations

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 14 | **No VFX Graph asset file generation** | HIGH | `compose_vfx_graph` generates C# scripts that configure VFX Graph parameters, but does NOT create `.vfx` asset files. The actual VFX Graph must be manually created in Unity Editor first. A true VFX pipeline would programmatically create Visual Effect Graph assets. |
| 15 | **No real-time VFX preview/iteration** | MEDIUM | VFX scripts are generated, compiled, and executed as a two-step process. No way to preview VFX results from MCP -- must rely on Unity Editor play mode. |
| 16 | **No LOD for VFX** | LOW | Particle systems don't automatically reduce particle count or disable expensive features at distance. Performance profiling exists but no VFX-specific LOD system. |

---

## 6. Animation System

### What Exists (STRONG)
- **12 Blender animation actions:**
  - Procedural walk/run cycles for 5 gait types (biped, quadruped, hexapod, arachnid, serpent)
  - Fly/hover animation
  - Idle animation (breathing, weight shift, secondary motion)
  - 8 attack types with anticipation-strike-recovery
  - Death, directional hit, spawn reactions
  - Custom animation from text description
  - Animation preview (contact sheet)
  - Secondary motion physics bake
  - Root motion extraction + animation events
  - Mixamo animation retargeting
  - AI motion generation (API + procedural fallback)
  - Batch export as Unity clips
- **Unity side:**
  - Animator controller creation with states/transitions
  - Avatar configuration (Humanoid/Generic bone mapping)
  - Animation Rigging: TwoBoneIK, MultiAim constraints
  - Blend trees (directional/speed)
  - Additive animation layers
  - Timeline setup
  - Animation clip editing
  - Avatar masks

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 17 | **No animation blending/layering in Blender** | MEDIUM | Blender animation creates single actions. No NLA strip composition or blending between animations (e.g., attack while moving). Blending happens Unity-side via Animator Controller but no tool to preview or compose in Blender. |
| 18 | **No facial animation/lipsync** | HIGH | Facial rig setup exists (RIG-04 with expressions) and shape keys exist (RIG-13), but no lipsync/phoneme mapping, no facial motion capture retargeting, no procedural dialogue animation. Critical for cutscenes and NPC interaction. |
| 19 | **No animation curve editor** | LOW | Animations are generated procedurally with keyframes at fixed interpolation. No tool to edit individual curve tangents, adjust timing, or fine-tune motion quality post-generation. |
| 20 | **No inverse kinematics animation creation** | MEDIUM | IK is set up for rigging (RIG-05) but animation generation doesn't use IK goals -- it's all FK keyframes. No foot-IK for ground contact, no hand-IK for weapon wielding. |
| 21 | **No State Machine Behaviour scripting** | LOW | Animator controllers have states/transitions but no tool to attach StateMachineBehaviour scripts to states (for triggering events on enter/exit/update). |

---

## 7. Rigging System

### What Exists (STRONG)
- Mesh analysis for rig recommendation (RIG-01)
- 8 creature rig templates (humanoid, quadruped, dragon, insect, floating, serpent, amorphous) via Rigify
- Custom rig builder from limb library (RIG-03)
- Facial rig with expressions (RIG-04)
- IK chain setup (RIG-05)
- Spring/jiggle bone system (RIG-06)
- Auto weight painting (RIG-07)
- Deformation testing at 8 poses (RIG-08)
- Rig validation with grading (RIG-09)
- Weight mirror/normalize/smooth (RIG-10)
- Ragdoll auto-setup (RIG-11)
- Rig retargeting (RIG-12)
- Shape keys for expressions/damage (RIG-13)
- Unity Humanoid avatar mapping (SCENE-06)
- Bone editing and listing (P2-A5)
- Environment object rigging (doors, chains, flags, etc.)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 22 | **No rig-to-Unity bone naming convention enforcement** | MEDIUM | Rigs use Rigify naming. Unity Humanoid requires specific bone names. `configure_avatar` exists for mapping but no automated rename-on-export to match Unity conventions (LeftUpperArm, RightHand, etc.). |
| 23 | **No muscle/constraint system export** | LOW | Spring bones and IK constraints set up in Blender don't export to Unity FBX. Must be recreated Unity-side. Animation Rigging (SCENE-07) handles this but there's no bridge. |

---

## 8. Audio System

### What Exists (STRONG)
- **20 Unity audio actions:**
  - AI-generated SFX from text (AUD-01) via ElevenLabs
  - Music loop generation (AUD-02)
  - Voice synthesis (AUD-03) via ElevenLabs
  - Biome ambient soundscapes (AUD-04)
  - Surface-material footstep mapping (AUD-05)
  - Adaptive music system (AUD-06)
  - Reverb zones for caves/outdoor/indoor (AUD-07)
  - Unity Audio Mixer with groups (AUD-08)
  - Audio pooling, priority, ducking (AUD-09)
  - Animation event SFX (AUD-10)
  - 3D spatial audio with occlusion (AUDM-01)
  - Layered sound design (AUDM-02)
  - Audio event chains (AUDM-03)
  - Dynamic music with horizontal re-sequencing + vertical layering (AUDM-04)
  - Room-based sound propagation via portals (AUDM-05)
  - Distance-based audio LOD (AUDM-06)
  - Dialogue/VO playback pipeline (AUDM-07)
  - Procedural foley (AUDM-08)
  - UI sound system (AU-01)
  - Physics material-aware impact sounds (AU-02)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 24 | **AI audio generation depends on external API** | MEDIUM | ElevenLabs API required for SFX/music/voice generation. No fallback for offline use. If API is unavailable or credits run out, audio generation fails entirely. No local audio generation capability. |
| 25 | **No FMOD/Wwise integration** | MEDIUM | Audio system uses Unity's built-in Audio system. AAA studios use FMOD or Wwise for middleware-level audio. The toolkit's custom middleware scripts (spatial, portal, dynamic music) replicate some features but aren't as mature. |
| 26 | **No audio file management/organization** | LOW | Generated audio files are written to disk but no catalog, tagging, or library management. Assets accumulate without organization. |

---

## 9. AI/Gameplay System

### What Exists (STRONG)
- FSM-based mob AI controller (MOB-01)
- Detection + threat + leash aggro system (MOB-02)
- Waypoint patrol routes (MOB-03)
- Spawn points + wave system (MOB-04)
- Behavior tree scaffolding (MOB-05)
- Combat ability prefab data + executor (MOB-06)
- Projectile system with trajectory + trail + impact (MOB-07)
- Encounter system with wave SO (AID-01)
- AI Director with AnimationCurve difficulty (AID-02)
- Monte Carlo encounter simulator (AID-03)
- Multi-phase boss AI FSM (VB-10)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 27 | **No trigger volume/event zone system** | HIGH | No dedicated tool for creating invisible trigger areas that fire gameplay events (enter zone -> spawn enemies, play cutscene, change music). `unity_world` has some zone concepts but no general-purpose trigger volume tool. Interactables (RPG-03) handle proximity but not area triggers. |
| 28 | **No stealth/detection system** | MEDIUM | Aggro system uses simple range-based detection. No line-of-sight, noise level, light level, or cover system for stealth gameplay. VeilBreakers is an action RPG so this is lower priority but still a gap for varied gameplay. |
| 29 | **No companion/ally AI** | MEDIUM | All AI is enemy-focused. No allied NPC AI for companions, quest givers that follow, or pet systems. |
| 30 | **No crowd/civilian AI** | MEDIUM | No ambient NPC population system for towns. NPCs can be placed (RPG-11) but have no behavior (walking, talking, daily routines). |
| 31 | **Behavior tree is scaffolding only** | HIGH | `create_behavior_tree` generates a ScriptableObject-based BT framework but the node implementations are stubs. No actual selector/sequence/decorator/action node implementations. Must be hand-coded for each enemy type. |

---

## 10. UI/UX System

### What Exists (STRONG)
- **Unity UI (14 actions):**
  - UXML + USS screen generation from description (UI-05)
  - Layout validation (UI-02)
  - Responsive testing at 5 resolutions (UI-03)
  - WCAG AA contrast validation (UI-06)
  - Visual regression detection (UI-07)
  - Procedural dark fantasy frames (UIPOL-01)
  - 3D icon render pipeline (UIPOL-02)
  - Context-sensitive cursors (UIPOL-03)
  - Rich tooltips with comparison (UIPOL-04)
  - Radial ability/item wheel (UIPOL-05)
  - Notification system (UIPOL-06)
  - Loading screen (UIPOL-07)
  - UI material shaders (UIPOL-08)
  - Combat HUD (UI-08)
- **Unity UX (12 actions):**
  - Minimap (UIX-01)
  - Tutorial system (UIX-02)
  - Damage numbers (UIX-03)
  - Interaction prompts (UIX-04)
  - PrimeTween sequences (SHDR-04)
  - TextMeshPro setup (PIPE-10)
  - Accessibility options (ACC-01)
  - Character select screen (VB-09)
  - World map (RPG-08)
  - Rarity VFX for items (EQUIP-07)
  - Corruption VFX overlay (EQUIP-08)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 32 | **No inventory UI implementation** | HIGH | `create_inventory_system` (GAME-02) generates backend logic (ScriptableObject, grid, equipment slots) and UXML/USS layout, but the visual inventory drag-and-drop, item stacking, grid snapping, and equipment paper doll are template code -- requires significant manual implementation to be functional. |
| 33 | **No dialogue UI implementation** | MEDIUM | Dialogue system (GAME-03) creates backend ScriptableObjects for dialogue trees but the actual dialogue box UI with typewriter effect, portrait display, choice buttons is not generated. |
| 34 | **No pause menu / game over screen** | LOW | Settings menu exists (GAME-08) but no pause overlay, game over screen, or victory screen templates. |
| 35 | **No controller/gamepad UI navigation** | MEDIUM | UI screens are generated but no EventSystem controller navigation setup, no UI focus management, no gamepad cursor simulation. Input system (GAME-07) handles input mapping but not UI navigation. |

---

## 11. World/Environment System

### What Exists (STRONG)
- **Blender environment (12 actions):**
  - Terrain generation (multi-type: mountains, hills, plains, etc.)
  - Terrain painting with biome rules
  - River carving with erosion
  - Road generation with grading
  - Water plane creation
  - Heightmap export
  - Vegetation scattering (per-biome with L-system trees)
  - Prop scattering
  - Breakable prop creation
  - Storytelling props (AAA-05)
  - Terrain sculpting
  - Multi-biome world generation
- **Blender worldbuilding (17 actions):**
  - Procedural dungeons, caves, towns, buildings, castles, ruins
  - Interior generation
  - Modular kit creation
  - Location generation (WORLD-01)
  - Boss arenas (WORLD-03)
  - World graph with connections (WORLD-04)
  - Linked interiors (WORLD-05)
  - Multi-floor dungeons (WORLD-06)
  - Corruption overrun variants (WORLD-09)
  - Easter eggs/secrets (WORLD-10)
  - Hearthvale (full settlement)
  - Settlement prop prefetching
- **Unity world (22 actions):**
  - Scene creation, transitions, probes, occlusion
  - Environment setup (skybox, ambient, GI)
  - Terrain detail painting
  - Tilemap (2D)
  - Time of day presets
  - Fast travel, puzzles, traps, spatial loot
  - Weather system, day/night cycle
  - NPC placement, dungeon lighting
  - Terrain-building blend
  - WFC tile-based dungeon generation
  - Interior/exterior streaming
  - Door/gate/lock system
  - Map streaming via Addressables
- **Advanced terrain:**
  - Erosion (thermal, hydraulic), flow maps
  - Canyon, waterfall, cliff face, swamp terrain generators
  - Coastline generation
  - Road network computation
  - Terrain spline deform, layers, stamps, snap objects
  - Atmospheric volume placement (fog, mist, embers)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 36 | **No terrain LOD / streaming in Blender** | MEDIUM | Large terrains are single meshes. No terrain chunking for streaming. `terrain_chunking.py` exists as a handler file but terrain output is monolithic. Unity-side streaming (WORLD-12) exists but Blender-side terrain must be pre-chunked for it. |
| 37 | **No procedural cave/mine interior decoration** | LOW | Cave generation creates geometry but interiors are bare. No stalactite/stalagmite placement, crystal formation, mineral veins, or mine support beam generation. |
| 38 | **No underwater environment** | MEDIUM | Water plane creation exists but no underwater environment system -- no underwater terrain, coral, kelp, fish schools, underwater lighting/fog, swimming mechanics integration. |
| 39 | **Settlement prop generation requires Tripo API** | HIGH | Town/settlement generation depends on Tripo AI for creating props (lanterns, market stalls, benches, etc.). Without network access or Tripo credits, settlements have no props. No offline fallback for common prop types. |

---

## 12. Pipeline/Export System

### What Exists (STRONG)
- FBX export with Unity-optimized settings (axis conversion, scale, leaf bones disabled)
- glTF/GLB export
- Batch export for animations
- Game-readiness check before export
- LOD generation (silhouette-preserving, per-asset-type presets)
- Asset pipeline orchestration (generate_3d, compose_map, compose_interior)
- Full production pipeline (repair -> UV -> texture -> rig -> animate -> export)
- Map package generation
- AAA visual verification
- Performance budget checks
- Asset catalog with tagging
- Unity FBX import configuration
- Material remapping on import
- Asset postprocessor with folder rules
- Git LFS configuration
- Tripo AI 3D generation integration

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 40 | **No automated Blender-to-Unity round-trip** | CRITICAL | The pipeline is linear: create in Blender -> export -> import in Unity. No automatic re-export when Blender file changes. No linked library system. Must manually trigger export, then import. AAA studios use live links (e.g., FBX auto-reimport on change). |
| 41 | **No texture export with FBX** | HIGH | FBX export sends mesh + armature + animation but texture files must be separately managed. No automatic texture copy/embed alongside FBX export. Must manually ensure texture paths match Unity import expectations. |
| 42 | **No prefab auto-generation from imported FBX** | HIGH | After FBX import into Unity, prefab must be manually set up. `unity_prefab` can create prefabs but doesn't auto-detect imported FBX and set up: (1) material assignment, (2) collider, (3) LOD Group, (4) layer assignment, (5) NavMesh static flags. The `atomic_import` action handles some of this but requires explicit configuration. |
| 43 | **No asset naming convention enforcement** | MEDIUM | No automatic naming validation (e.g., SM_RockWall_01, T_RockWall_Albedo, M_RockWall). Assets get ad-hoc names. No rename-on-export. |
| 44 | **No Blender file management** | MEDIUM | Blender operates on whatever is open. No project-level .blend file management, no automatic save, no file organization. All Blender state is ephemeral within a session. |

---

## 13. Performance/Quality System

### What Exists (STRONG)
- **Blender side:**
  - Topology analysis with grading
  - Game-readiness validation
  - LOD generation
  - AAA visual verification with map comparison
  - Screenshot regression testing
  - Performance budget checks
  - Quality checks (beauty scene, dark fantasy lighting)
- **Unity side:**
  - Scene profiler (frame time, draw calls, memory) (PERF-01)
  - LOD Group setup (PERF-02)
  - Lightmap baking (PERF-03)
  - Asset audit (oversized/unused/uncompressed) (PERF-04)
  - Build automation + size report (PERF-05)
  - Poly budget check per asset type (AAA-02)
  - Master material library (AAA-04)
  - Texture quality validation (AAA-06)
  - Combined AAA audit
  - Memory leak detection (QA-04)
  - Code static analysis (QA-05)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 45 | **No GPU profiling** | MEDIUM | Scene profiler checks frame time and draw calls but no GPU-specific profiling (shader complexity, fill rate, overdraw visualization, GPU memory bandwidth). |
| 46 | **No automatic optimization suggestions** | LOW | Performance tools report metrics but don't suggest specific fixes (e.g., "merge these 12 objects to reduce draw calls", "compress this texture from 4096 to 2048"). |
| 47 | **No runtime performance monitoring** | MEDIUM | Profiling is editor-time only. No FPS counter, memory tracker, or performance overlay for play-mode testing. |

---

## 14. Camera/Cinematics System

### What Exists (STRONG)
- Cinemachine virtual camera setup (CAM-01)
- State-driven cameras (CAM-01)
- Camera shake with impulse (CAM-04)
- Camera blend configuration (CAM-04)
- Timeline creation with tracks (CAM-02)
- Cutscene setup with PlayableDirector (CAM-03)
- Lock-on targeting camera (CAM-05)
- Timeline-based cinematic sequences with shot composition (ANIM3-07)
- Video player setup (MEDIA-01)
- Animation clip editing (ANIMA-01)
- Animator modification (ANIMA-02)
- Avatar mask creation (ANIMA-03)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 48 | **No in-engine cutscene authoring** | MEDIUM | Cutscenes use Timeline which must be manually composed in Unity. `cinematic_sequence` generates C# scripts that create Timeline assets programmatically, but complex multi-actor scenes with dialogue, camera switching, and VFX triggers require manual Timeline editing. |
| 49 | **No photo mode** | LOW | No player-accessible screenshot/photo mode with camera controls, filters, and depth of field adjustment. |

---

## 15. Code/Data System

### What Exists (STRONG)
- C# class generation (any type: MonoBehaviour, ScriptableObject, static, struct, enum)
- Script modification (add usings, fields, properties, methods, attributes)
- Editor tools: EditorWindow, PropertyDrawer, custom Inspector, SceneView overlay
- Test class generation
- Design patterns: service locator, object pool, singleton, state machine, event channel
- ScriptableObject definition + asset creation (DATA-02)
- JSON config validation + typed loader (DATA-01)
- Localization infrastructure (DATA-03)
- Data authoring EditorWindows (DATA-04)
- Assembly Definition creation
- Unity Preset creation/application
- Asset reference scanning

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 50 | **No automated test generation from game systems** | LOW | Test class scaffolding exists but doesn't auto-generate tests for generated game systems (e.g., health system -> test damage/heal/death, inventory -> test add/remove/stack). Tests are empty shells. |
| 51 | **No ECS/DOTS support** | LOW | All generated code uses classic MonoBehaviour/ScriptableObject patterns. No Entity Component System support for high-performance gameplay code. Acceptable for current Unity ecosystem but may become important. |

---

## 16. Build/Deploy System

### What Exists (STRONG)
- Multi-platform builds (BUILD-01)
- Addressables configuration (BUILD-02)
- CI/CD pipeline generation for GitHub Actions and GitLab CI (BUILD-03)
- Version management with auto-increment (BUILD-04)
- Platform-specific configuration (BUILD-05)
- Shader stripping (SHDR-03)
- Store metadata generation (ACC-02)
- Compile recovery (PROD-01)
- Asset/class name conflict detection (PROD-02)
- Multi-tool pipeline orchestration (PROD-03)
- Art style consistency validation (PROD-04)
- Post-build smoke test (PROD-05)
- Code reviewer deployment (PROD-06)

### GAPS

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 52 | **No console platform support** | LOW | Build targets are PC/Android/iOS/WebGL. No PlayStation, Xbox, or Nintendo Switch configuration. Requires platform-specific SDKs anyway but templates don't exist. |
| 53 | **No analytics/telemetry dashboard** | LOW | Analytics setup exists (QA-07) but no dashboard or data visualization for collected metrics. |

---

## 17. Cross-System Integration Gaps

These gaps exist between systems rather than within any single system.

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 54 | **No end-to-end character pipeline** | CRITICAL | Creating a game-ready character requires: model -> rig -> weight paint -> animate -> texture -> export -> Unity import -> prefab setup -> animator controller -> ability system -> VFX attachment. No single command orchestrates this. `full_pipeline` in asset_pipeline covers mesh processing but stops at export. Unity-side setup is entirely separate. |
| 55 | **No weapon/equipment attachment system end-to-end** | HIGH | `equipment_attachment` creates Unity MonoBehaviour for bone socket attachment but doesn't connect to Blender-side weapon generation + export. Must manually bridge: generate weapon in Blender -> export FBX -> import in Unity -> attach to character bone socket. |
| 56 | **No scene composition tool** | CRITICAL | No way to take Blender worldbuilding output (dungeon/town/map) and automatically set up a Unity scene with: imported meshes + lighting + navigation + spawn points + audio zones + VFX volumes + trigger zones. Each system must be invoked separately and manually connected. |
| 57 | **No multiplayer networking** | CRITICAL | Zero networking tools. No Netcode for GameObjects support, no Mirror/Fish-Net templates, no lobby system, no server authority, no state synchronization, no lag compensation. Any multiplayer features must be built entirely from scratch. |
| 58 | **No save/load integration testing** | HIGH | Save system exists (GAME-01) but no way to verify that all game systems properly serialize/deserialize. Inventory, quests, character progression, world state -- all generated independently with no guaranteed compatibility. |
| 59 | **No debug/cheat console** | MEDIUM | No in-game developer console for runtime debugging, variable modification, teleportation, spawning, etc. Essential during development iteration. |
| 60 | **No input rebinding UI** | MEDIUM | Input system (GAME-07) supports rebinding but no runtime UI for the player to view and change key bindings. Settings menu template mentions it but implementation is skeleton. |
| 61 | **No Blender addon auto-install/update** | HIGH | Blender addon must be manually installed and the TCP server manually started. No automatic installation from MCP toolkit, no version checking, no auto-reconnection when Blender restarts. |
| 62 | **No Unity bridge auto-install** | HIGH | Unity bridge (VBBridge) requires manual setup: install package, compile scripts, ensure TCP server runs. No bootstrap command that sets up a fresh Unity project for MCP toolkit use. |
| 63 | **No cross-tool state persistence** | CRITICAL | Blender and Unity operate independently. No shared project state. If Blender generates a dungeon, Unity has no knowledge of it until export+import. No project database tracking what assets exist, their status, or their relationships. Asset catalog exists but is Blender-only. |
| 64 | **No terrain continuity Blender -> Unity** | HIGH | Blender terrain (heightmap mesh) must be exported and reconstructed as Unity Terrain. No heightmap transfer tool. `setup_terrain` in Unity takes a heightmap image path but no tool creates that image from Blender terrain. `export_heightmap` exists in Blender but the Unity import path isn't connected. |
| 65 | **No physics material consistency** | LOW | Blender physics (rigid body, cloth, soft body) and Unity physics (collision, joints) are completely separate systems with no parameter transfer. |
| 66 | **No localization workflow for generated content** | LOW | Localization infrastructure exists (DATA-03) but generated UI, dialogue, quest text, item descriptions are all in English with no localization key system. All strings are hardcoded. |
| 67 | **No version control for generated assets** | MEDIUM | Git LFS config exists but no automatic commit/push workflow for generated Blender/Unity assets. Assets accumulate in working directory without version control discipline. |

---

## Priority Summary

### CRITICAL (8) -- Blocks Game Development
| # | Gap | System |
|---|-----|--------|
| 40 | No automated Blender-to-Unity round-trip | Pipeline |
| 54 | No end-to-end character pipeline | Cross-System |
| 56 | No scene composition tool | Cross-System |
| 57 | No multiplayer networking | Cross-System |
| 63 | No cross-tool state persistence | Cross-System |

Note: #57 (multiplayer) is only CRITICAL if the game requires multiplayer. For a single-player action RPG it drops to LOW.

### HIGH (19) -- Major Workaround Needed
| # | Gap | System |
|---|-----|--------|
| 1 | No Blender-side collision mesh generation | Modeling |
| 4 | No procedural armor fitting to arbitrary body shapes | Modeling |
| 7 | No Shader Graph visual template system | Materials |
| 10 | No Blender-to-Unity material transfer automation | Materials |
| 14 | No VFX Graph asset file generation | VFX |
| 18 | No facial animation/lipsync | Animation |
| 27 | No trigger volume/event zone system | Gameplay |
| 31 | Behavior tree nodes are stubs | Gameplay |
| 32 | No inventory UI implementation (just template) | UI |
| 39 | Settlement prop generation requires Tripo API | World |
| 41 | No texture export with FBX | Pipeline |
| 42 | No prefab auto-generation from imported FBX | Pipeline |
| 55 | No weapon/equipment attachment system end-to-end | Cross-System |
| 58 | No save/load integration testing | Cross-System |
| 61 | No Blender addon auto-install/update | Cross-System |
| 62 | No Unity bridge auto-install | Cross-System |
| 64 | No terrain continuity Blender -> Unity | Cross-System |

### MEDIUM (24) -- Nice to Have
| # | Gap | System |
|---|-----|--------|
| 2 | No internal face cleanup after booleans | Modeling |
| 3 | No NURBS modeling | Modeling |
| 5 | Limited procedural furniture/props | Modeling |
| 8 | No material variant system in Blender | Materials |
| 11 | No texture atlas generation in Blender | Textures |
| 15 | No real-time VFX preview | VFX |
| 17 | No animation blending in Blender | Animation |
| 20 | No IK-based animation creation | Animation |
| 22 | No rig bone naming convention enforcement | Rigging |
| 24 | AI audio generation depends on external API | Audio |
| 25 | No FMOD/Wwise integration | Audio |
| 28 | No stealth/detection system | Gameplay |
| 29 | No companion/ally AI | Gameplay |
| 30 | No crowd/civilian AI | Gameplay |
| 33 | No dialogue UI implementation | UI |
| 35 | No controller/gamepad UI navigation | UI |
| 36 | No terrain LOD/streaming in Blender | World |
| 38 | No underwater environment | World |
| 43 | No asset naming convention enforcement | Pipeline |
| 44 | No Blender file management | Pipeline |
| 45 | No GPU profiling | Performance |
| 47 | No runtime performance monitoring | Performance |
| 48 | No in-engine cutscene authoring | Cinematics |
| 59 | No debug/cheat console | Cross-System |
| 60 | No input rebinding UI | Cross-System |
| 67 | No version control for generated assets | Cross-System |

### LOW (16) -- Polish Items
| # | Gap | System |
|---|-----|--------|
| 6 | No auto vertex group painting by topology | Modeling |
| 9 | No tessellation/displacement shader | Materials |
| 12 | No automatic texture size optimization | Textures |
| 13 | No UV seam placement intelligence | UV |
| 16 | No LOD for VFX | VFX |
| 19 | No animation curve editor | Animation |
| 21 | No State Machine Behaviour scripting | Animation |
| 23 | No constraint system export | Rigging |
| 26 | No audio file management | Audio |
| 34 | No pause menu / game over screen | UI |
| 37 | No cave interior decoration | World |
| 46 | No auto optimization suggestions | Performance |
| 49 | No photo mode | Cinematics |
| 50 | No auto-generated tests from game systems | Code |
| 51 | No ECS/DOTS support | Code |
| 52 | No console platform support | Build |
| 53 | No analytics dashboard | Build |
| 65 | No physics material consistency | Cross-System |
| 66 | No localization workflow for generated content | Cross-System |

---

## Recommendations for Next Development Phase

### Tier 1: Ship-Blocking (do first)
1. **Scene composition tool** (#56) -- Take Blender output and auto-set-up Unity scene
2. **End-to-end character pipeline** (#54) -- Single command: model -> game-ready in Unity
3. **Cross-tool state persistence** (#63) -- Shared project database between Blender/Unity
4. **Blender-to-Unity auto round-trip** (#40) -- File watcher + auto re-export/reimport

### Tier 2: Quality-of-Life (do second)
5. **Blender/Unity auto-install** (#61, #62) -- Bootstrap commands for fresh setups
6. **Facial animation/lipsync** (#18) -- Critical for any story-driven game
7. **Trigger volumes** (#27) -- Core gameplay mechanic
8. **Behavior tree nodes** (#31) -- Complete the AI framework
9. **Shader Graph templates** (#7) -- Standard Unity material workflow

### Tier 3: Content Completeness (do third)
10. **Inventory UI polish** (#32) -- Make generated inventory actually functional
11. **Offline prop generation fallback** (#39) -- Basic shapes when Tripo unavailable
12. **Texture/material export pipeline** (#10, #41) -- Complete asset export chain
13. **Terrain Blender->Unity pipeline** (#64) -- Seamless heightmap transfer

### Tier 4: Polish (as time allows)
14-67. Remaining MEDIUM and LOW items in priority order.
