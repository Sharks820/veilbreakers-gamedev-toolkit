# Phase 6: Environment & World Building - Research

**Researched:** 2026-03-19
**Domain:** Blender Python procedural environment generation -- terrain heightmaps, erosion simulation, dungeon/cave systems, building generation, vegetation scatter, modular architecture, Unity-ready export
**Confidence:** HIGH

## Summary

This phase delivers a complete procedural environment generation pipeline as Blender addon handlers, following the established compound MCP tool pattern (13 tools, 64 handlers across 5 phases). The core work splits into six algorithmic domains: (1) heightmap-based terrain with noise functions and erosion simulation, (2) dungeon/cave layout generation using BSP and cellular automata, (3) procedural building construction from grammar rules, (4) vegetation and prop scatter systems, (5) modular architecture kits with grid-snapping, and (6) world layout orchestration (towns, settlements, roads, rivers).

All pure-logic algorithms (noise generation, erosion simulation, BSP partitioning, cellular automata, building grammar evaluation, scatter distribution) must be extracted into testable modules that run without Blender. The Blender-side handlers convert algorithm output (heightmaps, room layouts, building specs) into actual geometry via the established bmesh API pattern. The `bmesh.ops.create_grid()` function provides the terrain mesh foundation -- a subdivided plane whose vertex Z-positions are set from the heightmap array. Material slot assignment per-face enables biome auto-painting based on slope/altitude rules.

The project needs 2 new compound tools (`blender_environment` and `blender_worldbuilding`) with approximately 16-20 handler actions total, bringing the tool count to 15 (well within the 26-tool ARCH-01 budget). The `opensimplex` library (v0.4.5.1, May 2024, Python 3.8+) is the recommended noise generator -- it supports numpy array operations for performance and avoids the patent issues of Simplex noise and the staleness of the `noise` package (last updated 2015, Python 3.4 only). Heightmaps export as 16-bit little-endian RAW files for direct Unity Terrain import.

**Primary recommendation:** Build 4-5 pure-logic modules (noise/erosion, dungeon/cave, building grammar, scatter, modular kit) with corresponding handler files. Two compound tools: `blender_environment` for terrain/water/vegetation/roads and `blender_worldbuilding` for buildings/dungeons/towns/interiors/props. Target 4 plans covering terrain, structures, layouts, and scatter/props.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Heightmap-based terrain using noise functions (Perlin, Simplex, Voronoi, fBm)
- Erosion simulation: hydraulic (water flow) and thermal (slope collapse) applied as post-process
- Terrain features are parameterized: mountains (high amplitude), canyons (subtracted ridges), cliffs (step functions), volcanic (crater radial falloff)
- Auto texture painting based on slope/altitude/moisture rules mapped to terrain material slots
- Procedural building from grammar rules: foundation -> walls -> floors -> roof -> details
- Configurable style parameters: medieval, gothic, rustic, fortress, organic
- Interior generation places furniture, wall decorations, lighting based on room type
- Castle/tower/bridge/fortress use specialized generation templates
- BSP (Binary Space Partition) for room placement with corridor connections
- Cave systems use cellular automata for natural formations
- Connected graph ensures navigability (no orphan rooms)
- Spawn points, loot positions, and door placements are part of the layout
- Biome-aware scatter: tree types by altitude band, grass density by slope, rocks by terrain roughness
- Context-aware props: barrels near taverns, crates near docks, lanterns near paths
- Particle system or collection instances for performance
- Snap-together pieces: walls (straight, corner, T), floors, doors, windows, stairs
- Grid-based placement system with configurable cell size
- Ruins variant: damaged versions of modular pieces (broken walls, collapsed roofs, overgrown)

