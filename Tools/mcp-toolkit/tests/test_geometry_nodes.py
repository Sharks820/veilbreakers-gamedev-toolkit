"""Tests for geometry_nodes.py: face scatter, hair card mesh, GN presets.

All pure-logic -- no Blender/bpy required.
"""

import ast
import math
import re

import pytest

from blender_addon.handlers.geometry_nodes import (
    VALID_GN_NODE_TYPES,
    VALID_GN_PRESETS,
    compute_face_scatter_positions,
    compute_hair_card_mesh,
    generate_array_curve_preset_code,
    generate_boolean_preset_code,
    generate_scatter_preset_code,
    generate_vertex_displacement_code,
    _generate_edge_wear_mask_code,
    _generate_proximity_blend_code,
    _generate_random_scale_rotation_code,
    _generate_subdivision_smooth_code,
    _face_area,
    _face_normal,
    _face_centroid,
)


# ===================================================================
# Constants validation
# ===================================================================


class TestValidConstants:
    """Test VALID_GN_NODE_TYPES and VALID_GN_PRESETS."""

    def test_node_types_is_frozenset(self):
        assert isinstance(VALID_GN_NODE_TYPES, frozenset)

    def test_node_types_not_empty(self):
        assert len(VALID_GN_NODE_TYPES) > 50

    def test_all_node_types_are_strings(self):
        for nt in VALID_GN_NODE_TYPES:
            assert isinstance(nt, str)
            assert len(nt) > 0

    def test_core_geometry_nodes_present(self):
        """Key Geometry Node types must be in the set."""
        required = {
            "GeometryNodeMeshPrimitiveCube",
            "GeometryNodeSetPosition",
            "GeometryNodeDistributePointsOnFaces",
            "GeometryNodeInstanceOnPoints",
            "GeometryNodeMeshBoolean",
            "GeometryNodeSubdivisionSurface",
            "ShaderNodeMath",
            "ShaderNodeVectorMath",
            "FunctionNodeRandomValue",
            "GeometryNodeProximity",
            "GeometryNodeRaycast",
            "GeometryNodeMeshToVolume",
            "GeometryNodeVolumeToMesh",
            "NodeGroupInput",
            "NodeGroupOutput",
            "ShaderNodeTexNoise",
            "GeometryNodeCurveToMesh",
            "GeometryNodeResampleCurve",
            "GeometryNodeJoinGeometry",
            "GeometryNodeTransform",
        }
        for r in required:
            assert r in VALID_GN_NODE_TYPES, f"Missing node type: {r}"

    def test_node_types_naming_convention(self):
        """All node types should follow Blender naming patterns."""
        valid_prefixes = (
            "GeometryNode", "ShaderNode", "FunctionNode", "NodeGroup",
        )
        for nt in VALID_GN_NODE_TYPES:
            assert any(nt.startswith(p) for p in valid_prefixes), (
                f"Unexpected prefix in node type: {nt}"
            )

    def test_presets_is_frozenset(self):
        assert isinstance(VALID_GN_PRESETS, frozenset)

    def test_all_presets_present(self):
        expected = {
            "scatter_on_surface",
            "boolean_union",
            "subdivision_smooth",
            "vertex_displacement",
            "edge_wear_mask",
            "proximity_blend",
            "array_along_curve",
            "random_scale_rotation",
        }
        assert VALID_GN_PRESETS == expected


# ===================================================================
# Face scatter position tests (Gap #73)
# ===================================================================

