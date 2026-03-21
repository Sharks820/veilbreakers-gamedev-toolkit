"""unity_assets tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
)

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
)




# ---------------------------------------------------------------------------
# unity_assets compound tool -- asset pipeline operations
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_assets(
    action: Literal[
        "move",              # EDIT-10 + IMP-01: Move asset (GUID-safe)
        "rename",            # EDIT-10 + IMP-01: Rename asset (GUID-safe)
        "delete",            # EDIT-10: Delete asset (with optional reference scan)
        "duplicate",         # EDIT-10: Duplicate asset
        "create_folder",     # EDIT-10: Create folder
        "configure_fbx",     # EDIT-12: FBX ModelImporter settings
        "configure_texture", # EDIT-13: TextureImporter settings
        "remap_materials",   # EDIT-14 + IMP-02: Material remapping on FBX
        "auto_materials",    # EDIT-14 + IMP-02: Auto-generate materials from textures
        "create_asmdef",     # EDIT-15: Assembly Definition creation
        "create_preset",     # PIPE-09: Create Unity Preset
        "apply_preset",      # PIPE-09: Apply Unity Preset
        "scan_references",   # IMP-01: Scan asset references
        "atomic_import",     # Combined import sequence
    ],
    # Asset operation params
    asset_path: str = "",
    new_path: str = "",
    new_name: str = "",
    safe_delete: bool = True,
    source_path: str = "",
    dest_path: str = "",
    folder_path: str = "",
    # FBX import params
    scale: float = 1.0,
    mesh_compression: str = "Off",
    animation_type: str = "None",
    import_animation: bool = False,
    normals_mode: str = "Import",
    import_blend_shapes: bool = True,
    optimize: bool = True,
    is_readable: bool = False,
    preset_type: str = "",
    # Texture import params
    max_size: int = 2048,
    srgb: bool = True,
    mipmap: bool = True,
    filter_mode: str = "Bilinear",
    wrap_mode: str = "Repeat",
    sprite_mode: str = "",
    platform_overrides: dict | None = None,
    auto_detect_srgb: bool = False,
    # Material remap params
    fbx_path: str = "",
    remappings: dict | None = None,
    texture_dir: str = "",
    shader_name: str = "Universal Render Pipeline/Lit",
    material_name: str = "",
    # Asmdef params
    asmdef_name: str = "",
    root_dir: str = "",
    root_namespace: str = "",
    references: list[str] | None = None,
    platforms: list[str] | None = None,
    asmdef_defines: list[str] | None = None,
    allow_unsafe: bool = False,
    auto_referenced: bool = True,
    # Preset params
    preset_name: str = "",
    source_asset_path: str = "",
    save_dir: str = "Assets/Editor/Presets",
    preset_path: str = "",
    target_path: str = "",
    # Atomic import params
    texture_paths: list[str] | None = None,
) -> str:
    """Unity asset pipeline automation -- asset operations, import config,
    material management, Assembly Definitions, presets, and atomic imports.

    This compound tool generates C# editor scripts (or JSON for asmdef) for
    asset pipeline operations, writes them to the Unity project, and returns
    instructions for executing them via the VB toolkit.

    Actions:
    - move: Move asset preserving GUID (EDIT-10 + IMP-01)
    - rename: Rename asset preserving GUID (EDIT-10 + IMP-01)
    - delete: Delete asset with optional reference scan (EDIT-10)
    - duplicate: Duplicate asset (EDIT-10)
    - create_folder: Create folder structure (EDIT-10)
    - configure_fbx: Configure FBX ModelImporter settings (EDIT-12)
    - configure_texture: Configure TextureImporter settings (EDIT-13)
    - remap_materials: Remap materials on FBX import (EDIT-14 + IMP-02)
    - auto_materials: Auto-generate PBR materials from textures (EDIT-14 + IMP-02)
    - create_asmdef: Create Assembly Definition file (EDIT-15)
    - create_preset: Create Unity Preset from asset (PIPE-09)
    - apply_preset: Apply Unity Preset to asset (PIPE-09)
    - scan_references: Scan for assets referencing target (IMP-01)
    - atomic_import: Combined atomic import sequence
    """
    try:
        if action == "move":
            if not asset_path or not new_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path and new_path are required"}
                )
            return await _handle_assets_move(asset_path, new_path)
        elif action == "rename":
            if not asset_path or not new_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path and new_name are required"}
                )
            return await _handle_assets_rename(asset_path, new_name)
        elif action == "delete":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_delete(asset_path, safe_delete)
        elif action == "duplicate":
            if not source_path or not dest_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "source_path and dest_path are required"}
                )
            return await _handle_assets_duplicate(source_path, dest_path)
        elif action == "create_folder":
            if not folder_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "folder_path is required"}
                )
            return await _handle_assets_create_folder(folder_path)
        elif action == "configure_fbx":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_configure_fbx(
                asset_path, scale, mesh_compression, animation_type,
                import_animation, normals_mode, import_blend_shapes,
                optimize, is_readable, preset_type,
            )
        elif action == "configure_texture":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_configure_texture(
                asset_path, max_size, srgb, mipmap, filter_mode, wrap_mode,
                sprite_mode, platform_overrides, preset_type, auto_detect_srgb,
            )
        elif action == "remap_materials":
            if not fbx_path or not remappings:
                return json.dumps(
                    {"status": "error", "action": action, "message": "fbx_path and remappings are required"}
                )
            return await _handle_assets_remap_materials(fbx_path, remappings)
        elif action == "auto_materials":
            if not fbx_path or not texture_dir:
                return json.dumps(
                    {"status": "error", "action": action, "message": "fbx_path and texture_dir are required"}
                )
            return await _handle_assets_auto_materials(fbx_path, texture_dir, shader_name)
        elif action == "create_asmdef":
            if not asmdef_name or not root_dir:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asmdef_name and root_dir are required"}
                )
            return await _handle_assets_create_asmdef(
                asmdef_name, root_dir, root_namespace, references,
                platforms, asmdef_defines, allow_unsafe, auto_referenced,
            )
        elif action == "create_preset":
            if not preset_name or not source_asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "preset_name and source_asset_path are required"}
                )
            return await _handle_assets_create_preset(preset_name, source_asset_path, save_dir)
        elif action == "apply_preset":
            if not preset_path or not target_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "preset_path and target_path are required"}
                )
            return await _handle_assets_apply_preset(preset_path, target_path)
        elif action == "scan_references":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_scan_references(asset_path)
        elif action == "atomic_import":
            if not texture_paths or not material_name or not fbx_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "texture_paths, material_name, and fbx_path are required"}
                )
            return await _handle_assets_atomic_import(
                texture_paths, material_name, fbx_path, shader_name, remappings,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_assets action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# unity_assets handler functions
# ---------------------------------------------------------------------------


async def _handle_assets_move(asset_path: str, new_path: str) -> str:
    """Generate and write the asset move script."""
    script = generate_asset_move_script(asset_path, new_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_MoveAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "move", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "move", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Move Asset from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_rename(asset_path: str, new_name: str) -> str:
    """Generate and write the asset rename script."""
    script = generate_asset_rename_script(asset_path, new_name)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_RenameAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "rename", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "rename", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Rename Asset from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_delete(asset_path: str, safe_delete: bool) -> str:
    """Generate and write the asset delete script."""
    script = generate_asset_delete_script(asset_path, safe_delete=safe_delete)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_DeleteAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "delete", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "delete", "script_path": abs_path,
        "safe_delete": safe_delete,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Delete Asset from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_duplicate(source_path: str, dest_path: str) -> str:
    """Generate and write the asset duplicate script."""
    script = generate_asset_duplicate_script(source_path, dest_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_DuplicateAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "duplicate", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "duplicate", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Duplicate Asset from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_create_folder(folder_path: str) -> str:
    """Generate and write the create folder script."""
    script = generate_create_folder_script(folder_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_CreateFolder.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_folder", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_folder", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Create Folder from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_configure_fbx(
    asset_path: str, scale: float, mesh_compression: str,
    animation_type: str, import_animation: bool, normals_mode: str,
    import_blend_shapes: bool, optimize: bool, is_readable: bool,
    preset_type: str,
) -> str:
    """Generate and write the FBX import configuration script."""
    script = generate_fbx_import_script(
        asset_path, scale=scale, mesh_compression=mesh_compression,
        animation_type=animation_type, import_animation=import_animation,
        normals_mode=normals_mode, import_blend_shapes=import_blend_shapes,
        optimize=optimize, is_readable=is_readable, preset_type=preset_type,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ConfigureFBX.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_fbx", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "configure_fbx", "script_path": abs_path,
        "preset_type": preset_type if preset_type else "custom",
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Configure FBX Import from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_configure_texture(
    asset_path: str, max_size: int, srgb: bool, mipmap: bool,
    filter_mode: str, wrap_mode: str, sprite_mode: str,
    platform_overrides: dict | None, preset_type: str,
    auto_detect_srgb: bool,
) -> str:
    """Generate and write the texture import configuration script."""
    script = generate_texture_import_script(
        asset_path, max_size=max_size, srgb=srgb, mipmap=mipmap,
        filter_mode=filter_mode, wrap_mode=wrap_mode, sprite_mode=sprite_mode,
        platform_overrides=platform_overrides, preset_type=preset_type,
        auto_detect_srgb=auto_detect_srgb,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ConfigureTexture.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_texture", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "configure_texture", "script_path": abs_path,
        "preset_type": preset_type if preset_type else "custom",
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Configure Texture Import from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_remap_materials(fbx_path: str, remappings: dict) -> str:
    """Generate and write the material remap script."""
    script = generate_material_remap_script(fbx_path, remappings)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_RemapMaterials.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "remap_materials", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "remap_materials", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Remap Materials from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_auto_materials(
    fbx_path: str, texture_dir: str, shader_name: str,
) -> str:
    """Generate and write the auto material generation script."""
    script = generate_material_auto_generate_script(
        fbx_path, texture_dir, shader_name=shader_name,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_AutoMaterials.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "auto_materials", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "auto_materials", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Auto Generate Materials from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_create_asmdef(
    asmdef_name: str, root_dir: str, root_namespace: str,
    references: list[str] | None, platforms: list[str] | None,
    asmdef_defines: list[str] | None, allow_unsafe: bool,
    auto_referenced: bool,
) -> str:
    """Generate and write the assembly definition JSON file directly."""
    content = generate_asmdef_script(
        asmdef_name, root_dir, root_namespace=root_namespace,
        references=references, platforms=platforms, defines=asmdef_defines,
        allow_unsafe=allow_unsafe, auto_referenced=auto_referenced,
    )
    # asmdef is JSON, not C# -- write directly as {name}.asmdef
    asmdef_path = f"{root_dir.rstrip('/')}/{asmdef_name}.asmdef"
    try:
        abs_path = _write_to_unity(content, asmdef_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_asmdef", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_asmdef",
        "asmdef_path": abs_path, "asmdef_name": asmdef_name,
        "next_steps": [
            "Run unity_editor action=recompile to trigger Unity to recognize the new assembly definition",
        ],
        "result_file": None,
    }, indent=2)


async def _handle_assets_create_preset(
    preset_name: str, source_asset_path: str, save_dir: str,
) -> str:
    """Generate and write the preset creation script."""
    script = generate_preset_create_script(
        preset_name, source_asset_path, save_dir=save_dir,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_CreatePreset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_preset", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_preset", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Create Preset from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_apply_preset(preset_path: str, target_path: str) -> str:
    """Generate and write the preset apply script."""
    script = generate_preset_apply_script(preset_path, target_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ApplyPreset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "apply_preset", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "apply_preset", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Apply Preset from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_scan_references(asset_path: str) -> str:
    """Generate and write the reference scan script."""
    script = generate_reference_scan_script(asset_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ScanReferences.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "scan_references", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "scan_references", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Scan References from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_atomic_import(
    texture_paths: list[str], material_name: str, fbx_path: str,
    shader_name: str, remappings: dict | None,
) -> str:
    """Generate and write the atomic import script."""
    script = generate_atomic_import_script(
        texture_paths, material_name, fbx_path,
        shader_name=shader_name, remappings=remappings,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_AtomicImport.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "atomic_import", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "atomic_import", "script_path": abs_path,
        "next_steps": [
            "Run unity_editor action=recompile to compile the new script",
            'Open Unity Editor and run VeilBreakers > Assets > Atomic Import from the menu bar',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)
