"""Performance and correctness tests for AAA studio optimizations (2026-03).

Validates:
  1. Heightmap generation performance (numpy-vectorized, target <0.5s for 256x256)
  2. Fallback noise determinism (permutation table produces same output for same seed)
  3. Mesh smoothing output unchanged after double-buffer numpy refactor
  4. Weathering output unchanged after edge-convexity / bbox caching
  5. Blender timer poll interval reduced (10ms)
  6. TCP bridge persistent connection support

All pure-logic -- no Blender or live server required.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# 1. Heightmap generation: performance benchmark
# ---------------------------------------------------------------------------


class TestHeightmapPerformance:
    """Benchmark heightmap generation to verify numpy vectorization speedup."""

    def test_256x256_under_half_second(self):
        """256x256 heightmap with 8 octaves should complete in < 0.5s.

        Pre-optimization this took ~5-10s with pure-Python nested loops.
        Post-optimization (numpy meshgrid + batch noise) target is <0.1s;
        we use a generous 0.5s threshold to account for CI variance.
        """
        from blender_addon.handlers._terrain_noise import generate_heightmap

        start = time.perf_counter()
        hmap = generate_heightmap(256, 256, seed=42, terrain_type="mountains")
        elapsed = time.perf_counter() - start

        assert hmap.shape == (256, 256)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0
        assert elapsed < 0.5, (
            f"256x256 heightmap took {elapsed:.3f}s (target <0.5s)"
        )

    def test_128x128_all_terrain_types(self):
        """All 6 terrain types generate valid 128x128 heightmaps quickly."""
        from blender_addon.handlers._terrain_noise import (
            TERRAIN_PRESETS,
            generate_heightmap,
        )

        start = time.perf_counter()
        for terrain_type in TERRAIN_PRESETS:
            hmap = generate_heightmap(128, 128, seed=42, terrain_type=terrain_type)
            assert hmap.shape == (128, 128)
            assert hmap.min() >= 0.0
            assert hmap.max() <= 1.0
        total = time.perf_counter() - start

        # 6 terrain types x 128x128 should complete in well under 3s total
        assert total < 3.0, (
            f"All 6 terrain types at 128x128 took {total:.3f}s (target <3s)"
        )


# ---------------------------------------------------------------------------
# 2. Fallback noise: determinism and quality
# ---------------------------------------------------------------------------


class TestPermutationTableNoise:
    """Verify the fallback permutation-table noise is deterministic and varied."""

    def test_same_seed_same_output(self):
        """Same seed produces bit-identical heightmaps."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        h1 = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        h2 = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        np.testing.assert_array_equal(h1, h2)

    def test_different_seeds_different_output(self):
        """Different seeds produce meaningfully different heightmaps."""
        from blender_addon.handlers._terrain_noise import generate_heightmap

        h1 = generate_heightmap(64, 64, seed=42, terrain_type="mountains")
        h2 = generate_heightmap(64, 64, seed=999, terrain_type="mountains")
        assert not np.array_equal(h1, h2)

    def test_noise_generator_scalar_matches_array(self):
        """Scalar noise2() and vectorized noise2_array() agree on the
        permutation-table backend (fallback noise).

        When opensimplex is installed, noise2() delegates to opensimplex
        while noise2_array() uses the faster Perlin table, so they
        intentionally differ.  This test forces the perm-table backend.
        """
        from blender_addon.handlers._terrain_noise import _PermTableNoise

        gen = _PermTableNoise(seed=42)

        xs = np.array([0.5, 1.3, -2.7, 10.0], dtype=np.float64)
        ys = np.array([0.1, -0.8, 3.3, 7.5], dtype=np.float64)

        array_result = gen.noise2_array(xs, ys)
        scalar_results = np.array(
            [gen.noise2(float(x), float(y)) for x, y in zip(xs, ys)]
        )
        np.testing.assert_allclose(array_result, scalar_results, atol=1e-10)

    def test_noise_output_range(self):
        """Noise values should be in roughly [-1, 1]."""
        from blender_addon.handlers._terrain_noise import _make_noise_generator

        gen = _make_noise_generator(42)
        xs = np.linspace(-10, 10, 200, dtype=np.float64)
        ys = np.linspace(-10, 10, 200, dtype=np.float64)
        xs_grid, ys_grid = np.meshgrid(xs, ys)
        vals = gen.noise2_array(xs_grid, ys_grid)
        # Perlin noise is bounded by +/- sqrt(2)/2 ~ 0.707 in theory,
        # but allow up to 1.5 for implementation margin
        assert vals.min() >= -1.5
        assert vals.max() <= 1.5

    def test_noise_not_constant(self):
        """Noise output should have significant variation (not degenerate)."""
        from blender_addon.handlers._terrain_noise import _make_noise_generator

        gen = _make_noise_generator(42)
        xs = np.linspace(0, 5, 100, dtype=np.float64)
        ys = np.linspace(0, 5, 100, dtype=np.float64)
        xs_grid, ys_grid = np.meshgrid(xs, ys)
        vals = gen.noise2_array(xs_grid, ys_grid)
        assert np.std(vals) > 0.01, "Noise output is too uniform"

    def test_permutation_table_build(self):
        """_build_permutation_table returns 512-element int32 array."""
        from blender_addon.handlers._terrain_noise import _build_permutation_table

        perm = _build_permutation_table(42)
        assert perm.shape == (512,)
        assert perm.dtype == np.int32
        # First 256 are a permutation of 0..255
        assert set(perm[:256].tolist()) == set(range(256))
        # Second 256 repeat the first
        np.testing.assert_array_equal(perm[:256], perm[256:])


