# Procedural City & Settlement Generation -- Deep Research

> Compiled 2026-04-01 for VeilBreakers toolkit implementation.
> Sources: Parish & Muller 2001, Chen et al. 2008, Watabou TownGeneratorOS, mxgmn WFC,
> Townscaper (Stalberg), CityEngine/CGA, AC Unity/Mirage, Skyrim design docs, 20+ papers.

---

## 1. Road Network Generation Algorithms

### 1.1 L-System Road Generation (Parish & Muller 2001)

The foundational approach. An **extended parametric L-system** generates roads using two
external functions that override pure grammar rewriting:

**Axiom:**
```
R(0, initialRuleAttr) ?I(initRoadAttr, UNASSIGNED)
```
Where `R` = road module, `?I` = intersection query.

**Core Production Rules:**
```
Rule 1: R(delay, ruleAttr) : delay > 0  -->  R(delay-1, ruleAttr)
Rule 2: R(delay, ruleAttr) : delay == 0 -->
    ?I(roadAttr, UNASSIGNED)
    B(ruleAttr, roadAttr)     // Branch module

Rule 3: B(ruleAttr, roadAttr) -->
    R(delay_highway, ruleAttr_highway)   // continue forward
    R(delay_street, ruleAttr_street_L)   // branch left
    R(delay_street, ruleAttr_street_R)   // branch right

Rule 4: ?I(roadAttr, state) : state == SUCCEED --> I(roadAttr)
Rule 5: ?I(roadAttr, state) : state == FAILED  --> epsilon (remove)
```

**Global Goals Function** -- selects direction for new road segments:
- For **highways**: Cast N rays radially (typically 5-10) within preset radius
  - Sample population density along each ray
  - Weight samples by inverse distance: `score = sum(density(p) / dist(p, roadEnd))`
  - Choose direction with highest score
- For **streets**: Apply local pattern rules:
  - **Grid pattern**: Branch at 90deg, continue straight. Parameters: block_width 50-100m
  - **Radial pattern**: Branch toward/away from center point. Angle follows arc
  - **Organic pattern**: Add Perlin noise to direction. Amplitude: 15-30deg

**Local Constraints Function** -- validates each proposed segment:
```python
def local_constraints(proposed_segment, existing_roads, terrain):
    # 1. Water check
    if crosses_water(proposed_segment):
        if water_width < BRIDGE_THRESHOLD:  # ~30m
            mark_as_bridge(proposed_segment)
        else:
            rotate_search(proposed_segment, max_angle=90, step=10)
            if no_valid_rotation: return FAILED

    # 2. Intersection snapping
    for existing in nearby_roads(proposed_segment.end, snap_radius=15m):
        snap_to_intersection(proposed_segment, existing)
        return SUCCEED

    # 3. Elevation check
    grade = abs(terrain_height_diff / segment_length)
    if grade > MAX_GRADE:  # 0.15 for streets, 0.08 for highways
        if hill_width < CUT_THRESHOLD:
            mark_as_cut(proposed_segment)
        else:
            rotate_search(proposed_segment, max_angle=45, step=5)

    # 4. Collision check
    if intersects_existing_road(proposed_segment):
        create_intersection(at_crossing_point)
        trim_segment()

    return SUCCEED
```

**Key Parameters (implementable defaults):**
| Parameter | Highway | Main Street | Secondary | Alley |
|-----------|---------|-------------|-----------|-------|
| Segment length | 50-100m | 20-40m | 10-20m | 5-10m |
| Road width | 15-25m | 8-12m | 5-8m | 2-4m |
| Branch angle | 30-60deg | 70-90deg | 85-95deg | 60-120deg |
| Branch probability | 0.3 | 0.6 | 0.4 | 0.1 |
| Delay (iterations) | 5-10 | 2-4 | 1-2 | 0-1 |
| Max grade | 8% | 12% | 15% | 20% |
| Snap radius | 20m | 15m | 10m | 5m |

### 1.2 Tensor Field Road Generation (Chen et al. 2008)

Superior to L-systems for organic-feeling road networks. Core insight: roads naturally
follow **two dominant perpendicular directions** at any point -- tensor fields encode this.

**Tensor Definition:**
Each point p has a 2x2 symmetric tensor T(p) with orientation theta(p) and magnitude R >= 0.

```
T(p) = R * [cos(2*theta)  sin(2*theta)]
           [sin(2*theta) -cos(2*theta)]
```

The factor of 2 in the angle makes tensors 180-degree symmetric (a road going north
is the same as one going south).

**Basis Field Types (combine these):**
```python
# Grid field -- creates Manhattan-like grids
def grid_tensor(p, center, theta, decay):
    R = exp(-decay * dist(p, center))
    return R * rotation_tensor(theta)

# Radial field -- creates circular/radial patterns (market squares, plazas)
def radial_tensor(p, center, decay):
    theta = atan2(p.y - center.y, p.x - center.x)
    R = exp(-decay * dist(p, center))
    return R * rotation_tensor(theta)

# Height field -- roads follow terrain contours
def height_tensor(p, heightmap):
    gradient = sample_gradient(heightmap, p)
    theta = atan2(gradient.y, gradient.x)
    R = length(gradient)
    return R * rotation_tensor(theta)

# Boundary field -- roads parallel to water/walls/cliffs
def boundary_tensor(p, boundary_polyline, decay):
    closest, tangent = nearest_point_on_polyline(p, boundary_polyline)
    theta = atan2(tangent.y, tangent.x)
    R = exp(-decay * dist(p, closest))
    return R * rotation_tensor(theta)
```

**Field Combination (weighted average):**
```python
T_combined(p) = sum(weight_i * T_i(p)) / sum(weight_i)
```
This is the key advantage -- fields blend smoothly with no conflict resolution.

**Streamline Tracing (RK4 integration):**
```python
def trace_streamline(tensor_field, start, direction='major', step=1.0):
    points = [start]
    p = start
    prev_dir = None
    while in_bounds(p):
        T = tensor_field.sample(p)
        eigenvectors = decompose(T)
        dir = eigenvectors.major if direction == 'major' else eigenvectors.minor

        # Flip check: ensure consistent direction
        if prev_dir and dot(dir, prev_dir) < 0:
            dir = -dir

        # RK4 integration for smooth curves
        k1 = dir
        k2 = field_dir(p + step/2 * k1)
        k3 = field_dir(p + step/2 * k2)
        k4 = field_dir(p + step * k3)
        next_p = p + step/6 * (k1 + 2*k2 + 2*k3 + k4)

        # Termination conditions
        if dist(next_p, p) < MIN_SEGMENT:  # 0.5m
            break
        if too_close_to_existing(next_p, existing_streamlines, sep_dist):
            snap_or_terminate(next_p, existing_streamlines)
            break

        points.append(next_p)
        p = next_p
        prev_dir = dir
    return points
```

**Separation Distance (controls road density):**
- Major streamlines (highways): sep = 200-500m
- Minor streamlines (streets): sep = 30-80m
- Use population density to modulate: `sep = base_sep / (1 + density_factor)`

**Intersection Generation:**
- Intersections form naturally where major and minor streamlines cross
- Since eigenvectors are perpendicular, intersections are near-90-degree
- T-junctions form when a streamline terminates by snapping to an existing one

### 1.3 Road-Terrain Interaction

