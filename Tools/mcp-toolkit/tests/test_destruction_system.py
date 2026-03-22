"""Unit tests for the destruction state system.

Tests cover:
- DAMAGE_LEVELS constant definitions and invariants
- get_damage_level() lookup and validation
- interpolate_damage_levels() blending between damage states
- apply_destruction() vertex displacement, face removal, rubble generation
- generate_rubble_pile() debris chunk generation
- Edge cases: empty meshes, pristine (no-op), seed determinism

All pure-logic -- no Blender required.
"""

import math

import pytest

from blender_addon.handlers.destruction_system import (
    DAMAGE_LEVELS,
    apply_destruction,
    generate_rubble_pile,
    get_damage_level,
    interpolate_damage_levels,
)


# ---------------------------------------------------------------------------
# Test fixtures: simple mesh data
# ---------------------------------------------------------------------------

def _make_cube_mesh():
    """Simple cube mesh for testing (8 verts, 6 quad faces)."""
    vertices = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]
    faces = [
        (0, 3, 2, 1),  # bottom
        (4, 5, 6, 7),  # top
        (0, 1, 5, 4),  # front
        (2, 3, 7, 6),  # back
        (0, 4, 7, 3),  # left
        (1, 2, 6, 5),  # right
    ]
    return vertices, faces


def _make_large_mesh(n=50):
    """Generate a grid-like mesh with many faces for face removal tests."""
    vertices = []
    faces = []
    for row in range(n):
        for col in range(n):
            vertices.append((float(col), float(row) * 0.1, 0.0))
    # Create quads for the grid
    for row in range(n - 1):
        for col in range(n - 1):
            v0 = row * n + col
            v1 = v0 + 1
            v2 = v0 + n + 1
            v3 = v0 + n
            faces.append((v0, v1, v2, v3))
    return vertices, faces


# ---------------------------------------------------------------------------
# TestDamageLevels
# ---------------------------------------------------------------------------

class TestDamageLevels:
    """Test DAMAGE_LEVELS constant definitions."""

    def test_has_four_levels(self):
        assert len(DAMAGE_LEVELS) == 4

    def test_level_names(self):
        expected = {"pristine", "worn", "damaged", "destroyed"}
        assert set(DAMAGE_LEVELS.keys()) == expected

    def test_pristine_no_displacement(self):
        assert DAMAGE_LEVELS["pristine"]["vertex_displacement"] == 0.0

    def test_pristine_no_missing_faces(self):
        assert DAMAGE_LEVELS["pristine"]["missing_faces_pct"] == 0.0

    def test_pristine_no_rubble(self):
        assert DAMAGE_LEVELS["pristine"]["rubble"] is False

    def test_worn_small_displacement(self):
        assert DAMAGE_LEVELS["worn"]["vertex_displacement"] == 0.005

    def test_worn_no_rubble(self):
        assert DAMAGE_LEVELS["worn"]["rubble"] is False

    def test_damaged_has_rubble(self):
        assert DAMAGE_LEVELS["damaged"]["rubble"] is True
        assert DAMAGE_LEVELS["damaged"]["rubble_amount"] == 0.3

    def test_destroyed_max_damage(self):
        d = DAMAGE_LEVELS["destroyed"]
        assert d["vertex_displacement"] == 0.05
        assert d["missing_faces_pct"] == 0.4
        assert d["rubble"] is True
        assert d["rubble_amount"] == 1.0

    def test_displacement_increases_with_severity(self):
        levels = ["pristine", "worn", "damaged", "destroyed"]
        displacements = [DAMAGE_LEVELS[l]["vertex_displacement"] for l in levels]
        for i in range(len(displacements) - 1):
            assert displacements[i] <= displacements[i + 1]

    def test_missing_faces_increases_with_severity(self):
        levels = ["pristine", "worn", "damaged", "destroyed"]
        missing = [DAMAGE_LEVELS[l]["missing_faces_pct"] for l in levels]
        for i in range(len(missing) - 1):
            assert missing[i] <= missing[i + 1]

    def test_all_levels_have_required_keys(self):
        required = {"vertex_displacement", "missing_faces_pct", "rubble"}
        for name, level in DAMAGE_LEVELS.items():
            for key in required:
                assert key in level, f"Level '{name}' missing key '{key}'"


# ---------------------------------------------------------------------------
# TestGetDamageLevel
# ---------------------------------------------------------------------------

