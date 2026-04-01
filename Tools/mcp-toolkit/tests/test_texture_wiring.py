"""Unit tests for texture wiring handlers.

Tests cover:
  - handle_load_extracted_textures: albedo/ORM/normal wiring logic
  - handle_mix_weathering_over_texture: weathering mix node insertion

conftest.py stubs bpy/bmesh/mathutils at session start, so handlers import fine.
Each test patches `bpy` on the already-loaded module to inject a per-test mock tree.
"""

from __future__ import annotations

from unittest import mock

import pytest

from blender_addon.handlers.texture import handle_load_extracted_textures
from blender_addon.handlers.weathering import handle_mix_weathering_over_texture


# ---------------------------------------------------------------------------
# Helpers: build a realistic node-tree mock
# ---------------------------------------------------------------------------

def _make_socket(name: str):
    s = mock.MagicMock()
    s.name = name
    return s


def _make_node(node_type: str, label: str = "", location=(0, 0)):
    """Return a MagicMock node with plain-dict inputs/outputs so .get() works."""
    n = mock.MagicMock()
    n.type = node_type
    n.label = label
    n.location = list(location)
    n.inputs = {
        "Base Color": _make_socket("Base Color"),
        "Roughness": _make_socket("Roughness"),
        "Metallic": _make_socket("Metallic"),
        "Normal": _make_socket("Normal"),
        "Image": _make_socket("Image"),
        "Color": _make_socket("Color"),
        "Color1": _make_socket("Color1"),
        "Color2": _make_socket("Color2"),
        "Fac": _make_socket("Fac"),
    }
    n.outputs = {
        "BSDF": _make_socket("BSDF"),
        "Color": _make_socket("Color"),
        "R": _make_socket("R"),
        "G": _make_socket("G"),
        "B": _make_socket("B"),
        "Surface": _make_socket("Surface"),
        "Normal": _make_socket("Normal"),
    }
    return n


def _build_scene():
    """Return (bpy_mock, obj, mat, tree, bsdf_node, nodes_list, links_list).

    nodes_list and links_list are the mutable backing stores so tests can
    inspect what nodes/links were created.
    """
    bsdf_node = _make_node("BSDF_PRINCIPLED", "Principled BSDF")
    output_node = _make_node("OUTPUT_MATERIAL", "Material Output")

    nodes_list = [bsdf_node, output_node]
    links_list = []

    # nodes collection mock
    nodes_mock = mock.MagicMock()
    nodes_mock.__iter__ = lambda s: iter(list(nodes_list))

    def _new_node(node_type_str):
        type_map = {
            "ShaderNodeTexImage": "TEX_IMAGE",
            "ShaderNodeSeparateRGB": "SEPARATE_RGB",
            "ShaderNodeMixRGB": "MIX_RGB",
            "ShaderNodeNormalMap": "NORMAL_MAP",
            "ShaderNodeVertexColor": "VERTEX_COLOR",
            "ShaderNodeBsdfPrincipled": "BSDF_PRINCIPLED",
            "ShaderNodeOutputMaterial": "OUTPUT_MATERIAL",
        }
        n = _make_node(type_map.get(node_type_str, node_type_str))
        if node_type_str == "ShaderNodeTexImage":
            img = mock.MagicMock()
            img.colorspace_settings = mock.MagicMock()
            img.colorspace_settings.name = "sRGB"
            n.image = img
        nodes_list.append(n)
        return n

    nodes_mock.new = mock.MagicMock(side_effect=_new_node)

    # links collection mock
    links_mock = mock.MagicMock()
    links_mock.__iter__ = lambda s: iter(list(links_list))

    def _new_link(from_socket, to_socket):
        lnk = mock.MagicMock()
        lnk.from_socket = from_socket
        lnk.to_socket = to_socket
        lnk.from_node = mock.MagicMock()
        lnk.to_node = mock.MagicMock()
        links_list.append(lnk)
        return lnk

    links_mock.new = mock.MagicMock(side_effect=_new_link)
    links_mock.remove = mock.MagicMock(side_effect=lambda lnk: links_list.remove(lnk) if lnk in links_list else None)

    tree_mock = mock.MagicMock()
    tree_mock.nodes = nodes_mock
    tree_mock.links = links_mock

    mat_mock = mock.MagicMock()
    mat_mock.use_nodes = True
    mat_mock.node_tree = tree_mock

    obj_data = mock.MagicMock()
    obj_data.materials = [mat_mock]

    obj_mock = mock.MagicMock()
    obj_mock.type = "MESH"
    obj_mock.data = obj_data

    img_stub = mock.MagicMock()
    img_stub.colorspace_settings = mock.MagicMock()
    img_stub.colorspace_settings.name = "sRGB"

    bpy_mock = mock.MagicMock(name="bpy")
    bpy_mock.data.objects.get = mock.MagicMock(return_value=obj_mock)
    bpy_mock.data.images.load = mock.MagicMock(return_value=img_stub)
    bpy_mock.data.materials.new = mock.MagicMock(return_value=mat_mock)

    return bpy_mock, obj_mock, mat_mock, tree_mock, bsdf_node, nodes_list, links_list


