# Phase 18: Procedural Mesh Integration + Terrain Depth - Research

**Researched:** 2026-03-21
**Domain:** Blender procedural mesh integration, terrain geometry generation, LOD pipeline
**Confidence:** HIGH

## Summary

Phase 18 bridges the gap between a 127-generator procedural mesh library (`procedural_meshes.py`, 10,861 lines, 21 categories) and the worldbuilding/environment handlers that currently create primitive cubes, cones, and icospheres as placeholders. The core technical challenge is a `_mesh_from_spec()` bridge function that converts the MeshSpec dict format (vertices/faces/uvs/metadata) into actual Blender mesh objects via bmesh. Once this bridge exists, every handler that currently calls `bmesh.ops.create_cube()` can instead call the appropriate procedural mesh generator and convert the result.

The terrain depth features (cliffs, caves, waterfalls, bridges, multi-biome blending) are separate from the mesh integration work -- they require NEW generator functions in procedural_meshes.py and new handler logic in environment.py. These are geometry systems that go beyond heightmap limitations by generating standalone mesh objects that attach to terrain edges. The LOD requirement (MESH3-05) leverages the existing `pipeline_lod.py` Decimate modifier workflow, which already produces LOD0-LOD3 chains from any source mesh.

The codebase follows a clean pure-logic / Blender-handler separation: all pure-logic modules (`procedural_meshes.py`, `_building_grammar.py`, `_scatter_engine.py`, `_dungeon_gen.py`, `_terrain_noise.py`) have zero bpy imports and are fully testable via pytest with mock bpy modules. Handler files (`worldbuilding.py`, `environment.py`, `environment_scatter.py`) import bpy/bmesh and create actual Blender objects. New code must maintain this separation.

**Primary recommendation:** Build the `_mesh_from_spec()` bridge function first, then systematically replace primitive creation in each handler (interior, scatter, dungeon, castle), then add terrain depth generators, then wire LOD generation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Replace primitives at the handler level**: Modify `_building_grammar.py` interior generation to call `procedural_meshes.generate_table_mesh()` etc. instead of creating scaled cubes
- **Replace scatter primitives**: Modify `_scatter_engine.py` to use `procedural_meshes.generate_rock_mesh()`, `generate_tree_mesh()` instead of icospheres/cones
- **Replace dungeon props**: Modify `_dungeon_gen.py` to place actual trap meshes, altar meshes, torch sconces from procedural library
- **Replace castle elements**: Modify worldbuilding handlers to use gate, rampart, drawbridge, fountain meshes
- **Blender mesh conversion**: Create a `_mesh_from_spec(spec_dict)` helper that converts procedural_meshes output (vertices/faces) into actual Blender mesh objects via bmesh
- **Cliff face geometry**: Generate vertical rock wall meshes using noise-displaced cylinder segments -- not heightmap-based
- **Cave entrance transitions**: Generate archway/tunnel entrance meshes that blend seamlessly with terrain at the opening
- **Multi-biome blending**: Generate transition zone meshes using procedural variation
- **Waterfall geometry**: Generate stepped water surface meshes with cascade drop-offs
- **Bridge generation**: Detect river/chasm gaps in terrain and generate spanning bridge meshes (stone arch, rope, drawbridge)
- **3 LOD levels**: LOD0 (full detail), LOD1 (50% faces), LOD2 (25% faces)
- **Automatic via Blender decimate modifier**: Apply decimate modifier at ratios for each LOD level
- **Export all LODs**: Each mesh exports with LOD0/LOD1/LOD2 variants in the same FBX

### Claude's Discretion
- Exact vertex counts for each LOD level
- Noise parameters for cliff face displacement
- Cave entrance arch profile curve
- Biome transition zone width
- Waterfall step heights and widths
- Bridge structural detail level

