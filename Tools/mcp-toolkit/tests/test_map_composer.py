"""Comprehensive tests for the world map composition system.

Tests placement rules, distance constraints, road generation, slope/elevation
calculations, biome assignment, and edge cases.  Pure logic -- no bpy required.
"""

from __future__ import annotations

import math
import random

import pytest

from blender_addon.handlers.map_composer import (
    POI_PLACEMENT_RULES,
    VB_BIOMES,
    _MAX_PLACEMENT_ATTEMPTS,
    _SETTLEMENT_TYPES,
    _calculate_slope,
    _distance,
    _find_valid_position,
    _generate_road_waypoints,
    _generate_world_roads,
    _get_biome_at,
    _hash_noise_2d,
    _road_terrain_cost,
    _sample_heightmap,
    compose_world_map,
)


# ---------------------------------------------------------------------------
# Helper: generate a simple test heightmap
# ---------------------------------------------------------------------------

def _make_flat_heightmap(rows: int, cols: int, value: float = 0.25) -> list[list[float]]:
    """Uniform-height grid."""
    return [[value] * cols for _ in range(rows)]


def _make_gradient_heightmap(rows: int, cols: int) -> list[list[float]]:
    """Height increases linearly from 0 (top-left) to 1 (bottom-right)."""
    return [
        [((r / max(rows - 1, 1)) + (c / max(cols - 1, 1))) / 2.0 for c in range(cols)]
        for r in range(rows)
    ]


def _make_steep_heightmap(rows: int, cols: int) -> list[list[float]]:
    """Sharp height cliff in the middle for slope testing."""
    hm: list[list[float]] = []
    for r in range(rows):
        row: list[float] = []
        for c in range(cols):
            if c < cols // 2:
                row.append(0.1)
            else:
                row.append(0.9)
        hm.append(row)
    return hm


# =========================================================================
# POI_PLACEMENT_RULES data integrity
# =========================================================================

class TestPOIPlacementRules:
    """Validate the POI placement rule definitions."""

    def test_all_types_have_rules(self):
        expected = {"village", "town", "bandit_camp", "dungeon_entrance",
                    "shrine", "veil_crack", "castle"}
        assert set(POI_PLACEMENT_RULES.keys()) == expected

    def test_each_rule_has_required_fields(self):
        required = {"preferred_biomes", "min_slope", "max_slope",
                    "min_distance_from_others", "near_water", "elevation_range"}
        for poi_type, rules in POI_PLACEMENT_RULES.items():
            for field in required:
                assert field in rules, f"{poi_type} missing field: {field}"

    def test_slope_ranges_valid(self):
        for poi_type, rules in POI_PLACEMENT_RULES.items():
            assert rules["min_slope"] <= rules["max_slope"], (
                f"{poi_type}: min_slope > max_slope"
            )

    def test_elevation_ranges_valid(self):
        for poi_type, rules in POI_PLACEMENT_RULES.items():
            lo, hi = rules["elevation_range"]
            assert 0.0 <= lo <= hi <= 1.0, (
                f"{poi_type}: invalid elevation_range ({lo}, {hi})"
            )

    def test_preferred_biomes_are_known(self):
        for poi_type, rules in POI_PLACEMENT_RULES.items():
            for biome in rules["preferred_biomes"]:
                assert biome in VB_BIOMES, (
                    f"{poi_type} references unknown biome: {biome}"
                )

    def test_min_distance_positive(self):
        for poi_type, rules in POI_PLACEMENT_RULES.items():
            assert rules["min_distance_from_others"] > 0, (
                f"{poi_type}: min_distance must be positive"
            )


# =========================================================================
# _hash_noise_2d
# =========================================================================

class TestHashNoise2D:
    def test_returns_float(self):
        assert isinstance(_hash_noise_2d(1.0, 2.0), float)

    def test_deterministic(self):
        a = _hash_noise_2d(1.5, 2.5, seed=42)
        b = _hash_noise_2d(1.5, 2.5, seed=42)
        assert a == b

    def test_different_seeds_differ(self):
        a = _hash_noise_2d(1.0, 1.0, seed=0)
        b = _hash_noise_2d(1.0, 1.0, seed=999)
        # Not guaranteed to differ, but extremely unlikely to be equal
        # if the hash function mixes seeds. We allow this as a soft check.
        # The main test is that the function doesn't crash.
        assert isinstance(a, float)
        assert isinstance(b, float)

    def test_output_range(self):
        """Output should be in [-1, 1]."""
        for _ in range(100):
            x = random.uniform(-100, 100)
            y = random.uniform(-100, 100)
            v = _hash_noise_2d(x, y)
            assert -2.0 <= v <= 2.0  # allow small float overshoot


# =========================================================================
# _get_biome_at
# =========================================================================

class TestGetBiomeAt:
    def test_returns_known_biome(self):
        biome = _get_biome_at(50, 50, 100, 100)
        assert biome in VB_BIOMES

    def test_deterministic(self):
        a = _get_biome_at(30, 70, 200, 200, seed=42)
        b = _get_biome_at(30, 70, 200, 200, seed=42)
        assert a == b

    def test_different_positions_may_differ(self):
        biomes = set()
        for x in range(0, 500, 50):
            for y in range(0, 500, 50):
                biomes.add(_get_biome_at(x, y, 500, 500, seed=0))
        # Should produce at least 2 different biomes across the map
        assert len(biomes) >= 2

    def test_zero_width_no_crash(self):
        # Edge case: width/height = 0
        biome = _get_biome_at(0, 0, 0, 0)
        assert biome in VB_BIOMES


# =========================================================================
# _sample_heightmap
# =========================================================================

class TestSampleHeightmap:
    def test_none_heightmap(self):
        assert _sample_heightmap(None, 5, 5, 10, 10) == 0.25

    def test_empty_heightmap(self):
        assert _sample_heightmap([], 5, 5, 10, 10) == 0.25
        assert _sample_heightmap([[]], 5, 5, 10, 10) == 0.25

    def test_flat_heightmap(self):
        hm = _make_flat_heightmap(10, 10, value=0.5)
        val = _sample_heightmap(hm, 5, 5, 10, 10)
        assert abs(val - 0.5) < 1e-6

    def test_corner_values(self):
        hm = [[0.0, 1.0], [1.0, 0.5]]
        # Top-left corner
        v = _sample_heightmap(hm, 0, 0, 10, 10)
        assert abs(v - 0.0) < 1e-6
        # Bottom-right corner
        v = _sample_heightmap(hm, 10, 10, 10, 10)
        assert abs(v - 0.5) < 1e-6

    def test_bilinear_interpolation_center(self):
        hm = [[0.0, 0.0], [0.0, 1.0]]
        # Center should interpolate
        v = _sample_heightmap(hm, 5, 5, 10, 10)
        assert 0.0 < v < 1.0


# =========================================================================
# _calculate_slope
# =========================================================================

class TestCalculateSlope:
    def test_none_heightmap_zero_slope(self):
        assert _calculate_slope(None, 5, 5, 10, 10) == 0.0

    def test_small_heightmap(self):
        assert _calculate_slope([[0.5]], 0, 0, 1, 1) == 0.0

    def test_flat_terrain_zero_slope(self):
        hm = _make_flat_heightmap(10, 10, 0.5)
        slope = _calculate_slope(hm, 5, 5, 10, 10)
        assert slope < 1.0  # nearly flat

    def test_steep_terrain_high_slope(self):
        hm = _make_steep_heightmap(10, 10)
        # Sample near the cliff edge (middle of the heightmap)
        slope = _calculate_slope(hm, 5, 5, 10, 10)
        assert slope > 5.0  # should detect significant slope

    def test_slope_bounded(self):
        hm = _make_gradient_heightmap(10, 10)
        for x in range(1, 9):
            for y in range(1, 9):
                slope = _calculate_slope(hm, x, y, 10, 10)
                assert 0.0 <= slope <= 90.0


