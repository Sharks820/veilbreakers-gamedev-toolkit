"""Unit tests for tripo_post_processor module.

All tests use mocked extract/delight/validate calls -- no real GLB, Blender,
or network required.
"""

from __future__ import annotations

import os
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

_MOCK_CHANNELS_FULL = {
    "albedo": "/tmp/textures/albedo.png",
    "orm": "/tmp/textures/orm.png",
    "normal": "/tmp/textures/normal.png",
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
        "orm": "/tmp/textures/orm.png",
        "normal": "/tmp/textures/normal.png",
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
