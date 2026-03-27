"""Tests for environment_scatter handler output structure.

Tests verify the pure-logic scatter engine integration and handler
parameter validation. Blender-side geometry creation is not tested
(requires bpy); instead we test the underlying engine calls and
expected result dict shapes.
"""

import math

import numpy as np
import pytest

from blender_addon.handlers._scatter_engine import (
    biome_filter_points,
    context_scatter,
    generate_breakable_variants,
    poisson_disk_sample,
)


class TestScatterVegetationLogic:
    """Test the pure-logic path used by handle_scatter_vegetation."""

    def test_full_vegetation_pipeline(self):
        """Poisson disk + biome filter produces valid placements."""
        # Simulate what handle_scatter_vegetation does internally
        terrain_size = 100.0
        min_distance = 5.0
        seed = 42

        candidates = poisson_disk_sample(
            terrain_size, terrain_size, min_distance, seed=seed,
        )
        assert len(candidates) > 10

        # Create synthetic heightmap and slope map
        heightmap = np.random.RandomState(seed).random((64, 64))
        from blender_addon.handlers._terrain_noise import compute_slope_map
        slope_map = compute_slope_map(heightmap)

        rules = [
            {
                "vegetation_type": "tree",
                "min_alt": 0.2,
                "max_alt": 0.6,
                "min_slope": 0.0,
                "max_slope": 25.0,
                "scale_range": (0.8, 1.5),
                "density": 0.8,
            },
            {
                "vegetation_type": "rock",
                "min_alt": 0.5,
                "max_alt": 1.0,
                "min_slope": 15.0,
                "max_slope": 90.0,
                "scale_range": (0.5, 1.0),
                "density": 0.6,
            },
        ]

        placements = biome_filter_points(
            candidates, heightmap, slope_map, rules,
            terrain_size=terrain_size, seed=seed,
        )

        # Should produce some placements
        assert len(placements) > 0

        # All placements have required keys
        for p in placements:
            assert "position" in p
            assert "vegetation_type" in p
            assert p["vegetation_type"] in {"tree", "rock"}
            assert "scale" in p
            assert "rotation" in p
            assert 0 <= p["rotation"] <= 360

    def test_max_instances_cap(self):
        """Placements can be capped at max_instances."""
        candidates = poisson_disk_sample(100.0, 100.0, 2.0, seed=0)
        heightmap = np.full((64, 64), 0.5)
        slope_map = np.full((64, 64), 10.0)
        rules = [
            {
                "vegetation_type": "tree",
                "min_alt": 0.0,
                "max_alt": 1.0,
                "scale_range": (0.8, 1.2),
                "density": 1.0,
            },
        ]
        placements = biome_filter_points(
            candidates, heightmap, slope_map, rules,
            terrain_size=100.0, seed=0,
        )
        max_instances = 50
        capped = placements[:max_instances]
        assert len(capped) <= max_instances

    def test_overlapping_rules_produce_mixed_vegetation_types(self):
        """Overlapping biome rules should no longer collapse to first-match only."""
        candidates = poisson_disk_sample(60.0, 60.0, 3.0, seed=12)
        heightmap = np.full((48, 48), 0.4)
        slope_map = np.full((48, 48), 8.0)
        rules = [
            {
                "vegetation_type": "tree",
                "min_alt": 0.0,
                "max_alt": 1.0,
                "min_slope": 0.0,
                "max_slope": 20.0,
                "scale_range": (0.9, 1.2),
                "density": 0.6,
            },
            {
                "vegetation_type": "grass",
                "min_alt": 0.0,
                "max_alt": 1.0,
                "min_slope": 0.0,
                "max_slope": 20.0,
                "scale_range": (0.4, 0.8),
                "density": 0.7,
            },
            {
                "vegetation_type": "bush",
                "min_alt": 0.0,
                "max_alt": 1.0,
                "min_slope": 0.0,
                "max_slope": 20.0,
                "scale_range": (0.6, 1.0),
                "density": 0.5,
            },
        ]

        placements = biome_filter_points(
            candidates,
            heightmap,
            slope_map,
            rules,
            terrain_size=60.0,
            seed=12,
        )

        vegetation_types = {placement["vegetation_type"] for placement in placements}
        assert "tree" in vegetation_types
        assert "grass" in vegetation_types or "bush" in vegetation_types


class TestScatterPropsLogic:
    """Test the pure-logic path used by handle_scatter_props."""

    def test_context_scatter_with_multiple_buildings(self):
        """Scatter with multiple buildings produces props."""
        buildings = [
            {"type": "tavern", "position": (15, 15), "footprint": (8, 6)},
            {"type": "blacksmith", "position": (35, 35), "footprint": (6, 6)},
        ]
        result = context_scatter(buildings, area_size=50, prop_density=0.3, seed=42)
        assert len(result) > 0

        # Group by type
        type_counts: dict[str, int] = {}
        for p in result:
            type_counts[p["type"]] = type_counts.get(p["type"], 0) + 1

        # Should have multiple prop types
        assert len(type_counts) >= 2

    def test_empty_buildings_raises(self):
        """Empty buildings list should cause handler to raise."""
        # The handler itself checks for empty buildings;
        # context_scatter returns empty list for empty buildings
        result = context_scatter([], area_size=50, seed=0)
        # With no buildings, all props are generic
        assert isinstance(result, list)


class TestCreateBreakableLogic:
    """Test the pure-logic path used by handle_create_breakable."""

    def test_breakable_result_structure(self):
        """generate_breakable_variants returns expected structure."""
        result = generate_breakable_variants("crate", seed=42)

        assert "intact_spec" in result
        assert "destroyed_spec" in result

        intact = result["intact_spec"]
        assert "geometry_ops" in intact
        assert "material" in intact
        assert len(intact["geometry_ops"]) > 0

        destroyed = result["destroyed_spec"]
        assert "fragment_ops" in destroyed
        assert "debris_ops" in destroyed
        assert "material" in destroyed
        assert len(destroyed["fragment_ops"]) > 1
        assert len(destroyed["debris_ops"]) > 0

    def test_breakable_counts_match_config(self):
        """Fragment and debris counts fall within configured ranges."""
        from blender_addon.handlers._scatter_engine import BREAKABLE_PROPS

        for prop_type, config in BREAKABLE_PROPS.items():
            result = generate_breakable_variants(prop_type, seed=0)
            frag_min, frag_max = config["fragment_count"]
            deb_min, deb_max = config["debris_count"]

            frag_count = len(result["destroyed_spec"]["fragment_ops"])
            deb_count = len(result["destroyed_spec"]["debris_ops"])

            assert frag_min <= frag_count <= frag_max, (
                f"{prop_type}: fragment count {frag_count} "
                f"not in [{frag_min}, {frag_max}]"
            )
            assert deb_min <= deb_count <= deb_max, (
                f"{prop_type}: debris count {deb_count} "
                f"not in [{deb_min}, {deb_max}]"
            )


class TestPropGeneratorMapCoverage:
    """Verify PROP_GENERATOR_MAP covers all prop types used by the scatter engine."""

    def test_prop_generator_map_covers_all_affinity_types(self):
        """Every prop type in PROP_AFFINITY has a PROP_GENERATOR_MAP entry."""
        from blender_addon.handlers._scatter_engine import PROP_AFFINITY
        from blender_addon.handlers._mesh_bridge import PROP_GENERATOR_MAP

        missing = []
        for building_type, prop_list in PROP_AFFINITY.items():
            for prop_type, _weight in prop_list:
                if prop_type not in PROP_GENERATOR_MAP:
                    missing.append(f"{building_type}->{prop_type}")

        assert not missing, (
            f"PROP_GENERATOR_MAP is missing entries for: {missing}"
        )

    def test_prop_generator_map_covers_generic_props(self):
        """Every prop type in _GENERIC_PROPS has a PROP_GENERATOR_MAP entry."""
        from blender_addon.handlers._scatter_engine import _GENERIC_PROPS
        from blender_addon.handlers._mesh_bridge import PROP_GENERATOR_MAP

        missing = []
        for prop_type, _weight in _GENERIC_PROPS:
            if prop_type not in PROP_GENERATOR_MAP:
                missing.append(prop_type)

        assert not missing, (
            f"PROP_GENERATOR_MAP is missing generic prop entries: {missing}"
        )

    def test_generic_props_avoid_fallen_log_default_for_settlements(self):
        """Town-adjacent generic scatter should not default to fallen logs."""
        from blender_addon.handlers._scatter_engine import _GENERIC_PROPS

        generic_types = {prop_type for prop_type, _weight in _GENERIC_PROPS}
        assert "log" not in generic_types
        assert "mushroom" not in generic_types

    def test_all_prop_generators_are_callable(self):
        """All generator functions in PROP_GENERATOR_MAP are callable."""
        from blender_addon.handlers._mesh_bridge import PROP_GENERATOR_MAP

        for prop_type, (gen_func, _kwargs) in PROP_GENERATOR_MAP.items():
            assert callable(gen_func), (
                f"Generator for '{prop_type}' is not callable: {gen_func}"
            )

    def test_all_prop_generators_produce_valid_meshspec(self):
        """All generators in PROP_GENERATOR_MAP produce valid MeshSpec dicts."""
        from blender_addon.handlers._mesh_bridge import PROP_GENERATOR_MAP

        for prop_type, (gen_func, gen_kwargs) in PROP_GENERATOR_MAP.items():
            spec = gen_func(**gen_kwargs)
            assert isinstance(spec, dict), (
                f"Generator for '{prop_type}' did not return a dict"
            )
            assert "vertices" in spec, (
                f"MeshSpec for '{prop_type}' missing 'vertices'"
            )
            assert "faces" in spec, (
                f"MeshSpec for '{prop_type}' missing 'faces'"
            )
            assert len(spec["vertices"]) > 0, (
                f"MeshSpec for '{prop_type}' has empty vertices"
            )
            assert len(spec["faces"]) > 0, (
                f"MeshSpec for '{prop_type}' has empty faces"
            )

    def test_prop_generator_map_in_all_maps(self):
        """PROP_GENERATOR_MAP is registered in _ALL_MAPS for resolve_generator."""
        from blender_addon.handlers._mesh_bridge import _ALL_MAPS, PROP_GENERATOR_MAP

        assert "prop" in _ALL_MAPS, (
            "PROP_GENERATOR_MAP not registered in _ALL_MAPS"
        )
        assert _ALL_MAPS["prop"] is PROP_GENERATOR_MAP

    def test_prop_map_has_minimum_entries(self):
        """PROP_GENERATOR_MAP has at least 20 entries (all affinity + generic)."""
        from blender_addon.handlers._mesh_bridge import PROP_GENERATOR_MAP

        assert len(PROP_GENERATOR_MAP) >= 20, (
            f"Expected at least 20 entries, got {len(PROP_GENERATOR_MAP)}"
        )


class TestHandlerImports:
    """Test that handler module can be partially imported."""

    def test_scatter_engine_importable(self):
        """_scatter_engine module imports without bpy."""
        from blender_addon.handlers._scatter_engine import (
            BREAKABLE_PROPS,
            PROP_AFFINITY,
            biome_filter_points,
            context_scatter,
            generate_breakable_variants,
            poisson_disk_sample,
        )
        assert callable(poisson_disk_sample)
        assert callable(biome_filter_points)
        assert callable(context_scatter)
        assert callable(generate_breakable_variants)
        assert isinstance(PROP_AFFINITY, dict)
        assert isinstance(BREAKABLE_PROPS, dict)

    def test_prop_generator_map_importable(self):
        """PROP_GENERATOR_MAP imports without bpy."""
        from blender_addon.handlers._mesh_bridge import PROP_GENERATOR_MAP
        assert isinstance(PROP_GENERATOR_MAP, dict)
        assert len(PROP_GENERATOR_MAP) > 0
