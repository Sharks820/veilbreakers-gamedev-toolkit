"""Bundle I — geology plausibility tests.

Covers stratigraphy, glacial, wind erosion, coastline, karst modules and
the geology validator. Pure numpy — no Blender dependency.
"""

from __future__ import annotations

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_stack(tile_size: int = 32, heights: str = "ramp"):
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    H = W = tile_size
    if heights == "ramp":
        # Linear ramp 0..100 along Y
        h = np.tile(
            np.linspace(0.0, 100.0, H).reshape(-1, 1), (1, W)
        ).astype(np.float64)
    elif heights == "bowl":
        ys, xs = np.mgrid[0:H, 0:W]
        cy, cx = H / 2, W / 2
        d = np.sqrt((ys - cy) ** 2 + (xs - cx) ** 2)
        h = (d / d.max()) * 50.0
    elif heights == "flat":
        h = np.full((H, W), 10.0, dtype=np.float64)
    elif heights == "high":
        h = np.full((H, W), 2100.0, dtype=np.float64)
    else:
        raise ValueError(heights)

    return TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )


def _build_state(stack, *, seed: int = 42, hints=None):
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainPipelineState,
    )

    region = BBox(0.0, 0.0, float(stack.tile_size), float(stack.tile_size))
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region,
        tile_size=stack.tile_size,
        cell_size=stack.cell_size,
        composition_hints=dict(hints or {}),
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# Stratigraphy
# ---------------------------------------------------------------------------


def test_stratigraphy_layer_validates_hardness():
    from blender_addon.handlers.terrain_stratigraphy import StratigraphyLayer

    with pytest.raises(ValueError):
        StratigraphyLayer("bad", hardness=1.5, thickness_m=10.0)
    with pytest.raises(ValueError):
        StratigraphyLayer("bad", hardness=0.5, thickness_m=0.0)


def test_stratigraphy_stack_layer_for_elevation():
    from blender_addon.handlers.terrain_stratigraphy import (
        StratigraphyLayer,
        StratigraphyStack,
    )

    s = StratigraphyStack(
        base_elevation_m=0.0,
        layers=[
            StratigraphyLayer("a", 0.2, 10.0),
            StratigraphyLayer("b", 0.8, 10.0),
            StratigraphyLayer("c", 0.5, 10.0),
        ],
    )
    assert s.layer_for_elevation(-5.0).layer_id == "a"
    assert s.layer_for_elevation(5.0).layer_id == "a"
    assert s.layer_for_elevation(15.0).layer_id == "b"
    assert s.layer_for_elevation(25.0).layer_id == "c"
    assert s.layer_for_elevation(1000.0).layer_id == "c"
    assert s.total_thickness() == 30.0


def test_compute_rock_hardness_shape_and_range():
    from blender_addon.handlers.terrain_stratigraphy import (
        StratigraphyLayer,
        StratigraphyStack,
        compute_rock_hardness,
    )

    stack = _build_stack(heights="ramp")
    strat = StratigraphyStack(
        base_elevation_m=0.0,
        layers=[
            StratigraphyLayer("shale", 0.2, 30.0),
            StratigraphyLayer("sandstone", 0.6, 40.0),
            StratigraphyLayer("limestone", 0.9, 30.0),
        ],
    )
    hardness = compute_rock_hardness(stack, strat)
    assert hardness.shape == stack.height.shape
    assert hardness.dtype == np.float32
    assert hardness.min() >= 0.0
    assert hardness.max() <= 1.0
    # A ramp across 0..100 must cover all three layers
    assert len(np.unique(hardness)) == 3


def test_compute_strata_orientation_unit_vectors():
    from blender_addon.handlers.terrain_stratigraphy import (
        StratigraphyLayer,
        StratigraphyStack,
        compute_strata_orientation,
    )

    stack = _build_stack(heights="ramp")
    strat = StratigraphyStack(
        base_elevation_m=0.0,
        layers=[
            StratigraphyLayer("flat", 0.5, 50.0, dip_rad=0.0),
            StratigraphyLayer("tilted", 0.5, 100.0, dip_rad=math.pi / 6, azimuth_rad=0.0),
        ],
    )
    orient = compute_strata_orientation(stack, strat)
    assert orient.shape == (stack.height.shape[0], stack.height.shape[1], 3)
    # All unit vectors
    mags = np.sqrt((orient ** 2).sum(axis=-1))
    assert np.allclose(mags, 1.0, atol=1e-5)
    # Flat layer (lower band) produces nz ≈ 1
    assert orient[0, 0, 2] > 0.99