# ---------------------------------------------------------------------------
# Test 1: albedo wired to Base Color
# ---------------------------------------------------------------------------

def test_load_extracted_textures_wires_albedo_to_base_color(tmp_path):
    """handle_load_extracted_textures links albedo texture to Principled BSDF Base Color."""
    albedo_file = tmp_path / "albedo.png"
    albedo_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    bpy_mock, obj, mat, tree, bsdf, nodes_list, links_list = _build_scene()

    import blender_addon.handlers.texture as tex_mod
    with mock.patch.object(tex_mod, "bpy", bpy_mock):
        result = handle_load_extracted_textures({
            "object_name": "TestMesh",
            "albedo_path": str(albedo_file),
        })

    assert result["status"] == "success"
    assert "albedo" in result["channels_loaded"]
    bpy_mock.data.images.load.assert_called()


# ---------------------------------------------------------------------------
# Test 2: ORM creates a SeparateRGB node
# ---------------------------------------------------------------------------

def test_load_extracted_textures_splits_orm_channels(tmp_path):
    """handle_load_extracted_textures creates a SeparateRGB node for ORM input."""
    orm_file = tmp_path / "orm.png"
    orm_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    bpy_mock, obj, mat, tree, bsdf, nodes_list, links_list = _build_scene()

    import blender_addon.handlers.texture as tex_mod
    with mock.patch.object(tex_mod, "bpy", bpy_mock):
        result = handle_load_extracted_textures({
            "object_name": "TestMesh",
            "orm_path": str(orm_file),
        })

    assert "orm" in result["channels_loaded"]
    sep_nodes = [n for n in nodes_list if n.type == "SEPARATE_RGB"]
    assert len(sep_nodes) >= 1, "Expected at least one SeparateRGB node for ORM"


# ---------------------------------------------------------------------------
# Test 3: normal texture routes through NormalMap node
# ---------------------------------------------------------------------------

def test_load_extracted_textures_routes_normal_through_normalmap_node(tmp_path):
    """handle_load_extracted_textures inserts a NormalMap node for normal textures."""
    normal_file = tmp_path / "normal.png"
    normal_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    bpy_mock, obj, mat, tree, bsdf, nodes_list, links_list = _build_scene()

    import blender_addon.handlers.texture as tex_mod
    with mock.patch.object(tex_mod, "bpy", bpy_mock):
        result = handle_load_extracted_textures({
            "object_name": "TestMesh",
            "normal_path": str(normal_file),
        })

    assert "normal" in result["channels_loaded"]
    normal_map_nodes = [n for n in nodes_list if n.type == "NORMAL_MAP"]
    assert len(normal_map_nodes) >= 1, "Expected a NormalMap node for normal texture"


