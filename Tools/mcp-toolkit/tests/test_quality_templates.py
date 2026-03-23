"""Unit tests for quality_templates.py -- Unity C# AAA quality scripts.

Tests cover:
- AAA-02: Polygon budget check (all asset types)
- AAA-04: Master material library (default + custom materials)
- AAA-06: Texture quality validation (texel density, normal maps, channel packing)
- Combined AAA validation audit
- C# brace balance verification
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.quality_templates import (
    generate_aaa_validation_script,
    generate_master_material_script,
    generate_poly_budget_check_script,
    generate_texture_quality_check_script,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_brace_balance(text: str) -> bool:
    """Check that curly braces are balanced in generated C# code."""
    count = 0
    for ch in text:
        if ch == "{":
            count += 1
        elif ch == "}":
            count -= 1
        if count < 0:
            return False
    return count == 0


# ---------------------------------------------------------------------------
# TestPolyBudget (AAA-02)
# ---------------------------------------------------------------------------


class TestPolyBudget:
    """Tests for polygon budget check C# script generation."""

    def test_poly_budget_hero(self):
        """Hero type includes 40000-60000 budget range (AAA research values)."""
        script = generate_poly_budget_check_script("hero")
        assert "40000" in script
        assert "60000" in script

    def test_poly_budget_mob(self):
        """Mob type includes 15000-35000 budget range (AAA research values)."""
        script = generate_poly_budget_check_script("mob")
        assert "15000" in script
        assert "35000" in script

    def test_poly_budget_weapon(self):
        """Weapon type includes 3000-8000 budget range."""
        script = generate_poly_budget_check_script("weapon")
        assert "3000" in script
        assert "8000" in script

    def test_poly_budget_prop(self):
        """Prop type includes 500-5000 budget range (AAA research values)."""
        script = generate_poly_budget_check_script("prop")
        assert "500" in script
        assert "5000" in script

    def test_poly_budget_building(self):
        """Building type includes 5000-15000 budget range."""
        script = generate_poly_budget_check_script("building")
        assert "5000" in script
        assert "15000" in script

    def test_poly_budget_menu_item(self):
        """Script includes MenuItem attribute."""
        script = generate_poly_budget_check_script("prop")
        assert "MenuItem" in script
        assert "VeilBreakers/Quality/Check Poly Budget" in script

    def test_poly_budget_result_json(self):
        """Script writes to vb_result.json."""
        script = generate_poly_budget_check_script("prop")
        assert "vb_result.json" in script

    def test_poly_budget_balanced_braces(self):
        """Generated C# has balanced curly braces."""
        script = generate_poly_budget_check_script("hero")
        assert check_brace_balance(script), "Braces are unbalanced"

    def test_poly_budget_auto_flag_labels(self):
        """auto_flag=True includes asset labeling for retopo."""
        script = generate_poly_budget_check_script("hero", auto_flag=True)
        assert "vb_needs_retopo" in script

    def test_poly_budget_auto_flag_off(self):
        """auto_flag=False excludes asset labeling."""
        script = generate_poly_budget_check_script("hero", auto_flag=False)
        assert "vb_needs_retopo" not in script

    def test_poly_budget_custom_path(self):
        """Custom target_path is embedded in the script."""
        script = generate_poly_budget_check_script("prop", target_path="Assets/Models/Props")
        assert "Assets/Models/Props" in script

    def test_poly_budget_mesh_search(self):
        """Script uses FindAssets to search for meshes."""
        script = generate_poly_budget_check_script("prop")
        assert "FindAssets" in script
        assert "t:Mesh" in script


# ---------------------------------------------------------------------------
# TestMasterMaterials (AAA-04)
# ---------------------------------------------------------------------------


class TestMasterMaterials:
    """Tests for master material library C# script generation."""

    def test_master_materials_default(self):
        """Default script includes all 7 material names."""
        script = generate_master_material_script()
        for name in ["stone", "wood", "iron", "moss", "bone", "cloth", "leather"]:
            assert name in script, f"Missing material: {name}"

    def test_master_materials_urp_lit(self):
        """Script references URP Lit shader."""
        script = generate_master_material_script()
        assert "Universal Render Pipeline/Lit" in script

    def test_master_materials_properties(self):
        """Script sets _BaseColor, _Metallic, _Smoothness properties."""
        script = generate_master_material_script()
        assert "_BaseColor" in script
        assert "_Metallic" in script
        assert "_Smoothness" in script

    def test_master_materials_bump_scale(self):
        """Script sets _BumpScale for normal map intensity."""
        script = generate_master_material_script()
        assert "_BumpScale" in script

    def test_master_materials_create_asset(self):
        """Script uses AssetDatabase.CreateAsset to save materials."""
        script = generate_master_material_script()
        assert "AssetDatabase.CreateAsset" in script

    def test_master_materials_custom(self):
        """Custom materials list produces expected output."""
        custom = [
            {
                "name": "crystal",
                "color_hex": "44AADD",
                "metallic": 0.3,
                "roughness": 0.2,
                "normal_strength": 1.5,
            },
            {
                "name": "obsidian",
                "color_hex": "1A1A1A",
                "metallic": 0.1,
                "roughness": 0.3,
                "normal_strength": 0.8,
            },
        ]
        script = generate_master_material_script(materials=custom)
        assert "crystal" in script
        assert "obsidian" in script
        # Default materials should NOT be present
        assert "moss" not in script

    def test_master_materials_balanced_braces(self):
        """Generated C# has balanced curly braces."""
        script = generate_master_material_script()
        assert check_brace_balance(script), "Braces are unbalanced"

    def test_master_materials_folder_creation(self):
        """Script creates output folder hierarchy."""
        script = generate_master_material_script()
        assert "AssetDatabase.CreateFolder" in script
        assert "IsValidFolder" in script

    def test_master_materials_result_json(self):
        """Script writes result to vb_result.json."""
        script = generate_master_material_script()
        assert "vb_result.json" in script

    def test_master_materials_custom_folder(self):
        """Custom output folder is embedded in the script."""
        script = generate_master_material_script(output_folder="Assets/Art/Materials")
        assert "Assets/Art/Materials" in script


