# Deep Bug Scan: Procedural Asset Generators (Weapons, Armor, Creatures, Clothing, Hair, Destruction)

**Date:** 2026-04-02
**Scope:** armor_meshes.py, clothing_system.py, hair_system.py, destruction_system.py, character_advanced.py, monster_bodies.py, legendary_weapons.py, eye_mesh.py, facial_topology.py, monster_surface_detail.py, npc_characters.py, equipment_fitting.py, procedural_meshes.py (asset generator sections)
**Method:** Full line-by-line read of 13 files, cross-reference validation, geometry correctness analysis
**Scan #:** 19 (previous 18 scans found ~235 bugs across terrain/worldbuilding/settlement/materials/animation/etc.)

---

## CRITICAL BUGS (Will cause crashes or visibly broken output)

### BUG-01: O(V*F) normal computation in destruction_system -- quadratic performance
**File:** `destruction_system.py`, `_compute_vertex_normal_approx()`, lines 89-120, called at line 226
**Severity:** CRITICAL (performance -- will hang/freeze on larger meshes)
**Description:** `_compute_vertex_normal_approx(vertex_index, vertices, faces)` iterates over ALL faces for EVERY vertex to find which faces reference that vertex. `apply_destruction()` calls it inside a loop over all vertices (line 221-226). This is O(V * F) complexity.

For a 5000-vertex, 10000-face mesh (typical building), this is 50 million operations. For a 10K-vert mesh it's 200M. This will cause visible freezes or timeouts.

Every other module in the codebase (clothing_system, equipment_fitting, monster_surface_detail) computes vertex normals correctly using a single-pass accumulation approach.

**Fix:** Replace per-vertex iteration with single-pass face normal accumulation:
```python
def _compute_all_vertex_normals(vertices, faces):
    normals = [[0.0, 0.0, 0.0] for _ in range(len(vertices))]
    for face in faces:
        if len(face) >= 3:
            # compute face normal, accumulate to each vertex
            ...
    # normalize all at once
    return [normalize(n) for n in normals]
```
Then index into the precomputed array at line 226.

### BUG-02: eye_mesh.py uses Z-up coordinate system while rest of character pipeline uses Y-up
**File:** `eye_mesh.py`, `_uv_sphere()` lines 61-80, `generate_eye_mesh()`, `generate_eye_pair()`
**Severity:** CRITICAL (eyes will be rotated 90 degrees when integrated with character bodies)
**Description:** The `_uv_sphere()` function in eye_mesh.py generates spheres with Z as the vertical axis:
- Bottom pole: `(cx, cy, cz - radius)` (line 61) -- Z is min at bottom
- Top pole: `(cx, cy, cz + radius)` (line 80) -- Z is max at top
- Ring height: `z = cz - radius * math.cos(phi)` (line 67) -- Z varies with latitude

Compare with every other sphere generator in the codebase (armor_meshes, procedural_meshes, legendary_weapons, monster_bodies, npc_characters):
- Bottom pole: `(cx, cy - radius, cz)` -- Y is min at bottom
- Top pole: `(cx, cy + radius, cz)` -- Y is max at top

The `forward_axis` parameter in `_compute_iris_uvs()` defaults to `1` (Y) with `forward_sign=-1`, and `generate_eye_mesh()` passes `forward_axis=1` (line in generate_eye_mesh). This means the iris UV mapping expects Y-forward, but the sphere geometry has Y as a lateral axis and Z as up. The iris will be mapped to the wrong hemisphere.

Additionally, `generate_eye_pair()` positions eyes using `head_center` with Z as height (`default=(0, 0, 1.64)`) which matches Z-up, but `npc_characters.py` uses Z-up for bodies too. So internally the eye system is self-consistent (Z-up) but **armor_meshes.py, clothing_system.py, and hair_system.py all use Y-up**. When eyes are combined with helmets, hair, or facial armor from those systems, they will be in mismatched coordinate spaces.

