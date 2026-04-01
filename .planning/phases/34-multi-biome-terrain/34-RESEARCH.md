# Phase 34: Multi-biome Terrain -- Research

**Researched:** 2026-03-31
**Domain:** Procedural terrain, Voronoi biome distribution, corruption system, terrain-conforming foundations
**Confidence:** HIGH

## Summary

Phase 34 wires together a substantial amount of existing pure-logic infrastructure into a coherent multi-biome world map system. The core algorithms (Voronoi distribution, corruption tint, biome transition blending, terrain flatten zones, biome material palettes, L-system vegetation scatter) are all already written and tested. What is missing is: (1) a `_biome_grammar.py` pure-logic module that drives the full world-map generation pipeline, (2) a Blender handler (`handle_generate_multi_biome_terrain`) that stitches terrain mesh + biome material + vegetation + flatten zones in one shot, and (3) an MCP action `blender_environment action=generate_multi_biome_world` that exposes it to Claude.

The gap is integration plumbing, not algorithm invention. No new mathematical algorithms are required -- every primitive is proven and has tests. The work is composing them with the right parameter flow and adding tests for the composed pipeline.

**Primary recommendation:** Build `_biome_grammar.py` (pure logic, ~350 lines) as the composition layer, keep the handler thin (~200 lines), add one new MCP action. All done in ~4 focused tasks.

## Project Constraints (from CLAUDE.md)

- Pure-logic files (no `bpy`/`bmesh` imports) must be fully testable without Blender.
- Handler functions that mutate Blender scenes import `bpy` only at call time.
- All generators use seed-based RNG (`random.Random(seed)`) -- zero global random state.
- Environment saturation NEVER exceeds 40%; value range for environments: 10-50% (dark world).
- MCP tools use compound pattern: one tool name, `action` param selects operation.
- After every Blender mutation, verify visually via `blender_viewport action=contact_sheet`.
- Run `blender_mesh action=game_check` before export.
- Pipeline order: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.

## Standard Stack

### Core (all already in-repo, verified present)

| Module | Location | Purpose |
|--------|----------|---------|
| `_terrain_noise.py` | `handlers/` | `voronoi_biome_distribution()`, `generate_heightmap()`, `compute_slope_map()` |
| `terrain_materials.py` | `handlers/` | `BIOME_PALETTES` (14 biomes), `BIOME_PALETTES_V2`, `apply_corruption_tint()`, `compute_biome_transition()`, `auto_assign_terrain_layers()`, `handle_setup_terrain_biome()`, `handle_create_biome_terrain()` |
| `terrain_advanced.py` | `handlers/` | `flatten_terrain_zone()`, `flatten_multiple_zones()`, `handle_snap_to_terrain()` |
| `terrain_features.py` | `handlers/` | Canyon, cliff, waterfall, arch, lava flow geometry generators |
| `vegetation_system.py` | `handlers/` | `handle_scatter_biome_vegetation()`, `BIOME_VEGETATION_SETS`, Poisson disk scatter |
| `vegetation_lsystem.py` | `handlers/` | `LSYSTEM_GRAMMARS` (oak, pine, birch, etc.), leaf card geometry, billboard LOD |
| `settlement_generator.py` | `handlers/` | `_compute_foundation_height()`, `_compute_foundation_profile()` |
| `environment.py` | `handlers/` | `handle_generate_terrain()`, `VB_BIOME_PRESETS` (thornwood_forest, etc.) |
| `modular_building_kit.py` | `handlers/` | `foundation_block()`, `foundation_stepped()` |

### Supporting

| Library | Purpose | Already available |
|---------|---------|-------------------|
| `numpy` | Heightmap arrays, Voronoi math | Yes |
| `opensimplex` (optional) | Better noise; permutation-table fallback exists | Yes |

### No new dependencies required.

## Architecture Patterns

### Recommended New File Structure

```
handlers/
├── _biome_grammar.py         # NEW: pure-logic biome world map composer (~350 lines)
├── _terrain_noise.py         # EXISTING: voronoi_biome_distribution() -- no changes
├── terrain_materials.py      # EXISTING: palettes + tinting -- no changes
├── terrain_advanced.py       # EXISTING: flatten zones -- no changes
├── vegetation_system.py      # EXISTING: scatter_biome_vegetation -- no changes
└── environment.py            # EXISTING: handle_generate_terrain -- small extension
tests/
└── test_biome_grammar.py     # NEW: pure-logic tests for _biome_grammar.py
```

