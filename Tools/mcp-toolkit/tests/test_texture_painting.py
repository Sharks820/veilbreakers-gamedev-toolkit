"""Unit tests for multi-channel texture painting and projection/stencil painting.

Tests all pure-logic functions without Blender:
  - compute_projection_uvs (camera, planar, cylindrical, spherical)
  - compute_box_projection_uvs (tri-planar)
  - apply_stencil_mask
  - compute_multi_channel_blend
  - Validation helpers
  - Blend mode semantics

All tests run without bpy.
"""

import math

import pytest

from blender_addon.handlers.texture_painting import (
    VALID_BLEND_MODES,
    VALID_PAINT_CHANNELS,
    VALID_PROJECTION_TYPES,
    apply_stencil_mask,
    compute_box_projection_uvs,
    compute_multi_channel_blend,
    compute_projection_uvs,
    validate_blend_mode,
    validate_paint_channels,
    validate_projection_type,
)


# ---------------------------------------------------------------------------
# Canonical mesh geometries
# ---------------------------------------------------------------------------

# Unit cube centered at origin: 8 verts, 6 quad faces
CUBE_VERTICES = [
    (-1.0, -1.0, -1.0),  # 0: bottom-left-back
    ( 1.0, -1.0, -1.0),  # 1: bottom-right-back
    ( 1.0,  1.0, -1.0),  # 2: top-right-back
    (-1.0,  1.0, -1.0),  # 3: top-left-back
    (-1.0, -1.0,  1.0),  # 4: bottom-left-front
    ( 1.0, -1.0,  1.0),  # 5: bottom-right-front
    ( 1.0,  1.0,  1.0),  # 6: top-right-front
    (-1.0,  1.0,  1.0),  # 7: top-left-front
]

CUBE_FACES = [
    (0, 1, 2, 3),  # back  (-Z)
    (4, 7, 6, 5),  # front (+Z)
    (0, 3, 7, 4),  # left  (-X)
    (1, 5, 6, 2),  # right (+X)
    (0, 4, 5, 1),  # bottom (-Y)
    (3, 2, 6, 7),  # top    (+Y)
]

CUBE_FACE_NORMALS = [
    ( 0.0,  0.0, -1.0),  # back
    ( 0.0,  0.0,  1.0),  # front
    (-1.0,  0.0,  0.0),  # left
    ( 1.0,  0.0,  0.0),  # right
    ( 0.0, -1.0,  0.0),  # bottom
    ( 0.0,  1.0,  0.0),  # top
]

# Flat plane at Z=0 on XY
PLANE_VERTICES = [
    (-1.0, -1.0, 0.0),
    ( 1.0, -1.0, 0.0),
    ( 1.0,  1.0, 0.0),
    (-1.0,  1.0, 0.0),
]

PLANE_FACES = [(0, 1, 2, 3)]
PLANE_FACE_NORMALS = [(0.0, 0.0, 1.0)]

# Vertices on a unit sphere (6 cardinal points)
SPHERE_VERTICES = [
    ( 0.0,  1.0,  0.0),  # 0: north pole (+Y)
    ( 0.0, -1.0,  0.0),  # 1: south pole (-Y)
    ( 1.0,  0.0,  0.0),  # 2: +X
    (-1.0,  0.0,  0.0),  # 3: -X
    ( 0.0,  0.0,  1.0),  # 4: +Z
    ( 0.0,  0.0, -1.0),  # 5: -Z
]


# ===========================================================================
# Validation tests
# ===========================================================================

class TestValidation:
    """Test validation helpers reject bad inputs."""

    def test_valid_projection_types_accepted(self):
        for pt in VALID_PROJECTION_TYPES:
            validate_projection_type(pt)  # Should not raise

    def test_invalid_projection_type_rejected(self):
        with pytest.raises(ValueError, match="Invalid projection type"):
            validate_projection_type("cubemap")

    def test_empty_string_projection_type_rejected(self):
        with pytest.raises(ValueError):
            validate_projection_type("")

    def test_valid_blend_modes_accepted(self):
        for bm in VALID_BLEND_MODES:
            validate_blend_mode(bm)

    def test_invalid_blend_mode_rejected(self):
        with pytest.raises(ValueError, match="Invalid blend mode"):
            validate_blend_mode("BURN")

    def test_case_sensitive_blend_mode(self):
        with pytest.raises(ValueError):
            validate_blend_mode("mix")  # lowercase

    def test_valid_channels_accepted(self):
        validate_paint_channels(list(VALID_PAINT_CHANNELS))

    def test_invalid_channel_rejected(self):
        with pytest.raises(ValueError, match="Invalid paint channel"):
            validate_paint_channels(["color", "albedo"])

    def test_empty_channels_accepted(self):
        validate_paint_channels([])  # no channels = nothing to reject


# ===========================================================================
# Camera projection tests
# ===========================================================================

