"""unity_ui tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.ui_templates import (
    generate_uxml_screen,
    generate_uss_stylesheet,
    generate_responsive_test_script,
    validate_uxml_layout,
)
from veilbreakers_mcp.shared.wcag_checker import validate_uxml_contrast
from veilbreakers_mcp.shared.screenshot_diff import (
    compare_screenshots as _compare_screenshots,
    generate_diff_image,
)
from veilbreakers_mcp.shared.unity_templates.ui_polish_templates import (
    generate_procedural_frame_script,
    generate_icon_render_pipeline_script,
    generate_cursor_system_script,
    generate_tooltip_system_script,
    generate_radial_menu_script,
    generate_notification_system_script,
    generate_loading_screen_script,
    generate_ui_material_shaders,
)




# ---------------------------------------------------------------------------
# UI tool
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_ui(
    action: Literal[
        "generate_ui_screen",   # UI-05: UXML + USS from description
        "validate_layout",      # UI-02: check overlaps, zero-size, overflow
        "test_responsive",      # UI-03: capture at 5 resolutions
        "check_contrast",       # UI-06: WCAG AA contrast validation
        "compare_screenshots",  # UI-07: visual regression detection
        "create_procedural_frame",   # UIPOL-01: ornate dark fantasy UI frames
        "create_icon_pipeline",      # UIPOL-02: 3D icon render pipeline
        "create_cursor_system",      # UIPOL-03: context-sensitive cursors
        "create_tooltip_system",     # UIPOL-04: rich tooltips with comparison
        "create_radial_menu",        # UIPOL-05: radial ability/item wheel
        "create_notification_system", # UIPOL-06: toast notification system
        "create_loading_screen",     # UIPOL-07: loading screen with tips/lore
        "create_ui_shaders",         # UIPOL-08: material-based UI effect shaders
    ],
    # Screen generation params
    screen_spec: dict | None = None,
    theme: str = "dark_fantasy",
    screen_name: str = "default",
    # Validation params
    uxml_path: str = "",
    uss_path: str = "",
    uxml_content: str = "",
    uss_content: str = "",
    # Responsive test params
    resolutions: list[list[int]] | None = None,
    # Screenshot comparison params
    reference_path: str = "",
    current_path: str = "",
    diff_threshold: float = 0.01,
    # Procedural frame params (UIPOL-01)
    frame_name: str = "DarkFantasyFrame",
    frame_style: str = "gothic",
    border_width: int = 4,
    corner_style: str = "ornate",
    inner_glow: bool = True,
    rune_brand: str = "IRON",
    # Icon pipeline params (UIPOL-02)
    icon_size: int = 256,
    render_angle: str = "front_three_quarter",
    light_setup: str = "three_point",
    rarity_border: bool = True,
    background_gradient: bool = True,
    # Cursor system params (UIPOL-03)
    cursor_types: list[str] | None = None,
    detection_layers: str = "Default",
    cursor_size: int = 32,
    # Tooltip params (UIPOL-04)
    tooltip_style: str = "dark_fantasy",
    show_comparison: bool = True,
    show_lore: bool = True,
    fade_duration: float = 0.2,
    max_width: int = 350,
    # Radial menu params (UIPOL-05)
    segment_count: int = 8,
    menu_radius: float = 150.0,
    menu_type: str = "ability",
    trigger_key: str = "Tab",
    # Notification params (UIPOL-06)
    max_visible: int = 5,
    auto_dismiss_seconds: float = 4.0,
    toast_position: str = "top_right",
    toast_types: list[str] | None = None,
    # Loading screen params (UIPOL-07)
    show_tips: bool = True,
    show_loading_lore: bool = True,
    show_art: bool = True,
    progress_style: str = "bar",
    tip_interval: float = 5.0,
    # UI shader params (UIPOL-08)
    ui_shader_name: str = "VB_UIEffects",
    ui_effects: list[str] | None = None
) -> str:
    """Unity UI system -- UXML/USS generation, layout validation, WCAG contrast, responsive testing, visual regression, and dark fantasy UI polish."""
    try:
        if action == "generate_ui_screen":
            return await _handle_ui_generate_screen(screen_spec, theme, screen_name)
        elif action == "validate_layout":
            return await _handle_ui_validate_layout(uxml_path, uxml_content)
        elif action == "test_responsive":
            return await _handle_ui_test_responsive(
                uxml_path or f"Assets/Resources/UI/{screen_name}.uxml",
                screen_name,
                resolutions,
            )
        elif action == "check_contrast":
            return await _handle_ui_check_contrast(
                uxml_path, uss_path, uxml_content, uss_content
            )
        elif action == "compare_screenshots":
            return await _handle_ui_compare_screenshots(
                reference_path, current_path, diff_threshold
            )
        elif action == "create_procedural_frame":
            return await _handle_dict_template(
                "create_procedural_frame",
                generate_procedural_frame_script(
                    frame_name=frame_name, style=frame_style, border_width=border_width,
                    corner_style=corner_style, inner_glow=inner_glow, rune_brand=rune_brand,
                ),
            )
        elif action == "create_icon_pipeline":
            return await _handle_dict_template(
                "create_icon_pipeline",
                generate_icon_render_pipeline_script(
                    icon_size=icon_size, render_angle=render_angle, light_setup=light_setup,
                    rarity_border=rarity_border, background_gradient=background_gradient,
                ),
            )
        elif action == "create_cursor_system":
            return await _handle_dict_template(
                "create_cursor_system",
                generate_cursor_system_script(
                    cursor_types=cursor_types, detection_layers=detection_layers,
                    cursor_size=cursor_size,
                ),
            )
        elif action == "create_tooltip_system":
            return await _handle_dict_template(
                "create_tooltip_system",
                generate_tooltip_system_script(
                    tooltip_style=tooltip_style, show_comparison=show_comparison,
                    show_lore=show_lore, fade_duration=fade_duration, max_width=max_width,
                ),
            )
        elif action == "create_radial_menu":
            return await _handle_dict_template(
                "create_radial_menu",
                generate_radial_menu_script(
                    segment_count=segment_count, radius=menu_radius,
                    menu_type=menu_type, trigger_key=trigger_key,
                ),
            )
        elif action == "create_notification_system":
            return await _handle_dict_template(
                "create_notification_system",
                generate_notification_system_script(
                    max_visible=max_visible, auto_dismiss_seconds=auto_dismiss_seconds,
                    position=toast_position, toast_types=toast_types,
                ),
            )
        elif action == "create_loading_screen":
            return await _handle_dict_template(
                "create_loading_screen",
                generate_loading_screen_script(
                    show_tips=show_tips, show_lore=show_loading_lore, show_art=show_art,
                    progress_style=progress_style, tip_interval=tip_interval,
                ),
            )
        elif action == "create_ui_shaders":
            return await _handle_dict_template(
                "create_ui_shaders",
                generate_ui_material_shaders(
                    shader_name=ui_shader_name, effects=ui_effects,
                ),
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_ui action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# UI action handlers
# ---------------------------------------------------------------------------


async def _handle_ui_generate_screen(
    screen_spec: dict | None,
    theme: str,
    screen_name: str,
) -> str:
    """Generate UXML + USS from screen spec (UI-05)."""
    if not screen_spec:
        return json.dumps({
            "status": "error",
            "action": "generate_ui_screen",
            "message": "screen_spec is required for generate_ui_screen action",
        })

    uxml = generate_uxml_screen(screen_spec)
    uss = generate_uss_stylesheet(theme)

    uxml_rel = f"Assets/Resources/UI/{screen_name}.uxml"
    uss_rel = f"Assets/Resources/UI/{screen_name}.uss"

    try:
        uxml_abs = _write_to_unity(uxml, uxml_rel)
        uss_abs = _write_to_unity(uss, uss_rel)
    except ValueError as exc:
        return json.dumps({
            "status": "error",
            "action": "generate_ui_screen",
            "message": str(exc),
        })

    # Run validation on generated UXML
    body = uxml.split("\n", 1)[1] if "\n" in uxml else uxml
    layout_result = validate_uxml_layout(body)

    # Run contrast check on generated UXML + USS
    contrast_results = validate_uxml_contrast(body, uss)
    contrast_violations = [r for r in contrast_results if not r["passes"]]

    return json.dumps(
        {
            "status": "success",
            "action": "generate_ui_screen",
            "uxml_path": uxml_abs,
            "uss_path": uss_abs,
            "screen_name": screen_name,
            "theme": theme,
            "layout_valid": layout_result["valid"],
            "layout_issues": layout_result["issues"],
            "contrast_violations": contrast_violations,
            "next_steps": STANDARD_NEXT_STEPS,
        },
        indent=2,
    )


async def _handle_ui_validate_layout(uxml_path: str, uxml_content: str) -> str:
    """Validate UXML layout for issues (UI-02)."""
    content = uxml_content
    if not content and uxml_path:
        if settings.unity_project_path:
            full_path = Path(settings.unity_project_path) / uxml_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
            else:
                return json.dumps({
                    "status": "error",
                    "action": "validate_layout",
                    "message": f"UXML file not found: {full_path}",
                })
        else:
            return json.dumps({
                "status": "error",
                "action": "validate_layout",
                "message": "unity_project_path not configured and no uxml_content provided",
            })

    if not content:
        return json.dumps({
            "status": "error",
            "action": "validate_layout",
            "message": "No UXML content provided. Use uxml_path or uxml_content.",
        })

    result = validate_uxml_layout(content)

    return json.dumps(
        {
            "status": "success",
            "action": "validate_layout",
            "valid": result["valid"],
            "issues": result["issues"],
            "issue_count": len(result["issues"]),
        },
        indent=2,
    )


async def _handle_ui_test_responsive(
    uxml_path: str,
    screen_name: str,
    resolutions: list[list[int]] | None,
) -> str:
    """Generate responsive test C# script (UI-03)."""
    # Convert list-of-lists to list-of-tuples if provided
    res_tuples = None
    if resolutions:
        res_tuples = [(r[0], r[1]) for r in resolutions]

    script = generate_responsive_test_script(uxml_path, resolutions=res_tuples)
    script_rel = f"Assets/Editor/Generated/UI/ResponsiveTest_{screen_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_rel)
    except ValueError as exc:
        return json.dumps({
            "status": "error",
            "action": "test_responsive",
            "message": str(exc),
        })

    return json.dumps(
        {
            "status": "success",
            "action": "test_responsive",
            "script_path": abs_path,
            "screen_name": screen_name,
            "resolutions": resolutions or [[w, h] for w, h in [
                (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160), (800, 600)
            ]],
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_ui_check_contrast(
    uxml_path: str,
    uss_path: str,
    uxml_content: str,
    uss_content: str,
) -> str:
    """Validate WCAG AA contrast ratios (UI-06)."""
    uxml = uxml_content
    uss = uss_content

    # Read UXML from file if path provided and no inline content
    if not uxml and uxml_path and settings.unity_project_path:
        full = Path(settings.unity_project_path) / uxml_path
        if full.exists():
            uxml = full.read_text(encoding="utf-8")

    # Read USS from file if path provided and no inline content
    if not uss and uss_path and settings.unity_project_path:
        full = Path(settings.unity_project_path) / uss_path
        if full.exists():
            uss = full.read_text(encoding="utf-8")

    if not uxml or not uss:
        return json.dumps({
            "status": "error",
            "action": "check_contrast",
            "message": "Both UXML and USS content are required (via paths or inline content).",
        })

    results = validate_uxml_contrast(uxml, uss)
    passing = [r for r in results if r["passes"]]
    failing = [r for r in results if not r["passes"]]

    # Convert tuples to lists for JSON serialization
    for r in results:
        r["foreground"] = list(r["foreground"])
        r["background"] = list(r["background"])

    return json.dumps(
        {
            "status": "success",
            "action": "check_contrast",
            "total_checked": len(results),
            "passing": len(passing),
            "failing": len(failing),
            "wcag_aa_compliant": len(failing) == 0,
            "results": results,
        },
        indent=2,
    )


async def _handle_ui_compare_screenshots(
    reference_path: str,
    current_path: str,
    diff_threshold: float,
) -> str:
    """Compare screenshots for visual regression (UI-07)."""
    if not reference_path or not current_path:
        return json.dumps({
            "status": "error",
            "action": "compare_screenshots",
            "message": "Both reference_path and current_path are required.",
        })

    # Resolve paths relative to Unity project if needed
    ref = reference_path
    cur = current_path
    if settings.unity_project_path:
        ref_full = Path(settings.unity_project_path) / reference_path
        cur_full = Path(settings.unity_project_path) / current_path
        if ref_full.exists():
            ref = str(ref_full)
        if cur_full.exists():
            cur = str(cur_full)

    result = _compare_screenshots(ref, cur, threshold=diff_threshold)

    return json.dumps(
        {
            "status": "success",
            "action": "compare_screenshots",
            "match": result["match"],
            "diff_percentage": result["diff_percentage"],
            "diff_threshold": diff_threshold,
            "diff_image_path": result.get("diff_image_path"),
            "reference_size": list(result["reference_size"]),
            "current_size": list(result["current_size"]),
            "visual_regression_detected": not result["match"],
        },
        indent=2,
    )
