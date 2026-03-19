"""Pytest configuration for MCP toolkit tests.

Adds blender_addon to the Python path and provides mock modules
for bpy/bmesh so that pure-logic functions can be tested without Blender.
"""

import sys
import types
from pathlib import Path

# Add the mcp-toolkit root so `blender_addon` is importable as a package.
_toolkit_root = Path(__file__).resolve().parent.parent
if str(_toolkit_root) not in sys.path:
    sys.path.insert(0, str(_toolkit_root))

# Provide stub modules for Blender-only dependencies so that
# pure-logic imports (e.g. _compute_grade) succeed outside Blender.
for mod_name in ("bpy", "bmesh", "mathutils"):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
