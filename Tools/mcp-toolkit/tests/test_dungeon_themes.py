"""Tests for dungeon_themes handler."""

import pytest

from blender_addon.handlers.dungeon_themes import (
    DUNGEON_THEMES,
    THEME_NAMES,
    get_dungeon_theme,
    list_themes,
    apply_theme_to_dungeon,
    get_theme_props,
    get_theme_material,
)


# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------


class TestThemeDefinitions:
    def test_exactly_10_themes(self):
        assert len(DUNGEON_THEMES) == 10

    def test_all_themes_have_required_fields(self):
        required = {"wall_material", "floor", "props", "lighting",
                     "ambient_color", "fog_density"}
        for name, theme in DUNGEON_THEMES.items():
            missing = required - set(theme.keys())
            assert not missing, f"Theme '{name}' missing: {missing}"

    def test_ambient_color_is_rgb_tuple(self):
        for name, theme in DUNGEON_THEMES.items():
            color = theme["ambient_color"]
            assert len(color) == 3, f"Theme '{name}' ambient_color not RGB"
            for c in color:
                assert 0.0 <= c <= 1.0, f"Theme '{name}' color out of range"

    def test_fog_density_in_range(self):
        for name, theme in DUNGEON_THEMES.items():
            assert 0.0 <= theme["fog_density"] <= 1.0, \
                f"Theme '{name}' fog_density out of [0, 1]"

    def test_props_are_nonempty_lists(self):
        for name, theme in DUNGEON_THEMES.items():
            assert isinstance(theme["props"], list)
            assert len(theme["props"]) > 0, f"Theme '{name}' has no props"

    def test_theme_names_sorted(self):
        assert THEME_NAMES == sorted(DUNGEON_THEMES.keys())


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


class TestGetDungeonTheme:
    def test_valid_theme(self):
        theme = get_dungeon_theme("prison")
        assert theme["wall_material"] == "iron_bars"
        assert theme["floor"] == "cold_stone"

    def test_invalid_theme_raises(self):
        with pytest.raises(ValueError, match="Unknown dungeon theme"):
            get_dungeon_theme("nonexistent")

    def test_returns_copy(self):
        t1 = get_dungeon_theme("tomb")
        t2 = get_dungeon_theme("tomb")
        t1["wall_material"] = "modified"
        assert t2["wall_material"] == "carved_stone"


class TestListThemes:
    def test_returns_all_themes(self):
        themes = list_themes()
        assert len(themes) == 10
        assert "prison" in themes
        assert "tomb" in themes

    def test_sorted(self):
        themes = list_themes()
        assert themes == sorted(themes)


class TestGetThemeProps:
    def test_returns_props_list(self):
        props = get_theme_props("mine")
        assert isinstance(props, list)
        assert "cart" in props

    def test_invalid_theme(self):
        with pytest.raises(ValueError):
            get_theme_props("invalid")


class TestGetThemeMaterial:
    def test_wall_material(self):
        mat = get_theme_material("sewer", "wall")
        assert mat == "wet_brick"

    def test_floor_material(self):
        mat = get_theme_material("sewer", "floor")
        assert mat == "water_channel"

    def test_invalid_surface(self):
        with pytest.raises(ValueError, match="Unknown surface type"):
            get_theme_material("sewer", "ceiling")

    def test_invalid_theme(self):
        with pytest.raises(ValueError):
            get_theme_material("nonexistent", "wall")


# ---------------------------------------------------------------------------
# Theme application
# ---------------------------------------------------------------------------


class TestApplyTheme:
    def test_basic_application(self):
        layout = {"rooms": [{"center": (5, 5)}]}
        result = apply_theme_to_dungeon(layout, "prison")
        assert result["theme"] == "prison"
        assert "theme_config" in result
        assert "lighting" in result

    def test_does_not_mutate_original(self):
        layout = {"rooms": [{"center": (5, 5)}]}
        original_keys = set(layout.keys())
        apply_theme_to_dungeon(layout, "tomb")
        assert set(layout.keys()) == original_keys

    def test_ops_tagged_with_materials(self):
        layout = {
            "ops": [
                {"type": "wall", "position": (0, 0)},
                {"type": "floor", "position": (1, 1)},
                {"type": "other", "position": (2, 2)},
            ]
        }
        result = apply_theme_to_dungeon(layout, "library")
        for op in result["ops"]:
            if op["type"] == "wall":
                assert op["material"] == "bookshelf_walls"
            elif op["type"] == "floor":
                assert op["material"] == "wood_polish"
            elif op["type"] == "other":
                assert "material" not in op

    def test_themed_props_generated_for_rooms(self):
        layout = {"rooms": [
            {"center": (5, 5)},
            {"center": (15, 15)},
        ]}
        result = apply_theme_to_dungeon(layout, "mine")
        assert "themed_props" in result
        assert len(result["themed_props"]) > 0
        for prop in result["themed_props"]:
            assert prop["theme"] == "mine"
            assert "position" in prop
            assert len(prop["position"]) == 3

    def test_lighting_config(self):
        layout = {"rooms": []}
        result = apply_theme_to_dungeon(layout, "natural_cave")
        assert result["lighting"]["type"] == "bioluminescent"
        assert len(result["lighting"]["ambient_color"]) == 3

    def test_rooms_without_center_use_position(self):
        layout = {"rooms": [{"position": (2, 3), "size": (4, 6)}]}
        result = apply_theme_to_dungeon(layout, "arena")
        assert "themed_props" in result
        assert len(result["themed_props"]) > 0

    def test_invalid_theme_raises(self):
        with pytest.raises(ValueError):
            apply_theme_to_dungeon({}, "fake_theme")

    def test_deterministic_per_theme(self):
        layout = {"rooms": [{"center": (5, 5)}, {"center": (10, 10)}]}
        r1 = apply_theme_to_dungeon(layout, "hive")
        r2 = apply_theme_to_dungeon(layout, "hive")
        # Same theme => same prop placement (deterministic hash seed)
        assert r1["themed_props"] == r2["themed_props"]
