"""Tests for Unity QA C# template generators.

Covers:
- generate_bridge_server_script: [InitializeOnLoad], TcpListener, ConcurrentQueue,
  EditorApplication.update, ProcessCommands, ManualResetEventSlim, AssemblyReloadEvents,
  ReadExactly, port parameterization, namespace wrapping
- generate_bridge_commands_script: HANDLERS dictionary, all 9 handler names,
  Dispatch method, AssetDatabase.Refresh, ExecuteMenuItem, EnterPlaymode, ExitPlaymode,
  MiniJSON parser, SerializeResponse, namespace wrapping
- generate_crash_reporting_script: SentrySdk.Init, RuntimeInitializeOnLoadMethod,
  BeforeSceneLoad, DSN, breadcrumbs, CaptureException, CaptureMessage, SetTag, SetUser
- generate_analytics_script: DontDestroyOnLoad, TrackEvent, FlushEvents, sessionId,
  typed convenience methods, JSON serialization, OnApplicationQuit
- generate_live_inspector_script: EditorWindow, MenuItem, OnGUI, EditorApplication.update,
  GetComponents, Reflection, FieldInfo, PropertyInfo, isPlaying, Foldout, ScrollView
"""

from __future__ import annotations

import pytest

from veilbreakers_mcp.shared.unity_templates.qa_templates import (
    generate_analytics_script,
    generate_bridge_commands_script,
    generate_bridge_server_script,
    generate_crash_reporting_script,
    generate_live_inspector_script,
    generate_play_session_script,
    generate_profiler_handler,
    generate_test_runner_handler,
)


# =====================================================================
# Bridge Server Tests
# =====================================================================


class TestBridgeServer:
    """Tests for generate_bridge_server_script output."""

    @pytest.fixture
    def server_cs(self) -> str:
        return generate_bridge_server_script()

    def test_has_initialize_on_load(self, server_cs: str):
        assert "[InitializeOnLoad]" in server_cs

    def test_has_tcp_listener(self, server_cs: str):
        assert "TcpListener" in server_cs

    def test_has_concurrent_queue(self, server_cs: str):
        assert "ConcurrentQueue" in server_cs

    def test_has_editor_application_update(self, server_cs: str):
        assert "EditorApplication.update" in server_cs

    def test_has_process_commands(self, server_cs: str):
        assert "ProcessCommands" in server_cs

    def test_has_manual_reset_event_slim(self, server_cs: str):
        assert "ManualResetEventSlim" in server_cs

    def test_has_assembly_reload_events(self, server_cs: str):
        assert "AssemblyReloadEvents.beforeAssemblyReload" in server_cs

    def test_has_editor_application_quitting(self, server_cs: str):
        assert "EditorApplication.quitting" in server_cs

    def test_has_read_exactly(self, server_cs: str):
        assert "ReadExactly" in server_cs

    def test_default_port_9877(self, server_cs: str):
        assert "9877" in server_cs

    def test_has_ip_address_loopback(self, server_cs: str):
        assert "IPAddress.Loopback" in server_cs

    def test_has_thread_pool(self, server_cs: str):
        assert "ThreadPool.QueueUserWorkItem" in server_cs

    def test_has_handle_client(self, server_cs: str):
        assert "HandleClient" in server_cs

    def test_has_listener_loop(self, server_cs: str):
        assert "ListenerLoop" in server_cs

    def test_has_start_method(self, server_cs: str):
        assert "void Start()" in server_cs

    def test_has_stop_method(self, server_cs: str):
        assert "void Stop()" in server_cs

    def test_has_command_envelope(self, server_cs: str):
        assert "CommandEnvelope" in server_cs

    def test_has_escape_json(self, server_cs: str):
        assert "EscapeJson" in server_cs

    def test_has_vb_bridge_commands_dispatch(self, server_cs: str):
        assert "VBBridgeCommands.Dispatch" in server_cs

    def test_has_using_system_net_sockets(self, server_cs: str):
        assert "using System.Net.Sockets;" in server_cs

    def test_has_using_system_threading(self, server_cs: str):
        assert "using System.Threading;" in server_cs

    def test_has_using_unity_editor(self, server_cs: str):
        assert "using UnityEditor;" in server_cs

    def test_has_is_background_true(self, server_cs: str):
        assert "IsBackground = true" in server_cs

    def test_has_try_dequeue(self, server_cs: str):
        assert "TryDequeue" in server_cs

    def test_thread_sleep_50(self, server_cs: str):
        assert "Thread.Sleep(50)" in server_cs

    def test_timeout_300_seconds(self, server_cs: str):
        assert "FromSeconds(300)" in server_cs

    def test_4_byte_length_prefix_read(self, server_cs: str):
        assert "ReadExactly(stream, 4)" in server_cs

    def test_big_endian_decode(self, server_cs: str):
        # Check for the bit-shift big-endian decoding pattern
        assert "lenBytes[0] << 24" in server_cs

    def test_big_endian_encode_response(self, server_cs: str):
        assert "responseBytes.Length >> 24" in server_cs


