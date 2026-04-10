"""Test 12-step world terrain orchestration — Addendum 2.A.7 compliance.

Verifies the canonical run_twelve_step_world_terrain sequence on a 2x2
tile grid:
  - Full world heightmap is generated before tile split
  - Flow maps computed on full world before split
  - extract_tile produces valid per-tile arrays
  - Tiles at shared edges have matching height values
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers.terrain_semantics import (
    BBox,
    TerrainIntentState,
)
from blender_addon.handlers.terrain_twelve_step import (
    run_twelve_step_world_terrain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TILE_SIZE = 16
GRID_X = 2
GRID_Y = 2
SEED = 7777


def _make_intent() -> TerrainIntentState:
    total_x = GRID_X * TILE_SIZE + 1
    total_y = GRID_Y * TILE_SIZE + 1
    return TerrainIntentState(
        seed=SEED,
        region_bounds=BBox(0.0, 0.0, float(total_x), float(total_y)),
        tile_size=TILE_SIZE,
        cell_size=1.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTwelveStepOrchestration:
    """Tests for the canonical 12-step world terrain sequence."""

    def test_sequence_contains_all_twelve_steps(self):
        """The returned sequence list must have exactly 12 named steps."""
        intent = _make_intent()
        result = run_twelve_step_world_terrain(intent, GRID_X, GRID_Y)
        seq = result["sequence"]
        assert len(seq) == 12
        assert seq[0].startswith("1_")
        assert seq[-1].startswith("12_")

    def test_world_heightmap_generated_before_split(self):
        """World heightmap must exist and be the full (grid*tile+1) shape."""
        intent = _make_intent()
        result = run_twelve_step_world_terrain(intent, GRID_X, GRID_Y)
        world_hmap = result["world_heightmap"]
        expected_shape = (GRID_Y * TILE_SIZE + 1, GRID_X * TILE_SIZE + 1)
        assert world_hmap.shape == expected_shape
        # Must not be all zeros (generation actually ran)
        assert world_hmap.std() > 0.0, "World heightmap is flat — generation did not run"

    def test_flow_map_computed_on_full_world(self):
        """Flow map must be computed before tile split (step 7 before step 9)."""
        intent = _make_intent()
        result = run_twelve_step_world_terrain(intent, GRID_X, GRID_Y)
        seq = result["sequence"]
        flow_idx = next(i for i, s in enumerate(seq) if "flow" in s.lower())
        tile_idx = next(i for i, s in enumerate(seq) if "tile" in s.lower())
        assert flow_idx < tile_idx, "Flow map must be computed before tile extraction"

        flow = result["world_flow_map"]
        assert flow is not None
        # Flow map should have meaningful content (dict with keys)
        assert isinstance(flow, dict)
        assert len(flow) > 0

    def test_extract_tile_produces_valid_per_tile_arrays(self):
        """Each tile stack has the correct height shape: (tile_size+1, tile_size+1)."""
        intent = _make_intent()
        result = run_twelve_step_world_terrain(intent, GRID_X, GRID_Y)
        tile_stacks = result["tile_stacks"]
        assert len(tile_stacks) == GRID_X * GRID_Y, "Wrong number of tiles extracted"
        expected_tile_shape = (TILE_SIZE + 1, TILE_SIZE + 1)
        for (tx, ty), stack in tile_stacks.items():
            assert stack.height.shape == expected_tile_shape, (
                f"Tile ({tx},{ty}) has shape {stack.height.shape}, "
                f"expected {expected_tile_shape}"
            )
            # Tiles should carry real data, not zeros
            assert stack.height.std() > 0.0, (
                f"Tile ({tx},{ty}) height is flat — extraction broke"
            )

    def test_shared_edge_heights_match(self):
        """Adjacent tiles must share identical height values along their seam edge."""
        intent = _make_intent()
        result = run_twelve_step_world_terrain(intent, GRID_X, GRID_Y)
        seam = result["seam_report"]
        assert seam["seam_ok"] is True, f"Seam validation failed: {seam['issues']}"
        assert seam["max_edge_delta"] < 1e-6

    def test_deterministic_with_same_seed(self):
        """Two runs with the same seed produce identical world heightmaps."""
        intent_a = _make_intent()
        intent_b = _make_intent()
        result_a = run_twelve_step_world_terrain(intent_a, GRID_X, GRID_Y)
        result_b = run_twelve_step_world_terrain(intent_b, GRID_X, GRID_Y)
        np.testing.assert_array_equal(
            result_a["world_heightmap"],
            result_b["world_heightmap"],
        )

    def test_tile_transforms_have_correct_origins(self):
        """Each tile transform origin must reflect tile grid position."""
        intent = _make_intent()
        result = run_twelve_step_world_terrain(intent, GRID_X, GRID_Y)
        transforms = result["tile_transforms"]
        for (tx, ty), xform in transforms.items():
            expected_ox = float(tx * TILE_SIZE * 1.0)  # cell_size = 1.0
            expected_oy = float(ty * TILE_SIZE * 1.0)
            assert xform.origin_world[0] == pytest.approx(expected_ox, abs=1e-6)
            assert xform.origin_world[1] == pytest.approx(expected_oy, abs=1e-6)
