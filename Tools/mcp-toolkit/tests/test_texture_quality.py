"""Unit tests for AAA texture quality pipeline.

Tests smart material presets, trim sheet layouts, macro variation,
detail textures, and bake map code generation -- all pure logic,
testable without Blender.
"""

from __future__ import annotations

import ast
import math

import pytest


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

from blender_addon.handlers.texture_quality import (
    BAKE_MAP_TYPES,
    DEFAULT_TRIM_ELEMENTS,
    DETAIL_TEXTURE_TYPES,
    SMART_MATERIAL_PRESETS,
    TRIM_ELEMENT_PBR,
    VALID_BAKE_MAP_TYPES,
    VALID_DETAIL_TYPES,
    VALID_SMART_MATERIAL_TYPES,
    _REQUIRED_PRESET_KEYS,
    compute_macro_variation_params,
    compute_smart_material_params,
    compute_trim_sheet_layout,
    generate_bake_map_code,
    generate_detail_texture_setup_code,
    generate_macro_variation_code,
    generate_smart_material_code,
    generate_trim_sheet_code,
)


# =========================================================================
# Smart Material Presets -- data integrity
# =========================================================================


class TestSmartMaterialPresets:
    """Validate all 22 smart material presets."""

    ALL_TYPES = sorted(SMART_MATERIAL_PRESETS.keys())

    def test_at_least_22_presets(self):
        """There should be at least 22 smart material presets."""
        assert len(SMART_MATERIAL_PRESETS) >= 22

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_preset_has_required_keys(self, name: str):
        """Every preset must contain all required keys."""
        preset = SMART_MATERIAL_PRESETS[name]
        missing = _REQUIRED_PRESET_KEYS - set(preset.keys())
        assert not missing, f"Preset '{name}' missing keys: {missing}"

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_base_color_valid(self, name: str):
        """base_color must be 3-component tuple in 0-1 range."""
        bc = SMART_MATERIAL_PRESETS[name]["base_color"]
        assert len(bc) == 3, f"base_color has {len(bc)} components, expected 3"
        for i, v in enumerate(bc):
            assert 0.0 <= v <= 1.0, f"base_color[{i}]={v} out of [0,1]"

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_edge_wear_brighter_than_base(self, name: str):
        """Edge wear color must be brighter than base (physical abrasion reveals lighter surface)."""
        preset = SMART_MATERIAL_PRESETS[name]
        bc = preset["base_color"]
        ewc = preset["edge_wear_color"]
        # Luminance: 0.299R + 0.587G + 0.114B
        bc_lum = 0.299 * bc[0] + 0.587 * bc[1] + 0.114 * bc[2]
        ewc_lum = 0.299 * ewc[0] + 0.587 * ewc[1] + 0.114 * ewc[2]
        assert ewc_lum > bc_lum, (
            f"Edge wear ({ewc_lum:.4f}) must be brighter than base ({bc_lum:.4f}) "
            f"for '{name}'"
        )

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_cavity_darker_than_base(self, name: str):
        """Cavity dirt color must be darker than base (grime accumulates in crevices)."""
        preset = SMART_MATERIAL_PRESETS[name]
        bc = preset["base_color"]
        cc = preset["cavity_color"]
        bc_lum = 0.299 * bc[0] + 0.587 * bc[1] + 0.114 * bc[2]
        cc_lum = 0.299 * cc[0] + 0.587 * cc[1] + 0.114 * cc[2]
        assert cc_lum < bc_lum, (
            f"Cavity ({cc_lum:.4f}) must be darker than base ({bc_lum:.4f}) "
            f"for '{name}'"
        )

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_roughness_valid_range(self, name: str):
        """roughness must be in [0, 1]."""
        r = SMART_MATERIAL_PRESETS[name]["roughness"]
        assert 0.0 <= r <= 1.0

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_edge_wear_roughness_valid(self, name: str):
        """edge_wear_roughness must be in [0, 1]."""
        r = SMART_MATERIAL_PRESETS[name]["edge_wear_roughness"]
        assert 0.0 <= r <= 1.0

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_cavity_roughness_valid(self, name: str):
        """cavity_roughness must be in [0, 1]."""
        r = SMART_MATERIAL_PRESETS[name]["cavity_roughness"]
        assert 0.0 <= r <= 1.0

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_macro_variation_subtle(self, name: str):
        """Macro variation strength must be < 0.15 (subtle, not overpowering)."""
        s = SMART_MATERIAL_PRESETS[name]["macro_variation_strength"]
        assert s < 0.15, f"macro_variation_strength={s} exceeds 0.15 threshold"

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_edge_wear_sharpness_range(self, name: str):
        """edge_wear_sharpness must be in [0, 1]."""
        s = SMART_MATERIAL_PRESETS[name]["edge_wear_sharpness"]
        assert 0.0 <= s <= 1.0

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_normal_scales_descending(self, name: str):
        """micro_normal_scale > meso > macro (finer detail has higher frequency)."""
        p = SMART_MATERIAL_PRESETS[name]
        assert p["micro_normal_scale"] > p["meso_normal_scale"], (
            f"micro ({p['micro_normal_scale']}) should be > meso ({p['meso_normal_scale']})"
        )
        assert p["meso_normal_scale"] > p["macro_normal_scale"], (
            f"meso ({p['meso_normal_scale']}) should be > macro ({p['macro_normal_scale']})"
        )

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_edge_wear_color_valid_range(self, name: str):
        """edge_wear_color components must be in [0, 1]."""
        ewc = SMART_MATERIAL_PRESETS[name]["edge_wear_color"]
        assert len(ewc) == 3
        for v in ewc:
            assert 0.0 <= v <= 1.0

    @pytest.mark.parametrize("name", ALL_TYPES)
    def test_cavity_color_valid_range(self, name: str):
        """cavity_color components must be in [0, 1]."""
        cc = SMART_MATERIAL_PRESETS[name]["cavity_color"]
        assert len(cc) == 3
        for v in cc:
            assert 0.0 <= v <= 1.0

    def test_valid_types_frozenset_matches(self):
        """VALID_SMART_MATERIAL_TYPES must match SMART_MATERIAL_PRESETS keys."""
        assert VALID_SMART_MATERIAL_TYPES == frozenset(SMART_MATERIAL_PRESETS.keys())


# =========================================================================
# compute_smart_material_params -- pure logic
# =========================================================================


class TestComputeSmartMaterialParams:
    """Test the pure-logic parameter computation."""

    def test_valid_type_returns_dict(self):
        result = compute_smart_material_params("dungeon_stone", age=0.5)
        assert isinstance(result, dict)
        assert "material_type" in result
        assert result["material_type"] == "dungeon_stone"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown smart material type") as exc_info:
            compute_smart_material_params("nonexistent_material")
        assert "nonexistent_material" in str(exc_info.value)

    def test_invalid_environment_raises(self):
        with pytest.raises(ValueError, match="environment must be") as exc_info:
            compute_smart_material_params("dungeon_stone", environment="space")
        assert "space" in str(exc_info.value) or "environment" in str(exc_info.value)

    def test_age_zero_low_wear(self):
        """Age 0 should produce minimal wear/dirt."""
        result = compute_smart_material_params("dungeon_stone", age=0.0)
        assert result["edge_wear_intensity"] < 0.2
        assert result["cavity_dirt_intensity"] < 0.2

    def test_age_one_high_wear(self):
        """Age 1 should produce maximum wear/dirt."""
        result = compute_smart_material_params("dungeon_stone", age=1.0)
        assert result["edge_wear_intensity"] > 0.8
        assert result["cavity_dirt_intensity"] > 0.8

    def test_outdoor_enables_moss(self):
        result = compute_smart_material_params(
            "dungeon_stone", age=0.8, environment="outdoor"
        )
        assert result["enable_moss"] is True
        assert result["moss_intensity"] > 0.0

    def test_indoor_disables_moss(self):
        result = compute_smart_material_params(
            "dungeon_stone", age=0.8, environment="indoor"
        )
        assert result["enable_moss"] is False
        assert result["moss_intensity"] == 0.0

    def test_age_labels(self):
        assert compute_smart_material_params("dungeon_stone", age=0.1)["age_label"] == "new"
        assert compute_smart_material_params("dungeon_stone", age=0.3)["age_label"] == "weathered"
        assert compute_smart_material_params("dungeon_stone", age=0.6)["age_label"] == "old"
        assert compute_smart_material_params("dungeon_stone", age=0.9)["age_label"] == "ancient"

    def test_age_clamped(self):
        """Out-of-range age should be clamped, not error."""
        r1 = compute_smart_material_params("dungeon_stone", age=-1.0)
        r2 = compute_smart_material_params("dungeon_stone", age=5.0)
        assert r1["edge_wear_intensity"] == pytest.approx(0.1, abs=0.01)
        assert r2["edge_wear_intensity"] == pytest.approx(0.9, abs=0.01)

    @pytest.mark.parametrize("mat_type", sorted(SMART_MATERIAL_PRESETS.keys()))
    def test_all_types_computable(self, mat_type: str):
        """Every preset type must be computable without error."""
        result = compute_smart_material_params(mat_type, age=0.5)
        assert result["material_type"] == mat_type

    def test_metal_no_moss(self):
        """Metal presets should not have moss even outdoors (no moss_color key)."""
        result = compute_smart_material_params(
            "polished_steel", age=0.8, environment="outdoor"
        )
        assert result["enable_moss"] is False


# =========================================================================
# Trim Sheet Layout -- pure logic
# =========================================================================


class TestTrimSheetLayout:
    """Test trim sheet UV region computation."""

    def test_default_elements(self):
        layout = compute_trim_sheet_layout()
        assert layout["element_count"] == len(DEFAULT_TRIM_ELEMENTS)

    def test_custom_elements(self):
        layout = compute_trim_sheet_layout(["a", "b", "c"], 1024)
        assert layout["element_count"] == 3
        assert "a" in layout["elements"]
        assert "b" in layout["elements"]
        assert "c" in layout["elements"]

    def test_empty_elements_raises(self):
        with pytest.raises(ValueError, match="must not be empty") as exc_info:
            compute_trim_sheet_layout([])
        assert "empty" in str(exc_info.value).lower()

    def test_low_resolution_raises(self):
        with pytest.raises(ValueError, match="resolution must be >= 64") as exc_info:
            compute_trim_sheet_layout(["a"], 32)
        assert "32" in str(exc_info.value) or "64" in str(exc_info.value)

    def test_uv_regions_within_01(self):
        """All UV regions must be within [0, 1]."""
        layout = compute_trim_sheet_layout()
        for name, (u_min, v_min, u_max, v_max) in layout["elements"].items():
            assert 0.0 <= u_min <= 1.0, f"{name}: u_min={u_min}"
            assert 0.0 <= v_min <= 1.0, f"{name}: v_min={v_min}"
            assert 0.0 <= u_max <= 1.0, f"{name}: u_max={u_max}"
            assert 0.0 <= v_max <= 1.0, f"{name}: v_max={v_max}"

    def test_uv_regions_no_overlap(self):
        """UV regions must not overlap vertically."""
        layout = compute_trim_sheet_layout()
        sorted_regions = sorted(layout["elements"].values(), key=lambda r: r[1])
        for i in range(len(sorted_regions) - 1):
            assert sorted_regions[i][3] <= sorted_regions[i + 1][1] + 1e-6, (
                f"Region {i} v_max={sorted_regions[i][3]} overlaps "
                f"region {i+1} v_min={sorted_regions[i+1][1]}"
            )

    def test_full_u_range(self):
        """Each strip spans full U range (0 to 1)."""
        layout = compute_trim_sheet_layout()
        for name, (u_min, _, u_max, _) in layout["elements"].items():
            assert u_min == 0.0
            assert u_max == 1.0

    def test_strip_height_positive(self):
        layout = compute_trim_sheet_layout()
        assert layout["strip_height_px"] > 0

    def test_high_resolution_more_precision(self):
        """Higher resolution should give more pixels per strip."""
        low = compute_trim_sheet_layout(["a", "b"], 256)
        high = compute_trim_sheet_layout(["a", "b"], 4096)
        assert high["strip_height_px"] > low["strip_height_px"]


# =========================================================================
# Macro Variation -- pure logic
# =========================================================================


class TestMacroVariation:
    """Test macro variation parameter computation."""

    def test_small_surface(self):
        result = compute_macro_variation_params(0.5, "stone")
        assert result["scale"] > 2.0  # small surfaces need higher frequency

    def test_large_surface(self):
        result = compute_macro_variation_params(500.0, "stone")
        assert result["scale"] < 1.0  # large surfaces need lower frequency

    def test_variation_subtle(self):
        """All variation values must stay subtle (AAA requirement)."""
        for area in [0.1, 1.0, 10.0, 100.0, 1000.0]:
            for mat in ["stone", "wood", "metal", "organic"]:
                result = compute_macro_variation_params(area, mat)
                assert result["hue_shift"] <= 0.05
                assert result["value_shift"] <= 0.12
                assert result["roughness_shift"] <= 0.10

    def test_metal_less_variation(self):
        """Metal should have less color variation than stone."""
        stone = compute_macro_variation_params(10.0, "stone")
        metal = compute_macro_variation_params(10.0, "metal")
        assert metal["hue_shift"] < stone["hue_shift"]
        assert metal["value_shift"] < stone["value_shift"]

    def test_unknown_material_falls_back(self):
        """Unknown material type uses stone defaults."""
        result = compute_macro_variation_params(10.0, "unknown_type")
        stone = compute_macro_variation_params(10.0, "stone")
        assert result["hue_shift"] == stone["hue_shift"]

    def test_scale_clamped(self):
        """Extreme surface areas should produce clamped scales."""
        tiny = compute_macro_variation_params(0.001)
        huge = compute_macro_variation_params(100000.0)
        assert tiny["scale"] <= 20.0
        assert huge["scale"] >= 0.2


# =========================================================================
# Code Generation -- Smart Material
# =========================================================================


class TestGenerateSmartMaterialCode:
    """Test smart material code generation."""

    def test_valid_python(self):
        """Generated code must parse as valid Python."""
        code = generate_smart_material_code("dungeon_stone", "TestObj")
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown smart material type") as exc_info:
            generate_smart_material_code("totally_fake_material")
        assert "totally_fake_material" in str(exc_info.value)

    def test_aged_stone_alias(self):
        """'aged_stone' should alias to 'dungeon_stone'."""
        code = generate_smart_material_code("aged_stone", "Obj")
        assert "dungeon_stone" in code

    def test_contains_edge_wear(self):
        code = generate_smart_material_code("dungeon_stone", "Obj")
        assert "Edge Wear" in code
        assert "Pointiness" in code

    def test_contains_cavity_dirt(self):
        code = generate_smart_material_code("dungeon_stone", "Obj")
        assert "Cavity Dirt" in code
        assert "Invert Pointiness" in code

    def test_contains_macro_variation(self):
        code = generate_smart_material_code("dungeon_stone", "Obj")
        assert "Macro Variation" in code

    def test_contains_normal_chain(self):
        code = generate_smart_material_code("dungeon_stone", "Obj")
        assert "Micro Bump" in code
        assert "Meso Bump" in code
        assert "Macro Bump" in code

    def test_moss_layer_for_stone_with_moss(self):
        """Stone with moss preset should include moss layer."""
        code = generate_smart_material_code("dungeon_stone", "Obj", moss_intensity=0.5, age=0.8)
        assert "Moss" in code

    def test_no_moss_for_metal(self):
        """Metal presets should not generate moss code."""
        code = generate_smart_material_code("polished_steel", "Obj", moss_intensity=0.5, age=0.8)
        # polished_steel has no moss_color key, so moss should be skipped
        assert "Moss Color" not in code

    @pytest.mark.parametrize("mat_type", sorted(SMART_MATERIAL_PRESETS.keys()))
    def test_all_types_generate_valid_python(self, mat_type: str):
        """Every preset must generate valid Python code."""
        code = generate_smart_material_code(mat_type, "TestObj", age=0.5)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_wear_intensity_modulates_age(self):
        """Low age should produce lower effective wear."""
        code_new = generate_smart_material_code("dungeon_stone", "Obj", wear_intensity=0.5, age=0.0)
        code_old = generate_smart_material_code("dungeon_stone", "Obj", wear_intensity=0.5, age=1.0)
        # The wear intensity values embedded in the code should differ
        assert code_new != code_old

    def test_object_name_in_code(self):
        code = generate_smart_material_code("dungeon_stone", "MySpecialObject")
        assert "MySpecialObject" in code

    def test_uses_only_allowed_imports(self):
        """Generated code must only import bpy, mathutils, math, random, json."""
        code = generate_smart_material_code("dungeon_stone", "Obj")
        allowed = {"bpy", "mathutils", "math", "random", "json"}
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in allowed, f"Disallowed import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed, f"Disallowed import from: {node.module}"


