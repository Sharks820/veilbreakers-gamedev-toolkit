"""Geometry Nodes exposure, per-face instance scattering, and particle-to-mesh conversion.

Addresses gaps #73, #74, #78 — Blender's modern procedural system via MCP.

Pure-logic functions (no bpy):
  - compute_face_scatter_positions: Per-face instance scatter with density/rotation/scale
  - compute_hair_card_mesh: Convert hair strand points to flat card mesh geometry
  - generate_scatter_preset_code: GN scatter-on-surface Python code generator
  - generate_boolean_preset_code: GN boolean operations Python code generator
  - generate_array_curve_preset_code: GN instance-along-curve Python code generator
  - generate_vertex_displacement_code: GN noise vertex displacement Python code generator

bpy-dependent handlers (run inside Blender):
  - handle_geometry_nodes: Create/modify/query Geometry Nodes trees
  - handle_face_scatter: Scatter detail meshes on faces via GN or pure logic
  - handle_particle_to_mesh: Convert particle systems to exportable mesh geometry
"""

from __future__ import annotations

import math
import random
import textwrap
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
MeshSpec = dict[str, Any]

# ---------------------------------------------------------------------------
# Valid Geometry Node types (Blender 3.x / 4.x)
# ---------------------------------------------------------------------------
VALID_GN_NODE_TYPES: frozenset[str] = frozenset({
    # Geometry
    "GeometryNodeMeshPrimitiveCube",
    "GeometryNodeMeshPrimitiveCylinder",
    "GeometryNodeMeshPrimitiveCone",
    "GeometryNodeMeshPrimitiveCircle",
    "GeometryNodeMeshPrimitiveGrid",
    "GeometryNodeMeshPrimitiveIcoSphere",
    "GeometryNodeMeshPrimitiveLine",
    "GeometryNodeMeshPrimitiveUVSphere",
    # Mesh operations
    "GeometryNodeMeshBoolean",
    "GeometryNodeSubdivisionSurface",
    "GeometryNodeSubdivideMesh",
    "GeometryNodeTriangulate",
    "GeometryNodeDualMesh",
    "GeometryNodeFlipFaces",
    "GeometryNodeMeshToCurve",
    "GeometryNodeMeshToPoints",
    "GeometryNodeMeshToVolume",
    "GeometryNodeSplitEdges",
    "GeometryNodeExtrudeMesh",
    "GeometryNodeScaleElements",
    # Points
    "GeometryNodeDistributePointsOnFaces",
    "GeometryNodeDistributePointsInVolume",
    "GeometryNodePointsToVertices",
    "GeometryNodePointsToVolume",
    "GeometryNodePoints",
    # Instances
    "GeometryNodeInstanceOnPoints",
    "GeometryNodeInstancesToPoints",
    "GeometryNodeRealizeInstances",
    "GeometryNodeRotateInstances",
    "GeometryNodeScaleInstances",
    "GeometryNodeTranslateInstances",
    # Curve
    "GeometryNodeCurvePrimitiveLine",
    "GeometryNodeCurvePrimitiveCircle",
    "GeometryNodeCurvePrimitiveBezierSegment",
    "GeometryNodeCurvePrimitiveQuadrilateral",
    "GeometryNodeCurvePrimitiveStar",
    "GeometryNodeCurvePrimitiveSpiral",
    "GeometryNodeCurveToMesh",
    "GeometryNodeCurveToPoints",
    "GeometryNodeFillCurve",
    "GeometryNodeResampleCurve",
    "GeometryNodeReverseCurve",
    "GeometryNodeSubdivideCurve",
    "GeometryNodeTrimCurve",
    "GeometryNodeCurveLength",
    "GeometryNodeDeformCurvesOnSurface",
    # Volume
    "GeometryNodeVolumeToMesh",
    "GeometryNodeVolumeCube",
    # Attribute
    "GeometryNodeSetPosition",
    "GeometryNodeSetShadeSmooth",
    "GeometryNodeSetMaterial",
    "GeometryNodeSetID",
    "GeometryNodeStoreNamedAttribute",
    "GeometryNodeCaptureAttribute",
    "GeometryNodeAttributeStatistic",
    "GeometryNodeRemoveAttribute",
    # Input
    "GeometryNodeInputPosition",
    "GeometryNodeInputNormal",
    "GeometryNodeInputIndex",
    "GeometryNodeInputID",
    "GeometryNodeInputMeshEdgeAngle",
    "GeometryNodeInputMeshEdgeNeighbors",
    "GeometryNodeInputMeshEdgeVertices",
    "GeometryNodeInputMeshFaceArea",
    "GeometryNodeInputMeshFaceNeighbors",
    "GeometryNodeInputMeshIsland",
    "GeometryNodeInputMeshVertexNeighbors",
    "GeometryNodeInputRadius",
    "GeometryNodeInputSceneTime",
    "GeometryNodeIsViewport",
    "GeometryNodeObjectInfo",
    "GeometryNodeCollectionInfo",
    "GeometryNodeSelfObject",
    # Geometry ops
    "GeometryNodeBoundBox",
    "GeometryNodeConvexHull",
    "GeometryNodeDeleteGeometry",
    "GeometryNodeDuplicateElements",
    "GeometryNodeJoinGeometry",
    "GeometryNodeMergeByDistance",
    "GeometryNodeSeparateGeometry",
    "GeometryNodeSeparateComponents",
    "GeometryNodeSetPointRadius",
    "GeometryNodeTransform",
    "GeometryNodeProximity",
    "GeometryNodeRaycast",
    "GeometryNodeSampleIndex",
    "GeometryNodeSampleNearest",
    # Math / utility
    "ShaderNodeMath",
    "ShaderNodeVectorMath",
    "ShaderNodeMapRange",
    "ShaderNodeClamp",
    "ShaderNodeMix",
    "ShaderNodeCombineXYZ",
    "ShaderNodeSeparateXYZ",
    "ShaderNodeValToRGB",
    "FunctionNodeRandomValue",
    "FunctionNodeCompare",
    "FunctionNodeBooleanMath",
    "FunctionNodeAlignEulerToVector",
    "FunctionNodeRotateEuler",
    "FunctionNodeInputVector",
    "FunctionNodeInputColor",
    "FunctionNodeInputBool",
    "FunctionNodeInputInt",
    "FunctionNodeInputSpecialCharacters",
    "FunctionNodeInputString",
    # Texture / noise
    "ShaderNodeTexNoise",
    "ShaderNodeTexVoronoi",
    # ShaderNodeTexMusgrave removed -- merged into ShaderNodeTexNoise in Blender 4.1
    "ShaderNodeTexGradient",
    "ShaderNodeTexWave",
    "ShaderNodeTexWhiteNoise",
    # Group
    "NodeGroupInput",
    "NodeGroupOutput",
    "GeometryNodeGroup",
    # Selection
    "GeometryNodeInputNamedAttribute",
    "FunctionNodeSlice",
})

VALID_GN_PRESETS: frozenset[str] = frozenset({
    "scatter_on_surface",
    "boolean_union",
    "subdivision_smooth",
    "vertex_displacement",
    "edge_wear_mask",
    "proximity_blend",
    "array_along_curve",
    "random_scale_rotation",
})


# ---------------------------------------------------------------------------
# Pure-logic: face scatter positions (Gap #73)
# ---------------------------------------------------------------------------

def _triangle_area(a: Vec3, b: Vec3, c: Vec3) -> float:
    """Compute area of a triangle from three 3D vertices."""
    # Cross product of (b-a) x (c-a)
    abx, aby, abz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    acx, acy, acz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx = aby * acz - abz * acy
    cy = abz * acx - abx * acz
    cz = abx * acy - aby * acx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _face_normal(vertices: list[Vec3], face: tuple[int, ...]) -> Vec3:
    """Compute face normal using Newell's method (works for n-gons)."""
    nx, ny, nz = 0.0, 0.0, 0.0
    n = len(face)
    for i in range(n):
        v_curr = vertices[face[i]]
        v_next = vertices[face[(i + 1) % n]]
        nx += (v_curr[1] - v_next[1]) * (v_curr[2] + v_next[2])
        ny += (v_curr[2] - v_next[2]) * (v_curr[0] + v_next[0])
        nz += (v_curr[0] - v_next[0]) * (v_curr[1] + v_next[1])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-12:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


def _face_centroid(vertices: list[Vec3], face: tuple[int, ...]) -> Vec3:
    """Compute face centroid."""
    n = len(face)
    cx = sum(vertices[face[i]][0] for i in range(n)) / n
    cy = sum(vertices[face[i]][1] for i in range(n)) / n
    cz = sum(vertices[face[i]][2] for i in range(n)) / n
    return (cx, cy, cz)


def _face_area(vertices: list[Vec3], face: tuple[int, ...]) -> float:
    """Compute face area by triangulation from first vertex."""
    if len(face) < 3:
        return 0.0
    total = 0.0
    v0 = vertices[face[0]]
    for i in range(1, len(face) - 1):
        v1 = vertices[face[i]]
        v2 = vertices[face[i + 1]]
        total += _triangle_area(v0, v1, v2)
    return total


def _random_point_in_triangle(
    a: Vec3, b: Vec3, c: Vec3, rng: random.Random,
) -> Vec3:
    """Generate a uniformly random point inside a triangle."""
    r1 = rng.random()
    r2 = rng.random()
    sqrt_r1 = math.sqrt(r1)
    u = 1.0 - sqrt_r1
    v = sqrt_r1 * (1.0 - r2)
    w = sqrt_r1 * r2
    return (
        u * a[0] + v * b[0] + w * c[0],
        u * a[1] + v * b[1] + w * c[1],
        u * a[2] + v * b[2] + w * c[2],
    )


def _random_point_on_face(
    vertices: list[Vec3], face: tuple[int, ...], rng: random.Random,
) -> Vec3:
    """Generate a uniformly random point on a polygon face.

    Triangulates from first vertex, picks a triangle weighted by area,
    then picks a random point inside that triangle.
    """
    if len(face) == 3:
        return _random_point_in_triangle(
            vertices[face[0]], vertices[face[1]], vertices[face[2]], rng,
        )

    # Fan triangulation: (0,1,2), (0,2,3), (0,3,4), ...
    triangles: list[tuple[Vec3, Vec3, Vec3]] = []
    areas: list[float] = []
    v0 = vertices[face[0]]
    for i in range(1, len(face) - 1):
        v1 = vertices[face[i]]
        v2 = vertices[face[i + 1]]
        triangles.append((v0, v1, v2))
        areas.append(_triangle_area(v0, v1, v2))

    total = sum(areas)
    if total < 1e-12:
        return _face_centroid(vertices, face)

    # Weighted random triangle selection
    r = rng.random() * total
    cumulative = 0.0
    for tri, area in zip(triangles, areas):
        cumulative += area
        if r <= cumulative:
            return _random_point_in_triangle(tri[0], tri[1], tri[2], rng)

    # Fallback (floating point edge case)
    return _random_point_in_triangle(
        triangles[-1][0], triangles[-1][1], triangles[-1][2], rng,
    )