class TestGetDamageLevel:
    """Test get_damage_level() lookup function."""

    def test_valid_levels(self):
        for name in DAMAGE_LEVELS:
            result = get_damage_level(name)
            assert isinstance(result, dict)

    def test_returns_copy(self):
        result = get_damage_level("damaged")
        result["vertex_displacement"] = 999
        assert DAMAGE_LEVELS["damaged"]["vertex_displacement"] != 999

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError, match="Unknown damage level"):
            get_damage_level("nuclear")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            get_damage_level("")


# ---------------------------------------------------------------------------
# TestInterpolateDamageLevels
# ---------------------------------------------------------------------------

class TestInterpolateDamageLevels:
    """Test interpolate_damage_levels() blending."""

    def test_t0_equals_first_level(self):
        result = interpolate_damage_levels("pristine", "destroyed", 0.0)
        assert result["vertex_displacement"] == 0.0
        assert result["missing_faces_pct"] == 0.0

    def test_t1_equals_second_level(self):
        result = interpolate_damage_levels("pristine", "destroyed", 1.0)
        assert abs(result["vertex_displacement"] - 0.05) < 1e-9
        assert abs(result["missing_faces_pct"] - 0.4) < 1e-9

    def test_midpoint_interpolation(self):
        result = interpolate_damage_levels("pristine", "destroyed", 0.5)
        assert abs(result["vertex_displacement"] - 0.025) < 1e-9
        assert abs(result["missing_faces_pct"] - 0.2) < 1e-9

    def test_rubble_interpolation(self):
        result = interpolate_damage_levels("damaged", "destroyed", 0.5)
        assert result["rubble"] is True
        expected = 0.3 * 0.5 + 1.0 * 0.5
        assert abs(result["rubble_amount"] - expected) < 1e-9

    def test_no_rubble_between_non_rubble_levels(self):
        result = interpolate_damage_levels("pristine", "worn", 0.5)
        assert result["rubble"] is False

    def test_t_clamped_below_zero(self):
        result = interpolate_damage_levels("pristine", "destroyed", -0.5)
        assert result["vertex_displacement"] == 0.0

    def test_t_clamped_above_one(self):
        result = interpolate_damage_levels("pristine", "destroyed", 1.5)
        assert abs(result["vertex_displacement"] - 0.05) < 1e-9

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError):
            interpolate_damage_levels("pristine", "exploded", 0.5)


# ---------------------------------------------------------------------------
# TestApplyDestruction
# ---------------------------------------------------------------------------

class TestApplyDestruction:
    """Test apply_destruction() core function."""

    def test_pristine_no_change(self):
        verts, faces = _make_cube_mesh()
        result = apply_destruction(verts, faces, level="pristine")
        assert result["damaged_vertices"] == verts
        assert result["damaged_faces"] == faces
        assert result["rubble_mesh"] is None

    def test_worn_displaces_vertices(self):
        verts, faces = _make_cube_mesh()
        result = apply_destruction(verts, faces, level="worn")
        # Some vertices should be displaced
        displaced = sum(
            1 for i in range(len(verts))
            if verts[i] != result["damaged_vertices"][i]
        )
        assert displaced > 0

    def test_damaged_removes_faces(self):
        verts, faces = _make_large_mesh(10)
        result = apply_destruction(verts, faces, level="damaged")
        assert len(result["damaged_faces"]) < len(faces)

    def test_damaged_generates_rubble(self):
        verts, faces = _make_cube_mesh()
        result = apply_destruction(verts, faces, level="damaged")
        assert result["rubble_mesh"] is not None
        assert len(result["rubble_mesh"]["vertices"]) > 0

    def test_destroyed_removes_more_faces(self):
        verts, faces = _make_large_mesh(10)
        damaged = apply_destruction(verts, faces, level="damaged")
        destroyed = apply_destruction(verts, faces, level="destroyed")
        assert len(destroyed["damaged_faces"]) <= len(damaged["damaged_faces"])

    def test_vertex_count_preserved(self):
        verts, faces = _make_cube_mesh()
        result = apply_destruction(verts, faces, level="destroyed")
        assert len(result["damaged_vertices"]) == len(verts)

    def test_metadata_present(self):
        verts, faces = _make_cube_mesh()
        result = apply_destruction(verts, faces, level="damaged")
        meta = result["metadata"]
        assert "level" in meta
        assert "faces_removed" in meta
        assert "faces_remaining" in meta
        assert "total_faces_original" in meta
        assert "rubble_generated" in meta
        assert "seed" in meta

    def test_metadata_level_matches(self):
        verts, faces = _make_cube_mesh()
        result = apply_destruction(verts, faces, level="worn")
        assert result["metadata"]["level"] == "worn"

    def test_seed_determinism(self):
        verts, faces = _make_cube_mesh()
        r1 = apply_destruction(verts, faces, level="destroyed", seed=42)
        r2 = apply_destruction(verts, faces, level="destroyed", seed=42)
        assert r1["damaged_vertices"] == r2["damaged_vertices"]

    def test_different_seeds_differ(self):
        verts, faces = _make_cube_mesh()
        r1 = apply_destruction(verts, faces, level="destroyed", seed=42)
        r2 = apply_destruction(verts, faces, level="destroyed", seed=99)
        # At least some vertices should differ
        differs = any(
            r1["damaged_vertices"][i] != r2["damaged_vertices"][i]
            for i in range(len(verts))
        )
        assert differs

    def test_empty_mesh(self):
        result = apply_destruction([], [], level="destroyed")
        assert result["damaged_vertices"] == []
        assert result["damaged_faces"] == []
        assert result["rubble_mesh"] is None

    def test_invalid_level_raises(self):
        verts, faces = _make_cube_mesh()
        with pytest.raises(ValueError):
            apply_destruction(verts, faces, level="obliterated")

    def test_faces_remaining_plus_removed_equals_original(self):
        verts, faces = _make_large_mesh(10)
        result = apply_destruction(verts, faces, level="destroyed")
        meta = result["metadata"]
        assert meta["faces_remaining"] + meta["faces_removed"] == meta["total_faces_original"]


