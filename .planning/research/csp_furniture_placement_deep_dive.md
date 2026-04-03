# CSP Furniture Placement Deep Dive - Research

**Researched:** 2026-04-02
**Domain:** Constraint Satisfaction Problems for procedural interior layout
**Confidence:** HIGH (algorithms) / MEDIUM (performance estimates) / HIGH (integration path)

## Summary

The VeilBreakers interior layout system in `_building_grammar.py` currently uses a **4-phase random-retry approach**: focal points on walls, clustered items around anchors, remaining wall/corner items, and door corridor validation. Each phase uses random position sampling with up to 50 retry attempts per item and AABB collision checks. This produces acceptable results but has fundamental limitations: no backtracking across phases, no constraint propagation between items, placement order is hardcoded rather than optimized, and failure at one phase cannot revise earlier decisions.

A proper CSP solver would replace the random-retry loops with systematic backtracking search enhanced by constraint propagation (AC-3/MAC), variable ordering heuristics (MRV -- most constrained first), and domain ordering (prefer wall-adjacent positions). The existing data structures -- `ROOM_SPATIAL_GRAPHS`, `ROOM_ACTIVITY_ZONES`, `_ROOM_CONFIGS` -- map almost directly to CSP variables, domains, and constraints. The upgrade path is incremental: the CSP solver can be a drop-in replacement for `generate_interior_layout()` using identical input/output formats.

**Primary recommendation:** Build a custom lightweight CSP solver (~300 lines) tailored to 2D rectangular placement rather than using a generic library. The problem has specialized spatial structure (AABB collision, wall adjacency, clearance zones) that generic CSP libraries handle poorly. Discretize the room into a grid (0.1m resolution) for finite domains, apply unary constraints for zone restrictions and wall preferences, then binary constraints for non-overlap and facing relationships.

---

## Research Mission 1: CSP for Game Content Generation

### Academic & Industry Approaches

#### Constraint-Based Layout Synthesis (Academic)

The foundational approach comes from **"Make it Home: Automatic Optimization of Furniture Arrangement"** (Yu et al., SIGGRAPH 2011). Their system:
- Extracts hierarchical and spatial relationships between furniture objects
- Encodes ergonomic factors (visibility, accessibility, facing direction) into a cost function
- Optimizes via **simulated annealing** with Metropolis-Hastings sampling
- Cost function terms: pairwise alignment, wall clearance, accessibility paths, functional grouping

**Key insight:** They found that pure CSP (hard constraints only) produces valid but unnatural layouts. The best results combine **hard constraints** (no overlap, in-bounds, door clearance) with **soft constraints** as cost function terms (prefer near-wall, prefer facing direction, activity zone preference). This is directly applicable to VeilBreakers.

Confidence: HIGH (SIGGRAPH peer-reviewed paper, widely cited)

#### pvigier's Room Generation CSP (2022)

A practical game-oriented implementation documented at pvigier.github.io:
- Variables = objects/object groups to place
- Domains = all valid grid positions per object
- Constraints: no-overlap (baked into solver), wall distance, corner placement, connectivity (reachable paths)
- Solver: backtracking with **Minimum Remaining Values (MRV)** heuristic
- Performance trick: connectivity check uses DFS only when surrounding tiles fragment
- Randomization: shuffle domains each run for variety

Confidence: HIGH (working implementation with documented results)

#### "Method for Automatic Furniture Placement Based on Simulated Annealing and Genetic Algorithm" (2021)

- Uses simulated annealing for functional zone distribution
- Genetic algorithm for furniture placement within zones
- Handles non-rectangular rooms (L-shaped, T-shaped)
- Two-level optimization: macro (zone layout) then micro (furniture in zones)

Confidence: MEDIUM (academic paper, not directly verified)

### How Shipped Games Do It

#### Shadows of Doubt (ColePowered Games)

The most detailed publicly documented system for procedural furnished interiors:
- **Tile-based grid:** 1.8m x 1.8m tiles, building floors are 15x15 tiles
- **Hierarchical placement:** City > District > Block > Building > Floor > Address > Room > Tile
- **Room placement algorithm:**
  1. Cycle through room types ordered by importance (living room first)
  2. For each room: test every available space, rank by score, pick best
  3. Ranking criteria: floor space (prefer larger), uniform shape (minimize corners), window access
- **Constraint rules:**
  - Certain rooms can only connect to certain other rooms (kitchen -> living room)
  - Bathrooms limited to single door
  - Entrance doors cannot open into bedrooms
  - Excess floorspace redistributed via override system
- **Furniture:** Placed after room shapes are finalized, within room tile constraints

Confidence: HIGH (developer blog with implementation details)

#### The Sims

The Sims uses a constraint-based system where:
- Furniture has registered "sides" (front, back, left, right)
- Placement connects specified related sides at specified distances
- Overlap checking and clearance areas around furniture (and doors/windows) enforced
- Grid-snapped placement (0.5 tile increments)
- The system is closer to a rule engine than a full CSP solver

Confidence: MEDIUM (no official algorithm documentation; inferred from developer talks and modding documentation)

#### Dwarf Fortress

