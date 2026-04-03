# Math & Numeric Precision Bug Scan

**Date:** 2026-04-02
**Scope:** All .py files in Tools/mcp-toolkit (excluding .venv, tests)
**Focus:** Trigonometry, vector/matrix math, interpolation, heightmap math, geometry generation

---

## NEW BUGS FOUND

### BUG M-01: Breakable fragment/debris rotation silently discarded (MEDIUM)
**File:** `blender_addon/handlers/environment_scatter.py` lines 1622-1656
**What:** `_scatter_engine.py` generates `"rotation": rng.uniform(0, 360)` for each fragment and debris piece, but the breakable handler in `environment_scatter.py` never applies it. Fragment objects are created at `frag["position"]` but `frag["rotation"]` is ignored -- all fragments spawn axis-aligned.
```python
# Line 1634-1636: rotation never applied
frag_obj = bpy.data.objects.new(f"{prop_type}_frag_{i}", frag_mesh)
frag_obj.location = tuple(frag["position"])
frag_obj.parent = parent
# Missing: frag_obj.rotation_euler = (0, 0, math.radians(frag["rotation"]))
```
Same bug for debris at lines 1653-1656.
**Impact:** Destroyed breakable props look unnaturally grid-aligned instead of scattered chaotically.

---

### BUG M-02: `_terrain_depth.py` recomputes full heightmap gradient for EVERY cliff cluster (HIGH perf, LOW correctness)
**File:** `blender_addon/handlers/_terrain_depth.py` line 606
**What:** Inside a loop over cliff clusters, `np.gradient(heightmap)` is called on every iteration. This recomputes the full 2D gradient for the entire heightmap each time, instead of computing it once outside the loop.
```python
# Line 606 -- called inside a per-cluster loop
dy, dx = np.gradient(heightmap)
grad_x = float(dx[ri, ci])
grad_y = float(dy[ri, ci])
```
**Impact:** O(N * W * H) instead of O(W * H + N). For a 257x257 heightmap with 50 cliff clusters, this is ~50x slower than necessary. Not a correctness bug but wastes significant CPU for large terrains.

---

### BUG M-03: `compute_slope_map` ignores cell spacing in gradient (MEDIUM)
**File:** `blender_addon/handlers/_terrain_noise.py` lines 564-568
**What:** `np.gradient(heightmap)` is called without a `spacing` parameter. `np.gradient` defaults to spacing=1, meaning it computes the gradient in array-index space, not in world-unit space. If the heightmap has non-unit cell sizes (e.g., a 257x257 grid covering 100m), the slope calculation is wrong because the gradient magnitude is in "cells" not "meters."
```python
dy, dx = np.gradient(heightmap)
magnitude = np.sqrt(dx ** 2 + dy ** 2)
slope_rad = np.arctan(magnitude)  # arctan(dz/1) not arctan(dz/cell_size)
```
The function's docstring says it's marked as already-known (slope ignoring cell size). However, note that `_terrain_depth.py` line 606 has the SAME issue and is NOT in the known-bugs list. The `face_angle` computed from the un-spaced gradient in `_terrain_depth.py` will point cliff faces in wrong directions when terrain cells are not 1-unit wide.

**Note:** The known bug list mentions "slope angles wrong (ignores cell size)" for `_terrain_noise.py`. BUG M-03 is specifically about the SEPARATE occurrence in `_terrain_depth.py` at line 606 which has the same issue but manifests as wrong cliff face rotation angles, not just wrong slope degrees.

---

### BUG M-04: `environment_scatter.py` terrain slope from heightmap uses single-sided finite differences (LOW)
**File:** `blender_addon/handlers/environment_scatter.py` lines 1398-1401
**What:** The slope computation for aligning vegetation to terrain uses `h10 - h00` and `h01 - h00` (forward differences from a single corner). This is a first-order approximation that systematically biases the gradient toward the bottom-left corner of the bilinear cell. Central differences `(h10 - h_m10) / 2` would be more accurate.
```python
dzdx = (h10 - h00) * height_max / max(cell_size, 0.01)
dzdy = (h01 - h00) * height_max / max(cell_size, 0.01)
```
**Impact:** Vegetation on terrain slopes tilts slightly wrong, especially at coarse heightmap resolutions. The 70% alignment factor (line 1404) masks this somewhat.

