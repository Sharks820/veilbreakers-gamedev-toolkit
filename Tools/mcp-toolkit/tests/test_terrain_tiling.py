"""Tests for the tiled terrain world-space foundation."""

from __future__ import annotations

import numpy as np


class TestTerrainWorldFoundation:
    def test_adjacent_tiles_share_edge_with_world_origin(self):
        from blender_addon.handlers._terrain_noise import generate_heightmap

        tile_size = 32
        cell_size = 2.0
        tile_world_size = tile_size * cell_size

        west = generate_heightmap(
            tile_size + 1,
            tile_size + 1,
            seed=42,
            terrain_type="mountains",
            world_origin_x=0.0,
            world_origin_y=0.0,
            cell_size=cell_size,
            normalize=False,
        )
        east = generate_heightmap(
            tile_size + 1,
            tile_size + 1,
            seed=42,
            terrain_type="mountains",
            world_origin_x=tile_world_size,
            world_origin_y=0.0,
            cell_size=cell_size,
            normalize=False,
        )

        np.testing.assert_allclose(west[:, -1], east[:, 0], atol=1e-12)

    def test_world_heightmap_extract_tile_round_trip(self):
        from blender_addon.handlers._terrain_world import (
            extract_tile,
            generate_world_heightmap,
        )

        tile_size = 16
        world = generate_world_heightmap(
            tile_size * 2 + 1,
            tile_size * 2 + 1,
            seed=7,
            terrain_type="hills",
            normalize=False,
        )

        tile = extract_tile(world, 1, 1, tile_size)

        assert tile.shape == (tile_size + 1, tile_size + 1)
        np.testing.assert_array_equal(
            tile,
            world[tile_size:tile_size + tile_size + 1, tile_size:tile_size + tile_size + 1],
        )

    def test_validate_tile_seams_reports_clean(self):
        from blender_addon.handlers._terrain_world import (
            extract_tile,
            generate_world_heightmap,
            validate_tile_seams,
        )

        tile_size = 24
        world = generate_world_heightmap(
            tile_size * 2 + 1,
            tile_size * 2 + 1,
            seed=11,
            terrain_type="plains",
            normalize=False,
        )

        tiles = {
            (0, 0): extract_tile(world, 0, 0, tile_size),
            (1, 0): extract_tile(world, 1, 0, tile_size),
            (0, 1): extract_tile(world, 0, 1, tile_size),
            (1, 1): extract_tile(world, 1, 1, tile_size),
        }

        result = validate_tile_seams(tiles)

        assert result["seam_ok"] is True
        assert result["issues"] == []
        assert result["max_edge_delta"] <= 1e-12

    def test_sample_world_height_is_deterministic(self):
        from blender_addon.handlers._terrain_world import sample_world_height

        h1 = sample_world_height(
            128.0,
            256.0,
            seed=99,
            terrain_type="mountains",
            normalize=False,
        )
        h2 = sample_world_height(
            128.0,
            256.0,
            seed=99,
            terrain_type="mountains",
            normalize=False,
        )

        assert h1 == h2

    def test_theoretical_max_amplitude_formula(self):
        from blender_addon.handlers._terrain_noise import _theoretical_max_amplitude

        assert _theoretical_max_amplitude(1, 0.5) == 1.0
        assert np.isclose(_theoretical_max_amplitude(4, 0.5), 1.875)
        assert np.isclose(_theoretical_max_amplitude(8, 0.35), (1.0 - 0.35**8) / (1.0 - 0.35))
