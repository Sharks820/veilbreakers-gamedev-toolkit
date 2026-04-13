import json

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



@pytest.mark.asyncio
async def test_compose_map_threads_cave_candidates_into_terrain_and_creates_entrance(monkeypatch):
    commands: list[tuple[str, dict]] = []

    async def _handler(command, params):
        commands.append((command, dict(params)))
        if command == "clear_scene":
            return {"status": "success"}
        if command == "env_generate_terrain":
            return {
                "status": "success",
                "name": "CaveMap_Terrain",
                "cliff_overlays": 1,
                "hero_cliff_overlays": 0,
            }
        if command == "env_create_cave_entrance":
            return {"status": "success", "name": params["name"]}
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

    async def _fake_sample_height(*args, **kwargs):
        return 6.5

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

    assert parsed["status"] == "review_required"
    assert terrain_calls
    assert terrain_calls[0]["scene_read"]["cave_candidates"]
    assert entrance_calls
    assert entrance_calls[0]["name"] == "TreasureCave_Entrance"
    assert chamber_calls
    assert chamber_calls[0]["name"] == "TreasureCave_Chamber"


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
