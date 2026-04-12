# Terrain Audit Deep Code Review (Phases 49-59)

**Reviewed:** 2026-04-12T02:00:00Z
**Depth:** deep
**Files Requested:** 23
**Files That Exist:** 15
**Files Missing:** 8 (terrain_erosion_filter.py, terrain_delta_integrator.py, terrain_baked.py, terrain_seam_guards.py, terrain_node_registry.py, terrain_seam_stitcher.py, terrain_fault_lines.py, terrain_pipe_erosion.py)
**Status:** issues_found

---

## Missing Files (P1 -- Wiring)

The following 8 files were listed in the review scope but DO NOT EXIST on disk.
If these are intended deliverables from phases 49-59, they were never created.
If they were renamed or merged into other modules, the review request is stale.

- `terrain_erosion_filter.py`
- `terrain_delta_integrator.py`
- `terrain_baked.py`
- `terrain_seam_guards.py`
- `terrain_node_registry.py`
- `terrain_seam_stitcher.py`
- `terrain_fault_lines.py`
- `terrain_pipe_erosion.py`

---

## Critical Bugs (P0)

### P0-01: `get_swamp_specs` accesses non-existent attributes on `Wetland`

**File:** `terrain_water_variants.py:734`
**Issue:** `get_swamp_specs` calls `wl.radius_m` (line 734) and `wl.world_pos` (line 740), but the `Wetland` dataclass (line 88-91) has neither attribute. `Wetland` has `bounds: BBox`, `depth_m: float`, `vegetation_density: float`. This will crash with `AttributeError` at runtime every time `get_swamp_specs` is called.
**Fix:**
```python
# Line 734: replace wl.radius_m with a computed value from bounds
half_x = (wl.bounds.max_x - wl.bounds.min_x) / 2.0
half_y = (wl.bounds.max_y - wl.bounds.min_y) / 2.0
size = max(half_x, half_y) * 2.0

# Line 740: replace wl.world_pos with center of bounds
cx = (wl.bounds.min_x + wl.bounds.max_x) / 2.0
cy = (wl.bounds.min_y + wl.bounds.max_y) / 2.0
results.append({"mesh_spec": spec, "world_pos": (cx, cy, 0.0)})
```

### P0-02: `get_swamp_specs` passes `has_mangroves` kwarg that `generate_swamp_terrain` does not accept

**File:** `terrain_water_variants.py:736`
**Issue:** `get_swamp_specs` calls `generate_swamp_terrain(size=..., water_level=..., hummock_count=..., has_mangroves=..., seed=...)` but `generate_swamp_terrain` (terrain_features.py:688) accepts `(size, water_level, hummock_count, island_count, seed)`. The `has_mangroves` keyword does not exist. This will crash with `TypeError: unexpected keyword argument 'has_mangroves'`.
**Fix:** Replace `has_mangroves=bool(rng.random() > 0.5)` with `island_count=int(rng.integers(2, 6))`.

### P0-03: `pass_waterfalls` silently swallows solver exceptions

**File:** `terrain_waterfalls.py:698-700`
**Issue:** The waterfall chain solver catches bare `Exception` and `continue`s, silently discarding any solver errors. If the solver has a real bug (e.g., the `_water_network_ext` import fails, or a numpy shape mismatch), this will produce zero chains with no diagnostics, making the pass appear to succeed.
**Fix:** At minimum, log the exception. Better: catch only the expected failure modes.
```python
except Exception as exc:
    import logging
    logging.getLogger(__name__).warning(
        "Waterfall solver failed for lip %s: %s", lc.grid_rc, exc
    )
    continue
```

---

## Warnings (P1)

### P1-01: 8 planned handler files do not exist

**File:** (see Missing Files section above)
**Issue:** These modules are referenced in the review scope as terrain audit deliverables. They either were never created, were planned but not implemented, or were merged into other files under different names. Any code that attempts to import from them will fail.
**Fix:** Either create the files as planned, or update the implementation plan and any import references to reflect actual module names.

### P1-02: `pass_materials` in `terrain_materials_v2.py` computes `seed` but does not set `seed_used` on PassResult

**File:** `terrain_materials_v2.py:289-346`
**Issue:** `derive_pass_seed` is called (line 289) and the seed is recorded in `metrics["seed_used"]`, but the `PassResult.seed_used` field (the canonical field per terrain_semantics.py:841) is left at its default of 0. This breaks any downstream consumer that reads `result.seed_used` for determinism verification.
**Fix:** Add `seed_used=seed` to the PassResult constructor at line 339.

### P1-03: `pass_cliffs` computes seed but does not set `PassResult.seed_used`

**File:** `terrain_cliffs.py:570-641`
**Issue:** Same pattern as P1-02. Seed is computed via `derive_pass_seed` and stored in metrics dict, but not in the `PassResult.seed_used` field.
**Fix:** Add `seed_used=seed` to the PassResult constructor at line 624.

### P1-04: `pass_waterfalls` computes seed but does not set `PassResult.seed_used`

**File:** `terrain_waterfalls.py:677-772`
**Issue:** Same pattern. `derived_seed` computed at line 677 is only in metrics, not in `PassResult.seed_used`.
**Fix:** Add `seed_used=int(derived_seed)` to the PassResult constructor.

### P1-05: `_terrain_noise.py` global mutable state in `_features_gen` / `_features_seed`

**File:** `terrain_features.py:33-34`
**Issue:** `_hash_noise` uses module-level globals (`_features_gen`, `_features_seed`) for caching the noise generator. This is not thread-safe and creates implicit state coupling between calls with different seeds. If two functions call `_hash_noise` with different seeds in the same process, they silently overwrite each other's generator.
**Fix:** Use a function-local LRU cache or pass the generator explicitly.

### P1-06: `detect_perched_lakes` logic inverted -- finds VALLEYS not perched lakes

**File:** `terrain_water_variants.py:374`
**Issue:** The comment says "ring_mean >= basin_z means regular valley, not perched." But a perched lake sits ABOVE its surroundings (basin_z > ring_mean), and the code skips when `ring_mean >= basin_z` (i.e., surroundings are higher or equal). This means it keeps cells where `ring_mean < basin_z` -- i.e., cells that are local MAXIMA surrounded by lower terrain. That is the opposite of a lake. The `is_min` filter at line 355 catches local minima, but then the ring check at 374 further filters to cases where the surrounding ring is even lower -- which describes a perched highland, not a lake.

Actually, re-reading: `is_min = all(interior <= neighbors)` finds cells that are local minima. Then `ring_mean < basin_z` means the surrounding ring's average height is BELOW the basin cell's height. For a cell that is a local minimum AND has a ring that averages even lower, this describes a shallow depression on an elevated plateau -- which IS a perched lake (it sits above the regional average). The logic is correct but the comment is misleading. Downgrading to P2.

### P1-07: `_erode_brush` sign convention is confusing and fragile

**File:** `_terrain_erosion.py:366-399`
**Issue:** The brush is called with negative amount (`-erode_amount`) on line 239 for the erosion_amount accumulator. The function subtracts amount from cells (line 399). So negative amount gets double-negated back to positive, which accumulates correctly. However, the docstring (lines 375-382) tries to explain this but is unclear. The sign convention relies on `hmap[ny, nx] -= amount` where amount can be positive OR negative depending on caller intent. This is error-prone: any new call site could easily get the sign wrong.
**Fix:** Split into two functions: `_erode_brush_remove(hmap, ...)` and `_erode_brush_accumulate(hmap, ...)` with clear unsigned amount parameters. Or at minimum, assert that amount is positive in the erosion path.

### P1-08: `environment.py` uses `import copy` inside function body on every call

**File:** `environment.py:391`
**Issue:** `get_vb_biome_preset` does `import copy` on every invocation inside the function body. While Python caches imports, this is unnecessary overhead for a function that may be called frequently (once per biome lookup).
**Fix:** Move `import copy` to module-level imports.

---

## Info (P2)

### P2-01: `pass_waterfalls` creates RNG but never uses it

**File:** `terrain_waterfalls.py:681`
**Issue:** `_ = np.random.default_rng(derived_seed)` creates an RNG and immediately discards it to `_`. This is dead code -- the RNG is never used in the pass function.
**Fix:** Remove the line, or use the RNG if jitter is needed downstream.

### P2-02: `detect_perched_lakes` misleading comment

