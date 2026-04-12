"""Tests for terrain noise bug fixes F277 (gravity sign) and F805 (OpenSimplex mismatch).

These tests validate that:
1. F277: Hydraulic erosion gravity sign is correct — particles going downhill speed up
2. F805: OpenSimplex noise2 scalar matches noise2_array single-element evaluation
"""

from __future__ import annotations

import numpy as np
import pytest


class TestGravitySignBugF277:
    """F277: speed_sq = speed^2 + delta_h * gravity must use correct sign.

    Going downhill (delta_h < 0) with positive gravity should INCREASE speed.
    Going uphill (delta_h > 0) should DECREASE speed.
    """

    def test_downhill_particle_speeds_up(self):
        """A particle on a steep downhill slope should erode MORE than on flat terrain."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion as hydraulic_erosion

        # Create a tilted plane: high on left, low on right (steep gradient)
        rows, cols = 64, 64
        ys = np.linspace(0, 1, rows)
        xs = np.linspace(0, 1, cols)
        xg, _ = np.meshgrid(xs, ys)
        steep_slope = 1.0 - xg  # height decreases left to right

        # Flat terrain for comparison
        flat = np.full((rows, cols), 0.5)

        eroded_steep = hydraulic_erosion(steep_slope.copy(), iterations=2000, seed=42)
        eroded_flat = hydraulic_erosion(flat.copy(), iterations=2000, seed=42)

        # On steep terrain, particles accelerate downhill and erode more
        steep_change = np.abs(steep_slope - eroded_steep).sum()
        flat_change = np.abs(flat - eroded_flat).sum()

        # Steep slope must show MORE total erosion than flat terrain
        assert steep_change > flat_change * 1.5, (
            f"Steep terrain erosion ({steep_change:.4f}) should be significantly "
            f"more than flat terrain ({flat_change:.4f}). "
            f"Gravity sign bug may still be present (F277)."
        )

    def test_gravity_sign_speed_computation(self):
        """Verify the speed update formula uses correct sign convention.

        speed_sq = speed^2 + delta_h * gravity
        When going downhill: delta_h < 0
        With gravity > 0: delta_h * gravity < 0
        So speed_sq should be speed^2 - |delta_h| * gravity

        But physically: going downhill should INCREASE speed.
        The correct formula is: speed_sq = speed^2 - delta_h * gravity
        (note the MINUS, because delta_h is negative when going downhill,
        and -(-x) = +x, so speed increases)
        """
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion as hydraulic_erosion

        # Create a V-shaped valley — particles converge at center
        rows, cols = 64, 64
        xs = np.linspace(-1, 1, cols)
        ys = np.linspace(-1, 1, rows)
        xg, _ = np.meshgrid(xs, ys)
        valley = np.abs(xg)  # V-shape: high at edges, low at center

        eroded = hydraulic_erosion(valley.copy(), iterations=5000, seed=42)

        # The valley center (where particles converge at high speed) should
        # show visible erosion
        center_col = cols // 2
        center_strip = eroded[:, center_col - 2 : center_col + 3]
        original_strip = valley[:, center_col - 2 : center_col + 3]
        center_erosion = np.abs(original_strip - center_strip).mean()

        assert center_erosion > 0.001, (
            f"Valley center shows minimal erosion ({center_erosion:.6f}). "
            f"Gravity sign bug prevents particles from accelerating downhill (F277)."
        )


class TestOpenSimplexMismatchF805:
    """F805: noise2(x,y) must produce the same value as noise2_array([x],[y])[0]."""

    def test_scalar_matches_array_single_element(self):
        """noise2(x, y) must equal noise2_array(np.array([x]), np.array([y]))[0]."""
        from blender_addon.handlers._terrain_noise import _make_noise_generator

        gen = _make_noise_generator(seed=42)

        test_points = [
            (0.0, 0.0),
            (1.5, 2.3),
            (-0.7, 3.14),
            (100.0, -50.0),
            (0.001, 0.001),
        ]

        for x, y in test_points:
            scalar_val = gen.noise2(x, y)
            array_val = gen.noise2_array(np.array([x]), np.array([y]))[0]
            np.testing.assert_allclose(
                scalar_val,
                array_val,
                atol=1e-10,
                err_msg=(
                    f"noise2({x}, {y}) = {scalar_val} but "
                    f"noise2_array([{x}], [{y}])[0] = {array_val}. "
                    f"OpenSimplex scalar/array mismatch (F805)."
                ),
            )

    def test_batch_consistency(self):
        """Multiple points evaluated via noise2 loop must match noise2_array batch."""
        from blender_addon.handlers._terrain_noise import _make_noise_generator

        gen = _make_noise_generator(seed=123)

        xs = np.linspace(0, 10, 50)
        ys = np.linspace(0, 10, 50)

        # Scalar loop
        scalar_vals = np.array([gen.noise2(float(x), float(y)) for x, y in zip(xs, ys)])

        # Batch
        batch_vals = gen.noise2_array(xs, ys)

        np.testing.assert_allclose(
            scalar_vals,
            batch_vals,
            atol=1e-10,
            err_msg="Scalar noise2 loop does not match batch noise2_array (F805).",
        )
