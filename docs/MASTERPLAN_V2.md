# AI GAME DEVELOPMENT TOOLKIT — MASTER PLAN V2

## Mission
Transform Claude into a **multi-million dollar equivalent game development team** covering EVERY discipline: 3D art, technical art, animation, environment art, VFX, audio, UI/UX, gameplay programming, QA, and build engineering — all with built-in validation loops so nothing ships broken.

**V2 Expansion**: After comprehensive pipeline audit, the toolkit grew from ~50 tools across 3 stages to **~200 capabilities across 10 stages**, covering the entire AAA game development lifecycle.

---

## Architecture: Token-Efficient Compound Tools

### The Problem with V1
V1 had 50+ individual tools. Each MCP tool definition costs ~200-400 tokens of context. Loading 50 tools = **10,000-20,000 tokens** before a single message. This is unsustainable.

### V2 Solution: Compound Action Pattern
Instead of `create_walk_cycle`, `create_fly_cycle`, `create_idle_animation` as separate tools, we have ONE tool:

```python
@mcp.tool()
def blender_animate(action: str, params: dict) -> dict:
    """Blender animation pipeline.

    Actions: walk_cycle, fly_cycle, idle, attack, death, hit_reaction,
    spawn, special_ability, secondary_motion, blend_test, preview,
    root_motion, add_events, batch_export
    """
    return dispatch(action, params)
```

**Result**: 26 compound tools instead of 200+ individual tools.
**Token savings**: ~5,200 tokens total context vs ~40,000+. **~8x reduction.**

### Final Architecture

```
┌──────────────────────────────────────────────────────┐
│                   CLAUDE (Opus 4.6)                   │
│              Game Development AI Director              │
│                                                        │
│  Gemini CLI ←── Visual Review ──→ Screenshots          │
│  Sequential Thinking ←── Complex Analysis              │
└────────┬──────────────┬──────────────┬────────────────┘
         │              │              │
    ┌────▼─────┐  ┌─────▼─────┐  ┌────▼──────┐
    │ BLENDER  │  │  ASSET    │  │  UNITY    │
    │ GAMEDEV  │  │ PIPELINE  │  │ ENHANCED  │
    │ 12 tools │  │ 6 tools   │  │ 8 tools   │
    └────┬─────┘  └─────┬─────┘  └────┬──────┘
         │              │              │
    [Blender bpy]  [34 External   [Unity Editor
     + Addons]      APIs/Tools]    C# Scripts]
```

---

## MCP 1: `blender-gamedev-mcp` — 12 Compound Tools

### Tool 1: `blender_rig`
**All rigging operations**

| Action | Description |
|--------|-------------|
| `analyze` | Scan mesh for rig requirements (joint locations, symmetry, proportions, template recommendation) |
| `create_rigify` | Rigify meta-rig from template: humanoid, quadruped, bird, insect, serpent, floating, dragon, multi_armed, arachnid, amorphous |
| `create_creature` | Custom creature rig: configurable limb_count, wings, tail_segments, extra_appendages, jaw |
| `create_facial` | Face rig: jaw, lips, eyelids, eyebrows, cheeks, nose. Monster variants: snarl, hiss, roar |
| `setup_ik` | IK chain setup: 2-bone, spline (tails/tentacles), multi-target, with rotation limits |
| `setup_spring_bones` | Spring/jiggle physics: hair, capes, tails, chains, ears, tentacle tips |
| `auto_weight` | Heat/envelope/nearest weight painting with immediate deformation test |
| `test_deformation` | Pose at 8 standard poses, render contact sheet, report stretch/clip per bone group |
| `validate` | Full check: unweighted verts, bleeding, bone rolls, symmetry, hierarchy, constraints |
| `fix_weights` | Auto-fix: normalize, clean zeros, smooth problem areas, fix bleeding |
| `mirror_weights` | Copy weights L→R or R→L (save 50% painting work) |
| `retarget` | Transfer animation from one rig to another (different proportions) |
| `create_control_shapes` | Custom bone shapes for animator-friendly controls |
| `setup_ragdoll` | Automated ragdoll: map bones → colliders → joints → muscle limits |

### Tool 2: `blender_animate`
**All animation operations**

| Action | Description |
|--------|-------------|
| `walk_cycle` | Procedural gait: biped, quadruped, hexapod, arachnid, serpent. Configurable: speed, bounce, stride |
| `fly_cycle` | Wing flap: frequency, amplitude, glide_ratio, hover_mode. Handles body tilt + tail counterbalance |
| `idle` | Breathing + weight shift + secondary motion on tails/ears/wings/tentacles |
| `attack` | Anticipation → strike → follow-through. Types: melee_swing, thrust, slam, bite, claw, tail_whip, wing_buffet, breath_attack |
| `death` | Death animation: ragdoll-blend, dramatic collapse, dissolve preparation |
| `hit_reaction` | Directional flinch/stagger: front, back, left, right. Scales with damage intensity |
| `spawn` | Emergence: from_ground, materialize, portal_entry, drop_from_sky |
| `special_ability` | Custom from description: "rises up, spreads wings, breathes fire downward" |
| `secondary_motion` | Physics-based jiggle on: tails, ears, capes, hair, chains, hanging elements |
| `blend_test` | Test how two animations blend together (walk→run, idle→combat) |
| `root_motion` | Configure root motion extraction for Unity |
| `add_events` | Frame events: foot_step, attack_hit, vfx_trigger, sound_cue |
| `batch_export` | Export all actions as separate Unity animation clips |
| `apply_mixamo` | Download + retarget Mixamo animation to custom rig |
| `apply_ai_motion` | Generate motion from text via HY-Motion or MotionGPT |

