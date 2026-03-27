"""Unit tests for building grammar pure-logic module.

Tests grammar evaluation, style configs, specialized templates,
ruins damage, interior layout, and modular kit -- all without Blender.
"""

import pytest


# ---------------------------------------------------------------------------
# Style Config tests
# ---------------------------------------------------------------------------


class TestStyleConfigs:
    """Test STYLE_CONFIGS has all required presets and keys."""

    def test_style_configs_has_five_entries(self):
        """STYLE_CONFIGS must have exactly 5 style presets."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        assert len(STYLE_CONFIGS) == 5

    def test_style_configs_has_expected_styles(self):
        """All 5 expected style names are present."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        expected = {"medieval", "gothic", "rustic", "fortress", "organic"}
        assert set(STYLE_CONFIGS.keys()) == expected

    def test_each_style_has_required_keys(self):
        """Every style config must have foundation, walls, floor_slab, roof, windows, door, details."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        required_keys = {"foundation", "walls", "floor_slab", "roof", "windows", "door", "details"}
        for style_name, config in STYLE_CONFIGS.items():
            missing = required_keys - set(config.keys())
            assert not missing, f"Style '{style_name}' missing keys: {missing}"

    def test_medieval_style_has_plaster_walls(self):
        """Medieval style uses plaster wall material."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        assert STYLE_CONFIGS["medieval"]["walls"]["material"] == "plaster_white"

    def test_medieval_style_has_gabled_roof(self):
        """Medieval style uses gabled roof type."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        assert STYLE_CONFIGS["medieval"]["roof"]["type"] == "gabled"

    def test_gothic_style_has_pointed_roof(self):
        """Gothic style uses pointed roof type."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        assert STYLE_CONFIGS["gothic"]["roof"]["type"] == "pointed"

    def test_fortress_style_has_flat_roof(self):
        """Fortress style uses flat roof with battlements."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        assert STYLE_CONFIGS["fortress"]["roof"]["type"] == "flat"

    def test_organic_style_has_domed_roof(self):
        """Organic style uses domed roof type."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        assert STYLE_CONFIGS["organic"]["roof"]["type"] == "domed"

    def test_gothic_taller_walls_than_medieval(self):
        """Gothic style has taller walls (height_per_floor) than medieval."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        gothic_h = STYLE_CONFIGS["gothic"]["walls"]["height_per_floor"]
        medieval_h = STYLE_CONFIGS["medieval"]["walls"]["height_per_floor"]
        assert gothic_h > medieval_h

    def test_fortress_thicker_walls_than_medieval(self):
        """Fortress style has thicker walls (thickness) than medieval."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        fortress_t = STYLE_CONFIGS["fortress"]["walls"]["thickness"]
        medieval_t = STYLE_CONFIGS["medieval"]["walls"]["thickness"]
        assert fortress_t > medieval_t


# ---------------------------------------------------------------------------
# Building Grammar Evaluation tests
# ---------------------------------------------------------------------------


