"""Tests for visual quality validation helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from veilbreakers_mcp.shared.visual_validation import (
    aaa_verify_map,
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


def _write_checkerboard(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], cell: int, colors: tuple[tuple[int, int, int], tuple[int, int, int]]) -> None:
    left, top, right, bottom = box
    toggle = False
    for y in range(top, bottom, cell):
        row_toggle = toggle
        for x in range(left, right, cell):
            fill = colors[0] if row_toggle else colors[1]
            draw.rectangle(
                (x, y, min(x + cell - 1, right - 1), min(y + cell - 1, bottom - 1)),
                fill=fill,
            )
            row_toggle = not row_toggle
        toggle = not toggle


def _terrain_readability_pass_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (28, 42, 68))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 154, 255, 255), fill=(66, 84, 60))
    draw.polygon(
        [(0, 154), (24, 136), (48, 142), (76, 124), (110, 132), (152, 116), (202, 128), (255, 144), (255, 154)],
        fill=(48, 60, 52),
    )
    draw.line((0, 152, 255, 152), fill=(186, 180, 162), width=2)
    draw.line((12, 122, 52, 108, 92, 116, 136, 96, 184, 112, 232, 104), fill=(236, 228, 212), width=4)
    draw.line((24, 138, 64, 126, 104, 134, 148, 118, 198, 128, 246, 120), fill=(108, 122, 98), width=3)
    for x in range(12, 244, 28):
        draw.line((x, 164, x + 8, 218), fill=(95, 112, 82), width=2)
    _write_checkerboard(draw, (0, 164, 256, 256), 16, ((78, 96, 74), (64, 78, 58)))
    image.save(path)


def _terrain_readability_fail_image(path: Path) -> None:
    rng = np.random.default_rng(42)
    image = Image.new("RGB", (256, 256), (194, 188, 178))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 140), fill=(188, 184, 180))
    draw.rectangle((0, 154, 255, 255), fill=(222, 200, 166))
    _write_checkerboard(draw, (0, 164, 256, 256), 8, ((238, 210, 168), (164, 122, 92)))
    for x in range(0, 256, 12):
        for y in range(164, 256, 12):
            color = tuple(int(v) for v in rng.integers(150, 240, size=3))
            draw.rectangle((x, y, x + 8, y + 8), fill=color)
    for x in range(8, 248, 20):
        draw.line((x, 166, x + 8, 250), fill=(248, 232, 210), width=1)
    image.save(path)


def _terrain_cliff_pass_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (44, 58, 78))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 148, 255, 255), fill=(66, 72, 64))
    cliff = [(72, 76), (126, 48), (162, 56), (198, 116), (184, 220), (96, 232), (60, 172)]
    draw.polygon(cliff, fill=(126, 118, 108), outline=(220, 208, 192))
    draw.line((54, 78, 120, 44, 172, 54, 214, 112), fill=(240, 232, 216), width=4)
    draw.line((62, 84, 124, 60, 166, 68, 202, 120), fill=(82, 74, 68), width=3)
    for x in range(88, 184, 14):
        draw.line((x, 58, x + 14, 220), fill=(92, 84, 76), width=2)
    draw.line((68, 112, 196, 112), fill=(214, 202, 184), width=3)
    draw.line((78, 156, 188, 156), fill=(98, 92, 86), width=2)
    image.save(path)


def _terrain_cliff_fail_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (48, 68, 92))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 150, 255, 255), fill=(88, 102, 76))
    draw.ellipse((28, 116, 108, 172), fill=(92, 112, 84), outline=(126, 146, 108), width=2)
    draw.ellipse((154, 112, 228, 170), fill=(104, 120, 88), outline=(140, 154, 120), width=2)
    draw.line((0, 164, 255, 164), fill=(180, 176, 156), width=2)
    draw.line((0, 188, 255, 188), fill=(160, 150, 130), width=2)
    image.save(path)


def _terrain_waterfall_pass_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (28, 34, 52))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(34, 44, 62))
    draw.polygon([(44, 36), (94, 24), (150, 40), (184, 84), (172, 220), (72, 228), (36, 176)], fill=(74, 70, 66))
    draw.line((40, 52, 90, 44, 126, 58, 166, 48, 208, 78), fill=(112, 104, 96), width=3)
    draw.line((28, 100, 82, 96, 120, 110, 168, 98, 220, 126), fill=(96, 92, 88), width=2)
    draw.rectangle((110, 20, 146, 224), fill=(224, 240, 248))
    for y in range(24, 220, 14):
        shade = 255 - ((y // 14) % 4) * 20
        draw.rectangle((114, y, 142, min(y + 8, 224)), fill=(shade, min(255, shade + 8), min(255, shade + 16)))
    draw.line((124, 24, 132, 214), fill=(255, 255, 255), width=2)
    draw.line((116, 38, 140, 90, 120, 142, 142, 196), fill=(186, 214, 236), width=3)
    draw.ellipse((102, 196, 154, 244), fill=(214, 232, 240), outline=(255, 255, 255), width=3)
    draw.line((96, 200, 160, 220), fill=(188, 214, 230), width=4)
    draw.line((88, 208, 168, 238), fill=(106, 126, 146), width=3)
    for x in range(48, 208, 24):
        draw.line((x, 154, x + 10, 170, x + 4, 188, x + 12, 206), fill=(180, 202, 220), width=2)
    image.save(path)


def _terrain_waterfall_fail_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (36, 44, 58))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 160, 255, 255), fill=(84, 96, 74))
    draw.rectangle((18, 196, 238, 222), fill=(106, 142, 110))
    draw.line((0, 190, 255, 190), fill=(180, 176, 148), width=2)
    draw.line((0, 214, 255, 214), fill=(146, 152, 128), width=2)
    draw.ellipse((52, 58, 202, 148), fill=(96, 118, 146), outline=(206, 214, 230), width=3)
    image.save(path)


def _terrain_cave_pass_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (90, 84, 74))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(104, 96, 84))
    draw.ellipse((34, 28, 222, 226), fill=(88, 80, 70), outline=(194, 186, 170), width=8)
    draw.ellipse((72, 62, 184, 194), fill=(18, 16, 18))
    draw.arc((42, 34, 214, 222), start=196, end=344, fill=(226, 216, 198), width=5)
    draw.line((46, 186, 82, 156), fill=(210, 202, 188), width=4)
    draw.line((174, 156, 210, 186), fill=(210, 202, 188), width=4)
    image.save(path)


def _terrain_cave_fail_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (180, 172, 156))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(186, 180, 166))
    draw.rectangle((24, 88, 232, 220), fill=(208, 194, 172), outline=(236, 228, 214), width=4)
    draw.ellipse((86, 72, 170, 156), fill=(226, 218, 202), outline=(244, 240, 232), width=3)
    draw.line((0, 176, 255, 176), fill=(164, 154, 136), width=2)
    image.save(path)


def _terrain_river_pass_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (70, 84, 64))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(76, 90, 70))
    draw.polygon([(0, 182), (54, 150), (98, 144), (158, 156), (210, 138), (255, 124), (255, 255), (0, 255)], fill=(96, 112, 84))
    draw.line((26, 150, 76, 164, 120, 154, 176, 168, 234, 148), fill=(126, 142, 110), width=10)
    draw.line((30, 158, 82, 174, 126, 164, 178, 178, 238, 158), fill=(54, 94, 128), width=22)
    draw.line((30, 158, 82, 174, 126, 164, 178, 178, 238, 158), fill=(180, 216, 228), width=4)
    draw.line((34, 144, 74, 156), fill=(182, 176, 148), width=3)
    draw.line((190, 182, 228, 168), fill=(182, 176, 148), width=3)
    for x in range(24, 236, 18):
        draw.line((x, 136, x + 10, 148, x + 2, 164), fill=(158, 150, 124), width=2)
    for x in range(40, 224, 24):
        draw.line((x, 172, x + 6, 188, x - 4, 204), fill=(202, 226, 236), width=2)
    _write_checkerboard(draw, (0, 198, 256, 256), 14, ((88, 104, 78), (104, 120, 92)))
    image.save(path)


def _terrain_river_fail_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (118, 124, 108))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(120, 126, 112))
    draw.rectangle((18, 176, 238, 220), fill=(132, 144, 118))
    draw.line((0, 188, 255, 188), fill=(164, 168, 148), width=2)
    draw.line((0, 212, 255, 212), fill=(148, 154, 132), width=2)
    image.save(path)


def _terrain_road_pass_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (70, 82, 110))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(90, 104, 86))
    draw.rectangle((0, 0, 255, 80), fill=(86, 102, 126))
    draw.polygon([(0, 170), (60, 150), (118, 156), (166, 142), (214, 152), (255, 164), (255, 255), (0, 255)], fill=(116, 132, 102))
    draw.polygon([(42, 246), (78, 178), (114, 144), (152, 142), (198, 176), (224, 246)], fill=(112, 94, 68), outline=(236, 218, 182))
    draw.line((66, 236, 108, 158, 148, 156, 194, 214), fill=(54, 42, 30), width=8)
    draw.line((98, 196, 146, 178), fill=(240, 216, 164), width=4)
    draw.line((84, 210, 124, 186, 166, 202), fill=(244, 228, 196), width=2)
    for y in range(168, 238, 12):
        draw.line((76, y, 114, y - 18, 152, y - 16, 190, y + 10), fill=(172, 148, 112), width=2)
    for y in range(176, 240, 10):
        draw.line((92, y, 112, y - 10, 138, y - 8, 164, y + 4), fill=(72, 60, 46), width=1)
    _write_checkerboard(draw, (18, 204, 238, 256), 10, ((112, 126, 102), (68, 78, 64)))
    image.save(path)


def _terrain_road_fail_image(path: Path) -> None:
    image = Image.new("RGB", (256, 256), (110, 116, 102))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(112, 118, 104))
    draw.rectangle((28, 182, 228, 226), fill=(118, 126, 108))
    draw.line((0, 196, 255, 196), fill=(160, 164, 142), width=2)
    image.save(path)


def _write_profile_image(path: Path, profile: str, *, passing: bool) -> None:
    if profile == "terrain_readability":
        (_terrain_readability_pass_image if passing else _terrain_readability_fail_image)(path)
        return
    if profile == "terrain_cliff":
        (_terrain_cliff_pass_image if passing else _terrain_cliff_fail_image)(path)
        return
    if profile == "terrain_waterfall":
        (_terrain_waterfall_pass_image if passing else _terrain_waterfall_fail_image)(path)
        return
    if profile == "terrain_cave":
        (_terrain_cave_pass_image if passing else _terrain_cave_fail_image)(path)
        return
    if profile == "terrain_river":
        (_terrain_river_pass_image if passing else _terrain_river_fail_image)(path)
        return
    if profile == "terrain_road":
        (_terrain_road_pass_image if passing else _terrain_road_fail_image)(path)
        return
    raise ValueError(f"Unknown profile: {profile}")


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


@pytest.mark.parametrize(
    ("profile", "passing"),
    [
        ("terrain_readability", True),
        ("terrain_readability", False),
        ("terrain_cliff", True),
        ("terrain_cliff", False),
        ("terrain_waterfall", True),
        ("terrain_waterfall", False),
        ("terrain_cave", True),
        ("terrain_cave", False),
        ("terrain_river", True),
        ("terrain_river", False),
        ("terrain_road", True),
        ("terrain_road", False),
    ],
)
def test_aaa_verify_map_terrain_profiles_surface_semantics(tmp_path, profile, passing):
    path = tmp_path / f"{profile}_{'pass' if passing else 'fail'}.png"
    _write_profile_image(path, profile, passing=passing)

    result = aaa_verify_map([str(path)], min_score=0, validation_profile=profile)

    assert result["validation_profile"] == profile
    assert len(result["per_angle"]) == 1
    assert result["per_angle"][0]["validation_profile"] == profile
    assert "semantic_metrics" in result["per_angle"][0]
    assert "semantic_issues" in result["per_angle"][0]
    assert result["per_angle"][0]["semantic_metrics"]
    if passing:
        assert result["passed"] is True
        assert result["per_angle"][0]["passed"] is True
        assert result["per_angle"][0]["semantic_issues"] == []
    else:
        assert result["passed"] is False
        assert result["per_angle"][0]["passed"] is False
        assert result["per_angle"][0]["semantic_issues"]
