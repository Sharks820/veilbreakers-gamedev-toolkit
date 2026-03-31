"""Tests for Voronoi-based biome distribution.

Validates:
  - voronoi_biome_distribution assigns >= 5 distinct biome IDs with biome_count=6
  - Blend weights sum to 1.0 at every cell
  - Same seed produces identical output (determinism)
  - Biome boundaries have cells with 2+ non-zero weights (transition blending)
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers._terrain_noise import voronoi_biome_distribution


class TestVoronoiBiomeDistribution:
    """Tests for the voronoi_biome_distribution pure-logic function."""

    def test_voronoi_assigns_multiple_biomes(self):
        """64x64, 6 biomes -> at least 5 distinct IDs in output."""
        biome_ids, biome_weights = voronoi_biome_distribution(
            width=64, height=64, biome_count=6, seed=42
        )
        assert biome_ids.shape == (64, 64)
        unique_ids = np.unique(biome_ids)
        assert len(unique_ids) >= 5, (
            f"Only {len(unique_ids)} unique biome IDs, expected >= 5"
        )

    def test_voronoi_weights_sum_to_one(self):
        """All cells' blend weights sum to 1.0 +/- 1e-6."""
        biome_ids, biome_weights = voronoi_biome_distribution(
            width=64, height=64, biome_count=6, seed=42
        )
        assert biome_weights.shape == (64, 64, 6)
        sums = biome_weights.sum(axis=2)
        assert np.allclose(sums, 1.0, atol=1e-6), (
            f"Weight sums range [{sums.min()}, {sums.max()}], expected all ~1.0"
        )

    def test_voronoi_deterministic(self):
        """Same seed produces identical output."""
        ids1, w1 = voronoi_biome_distribution(width=32, height=32, biome_count=6, seed=99)
        ids2, w2 = voronoi_biome_distribution(width=32, height=32, biome_count=6, seed=99)
        assert np.array_equal(ids1, ids2), "biome_ids differ for same seed"
        assert np.array_equal(w1, w2), "biome_weights differ for same seed"

    def test_voronoi_transition_produces_blending(self):
        """At biome boundaries, some cells have 2+ non-zero weights."""
        biome_ids, biome_weights = voronoi_biome_distribution(
            width=64, height=64, biome_count=6, transition_width=0.15, seed=42
        )
        # Count cells where at least 2 weights are > 0.01
        multi_weight = (biome_weights > 0.01).sum(axis=2) >= 2
        blended_count = multi_weight.sum()
        assert blended_count > 0, "No cells have blended weights at biome boundaries"

    def test_voronoi_output_shapes(self):
        """Return shapes match (height, width) and (height, width, biome_count)."""
        biome_ids, biome_weights = voronoi_biome_distribution(
            width=48, height=32, biome_count=5, seed=0
        )
        assert biome_ids.shape == (32, 48), f"ids shape {biome_ids.shape}"
        assert biome_weights.shape == (32, 48, 5), f"weights shape {biome_weights.shape}"

    def test_voronoi_biome_ids_in_range(self):
        """All biome IDs are in [0, biome_count)."""
        biome_ids, _ = voronoi_biome_distribution(
            width=64, height=64, biome_count=8, seed=7
        )
        assert biome_ids.min() >= 0
        assert biome_ids.max() < 8

    def test_voronoi_different_seeds_differ(self):
        """Different seeds produce different biome distributions."""
        ids1, _ = voronoi_biome_distribution(width=32, height=32, biome_count=6, seed=1)
        ids2, _ = voronoi_biome_distribution(width=32, height=32, biome_count=6, seed=2)
        assert not np.array_equal(ids1, ids2), "Different seeds produced identical output"

    def test_voronoi_custom_biome_names(self):
        """Custom biome_names should not affect numeric output shapes."""
        names = ["forest", "desert", "swamp", "mountain", "plains", "tundra"]
        biome_ids, biome_weights = voronoi_biome_distribution(
            width=32, height=32, biome_count=6, seed=42, biome_names=names
        )
        assert biome_ids.shape == (32, 32)
        assert biome_weights.shape == (32, 32, 6)

    def test_voronoi_weights_non_negative(self):
        """All weights should be >= 0."""
        _, biome_weights = voronoi_biome_distribution(
            width=64, height=64, biome_count=6, seed=42
        )
        assert biome_weights.min() >= 0.0, f"Negative weight: {biome_weights.min()}"