**File:** `terrain_water_variants.py:331-332`
**Issue:** Docstring says "basin whose surrounding ring has a LOWER mean altitude" but the filter logic actually keeps cells where `ring_mean < basin_z`, which is: surrounding ring is lower than the basin. This is correct for detecting a perched feature (elevated depression), but the docstring describes the test as if it finds depressions below their surroundings.
**Fix:** Rewrite docstring: "A perched lake is a local height minimum (basin) that sits above its wider neighborhood -- i.e., the basin cell is higher than the surrounding ring average, indicating an elevated plateau depression."

### P2-03: `road_network.py` uses stdlib `random.Random` instead of numpy RNG

**File:** `road_network.py:167`
**Issue:** `_generate_switchback_points` uses `random.Random(seed)` for determinism, while the rest of the terrain pipeline uses `np.random.default_rng(seed)`. This inconsistency means the same seed produces different sequences depending on Python version.
**Fix:** Use `np.random.default_rng(seed)` for consistency with the pipeline's determinism contract.

### P2-04: `terrain_features.py` uses global mutable cache for noise generator

**File:** `terrain_features.py:33-34`
**Issue:** Module globals `_features_gen` and `_features_seed` cache the noise generator. Same concern as P1-05 but in the features module. Not thread-safe, creates implicit coupling.
**Fix:** Same as P1-05.

### P2-05: `_export_heightmap` in `terrain_unity_export.py` uses different quantization from `_quantize_heightmap`

**File:** `terrain_unity_export.py:58-71`
**Issue:** Two heightmap quantization functions exist:
- `_quantize_heightmap` (line 47): uses `stack.height_min_m` / `height_max_m` if available, adds 0.5 rounding
- `_export_heightmap` (line 58): uses local min/max, no rounding
Different quantization for the same data could cause subtle precision mismatches between the pass-based and export-based paths.
**Fix:** Consolidate into a single quantization function used by both paths.

### P2-06: `_audio_zones_json` computes `world_tile_extent` but never uses it correctly

**File:** `terrain_unity_export.py:299`
**Issue:** `world_tile_extent = stack.tile_size * stack.cell_size` is computed, then used as the Z max bound in `"max": [max_x, max_y, float(world_tile_extent)]`. This means the audio zone's vertical extent equals the tile's horizontal extent, which is almost certainly wrong for audio volumes. The Z max should be related to the height range, not the tile footprint.
**Fix:** Use `float(stack.height_max_m or stack.height.max())` for the Z max bound.

### P2-07: `generate_waterfall` in `terrain_features.py` does not use `facing_direction` parameter validation

**File:** `terrain_features.py:436-440`
**Issue:** A degenerate `facing_direction` (zero vector) silently falls back to identity rotation (`cos_t=1, sin_t=0`), which produces the legacy -Y orientation. This is correct defensive behavior but is undocumented -- callers passing `(0,0)` might expect an error.
**Fix:** Add a note in the docstring that zero vectors default to legacy -Y orientation.

### P2-08: `terrain_materials.py` is extremely large (700+ lines of data definitions)

**File:** `terrain_materials.py`
**Issue:** The file contains 60+ material definitions and 14 biome palettes as inline Python dicts. This makes the file ~36K tokens, hard to navigate, and any edit risks accidentally corrupting a material definition. The data should be externalized.
**Fix:** Move material/biome data to YAML or JSON sidecar files, load at module init.

---

## Security

No `eval()`, `exec()`, `__import__()`, command injection, or unsanitized input paths found in any of the 15 reviewed files. All file I/O in `terrain_unity_export.py` uses `pathlib.Path` with no user-controlled path traversal vectors.

---

## Summary

| Severity | Count |
|----------|-------|
| P0 (crash bugs) | 3 |
| P1 (logic/wiring) | 8 |
| P2 (quality/info) | 8 |
| **Total** | **19** |

**Top priority:** Fix P0-01 and P0-02 (`get_swamp_specs` will crash at runtime with `AttributeError` and `TypeError`). These are in `terrain_water_variants.py` lines 734 and 736.

**Second priority:** Decide on the 8 missing files (P1-01). If they are planned but not yet created, they should be removed from any import paths. If they were merged elsewhere, update the plan references.

**Third priority:** Fix the `seed_used` field omissions (P1-02 through P1-04) across three pass functions to maintain determinism contract compliance.

---

_Reviewed: 2026-04-12T02:00:00Z_
_Reviewer: Claude Opus 4.6 (gsd-code-reviewer)_
_Depth: deep_