### Pattern 1: Pure-Logic Composition Layer (`_biome_grammar.py`)

**What:** Owns the world-map generation spec. Takes `width`, `height`, `biome_count`, `biomes`, `seed`, and `corruption_map` parameters and returns a `WorldMapSpec` dataclass. No bpy.

**Key responsibilities:**
- Call `voronoi_biome_distribution()` to produce `biome_ids` and `biome_weights`.
- Map biome indices to VeilBreakers biome names (from `BIOME_PALETTES`).
- Assign temperature/moisture/elevation parameters per Voronoi cell.
- Compute per-cell corruption level (0.0-1.0) from a noise map.
- Produce flatten zone specs for building foundation placement (list of `{"center_x", "center_y", "radius", "blend_width"}`).
- Return a `WorldMapSpec` with enough data to drive the Blender handler.

```python
# Source: _terrain_noise.py voronoi_biome_distribution signature
from ._terrain_noise import voronoi_biome_distribution
from .terrain_materials import BIOME_PALETTES

AVAILABLE_BIOMES = list(BIOME_PALETTES.keys())  # 14 names

@dataclass
class WorldMapSpec:
    width: int
    height: int
    seed: int
    biome_ids: np.ndarray         # (height, width) int
    biome_weights: np.ndarray     # (height, width, biome_count) float
    biome_names: list[str]        # biome_count entries from BIOME_PALETTES
    corruption_map: np.ndarray    # (height, width) float in [0, 1]
    flatten_zones: list[dict]     # for building foundation placement
    cell_params: list[dict]       # per-biome: temperature, moisture, elevation
```

**When to use:** Called by the Blender handler. All tests target this module.

### Pattern 2: Thin Blender Handler Extension (`environment.py`)

**What:** Add `handle_generate_multi_biome_world()` to `environment.py`. Calls `_biome_grammar.generate_world_map_spec()`, then:
1. `handle_generate_terrain()` with merged heightmap parameters.
2. `handle_create_biome_terrain()` per biome zone with proper material.
3. `flatten_multiple_zones()` for each building plot.
4. `handle_scatter_biome_vegetation()` per biome zone.

No new algorithms -- pure orchestration.

### Pattern 3: MCP Action Extension (`blender_server.py`)

**What:** Add `"generate_multi_biome_world"` to the `blender_environment` Literal action list. Wire to `handle_generate_multi_biome_world()`.

**Parameters to add:**
- `biomes: list[str] | None` -- which biomes to include (defaults to 6 from VB presets)
- `world_size: float | None` -- terrain size in meters (default 512.0)
- `biome_count: int | None` -- number of Voronoi regions (default 6)
- `corruption_level: float | None` -- global corruption intensity (default 0.0)
- `building_plots: list[dict] | None` -- pre-placed building footprints to flatten

### Anti-Patterns to Avoid

- **Hardcoded biome boundaries:** Always use Voronoi + domain warping (already in `voronoi_biome_distribution`). Never use axis-aligned rectangles.
- **Global random state:** Use `random.Random(seed)` for all stochastic choices. `voronoi_biome_distribution` already does this.
- **Biome-per-separate-mesh:** The full world is ONE terrain mesh with Voronoi-weighted vertex colors driving material blending. Not 6 separate terrain patches.
- **Hand-rolling climate simulation:** Temperature/moisture are noise-map approximations, not full simulation. The existing `compute_biome_assignments()` approach is sufficient.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Voronoi cell distance math | Custom Voronoi | `voronoi_biome_distribution()` in `_terrain_noise.py` |
| Biome boundary blending | Custom alpha lerp | `compute_biome_transition()` in `terrain_materials.py` |
| Corruption tint | Custom color mixer | `apply_corruption_tint()` in `terrain_materials.py` |
| Terrain flatten for buildings | Custom heightmap edit | `flatten_terrain_zone()` / `flatten_multiple_zones()` in `terrain_advanced.py` |
| Per-biome material assignment | Hand-written shader | `handle_create_biome_terrain()` + `BIOME_PALETTES_V2` in `terrain_materials.py` |
| L-system trees | Sphere-cluster canopy | `LSYSTEM_GRAMMARS` + `handle_generate_lsystem_tree()` in `vegetation_lsystem.py` |
| Poisson disk scatter | Uniform random placement | `handle_scatter_biome_vegetation()` in `vegetation_system.py` |
| Foundation height calculation | Manual Z-offset | `_compute_foundation_profile()` in `settlement_generator.py` |

**Key insight:** Every difficult algorithm is already implemented and tested. Phase 34 is a composition phase, not an algorithm phase.

## What Already Exists vs What Needs Writing

### Already exists (verified in source):

| Capability | Location | Status |
|------------|----------|--------|
| `voronoi_biome_distribution()` with domain warping | `_terrain_noise.py:1234` | Complete, 4 tests |
| `BIOME_PALETTES` (14 biomes) | `terrain_materials.py:877` | Complete |
| `BIOME_PALETTES_V2` (full per-layer defs) | `terrain_materials.py:1810` | Complete |
| `apply_corruption_tint()` | `terrain_materials.py:1253` | Complete |
| `compute_biome_transition()` | `terrain_materials.py:1330` | Complete |
| `auto_assign_terrain_layers()` | `terrain_materials.py` | Complete |
| `handle_create_biome_terrain()` | `terrain_materials.py:2156` | Complete |
| `handle_setup_terrain_biome()` | `terrain_materials.py:1638` | Complete |
| `flatten_terrain_zone()` | `terrain_advanced.py:1454` | Complete, 193 tests |
| `flatten_multiple_zones()` | `terrain_advanced.py:1504` | Complete |
| `handle_snap_to_terrain()` | `terrain_advanced.py:1357` | Complete |
| `handle_scatter_biome_vegetation()` | `vegetation_system.py:637` | Complete |
| L-system tree grammars (5+ species) | `vegetation_lsystem.py` | Complete |
| `_compute_foundation_profile()` | `settlement_generator.py:1453` | Complete |
| `foundation_block()`, `foundation_stepped()` | `modular_building_kit.py` | Complete |
| VB biome presets | `environment.py:VB_BIOME_PRESETS` | Complete |
| `generate_terrain` Blender handler | `environment.py` | Complete |
| Corruption tint: purple/black overlay per biome | `terrain_materials.py` | Complete |

### Does NOT yet exist (needs writing):

| Gap | Module | Why Needed |
|----|--------|-----------|
| `WorldMapSpec` dataclass + `generate_world_map_spec()` | `_biome_grammar.py` (new file) | Composition layer that drives the full pipeline |
| Per-cell temperature/moisture/elevation params driving biome selection | `_biome_grammar.py` | Req SC-1: "temperature/moisture/elevation parameters per cell" |
| Corruption noise map generator (0-100% per region) | `_biome_grammar.py` | Req SC-3: corruption tinting per biome region |
| `handle_generate_multi_biome_world()` Blender handler | `environment.py` | Orchestrator calling all sub-handlers |
| `generate_multi_biome_world` MCP action | `blender_server.py` | Exposes capability to Claude |
| Foundation-mesh contact-edge material blend | `_biome_grammar.py` / handler | Req SC-4: "material blending at foundation-terrain contact edge" |
| Tests for `_biome_grammar.py` | `tests/test_biome_grammar.py` | Coverage requirement |

## Common Pitfalls

### Pitfall 1: Biome ID to Name Mapping Off-by-One
**What goes wrong:** `voronoi_biome_distribution()` returns integer IDs 0..N-1. If caller passes 6 biomes but only 5 names in the list, the 6th ID is unmapped -- KeyError at material assignment time.
**How to avoid:** `WorldMapSpec.biome_names` must have exactly `biome_count` entries. Validate `len(biome_names) == biome_count` in `generate_world_map_spec()`.

### Pitfall 2: Biome Transition Mismatch Between V1 and V2 Palettes
**What goes wrong:** `compute_biome_transition()` uses `BIOME_PALETTES_V2`; `get_biome_palette()` uses `BIOME_PALETTES` (V1). Not all 14 biomes appear in V2. Calling a V2 function with a V1-only biome name raises ValueError.
**How to avoid:** Check `BIOME_PALETTES_V2.keys()` before calling transition functions. Fall back to V1 palette if biome not in V2.

