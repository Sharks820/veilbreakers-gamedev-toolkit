# Requirements: VeilBreakers GameDev Toolkit

**Defined:** 2026-03-18
**Updated:** 2026-03-21 (v3.0 complete)
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
- [x] **GAME-02**: Claude can generate inventory system (item database SO, UI slots, drag-and-drop, equipment, storage)
- [x] **GAME-03**: Claude can generate dialogue system (branching trees, dialogue UI, NPC interaction, YarnSpinner-compatible)
- [x] **GAME-04**: Claude can generate quest system (objectives, tracking, quest givers, quest log UI, completion rewards)
- [x] **GAME-05**: Claude can generate health/damage system (HP component, damage numbers, death handling, respawn)
- [x] **GAME-06**: Claude can generate character controller (first-person and third-person movement, camera follow)
- [x] **GAME-07**: Claude can configure Input System (Input Action assets, action maps, control schemes, rebinding)
- [x] **GAME-08**: Claude can generate game settings menu (graphics quality, audio volume, keybindings, accessibility)
- [x] **GAME-09**: Claude can generate loot table system (weighted random, rarity tiers, drop conditions)
- [x] **GAME-10**: Claude can generate crafting/recipe system (ingredient requirements, crafting stations, unlock progression)
- [x] **GAME-11**: Claude can generate skill tree / talent system (node graph, unlock dependencies, point allocation)
- [x] **GAME-12**: Claude can generate combat balancing tools (DPS calculator, encounter simulator, stat curve editor)

### Camera & Cinematics

- [x] **CAM-01**: Claude can create and configure Cinemachine virtual cameras (FreeLook, follow, state-driven, blending)
- [x] **CAM-02**: Claude can create Timeline assets with animation, audio, activation, and Cinemachine tracks
- [x] **CAM-03**: Claude can set up cutscene sequences using Playable Director with Timeline
- [x] **CAM-04**: Claude can configure camera shake, zoom, and transition effects

### Scene Management

- [x] **SCNE-01**: Claude can create new Unity scenes and configure scene loading (single, additive, async)
- [x] **SCNE-02**: Claude can generate scene transition system (loading screens, fade transitions, bootstrapper)
- [x] **SCNE-03**: Claude can set up reflection probes, light probes, and probe groups
- [x] **SCNE-04**: Claude can configure occlusion culling (mark static occluders/occludees, bake data)
- [x] **SCNE-05**: Claude can set up HDR skybox, environment reflections, and Global Illumination
- [x] **SCNE-06**: Claude can generate terrain detail painting (grass, detail meshes on Unity terrain)

### Data & Configuration

- [x] **DATA-01**: Claude can create, edit, and validate JSON/XML game configuration files (difficulty, balance, progression)
- [x] **DATA-02**: Claude can create ScriptableObject definitions and instantiate .asset files for data-driven design
- [x] **DATA-03**: Claude can set up Unity Localization package (string tables, locale assets, localized variants)
- [x] **DATA-04**: Claude can generate game data authoring tools (item databases, stat tables, ability configs as SO assets)

### Build & Deploy

- [x] **BUILD-01**: Claude can orchestrate multi-platform builds (Windows, Mac, Linux, Android, iOS, WebGL) with per-platform settings
- [x] **BUILD-02**: Claude can configure Addressable Asset Groups (remote/local paths, content catalogs, memory management)
- [x] **BUILD-03**: Claude can generate CI/CD pipeline configs (GitHub Actions, GitLab CI) for automated Unity builds and tests
- [x] **BUILD-04**: Claude can manage version numbers, release branches, and changelogs
- [x] **BUILD-05**: Claude can configure platform-specific settings (Android manifest, iOS plist, WebGL template)
- [x] **BUILD-06**: Claude can set up sprite sheet packing, texture atlasing, and sprite animation

### Quality & Testing

- [x] **QA-00**: The VB Unity MCP server can directly communicate with the Unity Editor (TCP bridge addon) to trigger AssetDatabase.Refresh, execute menu items, enter/exit play mode, and read results — WITHOUT requiring mcp-unity or any external MCP server
- [x] **QA-01**: Claude can run EditMode and PlayMode tests via Unity Test Runner and report results through MCP
- [x] **QA-02**: Claude can script automated play sessions (walk to point, interact, verify state) for integration testing
- [x] **QA-03**: Claude can capture GPU profiling data and continuous performance analysis
- [x] **QA-04**: Claude can detect memory leaks (managed/native memory snapshots, growing allocations)
- [x] **QA-05**: Claude can run static code analysis (Roslyn analyzers for Update() allocations, string concat, Camera.main)
- [x] **QA-06**: Claude can set up crash reporting (Sentry, Unity Cloud Diagnostics)
- [x] **QA-07**: Claude can set up analytics/telemetry events for player behavior tracking
- [x] **QA-08**: Claude can inspect live game state during Play Mode (variable values on GameObjects, BT state)

### Import Pipeline

- [x] **IMP-01**: Claude can manage .meta files and GUIDs when moving/renaming assets (AssetDatabase.MoveAsset)
- [x] **IMP-02**: Claude can configure material remapping on FBX import (auto-generate from textures or remap to existing)
- [x] **IMP-03**: Claude can set up Git LFS rules, .gitignore, .gitattributes for Unity projects
- [x] **IMP-04**: Claude can configure normal map baking workflow (high-to-low with cage generation in one step)

### UI & UX Enhancements

- [x] **UIX-01**: Claude can generate minimap/compass with world-space markers
- [x] **UIX-02**: Claude can generate tutorial/onboarding sequences with tooltip overlays
- [x] **UIX-03**: Claude can generate damage number floating text system
- [x] **UIX-04**: Claude can generate context-sensitive interaction prompts (press E to interact)

### AI & Encounter Design

- [x] **AID-01**: Claude can generate encounter scripting system (triggers, waves, conditions, AI director)
- [x] **AID-02**: Claude can generate threat escalation / AI director (dynamic difficulty adjustment)
- [x] **AID-03**: Claude can simulate encounters for balance testing (run N encounters, report statistics)

### Shader & Rendering

- [x] **SHDR-01**: Claude can write arbitrary HLSL/ShaderLab shaders (not just predefined templates)
- [x] **SHDR-02**: Claude can create custom URP ScriptableRendererFeatures and render passes
- [x] **SHDR-03**: Claude can manage shader variant stripping and keyword sets for build size optimization
- [x] **SHDR-04**: Claude can generate DOTween/LeanTween animation sequences for UI polish and game juice

### 2D Systems

- [x] **TWO-01**: Claude can create and paint 2D Tilemaps with Tile Palettes and Rule Tiles
- [x] **TWO-02**: Claude can configure 2D Physics (Rigidbody2D, Collider2D, Physics2D settings, 2D joints)
- [x] **TWO-03**: Claude can configure Sprite Editor features (custom physics shapes, pivot, 9-slice borders)

### Physics Advanced

- [x] **PHYS-01**: Claude can configure physics Joints (HingeJoint, SpringJoint, ConfigurableJoint, CharacterJoint, FixedJoint)
- [x] **PHYS-02**: Claude can set up NavMeshObstacle, Off-Mesh Links, and NavMesh Areas with cost configuration

### Accessibility & Publishing

- [x] **ACC-01**: Claude can generate accessibility features (colorblind modes, subtitle sizing, screen reader tags, motor accessibility options)
- [x] **ACC-02**: Claude can generate store publishing metadata (screenshots, descriptions, content ratings, privacy policy templates)

### Asset Pipeline Advanced

- [x] **PIPE-08**: Claude can generate AssetPostprocessor scripts for custom import pipelines
- [x] **PIPE-09**: Claude can generate Unity Presets for reusable import/component configuration templates
- [x] **PIPE-10**: Claude can configure TextMeshPro (font asset creation, TMP component setup, rich text, font fallbacks)

### Video & Media

- [x] **MEDIA-01**: Claude can configure VideoPlayer component for video playback and render texture output
- [x] **MEDIA-02**: Claude can generate UnityWebRequest utilities for HTTP/REST API calls

### Animation Advanced

- [x] **ANIMA-01**: Claude can edit Unity AnimationClips (add/remove keyframes, modify curves) programmatically
- [x] **ANIMA-02**: Claude can modify existing Animator Controllers (add/remove states, configure transitions, sub-state machines)
- [x] **ANIMA-03**: Claude can create Avatar Masks for animation layer filtering

### AAA Quality & Art Style

- [x] **AAA-01**: Claude can apply albedo de-lighting to AI-generated model textures (remove baked-in lighting artifacts from Tripo3D output)
- [x] **AAA-02**: Claude can enforce per-asset-type polygon budgets (hero: 30-50k, mob: 8-15k, weapon: 3-8k, prop: 500-6k, building: 5-15k) with auto-retopo if over budget
- [x] **AAA-03**: Claude can apply dark fantasy material palette validation (saturation caps, color temperature rules, PBR roughness variation enforcement)
- [x] **AAA-04**: Claude can generate master material library with base materials (stone, wood, iron, moss, bone, cloth, leather) that all assets reference for art consistency
- [x] **AAA-05**: Claude can add storytelling props (layer 3: clutter, wall decor, narrative detail — cobwebs, bloodstains, scattered papers, broken pottery) to any interior
- [x] **AAA-06**: Claude can validate texture quality against standards (texel density 10.24 px/cm, no flat roughness, micro-detail normals present, proper channel packing M/R/AO)

