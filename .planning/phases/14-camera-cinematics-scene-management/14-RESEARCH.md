# Phase 14: Camera, Cinematics & Scene Management - Research

**Researched:** 2026-03-20
**Domain:** Unity C# template generation for camera systems (Cinemachine 3.x), Timeline/cutscenes, scene management, scene environment (probes, occlusion, GI), 2D systems (Tilemap, 2D physics), video playback, animation editing (AnimationClip/Animator/AvatarMask) + Blender Python handlers for world design (locations, interiors, boss arenas, world graph, time-of-day, overrun variants) + Unity C# for RPG world systems (fast travel, puzzles, traps, spatial loot, weather, day/night, NPC placement, dungeon lighting, terrain-building blending)
**Confidence:** HIGH

## Summary

Phase 14 is the largest phase in v2.0 with 36 requirements spanning 7 distinct domains: (1) Camera systems with Cinemachine 3.x virtual cameras, state-driven cameras, impulse/shake, and blend transitions; (2) Timeline and cutscene authoring via PlayableDirector; (3) Scene management with async loading, transitions, and bootstrapper pattern; (4) Scene environment setup (reflection probes, light probes, occlusion culling, HDR skybox, GI, terrain detail); (5) 2D systems (Tilemaps, 2D physics), video playback, and animation editing; (6) Blender-side world design extending existing worldbuilding/environment handlers (complete locations, 16 furnished room types, boss arenas, world graph, multi-floor dungeons, furniture scale, time-of-day presets, overrun variants, easter eggs); and (7) Unity RPG world systems generating runtime C# for fast travel, environmental puzzles, dungeon traps, spatial loot, weather, day/night cycle, NPC placement, dungeon lighting, and terrain-building blending.

The Unity camera and cinematics systems follow the established C# template generation pattern: Python generator functions produce C# editor scripts written to `Assets/Editor/Generated/` directories, registered under `VeilBreakers/` menu items. The existing Phase 12 character controller already demonstrates Cinemachine 3.x patterns (CinemachineCamera + CinemachineOrbitalFollow + CinemachineRotationComposer in game_templates.py). Phase 14 camera tools generalize this to configurable virtual camera creation, state-driven camera management, impulse sources, and Timeline authoring. The Blender world design requirements extend the existing `_building_grammar.py` interior system (currently 8 room types, needs 8 more) and worldbuilding handlers. Unity RPG world systems generate runtime MonoBehaviours following the Phase 12/13 pattern.

This phase creates two new Unity compound tools (`unity_camera` with ~12 actions for cameras/timeline/animation, `unity_world` with ~16 actions for scenes/environment/2D/weather/RPG systems) and extends existing Blender handlers (`blender_worldbuilding` + `blender_environment`) with new actions for world design requirements. The split into two new Unity tools avoids overloading the existing `unity_scene` tool (already 7 actions) and keeps tool boundaries clean.

**Primary recommendation:** Split into 4 plans: (1) Camera + Timeline template generators + `unity_camera` compound tool (CAM-01/02/03/04, ANIMA-01/02/03, MEDIA-01), (2) Scene management + environment templates + 2D + `unity_world` compound tool (SCNE-01/02/03/04/05/06, TWO-01/02), (3) Blender world design extensions (WORLD-01 through WORLD-10, AAA-05), (4) RPG world systems templates + tool wiring + integration tests (RPG-02/04/06/07/09/10/11/12/13).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Cinemachine 3.x API**: CinemachineCamera + OrbitalFollow/RotationComposer (NOT legacy 2.x FreeLook)
- **State-driven camera**: CinemachineStateDrivenCamera for gameplay state transitions
- **Camera shake**: CinemachineImpulseSource for screen shake effects
- **Zoom/transition**: CinemachineBlendDefinition for smooth camera cuts
- **Timeline asset generation**: Create .playable assets with animation, audio, activation, and Cinemachine tracks
- **Playable Director setup**: Configure PlayableDirector with Timeline bindings
- **Cutscene sequences**: Multi-track cutscenes with camera switching, audio, and character activation
- **Async scene loading**: SceneManager.LoadSceneAsync with additive/single modes
- **Scene transition system**: Loading screens, fade transitions, bootstrapper pattern
- **Match VeilBreakers flow**: Bootstrap -> MainMenu -> CharacterSelect -> Overworld <-> Battle
- **Reflection/light probes**: Programmatic placement with baking triggers
- **Occlusion culling**: Mark static occluders/occludees, bake data
- **HDR skybox + GI**: Environment reflections, skybox material, Global Illumination setup
- **Terrain detail**: Grass painting, detail meshes on Unity terrain
- **Tilemap generation**: Create tilemaps with Tile Palettes and Rule Tiles
- **2D Physics**: Rigidbody2D, Collider2D, Physics2D settings, 2D joints
- **AnimationClip editing**: Add/remove keyframes, modify curves programmatically
- **Animator Controller modification**: Add/remove states, configure transitions, sub-state machines
- **Avatar Masks**: Create masks for animation layer filtering
- **Location generation from descriptions**: Complete explorable areas with paths, POIs, proper scale
- **16 furnished room types**: Tavern, throne room, prison, bedroom, kitchen, library, armory, temple, blacksmith, guard barracks, treasury, war room, alchemy lab, torture chamber, crypt, dining hall
- **Boss arenas**: Fog gates, cover, hazard zones, phase triggers, 20-40m scale
- **World graph**: Connected locations with 30-second walking distances (~105m between POIs)
- **Interior-exterior linking**: Door triggers, occlusion zones, lighting transitions
- **Multi-floor dungeons**: Vertical progression, staircases, elevators, ladders
- **Real-world scale furniture**: Doors 1.0-1.2m, ceilings 2.8-3.5m, tables 0.75m
- **Time-of-day presets**: 8 presets (dawn through midnight) with matching fog/atmosphere
- **Overrun variants**: Debris, broken walls, overgrown vegetation, scattered remains
- **Easter eggs/hidden areas**: Secret rooms, hidden paths, lore items
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

### Deferred Ideas (OUT OF SCOPE)
None -- autonomous mode stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAM-01 | Create/configure Cinemachine virtual cameras (FreeLook, follow, state-driven, blending) | Cinemachine 3.x: CinemachineCamera + OrbitalFollow + RotationComposer + StateDrivenCamera; existing pattern in game_templates.py VB_CameraSetup |
| CAM-02 | Create Timeline assets with animation, audio, activation, Cinemachine tracks | TimelineAsset.CreateTrack<T>() API; AnimationTrack, AudioTrack, ActivationTrack, CinemachineTrack from com.unity.timeline + com.unity.cinemachine |
| CAM-03 | Set up cutscene sequences using Playable Director with Timeline | PlayableDirector.playableAsset assignment; SetGenericBinding for track-to-object bindings; wrap mode and play-on-awake config |
| CAM-04 | Configure camera shake, zoom, and transition effects | CinemachineImpulseSource.GenerateImpulse(); CinemachineBlendDefinition struct; CinemachineBrain default blend settings |
| SCNE-01 | Create new Unity scenes and configure scene loading | SceneManager.LoadSceneAsync with LoadSceneMode.Additive/Single; EditorSceneManager.NewScene for editor creation |
| SCNE-02 | Generate scene transition system (loading screens, fade, bootstrapper) | Bootstrap scene pattern with DontDestroyOnLoad; coroutine-based async loading with progress; UI Toolkit fade overlay |
| SCNE-03 | Set up reflection probes, light probes, probe groups | ReflectionProbe component (mode, resolution, boxSize); LightProbeGroup with programmatic positions |
| SCNE-04 | Configure occlusion culling (mark static, bake data) | StaticEditorFlags.OccluderStatic/OccludeeStatic; StaticOcclusionCulling.Compute() for baking |
| SCNE-05 | Set up HDR skybox, environment reflections, GI | RenderSettings.skybox/ambientMode/defaultReflectionMode; Lightmapping.BakeAsync() for GI; skybox material creation |
| SCNE-06 | Generate terrain detail painting (grass, detail meshes) | TerrainData.detailPrototypes for grass/detail mesh config; SetDetailLayer for painting density maps |
| TWO-01 | Create/paint 2D Tilemaps with Tile Palettes and Rule Tiles | Tilemap.SetTile/SetTiles; RuleTile SO creation with tiling rules; GridLayout.CellLayout config |
| TWO-02 | Configure 2D Physics (Rigidbody2D, Collider2D, settings, joints) | Rigidbody2D/BoxCollider2D/CircleCollider2D/CompositeCollider2D; Physics2D.gravity; HingeJoint2D/SpringJoint2D/DistanceJoint2D |
| MEDIA-01 | Configure VideoPlayer for video playback and render texture output | VideoPlayer.renderMode = RenderTexture; targetTexture assignment; VideoClip loading |
| ANIMA-01 | Edit AnimationClips (add/remove keyframes, modify curves) | AnimationUtility.SetEditorCurve + EditorCurveBinding for float properties; AnimationCurve with Keyframe[] construction |
| ANIMA-02 | Modify existing Animator Controllers (add/remove states, transitions, sub-state machines) | AnimatorController from UnityEditor.Animations; layers[0].stateMachine.AddState/AddTransition/AddStateMachine |
| ANIMA-03 | Create Avatar Masks for animation layer filtering | AvatarMask constructor + SetHumanoidBodyPartActive(AvatarMaskBodyPart, bool) + SetTransformActive for custom bones |
| AAA-05 | Add storytelling props (clutter, wall decor, narrative detail) to any interior | Extend _building_grammar.py generate_interior_layout with layer-3 clutter items; random placement with density control |
| WORLD-01 | Generate complete explorable locations from text descriptions | Blender handler: compose terrain + buildings + paths + POIs; use existing blender_environment terrain + blender_worldbuilding buildings |
| WORLD-02 | Generate fully furnished building interiors for 16 room types | Extend _ROOM_CONFIGS in _building_grammar.py from 8 to 16 types; add blacksmith/guard_barracks/treasury/war_room/alchemy_lab/torture_chamber/crypt/dining_hall |
| WORLD-03 | Generate boss arena environments (fog gates, cover, hazards, 20-40m scale) | New handler: generate circular/rectangular arena 20-40m; place cover objects/hazard zones/phase trigger markers; fog gate at entrance |
| WORLD-04 | Connect locations into world graph (30-second rule, ~105m between POIs) | Pure-logic world graph with nodes/edges; path generation between POIs; validate walking distance constraints |
| WORLD-05 | Generate interior-exterior linked buildings (door triggers, occlusion, lighting) | Handler: emit door_trigger, occlusion_zone, lighting_transition markers in geometry ops; Unity side handles runtime behavior |
| WORLD-06 | Generate multi-floor dungeon layouts with vertical progression | Extend _dungeon_gen.py with per-floor grids; staircase/elevator/ladder/pit_drop connection types between floors |
| WORLD-07 | Place furniture at correct real-world scale | Validate furniture dimensions against reference table (doors 1.0-1.2m, ceilings 2.8-3.5m, tables 0.75m); scale enforcement in interior layout |
| WORLD-08 | Apply time-of-day lighting presets (8 presets) | Extend _TIME_OF_DAY_PRESETS in scene_templates.py from 5 to 8 (add morning, afternoon, evening, midnight); Unity C# applies full scene preset |
| WORLD-09 | Generate overrun/ruined variants of intact locations | Extend existing apply_ruins_damage in _building_grammar.py; add debris, broken walls, overgrown vegetation, scattered remains |
| WORLD-10 | Place easter eggs and hidden areas | Handler: generate secret_room (breakable wall), hidden_path (off main route), lore_item (unexpected location) markers |
| RPG-02 | Fast travel/waypoint system | C# template: WaypointManager MonoBehaviour; discover on trigger enter; teleport with loading transition; save/load discovered list |
| RPG-04 | Environmental puzzle mechanics | C# template: PuzzleMechanic base class; LeverSequencePuzzle, PressurePlatePuzzle, KeyLockPuzzle, LightBeamPuzzle subclasses |
| RPG-06 | Dungeon trap mechanics | C# template: TrapBase MonoBehaviour; PressurePlateTrap, DartWallTrap, SpikePitTrap, PoisonGasTrap, SwingingBladeTrap implementations |
| RPG-07 | Spatial loot placement in dungeons | C# template: SpatialLootManager; treasure chest prefab positions; room-based item drop tables; treasure room layouts |
| RPG-09 | Weather system with state management | C# template: WeatherManager (rain/snow/fog/storms); particle systems per weather type; smooth transitions via coroutine lerp |
| RPG-10 | Day/night runtime cycle | C# template: DayNightCycleManager; continuous time progression; lighting preset transitions; NPC schedule callback; enemy behavior shift |
| RPG-11 | Friendly NPC placement markers inside buildings | C# template: NPCPlacementMarker SO; shopkeeper/quest_giver/bartender/guard positions; spawn on scene load |
| RPG-12 | Dungeon-specific lighting (torch sconces, dark corridors, fog) | C# template: DungeonLightingSetup; torch sconces every 4-6m along corridors; light pools around fire; atmospheric fog zones |
| RPG-13 | Terrain-building blending (vertex color, decals, depression) | C# template: TerrainBuildingBlend; vertex color painting at structure base; decal projector placement; terrain height depression |

