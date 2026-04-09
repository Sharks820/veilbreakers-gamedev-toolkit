"""Addendum 2.A.8 — 10 adjacent-tile contract requirements.

Verifies the "Generate Adjacent Tile" invariants:
- Same seed + different tile coords produce continuous heights at shared edges
- theoretical_max_amplitude normalization is tile-invariant
- Power-of-2+1 tile resolutions are accepted (257, 513, 1025)
- World-space noise → identical samples at shared coordinates
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blender_addon.handlers._terrain_world import (
    extract_tile,
    generate_world_heightmap,
    sample_world_height,
)
from blender_addon.handlers.terrain_semantics import (
    BBox,
    TerrainIntentState,
    TerrainMaskStack,
)
from blender_addon.handlers.terrain_twelve_step import run_twelve_step_world_terrain
from blender_addon.handlers.terrain_world_math import theoretical_max_amplitude


# ---------------------------------------------------------------------------
# Requirement 1 — Same heights at shared edge (deterministic world-space noise)
# ---------------------------------------------------------------------------


def test_shared_edge_bit_identical_between_horizontal_neighbors():
    tile_size = 32
    full_width = 2 * tile_size + 1
    world = generate_world_heightmap(
        width=full_width,
        height=tile_size + 1,
        scale=100.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        cell_size=1.0,
        seed=99,
        terrain_type="mountains",
        normalize=False,
    )
    tile_a = extract_tile(world, 0, 0, tile_size)
    tile_b = extract_tile(world, 1, 0, tile_size)
    # East edge of A == west edge of B, bit identical
    np.testing.assert_array_equal(tile_a[:, -1], tile_b[:, 0])


def test_shared_edge_bit_identical_between_vertical_neighbors():
    tile_size = 32
    full_height = 2 * tile_size + 1
    world = generate_world_heightmap(
        width=tile_size + 1,
        height=full_height,
        scale=100.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        cell_size=1.0,
        seed=99,
        terrain_type="mountains",
        normalize=False,
    )
    tile_a = extract_tile(world, 0, 0, tile_size)
    tile_b = extract_tile(world, 0, 1, tile_size)
    # North edge of A == south edge of B
    np.testing.assert_array_equal(tile_a[-1, :], tile_b[0, :])


def test_shared_corner_identical_across_four_tiles():
    tile_size = 16
    full = 2 * tile_size + 1
    world = generate_world_heightmap(
        width=full,
        height=full,
        scale=100.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        cell_size=1.0,
        seed=55,
        terrain_type="mountains",
        normalize=False,
    )
    t00 = extract_tile(world, 0, 0, tile_size)
    t10 = extract_tile(world, 1, 0, tile_size)
    t01 = extract_tile(world, 0, 1, tile_size)
    t11 = extract_tile(world, 1, 1, tile_size)
    # All four share the center corner
    corner = t00[tile_size, tile_size]
    assert corner == t10[tile_size, 0]
    assert corner == t01[0, tile_size]
    assert corner == t11[0, 0]


def test_world_space_sampling_same_coord_same_value():
    # Sampling the same world coordinate via different tile origins must agree
    s1 = sample_world_height(
        50.0,
        50.0,
        scale=100.0,
        cell_size=1.0,
        seed=7,
        terrain_type="mountains",
        normalize=False,
    )
    # Sample from a larger window that also covers (50, 50)
    window = generate_world_heightmap(
        width=3,
        height=3,
        scale=100.0,
        world_origin_x=49.0,
        world_origin_y=49.0,
        cell_size=1.0,
        seed=7,
        terrain_type="mountains",
        normalize=False,
    )
    s2 = float(np.asarray(window)[1, 1])
    assert math.isclose(s1, s2, rel_tol=1e-12, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# Requirement 2 — theoretical_max_amplitude normalization is tile-invariant
# ---------------------------------------------------------------------------


def test_theoretical_max_amplitude_does_not_depend_on_tile_coord():
    # The normalization constant is a pure function of persistence + octaves
    persistence, octaves = 0.5, 6
    const_a = theoretical_max_amplitude(persistence, octaves)
    const_b = theoretical_max_amplitude(persistence, octaves)
    assert const_a == const_b
    # And it is positive and bounded above by octaves (for persistence < 1)
    assert 0.0 < const_a < octaves


def test_theoretical_max_amplitude_strictly_monotonic_in_octaves():
    prev = 0.0
    for octaves in range(1, 10):
        v = theoretical_max_amplitude(0.5, octaves)
        assert v > prev
        prev = v


# ---------------------------------------------------------------------------
# Requirement 3 — Power-of-2+1 tile resolutions accepted (257, 513, 1025)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tile_size", [256, 512, 1024])
def test_power_of_two_tile_sizes_accepted(tile_size):
    # Construct with the new (tile_size+1, tile_size+1) shape
    height = np.zeros((tile_size + 1, tile_size + 1), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    assert stack.tile_size == tile_size
    assert stack.height.shape == (tile_size + 1, tile_size + 1)


def test_non_unity_tile_size_still_constructs_with_legacy_shape():
    # tile_size 100 is not power-of-2 — but legacy shape (100, 100) is allowed
    ts = 100
    stack = TerrainMaskStack(
        tile_size=ts,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=np.zeros((ts, ts), dtype=np.float64),
    )
    assert stack.height.shape == (ts, ts)


# ---------------------------------------------------------------------------
# Requirement 4 — 12-step orchestrator satisfies seam contract across 2x2
# ---------------------------------------------------------------------------


def test_twelve_step_2x2_seam_ok():
    intent = TerrainIntentState(
        seed=101,
        region_bounds=BBox(0.0, 0.0, 200.0, 200.0),
        tile_size=16,
        cell_size=1.0,
    )
    result = run_twelve_step_world_terrain(intent, 2, 2)
    assert result["seam_report"]["seam_ok"] is True


def test_twelve_step_different_seeds_diverge():
    intent_a = TerrainIntentState(
        seed=1,
        region_bounds=BBox(0.0, 0.0, 200.0, 200.0),
        tile_size=16,
        cell_size=1.0,
    )
    intent_b = TerrainIntentState(
        seed=2,
        region_bounds=BBox(0.0, 0.0, 200.0, 200.0),
        tile_size=16,
        cell_size=1.0,
    )
    ra = run_twelve_step_world_terrain(intent_a, 2, 2)
    rb = run_twelve_step_world_terrain(intent_b, 2, 2)
    assert not np.array_equal(ra["world_heightmap"], rb["world_heightmap"])