### Equipment & Weapons

- [x] **EQUIP-01**: Claude can generate weapon meshes from text descriptions (swords, axes, maces, staffs, bows, daggers, shields) with proper grip points, trail VFX attachment points, and collision mesh
- [x] **EQUIP-02**: Claude can set up bone socket attachment system on character rigs (10 standard sockets: weapon_hand_R/L, shield_hand_L, back_weapon, hip_L/R, head, chest, spell_hand_R/L)
- [x] **EQUIP-03**: Claude can split character mesh into modular parts (head, torso, upper arms, lower arms, upper legs, lower legs, feet) for armor swapping
- [x] **EQUIP-04**: Claude can generate armor/clothing meshes that fit character models using shape keys and vertex weight transfer
- [x] **EQUIP-05**: Claude can generate equipment preview icons (3D rendered turntable or flat icon) for inventory UI
- [x] **EQUIP-06**: Claude can set up Unity equipment attachment system (SkinnedMeshRenderer rebinding, bone socket parenting, sheathed weapon positioning with Multi-Parent Constraint)
- [x] **EQUIP-07**: Claude can apply rarity tier visual effects to equipment (Common gray, Rare blue, Epic purple, Legendary gold glow + particle effects)
- [x] **EQUIP-08**: Claude can apply corruption visual progression to equipment (0-100% corruption with increasing vein patterns, color shift, particle emission)

### World Design & Composition

- [x] **WORLD-01**: Claude can generate complete explorable locations from text descriptions (cities, bandit camps, dungeons, castles, forest clearings, ruins) with proper scale, paths, and points of interest
- [x] **WORLD-02**: Claude can generate fully furnished building interiors for 16 room types (tavern, throne room, prison, bedroom, kitchen, library, armory, temple, blacksmith, guard barracks, treasury, war room, alchemy lab, torture chamber, crypt, dining hall)
- [x] **WORLD-03**: Claude can generate boss arena environments with fog gates, cover objects, hazard zones, phase triggers, and proper scale (20-40m)
- [x] **WORLD-04**: Claude can connect locations into a world graph with proper walking distances (30-second rule: point of interest every ~105m), path generation, and terrain integration
- [x] **WORLD-05**: Claude can generate interior-exterior linked buildings (door triggers, occlusion culling zones, lighting transitions, collision boundaries)
- [x] **WORLD-06**: Claude can generate multi-floor dungeon layouts with vertical progression (descending staircases, elevators, ladders, pit drops), proper ceiling heights, and navigable corridors
- [x] **WORLD-07**: Claude can place furniture and props at correct real-world scale (doors: 1.0-1.2m wide, ceilings: 2.8-3.5m, tables: 0.75m high, chairs to fit character model)
- [x] **WORLD-08**: Claude can apply time-of-day lighting presets across entire scenes (8 presets: dawn, morning, noon, afternoon, dusk, evening, night, midnight) with matching fog/atmosphere
- [x] **WORLD-09**: Claude can generate overrun/ruined variants of intact locations (add debris, broken walls, overgrown vegetation, scattered remains, damaged furniture)
- [x] **WORLD-10**: Claude can place easter eggs and hidden areas (secret rooms behind breakable walls, hidden paths off main routes, lore items in unexpected locations)

### VeilBreakers Core Systems

- [x] **VB-01**: Claude can generate a player combat controller (light/heavy attack, dodge, block, combo chains, hit reactions, i-frames, stamina consumption)
- [x] **VB-02**: Claude can generate a player ability system with brand-specific ability slots, cooldown timers, mana/stamina resource management, and ability activation per combat brand
- [x] **VB-03**: Claude can generate the synergy detection engine (FULL/PARTIAL/NEUTRAL/ANTI tier evaluation, combo triggers, synergy UI feedback)
- [x] **VB-04**: Claude can generate corruption gameplay effects (stat modifiers, ability mutations, NPC reaction changes, threshold triggers at 25/50/75/100%)
- [x] **VB-05**: Claude can generate an experience/leveling system (XP gain from kills/quests, level-up triggers, stat scaling per level, per-hero-path progression curves)
- [x] **VB-06**: Claude can generate a currency system (gold/souls/marks earning, spending, display, multiple currency types)
- [x] **VB-07**: Claude can generate damage type system with 10 brand-specific damage types and elemental resistance calculations
- [x] **VB-08**: Claude can generate brand-specific loot affinity (IRON brand mobs drop IRON-themed gear, rarity-weighted per brand)
- [x] **VB-09**: Claude can generate a character creation/selection screen (choose hero path, customize appearance, name entry)
- [x] **VB-10**: Claude can generate boss AI behavior (multi-phase state machine, phase transitions at HP thresholds, unique attack patterns, enrage mechanics)

### RPG World Systems

- [x] **RPG-01**: Claude can generate a shop/merchant system (buy/sell UI, price display, equipment stat comparison, currency transactions, merchant inventory)
- [x] **RPG-02**: Claude can generate a fast travel/waypoint system (discover waypoints by visiting, teleport between unlocked points, loading transition)
- [x] **RPG-03**: Claude can generate an interactable object framework (state machine for doors, chests, levers, switches with animations and sound)
- [x] **RPG-04**: Claude can generate environmental puzzle mechanics (lever sequences, pressure plates, key-and-lock, movable blocks, light beam puzzles)
- [x] **RPG-05**: Claude can generate a journal/codex/bestiary system (lore entries from world, monster compendium with stats/weaknesses, item encyclopedia)
- [x] **RPG-06**: Claude can generate dungeon trap mechanics (pressure plates, dart walls, spike pits, falling rocks, poison gas, swinging blades)
- [x] **RPG-07**: Claude can generate spatial loot placement in dungeons (treasure chest positions, item drops in specific rooms, treasure room layouts)
- [x] **RPG-08**: Claude can generate a 2D world map screen from 3D terrain data (fog-of-war, location markers, player position, discovered areas)
- [x] **RPG-09**: Claude can generate a weather system with state management (rain, snow, fog, storms), smooth transitions, and optional gameplay effects
- [x] **RPG-10**: Claude can generate a day/night runtime cycle (continuous time progression, lighting preset transitions, NPC schedule changes, enemy behavior shifts)
- [x] **RPG-11**: Claude can generate friendly NPC placement markers inside buildings (shopkeeper positions, quest giver positions, bartender positions, guard positions)
- [x] **RPG-12**: Claude can generate dungeon-specific lighting (torch sconces every 4-6m, dark corridors, light pools around fire sources, atmospheric fog)
- [x] **RPG-13**: Claude can generate terrain-building blending (vertex color at base, decal projection, terrain depression beneath structures)

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
| GAME-02 | Phase 13 | Complete |
| GAME-03 | Phase 13 | Complete |
| GAME-04 | Phase 13 | Complete |
| GAME-09 | Phase 13 | Complete |
| GAME-10 | Phase 13 | Complete |
| GAME-11 | Phase 13 | Complete |
| GAME-12 | Phase 13 | Complete |
| CAM-01 | Phase 14 | Complete |
| CAM-02 | Phase 14 | Complete |
| CAM-03 | Phase 14 | Complete |
| CAM-04 | Phase 14 | Complete |
| SCNE-01 | Phase 14 | Complete |
| SCNE-02 | Phase 14 | Complete |
| SCNE-03 | Phase 14 | Complete |
| SCNE-04 | Phase 14 | Complete |
| SCNE-05 | Phase 14 | Complete |
| SCNE-06 | Phase 14 | Complete |
| UIX-01 | Phase 15 | Complete |
| UIX-02 | Phase 15 | Complete |
| UIX-03 | Phase 15 | Complete |
| UIX-04 | Phase 15 | Complete |
| AID-01 | Phase 15 | Complete |
| AID-02 | Phase 15 | Complete |
| AID-03 | Phase 15 | Complete |
| QA-01 | Phase 16 | Complete |
| QA-02 | Phase 16 | Complete |
| QA-03 | Phase 16 | Complete |
| QA-04 | Phase 16 | Complete |
| QA-05 | Phase 16 | Complete |
| QA-06 | Phase 16 | Complete |
| QA-07 | Phase 16 | Complete |
| QA-08 | Phase 16 | Complete |
| BUILD-01 | Phase 17 | Complete |
| BUILD-02 | Phase 17 | Complete |
| BUILD-03 | Phase 17 | Complete |
| BUILD-04 | Phase 17 | Complete |
| BUILD-05 | Phase 17 | Complete |
| SHDR-01 | Phase 10 | Complete |
| SHDR-02 | Phase 10 | Complete |
| SHDR-03 | Phase 17 | Complete |
| SHDR-04 | Phase 15 | Complete |
| TWO-01 | Phase 14 | Complete |
| TWO-02 | Phase 14 | Complete |
| TWO-03 | Phase 11 | Complete |
| PHYS-01 | Phase 9 | Complete |
| PHYS-02 | Phase 9 | Complete |
| ACC-01 | Phase 15 | Complete |
| ACC-02 | Phase 17 | Complete |
| PIPE-08 | Phase 11 | Complete |
| PIPE-09 | Phase 9 | Complete |
| PIPE-10 | Phase 15 | Complete |
| MEDIA-01 | Phase 14 | Complete |
| MEDIA-02 | Phase 12 | Complete |
| ANIMA-01 | Phase 14 | Complete |
| ANIMA-02 | Phase 14 | Complete |
| ANIMA-03 | Phase 14 | Complete |

