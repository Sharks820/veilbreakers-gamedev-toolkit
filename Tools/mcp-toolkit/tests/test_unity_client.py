"""Tests for Unity bridge Python client and models.

Covers:
- UnityCommand / UnityResponse / UnityError pydantic models
- UnityConnection lifecycle, defaults, _sync_send, send_command
- UnityCommandError exception formatting
"""

from __future__ import annotations

import asyncio
import json
import socket
import struct
import threading
from unittest.mock import MagicMock, patch

import pytest

from veilbreakers_mcp.shared.models import (
    UnityCommand,
    UnityError,
    UnityResponse,
)
from veilbreakers_mcp.shared.unity_client import (
    MAX_MESSAGE_SIZE,
    UnityCommandError,
    UnityConnection,
)


# =====================================================================
# Model tests
# =====================================================================


class TestUnityCommand:
    """UnityCommand pydantic model serialization."""

    def test_basic_serialization(self):
        cmd = UnityCommand(type="ping", params={})
        data = cmd.model_dump()
        assert data["type"] == "ping"
        assert data["params"] == {}

    def test_params_serialization(self):
        cmd = UnityCommand(type="screenshot", params={"path": "/tmp/shot.png", "supersize": 2})
        data = cmd.model_dump()
        assert data["params"]["path"] == "/tmp/shot.png"
        assert data["params"]["supersize"] == 2

    def test_params_default_factory(self):
        cmd = UnityCommand(type="recompile")
        assert cmd.params == {}

    def test_json_roundtrip(self):
        cmd = UnityCommand(type="execute_menu_item", params={"menu_path": "VB/Test"})
        json_str = cmd.model_dump_json()
        parsed = json.loads(json_str)
        cmd2 = UnityCommand(**parsed)
        assert cmd2.type == cmd.type
        assert cmd2.params == cmd.params


class TestUnityResponse:
    """UnityResponse pydantic model deserialization."""

    def test_success_response(self):
        resp = UnityResponse(status="success", result={"refreshed": True})
        assert resp.status == "success"
        assert resp.result == {"refreshed": True}
        assert resp.message is None
        assert resp.error_type is None

    def test_error_response(self):
        resp = UnityResponse(
            status="error",
            message="Command not found",
            error_type="unknown_command",
        )
        assert resp.status == "error"
        assert resp.message == "Command not found"
        assert resp.error_type == "unknown_command"
        assert resp.result is None

    def test_success_with_none_result(self):
        resp = UnityResponse(status="success")
        assert resp.result is None

    def test_from_dict(self):
        data = {"status": "success", "result": "pong"}
        resp = UnityResponse(**data)
        assert resp.result == "pong"

    def test_json_deserialization(self):
        raw = '{"status":"success","result":{"is_playing":true}}'
        resp = UnityResponse(**json.loads(raw))
        assert resp.result["is_playing"] is True


class TestUnityError:
    """UnityError structured error model."""

    def test_fields(self):
        err = UnityError(
            error_type="timeout",
            message="Command timed out after 300s",
            suggestion="Increase timeout or simplify command",
            can_retry=True,
        )
        assert err.error_type == "timeout"
        assert err.can_retry is True

    def test_to_tool_response_retryable(self):
        err = UnityError(
            error_type="timeout",
            message="Timed out",
            suggestion="Retry later",
            can_retry=True,
        )
        text = err.to_tool_response()
        assert "ERROR [timeout]" in text
        assert "Timed out" in text
        assert "SUGGESTION: Retry later" in text
        assert "RETRYABLE: yes" in text

    def test_to_tool_response_not_retryable(self):
        err = UnityError(
            error_type="invalid_command",
            message="Unknown",
            suggestion="Check docs",
            can_retry=False,
        )
        text = err.to_tool_response()
        assert "RETRYABLE: no" in text


# =====================================================================
# UnityCommandError tests
# =====================================================================


class TestUnityCommandError:
    """UnityCommandError exception formatting."""

    def test_message_with_error_type(self):
        resp = UnityResponse(status="error", message="Not found", error_type="handler_missing")
        exc = UnityCommandError(resp)
        assert "handler_missing" in str(exc)
        assert "Not found" in str(exc)

    def test_message_without_error_type(self):
        resp = UnityResponse(status="error", message="Something broke")
        exc = UnityCommandError(resp)
        assert "unknown" in str(exc)
        assert "Something broke" in str(exc)

    def test_preserves_response(self):
        resp = UnityResponse(status="error", message="oops")
        exc = UnityCommandError(resp)
        assert exc.response is resp

    def test_is_exception(self):
        resp = UnityResponse(status="error", message="fail")
        exc = UnityCommandError(resp)
        assert isinstance(exc, Exception)


# =====================================================================
# UnityConnection tests
# =====================================================================


class TestUnityConnectionDefaults:
    """UnityConnection __init__ defaults."""

    def test_default_host(self):
        conn = UnityConnection()
        assert conn.host == "localhost"

    def test_default_port(self):
        conn = UnityConnection()
        assert conn.port == 9877

    def test_default_timeout(self):
        conn = UnityConnection()
        assert conn.timeout == 300

    def test_custom_port(self):
        conn = UnityConnection(port=9999)
        assert conn.port == 9999

    def test_socket_initially_none(self):
        conn = UnityConnection()
        assert conn._socket is None

    def test_has_send_lock(self):
        conn = UnityConnection()
        assert isinstance(conn._send_lock, type(threading.Lock()))


