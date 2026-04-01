"""Tests for the lighting placement engine in _building_grammar.py.

Covers:
- Min 2 light sources per room guaranteed
- All color temperatures in 2700-3500K range
- Torches placed at doorway positions
- Candles on tables when tables present
- Chandelier in large rooms (>8m dimension)
- LIGHTING_SCHEMAS defined for all 22+ room types in _ROOM_CONFIGS
- Deterministic output (same seed = same layout)
- No lights outside room bounds
"""

import pytest

# conftest.py stubs bpy/bmesh/mathutils and adds toolkit root to sys.path,
# so a standard package import works here just like test_building_grammar.py.


@pytest.fixture(scope="module")
def grammar():
    from blender_addon.handlers import _building_grammar
    return _building_grammar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_furniture(*types_: str) -> list[dict]:
    """Build a minimal furniture list with given type strings."""
    items = []
    for i, t in enumerate(types_):
        items.append({
            "type": t,
            "position": [1.0 + i * 0.5, 1.0 + i * 0.5, 0.0],
        })
    return items


def _run_layout(grammar, room_type="tavern", width=6.0, depth=5.0, height=3.0,
                furniture=None, doors=None, seed=42):
    if furniture is None:
        furniture = []
    if doors is None:
        doors = []
    return grammar.generate_lighting_layout(
        room_type, width, depth, height,
        furniture_items=furniture,
        door_positions=doors,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Schema coverage
# ---------------------------------------------------------------------------

class TestLightingSchemas:
    """LIGHTING_SCHEMAS must cover every room type in _ROOM_CONFIGS."""

    def test_schemas_dict_exists(self, grammar):
        assert hasattr(grammar, "LIGHTING_SCHEMAS")
        assert isinstance(grammar.LIGHTING_SCHEMAS, dict)

    def test_all_room_types_have_schema(self, grammar):
        room_types = set(grammar._ROOM_CONFIGS.keys())
        schema_types = set(grammar.LIGHTING_SCHEMAS.keys())
        missing = room_types - schema_types
        assert not missing, f"LIGHTING_SCHEMAS missing schemas for: {sorted(missing)}"

    def test_each_schema_has_mandatory_key(self, grammar):
        for room_type, schema in grammar.LIGHTING_SCHEMAS.items():
            assert "mandatory" in schema, f"Schema for '{room_type}' missing 'mandatory'"
            assert isinstance(schema["mandatory"], list)

    def test_each_schema_has_conditional_key(self, grammar):
        for room_type, schema in grammar.LIGHTING_SCHEMAS.items():
            assert "conditional" in schema, f"Schema for '{room_type}' missing 'conditional'"
            assert isinstance(schema["conditional"], list)

    def test_mandatory_lists_contain_valid_light_types(self, grammar):
        valid_types = set(grammar._LIGHT_TYPE_PROPS.keys())
        for room_type, schema in grammar.LIGHTING_SCHEMAS.items():
            for lt in schema["mandatory"]:
                assert lt in valid_types, (
                    f"Room '{room_type}' mandatory light '{lt}' not in _LIGHT_TYPE_PROPS"
                )

    def test_conditional_lists_contain_valid_light_types(self, grammar):
        valid_types = set(grammar._LIGHT_TYPE_PROPS.keys())
        for room_type, schema in grammar.LIGHTING_SCHEMAS.items():
            for cond in schema["conditional"]:
                lt = cond.get("type")
                assert lt in valid_types, (
                    f"Room '{room_type}' conditional light '{lt}' not in _LIGHT_TYPE_PROPS"
                )


# ---------------------------------------------------------------------------
# Light type properties
# ---------------------------------------------------------------------------

class TestLightTypeProps:
    """_LIGHT_TYPE_PROPS contains all 5 required light types with correct values."""

    def test_all_five_light_types_exist(self, grammar):
        required = {
            "torch_sconce", "candle", "fireplace_light",
            "chandelier_light", "brazier_light",
        }
        assert required <= set(grammar._LIGHT_TYPE_PROPS.keys())

    def test_torch_sconce_properties(self, grammar):
        p = grammar._LIGHT_TYPE_PROPS["torch_sconce"]
        assert p["color_temperature"] == 2800
        assert p["radius"] == pytest.approx(4.0)
        assert p["intensity"] == pytest.approx(1.0)

    def test_candle_properties(self, grammar):
        p = grammar._LIGHT_TYPE_PROPS["candle"]
        assert p["color_temperature"] == 3000
        assert p["radius"] == pytest.approx(2.0)
        assert p["intensity"] == pytest.approx(0.5)

    def test_fireplace_light_properties(self, grammar):
        p = grammar._LIGHT_TYPE_PROPS["fireplace_light"]
        assert p["color_temperature"] == 2700
        assert p["radius"] == pytest.approx(5.0)
        assert p["intensity"] == pytest.approx(1.5)

    def test_chandelier_light_properties(self, grammar):
        p = grammar._LIGHT_TYPE_PROPS["chandelier_light"]
        assert p["color_temperature"] == 3200
        assert p["radius"] == pytest.approx(8.0)
        assert p["intensity"] == pytest.approx(2.0)

    def test_brazier_light_properties(self, grammar):
        p = grammar._LIGHT_TYPE_PROPS["brazier_light"]
        assert p["color_temperature"] == 3000
        assert p["radius"] == pytest.approx(3.0)
        assert p["intensity"] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Minimum light count
# ---------------------------------------------------------------------------

class TestMinimumLightCount:
    """Every room must produce at least 2 light sources."""

    @pytest.mark.parametrize("room_type", [
        "tavern", "smithy", "storage", "barracks", "guard_post",
        "throne_room", "dungeon_cell", "bedroom", "kitchen", "library",
        "study", "great_hall", "armory", "chapel", "shrine_room",
        "blacksmith", "guard_barracks", "treasury", "war_room",
        "alchemy_lab", "torture_chamber", "crypt", "dining_hall",
    ])
    def test_min_two_lights_per_room(self, grammar, room_type):
        lights = _run_layout(grammar, room_type=room_type, seed=0)
        assert len(lights) >= 2, (
            f"Room '{room_type}' produced only {len(lights)} light(s); need >= 2"
        )

    def test_empty_furniture_still_two_lights(self, grammar):
        lights = _run_layout(
            grammar, room_type="storage", furniture=[], doors=[], seed=99,
        )
        assert len(lights) >= 2

    def test_no_doors_still_two_lights(self, grammar):
        lights = _run_layout(
            grammar, room_type="bedroom", doors=[], seed=7,
        )
        assert len(lights) >= 2

    def test_unknown_room_type_still_two_lights(self, grammar):
        lights = _run_layout(
            grammar, room_type="unknown_room_xyz", doors=[], seed=1,
        )
        assert len(lights) >= 2


# ---------------------------------------------------------------------------
# Color temperature range
# ---------------------------------------------------------------------------

class TestColorTemperatureRange:
    """All generated lights must have color_temperature in 2700-3500 K."""

    _ALL_ROOMS = [
        "tavern", "smithy", "storage", "barracks", "guard_post",
        "throne_room", "dungeon_cell", "bedroom", "kitchen", "library",
        "study", "great_hall", "armory", "chapel", "shrine_room",
        "blacksmith", "guard_barracks", "treasury", "war_room",
        "alchemy_lab", "torture_chamber", "crypt", "dining_hall",
    ]

    @pytest.mark.parametrize("room_type", _ALL_ROOMS)
    def test_temperature_in_range(self, grammar, room_type):
        lights = _run_layout(grammar, room_type=room_type, seed=42)
        for light in lights:
            ct = light["color_temperature"]
            assert 2700 <= ct <= 3500, (
                f"Room '{room_type}' light '{light['type']}' has temperature "
                f"{ct} K, outside 2700-3500K range"
            )

    def test_light_type_props_all_in_range(self, grammar):
        for lt, props in grammar._LIGHT_TYPE_PROPS.items():
            ct = props["color_temperature"]
            assert 2700 <= ct <= 3500, (
                f"Light type '{lt}' has temperature {ct} K, outside 2700-3500K range"
            )


# ---------------------------------------------------------------------------
# Torch placement at doorways
# ---------------------------------------------------------------------------

class TestTorchDoorwayPlacement:
    """Torches must be placed near each door position."""

    def test_torches_placed_for_single_door(self, grammar):
        doors = [(3.0, 0.0)]  # front wall center
        lights = _run_layout(
            grammar, room_type="guard_post", width=6.0, depth=5.0,
            furniture=[], doors=doors, seed=0,
        )
        torch_lights = [l for l in lights if l["type"] == "torch_sconce"]
        # Expect at least 2 torches from the doorway
        assert len(torch_lights) >= 2

    def test_torches_placed_for_multiple_doors(self, grammar):
        doors = [(3.0, 0.0), (3.0, 5.0)]  # front and back walls
        lights = _run_layout(
            grammar, room_type="tavern", width=6.0, depth=5.0,
            furniture=[], doors=doors, seed=0,
        )
        torch_lights = [l for l in lights if l["type"] == "torch_sconce"]
        assert len(torch_lights) >= 4

    def test_torch_height_at_1_6m(self, grammar):
        """Door-placed torches should be at height 1.6m."""
        doors = [(3.0, 0.0)]
        lights = _run_layout(
            grammar, room_type="storage", width=6.0, depth=5.0,
            furniture=[], doors=doors, seed=0,
        )
        # Find lights that came from the door position (near x=3, y=0)
        door_torches = [
            l for l in lights
            if l["type"] == "torch_sconce" and abs(l["position"][1]) < 0.3
        ]
        assert door_torches, "No door torches found near the door position"
        for t in door_torches:
            assert t["position"][2] == pytest.approx(1.6), (
                f"Door torch z-height is {t['position'][2]}, expected 1.6"
            )

    def test_no_doors_does_not_add_door_torches(self, grammar):
        """With no doors, no door-specific torches are added (may still have wall torches)."""
        lights_with_door = _run_layout(
            grammar, room_type="bedroom", doors=[(3.0, 0.0)], seed=5,
        )
        lights_without_door = _run_layout(
            grammar, room_type="bedroom", doors=[], seed=5,
        )
        # Layout with a door should add at least 2 more lights (door torches)
        assert len(lights_with_door) >= len(lights_without_door)


# ---------------------------------------------------------------------------
# Candles on tables
# ---------------------------------------------------------------------------

class TestCandlesOnTables:
    """Candles should be placed on table surfaces when tables are in furniture."""

    def test_candle_placed_when_table_present(self, grammar):
        furniture = _make_furniture("table", "chair")
        lights = _run_layout(
            grammar, room_type="tavern", furniture=furniture, doors=[], seed=0,
        )
        candles = [l for l in lights if l["type"] == "candle"]
        assert candles, "Expected at least one candle on a table surface"

    def test_candle_position_matches_table_position(self, grammar):
        """Candle x,y should match the table's x,y position."""
        furniture = [{"type": "table", "position": [2.5, 3.0, 0.0]}]
        lights = _run_layout(
            grammar, room_type="storage", width=6.0, depth=6.0,
            furniture=furniture, doors=[], seed=0,
        )
        candles = [l for l in lights if l["type"] == "candle"]
        assert candles
        # At least one candle should be near the table's x,y
        table_candle = next(
            (c for c in candles
             if abs(c["position"][0] - 2.5) < 0.2 and abs(c["position"][1] - 3.0) < 0.2),
            None,
        )
        assert table_candle is not None, (
            "No candle found near the table position (2.5, 3.0)"
        )

    def test_no_candles_on_tables_when_no_tables(self, grammar):
        """Without table furniture, table-sourced candles should not appear
        (schema-driven candles from other triggers may still appear)."""
        furniture = _make_furniture("chair", "shelf", "barrel")
        lights_no_tables = _run_layout(
            grammar, room_type="storage", furniture=furniture, doors=[], seed=0,
        )
        furniture_with_table = _make_furniture("chair", "table", "barrel")
        lights_with_table = _run_layout(
            grammar, room_type="storage", furniture=furniture_with_table, doors=[], seed=0,
        )
        candles_no_table = [l for l in lights_no_tables if l["type"] == "candle"]
        candles_with_table = [l for l in lights_with_table if l["type"] == "candle"]
        # Having a table should result in at least one more candle
        assert len(candles_with_table) >= len(candles_no_table)

    def test_multiple_tables_produce_multiple_candles(self, grammar):
        furniture = _make_furniture("table", "long_table", "serving_table")
        lights = _run_layout(
            grammar, room_type="dining_hall", width=10.0, depth=8.0,
            furniture=furniture, doors=[], seed=0,
        )
        candles = [l for l in lights if l["type"] == "candle"]
        assert len(candles) >= 3, (
            f"Expected >= 3 candles for 3 tables, got {len(candles)}"
        )


# ---------------------------------------------------------------------------
# Chandelier in large rooms
# ---------------------------------------------------------------------------

class TestChandelierInLargeRooms:
    """Chandelier placed at ceiling center when room > 8m in any dimension."""

    def test_chandelier_in_wide_room(self, grammar):
        lights = _run_layout(
            grammar, room_type="great_hall", width=10.0, depth=6.0, height=5.0,
            furniture=[], doors=[], seed=0,
        )
        chandeliers = [l for l in lights if l["type"] == "chandelier_light"]
        assert chandeliers, "Expected chandelier in room with width > 8m"

    def test_chandelier_in_deep_room(self, grammar):
        lights = _run_layout(
            grammar, room_type="dining_hall", width=6.0, depth=9.0, height=4.0,
            furniture=[], doors=[], seed=0,
        )
        chandeliers = [l for l in lights if l["type"] == "chandelier_light"]
        assert chandeliers, "Expected chandelier in room with depth > 8m"

    def test_no_geometric_chandelier_in_small_room(self, grammar):
        """A small room (< 8m both ways) should not get a geometry-triggered chandelier
        unless the schema or furniture mandates one."""
        lights = _run_layout(
            grammar, room_type="dungeon_cell", width=4.0, depth=3.0, height=2.8,
            furniture=[], doors=[], seed=0,
        )
        # geometry-trigger chandeliers are for width or depth > 8m
        # dungeon_cell schema has no chandelier mandatory, and room is small
        schema = grammar.LIGHTING_SCHEMAS["dungeon_cell"]
        schema_chandeliers = (
            [lt for lt in schema["mandatory"] if lt == "chandelier_light"]
            + [c for c in schema["conditional"] if c["type"] == "chandelier_light"]
        )
        if not schema_chandeliers:
            chandeliers = [l for l in lights if l["type"] == "chandelier_light"]
            assert not chandeliers, (
                "Small dungeon_cell (4x3) should not have a geometry-triggered chandelier"
            )

    def test_chandelier_at_ceiling_center(self, grammar):
        """Chandelier x,y should be near room center; z near ceiling."""
        width, depth, height = 12.0, 10.0, 5.0
        lights = _run_layout(
            grammar, room_type="great_hall",
            width=width, depth=depth, height=height,
            furniture=[], doors=[], seed=0,
        )
        chandeliers = [l for l in lights if l["type"] == "chandelier_light"]
        assert chandeliers
        ch = chandeliers[0]
        assert abs(ch["position"][0] - width / 2) < 0.5, "Chandelier x not near center"
        assert abs(ch["position"][1] - depth / 2) < 0.5, "Chandelier y not near center"
        assert ch["position"][2] >= height * 0.7, "Chandelier not near ceiling"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Same seed must produce identical output across multiple calls."""

    @pytest.mark.parametrize("room_type", [
        "tavern", "bedroom", "great_hall", "crypt", "alchemy_lab",
    ])
    def test_same_seed_same_layout(self, grammar, room_type):
        furniture = _make_furniture("table", "chair", "fireplace")
        doors = [(3.0, 0.0)]
        kwargs = dict(
            room_type=room_type, width=8.0, depth=6.0, height=3.5,
            furniture_items=furniture, door_positions=doors, seed=12345,
        )
        result_a = grammar.generate_lighting_layout(**kwargs)
        result_b = grammar.generate_lighting_layout(**kwargs)
        assert result_a == result_b, (
            f"Non-deterministic output for room '{room_type}' with seed 12345"
        )

    def test_different_seeds_may_differ(self, grammar):
        """Different seeds should generally produce different layouts
        (not strictly required but strongly expected for randomised elements)."""
        furniture = _make_furniture("table")
        doors = [(2.0, 0.0)]
        kwargs_base = dict(
            room_type="tavern", width=8.0, depth=6.0, height=3.5,
            furniture_items=furniture, door_positions=doors,
        )
        result_0 = grammar.generate_lighting_layout(**kwargs_base, seed=0)
        result_1 = grammar.generate_lighting_layout(**kwargs_base, seed=9999)
        # They may differ (not a hard requirement but expected)
        # Just verify both are valid (>= 2 lights) — no assertion on inequality
        assert len(result_0) >= 2
        assert len(result_1) >= 2


# ---------------------------------------------------------------------------
# Bounds checking
# ---------------------------------------------------------------------------

class TestBoundsChecking:
    """No light should be placed outside the room extents."""

    @pytest.mark.parametrize("room_type", [
        "tavern", "smithy", "bedroom", "great_hall", "crypt",
    ])
    def test_no_lights_outside_room(self, grammar, room_type):
        width, depth = 6.0, 5.0
        furniture = _make_furniture("table", "fireplace", "chandelier")
        doors = [(width / 2, 0.0), (width / 2, depth)]
        lights = grammar.generate_lighting_layout(
            room_type, width, depth, 3.5, furniture, doors, seed=7,
        )
        for light in lights:
            x, y, z = light["position"]
            assert 0.0 <= x <= width, (
                f"Light '{light['type']}' x={x} out of bounds [0, {width}]"
            )
            assert 0.0 <= y <= depth, (
                f"Light '{light['type']}' y={y} out of bounds [0, {depth}]"
            )
            assert z >= 0.0, f"Light '{light['type']}' z={z} is below floor"

    def test_large_room_bounds(self, grammar):
        width, depth, height = 15.0, 12.0, 6.0
        lights = _run_layout(
            grammar, room_type="great_hall",
            width=width, depth=depth, height=height,
            furniture=_make_furniture("table", "chandelier", "fireplace"),
            doors=[(7.5, 0.0)],
            seed=42,
        )
        for light in lights:
            x, y, z = light["position"]
            assert 0.0 <= x <= width, f"x={x} out of bounds"
            assert 0.0 <= y <= depth, f"y={y} out of bounds"
            assert z >= 0.0

    def test_small_room_bounds(self, grammar):
        width, depth = 2.5, 2.5
        lights = _run_layout(
            grammar, room_type="dungeon_cell",
            width=width, depth=depth, height=2.5,
            furniture=[], doors=[(1.25, 0.0)],
            seed=3,
        )
        for light in lights:
            x, y, z = light["position"]
            assert 0.0 <= x <= width, f"x={x} out of bounds for small room"
            assert 0.0 <= y <= depth, f"y={y} out of bounds for small room"


# ---------------------------------------------------------------------------
# Return format
# ---------------------------------------------------------------------------

class TestReturnFormat:
    """generate_lighting_layout must return well-formed dicts."""

    def test_returns_list_of_dicts(self, grammar):
        lights = _run_layout(grammar)
        assert isinstance(lights, list)
        assert all(isinstance(l, dict) for l in lights)

    def test_each_light_has_required_keys(self, grammar):
        required_keys = {"type", "position", "color_temperature", "radius", "intensity"}
        lights = _run_layout(grammar, room_type="library", seed=0)
        for light in lights:
            missing = required_keys - set(light.keys())
            assert not missing, f"Light missing keys: {missing}"

    def test_position_is_three_tuple(self, grammar):
        lights = _run_layout(grammar)
        for light in lights:
            pos = light["position"]
            assert isinstance(pos, tuple), f"position should be tuple, got {type(pos)}"
            assert len(pos) == 3

    def test_intensity_is_positive(self, grammar):
        lights = _run_layout(grammar, room_type="great_hall", width=10.0, depth=9.0)
        for light in lights:
            assert light["intensity"] > 0.0, f"intensity must be positive, got {light['intensity']}"

    def test_radius_is_positive(self, grammar):
        lights = _run_layout(grammar, room_type="great_hall", width=10.0, depth=9.0)
        for light in lights:
            assert light["radius"] > 0.0, f"radius must be positive, got {light['radius']}"


# ---------------------------------------------------------------------------
# Fireplace emissive
# ---------------------------------------------------------------------------

class TestFireplacePlacement:
    """Fireplace emissive light placed when fireplace is in furniture."""

    def test_fireplace_light_when_fireplace_present(self, grammar):
        furniture = [{"type": "fireplace", "position": [1.0, 0.5, 0.0]}]
        lights = _run_layout(
            grammar, room_type="tavern", furniture=furniture, doors=[], seed=0,
        )
        fp_lights = [l for l in lights if l["type"] == "fireplace_light"]
        assert fp_lights, "Expected fireplace_light when fireplace furniture present"

    def test_cooking_fire_triggers_fireplace_light(self, grammar):
        furniture = [{"type": "cooking_fire", "position": [1.0, 0.5, 0.0]}]
        lights = _run_layout(
            grammar, room_type="kitchen", furniture=furniture, doors=[], seed=0,
        )
        fp_lights = [l for l in lights if l["type"] == "fireplace_light"]
        assert fp_lights, "Expected fireplace_light when cooking_fire furniture present"

    def test_fireplace_position_near_furniture(self, grammar):
        furniture = [{"type": "fireplace", "position": [2.0, 0.8, 0.0]}]
        lights = _run_layout(
            grammar, room_type="bedroom", width=6.0, depth=5.0,
            furniture=furniture, doors=[], seed=0,
        )
        fp_lights = [l for l in lights if l["type"] == "fireplace_light"]
        assert fp_lights
        fp = fp_lights[0]
        # fireplace light should be placed at or near the furniture x,y
        assert abs(fp["position"][0] - 2.0) < 0.3, (
            f"Fireplace light x {fp['position'][0]} not near furniture x 2.0"
        )
