"""Wiring integration tests -- verify dead-code modules are properly imported
and registered in the handlers package.

Phase 42-01: Dead Code Wiring foundation. These tests ensure all 4 dead-code
modules (modular_building_kit, building_interior_binding, prop_density,
terrain_features v2) are importable from the handlers package and that
COMMAND_HANDLERS has dispatch entries for all 10 terrain feature generators.
"""

import pytest


class TestNoImportCycles:
    """Importing handlers package should not raise ImportError."""

    def test_no_import_cycles(self):
        from blender_addon import handlers  # noqa: F401


class TestModularBuildingKitImportable:
    """modular_building_kit symbols importable from handlers."""

    def test_generate_modular_piece(self):
        from blender_addon.handlers import generate_modular_piece
        assert callable(generate_modular_piece)

    def test_assemble_building(self):
        from blender_addon.handlers import assemble_building
        assert callable(assemble_building)

    def test_get_available_pieces(self):
        from blender_addon.handlers import get_available_pieces
        assert callable(get_available_pieces)

    def test_modular_styles(self):
        from blender_addon.handlers import MODULAR_STYLES
        assert "medieval" in MODULAR_STYLES
        assert "gothic" in MODULAR_STYLES
        assert "fortress" in MODULAR_STYLES
        assert "organic" in MODULAR_STYLES
        assert "ruined" in MODULAR_STYLES


class TestBuildingInteriorBindingImportable:
    """building_interior_binding symbols importable from handlers."""

    def test_building_room_map(self):
        from blender_addon.handlers import BUILDING_ROOM_MAP
        assert isinstance(BUILDING_ROOM_MAP, dict)
        assert len(BUILDING_ROOM_MAP) >= 14, (
            f"Expected >= 14 building types, got {len(BUILDING_ROOM_MAP)}"
        )

    def test_style_material_map(self):
        from blender_addon.handlers import STYLE_MATERIAL_MAP
        assert isinstance(STYLE_MATERIAL_MAP, dict)
        assert "medieval" in STYLE_MATERIAL_MAP

    def test_get_interior_materials(self):
        from blender_addon.handlers import get_interior_materials
        assert callable(get_interior_materials)
        result = get_interior_materials("medieval")
        assert isinstance(result, dict)
        assert "wall" in result

    def test_get_room_types_for_building(self):
        from blender_addon.handlers import get_room_types_for_building
        assert callable(get_room_types_for_building)
        rooms = get_room_types_for_building("tavern")
        assert len(rooms) > 0

    def test_align_rooms_to_building(self):
        from blender_addon.handlers import align_rooms_to_building
        assert callable(align_rooms_to_building)

    def test_generate_door_metadata(self):
        from blender_addon.handlers import generate_door_metadata
        assert callable(generate_door_metadata)

    def test_generate_interior_spec_from_building(self):
        from blender_addon.handlers import generate_interior_spec_from_building
        assert callable(generate_interior_spec_from_building)


class TestPropDensityImportable:
    """prop_density symbols importable from handlers."""

    def test_room_density_rules(self):
        from blender_addon.handlers import ROOM_DENSITY_RULES
        assert isinstance(ROOM_DENSITY_RULES, dict)
        assert len(ROOM_DENSITY_RULES) >= 12, (
            f"Expected >= 12 room types, got {len(ROOM_DENSITY_RULES)}"
        )

    def test_compute_detail_prop_placements(self):
        from blender_addon.handlers import compute_detail_prop_placements
        assert callable(compute_detail_prop_placements)


class TestTerrainFeaturesAll10Importable:
    """All 10 terrain feature generators importable from handlers."""

    GENERATORS = [
        "generate_canyon",
        "generate_waterfall",
        "generate_cliff_face",
        "generate_swamp_terrain",
        "generate_natural_arch",
        "generate_geyser",
        "generate_sinkhole",
        "generate_floating_rocks",
        "generate_ice_formation",
        "generate_lava_flow",
    ]

    @pytest.mark.parametrize("name", GENERATORS)
    def test_generator_importable(self, name):
        import blender_addon.handlers as h
        gen = getattr(h, name, None)
        assert gen is not None, f"{name} not found in handlers"
        assert callable(gen), f"{name} is not callable"


class TestTerrainFeaturesAllDispatched:
    """COMMAND_HANDLERS contains entries for all 10 terrain feature commands."""

    DISPATCH_KEYS = [
        "env_generate_canyon",
        "env_generate_waterfall",
        "env_generate_cliff_face",
        "env_generate_swamp_terrain",
        "env_generate_natural_arch",
        "env_generate_geyser",
        "env_generate_sinkhole",
        "env_generate_floating_rocks",
        "env_generate_ice_formation",
        "env_generate_lava_flow",
    ]

    @pytest.mark.parametrize("key", DISPATCH_KEYS)
    def test_dispatch_entry_exists(self, key):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert key in COMMAND_HANDLERS, f"Missing COMMAND_HANDLERS['{key}']"

    @pytest.mark.parametrize("key", DISPATCH_KEYS)
    def test_dispatch_entry_callable(self, key):
        from blender_addon.handlers import COMMAND_HANDLERS
        handler = COMMAND_HANDLERS[key]
        assert callable(handler), f"COMMAND_HANDLERS['{key}'] is not callable"

    def test_dispatch_returns_dict(self):
        """Verify a terrain dispatch entry returns a dict when called."""
        from blender_addon.handlers import COMMAND_HANDLERS
        result = COMMAND_HANDLERS["env_generate_natural_arch"]({})
        assert isinstance(result, dict), "Dispatch entry should return a dict"


class TestModularBuildingKitNotDirectlyDispatched:
    """modular_building_kit does NOT need COMMAND_HANDLERS entries --
    these are called from worldbuilding.py directly, not via TCP dispatch."""

    def test_no_modular_piece_dispatch(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        # These should NOT be in dispatch -- they're called internally
        assert "generate_modular_piece" not in COMMAND_HANDLERS
        assert "assemble_building" not in COMMAND_HANDLERS


class TestLocHandlersExistence:
    """Verify _LOC_HANDLERS dict exists in blender_server.py (prep for Plan 02)."""

    def test_loc_handlers_in_blender_server_source(self):
        """Check that blender_server.py contains _LOC_HANDLERS dict definition."""
        from pathlib import Path
        server_path = (
            Path(__file__).resolve().parent.parent
            / "src" / "veilbreakers_mcp" / "blender_server.py"
        )
        source = server_path.read_text(encoding="utf-8")
        assert "_LOC_HANDLERS" in source, (
            "blender_server.py should contain _LOC_HANDLERS dict"
        )
        # Verify it maps location types to handler commands
        assert '"town"' in source
        assert '"castle"' in source
        assert '"settlement"' in source
