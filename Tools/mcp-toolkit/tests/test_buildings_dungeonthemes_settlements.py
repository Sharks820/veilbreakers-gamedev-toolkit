"""Tests for Task #43 (building generators), #48 (dungeon themes), #47 (settlement templates).

Validates:
- 5 new building mesh generators with all style variants
- 10 dungeon themes with accessor/application functions
- 8 settlement templates with spec generation
"""

from __future__ import annotations

import pytest

# ---- Task #43: Building mesh generators ----
from blender_addon.handlers.procedural_meshes import (
    generate_mine_entrance_mesh,
    generate_sewer_tunnel_mesh,
    generate_catacomb_mesh,
    generate_temple_mesh,
    generate_harbor_dock_mesh,
    GENERATORS,
)

# ---- Task #48: Dungeon themes ----
from blender_addon.handlers.dungeon_themes import (
    DUNGEON_THEMES,
    THEME_NAMES,
    get_dungeon_theme,
    list_themes,
    apply_theme_to_dungeon,
    get_theme_props,
    get_theme_material,
)

# ---- Task #47: Settlement templates ----
from blender_addon.handlers.worldbuilding_layout import (
    SETTLEMENT_TEMPLATES,
    SETTLEMENT_NAMES,
    get_settlement_template,
    list_settlement_types,
    generate_settlement_spec,
    generate_location_spec,
)


# ---------------------------------------------------------------------------
# Shared validation helper
# ---------------------------------------------------------------------------


def validate_mesh_spec(result: dict, name: str, min_verts: int = 4, min_faces: int = 1):
    """Validate a mesh spec dict has all required fields and valid data."""
    assert "vertices" in result, f"{name}: missing 'vertices'"
    assert "faces" in result, f"{name}: missing 'faces'"
    assert "uvs" in result, f"{name}: missing 'uvs'"
    assert "metadata" in result, f"{name}: missing 'metadata'"

    verts = result["vertices"]
    faces = result["faces"]
    meta = result["metadata"]

    assert len(verts) >= min_verts, (
        f"{name}: expected >= {min_verts} vertices, got {len(verts)}"
    )
    assert len(faces) >= min_faces, (
        f"{name}: expected >= {min_faces} faces, got {len(faces)}"
    )

    n_verts = len(verts)
    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components, expected 3"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{name}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    assert "name" in meta, f"{name}: metadata missing 'name'"
    assert "poly_count" in meta, f"{name}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{name}: metadata missing 'vertex_count'"
    assert "dimensions" in meta, f"{name}: metadata missing 'dimensions'"

    assert meta["poly_count"] == len(faces), (
        f"{name}: poly_count {meta['poly_count']} != actual {len(faces)}"
    )
    assert meta["vertex_count"] == len(verts), (
        f"{name}: vertex_count {meta['vertex_count']} != actual {len(verts)}"
    )

    dims = meta["dimensions"]
    assert "width" in dims and "height" in dims and "depth" in dims
    for dim_name, val in dims.items():
        assert val >= 0, f"{name}: dimension '{dim_name}' is negative: {val}"

    return True


# ===========================================================================
# TASK #43: Building Mesh Generators
# ===========================================================================


class TestMineEntrance:
    """Test mine entrance mesh generator with 3 styles."""

    @pytest.mark.parametrize("style", ["timber", "stone", "abandoned"])
    def test_style_produces_valid_mesh(self, style):
        result = generate_mine_entrance_mesh(style=style)
        validate_mesh_spec(result, f"MineEntrance_{style}", min_verts=20)

    def test_default_style_is_timber(self):
        result = generate_mine_entrance_mesh()
        assert result["metadata"]["name"] == "MineEntrance_timber"

    def test_category_is_building(self):
        result = generate_mine_entrance_mesh()
        assert result["metadata"]["category"] == "building"

    def test_different_styles_produce_different_geometry(self):
        timber = generate_mine_entrance_mesh(style="timber")
        stone = generate_mine_entrance_mesh(style="stone")
        abandoned = generate_mine_entrance_mesh(style="abandoned")
        counts = {
            timber["metadata"]["vertex_count"],
            stone["metadata"]["vertex_count"],
            abandoned["metadata"]["vertex_count"],
        }
        # At least 2 of the 3 styles should have different vertex counts
        assert len(counts) >= 2, "Different styles should produce different geometry"

    def test_timber_has_mine_cart(self):
        """Timber style should include cart (more geometry than stone)."""
        result = generate_mine_entrance_mesh(style="timber")
        # Timber has support beams + tracks + cart, so more geometry
        assert result["metadata"]["poly_count"] > 20

    def test_abandoned_has_rubble(self):
        result = generate_mine_entrance_mesh(style="abandoned")
        assert result["metadata"]["poly_count"] > 10


