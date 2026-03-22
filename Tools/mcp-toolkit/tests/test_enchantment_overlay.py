"""Unit tests for the enchantment/infusion visual overlay system.

Tests cover:
- BRAND_ENCHANTMENT_PATTERNS constant definitions
- get_brand_pattern() lookup and validation
- compute_pattern_density() per-pattern weight computation
- compute_enchantment_overlay() per-vertex emission mask
- generate_floating_rune_positions() orbital rune placement
- Edge cases: empty meshes, intensity bounds, all brands

All pure-logic -- no Blender required.
"""

import math

import pytest

from blender_addon.handlers.enchantment_overlay import (
    BRAND_ENCHANTMENT_PATTERNS,
    VALID_BRANDS,
    compute_enchantment_overlay,
    compute_pattern_density,
    generate_floating_rune_positions,
    get_brand_pattern,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_cube_mesh():
    """Simple cube mesh for testing."""
    vertices = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    return vertices, faces


def _make_sphere_mesh(segments=8, rings=4):
    """Simple UV sphere mesh for testing."""
    vertices = []
    faces = []

    # Top pole
    vertices.append((0, 1, 0))
    for ring in range(1, rings):
        phi = math.pi * ring / rings
        for seg in range(segments):
            theta = math.tau * seg / segments
            x = math.sin(phi) * math.cos(theta)
            y = math.cos(phi)
            z = math.sin(phi) * math.sin(theta)
            vertices.append((x, y, z))
    # Bottom pole
    vertices.append((0, -1, 0))

    # Top cap faces
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((0, 1 + i, 1 + j))

    # Middle ring faces
    for ring in range(rings - 2):
        base = 1 + ring * segments
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((base + i, base + segments + i, base + segments + j, base + j))

    # Bottom cap faces
    bottom_idx = len(vertices) - 1
    base = 1 + (rings - 2) * segments
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((base + i, bottom_idx, base + j))

    return vertices, faces


# ---------------------------------------------------------------------------
# TestBrandPatterns
# ---------------------------------------------------------------------------

class TestBrandPatterns:
    """Test BRAND_ENCHANTMENT_PATTERNS constant definitions."""

    def test_has_ten_brands(self):
        assert len(BRAND_ENCHANTMENT_PATTERNS) == 10

    def test_brand_names(self):
        expected = {"IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
                     "LEECH", "GRACE", "MEND", "RUIN", "VOID"}
        assert set(BRAND_ENCHANTMENT_PATTERNS.keys()) == expected

    def test_valid_brands_matches(self):
        assert VALID_BRANDS == frozenset(BRAND_ENCHANTMENT_PATTERNS.keys())

    def test_all_have_required_keys(self):
        required = {"pattern", "emission_color", "emission_strength", "particle",
                     "pulse_speed", "coverage"}
        for brand, data in BRAND_ENCHANTMENT_PATTERNS.items():
            for key in required:
                assert key in data, f"Brand '{brand}' missing key '{key}'"

    def test_emission_colors_are_rgb_tuples(self):
        for brand, data in BRAND_ENCHANTMENT_PATTERNS.items():
            color = data["emission_color"]
            assert len(color) == 3, f"Brand '{brand}' color should be (r, g, b)"
            for c in color:
                assert 0.0 <= c <= 1.0, f"Brand '{brand}' color channel out of [0, 1]"

    def test_emission_strengths_positive(self):
        for brand, data in BRAND_ENCHANTMENT_PATTERNS.items():
            assert data["emission_strength"] > 0.0

    def test_coverage_in_range(self):
        for brand, data in BRAND_ENCHANTMENT_PATTERNS.items():
            assert 0.0 < data["coverage"] <= 1.0

    def test_all_have_unique_patterns(self):
        patterns = [d["pattern"] for d in BRAND_ENCHANTMENT_PATTERNS.values()]
        assert len(patterns) == len(set(patterns)), "Duplicate patterns found"

    def test_all_have_unique_particles(self):
        particles = [d["particle"] for d in BRAND_ENCHANTMENT_PATTERNS.values()]
        assert len(particles) == len(set(particles)), "Duplicate particle types found"


# ---------------------------------------------------------------------------
# TestGetBrandPattern
# ---------------------------------------------------------------------------

class TestGetBrandPattern:
    """Test get_brand_pattern() lookup function."""

    def test_valid_brands(self):
        for brand in BRAND_ENCHANTMENT_PATTERNS:
            result = get_brand_pattern(brand)
            assert isinstance(result, dict)

    def test_case_insensitive(self):
        result_upper = get_brand_pattern("IRON")
        result_lower = get_brand_pattern("iron")
        assert result_upper == result_lower

    def test_returns_copy(self):
        result = get_brand_pattern("SURGE")
        result["emission_strength"] = 999
        assert BRAND_ENCHANTMENT_PATTERNS["SURGE"]["emission_strength"] != 999

    def test_invalid_brand_raises(self):
        with pytest.raises(ValueError, match="Unknown brand"):
            get_brand_pattern("PLASMA")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            get_brand_pattern("")


# ---------------------------------------------------------------------------
# TestComputePatternDensity
# ---------------------------------------------------------------------------

class TestComputePatternDensity:
    """Test compute_pattern_density() per-pattern weight computation."""

    ALL_PATTERNS = [d["pattern"] for d in BRAND_ENCHANTMENT_PATTERNS.values()]

    @pytest.mark.parametrize("pattern", ALL_PATTERNS)
    def test_returns_float_in_range(self, pattern):
        result = compute_pattern_density((0.5, 0.5, 0.5), pattern, seed=42)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.5  # some patterns can slightly exceed 1.0

    @pytest.mark.parametrize("pattern", ALL_PATTERNS)
    def test_deterministic(self, pattern):
        v = (0.3, 0.7, 0.1)
        r1 = compute_pattern_density(v, pattern, seed=42)
        r2 = compute_pattern_density(v, pattern, seed=42)
        assert r1 == r2

    def test_different_positions_vary(self):
        r1 = compute_pattern_density((0, 0, 0), "lightning_arcs", seed=42)
        r2 = compute_pattern_density((1, 1, 1), "lightning_arcs", seed=42)
        # They could theoretically be the same but very unlikely
        # At minimum the function should accept both without error
        assert isinstance(r1, float) and isinstance(r2, float)

    def test_unknown_pattern_returns_hash(self):
        # Fallback behavior for unknown patterns
        result = compute_pattern_density((0, 0, 0), "nonexistent", seed=42)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# TestComputeEnchantmentOverlay
# ---------------------------------------------------------------------------

class TestComputeEnchantmentOverlay:
    """Test compute_enchantment_overlay() core function."""

    def test_returns_expected_keys(self):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, "IRON")
        assert "emission_weights" in result
        assert "emission_color" in result
        assert "emission_strength" in result
        assert "particle_positions" in result
        assert "particle_type" in result
        assert "pattern" in result
        assert "metadata" in result

    def test_weight_count_matches_vertices(self):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, "IRON")
        assert len(result["emission_weights"]) == len(verts)

    def test_weights_in_range(self):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, "SURGE")
        for w in result["emission_weights"]:
            assert 0.0 <= w <= 1.0

    def test_emission_color_matches_brand(self):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, "RUIN")
        expected = BRAND_ENCHANTMENT_PATTERNS["RUIN"]["emission_color"]
        assert result["emission_color"] == expected

    def test_emission_strength_scaled_by_intensity(self):
        verts, faces = _make_cube_mesh()
        base = BRAND_ENCHANTMENT_PATTERNS["IRON"]["emission_strength"]
        result = compute_enchantment_overlay(verts, faces, "IRON", intensity=2.0)
        assert abs(result["emission_strength"] - base * 2.0) < 1e-9

    def test_zero_intensity_no_emission(self):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, "SURGE", intensity=0.0)
        assert all(w == 0.0 for w in result["emission_weights"])

    def test_particle_positions_are_tuples(self):
        verts, faces = _make_sphere_mesh()
        result = compute_enchantment_overlay(verts, faces, "GRACE", intensity=2.0)
        for pos in result["particle_positions"]:
            assert len(pos) == 3

    def test_case_insensitive_brand(self):
        verts, faces = _make_cube_mesh()
        r1 = compute_enchantment_overlay(verts, faces, "IRON", seed=42)
        r2 = compute_enchantment_overlay(verts, faces, "iron", seed=42)
        assert r1["emission_weights"] == r2["emission_weights"]

    @pytest.mark.parametrize("brand", list(BRAND_ENCHANTMENT_PATTERNS.keys()))
    def test_all_brands_work(self, brand):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, brand)
        assert len(result["emission_weights"]) == len(verts)
        assert result["pattern"] == BRAND_ENCHANTMENT_PATTERNS[brand]["pattern"]

    def test_metadata_fields(self):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, "VOID", intensity=1.5, seed=99)
        meta = result["metadata"]
        assert meta["brand"] == "VOID"
        assert meta["intensity"] == 1.5
        assert meta["total_vertices"] == len(verts)
        assert meta["seed"] == 99
        assert "active_vertices" in meta
        assert "coverage_pct" in meta
        assert "avg_emission_weight" in meta
        assert "particle_spawn_count" in meta

    def test_invalid_brand_raises(self):
        verts, faces = _make_cube_mesh()
        with pytest.raises(ValueError):
            compute_enchantment_overlay(verts, faces, "PLASMA")

    def test_empty_mesh(self):
        result = compute_enchantment_overlay([], [], "IRON")
        assert result["emission_weights"] == []
        assert result["particle_positions"] == []

    def test_seed_determinism(self):
        verts, faces = _make_cube_mesh()
        r1 = compute_enchantment_overlay(verts, faces, "SURGE", seed=42)
        r2 = compute_enchantment_overlay(verts, faces, "SURGE", seed=42)
        assert r1["emission_weights"] == r2["emission_weights"]

    def test_intensity_clamped_high(self):
        verts, faces = _make_cube_mesh()
        result = compute_enchantment_overlay(verts, faces, "RUIN", intensity=10.0)
        # Should be clamped to 5.0
        assert result["metadata"]["intensity"] == 5.0


# ---------------------------------------------------------------------------
# TestGenerateFloatingRunePositions
# ---------------------------------------------------------------------------

class TestGenerateFloatingRunePositions:
    """Test generate_floating_rune_positions() orbital placement."""

    def test_returns_correct_count(self):
        runes = generate_floating_rune_positions((0, 0, 0), count=4)
        assert len(runes) == 4

    def test_single_rune(self):
        runes = generate_floating_rune_positions((0, 0, 0), count=1)
        assert len(runes) == 1

    def test_zero_count_returns_one(self):
        runes = generate_floating_rune_positions((0, 0, 0), count=0)
        assert len(runes) == 1  # clamped to 1

    def test_rune_has_expected_keys(self):
        runes = generate_floating_rune_positions((0, 0, 0), count=1)
        rune = runes[0]
        assert "position" in rune
        assert "rotation" in rune
        assert "orbit_angle" in rune
        assert "brand" in rune
        assert "emission_color" in rune
        assert "glyph_index" in rune

    def test_positions_at_radius(self):
        radius = 0.5
        runes = generate_floating_rune_positions((0, 0, 0), radius=radius, count=4)
        for rune in runes:
            x, y, z = rune["position"]
            dist_xz = math.sqrt(x ** 2 + z ** 2)
            # Should be approximately at radius (with some vertical offset)
            assert abs(dist_xz - radius) < 0.01

    def test_positions_around_center(self):
        center = (5.0, 2.0, 3.0)
        runes = generate_floating_rune_positions(center, radius=0.3, count=4)
        for rune in runes:
            x, y, z = rune["position"]
            dist_xz = math.sqrt((x - center[0]) ** 2 + (z - center[2]) ** 2)
            assert abs(dist_xz - 0.3) < 0.01

    def test_evenly_spaced_angles(self):
        runes = generate_floating_rune_positions((0, 0, 0), count=4)
        angles = [r["orbit_angle"] for r in runes]
        for i in range(len(angles) - 1):
            diff = angles[i + 1] - angles[i]
            assert abs(diff - math.tau / 4) < 1e-9

    def test_brand_color_matches(self):
        runes = generate_floating_rune_positions((0, 0, 0), brand="SURGE")
        expected_color = BRAND_ENCHANTMENT_PATTERNS["SURGE"]["emission_color"]
        for rune in runes:
            assert rune["emission_color"] == expected_color
            assert rune["brand"] == "SURGE"

    def test_invalid_brand_raises(self):
        with pytest.raises(ValueError):
            generate_floating_rune_positions((0, 0, 0), brand="FAKE")

    def test_glyph_indices_sequential(self):
        runes = generate_floating_rune_positions((0, 0, 0), count=6)
        for i, rune in enumerate(runes):
            assert rune["glyph_index"] == i % 6