**Fix:** Either convert eye_mesh.py to Y-up to match armor/clothing/hair, or add a coordinate transform in the integration layer. The npc_characters/monster_bodies already use Z-up so the character pipeline has a split convention -- this needs a project-wide decision.

### BUG-03: Flipped normals on coordinate-swapped cylinders in armor_meshes.py
**File:** `armor_meshes.py`, lines 1913, 1918, 1996, 2025
**Severity:** HIGH (backfaces visible in-game, geometry appears inside-out)
**Description:** Four locations swap X and Z coordinates to rotate cylinders to horizontal orientation:
```python
frv = [(v[2], v[1], v[0]) for v in frv]  # line 1913 (backpack frame)
brv = [(v[2], v[1], v[0]) for v in brv]  # line 1918 (backpack bedroll)
cbv = [(v[2], v[1], v[0]) for v in cbv]  # line 1996 (trophy mount crossbar)
rv = [(v[2], v[1], v[0]) for v in rv]    # line 2025 (bedroll)
```

Swapping X and Z coordinates is equivalent to a reflection (determinant = -1), not a rotation. This flips the winding order of all faces, causing all face normals to point inward instead of outward. The face indices are NOT updated to reverse winding.

**Fix:** After coordinate swap, reverse the winding of all faces:
```python
frv = [(v[2], v[1], v[0]) for v in frv]
frf = [tuple(reversed(face)) for face in frf]  # fix winding
```
Or use a proper rotation matrix instead of coordinate swap.

---

## HIGH SEVERITY BUGS

### BUG-04: Unused cylinder variable in cape_mesh generation (dead code / missed geometry)
**File:** `armor_meshes.py`, lines 1192-1198 (generate_cape_mesh, "full" style)
**Severity:** HIGH (wasted computation, confusing code)
**Description:** A cylinder is generated for the clasp bar:
```python
cbv, cbf = _make_cylinder(0, cape_height - 0.005, 0,
                          0.008, 0.01, segments=6,
                          cap_top=True, cap_bottom=True)
# Rotate bar to be horizontal -- approximate with a box
cbv2, cbf2 = _make_box(0, cape_height, 0,
                       cape_width * 0.25, 0.006, 0.006)
parts.append((cbv2, cbf2))
```
`cbv` and `cbf` are computed but never used -- they're replaced by a box approximation. The cylinder geometry is wasted computation. The comment says "approximate with a box" suggesting the developer intended to use the cylinder but couldn't get the rotation right (same rotation problem as BUG-03).

**Fix:** Remove the dead cylinder generation (lines 1192-1194), or fix the rotation and use the cylinder.

### BUG-05: helmet_compatible_hair returns coverage names that don't exist in _COVERAGE_RANGES
**File:** `hair_system.py`, `get_helmet_compatible_hair()`, lines 492, 501
**Severity:** HIGH (wrong hair rendering when helmet is equipped)
**Description:** `get_helmet_compatible_hair()` returns `modified_coverage` values:
- `"back_and_sides"` (line 492, for open_face helmet)
- `"front_fringe"` (line 501, for hood helmet)

These coverage names do NOT exist in `_COVERAGE_RANGES` (lines 61-68). If a consumer takes the `modified_coverage` value and passes it to `_distribute_angles()` (used by `generate_hair_mesh()`), the function falls back to `_COVERAGE_RANGES["full"]` via `ranges = _COVERAGE_RANGES.get(coverage, _COVERAGE_RANGES["full"])` (line 149).

This means:
- Open face helmet: hair should show at back/sides only, but generates FULL coverage hair
- Hood: hair should show front fringe only, but generates FULL coverage hair

**Fix:** Add the missing coverage ranges to `_COVERAGE_RANGES`:
```python
"back_and_sides": [(math.pi * 0.4, math.pi * 1.6)],  # back 180 + sides
"front_fringe": [(2 * math.pi - 0.4, 2 * math.pi + 0.4)],  # narrow front band
```

