"""Unity Editor TCP bridge client.

Mirrors :pymod:`veilbreakers_mcp.shared.blender_client` exactly but
targets the Unity Editor bridge addon on **port 9877** instead of
Blender on port 9876.  Uses the same 4-byte big-endian length-prefix
JSON protocol and the same connection-per-command pattern (connect,
send, receive, close).

Exports:
    UnityConnection   -- TCP client for Unity Editor bridge
    UnityCommandError -- Raised when bridge returns ``status: "error"``
"""

from __future__ import annotations

import asyncio
import json
import socket
import struct
import threading
from typing import Any

from veilbreakers_mcp.shared.models import UnityCommand, UnityResponse

MAX_MESSAGE_SIZE = 64 * 1024 * 1024  # 64 MB


class UnityCommandError(Exception):
    """Raised when the Unity bridge returns an error response."""

    def __init__(self, response: UnityResponse):
        self.response = response
        super().__init__(
            f"ERROR [{response.error_type or 'unknown'}]: {response.message}"
        )


class UnityConnection:
    """TCP client that communicates with the Unity Editor bridge addon.

    The bridge runs inside Unity Editor as an ``[InitializeOnLoad]``
    ``TcpListener`` on *port* (default **9877**).  Each call to
    :meth:`_sync_send` opens a fresh connection (connection-per-command
    pattern), sends a :class:`UnityCommand`, reads the
    :class:`UnityResponse`, then closes.

    Parameters
    ----------
    host:
        Bridge hostname (default ``"localhost"``).
    port:
        Bridge TCP port (default **9877** -- NOT 9876 which is Blender).
    timeout:
        Socket timeout in seconds (default 300).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9877,
        timeout: int = 300,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._send_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open a TCP connection to the Unity bridge."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
        except (ConnectionRefusedError, OSError, TimeoutError) as exc:
            sock.close()
            self._socket = None
            raise ConnectionError(
                f"Cannot connect to Unity Editor on {self.host}:{self.port}. "
                "Start Unity and ensure the VBBridge addon is loaded."
            ) from exc
        self._socket = sock

    def disconnect(self) -> None:
        """Close the current TCP connection (if any)."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def is_alive(self) -> bool:
        """Return whether a socket is currently held (not a true liveness probe)."""
        return self._socket is not None

    def reconnect(self) -> None:
        """Disconnect then connect (used before every command)."""
        self.disconnect()
        self.connect()

    # ------------------------------------------------------------------
    # Low-level I/O
    # ------------------------------------------------------------------

    def _receive_exactly(self, n: int) -> bytes:
        """Read exactly *n* bytes from the socket."""
        if self._socket is None:
            raise ConnectionError("Not connected to Unity Editor")
        chunks: list[bytes] = []
        received = 0
        while received < n:
            chunk = self._socket.recv(n - received)
            if not chunk:
                raise ConnectionError("Connection closed by Unity Editor")
            chunks.append(chunk)
            received += len(chunk)
        return b"".join(chunks)

    # ------------------------------------------------------------------
    # Command transport
    # ------------------------------------------------------------------

    def _sync_send(self, command_type: str, params: dict[str, Any]) -> Any:
        """Send a command synchronously and return the result.

        Uses the connection-per-command pattern: reconnect, send the
        4-byte length-prefixed JSON payload, read the response, and
        disconnect in the ``finally`` block.
        """
        with self._send_lock:
            self.reconnect()
            if self._socket is None:
                raise ConnectionError("Not connected to Unity Editor")
            try:
                command = UnityCommand(type=command_type, params=params)
                json_bytes = command.model_dump_json().encode("utf-8")
                self._socket.sendall(
                    struct.pack(">I", len(json_bytes)) + json_bytes
                )

                length_bytes = self._receive_exactly(4)
                length = struct.unpack(">I", length_bytes)[0]
                if length > MAX_MESSAGE_SIZE:
                    raise ConnectionError(
                        f"Response too large: {length} bytes "
                        f"(max {MAX_MESSAGE_SIZE})"
                    )

                response_bytes = self._receive_exactly(length)
                try:
                    response_data = json.loads(response_bytes)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ConnectionError(
                        f"Unity returned invalid JSON ({len(response_bytes)} bytes): {exc}"
                    ) from exc
                response = UnityResponse(**response_data)

                if response.status == "error":
                    raise UnityCommandError(response)

                return response.result
            finally:
                self.disconnect()

    async def send_command(
        self, command_type: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Async wrapper around :meth:`_sync_send` via ``run_in_executor``."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_send, command_type, params or {}
        )