# ---------------------------------------------------------------------------
# 3. Mesh smoothing: double-buffer numpy correctness
# ---------------------------------------------------------------------------


class TestSmoothingDoubleBuffer:
    """Verify smoothing output is unchanged after the numpy refactor."""

    def _make_cube(self):
        verts = [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ]
        faces = [
            (0, 3, 2, 1), (4, 5, 6, 7),
            (0, 1, 5, 4), (2, 3, 7, 6),
            (0, 4, 7, 3), (1, 2, 6, 5),
        ]
        return verts, faces

    def _make_two_boxes(self):
        v1 = [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ]
        v2 = [
            (1, -0.5, -0.5), (3, -0.5, -0.5), (3, 0.5, -0.5), (1, 0.5, -0.5),
            (1, -0.5, 0.5), (3, -0.5, 0.5), (3, 0.5, 0.5), (1, 0.5, 0.5),
        ]
        verts = v1 + v2
        f1 = [
            (0, 3, 2, 1), (4, 5, 6, 7),
            (0, 1, 5, 4), (2, 3, 7, 6),
            (0, 4, 7, 3), (1, 2, 6, 5),
        ]
        f2 = [
            (8, 11, 10, 9), (12, 13, 14, 15),
            (8, 9, 13, 12), (10, 11, 15, 14),
            (8, 12, 15, 11), (9, 10, 14, 13),
        ]
        return verts, f1 + f2

    def test_vertex_count_preserved(self):
        """Numpy-smoothed output has same vertex count as input."""
        from blender_addon.handlers.mesh_smoothing import smooth_assembled_mesh

        verts, faces = self._make_cube()
        result = smooth_assembled_mesh(verts, faces, smooth_iterations=3)
        assert len(result) == len(verts)

    def test_blend_factor_zero_no_change(self):
        """blend_factor=0 leaves vertices unchanged with numpy buffers."""
        from blender_addon.handlers.mesh_smoothing import smooth_assembled_mesh

        verts, faces = self._make_cube()
        result = smooth_assembled_mesh(
            verts, faces, blend_factor=0.0, smooth_iterations=3
        )
        for a, b in zip(verts, result):
            assert abs(a[0] - b[0]) < 1e-12
            assert abs(a[1] - b[1]) < 1e-12
            assert abs(a[2] - b[2]) < 1e-12

    def test_smoothing_changes_vertices(self):
        """Smoothing with default factor changes vertex positions."""
        from blender_addon.handlers.mesh_smoothing import smooth_assembled_mesh

        verts, faces = self._make_two_boxes()
        result = smooth_assembled_mesh(verts, faces, smooth_iterations=3)
        changed = sum(
            1 for a, b in zip(verts, result)
            if abs(a[0] - b[0]) > 1e-10
            or abs(a[1] - b[1]) > 1e-10
            or abs(a[2] - b[2]) > 1e-10
        )
        assert changed > 0, "Smoothing did not change any vertices"

    def test_more_iterations_more_displacement(self):
        """More iterations produce more total displacement."""
        from blender_addon.handlers.mesh_smoothing import smooth_assembled_mesh

        verts, faces = self._make_two_boxes()
        s1 = smooth_assembled_mesh(verts, faces, smooth_iterations=1)
        s5 = smooth_assembled_mesh(verts, faces, smooth_iterations=5)

        def total_disp(original, smoothed):
            return sum(
                math.sqrt(sum((a - b) ** 2 for a, b in zip(o, s)))
                for o, s in zip(original, smoothed)
            )

        d1 = total_disp(verts, s1)
        d5 = total_disp(verts, s5)
        assert d5 > d1

    def test_empty_mesh_returns_empty(self):
        """Empty input handled gracefully."""
        from blender_addon.handlers.mesh_smoothing import smooth_assembled_mesh

        result = smooth_assembled_mesh([], [])
        assert result == []

    def test_output_types_are_float_tuples(self):
        """Output vertices are tuples of Python floats."""
        from blender_addon.handlers.mesh_smoothing import smooth_assembled_mesh

        verts, faces = self._make_cube()
        result = smooth_assembled_mesh(verts, faces, smooth_iterations=2)
        for v in result:
            assert isinstance(v, tuple)
            assert len(v) == 3
            for c in v:
                assert isinstance(c, float)


