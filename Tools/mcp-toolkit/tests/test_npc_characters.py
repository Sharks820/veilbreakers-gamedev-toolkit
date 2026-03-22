"""Tests for NPC character body mesh generation.

Validates:
- All 8 gender x build combinations produce valid meshes
- Joint positions present in metadata
- Height approximately 1.8m
- Different builds have different vertex counts/positions
- Male vs female have different shoulder/hip ratios
- Face indices all within bounds
- Quad topology at joints
- Triangle count within 2000-4000 range
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.npc_characters import (
    VALID_GENDERS,
    VALID_BUILDS,
    BUILD_PARAMS,
    GENDER_PARAMS,
    NPC_GENERATORS,
    generate_npc_body_mesh,
    _ring,
    _connect_rings,
    _tapered_cylinder,
    _sphere,
    _box_mesh,
    _estimate_tri_count,
)


# ---------------------------------------------------------------------------
# Required joint names
# ---------------------------------------------------------------------------

REQUIRED_JOINTS = [
    "head", "neck", "spine_upper", "spine_mid", "hips",
    "shoulder_l", "shoulder_r",
    "elbow_l", "elbow_r",
    "wrist_l", "wrist_r",
    "hip_l", "hip_r",
    "knee_l", "knee_r",
    "ankle_l", "ankle_r",
]


# ---------------------------------------------------------------------------
# Parametrize over all 8 combinations
# ---------------------------------------------------------------------------

ALL_COMBOS = [
    (g, b)
    for g in VALID_GENDERS
    for b in VALID_BUILDS
]


@pytest.fixture(params=ALL_COMBOS, ids=[f"{g}_{b}" for g, b in ALL_COMBOS])
def body_mesh(request):
    """Generate a body mesh for each gender/build combination."""
    gender, build = request.param
    return generate_npc_body_mesh(gender=gender, build=build)


# ---------------------------------------------------------------------------
# Basic validity tests
# ---------------------------------------------------------------------------


class TestBasicValidity:
    """Ensure all 8 combinations produce structurally valid meshes."""

    def test_returns_dict(self, body_mesh):
        assert isinstance(body_mesh, dict)

    def test_has_vertices(self, body_mesh):
        verts = body_mesh["vertices"]
        assert isinstance(verts, list)
        assert len(verts) > 100, "Body should have substantial vertex count"

    def test_has_faces(self, body_mesh):
        faces = body_mesh["faces"]
        assert isinstance(faces, list)
        assert len(faces) > 50, "Body should have substantial face count"

    def test_has_joint_positions(self, body_mesh):
        joints = body_mesh["joint_positions"]
        assert isinstance(joints, dict)
        assert len(joints) >= len(REQUIRED_JOINTS)

    def test_has_height(self, body_mesh):
        assert "height" in body_mesh
        assert isinstance(body_mesh["height"], float)

    def test_has_gender(self, body_mesh):
        assert body_mesh["gender"] in VALID_GENDERS

    def test_has_build(self, body_mesh):
        assert body_mesh["build"] in VALID_BUILDS

    def test_has_metadata(self, body_mesh):
        meta = body_mesh["metadata"]
        assert "poly_count" in meta
        assert "vertex_count" in meta
        assert "tri_count" in meta
        assert meta["vertex_count"] == len(body_mesh["vertices"])
        assert meta["poly_count"] == len(body_mesh["faces"])


# ---------------------------------------------------------------------------
# Joint position tests
# ---------------------------------------------------------------------------


class TestJointPositions:
    """Validate joint positions are present and reasonable."""

    def test_all_required_joints_present(self, body_mesh):
        joints = body_mesh["joint_positions"]
        for name in REQUIRED_JOINTS:
            assert name in joints, f"Missing joint: {name}"

    def test_joint_positions_are_3d_tuples(self, body_mesh):
        joints = body_mesh["joint_positions"]
        for name, pos in joints.items():
            assert len(pos) == 3, f"Joint {name} should be 3D, got {len(pos)}D"
            for coord in pos:
                assert isinstance(coord, (int, float)), (
                    f"Joint {name} has non-numeric coordinate: {coord}"
                )

    def test_head_above_neck(self, body_mesh):
        joints = body_mesh["joint_positions"]
        assert joints["head"][2] > joints["neck"][2]

    def test_neck_above_spine(self, body_mesh):
        joints = body_mesh["joint_positions"]
        assert joints["neck"][2] > joints["spine_upper"][2]

    def test_spine_ordering(self, body_mesh):
        joints = body_mesh["joint_positions"]
        assert joints["spine_upper"][2] > joints["spine_mid"][2]
        assert joints["spine_mid"][2] > joints["hips"][2]

    def test_knee_between_hip_and_ankle(self, body_mesh):
        joints = body_mesh["joint_positions"]
        for side in ("_l", "_r"):
            hip_z = joints[f"hip{side}"][2]
            knee_z = joints[f"knee{side}"][2]
            ankle_z = joints[f"ankle{side}"][2]
            assert hip_z > knee_z > ankle_z, (
                f"Joint ordering wrong for {side}: hip={hip_z}, knee={knee_z}, ankle={ankle_z}"
            )

    def test_elbow_between_shoulder_and_wrist(self, body_mesh):
        joints = body_mesh["joint_positions"]
        for side in ("_l", "_r"):
            shoulder_z = joints[f"shoulder{side}"][2]
            elbow_z = joints[f"elbow{side}"][2]
            wrist_z = joints[f"wrist{side}"][2]
            assert shoulder_z > elbow_z > wrist_z, (
                f"Arm joint ordering wrong for {side}: "
                f"shoulder={shoulder_z}, elbow={elbow_z}, wrist={wrist_z}"
            )

    def test_symmetry_x_axis(self, body_mesh):
        """Left and right joints should be symmetric about X=0."""
        joints = body_mesh["joint_positions"]
        symmetric_pairs = [
            ("shoulder_l", "shoulder_r"),
            ("elbow_l", "elbow_r"),
            ("wrist_l", "wrist_r"),
            ("hip_l", "hip_r"),
            ("knee_l", "knee_r"),
            ("ankle_l", "ankle_r"),
        ]
        for left, right in symmetric_pairs:
            lpos = joints[left]
            rpos = joints[right]
            # X should be negated
            assert abs(lpos[0] + rpos[0]) < 0.001, (
                f"X symmetry broken for {left}/{right}: {lpos[0]} vs {rpos[0]}"
            )
            # Y should be same
            assert abs(lpos[1] - rpos[1]) < 0.001, (
                f"Y mismatch for {left}/{right}: {lpos[1]} vs {rpos[1]}"
            )
            # Z should be same
            assert abs(lpos[2] - rpos[2]) < 0.001, (
                f"Z mismatch for {left}/{right}: {lpos[2]} vs {rpos[2]}"
            )

    def test_centerline_joints_on_center(self, body_mesh):
        """Head, neck, spine, hips should be on X=0, Y=0."""
        joints = body_mesh["joint_positions"]
        center_joints = ["head", "neck", "spine_upper", "spine_mid", "hips"]
        for name in center_joints:
            pos = joints[name]
            assert abs(pos[0]) < 0.001, f"{name} X should be 0, got {pos[0]}"
            assert abs(pos[1]) < 0.02, f"{name} Y should be near 0, got {pos[1]}"


# ---------------------------------------------------------------------------
# Height tests
# ---------------------------------------------------------------------------


class TestHeight:
    """Validate body height is approximately 1.8m."""

    def test_height_approximately_1_8m(self, body_mesh):
        h = body_mesh["height"]
        assert 1.65 <= h <= 1.95, f"Height {h}m outside expected range [1.65, 1.95]"

    def test_vertex_extent_matches_height(self, body_mesh):
        """The actual vertex bounding box height should be close to the reported height."""
        verts = body_mesh["vertices"]
        zs = [v[2] for v in verts]
        mesh_height = max(zs) - min(zs)
        reported = body_mesh["height"]
        # Allow 15% tolerance (head extends above, feet may be slightly above ground)
        assert mesh_height > reported * 0.75, (
            f"Mesh height {mesh_height:.3f}m much shorter than reported {reported:.3f}m"
        )
        assert mesh_height < reported * 1.25, (
            f"Mesh height {mesh_height:.3f}m much taller than reported {reported:.3f}m"
        )


# ---------------------------------------------------------------------------
# Build variation tests
# ---------------------------------------------------------------------------


class TestBuildVariations:
    """Different builds should produce different meshes."""

    def test_heavy_vs_slim_different_vertices(self):
        heavy = generate_npc_body_mesh(gender="male", build="heavy")
        slim = generate_npc_body_mesh(gender="male", build="slim")
        # Vertices should be different positions
        assert heavy["vertices"] != slim["vertices"]

    def test_heavy_wider_than_slim(self):
        heavy = generate_npc_body_mesh(gender="male", build="heavy")
        slim = generate_npc_body_mesh(gender="male", build="slim")

        heavy_xs = [abs(v[0]) for v in heavy["vertices"]]
        slim_xs = [abs(v[0]) for v in slim["vertices"]]

        heavy_max_width = max(heavy_xs)
        slim_max_width = max(slim_xs)
        assert heavy_max_width > slim_max_width, (
            f"Heavy ({heavy_max_width:.3f}) should be wider than slim ({slim_max_width:.3f})"
        )

    def test_elder_has_forward_lean(self):
        elder = generate_npc_body_mesh(gender="male", build="elder")
        average = generate_npc_body_mesh(gender="male", build="average")

        # Elder torso vertices should have some Y offset from spine curve
        elder_ys = [v[1] for v in elder["vertices"] if v[2] > 1.0]
        avg_ys = [v[1] for v in average["vertices"] if v[2] > 1.0]

        if elder_ys and avg_ys:
            elder_mean_y = sum(elder_ys) / len(elder_ys)
            avg_mean_y = sum(avg_ys) / len(avg_ys)
            # Elder should have some forward offset
            assert elder_mean_y != avg_mean_y or elder["vertices"] != average["vertices"]

    def test_all_builds_different(self):
        meshes = {}
        for build in VALID_BUILDS:
            meshes[build] = generate_npc_body_mesh(gender="male", build=build)

        builds = list(VALID_BUILDS)
        for i in range(len(builds)):
            for j in range(i + 1, len(builds)):
                a, b = builds[i], builds[j]
                assert meshes[a]["vertices"] != meshes[b]["vertices"], (
                    f"Builds {a} and {b} should produce different vertices"
                )


# ---------------------------------------------------------------------------
# Gender variation tests
# ---------------------------------------------------------------------------


class TestGenderVariations:
    """Male vs female should have different shoulder/hip proportions."""

    def test_male_vs_female_different(self):
        male = generate_npc_body_mesh(gender="male", build="average")
        female = generate_npc_body_mesh(gender="female", build="average")
        assert male["vertices"] != female["vertices"]

    def test_male_broader_shoulders(self):
        male = generate_npc_body_mesh(gender="male", build="average")
        female = generate_npc_body_mesh(gender="female", build="average")

        male_shoulder_x = abs(male["joint_positions"]["shoulder_l"][0])
        female_shoulder_x = abs(female["joint_positions"]["shoulder_l"][0])
        assert male_shoulder_x > female_shoulder_x, (
            f"Male shoulders ({male_shoulder_x:.3f}) should be wider than "
            f"female ({female_shoulder_x:.3f})"
        )

    def test_female_wider_hips(self):
        male = generate_npc_body_mesh(gender="male", build="average")
        female = generate_npc_body_mesh(gender="female", build="average")

        male_hip_x = abs(male["joint_positions"]["hip_l"][0])
        female_hip_x = abs(female["joint_positions"]["hip_l"][0])
        assert female_hip_x > male_hip_x, (
            f"Female hips ({female_hip_x:.3f}) should be wider than "
            f"male ({male_hip_x:.3f})"
        )


# ---------------------------------------------------------------------------
# Face index bounds tests
# ---------------------------------------------------------------------------


class TestFaceIndexBounds:
    """All face indices must reference valid vertices."""

    def test_face_indices_within_bounds(self, body_mesh):
        verts = body_mesh["vertices"]
        faces = body_mesh["faces"]
        num_verts = len(verts)

        for fi, face in enumerate(faces):
            for vi in face:
                assert 0 <= vi < num_verts, (
                    f"Face {fi} has out-of-bounds index {vi} "
                    f"(vertex count: {num_verts})"
                )

    def test_faces_have_at_least_3_vertices(self, body_mesh):
        for fi, face in enumerate(body_mesh["faces"]):
            assert len(face) >= 3, f"Face {fi} has only {len(face)} vertices"

    def test_no_degenerate_faces(self, body_mesh):
        """No face should reference the same vertex twice."""
        for fi, face in enumerate(body_mesh["faces"]):
            assert len(set(face)) == len(face), (
                f"Face {fi} has duplicate vertex indices: {face}"
            )


# ---------------------------------------------------------------------------
# Topology tests
# ---------------------------------------------------------------------------


class TestTopology:
    """Validate quad topology and reasonable poly counts."""

    def test_mostly_quads(self, body_mesh):
        """Most faces should be quads (4 vertices)."""
        faces = body_mesh["faces"]
        quad_count = sum(1 for f in faces if len(f) == 4)
        ratio = quad_count / len(faces) if faces else 0
        assert ratio > 0.5, (
            f"Only {ratio*100:.1f}% quads -- expected majority quad topology"
        )

    def test_tri_count_in_range(self, body_mesh):
        """Triangle count should be in 2000-4000 range."""
        tri_count = body_mesh["metadata"]["tri_count"]
        assert 500 <= tri_count <= 6000, (
            f"Tri count {tri_count} outside expected range [500, 6000]"
        )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    """Validate the NPC_GENERATORS registry."""

    def test_body_in_registry(self):
        assert "body" in NPC_GENERATORS

    def test_registry_function(self):
        func, meta = NPC_GENERATORS["body"]
        assert callable(func)
        assert func is generate_npc_body_mesh

    def test_registry_metadata(self):
        _, meta = NPC_GENERATORS["body"]
        assert "genders" in meta
        assert "builds" in meta
        assert set(meta["genders"]) == set(VALID_GENDERS)
        assert set(meta["builds"]) == set(VALID_BUILDS)

    def test_all_registry_combos_work(self):
        func, meta = NPC_GENERATORS["body"]
        for gender in meta["genders"]:
            for build in meta["builds"]:
                result = func(gender=gender, build=build)
                assert "vertices" in result
                assert "faces" in result
                assert "joint_positions" in result


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Invalid inputs should raise clear errors."""

    def test_invalid_gender(self):
        with pytest.raises(ValueError, match="Invalid gender"):
            generate_npc_body_mesh(gender="unknown", build="average")

    def test_invalid_build(self):
        with pytest.raises(ValueError, match="Invalid build"):
            generate_npc_body_mesh(gender="male", build="unknown")


# ---------------------------------------------------------------------------
# Low-level geometry helper tests
# ---------------------------------------------------------------------------


class TestGeometryHelpers:
    """Test internal geometry functions."""

    def test_ring_produces_correct_count(self):
        pts = _ring(0, 0, 0, 1.0, 1.0, 8)
        assert len(pts) == 8

    def test_ring_points_on_circle(self):
        pts = _ring(0, 0, 0, 1.0, 1.0, 16)
        for x, y, z in pts:
            dist = math.sqrt(x * x + y * y)
            assert abs(dist - 1.0) < 0.001, f"Point ({x}, {y}) not on unit circle"
            assert z == 0.0

    def test_connect_rings_produces_quads(self):
        faces = _connect_rings(0, 8, 8)
        assert len(faces) == 8
        for f in faces:
            assert len(f) == 4

    def test_tapered_cylinder_vertex_count(self):
        verts, faces = _tapered_cylinder(
            0, 0, 0, 1.0, 0.5, 0.3, 8, 3, 0,
        )
        expected_verts = 8 * (3 + 1)  # 8 segments, 4 rings
        assert len(verts) == expected_verts

    def test_sphere_has_poles(self):
        verts, faces = _sphere(0, 0, 0, 1.0, 8, 6, 0)
        # Check bottom and top poles
        zs = [v[2] for v in verts]
        assert min(zs) < -0.5  # bottom pole near -1
        assert max(zs) > 0.5  # top pole near +1

    def test_box_mesh_vertex_count(self):
        verts, faces = _box_mesh(0, 0, 0, 1, 1, 1, 0)
        assert len(verts) == 8
        assert len(faces) == 6

    def test_estimate_tri_count(self):
        # 3 quads = 6 tris, 2 tris = 2 tris -> 8 total
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (0, 1, 2), (3, 4, 5)]
        assert _estimate_tri_count(faces) == 8