# =========================================================================
# Code Generation -- Trim Sheet
# =========================================================================


class TestGenerateTrimSheetCode:
    """Test trim sheet code generation."""

    def test_valid_python(self):
        code = generate_trim_sheet_code("test_trim", 1024)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_contains_sheet_name(self):
        code = generate_trim_sheet_code("my_custom_trim", 2048)
        assert "my_custom_trim" in code

    def test_contains_resolution(self):
        code = generate_trim_sheet_code("trim", 4096)
        assert "4096" in code


# =========================================================================
# Code Generation -- Macro Variation
# =========================================================================


class TestGenerateMacroVariationCode:
    """Test macro variation code generation."""

    def test_valid_python(self):
        code = generate_macro_variation_code("Obj", 3.0, 0.03, 0.08)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_contains_object_name(self):
        code = generate_macro_variation_code("CastleWall")
        assert "CastleWall" in code

    def test_overlay_blend_mode(self):
        code = generate_macro_variation_code("Obj")
        assert "OVERLAY" in code

    def test_values_clamped(self):
        """Extreme inputs should be clamped in the generated code."""
        code = generate_macro_variation_code("Obj", variation_scale=999, hue_shift=1.0, value_shift=5.0)
        # Should contain clamped values, not the originals
        assert "999" not in code
        # value_shift gets clamped to 0.12
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0


# =========================================================================
# Code Generation -- Detail Texture
# =========================================================================


class TestGenerateDetailTextureCode:
    """Test detail texture code generation."""

    def test_valid_python(self):
        code = generate_detail_texture_setup_code("Obj", "stone_pores")
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown detail type") as exc_info:
            generate_detail_texture_setup_code("Obj", "nonexistent_detail")
        assert "nonexistent_detail" in str(exc_info.value)

    @pytest.mark.parametrize("detail_type", sorted(DETAIL_TEXTURE_TYPES.keys()))
    def test_all_types_generate_valid_python(self, detail_type: str):
        code = generate_detail_texture_setup_code("Obj", detail_type)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_contains_camera_distance(self):
        """Detail textures must use camera distance for LOD fading."""
        code = generate_detail_texture_setup_code("Obj", "stone_pores")
        assert "Camera Data" in code or "CameraData" in code

    def test_detail_scale_increases_for_fine_types(self):
        """Skin pores should have higher default scale than stone pores."""
        skin = DETAIL_TEXTURE_TYPES["skin_pores"]
        stone = DETAIL_TEXTURE_TYPES["stone_pores"]
        assert skin["default_scale"] > stone["default_scale"]

    def test_uses_only_allowed_imports(self):
        code = generate_detail_texture_setup_code("Obj", "stone_pores")
        allowed = {"bpy", "mathutils", "math", "random", "json"}
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in allowed
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed


# =========================================================================
# Code Generation -- Bake Maps
# =========================================================================


class TestGenerateBakeMapCode:
    """Test bake map code generation."""

    def test_valid_python_position(self):
        code = generate_bake_map_code("Obj", "position", 1024)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown bake map type") as exc_info:
            generate_bake_map_code("Obj", "invalid_map")
        assert "invalid_map" in str(exc_info.value)

    @pytest.mark.parametrize("bake_type", sorted(BAKE_MAP_TYPES.keys()))
    def test_all_types_generate_valid_python(self, bake_type: str):
        code = generate_bake_map_code("Obj", bake_type, 512)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) > 0

    def test_uses_only_allowed_imports(self):
        code = generate_bake_map_code("Obj", "position")
        allowed = {"bpy", "mathutils", "math", "random", "json"}
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in allowed


