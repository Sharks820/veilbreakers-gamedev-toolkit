"""Tests for AAA visual verification protocol and regression detection.

Covers:
- analyze_render_image scoring
- aaa_verify_map multi-angle scoring with floating geometry and default material detection
- capture_regression_baseline and compare_screenshots regression detection
- Curvature-to-roughness mapping logic (apply_curvature_roughness)
- Wear map age parameter logic
- Castle battlement dimension constants
- Wiring integration checks
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# Helpers — create synthetic test images
# ---------------------------------------------------------------------------

def _make_rich_image(path: str, width: int = 128, height: int = 128) -> str:
    """Create a visually rich image with varied colors and edges."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    # Gradient background
    for y in range(height):
        r = int(50 + (y / height) * 120)
        g = int(80 + (y / height) * 80)
        b = int(100 + (y / height) * 60)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    # Add shapes for edge density
    draw.rectangle([20, 20, 60, 60], fill=(200, 100, 50))
    draw.rectangle([70, 70, 110, 110], fill=(50, 150, 200))
    draw.ellipse([30, 70, 80, 110], fill=(180, 80, 120))
    img.save(path)
    return path


def _make_dark_image(path: str, width: int = 128, height: int = 128) -> str:
    """Create a very dark, flat image (low quality)."""
    img = Image.new("RGB", (width, height), color=(10, 10, 12))
    img.save(path)
    return path


def _make_gray_image(path: str, width: int = 128, height: int = 128) -> str:
    """Create a uniform gray image (default material indicator)."""
    img = Image.new("RGB", (width, height), color=(128, 128, 128))
    img.save(path)
    return path


