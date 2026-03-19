# Phase 2: Mesh, UV & Topology Pipeline - Research

**Researched:** 2026-03-18
**Domain:** Blender bmesh Topology Analysis + Mesh Editing + xatlas UV Unwrapping + Game-Readiness Validation
**Confidence:** HIGH

## Summary

Phase 2 builds the mesh analysis, editing, repair, and UV pipeline on top of the Phase 1 socket bridge and compound tool architecture. The core technical surfaces are: (1) Blender's `bmesh` module for topology analysis, mesh repair, and surgical editing, (2) `bpy.ops.mesh` / `bpy.ops.object` operators for operations not exposed through bmesh (boolean, retopology, sculpt filters), (3) the `xatlas` Python library for UV unwrapping and packing, and (4) custom algorithms for UV quality metrics (stretch, overlap, texel density).

The existing codebase already uses bmesh for object creation (see `objects.py` `_create_cube` etc.), the `get_3d_context_override()` pattern for operator calls from timer callbacks, and the compound tool + handler dispatch architecture. Phase 2 extends this with two new compound MCP tools (`blender_mesh` and `blender_uv`) and their corresponding Blender addon handler modules. Every mesh/UV mutation returns before/after screenshots; every analysis returns structured grading data.

**Primary recommendation:** Create two new compound tools (`blender_mesh` with ~12 actions, `blender_uv` with ~8 actions) rather than expanding `blender_object`. Use bmesh for all analysis and most repairs (no operator context issues), fall back to `bpy.ops` with `temp_override` only for boolean, retopology, sculpt filters, and UV layout export. Install xatlas into Blender's Python environment via `pip.main(['install', 'xatlas'])` for UV unwrapping.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MESH-01 | Full topology analysis with A-F grading | bmesh vertex/edge/face iteration for non-manifold, n-gon, pole detection; custom grading thresholds (Section: Topology Analysis Grading) |
| MESH-02 | Auto-repair (remove doubles, fix normals, fill holes, remove loose, dissolve degenerate) | bmesh.ops: remove_doubles, recalc_face_normals, holes_fill, dissolve_degenerate, delete; chained pipeline (Section: Auto-Repair Pipeline) |
| MESH-03 | Surgical mesh editing -- select by material slot, vertex group, loose parts, face normal | bmesh face.material_index, deform layer for vertex groups, vert.link_edges for loose detection, face.normal dot product (Section: Selection Engine) |
| MESH-04 | Sculpt operations on selections (smooth, inflate, flatten, crease) | bmesh.ops.smooth_vert / smooth_laplacian_vert for smooth; bpy.ops.sculpt.mesh_filter for inflate/flatten/sharpen; vertex group masking for targeted application (Section: Sculpt Operations) |
| MESH-05 | Boolean operations (add, subtract, intersect) | bpy.types.BooleanModifier with UNION/DIFFERENCE/INTERSECT + apply modifier pattern; requires context override (Section: Boolean Operations) |
| MESH-06 | Extrude, inset, mirror, separate, join | bmesh.ops: extrude_face_region, inset_individual/inset_region, mirror, bisect_plane; bpy.ops.mesh: separate; bpy.ops.object: join (Section: Editing Operations) |
| MESH-07 | Retopology with target face count preserving hard edges | bpy.ops.object.quadriflow_remesh with target_faces, use_preserve_sharp, use_preserve_boundary; Remesh modifier as fallback (Section: Retopology) |
| MESH-08 | Game-readiness check (poly budget, UV, materials, bones, naming) | Composite check combining MESH-01 metrics + UV-01 metrics + material slot validation + armature check + naming conventions (Section: Game-Readiness Check) |
| UV-01 | UV quality analysis (stretch, overlap, island count, texel density, seam placement) | Custom bmesh UV layer iteration: area-ratio stretch, 2D polygon intersection for overlap, connected-component island counting, texel density formula (Section: UV Quality Analysis) |
| UV-02 | Automatic UV unwrapping via xatlas | xatlas 0.0.11 Python bindings: parametrize(vertices, faces) or Atlas class with ChartOptions/PackOptions; install into Blender Python (Section: xatlas Integration) |
| UV-03 | UV island packing optimization | xatlas PackOptions (padding, resolution, texelsPerUnit, rotateCharts); also bpy.ops.uv.pack_islands as lightweight alternative (Section: UV Packing) |
| UV-04 | Lightmap UV (UV2) generation for Unity | Create second UV layer in bmesh, run xatlas with no-overlap guarantee and padding for lightmap bleeding; Unity requires UV2 named "UV2" or second UV channel (Section: Lightmap UV) |
| UV-05 | Texel density equalization across islands | Calculate per-island texel density (3D area / UV area * texture_size), scale each island to match target density, repack (Section: Texel Density Equalization) |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bmesh | (Blender built-in) | Topology analysis, mesh repair, surgical editing, UV data access | Blender's mesh editing API. Direct geometry access without operator context issues. Already used in Phase 1 `objects.py`. |
| bpy.ops.mesh | (Blender built-in) | Selection operators, cleanup, normals, UV operations requiring edit mode | Needed for operations not exposed via bmesh.ops (select_non_manifold, select_face_by_sides, normals_make_consistent). |
| bpy.ops.object | (Blender built-in) | Boolean modifiers, quadriflow remesh, mode switching | Object-level operations requiring context override from timer. |
| bpy.ops.uv | (Blender built-in) | UV unwrap, pack_islands, export_layout, average_islands_scale | UV manipulation and layout export to PNG/SVG. |
| xatlas | 0.0.11 | High-quality UV unwrapping and packing | Industry-standard parameterization (used by Godot, Unity). Python bindings via pip. Superior to Blender's built-in smart_project for complex geometry. |
| numpy | (Blender built-in) | Array conversion for xatlas integration | Blender ships numpy. Required to convert mesh data to arrays for xatlas. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mathutils | (Blender built-in) | Vector math, area calculations, normal comparison | UV stretch calculation, face normal dot products, geometry math |
| Pillow | >=12.1.0 | UV layout image composition, overlay rendering | Composing UV layout exports with analysis overlays (already in Phase 1 stack) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| xatlas for UV unwrapping | Blender smart_project | smart_project is simpler but produces inferior results on organic meshes. xatlas gives configurable chart/pack options and consistent quality. Use smart_project as quick fallback only. |
| quadriflow_remesh for retopology | Instant Meshes (external binary) | Instant Meshes produces better quad layouts but requires external binary distribution. Quadriflow is built into Blender -- zero dependencies. Use quadriflow first, Instant Meshes as future enhancement. |
| Remesh modifier (voxel) for retopology | quadriflow_remesh | Voxel remesh destroys all sharp features and UVs. Quadriflow preserves sharp edges and boundaries. Voxel remesh is only useful as pre-pass for extremely damaged meshes. |
| Custom UV overlap detection | bpy.ops.uv.select_overlap | The operator selects overlapping UVs in edit mode but does not return structured data. Custom detection via 2D polygon intersection gives counts and percentages. |

**Installation (xatlas into Blender Python):**
```python
# Run once inside Blender's Python to install xatlas
import subprocess
import sys
subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'xatlas==0.0.11'])
```

**Note:** xatlas has pre-built wheels for CPython 3.8-3.13 on Windows/macOS/Linux. Blender 4.x uses Python 3.11-3.12, so wheel installation works without compilation.

## Architecture Patterns

### Tool Architecture Decision: Two New Compound Tools

**Decision:** Create `blender_mesh` and `blender_uv` as two new compound tools (tools 7 and 8 of the ~26 tool budget). Do NOT add mesh/UV actions to the existing `blender_object` tool.

**Rationale:**
1. **Domain separation:** Object operations (create, move, delete) are fundamentally different from mesh topology operations (analyze, repair, edit geometry). Mixing them bloats parameter lists and confuses action semantics.
2. **Token budget:** Phase 1 has 6 tools at ~2000 tokens. Two new tools add ~800 tokens (400 each), bringing total to ~2800. This leaves ample room for the remaining ~18 tools across Phases 3-8.
3. **Parameter explosion prevention:** `blender_mesh` needs parameters like `selection_mode`, `merge_distance`, `target_faces`; `blender_uv` needs `texture_size`, `padding`, `chart_options`. These would pollute `blender_object`'s parameter list.

### New Tool Definitions

```
blender_mesh (~12 actions):
  - analyze_topology    (MESH-01)
  - auto_repair         (MESH-02)
  - select              (MESH-03)
  - sculpt              (MESH-04)
  - boolean             (MESH-05)
  - extrude             (MESH-06)
  - inset               (MESH-06)
  - mirror              (MESH-06)
  - separate            (MESH-06)
  - join                (MESH-06)
  - retopologize        (MESH-07)
  - check_game_ready    (MESH-08)

blender_uv (~8 actions):
  - analyze             (UV-01)
  - unwrap_xatlas       (UV-02)
  - unwrap_blender      (UV-02 fallback)
  - pack_islands        (UV-03)
  - generate_lightmap   (UV-04)
  - equalize_density    (UV-05)
  - export_layout       (visual verification)
  - set_active_layer    (utility)
```

### Handler Module Structure

```
blender_addon/
  handlers/
    __init__.py          # Extended: add mesh_* and uv_* command handlers
    _context.py          # Existing: get_3d_context_override()
    mesh_analysis.py     # NEW: topology analysis, grading, game-readiness check
    mesh_repair.py       # NEW: auto-repair pipeline, cleanup operations
    mesh_editing.py      # NEW: select, sculpt, boolean, extrude, inset, mirror, etc.
    mesh_retopo.py       # NEW: quadriflow retopology
    uv_analysis.py       # NEW: UV quality metrics, stretch, overlap, density
    uv_operations.py     # NEW: xatlas unwrap, pack, lightmap, density equalize
    uv_export.py         # NEW: UV layout rendering to image
    objects.py           # Existing (unchanged)
    scene.py             # Existing (unchanged)
    viewport.py          # Existing (unchanged)
    materials.py         # Existing (unchanged)
    export.py            # Existing (unchanged)
    execute.py           # Existing (unchanged)
```

### MCP Server Extension

```
src/veilbreakers_mcp/
  blender_server.py      # Extended: add blender_mesh() and blender_uv() tools
```

### Pattern: bmesh-First, Operator Fallback

**What:** Use `bmesh` for all operations that can be done without operator context. Fall back to `bpy.ops` with `get_3d_context_override()` + `temp_override` only when necessary.

**When:** Always prefer bmesh. Use operators only for: boolean modifiers, quadriflow_remesh, sculpt mesh_filter, UV export_layout, select_non_manifold (edit mode operator).

**Why:** bmesh operations do not require context overrides and work reliably from timer callbacks. Operators need a 3D viewport context and can fail with `poll()` errors when called from the socket handler's timer.

**Example (analysis via bmesh -- no context issues):**
```python
import bmesh
import bpy

def handle_analyze_topology(params: dict) -> dict:
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {name}")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Non-manifold edges
    non_manifold = [e for e in bm.edges if not e.is_manifold]

    # N-gons (faces with >4 vertices)
    ngons = [f for f in bm.faces if len(f.verts) > 4]

    # Triangles
    tris = [f for f in bm.faces if len(f.verts) == 3]

    # Poles (vertices with != 4 edges, excluding boundary)
    poles = [v for v in bm.verts if len(v.link_edges) != 4
             and not v.is_boundary and len(v.link_edges) > 0]

    # Loose vertices (no connected edges)
    loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]

    # Loose edges (no connected faces)
    loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]

    total_faces = len(bm.faces)
    total_verts = len(bm.verts)
    total_edges = len(bm.edges)

    bm.free()

    # Compute grade
    metrics = {
        "vertex_count": total_verts,
        "edge_count": total_edges,
        "face_count": total_faces,
        "tri_count": len(tris),
        "quad_count": total_faces - len(tris) - len(ngons),
        "ngon_count": len(ngons),
        "ngon_percentage": round(len(ngons) / max(total_faces, 1) * 100, 1),
        "non_manifold_edges": len(non_manifold),
        "pole_count": len(poles),
        "loose_vertices": len(loose_verts),
        "loose_edges": len(loose_edges),
    }
    metrics["grade"] = _compute_grade(metrics)
    return metrics
```

**Example (boolean via operator -- needs context override):**
```python
from ._context import get_3d_context_override

def handle_boolean(params: dict) -> dict:
    target_name = params.get("object_name")
    cutter_name = params.get("cutter_name")
    operation = params.get("operation", "DIFFERENCE")  # UNION, DIFFERENCE, INTERSECT

    target = bpy.data.objects.get(target_name)
    cutter = bpy.data.objects.get(cutter_name)
    if not target or not cutter:
        raise ValueError("Both target and cutter objects required")

    # Add boolean modifier
    mod = target.modifiers.new(name="Boolean", type='BOOLEAN')
    mod.operation = operation.upper()
    mod.object = cutter
    mod.solver = 'EXACT'  # More reliable than FAST

    # Apply modifier via context override
    override = get_3d_context_override()
    if override:
        with bpy.context.temp_override(**override, active_object=target):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    else:
        raise RuntimeError("No 3D viewport for boolean operation")

    # Optionally remove cutter
    if params.get("remove_cutter", True):
        bpy.data.objects.remove(cutter, do_unlink=True)

    return {
        "object_name": target.name,
        "vertex_count": len(target.data.vertices),
        "face_count": len(target.data.polygons),
        "operation": operation,
    }
```

### Pattern: Selection Engine for Surgical Editing

**What:** A reusable selection engine that can select geometry by multiple criteria (material, vertex group, face normal, loose parts) and then apply operations to the selection.

**Why:** MESH-03 and MESH-04 both require targeted selection before operation. A common engine avoids code duplication.

```python
def select_geometry(bm, criteria: dict) -> list:
    """Select bmesh geometry by criteria. Returns selected faces."""
    selected = set()

    if "material_index" in criteria:
        mat_idx = criteria["material_index"]
        for f in bm.faces:
            if f.material_index == mat_idx:
                selected.add(f)
                f.select = True

    if "vertex_group" in criteria:
        group_name = criteria["vertex_group"]
        # Need to access via deform layer
        deform_layer = bm.verts.layers.deform.active
        if deform_layer:
            group_index = criteria.get("vertex_group_index")
            for v in bm.verts:
                weights = v[deform_layer]
                if group_index in weights and weights[group_index] > 0.0:
                    v.select = True
                    for f in v.link_faces:
                        selected.add(f)
                        f.select = True

    if "face_normal_direction" in criteria:
        direction = mathutils.Vector(criteria["face_normal_direction"]).normalized()
        threshold = criteria.get("normal_threshold", 0.7)  # dot product threshold
        for f in bm.faces:
            if f.normal.dot(direction) > threshold:
                selected.add(f)
                f.select = True

    if "loose_parts" in criteria and criteria["loose_parts"]:
        # Select vertices with no face connections
        for v in bm.verts:
            if len(v.link_faces) == 0:
                v.select = True

    return list(selected)
```

### Anti-Patterns to Avoid

