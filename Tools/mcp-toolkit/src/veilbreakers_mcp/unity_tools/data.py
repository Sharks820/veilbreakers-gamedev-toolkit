"""unity_data tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
)

from veilbreakers_mcp.shared.unity_templates.data_templates import (
    generate_so_definition,
    generate_asset_creation_script,
    generate_json_validator_script,
    generate_json_loader_script,
    generate_localization_setup_script,
    generate_localization_entries_script,
    generate_data_authoring_window,
)
from veilbreakers_mcp.shared.unity_templates.code_templates import _sanitize_cs_identifier




# ---------------------------------------------------------------------------
# Compound tool: unity_data (DATA-01, DATA-02, DATA-03, DATA-04)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_data(
    action: Literal[
        "create_so_definition",       # DATA-02: ScriptableObject class definition
        "create_so_assets",           # DATA-02: .asset file instantiation
        "validate_json",             # DATA-01: JSON config schema validator
        "create_json_loader",        # DATA-01: Typed C# data class + JSON loader
        "setup_localization",        # DATA-03: Unity Localization infrastructure
        "add_localization_entries",   # DATA-03: String table entry population
        "create_data_editor",        # DATA-04: IMGUI EditorWindow for SO authoring
    ],
    # SO definition params
    class_name: str = "",
    namespace: str = "VeilBreakers.Data",
    fields: list[dict] | None = None,
    summary: str = "",
    menu_name: str = "",
    file_name: str = "",
    # Asset creation params
    so_class_name: str = "",
    assets: list[dict] | None = None,
    output_folder: str = "Assets/Data",
    category: str = "",
    # JSON params
    config_name: str = "",
    json_path: str = "",
    schema: dict | None = None,
    wrapper_class: str = "",
    is_array: bool = True,
    # Localization params
    default_locale: str = "en",
    locales: list[str] | None = None,
    table_name: str = "VeilBreakers_UI",
    entries: dict[str, str] | None = None,
    locale: str = "en",
    # Data editor params
    window_name: str = "",
    menu_path: str = "",
    data_folder: str = "Assets/Data",
) -> str:
    """Data-driven game architecture -- ScriptableObject definitions, JSON config
    loading, localization setup, and data authoring editor windows.

    This compound tool generates C# editor scripts for data architecture,
    writes them to the Unity project, and returns instructions for executing
    them via the VB toolkit.

    Actions:
    - create_so_definition: Generate ScriptableObject class with CreateAssetMenu (DATA-02)
    - create_so_assets: Create .asset instances from a ScriptableObject class (DATA-02)
    - validate_json: Generate JSON config schema validator (DATA-01)
    - create_json_loader: Generate typed C# data class + JSON loader (DATA-01)
    - setup_localization: Set up Unity Localization infrastructure (DATA-03)
    - add_localization_entries: Populate string table entries (DATA-03)
    - create_data_editor: Generate IMGUI EditorWindow for batch SO authoring (DATA-04)

    Args:
        action: The data action to perform.
        class_name: C# class name for SO definition or JSON loader.
        namespace: C# namespace (default VeilBreakers.Data).
        fields: Field definitions (list of dicts with name, type, optional default/label).
        summary: XML summary comment for the class.
        menu_name: CreateAssetMenu menu name for SO.
        file_name: Default file name for SO asset creation.
        so_class_name: ScriptableObject class name for asset creation or data editor.
        assets: List of asset data dicts for create_so_assets.
        output_folder: Output folder for assets (default Assets/Data).
        category: Category name for asset organization.
        config_name: Config name for JSON validator.
        json_path: JSON file path for validation or loading.
        schema: JSON schema dict for validator.
        wrapper_class: Wrapper class name for JSON validator.
        is_array: Whether JSON data is an array (for JSON loader).
        default_locale: Default locale for localization (default en).
        locales: List of additional locale codes.
        table_name: String table name for localization.
        entries: Dict of key->value entries for localization.
        locale: Locale code for localization entries.
        window_name: EditorWindow class name for data editor.
        menu_path: MenuItem path for data editor.
        data_folder: Folder for data editor to browse (default Assets/Data).
    """
    try:
        if action == "create_so_definition":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            safe_class = _sanitize_cs_identifier(class_name) or "SODefinition"
            script = generate_so_definition(
                class_name=safe_class,
                namespace=namespace,
                fields=fields or [],
                summary=summary,
                menu_name=menu_name,
                file_name=file_name,
            )
            rel_path = f"Assets/Scripts/Generated/Data/{safe_class}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "class_name": safe_class,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the SO definition",
                ],
            })

        elif action == "create_so_assets":
            if not so_class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "so_class_name is required"}
                )
            safe_class = _sanitize_cs_identifier(so_class_name) or "SOClass"
            script = generate_asset_creation_script(
                so_class_name=safe_class,
                namespace=namespace,
                assets=assets or [],
                output_folder=output_folder,
                category=category,
                menu_path=menu_path or f"VeilBreakers/Data/Create {safe_class} Assets",
            )
            rel_path = f"Assets/Editor/Generated/Data/Create_{safe_class}_Assets.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "so_class_name": safe_class,
                "asset_count": len(assets or []),
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the script",
                    f"Execute menu item: VeilBreakers/Data/Create {safe_class} Assets",
                ],
            })

        elif action == "validate_json":
            if not config_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "config_name is required"}
                )
            safe_config = _sanitize_cs_identifier(config_name) or "Config"
            script = generate_json_validator_script(
                config_name=safe_config,
                json_path=json_path,
                schema=schema or {},
                wrapper_class=wrapper_class,
            )
            rel_path = f"Assets/Editor/Generated/Data/Validate_{safe_config}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "config_name": safe_config,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the validator",
                    f"Execute menu item: VeilBreakers/Data/Validate {safe_config}",
                ],
            })

        elif action == "create_json_loader":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            safe_class = _sanitize_cs_identifier(class_name) or "DataLoader"
            script = generate_json_loader_script(
                class_name=safe_class,
                namespace=namespace,
                fields=fields or [],
                json_path=json_path,
                is_array=is_array,
            )
            rel_path = f"Assets/Scripts/Generated/Data/{safe_class}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "class_name": safe_class,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the loader class",
                ],
            })

        elif action == "setup_localization":
            script = generate_localization_setup_script(
                default_locale=default_locale,
                locales=locales or [],
                table_name=table_name,
                output_dir=output_folder,
            )
            safe_table = _sanitize_cs_identifier(table_name) or "Localization"
            rel_path = f"Assets/Editor/Generated/Data/Setup_{safe_table}_Localization.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "table_name": table_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the setup script",
                    f"Execute menu item: VeilBreakers/Data/Setup {table_name} Localization",
                ],
            })

        elif action == "add_localization_entries":
            if not entries:
                return json.dumps(
                    {"status": "error", "action": action, "message": "entries dict is required"}
                )
            script = generate_localization_entries_script(
                table_name=table_name,
                entries=entries,
                locale=locale,
            )
            safe_table = _sanitize_cs_identifier(table_name) or "Localization"
            rel_path = f"Assets/Editor/Generated/Data/Add_{safe_table}_{locale}_Entries.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "table_name": table_name,
                "locale": locale,
                "entry_count": len(entries),
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the entries script",
                    f"Execute menu item: VeilBreakers/Data/Add {table_name} {locale} Entries",
                ],
            })

        elif action == "create_data_editor":
            if not window_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "window_name is required"}
                )
            if not so_class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "so_class_name is required"}
                )
            safe_window = _sanitize_cs_identifier(window_name) or "DataEditor"
            safe_so = _sanitize_cs_identifier(so_class_name) or "SOClass"
            script = generate_data_authoring_window(
                window_name=safe_window,
                so_class_name=safe_so,
                namespace=namespace,
                fields=fields or [],
                menu_path=menu_path or f"VeilBreakers/Data/{safe_window}",
                data_folder=data_folder,
                category=category,
            )
            rel_path = f"Assets/Editor/Generated/Data/{safe_window}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "window_name": safe_window,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the editor window",
                    f"Open via menu: {menu_path or f'VeilBreakers/Data/{safe_window}'}",
                ],
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_data action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )
