# Mesh Inside / Outside / Surface Detection — Technical Reference

**Purpose:** Bulletproof primitives for a 3D scene editor agent that must stop placing objects inside cliffs, under terrain, or floating in air. This is the authoritative reference for "where is point P relative to mesh M?" in Blender's Python API.

**Applies to:** Blender 4.2+ (`bpy`, `bmesh`, `mathutils`, `mathutils.bvhtree`, `mathutils.geometry`)

**Sources consulted:**
- Blender Python API 4.5 (Context7: `/websites/blender_api_4_5`, `/websites/blender_api_current`)
- docs.blender.org/api/current/mathutils.bvhtree.html
- docs.blender.org/api/current/bpy.types.Scene.html (ray_cast)
- docs.blender.org/api/current/bpy.types.Object.html (ray_cast, closest_point_on_mesh)
- blog.michelanders.nl "Performance of ray casting in Blender Python" (parity method benchmark)
- blenderartists.org "Python BVH Tree for ray cast and collisions and snapping"
- developer.blender.org T79369 (calc_volume edge cases)

---

## 0. Coordinate Space — The #1 Source of Bugs

Every primitive in this document is affected by coordinate space. Decide once, be consistent.

| API | Expected space | How to convert |
|---|---|---|
| `scene.ray_cast(depsgraph, origin, direction, distance=...)` | **World space** | use world coords directly |
| `obj.ray_cast(origin, direction, distance=...)` | **Object-local space** | `obj.matrix_world.inverted() @ world_point` |
| `obj.closest_point_on_mesh(origin, distance=...)` | **Object-local space** | same |
| `BVHTree.FromObject(obj, depsgraph)` | **World space** (tree bakes the matrix in) | use world coords |
| `BVHTree.FromBMesh(bm)` | **Whatever the bmesh verts are in** | you must pre-transform bm.verts or post-transform results |
| `BVHTree.FromPolygons(verts, polys)` | **Whatever space the verts are in** | your choice, be explicit |
| `bmesh.calc_volume()` | **Local space of the bmesh** | multiply by `obj.matrix_world.to_3x3().determinant()` for world volume |

**Rule:** If you mix `obj.ray_cast` with a world-space origin, you will silently hit the wrong face or miss the mesh entirely. Every ray_cast site must comment which space it is operating in.

```python
# Canonical world->local conversion for obj.ray_cast
mwi = obj.matrix_world.inverted()
local_origin = mwi @ world_origin
local_dir = (mwi.to_3x3() @ world_direction).normalized()
hit, loc_local, nrm_local, face_idx = obj.ray_cast(local_origin, local_dir, distance=1e6)
if hit:
    loc_world = obj.matrix_world @ loc_local
    nrm_world = (obj.matrix_world.to_3x3().inverted().transposed() @ nrm_local).normalized()
```

The normal needs the **inverse transpose** of the 3x3 under non-uniform scale. If terrain is uniformly scaled this simplifies to the 3x3 itself.

---

## 1. Is Point P Inside Mesh M?

### 1.1 Ray-Cast Parity (odd/even hit count)

**Theory:** Cast a ray from P in any direction. If the ray exits the mesh an **odd** number of times, P was inside. If **even** (including zero), P was outside. Jordan curve theorem in 3D. Works only for closed manifold meshes.

**API:** `BVHTree.ray_cast(origin, direction, distance)` — preferred. Or `scene.ray_cast` / `obj.ray_cast`.

**Snippet (robust BVHTree version):**
```python
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def is_point_inside_bvh(bvh: BVHTree, point: Vector, direction=Vector((0.577, 0.577, 0.577))) -> bool:
    """
    bvh: built once from the target mesh (world space recommended)
    point: world-space point to test (must match BVH space)
    direction: arbitrary; use a non-axis-aligned dir to avoid grazing coplanar faces
    """
    count = 0
    origin = point.copy()
    EPSILON = 1e-5
    MAX_ITERS = 1000  # safety

    for _ in range(MAX_ITERS):
        hit, normal, index, dist = bvh.ray_cast(origin, direction)
        if hit is None:
            break
        count += 1
        # Nudge past the hit to avoid re-hitting the same face
        origin = hit + direction * EPSILON
    return (count % 2) == 1
```

