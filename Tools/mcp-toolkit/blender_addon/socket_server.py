import json
import queue
import socket
import struct
import threading

import bpy

from .handlers import COMMAND_HANDLERS


class BlenderMCPServer:
    def __init__(self, port: int = 9876):
        self.port = port
        self.command_queue: queue.Queue = queue.Queue()
        self.server_thread: threading.Thread | None = None
        self.running = False
        self._server_socket: socket.socket | None = None

    def start(self):
        self.running = True
        self.server_thread = threading.Thread(
            target=self._server_loop, daemon=True
        )
        self.server_thread.start()
        bpy.app.timers.register(
            self._process_commands, first_interval=0.05, persistent=True
        )
        print(f"[VeilBreakers MCP] Server listening on localhost:{self.port}")

    def stop(self):
        self.running = False
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        if bpy.app.timers.is_registered(self._process_commands):
            bpy.app.timers.unregister(self._process_commands)
        if self.server_thread is not None:
            self.server_thread.join(timeout=2.0)
            self.server_thread = None
        print("[VeilBreakers MCP] Server stopped")

    def _server_loop(self):
        """Background thread - NO bpy calls here."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("localhost", self.port))
        self._server_socket.listen(1)
        self._server_socket.settimeout(1.0)
        while self.running:
            try:
                client, addr = self._server_socket.accept()
                self._handle_client(client)
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    raise
                break

    def _handle_client(self, client_sock: socket.socket):
        """Background thread - NO bpy calls here."""
        try:
            length_bytes = self._receive_exactly(client_sock, 4)
            length = struct.unpack(">I", length_bytes)[0]
            json_bytes = self._receive_exactly(client_sock, length)
            command = json.loads(json_bytes)

            result_event = threading.Event()
            result_container: dict = {}
            self.command_queue.put((command, result_event, result_container))

            result_event.wait(timeout=300)

            if "response" in result_container:
                response = result_container["response"]
            else:
                response = {
                    "status": "error",
                    "message": "Command execution timed out",
                }

            response_bytes = json.dumps(response).encode("utf-8")
            client_sock.sendall(
                struct.pack(">I", len(response_bytes)) + response_bytes
            )
        except Exception as e:
            try:
                error_response = json.dumps({
                    "status": "error",
                    "message": f"Server error: {str(e)}",
                }).encode("utf-8")
                client_sock.sendall(
                    struct.pack(">I", len(error_response)) + error_response
                )
            except Exception:
                pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _receive_exactly(self, sock: socket.socket, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def _process_commands(self) -> float:
        """MAIN THREAD via bpy.app.timers - safe for bpy calls."""
        try:
            while not self.command_queue.empty():
                cmd, event, container = self.command_queue.get_nowait()
                try:
                    cmd_type = cmd.get("type", "unknown")
                    params = cmd.get("params", {})
                    handler = COMMAND_HANDLERS.get(cmd_type)
                    if handler is None:
                        container["response"] = {
                            "status": "error",
                            "message": f"Unknown command: {cmd_type}",
                        }
                    else:
                        result = handler(params)
                        if isinstance(result, dict) and "status" in result:
                            container["response"] = result
                        else:
                            container["response"] = {
                                "status": "success",
                                "result": result,
                            }
                except Exception as e:
                    container["response"] = {
                        "status": "error",
                        "message": str(e),
                    }
                finally:
                    event.set()
        except queue.Empty:
            pass
        return 0.05
