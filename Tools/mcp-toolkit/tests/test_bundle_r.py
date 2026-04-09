"""Bundle R — Protocol Enforcement + Runtime Safety — full test suite.

Covers every module from Addendum 1.A.1:
  - terrain_protocol (7 ProtocolGate rules + @enforce_protocol decorator)
  - terrain_viewport_sync (ViewportVantage + freshness + frustum)
  - terrain_reference_locks (lock/unlock/drift)
  - terrain_addon_health (version + registration)
  - terrain_blender_safety (Z-up, screenshot cap, boolean safety, Tripo serial)
  - terrain_scene_read (capture_scene_read snapshot)
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_state(*, include_scene_read=True, include_viewport=True, anchors=()):
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )
    from blender_addon.handlers.terrain_viewport_sync import read_user_vantage

    height = np.zeros((33, 33), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=32,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    region_bounds = BBox(0.0, 0.0, 32.0, 32.0)
    scene_read = None
    if include_scene_read:
        scene_read = TerrainSceneRead(
            timestamp=time.time(),
            major_landforms=("ridge",),
            focal_point=(0.0, 0.0, 0.0),
            hero_features_present=(),
            hero_features_missing=(),
            waterfall_chains=(),
            cave_candidates=(),
            protected_zones_in_region=(),
            edit_scope=region_bounds,
            success_criteria=("test",),
            reviewer="pytest",
        )
    intent = TerrainIntentState(
        seed=42,
        region_bounds=region_bounds,
        tile_size=32,
        cell_size=1.0,
        anchors=tuple(anchors),
        scene_read=scene_read,
    )
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    if include_viewport:
        state.viewport_vantage = read_user_vantage()  # type: ignore[attr-defined]
    return state


# ---------------------------------------------------------------------------
# terrain_protocol.py
# ---------------------------------------------------------------------------


def test_rule_1_fresh_scene_read_passes():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    state = _make_state()
    ProtocolGate.rule_1_observe_before_calculate(state)


def test_rule_1_missing_scene_read_raises():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolGate,
        ProtocolViolation,
    )

    state = _make_state(include_scene_read=False)
    with pytest.raises(ProtocolViolation, match="rule_1"):
        ProtocolGate.rule_1_observe_before_calculate(state)


def test_rule_1_stale_scene_read_raises():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolGate,
        ProtocolViolation,
    )

    state = _make_state()
    with pytest.raises(ProtocolViolation, match="rule_1"):
        ProtocolGate.rule_1_observe_before_calculate(
            state,
            max_age_s=1.0,
            now=time.time() + 3600.0,
        )


def test_rule_2_attached_viewport_passes():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    state = _make_state()
    ProtocolGate.rule_2_sync_to_user_viewport(state)


def test_rule_2_missing_viewport_raises():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolGate,
        ProtocolViolation,
    )

    state = _make_state(include_viewport=False)
    with pytest.raises(ProtocolViolation, match="rule_2"):
        ProtocolGate.rule_2_sync_to_user_viewport(state)


def test_rule_2_out_of_view_ok_bypasses():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    state = _make_state(include_viewport=False)
    ProtocolGate.rule_2_sync_to_user_viewport(state, out_of_view_ok=True)


def test_rule_3_unlocked_anchors_pass():
    from blender_addon.handlers.terrain_protocol import ProtocolGate
    from blender_addon.handlers.terrain_reference_locks import clear_all_locks
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    anchor = TerrainAnchor(name="HERO_A", world_position=(1.0, 2.0, 3.0))
    state = _make_state(anchors=(anchor,))
    ProtocolGate.rule_3_lock_reference_empties(state)


def test_rule_3_drifted_anchor_raises():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolGate,
        ProtocolViolation,
    )
    from blender_addon.handlers.terrain_reference_locks import (
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    lock_anchor(TerrainAnchor(name="HERO_A", world_position=(1.0, 2.0, 3.0)))
    drifted = TerrainAnchor(name="HERO_A", world_position=(5.0, 2.0, 3.0))
    state = _make_state(anchors=(drifted,))
    with pytest.raises(ProtocolViolation, match="rule_3"):
        ProtocolGate.rule_3_lock_reference_empties(state)
    clear_all_locks()


def test_rule_4_real_geometry_allowed():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    ProtocolGate.rule_4_real_geometry_not_vertex_tricks(
        {"feature_kind": "cliff", "vertex_color_fake": False}
    )


def test_rule_4_vertex_fake_hero_raises():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolGate,
        ProtocolViolation,
    )

    with pytest.raises(ProtocolViolation, match="rule_4"):
        ProtocolGate.rule_4_real_geometry_not_vertex_tricks(
            {"feature_kind": "waterfall", "vertex_color_fake": True}
        )


def test_rule_5_small_edits_pass():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    state = _make_state()
    ProtocolGate.rule_5_smallest_diff_per_iteration(
        state, cells_affected=5, objects_affected=2
    )


def test_rule_5_bulk_edits_without_flag_raise():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolGate,
        ProtocolViolation,
    )

    state = _make_state()
    total_cells = state.mask_stack.height.size
    with pytest.raises(ProtocolViolation, match="rule_5"):
        ProtocolGate.rule_5_smallest_diff_per_iteration(
            state, cells_affected=total_cells, objects_affected=0
        )


def test_rule_5_bulk_edit_flag_allows():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    state = _make_state()
    total_cells = state.mask_stack.height.size
    ProtocolGate.rule_5_smallest_diff_per_iteration(
        state, cells_affected=total_cells, bulk_edit=True
    )


def test_rule_6_valid_placement_class_passes():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    ProtocolGate.rule_6_surface_vs_interior_classification(
        {"placements": [{"id": "rock_1", "placement_class": "surface"}]}
    )


def test_rule_6_invalid_placement_class_raises():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolGate,
        ProtocolViolation,
    )

    with pytest.raises(ProtocolViolation, match="rule_6"):
        ProtocolGate.rule_6_surface_vs_interior_classification(
            {"placements": [{"id": "rock_1", "placement_class": "on_a_cliff"}]}
        )


def test_rule_7_plugin_version_passes():
    from blender_addon.handlers.terrain_protocol import ProtocolGate

    ProtocolGate.rule_7_plugin_usage({})


def test_enforce_protocol_decorator_runs_gates():
    from blender_addon.handlers.terrain_protocol import enforce_protocol
    from blender_addon.handlers.terrain_reference_locks import clear_all_locks

    clear_all_locks()

    @enforce_protocol(require_rule_3=False, require_rule_6=False, require_rule_7=False)
    def my_handler(state, params):
        return {"ok": True}

    state = _make_state()
    result = my_handler(state, {"feature_kind": "rock"})
    assert result == {"ok": True}


def test_enforce_protocol_decorator_blocks_on_failure():
    from blender_addon.handlers.terrain_protocol import (
        ProtocolViolation,
        enforce_protocol,
    )

    @enforce_protocol(require_rule_3=False, require_rule_6=False, require_rule_7=False)
    def my_handler(state, params):
        return {"ok": True}

    state = _make_state(include_scene_read=False)
    with pytest.raises(ProtocolViolation):
        my_handler(state, {})


# ---------------------------------------------------------------------------
# terrain_viewport_sync.py
# ---------------------------------------------------------------------------


def test_vantage_default_is_z_up():
    from blender_addon.handlers.terrain_viewport_sync import read_user_vantage

    v = read_user_vantage()
    assert v.camera_up == (0.0, 0.0, 1.0)


def test_vantage_fresh_passes():
    from blender_addon.handlers.terrain_viewport_sync import (
        assert_vantage_fresh,
        read_user_vantage,
    )

    v = read_user_vantage()
    assert_vantage_fresh(v, max_age_seconds=60.0)


def test_vantage_stale_raises():
    from blender_addon.handlers.terrain_viewport_sync import (
        ViewportStale,
        assert_vantage_fresh,
        read_user_vantage,
    )

    v = read_user_vantage()
    with pytest.raises(ViewportStale):
        assert_vantage_fresh(v, max_age_seconds=0.1, now=time.time() + 10.0)


def test_vantage_frustum_contains_center():
    from blender_addon.handlers.terrain_viewport_sync import (
        is_in_frustum,
        read_user_vantage,
    )

    v = read_user_vantage()
    assert is_in_frustum((0.0, 0.0, 0.0), v) is True


def test_vantage_frustum_rejects_far():
    from blender_addon.handlers.terrain_viewport_sync import (
        is_in_frustum,
        read_user_vantage,
    )

    v = read_user_vantage()
    assert is_in_frustum((1000.0, 1000.0, 0.0), v) is False


def test_vantage_transform_returns_tuple():
    from blender_addon.handlers.terrain_viewport_sync import (
        read_user_vantage,
        transform_world_to_vantage,
    )

    v = read_user_vantage()
    coords = transform_world_to_vantage((1.0, 2.0, 3.0), v)
    assert isinstance(coords, tuple)
    assert len(coords) == 3


def test_vantage_view_matrix_hash_is_stable():
    from blender_addon.handlers.terrain_viewport_sync import read_user_vantage

    v1 = read_user_vantage(
        camera_position=(0.0, -20.0, 12.0), focal_point=(0.0, 0.0, 0.0)
    )
    v2 = read_user_vantage(
        camera_position=(0.0, -20.0, 12.0), focal_point=(0.0, 0.0, 0.0)
    )
    assert v1.view_matrix_hash == v2.view_matrix_hash


def test_vantage_different_cameras_differ():
    from blender_addon.handlers.terrain_viewport_sync import read_user_vantage

    v1 = read_user_vantage(camera_position=(0.0, -20.0, 12.0))
    v2 = read_user_vantage(camera_position=(10.0, -20.0, 12.0))
    assert v1.view_matrix_hash != v2.view_matrix_hash


# ---------------------------------------------------------------------------
# terrain_reference_locks.py
# ---------------------------------------------------------------------------


def test_lock_and_retrieve():
    from blender_addon.handlers.terrain_reference_locks import (
        clear_all_locks,
        is_locked,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    a = TerrainAnchor(name="CLIFF_A", world_position=(1.0, 2.0, 3.0))
    lock_anchor(a)
    assert is_locked("CLIFF_A")


def test_unlock_releases():
    from blender_addon.handlers.terrain_reference_locks import (
        clear_all_locks,
        is_locked,
        lock_anchor,
        unlock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    lock_anchor(TerrainAnchor(name="CLIFF_A", world_position=(1.0, 2.0, 3.0)))
    unlock_anchor("CLIFF_A")
    assert not is_locked("CLIFF_A")


def test_intact_anchor_passes():
    from blender_addon.handlers.terrain_reference_locks import (
        assert_anchor_integrity,
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    a = TerrainAnchor(name="X", world_position=(0.0, 0.0, 0.0))
    lock_anchor(a)
    assert_anchor_integrity(a)


def test_drifted_anchor_raises():
    from blender_addon.handlers.terrain_reference_locks import (
        AnchorDrift,
        assert_anchor_integrity,
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    lock_anchor(TerrainAnchor(name="X", world_position=(0.0, 0.0, 0.0)))
    drifted = TerrainAnchor(name="X", world_position=(10.0, 0.0, 0.0))
    with pytest.raises(AnchorDrift):
        assert_anchor_integrity(drifted)


def test_assert_all_anchors_intact_returns_reports():
    from blender_addon.handlers.terrain_reference_locks import (
        assert_all_anchors_intact,
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainAnchor,
        TerrainIntentState,
    )

    clear_all_locks()
    a = TerrainAnchor(name="A", world_position=(0.0, 0.0, 0.0))
    b = TerrainAnchor(name="B", world_position=(5.0, 5.0, 5.0))
    lock_anchor(a)
    lock_anchor(b)
    intent = TerrainIntentState(
        seed=1,
        region_bounds=BBox(0, 0, 10, 10),
        tile_size=16,
        cell_size=1.0,
        anchors=(a, b),
    )
    reports = assert_all_anchors_intact(intent)
    assert len(reports) == 2
    assert all(not r.drifted for r in reports)


def test_unlocked_anchor_treated_as_intact():
    from blender_addon.handlers.terrain_reference_locks import (
        assert_anchor_integrity,
        clear_all_locks,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    a = TerrainAnchor(name="ghost", world_position=(1.0, 2.0, 3.0))
    # Unlocked — should not raise
    assert_anchor_integrity(a)


def test_lock_overwrites_previous():
    from blender_addon.handlers.terrain_reference_locks import (
        _LOCKED_ANCHORS,
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    lock_anchor(TerrainAnchor(name="X", world_position=(0, 0, 0)))
    lock_anchor(TerrainAnchor(name="X", world_position=(1, 1, 1)))
    assert _LOCKED_ANCHORS["X"].world_position == (1, 1, 1)


def test_within_tolerance_passes():
    from blender_addon.handlers.terrain_reference_locks import (
        assert_anchor_integrity,
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    lock_anchor(TerrainAnchor(name="X", world_position=(0.0, 0.0, 0.0)))
    # 0.005m drift below 0.01m tolerance
    drifted = TerrainAnchor(name="X", world_position=(0.005, 0.0, 0.0))
    assert_anchor_integrity(drifted, tolerance=0.01)


def test_beyond_tolerance_raises():
    from blender_addon.handlers.terrain_reference_locks import (
        AnchorDrift,
        assert_anchor_integrity,
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import TerrainAnchor

    clear_all_locks()
    lock_anchor(TerrainAnchor(name="X", world_position=(0.0, 0.0, 0.0)))
    drifted = TerrainAnchor(name="X", world_position=(0.02, 0.0, 0.0))
    with pytest.raises(AnchorDrift):
        assert_anchor_integrity(drifted, tolerance=0.01)


def test_zero_distance_intact():
    from blender_addon.handlers.terrain_reference_locks import (
        assert_all_anchors_intact,
        clear_all_locks,
        lock_anchor,
    )
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainAnchor,
        TerrainIntentState,
    )

    clear_all_locks()
    a = TerrainAnchor(name="Z", world_position=(0.0, 0.0, 0.0))
    lock_anchor(a)
    intent = TerrainIntentState(
        seed=0,
        region_bounds=BBox(0, 0, 1, 1),
        tile_size=1,
        cell_size=1.0,
        anchors=(a,),
    )
    reports = assert_all_anchors_intact(intent)
    assert reports[0].distance_m == 0.0


# ---------------------------------------------------------------------------
# terrain_addon_health.py
# ---------------------------------------------------------------------------


def test_addon_loaded():
    from blender_addon.handlers.terrain_addon_health import assert_addon_loaded

    assert_addon_loaded()


def test_addon_version_matches_minimum():
    from blender_addon.handlers.terrain_addon_health import (
        assert_addon_version_matches,
    )

    assert_addon_version_matches((1, 0, 0))


def test_addon_version_mismatch_raises():
    from blender_addon.handlers.terrain_addon_health import (
        AddonVersionMismatch,
        _read_bl_info_version,
        assert_addon_version_matches,
    )

    version = _read_bl_info_version()
    if version is None:
        pytest.skip("bl_info not present — version check is a no-op")
    with pytest.raises(AddonVersionMismatch):
        assert_addon_version_matches((999, 0, 0))


def test_handlers_registered_for_env_run_terrain_pass():
    from blender_addon.handlers.terrain_addon_health import (
        assert_handlers_registered,
    )

    assert_handlers_registered(["env_run_terrain_pass"])


def test_handlers_registered_missing_raises():
    from blender_addon.handlers.terrain_addon_health import (
        AddonNotLoaded,
        assert_handlers_registered,
    )

    with pytest.raises(AddonNotLoaded):
        assert_handlers_registered(["definitely_not_a_real_handler_123"])


def test_detect_stale_addon_returns_bool():
    from blender_addon.handlers.terrain_addon_health import detect_stale_addon

    assert isinstance(detect_stale_addon(), bool)


def test_force_reload_noop_headless():
    from blender_addon.handlers.terrain_addon_health import force_addon_reload

    force_addon_reload()  # must not raise in headless mode


def test_read_bl_info_version_returns_tuple_or_none():
    from blender_addon.handlers.terrain_addon_health import _read_bl_info_version

    version = _read_bl_info_version()
    assert version is None or isinstance(version, tuple)


# ---------------------------------------------------------------------------
# terrain_blender_safety.py
# ---------------------------------------------------------------------------


def test_assert_z_is_up_allows_z():
    from blender_addon.handlers.terrain_blender_safety import assert_z_is_up

    assert_z_is_up("Z")
    assert_z_is_up("+Z")
    assert_z_is_up("-Z")  # negative-Z still counts as Z axis
    assert_z_is_up("z")  # case-insensitive


def test_assert_z_is_up_rejects_y():
    from blender_addon.handlers.terrain_blender_safety import (
        CoordinateSystemError,
        assert_z_is_up,
    )

    with pytest.raises(CoordinateSystemError):
        assert_z_is_up("Y")


def test_convert_y_up_to_z_up_maps_axes():
    from blender_addon.handlers.terrain_blender_safety import convert_y_up_to_z_up

    pos, rot = convert_y_up_to_z_up((1.0, 2.0, 3.0))
    assert pos == (1.0, -3.0, 2.0)


def test_guard_z_up_blocks_y():
    from blender_addon.handlers.terrain_blender_safety import (
        CoordinateSystemError,
        guard_z_up,
    )

    @guard_z_up
    def setter(value, *, up_axis=None):
        return value

    setter(1, up_axis="Z")
    with pytest.raises(CoordinateSystemError):
        setter(1, up_axis="Y")


def test_screenshot_cap_clamps_large():
    from blender_addon.handlers.terrain_blender_safety import (
        BLENDER_SCREENSHOT_MAX_SIZE,
        clamp_screenshot_size,
    )

    assert clamp_screenshot_size(1024) == BLENDER_SCREENSHOT_MAX_SIZE
    assert clamp_screenshot_size(2048) == BLENDER_SCREENSHOT_MAX_SIZE


def test_screenshot_cap_clamps_small():
    from blender_addon.handlers.terrain_blender_safety import (
        BLENDER_SCREENSHOT_MIN_SIZE,
        clamp_screenshot_size,
    )

    assert clamp_screenshot_size(16) == BLENDER_SCREENSHOT_MIN_SIZE


def test_screenshot_cap_preserves_valid():
    from blender_addon.handlers.terrain_blender_safety import clamp_screenshot_size

    assert clamp_screenshot_size(256) == 256
    assert clamp_screenshot_size(507) == 507


def test_assert_boolean_safe_small_ok():
    from blender_addon.handlers.terrain_blender_safety import assert_boolean_safe

    assert_boolean_safe(1000, 2000)


def test_assert_boolean_safe_dense_raises():
    from blender_addon.handlers.terrain_blender_safety import (
        BlenderBooleanUnsafe,
        assert_boolean_safe,
    )

    with pytest.raises(BlenderBooleanUnsafe):
        assert_boolean_safe(70000, 5000)
    with pytest.raises(BlenderBooleanUnsafe):
        assert_boolean_safe(5000, 70000)


def test_decimate_ratio_for_dense():
    from blender_addon.handlers.terrain_blender_safety import (
        BOOLEAN_DENSE_MESH_DECIMATE_TARGET,
        decimate_to_safe_count,
    )

    ratio = decimate_to_safe_count(120000, BOOLEAN_DENSE_MESH_DECIMATE_TARGET)
    assert 0.0 < ratio < 0.5


def test_decimate_ratio_for_already_safe():
    from blender_addon.handlers.terrain_blender_safety import decimate_to_safe_count

    assert decimate_to_safe_count(5000, 30000) == 1.0


def test_recommend_solver_dense_uses_fast():
    from blender_addon.handlers.terrain_blender_safety import recommend_boolean_solver

    assert recommend_boolean_solver(50000, 10000) == "FAST"
    assert recommend_boolean_solver(1000, 1000) == "EXACT"


def test_tripo_serialized_preserves_order():
    from blender_addon.handlers.terrain_blender_safety import (
        clear_tripo_import_log,
        get_tripo_import_log,
        import_tripo_glb_serialized,
    )

    clear_tripo_import_log()
    paths = [Path(f"mock_{i}.glb") for i in range(5)]
    result = import_tripo_glb_serialized(paths)
    log = get_tripo_import_log()
    assert [str(p) for p in result] == [str(p) for p in paths]
    assert len(log) == 5


def test_tripo_serial_empty_list_ok():
    from blender_addon.handlers.terrain_blender_safety import (
        import_tripo_glb_serialized,
    )

    assert import_tripo_glb_serialized([]) == []


# ---------------------------------------------------------------------------
# terrain_scene_read.py
# ---------------------------------------------------------------------------


def test_capture_scene_read_basic():
    from blender_addon.handlers.terrain_scene_read import capture_scene_read

    sr = capture_scene_read(reviewer="pytest")
    assert sr.reviewer == "pytest"
    assert sr.focal_point == (0.0, 0.0, 0.0)
    assert sr.edit_scope is not None


def test_capture_scene_read_focal_hint():
    from blender_addon.handlers.terrain_scene_read import capture_scene_read

    sr = capture_scene_read(reviewer="p", focal_point_hint=(10.0, 20.0, 3.0))
    assert sr.focal_point == (10.0, 20.0, 3.0)


def test_capture_scene_read_includes_major_landforms():
    from blender_addon.handlers.terrain_scene_read import capture_scene_read

    sr = capture_scene_read(
        reviewer="p",
        major_landforms=("ridge_system", "canyon"),
    )
    assert "ridge_system" in sr.major_landforms
    assert "canyon" in sr.major_landforms


def test_capture_scene_read_timestamp_current():
    from blender_addon.handlers.terrain_scene_read import capture_scene_read

    before = time.time()
    sr = capture_scene_read(reviewer="p")
    after = time.time()
    assert before - 0.1 <= sr.timestamp <= after + 0.1


def test_handle_capture_scene_read_wrapper():
    from blender_addon.handlers.terrain_scene_read import handle_capture_scene_read

    result = handle_capture_scene_read(
        {
            "reviewer": "claude",
            "focal_point": [1.0, 2.0, 3.0],
            "major_landforms": ["ridge"],
        }
    )
    assert result["ok"] is True
    assert result["reviewer"] == "claude"
    assert result["focal_point"] == [1.0, 2.0, 3.0]


def test_scene_read_default_scope_centered_on_focal():
    from blender_addon.handlers.terrain_scene_read import capture_scene_read

    sr = capture_scene_read(reviewer="p", focal_point_hint=(100.0, 100.0, 5.0))
    assert sr.edit_scope.contains_point(100.0, 100.0)
