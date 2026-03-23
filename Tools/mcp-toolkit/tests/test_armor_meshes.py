"""Tests for armor system mesh generators (armor_meshes.py).

Validates all 12 generator functions across 52 style variants:
- Non-empty vertex and face lists with valid indices
- Poly counts within expected ranges (1500-5000 target, relaxed for simpler pieces)
- Different styles produce distinct geometry
- ARMOR_GENERATORS registry is complete
- Metadata contains required fields
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Load armor_meshes without triggering blender_addon __init__ (needs bpy)
_HANDLERS_DIR = Path(__file__).resolve().parent.parent / "blender_addon" / "handlers"
_spec = importlib.util.spec_from_file_location(
    "armor_meshes",
    str(_HANDLERS_DIR / "armor_meshes.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

generate_helmet_mesh = _mod.generate_helmet_mesh
generate_chest_armor_mesh = _mod.generate_chest_armor_mesh
generate_gauntlet_mesh = _mod.generate_gauntlet_mesh
generate_boot_mesh = _mod.generate_boot_mesh
generate_pauldron_mesh = _mod.generate_pauldron_mesh
generate_cape_mesh = _mod.generate_cape_mesh
generate_belt_mesh = _mod.generate_belt_mesh
generate_bracer_mesh = _mod.generate_bracer_mesh
generate_ring_mesh = _mod.generate_ring_mesh
generate_amulet_mesh = _mod.generate_amulet_mesh
generate_back_item_mesh = _mod.generate_back_item_mesh
generate_face_item_mesh = _mod.generate_face_item_mesh
ARMOR_GENERATORS = _mod.ARMOR_GENERATORS


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
# HELMET tests
# ---------------------------------------------------------------------------

class TestHelmetMesh:
    """Test helmet generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "open_face", "full_helm", "hood", "crown", "skull_mask",
    ])
    def test_helmet_style_valid(self, style):
        result = generate_helmet_mesh(style=style)
        validate_mesh_spec(result, f"Helmet_{style}", min_verts=30, min_faces=10)

    @pytest.mark.parametrize("style", [
        "open_face", "full_helm", "hood", "crown", "skull_mask",
    ])
    def test_helmet_metadata_fields(self, style):
        result = generate_helmet_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "helmet"
        assert meta["category"] == "armor"

    def test_helmet_styles_differ(self):
        results = {s: generate_helmet_mesh(style=s) for s in
                   ["open_face", "full_helm", "hood", "crown", "skull_mask"]}
        # Each pair should differ
        styles = list(results.keys())
        for i in range(len(styles)):
            for j in range(i + 1, len(styles)):
                r1 = results[styles[i]]
                r2 = results[styles[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Helmet styles {styles[i]} and {styles[j]} produced identical geometry"

    def test_helmet_poly_count_range(self):
        for style in ["open_face", "full_helm", "hood", "crown", "skull_mask"]:
            result = generate_helmet_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 10 <= pc <= 5000, (
                f"Helmet {style}: poly count {pc} outside expected range"
            )

    def test_helmet_invalid_style_fallback(self):
        result = generate_helmet_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "open_face"


# ---------------------------------------------------------------------------
# CHEST ARMOR tests
# ---------------------------------------------------------------------------

class TestChestArmorMesh:
    """Test chest armor generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "plate", "chain", "leather", "robes", "light",
    ])
    def test_chest_style_valid(self, style):
        result = generate_chest_armor_mesh(style=style)
        validate_mesh_spec(result, f"ChestArmor_{style}", min_verts=30, min_faces=10)

    @pytest.mark.parametrize("style", [
        "plate", "chain", "leather", "robes", "light",
    ])
    def test_chest_metadata_fields(self, style):
        result = generate_chest_armor_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "chest"
        assert meta["category"] == "armor"

    def test_chest_styles_differ(self):
        results = {s: generate_chest_armor_mesh(style=s)
                   for s in ["plate", "chain", "leather", "robes", "light"]}
        styles = list(results.keys())
        for i in range(len(styles)):
            for j in range(i + 1, len(styles)):
                r1 = results[styles[i]]
                r2 = results[styles[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Chest styles {styles[i]} and {styles[j]} produced identical geometry"

    def test_chest_poly_count_range(self):
        for style in ["plate", "chain", "leather", "robes", "light"]:
            result = generate_chest_armor_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 10 <= pc <= 5000, (
                f"Chest {style}: poly count {pc} outside expected range"
            )


# ---------------------------------------------------------------------------
# GAUNTLET tests
# ---------------------------------------------------------------------------

class TestGauntletMesh:
    """Test gauntlet generators across all 3 styles."""

    @pytest.mark.parametrize("style", ["plate", "leather", "wraps"])
    def test_gauntlet_style_valid(self, style):
        result = generate_gauntlet_mesh(style=style)
        validate_mesh_spec(result, f"Gauntlet_{style}", min_verts=20, min_faces=8)

    @pytest.mark.parametrize("style", ["plate", "leather", "wraps"])
    def test_gauntlet_metadata_fields(self, style):
        result = generate_gauntlet_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "gauntlet"
        assert meta["category"] == "armor"

    def test_gauntlet_styles_differ(self):
        results = {s: generate_gauntlet_mesh(style=s)
                   for s in ["plate", "leather", "wraps"]}
        styles = list(results.keys())
        for i in range(len(styles)):
            for j in range(i + 1, len(styles)):
                r1 = results[styles[i]]
                r2 = results[styles[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Gauntlet styles {styles[i]} and {styles[j]} produced identical geometry"

    def test_gauntlet_poly_count_range(self):
        for style in ["plate", "leather", "wraps"]:
            result = generate_gauntlet_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 8 <= pc <= 5000, (
                f"Gauntlet {style}: poly count {pc} outside expected range"
            )


# ---------------------------------------------------------------------------
# BOOT tests
# ---------------------------------------------------------------------------

class TestBootMesh:
    """Test boot generators across all 3 styles."""

    @pytest.mark.parametrize("style", ["plate", "leather", "sandals"])
    def test_boot_style_valid(self, style):
        result = generate_boot_mesh(style=style)
        validate_mesh_spec(result, f"Boot_{style}", min_verts=20, min_faces=8)

    @pytest.mark.parametrize("style", ["plate", "leather", "sandals"])
    def test_boot_metadata_fields(self, style):
        result = generate_boot_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "boot"
        assert meta["category"] == "armor"

    def test_boot_styles_differ(self):
        results = {s: generate_boot_mesh(style=s) for s in ["plate", "leather", "sandals"]}
        styles = list(results.keys())
        for i in range(len(styles)):
            for j in range(i + 1, len(styles)):
                r1 = results[styles[i]]
                r2 = results[styles[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Boot styles {styles[i]} and {styles[j]} produced identical geometry"

    def test_boot_poly_count_range(self):
        for style in ["plate", "leather", "sandals"]:
            result = generate_boot_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 8 <= pc <= 5000, (
                f"Boot {style}: poly count {pc} outside expected range"
            )


# ---------------------------------------------------------------------------
# PAULDRON tests
# ---------------------------------------------------------------------------

class TestPauldronMesh:
    """Test pauldron generators across all 3 styles."""

    @pytest.mark.parametrize("style", ["plate", "fur", "bone"])
    def test_pauldron_style_valid(self, style):
        result = generate_pauldron_mesh(style=style)
        validate_mesh_spec(result, f"Pauldron_{style}", min_verts=20, min_faces=8)

    @pytest.mark.parametrize("style", ["plate", "fur", "bone"])
    def test_pauldron_metadata_fields(self, style):
        result = generate_pauldron_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "pauldron"
        assert meta["category"] == "armor"

    def test_pauldron_side_left_right(self):
        r_left = generate_pauldron_mesh(style="plate", side="left")
        r_right = generate_pauldron_mesh(style="plate", side="right")
        assert r_left["metadata"]["side"] == "left"
        assert r_right["metadata"]["side"] == "right"
        # Geometry should differ (mirrored X)
        assert r_left["vertices"] != r_right["vertices"]

    def test_pauldron_styles_differ(self):
        results = {s: generate_pauldron_mesh(style=s) for s in ["plate", "fur", "bone"]}
        styles = list(results.keys())
        for i in range(len(styles)):
            for j in range(i + 1, len(styles)):
                r1 = results[styles[i]]
                r2 = results[styles[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Pauldron styles {styles[i]} and {styles[j]} produced identical geometry"

    def test_pauldron_poly_count_range(self):
        for style in ["plate", "fur", "bone"]:
            result = generate_pauldron_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 8 <= pc <= 5000, (
                f"Pauldron {style}: poly count {pc} outside expected range"
            )


# ---------------------------------------------------------------------------
# CAPE tests
# ---------------------------------------------------------------------------

class TestCapeMesh:
    """Test cape generators across all 3 styles."""

    @pytest.mark.parametrize("style", ["full", "half", "tattered"])
    def test_cape_style_valid(self, style):
        result = generate_cape_mesh(style=style)
        validate_mesh_spec(result, f"Cape_{style}", min_verts=20, min_faces=8)

    @pytest.mark.parametrize("style", ["full", "half", "tattered"])
    def test_cape_metadata_fields(self, style):
        result = generate_cape_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "cape"
        assert meta["category"] == "armor"

    def test_cape_styles_differ(self):
        results = {s: generate_cape_mesh(style=s) for s in ["full", "half", "tattered"]}
        styles = list(results.keys())
        for i in range(len(styles)):
            for j in range(i + 1, len(styles)):
                r1 = results[styles[i]]
                r2 = results[styles[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Cape styles {styles[i]} and {styles[j]} produced identical geometry"

    def test_cape_poly_count_range(self):
        for style in ["full", "half", "tattered"]:
            result = generate_cape_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 8 <= pc <= 5000, (
                f"Cape {style}: poly count {pc} outside expected range"
            )

    def test_full_cape_has_clasp(self):
        """Full cape should have clasp geometry (more verts than just the sheet)."""
        result = generate_cape_mesh(style="full")
        # 11x15 grid = 165 verts for sheet alone; clasp adds more
        assert result["metadata"]["vertex_count"] > 165


# ---------------------------------------------------------------------------
# BELT tests
# ---------------------------------------------------------------------------

class TestBeltMesh:
    """Test belt generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "leather", "chain", "rope", "ornate", "utility",
    ])
    def test_belt_style_valid(self, style):
        result = generate_belt_mesh(style=style)
        validate_mesh_spec(result, f"Belt_{style}", min_verts=20, min_faces=8)

    @pytest.mark.parametrize("style", [
        "leather", "chain", "rope", "ornate", "utility",
    ])
    def test_belt_metadata_fields(self, style):
        result = generate_belt_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "belt"
        assert meta["category"] == "armor"

    def test_belt_styles_differ(self):
        styles_list = ["leather", "chain", "rope", "ornate", "utility"]
        results = {s: generate_belt_mesh(style=s) for s in styles_list}
        for i in range(len(styles_list)):
            for j in range(i + 1, len(styles_list)):
                r1 = results[styles_list[i]]
                r2 = results[styles_list[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Belt styles {styles_list[i]} and {styles_list[j]} produced identical geometry"

    def test_belt_poly_count_range(self):
        for style in ["leather", "chain", "rope", "ornate", "utility"]:
            result = generate_belt_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 8 <= pc <= 5000, (
                f"Belt {style}: poly count {pc} outside expected range"
            )

    def test_belt_invalid_style_fallback(self):
        result = generate_belt_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "leather"

    def test_utility_belt_has_pouches(self):
        """Utility belt should have pouch geometry (significantly more verts)."""
        result = generate_belt_mesh(style="utility")
        simple = generate_belt_mesh(style="leather")
        assert result["metadata"]["vertex_count"] > simple["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# BRACER tests
# ---------------------------------------------------------------------------

class TestBracerMesh:
    """Test bracer generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "leather", "metal_vambrace", "enchanted", "chain", "bone",
    ])
    def test_bracer_style_valid(self, style):
        result = generate_bracer_mesh(style=style)
        validate_mesh_spec(result, f"Bracer_{style}", min_verts=20, min_faces=8)

    @pytest.mark.parametrize("style", [
        "leather", "metal_vambrace", "enchanted", "chain", "bone",
    ])
    def test_bracer_metadata_fields(self, style):
        result = generate_bracer_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "bracer"
        assert meta["category"] == "armor"

    def test_bracer_styles_differ(self):
        styles_list = ["leather", "metal_vambrace", "enchanted", "chain", "bone"]
        results = {s: generate_bracer_mesh(style=s) for s in styles_list}
        for i in range(len(styles_list)):
            for j in range(i + 1, len(styles_list)):
                r1 = results[styles_list[i]]
                r2 = results[styles_list[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Bracer styles {styles_list[i]} and {styles_list[j]} produced identical geometry"

    def test_bracer_poly_count_range(self):
        for style in ["leather", "metal_vambrace", "enchanted", "chain", "bone"]:
            result = generate_bracer_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 8 <= pc <= 5000, (
                f"Bracer {style}: poly count {pc} outside expected range"
            )

    def test_bracer_invalid_style_fallback(self):
        result = generate_bracer_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "leather"

    def test_enchanted_bracer_has_gem(self):
        """Enchanted bracer should have gem geometry (more verts than plain leather)."""
        result = generate_bracer_mesh(style="enchanted")
        simple = generate_bracer_mesh(style="leather")
        assert result["metadata"]["vertex_count"] > simple["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# RING tests
# ---------------------------------------------------------------------------

class TestRingMesh:
    """Test ring generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "band", "gem_set", "rune_etched", "signet", "twisted",
    ])
    def test_ring_style_valid(self, style):
        result = generate_ring_mesh(style=style)
        validate_mesh_spec(result, f"Ring_{style}", min_verts=10, min_faces=4)

    @pytest.mark.parametrize("style", [
        "band", "gem_set", "rune_etched", "signet", "twisted",
    ])
    def test_ring_metadata_fields(self, style):
        result = generate_ring_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "ring"
        assert meta["category"] == "armor"

    def test_ring_styles_differ(self):
        styles_list = ["band", "gem_set", "rune_etched", "signet", "twisted"]
        results = {s: generate_ring_mesh(style=s) for s in styles_list}
        for i in range(len(styles_list)):
            for j in range(i + 1, len(styles_list)):
                r1 = results[styles_list[i]]
                r2 = results[styles_list[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Ring styles {styles_list[i]} and {styles_list[j]} produced identical geometry"

    def test_ring_poly_count_range(self):
        for style in ["band", "gem_set", "rune_etched", "signet", "twisted"]:
            result = generate_ring_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 4 <= pc <= 5000, (
                f"Ring {style}: poly count {pc} outside expected range"
            )

    def test_ring_invalid_style_fallback(self):
        result = generate_ring_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "band"

    def test_gem_set_has_gem(self):
        """Gem-set ring should have more geometry than plain band."""
        gem = generate_ring_mesh(style="gem_set")
        band = generate_ring_mesh(style="band")
        assert gem["metadata"]["vertex_count"] > band["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# AMULET tests
# ---------------------------------------------------------------------------

class TestAmuletMesh:
    """Test amulet generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "pendant", "choker", "torc", "medallion", "holy_symbol",
    ])
    def test_amulet_style_valid(self, style):
        result = generate_amulet_mesh(style=style)
        validate_mesh_spec(result, f"Amulet_{style}", min_verts=10, min_faces=4)

    @pytest.mark.parametrize("style", [
        "pendant", "choker", "torc", "medallion", "holy_symbol",
    ])
    def test_amulet_metadata_fields(self, style):
        result = generate_amulet_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "amulet"
        assert meta["category"] == "armor"

    def test_amulet_styles_differ(self):
        styles_list = ["pendant", "choker", "torc", "medallion", "holy_symbol"]
        results = {s: generate_amulet_mesh(style=s) for s in styles_list}
        for i in range(len(styles_list)):
            for j in range(i + 1, len(styles_list)):
                r1 = results[styles_list[i]]
                r2 = results[styles_list[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"Amulet styles {styles_list[i]} and {styles_list[j]} produced identical geometry"

    def test_amulet_poly_count_range(self):
        for style in ["pendant", "choker", "torc", "medallion", "holy_symbol"]:
            result = generate_amulet_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 4 <= pc <= 5000, (
                f"Amulet {style}: poly count {pc} outside expected range"
            )

    def test_amulet_invalid_style_fallback(self):
        result = generate_amulet_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "pendant"

    def test_torc_is_open(self):
        """Torc should be an open ring (not closed like a choker)."""
        torc = generate_amulet_mesh(style="torc")
        choker = generate_amulet_mesh(style="choker")
        # Different topology
        assert torc["metadata"]["vertex_count"] != choker["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# BACK ITEM tests
# ---------------------------------------------------------------------------

class TestBackItemMesh:
    """Test back item generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "backpack", "quiver", "wings", "trophy_mount", "bedroll",
    ])
    def test_back_item_style_valid(self, style):
        result = generate_back_item_mesh(style=style)
        validate_mesh_spec(result, f"BackItem_{style}", min_verts=15, min_faces=6)

    @pytest.mark.parametrize("style", [
        "backpack", "quiver", "wings", "trophy_mount", "bedroll",
    ])
    def test_back_item_metadata_fields(self, style):
        result = generate_back_item_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "back_item"
        assert meta["category"] == "armor"

    def test_back_item_styles_differ(self):
        styles_list = ["backpack", "quiver", "wings", "trophy_mount", "bedroll"]
        results = {s: generate_back_item_mesh(style=s) for s in styles_list}
        for i in range(len(styles_list)):
            for j in range(i + 1, len(styles_list)):
                r1 = results[styles_list[i]]
                r2 = results[styles_list[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"BackItem styles {styles_list[i]} and {styles_list[j]} produced identical geometry"

    def test_back_item_poly_count_range(self):
        for style in ["backpack", "quiver", "wings", "trophy_mount", "bedroll"]:
            result = generate_back_item_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 6 <= pc <= 5000, (
                f"BackItem {style}: poly count {pc} outside expected range"
            )

    def test_back_item_invalid_style_fallback(self):
        result = generate_back_item_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "backpack"

    def test_wings_are_symmetric(self):
        """Wings should have geometry on both sides (positive and negative X)."""
        result = generate_back_item_mesh(style="wings")
        verts = result["vertices"]
        has_pos_x = any(v[0] > 0.01 for v in verts)
        has_neg_x = any(v[0] < -0.01 for v in verts)
        assert has_pos_x and has_neg_x, "Wings should span both sides of X axis"


# ---------------------------------------------------------------------------
# FACE ITEM tests
# ---------------------------------------------------------------------------

class TestFaceItemMesh:
    """Test face item generators across all 5 styles."""

    @pytest.mark.parametrize("style", [
        "mask", "blindfold", "war_paint_frame", "plague_doctor", "domino",
    ])
    def test_face_item_style_valid(self, style):
        result = generate_face_item_mesh(style=style)
        validate_mesh_spec(result, f"FaceItem_{style}", min_verts=15, min_faces=6)

    @pytest.mark.parametrize("style", [
        "mask", "blindfold", "war_paint_frame", "plague_doctor", "domino",
    ])
    def test_face_item_metadata_fields(self, style):
        result = generate_face_item_mesh(style=style)
        meta = result["metadata"]
        assert meta["style"] == style
        assert meta["slot"] == "face_item"
        assert meta["category"] == "armor"

    def test_face_item_styles_differ(self):
        styles_list = ["mask", "blindfold", "war_paint_frame", "plague_doctor", "domino"]
        results = {s: generate_face_item_mesh(style=s) for s in styles_list}
        for i in range(len(styles_list)):
            for j in range(i + 1, len(styles_list)):
                r1 = results[styles_list[i]]
                r2 = results[styles_list[j]]
                assert (
                    r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]
                    or r1["vertices"] != r2["vertices"]
                ), f"FaceItem styles {styles_list[i]} and {styles_list[j]} produced identical geometry"

    def test_face_item_poly_count_range(self):
        for style in ["mask", "blindfold", "war_paint_frame", "plague_doctor", "domino"]:
            result = generate_face_item_mesh(style=style)
            pc = result["metadata"]["poly_count"]
            assert 6 <= pc <= 5000, (
                f"FaceItem {style}: poly count {pc} outside expected range"
            )

    def test_face_item_invalid_style_fallback(self):
        result = generate_face_item_mesh(style="nonexistent")
        assert result["metadata"]["style"] == "mask"

    def test_plague_doctor_has_beak(self):
        """Plague doctor mask should have significantly more geometry than domino."""
        plague = generate_face_item_mesh(style="plague_doctor")
        domino = generate_face_item_mesh(style="domino")
        assert plague["metadata"]["vertex_count"] > domino["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------

class TestArmorRegistry:
    """Test the ARMOR_GENERATORS registry completeness."""

    def test_registry_has_all_slots(self):
        expected_slots = {
            "helmet", "chest_armor", "gauntlet", "boot", "pauldron", "cape",
            "belt", "bracer", "ring", "amulet", "back_item", "face_item",
        }
        assert set(ARMOR_GENERATORS.keys()) == expected_slots

    def test_registry_entries_are_tuples(self):
        for slot, entry in ARMOR_GENERATORS.items():
            assert isinstance(entry, tuple), f"{slot}: entry is not a tuple"
            assert len(entry) == 2, f"{slot}: entry should be (func, meta)"
            func, meta = entry
            assert callable(func), f"{slot}: first element not callable"
            assert isinstance(meta, dict), f"{slot}: second element not dict"
            assert "styles" in meta, f"{slot}: meta missing 'styles'"
            assert isinstance(meta["styles"], list), f"{slot}: styles not a list"

    def test_registry_style_counts(self):
        expected = {
            "helmet": 5,
            "chest_armor": 5,
            "gauntlet": 3,
            "boot": 3,
            "pauldron": 3,
            "cape": 3,
            "belt": 5,
            "bracer": 5,
            "ring": 5,
            "amulet": 5,
            "back_item": 5,
            "face_item": 5,
        }
        for slot, count in expected.items():
            styles = ARMOR_GENERATORS[slot][1]["styles"]
            assert len(styles) == count, (
                f"{slot}: expected {count} styles, got {len(styles)}"
            )

    def test_registry_all_styles_generate_valid_mesh(self):
        """Comprehensive test: every (slot, style) in the registry produces valid geometry."""
        for slot, (func, meta) in ARMOR_GENERATORS.items():
            for style in meta["styles"]:
                result = func(style=style)
                validate_mesh_spec(result, f"{slot}_{style}", min_verts=10, min_faces=4)

    def test_total_style_count_is_52(self):
        total = sum(len(meta["styles"]) for _, (_, meta) in ARMOR_GENERATORS.items())
        assert total == 52, f"Expected 52 total styles, got {total}"
