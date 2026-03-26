"""VeilBreakers Cowork Bridge - Standalone TCP client for Blender & Unity.

Lightweight bridge that lets Claude Cowork/Dispatch control Blender and Unity
via the same TCP protocol the MCP toolkit uses. No veilbreakers_mcp dependency.

Usage (Python REPL via Desktop Commander):
    from vb_bridge import blender, unity, blender_screenshot
    blender("get_scene_info")
    blender("create_object", mesh_type="cube", position=[0,0,1])
    blender_screenshot()  # returns filepath
    unity("console_logs", log_filter="error", log_count=10)

Usage (CLI one-shot):
    python vb_bridge.py blender get_scene_info
    python vb_bridge.py blender create_object mesh_type=cube
    python vb_bridge.py unity console_logs log_filter=error
"""
import json, socket, struct, sys, os
from typing import Any

MAX_MSG = 64 * 1024 * 1024

BLENDER_HOST = os.environ.get("BLENDER_HOST", "localhost")
BLENDER_PORT = int(os.environ.get("BLENDER_PORT", "9876"))
UNITY_HOST = os.environ.get("UNITY_HOST", "localhost")
UNITY_PORT = int(os.environ.get("UNITY_PORT", "9877"))


def _recv_exact(sock, n):
    chunks, got = [], 0
    while got < n:
        chunk = sock.recv(n - got)
        if not chunk:
            raise ConnectionError("Connection closed")
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


def _send_tcp(host, port, command_type, params, persistent_sock=None, timeout=300):
    """Send a length-prefixed JSON command and return the parsed result."""
    payload = json.dumps({"type": command_type, "params": params}).encode()
    sock = persistent_sock
    created = False
    if sock is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((host, port))
        created = True
    try:
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        length = struct.unpack(">I", _recv_exact(sock, 4))[0]
        if length > MAX_MSG:
            raise ValueError(f"Response too large: {length}")
        data = json.loads(_recv_exact(sock, length))
        if data.get("status") == "error":
            raise RuntimeError(f"[{data.get('error_type','err')}] {data.get('message','unknown')}")
        return data.get("result", data)
    finally:
        if created and persistent_sock is None:
            sock.close()


# --- Persistent Blender connection (reuses socket for speed) ---
_blender_sock = None

def _get_blender_sock():
    global _blender_sock
    if _blender_sock is None:
        _blender_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _blender_sock.settimeout(300)
        _blender_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        _blender_sock.connect((BLENDER_HOST, BLENDER_PORT))
    return _blender_sock

def _reset_blender():
    global _blender_sock
    if _blender_sock:
        try: _blender_sock.close()
        except: pass
    _blender_sock = None


def blender(command_type, **params):
    """Send command to Blender. Persistent connection with auto-reconnect."""
    for attempt in range(2):
        try:
            sock = _get_blender_sock()
            return _send_tcp(BLENDER_HOST, BLENDER_PORT, command_type, params, persistent_sock=sock)
        except (ConnectionError, BrokenPipeError, OSError):
            _reset_blender()
            if attempt == 0:
                continue
            raise


def blender_screenshot(save_path=None):
    """Take Blender viewport screenshot. Returns filepath."""
    result = blender("get_viewport_screenshot", format="png")
    return result.get("filepath", result) if isinstance(result, dict) else result


def blender_contact_sheet(object_name):
    """Render multi-angle contact sheet. Returns filepath."""
    result = blender("render_contact_sheet", object_name=object_name)
    return result.get("filepath", result) if isinstance(result, dict) else result


# --- Unity connection (per-command, matches VBBridge pattern) ---

def unity(command_type, **params):
    """Send command to Unity VBBridge. Fresh connection per command."""
    return _send_tcp(UNITY_HOST, UNITY_PORT, command_type, params)


# --- Convenience wrappers ---

def ping_blender():
    """Quick connectivity test."""
    return blender("ping")

def ping_unity():
    """Quick connectivity test."""
    return unity("ping")

def scene_info():
    """Get Blender scene overview."""
    return blender("get_scene_info")

def unity_logs(filter="all", count=20):
    """Get Unity console logs."""
    return unity("console_logs", log_filter=filter, log_count=count)

def unity_compile():
    """Trigger Unity recompile."""
    return unity("recompile")

def unity_screenshot(path=None, supersize=1):
    """Take Unity editor screenshot."""
    params = {"supersize": supersize}
    if path:
        params["screenshot_path"] = path
    return unity("screenshot", **params)


# --- CLI interface ---

def _parse_cli_params(args):
    """Parse key=value CLI args into dict, auto-converting types."""
    params = {}
    for arg in args:
        if "=" not in arg:
            continue
        k, v = arg.split("=", 1)
        # Try int, float, bool, list
        if v.lower() in ("true", "false"):
            v = v.lower() == "true"
        else:
            try: v = int(v)
            except ValueError:
                try: v = float(v)
                except ValueError:
                    if v.startswith("["):
                        try: v = json.loads(v)
                        except: pass
        params[k] = v
    return params


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python vb_bridge.py <blender|unity> <command> [key=value ...]")
        sys.exit(1)
    target = sys.argv[1].lower()
    cmd = sys.argv[2]
    params = _parse_cli_params(sys.argv[3:])
    fn = blender if target == "blender" else unity
    try:
        result = fn(cmd, **params)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
