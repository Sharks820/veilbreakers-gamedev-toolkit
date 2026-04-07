# VeilBreakers Terrain & Scene Editing Protocol

**This document is the failsafe rulebook for any agent doing interactive 3D editing in Blender on this project. Violating these rules has wasted multi-hour sessions. Follow them exactly.**

---

## TL;DR — The Six Commandments

1. **OBSERVE before you CALCULATE** — Never trust vertex math over what the user sees.
2. **SYNC to the user's viewport** — Every screenshot must use their live view, not arbitrary cameras.
3. **LOCK reference points** — Drop hidden empties, never recalculate from drifting vertex data.
4. **REAL geometry, not visual trickery** — Boolean cuts and displacement, not painted vertex colors.
5. **SMALLEST possible diff** — One change at a time. Resize, screenshot, confirm. Never rebuild from scratch.
6. **VERIFY placement** — Before placing, ray-cast to confirm in-front vs inside vs underneath.

---

## Section 1 — Live Viewport Sync (MANDATORY)

The user has a live Blender viewport. They're rotating, zooming, looking at things. You **must** see what they see.

### How to read the user's current view

```python
import bpy
from mathutils import Vector

def get_active_view_info():
    """Return the user's current 3D viewport view as a dict."""
    if bpy.context.screen is None:
        return None
    for area in bpy.context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for space in area.spaces:
            if space.type != 'VIEW_3D':
                continue
            r3d = space.region_3d
            cam_matrix = r3d.view_matrix.inverted()
            return {
                'cam_pos': cam_matrix.translation.copy(),
                'target': r3d.view_location.copy(),
                'distance': r3d.view_distance,
                'forward': -cam_matrix.col[2].xyz.normalized(),
                'up': cam_matrix.col[1].xyz.normalized(),
                'perspective': r3d.view_perspective,  # 'PERSP'/'ORTHO'/'CAMERA'
            }
    return None
```

### How to take a screenshot from the user's view

The existing `mcp__vb-blender__blender_viewport` `screenshot` action **already uses the active 3D viewport** via `bpy.ops.render.opengl` with a `temp_override`. **DO NOT pass `camera_location` or `camera_target` to the `screenshot` action — those args are silently dropped.**

```
mcp__vb-blender__blender_viewport(action="screenshot", max_size=800)
```

For a faster preview without beauty setup:

```
mcp__vb-blender__blender_viewport(action="quick_preview")  # 256px, no shading change
```

### Before taking a screenshot

Run `get_active_view_info()` and **report the cam_pos, target, and forward** to yourself. If you don't know what direction the user is looking, you can't interpret what's in the screenshot. This takes 10 lines of code and prevents 30 minutes of confusion.

---

## Section 2 — Locked Reference Empties (MANDATORY for multi-step edits)

When you're about to do anything that involves "the top of X" or "the front of Y" or "the center of Z", **drop a hidden empty** the first time you compute it. After that, READ from the empty. Never recompute.

### Naming convention

`Ref_<ObjectName><LandmarkName>` — e.g., `Ref_WaterfallTopMid`, `Ref_CliffEdgeAtRiver`, `Ref_LakeCenter`.

### Creating a reference empty

```python
def make_ref(name, location, display_type='SPHERE', size=0.5, custom_props=None):
    # Remove existing
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    e = bpy.data.objects.new(name, None)
    e.location = location
    e.empty_display_type = display_type  # SPHERE, CUBE, ARROWS, PLAIN_AXES
    e.empty_display_size = size
    e.show_in_front = True  # visible through other geometry
    bpy.context.collection.objects.link(e)
    if custom_props:
        for k, v in custom_props.items():
            e[k] = v
    return e
```

### Storing metadata on a reference

Use custom properties on the empty so you can later read direction vectors, lengths, etc.:

```python
mid = make_ref('Ref_WaterfallTopMid', mid_pos, 'CUBE', 0.7)
mid['edge_length'] = 1.34
mid['cnx'] = -0.943   # cliff normal X
mid['cny'] = 0.154
mid['cnz'] = 0.296
```

### Reading a reference

```python
mid = bpy.data.objects['Ref_WaterfallTopMid']
mid_pos = mid.matrix_world.translation
edge_length = mid['edge_length']
cliff_normal = Vector((mid['cnx'], mid['cny'], mid['cnz']))
```

### When to UPDATE a reference

Only when:
- The user explicitly says the underlying object moved
- You verify the underlying object's `matrix_world.translation` differs from the empty's recorded `<obj>_origin_*` custom prop

**Never** silently recompute on every iteration. That's how you end up building things in the wrong place.

---

## Section 3 — Surface vs Interior vs Underneath vs In-Front (MANDATORY)

This has been the #1 source of "the cave is buried inside the cliff" / "the waterfall is in mid-air" failures. Use this protocol every single time you place an object near terrain.

### Definitions

| Term | Meaning |
|---|---|
| **On the surface** | Point distance to surface < ε (~0.05). Touching. |
| **In front of** (visible) | Point is outside the mesh, on the same side as the surface normal at the nearest face. |
| **Inside the mesh** | Point is enclosed by the mesh boundary (odd ray-cast count from point to ∞). |
| **Underneath** | Inside the mesh AND on the negative-Z side of the nearest face — buried or below ground. |
| **Floating** | Far from the surface (> a few units). May be above, in front, or beside. |

### The Placement Verification Function

```python
import mathutils
from mathutils import Vector
BVHTree = mathutils.bvhtree.BVHTree

def classify_point(point, target_obj, eps=0.1):
    """
    Classify a world-space point relative to target_obj's surface.
    Returns dict with: nearest_point, distance, normal, side ('front'|'back'|'on'),
                       is_inside (best-effort odd-count test).
    """
    eval_obj = target_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = eval_obj.to_mesh()
    mw = eval_obj.matrix_world
    verts = [mw @ v.co for v in mesh.vertices]
    polys = [tuple(p.vertices) for p in mesh.polygons if len(p.vertices) >= 3]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    
    nearest = bvh.find_nearest(point, 1000.0)
    if nearest[0] is None:
        eval_obj.to_mesh_clear()
        return None
    nearest_point, normal, face_idx, dist = nearest
    
    rel = point - nearest_point
    side_dot = rel.dot(normal)
    if abs(dist) < eps:
        side = 'on'
    elif side_dot > 0:
        side = 'front'
    else:
        side = 'back'
    
    # Inside test: cast a ray to +X infinity and count hits
    ray_dir = Vector((1, 0, 0))
    hits = 0
    origin = point.copy()
    for _ in range(20):  # safety limit
        result = bvh.ray_cast(origin, ray_dir, 10000.0)
        if result[0] is None:
            break
        hits += 1
        origin = result[0] + ray_dir * 0.001
    is_inside = (hits % 2) == 1
    
    eval_obj.to_mesh_clear()
    return {
        'nearest': nearest_point,
        'distance': dist,
        'normal': normal,
        'side': side,
        'is_inside': is_inside,
    }
```

### Before placing ANY object near a surface

Run `classify_point(intended_position, terrain)`. If:
- `is_inside == True` — your object will be **buried**. Move along normal until outside.
- `side == 'back'` — your object is **behind** the surface (relative to normal). Wrong side.
- `distance > 5` — your object is **floating**. Either accept it or snap to surface.
- `side == 'front'` and `distance < 1` — **on the surface**, normal-aligned. ✓ correct.

### To "place flush against the surface"

```python
def snap_to_surface(point, target_obj, offset=0.05):
    info = classify_point(point, target_obj)
    return info['nearest'] + info['normal'] * offset
```

### To "place inside (for boolean cutter)"

The cutter must be FULLY embedded and PENETRATE through where the cut should be. Verify with:

```python
def all_verts_inside(cutter_obj, target_obj):
    for v in cutter_obj.data.vertices:
        wc = cutter_obj.matrix_world @ v.co
        info = classify_point(wc, target_obj)
        if not info['is_inside']:
            return False
    return True
```

Note: a useful cutter is **partially** inside (penetrating). Use `is_inside` to confirm at least 50% of cutter verts are inside the target.

---

## Section 4 — The Distance-from-Surface Diagnostic

When something looks "wrong" but you can't tell why, run this. It's the most useful diagnostic in this entire protocol.

```python
def distance_diagnostic(source_obj, target_obj, z_band_size=5):
    """
    Group source_obj vertices by Z bands, report how many touch target_obj
    surface in each band. Reveals exactly where source is in air vs touching.
    """
    eval_t = target_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = eval_t.to_mesh()
    mw = eval_t.matrix_world
    verts = [mw @ v.co for v in mesh.vertices]
    polys = [tuple(p.vertices) for p in mesh.polygons if len(p.vertices) >= 3]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    
    src_mw = source_obj.matrix_world
    bands = {}
    for v in source_obj.data.vertices:
        wc = src_mw @ v.co
        n = bvh.find_nearest(wc, 100.0)
        if n[0] is None:
            continue
        band = int(wc.z // z_band_size) * z_band_size
        bands.setdefault(band, []).append(n[3])
    
    for band in sorted(bands.keys(), reverse=True):
        ds = bands[band]
        n_touch = sum(1 for d in ds if d < 1.5)
        avg = sum(ds) / len(ds)
        print(f"  Z={band:>5} ({len(ds):>3}): touching={n_touch:>3} avg_d={avg:.2f}")
    
    eval_t.to_mesh_clear()
```

This single function would have saved hours in the waterfall session. It immediately reveals:
- What part of the object is floating in air
- What part is embedded
- Where the actual contact line is

**Run this before any "place X relative to Y" operation involving deformed/shrinkwrapped meshes.**

---

## Section 5 — The Smallest-Diff Principle

If the user says "make it wider", you change ONLY the width:

```python
# YES
obj.scale.x *= 1.5
# Screenshot. Confirm.
```

```python
# NO — you changed scale, position, AND material
bpy.data.objects.remove(obj)
new_obj = build_from_scratch(width=15, ...)
new_obj.location = compute_position(...)
apply_material(new_obj, ...)
```

### Allowed operations from smallest to largest

1. **Adjust transform** — `obj.location/rotation/scale` (cheapest, always reversible)
2. **Edit verts via bmesh** — modify existing geometry without rebuild
3. **Add a modifier** — non-destructive, removable
4. **Replace material** — visual only
5. **Rebuild from scratch** — LAST RESORT, requires explicit announcement

If you must rebuild, say so first: "Rebuilding from scratch because the topology can't be edited cheaply." Then do the rebuild.

---

## Section 6 — Real Boolean Cuts (not vertex color tricks)

For cave entrances, recessed openings, holes — **use boolean DIFFERENCE**, not "paint a dark oval on the surface".

### Pre-flight checks (MANDATORY before boolean)

