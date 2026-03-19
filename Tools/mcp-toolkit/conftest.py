"""Root conftest for mcp-toolkit tests.

Adds the project root to sys.path so that `blender_addon` is importable,
and provides a minimal bpy mock so handler modules that `import bpy` at the
top level can be loaded in a test environment without Blender.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Add mcp-toolkit root so `blender_addon` package is importable
_project_root = str(Path(__file__).parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Provide a minimal bpy stub so `import bpy` doesn't crash outside Blender.
# Handlers that actually USE bpy will fail at runtime (guarded by @pytest.mark.blender),
# but pure-math helpers can be imported and tested.
if "bpy" not in sys.modules:
    bpy_mock = MagicMock(name="bpy")
    sys.modules["bpy"] = bpy_mock

# Same for bmesh -- some handler modules import it at module level
if "bmesh" not in sys.modules:
    bmesh_mock = MagicMock(name="bmesh")
    sys.modules["bmesh"] = bmesh_mock

# mathutils stub -- provide a real-enough Vector if needed
if "mathutils" not in sys.modules:
    mathutils_mock = MagicMock(name="mathutils")
    sys.modules["mathutils"] = mathutils_mock