### BUG-06: Cape/cloak sheet meshes are single-sided -- invisible from back
**File:** `armor_meshes.py`, generate_cape_mesh all 3 styles (lines 1158-1296)
**Severity:** HIGH (cape invisible from behind in game)
**Description:** All three cape styles (full, half, tattered) generate flat quad sheets with single-sided geometry. In real-time rendering, these will be invisible from the back side unless the material has backface culling disabled.

The clothing_system.py explicitly handles this differently -- `_generate_sheet_grid()` is designed to produce sheets for cloth sim where thickness is added by the simulation. But capes in armor_meshes.py are static geometry that should be visible from both sides.

**Fix:** Either generate a back-face duplicate with reversed normals (adds poly count but ensures visibility), or document that cape materials MUST disable backface culling.

### BUG-07: Ornate belt decorative plates are axis-aligned, not tangent to belt curve
**File:** `armor_meshes.py`, generate_belt_mesh "ornate" style, lines 1399-1409
**Severity:** HIGH (visual -- plates float off the belt surface at odd angles)
**Description:** Decorative plates are placed at positions on the belt circle:
```python
px = math.cos(angle) * (waist_r + belt_h * 0.3)
pz = math.sin(angle) * (waist_r + belt_h * 0.3)
pv, pf = _make_box(px, 0, pz, belt_h * 0.35, belt_h * 0.45, belt_h * 0.08)
```
The boxes are axis-aligned (not rotated to be tangent to the belt). At angle=0 (front), the plate faces forward correctly. At angle=pi/2 (side), the plate still faces the same direction -- it intersects the belt from the side instead of sitting flush on the surface. Same issue affects the gem spheres offset by `pz + belt_h * 0.1` which only works at angle=0.

The same issue affects chain belt links (line 1341-1348) -- torus links are not rotated to follow the belt curve.

**Fix:** Rotate each plate and gem to be tangent to the belt circle at its placement angle. Use the angle to compute a local coordinate frame and transform the box accordingly.

---

## MEDIUM SEVERITY BUGS

### BUG-08: Coordinate system mismatch between character subsystems
**File:** Multiple files
**Severity:** MEDIUM (integration issue requiring manual coordinate transforms)
**Description:** The character generation pipeline has a coordinate system split:

| File | Up Axis | Forward Axis | Used By |
|------|---------|--------------|---------|
| `npc_characters.py` | Z | Y | Character bodies |
| `eye_mesh.py` | Z | -Y | Eyes |
| `facial_topology.py` | Y (depth) | implicit | Face mesh |
| `armor_meshes.py` | Y | Z | All armor pieces |
| `clothing_system.py` | Y | implicit | All clothing |
| `hair_system.py` | Z | Y | Hair cards |
| `monster_bodies.py` | Y | Z | Monster bodies |

NPC characters use Z-up (line 128: `_ring` generates in XY plane at height cz). Armor and clothing use Y-up (line 130 in armor: `_make_cylinder` generates along Y axis). Hair uses Z-up for head center default `(0, 0, 1.7)` (line 315).

When combining armor (Y-up) with an NPC body (Z-up), all coordinates will be misaligned.

**Fix:** Establish a single convention and add coordinate transform bridges at integration points, or convert all systems to the same convention.

### BUG-09: Rubble pile generates non-manifold geometry with potential degenerate faces
**File:** `destruction_system.py`, `generate_rubble_pile()`, lines 357-375
**Severity:** MEDIUM (non-manifold mesh, UV/normal issues)
**Description:** Each rubble chunk generates 4-6 random vertices, then creates faces as a triangle fan from vertex 0 plus one "bottom" face. The random vertex placement means:
1. Fan faces can be coplanar or nearly so (degenerate)
2. The mesh is not a closed solid -- it's an open fan with one additional triangle
3. Vertices can be extremely close together causing T-junctions
4. No UV data is generated (`"uvs": []` in the result)