### Claude's Discretion
All implementation choices are at Claude's discretion -- autonomous execution mode.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENV-01 | Terrain generation (mountains, hills, plains, volcanic, canyon, cliffs) with erosion | opensimplex noise + fBm octaves for heightmap; hydraulic droplet erosion + thermal talus erosion as post-process; terrain type presets as parameter dicts |
| ENV-02 | Auto terrain texture painting (slope/altitude/moisture biome rules) | Per-face material slot assignment via bmesh; slope from face normal dot(0,0,1), altitude from vertex Z, moisture as secondary noise layer |
| ENV-03 | Cave/dungeon system generation (connected rooms, corridors, natural formations) | Cellular automata (4-5 rule) for cave shapes; flood-fill connectivity check; 3D mesh extrusion from 2D cave map |
| ENV-04 | River/stream carving with erosion and flow | A* pathfinding from source to destination on heightmap; channel carving by lowering vertex heights along path; smooth Bezier interpolation |
| ENV-05 | Road/path generation between points with proper grading | Weighted A* on heightmap (prefer low-slope paths); flatten vertices along route; width parameter for road bed |
| ENV-06 | Water body creation (lakes, oceans, ponds with shoreline and depth) | Flat plane at water level with material; shoreline blend via vertex color gradient; depth map for transparency |
| ENV-07 | Biome-aware vegetation scatter (trees, grass, rocks, bushes with slope/altitude rules) | Poisson disk sampling for natural distribution; altitude/slope/moisture filter masks; collection instances for performance |
| ENV-08 | AAA-quality procedural building generation (configurable style, floors, roof, materials) | Grammar-rule system: foundation -> walls -> floors -> roof -> details; style config dicts (medieval, gothic, etc.); bmesh geometry construction |
| ENV-09 | Castle/tower/bridge/fortress generation with architectural detail | Specialized template configs extending building grammar; tower=cylinder+battlements, bridge=arch+road, fortress=walls+towers+keep |
| ENV-10 | Ruins generation (damage existing structures -- broken walls, collapsed roof, overgrown) | Mesh damage: random face deletion, edge displacement, boolean subtraction holes; overgrown = vegetation scatter on ruin surfaces |
| ENV-11 | Town/settlement layout (streets, building plots, districts, landmarks) | Voronoi-based district partitioning; road network from district boundaries; building plot subdivision within districts |
| ENV-12 | Dungeon layout generation (rooms, corridors, doors, spawn points, loot placement) | BSP tree recursive partition; room placement in leaf nodes; L-shaped corridor connections; metadata overlay for game objects |
| ENV-13 | Interior generation (furniture, wall decorations, lighting) | Room-type config dicts (tavern, throne room, cell, etc.); furniture placement with collision avoidance; wall-hugging decoration placement |
| ENV-14 | Modular architecture kit (snap-together walls, floors, corners, doors, windows) | Grid-aligned bmesh piece generation; configurable cell_size (default 2m); piece catalog with connection metadata |
| ENV-15 | Context-aware prop scatter (barrels near tavern, crates near dock) | Tag-based affinity system: buildings tagged with type, props scored by proximity to matching tags |
| ENV-16 | Breakable prop variants and destroyed versions | Per-prop destruction config: mesh fracture via boolean cuts, debris scatter, material darkening for damage |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bpy (Blender Python API) | 4.x | All mesh creation, material assignment, object linking, export | Only option for Blender scripting |
| bmesh | 4.x (bundled) | Terrain grid creation, building geometry, modular piece construction | Avoids bpy.ops context issues from timer callbacks (established pattern) |
| mathutils | 4.x (bundled) | Vector math, Matrix transforms, noise functions | Blender's native math library |
| opensimplex | 0.4.5.1 | Noise generation for terrain heightmaps (Perlin-like, fBm) | Python 3.8+, numpy-accelerated, no patent issues, actively maintained (May 2024) |
| numpy | >=1.26.0 | Heightmap arrays, erosion simulation, fast noise evaluation | Already in dev deps; essential for grid-based math at terrain resolution |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| math (stdlib) | 3.12 | Trigonometry, sqrt for erosion/distance calculations | All pure-logic modules |
| random (stdlib) | 3.12 | Seed-based randomization for BSP splits, scatter jitter | Reproducible generation with seed parameter |
| collections (stdlib) | 3.12 | deque for BFS/flood-fill connectivity, defaultdict for graph adjacency | Dungeon/cave connectivity validation |
| struct (stdlib) | 3.12 | Pack heightmap as 16-bit little-endian RAW for Unity | Terrain export (ENV-01) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| opensimplex | noise (caseman) | noise package last updated 2015, supports only Python 2.7/3.3/3.4 -- incompatible with Python 3.12 |
| opensimplex | pynoise 3.0.0 | More features (ridged multifractal, Worley) but heavier dependency; opensimplex + manual fBm octave stacking covers all terrain needs |
| opensimplex | mathutils.noise | Blender-only (not testable outside Blender); limited noise types |
| numpy erosion | scipy.ndimage | Gradient/convolution helpers, but adds dependency; raw numpy sufficient for droplet/thermal erosion |

### New Dependencies
```bash
# Add to pyproject.toml [project] dependencies:
# opensimplex>=0.4.5

# numpy already in [dependency-groups] dev -- move to main deps or keep as optional
# (opensimplex hard-depends on numpy anyway)
```

**Installation note:** `opensimplex` requires `numpy`. Since `numpy` is already in dev dependencies and `opensimplex` will pull it in, this is a single new dependency addition to pyproject.toml.

## Architecture Patterns