Dwarf Fortress does NOT use procedural furniture placement in the traditional sense:
- Rooms are defined FROM a piece of furniture (a bed defines a bedroom)
- Room quality = total value of contents + walls + floors
- Furniture placement is player-directed, not algorithm-driven
- Procedural generation handles dungeon layout, not interior decoration

Confidence: HIGH (well-documented in wiki, but not applicable to our problem)

### Key Takeaway

The most successful game implementations use a **hybrid approach**:
1. **Hard constraints** solved first (no overlap, in bounds, door clearance) via backtracking/CSP
2. **Soft constraints** optimized second (aesthetic quality, zone preference, facing) via scoring/annealing
3. **Grid discretization** for finite domains (0.1m-0.5m resolution depending on game)
4. **Hierarchical placement** (zones first, then furniture within zones)

---

## Research Mission 2: CSP Solver Design for VeilBreakers

### Variable Definition

Each furniture item in a room = one CSP variable.

```python
@dataclass
class FurnitureVariable:
    item_id: str          # "table_0", "chair_1", etc.
    item_type: str        # "table", "chair", "bed"
    size: tuple[float, float]  # (width, depth) in meters
    height: float         # vertical extent
    placement_rule: str   # "wall", "center", "corner" from _ROOM_CONFIGS
    
    # Derived from ROOM_SPATIAL_GRAPHS
    is_focal: bool        # Phase 1 focal point
    cluster_anchor: str | None  # Which anchor this clusters around
    face_anchor: bool     # Should face its cluster anchor
    wall_pref: str        # "back", "side", "front", "any"
```

### Domain Definition

Each variable's domain = set of valid (x, y, rotation) tuples.

**Grid discretization approach** (recommended for VeilBreakers):
- Room discretized at 0.1m resolution (a 6x8m room = 60x80 = 4,800 cells)
- Rotation discretized to 4 values: 0, pi/2, pi, 3*pi/2
- Domain per item = grid cells x rotations, pruned by unary constraints
- A 6x8m room with 4 rotations = 19,200 domain values per variable BEFORE pruning

**After unary constraint pruning:**
- Wall items: only cells within 0.3m of walls (~15% of grid) = ~2,880
- Center items: cells away from walls (~70% of grid) = ~13,440
- Corner items: 4 corner positions = ~16
- Typical domain after pruning: 500-3,000 positions per item

### Constraint Types

#### Hard Constraints (Must Satisfy)

| Constraint | Type | Description | Implementation |
|-----------|------|-------------|----------------|
| **No overlap** | Binary | AABB of items must not intersect | `abs(x1-x2) >= (w1+w2)/2 AND abs(y1-y2) >= (d1+d2)/2` |
| **In bounds** | Unary | Item must fit within room rectangle | Prune domain during initialization |
| **Door clearance** | Unary | 1.0m corridor from door to room center | Prune domain: exclude corridor cells |
| **Wall adjacency** | Unary | Wall items must touch wall (within 0.3m margin) | Prune domain: keep only wall-adjacent cells |
| **Floor items exempt** | Unary | Items with height < 0.1m (rugs) never collide | Skip overlap constraint for these |

#### Soft Constraints (Scored, Not Required)

| Constraint | Weight | Description | Scoring |
|-----------|--------|-------------|---------|
| **Activity zone** | 0.4 | Item should be in its designated zone | +1.0 if in correct zone, 0.0 otherwise |
| **Wall preference** | 0.3 | Preferred wall side (back, side, front) | +1.0 if on preferred wall |
| **Cluster proximity** | 0.5 | Cluster members within offset_dist of anchor | +1.0 * (1 - dist/max_dist) |
| **Facing direction** | 0.3 | Chairs face tables, thrones face doors | +1.0 if rotation points at target |
| **Density balance** | 0.2 | Not too crowded in any zone, not too empty | Penalty for zone occupancy > 70% or < 10% |
| **Symmetry bonus** | 0.1 | Symmetric placement for formal rooms | +0.5 for mirror-symmetric pairs |

### Solver Algorithm: Backtracking with MAC (Maintaining Arc Consistency)

```
function CSP_SOLVE(variables, domains, constraints):
    if all variables assigned:
        return score_soft_constraints(assignment)
    
    # MRV: pick variable with smallest remaining domain
    var = select_unassigned_variable_MRV(variables, domains)
    
    # Domain ordering: sort by soft constraint score (descending)
    for value in order_domain_values(var, domains):
        if consistent(var, value, constraints):
            assign(var, value)
            # MAC: propagate arc consistency
            pruned = propagate_AC3(var, domains, constraints)
            if no_domain_empty(domains):
                result = CSP_SOLVE(variables, domains, constraints)
                if result is not None:
                    return result
            undo_pruning(pruned, domains)
            unassign(var)
    
    return None  # backtrack
```

### Variable Ordering Heuristics

1. **Large items first** (focal points, beds, tables) -- they are most constrained
2. **Wall items before center items** -- walls have fewer valid positions
3. **Cluster anchors before cluster members** -- members depend on anchor position
4. **MRV tiebreaker** -- among equal-size items, pick the one with fewest remaining positions