def test_apply_differential_erosion_softer_erodes_more():
    from blender_addon.handlers.terrain_stratigraphy import (
        StratigraphyLayer,
        StratigraphyStack,
        apply_differential_erosion,
        compute_rock_hardness,
    )

    stack = _build_stack(heights="ramp")
    strat = StratigraphyStack(
        base_elevation_m=0.0,
        layers=[
            StratigraphyLayer("soft", 0.1, 50.0),
            StratigraphyLayer("hard", 0.95, 100.0),
        ],
    )
    compute_rock_hardness(stack, strat)
    delta = apply_differential_erosion(stack)
    assert delta.shape == stack.height.shape
    # Erosion is negative (lowering)
    assert delta.min() <= 0.0
    assert delta.max() <= 1e-9
    # Soft band erodes strictly more than hard band
    assert delta[5, 5] < delta[-5, -5]


def test_pass_stratigraphy_populates_channels():
    from blender_addon.handlers.terrain_stratigraphy import pass_stratigraphy

    stack = _build_stack(heights="ramp")
    state = _build_state(stack)
    result = pass_stratigraphy(state, None)
    assert result.status == "ok"
    assert stack.rock_hardness is not None
    assert stack.strata_orientation is not None
    assert "hardness_mean" in result.metrics


# ---------------------------------------------------------------------------
# Glacial
# ---------------------------------------------------------------------------


def test_compute_snow_line_factor_ranges():
    from blender_addon.handlers.terrain_glacial import compute_snow_line

    stack_low = _build_stack(heights="ramp")  # 0..100
    factor = compute_snow_line(stack_low, snow_line_altitude_m=50.0)
    assert factor.shape == stack_low.height.shape
    assert factor.min() >= 0.0
    assert factor.max() <= 1.0
    # Low half should be zero
    assert factor[0, 0] == 0.0
    # High end should be max
    assert factor[-1, -1] > 0.9


def test_carve_u_valley_produces_depression():
    from blender_addon.handlers.terrain_glacial import carve_u_valley

    stack = _build_stack(tile_size=40, heights="flat")
    path = [(5.0, 20.0), (35.0, 20.0)]
    delta = carve_u_valley(stack, path, width_m=6.0, depth_m=5.0)
    assert delta.shape == stack.height.shape
    assert delta.min() < -4.0
    # Center of path is carved
    assert delta[20, 20] < -4.0
    # Far from path is untouched
    assert delta[0, 0] == 0.0


def test_scatter_moraines_deterministic():
    from blender_addon.handlers.terrain_glacial import scatter_moraines

    stack = _build_stack(tile_size=40, heights="flat")
    path = [(5.0, 20.0), (35.0, 20.0)]
    m1 = scatter_moraines(stack, path, seed=123)
    m2 = scatter_moraines(stack, path, seed=123)
    assert m1 == m2
    assert len(m1) >= 3


def test_pass_glacial_populates_snow_line():
    from blender_addon.handlers.terrain_glacial import pass_glacial

    stack = _build_stack(heights="ramp")
    state = _build_state(stack, hints={"snow_line_altitude_m": 50.0})
    result = pass_glacial(state, None)
    assert result.status == "ok"
    assert stack.snow_line_factor is not None
    assert "snow_coverage_fraction" in result.metrics


# ---------------------------------------------------------------------------
# Wind erosion
# ---------------------------------------------------------------------------


def test_apply_wind_erosion_changes_height():
    from blender_addon.handlers.terrain_wind_erosion import apply_wind_erosion

    stack = _build_stack(heights="bowl")
    delta = apply_wind_erosion(stack, prevailing_dir_rad=0.0, intensity=0.5)
    assert delta.shape == stack.height.shape
    assert np.abs(delta).mean() > 0.0


def test_apply_wind_erosion_intensity_zero_noop():
    from blender_addon.handlers.terrain_wind_erosion import apply_wind_erosion

    stack = _build_stack(heights="bowl")
    delta = apply_wind_erosion(stack, prevailing_dir_rad=0.0, intensity=0.0)
    assert np.allclose(delta, 0.0)


def test_apply_wind_erosion_does_not_wrap_opposite_edges():
    from blender_addon.handlers.terrain_wind_erosion import apply_wind_erosion

    stack = _build_stack(heights="flat")
    stack.height[:, 0] = 0.0
    stack.height[:, -1] = 100.0
    delta = apply_wind_erosion(stack, prevailing_dir_rad=0.0, intensity=1.0)
    assert float(np.abs(delta[:, 0]).max()) < 10.0


def test_generate_dunes_nonzero_and_deterministic():
    from blender_addon.handlers.terrain_wind_erosion import generate_dunes

    stack = _build_stack(heights="flat")
    d1 = generate_dunes(stack, wind_dir=0.0, seed=7)
    d2 = generate_dunes(stack, wind_dir=0.0, seed=7)
    assert np.array_equal(d1, d2)
    assert np.abs(d1).max() > 0.0


def test_pass_wind_erosion_runs():
    from blender_addon.handlers.terrain_wind_erosion import pass_wind_erosion

    stack = _build_stack(heights="bowl")
    state = _build_state(stack, hints={"wind_erosion_intensity": 0.2})
    h_before = stack.height.copy()
    result = pass_wind_erosion(state, None)
    assert result.status == "ok"
    # Wind erosion stores a delta channel but does NOT mutate height directly
    # (the delta integrator pass applies it later).
    assert np.array_equal(stack.height, h_before)
    delta = stack.get("wind_erosion_delta")
    assert delta is not None
    assert not np.all(delta == 0)


# ---------------------------------------------------------------------------
# Coastline
# ---------------------------------------------------------------------------


def test_compute_wave_energy_shape_and_localization():
    from blender_addon.handlers.coastline import compute_wave_energy

    stack = _build_stack(heights="ramp")  # 0..100
    energy = compute_wave_energy(
        stack, sea_level_m=5.0, dominant_wave_dir_rad=0.0
    )
    assert energy.shape == stack.height.shape
    assert energy.dtype == np.float32
    # Energy concentrated near shoreline (low band)
    assert energy[0:4, :].mean() > energy[-4:, :].mean()


def test_detect_tidal_zones_populates_tidal():
    from blender_addon.handlers.coastline import detect_tidal_zones

    stack = _build_stack(heights="ramp")
    tidal = detect_tidal_zones(stack, sea_level_m=10.0, tidal_range_m=4.0)
    assert tidal.shape == stack.height.shape
    assert stack.tidal is not None
    assert tidal.max() > 0.9
    assert tidal.min() >= 0.0


def test_apply_coastal_erosion_returns_delta():
    from blender_addon.handlers.coastline import apply_coastal_erosion

    stack = _build_stack(heights="ramp")
    delta = apply_coastal_erosion(stack, sea_level_m=10.0)
    assert delta.shape == stack.height.shape
    # Delta is non-positive (erosion)
    assert delta.max() <= 1e-9


def test_pass_coastline_populates_tidal():
    from blender_addon.handlers.coastline import pass_coastline

    stack = _build_stack(heights="ramp")
    state = _build_state(
        stack,
        hints={"sea_level_m": 20.0, "tidal_range_m": 4.0},
    )
    result = pass_coastline(state, None)
    assert result.status == "ok"
    assert stack.tidal is not None
    assert "tidal_coverage_fraction" in result.metrics


# ---------------------------------------------------------------------------
# Karst
# ---------------------------------------------------------------------------


def test_karst_feature_validates_kind():
    from blender_addon.handlers.terrain_karst import KarstFeature

    with pytest.raises(ValueError):
        KarstFeature("k1", "not_a_kind", (0, 0, 0), 1.0)
    with pytest.raises(ValueError):
        KarstFeature("k1", "sinkhole", (0, 0, 0), 0.0)


def test_detect_karst_candidates_requires_hardness():
    from blender_addon.handlers.terrain_karst import detect_karst_candidates

    stack = _build_stack(heights="bowl")
    # No hardness populated → no features
    assert detect_karst_candidates(stack) == []


def test_detect_and_carve_karst():
    from blender_addon.handlers.terrain_karst import (
        carve_karst_features,
        detect_karst_candidates,
    )
    from blender_addon.handlers.terrain_stratigraphy import (
        StratigraphyLayer,
        StratigraphyStack,
        compute_rock_hardness,
    )

    stack = _build_stack(tile_size=40, heights="bowl")
    strat = StratigraphyStack(
        base_elevation_m=0.0,
        layers=[StratigraphyLayer("limestone", 0.55, 200.0)],
    )
    compute_rock_hardness(stack, strat)
    features = detect_karst_candidates(stack, hardness_threshold=0.55)
    # Should detect at least one in the soluble band
    assert len(features) >= 1
    delta = carve_karst_features(stack, features)
    assert delta.shape == stack.height.shape
    assert delta.min() < 0.0


def test_pass_karst_runs_without_hardness():
    from blender_addon.handlers.terrain_karst import pass_karst

    stack = _build_stack(heights="bowl")
    state = _build_state(stack)
    result = pass_karst(state, None)
    assert result.status == "ok"
    assert result.metrics["feature_count"] == 0


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_validate_strata_consistency_smooth_passes():
    from blender_addon.handlers.terrain_geology_validator import (
        validate_strata_consistency,
    )
    from blender_addon.handlers.terrain_stratigraphy import (
        StratigraphyLayer,
        StratigraphyStack,
        compute_strata_orientation,
    )

    stack = _build_stack(heights="flat")
    strat = StratigraphyStack(
        base_elevation_m=0.0,
        layers=[StratigraphyLayer("flat", 0.5, 200.0, dip_rad=0.0)],
    )
    compute_strata_orientation(stack, strat)
    issues = validate_strata_consistency(stack, tol_deg=5.0)
    # All horizontal → no inconsistency
    hard = [i for i in issues if i.is_hard()]
    assert hard == []


