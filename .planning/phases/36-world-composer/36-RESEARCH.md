# Phase 36: World Composer - Research

**Researched:** 2026-03-31
**Domain:** Procedural settlement generation — road networks, district zoning, lot subdivision, prop placement via Tripo AI
**Confidence:** HIGH (all findings based on direct code audit of existing files)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Organic medieval road layout — winding streets radiating from central square, irregularly curved, narrow alleys. L-system with noise perturbation on existing MST backbone.
- **D-02:** Full detail road meshes — extruded curb geometry (raised edges), cobblestone PBR material with proper UV tiling, gutters at building edges. Main roads 4m wide, alleys 2m wide.
- **D-03:** Concentric ring layout — market square at center → civic ring → residential → industrial → outskirts/walls. Distance from center determines zone.
- **D-04:** Soft gradient boundaries — building types blend at zone boundaries via probabilistic assignment based on distance to zone center. A tavern may appear in residential zone near market edge.
- **D-05:** OBB recursive split — each road-bounded block splits recursively along longest axis into lots with street frontage. Lot sizes vary by district (market=large, residential=small).
- **D-06:** District-dependent fill rate — market 100%, residential 80% (gardens/courtyards), industrial 95%, outskirts 60% (farmland). Empty lots become open spaces, not marker boxes.
- **D-07:** ALL small, medium, and street-level props are generated through Tripo AI — not procedural geometry. Use asset_pipeline generate_3d with dark fantasy art style prompts. Cache results for reuse across towns.
- **D-08:** Corruption-scaled density — Veil pressure determines prop density AND condition (4 tiers: 0.0-0.2 low, 0.2-0.5 medium, 0.5-0.8 high, 0.8-1.0 extreme).
- **D-09:** Performance-conscious — fewer high-quality props over many cheap ones. Every prop must be AAA quality, texturally coherent with surroundings, properly integrated into terrain. LOD awareness required.
- **D-10:** Tripo prompts must specify art style matching: "dark fantasy, hand-crafted medieval, PBR-ready" plus corruption level for visual variant generation.

### Claude's Discretion
- Town sizing (number of buildings, radius, generation time)
- Perimeter/wall generation approach (existing _generate_perimeter() can be reused)
- Specific Tripo prompt templates for each prop type
- LOD strategy for prop performance

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MESH-08 | City infrastructure: road mesh generation (curbs, cobblestones, intersections), market stalls, wells, lamp posts | D-01/D-02 road mesh spec; D-07 props via Tripo; integration in worldbuilding.py handler |
</phase_requirements>

---

## Summary

Phase 36 enhances the existing settlement generation system (2,386 lines in settlement_generator.py) to produce complete, walkable medieval towns matching Skyrim/Novigrad reference quality. Five major gaps exist between the current implementation and the CONTEXT.md specification: (1) road organics — current MST uses Prim's with simple bend noise, needs L-system + noise perturbation grammar; (2) road mesh detail — current `_road_segment_mesh_spec()` produces only flat quad strips, needs raised curb geometry + cobblestone PBR; (3) district model — current `generate_city_districts()` uses random Voronoi points, needs concentric ring zones with distance-based assignment; (4) lot subdivision — no lot system exists at all, blocks are undivided parcels; (5) prop sourcing — all props are procedural cubes via `_spawn_catalog_object()`, needs Tripo AI pipeline integration with corruption-scaled density.

The existing codebase provides strong foundations: MST backbone in road_network.py, Poisson disk sampling (Phase 31/33), `_veil_pressure_at()` for corruption calculation in map_composer.py, seed-based RNG throughout, and the pure-logic grammar pattern in `_*_grammar.py` files for testability. The work naturally splits into two plans: Plan 01 covers the data/grammar layer (road organics + curb mesh spec + concentric rings + OBB lot subdivision), and Plan 02 covers the Tripo prop pipeline + final worldbuilding.py wiring that materializes the grammar output as 3D objects.