### Pitfall 3: Flatten Zone Coordinates Must Be Normalized
**What goes wrong:** `flatten_terrain_zone()` expects `center_x/y` in [0,1] (normalized). If caller passes world-space meters, the zone is placed at (0,0) or off the edge.
**How to avoid:** In `generate_world_map_spec()`, always convert building plot positions to normalized coordinates: `center_x = plot_x / world_size`.

### Pitfall 4: `handle_scatter_biome_vegetation()` Requires Terrain Object in Scene
**What goes wrong:** If called before the terrain mesh is linked to the Blender scene (before `handle_generate_terrain()` returns), the `bpy.data.objects.get(terrain_name)` lookup returns None.
**How to avoid:** Handler execution order must be: (1) generate terrain mesh, (2) apply biome materials, (3) scatter vegetation. Never call scatter first.

### Pitfall 5: Contact Edge Blend Requires Vertex Color Layer
**What goes wrong:** `apply_corruption_tint()` modifies a list of RGBA tuples -- it does NOT create a vertex color layer in Blender. The handler must explicitly create a `vertex_colors` attribute and write the computed colors.
**How to avoid:** In `handle_generate_multi_biome_world()`, after calling `apply_corruption_tint()`, write results to `mesh.color_attributes` (Blender 3.2+ API) or `mesh.vertex_colors` (legacy).

## Code Examples

### Calling voronoi_biome_distribution

```python
# Source: _terrain_noise.py:1234
from blender_addon.handlers._terrain_noise import voronoi_biome_distribution

biome_ids, biome_weights = voronoi_biome_distribution(
    width=256,
    height=256,
    biome_count=6,
    transition_width=0.15,   # ~15% of world size = 77m on 512m map
    seed=42,
    biome_names=["thornwood_forest", "corrupted_swamp", "mountain_pass",
                 "volcanic_wastes", "frozen_tundra", "grasslands"],
)
# biome_ids.shape == (256, 256) -- integer 0-5
# biome_weights.shape == (256, 256, 6) -- soft blend weights, sum=1
```

### Applying corruption tint to vertex colors

```python
# Source: terrain_materials.py:1253
from blender_addon.handlers.terrain_materials import apply_corruption_tint

# vertex_colors: list of (R, G, B, A) from terrain layer assignment
corrupted = apply_corruption_tint(vertex_colors, corruption_level=0.65)
# Returns new list -- input unchanged
```

### Flattening a building foundation zone

```python
# Source: terrain_advanced.py:1454
from blender_addon.handlers.terrain_advanced import flatten_multiple_zones

zones = [
    {"center_x": 0.3, "center_y": 0.4, "radius": 0.04, "blend_width": 0.02},
    {"center_x": 0.7, "center_y": 0.6, "radius": 0.06, "blend_width": 0.03},
]
heightmap = flatten_multiple_zones(heightmap, zones)
# heightmap shape unchanged; zones are level platforms with smoothstep edges
```

### Scatter biome vegetation (Blender handler, requires terrain in scene)

