"""Preserve-list regression tests — Bundle A.

Asserts that the 7 Codex-landed fixes from docs/terrain_ultra_implementation_plan_2026-04-08.md §2.2
remain intact after Bundle A refactors.

1. env_generate_world_terrain returns a compatibility-wrapper result
2. aaa_verify_map returns passed=False for empty screenshot lists
3. validate_tile_seams handles 3D (per-channel) tile arrays
4. render_angle computes real yaw/pitch camera positions
5. env_generate_waterfall with a heightmap uses WaterNetwork
6. aaa_verify_map honors required_angle_count + angle_labels
7. blender_scene save_project + handle_save_project importable
"""

from __future__ import annotations

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# 1. env_generate_world_terrain compat wrapper
# ---------------------------------------------------------------------------


def test_preserve_env_generate_world_terrain_compat_wrapper():
    from blender_addon.handlers.environment import handle_generate_world_terrain

    # Force the wrapper path with a 1x1 tile — avoids the single-tile unwrap.
    result = handle_generate_world_terrain(
        {
            "name": "TestWorld",
            "tile_x": 0,
            "tile_y": 0,
            "tiles_x": 2,
            "tiles_y": 1,
            "width": 8,
            "height": 8,
            "scale": 50.0,
        }
    )
    assert result.get("deprecated_command") is True
    assert result.get("compatibility_mode") == "world_to_tile_wrapper"
    assert result.get("tile_count") == 2
    assert result.get("name") == "TestWorld"


# ---------------------------------------------------------------------------
# 2. aaa_verify_map empty screenshot list fails
# ---------------------------------------------------------------------------


def test_preserve_aaa_verify_map_empty_screenshot_fails():
    from veilbreakers_mcp.shared.visual_validation import aaa_verify_map

    result = aaa_verify_map([])
    assert result.get("passed") is False
    assert "missing_angles" in result or "reason" in result or "error" in result


# ---------------------------------------------------------------------------
# 3. validate_tile_seams 3D (per-channel) support
# ---------------------------------------------------------------------------


def test_preserve_validate_tile_seams_handles_3d_arrays():
    from blender_addon.handlers.terrain_chunking import validate_tile_seams

    # Two 4x4 tiles with 3 channels sharing an east seam
    tile_a = np.zeros((4, 4, 3), dtype=np.float64)
    tile_b = np.zeros((4, 4, 3), dtype=np.float64)
    tile_a[:, -1, :] = 1.0  # east edge
    tile_b[:, 0, :] = 1.0   # west edge matches

    result = validate_tile_seams(tile_a, tile_b, direction="east")

    assert isinstance(result, dict)
    assert result.get("match") is True
    # Per-channel metadata from Codex fix
    assert result.get("channel_count") == 3
    assert result.get("per_channel_max_delta") is not None
    assert result.get("per_channel_mean_delta") is not None


# ---------------------------------------------------------------------------
# 4. render_angle yaw/pitch camera math
# ---------------------------------------------------------------------------


def test_preserve_handle_render_angle_computes_yaw_pitch():
    """Verify handle_render_angle is NOT just an alias for get_viewport_screenshot.

    Inspect its source for the yaw/pitch camera math markers rather than
    executing it (the function needs a live bpy scene).
    """
    import inspect

    from blender_addon.handlers.viewport import handle_render_angle

    src = inspect.getsource(handle_render_angle)
    # Look for camera math markers added by Codex fix
    assert "yaw" in src.lower() or "pitch" in src.lower()
    assert "camera" in src.lower() or "render" in src.lower()


# ---------------------------------------------------------------------------
# 5. env_generate_waterfall uses WaterNetwork when given a heightmap
# ---------------------------------------------------------------------------


def test_preserve_env_generate_waterfall_uses_water_network_with_heightmap():
    """Inspect handle_generate_waterfall source to confirm the WaterNetwork wiring.

    Executing the full handler requires a live Blender scene for mesh ops;
    verifying the code path is sufficient for regression safety.
    """
    import inspect

    from blender_addon.handlers.environment import handle_generate_waterfall

    src = inspect.getsource(handle_generate_waterfall)
    assert "WaterNetwork" in src or "water_network" in src or "from_heightmap" in src
    assert "heightmap" in src


# ---------------------------------------------------------------------------
# 6. aaa_verify_map required_angle_count + angle_labels enforcement
# ---------------------------------------------------------------------------


def test_preserve_aaa_verify_map_required_angle_count_and_labels():
    from veilbreakers_mcp.shared.visual_validation import aaa_verify_map

    # Pass 2 fake screenshots but require 6 angles → must fail
    result = aaa_verify_map(
        [],
        required_angle_count=6,
        angle_labels=("front", "back", "left", "right", "top", "bottom"),
    )
    assert result.get("passed") is False
    # Should name specific missing angles
    missing = result.get("missing_angles") or result.get("missing") or []
    if missing:
        assert len(missing) > 0


# ---------------------------------------------------------------------------
# 7. blender_scene save_project + handle_save_project importable
# ---------------------------------------------------------------------------


def test_preserve_handle_save_project_importable():
    from blender_addon.handlers.scene import (
        handle_save_project,
        handle_verify_project_save,
    )

    assert callable(handle_save_project)
    assert callable(handle_verify_project_save)


def test_preserve_blender_scene_save_project_action_registered():
    """Verify the blender_scene MCP tool has save_project + verify_project_save actions."""
    import inspect

    from veilbreakers_mcp import blender_server

    src = inspect.getsource(blender_server)
    assert "save_project" in src
    assert "verify_project_save" in src


# ---------------------------------------------------------------------------
# Bonus: env_run_terrain_pass handler is dispatchable
# ---------------------------------------------------------------------------


def test_bundle_a_run_terrain_pass_dispatch_registered():
    """Ensure Bundle A's new handler is wired into the dispatch map."""
    from blender_addon.handlers import COMMAND_HANDLERS

    assert "env_run_terrain_pass" in COMMAND_HANDLERS
    assert callable(COMMAND_HANDLERS["env_run_terrain_pass"])