</phase_requirements>

## Standard Stack

### Core (Unity / C# -- generated by templates)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Unity Cinemachine | 3.1.x (com.unity.cinemachine) | Virtual cameras, state-driven cameras, impulse/shake, blending | Official Unity camera package; 3.x API with CinemachineCamera (not legacy FreeLook); already used in Phase 12 |
| Unity Timeline | 1.8.x (com.unity.timeline) | Timeline assets, PlayableDirector, cutscene authoring | Official Unity package for cinematic sequences; TimelineAsset.CreateTrack<T> API |
| Unity 2D Tilemap | Built-in (Unity 6) | Tilemap, Tile Palette, Rule Tiles | Built-in 2D system; Tilemap.SetTile/SetTiles API |
| Unity Video | Built-in (Unity 6) | VideoPlayer component, RenderTexture output | Built-in media playback; VideoPlayer + RenderTexture pattern |
| Unity UI Toolkit | Built-in (Unity 6) | Loading screen, weather HUD, fade overlay | Matches VeilBreakers existing UI approach from all prior phases |
| ScriptableObject | Built-in (Unity 6) | Weather presets, NPC placement data, loot tables, puzzle configs | Standard data-driven design pattern throughout project |

### Toolkit (Python -- template generators + Blender handlers)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastMCP | 1.26+ | MCP server framework | Tool registration for unity_camera and unity_world compound tools |
| pytest | 8.0+ | Template + handler validation | C# syntax verification + Blender handler logic tests |
| bpy | 4.x (Blender built-in) | World design geometry generation | All WORLD-01 through WORLD-10 Blender operations |
| bmesh | 4.x (Blender built-in) | Procedural mesh for arenas, locations, interiors | Location, arena, and interior mesh construction |
| numpy | (already installed) | Dungeon grid operations, world graph | Multi-floor dungeon grids, world graph distance calculations |

### No New Python Dependencies
This phase adds zero new Python pip dependencies. All Blender operations use bpy/bmesh/mathutils/numpy (already in use). Unity operations use built-in Unity 6 APIs plus Cinemachine 3.x and Timeline packages (both already referenced in project).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CinemachineStateDrivenCamera | Manual camera switching via Priority | State-driven is user decision; cleaner for Animator-linked states |
| TimelineAsset.CreateTrack<T> | Runtime Playable API | Timeline is the standard authoring approach; Playable API is lower-level and harder to debug |
| SceneManager.LoadSceneAsync | Addressables scene loading | Addressables adds complexity; standard scene loading sufficient for VeilBreakers flow |
| Built-in Tilemap | SuperTiled2Unity | Built-in is zero dependencies, sufficient for toolkit scope |
| AnimationUtility.SetEditorCurve | AnimationClip.SetCurve | SetCurve is runtime-only for legacy clips; SetEditorCurve works in editor for all clip types |

## Architecture Patterns

### Recommended Project Structure (New Files)
```
Tools/mcp-toolkit/src/veilbreakers_mcp/
  shared/unity_templates/
    camera_templates.py           # NEW: Cinemachine, Timeline, cutscene, animation editing generators
    world_templates.py            # NEW: Scene management, environment, 2D, weather, RPG world generators
  unity_server.py                 # EXTEND: Add unity_camera + unity_world compound tools

Tools/mcp-toolkit/blender_addon/handlers/
  _building_grammar.py            # EXTEND: 8 new room types, boss arena spec, world graph, overrun variant logic
  _dungeon_gen.py                 # EXTEND: Multi-floor dungeon generation
  worldbuilding.py                # EXTEND: New handlers for locations, arenas, easter eggs, world graph
  environment.py                  # EXTEND: Time-of-day presets, dungeon lighting placement

Tools/mcp-toolkit/tests/
  test_camera_templates.py        # NEW: Camera/Timeline/animation C# syntax tests
  test_world_templates.py         # NEW: Scene/environment/2D/RPG world C# syntax tests
  test_worldbuilding_v2.py        # NEW: World design handler logic tests (locations, arenas, world graph)
```

### Generated C# Output Structure
```
Assets/
  Editor/Generated/
    Camera/                        # Editor scripts (MenuItem-based)
      VeilBreakers_CinemachineSetup.cs
      VeilBreakers_TimelineSetup.cs
      VeilBreakers_CutsceneSetup.cs
      VeilBreakers_AnimClipEditor.cs
      VeilBreakers_AnimatorEditor.cs
      VeilBreakers_AvatarMaskSetup.cs
    World/
      VeilBreakers_SceneManager.cs
      VeilBreakers_ProbeSetup.cs
      VeilBreakers_OcclusionSetup.cs
      VeilBreakers_EnvironmentSetup.cs
      VeilBreakers_TilemapSetup.cs
      VeilBreakers_2DPhysicsSetup.cs
      VeilBreakers_VideoPlayerSetup.cs
  Scripts/Runtime/
    WorldSystems/                  # Runtime MonoBehaviours
      VB_SceneTransitionManager.cs
      VB_WaypointManager.cs
      VB_WeatherManager.cs
      VB_DayNightCycleManager.cs
      VB_PuzzleMechanics.cs
      VB_TrapSystem.cs
      VB_SpatialLootManager.cs
      VB_NPCPlacementManager.cs
      VB_DungeonLightingSetup.cs
      VB_TerrainBuildingBlend.cs
```

