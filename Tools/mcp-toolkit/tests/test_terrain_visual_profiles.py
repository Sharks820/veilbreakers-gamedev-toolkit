from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from veilbreakers_mcp import blender_server
from veilbreakers_mcp.shared.visual_validation import (
    aaa_verify_map,
    analyze_render_image,
)


def _write_framed_cave_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (135, 116, 94))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 70), fill=(170, 160, 148))
    draw.polygon(
        [(12, 255), (56, 148), (88, 112), (168, 112), (200, 148), (244, 255)],
        fill=(105, 86, 68),
        outline=(220, 205, 185),
    )
    draw.ellipse((72, 78, 184, 210), fill=(12, 12, 18))
    draw.arc((62, 68, 194, 220), start=180, end=360, fill=(245, 230, 210), width=6)
    draw.arc((52, 58, 204, 230), start=182, end=358, fill=(214, 196, 172), width=4)
    draw.line((38, 218, 110, 160), fill=(208, 194, 176), width=5)
    draw.line((216, 218, 146, 160), fill=(208, 194, 176), width=5)
    draw.line((28, 112, 80, 86), fill=(232, 220, 204), width=4)
    draw.line((176, 90, 228, 124), fill=(232, 220, 204), width=4)
    draw.line((30, 182, 78, 206), fill=(206, 188, 162), width=4)
    draw.line((178, 212, 226, 180), fill=(206, 188, 162), width=4)
    draw.rectangle((36, 210, 220, 246), fill=(92, 78, 58))
    image.save(path)


def _write_flat_terrain_image(path: Path) -> None:
    Image.new("RGB", (256, 256), (128, 128, 128)).save(path)


def _write_waterfall_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (42, 54, 66))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 72), fill=(82, 98, 112))
    draw.polygon(
        [(0, 255), (38, 144), (72, 108), (184, 108), (218, 144), (255, 255)],
        fill=(74, 66, 58),
        outline=(182, 168, 148),
    )
    draw.rectangle((104, 18, 148, 210), fill=(218, 236, 248), outline=(255, 255, 255))
    draw.line((126, 18, 126, 210), fill=(255, 255, 255), width=6)
    draw.ellipse((82, 190, 172, 242), fill=(170, 220, 244), outline=(250, 250, 255), width=5)
    draw.arc((70, 182, 184, 248), start=10, end=170, fill=(244, 248, 255), width=4)
    draw.line((84, 102, 104, 40), fill=(198, 184, 164), width=4)
    draw.line((172, 102, 152, 40), fill=(198, 184, 164), width=4)
    image.save(path)


class _DummyBlender:
    def __init__(self, handler):
        self._handler = handler

    async def send_command(self, command, params):
        return await self._handler(command, params)


def test_analyze_render_image_passes_framed_cave_profile(tmp_path):
    path = tmp_path / "cave.png"
    _write_framed_cave_image(path)

    result = analyze_render_image(str(path), validation_profile="terrain_cave")

    assert result["valid"] is True
    assert result["semantic_issues"] == []
    assert result["semantic_score"] >= 60.0
    assert result["metrics"]["semantic_enclosure"] >= 58.0


def test_analyze_render_image_flags_flat_waterfall_profile(tmp_path):
    path = tmp_path / "flat.png"
    _write_flat_terrain_image(path)

    result = analyze_render_image(str(path), validation_profile="terrain_waterfall")

    assert result["valid"] is False
    assert result["semantic_issues"]
    assert any("terrain_waterfall" in issue for issue in result["semantic_issues"])


def test_aaa_verify_map_surfaces_failed_angle_labels_with_profile(tmp_path):
    path = tmp_path / "waterfall.png"
    _write_waterfall_image(path)

    result = aaa_verify_map(
        [str(path)],
        min_score=10,
        angle_labels=["waterfall_side"],
        validation_profile="terrain_waterfall",
    )

    assert result["validation_profile"] == "terrain_waterfall"
    assert result["per_angle"][0]["angle_label"] == "waterfall_side"
    assert result["failed_angle_labels"] == [] or result["failed_angle_labels"] == ["waterfall_side"]


def test_aaa_verify_map_rejects_unknown_profile(tmp_path):
    path = tmp_path / "cave.png"
    _write_framed_cave_image(path)

    result = aaa_verify_map([str(path)], validation_profile="unknown_profile")

    assert result["passed"] is False
    assert result["failed_angles"] == [0]
    assert result["per_angle"][0]["validation_profile"] == "unknown_profile"
    assert any("Unknown validation_profile" in issue for issue in result["per_angle"][0]["issues"])


@pytest.mark.asyncio
async def test_asset_pipeline_aaa_verify_forwards_validation_profile(monkeypatch, tmp_path):
    captured: dict = {}

    async def _handler(command, params):
        if command == "render_angle":
            output_path = Path(params["output_path"])
            _write_framed_cave_image(output_path)
            return {"status": "success", "output_path": str(output_path)}
        raise AssertionError(f"unexpected command: {command}")

    def _fake_verify(paths, min_score=60, **kwargs):
        captured["paths"] = list(paths)
        captured["min_score"] = min_score
        captured.update(kwargs)
        return {
            "passed": False,
            "total_score": 42.0,
            "per_angle": [{
                "angle_id": 0,
                "angle_label": "front",
                "score": 42.0,
                "issues": ["terrain_cliff: cliff skyline and edge break-up are too soft (score=41.0)"],
                "semantic_issues": ["terrain_cliff: cliff skyline and edge break-up are too soft (score=41.0)"],
                "semantic_metrics": {"silhouette_read": 41.0},
                "semantic_score": 41.0,
                "validation_profile": kwargs.get("validation_profile"),
                "passed": False,
            }],
            "failed_angles": [0],
            "failed_angle_labels": ["front"],
            "missing_angles": [],
            "validation_profile": kwargs.get("validation_profile"),
            "issues": ["Validation profile 'terrain_cliff' failed for: front"],
        }

    monkeypatch.setattr(
        blender_server,
        "get_blender_connection",
        lambda: _DummyBlender(_handler),
    )
    monkeypatch.setattr(blender_server, "aaa_verify_map", _fake_verify, raising=False)

    result = await blender_server.asset_pipeline(
        action="aaa_verify",
        angles=1,
        validation_profile="terrain_cliff",
    )

    assert result["status"] == "failed"
    assert result["verification"]["validation_profile"] == "terrain_cliff"
    assert captured["validation_profile"] == "terrain_cliff"
    assert captured["required_angle_count"] == 1