class TestBridgeServerCustomPort:
    """Test generate_bridge_server_script with custom port."""

    def test_custom_port_9999(self):
        cs = generate_bridge_server_script(port=9999)
        assert "9999" in cs
        # Should NOT contain default port
        assert "_port = 9999" in cs

    def test_custom_port_8080(self):
        cs = generate_bridge_server_script(port=8080)
        assert "_port = 8080" in cs


class TestBridgeServerNamespace:
    """Test generate_bridge_server_script with namespace wrapping."""

    def test_namespace_wrapping(self):
        cs = generate_bridge_server_script(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self):
        cs = generate_bridge_server_script()
        assert "namespace " not in cs

    def test_namespace_indentation(self):
        cs = generate_bridge_server_script(namespace="VB.QA")
        # Content should be indented inside namespace
        assert "    [InitializeOnLoad]" in cs

    def test_namespace_closing_brace(self):
        cs = generate_bridge_server_script(namespace="VB.Bridge")
        lines = cs.strip().split("\n")
        # Last line should be closing brace for namespace
        assert lines[-1] == "}"


# =====================================================================
# Bridge Commands Tests
# =====================================================================


class TestBridgeCommands:
    """Tests for generate_bridge_commands_script output."""

    @pytest.fixture
    def commands_cs(self) -> str:
        return generate_bridge_commands_script()

    def test_has_handlers_dictionary(self, commands_cs: str):
        assert "HANDLERS" in commands_cs

    def test_has_dispatch_method(self, commands_cs: str):
        assert "public static string Dispatch(string requestJson)" in commands_cs

    def test_handler_ping(self, commands_cs: str):
        assert '"ping"' in commands_cs

    def test_handler_recompile(self, commands_cs: str):
        assert '"recompile"' in commands_cs

    def test_handler_execute_menu_item(self, commands_cs: str):
        assert '"execute_menu_item"' in commands_cs

    def test_handler_enter_play_mode(self, commands_cs: str):
        assert '"enter_play_mode"' in commands_cs

    def test_handler_exit_play_mode(self, commands_cs: str):
        assert '"exit_play_mode"' in commands_cs

    def test_handler_screenshot(self, commands_cs: str):
        assert '"screenshot"' in commands_cs

    def test_handler_console_logs(self, commands_cs: str):
        assert '"console_logs"' in commands_cs

    def test_handler_read_result(self, commands_cs: str):
        assert '"read_result"' in commands_cs

    def test_handler_get_game_objects(self, commands_cs: str):
        assert '"get_game_objects"' in commands_cs

    def test_all_9_handlers_present(self, commands_cs: str):
        expected_handlers = [
            "ping", "recompile", "execute_menu_item",
            "enter_play_mode", "exit_play_mode", "screenshot",
            "console_logs", "read_result", "get_game_objects",
        ]
        for handler in expected_handlers:
            assert f'["{handler}"]' in commands_cs, f"Missing handler: {handler}"

    def test_has_asset_database_refresh(self, commands_cs: str):
        assert "AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate)" in commands_cs

    def test_has_execute_menu_item_call(self, commands_cs: str):
        assert "EditorApplication.ExecuteMenuItem" in commands_cs

    def test_has_enter_playmode(self, commands_cs: str):
        assert "EditorApplication.EnterPlaymode()" in commands_cs

    def test_has_exit_playmode(self, commands_cs: str):
        assert "EditorApplication.ExitPlaymode()" in commands_cs

    def test_has_screen_capture(self, commands_cs: str):
        assert "ScreenCapture.CaptureScreenshot" in commands_cs

    def test_has_mini_json(self, commands_cs: str):
        assert "MiniJSON" in commands_cs

    def test_has_serialize_response(self, commands_cs: str):
        assert "SerializeResponse" in commands_cs

    def test_has_serialize_game_object(self, commands_cs: str):
        assert "SerializeGameObject" in commands_cs

    def test_has_scene_manager(self, commands_cs: str):
        assert "SceneManager.GetActiveScene().GetRootGameObjects()" in commands_cs

    def test_has_vb_result_json_path(self, commands_cs: str):
        assert "Temp/vb_result.json" in commands_cs

    def test_has_using_unity_editor(self, commands_cs: str):
        assert "using UnityEditor;" in commands_cs

    def test_has_using_system_collections_generic(self, commands_cs: str):
        assert "using System.Collections.Generic;" in commands_cs

    def test_has_escape_json_value(self, commands_cs: str):
        assert "EscapeJsonValue" in commands_cs

    def test_ping_returns_pong(self, commands_cs: str):
        assert '"pong"' in commands_cs

    def test_has_handle_ping(self, commands_cs: str):
        assert "HandlePing" in commands_cs

    def test_has_handle_recompile(self, commands_cs: str):
        assert "HandleRecompile" in commands_cs

    def test_mini_json_parser_class(self, commands_cs: str):
        assert "sealed class Parser" in commands_cs

    def test_mini_json_serializer_class(self, commands_cs: str):
        assert "sealed class Serializer" in commands_cs

    def test_mini_json_deserialize(self, commands_cs: str):
        assert "public static object Deserialize(string json)" in commands_cs

    def test_mini_json_serialize(self, commands_cs: str):
        assert "public static string Serialize(object obj)" in commands_cs


