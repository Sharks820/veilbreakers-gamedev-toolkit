import asyncio
import json
import os
import socket
import struct
import threading
from typing import Any

from veilbreakers_mcp.shared.models import BlenderCommand, BlenderResponse

MAX_MESSAGE_SIZE = 64 * 1024 * 1024  # 64 MB


class BlenderCommandError(Exception):
    def __init__(self, response: BlenderResponse):
        self.response = response
        super().__init__(
            f"ERROR [{response.error_type or 'unknown'}]: {response.message}"
        )


class BlenderConnection:
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

    def connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
        except (ConnectionRefusedError, OSError, TimeoutError) as exc:
            sock.close()
            self._socket = None
            raise ConnectionError(
                f"Cannot connect to Blender on {self.host}:{self.port}. "
                "Start Blender and enable the VeilBreakers addon."
            ) from exc
        self._socket = sock

    def disconnect(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def is_alive(self) -> bool:
        # Simple liveness check — don't ping since server is connection-per-command.
        # The actual liveness is tested when a command is sent.
        return self._socket is not None

    def reconnect(self) -> None:
        self.disconnect()
        self.connect()

    def _receive_exactly(self, n: int) -> bytes:
        if self._socket is None:
            raise ConnectionError("Not connected to Blender")
        chunks: list[bytes] = []
        received = 0
        while received < n:
            chunk = self._socket.recv(n - received)
            if not chunk:
                raise ConnectionError("Connection closed by Blender")
            chunks.append(chunk)
            received += len(chunk)
        return b"".join(chunks)

    def _sync_send(self, command_type: str, params: dict[str, Any]) -> Any:
        with self._send_lock:
            # Server closes socket after each command — reconnect each time
            self.reconnect()
            if self._socket is None:
                raise ConnectionError("Not connected to Blender")
            try:
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
                response_data = json.loads(response_bytes)
                response = BlenderResponse(**response_data)
                if response.status == "error":
                    raise BlenderCommandError(response)
                return response.result
            finally:
                # Server closes its end after each response — close ours too
                # to avoid leaving half-open sockets between commands.
                self.disconnect()

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
