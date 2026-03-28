"""Unit tests for socket server error handling."""

import struct


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
