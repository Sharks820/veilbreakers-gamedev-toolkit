"""Unit tests for UV handler math functions.

Tests pure math functions from handlers/uv.py that do NOT require bpy/Blender.
Blender-dependent tests are marked with @pytest.mark.blender and skipped by default.
"""

import math
import os
import types
import pytest


# ---------------------------------------------------------------------------
# _polygon_area_2d tests
# ---------------------------------------------------------------------------


class FakeUV:
    """Minimal stand-in for mathutils.Vector 2D, used by _polygon_area_2d."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


def test_polygon_area_2d_unit_square():
    """Unit square (1x1) should have area 1.0."""
    from blender_addon.handlers.uv import _polygon_area_2d

    coords = [FakeUV(0, 0), FakeUV(1, 0), FakeUV(1, 1), FakeUV(0, 1)]
    assert abs(_polygon_area_2d(coords) - 1.0) < 1e-9


def test_polygon_area_2d_triangle():
    """Triangle with vertices (0,0), (4,0), (0,3) should have area 6.0."""
    from blender_addon.handlers.uv import _polygon_area_2d

    coords = [FakeUV(0, 0), FakeUV(4, 0), FakeUV(0, 3)]
    assert abs(_polygon_area_2d(coords) - 6.0) < 1e-9


def test_polygon_area_2d_degenerate_line():
    """Fewer than 3 coords should return 0.0."""
    from blender_addon.handlers.uv import _polygon_area_2d

    assert _polygon_area_2d([FakeUV(0, 0), FakeUV(1, 1)]) == 0.0
    assert _polygon_area_2d([FakeUV(0, 0)]) == 0.0
    assert _polygon_area_2d([]) == 0.0


def test_polygon_area_2d_pentagon():
    """Regular pentagon with circumradius 1 should have area ~2.378."""
    from blender_addon.handlers.uv import _polygon_area_2d

    n = 5
    coords = [
        FakeUV(math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n))
        for k in range(n)
    ]
    expected = (n / 2) * math.sin(2 * math.pi / n)  # standard formula
    assert abs(_polygon_area_2d(coords) - expected) < 1e-6


# ---------------------------------------------------------------------------
# Texel density formula tests
# ---------------------------------------------------------------------------


def test_texel_density_formula_basic():
    """TD = sqrt(uv_area / face_3d_area) * texture_size."""
    # uv_area=0.01, face_3d_area=1.0, texture_size=1024
    # TD = sqrt(0.01 / 1.0) * 1024 = 0.1 * 1024 = 102.4
    uv_area = 0.01
    face_3d_area = 1.0
    texture_size = 1024
    td = math.sqrt(uv_area / face_3d_area) * texture_size
    assert abs(td - 102.4) < 1e-6


def test_texel_density_formula_scaled():
    """Double the texture size should double the texel density."""
    uv_area = 0.04
    face_3d_area = 1.0
    td_512 = math.sqrt(uv_area / face_3d_area) * 512
    td_1024 = math.sqrt(uv_area / face_3d_area) * 1024
    assert abs(td_1024 / td_512 - 2.0) < 1e-9


def test_texel_density_formula_equal_areas():
    """When uv_area == face_3d_area, TD should equal texture_size."""
    uv_area = 1.0
    face_3d_area = 1.0
    texture_size = 2048
    td = math.sqrt(uv_area / face_3d_area) * texture_size
    assert abs(td - 2048.0) < 1e-6


class TestRuntimeUvHandlers:
    """Runtime-style UV handler tests using a fake Blender context."""

    class _FakeUvLayer:
        def __init__(self, name: str, active: bool = False):
            self.name = name
            self.active = active

    class _FakeUvLayers:
        def __init__(self, names: list[str], active_name: str | None = None):
            self._layers = {
                name: TestRuntimeUvHandlers._FakeUvLayer(
                    name, active=(name == active_name)
                )
                for name in names
            }
            self.active = self._layers.get(active_name) if active_name else None

        def __contains__(self, key):
            return key in self._layers

        def __getitem__(self, key):
            return self._layers[key]

        def __iter__(self):
            return iter(self._layers.values())

        def __len__(self):
            return len(self._layers)

    class _FakeMeshData:
        def __init__(self, active_uv_name: str = "UVMap"):
            self.uv_layers = TestRuntimeUvHandlers._FakeUvLayers(
                ["UVMap", "UV2"], active_name=active_uv_name
            )

    class _FakeObject:
        def __init__(self, name: str, active_uv_name: str = "UVMap"):
            self.name = name
            self.type = "MESH"
            self.data = TestRuntimeUvHandlers._FakeMeshData(active_uv_name)
            self.selected = False

        def select_set(self, state: bool):
            self.selected = state

    class _FakeOverride:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeContext:
        def __init__(self, old_active=None):
            self.view_layer = types.SimpleNamespace(
                objects=types.SimpleNamespace(active=old_active)
            )

        def temp_override(self, **kwargs):
            return TestRuntimeUvHandlers._FakeOverride()

    class _FakeObjectOps:
        def __init__(self):
            self.mode_calls = []

        def mode_set(self, mode):
            self.mode_calls.append(mode)

    class _FakeMeshOps:
        def __init__(self):
            self.select_calls = []

        def select_all(self, action):
            self.select_calls.append(action)

    class _FakeUvOps:
        def __init__(self):
            self.smart_project_calls = []
            self.unwrap_calls = []
            self.pack_calls = []

        def smart_project(self, **kwargs):
            self.smart_project_calls.append(kwargs)

        def unwrap(self, **kwargs):
            self.unwrap_calls.append(kwargs)

        def pack_islands(self, **kwargs):
            self.pack_calls.append(kwargs)

    def test_handle_unwrap_blender_smart_project_executes_operator_flow(self, monkeypatch):
        from blender_addon.handlers import uv

        old_active = self._FakeObject("OldActive")
        obj = self._FakeObject("PropA", active_uv_name="UVMap")
        fake_context = self._FakeContext(old_active=old_active)
        object_ops = self._FakeObjectOps()
        mesh_ops = self._FakeMeshOps()
        uv_ops = self._FakeUvOps()
        fake_bpy = types.SimpleNamespace(
            data=types.SimpleNamespace(objects={"PropA": obj}),
            context=fake_context,
            ops=types.SimpleNamespace(object=object_ops, mesh=mesh_ops, uv=uv_ops),
        )

        monkeypatch.setattr(uv, "bpy", fake_bpy)
        monkeypatch.setattr(uv, "get_3d_context_override", lambda: {"area": "VIEW_3D"})

        result = uv.handle_unwrap_blender({
            "object_name": "PropA",
            "method": "smart_project",
            "angle_limit": 55.0,
        })

        assert obj.selected is True
        assert object_ops.mode_calls == ["EDIT", "OBJECT"]
        assert mesh_ops.select_calls == ["SELECT"]
        assert len(uv_ops.smart_project_calls) == 1
        assert uv_ops.smart_project_calls[0]["island_margin"] == 0.001
        assert result["object_name"] == "PropA"
        assert result["method"] == "smart_project"
        assert result["uv_layer"] == "UVMap"
        assert fake_context.view_layer.objects.active is old_active

    def test_handle_pack_islands_executes_operator_flow(self, monkeypatch):
        from blender_addon.handlers import uv

        old_active = self._FakeObject("OldActive")
        obj = self._FakeObject("PropB", active_uv_name="UV2")
        fake_context = self._FakeContext(old_active=old_active)
        object_ops = self._FakeObjectOps()
        mesh_ops = self._FakeMeshOps()
        uv_ops = self._FakeUvOps()
        fake_bpy = types.SimpleNamespace(
            data=types.SimpleNamespace(objects={"PropB": obj}),
            context=fake_context,
            ops=types.SimpleNamespace(object=object_ops, mesh=mesh_ops, uv=uv_ops),
        )

        monkeypatch.setattr(uv, "bpy", fake_bpy)
        monkeypatch.setattr(uv, "get_3d_context_override", lambda: {"area": "VIEW_3D"})

        result = uv.handle_pack_islands({
            "object_name": "PropB",
            "margin": 0.02,
        })

        assert obj.selected is True
        assert object_ops.mode_calls == ["EDIT", "OBJECT"]
        assert mesh_ops.select_calls == ["SELECT"]
        assert uv_ops.pack_calls == [{"margin": 0.02}]
        assert result == {
            "object_name": "PropB",
            "margin": 0.02,
            "packed": True,
        }
        assert fake_context.view_layer.objects.active is old_active

    def test_handle_set_active_uv_layer_switches_layer(self, monkeypatch):
        from blender_addon.handlers import uv

        obj = self._FakeObject("PropC", active_uv_name="UVMap")
        fake_bpy = types.SimpleNamespace(
            data=types.SimpleNamespace(objects={"PropC": obj}),
        )

        monkeypatch.setattr(uv, "bpy", fake_bpy)

        result = uv.handle_set_active_uv_layer({
            "object_name": "PropC",
            "layer_name": "UV2",
        })

        assert obj.data.uv_layers["UV2"].active is True
        assert result == {
            "object_name": "PropC",
            "active_uv_layer": "UV2",
            "total_uv_layers": 2,
        }

    def test_handle_export_uv_layout_executes_operator_flow(self, monkeypatch):
        from blender_addon.handlers import uv

        class _FakeUuid:
            hex = "deadbeefcafebabe"

        old_active = self._FakeObject("OldActive")
        obj = self._FakeObject("PropD", active_uv_name="UVMap")
        fake_context = self._FakeContext(old_active=old_active)
        object_ops = self._FakeObjectOps()
        mesh_ops = self._FakeMeshOps()
        uv_ops = self._FakeUvOps()
        export_calls = []

        def _export_layout(**kwargs):
            export_calls.append(kwargs)

        uv_ops.export_layout = _export_layout
        fake_bpy = types.SimpleNamespace(
            data=types.SimpleNamespace(objects={"PropD": obj}),
            context=fake_context,
            ops=types.SimpleNamespace(object=object_ops, mesh=mesh_ops, uv=uv_ops),
        )

        monkeypatch.setattr(uv, "bpy", fake_bpy)
        monkeypatch.setattr(uv, "get_3d_context_override", lambda: {"area": "VIEW_3D"})
        monkeypatch.setattr(uv.tempfile, "gettempdir", lambda: "C:/Temp")
        monkeypatch.setattr(uv.uuid, "uuid4", lambda: _FakeUuid())

        result = uv.handle_export_uv_layout({
            "object_name": "PropD",
            "size": 512,
            "opacity": 0.4,
        })

        assert obj.selected is True
        assert object_ops.mode_calls == ["EDIT", "OBJECT"]
        assert mesh_ops.select_calls == ["SELECT"]
        assert len(export_calls) == 1
        assert export_calls[0]["mode"] == "PNG"
        assert export_calls[0]["size"] == (512, 512)
        assert export_calls[0]["opacity"] == 0.4
        assert result == {
            "filepath": os.path.join("C:/Temp", "vb_uv_layout_deadbeef.png"),
            "size": 512,
            "format": "png",
        }
        assert fake_context.view_layer.objects.active is old_active

    def test_handle_export_uv_layout_uses_fallback_without_view_override(self, monkeypatch):
        from blender_addon.handlers import uv

        obj = self._FakeObject("PropFallback", active_uv_name="UVMap")
        fake_bpy = types.SimpleNamespace(
            data=types.SimpleNamespace(objects={"PropFallback": obj}),
        )
        fallback_calls = []

        monkeypatch.setattr(uv, "bpy", fake_bpy)
        monkeypatch.setattr(uv, "get_3d_context_override", lambda: None)
        monkeypatch.setattr(uv, "_render_uv_layout_fallback", lambda obj_arg, filepath, size: (
            fallback_calls.append({
                "object_name": obj_arg.name,
                "filepath": filepath,
                "size": size,
            }) or {
                "filepath": filepath,
                "size": size,
                "format": "png",
                "method": "pillow_fallback",
            }
        ))

        result = uv.handle_export_uv_layout({
            "object_name": "PropFallback",
            "size": 256,
        })

        assert len(fallback_calls) == 1
        assert fallback_calls[0]["object_name"] == "PropFallback"
        assert fallback_calls[0]["size"] == 256
        assert result["method"] == "pillow_fallback"