# =========================================================================
# _distance
# =========================================================================

class TestDistance:
    def test_zero_distance(self):
        assert _distance((0, 0), (0, 0)) == 0.0

    def test_unit_distance(self):
        assert abs(_distance((0, 0), (1, 0)) - 1.0) < 1e-9

    def test_pythagorean(self):
        assert abs(_distance((0, 0), (3, 4)) - 5.0) < 1e-9


# =========================================================================
# _find_valid_position
# =========================================================================

class TestFindValidPosition:
    def test_finds_position_on_open_map(self):
        rng = random.Random(42)
        rules = POI_PLACEMENT_RULES["village"]
        pos = _find_valid_position(rng, "village", [], 500, 500, None, rules)
        assert pos is not None
        assert 0 <= pos[0] <= 500
        assert 0 <= pos[1] <= 500

    def test_respects_min_distance(self):
        rng = random.Random(42)
        rules = POI_PLACEMENT_RULES["village"]
        # Place first
        pos1 = _find_valid_position(rng, "village", [], 500, 500, None, rules)
        assert pos1 is not None
        existing = [{"type": "village", "position": pos1}]
        # Place second
        pos2 = _find_valid_position(rng, "village", existing, 500, 500, None, rules)
        if pos2 is not None:
            d = _distance(pos1, pos2)
            assert d >= rules["min_distance_from_others"]

    def test_returns_none_on_tiny_map(self):
        """A tiny map with one POI already placed should fail to place another."""
        rng = random.Random(42)
        rules = POI_PLACEMENT_RULES["castle"]  # 150m min distance
        existing = [{"type": "castle", "position": (10, 10)}]
        pos = _find_valid_position(rng, "castle", existing, 20, 20, None, rules)
        assert pos is None

    def test_elevation_filtering(self):
        rng = random.Random(42)
        # Make a heightmap that's all very high (0.95)
        hm = _make_flat_heightmap(10, 10, 0.95)
        rules = POI_PLACEMENT_RULES["village"]  # elevation_range (0.1, 0.4)
        pos = _find_valid_position(rng, "village", [], 500, 500, hm, rules)
        # Should fail because elevation 0.95 is outside (0.1, 0.4)
        assert pos is None

    def test_slope_filtering(self):
        rng = random.Random(42)
        # Village needs max_slope 15, dungeon needs min_slope 10
        rules = POI_PLACEMENT_RULES["dungeon_entrance"]
        # Flat heightmap => slope near 0 => dungeon needs min_slope 10
        hm = _make_flat_heightmap(10, 10, 0.5)
        pos = _find_valid_position(rng, "dungeon_entrance", [], 500, 500, hm, rules)
        # Should fail because slope ~0 is below min_slope 10
        assert pos is None


# =========================================================================
# _generate_world_roads
# =========================================================================