### Deferred Ideas (OUT OF SCOPE)
None -- autonomous mode stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MESH3-01 | Worldbuilding handlers use procedural mesh library (real furniture, props, vegetation -- not primitive cubes/cones) | Bridge function `_mesh_from_spec()` + furniture type mapping table + handler modifications in worldbuilding.py |
| MESH3-02 | Environment scatter uses procedural rocks, trees, mushrooms, roots instead of geometric primitives | Replace `_create_vegetation_template()` in environment_scatter.py to use procedural_meshes generators |
| MESH3-03 | Dungeon generation places actual trap meshes, altar meshes, prison doors, torch sconces from procedural library | Dungeon prop placement after room generation + furniture-type-to-generator mapping |
| MESH3-04 | Castle generation uses actual gate, rampart, drawbridge, fountain meshes | Replace castle handler spec-to-geometry with procedural mesh calls for structural elements |
| MESH3-05 | All procedural meshes have LOD variants (high/medium/low poly) for performance budgets | Existing `pipeline_lod.py` Decimate workflow + integration into `_mesh_from_spec()` |
| TERR-01 | Claude can generate vertical cliff face geometry (not limited to 2.5D heightmap) | New `generate_cliff_face_mesh()` in procedural_meshes.py + handler in environment.py |
| TERR-02 | Claude can generate cave entrance transition meshes (seamless terrain-to-cave geometry) | New `generate_cave_entrance_mesh()` in procedural_meshes.py + terrain-edge placement logic |
| TERR-03 | Claude can generate multi-biome terrain with smooth transitions | New biome transition zone generator + vertex color blending at boundaries |
| TERR-04 | Claude can generate waterfall/cascade geometry with stepped water mesh | New `generate_waterfall_mesh()` in procedural_meshes.py |
| TERR-05 | Claude can generate bridges spanning rivers/chasms (stone arch, rope, drawbridge) | Existing `generate_bridge_mesh()` already in procedural_meshes.py -- needs handler exposure + terrain-aware placement |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| procedural_meshes.py | Internal (10,861 lines) | 127 mesh generators across 21 categories | Already built, pure-logic, returns MeshSpec dicts |
| _building_grammar.py | Internal | Room configs, furniture placement, scale validation | Existing pure-logic placement engine |
| _scatter_engine.py | Internal | Poisson disk sampling, biome rules | Existing pure-logic scatter distribution |
| _dungeon_gen.py | Internal | BSP dungeon layout, room types, corridors | Existing pure-logic dungeon generation |
| pipeline_lod.py | Internal | LOD chain via Decimate modifier | Existing Blender handler for LOD generation |
| opensimplex | (existing) | Noise generation for terrain/cliffs | Already used in _terrain_noise.py |
| numpy | (existing) | Heightmap arrays, terrain math | Already used throughout terrain system |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| bmesh | Blender built-in | Create mesh objects from vertex/face data | In handler files only (not pure-logic) |
| bpy | Blender built-in | Object creation, scene management | In handler files only |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Decimate modifier for LOD | Quadriflow retopo | Decimate is faster and more predictable for simple LOD; Quadriflow gives better topology but is slower |
| bmesh for mesh creation | bpy.ops.mesh.primitive_* | bmesh is lower-level but gives exact control over vertex/face placement; bpy.ops is higher-level but less precise |

## Architecture Patterns

### Recommended Project Structure
```
blender_addon/handlers/
  procedural_meshes.py     # 127 generators (EXISTING, pure-logic)
  _mesh_bridge.py           # NEW: _mesh_from_spec() bridge function (pure-logic helpers + Blender object creation)
  _terrain_depth.py         # NEW: cliff/cave/waterfall/biome pure-logic generators
  environment.py            # MODIFIED: add terrain depth handlers
  environment_scatter.py    # MODIFIED: replace primitive templates with procedural meshes
  worldbuilding.py          # MODIFIED: replace cube furniture with procedural meshes
  pipeline_lod.py           # EXISTING: LOD chain generation (may need batch helper)
tests/
  test_mesh_bridge.py       # NEW: bridge function tests
  test_terrain_depth.py     # NEW: terrain depth generator tests
  test_mesh_integration.py  # NEW: integration tests verifying handler->generator wiring
```

### Pattern 1: MeshSpec-to-Blender Bridge
**What:** A function that converts the pure-logic MeshSpec dict (vertices, faces, uvs, metadata) into a Blender mesh object.
**When to use:** Every time a handler needs to create geometry from a procedural mesh generator.
**Example:**
```python
# In _mesh_bridge.py
import bpy
import bmesh

def mesh_from_spec(
    spec: dict,
    name: str | None = None,
    location: tuple[float, float, float] = (0, 0, 0),
    rotation: tuple[float, float, float] = (0, 0, 0),
    scale: tuple[float, float, float] = (1, 1, 1),
    collection: bpy.types.Collection | None = None,
    parent: bpy.types.Object | None = None,
) -> bpy.types.Object:
    """Convert MeshSpec dict to a Blender mesh object.

    Args:
        spec: Dict with 'vertices', 'faces', optionally 'uvs' and 'metadata'.
        name: Object name (defaults to spec metadata name).
        location: World position.
        rotation: Euler rotation (radians).
        scale: Object scale.
        collection: Target collection (defaults to active).
        parent: Parent object.

    Returns:
        Created bpy.types.Object.
    """
    obj_name = name or spec.get("metadata", {}).get("name", "ProceduralMesh")

    mesh = bpy.data.meshes.new(obj_name)
    bm = bmesh.new()

    vertices = spec["vertices"]
    faces = spec["faces"]

    # Add vertices
    bm_verts = [bm.verts.new(v) for v in vertices]
    bm.verts.ensure_lookup_table()

    # Add faces
    for face_indices in faces:
        try:
            bm.faces.new([bm_verts[i] for i in face_indices])
        except (ValueError, IndexError):
            pass  # Skip degenerate faces

    # Apply UVs if present
    uvs = spec.get("uvs", [])
    if uvs:
        uv_layer = bm.loops.layers.uv.new("UVMap")
        for face in bm.faces:
            for loop in face.loops:
                vi = loop.vert.index
                if vi < len(uvs):
                    loop[uv_layer].uv = uvs[vi]

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(obj_name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = scale

    if parent:
        obj.parent = parent

    target_coll = collection or bpy.context.collection
    target_coll.objects.link(obj)

    return obj
```