**Primary recommendation:** Implement `_settlement_grammar.py` as a pure-logic grammar file (no bpy) for all new logic, then wire results through the existing `handle_generate_settlement()` in worldbuilding.py. This preserves testability and matches the Phase 32/33 pattern.

---

## Project Constraints (from CLAUDE.md)

- Always verify visually after Blender mutations (`blender_viewport` action=`contact_sheet`)
- Pipeline order: repair → UV → texture → rig → animate → export
- Use seeds for reproducible generation
- Batch when possible via `asset_pipeline` action=`batch_process`
- Game readiness check before export: `blender_mesh` action=`game_check`
- BLOCKED_FUNCTIONS: exec/eval/compile/__import__/breakpoint/globals/locals/vars ONLY — do NOT add getattr/setattr/open/type/format/dir
- No third-grade model generation — AAA quality benchmark (Skyrim/Fable/Valhalla)
- Pure-logic grammars in `_*_grammar.py` files for testability (no bpy dependency)
- Seed-based deterministic generation throughout

---

## Existing Code Audit

### What Exists (Reusable)

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| `generate_settlement()` | settlement_generator.py | entry point | REUSE — signature stays the same |
| `_generate_roads()` | settlement_generator.py | Prim's MST | EXTEND — add L-system layer on top |
| `_generate_perimeter()` | settlement_generator.py | wall gen | REUSE as-is |
| `_place_buildings()` | settlement_generator.py | building placement | REPLACE district logic |
| `_scatter_settlement_props()` | settlement_generator.py | prop scatter | REPLACE with Tripo pipeline |
| `generate_city_districts()` | settlement_generator.py | Voronoi districts | REPLACE with concentric rings |
| `compute_road_network()` | road_network.py | Kruskal's MST | REUSE mesh_specs base |
| `_road_segment_mesh_spec()` | road_network.py | flat quad strip | EXTEND — add curb verts |
| `_veil_pressure_at()` | map_composer.py | corruption calc | REUSE directly |
| `VEIL_PRESSURE_BANDS` | map_composer.py | band thresholds | REUSE for D-08 tiers |
| Poisson disk sampling | _terrain_grammar.py | 2D sampling | REUSE for prop placement |
| `evaluate_building_grammar()` | _building_grammar.py | building spec | REUSE — feeds _place_buildings |
| `_spawn_catalog_object()` | worldbuilding.py | cube proxy | REPLACE with Tripo calls |
| `handle_generate_settlement()` | worldbuilding.py | Blender wiring | EXTEND — add new section calls |

### What Is Missing (New Work)

| Gap | Location | Decision |
|-----|----------|----------|
| L-system road organics | New function in _settlement_grammar.py | D-01 |
| Curb/gutter geometry | `_road_segment_mesh_spec()` extension | D-02 |
| Concentric ring zones | New `_assign_district_ring()` function | D-03 |
| Soft gradient building assignment | New `_weighted_building_type()` function | D-04 |
| OBB recursive lot subdivision | New `_subdivide_block_to_lots()` function | D-05 |
| District fill rate enforcement | New `_apply_fill_rate()` function | D-06 |
| Tripo prop generation per type | New `_generate_prop_via_tripo()` function | D-07 |
| Corruption-scaled density tiers | New `_prop_density_for_pressure()` function | D-08 |
| Prop cache by (type, corruption_band) | New `_PROP_CACHE` dict in grammar | D-07 |
| LOD spec per prop | New `_prop_lod_spec()` function | D-09 |
| Tripo prompt templates | New `PROP_PROMPTS` dict | D-10 |

---

## Standard Stack

### Core (existing, confirmed by code audit)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| bpy | Blender 4.x | Blender scene API | Blender built-in |
| mathutils | Blender 4.x | Vector/Matrix math | Blender built-in |
| numpy | 1.x | OBB computation, spatial ops | Already imported in settlement_generator.py |
| random.Random | stdlib | Seed-based RNG | Already used throughout |

