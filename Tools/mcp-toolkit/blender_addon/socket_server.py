import json
import logging
import queue
import socket
import struct
import threading

import bpy

from .handlers import COMMAND_HANDLERS

MAX_MESSAGE_SIZE = 64 * 1024 * 1024  # 64 MB
logger = logging.getLogger(__name__)


class BlenderMCPServer:
    def __init__(self, port: int = 9876):
        self.port = port
        self.command_queue: queue.Queue = queue.Queue()
        self.server_thread: threading.Thread | None = None
        self.running = False
        self._server_socket: socket.socket | None = None
        self._socket_lock = threading.Lock()
        self._started_event = threading.Event()

    def start(self):
        self.running = True
        self._started_event.clear()
        self.server_thread = threading.Thread(
            target=self._server_loop, daemon=True
        )
        self.server_thread.start()
        # Wait for the server socket to be bound before returning,
        # preventing a race where stop() is called before the socket exists.
        self._started_event.wait(timeout=5.0)
        # 10ms poll interval for snappy interactive editing response.
        # Tradeoff: ~1% more idle CPU than 50ms, but commands execute 5x
        # faster after arriving.  Acceptable for a dev-time tool.
        bpy.app.timers.register(
            self._process_commands, first_interval=0.01, persistent=True
        )
        print(f"[VeilBreakers MCP] Server listening on localhost:{self.port}")

    def stop(self):
        self.running = False
        with self._socket_lock:
            if self._server_socket is not None:
                try:
                    self._server_socket.close()
                except OSError:
                    pass
                self._server_socket = None
        if bpy.app.timers.is_registered(self._process_commands):
            bpy.app.timers.unregister(self._process_commands)
        # Drain the command queue so waiting clients get an error response
        # instead of hanging until the 300s timeout expires.
        while True:
            try:
                _cmd, event, container = self.command_queue.get_nowait()
                container["response"] = {
                    "status": "error",
                    "message": "Server shutting down",
                }
                event.set()
            except queue.Empty:
                break
        if self.server_thread is not None:
            self.server_thread.join(timeout=2.0)
            self.server_thread = None
        print("[VeilBreakers MCP] Server stopped")

    def _server_loop(self):
        """Background thread - NO bpy calls here."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("localhost", self.port))
        srv.listen(5)
        srv.settimeout(1.0)
        with self._socket_lock:
            self._server_socket = srv
        # Signal that the socket is bound and ready for connections.
        self._started_event.set()
        try:
            while self.running:
                try:
                    client, addr = srv.accept()
                    threading.Thread(
                        target=self._handle_client, args=(client,), daemon=True
                    ).start()
                except socket.timeout:
                    continue
                except OSError:
                    if self.running:
                        raise
                    break
        finally:
            try:
                srv.close()
            except OSError:
                pass

    def _handle_client(self, client_sock: socket.socket):
        """Background thread - NO bpy calls here.

        Supports persistent connections: the client may send multiple
        length-prefixed commands on the same socket.  When the client
        closes the connection (recv returns empty bytes), the loop exits
        gracefully.  Legacy single-command clients still work because
        they simply close after the first response.
        """
        try:
            client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # Per-command idle timeout (30s).  If the client stays silent
            # for this long we assume the connection is stale and drop it.
            client_sock.settimeout(30.0)

            while self.running:
                try:
                    length_bytes = self._receive_exactly(client_sock, 4)
                except (ConnectionError, OSError):
                    # Client disconnected cleanly or connection lost
                    break
                length = struct.unpack(">I", length_bytes)[0]
                if length > MAX_MESSAGE_SIZE:
                    raise ValueError(
                        f"Message too large: {length} bytes (max {MAX_MESSAGE_SIZE})"
                    )
                json_bytes = self._receive_exactly(client_sock, length)
                try:
                    command = json.loads(json_bytes)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ValueError(f"Invalid JSON payload: {exc}") from exc

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
                try:
                    client_sock.sendall(
                        struct.pack(">I", len(response_bytes)) + response_bytes
                    )
                except (BrokenPipeError, ConnectionError, OSError):
                    # Client went away before we could send the response
                    break
        except (ConnectionError, OSError, ValueError, struct.error) as e:
            try:
                error_response = json.dumps({
                    "status": "error",
                    "message": f"Server error: {str(e)}",
                }).encode("utf-8")
                client_sock.sendall(
                    struct.pack(">I", len(error_response)) + error_response
                )
            except (BrokenPipeError, ConnectionError, OSError) as send_exc:
                logger.debug(
                    "Failed to send socket server error response: %s",
                    send_exc,
                    exc_info=True,
                )
        finally:
            try:
                client_sock.close()
            except OSError as close_exc:
                logger.debug(
                    "Failed to close client socket cleanly: %s",
                    close_exc,
                    exc_info=True,
                )

    def _receive_exactly(self, sock: socket.socket, n: int) -> bytes:
        chunks: list[bytes] = []
        received = 0
        while received < n:
            chunk = sock.recv(n - received)
            if not chunk:
                raise ConnectionError("Connection closed")
            chunks.append(chunk)
            received += len(chunk)
        return b"".join(chunks)

    def _process_commands(self) -> float:
        """MAIN THREAD via bpy.app.timers - safe for bpy calls."""
        if not self.running:
            return 0.0  # Stop the timer when server is shutting down
        try:
            # Process one command per tick to avoid freezing Blender UI
            try:
                cmd, event, container = self.command_queue.get_nowait()
            except queue.Empty:
                return 0.01
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
        except Exception as e:
            # Outer guard -- prevents timer from being silently unregistered
            print(f"[VeilBreakers MCP] Timer error: {e}")
        return 0.01