---

### BUG M-05: `animation_export.py` extracts quaternion Z component as root rotation angle (HIGH)
**File:** `blender_addon/handlers/animation_export.py` line 786
**What:** For QUATERNION rotation mode, the code extracts the `.z` component of the quaternion to use as a root rotation value:
```python
if rot_mode in ("QUATERNION",):
    rot_z = hip_pbone.matrix.to_quaternion().z
```
A quaternion's `.z` component is NOT the yaw/heading angle. For a rotation purely around Z axis by angle `a`, the quaternion is `(cos(a/2), 0, 0, sin(a/2))` -- so `.z` gives `sin(a/2)`, not `a`. This should be `.to_euler().z` to get the actual Z rotation angle, or decompose properly.
**Impact:** Root motion rotation extraction is wrong for quaternion-mode armatures. The keyframed root rotation will be `sin(angle/2)` instead of `angle`, producing severely wrong turning animations.
**Note:** The known bugs mention "root motion world vs local space" -- this is a DIFFERENT bug (extracting a quaternion component instead of an angle).

---

### BUG M-06: `vertex_colors.py` and `texture_quality.py` curvature sign determination methods disagree (LOW)
**File:** `blender_addon/handlers/vertex_colors.py` lines 191-207 vs `texture_quality.py` lines 2153-2158
**What:** Both files compute per-vertex curvature from dihedral angles, but use different methods to determine convex vs concave:
- `vertex_colors.py` (line 194-206): Uses face-center-to-face-center vector projected onto face A's normal to determine sign.
- `texture_quality.py` (line 2157-2158): Uses `cross(n0, n1)` dotted with edge vector to determine sign.

These are different geometric tests and can disagree for non-trivial topologies, especially near mesh boundaries or for non-planar quads.
**Impact:** The same mesh vertex can be classified as convex by one system and concave by the other, leading to inconsistent vertex color baking vs texture quality curvature maps.

---

### BUG M-07: `lod_pipeline.py` `_normalize` returns zero vector for degenerate input (LOW)
**File:** `blender_addon/handlers/lod_pipeline.py` lines 103-108
**What:** When normalizing a near-zero vector, `_normalize` returns `(0, 0, 0)`:
```python
def _normalize(v):
    length = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
```
Other implementations in the codebase (e.g., `character_advanced.py` line 752, `autonomous_loop.py` line 106, `geometry_nodes.py` line 208) return `(0, 0, 1)` as a safe fallback. A zero-length normal can cause division-by-zero or NaN downstream when used in dot products for silhouette importance.

The `_face_normal` function in `lod_pipeline.py` (line 116-123) correctly delegates to `_normalize`, which returns the zero vector for degenerate faces. Then `compute_silhouette_importance` (line 190) calls `_dot(fn, view_dir)` on these zero normals, which will always return 0.0, making degenerate-face edges appear as silhouette edges regardless of view direction.
**Impact:** Degenerate faces incorrectly inflate LOD importance scores.

---

### BUG M-08: `character_advanced.py` binormal computed from wrong cross product (MEDIUM)
**File:** `blender_addon/handlers/character_advanced.py` line 1372
**What:** The tangent frame construction for hair strands computes:
```python
tangent = _vec_normalize(_vec_cross(normal, up))
binormal = _vec_normalize(_vec_cross(normal, tangent))
```
The binormal should be `cross(tangent, normal)` or equivalently `cross(normal, tangent)` gives the opposite direction. Mathematically, for a right-handed frame (tangent, binormal, normal), the correct relationship is `binormal = cross(normal, tangent)` -- but this gives a LEFT-handed frame since typically `binormal = cross(tangent, normal)` for right-handed.