### Supporting (existing)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| TripoStudioClient | internal | Tripo AI model generation | blender_server.py asset_pipeline |
| asset_pipeline action=generate_3d | internal | Tripo API call | Confirmed in blender_server.py |
| Poisson disk sampling | _terrain_grammar.py | 2D prop distribution | Phase 31/33 established |
| `_veil_pressure_at()` | map_composer.py | Corruption value at position | Phase 34 established |

### No New Packages Required

All required functionality is available via existing imports. No pip installs needed.

---

## Architecture Patterns

### Recommended File Structure

```
blender_addon/handlers/
├── _settlement_grammar.py     # NEW: pure-logic grammar (no bpy)
│   ├── generate_road_network_organic()   # L-system + MST
│   ├── generate_concentric_districts()   # concentric ring zones
│   ├── subdivide_block_to_lots()         # OBB recursive split
│   ├── assign_buildings_to_lots()        # district-weighted building types
│   ├── generate_prop_manifest()          # corruption-scaled prop specs
│   └── PROP_PROMPTS                      # Tripo prompt templates
├── settlement_generator.py    # MODIFIED: replace Voronoi + prop scatter
│   ├── _generate_roads()                 # calls _settlement_grammar
│   ├── generate_city_districts()         # REPLACE with concentric rings
│   ├── _place_buildings()                # EXTEND with OBB lots
│   └── _scatter_settlement_props()       # REPLACE with Tripo manifest
├── road_network.py            # MODIFIED: curb geometry in _road_segment_mesh_spec()
└── worldbuilding.py           # MODIFIED: handle_generate_settlement wires Tripo calls
```

### Pattern 1: Pure Grammar Layer (established Phase 32/33)

New logic goes in `_settlement_grammar.py` with no bpy imports. Blender handler calls grammar, receives spec dicts, materializes objects. This allows pytest coverage without a Blender process.

```python
# _settlement_grammar.py — pure logic, no bpy
def generate_road_network_organic(center, radius, seed, road_style="medieval"):
    """Returns list of road segment dicts (no bpy objects)."""
    rng = random.Random(seed)
    # 1. Build MST backbone (reuse compute_mst_edges logic)
    # 2. Apply L-system branching for alleys
    # 3. Perturb each point with noise
    return [{"start": (x1,y1,0), "end": (x2,y2,0), "width": w, "style": s}, ...]

# worldbuilding.py — Blender handler
def handle_generate_settlement(params):
    segments = generate_road_network_organic(center, radius, seed)
    for seg in segments:
        _create_road_with_curbs(seg)  # materializes in bpy
```

### Pattern 2: Concentric Ring District Assignment

```python
def _assign_district_ring(pos, center, radius):
    """Returns district name based on normalized distance from center."""
    dist = (Vector(pos) - Vector(center)).length / radius
    # 0.0-0.15 = market_square
    # 0.15-0.35 = civic_ring
    # 0.35-0.60 = residential
    # 0.60-0.80 = industrial
    # 0.80-1.00 = outskirts
    thresholds = [("market_square", 0.15), ("civic_ring", 0.35),
                  ("residential", 0.60), ("industrial", 0.80), ("outskirts", 1.01)]
    for name, t in thresholds:
        if dist < t:
            return name
    return "outskirts"
```

### Pattern 3: OBB Recursive Lot Subdivision

```python
def subdivide_block_to_lots(block_polygon, district, seed, min_lot_area=25.0):
    """
    Recursively splits a road-bounded block along longest axis.
    Returns list of lot polygons, each with street_frontage edge.
    Uses numpy for PCA-based OBB computation.
    """
    rng = random.Random(seed)
    if block_area(block_polygon) < min_lot_area * 2:
        return [block_polygon]
    # Find OBB longest axis
    # Split with slight offset from midpoint (rng.uniform(0.4, 0.6))
    # Recurse on both halves
    # Assign street frontage to edge closest to road centerline
```

### Pattern 4: Tripo Prop Manifest (no bpy)

