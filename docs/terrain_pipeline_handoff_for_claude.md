# Terrain Pipeline Implementation Guide — Complete Specification

**Branch:** `feature/terrain-pipeline-clean`
**Date:** 2026-04-04
**Sources:** Claude Opus audit, Codex deep-dive audit, 3 research agent reports (AAA tiling, noise math, streaming implementations)
**Target:** Any AI or human implementer who needs the full picture

---

## 1. Executive Summary

The VeilBreakers MCP toolkit terrain system is **architecturally fragmented**. There are 9+ overlapping terrain/environment pipelines, competing road generators, two vegetation scatter handlers (one creates real meshes, one creates cubes), and pervasive centered-terrain assumptions that prevent tiled world generation.

**The fix is NOT bandaids.** It is a clean architectural migration to:

1. **Canonical world field** — one deterministic function maps (world_x, world_y, seed) to height
2. **Erode-before-split** — run erosion on the full world region, then extract tiles
3. **Tiles are packaging** — tiles are sampled windows over the world field, not independent generators
4. **World-space everything** — every terrain operation uses world coordinates, not tile-local
5. **One road system** — mesh roads only, no CURVE cylinders
6. **One scatter system** — real mesh generators only, no cube placeholders

The terrain must support **seamless tile expansion** — generating a new terrain node next to an existing one that meshes perfectly with shared edge vertices, consistent noise, consistent erosion, and continuous features.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 0: World Field Sampler (_terrain_world.py) — NEW             │
│                                                                     │
│ sample_world_height(world_x, world_y, seed, terrain_type, layers)  │
│ → deterministic height in WORLD UNITS at any world coordinate      │
│ This is the single source of truth for all terrain height queries. │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 1: World Heightmap Generation                                │
│                                                                     │
│ generate_world_heightmap(origin, samples, cell_size, seed, ...)    │
│ → sample rectangular window of world field                         │
│ → returns heights in WORLD UNITS (meters), NOT [0,1]              │
│ → NO per-tile normalization                                        │
│ → uses theoretical max amplitude for global range:                 │
│   max_amp = (1 - persistence^octaves) / (1 - persistence)         │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 2: Simulation — Erode Before Split                           │
│                                                                     │
│ erode_world_heightmap(heightmap, iterations, seed)                 │
│ → runs hydraulic + thermal erosion on FULL multi-tile region       │
│ → NO per-tile erosion, NO cross-tile seam problem                  │
│ → erosion operates in world-unit heights (no [0,1] assumption)    │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 3: World Features — All in World Space                       │
│                                                                     │
│ Rivers: route on world heightmap, carve before tile split          │
│ Canyons: apply to world heightmap before erosion                   │
│ Cliffs: detect on world heightmap, place meshes at world coords    │
│ Flatten zones: apply to world heightmap at world coordinates       │
│ Roads: compute network on world graph, mesh in world coords        │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 4: Tile Extraction                                           │
│                                                                     │
│ extract_tile(world_heightmap, tile_x, tile_y, tile_size)           │
│ → shared edge vertices: tile is (tile_size+1) x (tile_size+1)     │
│ → power-of-2+1 resolution (257, 513) for Unity compatibility      │
│ → tiles are packaging units, NOT authoritative source              │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 5: Per-Tile Mesh + Materials                                 │
│                                                                     │
│ create_terrain_tile_mesh() — Blender mesh at world position        │
│ paint_biome_materials() — world-space altitude/slope rules         │
│ cliff overlays — per-tile cliff face geometry at detected edges    │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 6: Per-Tile Scatter                                          │
│                                                                     │
│ Vegetation: world-space Poisson disk + VEGETATION_GENERATOR_MAP    │
│ Props: world-space contextual scatter + PROP_GENERATOR_MAP         │
│ All vertex positions transformed through obj.matrix_world          │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 7: LOD + Packaging                                           │
│                                                                     │
│ terrain_chunking.py for LOD levels + streaming metadata            │
│ Equal-LOD neighbors: edges match by data contract (no stitch)      │
│ Mixed-LOD neighbors: skirt geometry fallback                       │
│ Unity export: SetNeighbors(), heightmapResolution = power-of-2+1   │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Why erode-before-split (not per-tile erosion):**
Per-tile erosion spawns random droplets independently on each tile. Even with identical base noise in overlapping margins, different droplet histories produce different erosion results at tile edges. World Machine and Gaea both solve this with overlap+blend, but erode-before-split is simpler and guarantees bit-exact seams. Memory is trivial: 4x4 tiles at 257 = 1026x1026 = 8MB.

**Why world-unit heights (not [0,1]):**
Per-tile [0,1] normalization maps different noise values to the same heights across tiles (a tile with a mountain peak normalizes differently than a flat tile). Using world units with theoretical max amplitude formula provides deterministic, consistent normalization across all tiles.

**Why tiles are (tile_size+1) not tile_size:**
Two adjacent 256-cell tiles need 257 vertices per side. The last vertex column of Tile(0,0) and the first vertex column of Tile(1,0) sample the SAME world coordinate → identical height → seamless edge. This is the Unity standard (`heightmapResolution` must be power-of-2+1).

**Why stitch is fallback only:**
If the world field is deterministic and normalization is consistent, shared edge vertices have identical heights by construction. Stitching is only for: floating-point rounding artifacts (sub-mm), LOD mismatch at tile boundaries, or import precision loss.

---

## 3. Live Module Inventory

### Core Terrain and Environment
```
Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py      — Heightmap noise generation
Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py     — Hydraulic + thermal erosion
Tools/mcp-toolkit/blender_addon/handlers/environment.py          — Terrain mesh, roads, rivers, water, export
Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py  — Vegetation + prop scatter (GOOD path)
Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py     — Layers, sculpt, deform, stamp, flow
Tools/mcp-toolkit/blender_addon/handlers/terrain_sculpt.py       — Brush sculpting (pure logic)
Tools/mcp-toolkit/blender_addon/handlers/terrain_chunking.py     — LOD, streaming, chunk packaging
Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py    — Biome palettes, HeightBlend, materials, splatmap export
```

### Feature and Helper Generators
```
Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py     — Canyon, waterfall, cliff, arch, swamp, geyser, etc.
Tools/mcp-toolkit/blender_addon/handlers/coastline.py            — Coastline generator
Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py       — Cliff detection, cave entrance, bridge, transition
Tools/mcp-toolkit/blender_addon/handlers/road_network.py         — MST road graph + mesh specs (pure logic)
Tools/mcp-toolkit/blender_addon/handlers/_scatter_engine.py      — Poisson disk, biome filter, context scatter
Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py         — MeshSpec→Blender, generator maps
Tools/mcp-toolkit/blender_addon/handlers/vegetation_lsystem.py   — L-system tree generation
Tools/mcp-toolkit/blender_addon/handlers/vegetation_system.py    — Biome veg sets, placement logic, wind colors
Tools/mcp-toolkit/blender_addon/handlers/_biome_grammar.py       — Multi-biome world spec
```

### Worldbuilding and Orchestration
```
Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py        — Location/settlement/castle generation
Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py — Town/hearthvale layout + fallbacks
Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py        — safe_place_object, smoothstep
Tools/mcp-toolkit/blender_addon/handlers/__init__.py             — Command registration (35+ terrain commands)
Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py         — MCP server, compose_map orchestration
```

---

## 4. Command Registration Map

All live terrain/environment commands in `handlers/__init__.py`:

```
env_generate_terrain              env_paint_terrain
env_carve_river                   env_generate_road
env_create_water                  env_export_heightmap
env_scatter_vegetation            env_scatter_props
env_compute_road_network          env_generate_coastline
env_generate_canyon               env_generate_waterfall
env_generate_cliff_face           env_generate_swamp_terrain
env_generate_natural_arch         env_generate_geyser
env_generate_sinkhole             env_generate_floating_rocks
env_generate_ice_formation        env_generate_lava_flow
env_generate_multi_biome_world
env_add_storytelling_props        env_compute_light_placements
env_merge_lights                  env_light_budget
env_compute_atmospheric_placements
env_volume_mesh_spec              env_atmosphere_performance
terrain_setup_biome               terrain_create_biome_material
terrain_sculpt                    terrain_flatten_zone
terrain_spline_deform             terrain_layers
terrain_erosion_paint             terrain_stamp
terrain_snap_objects              terrain_flow_map
terrain_thermal_erosion           terrain_compute_chunks
terrain_chunk_lod                 terrain_streaming_distances
terrain_export_chunks_metadata
```

**NEW commands to register:**
```
env_generate_terrain_tile         ← Single tile at world position
env_generate_world_terrain        ← Multi-tile world generation
env_stitch_terrain_edges          ← Fallback edge snapping
env_validate_tile_seams           ← Numeric seam verification
```

---

## 5. Intertwined Generator Graph

### A. Core Terrain Path
`blender_server.py → env_generate_terrain → environment.handle_generate_terrain`

This is the main spine. Currently:
- Resolves biome presets
- Calls `generate_heightmap()` (tile-local coords — MUST FIX)
- Applies hydraulic/thermal erosion (clips to [0,1] — MUST FIX)
- Applies flatten zones
- Computes flow/moisture data
- Creates centered Blender mesh (MUST FIX for offset tiles)
- Generates cliff overlays via `_terrain_depth`

### B. River Path
`blender_server.py → env_carve_river → environment.handle_carve_river`

Currently carves directly on mesh heightmap. For tiled worlds, river carving MUST happen on the world heightmap BEFORE tile split. River A* paths must be computed in world space.

### C. Road Paths (FOUR competing systems)

| System | File | What It Creates | Status |
|--------|------|----------------|--------|
| `handle_generate_road` | environment.py:725 | Flat mesh ribbon + cobblestone | GOOD — fix centered coords |
| `_create_curve_path` | worldbuilding.py:2660 | CURVE with round bevel (cylinder) | BAD — deprecate |
| `_create_road_with_curbs` | worldbuilding.py:2685 | Mesh with raised curbs | GOOD — keep |
| `road_network.py` | road_network.py | Pure logic mesh specs | GOOD — keep, not fully adopted |

**Resolution:** Kill `_create_curve_path`. All callers migrate to `_create_road_with_curbs` or `handle_generate_road`.

### D. Water Path
`blender_server.py → env_create_water → environment.handle_create_water`

Creates spline-following or fallback water mesh. Fallback path assumes centered terrain. Water sizing derives from terrain dimensions. For tiled worlds: water bodies may span multiple tiles. World-space path point contract must be explicit.

### E. Scatter Paths (TWO competing systems)

| System | File | What It Creates | Status |
|--------|------|----------------|--------|
| `handle_scatter_vegetation` | environment_scatter.py:1217 | Real meshes via VEGETATION_GENERATOR_MAP | GOOD — fix centered coords |
| `scatter_biome_vegetation` | vegetation_system.py:673 | Mesh-backed biome placements via `mesh_from_spec` | GOOD — keep as helper, not a command |

**Resolution:** Keep `scatter_biome_vegetation` as the mesh-backed biome helper. Do not re-register the old cube command; migrate callers to the mesh-backed path.

### F. Multi-Biome Terrain Path (EASY TO FORGET)
`blender_server.py → env_generate_multi_biome_world → environment.handle_generate_multi_biome_world`

This is a SECOND full terrain generation orchestrator that:
 - Builds world spec with `_biome_grammar`
 - Calls `handle_generate_terrain`
 - Applies biome vertex colors/materials
 - Calls the mesh-backed biome vegetation helper

**MUST be patched in the same branch as the vegetation cleanup**, or it silently breaks.

### G2. World Map Composer Path (THIRD orchestrator)
`__init__.py → world_compose_world_map → worldbuilding.handle_compose_world_map`

Registered at `__init__.py:991`. NOT called from `blender_server.py` but callable directly via MCP.

This is a THIRD terrain orchestration path that:
- Calls `compose_world_map()` from `map_composer.py` (pure logic world planner)
- Creates curve roads at line 6796 (uses `_create_curve_path`)
- Materializes buildings, POIs, etc.

**Status:** Not called from compose_map. Has curve road dependency. Should be updated when curve roads are replaced. Low priority since it's not in the main compose_map flow.

### G. Worldbuilding Paths

