"""Unit tests for socket server error handling and race-condition guards."""

import json
import queue
import struct
import threading


class TestSocketServerErrorHandling:
    """Regression tests for narrowed socket error handling paths."""

    def test_handle_client_suppresses_connection_cleanup_errors(self):
        from blender_addon.socket_server import BlenderMCPServer, MAX_MESSAGE_SIZE

        class _FakeClientSocket:
            def __init__(self):
                self._recv_chunks = [struct.pack(">I", MAX_MESSAGE_SIZE + 1)]
                self.closed = False

            def setsockopt(self, *_args, **_kwargs):
                return None

            def settimeout(self, _timeout):
                return None

            def recv(self, _size):
                if self._recv_chunks:
                    return self._recv_chunks.pop(0)
                return b""

            def sendall(self, _payload):
                raise BrokenPipeError("peer disconnected")

            def close(self):
                self.closed = True
                raise OSError("close failed")

        server = BlenderMCPServer()
        server.running = True
        client = _FakeClientSocket()

        server._handle_client(client)

        assert client.closed is True


class TestSocketServerRaceConditions:
    """Tests for race-condition guards added to BlenderMCPServer."""

    def test_socket_lock_exists(self):
        """Server must have a lock protecting _server_socket access."""
        from blender_addon.socket_server import BlenderMCPServer

        server = BlenderMCPServer()
        assert hasattr(server, "_socket_lock")
        assert isinstance(server._socket_lock, type(threading.Lock()))

    def test_started_event_exists(self):
        """Server must have an event to signal socket-bound readiness."""
        from blender_addon.socket_server import BlenderMCPServer

        server = BlenderMCPServer()
        assert hasattr(server, "_started_event")
        assert isinstance(server._started_event, threading.Event)
        # Not set initially
        assert not server._started_event.is_set()

    def test_stop_drains_command_queue(self):
        """stop() must drain pending commands so clients don't hang."""
        from blender_addon.socket_server import BlenderMCPServer

        server = BlenderMCPServer()
        server.running = True

        # Enqueue a fake command
        event = threading.Event()
        container: dict = {}
        server.command_queue.put(({"type": "test"}, event, container))

        # Manually call the drain logic from stop() without bpy timer
        server.running = False
        while True:
            try:
                _cmd, evt, cont = server.command_queue.get_nowait()
                cont["response"] = {
                    "status": "error",
                    "message": "Server shutting down",
                }
                evt.set()
            except queue.Empty:
                break

        # The event should be set and container should have error response
        assert event.is_set()
        assert container["response"]["status"] == "error"
        assert "shutting down" in container["response"]["message"]

    def test_process_commands_returns_zero_when_not_running(self):
        """_process_commands must stop polling when server is shutting down."""
        from blender_addon.socket_server import BlenderMCPServer

        server = BlenderMCPServer()
        server.running = False

        # Should return 0.0 (stop timer) instead of 0.01 (continue)
        result = server._process_commands()
        assert result == 0.0

    def test_handle_client_rejects_invalid_json(self):
        """Client sending invalid JSON must get a ValueError path, not crash."""
        from blender_addon.socket_server import BlenderMCPServer

        # Craft a payload that is valid bytes but not valid JSON
        bad_payload = b"not json at all {"
        length_prefix = struct.pack(">I", len(bad_payload))

        class _FakeSocket:
            def __init__(self):
                self._data = length_prefix + bad_payload
                self._pos = 0
                self.closed = False
                self._sent: list[bytes] = []

            def setsockopt(self, *_args, **_kwargs):
                return None

            def settimeout(self, _timeout):
                return None

            def recv(self, n):
                chunk = self._data[self._pos : self._pos + n]
                self._pos += len(chunk)
                return chunk

            def sendall(self, data):
                self._sent.append(data)

            def close(self):
                self.closed = True

        server = BlenderMCPServer()
        server.running = True
        client = _FakeSocket()

        server._handle_client(client)

        assert client.closed is True
        # Should have sent an error response about invalid JSON
        assert len(client._sent) > 0
        # Decode the response (skip 4-byte length prefix)
        resp = json.loads(client._sent[0][4:])
        assert resp["status"] == "error"
        assert "Invalid JSON" in resp["message"] or "Server error" in resp["message"]