# Test geometry: a unit square lying on XY plane at z=0
_UNIT_SQUARE_VERTS = [
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (1.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
]
_UNIT_SQUARE_FACES = [(0, 1, 2, 3)]

# Two-triangle mesh (area = 1.0 total)
_TWO_TRI_VERTS = [
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (2.0, 0.0, 0.0),
    (2.0, 1.0, 0.0),
]
_TWO_TRI_FACES = [(0, 1, 2), (1, 3, 4)]


class TestFaceScatterPositions:
    """Tests for compute_face_scatter_positions."""

    def test_returns_list(self):
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=5.0, seed=42,
        )
        assert isinstance(result, list)

    def test_instance_count_scales_with_density(self):
        """Higher density should produce more instances."""
        low = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=1.0, seed=42,
        )
        high = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=50.0, seed=42,
        )
        assert len(high) > len(low)

    def test_density_zero_produces_no_instances(self):
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=0.0, seed=42,
        )
        assert len(result) == 0

    def test_approximate_instance_count(self):
        """For density=D on area=A, expected count ~ D*A."""
        density = 10.0
        # Unit square has area 1.0, so expected ~10 instances
        counts = []
        for seed in range(20):
            result = compute_face_scatter_positions(
                _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES,
                density=density, seed=seed,
            )
            counts.append(len(result))
        avg = sum(counts) / len(counts)
        # Average should be close to density * area = 10
        assert 5 <= avg <= 15, f"Average instance count {avg} too far from expected 10"

    def test_positions_on_face_surface(self):
        """All scatter positions should lie on z=0 for a flat XY quad."""
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=20.0, seed=42,
        )
        assert len(result) > 0
        for inst in result:
            pos = inst["position"]
            # z should be 0 for flat XY face
            assert abs(pos[2]) < 1e-6, f"z={pos[2]} not on face surface"
            # x and y should be within face bounds
            assert -1e-6 <= pos[0] <= 1.0 + 1e-6, f"x={pos[0]} out of face bounds"
            assert -1e-6 <= pos[1] <= 1.0 + 1e-6, f"y={pos[1]} out of face bounds"

    def test_normals_match_face_normal(self):
        """Scatter normals should match the face normal (0,0,1) for XY plane."""
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=10.0, seed=42,
        )
        for inst in result:
            nx, ny, nz = inst["normal"]
            assert abs(nx) < 1e-6
            assert abs(ny) < 1e-6
            assert abs(nz - 1.0) < 1e-6

    def test_scale_within_range(self):
        """All scales should be within the specified range."""
        s_min, s_max = 0.5, 2.0
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES,
            density=20.0, scale_range=(s_min, s_max), seed=42,
        )
        for inst in result:
            assert s_min <= inst["scale"] <= s_max, (
                f"Scale {inst['scale']} outside [{s_min}, {s_max}]"
            )

    def test_rotation_within_range(self):
        """Rotation should be within [-rotation_random, +rotation_random] radians."""
        rot_deg = 45.0
        rot_rad = math.radians(rot_deg)
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES,
            density=20.0, rotation_random=rot_deg, seed=42,
        )
        for inst in result:
            assert -rot_rad <= inst["rotation"] <= rot_rad, (
                f"Rotation {inst['rotation']} outside bounds"
            )

    def test_zero_rotation_random(self):
        """With rotation_random=0, all rotations should be 0."""
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES,
            density=10.0, rotation_random=0.0, seed=42,
        )
        for inst in result:
            assert inst["rotation"] == 0.0

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical results."""
        a = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=10.0, seed=123,
        )
        b = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=10.0, seed=123,
        )
        assert a == b

    def test_different_seeds_different_results(self):
        """Different seeds should produce different scatter patterns."""
        a = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=10.0, seed=1,
        )
        b = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=10.0, seed=2,
        )
        # At least some positions should differ
        if len(a) > 0 and len(b) > 0:
            positions_a = [inst["position"] for inst in a]
            positions_b = [inst["position"] for inst in b]
            assert positions_a != positions_b

    def test_empty_mesh_returns_empty(self):
        assert compute_face_scatter_positions([], [], density=10.0) == []

    def test_multi_face_scatter(self):
        """Scatter across multiple triangular faces."""
        result = compute_face_scatter_positions(
            _TWO_TRI_VERTS, _TWO_TRI_FACES, density=20.0, seed=42,
        )
        # Should have instances from both faces
        assert len(result) > 0

    def test_result_dict_keys(self):
        """Each instance dict should have position, normal, rotation, scale."""
        result = compute_face_scatter_positions(
            _UNIT_SQUARE_VERTS, _UNIT_SQUARE_FACES, density=10.0, seed=42,
        )
        required_keys = {"position", "normal", "rotation", "scale"}
        for inst in result:
            assert set(inst.keys()) == required_keys

    def test_tilted_face_normal(self):
        """Scatter on a tilted face should produce matching tilted normals."""
        # 45-degree tilted triangle
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.707, 0.707),
        ]
        faces = [(0, 1, 2)]
        result = compute_face_scatter_positions(
            verts, faces, density=50.0, seed=42,
        )
        if result:
            # Normal should not be (0,0,1) for tilted face
            nx, ny, nz = result[0]["normal"]
            assert abs(nz - 1.0) > 0.1, "Normal should be tilted, not straight up"


# ===================================================================
# Hair card mesh tests (Gap #74)
# ===================================================================

# Simple test strands
_SIMPLE_STRANDS = [
    [(0.0, 0.0, 0.0), (0.0, 0.0, 0.1), (0.0, 0.0, 0.2)],
    [(0.1, 0.0, 0.0), (0.1, 0.0, 0.1), (0.1, 0.0, 0.2)],
]

_SINGLE_STRAND = [
    [(0.0, 0.0, 0.0), (0.0, 0.0, 0.05), (0.0, 0.0, 0.1), (0.0, 0.0, 0.15)],
]


class TestHairCardMesh:
    """Tests for compute_hair_card_mesh."""

    def test_returns_mesh_spec(self):
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        assert "vertices" in result
        assert "faces" in result
        assert "uvs" in result
        assert "metadata" in result

    def test_vertex_count_formula(self):
        """2 vertices per control point per strand."""
        strands = _SIMPLE_STRANDS  # 2 strands, 3 points each
        result = compute_hair_card_mesh(strands, card_width=0.01)
        expected_verts = 2 * 3 * 2  # 2 strands * 3 points * 2 verts per point
        assert len(result["vertices"]) == expected_verts

    def test_face_count_formula(self):
        """(segments-1) quads per strand."""
        strands = _SIMPLE_STRANDS  # 2 strands, 3 points each -> 2 quads per strand
        result = compute_hair_card_mesh(strands, card_width=0.01)
        expected_faces = 2 * 2  # 2 strands * (3-1) quads
        assert len(result["faces"]) == expected_faces

    def test_single_strand_vertex_count(self):
        """Single strand with 4 points -> 8 vertices."""
        result = compute_hair_card_mesh(_SINGLE_STRAND, card_width=0.005)
        assert len(result["vertices"]) == 8  # 4 points * 2

    def test_single_strand_face_count(self):
        """Single strand with 4 points -> 3 quads."""
        result = compute_hair_card_mesh(_SINGLE_STRAND, card_width=0.005)
        assert len(result["faces"]) == 3  # 4-1 = 3

    def test_uvs_count_matches_vertices(self):
        """UV count should equal vertex count."""
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        assert len(result["uvs"]) == len(result["vertices"])

    def test_uvs_in_01_range(self):
        """All UVs should be in [0, 1] range."""
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        for u, v in result["uvs"]:
            assert 0.0 <= u <= 1.0, f"UV u={u} out of [0,1] range"
            assert 0.0 <= v <= 1.0, f"UV v={v} out of [0,1] range"

    def test_uv_u_values_are_0_or_1(self):
        """U values should be 0 (left edge) or 1 (right edge)."""
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        for u, _ in result["uvs"]:
            assert u == 0.0 or u == 1.0, f"UV u={u} should be 0 or 1"

    def test_uv_v_root_is_zero(self):
        """First vertex pair (root) should have v=0."""
        result = compute_hair_card_mesh(_SINGLE_STRAND, card_width=0.005)
        # First two UVs are the root pair
        assert result["uvs"][0][1] == 0.0
        assert result["uvs"][1][1] == 0.0

    def test_uv_v_tip_is_one(self):
        """Last vertex pair (tip) should have v=1."""
        result = compute_hair_card_mesh(_SINGLE_STRAND, card_width=0.005)
        # Last two UVs are the tip pair
        assert result["uvs"][-1][1] == 1.0
        assert result["uvs"][-2][1] == 1.0

    def test_faces_are_quads(self):
        """All faces should have 4 vertices (quads)."""
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        for face in result["faces"]:
            assert len(face) == 4, f"Face has {len(face)} verts, expected 4"

    def test_card_width_affects_geometry(self):
        """Wider cards should produce wider vertex spread."""
        narrow = compute_hair_card_mesh(_SINGLE_STRAND, card_width=0.001)
        wide = compute_hair_card_mesh(_SINGLE_STRAND, card_width=0.1)

        # Measure width of first pair
        v0_n = narrow["vertices"][0]
        v1_n = narrow["vertices"][1]
        w_narrow = math.sqrt(sum((a - b) ** 2 for a, b in zip(v0_n, v1_n)))

        v0_w = wide["vertices"][0]
        v1_w = wide["vertices"][1]
        w_wide = math.sqrt(sum((a - b) ** 2 for a, b in zip(v0_w, v1_w)))

        assert w_wide > w_narrow

    def test_empty_strands_returns_empty(self):
        result = compute_hair_card_mesh([], card_width=0.01)
        assert len(result["vertices"]) == 0
        assert len(result["faces"]) == 0

    def test_single_point_strand_skipped(self):
        """Strands with fewer than 2 points should be skipped."""
        strands = [[(0.0, 0.0, 0.0)]]
        result = compute_hair_card_mesh(strands, card_width=0.01)
        assert len(result["vertices"]) == 0
        assert len(result["faces"]) == 0

    def test_metadata_strand_count(self):
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        assert result["metadata"]["strand_count"] == 2

    def test_metadata_poly_count(self):
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        assert result["metadata"]["poly_count"] == len(result["faces"])

    def test_metadata_vertex_count(self):
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        assert result["metadata"]["vertex_count"] == len(result["vertices"])

    def test_metadata_dimensions(self):
        result = compute_hair_card_mesh(_SIMPLE_STRANDS, card_width=0.01)
        dims = result["metadata"]["dimensions"]
        assert "width" in dims
        assert "height" in dims
        assert "depth" in dims

    def test_many_strands(self):
        """Handle a large number of strands."""
        strands = [
            [(i * 0.01, 0.0, j * 0.05) for j in range(5)]
            for i in range(100)
        ]
        result = compute_hair_card_mesh(strands, card_width=0.005)
        assert len(result["vertices"]) == 100 * 5 * 2
        assert len(result["faces"]) == 100 * 4


# ===================================================================
# Geometry Nodes preset code generators (Gap #78)
# ===================================================================

# Allowed imports for generated code (only bpy is expected)
_ALLOWED_IMPORTS = {"bpy"}


def _assert_valid_python(code: str, name: str = "preset"):
    """Assert that generated code is valid Python that can be parsed."""
    try:
        ast.parse(code)
    except SyntaxError as e:
        pytest.fail(f"Generated {name} code has syntax error: {e}\n\nCode:\n{code}")


def _extract_imports(code: str) -> set[str]:
    """Extract imported module names from generated code."""
    tree = ast.parse(code)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _code_contains_node_type(code: str, node_type: str) -> bool:
    """Check if generated code references a specific GN node type."""
    return node_type in code


class TestScatterPresetCode:
    """Tests for generate_scatter_preset_code."""

    def test_generates_valid_python(self):
        code = generate_scatter_preset_code("Terrain", "Rock", density=5.0)
        _assert_valid_python(code, "scatter")

    def test_only_allowed_imports(self):
        code = generate_scatter_preset_code("Terrain", "Rock")
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS, f"Unexpected imports: {imports - _ALLOWED_IMPORTS}"

    def test_contains_distribute_points(self):
        code = generate_scatter_preset_code("Terrain", "Rock")
        assert _code_contains_node_type(code, "GeometryNodeDistributePointsOnFaces")

    def test_contains_instance_on_points(self):
        code = generate_scatter_preset_code("Terrain", "Rock")
        assert _code_contains_node_type(code, "GeometryNodeInstanceOnPoints")

    def test_contains_target_name(self):
        code = generate_scatter_preset_code("MyTerrain", "MyRock")
        assert "MyTerrain" in code
        assert "MyRock" in code

    def test_contains_density_value(self):
        code = generate_scatter_preset_code("T", "R", density=42.5)
        assert "42.5" in code

    def test_contains_seed_value(self):
        code = generate_scatter_preset_code("T", "R", seed=777)
        assert "777" in code

    def test_contains_join_geometry(self):
        code = generate_scatter_preset_code("T", "R")
        assert _code_contains_node_type(code, "GeometryNodeJoinGeometry")


class TestBooleanPresetCode:
    """Tests for generate_boolean_preset_code."""

    def test_generates_valid_python(self):
        code = generate_boolean_preset_code("Base", ["Cutter1"])
        _assert_valid_python(code, "boolean")

    def test_only_allowed_imports(self):
        code = generate_boolean_preset_code("Base", ["Cutter1"])
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS

    def test_contains_mesh_boolean(self):
        code = generate_boolean_preset_code("Base", ["Cutter1"])
        assert _code_contains_node_type(code, "GeometryNodeMeshBoolean")

    def test_single_cutter(self):
        code = generate_boolean_preset_code("Base", ["Cutter1"])
        _assert_valid_python(code, "boolean_single")
        assert "Cutter1" in code

    def test_multiple_cutters(self):
        """Boolean with multiple cutters should chain them."""
        cutters = ["Cutter1", "Cutter2", "Cutter3"]
        code = generate_boolean_preset_code("Base", cutters)
        _assert_valid_python(code, "boolean_multi")
        for c in cutters:
            assert c in code
        # Should have 3 boolean nodes
        assert code.count("GeometryNodeMeshBoolean") == 3

    def test_operation_types(self):
        for op in ["UNION", "DIFFERENCE", "INTERSECT"]:
            code = generate_boolean_preset_code("Base", ["C"], operation=op)
            _assert_valid_python(code, f"boolean_{op}")
            assert op in code

    def test_two_cutters_chained(self):
        """Two cutters should chain: first boolean feeds into second."""
        code = generate_boolean_preset_code("Base", ["A", "B"])
        _assert_valid_python(code, "boolean_chain")
        # Should reference boolean_0 output going to boolean_1 input
        assert "boolean_0" in code
        assert "boolean_1" in code


class TestArrayCurvePresetCode:
    """Tests for generate_array_curve_preset_code."""

    def test_generates_valid_python(self):
        code = generate_array_curve_preset_code("Pillar", "Path", count=20)
        _assert_valid_python(code, "array_curve")

    def test_only_allowed_imports(self):
        code = generate_array_curve_preset_code("Pillar", "Path")
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS

    def test_contains_instance_on_points(self):
        code = generate_array_curve_preset_code("Pillar", "Path")
        assert _code_contains_node_type(code, "GeometryNodeInstanceOnPoints")

    def test_contains_curve_to_points(self):
        """Array along curve should use CurveToPoints or ResampleCurve."""
        code = generate_array_curve_preset_code("Pillar", "Path")
        assert (
            _code_contains_node_type(code, "GeometryNodeCurveToPoints")
            or _code_contains_node_type(code, "GeometryNodeResampleCurve")
        )

    def test_contains_count(self):
        code = generate_array_curve_preset_code("P", "C", count=15)
        assert "15" in code

    def test_contains_object_names(self):
        code = generate_array_curve_preset_code("FencePole", "FencePath")
        assert "FencePole" in code
        assert "FencePath" in code


class TestVertexDisplacementCode:
    """Tests for generate_vertex_displacement_code."""

    def test_generates_valid_python(self):
        code = generate_vertex_displacement_code("Terrain", scale=0.5, noise_scale=3.0)
        _assert_valid_python(code, "vertex_displacement")

    def test_only_allowed_imports(self):
        code = generate_vertex_displacement_code("Terrain")
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS

    def test_contains_set_position(self):
        code = generate_vertex_displacement_code("Terrain")
        assert _code_contains_node_type(code, "GeometryNodeSetPosition")

    def test_contains_noise_texture(self):
        code = generate_vertex_displacement_code("Terrain")
        assert _code_contains_node_type(code, "ShaderNodeTexNoise")

    def test_contains_input_normal(self):
        code = generate_vertex_displacement_code("Terrain")
        assert _code_contains_node_type(code, "GeometryNodeInputNormal")

    def test_contains_scale_param(self):
        code = generate_vertex_displacement_code("T", scale=0.42)
        assert "0.42" in code

    def test_contains_noise_scale_param(self):
        code = generate_vertex_displacement_code("T", noise_scale=7.5)
        assert "7.5" in code


class TestEdgeWearMaskCode:
    """Tests for _generate_edge_wear_mask_code."""

    def test_generates_valid_python(self):
        code = _generate_edge_wear_mask_code("Sword")
        _assert_valid_python(code, "edge_wear")

    def test_only_allowed_imports(self):
        code = _generate_edge_wear_mask_code("Sword")
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS

    def test_contains_edge_angle(self):
        code = _generate_edge_wear_mask_code("Sword")
        assert _code_contains_node_type(code, "GeometryNodeInputMeshEdgeAngle")

    def test_contains_store_attribute(self):
        code = _generate_edge_wear_mask_code("Sword")
        assert _code_contains_node_type(code, "GeometryNodeStoreNamedAttribute")
        assert "edge_wear" in code


class TestProximityBlendCode:
    """Tests for _generate_proximity_blend_code."""

    def test_generates_valid_python(self):
        code = _generate_proximity_blend_code("Target", "Proxy")
        _assert_valid_python(code, "proximity_blend")

    def test_only_allowed_imports(self):
        code = _generate_proximity_blend_code("Target", "Proxy")
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS

    def test_contains_proximity_node(self):
        code = _generate_proximity_blend_code("Target", "Proxy")
        assert _code_contains_node_type(code, "GeometryNodeProximity")


class TestRandomScaleRotationCode:
    """Tests for _generate_random_scale_rotation_code."""

    def test_generates_valid_python(self):
        code = _generate_random_scale_rotation_code("Instances")
        _assert_valid_python(code, "random_scale_rotation")

    def test_only_allowed_imports(self):
        code = _generate_random_scale_rotation_code("Instances")
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS

    def test_contains_rotate_instances(self):
        code = _generate_random_scale_rotation_code("Instances")
        assert _code_contains_node_type(code, "GeometryNodeRotateInstances")

    def test_contains_scale_instances(self):
        code = _generate_random_scale_rotation_code("Instances")
        assert _code_contains_node_type(code, "GeometryNodeScaleInstances")

    def test_contains_random_value(self):
        code = _generate_random_scale_rotation_code("Instances")
        assert _code_contains_node_type(code, "FunctionNodeRandomValue")


class TestSubdivisionSmoothCode:
    """Tests for _generate_subdivision_smooth_code."""

    def test_generates_valid_python(self):
        code = _generate_subdivision_smooth_code("Mesh")
        _assert_valid_python(code, "subdivision")

    def test_only_allowed_imports(self):
        code = _generate_subdivision_smooth_code("Mesh")
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS

    def test_contains_subdivision_surface(self):
        code = _generate_subdivision_smooth_code("Mesh")
        assert _code_contains_node_type(code, "GeometryNodeSubdivisionSurface")


class TestAllPresetsParseClean:
    """Verify every preset generates valid Python with only allowed imports."""

    @pytest.mark.parametrize("preset_name", sorted(VALID_GN_PRESETS))
    def test_preset_parses(self, preset_name):
        """Each preset should generate parseable Python code."""
        # Build minimal args for each preset
        if preset_name == "scatter_on_surface":
            code = generate_scatter_preset_code("A", "B")
        elif preset_name == "boolean_union":
            code = generate_boolean_preset_code("A", ["B"])
        elif preset_name == "subdivision_smooth":
            code = _generate_subdivision_smooth_code("A")
        elif preset_name == "vertex_displacement":
            code = generate_vertex_displacement_code("A")
        elif preset_name == "edge_wear_mask":
            code = _generate_edge_wear_mask_code("A")
        elif preset_name == "proximity_blend":
            code = _generate_proximity_blend_code("A", "B")
        elif preset_name == "array_along_curve":
            code = generate_array_curve_preset_code("A", "B")
        elif preset_name == "random_scale_rotation":
            code = _generate_random_scale_rotation_code("A")
        else:
            pytest.fail(f"No test mapping for preset: {preset_name}")

        _assert_valid_python(code, preset_name)
        imports = _extract_imports(code)
        assert imports <= _ALLOWED_IMPORTS, (
            f"Preset {preset_name} has unauthorized imports: {imports - _ALLOWED_IMPORTS}"
        )


# ===================================================================
# Pure-logic helper tests
# ===================================================================

class TestFaceAreaNormalCentroid:
    """Tests for the internal geometry helpers."""

    def test_unit_square_area(self):
        area = _face_area(_UNIT_SQUARE_VERTS, (0, 1, 2, 3))
        assert abs(area - 1.0) < 1e-6

    def test_triangle_area(self):
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        area = _face_area(verts, (0, 1, 2))
        assert abs(area - 0.5) < 1e-6

    def test_unit_square_normal(self):
        normal = _face_normal(_UNIT_SQUARE_VERTS, (0, 1, 2, 3))
        assert abs(normal[0]) < 1e-6
        assert abs(normal[1]) < 1e-6
        assert abs(abs(normal[2]) - 1.0) < 1e-6

    def test_centroid(self):
        centroid = _face_centroid(_UNIT_SQUARE_VERTS, (0, 1, 2, 3))
        assert abs(centroid[0] - 0.5) < 1e-6
        assert abs(centroid[1] - 0.5) < 1e-6
        assert abs(centroid[2]) < 1e-6

    def test_degenerate_face_normal_fallback(self):
        """Degenerate face (all same point) should return fallback normal."""
        verts = [(0, 0, 0), (0, 0, 0), (0, 0, 0)]
        normal = _face_normal(verts, (0, 1, 2))
        # Should return fallback (0, 0, 1) without crashing
        assert len(normal) == 3