| AAA-01 | Phase 11 | Complete |
| AAA-02 | Phase 11 | Complete |
| AAA-03 | Phase 11 | Complete |
| AAA-04 | Phase 11 | Complete |
| AAA-05 | Phase 14 | Complete |
| AAA-06 | Phase 11 | Complete |
| EQUIP-01 | Phase 13 | Complete |
| EQUIP-02 | Phase 9 | Complete |
| EQUIP-03 | Phase 13 | Complete |
| EQUIP-04 | Phase 13 | Complete |
| EQUIP-05 | Phase 13 | Complete |
| EQUIP-06 | Phase 13 | Complete |
| EQUIP-07 | Phase 15 | Complete |
| EQUIP-08 | Phase 15 | Complete |
| WORLD-01 | Phase 14 | Complete |
| WORLD-02 | Phase 14 | Complete |
| WORLD-03 | Phase 14 | Complete |
| WORLD-04 | Phase 14 | Complete |
| WORLD-05 | Phase 14 | Complete |
| WORLD-06 | Phase 14 | Complete |
| WORLD-07 | Phase 14 | Complete |
| WORLD-08 | Phase 14 | Complete |
| WORLD-09 | Phase 14 | Complete |
| WORLD-10 | Phase 14 | Complete |

| VB-01 | Phase 12 | Complete |
| VB-02 | Phase 12 | Complete |
| VB-03 | Phase 12 | Complete |
| VB-04 | Phase 12 | Complete |
| VB-05 | Phase 12 | Complete |
| VB-06 | Phase 12 | Complete |
| VB-07 | Phase 12 | Complete |
| VB-08 | Phase 13 | Complete |
| VB-09 | Phase 15 | Complete |
| VB-10 | Phase 15 | Complete |
| RPG-01 | Phase 13 | Complete |
| RPG-02 | Phase 14 | Complete |
| RPG-03 | Phase 12 | Complete |
| RPG-04 | Phase 14 | Complete |
| RPG-05 | Phase 13 | Complete |
| RPG-06 | Phase 14 | Complete |
| RPG-07 | Phase 14 | Complete |
| RPG-08 | Phase 15 | Complete |
| RPG-09 | Phase 14 | Complete |
| RPG-10 | Phase 14 | Complete |
| RPG-11 | Phase 14 | Complete |
| RPG-12 | Phase 14 | Complete |
| RPG-13 | Phase 14 | Complete |

**Coverage:**
- v2 requirements: 143 total (across 23 categories)
- Mapped to phases: 143/143
- Unmapped: 0

**Categories:** EDIT (15), CODE (10), GAME (12), CAM (4), SCNE (6), DATA (4), BUILD (7), QA (8), IMP (4), UIX (4), AID (3), SHDR (4), TWO (3), PHYS (2), ACC (2), PIPE (3), MEDIA (2), ANIMA (3), AAA (6), EQUIP (8), WORLD (10), VB (10), RPG (13)

## v3 Requirements

Requirements for v3.0 — AAA Mesh Quality + Professional Systems.

### Mesh Integration

- [x] **MESH3-01**: Worldbuilding handlers use procedural mesh library (real furniture, props, vegetation -- not primitive cubes/cones)
- [x] **MESH3-02**: Environment scatter uses procedural rocks, trees, mushrooms, roots instead of geometric primitives
- [x] **MESH3-03**: Dungeon generation places actual trap meshes, altar meshes, prison doors, torch sconces from procedural library
- [x] **MESH3-04**: Castle generation uses actual gate, rampart, drawbridge, fountain meshes
- [x] **MESH3-05**: All procedural meshes have LOD variants (high/medium/low poly) for performance budgets

### Terrain Depth

- [x] **TERR-01**: Claude can generate vertical cliff face geometry (not limited to 2.5D heightmap)
- [x] **TERR-02**: Claude can generate cave entrance transition meshes (seamless terrain-to-cave geometry)
- [x] **TERR-03**: Claude can generate multi-biome terrain with smooth transitions (forest→swamp→mountain blend zones)
- [x] **TERR-04**: Claude can generate waterfall/cascade geometry with stepped water mesh
- [x] **TERR-05**: Claude can generate bridges spanning rivers/chasms (stone arch, rope, drawbridge)

### Character Excellence

- [x] **CHAR-01**: Claude can validate character body proportions against game-world scale specs (hero=1.8m, boss=3-6m, NPC=1.7m)
- [x] **CHAR-02**: Claude can generate hair card meshes (strip-based hair cards with UV layout for alpha textures)
- [x] **CHAR-03**: Claude can validate face topology (detect edge loops around eyes/mouth/nose for proper deformation)
- [x] **CHAR-04**: Claude can perform character-aware LOD retopology (preserve face detail while reducing body/extremities)
- [x] **CHAR-05**: Claude can generate armor seam-hiding overlap rings at split points (neck, wrist, ankle)
- [x] **CHAR-06**: Claude can validate hand/foot topology (finger separation, proper edge flow for deformation)
- [x] **CHAR-07**: Claude can configure Unity Cloth component on character meshes (vertex weight painting, collision spheres/capsules, wind interaction, stiffness/damping for capes, robes, hair, banners, and cloth armor pieces)
- [x] **CHAR-08**: Claude can generate subsurface scattering skin shaders, parallax eye shaders, and micro-detail normal maps for AAA character heads

### Advanced Animation

- [x] **ANIM3-01**: Claude can configure combat animation timing (anticipation frames, active frames, recovery frames per attack type)
- [x] **ANIM3-02**: Claude can inject animation events at specific keyframes (hit, VFX spawn, sound trigger, footstep)
- [x] **ANIM3-03**: Claude can generate blend trees for directional movement and speed blending
- [x] **ANIM3-04**: Claude can create additive animation layers (damage reactions on top of locomotion)
- [x] **ANIM3-05**: Claude can refine root motion curves (smooth drift, prevent sliding)
- [x] **ANIM3-06**: Claude can generate AI-driven motion (implement generate_ai_motion stub with MotionGPT/HunyuanVideo integration)
- [x] **ANIM3-07**: Claude can generate cinematic animation sequences (camera cuts, character staging, Timeline integration)

### Audio Middleware

- [x] **AUDM-01**: Claude can set up spatial audio system (3D sound propagation, distance attenuation, occlusion by geometry)
- [x] **AUDM-02**: Claude can create layered sound designs (combine multiple audio clips into complex impact/ability sounds)
- [x] **AUDM-03**: Claude can create audio event chains (impact → reverb tail → debris scatter trigger sequences)
- [x] **AUDM-04**: Claude can set up dynamic music system (horizontal re-sequencing, vertical layering, combat stingers)
- [x] **AUDM-05**: Claude can set up sound propagation through portals/doors (realistic attenuation between rooms)
- [x] **AUDM-06**: Claude can configure audio LOD (reduce quality/channels at distance for performance)
- [x] **AUDM-07**: Claude can set up dialogue/VO audio pipeline (lip sync markers, emotion tags, localized VO slots)
- [x] **AUDM-08**: Claude can generate procedural foley (cloth rustle, metal clinks, leather creaks based on movement speed and animation tags)

### AAA UI/UX Polish

- [x] **UIPOL-01**: Claude can generate procedural UI frames (ornate dark fantasy borders, rune decorations, weathered edges)
- [x] **UIPOL-02**: Claude can generate equipment/item icons via 3D render pipeline (render → stylize → border → background)
- [x] **UIPOL-03**: Claude can generate dark fantasy themed cursors (context-sensitive: default, interact, attack, loot)
- [x] **UIPOL-04**: Claude can generate tooltip system with rich content (item stats, lore text, equipment comparison)
- [x] **UIPOL-05**: Claude can generate radial menu (ability wheel, quick-select for items/spells)
- [x] **UIPOL-06**: Claude can generate notification/toast system (quest updates, item pickups, level-up, achievements)
- [x] **UIPOL-07**: Claude can generate loading screen system (tips, lore, concept art display with progress bar)
- [x] **UIPOL-08**: Claude can generate material-based UI shaders (gold-leaf shine, blood-stain overlays, dynamic rune glowing for dark fantasy UI elements)

### VFX Mastery

- [x] **VFX3-01**: Claude can generate flipbook texture sheets (animated sprite sequences for fire, smoke, energy effects)
- [x] **VFX3-02**: Claude can compose VFX Graph nodes programmatically (not just parameters — actual node graph construction)
- [x] **VFX3-03**: Claude can generate projectile VFX chains (spawn → travel trail → impact burst → aftermath residue)
- [x] **VFX3-04**: Claude can generate area-of-effect VFX (ground circles, expanding domes, cone blasts with brand colors)
- [x] **VFX3-05**: Claude can generate per-brand status effect VFX (burning, poisoned, frozen, stunned, blessed, cursed for all 10 brands)
- [x] **VFX3-06**: Claude can generate environmental VFX depth (volumetric fog, god rays, heat distortion, water caustics)
- [x] **VFX3-07**: Claude can generate directional combat hit VFX (blood splatter, sparks, energy bursts matched to brand)
- [x] **VFX3-08**: Claude can generate boss phase transition VFX (corruption wave, power surge, arena transformation)