### Recommended Project Structure
```
blender_addon/handlers/
    environment.py           # Terrain, water, river, road handlers (ENV-01, -02, -04, -05, -06)
    environment_scatter.py   # Vegetation scatter, prop scatter, breakable props (ENV-07, -15, -16)
    worldbuilding.py         # Building, castle, ruins, modular kit handlers (ENV-08, -09, -10, -14)
    worldbuilding_layout.py  # Dungeon, cave, town, interior handlers (ENV-03, -11, -12, -13)
blender_addon/handlers/
    _terrain_noise.py        # Pure-logic: noise generation, fBm, terrain presets (testable without Blender)
    _terrain_erosion.py      # Pure-logic: hydraulic + thermal erosion on numpy arrays (testable)
    _dungeon_gen.py          # Pure-logic: BSP partition, cellular automata, connectivity (testable)
    _building_grammar.py     # Pure-logic: grammar-rule building specs, style configs (testable)
    _scatter_engine.py       # Pure-logic: Poisson disk, biome filters, context-aware placement (testable)
tests/
    test_terrain_noise.py    # Noise function tests, fBm octave stacking, terrain preset validation
    test_terrain_erosion.py  # Erosion algorithm correctness, conservation of mass, edge cases
    test_dungeon_gen.py      # BSP partition, cave generation, connectivity guarantee tests
    test_building_grammar.py # Grammar rule evaluation, style config validation, piece generation
    test_scatter_engine.py   # Poisson disk spacing, biome filter accuracy, context affinity scoring
    test_environment_handlers.py  # Handler integration tests (pure-logic output verification)
    test_worldbuilding_handlers.py # Handler integration tests (building/layout output verification)
src/veilbreakers_mcp/
    blender_server.py        # Add blender_environment + blender_worldbuilding compound tools
```

### Pattern 1: Heightmap-as-Array Pipeline
**What:** All terrain operations work on numpy 2D float arrays (heightmaps). Noise generates the initial heightmap, erosion mutates it, then a Blender handler converts it to mesh geometry.
**When to use:** ENV-01, ENV-02, ENV-04, ENV-05, ENV-06
**Example:**
```python
# Pure-logic module: _terrain_noise.py (no bpy imports)
import numpy as np
from opensimplex import OpenSimplex

def generate_heightmap(
    width: int,
    height: int,
    scale: float = 100.0,
    octaves: int = 6,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
    seed: int = 0,
    terrain_type: str = "mountains",
) -> np.ndarray:
    """Generate a 2D heightmap using fBm noise.

    Returns numpy array of shape (height, width) with values in [0, 1].
    """
    gen = OpenSimplex(seed=seed)
    hmap = np.zeros((height, width), dtype=np.float64)

    for y in range(height):
        for x in range(width):
            amplitude = 1.0
            frequency = 1.0
            total = 0.0
            max_val = 0.0
            for _ in range(octaves):
                nx = x / scale * frequency
                ny = y / scale * frequency
                total += gen.noise2(nx, ny) * amplitude
                max_val += amplitude
                amplitude *= persistence
                frequency *= lacunarity
            hmap[y, x] = total / max_val

    # Apply terrain-type shaping
    hmap = _apply_terrain_preset(hmap, terrain_type)

    # Normalize to [0, 1]
    hmap = (hmap - hmap.min()) / (hmap.max() - hmap.min() + 1e-10)
    return hmap

# Performance note: For large terrains (512x512+), use opensimplex.noise2array()
# for vectorized evaluation instead of per-pixel loop.
```

### Pattern 2: BSP Dungeon Layout (Pure-Logic)
**What:** Recursive binary partition of a 2D grid into rooms, connected by corridors. Returns a structured dict of rooms, corridors, doors, and spawn points.
**When to use:** ENV-03, ENV-12
**Example:**
```python
# Pure-logic module: _dungeon_gen.py (no bpy imports)
import random
from dataclasses import dataclass, field
from collections import deque

@dataclass
class Room:
    x: int
    y: int
    width: int
    height: int
    room_type: str = "generic"  # generic, spawn, boss, treasure, entrance

@dataclass
class DungeonLayout:
    width: int
    height: int
    rooms: list[Room] = field(default_factory=list)
    corridors: list[tuple[tuple[int,int], tuple[int,int]]] = field(default_factory=list)
    doors: list[tuple[int,int]] = field(default_factory=list)
    spawn_points: list[tuple[int,int]] = field(default_factory=list)
    grid: list[list[int]] = field(default_factory=list)  # 0=wall, 1=floor, 2=corridor, 3=door

def generate_bsp_dungeon(
    width: int = 64,
    height: int = 64,
    min_room_size: int = 6,
    max_depth: int = 5,
    seed: int = 0,
) -> DungeonLayout:
    """Generate dungeon layout using BSP partitioning.

    Guarantees all rooms are connected (verified by flood-fill).
    """
    rng = random.Random(seed)
    # ... BSP partition, room placement, corridor connection ...
```

