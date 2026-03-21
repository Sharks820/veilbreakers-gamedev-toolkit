"""unity_qa tool handler."""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, _read_unity_result, _handle_dict_template,
)

from veilbreakers_mcp.shared.unity_templates.qa_templates import (
    generate_bridge_server_script,
    generate_bridge_commands_script,
    generate_test_runner_handler,
    generate_play_session_script,
    generate_profiler_handler,
    generate_memory_leak_script,
    analyze_csharp_static,
    generate_crash_reporting_script,
    generate_analytics_script,
    generate_live_inspector_script,
)
from veilbreakers_mcp.shared.unity_templates.production_templates import (
    generate_compile_recovery_script,
    generate_conflict_detector_script,
    generate_pipeline_orchestrator_script,
    generate_pipeline_step_definitions,
    generate_art_style_validator_script,
    generate_build_smoke_test_script,
)
from veilbreakers_mcp.shared.unity_client import UnityConnection, UnityCommandError




@mcp.tool()
async def unity_qa(
    action: Literal[
        "setup_bridge",             # QA-00
        "run_tests",                # QA-01
        "run_play_session",         # QA-02
        "profile_scene",            # QA-03
        "detect_memory_leaks",      # QA-04
        "analyze_code",             # QA-05
        "setup_crash_reporting",    # QA-06
        "setup_analytics",          # QA-07
        "inspect_live_state",       # QA-08
        "check_compile_status",     # QA-09
        "compile_recovery",         # PROD-01: compile error auto-recovery
        "detect_conflicts",         # PROD-02: asset/class name conflict detection
        "orchestrate_pipeline",     # PROD-03: multi-tool pipeline orchestration
        "list_pipeline_steps",      # PROD-03b: list available pipeline step definitions
        "validate_art_style",       # PROD-04: art style consistency validation
        "build_smoke_test",         # PROD-05: post-build smoke test verification
    ],
    name: str = "default",
    # bridge params
    bridge_port: int = 9877,
    # test runner params
    test_mode: str = "EditMode",
    test_filter: str = "",
    timeout_seconds: int = 60,
    # play session params
    steps: list[dict] | None = None,
    timeout_per_step: float = 10.0,
    # profiler params
    target_frame_time_ms: float = 16.67,
    max_draw_calls: int = 2000,
    max_memory_mb: int = 1024,
    sample_frames: int = 60,
    # memory leak params
    growth_threshold_mb: int = 10,
    sample_interval_seconds: int = 5,
    sample_count: int = 10,
    # static analysis params
    source_code: str = "",
    source_file_path: str = "<unknown>",
    # crash reporting params
    dsn: str = "",
    environment: str = "development",
    enable_breadcrumbs: bool = True,
    sample_rate: float = 1.0,
    # analytics params
    event_names: list[str] | None = None,
    flush_interval_seconds: int = 30,
    max_buffer_size: int = 100,
    log_file_path: str = "Analytics/events.json",
    # live inspector params
    update_interval_frames: int = 10,
    max_tracked_objects: int = 20,
    # common
    namespace: str = "",
    # compile recovery params (PROD-01)
    auto_fix_enabled: bool = True,
    max_retries: int = 3,
    watch_assemblies: list[str] | None = None,
    recovery_log_path: str = "Temp/vb_compile_recovery.json",
    # conflict detector params (PROD-02)
    scan_paths: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
    namespace_prefix: str = "VeilBreakers",
    # pipeline orchestrator params (PROD-03)
    pipeline_name: str = "custom",
    pipeline_steps: list[dict] | None = None,
    on_failure: str = "stop",
    # art style validator params (PROD-04)
    palette_colors: list[dict] | None = None,
    roughness_range: list[float] | None = None,
    max_texel_density: float | None = None,
    naming_pattern: str | None = None,
    # build smoke test params (PROD-05)
    build_path: str = "Builds/VeilBreakers.exe",
    smoke_timeout_seconds: int = 30,
    scene_to_load: str = "",
    expected_fps_min: int = 10,
) -> str:
    """Unity Quality Assurance & Testing tools -- bridge, test runner, profiler,
    memory leak detection, static analysis, crash reporting, analytics, live
    inspector, compile recovery, conflict detection, pipeline orchestration,
    art style validation, and build smoke tests.

    Bridge & Infrastructure (qa_templates.py):
    - setup_bridge: TCP bridge server + command dispatch for Unity Editor automation (QA-00)

    Testing & Profiling (qa_templates.py):
    - run_tests: TestRunnerApi-based EditMode/PlayMode test execution with JSON results (QA-01)
    - run_play_session: Automated play session with sequential steps and verification (QA-02)
    - profile_scene: GPU/CPU profiler with budget comparison via ProfilerRecorder (QA-03)
    - detect_memory_leaks: Managed/native memory leak detection over sampled intervals (QA-04)
    - analyze_code: Python-side regex static analysis for Unity performance anti-patterns (QA-05)

    Observability (qa_templates.py):
    - setup_crash_reporting: Sentry SDK initialization with breadcrumbs and environment tagging (QA-06)
    - setup_analytics: Singleton analytics manager with event buffering and JSON logging (QA-07)
    - inspect_live_state: IMGUI EditorWindow for live GameObject field inspection (QA-08)

    Compile Status:
    - check_compile_status: Query Unity bridge to detect compile errors after script writes (QA-09)

    Production Pipeline (production_templates.py):
    - compile_recovery: Compile error auto-detection and recovery (PROD-01)
    - detect_conflicts: Pre-write asset/class name conflict scanning (PROD-02)
    - orchestrate_pipeline: Multi-step pipeline orchestration with status tracking (PROD-03)
    - list_pipeline_steps: List available built-in pipeline step definitions (PROD-03b)
    - validate_art_style: Art style consistency validation (palette, roughness, naming) (PROD-04)
    - build_smoke_test: Post-build smoke test verification (PROD-05)

    Args:
        action: The QA action to perform.
        name: Name for the generated system (used in file paths).
        bridge_port: TCP port for VBBridge server (default 9877).
        test_mode: Test runner mode -- EditMode, PlayMode, or Both.
        test_filter: Optional test name filter substring.
        timeout_seconds: Test runner timeout in seconds.
        steps: Play session step definitions (list of dicts with action/params).
        timeout_per_step: Play session per-step timeout in seconds.
        target_frame_time_ms: Profiler target frame time budget in milliseconds.
        max_draw_calls: Profiler maximum draw call budget.
        max_memory_mb: Profiler maximum memory budget in MB.
        sample_frames: Profiler number of frames to sample.
        growth_threshold_mb: Memory leak growth threshold in MB.
        sample_interval_seconds: Memory leak sampling interval in seconds.
        sample_count: Memory leak number of samples to collect.
        source_code: C# source code string for static analysis.
        source_file_path: File path metadata for static analysis reports.
        dsn: Sentry DSN URL for crash reporting (empty = console fallback).
        environment: Sentry environment tag (development/staging/production).
        enable_breadcrumbs: Enable Sentry breadcrumb tracking.
        sample_rate: Sentry event sample rate (0.0 to 1.0).
        event_names: Analytics event names for typed convenience methods.
        flush_interval_seconds: Analytics event buffer flush interval.
        max_buffer_size: Analytics event buffer max size before auto-flush.
        log_file_path: Analytics JSON log file path relative to persistentDataPath.
        update_interval_frames: Live inspector refresh interval in frames.
        max_tracked_objects: Live inspector max pinned objects.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "setup_bridge":
            server_script = generate_bridge_server_script(
                port=bridge_port, **ns_kwargs,
            )
            commands_script = generate_bridge_commands_script(**ns_kwargs)
            server_path = _write_to_unity(
                server_script, "Assets/Editor/VBBridge/VBBridgeServer.cs",
            )
            commands_path = _write_to_unity(
                commands_script, "Assets/Editor/VBBridge/VBBridgeCommands.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_bridge",
                "paths": [server_path, commands_path],
                "next_steps": [
                    "Recompile scripts in Unity (AssetDatabase.Refresh)",
                    f"Verify VBBridge is listening on port {bridge_port} in Unity Console",
                ],
            }, indent=2)

        elif action == "run_tests":
            script = generate_test_runner_handler(
                test_mode=test_mode,
                test_filter=test_filter,
                timeout_seconds=timeout_seconds,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBTestRunner.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "run_tests",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile test runner",
                    "Execute menu item: VeilBreakers > QA > Run Tests",
                    "Read results from Temp/vb_test_results.json",
                ],
            }, indent=2)

        elif action == "run_play_session":
            script = generate_play_session_script(
                steps=steps,
                timeout_per_step=timeout_per_step,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBPlaySession.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "run_play_session",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile play session",
                    "Execute menu item: VeilBreakers > QA > Run Play Session",
                ],
            }, indent=2)

        elif action == "profile_scene":
            script = generate_profiler_handler(
                target_frame_time_ms=target_frame_time_ms,
                max_draw_calls=max_draw_calls,
                max_memory_mb=max_memory_mb,
                sample_frames=sample_frames,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBProfiler.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "profile_scene",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile profiler",
                    "Execute menu item: VeilBreakers > QA > Profile Scene",
                    "Read results from Temp/vb_profiler_results.json",
                ],
            }, indent=2)

        elif action == "detect_memory_leaks":
            script = generate_memory_leak_script(
                growth_threshold_mb=growth_threshold_mb,
                sample_interval_seconds=sample_interval_seconds,
                sample_count=sample_count,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBMemoryLeakDetector.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "detect_memory_leaks",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile leak detector",
                    "Enter Play Mode",
                    "Execute menu item: VeilBreakers > QA > Detect Memory Leaks",
                ],
            }, indent=2)

        elif action == "analyze_code":
            if not source_code:
                return json.dumps({
                    "status": "error",
                    "action": "analyze_code",
                    "message": "source_code parameter is required for static analysis",
                })
            result = analyze_csharp_static(source_code, source_file_path)
            report_lines = [
                f"Static Analysis: {result['file_path']}",
                f"Findings: {result['findings_count']}",
                "",
            ]
            for finding in result.get("findings", []):
                severity = finding.get("severity", "info")
                line = finding.get("line_number", finding.get("line", "?"))
                message = finding.get("message", "")
                fix = finding.get("fix", "")
                report_lines.append(
                    f"  [{severity.upper()}] Line {line}: {message}"
                )
                if fix:
                    report_lines.append(f"    Fix: {fix}")
            return json.dumps({
                "status": "success",
                "action": "analyze_code",
                "file_path": result["file_path"],
                "findings_count": result["findings_count"],
                "findings": result.get("findings", []),
                "report": "\n".join(report_lines),
            }, indent=2)

        elif action == "setup_crash_reporting":
            script = generate_crash_reporting_script(
                dsn=dsn,
                environment=environment,
                enable_breadcrumbs=enable_breadcrumbs,
                sample_rate=sample_rate,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Scripts/Generated/QA/VBCrashReporting.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_crash_reporting",
                "script_path": abs_path,
                "next_steps": [
                    "Install Sentry Unity SDK: add 'io.sentry.unity' via UPM",
                    "Set DSN in script or via Sentry dashboard",
                    "Call unity_editor action='recompile' to compile crash reporting",
                ],
            }, indent=2)

        elif action == "setup_analytics":
            # Validate log_file_path to prevent directory traversal

            if (log_file_path.startswith("/") or log_file_path.startswith("\\")
                    or ".." in log_file_path
                    or ":" in log_file_path):
                return json.dumps({
                    "status": "error",
                    "action": "setup_analytics",
                    "message": (
                        "log_file_path must be a relative path without "
                        "'..', leading '/' or '\\\\', or drive letters"
                    ),
                })
            script = generate_analytics_script(
                event_names=event_names,
                flush_interval_seconds=flush_interval_seconds,
                max_buffer_size=max_buffer_size,
                log_file_path=log_file_path,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Scripts/Generated/QA/VBAnalytics.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_analytics",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile analytics",
                    "Add VBAnalytics prefab to scene",
                    f"Events logged to Application.persistentDataPath/{log_file_path}",
                ],
            }, indent=2)

        elif action == "inspect_live_state":
            script = generate_live_inspector_script(
                update_interval_frames=update_interval_frames,
                max_tracked_objects=max_tracked_objects,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBLiveInspector.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "inspect_live_state",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile live inspector",
                    "Open via VeilBreakers > QA > Live Inspector",
                    "Enter Play Mode to see live values",
                ],
            }, indent=2)

        elif action == "check_compile_status":
            return await _handle_check_compile_status(bridge_port)

        elif action == "compile_recovery":
            return await _handle_dict_template(
                "compile_recovery",
                generate_compile_recovery_script(
                    auto_fix_enabled=auto_fix_enabled, max_retries=max_retries,
                    watch_assemblies=watch_assemblies, log_path=recovery_log_path,
                ),
            )
        elif action == "detect_conflicts":
            return await _handle_dict_template(
                "detect_conflicts",
                generate_conflict_detector_script(
                    scan_paths=scan_paths, ignore_patterns=ignore_patterns,
                    namespace_prefix=namespace_prefix,
                ),
            )
        elif action == "orchestrate_pipeline":
            return await _handle_dict_template(
                "orchestrate_pipeline",
                generate_pipeline_orchestrator_script(
                    pipeline_name=pipeline_name, steps=pipeline_steps,
                    on_failure=on_failure,
                ),
            )
        elif action == "list_pipeline_steps":
            result = generate_pipeline_step_definitions()
            return json.dumps({
                "status": "success",
                "action": "list_pipeline_steps",
                **result,
            }, indent=2)
        elif action == "validate_art_style":
            roughness_tuple = tuple(roughness_range) if roughness_range and len(roughness_range) == 2 else None
            return await _handle_dict_template(
                "validate_art_style",
                generate_art_style_validator_script(
                    palette_colors=palette_colors, roughness_range=roughness_tuple,
                    max_texel_density=max_texel_density, naming_pattern=naming_pattern,
                ),
            )
        elif action == "build_smoke_test":
            return await _handle_dict_template(
                "build_smoke_test",
                generate_build_smoke_test_script(
                    build_path=build_path, timeout_seconds=smoke_timeout_seconds,
                    scene_to_load=scene_to_load, expected_fps_min=expected_fps_min,
                ),
            )

        else:
            return json.dumps({
                "status": "error",
                "message": f"Unknown action: {action}",
            })

    except Exception as exc:
        logger.exception("unity_qa action '%s' failed", action)
        return json.dumps({
            "status": "error",
            "action": action,
            "message": str(exc),
        })
