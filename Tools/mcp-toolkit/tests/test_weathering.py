"""Tests for edge wear and weathering pipeline.

Verifies all pure-logic weathering functions:
  - Edge wear on convex geometry
  - Dirt accumulation in concave areas and at base
  - Moss growth on upward-facing surfaces only
  - Rain staining on vertical surfaces only
  - Structural settling vertex displacement
  - Corruption veins mask
  - Weathering presets structure
  - Combined vertex color computation

All pure-logic -- no Blender required.
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from blender_addon.handlers.weathering import (
    WEATHERING_PRESETS,
    VALID_PRESETS,
    VALID_EFFECTS,
    WEAR_TINT,
    DIRT_TINT,
    MOSS_TINT,
    RAIN_TINT,
    CORRUPTION_TINT,
    apply_edge_wear,
    apply_dirt_accumulation,
    apply_moss_growth,
    apply_rain_staining,
    apply_structural_settling,
    apply_corruption_veins,
    compute_weathered_vertex_colors,
    _compute_bounding_box,
    _height_factor,
    _compute_edge_convexity,
    _simple_noise,
)


# ---------------------------------------------------------------------------
# Test fixtures: simple geometry
# ---------------------------------------------------------------------------

def _make_cube_mesh_data() -> dict:
    """Create a unit cube mesh data dict centered at origin.

    Vertices at +/-0.5 on each axis. 6 quad faces, 8 vertices.
    """
    vertices = [
        (-0.5, -0.5, -0.5),  # 0: bottom-front-left
        ( 0.5, -0.5, -0.5),  # 1: bottom-front-right
        ( 0.5,  0.5, -0.5),  # 2: bottom-back-right
        (-0.5,  0.5, -0.5),  # 3: bottom-back-left
        (-0.5, -0.5,  0.5),  # 4: top-front-left
        ( 0.5, -0.5,  0.5),  # 5: top-front-right
        ( 0.5,  0.5,  0.5),  # 6: top-back-right
        (-0.5,  0.5,  0.5),  # 7: top-back-left
    ]
    faces = [
        (0, 1, 2, 3),  # bottom (-Z)
        (4, 7, 6, 5),  # top (+Z)
        (0, 4, 5, 1),  # front (-Y)
        (2, 6, 7, 3),  # back (+Y)
        (0, 3, 7, 4),  # left (-X)
        (1, 5, 6, 2),  # right (+X)
    ]
    face_normals = [
        (0.0, 0.0, -1.0),   # bottom
        (0.0, 0.0,  1.0),   # top
        (0.0, -1.0, 0.0),   # front
        (0.0,  1.0, 0.0),   # back
        (-1.0, 0.0, 0.0),   # left
        (1.0, 0.0, 0.0),    # right
    ]
    vertex_normals = [
        (-0.577, -0.577, -0.577),
        ( 0.577, -0.577, -0.577),
        ( 0.577,  0.577, -0.577),
        (-0.577,  0.577, -0.577),
        (-0.577, -0.577,  0.577),
        ( 0.577, -0.577,  0.577),
        ( 0.577,  0.577,  0.577),
        (-0.577,  0.577,  0.577),
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # bottom ring
        (4, 5), (5, 6), (6, 7), (7, 4),  # top ring
        (0, 4), (1, 5), (2, 6), (3, 7),  # vertical edges
    ]
    return {
        "vertices": vertices,
        "faces": faces,
        "face_normals": face_normals,
        "vertex_normals": vertex_normals,
        "edges": edges,
    }


def _make_flat_ground_mesh() -> dict:
    """Create a flat ground plane (Z=0) for moss/rain direction tests.

    4x4 grid of vertices at Z=0, all face normals pointing straight up (0,0,1).
    """
    vertices = []
    for y in range(4):
        for x in range(4):
            vertices.append((float(x), float(y), 0.0))

    faces = []
    face_normals = []
    for y in range(3):
        for x in range(3):
            v0 = y * 4 + x
            v1 = v0 + 1
            v2 = v0 + 5
            v3 = v0 + 4
            faces.append((v0, v1, v2, v3))
            face_normals.append((0.0, 0.0, 1.0))  # all face up

    vertex_normals = [(0.0, 0.0, 1.0)] * len(vertices)
    edges = []
    for y in range(4):
        for x in range(3):
            edges.append((y * 4 + x, y * 4 + x + 1))
    for y in range(3):
        for x in range(4):
            edges.append((y * 4 + x, (y + 1) * 4 + x))

    return {
        "vertices": vertices,
        "faces": faces,
        "face_normals": face_normals,
        "vertex_normals": vertex_normals,
        "edges": edges,
    }


def _make_vertical_wall_mesh() -> dict:
    """Create a vertical wall (XZ plane) for rain staining tests.

    4x4 grid in XZ plane. All face normals point in -Y direction (horizontal).
    """
    vertices = []
    for z in range(4):
        for x in range(4):
            vertices.append((float(x), 0.0, float(z)))

    faces = []
    face_normals = []
    for z in range(3):
        for x in range(3):
            v0 = z * 4 + x
            v1 = v0 + 1
            v2 = v0 + 5
            v3 = v0 + 4
            faces.append((v0, v1, v2, v3))
            face_normals.append((0.0, -1.0, 0.0))  # wall facing -Y

    vertex_normals = [(0.0, -1.0, 0.0)] * len(vertices)
    edges = []
    for z in range(4):
        for x in range(3):
            edges.append((z * 4 + x, z * 4 + x + 1))
    for z in range(3):
        for x in range(4):
            edges.append((z * 4 + x, (z + 1) * 4 + x))

    return {
        "vertices": vertices,
        "faces": faces,
        "face_normals": face_normals,
        "vertex_normals": vertex_normals,
        "edges": edges,
    }


# ---------------------------------------------------------------------------
# Preset structure tests
# ---------------------------------------------------------------------------

class TestWeatheringPresets:
    """Verify preset configuration structure."""

    def test_all_presets_exist(self):
        """All five named presets are defined."""
        expected = {"light", "medium", "heavy", "ancient", "corrupted"}
        assert set(WEATHERING_PRESETS.keys()) == expected

    def test_valid_presets_matches_keys(self):
        """VALID_PRESETS frozenset matches WEATHERING_PRESETS keys."""
        assert VALID_PRESETS == frozenset(WEATHERING_PRESETS.keys())

    def test_presets_have_core_keys(self):
        """Every preset has edge_wear, dirt, and settling at minimum."""
        core_keys = {"edge_wear", "dirt", "settling"}
        for name, preset in WEATHERING_PRESETS.items():
            missing = core_keys - set(preset.keys())
            assert not missing, f"Preset '{name}' missing keys: {missing}"

    def test_preset_values_are_floats(self):
        """All preset values are numeric (int or float)."""
        for name, preset in WEATHERING_PRESETS.items():
            for key, value in preset.items():
                assert isinstance(value, (int, float)), (
                    f"Preset '{name}' key '{key}' has type {type(value)}"
                )

    def test_preset_values_in_valid_range(self):
        """Effect strengths are in [0, 1] range (settling can be lower)."""
        for name, preset in WEATHERING_PRESETS.items():
            for key, value in preset.items():
                if key == "settling":
                    assert 0.0 <= value <= 0.1, (
                        f"Preset '{name}' settling={value} out of range [0, 0.1]"
                    )
                else:
                    assert 0.0 <= value <= 1.0, (
                        f"Preset '{name}' {key}={value} out of range [0, 1]"
                    )

    def test_corrupted_has_corruption_veins(self):
        """Corrupted preset uniquely includes corruption_veins."""
        assert "corruption_veins" in WEATHERING_PRESETS["corrupted"]
        for name in ("light", "medium", "heavy", "ancient"):
            assert "corruption_veins" not in WEATHERING_PRESETS[name]

    def test_severity_ordering(self):
        """Presets increase in severity: light < medium < heavy < ancient."""
        presets = WEATHERING_PRESETS
        for key in ("edge_wear", "dirt"):
            assert presets["light"][key] < presets["medium"][key]
            assert presets["medium"][key] < presets["heavy"][key]
            assert presets["heavy"][key] < presets["ancient"][key]

    def test_valid_effects_contains_all_effect_names(self):
        """VALID_EFFECTS contains all effect keys used across presets."""
        all_keys: set[str] = set()
        for preset in WEATHERING_PRESETS.values():
            all_keys.update(preset.keys())
        assert all_keys.issubset(VALID_EFFECTS)


# ---------------------------------------------------------------------------
# Color palette tests
# ---------------------------------------------------------------------------

class TestWeatheringPalette:
    """Verify weathering tint colors follow VB dark fantasy palette."""

    def test_tints_are_rgba(self):
        """All tint colors are 4-element tuples."""
        for tint in (WEAR_TINT, DIRT_TINT, MOSS_TINT, RAIN_TINT, CORRUPTION_TINT):
            assert len(tint) == 4
            assert all(isinstance(c, float) for c in tint)

    def test_tint_values_in_range(self):
        """Tint RGB values are in [0, 1] range."""
        for tint in (WEAR_TINT, DIRT_TINT, MOSS_TINT, RAIN_TINT, CORRUPTION_TINT):
            for c in tint[:3]:
                assert 0.0 <= c <= 1.0

    def test_dirt_is_dark(self):
        """Dirt tint is very dark (value < 0.1)."""
        assert max(DIRT_TINT[:3]) < 0.1

    def test_moss_is_greenish(self):
        """Moss tint has green as dominant channel."""
        assert MOSS_TINT[1] > MOSS_TINT[0]
        assert MOSS_TINT[1] > MOSS_TINT[2]

    def test_corruption_is_purple(self):
        """Corruption tint has blue > green and red > green (purple)."""
        r, g, b, _ = CORRUPTION_TINT
        assert b > g, "Corruption blue should exceed green"
        assert r > g, "Corruption red should exceed green"


# ---------------------------------------------------------------------------
# Edge wear tests
# ---------------------------------------------------------------------------

class TestEdgeWear:
    """Test edge wear mask computation."""

    def test_returns_correct_length(self):
        """Wear mask has one value per vertex."""
        mesh = _make_cube_mesh_data()
        mask = apply_edge_wear(mesh, strength=0.5)
        assert len(mask) == len(mesh["vertices"])

    def test_values_in_0_1_range(self):
        """All wear values are clamped to [0, 1]."""
        mesh = _make_cube_mesh_data()
        mask = apply_edge_wear(mesh, strength=1.0)
        for v in mask:
            assert 0.0 <= v <= 1.0

    def test_empty_mesh_returns_empty(self):
        """Empty mesh returns empty mask."""
        mesh = {"vertices": [], "faces": [], "face_normals": [], "vertex_normals": [], "edges": []}
        mask = apply_edge_wear(mesh, strength=0.5)
        assert mask == []

    def test_zero_strength_near_zero(self):
        """Zero strength produces near-zero wear values."""
        mesh = _make_cube_mesh_data()
        mask = apply_edge_wear(mesh, strength=0.0)
        for v in mask:
            assert v == 0.0

    def test_higher_strength_more_wear(self):
        """Higher strength produces higher average wear."""
        mesh = _make_cube_mesh_data()
        mask_low = apply_edge_wear(mesh, strength=0.2)
        mask_high = apply_edge_wear(mesh, strength=0.8)
        avg_low = sum(mask_low) / len(mask_low)
        avg_high = sum(mask_high) / len(mask_high)
        assert avg_high > avg_low

    def test_cube_corners_have_wear(self):
        """Cube corners are convex and should show some wear."""
        mesh = _make_cube_mesh_data()
        mask = apply_edge_wear(mesh, strength=1.0)
        # All cube vertices are corners (convex), so all should have some wear
        assert any(v > 0.0 for v in mask)

    def test_flat_ground_less_wear(self):
        """Flat ground has less wear than cube corners (less curvature)."""
        cube = _make_cube_mesh_data()
        ground = _make_flat_ground_mesh()
        cube_mask = apply_edge_wear(cube, strength=0.5)
        ground_mask = apply_edge_wear(ground, strength=0.5)
        # Interior ground vertices should have less wear than cube corners
        # Cube has all convex corners; ground interior verts are flat
        cube_avg = sum(cube_mask) / len(cube_mask)
        # Ground interior vertices (not boundary)
        interior = [ground_mask[i] for i in range(len(ground_mask))
                     if 0 < i % 4 < 3 and 4 <= i < 12]
        if interior:
            ground_avg = sum(interior) / len(interior)
            assert ground_avg <= cube_avg


# ---------------------------------------------------------------------------
# Dirt accumulation tests
# ---------------------------------------------------------------------------

class TestDirtAccumulation:
    """Test dirt accumulation mask computation."""

    def test_returns_correct_length(self):
        mesh = _make_cube_mesh_data()
        mask = apply_dirt_accumulation(mesh, strength=0.5)
        assert len(mask) == len(mesh["vertices"])

    def test_values_in_0_1_range(self):
        mesh = _make_cube_mesh_data()
        mask = apply_dirt_accumulation(mesh, strength=1.0)
        for v in mask:
            assert 0.0 <= v <= 1.0

    def test_empty_mesh_returns_empty(self):
        mesh = {"vertices": [], "faces": [], "face_normals": [], "vertex_normals": [], "edges": []}
        mask = apply_dirt_accumulation(mesh, strength=0.5)
        assert mask == []

    def test_zero_strength_zero_dirt(self):
        mesh = _make_cube_mesh_data()
        mask = apply_dirt_accumulation(mesh, strength=0.0)
        for v in mask:
            assert v == 0.0

    def test_bottom_more_dirt_than_top(self):
        """Bottom vertices accumulate more dirt than top vertices."""
        mesh = _make_cube_mesh_data()
        mask = apply_dirt_accumulation(mesh, strength=1.0)
        # Vertices 0-3 are at z=-0.5 (bottom), 4-7 at z=0.5 (top)
        bottom_avg = sum(mask[0:4]) / 4
        top_avg = sum(mask[4:8]) / 4
        assert bottom_avg > top_avg


# ---------------------------------------------------------------------------
# Moss growth tests
# ---------------------------------------------------------------------------

class TestMossGrowth:
    """Test moss growth mask computation."""

    def test_returns_correct_length(self):
        mesh = _make_cube_mesh_data()
        mask = apply_moss_growth(mesh, strength=0.5)
        assert len(mask) == len(mesh["vertices"])

    def test_values_in_0_1_range(self):
        mesh = _make_flat_ground_mesh()
        mask = apply_moss_growth(mesh, strength=1.0)
        for v in mask:
            assert 0.0 <= v <= 1.0

    def test_empty_mesh_returns_empty(self):
        mesh = {"vertices": [], "faces": [], "face_normals": [], "vertex_normals": [], "edges": []}
        mask = apply_moss_growth(mesh, strength=0.5)
        assert mask == []

    def test_flat_ground_gets_moss(self):
        """Flat ground (all normals up) should receive moss."""
        mesh = _make_flat_ground_mesh()
        mask = apply_moss_growth(mesh, strength=1.0)
        # At least some vertices should have moss > 0
        assert any(v > 0.0 for v in mask)

    def test_vertical_wall_no_moss(self):
        """Vertical wall (normals horizontal) should get zero or near-zero moss."""
        mesh = _make_vertical_wall_mesh()
        mask = apply_moss_growth(mesh, strength=1.0)
        # Wall normals point in -Y, not upward -- should be below threshold
        for v in mask:
            assert v == 0.0, "Vertical surfaces should not receive moss"

    def test_zero_strength_zero_moss(self):
        mesh = _make_flat_ground_mesh()
        mask = apply_moss_growth(mesh, strength=0.0)
        for v in mask:
            assert v == 0.0

    def test_only_upward_facing_receives_moss(self):
        """Only surfaces with upward-facing normals get moss."""
        # Cube has top face (up), bottom face (down), and 4 walls
        mesh = _make_cube_mesh_data()
        mask = apply_moss_growth(mesh, strength=1.0)
        # Top vertices (4,5,6,7) should have some moss contribution
        # Bottom and side-only vertices might have less
        # The key test: no vertex gets moss from downward-facing or pure-side surfaces
        # Cube corners are shared by up/side/down faces, so all get averaged
        # But wall-only mesh should have zero
        wall = _make_vertical_wall_mesh()
        wall_mask = apply_moss_growth(wall, strength=1.0)
        assert all(v == 0.0 for v in wall_mask)


# ---------------------------------------------------------------------------
# Rain staining tests
# ---------------------------------------------------------------------------

class TestRainStaining:
    """Test rain staining mask computation."""

    def test_returns_correct_length(self):
        mesh = _make_cube_mesh_data()
        mask = apply_rain_staining(mesh, strength=0.5)
        assert len(mask) == len(mesh["vertices"])

    def test_values_in_0_1_range(self):
        mesh = _make_vertical_wall_mesh()
        mask = apply_rain_staining(mesh, strength=1.0)
        for v in mask:
            assert 0.0 <= v <= 1.0

    def test_empty_mesh_returns_empty(self):
        mesh = {"vertices": [], "faces": [], "face_normals": [], "vertex_normals": [], "edges": []}
        mask = apply_rain_staining(mesh, strength=0.5)
        assert mask == []

    def test_vertical_wall_gets_rain(self):
        """Vertical wall (horizontal normals) should receive rain staining."""
        mesh = _make_vertical_wall_mesh()
        mask = apply_rain_staining(mesh, strength=1.0)
        assert any(v > 0.0 for v in mask)

    def test_flat_ground_no_rain(self):
        """Flat ground (normals pointing up) should not get rain staining."""
        mesh = _make_flat_ground_mesh()
        mask = apply_rain_staining(mesh, strength=1.0)
        for v in mask:
            assert v == 0.0, "Horizontal surfaces should not receive rain staining"

    def test_zero_strength_zero_rain(self):
        mesh = _make_vertical_wall_mesh()
        mask = apply_rain_staining(mesh, strength=0.0)
        for v in mask:
            assert v == 0.0

    def test_lower_vertices_more_staining(self):
        """STY-014: Lower vertices accumulate more rain staining (runoff collects below ledges)."""
        mesh = _make_vertical_wall_mesh()
        mask = apply_rain_staining(mesh, strength=1.0)
        # Bottom row: z=0 (indices 0-3), top row: z=3 (indices 12-15)
        bottom = [mask[i] for i in range(4)]
        top = [mask[i] for i in range(12, 16)]
        bottom_avg = sum(bottom) / len(bottom)
        top_avg = sum(top) / len(top)
        assert bottom_avg > top_avg, "Lower vertices should accumulate more rain staining (STY-014)"


# ---------------------------------------------------------------------------
# Structural settling tests
# ---------------------------------------------------------------------------

class TestStructuralSettling:
    """Test structural settling vertex displacement."""

    def test_returns_correct_length(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        result = apply_structural_settling(verts, strength=0.01)
        assert len(result) == len(verts)

    def test_empty_returns_empty(self):
        result = apply_structural_settling([], strength=0.01)
        assert result == []

    def test_vertices_are_displaced(self):
        """Vertices should be moved from original positions."""
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        result = apply_structural_settling(verts, strength=0.01)
        displaced = any(
            abs(r[0] - v[0]) > 1e-10 or abs(r[1] - v[1]) > 1e-10 or abs(r[2] - v[2]) > 1e-10
            for r, v in zip(result, verts)
        )
        assert displaced, "At least some vertices should be displaced"

    def test_displacement_bounded_by_strength(self):
        """Displacement should not exceed strength parameter."""
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        strength = 0.01
        result = apply_structural_settling(verts, strength=strength)
        for r, v in zip(result, verts):
            dx = abs(r[0] - v[0])
            dy = abs(r[1] - v[1])
            dz = abs(r[2] - v[2])
            assert dx <= strength * 1.01  # Small tolerance
            assert dy <= strength * 1.01
            assert dz <= strength * 1.01

    def test_top_displaced_more_than_bottom(self):
        """Top vertices should be displaced more than bottom (gravity settling)."""
        verts = [
            (0, 0, 0),   # bottom
            (1, 0, 0),   # bottom
            (0, 0, 5),   # top
            (1, 0, 5),   # top
        ]
        strength = 0.1
        # Run many seeds and average to smooth randomness
        top_total = 0.0
        bottom_total = 0.0
        n_trials = 50
        for seed in range(n_trials):
            result = apply_structural_settling(verts, strength=strength, seed=seed)
            for i, (r, v) in enumerate(zip(result, verts)):
                dist = math.sqrt(
                    (r[0] - v[0]) ** 2 + (r[1] - v[1]) ** 2 + (r[2] - v[2]) ** 2
                )
                if v[2] == 0:
                    bottom_total += dist
                else:
                    top_total += dist

        # Average displacement at top should be larger
        avg_top = top_total / (n_trials * 2)
        avg_bottom = bottom_total / (n_trials * 2)
        assert avg_top > avg_bottom, (
            f"Top avg displacement {avg_top:.6f} should exceed bottom {avg_bottom:.6f}"
        )

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical displacement."""
        verts = [(0, 0, 0), (1, 1, 1), (2, 2, 2)]
        r1 = apply_structural_settling(verts, strength=0.01, seed=42)
        r2 = apply_structural_settling(verts, strength=0.01, seed=42)
        for a, b in zip(r1, r2):
            assert a == b

    def test_different_seeds_differ(self):
        """Different seeds produce different displacement."""
        verts = [(0, 0, 0), (1, 1, 1), (2, 2, 2)]
        r1 = apply_structural_settling(verts, strength=0.01, seed=42)
        r2 = apply_structural_settling(verts, strength=0.01, seed=99)
        differ = any(a != b for a, b in zip(r1, r2))
        assert differ

    def test_zero_strength_no_displacement(self):
        """Zero strength should produce no displacement."""
        verts = [(0, 0, 0), (1, 1, 1)]
        result = apply_structural_settling(verts, strength=0.0)
        for r, v in zip(result, verts):
            assert r == v


# ---------------------------------------------------------------------------
# Corruption veins tests
# ---------------------------------------------------------------------------

class TestCorruptionVeins:
    """Test corruption vein mask computation."""

    def test_returns_correct_length(self):
        mesh = _make_cube_mesh_data()
        mask = apply_corruption_veins(mesh, strength=0.5)
        assert len(mask) == len(mesh["vertices"])

    def test_values_in_0_1_range(self):
        mesh = _make_cube_mesh_data()
        mask = apply_corruption_veins(mesh, strength=1.0)
        for v in mask:
            assert 0.0 <= v <= 1.0

    def test_empty_mesh_returns_empty(self):
        mesh = {"vertices": [], "faces": [], "face_normals": [], "vertex_normals": [], "edges": []}
        mask = apply_corruption_veins(mesh, strength=0.5)
        assert mask == []

    def test_zero_strength_zero_corruption(self):
        mesh = _make_cube_mesh_data()
        mask = apply_corruption_veins(mesh, strength=0.0)
        for v in mask:
            assert v == 0.0


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    """Test internal helper functions."""

    def test_bounding_box_cube(self):
        verts = [(-1, -2, -3), (1, 2, 3)]
        mn, mx = _compute_bounding_box(verts)
        assert mn == (-1, -2, -3)
        assert mx == (1, 2, 3)

    def test_bounding_box_empty(self):
        mn, mx = _compute_bounding_box([])
        assert mn == (0, 0, 0)
        assert mx == (0, 0, 0)

    def test_height_factor_range(self):
        assert _height_factor(0.0, 0.0, 10.0) == 0.0
        assert _height_factor(10.0, 0.0, 10.0) == 1.0
        assert _height_factor(5.0, 0.0, 10.0) == 0.5

    def test_height_factor_degenerate(self):
        """Degenerate height range returns 0."""
        assert _height_factor(5.0, 5.0, 5.0) == 0.0

    def test_height_factor_clamped(self):
        """Values outside range are clamped to [0, 1]."""
        assert _height_factor(-5.0, 0.0, 10.0) == 0.0
        assert _height_factor(15.0, 0.0, 10.0) == 1.0

    def test_simple_noise_range(self):
        """Noise output is in [0, 1]."""
        for i in range(100):
            v = _simple_noise(float(i), float(i * 2), float(i * 3), seed=42)
            assert 0.0 <= v <= 1.0

    def test_simple_noise_deterministic(self):
        """Same inputs produce same output."""
        v1 = _simple_noise(1.5, 2.5, 3.5, seed=42)
        v2 = _simple_noise(1.5, 2.5, 3.5, seed=42)
        assert v1 == v2

    def test_edge_convexity_cube(self):
        """Cube corners should have positive curvature (convex)."""
        mesh = _make_cube_mesh_data()
        curvature = _compute_edge_convexity(mesh)
        assert len(curvature) == 8
        # All cube corners are convex (angle defect > 0)
        for vi, c in curvature.items():
            assert c > 0.0, f"Cube vertex {vi} should be convex, got {c}"

    def test_edge_convexity_flat(self):
        """Interior flat vertices should have near-zero curvature."""
        mesh = _make_flat_ground_mesh()
        curvature = _compute_edge_convexity(mesh)
        # Interior vertices (not on boundary) should be near flat
        interior_verts = [5, 6, 9, 10]  # middle 2x2 of 4x4 grid
        for vi in interior_verts:
            assert abs(curvature[vi]) < 0.1, (
                f"Interior vertex {vi} curvature={curvature[vi]}, expected near 0"
            )


# ---------------------------------------------------------------------------
# Combined vertex color computation tests
# ---------------------------------------------------------------------------

class TestComputeWeatheredVertexColors:
    """Test the combined weathering color computation."""

    def test_returns_correct_length(self):
        mesh = _make_cube_mesh_data()
        base = (0.15, 0.13, 0.11, 1.0)
        colors = compute_weathered_vertex_colors(mesh, base, preset_name="medium")
        assert len(colors) == len(mesh["vertices"])

    def test_colors_are_rgba(self):
        mesh = _make_cube_mesh_data()
        base = (0.15, 0.13, 0.11, 1.0)
        colors = compute_weathered_vertex_colors(mesh, base, preset_name="light")
        for c in colors:
            assert len(c) == 4
            for ch in c:
                assert 0.0 <= ch <= 1.0

    def test_empty_mesh_empty_result(self):
        mesh = {"vertices": [], "faces": [], "face_normals": [], "vertex_normals": [], "edges": []}
        colors = compute_weathered_vertex_colors(mesh, (0.5, 0.5, 0.5, 1.0))
        assert colors == []

    def test_preset_name_selects_preset(self):
        """Different presets produce different results."""
        mesh = _make_cube_mesh_data()
        base = (0.15, 0.13, 0.11, 1.0)
        light = compute_weathered_vertex_colors(mesh, base, preset_name="light")
        heavy = compute_weathered_vertex_colors(mesh, base, preset_name="heavy")
        # Heavy weathering should produce more color deviation from base
        assert light != heavy

    def test_custom_effects_override(self):
        """Custom effects dict overrides preset."""
        mesh = _make_cube_mesh_data()
        base = (0.15, 0.13, 0.11, 1.0)
        custom = {"edge_wear": 1.0, "dirt": 0.0, "moss": 0.0, "rain": 0.0}
        colors = compute_weathered_vertex_colors(mesh, base, effects=custom)
        assert len(colors) == 8

    def test_alpha_preserved(self):
        """Alpha channel from base color is preserved."""
        mesh = _make_cube_mesh_data()
        base = (0.15, 0.13, 0.11, 0.75)
        colors = compute_weathered_vertex_colors(mesh, base, preset_name="light")
        for c in colors:
            assert c[3] == 0.75

    def test_corrupted_preset_applies_corruption(self):
        """Corrupted preset includes corruption vein effects."""
        mesh = _make_cube_mesh_data()
        base = (0.5, 0.5, 0.5, 1.0)
        corrupted = compute_weathered_vertex_colors(mesh, base, preset_name="corrupted")
        # With corruption active, colors should shift toward purple tint
        no_corruption = compute_weathered_vertex_colors(
            mesh, base, effects={"edge_wear": 0.4, "dirt": 0.3}
        )
        assert corrupted != no_corruption


# ---------------------------------------------------------------------------
# Handler tests (mocked bpy)
# ---------------------------------------------------------------------------

class TestHandleApplyWeathering:
    """Test the bpy handler wrapper with mocked Blender."""

    def test_missing_object_name_raises(self):
        from blender_addon.handlers.weathering import handle_apply_weathering
        with pytest.raises(ValueError, match="object_name"):
            handle_apply_weathering({})

    def test_invalid_preset_raises(self):
        from blender_addon.handlers.weathering import handle_apply_weathering
        with pytest.raises(ValueError, match="Invalid preset"):
            handle_apply_weathering({
                "object_name": "Cube",
                "weathering_preset": "nonexistent",
            })
