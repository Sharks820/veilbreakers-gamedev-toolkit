"""Silhouette-preserving LOD chain generation using Blender's Decimate modifier.

Generates LOD0-LOD3 objects with decreasing face counts from a source mesh.
Silhouette edges and boundary edges are detected via edge-angle analysis and
protected through a vertex-group-weighted Decimate modifier in COLLAPSE mode.
"""

from __future__ import annotations

import math

import bpy

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_lod_ratios(ratios: list[float]) -> bool:
    """Validate that LOD ratios are in descending order and within [0, 1].

    Args:
        ratios: List of decimation ratios (1.0 = full detail, 0.1 = 10%).

    Returns:
        True if valid.

    Raises:
        ValueError: If ratios are not descending or out of range.
    """
    if not ratios:
        raise ValueError("At least one LOD ratio is required")

    for r in ratios:
        if not (0.0 < r <= 1.0):
            raise ValueError(
                f"LOD ratio must be in (0, 1.0], got {r}"
            )

    for i in range(1, len(ratios)):
        if ratios[i] >= ratios[i - 1]:
            raise ValueError(
                f"LOD ratios must be strictly descending: "
                f"ratio[{i}]={ratios[i]} >= ratio[{i-1}]={ratios[i-1]}"
            )

    return True


def _build_lod_name(base_name: str, lod_level: int) -> str:
    """Build LOD object name following {name}_LOD{i} convention.

    Args:
        base_name: Original object name.
        lod_level: LOD level index (0, 1, 2, ...).

    Returns:
        Name string like "Barrel_LOD0".
    """
    return f"{base_name}_LOD{lod_level}"


# ---------------------------------------------------------------------------
# Silhouette importance helpers (bpy-dependent)
# ---------------------------------------------------------------------------


def _compute_silhouette_vertex_group(
    mesh_obj: bpy.types.Object,
    vgroup_name: str = "_lod_silhouette",
) -> str:
    """Compute silhouette importance per vertex and store in a vertex group.

    Vertices on boundary edges (only one adjacent face) or on sharp-angle
    edges (adjacent face normals diverge significantly) receive HIGH weight
    (1.0 = preserve).  Interior vertices on smooth surfaces receive LOW
    weight (0.0 = expendable).

    The Decimate modifier's ``vertex_group_factor`` inverts this so that
    low-weight vertices are decimated first, preserving the silhouette.

    Args:
        mesh_obj: A Blender mesh object (must be type 'MESH').
        vgroup_name: Name for the vertex group to create/overwrite.

    Returns:
        The vertex group name (same as *vgroup_name*).
    """
    mesh = mesh_obj.data

    # Ensure mesh has calculated normals and edge data (removed in Blender 4.1+)
    if hasattr(mesh, "calc_normals_split"):
        mesh.calc_normals_split()

    num_verts = len(mesh.vertices)

    # Per-vertex importance accumulator
    importance = [0.0] * num_verts

    # Build edge -> polygon adjacency via vertex-pair keys
    edge_pair_polys: dict[tuple[int, int], list[int]] = {}
    for pi, poly in enumerate(mesh.polygons):
        for ek in poly.edge_keys:
            key = (min(ek[0], ek[1]), max(ek[0], ek[1]))
            if key not in edge_pair_polys:
                edge_pair_polys[key] = []
            edge_pair_polys[key].append(pi)

    # Precompute polygon normals
    poly_normals = [(p.normal.x, p.normal.y, p.normal.z) for p in mesh.polygons]

    # Silhouette detection: edges where adjacent faces have large angle between normals
    silhouette_angle_threshold = math.cos(math.radians(40.0))  # ~40 deg = silhouette

    for (va, vb), adj_polys in edge_pair_polys.items():
        edge_importance = 0.0

        if len(adj_polys) == 1:
            # Boundary edge: always part of the silhouette
            edge_importance = 1.0
        elif len(adj_polys) >= 2:
            # Check angle between adjacent face normals
            n0 = poly_normals[adj_polys[0]]
            n1 = poly_normals[adj_polys[1]]
            dot = n0[0] * n1[0] + n0[1] * n1[1] + n0[2] * n1[2]
            dot = max(-1.0, min(1.0, dot))

            if dot < silhouette_angle_threshold:
                # Large angle: silhouette-important edge
                # Scale importance by how sharp the angle is
                edge_importance = 1.0 - max(0.0, dot)

        if edge_importance > 0.0:
            # Propagate to both edge vertices (take max across all edges)
            importance[va] = max(importance[va], edge_importance)
            importance[vb] = max(importance[vb], edge_importance)

    # Also mark vertices on mesh boundary loops (border edges)
    for edge in mesh.edges:
        if edge.use_edge_sharp:
            importance[edge.vertices[0]] = max(importance[edge.vertices[0]], 0.8)
            importance[edge.vertices[1]] = max(importance[edge.vertices[1]], 0.8)

    # Create or overwrite the vertex group
    vgroup = mesh_obj.vertex_groups.get(vgroup_name)
    if vgroup is not None:
        mesh_obj.vertex_groups.remove(vgroup)
    vgroup = mesh_obj.vertex_groups.new(name=vgroup_name)

    for vi in range(num_verts):
        vgroup.add([vi], importance[vi], "REPLACE")

    return vgroup_name