```python
def generate_road_on_terrain(road_points, heightmap, params):
    for i, point in enumerate(road_points):
        # Sample terrain height
        h = heightmap.sample(point.x, point.y)

        # Calculate grade
        if i > 0:
            grade = abs(h - prev_h) / dist(point, road_points[i-1])

        if grade > params.max_grade:
            # Option 1: Cut through hill
            if is_hill(heightmap, point, search_radius=50m):
                cut_depth = h - (prev_h + params.max_grade * dist)
                create_road_cut(point, cut_depth, road_width * 2)

            # Option 2: Bridge over valley
            elif is_valley(heightmap, point, search_radius=50m):
                bridge_start, bridge_end = find_valley_edges(point)
                create_bridge(bridge_start, bridge_end, height=prev_h)

            # Option 3: Switchback on steep slopes
            elif grade > params.switchback_threshold:  # 0.20
                insert_switchback(road_points, i, turn_radius=15m)

        # Road follows contour with gentle grading
        target_h = lerp(h, prev_h + params.preferred_grade * dist, 0.7)
        road_points[i].z = target_h
        prev_h = target_h
```

### 1.4 Intersection Types

```python
INTERSECTION_TYPES = {
    'T_JUNCTION': {
        'angles': [180, 90, 90],  # one road continues, one branches
        'usage': 'residential streets meeting main roads',
        'frequency': 0.45
    },
    'CROSSROAD': {
        'angles': [90, 90, 90, 90],  # four-way perpendicular
        'usage': 'grid districts, main road crossings',
        'frequency': 0.30
    },
    'ROUNDABOUT': {
        'radius': '8-15m',
        'usage': 'market squares, plazas, major junctions',
        'frequency': 0.05,
        'min_roads': 3
    },
    'Y_JUNCTION': {
        'angles': [120, 120, 120],  # three roughly equal
        'usage': 'organic medieval layouts, road forks',
        'frequency': 0.10
    },
    'DEAD_END': {
        'usage': 'cul-de-sacs, courtyard entrances, alleys',
        'frequency': 0.10,
        'turnaround_radius': '5-8m'
    }
}
```

---

## 2. Building Lot Subdivision

### 2.1 OBB Recursive Splitting Algorithm

```python
def subdivide_block(polygon, constraints, road_edges, depth=0):
    """
    Recursively split a city block into building lots.
    polygon: list of 2D points defining the block boundary
    constraints: { min_area, max_area, min_width, min_depth,
                   max_aspect_ratio, min_frontage, max_depth }
    road_edges: set of edge indices that touch roads
    """
    area = polygon_area(polygon)

    # Base case: lot is within target size
    if area <= constraints.max_area:
        if validate_lot(polygon, constraints, road_edges):
            return [polygon]
        else:
            return []  # reject invalid lot

    # Step 1: Compute minimum-area OBB
    obb = compute_min_area_obb(polygon)
    # OBB gives: center, major_axis, minor_axis, extents

    # Step 2: Choose split axis (along shorter OBB dimension)
    if obb.extent_major > obb.extent_minor:
        split_dir = obb.minor_axis  # split perpendicular to long axis
        extent = obb.extent_major
    else:
        split_dir = obb.major_axis
        extent = obb.extent_minor

    # Step 3: Choose split position
    # Add randomness: split between 40%-60% of extent
    split_t = 0.4 + random() * 0.2
    split_point = obb.center + split_dir * extent * (split_t - 0.5)
    split_line = Line(split_point, split_dir.perpendicular())

    # Step 4: Split polygon
    poly_a, poly_b = split_polygon_by_line(polygon, split_line)

    # Step 5: Validate children
    for child in [poly_a, poly_b]:
        child_obb = compute_min_area_obb(child)
        if child_obb.min_extent < constraints.min_width:  # 6m
            return [polygon]  # can't split further
        if child_obb.max_extent / child_obb.min_extent > constraints.max_aspect_ratio:  # 3:1
            return [polygon]  # would create too-narrow lot

    # Step 6: Propagate road edge info to children
    road_edges_a = classify_road_edges(poly_a, road_edges)
    road_edges_b = classify_road_edges(poly_b, road_edges)

    # Step 7: Recurse
    lots = []
    lots.extend(subdivide_block(poly_a, constraints, road_edges_a, depth+1))
    lots.extend(subdivide_block(poly_b, constraints, road_edges_b, depth+1))
    return lots

def validate_lot(polygon, constraints, road_edges):
    area = polygon_area(polygon)
    if area < constraints.min_area:     # 48 sq m (6x8)
        return False

    obb = compute_min_area_obb(polygon)
    if obb.min_extent < constraints.min_width:   # 6m
        return False
    if obb.max_extent < constraints.min_depth:   # 8m
        return False
    if obb.max_extent / obb.min_extent > constraints.max_aspect_ratio:  # 3:1
        return False

    # Frontage: lot must touch a road
    frontage = compute_road_frontage(polygon, road_edges)
    if frontage < constraints.min_frontage:  # 4m
        return False

    return True
```

### 2.2 Lot Constraints by District Type

| District | Min Area | Max Area | Min Width | Min Depth | Max Aspect | Min Frontage | Setback |
|----------|----------|----------|-----------|-----------|------------|--------------|---------|
| Market/Commercial | 80m2 | 300m2 | 8m | 10m | 2.5:1 | 6m | 0m |
| Residential (wealthy) | 150m2 | 500m2 | 10m | 12m | 2:1 | 8m | 3m |
| Residential (common) | 48m2 | 150m2 | 6m | 8m | 3:1 | 4m | 1m |
| Slum | 20m2 | 60m2 | 4m | 5m | 4:1 | 2m | 0m |
| Industrial/Craft | 100m2 | 400m2 | 10m | 10m | 2:1 | 6m | 2m |
| Noble/Patriciate | 300m2 | 1000m2 | 15m | 15m | 2:1 | 10m | 5m |
| Religious | 200m2 | 2000m2 | 12m | 15m | 2:1 | 8m | 3m |

### 2.3 Corner Lot Handling

```python
def handle_corner_lot(lot, road_edges):
    """Corner lots have frontage on 2+ roads. Buildings face both streets."""
    frontage_edges = [e for e in lot.edges if e in road_edges]
    if len(frontage_edges) >= 2:
        # Primary frontage = longer road-facing edge
        primary = max(frontage_edges, key=lambda e: e.length)
        secondary = [e for e in frontage_edges if e != primary]

        # Building footprint wraps the corner
        lot.building_orientation = 'L_SHAPE'
        lot.primary_facade = primary.direction
        lot.secondary_facade = secondary[0].direction
        lot.setback_primary = district.setback
        lot.setback_secondary = district.setback * 0.5  # reduced on side street
    return lot
```

### 2.4 Irregular Medieval Lot Generation

For organic medieval layouts, skip OBB and use **Voronoi-based** subdivision:

```python
def medieval_lot_subdivision(block_polygon, target_lot_count):
    """Creates irregular, organic lots typical of medieval cities."""
    # 1. Scatter points inside block (biased toward road edges)
    points = []
    for i in range(target_lot_count):
        p = random_point_in_polygon(block_polygon)
        # Bias toward roads: 70% of points within 5m of road edge
        if random() < 0.7:
            p = push_toward_nearest_road(p, road_edges, max_dist=5.0)
        points.append(p)

    # 2. Compute constrained Voronoi (clipped to block)
    voronoi = compute_voronoi(points)
    lots = clip_voronoi_to_polygon(voronoi, block_polygon)

    # 3. Lloyd relaxation (1-3 iterations for slight regularization)
    for _ in range(2):
        for i, lot in enumerate(lots):
            points[i] = centroid(lot)
        voronoi = compute_voronoi(points)
        lots = clip_voronoi_to_polygon(voronoi, block_polygon)

    # 4. Merge tiny lots, split oversized ones
    lots = merge_lots_below_min_area(lots, min_area=30)
    lots = split_lots_above_max_area(lots, max_area=200)

    return lots
```

---

## 3. Wave Function Collapse for Layouts

### 3.1 Core WFC Algorithm

```python
class WaveFunctionCollapse:
    def __init__(self, grid_size, tiles, adjacency_rules, weights):
        self.grid = {}  # (x,y,z) -> set of possible tile IDs
        self.tiles = tiles
        self.rules = adjacency_rules  # dict: (tile_id, direction) -> set(allowed_neighbors)
        self.weights = weights  # tile_id -> float (from frequency)

        # Initialize: every cell can be any tile
        for x in range(grid_size[0]):
            for y in range(grid_size[1]):
                for z in range(grid_size[2]):
                    self.grid[(x,y,z)] = set(tiles.keys())

    def solve(self):
        while not self.is_collapsed():
            # 1. Find cell with lowest entropy
            cell = self.lowest_entropy_cell()
            if cell is None:
                return False  # contradiction

            # 2. Collapse: choose tile weighted by frequency
            possible = self.grid[cell]
            tile = self.weighted_random_choice(possible, self.weights)
            self.grid[cell] = {tile}

            # 3. Propagate constraints
            self.propagate(cell)

        return True

    def entropy(self, cell):
        """Shannon entropy of remaining possibilities."""
        possible = self.grid[cell]
        if len(possible) <= 1:
            return 0
        total_w = sum(self.weights[t] for t in possible)
        H = math.log(total_w) - sum(
            self.weights[t] * math.log(self.weights[t])
            for t in possible
        ) / total_w
        return H

    def propagate(self, start_cell):
        """Constraint propagation via BFS."""
        stack = [start_cell]
        while stack:
            cell = stack.pop()
            for direction, neighbor in self.get_neighbors(cell):
                if neighbor not in self.grid:
                    continue
                # Compute allowed tiles for neighbor based on current cell
                allowed = set()
                for tile in self.grid[cell]:
                    allowed |= self.rules.get((tile, direction), set())

                # Intersect with neighbor's current possibilities
                prev = self.grid[neighbor]
                new = prev & allowed
                if new != prev:
                    if len(new) == 0:
                        raise Contradiction(f"No valid tiles at {neighbor}")
                    self.grid[neighbor] = new
                    stack.append(neighbor)

    DIRECTIONS_3D = {
        'north': (0, 0, 1), 'south': (0, 0, -1),
        'east': (1, 0, 0),  'west': (-1, 0, 0),
        'up': (0, 1, 0),    'down': (0, -1, 0)
    }
```

### 3.2 Tile Set for Medieval Buildings

**Socket System (from Townscaper / Marian42 approach):**
Each tile face has a **connector ID**. Two tiles can be adjacent if their facing connectors match.

```python
MEDIEVAL_BUILDING_TILES = {
    # Connector format: (north, east, south, west, up, down)
    # 0=air, 1=wall, 2=wall+window, 3=wall+door, 4=floor, 5=roof_edge

    'ground_floor_wall':     {'connectors': (1, 1, 1, 1, 4, 4), 'weight': 10},
    'ground_floor_door':     {'connectors': (3, 1, 1, 1, 4, 4), 'weight': 3},
    'ground_floor_shop':     {'connectors': (3, 2, 1, 1, 4, 4), 'weight': 2},
    'upper_floor_wall':      {'connectors': (2, 1, 2, 1, 4, 4), 'weight': 8},
    'upper_floor_window':    {'connectors': (2, 2, 1, 1, 4, 4), 'weight': 5},
    'corner_piece':          {'connectors': (1, 1, 0, 0, 4, 4), 'weight': 4},
    'roof_flat':             {'connectors': (5, 5, 5, 5, 0, 4), 'weight': 6},
    'roof_peak':             {'connectors': (5, 0, 5, 0, 0, 4), 'weight': 4},
    'roof_edge':             {'connectors': (5, 5, 0, 5, 0, 4), 'weight': 3},
    'half_timber_wall':      {'connectors': (2, 1, 1, 1, 4, 4), 'weight': 6},
    'balcony':               {'connectors': (0, 1, 0, 1, 4, 4), 'weight': 2},
    'chimney':               {'connectors': (0, 0, 0, 0, 0, 4), 'weight': 1},
    'air':                   {'connectors': (0, 0, 0, 0, 0, 0), 'weight': 15},
    'foundation':            {'connectors': (1, 1, 1, 1, 4, 0), 'weight': 5},
    'staircase':             {'connectors': (3, 1, 1, 1, 4, 4), 'weight': 1},
    'archway':               {'connectors': (3, 0, 3, 0, 4, 4), 'weight': 1},
}

# Adjacency generated from connector matching:
def generate_adjacency_rules(tiles):
    rules = {}
    opposite = {'north':'south','south':'north','east':'west',
                'west':'east','up':'down','down':'up'}
    dir_index = {'north':0,'east':1,'south':2,'west':3,'up':4,'down':5}

    for tid, tdata in tiles.items():
        for direction, opp in opposite.items():
            di = dir_index[direction]
            oi = dir_index[opp]
            my_connector = tdata['connectors'][di]
            allowed = set()
            for nid, ndata in tiles.items():
                if ndata['connectors'][oi] == my_connector:
                    allowed.add(nid)
            rules[(tid, direction)] = allowed
    return rules
```

### 3.3 WFC for Dungeons vs Settlements

| Aspect | Dungeon WFC | Settlement WFC |
|--------|-------------|----------------|
| Grid dimensions | 2D (top-down) or 2.5D | 3D (full vertical) |
| Primary tiles | Room, corridor, wall, door | Foundation, wall, floor, roof |
| Connectivity | Must ensure path from entrance to exit | Must ensure road access |
| Openness | Enclosed spaces, limited sightlines | Open courtyards, visible facades |
| Vertical | Stairs between levels (rare) | Multi-story buildings (common) |
| Constraint style | Hard path connectivity | Soft aesthetic + hard structural |
| Backtracking | Frequent (dead ends common) | Rare (more flexible) |
| Seeding | Fix entrance/exit/boss room | Fix road-facing facades, ground level |

### 3.4 Constraining WFC for Playable Game Spaces

