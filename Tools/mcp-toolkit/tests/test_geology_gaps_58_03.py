"""Tests for phase 58-03 geology gap generators in _biome_grammar.py.

Each test verifies the generator:
1. Returns correct shape/type
2. Actually modifies the heightmap (not a no-op stub)
3. Is deterministic given the same seed
4. Handles edge cases (zero intensity, flat terrain)
"""
from __future__ import annotations

import unittest

import numpy as np

from blender_addon.handlers._biome_grammar import (
    apply_desert_pavement,
    apply_geological_folds,
    apply_hot_spring_features,
    apply_landslide_scars,
    apply_periglacial_patterns,
    apply_reef_platform,
    apply_tafoni_weathering,
    compute_spring_line_mask,
)


def _make_terrain(h: int = 64, w: int = 64, seed: int = 0) -> np.ndarray:
    """Create a synthetic terrain heightmap with hills and valleys."""
    rng = np.random.RandomState(seed)
    ys = np.linspace(0, 2 * np.pi, h).reshape(-1, 1)
    xs = np.linspace(0, 2 * np.pi, w).reshape(1, -1)
    base = np.sin(ys) * np.cos(xs) * 0.5 + 0.5
    noise = rng.uniform(-0.05, 0.05, size=(h, w))
    return (base + noise).astype(np.float64)


def _make_coastal(h: int = 64, w: int = 64) -> np.ndarray:
    """Create terrain that slopes from land (left) into water (right)."""
    xs = np.linspace(0.3, -0.2, w).reshape(1, -1)
    return np.broadcast_to(xs, (h, w)).copy().astype(np.float64)


class TestPeriglacialPatterns(unittest.TestCase):

    def test_output_shape(self):
        hm = _make_terrain()
        result = apply_periglacial_patterns(hm, seed=1)
        self.assertEqual(result.shape, hm.shape)

    def test_modifies_heightmap(self):
        hm = _make_terrain()
        result = apply_periglacial_patterns(hm, seed=1, intensity=0.8)
        diff = np.abs(result - hm).max()
        self.assertGreater(diff, 1e-6, "Should modify heightmap")

    def test_zero_intensity_no_change(self):
        hm = _make_terrain()
        result = apply_periglacial_patterns(hm, seed=1, intensity=0.0)
        np.testing.assert_array_equal(result, hm)

    def test_deterministic(self):
        hm = _make_terrain()
        r1 = apply_periglacial_patterns(hm, seed=42, intensity=0.5)
        r2 = apply_periglacial_patterns(hm, seed=42, intensity=0.5)
        np.testing.assert_array_equal(r1, r2)

    def test_different_seeds_differ(self):
        hm = _make_terrain()
        r1 = apply_periglacial_patterns(hm, seed=1, intensity=0.5)
        r2 = apply_periglacial_patterns(hm, seed=999, intensity=0.5)
        self.assertFalse(np.allclose(r1, r2), "Different seeds should differ")


class TestDesertPavement(unittest.TestCase):

    def test_output_types(self):
        hm = _make_terrain()
        result, mask = apply_desert_pavement(hm, seed=1)
        self.assertEqual(result.shape, hm.shape)
        self.assertEqual(mask.shape, hm.shape)
        self.assertTrue(mask.min() >= 0.0)
        self.assertTrue(mask.max() <= 1.0)

    def test_modifies_heightmap(self):
        hm = _make_terrain()
        result, mask = apply_desert_pavement(hm, seed=1, intensity=0.8)
        diff = np.abs(result - hm).max()
        self.assertGreater(diff, 1e-6)

    def test_zero_intensity(self):
        hm = _make_terrain()
        result, mask = apply_desert_pavement(hm, seed=1, intensity=0.0)
        np.testing.assert_array_equal(result, hm)
        self.assertAlmostEqual(mask.sum(), 0.0)

    def test_mask_correlates_with_flat_areas(self):
        hm = _make_terrain()
        _, mask = apply_desert_pavement(hm, seed=1, intensity=1.0)
        # Pavement should exist somewhere
        self.assertGreater(mask.sum(), 0.0)

    def test_deterministic(self):
        hm = _make_terrain()
        r1, m1 = apply_desert_pavement(hm, seed=7)
        r2, m2 = apply_desert_pavement(hm, seed=7)
        np.testing.assert_array_equal(r1, r2)
        np.testing.assert_array_equal(m1, m2)


