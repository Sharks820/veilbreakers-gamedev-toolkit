"""Full test of VB bridge connections."""
import sys, os, traceback, json
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vb_bridge import *

print("=== VeilBreakers Cowork Bridge Test ===", flush=True)

try:
    r = ping_blender()
    print(f"[OK] Blender ping: {r}", flush=True)
except Exception as e:
    print(f"[FAIL] Blender: {e}", flush=True)

try:
    info = scene_info()
    obj_count = len(info.get("objects", [])) if isinstance(info, dict) else "?"
    print(f"[OK] Blender scene: {obj_count} objects", flush=True)
except Exception as e:
    print(f"[FAIL] Scene: {e}", flush=True)

try:
    r = unity("ping")
    print(f"[OK] Unity ping: {r}", flush=True)
except Exception as e:
    print(f"[FAIL] Unity: {e}", flush=True)

try:
    logs = unity("console_logs", log_filter="all", log_count=3)
    count = len(logs) if isinstance(logs, list) else "response"
    print(f"[OK] Unity logs: {count}", flush=True)
except Exception as e:
    print(f"[FAIL] Unity logs: {e}", flush=True)

print("=== Done ===", flush=True)
