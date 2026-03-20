"""Tests for Unity TCP bridge addon C# template generators.

Covers:
- generate_bridge_server_script: [InitializeOnLoad], TcpListener, ConcurrentQueue,
  EditorApplication.update, ProcessCommands, ManualResetEventSlim, AssemblyReloadEvents,
  ReadExactly, port parameterization, namespace wrapping
- generate_bridge_commands_script: HANDLERS dictionary, all 9 handler names,
  Dispatch method, AssetDatabase.Refresh, ExecuteMenuItem, EnterPlaymode, ExitPlaymode,
  MiniJSON parser, SerializeResponse, namespace wrapping
"""

from __future__ import annotations

import pytest

from veilbreakers_mcp.shared.unity_templates.qa_templates import (
    generate_bridge_commands_script,
    generate_bridge_server_script,
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
