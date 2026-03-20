# Phase 14: Camera, Cinematics & Scene Management - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (autonomous mode)

<domain>
## Phase Boundary

Camera systems (Cinemachine 3.x virtual cameras, shake/zoom/transitions), Timeline/cutscene creation, multi-scene management (async loading, transitions, bootstrapper), scene environment (reflection probes, light probes, occlusion culling, HDR skybox, GI, terrain detail), 2D systems (tilemaps, 2D physics), video playback, animation editing (AnimationClip keyframes, Animator Controller modification, Avatar Masks), world design (complete locations, furnished interiors, boss arenas, world graph, interior-exterior linking, multi-floor dungeons, furniture placement, time-of-day lighting, overrun variants, easter eggs), and RPG world systems (fast travel, environmental puzzles, dungeon traps, spatial loot, weather, day/night cycle, NPC placement, dungeon lighting, terrain-building blending).

Requirements: CAM-01 through CAM-04, SCNE-01 through SCNE-06, TWO-01, TWO-02, MEDIA-01, ANIMA-01 through ANIMA-03, AAA-05, WORLD-01 through WORLD-10, RPG-02, RPG-04, RPG-06, RPG-07, RPG-09 through RPG-13.

</domain>

<decisions>
## Implementation Decisions

### Camera Systems (CAM-01 through CAM-04)
- **Cinemachine 3.x API**: CinemachineCamera + OrbitalFollow/RotationComposer (NOT legacy 2.x FreeLook)
- **State-driven camera**: CinemachineStateDrivenCamera for gameplay state transitions
- **Camera shake**: CinemachineImpulseSource for screen shake effects
- **Zoom/transition**: CinemachineBlendDefinition for smooth camera cuts

### Timeline & Cutscenes (CAM-02, CAM-03)
- **Timeline asset generation**: Create .playable assets with animation, audio, activation, and Cinemachine tracks
- **Playable Director setup**: Configure PlayableDirector with Timeline bindings
- **Cutscene sequences**: Multi-track cutscenes with camera switching, audio, and character activation

### Scene Management (SCNE-01, SCNE-02)
- **Async scene loading**: SceneManager.LoadSceneAsync with additive/single modes
- **Scene transition system**: Loading screens, fade transitions, bootstrapper pattern
- **Match VeilBreakers flow**: Bootstrap → MainMenu → CharacterSelect → Overworld ↔ Battle

### Scene Environment (SCNE-03 through SCNE-06)
- **Reflection/light probes**: Programmatic placement with baking triggers
- **Occlusion culling**: Mark static occluders/occludees, bake data
- **HDR skybox + GI**: Environment reflections, skybox material, Global Illumination setup
- **Terrain detail**: Grass painting, detail meshes on Unity terrain

### 2D Systems (TWO-01, TWO-02)
- **Tilemap generation**: Create tilemaps with Tile Palettes and Rule Tiles
- **2D Physics**: Rigidbody2D, Collider2D, Physics2D settings, 2D joints

### Animation (ANIMA-01 through ANIMA-03)
- **AnimationClip editing**: Add/remove keyframes, modify curves programmatically
- **Animator Controller modification**: Add/remove states, configure transitions, sub-state machines
- **Avatar Masks**: Create masks for animation layer filtering

### World Design (WORLD-01 through WORLD-10)
- **Location generation from descriptions**: Complete explorable areas with paths, POIs, proper scale
- **16 furnished room types**: Tavern, throne room, prison, bedroom, kitchen, library, armory, temple, etc.
- **Boss arenas**: Fog gates, cover, hazard zones, phase triggers, 20-40m scale
- **World graph**: Connected locations with 30-second walking distances (~105m between POIs)
- **Interior-exterior linking**: Door triggers, occlusion zones, lighting transitions
- **Multi-floor dungeons**: Vertical progression, staircases, elevators, ladders
- **Real-world scale furniture**: Doors 1.0-1.2m, ceilings 2.8-3.5m, tables 0.75m
- **Time-of-day presets**: 8 presets (dawn through midnight) with matching fog/atmosphere
- **Overrun variants**: Debris, broken walls, overgrown vegetation, scattered remains
- **Easter eggs/hidden areas**: Secret rooms, hidden paths, lore items

### RPG World Systems (RPG-02, 04, 06, 07, 09-13)
- **Fast travel**: Discover waypoints by visiting, teleport between unlocked points
- **Environmental puzzles**: Lever sequences, pressure plates, key-and-lock, light beams
- **Dungeon traps**: Pressure plates, dart walls, spike pits, poison gas, swinging blades
- **Spatial loot**: Treasure chest positions, item drops in specific rooms
- **Weather system**: Rain/snow/fog/storms with smooth transitions
- **Day/night cycle**: Continuous time progression, lighting transitions, NPC schedule changes
- **NPC placement**: Shopkeeper/quest giver/guard positions inside buildings
- **Dungeon lighting**: Torch sconces every 4-6m, dark corridors, atmospheric fog
- **Terrain-building blending**: Vertex color at base, decal projection, terrain depression

### Claude's Discretion
- Cinemachine blend curve specifics
- Timeline track ordering and clip timing
- Scene loading progress bar implementation
- Probe placement density and baking quality
- Tilemap grid size and tile resolution
- AnimationClip curve interpolation mode
- World generation procedural algorithms
- Weather particle system density
- Day/night cycle duration

</decisions>

<canonical_refs>
## Canonical References

### VeilBreakers Game Project
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scenes/` — Existing scene structure
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Managers/SceneTransitionManager.cs` — Existing scene loading (if exists)

### Toolkit Implementation
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add unity_camera, unity_world compound tools
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` — Extend blender_worldbuilding, blender_environment

### Requirements
- `.planning/REQUIREMENTS.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 9 `unity_scene`: Existing terrain setup, lighting, NavMesh, animator (extend for new capabilities)
- Phase 12 `unity_game`: Character controller with Cinemachine 3.x camera (extend camera system)
- Blender `blender_environment`: Terrain, vegetation, water, breakable props
- Blender `blender_worldbuilding`: Dungeon, cave, town, building, castle, ruins, interior, modular kits

### Integration Points
- New `unity_camera` compound tool for Cinemachine/Timeline/cutscenes
- New `unity_world` compound tool for scene management, probes, occlusion, 2D, weather, day-night
- Extend existing Blender worldbuilding tools for world design requirements
- Extend `unity_scene` or create new actions for animation editing

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers already has Bootstrap → MainMenu → CharacterSelect → Overworld ↔ Battle flow — scene management should complement this
- Cinemachine 3.x is already used in Phase 12's character controller — camera systems extend this
- Blender worldbuilding tools already generate dungeons, caves, towns — WORLD requirements add higher-level composition and furnishing
- Dark fantasy aesthetic drives all visual decisions — time-of-day, weather, dungeon lighting

</specifics>

<deferred>
## Deferred Ideas

None — autonomous mode stayed within phase scope

</deferred>

---

*Phase: 14-camera-cinematics-scene-management*
*Context gathered: 2026-03-20 via autonomous mode*
