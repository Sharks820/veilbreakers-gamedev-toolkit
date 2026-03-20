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

- [x] **EDIT-01**: Claude can create, modify, and delete Prefabs programmatically (including nested prefabs and prefab variants)
- [x] **EDIT-02**: Claude can add, remove, and configure any Component on any GameObject (Rigidbody, Collider, AudioSource, Light, custom MonoBehaviours)
- [x] **EDIT-03**: Claude can manipulate scene hierarchy (create empties, rename, reparent, enable/disable, set layer/tag)
- [x] **EDIT-04**: Claude can configure physics layers, layer collision matrix, and physics materials (friction, bounciness)
- [x] **EDIT-05**: Claude can manage Player Settings (company name, product name, icon, splash, scripting backend, API compat, color space)
- [x] **EDIT-06**: Claude can manage Build Settings (add/remove/reorder scenes, switch platform, set scripting defines)
- [x] **EDIT-07**: Claude can configure Quality Settings (shadow distance/resolution, texture quality, AA, VSync, LOD bias)
- [x] **EDIT-08**: Claude can install, remove, and update Unity packages via Package Manager (manifest.json + UPM)
- [x] **EDIT-09**: Claude can create and manage custom Tags, Sorting Layers, and Physics Layers
- [x] **EDIT-10**: Claude can perform asset operations (move, rename, delete, duplicate, create folders) while preserving .meta/GUID integrity
- [x] **EDIT-11**: Claude can configure Time settings (fixed timestep), Graphics settings (render pipeline asset), and Editor preferences
- [x] **EDIT-12**: Claude can configure FBX ModelImporter settings on import (scale, mesh compression, normals, animation compression, rig)
- [x] **EDIT-13**: Claude can configure TextureImporter settings (max size, compression per platform, sRGB/linear, sprite mode, mip maps)
- [x] **EDIT-14**: Claude can remap materials on FBX import to existing project materials or auto-generate from imported textures
- [x] **EDIT-15**: Claude can create and manage Assembly Definition files (.asmdef) for compile time optimization

### C# Programming

- [x] **CODE-01**: Claude can generate arbitrary C# MonoBehaviours, plain classes, interfaces, enums, structs, and static utilities (not just domain templates)
- [x] **CODE-02**: Claude can modify existing C# scripts (add methods, fields, properties, attributes, using statements)
- [x] **CODE-03**: Claude can generate custom Inspector drawers, PropertyDrawers, EditorWindows, and SceneView overlays
- [x] **CODE-04**: Claude can create EditMode and PlayMode test assemblies, fixtures, and test methods (NUnit / Unity Test Framework)
- [x] **CODE-05**: Claude can run Unity tests and collect pass/fail results through MCP
- [x] **CODE-06**: Claude can scaffold dependency injection patterns (service locator, event bus, SO event channels)
- [x] **CODE-07**: Claude can generate generic object pooling systems (projectiles, enemies, VFX, UI elements)
- [x] **CODE-08**: Claude can generate singleton patterns (persistent MonoBehaviour, non-MB singletons)
- [x] **CODE-09**: Claude can generate generic reusable state machine framework usable by multiple systems
- [x] **CODE-10**: Claude can generate observer/event system with ScriptableObject event channels

### Game Systems

- [x] **GAME-01**: Claude can generate a complete save/load system (JSON/binary serialization, save slots, data migration)
- [ ] **GAME-02**: Claude can generate inventory system (item database SO, UI slots, drag-and-drop, equipment, storage)
- [ ] **GAME-03**: Claude can generate dialogue system (branching trees, dialogue UI, NPC interaction, YarnSpinner-compatible)
- [ ] **GAME-04**: Claude can generate quest system (objectives, tracking, quest givers, quest log UI, completion rewards)
- [x] **GAME-05**: Claude can generate health/damage system (HP component, damage numbers, death handling, respawn)
- [x] **GAME-06**: Claude can generate character controller (first-person and third-person movement, camera follow)
- [x] **GAME-07**: Claude can configure Input System (Input Action assets, action maps, control schemes, rebinding)
- [x] **GAME-08**: Claude can generate game settings menu (graphics quality, audio volume, keybindings, accessibility)
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

- [x] **DATA-01**: Claude can create, edit, and validate JSON/XML game configuration files (difficulty, balance, progression)
- [x] **DATA-02**: Claude can create ScriptableObject definitions and instantiate .asset files for data-driven design
- [x] **DATA-03**: Claude can set up Unity Localization package (string tables, locale assets, localized variants)
- [x] **DATA-04**: Claude can generate game data authoring tools (item databases, stat tables, ability configs as SO assets)

### Build & Deploy

- [ ] **BUILD-01**: Claude can orchestrate multi-platform builds (Windows, Mac, Linux, Android, iOS, WebGL) with per-platform settings
- [ ] **BUILD-02**: Claude can configure Addressable Asset Groups (remote/local paths, content catalogs, memory management)
- [ ] **BUILD-03**: Claude can generate CI/CD pipeline configs (GitHub Actions, GitLab CI) for automated Unity builds and tests
- [ ] **BUILD-04**: Claude can manage version numbers, release branches, and changelogs
- [ ] **BUILD-05**: Claude can configure platform-specific settings (Android manifest, iOS plist, WebGL template)
- [x] **BUILD-06**: Claude can set up sprite sheet packing, texture atlasing, and sprite animation

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

- [x] **IMP-01**: Claude can manage .meta files and GUIDs when moving/renaming assets (AssetDatabase.MoveAsset)
- [x] **IMP-02**: Claude can configure material remapping on FBX import (auto-generate from textures or remap to existing)
- [x] **IMP-03**: Claude can set up Git LFS rules, .gitignore, .gitattributes for Unity projects
- [x] **IMP-04**: Claude can configure normal map baking workflow (high-to-low with cage generation in one step)

### UI & UX Enhancements

- [ ] **UIX-01**: Claude can generate minimap/compass with world-space markers
- [ ] **UIX-02**: Claude can generate tutorial/onboarding sequences with tooltip overlays
- [ ] **UIX-03**: Claude can generate damage number floating text system
- [ ] **UIX-04**: Claude can generate context-sensitive interaction prompts (press E to interact)

### AI & Encounter Design

- [ ] **AID-01**: Claude can generate encounter scripting system (triggers, waves, conditions, AI director)
- [ ] **AID-02**: Claude can generate threat escalation / AI director (dynamic difficulty adjustment)
- [ ] **AID-03**: Claude can simulate encounters for balance testing (run N encounters, report statistics)

### Shader & Rendering

- [x] **SHDR-01**: Claude can write arbitrary HLSL/ShaderLab shaders (not just predefined templates)
- [x] **SHDR-02**: Claude can create custom URP ScriptableRendererFeatures and render passes
- [ ] **SHDR-03**: Claude can manage shader variant stripping and keyword sets for build size optimization
- [ ] **SHDR-04**: Claude can generate DOTween/LeanTween animation sequences for UI polish and game juice

### 2D Systems

- [ ] **TWO-01**: Claude can create and paint 2D Tilemaps with Tile Palettes and Rule Tiles
- [ ] **TWO-02**: Claude can configure 2D Physics (Rigidbody2D, Collider2D, Physics2D settings, 2D joints)
- [x] **TWO-03**: Claude can configure Sprite Editor features (custom physics shapes, pivot, 9-slice borders)

### Physics Advanced

- [x] **PHYS-01**: Claude can configure physics Joints (HingeJoint, SpringJoint, ConfigurableJoint, CharacterJoint, FixedJoint)
- [x] **PHYS-02**: Claude can set up NavMeshObstacle, Off-Mesh Links, and NavMesh Areas with cost configuration

### Accessibility & Publishing

- [ ] **ACC-01**: Claude can generate accessibility features (colorblind modes, subtitle sizing, screen reader tags, motor accessibility options)
- [ ] **ACC-02**: Claude can generate store publishing metadata (screenshots, descriptions, content ratings, privacy policy templates)

### Asset Pipeline Advanced

- [x] **PIPE-08**: Claude can generate AssetPostprocessor scripts for custom import pipelines
- [x] **PIPE-09**: Claude can generate Unity Presets for reusable import/component configuration templates
- [ ] **PIPE-10**: Claude can configure TextMeshPro (font asset creation, TMP component setup, rich text, font fallbacks)

### Video & Media

- [ ] **MEDIA-01**: Claude can configure VideoPlayer component for video playback and render texture output
- [x] **MEDIA-02**: Claude can generate UnityWebRequest utilities for HTTP/REST API calls

### Animation Advanced

- [ ] **ANIMA-01**: Claude can edit Unity AnimationClips (add/remove keyframes, modify curves) programmatically
- [ ] **ANIMA-02**: Claude can modify existing Animator Controllers (add/remove states, configure transitions, sub-state machines)
- [ ] **ANIMA-03**: Claude can create Avatar Masks for animation layer filtering

### AAA Quality & Art Style

