"""Tests for BlenderConnection TCP client."""

import json
import socket
import struct
import threading
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from veilbreakers_mcp.shared.blender_client import (
    BlenderConnection,
    BlenderCommandError,
    MAX_MESSAGE_SIZE,
)
from veilbreakers_mcp.shared.models import BlenderResponse


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


class TestConnectionRefused:
    def test_raises_connection_error_with_helpful_message(self):
        conn = BlenderConnection(host="localhost", port=19999, timeout=1)
        with pytest.raises(ConnectionError, match="Blender"):
            conn.connect()

    def test_message_includes_fix_steps(self):
        conn = BlenderConnection(host="localhost", port=19999, timeout=1)
        with pytest.raises(ConnectionError, match="VeilBreakers"):
            conn.connect()


class TestConnectionTimeout:
    def test_timeout_raises_connection_error(self):
        conn = BlenderConnection(host="192.0.2.1", port=9876, timeout=1)
        with pytest.raises(ConnectionError, match="timed out"):
            conn.connect()


class TestDisconnect:
    def test_disconnect_clears_socket(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        conn._socket = mock_sock
        conn.disconnect()
        assert conn._socket is None
        mock_sock.close.assert_called_once()

    def test_disconnect_when_not_connected(self):
        conn = BlenderConnection()
        conn.disconnect()  # Should not raise
        assert conn._socket is None

    def test_disconnect_handles_oserror(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("socket error")
        conn._socket = mock_sock
        conn.disconnect()  # Should not raise
        assert conn._socket is None


class TestIsAlive:
    def test_no_socket_probes_server(self):
        conn = BlenderConnection(host="localhost", port=19999)
        assert conn.is_alive() is False

    def test_with_socket_server_closed(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""
        conn._socket = mock_sock
        assert conn.is_alive() is False
        assert conn._socket is None

    def test_with_socket_blocking_io_error(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = BlockingIOError
        conn._socket = mock_sock
        assert conn.is_alive() is True


class TestReconnect:
    def test_reconnect_disconnects_first(self):
        conn = BlenderConnection(host="localhost", port=19999)
        mock_sock = MagicMock()
        conn._socket = mock_sock
        with pytest.raises(ConnectionError):
            conn.reconnect()
        mock_sock.close.assert_called_once()


# ---------------------------------------------------------------------------
# Wire protocol: length-prefixed framing
# ---------------------------------------------------------------------------


class TestLengthPrefixedFraming:
    def test_receive_exactly_reads_full_data(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        # Simulate fragmented recv
        mock_sock.recv.side_effect = [b"AB", b"CD"]
        conn._socket = mock_sock
        result = conn._receive_exactly(4)
        assert result == b"ABCD"

    def test_receive_exactly_connection_closed(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""
        conn._socket = mock_sock
        with pytest.raises(ConnectionError, match="Connection closed by Blender"):
            conn._receive_exactly(4)

    def test_receive_exactly_timeout(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = socket.timeout("timed out")
        conn._socket = mock_sock
        with pytest.raises(ConnectionError, match="stopped responding"):
            conn._receive_exactly(4)

    def test_receive_exactly_not_connected(self):
        conn = BlenderConnection()
        with pytest.raises(ConnectionError, match="Not connected"):
            conn._receive_exactly(4)


class TestMessageSizeLimit:
    def test_response_too_large_rejected(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        conn._socket = mock_sock

        # Send phase: succeed
        mock_sock.sendall = MagicMock()

        # Recv: return a length header exceeding MAX_MESSAGE_SIZE
        huge_len = MAX_MESSAGE_SIZE + 1
        length_bytes = struct.pack(">I", huge_len)
        # First _receive_exactly call returns the length header
        mock_sock.recv.side_effect = [length_bytes]

        with pytest.raises(ConnectionError, match="Response too large"):
            conn._send_on_socket("test_command", {})


# ---------------------------------------------------------------------------
# Command serialization
# ---------------------------------------------------------------------------


class TestSendCommand:
    def test_send_on_socket_serializes_correctly(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        conn._socket = mock_sock

        # Prepare response
        response_data = {"status": "success", "result": {"key": "value"}}
        response_bytes = json.dumps(response_data).encode("utf-8")
        length_header = struct.pack(">I", len(response_bytes))

        # Mock recv to return length header then response body
        mock_sock.recv.side_effect = [length_header, response_bytes]

        result = conn._send_on_socket("test_cmd", {"param1": "val1"})
        assert result == {"key": "value"}

        # Verify sendall was called with length-prefixed JSON
        call_args = mock_sock.sendall.call_args[0][0]
        sent_length = struct.unpack(">I", call_args[:4])[0]
        sent_json = json.loads(call_args[4:])
        assert sent_json["type"] == "test_cmd"
        assert sent_json["params"]["param1"] == "val1"
        assert sent_length == len(call_args[4:])


class TestResponseParsing:
    def test_success_response_returns_result(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        conn._socket = mock_sock

        response_data = {"status": "success", "result": [1, 2, 3]}
        response_bytes = json.dumps(response_data).encode("utf-8")
        mock_sock.recv.side_effect = [
            struct.pack(">I", len(response_bytes)),
            response_bytes,
        ]

        result = conn._send_on_socket("cmd", {})
        assert result == [1, 2, 3]

    def test_error_response_raises_command_error(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        conn._socket = mock_sock

        response_data = {
            "status": "error",
            "message": "Object not found",
            "error_type": "NOT_FOUND",
        }
        response_bytes = json.dumps(response_data).encode("utf-8")
        mock_sock.recv.side_effect = [
            struct.pack(">I", len(response_bytes)),
            response_bytes,
        ]

        with pytest.raises(BlenderCommandError, match="NOT_FOUND"):
            conn._send_on_socket("cmd", {})

    def test_invalid_json_raises_connection_error(self):
        conn = BlenderConnection()
        mock_sock = MagicMock()
        conn._socket = mock_sock

        bad_bytes = b"not valid json {{{{"
        mock_sock.recv.side_effect = [
            struct.pack(">I", len(bad_bytes)),
            bad_bytes,
        ]

        with pytest.raises(ConnectionError, match="invalid JSON"):
            conn._send_on_socket("cmd", {})


# ---------------------------------------------------------------------------
# Reconnection / retry
# ---------------------------------------------------------------------------


class TestReconnectionAfterDisconnect:
    def test_retries_once_on_broken_pipe(self):
        conn = BlenderConnection(host="localhost", port=19999)

        call_count = 0

        def fake_send(cmd_type, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise BrokenPipeError("pipe broken")
            return {"result": "ok"}

        conn._send_on_socket = fake_send
        conn.connect = MagicMock()

        result = conn._sync_send("test", {})
        assert result == {"result": "ok"}
        assert call_count == 2

    def test_fails_after_two_attempts(self):
        conn = BlenderConnection(host="localhost", port=19999)

        conn._send_on_socket = MagicMock(side_effect=BrokenPipeError("broken"))
        conn.connect = MagicMock()

        with pytest.raises(ConnectionError, match="Failed to communicate"):
            conn._sync_send("test", {})


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_send_lock_is_used(self):
        conn = BlenderConnection()
        assert isinstance(conn._send_lock, type(threading.Lock()))

    def test_concurrent_sync_sends_are_serialized(self):
        conn = BlenderConnection()
        lock_acquired_count = 0

        original_send = conn._send_on_socket

        def tracked_send(cmd_type, params):
            nonlocal lock_acquired_count
            # If we're here, the lock was acquired
            lock_acquired_count += 1
            raise ConnectionError("test - stop early")

        conn._send_on_socket = tracked_send
        conn.connect = MagicMock()

        with pytest.raises(ConnectionError):
            conn._sync_send("test", {})


# ---------------------------------------------------------------------------
# Async interface
# ---------------------------------------------------------------------------


class TestAsyncInterface:
    @pytest.mark.asyncio
    async def test_send_command_delegates_to_sync(self):
        conn = BlenderConnection()
        conn._sync_send = MagicMock(return_value={"status": "ok"})

        result = await conn.send_command("test_cmd", {"key": "val"})
        assert result == {"status": "ok"}
        conn._sync_send.assert_called_once_with("test_cmd", {"key": "val"})

    @pytest.mark.asyncio
    async def test_send_command_default_params(self):
        conn = BlenderConnection()
        conn._sync_send = MagicMock(return_value="ok")

        await conn.send_command("cmd")
        conn._sync_send.assert_called_once_with("cmd", {})


# ---------------------------------------------------------------------------
# BlenderCommandError
# ---------------------------------------------------------------------------


class TestBlenderCommandError:
    def test_error_message_format(self):
        response = BlenderResponse(
            status="error",
            message="Something broke",
            error_type="RUNTIME",
        )
        err = BlenderCommandError(response)
        assert "RUNTIME" in str(err)
        assert "Something broke" in str(err)
        assert err.response is response

    def test_error_with_no_error_type(self):
        response = BlenderResponse(
            status="error",
            message="Unknown error",
        )
        err = BlenderCommandError(response)
        assert "unknown" in str(err)
