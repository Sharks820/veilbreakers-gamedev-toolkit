"""unity_quality tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_generated_editor_response,
)

from veilbreakers_mcp.shared.unity_templates.quality_templates import (
    generate_poly_budget_check_script,
    generate_master_material_script,
    generate_texture_quality_check_script,
    generate_aaa_validation_script,
)
from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier




# ---------------------------------------------------------------------------
# Compound tool: unity_quality (AAA-01, AAA-02, AAA-03, AAA-04, AAA-06)
# ---------------------------------------------------------------------------

_QUALITY_MENU_PATHS = {
    "check_poly_budget": "VeilBreakers/Quality/Check Poly Budget",
    "create_master_materials": "VeilBreakers/Quality/Generate Master Material Library",
    "check_texture_quality": "VeilBreakers/Quality/Check Texture Quality",
    "aaa_audit": "VeilBreakers/Quality/Full AAA Audit",
}


@mcp.tool()
async def unity_quality(
    action: Literal[
        "check_poly_budget",         # AAA-02: Per-asset-type polygon budget check
        "create_master_materials",   # AAA-04: Master material library generation
        "check_texture_quality",     # AAA-06: Texture quality validation
        "aaa_audit",                 # Combined AAA quality audit
    ],
    asset_type: str = "prop",
    target_path: str = "",
    target_folder: str = "Assets",
    auto_flag: bool = True,
    output_folder: str = "Assets/Data/Materials/MasterLibrary",
    materials: list[dict] | None = None,
    target_texel_density: float = 10.24,
    check_normal_maps: bool = True,
    check_channel_packing: bool = True,
    check_poly: bool = True,
    check_textures: bool = True,
    check_materials: bool = True
) -> str:
    """AAA quality enforcement -- polygon budgets, master materials, texture quality, and combined quality auditing."""
    try:
        if action == "check_poly_budget":
            safe_type = sanitize_cs_identifier(asset_type) or "prop"
            script = generate_poly_budget_check_script(
                asset_type=safe_type,
                target_path=target_path,
                auto_flag=auto_flag,
            )
            rel_path = f"Assets/Editor/Generated/Quality/PolyBudgetCheck_{safe_type}.cs"
            return await _write_generated_editor_response(
                action_name=action,
                script_content=script,
                rel_path=rel_path,
                menu_path=_QUALITY_MENU_PATHS[action],
                response_fields={"asset_type": safe_type},
            )

        elif action == "create_master_materials":
            script = generate_master_material_script(
                output_folder=output_folder,
                materials=materials,
            )
            rel_path = "Assets/Editor/Generated/Quality/CreateMasterMaterials.cs"
            return await _write_generated_editor_response(
                action_name=action,
                script_content=script,
                rel_path=rel_path,
                menu_path=_QUALITY_MENU_PATHS[action],
                response_fields={
                    "material_count": len(materials) if materials else "default",
                    "output_folder": output_folder,
                },
            )

        elif action == "check_texture_quality":
            script = generate_texture_quality_check_script(
                target_folder=target_folder,
                target_texel_density=target_texel_density,
                check_normal_maps=check_normal_maps,
                check_channel_packing=check_channel_packing,
            )
            rel_path = "Assets/Editor/Generated/Quality/TextureQualityCheck.cs"
            return await _write_generated_editor_response(
                action_name=action,
                script_content=script,
                rel_path=rel_path,
                menu_path=_QUALITY_MENU_PATHS[action],
                response_fields={"target_folder": target_folder},
            )

        elif action == "aaa_audit":
            safe_type = sanitize_cs_identifier(asset_type) or "prop"
            script = generate_aaa_validation_script(
                target_folder=target_folder,
                asset_type=safe_type,
                check_poly=check_poly,
                check_textures=check_textures,
                check_materials=check_materials,
            )
            rel_path = "Assets/Editor/Generated/Quality/AAAQualityAudit.cs"
            return await _write_generated_editor_response(
                action_name=action,
                script_content=script,
                rel_path=rel_path,
                menu_path=_QUALITY_MENU_PATHS[action],
                response_fields={
                    "asset_type": safe_type,
                    "target_folder": target_folder,
                },
            )

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_quality action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )
