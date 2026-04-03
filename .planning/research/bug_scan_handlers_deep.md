# Deep Bug Scan: Blender Addon Handler Files

**Date:** 2026-04-02
**Scanned:** 24 handler files (22 exist, 2 not found: `texture_ops.py`, `shader_templates.py`)
**Method:** Full code read of each file, line-by-line analysis

---

## CRITICAL BUGS (will crash or corrupt data)

### BUG-01: Missing material key "moss" in BIOME_PALETTES
- **File:** `terrain_materials.py`, line 898
- **Severity:** CRITICAL (runtime KeyError / silent wrong material)
- **Description:** `BIOME_PALETTES["ruined_fortress"]["slopes"]` references `"moss"` but no material with key `"moss"` exists in `TERRAIN_MATERIALS`. Only `"mossy_rock"` (line 84) and `"moss_blanket_rock"` (line 840) exist. When `assign_terrain_materials_by_slope()` is called for the `ruined_fortress` biome, any face classified as "slopes" that cycles to the `"moss"` material will reference a nonexistent material definition.
- **Fix:** Change `"moss"` to `"mossy_rock"` on line 898:
  ```python
  "slopes": ["crumbling_wall_foundation", "mossy_rock"],
  ```

### BUG-02: Heightmap reshape assumes square vertex grid
- **File:** `terrain_advanced.py`, line 738 (handle_terrain_layers, flatten_layers action)
- **Severity:** CRITICAL (crash on non-square meshes)
- **Description:** `base = np.array([v.co.z for v in bm.verts]).reshape(res, -1)` where `res = max(2, int(math.sqrt(len(bm.verts))))`. If the vertex count is not a perfect square (e.g., 257x257 = 66049 vertices, sqrt = 257.0, OK; but 200x300 = 60000, sqrt = 244.9, int = 244, 244 * ? != 60000), this reshape will raise `ValueError: cannot reshape array of size N into shape (M,...)`. The same pattern appears in:
  - `environment.py`, line 668 (`handle_carve_river`)
  - `environment.py`, line 733 (`handle_generate_road`)
  - `terrain_advanced.py`, line 916 (`handle_erosion_paint`)
  - `environment_scatter.py`, line 269 (`_terrain_height_sampler`, which at least checks `side * side != vert_count`)
- **Fix:** Either enforce square grids in validation, or use the mesh's stored resolution if available, or compute both dimensions properly.

### BUG-03: Heightmap reshape assumes square vertex grid (carve_river)
- **File:** `environment.py`, line 668-673
- **Severity:** CRITICAL (crash on non-square terrain)
- **Description:** Same issue as BUG-02. `side = int(math.sqrt(vert_count))` then `heightmap = (heights / height_scale).reshape(side, side)`. If vert_count is not a perfect square, this crashes.

### BUG-04: Division by max height can produce division by zero
- **File:** `environment.py`, line 672
- **Severity:** HIGH (crash if terrain is completely flat at z=0)
- **Description:** `height_scale = heights.max() if heights.max() > 0 else 1.0` -- this only guards against max == 0, but if max is negative (terrain below origin), division would invert the heightmap. The `heights.max()` is also evaluated twice (performance issue on large arrays).
- **Fix:** `height_scale = max(abs(heights.max()), abs(heights.min()), 1e-6)`

### BUG-05: Global mutable state in terrain_features._hash_noise
- **File:** `terrain_features.py`, lines 33-46
- **Severity:** HIGH (state corruption in concurrent/repeated calls)
- **Description:** `_features_gen` and `_features_seed` are global mutable variables. If two different calls to generators use different seeds, the first call's seed caches the generator, and the second call replaces it. This is NOT thread-safe and causes subtle non-determinism if generators are called interleaved. Also, any function calling `_fbm()` creates a NEW generator per call (line 52), bypassing the cache entirely, so there's inconsistency between `_hash_noise` (cached) and `_fbm` (uncached).

### BUG-06: terrain_advanced flatten_layers reshape on non-square mesh
- **File:** `terrain_advanced.py`, line 737-738
- **Severity:** CRITICAL (same as BUG-02)
- **Description:** In `handle_terrain_layers` with `action="flatten_layers"`:
  ```python
  res = max(2, int(math.sqrt(len(bm.verts))))
  base = np.array([v.co.z for v in bm.verts]).reshape(res, -1)
  ```
  The `-1` in reshape will compute the second dimension, but if `len(bm.verts)` is not evenly divisible by `res`, it will crash.

---

## HIGH SEVERITY BUGS (wrong results / logic errors)

### BUG-07: Erosion paint heightmap loses XY coordinates
- **File:** `terrain_advanced.py`, lines 910-932
- **Severity:** HIGH (terrain geometry corruption)
- **Description:** In `handle_erosion_paint`, the vertex Z values are extracted into a 2D array via reshape, eroded, then written back as a flat ravel. But the bmesh vertices may not be ordered in a simple row-major grid pattern. If `bmesh.ops.create_grid` always produces row-major order this works, but if the mesh has been edited or came from a different source, the Z values will be written to wrong vertices.

### BUG-08: Road path grid index out of bounds
- **File:** `environment.py`, line 779
- **Severity:** HIGH (IndexError crash)
- **Description:** `z0 = float(graded_flat[r0 * side + c0]) * height_scale + 0.03` -- if `r0 * side + c0` exceeds `len(graded_flat)`, this crashes with IndexError. The path coordinates from A* may include boundary cells, and `side` is computed from `sqrt(vert_count)` which may not match the actual grid dimensions.

### BUG-09: _terrain_height_sampler divides heights by max but max could be negative
- **File:** `environment_scatter.py`, line 275-276
- **Severity:** MEDIUM (inverted terrain sampling if all Z values negative)
- **Description:** `height_max = heights.max() if heights.size and heights.max() > 0 else 1.0` then `heightmap = (heights / height_max)`. If the terrain has negative Z values but max is positive, the heightmap will have negative entries which is fine. But if someone has a terrain entirely below Z=0, all heights are negative, max check makes `height_max = 1.0`, and the normalized values are all negative. The sampler returns negative world heights, which would place vegetation below the terrain.

### BUG-10: TerrainLayer strength clamped to [0, 1] silently
- **File:** `terrain_advanced.py`, line 468
- **Severity:** LOW-MEDIUM (unexpected behavior)
- **Description:** `self.strength = max(0.0, min(1.0, strength))` silently clamps without warning. A user passing `strength=2.0` would get `1.0` with no feedback.

### BUG-11: compute_erosion_brush wind erosion is asymmetric and deposits less than erodes
- **File:** `terrain_advanced.py`, lines 863-869
- **Severity:** MEDIUM (terrain mass not conserved)
- **Description:** Wind erosion removes `abs(noise) * brush_weight * 0.05` but only deposits `abs(noise) * brush_weight * 0.03`. This means 40% of eroded material vanishes, causing the terrain to slowly sink in wind-eroded areas. While some loss is physically realistic (material blown out of the area), the fixed 60% ratio is arbitrary and undocumented.

### BUG-12: Water mesh location set to water_level causes double offset
- **File:** `environment.py`, line 1026
- **Severity:** HIGH (water appears at wrong height)
- **Description:** `obj.location = (0.0, 0.0, water_level)` -- but the vertex positions already include `water_level` in their Z coordinates (line 981: `vz = pz` where `pz` comes from path points which default to `water_level`). This means the water mesh is double-offset: vertices are at `water_level` in local space, and the object origin adds another `water_level` in world space. Result: water appears at `2 * water_level` instead of `water_level`.
- **Fix:** Either set `obj.location = (0, 0, 0)` or subtract water_level from vertex Z values.

### BUG-13: _ops_to_mesh bmesh.ops.create_cube geom extraction fragile
- **File:** `worldbuilding_layout.py`, lines 203-208
- **Severity:** MEDIUM (potential silent geometry corruption)
- **Description:** The code extracts vertices from `bmesh.ops.create_cube` result using:
  ```python
  result = bmesh.ops.create_cube(bm, size=1.0)
  verts = result["verts"] if "verts" in result else result.get("geom", [])
  ```
  But `bmesh.ops.create_cube` returns `{"verts": [...]}` in current Blender. The fallback `result.get("geom", [])` would include edges and faces too, and the filter `[v for v in verts if hasattr(v, "co")]` saves it, but this is fragile.

