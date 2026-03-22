"""Tests for combat & creature procedural mesh generators.

Validates that every generator in categories 11-14 returns valid mesh data:
- Non-empty vertex and face lists
- All face indices reference valid vertices
- Reasonable vertex/face counts for the object type
- Required metadata keys present
- Different styles produce different geometry
"""

from __future__ import annotations

import sys
import importlib.util

import pytest

# Load procedural_meshes without triggering blender_addon __init__ (needs bpy)
_spec = importlib.util.spec_from_file_location(
    "procedural_meshes",
    "blender_addon/handlers/procedural_meshes.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Monster Parts
generate_horn_mesh = _mod.generate_horn_mesh
generate_claw_set_mesh = _mod.generate_claw_set_mesh
generate_tail_mesh = _mod.generate_tail_mesh
generate_wing_mesh = _mod.generate_wing_mesh
generate_tentacle_mesh = _mod.generate_tentacle_mesh
generate_mandible_mesh = _mod.generate_mandible_mesh
generate_carapace_mesh = _mod.generate_carapace_mesh
generate_spine_ridge_mesh = _mod.generate_spine_ridge_mesh
generate_fang_mesh = _mod.generate_fang_mesh

# Monster Bodies
generate_humanoid_beast_body = _mod.generate_humanoid_beast_body
generate_quadruped_body = _mod.generate_quadruped_body
generate_serpent_body = _mod.generate_serpent_body
generate_insectoid_body = _mod.generate_insectoid_body
generate_skeletal_frame = _mod.generate_skeletal_frame
generate_golem_body = _mod.generate_golem_body

# Projectiles
generate_arrow_mesh = _mod.generate_arrow_mesh
generate_magic_orb_mesh = _mod.generate_magic_orb_mesh
generate_throwing_knife_mesh = _mod.generate_throwing_knife_mesh
generate_bomb_mesh = _mod.generate_bomb_mesh

# Armor
generate_helmet_mesh = _mod.generate_helmet_mesh
generate_pauldron_mesh = _mod.generate_pauldron_mesh
generate_gauntlet_mesh = _mod.generate_gauntlet_mesh
generate_greave_mesh = _mod.generate_greave_mesh
generate_breastplate_mesh = _mod.generate_breastplate_mesh
generate_shield_mesh = _mod.generate_shield_mesh

GENERATORS = _mod.GENERATORS


# ---------------------------------------------------------------------------
# Validation helper (same as in main test file)
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
# MONSTER PARTS tests
# ---------------------------------------------------------------------------


class TestMonsterParts:
    """Test monster part mesh generators."""

    @pytest.mark.parametrize("style", [
        "ram_curl", "demon_straight", "antler_branching", "unicorn_spiral",
    ])
    def test_horn_styles(self, style):
        result = generate_horn_mesh(style=style)
        validate_mesh_spec(result, f"Horn_{style}", min_verts=20, min_faces=8)

    def test_horn_different_styles_different_geometry(self):
        r1 = generate_horn_mesh(style="ram_curl")
        r2 = generate_horn_mesh(style="unicorn_spiral")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"] or \
               r1["vertices"] != r2["vertices"]

    def test_horn_custom_params(self):
        result = generate_horn_mesh(length=0.8, curve=1.0, segments=12)
        validate_mesh_spec(result, "Horn_custom")

    def test_claw_set_default(self):
        result = generate_claw_set_mesh()
        validate_mesh_spec(result, "ClawSet", min_verts=30, min_faces=10)

    def test_claw_set_finger_count(self):
        r3 = generate_claw_set_mesh(fingers=3)
        r6 = generate_claw_set_mesh(fingers=6)
        assert r6["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_claw_set_poly_count_reasonable(self):
        result = generate_claw_set_mesh(fingers=4)
        assert result["metadata"]["poly_count"] < 2000

    @pytest.mark.parametrize("tip_style", [
        "spike", "club", "blade", "whip", "stinger",
    ])
    def test_tail_tip_styles(self, tip_style):
        result = generate_tail_mesh(tip_style=tip_style)
        validate_mesh_spec(result, f"Tail_{tip_style}", min_verts=40, min_faces=15)

    def test_tail_different_tips_different_geometry(self):
        r1 = generate_tail_mesh(tip_style="spike")
        r2 = generate_tail_mesh(tip_style="club")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"] or \
               r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", [
        "bat_leather", "dragon_scaled", "skeletal_bone", "feathered",
    ])
    def test_wing_styles(self, style):
        result = generate_wing_mesh(style=style)
        validate_mesh_spec(result, f"Wing_{style}", min_verts=20, min_faces=5)

    def test_wing_different_styles_different_geometry(self):
        r1 = generate_wing_mesh(style="bat_leather")
        r2 = generate_wing_mesh(style="skeletal_bone")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"] or \
               r1["vertices"] != r2["vertices"]

    def test_wing_no_membrane(self):
        r_mem = generate_wing_mesh(membrane=True)
        r_no = generate_wing_mesh(membrane=False)
        assert r_mem["metadata"]["vertex_count"] >= r_no["metadata"]["vertex_count"]

    def test_tentacle_default(self):
        result = generate_tentacle_mesh()
        validate_mesh_spec(result, "Tentacle", min_verts=50, min_faces=20)

    def test_tentacle_no_suckers(self):
        r_suck = generate_tentacle_mesh(suckers=True)
        r_no = generate_tentacle_mesh(suckers=False)
        assert r_suck["metadata"]["vertex_count"] > r_no["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["insect", "spider"])
    def test_mandible_styles(self, style):
        result = generate_mandible_mesh(style=style)
        validate_mesh_spec(result, f"Mandible_{style}", min_verts=20, min_faces=8)

    def test_mandible_different_styles(self):
        r1 = generate_mandible_mesh(style="insect")
        r2 = generate_mandible_mesh(style="spider")
        assert r1["vertices"] != r2["vertices"]

    def test_carapace_default(self):
        result = generate_carapace_mesh()
        validate_mesh_spec(result, "Carapace", min_verts=30, min_faces=10)

    def test_carapace_segment_count(self):
        r3 = generate_carapace_mesh(segments=3)
        r8 = generate_carapace_mesh(segments=8)
        assert r8["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_spine_ridge_default(self):
        result = generate_spine_ridge_mesh()
        validate_mesh_spec(result, "SpineRidge", min_verts=20, min_faces=8)

    def test_spine_ridge_count_variation(self):
        r3 = generate_spine_ridge_mesh(count=3)
        r12 = generate_spine_ridge_mesh(count=12)
        assert r12["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_fang_default(self):
        result = generate_fang_mesh()
        validate_mesh_spec(result, "Fangs", min_verts=20, min_faces=8)

    def test_fang_count_variation(self):
        r2 = generate_fang_mesh(count=2)
        r8 = generate_fang_mesh(count=8)
        assert r8["metadata"]["vertex_count"] > r2["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# MONSTER BODIES tests
# ---------------------------------------------------------------------------


class TestMonsterBodies:
    """Test monster body mesh generators."""

    def test_humanoid_beast_default(self):
        result = generate_humanoid_beast_body()
        validate_mesh_spec(result, "HumanoidBeast", min_verts=100, min_faces=40)

    def test_humanoid_beast_bulk(self):
        r1 = generate_humanoid_beast_body(bulk=1.0)
        r2 = generate_humanoid_beast_body(bulk=2.0)
        d1 = r1["metadata"]["dimensions"]
        d2 = r2["metadata"]["dimensions"]
        assert d2["width"] > d1["width"]

    def test_humanoid_beast_poly_reasonable(self):
        result = generate_humanoid_beast_body()
        assert result["metadata"]["poly_count"] < 5000

    def test_quadruped_default(self):
        result = generate_quadruped_body()
        validate_mesh_spec(result, "Quadruped", min_verts=100, min_faces=40)

    def test_quadruped_poly_reasonable(self):
        result = generate_quadruped_body()
        assert result["metadata"]["poly_count"] < 5000

    def test_serpent_default(self):
        result = generate_serpent_body()
        validate_mesh_spec(result, "Serpent", min_verts=100, min_faces=50)

    def test_serpent_segment_count(self):
        r8 = generate_serpent_body(segments=8)
        r32 = generate_serpent_body(segments=32)
        assert r32["metadata"]["vertex_count"] > r8["metadata"]["vertex_count"]

    def test_insectoid_default(self):
        result = generate_insectoid_body()
        validate_mesh_spec(result, "Insectoid", min_verts=50, min_faces=20)

    def test_insectoid_leg_pairs(self):
        r2 = generate_insectoid_body(leg_pairs=2)
        r6 = generate_insectoid_body(leg_pairs=6)
        assert r6["metadata"]["vertex_count"] > r2["metadata"]["vertex_count"]

    def test_skeletal_frame_default(self):
        result = generate_skeletal_frame()
        validate_mesh_spec(result, "SkeletalFrame", min_verts=100, min_faces=40)

    def test_skeletal_frame_poly_reasonable(self):
        result = generate_skeletal_frame()
        assert result["metadata"]["poly_count"] < 5000

    @pytest.mark.parametrize("style", [
        "stone_rough", "crystal", "iron_plates", "wood_twisted",
    ])
    def test_golem_styles(self, style):
        result = generate_golem_body(material_style=style)
        validate_mesh_spec(result, f"Golem_{style}", min_verts=100, min_faces=40)

    def test_golem_different_styles_different_geometry(self):
        r1 = generate_golem_body(material_style="stone_rough")
        r2 = generate_golem_body(material_style="crystal")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# PROJECTILES tests
# ---------------------------------------------------------------------------


class TestProjectiles:
    """Test projectile mesh generators."""

    @pytest.mark.parametrize("head_style", [
        "broadhead", "bodkin", "barbed", "fire",
    ])
    def test_arrow_styles(self, head_style):
        result = generate_arrow_mesh(head_style=head_style)
        validate_mesh_spec(result, f"Arrow_{head_style}", min_verts=15, min_faces=5)

    def test_arrow_different_styles_different_geometry(self):
        r1 = generate_arrow_mesh(head_style="broadhead")
        r2 = generate_arrow_mesh(head_style="fire")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"] or \
               r1["vertices"] != r2["vertices"]

    def test_arrow_poly_reasonable(self):
        result = generate_arrow_mesh()
        assert result["metadata"]["poly_count"] < 500

    @pytest.mark.parametrize("style", [
        "smooth", "crackling", "void_rift", "flame_core",
    ])
    def test_magic_orb_styles(self, style):
        result = generate_magic_orb_mesh(style=style)
        validate_mesh_spec(result, f"MagicOrb_{style}", min_verts=20, min_faces=10)

    def test_magic_orb_different_styles(self):
        r1 = generate_magic_orb_mesh(style="smooth")
        r2 = generate_magic_orb_mesh(style="crackling")
        assert r1["vertices"] != r2["vertices"]

    def test_throwing_knife(self):
        result = generate_throwing_knife_mesh()
        validate_mesh_spec(result, "ThrowingKnife", min_verts=15, min_faces=5)

    def test_throwing_knife_poly_reasonable(self):
        result = generate_throwing_knife_mesh()
        assert result["metadata"]["poly_count"] < 500

    @pytest.mark.parametrize("style", [
        "round_fused", "flask_potion", "crystal_charge",
    ])
    def test_bomb_styles(self, style):
        result = generate_bomb_mesh(style=style)
        validate_mesh_spec(result, f"Bomb_{style}", min_verts=20, min_faces=8)

    def test_bomb_different_styles(self):
        r1 = generate_bomb_mesh(style="round_fused")
        r2 = generate_bomb_mesh(style="crystal_charge")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# ARMOR tests
# ---------------------------------------------------------------------------


class TestArmor:
    """Test armor mesh generators."""

    @pytest.mark.parametrize("style", [
        "open_face", "full_helm", "crown", "hood_chainmail", "horned_viking",
    ])
    def test_helmet_styles(self, style):
        result = generate_helmet_mesh(style=style)
        validate_mesh_spec(result, f"Helmet_{style}", min_verts=20, min_faces=8)

    def test_helmet_different_styles(self):
        r1 = generate_helmet_mesh(style="open_face")
        r2 = generate_helmet_mesh(style="crown")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", [
        "plate_smooth", "plate_spiked", "leather_layered",
    ])
    def test_pauldron_styles(self, style):
        result = generate_pauldron_mesh(style=style)
        validate_mesh_spec(result, f"Pauldron_{style}", min_verts=10, min_faces=4)

    def test_pauldron_left_vs_right(self):
        r_left = generate_pauldron_mesh(side="left")
        r_right = generate_pauldron_mesh(side="right")
        assert r_left["vertices"] != r_right["vertices"]

    @pytest.mark.parametrize("style", [
        "plate_fingers", "chainmail_glove", "claw_tipped",
    ])
    def test_gauntlet_styles(self, style):
        result = generate_gauntlet_mesh(style=style)
        validate_mesh_spec(result, f"Gauntlet_{style}", min_verts=20, min_faces=8)

    def test_gauntlet_different_styles(self):
        r1 = generate_gauntlet_mesh(style="plate_fingers")
        r2 = generate_gauntlet_mesh(style="claw_tipped")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", [
        "plate_shin", "leather_wrapped", "bone_strapped",
    ])
    def test_greave_styles(self, style):
        result = generate_greave_mesh(style=style)
        validate_mesh_spec(result, f"Greave_{style}", min_verts=20, min_faces=8)

    def test_greave_different_styles(self):
        r1 = generate_greave_mesh(style="plate_shin")
        r2 = generate_greave_mesh(style="bone_strapped")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", [
        "plate_full", "chainmail", "leather_studded", "bone_ribcage",
    ])
    def test_breastplate_styles(self, style):
        result = generate_breastplate_mesh(style=style)
        validate_mesh_spec(result, f"Breastplate_{style}", min_verts=30, min_faces=10)

    def test_breastplate_different_styles(self):
        r1 = generate_breastplate_mesh(style="plate_full")
        r2 = generate_breastplate_mesh(style="bone_ribcage")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", [
        "round_buckler", "kite_pointed", "tower_rectangular", "spiked_boss",
    ])
    def test_shield_styles(self, style):
        result = generate_shield_mesh(style=style)
        validate_mesh_spec(result, f"Shield_{style}", min_verts=15, min_faces=5)

    def test_shield_different_styles(self):
        r1 = generate_shield_mesh(style="round_buckler")
        r2 = generate_shield_mesh(style="kite_pointed")
        assert r1["vertices"] != r2["vertices"]

    def test_shield_size_scaling(self):
        r_small = generate_shield_mesh(size=0.5)
        r_large = generate_shield_mesh(size=2.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------


class TestCombatRegistry:
    """Test that all combat generators are properly registered."""

    def test_monster_part_category_exists(self):
        assert "monster_part" in GENERATORS

    def test_monster_body_category_exists(self):
        assert "monster_body" in GENERATORS

    def test_projectile_category_exists(self):
        assert "projectile" in GENERATORS

    def test_armor_category_exists(self):
        assert "armor" in GENERATORS

    def test_monster_part_count(self):
        assert len(GENERATORS["monster_part"]) == 9

    def test_monster_body_count(self):
        assert len(GENERATORS["monster_body"]) == 6

    def test_projectile_count(self):
        assert len(GENERATORS["projectile"]) >= 4

    def test_armor_count(self):
        assert len(GENERATORS["armor"]) >= 6

    def test_all_generators_callable(self):
        for category in ("monster_part", "monster_body", "projectile", "armor"):
            for name, func in GENERATORS[category].items():
                assert callable(func), f"{category}/{name} is not callable"

    def test_all_generators_produce_valid_mesh(self):
        """Smoke test: call every generator with defaults and validate output."""
        for category in ("monster_part", "monster_body", "projectile", "armor"):
            for name, func in GENERATORS[category].items():
                result = func()
                validate_mesh_spec(result, f"{category}/{name}")