| Handler | File | Terrain Dependencies |
|---------|------|---------------------|
| `handle_generate_location` | worldbuilding.py:6048 | Creates OWN terrain + curve roads |
| `handle_generate_settlement` | worldbuilding.py:6490 | Uses terrain-aware placement, curve road fallback |
| `handle_generate_town` | worldbuilding_layout.py:322 | Building placement on terrain |
| `handle_generate_hearthvale` | worldbuilding_layout.py:558 | Settlement + box fallbacks |

---

## 6. Deprecated / Dangerous Paths Still Active

### 1. Legacy curve-road path (4 active callers)
- `worldbuilding.handle_generate_location` (line 6144) calls `_create_curve_path`
- `worldbuilding.handle_generate_settlement` (line 6575) falls back to `_create_curve_path` for narrow roads
- `worldbuilding.handle_compose_world_map` (line 6796) creates world map roads as curves
- `worldbuilding._create_curve_from_points` (line 3535) thin wrapper — dead code, delete
- **Impact:** Cylinder roads appear even after mesh road system is fixed

### 2. Legacy cube vegetation handler
- Legacy command removed from `__init__.py`
- Current multi-biome path uses the mesh-backed vegetation helper
- **Impact:** Cube vegetation appears from multi-biome path even after main scatter is fixed

### 3. Box/cube fallbacks hide failures
- Hearthvale building fallback: `worldbuilding_layout.py:621-658` — creates 8-vertex box on ANY exception
- Perimeter wall fallback: `worldbuilding_layout.py:715-738` — creates 8-vertex box on ANY exception
- **Impact:** Generator failures look "successful" because geometry appears

### 4. Multi-biome path bypasses updated logic
- `handle_generate_multi_biome_world` uses its own terrain + vegetation flow
- **Impact:** Terrain refactor appears complete while this path remains incompatible

---

## 7. Centered / Single-Terrain Assumptions (11 locations)

### environment.py (1 location)
| Line | Code | Fix |
|------|------|-----|
| 471 | `u = (vert.co.x + terrain_size / 2.0) / terrain_size` | Works for local mesh (OK), but add obj.location awareness for UV on offset tiles |

### environment_scatter.py (4 locations)
| Line | Code | Fix |
|------|------|-----|
| 287-290 | `u = (world_x + half_size) / terrain_size` | Subtract `terrain_obj.location.x` before centering math |
| 1050 | `terrain_half = terrain_size / 2.0` for Poisson disk | Add terrain location offset to all candidate positions |
| 1348-1349 | `wx = p["position"][0] - terrain_half_bz` | Add terrain location offset for exclusion zone comparison |
| 1389-1403 | `terrain_half` used for instance positioning | Add `terrain_obj.location` to world position computation |

### terrain_advanced.py (3 locations)
| Line | Code | Fix |
|------|------|-----|
| 742 | `terrain_size = (dims.x, dims.y)` for layer ops | Pass `obj.location` to brush/layer functions |
| 944 | `terrain_size = (dims.x, dims.y)` for erosion brush | Adjust brush_center by subtracting `obj.location` |
| 1353 | `terrain_size = (dims.x, dims.y)` for stamp | Adjust stamp position by subtracting `obj.location` |

### blender_server.py (3 locations)
| Line | Code | Fix |
|------|------|-----|
| 179 | `half = terrain_size / 2.0` in `_normalize_map_point` | Add terrain_location parameter |
| 199 | `(y + half) / terrain_size` in `_map_point_to_terrain_cell` | Account for terrain offset |
| 212 | `half = terrain_size / 2.0` in `_plan_map_location_anchors` | Candidate positions need world offset |

### environment.py — ADDITIONAL (2 more locations found in deep verification)
| Line | Code | Fix |
|------|------|-----|
| 930-934 | Water fallback path: `(0.0, -fallback_depth / 2.0, water_level)` | When terrain is offset, center fallback water on `terrain_obj.location` instead of world origin |
| 1373-1374 | `nx = int((vx / world_size + 0.5) * cols)` in `_compute_vertex_colors_for_biome_map` | Subtract `obj.location` from vertex coords before mapping to biome grid: `vx = v.co.x + obj.location.x` then remap |

**Total: 13 centered-terrain assumptions (11 original + 2 found in deep verification)**

### vegetation_system.py (0 locations)
Already offset-aware at line 724 — correctly uses `obj.location` for area_bounds. No changes needed.

---

## 8. Vegetation Type Mapping (32 types found, 14 missing)

### Types IN VEGETATION_GENERATOR_MAP (18 types — these work)
```
tree, tree_healthy, tree_boundary, tree_blighted, tree_dead, tree_twisted,
pine_tree, bush, shrub, grass, weed, flower, rock, rock_mossy, cliff_rock,
mushroom, mushroom_cluster, root
```

### Types MISSING — will fall back to cubes

**Critical (used by default biome rules — MUST add):**
| Type | Used By | Map To |
|------|---------|--------|
| `fern` | thornwood_forest, deep_forest ground cover | `generate_shrub_mesh` with `size=0.3, branch_count=5` |
| `moss` | thornwood_forest, corrupted_swamp, 4+ biomes | `generate_grass_clump_mesh` with `blade_count=12, height=0.08, spread=0.2` |
| `vine` | thornwood_forest, corrupted_swamp | `generate_root_mesh` with `size=0.4` |
| `dead_tree` | `_TREE_VEG_TYPES` in environment_scatter.py | `_lsystem_tree_generator` with `tree_type="dead", iterations=4, leaf_type=None` |

**Deferred (specialized biome types — add when biomes are active):**
| Type | Used By | Map To |
|------|---------|--------|
| `gravestone` | cemetery biome | Custom mesh (not terrain scope) |
| `ember_plant` | ashen_wastes biome | `generate_mushroom_mesh` variant |
| `frost_lichen` | frozen_hollows biome | `generate_grass_clump_mesh` variant |
| `tumbleweed` | desert biome | `generate_grass_clump_mesh` variant |
| `crystal` | crystal_cavern biome | `generate_rock_mesh` variant |

**Deferred (building overrun types — not terrain scope):**
```
ivy_growth, moss_patch, vine_curtain, root_intrusion, fern_growth
```

---

## 9. Terrain Feature Generators — Wiring Status

All 11 generators return pure MeshSpec dicts. **None are called by compose_map.**

### Wire into terrain pipeline (this branch):
| Generator | File:Line | Integration Point |
|-----------|-----------|-------------------|
| `generate_cliff_face()` | terrain_features.py:446 | After erosion: `detect_cliff_edges()` → generate → `mesh_from_spec()` at world position |
| `generate_canyon()` | terrain_features.py:69 | Before erosion: apply canyon carving to world heightmap |
| `generate_waterfall()` | terrain_features.py:254 | After cliff detection: place at cliff+river intersections |
| `generate_coastline()` | coastline.py:433 | At water body creation: place along water/terrain boundary |
| `generate_cave_entrance_mesh()` | _terrain_depth.py:200 | After cliff detection: place in detected cliff faces |

### Keep registered but defer integration:
| Generator | Reason |
|-----------|--------|
| `generate_natural_arch()` | Feature placement, not core terrain |
| `generate_swamp_terrain()` | Alternative terrain type, wire when biome is active |
| `generate_geyser()` | Specialized biome feature |
| `generate_sinkhole()` | Specialized biome feature |
| `generate_floating_rocks()` | Specialized biome feature |
| `generate_ice_formation()` | Specialized biome feature |
| `generate_lava_flow()` | Specialized biome feature |

### All return this format:
```python
{
    "mesh": {"vertices": [(x,y,z), ...], "faces": [(v0,v1,v2,...), ...]},
    "materials": ["mat_name1", ...],
    "material_indices": [0, 1, ...],
    "vertex_count": int,
    "face_count": int,
    # Feature-specific keys: floor_path, side_caves, steps, pool, etc.
}
```
All use LOCAL coordinates (origin at base/center). Caller must position in world space using `mesh_from_spec(spec, location=(world_x, world_y, world_z))`.

---

## 10. Erosion Contract Change (CRITICAL)

### Current state (`_terrain_erosion.py:23`)
```python
def apply_hydraulic_erosion(heightmap, iterations=1000, ...) -> np.ndarray:
    # Assumes heightmap values in [0, 1]
    result = heightmap.astype(np.float64).copy()
    # ... droplet simulation ...
    return np.clip(result, 0.0, 1.0)  # ← LINE 176: hard clips to [0,1]
```

### Required changes
1. **Remove `np.clip(result, 0.0, 1.0)`** at line 176
2. **Add `height_range` parameter** so erosion can calibrate:
   - `capacity` scales with actual height differences, not normalized ones
   - `min_slope` expressed in world units, not [0,1] fraction
3. **Keep erosion math identical** — only change is removing the artificial domain assumption
4. **Update tests** in `test_terrain_erosion.py` — they enforce the old [0,1] assumption

### Erode-before-split pattern:
```python
def erode_world_heightmap(world_hmap, erosion_type, iterations, seed):
    """Erode a full multi-tile world heightmap as one piece."""
    h_range = world_hmap.max() - world_hmap.min()
    if erosion_type in ("hydraulic", "both"):
        world_hmap = apply_hydraulic_erosion(
            world_hmap, iterations=iterations, seed=seed,
            height_range=h_range,
        )
    if erosion_type in ("thermal", "both"):
        world_hmap = apply_thermal_erosion(world_hmap, iterations=max(iterations//50, 5))
    return world_hmap
```

---

## 11. New File: `_terrain_world.py`

```python
"""Canonical world-space terrain field — single source of truth.

Every terrain operation samples from this field. Tiles are just
windows. No per-tile normalization. No per-tile assumptions.

Provides:
  - sample_world_height: deterministic height at any world coordinate
  - generate_world_heightmap: sample rectangular window of world field
  - extract_tile: cut tile from world heightmap with shared edges
  - erode_world_heightmap: erode full region before splitting
  - validate_tile_seams: numeric edge/corner equality verification
  - theoretical_max_amplitude: global normalization constant
"""

# Key functions:

def theoretical_max_amplitude(persistence: float, octaves: int) -> float:
    """Deterministic max amplitude for fBm normalization."""
    if abs(persistence - 1.0) < 1e-10:
        return float(octaves)
    return (1.0 - persistence ** octaves) / (1.0 - persistence)

def generate_world_heightmap(
    world_origin_x: float,
    world_origin_y: float,
    samples_x: int,
    samples_y: int,
    cell_size: float = 1.0,
    seed: int = 0,
    terrain_type: str = "hills",
    height_scale: float = 20.0,
    warp_strength: float = 0.4,
    warp_scale: float = 0.5,
) -> np.ndarray:
    """Sample rectangular window of world terrain field.

    Returns heights in WORLD UNITS (meters), not [0,1].
    Same seed + same world coordinates = identical heights.
    """

def extract_tile(
    world_heightmap: np.ndarray,
    tile_x: int,
    tile_y: int,
    tile_size: int = 256,
) -> np.ndarray:
    """Extract tile with shared edge vertices.

    Returns array of shape (tile_size+1, tile_size+1).
    Last column of tile(x,y) == first column of tile(x+1,y).
    """

def validate_tile_seams(
    tile_a: np.ndarray,
    tile_b: np.ndarray,
    direction: str,
    tolerance: float = 1e-6,
) -> dict:
    """Verify shared edge heights match within tolerance.

    Returns: {matched: bool, max_diff: float, edge_length: int}
    """
```

---

## 12. Implementation Order (Phased, Dependency-Correct)

### Phase 1: Canonical World Terrain [blocks everything]

**Files:** `_terrain_world.py` (NEW), `_terrain_noise.py`

Changes:
- Create `_terrain_world.py` with all functions listed in Section 11
- In `_terrain_noise.py:generate_heightmap()`:
  - Add params: `world_origin_x=0.0`, `world_origin_y=0.0`, `cell_size=1.0`, `normalize=True`
  - Change coord grid: `x_coords = (np.arange(width) * cell_size + world_origin_x) / scale`
  - When `normalize=False`: use `theoretical_max_amplitude()` for global range
  - When `normalize=True`: keep existing per-tile normalization (backward compat)
- In `_terrain_noise.py:_apply_terrain_preset()`:
  - Crater preset: accept optional `world_center_x/y`; skip or use world coords in tiled mode