class TestUnityConnectionLifecycle:
    """Connection, disconnection, is_alive, reconnect."""

    def test_is_alive_false_initially(self):
        conn = UnityConnection()
        assert conn.is_alive() is False

    def test_disconnect_when_none(self):
        conn = UnityConnection()
        conn.disconnect()  # Should not raise
        assert conn._socket is None

    def test_disconnect_closes_socket(self):
        conn = UnityConnection()
        mock_sock = MagicMock()
        conn._socket = mock_sock
        conn.disconnect()
        mock_sock.close.assert_called_once()
        assert conn._socket is None

    def test_disconnect_handles_os_error(self):
        conn = UnityConnection()
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("already closed")
        conn._socket = mock_sock
        conn.disconnect()  # Should not raise
        assert conn._socket is None

    def test_connect_raises_on_refused(self):
        conn = UnityConnection(port=1)  # Almost certainly refused
        with pytest.raises(ConnectionError, match="Cannot connect to Unity"):
            conn.connect()

    def test_reconnect_calls_disconnect_then_connect(self):
        conn = UnityConnection()
        with patch.object(conn, "disconnect") as mock_dis, patch.object(
            conn, "connect"
        ) as mock_con:
            conn.reconnect()
            mock_dis.assert_called_once()
            mock_con.assert_called_once()


class TestUnityConnectionReceive:
    """_receive_exactly edge cases."""

    def test_receive_not_connected_raises(self):
        conn = UnityConnection()
        with pytest.raises(ConnectionError, match="Not connected"):
            conn._receive_exactly(4)

    def test_receive_closed_connection_raises(self):
        conn = UnityConnection()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""  # Connection closed
        conn._socket = mock_sock
        with pytest.raises(ConnectionError, match="Connection closed"):
            conn._receive_exactly(4)

    def test_receive_exact_bytes(self):
        conn = UnityConnection()
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"\x00\x00", b"\x00\x05"]
        conn._socket = mock_sock
        result = conn._receive_exactly(4)
        assert result == b"\x00\x00\x00\x05"


class TestUnityConnectionSyncSend:
    """_sync_send with mocked socket."""

    def test_sync_send_success(self):
        conn = UnityConnection()
        response_data = {"status": "success", "result": "pong"}
        response_bytes = json.dumps(response_data).encode("utf-8")
        response_len = struct.pack(">I", len(response_bytes))

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [
            response_len,
            response_bytes,
        ]

        with patch.object(conn, "reconnect"):
            conn._socket = mock_sock
            result = conn._sync_send("ping", {})
            assert result == "pong"

    def test_sync_send_error_raises(self):
        conn = UnityConnection()
        response_data = {"status": "error", "message": "bad cmd", "error_type": "invalid"}
        response_bytes = json.dumps(response_data).encode("utf-8")
        response_len = struct.pack(">I", len(response_bytes))

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [response_len, response_bytes]

        with patch.object(conn, "reconnect"):
            conn._socket = mock_sock
            with pytest.raises(UnityCommandError, match="bad cmd"):
                conn._sync_send("bad", {})

    def test_sync_send_too_large_response(self):
        conn = UnityConnection()
        huge_len = struct.pack(">I", MAX_MESSAGE_SIZE + 1)

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [huge_len]

        with patch.object(conn, "reconnect"):
            conn._socket = mock_sock
            with pytest.raises(ConnectionError, match="Response too large"):
                conn._sync_send("ping", {})

    def test_sync_send_disconnects_in_finally(self):
        conn = UnityConnection()
        response_data = {"status": "success", "result": None}
        response_bytes = json.dumps(response_data).encode("utf-8")
        response_len = struct.pack(">I", len(response_bytes))

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [response_len, response_bytes]

        with patch.object(conn, "reconnect"):
            conn._socket = mock_sock
            with patch.object(conn, "disconnect") as mock_dis:
                conn._sync_send("test", {})
                mock_dis.assert_called_once()


class TestUnityConnectionSendCommand:
    """Async send_command wrapper."""

    def test_send_command_exists(self):
        conn = UnityConnection()
        assert hasattr(conn, "send_command")
        assert asyncio.iscoroutinefunction(conn.send_command)

    def test_send_command_calls_sync_send(self):
        conn = UnityConnection()

        with patch.object(conn, "_sync_send", return_value="pong") as mock_sync:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(conn.send_command("ping"))
                assert result == "pong"
                mock_sync.assert_called_once_with("ping", {})
            finally:
                loop.close()

    def test_send_command_passes_params(self):
        conn = UnityConnection()
        params = {"menu_path": "VB/Test"}

        with patch.object(conn, "_sync_send", return_value=True) as mock_sync:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(conn.send_command("execute_menu_item", params))
                mock_sync.assert_called_once_with("execute_menu_item", params)
            finally:
                loop.close()


class TestMaxMessageSize:
    """MAX_MESSAGE_SIZE constant."""

    def test_value(self):
        assert MAX_MESSAGE_SIZE == 64 * 1024 * 1024

    def test_is_64_mb(self):
        assert MAX_MESSAGE_SIZE == 67_108_864
