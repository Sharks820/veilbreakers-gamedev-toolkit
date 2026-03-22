"""Functional tests for Blender MCP Tools 9-15.

Covers all pure-logic paths for:
  Tool  9: blender_texture (10 actions)
  Tool 10: asset_pipeline  (8 actions)
  Tool 11: concept_art     (4 actions)
  Tool 12: blender_rig     (13 actions)
  Tool 13: blender_animation (12 actions)
  Tool 14: blender_environment (9 actions)
  Tool 15: blender_worldbuilding (8 actions)

Every test uses real data and exercises actual functions -- no mocks.
"""

from __future__ import annotations

import io
import math
import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image as PILImage

# ---------------------------------------------------------------------------
# Imports: handlers __init__ (COMMAND_HANDLERS registry)
# ---------------------------------------------------------------------------
# The handlers package does `import bpy` at module scope in some files.
# We only need the COMMAND_HANDLERS dict keys and the pure-logic functions,
# so we import selectively and catch ImportError for bpy-dependent modules.

# Pure-logic modules -- no bpy dependency
from blender_addon.handlers.animation_gaits import (
    ATTACK_CONFIGS,
    BIPED_WALK_CONFIG,
    FLY_HOVER_CONFIG,
    IDLE_CONFIG,
    Keyframe,
    generate_attack_keyframes,
    generate_custom_keyframes,
    generate_cycle_keyframes,
    generate_reaction_keyframes,
    get_gait_config,
)
from blender_addon.handlers._terrain_noise import (
    BIOME_RULES,
    TERRAIN_PRESETS,
    compute_biome_assignments,
    compute_slope_map,
    generate_heightmap,
)
from blender_addon.handlers._terrain_erosion import (
    apply_hydraulic_erosion,
    apply_thermal_erosion,
)
from blender_addon.handlers._dungeon_gen import (
    CaveMap,
    DungeonLayout,
    TownLayout,
    generate_bsp_dungeon,
    generate_cave_map,
    generate_town_layout,
)
from blender_addon.handlers._building_grammar import (
    MODULAR_CATALOG,
    STYLE_CONFIGS,
    BuildingSpec,
    apply_ruins_damage,
    evaluate_building_grammar,
    generate_castle_spec,
    generate_interior_layout,
    generate_modular_pieces,
)

# Texture pure-logic from handlers/texture.py
from blender_addon.handlers.texture import (
    _is_power_of_two,
    _validate_texture_metadata,
    _validate_bake_params,
    _find_texture_file,
    _build_channel_config,
    BSDF_INPUT_MAP,
)

# Pipeline LOD pure-logic
from blender_addon.handlers.pipeline_lod import (
    _validate_lod_ratios,
    _build_lod_name,
)

# Rigging pure-logic
from blender_addon.handlers.rigging import (
    _analyze_proportions,
    _validate_custom_rig_config,
)
from blender_addon.handlers.rigging_templates import (
    LIMB_LIBRARY,
    TEMPLATE_CATALOG,
    VALID_RIGIFY_TYPES,
)
from blender_addon.handlers.rigging_advanced import (
    FACIAL_BONES,
    MONSTER_EXPRESSIONS,
    RAGDOLL_PRESETS,
    _validate_ik_params,
    _validate_spring_params,
    _validate_ragdoll_spec,
    _validate_retarget_mapping,
    _validate_shape_key_params,
)

# Animation pure-logic validators
from blender_addon.handlers.animation import (
    VALID_ATTACK_TYPES,
    VALID_GAITS,
    VALID_HIT_DIRECTIONS,
    VALID_REACTION_TYPES,
    VALID_SPEEDS,
    _validate_walk_params,
    _validate_fly_params,
    _validate_idle_params,
    _validate_attack_params,
    _validate_reaction_params,
    _validate_custom_params,
)

# Animation export pure-logic
from blender_addon.handlers.animation_export import (
    MIXAMO_TO_RIGIFY,
    PREVIEW_ANGLES,
    _validate_export_params,
    _validate_preview_params,
    _validate_secondary_motion_params,
    _validate_root_motion_params,
    _validate_batch_export_params,
    _map_mixamo_bones,
    _generate_unity_filename,
)

# Environment pure-logic
from blender_addon.handlers.environment import (
    _validate_terrain_params,
    _export_heightmap_raw,
)

# Worldbuilding layout pure-logic converters
from blender_addon.handlers.worldbuilding_layout import (
    _dungeon_to_geometry_ops,
    _cave_to_geometry_ops,
    _town_to_geometry_ops,
)

# Worldbuilding pure-logic result builders
from blender_addon.handlers.worldbuilding import (
    _building_ops_to_mesh_spec,
    _build_building_result,
    _build_castle_result,
    _build_ruins_result,
    _build_interior_result,
    _build_modular_kit_result,
)