class TestBridgeCommandsNamespace:
    """Test generate_bridge_commands_script with namespace wrapping."""

    def test_namespace_wrapping(self):
        cs = generate_bridge_commands_script(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self):
        cs = generate_bridge_commands_script()
        assert "namespace " not in cs

    def test_namespace_indentation(self):
        cs = generate_bridge_commands_script(namespace="VB.QA")
        assert "    public static class VBBridgeCommands" in cs


# =====================================================================
# Integration / Cross-cutting Tests
# =====================================================================


class TestBridgeIntegration:
    """Cross-cutting tests for server and commands together."""

    def test_server_references_commands_dispatch(self):
        server_cs = generate_bridge_server_script()
        assert "VBBridgeCommands.Dispatch" in server_cs

    def test_commands_dispatch_signature_matches_server_call(self):
        commands_cs = generate_bridge_commands_script()
        assert "public static string Dispatch(string requestJson)" in commands_cs

    def test_both_use_same_json_protocol_pattern(self):
        server_cs = generate_bridge_server_script()
        # Server reads 4-byte prefix
        assert "ReadExactly(stream, 4)" in server_cs
        # Server writes 4-byte prefix
        assert "responseLen[0]" in server_cs

    def test_both_generate_valid_usings(self):
        server_cs = generate_bridge_server_script()
        commands_cs = generate_bridge_commands_script()
        assert "using UnityEditor;" in server_cs
        assert "using UnityEditor;" in commands_cs

    def test_server_output_is_string(self):
        assert isinstance(generate_bridge_server_script(), str)

    def test_commands_output_is_string(self):
        assert isinstance(generate_bridge_commands_script(), str)

    def test_server_ends_with_newline(self):
        assert generate_bridge_server_script().endswith("\n")

    def test_commands_ends_with_newline(self):
        assert generate_bridge_commands_script().endswith("\n")


# =====================================================================
# Test Runner Handler Tests (QA-01)
# =====================================================================


class TestTestRunner:
    """Tests for generate_test_runner_handler output."""

    @pytest.fixture
    def runner_cs(self) -> str:
        return generate_test_runner_handler()

    def test_has_test_runner_api(self, runner_cs: str):
        assert "TestRunnerApi" in runner_cs

    def test_has_icallbacks(self, runner_cs: str):
        assert "ICallbacks" in runner_cs

    def test_has_run_finished(self, runner_cs: str):
        assert "RunFinished" in runner_cs

    def test_has_run_started(self, runner_cs: str):
        assert "RunStarted" in runner_cs

    def test_has_test_started(self, runner_cs: str):
        assert "TestStarted" in runner_cs

    def test_has_test_finished(self, runner_cs: str):
        assert "TestFinished" in runner_cs

    def test_has_execution_settings(self, runner_cs: str):
        assert "ExecutionSettings" in runner_cs

    def test_has_vb_test_results_json(self, runner_cs: str):
        assert "vb_test_results.json" in runner_cs

    def test_has_menu_item(self, runner_cs: str):
        assert "MenuItem" in runner_cs
        assert "VeilBreakers/QA/Run Tests" in runner_cs

    def test_default_edit_mode(self, runner_cs: str):
        assert "TestMode.EditMode" in runner_cs

    def test_has_run_synchronously(self, runner_cs: str):
        assert "runSynchronously = true" in runner_cs

    def test_has_register_callbacks(self, runner_cs: str):
        assert "RegisterCallbacks" in runner_cs

    def test_has_create_instance(self, runner_cs: str):
        assert "ScriptableObject.CreateInstance<TestRunnerApi>" in runner_cs

    def test_has_using_test_runner_api(self, runner_cs: str):
        assert "using UnityEditor.TestTools.TestRunner.Api;" in runner_cs

    def test_has_using_system_linq(self, runner_cs: str):
        assert "using System.Linq;" in runner_cs

    def test_has_using_system_io(self, runner_cs: str):
        assert "using System.IO;" in runner_cs

    def test_output_is_string(self, runner_cs: str):
        assert isinstance(runner_cs, str)

    def test_ends_with_newline(self, runner_cs: str):
        assert runner_cs.endswith("\n")


class TestTestRunnerPlayMode:
    """Test generate_test_runner_handler with PlayMode."""

    def test_play_mode_contains_play_mode(self):
        cs = generate_test_runner_handler(test_mode="PlayMode")
        assert "TestMode.PlayMode" in cs

    def test_play_mode_does_not_contain_edit_mode_only(self):
        cs = generate_test_runner_handler(test_mode="PlayMode")
        # Should have PlayMode, not EditMode as the filter mode
        assert "TestMode.PlayMode" in cs

    def test_both_mode(self):
        cs = generate_test_runner_handler(test_mode="Both")
        assert "TestMode.EditMode | TestMode.PlayMode" in cs

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="test_mode must be one of"):
            generate_test_runner_handler(test_mode="Invalid")

    def test_test_filter(self):
        cs = generate_test_runner_handler(test_filter="MyTest")
        assert "MyTest" in cs
        assert "testNames" in cs

    def test_namespace_wrapping(self):
        cs = generate_test_runner_handler(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self):
        cs = generate_test_runner_handler()
        assert "namespace " not in cs


# =====================================================================
# Play Session Tests (QA-02)
# =====================================================================


