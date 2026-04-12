"""Tests for TCP protocol correctness in socket_server (F098-F104).

Verifies:
- Zero-length messages are rejected with ValueError
- Invalid JSON raises ValueError with descriptive message
- socket.timeout in _receive_exactly is caught gracefully
- Oversized messages are rejected
- Normal message round-trip works
"""

from __future__ import annotations

import json
import queue
import socket
import struct
import threading
from unittest.mock import MagicMock, patch

import pytest


def _make_server():
    """Create a BlenderMCPServer without starting the socket."""
    with patch("blender_addon.socket_server.bpy"):
        from blender_addon.socket_server import BlenderMCPServer

        srv = BlenderMCPServer.__new__(BlenderMCPServer)
        srv.port = 9876
        srv.command_queue = queue.Queue()
        srv.server_thread = None
        srv.running = True
        srv._server_socket = None
        return srv


class _FakeSocket:
    """In-memory socket that reads from a buffer."""

    def __init__(self, data: bytes):
        self._buf = data
        self._pos = 0
        self._sent: list[bytes] = []

    def recv(self, n: int) -> bytes:
        chunk = self._buf[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def sendall(self, data: bytes) -> None:
        self._sent.append(data)

    def setsockopt(self, *args):
        pass

    def settimeout(self, t):
        pass

    def close(self):
        pass

    @property
    def sent_data(self) -> bytes:
        return b"".join(self._sent)


# ---------------------------------------------------------------------------
# F098: Zero-length message rejection
# ---------------------------------------------------------------------------


class TestZeroLengthMessage:
    def test_zero_length_raises_value_error(self):
        srv = _make_server()
        # Build a message with length=0
        data = struct.pack(">I", 0)
        fake_sock = _FakeSocket(data)

        # _handle_client should catch ValueError and send error response
        srv._handle_client(fake_sock)

        # Should have sent an error response
        assert fake_sock.sent_data
        resp_len = struct.unpack(">I", fake_sock.sent_data[:4])[0]
        resp = json.loads(fake_sock.sent_data[4 : 4 + resp_len])
        assert resp["status"] == "error"
        assert "zero-length" in resp["message"].lower() or "Zero-length" in resp["message"]


# ---------------------------------------------------------------------------
# F099: Invalid JSON rejection
# ---------------------------------------------------------------------------


class TestInvalidJSON:
    def test_bad_json_sends_error(self):
        srv = _make_server()
        bad_payload = b"not valid json!!!"
        data = struct.pack(">I", len(bad_payload)) + bad_payload
        fake_sock = _FakeSocket(data)

        srv._handle_client(fake_sock)

        assert fake_sock.sent_data
        resp_len = struct.unpack(">I", fake_sock.sent_data[:4])[0]
        resp = json.loads(fake_sock.sent_data[4 : 4 + resp_len])
        assert resp["status"] == "error"
        assert "invalid json" in resp["message"].lower() or "JSON" in resp["message"]


# ---------------------------------------------------------------------------
# F100: Oversized message rejection
# ---------------------------------------------------------------------------


class TestOversizedMessage:
    def test_oversized_message_rejected(self):
        srv = _make_server()
        # Claim 128MB message — above 64MB limit
        data = struct.pack(">I", 128 * 1024 * 1024)
        fake_sock = _FakeSocket(data)

        srv._handle_client(fake_sock)

        assert fake_sock.sent_data
        resp_len = struct.unpack(">I", fake_sock.sent_data[:4])[0]
        resp = json.loads(fake_sock.sent_data[4 : 4 + resp_len])
        assert resp["status"] == "error"
        assert "too large" in resp["message"].lower()


# ---------------------------------------------------------------------------
# F101: Normal message processing
# ---------------------------------------------------------------------------


class TestNormalMessage:
    def test_valid_command_queued(self):
        srv = _make_server()
        cmd = {"type": "ping", "params": {}}
        payload = json.dumps(cmd).encode("utf-8")
        # Build: length + payload + then EOF (empty recv to break loop)
        data = struct.pack(">I", len(payload)) + payload

        # We need to handle the response wait. Spawn a thread to process
        # the command from the queue.
        def _process():
            try:
                c, evt, ctr = srv.command_queue.get(timeout=5)
                ctr["response"] = {"status": "success", "result": "pong"}
                evt.set()
            except Exception:
                pass

        t = threading.Thread(target=_process, daemon=True)
        t.start()

        fake_sock = _FakeSocket(data)
        srv._handle_client(fake_sock)
        t.join(timeout=5)

        # Should have sent a success response
        assert fake_sock.sent_data
        resp_len = struct.unpack(">I", fake_sock.sent_data[:4])[0]
        resp = json.loads(fake_sock.sent_data[4 : 4 + resp_len])
        assert resp["status"] == "success"
        assert resp["result"] == "pong"


# ---------------------------------------------------------------------------
# F102: _receive_exactly on connection close
# ---------------------------------------------------------------------------


class TestReceiveExactly:
    def test_empty_recv_raises_connection_error(self):
        srv = _make_server()
        fake_sock = _FakeSocket(b"")  # Empty — simulates closed connection

        with pytest.raises(ConnectionError, match="Connection closed"):
            srv._receive_exactly(fake_sock, 4)

    def test_partial_recv_assembles(self):
        """_receive_exactly must handle multiple recv calls."""
        srv = _make_server()
        # Socket that returns 1 byte at a time
        data = b"ABCD"

        class _SlowSocket:
            def __init__(self, d):
                self._d = d
                self._pos = 0

            def recv(self, n):
                if self._pos >= len(self._d):
                    return b""
                chunk = self._d[self._pos : self._pos + 1]
                self._pos += 1
                return chunk

        result = srv._receive_exactly(_SlowSocket(data), 4)
        assert result == b"ABCD"


# ---------------------------------------------------------------------------
# F103-F104: socket.timeout handling
# ---------------------------------------------------------------------------


class TestSocketTimeout:
    def test_timeout_on_read_breaks_gracefully(self):
        """socket.timeout during header read should not crash server."""
        srv = _make_server()

        class _TimeoutSocket:
            def recv(self, n):
                raise socket.timeout("read timed out")

            def setsockopt(self, *a):
                pass

            def settimeout(self, t):
                pass

            def close(self):
                pass

        fake_sock = _TimeoutSocket()
        # Should not raise — graceful exit
        srv._handle_client(fake_sock)
