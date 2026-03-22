"""Tests for terrain biome material system (V2 splatmap API).

Verifies:
  - BIOME_PALETTES_V2 has all 8 biomes
  - Each biome has 4 layers (ground, slope, cliff, special)
  - Each layer has all required material parameters
  - auto_assign_terrain_layers returns correct weights for known slopes
  - Flat surface -> mostly R channel (ground)
  - Vertical surface -> mostly B channel (cliff)
  - 45-degree surface -> mostly G channel (slope)
  - Height extremes -> A channel (special)
  - Color values follow dark fantasy palette rules
  - Weights are normalised (R + G + B + A = 1.0)

All pure-logic -- no Blender required.
"""

import math

import pytest

from blender_addon.handlers.terrain_materials import (
    BIOME_PALETTES_V2,
    REQUIRED_LAYER_KEYS,
    VALID_LAYER_NAMES,
    auto_assign_terrain_layers,
)


# ---------------------------------------------------------------------------
# Canonical geometry fixtures
# ---------------------------------------------------------------------------

FLAT_QUAD_VERTS = [
    (0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (1.0, 1.0, 5.0), (0.0, 1.0, 5.0),
]
FLAT_QUAD_FACES = [(0, 1, 2, 3)]
FLAT_QUAD_NORMALS = [(0.0, 0.0, 1.0)]

# All verts at same Z so height gradient does not trigger special channel.
VERT_WALL_VERTS = [
    (0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (1.0, 1.0, 5.0), (0.0, 1.0, 5.0),
]
VERT_WALL_FACES = [(0, 1, 2, 3)]
VERT_WALL_NORMALS = [(0.0, 1.0, 0.0)]

_N45 = 1.0 / math.sqrt(2.0)
# All verts at same Z so height gradient does not trigger special channel.
SLOPE_45_VERTS = [
    (0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (1.0, 1.0, 5.0), (0.0, 1.0, 5.0),
]
SLOPE_45_FACES = [(0, 1, 2, 3)]
SLOPE_45_NORMALS = [(0.0, _N45, _N45)]

MULTI_ZONE_VERTS = [
    (0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (1.0, 1.0, 5.0), (0.0, 1.0, 5.0),
    (2.0, 0.0, 5.0), (3.0, 0.0, 5.0), (3.0, 1.0, 6.0), (2.0, 1.0, 6.0),
    (4.0, 0.0, 5.0), (5.0, 0.0, 5.0), (5.0, 0.0, 6.0), (4.0, 0.0, 6.0),
]
MULTI_ZONE_FACES = [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11)]
MULTI_ZONE_NORMALS = [(0.0, 0.0, 1.0), (0.0, _N45, _N45), (0.0, 1.0, 0.0)]

HEIGHT_EXTREME_VERTS = [
    (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
    (2.0, 0.0, 100.0), (3.0, 0.0, 100.0), (3.0, 1.0, 100.0), (2.0, 1.0, 100.0),
]
HEIGHT_EXTREME_FACES = [(0, 1, 2, 3), (4, 5, 6, 7)]
HEIGHT_EXTREME_NORMALS = [(0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]


def _rgb_to_hsv(r, g, b):
    mx = max(r, g, b)
    mn = min(r, g, b)
    diff = mx - mn
    v = mx * 100.0
    if mx == 0:
        return (0.0, 0.0, v)
    s = (diff / mx) * 100.0
    if diff == 0:
        h = 0.0
    elif mx == r:
        h = 60.0 * (((g - b) / diff) % 6)
    elif mx == g:
        h = 60.0 * (((b - r) / diff) + 2)
    else:
        h = 60.0 * (((r - g) / diff) + 4)
    return (h, s, v)


# ===========================================================================
# Biome palette structure tests
# ===========================================================================


class TestBiomePaletteStructure:
    EXPECTED_BIOMES = {
        "thornwood_forest", "corrupted_swamp", "mountain_pass",
        "ruined_fortress", "abandoned_village", "veil_crack_zone",
        "cemetery", "battlefield",
    }

    def test_all_8_biomes_present(self):
        assert len(BIOME_PALETTES_V2) == 8

    def test_expected_biome_names(self):
        assert set(BIOME_PALETTES_V2.keys()) == self.EXPECTED_BIOMES

    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_biome_has_4_layers(self, biome_name):
        palette = BIOME_PALETTES_V2[biome_name]
        assert set(palette.keys()) == VALID_LAYER_NAMES

    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_each_layer_has_required_keys(self, biome_name):
        palette = BIOME_PALETTES_V2[biome_name]
        for layer_name, layer_def in palette.items():
            missing = REQUIRED_LAYER_KEYS - set(layer_def.keys())
            assert not missing, f"{biome_name}.{layer_name} missing: {missing}"

    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_base_color_is_4_tuple(self, biome_name):
        for layer_name, layer_def in BIOME_PALETTES_V2[biome_name].items():
            bc = layer_def["base_color"]
            assert len(bc) == 4
            for v in bc:
                assert 0.0 <= v <= 1.0

    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_roughness_in_valid_range(self, biome_name):
        for layer_name, layer_def in BIOME_PALETTES_V2[biome_name].items():
            assert 0.0 <= layer_def["roughness"] <= 1.0

    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_node_recipe_is_valid(self, biome_name):
        valid = {"stone", "wood", "metal", "organic", "terrain", "fabric"}
        for layer_name, layer_def in BIOME_PALETTES_V2[biome_name].items():
            assert layer_def["node_recipe"] in valid

    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_description_nonempty(self, biome_name):
        for layer_name, layer_def in BIOME_PALETTES_V2[biome_name].items():
            assert isinstance(layer_def["description"], str)
            assert len(layer_def["description"]) > 0


# ===========================================================================
# auto_assign_terrain_layers: basics
# ===========================================================================


class TestAutoAssignBasics:
    def test_empty_mesh(self):
        assert auto_assign_terrain_layers([], [], []) == []

    def test_output_length(self):
        result = auto_assign_terrain_layers(FLAT_QUAD_VERTS, FLAT_QUAD_NORMALS, FLAT_QUAD_FACES)
        assert len(result) == len(FLAT_QUAD_VERTS)

    def test_output_is_4_tuples(self):
        for w in auto_assign_terrain_layers(FLAT_QUAD_VERTS, FLAT_QUAD_NORMALS, FLAT_QUAD_FACES):
            assert len(w) == 4

    def test_all_values_in_0_1(self):
        for r, g, b, a in auto_assign_terrain_layers(MULTI_ZONE_VERTS, MULTI_ZONE_NORMALS, MULTI_ZONE_FACES):
            assert 0.0 <= r <= 1.0 and 0.0 <= g <= 1.0
            assert 0.0 <= b <= 1.0 and 0.0 <= a <= 1.0

    def test_weights_sum_to_one(self):
        for r, g, b, a in auto_assign_terrain_layers(MULTI_ZONE_VERTS, MULTI_ZONE_NORMALS, MULTI_ZONE_FACES):
            assert abs(r + g + b + a - 1.0) < 0.01


# ===========================================================================
# auto_assign_terrain_layers: slope-based assignment
# ===========================================================================


class TestAutoAssignSlope:
    def test_flat_surface_mostly_R(self):
        for r, g, b, a in auto_assign_terrain_layers(FLAT_QUAD_VERTS, FLAT_QUAD_NORMALS, FLAT_QUAD_FACES):
            assert r > 0.5
            assert r > g and r > b

    def test_vertical_surface_mostly_B(self):
        for r, g, b, a in auto_assign_terrain_layers(VERT_WALL_VERTS, VERT_WALL_NORMALS, VERT_WALL_FACES):
            assert b > 0.5
            assert b > r and b > g

    def test_45_degree_slope_has_G(self):
        for r, g, b, a in auto_assign_terrain_layers(SLOPE_45_VERTS, SLOPE_45_NORMALS, SLOPE_45_FACES):
            assert g > 0.3

    def test_multi_zone_flat_verts_R_dominant(self):
        result = auto_assign_terrain_layers(MULTI_ZONE_VERTS, MULTI_ZONE_NORMALS, MULTI_ZONE_FACES)
        for r, g, b, a in result[0:4]:
            assert r >= g and r >= b

    def test_multi_zone_cliff_verts_B_dominant(self):
        result = auto_assign_terrain_layers(MULTI_ZONE_VERTS, MULTI_ZONE_NORMALS, MULTI_ZONE_FACES)
        for r, g, b, a in result[8:12]:
            assert b >= r and b >= g

    def test_R_decreases_with_steeper_slope(self):
        flat = auto_assign_terrain_layers(FLAT_QUAD_VERTS, FLAT_QUAD_NORMALS, FLAT_QUAD_FACES)
        slope = auto_assign_terrain_layers(SLOPE_45_VERTS, SLOPE_45_NORMALS, SLOPE_45_FACES)
        vert = auto_assign_terrain_layers(VERT_WALL_VERTS, VERT_WALL_NORMALS, VERT_WALL_FACES)
        avg_r_flat = sum(w[0] for w in flat) / len(flat)
        avg_r_slope = sum(w[0] for w in slope) / len(slope)
        avg_r_vert = sum(w[0] for w in vert) / len(vert)
        assert avg_r_flat > avg_r_slope
        assert avg_r_slope >= avg_r_vert


# ===========================================================================
# auto_assign_terrain_layers: height-based special
# ===========================================================================


class TestAutoAssignHeight:
    def test_low_height_has_special(self):
        result = auto_assign_terrain_layers(HEIGHT_EXTREME_VERTS, HEIGHT_EXTREME_NORMALS, HEIGHT_EXTREME_FACES)
        for r, g, b, a in result[0:4]:
            assert a > 0.0

    def test_high_height_has_special(self):
        result = auto_assign_terrain_layers(HEIGHT_EXTREME_VERTS, HEIGHT_EXTREME_NORMALS, HEIGHT_EXTREME_FACES)
        for r, g, b, a in result[4:8]:
            assert a > 0.0

    def test_mid_height_no_special(self):
        for r, g, b, a in auto_assign_terrain_layers(FLAT_QUAD_VERTS, FLAT_QUAD_NORMALS, FLAT_QUAD_FACES):
            assert a == 0.0

    def test_special_preserves_sum_1(self):
        for r, g, b, a in auto_assign_terrain_layers(HEIGHT_EXTREME_VERTS, HEIGHT_EXTREME_NORMALS, HEIGHT_EXTREME_FACES):
            assert abs(r + g + b + a - 1.0) < 0.01


# ===========================================================================
# Dark fantasy palette compliance
# ===========================================================================


class TestDarkFantasyCompliance:
    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_saturation_under_50(self, biome_name):
        for layer_name, layer_def in BIOME_PALETTES_V2[biome_name].items():
            bc = layer_def["base_color"]
            _, s, _ = _rgb_to_hsv(bc[0], bc[1], bc[2])
            assert s <= 50.0, f"{biome_name}.{layer_name} sat={s:.1f}%"

    @pytest.mark.parametrize("biome_name", list(BIOME_PALETTES_V2.keys()))
    def test_value_under_55(self, biome_name):
        for layer_name, layer_def in BIOME_PALETTES_V2[biome_name].items():
            bc = layer_def["base_color"]
            _, _, v = _rgb_to_hsv(bc[0], bc[1], bc[2])
            assert v <= 55.0, f"{biome_name}.{layer_name} val={v:.1f}%"


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_single_vertex_no_faces(self):
        result = auto_assign_terrain_layers([(0.0, 0.0, 0.0)], [], [])
        assert len(result) == 1

    def test_same_height_no_special(self):
        verts = [(0.0, 0.0, 3.0), (1.0, 0.0, 3.0), (1.0, 1.0, 3.0), (0.0, 1.0, 3.0)]
        for r, g, b, a in auto_assign_terrain_layers(verts, [(0.0, 0.0, 1.0)], [(0, 1, 2, 3)]):
            assert a == 0.0

    def test_all_biomes_accepted(self):
        for biome in BIOME_PALETTES_V2:
            result = auto_assign_terrain_layers(FLAT_QUAD_VERTS, FLAT_QUAD_NORMALS, FLAT_QUAD_FACES, biome_name=biome)
            assert len(result) == 4

    def test_downward_normal_is_cliff(self):
        verts = [(0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (1.0, 1.0, 5.0), (0.0, 1.0, 5.0)]
        result = auto_assign_terrain_layers(verts, [(0.0, 0.0, -1.0)], [(0, 1, 2, 3)])
        for r, g, b, a in result:
            assert b > r and b > g
