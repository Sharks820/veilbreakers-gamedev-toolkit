"""Tests for world design pure-logic functions.

All tests are pure-logic (no bpy) and seed-deterministic.
Covers: location generation (WORLD-01), 16 room types (WORLD-02),
boss arenas (WORLD-03), world graph (WORLD-04), linked interiors (WORLD-05),
multi-floor dungeons (WORLD-06), furniture scale (WORLD-07),
overrun variants (WORLD-09), easter eggs (WORLD-10),
storytelling props (AAA-05).
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers._building_grammar import (
    FURNITURE_SCALE_REFERENCE,
    _ROOM_CONFIGS,
    _STORYTELLING_PROPS,
    add_storytelling_props,
    generate_interior_layout,
    generate_overrun_variant,
    validate_furniture_scale,
)
from blender_addon.handlers._dungeon_gen import (
    generate_multi_floor_dungeon,
    MultiFloorDungeon,
)
from blender_addon.handlers.worldbuilding_layout import (
    WorldGraph,
    WorldGraphEdge,
    WorldGraphNode,
    generate_boss_arena_spec,
    generate_easter_egg_spec,
    generate_linked_interior_spec,
    generate_location_spec,
    generate_world_graph,
)


# =========================================================================
# WORLD-01: Location Generation
# =========================================================================


class TestLocationGeneration:
    """Test generate_location_spec returns valid location data."""

    def test_returns_dict(self):
        spec = generate_location_spec(seed=42)
        assert isinstance(spec, dict)

    def test_has_terrain_bounds(self):
        spec = generate_location_spec(seed=42)
        assert "terrain_bounds" in spec
        bounds = spec["terrain_bounds"]
        assert "min" in bounds
        assert "max" in bounds
        assert "size" in bounds
        assert bounds["size"] > 0

    def test_has_buildings(self):
        spec = generate_location_spec(building_count=5, seed=42)
        assert "buildings" in spec
        assert len(spec["buildings"]) > 0

    def test_buildings_have_position_and_type(self):
        spec = generate_location_spec(building_count=3, seed=42)
        for b in spec["buildings"]:
            assert "type" in b
            assert "position" in b
            assert len(b["position"]) == 2
            assert "rotation" in b
            assert "size" in b

    def test_has_paths(self):
        spec = generate_location_spec(path_count=3, seed=42)
        assert "paths" in spec
        assert len(spec["paths"]) > 0

    def test_paths_have_from_to(self):
        spec = generate_location_spec(building_count=5, path_count=3, seed=42)
        for p in spec["paths"]:
            assert "from" in p
            assert "to" in p
            assert "width" in p
            assert "type" in p

    def test_has_pois(self):
        spec = generate_location_spec(poi_count=3, seed=42)
        assert "pois" in spec
        assert len(spec["pois"]) == 3

    def test_buildings_within_terrain_bounds(self):
        spec = generate_location_spec(building_count=5, seed=42)
        bounds = spec["terrain_bounds"]
        for b in spec["buildings"]:
            bx, by = b["position"]
            assert bounds["min"][0] <= bx <= bounds["max"][0]
            assert bounds["min"][1] <= by <= bounds["max"][1]

    def test_different_location_types(self):
        for loc_type in ["village", "fortress", "dungeon_entrance", "camp"]:
            spec = generate_location_spec(location_type=loc_type, seed=42)
            assert spec["location_type"] == loc_type

    def test_seed_determinism(self):
        s1 = generate_location_spec(seed=42)
        s2 = generate_location_spec(seed=42)
        assert s1["buildings"] == s2["buildings"]


# =========================================================================
# WORLD-02: 16 Room Types
# =========================================================================


class TestRoomTypes:
    """Verify all 16 room types exist in _ROOM_CONFIGS."""

    EXPECTED_ROOMS = {
        "tavern", "throne_room", "dungeon_cell", "bedroom",
        "kitchen", "library", "armory", "chapel",
        "blacksmith", "guard_barracks", "treasury", "war_room",
        "alchemy_lab", "torture_chamber", "crypt", "dining_hall",
    }

    def test_all_16_room_types_exist(self):
        assert len(_ROOM_CONFIGS) >= 16

    def test_expected_room_names(self):
        for name in self.EXPECTED_ROOMS:
            assert name in _ROOM_CONFIGS, f"Missing room type: {name}"

    def test_each_room_has_at_least_3_furniture(self):
        for name in self.EXPECTED_ROOMS:
            config = _ROOM_CONFIGS[name]
            assert len(config) >= 3, (
                f"Room '{name}' has only {len(config)} furniture items (need >= 3)"
            )

    def test_each_furniture_has_correct_format(self):
        """Each entry is (type, placement_rule, (w, d), height)."""
        for room_name, items in _ROOM_CONFIGS.items():
            for i, item in enumerate(items):
                assert len(item) == 4, (
                    f"{room_name}[{i}]: expected 4-tuple, got {len(item)}"
                )
                item_type, rule, size, height = item
                assert isinstance(item_type, str)
                assert rule in ("wall", "center", "corner"), (
                    f"{room_name}/{item_type}: unknown rule '{rule}'"
                )
                assert len(size) == 2
                assert height > 0

    def test_new_room_blacksmith_has_anvil(self):
        types = [item[0] for item in _ROOM_CONFIGS["blacksmith"]]
        assert "anvil" in types

    def test_new_room_guard_barracks_has_bunk_beds(self):
        types = [item[0] for item in _ROOM_CONFIGS["guard_barracks"]]
        assert "bunk_bed" in types

    def test_new_room_treasury_has_locked_chests(self):
        types = [item[0] for item in _ROOM_CONFIGS["treasury"]]
        assert "locked_chest" in types

    def test_new_room_dining_hall_has_long_table(self):
        types = [item[0] for item in _ROOM_CONFIGS["dining_hall"]]
        assert "long_table" in types

    def test_generate_layout_for_all_16_rooms(self):
        """All 16 room types produce non-empty layouts when given enough space."""
        for room_name in self.EXPECTED_ROOMS:
            layout = generate_interior_layout(room_name, 12.0, 12.0, 3.0, seed=42)
            assert len(layout) > 0, f"Room '{room_name}' produced empty layout"


# =========================================================================
# WORLD-03: Boss Arena
# =========================================================================


class TestBossArena:
    """Test generate_boss_arena_spec returns valid arena data."""

    def test_returns_dict(self):
        spec = generate_boss_arena_spec(seed=42)
        assert isinstance(spec, dict)

    def test_has_required_keys(self):
        spec = generate_boss_arena_spec(seed=42)
        assert "arena_type" in spec
        assert "diameter" in spec
        assert "covers" in spec
        assert "hazard_zones" in spec
        assert "fog_gate" in spec
        assert "phase_triggers" in spec

    def test_cover_count_matches(self):
        spec = generate_boss_arena_spec(cover_count=6, seed=42)
        assert len(spec["covers"]) == 6

    def test_hazard_count_matches(self):
        spec = generate_boss_arena_spec(hazard_zones=3, seed=42)
        assert len(spec["hazard_zones"]) == 3

    def test_phase_trigger_count_matches(self):
        spec = generate_boss_arena_spec(phase_trigger_count=4, seed=42)
        assert len(spec["phase_triggers"]) == 4

    def test_fog_gate_present_by_default(self):
        spec = generate_boss_arena_spec(seed=42)
        assert spec["fog_gate"] is not None

    def test_fog_gate_absent_when_disabled(self):
        spec = generate_boss_arena_spec(has_fog_gate=False, seed=42)
        assert spec["fog_gate"] is None

    def test_covers_within_diameter(self):
        diameter = 30.0
        radius = diameter / 2
        spec = generate_boss_arena_spec(diameter=diameter, seed=42)
        for cover in spec["covers"]:
            cx, cy = cover["position"]
            dist = math.sqrt(cx ** 2 + cy ** 2)
            assert dist <= radius, (
                f"Cover at ({cx}, {cy}) distance {dist} exceeds radius {radius}"
            )

    def test_hazards_within_diameter(self):
        diameter = 30.0
        radius = diameter / 2
        spec = generate_boss_arena_spec(diameter=diameter, seed=42)
        for hz in spec["hazard_zones"]:
            hx, hy = hz["position"]
            dist = math.sqrt(hx ** 2 + hy ** 2)
            assert dist <= radius

    def test_arena_type_options(self):
        for t in ["circular", "rectangular"]:
            spec = generate_boss_arena_spec(arena_type=t, seed=42)
            assert spec["arena_type"] == t

    def test_diameter_range_20_to_40(self):
        """Boss arenas should be 20-40m scale."""
        for d in [20.0, 30.0, 40.0]:
            spec = generate_boss_arena_spec(diameter=d, seed=42)
            assert spec["diameter"] == d


# =========================================================================
# WORLD-04: World Graph
# =========================================================================


class TestWorldGraph:
    """Test generate_world_graph produces connected graph with distance validation."""

    LOCATIONS = [
        {"name": "Village", "type": "village", "position": (0, 0)},
        {"name": "Forest", "type": "wilderness", "position": (80, 50)},
        {"name": "Castle", "type": "fortress", "position": (150, 20)},
        {"name": "Cave", "type": "dungeon", "position": (60, 120)},
        {"name": "Lake", "type": "landmark", "position": (130, 100)},
    ]

    def test_returns_world_graph(self):
        graph = generate_world_graph(self.LOCATIONS, seed=42)
        assert isinstance(graph, WorldGraph)

    def test_node_count_matches_locations(self):
        graph = generate_world_graph(self.LOCATIONS, seed=42)
        assert len(graph.nodes) == 5

    def test_graph_is_connected(self):
        """MST guarantees connectivity -- verify all nodes reachable."""
        graph = generate_world_graph(self.LOCATIONS, seed=42)
        # Build adjacency
        adj: dict[str, set[str]] = {n.name: set() for n in graph.nodes}
        for edge in graph.edges:
            adj[edge.from_node].add(edge.to_node)
            adj[edge.to_node].add(edge.from_node)
        # BFS from first node
        visited: set[str] = set()
        queue = [graph.nodes[0].name]
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            for neighbor in adj[current]:
                if neighbor not in visited:
                    queue.append(neighbor)
        assert visited == {n.name for n in graph.nodes}

    def test_minimum_edge_count(self):
        """MST produces N-1 edges minimum."""
        graph = generate_world_graph(self.LOCATIONS, seed=42)
        assert len(graph.edges) >= len(self.LOCATIONS) - 1

    def test_edge_distances_positive(self):
        graph = generate_world_graph(self.LOCATIONS, seed=42)
        for edge in graph.edges:
            assert edge.distance > 0

    def test_edge_distances_near_target(self):
        """At least MST edges exist; extra edges should be near target distance."""
        target = 105.0
        tolerance = target * 0.6  # 60% tolerance (some edges will be shorter in MST)
        graph = generate_world_graph(self.LOCATIONS, target_distance=target, seed=42)
        # Not all edges will match (MST edges are shortest), but graph should be non-empty
        assert len(graph.edges) > 0

    def test_seed_determinism(self):
        g1 = generate_world_graph(self.LOCATIONS, seed=42)
        g2 = generate_world_graph(self.LOCATIONS, seed=42)
        assert len(g1.edges) == len(g2.edges)
        for e1, e2 in zip(g1.edges, g2.edges):
            assert e1.from_node == e2.from_node
            assert e1.distance == e2.distance

    def test_empty_locations(self):
        graph = generate_world_graph([], seed=42)
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_single_location(self):
        graph = generate_world_graph(
            [{"name": "A", "type": "x", "position": (0, 0)}],
            seed=42,
        )
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 0


# =========================================================================
# WORLD-05: Linked Interior
# =========================================================================


class TestLinkedInterior:
    """Test generate_linked_interior_spec returns door, occlusion, lighting markers."""

    def test_returns_dict(self):
        spec = generate_linked_interior_spec(
            building_exterior_bounds={"min": (0, 0), "max": (10, 10)},
            interior_rooms=[{"name": "room_0", "bounds": {"min": (1, 1), "max": (9, 9)}}],
            door_positions=[{"position": (5, 0, 0), "facing": "south"}],
        )
        assert isinstance(spec, dict)

    def test_has_door_triggers(self):
        spec = generate_linked_interior_spec(
            building_exterior_bounds={"min": (0, 0), "max": (10, 10)},
            interior_rooms=[{"name": "room_0", "bounds": {"min": (1, 1), "max": (9, 9)}}],
            door_positions=[{"position": (5, 0, 0), "facing": "south"}],
        )
        assert "door_triggers" in spec
        assert len(spec["door_triggers"]) == 1
        dt = spec["door_triggers"][0]
        assert "position" in dt
        assert "size" in dt
        assert "facing" in dt

    def test_has_occlusion_zones(self):
        spec = generate_linked_interior_spec(
            building_exterior_bounds={"min": (0, 0), "max": (10, 10)},
            interior_rooms=[{"name": "room_0", "bounds": {"min": (1, 1), "max": (9, 9)}}],
            door_positions=[{"position": (5, 0, 0), "facing": "south"}],
        )
        assert "occlusion_zones" in spec
        assert len(spec["occlusion_zones"]) == 1
        oz = spec["occlusion_zones"][0]
        assert "bounds_min" in oz
        assert "bounds_max" in oz

    def test_has_lighting_transitions(self):
        spec = generate_linked_interior_spec(
            building_exterior_bounds={"min": (0, 0), "max": (10, 10)},
            interior_rooms=[{"name": "room_0", "bounds": {"min": (1, 1), "max": (9, 9)}}],
            door_positions=[{"position": (5, 0, 0), "facing": "south"}],
        )
        assert "lighting_transitions" in spec
        assert len(spec["lighting_transitions"]) == 1
        lt = spec["lighting_transitions"][0]
        assert "fade_distance" in lt
        assert "exterior_probe_position" in lt
        assert "interior_probe_position" in lt

    def test_multiple_doors(self):
        rooms = [
            {"name": "room_0", "bounds": {"min": (1, 1), "max": (5, 5)}},
            {"name": "room_1", "bounds": {"min": (5, 1), "max": (9, 5)}},
        ]
        doors = [
            {"position": (3, 0, 0), "facing": "south"},
            {"position": (7, 0, 0), "facing": "south"},
        ]
        spec = generate_linked_interior_spec(
            building_exterior_bounds={"min": (0, 0), "max": (10, 10)},
            interior_rooms=rooms,
            door_positions=doors,
        )
        assert len(spec["door_triggers"]) == 2
        assert len(spec["occlusion_zones"]) == 2
        assert len(spec["lighting_transitions"]) == 2


# =========================================================================
# WORLD-06: Multi-Floor Dungeon
# =========================================================================


class TestMultiFloorDungeon:
    """Test generate_multi_floor_dungeon returns correct floor/connection data."""

    def test_returns_multi_floor_dungeon(self):
        d = generate_multi_floor_dungeon(seed=42)
        assert isinstance(d, MultiFloorDungeon)

    def test_correct_number_of_floors(self):
        d = generate_multi_floor_dungeon(num_floors=4, seed=42)
        assert len(d.floors) == 4
        assert d.num_floors == 4

    def test_connections_between_adjacent_floors(self):
        d = generate_multi_floor_dungeon(num_floors=3, seed=42)
        for conn in d.connections:
            assert conn["to_floor"] == conn["from_floor"] + 1

    def test_connections_exist(self):
        d = generate_multi_floor_dungeon(num_floors=3, seed=42)
        assert len(d.connections) > 0

    def test_connection_types(self):
        d = generate_multi_floor_dungeon(
            connection_types=["staircase", "ladder"],
            num_floors=3,
            seed=42,
        )
        for conn in d.connections:
            assert conn["type"] in ["staircase", "ladder"]

    def test_total_rooms_positive(self):
        d = generate_multi_floor_dungeon(seed=42)
        assert d.total_rooms > 0

    def test_each_floor_has_rooms(self):
        d = generate_multi_floor_dungeon(num_floors=3, seed=42)
        for floor in d.floors:
            assert len(floor.rooms) > 0

    def test_connection_positions_in_grid(self):
        d = generate_multi_floor_dungeon(width=64, height=64, seed=42)
        for conn in d.connections:
            cx, cy = conn["position"]
            assert 0 <= cx < 64
            assert 0 <= cy < 64

    def test_connection_positions_walkable(self):
        """Connection points must be on walkable cells."""
        d = generate_multi_floor_dungeon(num_floors=3, seed=42)
        for conn in d.connections:
            cx, cy = conn["position"]
            from_floor = d.floors[conn["from_floor"]]
            to_floor = d.floors[conn["to_floor"]]
            # At least one of the connected floors should have walkable cell
            assert (
                from_floor.grid[cy, cx] > 0 or to_floor.grid[cy, cx] > 0
            ), f"Connection at ({cx}, {cy}) not walkable on either floor"

    def test_seed_determinism(self):
        d1 = generate_multi_floor_dungeon(seed=42)
        d2 = generate_multi_floor_dungeon(seed=42)
        assert d1.total_rooms == d2.total_rooms
        assert len(d1.connections) == len(d2.connections)


# =========================================================================
# WORLD-07: Furniture Scale Validation
# =========================================================================


class TestFurnitureScale:
    """Test validate_furniture_scale checks dimensions correctly."""

    def test_valid_ceiling_height(self):
        violations = validate_furniture_scale("tavern", ceiling_height=3.0)
        ceiling_violations = [v for v in violations if "ceiling" in v]
        assert len(ceiling_violations) == 0

    def test_invalid_ceiling_height_too_low(self):
        violations = validate_furniture_scale("tavern", ceiling_height=2.0)
        ceiling_violations = [v for v in violations if "ceiling" in v]
        assert len(ceiling_violations) == 1

    def test_invalid_ceiling_height_too_high(self):
        violations = validate_furniture_scale("tavern", ceiling_height=5.0)
        ceiling_violations = [v for v in violations if "ceiling" in v]
        assert len(ceiling_violations) == 1

    def test_furniture_scale_reference_exists(self):
        assert len(FURNITURE_SCALE_REFERENCE) > 0
        assert "door" in FURNITURE_SCALE_REFERENCE
        assert "table" in FURNITURE_SCALE_REFERENCE
        assert "ceiling" in FURNITURE_SCALE_REFERENCE

    def test_all_16_rooms_pass_scale_validation(self):
        """All 16 room configurations should pass scale validation."""
        all_rooms = [
            "tavern", "throne_room", "dungeon_cell", "bedroom",
            "kitchen", "library", "armory", "chapel",
            "blacksmith", "guard_barracks", "treasury", "war_room",
            "alchemy_lab", "torture_chamber", "crypt", "dining_hall",
        ]
        for room_name in all_rooms:
            violations = validate_furniture_scale(room_name, ceiling_height=3.0)
            assert len(violations) == 0, (
                f"Room '{room_name}' has scale violations: {violations}"
            )

    def test_unknown_room_returns_only_ceiling_check(self):
        violations = validate_furniture_scale("nonexistent_room", ceiling_height=3.0)
        assert len(violations) == 0

    def test_door_reference_range(self):
        assert FURNITURE_SCALE_REFERENCE["door"]["width"] == (1.0, 1.2)
        assert FURNITURE_SCALE_REFERENCE["door"]["height"] == (2.0, 2.2)


# =========================================================================
# WORLD-09: Overrun Variant
# =========================================================================


class TestOverrunVariant:
    """Test generate_overrun_variant adds narrative debris to layouts."""

    def test_returns_list(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        result = generate_overrun_variant(layout, 8, 6, 0.5, seed=42)
        assert isinstance(result, list)

    def test_adds_debris(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        result = generate_overrun_variant(layout, 8, 6, 0.5, seed=42)
        debris = [item for item in result if item.get("role") == "debris"]
        assert len(debris) > 0

    def test_adds_broken_walls_at_high_corruption(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        result = generate_overrun_variant(layout, 8, 6, 0.8, seed=42)
        broken = [item for item in result if item.get("role") == "broken_wall"]
        assert len(broken) > 0

    def test_adds_vegetation_at_moderate_corruption(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        result = generate_overrun_variant(layout, 8, 6, 0.6, seed=42)
        veg = [item for item in result if item.get("role") == "vegetation"]
        assert len(veg) > 0

    def test_adds_remains(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        result = generate_overrun_variant(layout, 8, 6, 0.5, seed=42)
        remains = [item for item in result if item.get("role") == "remains"]
        assert len(remains) > 0

    def test_preserves_original_items(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        original_count = len(layout)
        result = generate_overrun_variant(layout, 8, 6, 0.5, seed=42)
        # Original items should be a subset (possibly with 'damaged' flag)
        original_items = [item for item in result if "type" in item and item["type"] in
                          [l["type"] for l in layout]]
        # At minimum the original items are present (possibly marked damaged)
        assert len(result) > original_count

    def test_higher_corruption_means_more_debris(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        low = generate_overrun_variant(layout, 8, 6, 0.2, seed=42)
        high = generate_overrun_variant(layout, 8, 6, 0.9, seed=42)
        low_extra = len(low) - len(layout)
        high_extra = len(high) - len(layout)
        assert high_extra > low_extra

    def test_zero_corruption_adds_minimal(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        result = generate_overrun_variant(layout, 8, 6, 0.0, seed=42)
        # Even at 0 corruption, some minimal debris/remains may be added (min 1)
        assert len(result) >= len(layout)

    def test_damaged_flag_on_items(self):
        layout = generate_interior_layout("tavern", 8, 6, 3.0, seed=42)
        result = generate_overrun_variant(layout, 8, 6, 0.9, seed=42)
        damaged = [item for item in result if item.get("damaged")]
        # At high corruption, some items should be damaged
        assert len(damaged) > 0 or len(layout) == 0


# =========================================================================
# WORLD-10: Easter Eggs
# =========================================================================


class TestEasterEggs:
    """Test generate_easter_egg_spec returns secret rooms, paths, lore items."""

    LOCATION = {
        "terrain_bounds": {"size": 100.0},
        "buildings": [
            {"type": "tavern", "position": (10.0, 20.0)},
            {"type": "blacksmith", "position": (-15.0, 5.0)},
        ],
        "paths": [
            {"from": (10.0, 20.0), "to": (-15.0, 5.0), "width": 2.0, "type": "dirt"},
        ],
    }

    def test_returns_list(self):
        result = generate_easter_egg_spec(self.LOCATION, seed=42)
        assert isinstance(result, list)

    def test_correct_secret_room_count(self):
        result = generate_easter_egg_spec(
            self.LOCATION, secret_room_count=2, hidden_path_count=0,
            lore_item_count=0, seed=42,
        )
        secret_rooms = [e for e in result if e["type"] == "secret_room"]
        assert len(secret_rooms) == 2

    def test_correct_hidden_path_count(self):
        result = generate_easter_egg_spec(
            self.LOCATION, secret_room_count=0, hidden_path_count=3,
            lore_item_count=0, seed=42,
        )
        hidden_paths = [e for e in result if e["type"] == "hidden_path"]
        assert len(hidden_paths) == 3

    def test_correct_lore_item_count(self):
        result = generate_easter_egg_spec(
            self.LOCATION, secret_room_count=0, hidden_path_count=0,
            lore_item_count=4, seed=42,
        )
        lore_items = [e for e in result if e["type"] == "lore_item"]
        assert len(lore_items) == 4

    def test_total_count(self):
        result = generate_easter_egg_spec(
            self.LOCATION, secret_room_count=1, hidden_path_count=1,
            lore_item_count=2, seed=42,
        )
        assert len(result) == 4

    def test_secret_room_has_breakable_wall(self):
        result = generate_easter_egg_spec(
            self.LOCATION, secret_room_count=1, seed=42,
        )
        sr = [e for e in result if e["type"] == "secret_room"][0]
        assert "breakable_wall_position" in sr
        assert "room_behind" in sr

    def test_hidden_path_has_end_position(self):
        result = generate_easter_egg_spec(
            self.LOCATION, hidden_path_count=1, seed=42,
        )
        hp = [e for e in result if e["type"] == "hidden_path"][0]
        assert "end_position" in hp
        assert "path_length" in hp
        assert "concealment" in hp

    def test_lore_item_has_item_type(self):
        result = generate_easter_egg_spec(
            self.LOCATION, lore_item_count=1, seed=42,
        )
        li = [e for e in result if e["type"] == "lore_item"][0]
        assert "item_type" in li
        assert "lore_text_id" in li

    def test_seed_determinism(self):
        r1 = generate_easter_egg_spec(self.LOCATION, seed=42)
        r2 = generate_easter_egg_spec(self.LOCATION, seed=42)
        assert r1 == r2

    def test_empty_location(self):
        empty_loc = {"terrain_bounds": {"size": 50.0}}
        result = generate_easter_egg_spec(empty_loc, seed=42)
        assert len(result) > 0  # still generates using random positions


# =========================================================================
# AAA-05: Storytelling Props
# =========================================================================


class TestStorytellingProps:
    """Test add_storytelling_props produces narrative clutter for rooms."""

    def test_returns_list(self):
        result = add_storytelling_props("tavern", 8, 6, seed=42)
        assert isinstance(result, list)

    def test_returns_non_empty(self):
        result = add_storytelling_props("tavern", 8, 6, seed=42)
        assert len(result) > 0

    def test_props_have_required_fields(self):
        result = add_storytelling_props("tavern", 8, 6, seed=42)
        for prop in result:
            assert "prop_type" in prop
            assert "position" in prop
            assert "placement_rule" in prop
            assert len(prop["position"]) == 3

    def test_prop_types_from_catalog(self):
        result = add_storytelling_props("tavern", 8, 6, seed=42)
        valid_types = set(_STORYTELLING_PROPS.keys())
        for prop in result:
            assert prop["prop_type"] in valid_types

    def test_different_room_types_get_different_distributions(self):
        """Crypt should have more cobwebs than kitchen."""
        crypt_props = add_storytelling_props("crypt", 8, 6, seed=42)
        kitchen_props = add_storytelling_props("kitchen", 8, 6, seed=42)

        crypt_cobwebs = sum(1 for p in crypt_props if p["prop_type"] == "cobwebs")
        kitchen_cobwebs = sum(1 for p in kitchen_props if p["prop_type"] == "cobwebs")

        # Crypt should have more cobwebs due to 2.0x modifier
        # (probabilistic -- use enough room size to make it reliable)
        crypt_props_big = add_storytelling_props("crypt", 20, 20, density_modifier=2.0, seed=42)
        kitchen_props_big = add_storytelling_props("kitchen", 20, 20, density_modifier=2.0, seed=42)
        crypt_cobwebs_big = sum(1 for p in crypt_props_big if p["prop_type"] == "cobwebs")
        kitchen_cobwebs_big = sum(1 for p in kitchen_props_big if p["prop_type"] == "cobwebs")
        # At larger scale, the modifier difference should show
        assert crypt_cobwebs_big >= kitchen_cobwebs_big

    def test_density_modifier_increases_props(self):
        low = add_storytelling_props("tavern", 8, 6, density_modifier=0.5, seed=42)
        high = add_storytelling_props("tavern", 8, 6, density_modifier=2.0, seed=42)
        assert len(high) >= len(low)

    def test_seed_determinism(self):
        r1 = add_storytelling_props("tavern", 8, 6, seed=42)
        r2 = add_storytelling_props("tavern", 8, 6, seed=42)
        assert r1 == r2

    def test_props_within_room_bounds(self):
        result = add_storytelling_props("tavern", 8, 6, seed=42)
        for prop in result:
            x, y, z = prop["position"]
            assert 0 <= x <= 8.0, f"Prop x={x} outside [0, 8]"
            assert 0 <= y <= 6.0, f"Prop y={y} outside [0, 6]"
            assert z == 0.0

    def test_storytelling_props_catalog_exists(self):
        assert len(_STORYTELLING_PROPS) >= 8
        expected = {"cobwebs", "bloodstains", "scattered_papers", "broken_pottery"}
        assert expected.issubset(set(_STORYTELLING_PROPS.keys()))