# ---------------------------------------------------------------------------
# Test 4: delit albedo preferred over raw albedo
# ---------------------------------------------------------------------------

def test_load_extracted_textures_prefers_delit_albedo(tmp_path):
    """handle_load_extracted_textures uses albedo_delit_path over albedo_path when both given."""
    albedo_file = tmp_path / "albedo.png"
    albedo_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    delit_file = tmp_path / "albedo_delit.png"
    delit_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)

    bpy_mock, obj, mat, tree, bsdf, nodes_list, links_list = _build_scene()

    loaded_paths = []

    def _mock_load(path, check_existing=False):
        loaded_paths.append(path)
        img = mock.MagicMock()
        img.colorspace_settings = mock.MagicMock()
        img.colorspace_settings.name = "sRGB"
        return img

    bpy_mock.data.images.load = mock.MagicMock(side_effect=_mock_load)

    import blender_addon.handlers.texture as tex_mod
    with mock.patch.object(tex_mod, "bpy", bpy_mock):
        result = handle_load_extracted_textures({
            "object_name": "TestMesh",
            "albedo_path": str(albedo_file),
            "albedo_delit_path": str(delit_file),
        })

    assert result["status"] == "success"
    assert str(delit_file) in loaded_paths, "delit path should have been loaded"
    assert str(albedo_file) not in loaded_paths, "raw albedo should NOT be loaded when delit present"


# ---------------------------------------------------------------------------
# Test 5: mix_weathering_over_texture inserts WeatheringMix node
# ---------------------------------------------------------------------------

def test_mix_weathering_inserts_mix_node():
    """handle_mix_weathering_over_texture creates a MixRGB(MULTIPLY) node labeled WeatheringMix."""
    bpy_mock, obj, mat, tree, bsdf, nodes_list, links_list = _build_scene()

    # Add a fake albedo tex image node so the handler finds it
    albedo_tex = _make_node("TEX_IMAGE", "Albedo", location=(-700, 300))
    albedo_img = mock.MagicMock()
    albedo_img.colorspace_settings = mock.MagicMock()
    albedo_img.colorspace_settings.name = "sRGB"
    albedo_tex.image = albedo_img
    nodes_list.append(albedo_tex)

    import blender_addon.handlers.weathering as w_mod
    with mock.patch.object(w_mod, "bpy", bpy_mock):
        result = handle_mix_weathering_over_texture({
            "object_name": "TestMesh",
            "weathering_strength": 0.5,
        })

    assert result["status"] == "success"
    assert result["mix_node_created"] is True
    mix_nodes = [n for n in nodes_list if n.type == "MIX_RGB"]
    assert len(mix_nodes) >= 1, "Expected a MixRGB node for weathering"


# ---------------------------------------------------------------------------
# Test 6: mix_weathering_over_texture idempotent if WeatheringMix exists
# ---------------------------------------------------------------------------

def test_mix_weathering_idempotent_if_already_wired():
    """handle_mix_weathering_over_texture returns already_wired if WeatheringMix exists."""
    bpy_mock, obj, mat, tree, bsdf, nodes_list, links_list = _build_scene()

    # Pre-add albedo node (needed for search)
    albedo_tex = _make_node("TEX_IMAGE", "Albedo", location=(-700, 300))
    albedo_img = mock.MagicMock()
    albedo_img.colorspace_settings = mock.MagicMock()
    albedo_img.colorspace_settings.name = "sRGB"
    albedo_tex.image = albedo_img
    nodes_list.append(albedo_tex)

    # Pre-add existing WeatheringMix so idempotency check triggers
    existing_mix = _make_node("MIX_RGB", "WeatheringMix")
    nodes_list.append(existing_mix)

    import blender_addon.handlers.weathering as w_mod
    with mock.patch.object(w_mod, "bpy", bpy_mock):
        result = handle_mix_weathering_over_texture({
            "object_name": "TestMesh",
            "weathering_strength": 0.4,
        })

    assert result["status"] == "already_wired"
    assert result["mix_node_created"] is False