```python
# Source: vegetation_system.py:637
result = handle_scatter_biome_vegetation({
    "terrain_name": "MultibiomeTerrain",
    "biome_name": "thornwood_forest",
    "min_distance": 4.0,
    "seed": 42,
    "max_instances": 3000,
    "season": "corrupted",
    "bake_wind_colors": True,
    "water_level": 0.05,
})
# result["instance_count"] = number placed
```

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Axis-aligned biome rectangles | Voronoi + domain warping | `voronoi_biome_distribution()` already implements this |
| Hard biome edges | Softmax distance weighting in Voronoi | Already in `_terrain_noise.py` |
| Flat-color biome materials | BIOME_PALETTES_V2 with per-slope/height layer rules | Already in `terrain_materials.py` |
| Sphere-cluster tree canopies | L-system branching (oak/pine/birch/willow/corrupted_tree) | `vegetation_lsystem.py` |
| Uniform random scatter | Poisson disk (Bridson's algorithm) via `_scatter_engine.py` | `vegetation_system.py` |

## Environment Availability

Step 2.6: SKIPPED -- Phase 34 operates entirely on Blender objects and pure-logic Python. No new external CLI tools, databases, or services are required beyond what Phase 31 established.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `Tools/mcp-toolkit/pyproject.toml` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_biome_grammar.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MESH-09 | Voronoi distribution produces 5+ distinct biome regions | unit | `pytest tests/test_terrain_biome_voronoi.py -x` | YES (96 lines) |
| MESH-09 | WorldMapSpec.biome_names maps all biome_count IDs | unit | `pytest tests/test_biome_grammar.py::TestWorldMapSpec -x` | NO -- Wave 0 |
| MESH-09 | Corruption map values in [0,1] for all cells | unit | `pytest tests/test_biome_grammar.py::TestCorruptionMap -x` | NO -- Wave 0 |
| MESH-09 | Blend zones 10-20m (transition_width 0.02-0.04 on 512m map) | unit | `pytest tests/test_biome_grammar.py::TestTransitionWidth -x` | NO -- Wave 0 |
| MESH-05 | flatten_terrain_zone produces level platform with smoothstep | unit | `pytest tests/test_terrain_flatten.py -x` | YES (193 lines) |
| MESH-05 | Foundation profile correctly computes height from heightmap | unit | `pytest tests/test_biome_grammar.py::TestFoundationPlacements -x` | NO -- Wave 0 |
| MESH-10 | L-system trees have 3+ species with leaf geometry | unit | `pytest tests/test_biome_grammar.py::TestVegetationSpec -x` | NO -- Wave 0 |

### Wave 0 Gaps

- [ ] `tests/test_biome_grammar.py` -- covers WorldMapSpec, corruption map, transition width, foundation placement, vegetation spec

*(Existing tests: `test_terrain_biome_voronoi.py` (Voronoi math), `test_terrain_flatten.py` (flatten zones), `test_terrain_materials.py` (biome palettes) all pass and cover the primitives. New file only needed for the composition layer.)*

## Open Questions

1. **Volcanic wastes and frozen tundra biome names**
   - What we know: `BIOME_PALETTES` has 14 named biomes; success criteria mentions "volcanic wastes" and "frozen tundra" but those exact keys are not in BIOME_PALETTES.
   - What's unclear: Should we add them as new palette entries, or map them to the closest existing biome (e.g., "desert" -> "volcanic_wastes")?
   - Recommendation: Add "volcanic_wastes" and "frozen_tundra" as aliases in `_biome_grammar.py` mapping to existing palette materials, so no changes needed in `terrain_materials.py`.

2. **BIOME_PALETTES_V2 coverage**
   - What we know: `compute_biome_transition()` requires biome names to be in V2. Not all 14 V1 biomes appear in V2.
   - What's unclear: Which V1 biomes lack V2 entries?
   - Recommendation: Audit V2 keys at plan time; fall back gracefully.

3. **512m world map performance**
   - What we know: `voronoi_biome_distribution(256, 256, 6)` is fast (numpy-vectorized). A 512x512 grid is 4x the data.
   - What's unclear: Whether Blender mesh creation at 512x512 resolution (262K verts) is within acceptable interactive time.
   - Recommendation: Default resolution to 256 (65K verts), with `high_quality` flag for 512. This matches existing `environment.py` pattern (default `resolution=256`).

## Sources

### Primary (HIGH confidence)

- Direct source reading: `_terrain_noise.py`, `terrain_materials.py`, `terrain_advanced.py`, `vegetation_system.py`, `vegetation_lsystem.py`, `settlement_generator.py`, `environment.py`, `modular_building_kit.py` -- all verified by reading actual function signatures and implementations
- Test files: `test_terrain_biome_voronoi.py`, `test_terrain_flatten.py`, `test_terrain_materials.py` -- verified by reading

### Secondary (MEDIUM confidence)

- `ROADMAP.md` Phase 34 success criteria (lines 531-540) -- authoritative spec
- `REQUIREMENTS.md` MESH-05/09/10 (lines 574-576) -- requirement definitions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all modules read directly from source
- Architecture: HIGH -- based on existing proven patterns in same codebase
- Pitfalls: HIGH -- derived from reading actual function signatures and their validation logic
- Missing capabilities: HIGH -- confirmed by absence in grep results

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable, no external dependencies)