```python
PROP_PROMPTS = {
    "lantern_post": "dark fantasy iron lantern post, hand-crafted medieval, PBR-ready, {corruption_desc}",
    "market_stall": "dark fantasy wooden market stall with fabric canopy, medieval, PBR-ready, {corruption_desc}",
    "well": "dark fantasy stone well with rope and bucket, hand-crafted medieval, PBR-ready, {corruption_desc}",
    "barrel_cluster": "dark fantasy weathered oak barrels, medieval market, PBR-ready, {corruption_desc}",
    "cart": "dark fantasy wooden merchant cart, hand-crafted medieval, PBR-ready, {corruption_desc}",
}

CORRUPTION_DESCS = {
    "pristine": "pristine condition, vibrant colors",
    "weathered": "weathered aged condition, worn textures",
    "damaged": "damaged cracked condition, dark corruption spreading",
    "corrupted": "heavily corrupted by dark void energy, blackened crumbling",
}

def generate_prop_manifest(road_segments, veil_pressure, seed):
    """
    Returns list of prop spec dicts. No bpy. Worldbuilding.py materializes via Tripo.
    Each spec: {prop_type, position, rotation, prompt, corruption_band, cache_key}
    """
```

### Pattern 5: Prop Cache Keyed by (type, corruption_band)

```python
# worldbuilding.py
_PROP_CACHE = {}  # {(prop_type, corruption_band): glb_path}

def _get_or_generate_prop(prop_type, corruption_band, prompt):
    key = (prop_type, corruption_band)
    if key in _PROP_CACHE:
        return _PROP_CACHE[key]
    result = call_asset_pipeline_generate_3d(prompt=prompt)
    _PROP_CACHE[key] = result["glb_path"]
    return result["glb_path"]
```

### Pattern 6: Curb Geometry Extension

```python
# road_network.py — extend _road_segment_mesh_spec()
def _road_segment_mesh_spec_with_curbs(start, end, width, curb_height=0.15, gutter_width=0.3):
    """
    Cross-section (left to right):
      gutter (0.3m) | road surface (width) | gutter (0.3m)
    Curb edge verts raised by curb_height above road surface.
    Returns {vertices, faces, uv_layers: {road_surface, curb}} for cobblestone PBR.
    """
    # 6 vertex columns along segment: outer-left, curb-left, inner-left,
    #                                  inner-right, curb-right, outer-right
    # Curb verts offset by curb_height in Z
```

### Anti-Patterns to Avoid

- **Voronoi for districts:** Current `generate_city_districts()` uses random Voronoi seed points — produces arbitrary polygons, not concentric rings. Replace entirely.
- **Flat road quads only:** Current `_road_segment_mesh_spec()` has no Z variation — no curb realism. Extend cross-section vertex layout.
- **`_spawn_catalog_object()` for props:** Creates procedural cubes. All street props must go through Tripo. Do not call `_spawn_catalog_object()` for any prop category.
- **Prop per-instance generation:** Do not call Tripo once per prop instance. Cache by (type, corruption_band) — one Tripo call per unique (type, band) combination, then instance.
- **Blocking settlement generation on Tripo:** Tripo calls are slow. Pre-generate prop types async, or generate prop manifest first and spawn a background Tripo pass. The grammar layer returns spec dicts only — Tripo integration happens in the wiring layer.
- **Grid layout bleed-through:** The existing `SETTLEMENT_TYPES["town"]` has `layout_pattern="grid"`. The new organic road grammar overrides this — ensure the concentric ring + L-system path is taken for the enhanced settlement type.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 3D prop generation | Custom mesh generators for lanterns/barrels/wells | `asset_pipeline` action=`generate_3d` + Tripo | D-07 locked decision; hand-rolled geometry won't meet AAA bar |
| Corruption value at position | Custom distance-to-veil calc | `_veil_pressure_at(pos, veil_sources)` in map_composer.py | Already exists, already tested |
| 2D point distribution | Custom grid / random scatter | Poisson disk sampling (Phase 31/_terrain_grammar.py) | Prevents clustering, already used |
| MST backbone | New graph algorithm | `compute_mst_edges()` from road_network.py | Already uses Kruskal's, handles edge cases |
| PBR material assignment | Custom shader code | Existing procedural material presets (45+ in procedural_meshes.py) | cobblestone preset exists |

