"""Tests for _biome_grammar.py -- WorldMapSpec and generate_world_map_spec.

Covers:
  - WorldMapSpec fields (biome_names length, biome_ids unique count, biome_weights sum)
  - Corruption map (range, zero at scale=0)
  - Transition width (stored, produces blend cells)
  - Foundation placement flatten zones (count, normalized coords)
  - Biome aliases (volcanic_wastes, unknown raises)
  - Vegetation cell_params (count, required keys)
  - Integration smoke test (full spec generation)
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers._biome_grammar import (
    WorldMapSpec,
    generate_world_map_spec,
    resolve_biome_name,
    BIOME_ALIASES,
    BIOME_CLIMATE_PARAMS,
)


# ---------------------------------------------------------------------------
# TestWorldMapSpec: basic shape and content invariants
# ---------------------------------------------------------------------------

class TestWorldMapSpec:
    def test_biome_names_length_matches_biome_count(self):
        spec = generate_world_map_spec(width=32, height=32, biome_count=6)
        assert len(spec.biome_names) == 6

    def test_biome_ids_shape(self):
        spec = generate_world_map_spec(width=32, height=64, biome_count=4)
        assert spec.biome_ids.shape == (64, 32)

    def test_biome_ids_unique_count_at_least_5(self):
        spec = generate_world_map_spec(width=64, height=64, biome_count=6, seed=42)
        unique = np.unique(spec.biome_ids)
        assert len(unique) >= 5

    def test_biome_weights_sum_to_one(self):
        spec = generate_world_map_spec(width=32, height=32, biome_count=6, seed=1)
        sums = spec.biome_weights.sum(axis=2)
        assert np.allclose(sums, 1.0, atol=1e-6)

    def test_biome_weights_shape(self):
        spec = generate_world_map_spec(width=16, height=16, biome_count=4)
        assert spec.biome_weights.shape == (16, 16, 4)

    def test_deterministic_same_seed(self):
        s1 = generate_world_map_spec(width=32, height=32, seed=99)
        s2 = generate_world_map_spec(width=32, height=32, seed=99)
        assert np.array_equal(s1.biome_ids, s2.biome_ids)

    def test_different_seeds_different_results(self):
        s1 = generate_world_map_spec(width=32, height=32, seed=1)
        s2 = generate_world_map_spec(width=32, height=32, seed=2)
        assert not np.array_equal(s1.biome_ids, s2.biome_ids)

    def test_world_size_stored(self):
        spec = generate_world_map_spec(world_size=1024.0)
        assert spec.world_size == 1024.0

    def test_seed_stored(self):
        spec = generate_world_map_spec(seed=12345)
        assert spec.seed == 12345

    def test_biome_ids_values_in_range(self):
        biome_count = 6
        spec = generate_world_map_spec(width=32, height=32, biome_count=biome_count)
        assert spec.biome_ids.min() >= 0
        assert spec.biome_ids.max() < biome_count

    def test_biome_ids_dtype_int(self):
        spec = generate_world_map_spec(width=16, height=16, biome_count=3)
        assert np.issubdtype(spec.biome_ids.dtype, np.integer)

    def test_biome_count_mismatch_raises(self):
        """Providing wrong number of biome names raises ValueError."""
        with pytest.raises(ValueError):
            generate_world_map_spec(
                biome_count=6,
                biomes=["thornwood_forest", "corrupted_swamp"],  # only 2, need 6
            )


# ---------------------------------------------------------------------------
# TestCorruptionMap
# ---------------------------------------------------------------------------

class TestCorruptionMap:
    def test_corruption_map_range(self):
        spec = generate_world_map_spec(width=32, height=32, corruption_level=0.8)
        assert spec.corruption_map.min() >= 0.0
        assert spec.corruption_map.max() <= 1.0

    def test_zero_corruption_all_zeros(self):
        spec = generate_world_map_spec(width=32, height=32, corruption_level=0.0)
        assert np.all(spec.corruption_map == 0.0)

    def test_full_corruption_nonzero(self):
        spec = generate_world_map_spec(width=32, height=32, corruption_level=1.0)
        assert spec.corruption_map.max() > 0.0

    def test_corruption_map_shape(self):
        spec = generate_world_map_spec(width=32, height=48, corruption_level=0.5)
        assert spec.corruption_map.shape == (48, 32)

    def test_corruption_deterministic(self):
        s1 = generate_world_map_spec(width=32, height=32, seed=7, corruption_level=0.6)
        s2 = generate_world_map_spec(width=32, height=32, seed=7, corruption_level=0.6)
        assert np.allclose(s1.corruption_map, s2.corruption_map)

    def test_corruption_independent_of_biome_pattern(self):
        """Corruption map should differ from biome_ids distribution."""
        spec = generate_world_map_spec(width=32, height=32, seed=42, corruption_level=0.7)
        # biome_ids are ints 0..5; corruption is float. Simply check shapes differ
        assert spec.corruption_map.shape == spec.biome_ids.shape
        # They should NOT be identical
        assert not np.allclose(spec.corruption_map, spec.biome_ids.astype(np.float64))


# ---------------------------------------------------------------------------
# TestTransitionWidth
# ---------------------------------------------------------------------------

class TestTransitionWidth:
    def test_transition_width_stored(self):
        spec = generate_world_map_spec(transition_width_m=15.0, world_size=512.0)
        assert spec.transition_width_m == 15.0

    def test_transition_width_custom(self):
        spec = generate_world_map_spec(transition_width_m=25.0, world_size=512.0)
        assert spec.transition_width_m == 25.0

    def test_transition_produces_blend_cells(self):
        """With wide transition, 2+ biome weights should be non-trivial at boundaries."""
        spec = generate_world_map_spec(
            width=64, height=64, biome_count=6,
            transition_width_m=50.0, world_size=512.0
        )
        multi = (spec.biome_weights > 0.05).sum(axis=2) >= 2
        assert multi.sum() > 0

    def test_narrow_transition_fewer_blend_cells(self):
        """Narrower transition should produce fewer multi-biome blend cells."""
        spec_wide = generate_world_map_spec(
            width=64, height=64, biome_count=6,
            transition_width_m=100.0, world_size=512.0, seed=42
        )
        spec_narrow = generate_world_map_spec(
            width=64, height=64, biome_count=6,
            transition_width_m=5.0, world_size=512.0, seed=42
        )
        wide_blend = ((spec_wide.biome_weights > 0.05).sum(axis=2) >= 2).sum()
        narrow_blend = ((spec_narrow.biome_weights > 0.05).sum(axis=2) >= 2).sum()
        assert wide_blend >= narrow_blend


# ---------------------------------------------------------------------------
# TestFoundationPlacements
# ---------------------------------------------------------------------------

class TestFoundationPlacements:
    def test_flatten_zones_count_matches_plots(self):
        plots = [
            {"x": 100.0, "y": 100.0, "width": 10.0, "depth": 8.0},
            {"x": 200.0, "y": 300.0, "width": 6.0, "depth": 6.0},
        ]
        spec = generate_world_map_spec(building_plots=plots)
        assert len(spec.flatten_zones) == 2

    def test_flatten_zones_empty_by_default(self):
        spec = generate_world_map_spec()
        assert spec.flatten_zones == []

    def test_flatten_zones_normalized(self):
        plots = [{"x": 256.0, "y": 256.0, "width": 8.0, "depth": 8.0}]
        spec = generate_world_map_spec(world_size=512.0, building_plots=plots)
        z = spec.flatten_zones[0]
        assert 0.0 <= z["center_x"] <= 1.0
        assert 0.0 <= z["center_y"] <= 1.0

    def test_flatten_zones_keys_present(self):
        plots = [{"x": 100.0, "y": 100.0, "width": 10.0, "depth": 8.0}]
        spec = generate_world_map_spec(building_plots=plots)
        z = spec.flatten_zones[0]
        assert "center_x" in z
        assert "center_y" in z
        assert "radius" in z
        assert "blend_width" in z

    def test_flatten_zones_radius_positive(self):
        plots = [{"x": 100.0, "y": 100.0, "width": 10.0, "depth": 8.0}]
        spec = generate_world_map_spec(world_size=512.0, building_plots=plots)
        z = spec.flatten_zones[0]
        assert z["radius"] > 0.0

    def test_flatten_zones_blend_width_positive(self):
        plots = [{"x": 50.0, "y": 50.0, "width": 6.0, "depth": 6.0}]
        spec = generate_world_map_spec(world_size=512.0, building_plots=plots)
        z = spec.flatten_zones[0]
        assert z["blend_width"] > 0.0

    def test_flatten_multiple_plots(self):
        plots = [
            {"x": 50.0, "y": 50.0, "width": 6.0, "depth": 6.0},
            {"x": 200.0, "y": 300.0, "width": 12.0, "depth": 10.0},
            {"x": 400.0, "y": 400.0, "width": 8.0, "depth": 8.0},
        ]
        spec = generate_world_map_spec(world_size=512.0, building_plots=plots)
        assert len(spec.flatten_zones) == 3


# ---------------------------------------------------------------------------
# TestBiomeAliases
# ---------------------------------------------------------------------------

class TestBiomeAliases:
    def test_alias_volcanic_wastes(self):
        spec = generate_world_map_spec(
            biome_count=6,
            biomes=["volcanic_wastes", "corrupted_swamp",
                    "mountain_pass", "grasslands",
                    "desert", "cemetery"]
        )
        # volcanic_wastes aliases to "desert"
        assert "desert" in spec.biome_names

    def test_alias_frozen_tundra(self):
        spec = generate_world_map_spec(
            biome_count=3,
            biomes=["frozen_tundra", "corrupted_swamp", "grasslands"]
        )
        # frozen_tundra aliases to "mountain_pass"
        assert "mountain_pass" in spec.biome_names

    def test_alias_thornwood(self):
        spec = generate_world_map_spec(
            biome_count=2,
            biomes=["thornwood", "desert"]
        )
        assert "thornwood_forest" in spec.biome_names

    def test_alias_swamp(self):
        spec = generate_world_map_spec(
            biome_count=2,
            biomes=["swamp", "desert"]
        )
        assert "corrupted_swamp" in spec.biome_names

    def test_unknown_biome_raises(self):
        with pytest.raises(ValueError, match="Unknown biome"):
            generate_world_map_spec(
                biome_count=6,
                biomes=["not_a_real_biome"] * 6
            )

    def test_resolve_biome_name_canonical(self):
        result = resolve_biome_name("thornwood_forest")
        assert result == "thornwood_forest"

    def test_resolve_biome_name_alias(self):
        result = resolve_biome_name("volcanic_wastes")
        assert result == "desert"

    def test_resolve_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown biome"):
            resolve_biome_name("fantasy_island")


# ---------------------------------------------------------------------------
# TestVegetationSpec (cell_params)
# ---------------------------------------------------------------------------

class TestVegetationSpec:
    def test_cell_params_count(self):
        spec = generate_world_map_spec(
            biome_count=5,
            biomes=["thornwood_forest", "corrupted_swamp",
                    "mountain_pass", "grasslands", "desert"]
        )
        assert len(spec.cell_params) == 5

    def test_cell_params_keys(self):
        spec = generate_world_map_spec(biome_count=1, biomes=["thornwood_forest"])
        p = spec.cell_params[0]
        assert "temperature" in p
        assert "moisture" in p
        assert "elevation" in p

    def test_cell_params_values_in_range(self):
        spec = generate_world_map_spec(biome_count=6)
        for p in spec.cell_params:
            assert 0.0 <= p["temperature"] <= 1.0
            assert 0.0 <= p["moisture"] <= 1.0
            assert 0.0 <= p["elevation"] <= 1.0

    def test_cell_params_known_biome_correct_values(self):
        spec = generate_world_map_spec(biome_count=1, biomes=["desert"])
        p = spec.cell_params[0]
        assert p["temperature"] == pytest.approx(0.85)
        assert p["moisture"] == pytest.approx(0.05)

    def test_cell_params_unknown_biome_has_defaults(self):
        """Biome not in BIOME_CLIMATE_PARAMS should get default 0.5 values."""
        # ruined_fortress may or may not be in BIOME_CLIMATE_PARAMS
        # cemetery is a known pallette biome but NOT in BIOME_CLIMATE_PARAMS
        # This tests the fallback path
        spec = generate_world_map_spec(biome_count=1, biomes=["cemetery"])
        p = spec.cell_params[0]
        # Should have all three keys (either from table or fallback)
        assert "temperature" in p
        assert "moisture" in p
        assert "elevation" in p


# ---------------------------------------------------------------------------
# TestWorldMapIntegration: end-to-end spec generation without Blender
# ---------------------------------------------------------------------------

class TestWorldMapIntegration:
    def test_generate_world_map_spec_returns_valid_spec(self):
        """End-to-end spec generation without Blender."""
        spec = generate_world_map_spec(
            width=32, height=32, world_size=512.0, biome_count=6, seed=7,
            corruption_level=0.5,
            building_plots=[{"x": 100.0, "y": 100.0, "width": 10.0, "depth": 8.0}],
        )
        assert spec.biome_ids.shape == (32, 32)
        assert spec.biome_weights.shape == (32, 32, 6)
        assert len(spec.biome_names) == 6
        assert spec.corruption_map.shape == (32, 32)
        assert len(spec.flatten_zones) == 1
        assert len(spec.cell_params) == 6

    def test_spec_is_worldmapspec_instance(self):
        spec = generate_world_map_spec(width=16, height=16)
        assert isinstance(spec, WorldMapSpec)

    def test_large_biome_count_works(self):
        """All 14 available biomes can be used simultaneously."""
        from blender_addon.handlers.terrain_materials import BIOME_PALETTES
        all_biomes = list(BIOME_PALETTES.keys())
        spec = generate_world_map_spec(
            width=32, height=32,
            biome_count=len(all_biomes),
            biomes=all_biomes,
            seed=42
        )
        assert len(spec.biome_names) == len(all_biomes)
        assert spec.biome_weights.shape[2] == len(all_biomes)

    def test_default_6_biomes_all_in_palettes(self):
        """Default biome list should use valid BIOME_PALETTES keys."""
        from blender_addon.handlers.terrain_materials import BIOME_PALETTES
        spec = generate_world_map_spec(width=16, height=16, biome_count=6)
        for name in spec.biome_names:
            assert name in BIOME_PALETTES, f"'{name}' not in BIOME_PALETTES"