### Pattern 1: Unity Camera Compound Tool
**What:** New `unity_camera` compound tool with ~12 actions covering all camera, timeline, animation editing requirements.
**When to use:** All CAM-01 through CAM-04, ANIMA-01 through ANIMA-03, MEDIA-01 requirements.
**Example:**
```python
# Source: Established compound tool pattern from unity_scene, unity_gameplay
@mcp.tool()
async def unity_camera(
    action: Literal[
        "create_virtual_camera",      # CAM-01: CinemachineCamera setup
        "create_state_driven_camera", # CAM-01: CinemachineStateDrivenCamera
        "create_camera_shake",        # CAM-04: CinemachineImpulseSource
        "configure_blend",            # CAM-04: CinemachineBlendDefinition
        "create_timeline",            # CAM-02: TimelineAsset with tracks
        "create_cutscene",            # CAM-03: PlayableDirector setup
        "edit_animation_clip",        # ANIMA-01: Add/remove keyframes
        "modify_animator",            # ANIMA-02: States/transitions/sub-states
        "create_avatar_mask",         # ANIMA-03: Body part masks
        "setup_video_player",         # MEDIA-01: VideoPlayer + RenderTexture
    ],
    ...
) -> str:
```

### Pattern 2: Unity World Compound Tool
**What:** New `unity_world` compound tool with ~16 actions covering scene management, environment, 2D, and RPG world systems.
**When to use:** All SCNE-01 through SCNE-06, TWO-01, TWO-02, RPG-02/04/06/07/09/10/11/12/13 requirements.
**Example:**
```python
@mcp.tool()
async def unity_world(
    action: Literal[
        "create_scene",               # SCNE-01: Scene creation + loading
        "create_transition_system",   # SCNE-02: Bootstrap + loading screens
        "setup_probes",               # SCNE-03: Reflection + light probes
        "setup_occlusion",            # SCNE-04: Occlusion culling
        "setup_environment",          # SCNE-05: HDR skybox + GI
        "paint_terrain_detail",       # SCNE-06: Grass + detail meshes
        "create_tilemap",             # TWO-01: Tilemap + Rule Tiles
        "setup_2d_physics",           # TWO-02: 2D physics config
        "create_fast_travel",         # RPG-02: Waypoint system
        "create_puzzle",              # RPG-04: Environmental puzzles
        "create_trap",                # RPG-06: Dungeon traps
        "create_spatial_loot",        # RPG-07: Loot placement
        "create_weather",             # RPG-09: Weather system
        "create_day_night",           # RPG-10: Day/night cycle
        "create_npc_placement",       # RPG-11: NPC markers
        "create_dungeon_lighting",    # RPG-12: Torch sconces + fog
        "create_terrain_blend",       # RPG-13: Building blending
    ],
    ...
) -> str:
```

### Pattern 3: Blender World Design Extensions
**What:** Extend existing `blender_worldbuilding` and `blender_environment` tools with new actions for world design.
**When to use:** All WORLD-01 through WORLD-10, AAA-05 requirements.
**Actions to add to `blender_worldbuilding`:**
- `generate_location` (WORLD-01): Compose terrain + buildings + paths + POIs
- `generate_boss_arena` (WORLD-03): Arena with cover, hazards, fog gates
- `generate_world_graph` (WORLD-04): Connected location graph
- `generate_linked_interior` (WORLD-05): Interior-exterior linked buildings
- `generate_multi_floor_dungeon` (WORLD-06): Vertical dungeon progression
- `generate_overrun_variant` (WORLD-09): Ruined version of location
- `generate_easter_egg` (WORLD-10): Secret rooms and hidden areas

**Actions to add/extend in `blender_environment`:**
- Extend time-of-day presets from 5 to 8 (WORLD-08)

### Pattern 4: Template Generator Functions
**What:** Each C# template generator follows the established line-by-line pattern with `_sanitize_cs_string` and `_sanitize_cs_identifier`.
**Example:**
```python
# Source: Established pattern from scene_templates.py, game_templates.py
def generate_cinemachine_setup_script(
    camera_type: str = "orbital",
    follow_target: str = "",
    look_at_target: str = "",
    priority: int = 10,
    radius: float = 5.0,
    impulse_force: float = 0.5,
    namespace: str = "VeilBreakers.CameraSystems",
) -> str:
    """Generate C# editor script for Cinemachine 3.x camera setup."""
    lines = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using Unity.Cinemachine;")
    # ... line-by-line C# generation
```

### Anti-Patterns to Avoid
- **Overloading unity_scene:** Do NOT add 20+ more actions to the existing 7-action tool. Create separate compound tools instead.
- **Legacy Cinemachine 2.x API:** Do NOT use CinemachineFreeLook, CinemachineVirtualCamera (2.x classes). Always use CinemachineCamera (3.x).
- **AnimationClip.SetCurve for editor clips:** SetCurve only works at runtime for legacy clips. Use AnimationUtility.SetEditorCurve for editor-based curve manipulation.
- **Direct bpy imports in pure-logic code:** Keep geometry computation in pure-logic functions (testable without Blender), only use bpy in handler functions.
- **Monolithic template files:** With 36 requirements, split templates into camera_templates.py and world_templates.py (not one giant file).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Camera blending curves | Custom lerp between camera transforms | CinemachineBlendDefinition + CinemachineBrain | Handles easing, cut-to-cut blending, custom curves natively |
| Screen shake | Random transform offset per frame | CinemachineImpulseSource + CinemachineImpulseListener | Handles attenuation, frequency, directional impulse |
| Timeline track creation | Manual PlayableGraph construction | TimelineAsset.CreateTrack<AnimationTrack>() etc. | Handles serialization, clip placement, binding management |
| Scene loading progress | Manual coroutine with progress polling | AsyncOperation.progress + allowSceneActivation pattern | Built-in Unity pattern, handles activation gating |
| Occlusion culling | Custom frustum culling script | StaticEditorFlags + StaticOcclusionCulling.Compute() | Hardware-accelerated, handles portal culling natively |
| Day/night sky blending | Custom skybox shader with time uniform | Existing time-of-day presets + RenderSettings lerp | Presets already defined in scene_templates.py; extend to 8 |
| Furniture collision avoidance | Custom placement grid | Existing generate_interior_layout with occupied-box check | Already implemented in _building_grammar.py with wall/center/corner rules |
| Weather transitions | Abrupt particle system enable/disable | Coroutine-based ParticleSystem.emission rate lerp | Smooth transitions between weather states |

**Key insight:** The existing codebase already has partial implementations for several of these areas (5 time-of-day presets, 8 room types, interior layout algorithm, Cinemachine 3.x camera creation). Phase 14 extends rather than rebuilds.

## Common Pitfalls

### Pitfall 1: Cinemachine 2.x vs 3.x API Confusion
**What goes wrong:** Using `CinemachineFreeLook` or `CinemachineVirtualCamera` which are Cinemachine 2.x classes, not available in Cinemachine 3.x.
**Why it happens:** Training data and many online tutorials reference 2.x API.
**How to avoid:** Always use `CinemachineCamera` (3.x). The namespace is `Unity.Cinemachine` (not `Cinemachine`). Key 3.x classes: CinemachineCamera, CinemachineOrbitalFollow, CinemachineRotationComposer, CinemachineStateDrivenCamera, CinemachineImpulseSource.
**Warning signs:** Any import of `using Cinemachine;` (should be `using Unity.Cinemachine;`).

### Pitfall 2: Timeline Track Creation Requires Asset in Database
**What goes wrong:** Creating tracks on a TimelineAsset that hasn't been saved to AssetDatabase causes clips to not persist.
**Why it happens:** Timeline tracks and clips are sub-assets that must be serialized.
**How to avoid:** Always `AssetDatabase.CreateAsset(timelineAsset, path)` before calling `CreateTrack<T>()`, then `AssetDatabase.SaveAssets()` after.
**Warning signs:** Timeline works in editor but tracks are empty on restart.

### Pitfall 3: AnimationClip.SetCurve vs AnimationUtility.SetEditorCurve
**What goes wrong:** Using SetCurve on non-legacy clips in editor context silently fails.
**Why it happens:** SetCurve is documented as working, but editor clips need AnimationUtility.SetEditorCurve with EditorCurveBinding.
**How to avoid:** Always use `AnimationUtility.SetEditorCurve(clip, binding, curve)` in editor scripts. Create bindings with `EditorCurveBinding.FloatCurve(relativePath, typeof(Component), propertyName)`.
**Warning signs:** Curves appear to be set but are empty when inspected.

### Pitfall 4: Scene Loading Additive Mode Unloads Existing Scenes
**What goes wrong:** Calling LoadSceneAsync without specifying LoadSceneMode.Additive causes current scene to unload.
**Why it happens:** Default LoadSceneMode is Single (unloads current scene).
**How to avoid:** Always explicitly specify `LoadSceneMode.Additive` for multi-scene setups. Use `SceneManager.UnloadSceneAsync` for explicit scene removal.
**Warning signs:** Objects disappearing when loading new scene.

### Pitfall 5: Reflection Probe Baking Mode Mismatch
**What goes wrong:** Setting probe to Realtime but expecting baked quality, or vice versa.
**Why it happens:** Baked probes require StaticEditorFlags on objects; Realtime probes use GPU at runtime.
**How to avoid:** For editor setup, use `ReflectionProbeMode.Baked` with bake trigger. For runtime, use `ReflectionProbeMode.Realtime` with appropriate refresh settings.
**Warning signs:** Black/missing reflections in probes.

### Pitfall 6: Existing Interior Room Types Need Careful Extension
**What goes wrong:** Adding new room types with furniture sizes that violate real-world scale constraints.
**Why it happens:** WORLD-07 mandates specific dimensions (doors 1.0-1.2m, ceilings 2.8-3.5m, tables 0.75m).
**How to avoid:** Create a FURNITURE_SCALE_REFERENCE dict with validated dimensions. All new room configs must reference this. Add validation tests.
**Warning signs:** Furniture clipping through walls, oversized or undersized props.

### Pitfall 7: Multi-Floor Dungeon Grid Alignment
**What goes wrong:** Staircase connections between floors don't align with walkable cells.
**Why it happens:** Each floor grid is generated independently without coordination.
**How to avoid:** Generate staircase positions first, then constrain floor grids to have walkable cells at staircase endpoints. Use a shared `connection_points` list across floors.
**Warning signs:** Stairs leading into walls.

## Code Examples

Verified patterns from official sources and existing codebase:

### Cinemachine 3.x Virtual Camera Setup (C# template output)
```csharp
// Source: Unity Cinemachine 3.1 API docs + existing game_templates.py VB_CameraSetup
using UnityEngine;
using UnityEditor;
using Unity.Cinemachine;

public static class VeilBreakers_CinemachineSetup
{
    [MenuItem("VeilBreakers/Camera/Setup Virtual Camera")]
    public static void Execute()
    {
        // Create CinemachineCamera (3.x API -- NOT CinemachineVirtualCamera)
        GameObject camGo = new GameObject("VB_CinemachineCamera");
        CinemachineCamera cm = camGo.AddComponent<CinemachineCamera>();
        cm.Priority.Value = 10;

        // Follow/LookAt targets
        // cm.Follow = followTarget;
        // cm.LookAt = lookAtTarget;

        // OrbitalFollow for third-person orbit
        CinemachineOrbitalFollow orbital = camGo.AddComponent<CinemachineOrbitalFollow>();
        orbital.Radius = 5f;
        orbital.TargetOffset = new Vector3(0f, 1.5f, 0f);

        // RotationComposer for look-at tracking
        CinemachineRotationComposer composer = camGo.AddComponent<CinemachineRotationComposer>();
        composer.Damping = new Vector3(1f, 0.5f, 0f);
    }
}
```

### CinemachineStateDrivenCamera (C# template output)
```csharp
// Source: Unity Cinemachine 3.1 API docs
using Unity.Cinemachine;
using UnityEngine;
using UnityEditor;

public static class VeilBreakers_StateDrivenCamera
{
    [MenuItem("VeilBreakers/Camera/Setup State-Driven Camera")]
    public static void Execute()
    {
        GameObject sdGo = new GameObject("VB_StateDrivenCamera");
        CinemachineStateDrivenCamera sdc = sdGo.AddComponent<CinemachineStateDrivenCamera>();

        // Assign Animator for state detection
        // sdc.AnimatedTarget = animator;

        // Child cameras are added as children of this GameObject
        // State-to-camera mappings configured via Instructions array
    }
}
```