**Key insight:** The Tripo pipeline + existing map/terrain infrastructure means this phase is primarily about connecting systems, not building new computation primitives. The data layer is new (L-system, OBB, concentric rings) but the heavy lifting (Tripo, MST, corruption, Poisson) already exists.

---

## Common Pitfalls

### Pitfall 1: Voronoi District Code Still Called
**What goes wrong:** `generate_settlement()` calls `generate_city_districts()` conditionally based on `settlement_type`. If the call site is not updated, the old Voronoi districts silently win.
**Why it happens:** The new concentric ring function will be new code — easy to forget to update the dispatch.
**How to avoid:** Search and replace all call sites of `generate_city_districts()` in settlement_generator.py. Add an assertion that the new path is taken for the enhanced type.
**Warning signs:** Districts appear as irregular polygons instead of rings. Buildings cluster in unexpected zones.

### Pitfall 2: Tripo Call Per Prop Instance (Performance Bomb)
**What goes wrong:** Calling `generate_3d` once per prop instance generates hundreds of Tripo requests for a single town, taking hours and consuming all credits.
**Why it happens:** The naive approach is to loop over prop manifest and generate each one.
**How to avoid:** Cache by `(prop_type, corruption_band)`. A town with 50 lanterns uses ONE Tripo call for `("lantern_post", "pristine")` and instances the GLB 50 times.
**Warning signs:** Generation time > 5 minutes, Tripo API rate limit errors.

### Pitfall 3: OBB Lots Without Street Frontage
**What goes wrong:** Recursive subdivision produces lots that face inward — building entrances point away from roads.
**Why it happens:** OBB split doesn't track which edges are adjacent to road centerlines.
**How to avoid:** In `subdivide_block_to_lots()`, pass road centerline geometries. After each split, assign the lot edge closest to any road centerline as `street_frontage_edge`. Building grammar receives this edge as front orientation.
**Warning signs:** Buildings placed with door facing courtyard, backs to street.

### Pitfall 4: L-System Points Below Terrain
**What goes wrong:** Perturbed road points drop below heightmap surface, producing floating/buried road segments.
**Why it happens:** Noise perturbation operates in XY only but Z is sampled from heightmap afterward — if perturbation moves point to steep slope, height discontinuity shows.
**How to avoid:** After L-system / noise pass, re-sample Z from heightmap for every road vertex. Then apply the existing bend-noise-on-curve pattern from `handle_generate_settlement()`.
**Warning signs:** Road segments visible intersecting terrain at steep angles.

### Pitfall 5: Prop Placement on Slope Without Normal Alignment
**What goes wrong:** Lantern posts and wells appear tilted or floating on sloped terrain.
**Why it happens:** Default Blender object spawn is Z-up. Terrain normal may differ.
**How to avoid:** For each prop, raycast down to terrain surface, sample surface normal, align object rotation to match. The existing `_scatter_settlement_props()` does NOT do this — it's a known gap.
**Warning signs:** Barrels floating 0.3m above ground on slopes, lanterns tilted into ground.

### Pitfall 6: Settlement Type Not Enhanced
**What goes wrong:** `generate_settlement()` is called with `settlement_type="town"` which routes through the OLD grid-layout path.
**Why it happens:** The function has dispatch logic keyed on settlement_type.
**How to avoid:** Either (a) modify `settlement_type="town"` behavior to use new system, or (b) introduce `settlement_type="medieval_town"` as the enhanced type and document it. Option (b) is safer (no regression on existing tests).
**Warning signs:** Generated town has grid-pattern roads instead of organic winding streets.

---

## Code Examples