This maps directly to the existing 4-phase order but makes it systematic:
- Phase 1 (focal points) = largest items with wall constraints = MRV picks these first
- Phase 2 (clusters) = anchors placed, then members with proximity constraints
- Phase 3 (remaining) = items with most remaining freedom

### Domain Ordering

For each variable, try positions in this order:
1. **Positions in correct activity zone** (from ROOM_ACTIVITY_ZONES)
2. **Positions near preferred wall** (from ROOM_SPATIAL_GRAPHS wall_preferences)
3. **Positions near cluster anchor** (if cluster member)
4. **Corner positions** (for corner-rule items)
5. **Random remaining** (for variety)

---

## Research Mission 3: Python Implementation

### Room, Furniture, and Constraint Representation

```python
@dataclass
class Room:
    width: float
    depth: float
    door_position: tuple[float, float]  # (x, y) of door center
    door_wall: int  # 0=front, 1=back, 2=left, 3=right
    zones: list[ActivityZone]  # from ROOM_ACTIVITY_ZONES

@dataclass
class ActivityZone:
    name: str
    bounds: tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)
    allowed_types: set[str]

@dataclass
class Placement:
    x: float
    y: float
    rotation: int  # 0, 1, 2, 3 (quarter turns)
    
    def aabb(self, width: float, depth: float) -> tuple[float, float, float, float]:
        """Return (x_min, y_min, x_max, y_max) accounting for rotation."""
        if self.rotation % 2 == 0:
            hw, hd = width / 2, depth / 2
        else:
            hw, hd = depth / 2, width / 2
        return (self.x - hw, self.y - hd, self.x + hw, self.y + hd)
```

### Efficient Collision Detection

For 2D rectangular (AABB) placement, the fastest approach for ~20 items:

1. **Brute-force AABB check** (current approach): O(n) per placement check, O(n^2) total. For n=20 items this is 190 checks -- trivially fast.

2. **Grid occupancy bitmap** (recommended for CSP): Discretize room to 0.1m grid, mark cells as occupied. Collision = check if any cell in new item's footprint is marked. O(area) per check but enables fast domain pruning.

```python
import numpy as np

class OccupancyGrid:
    """Fast 2D collision grid at 0.1m resolution."""
    
    def __init__(self, width: float, depth: float, resolution: float = 0.1):
        self.resolution = resolution
        self.cols = int(width / resolution) + 1
        self.rows = int(depth / resolution) + 1
        self.grid = np.zeros((self.rows, self.cols), dtype=np.uint8)
    
    def can_place(self, x: float, y: float, w: float, h: float) -> bool:
        x0 = int((x - w/2) / self.resolution)
        y0 = int((y - h/2) / self.resolution)
        x1 = int((x + w/2) / self.resolution)
        y1 = int((y + h/2) / self.resolution)
        if x0 < 0 or y0 < 0 or x1 >= self.cols or y1 >= self.rows:
            return False
        return np.all(self.grid[y0:y1+1, x0:x1+1] == 0)
    
    def place(self, x: float, y: float, w: float, h: float, item_id: int):
        x0 = int((x - w/2) / self.resolution)
        y0 = int((y - h/2) / self.resolution)
        x1 = int((x + w/2) / self.resolution)
        y1 = int((y + h/2) / self.resolution)
        self.grid[y0:y1+1, x0:x1+1] = item_id
    
    def remove(self, x: float, y: float, w: float, h: float):
        x0 = int((x - w/2) / self.resolution)
        y0 = int((y - h/2) / self.resolution)
        x1 = int((x + w/2) / self.resolution)
        y1 = int((y + h/2) / self.resolution)
        self.grid[y0:y1+1, x0:x1+1] = 0
```

### Handling Rotation

Discretize to 4 orientations (0, 90, 180, 270 degrees):

```python
def rotated_size(w: float, h: float, rotation: int) -> tuple[float, float]:
    """Return effective (width, height) after rotation (0-3 quarter turns)."""
    if rotation % 2 == 0:
        return (w, h)
    return (h, w)
```

For the CSP domain, each position is a (grid_x, grid_y, rotation) triple. Wall items constrained to rotations facing into the room. Center items allow all 4 rotations. Corner items rotation = 0.

### Performance Estimates

**Scenario: 20 items in a 6x8m room, 0.1m grid resolution**

- Grid size: 60 x 80 = 4,800 cells
- 4 rotations per position = 19,200 raw domain values per variable
- After unary pruning (wall/center/corner/bounds/door): ~500-3,000 per variable
- With MRV ordering and AC-3 propagation: typically solves in <1,000 backtracks
- **Estimated time: 5-50ms** for a single room (Python, no Cython)

**Why this is fast enough:**
- Room generation happens at world-build time, not per-frame
- 50ms per room x 20 rooms in a building = 1 second total
- Current random-retry: ~2-10ms per room but with worse results and occasional failures

**Worst case:** Highly constrained rooms (many large items, small room) could take 200-500ms. Add a 100ms timeout with fallback to current random-retry system.

### python-constraint Library Assessment