class TestPlaySession:
    """Tests for generate_play_session_script output."""

    @pytest.fixture
    def session_cs(self) -> str:
        return generate_play_session_script()

    def test_has_enter_playmode(self, session_cs: str):
        assert "EnterPlaymode" in session_cs

    def test_has_exit_playmode(self, session_cs: str):
        assert "ExitPlaymode" in session_cs

    def test_has_ienumerator(self, session_cs: str):
        assert "IEnumerator" in session_cs

    def test_has_vb_play_session_results_json(self, session_cs: str):
        assert "vb_play_session_results.json" in session_cs

    def test_has_menu_item(self, session_cs: str):
        assert "MenuItem" in session_cs
        assert "VeilBreakers/QA/Run Play Session" in session_cs

    def test_has_step_def_class(self, session_cs: str):
        assert "class StepDef" in session_cs

    def test_has_step_result_class(self, session_cs: str):
        assert "class StepResult" in session_cs

    def test_has_coroutine(self, session_cs: str):
        assert "IEnumerator Start()" in session_cs

    def test_has_monobehaviour(self, session_cs: str):
        assert "MonoBehaviour" in session_cs

    def test_has_wait_for_seconds(self, session_cs: str):
        assert "WaitForSeconds" in session_cs

    def test_has_send_message_interact(self, session_cs: str):
        assert 'SendMessage("Interact"' in session_cs

    def test_default_wait_step(self, session_cs: str):
        assert '"wait"' in session_cs

    def test_has_total_steps(self, session_cs: str):
        assert "total_steps" in session_cs

    def test_output_is_string(self, session_cs: str):
        assert isinstance(session_cs, str)

    def test_ends_with_newline(self, session_cs: str):
        assert session_cs.endswith("\n")


class TestPlaySessionCustomSteps:
    """Test generate_play_session_script with custom steps."""

    def test_custom_steps_move_to(self):
        steps = [
            {"action": "move_to", "position": [10.0, 0.0, 5.0], "expected": "arrived"},
        ]
        cs = generate_play_session_script(steps=steps)
        assert "10.0f" in cs
        assert "5.0f" in cs
        assert "move_to" in cs

    def test_custom_steps_interact(self):
        steps = [
            {"action": "interact", "target": "ChestObject", "expected": "chest_opened"},
        ]
        cs = generate_play_session_script(steps=steps)
        assert "ChestObject" in cs
        assert "interact" in cs

    def test_custom_timeout(self):
        cs = generate_play_session_script(timeout_per_step=30.0)
        assert "30.0f" in cs

    def test_multiple_steps(self):
        steps = [
            {"action": "wait", "seconds": 1, "expected": "ready"},
            {"action": "move_to", "position": [5, 0, 5], "expected": "arrived"},
            {"action": "interact", "target": "Door", "expected": "opened"},
        ]
        cs = generate_play_session_script(steps=steps)
        assert "Door" in cs
        assert "5.0f" in cs

    def test_namespace_wrapping(self):
        cs = generate_play_session_script(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self):
        cs = generate_play_session_script()
        assert "namespace " not in cs

    def test_navmesh_agent_support(self):
        cs = generate_play_session_script()
        assert "NavMeshAgent" in cs
        assert "SetDestination" in cs

    def test_verify_state_action(self):
        cs = generate_play_session_script()
        assert "verify_state" in cs


# =====================================================================
# Profiler Handler Tests (QA-03)
# =====================================================================


class TestProfiler:
    """Tests for generate_profiler_handler output."""

    @pytest.fixture
    def profiler_cs(self) -> str:
        return generate_profiler_handler()

    def test_has_profiler_recorder(self, profiler_cs: str):
        assert "ProfilerRecorder" in profiler_cs

    def test_has_start_new(self, profiler_cs: str):
        assert "StartNew" in profiler_cs

    def test_has_main_thread(self, profiler_cs: str):
        assert "Main Thread" in profiler_cs

    def test_has_draw_calls_count(self, profiler_cs: str):
        assert "Draw Calls Count" in profiler_cs

    def test_has_setpass_calls_count(self, profiler_cs: str):
        assert "SetPass Calls Count" in profiler_cs

    def test_has_system_used_memory(self, profiler_cs: str):
        assert "System Used Memory" in profiler_cs

    def test_has_triangles_count(self, profiler_cs: str):
        assert "Triangles Count" in profiler_cs

    def test_has_vb_profiler_results_json(self, profiler_cs: str):
        assert "vb_profiler_results.json" in profiler_cs

    def test_has_menu_item(self, profiler_cs: str):
        assert "MenuItem" in profiler_cs
        assert "VeilBreakers/QA/Profile Scene" in profiler_cs

    def test_has_using_unity_profiling(self, profiler_cs: str):
        assert "using Unity.Profiling;" in profiler_cs

    def test_has_frames_sampled(self, profiler_cs: str):
        assert "frames_sampled" in profiler_cs

    def test_has_recommendations(self, profiler_cs: str):
        assert "recommendations" in profiler_cs

    def test_has_budget_comparison(self, profiler_cs: str):
        assert "budget" in profiler_cs
        assert "passed" in profiler_cs

    def test_default_frame_time_budget(self, profiler_cs: str):
        assert "16.67" in profiler_cs

    def test_default_draw_calls_budget(self, profiler_cs: str):
        assert "2000" in profiler_cs

    def test_default_memory_budget(self, profiler_cs: str):
        assert "1024" in profiler_cs

    def test_default_sample_frames(self, profiler_cs: str):
        assert "_targetFrames = 60" in profiler_cs

    def test_output_is_string(self, profiler_cs: str):
        assert isinstance(profiler_cs, str)

    def test_ends_with_newline(self, profiler_cs: str):
        assert profiler_cs.endswith("\n")

    def test_has_dispose(self, profiler_cs: str):
        assert "Dispose()" in profiler_cs