### Road Organic Perturb (based on existing bend pattern)
```python
# Source: settlement_generator.py handle_generate_settlement bend noise pattern
# Existing: road_seed.uniform(-bend, bend) applied to control points
# New L-system extension:
def _perturb_road_segment(start, end, rng, amplitude=1.5, steps=3):
    """Insert mid-points with noise for organic feel."""
    points = [start]
    for i in range(1, steps):
        t = i / steps
        mid = lerp(start, end, t)
        offset = rng.uniform(-amplitude, amplitude)
        perp = perpendicular_2d(end - start)
        points.append(mid + perp * offset)
    points.append(end)
    return points
```

### Concentric Ring Lookup
```python
# Source: pattern derived from _pressure_band() in map_composer.py (same approach)
RING_THRESHOLDS = [
    ("market_square", 0.15),
    ("civic_ring",    0.35),
    ("residential",   0.60),
    ("industrial",    0.80),
    ("outskirts",     1.01),
]

def ring_for_position(pos, center, radius):
    dist_norm = (Vector(pos[:2]) - Vector(center[:2])).length / radius
    for name, threshold in RING_THRESHOLDS:
        if dist_norm < threshold:
            return name
    return "outskirts"
```

### Corruption Tier Lookup
```python
# Source: D-08 spec in CONTEXT.md
CORRUPTION_TIERS = [
    (0.2,  "pristine",  3.0, 5.0),   # spacing_min, spacing_max
    (0.5,  "weathered", 5.0, 8.0),
    (0.8,  "damaged",   8.0, 15.0),
    (1.01, "corrupted", 15.0, 50.0),
]

def prop_tier_for_pressure(pressure):
    for threshold, band, spacing_min, spacing_max in CORRUPTION_TIERS:
        if pressure < threshold:
            return band, spacing_min, spacing_max
    return "corrupted", 15.0, 50.0
```

### Curb Cross-Section Vertex Layout
```python
# road cross-section (7 vertex columns along segment):
# col 0: outer gutter left  (Z = road_z)
# col 1: curb top left      (Z = road_z + curb_height)
# col 2: inner gutter left  (Z = road_z)
# col 3: road center        (Z = road_z)  [for UV seam]
# col 4: inner gutter right (Z = road_z)
# col 5: curb top right     (Z = road_z + curb_height)
# col 6: outer gutter right (Z = road_z)
# UV layer "road_surface": cols 2-4 get cobblestone tiling UVs
# UV layer "curb": cols 1,5 get stone_edge tiling UVs
```