def compute_face_scatter_positions(
    vertices: list[Vec3],
    faces: list[tuple[int, ...]],
    density: float = 1.0,
    scale_range: tuple[float, float] = (0.8, 1.2),
    rotation_random: float = 0.0,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Compute scatter instance positions, rotations, scales from mesh faces.

    For each face, the expected number of instances is density * face_area
    (normalized so density=1.0 means ~1 instance per unit-area face).
    Points are placed randomly within each face with optional random rotation
    and scale variation.

    Parameters
    ----------
    vertices : list of (x, y, z)
        Mesh vertex positions.
    faces : list of int-tuples
        Face index tuples.
    density : float
        Instances per unit area. 0 = none, higher = more.
    scale_range : (min, max)
        Random uniform scale range for each instance.
    rotation_random : float
        Maximum random rotation in degrees (applied around face normal).
    seed : int
        Random seed for deterministic results.

    Returns
    -------
    list of dicts, each with:
      - position: (x, y, z)
      - normal: (nx, ny, nz)
      - rotation: float (radians around normal)
      - scale: float
    """
    if not vertices or not faces:
        return []

    rng = random.Random(seed)
    density = max(0.0, density)
    results: list[dict[str, Any]] = []

    rot_max_rad = math.radians(max(0.0, min(rotation_random, 360.0)))
    s_min, s_max = scale_range

    for face in faces:
        if len(face) < 3:
            continue

        area = _face_area(vertices, face)
        normal = _face_normal(vertices, face)

        # Expected instances = density * area
        expected = density * area
        # Integer count: floor + probabilistic extra
        count = int(expected)
        if rng.random() < (expected - count):
            count += 1

        for _ in range(count):
            pos = _random_point_on_face(vertices, face, rng)
            rot = rng.uniform(-rot_max_rad, rot_max_rad) if rot_max_rad > 0 else 0.0
            scale = rng.uniform(s_min, s_max)

            results.append({
                "position": pos,
                "normal": normal,
                "rotation": rot,
                "scale": scale,
            })

    return results


# ---------------------------------------------------------------------------
# Pure-logic: hair card mesh from strand points (Gap #74)
# ---------------------------------------------------------------------------

def compute_hair_card_mesh(
    strand_points: list[list[Vec3]],
    card_width: float = 0.005,
) -> MeshSpec:
    """Convert hair strand control points to flat card mesh geometry.

    Each strand becomes a quad strip: 2 vertices per control point, with
    the card oriented perpendicular to the strand direction and camera-facing
    approximation via cross product with an up vector.

    Parameters
    ----------
    strand_points : list of list of (x, y, z)
        Each inner list is a sequence of control points along one strand.
    card_width : float
        Half-width of each hair card.

    Returns
    -------
    MeshSpec dict with:
      - vertices: list of (x, y, z)
      - faces: list of (i0, i1, i2, i3) quads
      - uvs: list of (u, v) per vertex
      - metadata: dict with strand_count, vertex_count, poly_count, dimensions
    """
    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: list[Vec2] = []

    for strand in strand_points:
        if len(strand) < 2:
            continue

        seg_count = len(strand)
        base_idx = len(all_verts)

        for i, pt in enumerate(strand):
            # Compute tangent direction
            if i == 0:
                tangent = (
                    strand[1][0] - pt[0],
                    strand[1][1] - pt[1],
                    strand[1][2] - pt[2],
                )
            elif i == seg_count - 1:
                tangent = (
                    pt[0] - strand[i - 1][0],
                    pt[1] - strand[i - 1][1],
                    pt[2] - strand[i - 1][2],
                )
            else:
                tangent = (
                    strand[i + 1][0] - strand[i - 1][0],
                    strand[i + 1][1] - strand[i - 1][1],
                    strand[i + 1][2] - strand[i - 1][2],
                )

            # Normalize tangent
            t_len = math.sqrt(
                tangent[0] ** 2 + tangent[1] ** 2 + tangent[2] ** 2
            )
            if t_len < 1e-12:
                tangent = (0.0, 0.0, 1.0)
            else:
                tangent = (
                    tangent[0] / t_len,
                    tangent[1] / t_len,
                    tangent[2] / t_len,
                )

            # Cross tangent with up vector to get card width direction
            up = (0.0, 0.0, 1.0)
            if abs(tangent[2]) > 0.95:
                up = (1.0, 0.0, 0.0)

            # cross = tangent x up
            cx = tangent[1] * up[2] - tangent[2] * up[1]
            cy = tangent[2] * up[0] - tangent[0] * up[2]
            cz = tangent[0] * up[1] - tangent[1] * up[0]
            c_len = math.sqrt(cx * cx + cy * cy + cz * cz)
            if c_len < 1e-12:
                cx, cy, cz = 1.0, 0.0, 0.0
            else:
                cx /= c_len
                cy /= c_len
                cz /= c_len

            # Two vertices offset by card_width on each side
            hw = card_width * 0.5
            v_left = (pt[0] - cx * hw, pt[1] - cy * hw, pt[2] - cz * hw)
            v_right = (pt[0] + cx * hw, pt[1] + cy * hw, pt[2] + cz * hw)

            all_verts.append(v_left)
            all_verts.append(v_right)

            # UV: u=0 for left, u=1 for right; v goes 0 (root) to 1 (tip)
            v_param = i / max(seg_count - 1, 1)
            all_uvs.append((0.0, v_param))
            all_uvs.append((1.0, v_param))

        # Build quad faces along the strip
        for i in range(seg_count - 1):
            vi = base_idx + i * 2
            # Quad: bottom-left, bottom-right, top-right, top-left
            all_faces.append((vi, vi + 1, vi + 3, vi + 2))

    # Compute dimensions
    if all_verts:
        xs = [v[0] for v in all_verts]
        ys = [v[1] for v in all_verts]
        zs = [v[2] for v in all_verts]
        dims = {
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
            "depth": max(zs) - min(zs),
        }
    else:
        dims = {"width": 0.0, "height": 0.0, "depth": 0.0}

    return {
        "vertices": all_verts,
        "faces": all_faces,
        "uvs": all_uvs,
        "metadata": {
            "name": "hair_cards",
            "strand_count": len(strand_points),
            "vertex_count": len(all_verts),
            "poly_count": len(all_faces),
            "dimensions": dims,
        },
    }


# ---------------------------------------------------------------------------
# Geometry Nodes preset code generators (Gap #78)
# ---------------------------------------------------------------------------

def generate_scatter_preset_code(
    target_name: str,
    instance_name: str,
    density: float = 10.0,
    seed: int = 0,
) -> str:
    """Generate Blender Python code for a scatter-on-surface Geometry Nodes setup.

    Creates a GN modifier on target_name that uses Distribute Points on Faces
    + Instance on Points to scatter instance_name on the surface.
    """
    return textwrap.dedent(f"""\
        import bpy

        # Get objects
        target = bpy.data.objects[{target_name!r}]
        instance = bpy.data.objects[{instance_name!r}]

        # Create Geometry Nodes tree
        tree = bpy.data.node_groups.new(name="GN_Scatter_{target_name}", type='GeometryNodeTree')

        # Create nodes
        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-600, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (600, 0)

        distribute = tree.nodes.new('GeometryNodeDistributePointsOnFaces')
        distribute.location = (-200, 0)
        distribute.distribute_method = 'POISSON'

        instance_node = tree.nodes.new('GeometryNodeInstanceOnPoints')
        instance_node.location = (200, 0)

        obj_info = tree.nodes.new('GeometryNodeObjectInfo')
        obj_info.location = (0, -200)
        obj_info.inputs['Object'].default_value = instance

        join = tree.nodes.new('GeometryNodeJoinGeometry')
        join.location = (400, 0)

        # Create interface sockets
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

        # Set density
        distribute.inputs['Density'].default_value = {density!r}
        distribute.inputs['Seed'].default_value = {seed!r}

        # Link nodes
        tree.links.new(group_in.outputs['Geometry'], distribute.inputs['Mesh'])
        tree.links.new(distribute.outputs['Points'], instance_node.inputs['Points'])
        tree.links.new(obj_info.outputs['Geometry'], instance_node.inputs['Instance'])
        tree.links.new(group_in.outputs['Geometry'], join.inputs['Geometry'])
        tree.links.new(instance_node.outputs['Instances'], join.inputs['Geometry'])
        tree.links.new(join.outputs['Geometry'], group_out.inputs['Geometry'])

        # Add modifier to target
        mod = target.modifiers.new(name="GN_Scatter", type='NODES')
        mod.node_group = tree
    """)


def generate_boolean_preset_code(
    base_name: str,
    cutter_names: list[str],
    operation: str = "UNION",
) -> str:
    """Generate code for boolean operations via Geometry Nodes.

    Supports UNION, DIFFERENCE, INTERSECT with multiple cutters chained.
    """
    cutter_blocks = []
    for i, cutter in enumerate(cutter_names):
        y_offset = -200 * (i + 1)
        cutter_blocks.append(textwrap.dedent(f"""\
            obj_info_{i} = tree.nodes.new('GeometryNodeObjectInfo')
            obj_info_{i}.location = (-200, {y_offset})
            obj_info_{i}.inputs['Object'].default_value = bpy.data.objects[{cutter!r}]

            boolean_{i} = tree.nodes.new('GeometryNodeMeshBoolean')
            boolean_{i}.location = (200, {y_offset})
            boolean_{i}.operation = {operation!r}
        """))

    # Build link chain
    link_lines = []
    if len(cutter_names) == 1:
        link_lines.append(
            "tree.links.new(group_in.outputs['Geometry'], boolean_0.inputs['Mesh 1'])"
        )
        link_lines.append(
            "tree.links.new(obj_info_0.outputs['Geometry'], boolean_0.inputs['Mesh 2'])"
        )
        link_lines.append(
            "tree.links.new(boolean_0.outputs['Mesh'], group_out.inputs['Geometry'])"
        )
    else:
        # Chain: first boolean takes group_in, each subsequent takes previous output
        link_lines.append(
            "tree.links.new(group_in.outputs['Geometry'], boolean_0.inputs['Mesh 1'])"
        )
        link_lines.append(
            "tree.links.new(obj_info_0.outputs['Geometry'], boolean_0.inputs['Mesh 2'])"
        )
        for i in range(1, len(cutter_names)):
            link_lines.append(
                f"tree.links.new(boolean_{i - 1}.outputs['Mesh'], boolean_{i}.inputs['Mesh 1'])"
            )
            link_lines.append(
                f"tree.links.new(obj_info_{i}.outputs['Geometry'], boolean_{i}.inputs['Mesh 2'])"
            )
        link_lines.append(
            f"tree.links.new(boolean_{len(cutter_names) - 1}.outputs['Mesh'], group_out.inputs['Geometry'])"
        )

    cutter_code = "\n".join(cutter_blocks)
    links_code = "\n".join(link_lines)

    return textwrap.dedent(f"""\
        import bpy

        base = bpy.data.objects[{base_name!r}]

        tree = bpy.data.node_groups.new(name="GN_Boolean_{base_name}", type='GeometryNodeTree')

        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-600, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (600, 0)

        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

    """) + cutter_code + "\n# Link chain\n" + links_code + "\n\n" + textwrap.dedent(f"""\
        mod = base.modifiers.new(name="GN_Boolean", type='NODES')
        mod.node_group = tree
    """)


def generate_array_curve_preset_code(
    instance_name: str,
    curve_name: str,
    count: int = 10,
) -> str:
    """Generate code for instancing along a curve via Geometry Nodes."""
    return textwrap.dedent(f"""\
        import bpy

        instance_obj = bpy.data.objects[{instance_name!r}]
        curve_obj = bpy.data.objects[{curve_name!r}]

        tree = bpy.data.node_groups.new(name="GN_ArrayCurve", type='GeometryNodeTree')

        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-600, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (600, 0)

        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

        # Resample curve to get evenly spaced points
        resample = tree.nodes.new('GeometryNodeResampleCurve')
        resample.location = (-200, 0)
        resample.mode = 'COUNT'
        resample.inputs['Count'].default_value = {count!r}

        # Curve to Points
        curve_to_pts = tree.nodes.new('GeometryNodeCurveToPoints')
        curve_to_pts.location = (0, 0)
        curve_to_pts.mode = 'COUNT'
        curve_to_pts.inputs['Count'].default_value = {count!r}

        # Instance on Points
        instance_node = tree.nodes.new('GeometryNodeInstanceOnPoints')
        instance_node.location = (200, 0)

        # Object info for the instance
        obj_info = tree.nodes.new('GeometryNodeObjectInfo')
        obj_info.location = (0, -200)
        obj_info.inputs['Object'].default_value = instance_obj

        # Join with original geometry
        join = tree.nodes.new('GeometryNodeJoinGeometry')
        join.location = (400, 0)

        # Links
        tree.links.new(group_in.outputs['Geometry'], curve_to_pts.inputs['Curve'])
        tree.links.new(curve_to_pts.outputs['Points'], instance_node.inputs['Points'])
        tree.links.new(obj_info.outputs['Geometry'], instance_node.inputs['Instance'])
        tree.links.new(curve_to_pts.outputs['Rotation'], instance_node.inputs['Rotation'])
        tree.links.new(group_in.outputs['Geometry'], join.inputs['Geometry'])
        tree.links.new(instance_node.outputs['Instances'], join.inputs['Geometry'])
        tree.links.new(join.outputs['Geometry'], group_out.inputs['Geometry'])

        mod = curve_obj.modifiers.new(name="GN_ArrayCurve", type='NODES')
        mod.node_group = tree
    """)


def generate_vertex_displacement_code(
    target_name: str,
    scale: float = 0.1,
    noise_scale: float = 5.0,
) -> str:
    """Generate code for noise-based vertex displacement via Geometry Nodes."""
    return textwrap.dedent(f"""\
        import bpy

        target = bpy.data.objects[{target_name!r}]

        tree = bpy.data.node_groups.new(name="GN_VertexDisplacement", type='GeometryNodeTree')

        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-800, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (600, 0)

        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

        # Get position
        pos_node = tree.nodes.new('GeometryNodeInputPosition')
        pos_node.location = (-600, -200)

        # Noise texture for displacement
        noise = tree.nodes.new('ShaderNodeTexNoise')
        noise.location = (-400, -200)
        noise.inputs['Scale'].default_value = {noise_scale!r}

        # Get normal for displacement direction
        normal_node = tree.nodes.new('GeometryNodeInputNormal')
        normal_node.location = (-400, -400)

        # Multiply noise by normal and scale
        vec_math = tree.nodes.new('ShaderNodeVectorMath')
        vec_math.location = (-200, -200)
        vec_math.operation = 'SCALE'
        vec_math.inputs['Scale'].default_value = {scale!r}

        # Multiply normal by noise factor
        multiply = tree.nodes.new('ShaderNodeVectorMath')
        multiply.location = (-200, -400)
        multiply.operation = 'MULTIPLY'

        # Set position
        set_pos = tree.nodes.new('GeometryNodeSetPosition')
        set_pos.location = (200, 0)

        # Links
        tree.links.new(pos_node.outputs['Position'], noise.inputs['Vector'])
        tree.links.new(normal_node.outputs['Normal'], multiply.inputs[0])
        tree.links.new(noise.outputs['Fac'], vec_math.inputs[0])
        tree.links.new(normal_node.outputs['Normal'], vec_math.inputs[0])
        tree.links.new(vec_math.outputs['Vector'], set_pos.inputs['Offset'])
        tree.links.new(group_in.outputs['Geometry'], set_pos.inputs['Geometry'])
        tree.links.new(set_pos.outputs['Geometry'], group_out.inputs['Geometry'])

        mod = target.modifiers.new(name="GN_Displacement", type='NODES')
        mod.node_group = tree
    """)


# ---------------------------------------------------------------------------
# Additional preset code generators
# ---------------------------------------------------------------------------

def _generate_edge_wear_mask_code(target_name: str) -> str:
    """Generate code for curvature-based edge wear mask via Geometry Nodes."""
    return textwrap.dedent(f"""\
        import bpy

        target = bpy.data.objects[{target_name!r}]

        tree = bpy.data.node_groups.new(name="GN_EdgeWear_{target_name}", type='GeometryNodeTree')

        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-600, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (600, 0)

        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

        edge_angle = tree.nodes.new('GeometryNodeInputMeshEdgeAngle')
        edge_angle.location = (-400, -200)

        map_range = tree.nodes.new('ShaderNodeMapRange')
        map_range.location = (-200, -200)
        map_range.inputs['From Min'].default_value = 0.0
        map_range.inputs['From Max'].default_value = 1.5
        map_range.inputs['To Min'].default_value = 0.0
        map_range.inputs['To Max'].default_value = 1.0

        store_attr = tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store_attr.location = (200, 0)
        store_attr.data_type = 'FLOAT'
        store_attr.domain = 'FACE'
        store_attr.inputs['Name'].default_value = "edge_wear"

        tree.links.new(edge_angle.outputs['Unsigned Angle'], map_range.inputs['Value'])
        tree.links.new(map_range.outputs['Result'], store_attr.inputs['Value'])
        tree.links.new(group_in.outputs['Geometry'], store_attr.inputs['Geometry'])
        tree.links.new(store_attr.outputs['Geometry'], group_out.inputs['Geometry'])

        mod = target.modifiers.new(name="GN_EdgeWear", type='NODES')
        mod.node_group = tree
    """)


def _generate_proximity_blend_code(
    target_name: str, proxy_name: str,
) -> str:
    """Generate code for proximity-based blending via Geometry Nodes."""
    return textwrap.dedent(f"""\
        import bpy

        target = bpy.data.objects[{target_name!r}]
        proxy = bpy.data.objects[{proxy_name!r}]

        tree = bpy.data.node_groups.new(name="GN_ProximityBlend_{target_name}", type='GeometryNodeTree')

        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-600, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (600, 0)

        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

        obj_info = tree.nodes.new('GeometryNodeObjectInfo')
        obj_info.location = (-400, -200)
        obj_info.inputs['Object'].default_value = proxy

        proximity = tree.nodes.new('GeometryNodeProximity')
        proximity.location = (-200, -200)

        map_range = tree.nodes.new('ShaderNodeMapRange')
        map_range.location = (0, -200)
        map_range.inputs['From Min'].default_value = 0.0
        map_range.inputs['From Max'].default_value = 2.0
        map_range.inputs['To Min'].default_value = 1.0
        map_range.inputs['To Max'].default_value = 0.0

        store_attr = tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store_attr.location = (200, 0)
        store_attr.data_type = 'FLOAT'
        store_attr.domain = 'POINT'
        store_attr.inputs['Name'].default_value = "proximity_blend"

        tree.links.new(obj_info.outputs['Geometry'], proximity.inputs['Target'])
        tree.links.new(proximity.outputs['Distance'], map_range.inputs['Value'])
        tree.links.new(map_range.outputs['Result'], store_attr.inputs['Value'])
        tree.links.new(group_in.outputs['Geometry'], store_attr.inputs['Geometry'])
        tree.links.new(store_attr.outputs['Geometry'], group_out.inputs['Geometry'])

        mod = target.modifiers.new(name="GN_ProximityBlend", type='NODES')
        mod.node_group = tree
    """)


def _generate_random_scale_rotation_code(target_name: str, seed: int = 0) -> str:
    """Generate code for randomizing instance transforms via Geometry Nodes."""
    return textwrap.dedent(f"""\
        import bpy

        target = bpy.data.objects[{target_name!r}]

        tree = bpy.data.node_groups.new(name="GN_RandomTransform_{target_name}", type='GeometryNodeTree')

        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-600, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (600, 0)

        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

        rand_val = tree.nodes.new('FunctionNodeRandomValue')
        rand_val.location = (-200, -200)
        rand_val.data_type = 'FLOAT_VECTOR'
        rand_val.inputs['Seed'].default_value = {seed!r}

        rotate = tree.nodes.new('GeometryNodeRotateInstances')
        rotate.location = (0, 0)

        scale_inst = tree.nodes.new('GeometryNodeScaleInstances')
        scale_inst.location = (200, 0)

        tree.links.new(group_in.outputs['Geometry'], rotate.inputs['Instances'])
        tree.links.new(rand_val.outputs['Value'], rotate.inputs['Rotation'])
        tree.links.new(rotate.outputs['Instances'], scale_inst.inputs['Instances'])
        tree.links.new(scale_inst.outputs['Instances'], group_out.inputs['Geometry'])

        mod = target.modifiers.new(name="GN_RandomTransform", type='NODES')
        mod.node_group = tree
    """)


def _generate_subdivision_smooth_code(target_name: str, level: int = 2) -> str:
    """Generate code for subdivision surface via Geometry Nodes."""
    return textwrap.dedent(f"""\
        import bpy

        target = bpy.data.objects[{target_name!r}]

        tree = bpy.data.node_groups.new(name="GN_Subdivision_{target_name}", type='GeometryNodeTree')

        group_in = tree.nodes.new('NodeGroupInput')
        group_in.location = (-400, 0)
        group_out = tree.nodes.new('NodeGroupOutput')
        group_out.location = (400, 0)

        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

        subdiv = tree.nodes.new('GeometryNodeSubdivisionSurface')
        subdiv.location = (0, 0)
        subdiv.inputs['Level'].default_value = {level!r}

        tree.links.new(group_in.outputs['Geometry'], subdiv.inputs['Mesh'])
        tree.links.new(subdiv.outputs['Mesh'], group_out.inputs['Geometry'])

        mod = target.modifiers.new(name="GN_Subdivision", type='NODES')
        mod.node_group = tree
    """)


# Preset dispatcher map (preset name -> generator function + required params)
_PRESET_GENERATORS: dict[str, Any] = {
    "scatter_on_surface": generate_scatter_preset_code,
    "boolean_union": generate_boolean_preset_code,
    "subdivision_smooth": _generate_subdivision_smooth_code,
    "vertex_displacement": generate_vertex_displacement_code,
    "edge_wear_mask": _generate_edge_wear_mask_code,
    "proximity_blend": _generate_proximity_blend_code,
    "array_along_curve": generate_array_curve_preset_code,
    "random_scale_rotation": _generate_random_scale_rotation_code,
}


# ---------------------------------------------------------------------------
# bpy-dependent handlers (run inside Blender)
# ---------------------------------------------------------------------------

def handle_geometry_nodes(params: dict) -> dict:
    """Create, modify, and query Geometry Nodes trees via Python API.

    Parameters
    ----------
    params : dict
        action : str — 'create' | 'add_node' | 'link' | 'set_value' |
                        'remove_node' | 'list_nodes' | 'apply' | 'get_output' |
                        'create_preset'
        object_name : str (required for 'apply' and 'create_preset')
        tree_name : str (for most actions)
        ... (action-specific params)
    """
    import bpy  # noqa: F811 — available only inside Blender

    action = params.get("action", "create")

    if action == "create":
        tree_name = params.get("tree_name", "GeometryNodes")
        obj_name = params.get("object_name")

        tree = bpy.data.node_groups.new(name=tree_name, type="GeometryNodeTree")

        # Add Group Input / Output
        gin = tree.nodes.new("NodeGroupInput")
        gin.location = (-400, 0)
        gout = tree.nodes.new("NodeGroupOutput")
        gout.location = (400, 0)

        # Create interface sockets
        tree.interface.new_socket(
            "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry",
        )
        tree.interface.new_socket(
            "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry",
        )

        # Pass-through link
        tree.links.new(gin.outputs["Geometry"], gout.inputs["Geometry"])

        # Optionally assign to object
        if obj_name:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                mod = obj.modifiers.new(name=tree_name, type="NODES")
                mod.node_group = tree

        return {
            "status": "ok",
            "tree_name": tree.name,
            "node_count": len(tree.nodes),
        }

    elif action == "add_node":
        tree_name = params.get("tree_name", "GeometryNodes")
        node_type = params["node_type"]
        node_name = params.get("name", node_type)
        location = params.get("location", [0, 0])

        if node_type not in VALID_GN_NODE_TYPES:
            return {"status": "error", "message": f"Invalid node type: {node_type}"}

        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            return {"status": "error", "message": f"Node group '{tree_name}' not found"}

        node = tree.nodes.new(node_type)
        node.name = node_name
        node.label = node_name
        node.location = (location[0], location[1])

        return {
            "status": "ok",
            "node_name": node.name,
            "node_type": node_type,
            "location": list(node.location),
        }

    elif action == "link":
        tree_name = params.get("tree_name", "GeometryNodes")
        from_node = params["from_node"]
        from_socket = params["from_socket"]
        to_node = params["to_node"]
        to_socket = params["to_socket"]

        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            return {"status": "error", "message": f"Node group '{tree_name}' not found"}

        src = tree.nodes.get(from_node)
        dst = tree.nodes.get(to_node)
        if not src:
            return {"status": "error", "message": f"Node '{from_node}' not found"}
        if not dst:
            return {"status": "error", "message": f"Node '{to_node}' not found"}

        # Find sockets by name
        src_out = None
        for s in src.outputs:
            if s.name == from_socket:
                src_out = s
                break
        if not src_out:
            return {"status": "error", "message": f"Output socket '{from_socket}' not found on '{from_node}'"}

        dst_in = None
        for s in dst.inputs:
            if s.name == to_socket:
                dst_in = s
                break
        if not dst_in:
            return {"status": "error", "message": f"Input socket '{to_socket}' not found on '{to_node}'"}

        link = tree.links.new(src_out, dst_in)
        return {
            "status": "ok",
            "from": f"{from_node}.{from_socket}",
            "to": f"{to_node}.{to_socket}",
        }

    elif action == "set_value":
        tree_name = params.get("tree_name", "GeometryNodes")
        node_name = params["node_name"]
        input_name = params["input_name"]
        value = params["value"]

        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            return {"status": "error", "message": f"Node group '{tree_name}' not found"}

        node = tree.nodes.get(node_name)
        if not node:
            return {"status": "error", "message": f"Node '{node_name}' not found"}

        inp = None
        for s in node.inputs:
            if s.name == input_name:
                inp = s
                break
        if not inp:
            return {"status": "error", "message": f"Input '{input_name}' not found on '{node_name}'"}

        inp.default_value = value
        return {
            "status": "ok",
            "node_name": node_name,
            "input_name": input_name,
            "value": str(value),
        }

    elif action == "remove_node":
        tree_name = params.get("tree_name", "GeometryNodes")
        node_name = params["node_name"]

        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            return {"status": "error", "message": f"Node group '{tree_name}' not found"}

        node = tree.nodes.get(node_name)
        if not node:
            return {"status": "error", "message": f"Node '{node_name}' not found"}

        tree.nodes.remove(node)
        return {"status": "ok", "removed": node_name}

    elif action == "list_nodes":
        tree_name = params.get("tree_name", "GeometryNodes")

        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            return {"status": "error", "message": f"Node group '{tree_name}' not found"}

        nodes_info = []
        for n in tree.nodes:
            inputs = [s.name for s in n.inputs]
            outputs = [s.name for s in n.outputs]
            nodes_info.append({
                "name": n.name,
                "type": n.bl_idname,
                "location": [n.location.x, n.location.y],
                "inputs": inputs,
                "outputs": outputs,
            })

        links_info = []
        for link in tree.links:
            links_info.append({
                "from_node": link.from_node.name,
                "from_socket": link.from_socket.name,
                "to_node": link.to_node.name,
                "to_socket": link.to_socket.name,
            })

        return {
            "status": "ok",
            "tree_name": tree.name,
            "node_count": len(tree.nodes),
            "nodes": nodes_info,
            "links": links_info,
        }

    elif action == "apply":
        obj_name = params["object_name"]
        tree_name = params.get("tree_name")

        obj = bpy.data.objects.get(obj_name)
        if not obj:
            return {"status": "error", "message": f"Object '{obj_name}' not found"}

        if tree_name:
            tree = bpy.data.node_groups.get(tree_name)
            if not tree:
                return {"status": "error", "message": f"Node group '{tree_name}' not found"}
            mod = obj.modifiers.new(name=tree_name, type="NODES")
            mod.node_group = tree
        else:
            # Apply the first GN modifier
            for mod in obj.modifiers:
                if mod.type == "NODES":
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    return {"status": "ok", "applied": mod.name}
            return {"status": "error", "message": "No GN modifier found"}

        return {"status": "ok", "modifier": tree_name, "object": obj_name}

    elif action == "get_output":
        tree_name = params.get("tree_name", "GeometryNodes")

        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            return {"status": "error", "message": f"Node group '{tree_name}' not found"}

        output_node = None
        for n in tree.nodes:
            if n.bl_idname == "NodeGroupOutput":
                output_node = n
                break

        if not output_node:
            return {"status": "error", "message": "No Group Output node found"}

        return {
            "status": "ok",
            "tree_name": tree.name,
            "output_sockets": [
                {"name": s.name, "type": s.bl_idname}
                for s in output_node.inputs
                if s.name  # Skip the empty/virtual socket
            ],
        }

    elif action == "create_preset":
        preset_name = params.get("preset_name", "scatter_on_surface")
        obj_name = params.get("object_name")

        if preset_name not in VALID_GN_PRESETS:
            return {
                "status": "error",
                "message": f"Unknown preset: {preset_name}. Valid: {sorted(VALID_GN_PRESETS)}",
            }

        # Build kwargs for the generator based on preset
        if preset_name == "scatter_on_surface":
            code = generate_scatter_preset_code(
                target_name=obj_name or "Cube",
                instance_name=params.get("instance_name", "Sphere"),
                density=params.get("density", 10.0),
                seed=params.get("seed", 0),
            )
        elif preset_name == "boolean_union":
            code = generate_boolean_preset_code(
                base_name=obj_name or "Cube",
                cutter_names=params.get("cutter_names", ["Cube.001"]),
                operation=params.get("operation", "UNION"),
            )
        elif preset_name == "subdivision_smooth":
            code = _generate_subdivision_smooth_code(
                target_name=obj_name or "Cube",
                level=params.get("level", 2),
            )
        elif preset_name == "vertex_displacement":
            code = generate_vertex_displacement_code(
                target_name=obj_name or "Cube",
                scale=params.get("scale", 0.1),
                noise_scale=params.get("noise_scale", 5.0),
            )
        elif preset_name == "edge_wear_mask":
            code = _generate_edge_wear_mask_code(
                target_name=obj_name or "Cube",
            )
        elif preset_name == "proximity_blend":
            code = _generate_proximity_blend_code(
                target_name=obj_name or "Cube",
                proxy_name=params.get("proxy_name", "Empty"),
            )
        elif preset_name == "array_along_curve":
            code = generate_array_curve_preset_code(
                instance_name=params.get("instance_name", "Cube"),
                curve_name=params.get("curve_name", "BezierCurve"),
                count=params.get("count", 10),
            )
        elif preset_name == "random_scale_rotation":
            code = _generate_random_scale_rotation_code(
                target_name=obj_name or "Cube",
                seed=params.get("seed", 0),
            )
        else:
            return {"status": "error", "message": f"Preset '{preset_name}' not implemented"}

        # Execute the generated code inside Blender
        exec_globals = {"bpy": bpy}
        exec(compile(code, f"<gn_preset_{preset_name}>", "exec"), exec_globals)

        return {
            "status": "ok",
            "preset": preset_name,
            "code": code,
        }

    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


def handle_face_scatter(params: dict) -> dict:
    """Scatter detail meshes on every face of a target mesh.

    Parameters
    ----------
    params : dict
        object_name : str — target mesh to scatter onto
        instance_mesh : str — mesh to place on faces
        density : float — instances per unit area (default 1.0)
        scale_range : [min, max] — random scale variation
        rotation_random : float — 0-360 degrees
        align_to_normal : bool — orient instance to face normal
        seed : int
        use_geometry_nodes : bool — True = GN scatter, False = pure-logic
    """
    import bpy  # noqa: F811

    obj_name = params["object_name"]
    instance_name = params.get("instance_mesh", "Sphere")
    density = params.get("density", 1.0)
    scale_range = tuple(params.get("scale_range", [0.8, 1.2]))
    rotation_random = params.get("rotation_random", 0.0)
    align_to_normal = params.get("align_to_normal", True)
    seed = params.get("seed", 42)
    use_gn = params.get("use_geometry_nodes", True)

    obj = bpy.data.objects.get(obj_name)
    if not obj or obj.type != "MESH":
        return {"status": "error", "message": f"Mesh object '{obj_name}' not found"}

    if use_gn:
        # Generate and execute GN scatter code
        code = generate_scatter_preset_code(
            target_name=obj_name,
            instance_name=instance_name,
            density=density,
            seed=seed,
        )
        exec_globals = {"bpy": bpy}
        exec(compile(code, "<face_scatter_gn>", "exec"), exec_globals)

        return {
            "status": "ok",
            "mode": "geometry_nodes",
            "object": obj_name,
            "instance": instance_name,
            "density": density,
        }
    else:
        # Pure-logic mode: extract mesh data and compute positions
        mesh = obj.data
        vertices = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
        faces = [tuple(p.vertices) for p in mesh.polygons]

        instances = compute_face_scatter_positions(
            vertices=vertices,
            faces=faces,
            density=density,
            scale_range=scale_range,
            rotation_random=rotation_random,
            seed=seed,
        )

        return {
            "status": "ok",
            "mode": "pure_logic",
            "object": obj_name,
            "instance_count": len(instances),
            "instances": instances[:100],  # Cap returned data for token budget
            "total_instances": len(instances),
        }


def handle_particle_to_mesh(params: dict) -> dict:
    """Convert Blender particle system to exportable mesh geometry.

    Parameters
    ----------
    params : dict
        object_name : str — object with particle system
        particle_system_name : str — optional, defaults to first
        output_name : str — name for generated mesh object
        card_width : float — width of hair cards
        segments_per_strand : int — vertex count per strand
        merge_nearby : float — merge threshold for overlapping cards
    """
    import bpy  # noqa: F811
    import bmesh as _bmesh  # noqa: F811

    obj_name = params["object_name"]
    ps_name = params.get("particle_system_name")
    output_name = params.get("output_name", f"{obj_name}_cards")
    card_width = params.get("card_width", 0.005)
    segments = params.get("segments_per_strand", 5)
    merge_nearby = params.get("merge_nearby", 0.0)

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"status": "error", "message": f"Object '{obj_name}' not found"}

    # Find particle system
    ps = None
    if ps_name:
        for p in obj.particle_systems:
            if p.name == ps_name:
                ps = p
                break
        if not ps:
            return {"status": "error", "message": f"Particle system '{ps_name}' not found"}
    else:
        if not obj.particle_systems:
            return {"status": "error", "message": f"No particle systems on '{obj_name}'"}
        ps = obj.particle_systems[0]

    # Evaluate depsgraph to access particle data
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)

    ps_eval = None
    for p in obj_eval.particle_systems:
        if p.name == ps.name:
            ps_eval = p
            break
    if not ps_eval:
        return {"status": "error", "message": "Could not evaluate particle system"}

    # Extract strand data
    strand_points: list[list[tuple[float, float, float]]] = []

    is_hair = ps_eval.settings.type == "HAIR"

    if is_hair:
        for particle in ps_eval.particles:
            strand = []
            for key in particle.hair_keys:
                co = key.co
                strand.append((co.x, co.y, co.z))
            if len(strand) >= 2:
                # Resample to desired segment count
                if len(strand) != segments:
                    resampled = _resample_strand(strand, segments)
                    strand_points.append(resampled)
                else:
                    strand_points.append(strand)
    else:
        # Emitter particles: use location + velocity for short strands
        for particle in ps_eval.particles:
            loc = particle.location
            vel = particle.velocity
            vel_len = math.sqrt(vel.x ** 2 + vel.y ** 2 + vel.z ** 2)
            if vel_len < 1e-6:
                continue
            strand = []
            for i in range(segments):
                t = i / max(segments - 1, 1) * 0.1  # Short distance
                strand.append((
                    loc.x + vel.x * t,
                    loc.y + vel.y * t,
                    loc.z + vel.z * t,
                ))
            strand_points.append(strand)

    if not strand_points:
        return {"status": "error", "message": "No valid strands found"}

    # Convert to card mesh using pure-logic function
    mesh_spec = compute_hair_card_mesh(strand_points, card_width)

    # Create Blender mesh object from the spec
    mesh_data = bpy.data.meshes.new(output_name)
    mesh_data.from_pydata(mesh_spec["vertices"], [], mesh_spec["faces"])

    # Set UVs
    if mesh_spec["uvs"]:
        uv_layer = mesh_data.uv_layers.new(name="UVMap")
        for poly in mesh_data.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                if vi < len(mesh_spec["uvs"]):
                    uv_layer.data[li].uv = mesh_spec["uvs"][vi]

    mesh_data.update()

    new_obj = bpy.data.objects.new(output_name, mesh_data)
    bpy.context.collection.objects.link(new_obj)

    # Merge nearby vertices if requested
    if merge_nearby > 0:
        bpy.context.view_layer.objects.active = new_obj
        new_obj.select_set(True)
        bm = _bmesh.new()
        bm.from_mesh(new_obj.data)
        _bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_nearby)
        bm.to_mesh(new_obj.data)
        bm.free()
        new_obj.data.update()

    return {
        "status": "ok",
        "output_object": output_name,
        "strand_count": len(strand_points),
        "vertex_count": len(mesh_spec["vertices"]),
        "face_count": len(mesh_spec["faces"]),
        "metadata": mesh_spec["metadata"],
    }


def _resample_strand(
    points: list[tuple[float, float, float]], target_count: int,
) -> list[tuple[float, float, float]]:
    """Resample a strand to a target number of evenly spaced points."""
    if len(points) < 2 or target_count < 2:
        return points[:target_count] if target_count <= len(points) else points

    # Compute cumulative arc lengths
    lengths = [0.0]
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        dz = points[i][2] - points[i - 1][2]
        lengths.append(lengths[-1] + math.sqrt(dx * dx + dy * dy + dz * dz))

    total_length = lengths[-1]
    if total_length < 1e-12:
        return [points[0]] * target_count

    result: list[tuple[float, float, float]] = []
    for i in range(target_count):
        t = i / (target_count - 1) * total_length

        # Find segment
        seg = 0
        for j in range(1, len(lengths)):
            if lengths[j] >= t:
                seg = j - 1
                break
        else:
            seg = len(lengths) - 2

        seg_len = lengths[seg + 1] - lengths[seg]
        if seg_len < 1e-12:
            frac = 0.0
        else:
            frac = (t - lengths[seg]) / seg_len

        p0 = points[seg]
        p1 = points[seg + 1]
        result.append((
            p0[0] + frac * (p1[0] - p0[0]),
            p0[1] + frac * (p1[1] - p0[1]),
            p0[2] + frac * (p1[2] - p0[2]),
        ))

    return result
