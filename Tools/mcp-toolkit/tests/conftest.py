"""Pytest configuration for MCP toolkit tests.

Adds blender_addon to the Python path and provides mock modules
for bpy/bmesh so that pure-logic functions can be tested without Blender.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Add the mcp-toolkit root so `blender_addon` is importable as a package.
_toolkit_root = Path(__file__).resolve().parent.parent
if str(_toolkit_root) not in sys.path:
    sys.path.insert(0, str(_toolkit_root))


def _make_stub(name: str) -> types.ModuleType:
    """Create a stub module that returns MagicMock for any attribute access.

    This lets handler modules do ``bpy.types.Object``, ``bpy.data.objects``,
    ``bmesh.ops.create_cube``, ``mathutils.Vector``, etc. without crashing
    during import — while still allowing pure-logic tests to run.
    """
    mod = types.ModuleType(name)

    class _AttrProxy(MagicMock):
        """MagicMock that also works as a class base (for dataclass/enum)."""

        def __mro_entries__(self, bases):
            return (object,)

    # Provide nested attribute access that doesn't crash
    mod.__dict__["__getattr__"] = lambda attr: _AttrProxy(name=f"{name}.{attr}")

    # Key sub-modules that handlers import directly
    if name == "bpy":
        mod.types = _AttrProxy(name="bpy.types")
        mod.data = _AttrProxy(name="bpy.data")
        mod.context = _AttrProxy(name="bpy.context")
        mod.ops = _AttrProxy(name="bpy.ops")
        mod.props = _AttrProxy(name="bpy.props")
        mod.utils = _AttrProxy(name="bpy.utils")
        mod.app = _AttrProxy(name="bpy.app")
        # bpy.props functions used in addon registration
        for prop_fn in ("StringProperty", "IntProperty", "FloatProperty",
                        "BoolProperty", "EnumProperty", "CollectionProperty",
                        "PointerProperty", "FloatVectorProperty",
                        "IntVectorProperty", "BoolVectorProperty"):
            setattr(mod.props, prop_fn, lambda **kw: None)
            setattr(mod, prop_fn, lambda **kw: None)
    elif name == "bmesh":
        mod.types = _AttrProxy(name="bmesh.types")
        mod.ops = _AttrProxy(name="bmesh.ops")
        mod.new = MagicMock
    elif name == "mathutils":
        # Provide basic Vector/Matrix/Euler/Quaternion stubs
        mod.Vector = MagicMock
        mod.Matrix = MagicMock
        mod.Euler = MagicMock
        mod.Quaternion = MagicMock
        mod.Color = MagicMock
        mod.noise = _AttrProxy(name="mathutils.noise")

    return mod


# Install stubs for all Blender-only modules
_BLENDER_MODS = (
    "bpy", "bpy.types", "bpy.props", "bpy.utils", "bpy.app",
    "bmesh", "bmesh.types", "bmesh.ops",
    "mathutils", "mathutils.noise",
    "bpy_extras", "bpy_extras.io_utils",
    "gpu", "gpu_extras", "bl_math", "idprop",
)

for mod_name in _BLENDER_MODS:
    if mod_name not in sys.modules:
        # For sub-modules like "bpy.types", create the parent first
        parts = mod_name.split(".")
        if len(parts) > 1:
            parent_name = parts[0]
            if parent_name not in sys.modules:
                sys.modules[parent_name] = _make_stub(parent_name)
            parent = sys.modules[parent_name]
            child = getattr(parent, parts[1], None)
            if child is not None:
                sys.modules[mod_name] = child
            else:
                sys.modules[mod_name] = _make_stub(mod_name)
        else:
            sys.modules[mod_name] = _make_stub(mod_name)
