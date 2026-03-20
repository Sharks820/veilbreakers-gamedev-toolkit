# Requirements: VeilBreakers GameDev Toolkit

**Defined:** 2026-03-18
**Updated:** 2026-03-19 (v2.0 milestone)
**Core Value:** Every tool returns structured validation data and visual proof so Claude never works blind

## v1 Requirements (COMPLETE)

All v1 requirements delivered in 8 phases. See MILESTONES.md for details.
128 requirements across: ARCH (8), MESH (8), UV (5), TEX (10), RIG (13), ANIM (12), ENV (16), VFX (10), AUD (10), UI (7), SCENE (7), MOB (7), PERF (5), PIPE (7), CONC (3).

## v2 Requirements

Requirements for v2.0 -- closing every gap for complete Unity game development coverage.

### Unity Editor Control

- [ ] **EDIT-01**: Claude can create, modify, and delete Prefabs programmatically (including nested prefabs and prefab variants)
- [ ] **EDIT-02**: Claude can add, remove, and configure any Component on any GameObject (Rigidbody, Collider, AudioSource, Light, custom MonoBehaviours)
- [ ] **EDIT-03**: Claude can manipulate scene hierarchy (create empties, rename, reparent, enable/disable, set layer/tag)
- [ ] **EDIT-04**: Claude can configure physics layers, layer collision matrix, and physics materials (friction, bounciness)
- [ ] **EDIT-05**: Claude can manage Player Settings (company name, product name, icon, splash, scripting backend, API compat, color space)
- [ ] **EDIT-06**: Claude can manage Build Settings (add/remove/reorder scenes, switch platform, set scripting defines)
- [ ] **EDIT-07**: Claude can configure Quality Settings (shadow distance/resolution, texture quality, AA, VSync, LOD bias)
- [ ] **EDIT-08**: Claude can install, remove, and update Unity packages via Package Manager (manifest.json + UPM)
- [ ] **EDIT-09**: Claude can create and manage custom Tags, Sorting Layers, and Physics Layers
- [ ] **EDIT-10**: Claude can perform asset operations (move, rename, delete, duplicate, create folders) while preserving .meta/GUID integrity
- [ ] **EDIT-11**: Claude can configure Time settings (fixed timestep), Graphics settings (render pipeline asset), and Editor preferences
- [ ] **EDIT-12**: Claude can configure FBX ModelImporter settings on import (scale, mesh compression, normals, animation compression, rig)
- [ ] **EDIT-13**: Claude can configure TextureImporter settings (max size, compression per platform, sRGB/linear, sprite mode, mip maps)
- [ ] **EDIT-14**: Claude can remap materials on FBX import to existing project materials or auto-generate from imported textures
- [ ] **EDIT-15**: Claude can create and manage Assembly Definition files (.asmdef) for compile time optimization

### C# Programming

- [ ] **CODE-01**: Claude can generate arbitrary C# MonoBehaviours, plain classes, interfaces, enums, structs, and static utilities (not just domain templates)
- [ ] **CODE-02**: Claude can modify existing C# scripts (add methods, fields, properties, attributes, using statements)
- [ ] **CODE-03**: Claude can generate custom Inspector drawers, PropertyDrawers, EditorWindows, and SceneView overlays
- [ ] **CODE-04**: Claude can create EditMode and PlayMode test assemblies, fixtures, and test methods (NUnit / Unity Test Framework)
- [ ] **CODE-05**: Claude can run Unity tests and collect pass/fail results through MCP
- [ ] **CODE-06**: Claude can scaffold dependency injection patterns (service locator, event bus, SO event channels)
- [ ] **CODE-07**: Claude can generate generic object pooling systems (projectiles, enemies, VFX, UI elements)
- [ ] **CODE-08**: Claude can generate singleton patterns (persistent MonoBehaviour, non-MB singletons)
- [ ] **CODE-09**: Claude can generate generic reusable state machine framework usable by multiple systems
- [ ] **CODE-10**: Claude can generate observer/event system with ScriptableObject event channels

### Game Systems

- [ ] **GAME-01**: Claude can generate a complete save/load system (JSON/binary serialization, save slots, data migration)
- [ ] **GAME-02**: Claude can generate inventory system (item database SO, UI slots, drag-and-drop, equipment, storage)
- [ ] **GAME-03**: Claude can generate dialogue system (branching trees, dialogue UI, NPC interaction, YarnSpinner-compatible)
- [ ] **GAME-04**: Claude can generate quest system (objectives, tracking, quest givers, quest log UI, completion rewards)
- [ ] **GAME-05**: Claude can generate health/damage system (HP component, damage numbers, death handling, respawn)
- [ ] **GAME-06**: Claude can generate character controller (first-person and third-person movement, camera follow)
- [ ] **GAME-07**: Claude can configure Input System (Input Action assets, action maps, control schemes, rebinding)
- [ ] **GAME-08**: Claude can generate game settings menu (graphics quality, audio volume, keybindings, accessibility)
- [ ] **GAME-09**: Claude can generate loot table system (weighted random, rarity tiers, drop conditions)
- [ ] **GAME-10**: Claude can generate crafting/recipe system (ingredient requirements, crafting stations, unlock progression)
- [ ] **GAME-11**: Claude can generate skill tree / talent system (node graph, unlock dependencies, point allocation)
- [ ] **GAME-12**: Claude can generate combat balancing tools (DPS calculator, encounter simulator, stat curve editor)