### Pattern 3: Building Grammar Rules
**What:** A grammar-rule system where each building style is a config dict defining how to construct each layer (foundation, walls, floors, roof, details). The grammar evaluator produces a list of geometry operations that the Blender handler executes.
**When to use:** ENV-08, ENV-09, ENV-13
**Example:**
```python
# Pure-logic module: _building_grammar.py (no bpy imports)

MEDIEVAL_STYLE = {
    "name": "medieval",
    "foundation": {"height": 0.3, "inset": 0.05, "material": "stone_dark"},
    "walls": {"height_per_floor": 3.0, "thickness": 0.3, "material": "plaster_white"},
    "floor_slab": {"thickness": 0.2, "material": "wood_planks"},
    "roof": {"type": "gabled", "overhang": 0.4, "pitch": 35, "material": "thatch"},
    "windows": {"style": "arched", "width": 0.8, "height": 1.2, "per_wall": 2},
    "door": {"style": "wooden_arched", "width": 1.2, "height": 2.2},
    "details": ["timber_frame", "window_boxes", "chimney"],
}

@dataclass
class BuildingSpec:
    """Output of grammar evaluation -- geometry operations for handler."""
    footprint: tuple[float, float]     # width, depth
    floors: int
    style: dict
    operations: list[dict]  # [{type: "box", pos, size, material}, {type: "cylinder", ...}]
```

### Pattern 4: Scatter with Poisson Disk Sampling
**What:** Use Poisson disk sampling to place vegetation/props with minimum spacing, then filter by biome rules (altitude, slope, moisture). Output is a list of (position, type, scale, rotation) tuples.
**When to use:** ENV-07, ENV-15
**Example:**
```python
# Pure-logic module: _scatter_engine.py
def poisson_disk_sample(
    width: float, depth: float,
    min_distance: float,
    seed: int = 0,
    max_attempts: int = 30,
) -> list[tuple[float, float]]:
    """Bridson's algorithm for 2D Poisson disk sampling."""
    ...

def biome_filter(
    points: list[tuple[float, float]],
    heightmap: np.ndarray,
    slope_map: np.ndarray,
    rules: dict,
) -> list[dict]:
    """Filter scatter points by biome rules, return placement specs."""
    ...
```

### Anti-Patterns to Avoid
- **Per-vertex bpy.ops calls:** Never use `bpy.ops.mesh.primitive_*` in a loop for terrain vertices. Use bmesh.ops.create_grid() once, then set vertex Z positions from heightmap array.
- **Blender-dependent algorithm logic:** Never mix erosion/BSP/noise math with bpy calls. All algorithms must be in pure-logic modules importable without Blender.
- **Unbounded generation:** Always accept `seed` parameter for reproducibility. All generation functions must produce identical output for identical inputs.
- **Memory-heavy terrain:** For terrains over 512x512 vertices, use opensimplex array functions instead of per-pixel noise evaluation. Cap default resolution at 256x256 (65K vertices) with configurable override.
- **Single material for terrain:** Do not use vertex colors for biome painting. Use multiple material slots with per-face assignment -- this is the Unity-compatible approach for terrain splatmaps.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Noise generation | Custom Perlin implementation | opensimplex 0.4.5.1 | Correct gradient noise with numpy acceleration; patent-free; tested |
| fBm octave stacking | Custom octave loop on raw noise | opensimplex + standard fBm formula | Standard technique: sum(noise(f*x) * a^i) with persistence/lacunarity |
| Poisson disk sampling | Random scatter + rejection | Bridson's algorithm | O(n) vs O(n^2) rejection; guarantees minimum spacing in linear time |
| 16-bit RAW export | Custom binary format | `struct.pack('<H', value)` for each pixel | Unity expects exactly this format; no room for variation |
| Connected graph check | Custom DFS | BFS flood-fill from any room | Standard flood-fill guarantees all rooms reachable; simple to implement and test |
| Heightmap slope calculation | Manual finite differences | `np.gradient(heightmap)` then magnitude | numpy gradient is correct, vectorized, handles edges properly |

**Key insight:** The algorithms (noise, erosion, BSP, cellular automata, Poisson disk) are all well-established with standard implementations. The novelty is in the Blender integration layer (converting algorithm output to mesh geometry) and the game-specific parameterization (dark fantasy presets, Unity export format). Don't reinvent the algorithms.

