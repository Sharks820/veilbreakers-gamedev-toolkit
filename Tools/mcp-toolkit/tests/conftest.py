"""Pytest configuration for MCP toolkit tests.

Adds blender_addon and veilbreakers_mcp to the Python path and provides strict
stub modules for bpy/bmesh/mathutils so that pure-logic functions can be tested
without Blender.

Uses fake_bpy (strict stubs) -- unknown attribute access raises
AttributeError rather than silently returning more mocks.
"""

import sys
from pathlib import Path

# Add the mcp-toolkit root so `blender_addon` is importable as a package.
_toolkit_root = Path(__file__).resolve().parent.parent
if str(_toolkit_root) not in sys.path:
    sys.path.insert(0, str(_toolkit_root))

# Add src so `veilbreakers_mcp` is importable as a package.
_src_root = _toolkit_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

# Install strict Blender stubs (replaces old permissive mock approach)
import fake_bpy

fake_bpy.install()
