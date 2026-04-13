"""Addendum test: stratigraphy must be consistent between adjacent tiles.

When two tiles share an edge, the strata orientation at the boundary must
match within a tolerance. If tile A's east edge has dip=15deg azimuth=90deg
and tile B's west edge has dip=45deg azimuth=270deg, there's a visible seam
in the geology. This test generates two adjacent tiles with the same seed
and asserts shared-edge orientations match.
"""

from __future__ import annotations

import numpy as np

from blender_addon.handlers.terrain_stratigraphy import (
    StratigraphyLayer,
    StratigraphyStack,
    compute_strata_orientation,
    compute_rock_hardness,
)
from blender_addon.handlers.terrain_semantics import TerrainMaskStack


def _make_stack(tile_x: int, tile_y: int, tile_size: int = 32) -> TerrainMaskStack:
    """Build a terrain stack for a tile at grid position (tile_x, tile_y).

    Uses a continuous function so adjacent tiles share edge heights.
    """
    N = tile_size + 1
    # World coords for this tile
    ox = tile_x * tile_size
    oy = tile_y * tile_size

    # Continuous height function: gentle ramp + sine hills
    ys = np.arange(N, dtype=np.float64) + oy
    xs = np.arange(N, dtype=np.float64) + ox
    xg, yg = np.meshgrid(xs, ys)
    height = 20.0 + 30.0 * np.sin(xg * 0.05) + 15.0 * np.cos(yg * 0.04)

    return TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=float(ox),
        world_origin_y=float(oy),
        tile_x=tile_x,
        tile_y=tile_y,
        height=height,
    )


def _make_strat_stack() -> StratigraphyStack:
    """Build a deterministic stratigraphy column with tilted layers."""
    return StratigraphyStack(
        base_elevation_m=-10.0,
        layers=[
            StratigraphyLayer("shale", hardness=0.25, thickness_m=20.0,
                              dip_rad=0.15, azimuth_rad=1.2),
            StratigraphyLayer("sandstone", hardness=0.55, thickness_m=30.0,
                              dip_rad=0.10, azimuth_rad=1.2),
            StratigraphyLayer("caprock", hardness=0.90, thickness_m=25.0,
                              dip_rad=0.05, azimuth_rad=1.2),
            StratigraphyLayer("soil", hardness=0.15, thickness_m=100.0,
                              dip_rad=0.0, azimuth_rad=0.0),
        ],
    )


class TestStrataNeighborConsistency:
    """Adjacent tiles must have matching strata at shared edges."""

    def test_east_west_edge_orientation_matches(self):
        """Tile (0,0) east edge must match tile (1,0) west edge orientations."""
        strat = _make_strat_stack()
        stack_a = _make_stack(0, 0)
        stack_b = _make_stack(1, 0)

        orient_a = compute_strata_orientation(stack_a, strat)
        orient_b = compute_strata_orientation(stack_b, strat)

        # East edge of A = last column; West edge of B = first column
        edge_a = orient_a[:, -1, :]  # shape (N, 3)
        edge_b = orient_b[:, 0, :]   # shape (N, 3)

        # Heights at the shared edge must match (continuous function)
        h_a = np.asarray(stack_a.height)[:, -1]
        h_b = np.asarray(stack_b.height)[:, 0]
        np.testing.assert_allclose(h_a, h_b, atol=1e-10,
                                   err_msg="Heights at shared edge don't match")

        # Strata orientations at shared edge must match
        np.testing.assert_allclose(edge_a, edge_b, atol=1e-6,
                                   err_msg="Strata orientation mismatch at E-W edge")

    def test_north_south_edge_orientation_matches(self):
        """Tile (0,0) south edge must match tile (0,1) north edge orientations."""
        strat = _make_strat_stack()
        stack_a = _make_stack(0, 0)
        stack_b = _make_stack(0, 1)

        orient_a = compute_strata_orientation(stack_a, strat)
        orient_b = compute_strata_orientation(stack_b, strat)

        # South edge of A = last row; North edge of B = first row
        edge_a = orient_a[-1, :, :]  # shape (N, 3)
        edge_b = orient_b[0, :, :]

        h_a = np.asarray(stack_a.height)[-1, :]
        h_b = np.asarray(stack_b.height)[0, :]
        np.testing.assert_allclose(h_a, h_b, atol=1e-10,
                                   err_msg="Heights at N-S shared edge don't match")

        np.testing.assert_allclose(edge_a, edge_b, atol=1e-6,
                                   err_msg="Strata orientation mismatch at N-S edge")

    def test_rock_hardness_consistent_at_shared_edge(self):
        """Rock hardness must also match at tile boundaries."""
        strat = _make_strat_stack()
        stack_a = _make_stack(0, 0)
        stack_b = _make_stack(1, 0)

        hard_a = compute_rock_hardness(stack_a, strat)
        hard_b = compute_rock_hardness(stack_b, strat)

        edge_a = hard_a[:, -1]
        edge_b = hard_b[:, 0]
        np.testing.assert_allclose(edge_a, edge_b, atol=1e-6,
                                   err_msg="Rock hardness mismatch at E-W edge")

    def test_strata_orientation_is_not_trivial(self):
        """Orientations must not all be (0,0,1) -- tilted layers should produce tilt."""
        strat = _make_strat_stack()
        stack = _make_stack(0, 0)
        orient = compute_strata_orientation(stack, strat)

        # At least some cells should have non-zero x or y components (tilted)
        xy_magnitude = np.sqrt(orient[..., 0] ** 2 + orient[..., 1] ** 2)
        assert xy_magnitude.max() > 0.01, (
            "All strata orientations are purely vertical -- tilted layers should tilt"
        )

    def test_different_strat_stacks_produce_different_orientations(self):
        """Different stratigraphy columns must produce different orientation maps."""
        stack = _make_stack(0, 0)

        strat_a = StratigraphyStack(
            base_elevation_m=-10.0,
            layers=[
                StratigraphyLayer("a", hardness=0.5, thickness_m=50.0,
                                  dip_rad=0.3, azimuth_rad=0.0),
                StratigraphyLayer("b", hardness=0.5, thickness_m=200.0,
                                  dip_rad=0.0, azimuth_rad=0.0),
            ],
        )
        strat_b = StratigraphyStack(
            base_elevation_m=-10.0,
            layers=[
                StratigraphyLayer("a", hardness=0.5, thickness_m=50.0,
                                  dip_rad=0.3, azimuth_rad=1.57),
                StratigraphyLayer("b", hardness=0.5, thickness_m=200.0,
                                  dip_rad=0.0, azimuth_rad=0.0),
            ],
        )

        orient_a = compute_strata_orientation(stack, strat_a)
        # Reset the stack channel before second call
        stack_b = _make_stack(0, 0)
        orient_b = compute_strata_orientation(stack_b, strat_b)

        # They must differ somewhere
        assert not np.allclose(orient_a, orient_b, atol=1e-6), (
            "Different stratigraphy stacks produced identical orientations"
        )