## Common Pitfalls

### Pitfall 1: Heightmap-to-Mesh Y-Axis Inversion
**What goes wrong:** Generated terrain appears mirrored or rotated 90 degrees when imported into Unity.
**Why it happens:** Blender uses Z-up coordinate system; Unity uses Y-up. Additionally, numpy array row 0 is at the "top" which maps to negative Y in Blender space.
**How to avoid:** Always export heightmaps with explicit coordinate mapping. Use `struct.pack('<H', ...)` writing row by row where row 0 = min-Y in Blender space. Add a `flip_vertical` parameter matching Unity's import toggle.
**Warning signs:** Terrain looks correct in Blender but rivers flow uphill in Unity.

### Pitfall 2: Erosion Breaks Heightmap Bounds
**What goes wrong:** Hydraulic or thermal erosion produces negative heights or values exceeding the 16-bit range (0-65535).
**Why it happens:** Erosion algorithms subtract material from cells without clamping. Accumulated error over many iterations pushes values out of range.
**How to avoid:** Clamp heightmap values after each erosion iteration: `np.clip(heightmap, 0.0, 1.0)`. Normalize to [0, 1] range before RAW export, then scale to uint16 with `(heightmap * 65535).astype(np.uint16)`.
**Warning signs:** Black holes or white spikes in exported heightmap.

### Pitfall 3: BSP Generates Disconnected Rooms
**What goes wrong:** Some dungeon rooms are unreachable despite corridor generation.
**Why it happens:** Corridor generation connects sibling nodes in the BSP tree but may miss connections when the tree is unbalanced or room placement leaves gaps.
**How to avoid:** After BSP generation, run flood-fill from the entrance room. If any room is unreachable, add a forced corridor. The connectivity check is a required post-condition, not optional.
**Warning signs:** Player cannot reach all rooms; test asserts on `_verify_connectivity()` fail.

### Pitfall 4: Building Geometry Has Non-Manifold Edges
**What goes wrong:** Boolean operations for windows/doors leave non-manifold edges that fail game-readiness checks.
**Why it happens:** Boolean subtract for window openings in walls creates edge cases at exact face intersections.
**How to avoid:** Use the EXACT boolean solver (established in Phase 2). Run auto-repair after boolean operations. Alternative: build walls with window openings directly in bmesh (no boolean needed) by creating the wall faces around the opening.
**Warning signs:** mesh_analyze_topology returns non-manifold edge count > 0 after building generation.

### Pitfall 5: Scatter Performance Collapse
**What goes wrong:** Vegetation scatter with 10,000+ instances causes Blender to hang.
**Why it happens:** Creating individual objects via bpy.data.objects.new() for each grass blade.
**How to avoid:** Use collection instances (instancing) where one "template" object is duplicated via instance_collection. For dense vegetation, create a particle system or use Blender's collection instancer. Return instance count in handler result for verification.
**Warning signs:** Handler takes > 30 seconds; Blender becomes unresponsive.

### Pitfall 6: Modular Pieces Don't Snap
**What goes wrong:** Wall segments have visible gaps or overlap when placed on the grid.
**Why it happens:** Piece dimensions don't exactly match the grid cell size, or origin points are inconsistent.
**How to avoid:** All modular pieces must have origin at (0, 0, 0) corner (not center). Dimensions must be exact multiples of cell_size. Test by placing two pieces adjacently and checking for vertex proximity < epsilon.
**Warning signs:** Visible seams between snapped pieces; z-fighting at joints.

## Code Examples

Verified patterns from project codebase and official documentation:

### Terrain Mesh from Heightmap (Blender Handler)
```python
# In environment.py handler -- converts numpy heightmap to Blender mesh
import bpy
import bmesh
import numpy as np

def _heightmap_to_mesh(
    heightmap: np.ndarray,
    name: str,
    terrain_size: float = 100.0,
    height_scale: float = 20.0,
) -> bpy.types.Object:
    """Convert a 2D numpy heightmap to a Blender mesh object.

    Uses bmesh.ops.create_grid for the base plane, then sets vertex Z
    from heightmap values. This avoids bpy.ops context issues.
    """
    rows, cols = heightmap.shape

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # Create subdivided grid matching heightmap resolution
    bmesh.ops.create_grid(
        bm,
        x_segments=cols - 1,
        y_segments=rows - 1,
        size=terrain_size / 2.0,  # size is half-extent
        calc_uvs=True,
    )

    bm.verts.ensure_lookup_table()

    # Map grid vertices to heightmap values
    # bmesh create_grid generates verts in row-major order
    for i, vert in enumerate(bm.verts):
        # Convert vertex XY position to heightmap UV coordinates
        u = (vert.co.x + terrain_size / 2.0) / terrain_size
        v = (vert.co.y + terrain_size / 2.0) / terrain_size
        col_idx = int(u * (cols - 1))
        row_idx = int(v * (rows - 1))
        col_idx = max(0, min(col_idx, cols - 1))
        row_idx = max(0, min(row_idx, rows - 1))
        vert.co.z = heightmap[row_idx, col_idx] * height_scale

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj
```