The sign of the binormal is inverted compared to standard TBN convention (tangent x normal, not normal x tangent). For the hair strand use case, this means the `lateral_offset_b` (used for curly/braided styles) is applied in the opposite direction from intended.
**Impact:** Curly and braided hair strand geometry spirals in the wrong lateral direction. Wavy and straight styles are unaffected (they only use tangent-direction offset).

---

### BUG M-09: `_terrain_noise.py` slope map uses `arctan(magnitude)` instead of `arctan2(magnitude, cell_spacing)` (MEDIUM)
**File:** `blender_addon/handlers/_terrain_noise.py` line 566
**What:** The slope calculation computes:
```python
magnitude = np.sqrt(dx ** 2 + dy ** 2)
slope_rad = np.arctan(magnitude)
```
`arctan(magnitude)` computes `arctan(dz/1)` (since gradient spacing is 1). This conflates the gradient magnitude with the slope tangent. For the arctan to give a meaningful angle, the argument must be `rise/run` -- but the "run" is 1 in array space, not in world space. This is related to M-03 but note: even if cell_size were correctly passed to `np.gradient`, the `arctan(magnitude)` call would still be mathematically incorrect because `magnitude = sqrt(dx^2 + dy^2)` gives the gradient MAGNITUDE (a 2D length), which should then be `arctan(magnitude)` -- this part IS correct as `arctan(sqrt(dz_dx^2 + dz_dy^2))` correctly gives the slope angle from horizontal. The bug is solely the missing spacing, not the arctan formula.

**Correction to initial analysis:** The `arctan(magnitude)` formula IS correct given proper spacing. The only bug is the missing spacing parameter to `np.gradient`, which is already known. Retracting M-09 as a separate bug.

---

### BUG M-10: `prop_density.py` wall prop rotation in degrees passed to consumer expecting radians (HIGH)
**File:** `blender_addon/handlers/prop_density.py` line 548-553
**What:** The `compute_room_zone_placements` function computes wall-facing rotation in degrees:
```python
face_angle = math.degrees(math.atan2(normal[1], normal[0]))
results.append({
    ...
    "rotation": face_angle + rng.uniform(-10, 10),
    ...
})
```
And the ceiling/floor zone also outputs degrees (line 506): `"rotation": rng.uniform(0, 360)`.

This function returns pure data dicts. The consumer (`worldbuilding.py` line 5839) directly assigns to `rotation_euler`:
```python
item_obj.rotation_euler = (0, 0, item["rotation"])
```
Blender's `rotation_euler` expects RADIANS. So a `face_angle` of 90 degrees gets passed as 90.0 radians (which is 14.3 full rotations).

For the items that come from `_building_grammar.py`, the rotations are already in radians (using `math.pi * 2`). But items from `prop_density.py` are in degrees. If `worldbuilding.py` ever consumes `prop_density.py` output directly (for room zone placements), the rotation will be in the wrong unit.

**Impact:** If prop_density results are consumed by a Blender handler that sets `rotation_euler` directly, all wall/floor/ceiling props will have wildly wrong orientations. Need to verify whether `prop_density.py` results actually flow into a rotation_euler assignment. Based on code search, `prop_density.py` is currently only imported by tests and `settlement_generator.py` -- but `settlement_generator.py` could feed these into worldbuilding code.

**Confidence:** MEDIUM -- the bug is real if the data flows to Blender code, but the connection needs verification.

---

### BUG M-11: `_building_grammar.py` mixed rotation conventions (MEDIUM)
**File:** `blender_addon/handlers/_building_grammar.py`
**What:** Within the same module, different functions output rotation in different formats:
- Line 2750: `"rotation": round(rotation, 4)` -- scalar float (radians, set by caller)
- Line 3447: `"rotation": (0.0, 0.0, round(rng.uniform(0, 2 * math.pi), 4))` -- 3-tuple (radians)
- Line 4288: `"rotation": round(rng.uniform(0, math.pi * 2), 4)` -- scalar float (radians)

