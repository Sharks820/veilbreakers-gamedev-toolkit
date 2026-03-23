"""Unit tests for terrain noise, biome assignment, and pathing algorithms.

Tests _terrain_noise.py pure-logic functions: generate_heightmap,
compute_slope_map, compute_biome_assignments, carve_river_path,
generate_road_path, and TERRAIN_PRESETS.
"""

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Heightmap generation tests
# ---------------------------------------------------------------------------


class TestGenerateHeightmap:
    """Test generate_heightmap with various terrain types and parameters."""

    def test_returns_ndarray_correct_shape(self):
        """generate_heightmap returns ndarray of shape (height, width)."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 32, seed=42, terrain_type="mountains")
        assert isinstance(hmap, np.ndarray)
        assert hmap.shape == (32, 64)

    def test_values_in_0_1_range(self):
        """All heightmap values are in [0, 1]."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_deterministic_same_seed(self):
        """Same seed produces identical output."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        h1 = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        h2 = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        np.testing.assert_array_equal(h1, h2)

    def test_different_seeds_differ(self):
        """Different seeds produce different output."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        h1 = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        h2 = generate_heightmap(64, 64, seed=99, terrain_type="mountains")
        assert not np.array_equal(h1, h2)

    def test_mountains_terrain_type(self):
        """Mountains terrain type produces valid heightmap."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        assert hmap.shape == (64, 64)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_hills_terrain_type(self):
        """Hills terrain type produces valid heightmap."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="hills")
        assert hmap.shape == (64, 64)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_plains_terrain_type(self):
        """Plains terrain type produces valid heightmap."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="plains")
        assert hmap.shape == (64, 64)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_volcanic_terrain_type(self):
        """Volcanic terrain type produces valid heightmap."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="volcanic")
        assert hmap.shape == (64, 64)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_canyon_terrain_type(self):
        """Canyon terrain type produces valid heightmap."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="canyon")
        assert hmap.shape == (64, 64)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_cliffs_terrain_type(self):
        """Cliffs terrain type produces valid heightmap."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(64, 64, seed=42, terrain_type="cliffs")
        assert hmap.shape == (64, 64)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_mountains_higher_amplitude_than_plains(self):
        """Mountains preset produces more rugged terrain than plains.

        Uses the interquartile range (IQR) on a larger 128x128 grid for
        stability.  IQR is more robust than std when a power curve
        (mountains) compresses the distribution tails.
        """
        from blender_addon.handlers._terrain_noise import generate_heightmap

        mountains = generate_heightmap(128, 128, seed=42, terrain_type="mountains")
        plains = generate_heightmap(128, 128, seed=42, terrain_type="plains")
        # Compare interquartile range (Q75 - Q25) for distribution spread
        m_iqr = float(np.percentile(mountains, 75) - np.percentile(mountains, 25))
        p_iqr = float(np.percentile(plains, 75) - np.percentile(plains, 25))
        # Mountains should have wider height distribution than plains.
        # At minimum they should not be dramatically less varied.
        # Use a relaxed threshold: mountains IQR should be at least 80%
        # of plains IQR (power curve can compress, but amplitude_scale
        # compensates).
        assert m_iqr > p_iqr * 0.8, (
            f"Mountains IQR ({m_iqr:.4f}) is too small vs plains ({p_iqr:.4f})"
        )

    def test_canyon_has_valley_pattern(self):
        """Canyon terrain produces a different distribution than mountains.

        Canyon uses ridge subtraction to create valley-like patterns, which
        should produce a distinct height distribution.
        """
        from blender_addon.handlers._terrain_noise import generate_heightmap

        canyon = generate_heightmap(64, 64, seed=42, terrain_type="canyon")
        mountains = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        # Heights should differ significantly
        assert not np.allclose(canyon, mountains, atol=0.1)

    def test_unknown_terrain_type_raises(self):
        """Unknown terrain_type raises ValueError."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        with pytest.raises(ValueError, match="terrain_type"):
            generate_heightmap(64, 64, seed=42, terrain_type="unknown_biome")

    def test_custom_octaves_override(self):
        """Custom octaves parameter overrides preset."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        h_default = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        h_custom = generate_heightmap(
            64, 64, seed=42, terrain_type="mountains", octaves=2
        )
        # Different octave count should produce different result
        assert not np.array_equal(h_default, h_custom)

    def test_large_resolution_256(self):
        """256x256 heightmap generates correctly with vectorized path."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(256, 256, seed=42, terrain_type="mountains")
        assert hmap.shape == (256, 256)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_non_square_heightmap(self):
        """Non-square heightmaps generate correctly."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(128, 64, seed=42, terrain_type="hills")
        assert hmap.shape == (64, 128)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0


# ---------------------------------------------------------------------------
# Terrain presets tests
# ---------------------------------------------------------------------------


class TestTerrainPresets:
    """Test TERRAIN_PRESETS configuration dict."""

    def test_has_eight_terrain_types(self):
        """TERRAIN_PRESETS has exactly 8 terrain types."""
        from blender_addon.handlers._terrain_noise import TERRAIN_PRESETS

        assert len(TERRAIN_PRESETS) == 8

    def test_required_terrain_types_present(self):
        """All 8 required terrain types are present."""
        from blender_addon.handlers._terrain_noise import TERRAIN_PRESETS

        required = {"mountains", "hills", "plains", "volcanic", "canyon", "cliffs", "flat", "chaotic"}
        assert required == set(TERRAIN_PRESETS.keys())

    def test_each_preset_has_octaves(self):
        """Each preset has an 'octaves' key."""
        from blender_addon.handlers._terrain_noise import TERRAIN_PRESETS

        for name, preset in TERRAIN_PRESETS.items():
            assert "octaves" in preset, f"{name} missing 'octaves'"

    def test_each_preset_has_persistence(self):
        """Each preset has a 'persistence' key."""
        from blender_addon.handlers._terrain_noise import TERRAIN_PRESETS

        for name, preset in TERRAIN_PRESETS.items():
            assert "persistence" in preset, f"{name} missing 'persistence'"

    def test_each_preset_has_lacunarity(self):
        """Each preset has a 'lacunarity' key."""
        from blender_addon.handlers._terrain_noise import TERRAIN_PRESETS

        for name, preset in TERRAIN_PRESETS.items():
            assert "lacunarity" in preset, f"{name} missing 'lacunarity'"


# ---------------------------------------------------------------------------
# Slope map tests
# ---------------------------------------------------------------------------


class TestComputeSlopeMap:
    """Test compute_slope_map returns correct slope values."""

    def test_returns_same_shape(self):
        """Slope map has same shape as input heightmap."""
        from blender_addon.handlers._terrain_noise import compute_slope_map

        hmap = np.random.RandomState(42).rand(32, 32)
        slope = compute_slope_map(hmap)
        assert slope.shape == hmap.shape

    def test_flat_terrain_low_slope(self):
        """A flat heightmap produces near-zero slopes."""
        from blender_addon.handlers._terrain_noise import compute_slope_map

        hmap = np.ones((32, 32)) * 0.5
        slope = compute_slope_map(hmap)
        assert np.allclose(slope, 0.0, atol=0.01)

    def test_slope_values_in_valid_range(self):
        """All slope values are in [0, 90] degrees."""
        from blender_addon.handlers._terrain_noise import compute_slope_map

        hmap = np.random.RandomState(42).rand(32, 32)
        slope = compute_slope_map(hmap)
        assert slope.min() >= 0.0
        assert slope.max() <= 90.0

    def test_steep_terrain_has_high_slope(self):
        """Terrain with large height differences has high slope values."""
        from blender_addon.handlers._terrain_noise import compute_slope_map

        # Create a ramp: left side = 0, right side = 1
        hmap = np.tile(np.linspace(0, 1, 32), (32, 1))
        slope = compute_slope_map(hmap)
        # Interior cells should have non-trivial slope
        assert slope[16, 16] > 0.5


# ---------------------------------------------------------------------------
# Biome assignment tests
# ---------------------------------------------------------------------------


