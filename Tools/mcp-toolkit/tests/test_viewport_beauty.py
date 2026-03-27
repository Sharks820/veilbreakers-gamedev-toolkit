"""Unit tests for viewport beauty setup pure-logic functions.

Tests cover:
- compute_light_position: spherical coordinate positioning
- compute_camera_distance: bounding sphere to camera distance
- compute_ground_size: ground plane sizing from dimensions
- compute_ground_z: ground plane vertical placement
- run_quality_checks_pure: mesh quality validation logic
- Constants: light presets, thresholds, names

All pure-logic -- no Blender required.
"""

import math

import pytest

from blender_addon.handlers.viewport import (
    BEAUTY_CAMERA_NAME,
    BEAUTY_DISTANCE_FACTOR,
    BEAUTY_ELEVATION_DEG,
    BEAUTY_FILL_LIGHT,
    BEAUTY_FOCAL_LENGTH,
    BEAUTY_KEY_LIGHT,
    BEAUTY_LIGHT_PREFIX,
    BEAUTY_RIM_LIGHT,
    BEAUTY_STUDIO_LIGHT,
    DARK_FANTASY_LIGHTING_PRESETS,
    GROUND_COLOR,
    GROUND_MATERIAL_NAME,
    GROUND_PLANE_NAME,
    GROUND_ROUGHNESS,
    GROUND_SCALE_FACTOR,
    MIN_VERT_COUNT,
    compute_camera_distance,
    compute_ground_size,
    compute_ground_z,
    compute_light_position,
    run_quality_checks_pure,
)


# ---------------------------------------------------------------------------
# compute_light_position
# ---------------------------------------------------------------------------


class TestComputeLightPosition:
    """Test spherical coordinate light positioning."""

    def test_zero_angle_front(self):
        """Azimuth=0, elevation=0 places light along +X."""
        pos = compute_light_position((0, 0, 0), 5.0, 0.0, 0.0)
        assert abs(pos[0] - 5.0) < 0.001
        assert abs(pos[1] - 0.0) < 0.001
        assert abs(pos[2] - 0.0) < 0.001

    def test_azimuth_90_right_side(self):
        """Azimuth=90 places light along +Y."""
        pos = compute_light_position((0, 0, 0), 5.0, 90.0, 0.0)
        assert abs(pos[0]) < 0.001
        assert abs(pos[1] - 5.0) < 0.001
        assert abs(pos[2]) < 0.001

    def test_elevation_90_above(self):
        """Elevation=90 places light directly above."""
        pos = compute_light_position((0, 0, 0), 5.0, 0.0, 90.0)
        assert abs(pos[0]) < 0.001
        assert abs(pos[1]) < 0.001
        assert abs(pos[2] - 5.0) < 0.001

    def test_offset_center(self):
        """Light position offsets from non-zero center."""
        pos = compute_light_position((10, 20, 30), 5.0, 0.0, 0.0)
        assert abs(pos[0] - 15.0) < 0.001
        assert abs(pos[1] - 20.0) < 0.001
        assert abs(pos[2] - 30.0) < 0.001

    def test_azimuth_180_behind(self):
        """Azimuth=180 places light along -X."""
        pos = compute_light_position((0, 0, 0), 5.0, 180.0, 0.0)
        assert abs(pos[0] - (-5.0)) < 0.001
        assert abs(pos[1]) < 0.01  # small float error ok
        assert abs(pos[2]) < 0.001

    def test_45_degree_elevation(self):
        """Elevation=45 splits distance between horizontal and vertical."""
        pos = compute_light_position((0, 0, 0), 10.0, 0.0, 45.0)
        expected_xz = 10.0 * math.cos(math.radians(45))
        assert abs(pos[0] - expected_xz) < 0.001
        assert abs(pos[2] - expected_xz) < 0.001

    def test_zero_distance(self):
        """Zero distance returns the center point."""
        pos = compute_light_position((3, 4, 5), 0.0, 45.0, 30.0)
        assert abs(pos[0] - 3.0) < 0.001
        assert abs(pos[1] - 4.0) < 0.001
        assert abs(pos[2] - 5.0) < 0.001