### Production Pipeline

- [x] **PROD-01**: Claude can detect and auto-recover from Unity compilation errors (detect → diagnose → fix → recompile cycle)
- [x] **PROD-02**: Claude can detect asset/class name conflicts before writing (prevent duplicate type errors)
- [x] **PROD-03**: Claude can orchestrate multi-tool pipelines as single commands (character creation, level building)
- [x] **PROD-04**: Claude can validate art style consistency across batches of assets (palette, roughness, detail density checks)
- [x] **PROD-05**: Claude can run build verification smoke tests after every build

## Out of Scope (v3)

| Feature | Reason |
|---------|--------|
| Console SDK integration | Requires licensed devkits (PlayStation, Xbox, Switch) |
| Multiplayer/networking | VeilBreakers is single-player |
| Live ops infrastructure | Development tool, not production ops |
| Motion capture pipeline | Requires hardware; AI motion generation covers the use case |
| Soft body simulation | Beyond cloth — fluid, jelly, deformable terrain requires physics middleware |

## v3 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MESH3-01 | Phase 18 | Complete |
| MESH3-02 | Phase 18 | Complete |
| MESH3-03 | Phase 18 | Complete |
| MESH3-04 | Phase 18 | Complete |
| MESH3-05 | Phase 18 | Complete |
| TERR-01 | Phase 18 | Complete |
| TERR-02 | Phase 18 | Complete |
| TERR-03 | Phase 18 | Complete |
| TERR-04 | Phase 18 | Complete |
| TERR-05 | Phase 18 | Complete |
| CHAR-01 | Phase 19 | Complete |
| CHAR-02 | Phase 19 | Complete |
| CHAR-03 | Phase 19 | Complete |
| CHAR-04 | Phase 19 | Complete |
| CHAR-05 | Phase 19 | Complete |
| CHAR-06 | Phase 19 | Complete |
| CHAR-07 | Phase 19 | Complete |
| CHAR-08 | Phase 19 | Complete |
| ANIM3-01 | Phase 20 | Complete |
| ANIM3-02 | Phase 20 | Complete |
| ANIM3-03 | Phase 20 | Complete |
| ANIM3-04 | Phase 20 | Complete |
| ANIM3-05 | Phase 20 | Complete |
| ANIM3-06 | Phase 20 | Complete |
| ANIM3-07 | Phase 20 | Complete |
| AUDM-01 | Phase 21 | Complete |
| AUDM-02 | Phase 21 | Complete |
| AUDM-03 | Phase 21 | Complete |
| AUDM-04 | Phase 21 | Complete |
| AUDM-05 | Phase 21 | Complete |
| AUDM-06 | Phase 21 | Complete |
| AUDM-07 | Phase 21 | Complete |
| AUDM-08 | Phase 21 | Complete |
| UIPOL-01 | Phase 22 | Complete |
| UIPOL-02 | Phase 22 | Complete |
| UIPOL-03 | Phase 22 | Complete |
| UIPOL-04 | Phase 22 | Complete |
| UIPOL-05 | Phase 22 | Complete |
| UIPOL-06 | Phase 22 | Complete |
| UIPOL-07 | Phase 22 | Complete |
| UIPOL-08 | Phase 22 | Complete |
| VFX3-01 | Phase 23 | Complete |
| VFX3-02 | Phase 23 | Complete |
| VFX3-03 | Phase 23 | Complete |
| VFX3-04 | Phase 23 | Complete |
| VFX3-05 | Phase 23 | Complete |
| VFX3-06 | Phase 23 | Complete |
| VFX3-07 | Phase 23 | Complete |
| VFX3-08 | Phase 23 | Complete |
| PROD-01 | Phase 24 | Complete |
| PROD-02 | Phase 24 | Complete |
| PROD-03 | Phase 24 | Complete |
| PROD-04 | Phase 24 | Complete |
| PROD-05 | Phase 24 | Complete |

**Coverage:**
- v3 requirements: 56 total (across 8 categories), ALL COMPLETE
- Mapped to phases: 56/56
- Unmapped: 0

**Categories:** MESH3 (5), TERR (5), CHAR (8), ANIM3 (7), AUDM (8), UIPOL (8), VFX3 (8), PROD (5)

---
*Requirements defined: 2026-03-18 (v1), updated 2026-03-19 (v2), updated 2026-03-21 (v3 -- ALL COMPLETE)*

## v7.0 Requirements

Requirements for v7.0 — AAA Procedural City Production. IDs match PROJECT.md Active section.