The consumer in `worldbuilding.py` line 5839 does:
```python
item_obj.rotation_euler = (0, 0, item["rotation"])
```
This works when `item["rotation"]` is a scalar (becomes Z rotation), but FAILS when it's a 3-tuple because `(0, 0, (0.0, 0.0, 1.5))` is not a valid Euler tuple -- it would try to assign a tuple as the Z component, causing a TypeError at runtime.

Lines 3447 and 3481 return `"rotation"` as a `(0.0, 0.0, angle)` tuple, but the consumer expects a scalar.
**Impact:** Runtime TypeError when placing clutter items from `generate_clutter_layout` that use the 3-tuple rotation format.

---

### BUG M-12: `animation_production.py` `lerp_pose` quaternion nlerp without proper shortest-path for near-opposite quaternions (LOW)
**File:** `blender_addon/handlers/animation_production.py` lines 741-751
**What:** The nlerp implementation checks `dot < 0` to flip the quaternion for shortest path, which is correct. However, when `dot` is very close to -1 (quaternions nearly opposite), the linear interpolation produces a near-zero quaternion that, after normalization, can snap to an arbitrary orientation. True slerp handles this gracefully; nlerp does not.
```python
dot = sum(rot_a[i] * rot_b[i] for i in range(4))
sign = 1.0 if dot >= 0 else -1.0
interp = [rot_a[i] + (sign * rot_b[i] - rot_a[i]) * factor for i in range(4)]
length = math.sqrt(sum(v * v for v in interp))
if length > 1e-8:
    interp = [v / length for v in interp]
```
When `dot` is approximately -1 and `factor` is approximately 0.5, all four components approach zero, and the normalization amplifies floating-point noise.
**Impact:** Very rare orientation "pops" when blending between nearly opposite quaternion poses (e.g., 180-degree rotations). The `1e-8` guard catches the degenerate case but doesn't provide a meaningful fallback.

---

### BUG M-13: `_terrain_depth.py` cliff face_angle uses gradient of HEIGHT but applies it as a Z-rotation (MEDIUM)
**File:** `blender_addon/handlers/_terrain_depth.py` lines 606-622
**What:** After computing the gradient direction:
```python
face_angle = math.atan2(grad_y, grad_x)
...
placements.append({
    "position": [wx, wy, wz],
    "rotation": [0.0, 0.0, face_angle],
    ...
})
```
The `face_angle` is the direction of steepest ascent in the XY plane, and it's applied as a Z-rotation to orient the cliff mesh. However:
1. The gradient is in array-index space (row, col), not world space. Array rows map to Y, columns to X, but the mapping at lines 597-598 shows `wx` comes from `c_center/cols` (column) and `wy` from `r_center/rows` (row). So `grad_x` (column gradient) maps to world X, and `grad_y` (row gradient) maps to world Y. The `atan2(grad_y, grad_x)` correctly gives the world-space angle.
2. BUT: the cliff should face PERPENDICULAR to the slope direction (the cliff face is the wall, not the slope direction). The rotation should be `face_angle + pi/2` or `face_angle - pi/2` to orient the cliff mesh so its flat face is perpendicular to the slope.

**Impact:** Cliff meshes are rotated 90 degrees wrong -- they face along the slope instead of perpendicular to it.

---

### BUG M-14: `worldbuilding.py` stairs rotation is 90 degrees around X (MEDIUM)
**File:** `blender_addon/handlers/worldbuilding.py` line 5324
**What:**
```python
stairs_obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
```
This hardcodes stairs to always rotate 90 degrees around X axis with no Z rotation. The `stairs_direction` parameter is passed to `generate_staircase_spec` to control the stair geometry, but the placement ignores the actual direction the staircase should face. If the staircase connects rooms at different Z levels on different sides of a building, the stairs always face the same direction.
**Impact:** Stairs between floors always face the same world direction regardless of their intended orientation.

---

## BORDERLINE / STYLE ISSUES (not counted as bugs)

