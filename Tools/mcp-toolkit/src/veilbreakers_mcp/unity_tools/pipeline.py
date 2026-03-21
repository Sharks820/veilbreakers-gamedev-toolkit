"""unity_pipeline tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
)

from veilbreakers_mcp.shared.unity_templates.pipeline_templates import (
    generate_gitlfs_config,
    generate_gitignore,
    generate_normal_map_bake_script,
    generate_sprite_atlas_script,
    generate_sprite_animation_script,
    generate_sprite_editor_config_script,
    generate_asset_postprocessor_script,
)
from veilbreakers_mcp.shared.unity_templates.code_templates import _sanitize_cs_identifier




# ---------------------------------------------------------------------------
# Compound tool: unity_pipeline (BUILD-06, TWO-03, PIPE-08, IMP-03)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_pipeline(
    action: Literal[
        "create_sprite_atlas",       # BUILD-06: SpriteAtlas creation
        "create_sprite_animation",   # BUILD-06: Sprite AnimationClip
        "configure_sprite_editor",   # TWO-03: Sprite Editor configuration
        "create_asset_postprocessor",  # PIPE-08: AssetPostprocessor with folder rules
        "configure_git_lfs",         # IMP-03: Git LFS + .gitignore setup
    ],
    # Sprite atlas params
    atlas_name: str = "",
    source_folder: str = "",
    padding: int = 4,
    enable_tight_packing: bool = True,
    enable_rotation: bool = False,
    max_texture_size: int = 4096,
    srgb: bool = True,
    filter_mode: str = "Bilinear",
    include_in_build: bool = True,
    # Sprite animation params
    clip_name: str = "",
    sprite_folder: str = "",
    frame_rate: int = 12,
    loop: bool = True,
    # Sprite editor params
    sprite_path: str = "",
    pivot: list[float] | None = None,
    border: list[int] | None = None,
    pixels_per_unit: int = 100,
    sprite_mode: int = 1,
    custom_physics_shape: bool = False,
    # Postprocessor params
    processor_name: str = "",
    version: int = 1,
    texture_rules: list[dict] | None = None,
    model_rules: list[dict] | None = None,
    audio_rules: list[dict] | None = None,
    namespace: str = "VeilBreakers.Editor",
    # Git LFS params
    extra_extensions: list[str] | None = None,
    include_unity_yaml_merge: bool = True,
    extra_patterns: list[str] | None = None,
    output_path: str = "",
) -> str:
    """Asset pipeline automation -- sprite atlasing, sprite animation, Sprite
    Editor configuration, AssetPostprocessor, and Git LFS setup.

    This compound tool generates C# editor scripts and configuration files
    for Unity asset pipeline automation.

    Actions:
    - create_sprite_atlas: Create SpriteAtlas with folder sources (BUILD-06)
    - create_sprite_animation: Create sprite-based AnimationClip (BUILD-06)
    - configure_sprite_editor: Configure Sprite Editor import settings (TWO-03)
    - create_asset_postprocessor: Create AssetPostprocessor with folder rules (PIPE-08)
    - configure_git_lfs: Generate .gitattributes and .gitignore for Unity project (IMP-03)

    Args:
        action: The pipeline action to perform.
        atlas_name: SpriteAtlas name.
        source_folder: Source folder for sprites.
        padding: Atlas padding in pixels (default 4).
        enable_tight_packing: Enable tight packing (default True).
        enable_rotation: Allow sprite rotation in atlas (default False).
        max_texture_size: Maximum atlas texture size (default 4096).
        srgb: sRGB color space (default True).
        filter_mode: Texture filter mode (default Bilinear).
        include_in_build: Include atlas in build (default True).
        clip_name: Animation clip name.
        sprite_folder: Folder containing sprite frames.
        frame_rate: Animation frame rate (default 12).
        loop: Loop animation (default True).
        sprite_path: Path to sprite asset for editor config.
        pivot: Sprite pivot point [x, y] (default center).
        border: Sprite border [left, bottom, right, top].
        pixels_per_unit: Pixels per unit (default 100).
        sprite_mode: Sprite mode (1=Single, 2=Multiple, 3=Polygon).
        custom_physics_shape: Enable custom physics shape.
        processor_name: AssetPostprocessor class name.
        version: Postprocessor version number.
        texture_rules: Texture import rules list.
        model_rules: Model import rules list.
        audio_rules: Audio import rules list.
        namespace: C# namespace for postprocessor.
        extra_extensions: Additional file extensions for Git LFS tracking.
        include_unity_yaml_merge: Include Unity YAML merge driver config.
        extra_patterns: Additional .gitignore patterns.
        output_path: Output path for generated files.
    """
    try:
        if action == "create_sprite_atlas":
            if not atlas_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "atlas_name is required"}
                )
            safe_name = _sanitize_cs_identifier(atlas_name) or "Atlas"
            script = generate_sprite_atlas_script(
                atlas_name=safe_name,
                source_folder=source_folder,
                output_path=output_path or f"Assets/SpriteAtlases/{safe_name}.spriteatlas",
                padding=padding,
                enable_tight_packing=enable_tight_packing,
                enable_rotation=enable_rotation,
                max_texture_size=max_texture_size,
                srgb=srgb,
                filter_mode=filter_mode,
                include_in_build=include_in_build,
            )
            rel_path = f"Assets/Editor/Generated/Pipeline/Create_{safe_name}_Atlas.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "atlas_name": safe_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the atlas script",
                    f"Execute menu item: VeilBreakers/Pipeline/Create {safe_name} Atlas",
                ],
            })

        elif action == "create_sprite_animation":
            if not clip_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "clip_name is required"}
                )
            safe_clip = _sanitize_cs_identifier(clip_name) or "SpriteAnim"
            script = generate_sprite_animation_script(
                clip_name=safe_clip,
                sprite_folder=sprite_folder,
                frame_rate=frame_rate,
                loop=loop,
                output_path=output_path or f"Assets/Animations/{safe_clip}.anim",
            )
            rel_path = f"Assets/Editor/Generated/Pipeline/Create_{safe_clip}_Animation.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "clip_name": safe_clip,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the animation script",
                    f"Execute menu item: VeilBreakers/Pipeline/Create {safe_clip} Animation",
                ],
            })

        elif action == "configure_sprite_editor":
            if not sprite_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "sprite_path is required"}
                )
            # Convert list params to tuples for the generator
            pivot_tuple = tuple(pivot) if pivot else None
            border_tuple = tuple(border) if border else None
            script = generate_sprite_editor_config_script(
                sprite_path=sprite_path,
                pivot=pivot_tuple,
                border=border_tuple,
                pixels_per_unit=pixels_per_unit,
                sprite_mode=sprite_mode,
                custom_physics_shape=custom_physics_shape,
            )
            rel_path = "Assets/Editor/Generated/Pipeline/ConfigureSpriteEditor.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "sprite_path": sprite_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the configuration script",
                    "Execute menu item: VeilBreakers/Pipeline/Configure Sprite Editor",
                ],
            })

        elif action == "create_asset_postprocessor":
            if not processor_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "processor_name is required"}
                )
            safe_name = _sanitize_cs_identifier(processor_name) or "Postprocessor"
            script = generate_asset_postprocessor_script(
                processor_name=safe_name,
                version=version,
                texture_rules=texture_rules,
                model_rules=model_rules,
                audio_rules=audio_rules,
                namespace=namespace,
            )
            rel_path = f"Assets/Editor/Generated/Pipeline/{safe_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "processor_name": safe_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the postprocessor",
                    "The postprocessor will run automatically on future asset imports",
                ],
            })

        elif action == "configure_git_lfs":
            # Generate .gitattributes
            gitattributes = generate_gitlfs_config(
                extra_extensions=extra_extensions,
                include_unity_yaml_merge=include_unity_yaml_merge,
            )
            # Generate .gitignore
            gitignore = generate_gitignore(
                extra_patterns=extra_patterns,
            )
            # Write to Unity project root
            gitattr_path = _write_to_unity(gitattributes, ".gitattributes")
            gitignore_path = _write_to_unity(gitignore, ".gitignore")
            return json.dumps({
                "status": "success",
                "action": action,
                "gitattributes_path": gitattr_path,
                "gitignore_path": gitignore_path,
                "next_steps": [
                    "Run 'git lfs install' in the Unity project directory if not already configured",
                    "Commit the .gitattributes and .gitignore files",
                ],
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_pipeline action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )
