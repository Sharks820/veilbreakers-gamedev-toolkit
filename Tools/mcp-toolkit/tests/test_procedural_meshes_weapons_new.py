"""Tests for new weapon types: dual-wield, fist, rapier, throwing, off-hand.

Validates all 18 new weapon generators across 54 style variants:
- Non-empty vertex and face lists with valid indices
- Required weapon metadata (grip_point, trail_top, trail_bottom)
- Different styles produce different geometry
- Reasonable poly counts
- Category-specific metadata (dual_wield, offhand)
"""

from __future__ import annotations

import importlib.util

import pytest

# Load procedural_meshes without triggering blender_addon __init__ (needs bpy)
_spec = importlib.util.spec_from_file_location(
    "procedural_meshes",
    "blender_addon/handlers/procedural_meshes.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Dual-wield
generate_paired_daggers_mesh = _mod.generate_paired_daggers_mesh
generate_twin_swords_mesh = _mod.generate_twin_swords_mesh
generate_dual_axes_mesh = _mod.generate_dual_axes_mesh
generate_dual_claws_mesh = _mod.generate_dual_claws_mesh

# Fist / gauntlet
generate_brass_knuckles_mesh = _mod.generate_brass_knuckles_mesh
generate_cestus_mesh = _mod.generate_cestus_mesh
generate_bladed_gauntlet_mesh = _mod.generate_bladed_gauntlet_mesh
generate_iron_fist_mesh = _mod.generate_iron_fist_mesh

# Rapiers / thrusting
generate_rapier_mesh = _mod.generate_rapier_mesh
generate_estoc_mesh = _mod.generate_estoc_mesh

# Throwing
generate_javelin_mesh = _mod.generate_javelin_mesh
generate_throwing_axe_mesh = _mod.generate_throwing_axe_mesh
generate_shuriken_mesh = _mod.generate_shuriken_mesh
generate_bola_mesh = _mod.generate_bola_mesh

# Off-hand focus
generate_orb_focus_mesh = _mod.generate_orb_focus_mesh
generate_skull_fetish_mesh = _mod.generate_skull_fetish_mesh
generate_holy_symbol_mesh = _mod.generate_holy_symbol_mesh
generate_totem_mesh = _mod.generate_totem_mesh

GENERATORS = _mod.GENERATORS


# ---------------------------------------------------------------------------
# Validation helpers
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

    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components, expected 3"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    n_verts = len(verts)
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


def validate_weapon_metadata(result: dict, name: str):
    """Validate weapon-specific metadata: grip_point, trail_top, trail_bottom."""
    meta = result["metadata"]
    assert "grip_point" in meta, f"{name}: missing grip_point"
    assert "trail_top" in meta, f"{name}: missing trail_top"
    assert "trail_bottom" in meta, f"{name}: missing trail_bottom"

    grip = meta["grip_point"]
    assert len(grip) == 3, f"{name}: grip_point must be 3-tuple"
    for comp in grip:
        assert isinstance(comp, (int, float)), f"{name}: grip_point component not a number"

    trail_top = meta["trail_top"]
    assert len(trail_top) == 3, f"{name}: trail_top must be 3-tuple"

    trail_bottom = meta["trail_bottom"]
    assert len(trail_bottom) == 3, f"{name}: trail_bottom must be 3-tuple"


# ---------------------------------------------------------------------------
# DUAL-WIELD: Paired Daggers
# ---------------------------------------------------------------------------


class TestPairedDaggers:
    """Test paired daggers mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "curved", "serrated"])
    def test_styles(self, style):
        result = generate_paired_daggers_mesh(style=style)
        validate_mesh_spec(result, f"PairedDaggers_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"PairedDaggers_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_paired_daggers_mesh(style="standard")
        r2 = generate_paired_daggers_mesh(style="curved")
        assert r1["vertices"] != r2["vertices"]

    def test_dual_wield_metadata(self):
        result = generate_paired_daggers_mesh()
        assert result["metadata"].get("dual_wield") is True

    def test_poly_count_reasonable(self):
        result = generate_paired_daggers_mesh()
        assert result["metadata"]["poly_count"] < 600


# ---------------------------------------------------------------------------
# DUAL-WIELD: Twin Swords
# ---------------------------------------------------------------------------


class TestTwinSwords:
    """Test twin swords mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "falcata", "gladius"])
    def test_styles(self, style):
        result = generate_twin_swords_mesh(style=style)
        validate_mesh_spec(result, f"TwinSwords_{style}", min_verts=100, min_faces=50)
        validate_weapon_metadata(result, f"TwinSwords_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_twin_swords_mesh(style="standard")
        r2 = generate_twin_swords_mesh(style="gladius")
        assert r1["vertices"] != r2["vertices"]

    def test_dual_wield_metadata(self):
        result = generate_twin_swords_mesh()
        assert result["metadata"].get("dual_wield") is True

    def test_poly_count_reasonable(self):
        result = generate_twin_swords_mesh()
        assert result["metadata"]["poly_count"] < 800


# ---------------------------------------------------------------------------
# DUAL-WIELD: Dual Axes
# ---------------------------------------------------------------------------


class TestDualAxes:
    """Test dual axes mesh generator."""

    @pytest.mark.parametrize("style", ["hand", "hatchet", "tomahawk"])
    def test_styles(self, style):
        result = generate_dual_axes_mesh(style=style)
        validate_mesh_spec(result, f"DualAxes_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"DualAxes_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_dual_axes_mesh(style="hand")
        r2 = generate_dual_axes_mesh(style="tomahawk")
        assert r1["vertices"] != r2["vertices"]

    def test_dual_wield_metadata(self):
        result = generate_dual_axes_mesh()
        assert result["metadata"].get("dual_wield") is True


# ---------------------------------------------------------------------------
# DUAL-WIELD: Dual Claws
# ---------------------------------------------------------------------------


class TestDualClaws:
    """Test dual claws mesh generator."""

    @pytest.mark.parametrize("style", ["tiger", "hook", "katar"])
    def test_styles(self, style):
        result = generate_dual_claws_mesh(style=style)
        validate_mesh_spec(result, f"DualClaws_{style}", min_verts=40, min_faces=15)
        validate_weapon_metadata(result, f"DualClaws_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_dual_claws_mesh(style="tiger")
        r2 = generate_dual_claws_mesh(style="katar")
        assert r1["vertices"] != r2["vertices"]

    def test_dual_wield_metadata(self):
        result = generate_dual_claws_mesh()
        assert result["metadata"].get("dual_wield") is True

    def test_tiger_has_three_claws_per_side(self):
        """Tiger style should have more geometry due to 3 claws vs hook's 2."""
        r_tiger = generate_dual_claws_mesh(style="tiger")
        r_hook = generate_dual_claws_mesh(style="hook")
        assert r_tiger["metadata"]["vertex_count"] > r_hook["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# FIST: Brass Knuckles
# ---------------------------------------------------------------------------


class TestBrassKnuckles:
    """Test brass knuckles mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "spiked", "bladed"])
    def test_styles(self, style):
        result = generate_brass_knuckles_mesh(style=style)
        validate_mesh_spec(result, f"BrassKnuckles_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"BrassKnuckles_{style}")

    def test_spiked_has_more_geometry(self):
        r_std = generate_brass_knuckles_mesh(style="standard")
        r_spiked = generate_brass_knuckles_mesh(style="spiked")
        assert r_spiked["metadata"]["vertex_count"] > r_std["metadata"]["vertex_count"]

    def test_poly_count_reasonable(self):
        result = generate_brass_knuckles_mesh()
        assert result["metadata"]["poly_count"] < 500


# ---------------------------------------------------------------------------
# FIST: Cestus
# ---------------------------------------------------------------------------


class TestCestus:
    """Test cestus mesh generator."""

    @pytest.mark.parametrize("style", ["leather", "studded", "iron"])
    def test_styles(self, style):
        result = generate_cestus_mesh(style=style)
        validate_mesh_spec(result, f"Cestus_{style}", min_verts=40, min_faces=15)
        validate_weapon_metadata(result, f"Cestus_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_cestus_mesh(style="leather")
        r2 = generate_cestus_mesh(style="iron")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# FIST: Bladed Gauntlet
# ---------------------------------------------------------------------------


class TestBladedGauntlet:
    """Test bladed gauntlet mesh generator."""

    @pytest.mark.parametrize("style", ["wrist_blade", "finger_blades", "claw_tips"])
    def test_styles(self, style):
        result = generate_bladed_gauntlet_mesh(style=style)
        validate_mesh_spec(result, f"BladedGauntlet_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"BladedGauntlet_{style}")

    def test_wrist_blade_tallest(self):
        r_wrist = generate_bladed_gauntlet_mesh(style="wrist_blade")
        r_claw = generate_bladed_gauntlet_mesh(style="claw_tips")
        assert r_wrist["metadata"]["dimensions"]["height"] > r_claw["metadata"]["dimensions"]["height"]

    def test_finger_blades_more_geo_than_claw_tips(self):
        r_finger = generate_bladed_gauntlet_mesh(style="finger_blades")
        r_claw = generate_bladed_gauntlet_mesh(style="claw_tips")
        assert r_finger["metadata"]["vertex_count"] > r_claw["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# FIST: Iron Fist
# ---------------------------------------------------------------------------


class TestIronFist:
    """Test iron fist mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "hammer_fist", "spiked"])
    def test_styles(self, style):
        result = generate_iron_fist_mesh(style=style)
        validate_mesh_spec(result, f"IronFist_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"IronFist_{style}")

    def test_spiked_has_most_geometry(self):
        r_spiked = generate_iron_fist_mesh(style="spiked")
        r_std = generate_iron_fist_mesh(style="standard")
        assert r_spiked["metadata"]["vertex_count"] > r_std["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# RAPIER
# ---------------------------------------------------------------------------


class TestRapier:
    """Test rapier mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "ornate", "basket_hilt"])
    def test_styles(self, style):
        result = generate_rapier_mesh(style=style)
        validate_mesh_spec(result, f"Rapier_{style}", min_verts=100, min_faces=50)
        validate_weapon_metadata(result, f"Rapier_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_rapier_mesh(style="standard")
        r2 = generate_rapier_mesh(style="basket_hilt")
        assert r1["vertices"] != r2["vertices"]

    def test_height_near_1m(self):
        result = generate_rapier_mesh()
        assert result["metadata"]["dimensions"]["height"] > 0.8

    def test_basket_hilt_has_most_geometry(self):
        r_basket = generate_rapier_mesh(style="basket_hilt")
        r_std = generate_rapier_mesh(style="standard")
        assert r_basket["metadata"]["vertex_count"] > r_std["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# ESTOC
# ---------------------------------------------------------------------------


class TestEstoc:
    """Test estoc mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "heavy", "light"])
    def test_styles(self, style):
        result = generate_estoc_mesh(style=style)
        validate_mesh_spec(result, f"Estoc_{style}", min_verts=80, min_faces=30)
        validate_weapon_metadata(result, f"Estoc_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_estoc_mesh(style="standard")
        r2 = generate_estoc_mesh(style="heavy")
        assert r1["vertices"] != r2["vertices"]

    def test_heavy_taller_than_light(self):
        r_heavy = generate_estoc_mesh(style="heavy")
        r_light = generate_estoc_mesh(style="light")
        assert r_heavy["metadata"]["dimensions"]["height"] > r_light["metadata"]["dimensions"]["height"]


# ---------------------------------------------------------------------------
# THROWING: Javelin
# ---------------------------------------------------------------------------


class TestJavelin:
    """Test javelin mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "barbed", "fire"])
    def test_styles(self, style):
        result = generate_javelin_mesh(style=style)
        validate_mesh_spec(result, f"Javelin_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"Javelin_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_javelin_mesh(style="standard")
        r2 = generate_javelin_mesh(style="barbed")
        assert r1["vertices"] != r2["vertices"]

    def test_height_over_1m(self):
        result = generate_javelin_mesh()
        assert result["metadata"]["dimensions"]["height"] > 1.0


# ---------------------------------------------------------------------------
# THROWING: Throwing Axe
# ---------------------------------------------------------------------------


class TestThrowingAxe:
    """Test throwing axe mesh generator."""

    @pytest.mark.parametrize("style", ["tomahawk", "francisca", "double"])
    def test_styles(self, style):
        result = generate_throwing_axe_mesh(style=style)
        validate_mesh_spec(result, f"ThrowingAxe_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"ThrowingAxe_{style}")

    def test_double_has_more_geometry(self):
        r_double = generate_throwing_axe_mesh(style="double")
        r_toma = generate_throwing_axe_mesh(style="tomahawk")
        assert r_double["metadata"]["vertex_count"] > r_toma["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# THROWING: Shuriken
# ---------------------------------------------------------------------------


class TestShuriken:
    """Test shuriken mesh generator."""

    @pytest.mark.parametrize("style", ["four_point", "six_point", "circular"])
    def test_styles(self, style):
        result = generate_shuriken_mesh(style=style)
        validate_mesh_spec(result, f"Shuriken_{style}", min_verts=20, min_faces=8)
        validate_weapon_metadata(result, f"Shuriken_{style}")

    def test_six_point_more_geo_than_four(self):
        r6 = generate_shuriken_mesh(style="six_point")
        r4 = generate_shuriken_mesh(style="four_point")
        assert r6["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_circular_has_most_geometry(self):
        r_circ = generate_shuriken_mesh(style="circular")
        r_six = generate_shuriken_mesh(style="six_point")
        assert r_circ["metadata"]["vertex_count"] > r_six["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# THROWING: Bola
# ---------------------------------------------------------------------------


class TestBola:
    """Test bola mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "chain", "spiked"])
    def test_styles(self, style):
        result = generate_bola_mesh(style=style)
        validate_mesh_spec(result, f"Bola_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"Bola_{style}")

    def test_spiked_has_most_geometry(self):
        r_spiked = generate_bola_mesh(style="spiked")
        r_std = generate_bola_mesh(style="standard")
        assert r_spiked["metadata"]["vertex_count"] > r_std["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# OFF-HAND: Orb Focus
# ---------------------------------------------------------------------------


class TestOrbFocus:
    """Test orb focus mesh generator."""

    @pytest.mark.parametrize("style", ["crystal", "elemental", "void"])
    def test_styles(self, style):
        result = generate_orb_focus_mesh(style=style)
        validate_mesh_spec(result, f"OrbFocus_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"OrbFocus_{style}")

    def test_offhand_metadata(self):
        result = generate_orb_focus_mesh()
        assert result["metadata"].get("offhand") is True

    def test_different_styles_different_geometry(self):
        r1 = generate_orb_focus_mesh(style="crystal")
        r2 = generate_orb_focus_mesh(style="void")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# OFF-HAND: Skull Fetish
# ---------------------------------------------------------------------------


class TestSkullFetish:
    """Test skull fetish mesh generator."""

    @pytest.mark.parametrize("style", ["human", "beast", "demon"])
    def test_styles(self, style):
        result = generate_skull_fetish_mesh(style=style)
        validate_mesh_spec(result, f"SkullFetish_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"SkullFetish_{style}")

    def test_offhand_metadata(self):
        result = generate_skull_fetish_mesh()
        assert result["metadata"].get("offhand") is True

    def test_demon_tallest(self):
        r_demon = generate_skull_fetish_mesh(style="demon")
        r_human = generate_skull_fetish_mesh(style="human")
        assert r_demon["metadata"]["dimensions"]["height"] > r_human["metadata"]["dimensions"]["height"]


# ---------------------------------------------------------------------------
# OFF-HAND: Holy Symbol
# ---------------------------------------------------------------------------


class TestHolySymbol:
    """Test holy symbol mesh generator."""

    @pytest.mark.parametrize("style", ["pendant", "reliquary", "chalice"])
    def test_styles(self, style):
        result = generate_holy_symbol_mesh(style=style)
        validate_mesh_spec(result, f"HolySymbol_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"HolySymbol_{style}")

    def test_offhand_metadata(self):
        result = generate_holy_symbol_mesh()
        assert result["metadata"].get("offhand") is True

    def test_different_styles_different_geometry(self):
        r1 = generate_holy_symbol_mesh(style="pendant")
        r2 = generate_holy_symbol_mesh(style="chalice")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# OFF-HAND: Totem
# ---------------------------------------------------------------------------


class TestTotem:
    """Test totem mesh generator."""

    @pytest.mark.parametrize("style", ["wooden", "bone", "stone"])
    def test_styles(self, style):
        result = generate_totem_mesh(style=style)
        validate_mesh_spec(result, f"Totem_{style}", min_verts=40, min_faces=15)
        validate_weapon_metadata(result, f"Totem_{style}")

    def test_offhand_metadata(self):
        result = generate_totem_mesh()
        assert result["metadata"].get("offhand") is True

    def test_different_styles_different_geometry(self):
        r1 = generate_totem_mesh(style="wooden")
        r2 = generate_totem_mesh(style="stone")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------


class TestNewWeaponRegistry:
    """Test that all new weapon generators are properly registered."""

    def test_weapon_count_is_41(self):
        assert len(GENERATORS["weapon"]) == 41

    def test_new_weapons_registered(self):
        new_weapons = [
            # Dual-wield
            "paired_daggers", "twin_swords", "dual_axes", "dual_claws",
            # Fist / gauntlet
            "brass_knuckles", "cestus", "bladed_gauntlet", "iron_fist",
            # Rapiers
            "rapier", "estoc",
            # Throwing
            "javelin", "throwing_axe", "shuriken", "bola",
            # Off-hand
            "orb_focus", "skull_fetish", "holy_symbol", "totem",
        ]
        for name in new_weapons:
            assert name in GENERATORS["weapon"], f"{name} not registered in GENERATORS"

    def test_all_new_generators_callable(self):
        new_weapons = [
            "paired_daggers", "twin_swords", "dual_axes", "dual_claws",
            "brass_knuckles", "cestus", "bladed_gauntlet", "iron_fist",
            "rapier", "estoc",
            "javelin", "throwing_axe", "shuriken", "bola",
            "orb_focus", "skull_fetish", "holy_symbol", "totem",
        ]
        for name in new_weapons:
            assert callable(GENERATORS["weapon"][name])

    def test_all_new_generators_produce_valid_mesh(self):
        """Smoke test: call every new weapon generator with defaults."""
        new_weapons = [
            "paired_daggers", "twin_swords", "dual_axes", "dual_claws",
            "brass_knuckles", "cestus", "bladed_gauntlet", "iron_fist",
            "rapier", "estoc",
            "javelin", "throwing_axe", "shuriken", "bola",
            "orb_focus", "skull_fetish", "holy_symbol", "totem",
        ]
        for name in new_weapons:
            result = GENERATORS["weapon"][name]()
            validate_mesh_spec(result, f"weapon/{name}")
            validate_weapon_metadata(result, f"weapon/{name}")

    def test_original_weapons_still_present(self):
        originals = [
            "hammer", "spear", "crossbow", "scythe", "flail", "whip",
            "claw", "tome", "greatsword", "curved_sword", "hand_axe",
            "battle_axe", "greataxe", "club", "mace", "warhammer",
            "halberd", "glaive", "shortbow", "longbow", "staff_magic",
            "wand", "throwing_knife_weapon",
        ]
        for name in originals:
            assert name in GENERATORS["weapon"], f"original weapon {name} missing"