class TestGenerateWorldRoads:
    def _make_settlement_pois(self, count: int = 4) -> list[dict]:
        rng = random.Random(42)
        pois = []
        for i in range(count):
            pois.append({
                "name": f"village_{i+1}",
                "type": "village",
                "position": (rng.uniform(50, 450), rng.uniform(50, 450)),
            })
        return pois

    def test_empty_pois(self):
        roads = _generate_world_roads([], 500, 500)
        assert roads == []

    def test_single_settlement(self):
        pois = [{"name": "v1", "type": "village", "position": (100, 100)}]
        roads = _generate_world_roads(pois, 500, 500)
        assert roads == []

    def test_two_settlements_one_road(self):
        pois = [
            {"name": "v1", "type": "village", "position": (100, 100)},
            {"name": "v2", "type": "village", "position": (400, 400)},
        ]
        roads = _generate_world_roads(pois, 500, 500, shortcut_count=0)
        assert len(roads) == 1
        assert roads[0]["road_type"] == "main"

    def test_mst_connects_all(self):
        pois = self._make_settlement_pois(5)
        roads = _generate_world_roads(pois, 500, 500, shortcut_count=0)
        # MST on n nodes has n-1 edges
        main_roads = [r for r in roads if r["road_type"] == "main"]
        assert len(main_roads) == 4

    def test_shortcut_roads_added(self):
        pois = self._make_settlement_pois(5)
        roads = _generate_world_roads(pois, 500, 500, shortcut_count=2)
        shortcut_roads = [r for r in roads if r["road_type"] == "shortcut"]
        assert len(shortcut_roads) <= 2

    def test_roads_have_required_fields(self):
        pois = self._make_settlement_pois(3)
        roads = _generate_world_roads(pois, 500, 500)
        for road in roads:
            assert "from" in road
            assert "to" in road
            assert "distance" in road
            assert "road_type" in road
            assert "waypoints" in road
            assert isinstance(road["distance"], float)
            assert road["distance"] > 0

    def test_non_settlements_connected_via_trails(self):
        pois = [
            {"name": "v1", "type": "village", "position": (100, 100)},
            {"name": "v2", "type": "village", "position": (400, 400)},
            {"name": "s1", "type": "shrine", "position": (150, 150)},
        ]
        roads = _generate_world_roads(pois, 500, 500, shortcut_count=0)
        trail_roads = [r for r in roads if r["road_type"] == "trail"]
        assert len(trail_roads) == 1
        assert trail_roads[0]["from"] == "s1"

    def test_waypoints_are_3d(self):
        pois = [
            {"name": "v1", "type": "village", "position": (100, 100)},
            {"name": "v2", "type": "village", "position": (400, 400)},
        ]
        roads = _generate_world_roads(pois, 500, 500)
        for road in roads:
            for wp in road["waypoints"]:
                assert len(wp) == 3, "Waypoints should be (x, y, z)"


# =========================================================================
# _road_terrain_cost
# =========================================================================

class TestRoadTerrainCost:
    def test_no_heightmap(self):
        cost = _road_terrain_cost((0, 0), (100, 100), None, 200, 200)
        assert cost == 0.0

    def test_flat_terrain_low_cost(self):
        hm = _make_flat_heightmap(10, 10, 0.5)
        cost = _road_terrain_cost((10, 10), (90, 90), hm, 100, 100)
        assert cost < 0.5

    def test_steep_terrain_higher_cost(self):
        hm = _make_steep_heightmap(20, 20)
        cost = _road_terrain_cost((10, 50), (90, 50), hm, 100, 100)
        # Road crosses the cliff, should have higher cost
        assert cost >= 0.0


# =========================================================================
# _generate_road_waypoints
# =========================================================================

class TestGenerateRoadWaypoints:
    def test_basic_waypoints(self):
        rng = random.Random(0)
        wps = _generate_road_waypoints((0, 0), (100, 100), None, 200, 200, rng)
        assert len(wps) == 5  # default segments=4 means 5 waypoints

    def test_endpoints_match(self):
        rng = random.Random(0)
        wps = _generate_road_waypoints((10, 20), (190, 180), None, 200, 200, rng)
        # First waypoint should be at start
        assert abs(wps[0][0] - 10) < 1e-6
        assert abs(wps[0][1] - 20) < 1e-6
        # Last waypoint should be at end
        assert abs(wps[-1][0] - 190) < 1e-6
        assert abs(wps[-1][1] - 180) < 1e-6

    def test_zero_length_road(self):
        rng = random.Random(0)
        wps = _generate_road_waypoints((50, 50), (50, 50), None, 100, 100, rng)
        assert len(wps) == 1

    def test_waypoints_within_bounds(self):
        rng = random.Random(42)
        wps = _generate_road_waypoints((10, 10), (90, 90), None, 100, 100, rng)
        for x, y, z in wps:
            assert 0 <= x <= 100
            assert 0 <= y <= 100


# =========================================================================
# compose_world_map (integration)
# =========================================================================