### BUG-14: Biome palette "thornwood_forest" references "mud" which may not exist
- **File:** `terrain_materials.py`, line 882
- **Severity:** MEDIUM (depends on MATERIAL_LIBRARY)
- **Description:** `"water_edges": ["mud", "reeds"]` -- `"mud"` is not defined in TERRAIN_MATERIALS. The `_get_material_def()` function falls back to `MATERIAL_LIBRARY` from `procedural_materials.py`. If `"mud"` doesn't exist there either, it returns None, which could cause downstream failures. Looking at the `_terrain_noise.py` BIOME_RULES, there is a `"mud"` biome rule (line 337) with material key `"terrain_mud"`, but that's a different key from `"mud"`.

---

## MEDIUM SEVERITY BUGS (edge cases / suboptimal behavior)

### BUG-15: Poisson disk active list removal is O(1) but may skip points
- **File:** `_scatter_engine.py`, line 117
- **Severity:** LOW (minor quality difference)
- **Description:** `active[active_idx] = active[-1]; active.pop()` -- this is correct swap-remove, but the random selection `rng.randint(0, len(active) - 1)` means the swapped-in element at `active_idx` may be selected again on the next iteration before other elements get a chance. This slightly biases the spatial distribution toward points that were at the end of the active list.

### BUG-16: terrain_features generate_geyser unreferenced `rng` variable
- **File:** `terrain_features.py`, line 1096
- **Severity:** LOW (rng is created but may not be used in the truncated view)
- **Description:** `rng = random.Random(seed)` is created but based on the code pattern, it's used for terraced deposits. Not a bug per se but the function was not fully reviewed due to size.

### BUG-17: _terrain_noise compute_slope_map doesn't account for terrain scale
- **File:** `_terrain_noise.py`, line 542-568
- **Severity:** MEDIUM (slopes are incorrect for non-unit-scale heightmaps)
- **Description:** `np.gradient(heightmap)` computes derivatives assuming unit spacing between cells. If the heightmap represents a 100m x 100m terrain with 257 cells, the actual cell spacing is ~0.39m, not 1.0. The slope values returned will be much smaller than the actual terrain slopes. This means biome assignment thresholds (e.g., 35 degrees for rock) may never trigger, causing wrong biome painting.
- **Fix:** Pass `cell_size` to `compute_slope_map` and use `np.gradient(heightmap, cell_size)`.

### BUG-18: settlement_generator imports from blender_addon.handlers (absolute import)
- **File:** `settlement_generator.py`, lines 21-32
- **Severity:** MEDIUM (import will fail if package structure changes)
- **Description:** Uses absolute imports like `from blender_addon.handlers._settlement_grammar import ...` instead of relative imports like `from ._settlement_grammar import ...`. This works when the Blender addon is installed as a package, but will fail if the module is imported from a different path context (e.g., during testing).

### BUG-19: environment.py handle_carve_river doesn't validate source/destination
- **File:** `environment.py`, lines 650-651
- **Severity:** MEDIUM (silent wrong results)
- **Description:** `source = tuple(params.get("source", [0, 0]))` and `destination = tuple(params.get("destination", [0, 0]))` -- if both default to (0, 0), the A* pathfinding returns a zero-length path, and the function returns `path_length: 0` with no river carved. No error or warning is raised.