For a rubble pile used as background detail this is acceptable, but if these meshes go through the export pipeline they'll trigger game engine mesh validation warnings.

**Fix:** Use proper convex hull construction instead of fan triangulation, or at minimum validate that generated faces have non-zero area.

### BUG-10: monster_bodies.py O(n^2) vertex welding with no size guard
**File:** `monster_bodies.py`, `_weld_coincident_vertices()`, lines 89-151
**Severity:** MEDIUM (performance on larger monsters)
**Description:** The vertex welding function uses O(n^2) distance comparison:
```python
for i in range(n):
    ...
    for j in range(i + 1, n):
```
The comment says "acceptable for meshes under ~10k verts" but there's no guard or warning for larger meshes. A complex monster with many brand features could exceed this. The same O(n^2) weld function is duplicated in `npc_characters.py` (lines 158-205).

**Fix:** Add a vertex count guard that switches to spatial hashing above a threshold (e.g., 8000 verts), or document the limit in the function docstring and validate at the caller level.

### BUG-11: Thorn/bone spur cone orientation doesn't align with surface normal
**File:** `monster_bodies.py`, `_generate_thorns()`, lines 418-440
**Severity:** MEDIUM (thorns point upward instead of outward from surface)
**Description:** The thorn generation creates a cone at the surface point:
```python
tv, tf = _cone(pt[0], pt[1], pt[2], base_r, thorn_length, segments=5)
```
The cone is generated along the Y axis (vertical). Then only the apex vertex is moved to align with the normal:
```python
tv[-1] = (tip_x, tip_y, tip_z)
```
This moves the tip along the normal, but the base ring remains in the horizontal XZ plane. For thorns on the side of a creature, the base ring should be perpendicular to the normal, not horizontal. This creates banana-shaped thorns instead of straight ones projecting from the surface.

**Fix:** Transform all cone vertices using a rotation matrix that aligns the Y axis with the surface normal, not just the tip.

### BUG-12: Chain link rotation is incorrect in monster_bodies.py
**File:** `monster_bodies.py`, `_generate_chains()`, line 370
**Severity:** MEDIUM (chain links don't interlock properly)
**Description:** Every other chain link is "rotated 90 degrees" by this transform:
```python
link_v = [(v[2] - pt[2] + pt[0], v[1], -(v[0] - pt[0]) + pt[2]) for v in link_v]
```
This is a rotation around the Y axis, but it doesn't account for the link's position relative to the chain path direction. The rotation axis should be the chain path tangent, not global Y. Links along a curved surface will have inconsistent interlocking angles.

**Fix:** Compute chain path tangent between consecutive surface points, and rotate the alternate links around that tangent.

### BUG-13: facial_topology.py eye loop quads have mismatched vertex counts between rings
**File:** `facial_topology.py`, `generate_face_mesh()`, lines 246-258
**Severity:** MEDIUM (T-junctions and non-manifold edges around eyes)
**Description:** Concentric eye loops increase vertex count per ring: `n_pts = max(4, ring_seg // 2 + loop_i * 2)`. When connecting adjacent rings, the code uses `min(prev_count, curr_count)` to limit the quad count:
```python
for j in range(min(prev_count, curr_count)):
```
When prev_count < curr_count, the extra vertices in the outer ring are left unconnected -- they're floating vertices that create non-manifold edges. When prev_count > curr_count (can't happen with this formula, but fragile), quads would reference out-of-bounds indices.

**Fix:** Use proper ring bridging that handles different vertex counts (e.g., insert triangles to transition between ring sizes).

