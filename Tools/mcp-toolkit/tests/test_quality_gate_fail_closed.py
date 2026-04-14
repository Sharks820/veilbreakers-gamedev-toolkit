import json
import math

import pytest
from PIL import Image

from veilbreakers_mcp import blender_server
from veilbreakers_mcp.shared.pipeline_runner import PipelineRunner


class _DummyBlender:
    def __init__(self, handler):
        self._handler = handler

    async def send_command(self, command, params):
        return await self._handler(command, params)

    async def capture_viewport_bytes(self):
        return b""


@pytest.mark.asyncio
async def test_performance_check_fails_when_budget_probe_unavailable(monkeypatch):
    async def _handler(command, params):
        if command == "performance_budget_check":
            return {
                "status": "not_available",
                "error": "performance_budget_check_not_implemented",
            }
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )

    result = await blender_server.asset_pipeline(action="performance_check")
    assert result["status"] == "error"
    assert result["summary"]["passed"] is False


@pytest.mark.asyncio
async def test_screenshot_regression_fails_missing_baseline(monkeypatch, tmp_path):
    current = tmp_path / "angle_0.png"
    current.write_bytes(b"png")

    async def _handler(command, params):
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )

    result = await blender_server.asset_pipeline(
        action="screenshot_regression",
        baseline_dir=str(tmp_path / "missing_baselines"),
        current_screenshots=[str(current)],
    )
    assert result["status"] == "failed"
    assert result["all_match"] is False


@pytest.mark.asyncio
async def test_aaa_verify_errors_when_render_angle_produces_no_images(monkeypatch):
    async def _handler(command, params):
        if command == "render_angle":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )

    raw = await blender_server.asset_pipeline(action="aaa_verify", angles=1)
    result = raw if isinstance(raw, dict) else json.loads(raw)
    assert result["status"] == "error"
    assert result["capture_errors"]


@pytest.mark.asyncio
async def test_validate_visual_quality_requires_full_angle_set(tmp_path):
    image_path = tmp_path / "only_one.png"
    Image.new("RGB", (32, 32), color=(128, 128, 128)).save(image_path)

    async def _handler(command, params):
        if command == "render_contact_sheet":
            return {"paths": [str(image_path)]}
        raise AssertionError(f"unexpected command: {command}")

    runner = PipelineRunner(_DummyBlender(_handler), blender_server.settings)
    result = await runner.validate_visual_quality("TestMesh")
    assert result["valid"] is False
    assert any(
        "Expected 6 screenshots, got 1" in issue
        for issue in result["validation"]["issues"]
    )