The `python-constraint` library (PyPI: `python-constraint`, latest: production/stable) provides:
- BacktrackingSolver with constraint propagation
- Built-in AllDifferentConstraint, SomeInSetConstraint, etc.
- Parallel solver (experimental, not recommended)

**Verdict: DO NOT USE for this problem.** Reasons:
1. It operates on discrete enumerated domains -- fine for Sudoku, but spatial placement needs geometric constraints (AABB overlap) that require custom constraint functions
2. Custom constraint functions in python-constraint are called per-pair and cannot share state (like an occupancy grid)
3. No support for soft constraints or scoring
4. Adding spatial awareness would require wrapping every geometric operation in a constraint function, negating the library's simplification
5. A custom solver is ~300 lines and runs faster because it can use the occupancy grid directly

**Better alternative for future consideration:** Google OR-Tools CP-SAT solver -- handles large constraint problems efficiently, but is a heavy dependency. Not needed for 20-item room placement.

---

## Research Mission 4: Integration with VeilBreakers

### Current System Analysis

The existing `_building_grammar.py` system has three key data structures that map directly to CSP concepts:

| Existing Structure | CSP Concept | Mapping |
|-------------------|-------------|---------|
| `_ROOM_CONFIGS` | Variables + Domains | Each tuple = one variable; rule ("wall"/"center"/"corner") = domain type |
| `ROOM_SPATIAL_GRAPHS` | Constraint definitions | focal_points = priority ordering; clusters = proximity constraints; wall_preferences = unary constraints |
| `ROOM_ACTIVITY_ZONES` | Domain partitioning | Zone bounds restrict which positions each item can occupy |

### Current 4-Phase System -> CSP Translation

| Current Phase | CSP Equivalent |
|--------------|----------------|
| Phase 1: Place focal points on preferred walls | Unary constraint (wall_pref) + high MRV priority (large items) |
| Phase 2: Place clustered items near anchors | Binary constraint (proximity to anchor) + facing constraint |
| Phase 3: Place remaining wall/corner items | Unary constraints (wall adjacency, corner position) |
| Phase 4: Door corridor enforcement | Unary constraint (exclude corridor cells from all domains) |

### Integration Architecture

```python
def generate_interior_layout_csp(
    room_type: str,
    width: float,
    depth: float,
    height: float = 3.0,
    seed: int = 0,
    quality_tier: str = "standard",
    occupied_state: str = "inhabited",
) -> list[dict]:
    """CSP-based interior layout -- drop-in replacement for generate_interior_layout().
    
    Returns identical format: list of dicts with type, position, rotation, scale.
    Falls back to original random-retry if CSP times out.
    """
    rng = random.Random(seed)
    config = _ROOM_CONFIGS.get(room_type, [])
    if not config:
        return []
    
    config = _apply_interior_variant(list(config), quality_tier, occupied_state, rng)
    spatial = ROOM_SPATIAL_GRAPHS.get(room_type)
    zones = ROOM_ACTIVITY_ZONES.get(room_type, [])
    
    # Build CSP
    solver = RoomCSPSolver(width, depth, door_wall=0, seed=seed)
    
    # Add variables from config
    for idx, (item_type, rule, base_size, item_height) in enumerate(config):
        priority = _compute_priority(item_type, spatial, idx)
        solver.add_variable(
            f"{item_type}_{idx}",
            item_type=item_type,
            size=base_size,
            height=item_height,
            placement_rule=rule,
            priority=priority,
        )
    
    # Add constraints from spatial graphs
    if spatial:
        for fp in spatial.get("focal_points", []):
            solver.add_wall_preference(fp["type"], fp.get("wall_pref", "any"))
        for cluster in spatial.get("clusters", []):
            solver.add_cluster_constraint(
                cluster["anchor"],
                cluster.get("members", []),
            )
    
    # Add zone constraints
    for zone in zones:
        solver.add_zone_constraint(zone)
    
    # Solve with timeout
    result = solver.solve(timeout_ms=100)
    
    if result is None:
        # Fallback to existing system
        return generate_interior_layout(
            room_type, width, depth, height, seed, quality_tier, occupied_state,
        )
    
    return result
```

### Converting Existing Room Configs to CSP Constraints

The `_ROOM_CONFIGS` tuples `(item_type, rule, (width, depth), height)` map to:

```python
# rule -> domain generation strategy
RULE_TO_DOMAIN = {
    "wall": lambda w, d, margin: wall_adjacent_cells(w, d, margin),
    "center": lambda w, d, margin: interior_cells(w, d, margin),
    "corner": lambda w, d, margin: corner_cells(w, d, margin),
}
```

### Maintaining Dark Fantasy Storytelling

The CSP solver handles furniture placement. Storytelling is applied as a POST-PROCESSING step:

1. **CSP places furniture** (inhabited baseline)
2. **`_apply_interior_variant()` modifies placement** (quality tier: luxury/standard/poor/abandoned/ransacked)
3. **`add_storytelling_props()` adds atmosphere** (cobwebs, bloodstains, scattered papers)
4. **`generate_overrun_variant()` applies corruption** (rubble, vegetation, remains)

**New CSP-aware storytelling rules:**