### STYLE-01: Multiple inconsistent `_vec_normalize` fallback values
Different modules return different fallback vectors for zero-length inputs:
- `(0, 0, 1)` -- character_advanced.py, autonomous_loop.py, geometry_nodes.py, monster_surface_detail.py
- `(0, 1, 0)` -- monster_bodies.py (_outward_normal fallback)
- `(0, 0, 0)` -- lod_pipeline.py (BUG M-07 above)
- `(0, 0, 1)` with warning -- some places

Not a bug per se but makes behavior unpredictable for degenerate inputs.

### STYLE-02: Unclamped lerp `t` values in animation code
Multiple `_lerp` calls in `animation_abilities.py` pass `t` values that can exceed [0, 1] due to division by phase durations that may not perfectly partition the frame range. The `_lerp` function does not clamp. This is intentional for overshoot effects in some cases, but can cause unexpected values.

---

## AREAS VERIFIED CLEAN

### Trigonometry (MISSION 1)
- `math.radians()` / `math.degrees()` used correctly at all call sites checked
- `atan2(y, x)` argument order is correct everywhere checked
- `math.acos()` calls consistently clamp input to [-1, 1] (e.g., `max(-1.0, min(1.0, ...))`)
- Euler rotations assigned to `rotation_euler` consistently use radians (via `math.radians()` or raw radian values)
- `np.gradient` correctly unpacked as `dy, dx` (matching numpy convention) in all locations

### Vector/Matrix Math (MISSION 2)
- Cross product implementations in `character_advanced.py`, `autonomous_loop.py`, `geometry_nodes.py` are all algebraically correct
- Normalize functions include zero-length guards with epsilon checks (1e-6 to 1e-12 range)
- Face normal computations using both cross-product and Newell's method are correct

### Interpolation and Blending (MISSION 3)
- `lerp_pose` correctly clamps factor to [0, 1]
- Quaternion nlerp uses shortest-path check (dot product sign flip)
- Biome weight normalization in `map_composer.py` correctly handles zero-total fallback

### Heightmap Math (MISSION 4)
- Bilinear interpolation in `environment.py` lines 446-468 is correct
- Heightmap RAW export correctly normalizes to [0, 1] and converts to uint16
- Hydraulic erosion gradient computation is correct (bilinear sampling for continuous droplet positions)
- Thermal erosion correctly converts talus angle to height threshold via `tan(radians(angle))`

### Geometry Generation (MISSION 5)
- Hemisphere generation in `armor_meshes.py` correctly handles pole vertices and winding order
- Newell's method face normals are correctly implemented in multiple locations
- Face area calculations use cross-product magnitude / 2 correctly
- Random-point-in-triangle uses proper sqrt-based barycentric sampling
- Non-manifold edge detection correctly identifies edges shared by != 2 faces
- Box projection UVs correctly handle degenerate bounding boxes (zero-extent fallback)

---

## SUMMARY

| ID | Severity | File | Description |
|----|----------|------|-------------|
| M-01 | MEDIUM | environment_scatter.py | Fragment/debris rotation silently discarded |
| M-02 | LOW (perf) | _terrain_depth.py | Gradient recomputed per-cluster instead of once |
| M-03 | MEDIUM | _terrain_depth.py | Gradient lacks cell spacing (separate from known _terrain_noise.py bug) |
| M-04 | LOW | environment_scatter.py | Single-sided finite differences for slope |
| M-05 | HIGH | animation_export.py | Quaternion .z extracted as rotation angle (should be euler) |
| M-07 | LOW | lod_pipeline.py | Zero-vector fallback for degenerate normals |
| M-08 | MEDIUM | character_advanced.py | Binormal cross product order inverted |
| M-10 | HIGH | prop_density.py | Rotation in degrees, consumer expects radians |
| M-11 | MEDIUM | _building_grammar.py | Mixed scalar/tuple rotation format |
| M-12 | LOW | animation_production.py | Nlerp degenerate for near-opposite quaternions |
| M-13 | MEDIUM | _terrain_depth.py | Cliff face 90 degrees off (slope dir vs perpendicular) |
| M-14 | MEDIUM | worldbuilding.py | Stairs ignore actual connection direction |

**Total new bugs: 12** (2 HIGH, 6 MEDIUM, 4 LOW)
