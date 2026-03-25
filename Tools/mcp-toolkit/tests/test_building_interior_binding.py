"""Tests for building-interior spatial binding and configuration mapping.

All tests are pure-logic (no bpy) — validates room alignment, style
propagation, door metadata, and full interior spec generation.
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.building_interior_binding import (
    BUILDING_ROOM_MAP,
    STYLE_MATERIAL_MAP,
    align_rooms_to_building,
    generate_door_metadata,
    generate_interior_spec_from_building,
    get_interior_materials,
    get_room_types_for_building,
)


# ---------------------------------------------------------------------------
# Room type mapping tests
# ---------------------------------------------------------------------------


class TestBuildingRoomMapping:
    """Test building-to-room-type configuration mapping."""

    def test_tavern_has_expected_rooms(self):
        rooms = get_room_types_for_building("tavern")
        types = {r["type"] for r in rooms}
        assert "tavern_hall" in types
        assert "kitchen" in types
        assert "storage" in types

    def test_castle_has_throne_room(self):
        rooms = get_room_types_for_building("castle")
        types = {r["type"] for r in rooms}
        assert "throne_room" in types
        assert "guard_barracks" in types

    def test_house_has_bedroom_and_kitchen(self):
        rooms = get_room_types_for_building("house")
        types = {r["type"] for r in rooms}
        assert "bedroom" in types
        assert "kitchen" in types

    def test_unknown_building_returns_empty(self):
        rooms = get_room_types_for_building("nonexistent_type")
        assert rooms == []

    def test_gate_has_no_rooms(self):
        """Gates/bridges/walls have no interior rooms."""
        assert get_room_types_for_building("gate") == []
        assert get_room_types_for_building("bridge") == []
        assert get_room_types_for_building("wall_section") == []

    def test_returns_copies(self):
        """Returned room dicts should be copies, not references."""
        rooms1 = get_room_types_for_building("tavern")
        rooms2 = get_room_types_for_building("tavern")
        rooms1[0]["name"] = "MODIFIED"
        assert rooms2[0]["name"] != "MODIFIED"

    def test_all_rooms_have_required_keys(self):
        for building_type, rooms in BUILDING_ROOM_MAP.items():
            for room in rooms:
                assert "type" in room, f"{building_type}: room missing 'type'"
                assert "name" in room, f"{building_type}: room missing 'name'"
                assert "floor" in room, f"{building_type}: room missing 'floor'"
                assert "size_ratio" in room, f"{building_type}: room missing 'size_ratio'"

    def test_size_ratios_per_floor_dont_exceed_one(self):
        """Rooms on each floor shouldn't claim more than 100% of the space."""
        for building_type, rooms in BUILDING_ROOM_MAP.items():
            floors: dict[int, float] = {}
            for room in rooms:
                fl = room["floor"]
                floors[fl] = floors.get(fl, 0) + room["size_ratio"]
            for fl, total in floors.items():
                assert total <= 1.01, (
                    f"{building_type} floor {fl}: total size_ratio "
                    f"{total} exceeds 1.0"
                )


# ---------------------------------------------------------------------------
# Style material mapping tests
# ---------------------------------------------------------------------------


class TestStyleMaterialMapping:
    """Test building style to interior material palette."""

    def test_all_styles_have_required_keys(self):
        required = {"wall", "floor", "ceiling", "trim", "accent"}
        for style, materials in STYLE_MATERIAL_MAP.items():
            missing = required - set(materials.keys())
            assert not missing, f"Style '{style}' missing keys: {missing}"

    def test_unknown_style_falls_back_to_medieval(self):
        result = get_interior_materials("nonexistent_style")
        expected = get_interior_materials("medieval")
        assert result == expected

    def test_gothic_has_stone_vault_ceiling(self):
        mats = get_interior_materials("gothic")
        assert "vault" in mats["ceiling"]

    def test_corrupted_has_void_accent(self):
        mats = get_interior_materials("corrupted")
        assert "void" in mats["accent"]


# ---------------------------------------------------------------------------
# Spatial alignment tests
# ---------------------------------------------------------------------------


class TestSpatialAlignment:
    """Test room-to-building footprint constraint and positioning."""

    def test_single_room_fills_building(self):
        rooms = [{"type": "tavern_hall", "name": "hall", "floor": 0, "size_ratio": 1.0}]
        aligned = align_rooms_to_building(10, 8, (0, 0, 0), rooms)
        assert len(aligned) == 1
        room = aligned[0]
        assert room["width"] == pytest.approx(9.4, abs=0.1)  # 10 - 0.3*2
        assert room["depth"] == pytest.approx(7.4, abs=0.1)  # 8 - 0.3*2

    def test_two_rooms_split_width(self):
        rooms = [
            {"type": "room_a", "name": "a", "floor": 0, "size_ratio": 0.5},
            {"type": "room_b", "name": "b", "floor": 0, "size_ratio": 0.5},
        ]
        aligned = align_rooms_to_building(10, 8, (0, 0, 0), rooms)
        assert len(aligned) == 2
        total_w = sum(r["width"] for r in aligned)
        assert total_w == pytest.approx(9.4, abs=0.1)

    def test_building_position_offsets_rooms(self):
        rooms = [{"type": "room", "name": "r", "floor": 0, "size_ratio": 1.0}]
        aligned = align_rooms_to_building(10, 8, (100, 200, 0), rooms)
        room = aligned[0]
        assert room["position"][0] >= 100
        assert room["position"][1] >= 200

    def test_bounds_match_position_and_dimensions(self):
        rooms = [{"type": "room", "name": "r", "floor": 0, "size_ratio": 1.0}]
        aligned = align_rooms_to_building(10, 8, (5, 10, 0), rooms)
        room = aligned[0]
        bmin = room["bounds"]["min"]
        bmax = room["bounds"]["max"]
        assert bmax[0] - bmin[0] == pytest.approx(room["width"], abs=0.01)
        assert bmax[1] - bmin[1] == pytest.approx(room["depth"], abs=0.01)

    def test_multi_floor_rooms_have_different_z(self):
        rooms = [
            {"type": "r", "name": "ground", "floor": 0, "size_ratio": 1.0},
            {"type": "r", "name": "upper", "floor": 1, "size_ratio": 1.0},
            {"type": "r", "name": "cellar", "floor": -1, "size_ratio": 1.0},
        ]
        aligned = align_rooms_to_building(10, 8, (0, 0, 0), rooms)
        z_values = {r["name"]: r["position"][2] for r in aligned}
        assert z_values["upper"] > z_values["ground"]
        assert z_values["cellar"] < z_values["ground"]

    def test_tiny_building_returns_empty(self):
        """Building too small for walls -> no rooms."""
        rooms = [{"type": "r", "name": "r", "floor": 0, "size_ratio": 1.0}]
        aligned = align_rooms_to_building(0.5, 0.5, (0, 0, 0), rooms)
        assert aligned == []