| Narrative Pattern | CSP Implementation |
|------------------|-------------------|
| Corruption clutter | Post-solve: randomly displace 30-60% of placed items by rotation_jitter |
| Abandoned furniture | Post-solve: remove 40-60% of items, add debris at removed positions |
| Signs of struggle | Post-solve: tip over chairs (rotation += pi/4), scatter items from tables |
| Overturned tables | Post-solve: mark specific items as "tipped", adjust rotation and z-position |

The existing `_INTERIOR_QUALITY_TIERS` and `_INTERIOR_OCCUPIED_STATES` systems remain unchanged -- they modify the config BEFORE the CSP solver runs.

### Multi-Room Constraint Propagation

For connected rooms (hallway -> room -> room):

```python
class BuildingCSPSolver:
    """Coordinate furniture placement across multiple connected rooms."""
    
    def __init__(self, rooms: list[RoomSpec], connections: list[tuple[int, int]]):
        self.rooms = rooms
        self.connections = connections
    
    def solve(self):
        # Phase 1: Solve rooms independently
        room_solutions = []
        for room in self.rooms:
            solver = RoomCSPSolver(room.width, room.depth, ...)
            room_solutions.append(solver.solve())
        
        # Phase 2: Verify cross-room constraints
        for r1_idx, r2_idx in self.connections:
            # Ensure doors align
            # Ensure no furniture blocks connecting doorways
            # Ensure hallway has clear path
            self._verify_connection(room_solutions, r1_idx, r2_idx)
        
        return room_solutions
```

---

## Research Mission 5: Storytelling Through Placement

### Naughty Dog's Environmental Storytelling Principles

From level design studies of The Last of Us Part I and II:

1. **Every space has a purpose** -- environment artists ensure each room tells a story about who lived/worked there
2. **Lived-in feeling** -- spaces are designed to feel uniquely handcrafted with specific inhabitants in mind
3. **Props guide players** -- abandoned signs, lighting, and layout direct player navigation naturally
4. **Iterative process** -- spaces adjusted throughout production by both designers and environment artists

**Key insight for VeilBreakers:** Naughty Dog's approach is handcrafted, not procedural. But their RULES can be proceduralized:
- A desk with papers = someone worked here
- A meal on a table = someone left in a hurry
- A weapon near a body = combat happened here
- Personal effects near a bed = someone lived here

Confidence: MEDIUM (inferred from public analysis, not official algorithm documentation)

### Procedural Environmental Storytelling Rules

#### Corpse Placement Rules

```python
CORPSE_PLACEMENT_RULES = {
    "battle_victim": {
        "near": ["weapon", "shield", "door"],      # Near weapons or exits
        "facing": "away_from_threat",                # Fell facing away
        "props": ["blood_pool", "dropped_weapon"],   # Associated props
    },
    "ambush_victim": {
        "near": ["table", "bed", "chair"],           # Caught unaware
        "facing": "random",                           # Surprised
        "props": ["blood_pool", "scattered_papers"],
    },
    "defender": {
        "near": ["door", "barricade"],               # Defending an entrance
        "facing": "toward_door",                      # Facing the threat
        "props": ["blood_pool", "weapon_in_hand"],
    },
    "last_stand_group": {
        "count": [2, 4],
        "near": ["corner", "back_wall"],             # Pushed to corner
        "facing": "toward_center",
        "props": ["blood_pool", "weapon", "torn_banner"],
    },
}
```

#### Overturned Furniture Patterns

```python
STRUGGLE_PATTERNS = {
    "bar_fight": {
        "tip_chance": {"chair": 0.6, "table": 0.3, "barrel": 0.1},
        "scatter_radius": 1.5,  # meters from original position
        "add_props": ["broken_bottle", "blood_splatter"],
    },
    "ransacked_room": {
        "tip_chance": {"chair": 0.8, "shelf": 0.4, "desk": 0.3},
        "scatter_radius": 2.0,
        "add_props": ["scattered_papers", "broken_pottery", "torn_cloth"],
        "remove_chance": {"bookshelf_contents": 0.9, "shelf_contents": 0.8},
    },
    "hasty_departure": {
        "tip_chance": {"chair": 0.4},
        "scatter_radius": 0.5,
        "add_props": ["open_chest", "scattered_coins", "dropped_bag"],
    },
}
```

#### Abandoned vs Lived-in vs Corrupted Placement Patterns

| State | Furniture | Props | Clutter | Lighting |
|-------|-----------|-------|---------|----------|
| **Lived-in** | All upright, normal positions | Personal effects, food, tools | Moderate (books, items on shelves) | Candles lit, fire burning |
| **Recently abandoned** | Mostly upright, some chairs pushed back | Half-eaten meal, open books | Light (some items left behind) | Candles guttered, fire embers |
| **Long abandoned** | Some toppled, wood rotting | Cobwebs, dust, rat bones | Heavy (debris, collapsed shelves) | Dark, broken fixtures |
| **Ransacked** | Many toppled/moved, drawers open | Broken items, torn fabric | Very heavy (everything scattered) | Knocked-over candelabras |
| **Corrupted** | Some replaced by growths, others merged with walls | Fungal growths, dark ichor, crystalline formations | Organic (roots, tendrils, bone) | Eerie glow, bioluminescence |

#### Procedural "Moments" (Environmental Vignettes)

```python
ENVIRONMENTAL_VIGNETTES = {
    "last_meal": {
        "requires": ["table", "chair"],
        "add_on_table": ["plate", "cup", "half_eaten_bread"],
        "add_on_chair": [],  # chair pushed slightly back
        "chair_offset": (0.0, -0.3),  # pulled away from table
        "narrative": "Someone left mid-meal",
    },
    "letter_on_desk": {
        "requires": ["desk"],
        "add_on_desk": ["letter", "quill", "inkwell"],
        "narrative": "A letter was being written",
    },
    "prayer_at_altar": {
        "requires": ["altar"],
        "add_near_altar": ["prayer_beads", "candle_stub", "offering_bowl"],
        "add_kneeling_corpse": True,
        "narrative": "Someone died praying",
    },
    "last_stand": {
        "requires": ["door"],
        "add_near_door": ["barricade", "overturned_table"],
        "add_weapons": ["sword_on_ground", "shield_battered"],
        "corpse_count": [1, 3],
        "narrative": "Someone barricaded the door",
    },
    "alchemist_experiment": {
        "requires": ["workbench", "cauldron"],
        "add_near_workbench": ["shattered_vial", "burn_marks", "strange_residue"],
        "add_explosion_radius": 1.5,
        "narrative": "An experiment went wrong",
    },
}
```

### Integration with CSP

Vignettes are selected AFTER CSP placement:

1. CSP solver places all furniture
2. For each vignette type, check if required furniture was placed
3. If match found, apply vignette with probability based on room state
4. Vignette props placed relative to the furniture positions CSP determined

```python
def apply_vignettes(
    placed: list[dict],
    room_type: str,
    occupied_state: str,
    seed: int,
) -> list[dict]:
    """Add environmental storytelling vignettes to placed furniture."""
    rng = random.Random(seed + 9999)
    
    # Build lookup of placed item types -> positions
    placed_lookup: dict[str, list[dict]] = {}
    for item in placed:
        placed_lookup.setdefault(item["type"], []).append(item)
    
    vignette_props = []
    for vignette_name, vignette in ENVIRONMENTAL_VIGNETTES.items():
        # Check if required furniture exists
        if all(t in placed_lookup for t in vignette["requires"]):
            # Probability based on occupied state
            chance = {"inhabited": 0.1, "abandoned": 0.4, "ransacked": 0.6, "ruined": 0.3}
            if rng.random() < chance.get(occupied_state, 0.2):
                vignette_props.extend(
                    _generate_vignette_props(vignette, placed_lookup, rng)
                )
    
    return placed + vignette_props
```

---

## Architecture Patterns

### Recommended Module Structure

```
Tools/mcp-toolkit/blender_addon/handlers/
    _building_grammar.py          # Existing: room configs, spatial graphs, zones
    _csp_solver.py                # NEW: CSP solver engine (~300 lines)
    _storytelling_vignettes.py    # NEW: environmental vignettes (~200 lines)
```

### Pattern: Layered Generation Pipeline

```
Input: room_type, dimensions, quality_tier, occupied_state, seed
                          |
                    [1. Config Assembly]
                    _ROOM_CONFIGS + _apply_interior_variant()
                          |
                    [2. CSP Solve]
                    _csp_solver.RoomCSPSolver
                    Hard constraints: overlap, bounds, door, walls
                    Soft constraints: zones, facing, proximity, density
                          |
                    [3. Storytelling Post-Process]
                    apply_vignettes() + add_storytelling_props()
                          |
                    [4. State Mutation]
                    generate_overrun_variant() (if corrupted)
                    rotation_jitter (if abandoned/ransacked)
                          |
Output: list[dict] -- identical format to current system
```

### Anti-Patterns to Avoid

- **Continuous domain CSP:** Do NOT use floating-point positions as domains. Discretize to grid. Continuous CSP is orders of magnitude harder.
- **Global optimization:** Do NOT try to optimize all rooms in a building simultaneously. Solve room-by-room, verify connections after.
- **Over-constraining:** Start with hard constraints only. Add soft constraints as scoring, not as hard constraints -- otherwise the solver may find no solution for unusual room shapes.
- **python-constraint for spatial problems:** The library is designed for combinatorial CSP (Sudoku, scheduling), not geometric placement. Custom solver is both simpler and faster.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSP theory/algorithm | Novel CSP algorithm | Textbook backtracking + AC-3 + MRV | Decades of proven research, edge cases already solved |
| Occupancy grid | Custom 2D array management | NumPy boolean array | Fast vectorized operations, boundary checking built-in |
| AABB collision | Custom overlap math | Keep existing `_check_collision` as validator | Already tested and correct |
| Room discretization | Float-precision grid | Integer grid indices | Avoids floating-point comparison issues entirely |
| Constraint propagation | Custom propagation | Standard AC-3 algorithm | Well-understood O(e*k^3) complexity, simple to implement |

---

## Common Pitfalls

### Pitfall 1: Domain Explosion with Fine Grid Resolution
**What goes wrong:** Using 0.01m resolution turns a 6x8m room into 480,000 cells per variable, making the solver take seconds instead of milliseconds.
**Why it happens:** Temptation to get precise placement.
**How to avoid:** Use 0.1m grid for CSP solving, then jitter final positions by +/- 0.05m for variety. The grid determines which cell an item goes in; exact position within the cell can be randomized.
**Warning signs:** Solver taking >100ms for a standard room.

### Pitfall 2: No Fallback When CSP Fails
**What goes wrong:** CSP solver finds no valid assignment for unusual room dimensions or heavily customized configs.
**Why it happens:** Over-constrained problem (too many large items in a small room).
**How to avoid:** Always keep the existing random-retry system as a fallback. Set a 100ms timeout. If CSP fails, fall back gracefully.
**Warning signs:** CSP returning None for standard room types.

### Pitfall 3: Treating Soft Constraints as Hard Constraints
**What goes wrong:** Making "preferred wall" or "activity zone" into mandatory constraints causes solver failure.
**Why it happens:** Natural inclination to make everything a requirement.
**How to avoid:** Only overlap, bounds, and door clearance are hard constraints. Everything else is a scoring function applied to valid solutions.
**Warning signs:** Solver fails on rooms that the current system handles fine.

### Pitfall 4: Ignoring Rotation in Collision Detection
**What goes wrong:** Checking collision with original dimensions but placing at rotated orientation.
**Why it happens:** Forgetting that a 2.0x0.6m desk rotated 90 degrees occupies 0.6x2.0m.
**How to avoid:** Always compute effective AABB from (size, rotation) pair. The existing `_pick_wall_position` already handles this -- preserve that logic.
**Warning signs:** Items overlapping after rotation.

### Pitfall 5: Breaking Blender Addon Compatibility
**What goes wrong:** Importing numpy or other heavy libraries in the Blender addon context.
**Why it happens:** Blender Python environment may not have all packages.
**How to avoid:** Use pure Python for the CSP solver with an OPTIONAL numpy import for the occupancy grid. Fallback to a list-of-lists grid if numpy unavailable.
**Warning signs:** ImportError when the Blender addon loads.

---

## Code Examples

### Minimal CSP Solver for Room Layout

```python
"""Lightweight CSP solver for 2D rectangular furniture placement.

~300 lines, zero external dependencies (numpy optional for speed).
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field

@dataclass
class FurnitureVar:
    var_id: str
    item_type: str
    width: float
    depth: float
    height: float
    domain: list[tuple[int, int, int]]  # (grid_x, grid_y, rotation)
    priority: int = 0  # higher = place first (MRV tiebreaker)

@dataclass  
class RoomCSP:
    grid_w: int
    grid_h: int
    resolution: float
    variables: list[FurnitureVar] = field(default_factory=list)
    assignment: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    
    # Occupancy grid: 0 = free, >0 = variable index + 1
    grid: list[list[int]] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.grid:
            self.grid = [[0] * self.grid_w for _ in range(self.grid_h)]
    
    def _effective_size(self, var: FurnitureVar, rotation: int) -> tuple[int, int]:
        """Grid cells occupied (width_cells, depth_cells)."""
        w_cells = max(1, round(var.width / self.resolution))
        d_cells = max(1, round(var.depth / self.resolution))
        if rotation % 2 == 1:
            return d_cells, w_cells
        return w_cells, d_cells
    
    def _can_place(self, var: FurnitureVar, gx: int, gy: int, rot: int) -> bool:
        """Check if placement is valid (no overlap, in bounds)."""
        if var.height < 0.1:  # floor items (rugs) never collide
            return True
        wc, dc = self._effective_size(var, rot)
        if gx + wc > self.grid_w or gy + dc > self.grid_h:
            return False
        for dy in range(dc):
            for dx in range(wc):
                if self.grid[gy + dy][gx + dx] != 0:
                    return False
        return True
    
    def _place(self, var_idx: int, var: FurnitureVar, gx: int, gy: int, rot: int):
        """Mark grid cells as occupied."""
        if var.height < 0.1:
            return
        wc, dc = self._effective_size(var, rot)
        marker = var_idx + 1
        for dy in range(dc):
            for dx in range(wc):
                self.grid[gy + dy][gx + dx] = marker
    
    def _unplace(self, var: FurnitureVar, gx: int, gy: int, rot: int):
        """Clear grid cells."""
        if var.height < 0.1:
            return
        wc, dc = self._effective_size(var, rot)
        for dy in range(dc):
            for dx in range(wc):
                self.grid[gy + dy][gx + dx] = 0
    
    def solve(self, timeout_ms: float = 100.0) -> dict[str, tuple[int, int, int]] | None:
        """Backtracking search with MRV ordering."""
        deadline = time.monotonic() + timeout_ms / 1000.0
        # Sort variables: highest priority first, then smallest domain (MRV)
        ordered = sorted(
            range(len(self.variables)),
            key=lambda i: (-self.variables[i].priority, len(self.variables[i].domain)),
        )
        
        if self._backtrack(ordered, 0, deadline):
            return dict(self.assignment)
        return None
    
    def _backtrack(self, order: list[int], depth: int, deadline: float) -> bool:
        if depth == len(order):
            return True
        if time.monotonic() > deadline:
            return False
        
        var_idx = order[depth]
        var = self.variables[var_idx]
        
        for gx, gy, rot in var.domain:
            if self._can_place(var, gx, gy, rot):
                self._place(var_idx, var, gx, gy, rot)
                self.assignment[var.var_id] = (gx, gy, rot)
                
                if self._backtrack(order, depth + 1, deadline):
                    return True
                
                self._unplace(var, gx, gy, rot)
                del self.assignment[var.var_id]
        
        return False
```

### Converting Grid Results to World Coordinates

```python
def grid_to_world(
    gx: int, gy: int, rot: int,
    item_width: float, item_depth: float,
    resolution: float,
) -> tuple[float, float, float]:
    """Convert grid placement to world (x, y, rotation_radians)."""
    import math
    # Grid position is top-left corner; convert to center
    if rot % 2 == 0:
        cx = (gx + item_width / (2 * resolution)) * resolution
        cy = (gy + item_depth / (2 * resolution)) * resolution
    else:
        cx = (gx + item_depth / (2 * resolution)) * resolution
        cy = (gy + item_width / (2 * resolution)) * resolution
    
    rotation_rad = rot * (math.pi / 2)
    return (round(cx, 4), round(cy, 4), round(rotation_rad, 4))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Random placement + collision retry | CSP with backtracking + MRV + MAC | 2020-2025 (academic adoption) | Guarantees valid solutions; enables complex constraints |
| Single cost function (simulated annealing) | Hard+soft constraint hybrid | 2018+ | Better results in constrained spaces |
| Continuous position optimization | Grid-discretized domains | Always been standard for games | Finite domains enable fast CSP solving |
| Per-room isolated placement | Multi-room constraint propagation | 2022+ (Shadows of Doubt et al.) | Connected rooms feel coherent |
| Static furniture sets | Vignette-based storytelling | 2020+ (Last of Us II influence) | Props tell stories, not just fill space |

---

## Open Questions

1. **Grid resolution tradeoff**
   - What we know: 0.1m gives good precision; 0.2m is 4x faster
   - What's unclear: Whether 0.2m resolution causes visible snapping artifacts in Blender
   - Recommendation: Start with 0.1m, profile, increase if too slow

2. **Soft constraint weights**
   - What we know: Need zone preference, facing, proximity, density
   - What's unclear: Exact weight values for dark fantasy aesthetic
   - Recommendation: Make weights configurable per room type, tune empirically

3. **NumPy availability in Blender Python**
   - What we know: Blender bundles NumPy, but custom Python environments may not
   - What's unclear: Whether the Blender addon TCP server context has NumPy available
   - Recommendation: Code with optional NumPy import, fallback to pure Python lists

---

## Sources

### Primary (HIGH confidence)
- [pvigier Room Generation CSP](https://pvigier.github.io/2022/11/05/room-generation-using-constraint-satisfaction.html) - Complete CSP implementation for game rooms
- [Shadows of Doubt DevBlog 13](https://colepowered.com/shadows-of-doubt-devblog-13-creating-procedural-interiors/) - Tile-based procedural interior system
- [python-constraint GitHub](https://github.com/python-constraint/python-constraint) - Library assessment
- [AC-3 Wikipedia](https://en.wikipedia.org/wiki/AC-3_algorithm) - Algorithm reference
- Local codebase: `_building_grammar.py` lines 1884-3104 - Existing system analysis

### Secondary (MEDIUM confidence)
- [Make it Home: Automatic Optimization of Furniture Arrangement](https://dl.acm.org/doi/10.1145/2010324.1964981) - SIGGRAPH 2011 cost function approach
- [Method for Automatic Furniture Placement (SA+GA)](https://link.springer.com/chapter/10.1007/978-3-030-79457-6_41) - Hybrid optimization
- [Constraint Programming in Game Design](https://www.wayline.io/blog/constraint-programming-rethinking-game-design) - CSP in games overview
- [Boris the Brave: Arc Consistency](https://www.boristhebrave.com/2021/08/30/arc-consistency-explained/) - AC-3 visual explanation
- [The Last of Us Level Design Studies](https://medium.com/@ubaidkotwal/the-last-of-us-part-2-level-design-study-364ddaeec36f) - Environmental storytelling analysis

### Tertiary (LOW confidence)
- The Sims placement algorithm details (inferred from modding docs, no official source)
- Performance estimates for Python CSP solver (extrapolated from problem size, not benchmarked)
- Naughty Dog's specific procedural rules (analyzed from public studies, not official)

## Metadata

**Confidence breakdown:**
- CSP algorithm design: HIGH - well-established computer science with proven implementations
- Integration with existing codebase: HIGH - direct examination of current code and data structures
- Performance estimates: MEDIUM - extrapolated from problem size, needs real benchmarking
- Storytelling system design: MEDIUM - inspired by industry analysis, needs gameplay testing
- python-constraint assessment: HIGH - directly examined library capabilities and limitations

**Research date:** 2026-04-02
**Valid until:** 2026-06-02 (algorithms are stable; library versions may change)