class TestCameraProjection:
    """Test perspective camera projection."""

    def test_front_facing_vertices_in_range(self):
        """Vertices in front of the camera produce UVs in [0, 1]."""
        camera_pos = (0.0, 0.0, 5.0)
        camera_target = (0.0, 0.0, 0.0)
        uvs = compute_projection_uvs(
            PLANE_VERTICES, PLANE_FACES, "camera",
            camera_pos=camera_pos, camera_target=camera_target, fov=60.0,
        )
        assert len(uvs) == len(PLANE_VERTICES)
        for u, v in uvs:
            assert 0.0 <= u <= 1.0, f"U={u} out of [0,1]"
            assert 0.0 <= v <= 1.0, f"V={v} out of [0,1]"

    def test_vertices_behind_camera_clipped(self):
        """Vertices behind the camera get (-1, -1)."""
        # Camera at origin looking +Z, vertices at Z=-1 (behind)
        behind_verts = [(0.0, 0.0, -1.0), (1.0, 0.0, -2.0)]
        camera_pos = (0.0, 0.0, 0.0)
        camera_target = (0.0, 0.0, 1.0)
        uvs = compute_projection_uvs(
            behind_verts, [], "camera",
            camera_pos=camera_pos, camera_target=camera_target,
        )
        for u, v in uvs:
            assert u == -1.0 and v == -1.0, f"Expected clipped (-1,-1), got ({u},{v})"

    def test_mixed_front_and_behind(self):
        """Mix of front and behind vertices: behind gets clipped, front in range."""
        verts = [
            (0.0, 0.0, 2.0),   # in front
            (0.0, 0.0, -1.0),  # behind
            (1.0, 1.0, 3.0),   # in front
        ]
        camera_pos = (0.0, 0.0, 0.0)
        camera_target = (0.0, 0.0, 1.0)
        uvs = compute_projection_uvs(
            verts, [], "camera",
            camera_pos=camera_pos, camera_target=camera_target,
        )
        # Behind vertex (index 1) should be clipped
        assert uvs[1] == (-1.0, -1.0)
        # Front vertices should be in range
        for idx in [0, 2]:
            assert 0.0 <= uvs[idx][0] <= 1.0
            assert 0.0 <= uvs[idx][1] <= 1.0

    def test_camera_missing_params_raises(self):
        with pytest.raises(ValueError, match="camera_pos and camera_target"):
            compute_projection_uvs(PLANE_VERTICES, [], "camera")

    def test_all_behind_returns_all_clipped(self):
        """When all vertices are behind the camera, all UVs are (-1, -1)."""
        verts = [(0.0, 0.0, -1.0), (1.0, 0.0, -2.0)]
        uvs = compute_projection_uvs(
            verts, [], "camera",
            camera_pos=(0.0, 0.0, 0.0), camera_target=(0.0, 0.0, 1.0),
        )
        for u, v in uvs:
            assert (u, v) == (-1.0, -1.0)

    def test_symmetric_vertices_symmetric_uvs(self):
        """Two vertices symmetric about the camera axis should have symmetric UVs."""
        verts = [(-1.0, 0.0, 3.0), (1.0, 0.0, 3.0)]
        uvs = compute_projection_uvs(
            verts, [], "camera",
            camera_pos=(0.0, 0.0, 0.0), camera_target=(0.0, 0.0, 1.0), fov=90.0,
        )
        # U values should be symmetric around 0.5
        assert abs(uvs[0][0] + uvs[1][0] - 1.0) < 1e-6, \
            f"Expected symmetric U: {uvs[0][0]} + {uvs[1][0]} != 1.0"
        # V values should be equal (same height)
        assert abs(uvs[0][1] - uvs[1][1]) < 1e-6

    def test_empty_vertices(self):
        uvs = compute_projection_uvs(
            [], [], "camera",
            camera_pos=(0.0, 0.0, 5.0), camera_target=(0.0, 0.0, 0.0),
        )
        assert uvs == []


# ===========================================================================
# Planar projection tests
# ===========================================================================

