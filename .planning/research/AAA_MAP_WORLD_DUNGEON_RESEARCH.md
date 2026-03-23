# Deep Dive: AAA Map Generation, World Building, Dungeon Design & Environment Art

**Researched:** 2026-03-22
**Domain:** Terrain erosion, dungeon algorithms, city generation, vegetation systems, environmental storytelling, open-source tools
**Confidence:** HIGH (cross-referenced academic papers, GDC talks, open-source implementations, game postmortems)
**Target Stack:** Blender Python (procedural generation in `_terrain_noise.py`, `_dungeon_gen.py`, `worldbuilding_layout.py`) + Unity URP C# (runtime rendering)

---

## Table of Contents

1. [Terrain Generation (AAA Quality)](#1-terrain-generation-aaa-quality)
2. [Dungeon Generation (Beyond BSP)](#2-dungeon-generation-beyond-bsp)
3. [City/Town Generation](#3-citytown-generation)
4. [Vegetation Systems](#4-vegetation-systems)
5. [Environmental Storytelling](#5-environmental-storytelling)
6. [Open Source Tools & Libraries](#6-open-source-tools--libraries)
7. [Gap Analysis vs Current Toolkit](#7-gap-analysis-vs-current-toolkit)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. Terrain Generation (AAA Quality)

### 1.1 Hydraulic Erosion Algorithms

**Confidence:** HIGH (Sebastian Lague, Nick McDonald, Axel Paris implementations all verified)

Three distinct approaches exist, ordered by realism and cost:

#### A. Particle-Based (Drop) Simulation — RECOMMENDED FOR TOOLKIT

The simplest and most game-dev-friendly approach. Each "raindrop" particle:

1. Spawns at random position on heightmap
2. Computes gradient (slope) at current position
3. Moves downhill using classical mechanics: `velocity = velocity * inertia + gradient * (1 - inertia)`
4. Erodes terrain proportional to: `erosion_amount = max(0, sediment_capacity - current_sediment) * erosion_rate`
5. Deposits sediment when capacity is exceeded: `deposit_amount = (current_sediment - sediment_capacity) * deposition_rate`
6. Evaporates water each step: `water *= (1 - evaporation_rate)`
7. Dies when water depleted or lifetime exceeded

**Key Parameters:**
```
inertia          = 0.05   # How much old direction persists
erosion_rate     = 0.3    # Material pickup speed
deposition_rate  = 0.3    # Material dropout speed
evaporation_rate = 0.01   # Water loss per step
min_slope        = 0.01   # Minimum slope for capacity calculation
capacity_coeff   = 4.0    # sediment_capacity = max(slope, min_slope) * speed * water * capacity_coeff
gravity          = 4.0    # Acceleration due to gravity
max_lifetime     = 30     # Max steps per droplet
erosion_radius   = 3      # Radius of erosion/deposit brush
```

**Performance:** ~10-100 microseconds per particle. 200,000 particles on 512x512 terrain = 10-20 seconds. Numpy-vectorizable by batching particles.

**Python Implementation:** `github.com/keepitwiel/hydraulic-erosion-simulator` has a clean `src/algorithm.py`. Also `github.com/dandrino/terrain-erosion-3-ways` (Python 3.6 + numpy).

**Pseudocode for our toolkit:**
```python
def hydraulic_erode(heightmap: np.ndarray, num_drops: int = 100000,
                    erosion_rate: float = 0.3, deposition_rate: float = 0.3,
                    evaporation: float = 0.01, capacity_coeff: float = 4.0,
                    inertia: float = 0.05, gravity: float = 4.0,
                    max_life: int = 30, radius: int = 3,
                    seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    hmap = heightmap.copy().astype(np.float64)
    rows, cols = hmap.shape

    for _ in range(num_drops):
        # Spawn at random position
        px, py = rng.uniform(radius, cols - radius), rng.uniform(radius, rows - radius)
        dx, dy = 0.0, 0.0  # direction
        speed, water, sediment = 1.0, 1.0, 0.0

        for _ in range(max_life):
            ix, iy = int(px), int(py)
            if ix < 1 or ix >= cols-1 or iy < 1 or iy >= rows-1:
                break

            # Bilinear gradient
            gx, gy = _bilinear_gradient(hmap, px, py)
            # Update direction with inertia
            dx = dx * inertia - gx * (1 - inertia)
            dy = dy * inertia - gy * (1 - inertia)
            mag = math.sqrt(dx*dx + dy*dy)
            if mag > 0:
                dx /= mag; dy /= mag

            # Move
            px += dx; py += dy
            nix, niy = int(px), int(py)
            if nix < 1 or nix >= cols-1 or niy < 1 or niy >= rows-1:
                break

            # Height difference
            h_old = _bilinear_sample(hmap, ix + 0.5, iy + 0.5)
            h_new = _bilinear_sample(hmap, px, py)
            h_diff = h_new - h_old

            # Sediment capacity
            slope = max(-h_diff, 0.01)
            capacity = slope * speed * water * capacity_coeff

            if sediment > capacity or h_diff > 0:
                # Deposit
                amount = min(sediment, (sediment - capacity) * deposition_rate) if h_diff <= 0 else min(sediment, h_diff)
                sediment -= amount
                _deposit(hmap, px, py, amount, radius)
            else:
                # Erode
                amount = min((capacity - sediment) * erosion_rate, -h_diff)
                sediment += amount
                _erode(hmap, px, py, amount, radius)

            # Update speed and evaporate
            speed = math.sqrt(max(0, speed*speed + h_diff * gravity))
            water *= (1 - evaporation)

    return np.clip(hmap, 0, 1)
```

#### B. Grid-Based (Shallow Water) Simulation

Full fluid simulation on a grid. More realistic but 10-100x slower:
- Tracks water height, velocity, sediment per cell
- Uses Saint-Venant shallow water equations
- Produces realistic river networks, deltas, alluvial fans
- Best for offline preprocessing, not real-time

**Reference:** Stava et al. 2008, "Interactive Terrain Modeling Using Hydraulic Erosion"

#### C. Stream Power Law

Geomorphology-derived. Uses only drainage area and slope:
```
erosion_rate = K * A^m * S^n
```
Where A = upstream drainage area, S = slope, K/m/n are material parameters.

**Advantage:** Produces dendritic mountain ridgelines naturally. Very fast.
**Implementation:** `github.com/H-Schott/StreamPowerErosion` and `github.com/dandrino/terrain-erosion-3-ways` (the stream power example).

### 1.2 Thermal Erosion

**Confidence:** HIGH

Simulates rockfall/talus. Much simpler than hydraulic:

```python
def thermal_erode(heightmap: np.ndarray, iterations: int = 50,
                  talus_angle: float = 0.05, transfer_rate: float = 0.5) -> np.ndarray:
    hmap = heightmap.copy()
    rows, cols = hmap.shape
    for _ in range(iterations):
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dx == 0 and dy == 0: continue
                neighbor = np.roll(np.roll(hmap, -dy, axis=0), -dx, axis=1)
                diff = hmap - neighbor
                transfer = np.where(diff > talus_angle, diff * transfer_rate * 0.125, 0.0)
                hmap -= transfer
                # Note: simplified — proper impl accumulates into neighbor
    return np.clip(hmap, 0, 1)
```

**Key insight:** Thermal erosion produces plateau-and-slope terrain. Combined with hydraulic erosion, it creates realistic cliff faces with talus slopes at their bases. Run thermal first (defines coarse structure), then hydraulic (carves valleys and detail).

**GPU Portability:** Nearly identical to CPU version. Trivially parallelizable per-cell.

### 1.3 Multi-Octave Noise Layering

**Confidence:** HIGH (already implemented in toolkit `_terrain_noise.py`)

Current toolkit has fBm with 6 terrain presets. What's MISSING for AAA quality:

#### A. Ridged Multifractal Noise — CRITICAL GAP

Creates sharp mountain ridges. The "ridged" basis function:
```python
def ridged_noise(x, y, gen):
    return 1.0 - abs(gen.noise2(x, y))
```

Full ridged multifractal:
```python
def ridged_multifractal(x, y, gen, octaves=8, lacunarity=2.0,
                        gain=2.0, offset=1.0):
    value = 0.0
    weight = 1.0
    frequency = 1.0
    for _ in range(octaves):
        signal = ridged_noise(x * frequency, y * frequency, gen)
        signal = offset - signal  # Invert
        signal *= signal  # Square for sharper ridges
        signal *= weight
        weight = np.clip(signal * gain, 0, 1)  # Successive octave weighting
        value += signal * (1.0 / frequency)  # Amplitude decreases with frequency
        frequency *= lacunarity
    return value
```

**Why it matters:** Standard fBm produces rounded hills. Ridged multifractal produces the sharp, dramatic mountain ridges that define AAA dark fantasy landscapes (think Elden Ring's Mountaintops of the Giants).

#### B. Worley/Voronoi Noise — CRITICAL GAP

Creates cell-like patterns. Essential for:
- Rock formations with defined edges
- Cracked earth / dried mud flats
- Crystal formations
- Natural cell boundaries (hexagonal basalt columns)

```python
def worley_noise(x, y, seed=0, metric='euclidean'):
    """Returns distance to nearest feature point."""
    rng = np.random.RandomState(seed)
    # Grid cell
    ix, iy = int(np.floor(x)), int(np.floor(y))
    min_dist = float('inf')
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            # Feature point within cell
            cx, cy = ix + dx, iy + dy
            cell_seed = hash((cx, cy, seed)) & 0x7FFFFFFF
            cell_rng = np.random.RandomState(cell_seed)
            fx = cx + cell_rng.uniform()
            fy = cy + cell_rng.uniform()
            dist = math.sqrt((x - fx)**2 + (y - fy)**2)
            min_dist = min(min_dist, dist)
    return min_dist
```

Vectorized version using scipy.spatial.KDTree for batch processing is 100x faster.

#### C. Domain Warping — HIGH IMPACT

Distorts noise coordinates with another noise function to create organic, swirling terrain features:

```python
def domain_warp(x, y, gen, warp_scale=0.5, warp_freq=1.0):
    wx = gen.noise2(x * warp_freq + 100, y * warp_freq) * warp_scale
    wy = gen.noise2(x * warp_freq, y * warp_freq + 100) * warp_scale
    return x + wx, y + wy
```

Apply before heightmap generation:
```python
# In generate_heightmap, warp coordinates before noise sampling:
wx, wy = domain_warp(xs, ys, gen, warp_scale=2.0, warp_freq=0.3)
hmap += gen.noise2_array(wx * frequency, wy * frequency) * amplitude
```

**Result:** Breaks up the grid-aligned look of standard noise. Produces terrain that resembles real erosion patterns without actually simulating erosion. Very cheap.

### 1.4 Terrain Feature Generation

#### Cliffs and Mesas
Current toolkit has basic `step` post-processing. AAA approach:
- Generate noise heightmap
- Apply height quantization with smooth transitions at edges
- Use slope-dependent erosion: steep areas erode more
- Add noise-displaced vertical cliff faces

#### Valleys and Canyons
Current toolkit has basic `canyon` ridged inversion. Better approach:
- Use ridged multifractal as base
- Carve river channels using A* (already implemented) with widening based on upstream area
- Apply hydraulic erosion preferentially along channels
- Add meander noise to river paths

#### Waterfalls
Not yet implemented. Algorithm:
1. Detect sharp height drops along river paths (diff > threshold)
2. At waterfall point: widen channel, create plunge pool (circular depression)
3. Add mist particle emitter location marker
4. Carve undercut behind waterfall face

### 1.5 Biome Placement

**Current state:** Simple altitude + slope lookup table in `compute_biome_assignments()`.

**AAA approach — Whittaker Diagram:**

Use temperature + moisture as the two axes:

```python
# Temperature: decreases with altitude, varies with latitude
temperature = base_temp - altitude * lapse_rate + latitude_offset

# Moisture: simulate prevailing wind carrying moisture over terrain
moisture = simulate_wind_moisture(heightmap, wind_direction, base_moisture)

# Lookup biome from 2D table
WHITTAKER_TABLE = {
    # (temp_range, moisture_range): biome_name
    ((0.0, 0.2), (0.0, 0.3)): "tundra",
    ((0.0, 0.2), (0.3, 0.7)): "boreal_forest",
    ((0.2, 0.5), (0.0, 0.3)): "cold_desert",
    ((0.2, 0.5), (0.3, 0.6)): "temperate_forest",
    ((0.2, 0.5), (0.6, 1.0)): "temperate_rainforest",
    ((0.5, 0.8), (0.0, 0.3)): "grassland",
    ((0.5, 0.8), (0.3, 0.6)): "seasonal_forest",
    ((0.5, 0.8), (0.6, 1.0)): "tropical_forest",
    ((0.8, 1.0), (0.0, 0.3)): "hot_desert",
    ((0.8, 1.0), (0.3, 1.0)): "savanna",
}
```

**Moisture simulation (wind model):**
```python
def simulate_wind_moisture(heightmap, wind_dir=(1, 0), base_moisture=0.8):
    """Orographic precipitation: moisture decreases as wind crosses mountains."""
    moisture = np.full_like(heightmap, base_moisture)
    rows, cols = heightmap.shape

    # Scan in wind direction
    for r in range(rows):
        m = base_moisture
        for c in range(cols):
            altitude = heightmap[r, c]
            # Moisture loss proportional to altitude (rain shadow)
            rain = min(m, altitude * 0.3)
            moisture[r, c] = m
            m -= rain
            m = max(0, m)
            # Moisture recovery over water/flat terrain
            if altitude < 0.1:  # "water level"
                m = min(m + 0.1, base_moisture)
    return moisture
```

### 1.6 Terrain Texture Splatmapping

**Current state:** Biome assignment generates per-cell indices. No splatmap generation.

**AAA height-based blending:**

Standard splatmap uses RGBA channels (4 layers per splatmap). Height-based blending adds a depth map per texture to avoid mushy linear blending:

```python
def height_blend_splatmap(weights: np.ndarray, height_maps: list[np.ndarray],
                          blend_sharpness: float = 0.1) -> np.ndarray:
    """
    weights: (H, W, N) array of per-layer weights from biome rules
    height_maps: list of N (H, W) arrays — texture height/depth maps
    Returns: (H, W, N) blended weights
    """
    combined = np.zeros_like(weights)
    for i in range(weights.shape[2]):
        combined[:, :, i] = weights[:, :, i] + height_maps[i] * blend_sharpness

    # Winner-take-most: for each pixel, boost the highest combined value
    max_vals = np.max(combined, axis=2, keepdims=True)
    mask = combined >= (max_vals - blend_sharpness)
    result = np.where(mask, weights, 0.0)

    # Renormalize
    total = np.sum(result, axis=2, keepdims=True)
    total = np.where(total > 0, total, 1.0)
    return result / total
```

### 1.7 Virtual Texturing / Megatexture

**Concept:** Single enormous unique texture for entire terrain, streamed in tiles based on camera distance.

**Implementation levels:**
1. **Basic (implementable now):** Generate unique splatmap per terrain chunk. Export as texture atlas.
2. **Advanced (Unity runtime):** Procedural Virtual Texture — render near terrain at high res, far at low res. Unity's `RenderGraph` API can do this with custom `ScriptableRendererFeature`.
3. **Full megatexture (id Tech 5 style):** Not practical for our toolkit scope.

**Recommendation:** Focus on generating high-quality splatmaps in Blender that export cleanly to Unity terrain system. Unity's built-in terrain already handles LOD texturing.

---

## 2. Dungeon Generation (Beyond BSP)

### 2.1 Wave Function Collapse (WFC)

**Confidence:** HIGH (Maxim Gumin's original, plus Boris the Brave's analysis)

WFC is a constraint-solving algorithm that generates patterns by propagating adjacency constraints. Perfect for tile-based dungeon layouts.

**Core Algorithm:**
```python
@dataclass
class WFCCell:
    possible_tiles: set[int]  # Set of tile IDs still valid
    collapsed: bool = False
    chosen_tile: int = -1

def wfc_generate(width: int, height: int, adjacency_rules: dict,
                 tile_weights: dict, seed: int = 0) -> np.ndarray:
    """
    adjacency_rules: {tile_id: {direction: set_of_valid_neighbors}}
    tile_weights: {tile_id: float}  # Higher = more likely to be chosen
    """
    rng = np.random.RandomState(seed)
    all_tiles = set(tile_weights.keys())
    grid = [[WFCCell(possible_tiles=set(all_tiles)) for _ in range(width)]
            for _ in range(height)]
    result = np.full((height, width), -1, dtype=np.int32)

    while True:
        # 1. Find cell with minimum entropy (fewest possibilities)
        min_entropy = float('inf')
        min_cell = None
        for y in range(height):
            for x in range(width):
                cell = grid[y][x]
                if cell.collapsed:
                    continue
                entropy = len(cell.possible_tiles)
                if entropy == 0:
                    return None  # Contradiction — backtrack or restart
                # Add small random noise to break ties
                entropy += rng.uniform(0, 0.1)
                if entropy < min_entropy:
                    min_entropy = entropy
                    min_cell = (x, y)

        if min_cell is None:
            break  # All collapsed

        # 2. Collapse: choose a tile weighted by frequency
        x, y = min_cell
        cell = grid[y][x]
        choices = list(cell.possible_tiles)
        weights = np.array([tile_weights.get(t, 1.0) for t in choices])
        weights /= weights.sum()
        chosen = rng.choice(choices, p=weights)
        cell.collapsed = True
        cell.chosen_tile = chosen
        cell.possible_tiles = {chosen}
        result[y, x] = chosen

        # 3. Propagate constraints
        _wfc_propagate(grid, x, y, width, height, adjacency_rules)

    return result

def _wfc_propagate(grid, start_x, start_y, width, height, rules):
    """Propagate constraints from a collapsed cell to neighbors."""
    stack = [(start_x, start_y)]
    directions = [(0, -1, 'up'), (0, 1, 'down'), (-1, 0, 'left'), (1, 0, 'right')]
    opposite = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}

    while stack:
        cx, cy = stack.pop()
        current_tiles = grid[cy][cx].possible_tiles

        for dx, dy, direction in directions:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            neighbor = grid[ny][nx]
            if neighbor.collapsed:
                continue

            # Compute valid tiles for neighbor based on current cell's possibilities
            valid = set()
            for tile in current_tiles:
                if direction in rules.get(tile, {}):
                    valid |= rules[tile][direction]

            # Restrict neighbor's possibilities
            new_possible = neighbor.possible_tiles & valid
            if new_possible != neighbor.possible_tiles:
                neighbor.possible_tiles = new_possible
                stack.append((nx, ny))
```

**Tile Set Design for Dark Fantasy Dungeons:**
```python
DUNGEON_TILES = {
    0: "empty",
    1: "floor",
    2: "wall_n", 3: "wall_s", 4: "wall_e", 5: "wall_w",
    6: "corner_ne", 7: "corner_nw", 8: "corner_se", 9: "corner_sw",
    10: "corridor_ns", 11: "corridor_ew",
    12: "t_junction_n", 13: "t_junction_s", 14: "t_junction_e", 15: "t_junction_w",
    16: "crossroads",
    17: "room_center",
    18: "door_ns", 19: "door_ew",
    20: "stairs_up", 21: "stairs_down",
    22: "pillar",
    23: "altar",
    24: "trap_floor",
}
```

**Advantages over BSP:** Produces more organic, varied layouts. Can encode architectural style rules. Supports modular kit piece placement directly.

**Disadvantages:** Can fail (contradiction). Needs backtracking or multiple attempts. Slower than BSP for large maps.

### 2.2 Cyclic Dungeon Generation (Unexplored Algorithm)

**Confidence:** HIGH (Joris Dormans' GDC talk, Boris the Brave's analysis, Sersa Victory's implementation)

The most sophisticated dungeon generation algorithm for gameplay quality. Used in Unexplored (2017).

**Core Concept:** Dungeons are composed of CYCLES — circular loops of rooms. Each cycle creates a gameplay pattern.

**Cycle Types (Unexplored has 24, here are the essential ones):**

1. **Lock-and-Key Cycle:** Path A is blocked by a lock. Path B leads to the key. Player must take B first, then A.
2. **Shortcut Cycle:** Path A is the long way. Path B is a one-way shortcut back (FROM goal TO entrance). Classic Dark Souls design.
3. **Hazard Cycle:** Path A has an environmental hazard. Path B has the tool to bypass it.
4. **Guard Cycle:** Path A is guarded by a miniboss. Path B provides an optional power-up to make the fight easier.
5. **Secret Cycle:** Path B is hidden. Only observant players find it.

**Algorithm:**
```python
@dataclass
class CyclicNode:
    id: int
    room_type: str  # "entrance", "goal", "key", "lock", "shortcut", "secret"
    connections: list[int] = field(default_factory=list)
    position: tuple[int, int] = (0, 0)

def generate_cyclic_dungeon(num_cycles: int = 5, seed: int = 0) -> list[CyclicNode]:
    rng = random.Random(seed)
    nodes = []
    node_id = 0

    # 1. Start with entrance and goal
    entrance = CyclicNode(id=node_id, room_type="entrance"); node_id += 1
    goal = CyclicNode(id=node_id, room_type="goal"); node_id += 1
    nodes.extend([entrance, goal])

    # 2. Create major cycle connecting entrance to goal
    path_a_len = rng.randint(3, 6)
    path_b_len = rng.randint(2, 4)

    path_a = [entrance]
    for _ in range(path_a_len):
        n = CyclicNode(id=node_id, room_type="generic"); node_id += 1
        path_a[-1].connections.append(n.id)
        n.connections.append(path_a[-1].id)
        nodes.append(n)
        path_a.append(n)
    path_a[-1].connections.append(goal.id)
    goal.connections.append(path_a[-1].id)

    path_b = [entrance]
    for _ in range(path_b_len):
        n = CyclicNode(id=node_id, room_type="generic"); node_id += 1
        path_b[-1].connections.append(n.id)
        n.connections.append(path_b[-1].id)
        nodes.append(n)
        path_b.append(n)
    path_b[-1].connections.append(goal.id)
    goal.connections.append(path_b[-1].id)

    # 3. Apply cycle pattern (e.g., lock-and-key)
    # Place lock on path_a, key on path_b
    if len(path_a) > 2:
        lock_node = path_a[len(path_a) // 2]
        lock_node.room_type = "lock"
    if len(path_b) > 1:
        key_node = path_b[-1]  # Key before reaching goal via path_b
        key_node.room_type = "key"

    # 4. Add sub-cycles for additional complexity
    for _ in range(num_cycles - 1):
        # Pick random node to branch from
        base = rng.choice([n for n in nodes if n.room_type == "generic"])
        cycle_type = rng.choice(["shortcut", "secret", "guard", "hazard"])
        _add_sub_cycle(nodes, base, cycle_type, rng, node_id)
        node_id += rng.randint(2, 4)

    return nodes
```

**Spatial Layout:** After generating the graph, lay it out on a 2D grid:
1. Place entrance at center
2. BFS outward, placing rooms at grid cells
3. Corridors follow graph edges
4. Use spring-based layout or force-directed placement to minimize crossings

### 2.3 Graph-Based Key-Lock Puzzles (Metazelda)

**Confidence:** HIGH (tcoxon/metazelda on GitHub, academic papers)

Metazelda algorithm:
1. Track "access level" — which keys the player has at each point
2. Generate spanning tree of rooms
3. At each branch, decide: place a new lock (raising required access level) or leave open
4. Place corresponding key in a room reachable at the PREVIOUS access level
5. "Graphify" — add extra connections between rooms to create non-linear paths

**Key insight:** The lock placement creates a directed acyclic graph of progression, while the extra connections create loops for exploration.

```python
def add_key_lock(graph, room_a, room_b, current_level):
    """Insert a key-lock pair between two rooms."""
    # Lock goes on the edge from room_a to room_b
    graph.edges[room_a][room_b]['lock_level'] = current_level + 1
    # Key goes somewhere reachable from entrance at current_level
    reachable = get_reachable_rooms(graph, current_level)
    key_room = random.choice(reachable)
    key_room.items.append(f'key_{current_level + 1}')
    return current_level + 1
```

### 2.4 Cellular Automata Caves — ALREADY IMPLEMENTED, NEEDS REFINEMENT

**Current state:** `_dungeon_gen.py` has `generate_cave_map()`.

**Enhancements needed:**
1. **Pillar generation pass:** After standard 4-5 rule, add rule: if a floor cell has 0 wall neighbors in 3x3, make it wall. Reduces vast open spaces.
2. **Region connectivity:** Flood fill to find disconnected regions. Connect them via shortest-path tunnels.
3. **Stalactite/stalagmite placement:** At ceiling/floor cells adjacent to walls, randomly place decorative markers.
4. **Water pools:** At local height minima of the cave floor, mark water regions.

### 2.5 Multi-Floor Dungeon Strategies

**Current state:** `generate_multi_floor_dungeon()` exists in toolkit.

**AAA-quality enhancements:**

1. **Staircase geometry:** A staircase needs both horizontal AND vertical space. Rise:run ratio 1:2. Must clear 2 cells of headroom above each step.
2. **3D Delaunay connection:** Generate room positions in 3D, tetrahedralize, use MST + extra edges for vertical connections.
3. **Vertical types:**
   - Spiral staircases (compact, fits in 3x3 cell footprint)
   - Pits/drops (one-way down, Dark Souls style)
   - Elevators/platforms (two-way, requires mechanism)
   - Ladders (one-way up, slow)
   - Collapsed floors (surprise drop to lower level)

4. **Floor difficulty scaling:** Floor N+1 has stronger enemies. Boss every 3-5 floors.

### 2.6 Secret Room Placement

**Algorithm:**
```python
def place_secret_rooms(layout: DungeonLayout, num_secrets: int = 3,
                       seed: int = 0) -> list[dict]:
    """Place secret rooms adjacent to existing rooms with hidden connections."""
    rng = random.Random(seed)
    secrets = []
    grid = layout.grid

    for _ in range(num_secrets):
        # Find wall cells adjacent to exactly one floor cell
        candidates = []
        for y in range(1, grid.shape[0] - 1):
            for x in range(1, grid.shape[1] - 1):
                if grid[y, x] != 0:  # Must be wall
                    continue
                floor_neighbors = sum(1 for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]
                                     if grid[y+dy, x+dx] == 1)
                if floor_neighbors == 1:
                    # Check there's space to carve a room behind this wall
                    # (at least 3x3 clear area on the opposite side)
                    candidates.append((x, y))

        if not candidates:
            break

        sx, sy = rng.choice(candidates)
        # Determine direction away from floor
        # Carve 3x3 to 5x5 room in that direction
        secrets.append({
            "type": "secret_room",
            "entrance": (sx, sy),
            "trigger": "illusory_wall",  # or "hidden_lever", "bomb_wall"
            "contents": rng.choice(["treasure", "lore", "shortcut", "merchant"]),
        })
    return secrets
```

### 2.7 Boss Arena Design Rules

**Confidence:** HIGH (Level Design Book, GDC talks, FromSoftware analysis)

**Algorithmic arena generation:**
```python
def generate_boss_arena(arena_type: str, size: float = 30.0, seed: int = 0) -> dict:
    """Generate boss arena layout with cover, phases, and escape routes."""
    rng = random.Random(seed)

    arena = {
        "shape": "circular" if arena_type in ["demon", "beast"] else "rectangular",
        "radius": size / 2 if arena_type != "rectangular" else None,
        "width": size, "height": size,
        "fog_gate": {"position": (0, -size/2), "width": 3.0},
        "cover_points": [],
        "phase_triggers": [],
        "hazard_zones": [],
        "pillars": [],
    }

    # COVER PLACEMENT RULES:
    # 1. Minimum 4 cover points, distributed evenly around perimeter
    # 2. No cover within 5m of arena center (boss domain)
    # 3. Cover must not block line-of-sight between ANY two other cover points
    #    (prevents camping)
    num_cover = rng.randint(4, 8)
    for i in range(num_cover):
        angle = (2 * math.pi * i / num_cover) + rng.uniform(-0.3, 0.3)
        r = size * 0.35 + rng.uniform(0, size * 0.1)
        arena["cover_points"].append({
            "position": (math.cos(angle) * r, math.sin(angle) * r),
            "type": rng.choice(["pillar", "rubble", "statue", "altar"]),
            "destructible": rng.random() < 0.3,
        })

    # PHASE TRIGGERS (circular zones that activate at boss HP thresholds):
    arena["phase_triggers"] = [
        {"hp_threshold": 0.75, "effect": "add_hazard", "zone_radius": size * 0.3},
        {"hp_threshold": 0.50, "effect": "destroy_cover", "count": 2},
        {"hp_threshold": 0.25, "effect": "enrage", "arena_shrink": 0.8},
    ]

    # HAZARD ZONES:
    if arena_type == "volcanic":
        arena["hazard_zones"] = [
            {"type": "lava_pool", "position": (rng.uniform(-5, 5), rng.uniform(-5, 5)),
             "radius": 3.0, "damage_per_sec": 10}
            for _ in range(rng.randint(2, 4))
        ]

    return arena
```

**Key Design Rules (from FromSoftware analysis):**
1. Arena should be visible in its entirety upon entry (sense of scope)
2. Architecturally simple — no complex geometry to get stuck on during combat
3. Phase transitions can alter the arena (destroy pillars, open new areas, flood with hazard)
4. Multiple movement routes around the boss (non-linear)
5. No dead ends — player must always have an escape route
6. Vertical variation optional but powerful (elevated platforms for ranged attacks)

---

## 3. City/Town Generation

### 3.1 L-System Road Networks

**Confidence:** HIGH (Parish & Mueller 2001, CityEngine, multiple implementations)

L-systems generate road networks through string rewriting rules:

```python
# Simple road L-system
AXIOMS = {
    "organic": "F",  # Medieval organic growth
    "grid": "F+F+F+F",  # Manhattan grid
    "radial": "F[+F][-F]",  # Radial spokes
}

RULES = {
    "organic": {
        "F": "F[+FF][-F]F",  # Branch with randomization
    },
    "grid": {
        "F": "FF+F+F-F-FF",
    },
}

def apply_lsystem(axiom: str, rules: dict, iterations: int = 4,
                  angle: float = 90, step: float = 10,
                  rng=None) -> list[tuple[Vec2, Vec2]]:
    """Generate road segments from L-system rules."""
    string = axiom
    for _ in range(iterations):
        new = ""
        for ch in string:
            if ch in rules:
                new += rules[ch]
            else:
                new += ch
        string = new

    # Turtle interpretation
    segments = []
    x, y, heading = 0.0, 0.0, 0.0
    stack = []

    for ch in string:
        if ch == 'F':
            nx = x + step * math.cos(math.radians(heading))
            ny = y + step * math.sin(math.radians(heading))
            segments.append(((x, y), (nx, ny)))
            x, y = nx, ny
        elif ch == '+':
            heading += angle + (rng.uniform(-15, 15) if rng else 0)
        elif ch == '-':
            heading -= angle + (rng.uniform(-15, 15) if rng else 0)
        elif ch == '[':
            stack.append((x, y, heading))
        elif ch == ']':
            x, y, heading = stack.pop()

    return segments
```

**For medieval towns:** Use the organic axiom with angle randomization (70-110 degrees instead of fixed 90). Add terrain-following: roads prefer low slopes, avoid water.

### 3.2 Agent-Based City Growth

**Confidence:** HIGH (Northwestern LUTI model, multiple papers)

Three agent types simulate realistic city growth:

```python
class CityGrowthSimulation:
    def __init__(self, terrain, seed=0):
        self.terrain = terrain
        self.rng = random.Random(seed)
        self.roads = set()  # (x, y) cells
        self.buildings = []  # {type, position, size}
        self.districts = []  # {type, center, radius}

    def step(self):
        """One growth step."""
        # 1. Road Builder Agent: extend existing roads
        self._extend_roads()
        # 2. Connector Agent: link nearby road endpoints
        self._connect_roads()
        # 3. Builder Agent: place buildings along roads
        self._place_buildings()

    def _extend_roads(self):
        """Extend roads toward unserviced territory."""
        for endpoint in self._road_endpoints():
            # Prefer directions with high population potential
            # Avoid steep terrain and water
            best_dir = self._best_growth_direction(endpoint)
            if best_dir:
                self._grow_road(endpoint, best_dir)

    def _place_buildings(self):
        """Place buildings on lots adjacent to roads."""
        for road_cell in self.roads:
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                lot = (road_cell[0]+dx, road_cell[1]+dy)
                if lot not in self.roads and self._is_buildable(lot):
                    btype = self._determine_building_type(lot)
                    self.buildings.append({
                        "type": btype,
                        "position": lot,
                        "size": self._building_size(btype),
                    })
```

### 3.3 District Zoning

**Algorithm for medieval fantasy:**
```python
DISTRICT_TYPES = {
    "market": {"center_bias": 0.9, "road_access": "high", "building_types": ["shop", "stall", "inn"]},
    "residential": {"center_bias": 0.5, "road_access": "medium", "building_types": ["house", "apartment"]},
    "noble": {"center_bias": 0.7, "road_access": "high", "building_types": ["manor", "garden", "chapel"]},
    "industrial": {"center_bias": 0.2, "road_access": "medium", "building_types": ["forge", "tannery", "mill"]},
    "slums": {"center_bias": 0.1, "road_access": "low", "building_types": ["shack", "lean_to"]},
    "religious": {"center_bias": 0.6, "road_access": "high", "building_types": ["temple", "cemetery", "monastery"]},
    "military": {"center_bias": 0.3, "road_access": "high", "building_types": ["barracks", "armory", "training_ground"]},
}
```

Use Voronoi tessellation seeded with district center points (already partially implemented in `_dungeon_gen.py`'s `TownLayout`).

### 3.4 Building Lot Subdivision

**Confidence:** HIGH (Vanegas et al. 2012, Martin Devans' tutorial)

**OBB Recursive Subdivision:**
```python
def subdivide_lot(polygon, min_area=50, max_aspect_ratio=3.0, rng=None):
    """Recursively divide a polygon into building lots."""
    if polygon_area(polygon) < min_area:
        return [polygon]

    # Compute OBB (oriented bounding box)
    obb = compute_obb(polygon)
    if obb.aspect_ratio > max_aspect_ratio:
        return [polygon]  # Too thin to subdivide

    # Split along longest axis
    axis = obb.longest_axis
    split_point = 0.4 + (rng.random() * 0.2 if rng else 0.5)  # 40-60% split
    left, right = split_polygon(polygon, axis, split_point)

    return subdivide_lot(left, min_area, max_aspect_ratio, rng) + \
           subdivide_lot(right, min_area, max_aspect_ratio, rng)
```

**Key constraint:** Every lot must have one edge touching a street. The skeleton-based subdivision algorithm guarantees this.

### 3.5 Fortification Generation

**Medieval castle wall placement algorithm:**
```python
def generate_fortifications(town_boundary: list[Vec2], num_towers: int = 8,
                            gate_positions: list[str] = None, seed: int = 0) -> dict:
    """Generate walls, towers, and gates around a town."""
    rng = random.Random(seed)

    # 1. Compute convex hull of town boundary (or use as-is for irregular walls)
    wall_path = convex_hull(town_boundary)

    # 2. Place towers at corners and regular intervals
    towers = []
    perimeter = path_length(wall_path)
    tower_spacing = perimeter / num_towers

    current_dist = 0
    for i, (p1, p2) in enumerate(pairwise(wall_path)):
        seg_len = distance(p1, p2)
        while current_dist < seg_len:
            t = current_dist / seg_len
            pos = lerp(p1, p2, t)
            tower_type = rng.choice(["round", "d_shaped", "square"])
            towers.append({
                "position": pos,
                "type": tower_type,
                "radius": 3.0 + rng.uniform(0, 1),
            })
            current_dist += tower_spacing
        current_dist -= seg_len

    # 3. Place gates (typically 2-4, facing major roads)
    gates = []
    if gate_positions is None:
        gate_positions = ["north", "south"]
    for direction in gate_positions:
        # Find wall segment closest to direction
        gate_pos = find_wall_point_in_direction(wall_path, direction)
        gates.append({
            "position": gate_pos,
            "type": "gatehouse",
            "portcullis": True,
            "width": 4.0,
        })

    return {"wall_path": wall_path, "towers": towers, "gates": gates}
```

**Tower shape rules (historical accuracy):**
- **Round towers:** Best siege resistance. Use for corners and exposed positions.
- **D-shaped towers:** Compromise — flat interior wall for rooms, round exterior for defense.
- **Square towers:** Cheapest to build. Use for less exposed positions.
- **Tower spacing:** Must be within arrow range of adjacent towers (~30-50m). No blind spots along wall.

### 3.6 Market/Plaza Generation

```python
def generate_plaza(center: Vec2, size: float = 20.0, seed: int = 0) -> dict:
    """Generate a market plaza with stalls, fountain, and surrounding buildings."""
    rng = random.Random(seed)
    plaza = {
        "center": center,
        "shape": rng.choice(["square", "rectangular", "irregular"]),
        "size": size,
        "features": [],
    }

    # Central feature (fountain, well, gallows, statue)
    plaza["features"].append({
        "type": rng.choice(["fountain", "well", "statue", "market_cross"]),
        "position": center,
    })

    # Market stalls around perimeter
    num_stalls = rng.randint(6, 12)
    for i in range(num_stalls):
        angle = 2 * math.pi * i / num_stalls
        r = size * 0.35
        plaza["features"].append({
            "type": "market_stall",
            "position": (center[0] + r * math.cos(angle),
                        center[1] + r * math.sin(angle)),
            "rotation": math.degrees(angle) + 90,  # Face inward
            "goods": rng.choice(["food", "weapons", "potions", "armor", "trinkets"]),
        })

    return plaza
```

---

## 4. Vegetation Systems

### 4.1 L-System Tree Generation

**Confidence:** HIGH (Lindenmayer 1968, Modular Tree addon, tree-gen project)

**Parametric L-System for dark fantasy trees:**
```python
TREE_SPECIES = {
    "dead_oak": {
        "axiom": "F",
        "rules": {"F": "FF+[+F-F-F]-[-F+F+F]"},
        "angle": 25,
        "iterations": 4,
        "branch_radius_decay": 0.7,
        "leaf_probability": 0.1,  # Mostly bare
        "gnarled": True,
    },
    "dark_pine": {
        "axiom": "F",
        "rules": {"F": "F[+F][-F]F[+F][-F]"},
        "angle": 35,
        "iterations": 5,
        "branch_radius_decay": 0.65,
        "leaf_probability": 0.8,
        "needle_type": True,
    },
    "weeping_willow": {
        "axiom": "F",
        "rules": {"F": "FF[-F++F][+F--F]"},
        "angle": 20,
        "iterations": 5,
        "branch_radius_decay": 0.6,
        "leaf_probability": 0.9,
        "drooping": True,
    },
    "twisted_swamp": {
        "axiom": "F",
        "rules": {"F": "F[&+F]F[&-F]+F"},
        "angle": 30,
        "iterations": 4,
        "branch_radius_decay": 0.55,
        "gnarled": True,
        "moss_coverage": 0.6,
    },
}
```

**Blender implementation approach:**
1. Generate L-system string
2. Interpret as edges (skeleton)
3. Apply Blender Skin modifier for branch volume
4. Convert to mesh
5. Decimate for LOD variants
6. Scatter leaf instances on branch endpoints

**Reference implementations:**
- `github.com/friggog/tree-gen` — Blender addon, full L-system with skin modifier
- Modular Tree addon — biologically-inspired with apical dominance
- EZ Tree — lightweight Python, Apache 2.0, outputs .obj files

### 4.2 Grass/Foliage Instancing

**For Blender generation:**
- Use geometry nodes `Scatter on Surface` (native in Blender 5.0)
- Poisson disk sampling for natural distribution (avoid clumping)
- Distance-based density falloff from camera

**For Unity runtime:**
- GPU Instancing with compute shader culling
- Each blade = quadratic Bezier curve, 3-7 vertices
- Frustum + distance culling in compute shader
- LOD: reduce blade vertex count at distance, then billboard

**Performance targets:** ~1 million blades at stable 60fps with GPU instancing + culling.

### 4.3 Biome-Specific Plant Palettes

```python
DARK_FANTASY_BIOMES = {
    "dead_forest": {
        "trees": ["dead_oak", "dead_birch", "twisted_elm"],
        "ground": ["dead_grass", "fallen_leaves", "mushrooms", "moss_patches"],
        "features": ["fallen_logs", "stumps", "spider_webs"],
        "density": 0.6,
        "color_palette": [(0.15, 0.12, 0.08), (0.25, 0.20, 0.12), (0.10, 0.10, 0.08)],
    },
    "cursed_swamp": {
        "trees": ["twisted_swamp", "mangrove", "cypress"],
        "ground": ["mud", "swamp_grass", "bioluminescent_mushrooms", "lily_pads"],
        "features": ["fog", "standing_water", "rotting_wood", "hanging_moss"],
        "density": 0.4,
        "color_palette": [(0.08, 0.15, 0.05), (0.12, 0.10, 0.06), (0.05, 0.20, 0.10)],
    },
    "volcanic_waste": {
        "trees": ["charred_trunk", "petrified_tree"],
        "ground": ["ash", "obsidian_shards", "lava_cracks", "dead_scrub"],
        "features": ["fumaroles", "lava_pools", "volcanic_rock"],
        "density": 0.1,
        "color_palette": [(0.10, 0.08, 0.08), (0.30, 0.10, 0.05), (0.05, 0.05, 0.05)],
    },
    "frozen_tundra": {
        "trees": ["stunted_pine", "ice_covered_birch"],
        "ground": ["snow", "frozen_grass", "lichen", "ice_patches"],
        "features": ["ice_crystals", "frozen_corpses", "snow_drifts"],
        "density": 0.2,
        "color_palette": [(0.85, 0.90, 0.95), (0.15, 0.20, 0.25), (0.40, 0.45, 0.50)],
    },
    "corrupted_forest": {
        "trees": ["corruption_oak", "pulsing_tree", "crystal_growth"],
        "ground": ["corrupted_soil", "void_moss", "crystal_shards", "black_flowers"],
        "features": ["corruption_veins", "floating_debris", "distortion_zones"],
        "density": 0.7,
        "color_palette": [(0.20, 0.05, 0.30), (0.10, 0.00, 0.15), (0.30, 0.10, 0.40)],
    },
}
```

### 4.4 Tree LOD Strategy

**4-tier LOD chain:**
```
LOD0: Full mesh (500-5000 tris) — distance 0-30m
LOD1: Simplified mesh (100-500 tris) — distance 30-80m
LOD2: Cross-quad impostor (8 tris, 4 billboard planes) — distance 80-200m
LOD3: Single billboard (2 tris) — distance 200m+
```

**Cross-quad impostor generation (in Blender):**
1. Render tree from 4 orthogonal angles (front, back, left, right)
2. Create texture atlas from 4 renders (include alpha)
3. Create 2 intersecting planes (cross pattern)
4. Map each quadrant of atlas to corresponding plane face
5. Export as separate mesh for LOD2

**Octahedron impostors (advanced, Unity runtime):**
- Render from 8+ angles on octahedron hemisphere
- Store in atlas
- Shader interpolates between nearest 3 views based on camera angle
- Used in Fortnite for millions of trees

### 4.5 Procedural Ivy/Vine Growth

**Algorithm (based on IvyGen):**
```python
def grow_ivy(surface_mesh, start_point, max_length=100, seed=0):
    """Grow ivy along a mesh surface using physics-inspired rules."""
    rng = random.Random(seed)
    nodes = [start_point]
    directions = [Vec3(0, 0, 1)]  # Initial growth direction (up)

    adhesion_weight = 0.7  # Stick to surface
    gravity_weight = 0.3   # Pull down
    random_weight = 0.2    # Random wander

    for _ in range(max_length):
        current = nodes[-1]
        current_dir = directions[-1]

        # Compute growth direction
        surface_normal = get_closest_surface_normal(surface_mesh, current)
        gravity_dir = Vec3(0, 0, -1)
        random_dir = random_unit_vector(rng)

        # Weighted combination
        new_dir = normalize(
            current_dir * 0.5 +
            surface_normal * adhesion_weight +
            gravity_dir * gravity_weight +
            random_dir * random_weight
        )

        # Project onto surface
        new_point = current + new_dir * step_size
        snapped = snap_to_surface(surface_mesh, new_point, max_distance=1.0)

        if snapped is None:
            break  # Lost contact with surface

        nodes.append(snapped)
        directions.append(new_dir)

        # Branching
        if rng.random() < 0.1 and len(nodes) > 10:
            branch_dir = rotate(new_dir, rng.uniform(-45, 45))
            # Recursively grow branch (with reduced max_length)

    return nodes  # List of points defining ivy path
```

---

## 5. Environmental Storytelling

### 5.1 FromSoftware Design Principles

**Confidence:** HIGH (multiple GDC talks, game analysis articles)

**Key principles for procedural implementation:**

1. **Every prop tells a micro-story.** A skeleton's pose implies how they died. A broken weapon implies a failed battle. An open book implies interrupted study.

2. **Escalation through environment.** As player approaches a boss:
   - Increasing damage to architecture
   - More enemy corpses (including player's own faction)
   - Warning signs (blood trails, scratch marks)
   - Narrowing paths (increased tension)
   - Environmental hazards increase

3. **Interconnected shortcuts.** The environment doubles back on itself. After a long path forward, a shortcut opens back to a safe area. This creates the "aha!" moment.

4. **Vertical storytelling.** You can see where you're going before you get there (looking down into a valley) or see where you've been (looking up at a castle you already cleared).

### 5.2 Procedural Prop Placement for Narrative

```python
NARRATIVE_VIGNETTES = {
    "failed_adventurer": {
        "props": ["skeleton_sitting", "backpack", "broken_sword", "empty_potion"],
        "arrangement": "skeleton against wall, gear scattered nearby",
        "placement_rules": {
            "skeleton_sitting": {"against_wall": True, "facing": "entrance"},
            "backpack": {"distance_from_skeleton": 0.5, "on_ground": True},
            "broken_sword": {"distance_from_skeleton": 1.0, "random_rotation": True},
            "empty_potion": {"distance_from_skeleton": 0.3, "on_ground": True},
        },
    },
    "last_stand": {
        "props": ["skeleton_lying", "shield", "sword_in_ground", "enemy_corpse_x3"],
        "arrangement": "defender surrounded by enemies, sword planted as last defiance",
        "placement_rules": {
            "skeleton_lying": {"center": True},
            "shield": {"distance": 0.5, "facing_away": True},
            "sword_in_ground": {"distance": 0.3, "upright": True},
            "enemy_corpse_x3": {"ring_around": True, "radius": 2.0},
        },
    },
    "interrupted_ritual": {
        "props": ["candles_x5", "ritual_circle", "open_book", "blood_splatter", "corpse_robed"],
        "arrangement": "ritual circle with candles, interrupted by violence",
    },
    "trapped_explorer": {
        "props": ["skeleton_reaching", "key", "locked_chest", "pressure_plate"],
        "arrangement": "skeleton reaching for key near trapped chest",
    },
    "family_shelter": {
        "props": ["skeleton_adult_x2", "skeleton_child", "barricaded_door", "supplies"],
        "arrangement": "family huddled together behind barricade",
    },
}

def place_narrative_vignette(vignette_type: str, position: Vec3,
                             room_bounds: dict, seed: int = 0) -> list[dict]:
    """Place a narrative vignette's props according to arrangement rules."""
    template = NARRATIVE_VIGNETTES[vignette_type]
    rng = random.Random(seed)
    placements = []

    for prop_name, rules in template["placement_rules"].items():
        prop_pos = list(position)

        if rules.get("against_wall"):
            prop_pos = snap_to_nearest_wall(position, room_bounds)
        elif rules.get("center"):
            prop_pos = room_center(room_bounds)

        if "distance_from_skeleton" in rules or "distance" in rules:
            dist = rules.get("distance_from_skeleton", rules.get("distance", 1.0))
            angle = rng.uniform(0, 2 * math.pi)
            prop_pos[0] += dist * math.cos(angle)
            prop_pos[1] += dist * math.sin(angle)

        if rules.get("ring_around"):
            # Place multiple instances in a ring
            count = int(prop_name.split("_x")[-1]) if "_x" in prop_name else 1
            radius = rules.get("radius", 2.0)
            for i in range(count):
                angle = 2 * math.pi * i / count + rng.uniform(-0.3, 0.3)
                placements.append({
                    "prop": prop_name.split("_x")[0],
                    "position": (prop_pos[0] + radius * math.cos(angle),
                                prop_pos[1] + radius * math.sin(angle),
                                prop_pos[2]),
                    "rotation": rng.uniform(0, 360),
                })
                continue

        placements.append({
            "prop": prop_name,
            "position": tuple(prop_pos),
            "rotation": rng.uniform(0, 360) if rules.get("random_rotation") else 0,
        })

    return placements
```

### 5.3 Boss Approach Zone Escalation

```python
ESCALATION_STAGES = [
    # Distance from boss (as fraction of total path), intensity
    {"distance": 1.0, "damage_level": 0.0, "corpse_density": 0.0, "hazard_chance": 0.0},
    {"distance": 0.75, "damage_level": 0.2, "corpse_density": 0.1, "hazard_chance": 0.05},
    {"distance": 0.50, "damage_level": 0.5, "corpse_density": 0.3, "hazard_chance": 0.15},
    {"distance": 0.25, "damage_level": 0.8, "corpse_density": 0.5, "hazard_chance": 0.30},
    {"distance": 0.10, "damage_level": 1.0, "corpse_density": 0.7, "hazard_chance": 0.50},
]

def apply_boss_approach_escalation(dungeon_layout, boss_room_pos, seed=0):
    """Apply escalating environmental damage along paths leading to boss."""
    rng = random.Random(seed)
    # BFS from boss room to compute distance field
    distances = bfs_distance(dungeon_layout, boss_room_pos)
    max_dist = max(distances.values()) if distances else 1

    decorations = []
    for cell, dist in distances.items():
        normalized_dist = dist / max_dist
        stage = get_escalation_stage(normalized_dist)

        # Structural damage
        if rng.random() < stage["damage_level"] * 0.3:
            decorations.append({"type": "cracked_wall", "position": cell})
        if rng.random() < stage["damage_level"] * 0.2:
            decorations.append({"type": "collapsed_ceiling", "position": cell})

        # Corpses
        if rng.random() < stage["corpse_density"]:
            decorations.append({
                "type": rng.choice(["skeleton", "corpse_armored", "corpse_robed"]),
                "position": cell,
                "facing": boss_room_pos,  # Died facing the boss
            })

        # Hazards
        if rng.random() < stage["hazard_chance"]:
            decorations.append({
                "type": rng.choice(["fire_patch", "poison_pool", "spike_trap"]),
                "position": cell,
            })

    return decorations
```

### 5.4 Hidden Path Indicators

**FromSoftware's hidden path signaling (for procedural placement):**
1. **Subtle texture difference** on illusory walls (slightly different stone color)
2. **Missing environmental detail** — a wall section without moss/damage that surrounds it
3. **Player messages/corpse near wall** — place an NPC corpse facing the secret wall
4. **Acoustic cue** — hollow sound when striking wall (runtime audio system)
5. **Sight lines** — you can sometimes see through cracks in the wall to a visible treasure

---

## 6. Open Source Tools & Libraries

### 6.1 Noise Libraries for Python

| Library | Quality | Speed | Python | Key Feature |
|---------|---------|-------|--------|-------------|
| **opensimplex** | HIGH | Medium (2.3us/sample) | pip install | No patent issues, numpy support |
| **vnoise** | HIGH | Fast vectorized (0.3-4x C speed) | pip install | Pure Python, numpy vectorized |
| **pynoise** | HIGH | Slow | pip install | libnoise port, ridged/billow/turbulence |
| **perlin-noise** | LOW | Very slow | pip install | Simple, N-dimensional |
| **noise** (C ext) | HIGH | Fastest (0.1us/sample) | pip install | C extension, no Python 3.12+ |
| **FastNoiseLite** | HIGHEST | Fastest | No Python port | C/C#/JS, best quality. Needs ctypes wrapper |

**RECOMMENDATION:** Keep current opensimplex + permutation table fallback. Add **vnoise** as secondary option for vectorized Perlin. Port pynoise's ridged multifractal module (it's pure Python, easy to extract).

### 6.2 Terrain Erosion

| Project | Language | Quality | Key Technique |
|---------|----------|---------|---------------|
| **terrain-erosion-3-ways** | Python/numpy | HIGH | Particle, grid, stream power |
| **hydraulic-erosion-simulator** | Python | HIGH | GPU paper port |
| **SoilMachine** | C++ | HIGHEST | Multi-layer 3D erosion |
| **erodr** | C | HIGH | Hans Beyer's algorithm |

**RECOMMENDATION:** Port particle-based method from `terrain-erosion-3-ways` directly into `_terrain_noise.py`. It's 200 lines of numpy, fits perfectly.

### 6.3 WFC Implementations

| Project | Language | Quality | Notes |
|---------|----------|---------|-------|
| **mxgmn/WaveFunctionCollapse** | C# | HIGHEST | Original reference |
| **baskiton/wfc** | Python | MEDIUM | Tilemap generator |
| **Coac/wave-function-collapse** | Python | MEDIUM | 1D/2D/3D support |

**RECOMMENDATION:** Implement WFC from scratch in `_dungeon_gen.py`. The algorithm is 100-150 lines. Using a library adds dependency for something simple enough to own.

### 6.4 City/Town Generation

| Project | Language | Quality | Notes |
|---------|----------|---------|-------|
| **watabou/TownGeneratorOS** | Haxe | HIGHEST | Medieval fantasy, Voronoi-based |
| **tmwhere/city_generation** | JavaScript | HIGH | L-system roads, population map |
| **phiresky/procedural-cities** | TypeScript | MEDIUM | Parish & Mueller implementation |

**RECOMMENDATION:** Study watabou's algorithm (open source, Haxe). Reimplement the core Voronoi district + organic road growth in Python. Our `TownLayout` dataclass is already structured for this.

### 6.5 Vegetation Tools

| Project | Language | Quality | Notes |
|---------|----------|---------|-------|
| **Modular Tree addon** | Blender/Python | HIGH | L-system + biology sim |
| **friggog/tree-gen** | Blender/Python | MEDIUM | L-system + Skin modifier |
| **EZ Tree** | Python | MEDIUM | Standalone, outputs .obj |
| **IvyGen** | Blender built-in | HIGH | Ivy growth on surfaces |

**RECOMMENDATION:** Don't depend on external addons. Implement L-system tree skeleton generation in pure Python (50 lines), use Blender's Skin modifier for volume. This keeps it self-contained.

### 6.6 Poisson Disk Sampling

| Library | Language | Quality | Notes |
|---------|----------|---------|-------|
| **scipy.stats.qmc.PoissonDisk** | Python | HIGHEST | Production quality, in scipy |
| **poissonDiskSampling** | Python | MEDIUM | Standalone pip package |
| **Bridson's algorithm** | Any | HIGH | Classic, easy to implement |

**RECOMMENDATION:** Use `scipy.stats.qmc.PoissonDisk` if scipy available, otherwise implement Bridson's algorithm (30 lines). We already use Poisson disk sampling in `scatter_vegetation` — verify it's using the right approach.

### 6.7 Blender Environment Addons (Reference)

| Addon | Quality | Notes |
|-------|---------|-------|
| **Terrain Mixer** | HIGH | Free, erosion mixing, GN-based |
| **World Blender Pro 2025** | HIGHEST | Commercial, complete landscape system |
| **Scatter** (KIRI Engine) | HIGH | Free, surface scattering |

These are references for capability parity, not dependencies.

---

## 7. Gap Analysis vs Current Toolkit

### Currently Implemented (in `_terrain_noise.py`, `_dungeon_gen.py`, `worldbuilding_layout.py`)

| Feature | File | Quality |
|---------|------|---------|
| fBm heightmap generation | `_terrain_noise.py` | GOOD |
| 6 terrain presets | `_terrain_noise.py` | GOOD |
| Slope map computation | `_terrain_noise.py` | GOOD |
| Basic biome assignment | `_terrain_noise.py` | BASIC |
| A* river carving | `_terrain_noise.py` | GOOD |
| A* road generation | `_terrain_noise.py` | GOOD |
| BSP dungeon generation | `_dungeon_gen.py` | GOOD |
| Cellular automata caves | `_dungeon_gen.py` | GOOD |
| Voronoi town layout | `_dungeon_gen.py` | BASIC |
| Multi-floor dungeons | `_dungeon_gen.py` | BASIC |
| Boss arena generation | `worldbuilding_layout.py` | BASIC |
| Easter egg/secret rooms | `worldbuilding_layout.py` | BASIC |
| World graph (MST) | `worldbuilding_layout.py` | GOOD |
| Building grammar | `_building_grammar.py` | GOOD |
| Castle generation | `_building_grammar.py` | GOOD |

### Critical Gaps (HIGH PRIORITY)

| Gap | Impact | Effort | Location |
|-----|--------|--------|----------|
| **Hydraulic erosion** | AAA terrain quality | MEDIUM | `_terrain_noise.py` |
| **Thermal erosion** | Realistic cliffs/rocks | LOW | `_terrain_noise.py` |
| **Ridged multifractal** | Mountain ridges | LOW | `_terrain_noise.py` |
| **Domain warping** | Organic terrain shapes | LOW | `_terrain_noise.py` |
| **Worley/Voronoi noise** | Rock/crystal patterns | MEDIUM | `_terrain_noise.py` |
| **WFC dungeon generation** | Better dungeon variety | MEDIUM | `_dungeon_gen.py` |
| **Cyclic dungeon generation** | Gameplay-quality dungeons | HIGH | `_dungeon_gen.py` |
| **Whittaker biome system** | Realistic biome distribution | MEDIUM | `_terrain_noise.py` |
| **Height-based splatmap** | Better texture blending | MEDIUM | `terrain_materials.py` |
| **L-system trees** | Procedural vegetation | MEDIUM | new handler |
| **Narrative prop placement** | Environmental storytelling | MEDIUM | `worldbuilding_layout.py` |

### Nice-to-Have Gaps (MEDIUM PRIORITY)

| Gap | Impact | Effort |
|-----|--------|--------|
| L-system road networks | Better city layouts | MEDIUM |
| Building lot subdivision | Realistic towns | MEDIUM |
| Fortification generation | Castle walls/towers | MEDIUM |
| Ivy/vine growth | Environmental detail | LOW |
| Boss approach escalation | Narrative quality | LOW |
| Wind-based moisture sim | Better biome placement | LOW |
| Cross-quad tree impostors | LOD optimization | MEDIUM |
| Secret room algorithm | Dungeon quality | LOW |

---

## 8. Implementation Roadmap

### Phase 1: Terrain Quality Leap (3-4 tasks)

1. **Add ridged multifractal noise** to `_terrain_noise.py`
   - New preset: `"ridged_mountains"` using ridged basis
   - Add `noise_type` parameter to `generate_heightmap()`

2. **Add domain warping** to `generate_heightmap()`
   - New parameters: `warp_scale`, `warp_frequency`
   - Apply coordinate distortion before noise sampling

3. **Implement hydraulic erosion** in `_terrain_noise.py`
   - New function: `hydraulic_erode(heightmap, ...)`
   - Particle-based method, numpy-vectorized
   - Call from `generate_terrain` handler with `erosion=True`

4. **Implement thermal erosion** in `_terrain_noise.py`
   - New function: `thermal_erode(heightmap, ...)`
   - Simple neighbor comparison, runs fast

### Phase 2: Dungeon Quality Leap (2-3 tasks)

5. **Implement WFC dungeon generation** in `_dungeon_gen.py`
   - New function: `generate_wfc_dungeon(width, height, tile_set, seed)`
   - Define dark fantasy tile adjacency rules
   - Integrate as alternative to BSP in `generate_dungeon` handler

6. **Implement cyclic dungeon generation** in `_dungeon_gen.py`
   - New function: `generate_cyclic_dungeon(num_cycles, cycle_types, seed)`
   - Graph generation then spatial layout
   - Lock-and-key, shortcut, secret cycle types

7. **Enhanced secret room placement**
   - Upgrade `generate_easter_egg_spec()` with wall-scanning algorithm
   - Add illusory wall, hidden lever, destructible wall types

### Phase 3: World Building Enhancement (3-4 tasks)

8. **Whittaker biome system** upgrade to `compute_biome_assignments()`
   - Temperature + moisture dual-axis lookup
   - Wind-based moisture simulation
   - Dark fantasy biome palette

9. **L-system tree generation** (new handler)
   - Species presets for dark fantasy biomes
   - Skin modifier for branch volume
   - LOD chain generation (full mesh -> cross-quad -> billboard)

10. **Narrative prop placement system**
    - Vignette templates (failed adventurer, last stand, etc.)
    - Boss approach escalation algorithm
    - Integration with dungeon/building generation

11. **Town generation upgrade**
    - L-system or agent-based road growth
    - Building lot subdivision (OBB recursive)
    - Fortification generation (walls, towers, gates)
    - Market/plaza generation

### Phase 4: Polish & Integration (2-3 tasks)

12. **Height-based splatmap generation**
    - Per-texture depth maps for natural blending
    - Export as RGBA textures for Unity terrain

13. **Worley noise integration**
    - For rock formation generation
    - For cracked ground / dried mud terrain type
    - Vectorized implementation using spatial hashing

14. **Cross-quad tree impostor generation**
    - Automated LOD chain from full tree mesh
    - 4-angle render to atlas texture
    - Cross-plane mesh generation

---

## Sources

### Terrain Generation
- [Terrain Erosion on the GPU — Axel Paris](https://aparis69.github.io/public_html/posts/terrain_erosion.html)
- [terrain-erosion-3-ways — GitHub](https://github.com/dandrino/terrain-erosion-3-ways)
- [Simulating Hydraulic Erosion — Job Talle](https://jobtalle.com/simulating_hydraulic_erosion.html)
- [Simple Particle-Based Hydraulic Erosion — Nick McDonald](https://nickmcd.me/2020/04/10/simple-particle-based-hydraulic-erosion/)
- [SoilMachine — Multi-layer terrain erosion — GitHub](https://github.com/weigert/SoilMachine)
- [Procedural Hydrology — Nick McDonald](https://nickmcd.me/2020/04/15/procedural-hydrology/)
- [Making Maps with Noise — Red Blob Games](https://www.redblobgames.com/maps/terrain-from-noise/)
- [Domain Warping — Inigo Quilez](https://iquilezles.org/articles/warp/)
- [FastNoiseLite — GitHub](https://github.com/Auburn/FastNoiseLite)
- [OpenSimplex — PyPI](https://pypi.org/project/opensimplex/)
- [vnoise — GitHub](https://github.com/plottertools/vnoise)
- [pynoise documentation](https://pynoise.readthedocs.io/)
- [Stream Power Erosion — GitHub](https://github.com/H-Schott/StreamPowerErosion)
- [hydraulic-erosion-simulator — GitHub](https://github.com/keepitwiel/hydraulic-erosion-simulator)
- [Around The World Part 23: Hydraulic Erosion — Frozen Fractal](https://frozenfractal.com/blog/2025/6/6/around-the-world-23-hydraulic-erosion/)
- [Hydraulic Erosion — Sebastian Lague](https://sebastian.itch.io/hydraulic-erosion)

### Dungeon Generation
- [WaveFunctionCollapse — GitHub (Maxim Gumin)](https://github.com/mxgmn/WaveFunctionCollapse)
- [Dungeon Generation in Unexplored — Boris the Brave](https://www.boristhebrave.com/2021/04/10/dungeon-generation-in-unexplored/)
- [Unexplored's Secret: Cyclic Dungeon Generation — Game Developer](https://www.gamedeveloper.com/design/unexplored-s-secret-cyclic-dungeon-generation-)
- [Cyclic Dungeon Generation — Sersa Victory](https://sersavictory.itch.io/cyclic-dungeon-generation)
- [cyclic-dungeon-generation-model — GitHub](https://github.com/patrykferenc/cyclic-dungeon-generation-model)
- [Metazelda — GitHub](https://github.com/tcoxon/metazelda)
- [Graph-based dungeon generation — GitHub](https://github.com/amidos2006/GraphDungeonGenerator)
- [Lock and Key Dungeon Generation — Shaggy Dev](https://shaggydev.com/2021/12/17/lock-key-dungeon-generation/)
- [WFC Python implementation — GitHub](https://github.com/Coac/wave-function-collapse)
- [Cellular Automata Cave Generation — Jeremy Kun](https://www.jeremykun.com/2012/07/29/the-cellular-automaton-method-for-cave-generation/)
- [Rooms and Mazes — Bob Nystrom](https://journal.stuffwithstuff.com/2014/12/21/rooms-and-mazes/)
- [BSP Dungeon Generation — RogueBasin](https://www.roguebasin.com/index.php/Basic_BSP_Dungeon_generation)
- [Procedural Dungeon Generation Algorithm — Game Developer](https://www.gamedeveloper.com/programming/procedural-dungeon-generation-algorithm)
- [BSP-Based Dungeon Design Technical Note 2026](https://www.researchgate.net/publication/396442454_From_Algorithm_to_Playable_Space_A_Technical_Note_on_BSP-Based_Dungeon_Design)

### City/Town Generation
- [Procedural Modeling of Cities — Parish & Mueller](https://ccl.northwestern.edu/rp/cities/core.shtml)
- [Procedural City Generation — tmwhere](https://www.tmwhere.com/city_generation.html)
- [Medieval Fantasy City Generator — watabou](https://watabou.itch.io/medieval-fantasy-city-generator)
- [TownGeneratorOS — GitHub](https://github.com/watabou/TownGeneratorOS)
- [Procedural Generation of Parcels — Vanegas et al.](https://www.cs.purdue.edu/cgvlab/papers/aliaga/eg2012.pdf)
- [Lot Subdivision — Martin Devans](https://martindevans.me/game-development/2015/12/27/Procedural-Generation-For-Dummies-Lots/)
- [Agent-based city generation — arXiv](https://arxiv.org/abs/2211.01959)
- [L-system road networks — Liu thesis](https://liu.diva-portal.org/smash/get/diva2:1467574/FULLTEXT01.pdf)
- [CityGen — GDC paper](https://www.citygen.net/files/citygen_gdtw07.pdf)
- [Procedural Town Generation — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1524070323000012)

### Vegetation
- [L-Systems for Plant Generation — Springer (book chapter)](https://link.springer.com/chapter/10.1007/979-8-8688-1787-8_7)
- [Modular Tree addon — Blender Extensions](https://extensions.blender.org/add-ons/modular-tree/)
- [tree-gen — GitHub](https://github.com/friggog/tree-gen)
- [EZ Tree — Digital Production](https://digitalproduction.com/2025/05/07/ez-tree-your-next-trees-just-a-click-away/)
- [IvyGen — Blender Manual](https://docs.blender.org/manual/en/latest/addons/add_curve/ivy_gen.html)
- [Procedural Grass Rendering — AMD GPUOpen](https://gpuopen.com/learn/mesh_shaders/mesh_shaders-procedural_grass_rendering/)
- [Tree LOD with Impostor Baker — Medium](https://medium.com/@arnoldpaul/making-an-efficient-tree-lod-with-impostor-baker-plus-e9d152241831)
- [Cross-Quad Impostor Generator — GitHub](https://github.com/roundyyy/Tree-Cross-Quad-Impostor-Generator)

### Environmental Storytelling
- [World Design Lessons from FromSoftware — Medium](https://medium.com/@Jamesroha/world-design-lessons-from-fromsoftware-78cadc8982df)
- [Souls-like Level Design Methodology — Medium](https://medium.com/@bramasolejm030206/preface-ec08bc1459d0)
- [Environmental Storytelling — Game Developer](https://www.gamedeveloper.com/design/environmental-storytelling)
- [Cover Design — Level Design Book](https://book.leveldesignbook.com/process/combat/cover)
- [Boss Design Guide — Game Design Skills](https://gamedesignskills.com/game-design/game-boss-design/)
- [Elden Ring Environmental Storytelling — CBR](https://www.cbr.com/elden-ring-environmental-storytelling-fromsoftware/)

### Biome & Splatmap
- [Whittaker Diagram — PCG Wiki](http://pcg.wikidot.com/pcg-algorithm:whittaker-diagram)
- [AutoBiomes: Multi-biome Landscapes — Springer](https://link.springer.com/article/10.1007/s00371-020-01920-7)
- [Biomes Generation — Azgaar](https://azgaar.wordpress.com/2017/06/30/biomes-generation-and-rendering/)
- [Advanced Terrain Texture Splatting — Game Developer](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting)
- [Procedural Terrain Splatmapping — Alastair Aitchison](https://alastaira.wordpress.com/2013/11/14/procedural-terrain-splatmapping/)

### Blender Environment Tools
- [Terrain Mixer — Blender Extensions](https://extensions.blender.org/add-ons/terrainmixer/)
- [Geometry Nodes to UE5 Guide — Medium](https://medium.com/@Jamesroha/blender-geometry-nodes-to-unreal-engine-5-the-procedural-environment-art-guide-05cf8d8b4701)
- [Blender Procedural Level Generation — GitHub](https://github.com/aaronjolson/Blender-Python-Procedural-Level-Generation)
- [Scatter for Blender — KIRI Engine](https://digitalproduction.com/2026/02/17/kiri-engine-releases-free-scatter-for-blender/)
- [Virtual Texture Terrain — Game Developer](https://www.gamedeveloper.com/game-platforms/virtual-texture-terrain)
