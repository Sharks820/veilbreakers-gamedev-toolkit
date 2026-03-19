"""Tests for _scatter_engine.py: Poisson disk, biome filter, context scatter,
and breakable variant generation.

All pure-logic -- no Blender dependency.
"""

import math

import numpy as np
import pytest

from blender_addon.handlers._scatter_engine import (
    BREAKABLE_PROPS,
    PROP_AFFINITY,
    biome_filter_points,
    context_scatter,
    generate_breakable_variants,
    poisson_disk_sample,
)


# ===================================================================
# Poisson Disk Sampling
# ===================================================================


class TestPoissonDiskSample:
    """Tests for poisson_disk_sample."""

    def test_returns_list_of_tuples(self):
        """Result is a list of (x, y) tuples."""
        points = poisson_disk_sample(100.0, 100.0, min_distance=5.0, seed=42)
        assert isinstance(points, list)
        assert len(points) > 0
        for p in points:
            assert isinstance(p, tuple)
            assert len(p) == 2

    def test_minimum_distance_enforced(self):
        """All pairwise distances >= min_distance (checked for subset)."""
        min_dist = 5.0
        points = poisson_disk_sample(100.0, 100.0, min_distance=min_dist, seed=42)
        # Check first 50 points against each other
        subset = points[:50]
        for i in range(len(subset)):
            for j in range(i + 1, len(subset)):
                dx = subset[i][0] - subset[j][0]
                dy = subset[i][1] - subset[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                assert dist >= min_dist - 1e-6, (
                    f"Points {i} and {j} too close: {dist:.4f} < {min_dist}"
                )

    def test_points_within_bounds(self):
        """All points within [0, width] x [0, depth]."""
        w, d = 50.0, 80.0
        points = poisson_disk_sample(w, d, min_distance=3.0, seed=99)
        for x, y in points:
            assert 0 <= x < w, f"x={x} out of bounds [0, {w})"
            assert 0 <= y < d, f"y={y} out of bounds [0, {d})"

    def test_reasonable_point_count(self):
        """Point count is reasonable for area and min_distance."""
        w, d = 100.0, 100.0
        min_dist = 5.0
        points = poisson_disk_sample(w, d, min_distance=min_dist, seed=42)
        # Upper bound: area / (min_distance^2 * pi/4) -- hexagonal packing
        max_bound = (w * d) / (min_dist ** 2 * math.pi / 4)
        assert len(points) > 10, "Too few points generated"
        assert len(points) <= max_bound * 1.5, (
            f"Too many points: {len(points)} > {max_bound * 1.5:.0f}"
        )

    def test_different_seeds_different_distributions(self):
        """Different seeds produce different point sets."""
        pts_a = poisson_disk_sample(50.0, 50.0, min_distance=3.0, seed=1)
        pts_b = poisson_disk_sample(50.0, 50.0, min_distance=3.0, seed=2)
        # At least some points should differ
        assert pts_a != pts_b

    def test_same_seed_identical_distribution(self):
        """Same seed produces identical results."""
        pts_a = poisson_disk_sample(50.0, 50.0, min_distance=3.0, seed=42)
        pts_b = poisson_disk_sample(50.0, 50.0, min_distance=3.0, seed=42)
        assert pts_a == pts_b

    def test_small_min_distance_many_points(self):
        """Small min_distance on small area yields many points."""
        pts = poisson_disk_sample(10.0, 10.0, min_distance=0.5, seed=0)
        assert len(pts) > 50

    def test_large_min_distance_few_points(self):
        """Large min_distance on small area yields few points."""
        pts = poisson_disk_sample(10.0, 10.0, min_distance=8.0, seed=0)
        assert len(pts) < 10


# ===================================================================
# Biome Filter
# ===================================================================


class TestBiomeFilterPoints:
    """Tests for biome_filter_points."""

    @pytest.fixture()
    def heightmap_128(self):
        """128x128 heightmap with gradient from 0 to 1."""
        return np.linspace(0, 1, 128 * 128).reshape(128, 128)

    @pytest.fixture()
    def slope_map_128(self):
        """128x128 slope map with moderate slopes (0-30 degrees)."""
        return np.full((128, 128), 15.0)

    @pytest.fixture()
    def sample_rules(self):
        """Sample biome rules for testing."""
        return [
            {
                "vegetation_type": "trees",
                "min_alt": 0.2,
                "max_alt": 0.6,
                "min_slope": 0.0,
                "max_slope": 30.0,
                "scale_range": (0.8, 1.5),
                "density": 1.0,
            },
            {
                "vegetation_type": "grass",
                "min_alt": 0.0,
                "max_alt": 0.4,
                "min_slope": 0.0,
                "max_slope": 30.0,
                "scale_range": (0.5, 1.0),
                "density": 1.0,
            },
            {
                "vegetation_type": "rocks",
                "min_alt": 0.5,
                "max_alt": 1.0,
                "min_slope": 0.0,
                "max_slope": 90.0,
                "scale_range": (0.6, 1.2),
                "density": 1.0,
            },
        ]

    def test_returns_placement_dicts(
        self, heightmap_128, slope_map_128, sample_rules
    ):
        """Returns list of placement dicts with required keys."""
        points = [(25.0, 25.0), (50.0, 50.0), (75.0, 75.0)]
        result = biome_filter_points(
            points, heightmap_128, slope_map_128, sample_rules, terrain_size=100.0
        )
        assert isinstance(result, list)
        for p in result:
            assert "position" in p
            assert "vegetation_type" in p
            assert "scale" in p
            assert "rotation" in p

    def test_high_altitude_no_trees(
        self, heightmap_128, slope_map_128, sample_rules
    ):
        """Points at high altitude (>0.6) should not get 'trees' type."""
        # Point at position mapping to ~0.9 altitude
        points = [(90.0, 90.0)]
        result = biome_filter_points(
            points, heightmap_128, slope_map_128, sample_rules, terrain_size=100.0
        )
        for p in result:
            assert p["vegetation_type"] != "trees", (
                "Trees should not appear above max_alt=0.6"
            )

    def test_steep_slope_no_grass(self, heightmap_128, sample_rules):
        """Points on steep slopes should not get 'grass' type."""
        steep_slope = np.full((128, 128), 45.0)  # 45 degrees everywhere
        points = [(25.0, 25.0)]
        result = biome_filter_points(
            points, heightmap_128, steep_slope, sample_rules, terrain_size=100.0
        )
        for p in result:
            assert p["vegetation_type"] != "grass", (
                "Grass should not appear on slopes > 30 degrees"
            )

    def test_valid_vegetation_types(
        self, heightmap_128, slope_map_128, sample_rules
    ):
        """All returned vegetation types come from the rules."""
        points = poisson_disk_sample(100.0, 100.0, min_distance=5.0, seed=42)
        result = biome_filter_points(
            points, heightmap_128, slope_map_128, sample_rules, terrain_size=100.0
        )
        valid_types = {r["vegetation_type"] for r in sample_rules}
        for p in result:
            assert p["vegetation_type"] in valid_types

    def test_empty_heightmap_filters_all(self, sample_rules):
        """All-zero heightmap with min_alt=0.5 rule filters everything."""
        zero_hmap = np.zeros((128, 128))
        slope = np.full((128, 128), 10.0)
        rules = [
            {
                "vegetation_type": "alpine",
                "min_alt": 0.5,
                "max_alt": 1.0,
                "min_slope": 0.0,
                "max_slope": 90.0,
                "scale_range": (0.8, 1.2),
                "density": 1.0,
            },
        ]
        points = [(25.0, 25.0), (50.0, 50.0), (75.0, 75.0)]
        result = biome_filter_points(
            points, zero_hmap, slope, rules, terrain_size=100.0
        )
        assert len(result) == 0, "All points should be filtered on zero heightmap"


# ===================================================================
# Context-Aware Scatter
# ===================================================================


class TestContextScatter:
    """Tests for context_scatter and PROP_AFFINITY."""

    def test_prop_affinity_has_entries(self):
        """PROP_AFFINITY has building-type entries."""
        assert len(PROP_AFFINITY) >= 4
        assert "tavern" in PROP_AFFINITY
        assert "dock" in PROP_AFFINITY
        assert "blacksmith" in PROP_AFFINITY
        assert "graveyard" in PROP_AFFINITY

    def test_context_scatter_returns_placements(self):
        """context_scatter returns list of prop placement dicts."""
        buildings = [{"type": "tavern", "position": (10, 10)}]
        result = context_scatter(buildings, area_size=50, seed=0)
        assert isinstance(result, list)
        assert len(result) > 0
        for p in result:
            assert "type" in p
            assert "position" in p
            assert "rotation" in p
            assert "scale" in p

    def test_props_near_tavern_have_affinity(self):
        """Props near a tavern are mostly tavern-affinity types."""
        buildings = [{"type": "tavern", "position": (25, 25)}]
        result = context_scatter(buildings, area_size=50, seed=0)

        # Collect props within 10 units of tavern
        tavern_props = []
        tavern_types = {t for t, _ in PROP_AFFINITY["tavern"]}
        for p in result:
            dx = p["position"][0] - 25
            dy = p["position"][1] - 25
            if math.sqrt(dx * dx + dy * dy) < 10:
                tavern_props.append(p["type"])

        if tavern_props:
            matching = sum(1 for t in tavern_props if t in tavern_types)
            # At least some should be tavern props (allow for distance blending)
            assert matching > 0, (
                f"Expected some tavern affinity props near tavern, "
                f"got: {tavern_props}"
            )

    def test_props_far_from_buildings_are_generic(self):
        """Props far from any building use generic prop types."""
        # Place building in corner, check props in opposite corner
        buildings = [{"type": "tavern", "position": (5, 5), "footprint": (4, 4)}]
        result = context_scatter(buildings, area_size=80, seed=42)

        generic_types = {"rock", "log", "mushroom", "bush", "barrel"}
        far_props = []
        for p in result:
            dx = p["position"][0] - 5
            dy = p["position"][1] - 5
            if math.sqrt(dx * dx + dy * dy) > 30:
                far_props.append(p["type"])

        if far_props:
            generic_count = sum(1 for t in far_props if t in generic_types)
            # Most far props should be generic
            assert generic_count > len(far_props) * 0.5, (
                f"Expected mostly generic props far from buildings, "
                f"got {generic_count}/{len(far_props)}"
            )

    def test_no_props_inside_footprints(self):
        """No props placed inside building footprints."""
        buildings = [
            {"type": "tavern", "position": (25, 25), "footprint": (10, 10)},
        ]
        result = context_scatter(buildings, area_size=50, seed=0)

        for p in result:
            px, py = p["position"]
            # Check against footprint
            bx, by = 25, 25
            hw, hd = 5, 5  # half of footprint
            assert not (bx - hw <= px <= bx + hw and by - hd <= py <= by + hd), (
                f"Prop at {p['position']} is inside building footprint"
            )

    def test_placement_has_required_fields(self):
        """Each placement dict has type, position, rotation, scale."""
        buildings = [{"type": "dock", "position": (20, 20)}]
        result = context_scatter(buildings, area_size=40, seed=5)
        for p in result:
            assert isinstance(p["type"], str)
            assert len(p["position"]) == 2
            assert isinstance(p["rotation"], float)
            assert isinstance(p["scale"], float)


# ===================================================================
# Breakable Props
# ===================================================================


class TestBreakableVariants:
    """Tests for generate_breakable_variants."""

    def test_barrel_breakable(self):
        """Barrel generates intact and destroyed specs."""
        result = generate_breakable_variants("barrel")
        assert "intact_spec" in result
        assert "destroyed_spec" in result

    def test_intact_spec_structure(self):
        """intact_spec has geometry_ops and material."""
        result = generate_breakable_variants("barrel")
        intact = result["intact_spec"]
        assert "geometry_ops" in intact
        assert isinstance(intact["geometry_ops"], list)
        assert len(intact["geometry_ops"]) > 0
        assert "material" in intact

    def test_destroyed_spec_structure(self):
        """destroyed_spec has fragment_ops, debris_ops, and darkened material."""
        result = generate_breakable_variants("barrel")
        destroyed = result["destroyed_spec"]
        assert "fragment_ops" in destroyed
        assert "debris_ops" in destroyed
        assert "material" in destroyed

    def test_fragment_count_greater_than_one(self):
        """Barrel breaks into multiple fragments."""
        result = generate_breakable_variants("barrel")
        fragments = result["destroyed_spec"]["fragment_ops"]
        assert len(fragments) > 1

    def test_debris_ops_present(self):
        """Debris ops are non-empty for barrel."""
        result = generate_breakable_variants("barrel")
        debris = result["destroyed_spec"]["debris_ops"]
        assert len(debris) > 0

    def test_destroyed_material_darker(self):
        """Destroyed material is darker than intact material."""
        result = generate_breakable_variants("barrel")
        intact_color = result["intact_spec"]["material"]["base_color"]
        destroyed_color = result["destroyed_spec"]["material"]["base_color"]
        for ic, dc in zip(intact_color, destroyed_color):
            assert dc <= ic, "Destroyed color should be darker"

    @pytest.mark.parametrize("prop_type", ["barrel", "crate", "pot", "fence", "cart"])
    def test_all_standard_props_have_variants(self, prop_type):
        """All 5 standard props generate valid breakable variants."""
        result = generate_breakable_variants(prop_type)
        assert "intact_spec" in result
        assert "destroyed_spec" in result
        assert len(result["destroyed_spec"]["fragment_ops"]) > 1
        assert len(result["destroyed_spec"]["debris_ops"]) > 0

    def test_unknown_prop_raises(self):
        """Unknown prop type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown breakable prop"):
            generate_breakable_variants("unknown_prop")

    def test_breakable_props_dict_has_all_standard(self):
        """BREAKABLE_PROPS has all 5 standard props."""
        expected = {"barrel", "crate", "pot", "fence", "cart"}
        assert expected.issubset(set(BREAKABLE_PROPS.keys()))

    def test_deterministic_with_seed(self):
        """Same seed produces identical results."""
        a = generate_breakable_variants("barrel", seed=42)
        b = generate_breakable_variants("barrel", seed=42)
        assert a == b
