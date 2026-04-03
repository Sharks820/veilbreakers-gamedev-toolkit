# Deep Bug Scan: Materials, Textures, VFX, LOD/Mesh Pipeline

**Date:** 2026-04-02
**Scope:** terrain_materials.py, texture_quality.py, lod_pipeline.py, mesh.py, vegetation_lsystem.py, vegetation_system.py, _scatter_engine.py
**Method:** Full line-by-line read of all 7 files, cross-reference validation of material keys, PBR value audit, geometry edge-case analysis

---

## CRITICAL BUGS (Will cause crashes or visibly broken output)

### BUG-01: Billboard quad uses wrong axes -- faces +Z instead of camera
**File:** `lod_pipeline.py`, `_generate_billboard_quad()`, lines 588-624
**Severity:** CRITICAL
**Description:** The billboard quad is generated in the XY plane (all Z values are `cz`). The docstring says "The quad faces +Z" which means the quad's normal points along +Z (up). For a vegetation billboard that should be visible from the side (camera looking horizontally), this is **completely wrong** -- the billboard would be invisible from any horizontal viewing angle because it faces straight up. Billboard LODs for trees should face the camera (vertical quads), not lie flat.

The quad vertices are:
```python
(cx - half_w, cy - half_h, cz)  # all at same Z
(cx + half_w, cy - half_h, cz)
(cx + half_w, cy + half_h, cz)
(cx - half_w, cy + half_h, cz)
```

Additionally, `half_w` uses X extent and `half_h` uses Y extent. For a tree, the relevant dimensions should be **width (X or Y) and height (Z)**. The Z extent is completely ignored for sizing.

**Fix:** Billboard should be a vertical quad (varying X and Z, constant Y) sized to the XZ bounding box, or better yet, use the cross-billboard approach from `vegetation_lsystem.py` line 1007 which does this correctly.

### BUG-02: Seasonal color_tint values can push colors below 0
**File:** `vegetation_system.py`, `_SEASONAL_VARIANTS`, lines 220-249 and `get_seasonal_variant()` line 560+
**Severity:** CRITICAL
**Description:** The color_tint values include negative components:
- autumn: `(0.3, 0.15, -0.1)` -- blue channel goes negative
- winter: `(0.1, 0.1, 0.15)` -- OK
- corrupted: `(0.15, -0.1, 0.2)` -- green channel goes negative
- corrupted mushroom override: `(0.2, -0.15, 0.3)` -- green channel goes negative

These tints are **additive** to the base color. When a base color has a low green channel (e.g., 0.04) and the tint is -0.15, the result is -0.11 which is out of range. The `get_seasonal_variant()` function returns these raw tint values without clamping, and there is no downstream clamping visible.

**Fix:** Either clamp the tint result to [0,1] in `get_seasonal_variant()`, or document that consumers must clamp. The current code returns the raw negative tints.

### BUG-03: LOD billboard in vegetation preset uses ratio 0.0 but min_tris says 4
**File:** `lod_pipeline.py`, `LOD_PRESETS["vegetation"]`, line 58-60
**Severity:** HIGH
**Description:** The vegetation preset has `"ratios": [1.0, 0.5, 0.15, 0.0]` where 0.0 triggers billboard generation. But `generate_lod_chain()` at line 752 checks `if ratio <= 0.0` to call `_generate_billboard_quad()`. The billboard function (BUG-01) produces a broken flat quad. Combined with BUG-01, all vegetation LOD3 is a face-up invisible quad.

---

## HIGH SEVERITY BUGS

### BUG-04: Leaf card tilt modifies up vector non-orthogonally
**File:** `vegetation_lsystem.py`, `generate_leaf_cards()`, lines 851-853
**Severity:** HIGH
**Description:** The tilt application modifies `final_ux` and `final_uz` by adding direction components:
```python
final_ux += dz * tilt
final_uz -= dx * tilt
```
This does NOT preserve orthogonality between the right and up vectors. After tilt, `final_u` is no longer perpendicular to `final_r`, causing parallelogram-shaped (skewed) leaf cards instead of rectangles. The skew is proportional to `tilt * direction`, and with `tilt` up to 0.3, visible distortion occurs.

**Fix:** Apply tilt as a proper rotation around the right vector, or use Rodrigues' formula.

### BUG-05: Chitin metallic = 0.12 is physically incorrect
**File:** `texture_quality.py`, `SMART_MATERIAL_PRESETS["chitin"]`, line 498
**Severity:** HIGH (visual quality)
**Description:** Chitin (insect exoskeleton) is a dielectric/organic material. PBR convention: metallic should be either 0.0 (dielectric) or 1.0 (metal), with values in between only for transition zones (rust/paint chipping). Chitin at 0.12 will cause incorrect energy conservation -- Fresnel will look wrong, the material will have an uncanny metal-like sheen.

Similarly:
- `obsidian` metallic=0.05 (line 209) -- obsidian is a glass, metallic should be 0.0
- `ice` metallic=0.02 (line 566) -- ice is dielectric, metallic should be 0.0
- `crystal` metallic=0.05 (line 587) -- crystals are dielectric, metallic should be 0.0

**Fix:** Set metallic to 0.0 for all non-metal materials. Use roughness and IOR/specular tint to achieve the desired reflectivity instead.

### BUG-06: Terrain material crystal_surface and prismatic_rock have high metallic for non-metals
**File:** `terrain_materials.py`, lines 384-393 and 788-797
**Severity:** HIGH (visual quality)
**Description:**
- `crystal_surface`: metallic=0.12 -- crystals are dielectric
- `prismatic_rock`: metallic=0.20 -- rock is dielectric
- `crystal_wall`: metallic=0.30 -- crystal is dielectric

These are the same PBR-incorrectness issue as BUG-05 but in terrain materials. Crystal and rock are never metallic in reality. The shiny appearance should come from low roughness, not metallic.

**Fix:** Set metallic to 0.0, adjust roughness and IOR instead.

### BUG-07: Poisson disk + vegetation placement can place at terrain boundary with no height data
**File:** `vegetation_system.py`, `compute_vegetation_placement()`, line 380-382
**Severity:** HIGH
**Description:** When `_sample_terrain()` finds no nearby vertex (best_idx stays -1), it returns `(0.5, 0.0)` as defaults. The vegetation is then placed at `min_h + 0.5 * height_range` which may be completely wrong (mid-height in the air). This happens at terrain edges/corners where the grid lookup has no vertices in the 3x3 neighborhood.

The point is still placed with incorrect Z position, creating floating vegetation.

**Fix:** Skip placement when no terrain vertex is found (return a sentinel that triggers `continue` in the caller).

---

## MEDIUM SEVERITY BUGS

