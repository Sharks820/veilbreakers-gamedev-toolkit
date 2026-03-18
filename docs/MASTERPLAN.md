# AI GAME DEVELOPMENT TOOLKIT - MASTER PLAN

## Mission
Transform Claude into a **multi-million dollar equivalent game development team** by building custom MCP servers that give it the capabilities of 3D artists, technical artists, animators, environment artists, UI/UX designers, and QA engineers — all with built-in validation so nothing ships broken.

## The Core Problem (Why Rigging Took 72 Hours)
Every weakness traces to **one root cause**: blind execution without feedback loops.

| Problem | Root Cause | Solution |
|---------|-----------|----------|
| Broken rigs | Can't see deformation | Auto-test at 8 standard poses, return contact sheet |
| Bad topology | Can't inspect mesh quality | Programmatic mesh analysis (non-manifold, poles, edge flow) |
| Texture issues | Can't see UV/material results | Render preview + UV quality metrics |
| UI layout bugs | Can't see game running | Screenshot capture + layout validation rules |
| Animation glitches | Can't see motion | Render animation as contact sheet (every 4th frame) |
| Import failures | No pipeline validation | Automated FBX export → Unity import → verification |

**The fix: Every operation returns structured validation data + visual proof.**

---

## Architecture: 3 Custom MCP Servers

```
                    ┌─────────────────────────────────────┐
                    │           CLAUDE (Opus 4.6)          │
                    │     Game Development AI Director     │
                    └──────┬──────────┬──────────┬────────┘
                           │          │          │
              ┌────────────▼──┐  ┌────▼────────┐  ┌▼─────────────────┐
              │   BLENDER     │  │   ASSET      │  │   UNITY          │
              │   GAMEDEV     │  │   PIPELINE   │  │   ENHANCED       │
              │   MCP         │  │   MCP        │  │   MCP            │
              │               │  │              │  │                  │
              │ - Rigging     │  │ - Tripo3D    │  │ - Visual Test    │
              │ - Animation   │  │ - CHORD PBR  │  │ - UI Validation  │
              │ - Topology    │  │ - Gaea       │  │ - Anim Setup     │
              │ - Texturing   │  │ - PyMeshLab  │  │ - Scene Build    │
              │ - Environment │  │ - Real-ESRGAN│  │ - AI/Mobs        │
              │ - Export      │  │ - xatlas UV  │  │ - Performance    │
              └───────┬───────┘  └──────┬───────┘  └────────┬─────────┘
                      │                 │                    │
                      ▼                 ▼                    ▼
                  [Blender]     [External APIs +      [Unity Editor]
                  (bpy API)     Local Python Tools]   (C# Scripting)
```

### + Gemini Visual Reviewer
Gemini CLI receives screenshots at key checkpoints and provides visual quality feedback. Acts as the "art director" eye that Claude lacks.

---

## MCP 1: `veilbreakers-blender-mcp`

**Tech**: Python + FastMCP 3.0 + Blender bpy API (socket bridge to Blender addon)
**Purpose**: Replace a team of 3D artists, technical artists, and animators

### Module A: Rigging (The 72-Hour Fix)

| Tool | What It Does | Validation |
|------|-------------|------------|
| `analyze_mesh_for_rigging` | Scans mesh topology, finds joints, reports vert count, symmetry, problem areas | Returns structured report: {verts, faces, symmetry_score, problem_areas[]} |
| `create_rig_rigify` | Creates Rigify meta-rig fitted to mesh. Templates: humanoid, quadruped, bird, insect, serpent, floating | Returns bone count, hierarchy, screenshot of rig overlay |
| `create_rig_creature` | Custom creature rig builder. Params: limb_count, wing_type, tail_segments, extra_appendages | Returns rig hierarchy + constraint list |
| `setup_ik_chains` | Configures IK for all limb chains. Supports: 2-bone IK, spline IK (tails/tentacles), multi-target | Returns chain list with pole vectors |
| `auto_weight_paint` | Heat-based auto weights → immediate deformation test | Returns weight quality score per bone group |
| `test_deformation` | Poses rig at 8 standard poses (T, A, crouch, arms-up, kick, twist, extreme-bend, rest). Renders multi-angle contact sheet | Returns 8-pose contact sheet image + per-pose stretch/clip report |
| `fix_weight_issues` | Auto-fix: normalize weights, clean zeros, smooth problem areas, fix bleeding | Returns before/after weight comparison |
| `validate_rig` | Full validation: unweighted verts, weight bleeding, bone rolls, symmetry, hierarchy, constraint cycles | Returns pass/fail per check with details |

