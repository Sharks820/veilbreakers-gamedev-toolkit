"""Direct Blender addon TCP client for Phase 48 generation.

Usage:
    from scripts.blender_client import send_blender
    result = send_blender('execute_code', {'code': 'import bpy; print(len(bpy.data.objects))'})
"""

import socket
import json
import struct
import sys


def send_blender(cmd_type: str, params: dict, timeout: float = 300.0) -> dict:
    """Send a command to Blender addon via TCP and return the response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(('localhost', 9876))
    payload = json.dumps({'type': cmd_type, 'params': params}).encode('utf-8')
    s.sendall(struct.pack('>I', len(payload)) + payload)

    header = b''
    while len(header) < 4:
        header += s.recv(4 - len(header))
    resp_len = struct.unpack('>I', header)[0]

    data = b''
    while len(data) < resp_len:
        data += s.recv(min(65536, resp_len - len(data)))
    s.close()
    return json.loads(data.decode('utf-8'))


def blender_exec(code: str, timeout: float = 300.0) -> dict:
    """Execute Python code in Blender and return result."""
    return send_blender('execute_code', {'code': code}, timeout=timeout)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        code = ' '.join(sys.argv[1:])
    else:
        code = 'import bpy; print("Blender:", bpy.app.version_string)'
    result = send_blender('execute_code', {'code': code})
    print(json.dumps(result, indent=2))