```python
# Pre-collapse constraints for game-ready output:

# 1. Ground level must be solid
for x in range(grid_w):
    for z in range(grid_d):
        wfc.grid[(x, 0, z)] = {'foundation'}

# 2. Top must be open or roof
for x in range(grid_w):
    for z in range(grid_d):
        wfc.grid[(x, grid_h-1, z)] -= {'ground_floor_wall', 'upper_floor_wall'}

# 3. Road-facing cells must have doors on first floor
for cell in road_facing_cells:
    wfc.grid[cell] &= {'ground_floor_door', 'ground_floor_shop', 'archway'}

# 4. Interior must be navigable (post-generation validation)
def validate_interior_connectivity(building):
    """Ensure player can reach all rooms via doors/stairs."""
    rooms = flood_fill_from(building.entrance)
    all_rooms = find_all_rooms(building)
    if rooms != all_rooms:
        return False  # unreachable rooms exist
    return True

# 5. Structural integrity
def validate_structural(building):
    """Every non-ground tile must be supported."""
    for cell in building.cells:
        if cell.y > 0:
            below = (cell.x, cell.y - 1, cell.z)
            if building.grid[below] in {'air'}:
                return False  # floating structure
    return True
```

---

## 4. District Generation and Zoning

### 4.1 Voronoi-Based District Generation (Watabou Method)

```python
def generate_districts(city_bounds, num_districts, seed):
    """
    Full pipeline from Watabou's TownGeneratorOS.
    """
    random.seed(seed)

    # 1. Generate seed points in spiral pattern
    points = []
    for i in range(num_districts):
        radius = 10 + i * (2 + random.random())
        angle = i * GOLDEN_ANGLE  # 137.5 degrees -- fibonacci spiral
        x = radius * cos(angle)
        y = radius * sin(angle)
        points.append((x, y))

    # 2. Compute Voronoi diagram
    voronoi = compute_voronoi(points, bounds=city_bounds)

    # 3. Lloyd relaxation (3 iterations)
    for _ in range(3):
        for i, region in enumerate(voronoi.regions):
            points[i] = centroid(region)
        voronoi = compute_voronoi(points, bounds=city_bounds)

    # 4. Classify patches as inner/outer (wall boundary)
    inner = [p for p in voronoi.regions if distance(centroid(p), city_center) < wall_radius]

    # 5. Assign ward types by location rating
    ward_weights = {
        'CraftsmenWard': 40,
        'Slum': 11,
        'MerchantWard': 6,
        'Market': 6,
        'PatriciateWard': 6,
        'Cathedral': 3,
        'MilitaryWard': 3,
        'AdministrationWard': 2,
        'Park': 1,
        'Castle': 1  # always at center/highest point
    }

    for patch in inner:
        scores = {}
        for ward_type, base_weight in ward_weights.items():
            score = base_weight * rate_location(patch, ward_type, city)
            scores[ward_type] = score
        patch.ward = weighted_random_choice(scores)

    return voronoi, inner
```

### 4.2 Location Rating Functions

```python
def rate_location(patch, ward_type, city):
    """Rate how suitable a patch is for a given ward type."""
    c = centroid(patch)
    dist_center = distance(c, city.center)
    dist_gate = min(distance(c, g) for g in city.gates)
    dist_water = distance(c, city.river) if city.river else 999
    elevation = city.heightmap.sample(c)

    ratings = {
        'Castle':           (elevation * 2.0) + (1.0 / (dist_center + 1)),
        'Cathedral':        1.5 / (dist_center + 5) + elevation * 0.5,
        'Market':           2.0 / (dist_gate + 1) + 1.0 / (dist_center + 5),
        'MerchantWard':     1.5 / (dist_gate + 1),
        'PatriciateWard':   elevation * 1.5 + 1.0 / (dist_center + 5),
        'CraftsmenWard':    1.0 / (dist_water + 5) + 0.5,  # near water for mills
        'Slum':             dist_center * 0.1 + 1.0 / (dist_gate + 1),  # edge, near gates
        'MilitaryWard':     1.0 / (dist_gate + 1) + 0.5,  # near gates
        'AdministrationWard': 1.0 / (dist_center + 1),
        'Park':             dist_center * 0.05 + 0.3,
    }
    return ratings.get(ward_type, 0.5)
```

### 4.3 District Growth Simulation (Time-Based)

```python
def simulate_city_growth(terrain, seed_point, years=300, step=25):
    """
    Based on Weber et al. 2009 -- iterative city growth.
    Simulates how a medieval town grows over centuries.
    """
    city = City(center=seed_point)

    for year in range(0, years, step):
        # Phase 1: Extend road network
        population = city.population * (1 + growth_rate(year))

        # New roads grow from existing endpoints toward uncovered areas
        for endpoint in city.road_endpoints:
            if city.population_demand(endpoint) > THRESHOLD:
                direction = find_growth_direction(endpoint, terrain, city)
                new_road = extend_road(endpoint, direction, length=20+random()*30)
                city.add_road(new_road)

        # Phase 2: Zone new areas
        for block in city.unzoned_blocks:
            # Land value = f(road access, center distance, elevation, neighbors)
            value = compute_land_value(block, city)
            if value > COMMERCIAL_THRESHOLD:
                block.zone = 'commercial'
            elif value > RESIDENTIAL_HIGH:
                block.zone = 'residential_wealthy'
            else:
                block.zone = 'residential_common'

        # Phase 3: Build/upgrade structures
        for lot in city.empty_lots:
            if lot.value > BUILD_THRESHOLD:
                lot.building = generate_building(lot, lot.zone)

        for lot in city.built_lots:
            renovation_value = lot.value - lot.building.value
            if renovation_value > RENOVATION_THRESHOLD:
                lot.building = upgrade_building(lot.building, lot.zone)

        # Phase 4: Expand walls (every 100 years)
        if year % 100 == 0 and city.outside_wall_population > WALL_EXPANSION_THRESHOLD:
            city.expand_walls(radius_increase=50)

    return city
```

### 4.4 Building Distribution per District

```python
DISTRICT_BUILDINGS = {
    'Market': {
        'merchant_shop': 0.35, 'tavern': 0.10, 'warehouse': 0.15,
        'market_stall': 0.20, 'inn': 0.05, 'guild_hall': 0.02,
        'fountain': 0.03, 'residential_upper': 0.10
    },
    'CraftsmenWard': {
        'workshop': 0.30, 'residential': 0.35, 'shop_front': 0.15,
        'stable': 0.05, 'well': 0.02, 'small_warehouse': 0.08,
        'smithy': 0.05
    },
    'PatriciateWard': {
        'manor_house': 0.25, 'townhouse': 0.30, 'garden': 0.15,
        'chapel': 0.05, 'fountain': 0.05, 'servant_quarters': 0.10,
        'stable': 0.10
    },
    'Slum': {
        'hovel': 0.40, 'shanty': 0.25, 'lean_to': 0.15,
        'alehouse': 0.08, 'pawnshop': 0.05, 'empty_lot': 0.07
    },
    'MilitaryWard': {
        'barracks': 0.25, 'armory': 0.10, 'training_yard': 0.15,
        'stable': 0.15, 'officer_quarters': 0.10, 'gatehouse': 0.05,
        'watchtower': 0.10, 'mess_hall': 0.10
    },
    'Cathedral': {
        'cathedral': 0.05, 'monastery': 0.10, 'scriptorium': 0.05,
        'garden': 0.20, 'clergy_housing': 0.25, 'hospice': 0.10,
        'cemetery': 0.10, 'bell_tower': 0.05, 'courtyard': 0.10
    }
}
```

---

## 5. Vertical City Design

### 5.1 Multi-Level City Architecture

**Reference implementations:** Whiterun (Skyrim), Novigrad (Witcher 3), Leyndell (Elden Ring)

