"""Tests for visual quality validation helpers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from veilbreakers_mcp.shared.visual_validation import (
    analyze_render_image,
    validate_render_screens,
)


def _write_flat_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (128, 128, 128))
    image.save(path)


def _write_rich_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (32, 28, 24))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 120, 232, 220), fill=(156, 112, 72), outline=(240, 220, 190), width=6)
    draw.ellipse((96, 48, 160, 112), fill=(208, 168, 96), outline=(255, 255, 255), width=4)
    draw.line((32, 220, 224, 64), fill=(220, 220, 220), width=5)
    draw.line((64, 32, 196, 196), fill=(90, 140, 220), width=4)
    image.save(path)


def test_analyze_render_image_accepts_rich_image(tmp_path):
    path = tmp_path / "rich.png"
    _write_rich_image(path)

    result = analyze_render_image(str(path))

    assert result["valid"] is True
    assert result["score"] >= 55.0
    assert result["metrics"]["edge_density"] > 0


def test_analyze_render_image_rejects_flat_image(tmp_path):
    path = tmp_path / "flat.png"
    _write_flat_image(path)

    result = analyze_render_image(str(path))

    assert result["valid"] is False
    assert result["score"] < 55.0
    assert result["issues"]


def test_validate_render_screens_aggregates_scores(tmp_path):
    rich_path = tmp_path / "rich.png"
    flat_path = tmp_path / "flat.png"
    _write_rich_image(rich_path)
    _write_flat_image(flat_path)

    result = validate_render_screens([str(rich_path), str(flat_path)], min_score=40.0)

    assert result["valid"] is False
    assert result["score"] > 0
    assert len(result["images"]) == 2
    assert result["issues"]