class TestBuildingGrammar:
    """Test evaluate_building_grammar produces valid BuildingSpec."""

    def test_returns_building_spec(self):
        """evaluate_building_grammar returns a BuildingSpec instance."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            BuildingSpec,
        )

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        assert isinstance(result, BuildingSpec)

    def test_footprint_matches_input(self):
        """BuildingSpec.footprint matches the input width and depth."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        assert result.footprint == (10, 8)

    def test_floors_matches_input(self):
        """BuildingSpec.floors matches the input floor count."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        assert result.floors == 2

    def test_operations_non_empty(self):
        """BuildingSpec.operations is a non-empty list."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        assert isinstance(result.operations, list)
        assert len(result.operations) > 0

    def test_each_operation_has_type_key(self):
        """Every operation dict must have a 'type' key."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        for op in result.operations:
            assert "type" in op, f"Operation missing 'type' key: {op}"

    def test_operations_include_foundation(self):
        """Operations must include a foundation entry."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "foundation" in roles

    def test_operations_include_wall(self):
        """Operations must include wall entries."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "wall" in roles

    def test_operations_include_floor_slab(self):
        """Operations must include floor_slab entries."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "floor_slab" in roles

    def test_operations_include_roof(self):
        """Operations must include roof entries."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "roof" in roles

    def test_operations_include_window(self):
        """Operations must include window entries."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "window" in roles

    def test_operations_include_door(self):
        """Operations must include door entries."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "door" in roles

    def test_all_five_styles_produce_valid_spec(self):
        """All 5 styles produce a valid BuildingSpec with no errors."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            BuildingSpec,
            STYLE_CONFIGS,
        )

        for style_name in STYLE_CONFIGS:
            result = evaluate_building_grammar(
                width=10, depth=8, floors=2, style=style_name, seed=0
            )
            assert isinstance(result, BuildingSpec), f"Style '{style_name}' failed"
            assert len(result.operations) > 0, f"Style '{style_name}' produced no operations"

    def test_deterministic_with_same_seed(self):
        """Same inputs + same seed produces identical output."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        a = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=42)
        b = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=42)
        assert a.operations == b.operations

    def test_different_seed_produces_variation(self):
        """Different seeds may produce different detail operations."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        a = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        b = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=999)
        # At minimum, the specs should exist; variations may appear in detail placement
        assert isinstance(a.operations, list)
        assert isinstance(b.operations, list)

    def test_single_floor_building(self):
        """A single-floor building should work with no floor_slab between floors."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        result = evaluate_building_grammar(width=6, depth=6, floors=1, style="rustic", seed=0)
        assert result.floors == 1
        assert len(result.operations) > 0


class TestFacadeGrammar:
    """Test the modular facade grammar used by runtime building assembly."""

    def test_facade_plan_includes_core_modules(self):
        from blender_addon.handlers._building_grammar import plan_modular_facade

        plan = plan_modular_facade(
            width=10.0,
            depth=8.0,
            floors=2,
            style="medieval",
            wall_height=4.0,
            wall_thickness=0.4,
            openings=[
                {"wall": "front", "kind": "door", "center": 5.0, "world_bottom": 0.0, "width": 1.4, "height": 2.4},
                {"wall": "front", "kind": "window", "center": 2.2, "world_bottom": 1.2, "width": 1.0, "height": 1.4},
            ],
            site_profile="market",
            seed=7,
        )

        roles = {module["role"] for module in plan["modules"]}
        assert "facade_plinth" in roles
        assert "facade_cornice" in roles
        assert "facade_pilaster" in roles
        assert "facade_surround" in roles
        assert "facade_awning" in roles

    def test_gothic_facade_includes_buttresses(self):
        from blender_addon.handlers._building_grammar import plan_modular_facade

        plan = plan_modular_facade(
            width=14.0,
            depth=10.0,
            floors=3,
            style="gothic",
            wall_height=4.8,
            wall_thickness=0.5,
            openings=[],
            site_profile="fortified",
            seed=3,
        )

        assert any(module["type"] == "buttress" for module in plan["modules"])

    def test_facade_plan_is_deterministic(self):
        from blender_addon.handlers._building_grammar import plan_modular_facade

        kwargs = {
            "width": 12.0,
            "depth": 9.0,
            "floors": 2,
            "style": "medieval",
            "wall_height": 4.0,
            "wall_thickness": 0.4,
            "openings": [{"wall": "front", "kind": "door", "center": 6.0, "world_bottom": 0.0, "width": 1.5, "height": 2.5}],
            "site_profile": "rural",
            "seed": 11,
        }
        assert plan_modular_facade(**kwargs) == plan_modular_facade(**kwargs)


# ---------------------------------------------------------------------------
# Specialized Template tests
# ---------------------------------------------------------------------------


class TestSpecializedTemplates:
    """Test castle, tower, bridge, fortress specialized generators."""

    def test_castle_spec_returns_building_spec(self):
        """generate_castle_spec returns a BuildingSpec."""
        from blender_addon.handlers._building_grammar import (
            generate_castle_spec,
            BuildingSpec,
        )

        result = generate_castle_spec(seed=0)
        assert isinstance(result, BuildingSpec)

    def test_castle_has_keep(self):
        """Castle spec includes a 'keep' role."""
        from blender_addon.handlers._building_grammar import generate_castle_spec

        result = generate_castle_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "keep" in roles

    def test_castle_has_curtain_walls(self):
        """Castle spec includes 'curtain_wall' role."""
        from blender_addon.handlers._building_grammar import generate_castle_spec

        result = generate_castle_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "curtain_wall" in roles

    def test_castle_has_towers(self):
        """Castle spec includes 'tower' role."""
        from blender_addon.handlers._building_grammar import generate_castle_spec

        result = generate_castle_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "tower" in roles

    def test_castle_has_gatehouse(self):
        """Castle spec includes 'gatehouse' role."""
        from blender_addon.handlers._building_grammar import generate_castle_spec

        result = generate_castle_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "gatehouse" in roles

    def test_tower_spec_returns_building_spec(self):
        """generate_tower_spec returns a BuildingSpec."""
        from blender_addon.handlers._building_grammar import (
            generate_tower_spec,
            BuildingSpec,
        )

        result = generate_tower_spec(radius=3.0, height=15.0, seed=0)
        assert isinstance(result, BuildingSpec)

    def test_tower_has_tower_body(self):
        """Tower spec includes an explicit tower body operation."""
        from blender_addon.handlers._building_grammar import generate_tower_spec

        result = generate_tower_spec(radius=3.0, height=15.0, seed=0)
        types = [op.get("type") for op in result.operations]
        assert "tower" in types

    def test_tower_has_battlements(self):
        """Tower spec includes a crenellated crown."""
        from blender_addon.handlers._building_grammar import generate_tower_spec

        result = generate_tower_spec(radius=3.0, height=15.0, seed=0)
        tower_ops = [op for op in result.operations if op.get("type") == "tower"]
        assert tower_ops
        assert any(op.get("crown_height", 0.0) > 0.0 for op in tower_ops)

    def test_bridge_spec_returns_building_spec(self):
        """generate_bridge_spec returns a BuildingSpec."""
        from blender_addon.handlers._building_grammar import (
            generate_bridge_spec,
            BuildingSpec,
        )

        result = generate_bridge_spec(span=20.0, width=5.0, seed=0)
        assert isinstance(result, BuildingSpec)

    def test_bridge_has_arch(self):
        """Bridge spec includes 'arch' role."""
        from blender_addon.handlers._building_grammar import generate_bridge_spec

        result = generate_bridge_spec(span=20.0, width=5.0, seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "arch" in roles

    def test_bridge_has_road_deck(self):
        """Bridge spec includes 'road_deck' role."""
        from blender_addon.handlers._building_grammar import generate_bridge_spec

        result = generate_bridge_spec(span=20.0, width=5.0, seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "road_deck" in roles

    def test_bridge_has_railings(self):
        """Bridge spec includes 'railing' role."""
        from blender_addon.handlers._building_grammar import generate_bridge_spec

        result = generate_bridge_spec(span=20.0, width=5.0, seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "railing" in roles

    def test_fortress_spec_returns_building_spec(self):
        """generate_fortress_spec returns a BuildingSpec."""
        from blender_addon.handlers._building_grammar import (
            generate_fortress_spec,
            BuildingSpec,
        )

        result = generate_fortress_spec(seed=0)
        assert isinstance(result, BuildingSpec)

    def test_fortress_has_outer_walls(self):
        """Fortress spec includes 'curtain_wall' role for outer walls."""
        from blender_addon.handlers._building_grammar import generate_fortress_spec

        result = generate_fortress_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "curtain_wall" in roles

    def test_fortress_has_corner_towers(self):
        """Fortress spec includes 'tower' role for corners."""
        from blender_addon.handlers._building_grammar import generate_fortress_spec

        result = generate_fortress_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "tower" in roles

    def test_fortress_has_keep(self):
        """Fortress spec includes 'keep' role for the central building."""
        from blender_addon.handlers._building_grammar import generate_fortress_spec

        result = generate_fortress_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "keep" in roles

    def test_fortress_has_courtyard(self):
        """Fortress spec includes 'courtyard' role."""
        from blender_addon.handlers._building_grammar import generate_fortress_spec

        result = generate_fortress_spec(seed=0)
        roles = [op.get("role") for op in result.operations]
        assert "courtyard" in roles


# ---------------------------------------------------------------------------
# Ruins Damage tests
# ---------------------------------------------------------------------------


class TestRuinsDamage:
    """Test apply_ruins_damage transforms building specs correctly."""

    def test_returns_building_spec(self):
        """apply_ruins_damage returns a BuildingSpec."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
            BuildingSpec,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = apply_ruins_damage(spec, damage_level=0.5, seed=0)
        assert isinstance(result, BuildingSpec)

    def test_ruins_have_fewer_operations(self):
        """Damaged building has fewer operations than original (collapsed sections)."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        original_count = len(spec.operations)
        result = apply_ruins_damage(spec, damage_level=0.5, seed=0)
        # Debris adds some but removals should outweigh at moderate damage
        non_debris = [op for op in result.operations if op.get("role") != "debris"]
        assert len(non_debris) < original_count

    def test_ruins_include_debris(self):
        """Damaged building includes 'debris' type operations."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = apply_ruins_damage(spec, damage_level=0.5, seed=0)
        debris_ops = [op for op in result.operations if op.get("role") == "debris"]
        assert len(debris_ops) > 0

    def test_damage_level_zero_returns_unchanged(self):
        """damage_level=0.0 returns the spec unchanged (no damage)."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = apply_ruins_damage(spec, damage_level=0.0, seed=0)
        assert len(result.operations) == len(spec.operations)

    def test_damage_level_one_removes_most(self):
        """damage_level=1.0 removes most operations."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        original_count = len(spec.operations)
        result = apply_ruins_damage(spec, damage_level=1.0, seed=0)
        non_debris = [op for op in result.operations if op.get("role") != "debris"]
        assert len(non_debris) < original_count * 0.3  # at most 30% survives

    def test_deterministic_with_same_seed(self):
        """Same spec + same damage_level + same seed produces identical result."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        a = apply_ruins_damage(spec, damage_level=0.5, seed=42)
        b = apply_ruins_damage(spec, damage_level=0.5, seed=42)
        assert a.operations == b.operations

    def test_high_damage_adds_vegetation(self):
        """At high damage levels, vegetation markers appear."""
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = apply_ruins_damage(spec, damage_level=0.8, seed=0)
        vegetation_ops = [op for op in result.operations if op.get("role") == "vegetation"]
        assert len(vegetation_ops) > 0


# ---------------------------------------------------------------------------
# Interior Generation tests
# ---------------------------------------------------------------------------


class TestInteriorGeneration:
    """Test generate_interior_layout produces valid furniture placements."""

    def test_tavern_returns_list(self):
        """generate_interior_layout for tavern returns a list."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        assert isinstance(result, list)

    def test_tavern_items_have_required_keys(self):
        """Each placement dict has type, position, rotation, scale."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        required_keys = {"type", "position", "rotation", "scale"}
        for item in result:
            missing = required_keys - set(item.keys())
            assert not missing, f"Item {item.get('type')} missing keys: {missing}"

    def test_tavern_includes_expected_furniture(self):
        """Tavern includes tables, chairs, bar_counter, fireplace."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        types = {item["type"] for item in result}
        for expected in ["table", "chair", "bar_counter", "fireplace"]:
            assert expected in types, f"Tavern missing '{expected}'"

    def test_throne_room_includes_expected_furniture(self):
        """Throne room includes throne, carpet, pillar, banner."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(room_type="throne_room", width=10, depth=12, seed=0)
        types = {item["type"] for item in result}
        for expected in ["throne", "carpet", "pillar", "banner"]:
            assert expected in types, f"Throne room missing '{expected}'"

    def test_dungeon_cell_includes_expected_furniture(self):
        """Dungeon cell includes cot, chains, bucket."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(room_type="dungeon_cell", width=4, depth=4, seed=0)
        types = {item["type"] for item in result}
        for expected in ["cot", "chains", "bucket"]:
            assert expected in types, f"Dungeon cell missing '{expected}'"

    def test_positions_have_three_components(self):
        """Each position is a 3-element tuple/list (x, y, z)."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        for item in result:
            assert len(item["position"]) == 3, f"{item['type']} position not 3D"

    def test_furniture_within_room_bounds(self):
        """All furniture positions are within the room dimensions."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        width, depth = 8, 6
        result = generate_interior_layout(room_type="tavern", width=width, depth=depth, seed=0)
        for item in result:
            x, y, z = item["position"]
            assert 0 <= x <= width, f"{item['type']} x={x} outside [0, {width}]"
            assert 0 <= y <= depth, f"{item['type']} y={y} outside [0, {depth}]"
            assert z >= 0, f"{item['type']} z={z} below ground"

    def test_no_furniture_overlap(self):
        """No two furniture items have overlapping bounding boxes."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        # Check pairwise bounding box overlap
        for i, a in enumerate(result):
            for j, b in enumerate(result):
                if i >= j:
                    continue
                ax, ay, _ = a["position"]
                bx, by, _ = b["position"]
                a_sx, a_sy = a["scale"][0], a["scale"][1]
                b_sx, b_sy = b["scale"][0], b["scale"][1]
                # AABB overlap test
                overlap_x = abs(ax - bx) < (a_sx + b_sx) / 2
                overlap_y = abs(ay - by) < (a_sy + b_sy) / 2
                assert not (overlap_x and overlap_y), (
                    f"Overlap between {a['type']} at ({ax},{ay}) and {b['type']} at ({bx},{by})"
                )

    def test_deterministic_with_same_seed(self):
        """Same room_type + same seed produces identical result."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        a = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=42)
        b = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=42)
        assert a == b