### Pattern 2: Furniture Type-to-Generator Mapping
**What:** A mapping table that connects the furniture type strings in `_ROOM_CONFIGS` to the appropriate procedural mesh generator function.
**When to use:** When `handle_generate_interior` places furniture items.
**Example:**
```python
# In _mesh_bridge.py (pure-logic mapping portion)
from .procedural_meshes import (
    generate_table_mesh, generate_chair_mesh, generate_shelf_mesh,
    generate_chest_mesh, generate_barrel_mesh, generate_candelabra_mesh,
    generate_bookshelf_mesh, generate_altar_mesh, generate_pillar_mesh,
    generate_brazier_mesh, generate_chandelier_mesh, generate_crate_mesh,
    generate_rug_mesh, generate_banner_mesh, generate_anvil_mesh,
    generate_forge_mesh, generate_workbench_mesh, generate_cauldron_mesh,
    generate_sarcophagus_mesh, generate_chain_mesh, generate_door_mesh,
)

# Maps room config furniture type -> (generator_func, kwargs_override)
FURNITURE_GENERATOR_MAP: dict[str, tuple[callable, dict]] = {
    "table": (generate_table_mesh, {}),
    "large_table": (generate_table_mesh, {"width": 1.8, "depth": 1.2}),
    "long_table": (generate_table_mesh, {"width": 1.8, "depth": 4.0}),
    "serving_table": (generate_table_mesh, {"width": 1.5, "depth": 0.6}),
    "desk": (generate_table_mesh, {"style": "noble_carved", "width": 1.2}),
    "chair": (generate_chair_mesh, {}),
    "shelf": (generate_shelf_mesh, {}),
    "bookshelf": (generate_bookshelf_mesh, {}),
    "shelf_with_bottles": (generate_shelf_mesh, {"style": "potion_shelf"}),
    "chest": (generate_chest_mesh, {}),
    "locked_chest": (generate_chest_mesh, {"style": "iron_bound"}),
    "barrel": (generate_barrel_mesh, {}),
    "candelabra": (generate_candelabra_mesh, {}),
    "altar": (generate_altar_mesh, {}),
    "pillar": (generate_pillar_mesh, {}),
    "brazier": (generate_brazier_mesh, {}),
    "chandelier": (generate_chandelier_mesh, {}),
    "crate": (generate_crate_mesh, {}),
    "rug": (generate_rug_mesh, {}),
    "carpet": (generate_rug_mesh, {}),
    "banner": (generate_banner_mesh, {}),
    "sarcophagus": (generate_sarcophagus_mesh, {}),
    "chains": (generate_chain_mesh, {}),
    "anvil": (generate_anvil_mesh, {}),
    "forge": (generate_forge_mesh, {}),
    "workbench": (generate_workbench_mesh, {}),
    "cauldron": (generate_cauldron_mesh, {}),
    # Types without direct generator -> fallback to scaled cube (marked for future)
}
```

### Pattern 3: Vegetation Template Replacement
**What:** Replace `_create_vegetation_template()` in environment_scatter.py to generate real mesh templates from procedural_meshes instead of cones/cubes/icospheres.
**When to use:** When scatter handler creates template collection instances.
**Example:**
```python
from .procedural_meshes import (
    generate_tree_mesh, generate_rock_mesh,
    generate_mushroom_mesh, generate_root_mesh,
)
from ._mesh_bridge import mesh_from_spec

_VEG_GENERATOR_MAP = {
    "tree": generate_tree_mesh,
    "bush": generate_mushroom_mesh,  # Use mushroom as bush proxy
    "rock": generate_rock_mesh,
    "grass": None,  # Keep as billboard plane (no 3D generator needed)
    "mushroom": generate_mushroom_mesh,
    "root": generate_root_mesh,
}

def _create_vegetation_template(veg_type, collection):
    generator = _VEG_GENERATOR_MAP.get(veg_type)
    if generator is None:
        # Fallback: original primitive creation
        ...
    spec = generator()
    obj = mesh_from_spec(spec, name=f"_template_{veg_type}", collection=collection)
    return obj
```