class TestSewerTunnel:
    """Test sewer tunnel mesh generator with 3 styles."""

    @pytest.mark.parametrize("style", ["brick", "stone", "collapsed"])
    def test_style_produces_valid_mesh(self, style):
        result = generate_sewer_tunnel_mesh(style=style)
        validate_mesh_spec(result, f"SewerTunnel_{style}", min_verts=20)

    def test_default_style_is_brick(self):
        result = generate_sewer_tunnel_mesh()
        assert result["metadata"]["name"] == "SewerTunnel_brick"

    def test_category_is_building(self):
        result = generate_sewer_tunnel_mesh()
        assert result["metadata"]["category"] == "building"

    def test_different_styles_produce_different_geometry(self):
        brick = generate_sewer_tunnel_mesh(style="brick")
        stone = generate_sewer_tunnel_mesh(style="stone")
        collapsed = generate_sewer_tunnel_mesh(style="collapsed")
        counts = {
            brick["metadata"]["vertex_count"],
            stone["metadata"]["vertex_count"],
            collapsed["metadata"]["vertex_count"],
        }
        assert len(counts) >= 2

    def test_brick_has_water_channel(self):
        """Brick style should have significant geometry for channel + walkways."""
        result = generate_sewer_tunnel_mesh(style="brick")
        assert result["metadata"]["poly_count"] > 15

    def test_collapsed_has_rubble(self):
        result = generate_sewer_tunnel_mesh(style="collapsed")
        assert result["metadata"]["poly_count"] > 15


class TestCatacomb:
    """Test catacomb mesh generator with 3 styles."""

    @pytest.mark.parametrize("style", ["ossuary", "crypt", "burial_chamber"])
    def test_style_produces_valid_mesh(self, style):
        result = generate_catacomb_mesh(style=style)
        validate_mesh_spec(result, f"Catacomb_{style}", min_verts=20)

    def test_default_style_is_ossuary(self):
        result = generate_catacomb_mesh()
        assert result["metadata"]["name"] == "Catacomb_ossuary"

    def test_category_is_building(self):
        result = generate_catacomb_mesh()
        assert result["metadata"]["category"] == "building"

    def test_ossuary_has_skull_niches(self):
        """Ossuary should have many niches with skulls -- high vertex count."""
        result = generate_catacomb_mesh(style="ossuary")
        # 6 niches per side x 2 sides x 2 rows = 24 niches, each with sphere
        assert result["metadata"]["poly_count"] > 30

    def test_crypt_has_sarcophagi(self):
        result = generate_catacomb_mesh(style="crypt")
        assert result["metadata"]["poly_count"] > 15

    def test_different_styles_produce_different_geometry(self):
        ossuary = generate_catacomb_mesh(style="ossuary")
        crypt = generate_catacomb_mesh(style="crypt")
        chamber = generate_catacomb_mesh(style="burial_chamber")
        counts = {
            ossuary["metadata"]["vertex_count"],
            crypt["metadata"]["vertex_count"],
            chamber["metadata"]["vertex_count"],
        }
        assert len(counts) >= 2


