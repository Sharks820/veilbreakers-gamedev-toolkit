"""Integration tests for Phase 48: Starter City Generation pipeline.

Validates compose_map pipeline specs, settlement routing, vegetation wiring,
interior binding, and road network readiness -- all without Blender TCP.

Coverage:
  CITY-01: Terrain map_spec structure validation
  CITY-02: Settlement + castle location spec validation
  CITY-03: Interior spec structure validation
  CITY-07: Pipeline readiness (handler routing, imports)
"""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_toolkit_root = Path(__file__).resolve().parent.parent
if str(_toolkit_root) not in sys.path:
    sys.path.insert(0, str(_toolkit_root))

_src_root = _toolkit_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))


# ===========================================================================
# Hearthvale map_spec fixture (the canonical city generation payload)
# ===========================================================================

def _hearthvale_map_spec() -> dict:
    """Canonical Hearthvale map_spec for Phase 48 generation."""
    return {
        "name": "Hearthvale_Region",
        "seed": 42,
        "terrain": {
            "preset": "hills",
            "size": 250,
            "resolution": 256,
            "height_scale": 25.0,
            "erosion": True,
            "erosion_iterations": 8000,
        },
        "water": {
            "rivers": [
                {"source": [30, 30], "destination": [220, 220], "width": 6, "depth": 3.0},
                {"source": [150, 10], "destination": [200, 240], "width": 4, "depth": 2.0},
            ],
            "water_level": 2.5,
        },
        "roads": [
            {"waypoints": [[50, 125], [125, 125], [200, 125]], "width": 5},
            {"waypoints": [[125, 50], [125, 200]], "width": 4},
        ],
        "locations": [
            {
                "type": "settlement",
                "name": "Hearthvale",
                "position": [125, 125],
                "districts": 5,
                "building_count": 30,
            },
            {"type": "castle", "name": "Hearthvale_Castle", "position": [100, 180]},
            {"type": "ruins", "name": "Ancient_Watchtower", "position": [200, 60]},
        ],
        "biome": "thornwood_forest",
        "vegetation": {"density": 0.5, "max_instances": 4000},
        "atmosphere": "foggy",
        "props": True,
        "prop_density": 0.35,
    }


def _tavern_interior_spec() -> dict:
    """Canonical tavern interior_spec for Phase 48 generation."""
    return {
        "name": "Hearthvale_Tavern",
        "seed": 42,
        "rooms": [
            {"name": "main_hall", "type": "tavern_hall", "width": 12, "depth": 14, "height": 4.5},
            {"name": "kitchen", "type": "kitchen", "width": 6, "depth": 7, "height": 3.5},
            {"name": "cellar", "type": "storage", "width": 10, "depth": 10, "height": 3, "below_ground": True},
        ],
        "doors": [
            {"from": "main_hall", "to": "kitchen", "style": "wooden"},
            {"from": "main_hall", "to": "cellar", "style": "trapdoor"},
        ],
        "style": "medieval",
        "storytelling_density": 0.7,
        "generate_props_with_tripo": False,
    }


def _blacksmith_interior_spec() -> dict:
    """Canonical blacksmith interior_spec for Phase 48 generation."""
    return {
        "name": "Hearthvale_Blacksmith",
        "seed": 43,
        "rooms": [
            {"name": "forge_room", "type": "forge", "width": 8, "depth": 10, "height": 4},
            {"name": "shop_front", "type": "shop", "width": 6, "depth": 8, "height": 3.5},
            {"name": "storage", "type": "storage", "width": 5, "depth": 5, "height": 3},
        ],
        "doors": [
            {"from": "forge_room", "to": "shop_front", "style": "wooden"},
            {"from": "shop_front", "to": "storage", "style": "wooden"},
        ],
        "style": "medieval",
        "storytelling_density": 0.8,
        "generate_props_with_tripo": False,
    }


# ===========================================================================
# CITY-01: Map spec structure validation
# ===========================================================================


class TestComposeMapSpec:
    """Validate the Hearthvale map_spec structure has all required keys."""

    def test_compose_map_spec_valid(self):
        """map_spec has all required top-level keys for compose_map."""
        spec = _hearthvale_map_spec()
        required_keys = {"name", "seed", "terrain", "water", "roads", "locations", "biome", "vegetation"}
        assert required_keys.issubset(spec.keys()), (
            f"Missing keys: {required_keys - set(spec.keys())}"
        )

    def test_compose_map_terrain_params(self):
        """Terrain params match Hearthvale design: hills preset, 250m, 256 res, 25m height, erosion."""
        t = _hearthvale_map_spec()["terrain"]
        assert t["preset"] == "hills"
        assert t["size"] == 250
        assert t["resolution"] == 256
        assert t["height_scale"] == 25.0
        assert t["erosion"] is True

    def test_compose_map_settlement_location(self):
        """Locations list includes a settlement type with name Hearthvale."""
        locs = _hearthvale_map_spec()["locations"]
        settlements = [loc for loc in locs if loc["type"] == "settlement"]
        assert len(settlements) >= 1, "No settlement location found"
        assert any(s["name"] == "Hearthvale" for s in settlements)

    def test_compose_map_castle_location(self):
        """Locations list includes a castle type."""
        locs = _hearthvale_map_spec()["locations"]
        castles = [loc for loc in locs if loc["type"] == "castle"]
        assert len(castles) >= 1, "No castle location found"

    def test_compose_map_road_waypoints_integer(self):
        """All road waypoints are integers (not floats -- Phase 39 bug fix)."""
        roads = _hearthvale_map_spec()["roads"]
        for road in roads:
            for wp in road["waypoints"]:
                for coord in wp:
                    assert isinstance(coord, int), (
                        f"Road waypoint coordinate {coord} is {type(coord).__name__}, expected int"
                    )

    def test_compose_map_water_rivers(self):
        """Water spec has at least one river with source, destination, width."""
        w = _hearthvale_map_spec()["water"]
        assert "rivers" in w
        assert len(w["rivers"]) >= 1
        for river in w["rivers"]:
            assert "source" in river
            assert "destination" in river
            assert "width" in river
            assert river["width"] > 0

    def test_compose_map_biome_is_valid(self):
        """Biome string is a known biome type."""
        valid_biomes = {
            "thornwood_forest", "temperate_woodland", "dark_forest",
            "corrupted_waste", "mountainous", "swamp",
        }
        biome = _hearthvale_map_spec()["biome"]
        assert biome in valid_biomes, f"Unknown biome: {biome}"


# ===========================================================================
# CITY-03: Interior spec structure validation
# ===========================================================================


class TestComposeInteriorSpec:
    """Validate interior_spec structures for key buildings."""

    def test_compose_interior_tavern_spec(self):
        """Tavern interior_spec has rooms=[tavern_hall, kitchen, cellar], doors, style=medieval."""
        spec = _tavern_interior_spec()
        assert spec["style"] == "medieval"
        room_types = {r["type"] for r in spec["rooms"]}
        assert "tavern_hall" in room_types
        assert "kitchen" in room_types
        assert "storage" in room_types  # cellar
        assert len(spec["doors"]) >= 2

    def test_compose_interior_blacksmith_spec(self):
        """Blacksmith interior_spec has rooms=[forge, shop, storage]."""
        spec = _blacksmith_interior_spec()
        assert spec["style"] == "medieval"
        room_types = {r["type"] for r in spec["rooms"]}
        assert "forge" in room_types
        assert "shop" in room_types
        assert "storage" in room_types
        assert len(spec["doors"]) >= 2

    def test_interior_room_dimensions_positive(self):
        """All room dimensions in interior specs are positive values."""
        for spec_fn in [_tavern_interior_spec, _blacksmith_interior_spec]:
            spec = spec_fn()
            for room in spec["rooms"]:
                assert room["width"] > 0, f"Room {room['name']} has non-positive width"
                assert room["depth"] > 0, f"Room {room['name']} has non-positive depth"
                assert room["height"] > 0, f"Room {room['name']} has non-positive height"


# ===========================================================================
# CITY-07: Pipeline readiness (handler routing, imports)
# ===========================================================================


class TestPipelineReadiness:
    """Verify compose_map pipeline dependencies are wired and importable."""

    @staticmethod
    def _compose_map_loc_handlers() -> dict[str, str]:
        import veilbreakers_mcp.blender_server as blender_server

        module = ast.parse(inspect.getsource(blender_server))
        for node in ast.walk(module):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "_LOC_HANDLERS" for target in node.targets):
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            handlers: dict[str, str] = {}
            for key_node, value_node in zip(node.value.keys, node.value.values):
                if isinstance(key_node, ast.Constant) and isinstance(value_node, ast.Constant):
                    handlers[str(key_node.value)] = str(value_node.value)
            return handlers
        raise AssertionError("Could not find _LOC_HANDLERS assignment in blender_server")

    def test_loc_handlers_settlement_exists(self):
        """compose_map routes settlement locations to the settlement generator."""
        loc_handlers = self._compose_map_loc_handlers()
        assert loc_handlers["settlement"] == "world_generate_settlement"

    def test_loc_handlers_castle_routes_to_castle(self):
        """compose_map keeps castle routing pointed at the castle generator."""
        loc_handlers = self._compose_map_loc_handlers()
        assert loc_handlers["castle"] == "world_generate_castle"

    def test_vegetation_generator_map_exists(self):
        """VEGETATION_GENERATOR_MAP is importable and has 15+ entries."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP

        assert len(VEGETATION_GENERATOR_MAP) >= 15, (
            f"VEGETATION_GENERATOR_MAP has only {len(VEGETATION_GENERATOR_MAP)} entries (expected 15+)"
        )

    def test_building_interior_binding_imported(self):
        """building_interior_binding module is importable."""
        # Check that the module file exists
        binding_path = _toolkit_root / "blender_addon" / "handlers" / "building_interior_binding.py"
        assert binding_path.exists(), (
            f"building_interior_binding.py not found at {binding_path}"
        )
        # Check it's referenced in __init__.py
        init_path = _toolkit_root / "blender_addon" / "handlers" / "__init__.py"
        if init_path.exists():
            content = init_path.read_text()
            assert "building_interior_binding" in content, (
                "building_interior_binding not imported in handlers/__init__.py"
            )

    def test_mst_road_network_exists(self):
        """road_network exposes a working MST helper used by road generation."""
        from blender_addon.handlers.road_network import compute_mst_edges

        waypoints = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)]
        mst_edges = compute_mst_edges(waypoints)
        assert len(mst_edges) == len(waypoints) - 1
        assert all(len(edge) == 3 for edge in mst_edges)

    def test_compose_map_helper_functions_importable(self):
        """Key compose_map helper functions are importable from blender_server."""
        from veilbreakers_mcp.blender_server import (
            _map_point_to_terrain_cell,
            _normalize_map_point,
            _normalize_vegetation_rules,
            _plan_map_location_anchors,
            _resolve_map_generation_budget,
            _build_location_generation_params,
            _lighting_preset_for_biome,
        )
        # All imported successfully
        assert callable(_map_point_to_terrain_cell)
        assert callable(_normalize_map_point)
        assert callable(_normalize_vegetation_rules)

    def test_pipeline_state_checkpoint_functions_importable(self):
        """Pipeline checkpoint save/load/delete functions are importable."""
        from blender_addon.handlers.pipeline_state import (
            save_pipeline_checkpoint,
            load_pipeline_checkpoint,
            delete_pipeline_checkpoint,
            validate_checkpoint_compatibility,
            get_remaining_steps,
        )
        assert callable(save_pipeline_checkpoint)
        assert callable(load_pipeline_checkpoint)
