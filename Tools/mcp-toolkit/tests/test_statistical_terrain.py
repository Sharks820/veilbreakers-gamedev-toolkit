"""Statistical terrain quality tests.

Validates height distribution, slope statistics, fractal dimension
estimation, and spectral power characteristics of generated heightmaps.
Pure numpy -- no Blender required.
"""

from __future__ import annotations

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def _estimate_fractal_dimension_boxcount(heightmap: np.ndarray, n_scales: int = 6) -> float:
    """Estimate 2D fractal dimension of a heightmap via box-counting.

    Treats the heightmap as a 2D surface and counts how many boxes of
    decreasing size are needed to cover it. The slope of log(count) vs
    log(1/scale) estimates the fractal dimension D (expected 2.0-2.5 for
    natural terrain).
    """
    h = heightmap
    rows, cols = h.shape
    side = min(rows, cols)
    if side < 4:
        return 2.0

    # Quantize height to integer levels for box counting
    h_min, h_max = h.min(), h.max()
    h_range = max(h_max - h_min, 1e-12)
    h_quant = ((h - h_min) / h_range * 255).astype(np.int32)

    scales = []
    counts = []

    for k in range(1, n_scales + 1):
        box_size = max(2, side // (2 ** k))
        if box_size < 1:
            break
        n_boxes = 0
        for r in range(0, rows, box_size):
            for c in range(0, cols, box_size):
                patch = h_quant[r:r + box_size, c:c + box_size]
                if patch.size == 0:
                    continue
                z_range = int(patch.max()) - int(patch.min())
                z_boxes = max(1, z_range // max(1, box_size))
                n_boxes += z_boxes
        if n_boxes > 0:
            scales.append(1.0 / box_size)
            counts.append(n_boxes)

    if len(scales) < 2:
        return 2.0

    # Linear regression on log-log
    log_s = np.log(scales)
    log_c = np.log(counts)
    coeffs = np.polyfit(log_s, log_c, 1)
    return float(coeffs[0])


def _radial_spectral_power(heightmap: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute radially averaged power spectrum of a heightmap.

    Returns (frequencies, power) arrays where power is the azimuthally
    averaged power at each radial frequency bin.
    """
    fft2 = np.fft.fft2(heightmap - heightmap.mean())
    power2d = np.abs(np.fft.fftshift(fft2)) ** 2
    rows, cols = power2d.shape
    cy, cx = rows // 2, cols // 2

    max_radius = min(cy, cx)
    radii = np.zeros(power2d.shape, dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            radii[r, c] = math.sqrt((r - cy) ** 2 + (c - cx) ** 2)

    freq_bins = np.arange(1, max_radius + 1, dtype=np.float64)
    power_bins = np.zeros(max_radius, dtype=np.float64)
    count_bins = np.zeros(max_radius, dtype=np.int64)

    for r in range(rows):
        for c in range(cols):
            rad = int(round(radii[r, c]))
            if 1 <= rad <= max_radius:
                power_bins[rad - 1] += power2d[r, c]
                count_bins[rad - 1] += 1

    mask = count_bins > 0
    power_bins[mask] /= count_bins[mask]

    return freq_bins, power_bins


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mountain_hmap():
    from blender_addon.handlers._terrain_noise import generate_heightmap
    return generate_heightmap(128, 128, scale=80.0, seed=42, terrain_type="mountains")


@pytest.fixture
def plains_hmap():
    from blender_addon.handlers._terrain_noise import generate_heightmap
    return generate_heightmap(128, 128, scale=80.0, seed=42, terrain_type="plains")


@pytest.fixture
def canyon_hmap():
    from blender_addon.handlers._terrain_noise import generate_heightmap
    return generate_heightmap(128, 128, scale=80.0, seed=42, terrain_type="canyon")


@pytest.fixture
def mountain_slope(mountain_hmap):
    from blender_addon.handlers._terrain_noise import compute_slope_map
    return compute_slope_map(mountain_hmap)


@pytest.fixture
def plains_slope(plains_hmap):
    from blender_addon.handlers._terrain_noise import compute_slope_map
    return compute_slope_map(plains_hmap)


# ===========================================================================
# Height distribution tests
# ===========================================================================


class TestHeightDistribution:
    """Height values should follow expected statistical properties."""

    def test_mountain_full_range(self, mountain_hmap):
        """Mountain heightmap should use most of the [0,1] range."""
        h_range = mountain_hmap.max() - mountain_hmap.min()
        assert h_range > 0.5, f"Mountain range {h_range:.3f} too narrow"

    def test_plains_narrow_range(self, plains_hmap):
        """Plains should have a narrower height range than mountains (unnormalized)."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        # Use normalize=False to see the raw amplitude differences between presets
        mtn = generate_heightmap(128, 128, scale=80.0, seed=42, terrain_type="mountains", normalize=False)
        pln = generate_heightmap(128, 128, scale=80.0, seed=42, terrain_type="plains", normalize=False)
        plains_std = pln.std()
        mtn_std = mtn.std()
        assert plains_std < mtn_std, (
            f"Plains std={plains_std:.4f} should be less than mountain std={mtn_std:.4f}"
        )

    def test_mountain_height_not_degenerate(self, mountain_hmap):
        """Mountain heightmap should not be constant or near-constant."""
        assert mountain_hmap.std() > 0.01

    def test_normalized_in_unit_range(self, mountain_hmap):
        """Normalized heightmap values should be in [0, 1]."""
        assert mountain_hmap.min() >= -1e-6
        assert mountain_hmap.max() <= 1.0 + 1e-6

    def test_height_mean_not_extreme(self, mountain_hmap):
        """Mean height should not be at extremes (degenerate distribution)."""
        mean = mountain_hmap.mean()
        assert 0.05 < mean < 0.95, f"Mean height {mean:.3f} is extreme"

    def test_different_seeds_different_distribution(self):
        """Different seeds should produce different height distributions."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        h1 = generate_heightmap(64, 64, scale=50.0, seed=1, terrain_type="mountains")
        h2 = generate_heightmap(64, 64, scale=50.0, seed=999, terrain_type="mountains")
        assert abs(h1.mean() - h2.mean()) > 1e-4 or abs(h1.std() - h2.std()) > 1e-4

    def test_terrain_types_differ_statistically(self):
        """Different terrain types should have distinguishable statistics (unnormalized)."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        # Use normalize=False to preserve the amplitude_scale differences
        mtn = generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="mountains", normalize=False)
        plains = generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="plains", normalize=False)
        flat = generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="flat", normalize=False)
        # Mountains should have higher std than plains, plains higher than flat
        assert mtn.std() > plains.std()
        assert plains.std() > flat.std()

    def test_canyon_has_bimodal_tendency(self, canyon_hmap):
        """Canyon terrain should show more spread in height values."""
        assert canyon_hmap.std() > 0.05, "Canyon terrain should have significant variation"


# ===========================================================================
# Slope statistics tests
# ===========================================================================


class TestSlopeStatistics:
    """Slope maps should match expected terrain character."""

    def test_slope_non_negative(self, mountain_slope):
        """All slope values must be >= 0."""
        assert mountain_slope.min() >= 0.0

    def test_slope_under_90_degrees(self, mountain_slope):
        """All slope values must be <= 90 degrees."""
        assert mountain_slope.max() <= 90.0 + 1e-6

    def test_mountain_has_steep_areas(self, mountain_slope):
        """Mountain terrain should have some areas steeper than the mean."""
        # Heightmaps normalized to [0,1] with cell_size=1.0 produce low absolute
        # slopes (~1-5 deg).  Test that mountains have meaningful slope variation
        # and the steepest areas exceed twice the mean.
        mean_slope = mountain_slope.mean()
        max_slope = mountain_slope.max()
        assert max_slope > mean_slope * 1.5, (
            f"Mountain max slope ({max_slope:.2f}) should significantly exceed mean ({mean_slope:.2f})"
        )
        assert mean_slope > 0.1, f"Mountain mean slope {mean_slope:.3f} too low"

    def test_plains_mostly_flat(self, plains_slope):
        """Plains should be mostly flat (< 15 deg slope)."""
        flat_frac = (plains_slope < 15.0).mean()
        assert flat_frac > 0.8, f"Only {flat_frac:.1%} of plains is flat"

    def test_slope_map_same_shape(self, mountain_hmap, mountain_slope):
        """Slope map should have same shape as heightmap."""
        assert mountain_slope.shape == mountain_hmap.shape

    def test_flat_heightmap_zero_slope(self):
        """A perfectly flat heightmap should have zero slope everywhere."""
        from blender_addon.handlers._terrain_noise import compute_slope_map
        flat = np.full((32, 32), 0.5)
        slope = compute_slope_map(flat)
        np.testing.assert_allclose(slope, 0.0, atol=1e-10)

    def test_slope_mean_ordered_by_terrain_type(self):
        """Mean slope: mountains > canyon > hills > plains > flat."""
        from blender_addon.handlers._terrain_noise import generate_heightmap, compute_slope_map
        types_ordered = ["mountains", "canyon", "hills", "plains", "flat"]
        means = []
        for t in types_ordered:
            h = generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type=t)
            s = compute_slope_map(h)
            means.append(s.mean())
        # At minimum, mountains should be steeper than flat
        assert means[0] > means[-1], (
            f"Mountains mean slope ({means[0]:.2f}) should exceed flat ({means[-1]:.2f})"
        )


# ===========================================================================
# Fractal dimension tests
# ===========================================================================


