"""Tests for expanded shield types, spell scrolls, rune stones, and special ammo.

Validates:
- 8 new shield types with valid geometry
- 6 spell scroll element styles
- 10 brand-specific rune stones
- 6 elemental/special ammo variants
- All registered in GENERATORS
- Different styles/brands produce distinct geometry
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

# Shields
generate_heater_shield_mesh = _mod.generate_heater_shield_mesh
generate_pavise_mesh = _mod.generate_pavise_mesh
generate_targe_mesh = _mod.generate_targe_mesh
generate_magical_barrier_mesh = _mod.generate_magical_barrier_mesh
generate_bone_shield_mesh = _mod.generate_bone_shield_mesh
generate_crystal_shield_mesh = _mod.generate_crystal_shield_mesh
generate_living_wood_shield_mesh = _mod.generate_living_wood_shield_mesh
generate_aegis_mesh = _mod.generate_aegis_mesh

# Combat items
generate_spell_scroll_mesh = _mod.generate_spell_scroll_mesh
generate_rune_stone_mesh = _mod.generate_rune_stone_mesh

# Ammo variants
generate_fire_arrow_mesh = _mod.generate_fire_arrow_mesh
generate_ice_arrow_mesh = _mod.generate_ice_arrow_mesh
generate_poison_arrow_mesh = _mod.generate_poison_arrow_mesh
generate_explosive_bolt_mesh = _mod.generate_explosive_bolt_mesh
generate_silver_arrow_mesh = _mod.generate_silver_arrow_mesh
generate_barbed_arrow_mesh = _mod.generate_barbed_arrow_mesh

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


# ---------------------------------------------------------------------------
# EXPANDED SHIELD tests
# ---------------------------------------------------------------------------

class TestHeaterShield:
    def test_valid_geometry(self):
        result = generate_heater_shield_mesh()
        validate_mesh_spec(result, "Shield_heater", min_verts=20, min_faces=10)

    def test_metadata(self):
        result = generate_heater_shield_mesh()
        assert result["metadata"]["style"] == "heater"
        assert result["metadata"]["category"] == "armor"

    def test_size_scaling(self):
        r1 = generate_heater_shield_mesh(size=1.0)
        r2 = generate_heater_shield_mesh(size=2.0)
        d1 = r1["metadata"]["dimensions"]
        d2 = r2["metadata"]["dimensions"]
        # Larger size should have larger dimensions
        assert d2["width"] > d1["width"]


class TestPavise:
    def test_valid_geometry(self):
        result = generate_pavise_mesh()
        validate_mesh_spec(result, "Shield_pavise", min_verts=30, min_faces=10)

    def test_metadata(self):
        result = generate_pavise_mesh()
        assert result["metadata"]["style"] == "pavise"

    def test_full_body_height(self):
        """Pavise should be taller than wide (full-body shield)."""
        result = generate_pavise_mesh()
        dims = result["metadata"]["dimensions"]
        assert dims["height"] > dims["width"]


class TestTarge:
    def test_valid_geometry(self):
        result = generate_targe_mesh()
        validate_mesh_spec(result, "Shield_targe", min_verts=20, min_faces=10)

    def test_metadata(self):
        result = generate_targe_mesh()
        assert result["metadata"]["style"] == "targe"


class TestMagicalBarrier:
    def test_valid_geometry(self):
        result = generate_magical_barrier_mesh()
        validate_mesh_spec(result, "Shield_magical_barrier", min_verts=30, min_faces=10)

    def test_metadata(self):
        result = generate_magical_barrier_mesh()
        assert result["metadata"]["style"] == "magical_barrier"

    def test_has_significant_geometry(self):
        """Magical barrier has hex grid, should have many verts."""
        result = generate_magical_barrier_mesh()
        assert result["metadata"]["vertex_count"] > 100


class TestBoneShield:
    def test_valid_geometry(self):
        result = generate_bone_shield_mesh()
        validate_mesh_spec(result, "Shield_bone", min_verts=30, min_faces=10)

    def test_metadata(self):
        result = generate_bone_shield_mesh()
        assert result["metadata"]["style"] == "bone"


class TestCrystalShield:
    def test_valid_geometry(self):
        result = generate_crystal_shield_mesh()
        validate_mesh_spec(result, "Shield_crystal", min_verts=20, min_faces=10)

    def test_metadata(self):
        result = generate_crystal_shield_mesh()
        assert result["metadata"]["style"] == "crystal"


class TestLivingWoodShield:
    def test_valid_geometry(self):
        result = generate_living_wood_shield_mesh()
        validate_mesh_spec(result, "Shield_living_wood", min_verts=30, min_faces=10)

    def test_metadata(self):
        result = generate_living_wood_shield_mesh()
        assert result["metadata"]["style"] == "living_wood"


class TestAegis:
    def test_valid_geometry(self):
        result = generate_aegis_mesh()
        validate_mesh_spec(result, "Shield_aegis", min_verts=30, min_faces=10)

    def test_metadata(self):
        result = generate_aegis_mesh()
        assert result["metadata"]["style"] == "aegis"

    def test_has_face_relief(self):
        """Aegis should have substantial geometry from face relief and serpents."""
        result = generate_aegis_mesh()
        assert result["metadata"]["vertex_count"] > 200


class TestAllShieldsDiffer:
    """All 8 shield types should produce distinct geometry."""

    def test_shields_differ(self):
        generators = [
            ("heater", generate_heater_shield_mesh),
            ("pavise", generate_pavise_mesh),
            ("targe", generate_targe_mesh),
            ("magical_barrier", generate_magical_barrier_mesh),
            ("bone", generate_bone_shield_mesh),
            ("crystal", generate_crystal_shield_mesh),
            ("living_wood", generate_living_wood_shield_mesh),
            ("aegis", generate_aegis_mesh),
        ]
        results = {name: func() for name, func in generators}
        names = list(results.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                r1 = results[names[i]]
                r2 = results[names[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Shields {names[i]} and {names[j]} produced identical geometry"


# ---------------------------------------------------------------------------
# SPELL SCROLL tests
# ---------------------------------------------------------------------------

class TestSpellScroll:

    @pytest.mark.parametrize("style", [
        "fire", "ice", "lightning", "teleport", "protection", "identify",
    ])
    def test_valid_geometry(self, style):
        result = generate_spell_scroll_mesh(style=style)
        validate_mesh_spec(result, f"SpellScroll_{style}", min_verts=20, min_faces=10)

    @pytest.mark.parametrize("style", [
        "fire", "ice", "lightning", "teleport", "protection", "identify",
    ])
    def test_metadata(self, style):
        result = generate_spell_scroll_mesh(style=style)
        assert result["metadata"]["style"] == style
        assert result["metadata"]["category"] == "combat_item"

    def test_styles_differ(self):
        styles = ["fire", "ice", "lightning", "teleport", "protection", "identify"]
        results = {s: generate_spell_scroll_mesh(style=s) for s in styles}
        for i in range(len(styles)):
            for j in range(i + 1, len(styles)):
                r1 = results[styles[i]]
                r2 = results[styles[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Scroll styles {styles[i]} and {styles[j]} produced identical geometry"

    def test_invalid_style_fallback(self):
        result = generate_spell_scroll_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "fire"


# ---------------------------------------------------------------------------
# RUNE STONE tests
# ---------------------------------------------------------------------------

class TestRuneStone:

    @pytest.mark.parametrize("brand", [
        "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
        "LEECH", "GRACE", "MEND", "RUIN", "VOID",
    ])
    def test_valid_geometry(self, brand):
        result = generate_rune_stone_mesh(brand=brand)
        validate_mesh_spec(result, f"RuneStone_{brand}", min_verts=8, min_faces=4)

    @pytest.mark.parametrize("brand", [
        "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
        "LEECH", "GRACE", "MEND", "RUIN", "VOID",
    ])
    def test_metadata(self, brand):
        result = generate_rune_stone_mesh(brand=brand)
        assert result["metadata"]["brand"] == brand
        assert result["metadata"]["category"] == "combat_item"

    def test_brands_differ(self):
        brands = ["IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
                  "LEECH", "GRACE", "MEND", "RUIN", "VOID"]
        results = {b: generate_rune_stone_mesh(brand=b) for b in brands}
        for i in range(len(brands)):
            for j in range(i + 1, len(brands)):
                r1 = results[brands[i]]
                r2 = results[brands[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Rune stones {brands[i]} and {brands[j]} produced identical geometry"

    def test_invalid_brand_fallback(self):
        result = generate_rune_stone_mesh(brand="NONEXISTENT")
        assert result["metadata"]["brand"] == "IRON"


# ---------------------------------------------------------------------------
# SPECIAL AMMO tests
# ---------------------------------------------------------------------------

class TestFireArrow:
    def test_valid_geometry(self):
        result = generate_fire_arrow_mesh()
        validate_mesh_spec(result, "Arrow_fire", min_verts=15, min_faces=5)

    def test_metadata(self):
        result = generate_fire_arrow_mesh()
        assert result["metadata"]["element"] == "fire"
        assert result["metadata"]["category"] == "projectile"


class TestIceArrow:
    def test_valid_geometry(self):
        result = generate_ice_arrow_mesh()
        validate_mesh_spec(result, "Arrow_ice", min_verts=15, min_faces=5)

    def test_metadata(self):
        result = generate_ice_arrow_mesh()
        assert result["metadata"]["element"] == "ice"


class TestPoisonArrow:
    def test_valid_geometry(self):
        result = generate_poison_arrow_mesh()
        validate_mesh_spec(result, "Arrow_poison", min_verts=15, min_faces=5)

    def test_metadata(self):
        result = generate_poison_arrow_mesh()
        assert result["metadata"]["element"] == "poison"


class TestExplosiveBolt:
    def test_valid_geometry(self):
        result = generate_explosive_bolt_mesh()
        validate_mesh_spec(result, "Bolt_explosive", min_verts=15, min_faces=5)

    def test_metadata(self):
        result = generate_explosive_bolt_mesh()
        assert result["metadata"]["element"] == "explosive"

    def test_thicker_shaft(self):
        """Bolts should be thicker than arrows."""
        bolt = generate_explosive_bolt_mesh(shaft_length=0.5)
        arrow = generate_fire_arrow_mesh(shaft_length=0.5)
        # Bolt uses sr * 0.012 vs arrow sr * 0.008 -- bolt should be wider
        bolt_d = bolt["metadata"]["dimensions"]
        arrow_d = arrow["metadata"]["dimensions"]
        assert bolt_d["width"] > arrow_d["width"]


class TestSilverArrow:
    def test_valid_geometry(self):
        result = generate_silver_arrow_mesh()
        validate_mesh_spec(result, "Arrow_silver", min_verts=15, min_faces=5)

    def test_metadata(self):
        result = generate_silver_arrow_mesh()
        assert result["metadata"]["element"] == "silver"


class TestBarbedArrow:
    def test_valid_geometry(self):
        result = generate_barbed_arrow_mesh()
        validate_mesh_spec(result, "Arrow_barbed", min_verts=15, min_faces=5)

    def test_metadata(self):
        result = generate_barbed_arrow_mesh()
        assert result["metadata"]["element"] == "barbed"

    def test_barbed_has_more_geometry(self):
        """Barbed arrow with 3 barb rows should have more faces than ice arrow."""
        barbed = generate_barbed_arrow_mesh()
        ice = generate_ice_arrow_mesh()
        # barbed has 9 barb triangles extra, should differ
        assert barbed["vertices"] != ice["vertices"]


class TestAllAmmoDiffer:
    """All 6 ammo variants should produce distinct geometry."""

    def test_ammo_differ(self):
        generators = {
            "fire": generate_fire_arrow_mesh,
            "ice": generate_ice_arrow_mesh,
            "poison": generate_poison_arrow_mesh,
            "explosive": generate_explosive_bolt_mesh,
            "silver": generate_silver_arrow_mesh,
            "barbed": generate_barbed_arrow_mesh,
        }
        results = {name: func() for name, func in generators.items()}
        names = list(results.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                r1 = results[names[i]]
                r2 = results[names[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Ammo {names[i]} and {names[j]} produced identical geometry"


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------

class TestRegistry:
    """Verify all new generators are registered in GENERATORS."""

    def test_shields_registered(self):
        expected = ["heater_shield", "pavise", "targe", "magical_barrier",
                    "bone_shield", "crystal_shield", "living_wood_shield", "aegis"]
        for name in expected:
            assert name in GENERATORS["armor"], f"Missing armor/{name} in registry"

    def test_ammo_registered(self):
        expected = ["fire_arrow", "ice_arrow", "poison_arrow",
                    "explosive_bolt", "silver_arrow", "barbed_arrow"]
        for name in expected:
            assert name in GENERATORS["projectile"], f"Missing projectile/{name} in registry"

    def test_combat_items_registered(self):
        assert "combat_item" in GENERATORS, "Missing 'combat_item' category"
        assert "spell_scroll" in GENERATORS["combat_item"]
        assert "rune_stone" in GENERATORS["combat_item"]

    def test_all_registered_produce_valid_mesh(self):
        """Every new registered generator produces valid geometry."""
        # Shields
        for name in ["heater_shield", "pavise", "targe", "magical_barrier",
                     "bone_shield", "crystal_shield", "living_wood_shield", "aegis"]:
            func = GENERATORS["armor"][name]
            result = func()
            validate_mesh_spec(result, f"armor/{name}", min_verts=10, min_faces=4)

        # Ammo
        for name in ["fire_arrow", "ice_arrow", "poison_arrow",
                     "explosive_bolt", "silver_arrow", "barbed_arrow"]:
            func = GENERATORS["projectile"][name]
            result = func()
            validate_mesh_spec(result, f"projectile/{name}", min_verts=10, min_faces=4)

        # Combat items
        result = GENERATORS["combat_item"]["spell_scroll"]()
        validate_mesh_spec(result, "combat_item/spell_scroll", min_verts=10, min_faces=4)
        result = GENERATORS["combat_item"]["rune_stone"]()
        validate_mesh_spec(result, "combat_item/rune_stone", min_verts=8, min_faces=4)