- **Using bpy.ops for analysis:** Operators modify state and require context. Use bmesh for read-only analysis -- it works from any thread context via `bm.from_mesh()`.
- **Caching bmesh objects across handler calls:** bmesh references become invalid when the underlying mesh changes. Always create fresh `bm = bmesh.new(); bm.from_mesh(obj.data)` per handler call, and always call `bm.free()`.
- **Forgetting `bm.to_mesh(obj.data)` after edits:** Changes to a bmesh are NOT reflected in the Blender mesh until you write back. Always call `bm.to_mesh()` then `obj.data.update()`.
- **Calling sculpt operators outside sculpt mode:** `bpy.ops.sculpt.mesh_filter()` requires the object to be in SCULPT mode. Must switch mode, apply filter, switch back.
- **Applying boolean without EXACT solver:** The FAST boolean solver frequently fails on complex geometry. Always use `solver='EXACT'`.
- **Running xatlas on non-triangulated mesh:** xatlas requires triangle indices. Triangulate first (in memory via bmesh, not destructively) or use `bmesh.ops.triangulate()` on a copy.

## Topology Analysis Grading

### A-F Grading Thresholds

Based on game industry standards (Polycount wiki, AAA studio guidelines, ThunderCloud Studio QA rubric):

| Grade | Non-Manifold | N-gon % | Poles (5+ edges) | Loose Geo | Tri % | Description |
|-------|-------------|---------|-------------------|-----------|-------|-------------|
| **A** | 0 | 0% | <5% of verts | 0 | <10% | Production-ready, clean quad topology |
| **B** | 0 | <2% | <10% of verts | 0 | <20% | Game-ready with minor topology issues |
| **C** | 0 | <5% | <20% of verts | 0 | <40% | Acceptable for background/LOD assets |
| **D** | 1-5 | <10% | <30% of verts | <10 loose | Any | Needs cleanup before game use |
| **E** | 6-20 | <25% | <50% of verts | <50 loose | Any | Significant issues, auto-repair recommended |
| **F** | >20 | >25% | >50% of verts | >50 loose | Any | Broken mesh, full repair/retopology needed |

**Grading algorithm:**
```python
def _compute_grade(metrics: dict) -> str:
    """Compute A-F topology grade from analysis metrics."""
    total_faces = max(metrics["face_count"], 1)
    total_verts = max(metrics["vertex_count"], 1)
    ngon_pct = metrics["ngon_percentage"]
    nm = metrics["non_manifold_edges"]
    pole_pct = metrics["pole_count"] / total_verts * 100
    loose = metrics["loose_vertices"] + metrics["loose_edges"]
    tri_pct = metrics["tri_count"] / total_faces * 100

    # Grade from worst to best -- first failing threshold sets grade
    if nm > 20 or ngon_pct > 25 or pole_pct > 50 or loose > 50:
        return "F"
    if nm > 5 or ngon_pct > 10 or pole_pct > 30 or loose > 10:
        return "E"
    if nm > 0 or ngon_pct > 5 or pole_pct > 20 or loose > 0 or tri_pct > 40:
        return "D"
    if ngon_pct > 2 or pole_pct > 10 or tri_pct > 20:
        return "C"
    if ngon_pct > 0 or pole_pct > 5 or tri_pct > 10:
        return "B"
    return "A"
```

**Confidence: MEDIUM** -- Thresholds derived from multiple community sources (Polycount, CG Cookie, ThunderCloud Studio). No single authoritative standard exists. Thresholds should be configurable via parameters.

## Auto-Repair Pipeline

### Chained Repair Operations (bmesh)

The repair pipeline chains bmesh.ops operations in a specific order to avoid cascading failures:

```python
def handle_auto_repair(params: dict) -> dict:
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    report = {}

    # 1. Remove loose vertices (no edges)
    loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
    if loose_verts:
        bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
        report["removed_loose_verts"] = len(loose_verts)

    # 2. Remove loose edges (no faces)
    loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
    if loose_edges:
        bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        report["removed_loose_edges"] = len(loose_edges)

    # 3. Dissolve degenerate (zero-area faces, zero-length edges)
    result = bmesh.ops.dissolve_degenerate(bm, dist=0.0001, edges=bm.edges[:])
    report["dissolved_degenerate"] = len(result.get("region", []))

    # 4. Remove doubles (merge by distance)
    merge_dist = params.get("merge_distance", 0.0001)
    result = bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge_dist)
    report["merged_vertices"] = len(result.get("targetmap", {}))

    # 5. Recalculate normals (make consistent outward)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    report["normals_recalculated"] = True

    # 6. Fill holes (boundary edges)
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if boundary_edges:
        result = bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=params.get("max_hole_sides", 8))
        report["holes_filled"] = len(result.get("faces", []))

    # Write back
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()

    # Re-analyze to confirm repair
    report["post_repair_grade"] = _quick_grade(obj)
    return report
```

**Confidence: HIGH** -- All bmesh.ops functions verified against official Blender Python API docs. Order matters: remove loose first (prevents false doubles), dissolve degenerate (prevents fill errors), then merge, then normals, then fill.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UV unwrapping | Custom parameterization algorithm | xatlas 0.0.11 `parametrize()` or `Atlas` class | UV parameterization is a solved, hard problem. xatlas handles seam placement, chart optimization, and packing in one library. |
| Retopology | Custom quad remeshing from scratch | `bpy.ops.object.quadriflow_remesh()` | Quadriflow is built into Blender, handles target face count, and preserves sharp edges. Custom quad remesh would take months. |
| Non-manifold detection | Custom edge traversal algorithm | `bmesh.BMEdge.is_manifold` property | Built into bmesh at C level. Iterating edges and checking `.is_manifold` is O(n) and correct by definition. |
| Face normal recalculation | Custom winding-order algorithm | `bmesh.ops.recalc_face_normals()` | Handles connected components, boundary conditions, and non-manifold cases. Custom implementation would miss edge cases. |
| Boolean operations | Custom CSG implementation | `bpy.types.BooleanModifier` with EXACT solver | Blender's boolean is a mature implementation handling coplanar faces, non-manifold inputs, and material transfer. |
| Texel density calculation | Approximate per-face metric | Proper area-ratio formula (3D face area vs UV face area) | Must be mathematically correct for equalization to work. Formula: `TD = sqrt(uv_area / face_3d_area) * texture_size` |
| UV layout export | Custom image rendering | `bpy.ops.uv.export_layout()` | Built-in operator handles wireframe rendering, alpha, SVG/PNG output, and proper UV-to-pixel mapping. |

**Key insight:** The value-add for Phase 2 is in the INTEGRATION layer -- combining bmesh analysis with structured MCP responses, chaining repair operations intelligently, bridging xatlas with Blender's UV layers, and presenting results with visual verification. The individual operations already exist in Blender/xatlas.

## Common Pitfalls

### Pitfall 1: bmesh Not Written Back to Mesh (CRITICAL)

**What goes wrong:** Analysis or edits appear to succeed (bmesh reports correct data), but the Blender viewport shows no change. Subsequent operations read stale data.
**Why it happens:** bmesh is an in-memory copy of the mesh. Changes exist only in the bmesh object until `bm.to_mesh(obj.data)` is called.
**How to avoid:** Always call `bm.to_mesh(obj.data)` + `obj.data.update()` after any bmesh modification. For analysis-only operations, skip the write-back and just `bm.free()`.
**Warning signs:** "Auto-repair succeeded" but mesh still fails analysis. Before/after screenshots look identical.

### Pitfall 2: Sculpt Mode Context Requirements

**What goes wrong:** `bpy.ops.sculpt.mesh_filter()` raises `RuntimeError: Operator bpy.ops.sculpt.mesh_filter.poll() failed` when called from timer callback.
**Why it happens:** Sculpt operators require the active object to be in SCULPT mode, and a 3D viewport context.
**How to avoid:** Switch to sculpt mode first: `bpy.ops.object.mode_set(mode='SCULPT')`, apply filter, switch back to OBJECT mode. Wrap in context override. Consider using bmesh.ops.smooth_vert/smooth_laplacian_vert as alternatives that don't need sculpt mode.
**Warning signs:** Poll failures on sculpt operators. Mode assertion errors.