Tests:
- T1: Adjacent tile edge equality (east of 0,0 == west of 1,0 within 1e-6)
- T2: 2×2 corner agreement (four tiles share corner, all four values match)
- T4: Same seed reproduces (regenerating same tile = bit-identical)
- T5: Different seed differs
- T9: Theoretical max amplitude correctly bounds all presets

### Phase 2: Erosion Contract [blocks mesh creation]

**Files:** `_terrain_erosion.py`, `_terrain_world.py`

Changes:
- Remove `np.clip(result, 0.0, 1.0)` at `_terrain_erosion.py:176`
- Add `height_range` param to `apply_hydraulic_erosion()`
- Scale `capacity` and `min_slope` by height_range when provided
- Implement `erode_world_heightmap()` in `_terrain_world.py`
- Update all erosion tests for world-unit domain

Tests:
- T3: Erode-before-split seam preservation
- T8: World-unit erosion produces valid terrain
- T10: Backward compat — single-terrain with `normalize=True` still works

### Phase 3: Terrain Mesh and Tile Handlers [blocks features/scatter]

**Files:** `environment.py`

Changes:
- New `handle_generate_terrain_tile()`: create tile mesh at world position
- New `handle_generate_world_terrain()`: multi-tile generation pipeline
- New `handle_stitch_terrain_edges()`: fallback edge snapping
- Update `handle_generate_terrain()`: add `tile_x`, `tile_y`, `world_origin_x/y` with backward-compat defaults (0,0)
- Mesh creation: `obj.location = (tile_x * tile_world_size, tile_y * tile_world_size, 0)`
- Biome painting: use world-space altitude for multi-tile consistency

### Phase 4: All Offset-Sensitive Consumers [blocks scatter/roads]

**Files:** `environment_scatter.py`, `terrain_advanced.py`, `blender_server.py`

Changes:
- Fix all 11 centered-terrain assumptions listed in Section 7
- Each fix is: subtract `terrain_obj.location` from world coords before centering math
- Module-level coordinate cleanup in `environment_scatter.py` (not just 3 lines — audit all world↔local conversions)

### Phase 5: Roads, Rivers, Water, Features [independent of scatter]

**Files:** `environment.py`, `worldbuilding.py`

Changes:
- `handle_generate_road()` line 799: add tile world offset to all vertex coords
- `handle_carve_river()`: for tiled worlds, carve on world heightmap before split
- `handle_create_water()`: review/document world-space path point contract
- Wire terrain feature generators (cliff, canyon, waterfall, coastline, cave) into compose pipeline
  - Each: call generator → `mesh_from_spec()` → position at world coordinates