def _detect_symmetry(mesh_obj: bpy.types.Object) -> bool:
    """Heuristic check for mesh symmetry along the X axis.

    Samples up to 200 vertices; if >80% have a mirrored counterpart
    within tolerance, the mesh is considered symmetric.
    """
    mesh = mesh_obj.data
    verts = mesh.vertices
    num_verts = len(verts)
    if num_verts < 8:
        return False

    sample_count = min(200, num_verts)
    step = max(1, num_verts // sample_count)
    tolerance = 0.001

    mirrored = 0
    checked = 0
    for i in range(0, num_verts, step):
        co = verts[i].co
        if abs(co.x) < tolerance:
            mirrored += 1
            checked += 1
            continue
        # Look for a mirrored vertex
        mirror_x = -co.x
        found = False
        for j in range(num_verts):
            oco = verts[j].co
            if (
                abs(oco.x - mirror_x) < tolerance
                and abs(oco.y - co.y) < tolerance
                and abs(oco.z - co.z) < tolerance
            ):
                found = True
                break
        if found:
            mirrored += 1
        checked += 1

    return checked > 0 and (mirrored / checked) > 0.8


# ---------------------------------------------------------------------------
# Blender handler
# ---------------------------------------------------------------------------


def handle_generate_lods(params: dict) -> dict:
    """Generate LOD chain using silhouette-preserving Decimate modifier.

    Computes per-vertex silhouette importance from edge-angle analysis,
    stores it in a vertex group, and uses ``vertex_group_factor`` on the
    Decimate COLLAPSE modifier so that interior/smooth-surface vertices
    are decimated first while boundary and silhouette edges are preserved.

    Params:
        object_name (str): Name of the source mesh object.
        ratios (list[float]): Decimation ratios per LOD level.
            Default: [1.0, 0.5, 0.25, 0.1] for LOD0-LOD3.
        preserve_silhouette (bool): Enable silhouette-preserving decimation.
            Default: True.
        use_symmetry (bool | None): Force symmetry on/off.  None = auto-detect.
            Default: None (auto).

    Returns:
        Dict with source, lod_count, silhouette_preserved, symmetry_used,
        and lods list containing per-LOD info.
    """
    object_name = params["object_name"]
    ratios = params.get("ratios", [1.0, 0.5, 0.25, 0.1])
    preserve_silhouette = params.get("preserve_silhouette", True)
    use_symmetry_param = params.get("use_symmetry", None)

    _validate_lod_ratios(ratios)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(
            f"Object '{object_name}' is type '{obj.type}', expected 'MESH'"
        )

    # Determine symmetry setting
    if use_symmetry_param is not None:
        use_symmetry = bool(use_symmetry_param)
    else:
        use_symmetry = _detect_symmetry(obj)

    # Compute silhouette vertex group on the source mesh (LOD0)
    vgroup_name = None
    if preserve_silhouette:
        vgroup_name = _compute_silhouette_vertex_group(obj)

    lods: list[dict] = []
    source_faces = len(obj.data.polygons)

    for i, ratio in enumerate(ratios):
        lod_name = _build_lod_name(object_name, i)

        if i == 0:
            # LOD0: rename original, record face count
            obj.name = lod_name
            obj.data.name = lod_name
            lods.append({
                "name": lod_name,
                "lod_level": i,
                "ratio": ratio,
                "face_count": source_faces,
                "reduction_pct": 0.0,
            })
        else:
            # Duplicate the LOD0 object for decimation
            lod0 = bpy.data.objects.get(_build_lod_name(object_name, 0))
            new_mesh = lod0.data.copy()
            new_obj = lod0.copy()
            new_obj.data = new_mesh
            new_obj.name = lod_name
            new_obj.data.name = lod_name

            # Link to same collection as source
            for col in lod0.users_collection:
                col.objects.link(new_obj)

            # Re-create the silhouette vertex group on the duplicate
            dup_vgroup_name = None
            if preserve_silhouette and vgroup_name:
                dup_vgroup_name = _compute_silhouette_vertex_group(
                    new_obj, vgroup_name,
                )

            # Add Decimate modifier with silhouette preservation
            mod = new_obj.modifiers.new(name="Decimate_LOD", type="DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = ratio
            mod.use_collapse_triangulate = True

            if use_symmetry:
                mod.use_symmetry = True

            # Wire vertex group: factor < 0 means high-weight verts are
            # PRESERVED (decimation removes low-weight verts first).
            # vertex_group_factor of 0.0 means the group has no effect;
            # 1.0 means full influence. We invert so importance=1.0 vertices
            # are protected from collapse.
            if dup_vgroup_name:
                mod.vertex_group = dup_vgroup_name
                # Invert: vertex_group weight 1.0 = preserve (don't decimate)
                mod.invert_vertex_group = True
                # Factor controls how strongly the group influences decimation
                # Higher = silhouette edges more strongly preserved
                mod.vertex_group_factor = 1.0

            # Apply modifier via operator with context override
            ctx = get_3d_context_override()
            if ctx:
                with bpy.context.temp_override(**ctx, object=new_obj):
                    bpy.ops.object.modifier_apply(modifier=mod.name)
            else:
                # Fallback: try without override
                with bpy.context.temp_override(object=new_obj):
                    bpy.ops.object.modifier_apply(modifier=mod.name)

            # Clean up the helper vertex group after modifier is applied
            if dup_vgroup_name:
                cleanup_vg = new_obj.vertex_groups.get(dup_vgroup_name)
                if cleanup_vg:
                    new_obj.vertex_groups.remove(cleanup_vg)

            face_count = len(new_obj.data.polygons)
            reduction = (
                round((1.0 - face_count / source_faces) * 100, 1)
                if source_faces > 0
                else 0.0
            )

            lods.append({
                "name": lod_name,
                "lod_level": i,
                "ratio": ratio,
                "face_count": face_count,
                "reduction_pct": reduction,
            })

    # Clean up the helper vertex group from LOD0
    if vgroup_name:
        cleanup_vg = obj.vertex_groups.get(vgroup_name)
        if cleanup_vg:
            obj.vertex_groups.remove(cleanup_vg)

    # EXP-002: Create a Unity LODGroup parent empty so Unity's FBX importer
    # can automatically configure the LODGroup component.
    # The empty is named "<BaseName>_LODGroup" and each LOD mesh is re-parented to it.
    # Custom property "unity_lod_group" = True signals the Unity import script.
    base_name = object_name  # may have been renamed to LOD0 already; use original
    lod_group_name = f"{base_name}_LODGroup"

    # Remove existing group empty if regenerating
    existing_group = bpy.data.objects.get(lod_group_name)
    if existing_group:
        bpy.data.objects.remove(existing_group, do_unlink=True)

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    group_empty = bpy.context.active_object
    group_empty.name = lod_group_name
    group_empty["unity_lod_group"] = True
    group_empty["lod_count"] = len(lods)

    # Collect LOD objects and re-parent them under the group empty
    for lod_info in lods:
        lod_obj = bpy.data.objects.get(lod_info["name"])
        if lod_obj is None:
            continue
        # Store LOD screen-size transition thresholds as custom props
        # Unity reads these during FBX post-import via the import script
        lod_obj["unity_lod_level"] = lod_info["lod_level"]
        lod_obj["unity_lod_ratio"] = lod_info["ratio"]

        # Re-parent to group empty, keeping world transform
        saved_matrix = lod_obj.matrix_world.copy()
        lod_obj.parent = group_empty
        lod_obj.matrix_world = saved_matrix

    # Place group empty in the same collections as the first LOD
    lod0_obj = bpy.data.objects.get(lods[0]["name"]) if lods else None
    if lod0_obj:
        for col in lod0_obj.users_collection:
            if group_empty.name not in col.objects:
                col.objects.link(group_empty)
        # Ensure group is not in default scene collection twice
        scene_col = bpy.context.scene.collection
        if group_empty.name in scene_col.objects and lod0_obj.users_collection:
            scene_col.objects.unlink(group_empty)

    return {
        "source": object_name,
        "lod_count": len(lods),
        "lod_group": lod_group_name,
        "silhouette_preserved": preserve_silhouette,
        "symmetry_used": use_symmetry,
        "lods": lods,
        "next_steps": [
            f"Import {lod_group_name}_LOD*.fbx into Unity",
            "Unity will auto-detect LODGroup from parent empty naming convention",
        ],
    }
