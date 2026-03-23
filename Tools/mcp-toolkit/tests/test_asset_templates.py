"""Unit tests for Unity asset pipeline C# template generators.

Tests that each generator function produces valid C# source (or JSON for asmdef)
containing the expected Unity API calls, parameter substitutions, and safety
guarantees (never using File.Move for asset operations).
"""

import json

import pytest

from veilbreakers_mcp.shared.unity_templates.asset_templates import (
    generate_asset_move_script,
    generate_asset_rename_script,
    generate_asset_delete_script,
    generate_asset_duplicate_script,
    generate_create_folder_script,
    generate_fbx_import_script,
    generate_texture_import_script,
    generate_material_remap_script,
    generate_material_auto_generate_script,
    generate_asmdef_script,
    generate_preset_create_script,
    generate_preset_apply_script,
    generate_reference_scan_script,
    generate_atomic_import_script,
    generate_blender_to_unity_bridge_script,
)


# ---------------------------------------------------------------------------
# Asset Move
# ---------------------------------------------------------------------------


class TestGenerateAssetMoveScript:
    """Tests for generate_asset_move_script()."""

    def test_contains_asset_database_move(self):
        result = generate_asset_move_script("Assets/Old/model.fbx", "Assets/New/model.fbx")
        assert "AssetDatabase.MoveAsset" in result

    def test_never_uses_file_move(self):
        result = generate_asset_move_script("Assets/Old/model.fbx", "Assets/New/model.fbx")
        assert "File.Move" not in result

    def test_contains_old_path(self):
        result = generate_asset_move_script("Assets/Old/model.fbx", "Assets/New/model.fbx")
        assert "Assets/Old/model.fbx" in result

    def test_contains_new_path(self):
        result = generate_asset_move_script("Assets/Old/model.fbx", "Assets/New/model.fbx")
        assert "Assets/New/model.fbx" in result

    def test_contains_vb_result_json(self):
        result = generate_asset_move_script("Assets/Old/model.fbx", "Assets/New/model.fbx")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_asset_move_script("Assets/Old/model.fbx", "Assets/New/model.fbx")
        assert '[MenuItem("VeilBreakers/Assets/Move Asset")]' in result

    def test_contains_using_unity_editor(self):
        result = generate_asset_move_script("Assets/Old/model.fbx", "Assets/New/model.fbx")
        assert "using UnityEditor;" in result


# ---------------------------------------------------------------------------
# Asset Rename
# ---------------------------------------------------------------------------


class TestGenerateAssetRenameScript:
    """Tests for generate_asset_rename_script()."""

    def test_contains_asset_database_rename(self):
        result = generate_asset_rename_script("Assets/Models/old_name.fbx", "new_name")
        assert "AssetDatabase.RenameAsset" in result

    def test_never_uses_file_move(self):
        result = generate_asset_rename_script("Assets/Models/old_name.fbx", "new_name")
        assert "File.Move" not in result

    def test_contains_asset_path(self):
        result = generate_asset_rename_script("Assets/Models/old_name.fbx", "new_name")
        assert "Assets/Models/old_name.fbx" in result

    def test_contains_new_name(self):
        result = generate_asset_rename_script("Assets/Models/old_name.fbx", "new_name")
        assert "new_name" in result

    def test_contains_vb_result_json(self):
        result = generate_asset_rename_script("Assets/Models/old_name.fbx", "new_name")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_asset_rename_script("Assets/Models/old_name.fbx", "new_name")
        assert '[MenuItem("VeilBreakers/Assets/Rename Asset")]' in result


# ---------------------------------------------------------------------------
# Asset Delete
# ---------------------------------------------------------------------------