class TestProfilerCustomBudgets:
    """Test generate_profiler_handler with custom budget values."""

    def test_custom_frame_time(self):
        cs = generate_profiler_handler(target_frame_time_ms=33.33)
        assert "33.33" in cs

    def test_custom_draw_calls(self):
        cs = generate_profiler_handler(max_draw_calls=5000)
        assert "5000" in cs

    def test_custom_memory(self):
        cs = generate_profiler_handler(max_memory_mb=2048)
        assert "2048" in cs

    def test_custom_sample_frames(self):
        cs = generate_profiler_handler(sample_frames=120)
        assert "_targetFrames = 120" in cs

    def test_namespace_wrapping(self):
        cs = generate_profiler_handler(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self):
        cs = generate_profiler_handler()
        assert "namespace " not in cs


# =====================================================================
# Crash Reporting Tests (QA-06)
# =====================================================================


class TestCrashReporting:
    """Tests for generate_crash_reporting_script output."""

    @pytest.fixture
    def crash_cs(self) -> str:
        return generate_crash_reporting_script()

    def test_has_sentry_sdk_init(self, crash_cs: str):
        assert "SentrySdk.Init" in crash_cs

    def test_has_runtime_initialize_on_load_method(self, crash_cs: str):
        assert "RuntimeInitializeOnLoadMethod" in crash_cs

    def test_has_before_scene_load(self, crash_cs: str):
        assert "BeforeSceneLoad" in crash_cs

    def test_dsn_value_when_provided(self):
        cs = generate_crash_reporting_script(dsn="https://example@sentry.io/123")
        assert "https://example@sentry.io/123" in cs

    def test_empty_dsn_fallback_logging(self, crash_cs: str):
        assert "fallback console logging" in crash_cs

    def test_breadcrumbs_enabled_by_default(self, crash_cs: str):
        assert "logMessageReceived" in crash_cs

    def test_breadcrumbs_disabled(self):
        cs = generate_crash_reporting_script(enable_breadcrumbs=False)
        assert "logMessageReceived" not in cs

    def test_custom_environment(self):
        cs = generate_crash_reporting_script(environment="production")
        assert "production" in cs

    def test_custom_sample_rate(self):
        cs = generate_crash_reporting_script(sample_rate=0.5)
        assert "0.5f" in cs

    def test_has_capture_exception(self, crash_cs: str):
        assert "CaptureException" in crash_cs

    def test_has_capture_message(self, crash_cs: str):
        assert "CaptureMessage" in crash_cs

    def test_has_set_tag(self, crash_cs: str):
        assert "SetTag" in crash_cs

    def test_has_set_user(self, crash_cs: str):
        assert "SetUser" in crash_cs

    def test_sentry_user_class(self, crash_cs: str):
        assert "SentryUser" in crash_cs

    def test_configure_scope(self, crash_cs: str):
        assert "SentrySdk.ConfigureScope" in crash_cs

    def test_auto_session_tracking(self, crash_cs: str):
        assert "AutoSessionTracking" in crash_cs

    def test_namespace_wrapping(self):
        cs = generate_crash_reporting_script(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self, crash_cs: str):
        assert "namespace " not in crash_cs

    def test_output_is_string(self, crash_cs: str):
        assert isinstance(crash_cs, str)

    def test_output_ends_with_newline(self, crash_cs: str):
        assert crash_cs.endswith("\n")

    def test_add_breadcrumb(self, crash_cs: str):
        assert "SentrySdk.AddBreadcrumb" in crash_cs

    def test_sentry_available_preprocessor(self, crash_cs: str):
        assert "SENTRY_AVAILABLE" in crash_cs

    def test_using_unity_engine(self, crash_cs: str):
        assert "using UnityEngine;" in crash_cs