class TestTemple:
    """Test temple mesh generator with 3 styles."""

    @pytest.mark.parametrize("style", ["gothic", "ancient", "ruined"])
    def test_style_produces_valid_mesh(self, style):
        result = generate_temple_mesh(style=style)
        validate_mesh_spec(result, f"Temple_{style}", min_verts=30)

    def test_default_style_is_gothic(self):
        result = generate_temple_mesh()
        assert result["metadata"]["name"] == "Temple_gothic"

    def test_category_is_building(self):
        result = generate_temple_mesh()
        assert result["metadata"]["category"] == "building"

    def test_gothic_has_columns_and_roof(self):
        """Gothic temple should have nave columns and pointed roof."""
        result = generate_temple_mesh(style="gothic")
        # 2 rows x 5 columns each = 10 cylinders + walls + roof
        assert result["metadata"]["poly_count"] > 30

    def test_ancient_has_peristyle_columns(self):
        result = generate_temple_mesh(style="ancient")
        assert result["metadata"]["poly_count"] > 30

    def test_ruined_has_rubble(self):
        result = generate_temple_mesh(style="ruined")
        assert result["metadata"]["poly_count"] > 20

    def test_different_styles_produce_different_geometry(self):
        gothic = generate_temple_mesh(style="gothic")
        ancient = generate_temple_mesh(style="ancient")
        ruined = generate_temple_mesh(style="ruined")
        counts = {
            gothic["metadata"]["vertex_count"],
            ancient["metadata"]["vertex_count"],
            ruined["metadata"]["vertex_count"],
        }
        assert len(counts) >= 2


class TestHarborDock:
    """Test harbor dock complex mesh generator with 3 styles."""

    @pytest.mark.parametrize("style", ["wooden", "stone", "fortified"])
    def test_style_produces_valid_mesh(self, style):
        result = generate_harbor_dock_mesh(style=style)
        validate_mesh_spec(result, f"HarborDock_{style}", min_verts=30)

    def test_default_style_is_wooden(self):
        result = generate_harbor_dock_mesh()
        assert result["metadata"]["name"] == "HarborDock_wooden"

    def test_category_is_building(self):
        result = generate_harbor_dock_mesh()
        assert result["metadata"]["category"] == "building"

    def test_wooden_has_berths_and_crane(self):
        """Wooden dock should have berth fingers + crane + warehouse."""
        result = generate_harbor_dock_mesh(style="wooden")
        assert result["metadata"]["poly_count"] > 40

    def test_fortified_has_towers(self):
        result = generate_harbor_dock_mesh(style="fortified")
        assert result["metadata"]["poly_count"] > 30

    def test_different_styles_produce_different_geometry(self):
        wooden = generate_harbor_dock_mesh(style="wooden")
        stone = generate_harbor_dock_mesh(style="stone")
        fortified = generate_harbor_dock_mesh(style="fortified")
        counts = {
            wooden["metadata"]["vertex_count"],
            stone["metadata"]["vertex_count"],
            fortified["metadata"]["vertex_count"],
        }
        assert len(counts) >= 2


class TestBuildingRegistry:
    """Test that all building generators are registered in GENERATORS."""

    def test_building_category_exists(self):
        assert "building" in GENERATORS

    def test_all_five_building_types_registered(self):
        building_gen = GENERATORS["building"]
        expected = {"mine_entrance", "sewer_tunnel", "catacomb", "temple", "harbor_dock"}
        assert expected.issubset(set(building_gen.keys()))

    def test_registered_generators_are_callable(self):
        for name, gen in GENERATORS["building"].items():
            assert callable(gen), f"GENERATORS['building']['{name}'] is not callable"

    def test_registered_generators_produce_valid_output(self):
        for name, gen in GENERATORS["building"].items():
            result = gen()
            validate_mesh_spec(result, name)


# ===========================================================================
# TASK #48: Dungeon Themes
# ===========================================================================


class TestDungeonThemeDefinitions:
    """Test DUNGEON_THEMES dict completeness and structure."""

    EXPECTED_THEMES = [
        "prison", "tomb", "natural_cave", "mine", "sewer",
        "library", "laboratory", "arena", "temple", "hive",
    ]

    def test_all_10_themes_defined(self):
        assert len(DUNGEON_THEMES) == 10

    @pytest.mark.parametrize("theme_name", EXPECTED_THEMES)
    def test_theme_exists(self, theme_name):
        assert theme_name in DUNGEON_THEMES

    @pytest.mark.parametrize("theme_name", EXPECTED_THEMES)
    def test_theme_has_required_keys(self, theme_name):
        theme = DUNGEON_THEMES[theme_name]
        required = {"wall_material", "floor", "props", "lighting",
                     "ambient_color", "fog_density"}
        assert required.issubset(set(theme.keys())), (
            f"Theme '{theme_name}' missing keys: {required - set(theme.keys())}"
        )

    @pytest.mark.parametrize("theme_name", EXPECTED_THEMES)
    def test_theme_props_is_nonempty_list(self, theme_name):
        props = DUNGEON_THEMES[theme_name]["props"]
        assert isinstance(props, list)
        assert len(props) >= 1

    @pytest.mark.parametrize("theme_name", EXPECTED_THEMES)
    def test_theme_ambient_color_is_rgb_tuple(self, theme_name):
        color = DUNGEON_THEMES[theme_name]["ambient_color"]
        assert isinstance(color, tuple)
        assert len(color) == 3
        for c in color:
            assert 0.0 <= c <= 1.0

    @pytest.mark.parametrize("theme_name", EXPECTED_THEMES)
    def test_theme_fog_density_in_range(self, theme_name):
        fog = DUNGEON_THEMES[theme_name]["fog_density"]
        assert isinstance(fog, (int, float))
        assert 0.0 <= fog <= 1.0


class TestGetDungeonTheme:
    """Test get_dungeon_theme accessor."""

    def test_returns_valid_theme_dict(self):
        theme = get_dungeon_theme("prison")
        assert isinstance(theme, dict)
        assert "wall_material" in theme
        assert theme["wall_material"] == "iron_bars"

    def test_returns_copy_not_reference(self):
        theme1 = get_dungeon_theme("tomb")
        theme2 = get_dungeon_theme("tomb")
        theme1["wall_material"] = "MUTATED"
        assert theme2["wall_material"] == "carved_stone"
        assert DUNGEON_THEMES["tomb"]["wall_material"] == "carved_stone"

    def test_unknown_theme_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown dungeon theme"):
            get_dungeon_theme("nonexistent_theme")


class TestListThemes:
    """Test list_themes function."""

    def test_returns_list(self):
        result = list_themes()
        assert isinstance(result, list)

    def test_returns_all_10_themes(self):
        assert len(list_themes()) == 10

    def test_returns_sorted(self):
        result = list_themes()
        assert result == sorted(result)


class TestApplyThemeToDungeon:
    """Test apply_theme_to_dungeon function."""

    def test_adds_theme_metadata(self):
        layout = {"rooms": [], "ops": []}
        result = apply_theme_to_dungeon(layout, "prison")
        assert result["theme"] == "prison"
        assert "theme_config" in result

    def test_does_not_mutate_original(self):
        layout = {"rooms": [], "ops": [{"type": "wall", "position": (0, 0, 0)}]}
        result = apply_theme_to_dungeon(layout, "prison")
        # Original ops should not have material key
        assert "material" not in layout["ops"][0]
        assert "material" in result["ops"][0]

    def test_tags_wall_ops_with_theme_material(self):
        layout = {
            "rooms": [],
            "ops": [
                {"type": "wall", "position": (0, 0, 0), "size": (2, 2, 3)},
                {"type": "floor", "position": (2, 0, 0), "size": (2, 2, 0.1)},
            ],
        }
        result = apply_theme_to_dungeon(layout, "sewer")
        wall_op = [op for op in result["ops"] if op["type"] == "wall"][0]
        floor_op = [op for op in result["ops"] if op["type"] == "floor"][0]
        assert wall_op["material"] == "wet_brick"
        assert floor_op["material"] == "water_channel"

    def test_tags_corridor_ops_with_floor_material(self):
        layout = {
            "rooms": [],
            "ops": [{"type": "corridor", "position": (0, 0, 0), "size": (2, 2, 0.1)}],
        }
        result = apply_theme_to_dungeon(layout, "library")
        assert result["ops"][0]["material"] == "wood_polish"

    def test_adds_lighting_config(self):
        layout = {"rooms": []}
        result = apply_theme_to_dungeon(layout, "temple")
        assert "lighting" in result
        assert result["lighting"]["type"] == "candle"
        assert result["lighting"]["ambient_color"] == (0.18, 0.15, 0.1)
        assert result["lighting"]["fog_density"] == 0.15

    def test_generates_themed_props_for_rooms(self):
        layout = {
            "rooms": [
                {"position": (0, 0), "size": (6, 6)},
                {"position": (10, 0), "size": (5, 5)},
            ],
        }
        result = apply_theme_to_dungeon(layout, "laboratory")
        assert "themed_props" in result
        assert len(result["themed_props"]) > 0
        # All props should be from the laboratory theme
        lab_props = {"cauldron", "workbench", "potion_bottle"}
        for prop in result["themed_props"]:
            assert prop["type"] in lab_props
            assert prop["theme"] == "laboratory"

    def test_unknown_theme_raises_valueerror(self):
        with pytest.raises(ValueError):
            apply_theme_to_dungeon({}, "fake_theme")

    def test_handles_empty_layout(self):
        result = apply_theme_to_dungeon({}, "hive")
        assert result["theme"] == "hive"
        assert "lighting" in result

    def test_deterministic_prop_placement(self):
        layout = {"rooms": [{"position": (0, 0), "size": (6, 6)}]}
        result1 = apply_theme_to_dungeon(layout, "mine")
        result2 = apply_theme_to_dungeon(layout, "mine")
        assert result1["themed_props"] == result2["themed_props"]


