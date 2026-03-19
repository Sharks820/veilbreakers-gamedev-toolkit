---
phase: 06-environment-world-building
plan: 01
status: complete
completed: 2026-03-19
tests_passed: 84  # 41 terrain_noise + 13 terrain_erosion + 30 environment_handlers
tests_total: 84
regressions: 0
full_suite: 998 passed
---

# Phase 06 Plan 01 Summary: Terrain Generation System

## What was built

### Pure-logic module: `_terrain_noise.py`
- **Heightmap generation** (`generate_heightmap`): fBm noise using opensimplex with 6 terrain-type presets (mountains, hills, plains, volcanic, canyon, cliffs). Each preset controls octaves, persistence, lacunarity, amplitude, and post-processing (power curves, smoothing, crater radial falloff, ridge subtraction, step quantization). Deterministic via seed parameter. All outputs normalized to [0, 1].
- **Slope computation** (`compute_slope_map`): Uses `np.gradient()` to compute per-cell slope in degrees [0, 90].
- **Biome assignment** (`compute_biome_assignments`): Priority-ordered rule matching on altitude + slope ranges. Default dark-fantasy rules: snow, rock, dead_grass, mud. Returns integer index array.
- **River carving** (`carve_river_path`): A* pathfinding preferring downhill routes. Carves channel with distance-based depth falloff. Returns path coordinates and modified heightmap.
- **Road generation** (`generate_road_path`): Weighted A* preferring low-slope routes. Flattens terrain along corridor with configurable grade strength. Supports multi-waypoint routes.
- **TERRAIN_PRESETS** and **BIOME_RULES** constants for reuse across handlers.
- Zero bpy/bmesh imports. Fully testable outside Blender.

### Pure-logic module: `_terrain_erosion.py`
- **Hydraulic erosion** (`apply_hydraulic_erosion`): Droplet-based simulation with bilinear interpolation, inertia, sediment capacity, erosion/deposition, evaporation. Brush-based erosion kernel for smooth results. Deterministic via seed.
- **Thermal erosion** (`apply_thermal_erosion`): Talus-angle based material transfer. Reduces maximum slope by redistributing material from steep to flat areas.
- Both functions clamp output to [0, 1]. Flat heightmaps produce near-identical output (no unnecessary modification).
- Zero bpy/bmesh imports.

### Blender handlers: `environment.py`
- `handle_generate_terrain` -- Heightmap to bmesh grid with optional hydraulic/thermal/both erosion. Returns name, vertex_count, terrain_type, resolution, height_scale, erosion_applied.
- `handle_paint_terrain` -- Slope/altitude biome rules applied as per-face material slot assignments via bmesh. Default dark-fantasy palette.
- `handle_carve_river` -- Extracts heightmap from mesh vertices, carves A* river channel, writes back to mesh.
- `handle_generate_road` -- Extracts heightmap, generates graded road between waypoints, writes back to mesh.
- `handle_create_water` -- Flat plane at water level with transparent blue material. Matches terrain size if terrain_name provided.
- `handle_export_heightmap` -- Extracts heightmap from mesh, exports as 16-bit little-endian RAW for Unity. Supports flip_vertical and unity_compat (nearest POT+1 resize).
- Pure-logic helpers (`_validate_terrain_params`, `_export_heightmap_raw`, `_nearest_pot_plus_1`) extracted for testability.

### Handler registration
- 6 new entries in `COMMAND_HANDLERS`: `env_generate_terrain`, `env_paint_terrain`, `env_carve_river`, `env_generate_road`, `env_create_water`, `env_export_heightmap`

### Dependencies
- Added `opensimplex>=0.4.5` to `[project] dependencies` in pyproject.toml
- Moved `numpy>=1.26.0` from `[dependency-groups] dev` to `[project] dependencies` (required at runtime by terrain algorithms and opensimplex)

## Test coverage

| Test file | Tests | Coverage |
|-----------|-------|----------|
| test_terrain_noise.py | 41 | 6 terrain types, determinism, amplitude comparison, slope map, biome assignment (4 rules), river carving (connectivity, bounds), road grading |
| test_terrain_erosion.py | 13 | Hydraulic shape/bounds/determinism/modification/flat, thermal shape/bounds/slope-reduction/flat/extremes |
| test_environment_handlers.py | 30 | Param validation (resolution limits, type checking, erosion modes), RAW export (byte length, uint16 values, endianness, flip), POT+1 calculation |

## Files modified/created

| File | Action |
|------|--------|
| `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` | Created |
| `Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py` | Created |
| `Tools/mcp-toolkit/blender_addon/handlers/environment.py` | Created |
| `Tools/mcp-toolkit/blender_addon/handlers/__init__.py` | Modified (added imports + 6 COMMAND_HANDLERS entries) |
| `Tools/mcp-toolkit/pyproject.toml` | Modified (added numpy + opensimplex to project deps) |
| `Tools/mcp-toolkit/tests/test_terrain_noise.py` | Created |
| `Tools/mcp-toolkit/tests/test_terrain_erosion.py` | Created |
| `Tools/mcp-toolkit/tests/test_environment_handlers.py` | Created |