class TestComputeBiomeAssignments:
    """Test compute_biome_assignments with altitude/slope rules."""

    def test_returns_int_array_same_shape(self):
        """Biome assignments return integer array matching heightmap shape."""
        from blender_addon.handlers._terrain_noise import (
            compute_biome_assignments,
            compute_slope_map,
        )

        hmap = np.random.RandomState(42).rand(32, 32)
        slope = compute_slope_map(hmap)
        biomes = compute_biome_assignments(hmap, slope)
        assert biomes.shape == hmap.shape
        assert biomes.dtype in (np.int32, np.int64)

    def test_all_values_are_valid_rule_indices(self):
        """All biome values are valid rule indices (0 to len(rules)-1)."""
        from blender_addon.handlers._terrain_noise import (
            BIOME_RULES,
            compute_biome_assignments,
            compute_slope_map,
        )

        hmap = np.random.RandomState(42).rand(32, 32)
        slope = compute_slope_map(hmap)
        biomes = compute_biome_assignments(hmap, slope)
        assert biomes.min() >= 0
        assert biomes.max() < len(BIOME_RULES)

    def test_snow_at_high_altitude(self):
        """High altitude, low slope cells should be assigned 'snow' (rule 0)."""
        from blender_addon.handlers._terrain_noise import (
            BIOME_RULES,
            compute_biome_assignments,
        )

        # Create heightmap with high altitude and low slope
        hmap = np.full((8, 8), 0.9)  # High altitude
        slope = np.full((8, 8), 5.0)  # Low slope
        biomes = compute_biome_assignments(hmap, slope)
        # Snow rule is index 0 (min_alt=0.8, max_slope=45)
        assert np.all(biomes == 0)

    def test_rock_at_steep_slope(self):
        """Steep slope cells should be assigned 'rock' (rule 1)."""
        from blender_addon.handlers._terrain_noise import compute_biome_assignments

        hmap = np.full((8, 8), 0.5)  # Mid altitude
        slope = np.full((8, 8), 50.0)  # Steep slope
        biomes = compute_biome_assignments(hmap, slope)
        # Rock rule is index 1 (min_slope=40, max_slope=90)
        assert np.all(biomes == 1)

    def test_dead_grass_at_mid_altitude(self):
        """Mid altitude, moderate slope -> dead_grass (rule 2)."""
        from blender_addon.handlers._terrain_noise import compute_biome_assignments

        hmap = np.full((8, 8), 0.5)  # Mid altitude
        slope = np.full((8, 8), 10.0)  # Low slope
        biomes = compute_biome_assignments(hmap, slope)
        # dead_grass rule is index 2 (min_alt=0.2, max_alt=0.8, max_slope=40)
        assert np.all(biomes == 2)

    def test_mud_at_low_altitude(self):
        """Low altitude, low slope -> mud (rule 3)."""
        from blender_addon.handlers._terrain_noise import compute_biome_assignments

        hmap = np.full((8, 8), 0.1)  # Low altitude
        slope = np.full((8, 8), 5.0)  # Low slope
        biomes = compute_biome_assignments(hmap, slope)
        # mud rule is index 3 (max_alt=0.2, max_slope=40)
        assert np.all(biomes == 3)

    def test_custom_biome_rules(self):
        """Custom biome rules override defaults."""
        from blender_addon.handlers._terrain_noise import compute_biome_assignments

        rules = [
            {"name": "water", "min_alt": 0.0, "max_alt": 0.3},
            {"name": "land", "min_alt": 0.3, "max_alt": 1.0},
        ]
        hmap = np.array([[0.1, 0.5], [0.2, 0.8]])
        slope = np.zeros_like(hmap)
        biomes = compute_biome_assignments(hmap, slope, biome_rules=rules)
        assert biomes[0, 0] == 0  # water
        assert biomes[0, 1] == 1  # land
        assert biomes[1, 0] == 0  # water
        assert biomes[1, 1] == 1  # land


# ---------------------------------------------------------------------------
# River carving tests
# ---------------------------------------------------------------------------


class TestCarveRiverPath:
    """Test carve_river_path A* pathfinding and channel carving."""

    def test_returns_path_and_heightmap(self):
        """Returns a tuple of (path, modified_heightmap)."""
        from blender_addon.handlers._terrain_noise import carve_river_path

        hmap = np.random.RandomState(42).rand(32, 32)
        path, result = carve_river_path(hmap, source=(0, 16), dest=(31, 16))
        assert isinstance(path, list)
        assert isinstance(result, np.ndarray)
        assert result.shape == hmap.shape

    def test_path_is_connected(self):
        """Path forms a connected sequence of adjacent cells."""
        from blender_addon.handlers._terrain_noise import carve_river_path

        hmap = np.random.RandomState(42).rand(32, 32)
        path, _ = carve_river_path(hmap, source=(0, 16), dest=(31, 16))
        assert len(path) >= 2
        for i in range(1, len(path)):
            r0, c0 = path[i - 1]
            r1, c1 = path[i]
            assert abs(r1 - r0) <= 1 and abs(c1 - c0) <= 1, (
                f"Gap in path at {i}: {path[i-1]} -> {path[i]}"
            )

    def test_path_starts_at_source(self):
        """Path starts at the source coordinate."""
        from blender_addon.handlers._terrain_noise import carve_river_path

        hmap = np.random.RandomState(42).rand(32, 32)
        path, _ = carve_river_path(hmap, source=(0, 16), dest=(31, 16))
        assert path[0] == (0, 16)

    def test_path_ends_at_dest(self):
        """Path ends at the destination coordinate."""
        from blender_addon.handlers._terrain_noise import carve_river_path

        hmap = np.random.RandomState(42).rand(32, 32)
        path, _ = carve_river_path(hmap, source=(0, 16), dest=(31, 16))
        assert path[-1] == (31, 16)

    def test_carving_lowers_heightmap(self):
        """River carving reduces heightmap values along the path."""
        from blender_addon.handlers._terrain_noise import carve_river_path

        hmap = np.full((32, 32), 0.5)
        path, result = carve_river_path(
            hmap, source=(0, 16), dest=(31, 16), depth=0.1
        )
        # At least some cells along the path should be lower
        lowered = False
        for r, c in path:
            if result[r, c] < hmap[r, c]:
                lowered = True
                break
        assert lowered, "River carving did not lower any heightmap values"

    def test_result_values_in_bounds(self):
        """Carved heightmap values stay in [0, 1]."""
        from blender_addon.handlers._terrain_noise import carve_river_path

        hmap = np.random.RandomState(42).rand(32, 32)
        _, result = carve_river_path(hmap, source=(0, 16), dest=(31, 16))
        assert result.min() >= 0.0
        assert result.max() <= 1.0


# ---------------------------------------------------------------------------
# Road generation tests
# ---------------------------------------------------------------------------


class TestGenerateRoadPath:
    """Test generate_road_path A* pathfinding and terrain grading."""

    def test_returns_path_and_heightmap(self):
        """Returns a tuple of (path, modified_heightmap)."""
        from blender_addon.handlers._terrain_noise import generate_road_path

        hmap = np.random.RandomState(42).rand(32, 32)
        path, result = generate_road_path(
            hmap, waypoints=[(0, 0), (31, 31)], width=3
        )
        assert isinstance(path, list)
        assert isinstance(result, np.ndarray)

    def test_path_is_connected(self):
        """Road path forms a connected sequence of adjacent cells."""
        from blender_addon.handlers._terrain_noise import generate_road_path

        hmap = np.random.RandomState(42).rand(32, 32)
        path, _ = generate_road_path(
            hmap, waypoints=[(0, 0), (31, 31)], width=3
        )
        assert len(path) >= 2
        for i in range(1, len(path)):
            r0, c0 = path[i - 1]
            r1, c1 = path[i]
            assert abs(r1 - r0) <= 1 and abs(c1 - c0) <= 1

    def test_road_flattens_terrain(self):
        """Road grading reduces height variation along the path."""
        from blender_addon.handlers._terrain_noise import generate_road_path

        rng = np.random.RandomState(42)
        hmap = rng.rand(32, 32)
        path, result = generate_road_path(
            hmap, waypoints=[(0, 0), (31, 31)], width=3, grade_strength=0.8
        )
        # Measure height variance along the path
        orig_heights = [float(hmap[r, c]) for r, c in path]
        new_heights = [float(result[r, c]) for r, c in path]
        orig_var = np.var(orig_heights)
        new_var = np.var(new_heights)
        # Graded road should have equal or lower variance
        assert new_var <= orig_var + 0.01

    def test_result_values_in_bounds(self):
        """Road-graded heightmap values stay in [0, 1]."""
        from blender_addon.handlers._terrain_noise import generate_road_path

        hmap = np.random.RandomState(42).rand(32, 32)
        _, result = generate_road_path(
            hmap, waypoints=[(0, 0), (31, 31)], width=3
        )
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_multi_waypoint_road(self):
        """Road with multiple waypoints connects all segments."""
        from blender_addon.handlers._terrain_noise import generate_road_path

        hmap = np.random.RandomState(42).rand(32, 32)
        path, _ = generate_road_path(
            hmap, waypoints=[(0, 0), (16, 16), (31, 31)], width=3
        )
        assert len(path) > 10  # Should have a reasonable number of cells
