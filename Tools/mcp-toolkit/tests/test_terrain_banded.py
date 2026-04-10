"""Bundle G — Banded Noise Refactor tests.

Covers the acceptance criteria from docs/terrain_ultra_implementation_plan_2026-04-08.md §12.2:

1.  Each band is independently reproducible (same seed -> identical)
2.  Each band has distinct frequency content (FFT peak differs)
3.  Composite = weighted sum of bands (dimensionless, pre-vertical-scale)
4.  Changing one band weight changes composite only in that frequency range
5.  Domain warp perturbs but doesn't invalidate the composite
6.  Strata band produces near-horizontal layering
7.  Legacy generate_heightmap remains importable
8.  Banded pass registers on the TerrainPassController
9.  Banded pass height matches the composite
10. Determinism: same seed -> bit-identical composite
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gen(width=64, height=64, seed=1234, biome="dark_fantasy_default", **kw):
    from blender_addon.handlers.terrain_banded import generate_banded_heightmap

    return generate_banded_heightmap(
        width, height,
        scale=100.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        cell_size=1.0,
        seed=seed,
        biome=biome,
        **kw,
    )


def _dominant_freq(arr: np.ndarray) -> float:
    """Return the radial frequency (cycles per cell) of the FFT magnitude peak."""
    # Remove DC so the peak is not always at (0,0).
    centered = arr - arr.mean()
    spec = np.abs(np.fft.fft2(centered))
    h, w = spec.shape
    # Mask out the DC bin.
    spec[0, 0] = 0.0
    iy, ix = np.unravel_index(int(np.argmax(spec)), spec.shape)
    # Wrap frequencies into [-N/2, N/2) so low-freq and high-freq are distinguishable.
    fy = iy if iy <= h // 2 else iy - h
    fx = ix if ix <= w // 2 else ix - w
    return float(np.hypot(fy / h, fx / w))


# ---------------------------------------------------------------------------
# 1. Reproducibility per band
# ---------------------------------------------------------------------------


def test_each_band_is_reproducible_with_same_seed():
    a = _gen(seed=4242)
    b = _gen(seed=4242)
    for name in ("macro", "meso", "micro", "strata", "warp"):
        np.testing.assert_array_equal(
            a.band(name), b.band(name),
            err_msg=f"band {name} not reproducible",
        )


def test_different_seeds_produce_different_macro_bands():
    a = _gen(seed=1)
    b = _gen(seed=2)
    assert not np.array_equal(a.macro_band, b.macro_band)
    assert not np.array_equal(a.meso_band, b.meso_band)
    assert not np.array_equal(a.micro_band, b.micro_band)


# ---------------------------------------------------------------------------
# 2. Frequency separation (FFT peak differs between bands)
# ---------------------------------------------------------------------------


def test_bands_have_distinct_frequency_content():
    bands = _gen(width=128, height=128, seed=7)
    f_macro = _dominant_freq(bands.macro_band)
    f_meso  = _dominant_freq(bands.meso_band)
    f_micro = _dominant_freq(bands.micro_band)

    # Macro should be the lowest-frequency band, micro the highest.
    assert f_macro < f_micro, (
        f"macro should be lower frequency than micro; got {f_macro} vs {f_micro}"
    )
    assert f_macro <= f_meso, (
        f"macro should be <= meso frequency; got {f_macro} vs {f_meso}"
    )
    assert f_meso < f_micro, (
        f"meso should be lower frequency than micro; got {f_meso} vs {f_micro}"
    )


# ---------------------------------------------------------------------------
# 3. Composite = weighted sum of bands
# ---------------------------------------------------------------------------


def test_composite_equals_weighted_sum_of_bands():
    from blender_addon.handlers.terrain_banded import (
        BAND_WEIGHTS,
        compose_banded_heightmap,
    )

    bands = _gen(seed=99)
    weights = BAND_WEIGHTS[bands.metadata["biome"]]
    expected = compose_banded_heightmap(bands, weights) * bands.metadata["vertical_scale_m"]
    np.testing.assert_allclose(bands.composite, expected, atol=1e-10)


# ---------------------------------------------------------------------------
# 4. Changing one weight changes only that frequency range
# ---------------------------------------------------------------------------


def test_changing_micro_weight_only_perturbs_high_frequencies():
    from blender_addon.handlers.terrain_banded import compose_banded_heightmap

    bands = _gen(width=128, height=128, seed=11)
    w0 = (0.55, 0.28, 0.12, 0.05)
    w1 = (0.55, 0.28, 0.30, 0.05)  # boost micro only
    c0 = compose_banded_heightmap(bands, w0)
    c1 = compose_banded_heightmap(bands, w1)

    # The delta should be exactly (w1_micro - w0_micro) * micro_band.
    delta = c1 - c0
    expected_delta = (w1[2] - w0[2]) * bands.micro_band
    np.testing.assert_allclose(delta, expected_delta, atol=1e-12)

    # And the delta's dominant frequency should match the micro band's.
    f_delta = _dominant_freq(delta)
    f_micro = _dominant_freq(bands.micro_band)
    assert abs(f_delta - f_micro) < 1e-9


def test_changing_macro_weight_only_perturbs_low_frequencies():
    from blender_addon.handlers.terrain_banded import compose_banded_heightmap

    bands = _gen(width=128, height=128, seed=13)
    w0 = (0.55, 0.28, 0.12, 0.05)
    w1 = (0.90, 0.28, 0.12, 0.05)
    c0 = compose_banded_heightmap(bands, w0)
    c1 = compose_banded_heightmap(bands, w1)

    delta = c1 - c0
    expected_delta = (w1[0] - w0[0]) * bands.macro_band
    np.testing.assert_allclose(delta, expected_delta, atol=1e-12)


# ---------------------------------------------------------------------------
# 5. Domain warp perturbs without invalidating
# ---------------------------------------------------------------------------


def test_domain_warp_field_is_finite_and_bounded():
    bands = _gen(seed=17)
    assert np.all(np.isfinite(bands.warp_band))
    # After normalization, std should be ~1 and mean ~0 for non-degenerate inputs.
    assert abs(float(bands.warp_band.mean())) < 1e-9
    assert float(bands.warp_band.std()) > 0.0


def test_meso_band_shows_nonzero_warp_displacement():
    """The meso band applies domain warp; if warp is zero the band would
    equal plain fBm on a regular grid. We assert the meso band is NOT
    equal to a non-warped fBm sampled on the same grid — confirming the
    warp path is exercised."""
    from blender_addon.handlers.terrain_banded import _fbm_array, _coord_grids

    bands = _gen(width=64, height=64, seed=21)
    xs, ys = _coord_grids(64, 64, 0.0, 0.0, 1.0, 150.0 * 1.0)
    plain_fbm = _fbm_array(xs, ys, octaves=4, persistence=0.5, lacunarity=2.0,
                           seed=(21 + 104_729) & 0xFFFFFFFF)
    # Normalize the plain fBm the same way the band pipeline does.
    pmean = float(plain_fbm.mean())
    pstd = float(plain_fbm.std()) or 1.0
    plain_norm = (plain_fbm - pmean) / pstd
    # If warp did anything, the meso band must differ.
    assert not np.allclose(bands.meso_band, plain_norm, atol=1e-6)


# ---------------------------------------------------------------------------
# 6. Strata band is near-horizontal
# ---------------------------------------------------------------------------


def test_strata_band_variance_dominated_by_vertical_axis():
    bands = _gen(width=128, height=128, seed=31)
    strata = bands.strata_band
    # The sine is indexed by world-Y (= row axis). So walking down a
    # column traverses the sine (high variance); walking across a row
    # should barely change (low variance). axis=0 reduces across rows
    # within each column, axis=1 reduces across columns within each row.
    var_along_columns = float(strata.var(axis=0).mean())  # per-column variance (down a col)
    var_along_rows    = float(strata.var(axis=1).mean())  # per-row variance (across a row)
    assert var_along_columns > var_along_rows * 3.0, (
        f"strata should vary more along Y (down columns) than X (across rows); "
        f"var_along_columns={var_along_columns} var_along_rows={var_along_rows}"
    )


# ---------------------------------------------------------------------------
# 7. Legacy generate_heightmap still importable
# ---------------------------------------------------------------------------


def test_legacy_generate_heightmap_is_reexported():
    from blender_addon.handlers._terrain_noise import generate_heightmap as direct
    from blender_addon.handlers.terrain_banded import generate_heightmap as reexport

    assert direct is reexport
    h = direct(16, 16, scale=100.0, seed=0, terrain_type="mountains", normalize=False)
    assert h.shape == (16, 16)


# ---------------------------------------------------------------------------
# 8. Banded pass registers on the controller
# ---------------------------------------------------------------------------


def test_banded_macro_registers_on_pass_controller():
    from blender_addon.handlers.terrain_banded import register_bundle_g_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    try:
        register_bundle_g_passes()
        assert "banded_macro" in TerrainPassController.PASS_REGISTRY
        definition = TerrainPassController.PASS_REGISTRY["banded_macro"]
        assert "height" in definition.produces_channels
    finally:
        TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# 9. Banded pass height matches composite
# ---------------------------------------------------------------------------


def _build_minimal_state(tile_size=24, seed=321):
    from blender_addon.handlers._terrain_noise import generate_heightmap
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    h0 = np.asarray(
        generate_heightmap(
            tile_size + 1, tile_size + 1,
            scale=100.0, world_origin_x=0.0, world_origin_y=0.0,
            cell_size=1.0, seed=seed, terrain_type="mountains", normalize=False,
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
        height=h0,
    )
    region = BBox(0.0, 0.0, float(tile_size), float(tile_size))
    scene_read = TerrainSceneRead(
        timestamp=0.0,
        major_landforms=("ridge_system",),
        focal_point=(tile_size * 0.5, tile_size * 0.5, 0.0),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=(),
        protected_zones_in_region=(),
        edit_scope=region,
        success_criteria=("banded_macro_smoke",),
        reviewer="pytest",
    )
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region,
        tile_size=tile_size,
        cell_size=1.0,
        scene_read=scene_read,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


def test_banded_pass_writes_composite_into_stack_height():
    from blender_addon.handlers.terrain_banded import (
        generate_banded_heightmap,
        pass_banded_macro,
        register_bundle_g_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    try:
        register_bundle_g_passes()
        with tempfile.TemporaryDirectory() as td:
            state = _build_minimal_state(tile_size=24, seed=555)
            controller = TerrainPassController(state, checkpoint_dir=Path(td))
            result = controller.run_pass("banded_macro", checkpoint=False)

            assert result.status == "ok", f"pass failed: {result.issues}"
            assert "height" in result.produced_channels

            expected = generate_banded_heightmap(
                state.mask_stack.height.shape[1],
                state.mask_stack.height.shape[0],
                scale=100.0,
                world_origin_x=0.0,
                world_origin_y=0.0,
                cell_size=1.0,
                seed=555,
            )
            np.testing.assert_allclose(
                state.mask_stack.height, expected.composite, atol=1e-10
            )
    finally:
        TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# 10. Bit-identical composite determinism
# ---------------------------------------------------------------------------


def test_composite_is_bit_identical_across_runs():
    a = _gen(width=96, height=96, seed=2026)
    b = _gen(width=96, height=96, seed=2026)
    np.testing.assert_array_equal(a.composite, b.composite)
    np.testing.assert_array_equal(a.macro_band, b.macro_band)
    np.testing.assert_array_equal(a.strata_band, b.strata_band)


def test_biome_preset_changes_weights_and_composite():
    a = _gen(seed=77, biome="dark_fantasy_default")
    b = _gen(seed=77, biome="plains")
    # Bands are identical (same seed), weights differ, so composite differs.
    np.testing.assert_array_equal(a.macro_band, b.macro_band)
    assert a.metadata["weights"] != b.metadata["weights"]
    assert not np.allclose(a.composite, b.composite)