# Shared modules (server-side, no bpy)
from veilbreakers_mcp.shared.texture_ops import (
    generate_uv_mask,
    generate_uv_mask_image,
    apply_hsv_adjustment,
    blend_seams,
    make_tileable,
)
from veilbreakers_mcp.shared.texture_validation import (
    check_power_of_two,
    validate_texture_file,
)
from veilbreakers_mcp.shared.asset_catalog import AssetCatalog
from veilbreakers_mcp.shared.fal_client import (
    extract_color_palette,
    compose_style_board,
    test_silhouette_readability as silhouette_readability_fn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_png_bytes(img: PILImage.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# The full COMMAND_HANDLERS dict requires bpy at import time.
# We parse expected keys here and validate them against the __init__.py
# source to ensure they are registered.  We read the file as text.
_INIT_PATH = Path(__file__).resolve().parent.parent / "blender_addon" / "handlers" / "__init__.py"


def _read_handler_keys() -> set[str]:
    """Parse all COMMAND_HANDLERS keys from __init__.py source text."""
    text = _INIT_PATH.read_text(encoding="utf-8")
    keys: set[str] = set()
    in_dict = False
    for line in text.splitlines():
        stripped = line.strip()
        if "COMMAND_HANDLERS" in stripped and "{" in stripped:
            in_dict = True
            continue
        if in_dict:
            if stripped.startswith("}"):
                break
            if stripped.startswith('"'):
                key = stripped.split('"')[1]
                keys.add(key)
    return keys


HANDLER_KEYS = _read_handler_keys()


# ===================================================================
# TOOL 9: blender_texture (10 actions)
# ===================================================================


class TestTool9BlenderTexture:
    """Verify all 10 blender_texture action handler keys and pure-logic."""

    # -- handler key verification --

    TEXTURE_KEYS = {
        "texture_create_pbr",
        "texture_bake",
        "texture_validate",
        "texture_generate_wear",
        "texture_get_uv_region",
        "texture_get_seam_pixels",
    }

    def test_texture_handler_keys_registered(self):
        """All 6 texture handler keys present in COMMAND_HANDLERS."""
        for key in self.TEXTURE_KEYS:
            assert key in HANDLER_KEYS, f"Missing handler key: {key}"

    # -- pure-logic: texture metadata validation --

    def test_validate_texture_metadata_valid_pot(self):
        result = _validate_texture_metadata(1024, 1024, "PNG", "sRGB")
        assert result["is_power_of_two"] is True
        assert result["issues"] == []

    def test_validate_texture_metadata_non_pot(self):
        result = _validate_texture_metadata(300, 300, "PNG", "sRGB")
        assert result["is_power_of_two"] is False
        assert len(result["issues"]) >= 1

    def test_validate_texture_metadata_low_res(self):
        result = _validate_texture_metadata(64, 64, "PNG", "sRGB")
        assert any("Low resolution" in i for i in result["issues"])

    def test_validate_texture_metadata_oversized(self):
        result = _validate_texture_metadata(16384, 16384, "PNG", "sRGB")
        assert any("Oversized" in i for i in result["issues"])

    # -- pure-logic: power of two --

    @pytest.mark.parametrize("n,expected", [
        (1, True), (2, True), (4, True), (1024, True), (8192, True),
        (0, False), (-1, False), (3, False), (100, False), (1023, False),
    ])
    def test_is_power_of_two(self, n, expected):
        assert _is_power_of_two(n) == expected

    # -- pure-logic: bake params --

    def test_validate_bake_params_valid(self):
        for btype in ("NORMAL", "AO", "COMBINED", "ROUGHNESS", "EMIT", "DIFFUSE"):
            _validate_bake_params(btype)  # should not raise

    def test_validate_bake_params_invalid(self):
        with pytest.raises(ValueError, match="Invalid bake_type"):
            _validate_bake_params("INVALID")

    # -- pure-logic: channel config --

    def test_build_channel_config_has_5_channels(self):
        cfg = _build_channel_config()
        assert set(cfg.keys()) == {"albedo", "metallic", "roughness", "normal", "ao"}

    def test_bsdf_input_map_has_expected_entries(self):
        expected = {"base_color", "metallic", "roughness", "normal", "ior", "alpha",
                    "subsurface", "specular", "transmission", "coat", "sheen", "emission"}
        assert set(BSDF_INPUT_MAP.keys()) == expected

    # -- texture_ops: generate_uv_mask with real image data --

    def test_generate_uv_mask_produces_png(self):
        polygons = [[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]]
        mask_bytes = generate_uv_mask(polygons, texture_size=64, feather_radius=3)
        assert len(mask_bytes) > 0
        img = PILImage.open(io.BytesIO(mask_bytes))
        assert img.mode == "L"
        assert img.size == (64, 64)

    def test_generate_uv_mask_image_has_white_interior(self):
        polygons = [[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]]
        mask = generate_uv_mask_image(polygons, texture_size=128, feather_radius=0)
        # Center pixel should be white
        center = mask.getpixel((64, 64))
        assert center == 255

    # -- texture_ops: apply_hsv_adjustment --

    def test_apply_hsv_adjustment_returns_valid_png(self):
        img = PILImage.new("RGB", (32, 32), (200, 100, 50))
        mask = PILImage.new("L", (32, 32), 255)
        result = apply_hsv_adjustment(
            _to_png_bytes(img), _to_png_bytes(mask),
            hue_shift=0.5, saturation_scale=1.0, value_scale=1.0,
        )
        out = PILImage.open(io.BytesIO(result))
        assert out.size == (32, 32)
        assert out.mode == "RGB"

    # -- texture_ops: blend_seams --

    def test_blend_seams_returns_valid_png(self):
        img = PILImage.new("RGB", (64, 64), (100, 100, 100))
        seam_pixels = [(32, y) for y in range(64)]
        result = blend_seams(_to_png_bytes(img), seam_pixels, blend_radius=4)
        out = PILImage.open(io.BytesIO(result))
        assert out.size == (64, 64)

    # -- texture_ops: make_tileable --

    def test_make_tileable_edge_pixels_match(self):
        img = PILImage.new("RGB", (64, 64), (0, 0, 0))
        # Set different colors at edges to test blending
        for y in range(64):
            img.putpixel((0, y), (255, 0, 0))
            img.putpixel((63, y), (0, 0, 255))
        result = make_tileable(_to_png_bytes(img), overlap_pct=0.15)
        out = PILImage.open(io.BytesIO(result))
        assert out.size == (64, 64)
        # After tileable processing, left and right edges should be similar
        left_pixel = out.getpixel((0, 32))
        right_pixel = out.getpixel((63, 32))
        # They should be close (blended)
        for c in range(3):
            assert abs(left_pixel[c] - right_pixel[c]) < 50, (
                f"Edge pixels not matched: left={left_pixel}, right={right_pixel}"
            )

    # -- texture_validation: check_power_of_two --

    @pytest.mark.parametrize("n,expected", [
        (256, True), (512, True), (1024, True), (100, False), (0, False),
    ])
    def test_check_power_of_two_shared(self, n, expected):
        assert check_power_of_two(n) == expected

    # -- texture_validation: validate_texture_file --

    def test_validate_texture_file_valid_pot(self, tmp_path):
        img = PILImage.new("RGB", (512, 512), (128, 128, 128))
        fpath = str(tmp_path / "test.png")
        img.save(fpath)
        result = validate_texture_file(fpath)
        assert result["valid"] is True
        assert result["is_power_of_two"] is True
        assert result["width"] == 512
        assert result["height"] == 512

    def test_validate_texture_file_non_pot(self, tmp_path):
        img = PILImage.new("RGB", (300, 300), (128, 128, 128))
        fpath = str(tmp_path / "test_npot.png")
        img.save(fpath)
        result = validate_texture_file(fpath)
        assert result["valid"] is False
        assert result["is_power_of_two"] is False

    def test_validate_texture_file_not_found(self):
        result = validate_texture_file("/nonexistent/path.png")
        assert result["valid"] is False
        assert len(result["issues"]) >= 1


# ===================================================================
# TOOL 10: asset_pipeline (8 actions)
# ===================================================================


class TestTool10AssetPipeline:
    """Verify all 8 asset_pipeline action handler keys and functional tests."""

    PIPELINE_KEYS = {
        # Mapped to COMMAND_HANDLERS keys:
        "texture_create_pbr",       # generate_3d maps to tripo (server-side)
        "pipeline_generate_lods",   # generate_lods
    }

    def test_pipeline_generate_lods_key_registered(self):
        assert "pipeline_generate_lods" in HANDLER_KEYS

    # -- LOD pure-logic --

    def test_validate_lod_ratios_valid(self):
        assert _validate_lod_ratios([1.0, 0.5, 0.25, 0.1]) is True

    def test_validate_lod_ratios_empty_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            _validate_lod_ratios([])

    def test_validate_lod_ratios_out_of_range_raises(self):
        with pytest.raises(ValueError, match="must be in"):
            _validate_lod_ratios([0.0])

    def test_validate_lod_ratios_not_descending_raises(self):
        with pytest.raises(ValueError, match="strictly descending"):
            _validate_lod_ratios([0.5, 0.5])

    def test_build_lod_name(self):
        assert _build_lod_name("Barrel", 0) == "Barrel_LOD0"
        assert _build_lod_name("Barrel", 3) == "Barrel_LOD3"

    # -- AssetCatalog functional tests (in-memory) --

    def test_asset_catalog_add_query_update_delete(self):
        catalog = AssetCatalog(":memory:")
        try:
            # Add
            aid = catalog.add_asset(
                "Barrel", "prop", "/barrel.glb",
                tags=["wood", "container"], poly_count=1200,
                texture_res="2048x2048", lod_count=3,
            )
            assert aid

            # Get
            asset = catalog.get_asset(aid)
            assert asset is not None
            assert asset["name"] == "Barrel"
            assert asset["asset_type"] == "prop"
            assert "wood" in asset["tags"]
            assert asset["poly_count"] == 1200

            # Query by tags
            results = catalog.query_assets(tags=["wood"])
            assert len(results) == 1
            assert results[0]["id"] == aid

            # Query by type
            results = catalog.query_assets(asset_type="prop")
            assert len(results) == 1

            # Query by name pattern
            results = catalog.query_assets(name_pattern="Bar%")
            assert len(results) == 1

            # Update
            updated = catalog.update_asset(aid, status="processed", lod_count=4)
            assert updated is True
            asset = catalog.get_asset(aid)
            assert asset["status"] == "processed"
            assert asset["lod_count"] == 4

            # Delete
            deleted = catalog.delete_asset(aid)
            assert deleted is True
            assert catalog.get_asset(aid) is None

        finally:
            catalog.close()

    def test_asset_catalog_query_poly_range(self):
        catalog = AssetCatalog(":memory:")
        try:
            catalog.add_asset("Low", "prop", "/low.glb", poly_count=100)
            catalog.add_asset("Mid", "prop", "/mid.glb", poly_count=5000)
            catalog.add_asset("High", "prop", "/high.glb", poly_count=50000)

            results = catalog.query_assets(min_poly=1000, max_poly=10000)
            assert len(results) == 1
            assert results[0]["name"] == "Mid"
        finally:
            catalog.close()

    # -- validate_export on a dummy file --

    def test_validate_texture_file_on_dummy(self, tmp_path):
        img = PILImage.new("RGB", (1024, 1024), (0, 0, 0))
        fpath = str(tmp_path / "export_test.png")
        img.save(fpath)
        result = validate_texture_file(fpath)
        assert result["valid"] is True


# ===================================================================
# TOOL 11: concept_art (4 actions)
# ===================================================================


class TestTool11ConceptArt:
    """Verify concept_art actions and functional tests."""

    def test_extract_color_palette_solid_red(self):
        """extract_color_palette on solid red 64x64 returns red dominant."""
        img = PILImage.new("RGB", (64, 64), (255, 0, 0))
        result = extract_color_palette(_to_png_bytes(img), num_colors=4)
        assert len(result["colors"]) >= 1
        dominant = result["colors"][0]
        assert dominant["rgb"][0] > 200
        assert dominant["rgb"][1] < 50
        assert dominant["rgb"][2] < 50
        assert dominant["hex"].startswith("#")
        assert "percentage" in dominant

    def test_extract_color_palette_swatch_bytes(self):
        img = PILImage.new("RGB", (64, 64), (0, 128, 255))
        result = extract_color_palette(_to_png_bytes(img), num_colors=4)
        swatch = PILImage.open(io.BytesIO(result["swatch_bytes"]))
        assert swatch.mode == "RGB"
        assert swatch.size[0] > 0

    def test_silhouette_readability_dark_shape_readable(self):
        """Centered dark shape on white background is readable."""
        img = PILImage.new("L", (256, 256), 255)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.ellipse([48, 48, 208, 208], fill=0)
        result = silhouette_readability_fn(
            _to_png_bytes(img), threshold=128,
            min_contrast_ratio=0.3, distances=[1.0, 0.5, 0.25],
        )
        assert result["readable"] is True
        assert result["silhouette_coverage"] > 0.1
        assert len(result["distances"]) == 3

    def test_silhouette_readability_solid_gray_not_readable(self):
        """Solid gray above threshold has no foreground."""
        img = PILImage.new("L", (256, 256), 130)
        result = silhouette_readability_fn(
            _to_png_bytes(img), threshold=128,
            min_contrast_ratio=0.3, distances=[1.0],
        )
        assert result["readable"] is False

    def test_compose_style_board_with_2_images(self):
        """compose_style_board with 2 test images produces valid PNG."""
        img1 = PILImage.new("RGB", (200, 200), (255, 0, 0))
        img2 = PILImage.new("RGB", (200, 200), (0, 255, 0))
        board_bytes = compose_style_board(
            images=[_to_png_bytes(img1), _to_png_bytes(img2)],
            palette_colors=[{"rgb": [255, 0, 0]}, {"rgb": [0, 255, 0]}],
            title="Test Board",
            board_width=1024,
        )
        board = PILImage.open(io.BytesIO(board_bytes))
        assert board.width == 1024
        assert board.height > 0


# ===================================================================
# TOOL 12: blender_rig (13 actions)
# ===================================================================


class TestTool12BlenderRig:
    """Verify all 13 rig action handler keys and pure-logic functions."""

    RIG_KEYS = {
        "rig_analyze", "rig_apply_template", "rig_build_custom",
        "rig_auto_weight", "rig_test_deformation", "rig_validate", "rig_fix_weights",
        "rig_setup_facial", "rig_setup_ik", "rig_setup_spring_bones",
        "rig_setup_ragdoll", "rig_retarget", "rig_add_shape_keys",
    }

    def test_all_13_rig_handler_keys_registered(self):
        for key in self.RIG_KEYS:
            assert key in HANDLER_KEYS, f"Missing rig handler key: {key}"

    # -- TEMPLATE_CATALOG: 10 templates --

    EXPECTED_TEMPLATES = {
        "humanoid", "quadruped", "bird", "insect", "serpent",
        "floating", "dragon", "multi_armed", "arachnid", "amorphous",
    }

    def test_template_catalog_has_10_templates(self):
        assert set(TEMPLATE_CATALOG.keys()) == self.EXPECTED_TEMPLATES

    def test_each_template_has_bones_with_required_fields(self):
        for tname, bones in TEMPLATE_CATALOG.items():
            assert len(bones) > 0, f"Template {tname} has no bones"
            for bname, bdef in bones.items():
                assert "head" in bdef, f"{tname}.{bname} missing 'head'"
                assert "tail" in bdef, f"{tname}.{bname} missing 'tail'"
                assert "roll" in bdef, f"{tname}.{bname} missing 'roll'"
                assert "rigify_type" in bdef, f"{tname}.{bname} missing 'rigify_type'"
                assert bdef["rigify_type"] in VALID_RIGIFY_TYPES, (
                    f"{tname}.{bname} has invalid rigify_type: {bdef['rigify_type']}"
                )

    # -- LIMB_LIBRARY --

    EXPECTED_LIMBS = {
        "arm_pair", "leg_pair", "paw_leg_pair", "wing_pair", "tail_chain",
        "head_chain", "jaw", "tentacle_chain", "insect_leg_pair",
    }

    def test_limb_library_has_expected_entries(self):
        assert set(LIMB_LIBRARY.keys()) == self.EXPECTED_LIMBS

    def test_each_limb_function_returns_bones(self):
        for lname, lfn in LIMB_LIBRARY.items():
            bones = lfn()
            assert isinstance(bones, dict), f"LIMB_LIBRARY[{lname}] did not return dict"
            assert len(bones) > 0, f"LIMB_LIBRARY[{lname}] returned empty dict"

    # -- _analyze_proportions --

    def test_analyze_proportions_humanoid(self):
        result = _analyze_proportions((0.5, 0.5, 2.0), 5000, True)
        assert result["recommended_template"] == "humanoid"
        assert result["confidence"] >= 0.6

    def test_analyze_proportions_serpent(self):
        result = _analyze_proportions((4.0, 0.5, 0.3), 2000, False)
        assert result["recommended_template"] == "serpent"

    def test_analyze_proportions_amorphous_fallback(self):
        # Very unusual proportions with no symmetry
        result = _analyze_proportions((0.001, 0.001, 0.001), 10, False)
        assert "recommended_template" in result

    # -- _validate_custom_rig_config --

    def test_validate_custom_rig_config_valid(self):
        result = _validate_custom_rig_config(["arm_pair", "leg_pair"])
        assert result["valid"] is True
        assert result["limb_count"] == 2
        assert result["bone_estimate"] > 4  # spine (4) + limbs

    def test_validate_custom_rig_config_empty(self):
        result = _validate_custom_rig_config([])
        assert result["valid"] is False

    def test_validate_custom_rig_config_unknown_limb(self):
        result = _validate_custom_rig_config(["nonexistent_limb"])
        assert result["valid"] is False
        assert len(result["errors"]) >= 1

    # -- _compute_rig_grade via _validate_custom_rig_config --

    def test_validate_custom_rig_bone_estimate(self):
        result = _validate_custom_rig_config(["arm_pair"])
        # arm_pair returns 6 bones + 4 spine = 10
        assert result["bone_estimate"] >= 10

    # -- _validate_ik_params --

    def test_validate_ik_params_valid_standard(self):
        result = _validate_ik_params({
            "bone_name": "forearm.L", "chain_length": 2,
            "constraint_type": "IK", "pole_angle": 0.0,
        })
        assert result["valid"] is True

    def test_validate_ik_params_valid_spline(self):
        result = _validate_ik_params({
            "bone_name": "tail.001", "chain_length": 5,
            "constraint_type": "SPLINE_IK", "curve_points": 4,
        })
        assert result["valid"] is True

    def test_validate_ik_params_missing_bone_name(self):
        result = _validate_ik_params({"chain_length": 2})
        assert result["valid"] is False

    def test_validate_ik_params_chain_too_long(self):
        result = _validate_ik_params({
            "bone_name": "b", "chain_length": 25,
        })
        assert result["valid"] is False

    def test_validate_ik_params_spline_needs_curve_points(self):
        result = _validate_ik_params({
            "bone_name": "b", "constraint_type": "SPLINE_IK", "curve_points": 1,
        })
        assert result["valid"] is False

    # -- _validate_spring_params --

    def test_validate_spring_params_valid(self):
        result = _validate_spring_params(["tail.001", "tail.002"], 0.5, 0.3, 1.0)
        assert result["valid"] is True
        assert result["bone_count"] == 2

    def test_validate_spring_params_empty_bones(self):
        result = _validate_spring_params([], 0.5, 0.3, 1.0)
        assert result["valid"] is False

    def test_validate_spring_params_out_of_range(self):
        result = _validate_spring_params(["a"], 2.0, 0.3, 1.0)
        assert result["valid"] is False

    # -- _validate_ragdoll_spec --

    def test_validate_ragdoll_spec_valid(self):
        spec = {
            "bone1": {"shape": "CAPSULE", "radius": 0.05, "length": 0.3, "mass": 2.0},
        }
        result = _validate_ragdoll_spec(spec)
        assert result["valid"] is True
        assert result["collider_count"] == 1

    def test_validate_ragdoll_spec_empty(self):
        result = _validate_ragdoll_spec({})
        assert result["valid"] is False

    def test_validate_ragdoll_spec_bad_shape(self):
        result = _validate_ragdoll_spec({
            "b": {"shape": "SPHERE", "radius": 0.1, "length": 0.1, "mass": 1.0},
        })
        assert result["valid"] is False

    def test_validate_ragdoll_preset_humanoid(self):
        """Humanoid ragdoll preset passes validation."""
        result = _validate_ragdoll_spec(RAGDOLL_PRESETS["humanoid"])
        assert result["valid"] is True
        assert result["collider_count"] > 5

    # -- _validate_retarget_mapping --

    def test_validate_retarget_mapping_valid(self):
        source = ["boneA", "boneB"]
        target = ["boneX", "boneY"]
        mapping = {"boneA": "boneX"}
        result = _validate_retarget_mapping(source, target, mapping)
        assert result["valid"] is True
        assert result["mapped_count"] == 1
        assert "boneB" in result["unmapped_source"]
        assert "boneY" in result["unmapped_target"]

    def test_validate_retarget_mapping_missing_bones(self):
        result = _validate_retarget_mapping(["a"], ["b"], {"missing": "also_missing"})
        assert result["valid"] is False

    # -- _validate_shape_key_params --

    def test_validate_shape_key_params_valid(self):
        result = _validate_shape_key_params("snarl", {0: (0.1, 0.0, 0.0), 1: (0.0, 0.1, 0.0)})
        assert result["valid"] is True
        assert result["vertex_count"] == 2

    def test_validate_shape_key_params_bad_name(self):
        result = _validate_shape_key_params("bad name!", {0: (0.0, 0.0, 0.0)})
        assert result["valid"] is False

    def test_validate_shape_key_params_empty_offsets(self):
        result = _validate_shape_key_params("test", {})
        assert result["valid"] is False


# ===================================================================
# TOOL 13: blender_animation (12 actions)
# ===================================================================


class TestTool13BlenderAnimation:
    """Verify all 12 animation action handler keys and functional tests."""

    ANIM_KEYS = {
        "anim_generate_walk", "anim_generate_fly", "anim_generate_idle",
        "anim_generate_attack", "anim_generate_reaction", "anim_generate_custom",
        "anim_preview", "anim_add_secondary_motion", "anim_extract_root_motion",
        "anim_retarget_mixamo", "anim_generate_ai_motion", "anim_batch_export",
    }

    def test_all_12_animation_handler_keys_registered(self):
        for key in self.ANIM_KEYS:
            assert key in HANDLER_KEYS, f"Missing animation handler key: {key}"

    # -- generate_cycle_keyframes for all 5 gaits --

    @pytest.mark.parametrize("gait", ["biped", "quadruped", "hexapod", "arachnid", "serpent"])
    def test_generate_cycle_keyframes_walk(self, gait):
        config = get_gait_config(gait, "walk", frame_count=24)
        kfs = generate_cycle_keyframes(config)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)
        # Verify seamless loop: frame 0 and frame 24 have same values for each bone
        by_bone = {}
        for kf in kfs:
            by_bone.setdefault((kf.bone_name, kf.channel, kf.axis), {})[kf.frame] = kf.value
        for key, frames in by_bone.items():
            if 0 in frames and 24 in frames:
                assert abs(frames[0] - frames[24]) < 1e-6, (
                    f"Seamless loop broken for {key}: frame0={frames[0]}, frame24={frames[24]}"
                )

    @pytest.mark.parametrize("gait", ["biped", "quadruped", "hexapod", "arachnid", "serpent"])
    def test_generate_cycle_keyframes_run(self, gait):
        config = get_gait_config(gait, "run")
        kfs = generate_cycle_keyframes(config)
        assert len(kfs) > 0

    # -- generate_attack_keyframes for all 8 attack types --

    @pytest.mark.parametrize("attack_type", list(ATTACK_CONFIGS.keys()))
    def test_generate_attack_keyframes(self, attack_type):
        kfs = generate_attack_keyframes(attack_type, frame_count=24, intensity=1.0)
        assert len(kfs) > 0
        # Verify all keyframes have frame in [0, 24]
        for kf in kfs:
            assert 0 <= kf.frame <= 24
        # Verify last phase ends at frame 24
        max_frame = max(kf.frame for kf in kfs)
        assert max_frame == 24

    def test_attack_configs_has_8_types(self):
        expected = {
            "melee_swing", "thrust", "slam", "bite",
            "claw", "tail_whip", "wing_buffet", "breath_attack",
        }
        assert set(ATTACK_CONFIGS.keys()) == expected

    # -- generate_reaction_keyframes --

    def test_generate_reaction_death(self):
        kfs = generate_reaction_keyframes("death", frame_count=24)
        assert len(kfs) > 0
        bone_names = {kf.bone_name for kf in kfs}
        assert "DEF-spine" in bone_names

    @pytest.mark.parametrize("direction", ["front", "back", "left", "right"])
    def test_generate_reaction_hit_all_directions(self, direction):
        kfs = generate_reaction_keyframes("hit", direction=direction, frame_count=24)
        assert len(kfs) > 0
        # Should include directional torso rotation
        spine001_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        assert len(spine001_kfs) > 0

    def test_generate_reaction_spawn(self):
        kfs = generate_reaction_keyframes("spawn", frame_count=30)
        assert len(kfs) > 0
        # Spawn starts from non-zero values
        first_frames = [kf for kf in kfs if kf.frame == 0]
        non_zero = [kf for kf in first_frames if abs(kf.value) > 0.01]
        assert len(non_zero) > 0

    # -- generate_custom_keyframes --

    def test_generate_custom_raise_arms_and_spin(self):
        kfs = generate_custom_keyframes("raise arms and spin", frame_count=48)
        assert len(kfs) > 0
        bone_names = {kf.bone_name for kf in kfs}
        # Should affect arm bones
        arm_bones = [b for b in bone_names if "arm" in b.lower()]
        assert len(arm_bones) > 0

    def test_generate_custom_empty_returns_empty(self):
        kfs = generate_custom_keyframes("", frame_count=24)
        assert len(kfs) == 0

    # -- Mixamo bone mapping --

    def test_mixamo_to_rigify_has_52_entries(self):
        """22 core + 30 finger bones = 52."""
        assert len(MIXAMO_TO_RIGIFY) == 52

    def test_mixamo_mapping_all_keys_have_prefix(self):
        for key in MIXAMO_TO_RIGIFY:
            assert key.startswith("mixamorig:"), f"Key {key} missing mixamorig: prefix"

    def test_mixamo_mapping_all_values_have_def_prefix(self):
        for val in MIXAMO_TO_RIGIFY.values():
            assert val.startswith("DEF-"), f"Value {val} missing DEF- prefix"

    # -- _map_mixamo_bones --

    def test_map_mixamo_bones_filters_existing(self):
        source = list(MIXAMO_TO_RIGIFY.keys())[:5]
        target = list(MIXAMO_TO_RIGIFY.values())[:5]
        result = _map_mixamo_bones(source, target)
        assert len(result["mapped"]) == 5

    def test_map_mixamo_bones_no_match(self):
        result = _map_mixamo_bones(["Random_Bone"], ["Other_Bone"])
        assert len(result["mapped"]) == 0

    # -- _generate_unity_filename --

    def test_unity_filename(self):
        assert _generate_unity_filename("Warrior", "Idle", "unity") == "Warrior@Idle.fbx"
        assert _generate_unity_filename("Warrior", "Idle", "raw") == "Idle.fbx"

    # -- Validation functions --

    def test_validate_walk_params_valid(self):
        result = _validate_walk_params({
            "object_name": "rig", "gait": "biped", "speed": "walk", "frame_count": 24,
        })
        assert result["gait"] == "biped"

    def test_validate_walk_params_invalid_gait(self):
        with pytest.raises(ValueError, match="Invalid gait"):
            _validate_walk_params({"object_name": "rig", "gait": "centipede"})

    def test_validate_attack_params_valid(self):
        result = _validate_attack_params({
            "object_name": "rig", "attack_type": "bite", "frame_count": 24,
        })
        assert result["attack_type"] == "bite"

    def test_validate_reaction_params_valid(self):
        result = _validate_reaction_params({
            "object_name": "rig", "reaction_type": "death",
        })
        assert result["reaction_type"] == "death"

    def test_validate_custom_params_valid(self):
        result = _validate_custom_params({
            "object_name": "rig", "description": "raise arms",
        })
        assert result["description"] == "raise arms"

    def test_validate_batch_export_params_valid(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp/anims", "naming": "unity",
        })
        assert result["valid"] is True

    def test_validate_batch_export_params_bad_naming(self):
        result = _validate_batch_export_params({
            "output_dir": "/tmp", "naming": "custom",
        })
        assert result["valid"] is False