#### Creature Rig Templates (Built on Rigify Feature Sets)

| Template | Bones | Special Features |
|----------|-------|-----------------|
| **Humanoid** | ~120 | Standard Rigify + face rig + finger controls |
| **Quadruped** | ~140 | 4-leg IK, spine chain, tail spline IK |
| **Hexapod (Insect)** | ~180 | 6-leg IK with alternating tetrapod gait markers, mandible controls |
| **Winged Biped** | ~160 | Wing fold/flap/spread controls, membrane stretch bones, flight pose presets |
| **Winged Quadruped (Dragon)** | ~200 | 4-leg + wings + tail + jaw, breath weapon pose |
| **Serpent/Worm** | ~60+ | Spline IK chain (variable segments), slither gait markers |
| **Floating/Ethereal** | ~40 | Lattice deform + tentacle spline IK, bob/sway procedural controls |
| **Multi-Armed** | ~160+ | N-arm support with independent IK, coordinated gesture system |
| **Arachnid** | ~200 | 8-leg IK, pedipalp controls, abdomen deform, web-spin pose |
| **Amorphous/Blob** | ~20 | Shape key driven, lattice mesh deform, no skeleton needed |

#### Wing Rigging System (Detailed)
```
Wing Structure:
  shoulder_wing → upper_wing → forearm_wing → hand_wing → [finger_bones x3-5]
                                                          → membrane_stretch_bones
Controls:
  - fold_ctrl: Tucks wing against body (FK chain)
  - flap_ctrl: Primary flight motion (driven key on rotation)
  - spread_ctrl: Full extension (blend between folded/spread shape keys)
  - tip_ctrls: Per-finger fine control for expression
  - membrane_lattice: Stretches skin between fingers

Constraints:
  - Copy Rotation (shoulder → body twist)
  - Stretch To (membrane bones → finger tips)
  - Limit Rotation (per joint, anatomically correct ranges)
  - Damped Track (wrist → flight direction)
```

### Module B: Animation

| Tool | What It Does | Validation |
|------|-------------|------------|
| `create_walk_cycle` | Procedural walk/run cycle. Params: gait_type (biped/quad/hexapod/serpent), speed, bounce, stride_length | Returns animation clip + contact sheet |
| `create_fly_cycle` | Wing flap cycle with configurable: frequency, amplitude, glide_ratio, hover_mode | Returns clip + contact sheet |
| `create_idle_animation` | Breathing, weight shift, secondary motion (ears, tail, tentacles) | Returns clip + contact sheet |
| `create_attack_animation` | Anticipation → strike → follow-through. Params: attack_type, speed, power_level | Returns clip + contact sheet |
| `apply_mixamo_animation` | Downloads Mixamo animation, retargets to custom rig | Returns retarget quality report |
| `render_animation_preview` | Renders full animation as GIF or contact sheet (every Nth frame) | Returns viewable animation preview |
| `validate_animation` | Checks: foot sliding, interpenetration, impossible poses, smooth curves | Returns issue list with frame numbers |
| `procedural_secondary_motion` | Adds physics-based jiggle/spring to tails, ears, capes, hair, tentacles | Returns spring parameter summary |

#### Contact Sheet System (How I "See" Animation)
Instead of single screenshots, render a **contact sheet** showing the full motion arc:
```
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ F01 │ F04 │ F08 │ F12 │ F16 │ F20 │ F24 │ F28 │
│     │     │     │     │     │     │     │     │
│  T  │ /   │ /   │  |  │  \  │  \  │  T  │ ... │
│ /|\ │/|\  │/|\  │ /|\ │ /|\ │ /|\│ /|\ │     │
│ / \ │ | \ │/ |  │ / \ │  | \│/ | │ / \ │     │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
  Key poses visible in one image = I can evaluate the motion
```
Rendered from 3 angles (front, side, 3/4) at configurable frame intervals.

#### Procedural Gait Generation (Code-Driven)

**Biped Walk**: Phase-offset sine waves
```
left_leg_phase  = sin(time * frequency)
right_leg_phase = sin(time * frequency + PI)  // 180 offset
hip_bob         = abs(sin(time * frequency * 2)) * bounce_height
spine_twist     = sin(time * frequency) * twist_amount
```

**Quadruped Walk**: Diagonal pairs
```
front_left  = sin(t * freq)
back_right  = sin(t * freq)           // same phase (diagonal pair)
front_right = sin(t * freq + PI)
back_left   = sin(t * freq + PI)      // opposite diagonal
```

**Hexapod (Alternating Tetrapod)**:
```
Group A: legs[0], legs[2], legs[4]  // alternating legs
Group B: legs[1], legs[3], legs[5]
phase_A = sin(t * freq)
phase_B = sin(t * freq + PI)         // antiphasic
```

**Serpent**: Traveling sine wave along spine chain
```
for each bone[i] in spine_chain:
    bone[i].rotation.z = sin(time * freq - i * wave_offset) * amplitude
    // Wave travels down the body
```

### Module C: Topology Analysis & Repair

| Tool | What It Does | Validation |
|------|-------------|------------|
| `analyze_topology` | Full mesh analysis: non-manifold edges, n-gons, tri count, pole locations, edge flow quality | Returns scored report card (A-F per category) |
| `fix_topology_auto` | Auto-fix: remove doubles, fix normals, fill holes, dissolve degenerate faces, remove loose geometry | Returns fix count per category |
| `retopologize` | Quad remesh with target face count, preserves hard edges and UV seams | Returns before/after face count + preview |
| `analyze_uvs` | UV quality: stretch, overlap, island count, texel density consistency, seam placement | Returns UV quality score + heatmap render |
| `auto_unwrap` | Smart UV projection with xatlas. Params: island_margin, target_stretch | Returns UV layout preview |
| `check_game_ready` | Full game-readiness check: vert count budget, UV2 lightmap, material count, bone count | Returns pass/fail checklist |

#### Topology Scoring System
```
Grade A (Excellent): All quads, good edge flow, no poles in deform areas, clean UVs
Grade B (Good):      <5% tris, minor pole issues, acceptable UVs
Grade C (Acceptable): Some n-gons, edge flow issues in non-critical areas
Grade D (Needs Work): Significant topology problems affecting deformation
Grade F (Broken):     Non-manifold geometry, inverted normals, degenerate faces
```

### Module D: Texturing

| Tool | What It Does | Validation |
|------|-------------|------------|
| `create_pbr_material` | Generates full PBR material (albedo, normal, roughness, metallic, AO) from description | Returns material preview render |
| `bake_textures` | Bakes high-poly → low-poly maps (normal, AO, curvature, thickness) | Returns bake preview per map |
| `generate_ai_texture` | Calls CHORD/Scenario API for AI texture generation from text prompt | Returns generated texture set |
| `upscale_texture` | Real-ESRGAN upscale (2x/4x) with game texture optimization | Returns before/after comparison |
| `validate_textures` | Checks: resolution power-of-2, proper format, UV coverage, tiling seams | Returns validation report |
| `create_tileable_texture` | Generates seamless tileable texture from prompt or reference | Returns tileability test (2x2 grid preview) |

### Module E: Environment Generation

| Tool | What It Does | Validation |
|------|-------------|------------|
| `generate_terrain` | Creates terrain heightmap. Params: style (mountains/plains/islands/volcanic), size, detail | Returns heightmap + 3D preview |
| `scatter_vegetation` | Geometry Nodes scatter system. Params: density, types (trees/grass/rocks/flowers), biome rules | Returns overhead + perspective previews |
| `generate_building` | Procedural building from params: style, floors, width, roof_type, material_set | Returns 4-angle preview |
| `create_biome` | Full biome setup: terrain + vegetation + props + lighting. Presets: forest, desert, tundra, swamp, volcanic | Returns panoramic preview |
| `batch_generate_props` | Generate N variations of a prop type (barrels, crates, lamps, etc.) | Returns grid preview of all variations |

