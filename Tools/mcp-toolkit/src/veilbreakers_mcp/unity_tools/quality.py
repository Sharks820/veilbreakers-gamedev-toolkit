"""unity_quality tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template, STANDARD_NEXT_STEPS,
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
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "asset_type": safe_type,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "create_master_materials":
            script = generate_master_material_script(
                output_folder=output_folder,
                materials=materials,
            )
            rel_path = "Assets/Editor/Generated/Quality/CreateMasterMaterials.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "material_count": len(materials) if materials else "default",
                "next_steps": STANDARD_NEXT_STEPS,
            })

        elif action == "check_texture_quality":
            script = generate_texture_quality_check_script(
                target_folder=target_folder,
                target_texel_density=target_texel_density,
                check_normal_maps=check_normal_maps,
                check_channel_packing=check_channel_packing,
            )
            rel_path = "Assets/Editor/Generated/Quality/TextureQualityCheck.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": STANDARD_NEXT_STEPS,
            })

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
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "asset_type": safe_type,
                "next_steps": STANDARD_NEXT_STEPS,
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_quality action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )
