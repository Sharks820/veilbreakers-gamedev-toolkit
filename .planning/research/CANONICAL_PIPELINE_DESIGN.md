# Canonical World Generation Pipeline Design

**Researched:** 2026-04-03
**Domain:** Blender MCP world generation pipeline architecture
**Confidence:** HIGH

## Summary

The VeilBreakers MCP toolkit currently has **three competing world generation code paths** that cause confusion about which subsystems get called, what order they run in, and which produces correct output:

1. **`blender_server.py` compose_map** (lines 2732-3224) -- the MCP server orchestrator. This is the most complete path: 10 steps, checkpoint/resume, budget control, foundation profiling, quality enforcement. It sends commands over TCP to Blender handlers. This is the **correct canonical entry point**.

2. **`map_composer.py` compose_world_map** -- pure-logic planner (no bpy). Generates POI placements, road networks, world features, and biome maps. Returns data structures only. Currently **not called** by compose_map at all -- it is only reachable via `handle_compose_world_map` in worldbuilding.py which is registered as `world_compose_world_map` in the handler dispatch table. This is a **planning module** that should feed INTO the canonical pipeline but currently runs as a separate entry point.

3. **`worldbuilding.py` handle_compose_world_map** (line 6734) -- Blender-side handler that calls `compose_world_map()`, then materializes roads as curves and POIs as mesh objects directly in Blender. This is a **parallel implementation** that duplicates what compose_map does server-side but with simpler geometry (cubes for some vegetation, basic curve roads).

**Primary recommendation:** Consolidate to a single canonical pipeline in `blender_server.py` compose_map, use `map_composer.py` as the planning/layout phase, deprecate `handle_compose_world_map`, and add missing steps (terrain features, atmospheric volumes, veil corruption, lighting props).

## Current Architecture Analysis

### What Each Code Path Does

| Step | compose_map (server) | compose_world_map (planner) | handle_compose_world_map (handler) |
|------|---------------------|---------------------------|-----------------------------------|
| Scene clear | YES (step 1) | N/A (no bpy) | NO |
| POI placement planning | Basic ring-based anchoring | Full biome/slope/distance rules | Delegates to compose_world_map |
| Terrain generation | YES (step 2, via env_generate_terrain) | NO | NO |
| Water (rivers/lakes) | YES (step 3) | NO | NO |
| Road network | YES (step 4, from map_spec waypoints) | YES (MST + shortcuts, A* pathing) | YES (materializes as curves) |
| Settlement generation | YES (step 5, via world_generate_town etc.) | NO (POI placement only) | YES (calls _generate_location_poi) |
| Biome painting | YES (step 6) | NO | NO |
| Lighting | YES (step 6b, dark_fantasy_lighting) | NO | NO |
| Vegetation | YES (step 7, via env_scatter_vegetation) | NO | NO |
| Props | YES (step 8, via env_scatter_props) | NO | NO |
| Interiors | YES (step 9, via world_generate_linked_interior) | NO | NO |
| Heightmap export | YES (step 10) | NO | NO |
| World features | NO | YES (bridges, milestones, watchtowers, etc.) | YES (materializes features) |
| Terrain features | NO | NO | NO |
| Atmospheric volumes | NO | NO | NO |
| Veil corruption | NO | NO | Partial (assigns corruption_overlay material) |
| Quality enforcement | YES (_enforce_world_quality) | NO | NO |
| Checkpoint/resume | YES (pipeline_state.py) | NO | NO |

### Key Insight: compose_map Does NOT Use the Smart Planner

The biggest gap is that `compose_map` uses a simple ring-based anchor placement algorithm (`_plan_map_location_anchors`) instead of `compose_world_map`'s biome-aware, slope-aware, distance-respecting placement system. The planner in `map_composer.py` is strictly superior:

- Considers biome affinity (towns in forests, dungeons in mountains)
- Respects slope constraints per POI type
- Enforces minimum distances between settlements
- Generates Veil pressure bands
- Produces an MST-based road network with terrain-following waypoints
- Generates world features (bridges, watchtowers, farm belts, market quarters)

## Pipeline Architecture Decision: Linear with Optional Parallelism

### Why Linear (Not DAG)

For this specific use case, a **linear pipeline with checkpoint gates** is the correct choice, not a full DAG. Rationale:

1. **Sequential dependencies are real**: You cannot scatter vegetation before terrain exists. You cannot place buildings before terrain is flattened. You cannot paint biomes before terrain geometry is generated. The natural dependency chain is almost perfectly linear.

2. **Blender is single-threaded for mesh ops**: Even if we could express parallelism (e.g., vegetation and props could theoretically run in parallel), Blender's Python API is single-threaded. No benefit from DAG parallelism.

3. **Checkpoint/resume already works**: The existing `pipeline_state.py` checkpoint system is designed for linear step progression and works well.

4. **Complexity cost is not justified**: DAG orchestrators (Airflow, Prefect) add significant complexity. For a 15-step pipeline running in one process, linear steps with skip/resume are sufficient.

**However**, the pipeline should support **optional step skipping** and **step groups** to handle cases where users want to regenerate only vegetation, or skip water entirely.

### Step Communication: Shared State Dict

The pipeline should pass a single **mutable state dictionary** through all steps. This is the pattern `compose_map` already uses (with `steps_completed`, `created_objects`, `location_results`, etc.). 

Recommended state dict structure:

```python
PipelineState = {
    # Identity
    "map_name": str,
    "seed": int,
    "map_spec": dict,  # original spec, immutable reference
    
    # Terrain context (set by step 2, consumed by all later steps)
    "terrain_name": str,
    "terrain_size": float,
    "terrain_resolution": int,
    "terrain_height_scale": float,
    
    # Layout context (set by planning step, consumed by settlement/road steps)
    "planned_pois": list[dict],  # from compose_world_map
    "planned_roads": list[dict],  # from compose_world_map  
    "world_features": list[dict],  # from compose_world_map
    
    # Accumulation
    "steps_completed": list[str],
    "steps_failed": list[dict],
    "created_objects": list[str],
    "location_results": list[dict],
    "interior_results": list[dict],
    
    # Budget
    "budget": dict,
    
    # Checkpoint
    "checkpoint_dir": str | None,
}
```

### Error Handling Strategy

Each step should follow this protocol:

1. **Try-except around the entire step body**
2. **On failure**: Record in `steps_failed` with step name + error message + traceback
3. **Non-fatal by default**: Pipeline continues to next step (most steps are independent enough)
4. **Fatal steps**: Only `terrain_generated` is truly fatal -- nothing else can proceed without terrain. Mark these explicitly.
5. **No retry loops**: Failed steps are skipped on checkpoint resume (existing behavior in `get_remaining_steps`). User can force-restart to retry everything.
6. **Idempotent steps**: Each step should check if its output already exists before creating it (prevents duplication on partial reruns).

## Canonical Pipeline Design: 16 Steps

### Step Registry

```python
PIPELINE_STEPS = [
    # Phase 1: Foundation
    {"name": "scene_clear",          "handler": "clear_scene",              "fatal": False, "group": "foundation"},
    {"name": "terrain_generate",     "handler": "env_generate_terrain",     "fatal": True,  "group": "foundation"},
    {"name": "terrain_features",     "handler": "terrain_generate_feature", "fatal": False, "group": "foundation"},
    
    # Phase 2: Hydrology
    {"name": "water_rivers",         "handler": "env_carve_river",          "fatal": False, "group": "hydrology"},
    {"name": "water_bodies",         "handler": "env_create_water",         "fatal": False, "group": "hydrology"},
    
    # Phase 3: Infrastructure  
    {"name": "road_network",         "handler": "env_generate_road",        "fatal": False, "group": "infrastructure"},
    
    # Phase 4: Settlements
    {"name": "settlement_place",     "handler": "_location_handlers",       "fatal": False, "group": "settlements"},
    {"name": "building_materialize", "handler": "modular_building_kit",     "fatal": False, "group": "settlements"},
    {"name": "interior_generate",    "handler": "world_generate_linked_interior", "fatal": False, "group": "settlements"},
    
    # Phase 5: Surface
    {"name": "biome_paint",          "handler": "terrain_create_biome_material",  "fatal": False, "group": "surface"},
    {"name": "vegetation_scatter",   "handler": "env_scatter_vegetation",   "fatal": False, "group": "surface"},
    {"name": "prop_scatter",         "handler": "env_scatter_props",        "fatal": False, "group": "surface"},
    
    # Phase 6: Atmosphere
    {"name": "lighting_setup",       "handler": "setup_dark_fantasy_lighting", "fatal": False, "group": "atmosphere"},
    {"name": "atmosphere_volumes",   "handler": "atmospheric_volumes",      "fatal": False, "group": "atmosphere"},
    {"name": "veil_corruption",      "handler": "corruption_overlay",       "fatal": False, "group": "atmosphere"},
    
    # Phase 7: Export
    {"name": "export_heightmap",     "handler": "env_export_heightmap",     "fatal": False, "group": "export"},
]
```

### Detailed Step Specifications

#### Step 1: scene_clear
- **Handler**: `clear_scene`
- **Input**: None
- **Output**: Empty scene
- **Validation**: Scene object count == 0
- **Skip condition**: `resume=True` and checkpoint has steps beyond this

#### Step 2: terrain_generate (FATAL)
- **Handler**: `env_generate_terrain`
- **Input**: terrain preset, resolution, height_scale, seed, size, erosion config
- **Output**: Terrain mesh object named `{map_name}_Terrain`
- **Validation**: Object exists, vertex count matches expected resolution^2
- **Fatal**: YES -- all subsequent steps depend on terrain existing

#### Step 3: terrain_features (NEW)
- **Handler**: Multiple calls to terrain feature generators
- **Input**: `world_features` from planning step (canyons, waterfalls, cliffs, etc.)
- **Output**: Feature meshes parented to terrain
- **Validation**: Each feature object exists
- **Source**: `terrain_features.py` generators (currently dead code -- not called by any pipeline)
- **Note**: The `compose_world_map` planner already generates feature specs (bridge_crossing, watchtower, milestone, etc.). These need to be materialized here.

#### Step 4: water_rivers
- **Handler**: `env_carve_river` (one call per river)
- **Input**: River source/destination from map_spec or planned_roads (rivers follow valleys)
- **Output**: Carved river channels in terrain
- **Validation**: Terrain mesh modified (vertex heights changed along river path)

#### Step 5: water_bodies
- **Handler**: `env_create_water`
- **Input**: water_level, terrain_name
- **Output**: Water plane object named `{map_name}_Water`
- **Validation**: Water object exists at correct Z height

#### Step 6: road_network
- **Handler**: `env_generate_road` (one call per road segment)
- **Input**: Road waypoints from `compose_world_map` planner output (MST-based)
- **Output**: Road deformations on terrain + road objects
- **Validation**: Roads connect planned settlements
- **Key change**: Use planner-generated roads instead of raw map_spec waypoints. The planner produces terrain-following A*-based waypoints with proper road types (main/shortcut/path).

#### Step 7: settlement_place
- **Handler**: Multiple handlers based on location type (world_generate_town, world_generate_castle, etc.)
- **Input**: Planned POI positions from compose_world_map, with terrain height sampling for Z
- **Output**: Settlement objects positioned on terrain
- **Substeps**:
  1. Flatten terrain zone under each settlement
  2. Compute foundation profile from corner heights
  3. Generate settlement via appropriate handler
  4. Position at anchor point with correct Z
- **Validation**: Each settlement object exists at planned position

#### Step 8: building_materialize
- **Handler**: `modular_building_kit` functions
- **Input**: Settlement results from step 7
- **Output**: Detailed building geometry replacing placeholder volumes
- **Note**: This step enhances buildings generated in step 7. The `modular_building_kit.py` provides detailed medieval architectural elements.

#### Step 9: interior_generate
- **Handler**: `world_generate_linked_interior` / `building_interior_binding.py`
- **Input**: Interior specs from map_spec locations with `interiors` key
- **Output**: Interior room shells, door triggers, furniture, occlusion markers
- **Validation**: Interior objects created for each specified room

#### Step 10: biome_paint
- **Handler**: `env_paint_terrain` + `terrain_create_biome_material`
- **Input**: Biome name, terrain object, height_scale
- **Output**: Material slots assigned to terrain with biome-appropriate textures
- **Validation**: Terrain has non-default material assigned
- **Note**: Uses 14 biome palettes with HeightBlend splatmap from `terrain_materials.py`

#### Step 11: vegetation_scatter
- **Handler**: `env_scatter_vegetation`
- **Input**: Vegetation rules (from `_normalize_vegetation_rules`), terrain_name, budget limits
- **Output**: Vegetation instances (real meshes from `VEGETATION_GENERATOR_MAP`, not cubes)
- **Validation**: Instance count > 0, no instances intersecting buildings

#### Step 12: prop_scatter
- **Handler**: `env_scatter_props`
- **Input**: Building locations (from settlement results), prop_density, budget
- **Output**: Context-aware props around buildings (from `PROP_AFFINITY` mapping)
- **Validation**: Props placed near buildings, density within budget

#### Step 13: lighting_setup
- **Handler**: `setup_dark_fantasy_lighting`
- **Input**: Biome-appropriate lighting preset (from `_lighting_preset_for_biome`)
- **Output**: Sun/environment lights configured
- **Validation**: At least one light exists in scene
- **Also**: Place light props from `LIGHT_PROP_MAP` near buildings (torches, lanterns, braziers)

#### Step 14: atmosphere_volumes (NEW)
- **Handler**: `compute_atmospheric_placements` from `atmospheric_volumes.py`
- **Input**: Biome type, terrain bounds, density rules
- **Output**: Fog/dust/firefly/god_ray volume objects
- **Validation**: Volume objects created matching biome rules
- **Note**: `atmospheric_volumes.py` is pure-logic and fully implemented but never called by compose_map. The volume specs need to be materialized as Blender volume objects.

#### Step 15: veil_corruption (NEW)
- **Handler**: Custom step using `corruption_overlay` material from `procedural_materials.py`
- **Input**: Veil pressure bands from compose_world_map planner, corruption intensity
- **Output**: Corruption visual overlay on terrain/objects in high-pressure zones
- **Validation**: Objects in veil_belt pressure band have corruption material applied
- **Note**: `worldbuilding.py` already has `_assign_procedural_material(obj, "corruption_overlay")` logic. This needs to be generalized for terrain zones.

#### Step 16: export_heightmap
- **Handler**: `env_export_heightmap`
- **Input**: Terrain name, export path, Unity compatibility flags
- **Output**: 16-bit RAW heightmap file
- **Validation**: File exists and size matches resolution^2 * 2 bytes

### Integration of compose_world_map as Planning Phase

The critical architectural change is inserting `compose_world_map` as a **pre-step planning phase** that runs BEFORE the main pipeline:

```
User map_spec
    |
    v
compose_world_map()  <-- Pure-logic planning (no bpy)
    |                    - Biome-aware POI placement
    |                    - MST road network
    |                    - World feature generation
    |                    - Veil pressure mapping
    v
PipelineState (enriched with planned_pois, planned_roads, world_features)
    |
    v
16-step pipeline (Blender execution)
```

This means the `map_spec.locations` list gets **replaced** by the planner's output. The planner considers:
- Biome affinity for each POI type
- Slope constraints
- Minimum distances between POIs
- Elevation ranges
- Veil pressure bands
- Road connectivity (MST + shortcuts)
- World feature placement (bridges at road crossings, watchtowers at high points, milestones along roads)

The user can still override positions by providing explicit `"position"` in location specs -- the planner respects these as fixed anchors.

## What to Deprecate

### `handle_compose_world_map` (worldbuilding.py:6734)

This handler runs `compose_world_map()` and then materializes results directly in Blender with basic geometry. It should be marked `@deprecated` and its handler registration (`world_compose_world_map`) should emit a deprecation warning pointing users to `asset_pipeline action=compose_map`.

**Reason**: It duplicates compose_map's functionality but with worse results (no terrain generation, no biome painting, no vegetation, no checkpoint, no quality enforcement, basic geometry for POIs).

### Direct handler calls for world generation without pipeline context

Individual calls to `world_generate_town`, `env_generate_terrain`, etc. remain valid for single-asset generation. The deprecation only applies to the **orchestration** layer -- there should be ONE orchestrator (compose_map), not three.

## Extensibility Design

### Adding New Steps

New steps should be addable by:
1. Adding an entry to `PIPELINE_STEPS` list at the correct position
2. Implementing the step logic as a function with signature: `async def step_X(blender, state) -> None`
3. The step function reads from `state` and writes results back to `state`
4. Checkpoint happens automatically after each step

### Step Groups for Selective Regeneration

The `group` field in step definitions enables commands like:
- `compose_map resume_from="surface"` -- re-run biome painting, vegetation, and props without regenerating terrain or settlements
- `compose_map skip_groups=["atmosphere"]` -- skip lighting/fog/corruption

### Plugin Steps

Future: Allow the user to register custom steps via map_spec:
```json
{
    "custom_steps": [
        {"after": "vegetation_scatter", "handler": "custom_mushroom_ring_scatter", "params": {...}}
    ]
}
```

## Common Pitfalls

### Pitfall 1: Terrain Height Sampling Timing
**What goes wrong:** Steps that need terrain Z heights (settlement placement, prop scatter) fail or produce floating objects if they run before terrain erosion modifies the heightmap.
**Prevention:** Terrain height sampling must happen AFTER erosion, not before. The pipeline order (terrain generate with erosion -> water carve -> flatten zones -> sample heights) is critical.

### Pitfall 2: Checkpoint Step Name Drift
**What goes wrong:** If step names change between versions, old checkpoints become incompatible and the pipeline either skips steps or re-runs completed steps.
**Prevention:** Step names must be treated as stable API. Use a version field in checkpoints and add migration logic for name changes.

### Pitfall 3: Object Name Collisions
**What goes wrong:** Multiple pipeline runs create objects with the same names, causing Blender to auto-rename with `.001` suffixes, breaking later references.
**Prevention:** Scene clear (step 1) must be mandatory for fresh runs. On checkpoint resume, validate that expected objects still exist.

### Pitfall 4: Budget Enforcement Gaps
**What goes wrong:** Individual steps respect their own limits but the total scene exceeds poly/instance budgets.
**Prevention:** The `_resolve_map_generation_budget` function already exists. Each step should decrement from a shared budget counter in state, not just use independent limits.

### Pitfall 5: Planner-Pipeline Data Format Mismatch
**What goes wrong:** compose_world_map returns POIs with `"position": (x, y)` in world units, but compose_map's terrain commands expect grid cells or terrain-local coordinates.
**Prevention:** The `_map_point_to_terrain_cell` function handles this conversion. Ensure all planner output coordinates are in world units and converted at the point of use.

## Architecture Patterns

### Recommended File Organization

```
blender_addon/handlers/
    pipeline_state.py          # Checkpoint persistence (exists, keep as-is)
    pipeline_steps.py          # NEW: Step registry + step implementations
    map_composer.py            # Planning phase (exists, keep as-is, pure-logic)
    
src/veilbreakers_mcp/
    blender_server.py          # compose_map action calls pipeline_steps
```

### Pattern: Step Function Contract

```python
async def step_terrain_generate(blender: BlenderConnection, state: dict) -> None:
    """Generate terrain mesh.
    
    Reads from state: map_spec.terrain, seed
    Writes to state: terrain_name, terrain_size, terrain_resolution
    Handler: env_generate_terrain
    """
    terrain_cfg = state["map_spec"].get("terrain", {})
    terrain_name = f"{state['map_name']}_Terrain"
    
    result = await blender.send_command("env_generate_terrain", {
        "name": terrain_name,
        "terrain_type": terrain_cfg.get("preset", "hills"),
        "resolution": state["terrain_resolution"],
        "height_scale": terrain_cfg.get("height_scale", 20.0),
        "scale": state["terrain_size"],
        "seed": state["seed"],
        "erosion": "hydraulic" if terrain_cfg.get("erosion", True) else "none",
        "erosion_iterations": terrain_cfg.get("erosion_iterations", 5000),
    })
    
    state["terrain_name"] = terrain_name
    state["created_objects"].append(terrain_name)
```

### Pattern: Pipeline Runner

```python
async def run_pipeline(blender, state, steps=PIPELINE_STEPS):
    for step_def in steps:
        step_name = step_def["name"]
        if step_name in state["steps_completed"]:
            continue  # checkpoint resume
        if step_name in {e["step"] for e in state.get("steps_failed", []) if isinstance(e, dict)}:
            continue  # previously failed, skip
            
        try:
            step_fn = STEP_FUNCTIONS[step_name]
            await step_fn(blender, state)
            state["steps_completed"].append(step_name)
            _save_checkpoint(state)
        except Exception as e:
            state["steps_failed"].append({"step": step_name, "error": str(e)})
            if step_def.get("fatal"):
                raise PipelineFatalError(f"Fatal step '{step_name}' failed: {e}")
            _save_checkpoint(state)
```

### Anti-Patterns to Avoid