### Camera & Cinematics

- [ ] **CAM-01**: Claude can create and configure Cinemachine virtual cameras (FreeLook, follow, state-driven, blending)
- [ ] **CAM-02**: Claude can create Timeline assets with animation, audio, activation, and Cinemachine tracks
- [ ] **CAM-03**: Claude can set up cutscene sequences using Playable Director with Timeline
- [ ] **CAM-04**: Claude can configure camera shake, zoom, and transition effects

### Scene Management

- [ ] **SCNE-01**: Claude can create new Unity scenes and configure scene loading (single, additive, async)
- [ ] **SCNE-02**: Claude can generate scene transition system (loading screens, fade transitions, bootstrapper)
- [ ] **SCNE-03**: Claude can set up reflection probes, light probes, and probe groups
- [ ] **SCNE-04**: Claude can configure occlusion culling (mark static occluders/occludees, bake data)
- [ ] **SCNE-05**: Claude can set up HDR skybox, environment reflections, and Global Illumination
- [ ] **SCNE-06**: Claude can generate terrain detail painting (grass, detail meshes on Unity terrain)

### Data & Configuration

- [ ] **DATA-01**: Claude can create, edit, and validate JSON/XML game configuration files (difficulty, balance, progression)
- [ ] **DATA-02**: Claude can create ScriptableObject definitions and instantiate .asset files for data-driven design
- [ ] **DATA-03**: Claude can set up Unity Localization package (string tables, locale assets, localized variants)
- [ ] **DATA-04**: Claude can generate game data authoring tools (item databases, stat tables, ability configs as SO assets)

### Build & Deploy

- [ ] **BUILD-01**: Claude can orchestrate multi-platform builds (Windows, Mac, Linux, Android, iOS, WebGL) with per-platform settings
- [ ] **BUILD-02**: Claude can configure Addressable Asset Groups (remote/local paths, content catalogs, memory management)
- [ ] **BUILD-03**: Claude can generate CI/CD pipeline configs (GitHub Actions, GitLab CI) for automated Unity builds and tests
- [ ] **BUILD-04**: Claude can manage version numbers, release branches, and changelogs
- [ ] **BUILD-05**: Claude can configure platform-specific settings (Android manifest, iOS plist, WebGL template)
- [ ] **BUILD-06**: Claude can set up sprite sheet packing, texture atlasing, and sprite animation

### Quality & Testing

- [ ] **QA-01**: Claude can run EditMode and PlayMode tests via Unity Test Runner and report results through MCP
- [ ] **QA-02**: Claude can script automated play sessions (walk to point, interact, verify state) for integration testing
- [ ] **QA-03**: Claude can capture GPU profiling data and continuous performance analysis
- [ ] **QA-04**: Claude can detect memory leaks (managed/native memory snapshots, growing allocations)
- [ ] **QA-05**: Claude can run static code analysis (Roslyn analyzers for Update() allocations, string concat, Camera.main)
- [ ] **QA-06**: Claude can set up crash reporting (Sentry, Unity Cloud Diagnostics)
- [ ] **QA-07**: Claude can set up analytics/telemetry events for player behavior tracking
- [ ] **QA-08**: Claude can inspect live game state during Play Mode (variable values on GameObjects, BT state)

### Import Pipeline

- [ ] **IMP-01**: Claude can manage .meta files and GUIDs when moving/renaming assets (AssetDatabase.MoveAsset)
- [ ] **IMP-02**: Claude can configure material remapping on FBX import (auto-generate from textures or remap to existing)
- [ ] **IMP-03**: Claude can set up Git LFS rules, .gitignore, .gitattributes for Unity projects
- [ ] **IMP-04**: Claude can configure normal map baking workflow (high-to-low with cage generation in one step)

### UI & UX Enhancements

- [ ] **UIX-01**: Claude can generate minimap/compass with world-space markers
- [ ] **UIX-02**: Claude can generate tutorial/onboarding sequences with tooltip overlays
- [ ] **UIX-03**: Claude can generate damage number floating text system
- [ ] **UIX-04**: Claude can generate context-sensitive interaction prompts (press E to interact)

### AI & Encounter Design