### Pitfall 3: Boolean Modifier on Non-Manifold Input

**What goes wrong:** Boolean operation produces garbage geometry (floating faces, inverted normals, holes) or crashes Blender.
**Why it happens:** The EXACT boolean solver assumes manifold, closed meshes. Non-manifold input produces undefined results.
**How to avoid:** Run auto-repair (MESH-02) before boolean operations. Validate both objects are manifold. Use `solver='EXACT'` (not FAST). Check face count after operation to detect failures.
**Warning signs:** Face count drops to near-zero. Result mesh has more non-manifold edges than inputs combined.

### Pitfall 4: xatlas Requires Triangulated Input

**What goes wrong:** xatlas produces distorted or incorrect UV coordinates when given n-gon or quad face indices.
**Why it happens:** xatlas expects triangle-only face arrays (Fx3 shape). Quads (Fx4) or mixed-polygon arrays cause index misalignment.
**How to avoid:** Triangulate the bmesh copy before extracting vertices/faces for xatlas: `bmesh.ops.triangulate(bm, faces=bm.faces[:])`. After xatlas produces UVs, map them back to the original (non-triangulated) mesh via the vmapping.
**Warning signs:** UV coordinates appear scrambled. xatlas returns fewer UV coordinates than expected.

### Pitfall 5: UV Layer Must Exist Before Writing UVs

**What goes wrong:** Attempting to access `bm.loops.layers.uv.active` returns None, causing AttributeError when writing xatlas results back.
**Why it happens:** New meshes (especially from AI generation tools like Tripo3D) often have no UV layer.
**How to avoid:** Always check and create UV layer if missing: `uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")`.
**Warning signs:** AttributeError on UV layer access. "NoneType has no attribute" errors.

### Pitfall 6: Quadriflow Remesh Crashes on Complex Meshes