### Per-Face Material Assignment for Biome Painting
```python
# Assign material slots based on slope/altitude rules
def _auto_paint_terrain(obj, heightmap, biome_rules):
    """Assign material slots to terrain faces based on biome rules.

    biome_rules example:
    [
        {"name": "snow",    "material": "terrain_snow",    "min_alt": 0.8, "max_slope": 45},
        {"name": "rock",    "material": "terrain_rock",    "min_slope": 40, "max_slope": 90},
        {"name": "grass",   "material": "terrain_grass",   "min_alt": 0.2, "max_alt": 0.8, "max_slope": 35},
        {"name": "sand",    "material": "terrain_sand",    "max_alt": 0.2, "max_slope": 20},
    ]
    """
    import math
    mesh = obj.data

    # Create and assign material slots
    for rule in biome_rules:
        mat = bpy.data.materials.get(rule["material"])
        if mat is None:
            mat = bpy.data.materials.new(name=rule["material"])
            mat.use_nodes = True
        mesh.materials.append(mat)

    # Assign each face to a material slot based on rules
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    for face in bm.faces:
        # Calculate face center altitude (normalized 0-1)
        center = face.calc_center_median()
        altitude = center.z / height_scale  # normalize

        # Calculate slope from face normal (degrees from vertical)
        slope_rad = math.acos(max(-1, min(1, face.normal.z)))
        slope_deg = math.degrees(slope_rad)

        # Find matching biome rule (first match wins, order matters)
        for idx, rule in enumerate(biome_rules):
            if _matches_biome_rule(altitude, slope_deg, rule):
                face.material_index = idx
                break

    bm.to_mesh(mesh)
    bm.free()
```

### 16-bit RAW Heightmap Export for Unity
```python
# Export heightmap as 16-bit little-endian RAW for Unity Terrain import
import struct
import numpy as np

def export_heightmap_raw(
    heightmap: np.ndarray,
    filepath: str,
    flip_vertical: bool = True,
) -> dict:
    """Export heightmap as 16-bit RAW for Unity.

    Unity expects:
    - 16-bit unsigned integers (0-65535)
    - Little-endian byte order (Windows default)
    - Power-of-two dimensions + 1 (e.g., 257x257, 513x513)
    - Row-major order
    """
    # Normalize to [0, 1]
    hmap = (heightmap - heightmap.min()) / (heightmap.max() - heightmap.min() + 1e-10)

    if flip_vertical:
        hmap = np.flipud(hmap)

    # Convert to uint16
    hmap_u16 = (hmap * 65535).astype(np.uint16)

    # Write as raw bytes (little-endian)
    with open(filepath, 'wb') as f:
        f.write(hmap_u16.tobytes())

    return {
        "filepath": filepath,
        "width": heightmap.shape[1],
        "height": heightmap.shape[0],
        "bit_depth": 16,
        "byte_order": "little-endian",
        "file_size": heightmap.shape[0] * heightmap.shape[1] * 2,
    }
```