# ---------------------------------------------------------------------------
# compute_camera_distance
# ---------------------------------------------------------------------------


class TestComputeCameraDistance:
    """Test camera distance from object dimensions."""

    def test_unit_cube(self):
        """1x1x1 cube gives distance based on bounding sphere."""
        dist = compute_camera_distance((1.0, 1.0, 1.0))
        radius = math.sqrt(3) / 2.0
        expected = radius * BEAUTY_DISTANCE_FACTOR
        assert abs(dist - max(expected, 2.0)) < 0.01

    def test_minimum_distance(self):
        """Very small objects get at least 2.0 distance."""
        dist = compute_camera_distance((0.01, 0.01, 0.01))
        assert dist >= 2.0

    def test_large_object(self):
        """Large object gets proportional distance."""
        dist = compute_camera_distance((10.0, 10.0, 10.0))
        radius = math.sqrt(300) / 2.0
        expected = radius * BEAUTY_DISTANCE_FACTOR
        assert abs(dist - expected) < 0.01

    def test_flat_object(self):
        """Flat object (0 height) uses width/depth for distance."""
        dist = compute_camera_distance((5.0, 5.0, 0.0))
        radius = math.sqrt(50) / 2.0
        expected = max(radius * BEAUTY_DISTANCE_FACTOR, 2.0)
        assert abs(dist - expected) < 0.01

    def test_tall_narrow_object(self):
        """Tall narrow object uses height for distance."""
        dist = compute_camera_distance((0.5, 0.5, 10.0))
        radius = math.sqrt(0.25 + 0.25 + 100) / 2.0
        expected = radius * BEAUTY_DISTANCE_FACTOR
        assert abs(dist - expected) < 0.01


# ---------------------------------------------------------------------------
# compute_ground_size
# ---------------------------------------------------------------------------


class TestComputeGroundSize:
    """Test ground plane sizing."""

    def test_unit_object(self):
        """1x1x1 object gives size = GROUND_SCALE_FACTOR."""
        size = compute_ground_size((1.0, 1.0, 1.0))
        assert abs(size - max(GROUND_SCALE_FACTOR, 4.0)) < 0.01

    def test_tiny_object_minimum(self):
        """Very small objects get minimum 4.0 ground size."""
        size = compute_ground_size((0.1, 0.1, 0.1))
        assert size >= 4.0

    def test_large_object(self):
        """Large object gets proportional ground size."""
        size = compute_ground_size((5.0, 3.0, 2.0))
        expected = 5.0 * GROUND_SCALE_FACTOR
        assert abs(size - expected) < 0.01

    def test_zero_dimensions(self):
        """Zero dimensions get minimum size."""
        size = compute_ground_size((0.0, 0.0, 0.0))
        assert size >= 4.0


# ---------------------------------------------------------------------------
# compute_ground_z
# ---------------------------------------------------------------------------


class TestComputeGroundZ:
    """Test ground plane Z positioning."""

    def test_origin_object(self):
        """Object at origin with height 2 gives ground at -1."""
        z = compute_ground_z(0.0, 1.0)
        assert abs(z - (-1.0)) < 0.001

    def test_elevated_object(self):
        """Object at z=5 with height 4 gives ground at 3."""
        z = compute_ground_z(5.0, 2.0)
        assert abs(z - 3.0) < 0.001

    def test_zero_height(self):
        """Zero height object has ground at object origin."""
        z = compute_ground_z(3.0, 0.0)
        assert abs(z - 3.0) < 0.001

    def test_negative_location(self):
        """Negative location works correctly."""
        z = compute_ground_z(-2.0, 1.5)
        assert abs(z - (-3.5)) < 0.001


# ---------------------------------------------------------------------------
# run_quality_checks_pure
# ---------------------------------------------------------------------------


