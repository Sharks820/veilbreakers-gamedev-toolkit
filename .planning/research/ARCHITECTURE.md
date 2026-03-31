# Architecture Patterns: AAA Procedural 3D Generation

**Domain:** AAA procedural 3D generation for dark fantasy RPG (Blender + Unity pipeline)
**Researched:** 2026-03-30
**Confidence:** HIGH (verified against existing 838KB codebase, 100+ handler files, AAA studio references, and Blender/Unity API)

## System Overview

The AAA procedural 3D system follows a layered pipeline architecture where each stage produces spec dicts (pure-logic data) that downstream stages consume. The existing codebase already implements the critical **pure-logic / bpy-guarded split**: all generation logic runs without Blender imports, producing serializable MeshSpec dicts, and only the final materialization step in `_mesh_bridge.py` touches bpy/bmesh.

This document covers two perspectives: (1) the existing codebase architecture with concrete file-level detail, and (2) the target AAA architecture for the v4.0 milestone.

```
+====================================================================+
|                    GENERATION LAYER (Blender)                        |
|                                                                     |
|  +-------------------+  +---------------------+  +---------------+  |
|  | Imperative Gen    |  | Declarative Gen     |  | AI Generation |  |
|  | (bpy/bmesh)       |  | (Geometry Nodes)    |  | (API calls)   |  |
|  |                   |  |                     |  |               |  |
|  | - Buildings       |  | - Facade scatter    |  | - Tripo v3.0  |  |
|  | - Terrain         |  | - Detail instancing |  | - Hunyuan3D   |  |
|  | - Mesh repair     |  | - Trim sheet UV     |  | - Rodin Gen-2 |  |
|  | - UV/texturing    |  | - Procedural mats   |  | - Marble      |  |
|  | - Rigging/anim    |  | - Repeat zones      |  |               |  |
|  +--------+----------+  +----------+----------+  +-------+-------+  |
|           |                         |                      |         |
+===========+=========================+======================+=========+
            |                         |                      |
            v                         v                      v
+====================================================================+
|                  PROCESSING PIPELINE (Python/Blender)                |
|                                                                     |
|  Repair -> UV (xatlas) -> Texture (PBR) -> Weathering -> LOD       |
|  game_check (budget) |  validate_palette (style) |  bake (maps)    |
|  Quality gates between every stage                                  |
+====================================================================+
                                    |
                                    v
+====================================================================+
|                  ORCHESTRATION LAYER (MCP Tools)                     |
|                                                                     |
|  asset_pipeline: compose_map, compose_interior, full_pipeline       |
|  Coordinates: terrain -> water -> roads -> buildings -> interiors   |
|              -> biome paint -> vegetation -> props -> LOD -> export  |
+====================================================================+
                                    |
                                    v
+====================================================================+
|                    EXPORT LAYER (Blender -> Unity)                   |
|                                                                     |
|  FBX/GLB export  ->  Unity import  ->  Asset post-processing       |
|  game_check      ->  Addressables  ->  Scene setup                  |
|                                                                     |
+====================================================================+
                                    |
                                    v
+====================================================================+
|                    RUNTIME LAYER (Unity URP)                         |
|                                                                     |
|  Forward+ Rendering  |  Addressables Streaming  |  NavMesh          |
|  SRP Batcher         |  GPU Instancing          |  Cinemachine 3.x  |
|  LOD Groups          |  Occlusion Culling       |  Interior Stream  |
|  Light Probes        |  Terrain Splatmaps       |  Day/Night Cycle  |
|                                                                     |
+====================================================================+
```

## Component Boundaries

### Core Components

| Component | Responsibility | Key Files | Inputs | Outputs |
|-----------|---------------|-----------|--------|---------|
| **Procedural Mesh Generator** | Create AAA-quality mesh geometry from parameters | `procedural_meshes.py` (838KB, 127+ generators) | Blueprint params (type, style, size, seed) | MeshSpec dicts `{vertices, faces, uvs, metadata}` |
| **Mesh Bridge** | Convert pure-logic MeshSpec to Blender geometry | `_mesh_bridge.py` (21KB, registry of all generators) | MeshSpec dict + type string | Blender mesh objects |
| **Building Grammar** | Grammar-based building composition from rules | `_building_grammar.py` (103KB), `building_quality.py` (104KB) | Style config + seed + constraints | List of geometry operation dicts |
| **Modular Kit** | Snap-together architecture pieces (5 styles) | `modular_building_kit.py` (55KB, 175 pieces) | Piece type + style + kwargs | MeshSpec per piece |
| **Terrain System** | Heightmap generation, erosion, biome mapping | `_terrain_noise.py` (41KB), `_terrain_erosion.py`, `_terrain_depth.py`, `terrain_features.py` (74KB), `terrain_materials.py` (87KB) | Terrain spec (size, resolution, biomes, seed) | Heightmap ndarray, splatmaps, biome map |
| **Settlement System** | Compose buildings + roads + props into locations | `settlement_generator.py` (90KB), `road_network.py` | Settlement type + terrain data | Building positions, road paths, prop placements |
| **Interior System** | Room layout, furniture, lighting, doors, occlusion | `_building_grammar.py` (interior_layout), `worldbuilding.py` (linked interior) | Interior spec (room types, connections, style) | Room shells, door markers, prop queues |
| **Scatter Engine** | Poisson disk sampling, biome filtering, context scatter | `_scatter_engine.py` (20KB), `environment_scatter.py` (30KB) | Biome map + rules + seed | Instance point tuples |
| **LOD Pipeline** | Silhouette-preserving decimation, collision meshes | `lod_pipeline.py` (31KB), `pipeline_lod.py` | Source mesh + asset type | LOD0-LOD3 chain + convex hull |
| **Material System** | Procedural PBR materials, weathering, trim sheets | `procedural_materials.py` (68KB), `weathering.py` (33KB), `texture_quality.py` | Material preset + roughness + wear | Principled BSDF node trees |
| **World Composer** | Place settlements/dungeons/POIs on terrain | `map_composer.py` (48KB), `world_map.py` (37KB), `worldbuilding_layout.py` (41KB) | map_spec dict | Complete world with all elements placed |
| **Pipeline Runner** | Orchestrate processing stages | `pipeline_runner.py` (47KB) | Object name + steps | Processed Blender objects |
| **AI Generation** | External 3D model generation via API | `tripo_client.py`, `tripo_studio_client.py` | Prompt/image + quality tier | GLB file with PBR textures |
| **Asset Catalog** | Track generated assets, metadata, dependencies | `asset_catalog.py` | Asset metadata dict | Catalog entries with lineage |

### Sub-System Communication Map

```
                    +------------------+
                    |  World Composer  |
                    |  (map_composer)  |
                    +--------+---------+
                             |
            +----------------+----------------+
            |                |                |
    +-------v------+  +-----v-------+  +----v--------+
    |   Terrain    |  | Settlement  |  |  Road       |
    |   System     |  | Generator   |  |  Network    |
    +-------+------+  +-----+-------+  +----+--------+
            |               |                |
            |        +------v-------+        |
            |        | Building     |        |
            +------->| Grammar      |<-------+
            |        +------+-------+
            |               |
            |        +------v-------+
            |        | Modular Kit  |
            |        +------+-------+
            |               |
            |        +------v-------+
            |        | Interior     |
            +------->| System       |
            |        +------+-------+
            |               |
    +-------v------+  +----v---------+
    | Biome Map    |  | Scatter      |
    +-------+------+  | Engine       |
            |         +----+---------+
            |              |
    +-------v------+  +----v---------+
    | Material     |  | Prop         |
    | System       |  | Generators   |
    +-------+------+  +----+---------+
            |              |
            +-------+------+
                    |
            +-------v------+
            |  LOD Pipeline |
            |  + Export     |
            +-------+------+
                    |
            +-------v------+
            | Asset Catalog |
            +--------------+
```

## Data Flow

### Primary Generation Flow (Map Composition)

This is the main flow triggered by `asset_pipeline compose_map`:

```
map_spec (dict from MCP tool call)
    |
    v
+---v------------------------+
| 1. TERRAIN GENERATION       |  _terrain_noise.py -> heightmap ndarray
|    seed + preset + size      |  _terrain_erosion.py -> eroded heightmap
|    -> heightmap + biome map  |  biome map from altitude/slope/moisture
+---+------------------------+
    |
    v
+---v------------------------+
| 2. WATER + RIVER CARVING    |  carve_river -> modify heightmap
|    heightmap + params        |  create_water -> water plane mesh
|    -> water geometry         |
+---+------------------------+
    |
    v
+---v------------------------+
| 3. ROAD NETWORK             |  road_network.py -> path curves
|    settlement positions      |  cosine-blended falloff carving
|    -> road curves            |  Modify heightmap under roads
+---+------------------------+
    |
    v
+---v------------------------+
| 4. SETTLEMENT PLACEMENT     |  settlement_generator.py -> building specs
|    terrain + biome map       |  Each building -> BuildingSpec via grammar
|    -> building geometry ops  |  Foundation height from heightmap sampling
+---+------------------------+
    |
    v
+---v------------------------+
| 5. INTERIOR GENERATION      |  For each building with interiors:
|    building spec             |  room layout -> furniture placement
|    -> interior specs         |  door/occlusion/lighting markers
+---+------------------------+
    |
    v
+---v------------------------+
| 6. BIOME MATERIAL PAINT     |  terrain_materials.py -> splatmap
|    heightmap + biome map     |  Material layers per biome
|    -> material regions       |  Height-based blending (not linear)
+---+------------------------+
    |
    v
+---v------------------------+
| 7. VEGETATION SCATTER       |  poisson_disk_sample -> points
|    biome map + rules         |  biome_filter_points -> valid spots
|    -> instance points        |  Collection instances (not duplicates)
+---+------------------------+
    |
    v
+---v------------------------+
| 8. PROP SCATTER             |  context_scatter -> prop positions
|    buildings + rooms         |  Near-building prop affinity
|    -> prop instances         |  Storytelling props via AAA-05
+---+------------------------+
    |
    v
+---v------------------------+
| 9. LOD GENERATION           |  lod_pipeline.py -> LOD chains
|    per-asset-type presets    |  Silhouette-preserving decimation
|    -> LOD groups             |  Collision meshes for physics
+---+------------------------+
    |
    v
+---v------------------------+
| 10. EXPORT + VALIDATE       |  blender_export -> FBX/glTF
|     game_check per asset     |  validate_export -> pass/fail report
|     -> export files          |  Asset catalog updated
+---+------------------------+
    |
    v
+---v------------------------+
| 11. UNITY INTEGRATION       |  Import to Assets/Art/
|     next_steps returned      |  Scene setup via unity_world tools
|     -> Unity scenes          |  NavMesh, lighting, streaming setup
+---+------------------------+
```

### Per-Asset Processing Pipeline

Triggered by `asset_pipeline cleanup`, `import_and_process`, or `full_pipeline`:

```
MeshSpec (from any generator)
    |
    v
REPAIR: remove_doubles, fix_normals, fill_holes
    |  Quality gate: non-manifold check, vertex count, A-F topology grade
    v
GAME CHECK: poly budget compliance by platform
    |  Quality gate: under budget for target platform
    v
RETOPO (if over budget): target_faces decimation
    |  Quality gate: silhouette preservation score
    v
UV UNWRAP: xatlas (primary) or smart_project (fallback)
    |  Quality gate: UV coverage > 70%, no overlaps
    v
PBR TEXTURE: create_pbr -> Principled BSDF node tree
    |  Quality gate: all PBR slots filled (albedo/normal/roughness/metallic)
    v
WEATHERING: wear, grime, moss (optional, biome-driven)
    |  Quality gate: palette validation against dark_fantasy rules
    v
LOD CHAIN: silhouette-preserving decimation per asset type
    |  LOD presets: hero(4 levels), building(4), prop(3), vegetation(4+billboard)
    v
COLLISION: convex hull generation for physics
    v
EXPORT: FBX or glTF with game_check validation
```

### Tripo AI Integration Flow

```
asset_pipeline generate_3d(prompt/image)
    |
    v
Tripo API -> GLB file with quad mesh + PBR textures
    |
    v
import_model: Load GLB into Blender
    |
    v
cleanup_ai_model (PipelineRunner):
    repair -> game_check -> retopo(if over budget)
    -> UV unwrap -> PBR material
    |
    v
Optional: rig -> animate -> batch_export
    |
    v
generate_lods -> export
```

**Hybrid generation principle:** Tripo handles organic/complex shapes (characters, monsters, hero props). Procedural handles structural/regular shapes (buildings, terrain, weapons, architecture). The hybrid uses Tripo for hero assets and procedural for environment fill.

## Patterns to Follow

### Pattern 1: Pure-Logic / bpy-Guarded Split

**What:** All mesh generation functions return `MeshSpec` dicts (vertices, faces, UVs, metadata) without importing bpy. Only `_mesh_bridge.py` converter and handler functions touch bpy/bmesh.

**When to use:** ALWAYS. Every new generator must follow this pattern.

**Trade-offs:** Slightly more code (spec dict creation + converter), but enables:
- Full pytest testing without Blender running (13,616 tests in codebase prove this works)
- Deterministic, reproducible generation
- Safe parallel generation (no GIL contention with bpy)
- Serializable specs for caching/resumption

**Example:**
```python
# procedural_meshes.py -- NO bpy imports
def generate_sword_mesh(length, blade_width, style, seed):
    vertices = [...]
    faces = [...]
    uvs = [...]
    return _make_result("sword", vertices, faces, uvs,
                        style=style, poly_count=len(faces))

# _mesh_bridge.py -- registers the generator
SWORD_GENERATOR_MAP = {
    "greatsword": (generate_sword_mesh, {"length": 1.4, "blade_width": 0.08}),
    "rapier": (generate_sword_mesh, {"length": 1.1, "blade_width": 0.03}),
}

# Handler function -- ONLY place bpy is used
def handle_generate_building(conn, params):
    spec = evaluate_building_grammar(params)
    mesh_from_spec(spec)  # <-- bpy happens here
```

### Pattern 2: Grammar-Based Building Composition

**What:** Complex structures (buildings, dungeons, settlements) are assembled from smaller pieces using grammar rules, not generated as single monolithic meshes. Grammar takes a style config + seed + constraints and produces a list of placement operations.

**When to use:** Buildings, dungeons, interiors, settlements -- anything with recognizable structural elements.

**Trade-offs:** More upfront investment (grammar rules + piece library), but enables:
- Style variation without rewriting generators (5 style configs already exist)
- Consistent quality across buildings of same style
- Modular upgrades (improve one piece, all buildings benefit)
- Real-time editing (swap pieces without regenerating everything)

**Example:**
```python
# _building_grammar.py -- grammar rules define structure
STYLE_CONFIGS = {
    "gothic": {
        "foundation": {"height": 0.5, "inset": 0.1, "material": "stone_grey"},
        "walls": {"height_per_floor": 4.5, "thickness": 0.5},
        "windows": {"style": "pointed_arch", "per_wall": 3},
        "details": ["flying_buttress", "gargoyle", "rose_window", "spire"],
    },
}

# BuildingSpec -> list of geometry operations
def evaluate_building_grammar(style, seed, constraints):
    config = STYLE_CONFIGS[style]
    ops = []
    ops += generate_foundation(config, constraints)
    ops += generate_walls(config, constraints)
    ops += generate_roof(config, constraints)
    for detail in config["details"]:
        ops += generate_detail(detail, config, seed)
    return ops
```

### Pattern 3: Trim Sheet Material Sharing

**What:** All kit pieces in an architectural style share one trim sheet material.

**When to use:** Any modular building system (already partially in `modular_building_kit.py`).

**Why:** Single material = single draw call per building. 100 buildings with shared trim sheet = 100 draw calls. 100 buildings with unique materials = 600+ draw calls.

**Example:**
```python
# One material per architectural kit style
material = bpy.data.materials["dark_fantasy_kit_01"]
for piece in kit_pieces:
    piece.data.materials.append(material)
    # UV layout aligns to correct trim strip (wall, floor, roof, etc.)
```

### Pattern 4: Quality Gate at Every Pipeline Stage

**What:** Each pipeline stage validates input, processes, validates output. If validation fails, auto-fix or return diagnostic error.

**When to use:** All processing pipelines (repair -> UV -> texture -> LOD -> export).

**Why:** Catching issues early prevents cascading failures where bad geometry propagates through the entire pipeline and wastes computation time.

