"""Tests for vegetation_serializer module.

Pure-logic tests only -- no bpy required.
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.vegetation_serializer import (
    serialize_vegetation_instances,
)


_TERRAIN_BOUNDS = {
    "terrain_name": "TestTerrain",
    "min_x": 0.0,
    "max_x": 200.0,
    "min_y": 0.0,
    "max_y": 200.0,
}


class TestVegetationSerializer:
    """Tests for pure-logic vegetation serialization."""

    def test_z_up_to_y_up_swap(self):
        """Blender position Z component does NOT go into Unity position Y (height from terrain=0)."""
        veg = [{
            "name": "Tree_01",
            "location": (100.0, 50.0, 15.0),  # Blender Z-up
            "rotation_z": 0.0,
            "scale": (1.0, 1.0, 1.0),
            "veg_type": "Oak_Tree",
        }]
        result = serialize_vegetation_instances(veg, _TERRAIN_BOUNDS)
        instance = result["instances"][0]
        # Unity TreeInstance position Y should be 0 (height comes from terrain)
        assert instance["position"][1] == 0.0

    def test_position_normalization(self):
        """Positions normalized to [0,1] range relative to terrain bounds."""
        veg = [{
            "name": "Tree_01",
            "location": (100.0, 100.0, 0.0),
            "rotation_z": 0.0,
            "scale": (1.0, 1.0, 1.0),
            "veg_type": "Oak",
        }]
        result = serialize_vegetation_instances(veg, _TERRAIN_BOUNDS)
        pos = result["instances"][0]["position"]
        assert pos[0] == pytest.approx(0.5, abs=0.001)  # 100/200
        assert pos[2] == pytest.approx(0.5, abs=0.001)  # 100/200

    def test_position_at_origin(self):
        """Position at terrain min should normalize to 0."""
        veg = [{
            "name": "Tree_01",
            "location": (0.0, 0.0, 0.0),
            "rotation_z": 0.0,
            "scale": (1.0, 1.0, 1.0),
            "veg_type": "Oak",
        }]
        result = serialize_vegetation_instances(veg, _TERRAIN_BOUNDS)
        pos = result["instances"][0]["position"]
        assert pos[0] == pytest.approx(0.0, abs=0.001)
        assert pos[2] == pytest.approx(0.0, abs=0.001)

    def test_position_at_max(self):
        """Position at terrain max should normalize to 1."""
        veg = [{
            "name": "Tree_01",
            "location": (200.0, 200.0, 0.0),
            "rotation_z": 0.0,
            "scale": (1.0, 1.0, 1.0),
            "veg_type": "Oak",
        }]
        result = serialize_vegetation_instances(veg, _TERRAIN_BOUNDS)
        pos = result["instances"][0]["position"]
        assert pos[0] == pytest.approx(1.0, abs=0.001)
        assert pos[2] == pytest.approx(1.0, abs=0.001)

    def test_prototype_mapping(self):
        """Each unique vegetation type gets a prototype_index."""
        veg = [
            {"name": "T1", "location": (10, 10, 0), "rotation_z": 0, "scale": (1, 1, 1), "veg_type": "Oak_Tree"},
            {"name": "T2", "location": (20, 20, 0), "rotation_z": 0, "scale": (1, 1, 1), "veg_type": "Pine_Tree"},
            {"name": "T3", "location": (30, 30, 0), "rotation_z": 0, "scale": (1, 1, 1), "veg_type": "Oak_Tree"},
        ]
        result = serialize_vegetation_instances(veg, _TERRAIN_BOUNDS)
        assert len(result["tree_prototypes"]) == 2  # Oak and Pine
        proto_names = {p["prefab_name"] for p in result["tree_prototypes"]}
        assert "Oak_Tree" in proto_names
        assert "Pine_Tree" in proto_names

        # Oak instances should share same prototype_index
        oak_indices = [i["prototype_index"] for i in result["instances"] if i["prototype_index"] == result["instances"][0]["prototype_index"]]
        assert len(oak_indices) == 2  # T1 and T3

    def test_output_json_format(self):
        """Output matches Unity TreeInstance JSON schema."""
        veg = [{
            "name": "T1",
            "location": (50, 50, 0),
            "rotation_z": 1.57,
            "scale": (1.5, 1.5, 2.0),
            "veg_type": "Bush",
        }]
        result = serialize_vegetation_instances(veg, _TERRAIN_BOUNDS)

        assert "terrain_name" in result
        assert result["terrain_name"] == "TestTerrain"
        assert "tree_prototypes" in result
        assert "instances" in result

        inst = result["instances"][0]
        assert "position" in inst
        assert "rotation" in inst
        assert "width_scale" in inst
        assert "height_scale" in inst
        assert "prototype_index" in inst
        assert len(inst["position"]) == 3
        assert inst["width_scale"] == pytest.approx(1.5, abs=0.01)
        assert inst["height_scale"] == pytest.approx(2.0, abs=0.01)

    def test_empty_collection(self):
        """Empty vegetation list returns valid JSON with zero instances."""
        result = serialize_vegetation_instances([], _TERRAIN_BOUNDS)
        assert result["instances"] == []
        assert result["tree_prototypes"] == []
        assert result["terrain_name"] == "TestTerrain"