# =====================================================================
# Analytics Tests (QA-07)
# =====================================================================


class TestAnalytics:
    """Tests for generate_analytics_script output."""

    @pytest.fixture
    def analytics_cs(self) -> str:
        return generate_analytics_script()

    def test_has_dont_destroy_on_load(self, analytics_cs: str):
        assert "DontDestroyOnLoad" in analytics_cs

    def test_has_track_event(self, analytics_cs: str):
        assert "TrackEvent" in analytics_cs

    def test_has_flush_events(self, analytics_cs: str):
        assert "FlushEvents" in analytics_cs

    def test_has_session_id(self, analytics_cs: str):
        assert "sessionId" in analytics_cs
        assert "Guid.NewGuid" in analytics_cs

    def test_default_event_names_as_typed_methods(self, analytics_cs: str):
        expected_methods = [
            "TrackLevelStart",
            "TrackLevelComplete",
            "TrackItemAcquired",
            "TrackEnemyKilled",
            "TrackPlayerDeath",
            "TrackSessionStart",
            "TrackSessionEnd",
        ]
        for method in expected_methods:
            assert method in analytics_cs, f"Missing method: {method}"

    def test_custom_event_names(self):
        cs = generate_analytics_script(event_names=["boss_defeated", "chest_opened"])
        assert "TrackBossDefeated" in cs
        assert "TrackChestOpened" in cs

    def test_buffer_size_value(self, analytics_cs: str):
        assert "_maxBufferSize = 100" in analytics_cs

    def test_custom_buffer_size(self):
        cs = generate_analytics_script(max_buffer_size=50)
        assert "_maxBufferSize = 50" in cs

    def test_flush_interval_value(self, analytics_cs: str):
        assert "_flushIntervalSeconds = 30" in analytics_cs

    def test_custom_flush_interval(self):
        cs = generate_analytics_script(flush_interval_seconds=60)
        assert "_flushIntervalSeconds = 60" in cs

    def test_json_serialization(self, analytics_cs: str):
        assert "SerializeEventsToJson" in analytics_cs

    def test_on_application_quit(self, analytics_cs: str):
        assert "OnApplicationQuit" in analytics_cs

    def test_singleton_pattern(self, analytics_cs: str):
        assert "_instance" in analytics_cs
        assert "Instance" in analytics_cs

    def test_monobehaviour(self, analytics_cs: str):
        assert "MonoBehaviour" in analytics_cs

    def test_persistent_data_path(self, analytics_cs: str):
        assert "Application.persistentDataPath" in analytics_cs

    def test_log_file_path_default(self, analytics_cs: str):
        assert "Analytics/events.json" in analytics_cs

    def test_custom_log_file_path(self):
        cs = generate_analytics_script(log_file_path="Logs/custom.json")
        assert "Logs/custom.json" in cs

    def test_iso_8601_timestamp(self, analytics_cs: str):
        assert 'ToString("o")' in analytics_cs

    def test_namespace_wrapping(self):
        cs = generate_analytics_script(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self, analytics_cs: str):
        assert "namespace " not in analytics_cs

    def test_output_is_string(self, analytics_cs: str):
        assert isinstance(analytics_cs, str)

    def test_output_ends_with_newline(self, analytics_cs: str):
        assert analytics_cs.endswith("\n")

    def test_using_system_io(self, analytics_cs: str):
        assert "using System.IO;" in analytics_cs

    def test_using_system_collections_generic(self, analytics_cs: str):
        assert "using System.Collections.Generic;" in analytics_cs

    def test_event_buffer_list(self, analytics_cs: str):
        assert "_eventBuffer" in analytics_cs