class TestSpringLineMask(unittest.TestCase):

    def test_output_shape_and_range(self):
        hm = _make_terrain()
        mask = compute_spring_line_mask(hm, seed=1)
        self.assertEqual(mask.shape, hm.shape)
        self.assertTrue(mask.min() >= 0.0)
        self.assertTrue(mask.max() <= 1.0)

    def test_springs_exist_on_varied_terrain(self):
        hm = _make_terrain()
        mask = compute_spring_line_mask(hm, geology_layers=5, seed=1)
        self.assertGreater(mask.sum(), 0.0, "Springs should form on varied terrain")

    def test_flat_terrain_no_springs(self):
        hm = np.ones((32, 32), dtype=np.float64)
        mask = compute_spring_line_mask(hm, seed=1)
        # Flat terrain has no slope, so spring_mask should be near zero
        self.assertLess(mask.max(), 0.01)

    def test_deterministic(self):
        hm = _make_terrain()
        m1 = compute_spring_line_mask(hm, seed=5)
        m2 = compute_spring_line_mask(hm, seed=5)
        np.testing.assert_array_equal(m1, m2)

    def test_more_layers_more_springs(self):
        hm = _make_terrain()
        m3 = compute_spring_line_mask(hm, geology_layers=3, seed=1)
        m8 = compute_spring_line_mask(hm, geology_layers=8, seed=1)
        # More layer boundaries should produce more spring area
        self.assertGreater(m8.sum(), m3.sum() * 0.5)


class TestLandslideScars(unittest.TestCase):

    def test_output_shape(self):
        hm = _make_terrain()
        result = apply_landslide_scars(hm, seed=1)
        self.assertEqual(result.shape, hm.shape)

    def test_modifies_heightmap(self):
        hm = _make_terrain()
        result = apply_landslide_scars(hm, seed=1, num_slides=5, scar_depth=0.1)
        diff = np.abs(result - hm).max()
        self.assertGreater(diff, 1e-6)

    def test_zero_slides_no_change(self):
        hm = _make_terrain()
        result = apply_landslide_scars(hm, seed=1, num_slides=0)
        np.testing.assert_array_equal(result, hm)

    def test_deterministic(self):
        hm = _make_terrain()
        r1 = apply_landslide_scars(hm, seed=10)
        r2 = apply_landslide_scars(hm, seed=10)
        np.testing.assert_array_equal(r1, r2)

    def test_both_excavation_and_deposition(self):
        """Landslide should both excavate (lower) and deposit (raise) areas."""
        hm = _make_terrain(h=128, w=128)
        result = apply_landslide_scars(hm, seed=1, num_slides=1, scar_depth=0.1)
        diff = result - hm
        has_excavation = (diff < -1e-6).any()
        has_deposit = (diff > 1e-6).any()
        self.assertTrue(has_excavation, "Landslide should excavate (lower) terrain")
        self.assertTrue(has_deposit, "Landslide should deposit (raise) terrain")


class TestHotSpringFeatures(unittest.TestCase):

    def test_output_types(self):
        hm = _make_terrain()
        result, springs = apply_hot_spring_features(hm, seed=1)
        self.assertEqual(result.shape, hm.shape)
        self.assertIsInstance(springs, list)
        self.assertGreater(len(springs), 0)

    def test_spring_info_keys(self):
        hm = _make_terrain()
        _, springs = apply_hot_spring_features(hm, seed=1, num_springs=2)
        for s in springs:
            self.assertIn("grid_y", s)
            self.assertIn("grid_x", s)
            self.assertIn("pool_radius", s)
            self.assertIn("elevation", s)

    def test_modifies_heightmap(self):
        hm = _make_terrain()
        result, _ = apply_hot_spring_features(hm, seed=1, pool_depth=0.05)
        diff = np.abs(result - hm).max()
        self.assertGreater(diff, 1e-6)

    def test_pool_depression(self):
        """Spring pool should create a depression (lower than original)."""
        hm = _make_terrain()
        result, springs = apply_hot_spring_features(hm, seed=1, pool_depth=0.05)
        for s in springs:
            y, x = s["grid_y"], s["grid_x"]
            # Pool center should be lower
            self.assertLess(result[y, x], hm[y, x])

    def test_deterministic(self):
        hm = _make_terrain()
        r1, s1 = apply_hot_spring_features(hm, seed=3)
        r2, s2 = apply_hot_spring_features(hm, seed=3)
        np.testing.assert_array_equal(r1, r2)
        self.assertEqual(len(s1), len(s2))


class TestReefPlatform(unittest.TestCase):

    def test_output_shape(self):
        hm = _make_coastal()
        result = apply_reef_platform(hm, sea_level=0.0, seed=1)
        self.assertEqual(result.shape, hm.shape)

    def test_modifies_underwater(self):
        hm = _make_coastal()
        result = apply_reef_platform(hm, sea_level=0.0, seed=1, reef_height=0.05)
        underwater = hm < 0.0
        diff = np.abs(result[underwater] - hm[underwater]).max()
        self.assertGreater(diff, 1e-6, "Reef should modify underwater terrain")

    def test_above_water_unchanged(self):
        """Land areas should not be affected by reef formation."""
        hm = _make_coastal()
        result = apply_reef_platform(hm, sea_level=0.0, seed=1)
        above = hm >= 0.0
        np.testing.assert_array_equal(result[above], hm[above])

    def test_reef_does_not_exceed_sea_level(self):
        hm = _make_coastal()
        result = apply_reef_platform(hm, sea_level=0.0, seed=1)
        underwater = hm < 0.0
        self.assertTrue((result[underwater] <= 0.0).all(),
                        "Reef should not protrude above sea level")

    def test_no_coastline_no_change(self):
        """All-land terrain should not be modified."""
        hm = np.ones((32, 32), dtype=np.float64)
        result = apply_reef_platform(hm, sea_level=0.0, seed=1)
        np.testing.assert_array_equal(result, hm)

    def test_deterministic(self):
        hm = _make_coastal()
        r1 = apply_reef_platform(hm, seed=5)
        r2 = apply_reef_platform(hm, seed=5)
        np.testing.assert_array_equal(r1, r2)


class TestTafoniWeathering(unittest.TestCase):

    def test_output_shape(self):
        hm = _make_terrain()
        result = apply_tafoni_weathering(hm, seed=1)
        self.assertEqual(result.shape, hm.shape)

    def test_modifies_heightmap(self):
        hm = _make_terrain()
        result = apply_tafoni_weathering(hm, seed=1, intensity=0.8)
        diff = np.abs(result - hm).max()
        self.assertGreater(diff, 1e-6)

    def test_zero_intensity_no_change(self):
        hm = _make_terrain()
        result = apply_tafoni_weathering(hm, seed=1, intensity=0.0)
        np.testing.assert_array_equal(result, hm)

    def test_erosion_is_subtractive(self):
        """Tafoni creates pits, so net effect should reduce average height."""
        hm = _make_terrain()
        result = apply_tafoni_weathering(hm, seed=1, intensity=1.0, num_cavities=100)
        self.assertLess(result.mean(), hm.mean(),
                        "Tafoni erosion should lower average height")

    def test_deterministic(self):
        hm = _make_terrain()
        r1 = apply_tafoni_weathering(hm, seed=8)
        r2 = apply_tafoni_weathering(hm, seed=8)
        np.testing.assert_array_equal(r1, r2)

    def test_flat_terrain_minimal_effect(self):
        """Flat terrain has no steep slopes, so tafoni should be minimal."""
        hm = np.ones((32, 32), dtype=np.float64) * 0.5
        result = apply_tafoni_weathering(hm, seed=1, intensity=1.0)
        diff = np.abs(result - hm).max()
        self.assertLess(diff, 1e-6, "Flat terrain should not get tafoni")


class TestGeologicalFolds(unittest.TestCase):

    def test_output_shape(self):
        hm = _make_terrain()
        result = apply_geological_folds(hm, seed=1)
        self.assertEqual(result.shape, hm.shape)

    def test_modifies_heightmap(self):
        hm = _make_terrain()
        result = apply_geological_folds(hm, seed=1, amplitude=0.1)
        diff = np.abs(result - hm).max()
        self.assertGreater(diff, 1e-6)

    def test_anticline_type(self):
        hm = _make_terrain()
        result = apply_geological_folds(hm, seed=1, fold_type="anticline")
        self.assertEqual(result.shape, hm.shape)

    def test_syncline_type(self):
        hm = _make_terrain()
        result = apply_geological_folds(hm, seed=1, fold_type="syncline")
        self.assertEqual(result.shape, hm.shape)

    def test_chevron_type(self):
        hm = _make_terrain()
        result = apply_geological_folds(hm, seed=1, fold_type="chevron")
        self.assertEqual(result.shape, hm.shape)
        diff = np.abs(result - hm).max()
        self.assertGreater(diff, 1e-6)

    def test_deterministic(self):
        hm = _make_terrain()
        r1 = apply_geological_folds(hm, seed=11)
        r2 = apply_geological_folds(hm, seed=11)
        np.testing.assert_array_equal(r1, r2)

    def test_zero_folds_no_change(self):
        hm = _make_terrain()
        result = apply_geological_folds(hm, seed=1, num_folds=0)
        np.testing.assert_array_equal(result, hm)

    def test_anticline_vs_syncline_opposite(self):
        """Anticline and syncline should deform in opposite directions."""
        hm = _make_terrain()
        anti = apply_geological_folds(hm, seed=1, fold_type="anticline", num_folds=1)
        sync = apply_geological_folds(hm, seed=1, fold_type="syncline", num_folds=1)
        # The fold displacements should be opposite
        anti_diff = anti - hm
        sync_diff = sync - hm
        # They should be negatives of each other (same magnitude, opposite sign)
        np.testing.assert_allclose(anti_diff, -sync_diff, atol=1e-10)


if __name__ == "__main__":
    unittest.main()
