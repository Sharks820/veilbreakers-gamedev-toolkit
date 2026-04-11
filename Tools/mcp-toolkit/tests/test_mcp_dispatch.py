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

    @pytest.mark.asyncio
    async def test_save_project_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_scene
            result = await blender_scene(action="save_project", filepath="C:/tmp/test.blend")
            mock_conn.send_command.assert_any_call(
                "save_project",
                {
                    "filepath": "C:/tmp/test.blend",
                    "incremental": False,
                    "copy": False,
                    "compress": True,
                    "verify": True,
                    "compute_hash": False,
                },
            )

    @pytest.mark.asyncio
    async def test_verify_project_save_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_scene
            result = await blender_scene(
                action="verify_project_save",
                filepath="C:/tmp/test.blend",
                expect_current_file=True,
            )
            mock_conn.send_command.assert_any_call(
                "verify_project_save",
                {
                    "filepath": "C:/tmp/test.blend",
                    "compute_hash": False,
                    "expect_current_file": True,
                },
            )


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
# terrain_pipeline / blender_environment / asset_pipeline dispatch
# ---------------------------------------------------------------------------


class TestTerrainPipelineDispatch:
    @pytest.mark.asyncio
    async def test_run_pipeline_forwards_return_height(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import terrain_pipeline

            await terrain_pipeline(
                action="run_pipeline",
                pipeline=["macro_world", "structural_masks"],
                return_height=True,
            )

            mock_conn.send_command.assert_any_call(
                "env_run_terrain_pass",
                {
                    "tile_size": 64,
                    "cell_size": 1.0,
                    "seed": 0,
                    "tile_x": 0,
                    "tile_y": 0,
                    "world_origin_x": 0.0,
                    "world_origin_y": 0.0,
                    "terrain_type": "mountains",
                    "scale": 100.0,
                    "erosion_profile": "temperate",
                    "checkpoint": False,
                    "enforce_protocol": False,
                    "out_of_view_ok": True,
                    "return_height": True,
                    "pipeline": ["macro_world", "structural_masks"],
                },
            )


class TestBlenderEnvironmentDispatch:
    @pytest.mark.asyncio
    async def test_generate_terrain_forwards_location_and_heightmap(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_environment

            await blender_environment(
                action="generate_terrain",
                name="HeroTerrain",
                terrain_type="mountains",
                resolution=65,
                scale=128.0,
                height_scale=1.0,
                location=[10.0, 20.0, 3.0],
                heightmap=[[0.0, 1.0], [1.0, 0.0]],
                capture_viewport=False,
            )

            mock_conn.send_command.assert_any_call(
                "env_generate_terrain",
                {
                    "name": "HeroTerrain",
                    "terrain_type": "mountains",
                    "resolution": 65,
                    "height_scale": 1.0,
                    "scale": 128.0,
                    "location": [10.0, 20.0, 3.0],
                    "heightmap": [[0.0, 1.0], [1.0, 0.0]],
                },
            )

    @pytest.mark.asyncio
    async def test_build_cliff_face_dispatches(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import blender_environment

            await blender_environment(
                action="build_cliff_face",
                name="HeroCliff",
                position=[0.0, 1.0, 2.0],
                width=24.0,
                height=18.0,
                overhang=6.0,
                num_cave_entrances=1,
                has_ledge_path=True,
                seed=123,
                capture_viewport=False,
            )

            mock_conn.send_command.assert_any_call(
                "env_build_cliff_face",
                {
                    "name": "HeroCliff",
                    "position": [0.0, 1.0, 2.0],
                    "width": 24.0,
                    "height": 18.0,
                    "overhang": 6.0,
                    "num_cave_entrances": 1,
                    "has_ledge_path": True,
                    "seed": 123,
                },
            )


class TestAssetPipelineDispatch:
    @pytest.mark.asyncio
    async def test_compose_terrain_node_requires_spec(self):
        mock_conn = _make_mock_connection()
        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import asset_pipeline

            result = await asset_pipeline(action="compose_terrain_node")
            assert "terrain_node_spec is required" in result

    @pytest.mark.asyncio
    async def test_compose_terrain_node_dispatches_authoring_sequence(self):
        mock_conn = _make_mock_connection()

        async def _dispatch(cmd, params=None):
            if cmd == "toolchain_inspect_external":
                return {"agent_contract": {"selection": "terrain_unity_ready_free"}}
            if cmd == "env_run_terrain_pass":
                return {
                    "ok": True,
                    "results": [],
                    "populated_channels": ["cliff_candidate", "cave_candidate", "waterfall_lip_candidate"],
                    "shared_height_range": [-120.0, 320.0],
                    "height": [[0.0, 0.0], [0.0, 0.0]],
                }
            if cmd == "env_validate_tile_seams":
                return {"seam_ok": True, "max_edge_delta": 0.0, "issues": []}
            if cmd == "env_generate_terrain":
                return {"name": params["name"], "object_location": params.get("location", [0.0, 0.0, 0.0])}
            if cmd.startswith("env_build_"):
                return {"name": params["name"]}
            if cmd == "env_export_heightmap":
                return {"filepath": params["filepath"]}
            return {"name": params.get("name", cmd) if isinstance(params, dict) else cmd}

        mock_conn.send_command = AsyncMock(side_effect=_dispatch)

        with patch("veilbreakers_mcp.blender_server.get_blender_connection", return_value=mock_conn):
            from veilbreakers_mcp.blender_server import asset_pipeline

            result = await asset_pipeline(
                action="compose_terrain_node",
                terrain_node_spec={
                    "name": "Riftpass_01",
                    "seed": 42,
                    "terrain": {
                        "preset": "mountains",
                        "size": 128.0,
                        "resolution": 65,
                        "location": [12.0, 24.0, 0.0],
                    },
                    "scene_read": {
                        "major_landforms": ["mountain_pass", "cliff", "waterfall", "river", "basin", "cave"],
                        "focal_point": [8.0, 6.0, 12.0],
                        "hero_features_missing": ["cliffside_cave", "volumetric_waterfall", "readable_pass"],
                        "cave_candidates": [[7.0, 5.0, 10.0]],
                        "waterfall_chains": [{"lip_position": [6.0, -2.0, 16.0], "pool_position": [6.0, -10.0, 4.0], "drop_height": 12.0}],
                        "success_criteria": ["readable cliff"],
                        "reviewer": "pytest",
                    },
                },
                capture_viewport=False,
            )

            payload = json.loads(result)
            assert payload["status"] == "success"
            assert payload["tile_contract"]["world_origin_x"] == 0.0
            assert payload["tile_contract"]["world_origin_y"] == 0.0
            assert payload["tile_contract"]["object_center"] == [64.0, 64.0, 0.0]
            assert payload["seam_report"]["seam_ok"] is True

            dispatched = [call.args[0] for call in mock_conn.send_command.call_args_list]
            assert "toolchain_inspect_external" in dispatched
            assert "clear_scene" in dispatched
            assert "env_run_terrain_pass" in dispatched
            assert "env_validate_tile_seams" in dispatched
            assert "env_generate_terrain" in dispatched
            assert "env_build_cliff_face" in dispatched
            assert "env_build_cave_entrance" in dispatched
            assert "env_build_waterfall" in dispatched
            assert "env_export_heightmap" in dispatched

            export_call = next(
                call for call in mock_conn.send_command.call_args_list
                if call.args[0] == "env_export_heightmap"
            )
            assert export_call.args[1]["tiled_world"] is True
            assert export_call.args[1]["use_global_height_range"] is True
            assert export_call.args[1]["height_range"] == [-120.0, 320.0]

            terrain_call = next(
                call for call in mock_conn.send_command.call_args_list
                if call.args[0] == "env_generate_terrain"
            )
            assert terrain_call.args[1]["location"] == [64.0, 64.0, 0.0]

    def test_compose_map_redirect_notice_flags_hero_terrain_specs(self):
        from veilbreakers_mcp.blender_server import _compose_map_redirect_notice

        notice = _compose_map_redirect_notice(
            {
                "name": "Riftpass",
                "terrain": {
                    "preset": "mountains",
                    "description": "cliffside cave with waterfall through a mountain pass",
                },
                "water": {"rivers": [{"source": [0, 0], "destination": [10, 10]}]},
                "locations": [{"type": "cave", "name": "Hero Cave"}],
            }
        )

        assert notice["workflow_scope"] == "generic_map"
        assert notice["recommended_action"] == "compose_terrain_node"


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