### Module F: Export Pipeline

| Tool | What It Does | Validation |
|------|-------------|------------|
| `export_to_unity` | FBX export with Unity settings (scale 1.0, Y-up, bone naming convention) | Returns export report + file size |
| `export_with_lods` | Exports mesh + auto-generated LODs (100%, 50%, 25%, 10%) | Returns LOD chain preview |
| `validate_export` | Re-imports exported file, checks: scale, orientation, bone count, material slots | Returns validation pass/fail |
| `batch_export` | Exports all modified objects to Unity project folder | Returns batch report |

---

## MCP 2: `veilbreakers-asset-pipeline-mcp`

**Tech**: Python + FastMCP 3.0 + External API clients
**Purpose**: Bridge AI generation services and mesh processing tools

### Module A: 3D Model Generation

| Tool | API | What It Does |
|------|-----|-------------|
| `generate_model_tripo` | Tripo3D Python SDK | Text/image → 3D model with clean quad topology + PBR textures |
| `generate_model_meshy` | Meshy REST API | Fast iteration 3D generation, good for prototyping |
| `generate_model_rodin` | Hyper3D Rodin API | Highest quality generation (10B param model) |
| `check_generation_status` | All | Poll async task completion |
| `download_and_process` | All + PyMeshLab | Download generated model → auto-cleanup → optimize → export |

### Module B: Texture Generation

| Tool | Backend | What It Does |
|------|---------|-------------|
| `generate_pbr_chord` | Ubisoft CHORD (local/open-source) | Text/image → full PBR map set (albedo, normal, height, roughness, metallic) |
| `generate_texture_scenario` | Scenario REST API | AI texture with custom model training (match your art style) |
| `generate_tileable` | Material Maker CLI | Procedural tileable texture from node graph preset |
| `upscale_texture` | Real-ESRGAN (local) | 2x/4x AI upscaling for game textures |
| `generate_normal_map` | CHORD / local | Single image → normal map extraction |

### Module C: Terrain Generation

| Tool | Backend | What It Does |
|------|---------|-------------|
| `generate_terrain_gaea` | Gaea CLI (Build Swarm) | Professional terrain from Gaea node graphs. Params: preset, seed, resolution |
| `generate_heightmap` | Local Python (noise + erosion) | Procedural heightmap with thermal/hydraulic erosion simulation |
| `terrain_to_unity` | Local | Convert heightmap → Unity Terrain Data format with splatmaps |

### Module D: Mesh Processing

| Tool | Backend | What It Does |
|------|---------|-------------|
| `analyze_mesh` | PyMeshLab | Topology analysis: non-manifold, self-intersection, holes, duplicate faces |
| `repair_mesh` | PyMeshLab | Auto-fix all detected issues |
| `simplify_mesh` | fast-simplification / PyMeshLab | Quadric edge collapse decimation with quality preservation |
| `generate_lods` | PyMeshLab | Multi-level LOD chain generation (configurable percentages) |
| `auto_uv_unwrap` | xatlas-python | Automatic UV unwrapping with configurable quality parameters |
| `optimize_for_game` | PyMeshLab + xatlas | Full pipeline: clean → optimize → UV → validate → export |

### Module E: Quality Validation

| Tool | What It Does |
|------|-------------|
| `validate_asset` | Comprehensive check: poly budget, UV quality, texture resolution, material count |
| `compare_meshes` | Hausdorff distance between original and processed mesh (did simplification lose too much?) |
| `check_unity_ready` | Verify asset meets Unity import requirements (scale, axes, naming, materials) |

---

## MCP 3: `veilbreakers-unity-enhanced-mcp`

**Tech**: C# Unity Editor scripts + Node.js MCP bridge (extends existing mcp-unity)
**Purpose**: Replace UI/UX designers, QA team, level designers, and AI programmers

### Module A: Visual Testing & UI Validation

| Tool | What It Does | Why It Matters |
|------|-------------|----------------|
| `capture_game_view` | High-res screenshot of Game view at specified resolution | Visual verification of any change |
| `capture_ui_element` | Screenshot of specific UI element by name/path | Targeted UI testing |
| `validate_ui_layout` | Traverses UI Toolkit VisualElement tree. Checks: overlaps, zero-size, overflow, contrast | Catches layout bugs programmatically |
| `test_responsive` | Captures screenshots at 5 resolutions (1920x1080, 2560x1440, 3840x2160, 1280x720, mobile) | Responsive design validation |
| `compare_screenshots` | Pixel diff between two screenshots, highlights changes | Visual regression testing |
| `gemini_visual_review` | Sends screenshot to Gemini CLI with review prompt. Gets visual quality assessment | "Art director" eye for every change |
| `ui_hierarchy_dump` | Full UI Toolkit tree with: element types, classes, computed sizes, visibility | Debug UI structure without seeing it |

#### Gemini Visual Review Workflow
```
1. Claude makes a UI change
2. capture_game_view → screenshot
3. gemini_visual_review(screenshot, "Review this game UI for:
   - Visual hierarchy and readability
   - Color harmony and contrast
   - Layout balance and spacing
   - AAA quality assessment
   - Specific issues or improvements")
4. Gemini returns structured feedback
5. Claude iterates based on feedback
```

### Module B: Animation Setup

| Tool | What It Does |
|------|-------------|
| `create_animator_controller` | Programmatically create Animator Controller with states, transitions, parameters |
| `configure_avatar` | Set up Humanoid/Generic avatar mapping for imported FBX |
| `setup_animation_rigging` | Configure Animation Rigging constraints (Two-Bone IK, Multi-Aim, etc.) |
| `preview_animation` | Play animation, capture frames as contact sheet |
| `setup_blend_tree` | Create blend trees for locomotion (walk/run/idle blending) |
| `import_animation_clips` | Import FBX animations with proper settings (loop, root motion, events) |

### Module C: Scene Building

| Tool | What It Does |
|------|-------------|
| `create_terrain` | Generate Unity Terrain from heightmap data with splat maps |
| `scatter_objects` | Distribute objects across terrain (trees, rocks, props) with density rules |
| `setup_lighting` | Configure: directional light, ambient, fog, post-processing volume (URP) |
| `build_with_probuilder` | Create ProBuilder geometry: rooms, corridors, platforms, stairs |
| `place_prefabs` | Position prefabs in scene from layout description |
| `setup_navmesh` | Bake NavMesh with agent settings, add NavMesh Links for jumps/drops |
| `configure_camera` | Set up camera rigs: follow, orbit, cinematic, combat |

### Module D: AI / Mob Systems

| Tool | What It Does |
|------|-------------|
| `create_mob_controller` | Generate C# MonoBehaviour for mob with: patrol, chase, attack, flee states |
| `setup_aggro_system` | Configure aggro: detection range, aggro decay, threat table, leash distance |
| `create_patrol_route` | Define patrol waypoints, dwell times, random deviation |
| `setup_spawner` | Create spawn system: max count, respawn timer, spawn conditions, area bounds |
| `create_behavior_tree` | Generate behavior tree ScriptableObject with: selector, sequence, condition, action nodes |
| `test_mob_behavior` | Run simulation, capture mob paths/decisions over N seconds |

### Module E: Performance Automation

| Tool | What It Does |
|------|-------------|
| `profile_scene` | Capture: frame time, draw calls, batches, tris, memory, SetPass calls |
| `generate_lods` | Auto-generate LODGroup for all meshes in scene using UnityMeshSimplifier |
| `bake_lightmaps` | Trigger lightmap bake with progress monitoring |
| `bake_occlusion` | Bake occlusion culling data |
| `setup_streaming` | Configure addressable/streaming for large scenes |
| `performance_report` | Full performance analysis with specific recommendations |

---

## External Tool Requirements

### Must Install (Free / Open-Source)

| Tool | Install | Purpose |
|------|---------|---------|
| **Python 3.10+** | `winget install Python` | MCP server runtime |
| **FastMCP** | `pip install fastmcp` | MCP framework |
| **PyMeshLab** | `pip install pymeshlab` | Mesh processing |
| **xatlas-python** | `pip install xatlas` | UV unwrapping |
| **fast-simplification** | `pip install fast-simplification` | Mesh decimation |
| **Real-ESRGAN** | GitHub release binary | Texture upscaling |
| **Ubisoft CHORD** | `git clone` + ComfyUI | PBR texture generation |
| **Material Maker** | Download v1.5+ | Procedural textures (CLI) |

### Recommended (Free Tier Available)

| Tool | Cost | Purpose |
|------|------|---------|
| **Tripo3D API** | $19.90/mo starter | AI 3D model generation (user already has this) |
| **Scenario API** | Compute units | AI texture generation with style training |
| **Gaea** | Community free | Professional terrain generation |

### Blender Addons to Install

| Addon | Cost | Purpose |
|-------|------|---------|
| **Rigify** | Free (built-in) | Rigging foundation |
| **CloudRig** | Free | Enhanced Rigify for production |
| **Auto-Rig Pro** | ~$40 | Quick rigging for standard characters |
| **Quad Remesher** | ~$100 | Industry-standard retopology |
| **Zen UV** | ~$30 | Professional UV tools |

### Unity Packages to Add

| Package | Source | Purpose |
|---------|--------|---------|
| **ProBuilder** | Package Manager | In-editor level building |
| **Animation Rigging** | Package Manager | Runtime IK + constraints |
| **AI Navigation** | Package Manager | NavMesh system |
| **UnityMeshSimplifier** | GitHub/NuGet | LOD generation |
| **IvanMurzak Unity-MCP** | Consider switching | 100+ tools, Roslyn C# execution |

---

## Unity MCP Upgrade Path

**Current**: CoderGamester/mcp-unity (basic tools)
**Recommended**: Evaluate IvanMurzak/Unity-MCP for:
- 100+ native tools (vs current ~20)
- Roslyn-based instant C# compilation (execute any C# in editor without recompile)
- Custom tool creation via C# attribute decorators
- Runtime agents (NPC control from AI)

**Also consider**: CoplayDev/unity-mcp for `manage_graphics` (33 rendering/post-processing actions)

**Strategy**: Could run multiple Unity MCPs for different capabilities, or fork one and add our custom tools.

---

## Implementation Roadmap

### Phase 1: Foundation (Session 1-2)
**Goal**: Get the MCP server framework running with basic Blender tools

1. Create `Tools/mcp-servers/blender-gamedev/` project structure
2. Build FastMCP server skeleton with Blender socket bridge
3. Implement: `analyze_mesh_for_rigging`, `analyze_topology`, `test_deformation`
4. Implement: contact sheet rendering system (the "sight" breakthrough)
5. Test with existing VeilBreakers monster model

**Deliverable**: I can see meshes, analyze topology, and test deformations

### Phase 2: Rigging Revolution (Session 3-4)
**Goal**: Creature rigging that works first time

1. Implement all 10 creature rig templates (Rigify-based)
2. Build wing rigging system with membrane support
3. Implement `auto_weight_paint` with deformation testing
4. Build `validate_rig` comprehensive checker
5. Test: rig a multi-limbed monster end-to-end

**Deliverable**: Full creature rigging pipeline with validation

### Phase 3: Animation Pipeline (Session 5-6)
**Goal**: Procedural animation generation

1. Implement gait generators (biped, quad, hexapod, serpent, flying)
2. Build idle/attack/death animation generators
3. Implement secondary motion system (tails, wings, jiggle)
4. Build animation contact sheet preview system
5. Implement Mixamo retargeting bridge

**Deliverable**: Generate and validate animations for any creature type

### Phase 4: Asset Pipeline (Session 7-8)
**Goal**: AI-powered asset generation and processing

1. Build `veilbreakers-asset-pipeline-mcp` with Tripo3D integration
2. Integrate CHORD for PBR texture generation
3. Wire up PyMeshLab for mesh processing pipeline
4. Build xatlas UV unwrapping integration
5. Implement Real-ESRGAN texture upscaling

**Deliverable**: Text → 3D model → cleaned → textured → game-ready pipeline

### Phase 5: Unity Enhancement (Session 9-10)
**Goal**: Visual testing and scene building

1. Build Unity Editor scripts for screenshot capture + UI inspection
2. Create MCP bridge for enhanced Unity tools
3. Implement Gemini visual review pipeline
4. Build responsive UI testing system
5. Implement animation setup automation

