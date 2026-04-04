# Phase 44: Geometry Quality Overhaul -- Props, Environments, Buildings - Research

**Researched:** 2026-04-04
**Domain:** Procedural mesh generation quality, medieval dark fantasy architecture, terrain features, prop detail geometry
**Confidence:** HIGH

## Summary

Phase 44 covers 9 GEOM requirements (GEOM-04 through GEOM-12) plus 2 TEST requirements (TEST-03, TEST-04), targeting the upgrade of all prop, environment, and building geometry from PLACEHOLDER/BASIC quality to DECENT+. The v9.0 53-agent audit found **zero assets scored DECENT or higher** across all 41 tested assets. This phase specifically addresses non-weapon, non-armor, non-creature geometry: props (chest, door, chain, flag, chandelier, etc.), environments (dungeon, cave, terrain), and buildings (castle walls, buildings, rubble).

The codebase already contains substantial infrastructure: a 260-piece modular building kit (`modular_building_kit.py`), castle wall battlements with merlon generation (`building_quality.py`), terrain feature generators (`terrain_features.py`), and riggable prop generators (`riggable_objects.py`). The core problem is not missing code but **insufficient geometry detail** within existing generators. Chests are 102 verts with no iron banding. Doors are 72 verts flat slabs. Dungeons are 3m tall box rooms. Castle walls are 1.5m thick with undersized merlons. Terrain has no micro-undulation, no skirt geometry, and no scree at cliff bases.

**Primary recommendation:** Systematically upgrade each generator's vertex counts, add sub-detail geometry (iron banding, locks, hinges, wood grain for props; stalactites, variable height for environments; proper wall thickness, historical merlons, rubble stones for buildings), and add terrain micro-features. Use the existing `_make_box`, `_make_beveled_box`, `_make_cylinder`, `_make_sphere` helper functions in `procedural_meshes.py` as building blocks. All changes are pure Python mesh generation -- no new dependencies required.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GEOM-04 | Prop detail geometry -- iron banding, locks, hinges, wood grain, rope braid, carved lettering | Current props are 72-2480 verts with no detail. Chest=102v no lock, Door=72v flat slab, Chain=576v uniform, Flag=205v flat plane. All generators in `riggable_objects.py` and `procedural_meshes.py` need detail sub-geometry added. |
| GEOM-05 | Clothing cloth-sim topology -- proper vertex density for deformation, seams, folds | `clothing_system.py` has 12 garment types with cloth_sim vertex groups but tunic scored BASIC (320 verts, not cloth-sim ready). Need higher vertex density (800-4000 target per docstring) and proper edge loop placement at joints. |
| GEOM-06 | Interior furniture quality -- real mesh shapes replacing cube primitives | `procedural_meshes.py` has `generate_table_mesh` and `generate_bed_mesh` using beveled boxes. Interior tavern scored BASIC (box furniture). `_mesh_bridge.py` maps 20+ furniture types to generators. Need richer geometry: turned legs, plank detail, proper mattress. |
| GEOM-07 | Dungeon/cave height variation (3m -> 6-8m+), stalactites, environmental detail, rock meshes | Dungeon handler uses `wall_height=3.0` default. Cave handler uses `wall_height=4.0`. Both in `worldbuilding_layout.py`. Need: increased default heights, stalactite mesh generation, environmental scatter (rubble, puddles, cobwebs). |
| GEOM-08 | Castle wall thickness (1.5m -> 2-3m), gatehouse arches, historical merlon sizing | `_building_grammar.py:generate_castle_spec` uses `wall_thickness=1.5`. `building_quality.py` has merlon_w=0.6, merlon_h=0.8. Historical standard: wall 2-4m thick, merlons follow one-third rule (width=1/3 of crenel+merlon span). Need arch geometry for gatehouse. |
| GEOM-09 | Terrain micro-undulation (5-15cm/m), macro variation, terrain skirt geometry | `environment.py:handle_generate_terrain` generates heightmap with noise but no micro-undulation layer. No terrain skirt mesh exists anywhere in codebase. V9 findings: "perfectly smooth between noise samples." |
| GEOM-10 | Scree/talus at every cliff base, smootherstep on ALL terrain feature transitions | Thermal erosion exists in `terrain_advanced.py` (talus_angle param) but scree MESH generation does not exist. `terrain_features.py` generates canyons/cliffs/arches with NO scree at bases. `smootherstep` function does not exist -- only `smoothstep` in `_shared_utils.py`. |
| GEOM-11 | Chain poly optimization (288 -> 80 tris/link), flag cloth density increase | Chain generator in `riggable_objects.py` uses seg=12, tube=6 for iron style = ~288 tris/link. Need seg=8, tube=4 = ~80 tris/link. Flag is flat plane (205 verts), needs 800+ verts with subdivision for cloth sim. |
| GEOM-12 | Building rubble stone detail, timber framing, roof tile variation, shutters/signs | Building generator in `worldbuilding.py` creates walls/roof/windows but scored PLACEHOLDER (pristine white, no weathering). Missing: rubble stone block surface, exposed timber beams, varied roof tiles, window shutters, hanging shop signs. |
| TEST-03 | Visual regression -- zai before/after for each generator category | Need to use `blender_viewport` action=`contact_sheet` and zai visual analysis tools for before/after comparison on each upgraded generator. |
| TEST-04 | Opus verification scan after every phase -- follow-up rounds until CLEAN | Standard Opus scan protocol after all changes. |
</phase_requirements>