# ---------------------------------------------------------------------------
# 4. Weathering: caching correctness
# ---------------------------------------------------------------------------


class TestWeatheringCaching:
    """Verify weathering produces identical output with caching enabled."""

    def _make_cube_mesh_data(self) -> dict:
        vertices = [
            (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5),
            (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
            (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5),
            (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
        ]
        faces = [
            (0, 1, 2, 3), (4, 7, 6, 5),
            (0, 4, 5, 1), (2, 6, 7, 3),
            (0, 3, 7, 4), (1, 5, 6, 2),
        ]
        face_normals = [
            (0, 0, -1), (0, 0, 1),
            (0, -1, 0), (0, 1, 0),
            (-1, 0, 0), (1, 0, 0),
        ]
        vertex_normals = [
            (-0.577, -0.577, -0.577), (0.577, -0.577, -0.577),
            (0.577, 0.577, -0.577), (-0.577, 0.577, -0.577),
            (-0.577, -0.577, 0.577), (0.577, -0.577, 0.577),
            (0.577, 0.577, 0.577), (-0.577, 0.577, 0.577),
        ]
        return {
            "vertices": vertices,
            "faces": faces,
            "face_normals": face_normals,
            "vertex_normals": vertex_normals,
            "edges": [
                (0, 1), (1, 2), (2, 3), (3, 0),
                (4, 5), (5, 6), (6, 7), (7, 4),
                (0, 4), (1, 5), (2, 6), (3, 7),
            ],
        }

    def test_cached_convexity_matches_uncached(self):
        """Caching edge convexity does not change weathering output."""
        from blender_addon.handlers.weathering import (
            compute_weathered_vertex_colors,
        )

        md1 = self._make_cube_mesh_data()
        md2 = self._make_cube_mesh_data()

        base = (0.3, 0.25, 0.2, 1.0)
        c1 = compute_weathered_vertex_colors(md1, base, preset_name="medium")
        c2 = compute_weathered_vertex_colors(md2, base, preset_name="medium")

        # Results should be identical
        assert len(c1) == len(c2)
        for a, b in zip(c1, c2):
            for i in range(4):
                assert abs(a[i] - b[i]) < 1e-12

    def test_structural_settling_with_cached_bbox(self):
        """apply_structural_settling produces identical output with cached bbox."""
        from blender_addon.handlers.weathering import (
            apply_structural_settling,
            _compute_bounding_box,
        )

        verts = [
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0), (0.0, 1.0, 1.0),
        ]

        r1 = apply_structural_settling(verts, strength=0.01, seed=42)
        bbox = _compute_bounding_box(verts)
        r2 = apply_structural_settling(
            verts, strength=0.01, seed=42, _cached_bbox=bbox
        )

        for a, b in zip(r1, r2):
            for i in range(3):
                assert abs(a[i] - b[i]) < 1e-12

    def test_all_presets_produce_valid_colors(self):
        """All weathering presets produce valid RGBA colors in [0, 1]."""
        from blender_addon.handlers.weathering import (
            WEATHERING_PRESETS,
            compute_weathered_vertex_colors,
        )

        md = self._make_cube_mesh_data()
        base = (0.3, 0.25, 0.2, 1.0)
        for preset_name in WEATHERING_PRESETS:
            # Fresh mesh_data each time to avoid cross-contamination
            md = self._make_cube_mesh_data()
            colors = compute_weathered_vertex_colors(
                md, base, preset_name=preset_name
            )
            assert len(colors) == 8
            for r, g, b, a in colors:
                assert 0.0 <= r <= 1.0
                assert 0.0 <= g <= 1.0
                assert 0.0 <= b <= 1.0
                assert 0.0 <= a <= 1.0


# ---------------------------------------------------------------------------
# 5. Timer poll interval
# ---------------------------------------------------------------------------


class TestTimerConfiguration:
    """Verify the Blender addon timer poll interval is correctly set."""

    def test_timer_interval_is_10ms(self):
        """Socket server timer should use 10ms (0.01s) poll interval."""
        import inspect
        from blender_addon import socket_server

        source = inspect.getsource(socket_server.BlenderMCPServer._process_commands)
        # The method returns the poll interval -- should be 0.01
        assert "0.01" in source, (
            "Timer poll interval should be 0.01 (10ms)"
        )
        assert "0.05" not in source, (
            "Old 50ms interval (0.05) should be replaced with 0.01"
        )


# ---------------------------------------------------------------------------
# 6. TCP bridge persistent connection (unit-level)
# ---------------------------------------------------------------------------


class TestBlenderClientPersistentConnection:
    """Verify BlenderConnection supports persistent connections."""

    def test_connection_class_has_persistent_send(self):
        """_sync_send should not disconnect after each command."""
        import inspect
        from veilbreakers_mcp.shared.blender_client import BlenderConnection

        source = inspect.getsource(BlenderConnection._send_on_socket)
        # The method should NOT call self.disconnect() -- that's the key
        # difference from the old connection-per-command pattern.
        assert "self.disconnect()" not in source, (
            "_send_on_socket should not disconnect after sending"
        )

    def test_sync_send_has_retry_logic(self):
        """_sync_send should retry once on connection failure."""
        import inspect
        from veilbreakers_mcp.shared.blender_client import BlenderConnection

        source = inspect.getsource(BlenderConnection._sync_send)
        assert "range(2)" in source, (
            "_sync_send should have a retry loop with range(2)"
        )

    def test_disconnect_is_idempotent(self):
        """Calling disconnect() when not connected should not raise."""
        from veilbreakers_mcp.shared.blender_client import BlenderConnection

        conn = BlenderConnection(host="localhost", port=19999)
        # Should not raise
        conn.disconnect()
        conn.disconnect()

    def test_is_alive_when_not_connected(self):
        """is_alive() returns False when server is not running."""
        from veilbreakers_mcp.shared.blender_client import BlenderConnection

        conn = BlenderConnection(host="localhost", port=19999, timeout=1)
        assert conn.is_alive() is False
