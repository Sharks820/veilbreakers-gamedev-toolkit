"""Unit tests for the full production pipeline (PipelineRunner).

Tests the end-to-end ``full_asset_pipeline()`` and ``generate_and_process()``
methods, as well as the ``_detect_asset_type()`` heuristic and constants.

All Blender commands are mocked -- no live Blender instance required.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from veilbreakers_mcp.shared.pipeline_runner import (
    ANIMATION_COMMANDS,
    IMPORT_EXTENSIONS,
    MATERIAL_PRESETS,
    PipelineRunner,
    RIG_TEMPLATES,
    RIGGABLE_TYPES,
)


def _make_visual_gate_images() -> list[str]:
    """Create a few simple but non-flat screenshots for the visual gate."""
    out_dir = Path(tempfile.gettempdir()) / "veilbreakers_pipeline_visual_gate"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    palettes = [
        ((48, 42, 34), (156, 112, 72), (220, 196, 160)),
        ((28, 36, 52), (88, 124, 172), (192, 214, 238)),
        ((36, 24, 48), (132, 84, 180), (232, 200, 250)),
    ]
    for idx, (bg, fill, accent) in enumerate(palettes):
        path = out_dir / f"contact_{idx}.png"
        image = Image.new("RGB", (512, 512), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle((64, 220, 448, 420), fill=fill, outline=accent, width=8)
        draw.rectangle((160, 128, 352, 280), fill=accent, outline=(240, 240, 240), width=6)
        draw.polygon([(64, 220), (128, 150), (160, 128), (256, 110), (352, 128), (384, 150), (448, 220)], outline=(255, 255, 255), fill=None)
        draw.ellipse((232, 92, 280, 140), fill=(250, 220, 120), outline=(255, 255, 255), width=4)
        draw.line((64, 420, 448, 420), fill=(20, 20, 20), width=10)
        draw.line((120, 420, 120, 300), fill=(20, 20, 20), width=8)
        draw.line((392, 420, 392, 300), fill=(20, 20, 20), width=8)
        for x in range(176, 336, 32):
            draw.rectangle((x, 164, x + 14, 192), fill=(20, 20, 20), outline=(245, 245, 245), width=2)
            draw.rectangle((x, 208, x + 14, 236), fill=(20, 20, 20), outline=(245, 245, 245), width=2)
        for x in range(96, 416, 48):
            draw.line((x, 420, x + 10, 280), fill=(30, 30, 30), width=3)
        for y in range(288, 416, 24):
            draw.line((64, y, 448, y), fill=(32, 28, 24), width=2)
        for i in range(6):
            draw.line((72 + i * 72, 220, 72 + i * 72, 420), fill=(30, 30, 30), width=2)
        image.save(path)
        paths.append(str(path))

    return paths


VISUAL_GATE_IMAGES = _make_visual_gate_images()

VALID_MODEL_VALIDATION = {
    "valid": True,
    "filepath": "/tmp/model.glb",
    "format": "glb",
    "checks": {
        "file_size": {"value": 2048, "passed": True},
        "header": {"passed": True, "version": 2},
        "declared_length": {"passed": True, "value": 2048, "actual": 2048},
        "json_chunk": {
            "passed": True,
            "scenes": 1,
            "nodes": 1,
            "meshes": 1,
            "materials": 1,
        },
        "materials": {"passed": True, "count": 1},
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(command_responses=None, tripo_api_key="test-key"):
    """Create a PipelineRunner with a fully mocked BlenderConnection.

    Args:
        command_responses: Dict mapping command names to return dicts.
            Merged on top of a happy-path default set.
        tripo_api_key: Value for settings.tripo_api_key.
    """
    defaults = {
        # Cleanup sub-steps
        "mesh_auto_repair": {"status": "success", "fixed": 2},
        "mesh_check_game_ready": {
            "game_ready": True,
            "grade": "A",
            "checks": {"poly_budget": {"passed": True, "value": 5000}},
        },
        "mesh_retopologize": {"status": "success", "final_faces": 8000},
        "uv_unwrap_xatlas": {"status": "success", "coverage": 0.98},
        "texture_create_pbr": {"status": "success"},
        # Smart material / weathering / quality gate
        "material_create_procedural": {"status": "success"},
        "weathering_apply": {"status": "success"},
        "autonomous_refine": {"status": "success", "iterations": 1},
        # Rig
        "rig_apply_template": {"status": "success", "bone_count": 42},
        "rig_auto_weight": {"status": "success"},
        # Animations
        "anim_generate_walk": {"status": "success", "frames": 30},
        "anim_generate_idle": {"status": "success", "frames": 60},
        "anim_generate_attack": {"status": "success", "frames": 20},
        "anim_generate_fly": {"status": "success", "frames": 40},
        "anim_generate_reaction": {"status": "success", "frames": 25},
        # LODs
        "pipeline_generate_lods": {"status": "success", "lod_count": 3},
        # Visual gate
        "render_contact_sheet": {
            "paths": VISUAL_GATE_IMAGES,
            "count": len(VISUAL_GATE_IMAGES),
            "angles": [[0, 12], [90, 12], [180, 12], [270, 12], [45, 28], [315, 28]],
            "beauty_applied": True,
        },
        # Export
        "export_fbx": {"status": "success", "filepath": "model.fbx"},
        "export_gltf": {"status": "success", "filepath": "model.glb"},
        # Import
        "execute_code": {"status": "success"},
    }
    if command_responses:
        defaults.update(command_responses)

    blender = MagicMock()

    async def mock_send(cmd, params=None):
        if cmd in defaults:
            return defaults[cmd]
        return {"status": "success"}

    blender.send_command = AsyncMock(side_effect=mock_send)

    settings = MagicMock()
    settings.tripo_api_key = tripo_api_key
    settings.tripo_session_cookie = ""
    settings.tripo_studio_token = ""
    return PipelineRunner(blender, settings)


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===========================================================================
# Constants tests
# ===========================================================================


class TestPipelineConstants:
    """Verify module-level constant tables are complete and consistent."""

    def test_material_presets_has_all_asset_types(self):
        expected = {"prop", "character", "creature", "weapon", "building", "vegetation"}
        assert set(MATERIAL_PRESETS.keys()) == expected

    def test_material_presets_values_are_strings(self):
        for k, v in MATERIAL_PRESETS.items():
            assert isinstance(v, str), f"MATERIAL_PRESETS[{k}] is not a string"

    def test_rig_templates_only_for_riggable_types(self):
        assert set(RIG_TEMPLATES.keys()) == RIGGABLE_TYPES

    def test_riggable_types_are_strings(self):
        for t in RIGGABLE_TYPES:
            assert isinstance(t, str)

    def test_animation_commands_keys(self):
        expected = {"walk", "run", "idle", "attack", "fly", "death", "hit", "spawn"}
        assert set(ANIMATION_COMMANDS.keys()) == expected

    def test_animation_commands_structure(self):
        for name, (cmd, params) in ANIMATION_COMMANDS.items():
            assert isinstance(cmd, str), f"Animation '{name}' command is not str"
            assert isinstance(params, dict), f"Animation '{name}' params is not dict"
            assert cmd.startswith("anim_"), f"Animation '{name}' cmd doesn't start with anim_"

    def test_import_extensions(self):
        expected = {".glb", ".gltf", ".fbx", ".obj"}
        assert IMPORT_EXTENSIONS == expected


# ===========================================================================
# _detect_asset_type tests
# ===========================================================================


class TestDetectAssetType:
    """Tests for PipelineRunner._detect_asset_type() heuristic."""

    def test_weapon_elongated_thin(self):
        stats = {"vertex_count": 3000, "dimensions": [0.1, 0.1, 2.0]}
        assert PipelineRunner._detect_asset_type("Sword", stats) == "weapon"

    def test_weapon_from_low_vert_elongated(self):
        stats = {"vertex_count": 5000, "dimensions": [0.15, 0.05, 1.5]}
        assert PipelineRunner._detect_asset_type("Axe", stats) == "weapon"

    def test_building_large_footprint(self):
        stats = {
            "vertex_count": 12000,
            "dimensions": [10.0, 10.0, 5.0],
            "non_manifold_edges": 20,
        }
        assert PipelineRunner._detect_asset_type("House", stats) == "building"

    def test_character_by_keyword(self):
        stats = {"vertex_count": 15000, "dimensions": [0.5, 0.4, 1.8]}
        assert PipelineRunner._detect_asset_type("PlayerCharacter", stats) == "character"

    def test_creature_by_keyword(self):
        stats = {"vertex_count": 15000, "dimensions": [0.6, 0.5, 1.5]}
        assert PipelineRunner._detect_asset_type("MonsterSpider", stats) == "creature"

    def test_character_high_verts_humanoid(self):
        stats = {"vertex_count": 25000, "dimensions": [0.5, 0.4, 1.7]}
        assert PipelineRunner._detect_asset_type("GenericFigure", stats) == "character"

    def test_vegetation_by_keyword(self):
        stats = {"vertex_count": 500, "dimensions": [1.0, 1.0, 3.0]}
        assert PipelineRunner._detect_asset_type("OakTree", stats) == "vegetation"

    def test_vegetation_bush_keyword(self):
        stats = {"vertex_count": 200, "dimensions": [0.5, 0.5, 0.3]}
        assert PipelineRunner._detect_asset_type("SmallBush", stats) == "vegetation"

    def test_prop_default(self):
        stats = {"vertex_count": 1000, "dimensions": [0.5, 0.5, 0.5]}
        assert PipelineRunner._detect_asset_type("Barrel", stats) == "prop"

    def test_prop_no_dimensions(self):
        stats = {"vertex_count": 500}
        assert PipelineRunner._detect_asset_type("Crate", stats) == "prop"

    def test_creature_non_humanoid_high_verts(self):
        stats = {"vertex_count": 15000, "dimensions": [3.0, 1.0, 0.5]}
        assert PipelineRunner._detect_asset_type("Serpent", stats) == "creature"

    def test_empty_stats_returns_prop(self):
        assert PipelineRunner._detect_asset_type("Unknown", {}) == "prop"


# ===========================================================================
# full_asset_pipeline tests
# ===========================================================================


class TestFullAssetPipeline:
    """Tests for PipelineRunner.full_asset_pipeline()."""

    def test_returns_dict(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert isinstance(result, dict)

    def test_success_status_on_happy_path(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert result["status"] == "success"

    def test_object_name_in_result(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert result["object_name"] == "Barrel"

    def test_asset_type_in_result(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel", asset_type="prop"))
        assert result["asset_type"] == "prop"

    def test_export_path_set(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "Barrel" in result["export_path"]
        assert result["export_path"].endswith(".fbx")

    def test_gltf_export_format(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel", export_format="gltf"))
        assert result["export_path"].endswith(".glb")

    def test_cleanup_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "cleanup" in result["steps"]
        assert "cleanup" in result["steps_completed"]

    def test_smart_material_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "smart_material" in result["steps"]
        assert "smart_material" in result["steps_completed"]

    def test_weathering_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel", weathering_preset="heavy"))
        assert "weathering" in result["steps"]
        assert "weathering" in result["steps_completed"]

    def test_weathering_skipped_when_none(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel", weathering_preset="none"))
        assert "weathering" not in result["steps"]

    def test_quality_gate_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "quality_gate" in result["steps"]

    def test_export_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "export" in result["steps"]
        assert "export" in result["steps_completed"]

    def test_validate_export_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "validate_export" in result["steps"]

    def test_lod_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "lod_generation" in result["steps"]

    # --- Material auto-selection ---

    def test_material_auto_prop(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Barrel", asset_type="prop"))
        # Check that material_create_procedural was called with old_wood
        calls = runner.blender.send_command.call_args_list
        mat_calls = [c for c in calls if c[0][0] == "material_create_procedural"]
        assert len(mat_calls) >= 1
        assert mat_calls[0][0][1]["preset"] == "old_wood"

    def test_material_auto_character(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Hero", asset_type="character"))
        calls = runner.blender.send_command.call_args_list
        mat_calls = [c for c in calls if c[0][0] == "material_create_procedural"]
        assert len(mat_calls) >= 1
        assert mat_calls[0][0][1]["preset"] == "worn_leather"

    def test_material_auto_creature(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Spider", asset_type="creature"))
        calls = runner.blender.send_command.call_args_list
        mat_calls = [c for c in calls if c[0][0] == "material_create_procedural"]
        assert len(mat_calls) >= 1
        assert mat_calls[0][0][1]["preset"] == "chitin"

    def test_material_auto_weapon(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Sword", asset_type="weapon"))
        calls = runner.blender.send_command.call_args_list
        mat_calls = [c for c in calls if c[0][0] == "material_create_procedural"]
        assert len(mat_calls) >= 1
        assert mat_calls[0][0][1]["preset"] == "rusted_armor"

    def test_material_auto_building(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Tower", asset_type="building"))
        calls = runner.blender.send_command.call_args_list
        mat_calls = [c for c in calls if c[0][0] == "material_create_procedural"]
        assert len(mat_calls) >= 1
        assert mat_calls[0][0][1]["preset"] == "dungeon_stone"

    def test_material_auto_vegetation(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Tree", asset_type="vegetation"))
        calls = runner.blender.send_command.call_args_list
        mat_calls = [c for c in calls if c[0][0] == "material_create_procedural"]
        assert len(mat_calls) >= 1
        assert mat_calls[0][0][1]["preset"] == "bark"

    def test_material_explicit_preset(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Barrel", material_preset="obsidian"))
        calls = runner.blender.send_command.call_args_list
        mat_calls = [c for c in calls if c[0][0] == "material_create_procedural"]
        assert len(mat_calls) >= 1
        assert mat_calls[0][0][1]["preset"] == "obsidian"

    # --- Rig logic ---

    def test_rig_for_character(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Hero", asset_type="character"))
        assert "rig_template" in result["steps_completed"]
        assert "rig_auto_weight" in result["steps_completed"]

    def test_rig_for_creature(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Spider", asset_type="creature"))
        assert "rig_template" in result["steps_completed"]

    def test_no_rig_for_prop(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel", asset_type="prop"))
        assert "rig_template" not in result["steps_completed"]
        assert "rig_auto_weight" not in result["steps_completed"]

    def test_no_rig_for_weapon(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Sword", asset_type="weapon"))
        assert "rig_template" not in result["steps_completed"]

    def test_no_rig_for_building(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Tower", asset_type="building"))
        assert "rig_template" not in result["steps_completed"]

    def test_rig_template_auto_character(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Hero", asset_type="character"))
        calls = runner.blender.send_command.call_args_list
        rig_calls = [c for c in calls if c[0][0] == "rig_apply_template"]
        assert len(rig_calls) >= 1
        assert rig_calls[0][0][1]["template"] == "humanoid"

    def test_rig_template_auto_creature(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline("Spider", asset_type="creature"))
        calls = runner.blender.send_command.call_args_list
        rig_calls = [c for c in calls if c[0][0] == "rig_apply_template"]
        assert len(rig_calls) >= 1
        assert rig_calls[0][0][1]["template"] == "quadruped"

    def test_rig_template_explicit(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline(
            "Dragon", asset_type="creature", rig_template="bird"
        ))
        calls = runner.blender.send_command.call_args_list
        rig_calls = [c for c in calls if c[0][0] == "rig_apply_template"]
        assert len(rig_calls) >= 1
        assert rig_calls[0][0][1]["template"] == "bird"

    # --- Animation logic ---

    def test_animations_generated(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline(
            "Hero", asset_type="character", animations=["idle", "walk", "attack"]
        ))
        assert "anim_idle" in result["steps_completed"]
        assert "anim_walk" in result["steps_completed"]
        assert "anim_attack" in result["steps_completed"]

    def test_animations_step_dict(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline(
            "Hero", asset_type="character", animations=["idle", "walk"]
        ))
        assert "animations" in result["steps"]
        assert "idle" in result["steps"]["animations"]
        assert "walk" in result["steps"]["animations"]

    def test_no_animations_when_not_requested(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "animations" not in result["steps"]

    def test_unknown_animation_warns(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline(
            "Hero", asset_type="character", animations=["dance"]
        ))
        assert any("dance" in w for w in result["warnings"])

    def test_all_valid_animation_names(self):
        """Every name in ANIMATION_COMMANDS should be processable."""
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline(
            "Hero",
            asset_type="character",
            animations=list(ANIMATION_COMMANDS.keys()),
        ))
        for anim_name in ANIMATION_COMMANDS:
            assert f"anim_{anim_name}" in result["steps_completed"], (
                f"Animation '{anim_name}' was not completed"
            )

    def test_run_animation_parsed(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline(
            "Hero", asset_type="character", animations=["run"]
        ))
        calls = runner.blender.send_command.call_args_list
        walk_calls = [c for c in calls if c[0][0] == "anim_generate_walk"]
        assert any(c[0][1].get("speed") == "run" for c in walk_calls)

    def test_death_animation_parsed(self):
        runner = _make_runner()
        _run(runner.full_asset_pipeline(
            "Hero", asset_type="character", animations=["death"]
        ))
        calls = runner.blender.send_command.call_args_list
        react_calls = [c for c in calls if c[0][0] == "anim_generate_reaction"]
        assert any(c[0][1].get("reaction_type") == "death" for c in react_calls)

    # --- Import logic ---

    def test_import_glb_file(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("model.glb"))
        assert "import" in result["steps_completed"]
        # Object name should be the stem
        assert result["object_name"] == "model"

    def test_import_fbx_file(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("character.fbx"))
        assert "import" in result["steps_completed"]
        assert result["object_name"] == "character"

    def test_import_obj_file(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("scene.obj"))
        assert "import" in result["steps_completed"]
        assert result["object_name"] == "scene"

    def test_no_import_for_blender_object(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert "import" not in result["steps_completed"]

    def test_import_gltf_file(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("model.gltf"))
        assert "import" in result["steps_completed"]

    # --- Export path construction ---

    def test_export_dir_default(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert result["export_path"] == "Barrel.fbx"

    def test_export_dir_custom(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel", export_dir="/output"))
        # Path should combine export_dir and name (platform-agnostic check)
        export_path = result["export_path"].replace("\\", "/")
        assert "/output" in export_path
        assert "Barrel" in export_path

    def test_export_format_gltf_extension(self):
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel", export_format="gltf"))
        assert result["export_path"].endswith(".glb")

    # --- Error handling ---

    def test_import_failure_aborts(self):
        from veilbreakers_mcp.shared.blender_client import BlenderCommandError
        from veilbreakers_mcp.shared.models import BlenderResponse

        runner = _make_runner()

        original_side_effect = runner.blender.send_command.side_effect

        async def fail_on_import(cmd, params=None):
            if cmd == "execute_code":
                raise BlenderCommandError(
                    BlenderResponse(status="error", message="Import failed", result=None)
                )
            return await original_side_effect(cmd, params)

        runner.blender.send_command = AsyncMock(side_effect=fail_on_import)
        result = _run(runner.full_asset_pipeline("broken.glb"))
        assert result["status"] == "failed"
        assert "Import failed" in result.get("error", "")

    def test_cleanup_failure_aborts(self):
        from veilbreakers_mcp.shared.blender_client import BlenderCommandError
        from veilbreakers_mcp.shared.models import BlenderResponse

        runner = _make_runner()

        original_side_effect = runner.blender.send_command.side_effect

        async def fail_on_repair(cmd, params=None):
            if cmd == "mesh_auto_repair":
                raise BlenderCommandError(
                    BlenderResponse(status="error", message="Repair crashed", result=None)
                )
            return await original_side_effect(cmd, params)

        runner.blender.send_command = AsyncMock(side_effect=fail_on_repair)
        result = _run(runner.full_asset_pipeline("Barrel"))
        assert result["status"] == "failed"

    def test_non_critical_step_failure_continues(self):
        """Weathering failure should not abort the pipeline."""
        from veilbreakers_mcp.shared.blender_client import BlenderCommandError
        from veilbreakers_mcp.shared.models import BlenderResponse

        runner = _make_runner()

        original_side_effect = runner.blender.send_command.side_effect

        async def fail_on_weathering(cmd, params=None):
            if cmd == "weathering_apply":
                raise BlenderCommandError(
                    BlenderResponse(status="error", message="Weathering failed", result=None)
                )
            return await original_side_effect(cmd, params)

        runner.blender.send_command = AsyncMock(side_effect=fail_on_weathering)
        result = _run(runner.full_asset_pipeline("Barrel"))
        # Pipeline should still succeed overall
        assert result["status"] == "success"
        assert any("weathering" in w.lower() for w in result["warnings"])

    def test_all_expected_step_keys_in_results(self):
        """Result dict must contain all documented keys."""
        runner = _make_runner()
        result = _run(runner.full_asset_pipeline("Barrel"))
        required_keys = {
            "object_name", "asset_type", "export_path", "steps",
            "steps_completed", "warnings", "status",
        }
        assert required_keys.issubset(set(result.keys()))


# ===========================================================================
# generate_and_process tests
# ===========================================================================


class TestGenerateAndProcess:
    """Tests for PipelineRunner.generate_and_process()."""

    def test_missing_prompt_and_image_fails(self):
        runner = _make_runner()
        result = _run(runner.generate_and_process())
        assert result["status"] == "failed"
        assert "prompt" in result["error"].lower() or "image_path" in result["error"].lower()

    def test_missing_api_key_fails(self):
        runner = _make_runner(tripo_api_key="")
        result = _run(runner.generate_and_process(prompt="a barrel"))
        assert result["status"] == "failed"
        assert "TRIPO_API_KEY" in result["error"]

    @patch("veilbreakers_mcp.shared.pipeline_runner.validate_generated_model_file", return_value=VALID_MODEL_VALIDATION)
    @patch("veilbreakers_mcp.shared.pipeline_runner.PipelineRunner.full_asset_pipeline")
    def test_successful_text_generation(self, mock_pipeline, _mock_validation):
        """With mocked Tripo + mocked pipeline, the flow succeeds."""
        mock_pipeline.return_value = {
            "status": "success",
            "export_path": "barrel.fbx",
            "object_name": "model",
            "steps_completed": ["cleanup", "export"],
        }

        runner = _make_runner()

        with patch(
            "veilbreakers_mcp.shared.tripo_client.TripoGenerator"
        ) as MockTripo:
            mock_gen = MagicMock()
            mock_gen.generate_from_text = AsyncMock(return_value={
                "status": "success",
                "model_path": "/tmp/model.glb",
                "pbr_model_path": "/tmp/model_pbr.glb",
                "task_id": "test-123",
            })
            MockTripo.return_value = mock_gen

            result = _run(runner.generate_and_process(prompt="a wooden barrel"))

        assert result["status"] == "success"
        assert "generation" in result
        assert "pipeline" in result
        assert result["generation"]["status"] == "success"

    @patch("veilbreakers_mcp.shared.pipeline_runner.validate_generated_model_file", return_value=VALID_MODEL_VALIDATION)
    @patch("veilbreakers_mcp.shared.pipeline_runner.PipelineRunner.full_asset_pipeline")
    def test_successful_image_generation(self, mock_pipeline, _mock_validation):
        mock_pipeline.return_value = {
            "status": "success",
            "export_path": "model.fbx",
            "object_name": "model",
            "steps_completed": ["cleanup", "export"],
        }

        runner = _make_runner()

        with patch(
            "veilbreakers_mcp.shared.tripo_client.TripoGenerator"
        ) as MockTripo:
            mock_gen = MagicMock()
            mock_gen.generate_from_image = AsyncMock(return_value={
                "status": "success",
                "model_path": "/tmp/model.glb",
                "task_id": "test-456",
            })
            MockTripo.return_value = mock_gen

            result = _run(runner.generate_and_process(image_path="/tmp/ref.png"))

        assert result["status"] == "success"

    @patch("veilbreakers_mcp.shared.pipeline_runner.validate_generated_model_file", return_value=VALID_MODEL_VALIDATION)
    @patch("veilbreakers_mcp.shared.pipeline_runner.PipelineRunner.full_asset_pipeline")
    def test_tripo_failure_reported(self, mock_pipeline, _mock_validation):
        runner = _make_runner()

        with patch(
            "veilbreakers_mcp.shared.tripo_client.TripoGenerator"
        ) as MockTripo:
            mock_gen = MagicMock()
            mock_gen.generate_from_text = AsyncMock(return_value={
                "status": "failed",
                "error": "API rate limit exceeded",
            })
            MockTripo.return_value = mock_gen

            result = _run(runner.generate_and_process(prompt="a barrel"))

        assert result["status"] == "failed"
        assert "Tripo generation failed" in result["error"]
        mock_pipeline.assert_not_called()

    @patch("veilbreakers_mcp.shared.pipeline_runner.validate_generated_model_file", return_value=VALID_MODEL_VALIDATION)
    @patch("veilbreakers_mcp.shared.pipeline_runner.PipelineRunner.full_asset_pipeline")
    def test_prefers_pbr_model(self, mock_pipeline, _mock_validation):
        """Should prefer pbr_model_path over model_path."""
        mock_pipeline.return_value = {
            "status": "success",
            "export_path": "model.fbx",
            "object_name": "model_pbr",
            "steps_completed": ["cleanup", "export"],
        }

        runner = _make_runner()

        with patch(
            "veilbreakers_mcp.shared.tripo_client.TripoGenerator"
        ) as MockTripo:
            mock_gen = MagicMock()
            mock_gen.generate_from_text = AsyncMock(return_value={
                "status": "success",
                "model_path": "/tmp/model.glb",
                "pbr_model_path": "/tmp/model_pbr.glb",
                "task_id": "test-789",
            })
            MockTripo.return_value = mock_gen

            _run(runner.generate_and_process(prompt="a barrel"))

        # full_asset_pipeline should have been called with the PBR model path
        call_args = mock_pipeline.call_args
        assert "model_pbr.glb" in call_args[1]["object_name"]

    @patch("veilbreakers_mcp.shared.pipeline_runner.validate_generated_model_file", return_value=VALID_MODEL_VALIDATION)
    @patch("veilbreakers_mcp.shared.pipeline_runner.PipelineRunner.full_asset_pipeline")
    def test_export_path_propagated(self, mock_pipeline, _mock_validation):
        mock_pipeline.return_value = {
            "status": "success",
            "export_path": "/out/barrel.fbx",
            "object_name": "barrel",
            "steps_completed": ["cleanup", "export"],
        }

        runner = _make_runner()

        with patch(
            "veilbreakers_mcp.shared.tripo_client.TripoGenerator"
        ) as MockTripo:
            mock_gen = MagicMock()
            mock_gen.generate_from_text = AsyncMock(return_value={
                "status": "success",
                "model_path": "/tmp/model.glb",
                "task_id": "test-000",
            })
            MockTripo.return_value = mock_gen

            result = _run(runner.generate_and_process(prompt="a barrel"))

        assert result["export_path"] == "/out/barrel.fbx"

    def test_result_structure(self):
        """Result must contain generation, pipeline, and status keys."""
        runner = _make_runner(tripo_api_key="")
        result = _run(runner.generate_and_process(prompt="a barrel"))
        # Even on failure, structure should be present
        assert "generation" in result
        assert "pipeline" in result
        assert "status" in result