### Tool 3: `blender_mesh_edit`
**Surgical model editing (USER'S EXPLICIT REQUEST)**

| Action | Description |
|--------|-------------|
| `select_by_material` | Isolate geometry by material slot (select just the belt, hat, armor piece) |
| `select_by_vertex_group` | Target named regions |
| `select_by_loose_parts` | Find disconnected mesh islands |
| `select_by_face_normal` | Select faces pointing in a direction (top, bottom, sides) |
| `sculpt_smooth` | Smooth problem areas without affecting rest |
| `sculpt_inflate` | Add volume to thin areas |
| `sculpt_flatten` | Flatten uneven surfaces |
| `sculpt_crease` | Sharpen edges for hard-surface detail |
| `boolean_add` | Merge new geometry (add horn, spike, decoration) |
| `boolean_subtract` | Cut away geometry (hollow, create holes) |
| `boolean_intersect` | Keep only overlapping geometry |
| `extrude_faces` | Extend geometry from selected faces |
| `inset_faces` | Create inner face borders (for panel lines, armor plates) |
| `mirror_mesh` | Enforce perfect symmetry |
| `snap_to_symmetry` | Fix asymmetric meshes |
| `separate_by_material` | Split model into parts for independent editing |
| `join_meshes` | Recombine parts after editing |
| `proportional_edit` | Soft selection for organic adjustments |
| `add_detail_geometry` | Subdivide + sculpt specific areas (rivets, wrinkles, scales) |
| `smooth_vertex_group` | Smooth only a specific named region |

### Tool 4: `blender_topology`
**Mesh analysis, repair, retopology**

| Action | Description |
|--------|-------------|
| `analyze` | Full report: non-manifold, n-gons, poles, edge flow, loose geo, inverted normals, zero-area faces. Graded A-F |
| `fix_auto` | Auto-fix: remove doubles, fix normals, fill holes, remove loose, dissolve degenerate |
| `retopologize` | Quad remesh with target face count, preserving hard edges and UV seams |
| `fix_normals` | Recalculate all normals consistently |
| `dissolve_ngons` | Convert n-gons to quads/tris properly |
| `fix_poles` | Reduce pole count in deformation areas by edge flow optimization |
| `check_game_ready` | Full checklist: poly budget, UV, materials, bones, naming conventions |

### Tool 5: `blender_uv`
**UV unwrapping and optimization**

| Action | Description |
|--------|-------------|
| `analyze` | UV quality: stretch, overlap, island count, texel density, seam placement, bounds check |
| `smart_unwrap` | Angle-based smart UV projection |
| `xatlas_unwrap` | High-quality xatlas-based unwrapping |
| `pack_islands` | Optimize UV island packing for maximum texture usage |
| `create_lightmap_uv` | Generate UV2 channel for Unity lightmapping |
| `fix_seams` | Optimize seam placement to hidden areas |
| `equalize_texel_density` | Normalize texel density across all UV islands |
| `render_uv_layout` | Render UV layout as image for inspection |

### Tool 6: `blender_texture`
**Texture creation, editing, baking (USER'S EXPLICIT REQUEST)**

| Action | Description |
|--------|-------------|
| `create_pbr` | PBR material from description (albedo, normal, roughness, metallic, AO) |
| `edit_region` | Mask a UV/material region and apply changes (recolor, adjust, replace) |
| `inpaint_ai` | AI-regenerate just a masked region (fix a belt, change armor trim) via SD inpainting |
| `clone_stamp` | Clone texture details between regions |
| `projection_paint` | Project an image onto a specific UV area |
| `adjust_hsv` | Hue/saturation/value adjustment on masked region only |
| `fix_seams` | Blend texture seams between UV islands |
| `generate_wear_map` | Procedural wear/damage: convex = worn, concave = dirty, edges = chipped |
| `generate_detail_map` | Add scratches, dirt, grime, rust, moss procedurally |
| `bake_maps` | Bake high→low: normal, AO, curvature, thickness, diffuse |
| `create_tileable` | Generate seamless tileable texture from description |
| `upscale` | AI upscale via Real-ESRGAN (2x/4x) |
| `validate` | Check resolution, format, UV coverage, tiling, compression suitability |

### Tool 7: `blender_material`
**Material creation and management**

| Action | Description |
|--------|-------------|
| `create` | Full PBR material with node tree from description |
| `create_variant` | Color/texture variant of existing material (same monster, different elemental type) |
| `batch_swap` | Swap materials across multiple objects |
| `preview` | Render material on sphere + flat surface |
| `create_transparent` | Glass, crystal, force field, ghost materials |
| `create_emissive` | Glowing materials: lava, magic, bioluminescence, corruption |

### Tool 8: `blender_shape_key`
**Blend shapes for animation and states**

| Action | Description |
|--------|-------------|
| `create` | New shape key (facial expression, damage state, form change) |
| `edit` | Modify specific shape key vertices |
| `transfer` | Copy shape keys between similar meshes |
| `preview` | Render shape key at various blend values |
| `create_expression_set` | Generate full expression library (happy, angry, sad, surprised, pain, roar) |

### Tool 9: `blender_scene`
**World/environment building**

| Action | Description |
|--------|-------------|
| `terrain_heightmap` | Generate terrain: mountains, hills, plains, volcanic, canyon, cliffs |
| `terrain_erosion` | Apply realistic erosion simulation |
| `terrain_paint` | Auto-paint textures based on slope/altitude/moisture rules |
| `create_cave` | Procedural cave system: connected rooms, corridors, natural formations |
| `create_river` | Carve river/stream into terrain with erosion + flow direction |
| `create_road` | Generate road/path between points with proper grading |
| `create_water` | Lake, ocean, pond with shoreline and depth |
| `scatter_vegetation` | Biome-aware scatter: trees, grass, rocks, bushes. Slope/altitude rules |
| `generate_building` | Procedural building: style, floors, width, roof, materials |
| `generate_ruins` | Take building → damage it (broken walls, collapsed roof, overgrown) |
| `generate_dungeon` | Procedural dungeon: rooms, corridors, doors, spawn points |
| `generate_town` | Town layout: streets, building plots, districts, landmarks |
| `create_modular_kit` | Modular pieces: walls, floors, corners, doors, windows that snap together |
| `scatter_props` | Context-aware prop placement (barrels near tavern, crates near dock) |
| `generate_prop_variants` | N variations of a prop type (different barrels, rocks, lamps) |
| `create_breakable` | Generate broken/destroyed variant of a prop |

### Tool 10: `blender_export`
**Export pipeline with validation**

| Action | Description |
|--------|-------------|
| `unity_fbx` | FBX export: Unity scale, Y-up, -Z forward, triangulated, bone naming |
| `lod_chain` | Export mesh + auto-generated LODs (100%, 50%, 25%, 10%) |
| `validate` | Re-import check: scale, orientation, bones, materials, animations |
| `batch` | Export all modified objects to Unity folder |
| `with_animations` | Export mesh + all animation clips as separate takes |

### Tool 11: `blender_preview`
**Visual feedback system (THE breakthrough)**

| Action | Description |
|--------|-------------|
| `screenshot` | Single viewport screenshot from specified angle |
| `contact_sheet` | Animation frames in grid (every Nth frame, multiple angles) |
| `turntable` | 360-degree rotation renders (8-16 angles) |
| `comparison` | Before/after side-by-side |
| `silhouette` | Render as solid black at multiple sizes (gameplay readability test) |
| `wireframe` | Wireframe overlay showing topology |
| `weight_heatmap` | Weight paint visualization per bone group |
| `uv_layout` | UV map render with stretch heatmap |
| `material_preview` | Material on sphere + flat + model |

### Tool 12: `blender_concept`
**Pre-production / concept generation**

| Action | Description |
|--------|-------------|
| `generate_art` | Text → concept art image via SD/FLUX (character, environment, prop, creature) |
| `color_palette` | Generate cohesive color palette from description or reference |
| `style_guide` | Visual reference document for an entity/area |
| `mood_board` | Collect and arrange reference images |
| `silhouette_test` | Test character readability at game camera distances |

---

## MCP 2: `asset-pipeline-mcp` — 6 Compound Tools

### Tool 1: `asset_generate_3d`
**AI 3D model generation**

| Action | Backend | Description |
|--------|---------|-------------|
| `tripo` | Tripo3D Python SDK | Text/image → 3D, clean quad topology, PBR textures, auto-rig available |
| `meshy` | Meshy REST API | Fast iteration, prototyping, 500+ game-ready animations |
| `rodin` | Hyper3D Rodin API | Highest quality (10B params), photorealistic |
| `sf3d` | Stability SF3D (open source) | Fastest (0.5s), includes UV unwrapping |
| `hunyuan` | Hunyuan3D 3.5 API | PBR textures up to 8K resolution |
| `check_status` | All | Poll async generation tasks |
| `download` | All | Download + auto-process generated model |

### Tool 2: `asset_generate_texture`
**AI texture generation and processing**

| Action | Backend | Description |
|--------|---------|-------------|
| `chord_pbr` | Ubisoft CHORD (open source) | Text/image → full PBR map set |
| `scenario` | Scenario REST API | Custom-trained on YOUR art style |
| `material_maker` | Material Maker CLI | Procedural tileable textures |
| `normal_map` | CHORD / local | Image → normal map |
| `upscale` | Real-ESRGAN | AI 2x/4x upscaling |
| `tileable` | Multiple | Seamless tileable generation |

### Tool 3: `asset_generate_terrain`
**Terrain heightmap generation**

| Action | Backend | Description |
|--------|---------|-------------|
| `gaea` | Gaea CLI (Build Swarm) | Professional terrain: JSON config, seed control |
| `procedural` | NumPy + erosion sim | No external tool needed, pure Python |
| `world_machine` | World Machine CLI | Alternative professional terrain |
| `to_unity` | Local | Convert heightmap → Unity Terrain Data + splatmaps |

### Tool 4: `asset_process_mesh`
**Mesh processing and optimization**

| Action | Backend | Description |
|--------|---------|-------------|
| `analyze` | PyMeshLab | Full topology analysis + grade |
| `repair` | PyMeshLab | Auto-fix all detected issues |
| `simplify` | PyMeshLab / fast-simplification | Quadric edge collapse with quality preservation |
| `lod_chain` | PyMeshLab | Multi-level LOD generation |
| `uv_unwrap` | xatlas-python | Automatic UV unwrapping |
| `optimize` | PyMeshLab + xatlas | Full pipeline: clean → optimize → UV → validate |
| `compare` | PyMeshLab | Hausdorff distance between original and processed |

### Tool 5: `asset_generate_audio`
**AI audio generation (NEW — ENTIRE MODULE)**

| Action | Backend | Description |
|--------|---------|-------------|
| `sfx` | ElevenLabs / AudioCraft | Generate sound effect from description |
| `music_loop` | MusicGen / Suno API | Generate music loop: combat, exploration, boss, town |
| `voice_line` | ElevenLabs / XTTS | AI voice synthesis for NPCs/monsters |
| `ambient` | AudioCraft | Layered ambient soundscape for biome |
| `stinger` | MusicGen | Short musical cue: level_up, item_found, quest_complete |
| `bark` | ElevenLabs / Bark | Short NPC vocalizations: grunts, battle cries, pain |
| `variant` | Local | Pitch/timing variations for variety |

### Tool 6: `asset_validate`
**Comprehensive quality validation**

| Action | Description |
|--------|-------------|
| `full_check` | All checks: poly budget, UV, textures, materials, naming |
| `compare_meshes` | Hausdorff distance (did simplification lose too much?) |
| `unity_ready` | Verify Unity import requirements |
| `budget_check` | Check asset against memory/performance budgets |
| `texture_audit` | Resolution, format, compression suitability |
| `batch_audit` | Audit entire asset folder for issues |

---

## MCP 3: `unity-enhanced-mcp` — 8 Compound Tools

### Tool 1: `unity_visual_test`
**Visual testing and UI validation**

| Action | Description |
|--------|-------------|
| `capture` | High-res Game view screenshot at specified resolution |
| `capture_element` | Screenshot of specific UI element |
| `compare` | Pixel diff between two screenshots, highlight changes |
| `validate_ui` | Traverse VisualElement tree: overlaps, zero-size, overflow, style issues |
| `responsive` | Screenshots at 5 resolutions: 720p, 1080p, 1440p, 4K, mobile |
| `gemini_review` | Send screenshot to Gemini for visual quality assessment |
| `contrast_check` | WCAG contrast ratio validation for all text |
| `color_blind_check` | Simulate color blindness modes |
| `hierarchy_dump` | Full UI tree with computed sizes and styles |

### Tool 2: `unity_animation`
**Animation system setup**

| Action | Description |
|--------|-------------|
| `create_controller` | Programmatic Animator Controller: states, transitions, parameters |
| `configure_avatar` | Humanoid/Generic avatar bone mapping |
| `setup_rigging` | Animation Rigging constraints: Two-Bone IK, Multi-Aim, Rig component |
| `create_blend_tree` | Locomotion blend trees: walk/run/idle/strafe blending |
| `import_clips` | Import FBX animations with: loop, root motion, events settings |
| `preview` | Play animation, capture contact sheet |
| `setup_ik_targets` | Place IK targets for foot/hand placement |

### Tool 3: `unity_scene_build`
**Level design and scene construction**

| Action | Description |
|--------|-------------|
| `create_terrain` | Unity Terrain from heightmap + splatmaps |
| `scatter` | Distribute objects: trees, rocks, props with density rules |
| `setup_lighting` | Directional, ambient, fog, post-processing, time-of-day |
| `probuilder` | Create geometry: rooms, corridors, platforms, stairs |
| `place_prefabs` | Position prefabs from layout description |
| `setup_navmesh` | Bake NavMesh + Links for jumps/drops |
| `camera_setup` | Follow, orbit, cinematic, combat cameras |
| `water` | Water plane with shader and collider |
| `reflection_probes` | Automated placement based on material reflectivity |
| `light_probes` | Automated probe grid placement |
| `create_trigger_zone` | Trigger volumes for gameplay events |

### Tool 4: `unity_vfx`
**VFX and shaders (NEW — ENTIRE MODULE)**

| Action | Description |
|--------|-------------|
| `particle_system` | VFX Graph setup from description ("fire + sparks + smoke") |
| `hit_effect` | Per-brand damage VFX: IRON sparks, VENOM drip, SURGE crackle, etc. |
| `environmental` | Dust motes, fireflies, snow, rain, ash, pollen |
| `trail` | Weapon/projectile trails with fade |
| `aura` | Character buff VFX: corruption glow, healing shimmer |
| `destruction` | Explosion, crumble, shatter |
| `shader_graph` | Shader Graph setup: dissolve, force field, hologram, toon, water, foliage |
| `outline_shader` | Character/object outline for selection/interaction |
| `corruption_shader` | VeilBreakers corruption visual scaling with corruption % |
| `damage_shader` | Cracks, burns, frost overlay on characters |
| `post_processing` | URP Volume: bloom, color grading, vignette, AO, DOF, motion blur |
| `screen_shake` | Camera shake: intensity, frequency, duration |
| `screen_effects` | Damage vignette, low health pulse, poison overlay, heal glow |

### Tool 5: `unity_ai_mob`
**AI and creature behavior**

| Action | Description |
|--------|-------------|
| `create_controller` | Generate mob MonoBehaviour: patrol, chase, attack, flee states |
| `setup_aggro` | Aggro system: detection range, decay, threat table, leash |
| `create_patrol` | Patrol waypoints, dwell times, random deviation |
| `setup_spawner` | Spawn system: max count, respawn timer, conditions, bounds |
| `behavior_tree` | Generate behavior tree ScriptableObject with nodes |
| `test_behavior` | Run simulation, capture mob paths/decisions over N seconds |
| `create_ability` | Combat ability prefab: animation + VFX + hitbox + damage + sound |
| `projectile` | Projectile system: trajectory, trail VFX, impact effect |
| `hitbox_system` | Configurable hitboxes synced to animation frames |
| `loot_table` | Generate drop tables with rarity tiers and weighting |

### Tool 6: `unity_audio`
**Audio system (NEW — ENTIRE MODULE)**

| Action | Description |
|--------|-------------|
| `create_mixer` | Audio mixer with groups: SFX, Music, Voice, Ambient, UI |
| `create_manager` | C# audio manager with pooling, priority, ducking |
| `assign_sfx` | Link sound effects to animation events |
| `footstep_system` | Surface-material-aware footstep sounds |
| `music_zones` | Trigger music changes when entering areas |
| `audio_zones` | Reverb zones: cave echo, outdoor, indoor |
| `place_sources` | Ambient emitters: fireplace, waterfall, forge |
| `adaptive_music` | Layers that add/remove based on game state |

### Tool 7: `unity_performance`
**Performance profiling and optimization**

| Action | Description |
|--------|-------------|
| `profile` | Frame time, draw calls, batches, tris, memory, SetPass calls |
| `setup_lods` | Auto-generate LODGroups for scene meshes |
| `bake_lightmaps` | Trigger lightmap bake with progress monitoring |
| `bake_occlusion` | Occlusion culling data generation |
| `memory_report` | Texture, mesh, audio memory breakdown |
| `shader_audit` | Shader variant count, instruction complexity |
| `optimize_hierarchy` | Flatten unnecessary parents, remove empty GameObjects |
| `setup_instancing` | Configure GPU instancing for repeated objects |
| `atlas_textures` | Combine textures into atlases to reduce draw calls |
| `benchmark` | Automated camera path through scene, capture frame times |

### Tool 8: `unity_build`
**Build pipeline and QA**

| Action | Description |
|--------|-------------|
| `build_player` | Automated build with platform settings |
| `size_report` | Build output analysis by category |
| `compress_textures` | Batch compression: ASTC, BC7, ETC2 per platform |
| `compress_audio` | Format optimization: Vorbis quality, mono/stereo |
| `pre_build_check` | Missing references, null components, disabled scripts |
| `asset_audit` | Unused assets, oversized textures, uncompressed audio |
| `quality_tiers` | Generate Low/Medium/High/Ultra settings |
| `regression_test` | Screenshot comparison against baseline |
| `detect_issues` | Z-fighting, floating objects, missing colliders, clipping |
| `stress_test` | Spawn max entities, check frame rate stability |

---

## External Tool Integration Map (34 Tools)

### AI 3D Generation
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 1 | Tripo3D | Python SDK | Direct import |
| 2 | Meshy | REST API | HTTP client |
| 3 | Rodin/Hyper3D | REST API | HTTP client |
| 4 | Stability SF3D | Open source Python | Local execution |
| 5 | Hunyuan3D 3.5 | REST API | HTTP client |

### AI Texture
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 6 | Ubisoft CHORD | Open source Python + ComfyUI | Local execution |
| 7 | Scenario | REST API | HTTP client |
| 8 | Material Maker | CLI (v1.5+) | Subprocess |
| 9 | Dream Textures | Blender addon | Blender bpy |
| 10 | SD Inpainting | Local / API | ComfyUI API |
| 11 | ControlNet | Local | ComfyUI API |

### Texture Processing
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 12 | Real-ESRGAN | CLI binary | Subprocess |
| 13 | Normal map gen | Python | Direct import |

### Mesh Processing
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 14 | PyMeshLab | Python (pip) | Direct import |
| 15 | xatlas-python | Python (pip) | Direct import |
| 16 | fast-simplification | Python (pip) | Direct import |
| 17 | Quad Remesher | Blender addon | Blender bpy |

### Terrain
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 18 | Gaea | CLI (Build Swarm) | Subprocess + JSON |
| 19 | World Machine | CLI + XML | Subprocess |

### Vegetation
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 20 | EZ Tree | Python | Direct import |
| 21 | TreeGen | Python + Blender | Blender bpy |

### AI Animation
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 22 | HY-Motion 1.0 | Open source Python | Local execution |
| 23 | MotionGPT | Open source Python | Local execution |
| 24 | Mixamo | Web API | HTTP client |
| 25 | Cascadeur | Bridge addon | Blender bpy |

### AI Audio
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 26 | ElevenLabs | REST API | HTTP client |
| 27 | Stability Audio | REST API | HTTP client |
| 28 | Bark | Open source Python | Local execution |
| 29 | MusicGen/AudioCraft | Open source Python | Local execution |

### AI Image/Concept
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 30 | Stable Diffusion/FLUX | Local / API | ComfyUI API |
| 31 | ComfyUI | Local (has HTTP API) | HTTP client |

### Analysis/Review
| # | Tool | Type | Integration |
|---|------|------|-------------|
| 32 | Gemini CLI | CLI tool | Subprocess |
| 33 | Sequential Thinking | MCP server | MCP protocol |

---

## Implementation Waves

### Wave 1: "I Can See and Edit" (Sessions 1-3) — HIGHEST PRIORITY
**Goal**: Visual feedback + surgical editing. This alone makes me 10x more effective.

1. Contact sheet rendering system (THE breakthrough for visual feedback)
2. Mesh analysis + topology grading
3. Surgical mesh editing (select region, sculpt, boolean, extrude)
4. Surgical texture editing (mask region, inpaint, recolor, fix seams)
5. Token-efficient compound tool refactor (all servers)
6. Turntable/comparison/wireframe preview modes
7. Gemini visual review integration

**After Wave 1**: I can see what I'm doing, edit specific parts, and get visual quality feedback.

### Wave 2: "I Can Rig Anything" (Sessions 4-6)
**Goal**: Any creature, rigged correctly, first time.

8. 10 creature rig templates (Rigify-based)
9. Facial rigging system (with monster-specific expressions)
10. Spring/jiggle bone system (hair, capes, tails)
11. Weight painting with auto-validation + deformation contact sheets
12. Shape keys for expressions and damage states
13. Ragdoll auto-setup from rig
14. Rig retargeting between different body types

**After Wave 2**: Rig any creature in ~30 minutes with validation, not 72 hours broken.

### Wave 3: "I Can Animate Anything" (Sessions 7-9)
**Goal**: Procedural + AI-generated animation for any creature type.

15. All procedural gait generators (biped through arachnid)
16. Attack/death/hit/spawn/special animations
17. Animation contact sheet preview system
18. Root motion + animation events
19. HY-Motion/MotionGPT AI motion integration
20. Secondary motion physics (jiggle, spring, cloth)
21. Mixamo retargeting pipeline

**After Wave 3**: Generate and validate animations for any creature type.

### Wave 4: "I Can Build Worlds" (Sessions 10-12)
**Goal**: AAA environments from description.

22. Advanced terrain (caves, rivers, roads, cliffs, water)
23. Town/dungeon/interior layout generation
24. Modular building kits
25. Vegetation + prop scatter with biome rules
26. Breakable/ruins generation
27. Gaea integration for professional terrain
28. Environmental lighting + atmosphere

**After Wave 4**: Generate complete environments from descriptions.

### Wave 5: "It Feels AAA" (Sessions 13-16)
**Goal**: VFX, audio, and UI that make it feel like a real game.

29. VFX pipeline (particles, shaders, post-processing)
30. VeilBreakers-specific VFX (brand damage, corruption visuals)
31. Audio pipeline (SFX, music, voice, spatial)
32. UI building (full screen generation, not just validation)
33. UI polish (juice, transitions, tooltips, HUD elements)
34. Combat ability creation pipeline
35. Screen effects (shake, vignette, flash)

**After Wave 5**: Game looks and sounds like a AAA title.

### Wave 6: "Ship It" (Sessions 17-20)
**Goal**: Build, test, and optimize for release.

36. Build pipeline automation
37. Performance benchmarking
38. Asset auditing and optimization
39. Visual regression testing
40. Stress testing
41. Platform-specific validation
42. Quality tier generation
43. Full end-to-end pipeline test

**After Wave 6**: Production-ready build pipeline.

---

## Gemini Review Integration Points

Gemini acts as the "art director" — the visual quality eye that Claude lacks.

| Checkpoint | What Gemini Reviews |
|-----------|-------------------|
| After texture creation/editing | Color accuracy, detail quality, material convincingness |
| After UI changes | Layout balance, visual hierarchy, readability, AAA polish |
| After lighting setup | Mood, atmosphere, shadow quality, color temperature |
| After animation (contact sheet) | Motion quality, weight, timing, appeal |
| After VFX creation | Effect quality, readability, performance concern flags |
| After environment generation | Composition, scale, believability, mood |
| After character/creature creation | Design appeal, silhouette readability, AAA quality level |

---

## Estimated Impact Summary

| Capability | Before | After |
|-----------|--------|-------|
| Rig any creature | 72 hrs, broken | ~30 min, validated |
| Edit specific model part | Impossible | Select → sculpt → validate |
| Edit specific texture region | Impossible | Mask → inpaint/recolor → preview |
| Create walk cycle | Can't verify | Procedural + contact sheet, 5 min |
| Build environment | One object at a time | Full biome generation, 20 min |
| Create VFX | Zero capability | VFX Graph from description |
| Generate audio | Zero capability | AI SFX/music/voice generation |
| Build UI screen | Write UXML blindly | Generate + validate + Gemini review |
| Performance check | Manual profiling | Automated benchmarks + reports |
| Visual QA | Can't see the game | Screenshots + regression + Gemini |

---

## Token Budget

| Component | Tools | Est. Context Tokens |
|-----------|-------|-------------------|
| blender-gamedev-mcp | 12 compound tools | ~2,400 |
| asset-pipeline-mcp | 6 compound tools | ~1,200 |
| unity-enhanced-mcp | 8 compound tools | ~1,600 |
| **Total** | **26 tools** | **~5,200** |

Compare to V1's individual tool approach: ~200 tools at ~200 tokens each = ~40,000 tokens.
**V2 saves ~35,000 tokens per conversation.** That's 35K tokens back for actual reasoning.

---

*Master Plan V2.0 — March 2026*
*~200 capabilities across 26 compound tools in 3 MCP servers*
*Integrating 34 external tools/APIs*
*Covering 10 stages of AAA game development*
*Researched from 100+ sources across the game dev tool ecosystem*