## Standard Stack

### Core (all already in project)

| Library/Module | Location | Purpose | Why Standard |
|----------------|----------|---------|--------------|
| `riggable_objects.py` | `handlers/` | Prop generators (door, chain, flag, chest, cage, chandelier, etc.) | Contains all 10 riggable prop generators needing upgrade |
| `procedural_meshes.py` | `handlers/` | Furniture and detail mesh generators (table, bed, barrel, etc.) | Has `_make_box`, `_make_beveled_box`, `_make_cylinder`, `_make_sphere` helpers |
| `worldbuilding_layout.py` | `handlers/` | Dungeon/cave mesh generation handlers | BSP dungeon + cellular automata cave systems |
| `_building_grammar.py` | `handlers/` | Castle spec generation (walls, towers, keep) | `generate_castle_spec` with box-type ops |
| `building_quality.py` | `handlers/` | Castle wall battlements, stone blocks, arrow slits | Has `_stone_block_grid`, merlon generation, machicolation geometry |
| `worldbuilding.py` | `handlers/` | Building generation handler | `handle_generate_building` composing walls+roof+windows |
| `terrain_features.py` | `handlers/` | Canyon, cliff, arch, geyser, etc. pure-logic generators | Returns MeshSpec dicts (no bpy) |
| `environment.py` | `handlers/` | Terrain generation handler | Heightmap noise + erosion pipeline |
| `clothing_system.py` | `handlers/` | Clothing mesh generation (12 types, 5+ styles each) | Pure-logic quad grid topology |
| `modular_building_kit.py` | `handlers/` | 175 modular pieces (25 types x 5 styles + ruined) | Complete dispatch + assemble system |
| `_shared_utils.py` | `handlers/` | Shared interpolation utilities | Has `smoothstep`, needs `smootherstep` added |
| `_dungeon_gen.py` | `handlers/` | BSP dungeon + cave map generation algorithms | Pure logic for room layout and cave cellular automata |

### Supporting (already in project)

| Library/Module | Location | Purpose | When to Use |
|----------------|----------|---------|-------------|
| `_terrain_noise.py` | `handlers/` | OpenSimplex noise generation | For micro-undulation noise layers on terrain |
| `_terrain_erosion.py` | `handlers/` | Hydraulic + thermal erosion | Already wired into terrain gen |
| `terrain_advanced.py` | `handlers/` | Advanced terrain ops (thermal erosion with talus) | For scree slope angle calculations |
| `weathering.py` | `handlers/` | Weathering systems for materials | For vertex-color based wear on building geometry |
| `_mesh_bridge.py` | `handlers/` | Maps furniture names to generators | Dispatches 20+ furniture types; upgrade target |
| `prop_density.py` | `handlers/` | Prop placement density/quality | Furniture collision + surface placement |

### No New Dependencies Required

This phase is entirely about improving procedural geometry within existing pure-Python generators. No new libraries, packages, or external tools are needed. All mesh generation uses raw vertex/face lists with helper functions already in the codebase.

## Architecture Patterns

### Generator Upgrade Pattern

Every generator in this phase follows the same pattern:

```python
# BEFORE: Simple box-based geometry
outer_v, outer_f = _make_box(0, h/2, 0, hw, h/2, hd)
parts.append((outer_v, outer_f))

# AFTER: Add detail sub-geometry on top of base
outer_v, outer_f = _make_box(0, h/2, 0, hw, h/2, hd)
parts.append((outer_v, outer_f))

# Iron banding straps across front face
for i in range(strap_count):
    sy = height * (i + 1) / (strap_count + 1)
    sv, sf = _make_box(0, sy, hd + 0.001,
                        hw * 0.95, strap_height / 2, strap_thickness / 2)
    parts.append((sv, sf))

# Lock plate
lock_v, lock_f = _make_cylinder(0, height * 0.45, hd + 0.005,
                                 lock_radius, lock_depth, segments=8)
parts.append((lock_v, lock_f))

# Hinge geometry
for hy in [height * 0.25, height * 0.75]:
    hv, hf = _make_cylinder(-hw + 0.02, hy, hd + 0.003,
                             0.015, 0.04, segments=6)
    parts.append((hv, hf))

final_verts, final_faces = _merge_parts(*parts)
```

### Terrain Micro-Undulation Pattern

Add a high-frequency noise displacement pass AFTER the main heightmap generation but BEFORE erosion:

```python
# In environment.py, after heightmap generation, before erosion
# Micro-undulation: 5-15cm per meter variation
micro_gen = _make_noise_generator(seed + 9999)
for i in range(resolution):
    for j in range(resolution):
        x_world = i * cell_size
        y_world = j * cell_size
        # High frequency, low amplitude
        micro = micro_gen.noise2(x_world * 2.0, y_world * 2.0)
        heightmap[i][j] += micro * 0.10  # 10cm amplitude
```

### Terrain Skirt Pattern

Extend terrain edges downward to hide paper-thin edges:

```python
# After terrain mesh creation, add skirt ring
skirt_depth = 5.0  # meters below lowest terrain point
for edge_vert_idx in edge_vertex_indices:
    x, y, z = verts[edge_vert_idx]
    skirt_verts.append((x, y, z - skirt_depth))
    # Create face connecting edge to skirt
    skirt_faces.append((edge_vert_idx, next_edge_idx, next_skirt_idx, skirt_idx))
```

### Scree/Talus Generation Pattern

Scatter rock debris meshes at cliff bases using slope detection:

```python
# For each cliff face / steep terrain edge:
# 1. Detect base of cliff (where slope transitions from >45deg to <35deg)
# 2. Generate cone-shaped accumulation at angle of repose (30-37 degrees)
# 3. Scatter individual rock meshes with size gradient (large at bottom, small at top)
for cliff_base_point in cliff_bases:
    scree_cone_verts, scree_cone_faces = _generate_scree_cone(
        center=cliff_base_point,
        radius=cliff_height * 0.4,
        angle_of_repose=33.0,  # degrees
        rock_count=int(cliff_height * 2),
        seed=seed,
    )
```

### Historical Merlon Sizing Pattern

```python
# One-third rule: merlon width = crenel width (or merlon = 1/3 of span)
# Historical range: merlons 0.8-1.2m wide, 1.0-1.5m tall, 0.4-0.6m deep
merlon_w = 1.0   # was 0.6
merlon_h = 1.2   # was 0.8
crenel_w = 1.0   # equal to merlon for one-third rule
merlon_d = wall_thickness * 0.35

# Arrow slit in each merlon (vertical slot)
slit_w = 0.08   # 8cm wide
slit_h = 0.6    # 60cm tall
```

### Anti-Patterns to Avoid

- **Single-vertex-thick walls:** Castle walls, building walls, and dungeon walls must be extruded to proper thickness (2-3m for castle, 0.3-0.5m for building). Never a single face plane.
- **Uniform geometry:** Props, rocks, and merlons should have subtle randomization (vertex jitter, rotation variation, scale variation) to avoid a manufactured look.
- **Z=0 placement:** All terrain features and environment generators still hardcode Z=0. Phase 39 addresses this systemically (PIPE-02), but this phase should not INTRODUCE new Z=0 hardcoding.
- **Y-axis confusion:** Blender is Z-up. All vertical measurements use Z axis. Recurring codebase bug (PIPE-04).
- **Ignoring existing helpers:** `procedural_meshes.py` has `_make_beveled_box`, `_make_cylinder`, `_make_sphere`, `_make_torus`. Use these instead of writing new box/cylinder primitives.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Basic primitive shapes | Custom vertex math for boxes/cylinders | `_make_box`, `_make_beveled_box`, `_make_cylinder`, `_make_sphere` in `procedural_meshes.py` | Already tested, handles UVs, normals |
| Stone block patterns | Manual vertex placement per stone | `_stone_block_grid()` in `building_quality.py` | Generates parametric stone courses with mortar gaps |
| Merlon/battlement geometry | Custom battlement code | `generate_castle_wall_battlements()` in `building_quality.py` | Has merlon styles (squared, swallow_tail, rounded), arrow slits, machicolations |
| Noise generation | `math.sin` hash-based noise | `_make_noise_generator()` from `_terrain_noise.py` | Proper OpenSimplex, deterministic seeds |
| Mesh merging | Manual index offsetting | `_merge_parts()` in riggable_objects.py / procedural_meshes.py | Handles vertex offset, face reindexing |
| Modular building pieces | New piece generators | `modular_building_kit.py` (175 pieces) | Complete kit with grid snapping, 5 styles |
| Furniture dispatch | Hardcoded furniture generators | `_mesh_bridge.py` MESH_GENERATORS map | Maps 20+ furniture types to generators |