**Important:**
- Use a **non-axis-aligned** direction like `(0.577, 0.577, 0.577)` (i.e., `Vector((1,1,1)).normalized()`). Axis-aligned rays frequently hit edges and coplanar faces exactly, causing double-counts.
- After each hit, you must offset the new origin by `EPSILON * direction` or you will re-hit the same triangle due to float precision.
- **Majority vote with 3 rays** in different directions is the standard hardening against pathological grazing:

```python
def is_point_inside_hardened(bvh, point):
    dirs = [Vector((1, 1, 1)), Vector((1, -1, 0.5)), Vector((-0.3, 1, 0.7))]
    votes = sum(1 for d in dirs if is_point_inside_bvh(bvh, point, d.normalized()))
    return votes >= 2
```

**Time complexity:** O(k log n) per ray where n = face count, k = hit count along the ray (typically 0-4 for convex-ish regions). Majority vote triples this.

**Failure modes:**
- **Open mesh / non-manifold:** parity is undefined. A terrain plane is a classic case — it has no interior. Do not use parity on terrain strip meshes.
- **Self-intersecting mesh:** parity counts the intersections, not the topological interior. Results can be wrong in self-overlapping regions.
- **Inverted normals:** parity itself does not care about normal direction (it only counts hits). But `bmesh.calc_volume(signed=True)` does.
- **Degenerate triangles:** can double-count. BVHTree ignores zero-area faces but bad UVs or booleans can leave nearly-degenerate faces.

**Test case:**
```python
# Cube at origin, size 2 (world bounds [-1,1]^3)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bvh = BVHTree.FromBMesh(bm)

assert is_point_inside_bvh(bvh, Vector((0, 0, 0))) == True   # dead center
assert is_point_inside_bvh(bvh, Vector((0.9, 0.9, 0.9))) == True   # inside near corner
assert is_point_inside_bvh(bvh, Vector((1.1, 0, 0))) == False  # just outside
assert is_point_inside_bvh(bvh, Vector((100, 100, 100))) == False  # far outside
# Surface point is ambiguous; with EPSILON nudge it usually reads as outside.
```

---

### 1.2 find_nearest + Normal Dot Product

**Theory:** Find the closest surface point `H` with its face normal `N`. Compute `(P - H) . N`. If positive, P is on the outside side of that face; if negative, P is on the inside. Much cheaper than ray parity (single BVH query), but only reliable for **convex** or **near-convex** regions and **correctly oriented** meshes.

**API:** `BVHTree.find_nearest(origin, distance=1.84467e+19) -> (position, normal, index, distance)`

**Snippet:**
```python
def is_point_inside_normal_dot(bvh: BVHTree, point: Vector) -> bool | None:
    hit, normal, index, dist = bvh.find_nearest(point)
    if hit is None:
        return None  # empty BVH
    return (point - hit).dot(normal) < 0.0
```

**Time complexity:** O(log n). Fastest option.

**Failure modes:**
- **Concave cavities:** the nearest face can be on the far wall of a concavity, flipping the sign. Example: testing a point inside a cup-shaped cliff — the nearest face might be the lip, giving the wrong answer.
- **Inverted normals:** the sign flips globally. Always verify the mesh normals first (see section 8.3).
- **Non-manifold terrain:** find_nearest still works on a one-sided terrain strip, but "inside" has no meaning — you get a half-space test relative to the nearest face only.

**When to use:** Fast culling pass. For AAA correctness, combine: fast `normal_dot` first, then confirm with `ray_parity` only on borderline points.

**Test case:**
```python
# Same cube
assert is_point_inside_normal_dot(bvh, Vector((0, 0, 0))) == True
assert is_point_inside_normal_dot(bvh, Vector((2, 0, 0))) == False
# Concave test (torus): a point in the hole of a torus can fail this test
bm.clear()
bmesh.ops.create_circle(bm, segments=32, radius=1.0)  # not a torus but for shape
# For a torus, the center of the hole will report False (correct) via dot product,
# because the nearest face is the inner ring with normal pointing inward.
```

