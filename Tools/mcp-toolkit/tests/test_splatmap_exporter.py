"""Tests for splatmap_exporter module.

Pure-logic tests only -- no bpy required.
"""

from __future__ import annotations

import os

import pytest

from blender_addon.handlers.splatmap_exporter import (
    export_splatmap_to_png,
    rasterize_splatmap,
)


def _make_grid(rows: int, cols: int, color: tuple[float, float, float, float] = (0.5, 0.2, 0.2, 0.1)):
    """Create a uniform grid of vertex colors."""
    return [color] * (rows * cols)


class TestSplatmapExporter:
    """Tests for pure-logic splatmap rasterization."""

    def test_rasterize_grid_to_image(self):
        """4x4 grid produces correct-size output at 512x512."""
        colors = _make_grid(4, 4, (0.6, 0.2, 0.1, 0.1))
        raw = rasterize_splatmap(colors, 4, 4, target_resolution=512)
        # 512*512 pixels * 4 bytes (RGBA)
        assert len(raw) == 512 * 512 * 4

    def test_channel_convention(self):
        """R=grass dominant pixel has high R channel value."""
        # All grass: R=1.0, G=0, B=0, A=0
        colors = _make_grid(2, 2, (1.0, 0.0, 0.0, 0.0))
        raw = rasterize_splatmap(colors, 2, 2, target_resolution=4)
        # Check first pixel: R should be 255 (after normalization, R=1.0 -> R=255)
        r, g, b, a = raw[0], raw[1], raw[2], raw[3]
        assert r == 255, f"R channel should be 255 for all-grass, got {r}"
        assert g == 0
        assert b == 0
        assert a == 0

    def test_resolution_parameter(self):
        """Output image dimensions match target_resolution parameter."""
        colors = _make_grid(4, 4)
        for res in [64, 128, 256]:
            raw = rasterize_splatmap(colors, 4, 4, target_resolution=res)
            assert len(raw) == res * res * 4

    def test_normalization(self):
        """Output pixel values sum to ~255 per pixel (normalized weights)."""
        colors = _make_grid(2, 2, (0.3, 0.3, 0.2, 0.2))
        raw = rasterize_splatmap(colors, 2, 2, target_resolution=4)
        # Check first pixel sums approximately to 255
        for pixel_start in range(0, len(raw), 4):
            r, g, b, a = raw[pixel_start:pixel_start + 4]
            total = r + g + b + a
            # Allow some rounding tolerance
            assert 250 <= total <= 260, f"Pixel channels sum to {total}, expected ~255"

    def test_irregular_vertex_count_handling(self):
        """Mismatched vertex count raises ValueError."""
        colors = [(0.5, 0.2, 0.2, 0.1)] * 10  # 10 != 4*4
        with pytest.raises(ValueError, match="doesn't match"):
            rasterize_splatmap(colors, 4, 4)

    def test_output_path_written(self, tmp_path):
        """PNG file is written to specified output_path."""
        colors = _make_grid(4, 4)
        out = str(tmp_path / "test_splatmap.png")
        result = export_splatmap_to_png(colors, 4, 4, out, target_resolution=32)
        assert result == out
        assert os.path.isfile(out)
        # Check it's a valid PNG (starts with PNG signature)
        with open(out, "rb") as f:
            header = f.read(8)
        assert header[:4] == b"\x89PNG", "Output should be a valid PNG file"

    def test_small_grid_export(self, tmp_path):
        """2x2 grid exports successfully."""
        colors = _make_grid(2, 2, (0.25, 0.25, 0.25, 0.25))
        out = str(tmp_path / "small.png")
        export_splatmap_to_png(colors, 2, 2, out, target_resolution=16)
        assert os.path.isfile(out)
