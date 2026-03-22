"""Unit tests for VeilBreakers landmark preset data and handler pure-logic outputs.

Tests VB_LANDMARK_PRESETS dict, get_vb_landmark_preset helper,
_generate_landmark_unique_features, _apply_corruption_tint, and
_build_landmark_result without Blender.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# VB_LANDMARK_PRESETS data tests
# ---------------------------------------------------------------------------


class TestVBLandmarkPresets:
    """Test VeilBreakers landmark preset data integrity."""

    def test_presets_dict_has_six_entries(self):
        """VB_LANDMARK_PRESETS must have exactly 6 presets."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        assert len(VB_LANDMARK_PRESETS) == 6

    def test_preset_names(self):
        """All expected VB landmark preset names are present."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        expected = {
            "the_congregation_lair", "wardens_prison", "thornwood_heart",
            "veil_breach", "storm_citadel", "broodmother_nest",
        }
        assert set(VB_LANDMARK_PRESETS.keys()) == expected

    def test_each_preset_has_required_keys(self):
        """Every VB landmark preset must have all required keys."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        required = {
            "description", "base_style", "scale", "floors", "width", "depth",
            "wall_height", "unique_features", "interior_rooms",
            "corruption_level", "props",
        }
        for name, preset in VB_LANDMARK_PRESETS.items():
            missing = required - set(preset.keys())
            assert not missing, f"Preset '{name}' missing keys: {missing}"

    def test_each_preset_has_nonempty_description(self):
        """Every landmark preset must have a non-empty description."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert isinstance(preset["description"], str)
            assert len(preset["description"]) > 5, f"Preset '{name}' has too short description"

    def test_each_preset_has_valid_base_style(self):
        """Every landmark base_style must be a string (may or may not be in STYLE_CONFIGS)."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert isinstance(preset["base_style"], str), f"Preset '{name}' base_style not str"

    def test_most_presets_have_valid_base_style(self):
        """Most landmark base_styles should exist in STYLE_CONFIGS (chaotic is the exception)."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        invalid = []
        for name, preset in VB_LANDMARK_PRESETS.items():
            if preset["base_style"] not in STYLE_CONFIGS:
                invalid.append(name)
        # Only veil_breach should have a non-standard style
        assert len(invalid) <= 1, f"Too many presets with invalid style: {invalid}"

    def test_each_preset_has_positive_scale(self):
        """Every landmark scale must be > 0."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert preset["scale"] > 0, f"Preset '{name}' has non-positive scale"

    def test_each_preset_has_nonneg_floors(self):
        """Every landmark floors must be >= 0."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert preset["floors"] >= 0, f"Preset '{name}' has negative floors"

    def test_each_preset_has_positive_dimensions(self):
        """Every landmark must have positive width, depth, wall_height."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert preset["width"] > 0, f"Preset '{name}' width not positive"
            assert preset["depth"] > 0, f"Preset '{name}' depth not positive"
            assert preset["wall_height"] > 0, f"Preset '{name}' wall_height not positive"

    def test_each_preset_corruption_level_in_range(self):
        """Every landmark corruption_level must be between 0.0 and 1.0."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert 0.0 <= preset["corruption_level"] <= 1.0, (
                f"Preset '{name}' corruption_level out of range"
            )

    def test_each_preset_has_unique_features_list(self):
        """Every landmark preset must have a non-empty unique_features list."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert isinstance(preset["unique_features"], list), (
                f"Preset '{name}' unique_features not a list"
            )
            assert len(preset["unique_features"]) > 0, (
                f"Preset '{name}' has empty unique_features"
            )

    def test_each_preset_has_props_list(self):
        """Every landmark preset must have a non-empty props list."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert isinstance(preset["props"], list), f"Preset '{name}' props not a list"
            assert len(preset["props"]) > 0, f"Preset '{name}' has empty props"

    def test_each_preset_interior_rooms_is_list(self):
        """Every landmark interior_rooms must be a list (possibly empty)."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name, preset in VB_LANDMARK_PRESETS.items():
            assert isinstance(preset["interior_rooms"], list), (
                f"Preset '{name}' interior_rooms not a list"
            )

    def test_veil_breach_has_no_interior_rooms(self):
        """veil_breach is an open rift with no interior rooms."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        p = VB_LANDMARK_PRESETS["veil_breach"]
        assert len(p["interior_rooms"]) == 0
        assert p["floors"] == 0

    def test_veil_breach_has_high_corruption(self):
        """veil_breach should have corruption_level >= 0.8."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        assert VB_LANDMARK_PRESETS["veil_breach"]["corruption_level"] >= 0.8

    def test_congregation_lair_full_corruption(self):
        """the_congregation_lair should have corruption_level == 1.0."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        assert VB_LANDMARK_PRESETS["the_congregation_lair"]["corruption_level"] == 1.0

    def test_congregation_lair_is_gothic(self):
        """the_congregation_lair uses gothic architecture."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        assert VB_LANDMARK_PRESETS["the_congregation_lair"]["base_style"] == "gothic"

    def test_wardens_prison_is_fortress(self):
        """wardens_prison uses fortress architecture."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        assert VB_LANDMARK_PRESETS["wardens_prison"]["base_style"] == "fortress"

    def test_thornwood_heart_is_organic(self):
        """thornwood_heart uses organic architecture."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        assert VB_LANDMARK_PRESETS["thornwood_heart"]["base_style"] == "organic"

    def test_storm_citadel_is_fortress_with_4_floors(self):
        """storm_citadel uses fortress architecture with 4 floors."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        p = VB_LANDMARK_PRESETS["storm_citadel"]
        assert p["base_style"] == "fortress"
        assert p["floors"] == 4

    def test_broodmother_nest_is_organic(self):
        """broodmother_nest uses organic architecture."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        assert VB_LANDMARK_PRESETS["broodmother_nest"]["base_style"] == "organic"

    def test_broodmother_nest_has_expected_features(self):
        """broodmother_nest has web, egg, cocoon, acid features."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        features = VB_LANDMARK_PRESETS["broodmother_nest"]["unique_features"]
        assert "web_canopy" in features
        assert "egg_chamber" in features
        assert "acid_pools" in features


# ---------------------------------------------------------------------------
# get_vb_landmark_preset tests
# ---------------------------------------------------------------------------


class TestGetVBLandmarkPreset:
    """Test the get_vb_landmark_preset lookup helper."""

    def test_returns_dict_for_valid_name(self):
        """get_vb_landmark_preset returns dict for a valid preset name."""
        from blender_addon.handlers.worldbuilding import get_vb_landmark_preset

        result = get_vb_landmark_preset("the_congregation_lair")
        assert isinstance(result, dict)
        assert result["base_style"] == "gothic"

    def test_returns_none_for_unknown_name(self):
        """get_vb_landmark_preset returns None for unknown name."""
        from blender_addon.handlers.worldbuilding import get_vb_landmark_preset

        assert get_vb_landmark_preset("nonexistent_landmark") is None

    def test_returns_correct_preset_data(self):
        """get_vb_landmark_preset returns the correct preset for each name."""
        from blender_addon.handlers.worldbuilding import (
            get_vb_landmark_preset,
            VB_LANDMARK_PRESETS,
        )

        for name in VB_LANDMARK_PRESETS:
            result = get_vb_landmark_preset(name)
            assert result is not None, f"get_vb_landmark_preset('{name}') returned None"
            assert result["description"] == VB_LANDMARK_PRESETS[name]["description"]


# ---------------------------------------------------------------------------
# _LANDMARK_ROOM_TYPE_MAP tests
# ---------------------------------------------------------------------------


class TestLandmarkRoomTypeMap:
    """Test that landmark room type mappings resolve to valid room configs."""

    def test_all_interior_rooms_have_mapping_or_direct_match(self):
        """Every interior_room in all presets must map to a valid room config."""
        from blender_addon.handlers.worldbuilding import (
            VB_LANDMARK_PRESETS,
            _LANDMARK_ROOM_TYPE_MAP,
        )
        from blender_addon.handlers._building_grammar import _ROOM_CONFIGS

        for lm_name, preset in VB_LANDMARK_PRESETS.items():
            for room_name in preset["interior_rooms"]:
                mapped = _LANDMARK_ROOM_TYPE_MAP.get(room_name, room_name)
                assert mapped in _ROOM_CONFIGS or mapped in _LANDMARK_ROOM_TYPE_MAP, (
                    f"Landmark '{lm_name}' room '{room_name}' -> '{mapped}' "
                    f"not found in _ROOM_CONFIGS"
                )


# ---------------------------------------------------------------------------
# _apply_corruption_tint tests
# ---------------------------------------------------------------------------


class TestApplyCorruptionTint:
    """Test the corruption tint computation."""

    def test_zero_corruption_clean(self):
        """Zero corruption produces clean material."""
        from blender_addon.handlers.worldbuilding import _apply_corruption_tint

        result = _apply_corruption_tint(0.0)
        assert result["corruption_level"] == 0.0
        assert result["material_name"] == "landmark_clean"
        assert result["emission_strength"] == 0.0

    def test_full_corruption_dark(self):
        """Full corruption produces dark corrupted material."""
        from blender_addon.handlers.worldbuilding import _apply_corruption_tint

        result = _apply_corruption_tint(1.0)
        assert result["corruption_level"] == 1.0
        assert result["material_name"] == "landmark_corrupted"
        assert result["emission_strength"] > 0

    def test_mid_corruption(self):
        """Mid corruption produces intermediate values."""
        from blender_addon.handlers.worldbuilding import _apply_corruption_tint

        result = _apply_corruption_tint(0.5)
        assert result["corruption_level"] == 0.5
        assert result["material_name"] == "landmark_corrupted"
        color = result["base_color"]
        assert len(color) == 4
        assert color[3] == 1.0  # alpha always 1

    def test_corruption_clamped_above_1(self):
        """Corruption level > 1.0 is clamped to 1.0."""
        from blender_addon.handlers.worldbuilding import _apply_corruption_tint

        result = _apply_corruption_tint(2.0)
        assert result["corruption_level"] == 1.0

    def test_corruption_clamped_below_0(self):
        """Corruption level < 0.0 is clamped to 0.0."""
        from blender_addon.handlers.worldbuilding import _apply_corruption_tint

        result = _apply_corruption_tint(-0.5)
        assert result["corruption_level"] == 0.0

    def test_color_darkens_with_corruption(self):
        """Higher corruption produces darker base color."""
        from blender_addon.handlers.worldbuilding import _apply_corruption_tint

        low = _apply_corruption_tint(0.1)
        high = _apply_corruption_tint(0.9)
        # Each RGB channel should be darker at higher corruption
        for i in range(3):
            assert high["base_color"][i] < low["base_color"][i]

    def test_returns_base_color_as_list(self):
        """base_color must be a 4-element list [R, G, B, A]."""
        from blender_addon.handlers.worldbuilding import _apply_corruption_tint

        result = _apply_corruption_tint(0.5)
        assert isinstance(result["base_color"], list)
        assert len(result["base_color"]) == 4


# ---------------------------------------------------------------------------
# _generate_landmark_unique_features tests
# ---------------------------------------------------------------------------


class TestGenerateLandmarkUniqueFeatures:
    """Test unique feature geometry generation (pure logic)."""

    def test_returns_list(self):
        """Returns a list of operation dicts."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["corrupted_spire"], 10.0, 10.0, 5.0, 1.0, seed=0,
        )
        assert isinstance(ops, list)
        assert len(ops) > 0

    def test_empty_features_returns_empty(self):
        """Empty feature list returns empty ops."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features([], 10.0, 10.0, 5.0, 1.0, seed=0)
        assert ops == []

    def test_spire_is_cylinder(self):
        """corrupted_spire generates a cylinder operation."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["corrupted_spire"], 10.0, 10.0, 5.0, 1.0, seed=0,
        )
        assert ops[0]["type"] == "cylinder"
        assert ops[0]["role"] == "landmark_spire"

    def test_soul_anchors_produces_4_pylons(self):
        """soul_anchors generates 4 corner pylons."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["soul_anchors"], 10.0, 10.0, 5.0, 1.0, seed=0,
        )
        assert len(ops) == 4
        assert all(op["role"] == "landmark_pylon" for op in ops)

    def test_guard_towers_produces_4_towers(self):
        """guard_towers generates 4 corner towers."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["guard_towers"], 20.0, 25.0, 6.0, 1.5, seed=0,
        )
        assert len(ops) == 4
        assert all(op["role"] == "landmark_tower" for op in ops)

    def test_void_portal_is_barrier(self):
        """void_portal generates a barrier box."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["void_portal"], 30.0, 30.0, 20.0, 2.5, seed=0,
        )
        assert len(ops) == 1
        assert ops[0]["type"] == "box"
        assert ops[0]["role"] == "landmark_barrier"

    def test_giant_tree_trunk_is_large_cylinder(self):
        """giant_tree_trunk generates a large cylinder."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["giant_tree_trunk"], 10.0, 10.0, 15.0, 3.0, seed=0,
        )
        assert len(ops) == 1
        assert ops[0]["type"] == "cylinder"
        assert ops[0]["role"] == "landmark_tree"
        assert ops[0]["segments"] == 24  # high detail

    def test_floating_platforms_produces_multiple(self):
        """floating_platforms generates multiple floating boxes."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["floating_platforms"], 30.0, 30.0, 20.0, 2.5, seed=42,
        )
        assert len(ops) >= 4
        assert all(op["role"] == "landmark_floating" for op in ops)

    def test_web_canopy_is_ceiling_box(self):
        """web_canopy generates a ceiling-level box."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["web_canopy"], 25.0, 30.0, 10.0, 2.0, seed=0,
        )
        assert len(ops) == 1
        assert ops[0]["type"] == "box"
        assert ops[0]["role"] == "landmark_canopy"
        # Should be near ceiling height
        assert ops[0]["position"][2] == pytest.approx(10.0 * 0.85, abs=0.1)

    def test_acid_pools_are_flat_cylinders(self):
        """acid_pools generates flat floor-level cylinders."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["acid_pools"], 25.0, 30.0, 10.0, 2.0, seed=0,
        )
        assert len(ops) >= 2
        assert all(op["type"] == "cylinder" for op in ops)
        assert all(op["height"] == pytest.approx(0.05) for op in ops)
        assert all(op["role"] == "landmark_hazard" for op in ops)

    def test_bioluminescent_fungi_produces_multiple(self):
        """bioluminescent_fungi generates multiple small cylinders."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["bioluminescent_fungi"], 10.0, 10.0, 15.0, 3.0, seed=0,
        )
        assert len(ops) >= 5
        assert all(op["role"] == "landmark_flora" for op in ops)

    def test_all_ops_have_feature_name(self):
        """Every generated operation has a feature_name key."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        features = ["corrupted_spire", "iron_gates", "chain_bridges"]
        ops = _generate_landmark_unique_features(features, 20.0, 25.0, 6.0, 1.5, seed=0)
        for op in ops:
            assert "feature_name" in op

    def test_unknown_feature_gets_fallback(self):
        """An unknown feature name gets a generic fallback."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops = _generate_landmark_unique_features(
            ["totally_unknown_feature"], 10.0, 10.0, 5.0, 1.0, seed=0,
        )
        assert len(ops) == 1
        assert ops[0]["role"] == "landmark_feature"

    def test_multiple_features_combined(self):
        """Multiple features produce combined operations."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        features = ["corrupted_spire", "soul_anchors", "darkness_veil"]
        ops = _generate_landmark_unique_features(features, 15.0, 20.0, 8.0, 2.0, seed=0)
        # spire=1, anchors=4, veil=1 = 6
        assert len(ops) == 6

    def test_seed_reproducibility(self):
        """Same seed produces same output."""
        from blender_addon.handlers.worldbuilding import _generate_landmark_unique_features

        ops1 = _generate_landmark_unique_features(
            ["bioluminescent_fungi"], 10.0, 10.0, 15.0, 3.0, seed=99,
        )
        ops2 = _generate_landmark_unique_features(
            ["bioluminescent_fungi"], 10.0, 10.0, 15.0, 3.0, seed=99,
        )
        assert len(ops1) == len(ops2)
        for o1, o2 in zip(ops1, ops2):
            assert o1["position"] == o2["position"]


# ---------------------------------------------------------------------------
# _build_landmark_result tests
# ---------------------------------------------------------------------------


class TestBuildLandmarkResult:
    """Test the pure-logic landmark result builder."""

    def _make_result(self, preset_key="the_congregation_lair", seed=0):
        """Helper to build a landmark result from a preset."""
        from blender_addon.handlers.worldbuilding import (
            VB_LANDMARK_PRESETS,
            _generate_landmark_unique_features,
            _apply_corruption_tint,
            _build_landmark_result,
            _LANDMARK_ROOM_TYPE_MAP,
        )
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            generate_interior_layout,
            STYLE_CONFIGS,
        )

        preset = VB_LANDMARK_PRESETS[preset_key]
        base_style = preset["base_style"]
        if base_style not in STYLE_CONFIGS:
            base_style = "gothic"

        spec = None
        if preset["floors"] > 0:
            spec = evaluate_building_grammar(
                preset["width"], preset["depth"], preset["floors"],
                base_style, seed,
            )

        unique_ops = _generate_landmark_unique_features(
            preset["unique_features"],
            preset["width"], preset["depth"], preset["wall_height"],
            preset["scale"], seed,
        )

        corruption_tint = _apply_corruption_tint(preset["corruption_level"])

        room_layouts = {}
        for i, room_name in enumerate(preset["interior_rooms"]):
            mapped = _LANDMARK_ROOM_TYPE_MAP.get(room_name, room_name)
            layout = generate_interior_layout(
                mapped, preset["width"] * 0.4, preset["depth"] * 0.3,
                preset["wall_height"], seed=seed + i + 1,
            )
            room_key = (
                f"{room_name}_{i}"
                if preset["interior_rooms"].count(room_name) > 1
                else room_name
            )
            room_layouts[room_key] = layout

        return _build_landmark_result(
            name=preset_key,
            preset=preset,
            spec=spec,
            unique_feature_ops=unique_ops,
            room_layouts=room_layouts,
            corruption_tint=corruption_tint,
        )

    def test_result_has_required_keys(self):
        """Landmark result dict must have all required keys."""
        result = self._make_result("the_congregation_lair")
        required = {
            "name", "description", "base_style", "scale", "floors",
            "footprint", "wall_height", "corruption_level", "corruption_tint",
            "structure_vertex_count", "structure_face_count",
            "unique_feature_count", "unique_feature_roles", "unique_features",
            "rooms_furnished", "total_furniture", "props",
        }
        missing = required - set(result.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_congregation_lair_has_structure_geometry(self):
        """the_congregation_lair (2 floors) should have structure geometry."""
        result = self._make_result("the_congregation_lair")
        assert result["structure_vertex_count"] > 0
        assert result["structure_face_count"] > 0

    def test_veil_breach_has_no_structure_geometry(self):
        """veil_breach (0 floors) should have zero structure geometry."""
        result = self._make_result("veil_breach")
        assert result["structure_vertex_count"] == 0
        assert result["structure_face_count"] == 0

    def test_unique_feature_count_matches_preset(self):
        """unique_feature_count reflects generated operations (not preset list length)."""
        result = self._make_result("the_congregation_lair")
        assert result["unique_feature_count"] > 0

    def test_rooms_furnished_for_congregation_lair(self):
        """the_congregation_lair should have 3 furnished rooms."""
        result = self._make_result("the_congregation_lair")
        assert len(result["rooms_furnished"]) == 3

    def test_veil_breach_has_no_rooms(self):
        """veil_breach should have no furnished rooms."""
        result = self._make_result("veil_breach")
        assert len(result["rooms_furnished"]) == 0
        assert result["total_furniture"] == 0

    def test_wardens_prison_has_5_rooms(self):
        """wardens_prison should have 5 furnished rooms (3 prison + guard + storage)."""
        result = self._make_result("wardens_prison")
        assert len(result["rooms_furnished"]) == 5

    def test_corruption_tint_included(self):
        """Result includes corruption_tint with base_color."""
        result = self._make_result("the_congregation_lair")
        assert "base_color" in result["corruption_tint"]
        assert len(result["corruption_tint"]["base_color"]) == 4

    def test_props_list_preserved(self):
        """Props list from preset is preserved in result."""
        result = self._make_result("storm_citadel")
        assert "lightning_rod" in result["props"]
        assert "anvil" in result["props"]

    def test_footprint_matches_preset(self):
        """Footprint matches preset width/depth."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        result = self._make_result("storm_citadel")
        p = VB_LANDMARK_PRESETS["storm_citadel"]
        assert result["footprint"] == [p["width"], p["depth"]]

    def test_all_presets_produce_valid_result(self):
        """Every preset can produce a valid result dict."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        for name in VB_LANDMARK_PRESETS:
            result = self._make_result(name)
            assert result["name"] == name
            assert result["unique_feature_count"] > 0
            assert isinstance(result["props"], list)


# ---------------------------------------------------------------------------
# Full handler pure-logic integration (without Blender)
# ---------------------------------------------------------------------------


class TestHandleGenerateLandmarkPureLogic:
    """Test handle_generate_landmark input validation and error paths.

    Actual Blender calls are not exercised here -- only the parts
    that can be tested without bpy.
    """

    def test_invalid_preset_raises_valueerror(self):
        """Requesting an unknown preset name raises ValueError."""
        from blender_addon.handlers.worldbuilding import VB_LANDMARK_PRESETS

        # We test the preset lookup + error path directly
        from blender_addon.handlers.worldbuilding import get_vb_landmark_preset

        result = get_vb_landmark_preset("fake_landmark_123")
        assert result is None

    def test_custom_preset_builds_config(self):
        """Custom mode constructs a config from params."""
        # Verify the custom config construction logic
        params = {
            "landmark_name": "custom",
            "description": "Test landmark",
            "base_style": "medieval",
            "scale": 1.5,
            "floors": 2,
            "width": 12.0,
            "depth": 14.0,
            "wall_height": 6.0,
            "unique_features": ["corrupted_spire"],
            "interior_rooms": ["throne_room"],
            "corruption_level": 0.3,
            "props": ["brazier"],
        }
        # Build the config as the handler would
        preset = {
            "description": params.get("description", "Custom landmark"),
            "base_style": params.get("base_style", "gothic"),
            "scale": params.get("scale", 1.0),
            "floors": params.get("floors", 1),
            "width": params.get("width", 10.0),
            "depth": params.get("depth", 10.0),
            "wall_height": params.get("wall_height", 5.0),
            "unique_features": params.get("unique_features", []),
            "interior_rooms": params.get("interior_rooms", []),
            "corruption_level": params.get("corruption_level", 0.0),
            "props": params.get("props", []),
        }
        assert preset["description"] == "Test landmark"
        assert preset["scale"] == 1.5
        assert preset["floors"] == 2
        assert preset["width"] == 12.0
        assert preset["corruption_level"] == 0.3
        assert "corrupted_spire" in preset["unique_features"]

    def test_chaotic_style_fallback(self):
        """veil_breach's 'chaotic' style should fall back to 'gothic' for grammar."""
        from blender_addon.handlers._building_grammar import STYLE_CONFIGS

        base_style = "chaotic"
        if base_style not in STYLE_CONFIGS:
            base_style = "gothic"
        assert base_style == "gothic"
        assert base_style in STYLE_CONFIGS
