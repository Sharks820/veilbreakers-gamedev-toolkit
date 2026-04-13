"""Unit tests for tripo_post_processor module.

All tests use mocked extract/delight/validate calls -- no real GLB, Blender,
or network required.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from veilbreakers_mcp.shared.tripo_post_processor import (
    post_process_tripo_model,
    score_variants,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TMPDIR = Path(tempfile.gettempdir())
_MOCK_CHANNELS_FULL = {
    "albedo": str(_TMPDIR / "textures" / "albedo.png"),
    "orm": str(_TMPDIR / "textures" / "orm.png"),
    "normal": str(_TMPDIR / "textures" / "normal.png"),
}

_PALETTE_PASSED = {"passed": True, "issues": [], "stats": {"mean_saturation": 0.3}}
_PALETTE_FAILED = {
    "passed": False,
    "issues": [{"rule": "saturation_cap", "value": 0.72, "threshold": 0.55, "severity": "error"}],
    "stats": {"mean_saturation": 0.72},
}
_ROUGHNESS_PASSED = {"passed": True, "variance": 0.08, "min_variance": 0.05}
_ROUGHNESS_FAILED = {"passed": False, "variance": 0.01, "min_variance": 0.05}

_DELIGHT_APPLIED = {
    "correction_applied": True,
    "mean_luminance_before": 0.6,
    "mean_luminance_after": 0.5,
}
_DELIGHT_NOT_APPLIED = {
    "correction_applied": False,
    "mean_luminance_before": 0.5,
    "mean_luminance_after": 0.5,
}


def _make_mock_file_exists(paths: set[str]):
    """Return a side_effect for os.path.isfile that treats *paths* as existing."""
    real_isfile = os.path.isfile

    def _isfile(p: str) -> bool:
        if p in paths:
            return True
        return real_isfile(p)

    return _isfile


# ---------------------------------------------------------------------------
# Test 1: all steps run when all channels present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_process_runs_all_steps_when_all_channels_present(
    tmp_path: Path,
) -> None:
    """post_process_tripo_model calls extract, delight, palette, roughness steps."""
    glb_path = str(tmp_path / "model.glb")
    (tmp_path / "model.glb").write_bytes(b"fake")

    delit_path = str(tmp_path / "textures" / "albedo_delit.png")
    mock_files = {
        _MOCK_CHANNELS_FULL["albedo"],
        _MOCK_CHANNELS_FULL["orm"],
        _MOCK_CHANNELS_FULL["normal"],
        delit_path,
    }

    with (
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.extract_glb_textures",
            return_value=_MOCK_CHANNELS_FULL,
        ) as mock_extract,
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.delight_albedo",
            return_value=_DELIGHT_APPLIED,
        ) as mock_delight,
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_palette",
            return_value=_PALETTE_PASSED,
        ) as mock_palette,
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_roughness_map",
            return_value=_ROUGHNESS_PASSED,
        ) as mock_roughness,
        mock.patch("os.path.isfile", side_effect=_make_mock_file_exists(mock_files)),
    ):
        result = await post_process_tripo_model(glb_path, str(tmp_path))

    mock_extract.assert_called_once()
    mock_delight.assert_called_once()
    mock_palette.assert_called_once()
    mock_roughness.assert_called_once()

    assert result["channels"] == _MOCK_CHANNELS_FULL
    assert result["palette_validation"]["passed"] is True
    assert result["roughness_validation"]["passed"] is True
    assert result["channel_score"] == 100  # all channels + both validations passed


# ---------------------------------------------------------------------------
# Test 2: delight skipped when no albedo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_process_skips_delight_when_no_albedo(tmp_path: Path) -> None:
    """de-lighting step is skipped when albedo is absent from channels."""
    glb_path = str(tmp_path / "model.glb")
    (tmp_path / "model.glb").write_bytes(b"fake")

    channels_no_albedo = {
        "orm": str(_TMPDIR / "textures" / "orm.png"),
        "normal": str(_TMPDIR / "textures" / "normal.png"),
    }
    mock_files = {channels_no_albedo["orm"], channels_no_albedo["normal"]}

    with (
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.extract_glb_textures",
            return_value=channels_no_albedo,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.delight_albedo",
        ) as mock_delight,
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_palette",
            return_value=_PALETTE_PASSED,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_roughness_map",
            return_value=_ROUGHNESS_PASSED,
        ),
        mock.patch("os.path.isfile", side_effect=_make_mock_file_exists(mock_files)),
    ):
        result = await post_process_tripo_model(glb_path, str(tmp_path))

    mock_delight.assert_not_called()
    assert result["albedo_delit"] is None
    # palette validation is skipped too (no albedo for it)
    assert result["palette_validation"]["passed"] is False


# ---------------------------------------------------------------------------
# Test 3: partial result when extraction fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_process_returns_partial_result_when_extraction_fails(
    tmp_path: Path,
) -> None:
    """Returns early with extraction_error key when extract_glb_textures raises."""
    glb_path = str(tmp_path / "model.glb")
    (tmp_path / "model.glb").write_bytes(b"fake")

    with mock.patch(
        "veilbreakers_mcp.shared.tripo_post_processor.extract_glb_textures",
        side_effect=ValueError("bad GLB"),
    ):
        result = await post_process_tripo_model(glb_path, str(tmp_path))

    assert "extraction_error" in result
    assert "bad GLB" in result["extraction_error"]
    assert result["channels"] == {}
    assert result["channel_score"] == 0


# ---------------------------------------------------------------------------
# Test 3b: non-fatal step failures surface explicit warnings/errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_process_surfaces_delight_failure(tmp_path: Path) -> None:
    """De-light failures should be reported instead of silently swallowed."""
    glb_path = str(tmp_path / "model.glb")
    (tmp_path / "model.glb").write_bytes(b"fake")

    mock_files = set(_MOCK_CHANNELS_FULL.values())

    with (
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.extract_glb_textures",
            return_value=_MOCK_CHANNELS_FULL,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.delight_albedo",
            side_effect=RuntimeError("delight exploded"),
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_palette",
            return_value=_PALETTE_PASSED,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_roughness_map",
            return_value=_ROUGHNESS_PASSED,
        ),
        mock.patch("os.path.isfile", side_effect=_make_mock_file_exists(mock_files)),
    ):
        result = await post_process_tripo_model(glb_path, str(tmp_path))

    assert result["delight_error"] == "delight exploded"
    assert any("delight_failed" in warning for warning in result["warnings"])
    assert result["palette_validation"]["passed"] is True


@pytest.mark.asyncio
async def test_post_process_surfaces_validation_failures(tmp_path: Path) -> None:
    """Palette and roughness validator exceptions should be visible in output."""
    glb_path = str(tmp_path / "model.glb")
    (tmp_path / "model.glb").write_bytes(b"fake")

    mock_files = set(_MOCK_CHANNELS_FULL.values())

    with (
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.extract_glb_textures",
            return_value=_MOCK_CHANNELS_FULL,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.delight_albedo",
            return_value=_DELIGHT_NOT_APPLIED,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_palette",
            side_effect=RuntimeError("palette blew up"),
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_roughness_map",
            side_effect=RuntimeError("roughness blew up"),
        ),
        mock.patch("os.path.isfile", side_effect=_make_mock_file_exists(mock_files)),
    ):
        result = await post_process_tripo_model(glb_path, str(tmp_path))

    assert result["palette_validation_error"] == "palette blew up"
    assert result["roughness_validation_error"] == "roughness blew up"
    assert any("palette_validation_failed" in warning for warning in result["warnings"])
    assert any("roughness_validation_failed" in warning for warning in result["warnings"])
    assert result["channel_score"] == 75


# ---------------------------------------------------------------------------
# Test 4: score_variants orders by channel_score
# ---------------------------------------------------------------------------

def test_score_variants_orders_by_channel_score() -> None:
    """score_variants returns variants sorted best (highest score) first."""
    variants = [
        {"channel_score": 50, "channels": {"albedo": "a"}},
        {"channel_score": 100, "channels": {"albedo": "b", "orm": "c", "normal": "d"}},
        {"channel_score": 75, "channels": {"albedo": "e", "orm": "f"}},
    ]

    ranked = score_variants(variants)

    assert ranked[0]["channel_score"] == 100
    assert ranked[1]["channel_score"] == 75
    assert ranked[2]["channel_score"] == 50


# ---------------------------------------------------------------------------
# Test 5: score is 100 for perfect model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_is_100_for_perfect_model(tmp_path: Path) -> None:
    """channel_score is 100 when all channels present and all validations pass."""
    glb_path = str(tmp_path / "model.glb")
    (tmp_path / "model.glb").write_bytes(b"fake")

    delit_path = str(tmp_path / "textures" / "albedo_delit.png")
    mock_files = set(_MOCK_CHANNELS_FULL.values()) | {delit_path}

    with (
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.extract_glb_textures",
            return_value=_MOCK_CHANNELS_FULL,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.delight_albedo",
            return_value=_DELIGHT_APPLIED,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_palette",
            return_value=_PALETTE_PASSED,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_roughness_map",
            return_value=_ROUGHNESS_PASSED,
        ),
        mock.patch("os.path.isfile", side_effect=_make_mock_file_exists(mock_files)),
    ):
        result = await post_process_tripo_model(glb_path, str(tmp_path))

    assert result["channel_score"] == 100, (
        f"Expected 100, got {result['channel_score']}. "
        f"palette={result['palette_validation']}, roughness={result['roughness_validation']}"
    )


# ---------------------------------------------------------------------------
# Test 6: palette deviation metrics in output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_palette_deviation_metrics_in_output(tmp_path: Path) -> None:
    """palette_validation issues list contains {rule, value, threshold} dicts."""
    glb_path = str(tmp_path / "model.glb")
    (tmp_path / "model.glb").write_bytes(b"fake")

    mock_files = set(_MOCK_CHANNELS_FULL.values())

    with (
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.extract_glb_textures",
            return_value=_MOCK_CHANNELS_FULL,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.delight_albedo",
            return_value=_DELIGHT_NOT_APPLIED,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_palette",
            return_value=_PALETTE_FAILED,
        ),
        mock.patch(
            "veilbreakers_mcp.shared.tripo_post_processor.validate_roughness_map",
            return_value=_ROUGHNESS_FAILED,
        ),
        mock.patch("os.path.isfile", side_effect=_make_mock_file_exists(mock_files)),
    ):
        result = await post_process_tripo_model(glb_path, str(tmp_path))

    palette = result["palette_validation"]
    assert palette["passed"] is False
    assert len(palette["issues"]) > 0

    issue = palette["issues"][0]
    assert "rule" in issue, "issue should have 'rule' key"
    assert "value" in issue, "issue should have 'value' key"
    assert "threshold" in issue, "issue should have 'threshold' key"

    # Score should be reduced due to failed validations (no roughness, no palette)
    # albedo=25, orm=25, normal=25, palette=0, roughness=0 → 75
    assert result["channel_score"] == 75


# ---------------------------------------------------------------------------
# Helper: create a mock PipelineRunner for generate_and_process tests
# ---------------------------------------------------------------------------

def _make_mock_runner(tmp_path, mock_post_process_fn, mock_full_pipeline_fn):
    """Set up all patches and call generate_and_process with mocked dependencies."""
    from unittest.mock import MagicMock

    runner = MagicMock()
    runner.settings = MagicMock()
    runner.settings.preferred_3d_backend = ""
    runner.settings.stable_fast3d_repo_path = ""
    runner.settings.stable_fast3d_python = ""
    runner.settings.stable_fast3d_device = "auto"
    runner.settings.stable_fast3d_texture_resolution = 512
    runner.settings.stable_fast3d_remesh_option = "triangle"
    runner.settings.stable_fast3d_target_vertex_count = 20000
    runner.settings.tripo_api_key = "test-key"
    runner.settings.tripo_session_cookie = ""
    runner.settings.tripo_studio_token = ""
    runner.settings.blender_timeout = 300
    # Wire up the async methods via AsyncMock
    runner.full_asset_pipeline = mock_full_pipeline_fn
    return runner


async def _run_generate_and_process(tmp_path, runner, mock_post_process_fn):
    """Execute generate_and_process with patched dependencies."""
    from unittest.mock import AsyncMock, patch
    from veilbreakers_mcp.shared.pipeline_runner import PipelineRunner

    gen_result = {"status": "success", "model_path": str(tmp_path / "model.glb")}
    (tmp_path / "model.glb").write_bytes(b"fake-glb")

    mock_gen = AsyncMock()
    mock_gen.generate_from_text = AsyncMock(return_value=gen_result)
    mock_gen.close = AsyncMock()

    pp_module = "veilbreakers_mcp.shared.tripo_post_processor"
    runner_module = "veilbreakers_mcp.shared.pipeline_runner"
    with (
        patch(f"{pp_module}.post_process_tripo_model", side_effect=mock_post_process_fn),
        patch(f"{runner_module}.validate_generated_model_file", return_value={"valid": True}),
        patch("veilbreakers_mcp.shared.tripo_client.TripoGenerator", return_value=mock_gen),
    ):
        result = await PipelineRunner.generate_and_process(
            runner,
            prompt="dark fantasy sword",
            output_dir=str(tmp_path),
        )
    return result


# ---------------------------------------------------------------------------
# Test 7: generate_and_process extracts textures before pipeline (SAFE-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_and_process_extracts_textures(tmp_path: Path) -> None:
    """generate_and_process calls post_process_tripo_model BEFORE full_asset_pipeline."""
    from unittest.mock import AsyncMock

    call_order: list[str] = []

    async def mock_post_process(glb_path, out_dir, asset_type="prop"):
        call_order.append("post_process")
        return {
            "channels": {"albedo": "/fake/albedo.png", "orm": "/fake/orm.png"},
            "albedo_delit": "/fake/albedo_delit.png",
            "channel_score": 75,
        }

    async def mock_full_pipeline(*args, **kwargs):
        call_order.append("full_pipeline")
        return {"status": "success", "export_path": "/fake/export.fbx"}

    runner = _make_mock_runner(tmp_path, mock_post_process, AsyncMock(side_effect=mock_full_pipeline))
    await _run_generate_and_process(tmp_path, runner, mock_post_process)

    assert "post_process" in call_order, "post_process_tripo_model was not called"
    assert "full_pipeline" in call_order, "full_asset_pipeline was not called"
    assert call_order.index("post_process") < call_order.index("full_pipeline"), \
        "post_process must be called BEFORE full_asset_pipeline"


# ---------------------------------------------------------------------------
# Test 8: generate_and_process passes delit channel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_and_process_passes_delit_channel(tmp_path: Path) -> None:
    """When post_process returns albedo_delit, it appears in texture_channels."""
    from unittest.mock import AsyncMock

    captured_kwargs: dict = {}

    async def mock_post_process(glb_path, out_dir, asset_type="prop"):
        return {
            "channels": {"albedo": "/fake/albedo.png"},
            "albedo_delit": "/fake/albedo_delit.png",
            "channel_score": 50,
        }

    async def mock_full_pipeline(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return {"status": "success"}

    runner = _make_mock_runner(tmp_path, mock_post_process, AsyncMock(side_effect=mock_full_pipeline))
    await _run_generate_and_process(tmp_path, runner, mock_post_process)

    assert captured_kwargs.get("has_extracted_textures") is True
    tex_channels = captured_kwargs.get("texture_channels", {})
    assert "albedo_delit" in tex_channels, "albedo_delit should be in texture_channels"


# ---------------------------------------------------------------------------
# Test 9: generate_and_process handles empty extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_and_process_handles_empty_extraction(tmp_path: Path) -> None:
    """When post_process returns empty channels, has_extracted_textures=False."""
    from unittest.mock import AsyncMock

    captured_kwargs: dict = {}

    async def mock_post_process(glb_path, out_dir, asset_type="prop"):
        return {
            "channels": {},
            "albedo_delit": None,
            "channel_score": 0,
        }

    async def mock_full_pipeline(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return {"status": "success"}

    runner = _make_mock_runner(tmp_path, mock_post_process, AsyncMock(side_effect=mock_full_pipeline))
    await _run_generate_and_process(tmp_path, runner, mock_post_process)

    assert captured_kwargs.get("has_extracted_textures") is False
    assert captured_kwargs.get("texture_channels") is None