- **Multiple entry points for the same operation**: The current situation with three compose functions. ONE entry point, period.
- **Inline pipeline logic in blender_server.py**: The 500-line compose_map block should be refactored into step functions in a separate module.
- **Handler-side orchestration**: `handle_compose_world_map` should NOT orchestrate -- handlers are leaf operations, not orchestrators. Orchestration belongs in the MCP server layer.
- **Mixing planning and execution**: Keep `map_composer.py` pure (no bpy) and all Blender calls in the execution steps.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| POI placement | Simple ring-based anchoring | `compose_world_map()` from map_composer.py | Has biome affinity, slope, distance, pressure band rules |
| Road network | User-specified waypoints only | MST + shortcut algorithm in map_composer.py | Automatically connects all settlements with optimal paths |
| Checkpoint persistence | Custom file I/O | `pipeline_state.py` save/load/validate | Already handles atomic writes, version checking, compatibility validation |
| Terrain height sampling | Hardcoded Z values | `_sample_terrain_height()` in blender_server.py | Raycasts against actual terrain mesh |
| Vegetation meshes | Cube primitives | `VEGETATION_GENERATOR_MAP` in _mesh_bridge.py | Real procedural trees, bushes, grass |
| Context-aware props | Random scatter | `PROP_AFFINITY` in _scatter_engine.py | Building-type-aware weighted selection |
| Biome materials | Single material assignment | `terrain_create_biome_material` handler | 14 palettes, HeightBlend, splatmap |

## Open Questions

1. **Planning phase performance**: `compose_world_map` uses exhaustive position search (1000 attempts per POI). For maps with many POIs this could be slow. Consider spatial hashing or grid-based placement.

2. **Building materialization step**: Step 8 (building_materialize via modular_building_kit) is conceptually distinct from step 7 (settlement placement), but currently settlements already produce geometry. Need to determine if this is a separate enhancement pass or if it's already handled within settlement generation.

3. **Terrain features handler**: `terrain_features.py` has generators for canyons, waterfalls, cliffs, etc., but there is no registered handler in `__init__.py` that calls them. A new handler or direct integration is needed.

4. **Atmospheric volume materialization**: `atmospheric_volumes.py` computes placements but is pure-logic. A Blender handler is needed to create actual volume objects from the computed specs.

5. **Veil corruption spatial extent**: The corruption overlay material exists but there is no spatial mapping from Veil pressure bands (computed by the planner) to terrain regions. Need to define how corruption is applied -- vertex colors? Separate overlay mesh? Material blend zones?

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of blender_server.py compose_map (lines 2732-3224)
- Direct codebase analysis of map_composer.py compose_world_map (lines 1002-1160)
- Direct codebase analysis of worldbuilding.py handle_compose_world_map (lines 6734-6920+)
- Direct codebase analysis of pipeline_state.py (full file, checkpoint system)
- Direct codebase analysis of handler dispatch table in __init__.py

### Secondary (MEDIUM confidence)
- [JAHAN Framework for Procedural Map Generation](https://www.sciencedirect.com/science/article/abs/pii/S1875952124000120) -- Pipeline architecture for PCG
- [Data Pipeline Design Patterns](https://www.techment.com/blogs/data-pipeline-design-patterns/) -- DAG vs linear pipeline tradeoffs
- [Pipeline Orchestration Guide](https://www.mage.ai/blog/data-pipeline-orchestration-the-ultimate-guide-for-data-engineers) -- Checkpoint/resume patterns
- [DAG Architecture](https://www.databricks.com/glossary/dag) -- When DAGs are vs aren't warranted
- [Reliable Data Pipeline Design](https://datalakehousehub.com/blog/2026-02-de-best-practices-02-design-data-pipelines/) -- Checkpointing and idempotency patterns
- [Hytale World Generation](https://hytale.com/news/2026/1/the-future-of-world-generation) -- Modern game world generation approaches

## Metadata

**Confidence breakdown:**
- Current architecture analysis: HIGH -- direct codebase reading
- Pipeline design recommendation: HIGH -- based on actual code patterns and constraints
- Step specifications: HIGH -- each step maps to existing handlers
- Missing steps (terrain features, atmosphere, veil): MEDIUM -- handlers exist but integration path needs implementation
- Extensibility design: MEDIUM -- pattern is sound but untested

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable architecture, unlikely to change rapidly)