class TestGenerateAssetDeleteScript:
    """Tests for generate_asset_delete_script()."""

    def test_safe_delete_scans_references(self):
        result = generate_asset_delete_script("Assets/Old/model.fbx", safe_delete=True)
        assert "AssetDatabase.DeleteAsset" in result
        # Safe delete should scan for references first
        assert "blocked_by_references" in result or "referenc" in result.lower()

    def test_unsafe_delete_no_reference_scan(self):
        result = generate_asset_delete_script("Assets/Old/model.fbx", safe_delete=False)
        assert "AssetDatabase.DeleteAsset" in result

    def test_safe_and_unsafe_produce_different_output(self):
        safe = generate_asset_delete_script("Assets/Old/model.fbx", safe_delete=True)
        unsafe = generate_asset_delete_script("Assets/Old/model.fbx", safe_delete=False)
        assert safe != unsafe

    def test_never_uses_file_delete(self):
        result = generate_asset_delete_script("Assets/Old/model.fbx", safe_delete=True)
        assert "File.Delete" not in result

    def test_contains_vb_result_json(self):
        result = generate_asset_delete_script("Assets/Old/model.fbx")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_asset_delete_script("Assets/Old/model.fbx")
        assert '[MenuItem("VeilBreakers/Assets/Delete Asset")]' in result


# ---------------------------------------------------------------------------
# Asset Duplicate
# ---------------------------------------------------------------------------


class TestGenerateAssetDuplicateScript:
    """Tests for generate_asset_duplicate_script()."""

    def test_contains_asset_database_copy(self):
        result = generate_asset_duplicate_script("Assets/Models/model.fbx", "Assets/Models/model_copy.fbx")
        assert "AssetDatabase.CopyAsset" in result

    def test_never_uses_file_copy(self):
        result = generate_asset_duplicate_script("Assets/Models/model.fbx", "Assets/Models/model_copy.fbx")
        assert "File.Copy" not in result

    def test_contains_source_path(self):
        result = generate_asset_duplicate_script("Assets/Models/model.fbx", "Assets/Models/model_copy.fbx")
        assert "Assets/Models/model.fbx" in result

    def test_contains_dest_path(self):
        result = generate_asset_duplicate_script("Assets/Models/model.fbx", "Assets/Models/model_copy.fbx")
        assert "Assets/Models/model_copy.fbx" in result

    def test_contains_vb_result_json(self):
        result = generate_asset_duplicate_script("Assets/Models/model.fbx", "Assets/Models/model_copy.fbx")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_asset_duplicate_script("Assets/Models/model.fbx", "Assets/Models/model_copy.fbx")
        assert '[MenuItem("VeilBreakers/Assets/Duplicate Asset")]' in result


# ---------------------------------------------------------------------------
# Create Folder
# ---------------------------------------------------------------------------


class TestGenerateCreateFolderScript:
    """Tests for generate_create_folder_script()."""

    def test_contains_asset_database_create_folder(self):
        result = generate_create_folder_script("Assets/Prefabs/Monsters")
        assert "AssetDatabase.CreateFolder" in result

    def test_contains_folder_path(self):
        result = generate_create_folder_script("Assets/Prefabs/Monsters")
        assert "Monsters" in result

    def test_contains_vb_result_json(self):
        result = generate_create_folder_script("Assets/Prefabs/Monsters")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_create_folder_script("Assets/Prefabs/Monsters")
        assert '[MenuItem("VeilBreakers/Assets/Create Folder")]' in result


# ---------------------------------------------------------------------------
# FBX Import
# ---------------------------------------------------------------------------