**Key insight:** 90% of the geometry upgrade work is adding sub-detail calls (iron straps, hinges, locks, rock scatter) to existing generators using existing helper functions. The architecture is sound -- the detail just was never added.

## Common Pitfalls

### Pitfall 1: Vertex Count Explosion
**What goes wrong:** Adding too many detail elements per prop/building pushes vertex counts beyond game-ready budgets, causing performance issues.
**Why it happens:** Each detail element (hinge, strap, lock, stone block) adds 8-50+ vertices. Adding 20 details to each of 100 props in a scene = massive vertex increase.
**How to avoid:** Set strict per-asset vertex budgets: Props 500-3000v, Furniture 800-4000v, Building sections 2000-8000v, Castle walls 5000-15000v per section. Test with `blender_mesh action=game_check` after each upgrade.
**Warning signs:** Any single prop exceeding 5000 verts, any building section exceeding 20000 verts.

### Pitfall 2: Non-Manifold Geometry from Detail Overlaps
**What goes wrong:** Detail geometry (iron straps, hinges) placed ON the surface of base geometry creates overlapping faces, internal faces, non-manifold edges.
**Why it happens:** `_make_box` placed at `z = surface + 0.001` creates a box that intersects the surface.
**How to avoid:** Place detail geometry at a small but consistent offset (0.002-0.005m) from the surface. For iron straps on chests/doors, extrude FROM the surface rather than placing a separate box. Run `blender_mesh action=repair` after generation.
**Warning signs:** `game_check` reporting non-manifold edges, visual z-fighting in viewport.

### Pitfall 3: Dungeon/Cave Height Change Breaking BSP Layout
**What goes wrong:** Increasing dungeon wall_height from 3m to 6-8m changes vertical proportions but BSP layout algorithm assumes 2D. Rooms look like chimneys.
**Why it happens:** BSP dungeon generation in `_dungeon_gen.py` is 2D grid-based. Wall height is just an extrusion parameter.
**How to avoid:** Increase wall height while also adding ceiling geometry, floor variation, and vertical detail (stalactites, pillars, ledges) to fill the vertical space. The room footprint stays the same -- vertical detail makes the height feel intentional.
**Warning signs:** Rooms that are taller than they are wide, empty vertical space, visible ceiling plane.

### Pitfall 4: Castle Wall Thickness Change Breaking Tower Connections
**What goes wrong:** Increasing castle wall thickness from 1.5m to 2-3m shifts wall geometry outward, causing tower-to-wall intersections or gaps.
**Why it happens:** `generate_castle_spec` calculates tower positions relative to corners, and wall positions use direct box placement. Changing thickness without adjusting tower offsets creates misalignment.
**How to avoid:** Update tower corner offsets proportional to wall thickness increase. Test with visual verification (`blender_viewport action=contact_sheet`) for each thickness value.
**Warning signs:** Visible gaps between wall and tower, walls cutting through tower cylinders.

### Pitfall 5: Terrain Skirt Creating Visible Seams
**What goes wrong:** Terrain skirt geometry has different material/shading than the terrain surface, creating a visible band at the terrain edge.
**Why it happens:** Skirt vertices don't inherit vertex colors or UV coordinates from the terrain surface.
**How to avoid:** Copy vertex color and UV data from the nearest terrain edge vertex to each skirt vertex. Use the same material slot. Extend the skirt far enough below the lowest terrain point that the camera never sees the bottom edge.
**Warning signs:** Visible color change at terrain edges when viewed from below.

### Pitfall 6: Clothing Topology Upgrade Breaking Existing Tests
**What goes wrong:** Changing vertex counts in clothing generators invalidates existing test assertions that check specific vertex counts.
**Why it happens:** Tests like `assert tunic.vertex_count == 320` will fail when count increases to 1200.
**How to avoid:** Update test assertions to match new counts. Use range-based assertions: `assert 800 <= tunic.vertex_count <= 4000` per the clothing system's own documented target range.
**Warning signs:** Test failures referencing exact vertex/face counts.

## Code Examples

### Example 1: Adding Iron Banding to Chest

```python
# In riggable_objects.py, generate_chest(), after base box creation:

# Iron banding straps (3 horizontal straps across front face)
if style in ("iron_bound", "wooden"):
    strap_count = 3
    strap_h = 0.015  # 15mm tall strap
    strap_d = 0.008  # 8mm thick
    for si in range(strap_count):
        sy = base_h * (si + 1) / (strap_count + 1)
        # Front strap
        sv, sf = _make_box(0, sy, hd + strap_d / 2,
                            hw * 0.98, strap_h / 2, strap_d / 2)
        base_parts.append((sv, sf))
        # Side straps wrap around
        for sign in (-1, 1):
            ssv, ssf = _make_box(sign * hw + sign * strap_d / 2, sy, 0,
                                  strap_d / 2, strap_h / 2, hd * 0.9)
            base_parts.append((ssv, ssf))

# Lock plate (circular plate + keyhole)
lock_parts = []
lock_r = 0.03
lock_v, lock_f = _make_cylinder(0, base_h * 0.5, hd + 0.005,
                                 lock_r, 0.005, segments=8,
                                 cap_top=True, cap_bottom=True)
base_parts.append((lock_v, lock_f))

# Hinge plates (2 hinges on back edge)
for hy_frac in (0.3, 0.7):
    hy = base_h * hy_frac
    hinge_plate_v, hinge_plate_f = _make_box(
        0, hy, -hd - 0.003,
        0.02, 0.03, 0.003)
    base_parts.append((hinge_plate_v, hinge_plate_f))
    hinge_pin_v, hinge_pin_f = _make_cylinder(
        0, hy, -hd - 0.006,
        0.005, 0.07, segments=6, cap_top=True, cap_bottom=True)
    base_parts.append((hinge_pin_v, hinge_pin_f))
```

### Example 2: Increasing Dungeon Height with Stalactites

```python
# In worldbuilding_layout.py, handle_generate_dungeon():
# Change default wall_height from 3.0 to 7.0
wall_height = params.get("wall_height", 7.0)

# In _dungeon_gen.py, add stalactite generation after room geometry:
def _generate_stalactites(room_bounds, ceiling_height, seed=0):
    """Generate hanging stalactite meshes from ceiling."""
    rng = random.Random(seed)
    stalactites = []
    x0, y0, x1, y1 = room_bounds
    count = int((x1 - x0) * (y1 - y0) * 0.3)  # ~0.3 per sq meter
    for _ in range(count):
        sx = rng.uniform(x0 + 0.5, x1 - 0.5)
        sy = rng.uniform(y0 + 0.5, y1 - 0.5)
        length = rng.uniform(0.3, 1.5)
        base_r = length * rng.uniform(0.08, 0.15)
        # Cone mesh pointing downward from ceiling
        sv, sf = _make_cone(sx, ceiling_height, sy,
                            base_r, length, segments=6)
        stalactites.append((sv, sf))
    return stalactites
```

### Example 3: Terrain Micro-Undulation

```python
# In environment.py, inside terrain generation, after heightmap but before erosion:
def _apply_micro_undulation(heightmap, resolution, cell_size, seed, amplitude=0.10):
    """Add 5-15cm high-frequency undulation to terrain surface.
    
    Prevents the 'perfectly smooth between noise samples' artifact.
    """
    micro_gen = _make_noise_generator(seed + 77777)
    for i in range(resolution):
        for j in range(resolution):
            x = i * cell_size
            y = j * cell_size
            # Two octaves of high-frequency noise
            n1 = micro_gen.noise2(x * 1.5, y * 1.5) * amplitude
            n2 = micro_gen.noise2(x * 4.0, y * 4.0) * amplitude * 0.3
            heightmap[i][j] += n1 + n2
    return heightmap
```

### Example 4: smootherstep Utility

```python
# In _shared_utils.py, add alongside existing smoothstep:
def smootherstep(t: float) -> float:
    """Ken Perlin's smootherstep: 6t^5 - 15t^4 + 10t^3. Clamps t to [0,1].
    
    Higher-order polynomial than smoothstep. First AND second derivative
    are zero at endpoints, giving smoother transitions for terrain blending.
    smootherstep(0) = 0, smootherstep(0.5) = 0.5, smootherstep(1) = 1.
    """
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
```

### Example 5: Terrain Skirt Geometry

```python
def _add_terrain_skirt(verts, faces, resolution, skirt_depth=5.0):
    """Add skirt geometry around terrain edges to hide paper-thin edges.
    
    Creates a ring of downward-facing faces around the terrain perimeter,
    dropping `skirt_depth` meters below the edge vertices.
    """
    edge_indices = []
    n = resolution
    # Top edge
    edge_indices.extend(range(0, n))
    # Bottom edge
    edge_indices.extend(range(n * (n - 1), n * n))
    # Left edge (excluding corners)
    edge_indices.extend(range(n, n * (n - 1), n))
    # Right edge (excluding corners)
    edge_indices.extend(range(2 * n - 1, n * n - 1, n))
    
    skirt_verts = []
    skirt_faces = []
    skirt_base = len(verts)
    
    for idx in edge_indices:
        x, y, z = verts[idx]
        skirt_verts.append((x, y, z - skirt_depth))
    
    # Connect edge pairs with quads
    # (implementation connects adjacent edge vertices to their skirt counterparts)
    return verts + skirt_verts, faces + skirt_faces
```

## State of the Art

| Old Approach (Current) | New Approach (Phase 44) | Impact |
|------------------------|------------------------|--------|
| Box primitives for all castle geometry | Proper wall extrusions with historical dimensions | Castle looks like a real fortification, not stacked boxes |
| 3m dungeon ceilings | 6-8m variable height ceilings + stalactites | Dungeons feel vast and atmospheric |
| 102-vert chest (rounded box) | 400-800 vert chest with iron banding, lock, hinges | Props look hand-crafted, not primitive |
| 1.5m castle wall thickness | 2-3m walls with walkable parapet | Structurally believable walls |
| 0.6m x 0.8m merlons | 1.0m x 1.2m merlons (one-third rule) | Historically accurate battlements |
| Perfectly smooth terrain | 5-15cm micro-undulation | Terrain has natural feel at close range |
| Paper-thin terrain edges | Terrain skirt geometry extending 5m below | No visible terrain edge from any angle |
| No cliff-base scree | Talus cone at 30-37 degree angle of repose | Geologically realistic cliff bases |
| Linear interpolation in terrain features | smootherstep (6t^5-15t^4+10t^3) | Smoother, more natural transitions |
| 288 tris/chain link | 80 tris/chain link (seg=8, tube=4) | 72% polygon reduction, same visual |
| 205-vert flat flag | 800+ vert subdivided cloth mesh | Cloth simulation compatibility |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `python -m pytest Tools/mcp-toolkit/tests/ -x -q --timeout=30` |
| Full suite command | `python -m pytest Tools/mcp-toolkit/tests/ -q --timeout=60` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GEOM-04 | Prop detail geometry (iron banding, locks, hinges) | unit | `pytest tests/test_geom_props.py -x` | No -- Wave 0 |
| GEOM-05 | Clothing cloth-sim topology density | unit | `pytest tests/test_geom_clothing.py -x` | No -- Wave 0 |
| GEOM-06 | Interior furniture quality (non-cube) | unit | `pytest tests/test_geom_furniture.py -x` | No -- Wave 0 |
| GEOM-07 | Dungeon/cave height and stalactites | unit | `pytest tests/test_geom_dungeon_cave.py -x` | No -- Wave 0 |
| GEOM-08 | Castle wall thickness and merlon sizing | unit | `pytest tests/test_geom_castle.py -x` | No -- Wave 0 |
| GEOM-09 | Terrain micro-undulation and skirt | unit | `pytest tests/test_geom_terrain.py -x` | No -- Wave 0 |
| GEOM-10 | Scree at cliff bases, smootherstep | unit | `pytest tests/test_geom_scree.py -x` | No -- Wave 0 |
| GEOM-11 | Chain poly optimization, flag density | unit | `pytest tests/test_geom_chain_flag.py -x` | No -- Wave 0 |
| GEOM-12 | Building rubble, timber, roof, shutters | unit | `pytest tests/test_geom_building.py -x` | No -- Wave 0 |
| TEST-03 | Visual regression zai comparison | manual + zai | `blender_viewport action=contact_sheet` | N/A -- visual |
| TEST-04 | Opus scan until CLEAN | manual | Full test suite + Opus review | N/A |

### Sampling Rate
- **Per task commit:** `python -m pytest Tools/mcp-toolkit/tests/ -x -q --timeout=30`
- **Per wave merge:** `python -m pytest Tools/mcp-toolkit/tests/ -q --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_geom_props.py` -- covers GEOM-04 (verify chest/door/chain/flag/sign have detail geometry, vertex counts in range)
- [ ] `tests/test_geom_environments.py` -- covers GEOM-07, GEOM-09, GEOM-10 (dungeon height, terrain micro-undulation, scree generation)
- [ ] `tests/test_geom_buildings.py` -- covers GEOM-08, GEOM-12 (castle wall thickness, merlon sizing, building rubble detail)
- [ ] `tests/test_geom_clothing.py` -- covers GEOM-05 (vertex density for cloth sim)
- [ ] `tests/test_geom_chain_optimization.py` -- covers GEOM-11 (chain tri count <= 80/link, flag verts >= 800)
- [ ] Existing tests in `test_aaa_castle_settlement.py` have assertions for wall thickness that need updating from 1.5m to 2-3m

## Key File Map

| File | What to Change | Estimated Scope |
|------|----------------|-----------------|
| `handlers/riggable_objects.py` | `generate_chest`, `generate_door`, `generate_chain`, `generate_flag`, `generate_hanging_sign`, `generate_cage`, `generate_chandelier`, `generate_windmill`, `generate_rope_bridge`, `generate_drawbridge` | LARGE -- 10 generators need detail geometry |
| `handlers/procedural_meshes.py` | `generate_table_mesh`, `generate_bed_mesh`, `generate_chair_mesh`, `generate_barrel_mesh` | MEDIUM -- furniture quality upgrade |
| `handlers/worldbuilding_layout.py` | `handle_generate_dungeon`, `handle_generate_cave` -- increase default heights, add stalactites | MEDIUM |
| `handlers/_dungeon_gen.py` | Add stalactite generation, rock mesh scatter, variable floor height | MEDIUM |
| `handlers/_building_grammar.py` | `generate_castle_spec` -- wall_thickness 1.5->2.5, tower offset adjustment | SMALL |
| `handlers/building_quality.py` | Merlon sizing (0.6->1.0 width, 0.8->1.2 height), gatehouse arch geometry | MEDIUM |
| `handlers/worldbuilding.py` | `handle_generate_building` -- add rubble stone, timber framing, roof tile variation, shutters, signs | LARGE |
| `handlers/environment.py` | `handle_generate_terrain` -- add micro-undulation pass, terrain skirt generation | MEDIUM |
| `handlers/terrain_features.py` | Add scree/talus generation at cliff bases, replace linear interp with smootherstep | MEDIUM |
| `handlers/clothing_system.py` | Increase vertex density for all garment types (target 800-4000 per garment) | MEDIUM |
| `handlers/_shared_utils.py` | Add `smootherstep()` function | SMALL |
| `handlers/_mesh_bridge.py` | Update furniture mappings if new generators are added | SMALL |

## Vertex Budget Reference

Target vertex counts per asset category (game-ready LOD0):

| Asset Type | Current (v9 audit) | Target | Rationale |
|------------|-------------------|--------|-----------|
| Chest | 102 | 500-800 | Iron banding, lock, hinges, plank grooves |
| Door | 72 | 300-600 | Handle, hinges, plank detail, frame |
| Chain (per link) | ~48 verts (288 tris) | ~20 verts (80 tris) | Reduce segments while keeping recognizable shape |
| Flag | 205 | 800-1200 | Cloth sim needs quad grid density |
| Chandelier | 2480 | 2000-3500 | Already decent count, add ornament detail |
| Hanging Sign | 158 | 300-500 | Carved lettering, bracket detail |
| Cage | 916 | 800-1500 | Thicker bars, dent/bend variation |
| Windmill | 676 | 1500-3000 | Proper blade profile, gear mechanism |
| Rope Bridge | 1024 | 1500-2500 | Rope braid, plank weathering, sag curve |
| Drawbridge | 208 | 500-1000 | Hinge mechanism, chains, plank detail |
| Table | ~200 | 400-800 | Turned legs, plank gaps, edge wear |
| Bed | ~300 | 600-1200 | Frame joints, mattress shape, pillow |
| Dungeon room | 22152 (total) | 30000-50000 | With stalactites, floor variation, rubble |
| Cave | 15576 (total) | 25000-40000 | Stalactites, stalagmites, rock formations |
| Castle | 14357 (total) | 30000-60000 | Thicker walls, proper merlons, gatehouse arch |
| Building | 54246 (total) | 50000-80000 | Timber framing, rubble stone, shutters |
| Terrain (per 128x128) | 16384 | 20000-25000 | With skirt and micro-undulation (may increase resolution) |

## Historical Architecture Reference (for accuracy)

### Castle Walls (Source: castle_terrain_medieval_landscape_research.md)
- **Wall thickness:** 2-4m for curtain walls, up to 5m for keeps
- **Wall height:** 8-12m
- **Merlon dimensions (one-third rule):** Width equal to crenel width. Historical: 0.8-1.2m wide, 1.0-1.5m tall
- **Arrow slits:** 8cm wide (outside), 0.6m tall, splayed to 30-50cm inside
- **Machicolations:** Corbeled-out gallery at wall top, openings 30-40cm