def test_validate_strata_consistency_missing_channel():
    from blender_addon.handlers.terrain_geology_validator import (
        validate_strata_consistency,
    )

    stack = _build_stack(heights="flat")
    issues = validate_strata_consistency(stack)
    assert any(i.code == "STRATA_MISSING" for i in issues)


def test_validate_strahler_ordering_detects_jump():
    from blender_addon.handlers.terrain_geology_validator import (
        validate_strahler_ordering,
    )

    net = {
        "streams": [
            {"order": 1, "parent_order": 1},
            {"order": 2, "parent_order": 1},
            {"order": 5, "parent_order": 1},  # jump
        ]
    }
    issues = validate_strahler_ordering(net)
    assert any(i.code == "STRAHLER_JUMP" for i in issues)


def test_validate_strahler_ordering_none_safe():
    from blender_addon.handlers.terrain_geology_validator import (
        validate_strahler_ordering,
    )

    assert validate_strahler_ordering(None) == []


def test_validate_glacial_plausibility_below_treeline_fails():
    from blender_addon.handlers.terrain_geology_validator import (
        validate_glacial_plausibility,
    )

    stack = _build_stack(heights="ramp")  # 0..100
    glacier_paths = [{"path": [(5.0, 5.0), (10.0, 10.0)]}]
    issues = validate_glacial_plausibility(
        stack, glacier_paths, tree_line_altitude_m=50.0
    )
    assert any(i.code == "GLACIER_BELOW_TREELINE" for i in issues)


def test_validate_glacial_plausibility_above_treeline_passes():
    from blender_addon.handlers.terrain_geology_validator import (
        validate_glacial_plausibility,
    )

    stack = _build_stack(heights="high")  # 2100 everywhere
    glacier_paths = [{"path": [(5.0, 5.0), (10.0, 10.0)]}]
    issues = validate_glacial_plausibility(
        stack, glacier_paths, tree_line_altitude_m=1800.0
    )
    assert issues == []


def test_validate_karst_plausibility_flags_hard_rock():
    from blender_addon.handlers.terrain_geology_validator import (
        validate_karst_plausibility,
    )
    from blender_addon.handlers.terrain_karst import KarstFeature
    from blender_addon.handlers.terrain_stratigraphy import (
        StratigraphyLayer,
        StratigraphyStack,
        compute_rock_hardness,
    )

    stack = _build_stack(tile_size=16, heights="flat")
    # Granite hardness everywhere
    strat = StratigraphyStack(
        base_elevation_m=0.0,
        layers=[StratigraphyLayer("granite", 0.95, 200.0)],
    )
    compute_rock_hardness(stack, strat)
    feats = [KarstFeature("k0", "sinkhole", (5.0, 5.0, 10.0), 2.0)]
    issues = validate_karst_plausibility(stack, feats)
    assert any(i.code == "KARST_WRONG_ROCK" for i in issues)


# ---------------------------------------------------------------------------
# Bundle registrar
# ---------------------------------------------------------------------------


def test_register_bundle_i_passes_registers_all_five():
    from blender_addon.handlers.terrain_geology_validator import (
        BUNDLE_I_PASSES,
        register_bundle_i_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    # Snapshot current registry to restore after
    prior = dict(TerrainPassController.PASS_REGISTRY)
    try:
        register_bundle_i_passes()
        for name in BUNDLE_I_PASSES:
            assert name in TerrainPassController.PASS_REGISTRY, (
                f"Bundle I pass {name!r} not registered"
            )
    finally:
        TerrainPassController.PASS_REGISTRY.clear()
        TerrainPassController.PASS_REGISTRY.update(prior)


def test_bundle_i_does_not_modify_default_passes():
    """Ensure register_bundle_i_passes is independent of register_default_passes."""
    from blender_addon.handlers.terrain_geology_validator import (
        register_bundle_i_passes,
    )
    from blender_addon.handlers.terrain_pipeline import (
        TerrainPassController,
        register_default_passes,
    )

    prior = dict(TerrainPassController.PASS_REGISTRY)
    try:
        TerrainPassController.PASS_REGISTRY.clear()
        register_default_passes()
        default_names = set(TerrainPassController.PASS_REGISTRY.keys())
        register_bundle_i_passes()
        after_names = set(TerrainPassController.PASS_REGISTRY.keys())
        assert default_names.issubset(after_names)
        assert after_names - default_names == {
            "stratigraphy",
            "glacial",
            "wind_erosion",
            "coastline",
            "karst",
        }
    finally:
        TerrainPassController.PASS_REGISTRY.clear()
        TerrainPassController.PASS_REGISTRY.update(prior)