- [x] **AAA-01**: Claude can apply albedo de-lighting to AI-generated model textures (remove baked-in lighting artifacts from Tripo3D output)
- [x] **AAA-02**: Claude can enforce per-asset-type polygon budgets (hero: 30-50k, mob: 8-15k, weapon: 3-8k, prop: 500-6k, building: 5-15k) with auto-retopo if over budget
- [x] **AAA-03**: Claude can apply dark fantasy material palette validation (saturation caps, color temperature rules, PBR roughness variation enforcement)
- [x] **AAA-04**: Claude can generate master material library with base materials (stone, wood, iron, moss, bone, cloth, leather) that all assets reference for art consistency
- [ ] **AAA-05**: Claude can add storytelling props (layer 3: clutter, wall decor, narrative detail — cobwebs, bloodstains, scattered papers, broken pottery) to any interior
- [x] **AAA-06**: Claude can validate texture quality against standards (texel density 10.24 px/cm, no flat roughness, micro-detail normals present, proper channel packing M/R/AO)

### Equipment & Weapons

- [x] **EQUIP-01**: Claude can generate weapon meshes from text descriptions (swords, axes, maces, staffs, bows, daggers, shields) with proper grip points, trail VFX attachment points, and collision mesh
- [x] **EQUIP-02**: Claude can set up bone socket attachment system on character rigs (10 standard sockets: weapon_hand_R/L, shield_hand_L, back_weapon, hip_L/R, head, chest, spell_hand_R/L)
- [x] **EQUIP-03**: Claude can split character mesh into modular parts (head, torso, upper arms, lower arms, upper legs, lower legs, feet) for armor swapping
- [x] **EQUIP-04**: Claude can generate armor/clothing meshes that fit character models using shape keys and vertex weight transfer
- [x] **EQUIP-05**: Claude can generate equipment preview icons (3D rendered turntable or flat icon) for inventory UI
- [ ] **EQUIP-06**: Claude can set up Unity equipment attachment system (SkinnedMeshRenderer rebinding, bone socket parenting, sheathed weapon positioning with Multi-Parent Constraint)
- [ ] **EQUIP-07**: Claude can apply rarity tier visual effects to equipment (Common gray, Rare blue, Epic purple, Legendary gold glow + particle effects)
- [ ] **EQUIP-08**: Claude can apply corruption visual progression to equipment (0-100% corruption with increasing vein patterns, color shift, particle emission)

### World Design & Composition

- [ ] **WORLD-01**: Claude can generate complete explorable locations from text descriptions (cities, bandit camps, dungeons, castles, forest clearings, ruins) with proper scale, paths, and points of interest
- [ ] **WORLD-02**: Claude can generate fully furnished building interiors for 16 room types (tavern, throne room, prison, bedroom, kitchen, library, armory, temple, blacksmith, guard barracks, treasury, war room, alchemy lab, torture chamber, crypt, dining hall)
- [ ] **WORLD-03**: Claude can generate boss arena environments with fog gates, cover objects, hazard zones, phase triggers, and proper scale (20-40m)
- [ ] **WORLD-04**: Claude can connect locations into a world graph with proper walking distances (30-second rule: point of interest every ~105m), path generation, and terrain integration
- [ ] **WORLD-05**: Claude can generate interior-exterior linked buildings (door triggers, occlusion culling zones, lighting transitions, collision boundaries)
- [ ] **WORLD-06**: Claude can generate multi-floor dungeon layouts with vertical progression (descending staircases, elevators, ladders, pit drops), proper ceiling heights, and navigable corridors
- [ ] **WORLD-07**: Claude can place furniture and props at correct real-world scale (doors: 1.0-1.2m wide, ceilings: 2.8-3.5m, tables: 0.75m high, chairs to fit character model)
- [ ] **WORLD-08**: Claude can apply time-of-day lighting presets across entire scenes (8 presets: dawn, morning, noon, afternoon, dusk, evening, night, midnight) with matching fog/atmosphere
- [ ] **WORLD-09**: Claude can generate overrun/ruined variants of intact locations (add debris, broken walls, overgrown vegetation, scattered remains, damaged furniture)
- [ ] **WORLD-10**: Claude can place easter eggs and hidden areas (secret rooms behind breakable walls, hidden paths off main routes, lore items in unexpected locations)

### VeilBreakers Core Systems