class TestQualityChecksPure:
    """Test pure-logic quality check validation."""

    def test_bare_cube_fails_all(self):
        """Default cube (8 verts, no textures, no UVs) fails multiple checks."""
        issues = run_quality_checks_pure(
            vert_count=8,
            has_materials=False,
            has_textures=False,
            has_uvs=False,
            uv_area=0.0,
            face_count=6,
        )
        assert len(issues) >= 3
        assert any("vertex count" in i.lower() for i in issues)
        assert any("material" in i.lower() for i in issues)
        assert any("uv" in i.lower() for i in issues)

    def test_proper_mesh_passes(self):
        """Well-prepared mesh with materials, textures, UVs passes."""
        issues = run_quality_checks_pure(
            vert_count=5000,
            has_materials=True,
            has_textures=True,
            has_uvs=True,
            uv_area=0.8,
            face_count=4000,
        )
        assert len(issues) == 0

    def test_low_verts_only(self):
        """Only low vert count fails if everything else is good."""
        issues = run_quality_checks_pure(
            vert_count=100,
            has_materials=True,
            has_textures=True,
            has_uvs=True,
            uv_area=0.5,
            face_count=80,
        )
        assert len(issues) == 1
        assert "vertex count" in issues[0].lower()

    def test_no_materials(self):
        """Missing materials produces material issue."""
        issues = run_quality_checks_pure(
            vert_count=1000,
            has_materials=False,
            has_textures=False,
            has_uvs=True,
            uv_area=0.5,
            face_count=800,
        )
        assert any("no materials" in i.lower() for i in issues)

    def test_blank_material_no_textures(self):
        """Material without textures produces texture issue."""
        issues = run_quality_checks_pure(
            vert_count=1000,
            has_materials=True,
            has_textures=False,
            has_uvs=True,
            uv_area=0.5,
            face_count=800,
        )
        assert any("no image textures" in i.lower() for i in issues)

    def test_no_uvs(self):
        """Missing UV maps produces UV issue."""
        issues = run_quality_checks_pure(
            vert_count=1000,
            has_materials=True,
            has_textures=True,
            has_uvs=False,
            uv_area=0.0,
            face_count=800,
        )
        assert any("uv" in i.lower() for i in issues)

    def test_collapsed_uvs(self):
        """UVs present but with near-zero area triggers warning."""
        issues = run_quality_checks_pure(
            vert_count=1000,
            has_materials=True,
            has_textures=True,
            has_uvs=True,
            uv_area=0.0001,
            face_count=800,
        )
        assert any("coverage" in i.lower() for i in issues)

    def test_no_faces(self):
        """Mesh with no faces produces face issue."""
        issues = run_quality_checks_pure(
            vert_count=1000,
            has_materials=True,
            has_textures=True,
            has_uvs=True,
            uv_area=0.5,
            face_count=0,
        )
        assert any("no faces" in i.lower() for i in issues)

    def test_exactly_min_verts_passes(self):
        """Exactly MIN_VERT_COUNT passes the vertex check."""
        issues = run_quality_checks_pure(
            vert_count=MIN_VERT_COUNT,
            has_materials=True,
            has_textures=True,
            has_uvs=True,
            uv_area=0.5,
            face_count=400,
        )
        assert not any("vertex count" in i.lower() for i in issues)

    def test_one_below_min_verts_fails(self):
        """One below MIN_VERT_COUNT fails the vertex check."""
        issues = run_quality_checks_pure(
            vert_count=MIN_VERT_COUNT - 1,
            has_materials=True,
            has_textures=True,
            has_uvs=True,
            uv_area=0.5,
            face_count=400,
        )
        assert any("vertex count" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------


class TestBeautyConstants:
    """Test that beauty setup constants are correct."""

    def test_key_light_is_area(self):
        assert BEAUTY_KEY_LIGHT["type"] == "AREA"

    def test_key_light_warm_color(self):
        """Key light has warm color (red > blue)."""
        r, g, b = BEAUTY_KEY_LIGHT["color"]
        assert r > b, "Key light should be warm (red > blue)"

    def test_key_light_energy(self):
        assert BEAUTY_KEY_LIGHT["energy"] == 2.0

    def test_key_light_has_shadow(self):
        assert BEAUTY_KEY_LIGHT["use_shadow"] is True

    def test_fill_light_is_area(self):
        assert BEAUTY_FILL_LIGHT["type"] == "AREA"

    def test_fill_light_cool_color(self):
        """Fill light has cool color (blue > red)."""
        r, g, b = BEAUTY_FILL_LIGHT["color"]
        assert b > r, "Fill light should be cool (blue > red)"

    def test_fill_light_lower_energy(self):
        """Fill light is dimmer than key light."""
        assert BEAUTY_FILL_LIGHT["energy"] < BEAUTY_KEY_LIGHT["energy"]

    def test_fill_light_no_shadow(self):
        assert BEAUTY_FILL_LIGHT["use_shadow"] is False

    def test_rim_light_is_area(self):
        assert BEAUTY_RIM_LIGHT["type"] == "AREA"

    def test_rim_light_neutral_color(self):
        """Rim light has neutral white color."""
        r, g, b = BEAUTY_RIM_LIGHT["color"]
        assert r == g == b == 1.0

    def test_rim_light_behind(self):
        """Rim light azimuth is 180 (behind the object)."""
        assert BEAUTY_RIM_LIGHT["azimuth"] == 180.0

    def test_rim_light_no_shadow(self):
        assert BEAUTY_RIM_LIGHT["use_shadow"] is False

    def test_three_lights_different_positions(self):
        """All three lights have different azimuth positions."""
        azimuths = {
            BEAUTY_KEY_LIGHT["azimuth"],
            BEAUTY_FILL_LIGHT["azimuth"],
            BEAUTY_RIM_LIGHT["azimuth"],
        }
        assert len(azimuths) == 3

    def test_ground_plane_name(self):
        assert GROUND_PLANE_NAME == "VB_Beauty_Ground"

    def test_ground_color_dark(self):
        """Ground color is dark (all channels <= 0.15)."""
        for c in GROUND_COLOR[:3]:
            assert c <= 0.15, f"Ground color channel {c} too bright"

    def test_ground_roughness_medium(self):
        """Ground roughness is medium (some reflection)."""
        assert 0.3 <= GROUND_ROUGHNESS <= 0.8

    def test_camera_focal_length(self):
        assert BEAUTY_FOCAL_LENGTH == 50.0

    def test_camera_elevation(self):
        assert BEAUTY_ELEVATION_DEG == 30.0

    def test_beauty_prefix(self):
        """All beauty light names start with the prefix."""
        for preset in (BEAUTY_KEY_LIGHT, BEAUTY_FILL_LIGHT, BEAUTY_RIM_LIGHT):
            assert preset["name"].startswith(BEAUTY_LIGHT_PREFIX)

    def test_camera_name(self):
        assert BEAUTY_CAMERA_NAME == "VB_Beauty_Camera"

    def test_studio_light_is_exr(self):
        assert BEAUTY_STUDIO_LIGHT.endswith(".exr")

    def test_min_vert_count(self):
        assert MIN_VERT_COUNT == 500

    def test_ground_material_name(self):
        assert GROUND_MATERIAL_NAME == "VB_Beauty_Ground_Mat"

    def test_dark_fantasy_forest_presets_exist(self):
        assert "forest_healthy" in DARK_FANTASY_LIGHTING_PRESETS
        assert "forest_transition" in DARK_FANTASY_LIGHTING_PRESETS
        assert "veil_corrupted" in DARK_FANTASY_LIGHTING_PRESETS


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


class TestBeautyHandlerRegistration:
    """Test that beauty handlers are registered in COMMAND_HANDLERS."""

    def test_setup_beauty_scene_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "setup_beauty_scene" in COMMAND_HANDLERS

    def test_setup_dark_fantasy_lighting_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "setup_dark_fantasy_lighting" in COMMAND_HANDLERS

    def test_setup_ground_plane_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "setup_ground_plane" in COMMAND_HANDLERS

    def test_auto_frame_camera_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "auto_frame_camera" in COMMAND_HANDLERS

    def test_run_quality_checks_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "run_quality_checks" in COMMAND_HANDLERS

    def test_original_viewport_handlers_still_registered(self):
        """Original viewport handlers are still present."""
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "get_viewport_screenshot" in COMMAND_HANDLERS
        assert "render_contact_sheet" in COMMAND_HANDLERS
        assert "set_shading" in COMMAND_HANDLERS
        assert "navigate_camera" in COMMAND_HANDLERS