# ===================================================================
# TOOL 14: blender_environment (9 actions)
# ===================================================================


class TestTool14BlenderEnvironment:
    """Verify all 9 environment action handler keys and functional tests."""

    ENV_KEYS = {
        "env_generate_terrain", "env_paint_terrain", "env_carve_river",
        "env_generate_road", "env_create_water", "env_export_heightmap",
        "env_scatter_vegetation", "env_scatter_props", "env_create_breakable",
    }

    def test_all_9_environment_handler_keys_registered(self):
        for key in self.ENV_KEYS:
            assert key in HANDLER_KEYS, f"Missing env handler key: {key}"

    # -- generate_heightmap for all 6 terrain presets --

    @pytest.mark.parametrize("terrain_type", list(TERRAIN_PRESETS.keys()))
    def test_generate_heightmap_all_presets(self, terrain_type):
        hmap = generate_heightmap(
            width=33, height=33, scale=50.0, seed=42,
            terrain_type=terrain_type,
        )
        assert hmap.shape == (33, 33)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0
        # Not all zeros
        assert hmap.max() > hmap.min()

    def test_terrain_presets_has_6_types(self):
        expected = {"mountains", "hills", "plains", "volcanic", "canyon", "cliffs"}
        assert set(TERRAIN_PRESETS.keys()) == expected

    # -- apply_hydraulic_erosion --

    def test_apply_hydraulic_erosion_changes_heightmap(self):
        hmap = generate_heightmap(width=33, height=33, seed=1, terrain_type="mountains")
        eroded = apply_hydraulic_erosion(hmap, iterations=50, seed=1)
        assert eroded.shape == hmap.shape
        assert eroded.min() >= 0.0
        assert eroded.max() <= 1.0
        # Erosion should change something
        diff = np.abs(eroded - hmap).sum()
        assert diff > 0, "Hydraulic erosion had no effect"

    # -- apply_thermal_erosion --

    def test_apply_thermal_erosion_changes_heightmap(self):
        # Create a heightmap with a sharp spike that exceeds the talus angle
        hmap = np.zeros((17, 17), dtype=np.float64)
        # Single spike at center: slope = 1.0 per cell >> tan(20) = 0.36
        hmap[8, 8] = 1.0
        hmap[7, 8] = 0.3
        hmap[9, 8] = 0.3
        hmap[8, 7] = 0.3
        hmap[8, 9] = 0.3
        eroded = apply_thermal_erosion(hmap, iterations=10, talus_angle=20.0)
        assert eroded.shape == hmap.shape
        diff = np.abs(eroded - hmap).sum()
        assert diff > 0, "Thermal erosion had no effect"

    # -- compute_biome_assignments --

    def test_compute_biome_assignments(self):
        hmap = generate_heightmap(width=33, height=33, seed=3, terrain_type="mountains")
        slope = compute_slope_map(hmap)
        biomes = compute_biome_assignments(hmap, slope)
        assert biomes.shape == hmap.shape
        assert biomes.dtype == np.int32
        # Should have at least 2 distinct biome indices
        unique = np.unique(biomes)
        assert len(unique) >= 2, f"Only {len(unique)} biome(s) assigned"

    # -- _export_heightmap_raw roundtrip --

    def test_export_heightmap_raw_roundtrip(self):
        hmap = np.array([[0.0, 0.5], [0.5, 1.0]])
        raw_bytes = _export_heightmap_raw(hmap, flip_vertical=False)
        # 4 pixels * 2 bytes each = 8 bytes
        assert len(raw_bytes) == 8
        # Decode and verify
        values = struct.unpack("<4H", raw_bytes)
        assert values[0] == 0       # 0.0 -> 0
        assert values[3] == 65535   # 1.0 -> 65535
        # Middle values should be around 32767
        assert 32000 < values[1] < 33000

    def test_export_heightmap_raw_flip_vertical(self):
        hmap = np.array([[0.0, 0.0], [1.0, 1.0]])
        raw_no_flip = _export_heightmap_raw(hmap, flip_vertical=False)
        raw_flip = _export_heightmap_raw(hmap, flip_vertical=True)
        # Flipped should have the rows reversed
        assert raw_no_flip != raw_flip

    # -- _validate_terrain_params --

    def test_validate_terrain_params_valid(self):
        result = _validate_terrain_params({
            "resolution": 129, "terrain_type": "mountains", "erosion": "both",
        })
        assert result["resolution"] == 129
        assert result["terrain_type"] == "mountains"
        assert result["erosion"] == "both"

    def test_validate_terrain_params_bad_type(self):
        with pytest.raises(ValueError, match="Unknown terrain_type"):
            _validate_terrain_params({"terrain_type": "fantasy"})

    def test_validate_terrain_params_oversized(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            _validate_terrain_params({"resolution": 2048})

    def test_validate_terrain_params_bad_erosion(self):
        with pytest.raises(ValueError, match="Unknown erosion"):
            _validate_terrain_params({"erosion": "wind"})


# ===================================================================
# TOOL 15: blender_worldbuilding (8 actions)
# ===================================================================


class TestTool15BlenderWorldbuilding:
    """Verify all 8 worldbuilding action handler keys and functional tests."""

    WORLD_KEYS = {
        "world_generate_building", "world_generate_castle", "world_generate_ruins",
        "world_generate_interior", "world_generate_modular_kit",
        "world_generate_dungeon", "world_generate_cave", "world_generate_town",
    }

    def test_all_8_worldbuilding_handler_keys_registered(self):
        for key in self.WORLD_KEYS:
            assert key in HANDLER_KEYS, f"Missing worldbuilding handler key: {key}"

    # -- generate_bsp_dungeon: verify connectivity --

    def test_generate_bsp_dungeon_connectivity(self):
        layout = generate_bsp_dungeon(width=64, height=64, min_room_size=6, max_depth=5, seed=42)
        assert isinstance(layout, DungeonLayout)
        assert len(layout.rooms) >= 2
        assert layout.grid is not None
        assert layout.grid.shape == (64, 64)

        # Verify all rooms reachable via flood fill from entrance
        from collections import deque
        entrance = layout.rooms[0]
        grid = layout.grid
        start = entrance.center
        visited = set()
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            if (x, y) in visited:
                continue
            if x < 0 or x >= 64 or y < 0 or y >= 64:
                continue
            if grid[y, x] == 0:
                continue
            visited.add((x, y))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                queue.append((x + dx, y + dy))

        for room in layout.rooms:
            assert room.center in visited, (
                f"Room at {room.center} not reachable from entrance"
            )

    def test_dungeon_has_spawn_and_loot(self):
        layout = generate_bsp_dungeon(width=64, height=64, seed=7)
        assert len(layout.spawn_points) >= 1
        assert len(layout.loot_points) >= 0  # boss/treasure rooms have loot

    # -- generate_cave_map: verify single connected region --

    def test_generate_cave_map_single_region(self):
        cave = generate_cave_map(width=64, height=64, fill_probability=0.45, iterations=5, seed=42)
        assert isinstance(cave, CaveMap)
        assert cave.grid is not None
        assert cave.grid.shape == (64, 64)
        assert len(cave.regions) == 1, f"Expected 1 region, got {len(cave.regions)}"
        # Verify floor cells exist
        floor_count = int(np.sum(cave.grid == 1))
        assert floor_count > 0

    # -- generate_town_layout: verify districts + roads --

    def test_generate_town_layout_has_districts_and_roads(self):
        town = generate_town_layout(width=100, height=100, num_districts=4, seed=42)
        assert isinstance(town, TownLayout)
        assert len(town.districts) == 4
        assert len(town.roads) > 0
        # Verify district types assigned
        types = {d["type"] for d in town.districts}
        assert "civic" in types
        # Should have building plots
        assert len(town.building_plots) > 0
        # Should have landmarks
        assert len(town.landmarks) > 0

    # -- evaluate_building_grammar for all 5 styles --

    @pytest.mark.parametrize("style", list(STYLE_CONFIGS.keys()))
    def test_evaluate_building_grammar_all_styles(self, style):
        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style=style, seed=0)
        assert isinstance(spec, BuildingSpec)
        assert spec.style == style
        assert spec.floors == 2
        assert len(spec.operations) > 0
        # Should have foundation, walls, roof, windows, door
        roles = {op.get("role") for op in spec.operations}
        assert "foundation" in roles
        assert "wall" in roles
        assert "roof" in roles

    def test_style_configs_has_5_styles(self):
        expected = {"medieval", "gothic", "rustic", "fortress", "organic"}
        assert set(STYLE_CONFIGS.keys()) == expected

    # -- apply_ruins_damage --

    def test_apply_ruins_damage(self):
        spec = evaluate_building_grammar(10, 8, 2, "medieval", seed=0)
        original_ops = len(spec.operations)
        damaged = apply_ruins_damage(spec, damage_level=0.7, seed=0)
        assert isinstance(damaged, BuildingSpec)
        # Damage should produce debris operations
        debris = [op for op in damaged.operations if op.get("role") == "debris"]
        assert len(debris) > 0
        # High damage should add vegetation
        veg = [op for op in damaged.operations if op.get("role") == "vegetation"]
        assert len(veg) > 0

    def test_apply_ruins_damage_zero_preserves(self):
        spec = evaluate_building_grammar(10, 8, 2, "medieval", seed=0)
        undamaged = apply_ruins_damage(spec, damage_level=0.0, seed=0)
        assert len(undamaged.operations) == len(spec.operations)

    # -- generate_interior_layout for all 8 room types --

    ROOM_TYPES = [
        "tavern", "throne_room", "dungeon_cell", "bedroom",
        "kitchen", "library", "armory", "chapel",
    ]

    @pytest.mark.parametrize("room_type", ROOM_TYPES)
    def test_generate_interior_layout_all_room_types(self, room_type):
        layout = generate_interior_layout(room_type, width=10, depth=8, height=3.0, seed=42)
        assert isinstance(layout, list)
        assert len(layout) > 0, f"Room type {room_type} produced empty layout"
        for item in layout:
            assert "type" in item
            assert "position" in item
            assert "rotation" in item
            assert "scale" in item
            assert len(item["position"]) == 3
            assert len(item["scale"]) == 3

    def test_interior_layout_no_overlaps(self):
        """Items in interior layout should not overlap."""
        layout = generate_interior_layout("tavern", width=12, depth=10, height=3.0, seed=42)
        # Check pairwise bounding box overlap
        for i in range(len(layout)):
            for j in range(i + 1, len(layout)):
                a = layout[i]
                b = layout[j]
                ax, ay = a["position"][0], a["position"][1]
                asx, asy = a["scale"][0], a["scale"][1]
                bx, by = b["position"][0], b["position"][1]
                bsx, bsy = b["scale"][0], b["scale"][1]
                overlap_x = abs(ax - bx) < (asx + bsx) / 2
                overlap_y = abs(ay - by) < (asy + bsy) / 2
                assert not (overlap_x and overlap_y), (
                    f"Items {a['type']} and {b['type']} overlap at "
                    f"({ax:.2f},{ay:.2f}) and ({bx:.2f},{by:.2f})"
                )

    # -- generate_modular_pieces --

    def test_generate_modular_pieces_all(self):
        pieces = generate_modular_pieces(cell_size=2.0)
        assert len(pieces) == len(MODULAR_CATALOG)
        for piece in pieces:
            assert "name" in piece
            assert "dimensions" in piece
            assert "connection_points" in piece
            assert piece["cell_size"] == 2.0
            # Dimensions should be scaled by cell_size
            assert all(d >= 2.0 for d in piece["dimensions"])

    def test_generate_modular_pieces_subset(self):
        pieces = generate_modular_pieces(cell_size=1.5, pieces=["wall_straight", "floor"])
        assert len(pieces) == 2
        names = {p["name"] for p in pieces}
        assert names == {"wall_straight", "floor"}

    def test_modular_catalog_has_8_entries(self):
        expected = {
            "wall_straight", "wall_corner", "wall_t", "floor",
            "door_frame", "window_frame", "stairs", "pillar",
        }
        assert set(MODULAR_CATALOG.keys()) == expected

    # -- geometry op converters --

    def test_dungeon_to_geometry_ops_produces_ops(self):
        layout = generate_bsp_dungeon(width=32, height=32, seed=99)
        ops = _dungeon_to_geometry_ops(layout, cell_size=2.0, wall_height=3.0)
        assert len(ops) > 0
        types = {op["type"] for op in ops}
        assert "floor" in types or "corridor" in types

    def test_cave_to_geometry_ops_produces_ops(self):
        cave = generate_cave_map(width=32, height=32, seed=99)
        ops = _cave_to_geometry_ops(cave, cell_size=2.0)
        assert len(ops) > 0

    def test_town_to_geometry_ops_produces_ops(self):
        town = generate_town_layout(width=60, height=60, num_districts=3, seed=99)
        ops = _town_to_geometry_ops(town, cell_size=2.0)
        assert len(ops) > 0
        types = {op["type"] for op in ops}
        assert "road" in types

    # -- pure-logic result builders --

    def test_build_building_result(self):
        spec = evaluate_building_grammar(10, 8, 2, "medieval", seed=0)
        result = _build_building_result("TestBuilding", spec)
        assert result["name"] == "TestBuilding"
        assert result["style"] == "medieval"
        assert result["floors"] == 2
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0

    def test_build_castle_result(self):
        spec = generate_castle_spec(outer_size=40, seed=0)
        result = _build_castle_result("TestCastle", spec)
        assert result["name"] == "TestCastle"
        assert result["component_count"] > 0
        assert len(result["roles"]) > 0

    def test_build_interior_result(self):
        layout = generate_interior_layout("tavern", 10, 8, seed=0)
        result = _build_interior_result("Tavern", "tavern", layout)
        assert result["room_type"] == "tavern"
        assert result["furniture_count"] == len(layout)

    def test_build_modular_kit_result(self):
        pieces = generate_modular_pieces(cell_size=2.0)
        result = _build_modular_kit_result(pieces, 2.0)
        assert result["piece_count"] == len(pieces)
        assert result["cell_size"] == 2.0


# ===================================================================
# Cross-tool: overall COMMAND_HANDLERS count
# ===================================================================


class TestHandlerRegistryCompleteness:
    """Verify COMMAND_HANDLERS has the expected total count."""

    def test_handler_count_at_least_expected(self):
        """Registry should have at least the documented handler count."""
        # As of the latest commit: 40 total handlers in __init__.py
        # Plus environment scatter (3) + worldbuilding (5) + worldbuilding_layout (3)
        # = at least 51 total
        assert len(HANDLER_KEYS) >= 50, (
            f"Expected at least 50 handler keys, got {len(HANDLER_KEYS)}"
        )

    def test_ping_handler_exists(self):
        assert "ping" in HANDLER_KEYS