# ---------------------------------------------------------------------------
# TestTextureQuality (AAA-06)
# ---------------------------------------------------------------------------


class TestTextureQuality:
    """Tests for texture quality validation C# script generation."""

    def test_texture_quality_basic(self):
        """Script includes Texture2D search via FindAssets."""
        script = generate_texture_quality_check_script()
        assert "Texture2D" in script
        assert "FindAssets" in script

    def test_texture_quality_texel_density(self):
        """Script includes texel density check with configurable value."""
        script = generate_texture_quality_check_script()
        assert "10.24" in script
        assert "TargetTexelDensity" in script

    def test_texture_quality_custom_density(self):
        """Custom texel density value is embedded."""
        script = generate_texture_quality_check_script(target_texel_density=5.12)
        assert "5.12" in script

    def test_texture_quality_normal_check(self):
        """Normal map presence check is included when enabled."""
        script = generate_texture_quality_check_script(check_normal_maps=True)
        assert "_Normal" in script
        assert "Normal Map" in script or "normalSearch" in script

    def test_texture_quality_normal_disabled(self):
        """Normal map check can be disabled."""
        script = generate_texture_quality_check_script(check_normal_maps=False)
        assert "normalSearch" not in script

    def test_texture_quality_channel_packing(self):
        """Channel packing check includes MRA/ORM detection."""
        script = generate_texture_quality_check_script(check_channel_packing=True)
        assert "_MRA" in script
        assert "_ORM" in script
        assert "sRGBTexture" in script

    def test_texture_quality_packing_disabled(self):
        """Channel packing check can be disabled."""
        script = generate_texture_quality_check_script(check_channel_packing=False)
        assert "_MRA" not in script
        assert "_ORM" not in script

    def test_texture_quality_balanced_braces(self):
        """Generated C# has balanced curly braces."""
        script = generate_texture_quality_check_script()
        assert check_brace_balance(script), "Braces are unbalanced"

    def test_texture_quality_menu_item(self):
        """Script includes MenuItem for Quality menu."""
        script = generate_texture_quality_check_script()
        assert "MenuItem" in script
        assert "VeilBreakers/Quality/Check Texture Quality" in script

    def test_texture_quality_result_json(self):
        """Script writes result to vb_result.json."""
        script = generate_texture_quality_check_script()
        assert "vb_result.json" in script


# ---------------------------------------------------------------------------
# TestAAAValidation
# ---------------------------------------------------------------------------


class TestAAAValidation:
    """Tests for combined AAA validation audit C# script generation."""

    def test_aaa_validation_combined(self):
        """Combined script includes poly, texture, and material checks."""
        script = generate_aaa_validation_script()
        assert "t:Mesh" in script  # Poly check
        assert "t:Texture2D" in script  # Texture check
        assert "t:Material" in script  # Material check

    def test_aaa_validation_selective(self):
        """Selective flags control which checks are included."""
        script = generate_aaa_validation_script(check_poly=False)
        assert "t:Mesh" not in script

        script2 = generate_aaa_validation_script(check_textures=False)
        assert "t:Texture2D" not in script2

        script3 = generate_aaa_validation_script(check_materials=False)
        assert "t:Material" not in script3

    def test_aaa_validation_balanced_braces(self):
        """Generated C# has balanced curly braces."""
        script = generate_aaa_validation_script()
        assert check_brace_balance(script), "Braces are unbalanced"

    def test_aaa_validation_result_json(self):
        """Script writes result to vb_result.json."""
        script = generate_aaa_validation_script()
        assert "vb_result.json" in script

    def test_aaa_validation_menu_item(self):
        """Script includes MenuItem for Full AAA Audit."""
        script = generate_aaa_validation_script()
        assert "MenuItem" in script
        assert "VeilBreakers/Quality/Full AAA Audit" in script

    def test_aaa_validation_asset_type(self):
        """Asset type is reflected in class name."""
        script = generate_aaa_validation_script(asset_type="hero")
        assert "VeilBreakers_AAAValidation_hero" in script

    def test_aaa_validation_custom_folder(self):
        """Custom target folder is embedded in the script."""
        script = generate_aaa_validation_script(target_folder="Assets/Art")
        assert "Assets/Art" in script

    def test_aaa_validation_budget_values(self):
        """Budget values match the specified asset type (AAA research values)."""
        script = generate_aaa_validation_script(asset_type="hero")
        assert "40000" in script or "60000" in script