### Dungeon Proportions
- **Room height:** Cathedral-scale dungeons 6-10m, standard rooms 4-6m, tunnels 2.5-3m
- **Stalactite length:** 0.3-2m for game-scale (real can be 10m+)
- **Stalagmite height:** Half of stalactite length (slower growth)

### Terrain Features (Source: castle_terrain_medieval_landscape_research.md)
- **Scree angle of repose:** 30-37 degrees for broken rock
- **Talus cone shape:** Fan-shaped at cliff base, larger rocks at bottom, finer at top
- **Terrain micro-undulation:** 5-15cm per meter in natural terrain
- **Terrain skirt:** Extend 3-5m below lowest terrain point

## Open Questions

1. **Modular kit integration timing**
   - What we know: Phase 42 (WIRE-02) is supposed to wire the modular building kit into generation. Phase 44 is about geometry quality.
   - What's unclear: Should GEOM-12 (building rubble/timber) upgrade the modular kit pieces or the direct building generator?
   - Recommendation: Upgrade the direct `handle_generate_building` generator in `worldbuilding.py` for this phase, since the modular kit wiring is a Phase 42 concern. If Phase 42 completes first, the improvements here should target whichever path is active.

2. **Interaction with Phase 39 smootherstep utility**
   - What we know: PIPE-06 in Phase 39 creates the shared `smootherstep()` utility. GEOM-10 needs it.
   - What's unclear: Whether Phase 39 will be complete before Phase 44 executes.
   - Recommendation: If `smootherstep()` does not exist when Phase 44 starts, create it in `_shared_utils.py` as part of GEOM-10 work. It is a trivial 4-line function. No duplication risk.

3. **Test assertion updates for existing tests**
   - What we know: `test_aaa_castle_settlement.py` has tests for castle wall thickness asserting current 1.5m value.
   - What's unclear: Exact test assertions that will break when wall thickness changes to 2-3m.
   - Recommendation: Grep for `wall_thickness` and `1.5` in test files before making changes. Update assertions to new values.

## Project Constraints (from CLAUDE.md)

- **Always verify visually** after Blender mutations. Use `blender_viewport` action=`contact_sheet` for thorough review.
- **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
- **Game readiness**: Run `blender_mesh` action=`game_check` before export.
- **Use seeds** for reproducible generation.
- **Batch when possible**.
- **Blender is Z-up**: All vertical measurements use Z axis. Y is depth. Recurring codebase bug.
- **Context7** for library/framework questions.
- **Episodic Memory** before starting any non-trivial task.
- **AAA visual quality demanded** -- user will cancel subscription if quality is not AAA. Verify ALL generation visually in Blender.
- **Follow-up bug scan rounds**: Always run until CLEAN -- never stop after one round if bugs were found.
- **Do NOT tighten security sandbox**.
- **BLOCKED_FUNCTIONS minimal** (exec/eval/compile/__import__/breakpoint/globals/locals/vars ONLY).

## Sources

### Primary (HIGH confidence)
- `V9_MASTER_FINDINGS.md` -- Sections 3 (terrain), 5 (vegetation), 6 (castle/settlement), 9 (riggable props), 17.4/17.7/17.8 (visual audit scores)
- `REQUIREMENTS.md` -- GEOM-04 through GEOM-12, TEST-03, TEST-04
- Direct codebase inspection of all 12 generator files listed in Key File Map
- `castle_terrain_medieval_landscape_research.md` -- Historical castle dimensions, terrain feature standards
- `modular_building_kits_research.md` -- Skyrim kit system, trim sheets, grid standards
- `TEXTURING_ENVIRONMENTS_RESEARCH.md` -- Terrain texturing, building materials, anti-tiling

### Secondary (MEDIUM confidence)
- Historical merlon one-third rule (cross-referenced in multiple castle architecture sources)
- Scree angle of repose 30-37 degrees (standard geological reference)
- Vertex budget targets (based on AAA game standards and existing LOD_PRESETS in `lod_pipeline.py`)

### Tertiary (LOW confidence)
- None -- all findings verified through codebase inspection and existing research documents

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all files directly inspected, no external dependencies
- Architecture: HIGH -- patterns derived from existing codebase patterns, just adding detail
- Pitfalls: HIGH -- derived from V9 audit findings and known codebase bugs
- Historical accuracy: HIGH -- sourced from project's own research docs with academic citations

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days -- stable domain, no external dependencies to version)