class TestPlanarProjection:
    """Test orthographic planar projection."""

    def test_xy_plane_uvs_in_range(self):
        """Projecting onto Z-normal plane produces UVs in [0, 1]."""
        uvs = compute_projection_uvs(
            PLANE_VERTICES, PLANE_FACES, "planar",
            plane_normal=(0.0, 0.0, 1.0), plane_point=(0.0, 0.0, 0.0),
        )
        assert len(uvs) == 4
        for u, v in uvs:
            assert 0.0 <= u <= 1.0
            assert 0.0 <= v <= 1.0

    def test_planar_all_same_depth(self):
        """All vertices at the same depth from the plane should project the same way.

        Vertices at different depths but same XY should map to the same UV,
        because planar projection ignores depth.
        """
        # Two vertices at same XY but different Z
        verts = [(1.0, 2.0, 0.0), (1.0, 2.0, 5.0), (0.0, 0.0, 0.0)]
        uvs = compute_projection_uvs(
            verts, [], "planar",
            plane_normal=(0.0, 0.0, 1.0), plane_point=(0.0, 0.0, 0.0),
        )
        # First two vertices should have same UV (same position on XY plane)
        assert abs(uvs[0][0] - uvs[1][0]) < 1e-6
        assert abs(uvs[0][1] - uvs[1][1]) < 1e-6

    def test_planar_missing_params_raises(self):
        with pytest.raises(ValueError, match="plane_normal and plane_point"):
            compute_projection_uvs(PLANE_VERTICES, [], "planar")

    def test_planar_cube_uvs_in_range(self):
        uvs = compute_projection_uvs(
            CUBE_VERTICES, CUBE_FACES, "planar",
            plane_normal=(0.0, 0.0, 1.0), plane_point=(0.0, 0.0, 0.0),
        )
        assert len(uvs) == 8
        for u, v in uvs:
            assert 0.0 <= u <= 1.0
            assert 0.0 <= v <= 1.0

    def test_planar_empty_vertices(self):
        uvs = compute_projection_uvs(
            [], [], "planar",
            plane_normal=(0.0, 0.0, 1.0), plane_point=(0.0, 0.0, 0.0),
        )
        assert uvs == []

    def test_planar_single_vertex(self):
        """Single vertex should map to (0, 0) or (0.5, 0.5) since there's no range."""
        uvs = compute_projection_uvs(
            [(1.0, 2.0, 3.0)], [], "planar",
            plane_normal=(0.0, 0.0, 1.0), plane_point=(0.0, 0.0, 0.0),
        )
        assert len(uvs) == 1
        # With a single point, normalisation maps to 0/0 (range is 0, denom is 1)
        assert 0.0 <= uvs[0][0] <= 1.0
        assert 0.0 <= uvs[0][1] <= 1.0


# ===========================================================================
# Cylindrical projection tests
# ===========================================================================

class TestCylindricalProjection:
    """Test cylindrical unwrap around Y axis."""

    def test_uvs_in_range(self):
        """All UVs should be in [0, 1]."""
        uvs = compute_projection_uvs(CUBE_VERTICES, CUBE_FACES, "cylindrical")
        for u, v in uvs:
            assert 0.0 <= u <= 1.0, f"U={u} out of range"
            assert 0.0 <= v <= 1.0, f"V={v} out of range"

    def test_wraps_around_y_axis(self):
        """U=0 and U=1 should correspond to the same seam angle (atan2 = -pi / +pi).

        Vertices at slightly positive and negative X at Z<0 should map
        near U=0 and U=1 respectively.
        """
        # Two vertices just across the seam at -Z
        verts = [
            ( 0.001, 0.0, -1.0),  # atan2(+eps, -1) ~ pi -> U ~ 1.0
            (-0.001, 0.0, -1.0),  # atan2(-eps, -1) ~ -pi -> U ~ 0.0
        ]
        uvs = compute_projection_uvs(verts, [], "cylindrical")
        # They should be at opposite ends of U range
        u_diff = abs(uvs[0][0] - uvs[1][0])
        assert u_diff > 0.9, f"Seam vertices should be far apart in U: diff={u_diff}"

    def test_height_maps_to_v(self):
        """Vertices at different Y should have different V values."""
        verts = [(1.0, -2.0, 0.0), (1.0, 0.0, 0.0), (1.0, 2.0, 0.0)]
        uvs = compute_projection_uvs(verts, [], "cylindrical")
        # V should be strictly increasing with Y
        assert uvs[0][1] < uvs[1][1] < uvs[2][1]

    def test_same_angle_different_radius(self):
        """Vertices at the same angle but different XZ distance should have the same U."""
        verts = [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
        uvs = compute_projection_uvs(verts, [], "cylindrical")
        assert abs(uvs[0][0] - uvs[1][0]) < 1e-6

    def test_empty(self):
        uvs = compute_projection_uvs([], [], "cylindrical")
        assert uvs == []

    def test_single_vertex(self):
        uvs = compute_projection_uvs([(1.0, 0.0, 0.0)], [], "cylindrical")
        assert len(uvs) == 1
        assert 0.0 <= uvs[0][0] <= 1.0
        assert 0.0 <= uvs[0][1] <= 1.0


# ===========================================================================
# Spherical projection tests
# ===========================================================================

class TestSphericalProjection:
    """Test equirectangular (spherical) projection."""

    def test_uvs_in_range(self):
        """All UVs in [0, 1]."""
        uvs = compute_projection_uvs(SPHERE_VERTICES, [], "spherical")
        for u, v in uvs:
            assert 0.0 <= u <= 1.0, f"U={u} out of range"
            assert 0.0 <= v <= 1.0, f"V={v} out of range"

    def test_north_pole(self):
        """North pole (+Y) maps to V=1.0."""
        uvs = compute_projection_uvs([(0.0, 1.0, 0.0)], [], "spherical")
        assert abs(uvs[0][1] - 1.0) < 1e-6, f"North pole V={uvs[0][1]}, expected 1.0"

    def test_south_pole(self):
        """South pole (-Y) maps to V=0.0."""
        uvs = compute_projection_uvs([(0.0, -1.0, 0.0)], [], "spherical")
        assert abs(uvs[0][1]) < 1e-6, f"South pole V={uvs[0][1]}, expected 0.0"

    def test_poles_u_is_half(self):
        """At the poles (pure Y), longitude is undefined; should default to U=0.5."""
        # North pole
        uvs_n = compute_projection_uvs([(0.0, 1.0, 0.0)], [], "spherical")
        assert abs(uvs_n[0][0] - 0.5) < 1e-6, f"North pole U={uvs_n[0][0]}, expected 0.5"

        # South pole
        uvs_s = compute_projection_uvs([(0.0, -1.0, 0.0)], [], "spherical")
        assert abs(uvs_s[0][0] - 0.5) < 1e-6, f"South pole U={uvs_s[0][0]}, expected 0.5"

    def test_equator_v_is_half(self):
        """Vertices on the equator (Y=0) map to V=0.5."""
        equator_verts = [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0)]
        uvs = compute_projection_uvs(equator_verts, [], "spherical")
        for i, (u, v) in enumerate(uvs):
            assert abs(v - 0.5) < 1e-6, f"Equator vert {i} V={v}, expected 0.5"

    def test_origin_vertex(self):
        """Vertex at origin maps to (0.5, 0.5)."""
        uvs = compute_projection_uvs([(0.0, 0.0, 0.0)], [], "spherical")
        assert abs(uvs[0][0] - 0.5) < 1e-6
        assert abs(uvs[0][1] - 0.5) < 1e-6

    def test_empty(self):
        uvs = compute_projection_uvs([], [], "spherical")
        assert uvs == []