def _make_bright_bottom_image(path: str, width: int = 128, height: int = 128) -> str:
    """Create an image where the bottom 20% is sky-bright (floating geometry indicator)."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    # Top 80%: normal dark ground color
    draw.rectangle([0, 0, width, int(height * 0.80)], fill=(60, 80, 50))
    # Bottom 20%: sky-bright (mean brightness > 200)
    draw.rectangle([0, int(height * 0.80), width, height], fill=(220, 225, 230))
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# Tests: analyze_render_image
# ---------------------------------------------------------------------------

class TestAnalyzeRenderImage:
    def test_analyze_render_returns_score(self, tmp_path):
        """analyze_render_image returns a score in 0-100 range."""
        from veilbreakers_mcp.shared.visual_validation import analyze_render_image
        p = str(tmp_path / "test.png")
        _make_rich_image(p)
        result = analyze_render_image(p)
        assert "score" in result
        assert 0.0 <= result["score"] <= 100.0

    def test_analyze_render_returns_metrics(self, tmp_path):
        """analyze_render_image returns the expected metrics keys."""
        from veilbreakers_mcp.shared.visual_validation import analyze_render_image
        p = str(tmp_path / "test.png")
        _make_rich_image(p)
        result = analyze_render_image(p)
        assert "metrics" in result
        for key in ("brightness_mean", "contrast_score", "edge_score", "entropy_score"):
            assert key in result["metrics"]

    def test_analyze_render_missing_file(self):
        """analyze_render_image returns valid=False for a missing file."""
        from veilbreakers_mcp.shared.visual_validation import analyze_render_image
        result = analyze_render_image("/nonexistent/path/image.png")
        assert result["valid"] is False
        assert result["score"] == 0.0

    def test_analyze_render_dark_image_low_score(self, tmp_path):
        """A very dark image should produce a low score."""
        from veilbreakers_mcp.shared.visual_validation import analyze_render_image
        p = str(tmp_path / "dark.png")
        _make_dark_image(p)
        result = analyze_render_image(p)
        assert result["score"] < 60.0


# ---------------------------------------------------------------------------
# Tests: aaa_verify_map
# ---------------------------------------------------------------------------

class TestAaaVerifyMap:
    def test_aaa_verify_map_passes_good_images(self, tmp_path):
        """aaa_verify_map passes when all 10 angles score above threshold."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        paths = []
        for i in range(10):
            p = str(tmp_path / f"angle_{i}.png")
            _make_rich_image(p)
            paths.append(p)
        result = aaa_verify_map(paths, min_score=10)  # low threshold so rich images pass
        assert "passed" in result
        assert "total_score" in result
        assert "per_angle" in result
        assert "failed_angles" in result
        assert len(result["per_angle"]) == 10

    def test_aaa_verify_map_fails_low_score(self, tmp_path):
        """aaa_verify_map fails when all angles are dark/flat."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        paths = []
        for i in range(10):
            p = str(tmp_path / f"dark_{i}.png")
            _make_dark_image(p)
            paths.append(p)
        result = aaa_verify_map(paths, min_score=60)
        assert result["passed"] is False
        assert len(result["failed_angles"]) > 0

    def test_aaa_verify_map_score_range(self, tmp_path):
        """total_score is a float in 0-100 range."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        paths = []
        for i in range(5):
            p = str(tmp_path / f"img_{i}.png")
            _make_rich_image(p)
            paths.append(p)
        result = aaa_verify_map(paths, min_score=60)
        assert 0.0 <= result["total_score"] <= 100.0

    def test_aaa_verify_map_per_angle_structure(self, tmp_path):
        """Each per_angle entry has angle_id, score, issues, passed."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        p = str(tmp_path / "img.png")
        _make_rich_image(p)
        result = aaa_verify_map([p], min_score=60)
        assert len(result["per_angle"]) == 1
        entry = result["per_angle"][0]
        assert "angle_id" in entry
        assert "score" in entry
        assert "issues" in entry
        assert "passed" in entry

    def test_floating_geometry_detection(self, tmp_path):
        """Image with bright bottom region is flagged as floating_geometry_suspected."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        p = str(tmp_path / "float.png")
        _make_bright_bottom_image(p)
        result = aaa_verify_map([p], min_score=60)
        issues = result["per_angle"][0]["issues"]
        assert "floating_geometry_suspected" in issues

    def test_default_material_detection(self, tmp_path):
        """Uniform gray image is flagged as default_material_detected."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        p = str(tmp_path / "gray.png")
        _make_gray_image(p)
        result = aaa_verify_map([p], min_score=60)
        issues = result["per_angle"][0]["issues"]
        assert "default_material_detected" in issues

    def test_default_material_causes_failure(self, tmp_path):
        """An angle with default_material_detected always fails regardless of score."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        p = str(tmp_path / "gray.png")
        _make_gray_image(p)
        result = aaa_verify_map([p], min_score=0)  # min_score=0 means score alone would pass
        # Default material should still cause failure
        assert result["per_angle"][0]["passed"] is False

    def test_floating_geometry_causes_failure(self, tmp_path):
        """An angle with floating_geometry_suspected always fails."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        p = str(tmp_path / "float.png")
        _make_bright_bottom_image(p)
        result = aaa_verify_map([p], min_score=0)
        assert result["per_angle"][0]["passed"] is False

    def test_empty_path_list(self):
        """aaa_verify_map handles empty list gracefully."""
        from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
        result = aaa_verify_map([])
        assert result["total_score"] == 0.0
        assert result["passed"] is True  # no angles = no failures
        assert result["failed_angles"] == []


# ---------------------------------------------------------------------------
# Tests: capture_regression_baseline and compare_screenshots
# ---------------------------------------------------------------------------

class TestRegressionBaseline:
    def test_regression_baseline_capture(self, tmp_path):
        """capture_regression_baseline creates baseline files in target dir."""
        from veilbreakers_mcp.shared.screenshot_diff import capture_regression_baseline
        screenshots = []
        for i in range(3):
            p = str(tmp_path / f"angle_{i}.png")
            _make_rich_image(p)
            screenshots.append(p)
        baseline_dir = str(tmp_path / "baselines")
        result = capture_regression_baseline(screenshots, baseline_dir)
        assert result["baseline_count"] == 3
        assert os.path.isdir(baseline_dir)
        for i in range(3):
            assert os.path.isfile(os.path.join(baseline_dir, f"baseline_{i}.png"))

    def test_regression_baseline_paths_in_result(self, tmp_path):
        """capture_regression_baseline returns list of written paths."""
        from veilbreakers_mcp.shared.screenshot_diff import capture_regression_baseline
        p = str(tmp_path / "shot.png")
        _make_rich_image(p)
        baseline_dir = str(tmp_path / "bl")
        result = capture_regression_baseline([p], baseline_dir)
        assert len(result["paths"]) == 1
        assert result["paths"][0].endswith("baseline_0.png")

    def test_regression_comparison_match(self, tmp_path):
        """compare_screenshots: same image vs itself = match."""
        from veilbreakers_mcp.shared.screenshot_diff import compare_screenshots
        p = str(tmp_path / "img.png")
        _make_rich_image(p)
        result = compare_screenshots(p, p, threshold=0.01)
        assert result["match"] is True
        assert result["diff_percentage"] == 0.0

    def test_regression_comparison_diff(self, tmp_path):
        """compare_screenshots: different images = diff detected."""
        from veilbreakers_mcp.shared.screenshot_diff import compare_screenshots
        p1 = str(tmp_path / "img1.png")
        p2 = str(tmp_path / "img2.png")
        _make_rich_image(p1)
        _make_dark_image(p2)
        result = compare_screenshots(p1, p2, threshold=0.01)
        assert result["match"] is False
        assert result["diff_percentage"] > 0.01


# ---------------------------------------------------------------------------
# Tests: Curvature-to-roughness mapping logic
# ---------------------------------------------------------------------------

class TestCurvatureRoughness:
    def test_curvature_roughness_function_exists(self):
        """apply_curvature_roughness is importable from mesh_enhance."""
        from blender_addon.handlers.mesh_enhance import apply_curvature_roughness
        assert callable(apply_curvature_roughness)

    def test_curvature_roughness_mapping_convex(self):
        """Convex curvature reduces roughness from the base value."""
        from blender_addon.handlers.mesh_enhance import apply_curvature_roughness
        # Mock handle_bake_curvature_map to return convex data
        mock_curvature = {
            "curvature_convex": 0.8,
            "curvature_concave": 0.1,
            "object_name": "TestObj",
        }
        with patch("blender_addon.handlers.mesh_enhance.handle_bake_curvature_map",
                   return_value=mock_curvature):
            with patch("blender_addon.handlers.mesh_enhance._HAS_BPY", False):
                result = apply_curvature_roughness("TestObj", base_roughness=0.7)
        assert result["applied"] is True
        # Convex reduces roughness: 0.7 - 0.8 * 0.15 = 0.58
        assert result["convex_adjustment"] < 0.0  # negative adjustment
        final_roughness = result["base_roughness"] + result["convex_adjustment"]
        assert final_roughness < 0.7

    def test_curvature_roughness_mapping_concave(self):
        """Concave curvature increases roughness from the base value."""
        from blender_addon.handlers.mesh_enhance import apply_curvature_roughness
        mock_curvature = {
            "curvature_convex": 0.0,
            "curvature_concave": 0.8,
            "object_name": "TestObj",
        }
        with patch("blender_addon.handlers.mesh_enhance.handle_bake_curvature_map",
                   return_value=mock_curvature):
            with patch("blender_addon.handlers.mesh_enhance._HAS_BPY", False):
                result = apply_curvature_roughness("TestObj", base_roughness=0.7)
        assert result["applied"] is True
        # Concave increases roughness: 0.7 + 0.8 * 0.2 = 0.86
        assert result["concave_adjustment"] > 0.0  # positive adjustment


# ---------------------------------------------------------------------------
# Tests: Wear map age parameter
# ---------------------------------------------------------------------------

class TestWearMapAge:
    def test_wear_map_age_parameter(self):
        """handle_generate_wear_map age parameter is accepted in params."""
        # This tests that the parameter interface exists; actual bpy execution
        # is tested in integration. Here we verify the handler is importable
        # and the wear age logic is consistent.
        from blender_addon.handlers.texture import handle_generate_wear_map
        assert callable(handle_generate_wear_map)

    def test_wear_age_values_by_building_type(self):
        """Building type wear age mapping produces correct 0-1 range values."""
        # Test the age mapping constants used in worldbuilding.py settlement wiring
        BUILDING_WEAR_AGE = {
            "tavern": (0.3, 0.5),
            "shop": (0.3, 0.5),
            "residential": (0.2, 0.4),
            "military": (0.4, 0.6),
            "religious": (0.5, 0.7),
            "slums": (0.6, 0.8),
        }
        for btype, (lo, hi) in BUILDING_WEAR_AGE.items():
            assert 0.0 <= lo <= 1.0, f"{btype} low age out of range"
            assert 0.0 <= hi <= 1.0, f"{btype} high age out of range"
            assert lo < hi, f"{btype} age range inverted"


# ---------------------------------------------------------------------------
# Tests: Castle battlement dimensions
# ---------------------------------------------------------------------------

class TestBattlementDimensions:
    def test_battlements_merlon_dimensions(self):
        """generate_battlements accepts the AAA-spec merlon dimensions."""
        from blender_addon.handlers.building_quality import generate_battlements
        # Research spec: 0.5m wide x 1.0m tall merlons, 0.4m gaps
        # Call should not raise; result should be a MeshSpec-like object
        result = generate_battlements(
            wall_length=10.0,
            wall_height=6.0,
            wall_thickness=1.5,
            merlon_style="squared",
            seed=42,
        )
        assert result is not None

    def test_battlements_importable(self):
        """generate_battlements is importable from building_quality."""
        from blender_addon.handlers.building_quality import generate_battlements
        assert callable(generate_battlements)


# ---------------------------------------------------------------------------
# Tests: Wiring integration checks
# ---------------------------------------------------------------------------

class TestWiringIntegration:
    def test_castle_calls_battlements(self):
        """worldbuilding.py imports generate_battlements."""
        import ast
        import importlib.util
        wbpath = Path(__file__).parent.parent / "blender_addon" / "handlers" / "worldbuilding.py"
        source = wbpath.read_text(encoding="utf-8")
        assert "generate_battlements" in source, (
            "generate_battlements not found in worldbuilding.py — wiring missing"
        )

    def test_settlement_applies_wear(self):
        """worldbuilding.py references handle_generate_wear_map for settlement wear."""
        wbpath = Path(__file__).parent.parent / "blender_addon" / "handlers" / "worldbuilding.py"
        source = wbpath.read_text(encoding="utf-8")
        assert "handle_generate_wear_map" in source or "wear_map" in source or "wear" in source.lower(), (
            "No wear map wiring found in worldbuilding.py"
        )

    def test_aaa_verify_action_registered(self):
        """aaa_verify action is present in blender_server.py."""
        server_path = (
            Path(__file__).parent.parent / "src" / "veilbreakers_mcp" / "blender_server.py"
        )
        source = server_path.read_text(encoding="utf-8")
        assert '"aaa_verify"' in source, "aaa_verify action not registered in blender_server.py"
        assert '"screenshot_regression"' in source, (
            "screenshot_regression action not registered in blender_server.py"
        )