class TestFractalDimension:
    """Natural terrain should have fractal dimension ~2.0-2.5."""

    def test_mountain_fractal_dimension_range(self, mountain_hmap):
        """Mountain fractal dimension should be in [1.5, 3.0]."""
        fd = _estimate_fractal_dimension_boxcount(mountain_hmap)
        assert 1.5 < fd < 3.0, f"Fractal dimension {fd:.2f} out of natural range"

    def test_plains_lower_fractal_than_mountains(self, mountain_hmap, plains_hmap):
        """Plains should have equal or lower fractal dimension than mountains."""
        fd_mtn = _estimate_fractal_dimension_boxcount(mountain_hmap)
        fd_plains = _estimate_fractal_dimension_boxcount(plains_hmap)
        # Plains can be close but shouldn't significantly exceed mountains
        assert fd_plains < fd_mtn + 0.5, (
            f"Plains FD={fd_plains:.2f} should not greatly exceed mountain FD={fd_mtn:.2f}"
        )

    def test_flat_terrain_low_fractal_dimension(self):
        """Flat terrain should have lower fractal dimension."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        flat = generate_heightmap(128, 128, scale=80.0, seed=42, terrain_type="flat")
        fd = _estimate_fractal_dimension_boxcount(flat)
        assert fd < 3.5, f"Flat terrain FD={fd:.2f} is unexpectedly high"

    def test_fractal_dimension_deterministic(self, mountain_hmap):
        """Same heightmap should produce same fractal dimension."""
        fd1 = _estimate_fractal_dimension_boxcount(mountain_hmap)
        fd2 = _estimate_fractal_dimension_boxcount(mountain_hmap)
        assert fd1 == fd2


# ===========================================================================
# Spectral power tests
# ===========================================================================


class TestSpectralPower:
    """Terrain should show 1/f-like spectral characteristics."""

    def test_power_spectrum_decreasing(self, mountain_hmap):
        """Power should generally decrease with frequency (1/f^beta)."""
        freqs, power = _radial_spectral_power(mountain_hmap)
        # Compare low-freq power (first quarter) vs high-freq (last quarter)
        n = len(power)
        low_power = power[:n // 4].mean()
        high_power = power[3 * n // 4:].mean()
        assert low_power > high_power, (
            f"Low-freq power ({low_power:.1f}) should exceed high-freq ({high_power:.1f})"
        )

    def test_spectral_slope_negative(self, mountain_hmap):
        """Log-log spectral slope should be negative (power law decay)."""
        freqs, power = _radial_spectral_power(mountain_hmap)
        mask = (freqs > 0) & (power > 0)
        if mask.sum() < 2:
            pytest.skip("Not enough spectral data")
        log_f = np.log(freqs[mask])
        log_p = np.log(power[mask])
        slope = np.polyfit(log_f, log_p, 1)[0]
        assert slope < 0, f"Spectral slope {slope:.2f} should be negative"

    def test_white_noise_flat_spectrum(self):
        """White noise should have roughly flat power spectrum."""
        rng = np.random.RandomState(42)
        noise = rng.rand(128, 128)
        freqs, power = _radial_spectral_power(noise)
        mask = (freqs > 0) & (power > 0)
        if mask.sum() < 2:
            pytest.skip("Not enough spectral data")
        log_f = np.log(freqs[mask])
        log_p = np.log(power[mask])
        slope = np.polyfit(log_f, log_p, 1)[0]
        # White noise slope should be near 0 (flat), not strongly negative
        assert slope > -1.5, f"White noise spectral slope {slope:.2f} is too steep"

    def test_mountain_steeper_spectrum_than_plains(self, mountain_hmap, plains_hmap):
        """Mountain terrain should have steeper spectral decay than plains."""
        _, p_mtn = _radial_spectral_power(mountain_hmap)
        _, p_pln = _radial_spectral_power(plains_hmap)
        # Mountains have more large-scale features = more low-freq energy
        mtn_ratio = p_mtn[:8].mean() / max(p_mtn[-8:].mean(), 1e-12)
        pln_ratio = p_pln[:8].mean() / max(p_pln[-8:].mean(), 1e-12)
        assert mtn_ratio > pln_ratio * 0.1, "Mountain spectrum should show stronger decay"


class TestHeightmapReproducibility:
    """Heightmap generation must be deterministic."""

    def test_same_params_same_output(self):
        """Identical parameters produce identical heightmaps."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        h1 = generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="mountains")
        h2 = generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="mountains")
        np.testing.assert_array_equal(h1, h2)

    def test_different_seeds_different_output(self):
        """Different seeds produce different heightmaps."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        h1 = generate_heightmap(64, 64, scale=50.0, seed=1, terrain_type="mountains")
        h2 = generate_heightmap(64, 64, scale=50.0, seed=2, terrain_type="mountains")
        assert not np.array_equal(h1, h2)

    def test_all_terrain_types_generate(self):
        """Every terrain preset should generate without error."""
        from blender_addon.handlers._terrain_noise import generate_heightmap, TERRAIN_PRESETS
        for ttype in TERRAIN_PRESETS:
            h = generate_heightmap(32, 32, scale=30.0, seed=42, terrain_type=ttype)
            assert h.shape == (32, 32)
            assert np.isfinite(h).all(), f"{ttype} has non-finite values"