- `handle_export_heightmap()`: add tiled-world export mode (don't renormalize per tile)

Tests:
- T7: Road on offset tile at correct world position
- River across tile boundary test

### Phase 6: Vegetation Path Cleanup [independent of roads]

**Files:** `_mesh_bridge.py`, `vegetation_system.py`, `environment.py`, `__init__.py`

Changes:
- Add 4 critical aliases to `VEGETATION_GENERATOR_MAP`: fern, moss, vine, dead_tree
- Keep the mesh-backed `scatter_biome_vegetation()` helper in `vegetation_system.py`
- Keep the legacy cube vegetation command absent from `__init__.py`
- Patch `handle_generate_multi_biome_world()` to use the mesh-backed biome helper and the good scatter path consistently

Tests:
- T6: Scatter on offset tile — vegetation at correct world positions
- Multi-biome regression: `handle_generate_multi_biome_world` still works

### Phase 7: Worldbuilding Road Cleanup [final cleanup]

**Files:** `worldbuilding.py`, `worldbuilding_layout.py`

Changes:
- Replace ALL `_create_curve_path` callers with `_create_road_with_curbs`:
  - Line 6144: `handle_generate_location` roads
  - Line 6575: `handle_generate_settlement` narrow road fallback
  - Line 6796: `handle_compose_world_map` world map roads
  - Line 3535: `_create_curve_from_points` wrapper (dead code — also delete)
- Mark `_create_curve_path` as `@deprecated`
- Remove Hearthvale box fallback at lines 621-658 (replace with error logging)
- Remove perimeter box fallback at lines 715-738 (replace with error logging)

### Phase 8: Orchestration [depends on all above]

**Files:** `blender_server.py`, `__init__.py`, `terrain_chunking.py`

Changes:
- Register new commands: `env_generate_terrain_tile`, `env_generate_world_terrain`, `env_stitch_terrain_edges`, `env_validate_tile_seams`
- Add world terrain service (new `compose_map_tiled` action or separate MCP action)
- Update `terrain_chunking.py:compute_terrain_chunks()` to accept pre-tiled world heightmaps with `world_origin` param
- Ensure compose_map location anchors, flattening, scatter, and props honor tile/world origins

---

## 13. Required Tests

### Critical (must pass before merge)
| ID | Test | Verifies |
|----|------|----------|
| T1 | Adjacent tile edge equality | East edge of (0,0) == west edge of (1,0) within 1e-6 |
| T2 | 2×2 corner agreement | Four tiles share corner — all four values match |
| T3 | Erode-before-split seam | World heightmap eroded then split has seamless tiles |
| T4 | Deterministic reproduction | Same seed = bit-identical heightmap |
| T10 | Backward compatibility | Single-terrain (tile_x=0, tile_y=0, normalize=True) unchanged |

### High priority
| ID | Test | Verifies |
|----|------|----------|
| T5 | Different seed differs | Different seeds at same position produce different terrain |
| T6 | Scatter on offset tile | Vegetation at correct world positions on Tile(1,0) |
| T7 | Road on offset tile | Road mesh at correct world coords |
| T8 | World-unit erosion | Erosion valid without [0,1] clip |
| T11 | Multi-biome regression | `handle_generate_multi_biome_world` works after scatter migration |

### Medium priority
| ID | Test | Verifies |
|----|------|----------|
| T9 | Theoretical max amplitude | Formula correctly bounds fBm output for all 8 presets |
| T12 | Export contract for tiles | Heightmap export doesn't renormalize in tiled mode |
| T13 | Water on offset tile | Water placement correct on non-origin terrain |

---

## 14. Branch and Repo Organization

### Branch name
```
feature/terrain-pipeline-clean
```

### Branch from
```
master (current HEAD: 0a683a8)
```

### File creation order
```
1. _terrain_world.py              — NEW (canonical world field)
2. tests/test_terrain_tiling.py   — NEW (seam tests, write FIRST)
3. Modify _terrain_noise.py       — world-origin params
4. Modify _terrain_erosion.py     — remove [0,1] clip
5. Modify environment.py          — tile handlers + offset fixes
6. Modify environment_scatter.py  — offset fixes
7. Modify terrain_advanced.py     — offset fixes
8. Modify blender_server.py       — offset fixes + orchestration
9. Modify _mesh_bridge.py         — vegetation aliases
10. Modify vegetation_system.py   — delete cube handler
11. Modify worldbuilding.py       — replace curve roads
12. Modify worldbuilding_layout.py — remove box fallbacks
13. Modify __init__.py             — register/deregister commands
14. Update existing test files     — erosion, scatter, road tests
```

### Commit strategy
One commit per phase (8 total). Each commit should leave tests passing.

---

## 14b. Items Found During Final Gap Check

These were identified during cross-reference and are NOT covered elsewhere in this document.

### Gap 1: Flow Map / Moisture Map Must Be World-Level

`environment.py:441-448` computes flow accumulation from erosion results:
```python
flow_result = compute_flow_map(heightmap)
moisture_map = log_flow / fa_max
```
For tiled worlds, flow accumulation MUST be computed on the world heightmap (before tile split), because water flows across tile boundaries. Per-tile flow maps will have truncated drainage basins at tile edges.

**Fix:** Add `compute_flow_map()` call to `erode_world_heightmap()` in `_terrain_world.py`. Store the world flow map alongside the world heightmap. Extract per-tile moisture slices the same way tiles are extracted.

### Gap 2: World Expansion Strategy

When a user has an existing 2x2 world and wants to add Tile(2,0):
- **Same seed + world-space noise = deterministic.** Regenerating the full 3x2 world heightmap produces identical values for the original 2x2 area.
- **Erode-before-split requires re-eroding the expanded region.** The original 2x2 erosion result is NOT reusable because the new tile changes drainage patterns at the boundary.
- **Practical approach:** Regenerate + re-erode the full region every time. For a 10x10 world (2570x2570 heightmap), this takes ~5 seconds. Acceptable.
- **Future optimization:** Store pre-erosion world heightmap. On expansion, extend it and re-erode only. Or use overlap+blend for the new tiles only.

### Gap 3: Noise Repeat Distance

The fallback Perlin implementation (`_PermTableNoise`) uses a 256-element permutation table with `& 255` wrapping. This means noise REPEATS every 256 grid cells. At the default `scale=100.0`:
- Grid cells are spaced `1.0 / scale = 0.01` world units apart in noise space
- Repeat distance = `256 / (1/scale)` = `256 * scale` = 25,600 world units (25.6 km)
- For most game worlds this is fine. For worlds > 25 km, increase `scale` or use the real opensimplex backend (which does NOT repeat).

The real `opensimplex` library uses hash-based evaluation that does NOT repeat. However, the codebase currently uses the Perlin fallback for `noise2_array()` EVEN WHEN opensimplex is installed (see `_OpenSimplexWrapper` class — `noise2_array` inherits from `_PermTableNoise`).

**If world size > 25 km is ever needed:** Override `noise2_array()` in `_OpenSimplexWrapper` to use the real opensimplex backend, or increase the permutation table size.

### Gap 4: `handle_generate_multi_biome_world` Exact Location

`environment.py:1213` — This is a FULL terrain orchestrator that:
1. Builds world spec from `_biome_grammar.generate_world_map_spec()`
2. Calls `handle_generate_terrain()` to create the mesh
3. Applies Voronoi biome vertex colors and materials
4. At **line 1321**, imports and calls `scatter_biome_vegetation` (the mesh-backed helper)

```python
# environment.py:1321-1324
from .vegetation_system import scatter_biome_vegetation
veg_result = scatter_biome_vegetation({...})
```

This must remain aligned with the mesh-backed helper and the good scatter path. Do not reintroduce the removed cube handler.

### Gap 5: `safe_place_object` — Already World-Space Safe

`_shared_utils.py:34` — Uses world-space (x, y) coordinates and raycasts downward onto terrain. The `terrain_name` parameter targets a specific terrain object.

**Status: OK for offset tiles.** The raycast operates in world space regardless of terrain object position. No changes needed. Keep as-is.

### Gap 6: `terrain_thermal_erosion` Command

`__init__.py:1267` registers a lambda:
```python
"terrain_thermal_erosion": lambda params: {...}
```
This wraps `apply_thermal_erosion()` from `_terrain_erosion.py`. Thermal erosion is a local talus operation (no [0,1] clip issue). It operates on any heightmap and is already tile-safe.

**Status: No changes needed for thermal erosion.** Only hydraulic erosion has the [0,1] clip problem.

### Gap 7: Unity `scene_templates.py` Terrain Setup

`src/veilbreakers_mcp/shared/unity_templates/scene_templates.py` contains `generate_terrain_setup_script()` which generates Unity C# code with `terrain_size`, `terrain_resolution`, and `splatmap_layers` parameters. This template hardcodes a single-terrain assumption.

**Fix (Phase 8):** Update the Unity template to support tiled terrain:
- Accept `tile_count_x`, `tile_count_y` parameters
- Generate `Terrain.SetNeighbors()` calls for all adjacent tiles
- Use `TerrainData.SetHeightsDelayLOD()` for batch heightmap loading
- Set `heightmapResolution` to power-of-2+1 (matching Blender tile resolution)
- Generate `TerrainGroup` component for auto-connection

### Gap 8: Existing Test Files With Hard [0,1] Assertions (WILL BREAK)

Three existing test files have assertions that WILL FAIL when erosion/normalization changes are made. These must be updated in their respective phases.

**`test_terrain_erosion.py`** (191 lines, 9 tests) — CRITICAL BREAK RISK
- Lines 33-34: `assert result.min() >= 0.0` and `assert result.max() <= 1.0`
- Tests: `test_erosion_initial_bounds`, `test_erosion_height_preserved`, `test_erosion_50k_visible_channels`, 5 `test_apply_hydraulic_erosion` variants, 2 `test_apply_thermal_erosion` variants
- **Fix in Phase 2:** Change bounds assertions to use `height_range` parameter. When `height_range` is provided, assert result is within `[0, height_range]` instead of `[0, 1]`. Keep old tests passing with `normalize=True` backward compat path.

**`test_terrain_noise.py`** (585 lines, 26 tests) — CRITICAL BREAK RISK
- 8 `test_height_in_bounds` variants asserting heightmap in [0, 1]
- 8 `test_slope_in_bounds` variants
- 8 `test_biome_assignments` variants with altitude/slope thresholds
- **Fix in Phase 1:** When `normalize=True` (default, backward compat), all existing assertions still pass. New tests for `normalize=False` use theoretical max amplitude range. Do NOT modify existing tests — add NEW tests for the worldspace path.

**`test_environment_handlers.py`** (486 lines, 50 tests) — MODERATE BREAK RISK
- RAW export tests assert 16-bit values in uint16 range [0, 65535]
- 10 biome preset structure tests
- 16 terrain parameter validation tests
- **Fix in Phase 5:** Add `tiled_mode` flag to export handler. When `tiled_mode=False` (default), normalize per-mesh (existing behavior). When `tiled_mode=True`, use world-unit heights with global range.

**Additional test files affected (lower risk):**

| Test File | Tests | Risk | Reason |
|-----------|-------|------|--------|
| `test_terrain_flatten.py` | 8 | MODERATE | Blend thresholds may change at tile boundaries |
| `test_scatter_engine.py` | 37 | LOW | Pure logic, no [0,1] assumption |
| `test_terrain_chunking.py` | 13 | MODERATE | Chunk structure may need new fields |
| `test_terrain_biome_voronoi.py` | 4 | LOW | Voronoi is position-independent |
| `test_terrain_depth.py` | 23 | LOW | Feature generators are local-coordinate |
| `test_aaa_terrain_vegetation.py` | 31 | LOW | Vegetation generators are independent |
| `test_terrain_features_v2.py` | 21 | LOW | Feature generators are local-coordinate |
| `test_environment_scatter_handlers.py` | 15 | MODERATE | Scatter logic depends on heightmap |
| `test_terrain_materials.py` | ? | LOW | Material setup is position-independent |
| `test_road_coastline_terrain_features.py` | ? | MODERATE | Road/coastline may assume centered terrain |

**Total existing terrain tests: ~238 functions across 12 files.** Of these, ~43 tests in 3 files have CRITICAL break risk from [0,1] changes.

### Gap 9: Erosion Capacity/Min-Slope Scaling Direction

The doc says "Scale capacity and min_slope by height_range" but doesn't specify the direction. This matters:

The erosion capacity formula is: `c = max(-h_diff, min_slope) * speed * water * capacity`

When heightmap changes from [0,1] to [0, height_range]:
- `h_diff` becomes height_range× larger (height differences are in meters now)
- `capacity` = 4.0 was tuned for [0,1]. For proportional erosion behavior, DON'T change capacity — the larger h_diff automatically increases sediment carrying proportionally.
- `min_slope` = 0.01 was "1% of max height" in [0,1]. In world units, this should become `0.01 * height_range` (e.g., 0.2 for a 20m terrain) to maintain the same proportional threshold.

**Recommended approach:** Remove the [0,1] clip. Keep `capacity` as-is (it auto-scales with height differences). Scale `min_slope` by `height_range` when provided:
```python
effective_min_slope = min_slope * height_range if height_range else min_slope
```

Alternatively, normalize → erode → denormalize (simplest, but reintroduces per-region normalization — acceptable for erode-before-split since the entire world region is normalized together).

### Gap 10: End-to-End Flow for `handle_generate_world_terrain()`

The architecture diagram shows layers but the actual execution sequence needs to be explicit for implementers:

```
handle_generate_world_terrain(params):
  1. Parse params: tile_grid (e.g., 2x2), cell_size, seed, terrain_type, etc.
  2. Compute world region: total_samples_x = tile_grid_x * tile_size + 1
  3. generate_world_heightmap() → world heightmap in world units
  4. Apply flatten zones on world heightmap (building foundations)
  5. Apply canyon/river carving on world heightmap (A* paths)
  6. erode_world_heightmap() → erosion + flow map computation
  7. detect_cliff_edges() on world heightmap → cliff placement list
  8. FOR EACH tile (tx, ty):
     a. extract_tile() → per-tile heightmap
     b. create_terrain_tile_mesh() at world position
     c. paint_biome_materials() using world-space rules
     d. generate cliff overlay meshes at world positions
     e. scatter vegetation (world-space Poisson disk)
     f. scatter props (world-space context scatter)
  9. Generate road meshes in world space (span tiles)
  10. Generate water bodies in world space (span tiles)
  11. validate_tile_seams() on all adjacent pairs
  12. Return tile list + metadata
```

Steps 4-6 operate on the FULL world heightmap (before splitting). Steps 8a-8f operate per-tile. Steps 9-10 operate in world space across all tiles.

### Gap 11: Canyon Integration — Heightmap Carving vs Mesh Decoration

Section 9 says "Before erosion: apply canyon carving to world heightmap" but `generate_canyon()` returns a MeshSpec dict (mesh geometry), NOT a heightmap modification. These are two different operations:

**Heightmap carving** (modifies world heightmap directly):
- Use the EXISTING `handle_carve_river()` approach: A* path on heightmap, lower vertex heights along path
- Canyon is just a wider, deeper river carve: increase width and depth parameters
- This creates the terrain depression that erosion will then naturally enhance

**Mesh decoration** (separate geometry placed on terrain):
- Call `generate_canyon()` → MeshSpec with floor path, side caves, weathered materials
- `mesh_from_spec()` → Blender object positioned at world coordinates
- This adds visual detail (rock faces, cave entrances) that heightmap carving alone doesn't provide

**Both are needed:** Carve the heightmap first (creates the terrain shape), then place canyon decoration meshes (adds visual richness). The same applies to waterfalls (carve ledge into heightmap, place cascade mesh) and cliffs (steep heightmap area, place cliff face mesh overlay).

### Gap 12: `terrain_advanced.py` Still Assumes Normalized Height Domains In Multiple Editing Paths

The current spec correctly identifies `_terrain_erosion.py` as a `[0,1]` blocker, but it still understates the same issue in `terrain_advanced.py`.

**Live code paths affected:**
- `compute_erosion_brush()` at `terrain_advanced.py:898` returns `np.clip(result, 0.0, 1.0)`
- `flatten_terrain_zone()` at `terrain_advanced.py:1528` returns `np.clip(result, 0.0, 1.0)`
- `handle_erosion_paint()` builds a mesh-derived heightmap and feeds it through `compute_erosion_brush()`
- `handle_terrain_flatten_zone()` and `flatten_multiple_zones()` are used for building foundations and terrain prep
- Several docstrings and helper contracts still explicitly describe heightmaps as normalized `[0,1]`

**Impact:** If the canonical tiled world pipeline moves to world-unit heights, these editor/helper paths will silently re-normalize or clamp terrain unless they are updated. That means a world tile can generate correctly, then later get corrupted by brush erosion or flatten operations.

**Required decision:** choose ONE of these and document it explicitly:
1. **World-unit everywhere**: remove `[0,1]` clips from terrain editing helpers and scale thresholds by world height range.
2. **Normalized editing wrapper**: normalize the full world region (or extracted tile with global range), apply local editing, then de-normalize back to world units.

**Implementation note:** `handle_terrain_layers()` and `flatten_layers()` are mostly additive/multiplicative and do not hard-clip, but they still inherit whatever height domain the mesh uses. The main break risk is in the helper functions above that explicitly clamp.

**Additional tests to update/add:**
- `tests/test_terrain_advanced.py`
- `tests/test_terrain_flatten.py`

### Gap 13: `worldbuilding_layout.py` Has Additional Local-Space Terrain Generators Beyond The Fallback Boxes

The current spec captures the Hearthvale/perimeter fallback boxes, but it does NOT yet capture the broader worldbuilding layout generators that are still centered/local-space by design:

**Live pure-logic generators affected:**
- `generate_location_spec()` at `worldbuilding_layout.py:1050`
- `generate_easter_egg_spec()` at `worldbuilding_layout.py:1288`
- `generate_settlement_spec()` at `worldbuilding_layout.py:1483`
- `assign_district_zones()` at `worldbuilding_layout.py:1636`

These functions all generate positions relative to local bounds centered around `(-half, +half)` or settlement-center heuristics. That is valid for standalone location/settlement generation, but it is NOT the same thing as a world-space tiled terrain contract.

**Status:** safe to keep as local scene/layout generators if they remain explicitly standalone.

**Risk:** if `compose_map_tiled` or any future tiled world orchestration begins consuming these outputs as if they are already world coordinates, roads, props, district seeds, POIs, and hidden-path markers will be misaligned.

**Required contract:** either
1. keep these functions explicitly local and make callers transform them into world coordinates, or
2. add `world_origin` / `terrain_bounds` inputs so they can emit world-space placements directly.

**Tests affected if this path is migrated:**
- `tests/test_worldbuilding_v2.py`
- `tests/test_buildings_dungeonthemes_settlements.py`
- `tests/test_aaa_castle_settlement.py`
- `tests/test_worldbuilding_layout_handlers.py`

---

## 15. "Generate Adjacent Tile" Contract

When a user generates Tile(1,0) next to existing Tile(0,0):

| Requirement | How It's Met |
|-------------|-------------|
| Same heights at shared edge | Same seed + world-space noise → identical values at shared coordinates |
| No per-tile normalization drift | `theoretical_max_amplitude()` provides global range constant |
| Connected erosion | Erode-before-split on full multi-tile region |
| Consistent biome painting | World-space altitude/slope rules (not tile-local) |
| Continuous vegetation | World-space Poisson disk scatter, same seed |
| Roads can span tiles | World-space road network, mesh in world coords |
| Rivers can span tiles | A* path on world heightmap, carve before split |
| No stitching needed | Correct data contract → edges match by construction |
| Compatible LOD | Shared edge vertices (tile_size+1), skirts for mixed LOD |
| Resolution matches Unity | Power-of-2+1 (257, 513, 1025) |

---

## 16. Research References

Three research documents with full details:

1. **`.planning/research/terrain_tiling_research.md`** (819 lines)
   - UE5 World Partition, Unity Terrain API, Houdini HeightField Tile Split
   - CDLOD, Geometry Clipmaps, GPU tessellation
   - No Man's Sky, Minecraft, Skyrim world streaming

2. **`.planning/research/terrain_noise_tiling_research.md`** (952 lines)
   - World-space noise math, fBm continuity proof
   - Cross-tile erosion (expand-erode-shrink)
   - Global normalization formula
   - Skirt geometry for LOD stitching

3. **`.planning/research/terrain_streaming_implementations.md`** (637 lines)
   - FastNoiseLite, libnoise, OpenSimplex2 world-space support
   - World Machine overlap+blend, Gaea TileGate concept
   - Proland residual elevation, Terrain3D clipmaps
   - GPU erosion halo exchange, Sebastian Lague droplet erosion
   - Unity SetNeighbors(), SetHeightsDelayLOD(), heightmapResolution

---

## 17. Bottom-Line Instructions

1. **Treat the terrain system as a family of pipelines, not one file.** Changes to one path can silently break another.
2. **Do NOT delete a deprecated path until every active caller is migrated.** grep for all callers first.
3. **Do NOT trust fallback cubes/boxes.** Remove or hard-error them in terrain/worldbuilding flows. Silent fallbacks hide regressions.
4. **Keep `terrain_chunking.py` as packaging/LOD support, not as terrain authority.** The world field is authoritative.
5. **Patch `handle_generate_multi_biome_world` in the same branch** as the biome-scatter cleanup. It is an active caller of the deleted handler.
6. **Add world/tile tests BEFORE claiming completion.** If a path still assumes one centered terrain object, it is not done.
7. **Write `_terrain_world.py` FIRST.** It is the canonical source of truth that everything else depends on.
8. **Write tests FIRST.** Seam tests define the contract. Code must satisfy the tests, not the other way around.
9. **Erode the whole world, then split into tiles.** Do NOT erode tiles independently.
10. **Every coordinate in the terrain pipeline must be world-space.** If it uses `terrain_size / 2` without subtracting `obj.location`, it is wrong.