@pytest.mark.asyncio
async def test_generate_map_package_surfaces_nonfatal_substep_failures(monkeypatch, tmp_path):
    async def _handler(command, params):
        if command == "mesh_check_game_ready":
            raise RuntimeError("probe unavailable")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )

    result = await blender_server.asset_pipeline(
        action="generate_map_package",
        map_package_spec={
            "map_name": "WarnMap",
            "objects": ["WarnMap_House"],
            "locations": [],
            "export_dir": str(tmp_path),
            "generate_lods": False,
        },
    )

    assert result["status"] == "partial"
    assert any("game_check_failed" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_compose_map_blocks_export_when_terrain_visual_gate_fails(monkeypatch):
    commands: list[str] = []

    async def _handler(command, params):
        commands.append(command)
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "GateMap_Terrain",
                "cliff_overlays": 3,
                "hero_cliff_overlays": 1,
            }
        if command == "env_export_heightmap":
            raise AssertionError("compose_map should stop before export when terrain verification fails")
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "failed",
            "passed": False,
            "required_profiles": ["terrain_readability", "terrain_cliff"],
            "failed_profiles": ["terrain_cliff"],
            "issues": ["Validation profile 'terrain_cliff' failed for: front"],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "GateMap",
            "seed": 9,
            "terrain": {
                "preset": "canyon",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "roads": [],
            "locations": [],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    assert parsed["status"] == "partial"
    assert any(step["step"] == "terrain_visual_verification" for step in parsed["steps_failed"])
    assert parsed["terrain_visual_profiles"] == ["terrain_readability", "terrain_cliff"]
    assert parsed["terrain_visual_verification"]["failed_profiles"] == ["terrain_cliff"]
    assert "env_export_heightmap" not in commands


@pytest.mark.asyncio
async def test_compose_map_stops_immediately_when_terrain_generation_fails(monkeypatch):
    commands: list[str] = []

    async def _handler(command, params):
        commands.append(command)
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {"status": "error", "error": "terrain exploded"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        raise AssertionError("terrain visual gate must not run when terrain generation fails")

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "BrokenTerrainMap",
            "seed": 12,
            "terrain": {
                "preset": "coastal",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "roads": [],
            "locations": [],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    assert parsed["status"] == "partial"
    assert parsed["unity_export_status"] == "blocked_by_terrain_generation_failure"
    assert any(step["step"] == "terrain" for step in parsed["steps_failed"])
    assert "terrain_visual_verified" not in parsed["steps_completed"]
    assert parsed["terrain_visual_verification"]["status"] == "skipped"
    assert commands == ["clear_scene", "env_generate_terrain"]


@pytest.mark.asyncio
async def test_compose_map_continues_when_terrain_visual_gate_passes(monkeypatch, tmp_path):
    export_dir = tmp_path / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    async def _handler(command, params):
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "PassMap_Terrain",
                "cliff_overlays": 2,
                "hero_cliff_overlays": 0,
            }
        if command == "env_export_heightmap":
            path = export_dir / "PassMap_heightmap.raw"
            path.write_bytes(b"raw")
            return {"filepath": str(path)}
        if command == "export_splatmap":
            return {"status": "success"}
        if command == "export_fbx":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_cliff"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    async def _fake_quality(*args, **kwargs):
        return {"validated_objects": [], "warnings": [], "failures": []}

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)
    monkeypatch.setattr(blender_server, "_enforce_world_quality", _fake_quality, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "PassMap",
            "seed": 9,
            "terrain": {
                "preset": "canyon",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "roads": [],
            "locations": [],
            "props": False,
            "auto_export_unity": True,
        },
        checkpoint_dir=str(export_dir),
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    assert parsed["status"] == "success"
    assert "terrain_visual_verified" in parsed["steps_completed"]
    assert parsed["terrain_visual_verification"]["passed"] is True
    assert parsed["heightmap_export_path"].endswith("PassMap_heightmap.raw")
    assert parsed["approved_for_unity_export"] is True
    assert parsed["unity_export_status"] == "export_completed"


@pytest.mark.asyncio
async def test_compose_map_passes_terrain_object_to_visual_gate(monkeypatch):
    captured_kwargs: dict = {}

    async def _handler(command, params):
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "FramedMap_Terrain",
                "cliff_overlays": 1,
                "hero_cliff_overlays": 0,
            }
        if command == "auto_frame_camera":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "FramedMap",
            "seed": 5,
            "terrain": {
                "preset": "hills",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "roads": [],
            "locations": [],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    assert parsed["status"] == "review_required"
    assert captured_kwargs["object_name"] == "FramedMap_Terrain"


@pytest.mark.asyncio
async def test_compose_map_waits_for_user_approval_before_export(monkeypatch):
    commands: list[str] = []

    async def _handler(command, params):
        commands.append(command)
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "ReviewMap_Terrain",
                "cliff_overlays": 2,
                "hero_cliff_overlays": 0,
            }
        if command == "auto_frame_camera":
            return {"status": "success"}
        if command == "env_export_heightmap":
            raise AssertionError("compose_map should wait for approval before export")
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_cliff"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "ReviewMap",
            "seed": 11,
            "terrain": {
                "preset": "canyon",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "roads": [],
            "locations": [],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    assert parsed["status"] == "review_required"
    assert parsed["approved_for_unity_export"] is False
    assert parsed["unity_export_status"] == "awaiting_user_approval"
    assert parsed["export_ready"] is True
    assert "env_export_heightmap" not in commands


@pytest.mark.asyncio
async def test_compose_map_creates_river_water_mesh_from_carve_result(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "RiverMap_Terrain",
                "cliff_overlays": 0,
                "hero_cliff_overlays": 0,
            }
        if command == "env_carve_river":
            return {
                "status": "success",
                "name": "RiverMap_Terrain",
                "path_length": 3,
                "path_points": [
                    [0.0, -20.0, 1.5],
                    [5.0, 0.0, 1.25],
                    [12.0, 20.0, 1.0],
                ],
            }
        if command == "env_create_water":
            return {"status": "success", "name": params["name"]}
        if command == "auto_frame_camera":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_river"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "RiverMap",
            "seed": 13,
            "terrain": {
                "preset": "hills",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "water": {
                "rivers": [{"source": [10, 10], "destination": [150, 140], "width": 6}],
            },
            "roads": [],
            "locations": [],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    create_water_calls = [params for command, params in commands if command == "env_create_water"]
    assert parsed["status"] == "review_required"
    assert any(step == "river_water_0" for step in parsed["steps_completed"])
    assert create_water_calls
    assert create_water_calls[0]["name"] == "RiverMap_River_0"
    assert create_water_calls[0]["path_points"][0] == [0.0, -20.0, 1.5]
    assert create_water_calls[0]["preserve_path_shape"] is True


def test_deprecated_world_terrain_runtime_command_fails_closed():
    from blender_addon.handlers import COMMAND_HANDLERS

    result = COMMAND_HANDLERS["env_generate_world_terrain"]({"name": "LegacyWorld"})

    assert result["status"] == "error"
    assert result["fail_closed"] is True
    assert result["command"] == "env_generate_world_terrain"
    assert "env_generate_terrain_tile" in result["replacement"]


@pytest.mark.asyncio
async def test_compose_map_emits_waterfall_when_river_requests_one(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "FallsMap_Terrain",
                "cliff_overlays": 1,
                "hero_cliff_overlays": 0,
                "heightmap": [
                    [12.0, 11.0, 10.0],
                    [9.0, 7.0, 5.0],
                    [6.0, 4.0, 3.0],
                ],
                "tile_size": 2,
                "cell_size": 1.5,
                "world_origin_x": -6.0,
                "world_origin_y": -8.0,
            }
        if command == "execute_code":
            return {
                "output": json.dumps(
                    {
                        "heightmap": [
                            [22.0, 21.0, 20.0],
                            [19.0, 42.0, 15.0],
                            [16.0, 14.0, 13.0],
                        ],
                        "rows": 3,
                        "cols": 3,
                        "tile_size": 2,
                        "cell_size": 2.0,
                        "world_origin_x": -5.5,
                        "world_origin_y": -7.5,
                    }
                )
            }
        if command == "env_carve_river":
            return {
                "status": "success",
                "name": "FallsMap_Terrain",
                "path_length": 3,
                "path_points": [
                    [0.0, 0.0, 12.0],
                    [0.0, -2.0, 5.0],
                    [0.0, -12.0, 4.0],
                ],
            }
        if command == "env_create_water":
            return {"status": "success", "name": params["name"]}
        if command == "env_generate_waterfall":
            return {"status": "success", "name": params["name"], "object_created": True}
        if command == "auto_frame_camera":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_river", "terrain_waterfall"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "FallsMap",
            "seed": 21,
            "terrain": {
                "preset": "canyon",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "water": {
                "rivers": [
                    {
                        "source": [10, 10],
                        "destination": [150, 140],
                        "width": 6,
                        "has_waterfall": True,
                    }
                ],
            },
            "roads": [],
            "locations": [],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    waterfall_calls = [params for command, params in commands if command == "env_generate_waterfall"]
    assert parsed["status"] == "review_required"
    assert any(step == "waterfall_0" for step in parsed["steps_completed"])
    assert waterfall_calls
    assert waterfall_calls[0]["name"] == "FallsMap_Waterfall_0"
    assert waterfall_calls[0]["facing_direction"] == [0.0, -1.0]
    assert waterfall_calls[0]["location"] == [0.0, 0.0, 5.0]
    assert waterfall_calls[0]["materialize_object"] is True
    assert waterfall_calls[0]["require_heightmap_context"] is True
    assert waterfall_calls[0]["heightmap"][1][1] == 42.0
    assert waterfall_calls[0]["tile_size"] == 2
    assert waterfall_calls[0]["cell_size"] == pytest.approx(2.0)
    assert waterfall_calls[0]["world_origin_x"] == pytest.approx(-5.5)
    assert waterfall_calls[0]["world_origin_y"] == pytest.approx(-7.5)
    assert parsed["terrain_runtime_diagnostics"]["water_network_present"] is False
    assert parsed["waterfall_runtime_diagnostics"][0]["authoring_path"] == "unknown"


@pytest.mark.asyncio
async def test_compose_map_emits_explicit_waterfall_without_other_water_surfaces(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "OnlyFalls_Terrain",
                "cliff_overlays": 0,
                "hero_cliff_overlays": 0,
                "heightmap": [
                    [8.0, 7.0, 6.0],
                    [5.0, 4.0, 2.0],
                    [4.0, 1.0, 0.0],
                ],
                "tile_size": 2,
                "cell_size": 1.0,
                "world_origin_x": -2.0,
                "world_origin_y": -2.0,
                "water_network_present": True,
            }
        if command == "execute_code":
            return {
                "output": json.dumps(
                    {
                        "heightmap": [
                            [9.0, 7.0, 6.0],
                            [5.0, 4.5, 2.0],
                            [4.0, 1.0, 0.0],
                        ],
                        "rows": 3,
                        "cols": 3,
                        "tile_size": 2,
                        "cell_size": 1.0,
                        "world_origin_x": -2.0,
                        "world_origin_y": -2.0,
                    }
                )
            }
        if command == "env_generate_waterfall":
            return {
                "status": "success",
                "name": params["name"],
                "authoring_path": "water_network_derived",
            }
        if command == "auto_frame_camera":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_waterfall"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "OnlyFalls",
            "seed": 31,
            "terrain": {
                "preset": "canyon",
                "size": 120.0,
                "resolution": 64,
                "height_scale": 16.0,
            },
            "water": {
                "waterfalls": [
                    {
                        "name": "OnlyFalls_Waterfall_Explicit_0",
                        "location": [0.0, 0.0, 2.0],
                        "height": 6.0,
                        "width": 4.0,
                    }
                ]
            },
            "roads": [],
            "locations": [],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    waterfall_calls = [params for command, params in commands if command == "env_generate_waterfall"]
    assert parsed["status"] == "review_required"
    assert waterfall_calls
    assert waterfall_calls[0]["require_heightmap_context"] is True
    assert parsed["waterfall_runtime_diagnostics"][0]["authoring_path"] == "water_network_derived"



@pytest.mark.asyncio
async def test_compose_map_threads_cave_candidates_into_terrain_and_returns_terrain_carved_entrance(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command in {
            "clear_scene",
            "terrain_spline_deform",
            "terrain_flatten_zone",
            "material_create_procedural",
            "modify_object",
            "env_paint_terrain",
            "terrain_create_biome_material",
            "setup_dark_fantasy_lighting",
        }:
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "CaveMap_Terrain",
                "cliff_overlays": 1,
                "hero_cliff_overlays": 0,
            }
        if command == "world_generate_cave":
            return {"status": "success", "name": params["name"]}
        if command == "auto_frame_camera":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_cliff", "terrain_cave"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    async def _fake_position(*args, **kwargs):
        return None

    async def _fake_sample_height(_blender, _terrain_name, x, y):
        return 6.0 + 0.12 * float(x)

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)
    monkeypatch.setattr(blender_server, "_position_generated_object", _fake_position, raising=False)
    monkeypatch.setattr(blender_server, "_sample_terrain_height", _fake_sample_height, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "CaveMap",
            "seed": 17,
            "terrain": {
                "preset": "mountains",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "roads": [],
            "locations": [
                {"type": "cave", "name": "TreasureCave", "grid_size": 28},
            ],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    terrain_calls = [params for command, params in commands if command == "env_generate_terrain"]
    entrance_calls = [params for command, params in commands if command == "env_create_cave_entrance"]
    chamber_calls = [params for command, params in commands if command == "world_generate_cave"]
    cave_results = [loc for loc in parsed["locations"] if loc.get("type") == "cave"]

    assert parsed["status"] == "review_required"
    assert terrain_calls
    assert terrain_calls[0]["scene_read"]["cave_candidates"]
    assert not entrance_calls
    assert chamber_calls
    assert chamber_calls[0]["name"] == "TreasureCave_Chamber"
    assert cave_results
    assert cave_results[0]["result"]["entrance"]["surface_mode"] == "terrain_carved"
    assert cave_results[0]["supporting_objects"] == ["TreasureCave_Chamber"]


@pytest.mark.asyncio
async def test_compose_map_terrain_only_skips_non_cave_locations_and_props(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command in {
            "clear_scene",
            "terrain_spline_deform",
            "terrain_flatten_zone",
            "material_create_procedural",
            "modify_object",
            "auto_frame_camera",
        }:
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "TerrainOnlyMap_Terrain",
                "cliff_overlays": 1,
                "hero_cliff_overlays": 0,
            }
        if command == "world_generate_cave":
            return {"status": "success", "name": params["name"]}
        if command in {"world_generate_settlement", "world_generate_ruins", "env_scatter_props"}:
            raise AssertionError(f"terrain_only mode should not call {command}")
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_cliff", "terrain_cave"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    async def _fake_position(*args, **kwargs):
        return None

    async def _fake_sample_height(_blender, _terrain_name, x, y):
        return 5.5 + 0.08 * float(x)

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)
    monkeypatch.setattr(blender_server, "_position_generated_object", _fake_position, raising=False)
    monkeypatch.setattr(blender_server, "_sample_terrain_height", _fake_sample_height, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "TerrainOnlyMap",
            "seed": 23,
            "terrain_only": True,
            "terrain": {
                "preset": "mountains",
                "size": 180.0,
                "resolution": 64,
                "height_scale": 20.0,
            },
            "locations": [
                {"type": "settlement", "name": "ShouldNotSpawn"},
                {"type": "ruins", "name": "AlsoSkip"},
                {"type": "cave", "name": "KeepCave", "grid_size": 26},
            ],
            "props": True,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    command_names = [command for command, _ in commands]
    assert parsed["status"] == "review_required"
    assert "world_generate_settlement" not in command_names
    assert "world_generate_ruins" not in command_names
    assert "env_scatter_props" not in command_names
    assert "world_generate_cave" in command_names
    assert [loc["name"] for loc in parsed["locations"]] == ["KeepCave"]
    assert any(
        "terrain_only mode skipped 2 non-terrain locations" in warning
        for warning in parsed["warnings"]
    )
    assert any(
        "terrain_only mode disabled contextual prop scatter" in warning
        for warning in parsed["warnings"]
    )


@pytest.mark.asyncio
async def test_compose_map_biome_paints_before_low_profile_road_and_keeps_trail_terrain_only(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command in {
            "clear_scene",
            "env_paint_terrain",
            "terrain_create_biome_material",
            "setup_dark_fantasy_lighting",
            "auto_frame_camera",
        }:
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "RoadBiomeMap_Terrain",
                "cliff_overlays": 0,
                "hero_cliff_overlays": 0,
            }
        if command == "env_generate_road":
            return {
                "status": "success",
                "name": params["terrain_name"],
                "surface_mode": "terrain_only",
                "road_mesh_name": None,
            }
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_road"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "RoadBiomeMap",
            "seed": 44,
            "terrain": {
                "preset": "swamp",
                "size": 140.0,
                "resolution": 64,
                "height_scale": 12.0,
            },
            "biome": "thornwood_forest",
            "roads": [{"waypoints": [[-40, -20], [0, 0], [36, 18]], "width": 2.0, "surface": "trail"}],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    biome_index = next(
        idx for idx, (command, _) in enumerate(commands)
        if command == "terrain_create_biome_material"
    )
    road_index = next(
        idx for idx, (command, _) in enumerate(commands)
        if command == "env_generate_road"
    )
    road_call = next(params for command, params in commands if command == "env_generate_road")

    assert parsed["status"] == "review_required"
    assert biome_index < road_index
    assert road_call["surface"] == "trail"
    assert road_call["force_mesh_overlay"] is False


@pytest.mark.asyncio
async def test_compose_map_shapes_hero_cliff_before_water_and_buries_cave_chamber(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command in {
            "clear_scene",
            "env_generate_terrain",
            "terrain_flatten_zone",
            "terrain_spline_deform",
            "env_carve_river",
            "env_create_water",
            "env_generate_road",
            "env_create_cave_entrance",
            "world_generate_cave",
            "material_create_procedural",
            "modify_object",
            "auto_frame_camera",
        }:
            if command == "env_generate_terrain":
                return {
                    "status": "success",
                    "name": "HeroMap_Terrain",
                    "cliff_overlays": 2,
                    "hero_cliff_overlays": 1,
                }
            if command == "env_carve_river":
                return {
                    "status": "success",
                    "name": "HeroMap_Terrain",
                    "path_length": 4,
                    "path_points": [
                        [10.0, -14.0, 11.0],
                        [18.0, -6.0, 10.4],
                        [28.0, 2.0, 9.8],
                        [40.0, 10.0, 9.0],
                    ],
                }
            if command == "env_create_water":
                return {"status": "success", "name": params["name"]}
            if command == "env_generate_road":
                return {"status": "success", "name": "HeroMap_Road_0"}
            if command == "env_create_cave_entrance":
                return {"status": "success", "name": params["name"]}
            if command == "world_generate_cave":
                return {"status": "success", "name": params["name"]}
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_cliff", "terrain_river"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    def _fake_plan(_spec):
        return [
            {
                "name": "TreasureCave",
                "type": "cave",
                "anchor": (20.0, 10.0),
                "radius": 18.0,
                "source": {"type": "cave", "name": "TreasureCave", "grid_size": 28},
            }
        ]

    async def _fake_sample_height(_blender, _terrain_name, x, y):
        return 10.0 + 0.2 * float(x)

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)
    monkeypatch.setattr(blender_server, "_plan_map_location_anchors", _fake_plan, raising=False)
    monkeypatch.setattr(blender_server, "_sample_terrain_height", _fake_sample_height, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "HeroMap",
            "seed": 21,
            "terrain": {
                "preset": "mountains",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "water": {
                "rivers": [{"source": [10, 10], "destination": [150, 140], "width": 6}],
                "water_level": 1.0,
            },
            "roads": [{"waypoints": [[-60, -42], [-20, -12], [12, 4]], "width": 3}],
            "locations": [
                {"type": "cave", "name": "TreasureCave", "grid_size": 28},
            ],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    raise_index = next(
        idx for idx, (command, params) in enumerate(commands)
        if command == "terrain_spline_deform" and params.get("mode") == "raise"
    )
    river_index = next(idx for idx, (command, _) in enumerate(commands) if command == "env_carve_river")
    road_index = next(idx for idx, (command, _) in enumerate(commands) if command == "env_generate_road")

    entrance_calls = [params for command, params in commands if command == "env_create_cave_entrance"]
    chamber_moves = [params for command, params in commands if command == "modify_object" and params.get("name") == "TreasureCave_Chamber"]
    cave_results = [loc for loc in parsed["locations"] if loc.get("type") == "cave"]

    assert parsed["status"] == "review_required"
    assert any(step == "hero_cliff_TreasureCave" for step in parsed["steps_completed"])
    assert raise_index < river_index < road_index
    assert not entrance_calls
    assert chamber_moves
    chamber_position = chamber_moves[0]["position"]
    chamber_surface_z = 10.0 + 0.2 * float(chamber_position[0])
    assert chamber_position[2] <= chamber_surface_z - 5.5
    assert cave_results
    assert math.isclose(
        cave_results[0]["result"]["entrance"]["rotation_z"],
        math.pi / 2.0,
        rel_tol=1e-3,
        abs_tol=1e-3,
    )


@pytest.mark.asyncio
async def test_compose_map_fails_closed_when_cave_deformation_fails(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command in {
            "clear_scene",
            "terrain_flatten_zone",
            "material_create_procedural",
            "modify_object",
            "env_paint_terrain",
            "terrain_create_biome_material",
            "setup_dark_fantasy_lighting",
        }:
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "BrokenCave_Terrain",
                "cliff_overlays": 2,
                "hero_cliff_overlays": 1,
            }
        if command == "terrain_spline_deform":
            if params.get("mode") == "raise":
                return {"status": "success"}
            raise RuntimeError("cave tunnel deformation failed")
        if command == "auto_frame_camera":
            return {"status": "success"}
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "success",
            "passed": True,
            "required_profiles": ["terrain_readability", "terrain_cliff"],
            "failed_profiles": [],
            "issues": [],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    def _fake_plan(_spec):
        return [
            {
                "name": "BrokenCave",
                "type": "cave",
                "anchor": (16.0, 8.0),
                "radius": 16.0,
                "source": {"type": "cave", "name": "BrokenCave", "grid_size": 24},
            }
        ]

    async def _fake_sample_height(_blender, _terrain_name, x, y):
        return 8.0 + 0.15 * float(x)

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)
    monkeypatch.setattr(blender_server, "_plan_map_location_anchors", _fake_plan, raising=False)
    monkeypatch.setattr(blender_server, "_sample_terrain_height", _fake_sample_height, raising=False)

    raw = await blender_server.asset_pipeline(
        action="compose_map",
        map_spec={
            "name": "BrokenCaveMap",
            "seed": 22,
            "terrain": {
                "preset": "mountains",
                "size": 160.0,
                "resolution": 64,
                "height_scale": 18.0,
            },
            "roads": [],
            "locations": [
                {"type": "cave", "name": "BrokenCave", "grid_size": 24},
            ],
            "props": False,
        },
        capture_viewport=False,
    )
    parsed = json.loads(raw[0])

    entrance_calls = [params for command, params in commands if command == "env_create_cave_entrance"]
    chamber_calls = [params for command, params in commands if command == "world_generate_cave"]

    assert parsed["status"] == "review_required"
    assert any(
        str(step.get("step", "")).startswith("location_BrokenCave")
        and (
            "cave tunnel flatten failed" in str(step.get("error", ""))
            or "cave tunnel deformation failed" in str(step.get("error", ""))
        )
        for step in parsed["steps_failed"]
    )
    assert not entrance_calls
    assert not chamber_calls
    assert any(command == "terrain_spline_deform" and params.get("mode") == "raise" for command, params in commands)


@pytest.mark.asyncio
async def test_generate_map_package_blocks_on_failed_terrain_visual_gate(monkeypatch, tmp_path):
    commands: list[str] = []

    async def _handler(command, params):
        commands.append(command)
        if command == "mesh_check_game_ready":
            return {"game_ready": True, "checks": {}, "summary": "ok"}
        if command == "export_fbx":
            raise AssertionError("generate_map_package should stop before export when terrain verification fails")
        raise AssertionError(f"unexpected command: {command}")

    async def _fake_gate(*args, **kwargs):
        return {
            "status": "failed",
            "passed": False,
            "required_profiles": ["terrain_readability", "terrain_cave"],
            "failed_profiles": ["terrain_cave"],
            "issues": ["Validation profile 'terrain_cave' failed for: front"],
            "capture_errors": [],
            "screenshots": ["front.png"],
            "angle_labels": ["front"],
            "profile_results": [],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "_run_terrain_visual_gate", _fake_gate, raising=False)

    result = await blender_server.asset_pipeline(
        action="generate_map_package",
        map_package_spec={
            "map_name": "PkgMap",
            "objects": ["PkgMap_Terrain", "PkgMap_CaveEntrance"],
            "locations": [{"name": "Cave", "type": "cave"}],
            "export_dir": str(tmp_path),
            "generate_lods": False,
        },
    )

    assert result["status"] == "error"
    assert result["terrain_visual_profiles"] == ["terrain_readability", "terrain_cave"]
    assert result["terrain_visual_verification"]["failed_profiles"] == ["terrain_cave"]
    assert "export_fbx" not in commands


@pytest.mark.asyncio
async def test_compose_interior_surfaces_room_enhancement_warning(monkeypatch):
    async def _handler(command, params):
        if command in {"world_generate_linked_interior", "world_generate_interior", "modify_object"}:
            return {"status": "success"}
        if command == "mesh_enhance_geometry":
            raise RuntimeError("bevel stack failed")
        if command == "validate_prop_quality":
            return {"passed": True, "issues": []}
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )

    result = await blender_server.asset_pipeline(
        action="compose_interior",
        interior_spec={
            "name": "WarnInterior",
            "seed": 7,
            "rooms": [
                {"name": "hall", "type": "generic", "width": 6, "depth": 6, "height": 3},
            ],
            "doors": [],
            "storytelling_density": 0.0,
        },
        capture_viewport=False,
    )
    parsed = json.loads(result[0])

    assert parsed["status"] == "partial"
    assert any("room_enhancement_failed" in warning for warning in parsed["warnings"])
