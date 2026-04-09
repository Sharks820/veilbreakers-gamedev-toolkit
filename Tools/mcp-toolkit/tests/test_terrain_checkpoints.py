"""Bundle D — tests for terrain_checkpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_controller(tile_size=16, checkpoint_dir=None):
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        HeroFeatureSpec,
        ProtectedZoneSpec,
        TerrainAnchor,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
    )

    rng = np.random.default_rng(0)
    h = rng.normal(100.0, 5.0, (tile_size, tile_size)).astype(np.float64)
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )
    extent = float(tile_size)
    intent = TerrainIntentState(
        seed=123,
        region_bounds=BBox(0.0, 0.0, extent, extent),
        tile_size=tile_size,
        cell_size=1.0,
        anchors=(
            TerrainAnchor(
                name="anchor1",
                world_position=(1.0, 2.0, 3.0),
                anchor_kind="hero_vantage",
            ),
        ),
        protected_zones=(
            ProtectedZoneSpec(
                zone_id="z1",
                bounds=BBox(2.0, 2.0, 6.0, 6.0),
                kind="hero_mesh",
                forbidden_mutations=frozenset({"erosion"}),
            ),
        ),
        hero_feature_specs=(
            HeroFeatureSpec(
                feature_id="h1",
                feature_kind="cliff",
                world_position=(8.0, 8.0, 0.0),
                exclusion_radius=4.0,
            ),
        ),
        composition_hints={"mood": "foreboding"},
    )
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    cp_dir = Path(checkpoint_dir) if checkpoint_dir else Path(tempfile.mkdtemp())
    return TerrainPassController(state, checkpoint_dir=cp_dir), cp_dir


# ---------------------------------------------------------------------------
# save_checkpoint
# ---------------------------------------------------------------------------


def test_save_checkpoint_writes_file():
    from blender_addon.handlers.terrain_checkpoints import save_checkpoint

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        ckpt = save_checkpoint(controller, "macro_world")
        assert ckpt.mask_stack_path.exists()
        assert ckpt.checkpoint_id.startswith("macro_world_")
        assert len(controller.state.checkpoints) == 1


def test_save_checkpoint_with_label():
    from blender_addon.handlers.terrain_checkpoints import save_checkpoint

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        ckpt = save_checkpoint(controller, "macro_world", label="clean_state")
        assert ckpt.metrics.get("label") == "clean_state"


def test_save_checkpoint_populates_unity_metadata():
    from blender_addon.handlers.terrain_checkpoints import save_checkpoint

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        ckpt = save_checkpoint(controller, "macro_world")
        assert ckpt.world_bounds is not None
        assert ckpt.cell_size_m == 1.0
        assert ckpt.coordinate_system == "z-up"
        assert ckpt.tile_size == 16


# ---------------------------------------------------------------------------
# rollback_last_checkpoint
# ---------------------------------------------------------------------------


def test_rollback_last_checkpoint_restores_state():
    from blender_addon.handlers.terrain_checkpoints import (
        rollback_last_checkpoint,
        save_checkpoint,
    )

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        save_checkpoint(controller, "baseline")
        baseline_hash = controller.state.mask_stack.compute_hash()
        # Mutate
        controller.state.mask_stack.height += 100.0
        assert controller.state.mask_stack.compute_hash() != baseline_hash
        rollback_last_checkpoint(controller)
        assert controller.state.mask_stack.compute_hash() == baseline_hash


def test_rollback_last_checkpoint_raises_on_empty():
    from blender_addon.handlers.terrain_checkpoints import rollback_last_checkpoint

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        with pytest.raises(RuntimeError):
            rollback_last_checkpoint(controller)


# ---------------------------------------------------------------------------
# rollback_to
# ---------------------------------------------------------------------------


def test_rollback_to_by_id():
    from blender_addon.handlers.terrain_checkpoints import rollback_to, save_checkpoint

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        ckpt1 = save_checkpoint(controller, "p1")
        hash1 = controller.state.mask_stack.compute_hash()
        controller.state.mask_stack.height += 5.0
        save_checkpoint(controller, "p2")
        rollback_to(controller, ckpt1.checkpoint_id)
        assert controller.state.mask_stack.compute_hash() == hash1


def test_rollback_to_by_label():
    from blender_addon.handlers.terrain_checkpoints import rollback_to, save_checkpoint

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        save_checkpoint(controller, "p1", label="clean")
        hash1 = controller.state.mask_stack.compute_hash()
        controller.state.mask_stack.height += 5.0
        save_checkpoint(controller, "p2")
        rollback_to(controller, "clean")
        assert controller.state.mask_stack.compute_hash() == hash1


def test_rollback_to_unknown_raises():
    from blender_addon.handlers.terrain_checkpoints import rollback_to, save_checkpoint

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        save_checkpoint(controller, "p1")
        with pytest.raises(KeyError):
            rollback_to(controller, "nonexistent_label_or_id")


# ---------------------------------------------------------------------------
# list_checkpoints
# ---------------------------------------------------------------------------


def test_list_checkpoints_serialized_summary():
    from blender_addon.handlers.terrain_checkpoints import (
        list_checkpoints,
        save_checkpoint,
    )

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        save_checkpoint(controller, "p1", label="clean")
        save_checkpoint(controller, "p2")
        summaries = list_checkpoints(controller)
        assert len(summaries) == 2
        # JSON-serializable
        json.dumps(summaries, default=str)
        assert summaries[0]["label"] == "clean"
        assert summaries[1]["label"] is None
        assert "world_bounds" in summaries[0]


def test_list_checkpoints_empty():
    from blender_addon.handlers.terrain_checkpoints import list_checkpoints

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        assert list_checkpoints(controller) == []


# ---------------------------------------------------------------------------
# save_preset / restore_preset
# ---------------------------------------------------------------------------


def test_preset_save_and_restore_roundtrip():
    from blender_addon.handlers.terrain_checkpoints import (
        restore_preset,
        save_preset,
    )

    with tempfile.TemporaryDirectory() as td:
        preset_dir = Path(td) / "presets"
        controller, _ = _make_controller(checkpoint_dir=td)
        original_hash = controller.state.mask_stack.compute_hash()
        original_intent_hash = controller.state.intent.intent_hash()

        preset_path = save_preset(controller, "my_preset", preset_dir=preset_dir)
        assert preset_path.exists()
        assert (preset_dir / "my_preset.npz").exists()

        restored_state = restore_preset(preset_path)
        assert restored_state.mask_stack.compute_hash() == original_hash
        assert restored_state.intent.intent_hash() == original_intent_hash


def test_preset_preserves_protected_zones_and_hero_specs():
    from blender_addon.handlers.terrain_checkpoints import (
        restore_preset,
        save_preset,
    )

    with tempfile.TemporaryDirectory() as td:
        preset_dir = Path(td) / "presets"
        controller, _ = _make_controller(checkpoint_dir=td)
        preset_path = save_preset(controller, "p1", preset_dir=preset_dir)
        restored = restore_preset(preset_path)
        assert len(restored.intent.protected_zones) == 1
        assert restored.intent.protected_zones[0].zone_id == "z1"
        assert restored.intent.protected_zones[0].forbidden_mutations == frozenset(
            {"erosion"}
        )
        assert len(restored.intent.hero_feature_specs) == 1
        assert restored.intent.hero_feature_specs[0].feature_id == "h1"
        assert restored.intent.hero_feature_specs[0].feature_kind == "cliff"
        assert len(restored.intent.anchors) == 1
        assert restored.intent.anchors[0].name == "anchor1"


def test_preset_json_is_valid():
    from blender_addon.handlers.terrain_checkpoints import save_preset

    with tempfile.TemporaryDirectory() as td:
        preset_dir = Path(td) / "presets"
        controller, _ = _make_controller(checkpoint_dir=td)
        preset_path = save_preset(controller, "p1", preset_dir=preset_dir)
        with open(preset_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        assert payload["preset_name"] == "p1"
        assert "intent" in payload
        assert "content_hash" in payload


# ---------------------------------------------------------------------------
# autosave_after_pass
# ---------------------------------------------------------------------------


def test_autosave_adds_checkpoint_after_successful_pass():
    from blender_addon.handlers.terrain_checkpoints import autosave_after_pass
    from blender_addon.handlers.terrain_pipeline import (
        TerrainPassController,
        register_default_passes,
    )

    TerrainPassController.clear_registry()
    register_default_passes()
    try:
        with tempfile.TemporaryDirectory() as td:
            controller, _ = _make_controller(checkpoint_dir=td)
            autosave_after_pass(controller, enabled=True)
            before = len(controller.state.checkpoints)
            controller.run_pass("macro_world", checkpoint=False)
            after = len(controller.state.checkpoints)
            # One extra checkpoint appended via autosave wrapper
            assert after >= before + 1
            # Latest is labeled autosave_*
            assert any(
                "autosave_macro_world" in (
                    (ck.metrics or {}).get("label") or ""
                )
                for ck in controller.state.checkpoints
            )
    finally:
        TerrainPassController.clear_registry()


def test_autosave_disable_restores_original_run_pass():
    from blender_addon.handlers.terrain_checkpoints import autosave_after_pass
    from blender_addon.handlers.terrain_pipeline import (
        TerrainPassController,
        register_default_passes,
    )

    TerrainPassController.clear_registry()
    register_default_passes()
    try:
        with tempfile.TemporaryDirectory() as td:
            controller, _ = _make_controller(checkpoint_dir=td)
            original_method = controller.run_pass
            autosave_after_pass(controller, enabled=True)
            assert controller.run_pass is not original_method
            autosave_after_pass(controller, enabled=False)
            # After disable, method is restored to the original bound method
            assert controller.run_pass == original_method
    finally:
        TerrainPassController.clear_registry()


def test_autosave_idempotent_enable():
    from blender_addon.handlers.terrain_checkpoints import autosave_after_pass

    with tempfile.TemporaryDirectory() as td:
        controller, _ = _make_controller(checkpoint_dir=td)
        autosave_after_pass(controller, enabled=True)
        wrapped_once = controller.run_pass
        autosave_after_pass(controller, enabled=True)
        # Enabling twice must not double-wrap
        assert controller.run_pass is wrapped_once
        autosave_after_pass(controller, enabled=False)
