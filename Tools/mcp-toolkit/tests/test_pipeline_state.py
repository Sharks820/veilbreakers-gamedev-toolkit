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

    def test_derive_addressable_groups_produces_terrain_tiers(self):
        """Near/Mid/Far terrain tiers are present in the output groups."""
        locations = [
            {"name": "Village1", "type": "town"},
            {"name": "Keep1", "type": "castle"},
        ]
        groups = derive_addressable_groups("TestMap", locations)
        tiers = {g["distance_tier"] for g in groups}
        assert "near" in tiers, "Expected 'near' tier for terrain base"
        assert "mid" in tiers, "Expected 'mid' tier for location groups"
        assert "far" in tiers, "Expected 'far' tier for interiors group"

    def test_derive_addressable_groups_per_location_type(self):
        """Each distinct location type gets its own addressable group."""
        locations = [
            {"name": "Town1", "type": "town"},
            {"name": "Town2", "type": "town"},
            {"name": "Castle1", "type": "castle"},
            {"name": "Dungeon1", "type": "dungeon"},
        ]
        groups = derive_addressable_groups("TestMap", locations)
        type_groups = [g for g in groups if g["group_type"] not in ("terrain", "interior")]
        assert len(type_groups) == 3  # town, castle, dungeon
        town_group = [g for g in type_groups if g["group_type"] == "town"][0]
        assert "Town1" in town_group["objects"]
        assert "Town2" in town_group["objects"]
        castle_group = [g for g in type_groups if g["group_type"] == "castle"][0]
        assert "Castle1" in castle_group["objects"]


# ---------------------------------------------------------------------------
# emit_scene_hierarchy -- requires bpy, test RuntimeError guard + fields
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

    def test_scene_hierarchy_fields_present(self):
        """With a mocked bpy, emit_scene_hierarchy returns correct fields."""
        import sys
        import types
        from unittest.mock import MagicMock

        # Build a fake bpy module with bpy.data.objects
        fake_bpy = types.ModuleType("bpy")
        fake_data = MagicMock()

        # Create a mock Blender object
        mock_obj = MagicMock()
        mock_obj.name = "Map_Terrain"
        mock_obj.type = "MESH"
        mock_obj.matrix_world.translation.x = 1.0
        mock_obj.matrix_world.translation.y = 2.0
        mock_obj.matrix_world.translation.z = 3.0
        mock_obj.rotation_euler.x = 0.0
        mock_obj.rotation_euler.y = 0.0
        mock_obj.rotation_euler.z = 0.0
        mock_obj.scale.x = 1.0
        mock_obj.scale.y = 1.0
        mock_obj.scale.z = 1.0

        fake_data.objects = [mock_obj]
        fake_bpy.data = fake_data
        sys.modules["bpy"] = fake_bpy

        try:
            # Must re-import so the guarded import picks up our fake bpy
            from blender_addon.handlers.pipeline_state import emit_scene_hierarchy
            result = emit_scene_hierarchy("TestMap", [{"name": "Map_Terrain", "type": "terrain"}])

            assert "map_name" in result
            assert result["map_name"] == "TestMap"
            assert "generated_at" in result
            assert "objects" in result
            assert len(result["objects"]) >= 1

            obj_entry = result["objects"][0]
            assert "name" in obj_entry
            assert "type" in obj_entry
            assert "district" in obj_entry
            assert "world_position" in obj_entry
            assert "world_rotation_euler" in obj_entry
            assert "world_scale" in obj_entry
            assert obj_entry["name"] == "Map_Terrain"
            assert obj_entry["district"] == "terrain"
        finally:
            del sys.modules["bpy"]
