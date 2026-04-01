"""Tests for pipeline_state.py -- checkpoint persistence for compose_map resume.

All tests are pure Python (no bpy dependency).  Uses temporary directories
for checkpoint file I/O.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from blender_addon.handlers.pipeline_state import (
    delete_pipeline_checkpoint,
    derive_addressable_groups,
    get_remaining_steps,
    load_pipeline_checkpoint,
    save_pipeline_checkpoint,
    validate_checkpoint_compatibility,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_checkpoint_dir(tmp_path):
    return str(tmp_path / "checkpoints")


def _base_state(**overrides):
    """Return a minimal valid pipeline state dict."""
    state = {
        "map_name": "TestMap",
        "seed": 42,
        "location_count": 3,
        "steps_completed": ["scene_cleared", "terrain_generated"],
        "created_objects": ["TestMap_Terrain"],
        "location_results": [],
        "interior_results": [],
        "params_snapshot": {"terrain_preset": "hills"},
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# save_pipeline_checkpoint / load_pipeline_checkpoint round-trip
# ---------------------------------------------------------------------------


class TestSaveAndLoad:

    def test_save_and_load_roundtrip(self, tmp_checkpoint_dir):
        state = _base_state()
        path = save_pipeline_checkpoint(tmp_checkpoint_dir, state)
        assert os.path.isfile(path)

        loaded = load_pipeline_checkpoint(tmp_checkpoint_dir, "TestMap")
        assert loaded is not None
        assert loaded["map_name"] == "TestMap"
        assert loaded["seed"] == 42
        assert loaded["steps_completed"] == ["scene_cleared", "terrain_generated"]
        assert loaded["created_objects"] == ["TestMap_Terrain"]

    def test_save_creates_directory(self, tmp_path):
        deep_dir = str(tmp_path / "a" / "b" / "c")
        path = save_pipeline_checkpoint(deep_dir, _base_state())
        assert os.path.isdir(deep_dir)
        assert os.path.isfile(path)

    def test_save_returns_absolute_path(self, tmp_checkpoint_dir):
        path = save_pipeline_checkpoint(tmp_checkpoint_dir, _base_state())
        assert os.path.isabs(path)

    def test_save_sanitises_map_name(self, tmp_checkpoint_dir):
        state = _base_state(map_name="Thornveil Region/v2")
        path = save_pipeline_checkpoint(tmp_checkpoint_dir, state)
        assert "Thornveil_Region_v2_checkpoint.json" in path

    def test_save_writes_valid_json(self, tmp_checkpoint_dir):
        path = save_pipeline_checkpoint(tmp_checkpoint_dir, _base_state())
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["version"] == 1

    def test_save_updated_at_changes(self, tmp_checkpoint_dir):
        import time
        save_pipeline_checkpoint(tmp_checkpoint_dir, _base_state())
        time.sleep(0.05)
        save_pipeline_checkpoint(tmp_checkpoint_dir, _base_state(steps_completed=["scene_cleared", "terrain_generated", "water_plane"]))
        loaded = load_pipeline_checkpoint(tmp_checkpoint_dir, "TestMap")
        assert "water_plane" in loaded["steps_completed"]

    def test_load_returns_none_when_no_file(self, tmp_checkpoint_dir):
        result = load_pipeline_checkpoint(tmp_checkpoint_dir, "NonExistent")
        assert result is None


# ---------------------------------------------------------------------------
# validate_checkpoint_compatibility
# ---------------------------------------------------------------------------


class TestValidateCompatibility:

    def test_validate_compatible_checkpoint(self):
        checkpoint = {"seed": 42, "location_count": 3}
        spec = {"seed": 42, "locations": [{"type": "town"}, {"type": "castle"}, {"type": "dungeon"}]}
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        assert ok is True
        assert reason == ""

    def test_validate_incompatible_seed(self):
        checkpoint = {"seed": 99, "location_count": 3}
        spec = {"seed": 42, "locations": [{}, {}, {}]}
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        assert ok is False
        assert "Seed mismatch" in reason

    def test_validate_incompatible_location_count(self):
        checkpoint = {"seed": 42, "location_count": 2}
        spec = {"seed": 42, "locations": [{}, {}, {}]}
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        assert ok is False
        assert "Location count mismatch" in reason

    def test_validate_compatible_when_seed_none(self):
        """If checkpoint has no seed, it should still be compatible."""
        checkpoint = {"location_count": 1}
        spec = {"seed": 42, "locations": [{}]}
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        assert ok is True

    def test_validate_compatible_when_spec_no_seed(self):
        """If spec has no seed, it should still be compatible."""
        checkpoint = {"seed": 42, "location_count": 1}
        spec = {"locations": [{}]}
        ok, reason = validate_checkpoint_compatibility(checkpoint, spec)
        assert ok is True


# ---------------------------------------------------------------------------
# get_remaining_steps
# ---------------------------------------------------------------------------


class TestGetRemainingSteps:

    def test_get_remaining_steps_all_missing(self):
        checkpoint = {"steps_completed": []}
        all_steps = ["scene_cleared", "terrain_generated", "water_plane", "locations"]
        remaining = get_remaining_steps(checkpoint, all_steps)
        assert remaining == all_steps

    def test_get_remaining_steps_partial(self):
        checkpoint = {"steps_completed": ["scene_cleared", "terrain_generated"]}
        all_steps = ["scene_cleared", "terrain_generated", "water_plane", "locations"]
        remaining = get_remaining_steps(checkpoint, all_steps)
        assert remaining == ["water_plane", "locations"]

    def test_get_remaining_steps_all_done(self):
        checkpoint = {"steps_completed": ["a", "b", "c"]}
        all_steps = ["a", "b", "c"]
        remaining = get_remaining_steps(checkpoint, all_steps)
        assert remaining == []

    def test_get_remaining_steps_preserves_order(self):
        checkpoint = {"steps_completed": ["terrain_generated"]}
        all_steps = ["scene_cleared", "terrain_generated", "water_plane", "roads"]
        remaining = get_remaining_steps(checkpoint, all_steps)
        assert remaining == ["scene_cleared", "water_plane", "roads"]


# ---------------------------------------------------------------------------
# delete_pipeline_checkpoint
# ---------------------------------------------------------------------------


class TestDeleteCheckpoint:

    def test_delete_removes_file(self, tmp_checkpoint_dir):
        save_pipeline_checkpoint(tmp_checkpoint_dir, _base_state())
        assert load_pipeline_checkpoint(tmp_checkpoint_dir, "TestMap") is not None
        deleted = delete_pipeline_checkpoint(tmp_checkpoint_dir, "TestMap")
        assert deleted is True
        assert load_pipeline_checkpoint(tmp_checkpoint_dir, "TestMap") is None

    def test_delete_returns_false_when_missing(self, tmp_checkpoint_dir):
        deleted = delete_pipeline_checkpoint(tmp_checkpoint_dir, "NonExistent")
        assert deleted is False


# ---------------------------------------------------------------------------
# derive_addressable_groups
# ---------------------------------------------------------------------------


class TestDeriveAddressableGroups:

    def test_produces_terrain_base_group(self):
        groups = derive_addressable_groups("TestMap", [])
        group_names = [g["group_name"] for g in groups]
        assert "TestMap_terrain_base" in group_names

    def test_per_location_type_group(self):
        locations = [
            {"name": "Village1", "type": "town"},
            {"name": "Keep1", "type": "castle"},
            {"name": "Crypt1", "type": "dungeon"},
        ]
        groups = derive_addressable_groups("TestMap", locations)
        group_types = {g["group_type"] for g in groups}
        assert "town" in group_types
        assert "castle" in group_types
        assert "dungeon" in group_types

    def test_same_type_locations_merge(self):
        locations = [
            {"name": "Town1", "type": "town"},
            {"name": "Town2", "type": "town"},
        ]
        groups = derive_addressable_groups("TestMap", locations)
        town_group = [g for g in groups if g["group_type"] == "town"]
        assert len(town_group) == 1
        assert "Town1" in town_group[0]["objects"]
        assert "Town2" in town_group[0]["objects"]

    def test_produces_interiors_group(self):
        groups = derive_addressable_groups("TestMap", [])
        group_types = {g["group_type"] for g in groups}
        assert "interior" in group_types

    def test_distance_tiers_present(self):
        groups = derive_addressable_groups("TestMap", [{"name": "V", "type": "town"}])
        for g in groups:
            assert "distance_tier" in g


# ---------------------------------------------------------------------------
# emit_scene_hierarchy -- requires bpy, test RuntimeError guard
# ---------------------------------------------------------------------------


class TestEmitSceneHierarchyGuard:

    def test_raises_runtime_error_without_bpy(self):
        import sys
        from blender_addon.handlers.pipeline_state import emit_scene_hierarchy
        saved = sys.modules.pop("bpy", None)
        try:
            with pytest.raises(RuntimeError, match="requires bpy"):
                emit_scene_hierarchy("TestMap", [])
        finally:
            if saved is not None:
                sys.modules["bpy"] = saved