---

### 1.3 BVHTree Construction

You will build the BVH **once per terrain** and reuse it for every placement query. Construction is the expensive step.

**BVHTree.FromObject(object, depsgraph, deform=True, cage=False, epsilon=0.0)**
- Returns a tree in **world space** (it applies the object's matrix_world and all modifiers via depsgraph).
- `deform=True` evaluates armature/shape-key deformations.
- `cage=False` uses the final render mesh; `cage=True` uses the edit cage (pre-subdiv, etc.).
- **Use this** when the terrain has modifiers (subsurf, displace) you want resolved.

```python
depsgraph = bpy.context.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(terrain_obj, depsgraph)  # world space
# reuse for thousands of point queries
```

**BVHTree.FromBMesh(bmesh, epsilon=0.0)**
- Returns a tree in **whatever space the bmesh verts are in**.
- Use when you need the unmodified raw geometry, or when you want control over which faces to include.

```python
bm = bmesh.new()
bm.from_mesh(terrain_obj.data)
bm.transform(terrain_obj.matrix_world)  # move verts to world space explicitly
bvh = BVHTree.FromBMesh(bm)
bm.free()
```

**BVHTree.FromPolygons(vertices, polygons, all_triangles=False, epsilon=0.0)**
- Raw construction from `[Vector]` and `[(i,j,k[,l])]` lists. Fastest, no Blender data dependency.
- Set `all_triangles=True` if you guarantee all polys are length 3 — skips the triangulation pass.
- Use for streamed heightmaps, AI-generated geometry, or anything not already a `bpy.types.Object`.

```python
verts = [Vector((0,0,0)), Vector((1,0,0)), Vector((0,1,0)), Vector((1,1,0))]
polys = [(0,1,3,2)]
bvh = BVHTree.FromPolygons(verts, polys)
```

**Performance:**
- Construction is O(n log n).
- One-time cost. Cache the BVH keyed on `(object_name, depsgraph_update_id)` so invalidating on edit is automatic.
- A 1M-triangle terrain builds in ~1-2s, queries are ~5-20us each.

**Pitfall:** BVHTree does not auto-invalidate if you mutate the mesh. You must rebuild after any `bm.to_mesh()` or operator that changes the terrain. Use `depsgraph.update()` + rebuild.

---

## 2. Is Point P On the Surface of M (within tolerance)?

**API:** `BVHTree.find_nearest` — check distance against epsilon.

**Snippet:**
```python
def is_point_on_surface(bvh: BVHTree, point: Vector, tolerance: float = 1e-4) -> bool:
    hit, normal, index, dist = bvh.find_nearest(point)
    return hit is not None and dist <= tolerance
```

**Choosing tolerance:**
- 1e-4 (0.0001 m = 0.1 mm): exact snap after a surface operation.
- 1e-2 (0.01 m = 1 cm): "sitting on the ground" for game objects.
- 0.1-1.0 m: "near the terrain" for fuzzy placement checks.

**Snap workflow:**
```python
def snap_to_surface(bvh: BVHTree, point: Vector) -> tuple[Vector, Vector]:
    """Returns (snapped_point, surface_normal). Always succeeds if BVH is non-empty."""
    hit, normal, index, dist = bvh.find_nearest(point)
    return hit, normal
```

**Time complexity:** O(log n).

**Failure modes:**
- Does not tell you which **side** of the surface you were on — combine with section 3.
- Tolerance too tight: you get `False` for points that were "on" the surface in intent but were placed by a worldbuilding pass that used single-precision floats. Prefer 1e-3 or larger unless you just ran a snap.

**Test case:**
```python
# Plane at z=0
verts = [Vector((-1,-1,0)), Vector((1,-1,0)), Vector((1,1,0)), Vector((-1,1,0))]
polys = [(0,1,2,3)]
bvh = BVHTree.FromPolygons(verts, polys)
assert is_point_on_surface(bvh, Vector((0, 0, 0))) == True
assert is_point_on_surface(bvh, Vector((0, 0, 0.0001))) == True  # at tolerance
assert is_point_on_surface(bvh, Vector((0, 0, 0.1))) == False
```

---

## 3. Is Point P In Front of Mesh M (along surface normal)?

**Theory:** "In front" = on the side the face normal points toward. Useful for "place this decal flush with the cliff face, camera side."

**Snippet:**
```python
def is_point_in_front(bvh: BVHTree, point: Vector) -> bool | None:
    hit, normal, index, dist = bvh.find_nearest(point)
    if hit is None:
        return None
    offset = point - hit
    return offset.dot(normal) > 0.0
```

**Variant — signed distance from surface (best for decision logic):**
```python
def signed_distance_to_surface(bvh, point) -> float | None:
    hit, normal, index, dist = bvh.find_nearest(point)
    if hit is None:
        return None
    sign = 1.0 if (point - hit).dot(normal) > 0 else -1.0
    return sign * dist
```

A signed distance of `+1.5` means "1.5 meters in front of the surface." `-0.3` means "0.3 meters behind the surface" (buried). This is the single best scalar to key placement logic on.

**Time complexity:** O(log n).

**Failure modes:**
- Depends on correct normals (section 8.3).
- Ambiguous at concavities — see 1.2.
- On a non-manifold strip, "in front" depends on which side the normals were baked on. Run `bpy.ops.mesh.normals_make_consistent(inside=False)` after generation, or explicitly flip.

---

## 4. What Direction is "Outside" at Point P?

For decal and placement orientation: you need a **stable** surface normal at P, not the jittery face normal.

### 4.1 Nearest face normal (fastest, noisy)
```python
hit, normal, index, dist = bvh.find_nearest(point)
# `normal` is the face normal of the closest polygon
```

Noisy across triangle boundaries — if P moves 1 mm, normal can jump by 60 degrees at a sharp edge.

### 4.2 Averaged vertex-weighted normal (smoother)
```python
def smooth_outward_normal(obj, bvh, point: Vector) -> Vector:
    """Uses vertex normals of the closest face for smooth interpolation."""
    hit, face_normal, face_idx, dist = bvh.find_nearest(point)
    if hit is None:
        return Vector((0, 0, 1))

    # Get the face and its vertex normals (world space)
    mesh = obj.data
    poly = mesh.polygons[face_idx]
    mw3 = obj.matrix_world.to_3x3().inverted().transposed()
    verts_world = [obj.matrix_world @ mesh.vertices[vi].co for vi in poly.vertices]
    normals_world = [(mw3 @ mesh.vertices[vi].normal).normalized() for vi in poly.vertices]

    # Barycentric-ish weighting by inverse distance
    weights = [1.0 / max((point - v).length, 1e-6) for v in verts_world]
    total_w = sum(weights)
    smoothed = Vector((0, 0, 0))
    for n, w in zip(normals_world, weights):
        smoothed += n * (w / total_w)
    return smoothed.normalized()
```

### 4.3 Multi-sample smoothing (smoothest, slowest)
```python
def averaged_normal(bvh: BVHTree, point: Vector, radius: float = 0.5, samples: int = 8) -> Vector:
    """Sample find_nearest at jittered points around P, average the normals."""
    import random
    random.seed(42)
    acc = Vector((0, 0, 0))
    count = 0
    for _ in range(samples):
        jitter = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))) * radius
        hit, n, idx, d = bvh.find_nearest(point + jitter)
        if hit is not None:
            acc += n
            count += 1
    return (acc / count).normalized() if count else Vector((0, 0, 1))
```

**Use case routing:**
- Rock placement on ground: 4.1 is fine, jitter doesn't matter.
- Decal placement on cliff: 4.2 (smooth across the triangle).
- Camera-facing banner on uneven terrain: 4.3 (need stability under small position changes).

---

## 5. Project Point P onto Surface Along Direction D

**API:** `BVHTree.ray_cast(origin, direction, distance)` or `scene.ray_cast`.

### 5.1 BVHTree ray cast
```python
def project_onto_surface(bvh: BVHTree, point: Vector, direction: Vector, max_dist=1e6):
    """Returns (hit_point, hit_normal) or (None, None)."""
    dir_n = direction.normalized()
    hit, normal, index, dist = bvh.ray_cast(point, dir_n, max_dist)
    return hit, normal
```

### 5.2 Snap-to-ground convenience
```python
def snap_to_ground(bvh: BVHTree, point: Vector, up=Vector((0, 0, 1)), max_drop=1000.0):
    """Drops P straight down onto terrain. Returns (grounded_point, up_normal) or (None, None)."""
    # Start above in case P is below terrain
    origin = point + up * max_drop
    hit, normal, index, dist = bvh.ray_cast(origin, -up, max_drop * 2)
    return hit, normal
```

**Important: Z-up.** Blender is Z-up. Do not use `(0, 1, 0)` for "down" — that's Y-forward. This is a recurring bug in this codebase per `feedback_blender_z_up.md`.

### 5.3 Scene ray_cast (hits any visible object, not just one)
```python
def scene_snap_to_ground(context, world_point: Vector, up=Vector((0, 0, 1)), max_drop=1000.0):
    depsgraph = context.evaluated_depsgraph_get()
    origin = world_point + up * max_drop
    result, location, normal, index, obj, matrix = context.scene.ray_cast(
        depsgraph, origin, -up, distance=max_drop * 2
    )
    return (location, normal, obj) if result else (None, None, None)
```

`scene.ray_cast` signature (Blender 4.x): `ray_cast(depsgraph, origin, direction, *, distance=1.70141e+38)` — returns `(result, location, normal, index, object, matrix)`. Note the `depsgraph` is now positional and required.

### 5.4 Primitive ray-triangle (no BVH)
```python
from mathutils.geometry import intersect_ray_tri
hit = intersect_ray_tri(v0, v1, v2, direction, origin, clip=True)
# Returns Vector or None. Use for one-off triangle tests; do not loop this over a mesh.
```

---

## 6. All Vertices of Object A Relative to Mesh M

Use this before a boolean to catch "cutter fully outside target" or "cutter fully embedded" — both cause silent booleans-that-do-nothing.

```python
def classify_verts(obj_a, bvh_m: BVHTree) -> dict:
    """
    Classifies every vertex of A as 'inside' | 'outside' | 'surface' relative to M.
    Returns counts and a fully_inside / fully_outside / straddles summary.
    """
    mesh_a = obj_a.data
    mw = obj_a.matrix_world
    inside = outside = surface = 0
    TOL = 1e-4

    for v in mesh_a.vertices:
        wp = mw @ v.co
        hit, nrm, idx, dist = bvh_m.find_nearest(wp)
        if hit is None:
            outside += 1
            continue
        if dist <= TOL:
            surface += 1
        elif (wp - hit).dot(nrm) < 0.0:
            inside += 1
        else:
            outside += 1

    n = len(mesh_a.vertices)
    return {
        "inside": inside,
        "outside": outside,
        "surface": surface,
        "total": n,
        "fully_inside": inside == n,
        "fully_outside": outside == n,
        "straddles": inside > 0 and outside > 0,
    }
```

**Decision matrix for boolean operations:**
| Classification | Action |
|---|---|
| `fully_outside` | Boolean will do nothing. Warn or skip. |
| `fully_inside` (cutter inside M) | DIFFERENCE will hollow out cleanly. UNION is a no-op. |
| `straddles` | Normal boolean case. Proceed. |
| `surface > 0.5 * total` | Coplanar overlap. Booleans will produce NaN faces. Nudge cutter by 1e-3 first. |

**Note:** This uses the fast normal_dot method. For non-manifold cliffs, augment with `is_point_inside_bvh` (ray parity) on a sample of 10-20 vertices to double-check.

---

## 7. Volumetric Tests

### 7.1 BVHTree.overlap — does A intersect M?
```python
def objects_intersect(obj_a, obj_b, depsgraph) -> bool:
    bvh_a = BVHTree.FromObject(obj_a, depsgraph)
    bvh_b = BVHTree.FromObject(obj_b, depsgraph)
    pairs = bvh_a.overlap(bvh_b)  # list of (tri_idx_a, tri_idx_b)
    return len(pairs) > 0
```

**Returns:** `list[(index_a, index_b)]` — pairs of triangle indices whose bounds overlap AND that actually intersect.

**Time complexity:** O((n+m) log(n+m)) roughly. Very fast because it rejects on bounding boxes first.

**Failure modes:**
- `overlap` only reports **surface intersections**. If A is fully inside M with no touching faces, overlap returns `[]` — NOT what you want for "is A embedded." Combine with `classify_verts` for embedded-object detection.
- Coplanar faces can be over-reported. Treat any `len(pairs) > 0` as "they touch" and dig deeper only if needed.

### 7.2 bm.calc_volume — closed-mesh volume
```python
def mesh_volume(obj) -> float:
    """World-space volume. Requires closed, manifold mesh."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])  # improves accuracy
    bm.normal_update()
    vol_local = bm.calc_volume(signed=True)
    bm.free()
    # Scale to world space
    scale = obj.matrix_world.to_3x3().determinant()
    return abs(vol_local * scale)
```

**`signed=True`:** returns **negative** volume if normals are flipped. Use as a normal-orientation sanity check:
```python
if bm.calc_volume(signed=True) < 0:
    bmesh.ops.reverse_faces(bm, faces=bm.faces)  # fix inversion
```

**Failure modes:**
- Non-closed mesh → garbage result, not an error. Check `all(len(e.link_faces) == 2 for e in bm.edges)` for manifold-ness first.
- N-gons → inaccurate. Triangulate first.
- Reported off-by-2x bug in some versions (developer.blender.org T79369) — triangulate to avoid.

---

## 8. Edge Cases

### 8.1 Non-manifold terrain
Real terrain is a **heightmap strip** with an open bottom. It has no "inside." Use only:
- `find_nearest` (works fine)
- `ray_cast` from above in the `-Z` direction (works fine if the strip faces up)
- **NOT** parity counting — undefined.

If you need an "inside" concept for terrain (e.g., "is this cave entrance below the surface"), wrap the terrain in a closed volume first:
```python
# Clone terrain, extrude down to a floor plane, solidify — gives you a closed proxy
proxy = terrain_obj.copy()
proxy.data = terrain_obj.data.copy()
# ... extrude bottom edges to z=BEDROCK_Z, fill
bvh_proxy = BVHTree.FromObject(proxy, depsgraph)
# Now parity tests work: "is P inside the closed bedrock volume"
```

### 8.2 Self-intersecting meshes
Parity counting double-counts through self-intersections. If you cannot clean the mesh, prefer `find_nearest + normal_dot` which is locally correct, even though globally inconsistent.

### 8.3 Inverted normals — detection and fix

**Detect via signed volume:**
```python
bm = bmesh.new(); bm.from_mesh(obj.data); bm.normal_update()
if bm.calc_volume(signed=True) < 0:
    print("Normals inverted")
```

**Detect via ray from outside (BVH):**
```python
# Shoot a ray from a point known to be outside (e.g., bounding-box corner + 1000 up)
far_outside = Vector(obj.bound_box[0]) + Vector((0, 0, 1000))
hit, nrm, idx, d = bvh.ray_cast(far_outside, Vector((0, 0, -1)))
# If hit, the first face should have normal pointing AWAY from the ray direction
# i.e., nrm.dot(-ray_dir) > 0, i.e., nrm.z > 0
if hit and nrm.z < 0:
    print("Top-face normal points down — inverted")
```

**Fix:**
```python
import bpy
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)  # recalculate outside
bpy.ops.object.mode_set(mode='OBJECT')
```

### 8.4 High poly count performance

| Mesh size | BVHTree build | find_nearest | ray_cast | Parity (3 rays) |
|---|---|---|---|---|
| 1k tris | ~1 ms | ~2 us | ~3 us | ~10 us |
| 100k tris | ~50 ms | ~5 us | ~10 us | ~30 us |
| 1M tris | ~800 ms | ~10 us | ~20 us | ~60 us |
| 10M tris | ~10 s | ~15 us | ~30 us | ~100 us |

(Ballpark numbers — real values depend on CPU and query distribution. Source: michelanders.nl benchmark and blenderartists threads.)

**Takeaways:**
- Build the BVH **once** per terrain, cache it on the addon state keyed by depsgraph update id.
- For point queries, prefer `BVHTree` over `obj.closest_point_on_mesh` — BVHTree is 2-5x faster in practice.
- For batch placement of 10k+ objects, use a **kd-tree of pre-sampled surface points** (`mathutils.kdtree.KDTree`) and interpolate, instead of doing 10k ray_casts.

```python
from mathutils.kdtree import KDTree
# Pre-sample 50k surface points on terrain
kd = KDTree(50_000)
# ... populate with Vector samples ...
kd.balance()
# Query: nearest_co, idx, dist = kd.find(point)
```

### 8.5 Coordinate precision
Blender uses single-precision floats internally. For a terrain spanning >10 km, position errors of 1-10 cm are normal and BVH queries will reflect that. Either:
- Work in chunks (local-origin per tile), or
- Accept `1e-2` as the minimum tolerance for "on surface" checks.

---

## 9. Placement Verification Protocol

**Intent:** "Place object O so it sits flush with surface of terrain T at world position P, facing camera C."

### Pre-flight
1. **Build/fetch BVH** for T in world space. Cache key: `(T.name, depsgraph_update_id)`.
2. **Validate T normals:** `bm.calc_volume(signed=True) >= 0` (if closed) OR sample 10 top-face normals and assert `z > 0` (if terrain strip). Fix inversions before proceeding.

### Snap
3. **Determine snap axis.** For ground placement: `-Z`. For wall placement: use the averaged surface normal at P (section 4.2/4.3) and snap along `-normal`.
4. **Ray-cast snap:**
   ```python
   snap_origin = P + snap_up * MAX_DROP
   hit, nrm, face_idx, dist = bvh.ray_cast(snap_origin, -snap_up, MAX_DROP * 2)
   ```
5. **Fallback to find_nearest** if ray missed (P was outside terrain bounds):
   ```python
   if hit is None:
       hit, nrm, face_idx, dist = bvh.find_nearest(P)
       if hit is None:
           raise ValueError("Terrain BVH is empty")
   ```
6. **Snapped position** = `hit`. **Surface normal** = smoothed normal via section 4.2.

### Orient
7. **Up vector** = surface normal (or world Z for "upright regardless of slope" objects like buildings).
8. **Forward vector** = project (C.location - hit) onto the plane perpendicular to up:
   ```python
   to_camera = (camera_obj.matrix_world.translation - hit).normalized()
   forward = (to_camera - to_camera.project(up)).normalized()
   right = forward.cross(up).normalized()
   # Build orientation matrix from (right, forward, up)
   rot = Matrix((right, forward, up)).transposed().to_4x4()
   ```

### Clearance check (the part that catches "inside the cliff")
9. **Object bounding-box vertices in world space:**
   ```python
   bbox_world = [obj.matrix_world @ Vector(c) for c in O.bound_box]
   ```
10. **For each bbox vertex**, compute `signed_distance_to_surface(bvh, v)`.
11. **Decision:**
    - If **any** signed distance is `< -clearance_tolerance` (default 1 cm): object is **embedded in terrain**. Lift along `up` by `-min(signed_distances) + tolerance` and retry.
    - If **all** signed distances are `> 1.0 m`: object is **floating**. Drop along `-up` until bottom face touches.
    - If any point is embedded AND lifting would leave >50% of bbox floating: geometry conflict. Reject placement and log.
12. **Footprint ray-casts** for extra safety (4 corner rays straight down from the bbox top):
    ```python
    for corner in bbox_top_corners:
        hit, *_ = bvh.ray_cast(corner, -up, 10.0)
        if hit is None:
            raise ValueError(f"Corner {corner} has no terrain below — cliff edge overhang")
    ```

### Post-placement validation
13. **Classify the verts** of O against T BVH (section 6). Assert `inside == 0`.
14. **Visibility check:** ray-cast from camera to object center. If the ray hits T before hitting O, object is occluded — ok or not depending on intent, but log it.
15. **(Optional) Boolean preview:** `bvh_O.overlap(bvh_T)` must be `[]` for full clearance, or a small list for a "half-buried rock" intent.

### Failure recovery
16. If all snaps fail (empty terrain region, P outside bounds): **do not place**. Return an error with the diagnosis (`"P at (x,y,z) is outside terrain AABB"` or `"Terrain BVH is empty — check if depsgraph evaluated"`).
17. Log every attempt with the signed distance of each bbox vertex. Agents should be able to see "placed at (x,y,z), deepest vert was at -2.3 m, lifted by 2.35 m" as a trace.

---

## 10. Reference Card

```python
# -- setup (once per terrain) --
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
depsgraph = bpy.context.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(terrain, depsgraph)  # world space

# -- queries --
# nearest point on surface
hit, normal, face_idx, dist = bvh.find_nearest(P)

# ray cast
hit, normal, face_idx, dist = bvh.ray_cast(origin, direction, distance=1e6)

# on surface (tolerance)
on_surface = hit is not None and dist < 1e-4

# signed distance (positive = outside)
sd = (P - hit).dot(normal)

# inside test (closed mesh, concave-safe with parity)
inside = is_point_inside_bvh(bvh, P)

# object-object intersection
pairs = bvh_A.overlap(bvh_B)  # list of (face_a, face_b)

# snap to ground (Z-up)
hit, nrm, *_ = bvh.ray_cast(P + Vector((0,0,1000)), Vector((0,0,-1)), 2000)
```

---

## 11. Known Gotchas Specific to This Codebase

1. **Z-up violations:** per `feedback_blender_z_up.md`, placement code in this repo repeatedly uses Y as vertical. Every ray-cast in terrain/placement modules must use `Vector((0, 0, -1))` for "down."
2. **BVH caching missing:** there is no BVH cache in `handlers/environment.py` or `handlers/terrain_advanced.py` at time of writing — every placement rebuilds the tree. Expected 10-100x speedup from caching.
3. **Scene.ray_cast signature change:** older Blender used `scene.ray_cast(origin, direction)`. Blender 2.91+ requires `scene.ray_cast(depsgraph, origin, direction, distance=...)`. Any handler that fails with "missing argument" is hitting this.
4. **`obj.closest_point_on_mesh` vs BVH:** the former operates on the **object-local** mesh pre-modifiers, the latter can include modifiers via `FromObject(obj, depsgraph)`. For terrain with a Subsurf modifier, they disagree. Prefer BVHTree.
5. **Terrain is non-manifold:** worldbuilding terrain in this project is a top-strip heightmap. Never run parity inside-tests on it. Always use find_nearest + signed distance for "is this buried."

---

## 12. Implementation Checklist for the Placement Agent

- [ ] Build BVHTree once per terrain, cache keyed on depsgraph update id.
- [ ] Validate terrain normals at build time; auto-fix if inverted.
- [ ] Use `snap_to_ground` (ray cast from above) for all ground placements.
- [ ] Use `smooth_outward_normal` (section 4.2) for orientation, not raw face normal.
- [ ] Classify bbox vertices against terrain BVH before confirming placement.
- [ ] Reject any placement with `inside > 0` or `min_signed_distance < -1 cm`.
- [ ] Log signed distances for every placement for debuggability.
- [ ] Unit test against: flat plane, sphere (closed), torus (concave), heightmap strip (non-manifold), thin cube (coplanar edge case).

---

**End of reference.**