### Pattern 4: Pure-Logic / Handler Separation
**What:** All mesh generation logic lives in pure-Python files with no bpy imports. Handler files are thin wrappers that call pure-logic, then convert results to Blender objects.
**When to use:** Always. This is the established project pattern -- never break it.
**Rationale:** Enables testing 127+ generators via pytest without Blender running. Tests run in CI. Only handler files touch bpy.

### Anti-Patterns to Avoid
- **Importing bpy in pure-logic modules:** Never. The existing separation is critical for testability. New terrain depth generators must be pure-logic.
- **Creating geometry directly in handler loops:** Use the bridge function. Do not inline vertex/face creation in each handler.
- **Hardcoding furniture type -> generator mapping in multiple places:** Create a single FURNITURE_GENERATOR_MAP, import it everywhere.
- **Creating N individual objects for scatter:** Use collection instances (the existing pattern). Create one template mesh from the procedural generator, then instance it many times.
- **Generating LODs inside the procedural mesh generators:** LOD generation happens AFTER mesh creation via the existing Decimate modifier pipeline. Generators always produce LOD0 (full detail).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vertex/face -> Blender object | Inline bmesh code in every handler | `_mesh_from_spec()` bridge function | Single point of change, handles UVs, normals, materials consistently |
| LOD generation | Custom face reduction algorithm | `pipeline_lod.py` Decimate modifier pipeline | Already tested, handles LOD naming, produces clean results |
| Point distribution for scatter | Custom random placement | `_scatter_engine.py` Poisson disk sampling | Already tested, produces blue-noise distribution, avoids clustering |
| Noise for terrain features | Custom noise function | `opensimplex.OpenSimplex` via `_terrain_noise.py` | Already integrated, deterministic with seeds |
| Mesh merging | Manual vertex offset tracking | `procedural_meshes._merge_meshes()` | Already tested utility, handles index remapping |
| Room furniture placement | Custom collision avoidance | `_building_grammar.generate_interior_layout()` | Already has wall/center/corner placement rules with collision avoidance |

**Key insight:** Almost all the infrastructure for this phase already exists. The work is primarily WIRING -- connecting existing generators to existing placement engines through a bridge function, and adding a handful of new terrain depth generators that follow the established pure-logic pattern.

## Common Pitfalls

### Pitfall 1: Furniture Scale Mismatch
**What goes wrong:** Procedural meshes have their own dimensions (e.g., `generate_table_mesh(width=1.2, height=0.8)`) but `_ROOM_CONFIGS` also specifies dimensions `(width, depth, height)` for placement. If the generated mesh dimensions don't match the room config expected dimensions, furniture will be wrong-sized or overlap.
**Why it happens:** The room config tuple `(type, placement_rule, (base_size_x, base_size_y), height)` was designed for cubes where the size IS the cube size. Procedural meshes have their own internal dimensions.
**How to avoid:** The bridge function must SCALE the generated mesh to match the room config dimensions. Compare the spec's `metadata.dimensions` (width/height/depth) to the room config's expected size, and apply a scale factor.
**Warning signs:** Furniture clipping through walls, tables floating above the floor, chairs twice the size of tables.

### Pitfall 2: UV Coordinate Loss
**What goes wrong:** Procedural meshes include UV data in the `uvs` field, but if the bridge function doesn't properly assign UVs to the bmesh before converting to a Blender mesh, UVs are lost and texturing fails.
**Why it happens:** bmesh UV assignment requires iterating over face loops and setting per-loop UV coordinates, not just per-vertex. The MeshSpec format stores per-vertex UVs which need to be mapped to per-loop.
**How to avoid:** The bridge function must handle UVs via `bm.loops.layers.uv` after face creation. If a generator returns empty UVs, skip UV assignment (Blender will auto-unwrap later).
**Warning signs:** Black or stretched textures on procedural meshes, UV validation failures.

### Pitfall 3: Normal Direction Inconsistency
**What goes wrong:** Some procedural mesh generators may produce faces with inconsistent winding order (some faces point inward, some outward), causing visual artifacts in Blender (dark patches, invisible faces).
**Why it happens:** When merging multiple primitive shapes (via `_merge_meshes`), face winding can be inconsistent between shapes.
**How to avoid:** Call `bm.normal_update()` and optionally `bmesh.ops.recalc_face_normals(bm, faces=bm.faces)` in the bridge function after constructing the mesh.
**Warning signs:** Dark triangles visible in solid or material shading, faces invisible from certain angles.

### Pitfall 4: Scatter Performance with Complex Templates
**What goes wrong:** Replacing simple cones (8 vertices) with full procedural tree meshes (200+ vertices) as scatter templates causes massive viewport slowdown when instancing 5000 times.
**Why it happens:** Collection instances share mesh data, but the display complexity is still multiplied by instance count.
**How to avoid:** Use simplified versions of procedural meshes for scatter templates (lower segment counts), or apply the Decimate modifier to templates before instancing. The existing `max_instances` cap (default 5000) helps, but may need to be lowered for complex templates.
**Warning signs:** Blender viewport becomes sluggish after scatter, memory usage spikes.

### Pitfall 5: Terrain Depth Mesh Seams
**What goes wrong:** Cliff faces, cave entrances, and other terrain depth meshes don't connect seamlessly with the heightmap terrain surface, leaving visible gaps or z-fighting.
**Why it happens:** The terrain mesh and the depth meshes are separate objects with independent vertex positions. If they don't share edge vertices at the junction, a visible seam appears.
**How to avoid:** Terrain depth generators must accept terrain edge position data as input and generate mesh vertices that exactly match the terrain edge. For cliffs, sample the terrain heightmap at the cliff base to compute matching vertex positions.
**Warning signs:** Visible light bleeding through gaps, flickering pixels at mesh junctions.

### Pitfall 6: Breaking Existing Tests
**What goes wrong:** Modifying handler functions breaks existing tests that assert on specific output formats (vertex counts, face counts, result dict structure).
**Why it happens:** Tests for `handle_generate_interior` may assert that the result contains cube-based geometry counts. Replacing cubes with procedural meshes changes these counts.
**How to avoid:** Review existing test assertions before modifying handlers. Update test expectations to match new procedural mesh outputs. Add new tests for the bridge function and generator mapping.
**Warning signs:** Test failures in `test_worldbuilding_handlers.py`, `test_environment_scatter_handlers.py`, `test_building_grammar.py`.

## Code Examples

### Bridge Function Core (verified pattern from existing codebase)
```python
# Source: worldbuilding.py _spec_to_bmesh (lines 232-259) - adapted for MeshSpec
# This pattern is already used in the codebase for BuildingSpec -> bmesh conversion

def _spec_to_blender_mesh(spec: dict) -> bmesh.types.BMesh:
    """Convert MeshSpec dict to bmesh (no object creation yet)."""
    bm = bmesh.new()

    bm_verts = [bm.verts.new(v) for v in spec["vertices"]]
    bm.verts.ensure_lookup_table()

    for face_indices in spec["faces"]:
        try:
            bm.faces.new([bm_verts[i] for i in face_indices])
        except (ValueError, IndexError):
            pass  # Skip degenerate faces (same pattern as worldbuilding.py line 256)

    # Recalculate normals for consistent face direction
    bm.normal_update()

    return bm
```

### Furniture Replacement in Interior Handler
```python
# Source: worldbuilding.py handle_generate_interior (lines 395-414) - modification target
# BEFORE (current):
for item in layout:
    item_bm = bmesh.new()
    bmesh.ops.create_cube(item_bm, size=1.0)
    # Scale cube to furniture dimensions...

# AFTER (target):
for item in layout:
    generator, kwargs = FURNITURE_GENERATOR_MAP.get(
        item["type"], (None, {})
    )
    if generator:
        spec = generator(**kwargs)
        obj = mesh_from_spec(
            spec,
            name=f"{name}_{item['type']}",
            location=tuple(item["position"]),
            rotation=(0, 0, item["rotation"]),
            parent=room_empty,
        )
        # Scale to match room config dimensions
        dims = spec["metadata"]["dimensions"]
        target_sx, target_sy, target_sz = item["scale"]
        if dims["width"] > 0:
            obj.scale.x = target_sx / dims["width"]
        if dims["depth"] > 0:
            obj.scale.y = target_sy / dims["depth"]
        if dims["height"] > 0:
            obj.scale.z = target_sz / dims["height"]
    else:
        # Fallback: original cube creation for unmapped types
        item_bm = bmesh.new()
        bmesh.ops.create_cube(item_bm, size=1.0)
        ...
```