- [x] **VB-01**: Claude can generate a player combat controller (light/heavy attack, dodge, block, combo chains, hit reactions, i-frames, stamina consumption)
- [x] **VB-02**: Claude can generate a player ability system with brand-specific ability slots, cooldown timers, mana/stamina resource management, and ability activation per combat brand
- [x] **VB-03**: Claude can generate the synergy detection engine (FULL/PARTIAL/NEUTRAL/ANTI tier evaluation, combo triggers, synergy UI feedback)
- [x] **VB-04**: Claude can generate corruption gameplay effects (stat modifiers, ability mutations, NPC reaction changes, threshold triggers at 25/50/75/100%)
- [x] **VB-05**: Claude can generate an experience/leveling system (XP gain from kills/quests, level-up triggers, stat scaling per level, per-hero-path progression curves)
- [x] **VB-06**: Claude can generate a currency system (gold/souls/marks earning, spending, display, multiple currency types)
- [x] **VB-07**: Claude can generate damage type system with 10 brand-specific damage types and elemental resistance calculations
- [ ] **VB-08**: Claude can generate brand-specific loot affinity (IRON brand mobs drop IRON-themed gear, rarity-weighted per brand)
- [ ] **VB-09**: Claude can generate a character creation/selection screen (choose hero path, customize appearance, name entry)
- [ ] **VB-10**: Claude can generate boss AI behavior (multi-phase state machine, phase transitions at HP thresholds, unique attack patterns, enrage mechanics)

### RPG World Systems

- [ ] **RPG-01**: Claude can generate a shop/merchant system (buy/sell UI, price display, equipment stat comparison, currency transactions, merchant inventory)
- [ ] **RPG-02**: Claude can generate a fast travel/waypoint system (discover waypoints by visiting, teleport between unlocked points, loading transition)
- [x] **RPG-03**: Claude can generate an interactable object framework (state machine for doors, chests, levers, switches with animations and sound)
- [ ] **RPG-04**: Claude can generate environmental puzzle mechanics (lever sequences, pressure plates, key-and-lock, movable blocks, light beam puzzles)
- [ ] **RPG-05**: Claude can generate a journal/codex/bestiary system (lore entries from world, monster compendium with stats/weaknesses, item encyclopedia)
- [ ] **RPG-06**: Claude can generate dungeon trap mechanics (pressure plates, dart walls, spike pits, falling rocks, poison gas, swinging blades)
- [ ] **RPG-07**: Claude can generate spatial loot placement in dungeons (treasure chest positions, item drops in specific rooms, treasure room layouts)
- [ ] **RPG-08**: Claude can generate a 2D world map screen from 3D terrain data (fog-of-war, location markers, player position, discovered areas)
- [ ] **RPG-09**: Claude can generate a weather system with state management (rain, snow, fog, storms), smooth transitions, and optional gameplay effects
- [ ] **RPG-10**: Claude can generate a day/night runtime cycle (continuous time progression, lighting preset transitions, NPC schedule changes, enemy behavior shifts)
- [ ] **RPG-11**: Claude can generate friendly NPC placement markers inside buildings (shopkeeper positions, quest giver positions, bartender positions, guard positions)
- [ ] **RPG-12**: Claude can generate dungeon-specific lighting (torch sconces every 4-6m, dark corridors, light pools around fire sources, atmospheric fog)
- [ ] **RPG-13**: Claude can generate terrain-building blending (vertex color at base, decal projection, terrain depression beneath structures)

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
| EDIT-01 | Phase 9 | Complete |
| EDIT-02 | Phase 9 | Complete |
| EDIT-03 | Phase 9 | Complete |
| EDIT-04 | Phase 9 | Complete |
| EDIT-05 | Phase 9 | Complete |
| EDIT-06 | Phase 9 | Complete |
| EDIT-07 | Phase 9 | Complete |
| EDIT-08 | Phase 9 | Complete |
| EDIT-09 | Phase 9 | Complete |
| EDIT-10 | Phase 9 | Complete |
| EDIT-11 | Phase 9 | Complete |
| EDIT-12 | Phase 9 | Complete |
| EDIT-13 | Phase 9 | Complete |
| EDIT-14 | Phase 9 | Complete |
| EDIT-15 | Phase 9 | Complete |
| IMP-01 | Phase 9 | Complete |
| IMP-02 | Phase 9 | Complete |
| CODE-01 | Phase 10 | Complete |
| CODE-02 | Phase 10 | Complete |
| CODE-03 | Phase 10 | Complete |
| CODE-04 | Phase 10 | Complete |
| CODE-05 | Phase 10 | Complete |
| CODE-06 | Phase 10 | Complete |
| CODE-07 | Phase 10 | Complete |
| CODE-08 | Phase 10 | Complete |
| CODE-09 | Phase 10 | Complete |
| CODE-10 | Phase 10 | Complete |
| DATA-01 | Phase 11 | Complete |
| DATA-02 | Phase 11 | Complete |
| DATA-03 | Phase 11 | Complete |
| DATA-04 | Phase 11 | Complete |
| IMP-03 | Phase 11 | Complete |
| IMP-04 | Phase 11 | Complete |
| BUILD-06 | Phase 11 | Complete |
| GAME-01 | Phase 12 | Complete |
| GAME-05 | Phase 12 | Complete |
| GAME-06 | Phase 12 | Complete |
| GAME-07 | Phase 12 | Complete |
| GAME-08 | Phase 12 | Complete |
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
| SHDR-01 | Phase 10 | Complete |
| SHDR-02 | Phase 10 | Complete |
| SHDR-03 | Phase 17 | Pending |
| SHDR-04 | Phase 15 | Pending |
| TWO-01 | Phase 14 | Pending |
| TWO-02 | Phase 14 | Pending |
| TWO-03 | Phase 11 | Complete |
| PHYS-01 | Phase 9 | Complete |
| PHYS-02 | Phase 9 | Complete |
| ACC-01 | Phase 15 | Pending |
| ACC-02 | Phase 17 | Pending |
| PIPE-08 | Phase 11 | Complete |
| PIPE-09 | Phase 9 | Complete |
| PIPE-10 | Phase 15 | Pending |
| MEDIA-01 | Phase 14 | Pending |
| MEDIA-02 | Phase 12 | Complete |
| ANIMA-01 | Phase 14 | Pending |
| ANIMA-02 | Phase 14 | Pending |
| ANIMA-03 | Phase 14 | Pending |

