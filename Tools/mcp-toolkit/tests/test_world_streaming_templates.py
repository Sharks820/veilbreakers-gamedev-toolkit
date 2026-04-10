"""Tests for world_streaming_templates.py -- C# map streaming + occlusion zone spec.

All tests are pure Python (no Unity/Blender dependency).
"""

from __future__ import annotations

import re

import pytest

from veilbreakers_mcp.shared.unity_templates.world_streaming_templates import (
    generate_map_streaming_script,
    generate_occlusion_zone_spec,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_hierarchy(**overrides):
    """Return a minimal scene hierarchy dict."""
    base = {
        "map_name": "Thornveil",
        "generated_at": "2026-04-01T12:00:00Z",
        "objects": [
            {
                "name": "Thornveil_Terrain",
                "type": "MESH",
                "district": "terrain",
                "world_position": [0.0, 0.0, 0.0],
                "world_rotation_euler": [0.0, 0.0, 0.0],
                "world_scale": [1.0, 1.0, 1.0],
            },
            {
                "name": "Thornveil_Village_Hall",
                "type": "MESH",
                "district": "town",
                "world_position": [50.0, 0.0, 30.0],
                "world_rotation_euler": [0.0, 0.0, 0.0],
                "world_scale": [1.0, 1.0, 1.0],
            },
            {
                "name": "Thornveil_Castle_Keep",
                "type": "MESH",
                "district": "castle",
                "world_position": [-40.0, 10.0, -20.0],
                "world_rotation_euler": [0.0, 0.0, 0.0],
                "world_scale": [1.0, 1.0, 1.0],
            },
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# generate_map_streaming_script
# ---------------------------------------------------------------------------


class TestGenerateMapStreamingScript:

    def test_generate_map_streaming_script_is_valid_csharp(self):
        """Output contains essential C# structure: namespace, class, using directives."""
        cs = generate_map_streaming_script(_sample_hierarchy())
        assert "namespace VeilBreakers.World" in cs
        assert "public static class MapStreaming_Thornveil" in cs
        assert "using UnityEditor;" in cs
        assert "using UnityEngine;" in cs
        # Must have balanced braces (rough check)
        assert cs.count("{") == cs.count("}")

    def test_generate_map_streaming_includes_addressable_groups(self):
        """Script creates Addressable groups for each district in the hierarchy."""
        cs = generate_map_streaming_script(_sample_hierarchy())
        assert "CreateOrGetGroup" in cs
        assert "Thornveil_terrain" in cs
        assert "Thornveil_town" in cs
        assert "Thornveil_castle" in cs

    def test_generate_map_streaming_sets_static_flags(self):
        """Buildings (town/castle districts) get StaticEditorFlags set."""
        cs = generate_map_streaming_script(_sample_hierarchy())
        assert "StaticEditorFlags.BatchingStatic" in cs
        assert "StaticEditorFlags.OccluderStatic" in cs
        assert "StaticEditorFlags.OccludeeStatic" in cs
        # The town building should have static flags
        assert "Thornveil_Village_Hall" in cs
        # The castle building should have static flags
        assert "Thornveil_Castle_Keep" in cs

    def test_generate_map_streaming_calls_occlusion_compute(self):
        """Script calls StaticOcclusionCulling.Compute() for occlusion bake."""
        cs = generate_map_streaming_script(_sample_hierarchy())
        assert "StaticOcclusionCulling.Compute()" in cs

    def test_generate_map_streaming_script_with_namespace(self):
        """Custom namespace is appended to VeilBreakers.World."""
        cs = generate_map_streaming_script(_sample_hierarchy(), namespace="TestRegion")
        assert "namespace VeilBreakers.World.TestRegion" in cs


# ---------------------------------------------------------------------------
# generate_occlusion_zone_spec
# ---------------------------------------------------------------------------


class TestGenerateOcclusionZoneSpec:

    def test_generate_occlusion_zone_spec_returns_required_fields(self):
        """Return dict contains all required portal/zone fields."""
        door = {"position": [5.0, 0.0, 0.0], "width": 1.2, "height": 2.4, "facing": "north"}
        room = {"min": [0.0, 0.0, 0.0], "max": [10.0, 4.0, 10.0]}
        spec = generate_occlusion_zone_spec(door, room)

        required_keys = {
            "portal_center", "portal_extents", "zone_min", "zone_max",
            "facing", "door_width", "door_height",
        }
        assert required_keys.issubset(set(spec.keys()))
        assert spec["facing"] == "north"
        assert spec["door_width"] == 1.2
        assert spec["door_height"] == 2.4

    def test_generate_occlusion_zone_spec_portal_covers_door(self):
        """Portal extents must be at least half the door dimensions."""
        door = {"position": [5.0, 0.0, 5.0], "width": 2.0, "height": 3.0, "facing": "south"}
        room = {"min": [0.0, 0.0, 0.0], "max": [10.0, 4.0, 10.0]}
        spec = generate_occlusion_zone_spec(door, room)

        # Portal center matches door position
        assert spec["portal_center"] == [5.0, 0.0, 5.0]

        # For north/south facing: extents[0] = width/2, extents[1] = height/2
        assert spec["portal_extents"][0] >= 2.0 / 2.0  # half width
        assert spec["portal_extents"][1] >= 3.0 / 2.0  # half height

    def test_generate_occlusion_zone_spec_zone_inset(self):
        """Zone bounds are inset from room bounds (not flush with walls)."""
        door = {"position": [5.0, 0.0, 0.0], "width": 1.2, "height": 2.4, "facing": "north"}
        room = {"min": [0.0, 0.0, 0.0], "max": [10.0, 4.0, 10.0]}
        spec = generate_occlusion_zone_spec(door, room)

        # Zone min should be slightly larger than room min (inset)
        assert spec["zone_min"][0] > room["min"][0]
        assert spec["zone_min"][2] > room["min"][2]
        # Zone max should be slightly smaller than room max (inset)
        assert spec["zone_max"][0] < room["max"][0]
        assert spec["zone_max"][2] < room["max"][2]
        # Y axis is not inset (floor/ceiling stay)
        assert spec["zone_min"][1] == room["min"][1]
        assert spec["zone_max"][1] == room["max"][1]