# ===========================================================================
# Box (tri-planar) projection tests
# ===========================================================================

class TestBoxProjection:
    """Test tri-planar box projection UVs."""

    def test_uvs_in_range(self):
        """All UVs in [0, 1]."""
        uvs = compute_box_projection_uvs(
            CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS,
        )
        assert len(uvs) == 8
        for u, v in uvs:
            assert 0.0 <= u <= 1.0, f"U={u}"
            assert 0.0 <= v <= 1.0, f"V={v}"

    def test_x_aligned_face_uses_yz(self):
        """A face with normal along X should project using (Y, Z).

        We test this by creating a single-face mesh aligned with +X and
        verifying the UVs change when Y/Z change but not when X changes.
        """
        # Two verts differing only in X (same Y, Z)
        verts_x_only = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
        faces = [(0, 1, 2, 3)]
        normals = [(1.0, 0.0, 0.0)]  # X-aligned

        uvs = compute_box_projection_uvs(verts_x_only, faces, normals, blend_amount=0.0)

        # Verts 0 and 1 differ only in X -> with X-axis projection (YZ), same UV
        # But normalisation maps them based on their Y and Z
        # Vert 0: Y=0, Z=0
        # Vert 1: Y=0, Z=0 (X differs but ignored in YZ projection)
        # Both have Y=0 and Z=0, so they should be mapped to the same UV
        assert abs(uvs[0][0] - uvs[1][0]) < 1e-6, \
            f"X-only diff should give same U in YZ projection: {uvs[0]} vs {uvs[1]}"
        assert abs(uvs[0][1] - uvs[1][1]) < 1e-6

    def test_blend_zero_uses_dominant_axis_only(self):
        """With blend_amount=0, only the dominant axis contributes.

        We use a face with a clearly dominant normal axis (X) and a minor
        secondary (Z).  At blend=0 the minor axis is zeroed out; at
        blend=1 it contributes equally.  The geometry is chosen so that
        different projection axes produce visibly different UVs.
        """
        # Rectangular quad: large range in X (0..3), Y (0..1), small Z range
        verts = [
            (0.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (3.0, 1.0, 0.2),
            (0.0, 1.0, 0.2),
        ]
        faces = [(0, 1, 2, 3)]
        # Normal strongly X-dominant but with Z secondary
        normals = [(0.9, 0.0, 0.3)]

        uvs_no_blend = compute_box_projection_uvs(
            verts, faces, normals, blend_amount=0.0,
        )
        uvs_full_blend = compute_box_projection_uvs(
            verts, faces, normals, blend_amount=1.0,
        )

        # At blend=0, X dominates: projection is (Y, Z).
        # At blend=1 (all axes equal weight), Z-projection (X, Y) mixes in,
        # which has a very different X range (0..3) vs Y/Z range.
        # Verify: at blend=0 the UVs should purely reflect YZ positions.
        # Verts 0 and 1 have identical Y and Z -> identical UVs at blend=0
        assert abs(uvs_no_blend[0][0] - uvs_no_blend[1][0]) < 1e-6, \
            "At blend=0, verts differing only in X should have same U (YZ projection)"
        assert abs(uvs_no_blend[0][1] - uvs_no_blend[1][1]) < 1e-6, \
            "At blend=0, verts differing only in X should have same V (YZ projection)"

        # At blend=1, the Z-axis projection (XY) contributes, so verts 0 and 1
        # (which differ in X by 3.0) should have different UVs.
        u_diff_blend = abs(uvs_full_blend[0][0] - uvs_full_blend[1][0])
        assert u_diff_blend > 0.1, \
            f"At blend=1, X-different verts should have different U: diff={u_diff_blend}"

    def test_empty_vertices(self):
        uvs = compute_box_projection_uvs([], [], [])
        assert uvs == []

    def test_vertex_not_in_any_face(self):
        """Vertices not referenced by any face should still get valid UVs."""
        verts = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
        faces = []  # no faces reference these vertices
        normals = []
        uvs = compute_box_projection_uvs(verts, faces, normals)
        assert len(uvs) == 2
        for u, v in uvs:
            assert 0.0 <= u <= 1.0
            assert 0.0 <= v <= 1.0

    def test_single_face_z_aligned(self):
        """A Z-aligned face should project using XY."""
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
        faces = [(0, 1, 2, 3)]
        normals = [(0.0, 0.0, 1.0)]  # Z-aligned
        uvs = compute_box_projection_uvs(verts, faces, normals, blend_amount=0.0)

        # With Z-aligned face and blend=0, projection is XY
        # Vert 0 (0,0,0) -> U = Xnorm, V = Ynorm -> (0.0, 0.0)
        # Vert 2 (1,1,0) -> U = Xnorm, V = Ynorm -> (1.0, 1.0)
        assert abs(uvs[0][0] - 0.0) < 1e-6
        assert abs(uvs[0][1] - 0.0) < 1e-6
        assert abs(uvs[2][0] - 1.0) < 1e-6
        assert abs(uvs[2][1] - 1.0) < 1e-6

    def test_plane_geometry_uvs(self):
        """Plane with Z-normal should produce clean XY projection UVs."""
        uvs = compute_box_projection_uvs(
            PLANE_VERTICES, PLANE_FACES, PLANE_FACE_NORMALS, blend_amount=0.0,
        )
        assert len(uvs) == 4
        for u, v in uvs:
            assert 0.0 <= u <= 1.0
            assert 0.0 <= v <= 1.0


# ===========================================================================
# Stencil mask tests
# ===========================================================================

class TestStencilMask:
    """Test apply_stencil_mask."""

    def test_mask_zero_no_paint(self):
        """Mask value 0 should produce alpha = 0 (no paint)."""
        result = apply_stencil_mask((1.0, 0.0, 0.0, 1.0), 0.0, 1.0)
        assert result[3] == 0.0, f"Alpha={result[3]}, expected 0.0"

    def test_mask_one_full_paint(self):
        """Mask value 1 at full strength should preserve original alpha."""
        result = apply_stencil_mask((1.0, 0.0, 0.0, 1.0), 1.0, 1.0)
        assert abs(result[3] - 1.0) < 1e-6

    def test_mask_half_halves_alpha(self):
        """Mask value 0.5 at full strength should halve alpha."""
        result = apply_stencil_mask((1.0, 0.0, 0.0, 1.0), 0.5, 1.0)
        assert abs(result[3] - 0.5) < 1e-6

    def test_strength_modulates(self):
        """Strength 0.5 with mask 1.0 should halve alpha."""
        result = apply_stencil_mask((1.0, 0.0, 0.0, 1.0), 1.0, 0.5)
        assert abs(result[3] - 0.5) < 1e-6

    def test_mask_and_strength_multiply(self):
        """mask=0.5, strength=0.5 -> alpha = original * 0.25."""
        result = apply_stencil_mask((1.0, 1.0, 1.0, 0.8), 0.5, 0.5)
        expected = 0.8 * 0.5 * 0.5  # 0.2
        assert abs(result[3] - expected) < 1e-6

    def test_rgb_unchanged(self):
        """RGB channels should pass through unchanged."""
        result = apply_stencil_mask((0.2, 0.4, 0.6, 1.0), 0.5, 1.0)
        assert abs(result[0] - 0.2) < 1e-6
        assert abs(result[1] - 0.4) < 1e-6
        assert abs(result[2] - 0.6) < 1e-6

    def test_rgb_tuple_gets_alpha_appended(self):
        """An RGB-only tuple (3 components) should get alpha appended."""
        result = apply_stencil_mask((0.5, 0.5, 0.5), 1.0, 1.0)
        assert len(result) == 4
        assert abs(result[3] - 1.0) < 1e-6  # default alpha 1.0 * mask * strength

    def test_clamping(self):
        """Values are clamped to [0, 1]."""
        result = apply_stencil_mask((1.5, -0.2, 0.5, 1.0), 1.0, 1.0)
        assert result[0] == 1.0
        assert result[1] == 0.0
        assert 0.0 <= result[2] <= 1.0

    def test_mask_value_clamped(self):
        """Mask values outside [0, 1] are clamped."""
        result = apply_stencil_mask((1.0, 1.0, 1.0, 1.0), 2.0, 1.0)
        assert result[3] <= 1.0

    def test_zero_strength_no_paint(self):
        """Strength = 0 should produce alpha = 0."""
        result = apply_stencil_mask((1.0, 0.0, 0.0, 1.0), 1.0, 0.0)
        assert result[3] == 0.0


# ===========================================================================
# Multi-channel blend tests
# ===========================================================================

class TestMultiChannelBlend:
    """Test per-channel blending for multi-channel painting."""

    def test_mix_strength_zero_returns_existing(self):
        """MIX at strength=0 should return existing values unchanged."""
        existing = {"color": (0.5, 0.5, 0.5, 1.0), "roughness": 0.3}
        paint = {"color": (1.0, 0.0, 0.0, 1.0), "roughness": 0.9}
        result = compute_multi_channel_blend(existing, paint, 0.0, "MIX")
        assert abs(result["roughness"] - 0.3) < 1e-6
        for i in range(4):
            assert abs(result["color"][i] - existing["color"][i]) < 1e-6

    def test_mix_strength_one_returns_paint(self):
        """MIX at strength=1 should return paint values."""
        existing = {"color": (0.5, 0.5, 0.5, 1.0), "roughness": 0.3}
        paint = {"color": (1.0, 0.0, 0.0, 1.0), "roughness": 0.9}
        result = compute_multi_channel_blend(existing, paint, 1.0, "MIX")
        assert abs(result["roughness"] - 0.9) < 1e-6
        assert abs(result["color"][0] - 1.0) < 1e-6
        assert abs(result["color"][1] - 0.0) < 1e-6

    def test_mix_strength_half(self):
        """MIX at strength=0.5 should interpolate halfway."""
        existing = {"roughness": 0.0}
        paint = {"roughness": 1.0}
        result = compute_multi_channel_blend(existing, paint, 0.5, "MIX")
        assert abs(result["roughness"] - 0.5) < 1e-6

    def test_add_mode(self):
        """ADD should add paint * strength to existing."""
        existing = {"roughness": 0.3}
        paint = {"roughness": 0.2}
        result = compute_multi_channel_blend(existing, paint, 1.0, "ADD")
        assert abs(result["roughness"] - 0.5) < 1e-6

    def test_add_is_commutative_for_equal_values(self):
        """ADD(a, b) + ADD(b, a) should give equal results when strength = 1."""
        a_vals = {"roughness": 0.3}
        b_vals = {"roughness": 0.2}
        r1 = compute_multi_channel_blend(a_vals, b_vals, 1.0, "ADD")
        r2 = compute_multi_channel_blend(b_vals, a_vals, 1.0, "ADD")
        # ADD is a + b*s, so ADD(0.3, 0.2, 1) = 0.5, ADD(0.2, 0.3, 1) = 0.5
        assert abs(r1["roughness"] - r2["roughness"]) < 1e-6

    def test_multiply_mode(self):
        """MULTIPLY should multiply existing by lerp(1, paint, strength)."""
        existing = {"roughness": 0.8}
        paint = {"roughness": 0.5}
        result = compute_multi_channel_blend(existing, paint, 1.0, "MULTIPLY")
        # factor = 1 + (0.5 - 1) * 1 = 0.5; result = 0.8 * 0.5 = 0.4
        assert abs(result["roughness"] - 0.4) < 1e-6

    def test_overlay_mode(self):
        """OVERLAY on dark existing should darken (2*a*b formula)."""
        existing = {"roughness": 0.2}  # < 0.5 -> 2*a*b
        paint = {"roughness": 0.4}
        result = compute_multi_channel_blend(existing, paint, 1.0, "OVERLAY")
        overlay_val = 2.0 * 0.2 * 0.4  # = 0.16
        # result = existing + (overlay - existing) * strength = 0.2 + (0.16 - 0.2) * 1 = 0.16
        assert abs(result["roughness"] - overlay_val) < 1e-4

    def test_overlay_is_not_commutative(self):
        """OVERLAY(a,b) != OVERLAY(b,a) in general."""
        a_vals = {"roughness": 0.2}
        b_vals = {"roughness": 0.8}
        r1 = compute_multi_channel_blend(a_vals, b_vals, 1.0, "OVERLAY")
        r2 = compute_multi_channel_blend(b_vals, a_vals, 1.0, "OVERLAY")
        # OVERLAY is not commutative: existing < 0.5 and existing >= 0.5 use different formulas
        assert abs(r1["roughness"] - r2["roughness"]) > 0.01

    def test_screen_mode(self):
        """SCREEN: 1 - (1-a)(1-b)."""
        existing = {"roughness": 0.4}
        paint = {"roughness": 0.6}
        result = compute_multi_channel_blend(existing, paint, 1.0, "SCREEN")
        screen = 1.0 - (1.0 - 0.4) * (1.0 - 0.6)  # = 1 - 0.6*0.4 = 0.76
        expected = 0.4 + (screen - 0.4) * 1.0  # = 0.76
        assert abs(result["roughness"] - expected) < 1e-6

    def test_subtract_mode(self):
        """SUBTRACT should subtract paint * strength from existing."""
        existing = {"roughness": 0.8}
        paint = {"roughness": 0.3}
        result = compute_multi_channel_blend(existing, paint, 1.0, "SUBTRACT")
        assert abs(result["roughness"] - 0.5) < 1e-6

    def test_invalid_blend_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid blend mode"):
            compute_multi_channel_blend({"r": 0.5}, {"r": 0.5}, 1.0, "DODGE")

    def test_only_matching_channels_blended(self):
        """Only channels present in both dicts appear in output."""
        existing = {"color": (0.5, 0.5, 0.5, 1.0), "roughness": 0.3}
        paint = {"roughness": 0.9, "metallic": 0.5}  # metallic not in existing
        result = compute_multi_channel_blend(existing, paint, 1.0, "MIX")
        assert "roughness" in result
        assert "metallic" not in result
        assert "color" not in result  # not in paint

    def test_tuple_channel_blend(self):
        """Colour tuple channels should be blended component-wise."""
        existing = {"emission": (0.0, 0.0, 0.0)}
        paint = {"emission": (1.0, 0.5, 0.2)}
        result = compute_multi_channel_blend(existing, paint, 1.0, "MIX")
        assert abs(result["emission"][0] - 1.0) < 1e-6
        assert abs(result["emission"][1] - 0.5) < 1e-6
        assert abs(result["emission"][2] - 0.2) < 1e-6

    def test_clamped_to_zero_one(self):
        """Blended values should be clamped to [0, 1]."""
        existing = {"roughness": 0.9}
        paint = {"roughness": 0.5}
        result = compute_multi_channel_blend(existing, paint, 1.0, "ADD")
        assert result["roughness"] <= 1.0

        existing2 = {"roughness": 0.1}
        paint2 = {"roughness": 0.5}
        result2 = compute_multi_channel_blend(existing2, paint2, 1.0, "SUBTRACT")
        assert result2["roughness"] >= 0.0

    def test_strength_clamped(self):
        """Strength > 1.0 or < 0.0 should be clamped internally."""
        existing = {"roughness": 0.5}
        paint = {"roughness": 1.0}
        result_high = compute_multi_channel_blend(existing, paint, 5.0, "MIX")
        result_one = compute_multi_channel_blend(existing, paint, 1.0, "MIX")
        assert abs(result_high["roughness"] - result_one["roughness"]) < 1e-6

        result_neg = compute_multi_channel_blend(existing, paint, -1.0, "MIX")
        result_zero = compute_multi_channel_blend(existing, paint, 0.0, "MIX")
        assert abs(result_neg["roughness"] - result_zero["roughness"]) < 1e-6

    def test_type_mismatch_keeps_existing(self):
        """If types don't match (scalar vs tuple), keep existing."""
        existing = {"roughness": 0.5}
        paint = {"roughness": (1.0, 0.0, 0.0)}  # wrong type
        result = compute_multi_channel_blend(existing, paint, 1.0, "MIX")
        assert result["roughness"] == 0.5


# ===========================================================================
# Projection type dispatch tests
# ===========================================================================

class TestProjectionDispatch:
    """Test that compute_projection_uvs rejects box and bad types."""

    def test_box_type_raises(self):
        """Passing 'box' to compute_projection_uvs should raise ValueError."""
        with pytest.raises(ValueError, match="compute_box_projection_uvs"):
            compute_projection_uvs(CUBE_VERTICES, CUBE_FACES, "box")

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid projection type"):
            compute_projection_uvs(CUBE_VERTICES, CUBE_FACES, "cubemap")


# ===========================================================================
# All-projection-types UVs-in-range sweep
# ===========================================================================

class TestAllProjectionsUVRange:
    """All projection types produce UVs in [0, 1] for standard meshes (except clipped)."""

    @pytest.mark.parametrize("proj_type", ["camera", "planar", "cylindrical", "spherical"])
    def test_projection_uvs_in_range(self, proj_type):
        kwargs: dict[str, Any] = {}
        if proj_type == "camera":
            kwargs = {"camera_pos": (0, 0, 5), "camera_target": (0, 0, 0), "fov": 60}
        elif proj_type == "planar":
            kwargs = {"plane_normal": (0, 0, 1), "plane_point": (0, 0, 0)}

        uvs = compute_projection_uvs(CUBE_VERTICES, CUBE_FACES, proj_type, **kwargs)
        for u, v in uvs:
            if u == -1.0 and v == -1.0:
                continue  # clipped
            assert 0.0 <= u <= 1.0, f"{proj_type}: U={u}"
            assert 0.0 <= v <= 1.0, f"{proj_type}: V={v}"

    def test_box_uvs_in_range(self):
        uvs = compute_box_projection_uvs(CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS)
        for u, v in uvs:
            assert 0.0 <= u <= 1.0, f"Box: U={u}"
            assert 0.0 <= v <= 1.0, f"Box: V={v}"


# ===========================================================================
# Blend mode commutativity tests
# ===========================================================================

class TestBlendModeCommutativity:
    """ADD is commutative; OVERLAY is not."""

    def test_add_commutative(self):
        """ADD(a, b) == ADD(b, a) when strength=1 and values small enough to not clip."""
        a = {"roughness": 0.1}
        b = {"roughness": 0.2}
        r1 = compute_multi_channel_blend(a, b, 1.0, "ADD")
        r2 = compute_multi_channel_blend(b, a, 1.0, "ADD")
        assert abs(r1["roughness"] - r2["roughness"]) < 1e-6

    def test_overlay_not_commutative(self):
        """OVERLAY is not commutative in general."""
        a = {"roughness": 0.2}
        b = {"roughness": 0.7}
        r1 = compute_multi_channel_blend(a, b, 1.0, "OVERLAY")
        r2 = compute_multi_channel_blend(b, a, 1.0, "OVERLAY")
        # These should differ because the formula branches on existing < 0.5
        assert abs(r1["roughness"] - r2["roughness"]) > 0.01


# ===========================================================================
# Edge cases and integration-style tests
# ===========================================================================

class TestEdgeCases:
    """Edge cases: large meshes, degenerate geometry."""

    def test_cylindrical_360_coverage(self):
        """Vertices at 12 evenly-spaced angles produce UVs spanning [0, 1]."""
        verts = []
        for i in range(12):
            angle = 2 * math.pi * i / 12
            verts.append((math.sin(angle), 0.0, math.cos(angle)))
        uvs = compute_projection_uvs(verts, [], "cylindrical")
        us = [u for u, v in uvs]
        assert min(us) < 0.1, f"Min U={min(us)}, expected near 0"
        assert max(us) > 0.9, f"Max U={max(us)}, expected near 1"

    def test_spherical_full_coverage(self):
        """Vertices covering the full sphere produce UVs spanning most of [0,1]."""
        verts = SPHERE_VERTICES
        uvs = compute_projection_uvs(verts, [], "spherical")
        us = [u for u, v in uvs]
        vs = [v for u, v in uvs]
        assert min(vs) < 0.01  # south pole
        assert max(vs) > 0.99  # north pole

    def test_box_projection_handles_missing_normals(self):
        """If face_normals is shorter than faces, extra faces are skipped gracefully."""
        # 6 faces but only 3 normals
        uvs = compute_box_projection_uvs(
            CUBE_VERTICES, CUBE_FACES, CUBE_FACE_NORMALS[:3],
        )
        assert len(uvs) == 8
        for u, v in uvs:
            assert 0.0 <= u <= 1.0
            assert 0.0 <= v <= 1.0

    def test_multi_blend_empty_paint(self):
        """Empty paint dict produces empty result."""
        existing = {"roughness": 0.5, "color": (0.5, 0.5, 0.5, 1.0)}
        result = compute_multi_channel_blend(existing, {}, 1.0, "MIX")
        assert result == {}

    def test_multi_blend_empty_existing(self):
        """Empty existing dict produces empty result (no matching channels)."""
        paint = {"roughness": 0.5}
        result = compute_multi_channel_blend({}, paint, 1.0, "MIX")
        assert result == {}

    def test_stencil_mask_on_rgb_tuple(self):
        """apply_stencil_mask pads RGB to RGBA and applies mask."""
        result = apply_stencil_mask((0.5, 0.5, 0.5), 0.0, 1.0)
        assert len(result) == 4
        assert result[3] == 0.0  # mask=0 -> alpha=0

    def test_camera_single_vertex_in_front(self):
        """Single vertex directly in front of camera should produce valid UVs."""
        uvs = compute_projection_uvs(
            [(0.0, 0.0, 0.0)], [], "camera",
            camera_pos=(0.0, 0.0, 5.0), camera_target=(0.0, 0.0, 0.0),
        )
        assert len(uvs) == 1
        # Single point normalises to something in [0,1]
        assert 0.0 <= uvs[0][0] <= 1.0
        assert 0.0 <= uvs[0][1] <= 1.0
