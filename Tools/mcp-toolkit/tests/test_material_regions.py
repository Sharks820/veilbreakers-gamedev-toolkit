"""Tests for material region assignment in body mesh generators.

Validates:
- Every face in NPC body meshes has a material region assigned
- Every face in monster body meshes has a material region assigned
- Material region names are valid strings
- NPC bodies have expected region types (body_skin, head_skin, extremity_skin)
- Monster bodies have body_skin for base and brand-specific regions for features
- Coverage is complete (no gaps in face indices)
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.npc_characters import (
    VALID_GENDERS,
    VALID_BUILDS,
    generate_npc_body_mesh,
)
from blender_addon.handlers.monster_bodies import (
    ALL_BODY_TYPES,
    ALL_BRANDS,
    generate_monster_body,
    _brand_material_region,
)


# ---------------------------------------------------------------------------
# NPC material region tests
# ---------------------------------------------------------------------------


NPC_COMBOS = [(g, b) for g in VALID_GENDERS for b in VALID_BUILDS]


class TestNPCMaterialRegions:
    """Validate material regions on NPC body meshes."""

    @pytest.mark.parametrize("gender,build", NPC_COMBOS,
                             ids=[f"{g}_{b}" for g, b in NPC_COMBOS])
    def test_every_face_has_region(self, gender, build):
        """Every face should have a material region assigned."""
        result = generate_npc_body_mesh(gender=gender, build=build)
        regions = result["material_regions"]
        faces = result["faces"]
        assert len(regions) == len(faces), (
            f"{gender}/{build}: regions={len(regions)}, faces={len(faces)}"
        )
        for fi in range(len(faces)):
            assert fi in regions, f"Face {fi} has no material region"

    @pytest.mark.parametrize("gender,build", NPC_COMBOS,
                             ids=[f"{g}_{b}" for g, b in NPC_COMBOS])
    def test_region_names_are_strings(self, gender, build):
        """All region values should be non-empty strings."""
        result = generate_npc_body_mesh(gender=gender, build=build)
        for fi, region in result["material_regions"].items():
            assert isinstance(region, str), f"Face {fi} region not a string"
            assert len(region) > 0, f"Face {fi} has empty region name"

    @pytest.mark.parametrize("gender,build", NPC_COMBOS,
                             ids=[f"{g}_{b}" for g, b in NPC_COMBOS])
    def test_expected_regions_present(self, gender, build):
        """NPC bodies should have body_skin, head_skin, and extremity_skin."""
        result = generate_npc_body_mesh(gender=gender, build=build)
        region_set = set(result["material_regions"].values())
        assert "body_skin" in region_set, f"Missing body_skin region"
        assert "head_skin" in region_set, f"Missing head_skin region"
        assert "extremity_skin" in region_set, f"Missing extremity_skin region"

    def test_metadata_has_region_names(self):
        """Metadata should list unique region names."""
        result = generate_npc_body_mesh(gender="male", build="average")
        meta = result["metadata"]
        assert "material_region_names" in meta
        names = meta["material_region_names"]
        assert isinstance(names, list)
        assert len(names) >= 3  # body_skin, head_skin, extremity_skin
        assert "body_skin" in names
        assert "head_skin" in names
        assert "extremity_skin" in names

    def test_body_skin_is_majority(self):
        """body_skin should be the largest region (torso + limbs)."""
        result = generate_npc_body_mesh(gender="male", build="average")
        regions = result["material_regions"]
        region_counts = {}
        for region in regions.values():
            region_counts[region] = region_counts.get(region, 0) + 1
        body_count = region_counts.get("body_skin", 0)
        for name, count in region_counts.items():
            if name != "body_skin":
                assert body_count >= count, (
                    f"body_skin ({body_count}) should be >= {name} ({count})"
                )

    def test_head_region_has_faces(self):
        """Head region should have a reasonable number of faces."""
        result = generate_npc_body_mesh(gender="male", build="average")
        regions = result["material_regions"]
        head_count = sum(1 for r in regions.values() if r == "head_skin")
        assert head_count >= 10, f"Only {head_count} head_skin faces, expected >= 10"

    def test_extremity_region_has_faces(self):
        """Extremity region (hands + feet) should have faces."""
        result = generate_npc_body_mesh(gender="male", build="average")
        regions = result["material_regions"]
        ext_count = sum(1 for r in regions.values() if r == "extremity_skin")
        assert ext_count >= 4, f"Only {ext_count} extremity_skin faces, expected >= 4"


# ---------------------------------------------------------------------------
# Monster material region tests
# ---------------------------------------------------------------------------


class TestMonsterMaterialRegions:
    """Validate material regions on monster body meshes."""

    @pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
    def test_every_face_has_region(self, body_type):
        """Every face should have a material region assigned."""
        result = generate_monster_body(body_type=body_type, brand="IRON")
        regions = result["material_regions"]
        faces = result["faces"]
        assert len(regions) == len(faces), (
            f"{body_type}: regions={len(regions)}, faces={len(faces)}"
        )
        for fi in range(len(faces)):
            assert fi in regions, f"Face {fi} has no material region"

    @pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
    def test_region_names_are_strings(self, body_type):
        """All region values should be non-empty strings."""
        result = generate_monster_body(body_type=body_type, brand="IRON")
        for fi, region in result["material_regions"].items():
            assert isinstance(region, str), f"Face {fi} region not a string"
            assert len(region) > 0, f"Face {fi} has empty region name"

    @pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
    def test_body_skin_present(self, body_type):
        """All monsters should have body_skin region."""
        result = generate_monster_body(body_type=body_type, brand="IRON")
        region_set = set(result["material_regions"].values())
        assert "body_skin" in region_set

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_brand_region_present(self, brand):
        """Brands with geometric features should have brand material region."""
        result = generate_monster_body(body_type="humanoid", brand=brand)
        regions = result["material_regions"]
        region_set = set(regions.values())
        expected_brand_region = _brand_material_region(brand)
        # Brand region should be present (all brands add geometry)
        assert expected_brand_region in region_set, (
            f"Brand {brand}: expected region '{expected_brand_region}' not found. "
            f"Found: {region_set}"
        )

    @pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_all_combos_complete_coverage(self, body_type, brand):
        """Every body_type x brand combo should have complete region coverage."""
        result = generate_monster_body(body_type=body_type, brand=brand)
        regions = result["material_regions"]
        faces = result["faces"]
        assert len(regions) == len(faces)


# ---------------------------------------------------------------------------
# Brand material region mapping tests
# ---------------------------------------------------------------------------


class TestBrandMaterialRegion:
    """Validate brand-to-material-region mapping."""

    def test_iron_is_metal(self):
        assert _brand_material_region("IRON") == "brand_metal"

    def test_savage_is_organic(self):
        assert _brand_material_region("SAVAGE") == "brand_organic"

    def test_venom_is_organic(self):
        assert _brand_material_region("VENOM") == "brand_organic"

    def test_leech_is_organic(self):
        assert _brand_material_region("LEECH") == "brand_organic"

    def test_surge_is_crystal(self):
        assert _brand_material_region("SURGE") == "brand_crystal"

    def test_grace_is_crystal(self):
        assert _brand_material_region("GRACE") == "brand_crystal"

    def test_mend_is_crystal(self):
        assert _brand_material_region("MEND") == "brand_crystal"

    def test_dread_is_dark(self):
        assert _brand_material_region("DREAD") == "brand_dark"

    def test_ruin_is_dark(self):
        assert _brand_material_region("RUIN") == "brand_dark"

    def test_void_is_dark(self):
        assert _brand_material_region("VOID") == "brand_dark"

    def test_all_brands_have_regions(self):
        """Every brand should map to a non-empty region string."""
        for brand in ALL_BRANDS:
            region = _brand_material_region(brand)
            assert isinstance(region, str)
            assert len(region) > 0
