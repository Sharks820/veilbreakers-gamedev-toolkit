"""Bundle A smoke tests for the terrain pass pipeline.

Covers the acceptance criteria from docs/terrain_ultra_implementation_plan_2026-04-08.md §6.5:

1.  End-to-end pipeline runs
2.  Mask stack channels populated
3.  Determinism (bit-identical re-run with same seed)
4.  Region scoping (only cells inside region change)
5.  Protected zones honored (forbidden cells untouched)
6.  Scene-read enforcement (SceneReadRequired raised)
7.  Checkpoint create / rollback
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _register_passes():
    """Ensure the default Bundle A passes are registered before each test."""
    from blender_addon.handlers.terrain_pipeline import (
        TerrainPassController,
        register_default_passes,
    )

    TerrainPassController.clear_registry()
    register_default_passes()
    yield
    TerrainPassController.clear_registry()


def _build_state(
    *,
    tile_size: int = 32,
    seed: int = 1234,
    include_scene_read: bool = True,
    protected_zones=(),
):
    from blender_addon.handlers._terrain_noise import generate_heightmap
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    height = np.asarray(
        generate_heightmap(
            tile_size + 1,
            tile_size + 1,
            scale=100.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            cell_size=1.0,
            seed=seed,
            terrain_type="mountains",
            normalize=False,
        ),
        dtype=np.float64,
    )
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    region_bounds = BBox(0.0, 0.0, float(tile_size), float(tile_size))

    scene_read = None
    if include_scene_read:
        scene_read = TerrainSceneRead(
            timestamp=0.0,
            major_landforms=("ridge_system",),
            focal_point=(float(tile_size) * 0.5, float(tile_size) * 0.5, 0.0),
            hero_features_present=(),
            hero_features_missing=(),
            waterfall_chains=(),
            cave_candidates=(),
            protected_zones_in_region=tuple(z.zone_id for z in protected_zones),
            edit_scope=region_bounds,
            success_criteria=("smoke_test",),
            reviewer="pytest",
        )

    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
        protected_zones=tuple(protected_zones),
        scene_read=scene_read,
    )

    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# 1. End-to-end pipeline runs
# ---------------------------------------------------------------------------


def test_pipeline_end_to_end_runs_all_four_passes():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        results = controller.run_pipeline()

    assert len(results) == 4
    for r in results:
        assert r.status == "ok", f"pass {r.pass_name} failed: {r.issues}"


# ---------------------------------------------------------------------------
# 2. Mask stack channels populated after each pass
# ---------------------------------------------------------------------------


def test_mask_stack_channels_populated_after_each_pass():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))

        controller.run_pass("macro_world", checkpoint=False)
        assert state.mask_stack.height is not None

        controller.run_pass("structural_masks", checkpoint=False)
        stack = state.mask_stack
        for ch in ("slope", "curvature", "concavity", "convexity", "ridge", "basin", "saliency_macro"):
            val = stack.get(ch)
            assert val is not None, f"channel {ch} missing"
            assert val.shape == stack.height.shape, f"{ch} shape mismatch"

        controller.run_pass("erosion", checkpoint=False)
        for ch in ("erosion_amount", "deposition_amount", "wetness", "drainage", "bank_instability", "talus"):
            val = stack.get(ch)
            assert val is not None, f"erosion channel {ch} missing"
            assert val.shape == stack.height.shape


# ---------------------------------------------------------------------------
# 3. Determinism — identical hashes for identical seeds
# ---------------------------------------------------------------------------


def test_pipeline_determinism_bit_identical_reruns():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with tempfile.TemporaryDirectory() as td:
        state_a = _build_state(tile_size=24, seed=9001)
        controller_a = TerrainPassController(state_a, checkpoint_dir=Path(td) / "a")
        controller_a.run_pipeline()
        hash_a = state_a.mask_stack.compute_hash()

        state_b = _build_state(tile_size=24, seed=9001)
        controller_b = TerrainPassController(state_b, checkpoint_dir=Path(td) / "b")
        controller_b.run_pipeline()
        hash_b = state_b.mask_stack.compute_hash()

    assert hash_a == hash_b, "content hash differs across identical re-runs"
    np.testing.assert_array_equal(state_a.mask_stack.height, state_b.mask_stack.height)
    np.testing.assert_array_equal(
        state_a.mask_stack.erosion_amount, state_b.mask_stack.erosion_amount
    )


# ---------------------------------------------------------------------------
# 4. Region scoping — cells outside region unchanged
# ---------------------------------------------------------------------------


def test_region_scoping_leaves_outside_cells_unchanged():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import BBox

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=32)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))

        # First populate the prerequisite channels
        controller.run_pass("macro_world", checkpoint=False)
        controller.run_pass("structural_masks", checkpoint=False)

        h_before = state.mask_stack.height.copy()

        # Scope erosion to the center 10x10 region in world coords
        region = BBox(10.0, 10.0, 20.0, 20.0)
        controller.run_pass("erosion", region=region, checkpoint=False)
        h_after = state.mask_stack.height

        # Cells at (0,0) should be unchanged
        np.testing.assert_array_equal(h_before[0:3, 0:3], h_after[0:3, 0:3])


# ---------------------------------------------------------------------------
# 5. Protected zones honored
# ---------------------------------------------------------------------------


def test_protected_zone_cells_are_not_mutated_by_erosion():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import BBox, ProtectedZoneSpec

    zone = ProtectedZoneSpec(
        zone_id="hero_cliff",
        bounds=BBox(5.0, 5.0, 15.0, 15.0),
        kind="hero_mesh",
        forbidden_mutations=frozenset({"erosion"}),
    )

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=32, protected_zones=(zone,))
        controller = TerrainPassController(state, checkpoint_dir=Path(td))

        controller.run_pass("macro_world", checkpoint=False)
        controller.run_pass("structural_masks", checkpoint=False)

        h_before = state.mask_stack.height.copy()
        controller.run_pass("erosion", checkpoint=False)
        h_after = state.mask_stack.height

        # Inner part of the protected zone (cells 6..14 inclusive) must match.
        np.testing.assert_array_equal(h_before[7:14, 7:14], h_after[7:14, 7:14])


# ---------------------------------------------------------------------------
# 6. Scene-read enforcement
# ---------------------------------------------------------------------------


def test_erosion_pass_requires_scene_read():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import SceneReadRequired

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=24, include_scene_read=False)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))

        controller.run_pass("macro_world", checkpoint=False)
        controller.run_pass("structural_masks", checkpoint=False)

        with pytest.raises(SceneReadRequired):
            controller.run_pass("erosion", checkpoint=False)


# ---------------------------------------------------------------------------
# 7. Checkpoint create / rollback
# ---------------------------------------------------------------------------


def test_checkpoint_rollback_restores_prior_state():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=24)
        controller = TerrainPassController(state, checkpoint_dir=Path(td))

        r1 = controller.run_pass("macro_world", checkpoint=True)
        r2 = controller.run_pass("structural_masks", checkpoint=True)

        hash_after_pass2 = state.mask_stack.compute_hash()
        assert r1.checkpoint_path is not None
        assert r2.checkpoint_path is not None
        assert len(state.checkpoints) == 2

        # Now mutate with erosion
        controller.run_pass("erosion", checkpoint=True)
        assert state.mask_stack.compute_hash() != hash_after_pass2

        # Rollback to pass2
        controller.rollback_to(state.checkpoints[1].checkpoint_id)

        # Height should match the pass2 snapshot (structural_masks does not
        # modify height, so it equals pass1 height too)
        assert len(state.checkpoints) == 2
        assert state.mask_stack.compute_hash() == hash_after_pass2


# ---------------------------------------------------------------------------
# Extra: derive_pass_seed determinism
# ---------------------------------------------------------------------------


def test_derive_pass_seed_is_deterministic_and_varies_by_inputs():
    from blender_addon.handlers.terrain_pipeline import derive_pass_seed

    a = derive_pass_seed(42, "erosion", 0, 0, None)
    b = derive_pass_seed(42, "erosion", 0, 0, None)
    c = derive_pass_seed(42, "erosion", 1, 0, None)
    d = derive_pass_seed(42, "macro_world", 0, 0, None)
    e = derive_pass_seed(43, "erosion", 0, 0, None)

    assert a == b
    assert a != c
    assert a != d
    assert a != e
    assert all(0 <= x < (1 << 32) for x in (a, b, c, d, e))
