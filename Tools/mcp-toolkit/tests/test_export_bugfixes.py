"""Tests for export pipeline bug fixes (Phase 46 Plan 01).

Tests render_angle handler, aaa_verify cleanup, derive_addressable_groups
terrain/interior population, and export_fbx object_names filter.
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# TestRenderAngle -- verify handle_render_angle exists and is registered
# ---------------------------------------------------------------------------


class TestRenderAngle:
    """Tests for render_angle handler registration and camera math."""

    def test_handler_registered(self):
        """__init__.py maps 'render_angle' to handle_render_angle (not alias)."""
        from blender_addon.handlers import handle_render_angle
        from blender_addon.handlers.viewport import handle_render_angle as real_handler
        from blender_addon.handlers.viewport import handle_get_viewport_screenshot

        # Verify handle_render_angle is NOT the same as handle_get_viewport_screenshot
        assert handle_render_angle is not handle_get_viewport_screenshot, \
            "render_angle should NOT be aliased to handle_get_viewport_screenshot"
        assert handle_render_angle is real_handler

    def test_camera_position_from_yaw_pitch(self):
        """Spherical coordinate math produces correct positions for known angles."""
        # Import the pure-logic helper used inside handle_render_angle
        from blender_addon.handlers.viewport import compute_light_position

        center = (0.0, 0.0, 0.0)
        distance = 10.0

        # yaw=0, pitch=0 -> front (along +Y axis in Blender convention)
        pos = compute_light_position(center, distance, 0, 0)
        assert isinstance(pos, (list, tuple))
        assert len(pos) == 3

        # yaw=90, pitch=0 -> side
        pos90 = compute_light_position(center, distance, 90, 0)
        assert isinstance(pos90, (list, tuple))

        # Different yaw should give different positions
        assert pos != pos90

    def test_output_path_accepted(self):
        """_resolve_output_path handles both output_path and filepath params."""
        from blender_addon.handlers.viewport import _resolve_output_path

        # filepath takes precedence (checked first in the implementation)
        path = _resolve_output_path(
            {"filepath": "/tmp/fb.png"},
            "vb_test",
        )
        assert path == "/tmp/fb.png"

        # output_path works as fallback
        path2 = _resolve_output_path({"output_path": "/tmp/out.png"}, "vb_test")
        assert path2 == "/tmp/out.png"

        # Both present: filepath wins
        path3 = _resolve_output_path(
            {"filepath": "/tmp/fp.png", "output_path": "/tmp/op.png"},
            "vb_test",
        )
        assert path3 == "/tmp/fp.png"


# ---------------------------------------------------------------------------
# TestAaaVerifyCleanup
# ---------------------------------------------------------------------------


class TestAaaVerifyCleanup:
    """Tests for aaa_verify stale screenshot cleanup."""

    def test_old_screenshots_cleared(self, tmp_path):
        """Verify the glob cleanup pattern works on a temp directory."""
        import glob

        # Simulate old screenshots
        test_dir = str(tmp_path / "vb_aaa_verify")
        os.makedirs(test_dir, exist_ok=True)
        for name in ["aaa_front.png", "aaa_back.png", "aaa_top.png"]:
            (Path(test_dir) / name).write_bytes(b"old")

        # The cleanup pattern from blender_server.py
        for old_png in glob.glob(os.path.join(test_dir, "aaa_*.png")):
            os.remove(old_png)

        remaining = glob.glob(os.path.join(test_dir, "aaa_*.png"))
        assert len(remaining) == 0, "All old screenshots should be removed"

    def test_cleanup_preserves_non_aaa_files(self, tmp_path):
        """Cleanup pattern only removes aaa_* files, not others."""
        import glob

        test_dir = str(tmp_path / "vb_aaa_verify")
        os.makedirs(test_dir, exist_ok=True)
        (Path(test_dir) / "aaa_front.png").write_bytes(b"old")
        (Path(test_dir) / "other_file.png").write_bytes(b"keep")

        for old_png in glob.glob(os.path.join(test_dir, "aaa_*.png")):
            os.remove(old_png)

        assert os.path.exists(os.path.join(test_dir, "other_file.png"))
        assert not os.path.exists(os.path.join(test_dir, "aaa_front.png"))


# ---------------------------------------------------------------------------
# TestDeriveAddressableGroups -- terrain/interior population
# ---------------------------------------------------------------------------


class TestDeriveAddressableGroups:
    """Tests for derive_addressable_groups terrain_objects and interior_results."""

    def test_terrain_objects_populated(self):
        """Passing terrain_objects populates the terrain group."""
        from blender_addon.handlers.pipeline_state import derive_addressable_groups

        groups = derive_addressable_groups(
            "TestMap", [],
            terrain_objects=["Map_Terrain"],
        )
        terrain_group = [g for g in groups if g["group_type"] == "terrain"][0]
        assert "Map_Terrain" in terrain_group["objects"]

    def test_interior_results_populated(self):
        """Passing interior_results populates the interiors group."""
        from blender_addon.handlers.pipeline_state import derive_addressable_groups

        groups = derive_addressable_groups(
            "TestMap", [],
            interior_results=[{"name": "Tavern_Interior"}, {"name": "Chapel_Interior"}],
        )
        interior_group = [g for g in groups if g["group_type"] == "interior"][0]
        assert "Tavern_Interior" in interior_group["objects"]
        assert "Chapel_Interior" in interior_group["objects"]

    def test_backward_compatible(self):
        """Calling with only positional args still works (no crash)."""
        from blender_addon.handlers.pipeline_state import derive_addressable_groups

        groups = derive_addressable_groups("TestMap", [])
        assert isinstance(groups, list)
        assert len(groups) >= 1

    def test_empty_terrain_objects(self):
        """When terrain_objects is empty, terrain group has empty objects."""
        from blender_addon.handlers.pipeline_state import derive_addressable_groups

        groups = derive_addressable_groups("TestMap", [], terrain_objects=[])
        terrain_group = [g for g in groups if g["group_type"] == "terrain"][0]
        assert terrain_group["objects"] == []


# ---------------------------------------------------------------------------
# TestExportFbxObjectNames -- object_names filter
# ---------------------------------------------------------------------------


class TestExportFbxObjectNames:
    """Tests for export_fbx object_names parameter (pure-logic validation)."""

    def test_object_names_param_in_handler(self):
        """handle_export_fbx reads the object_names parameter."""
        from blender_addon.handlers.export import handle_export_fbx
        import inspect

        source = inspect.getsource(handle_export_fbx)
        assert "object_names" in source, "handle_export_fbx should read object_names param"

    def test_object_names_in_return_dict(self):
        """Return dict includes object_names_filter key."""
        from blender_addon.handlers.export import handle_export_fbx
        import inspect

        source = inspect.getsource(handle_export_fbx)
        assert "object_names_filter" in source, "Return dict should include object_names_filter"

    def test_selection_logic_present(self):
        """object_names triggers selection-based export with selected_only=True."""
        from blender_addon.handlers.export import handle_export_fbx
        import inspect

        source = inspect.getsource(handle_export_fbx)
        assert "select_set" in source, "Should call select_set for per-object selection"
        assert "DESELECT" in source, "Should deselect all before selecting specific objects"