**Example:**
```python
# PipelineRunner.cleanup_ai_model already implements this pattern:
result = handle_game_check(mesh_name, poly_budget=8000, platform="pc")
if result["grade"] not in ("A", "B"):
    handle_repair(mesh_name)
    result = handle_game_check(mesh_name, poly_budget=8000)
    if result["grade"] not in ("A", "B"):
        raise QualityError(f"Mesh {mesh_name} failed quality gate: {result}")
```

### Pattern 5: Seed-Based Deterministic Generation

**What:** Every generation function accepts a `seed` parameter. All randomness uses `random.Random(seed)` (not the global random).

**When to use:** Every generator, every scatter function, every layout algorithm.

**Why:** Same seed produces same output. Enables iterative refinement, multi-pass generation (terrain then scatter, same seed), and exact reproduction for debugging.

**Example:**
```python
rng = random.Random(seed)
# NOT random.random() -- that uses global state
points = poisson_disk_sample(width, depth, min_distance, seed=42)
```

### Pattern 6: Lazy Materialization with Collection Instances

**What:** Scatter systems use Blender collection instances rather than duplicating mesh data. A tree mesh is generated once, stored in a collection, and instanced at scatter points.

**When to use:** Vegetation scatter, prop scatter -- anything placing many copies of fewer unique meshes.

**Why:** At 10K+ instances, duplicated meshes exhaust memory. Collection instances share geometry data.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic Building Meshes

**What people do:** Generate entire buildings as single mesh objects.
**Why it is wrong:** No LOD flexibility, no interior streaming, no modular variation, massive memory cost. Cannot swap individual pieces.
**Do this instead:** Modular kit pieces (25-40 per style) snapped to 2m grid. Each piece is separate object, shared trim sheet material.

### Anti-Pattern 2: Unique Material Per Object

**What people do:** Create a new material for every generated object.
**Why it is wrong:** Draw calls explode. 50 props = 50 materials = 50 draw calls minimum.
**Do this instead:** Material library (20-40 master materials). Objects reference shared materials. Per-instance variation via vertex colors or MaterialPropertyBlock.

### Anti-Pattern 3: Post-Hoc Quality Application

**What people do:** Generate all content first, then try to improve quality later.
**Why it is wrong:** Quality problems compound. Bad topology makes bad UVs, bad UVs make bad textures. Fixing quality after generation requires redoing most of the pipeline.
**Do this instead:** Quality gate after every step. Generate -> validate -> next step. Never skip validation.

### Anti-Pattern 4: Flat Height-Only Terrain

**What people do:** Use only a heightmap grid for all terrain features.
**Why it is wrong:** Cannot represent cliffs, overhangs, caves, arches. All terrain is smooth slopes.
**Do this instead:** Heightmap for base terrain + separate mesh layer for vertical features. Modular cliff kit pieces snap to terrain edges. `terrain_features.py` already has canyon, cliff, geyser generators.

### Anti-Pattern 5: bpy in Pure-Logic Code

**What people do:** Import bpy in generator functions "just to create a quick mesh."
**Why it is wrong:** Breaks pytest testing (13,616 tests run without Blender). Breaks parallel generation. Couples generation to Blender's state.
**Do this instead:** Return MeshSpec dicts from generators. Convert to Blender objects only in `_mesh_bridge.py` or handler functions with guarded bpy imports.

### Anti-Pattern 6: Context-Dependent Generation State

**What people do:** Store generation state in LLM conversation context.
**Why it is wrong:** Context window fills up. Auto-compact loses state. Duplicate objects generated. Inconsistent naming.
**Do this instead:** Write state to disk files after each major operation. Read state from files, not conversation history. Use `asset_catalog.py` for tracking.

### Anti-Pattern 7: Global Random State

**What people do:** Use `random.random()` or `random.randint()` without seeding.
**Why it is wrong:** Non-reproducible generation. Cannot regenerate a specific asset. Cannot debug generation issues.
**Do this instead:** Always create `rng = random.Random(seed)` and use `rng` for all randomness in that generation.

## Build Order and Dependencies

The following build order reflects hard dependencies between systems. Each phase assumes the prior phase is complete and tested.

```
Phase 1: FOUNDATION QUALITY UPGRADE
  Files: procedural_meshes.py, procedural_materials.py, building_quality.py
  Scope: Upgrade geometry quality to AAA benchmark
  Dependencies: None (standalone generators)
  Blocks: Everything else (quality foundation)
  Risk: LOW -- generators are independent, testable

Phase 2: MODULAR KIT EXPANSION
  Files: modular_building_kit.py
  Scope: Expand from 175 to 300+ pieces, 5 style variants, ruined/corrupted
  Dependencies: Phase 1 (quality baseline)
  Blocks: Building grammar upgrade, interior system
  Risk: MEDIUM -- piece count is large but each piece is independent

Phase 3: BUILDING GRAMMAR UPGRADE
  Files: _building_grammar.py, settlement_generator.py
  Scope: AAA grammar rules, storyline-aware generation, intelligent openings
  Dependencies: Phase 2 (piece library)
  Blocks: Settlement system, interior system
  Risk: MEDIUM -- grammar complexity scales with quality requirements

Phase 4: TERRAIN + BIOME SYSTEM
  Files: _terrain_noise.py, terrain_features.py, terrain_materials.py, _terrain_depth.py
  Scope: Biome-aware terrain, transition zones, terrain/building height integration
  Dependencies: Phase 1 (material quality)
  Blocks: Map composition, scatter system
  Risk: LOW -- terrain system is already well-structured

Phase 5: INTERIOR SYSTEM
  Files: _building_grammar.py (interior), worldbuilding.py
  Scope: Room layout, furniture with scale validation, door/occlusion/lighting
  Dependencies: Phase 3 (building grammar)
  Blocks: Full pipeline integration
  Risk: MEDIUM -- interior-room mapping is complex

Phase 6: SCATTER + POPULATION
  Files: _scatter_engine.py, environment_scatter.py, vegetation_system.py
  Scope: Biome-aware scatter, context props, vegetation density control
  Dependencies: Phase 4 (biome map), Phase 3 (buildings)
  Blocks: Map composition
  Risk: LOW -- scatter engine already works, needs biome awareness

Phase 7: MAP COMPOSITION + INTEGRATION
  Files: map_composer.py, world_map.py, worldbuilding_layout.py
  Scope: Full world generation, road networks, terrain/building seamless integration
  Dependencies: All prior phases
  Blocks: Starter town
  Risk: HIGH -- most complex integration point, many moving parts

Phase 8: STARTER TOWN
  Scope: Generate functional, gameplay-ready location as proof-of-concept
  Dependencies: Phase 7 (full pipeline working)
  Blocks: Nothing (final deliverable)
  Risk: LOW -- if Phase 7 works, this is just exercising it
```

## Scalability Considerations

| Concern | At 1 Room | At 50 Rooms (Dungeon) | At 500+ Rooms (Full Game) |
|---------|-----------|----------------------|--------------------------|
| Draw calls | 10-30 (manageable) | 500-1500 (needs batching) | Addressables streaming, load only adjacent rooms |
| Triangle count | 50K-150K per room | 2.5M-7.5M (all rooms) | Occlusion culling, only render visible rooms |
| Texture memory | 50-100MB (room textures) | 2.5-5GB (all rooms) | Texture streaming via Addressables, LOD-appropriate resolution |
| Vegetation instances | 100-500 plants | 5K-25K plants | GPU instancing + LOD, cull beyond 100m |
| AI generation time | 10-30 min (all props) | 8-25 hours (all props) | Self-hosted Hunyuan3D for bulk, Tripo for hero pieces |
| Generation memory | Fits in Blender easily | Needs terrain chunking | `terrain_chunking.py` (13KB) exists for this |
| Context window | Fits easily | Requires state persistence | Must use file-based state, batch operations |

### Scaling Priorities

1. **First bottleneck:** Terrain mesh density. 1km x 1km at 1m resolution = 1M vertices. Solution: multi-resolution grid using `_terrain_depth.py` importance mapping (dense near paths, sparse in wilderness). `terrain_chunking.py` already provides tile infrastructure.

2. **Second bottleneck:** Material draw calls. 100 buildings x 5 materials = 500 draw calls. Solution: texture atlases per biome (terrain_materials.py supports splatmaps), shared material instances via `_assign_procedural_material` pooling, trim sheets for buildings.

3. **Third bottleneck:** Prop count in settlements. 200 props/building x 16 buildings = 3,200 props. Solution: collection instancing (already implemented in environment_scatter.py), prop LOD, occlusion culling.