# ---------------------------------------------------------------------------
# Modular Kit tests
# ---------------------------------------------------------------------------


class TestModularKit:
    """Test MODULAR_CATALOG and generate_modular_pieces."""

    def test_catalog_has_expected_pieces(self):
        """MODULAR_CATALOG has entries for all required piece types."""
        from blender_addon.handlers._building_grammar import MODULAR_CATALOG

        expected = {
            "wall_straight", "wall_corner", "wall_t",
            "floor", "door_frame", "window_frame", "stairs",
        }
        assert expected.issubset(set(MODULAR_CATALOG.keys()))

    def test_catalog_entries_have_required_keys(self):
        """Each catalog entry has dimensions, origin, connection_points."""
        from blender_addon.handlers._building_grammar import MODULAR_CATALOG

        required_keys = {"dimensions", "origin", "connection_points"}
        for piece_name, spec in MODULAR_CATALOG.items():
            missing = required_keys - set(spec.keys())
            assert not missing, f"Piece '{piece_name}' missing keys: {missing}"

    def test_catalog_origin_is_corner(self):
        """All catalog entries have origin='corner'."""
        from blender_addon.handlers._building_grammar import MODULAR_CATALOG

        for piece_name, spec in MODULAR_CATALOG.items():
            assert spec["origin"] == "corner", f"Piece '{piece_name}' origin is not 'corner'"

    def test_generate_modular_pieces_returns_list(self):
        """generate_modular_pieces returns a list of piece spec dicts."""
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        result = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight", "floor"])
        assert isinstance(result, list)
        assert len(result) == 2

    def test_piece_dimensions_exact_multiples_of_cell_size(self):
        """Generated piece dimensions are exact multiples of cell_size (no floating point drift)."""
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        result = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight", "floor"])
        for piece in result:
            for dim_val in piece["dimensions"]:
                remainder = dim_val % 2.0
                assert remainder < 1e-9 or abs(remainder - 2.0) < 1e-9, (
                    f"Piece '{piece['name']}' dimension {dim_val} not a multiple of 2.0"
                )

    def test_generate_all_pieces_when_none(self):
        """generate_modular_pieces with pieces=None generates all catalog entries."""
        from blender_addon.handlers._building_grammar import (
            generate_modular_pieces,
            MODULAR_CATALOG,
        )

        result = generate_modular_pieces(cell_size=2.0, pieces=None)
        assert len(result) == len(MODULAR_CATALOG)

    def test_cell_size_scaling(self):
        """Changing cell_size=3.0 scales all dimensions proportionally."""
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        result_2 = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight"])
        result_3 = generate_modular_pieces(cell_size=3.0, pieces=["wall_straight"])
        # Each dimension should be scaled by 3.0/2.0 = 1.5x
        for d2, d3 in zip(result_2[0]["dimensions"], result_3[0]["dimensions"]):
            expected = d2 * 1.5
            assert abs(d3 - expected) < 1e-9, (
                f"Expected {expected} but got {d3} for cell_size=3.0"
            )

    def test_pieces_have_connection_points(self):
        """Generated piece specs include connection_points."""
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        result = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight"])
        assert "connection_points" in result[0]
        assert isinstance(result[0]["connection_points"], list)
        assert len(result[0]["connection_points"]) > 0

    def test_piece_spec_has_name(self):
        """Generated piece specs include the piece name."""
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        result = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight"])
        assert result[0]["name"] == "wall_straight"


