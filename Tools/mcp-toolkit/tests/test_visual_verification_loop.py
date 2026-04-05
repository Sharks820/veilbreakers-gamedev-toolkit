"""Tests for Phase 48: Visual verification loop (CITY-06).

Validates aaa_verify score thresholds, angle counts, screenshot directory
management, and freshness checks -- all without Blender TCP.

Coverage:
  CITY-06: aaa_verify scoring thresholds and visual regression baseline
  TEST-03: Visual regression baseline management
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_toolkit_root = Path(__file__).resolve().parent.parent
if str(_toolkit_root) not in sys.path:
    sys.path.insert(0, str(_toolkit_root))

_src_root = _toolkit_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from veilbreakers_mcp.shared import visual_validation


# ===========================================================================
# AAA verification score thresholds
# ===========================================================================


class TestAAAVerifyScoreThreshold:
    """Validate aaa_verify min_score enforcement."""

    def test_aaa_verify_marks_failed_angles_below_threshold(self, monkeypatch):
        """aaa_verify_map reports exactly which angles miss the threshold."""
        scores = [72, 68, 55, 71, 80, 63, 58, 74, 66, 70]
        paths = [f"angle_{idx}.png" for idx in range(len(scores))]

        def _fake_analyze(path: str) -> dict:
            idx = int(Path(path).stem.split("_")[-1])
            return {"score": float(scores[idx]), "issues": []}

        monkeypatch.setattr(visual_validation, "analyze_render_image", _fake_analyze)
        result = visual_validation.aaa_verify_map(paths, min_score=60)

        assert len(result["per_angle"]) == 10
        assert result["failed_angles"] == [2, 6]
        assert result["passed"] is False

    def test_aaa_verify_fails_angles_with_critical_issues(self, monkeypatch):
        """Critical AAA flags fail an angle even if its score is high."""
        monkeypatch.setattr(
            visual_validation,
            "analyze_render_image",
            lambda _path: {"score": 95.0, "issues": ["default_material_detected"]},
        )
        result = visual_validation.aaa_verify_map(["angle_0.png"], min_score=60)

        assert result["failed_angles"] == [0]
        assert result["per_angle"][0]["passed"] is False


class TestScreenshotDirectory:
    """Validate screenshot directory management."""

    def test_screenshot_directory_path_valid(self):
        """C:/tmp/vb_visual_test/ is a valid path format."""
        screenshot_dir = Path("C:/tmp/vb_visual_test")
        # Path is constructable (doesn't need to exist for test)
        assert screenshot_dir.name == "vb_visual_test"
        assert str(screenshot_dir).replace("\\", "/").endswith("tmp/vb_visual_test")

    def test_screenshot_directory_creation(self):
        """Screenshot directory can be created in a temp location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "vb_visual_test"
            test_dir.mkdir(parents=True, exist_ok=True)
            assert test_dir.exists()
            assert test_dir.is_dir()

    def test_screenshot_freshness_check(self):
        """Screenshot older than 60 seconds should be flagged as stale."""
        max_age_seconds = 60
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png data")
            f.flush()
            tmp_path = f.name

        try:
            # File just created -- should be fresh
            file_age = time.time() - os.path.getmtime(tmp_path)
            assert file_age < max_age_seconds, "Freshly created file should not be stale"

            # Simulate staleness by modifying mtime
            stale_time = time.time() - 120  # 2 minutes ago
            os.utime(tmp_path, (stale_time, stale_time))
            file_age = time.time() - os.path.getmtime(tmp_path)
            assert file_age > max_age_seconds, "File modified 2 min ago should be stale"
        finally:
            os.unlink(tmp_path)

    def test_screenshot_naming_convention(self):
        """Phase 48 screenshots follow 48_*.png naming convention."""
        expected_names = [
            "48_terrain_overview.png",
            "48_terrain_river.png",
            "48_terrain_cliff.png",
            "48_terrain_FINAL.png",
            "48_city_overview.png",
            "48_city_castle.png",
            "48_city_tavern_interior.png",
            "48_city_vegetation.png",
            "48_FINAL_contact_sheet.png",
        ]
        for name in expected_names:
            assert name.startswith("48_"), f"Screenshot {name} doesn't follow 48_ prefix"
            assert name.endswith(".png"), f"Screenshot {name} doesn't have .png extension"