### Timeline Asset Creation (C# template output)
```csharp
// Source: Unity Timeline 1.7+ API docs
using UnityEngine;
using UnityEditor;
using UnityEngine.Timeline;
using UnityEngine.Playables;
using Unity.Cinemachine;

public static class VeilBreakers_TimelineSetup
{
    [MenuItem("VeilBreakers/Camera/Create Timeline")]
    public static void Execute()
    {
        // Create and save TimelineAsset
        TimelineAsset timeline = ScriptableObject.CreateInstance<TimelineAsset>();
        string path = "Assets/Timelines/VB_Cutscene.playable";
        AssetDatabase.CreateAsset(timeline, path);

        // Add tracks (MUST happen after CreateAsset for persistence)
        var animTrack = timeline.CreateTrack<AnimationTrack>(null, "Character Animation");
        var audioTrack = timeline.CreateTrack<AudioTrack>(null, "Dialogue Audio");
        var activationTrack = timeline.CreateTrack<ActivationTrack>(null, "Props");
        // CinemachineTrack for camera cuts
        var cinemachineTrack = timeline.CreateTrack<CinemachineTrack>(null, "Camera Cuts");

        AssetDatabase.SaveAssets();
    }
}
```

### AnimationClip Curve Editing (C# template output)
```csharp
// Source: Unity AnimationUtility API docs
using UnityEngine;
using UnityEditor;

public static class VeilBreakers_AnimClipEditor
{
    [MenuItem("VeilBreakers/Camera/Edit Animation Clip")]
    public static void Execute()
    {
        // Create or load clip
        AnimationClip clip = new AnimationClip();
        clip.name = "VB_CustomClip";

        // Create curve binding
        EditorCurveBinding binding = EditorCurveBinding.FloatCurve(
            "",                    // relativePath (empty = root)
            typeof(Transform),     // component type
            "localPosition.x"     // property name
        );

        // Create keyframes
        Keyframe[] keys = new Keyframe[]
        {
            new Keyframe(0f, 0f),
            new Keyframe(0.5f, 2f),
            new Keyframe(1f, 0f),
        };
        AnimationCurve curve = new AnimationCurve(keys);

        // Apply curve to clip (editor API)
        AnimationUtility.SetEditorCurve(clip, binding, curve);

        AssetDatabase.CreateAsset(clip, "Assets/Animations/VB_CustomClip.anim");
        AssetDatabase.SaveAssets();
    }
}
```

### AvatarMask Creation (C# template output)
```csharp
// Source: Unity AvatarMask API docs
using UnityEngine;
using UnityEditor;

public static class VeilBreakers_AvatarMaskSetup
{
    [MenuItem("VeilBreakers/Camera/Create Avatar Mask")]
    public static void Execute()
    {
        AvatarMask mask = new AvatarMask();
        mask.name = "VB_UpperBodyMask";

        // Enable/disable humanoid body parts
        mask.SetHumanoidBodyPartActive(AvatarMaskBodyPart.Body, true);
        mask.SetHumanoidBodyPartActive(AvatarMaskBodyPart.Head, true);
        mask.SetHumanoidBodyPartActive(AvatarMaskBodyPart.LeftArm, true);
        mask.SetHumanoidBodyPartActive(AvatarMaskBodyPart.RightArm, true);
        mask.SetHumanoidBodyPartActive(AvatarMaskBodyPart.LeftLeg, false);
        mask.SetHumanoidBodyPartActive(AvatarMaskBodyPart.RightLeg, false);

        AssetDatabase.CreateAsset(mask, "Assets/Animations/VB_UpperBodyMask.mask");
        AssetDatabase.SaveAssets();
    }
}
```

### Scene Transition System (runtime C# template output)
```csharp
// Source: Unity SceneManager API docs + bootstrap pattern
using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;

namespace VeilBreakers.WorldSystems
{
    public class VB_SceneTransitionManager : MonoBehaviour
    {
        public static VB_SceneTransitionManager Instance { get; private set; }

        [SerializeField] private float _fadeDuration = 0.5f;

        void Awake()
        {
            if (Instance != null) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        public void LoadScene(string sceneName, LoadSceneMode mode = LoadSceneMode.Single)
        {
            StartCoroutine(LoadSceneRoutine(sceneName, mode));
        }

        private IEnumerator LoadSceneRoutine(string sceneName, LoadSceneMode mode)
        {
            // Fade out
            yield return StartCoroutine(FadeOut());

            // Async load
            AsyncOperation op = SceneManager.LoadSceneAsync(sceneName, mode);
            op.allowSceneActivation = false;

            while (op.progress < 0.9f)
            {
                // Update loading progress (op.progress / 0.9f for 0-1 range)
                yield return null;
            }

            op.allowSceneActivation = true;
            yield return op;

            // Fade in
            yield return StartCoroutine(FadeIn());
        }

        private IEnumerator FadeOut() { yield return new WaitForSeconds(_fadeDuration); }
        private IEnumerator FadeIn() { yield return new WaitForSeconds(_fadeDuration); }
    }
}
```

### Weather System (runtime C# template output)
```csharp
// Source: Standard Unity particle system + coroutine patterns
using UnityEngine;
using System.Collections;

namespace VeilBreakers.WorldSystems
{
    public enum WeatherState { Clear, Rain, Snow, Fog, Storm }

    public class VB_WeatherManager : MonoBehaviour
    {
        [SerializeField] private ParticleSystem _rainParticles;
        [SerializeField] private ParticleSystem _snowParticles;
        [SerializeField] private float _transitionDuration = 3f;

        private WeatherState _currentWeather = WeatherState.Clear;

        public void TransitionTo(WeatherState target)
        {
            if (target == _currentWeather) return;
            StartCoroutine(WeatherTransitionRoutine(target));
        }

        private IEnumerator WeatherTransitionRoutine(WeatherState target)
        {
            // Fade out current weather particles
            // Fade in target weather particles
            // Adjust fog density, ambient lighting
            _currentWeather = target;
            yield return new WaitForSeconds(_transitionDuration);
        }
    }
}
```