```python
class VerticalCity:
    def __init__(self, terrain_heightmap, base_elevation, num_tiers):
        self.tiers = []
        self.connections = []  # staircases, ramps, bridges

    def generate_tiers(self, terrain, num_tiers=3):
        """
        Generate city tiers based on terrain elevation bands.
        Skyrim Whiterun model: Plains District -> Wind District -> Cloud District
        """
        # Analyze terrain to find natural plateaus
        elevation_range = terrain.max_height - terrain.min_height
        tier_height = elevation_range / num_tiers

        for i in range(num_tiers):
            tier = CityTier(
                level=i,
                min_elevation=terrain.min_height + i * tier_height,
                max_elevation=terrain.min_height + (i+1) * tier_height,
                social_class=TIER_CLASSES[i]
            )

            # Extract buildable area at this elevation
            tier.buildable_mask = terrain.extract_plateau(
                tier.min_elevation, tier.max_elevation,
                min_area=500  # sq meters
            )

            # Higher tiers are smaller (pyramid structure)
            tier.target_area = tier.buildable_mask.area * (1.0 - i * 0.3)

            self.tiers.append(tier)

    def place_connections(self):
        """Place staircases and ramps between tiers."""
        for i in range(len(self.tiers) - 1):
            lower = self.tiers[i]
            upper = self.tiers[i + 1]

            # Find cliff edges where tiers meet
            boundary = find_tier_boundary(lower, upper)

            # Place main staircase (wide, central)
            main_stair = StairPlacement(
                location=boundary.midpoint,
                width=4.0,  # meters
                style='grand_staircase',
                rise=upper.min_elevation - lower.max_elevation,
                max_grade=0.45,  # 45% grade = ~24 degrees
                step_height=0.2,  # 20cm per step
                step_depth=0.3,   # 30cm tread
                landing_every=12  # landing every 12 steps
            )
            self.connections.append(main_stair)

            # Place secondary access (2-3 narrower paths)
            for j in range(2):
                side_pos = boundary.point_at(0.25 + j * 0.5)
                ramp = RampPlacement(
                    location=side_pos,
                    width=2.0,
                    style='switchback_ramp' if rise > 8 else 'straight_ramp',
                    max_grade=0.20
                )
                self.connections.append(ramp)

TIER_CLASSES = {
    0: {'name': 'Lower Ward', 'types': ['market', 'crafts', 'slum', 'gate'],
        'building_quality': 0.3, 'density': 0.8},
    1: {'name': 'Middle Ward', 'types': ['residential', 'merchant', 'temple'],
        'building_quality': 0.6, 'density': 0.6},
    2: {'name': 'Upper Ward', 'types': ['noble', 'castle', 'administration'],
        'building_quality': 0.9, 'density': 0.4},
}
```

### 5.2 Cliff-Side Building Placement

```python
def place_cliff_buildings(terrain, cliff_edges, building_templates):
    """
    Place buildings carved into or hanging from cliff faces.
    Reference: Markarth (Skyrim), Rito Village (BotW).
    """
    buildings = []

    for edge in cliff_edges:
        cliff_normal = edge.outward_normal  # points away from cliff face
        cliff_height = edge.top_elevation - edge.bottom_elevation

        # Subdivide cliff face into vertical zones
        num_levels = int(cliff_height / 4.0)  # ~4m per level
        for level in range(num_levels):
            y = edge.bottom_elevation + level * 4.0

            # Carve into cliff: building extends INTO the rock
            if random() < 0.6:  # 60% carved
                b = Building(
                    type='carved_dwelling',
                    position=edge.point_at_height(y) + cliff_normal * 1.0,
                    depth_into_cliff=3.0 + random() * 5.0,  # 3-8m deep
                    width=4.0 + random() * 4.0,
                    height=3.5,
                    facade_style='cliff_face_with_door_window',
                    has_balcony=random() < 0.3
                )
            else:  # 40% hanging/cantilevered
                b = Building(
                    type='cantilevered_dwelling',
                    position=edge.point_at_height(y),
                    overhang=2.0 + random() * 3.0,  # 2-5m out from cliff
                    support='wooden_brackets' if level < 3 else 'stone_corbels',
                    width=3.0 + random() * 3.0,
                    height=3.5
                )

            buildings.append(b)

        # Place connecting walkways along cliff face
        if num_levels > 1:
            walkway = CliffWalkway(
                edge=edge,
                width=1.5,
                style='carved_ledge' if random() < 0.5 else 'wooden_platform',
                railing='wooden_rail',
                connects_levels=range(num_levels)
            )
            buildings.append(walkway)

    return buildings
```

### 5.3 Underground Sections

```python
def generate_underground(city, terrain):
    """Generate sewers, catacombs, and basements beneath the city."""
    underground = UndergroundNetwork()

    # Layer 1: Basements (-3m to 0m)
    for building in city.buildings:
        if building.type in ['warehouse', 'tavern', 'manor_house', 'guild_hall']:
            basement = Basement(
                footprint=building.footprint.shrink(0.5),  # slightly smaller
                depth=-3.0,
                access=TrapdoorOrStairs(position=building.interior_corner),
                has_secret_passage=random() < 0.1  # 10% chance
            )
            underground.add(basement, layer=0)

    # Layer 2: Sewers (-6m to -3m) -- follow major roads
    for road in city.major_roads:
        sewer = SewerTunnel(
            path=road.centerline,
            width=2.5,
            height=2.0,
            depth=-5.0,
            style='arched_stone',
            water_channel_width=1.0
        )
        underground.add(sewer, layer=1)

    # Connect sewers at intersections
    for intersection in city.road_intersections:
        junction = SewerJunction(
            position=intersection.position,
            depth=-5.0,
            room_radius=3.0,
            connecting_tunnels=intersection.road_count
        )
        underground.add(junction, layer=1)

    # Layer 3: Catacombs (-12m to -6m) -- beneath religious district
    cathedral_district = city.get_district('Cathedral')
    if cathedral_district:
        catacomb = generate_catacomb_network(
            bounds=cathedral_district.bounds,
            depth=-9.0,
            style='roman_catacomb',
            corridor_width=1.5,
            niche_spacing=1.0,  # burial niches every 1m
            room_count=5 + int(random() * 10),
            connectivity=0.3  # 30% of possible connections exist
        )
        underground.add(catacomb, layer=2)

    # Connect layers via vertical shafts
    for sewer_junction in underground.layer(1).junctions:
        if random() < 0.2:  # 20% of junctions connect down
            shaft = VerticalShaft(
                position=sewer_junction.position,
                top_depth=-5.0,
                bottom_depth=-9.0,
                style='ladder' if random() < 0.7 else 'spiral_stair'
            )
            underground.add_connection(shaft, from_layer=1, to_layer=2)

    return underground
```

### 5.4 Bridge Placement Within Cities

```python
def place_city_bridges(city, rivers, canyons):
    """Place bridges where roads cross water or gaps."""
    bridges = []

    for road in city.all_roads:
        # Check river crossings
        for river in rivers:
            crossing = road.intersection_with(river.centerline)
            if crossing:
                width = river.width_at(crossing)
                bridge = Bridge(
                    position=crossing,
                    span=width + 2.0,  # 1m overhang each side
                    width=road.width,
                    style=select_bridge_style(width, road.hierarchy),
                    height_above_water=2.0 + width * 0.1  # taller for wider rivers
                )
                bridges.append(bridge)

        # Check canyon/gap crossings
        for canyon in canyons:
            crossing = road.intersection_with(canyon.edge)
            if crossing:
                gap = canyon.width_at(crossing)
                bridge = Bridge(
                    position=crossing,
                    span=gap,
                    style='stone_arch' if gap < 15 else 'suspension_wooden',
                    supports=max(1, int(gap / 10))  # support pillar every 10m
                )
                bridges.append(bridge)

    return bridges

BRIDGE_STYLES = {
    'small_stone':    {'max_span': 8,  'min_road': 'alley',    'arch_count': 1},
    'stone_arch':     {'max_span': 20, 'min_road': 'secondary','arch_count': 'span/8'},
    'covered_wooden': {'max_span': 15, 'min_road': 'secondary','style': 'medieval'},
    'grand_stone':    {'max_span': 40, 'min_road': 'main',     'arch_count': 'span/6',
                       'has_shops': True, 'width': 'road_width * 2'},
    'drawbridge':     {'max_span': 10, 'min_road': 'main',     'at_gate': True},
}
```

---

## 6. Defensive Settlement Layout

### 6.1 Motte-and-Bailey Generation

```python
def generate_motte_and_bailey(terrain, position, size='medium'):
    """
    Generate a motte-and-bailey castle complex.

    Historical specs:
    - Motte: artificial hill, 5-10m high, 30-90m diameter at base
    - Bailey: enclosed courtyard, 1-3 baileys typical
    - Palisade/wall surrounding both
    - Ditch around perimeter (2-4m deep, 3-6m wide)
    """
    params = MOTTE_PARAMS[size]  # small/medium/large

    # 1. Place motte (highest natural point or create artificial mound)
    best_pos = find_highest_nearby(terrain, position, search_radius=50)
    motte = Motte(
        center=best_pos,
        base_radius=params['motte_radius'],      # 15-45m
        top_radius=params['motte_radius'] * 0.4,  # 40% of base
        height=params['motte_height'],             # 5-10m
        slope_angle=40,                            # degrees, steep but climbable
    )

    # 2. Place keep on motte top
    keep = Keep(
        position=motte.top_center,
        footprint_radius=motte.top_radius * 0.7,
        height=params['keep_height'],  # 8-15m
        style='square_tower' if random() < 0.6 else 'round_tower',
        walls_thickness=2.0,  # meters
    )

    # 3. Generate bailey(s)
    baileys = []
    num_baileys = params['num_baileys']  # 1-3

    for i in range(num_baileys):
        angle = i * (360 / num_baileys) + random() * 30  # spread around motte
        distance = motte.base_radius + 20 + i * 30
        bailey_center = motte.center + polar_to_cart(distance, angle)

        bailey = Bailey(
            center=bailey_center,
            radius=params['bailey_radius'] - i * 10,  # inner baileys smaller
            shape='irregular_oval',
            enclosed_buildings=generate_bailey_buildings(i, params)
        )
        baileys.append(bailey)

    # 4. Perimeter defenses
    all_points = [motte.center] + [b.center for b in baileys]
    perimeter = compute_convex_hull(all_points, padding=10)

    defense = Defenses(
        wall=Palisade(
            path=perimeter,
            height=3.5,  # timber palisade
            material='wooden_stakes',
            thickness=0.3
        ),
        ditch=Ditch(
            path=perimeter.offset(5),  # 5m outside wall
            width=params['ditch_width'],   # 3-6m
            depth=params['ditch_depth'],   # 2-4m
        ),
        gate=Gate(
            position=perimeter.point_furthest_from(motte.center),
            width=3.0,
            has_drawbridge=params['has_drawbridge'],
            tower_count=2
        )
    )

    return MotteAndBailey(motte, keep, baileys, defense)

MOTTE_PARAMS = {
    'small':  {'motte_radius': 15, 'motte_height': 5, 'keep_height': 8,
               'num_baileys': 1, 'bailey_radius': 30, 'ditch_width': 3,
               'ditch_depth': 2, 'has_drawbridge': False},
    'medium': {'motte_radius': 25, 'motte_height': 7, 'keep_height': 12,
               'num_baileys': 2, 'bailey_radius': 45, 'ditch_width': 4,
               'ditch_depth': 3, 'has_drawbridge': True},
    'large':  {'motte_radius': 40, 'motte_height': 10, 'keep_height': 15,
               'num_baileys': 3, 'bailey_radius': 60, 'ditch_width': 6,
               'ditch_depth': 4, 'has_drawbridge': True},
}
```

### 6.2 Concentric Walled City Growth

```python
def generate_concentric_walled_city(terrain, center, growth_stages=4):
    """
    Simulates historical concentric wall expansion.

    Historical pattern:
    Stage 0: Castle/keep on hilltop
    Stage 1: First wall (inner bailey) ~100m radius -- 50-100 buildings
    Stage 2: Second wall ~250m radius -- 500-1000 buildings
    Stage 3: Third wall ~500m radius -- 2000-5000 buildings
    Stage 4: Suburbs outside walls -- unlimited

    Real examples: Carcassonne, Paris, Vienna, London
    """
    city = ConcentricCity(center=center, terrain=terrain)

    WALL_RADII = [0, 80, 200, 400, 700]  # meters per stage
    WALL_HEIGHTS = [0, 5, 8, 10, 12]     # wall height increases over time
    TOWER_SPACING = [0, 30, 40, 50, 60]  # meters between towers

    for stage in range(growth_stages + 1):
        if stage == 0:
            # Place castle at center (highest point)
            city.castle = generate_castle(center, terrain)
            continue

        radius = WALL_RADII[stage]

        # Generate wall following terrain (not perfect circle)
        wall_path = generate_organic_wall(
            center=center,
            target_radius=radius,
            terrain=terrain,
            irregularity=0.15,  # 15% deviation from circle
            follow_ridges=True,  # walls prefer high ground
            avoid_water=True
        )

        # Place towers
        towers = place_wall_towers(
            wall_path,
            spacing=TOWER_SPACING[stage],
            corner_towers=True,  # always at sharp turns
            styles=['round', 'square', 'D_shaped']
        )

        # Place gates (2-6 per wall ring)
        num_gates = min(2 + stage, 6)
        gates = place_gates(
            wall_path,
            num_gates=num_gates,
            prefer_road_directions=True,
            gate_styles=['simple_arch', 'twin_tower', 'barbican']
        )

        wall = CityWall(
            path=wall_path,
            height=WALL_HEIGHTS[stage],
            thickness=1.5 + stage * 0.5,
            towers=towers,
            gates=gates,
            has_walkway=stage >= 2,
            has_crenellations=True
        )
        city.walls.append(wall)

        # Fill area between this wall and previous with buildings
        if stage >= 2:
            inner_wall = city.walls[-2].path
        else:
            inner_wall = city.castle.perimeter

        ring_area = compute_ring_area(inner_wall, wall_path)
        roads = generate_roads_in_ring(ring_area, gates, city.center)
        blocks = roads_to_blocks(roads)

        # Ward assignment based on distance from center
        for block in blocks:
            d = distance(centroid(block), center) / radius
            if d < 0.3:
                block.ward = 'noble' if stage <= 2 else 'merchant'
            elif d < 0.6:
                block.ward = 'merchant' if stage <= 2 else 'craftsmen'
            else:
                block.ward = 'craftsmen' if stage <= 2 else 'residential'

        city.rings.append(CityRing(wall, roads, blocks, stage))

    return city

def generate_organic_wall(center, target_radius, terrain, irregularity, **kwargs):
    """Generate a wall that follows terrain rather than being a perfect circle."""
    num_points = 64
    wall_points = []
    for i in range(num_points):
        angle = 2 * pi * i / num_points

        # Base radius with noise
        r = target_radius * (1 + (perlin_noise_1d(angle * 3) * irregularity))

        # Follow ridgelines (prefer high ground)
        if kwargs.get('follow_ridges'):
            for offset in [-10, -5, 0, 5, 10]:
                test_r = r + offset
                test_pos = center + polar_to_cart(test_r, angle)
                test_elevation = terrain.sample(test_pos)
                if test_elevation > terrain.sample(center + polar_to_cart(r, angle)):
                    r = test_r

        # Avoid water
        pos = center + polar_to_cart(r, angle)
        if kwargs.get('avoid_water') and terrain.is_water(pos):
            while terrain.is_water(pos) and r > target_radius * 0.5:
                r -= 5
                pos = center + polar_to_cart(r, angle)

        wall_points.append(pos)

    return smooth_polyline(wall_points, iterations=2)
```

