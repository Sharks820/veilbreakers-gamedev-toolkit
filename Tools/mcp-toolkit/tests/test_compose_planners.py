"""Regression tests for compose_map / compose_interior planning helpers."""

from __future__ import annotations

import math

from veilbreakers_mcp.blender_server import (
    _build_location_generation_params,
    _lighting_preset_for_biome,
    _map_point_to_terrain_cell,
    _normalize_map_point,
    _normalize_vegetation_rules,
    _plan_interior_rooms,
    _plan_map_location_anchors,
    _resolve_map_generation_budget,
    _should_validate_world_mesh,
    _world_quality_family,
    _world_quality_prefixes,
)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


class TestMapPlacementPlanning:
    def test_normalize_map_point_converts_unsigned_space(self):
        point = _normalize_map_point((150.0, 50.0), terrain_size=200.0)
        assert point == (50.0, -50.0)

    def test_map_point_to_terrain_cell_converts_centered_space(self):
        point = _map_point_to_terrain_cell((-100.0, 100.0), terrain_size=200.0, resolution=201)
        assert point == (200, 0)

    def test_map_point_to_terrain_cell_converts_unsigned_space(self):
        point = _map_point_to_terrain_cell((150.0, 50.0), terrain_size=200.0, resolution=201)
        assert point == (50, 150)

    def test_anchor_planner_keeps_locations_apart(self):
        placements = _plan_map_location_anchors({
            "terrain": {"size": 220.0},
            "locations": [
                {"name": "Town", "type": "town", "districts": 4},
                {"name": "Castle", "type": "castle", "outer_size": 44},
                {"name": "Dungeon", "type": "dungeon", "grid_size": 64},
            ],
        })

        assert len(placements) == 3
        for idx, current in enumerate(placements):
            cx, cy = current["anchor"]
            assert -110.0 <= cx <= 110.0
            assert -110.0 <= cy <= 110.0
            for other in placements[idx + 1:]:
                min_distance = current["radius"] + other["radius"] + 6.0
                assert _distance(current["anchor"], other["anchor"]) >= min_distance

    def test_anchor_planner_preserves_explicit_positions(self):
        placements = _plan_map_location_anchors({
            "terrain": {"size": 200.0},
            "locations": [
                {"name": "Gate", "type": "building", "position": [140.0, 80.0]},
            ],
        })

        assert placements[0]["anchor"] == (40.0, -20.0)

    def test_budget_defaults_to_balanced_pc_for_regular_region(self):
        budget = _resolve_map_generation_budget({
            "terrain": {"size": 220.0},
            "locations": [{"type": "town"}, {"type": "castle"}],
        })

        assert budget["profile"] == "balanced_pc"
        assert budget["terrain_resolution_cap"] == 384
        assert budget["vegetation_max_instances"] == 4500

    def test_budget_switches_to_large_world_for_dense_large_map(self):
        budget = _resolve_map_generation_budget({
            "terrain": {"size": 480.0},
            "locations": [{"type": "building"} for _ in range(9)],
        })

        assert budget["profile"] == "large_world"
        assert budget["terrain_resolution_cap"] == 256
        assert budget["prop_density_scale"] == 0.7

    def test_location_generation_params_preserve_layout_brief_and_site_profile(self):
        params = _build_location_generation_params(
            {
                "name": "Rivergate",
                "type": "town",
                "districts": 5,
                "grid_size": 40,
                "layout_brief": "harbor trade town with docks and merchant quays",
            },
            map_spec={
                "layout_brief": "grim canal city with fortress spine",
                "theme": "dark fantasy waterfront",
            },
            map_seed=42,
            index=1,
        )

        assert params["name"] == "Rivergate"
        assert params["num_districts"] == 5
        assert params["width"] == 40
        assert params["layout_brief"] == "harbor trade town with docks and merchant quays"
        assert params["site_profile"] == "waterfront"

    def test_location_generation_params_fall_back_to_map_brief(self):
        params = _build_location_generation_params(
            {
                "name": "Academy",
                "type": "building",
                "width": 18,
                "depth": 12,
            },
            map_spec={
                "layout_brief": "cliffside sorcery academy with terraces and ritual towers",
            },
            map_seed=7,
            index=0,
        )

        assert params["layout_brief"] == "cliffside sorcery academy with terraces and ritual towers"
        assert params["site_profile"] == "cliffside"
        assert params["width"] == 18
        assert params["depth"] == 12

    def test_world_quality_prefixes_deduplicate_and_strip_blanks(self):
        prefixes = _world_quality_prefixes(["TownRoot", "", "TownRoot", "CastleKeep", "  "])
        assert prefixes == ["TownRoot", "CastleKeep"]

    def test_world_quality_filter_skips_detail_repeats(self):
        prefixes = ["TownRoot"]
        assert _should_validate_world_mesh("TownRoot_Wall_front", "MESH", prefixes) is True
        assert _should_validate_world_mesh("TownRoot_Window_F0_0", "MESH", prefixes) is False
        assert _should_validate_world_mesh("TownRoot_Facade_12", "MESH", prefixes) is False
        assert _should_validate_world_mesh("TownRoot_Wall_front_LOD0", "MESH", prefixes) is False

    def test_world_quality_family_collapses_segment_suffixes(self):
        assert _world_quality_family("TownRoot_Wall_front_12") == "TownRoot_Wall_front_#"
        assert _world_quality_family("TownRoot_Interior_3_Wall_Back") == "TownRoot_Interior_Wall_Back"

    def test_vegetation_rules_normalize_asset_aliases(self):
        rules = _normalize_vegetation_rules({
            "density": 0.6,
            "rules": [{"asset": "tree", "density": 0.5}],
        })
        assert rules[0]["vegetation_type"] == "tree"
        assert rules[0]["density"] == 0.5

    def test_vegetation_rules_default_to_thornwood_progression(self):
        rules = _normalize_vegetation_rules({"density": 1.0}, "thornwood_forest")
        rule_types = {rule["vegetation_type"] for rule in rules}
        assert "tree_healthy" in rule_types
        assert "tree_boundary" in rule_types
        assert "tree_blighted" in rule_types

    def test_lighting_preset_tracks_biome_darkness(self):
        assert _lighting_preset_for_biome("thornwood_forest") == "forest_review"
        assert _lighting_preset_for_biome("veil_crack_zone") == "veil_corrupted"
        assert _lighting_preset_for_biome("grasslands") == "forest_healthy"