### Generation-Time Optimization

| Strategy | File | Impact |
|----------|------|--------|
| Trig lookup table (`_get_trig_table`) | `procedural_meshes.py` | Eliminates redundant cos/sin across 127+ generators |
| Collection instancing | `environment_scatter.py` | 100x memory reduction for vegetation |
| Seed-based generation | All generators | Enables parallel generation without state conflicts |
| Geometry Nodes delegation | Complex terrain operations | Leverages Blender's optimized node evaluation |
| Batch processing | `pipeline_runner.py` | Processes objects in groups, releases memory between batches |

## Integration Points

### Tripo Pipeline Integration

| Trigger | Flow | Output |
|---------|------|--------|
| `asset_pipeline generate_3d` | API call -> download GLB -> import_model -> cleanup_ai_model | Clean Blender mesh with PBR material |
| `asset_pipeline generate_building` | Tripo + procedural hybrid | Building shell from Tripo, structural detail from grammar |
| Character generation | Tripo for body -> rig -> animate | Rigged character with animations |

### Unity Integration

All generated assets flow to Unity through the export pipeline:

```
Blender mesh -> blender_export (FBX/glTF)
    -> Unity Assets/Art/ directory
    -> unity_editor recompile
    -> Scene setup via unity_world / unity_scene tools
    -> NavMesh, lighting, streaming setup via next_steps
```

### Internal Boundaries

| Boundary | Communication | Data Format |
|----------|---------------|-------------|
| Generator -> Mesh Bridge | Function call, dict return | MeshSpec: `{vertices, faces, uvs, metadata}` |
| Mesh Bridge -> Blender | `mesh_from_spec()` via bpy/bmesh | Creates mesh data-block + object |
| Pipeline Stage -> Stage | PipelineRunner async calls | Modified MeshSpec or Blender object names |
| Grammar Rules -> Geometry Ops | BuildingSpec -> list of op dicts | `{type, position, size, material_key}` |
| Scatter Engine -> Environment | Point tuples + type strings | `(x, y, z, rot, scale, type_key)` |
| World Composer -> Sub-systems | Spec dicts with seed | `map_spec` dict chains all subsystems |

## Key Architectural Decisions

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Pure-logic / bpy-guarded split | Enables 13K+ tests, parallel generation, debugging | All generators must return MeshSpec dicts |
| Grammar-based composition (not monolithic) | Industry standard (Bethesda/FromSoftware). Enables LOD, streaming, variation | 25-40 pieces per kit required upfront |
| Trim sheet over unique textures | Single material per building style. Dramatic draw call reduction | All kit pieces must UV-map to shared trim sheet |
| Multi-backend AI generation | 51% cost savings, quality-tier matching | Requires backend abstraction in generate_3d |
| Height-blend over linear blend | AAA standard for natural terrain transitions | Requires per-material heightmaps in terrain shader |
| Collection instancing for scatter | 100x memory reduction at scale | Scatter must generate templates, then instance |
| Seed-based determinism | Reproducible generation for iterative refinement | All noise/random calls use seed-derived values |
| File-based state over context-based | Prevents context window bloat during long sessions | All generators must read/write state files |
| Quality gates between pipeline stages | Prevents cascading failures | Each stage validates input and output |

## Sources

- Codebase analysis: 100+ handler files in `blender_addon/handlers/`, `shared/` modules
- Existing architecture: `_mesh_bridge.py` dispatch pattern, `PipelineRunner` orchestration
- AAA game architecture patterns: Skyrim Creation Kit modular kit system, Witcher 3 WCC, Valhalla procedural scatter
- Existing research: `.planning/research/AAA_BEST_PRACTICES_COMPREHENSIVE.md`, `.planning/research/MAP_BUILDING_TECHNIQUES.md`, `.planning/research/TEXTURING_ENVIRONMENTS_RESEARCH.md`
- Memory files: `project_v5_gap_analysis.md` (192 gaps), `project_visual_quality_crisis.md` (AAA quality mandate)
- Established patterns: pure-logic/bpy-guarded split (v3.0 decision), seed-based determinism, compound tool architecture

---
*Architecture research for: AAA Procedural 3D Pipeline (VeilBreakers v4.0 milestone)*
*Researched: 2026-03-30*