# =========================================================================
# Detail Texture Types -- data integrity
# =========================================================================


class TestDetailTextureTypes:
    """Validate detail texture type definitions."""

    @pytest.mark.parametrize("name", sorted(DETAIL_TEXTURE_TYPES.keys()))
    def test_has_required_fields(self, name: str):
        dt = DETAIL_TEXTURE_TYPES[name]
        assert "noise_type" in dt
        assert "default_scale" in dt
        assert "default_strength" in dt
        assert "roughness_bias" in dt
        assert "description" in dt

    @pytest.mark.parametrize("name", sorted(DETAIL_TEXTURE_TYPES.keys()))
    def test_default_scale_positive(self, name: str):
        assert DETAIL_TEXTURE_TYPES[name]["default_scale"] > 0.0

    @pytest.mark.parametrize("name", sorted(DETAIL_TEXTURE_TYPES.keys()))
    def test_default_strength_range(self, name: str):
        s = DETAIL_TEXTURE_TYPES[name]["default_strength"]
        assert 0.0 < s <= 1.0

    @pytest.mark.parametrize("name", sorted(DETAIL_TEXTURE_TYPES.keys()))
    def test_noise_type_valid(self, name: str):
        valid_noise = {"voronoi", "wave", "noise", "checker"}
        assert DETAIL_TEXTURE_TYPES[name]["noise_type"] in valid_noise

    def test_valid_detail_types_matches(self):
        assert VALID_DETAIL_TYPES == frozenset(DETAIL_TEXTURE_TYPES.keys())


# =========================================================================
# Bake Map Types -- data integrity
# =========================================================================


class TestBakeMapTypes:
    """Validate bake map type definitions."""

    @pytest.mark.parametrize("name", sorted(BAKE_MAP_TYPES.keys()))
    def test_has_required_fields(self, name: str):
        bm = BAKE_MAP_TYPES[name]
        assert "description" in bm
        assert "colorspace" in bm
        assert "default_bit_depth" in bm

    @pytest.mark.parametrize("name", sorted(BAKE_MAP_TYPES.keys()))
    def test_colorspace_valid(self, name: str):
        valid_cs = {"sRGB", "Non-Color"}
        assert BAKE_MAP_TYPES[name]["colorspace"] in valid_cs

    def test_five_bake_types(self):
        assert len(BAKE_MAP_TYPES) == 5
        expected = {"position", "bent_normal", "world_normal", "flow", "gradient"}
        assert set(BAKE_MAP_TYPES.keys()) == expected

    def test_valid_bake_map_types_matches(self):
        assert VALID_BAKE_MAP_TYPES == frozenset(BAKE_MAP_TYPES.keys())


# =========================================================================
# Trim Element PBR -- data integrity
# =========================================================================


class TestTrimElementPBR:
    """Validate trim element PBR hints."""

    @pytest.mark.parametrize("name", sorted(TRIM_ELEMENT_PBR.keys()))
    def test_has_base_color(self, name: str):
        bc = TRIM_ELEMENT_PBR[name]["base_color"]
        assert len(bc) == 3
        for v in bc:
            assert 0.0 <= v <= 1.0

    @pytest.mark.parametrize("name", sorted(TRIM_ELEMENT_PBR.keys()))
    def test_has_roughness(self, name: str):
        r = TRIM_ELEMENT_PBR[name]["roughness"]
        assert 0.0 <= r <= 1.0

    @pytest.mark.parametrize("name", sorted(TRIM_ELEMENT_PBR.keys()))
    def test_has_metallic(self, name: str):
        m = TRIM_ELEMENT_PBR[name]["metallic"]
        assert 0.0 <= m <= 1.0

    def test_all_default_elements_have_pbr(self):
        """Every default trim element should have PBR data."""
        for elem in DEFAULT_TRIM_ELEMENTS:
            assert elem in TRIM_ELEMENT_PBR, f"Missing PBR data for '{elem}'"