**What goes wrong:** `bpy.ops.object.quadriflow_remesh()` crashes Blender (segfault) on meshes with extreme non-manifold geometry or very high face counts.
**Why it happens:** Known Blender bug (issue #124004). Quadriflow's C++ implementation doesn't handle all degenerate inputs gracefully.
**How to avoid:** Run auto-repair before retopology. For very high-poly meshes (>500k faces), decimate first with `bpy.ops.object.modifier_add(type='DECIMATE')` to reduce to <200k before quadriflow. Wrap in try/except to catch crashes gracefully.
**Warning signs:** Blender stops responding. No error output -- just silence and disconnect.

### Pitfall 7: UV Export Requires Edit Mode + UV Editor Context

**What goes wrong:** `bpy.ops.uv.export_layout()` fails with poll error.
**Why it happens:** UV operators require edit mode AND often a UV editor area context.
**How to avoid:** Switch to edit mode, select all faces, then use temp_override with a UV editor area if available. Alternative: render UV layout manually using bmesh UV data + Pillow (more reliable from timer context).
**Warning signs:** "No UV editor found" errors. Empty/black exported UV images.

## Code Examples

### Topology Analysis Handler (Complete)

```python
# Source: Blender bmesh API docs + custom grading research
# File: blender_addon/handlers/mesh_analysis.py

import bmesh
import bpy
import math


def handle_analyze_topology(params: dict) -> dict:
    """Full topology analysis with A-F grading (MESH-01)."""
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {name}")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    total_verts = len(bm.verts)
    total_edges = len(bm.edges)
    total_faces = len(bm.faces)

    # Non-manifold edges (edges not shared by exactly 2 faces)
    non_manifold_edges = [e for e in bm.edges if not e.is_manifold]

    # N-gons (faces with >4 vertices)
    ngons = [f for f in bm.faces if len(f.verts) > 4]

    # Triangles
    tris = [f for f in bm.faces if len(f.verts) == 3]

    # Quads
    quads = [f for f in bm.faces if len(f.verts) == 4]

    # Poles: vertices with != 4 edges (excluding boundary vertices)
    e_poles = [v for v in bm.verts if len(v.link_edges) == 3 and not v.is_boundary]
    n_poles = [v for v in bm.verts if len(v.link_edges) >= 5 and not v.is_boundary]

    # Loose geometry
    loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
    loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]

    # Boundary edges (not non-manifold, just open boundaries)
    boundary_edges = [e for e in bm.edges if e.is_boundary]

    # Edge flow: average face angle at edges (higher = harder edges)
    edge_angles = []
    for e in bm.edges:
        if len(e.link_faces) == 2:
            angle = e.link_faces[0].normal.angle(e.link_faces[1].normal)
            edge_angles.append(math.degrees(angle))

    bm.free()

    metrics = {
        "object_name": name,
        "vertex_count": total_verts,
        "edge_count": total_edges,
        "face_count": total_faces,
        "tri_count": len(tris),
        "quad_count": len(quads),
        "ngon_count": len(ngons),
        "ngon_percentage": round(len(ngons) / max(total_faces, 1) * 100, 1),
        "non_manifold_edges": len(non_manifold_edges),
        "boundary_edges": len(boundary_edges),
        "e_poles": len(e_poles),
        "n_poles": len(n_poles),
        "pole_count": len(e_poles) + len(n_poles),
        "loose_vertices": len(loose_verts),
        "loose_edges": len(loose_edges),
        "avg_edge_angle": round(sum(edge_angles) / max(len(edge_angles), 1), 1),
        "max_edge_angle": round(max(edge_angles) if edge_angles else 0, 1),
    }
    metrics["grade"] = _compute_grade(metrics)
    metrics["issues"] = _list_issues(metrics)
    return metrics


def _list_issues(m: dict) -> list[str]:
    """Generate human-readable issue list."""
    issues = []
    if m["non_manifold_edges"] > 0:
        issues.append(f"{m['non_manifold_edges']} non-manifold edges (will cause rendering artifacts)")
    if m["ngon_count"] > 0:
        issues.append(f"{m['ngon_count']} n-gons ({m['ngon_percentage']}% of faces)")
    if m["loose_vertices"] > 0:
        issues.append(f"{m['loose_vertices']} loose vertices")
    if m["loose_edges"] > 0:
        issues.append(f"{m['loose_edges']} loose edges (wire geometry)")
    if m["pole_count"] > m["vertex_count"] * 0.1:
        issues.append(f"{m['pole_count']} poles ({m['e_poles']} E-poles, {m['n_poles']} N-poles)")
    return issues
```

### xatlas UV Unwrapping Handler

```python
# Source: xatlas-python README + Blender integration issue #19
# File: blender_addon/handlers/uv_operations.py

import bmesh
import bpy
import numpy as np


def handle_unwrap_xatlas(params: dict) -> dict:
    """UV unwrap using xatlas library (UV-02)."""
    try:
        import xatlas
    except ImportError:
        raise RuntimeError(
            "xatlas not installed in Blender Python. "
            "Run: import subprocess, sys; "
            "subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'xatlas'])"
        )

    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {name}")

    mesh = obj.data

    # Extract geometry via numpy
    vert_count = len(mesh.vertices)
    poly_count = len(mesh.polygons)
    loop_count = len(mesh.loops)

    vertices = np.zeros(vert_count * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", vertices)
    vertices = vertices.reshape(-1, 3)

    normals = np.zeros(vert_count * 3, dtype=np.float32)
    mesh.vertices.foreach_get("normal", normals)
    normals = normals.reshape(-1, 3)

    # Get triangle indices (triangulate polygons)
    loop_indices = np.zeros(loop_count, dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_indices)

    # Build triangle list from polygons
    triangles = []
    for poly in mesh.polygons:
        verts = [loop_indices[li] for li in poly.loop_indices]
        # Fan triangulation for n-gons
        for i in range(1, len(verts) - 1):
            triangles.append([verts[0], verts[i], verts[i + 1]])
    faces = np.array(triangles, dtype=np.uint32)

    # Create atlas with options
    atlas = xatlas.Atlas()
    atlas.add_mesh(vertices, faces, normals)

    chart_options = xatlas.ChartOptions()
    pack_options = xatlas.PackOptions()

    # Apply user-configurable options
    if params.get("max_chart_area"):
        chart_options.max_chart_area = params["max_chart_area"]
    if params.get("normal_deviation_weight"):
        chart_options.normal_deviation_weight = params["normal_deviation_weight"]
    if params.get("max_iterations"):
        chart_options.max_iterations = params["max_iterations"]

    pack_options.padding = params.get("padding", 2)
    pack_options.resolution = params.get("resolution", 1024)
    pack_options.bilinear = params.get("bilinear", True)
    pack_options.rotate_charts = params.get("rotate_charts", True)

    atlas.generate(chart_options, pack_options)

    vmapping, indices, uvs = atlas[0]

    # Write UVs back to Blender mesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        uv_layer = bm.loops.layers.uv.new("UVMap")

    # Build vertex-to-UV mapping from xatlas output
    # vmapping[new_vert_idx] = original_vert_idx
    # uvs[new_vert_idx] = (u, v)
    vert_uv_map = {}
    for new_idx, orig_idx in enumerate(vmapping):
        orig_idx = int(orig_idx)
        if orig_idx not in vert_uv_map:
            vert_uv_map[orig_idx] = uvs[new_idx]

    # Apply UVs to bmesh loops
    for face in bm.faces:
        for loop in face.loops:
            vert_idx = loop.vert.index
            if vert_idx in vert_uv_map:
                loop[uv_layer].uv = tuple(vert_uv_map[vert_idx])

    bm.to_mesh(mesh)
    mesh.update()
    bm.free()

    return {
        "object_name": name,
        "atlas_width": atlas.width,
        "atlas_height": atlas.height,
        "chart_count": atlas.get_mesh_chart_count(0) if hasattr(atlas, 'get_mesh_chart_count') else -1,
        "utilization": atlas.get_utilization(0) if hasattr(atlas, 'get_utilization') else -1,
        "uv_layer": "UVMap",
    }
```

### UV Quality Analysis

```python
# Source: Texel density formula (standard CG), UV area calculation via mathutils
# File: blender_addon/handlers/uv_analysis.py

import bmesh
import bpy
import math
from mathutils import Vector


def handle_analyze_uv(params: dict) -> dict:
    """UV quality analysis: stretch, overlap, island count, texel density (UV-01)."""
    name = params.get("object_name")
    texture_size = params.get("texture_size", 1024)
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {name}")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        bm.free()
        return {"error": "No UV layer found", "has_uvs": False}

    # Per-face metrics
    stretch_values = []
    texel_densities = []
    total_3d_area = 0.0
    total_uv_area = 0.0

    for face in bm.faces:
        # 3D face area
        face_3d_area = face.calc_area()
        total_3d_area += face_3d_area

        # UV face area (2D polygon area via shoelace formula)
        uv_coords = [loop[uv_layer].uv.copy() for loop in face.loops]
        uv_area = _polygon_area_2d(uv_coords)
        total_uv_area += uv_area

        # Stretch: ratio of UV area to 3D area (1.0 = no distortion)
        if face_3d_area > 1e-8 and uv_area > 1e-8:
            stretch = uv_area / face_3d_area
            stretch_values.append(stretch)
        else:
            stretch_values.append(0.0)

        # Texel density: pixels per world unit
        if face_3d_area > 1e-8:
            td = math.sqrt(uv_area / face_3d_area) * texture_size
            texel_densities.append(td)

    # Island counting via connected UV components
    island_count = _count_uv_islands(bm, uv_layer)

    # Overlap detection
    overlap_count = _count_uv_overlaps(bm, uv_layer)

    # Seam edges
    seam_edges = sum(1 for e in bm.edges if e.seam)

    bm.free()

    # Compute statistics
    avg_td = sum(texel_densities) / max(len(texel_densities), 1)
    min_td = min(texel_densities) if texel_densities else 0
    max_td = max(texel_densities) if texel_densities else 0
    td_variance = (max_td - min_td) / max(avg_td, 1e-8)

    # Normalize stretch to deviation from median
    if stretch_values:
        median_stretch = sorted(stretch_values)[len(stretch_values) // 2]
        stretch_deviations = [abs(s - median_stretch) / max(median_stretch, 1e-8) for s in stretch_values]
        avg_stretch_deviation = sum(stretch_deviations) / len(stretch_deviations)
    else:
        avg_stretch_deviation = 0.0

    return {
        "object_name": name,
        "has_uvs": True,
        "island_count": island_count,
        "overlap_count": overlap_count,
        "seam_edge_count": seam_edges,
        "total_3d_area": round(total_3d_area, 4),
        "total_uv_area": round(total_uv_area, 6),
        "uv_coverage": round(total_uv_area, 4),  # 0-1 range in UV space
        "texel_density": {
            "average": round(avg_td, 1),
            "min": round(min_td, 1),
            "max": round(max_td, 1),
            "variance_ratio": round(td_variance, 2),
            "texture_size": texture_size,
        },
        "stretch": {
            "average_deviation": round(avg_stretch_deviation, 3),
            "faces_analyzed": len(stretch_values),
        },
    }


def _polygon_area_2d(coords: list) -> float:
    """Shoelace formula for 2D polygon area."""
    n = len(coords)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i].x * coords[j].y
        area -= coords[j].x * coords[i].y
    return abs(area) / 2.0


def _count_uv_islands(bm, uv_layer) -> int:
    """Count connected UV islands using flood fill."""
    visited = set()
    island_count = 0
    for face in bm.faces:
        if face.index in visited:
            continue
        # BFS from this face
        island_count += 1
        queue = [face]
        while queue:
            f = queue.pop()
            if f.index in visited:
                continue
            visited.add(f.index)
            for edge in f.edges:
                if edge.seam:
                    continue  # Seams break islands
                for linked_face in edge.link_faces:
                    if linked_face.index not in visited:
                        # Check UV connectivity (same UV coords at shared edge)
                        if _faces_share_uv_edge(f, linked_face, edge, uv_layer):
                            queue.append(linked_face)
    return island_count


def _faces_share_uv_edge(f1, f2, edge, uv_layer) -> bool:
    """Check if two faces share a UV-connected edge (same UV coords)."""
    # Get UV coords at shared vertices for each face
    uv1 = {}
    for loop in f1.loops:
        if loop.vert in edge.verts:
            uv1[loop.vert.index] = tuple(round(c, 6) for c in loop[uv_layer].uv)
    uv2 = {}
    for loop in f2.loops:
        if loop.vert in edge.verts:
            uv2[loop.vert.index] = tuple(round(c, 6) for c in loop[uv_layer].uv)
    # If same vertices have same UV coords, faces are UV-connected
    for vi in uv1:
        if vi in uv2 and uv1[vi] != uv2[vi]:
            return False
    return True
```

### UV Layout Export for Visual Verification

```python
# Source: bpy.ops.uv.export_layout docs
# File: blender_addon/handlers/uv_export.py

import bpy
import os
import tempfile
import uuid

from ._context import get_3d_context_override


def handle_export_uv_layout(params: dict) -> dict:
    """Export UV layout as PNG image for visual verification."""
    name = params.get("object_name")
    size = params.get("size", 1024)
    opacity = params.get("opacity", 0.25)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {name}")

    filepath = os.path.join(
        tempfile.gettempdir(),
        f"vb_uv_layout_{uuid.uuid4().hex[:8]}.png"
    )

    # Must be in edit mode with faces selected
    override = get_3d_context_override()
    if not override:
        raise RuntimeError("No 3D viewport for UV export")

    # Store current state
    old_active = bpy.context.view_layer.objects.active
    old_mode = obj.mode if obj == old_active else 'OBJECT'

    try:
        bpy.context.view_layer.objects.active = obj
        with bpy.context.temp_override(**override, active_object=obj):
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.export_layout(
                filepath=filepath,
                export_all=True,
                mode='PNG',
                size=(size, size),
                opacity=opacity,
            )
            bpy.ops.object.mode_set(mode='OBJECT')
    finally:
        if old_active:
            bpy.context.view_layer.objects.active = old_active

    return {
        "filepath": filepath,
        "size": size,
        "format": "png",
    }
```

### Retopology Handler

```python
# Source: bpy.ops.object.quadriflow_remesh API docs
# File: blender_addon/handlers/mesh_retopo.py

import bpy
from ._context import get_3d_context_override


def handle_retopologize(params: dict) -> dict:
    """Retopology using Quadriflow with target face count (MESH-07)."""
    name = params.get("object_name")
    target_faces = params.get("target_faces", 4000)
    preserve_sharp = params.get("preserve_sharp", True)
    preserve_boundary = params.get("preserve_boundary", True)
    smooth_normals = params.get("smooth_normals", True)
    seed = params.get("seed", 0)

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {name}")

    before_faces = len(obj.data.polygons)
    before_verts = len(obj.data.vertices)

    override = get_3d_context_override()
    if not override:
        raise RuntimeError("No 3D viewport for retopology")

    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        with bpy.context.temp_override(**override, active_object=obj):
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.quadriflow_remesh(
                use_mesh_symmetry=params.get("use_symmetry", False),
                use_preserve_sharp=preserve_sharp,
                use_preserve_boundary=preserve_boundary,
                preserve_attributes=False,
                smooth_normals=smooth_normals,
                mode='FACES',
                target_faces=target_faces,
                seed=seed,
            )
    except RuntimeError as e:
        if "canceled" in str(e).lower():
            raise RuntimeError(
                f"Quadriflow remesh failed on '{name}'. "
                "Try running auto_repair first, or reduce face count with decimate."
            )
        raise

    after_faces = len(obj.data.polygons)
    after_verts = len(obj.data.vertices)

    return {
        "object_name": obj.name,
        "before": {"vertices": before_verts, "faces": before_faces},
        "after": {"vertices": after_verts, "faces": after_faces},
        "target_faces": target_faces,
        "reduction_ratio": round(after_faces / max(before_faces, 1), 3),
        "preserve_sharp": preserve_sharp,
    }
```

## Sculpt Operations

### Approach: bmesh for Smooth, Operators for Others

For MESH-04, the sculpt operations divide into two categories:

**1. bmesh-native (no mode switching needed):**
- **Smooth:** `bmesh.ops.smooth_vert(bm, verts=selected, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)` -- simple Laplacian smooth
- **Smooth (volume-preserving):** `bmesh.ops.smooth_laplacian_vert(bm, verts=selected, lambda_factor=0.5, preserve_volume=True)`

**2. Operator-based (requires sculpt mode):**
- **Inflate:** `bpy.ops.sculpt.mesh_filter(type='INFLATE', strength=0.5, iteration_count=3)`
- **Flatten:** `bpy.ops.sculpt.mesh_filter(type='SURFACE_SMOOTH', strength=1.0)` (closest to flatten)
- **Crease/Sharpen:** `bpy.ops.sculpt.mesh_filter(type='SHARPEN', strength=0.5, sharpen_smooth_ratio=0.35)`

**Sculpt mode workflow from timer:**
```python
def handle_sculpt(params: dict) -> dict:
    name = params.get("object_name")
    operation = params.get("operation")  # smooth, inflate, flatten, crease
    strength = params.get("strength", 0.5)
    iterations = params.get("iterations", 3)

    obj = bpy.data.objects.get(name)

    # For smooth: use bmesh (no mode switch needed)
    if operation == "smooth":
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        verts = [v for v in bm.verts if v.select] or bm.verts[:]
        bmesh.ops.smooth_vert(
            bm, verts=verts, factor=strength,
            use_axis_x=True, use_axis_y=True, use_axis_z=True
        )
        bm.to_mesh(obj.data)
        obj.data.update()
        bm.free()
        return {"operation": "smooth", "verts_affected": len(verts)}

    # For others: sculpt mode required
    override = get_3d_context_override()
    if not override:
        raise RuntimeError("No 3D viewport for sculpt operation")

    op_map = {
        "inflate": ("INFLATE", {}),
        "flatten": ("SURFACE_SMOOTH", {"surface_smooth_shape_preservation": 0.5}),
        "crease": ("SHARPEN", {"sharpen_smooth_ratio": 0.35}),
    }
    filter_type, extra_params = op_map.get(operation, ("SMOOTH", {}))

    old_mode = obj.mode
    bpy.context.view_layer.objects.active = obj
    with bpy.context.temp_override(**override, active_object=obj):
        bpy.ops.object.mode_set(mode='SCULPT')
        bpy.ops.sculpt.mesh_filter(
            type=filter_type, strength=strength,
            iteration_count=iterations, **extra_params
        )
        bpy.ops.object.mode_set(mode=old_mode)

    return {"operation": operation, "strength": strength, "iterations": iterations}
```

**Confidence: MEDIUM** -- bmesh smooth operations are well-documented. Sculpt mesh_filter from timer context needs testing; the mode-switch + context-override pattern may have timing issues with rapid calls.

## xatlas Integration Details

### Installation Strategy

xatlas must be installed into Blender's bundled Python, not the system Python or the MCP server's venv. Two approaches:

**Approach A: Pre-install via handler command (recommended):**
Add a handler command `ensure_xatlas` that checks import and installs if missing:
```python
def handle_ensure_xatlas(params: dict) -> dict:
    try:
        import xatlas
        return {"installed": True, "version": xatlas.__version__}
    except ImportError:
        import subprocess
        import sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'xatlas==0.0.11'])
        import xatlas
        return {"installed": True, "version": xatlas.__version__, "just_installed": True}
```

**Approach B: Document as setup step**
User runs the install command once in Blender's Python console.

**Recommendation:** Approach A -- auto-install on first use. The handler runs inside Blender's Python, so `sys.executable` correctly points to Blender's bundled Python.

### xatlas ChartOptions (Configurable Quality)

| Parameter | Default | Use Case |
|-----------|---------|----------|
| `max_chart_area` | 0 (no limit) | Limit chart size for even texel distribution |
| `max_iterations` | 1 | Higher = better charts, slower. Use 4 for production. |
| `normal_deviation_weight` | 2.0 | Higher = more charts at normal discontinuities. Good for hard-surface. |
| `normal_seam_weight` | 4.0 | Respect existing seams. >1000 = fully respect. |
| `use_input_mesh_uvs` | false | Use existing UVs as starting point (for re-packing). |

### xatlas PackOptions (Island Packing)

| Parameter | Default | Use Case |
|-----------|---------|----------|
| `padding` | 0 | Set to 2-4 for mipmap bleeding prevention |
| `resolution` | 0 | Target atlas resolution. 1024 for game assets. |
| `texels_per_unit` | 0 (auto) | Control texel density. 0 = auto-fit resolution. |
| `bilinear` | true | Leave space for bilinear filtering |
| `rotate_charts` | true | Rotation improves packing efficiency by ~15-20% |
| `brute_force` | false | Best packing quality, slower. Use for final assets. |

**Confidence: HIGH** -- ChartOptions/PackOptions verified against xatlas.h source header in jpcy/xatlas repository.

## Lightmap UV Generation (UV-04)

Unity requires a second UV channel (UV2) for lightmapping. The approach:

1. **Create UV2 layer in bmesh:** `uv2_layer = bm.loops.layers.uv.new("UV2")`
2. **Run xatlas on UV2** with specific lightmap options:
   - `pack_options.padding = 4` (lightmap bleeding requires more padding)
   - `pack_options.bilinear = True`
   - `chart_options.max_chart_area = 0` (no limit -- want minimal seams for lightmaps)
   - No overlap allowed (xatlas guarantees this)
3. **Write results to UV2 layer** (not UV1)
4. Unity import settings: ensure "Generate Lightmap UVs" is OFF (we provide them)

## Texel Density Equalization (UV-05)

**Formula:** `texel_density = sqrt(uv_area / face_3d_area) * texture_size`

**Equalization algorithm:**
1. Calculate per-island texel density (average of all faces in island)
2. Determine target density (median of all islands, or user-specified)
3. For each island: `scale_factor = target_density / island_density`
4. Scale island UVs around island center by `scale_factor`
5. Re-pack islands to fit within 0-1 UV space

This is essentially what `bpy.ops.uv.average_islands_scale()` does, but our version provides the metrics before/after and allows a specific target density.

## Game-Readiness Check (MESH-08)

Composite validation that combines multiple analyses:

```python
def handle_check_game_ready(params: dict) -> dict:
    """Full game-readiness check combining topology + UV + material + naming (MESH-08)."""
    name = params.get("object_name")
    poly_budget = params.get("poly_budget", 50000)  # Default 50k tris
    target_platform = params.get("platform", "pc")  # pc, mobile, console

    obj = bpy.data.objects.get(name)
    checks = {}
    passed = True

    # 1. Topology grade
    topo = handle_analyze_topology({"object_name": name})
    checks["topology"] = {
        "grade": topo["grade"],
        "pass": topo["grade"] in ("A", "B", "C"),
        "issues": topo["issues"],
    }
    if not checks["topology"]["pass"]:
        passed = False

    # 2. Poly budget
    tri_count = topo["tri_count"] + topo["quad_count"] * 2 + topo["ngon_count"] * 3
    checks["poly_budget"] = {
        "triangle_count": tri_count,
        "budget": poly_budget,
        "pass": tri_count <= poly_budget,
        "utilization": round(tri_count / poly_budget * 100, 1),
    }
    if not checks["poly_budget"]["pass"]:
        passed = False

    # 3. UV check
    uv_metrics = handle_analyze_uv({"object_name": name})
    checks["uv"] = {
        "has_uvs": uv_metrics.get("has_uvs", False),
        "overlap_count": uv_metrics.get("overlap_count", -1),
        "island_count": uv_metrics.get("island_count", 0),
        "pass": uv_metrics.get("has_uvs", False) and uv_metrics.get("overlap_count", 1) == 0,
    }
    if not checks["uv"]["pass"]:
        passed = False

    # 4. Materials
    mat_count = len(obj.data.materials)
    checks["materials"] = {
        "count": mat_count,
        "has_materials": mat_count > 0,
        "pass": mat_count > 0,
    }
    if not checks["materials"]["pass"]:
        passed = False

    # 5. Naming convention
    valid_name = not name.startswith("Cube") and not name.startswith("Sphere")
    checks["naming"] = {
        "name": name,
        "pass": valid_name,
        "suggestion": "Use descriptive name (e.g., SM_Dragon_Body)" if not valid_name else None,
    }

    # 6. Scale/transform
    checks["transform"] = {
        "location": list(obj.location),
        "rotation": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "has_applied_transforms": (
            all(abs(v) < 0.001 for v in obj.location) and
            all(abs(v) < 0.001 for v in obj.rotation_euler) and
            all(abs(v - 1.0) < 0.001 for v in obj.scale)
        ),
        "pass": True,  # Warn but don't fail
    }

    return {
        "object_name": name,
        "game_ready": passed,
        "checks": checks,
        "summary": "PASS - Game ready" if passed else "FAIL - See checks for issues",
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual UV unwrap in Blender | xatlas automated parameterization | xatlas-python 0.0.11 (2025) | Consistent, repeatable UV results from code |
| Voxel remesh for retopology | Quadriflow with target face count | Built into Blender 2.83+ | Preserves sharp edges, produces quads |
| Text-only mesh validation | Structured grading + visual overlay | This phase | Claude can actually understand mesh quality |
| Per-face UV operations | Island-aware UV manipulation | bmesh UV island detection | Proper texel density equalization |
| Manual game-readiness checklist | Automated composite check | This phase | Consistent quality gate for all assets |

**Deprecated/outdated:**
- `bpy.ops.mesh.remove_doubles()`: Renamed to `bpy.ops.mesh.merge_by_distance()` in Blender 2.82+. The bmesh equivalent `bmesh.ops.remove_doubles()` retains the old name.
- `bgl` module for UV visualization: Removed in Blender 4.0. Use `gpu` module or Pillow-based image composition instead.
- Blender's built-in UV packing: Significantly improved in Blender 4.2+ but still inferior to xatlas for complex meshes.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (from Phase 1) |
| Config file | `Tools/mcp-toolkit/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd Tools/mcp-toolkit && uv run pytest tests/ -x --timeout=30` |
| Full suite command | `cd Tools/mcp-toolkit && uv run pytest tests/ --timeout=60` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MESH-01 | Topology analysis returns correct metrics and grade | unit | `uv run pytest tests/test_mesh_analysis.py::test_topology_grading -x` | Wave 0 |
| MESH-02 | Auto-repair removes doubles, fixes normals, fills holes | unit | `uv run pytest tests/test_mesh_repair.py::test_auto_repair_pipeline -x` | Wave 0 |
| MESH-03 | Selection by material/vertex group/normal returns correct geometry | unit | `uv run pytest tests/test_mesh_editing.py::test_selection_engine -x` | Wave 0 |
| MESH-04 | Sculpt smooth modifies vertex positions | unit | `uv run pytest tests/test_mesh_editing.py::test_sculpt_smooth -x` | Wave 0 |
| MESH-05 | Boolean union/difference/intersect produces valid mesh | integration | `uv run pytest tests/test_mesh_editing.py::test_boolean_ops -x` | Wave 0 |
| MESH-06 | Extrude/inset/mirror produce expected geometry changes | unit | `uv run pytest tests/test_mesh_editing.py::test_edit_ops -x` | Wave 0 |
| MESH-07 | Retopology hits target face count within 20% tolerance | integration | `uv run pytest tests/test_mesh_retopo.py -x` | Wave 0 |
| MESH-08 | Game-readiness check returns structured pass/fail with all sub-checks | unit | `uv run pytest tests/test_mesh_analysis.py::test_game_readiness -x` | Wave 0 |
| UV-01 | UV analysis returns island count, stretch, density metrics | unit | `uv run pytest tests/test_uv_analysis.py -x` | Wave 0 |
| UV-02 | xatlas unwrap produces valid UVs with no overlap | integration | `uv run pytest tests/test_uv_operations.py::test_xatlas_unwrap -x` | Wave 0 |
| UV-03 | Pack islands fits all islands within 0-1 UV space | integration | `uv run pytest tests/test_uv_operations.py::test_pack_islands -x` | Wave 0 |
| UV-04 | Lightmap UV creates UV2 layer with no overlap | integration | `uv run pytest tests/test_uv_operations.py::test_lightmap_uv -x` | Wave 0 |
| UV-05 | Density equalization brings variance ratio below threshold | integration | `uv run pytest tests/test_uv_operations.py::test_equalize_density -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && uv run pytest tests/test_mesh_analysis.py tests/test_mesh_repair.py tests/test_uv_analysis.py -x --timeout=30`
- **Per wave merge:** `cd Tools/mcp-toolkit && uv run pytest tests/ --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mesh_analysis.py` -- covers MESH-01, MESH-08 (topology grading, game-readiness)
- [ ] `tests/test_mesh_repair.py` -- covers MESH-02 (auto-repair pipeline)
- [ ] `tests/test_mesh_editing.py` -- covers MESH-03, MESH-04, MESH-05, MESH-06 (selection, sculpt, boolean, edit ops)
- [ ] `tests/test_mesh_retopo.py` -- covers MESH-07 (retopology)
- [ ] `tests/test_uv_analysis.py` -- covers UV-01 (UV quality metrics)
- [ ] `tests/test_uv_operations.py` -- covers UV-02, UV-03, UV-04, UV-05 (xatlas, packing, lightmap, density)

**Note:** Tests that require a running Blender instance (integration tests) must be marked with `@pytest.mark.blender` and skipped in CI. Unit tests can mock bmesh operations on synthetic mesh data.

## Open Questions

1. **xatlas vertex mapping back to non-triangulated mesh**
   - What we know: xatlas returns vmapping (new->original vertex index) and uvs for a triangulated mesh. The original mesh may have quads and n-gons.
   - What's unclear: The mapping from xatlas triangulated output back to the original polygon loops is non-trivial when faces have been fan-triangulated. The vmapping maps vertices, not loops.
   - Recommendation: Store a tri-to-original-face mapping during triangulation. For each original face loop, find the corresponding xatlas UV by matching the vertex index via vmapping. Multiple xatlas UVs may map to the same original vertex (at seams) -- use the one from the correct triangle.

2. **Sculpt mesh_filter from timer callback reliability**
   - What we know: The operator requires sculpt mode. Mode switching works with temp_override. The mesh_filter operator uses mouse-relative interaction internally.
   - What's unclear: The `start_mouse` parameter suggests the operator expects mouse input. Calling it programmatically with default `start_mouse=(0,0)` may produce unexpected results.
   - Recommendation: Test in Blender first. If mesh_filter is unreliable, implement smooth/inflate/flatten purely through bmesh vertex manipulation (mathematically straightforward). Mark sculpt operations as "best effort" with fallback.

3. **UV overlap detection performance**
   - What we know: Naive 2D polygon intersection is O(n^2) for n faces. A mesh with 50k faces would require 2.5 billion comparisons.
   - What's unclear: Whether Blender's built-in overlap detection (`bpy.ops.uv.select_overlap`) can be used to count overlaps faster.
   - Recommendation: Use a spatial acceleration structure (2D grid hash or R-tree) for overlap detection. For meshes >10k faces, use approximate sampling (random 10% of faces) and extrapolate. Flag as estimate in response.

4. **Blender version-specific API differences**
   - What we know: The project targets Blender 3.6+ (per CLAUDE.md constraint: "Blender version: 3.6+ (Rigify required)").
   - What's unclear: Whether `bpy.context.temp_override` (introduced in 3.2) works identically across 3.6, 4.x, and 5.x for all the operators we need.
   - Recommendation: Add version check in handlers that use temp_override. Test on Blender 4.2+ (likely user's version). Document minimum Blender version in handler docstrings.

## Sources

### Primary (HIGH confidence)
- [Blender bmesh API - bmesh.html](https://docs.blender.org/api/current/bmesh.html) -- bmesh module overview, layer access, vertex/edge/face types
- [Blender bmesh.ops API](https://docs.blender.org/api/current/bmesh.ops.html) -- remove_doubles, dissolve_degenerate, recalc_face_normals, holes_fill, smooth_vert, smooth_laplacian_vert, extrude_face_region, mirror, bisect_plane
- [Blender bmesh.types](https://docs.blender.org/api/current/bmesh.types.html) -- BMVert, BMEdge, BMFace properties (is_manifold, is_boundary, link_edges, link_faces, material_index)
- [Blender bpy.ops.mesh](https://docs.blender.org/api/current/bpy.ops.mesh.html) -- select_non_manifold, select_face_by_sides, normals_make_consistent
- [Blender bpy.ops.uv](https://docs.blender.org/api/current/bpy.ops.uv.html) -- export_layout, pack_islands, smart_project, average_islands_scale
- [Blender bpy.ops.sculpt](https://docs.blender.org/api/current/bpy.ops.sculpt.html) -- mesh_filter (SMOOTH, INFLATE, SURFACE_SMOOTH, SHARPEN)
- [Blender BooleanModifier](https://docs.blender.org/api/current/bpy.types.BooleanModifier.html) -- operation modes, solver types
- [Blender RemeshModifier](https://docs.blender.org/api/current/bpy.types.RemeshModifier.html) -- voxel_size, mode options
- [xatlas-python GitHub](https://github.com/mworchel/xatlas-python) -- Python bindings API, parametrize(), Atlas class
- [xatlas PyPI](https://pypi.org/project/xatlas/) -- v0.0.11, Python 3.8-3.13, MIT license, wheels for Windows/macOS/Linux
- [xatlas C++ header (jpcy/xatlas)](https://github.com/jpcy/xatlas/blob/master/source/xatlas/xatlas.h) -- ChartOptions, PackOptions struct definitions with defaults

### Secondary (MEDIUM confidence)
- [Blender quadriflow_remesh](https://docs.blender.org/api/2.83/bpy.ops.object.html) -- target_faces, use_preserve_sharp, use_preserve_boundary parameters
- [xatlas-python Blender integration (issue #19)](https://github.com/mworchel/xatlas-python/issues/19) -- Installing xatlas in Blender Python, numpy array workflow
- [Texel Density Checker addon](https://github.com/mrven/Blender-Texel-Density-Checker) -- Reference for texel density calculation approach
- [Blender bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html) -- Timer pattern for main-thread dispatch (from Phase 1 research)
- [Polycount Topology Wiki](http://wiki.polycount.com/wiki/Topology) -- Poles, edge flow, quad dominance standards

### Tertiary (LOW confidence)
- Topology grading thresholds (A-F): Synthesized from multiple community sources (Polycount, CG Cookie, ThunderCloud Studio). No single authoritative standard. Should be configurable.
- Sculpt mesh_filter reliability from timer: Based on API docs, but untested in timer-callback context. The `start_mouse` parameter concern needs empirical validation.
- UV overlap detection performance: Algorithmic complexity analysis is theoretical. Actual performance depends on Blender's Python overhead and mesh complexity.

## Metadata

**Confidence breakdown:**
- Standard stack (bmesh, bpy.ops): HIGH -- Official Blender API, well-documented, already used in Phase 1
- Standard stack (xatlas): HIGH -- Verified on PyPI (v0.0.11, July 2025), wheels for all platforms, MIT license
- Architecture (two new compound tools): HIGH -- Follows established Phase 1 compound tool pattern
- Topology analysis: HIGH -- bmesh properties (is_manifold, link_edges) are C-level, reliable
- Auto-repair pipeline: HIGH -- All bmesh.ops functions verified against official docs
- Grading thresholds: MEDIUM -- Community-sourced, not standardized. Should be configurable.
- Sculpt operations: MEDIUM -- bmesh smooth is reliable; sculpt mesh_filter from timer needs testing
- xatlas integration: MEDIUM -- API verified, Blender integration demonstrated in issue #19, but vertex mapping back to quads needs careful implementation
- UV quality analysis: MEDIUM -- Algorithms are standard (shoelace, BFS), but overlap detection performance at scale is uncertain
- Boolean operations: HIGH -- BooleanModifier API well-documented, EXACT solver recommended

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain -- Blender bmesh API and xatlas are not fast-moving)