class TestGenerateFbxImportScript:
    """Tests for generate_fbx_import_script()."""

    def test_contains_model_importer(self):
        result = generate_fbx_import_script(
            "Assets/Models/hero.fbx", scale=1.0, mesh_compression="Medium",
            animation_type="Humanoid", import_animation=True,
        )
        assert "ModelImporter" in result

    def test_contains_asset_importer_get_at_path(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx")
        assert "AssetImporter.GetAtPath" in result

    def test_contains_global_scale(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx", scale=2.5)
        assert "globalScale" in result

    def test_contains_mesh_compression(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx", mesh_compression="Medium")
        assert "meshCompression" in result

    def test_contains_animation_type_humanoid(self):
        result = generate_fbx_import_script(
            "Assets/Models/hero.fbx", animation_type="Humanoid",
        )
        assert "animationType" in result
        assert "Humanoid" in result

    def test_contains_save_and_reimport(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx")
        assert "SaveAndReimport" in result

    def test_preset_type_hero_uses_humanoid(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx", preset_type="hero")
        assert "Humanoid" in result

    def test_preset_type_prop_no_rig(self):
        result = generate_fbx_import_script("Assets/Models/prop.fbx", preset_type="prop")
        assert "None" in result or "ModelImporterAnimationType.None" in result

    def test_contains_vb_result_json(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx")
        assert '[MenuItem("VeilBreakers/Assets/Configure FBX Import")]' in result

    def test_contains_using_unity_editor(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx")
        assert "using UnityEditor;" in result

    def test_contains_changed_assets(self):
        result = generate_fbx_import_script("Assets/Models/hero.fbx")
        assert "changed_assets" in result


# ---------------------------------------------------------------------------
# Texture Import
# ---------------------------------------------------------------------------


class TestGenerateTextureImportScript:
    """Tests for generate_texture_import_script()."""

    def test_contains_texture_importer(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png")
        assert "TextureImporter" in result

    def test_contains_max_size(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png", max_size=2048)
        assert "2048" in result

    def test_contains_save_and_reimport(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png")
        assert "SaveAndReimport" in result

    def test_platform_overrides_set_platform_settings(self):
        overrides = {
            "Standalone": {"format": "DXT5", "max_size": 2048},
            "Android": {"format": "ASTC_6x6", "max_size": 1024},
        }
        result = generate_texture_import_script(
            "Assets/Textures/albedo.png", platform_overrides=overrides,
        )
        assert "SetPlatformTextureSettings" in result
        assert "TextureImporterFormat" in result

    def test_preset_type_hero_max_size_2048(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png", preset_type="hero")
        assert "2048" in result

    def test_preset_type_prop_max_size_512(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png", preset_type="prop")
        assert "512" in result

    def test_auto_detect_srgb_checks_name(self):
        result = generate_texture_import_script(
            "Assets/Textures/albedo.png", auto_detect_srgb=True,
        )
        # Should check for normal, roughness, metallic keywords
        assert "normal" in result.lower() or "Normal" in result

    def test_contains_vb_result_json(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png")
        assert '[MenuItem("VeilBreakers/Assets/Configure Texture Import")]' in result

    def test_contains_changed_assets(self):
        result = generate_texture_import_script("Assets/Textures/albedo.png")
        assert "changed_assets" in result


# ---------------------------------------------------------------------------
# Material Remap
# ---------------------------------------------------------------------------


class TestGenerateMaterialRemapScript:
    """Tests for generate_material_remap_script()."""

    def test_contains_model_importer(self):
        remappings = {"Material_1": "Assets/Materials/HeroSkin.mat"}
        result = generate_material_remap_script("Assets/Models/hero.fbx", remappings)
        assert "ModelImporter" in result

    def test_contains_add_remap_or_material_import(self):
        remappings = {"Material_1": "Assets/Materials/HeroSkin.mat"}
        result = generate_material_remap_script("Assets/Models/hero.fbx", remappings)
        assert "AddRemap" in result or "materialImportMode" in result

    def test_contains_load_material(self):
        remappings = {"Material_1": "Assets/Materials/HeroSkin.mat"}
        result = generate_material_remap_script("Assets/Models/hero.fbx", remappings)
        assert "LoadAssetAtPath" in result and "Material" in result

    def test_contains_save_and_reimport(self):
        remappings = {"Material_1": "Assets/Materials/HeroSkin.mat"}
        result = generate_material_remap_script("Assets/Models/hero.fbx", remappings)
        assert "SaveAndReimport" in result

    def test_contains_vb_result_json(self):
        remappings = {"Material_1": "Assets/Materials/HeroSkin.mat"}
        result = generate_material_remap_script("Assets/Models/hero.fbx", remappings)
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        remappings = {"Material_1": "Assets/Materials/HeroSkin.mat"}
        result = generate_material_remap_script("Assets/Models/hero.fbx", remappings)
        assert '[MenuItem("VeilBreakers/Assets/Remap Materials")]' in result


# ---------------------------------------------------------------------------
# Material Auto Generate
# ---------------------------------------------------------------------------


class TestGenerateMaterialAutoGenerateScript:
    """Tests for generate_material_auto_generate_script()."""

    def test_contains_shader_find(self):
        result = generate_material_auto_generate_script(
            "Assets/Models/hero.fbx", "Assets/Textures/Hero/",
        )
        assert "Shader.Find" in result

    def test_contains_urp_lit_shader(self):
        result = generate_material_auto_generate_script(
            "Assets/Models/hero.fbx", "Assets/Textures/Hero/",
        )
        assert "Universal Render Pipeline/Lit" in result

    def test_contains_base_map_property(self):
        result = generate_material_auto_generate_script(
            "Assets/Models/hero.fbx", "Assets/Textures/Hero/",
        )
        assert "_BaseMap" in result or "_MainTex" in result

    def test_contains_bump_map(self):
        result = generate_material_auto_generate_script(
            "Assets/Models/hero.fbx", "Assets/Textures/Hero/",
        )
        assert "_BumpMap" in result

    def test_contains_vb_result_json(self):
        result = generate_material_auto_generate_script(
            "Assets/Models/hero.fbx", "Assets/Textures/Hero/",
        )
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_material_auto_generate_script(
            "Assets/Models/hero.fbx", "Assets/Textures/Hero/",
        )
        assert '[MenuItem("VeilBreakers/Assets/Auto Generate Materials")]' in result


# ---------------------------------------------------------------------------
# Assembly Definition (asmdef)
# ---------------------------------------------------------------------------


class TestGenerateAsmdefScript:
    """Tests for generate_asmdef_script()."""

    def test_returns_valid_json(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
        )
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_contains_name_key(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
        )
        parsed = json.loads(result)
        assert parsed["name"] == "VeilBreakers.Runtime"

    def test_contains_root_namespace(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
            root_namespace="VeilBreakers",
        )
        parsed = json.loads(result)
        assert parsed["rootNamespace"] == "VeilBreakers"

    def test_default_root_namespace_matches_name(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
        )
        parsed = json.loads(result)
        assert parsed["rootNamespace"] == "VeilBreakers.Runtime"

    def test_contains_references(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
            references=["Unity.InputSystem", "Unity.AI.Navigation"],
        )
        parsed = json.loads(result)
        assert "Unity.InputSystem" in parsed["references"]
        assert "Unity.AI.Navigation" in parsed["references"]

    def test_contains_include_platforms(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
            platforms=["Editor"],
        )
        parsed = json.loads(result)
        assert "Editor" in parsed["includePlatforms"]

    def test_contains_define_constraints(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
            defines=["VEILBREAKERS_DEBUG"],
        )
        parsed = json.loads(result)
        assert "VEILBREAKERS_DEBUG" in parsed["defineConstraints"]

    def test_has_all_required_keys(self):
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
        )
        parsed = json.loads(result)
        required_keys = [
            "name", "rootNamespace", "references", "includePlatforms",
            "excludePlatforms", "allowUnsafeCode", "overrideReferences",
            "precompiledReferences", "autoReferenced", "defineConstraints",
            "versionDefines", "noEngineReferences",
        ]
        for key in required_keys:
            assert key in parsed, f"Missing key: {key}"

    def test_is_not_csharp(self):
        """Asmdef output should be JSON, not C#."""
        result = generate_asmdef_script(
            "VeilBreakers.Runtime", "Assets/Scripts/Runtime/",
        )
        assert "using UnityEditor;" not in result
        assert "MenuItem" not in result


# ---------------------------------------------------------------------------
# Preset Create
# ---------------------------------------------------------------------------


class TestGeneratePresetCreateScript:
    """Tests for generate_preset_create_script()."""

    def test_contains_new_preset(self):
        result = generate_preset_create_script(
            "HeroFBXPreset", "Assets/Models/hero.fbx",
        )
        assert "new Preset" in result or "Preset(" in result

    def test_contains_create_asset(self):
        result = generate_preset_create_script(
            "HeroFBXPreset", "Assets/Models/hero.fbx",
        )
        assert "AssetDatabase.CreateAsset" in result

    def test_preset_extension(self):
        result = generate_preset_create_script(
            "HeroFBXPreset", "Assets/Models/hero.fbx",
        )
        assert ".preset" in result

    def test_contains_vb_result_json(self):
        result = generate_preset_create_script(
            "HeroFBXPreset", "Assets/Models/hero.fbx",
        )
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_preset_create_script(
            "HeroFBXPreset", "Assets/Models/hero.fbx",
        )
        assert '[MenuItem("VeilBreakers/Assets/Create Preset")]' in result


# ---------------------------------------------------------------------------
# Preset Apply
# ---------------------------------------------------------------------------


class TestGeneratePresetApplyScript:
    """Tests for generate_preset_apply_script()."""

    def test_contains_apply_to(self):
        result = generate_preset_apply_script(
            "Assets/Editor/Presets/HeroFBXPreset.preset",
            "Assets/Models/new_hero.fbx",
        )
        assert "ApplyTo" in result

    def test_contains_preset_path(self):
        result = generate_preset_apply_script(
            "Assets/Editor/Presets/HeroFBXPreset.preset",
            "Assets/Models/new_hero.fbx",
        )
        assert "HeroFBXPreset.preset" in result

    def test_contains_vb_result_json(self):
        result = generate_preset_apply_script(
            "Assets/Editor/Presets/HeroFBXPreset.preset",
            "Assets/Models/new_hero.fbx",
        )
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_preset_apply_script(
            "Assets/Editor/Presets/HeroFBXPreset.preset",
            "Assets/Models/new_hero.fbx",
        )
        assert '[MenuItem("VeilBreakers/Assets/Apply Preset")]' in result


# ---------------------------------------------------------------------------
# Reference Scan
# ---------------------------------------------------------------------------


class TestGenerateReferenceScanScript:
    """Tests for generate_reference_scan_script()."""

    def test_contains_guid_lookup(self):
        result = generate_reference_scan_script("Assets/Models/old.fbx")
        assert "AssetPathToGUID" in result or "GUID" in result

    def test_contains_dependency_search(self):
        result = generate_reference_scan_script("Assets/Models/old.fbx")
        # Should either use GetDependencies or search by GUID
        assert "GetDependencies" in result or "FindAssets" in result or "GUID" in result

    def test_contains_vb_result_json(self):
        result = generate_reference_scan_script("Assets/Models/old.fbx")
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_reference_scan_script("Assets/Models/old.fbx")
        assert '[MenuItem("VeilBreakers/Assets/Scan References")]' in result


# ---------------------------------------------------------------------------
# Atomic Import
# ---------------------------------------------------------------------------


class TestGenerateAtomicImportScript:
    """Tests for generate_atomic_import_script()."""

    def test_contains_start_asset_editing(self):
        result = generate_atomic_import_script(
            texture_paths=["Assets/Textures/albedo.png"],
            material_name="HeroSkin",
            fbx_path="Assets/Models/hero.fbx",
        )
        assert "StartAssetEditing" in result

    def test_contains_stop_asset_editing(self):
        result = generate_atomic_import_script(
            texture_paths=["Assets/Textures/albedo.png"],
            material_name="HeroSkin",
            fbx_path="Assets/Models/hero.fbx",
        )
        assert "StopAssetEditing" in result

    def test_enforces_order_textures_before_materials(self):
        """Verify the atomic import enforces: textures -> materials -> FBX -> remap."""
        result = generate_atomic_import_script(
            texture_paths=["Assets/Textures/albedo.png", "Assets/Textures/normal.png"],
            material_name="HeroSkin",
            fbx_path="Assets/Models/hero.fbx",
            remappings={"default": "HeroSkin"},
        )
        # Step ordering: texture import before material, material before FBX
        tex_idx = result.index("TextureImporter") if "TextureImporter" in result else -1
        mat_idx = result.index("new Material") if "new Material" in result else result.index("Material(")
        fbx_idx = result.index("ModelImporter")
        assert tex_idx < mat_idx < fbx_idx

    def test_contains_changed_assets(self):
        result = generate_atomic_import_script(
            texture_paths=["Assets/Textures/albedo.png"],
            material_name="HeroSkin",
            fbx_path="Assets/Models/hero.fbx",
        )
        assert "changed_assets" in result

    def test_contains_vb_result_json(self):
        result = generate_atomic_import_script(
            texture_paths=["Assets/Textures/albedo.png"],
            material_name="HeroSkin",
            fbx_path="Assets/Models/hero.fbx",
        )
        assert "vb_result.json" in result

    def test_contains_menu_item(self):
        result = generate_atomic_import_script(
            texture_paths=["Assets/Textures/albedo.png"],
            material_name="HeroSkin",
            fbx_path="Assets/Models/hero.fbx",
        )
        assert '[MenuItem("VeilBreakers/Assets/Atomic Import")]' in result


# ---------------------------------------------------------------------------
# Blender-to-Unity Bridge
# ---------------------------------------------------------------------------


class TestGenerateBlenderToUnityBridgeScript:
    """Tests for generate_blender_to_unity_bridge_script()."""

    def test_contains_menu_item(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert '[MenuItem("VeilBreakers/Assets/Blender To Unity Bridge")]' in result

    def test_contains_using_unity_editor(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "using UnityEditor;" in result

    def test_contains_vb_result_json(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "vb_result.json" in result

    def test_contains_validation_status(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "validation_status" in result

    def test_contains_fbx_path(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "Assets/Models/hero.fbx" in result

    def test_contains_model_importer(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "ModelImporter" in result

    def test_contains_texture_scan(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "FindAssets" in result

    def test_contains_material_creation(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "new Material" in result

    def test_contains_normal_map_fix(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "FixNormalMapImport" in result
        assert "NormalMap" in result

    def test_contains_prefab_creation(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx", create_prefab=True
        )
        assert "SaveAsPrefabAsset" in result

    def test_contains_lod_setup(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx", setup_lod=True
        )
        assert "_LOD" in result

    def test_contains_poly_budget_validation(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx", validate_budget=True
        )
        assert "polyBudget" in result

    def test_hero_preset_uses_humanoid(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx", asset_type="hero"
        )
        assert "Humanoid" in result

    def test_weapon_preset_uses_none_animation(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/sword.fbx", asset_type="weapon"
        )
        assert "ModelImporterAnimationType.None" in result

    def test_custom_shader_name(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx",
            shader_name="Shader Graphs/CustomLit",
        )
        assert "Shader Graphs/CustomLit" in result

    def test_custom_texture_dir(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx",
            texture_dir="Assets/Textures/Hero",
        )
        assert "Assets/Textures/Hero" in result

    def test_contains_all_pipeline_steps(self):
        """Bridge must contain all 10 pipeline steps."""
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "scan_fbx" in result
        assert "configure_import" in result
        assert "fix_normals" in result
        assert "auto_materials" in result
        assert "setup_lod" in result
        assert "configure_avatar" in result
        assert "create_prefab" in result
        assert "validate_budget" in result

    def test_step_ordering_scan_before_configure(self):
        """Scan must come before configure in the generated script."""
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        scan_idx = result.index("Step 1: Scan FBX")
        config_idx = result.index("Step 2: Configure Import")
        assert scan_idx < config_idx

    def test_step_ordering_materials_before_prefab(self):
        """Materials must be created before prefab."""
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        mat_idx = result.index("Step 4")
        prefab_idx = result.index("Step 8")
        assert mat_idx < prefab_idx

    def test_contains_bridge_report_class(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "BridgeReport" in result

    def test_contains_step_result_tracking(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "PassStep" in result
        assert "FailStep" in result
        assert "SkipStep" in result

    def test_contains_pbr_texture_assignments(self):
        """Must assign all PBR map types."""
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "_BaseMap" in result       # albedo
        assert "_BumpMap" in result        # normal
        assert "_MetallicGlossMap" in result  # metallic
        assert "_OcclusionMap" in result   # AO
        assert "_EmissionMap" in result    # emission
        assert "_ParallaxMap" in result    # height

    def test_contains_ensure_folder(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "EnsureFolder" in result

    def test_contains_asset_database_save(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "AssetDatabase.SaveAssets()" in result

    def test_contains_changed_assets_in_report(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "changed_assets" in result

    def test_hero_poly_budget_is_65000(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx", asset_type="hero"
        )
        assert "65000" in result

    def test_weapon_poly_budget_is_15000(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/sword.fbx", asset_type="weapon"
        )
        assert "15000" in result

    def test_environment_poly_budget_is_100000(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/terrain.fbx", asset_type="environment"
        )
        assert "100000" in result

    def test_prefab_folder_hero(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx", asset_type="hero"
        )
        assert "Characters/Heroes" in result

    def test_prefab_folder_weapon(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/sword.fbx", asset_type="weapon"
        )
        assert "Equipment/Weapons" in result

    def test_no_file_move(self):
        """Bridge must never use File.Move for asset operations."""
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "File.Move" not in result
        assert "File.Copy" not in result
        assert "File.Delete" not in result

    def test_contains_tangent_import_mode(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "CalculateMikk" in result

    def test_auto_detect_texture_dir_when_empty(self):
        result = generate_blender_to_unity_bridge_script(
            "Assets/Models/hero.fbx", texture_dir=""
        )
        assert "GetDirectoryName" in result

    def test_action_is_blender_to_unity_bridge(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "blender_to_unity_bridge" in result

    def test_handles_missing_shader_gracefully(self):
        """Must handle missing shader with warning, not crash."""
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "Shader not found" in result
        assert "Standard" in result  # fallback shader

    def test_mesh_count_tracked(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "meshCount" in result
        assert "MeshFilter" in result

    def test_skinned_mesh_tracked(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "SkinnedMeshRenderer" in result

    def test_animation_clips_tracked(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "AnimationClip" in result
        assert "animationClipCount" in result

    def test_bone_count_tracked(self):
        result = generate_blender_to_unity_bridge_script("Assets/Models/hero.fbx")
        assert "boneCount" in result


# ---------------------------------------------------------------------------
# Cross-cutting: all generators use Unity APIs and never File.Move
# ---------------------------------------------------------------------------


class TestAllGeneratorsCrossCutting:
    """Tests that apply across all generator functions."""

    def test_no_file_move_in_any_asset_script(self):
        """File.Move must NEVER appear in any asset operation script."""
        scripts = [
            generate_asset_move_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_asset_rename_script("Assets/a.fbx", "new_name"),
            generate_asset_delete_script("Assets/a.fbx"),
            generate_asset_duplicate_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_create_folder_script("Assets/NewFolder"),
        ]
        for script in scripts:
            assert "File.Move" not in script
            assert "File.Copy" not in script
            assert "File.Delete" not in script

    def test_all_cs_generators_have_using_unity_editor(self):
        """All C# generators (not asmdef) must include using UnityEditor."""
        generators = [
            generate_asset_move_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_asset_rename_script("Assets/a.fbx", "new_name"),
            generate_asset_delete_script("Assets/a.fbx"),
            generate_asset_duplicate_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_create_folder_script("Assets/NewFolder"),
            generate_fbx_import_script("Assets/a.fbx"),
            generate_texture_import_script("Assets/a.png"),
            generate_material_remap_script("Assets/a.fbx", {"m": "Assets/m.mat"}),
            generate_material_auto_generate_script("Assets/a.fbx", "Assets/Textures/"),
            generate_preset_create_script("Preset", "Assets/a.fbx"),
            generate_preset_apply_script("Assets/p.preset", "Assets/a.fbx"),
            generate_reference_scan_script("Assets/a.fbx"),
            generate_atomic_import_script(["Assets/t.png"], "Mat", "Assets/a.fbx"),
            generate_blender_to_unity_bridge_script("Assets/a.fbx"),
        ]
        for script in generators:
            assert "using UnityEditor;" in script

    def test_all_cs_generators_have_menu_item(self):
        """All C# generators must register a MenuItem."""
        generators = [
            generate_asset_move_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_asset_rename_script("Assets/a.fbx", "new_name"),
            generate_asset_delete_script("Assets/a.fbx"),
            generate_asset_duplicate_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_create_folder_script("Assets/NewFolder"),
            generate_fbx_import_script("Assets/a.fbx"),
            generate_texture_import_script("Assets/a.png"),
            generate_material_remap_script("Assets/a.fbx", {"m": "Assets/m.mat"}),
            generate_material_auto_generate_script("Assets/a.fbx", "Assets/Textures/"),
            generate_preset_create_script("Preset", "Assets/a.fbx"),
            generate_preset_apply_script("Assets/p.preset", "Assets/a.fbx"),
            generate_reference_scan_script("Assets/a.fbx"),
            generate_atomic_import_script(["Assets/t.png"], "Mat", "Assets/a.fbx"),
            generate_blender_to_unity_bridge_script("Assets/a.fbx"),
        ]
        for script in generators:
            assert "[MenuItem(" in script

    def test_all_cs_generators_have_vb_result_json(self):
        """All C# generators must write to vb_result.json."""
        generators = [
            generate_asset_move_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_asset_rename_script("Assets/a.fbx", "new_name"),
            generate_asset_delete_script("Assets/a.fbx"),
            generate_asset_duplicate_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_create_folder_script("Assets/NewFolder"),
            generate_fbx_import_script("Assets/a.fbx"),
            generate_texture_import_script("Assets/a.png"),
            generate_material_remap_script("Assets/a.fbx", {"m": "Assets/m.mat"}),
            generate_material_auto_generate_script("Assets/a.fbx", "Assets/Textures/"),
            generate_preset_create_script("Preset", "Assets/a.fbx"),
            generate_preset_apply_script("Assets/p.preset", "Assets/a.fbx"),
            generate_reference_scan_script("Assets/a.fbx"),
            generate_atomic_import_script(["Assets/t.png"], "Mat", "Assets/a.fbx"),
            generate_blender_to_unity_bridge_script("Assets/a.fbx"),
        ]
        for script in generators:
            assert "vb_result.json" in script

    def test_all_cs_generators_have_validation_status(self):
        """All C# generators should include validation_status in result JSON."""
        generators = [
            generate_asset_move_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_asset_rename_script("Assets/a.fbx", "new_name"),
            generate_asset_delete_script("Assets/a.fbx"),
            generate_asset_duplicate_script("Assets/a.fbx", "Assets/b.fbx"),
            generate_create_folder_script("Assets/NewFolder"),
            generate_fbx_import_script("Assets/a.fbx"),
            generate_texture_import_script("Assets/a.png"),
            generate_material_remap_script("Assets/a.fbx", {"m": "Assets/m.mat"}),
            generate_material_auto_generate_script("Assets/a.fbx", "Assets/Textures/"),
            generate_preset_create_script("Preset", "Assets/a.fbx"),
            generate_preset_apply_script("Assets/p.preset", "Assets/a.fbx"),
            generate_reference_scan_script("Assets/a.fbx"),
            generate_atomic_import_script(["Assets/t.png"], "Mat", "Assets/a.fbx"),
            generate_blender_to_unity_bridge_script("Assets/a.fbx"),
        ]
        for script in generators:
            assert "validation_status" in script