### 6.3 Kill Zone and Chokepoint Design

```python
def design_gate_defense(gate, wall, terrain):
    """
    Design defensive features around a city gate.

    Historical kill zone elements:
    1. Barbican: outer fortification before gate
    2. Murder holes: openings above passage for dropping projectiles
    3. Arrow loops: narrow slits in walls for archers
    4. Bent entrance: L-shaped passage forcing attackers to turn
    5. Ditch/moat before gate
    6. Open killing ground: clear area with no cover
    """
    defense = GateDefense(gate=gate)

    # Killing ground: 30-50m clear zone outside gate
    defense.killing_ground = ClearZone(
        center=gate.exterior_position,
        radius=40,
        shape='semicircle',
        side='exterior',
        slope='gentle_upward_toward_gate'  # attackers run uphill
    )

    # Barbican: forward fortification
    defense.barbican = Barbican(
        position=gate.exterior_position + gate.outward_normal * 20,
        width=8,
        depth=12,
        wall_height=wall.height + 2,  # taller than main wall
        has_own_gate=True,
        gate_offset=True  # barbican gate not aligned with main gate (bent entry)
    )

    # Bent entrance (L-shaped or Z-shaped passage)
    defense.passage = BentPassage(
        length=15,
        width=3,  # only 3m wide -- restricts battering ram use
        turns=1 if gate.importance == 'minor' else 2,
        turn_angle=90,
        ceiling_height=4,
        murder_holes=True,  # every 2m along passage
        arrow_loops=True,   # every 3m, alternating sides
        portcullis_count=2  # one at each end of passage
    )

    # Flanking towers
    defense.towers = [
        FlankingTower(
            position=gate.position + perpendicular * (wall.thickness + 3),
            height=wall.height + 5,
            shape='D_shaped',  # flat interior, curved exterior
            arrow_loops_per_level=4,
            levels=3
        )
        for perpendicular in [gate.left_normal, gate.right_normal]
    ]

    # Ditch/moat
    defense.moat = Moat(
        path=gate.exterior_arc(radius=25, arc_angle=180),
        width=6,
        depth=3,
        has_water=terrain.water_table_high,
        drawbridge=Drawbridge(width=gate.width, length=7)
    )

    return defense
```

### 6.4 Historical Medieval City Growth Patterns

**Implementable rules derived from real medieval cities:**

```python
MEDIEVAL_GROWTH_RULES = {
    'founding': {
        'trigger': 'initial',
        'elements': ['castle_or_manor', 'church', 'market_cross', 'well'],
        'road_pattern': 'single_main_road',
        'population': '50-200',
        'note': 'Castle on high ground, church nearby, market at crossroads'
    },
    'early_growth': {
        'trigger': 'population > 200',
        'elements': ['first_palisade', 'mill', 'smithy', 'inn'],
        'road_pattern': 'main_road + 2-3 side streets',
        'building_material': 'wattle_and_daub, thatch_roof',
        'note': 'Buildings cluster along main road, organic growth'
    },
    'town_charter': {
        'trigger': 'population > 500',
        'elements': ['stone_wall', 'market_square', 'guild_halls', 'bridge'],
        'road_pattern': 'radial_from_market + ring_road_inside_walls',
        'building_material': 'timber_frame, stone_foundations',
        'note': 'Walls define boundary, gates become economic chokepoints'
    },
    'prosperous_town': {
        'trigger': 'population > 2000',
        'elements': ['cathedral', 'second_wall', 'multiple_churches', 'hospital'],
        'road_pattern': 'complex_organic + main_arterials',
        'building_material': 'stone_lower, timber_upper, tile_roofs',
        'suburbs': 'craftsmen and traders outside walls near gates',
        'note': 'Suburbs grow outside walls, eventually enclosed by new wall'
    },
    'major_city': {
        'trigger': 'population > 10000',
        'elements': ['third_wall', 'university', 'palace', 'multiple_markets'],
        'road_pattern': 'concentric_rings + radial_arterials',
        'districts': 'clearly_defined_by_trade_and_class',
        'note': 'River becomes key for trade; waterfront warehouses and docks'
    }
}

# Key placement rules observed in real medieval cities:
PLACEMENT_RULES = [
    "Castle/lord's seat ALWAYS on highest defensible ground",
    "Church within 100m of market square (soul + commerce)",
    "Market at main crossroads or widest point of main road",
    "Tanners, dyers, butchers DOWNWIND and DOWNSTREAM (pollution)",
    "Mills at river with sufficient fall (need water power)",
    "Jewish quarter often near castle (lord's protection) but segregated",
    "Monastery outside walls but within suburb zone",
    "Cemetery attached to church, within walls",
    "Gallows/execution site outside walls, visible from main road",
    "Leper hospital outside walls, downwind",
    "Inns cluster near gates (travelers arrive late, can't enter after curfew)",
    "Wealthy merchants on main street near market",
    "Poor housing in alleys behind main street buildings",
    "Stables and animal pens near gates (manure removal)",
    "Well/fountain at every major intersection",
    "Grain storage inside walls (siege protection)",
]
```

---

## 7. CGA Shape Grammar (CityEngine Pattern)

For building facade and mass generation, the CGA approach is highly implementable:

```python
# CGA-style shape grammar for building generation

def Lot(shape, params):
    """Start rule: extrude lot into building mass."""
    height = params.floors * params.floor_height
    return extrude(shape, height) >> Envelope

def Envelope(shape, params):
    """Split building mass into components."""
    return comp(shape, {
        'front': FrontFacade,
        'back': BackFacade,
        'left': SideFacade,
        'right': SideFacade,
        'top': Roof
    })

def FrontFacade(shape, params):
    """Split front face into floors."""
    return split_y(shape, [
        (params.ground_floor_height, GroundFloor),
        ('~', lambda s: repeat_y(s, params.floor_height, UpperFloor)),
        (params.cornice_height, Cornice)
    ])

def GroundFloor(shape, params):
    """Ground floor: doors, shop windows."""
    return split_x(shape, [
        (params.pillar_width, Pilaster),
        ('~', lambda s: split_x(s, [
            (params.door_width, Door),
            ('~', ShopWindow),
        ])),
        (params.pillar_width, Pilaster),
    ])

def UpperFloor(shape, params):
    """Upper floor: windows with spacing."""
    return split_x(shape, [
        (params.pillar_width, Wall),
        ('~', lambda s: repeat_x(s, params.window_spacing, WindowBay)),
        (params.pillar_width, Wall),
    ])

def WindowBay(shape, params):
    """Single window bay: wall-window-wall."""
    return split_x(shape, [
        ('~', Wall),
        (params.window_width, split_y(shape, [
            ('~', Wall),
            (params.window_height, Window),
            ('~', Wall),
        ])),
        ('~', Wall),
    ])

def Roof(shape, params):
    """Generate roof from footprint."""
    style = random.choice(['gable', 'hip', 'flat', 'mansard'],
                          weights=[0.4, 0.3, 0.1, 0.2])
    if style == 'gable':
        return roof_gable(shape, angle=35 + random() * 15)  # 35-50 degrees
    elif style == 'hip':
        return roof_hip(shape, angle=30 + random() * 10)
    elif style == 'mansard':
        return roof_mansard(shape, lower_angle=70, upper_angle=30)
    else:
        return roof_flat(shape, parapet_height=0.5)

# Parameters by building class:
BUILDING_PARAMS = {
    'medieval_common': {
        'floors': (1, 3), 'floor_height': 2.8, 'ground_floor_height': 3.2,
        'window_width': 0.6, 'window_height': 0.9, 'window_spacing': 2.5,
        'door_width': 1.2, 'pillar_width': 0.4, 'cornice_height': 0.3,
        'materials': ['timber_frame', 'wattle_daub', 'plaster'],
        'roof_material': 'thatch'
    },
    'medieval_wealthy': {
        'floors': (2, 4), 'floor_height': 3.2, 'ground_floor_height': 3.8,
        'window_width': 0.8, 'window_height': 1.2, 'window_spacing': 2.0,
        'door_width': 1.5, 'pillar_width': 0.5, 'cornice_height': 0.5,
        'materials': ['stone', 'carved_timber', 'stucco'],
        'roof_material': 'slate_tile'
    },
    'medieval_shop': {
        'floors': (2, 3), 'floor_height': 2.8, 'ground_floor_height': 3.5,
        'shop_front_width': 3.0, 'awning': True, 'upper_overhang': 0.5,
        'materials': ['timber_frame', 'brick_infill'],
        'roof_material': 'clay_tile'
    }
}
```

---

## 8. Implementation Priority for VeilBreakers Toolkit

### Recommended Build Order:

1. **Tensor Field Roads** (highest ROI -- natural-looking, easy to combine)
2. **OBB Lot Subdivision** (well-defined algorithm, direct implementation)
3. **Voronoi District Generation** (Watabou pipeline -- proven, 6-stage)
4. **CGA Building Facades** (shape grammar for variety at scale)
5. **WFC Building Interiors** (module-based, constraint-driven)
6. **Concentric Wall Growth** (historical simulation)
7. **Vertical City Tiers** (Skyrim-style elevation bands)
8. **Underground Networks** (sewers follow roads, catacombs follow districts)

### Key Insight from Cyberpunk 2077:
Night City was NOT procedurally generated. CD Projekt RED hand-built everything
because "quality comes first." However, their prefab-based hierarchy system
(modular building kits assembled into blocks) IS procedural-adjacent and is
exactly how our toolkit should work: procedural layout + curated modular pieces.

### Key Insight from Assassin's Creed:
Ubisoft uses **modular architectural kits** per cultural style (Abbasid for Baghdad,
Gothic for Paris, etc). The kits contain walls, columns, arches, windows, roofs as
separate meshes that snap together. This is the same approach as WFC modules
but with hand-authored quality.

### Key Insight from Townscaper:
Oskar Stalberg's innovation: use an **irregular grid** (not square) for more organic
feel. The WFC constraint solving + marching cubes mesh generation produces
architecture that hides its procedural origins. ~100 hand-made blocks are enough
for entire cities.

---

## Sources

- [Parish & Muller - Procedural Modeling of Cities (2001)](https://cgl.ethz.ch/Downloads/Publications/Papers/2001/p_Par01.pdf)
- [Chen et al. - Interactive Procedural Street Modeling (2008)](https://www.sci.utah.edu/~chengu/street_sig08/street_project.htm)
- [Martin Devans - Procedural Generation: Roads](https://martindevans.me/game-development/2015/12/11/Procedural-Generation-For-Dummies-Roads/)
- [Martin Devans - Procedural Generation: Lot Subdivision](https://martindevans.me/game-development/2015/12/27/Procedural-Generation-For-Dummies-Lots/)
- [Watabou TownGeneratorOS (DeepWiki)](https://deepwiki.com/watabou/TownGeneratorOS)
- [Watabou Medieval Fantasy City Generator](https://watabou.github.io/city.html)
- [mxgmn Wave Function Collapse](https://github.com/mxgmn/WaveFunctionCollapse)
- [Robert Heaton - WFC Explained](https://robertheaton.com/2018/12/17/wavefunction-collapse-algorithm/)
- [Boris the Brave - WFC Tips and Tricks](https://www.boristhebrave.com/2020/02/08/wave-function-collapse-tips-and-tricks/)
- [Marian42 - Infinite WFC City](https://marian42.de/article/wfc/)
- [How Townscaper Works](https://www.gamedeveloper.com/game-platforms/how-townscaper-works-a-story-four-games-in-the-making)
- [Skyrim Cities Design Excerpts](https://en.uesp.net/wiki/General:Skyrim_Cities'_Design_Excerpts)
- [Exploring Skyrim Architecture: Whiterun](https://mydeerestdivine.medium.com/exploring-skyrims-architecture-whiterun-8b49bceb7352)
- [CityEngine CGA Shape Grammar](https://doc.arcgis.com/en/cityengine/latest/tutorials/tutorial-6-basic-shape-grammar.htm)
- [Procedural Cities Survey Paper](https://www.citygen.net/files/images/Procedural_City_Generation_Survey.pdf)
- [Procedural Generation of Parcels (Purdue)](https://www.cs.purdue.edu/cgvlab/papers/aliaga/eg2012.pdf)
- [phiresky Procedural Cities Comparison](https://github.com/phiresky/procedural-cities/blob/master/paper.md)
- [Building Night City (GDC)](https://www.gdcvault.com/play/1028734/Building-Night-City-The-Technology)
- [AC Mirage Baghdad Architecture](https://news.ubisoft.com/en-us/article/YJZekvzJH1XyKlygfhSbF/assassins-creed-mirage-building-an-authentic-baghdad)
- [SideFX Houdini Procedural City Tutorials](https://www.sidefx.com/tutorials/procedural-city-1-building-generator/)
- [No Man's Sky Procedural Generation](https://nomanssky.fandom.com/wiki/Procedural_generation)
- [ShaanKhan - WFC + BSP Dungeon Generation](https://medium.com/@ShaanCoding/implementing-wave-function-collapse-binary-space-partitioning-for-procedural-dungeon-generation-2f1a6cc376db)
