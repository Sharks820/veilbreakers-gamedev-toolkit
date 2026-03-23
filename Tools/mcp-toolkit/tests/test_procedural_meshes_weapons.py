"""Tests for new weapon procedural mesh generators (15 new types).

Validates that every new weapon generator returns valid mesh data:
- Non-empty vertex and face lists
- All face indices reference valid vertices
- Required metadata keys present (grip_point, trail_top, trail_bottom)
- Different styles produce different geometry
- Reasonable poly counts for each weapon type
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Load procedural_meshes without triggering blender_addon __init__ (needs bpy)
_HANDLERS_DIR = Path(__file__).resolve().parent.parent / "blender_addon" / "handlers"
_spec = importlib.util.spec_from_file_location(
    "procedural_meshes",
    str(_HANDLERS_DIR / "procedural_meshes.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

generate_greatsword_mesh = _mod.generate_greatsword_mesh
generate_curved_sword_mesh = _mod.generate_curved_sword_mesh
generate_hand_axe_mesh = _mod.generate_hand_axe_mesh
generate_battle_axe_mesh = _mod.generate_battle_axe_mesh
generate_greataxe_mesh = _mod.generate_greataxe_mesh
generate_club_mesh = _mod.generate_club_mesh
generate_mace_mesh = _mod.generate_mace_mesh
generate_warhammer_mesh = _mod.generate_warhammer_mesh
generate_halberd_mesh = _mod.generate_halberd_mesh
generate_glaive_mesh = _mod.generate_glaive_mesh
generate_shortbow_mesh = _mod.generate_shortbow_mesh
generate_longbow_mesh = _mod.generate_longbow_mesh
generate_staff_magic_mesh = _mod.generate_staff_magic_mesh
generate_wand_mesh = _mod.generate_wand_mesh
generate_throwing_knife_weapon_mesh = _mod.generate_throwing_knife_weapon_mesh

GENERATORS = _mod.GENERATORS


# ---------------------------------------------------------------------------
# Validation helper
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
# GREATSWORD tests
# ---------------------------------------------------------------------------


class TestGreatsword:
    """Test greatsword mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "flamberge", "executioner"])
    def test_styles(self, style):
        result = generate_greatsword_mesh(style=style)
        validate_mesh_spec(result, f"Greatsword_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"Greatsword_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_greatsword_mesh(style="standard")
        r2 = generate_greatsword_mesh(style="flamberge")
        assert r1["vertices"] != r2["vertices"]

    def test_poly_count_reasonable(self):
        result = generate_greatsword_mesh()
        assert result["metadata"]["poly_count"] < 1000

    def test_height_greater_than_1m(self):
        result = generate_greatsword_mesh()
        assert result["metadata"]["dimensions"]["height"] > 1.0


# ---------------------------------------------------------------------------
# CURVED SWORD tests
# ---------------------------------------------------------------------------


class TestCurvedSword:
    """Test curved sword mesh generator."""

    @pytest.mark.parametrize("style", ["scimitar", "katana", "falchion"])
    def test_styles(self, style):
        result = generate_curved_sword_mesh(style=style)
        validate_mesh_spec(result, f"CurvedSword_{style}", min_verts=40, min_faces=15)
        validate_weapon_metadata(result, f"CurvedSword_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_curved_sword_mesh(style="scimitar")
        r2 = generate_curved_sword_mesh(style="katana")
        assert r1["vertices"] != r2["vertices"]

    def test_poly_count_reasonable(self):
        result = generate_curved_sword_mesh()
        assert result["metadata"]["poly_count"] < 800


# ---------------------------------------------------------------------------
# HAND AXE tests
# ---------------------------------------------------------------------------


class TestHandAxe:
    """Test hand axe mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "bearded", "tomahawk"])
    def test_styles(self, style):
        result = generate_hand_axe_mesh(style=style)
        validate_mesh_spec(result, f"HandAxe_{style}", min_verts=20, min_faces=8)
        validate_weapon_metadata(result, f"HandAxe_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_hand_axe_mesh(style="standard")
        r2 = generate_hand_axe_mesh(style="bearded")
        assert r1["vertices"] != r2["vertices"]

    def test_poly_count_reasonable(self):
        result = generate_hand_axe_mesh()
        assert result["metadata"]["poly_count"] < 500


# ---------------------------------------------------------------------------
# BATTLE AXE tests
# ---------------------------------------------------------------------------


class TestBattleAxe:
    """Test battle axe mesh generator."""

    @pytest.mark.parametrize("style", ["double", "crescent", "single_large"])
    def test_styles(self, style):
        result = generate_battle_axe_mesh(style=style)
        validate_mesh_spec(result, f"BattleAxe_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"BattleAxe_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_battle_axe_mesh(style="double")
        r2 = generate_battle_axe_mesh(style="crescent")
        assert r1["vertices"] != r2["vertices"]

    def test_double_has_more_geometry(self):
        r_double = generate_battle_axe_mesh(style="double")
        r_single = generate_battle_axe_mesh(style="single_large")
        assert r_double["metadata"]["vertex_count"] > r_single["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# GREATAXE tests
# ---------------------------------------------------------------------------


class TestGreataxe:
    """Test greataxe mesh generator."""

    @pytest.mark.parametrize("style", ["massive", "cleaver", "moon"])
    def test_styles(self, style):
        result = generate_greataxe_mesh(style=style)
        validate_mesh_spec(result, f"Greataxe_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"Greataxe_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_greataxe_mesh(style="massive")
        r2 = generate_greataxe_mesh(style="moon")
        assert r1["vertices"] != r2["vertices"]

    def test_height_greater_than_1m(self):
        result = generate_greataxe_mesh()
        assert result["metadata"]["dimensions"]["height"] > 1.0


# ---------------------------------------------------------------------------
# CLUB tests
# ---------------------------------------------------------------------------


class TestClub:
    """Test club mesh generator."""

    @pytest.mark.parametrize("style", ["wooden", "spiked", "bone"])
    def test_styles(self, style):
        result = generate_club_mesh(style=style)
        validate_mesh_spec(result, f"Club_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"Club_{style}")

    def test_spiked_has_more_geometry(self):
        r_wood = generate_club_mesh(style="wooden")
        r_spiked = generate_club_mesh(style="spiked")
        assert r_spiked["metadata"]["vertex_count"] > r_wood["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# MACE tests
# ---------------------------------------------------------------------------


class TestMace:
    """Test mace mesh generator."""

    @pytest.mark.parametrize("style", ["flanged", "studded", "morningstar"])
    def test_styles(self, style):
        result = generate_mace_mesh(style=style)
        validate_mesh_spec(result, f"Mace_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"Mace_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_mace_mesh(style="flanged")
        r2 = generate_mace_mesh(style="morningstar")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# WARHAMMER tests
# ---------------------------------------------------------------------------


class TestWarhammer:
    """Test warhammer mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "maul", "lucerne"])
    def test_styles(self, style):
        result = generate_warhammer_mesh(style=style)
        validate_mesh_spec(result, f"Warhammer_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"Warhammer_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_warhammer_mesh(style="standard")
        r2 = generate_warhammer_mesh(style="lucerne")
        assert r1["vertices"] != r2["vertices"]

    def test_lucerne_has_spike(self):
        r = generate_warhammer_mesh(style="lucerne")
        assert r["metadata"]["vertex_count"] > generate_warhammer_mesh(style="standard")["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# HALBERD tests
# ---------------------------------------------------------------------------


class TestHalberd:
    """Test halberd mesh generator."""

    @pytest.mark.parametrize("style", ["standard", "voulge", "partisan"])
    def test_styles(self, style):
        result = generate_halberd_mesh(style=style)
        validate_mesh_spec(result, f"Halberd_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"Halberd_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_halberd_mesh(style="standard")
        r2 = generate_halberd_mesh(style="partisan")
        assert r1["vertices"] != r2["vertices"]

    def test_height_greater_than_1_5m(self):
        result = generate_halberd_mesh()
        assert result["metadata"]["dimensions"]["height"] > 1.5


# ---------------------------------------------------------------------------
# GLAIVE tests
# ---------------------------------------------------------------------------


class TestGlaive:
    """Test glaive mesh generator."""

    @pytest.mark.parametrize("style", ["curved", "naginata", "guandao"])
    def test_styles(self, style):
        result = generate_glaive_mesh(style=style)
        validate_mesh_spec(result, f"Glaive_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"Glaive_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_glaive_mesh(style="curved")
        r2 = generate_glaive_mesh(style="guandao")
        assert r1["vertices"] != r2["vertices"]

    def test_height_greater_than_1_5m(self):
        result = generate_glaive_mesh()
        assert result["metadata"]["dimensions"]["height"] > 1.5


# ---------------------------------------------------------------------------
# SHORTBOW tests
# ---------------------------------------------------------------------------


class TestShortbow:
    """Test shortbow mesh generator."""

    @pytest.mark.parametrize("style", ["recurve", "flat", "composite"])
    def test_styles(self, style):
        result = generate_shortbow_mesh(style=style)
        validate_mesh_spec(result, f"Shortbow_{style}", min_verts=30, min_faces=10)
        validate_weapon_metadata(result, f"Shortbow_{style}")

    def test_composite_has_wraps(self):
        r_flat = generate_shortbow_mesh(style="flat")
        r_comp = generate_shortbow_mesh(style="composite")
        assert r_comp["metadata"]["vertex_count"] > r_flat["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# LONGBOW tests
# ---------------------------------------------------------------------------


class TestLongbow:
    """Test longbow mesh generator."""

    @pytest.mark.parametrize("style", ["recurve", "english", "elven"])
    def test_styles(self, style):
        result = generate_longbow_mesh(style=style)
        validate_mesh_spec(result, f"Longbow_{style}", min_verts=40, min_faces=15)
        validate_weapon_metadata(result, f"Longbow_{style}")

    def test_longbow_taller_than_shortbow(self):
        r_short = generate_shortbow_mesh()
        r_long = generate_longbow_mesh()
        assert r_long["metadata"]["dimensions"]["height"] > r_short["metadata"]["dimensions"]["height"]

    def test_elven_has_inlays(self):
        r_eng = generate_longbow_mesh(style="english")
        r_elven = generate_longbow_mesh(style="elven")
        assert r_elven["metadata"]["vertex_count"] > r_eng["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# STAFF MAGIC tests
# ---------------------------------------------------------------------------


class TestStaffMagic:
    """Test magic staff mesh generator."""

    @pytest.mark.parametrize("style", ["gnarled", "crystal", "runic"])
    def test_styles(self, style):
        result = generate_staff_magic_mesh(style=style)
        validate_mesh_spec(result, f"StaffMagic_{style}", min_verts=50, min_faces=20)
        validate_weapon_metadata(result, f"StaffMagic_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_staff_magic_mesh(style="gnarled")
        r2 = generate_staff_magic_mesh(style="crystal")
        assert r1["vertices"] != r2["vertices"]

    def test_height_greater_than_1m(self):
        result = generate_staff_magic_mesh()
        assert result["metadata"]["dimensions"]["height"] > 1.0


# ---------------------------------------------------------------------------
# WAND tests
# ---------------------------------------------------------------------------


class TestWand:
    """Test wand mesh generator."""

    @pytest.mark.parametrize("style", ["straight", "twisted", "bone"])
    def test_styles(self, style):
        result = generate_wand_mesh(style=style)
        validate_mesh_spec(result, f"Wand_{style}", min_verts=20, min_faces=8)
        validate_weapon_metadata(result, f"Wand_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_wand_mesh(style="straight")
        r2 = generate_wand_mesh(style="twisted")
        assert r1["vertices"] != r2["vertices"]

    def test_wand_shorter_than_staff(self):
        r_wand = generate_wand_mesh()
        r_staff = generate_staff_magic_mesh()
        assert r_wand["metadata"]["dimensions"]["height"] < r_staff["metadata"]["dimensions"]["height"]


# ---------------------------------------------------------------------------
# THROWING KNIFE WEAPON tests
# ---------------------------------------------------------------------------


class TestThrowingKnifeWeapon:
    """Test throwing knife weapon mesh generator."""

    @pytest.mark.parametrize("style", ["balanced", "kunai", "star"])
    def test_styles(self, style):
        result = generate_throwing_knife_weapon_mesh(style=style)
        validate_mesh_spec(result, f"ThrowingKnifeWeapon_{style}", min_verts=10, min_faces=4)
        validate_weapon_metadata(result, f"ThrowingKnifeWeapon_{style}")

    def test_different_styles_different_geometry(self):
        r1 = generate_throwing_knife_weapon_mesh(style="balanced")
        r2 = generate_throwing_knife_weapon_mesh(style="star")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------


class TestWeaponRegistry:
    """Test that all weapon generators are properly registered."""

    def test_weapon_category_exists(self):
        assert "weapon" in GENERATORS

    def test_weapon_count_at_least_23(self):
        assert len(GENERATORS["weapon"]) >= 23

    def test_new_weapons_registered(self):
        new_weapons = [
            "greatsword", "curved_sword", "hand_axe", "battle_axe", "greataxe",
            "club", "mace", "warhammer", "halberd", "glaive",
            "shortbow", "longbow", "staff_magic", "wand", "throwing_knife_weapon",
        ]
        for name in new_weapons:
            assert name in GENERATORS["weapon"], f"{name} not registered"

    def test_original_weapons_still_registered(self):
        originals = ["hammer", "spear", "crossbow", "scythe", "flail", "whip", "claw", "tome"]
        for name in originals:
            assert name in GENERATORS["weapon"], f"{name} missing from registry"

    def test_all_generators_callable(self):
        for name, func in GENERATORS["weapon"].items():
            assert callable(func), f"weapon/{name} is not callable"

    def test_all_generators_produce_valid_mesh(self):
        """Smoke test: call every weapon generator with defaults and validate output."""
        for name, func in GENERATORS["weapon"].items():
            result = func()
            validate_mesh_spec(result, f"weapon/{name}")

    def test_all_new_generators_have_weapon_metadata(self):
        """All new generators must have grip_point, trail_top, trail_bottom."""
        new_weapons = [
            "greatsword", "curved_sword", "hand_axe", "battle_axe", "greataxe",
            "club", "mace", "warhammer", "halberd", "glaive",
            "shortbow", "longbow", "staff_magic", "wand", "throwing_knife_weapon",
        ]
        for name in new_weapons:
            result = GENERATORS["weapon"][name]()
            validate_weapon_metadata(result, f"weapon/{name}")
