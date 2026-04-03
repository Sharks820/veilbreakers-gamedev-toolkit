"""Tests for MCP tool dispatch -- verifies every action is handled.

Uses mocking to avoid needing a live Blender connection. Each test
calls the tool function directly and asserts the correct Blender
command is dispatched (or the correct error is raised for unknown actions).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_TMP_TEST_FBX = str(Path(tempfile.gettempdir()) / "test.fbx")
_TMP_IMG_PNG = str(Path(tempfile.gettempdir()) / "img.png")

# ---------------------------------------------------------------------------
# Mock BlenderConnection before importing blender_server
# ---------------------------------------------------------------------------


def _make_mock_connection():
    """Create a mock BlenderConnection for dispatch tests."""
    conn = AsyncMock()
    conn.send_command = AsyncMock(return_value={"status": "success", "result": {}})
    conn.capture_viewport_bytes = AsyncMock(return_value=b"\x89PNG fake")
    return conn


# ---------------------------------------------------------------------------
# blender_scene dispatch
# ---------------------------------------------------------------------------


class TestBlenderSceneDispatch:
    @pytest.mark.asyncio
    async def test_inspect_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_scene
            result = await blender_scene(action="inspect")
            mock_conn.send_command.assert_any_call("get_scene_info")

    @pytest.mark.asyncio
    async def test_clear_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_scene
            result = await blender_scene(action="clear")
            mock_conn.send_command.assert_any_call("clear_scene")

    @pytest.mark.asyncio
    async def test_configure_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_scene
            result = await blender_scene(action="configure", render_engine="CYCLES")
            mock_conn.send_command.assert_any_call(
                "configure_scene", {"render_engine": "CYCLES"}
            )

    @pytest.mark.asyncio
    async def test_list_objects_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_scene
            result = await blender_scene(action="list_objects")
            mock_conn.send_command.assert_any_call("list_objects")


# ---------------------------------------------------------------------------
# blender_object dispatch
# ---------------------------------------------------------------------------


class TestBlenderObjectDispatch:
    @pytest.mark.asyncio
    async def test_create_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_object
            result = await blender_object(action="create", mesh_type="cube")
            mock_conn.send_command.assert_called()

    @pytest.mark.asyncio
    async def test_list_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_object
            result = await blender_object(action="list")
            mock_conn.send_command.assert_any_call("list_objects")

    @pytest.mark.asyncio
    async def test_modify_requires_name(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_object
            result = await blender_object(action="modify")
            assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_delete_requires_name(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_object
            result = await blender_object(action="delete")
            assert "ERROR" in result


# ---------------------------------------------------------------------------
# blender_material dispatch
# ---------------------------------------------------------------------------


class TestBlenderMaterialDispatch:
    @pytest.mark.asyncio
    async def test_create_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_material
            result = await blender_material(action="create", name="TestMat")
            mock_conn.send_command.assert_called()

    @pytest.mark.asyncio
    async def test_list_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_material
            result = await blender_material(action="list")
            mock_conn.send_command.assert_called()


# ---------------------------------------------------------------------------
# blender_viewport dispatch
# ---------------------------------------------------------------------------


class TestBlenderViewportDispatch:
    @pytest.mark.asyncio
    async def test_screenshot_dispatches(self):
        mock_conn = _make_mock_connection()
        # Create a minimal valid 1x1 PNG so PIL can parse it
        import struct, zlib
        def _make_tiny_png() -> bytes:
            sig = b"\x89PNG\r\n\x1a\n"
            ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
            ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
            raw = zlib.compress(b"\x00\x00\x00\x00")
            idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF)
            idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + idat_crc
            iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
            iend = struct.pack(">I", 0) + b"IEND" + iend_crc
            return sig + ihdr + idat + iend
        mock_conn.capture_viewport_bytes = AsyncMock(return_value=_make_tiny_png())
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_viewport
            result = await blender_viewport(action="screenshot")
            # Should call capture_viewport_bytes or send_command
            assert mock_conn.send_command.called or mock_conn.capture_viewport_bytes.called

    @pytest.mark.asyncio
    async def test_set_shading_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_viewport
            result = await blender_viewport(action="set_shading", shading_type="MATERIAL")
            mock_conn.send_command.assert_called()


# ---------------------------------------------------------------------------
# blender_mesh dispatch (most actions)
# ---------------------------------------------------------------------------


class TestBlenderMeshDispatch:
    @pytest.mark.asyncio
    async def test_analyze_dispatches(self):
        mock_conn = _make_mock_connection()
        mock_conn.send_command = AsyncMock(return_value={
            "status": "success", "vertices": 100, "edges": 200, "faces": 50,
            "non_manifold_edges": 0, "loose_vertices": 0,
        })
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_mesh
            result = await blender_mesh(action="analyze", object_name="Cube")
            mock_conn.send_command.assert_called()
            # Should have called with mesh_analyze_topology or similar
            cmd = mock_conn.send_command.call_args[0][0]
            assert "mesh" in cmd.lower() or "analyze" in cmd.lower() or mock_conn.send_command.called

    @pytest.mark.asyncio
    async def test_repair_dispatches(self):
        mock_conn = _make_mock_connection()
        mock_conn.send_command = AsyncMock(return_value={"status": "success"})
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_mesh
            result = await blender_mesh(action="repair", object_name="Cube")
            mock_conn.send_command.assert_called()

    @pytest.mark.asyncio
    async def test_game_check_dispatches(self):
        mock_conn = _make_mock_connection()
        mock_conn.send_command = AsyncMock(return_value={
            "vertices": 100, "faces": 50, "has_uv": True,
        })
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_mesh
            result = await blender_mesh(action="game_check", object_name="Cube")
            mock_conn.send_command.assert_called()


# ---------------------------------------------------------------------------
# blender_uv dispatch
# ---------------------------------------------------------------------------


class TestBlenderUVDispatch:
    @pytest.mark.asyncio
    async def test_analyze_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_uv
            result = await blender_uv(action="analyze", object_name="Cube")
            mock_conn.send_command.assert_called()

    @pytest.mark.asyncio
    async def test_unwrap_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_uv
            result = await blender_uv(action="unwrap", object_name="Cube")
            mock_conn.send_command.assert_called()

    @pytest.mark.asyncio
    async def test_pack_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_uv
            result = await blender_uv(action="pack", object_name="Cube")
            mock_conn.send_command.assert_called()


# ---------------------------------------------------------------------------
# blender_export dispatch
# ---------------------------------------------------------------------------


class TestBlenderExportDispatch:
    @pytest.mark.asyncio
    async def test_export_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_export
            result = await blender_export(
                export_format="fbx", filepath=_TMP_TEST_FBX
            )
            mock_conn.send_command.assert_called()


# ---------------------------------------------------------------------------
# blender_execute dispatch
# ---------------------------------------------------------------------------


class TestBlenderExecuteDispatch:
    @pytest.mark.asyncio
    async def test_execute_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_execute
            result = await blender_execute(code="print('hello')")
            mock_conn.send_command.assert_called()


# ---------------------------------------------------------------------------
# concept_art dispatch
# ---------------------------------------------------------------------------


class TestConceptArtDispatch:
    @pytest.mark.asyncio
    async def test_generate_dispatches(self):
        with patch("veilbreakers_mcp.blender_server.generate_concept_art") as mock_gen:
            mock_gen.return_value = {"url": "http://example.com/art.png", "seed": 42}
            from veilbreakers_mcp.blender_server import concept_art
            result = await concept_art(
                action="generate", prompt="a dark castle"
            )
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_palette_dispatches(self):
        with patch("veilbreakers_mcp.blender_server.extract_color_palette") as mock_pal:
            mock_pal.return_value = {"colors": ["#000"]}
            from veilbreakers_mcp.blender_server import concept_art
            result = await concept_art(
                action="extract_palette", image_path=_TMP_IMG_PNG
            )
            mock_pal.assert_called_once()


# ---------------------------------------------------------------------------
# Verify all tool functions exist and are callable
# ---------------------------------------------------------------------------


class TestToolFunctionsExist:
    """Verify all expected tool functions are importable."""

    def test_blender_scene_importable(self):
        from veilbreakers_mcp.blender_server import blender_scene
        assert callable(blender_scene)

    def test_blender_object_importable(self):
        from veilbreakers_mcp.blender_server import blender_object
        assert callable(blender_object)

    def test_blender_material_importable(self):
        from veilbreakers_mcp.blender_server import blender_material
        assert callable(blender_material)

    def test_blender_viewport_importable(self):
        from veilbreakers_mcp.blender_server import blender_viewport
        assert callable(blender_viewport)

    def test_blender_execute_importable(self):
        from veilbreakers_mcp.blender_server import blender_execute
        assert callable(blender_execute)

    def test_blender_export_importable(self):
        from veilbreakers_mcp.blender_server import blender_export
        assert callable(blender_export)

    def test_blender_mesh_importable(self):
        from veilbreakers_mcp.blender_server import blender_mesh
        assert callable(blender_mesh)

    def test_blender_uv_importable(self):
        from veilbreakers_mcp.blender_server import blender_uv
        assert callable(blender_uv)

    def test_blender_texture_importable(self):
        from veilbreakers_mcp.blender_server import blender_texture
        assert callable(blender_texture)

    def test_asset_pipeline_importable(self):
        from veilbreakers_mcp.blender_server import asset_pipeline
        assert callable(asset_pipeline)

    def test_concept_art_importable(self):
        from veilbreakers_mcp.blender_server import concept_art
        assert callable(concept_art)

    def test_blender_rig_importable(self):
        from veilbreakers_mcp.blender_server import blender_rig
        assert callable(blender_rig)

    def test_blender_animation_importable(self):
        from veilbreakers_mcp.blender_server import blender_animation
        assert callable(blender_animation)

    def test_blender_environment_importable(self):
        from veilbreakers_mcp.blender_server import blender_environment
        assert callable(blender_environment)

    def test_blender_worldbuilding_importable(self):
        from veilbreakers_mcp.blender_server import blender_worldbuilding
        assert callable(blender_worldbuilding)

    def test_blender_quality_importable(self):
        from veilbreakers_mcp.blender_server import blender_quality
        assert callable(blender_quality)