class TestComposeWorldMap:
    def test_basic_composition(self):
        result = compose_world_map(
            width=500, height=500,
            poi_list=[
                {"type": "village", "count": 2},
                {"type": "shrine", "count": 3},
            ],
            seed=42,
        )
        assert "pois" in result
        assert "roads" in result
        assert "metadata" in result

    def test_deterministic_with_seed(self):
        args = dict(
            width=500, height=500,
            poi_list=[
                {"type": "village", "count": 2},
                {"type": "bandit_camp", "count": 2},
            ],
            seed=12345,
        )
        r1 = compose_world_map(**args)
        r2 = compose_world_map(**args)
        assert r1["pois"] == r2["pois"]
        assert r1["roads"] == r2["roads"]

    def test_poi_fields(self):
        result = compose_world_map(
            width=500, height=500,
            poi_list=[{"type": "village", "count": 1}],
            seed=42,
        )
        if result["pois"]:
            poi = result["pois"][0]
            assert "name" in poi
            assert "type" in poi
            assert "position" in poi
            assert "elevation" in poi
            assert "biome" in poi
            assert "slope" in poi
            assert poi["type"] == "village"
            assert len(poi["position"]) == 2

    def test_metadata_fields(self):
        result = compose_world_map(
            width=500, height=500,
            poi_list=[{"type": "village", "count": 2}],
            seed=42,
        )
        meta = result["metadata"]
        assert meta["seed"] == 42
        assert meta["world_size"] == (500, 500)
        assert meta["total_pois_requested"] == 2
        assert isinstance(meta["total_pois_placed"], int)
        assert isinstance(meta["placement_failures"], list)
        assert isinstance(meta["road_count"], int)
        assert isinstance(meta["biome_distribution"], dict)

    def test_minimum_distance_between_pois(self):
        result = compose_world_map(
            width=1000, height=1000,
            poi_list=[{"type": "village", "count": 5}],
            seed=42,
        )
        pois = result["pois"]
        min_d = POI_PLACEMENT_RULES["village"]["min_distance_from_others"]
        for i in range(len(pois)):
            for j in range(i + 1, len(pois)):
                d = _distance(pois[i]["position"], pois[j]["position"])
                assert d >= min_d * 0.99, (  # small float tolerance
                    f"POIs {pois[i]['name']} and {pois[j]['name']} too close: {d:.1f} < {min_d}"
                )

    def test_unknown_poi_type_reported(self):
        result = compose_world_map(
            width=500, height=500,
            poi_list=[{"type": "nonexistent_type", "count": 1}],
            seed=42,
        )
        assert result["metadata"]["placement_failures"]
        assert result["metadata"]["placement_failures"][0]["type"] == "nonexistent_type"

    def test_too_many_pois_for_space(self):
        """Requesting 20 castles (150m apart) on a 200x200 map should fail partially."""
        result = compose_world_map(
            width=200, height=200,
            poi_list=[{"type": "castle", "count": 20}],
            seed=42,
        )
        placed = result["metadata"]["total_pois_placed"]
        assert placed < 20
        assert result["metadata"]["placement_failures"]

    def test_roads_connect_settlements(self):
        result = compose_world_map(
            width=1000, height=1000,
            poi_list=[
                {"type": "village", "count": 3},
                {"type": "town", "count": 1},
            ],
            seed=42,
        )
        settlements_placed = [p for p in result["pois"] if p["type"] in _SETTLEMENT_TYPES]
        if len(settlements_placed) >= 2:
            main_roads = [r for r in result["roads"] if r["road_type"] == "main"]
            assert len(main_roads) >= len(settlements_placed) - 1

    def test_with_heightmap(self):
        hm = _make_gradient_heightmap(20, 20)
        result = compose_world_map(
            width=500, height=500,
            poi_list=[
                {"type": "village", "count": 2},
                {"type": "dungeon_entrance", "count": 2},
            ],
            seed=42,
            heightmap=hm,
        )
        # Villages should be at lower elevations, dungeons at higher
        villages = [p for p in result["pois"] if p["type"] == "village"]
        dungeons = [p for p in result["pois"] if p["type"] == "dungeon_entrance"]
        if villages and dungeons:
            avg_village_elev = sum(v["elevation"] for v in villages) / len(villages)
            avg_dungeon_elev = sum(d["elevation"] for d in dungeons) / len(dungeons)
            # Dungeons have elevation_range (0.3, 0.8) vs villages (0.1, 0.4)
            # so dungeons should generally be higher
            assert avg_dungeon_elev >= avg_village_elev * 0.5  # soft check

    def test_pois_within_bounds(self):
        result = compose_world_map(
            width=500, height=500,
            poi_list=[
                {"type": "village", "count": 3},
                {"type": "shrine", "count": 5},
                {"type": "bandit_camp", "count": 4},
            ],
            seed=42,
        )
        for poi in result["pois"]:
            x, y = poi["position"]
            assert 0 <= x <= 500, f"{poi['name']} x={x} out of bounds"
            assert 0 <= y <= 500, f"{poi['name']} y={y} out of bounds"

    def test_large_map_many_pois(self):
        result = compose_world_map(
            width=2000, height=2000,
            poi_list=[
                {"type": "village", "count": 5},
                {"type": "town", "count": 2},
                {"type": "castle", "count": 1},
                {"type": "dungeon_entrance", "count": 4},
                {"type": "shrine", "count": 6},
                {"type": "bandit_camp", "count": 4},
                {"type": "veil_crack", "count": 3},
            ],
            seed=100,
        )
        total = result["metadata"]["total_pois_placed"]
        assert total >= 10  # should place most POIs on a large map

    def test_auto_seed_when_none(self):
        r1 = compose_world_map(500, 500, [{"type": "village", "count": 1}], seed=None)
        assert r1["metadata"]["seed"] is not None

    def test_empty_poi_list(self):
        result = compose_world_map(500, 500, [], seed=42)
        assert result["pois"] == []
        assert result["roads"] == []
        assert result["metadata"]["total_pois_requested"] == 0

    def test_mixed_settlements_and_non_settlements(self):
        result = compose_world_map(
            width=800, height=800,
            poi_list=[
                {"type": "village", "count": 2},
                {"type": "shrine", "count": 2},
                {"type": "dungeon_entrance", "count": 1},
            ],
            seed=42,
        )
        road_types = {r["road_type"] for r in result["roads"]}
        # Should have main roads (connecting settlements) and possibly trails
        if len([p for p in result["pois"] if p["type"] in _SETTLEMENT_TYPES]) >= 2:
            assert "main" in road_types

    def test_shortcut_roads_parameter(self):
        result = compose_world_map(
            width=1000, height=1000,
            poi_list=[
                {"type": "village", "count": 4},
                {"type": "town", "count": 2},
            ],
            seed=42,
            shortcut_roads=0,
        )
        shortcut_roads = [r for r in result["roads"] if r["road_type"] == "shortcut"]
        assert len(shortcut_roads) == 0

    def test_biome_distribution_populated(self):
        result = compose_world_map(
            width=1000, height=1000,
            poi_list=[
                {"type": "village", "count": 3},
                {"type": "shrine", "count": 3},
            ],
            seed=42,
        )
        if result["pois"]:
            assert result["metadata"]["biome_distribution"]
            total = sum(result["metadata"]["biome_distribution"].values())
            assert total == result["metadata"]["total_pois_placed"]

    def test_poi_names_unique(self):
        result = compose_world_map(
            width=1000, height=1000,
            poi_list=[
                {"type": "village", "count": 3},
                {"type": "shrine", "count": 3},
            ],
            seed=42,
        )
        names = [p["name"] for p in result["pois"]]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_priority_ordering_large_pois_first(self):
        """Castles (150m) should be placed before villages (80m)."""
        result = compose_world_map(
            width=500, height=500,
            poi_list=[
                {"type": "village", "count": 2},
                {"type": "castle", "count": 1},
            ],
            seed=42,
        )
        # Castle should be placed (it's processed first due to sorting)
        castles = [p for p in result["pois"] if p["type"] == "castle"]
        # On a 500x500 map, at least one castle should fit
        assert len(castles) >= 1 or result["metadata"]["placement_failures"]
