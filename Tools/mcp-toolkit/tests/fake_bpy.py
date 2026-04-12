"""Strict bpy/bmesh/mathutils stubs for testing without Blender.

Unlike the old MagicMock approach, these stubs raise AttributeError for any
attribute not explicitly defined.  This catches real bugs in bpy-touching code
instead of silently returning more MagicMocks.

Usage (from conftest.py):
    import fake_bpy
    fake_bpy.install()
"""

from __future__ import annotations

import math
import sys
import types
from typing import Any, Sequence, Tuple


# ---------------------------------------------------------------------------
# StrictModule: the key abstraction
# ---------------------------------------------------------------------------

class StrictModule(types.ModuleType):
    """A module that raises AttributeError for any attribute not explicitly set.

    This is the opposite of MagicMock -- unknown attribute access fails loudly.
    """

    def __getattr__(self, name: str) -> Any:
        # Allow dunder attributes through to default behaviour
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(
                f"module '{self.__name__}' has no attribute '{name}'"
            )
        raise AttributeError(
            f"module '{self.__name__}' has no attribute '{name}'"
        )


# ---------------------------------------------------------------------------
# Lightweight mathutils types
# ---------------------------------------------------------------------------

class Vector:
    """Minimal Vector matching Blender's mathutils.Vector interface."""

    __slots__ = ("_data",)

    def __init__(self, data: Sequence[float] = (0.0, 0.0, 0.0)):
        self._data = list(float(v) for v in data)

    # Properties
    @property
    def x(self) -> float:
        return self._data[0]

    @x.setter
    def x(self, val: float) -> None:
        self._data[0] = float(val)

    @property
    def y(self) -> float:
        return self._data[1] if len(self._data) > 1 else 0.0

    @y.setter
    def y(self, val: float) -> None:
        if len(self._data) > 1:
            self._data[1] = float(val)

    @property
    def z(self) -> float:
        return self._data[2] if len(self._data) > 2 else 0.0

    @z.setter
    def z(self, val: float) -> None:
        if len(self._data) > 2:
            self._data[2] = float(val)

    @property
    def w(self) -> float:
        return self._data[3] if len(self._data) > 3 else 0.0

    @property
    def length(self) -> float:
        return math.sqrt(sum(v * v for v in self._data))

    def normalized(self) -> "Vector":
        ln = self.length
        if ln == 0:
            return Vector([0.0] * len(self._data))
        return Vector([v / ln for v in self._data])

    def copy(self) -> "Vector":
        return Vector(list(self._data))

    def dot(self, other: "Vector") -> float:
        return sum(a * b for a, b in zip(self._data, other._data))

    def cross(self, other: "Vector") -> "Vector":
        if len(self._data) != 3 or len(other._data) != 3:
            raise ValueError("Cross product requires 3D vectors")
        a, b = self._data, other._data
        return Vector([
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ])

    # Container protocol
    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx: int) -> float:
        return self._data[idx]

    def __setitem__(self, idx: int, val: float) -> None:
        self._data[idx] = float(val)

    def __iter__(self):
        return iter(self._data)

    # Arithmetic
    def __add__(self, other: "Vector") -> "Vector":
        return Vector([a + b for a, b in zip(self._data, other._data)])

    def __sub__(self, other: "Vector") -> "Vector":
        return Vector([a - b for a, b in zip(self._data, other._data)])

    def __mul__(self, scalar: float) -> "Vector":
        if isinstance(scalar, (int, float)):
            return Vector([v * scalar for v in self._data])
        return NotImplemented

    def __rmul__(self, scalar: float) -> "Vector":
        return self.__mul__(scalar)

    def __neg__(self) -> "Vector":
        return Vector([-v for v in self._data])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Vector):
            return self._data == other._data
        return NotImplemented

    def __repr__(self) -> str:
        return f"Vector({self._data})"


class Euler:
    """Minimal Euler rotation stub."""

    __slots__ = ("x", "y", "z", "order")

    def __init__(self, values: Sequence[float] = (0.0, 0.0, 0.0), order: str = "XYZ"):
        vals = list(values)
        self.x = float(vals[0]) if len(vals) > 0 else 0.0
        self.y = float(vals[1]) if len(vals) > 1 else 0.0
        self.z = float(vals[2]) if len(vals) > 2 else 0.0
        self.order = order

    def copy(self) -> "Euler":
        return Euler((self.x, self.y, self.z), self.order)

    def __repr__(self) -> str:
        return f"Euler(({self.x}, {self.y}, {self.z}), '{self.order}')"


class Matrix:
    """Minimal Matrix stub with Identity classmethod."""

    __slots__ = ("_rows", "_size")

    def __init__(self, rows: Sequence[Sequence[float]] | None = None):
        if rows is not None:
            self._rows = [list(r) for r in rows]
            self._size = len(self._rows)
        else:
            self._rows = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
            self._size = 4

    @classmethod
    def Identity(cls, size: int) -> "Matrix":
        rows = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
        return cls(rows)

    @classmethod
    def Translation(cls, vec: Sequence[float]) -> "Matrix":
        m = cls.Identity(4)
        for i, v in enumerate(vec):
            if i < 3:
                m._rows[i][3] = float(v)
        return m

    @classmethod
    def Rotation(cls, angle: float, size: int, axis: str = "Z") -> "Matrix":
        return cls.Identity(size)

    @classmethod
    def Scale(cls, factor: float, size: int, axis: Sequence[float] | None = None) -> "Matrix":
        return cls.Identity(size)

    def copy(self) -> "Matrix":
        return Matrix([list(r) for r in self._rows])

    def __matmul__(self, other: Any) -> Any:
        if isinstance(other, Matrix):
            return self.copy()
        if isinstance(other, Vector):
            return other.copy()
        return NotImplemented

    def __getitem__(self, idx: int) -> list:
        return self._rows[idx]

    def __repr__(self) -> str:
        return f"Matrix({self._rows})"


class Quaternion:
    """Minimal Quaternion stub."""

    __slots__ = ("w", "x", "y", "z")

    def __init__(self, values: Sequence[float] = (1.0, 0.0, 0.0, 0.0)):
        vals = list(values)
        self.w = float(vals[0]) if len(vals) > 0 else 1.0
        self.x = float(vals[1]) if len(vals) > 1 else 0.0
        self.y = float(vals[2]) if len(vals) > 2 else 0.0
        self.z = float(vals[3]) if len(vals) > 3 else 0.0

    def copy(self) -> "Quaternion":
        return Quaternion((self.w, self.x, self.y, self.z))

    def __repr__(self) -> str:
        return f"Quaternion(({self.w}, {self.x}, {self.y}, {self.z}))"


class Color:
    """Minimal Color stub."""

    __slots__ = ("r", "g", "b")

    def __init__(self, values: Sequence[float] = (0.0, 0.0, 0.0)):
        vals = list(values)
        self.r = float(vals[0]) if len(vals) > 0 else 0.0
        self.g = float(vals[1]) if len(vals) > 1 else 0.0
        self.b = float(vals[2]) if len(vals) > 2 else 0.0

    def __repr__(self) -> str:
        return f"Color(({self.r}, {self.g}, {self.b}))"


# ---------------------------------------------------------------------------
# Stub base classes for bpy.types (supports class inheritance)
# ---------------------------------------------------------------------------

class _BpyTypeBase:
    """Base for bpy.types stub classes that support __mro_entries__."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)


class Panel(_BpyTypeBase):
    pass


class Operator(_BpyTypeBase):
    pass


class PropertyGroup(_BpyTypeBase):
    pass


class Menu(_BpyTypeBase):
    pass


class Header(_BpyTypeBase):
    pass


class UIList(_BpyTypeBase):
    pass


class Node(_BpyTypeBase):
    pass


class NodeTree(_BpyTypeBase):
    pass


class AddonPreferences(_BpyTypeBase):
    pass


class Object:
    """Stub for bpy.types.Object (used in isinstance checks)."""
    pass


class Mesh:
    """Stub for bpy.types.Mesh."""
    pass


class Material:
    """Stub for bpy.types.Material."""
    pass


class Scene:
    """Stub for bpy.types.Scene."""
    pass


class Collection:
    """Stub for bpy.types.Collection."""
    pass


class Image:
    """Stub for bpy.types.Image."""
    pass


# ---------------------------------------------------------------------------
# Property function stubs
# ---------------------------------------------------------------------------

def _prop_stub(**kw: Any) -> None:
    """All bpy.props property functions return None (annotation-only in stubs)."""
    return None


# ---------------------------------------------------------------------------
# Module builders
# ---------------------------------------------------------------------------

def _build_bpy() -> StrictModule:
    """Build the strict bpy stub module hierarchy."""
    bpy = StrictModule("bpy")

    # bpy.types with common base classes
    bpy_types = StrictModule("bpy.types")
    for cls_name in (
        "Panel", "Operator", "PropertyGroup", "Menu", "Header", "UIList",
        "Node", "NodeTree", "AddonPreferences", "Object", "Mesh",
        "Material", "Scene", "Collection", "Image",
    ):
        setattr(bpy_types, cls_name, globals()[cls_name])
    bpy.types = bpy_types

    # bpy.props with all property functions
    bpy_props = StrictModule("bpy.props")
    _prop_names = (
        "StringProperty", "IntProperty", "FloatProperty",
        "BoolProperty", "EnumProperty", "CollectionProperty",
        "PointerProperty", "FloatVectorProperty",
        "IntVectorProperty", "BoolVectorProperty",
    )
    for pname in _prop_names:
        setattr(bpy_props, pname, _prop_stub)
        setattr(bpy, pname, _prop_stub)
    bpy.props = bpy_props

    # bpy.data, bpy.context, bpy.ops (strict -- error on access)
    bpy.data = StrictModule("bpy.data")
    bpy.context = StrictModule("bpy.context")
    bpy.ops = StrictModule("bpy.ops")

    # bpy.utils
    bpy_utils = StrictModule("bpy.utils")
    bpy_utils.register_class = lambda cls: None
    bpy_utils.unregister_class = lambda cls: None
    bpy.utils = bpy_utils

    # bpy.app
    bpy_app = StrictModule("bpy.app")
    bpy_app.version = (4, 0, 0)
    bpy_app.version_string = "4.0.0"
    bpy_app.timers = StrictModule("bpy.app.timers")
    bpy_app.handlers = StrictModule("bpy.app.handlers")
    bpy.app = bpy_app

    return bpy


def _build_bmesh() -> StrictModule:
    """Build the strict bmesh stub module hierarchy."""
    bm = StrictModule("bmesh")
    bm.types = StrictModule("bmesh.types")
    bm.ops = StrictModule("bmesh.ops")
    # bmesh.new intentionally NOT defined -- raises AttributeError
    return bm


def _build_mathutils() -> StrictModule:
    """Build the strict mathutils stub module."""
    mu = StrictModule("mathutils")
    mu.Vector = Vector
    mu.Euler = Euler
    mu.Matrix = Matrix
    mu.Quaternion = Quaternion
    mu.Color = Color
    mu.noise = StrictModule("mathutils.noise")
    return mu


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_BLENDER_MODS = (
    "bpy", "bpy.types", "bpy.props", "bpy.utils", "bpy.app",
    "bmesh", "bmesh.types", "bmesh.ops",
    "mathutils", "mathutils.noise",
    "bpy_extras", "bpy_extras.io_utils",
    "gpu", "gpu_extras", "bl_math", "idprop",
)


def install() -> None:
    """Install all strict Blender stub modules into sys.modules.

    Call this once at test startup (e.g., from conftest.py) to replace
    the old MagicMock stubs with strict versions.
    """
    bpy = _build_bpy()
    bmesh = _build_bmesh()
    mathutils = _build_mathutils()

    # Map of module name -> module object
    modules = {
        "bpy": bpy,
        "bpy.types": bpy.types,
        "bpy.props": bpy.props,
        "bpy.utils": bpy.utils,
        "bpy.app": bpy.app,
        "bmesh": bmesh,
        "bmesh.types": bmesh.types,
        "bmesh.ops": bmesh.ops,
        "mathutils": mathutils,
        "mathutils.noise": mathutils.noise,
        "bpy_extras": StrictModule("bpy_extras"),
        "bpy_extras.io_utils": StrictModule("bpy_extras.io_utils"),
        "gpu": StrictModule("gpu"),
        "gpu_extras": StrictModule("gpu_extras"),
        "bl_math": StrictModule("bl_math"),
        "idprop": StrictModule("idprop"),
    }

    # Wire up bpy_extras parent-child
    modules["bpy_extras"].io_utils = modules["bpy_extras.io_utils"]

    for name, mod in modules.items():
        sys.modules[name] = mod