- [ ] **AID-01**: Claude can generate encounter scripting system (triggers, waves, conditions, AI director)
- [ ] **AID-02**: Claude can generate threat escalation / AI director (dynamic difficulty adjustment)
- [ ] **AID-03**: Claude can simulate encounters for balance testing (run N encounters, report statistics)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Custom game engine | Unity is the target |
| Houdini integration | Blender Geometry Nodes covers procedural needs |
| Live operations / analytics infrastructure | Development tool, not production ops |
| Console platform SDKs (PlayStation, Xbox, Switch) | Requires licensed devkits |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EDIT-01 | Phase 9 | Pending |
| EDIT-02 | Phase 9 | Pending |
| EDIT-03 | Phase 9 | Pending |
| EDIT-04 | Phase 9 | Pending |
| EDIT-05 | Phase 9 | Pending |
| EDIT-06 | Phase 9 | Pending |
| EDIT-07 | Phase 9 | Pending |
| EDIT-08 | Phase 9 | Pending |
| EDIT-09 | Phase 9 | Pending |
| EDIT-10 | Phase 9 | Pending |
| EDIT-11 | Phase 9 | Pending |
| EDIT-12 | Phase 9 | Pending |
| EDIT-13 | Phase 9 | Pending |
| EDIT-14 | Phase 9 | Pending |
| EDIT-15 | Phase 9 | Pending |
| IMP-01 | Phase 9 | Pending |
| IMP-02 | Phase 9 | Pending |
| CODE-01 | Phase 10 | Pending |
| CODE-02 | Phase 10 | Pending |
| CODE-03 | Phase 10 | Pending |
| CODE-04 | Phase 10 | Pending |
| CODE-05 | Phase 10 | Pending |
| CODE-06 | Phase 10 | Pending |
| CODE-07 | Phase 10 | Pending |
| CODE-08 | Phase 10 | Pending |
| CODE-09 | Phase 10 | Pending |
| CODE-10 | Phase 10 | Pending |
| DATA-01 | Phase 11 | Pending |
| DATA-02 | Phase 11 | Pending |
| DATA-03 | Phase 11 | Pending |
| DATA-04 | Phase 11 | Pending |
| IMP-03 | Phase 11 | Pending |
| IMP-04 | Phase 11 | Pending |
| BUILD-06 | Phase 11 | Pending |
| GAME-01 | Phase 12 | Pending |
| GAME-05 | Phase 12 | Pending |
| GAME-06 | Phase 12 | Pending |
| GAME-07 | Phase 12 | Pending |
| GAME-08 | Phase 12 | Pending |
| GAME-02 | Phase 13 | Pending |
| GAME-03 | Phase 13 | Pending |
| GAME-04 | Phase 13 | Pending |
| GAME-09 | Phase 13 | Pending |
| GAME-10 | Phase 13 | Pending |
| GAME-11 | Phase 13 | Pending |
| GAME-12 | Phase 13 | Pending |
| CAM-01 | Phase 14 | Pending |
| CAM-02 | Phase 14 | Pending |
| CAM-03 | Phase 14 | Pending |
| CAM-04 | Phase 14 | Pending |
| SCNE-01 | Phase 14 | Pending |
| SCNE-02 | Phase 14 | Pending |
| SCNE-03 | Phase 14 | Pending |
| SCNE-04 | Phase 14 | Pending |
| SCNE-05 | Phase 14 | Pending |
| SCNE-06 | Phase 14 | Pending |
| UIX-01 | Phase 15 | Pending |
| UIX-02 | Phase 15 | Pending |
| UIX-03 | Phase 15 | Pending |
| UIX-04 | Phase 15 | Pending |
| AID-01 | Phase 15 | Pending |
| AID-02 | Phase 15 | Pending |
| AID-03 | Phase 15 | Pending |
| QA-01 | Phase 16 | Pending |
| QA-02 | Phase 16 | Pending |
| QA-03 | Phase 16 | Pending |
| QA-04 | Phase 16 | Pending |
| QA-05 | Phase 16 | Pending |
| QA-06 | Phase 16 | Pending |
| QA-07 | Phase 16 | Pending |
| QA-08 | Phase 16 | Pending |
| BUILD-01 | Phase 17 | Pending |
| BUILD-02 | Phase 17 | Pending |
| BUILD-03 | Phase 17 | Pending |
| BUILD-04 | Phase 17 | Pending |
| BUILD-05 | Phase 17 | Pending |

**Coverage:**
- v2 requirements: 76 total (across 11 categories: EDIT, CODE, GAME, CAM, SCNE, DATA, BUILD, QA, IMP, UIX, AID)
- Mapped to phases: 76/76
- Unmapped: 0

**Note:** The previous count of "65 total" only covered the first 8 categories. The actual count including IMP (4), UIX (4), and AID (3) is 76.

---
*Requirements defined: 2026-03-18 (v1), updated 2026-03-19 (v2 with traceability)*
