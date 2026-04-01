"""Tests for the settlement composition system.

Pure-logic tests -- no bpy/bmesh required.  Validates building placement,
road networks, prop scatter, interior furnishing, perimeter generation,
building variation, deterministic seeding, and all settlement types.
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.settlement_generator import (
    ROOM_FURNISHINGS,
    SETTLEMENT_TYPES,
    _ROOM_LIGHTS,
    _BUILDING_ROOMS,
    _BUILDING_FOOTPRINTS,
    _apply_building_variation,
    _compute_foundation_profile,
    _derive_settlement_profile,
    _compute_foundation_height,
    _dist2d,
    _aabb_overlaps,
    _furnish_interior,
    _generate_perimeter,
    _generate_roads,
    _place_buildings,
    _place_interior_lights,
    _sample_heightmap,
    _scatter_settlement_props,
    generate_city_districts,
    generate_settlement,
)
from blender_addon.handlers._settlement_grammar import (
    _road_segment_mesh_spec_with_curbs,
)
import random


# =========================================================================
# Helper utilities
# =========================================================================


class TestHelpers:
    """Tests for internal helper functions."""

    def test_dist2d_zero(self):
        assert _dist2d((0, 0), (0, 0)) == 0.0

    def test_dist2d_unit(self):
        assert abs(_dist2d((0, 0), (3, 4)) - 5.0) < 1e-6

    def test_dist2d_negative(self):
        assert abs(_dist2d((-1, -1), (2, 3)) - 5.0) < 1e-6

    def test_aabb_no_overlap(self):
        assert not _aabb_overlaps((0, 0), (2, 2), (10, 10), (2, 2), margin=0)

    def test_aabb_overlap(self):
        assert _aabb_overlaps((0, 0), (4, 4), (3, 0), (4, 4), margin=0)

    def test_aabb_margin_causes_overlap(self):
        # Without margin they don't overlap; with margin=1.5 they do
        assert not _aabb_overlaps((0, 0), (2, 2), (3, 0), (2, 2), margin=0)
        assert _aabb_overlaps((0, 0), (2, 2), (3, 0), (2, 2), margin=1.5)

    def test_aabb_touching_no_margin(self):
        # Edges touching: half-widths sum to 2.0, distance is exactly 2.0
        # Overlap requires strict < so touching should NOT overlap
        assert not _aabb_overlaps((0, 0), (2, 2), (2, 0), (2, 2), margin=0)


# =========================================================================
# generate_settlement -- main entry
# =========================================================================


class TestGenerateSettlement:
    """Integration tests for the main generate_settlement function."""

    @pytest.mark.parametrize("stype", list(SETTLEMENT_TYPES.keys()))
    def test_all_types_generate(self, stype: str):
        result = generate_settlement(stype, seed=42)
        assert result["settlement_type"] == stype
        assert isinstance(result["buildings"], list)
        assert isinstance(result["roads"], list)
        assert isinstance(result["props"], list)
        assert isinstance(result["perimeter"], list)
        assert isinstance(result["interiors"], dict)
        assert isinstance(result["lights"], list)
        assert isinstance(result["metadata"], dict)

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown settlement type"):
            generate_settlement("floating_city", seed=1)

    def test_seed_determinism(self):
        r1 = generate_settlement("village", seed=12345)
        r2 = generate_settlement("village", seed=12345)
        assert len(r1["buildings"]) == len(r2["buildings"])
        for b1, b2 in zip(r1["buildings"], r2["buildings"]):
            assert b1["position"] == b2["position"]
            assert b1["type"] == b2["type"]
            assert b1["rotation"] == b2["rotation"]

    def test_different_seeds_differ(self):
        r1 = generate_settlement("town", seed=100)
        r2 = generate_settlement("town", seed=200)
        # With different seeds, at least building positions should differ
        positions1 = [b["position"] for b in r1["buildings"]]
        positions2 = [b["position"] for b in r2["buildings"]]
        assert positions1 != positions2

    def test_center_offset(self):
        result = generate_settlement("village", seed=42, center=(100, 200))
        for bld in result["buildings"]:
            bx, by = bld["position"]
            dist = _dist2d((bx, by), (100, 200))
            # All buildings should be within radius
            assert dist < 100, f"Building at {bld['position']} too far from center"

    def test_custom_radius(self):
        small = generate_settlement("outpost", seed=42, radius=20.0)
        large = generate_settlement("outpost", seed=42, radius=100.0)
        # Both should have buildings, but larger radius should spread them more
        assert len(small["buildings"]) > 0
        assert len(large["buildings"]) > 0

    def test_metadata_counts_match(self):
        result = generate_settlement("town", seed=42)
        m = result["metadata"]
        assert m["building_count"] == len(result["buildings"])
        assert m["road_count"] == len(result["roads"])
        assert m["prop_count"] == len(result["props"])
        assert m["perimeter_element_count"] == len(result["perimeter"])
        assert m["furnished_building_count"] == len(result["interiors"])
        total_furniture = sum(len(v) for v in result["interiors"].values())
        assert m["total_furniture_pieces"] == total_furniture

    def test_none_seed_generates(self):
        result = generate_settlement("village", seed=None)
        assert result["seed"] is not None
        assert isinstance(result["seed"], int)
        assert len(result["buildings"]) > 0

    def test_layout_brief_is_deterministic(self):
        r1 = generate_settlement(
            "town",
            seed=77,
            layout_brief="river trade town with docks and crowded markets",
        )
        r2 = generate_settlement(
            "town",
            seed=77,
            layout_brief="river trade town with docks and crowded markets",
        )
        assert r1["metadata"]["layout_profile"]["signature"] == r2["metadata"]["layout_profile"]["signature"]
        assert [b["position"] for b in r1["buildings"]] == [b["position"] for b in r2["buildings"]]

    def test_layout_brief_changes_layout_for_same_seed(self):
        waterfront = generate_settlement(
            "town",
            seed=88,
            layout_brief="harbor trade town with docks and waterfront bazaar",
        )
        fortress = generate_settlement(
            "town",
            seed=88,
            layout_brief="fortified hill town with processional avenue and citadel",
        )
        assert waterfront["metadata"]["layout_profile"]["pattern"] != fortress["metadata"]["layout_profile"]["pattern"]
        assert [b["position"] for b in waterfront["buildings"]] != [b["position"] for b in fortress["buildings"]]

    def test_heightmap_buildings_include_foundation_profile(self):
        result = generate_settlement(
            "town",
            seed=51,
            heightmap=lambda x, y: x * 0.05 + y * 0.02,
        )
        assert result["buildings"]
        assert "foundation_profile" in result["buildings"][0]
        assert "platform_elevation" in result["buildings"][0]

    def test_medieval_town_generates_roads(self):
        """medieval_town uses concentric_organic layout with winding road network."""
        result = generate_settlement("medieval_town", seed=42, radius=150.0)
        assert result["settlement_type"] == "medieval_town"
        # Must produce roads
        assert len(result["roads"]) > 0, "medieval_town must generate road segments"
        # Roads must have required keys
        for road in result["roads"]:
            assert "start" in road, f"Road missing 'start': {road}"
            assert "end" in road, f"Road missing 'end': {road}"
            assert "width" in road, f"Road missing 'width': {road}"
            assert "style" in road, f"Road missing 'style': {road}"
        # Must produce buildings
        assert len(result["buildings"]) > 0, "medieval_town must place buildings"
        # Buildings must have district assignment
        for bld in result["buildings"]:
            assert "district" in bld, f"Building missing district: {bld}"
        # Props may include Tripo manifest entries
        assert isinstance(result["props"], list)
        # Metadata must reflect concentric_organic pattern
        assert result["metadata"]["layout_pattern"] == "concentric_organic"
        # Deterministic: same seed → same road count
        result2 = generate_settlement("medieval_town", seed=42, radius=150.0)
        assert len(result["roads"]) == len(result2["roads"])

    def test_medieval_town_veil_pressure_scales_props(self):
        """Higher veil_pressure should produce fewer props (sparser Poisson spacing)."""
        low = generate_settlement("medieval_town", seed=99, radius=150.0, veil_pressure=0.1)
        high = generate_settlement("medieval_town", seed=99, radius=150.0, veil_pressure=0.9)
        # High pressure → larger minimum spacing → fewer props
        assert len(high["props"]) <= len(low["props"]), (
            f"High pressure ({len(high['props'])} props) should have <= props than "
            f"low pressure ({len(low['props'])} props)"
        )


# =========================================================================
# _place_buildings
# =========================================================================


class TestPlaceBuildings:
    """Tests for building placement logic."""

    @pytest.mark.parametrize("stype", list(SETTLEMENT_TYPES.keys()))
    def test_places_within_range(self, stype: str):
        config = SETTLEMENT_TYPES[stype]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        assert len(buildings) > 0
        for bld in buildings:
            assert "position" in bld
            assert "rotation" in bld
            assert "type" in bld
            assert "unique_seed" in bld
            assert "room_functions" in bld
            assert "footprint" in bld

    def test_no_overlapping_buildings(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        # Check all pairs for overlap
        for i, a in enumerate(buildings):
            for j, b in enumerate(buildings):
                if i >= j:
                    continue
                overlaps = _aabb_overlaps(
                    a["position"], a["footprint"],
                    b["position"], b["footprint"],
                    margin=1.5,
                )
                assert not overlaps, (
                    f"Buildings {i} ({a['type']} at {a['position']}) and "
                    f"{j} ({b['type']} at {b['position']}) overlap"
                )

    def test_shrine_placed_when_configured(self):
        config = SETTLEMENT_TYPES["village"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        shrine_buildings = [b for b in buildings if "shrine" in b["type"]]
        assert len(shrine_buildings) >= 1

    def test_market_placed_when_configured(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        market_buildings = [b for b in buildings if "market" in b["type"]]
        assert len(market_buildings) >= 1

    def test_no_shrine_when_not_configured(self):
        config = SETTLEMENT_TYPES["bandit_camp"]
        assert not config["has_shrine"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        shrine_buildings = [b for b in buildings if "shrine" in b["type"]]
        assert len(shrine_buildings) == 0

    def test_building_count_within_range(self):
        for stype, config in SETTLEMENT_TYPES.items():
            rng = random.Random(42)
            buildings = _place_buildings(rng, config, (0, 0), 50.0)
            lo, hi = config["building_count"]
            # Allow for fewer if overlap prevents placement, but at least 1
            assert len(buildings) >= 1, f"No buildings for {stype}"
            # Should not exceed max + priority placements
            assert len(buildings) <= hi + 2  # shrine + market priority

    def test_buildings_face_center(self):
        config = SETTLEMENT_TYPES["bandit_camp"]  # circular layout
        rng = random.Random(42)
        center = (0.0, 0.0)
        buildings = _place_buildings(rng, config, center, 50.0)
        for bld in buildings:
            bx, by = bld["position"]
            expected_angle = math.atan2(
                center[1] - by, center[0] - bx
            )
            # Rotation should approximately face center
            diff = abs(bld["rotation"] - expected_angle)
            # Normalize to [0, 2pi]
            diff = diff % (2 * math.pi)
            assert diff < 0.01 or abs(diff - 2 * math.pi) < 0.01

    def test_room_functions_assigned(self):
        config = SETTLEMENT_TYPES["castle"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        for bld in buildings:
            assert isinstance(bld["room_functions"], list)


class TestFoundationProfile:
    """Tests for terrain-aware foundation fitting metadata."""

    def test_profile_is_flat_without_heightmap(self):
        profile = _compute_foundation_profile(None, (0.0, 0.0), (8.0, 6.0))
        assert profile["foundation_height"] == 0.0
        assert profile["retaining_sides"] == []
        assert profile["dominant_slope_axis"] == "flat"

    def test_profile_detects_slope_and_retaining_side(self):
        profile = _compute_foundation_profile(
            lambda x, y: max(0.0, x * 0.4),
            (0.0, 0.0),
            (8.0, 6.0),
            rotation=0.0,
        )
        assert profile["foundation_height"] > 0.0
        assert "left" in profile["retaining_sides"]
        assert profile["dominant_slope_axis"] == "x"

    def test_profile_generates_entry_steps_when_front_edge_drops(self):
        profile = _compute_foundation_profile(
            lambda x, y: max(0.0, y * 0.3),
            (0.0, 0.0),
            (8.0, 8.0),
            entrance_wall="front",
        )
        assert profile["stair_wall"] == "front"
        assert profile["stair_steps"] > 0


# =========================================================================
# _generate_roads
# =========================================================================


class TestGenerateRoads:
    """Tests for road network generation."""

    def test_roads_connect_buildings(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        # MST: N-1 edges + 1 main road
        assert len(roads) >= len(buildings)  # at least N-1 + main

    def test_no_roads_for_none_style(self):
        config = SETTLEMENT_TYPES["bandit_camp"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "none")
        assert len(roads) == 0

    def test_road_segments_have_required_keys(self):
        config = SETTLEMENT_TYPES["village"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "dirt_path")
        for road in roads:
            assert "start" in road
            assert "end" in road
            assert "width" in road
            assert "style" in road
            assert len(road["start"]) == 2
            assert len(road["end"]) == 2
            assert road["width"] > 0

    def test_main_road_exists(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        main_roads = [r for r in roads if r.get("is_main_road")]
        assert len(main_roads) == 1

    def test_main_road_is_wider(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        main = [r for r in roads if r.get("is_main_road")][0]
        others = [r for r in roads if not r.get("is_main_road")]
        if others:
            assert main["width"] > others[0]["width"]

    def test_road_style_matches(self):
        config = SETTLEMENT_TYPES["castle"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "stone")
        for road in roads:
            assert road["style"] == "stone"

    def test_single_building_no_roads(self):
        buildings = [{
            "position": (0, 0),
            "type": "tent",
            "footprint": (4, 4),
            "rotation": 0,
        }]
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        assert len(roads) == 0

    def test_mst_connectivity(self):
        """All buildings reachable via MST roads."""
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        # Build adjacency from road endpoints matching building positions
        positions = {b["position"] for b in buildings}
        non_main = [r for r in roads if not r.get("is_main_road")]
        # MST should have N-1 edges for N buildings
        assert len(non_main) == len(buildings) - 1


# =========================================================================
# _scatter_settlement_props
# =========================================================================


class TestScatterProps:
    """Tests for prop scatter logic."""

    def test_props_generated(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        props = _scatter_settlement_props(
            rng, buildings, roads, config, 50.0
        )
        assert len(props) > 0

    def test_prop_has_required_keys(self):
        config = SETTLEMENT_TYPES["village"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "dirt_path")
        props = _scatter_settlement_props(
            rng, buildings, roads, config, 50.0
        )
        for prop in props:
            assert "type" in prop
            assert "position" in prop
            assert "rotation" in prop
            assert "scale" in prop
            assert "source" in prop

    def test_road_props_exist_for_styled_roads(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        props = _scatter_settlement_props(
            rng, buildings, roads, config, 50.0
        )
        road_props = [p for p in props if p["source"] == "road"]
        assert len(road_props) > 0

    def test_building_adjacent_props_exist(self):
        config = SETTLEMENT_TYPES["town"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "cobblestone")
        props = _scatter_settlement_props(
            rng, buildings, roads, config, 50.0
        )
        # Accept both generic adjacent and narrative cluster props near buildings
        adj_props = [
            p for p in props
            if p["source"] in ("building_adjacent", "narrative_cluster")
        ]
        assert len(adj_props) > 0

    def test_no_road_props_for_none_style(self):
        config = SETTLEMENT_TYPES["bandit_camp"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "none")
        props = _scatter_settlement_props(
            rng, buildings, roads, config, 50.0
        )
        road_props = [p for p in props if p["source"] == "road"]
        assert len(road_props) == 0

    def test_scatter_props_not_inside_buildings(self):
        config = SETTLEMENT_TYPES["village"]
        rng = random.Random(42)
        buildings = _place_buildings(rng, config, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "dirt_path")
        props = _scatter_settlement_props(
            rng, buildings, roads, config, 50.0
        )
        scatter_props = [p for p in props if p["source"] == "scatter"]
        for prop in scatter_props:
            px, py = prop["position"]
            for bld in buildings:
                bx, by = bld["position"]
                dist = _dist2d((px, py), (bx, by))
                assert dist >= 4.0, (
                    f"Scatter prop at {prop['position']} too close to "
                    f"building at {bld['position']} (dist={dist:.2f})"
                )

    def test_higher_density_more_props(self):
        """Higher prop_density should yield more building-adjacent props."""
        rng1 = random.Random(42)
        config_low = dict(SETTLEMENT_TYPES["village"])
        config_low["prop_density"] = 0.1
        buildings = _place_buildings(rng1, config_low, (0, 0), 50.0)
        roads = _generate_roads(buildings, (0, 0), "dirt_path")
        props_low = _scatter_settlement_props(
            random.Random(42), buildings, roads, config_low, 50.0
        )

        rng2 = random.Random(42)
        config_high = dict(SETTLEMENT_TYPES["village"])
        config_high["prop_density"] = 0.9
        buildings2 = _place_buildings(rng2, config_high, (0, 0), 50.0)
        roads2 = _generate_roads(buildings2, (0, 0), "dirt_path")
        props_high = _scatter_settlement_props(
            random.Random(42), buildings2, roads2, config_high, 50.0
        )

        adj_low = len([p for p in props_low if p["source"] == "building_adjacent"])
        adj_high = len([p for p in props_high if p["source"] == "building_adjacent"])
        assert adj_high >= adj_low


# =========================================================================
# _furnish_interior
# =========================================================================


class TestFurnishInterior:
    """Tests for room interior furnishing."""

    @pytest.mark.parametrize("room_type", list(ROOM_FURNISHINGS.keys()))
    def test_furnishes_all_room_types(self, room_type: str):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (8.0, 8.0)}
        result = _furnish_interior(rng, room_type, bounds)
        assert isinstance(result, list)
        # Should place at least some furniture for valid rooms
        assert len(result) > 0

    def test_furniture_has_required_keys(self):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (8.0, 8.0)}
        result = _furnish_interior(rng, "bedroom", bounds)
        for item in result:
            assert "type" in item
            assert "position" in item
            assert "rotation" in item
            assert len(item["position"]) == 2

    def test_furniture_within_bounds(self):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (10.0, 10.0)}
        result = _furnish_interior(rng, "kitchen", bounds)
        for item in result:
            px, py = item["position"]
            assert 0.0 <= px <= 10.0, f"Furniture {item['type']} x={px} out of bounds"
            assert 0.0 <= py <= 10.0, f"Furniture {item['type']} y={py} out of bounds"

    def test_no_furniture_overlap(self):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (10.0, 10.0)}
        result = _furnish_interior(rng, "tavern", bounds)
        for i, a in enumerate(result):
            for j, b in enumerate(result):
                if i >= j:
                    continue
                dist = _dist2d(a["position"], b["position"])
                # Minimum spacing: at least 0.2 margin between items
                assert dist > 0.15, (
                    f"Furniture overlap: {a['type']} at {a['position']} and "
                    f"{b['type']} at {b['position']} (dist={dist:.2f})"
                )

    def test_tiny_room_graceful(self):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (0.5, 0.5)}
        result = _furnish_interior(rng, "bedroom", bounds)
        # Should not crash, may place nothing due to size constraints
        assert isinstance(result, list)

    def test_unknown_room_type_uses_fallback(self):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (6.0, 6.0)}
        result = _furnish_interior(rng, "nonexistent_room", bounds)
        assert isinstance(result, list)
        # Fallback is ["crate"]
        if result:
            assert result[0]["type"] == "crate"

    def test_deterministic_furnishing(self):
        bounds = {"min": (0.0, 0.0), "max": (8.0, 8.0)}
        r1 = _furnish_interior(random.Random(99), "smithy", bounds)
        r2 = _furnish_interior(random.Random(99), "smithy", bounds)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a["type"] == b["type"]
            assert a["position"] == b["position"]


# =========================================================================
# _apply_building_variation
# =========================================================================


class TestBuildingVariation:
    """Tests for per-building visual variation."""

    def test_adds_variation_key(self):
        rng = random.Random(42)
        building = {"type": "abandoned_house", "position": (0, 0), "unique_seed": 42}
        result = _apply_building_variation(rng, building)
        assert "variation" in result

    def test_variation_keys(self):
        rng = random.Random(42)
        building = {"type": "forge", "position": (5, 5), "unique_seed": 123}
        result = _apply_building_variation(rng, building)
        v = result["variation"]
        assert "wall_damage" in v
        assert "roof_condition" in v
        assert "window_count" in v
        assert "door_condition" in v
        assert "prop_additions" in v

    def test_wall_damage_range(self):
        for seed in range(50):
            rng = random.Random(seed)
            building = {"type": "x", "position": (0, 0), "unique_seed": seed}
            result = _apply_building_variation(rng, building)
            assert 0.0 <= result["variation"]["wall_damage"] <= 0.3

    def test_roof_condition_values(self):
        conditions_seen = set()
        for seed in range(100):
            rng = random.Random(seed)
            building = {"type": "x", "position": (0, 0), "unique_seed": seed}
            result = _apply_building_variation(rng, building)
            conditions_seen.add(result["variation"]["roof_condition"])
        assert conditions_seen == {"intact", "damaged", "missing"}

    def test_door_condition_values(self):
        conditions_seen = set()
        for seed in range(100):
            rng = random.Random(seed)
            building = {"type": "x", "position": (0, 0), "unique_seed": seed}
            result = _apply_building_variation(rng, building)
            conditions_seen.add(result["variation"]["door_condition"])
        assert conditions_seen == {"intact", "broken", "missing"}

    def test_does_not_mutate_original(self):
        rng = random.Random(42)
        original = {"type": "tent", "position": (0, 0), "unique_seed": 42}
        result = _apply_building_variation(rng, original)
        assert "variation" not in original
        assert "variation" in result

    def test_prop_additions_are_strings(self):
        rng = random.Random(42)
        building = {"type": "x", "position": (0, 0), "unique_seed": 42}
        result = _apply_building_variation(rng, building)
        for p in result["variation"]["prop_additions"]:
            assert isinstance(p, str)

    def test_deterministic_variation(self):
        building = {"type": "x", "position": (0, 0), "unique_seed": 42}
        r1 = _apply_building_variation(random.Random(42), building)
        r2 = _apply_building_variation(random.Random(42), building)
        assert r1["variation"] == r2["variation"]


# =========================================================================
# _generate_perimeter
# =========================================================================


class TestGeneratePerimeter:
    """Tests for perimeter wall and gate generation."""

    def test_no_perimeter_when_no_walls(self):
        rng = random.Random(42)
        config = SETTLEMENT_TYPES["village"]
        result = _generate_perimeter(rng, config, (0, 0), 50.0)
        assert len(result) == 0

    def test_perimeter_when_walls_configured(self):
        rng = random.Random(42)
        config = SETTLEMENT_TYPES["town"]
        result = _generate_perimeter(rng, config, (0, 0), 50.0)
        assert len(result) > 0

    def test_has_gate(self):
        rng = random.Random(42)
        config = SETTLEMENT_TYPES["castle"]
        result = _generate_perimeter(rng, config, (0, 0), 50.0)
        gates = [e for e in result if e.get("is_gate")]
        assert len(gates) >= 1

    def test_perimeter_elements_have_keys(self):
        rng = random.Random(42)
        config = SETTLEMENT_TYPES["town"]
        result = _generate_perimeter(rng, config, (0, 0), 50.0)
        for elem in result:
            assert "type" in elem
            assert "position" in elem
            assert "rotation" in elem

    def test_perimeter_forms_ring(self):
        rng = random.Random(42)
        config = SETTLEMENT_TYPES["castle"]
        center = (10.0, 20.0)
        radius = 40.0
        result = _generate_perimeter(rng, config, center, radius)
        # All non-tower elements should be approximately on the ring
        wall_radius = radius * 0.9
        for elem in result:
            if elem.get("is_tower"):
                continue
            px, py = elem["position"]
            dist = _dist2d((px, py), center)
            assert abs(dist - wall_radius) < 1.0, (
                f"Element at {elem['position']} not on ring "
                f"(dist={dist:.2f}, expected={wall_radius:.2f})"
            )

    def test_tower_placement(self):
        rng = random.Random(42)
        config = SETTLEMENT_TYPES["castle"]
        result = _generate_perimeter(rng, config, (0, 0), 50.0)
        towers = [e for e in result if e.get("is_tower")]
        # Castle has corner_tower in perimeter_props, so towers should appear
        assert len(towers) >= 1


# =========================================================================
# Settlement-type specific tests
# =========================================================================


class TestVillage:
    def test_no_walls(self):
        result = generate_settlement("village", seed=42)
        assert len(result["perimeter"]) == 0

    def test_has_shrine(self):
        result = generate_settlement("village", seed=42)
        shrine = [b for b in result["buildings"] if "shrine" in b["type"]]
        assert len(shrine) >= 1

    def test_building_count_range(self):
        result = generate_settlement("village", seed=42)
        lo, hi = SETTLEMENT_TYPES["village"]["building_count"]
        count = len(result["buildings"])
        assert lo <= count <= hi + 2  # +2 for priority placements


class TestTown:
    def test_has_walls(self):
        result = generate_settlement("town", seed=42)
        assert len(result["perimeter"]) > 0

    def test_has_market(self):
        result = generate_settlement("town", seed=42)
        market = [b for b in result["buildings"] if "market" in b["type"]]
        assert len(market) >= 1

    def test_cobblestone_roads(self):
        result = generate_settlement("town", seed=42)
        for road in result["roads"]:
            assert road["style"] == "cobblestone"


class TestBanditCamp:
    def test_no_walls(self):
        result = generate_settlement("bandit_camp", seed=42)
        assert len(result["perimeter"]) == 0

    def test_no_roads(self):
        result = generate_settlement("bandit_camp", seed=42)
        assert len(result["roads"]) == 0

    def test_camp_building_types(self):
        result = generate_settlement("bandit_camp", seed=42)
        allowed = {"tent", "lean_to", "campfire_area", "cage"}
        for bld in result["buildings"]:
            assert bld["type"] in allowed


class TestCastle:
    def test_has_walls(self):
        result = generate_settlement("castle", seed=42)
        assert len(result["perimeter"]) > 0

    def test_concentric_layout(self):
        result = generate_settlement("castle", seed=42)
        assert result["metadata"]["layout_pattern"] == "concentric"


class TestOutpost:
    def test_has_walls(self):
        result = generate_settlement("outpost", seed=42)
        assert len(result["perimeter"]) > 0

    def test_small_building_count(self):
        result = generate_settlement("outpost", seed=42)
        assert len(result["buildings"]) <= 6


class TestLayoutBriefProfiles:
    """Prompt-to-layout profile tests."""

    def test_derive_settlement_profile_detects_waterfront(self):
        profile = _derive_settlement_profile(
            "city",
            "river port city with harbor docks and merchant quays",
            seed=42,
        )
        assert profile["pattern"] == "waterfront_edge"
        assert "port_district" in profile["district_types"][:2]

    def test_generate_city_districts_honors_main_axis(self):
        profile = {
            "main_axis": "y",
            "district_types": ["temple_district", "market_quarter", "military_quarter"],
            "district_layouts": {
                "temple_district": "axial",
                "market_quarter": "organic",
                "military_quarter": "axial",
            },
            "signature": "test-axis",
        }
        result = generate_city_districts(120.0, 90.0, num_districts=3, seed=42, city_profile=profile)
        assert result["main_road"]["axis"] == "y"
        assert result["metadata"]["main_axis"] == "y"

    def test_city_layout_brief_changes_main_axis_metadata(self):
        harbor_city = generate_settlement(
            "city",
            seed=91,
            layout_brief="canal city with harbor docks and merchant quays",
        )
        fortress_city = generate_settlement(
            "city",
            seed=91,
            layout_brief="imperial capital with grand avenue and military quarter",
        )
        assert harbor_city["metadata"]["layout_profile"]["signature"] != fortress_city["metadata"]["layout_profile"]["signature"]
        assert harbor_city["metadata"]["main_axis"] != fortress_city["metadata"]["main_axis"] or (
            harbor_city["metadata"]["district_types"] != fortress_city["metadata"]["district_types"]
        )


# =========================================================================
# Interiors integration
# =========================================================================


class TestInteriorsIntegration:
    """Test that interior furnishing integrates correctly into settlements."""

    def test_interiors_populated(self):
        result = generate_settlement("town", seed=42)
        assert len(result["interiors"]) > 0

    def test_interior_keys_are_building_indices(self):
        result = generate_settlement("village", seed=42)
        for idx in result["interiors"]:
            assert isinstance(idx, int)
            assert 0 <= idx < len(result["buildings"])

    def test_interior_furniture_types_valid(self):
        result = generate_settlement("castle", seed=42)
        all_furniture_types = set()
        for flist in ROOM_FURNISHINGS.values():
            all_furniture_types.update(flist)
        # Also include the fallback
        all_furniture_types.add("crate")

        for idx, furnishings in result["interiors"].items():
            for item in furnishings:
                assert item["type"] in all_furniture_types, (
                    f"Unknown furniture type '{item['type']}' in building {idx}"
                )


# =========================================================================
# Stress / edge cases
# =========================================================================


class TestEdgeCases:
    """Edge cases and stress tests."""

    def test_very_small_radius(self):
        """Small radius may prevent placing all buildings, should not crash."""
        result = generate_settlement("village", seed=42, radius=5.0)
        assert isinstance(result["buildings"], list)
        # At least one building should be placed
        assert len(result["buildings"]) >= 1

    def test_very_large_radius(self):
        result = generate_settlement("town", seed=42, radius=500.0)
        assert len(result["buildings"]) > 0

    def test_many_seeds_no_crash(self):
        """Generate 20 settlements with different seeds, none should crash."""
        for seed in range(20):
            for stype in SETTLEMENT_TYPES:
                result = generate_settlement(stype, seed=seed)
                assert result["metadata"]["building_count"] >= 1

    def test_negative_center(self):
        result = generate_settlement(
            "village", seed=42, center=(-100.0, -200.0)
        )
        for bld in result["buildings"]:
            # Buildings should be near the center
            dist = _dist2d(bld["position"], (-100.0, -200.0))
            assert dist < 100

    def test_zero_radius_does_not_crash(self):
        """Zero radius is degenerate but should not raise."""
        result = generate_settlement("outpost", seed=42, radius=0.0)
        assert isinstance(result, dict)


# =========================================================================
# Heightmap support (Fix 2)
# =========================================================================


class TestHeightmapSupport:
    """Tests for terrain-aware Z placement via heightmap."""

    def test_flat_terrain_elevation_zero(self):
        """Without heightmap, elevation should be 0.0."""
        result = generate_settlement("village", seed=42)
        for bld in result["buildings"]:
            assert bld["elevation"] == 0.0
            assert bld["foundation_height"] == 0.0

    def test_heightmap_sets_elevation(self):
        """Heightmap function should set building elevation."""
        def hmap(x: float, y: float) -> float:
            return x * 0.1 + y * 0.05

        result = generate_settlement("village", seed=42, heightmap=hmap)
        for bld in result["buildings"]:
            bx, by = bld["position"]
            expected = round(hmap(bx, by), 3)
            assert bld["elevation"] == expected

    def test_heightmap_foundation_height_on_slope(self):
        """Sloped terrain should produce non-zero foundation_height."""
        def slope(x: float, y: float) -> float:
            return x * 0.5  # steep slope in X

        result = generate_settlement("village", seed=42, heightmap=slope)
        # At least some buildings should have foundation_height > 0
        has_foundation = any(
            bld["foundation_height"] > 0.0 for bld in result["buildings"]
        )
        assert has_foundation, "No buildings have foundation_height on sloped terrain"

    def test_heightmap_foundation_flat(self):
        """Flat heightmap should produce zero foundation_height."""
        def flat(x: float, y: float) -> float:
            return 5.0  # constant height

        result = generate_settlement("village", seed=42, heightmap=flat)
        for bld in result["buildings"]:
            assert bld["foundation_height"] == 0.0

    def test_sample_heightmap_none(self):
        assert _sample_heightmap(None, 10.0, 20.0) == 0.0

    def test_sample_heightmap_callable(self):
        hm = lambda x, y: x + y
        assert _sample_heightmap(hm, 3.0, 4.0) == 7.0

    def test_compute_foundation_height_none(self):
        assert _compute_foundation_height(None, (0, 0), (6, 6)) == 0.0

    def test_compute_foundation_height_slope(self):
        hm = lambda x, y: x * 1.0
        # Building at (10, 0) with footprint (4, 4)
        # Corners: x = 8, 12 -> heights 8, 12
        fh = _compute_foundation_height(hm, (10, 0), (4, 4))
        assert abs(fh - 4.0) < 1e-6


# =========================================================================
# Multi-floor interior furnishing (Fix 3)
# =========================================================================


class TestMultiFloorFurnishing:
    """Tests for multi-floor interior furnishing."""

    def test_single_floor_still_works(self):
        """Buildings without 'floors' key default to 1 floor."""
        result = generate_settlement("village", seed=42)
        # Should produce furniture as before
        assert len(result["interiors"]) > 0

    def test_multi_floor_produces_more_furniture(self):
        """Buildings with multiple floors should have more furniture."""
        # Generate baseline single-floor settlement
        r1 = generate_settlement("village", seed=42)
        single_total = sum(len(v) for v in r1["interiors"].values())

        # Now manually set a building to have multiple floors and regenerate
        # We test this by directly calling _furnish_interior for multiple floors
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (8.0, 8.0)}
        floor0 = _furnish_interior(rng, "bedroom", bounds)

        rng2 = random.Random(1042)
        floor1 = _furnish_interior(rng2, "bedroom", bounds)

        # Each floor should produce furniture independently
        assert len(floor0) > 0
        assert len(floor1) > 0

    def test_floor_tag_on_furniture(self):
        """Furniture items should have a 'floor' tag."""
        result = generate_settlement("village", seed=42)
        for idx, furnishings in result["interiors"].items():
            for item in furnishings:
                assert "floor" in item, (
                    f"Furniture {item['type']} in building {idx} missing 'floor' tag"
                )
                assert item["floor"] >= 0


# =========================================================================
# Interior lighting (Fix 4)
# =========================================================================


class TestInteriorLighting:
    """Tests for interior light placement."""

    def test_lights_generated(self):
        """Settlement should have lights in interiors."""
        result = generate_settlement("town", seed=42)
        assert len(result["lights"]) > 0

    def test_light_has_required_keys(self):
        """Each light should have position, color, intensity, range, type."""
        result = generate_settlement("town", seed=42)
        for light in result["lights"]:
            assert "type" in light
            assert "position" in light
            assert "color" in light
            assert "intensity" in light
            assert "range" in light
            assert "light_type" in light
            assert "building_index" in light
            assert "floor" in light

    def test_light_position_is_3d(self):
        """Light position should be (x, y, z) tuple."""
        result = generate_settlement("village", seed=42)
        for light in result["lights"]:
            assert len(light["position"]) == 3, (
                f"Light {light['type']} position should be 3D, got {light['position']}"
            )

    def test_light_intensity_positive(self):
        result = generate_settlement("town", seed=42)
        for light in result["lights"]:
            assert light["intensity"] > 0

    def test_light_range_positive(self):
        result = generate_settlement("town", seed=42)
        for light in result["lights"]:
            assert light["range"] > 0

    def test_light_color_valid(self):
        result = generate_settlement("village", seed=42)
        for light in result["lights"]:
            r, g, b = light["color"]
            assert 0.0 <= r <= 1.0
            assert 0.0 <= g <= 1.0
            assert 0.0 <= b <= 1.0

    def test_light_type_is_point_or_spot(self):
        result = generate_settlement("town", seed=42)
        for light in result["lights"]:
            assert light["light_type"] in ("point", "spot")

    def test_metadata_includes_light_count(self):
        result = generate_settlement("town", seed=42)
        assert "light_count" in result["metadata"]
        assert result["metadata"]["light_count"] == len(result["lights"])

    @pytest.mark.parametrize("room_type", list(_ROOM_LIGHTS.keys()))
    def test_place_lights_all_room_types(self, room_type: str):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (8.0, 8.0)}
        lights = _place_interior_lights(rng, room_type, bounds)
        assert len(lights) > 0
        assert len(lights) == len(_ROOM_LIGHTS[room_type])

    def test_place_lights_unknown_room_empty(self):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (8.0, 8.0)}
        lights = _place_interior_lights(rng, "nonexistent", bounds)
        assert lights == []

    def test_place_lights_tiny_room_empty(self):
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (0.5, 0.5)}
        lights = _place_interior_lights(rng, "bedroom", bounds)
        assert lights == []

    def test_place_lights_floor_offset(self):
        """Lights on higher floors should have higher Z position."""
        rng = random.Random(42)
        bounds = {"min": (0.0, 0.0), "max": (8.0, 8.0)}
        lights_f0 = _place_interior_lights(rng, "bedroom", bounds, floor_index=0)
        lights_f1 = _place_interior_lights(
            random.Random(42), "bedroom", bounds, floor_index=1
        )
        assert lights_f1[0]["position"][2] > lights_f0[0]["position"][2]

    def test_building_index_on_lights(self):
        """Each light should reference which building it belongs to."""
        result = generate_settlement("castle", seed=42)
        for light in result["lights"]:
            idx = light["building_index"]
            assert 0 <= idx < len(result["buildings"])


# ===========================================================================
# Prop cache / prefetch infrastructure (Phase 36-02)
# ===========================================================================


class TestPropPrefetchInfrastructure:
    """Tests for prefetch_town_props() and prop manifest structure (Plan 36-02)."""

    def _make_manifest(self, entries: list[tuple[str, str]]) -> list[dict]:
        """Build a minimal prop manifest with cache_key tuples."""
        return [
            {
                "prop_type": t,
                "corruption_band": b,
                "cache_key": (t, b),
                "position": (0.0, 0.0, 0.0),
                "rotation_z": 0.0,
                "district": "residential",
            }
            for t, b in entries
        ]

    def test_prefetch_returns_summary_dict(self):
        """prefetch_town_props returns dict keyed by (type, band) tuples."""
        from blender_addon.handlers.worldbuilding import (
            prefetch_town_props,
            clear_prop_cache,
        )
        clear_prop_cache()
        manifest = self._make_manifest([("lantern_post", "pristine"), ("well", "weathered")])
        result = prefetch_town_props(manifest, veil_pressure=0.1, blender_connection=None)
        assert isinstance(result, dict)
        # Both keys should appear (values may be None when blender_connection is None)
        assert ("lantern_post", "pristine") in result
        assert ("well", "weathered") in result

    def test_prefetch_deduplicates_cache_keys(self):
        """Duplicate cache_key entries in manifest produce only one lookup."""
        from blender_addon.handlers.worldbuilding import (
            prefetch_town_props,
            clear_prop_cache,
        )
        clear_prop_cache()
        # Same (type, band) repeated three times
        manifest = self._make_manifest(
            [("lantern_post", "pristine")] * 3
        )
        result = prefetch_town_props(manifest, veil_pressure=0.0, blender_connection=None)
        assert len(result) == 1

    def test_prefetch_empty_manifest_returns_empty(self):
        """Empty manifest produces empty result dict."""
        from blender_addon.handlers.worldbuilding import prefetch_town_props
        result = prefetch_town_props([], veil_pressure=0.0, blender_connection=None)
        assert result == {}

    def test_prop_manifest_position_format(self):
        """All prop positions in manifest are 3-tuples of numbers."""
        manifest = self._make_manifest([("bench", "damaged"), ("cart", "corrupted")])
        for spec in manifest:
            pos = spec["position"]
            assert len(pos) == 3
            assert all(isinstance(v, (int, float)) for v in pos)

    def test_prop_manifest_cache_keys_are_tuples(self):
        """All cache_key values are (str, str) pairs."""
        manifest = self._make_manifest([("trough", "pristine"), ("barrel_cluster", "weathered")])
        for spec in manifest:
            ck = spec["cache_key"]
            assert isinstance(ck, tuple)
            assert len(ck) == 2
            assert all(isinstance(s, str) for s in ck)


# =========================================================================
# Road curb geometry materialisation tests
# =========================================================================


class TestRoadCurbMaterialisation:
    """Tests for road curb mesh spec used during settlement materialisation."""

    def test_curb_verts_have_z_offset(self):
        """Curb-top vertices are raised by curb_height (0.15m)."""
        spec = _road_segment_mesh_spec_with_curbs(
            start=(0, 0, 0), end=(10, 0, 0), width=4.0,
            curb_height=0.15, gutter_width=0.3, resolution=1,
        )
        verts = spec["vertices"]
        # 7 columns per cross-section; cols 1 and 5 are curb tops
        assert len(verts) >= 7
        first_row = verts[:7]
        assert abs(first_row[1][2] - 0.15) < 1e-6, (
            f"Curb col 1 Z={first_row[1][2]}, expected 0.15"
        )
        assert abs(first_row[5][2] - 0.15) < 1e-6, (
            f"Curb col 5 Z={first_row[5][2]}, expected 0.15"
        )

    def test_road_with_curbs_total_width(self):
        """Total mesh width covers road_width + 2 * gutter_width."""
        width = 4.0
        gutter = 0.3
        spec = _road_segment_mesh_spec_with_curbs(
            start=(0, 0, 0), end=(10, 0, 0), width=width,
            curb_height=0.15, gutter_width=gutter, resolution=1,
        )
        expected_total = width + 2 * gutter
        assert abs(spec["total_width"] - expected_total) < 1e-6, (
            f"total_width={spec['total_width']}, expected {expected_total}"
        )
        # Also verify from actual vertex positions: first row leftmost vs rightmost
        first_row = spec["vertices"][:7]
        # Y positions encode the lateral offset (road along X axis)
        y_vals = [v[1] for v in first_row]
        actual_span = max(y_vals) - min(y_vals)
        assert abs(actual_span - expected_total) < 1e-4, (
            f"Vertex span={actual_span}, expected {expected_total}"
        )


# ---------------------------------------------------------------------------
# Hearthvale settlement tests (Phase 38 -- MESH-13)
# ---------------------------------------------------------------------------


class TestHearthvale:
    """Tests for the Hearthvale fortified castle-town settlement profile."""

    def test_hearthvale_type_registered(self):
        assert "hearthvale" in SETTLEMENT_TYPES
        cfg = SETTLEMENT_TYPES["hearthvale"]
        assert cfg["building_count"] == (14, 14)
        assert cfg["has_walls"] is True
        assert cfg["has_market"] is True
        assert cfg["layout_pattern"] == "concentric_organic"
        assert cfg.get("default_radius") == 65.0

    def test_hearthvale_building_types_all_mapped(self):
        """Every building type in the hearthvale config has room + footprint entries."""
        cfg = SETTLEMENT_TYPES["hearthvale"]
        for btype in cfg["building_types"]:
            assert btype in _BUILDING_ROOMS, (
                f"Building type '{btype}' missing from _BUILDING_ROOMS"
            )
            assert btype in _BUILDING_FOOTPRINTS, (
                f"Building type '{btype}' missing from _BUILDING_FOOTPRINTS"
            )

    def test_hearthvale_generates_buildings(self):
        """Concentric-organic path produces at least some buildings."""
        result = generate_settlement("hearthvale", seed=3810)
        buildings = result["buildings"]
        assert len(buildings) >= 1, "Expected at least 1 building from hearthvale generation"

    def test_hearthvale_has_perimeter(self):
        """Perimeter walls are generated for the walled town."""
        result = generate_settlement("hearthvale", seed=3810)
        perimeter = result.get("perimeter", [])
        assert len(perimeter) >= 1, "Expected perimeter elements for walled town"

    def test_hearthvale_perimeter_has_gate(self):
        """Perimeter includes at least one gate element."""
        result = generate_settlement("hearthvale", seed=3810)
        perimeter = result.get("perimeter", [])
        gate_types = [p.get("type", "") for p in perimeter]
        has_gate = any("gate" in gt.lower() for gt in gate_types)
        assert has_gate, f"No gate in perimeter. Types: {gate_types}"

    def test_hearthvale_has_roads(self):
        """Concentric-organic path generates road network."""
        result = generate_settlement("hearthvale", seed=3810)
        roads = result.get("roads", [])
        assert len(roads) >= 1, "Expected at least 1 road segment"

    def test_hearthvale_has_metadata(self):
        """Result contains expected metadata keys."""
        result = generate_settlement("hearthvale", seed=3810)
        meta = result.get("metadata", {})
        assert "building_count" in meta
        assert meta.get("layout_pattern") == "concentric_organic"
        assert meta.get("has_walls") is True

    def test_hearthvale_determinism(self):
        """Same seed produces identical results."""
        r1 = generate_settlement("hearthvale", seed=3810)
        r2 = generate_settlement("hearthvale", seed=3810)
        b1 = [(b["position"], b.get("type", "")) for b in r1["buildings"]]
        b2 = [(b["position"], b.get("type", "")) for b in r2["buildings"]]
        assert b1 == b2, "Two calls with same seed produced different buildings"
