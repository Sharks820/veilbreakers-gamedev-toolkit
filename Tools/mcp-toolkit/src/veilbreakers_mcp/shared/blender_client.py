"""TCP client for communicating with the Blender MCP addon socket server.

Supports **persistent connections**: a single TCP socket is kept alive
between commands to eliminate the connect/disconnect overhead (~2-5ms
per round-trip on localhost).  If the connection is lost mid-command,
the client transparently reconnects and retries once.

Connection lifecycle:
  1. First ``send_command`` lazily opens a socket.
  2. Subsequent calls reuse the same socket (length-prefixed framing).
  3. ``disconnect()`` or ``atexit`` closes the socket.
  4. On send/recv failure the socket is discarded and a fresh one is
     opened for the retry attempt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import struct
import threading
from typing import Any

from veilbreakers_mcp.shared.models import BlenderCommand, BlenderResponse

MAX_MESSAGE_SIZE = 64 * 1024 * 1024  # 64 MB

logger = logging.getLogger(__name__)


class BlenderCommandError(Exception):
    def __init__(self, response: BlenderResponse):
        self.response = response
        super().__init__(
            f"ERROR [{response.error_type or 'unknown'}]: {response.message}"
        )


class BlenderConnection:
    """Persistent TCP connection to the Blender MCP addon.

    The connection is kept alive between commands.  If a transient network
    error occurs during a command, the client reconnects once and retries.

    Parameters
    ----------
    host : str
        Blender addon hostname (default ``"localhost"``).
    port : int
        Blender addon port (default ``9876``).
    timeout : int
        Socket timeout in seconds for connect and per-recv (default 300).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9876,
        timeout: int = 300,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._send_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open a TCP socket to Blender (if not already connected)."""
        if self._socket is not None:
            return  # already connected
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except ConnectionRefusedError as exc:
            sock.close()
            raise ConnectionError(
                f"Cannot connect to Blender on {self.host}:{self.port} "
                "(connection refused). Blender is not running or the "
                "VeilBreakers addon is not enabled.\n\n"
                "To fix this:\n"
                "  1. Start Blender\n"
                "  2. Go to Edit > Preferences > Add-ons\n"
                "  3. Search for 'VeilBreakers' and enable the addon\n"
                "  4. Verify the addon status bar shows 'Listening on "
                f"{self.host}:{self.port}'\n"
                "  5. Retry the command"
            ) from exc
        except TimeoutError as exc:
            sock.close()
            raise ConnectionError(
                f"Connection to Blender on {self.host}:{self.port} timed out "
                f"after {self.timeout}s. Blender may be busy with a long "
                "operation (rendering, baking, heavy computation) or the "
                "VeilBreakers addon socket listener is not responding.\n\n"
                "To fix this:\n"
                "  1. Check if Blender is frozen or processing a task\n"
                "  2. If Blender is idle, disable and re-enable the "
                "VeilBreakers addon in Edit > Preferences > Add-ons\n"
                "  3. Retry the command"
            ) from exc
        except OSError as exc:
            sock.close()
            raise ConnectionError(
                f"Network error connecting to Blender on "
                f"{self.host}:{self.port}: {exc}\n\n"
                "To fix this:\n"
                "  1. Ensure Blender is running with the VeilBreakers addon "
                "enabled (Edit > Preferences > Add-ons)\n"
                "  2. Check that no firewall is blocking localhost connections\n"
                "  3. Verify the addon is listening on the correct port\n"
                "  4. Retry the command"
            ) from exc
        self._socket = sock

    def disconnect(self) -> None:
        """Close the persistent TCP socket, if open."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def is_alive(self) -> bool:
        """Check if the existing connection is usable, or probe the server.

        If a persistent socket is held, checks whether it appears valid.
        Otherwise does a quick connect/disconnect probe.
        """
        if self._socket is not None:
            # Quick liveness check via zero-length peek
            try:
                self._socket.setblocking(False)
                try:
                    data = self._socket.recv(1, socket.MSG_PEEK)
                    # If recv returns empty bytes the server closed
                    if data == b"":
                        self.disconnect()
                        return False
                except BlockingIOError:
                    pass  # No data waiting -- socket is likely still good
                finally:
                    self._socket.settimeout(self.timeout)
                return True
            except OSError:
                self.disconnect()
                return False

        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(2)
        try:
            probe.connect((self.host, self.port))
            probe.close()
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False

    def reconnect(self) -> None:
        """Drop the current socket and establish a fresh connection."""
        self.disconnect()
        self.connect()

    # ------------------------------------------------------------------
    # Wire protocol helpers
    # ------------------------------------------------------------------

    def _receive_exactly(self, n: int) -> bytes:
        """Read exactly *n* bytes from the socket."""
        if self._socket is None:
            raise ConnectionError("Not connected to Blender")
        chunks: list[bytes] = []
        received = 0
        try:
            while received < n:
                chunk = self._socket.recv(n - received)
                if not chunk:
                    raise ConnectionError(
                        "Connection closed by Blender mid-response. "
                        "The addon may have crashed or restarted. "
                        "Check the Blender console for errors and retry."
                    )
                chunks.append(chunk)
                received += len(chunk)
        except socket.timeout as exc:
            raise ConnectionError(
                f"Blender stopped responding while sending data "
                f"(received {received}/{n} bytes). The operation may "
                "be taking longer than expected. Check Blender's status "
                "and retry, or increase the timeout."
            ) from exc
        return b"".join(chunks)

    # ------------------------------------------------------------------
    # Command send/receive (persistent connection with auto-retry)
    # ------------------------------------------------------------------

    def _sync_send(self, command_type: str, params: dict[str, Any]) -> Any:
        """Send a command and return the result, reusing a persistent socket.

        On transient failure (broken pipe, connection reset) the client
        reconnects once and retries the command.
        """
        with self._send_lock:
            last_error: Exception | None = None
            for attempt in range(2):  # at most 1 retry
                try:
                    # Lazily connect, or reuse existing socket
                    if self._socket is None:
                        self.connect()
                    return self._send_on_socket(command_type, params)
                except (ConnectionError, BrokenPipeError, OSError) as exc:
                    last_error = exc
                    logger.debug(
                        "Blender connection lost (attempt %d): %s", attempt, exc
                    )
                    # Discard the broken socket and retry once
                    self.disconnect()
                    if attempt == 0:
                        continue
            # Both attempts failed
            raise ConnectionError(
                f"Failed to communicate with Blender after reconnect: "
                f"{last_error}"
            ) from last_error

    def _send_on_socket(
        self, command_type: str, params: dict[str, Any]
    ) -> Any:
        """Perform the actual send/recv on the current socket.

        Does NOT close the socket after the command -- the socket stays
        alive for subsequent commands.
        """
        if self._socket is None:
            raise ConnectionError("Not connected to Blender")
        command = BlenderCommand(type=command_type, params=params)
        json_bytes = command.model_dump_json().encode("utf-8")
        self._socket.sendall(struct.pack(">I", len(json_bytes)) + json_bytes)

        length_bytes = self._receive_exactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        if length > MAX_MESSAGE_SIZE:
            raise ConnectionError(
                f"Response too large: {length} bytes (max {MAX_MESSAGE_SIZE})"
            )
        response_bytes = self._receive_exactly(length)
        try:
            response_data = json.loads(response_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ConnectionError(
                f"Blender returned invalid JSON ({len(response_bytes)} bytes): {exc}"
            ) from exc
        response = BlenderResponse(**response_data)
        if response.status == "error":
            raise BlenderCommandError(response)
        return response.result

    # ------------------------------------------------------------------
    # Async interface
    # ------------------------------------------------------------------

    async def send_command(
        self, command_type: str, params: dict[str, Any] | None = None
    ) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_send, command_type, params or {}
        )

    async def capture_viewport_bytes(self) -> bytes:
        result = await self.send_command(
            "get_viewport_screenshot", {"format": "png"}
        )
        filepath = result.get("filepath", "")
        if not filepath:
            raise ConnectionError("Blender did not return a screenshot filepath")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._read_and_cleanup, filepath
        )

    @staticmethod
    def _read_and_cleanup(filepath: str) -> bytes:
        with open(filepath, "rb") as f:
            data = f.read()
        try:
            os.unlink(filepath)
        except OSError:
            pass
        return data

    async def capture_viewport_to_file(self) -> str:
        result = await self.send_command(
            "get_viewport_screenshot", {"format": "png"}
        )
        return result.get("filepath", "")
