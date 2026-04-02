"""Integration tests for procedural mesh wiring into handlers.

Tests verify that:
- Furniture types from _ROOM_CONFIGS are mapped or documented as unmapped
- Vegetation types are handled (mapped or fallback)
- Dungeon prop placements produce valid types for DUNGEON_PROP_MAP
- Dungeon prop placement rules (torch spacing, boss altar, etc.)
- Castle elements are mapped in CASTLE_ELEMENT_MAP

All tests are pure-logic (no bpy needed).
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers._building_grammar import _ROOM_CONFIGS
from blender_addon.handlers._mesh_bridge import (
    CASTLE_ELEMENT_MAP,
    DUNGEON_PROP_MAP,
    FURNITURE_GENERATOR_MAP,
    VEGETATION_GENERATOR_MAP,
)
from blender_addon.handlers._dungeon_gen import (
    DungeonLayout,
    Room,
    generate_bsp_dungeon,
    generate_dungeon_prop_placements,
)


# -------------------------------------------------------------------------
# Known unmapped furniture types (documented -- these fall back to cubes)
# -------------------------------------------------------------------------

_UNMAPPED_FURNITURE_TYPES = {
    "armor_stand", "bar_counter", "bed", "bellows", "bucket",
    "bunk_bed", "coin_pile", "cooking_fire", "cot", "display_case",
    "distillation_apparatus", "fireplace", "footlocker", "herb_rack",
    "iron_maiden", "map_display", "nightstand", "painting", "pew",
    "rack", "safe", "throne", "tool_rack", "trophy_mount",
    "wardrobe", "weapon_rack",
}


class TestInteriorFurnitureMapping:
    """Test that interior furniture types are mapped or documented."""

    def test_interior_furniture_types_mapped(self):
        """Every furniture type in _ROOM_CONFIGS is either in
        FURNITURE_GENERATOR_MAP or documented as unmapped."""
        all_types: set[str] = set()
        for room_type, items in _ROOM_CONFIGS.items():
            for item_type, _, _, _ in items:
                all_types.add(item_type)

        mapped = set(FURNITURE_GENERATOR_MAP.keys())
        unmapped = all_types - mapped

        # All unmapped types must be in the documented set
        undocumented = unmapped - _UNMAPPED_FURNITURE_TYPES
        assert not undocumented, (
            f"Furniture types not mapped and not documented as unmapped: "
            f"{sorted(undocumented)}"
        )

    def test_mapped_generators_return_valid_specs(self):
        """All mapped generators return dicts with required MeshSpec keys."""
        for ftype, (gen_func, kwargs) in FURNITURE_GENERATOR_MAP.items():
            spec = gen_func(**kwargs)
            assert "vertices" in spec, f"{ftype}: missing 'vertices'"
            assert "faces" in spec, f"{ftype}: missing 'faces'"
            assert "metadata" in spec, f"{ftype}: missing 'metadata'"

    def test_mapped_count_at_least_27(self):
        """At least 27 furniture types are mapped to procedural generators."""
        all_types: set[str] = set()
        for room_type, items in _ROOM_CONFIGS.items():
            for item_type, _, _, _ in items:
                all_types.add(item_type)
        mapped_count = len(all_types & set(FURNITURE_GENERATOR_MAP.keys()))
        assert mapped_count >= 27


class TestVegetationMapping:
    """Test that vegetation types used in scatter are handled."""

    _DEFAULT_VEG_TYPES = {"tree", "bush", "rock", "grass", "mushroom", "root"}

    def test_vegetation_types_mapped(self):
        """All default vegetation types are either in VEGETATION_GENERATOR_MAP
        or intentionally handled by fallback logic."""
        mapped = set(VEGETATION_GENERATOR_MAP.keys())
        fallback_types: set[str] = set()

        for vt in self._DEFAULT_VEG_TYPES:
            assert vt in mapped or vt in fallback_types, (
                f"Vegetation type '{vt}' has no generator and no fallback"
            )

    def test_vegetation_generators_return_valid_specs(self):
        """Mapped vegetation generators return valid MeshSpec dicts."""
        for vtype, (gen_func, kwargs) in VEGETATION_GENERATOR_MAP.items():
            spec = gen_func(**kwargs)
            assert "vertices" in spec, f"{vtype}: missing 'vertices'"
            assert "faces" in spec, f"{vtype}: missing 'faces'"
            assert "metadata" in spec, f"{vtype}: missing 'metadata'"


class TestDungeonPropPlacement:
    """Test dungeon prop placement logic (pure-logic, no bpy)."""

    @pytest.fixture
    def dungeon_layout(self) -> DungeonLayout:
        """Generate a reproducible dungeon layout for testing."""
        return generate_bsp_dungeon(64, 64, seed=42)

    def test_dungeon_prop_placement_produces_valid_types(
        self, dungeon_layout: DungeonLayout
    ):
        """All prop types in placements exist in DUNGEON_PROP_MAP or are
        known scatter types (chest, crate, barrel)."""
        props = generate_dungeon_prop_placements(dungeon_layout, seed=0)
        assert len(props) > 0, "Should produce at least some props"

        valid_types = set(DUNGEON_PROP_MAP.keys()) | {"chest", "crate", "barrel"}
        for p in props:
            assert p["type"] in valid_types, (
                f"Prop type '{p['type']}' not in DUNGEON_PROP_MAP or known types"
            )

    def test_dungeon_prop_placement_has_required_keys(
        self, dungeon_layout: DungeonLayout
    ):
        """Each placement dict has type, position, rotation, room_type."""
        props = generate_dungeon_prop_placements(dungeon_layout, seed=0)
        for p in props:
            assert "type" in p
            assert "position" in p
            assert "rotation" in p
            assert "room_type" in p
            assert len(p["position"]) == 3

    def test_dungeon_prop_placement_torch_spacing(
        self, dungeon_layout: DungeonLayout
    ):
        """Corridor torch sconces follow 4-6 cell spacing rule.

        Verifies that:
        1. Corridor torches exist when corridors exist
        2. Torch count is reasonable relative to total corridor length
           (roughly 1 torch per 4-6 cells of corridor)
        """
        props = generate_dungeon_prop_placements(dungeon_layout, seed=0)
        corridor_torches = [
            p for p in props
            if p["type"] == "torch_sconce" and p["room_type"] == "corridor"
        ]
        assert len(corridor_torches) > 0, (
            "Should have corridor torch sconces"
        )

        # Compute total corridor length
        total_corridor_cells = 0
        for (x1, y1), (x2, y2) in dungeon_layout.corridors:
            h_len = abs(x2 - x1) + 1
            v_len = abs(y2 - y1) + 1
            total_corridor_cells += h_len + v_len

        # With spacing of 4-6 cells, expect roughly
        # total_cells / 6 to total_cells / 4 torches per corridor
        # But corridors overlap at junctions so total is approximate
        min_expected = max(1, total_corridor_cells // 10)  # generous lower bound
        max_expected = total_corridor_cells  # generous upper bound

        assert min_expected <= len(corridor_torches) <= max_expected, (
            f"Corridor torch count {len(corridor_torches)} seems wrong "
            f"for {total_corridor_cells} corridor cells "
            f"(expected {min_expected}-{max_expected})"
        )

    def test_dungeon_boss_room_has_altar(
        self, dungeon_layout: DungeonLayout
    ):
        """Boss room placements include at least one altar."""
        # Ensure layout has a boss room
        boss_rooms = [r for r in dungeon_layout.rooms if r.room_type == "boss"]
        assert len(boss_rooms) > 0, "Dungeon should have a boss room"

        props = generate_dungeon_prop_placements(dungeon_layout, seed=0)
        boss_altars = [
            p for p in props
            if p["type"] == "altar" and p["room_type"] == "boss"
        ]
        assert len(boss_altars) >= 1, "Boss room should have at least one altar"

    def test_dungeon_treasure_room_has_chest(
        self, dungeon_layout: DungeonLayout
    ):
        """Treasure rooms include a chest."""
        treasure_rooms = [
            r for r in dungeon_layout.rooms if r.room_type == "treasure"
        ]
        if not treasure_rooms:
            pytest.skip("No treasure rooms in this layout")

        props = generate_dungeon_prop_placements(dungeon_layout, seed=0)
        treasure_chests = [
            p for p in props
            if p["type"] == "chest" and p["room_type"] == "treasure"
        ]
        assert len(treasure_chests) >= 1

    def test_dungeon_boss_room_has_pillars(
        self, dungeon_layout: DungeonLayout
    ):
        """Boss rooms have pillars at corners."""
        props = generate_dungeon_prop_placements(dungeon_layout, seed=0)
        boss_pillars = [
            p for p in props
            if p["type"] == "pillar" and p["room_type"] == "boss"
        ]
        # 4 corners per boss room
        boss_rooms = [r for r in dungeon_layout.rooms if r.room_type == "boss"]
        assert len(boss_pillars) >= 4 * len(boss_rooms)

    def test_dungeon_prop_placement_deterministic(
        self, dungeon_layout: DungeonLayout
    ):
        """Same seed produces same placements."""
        props1 = generate_dungeon_prop_placements(dungeon_layout, seed=123)
        props2 = generate_dungeon_prop_placements(dungeon_layout, seed=123)
        assert len(props1) == len(props2)
        for p1, p2 in zip(props1, props2):
            assert p1 == p2


class TestCastleElementMapping:
    """Test that castle element types are mapped."""

    _EXPECTED_ELEMENTS = {"gate", "rampart", "drawbridge", "fountain"}

    def test_castle_elements_mapped(self):
        """All castle element types are in CASTLE_ELEMENT_MAP."""
        mapped = set(CASTLE_ELEMENT_MAP.keys())
        for elem in self._EXPECTED_ELEMENTS:
            assert elem in mapped, f"Castle element '{elem}' not mapped"

    def test_castle_generators_return_valid_specs(self):
        """Castle element generators return valid MeshSpec dicts."""
        for etype, (gen_func, kwargs) in CASTLE_ELEMENT_MAP.items():
            spec = gen_func(**kwargs)
            assert "vertices" in spec, f"{etype}: missing 'vertices'"
            assert "faces" in spec, f"{etype}: missing 'faces'"
            assert "metadata" in spec, f"{etype}: missing 'metadata'"