### Blender World Graph (pure-logic, testable)
```python
# Source: Existing _dungeon_gen.py pattern for pure-logic generation
from dataclasses import dataclass, field

@dataclass
class WorldNode:
    name: str
    position: tuple[float, float]  # (x, y) world coords
    node_type: str  # "city", "camp", "dungeon", "ruins", etc.

@dataclass
class WorldEdge:
    from_node: str
    to_node: str
    distance: float  # meters
    path_type: str  # "road", "trail", "hidden"

@dataclass
class WorldGraph:
    nodes: list[WorldNode] = field(default_factory=list)
    edges: list[WorldEdge] = field(default_factory=list)

def generate_world_graph(
    locations: list[dict],
    target_distance: float = 105.0,  # 30-second walk at 3.5 m/s
    seed: int = 0,
) -> WorldGraph:
    """Generate connected world graph with POI spacing constraint."""
    # Place nodes, connect with edges, validate ~105m distances
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Cinemachine 2.x CinemachineFreeLook | Cinemachine 3.x CinemachineCamera + OrbitalFollow | Cinemachine 3.0 (2024) | Different namespace (Unity.Cinemachine), different component names, different API |
| AnimationClip.SetCurve (runtime) | AnimationUtility.SetEditorCurve (editor) | Always was editor-only for non-legacy | SetCurve only works for legacy clips in editor; must use AnimationUtility for modern clips |
| Coroutine scene loading | Awaitable scene loading (Unity 6) | Unity 6 (2024) | Can use `await SceneManager.LoadSceneAsync()` with `#if UNITY_6000_0_OR_NEWER` guard |
| Old Timeline API | Timeline 1.7+ CreateTrack<T>() | Timeline 1.0+ | Generic track creation method on TimelineAsset |

**Deprecated/outdated:**
- `CinemachineFreeLook`: Cinemachine 2.x class. Replaced by CinemachineCamera + CinemachineOrbitalFollow in 3.x.
- `CinemachineVirtualCamera`: Cinemachine 2.x class. Replaced by CinemachineCamera in 3.x.
- `using Cinemachine;`: Old namespace. Now `using Unity.Cinemachine;`.
- `AnimationClip.SetCurve` for editor: Only works runtime for legacy clips. Use `AnimationUtility.SetEditorCurve`.

## Open Questions

1. **CinemachineTrack exact API for clip creation**
   - What we know: TimelineAsset.CreateTrack<CinemachineTrack>() creates the track. Clips reference CinemachineCamera via binding.
   - What's unclear: Exact API for creating CinemachineShot clips and assigning cameras to them within the track.
   - Recommendation: Generate the track setup; camera shot assignment can be done via SetGenericBinding or by creating CinemachineShot playable clips. Test in implementation.

2. **Terrain detail painting density map format**
   - What we know: TerrainData.SetDetailLayer takes int[,] density arrays per detail prototype.
   - What's unclear: Optimal resolution and density values for grass that looks good.
   - Recommendation: Use reasonable defaults (resolution matching terrain, density 0-16 range). This is Claude's discretion area.

3. **Multi-floor dungeon staircase geometry**
   - What we know: Current _dungeon_gen.py generates single-floor grids. Floors need vertical connections.
   - What's unclear: Best approach for staircase mesh geometry (spiral vs straight vs L-shaped).
   - Recommendation: Use straight staircase segments (simplest mesh, fits corridor width). Implement as special geometry op type in dungeon grid.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | Tools/mcp-toolkit/pyproject.toml (existing) |