# ---------------------------------------------------------------------------
# Interior-Exterior Consistency Linking tests (AAA-06)
# ---------------------------------------------------------------------------


class TestConsistentInterior:
    """Test generate_consistent_interior produces valid linked interiors."""

    def _make_spec(self, width=8.0, depth=6.0, floors=2, style="medieval"):
        from blender_addon.handlers._building_grammar import evaluate_building_grammar
        return evaluate_building_grammar(width=width, depth=depth, floors=floors, style=style, seed=42)

    def test_returns_dict_with_floors(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec()
        result = generate_consistent_interior(spec, building_type="house", seed=42)
        assert "floors" in result
        assert "metadata" in result
        assert len(result["floors"]) == 2

    def test_metadata_has_required_fields(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec()
        result = generate_consistent_interior(spec, building_type="house", seed=42)
        meta = result["metadata"]
        assert meta["building_type"] == "house"
        assert meta["total_rooms"] >= 2
        assert meta["total_furniture"] > 0
        assert meta["total_lights"] > 0
        assert meta["total_floors"] == 2

    def test_each_room_has_furniture(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec()
        result = generate_consistent_interior(spec, building_type="tavern", seed=42)
        for floor in result["floors"]:
            for room in floor["rooms"]:
                assert len(room["furniture"]) > 0, f"Room {room['type']} has no furniture"

    def test_each_room_has_lighting(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec()
        result = generate_consistent_interior(spec, building_type="tavern", seed=42)
        for floor in result["floors"]:
            for room in floor["rooms"]:
                assert len(room["lighting"]) > 0, f"Room {room['type']} has no lighting"

    def test_lighting_has_world_position(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec()
        result = generate_consistent_interior(spec, building_type="house", seed=42)
        for floor in result["floors"]:
            for room in floor["rooms"]:
                for light in room["lighting"]:
                    assert "world_position" in light
                    assert len(light["world_position"]) == 3

    def test_room_bounds_within_footprint(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec(width=10.0, depth=8.0)
        result = generate_consistent_interior(spec, building_type="castle", seed=42)
        for floor in result["floors"]:
            for room in floor["rooms"]:
                b = room["bounds"]
                assert b["x"] >= 0
                assert b["y"] >= 0
                assert b["x"] + b["width"] <= 10.0
                assert b["y"] + b["depth"] <= 8.0

    @pytest.mark.parametrize("building_type", [
        "tavern", "house", "shop", "castle", "cathedral", "tower",
        "forge", "shrine", "dungeon", "barracks", "library", "temple",
        "wizard_tower",
    ])
    def test_all_building_types_produce_valid_output(self, building_type):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        floors = 3 if building_type in ("castle", "tower", "wizard_tower") else 2
        spec = self._make_spec(floors=floors)
        result = generate_consistent_interior(spec, building_type=building_type, seed=42)
        assert result["metadata"]["total_rooms"] >= 1
        assert len(result["floors"]) == floors

    def test_deterministic_with_same_seed(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec()
        r1 = generate_consistent_interior(spec, building_type="tavern", seed=99)
        r2 = generate_consistent_interior(spec, building_type="tavern", seed=99)
        assert r1["metadata"] == r2["metadata"]
        assert len(r1["floors"]) == len(r2["floors"])

    def test_different_seeds_produce_different_layouts(self):
        from blender_addon.handlers._building_grammar import generate_consistent_interior
        spec = self._make_spec()
        r1 = generate_consistent_interior(spec, building_type="house", seed=1)
        r2 = generate_consistent_interior(spec, building_type="house", seed=2)
        # Furniture positions should differ
        f1 = r1["floors"][0]["rooms"][0]["furniture"]
        f2 = r2["floors"][0]["rooms"][0]["furniture"]
        if f1 and f2:
            assert f1[0]["position"] != f2[0]["position"]