**Deliverable**: Visual validation for every Unity change

### Phase 6: Environment & World Building (Session 11-12)
**Goal**: AAA environment creation

1. Implement Geometry Nodes terrain generation in Blender
2. Build vegetation scatter system
3. Integrate Gaea CLI for professional terrain
4. Implement procedural building generator
5. Build biome presets (forest, desert, tundra, swamp, volcanic, urban)

**Deliverable**: Generate complete biomes and environments

### Phase 7: AI & Mob Systems (Session 13-14)
**Goal**: Living world with intelligent creatures

1. Build mob controller generator (patrol, aggro, combat, flee)
2. Implement NavMesh automation
3. Build spawn system generator
4. Create behavior tree scaffolding
5. Wire up procedural animation to Unity (IK foot placement, look-at, etc.)

**Deliverable**: Spawn, path, and fight monsters with AI behavior

### Phase 8: Integration & Polish (Session 15-16)
**Goal**: End-to-end pipeline working

1. Full pipeline test: concept → model → rig → animate → texture → export → import → place in scene
2. Performance profiling and optimization tools
3. Batch operations for entire asset libraries
4. Documentation and preset library
5. Gemini review integration across all phases

**Deliverable**: Complete game development AI toolkit

---

## Estimated Impact

| Capability | Before (Current) | After (With Toolkit) |
|-----------|-------------------|---------------------|
| Rig a monster | 72 hours, broken | ~30 min, validated |
| Create walk cycle | Manual keyframing, can't verify | Procedural + contact sheet, 5 min |
| Texture a model | Basic material setup | AI PBR generation + baking, 10 min |
| Build an environment | Place objects one by one | Procedural biome generation, 20 min |
| Check UI layout | Can't see it | Screenshot + validation + Gemini review |
| Fix topology | Blind Python execution | Scored analysis + auto-repair |
| Import to Unity | Manual settings, hope it works | Automated pipeline with verification |
| Create mob AI | Write code, hope behavior works | Generated + simulated + tested |

---

## Key Insight: The Gemini Partnership

Claude handles: code, architecture, tool execution, pipeline orchestration
Gemini handles: visual review, art direction feedback, web research, second opinions

This isn't just "two AIs" — it's leveraging each model's strengths:
- Claude + Serena = deep code understanding
- Claude + Blender MCP = 3D creation with validation
- Claude + Unity MCP = editor control with automation
- Gemini + screenshots = the "eyes" Claude doesn't have
- Gemini + web search = current trends, reference material, documentation

---

## Files to Create

```
Tools/
  mcp-servers/
    blender-gamedev/
      server.py              # FastMCP server entry point
      blender_addon.py       # Blender-side addon (socket listener)
      modules/
        rigging.py           # Rig creation, weight painting, validation
        animation.py         # Procedural animation, keyframing, preview
        topology.py          # Mesh analysis, repair, retopology
        texturing.py         # Material creation, baking, AI integration
        environment.py       # Terrain, scatter, buildings
        export.py            # FBX export pipeline
      templates/
        rigs/                # Rigify meta-rig templates per creature type
        animations/          # Animation curve presets
        materials/           # PBR material presets
      requirements.txt

    asset-pipeline/
      server.py              # FastMCP server entry point
      modules/
        tripo.py             # Tripo3D API client
        chord.py             # Ubisoft CHORD integration
        meshlab.py           # PyMeshLab wrapper
        textures.py          # Texture gen/upscale pipeline
        terrain.py           # Gaea CLI + procedural heightmaps
      requirements.txt

    unity-enhanced/
      server.py              # Node.js MCP server (extends mcp-unity)
      Editor/
        VisualTestingTools.cs    # Screenshot, UI inspection, comparison
        AnimationSetupTools.cs   # Animator, avatar, rigging setup
        SceneBuildingTools.cs    # Terrain, scatter, lighting, ProBuilder
        MobSystemTools.cs        # AI, NavMesh, spawning, behavior trees
        PerformanceTools.cs      # Profiling, LOD, lightmaps, occlusion
```

---

*Master Plan v1.0 — March 2026*
*Built from research across 100+ sources, 6+ MCP servers, 30+ AI tools, and 50+ Blender/Unity APIs*