# ---------------------------------------------------------------------------
# TestGenerateRubblePile
# ---------------------------------------------------------------------------

class TestGenerateRubblePile:
    """Test generate_rubble_pile() debris generation."""

    def test_returns_mesh_spec(self):
        result = generate_rubble_pile((0, 0, 0), 1.0, 0.5)
        assert "vertices" in result
        assert "faces" in result
        assert "metadata" in result

    def test_has_vertices_and_faces(self):
        result = generate_rubble_pile((0, 0, 0), 1.0, 0.5)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_more_amount_more_chunks(self):
        small = generate_rubble_pile((0, 0, 0), 1.0, 0.1)
        large = generate_rubble_pile((0, 0, 0), 1.0, 1.0)
        assert large["metadata"]["chunk_count"] >= small["metadata"]["chunk_count"]

    def test_rubble_near_center(self):
        center = (5.0, 0.0, 3.0)
        result = generate_rubble_pile(center, 1.0, 0.5)
        for vx, vy, vz in result["vertices"]:
            dist = math.sqrt((vx - center[0]) ** 2 + (vz - center[2]) ** 2)
            # Should be within radius + chunk size tolerance
            assert dist < 2.0

    def test_rubble_above_ground(self):
        center = (0, 0, 0)
        result = generate_rubble_pile(center, 1.0, 0.5)
        for _, vy, _ in result["vertices"]:
            assert vy >= center[1] - 0.01  # allow tiny float error

    def test_seed_determinism(self):
        r1 = generate_rubble_pile((0, 0, 0), 1.0, 0.5, seed=42)
        r2 = generate_rubble_pile((0, 0, 0), 1.0, 0.5, seed=42)
        assert r1["vertices"] == r2["vertices"]
        assert r1["faces"] == r2["faces"]

    def test_amount_clamped(self):
        result = generate_rubble_pile((0, 0, 0), 1.0, 2.0)
        assert result["metadata"]["amount"] == 1.0

    def test_zero_amount_minimal(self):
        result = generate_rubble_pile((0, 0, 0), 1.0, 0.0)
        # Should still produce at least 1 chunk (minimum)
        assert result["metadata"]["chunk_count"] >= 1

    def test_metadata_fields(self):
        result = generate_rubble_pile((0, 0, 0), 2.0, 0.7, seed=123)
        meta = result["metadata"]
        assert meta["name"] == "rubble_pile"
        assert meta["radius"] == 2.0
        assert abs(meta["amount"] - 0.7) < 1e-9
        assert meta["seed"] == 123
        assert meta["chunk_count"] > 0
        assert meta["poly_count"] == len(result["faces"])
        assert meta["vertex_count"] == len(result["vertices"])

    def test_face_indices_valid(self):
        result = generate_rubble_pile((0, 0, 0), 1.0, 0.5)
        num_verts = len(result["vertices"])
        for face in result["faces"]:
            for idx in face:
                assert 0 <= idx < num_verts