### Scatter Template Replacement
```python
# Source: environment_scatter.py _create_vegetation_template (lines 87-123) - modification target
# BEFORE (current):
if veg_type == "tree":
    bmesh.ops.create_cone(bm, ...)  # 8-vertex cone
elif veg_type == "rock":
    bmesh.ops.create_cube(bm, ...)  # 8-vertex cube

# AFTER (target):
from .procedural_meshes import generate_tree_mesh, generate_rock_mesh, ...
from ._mesh_bridge import mesh_from_spec

def _create_vegetation_template(veg_type, collection):
    generator_map = {
        "tree": (generate_tree_mesh, {"style": "dead_twisted", "segments": 6}),
        "bush": (generate_mushroom_mesh, {"style": "common_cluster", "count": 3}),
        "rock": (generate_rock_mesh, {"style": "boulder", "segments": 8}),
        "grass": None,  # Keep as grid plane (billboard)
    }
    entry = generator_map.get(veg_type)
    if entry:
        gen_func, kwargs = entry
        spec = gen_func(**kwargs)
        obj = mesh_from_spec(spec, name=f"_template_{veg_type}", collection=collection)
    else:
        # Original primitive fallback
        ...
```

### Terrain Depth Generator (new pure-logic pattern)
```python
# Source: procedural_meshes.py _make_cylinder + noise displacement pattern
# New generator following established conventions

def generate_cliff_face_mesh(
    width: float = 20.0,
    height: float = 15.0,
    segments_horizontal: int = 16,
    segments_vertical: int = 12,
    noise_amplitude: float = 0.8,
    noise_scale: float = 3.0,
    seed: int = 0,
    style: str = "granite",
) -> MeshSpec:
    """Generate a vertical cliff face mesh with noise displacement.

    Creates a curved vertical surface (partial cylinder segment) with
    noise-driven surface detail. NOT heightmap-based -- true 3D geometry.
    """
    import random
    rng = random.Random(seed)
    verts = []
    faces = []

    for iy in range(segments_vertical + 1):
        y_frac = iy / segments_vertical
        y = y_frac * height
        for ix in range(segments_horizontal + 1):
            x_frac = ix / segments_horizontal
            x = (x_frac - 0.5) * width
            # Base Z position (slight curve for natural look)
            z_base = 0.3 * math.sin(x_frac * math.pi)
            # Noise displacement
            noise_val = rng.gauss(0, noise_amplitude * 0.3)
            z = z_base + noise_val
            verts.append((x, y, z))

    # Quad faces
    for iy in range(segments_vertical):
        for ix in range(segments_horizontal):
            v0 = iy * (segments_horizontal + 1) + ix
            v1 = v0 + 1
            v2 = v0 + (segments_horizontal + 1) + 1
            v3 = v0 + (segments_horizontal + 1)
            faces.append((v0, v1, v2, v3))

    return _make_result(
        f"cliff_face_{style}",
        verts, faces,
        category="terrain_depth",
        style=style,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Cubes for furniture | Procedural meshes with geometry | This phase | Real game-ready interiors instead of blockout |
| Cones for trees | L-system trunk+branch generators | This phase | Visually recognizable vegetation |
| Heightmap-only terrain | Heightmap + standalone vertical meshes | This phase | Cliffs, caves, overhangs become possible |
| No LOD for procedural meshes | Decimate-based LOD0/1/2 per mesh | This phase | Performance-ready assets |
| No bridge generation handler | Terrain-aware bridge placement | This phase | River/chasm crossings auto-generated |

**Key note:** The `generate_bridge_mesh()` function already exists in procedural_meshes.py (line 3134) but is not exposed as a handler action. The `generate_bridge_spec()` function also exists in `_building_grammar.py` as an internal function. Both need handler wiring.

## Detailed Integration Analysis

### Furniture Types in _ROOM_CONFIGS vs. Available Generators

**Direct matches (generator exists):** table, chair, shelf, chest, barrel, candelabra, bookshelf, altar, pillar, brazier, chandelier, crate, rug, banner, anvil, forge, workbench, cauldron, sarcophagus, chains (chain)

**Close matches (can use existing generator with parameters):**
- large_table -> generate_table_mesh(width=1.8, depth=1.2)
- long_table -> generate_table_mesh(width=1.8, depth=4.0)
- serving_table -> generate_table_mesh(width=1.5, depth=0.6)
- desk -> generate_table_mesh(style="noble_carved")
- locked_chest -> generate_chest_mesh(style="iron_bound")
- shelf_with_bottles -> generate_shelf_mesh() (or bookshelf variant)
- carpet -> generate_rug_mesh()
- cage -> generate_falling_cage_mesh() or generate_hanging_cage_mesh()
- wall_tomb -> generate_sarcophagus_mesh() (rotated)

**No generator available (keep as cube fallback, 18 types):**
bar_counter, fireplace, throne, cot, bucket, bed, wardrobe, nightstand, cooking_fire, weapon_rack, armor_stand, pew, tool_rack, bellows, bunk_bed, footlocker, coin_pile, display_case, safe, map_display, herb_rack, distillation_apparatus, rack, iron_maiden

**Recommendation:** Use generators for all direct and close matches (~30 types). Keep cube fallback for the remaining ~18 unmapped types -- they can be addressed in future phases. This still transforms the majority of interiors from cubes to real meshes.

### Scatter Type Mapping

| Scatter Type | Current Primitive | Procedural Generator | Notes |
|--------------|-------------------|---------------------|-------|
| tree | 8-vert cone | generate_tree_mesh() | 5 styles: dead_twisted, ancient, fungal, willow, pine |
| bush | icosphere | generate_mushroom_mesh() | Use cluster style as proxy, or generate_root_mesh() |
| grass | flat plane | KEEP as plane | Billboard grass is standard game technique |
| rock | cube | generate_rock_mesh() | 4 styles: boulder, cliff_chunk, crystal_embedded, mossy |
| mushroom | N/A | generate_mushroom_mesh() | New scatter type possible |
| root | N/A | generate_root_mesh() | New scatter type possible |

### Dungeon Prop Placement Points

The existing dungeon generator creates room types (generic, spawn, boss, treasure, entrance, exit) but does NOT place props inside rooms. Dungeon prop placement is currently handled ONLY when `handle_generate_interior` is called separately with a dungeon room type.

For MESH3-03, the dungeon handler needs modification to:
1. After generating BSP rooms, place dungeon props (torch sconces along corridor walls, altars in boss rooms, prison doors at cell entrances, trap meshes at corridor junctions)
2. Use the bridge function to create actual meshes from procedural generators
3. The placement logic already exists in `_ROOM_CONFIGS` for dungeon_cell, torture_chamber, and crypt -- extend to cover all dungeon room types

### Castle Element Mapping

| Castle Component | Current Creation | Available Generator | Notes |
|-----------------|-----------------|---------------------|-------|
| Gatehouse | Box with opening | generate_gate_mesh() | Includes portcullis geometry |
| Ramparts | Box primitives | generate_rampart_mesh() | Wall segments with merlons |
| Drawbridge | Not generated | generate_drawbridge_mesh() | Raised/lowered states |
| Corner towers | Cylinder primitives | generate_pillar_mesh() (partial) | May need custom tower variant |
| Courtyard | Flat box | generate_fountain_mesh() + others | Place courtyard detail props |
| Curtain walls | Box primitives | generate_rampart_mesh() | Use as wall segments |

## LOD Integration Strategy

The existing `pipeline_lod.py` handler (`handle_generate_lods`) takes an object name and ratios, then:
1. Renames original to `{name}_LOD0`
2. Duplicates and decimates for each subsequent LOD level
3. Returns per-LOD face counts

**For this phase, LOD integration works in two ways:**

1. **On-demand LOD for individual meshes:** After creating a mesh via `mesh_from_spec()`, call `handle_generate_lods({"object_name": obj.name, "ratios": [1.0, 0.5, 0.25]})`. This is the simplest approach for individually placed furniture/props.

2. **Batch LOD for scatter templates:** Generate LODs for template meshes BEFORE instancing. Each scatter type gets LOD0/LOD1/LOD2 templates, and instances reference the appropriate LOD based on distance (handled at Unity LOD Group setup time, not in Blender).

**Decision ratios (from CONTEXT.md):** LOD0 = full detail, LOD1 = 50% faces, LOD2 = 25% faces. Map to `ratios=[1.0, 0.5, 0.25]`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | Tools/mcp-toolkit/pyproject.toml (implicit) |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_procedural_meshes.py tests/test_building_grammar.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MESH3-01 | Furniture generator mapping covers all _ROOM_CONFIGS types | unit | `pytest tests/test_mesh_bridge.py::test_furniture_mapping -x` | No - Wave 0 |
| MESH3-01 | mesh_from_spec produces valid Blender-compatible data | unit | `pytest tests/test_mesh_bridge.py::test_mesh_from_spec -x` | No - Wave 0 |
| MESH3-02 | Vegetation generator map covers all scatter types | unit | `pytest tests/test_mesh_bridge.py::test_vegetation_mapping -x` | No - Wave 0 |
| MESH3-03 | Dungeon prop placement uses generators from procedural lib | unit | `pytest tests/test_mesh_integration.py::test_dungeon_props -x` | No - Wave 0 |
| MESH3-04 | Castle handler uses gate/rampart/drawbridge generators | unit | `pytest tests/test_mesh_integration.py::test_castle_elements -x` | No - Wave 0 |
| MESH3-05 | LOD ratios [1.0, 0.5, 0.25] produce valid reduced meshes | unit | `pytest tests/test_mesh_bridge.py::test_lod_integration -x` | No - Wave 0 |
| TERR-01 | Cliff face generator produces vertical geometry | unit | `pytest tests/test_terrain_depth.py::test_cliff_face -x` | No - Wave 0 |
| TERR-02 | Cave entrance generator produces arch geometry | unit | `pytest tests/test_terrain_depth.py::test_cave_entrance -x` | No - Wave 0 |
| TERR-03 | Multi-biome blending produces transition zone geometry | unit | `pytest tests/test_terrain_depth.py::test_biome_transition -x` | No - Wave 0 |
| TERR-04 | Waterfall generator produces stepped cascade mesh | unit | `pytest tests/test_terrain_depth.py::test_waterfall -x` | No - Wave 0 |
| TERR-05 | Bridge generator produces spanning geometry with correct endpoints | unit | `pytest tests/test_terrain_depth.py::test_bridge -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_mesh_bridge.py tests/test_terrain_depth.py tests/test_mesh_integration.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mesh_bridge.py` -- covers MESH3-01, MESH3-02, MESH3-05 (bridge function, mapping tables, LOD)
- [ ] `tests/test_terrain_depth.py` -- covers TERR-01 through TERR-05 (all terrain depth generators)
- [ ] `tests/test_mesh_integration.py` -- covers MESH3-03, MESH3-04 (dungeon prop placement, castle elements)

## Open Questions

1. **UV mapping quality for procedural meshes through the bridge**
   - What we know: Generators return per-vertex UVs in the `uvs` list. bmesh uses per-loop UVs.
   - What's unclear: Whether all 127 generators produce valid UV data, or if some return empty `uvs` lists.
   - Recommendation: The bridge function should handle both cases: apply UVs if present, skip if empty. Add a post-creation UV check and auto-unwrap if UVs are missing.

2. **Performance impact of complex scatter templates**
   - What we know: Current scatter uses 8-vertex primitives. Procedural tree meshes could have 200+ vertices.
   - What's unclear: At what vertex count per template does scatter performance become unacceptable for 5000 instances.
   - Recommendation: Use lower-segment-count generator parameters for scatter templates (e.g., `segments=6` instead of default 12). Monitor viewport FPS after scatter. Consider auto-applying LOD1 to templates.

3. **Furniture types without generators (18 unmapped types)**
   - What we know: 18 furniture types in _ROOM_CONFIGS have no matching procedural generator (bed, throne, fireplace, etc.).
   - What's unclear: Whether to add new generators for all 18, or accept cube fallback for now.
   - Recommendation: Accept cube fallback for unmapped types in this phase. The ~30 mapped types already transform the visual quality dramatically. Adding 18 new generators is scope creep -- defer to a future phase.

## Sources

### Primary (HIGH confidence)
- `procedural_meshes.py` (10,861 lines) -- Direct code inspection: 127 generators, 21 categories, MeshSpec format, _merge_meshes, _make_box/_make_cylinder/_make_sphere utilities
- `worldbuilding.py` (1,030+ lines) -- Direct code inspection: _spec_to_bmesh pattern (lines 232-259), _create_mesh_object pattern (lines 262-269), handle_generate_interior (lines 368-417)
- `environment_scatter.py` (322+ lines) -- Direct code inspection: _create_vegetation_template (lines 87-123), _DEFAULT_VEG_RULES, handle_scatter_vegetation
- `_building_grammar.py` (1,600+ lines) -- Direct code inspection: _ROOM_CONFIGS (16 room types, lines 886-1034), FURNITURE_SCALE_REFERENCE, generate_interior_layout
- `_dungeon_gen.py` (80+ lines header) -- Direct code inspection: BSP layout, Room dataclass, DungeonLayout, CaveMap
- `pipeline_lod.py` -- Direct code inspection: handle_generate_lods, _validate_lod_ratios, Decimate modifier workflow
- `_terrain_noise.py` -- Direct code inspection: 6 terrain presets, heightmap generation, opensimplex noise
- `.planning/research/3d-modeling-gap-analysis.md` -- Gap analysis identifying P-01 (furniture cubes), E-01 (vegetation primitives), T-02 (cliff faces), T-03 (cave entrances) as critical gaps

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` -- Phase 18 success criteria, dependency chain
- `.planning/REQUIREMENTS.md` -- MESH3-01 through MESH3-05, TERR-01 through TERR-05 requirement text

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries are internal, directly inspected
- Architecture: HIGH -- patterns derived from existing codebase conventions with 10,000+ lines of precedent
- Pitfalls: HIGH -- identified from actual code structure (scale mismatches, UV handling, normal directions)
- Terrain depth: MEDIUM -- new generators follow established patterns but exact implementations untested
- LOD integration: HIGH -- existing pipeline_lod.py handles the complexity

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (internal codebase, stable patterns)
