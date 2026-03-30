"""unity_performance tool handler."""

import json
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, logger,
    _write_to_unity, STANDARD_NEXT_STEPS,
)

from veilbreakers_mcp.shared.unity_templates.performance_templates import (
    generate_scene_profiler_script,
    generate_lod_setup_script,
    generate_lightmap_bake_script,
    generate_asset_audit_script,
    generate_build_automation_script,
    _validate_lod_screen_percentages,
)




# ---------------------------------------------------------------------------
# Performance tool -- compound tool covering PERF-01 through PERF-05
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_performance(
    action: Literal[
        "profile_scene",        # PERF-01: frame time, draw calls, memory
        "setup_lod_groups",     # PERF-02: auto-generate LODGroups
        "bake_lightmaps",      # PERF-03: async lightmap baking
        "audit_assets",        # PERF-04: find oversized/unused/uncompressed
        "automate_build",      # PERF-05: build + size report
    ],
    # Profiler budgets (PERF-01)
    target_frame_time_ms: float = 16.67,
    max_draw_calls: int = 2000,
    max_batches: int = 1000,
    max_triangles: int = 2000000,
    max_memory_mb: float = 2048.0,
    # LOD params (PERF-02)
    lod_count: int = 3,
    screen_percentages: list[float] | None = None,
    # Lightmap params (PERF-03)
    lightmap_quality: str = "medium",
    bounces: int = 2,
    lightmap_resolution: int = 32,
    # Asset audit params (PERF-04)
    max_texture_size: int = 2048,
    allowed_audio_formats: list[str] | None = None,
    # Build params (PERF-05)
    build_target: str = "StandaloneWindows64",
    scenes: list[str] | None = None,
    build_options: str = "None"
) -> str:
    """Unity Performance -- scene profiling, LOD setup, lightmap baking, asset audit, build automation."""
    try:
        if action == "profile_scene":
            return await _handle_performance_profile_scene(
                target_frame_time_ms, max_draw_calls, max_batches, max_triangles, max_memory_mb,
            )
        elif action == "setup_lod_groups":
            return await _handle_performance_setup_lod_groups(
                lod_count, screen_percentages,
            )
        elif action == "bake_lightmaps":
            return await _handle_performance_bake_lightmaps(
                lightmap_quality, bounces, lightmap_resolution,
            )
        elif action == "audit_assets":
            return await _handle_performance_audit_assets(
                max_texture_size, allowed_audio_formats,
            )
        elif action == "automate_build":
            return await _handle_performance_automate_build(
                build_target, scenes, build_options,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_performance action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Performance action handlers
# ---------------------------------------------------------------------------


async def _handle_performance_profile_scene(
    target_frame_time_ms: float,
    max_draw_calls: int,
    max_batches: int,
    max_triangles: int,
    max_memory_mb: float,
) -> str:
    """Generate scene profiler editor script (PERF-01)."""
    budgets = {
        "frame_time": target_frame_time_ms,
        "draw_calls": max_draw_calls,
        "batches": max_batches,
        "triangles": max_triangles,
        "memory_mb": max_memory_mb,
    }
    script = generate_scene_profiler_script(budgets=budgets)
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_SceneProfiler.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "profile_scene", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "profile_scene",
            "script_path": abs_path,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_setup_lod_groups(
    lod_count: int,
    screen_percentages: list[float] | None,
) -> str:
    """Generate LODGroup setup editor script (PERF-02)."""
    pcts = screen_percentages or [0.6, 0.3, 0.15][:lod_count]

    if not _validate_lod_screen_percentages(pcts):
        return json.dumps({
            "status": "error",
            "action": "setup_lod_groups",
            "message": f"screen_percentages must be strictly descending and all > 0, got: {pcts}",
        })

    script = generate_lod_setup_script(lod_count=lod_count, screen_percentages=pcts)
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_LODSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_lod_groups", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_lod_groups",
            "script_path": abs_path,
            "lod_count": len(pcts),
            "screen_percentages": pcts,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_bake_lightmaps(
    lightmap_quality: str,
    bounces: int,
    lightmap_resolution: int,
) -> str:
    """Generate lightmap bake editor script (PERF-03)."""
    script = generate_lightmap_bake_script(
        quality=lightmap_quality,
        bounces=bounces,
        resolution=lightmap_resolution,
    )
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_LightmapBaker.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "bake_lightmaps", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "bake_lightmaps",
            "script_path": abs_path,
            "quality": lightmap_quality,
            "bounces": bounces,
            "resolution": lightmap_resolution,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_audit_assets(
    max_texture_size: int,
    allowed_audio_formats: list[str] | None,
) -> str:
    """Generate asset audit editor script (PERF-04)."""
    formats = allowed_audio_formats or ["Vorbis", "AAC"]
    script = generate_asset_audit_script(
        max_texture_size=max_texture_size,
        allowed_audio_formats=formats,
    )
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_AssetAudit.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "audit_assets", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "audit_assets",
            "script_path": abs_path,
            "max_texture_size": max_texture_size,
            "allowed_audio_formats": formats,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_automate_build(
    build_target: str,
    scenes: list[str] | None,
    build_options: str,
) -> str:
    """Generate build automation editor script (PERF-05)."""
    scene_list = scenes or []
    script = generate_build_automation_script(
        target=build_target,
        scenes=scene_list if scene_list else None,
        options=build_options,
    )
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_BuildAutomation.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "automate_build", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "automate_build",
            "script_path": abs_path,
            "build_target": build_target,
            "build_options": build_options,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )
