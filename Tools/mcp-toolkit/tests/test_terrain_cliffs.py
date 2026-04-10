"""Bundle B — tests for terrain_cliffs.py.

Pure-numpy cliff analysis. All fixtures construct a synthetic heightmap
that guarantees a deterministic cliff signature.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_pass_registry():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    yield
    TerrainPassController.clear_registry()


def _build_cliff_state(tile_size: int = 48):
    """Build a state with a single synthetic cliff in the centre.

    The heightmap has:
      - a flat plateau at z = 40 in the top half
      - a flat plain at z = 5 in the bottom half
      - a sharp vertical drop between them
    This gives a single connected cliff region with high slope and
    clear lip geometry.
    """
    from blender_addon.handlers.terrain_masks import compute_base_masks
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
    )

    N = tile_size + 1
    height = np.zeros((N, N), dtype=np.float64)
    # Top half (rows < N/2): high plateau; bottom half: low plain
    half = N // 2
    height[:half, :] = 40.0
    height[half:, :] = 5.0
    # Add a little noise so slope + curvature don't degenerate at edges
    rng = np.random.default_rng(42)
    height += rng.normal(0.0, 0.05, size=height.shape)

    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    compute_base_masks(
        height,
        cell_size=1.0,
        tile_coords=(0, 0),
        stack=stack,
        pass_name="structural_masks",
    )

    region_bounds = BBox(0.0, 0.0, float(N), float(N))
    intent = TerrainIntentState(
        seed=1234,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


def _build_two_cliff_state(tile_size: int = 48):
    """Two isolated high plateaus separated by low ground — two cliffs."""
    from blender_addon.handlers.terrain_masks import compute_base_masks
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
    )

    N = tile_size + 1
    height = np.full((N, N), 5.0, dtype=np.float64)
    # Left plateau
    height[10:22, 5:15] = 35.0
    # Right plateau (disconnected from the left)
    height[10:22, 30:40] = 35.0
    rng = np.random.default_rng(7)
    height += rng.normal(0.0, 0.02, size=height.shape)

    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    compute_base_masks(
        height,
        cell_size=1.0,
        tile_coords=(0, 0),
        stack=stack,
        pass_name="structural_masks",
    )
    region_bounds = BBox(0.0, 0.0, float(N), float(N))
    intent = TerrainIntentState(
        seed=1,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# Candidate mask
# ---------------------------------------------------------------------------


def test_candidate_mask_respects_slope_threshold():
    from blender_addon.handlers.terrain_cliffs import build_cliff_candidate_mask

    state = _build_cliff_state()
    low = build_cliff_candidate_mask(state.mask_stack, slope_threshold_deg=20.0)
    high = build_cliff_candidate_mask(state.mask_stack, slope_threshold_deg=85.0)
    # A lower threshold must produce AT LEAST as many candidate cells
    assert int(low.sum()) >= int(high.sum())
    assert int(low.sum()) > 0, "cliff heightmap should produce candidates at 20 deg"


def test_candidate_mask_excludes_hero_exclusion():
    from blender_addon.handlers.terrain_cliffs import build_cliff_candidate_mask

    state = _build_cliff_state()
    # Exclude the upper half of the grid — should eliminate the cliff
    excl = np.zeros_like(state.mask_stack.height, dtype=bool)
    excl[:] = True
    state.mask_stack.set("hero_exclusion", excl, "fixture")
    mask = build_cliff_candidate_mask(state.mask_stack, slope_threshold_deg=20.0)
    assert int(mask.sum()) == 0


def test_candidate_mask_drops_small_clusters():
    from blender_addon.handlers.terrain_cliffs import build_cliff_candidate_mask

    state = _build_cliff_state()
    mask = build_cliff_candidate_mask(
        state.mask_stack,
        slope_threshold_deg=20.0,
        min_cluster_size=10000,  # too large — should drop everything
    )
    assert int(mask.sum()) == 0


# ---------------------------------------------------------------------------
# Connected components / carving
# ---------------------------------------------------------------------------


def test_carve_cliff_system_finds_single_cliff():
    from blender_addon.handlers.terrain_cliffs import carve_cliff_system

    state = _build_cliff_state()
    cliffs = carve_cliff_system(state, region=None)
    assert len(cliffs) >= 1
    top = cliffs[0]
    assert top.face_mask.any()
    assert top.cell_count > 0
    assert top.max_height_m > top.min_height_m


def test_carve_cliff_system_separates_two_components():
    from blender_addon.handlers.terrain_cliffs import carve_cliff_system

    state = _build_two_cliff_state()
    cliffs = carve_cliff_system(state, region=None, min_component_size=5)
    # Two plateaus -> at least two cliff components
    assert len(cliffs) >= 2
    # Component face masks must be disjoint
    a = cliffs[0].face_mask
    b = cliffs[1].face_mask
    assert int((a & b).sum()) == 0


def test_carve_cliff_system_respects_max_cliff_count():
    from blender_addon.handlers.terrain_cliffs import carve_cliff_system

    state = _build_two_cliff_state()
    cliffs = carve_cliff_system(
        state, region=None, max_cliff_count=1, min_component_size=5
    )
    assert len(cliffs) == 1


# ---------------------------------------------------------------------------
# Ledges
# ---------------------------------------------------------------------------


def test_add_cliff_ledges_scales_with_span():
    from blender_addon.handlers.terrain_cliffs import (
        add_cliff_ledges,
        carve_cliff_system,
    )

    state = _build_cliff_state()
    cliffs = carve_cliff_system(state, region=None)
    assert cliffs
    cliff = cliffs[0]
    # span is ~35m => count should be 3
    add_cliff_ledges(cliff, height=state.mask_stack.height)
    assert 1 <= len(cliff.ledges) <= 3


def test_add_cliff_ledges_honors_explicit_count():
    from blender_addon.handlers.terrain_cliffs import (
        add_cliff_ledges,
        carve_cliff_system,
    )

    state = _build_cliff_state()
    cliffs = carve_cliff_system(state, region=None)
    cliff = cliffs[0]
    add_cliff_ledges(cliff, count=2, height=state.mask_stack.height)
    assert len(cliff.ledges) <= 2


# ---------------------------------------------------------------------------
# Talus
# ---------------------------------------------------------------------------


def test_talus_field_disjoint_from_face_mask():
    from blender_addon.handlers.terrain_cliffs import (
        build_talus_field,
        carve_cliff_system,
    )

    state = _build_cliff_state()
    cliffs = carve_cliff_system(state, region=None)
    cliff = cliffs[0]
    talus = build_talus_field(cliff, state.mask_stack)
    # Non-overlap with face mask
    overlap = int((talus.mask & cliff.face_mask).sum())
    assert overlap == 0
    # Angle of repose must be ~34 degrees
    assert abs(talus.angle_of_repose_radians - math.radians(34.0)) < 1e-6


# ---------------------------------------------------------------------------
# pass_cliffs
# ---------------------------------------------------------------------------


def test_pass_cliffs_populates_cliff_candidate_channel():
    from blender_addon.handlers.terrain_cliffs import register_bundle_b_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_b_passes()
    state = _build_cliff_state()
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        result = controller.run_pass("cliffs", checkpoint=False)
    assert result.status in ("ok", "warning")
    assert state.mask_stack.cliff_candidate is not None
    assert state.mask_stack.cliff_candidate.dtype == bool
    assert result.metrics["cliff_count"] >= 1


def test_pass_cliffs_records_structure_side_effects():
    from blender_addon.handlers.terrain_cliffs import register_bundle_b_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_b_passes()
    state = _build_cliff_state()
    with tempfile.TemporaryDirectory() as td:
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        controller.run_pass("cliffs", checkpoint=False)
    effects_text = " ".join(state.side_effects)
    assert "cliff_structure:" in effects_text


def test_pass_cliffs_is_deterministic():
    from blender_addon.handlers.terrain_cliffs import register_bundle_b_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_b_passes()
    state_a = _build_cliff_state()
    state_b = _build_cliff_state()
    with tempfile.TemporaryDirectory() as td:
        ca = TerrainPassController(state_a, checkpoint_dir=Path(td))
        cb = TerrainPassController(state_b, checkpoint_dir=Path(td))
        ra = ca.run_pass("cliffs", checkpoint=False)
        rb = cb.run_pass("cliffs", checkpoint=False)
    assert ra.metrics["cliff_count"] == rb.metrics["cliff_count"]
    np.testing.assert_array_equal(
        state_a.mask_stack.cliff_candidate, state_b.mask_stack.cliff_candidate
    )


# ---------------------------------------------------------------------------
# validate_cliff_readability
# ---------------------------------------------------------------------------


def test_validate_cliff_readability_flags_small_face():
    from blender_addon.handlers.terrain_cliffs import (
        CliffStructure,
        validate_cliff_readability,
    )

    state = _build_cliff_state()
    empty_face = np.zeros_like(state.mask_stack.height, dtype=bool)
    empty_face[0, 0] = True
    cliff = CliffStructure(
        cliff_id="dummy",
        lip_polyline=np.zeros((0, 2), dtype=np.int32),
        face_mask=empty_face,
    )
    issues = validate_cliff_readability(cliff, state.mask_stack)
    codes = {i.code for i in issues}
    assert "CLIFF_FACE_TOO_SMALL" in codes
    assert "CLIFF_LIP_MISSING" in codes


def test_validate_cliff_readability_passes_for_real_cliff():
    from blender_addon.handlers.terrain_cliffs import (
        add_cliff_ledges,
        build_talus_field,
        carve_cliff_system,
        validate_cliff_readability,
    )

    state = _build_cliff_state()
    cliffs = carve_cliff_system(state, region=None)
    cliff = cliffs[0]
    add_cliff_ledges(cliff, height=state.mask_stack.height)
    build_talus_field(cliff, state.mask_stack)
    issues = validate_cliff_readability(cliff, state.mask_stack)
    hard = [i for i in issues if i.is_hard()]
    assert hard == [], f"unexpected hard issues: {hard}"


def test_hero_mesh_insertion_records_intent():
    from blender_addon.handlers.terrain_cliffs import (
        carve_cliff_system,
        insert_hero_cliff_meshes,
    )

    state = _build_cliff_state()
    cliffs = carve_cliff_system(state, region=None)
    # Mark first cliff as hero (carve_cliff_system already does this)
    intents = insert_hero_cliff_meshes(state, cliffs)
    assert len(intents) >= 1
    assert any("insert_hero_cliff_mesh" in s for s in state.side_effects)