# ---------------------------------------------------------------------------
# Door metadata tests
# ---------------------------------------------------------------------------


class TestDoorMetadata:
    """Test door metadata generation with scene linking."""

    def test_front_door_faces_south(self):
        openings = [{"type": "door", "wall": "front", "floor": 0, "style": "square"}]
        doors = generate_door_metadata("Tavern", (0, 0, 0), 10, 8, openings)
        assert len(doors) == 1
        assert doors[0]["facing"] == "south"
        assert doors[0]["interior_scene_name"] == "Tavern_Interior"

    def test_windows_are_excluded(self):
        openings = [
            {"type": "door", "wall": "front", "floor": 0},
            {"type": "window", "wall": "left", "floor": 0},
        ]
        doors = generate_door_metadata("Test", (0, 0, 0), 10, 8, openings)
        assert len(doors) == 1

    def test_back_door_faces_north(self):
        openings = [{"type": "door", "wall": "back", "floor": 0}]
        doors = generate_door_metadata("Test", (0, 0, 0), 10, 8, openings)
        assert doors[0]["facing"] == "north"

    def test_door_position_offset_by_building(self):
        openings = [{"type": "door", "wall": "front", "floor": 0}]
        doors = generate_door_metadata("Test", (50, 100, 0), 10, 8, openings)
        assert doors[0]["position"][0] == pytest.approx(55.0, abs=0.1)
        assert doors[0]["position"][1] == pytest.approx(100.0, abs=0.1)

    def test_upper_floor_door_has_z_offset(self):
        openings = [{"type": "door", "wall": "front", "floor": 1}]
        doors = generate_door_metadata("Test", (0, 0, 0), 10, 8, openings, wall_height=4.0)
        assert doors[0]["position"][2] > 3.0  # floor 1 * 4.0 + offset


# ---------------------------------------------------------------------------
# Full interior spec generation tests
# ---------------------------------------------------------------------------


class TestGenerateInteriorSpec:
    """Test end-to-end interior spec generation from building definition."""

    def test_tavern_generates_valid_spec(self):
        spec = generate_interior_spec_from_building(
            "Tavern_01", "tavern", "medieval", 10, 12, (0, 0, 0)
        )
        assert spec["name"] == "Tavern_01_Interior"
        assert spec["style"] == "medieval"
        assert len(spec["rooms"]) > 0
        assert "materials" in spec

    def test_rooms_have_position_and_dimensions(self):
        spec = generate_interior_spec_from_building(
            "Test", "house", "medieval", 8, 6, (10, 20, 0)
        )
        for room in spec["rooms"]:
            assert "width" in room
            assert "depth" in room
            assert "position" in room
            assert room["width"] > 0
            assert room["depth"] > 0

    def test_building_bounds_included(self):
        spec = generate_interior_spec_from_building(
            "Test", "tavern", "gothic", 10, 12, (5, 10, 0)
        )
        assert "building_bounds" in spec
        assert spec["building_bounds"]["min"] == (5, 10)
        assert spec["building_bounds"]["max"] == (15, 22)

    def test_materials_match_style(self):
        spec = generate_interior_spec_from_building(
            "Test", "tavern", "gothic", 10, 12, (0, 0, 0)
        )
        assert spec["materials"]["ceiling"] == "stone_vault"

    def test_doors_generated_from_openings(self):
        openings = [
            {"type": "door", "wall": "front", "floor": 0, "style": "pointed_arch"},
        ]
        spec = generate_interior_spec_from_building(
            "Cathedral", "cathedral", "gothic", 15, 20, (0, 0, 0),
            openings=openings,
        )
        assert len(spec["doors"]) == 1
        assert spec["doors"][0]["interior_scene_name"] == "Cathedral_Interior"

    def test_gate_building_has_no_rooms(self):
        spec = generate_interior_spec_from_building(
            "Gate_01", "gate", "medieval", 6, 4, (0, 0, 0)
        )
        assert spec["rooms"] == []

    def test_castle_has_multiple_floors(self):
        spec = generate_interior_spec_from_building(
            "Castle_01", "castle", "gothic", 30, 40, (0, 0, 0)
        )
        floors = {r.get("position", (0, 0, 0))[2] for r in spec["rooms"]}
        # Castle should have ground floor and at least one other floor
        assert len(floors) >= 2