```python
def boolean_preflight(target_obj, cutter_obj):
    """Check if a boolean DIFFERENCE will likely succeed."""
    issues = []
    
    # Target must have polys
    if len(target_obj.data.polygons) == 0:
        issues.append("target has no faces")
    
    # Cutter must be closed (manifold)
    cutter_eval = cutter_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    cm = cutter_eval.to_mesh()
    edges_per_face = {}
    for face in cm.polygons:
        for i in range(len(face.vertices)):
            v1, v2 = face.vertices[i], face.vertices[(i+1) % len(face.vertices)]
            key = (min(v1, v2), max(v1, v2))
            edges_per_face[key] = edges_per_face.get(key, 0) + 1
    non_manifold = [k for k, c in edges_per_face.items() if c != 2]
    if non_manifold:
        issues.append(f"cutter has {len(non_manifold)} non-manifold edges (not closed)")
    cutter_eval.to_mesh_clear()
    
    # Cutter must overlap target spatially
    t_bb = [target_obj.matrix_world @ Vector(c) for c in target_obj.bound_box]
    c_bb = [cutter_obj.matrix_world @ Vector(c) for c in cutter_obj.bound_box]
    t_min = Vector((min(v.x for v in t_bb), min(v.y for v in t_bb), min(v.z for v in t_bb)))
    t_max = Vector((max(v.x for v in t_bb), max(v.y for v in t_bb), max(v.z for v in t_bb)))
    c_min = Vector((min(v.x for v in c_bb), min(v.y for v in c_bb), min(v.z for v in c_bb)))
    c_max = Vector((max(v.x for v in c_bb), max(v.y for v in c_bb), max(v.z for v in c_bb)))
    overlap = all(c_min[i] <= t_max[i] and c_max[i] >= t_min[i] for i in range(3))
    if not overlap:
        issues.append("cutter and target bounding boxes do not overlap")
    
    return issues
```

### Robust cave-cut function

```python
def cut_cave(terrain_obj, cutter_obj, solver='EXACT'):
    """
    Cut cutter_obj out of terrain_obj using boolean DIFFERENCE.
    Returns (success: bool, error: str|None).
    """
    issues = boolean_preflight(terrain_obj, cutter_obj)
    if issues:
        return False, "preflight failed: " + "; ".join(issues)
    
    # Backup the terrain so we can restore on failure
    backup_name = terrain_obj.name + "_BackupBeforeBoolean"
    if backup_name not in bpy.data.objects:
        backup = terrain_obj.copy()
        backup.data = terrain_obj.data.copy()
        backup.name = backup_name
        backup.hide_viewport = True
        bpy.context.collection.objects.link(backup)
    
    bpy.context.view_layer.objects.active = terrain_obj
    mod = terrain_obj.modifiers.new(name="CaveCut", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = solver
    mod.object = cutter_obj
    
    verts_before = len(terrain_obj.data.vertices)
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except RuntimeError as e:
        # Modifier failed — clean up
        terrain_obj.modifiers.remove(mod)
        return False, str(e)
    
    verts_after = len(terrain_obj.data.vertices)
    if verts_after <= verts_before:
        return False, f"boolean produced no new geometry (before={verts_before}, after={verts_after})"
    
    return True, None
```

### If boolean fails on non-manifold terrain

In order, try:
1. **Solver = `'EXACT'`** with `use_hole_tolerant = True` (handles open meshes better)
2. **Solver = `'FLOAT'`** with `double_threshold = 1e-5` (faster, less robust)
3. **Pre-clean** the terrain: remove doubles, recalc normals, fill holes, dissolve degenerates
4. **Voxel remesh** the cut region (expensive but always works)
5. **Solidify modifier** on terrain to give it thickness, then boolean
6. **Fallback to facade**: build a sunken disk in front of the cliff with strong shadows (acceptable but less AAA)

### Valid solver values (Context7 verified, Blender 4.x)

```python
mod = obj.modifiers.new(name="CaveCut", type='BOOLEAN')
mod.operation = 'DIFFERENCE'    # or 'UNION', 'INTERSECT'
mod.solver = 'EXACT'            # 'FLOAT' (fast), 'EXACT' (robust), 'MANIFOLD' (needs closed meshes)
mod.object = cutter_obj
mod.use_self = False
mod.use_hole_tolerant = True    # CRITICAL for terrain
mod.double_threshold = 1e-6
mod.material_mode = 'INDEX'     # or 'TRANSFER'
```

**WRONG:** `mod.solver = 'FAST'` — `'FAST'` is not a valid value. This is why the modifier silently disables. Past sessions wasted hours on this. The valid names are `'FLOAT'`, `'EXACT'`, `'MANIFOLD'`.

