import asyncio
import json
import socket
import struct
from typing import Any

from veilbreakers_mcp.shared.models import BlenderCommand, BlenderResponse


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

    def connect(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(self.timeout)
        try:
            self._socket.connect((self.host, self.port))
        except ConnectionRefusedError:
            self._socket = None
            raise ConnectionError(
                f"Cannot connect to Blender on {self.host}:{self.port}. "
                "Start Blender and enable the VeilBreakers addon."
            )

    def disconnect(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def is_alive(self) -> bool:
        if self._socket is None:
            return False
        try:
            result = self._sync_send("ping", {})
            return result is not None
        except Exception:
            self._socket = None
            return False

    def reconnect(self) -> None:
        self.disconnect()
        self.connect()

    def _receive_exactly(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self._socket.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by Blender")
            data += chunk
        return data

    def _sync_send(self, command_type: str, params: dict[str, Any]) -> Any:
        if self._socket is None:
            raise ConnectionError("Not connected to Blender")
        command = BlenderCommand(type=command_type, params=params)
        json_bytes = command.model_dump_json().encode("utf-8")
        self._socket.sendall(struct.pack(">I", len(json_bytes)) + json_bytes)
        length_bytes = self._receive_exactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        response_bytes = self._receive_exactly(length)
        response_data = json.loads(response_bytes)
        response = BlenderResponse(**response_data)
        if response.status == "error":
            raise BlenderCommandError(response)
        return response.result

    async def send_command(
        self, command_type: str, params: dict[str, Any] | None = None
    ) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_send, command_type, params or {}
        )

    async def capture_viewport_bytes(self) -> bytes:
        result = await self.send_command(
            "get_viewport_screenshot", {"format": "png"}
        )
        filepath = result.get("filepath", "")
        with open(filepath, "rb") as f:
            return f.read()

    async def capture_viewport_to_file(self) -> str:
        result = await self.send_command(
            "get_viewport_screenshot", {"format": "png"}
        )
        return result.get("filepath", "")