class TestGetThemeProps:
    """Test get_theme_props helper."""

    def test_returns_list(self):
        props = get_theme_props("prison")
        assert isinstance(props, list)

    def test_prison_props(self):
        props = get_theme_props("prison")
        assert set(props) == {"shackle", "cage", "stocks"}

    def test_hive_props(self):
        props = get_theme_props("hive")
        assert "spider_egg_sac" in props
        assert "cobweb" in props

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            get_theme_props("nonexistent")


class TestGetThemeMaterial:
    """Test get_theme_material helper."""

    def test_wall_material(self):
        assert get_theme_material("tomb", "wall") == "carved_stone"

    def test_floor_material(self):
        assert get_theme_material("tomb", "floor") == "burial_slab"

    def test_sewer_wall(self):
        assert get_theme_material("sewer", "wall") == "wet_brick"

    def test_unknown_surface_raises(self):
        with pytest.raises(ValueError, match="Unknown surface type"):
            get_theme_material("prison", "ceiling")

    def test_unknown_theme_raises(self):
        with pytest.raises(ValueError):
            get_theme_material("nonexistent", "wall")


# ===========================================================================
# TASK #47: Settlement Layout Templates
# ===========================================================================


class TestSettlementTemplateDefinitions:
    """Test SETTLEMENT_TEMPLATES dict completeness and structure."""

    EXPECTED_TYPES = [
        "fishing_village", "mining_town", "port_city", "monastery",
        "necropolis", "military_outpost", "crossroads_inn", "bandit_hideout",
    ]

    def test_all_8_templates_defined(self):
        assert len(SETTLEMENT_TEMPLATES) == 8

    @pytest.mark.parametrize("settlement_type", EXPECTED_TYPES)
    def test_template_exists(self, settlement_type):
        assert settlement_type in SETTLEMENT_TEMPLATES

    @pytest.mark.parametrize("settlement_type", EXPECTED_TYPES)
    def test_template_has_buildings_key(self, settlement_type):
        template = SETTLEMENT_TEMPLATES[settlement_type]
        assert "buildings" in template
        assert isinstance(template["buildings"], list)
        assert len(template["buildings"]) >= 1

    @pytest.mark.parametrize("settlement_type", EXPECTED_TYPES)
    def test_template_has_features_key(self, settlement_type):
        template = SETTLEMENT_TEMPLATES[settlement_type]
        assert "features" in template
        assert isinstance(template["features"], list)
        assert len(template["features"]) >= 1


class TestGetSettlementTemplate:
    """Test get_settlement_template accessor."""

    def test_returns_valid_template(self):
        template = get_settlement_template("fishing_village")
        assert "buildings" in template
        assert "features" in template
        assert "dock" in template["buildings"]

    def test_returns_copy_not_reference(self):
        t1 = get_settlement_template("mining_town")
        t2 = get_settlement_template("mining_town")
        t1["buildings"].append("MUTATED")
        assert "MUTATED" not in t2["buildings"]
        assert "MUTATED" not in SETTLEMENT_TEMPLATES["mining_town"]["buildings"]

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown settlement type"):
            get_settlement_template("space_station")


class TestListSettlementTypes:
    """Test list_settlement_types function."""

    def test_returns_list(self):
        result = list_settlement_types()
        assert isinstance(result, list)

    def test_returns_all_8_types(self):
        assert len(list_settlement_types()) == 8

    def test_returns_sorted(self):
        result = list_settlement_types()
        assert result == sorted(result)


class TestGenerateSettlementSpec:
    """Test generate_settlement_spec function."""

    EXPECTED_TYPES = [
        "fishing_village", "mining_town", "port_city", "monastery",
        "necropolis", "military_outpost", "crossroads_inn", "bandit_hideout",
    ]

    @pytest.mark.parametrize("settlement_type", EXPECTED_TYPES)
    def test_generates_valid_spec(self, settlement_type):
        spec = generate_settlement_spec(settlement_type=settlement_type, seed=42)
        assert "terrain_bounds" in spec
        assert "buildings" in spec
        assert "paths" in spec
        assert "pois" in spec
        assert "features" in spec
        assert "settlement_type" in spec
        assert spec["settlement_type"] == settlement_type

    def test_buildings_use_template_types(self):
        spec = generate_settlement_spec("fishing_village", seed=0)
        template = SETTLEMENT_TEMPLATES["fishing_village"]
        building_types = [b["type"] for b in spec["buildings"]]
        # Buildings should match template (may have fewer if placement fails)
        for bt in building_types:
            assert bt in template["buildings"]

    def test_features_populated(self):
        spec = generate_settlement_spec("mining_town", seed=0)
        assert len(spec["features"]) > 0
        feature_types = [f["type"] for f in spec["features"]]
        expected = {"ore_cart", "mine_track", "slag_heap"}
        assert set(feature_types) == expected

    def test_deterministic_with_seed(self):
        spec1 = generate_settlement_spec("port_city", seed=123)
        spec2 = generate_settlement_spec("port_city", seed=123)
        assert spec1["buildings"] == spec2["buildings"]
        assert spec1["features"] == spec2["features"]

    def test_different_seeds_produce_different_layouts(self):
        spec1 = generate_settlement_spec("monastery", seed=1)
        spec2 = generate_settlement_spec("monastery", seed=999)
        # Building positions should differ
        if spec1["buildings"] and spec2["buildings"]:
            pos1 = spec1["buildings"][0]["position"]
            pos2 = spec2["buildings"][0]["position"]
            assert pos1 != pos2

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            generate_settlement_spec("underwater_city")

    def test_template_included_in_spec(self):
        spec = generate_settlement_spec("necropolis", seed=0)
        assert "template" in spec
        assert spec["template"]["buildings"] == SETTLEMENT_TEMPLATES["necropolis"]["buildings"]

    def test_poi_count_respected(self):
        spec = generate_settlement_spec("crossroads_inn", seed=0, poi_count=5)
        assert len(spec["pois"]) == 5

    def test_features_have_positions(self):
        spec = generate_settlement_spec("military_outpost", seed=42)
        for feature in spec["features"]:
            assert "type" in feature
            assert "position" in feature
            assert len(feature["position"]) == 2


class TestLocationSpecSettlementTypes:
    """Test that generate_location_spec supports new settlement types."""

    NEW_TYPES = [
        "fishing_village", "mining_town", "port_city", "monastery",
        "necropolis", "military_outpost", "crossroads_inn", "bandit_hideout",
    ]

    @pytest.mark.parametrize("location_type", NEW_TYPES)
    def test_location_spec_accepts_new_types(self, location_type):
        spec = generate_location_spec(
            location_type=location_type,
            building_count=3,
            seed=42,
        )
        assert spec["location_type"] == location_type
        assert len(spec["buildings"]) > 0

    def test_fishing_village_has_dock_building(self):
        spec = generate_location_spec(
            location_type="fishing_village",
            building_count=5,
            seed=0,
        )
        building_types = [b["type"] for b in spec["buildings"]]
        assert "dock" in building_types

    def test_necropolis_has_catacomb(self):
        spec = generate_location_spec(
            location_type="necropolis",
            building_count=4,
            seed=0,
        )
        building_types = [b["type"] for b in spec["buildings"]]
        assert "catacomb" in building_types

    def test_military_outpost_has_watchtower(self):
        spec = generate_location_spec(
            location_type="military_outpost",
            building_count=5,
            seed=0,
        )
        building_types = [b["type"] for b in spec["buildings"]]
        assert "watchtower" in building_types