> **Note:** v1 requirements (128 total including PIPE-01 through PIPE-07) are summarized by category count in the v1 section above but were never individually listed with descriptions in this file. The PIPE-01 below is a new v7.0 requirement, distinct from the v1 PIPE category.

### Mesh Quality

- [x] **MESH-01**: Every procedural mesh generator produces geometry with proper edge flow, zero non-manifold edges, and contact sheet showing silhouette distinguishable from primitive shapes — furniture >500 verts, buildings >2000 verts, vegetation >300 verts
- [x] **MESH-02**: All materials assigned via smart material system with roughness driven by noise texture nodes (never single float). Procedural materials baked to image textures (albedo, normal, roughness, metallic, AO) for export
- [x] **MESH-06**: Mesh topology passes game-readiness: zero non-manifold edges, consistent normals, UV coverage >0.8, no degenerate faces (<0.001 area), proper edge loops at deformation points

### Architecture & Interiors

- [ ] **MESH-03**: Interior rooms have purpose-driven furniture placement with spatial relationships (chairs face tables, beds have nightstands, work triangles in kitchens), 5-15 props per room, path to door always clear
- [ ] **MESH-04**: Building generation uses CGA-style split grammar for facades — footprint → extrude → split(floors) → split(bays) → fill(window|door|wall). No two buildings within line of sight have identical facade layouts
- [ ] **MESH-07**: Modular building kit has 50+ pieces per style on consistent snap grid. Includes: wall (straight/corner/window/door), floor, ceiling, roof (ridge/eave/hip/gable), stairs, trim, foundation. Straight skeleton roofs from arbitrary footprints

### Terrain & Environment

- [x] **MESH-05**: Terrain-building integration with foundation meshes, terrain flatten/cutout zones, and material blending at contact edges. Zero visible gaps in side-view verification
- [x] **MESH-09**: Voronoi-based biome distribution with 5+ biome types, corruption-aware tinting (0-100%), smooth 10-20m blend zones between biomes. Uses existing 14 biome palettes
- [x] **MESH-10**: Vegetation uses L-system branching for trees (not sphere clusters), 3+ species with leaf card geometry, billboard LOD fallback. Poisson disk scatter (Bridson's algorithm) for natural distribution

### Performance & Pipeline

- [x] **MESH-11**: LOD chain per asset type using existing lod_pipeline.py presets with silhouette preservation >85%. Scene budget validator enforces per-room (50K-150K tris) and per-block (200K-500K tris) polygon budgets
- [ ] **MESH-12**: Tripo pipeline with automatic post-processing: de-lighting, mesh repair, UV unwrap, PBR texture EXTRACTION from GLB into standalone maps (not blank images), LOD generation, quality gate
- [ ] **MESH-13**: Starter town: 10-15 buildings with furnished interiors, market area, fortifications, road network, vegetation, terrain integration. Exports to Unity as Addressables-ready package, maintains 60fps at 1080p
- [x] **MESH-14**: All 267 generators use seed-based RNG (`random.Random(seed)`) exclusively — zero instances of global random state. Same seed produces identical output
- [x] **MESH-15**: Boolean cleanup pipeline: remove doubles (0.0001 merge distance), recalculate normals, fix non-manifold edges, fill holes (up to 8 sides). Runs automatically after every boolean operation

### Infrastructure

- [ ] **MESH-08**: City infrastructure with road MESH generation (curbs, cobblestones, intersections), market stalls, wells, lamp posts, benches. Road network connects all buildings via L-system or tensor field approach
- [ ] **MESH-16**: Clean commit workflow — atomic commits after every bug/error scan, state tracked in STATE.md
- [ ] **PIPE-01**: AAA technique research documented: CGA split grammars, WFC, L-systems, hydraulic erosion (50K+ droplets), Poisson disk sampling, straight skeleton roofs, domain warping

### Requirement-to-Phase Mapping

| Requirement | Phase | Description |
|---|---|---|
| MESH-01, MESH-02, MESH-06, MESH-11, MESH-14, MESH-15 | Phase 30 (P0) | Mesh Foundation |
| MESH-05, MESH-09, MESH-10 | Phase 31 (P1) | Terrain & Environment |
| MESH-04, MESH-07 | Phase 32 (P2) | Building System |
| MESH-03 | Phase 33 (P3) | Interior System |
| MESH-05, MESH-09, MESH-10 | Phase 34 (P4) | Multi-biome Terrain |
| MESH-12 | Phase 35 (P5) | Multi-backend AI |
| MESH-08 | Phase 36 (P6) | World Composer |
| MESH-16, PIPE-01 | Phase 37 (P7) | Pipeline Integration |
| MESH-13 | Phase 38 (P8) | Starter Town |