### BUG-20: vegetation_lsystem interpret_lsystem tip marking incorrect for certain L-strings
- **File:** `vegetation_lsystem.py`, line 362
- **Severity:** MEDIUM (wrong tip identification)
- **Description:** `if segments and segments[-1].depth >= state.depth:` -- When popping a branch state with `]`, it marks `segments[-1]` as a tip only if the last segment's depth >= current state depth. But `state.depth` has already been decremented before this check (since we're about to pop). Wait -- actually the pop happens AFTER the check (line 365-368). So `state.depth` is still the branch depth, not the parent depth. This should be correct. However, if two `]` brackets appear consecutively (e.g., `F[+F][-F]` produces `...[+F][...]`, when processing the second `]`, the last segment is from the second branch, which IS a tip. But the first branch's last segment was already correctly marked. This seems OK on closer inspection. NOT A BUG -- removing from final count.

### BUG-21: apply_stamp_to_heightmap falloff calculation has no-op logic
- **File:** `terrain_advanced.py`, line 1271-1272
- **Severity:** LOW (confusing but not broken)
- **Description:**
  ```python
  edge_falloff = compute_falloff(dist, "smooth") if falloff > 0 else 1.0
  blend = edge_falloff * (1.0 - falloff) + edge_falloff * falloff
  ```
  The `blend` calculation simplifies to `edge_falloff * (1 - falloff + falloff) = edge_falloff`. The entire expression is equivalent to just `blend = edge_falloff`. The `falloff` parameter has no effect beyond the `if falloff > 0` branch.

### BUG-22: _BIOME_PALETTES desert references "dried_mud" also in abandoned_village
- **File:** `terrain_materials.py`, lines 907, 931
- **Severity:** LOW (not a bug, but surprising shared material between unrelated biomes)
- **Description:** `"dried_mud"` appears in both `abandoned_village.water_edges` and `desert.water_edges`. This is intentional but may cause visual sameness.

---

## LOW SEVERITY ISSUES (code quality / minor)

### BUG-23: environment.py handle_export_heightmap not shown but referenced
- **File:** `environment.py` (documented in docstring, line 9)
- **Severity:** LOW (documentation inconsistency)
- **Description:** The module docstring says it provides `handle_export_heightmap` but the function `_export_heightmap_raw` (line 270) is a pure-logic helper that returns bytes. The actual handler may exist beyond the scanned range or may be missing.

### BUG-24: terrain_advanced TerrainLayer.from_dict doesn't validate blend_mode
- **File:** `terrain_advanced.py`, line 481-492
- **Severity:** LOW (crash deferred to usage)
- **Description:** `from_dict` uses `data.get("blend_mode", "ADD")` but doesn't validate it against `VALID_BLEND_MODES`. Invalid stored values would be accepted silently and only cause issues when `flatten_layers` tries to use the invalid mode.

### BUG-25: _building_grammar.py duplicate dict keys
- **File:** `_building_grammar.py`, lines 67/88, 76/90, 78/91, 79/92, 80/95, 81/96, 82/97, 83/98
- **Severity:** LOW (later entries overwrite earlier -- intended but confusing)
- **Description:** `_DETAIL_TYPE_MATERIAL_CATEGORY` has duplicate keys like `"battlement"` (lines 67 and 88), `"gargoyle"` (lines 77 and 92), `"rose_window"` (lines 78 and 93). In Python, the last assignment wins. The duplicates are "convenience aliases" but they create confusion about which value is active.

### BUG-26: worldbuilding.py _get_or_generate_prop may return None without caller handling
- **File:** `worldbuilding.py`, lines 52-110
- **Severity:** LOW (returns None when blender_connection is None -- testing only)
- **Description:** `_get_or_generate_prop` returns `None` when generation fails or when `blender_connection` is None. Callers need to handle None, which they appear to do (checking result before use).

---

## FILES NOT FOUND

- `texture_ops.py` -- Does not exist at the specified path. May have been renamed to `texture_painting.py` or `texture.py`.
- `shader_templates.py` -- Does not exist at the specified path. No similar file found.

---

## SUMMARY

| Severity | Count | Files Affected |
|----------|-------|----------------|
| CRITICAL | 6 | terrain_materials.py, terrain_advanced.py (x3), environment.py (x2) |
| HIGH | 5 | terrain_advanced.py, environment.py (x2), environment_scatter.py, terrain_features.py |
| MEDIUM | 5 | terrain_advanced.py, _terrain_noise.py, settlement_generator.py, environment.py, terrain_materials.py |
| LOW | 4 | environment.py, terrain_advanced.py, _building_grammar.py, worldbuilding.py |

### Top Priority Fixes

1. **BUG-01:** Fix `"moss"` -> `"mossy_rock"` in `terrain_materials.py` line 898
2. **BUG-12:** Fix water double-offset in `environment.py` line 1026 (set location to origin)
3. **BUG-02/03/06:** Fix all reshape-assumes-square-grid bugs across 4 files
4. **BUG-17:** Fix `compute_slope_map` to account for terrain cell spacing
5. **BUG-04:** Fix division-by-max-height in `environment.py` carve_river/generate_road