### Cellular Automata Cave Generation (Pure-Logic)
```python
# Pure-logic: no bpy imports, fully testable
import random
import numpy as np
from collections import deque

def generate_cave_map(
    width: int = 64,
    height: int = 64,
    fill_probability: float = 0.45,
    iterations: int = 5,
    seed: int = 0,
) -> np.ndarray:
    """Generate cave map using cellular automata 4-5 rule.

    Returns 2D array: 0 = wall, 1 = floor.
    Guarantees single connected cave region via flood-fill.
    """
    rng = random.Random(seed)

    # Initialize random grid
    grid = np.zeros((height, width), dtype=np.int8)
    for y in range(height):
        for x in range(width):
            grid[y, x] = 1 if rng.random() > fill_probability else 0

    # Set borders to wall
    grid[0, :] = 0
    grid[-1, :] = 0
    grid[:, 0] = 0
    grid[:, -1] = 0

    # Apply cellular automata iterations
    for _ in range(iterations):
        new_grid = grid.copy()
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                neighbors = _count_neighbors(grid, x, y)
                if grid[y, x] == 0:  # wall
                    new_grid[y, x] = 0 if neighbors >= 4 else 1
                else:  # floor
                    new_grid[y, x] = 0 if neighbors >= 5 else 1
        grid = new_grid

    # Keep only largest connected region
    grid = _keep_largest_region(grid)
    return grid
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| noise library (caseman) | opensimplex 0.4.x | noise abandoned 2015 | noise incompatible with Python 3.12; opensimplex has numpy acceleration |
| Simplex noise (Perlin 2001) | OpenSimplex (2014+) | Patent expired 2022 but OpenSimplex remains cleaner | No patent risk; better isotropy than Perlin; similar performance |
| Per-object scatter | Collection instancing | Blender 2.8+ | 100x+ performance improvement for dense vegetation; single draw call per instance type |
| Vertex color terrain painting | Material slot per-face | Standard game practice | Direct export to Unity splatmap channels; no custom shader needed |
| Random room placement | BSP + corridor connection | Well-established since 2004 (RogueBasin) | Guarantees space efficiency and controllable room sizes |

**Deprecated/outdated:**
- `noise` package (PyPI): Last updated 2015, Python 3.4 max. Do not use.
- `mathutils.noise` for terrain: Runs only inside Blender; cannot unit test. Use opensimplex for all pure-logic noise.
- Blender Geometry Nodes for terrain: While powerful for interactive design, not scriptable via Python API in the way handlers need. Handler pattern requires imperative bmesh code.

## Open Questions

1. **Terrain resolution default**
   - What we know: 256x256 (65K vertices) is reasonable for preview; 512x512 (262K) for production. Unity Terrain requires power-of-two + 1 (257, 513, 1025).
   - What's unclear: Whether to match Unity's N+1 convention in Blender or export with resampling.
   - Recommendation: Generate at requested resolution, add a `unity_compat` flag that resizes to nearest power-of-two + 1 on export. Default resolution 129x129 for fast iteration.

2. **Building generation geometric complexity**
   - What we know: Grammar rules produce geometry operation lists. Each operation creates bmesh primitives.
   - What's unclear: Whether boolean operations for windows/doors will be reliable at scale, or if direct bmesh face construction (building walls with holes) is more robust.
   - Recommendation: Use direct bmesh construction for window/door openings (create wall faces around the opening) rather than boolean subtract. Reserve boolean ops for special cases only (ruins damage).

3. **Vegetation LOD in Blender**
   - What we know: CONTEXT.md mentions LOD0-LOD2 for trees. Phase 3 has pipeline_generate_lods handler.
   - What's unclear: Whether to generate LODs in this phase or rely on the existing LOD pipeline for post-processing.
   - Recommendation: Generate base vegetation geometry only. LODs handled by existing pipeline_generate_lods handler as a separate step. Document this as a recommended post-processing workflow.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 + pytest-asyncio >= 0.24.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_terrain_noise.py tests/test_terrain_erosion.py tests/test_dungeon_gen.py tests/test_building_grammar.py tests/test_scatter_engine.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENV-01 | Terrain heightmap generation with noise + erosion | unit | `pytest tests/test_terrain_noise.py tests/test_terrain_erosion.py -x` | No - Wave 0 |
| ENV-02 | Biome rule matching (slope/altitude) | unit | `pytest tests/test_terrain_noise.py::TestBiomeRules -x` | No - Wave 0 |
| ENV-03 | Cave system via cellular automata | unit | `pytest tests/test_dungeon_gen.py::TestCaveGeneration -x` | No - Wave 0 |
| ENV-04 | River path carving on heightmap | unit | `pytest tests/test_terrain_noise.py::TestRiverCarving -x` | No - Wave 0 |
| ENV-05 | Road path generation with grading | unit | `pytest tests/test_terrain_noise.py::TestRoadGeneration -x` | No - Wave 0 |
| ENV-06 | Water body creation | unit | `pytest tests/test_environment_handlers.py::TestWaterBody -x` | No - Wave 0 |
| ENV-07 | Vegetation scatter with biome rules | unit | `pytest tests/test_scatter_engine.py::TestVegetationScatter -x` | No - Wave 0 |
| ENV-08 | Building generation from grammar | unit | `pytest tests/test_building_grammar.py::TestBuildingGeneration -x` | No - Wave 0 |
| ENV-09 | Castle/tower/bridge templates | unit | `pytest tests/test_building_grammar.py::TestSpecializedTemplates -x` | No - Wave 0 |
| ENV-10 | Ruins damage application | unit | `pytest tests/test_building_grammar.py::TestRuinsDamage -x` | No - Wave 0 |
| ENV-11 | Town layout with districts/roads | unit | `pytest tests/test_dungeon_gen.py::TestTownLayout -x` | No - Wave 0 |
| ENV-12 | BSP dungeon layout with connectivity | unit | `pytest tests/test_dungeon_gen.py::TestBSPDungeon -x` | No - Wave 0 |
| ENV-13 | Interior furniture placement | unit | `pytest tests/test_building_grammar.py::TestInteriorGeneration -x` | No - Wave 0 |
| ENV-14 | Modular kit piece generation | unit | `pytest tests/test_building_grammar.py::TestModularKit -x` | No - Wave 0 |
| ENV-15 | Context-aware prop scatter | unit | `pytest tests/test_scatter_engine.py::TestContextScatter -x` | No - Wave 0 |
| ENV-16 | Breakable prop variants | unit | `pytest tests/test_scatter_engine.py::TestBreakableProps -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_terrain_noise.py tests/test_terrain_erosion.py tests/test_dungeon_gen.py tests/test_building_grammar.py tests/test_scatter_engine.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_terrain_noise.py` -- covers ENV-01, ENV-02, ENV-04, ENV-05
- [ ] `tests/test_terrain_erosion.py` -- covers ENV-01 erosion
- [ ] `tests/test_dungeon_gen.py` -- covers ENV-03, ENV-11, ENV-12
- [ ] `tests/test_building_grammar.py` -- covers ENV-08, ENV-09, ENV-10, ENV-13, ENV-14
- [ ] `tests/test_scatter_engine.py` -- covers ENV-07, ENV-15, ENV-16
- [ ] `tests/test_environment_handlers.py` -- integration tests for terrain/water handlers
- [ ] `tests/test_worldbuilding_handlers.py` -- integration tests for building/layout handlers
- [ ] `opensimplex>=0.4.5` added to pyproject.toml dependencies

## Sources

### Primary (HIGH confidence)
- [Blender bmesh.ops API](https://docs.blender.org/api/current/bmesh.ops.html) -- create_grid, subdivide_edges, extrude operations
- [opensimplex PyPI](https://pypi.org/project/opensimplex/) -- v0.4.5.1, May 2024, Python 3.8+, numpy-accelerated
- [Unity Heightmap Manual](https://docs.unity3d.com/Manual/terrain-Heightmaps.html) -- 16-bit RAW format, power-of-two dimensions
- [Unity Terrain Tools Import Heightmap](https://docs.unity3d.com/Packages/com.unity.terrain-tools@4.0/manual/toolbox-import-heightmap.html) -- r16 little-endian format spec
- Project codebase: handlers/__init__.py, objects.py, texture.py, blender_server.py -- established patterns

### Secondary (MEDIUM confidence)
- [RogueBasin BSP Dungeon Generation](https://www.roguebasin.com/index.php/Basic_BSP_Dungeon_generation) -- standard algorithm description, widely implemented
- [RogueBasin Cellular Automata Caves](https://www.roguebasin.com/index.php/Cellular_Automata_Method_for_Generating_Random_Cave-Like_Levels) -- 4-5 rule, fill probability 40-45%
- [Red Blob Games: Terrain from Noise](https://www.redblobgames.com/maps/terrain-from-noise/) -- fBm octave stacking, terrain feature shaping
- [terrain-erosion-3-ways (GitHub)](https://github.com/dandrino/terrain-erosion-3-ways) -- Python/numpy hydraulic + thermal erosion implementations
- [Simulating Hydraulic Erosion (Job Talle)](https://jobtalle.com/simulating_hydraulic_erosion.html) -- droplet-based erosion algorithm details
- [Prokitektura (GitHub)](https://github.com/nortikin/prokitektura-blender) -- grammar-based building generation for Blender

### Tertiary (LOW confidence)
- [pynoise 3.0.0 (PyPI)](https://pypi.org/project/pynoise/) -- alternative noise library; not recommended over opensimplex
- [noise (caseman) PyPI](https://pypi.org/project/noise/) -- v1.2.2, 2015, Python 3.4 only; DO NOT USE

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- opensimplex verified on PyPI (v0.4.5.1, May 2024); numpy already in deps; bmesh API well-documented and used extensively in Phases 1-5
- Architecture: HIGH -- follows established handler + pure-logic pattern from 5 prior phases; compound tool pattern proven with 13 existing tools
- Pitfalls: HIGH -- terrain/erosion edge cases well-documented in literature; BSP connectivity is a known requirement; scatter performance solved by instancing
- Algorithms: MEDIUM -- erosion and building grammar implementations need validation during development; standard algorithms but implementation details matter

**Research date:** 2026-03-19
**Valid until:** 2026-04-18 (30 days -- stable domain, no fast-moving dependencies)