### BUG-14: clothing_system.py _pseudo_random can return exactly 0.0 and 1.0
**File:** `clothing_system.py`, `_pseudo_random()`, line 217
**Severity:** LOW-MEDIUM (edge case in tatter displacement)
**Description:** The function `(math.sin(seed * 12.9898 + 78.233) * 43758.5453) % 1.0` can return exactly 0.0 (when the product is an integer) or values very close to 1.0. In the tatter displacement code (line 300), the random value scales vertex displacement. A value of 0.0 means no displacement at that vertex, creating a visible sharp undamaged point in an otherwise tattered edge. While rare, this is noticeable on tattered robes and cloaks where all surrounding vertices are displaced but one is perfectly aligned.

**Fix:** Add a minimum displacement floor for tatter: `rnd = max(0.1, _pseudo_random(seed_v))` in tatter contexts.

---

## LOW SEVERITY / CODE QUALITY

### BUG-15: armor_meshes.py silently defaults invalid styles instead of raising ValueError
**File:** `armor_meshes.py`, every generator function (e.g., line 403, 592, 787, 909, etc.)
**Severity:** LOW (defensive coding issue)
**Description:** When an invalid style is passed, every generator silently defaults:
```python
if style not in _HELMET_STYLES:
    style = "open_face"
```
Compare with hair_system.py and character_advanced.py which raise `ValueError` for invalid inputs. The silent defaulting masks bugs where wrong style names are passed from upstream code.

**Fix:** Raise `ValueError` with valid style list, consistent with other generators.

### BUG-16: No UV data generated for any armor_meshes.py or legendary_weapons.py output
**File:** `armor_meshes.py` (all generators), `legendary_weapons.py` (all generators)
**Severity:** LOW (functional but texturing requires auto-UV at import time)
**Description:** Neither `armor_meshes.py` nor `legendary_weapons.py` generate UV coordinates. The `_make_result()` in both files stores `uvs or []`. Compare with `procedural_meshes.py` which auto-generates box-projection UVs via `_auto_generate_box_projection_uvs()`, and `clothing_system.py` which generates proper sewing-pattern UVs.

Armor and weapons are the most visible equipment in the game and need proper UV mapping for texture detail. Currently they rely entirely on the Blender bridge to auto-UV after creation, which produces suboptimal seam placement for complex merged geometry.

**Fix:** Either import and use `_auto_generate_box_projection_uvs` from procedural_meshes.py, or implement armor-specific UV unwrapping (cylindrical for body pieces, planar for plates).

### BUG-17: Duplicated primitive functions across 6+ files
**File:** armor_meshes.py, legendary_weapons.py, loot_display.py, monster_bodies.py, npc_characters.py, weapon_quality.py
**Severity:** LOW (maintenance burden, divergence risk)
**Description:** `_make_box`, `_make_cylinder`, `_make_sphere`, `_make_cone`, `_make_torus_ring`, `_make_tapered_cylinder`, `_merge_meshes`, `_compute_dimensions` are each independently reimplemented in 4-6 files. Some copies have minor differences (e.g., `base_idx` parameter in procedural_meshes.py but not in armor_meshes.py). Over time these will diverge, and a fix in one copy won't propagate.

**Fix:** Extract shared primitives to a `_mesh_primitives.py` module and import everywhere.

---

## Summary

| Severity | Count | New This Scan |
|----------|-------|---------------|
| CRITICAL | 3 | 3 |
| HIGH | 4 | 4 |
| MEDIUM | 7 | 7 |
| LOW | 3 | 3 |
| **TOTAL** | **17** | **17** |

**Running total across 19 scans: ~252 bugs**

### Priority Fixes
1. **BUG-01** (destruction O(n^2)) -- simple fix, massive perf improvement
2. **BUG-03** (flipped normals on coord swap) -- 4 locations, all in armor back items
3. **BUG-05** (helmet hair coverage) -- breaks helmet+hair visual integration
4. **BUG-02/BUG-08** (coordinate system mismatch) -- needs architectural decision before fixing
5. **BUG-07** (belt decorations) -- visual quality issue on ornate/chain belts