### OBB Longest-Axis Split
```python
import numpy as np

def _obb_longest_axis_split(polygon_verts, rng, split_ratio_range=(0.4, 0.6)):
    pts = np.array(polygon_verts)
    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Principal axis = eigenvector of largest eigenvalue
    axis = eigenvectors[:, np.argmax(eigenvalues)]
    # Project all points onto axis, find range
    projections = centered @ axis
    split_t = rng.uniform(*split_ratio_range)
    split_val = projections.min() + (projections.max() - projections.min()) * split_t
    # Divide polygon at split_val along axis
    # ... returns (left_polygon, right_polygon)
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `Tools/mcp-toolkit/pytest.ini` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_settlement_generator.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MESH-08 (roads) | L-system produces organic road segments | unit | `pytest tests/test_settlement_grammar.py::test_road_network_organic -x` | ❌ Wave 0 |
| MESH-08 (curbs) | Road mesh spec includes curb vertices (Z offset) | unit | `pytest tests/test_settlement_grammar.py::test_road_curb_geometry -x` | ❌ Wave 0 |
| MESH-08 (districts) | Concentric ring assigns correct zone by distance | unit | `pytest tests/test_settlement_grammar.py::test_ring_district_assignment -x` | ❌ Wave 0 |
| MESH-08 (lots) | OBB subdivision produces lots with street frontage | unit | `pytest tests/test_settlement_grammar.py::test_obb_lot_subdivision -x` | ❌ Wave 0 |
| MESH-08 (props) | Prop manifest respects corruption tier spacing | unit | `pytest tests/test_settlement_grammar.py::test_prop_manifest_corruption_tiers -x` | ❌ Wave 0 |
| MESH-08 (cache) | Prop cache returns same path for same (type, band) | unit | `pytest tests/test_settlement_grammar.py::test_prop_cache_keying -x` | ❌ Wave 0 |
| MESH-08 (integration) | generate_settlement() returns buildings+roads+props | integration | `pytest tests/test_settlement_generator.py -x -q` | ✅ exists |

### Sampling Rate
- **Per task commit:** `pytest tests/test_settlement_grammar.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_settlement_grammar.py` — covers all MESH-08 pure-logic tests (6 tests listed above)
- [ ] Framework install: already installed (18,576 tests passing)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Voronoi random districts | Concentric ring zones | Phase 36 | Predictable market-center layout |
| Flat quad road strip | Raised curb + cobblestone PBR | Phase 36 | Ground-level visual fidelity |
| Cube proxy props | Tripo AI GLB imports | Phase 36 | AAA street-level props |
| Grid settlement layout | L-system organic medieval | Phase 36 | Skyrim/Novigrad character |
| No lot subdivision | OBB recursive split | Phase 36 | Proper building-to-street relationship |

**Deprecated/outdated in this codebase (to replace):**
- `generate_city_districts()` Voronoi path: replace with `generate_concentric_districts()`
- `_spawn_catalog_object()` for prop categories: replace with `_get_or_generate_prop()` + Tripo
- `SETTLEMENT_TYPES["town"] layout_pattern="grid"`: override with new organic path

---

## Open Questions

1. **Tripo generation during settlement generation — async vs sync?**
   - What we know: `asset_pipeline` action=`generate_3d` is synchronous (HTTP call, waits for result)
   - What's unclear: Does the settlement generation caller tolerate a 30-60 second Tripo wait per prop type?
   - Recommendation: Generate prop manifest first (instant), then do a separate "materialize props" pass. This allows partial progress display in Blender.

2. **How many unique prop types per town?**
   - What we know: D-09 says "fewer high-quality props" — suggests < 10 prop types per corruption band
   - What's unclear: Exact prop type list for each district type
   - Recommendation: Claude's discretion per CONTEXT.md. Propose: lantern_post, well, market_stall, barrel_cluster, cart, bench, trough, notice_board = 8 types × 4 corruption bands = max 32 Tripo calls per town (acceptable).

3. **LOD strategy for props**
   - What we know: D-09 requires LOD awareness. Phase 30 established LOD pipeline with 7 presets.
   - What's unclear: Should LOD be baked into Tripo GLB or applied post-import?
   - Recommendation: Claude's discretion. Apply LOD post-import using existing Phase 30 LOD pipeline (consistent with rest of toolkit).

---

## Environment Availability

Step 2.6: No new external dependencies required. All tools (pytest, Blender, Tripo via asset_pipeline) confirmed available from prior phases.

---

## Sources

### Primary (HIGH confidence)
- Direct code audit: `settlement_generator.py` (2,386 lines) — all function signatures, district types, road generation, prop scatter
- Direct code audit: `road_network.py` (562 lines) — MST algorithm, mesh spec, intersection classification
- Direct code audit: `map_composer.py` (1,380 lines) — `_veil_pressure_at()`, `VEIL_PRESSURE_BANDS`
- Direct code audit: `worldbuilding.py` — `handle_generate_settlement()`, `_spawn_catalog_object()`
- Direct code audit: `blender_server.py` — `asset_pipeline` action=`generate_3d` routing
- `36-CONTEXT.md` — all locked decisions D-01 through D-10

### Secondary (MEDIUM confidence)
- Phase 32/33 pattern: pure grammar in `_*_grammar.py` confirmed in `_building_grammar.py`
- Phase 31/33 Poisson disk sampling confirmed via Grep of _terrain_grammar.py

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all from direct code audit, no new packages
- Architecture: HIGH — follows established Phase 32/33 grammar pattern exactly
- Pitfalls: HIGH — all from direct code inspection of gaps between existing and required behavior

**Research date:** 2026-03-31
**Valid until:** 2026-05-01 (stable — no external dependencies)
