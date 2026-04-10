"""Bundle D — tests for terrain_validation.

Covers all 10 validators + run_validation_suite + pass_validation_full.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_stack(tile_size=16, cell_size=1.0, seed=0):
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    rng = np.random.default_rng(seed)
    h = rng.normal(loc=100.0, scale=5.0, size=(tile_size, tile_size)).astype(np.float64)
    return TerrainMaskStack(
        tile_size=tile_size,
        cell_size=cell_size,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )


def _make_intent(stack, protected_zones=(), hero_specs=(), composition_hints=None):
    from blender_addon.handlers.terrain_semantics import BBox, TerrainIntentState

    extent = float(stack.tile_size) * float(stack.cell_size)
    return TerrainIntentState(
        seed=42,
        region_bounds=BBox(0.0, 0.0, extent, extent),
        tile_size=stack.tile_size,
        cell_size=float(stack.cell_size),
        protected_zones=tuple(protected_zones),
        hero_feature_specs=tuple(hero_specs),
        composition_hints=dict(composition_hints or {}),
    )


# ---------------------------------------------------------------------------
# 1. validate_height_finite
# ---------------------------------------------------------------------------


def test_height_finite_ok_for_clean_stack():
    from blender_addon.handlers.terrain_validation import validate_height_finite

    stack = _make_stack()
    intent = _make_intent(stack)
    assert validate_height_finite(stack, intent) == []


def test_height_finite_fails_on_nan():
    from blender_addon.handlers.terrain_validation import validate_height_finite

    stack = _make_stack()
    stack.height[2, 2] = np.nan
    intent = _make_intent(stack)
    issues = validate_height_finite(stack, intent)
    assert len(issues) == 1
    assert issues[0].code == "HEIGHT_NONFINITE"
    assert issues[0].severity == "hard"


# ---------------------------------------------------------------------------
# 2. validate_height_range
# ---------------------------------------------------------------------------


def test_height_range_ok_normal_terrain():
    from blender_addon.handlers.terrain_validation import validate_height_range

    stack = _make_stack()
    assert validate_height_range(stack, _make_intent(stack)) == []


def test_height_range_fails_on_flat_terrain():
    from blender_addon.handlers.terrain_validation import validate_height_range

    stack = _make_stack()
    stack.height[:] = 50.0
    issues = validate_height_range(stack, _make_intent(stack))
    assert any(i.code == "HEIGHT_FLAT" for i in issues)


def test_height_range_fails_on_implausible_values():
    from blender_addon.handlers.terrain_validation import validate_height_range

    stack = _make_stack()
    stack.height[0, 0] = 1e6
    issues = validate_height_range(stack, _make_intent(stack))
    assert any(i.code == "HEIGHT_IMPLAUSIBLE" for i in issues)


# ---------------------------------------------------------------------------
# 3. validate_slope_distribution
# ---------------------------------------------------------------------------


def test_slope_distribution_ok():
    from blender_addon.handlers.terrain_validation import validate_slope_distribution

    stack = _make_stack()
    stack.slope = np.random.default_rng(0).uniform(0.0, 1.0, stack.height.shape)
    issues = validate_slope_distribution(stack, _make_intent(stack))
    assert issues == []


def test_slope_distribution_fails_uniform():
    from blender_addon.handlers.terrain_validation import validate_slope_distribution

    stack = _make_stack()
    stack.slope = np.full(stack.height.shape, 0.5, dtype=np.float64)
    issues = validate_slope_distribution(stack, _make_intent(stack))
    assert any(i.code == "SLOPE_UNIFORM" for i in issues)


def test_slope_distribution_info_when_missing():
    from blender_addon.handlers.terrain_validation import validate_slope_distribution

    stack = _make_stack()
    issues = validate_slope_distribution(stack, _make_intent(stack))
    assert any(i.severity == "info" for i in issues)


# ---------------------------------------------------------------------------
# 4. validate_protected_zones_untouched
# ---------------------------------------------------------------------------


def test_protected_zones_ok_with_baseline():
    from blender_addon.handlers.terrain_semantics import BBox, ProtectedZoneSpec
    from blender_addon.handlers.terrain_validation import (
        validate_protected_zones_untouched,
    )

    stack = _make_stack(tile_size=16)
    zone = ProtectedZoneSpec("z1", BBox(2, 2, 6, 6), "hero_mesh")
    intent = _make_intent(stack, protected_zones=(zone,))
    baseline = _make_stack(tile_size=16)
    baseline.height = stack.height.copy()
    issues = validate_protected_zones_untouched(stack, intent, baseline_stack=baseline)
    assert issues == []


def test_protected_zones_hard_fail_on_mutation():
    from blender_addon.handlers.terrain_semantics import BBox, ProtectedZoneSpec
    from blender_addon.handlers.terrain_validation import (
        validate_protected_zones_untouched,
    )

    stack = _make_stack(tile_size=16)
    baseline = _make_stack(tile_size=16)
    baseline.height = stack.height.copy()
    stack.height[3, 3] += 10.0  # mutate inside zone
    zone = ProtectedZoneSpec("z1", BBox(2, 2, 6, 6), "hero_mesh")
    intent = _make_intent(stack, protected_zones=(zone,))
    issues = validate_protected_zones_untouched(stack, intent, baseline_stack=baseline)
    assert any(
        i.code == "PROTECTED_ZONE_MUTATED" and i.severity == "hard" for i in issues
    )


def test_protected_zones_info_when_no_baseline():
    from blender_addon.handlers.terrain_semantics import BBox, ProtectedZoneSpec
    from blender_addon.handlers.terrain_validation import (
        validate_protected_zones_untouched,
    )

    stack = _make_stack(tile_size=16)
    zone = ProtectedZoneSpec("z1", BBox(2, 2, 6, 6), "hero_mesh")
    intent = _make_intent(stack, protected_zones=(zone,))
    issues = validate_protected_zones_untouched(stack, intent)
    assert any(i.code == "PROTECTED_BASELINE_ABSENT" for i in issues)


# ---------------------------------------------------------------------------
# 5. validate_tile_seam_continuity
# ---------------------------------------------------------------------------


def test_seam_ok_smooth_edges():
    from blender_addon.handlers.terrain_validation import validate_tile_seam_continuity

    stack = _make_stack(tile_size=16)
    # Replace with a smooth gradient so edges are mellow
    xs = np.linspace(0, 10, 16)
    stack.height = np.broadcast_to(xs, (16, 16)).copy()
    assert validate_tile_seam_continuity(stack, _make_intent(stack)) == []


def test_seam_fails_on_nan_edge():
    from blender_addon.handlers.terrain_validation import validate_tile_seam_continuity

    stack = _make_stack(tile_size=16)
    stack.height[0, :] = np.nan
    issues = validate_tile_seam_continuity(stack, _make_intent(stack))
    assert any("SEAM_NONFINITE" in i.code for i in issues)


# ---------------------------------------------------------------------------
# 6. validate_erosion_mass_conservation
# ---------------------------------------------------------------------------


def test_mass_conservation_ok():
    from blender_addon.handlers.terrain_validation import (
        validate_erosion_mass_conservation,
    )

    stack = _make_stack()
    stack.erosion_amount = np.full(stack.height.shape, 1.0, dtype=np.float64)
    stack.deposition_amount = np.full(stack.height.shape, 1.02, dtype=np.float64)
    issues = validate_erosion_mass_conservation(stack, _make_intent(stack))
    assert issues == []


def test_mass_conservation_soft_fail_imbalance():
    from blender_addon.handlers.terrain_validation import (
        validate_erosion_mass_conservation,
    )

    stack = _make_stack()
    stack.erosion_amount = np.full(stack.height.shape, 10.0, dtype=np.float64)
    stack.deposition_amount = np.full(stack.height.shape, 1.0, dtype=np.float64)
    issues = validate_erosion_mass_conservation(stack, _make_intent(stack))
    assert any(i.code == "EROSION_MASS_IMBALANCE" for i in issues)


def test_mass_conservation_info_when_unpopulated():
    from blender_addon.handlers.terrain_validation import (
        validate_erosion_mass_conservation,
    )

    stack = _make_stack()
    issues = validate_erosion_mass_conservation(stack, _make_intent(stack))
    assert any(i.severity == "info" for i in issues)


# ---------------------------------------------------------------------------
# 7. validate_hero_feature_placement
# ---------------------------------------------------------------------------


def test_hero_feature_ok_when_mask_populated():
    from blender_addon.handlers.terrain_semantics import HeroFeatureSpec
    from blender_addon.handlers.terrain_validation import (
        validate_hero_feature_placement,
    )

    stack = _make_stack(tile_size=16)
    stack.cliff_candidate = np.zeros(stack.height.shape, dtype=np.float32)
    stack.cliff_candidate[6:10, 6:10] = 1.0
    spec = HeroFeatureSpec(
        feature_id="c1",
        feature_kind="cliff",
        world_position=(8.0, 8.0, 0.0),
        exclusion_radius=4.0,
    )
    intent = _make_intent(stack, hero_specs=(spec,))
    assert validate_hero_feature_placement(stack, intent) == []


def test_hero_feature_hard_fail_when_channel_missing():
    from blender_addon.handlers.terrain_semantics import HeroFeatureSpec
    from blender_addon.handlers.terrain_validation import (
        validate_hero_feature_placement,
    )

    stack = _make_stack(tile_size=16)
    spec = HeroFeatureSpec(
        feature_id="c1",
        feature_kind="cliff",
        world_position=(8.0, 8.0, 0.0),
        exclusion_radius=4.0,
    )
    intent = _make_intent(stack, hero_specs=(spec,))
    issues = validate_hero_feature_placement(stack, intent)
    assert any(i.code == "HERO_FEATURE_CHANNEL_MISSING" for i in issues)


def test_hero_feature_hard_fail_when_signature_missing():
    from blender_addon.handlers.terrain_semantics import HeroFeatureSpec
    from blender_addon.handlers.terrain_validation import (
        validate_hero_feature_placement,
    )

    stack = _make_stack(tile_size=16)
    stack.cliff_candidate = np.zeros(stack.height.shape, dtype=np.float32)
    spec = HeroFeatureSpec(
        feature_id="c1",
        feature_kind="cliff",
        world_position=(8.0, 8.0, 0.0),
        exclusion_radius=4.0,
    )
    intent = _make_intent(stack, hero_specs=(spec,))
    issues = validate_hero_feature_placement(stack, intent)
    assert any(i.code == "HERO_FEATURE_SIGNATURE_MISSING" for i in issues)


# ---------------------------------------------------------------------------
# 8. validate_material_coverage
# ---------------------------------------------------------------------------


def test_material_coverage_ok():
    from blender_addon.handlers.terrain_validation import validate_material_coverage

    stack = _make_stack(tile_size=16)
    weights = np.zeros((16, 16, 4), dtype=np.float32)
    weights[..., 0] = 0.3
    weights[..., 1] = 0.3
    weights[..., 2] = 0.2
    weights[..., 3] = 0.2
    stack.splatmap_weights_layer = weights
    assert validate_material_coverage(stack, _make_intent(stack)) == []


def test_material_coverage_fails_sum_mismatch():
    from blender_addon.handlers.terrain_validation import validate_material_coverage

    stack = _make_stack(tile_size=16)
    weights = np.zeros((16, 16, 3), dtype=np.float32)
    weights[..., 0] = 0.5
    # Sum = 0.5, not 1.0
    stack.splatmap_weights_layer = weights
    issues = validate_material_coverage(stack, _make_intent(stack))
    assert any(i.code == "MATERIAL_COVERAGE_GAP" for i in issues)


def test_material_coverage_soft_fail_layer_dominates():
    from blender_addon.handlers.terrain_validation import validate_material_coverage

    stack = _make_stack(tile_size=16)
    weights = np.zeros((16, 16, 2), dtype=np.float32)
    weights[..., 0] = 0.9
    weights[..., 1] = 0.1
    stack.splatmap_weights_layer = weights
    issues = validate_material_coverage(stack, _make_intent(stack))
    assert any(i.code == "MATERIAL_LAYER_DOMINATES" for i in issues)


def test_material_coverage_skipped_when_not_populated():
    from blender_addon.handlers.terrain_validation import validate_material_coverage

    stack = _make_stack(tile_size=16)
    assert validate_material_coverage(stack, _make_intent(stack)) == []


# ---------------------------------------------------------------------------
# 9. validate_channel_dtypes
# ---------------------------------------------------------------------------


def test_channel_dtypes_ok():
    from blender_addon.handlers.terrain_validation import validate_channel_dtypes

    stack = _make_stack()
    stack.slope = np.zeros(stack.height.shape, dtype=np.float32)
    assert validate_channel_dtypes(stack, _make_intent(stack)) == []


def test_channel_dtypes_accepts_semantic_mask_kinds():
    from blender_addon.handlers.terrain_validation import validate_channel_dtypes

    stack = _make_stack()
    stack.ridge = np.zeros(stack.height.shape, dtype=bool)
    stack.basin = np.zeros(stack.height.shape, dtype=np.int32)

    assert validate_channel_dtypes(stack, _make_intent(stack)) == []


def test_channel_dtypes_fails_wrong_kind():
    from blender_addon.handlers.terrain_validation import validate_channel_dtypes

    stack = _make_stack()
    # heightmap_raw_u16 must be unsigned, not float
    stack.heightmap_raw_u16 = np.zeros(stack.height.shape, dtype=np.float32)
    issues = validate_channel_dtypes(stack, _make_intent(stack))
    assert any(i.code == "CHANNEL_DTYPE_MISMATCH" for i in issues)


# ---------------------------------------------------------------------------
# 10. validate_unity_export_ready
# ---------------------------------------------------------------------------


def test_unity_export_hard_fail_when_channels_missing():
    from blender_addon.handlers.terrain_validation import validate_unity_export_ready

    stack = _make_stack()
    issues = validate_unity_export_ready(stack, _make_intent(stack))
    assert any(
        i.code == "UNITY_EXPORT_INCOMPLETE" and i.severity == "hard" for i in issues
    )


def test_unity_export_opt_out_is_info_only():
    from blender_addon.handlers.terrain_validation import validate_unity_export_ready

    stack = _make_stack()
    intent = _make_intent(stack, composition_hints={"unity_export_opt_out": True})
    issues = validate_unity_export_ready(stack, intent)
    assert all(i.severity != "hard" for i in issues)


def test_unity_export_ok_when_channels_populated():
    from blender_addon.handlers.terrain_validation import validate_unity_export_ready

    stack = _make_stack()
    shape = stack.height.shape
    stack.heightmap_raw_u16 = np.zeros(shape, dtype=np.uint16)
    stack.splatmap_weights_layer = np.zeros((*shape, 2), dtype=np.float32)
    stack.navmesh_area_id = np.zeros(shape, dtype=np.int32)
    assert validate_unity_export_ready(stack, _make_intent(stack)) == []


# ---------------------------------------------------------------------------
# run_validation_suite
# ---------------------------------------------------------------------------


def test_run_validation_suite_aggregates_issues():
    from blender_addon.handlers.terrain_validation import run_validation_suite

    stack = _make_stack()
    stack.height[0, 0] = np.nan
    report = run_validation_suite(stack, _make_intent(stack))
    assert report.overall_status == "failed"
    assert len(report.hard_issues) > 0
    assert report.metrics["hard_count"] == len(report.hard_issues)


def test_run_validation_suite_ok_when_clean():
    from blender_addon.handlers.terrain_validation import run_validation_suite

    stack = _make_stack()
    stack.slope = np.random.default_rng(0).uniform(0, 1, stack.height.shape)
    shape = stack.height.shape
    stack.heightmap_raw_u16 = np.zeros(shape, dtype=np.uint16)
    stack.splatmap_weights_layer = np.full((*shape, 2), 0.5, dtype=np.float32)
    stack.navmesh_area_id = np.zeros(shape, dtype=np.int32)
    report = run_validation_suite(stack, _make_intent(stack))
    assert report.overall_status in ("ok", "warning")
    assert len(report.hard_issues) == 0


def test_run_validation_suite_custom_validators():
    from blender_addon.handlers.terrain_validation import (
        run_validation_suite,
        validate_height_finite,
    )

    stack = _make_stack()
    report = run_validation_suite(
        stack,
        _make_intent(stack),
        validators=[("only_finite", validate_height_finite)],
    )
    assert report.overall_status == "ok"
    assert "only_finite_issue_count" in report.metrics


# ---------------------------------------------------------------------------
# pass_validation_full
# ---------------------------------------------------------------------------


@pytest.fixture
def _build_controller_with_checkpoint():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainPipelineState,
    )

    def _make(tile_size=16):
        stack = _make_stack(tile_size=tile_size)
        intent = TerrainIntentState(
            seed=42,
            region_bounds=BBox(
                0.0, 0.0, float(tile_size), float(tile_size)
            ),
            tile_size=tile_size,
            cell_size=1.0,
            composition_hints={"unity_export_opt_out": True},
        )
        state = TerrainPipelineState(intent=intent, mask_stack=stack)
        td = tempfile.mkdtemp()
        controller = TerrainPassController(state, checkpoint_dir=Path(td))
        return controller, td

    return _make


def test_pass_validation_full_returns_pass_result(_build_controller_with_checkpoint):
    from blender_addon.handlers.terrain_validation import pass_validation_full

    controller, _ = _build_controller_with_checkpoint()
    result = pass_validation_full(controller.state, None)
    assert result.pass_name == "validation_full"
    assert result.status in ("ok", "warning", "failed")


def test_pass_validation_full_triggers_rollback_on_hard_fail(
    _build_controller_with_checkpoint,
):
    from blender_addon.handlers.terrain_checkpoints import save_checkpoint
    from blender_addon.handlers.terrain_validation import (
        bind_active_controller,
        pass_validation_full,
    )

    controller, _ = _build_controller_with_checkpoint()
    # Save a clean checkpoint first
    save_checkpoint(controller, pass_name="baseline")
    clean_hash = controller.state.mask_stack.compute_hash()
    # Now corrupt the height
    controller.state.mask_stack.height[0, 0] = np.nan
    assert controller.state.mask_stack.compute_hash() != clean_hash

    bind_active_controller(controller)
    try:
        result = pass_validation_full(controller.state, None)
    finally:
        bind_active_controller(None)

    assert result.status == "failed"
    assert result.metrics.get("triggered_rollback") is True
    # After rollback, hash matches clean baseline
    assert controller.state.mask_stack.compute_hash() == clean_hash


def test_register_bundle_d_passes_adds_validation_full():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_validation import register_bundle_d_passes

    TerrainPassController.clear_registry()
    register_bundle_d_passes()
    assert "validation_full" in TerrainPassController.PASS_REGISTRY
    TerrainPassController.clear_registry()