---

## Section 7 — The Self-Check Before Any Bmesh Code

Mentally run this checklist before every non-trivial edit:

1. ☐ Did I screenshot from the user's viewport in the last 60 seconds?
2. ☐ Did I run `get_active_view_info()` so I know what direction the user is looking?
3. ☐ Are all reference points locked to empties? Am I recomputing from drifting vertex data?
4. ☐ Did I run `distance_diagnostic` to see where source is touching target?
5. ☐ Did I run `classify_point` for any placement near a surface?
6. ☐ Is this REAL geometry or am I faking depth with vertex colors?
7. ☐ Is this the smallest possible diff for the user's stated request?
8. ☐ Did I confirm ambiguous interpretation (round = circle/oval/arch?) BEFORE building?
9. ☐ Did I research with Context7 / web search / episodic memory if this is non-trivial?

If any box is unchecked, **stop and fix it** before running the bmesh code. The cost of the check is 30 seconds. The cost of skipping is 30 minutes of rework.

---

## Section 8 — When the geometry doesn't make sense

Sometimes the user's mesh is in a weird state — a waterfall extending 20 units into open air, a building floating, etc. **Do not silently work around it.**

1. Run `distance_diagnostic`.
2. If the data shows a clear physical anomaly (e.g., 18-unit air gap), describe it to the user in a single sentence with specific numbers.
3. Offer 2-3 specific options to resolve it.
4. Wait for them to pick one.

Example: "The waterfall mesh extends from Z=2 to Z=110, but it only TOUCHES the cliff between Z=85 and Z=90. The top 20 units (Z=90-110) are floating 3-7 units in front of the cliff. To build a cave at the water emergence point, I can: (a) trim the floating section, (b) build the cave at Z≈92 where water actually meets cliff, or (c) extend the cliff up to meet the waterfall top. Which?"

This respects the user's time better than silently building something wrong.

---

## Section 9 — Required Tool Usage

Before starting any non-trivial editing task, you **must** consider these tools:

| Tool | When to use |
|---|---|
| `mcp__plugin_context7_context7__resolve-library-id` + `query-docs` | Any Blender Python API question — even ones you "know" |
| `mcp__plugin_episodic-memory_episodic-memory__search` | Before starting work on a recurring problem area |
| `mcp__web-search-prime__web_search_prime` | "AAA <thing> technique" research |
| `mcp__zai-mcp-server__analyze_image` | When a screenshot is ambiguous or you're not sure what you're seeing |
| `mcp__zai-mcp-server__ui_diff_check` | When comparing before/after screenshots |
| `mcp__vb-blender__blender_viewport` action=`screenshot` | After every meaningful change |
| `mcp__vb-blender__blender_execute` | The most flexible tool — has full bpy/bmesh/mathutils access |

If you build something non-trivial without using ANY of these tools, you have violated Rule 7 from `feedback_visual_editing_protocol.md` in memory.

---

## Section 10 — Reference: Common Failure Patterns From Past Sessions

| Symptom | Root cause | Prevention |
|---|---|---|
| "the object is inside the cliff" | Used `obj.location` without ray-casting | `classify_point` before placement |
| "the cave is in mid-air" | Used `max(z)` for "top edge" on a deformed mesh | `distance_diagnostic` to find actual cliff contact |
| "the cave moved" between iterations | Recomputed reference each time, mesh drifted | Lock to empties |
| "the boolean did nothing" | Cutter not actually inside target | `all_verts_inside` check + preflight |
| "the colors don't match the existing water" | Built new material instead of reusing | Use existing material name, never `materials.new()` for water |
| "I can't see the change" | Screenshot from wrong angle | Always use the user's active viewport |
| "the math says X but I see Y" | Trusted vertex math over visual | OBSERVE wins. Always. |

---

This protocol is enforced by the agent's auto-memory. Failures are recorded as feedback memories so the next session inherits the lessons.