### BUG-08: `rusted_armor` metallic=0.95 should be 1.0 for base metal
**File:** `texture_quality.py`, `SMART_MATERIAL_PRESETS["rusted_armor"]`, line 321
**Severity:** MEDIUM
**Description:** The base metal of armor is steel, which should have metallic=1.0. The rust patches are what have lower metallic (they're iron oxide, a dielectric). The preset has the base at 0.95 which is slightly incorrect -- the rust_color/rust_spread mechanism should handle the metallic transition, not the base value.

Similarly: `aged_bronze` metallic=0.90 and `tarnished_gold` metallic=0.95 -- polished metals should be 1.0 with patina/tarnish being the varying area.

Also: `rusted_iron` metallic=0.85 (line 408) -- same issue, base iron is metallic=1.0.

**Fix:** Set base metallic to 1.0 for all metal presets. The edge-wear and cavity systems already handle the non-metal transitions.

### BUG-09: `_generate_billboard_quad` returns XY extent, ignoring Z height
**File:** `lod_pipeline.py`, lines 610-611
**Severity:** MEDIUM (related to BUG-01)
**Description:** `half_w = (max(xs) - min(xs)) / 2.0` and `half_h = (max(ys) - min(ys)) / 2.0`. For a tree that is tall in Z and narrow in X/Y, this produces a tiny, squat billboard that doesn't represent the tree's silhouette at all.

### BUG-10: `_auto_detect_regions` uses Y for height but Blender convention is Z-up
**File:** `lod_pipeline.py`, `_auto_detect_regions()`, lines 632-696
**Severity:** MEDIUM
**Description:** The function uses Y axis for height (e.g., "face" is top 13% of Y range, "hands" checks Y percentages). Blender's convention is Z-up, so a character modeled in Blender has height along Z, not Y. This means:
- "face" detection selects vertices at max-Y (back of the model?) instead of max-Z (top of head)
- "hands" detection looks at Y 35-50% which is the middle depth, not arm height

However, Unity uses Y-up, so if models are pre-rotated for Unity export, this might be intentional. The code doesn't document which coordinate convention it expects.

**Fix:** Either document the expected orientation clearly, or add a `coordinate_system` parameter with Z-up default matching Blender.

### BUG-11: Duplicate material key `sandstone` in TERRAIN_MATERIALS
**File:** `terrain_materials.py`, lines 550-558
**Severity:** MEDIUM
**Description:** The key `"sandstone"` appears at line 550 in TERRAIN_MATERIALS and is also defined as a smart material preset in `texture_quality.py` (`SMART_MATERIAL_PRESETS["sandstone"]`). While they're in different dicts, this can cause confusion about which material definition is used when the key is referenced.

Additionally, both the desert biome palette (line 928) and the mountain_pass biome could reference this key, and `_get_material_def()` prioritizes TERRAIN_MATERIALS over MATERIAL_LIBRARY, so the correct one is used. But the dual definition is a maintenance hazard.

### BUG-12: Vegetation placement rotation is in degrees but Blender expects radians
**File:** `vegetation_system.py`, `compute_vegetation_placement()`, line 459 and `handle_scatter_biome_vegetation()`, line 750
**Severity:** MEDIUM
**Description:** `compute_vegetation_placement()` generates `rotation` in degrees (line 459: `rotation = rng.uniform(0.0, 360.0)`). The handler at line 750 correctly converts: `instance.rotation_euler = (0, 0, math.radians(p["rotation"]))`. This is correct but fragile -- the returned dict value is in degrees but looks like it could be radians. Any other consumer of `compute_vegetation_placement()` that doesn't convert will get wrong rotations.

**Fix:** Add a note to the return dict or return radians directly.

### BUG-13: Edge-collapse decimation can produce degenerate mesh at very low ratios
**File:** `lod_pipeline.py`, `decimate_preserving_silhouette()`, line 303
**Severity:** MEDIUM
**Description:** `target_verts = max(4, int(math.ceil(num_verts * target_ratio)))`. The minimum is 4 vertices, which can form a tetrahedron. But the edge collapse is greedy and doesn't verify topological validity after each collapse. When the mesh is near the minimum, collapses can produce:
- Faces where all 3+ unique vertices are collinear (zero-area faces)
- Non-manifold configurations
- The degenerate face removal at line 384-392 catches faces with < 3 unique vertices but not zero-area faces.

### BUG-14: `normal_strength` value of 2.0 is unusually high
**File:** `terrain_materials.py`, `TERRAIN_MATERIALS["reality_torn_rock"]`, line 399
**Severity:** LOW-MEDIUM
**Description:** Normal strength of 2.0 is double the typical maximum of 1.0. While Blender allows values > 1.0, this will cause extreme surface distortion that looks like geometry errors rather than surface detail. Most other materials in the file cap at 1.6-1.8.

---

## LOW SEVERITY BUGS / CODE QUALITY

### BUG-15: Poisson disk sample can theoretically infinite-loop on degenerate input
**File:** `_scatter_engine.py`, `poisson_disk_sample()`, line 51-120
**Severity:** LOW
**Description:** If `min_distance` is 0 or negative, `cell_size = min_distance / sqrt(2)` could be 0 or negative, causing division by zero in grid index calculations. The caller should validate but currently doesn't always.

### BUG-16: `_simple_noise_2d` hash can produce slightly biased values
**File:** `terrain_materials.py`, lines 1295-1327
**Severity:** LOW
**Description:** The hash `h % 10000 / 5000.0 - 1.0` will never produce exactly -1.0 or 1.0 due to modular arithmetic (range is [-1.0, 0.9998]). This is fine for visual noise but technically biased.

### BUG-17: Missing UVs in billboard quad from LOD pipeline
**File:** `lod_pipeline.py`, `_generate_billboard_quad()`, lines 588-624
**Severity:** LOW
**Description:** The billboard quad generator returns only vertices and faces but no UVs. The vegetation_lsystem.py billboard generator (line 974+) correctly generates UVs. Without UVs, the billboard texture cannot be mapped.

### BUG-18: Hardcoded magic numbers throughout
**File:** Multiple
**Severity:** LOW
**Description:** Notable hardcoded values that should be parameters or named constants:
- `lod_pipeline.py:303` -- `max(4, ...)` minimum vertex count
- `vegetation_system.py:519` -- `0.1` threshold for trunk detection
- `vegetation_system.py:402` -- `poisson_disk_sample(width, depth, min_distance, seed=seed)` passes width/depth without offset, assumes 0-based coordinates
- `_scatter_engine.py:363` -- `affinity_radius = 15.0`
- `terrain_materials.py:1056` -- `water_level + 0.5` constant offset for water edge detection

### BUG-19: `context_scatter` building footprint is not terrain-aligned
**File:** `_scatter_engine.py`, `context_scatter()`, lines 338-350
**Severity:** LOW
**Description:** Building footprint exclusion uses axis-aligned rectangles (bx +/- half_w, by +/- half_d) but buildings could be rotated. Props may be placed inside rotated buildings.

### BUG-20: Vegetation `compute_wind_vertex_colors` has different channel mapping than `bake_wind_vertex_colors`
**File:** `vegetation_system.py` lines 476-557 vs `vegetation_lsystem.py` lines 888-967
**Severity:** MEDIUM
**Description:** Two different wind color baking functions exist with **different channel semantics**:

vegetation_system.py `compute_wind_vertex_colors()`:
- R = distance from trunk center (sway amount)
- G = height from ground (sway amplitude)  
- B = branch level estimation

vegetation_lsystem.py `bake_wind_vertex_colors()`:
- R = primary sway (radial + height blend)
- G = secondary sway (branch depth)
- B = phase offset (hash-based)

Unity shaders reading these vertex colors will get **completely different behavior** depending on which function generated them. The B channel is particularly divergent: one is smooth (branch level), the other is high-frequency noise (phase hash).

---

## PBR VALUE AUDIT SUMMARY

### Smart Material Presets (texture_quality.py) -- 22 presets

| Preset | Metallic | Issue |
|--------|----------|-------|
| dungeon_stone | 0.0 | OK |
| castle_stone | 0.0 | OK |
| brick | 0.0 | OK |
| rough_plaster | 0.0 | OK |
| sandstone | 0.0 | OK |
| marble | 0.0 | OK |
| obsidian | 0.05 | **WRONG** -- glass, should be 0.0 |
| old_wood | 0.0 | OK |
| dark_wood | 0.0 | OK |
| polished_wood | 0.0 | OK |
| rusted_armor | 0.95 | **Should be 1.0** (base is steel) |
| polished_steel | 1.0 | OK |
| tarnished_gold | 0.95 | **Should be 1.0** (base is gold) |
| aged_bronze | 0.90 | **Should be 1.0** (base is bronze) |
| rusted_iron | 0.85 | **Should be 1.0** (base is iron) |
| worn_leather | 0.0 | OK |
| dark_fabric | 0.0 | OK |
| bone | 0.0 | OK |
| chitin | 0.12 | **WRONG** -- organic, should be 0.0 |
| bark | 0.0 | OK |
| moss | 0.0 | OK |
| ice | 0.02 | **WRONG** -- dielectric, should be 0.0 |
| crystal | 0.05 | **WRONG** -- dielectric, should be 0.0 |

### Color Value Audit
All base_color values in TERRAIN_MATERIALS and SMART_MATERIAL_PRESETS are in valid 0-1 range. No 0-255 range values found.

### Roughness Value Audit
All roughness values are in valid 0-1 range across all files. No out-of-range values found.

---

## MATERIAL KEY CROSS-REFERENCE AUDIT

### BIOME_PALETTES keys vs TERRAIN_MATERIALS + MATERIAL_LIBRARY

Every material key used in BIOME_PALETTES was verified against both TERRAIN_MATERIALS and MATERIAL_LIBRARY:

| Palette Key | Found In | Status |
|-------------|----------|--------|
| `mud` (thornwood_forest water_edges) | MATERIAL_LIBRARY | OK (falls through from `_get_material_def`) |
| `moss` (ruined_fortress slopes) | MATERIAL_LIBRARY | OK (falls through from `_get_material_def`) |
| All other keys | TERRAIN_MATERIALS | OK |

NOTE: The previous bug scan flagged `"moss"` as needing to be `"mossy_rock"` but actually `"moss"` exists as a valid key in MATERIAL_LIBRARY (procedural_materials.py line 481). Both are valid but semantically different materials -- `"moss"` is the organic moss material, `"mossy_rock"` is a stone with moss overlay. For terrain slopes in a ruined fortress, `"mossy_rock"` would be more appropriate but `"moss"` technically resolves.

---

## GEOMETRY EDGE CASE ANALYSIS

### Division by zero protected:
- `_scatter_engine.py:52-55` -- `cell_size` protected by `max(1, ...)` on grid dimensions
- `lod_pipeline.py:105-108` -- `_normalize()` checks `length < 1e-12`
- `vegetation_system.py:342-346` -- `height_range` defaults to 1.0 if flat
- `terrain_materials.py:1032` -- slope computation checks `length < 1e-9`

### Division by zero NOT protected:
- None found in critical paths (good)

### Array index safety:
- `lod_pipeline.py:383-392` -- remapped face filtering catches KeyError
- `vegetation_system.py:374-380` -- grid lookup uses `.get()` with empty list default
- `mesh.py:1110` -- face normal fallback: `normals[fi] if fi < len(normals) else (0.0, 0.0, 1.0)`

---

## SUMMARY

| Severity | Count | Key Items |
|----------|-------|-----------|
| CRITICAL | 3 | Billboard faces wrong direction, seasonal color underflow, vegetation LOD3 invisible |
| HIGH | 4 | Leaf card skew, PBR metallic on dielectrics, floating vegetation at edges |
| MEDIUM | 7 | Metal metallic not 1.0, coordinate convention mismatch, wind color channel mismatch |
| LOW | 6 | Magic numbers, missing UVs, noise bias, footprint rotation |
| **TOTAL** | **20** | |

### Recommended Fix Priority:
1. **BUG-01 + BUG-03** (billboard orientation) -- breaks all vegetation LOD3
2. **BUG-02** (color underflow) -- produces clamped/black seasonal variants
3. **BUG-05 + BUG-06** (dielectric metallic) -- pervasive PBR incorrectness
4. **BUG-07** (floating vegetation) -- visible at terrain edges
5. **BUG-20** (wind color channel mismatch) -- Unity shader will behave differently per tree source
6. **BUG-04** (leaf card skew) -- subtly visible distortion
7. **BUG-08** (metal metallic) -- minor visual improvement
8. **BUG-10** (coordinate convention) -- only matters for character LOD