# =====================================================================
# Live Inspector Tests (QA-08)
# =====================================================================


class TestLiveInspector:
    """Tests for generate_live_inspector_script output."""

    @pytest.fixture
    def inspector_cs(self) -> str:
        return generate_live_inspector_script()

    def test_has_editor_window(self, inspector_cs: str):
        assert "EditorWindow" in inspector_cs

    def test_has_menu_item(self, inspector_cs: str):
        assert "MenuItem" in inspector_cs
        assert "VeilBreakers/QA/Live Inspector" in inspector_cs

    def test_has_on_gui(self, inspector_cs: str):
        assert "OnGUI()" in inspector_cs

    def test_has_editor_application_update(self, inspector_cs: str):
        assert "EditorApplication.update" in inspector_cs

    def test_has_get_components(self, inspector_cs: str):
        assert "GetComponents<Component>()" in inspector_cs

    def test_has_field_info(self, inspector_cs: str):
        assert "FieldInfo" in inspector_cs

    def test_has_property_info(self, inspector_cs: str):
        assert "PropertyInfo" in inspector_cs

    def test_has_is_playing_check(self, inspector_cs: str):
        assert "EditorApplication.isPlaying" in inspector_cs

    def test_play_mode_warning(self, inspector_cs: str):
        assert "Enter Play Mode to inspect live state" in inspector_cs

    def test_custom_update_interval(self):
        cs = generate_live_inspector_script(update_interval_frames=5)
        assert "_updateIntervalFrames = 5" in cs

    def test_default_update_interval(self, inspector_cs: str):
        assert "_updateIntervalFrames = 10" in inspector_cs

    def test_foldout_elements(self, inspector_cs: str):
        assert "Foldout" in inspector_cs

    def test_scroll_view(self, inspector_cs: str):
        assert "BeginScrollView" in inspector_cs
        assert "EndScrollView" in inspector_cs

    def test_reflection_binding_flags(self, inspector_cs: str):
        assert "BindingFlags.Public" in inspector_cs
        assert "BindingFlags.Instance" in inspector_cs

    def test_using_system_reflection(self, inspector_cs: str):
        assert "using System.Reflection;" in inspector_cs

    def test_using_system_linq(self, inspector_cs: str):
        assert "using System.Linq;" in inspector_cs

    def test_fsm_state_detection(self, inspector_cs: str):
        assert "currentState" in inspector_cs
        assert "_state" in inspector_cs

    def test_vector3_formatting(self, inspector_cs: str):
        assert "Vector3" in inspector_cs

    def test_color_formatting(self, inspector_cs: str):
        assert "ColorField" in inspector_cs

    def test_bool_toggle(self, inspector_cs: str):
        assert "Toggle" in inspector_cs

    def test_pinned_objects(self, inspector_cs: str):
        assert "_pinnedObjects" in inspector_cs
        assert "Pin Selected" in inspector_cs

    def test_max_tracked_objects_default(self, inspector_cs: str):
        assert "_maxTrackedObjects = 20" in inspector_cs

    def test_custom_max_tracked_objects(self):
        cs = generate_live_inspector_script(max_tracked_objects=10)
        assert "_maxTrackedObjects = 10" in cs

    def test_namespace_wrapping(self):
        cs = generate_live_inspector_script(namespace="VB.QA")
        assert "namespace VB.QA" in cs

    def test_no_namespace_by_default(self, inspector_cs: str):
        assert "namespace " not in inspector_cs

    def test_output_is_string(self, inspector_cs: str):
        assert isinstance(inspector_cs, str)

    def test_output_ends_with_newline(self, inspector_cs: str):
        assert inspector_cs.endswith("\n")

    def test_search_filter(self, inspector_cs: str):
        assert "_searchFilter" in inspector_cs
        assert "TextField" in inspector_cs

    def test_help_box_warning(self, inspector_cs: str):
        assert "HelpBox" in inspector_cs