class TestInteriorPlanning:
    def test_room_graph_creates_non_overlapping_bounds(self):
        plan = _plan_interior_rooms({
            "rooms": [
                {"name": "hall", "type": "tavern_hall", "width": 10, "depth": 12, "height": 4},
                {"name": "kitchen", "type": "kitchen", "width": 5, "depth": 6, "height": 3.5},
                {"name": "bedroom", "type": "bedroom", "width": 6, "depth": 7, "height": 3.0},
            ],
            "doors": [
                {"from": "hall", "to": "kitchen"},
                {"from": "hall", "to": "bedroom"},
            ],
        })

        rooms = {room["name"]: room for room in plan["rooms"]}
        hall = rooms["hall"]["bounds"]
        kitchen = rooms["kitchen"]["bounds"]
        bedroom = rooms["bedroom"]["bounds"]

        assert kitchen["min"][0] >= hall["max"][0] or kitchen["min"][1] >= hall["max"][1]
        assert bedroom["min"][0] <= hall["min"][0] or bedroom["min"][1] >= hall["max"][1] or bedroom["max"][1] <= hall["min"][1]

    def test_room_graph_generates_internal_doors_from_from_to_edges(self):
        plan = _plan_interior_rooms({
            "rooms": [
                {"name": "hall", "type": "tavern_hall", "width": 10, "depth": 12, "height": 4},
                {"name": "kitchen", "type": "kitchen", "width": 5, "depth": 6, "height": 3.5},
            ],
            "doors": [
                {"from": "hall", "to": "kitchen"},
            ],
        })

        assert len(plan["doors"]) == 1
        door = plan["doors"][0]
        assert door["facing"] in {"east", "west", "north", "south"}
        assert len(door["position"]) == 3

    def test_room_graph_generates_default_exterior_door_when_none_supplied(self):
        plan = _plan_interior_rooms({
            "rooms": [
                {"name": "single_room", "type": "library", "width": 8, "depth": 8, "height": 3.5},
            ],
            "doors": [],
        })

        assert len(plan["doors"]) == 1
        assert plan["doors"][0]["facing"] == "south"
        assert plan["building_bounds"]["max"][0] > plan["building_bounds"]["min"][0]