| Quick run command | `python -m pytest tests/test_camera_templates.py tests/test_world_templates.py tests/test_worldbuilding_v2.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAM-01 | Cinemachine virtual camera C# generation | unit | `pytest tests/test_camera_templates.py::TestCinemachineSetup -x` | Wave 0 |
| CAM-02 | Timeline asset C# generation | unit | `pytest tests/test_camera_templates.py::TestTimelineSetup -x` | Wave 0 |
| CAM-03 | Cutscene/PlayableDirector C# generation | unit | `pytest tests/test_camera_templates.py::TestCutsceneSetup -x` | Wave 0 |
| CAM-04 | Camera shake/zoom/transition C# generation | unit | `pytest tests/test_camera_templates.py::TestCameraEffects -x` | Wave 0 |
| SCNE-01 | Scene creation/loading C# generation | unit | `pytest tests/test_world_templates.py::TestSceneLoading -x` | Wave 0 |
| SCNE-02 | Scene transition system C# generation | unit | `pytest tests/test_world_templates.py::TestSceneTransition -x` | Wave 0 |
| SCNE-03 | Probe setup C# generation | unit | `pytest tests/test_world_templates.py::TestProbeSetup -x` | Wave 0 |
| SCNE-04 | Occlusion culling C# generation | unit | `pytest tests/test_world_templates.py::TestOcclusionSetup -x` | Wave 0 |
| SCNE-05 | Environment/GI C# generation | unit | `pytest tests/test_world_templates.py::TestEnvironmentSetup -x` | Wave 0 |
| SCNE-06 | Terrain detail C# generation | unit | `pytest tests/test_world_templates.py::TestTerrainDetail -x` | Wave 0 |
| TWO-01 | Tilemap C# generation | unit | `pytest tests/test_world_templates.py::TestTilemapSetup -x` | Wave 0 |
| TWO-02 | 2D physics C# generation | unit | `pytest tests/test_world_templates.py::TestPhysics2DSetup -x` | Wave 0 |
| MEDIA-01 | VideoPlayer C# generation | unit | `pytest tests/test_camera_templates.py::TestVideoPlayerSetup -x` | Wave 0 |
| ANIMA-01 | AnimationClip editing C# generation | unit | `pytest tests/test_camera_templates.py::TestAnimClipEditor -x` | Wave 0 |
| ANIMA-02 | Animator modification C# generation | unit | `pytest tests/test_camera_templates.py::TestAnimatorEditor -x` | Wave 0 |
| ANIMA-03 | Avatar mask C# generation | unit | `pytest tests/test_camera_templates.py::TestAvatarMaskSetup -x` | Wave 0 |
| AAA-05 | Storytelling props placement logic | unit | `pytest tests/test_worldbuilding_v2.py::TestStorytellingProps -x` | Wave 0 |
| WORLD-01 | Location generation logic | unit | `pytest tests/test_worldbuilding_v2.py::TestLocationGeneration -x` | Wave 0 |
| WORLD-02 | 16 room types in interior layout | unit | `pytest tests/test_worldbuilding_v2.py::TestRoomTypes -x` | Wave 0 |
| WORLD-03 | Boss arena generation logic | unit | `pytest tests/test_worldbuilding_v2.py::TestBossArena -x` | Wave 0 |
| WORLD-04 | World graph generation + distance validation | unit | `pytest tests/test_worldbuilding_v2.py::TestWorldGraph -x` | Wave 0 |
| WORLD-05 | Interior-exterior linking logic | unit | `pytest tests/test_worldbuilding_v2.py::TestLinkedInterior -x` | Wave 0 |
| WORLD-06 | Multi-floor dungeon generation | unit | `pytest tests/test_worldbuilding_v2.py::TestMultiFloorDungeon -x` | Wave 0 |
| WORLD-07 | Furniture real-world scale validation | unit | `pytest tests/test_worldbuilding_v2.py::TestFurnitureScale -x` | Wave 0 |
| WORLD-08 | 8 time-of-day presets in lighting | unit | `pytest tests/test_world_templates.py::TestTimeOfDayPresets -x` | Wave 0 |
| WORLD-09 | Overrun variant generation logic | unit | `pytest tests/test_worldbuilding_v2.py::TestOverrunVariant -x` | Wave 0 |
| WORLD-10 | Easter egg/hidden area generation | unit | `pytest tests/test_worldbuilding_v2.py::TestEasterEggs -x` | Wave 0 |
| RPG-02 | Fast travel C# generation | unit | `pytest tests/test_world_templates.py::TestFastTravel -x` | Wave 0 |
| RPG-04 | Puzzle mechanics C# generation | unit | `pytest tests/test_world_templates.py::TestPuzzleMechanics -x` | Wave 0 |
| RPG-06 | Trap mechanics C# generation | unit | `pytest tests/test_world_templates.py::TestTrapMechanics -x` | Wave 0 |
| RPG-07 | Spatial loot C# generation | unit | `pytest tests/test_world_templates.py::TestSpatialLoot -x` | Wave 0 |
| RPG-09 | Weather system C# generation | unit | `pytest tests/test_world_templates.py::TestWeatherSystem -x` | Wave 0 |
| RPG-10 | Day/night cycle C# generation | unit | `pytest tests/test_world_templates.py::TestDayNightCycle -x` | Wave 0 |
| RPG-11 | NPC placement C# generation | unit | `pytest tests/test_world_templates.py::TestNPCPlacement -x` | Wave 0 |
| RPG-12 | Dungeon lighting C# generation | unit | `pytest tests/test_world_templates.py::TestDungeonLighting -x` | Wave 0 |
| RPG-13 | Terrain-building blend C# generation | unit | `pytest tests/test_world_templates.py::TestTerrainBlend -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_camera_templates.py tests/test_world_templates.py tests/test_worldbuilding_v2.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_camera_templates.py` -- covers CAM-01/02/03/04, ANIMA-01/02/03, MEDIA-01
- [ ] `tests/test_world_templates.py` -- covers SCNE-01/02/03/04/05/06, TWO-01/02, WORLD-08, RPG-02/04/06/07/09/10/11/12/13
- [ ] `tests/test_worldbuilding_v2.py` -- covers WORLD-01/02/03/04/05/06/07/09/10, AAA-05

## Sources

### Primary (HIGH confidence)
- [Unity Cinemachine 3.1 API - CinemachineCamera](https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/api/Unity.Cinemachine.CinemachineCamera.html) - Class properties, methods, namespace
- [Unity Cinemachine 3.1 API - CinemachineOrbitalFollow](https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/api/Unity.Cinemachine.CinemachineOrbitalFollow.html) - Radius, TargetOffset, OrbitStyle
- [Unity Cinemachine 3.1 API - Namespace](https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/api/Unity.Cinemachine.html) - All classes: StateDrivenCamera, ImpulseSource, BlendDefinition
- [Unity Timeline 1.7 API - TimelineAsset](https://docs.unity3d.com/Packages/com.unity.timeline@1.7/api/UnityEngine.Timeline.TimelineAsset.html) - CreateTrack<T>, GetOutputTracks, duration
- [Unity AnimationUtility.SetEditorCurve](https://docs.unity3d.com/ScriptReference/AnimationUtility.SetEditorCurve.html) - Editor curve manipulation
- [Unity EditorCurveBinding](https://docs.unity3d.com/ScriptReference/EditorCurveBinding.html) - Binding creation for curve assignment
- [Unity SceneManager 6000.3](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/SceneManagement.SceneManager.html) - LoadSceneAsync, additive mode
- [Unity ReflectionProbe API](https://docs.unity3d.com/ScriptReference/ReflectionProbe.html) - Probe creation and configuration
- [Unity AvatarMask API](https://docs.unity3d.com/ScriptReference/AvatarMask.html) - Body part masking
- [Unity VideoPlayer API](https://docs.unity3d.com/ScriptReference/Video.VideoPlayer.html) - Video playback configuration
- [Unity Tilemap API](https://docs.unity3d.com/ScriptReference/Tilemaps.Tilemap.html) - SetTile, tile placement
- Existing codebase: `game_templates.py` VB_CameraSetup (Cinemachine 3.x reference implementation)
- Existing codebase: `scene_templates.py` _TIME_OF_DAY_PRESETS (5 presets, extend to 8)
- Existing codebase: `_building_grammar.py` _ROOM_CONFIGS (8 room types, extend to 16)
- Existing codebase: `_building_grammar.py` apply_ruins_damage (overrun variant base)

### Secondary (MEDIUM confidence)
- [Unity AnimatorController API](https://docs.unity3d.com/ScriptReference/Animations.AnimatorController.html) - CreateAnimatorControllerAtPath, AddParameter
- [Unity AnimatorStateMachine API](https://docs.unity3d.com/ScriptReference/Animations.AnimatorStateMachine.html) - AddState, AddTransition, AddStateMachine
- [Unity RenderTexture for Video](https://docs.unity3d.com/6000.3/Documentation/Manual/VideoPlayer-rendertexture.html) - VideoPlayer render mode setup

### Tertiary (LOW confidence)
- CinemachineTrack clip creation specifics (exact API for CinemachineShot within tracks) -- needs validation during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Cinemachine 3.x, Timeline, and all Unity built-in APIs verified via official docs
- Architecture: HIGH - Follows established compound tool pattern from prior phases with proven template generation approach
- Pitfalls: HIGH - API differences between Cinemachine 2.x/3.x and AnimationClip.SetCurve vs AnimationUtility verified in official docs
- World design: HIGH - Extends existing codebase (_building_grammar.py, _dungeon_gen.py) with well-understood patterns
- RPG systems: MEDIUM - Standard Unity patterns (particle systems, coroutines, MonoBehaviour) but specific implementations need testing

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable APIs, no major changes expected)