| AAA-01 | Phase 11 | Complete |
| AAA-02 | Phase 11 | Complete |
| AAA-03 | Phase 11 | Complete |
| AAA-04 | Phase 11 | Complete |
| AAA-05 | Phase 14 | Pending |
| AAA-06 | Phase 11 | Complete |
| EQUIP-01 | Phase 13 | Complete |
| EQUIP-02 | Phase 9 | Complete |
| EQUIP-03 | Phase 13 | Complete |
| EQUIP-04 | Phase 13 | Complete |
| EQUIP-05 | Phase 13 | Complete |
| EQUIP-06 | Phase 13 | Pending |
| EQUIP-07 | Phase 15 | Pending |
| EQUIP-08 | Phase 15 | Pending |
| WORLD-01 | Phase 14 | Pending |
| WORLD-02 | Phase 14 | Pending |
| WORLD-03 | Phase 14 | Pending |
| WORLD-04 | Phase 14 | Pending |
| WORLD-05 | Phase 14 | Pending |
| WORLD-06 | Phase 14 | Pending |
| WORLD-07 | Phase 14 | Pending |
| WORLD-08 | Phase 14 | Pending |
| WORLD-09 | Phase 14 | Pending |
| WORLD-10 | Phase 14 | Pending |

| VB-01 | Phase 12 | Complete |
| VB-02 | Phase 12 | Complete |
| VB-03 | Phase 12 | Complete |
| VB-04 | Phase 12 | Complete |
| VB-05 | Phase 12 | Complete |
| VB-06 | Phase 12 | Complete |
| VB-07 | Phase 12 | Complete |
| VB-08 | Phase 13 | Pending |
| VB-09 | Phase 15 | Pending |
| VB-10 | Phase 15 | Pending |
| RPG-01 | Phase 13 | Pending |
| RPG-02 | Phase 14 | Pending |
| RPG-03 | Phase 12 | Complete |
| RPG-04 | Phase 14 | Pending |
| RPG-05 | Phase 13 | Pending |
| RPG-06 | Phase 14 | Pending |
| RPG-07 | Phase 14 | Pending |
| RPG-08 | Phase 15 | Pending |
| RPG-09 | Phase 14 | Pending |
| RPG-10 | Phase 14 | Pending |
| RPG-11 | Phase 14 | Pending |
| RPG-12 | Phase 14 | Pending |
| RPG-13 | Phase 14 | Pending |

**Coverage:**
- v2 requirements: 143 total (across 23 categories)
- Mapped to phases: 143/143
- Unmapped: 0

**Categories:** EDIT (15), CODE (10), GAME (12), CAM (4), SCNE (6), DATA (4), BUILD (7), QA (8), IMP (4), UIX (4), AID (3), SHDR (4), TWO (3), PHYS (2), ACC (2), PIPE (3), MEDIA (2), ANIMA (3), AAA (6), EQUIP (8), WORLD (10), VB (10), RPG (13)

---
*Requirements defined: 2026-03-18 (v1), updated 2026-03-19 (v2 with traceability)*
