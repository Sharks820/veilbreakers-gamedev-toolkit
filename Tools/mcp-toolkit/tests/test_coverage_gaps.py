"""Coverage gap tests targeting edge cases that could hide real bugs.

Each test targets a specific edge case identified during coverage analysis
that could cause a crash, incorrect result, or security bypass in production.
"""

from __future__ import annotations

import io
import math

import numpy as np
import pytest
from PIL import Image as PILImage


# ===================================================================
# 1. _terrain_noise: 1x1 heightmap and smooth post-processing
# ===================================================================


class TestTerrainNoiseEdgeCases:
    """Edge cases for _terrain_noise heightmap generation."""

    def test_1x1_heightmap_all_terrain_types(self):
        """1x1 heightmap must not crash for any terrain type.

        The 'smooth' post-process uses a 3x3 box blur that guards on
        `rows >= 3 and cols >= 3` -- but normalization could still
        divide by zero if hmax == hmin on a single pixel.
        """
        from blender_addon.handlers._terrain_noise import generate_heightmap, TERRAIN_PRESETS

        for terrain_type in TERRAIN_PRESETS:
            hmap = generate_heightmap(1, 1, seed=42, terrain_type=terrain_type)
            assert hmap.shape == (1, 1)
            assert hmap.min() >= 0.0
            assert hmap.max() <= 1.0

    def test_2x2_heightmap_smooth_skips_blur(self):
        """2x2 heightmap with 'smooth' post-process should not crash.

        The smooth path has `if rows >= 3 and cols >= 3` guard.
        A 2x2 map should skip the blur and still normalize correctly.
        """
        from blender_addon.handlers._terrain_noise import generate_heightmap

        hmap = generate_heightmap(2, 2, seed=0, terrain_type="plains")
        assert hmap.shape == (2, 2)
        assert hmap.min() >= 0.0
        assert hmap.max() <= 1.0

    def test_slope_map_1x1(self):
        """Slope map on a 1x1 heightmap should return a valid 1x1 array."""
        from blender_addon.handlers._terrain_noise import compute_slope_map

        hmap = np.array([[0.5]])
        slope = compute_slope_map(hmap)
        assert slope.shape == (1, 1)
        assert slope.min() >= 0.0
        assert slope.max() <= 90.0

    def test_biome_assignment_1x1(self):
        """Biome assignment on 1x1 arrays should not crash."""
        from blender_addon.handlers._terrain_noise import compute_biome_assignments

        hmap = np.array([[0.5]])
        slope = np.array([[10.0]])
        biomes = compute_biome_assignments(hmap, slope)
        assert biomes.shape == (1, 1)

    def test_river_on_tiny_map(self):
        """River carving on a 3x3 map should not crash."""
        from blender_addon.handlers._terrain_noise import carve_river_path

        hmap = np.full((3, 3), 0.5)
        path, result = carve_river_path(hmap, source=(0, 1), dest=(2, 1))
        assert len(path) >= 1
        assert result.shape == (3, 3)


# ===================================================================
# 2. _terrain_erosion: single-pixel and tiny maps
# ===================================================================


class TestTerrainErosionEdgeCases:
    """Edge cases for terrain erosion on very small heightmaps."""

    def test_hydraulic_erosion_2x2(self):
        """2x2 heightmap: droplets spawn at x in [0.5, 0.5], immediately
        out-of-bounds check (ix < 1 or ix >= cols-2) triggers. Should
        not crash, just return unchanged.
        """
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        hmap = np.array([[0.3, 0.7], [0.5, 0.9]])
        result = apply_hydraulic_erosion(hmap, iterations=10, seed=42)
        assert result.shape == (2, 2)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_thermal_erosion_2x2(self):
        """2x2 heightmap: vectorized erosion processes all cells via padding.
        Result should have same shape with values in [0, 1] and reduced contrast
        (slopes are smoothed towards the talus threshold).
        """
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.array([[0.0, 1.0], [1.0, 0.0]])
        result = apply_thermal_erosion(hmap, iterations=5, talus_angle=30.0)
        assert result.shape == (2, 2)
        assert result.min() >= 0.0
        assert result.max() <= 1.0
        # Erosion should reduce the extreme slopes (contrast decreases)
        original_range = hmap.max() - hmap.min()
        result_range = result.max() - result.min()
        assert result_range <= original_range

    def test_thermal_erosion_zero_iterations(self):
        """Zero iterations should return input unchanged."""
        from blender_addon.handlers._terrain_erosion import apply_thermal_erosion

        hmap = np.random.RandomState(42).rand(16, 16)
        result = apply_thermal_erosion(hmap, iterations=0, talus_angle=30.0)
        np.testing.assert_array_almost_equal(result, np.clip(hmap, 0, 1))


# ===================================================================
# 3. _dungeon_gen: minimum-size dungeon
# ===================================================================


class TestDungeonGenEdgeCases:
    """Edge cases for dungeon, cave, and town generation."""

    def test_small_dungeon_does_not_crash(self):
        """A 20x20 dungeon with min_room_size=3 should still work.

        With small sizes, BSP may not split, falling back to _force_rooms.
        """
        from blender_addon.handlers._dungeon_gen import (
            generate_bsp_dungeon,
            _verify_connectivity,
        )

        layout = generate_bsp_dungeon(
            width=20, height=20, min_room_size=3, max_depth=2, seed=42
        )
        assert len(layout.rooms) >= 2
        assert layout.grid is not None
        assert _verify_connectivity(layout)

    def test_cave_map_small(self):
        """10x10 cave map should not crash. The degenerate fallback
        opens the center when no floor regions exist.
        """
        from blender_addon.handlers._dungeon_gen import generate_cave_map

        cave = generate_cave_map(width=10, height=10, seed=42)
        assert cave.grid.shape == (10, 10)
        # Should have at least some floor cells
        assert np.sum(cave.grid == 1) > 0

    def test_room_intersects_self(self):
        """A Room must intersect with itself."""
        from blender_addon.handlers._dungeon_gen import Room

        r = Room(5, 5, 10, 10)
        assert r.intersects(r)

    def test_room_adjacent_no_overlap(self):
        """Two adjacent rooms (sharing an edge) should NOT intersect
        because intersects uses strict < comparison.
        """
        from blender_addon.handlers._dungeon_gen import Room

        r1 = Room(0, 0, 5, 5)  # x2=5, y2=5
        r2 = Room(5, 0, 5, 5)  # starts at x=5
        assert not r1.intersects(r2)

    def test_town_layout_small(self):
        """Small town (30x30) with 2 districts should not crash."""
        from blender_addon.handlers._dungeon_gen import generate_town_layout

        town = generate_town_layout(width=30, height=30, num_districts=2, seed=42)
        assert len(town.districts) == 2
        assert len(town.roads) > 0


# ===================================================================
# 4. _building_grammar: 0-floor building and extreme damage
# ===================================================================


class TestBuildingGrammarEdgeCases:
    """Edge cases for building grammar evaluation."""

    def test_zero_floor_building(self):
        """A 0-floor building should produce a spec with foundation and
        roof but no wall/window operations. The roof_z calculation must
        not produce negative or nonsensical values.
        """
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            BuildingSpec,
        )

        result = evaluate_building_grammar(
            width=10, depth=8, floors=0, style="medieval", seed=0
        )
        assert isinstance(result, BuildingSpec)
        assert result.floors == 0
        # Should have at least foundation and roof
        roles = [op.get("role") for op in result.operations]
        assert "foundation" in roles
        assert "roof" in roles
        # Should NOT have any walls (no floors = no walls)
        wall_ops = [op for op in result.operations if op.get("role") == "wall"]
        assert len(wall_ops) == 0

    def test_damage_level_above_one(self):
        """damage_level > 1.0 should not crash. The remove_chance can
        exceed 1.0, which just means everything gets removed.
        """
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(
            width=10, depth=8, floors=2, style="medieval", seed=0
        )
        result = apply_ruins_damage(spec, damage_level=2.0, seed=0)
        # Should not crash; most/all operations removed
        non_debris = [op for op in result.operations
                      if op.get("role") not in ("debris", "vegetation")]
        assert len(non_debris) < len(spec.operations)

    def test_unknown_room_type_interior(self):
        """Unknown room_type for interior layout should return empty list."""
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(
            room_type="nonexistent_room", width=8, depth=6, seed=0
        )
        assert result == []

    def test_tiny_room_interior(self):
        """Very small room (2x2) should not crash even if furniture
        cannot fit. Items that can't be placed are silently skipped.
        """
        from blender_addon.handlers._building_grammar import generate_interior_layout

        result = generate_interior_layout(
            room_type="tavern", width=2, depth=2, seed=0
        )
        # May be empty or have very few items -- just shouldn't crash
        assert isinstance(result, list)


# ===================================================================
# 5. _scatter_engine: zero-area and extreme parameters
# ===================================================================


class TestScatterEngineEdgeCases:
    """Edge cases for scatter engine."""

    def test_poisson_min_distance_larger_than_area(self):
        """min_distance > area diagonal: should return exactly 1 point
        (the initial seed point).
        """
        from blender_addon.handlers._scatter_engine import poisson_disk_sample

        points = poisson_disk_sample(5.0, 5.0, min_distance=100.0, seed=42)
        assert len(points) == 1
        assert 0 <= points[0][0] < 5.0
        assert 0 <= points[0][1] < 5.0

    def test_context_scatter_no_buildings(self):
        """Context scatter with empty building list should use all
        generic props (no crash from nearest-building search).
        """
        from blender_addon.handlers._scatter_engine import context_scatter

        result = context_scatter(buildings=[], area_size=50.0, seed=42)
        assert isinstance(result, list)
        # Should still produce some placements
        assert len(result) > 0

    def test_breakable_variants_deterministic_fragments(self):
        """Fragment counts should be within the configured range."""
        from blender_addon.handlers._scatter_engine import (
            generate_breakable_variants,
            BREAKABLE_PROPS,
        )

        for prop_type, config in BREAKABLE_PROPS.items():
            result = generate_breakable_variants(prop_type, seed=42)
            fmin, fmax = config["fragment_count"]
            actual = len(result["destroyed_spec"]["fragment_ops"])
            assert fmin <= actual <= fmax, (
                f"{prop_type}: fragment count {actual} not in [{fmin}, {fmax}]"
            )


# ===================================================================
# 6. security.py: bypass attack vectors
# ===================================================================


class TestSecurityBypassAttempts:
    """Test security bypass vectors that existing tests miss."""

    def test_walrus_operator_import(self):
        """Walrus operator in comprehension to sneak an import."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "[x := __import__('os') for x in [1]]"
        safe, violations = validate_code(code)
        assert safe is False
        assert any("__import__" in v for v in violations)

    def test_fstring_code_execution(self):
        """f-string with format spec can access dunders.

        The validator blocks str.format() but f-strings compile to
        different AST nodes. However, f'{x.__class__}' produces an
        ast.Attribute with attr='__class__' which IS caught.
        """
        from veilbreakers_mcp.shared.security import validate_code

        code = "result = f'{x.__class__.__mro__}'"
        safe, violations = validate_code(code)
        assert safe is False
        assert any("__class__" in v or "__mro__" in v for v in violations)

    def test_lambda_exec_bypass(self):
        """lambda wrapping exec should be caught as bare exec call."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "f = lambda: exec('import os')"
        safe, violations = validate_code(code)
        assert safe is False
        assert any("exec" in v for v in violations)

    def test_type_metaclass_trick(self):
        """type() with 3 args creates a class dynamically. 'type' is not
        blocked but __bases__ access is. Make sure chaining is caught.
        """
        from veilbreakers_mcp.shared.security import validate_code

        code = "cls = type('X', (object,), {}); cls.__bases__"
        safe, violations = validate_code(code)
        assert safe is False
        assert any("__bases__" in v for v in violations)

    def test_nested_getattr_in_comprehension(self):
        """getattr() is allowed per user security policy — not in BLOCKED_FUNCTIONS."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "[getattr(x, a) for x in objs for a in attrs]"
        safe, violations = validate_code(code)
        assert safe is True

    def test_dunder_import_as_attribute(self):
        """Accessing __import__ as attribute (not call) should be blocked."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "fn = x.__import__"
        safe, violations = validate_code(code)
        assert safe is False

    def test_setattr_allowed(self):
        """setattr is allowed per user security policy — needed for Blender scripting."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "setattr(obj, '__class__', Evil)"
        safe, violations = validate_code(code)
        assert safe is True

    def test_delattr_allowed(self):
        """delattr is allowed per user security policy — needed for Blender scripting."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "delattr(obj, 'safe_attr')"
        safe, violations = validate_code(code)
        assert safe is True

    def test_compile_then_exec(self):
        """compile() followed by exec() -- both should be caught."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "code = compile('import os', '<string>', 'exec')\nexec(code)"
        safe, violations = validate_code(code)
        assert safe is False
        # Should catch both compile and exec
        has_compile = any("compile" in v for v in violations)
        has_exec = any("exec" in v for v in violations)
        assert has_compile and has_exec

    def test_bpy_driver_namespace_access(self):
        """Accessing bpy.app.driver_namespace should be blocked."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "bpy.app.driver_namespace['evil'] = lambda: None"
        safe, violations = validate_code(code)
        assert safe is False
        assert any("driver_namespace" in v for v in violations)

    def test_bpy_addon_install(self):
        """bpy.ops.preferences.addon_install should be blocked."""
        from veilbreakers_mcp.shared.security import validate_code

        code = "bpy.ops.preferences.addon_install(filepath='/tmp/evil.zip')"
        safe, violations = validate_code(code)
        assert safe is False
        assert any("addon_install" in v for v in violations)


# ===================================================================
# 7. wcag_checker.py: same-color edge cases
# ===================================================================


class TestWcagEdgeCases:
    """Edge cases for WCAG contrast checker."""

    def test_pure_black_on_black(self):
        """Black on black should have ratio = 1.0 and fail WCAG."""
        from veilbreakers_mcp.shared.wcag_checker import contrast_ratio, check_wcag_aa

        ratio = contrast_ratio((0, 0, 0), (0, 0, 0))
        assert ratio == pytest.approx(1.0, abs=0.01)
        assert check_wcag_aa((0, 0, 0), (0, 0, 0)) is False

    def test_pure_white_on_white(self):
        """White on white should have ratio = 1.0 and fail WCAG."""
        from veilbreakers_mcp.shared.wcag_checker import contrast_ratio, check_wcag_aa

        ratio = contrast_ratio((255, 255, 255), (255, 255, 255))
        assert ratio == pytest.approx(1.0, abs=0.01)
        assert check_wcag_aa((255, 255, 255), (255, 255, 255)) is False

    def test_contrast_ratio_symmetry(self):
        """contrast_ratio(a, b) == contrast_ratio(b, a) for any colors."""
        from veilbreakers_mcp.shared.wcag_checker import contrast_ratio

        pairs = [
            ((255, 0, 0), (0, 255, 0)),
            ((128, 64, 32), (10, 200, 100)),
            ((0, 0, 0), (128, 128, 128)),
        ]
        for a, b in pairs:
            r1 = contrast_ratio(a, b)
            r2 = contrast_ratio(b, a)
            assert r1 == pytest.approx(r2, abs=1e-10), (
                f"Asymmetry: contrast_ratio{a, b}={r1} != contrast_ratio{b, a}={r2}"
            )

    def test_parse_color_empty_string(self):
        """Empty string should return None, not crash."""
        from veilbreakers_mcp.shared.wcag_checker import parse_color

        assert parse_color("") is None

    def test_parse_color_hex4_digit(self):
        """4-digit hex (#RGBA shorthand) should return None (not supported)."""
        from veilbreakers_mcp.shared.wcag_checker import parse_color

        result = parse_color("#f00f")
        # 4-digit is not a standard supported format
        assert result is None


# ===================================================================
# 8. texture_ops.py: 1x1 and empty polygon edge cases
# ===================================================================


def _to_png_bytes(img: PILImage.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _img_from_bytes(data: bytes) -> PILImage.Image:
    return PILImage.open(io.BytesIO(data))


class TestTextureOpsEdgeCases:
    """Edge cases for texture operations."""

    def test_uv_mask_no_polygons(self):
        """Empty polygon list should produce an all-black mask."""
        from veilbreakers_mcp.shared.texture_ops import generate_uv_mask_image

        mask = generate_uv_mask_image([], texture_size=64, feather_radius=5)
        arr = np.array(mask)
        assert np.all(arr == 0), "Empty polygon list should produce all-zero mask"

    def test_uv_mask_1x1_texture(self):
        """1x1 texture mask should not crash."""
        from veilbreakers_mcp.shared.texture_ops import generate_uv_mask_image

        # Polygon covering the full UV space
        polygons = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]
        mask = generate_uv_mask_image(polygons, texture_size=1, feather_radius=0)
        assert mask.size == (1, 1)

    def test_make_tileable_2x2_image(self):
        """make_tileable on a 2x2 image: overlap=0.15 gives overlap_w=max(2,0)=2,
        which covers the entire image. Should not crash or produce NaN.
        """
        from veilbreakers_mcp.shared.texture_ops import make_tileable

        img = PILImage.new("RGB", (2, 2), (128, 64, 32))
        img.putpixel((0, 0), (255, 0, 0))
        img.putpixel((1, 1), (0, 0, 255))
        img_bytes = _to_png_bytes(img)

        result_bytes = make_tileable(img_bytes, overlap_pct=0.15)
        result = _img_from_bytes(result_bytes)
        assert result.size == (2, 2)
        # No NaN or out-of-range values
        arr = np.array(result)
        assert arr.min() >= 0
        assert arr.max() <= 255

    def test_make_tileable_4x4_image(self):
        """4x4 image with overlap: overlap_w=max(2, int(4*0.15))=max(2,0)=2.
        Indices will overlap since width(4) - overlap_w(2) = 2, meaning
        left_idx=[0,1] and right_idx=[2,3] and left_mirror=[3,2].
        """
        from veilbreakers_mcp.shared.texture_ops import make_tileable

        np.random.seed(42)
        arr = np.random.randint(0, 256, (4, 4, 3), dtype=np.uint8)
        img = PILImage.fromarray(arr, "RGB")
        img_bytes = _to_png_bytes(img)

        result_bytes = make_tileable(img_bytes, overlap_pct=0.5)
        result = _img_from_bytes(result_bytes)
        result_arr = np.array(result)

        # Edges should match for tiling
        left = result_arr[:, 0, :].astype(int)
        right = result_arr[:, -1, :].astype(int)
        diff = np.abs(left - right)
        assert diff.max() <= 20, f"Edge diff too large: max={diff.max()}"

    def test_render_wear_map_empty_curvature(self):
        """Empty curvature data should produce mid-gray image."""
        from veilbreakers_mcp.shared.texture_ops import render_wear_map

        result_bytes = render_wear_map({}, texture_size=32)
        result = _img_from_bytes(result_bytes)
        assert result.size == (32, 32)
        # Should be uniform mid-gray (128)
        center = result.getpixel((16, 16))
        assert center == 128

    def test_render_wear_map_single_vertex(self):
        """Single-vertex curvature: all one brightness level."""
        from veilbreakers_mcp.shared.texture_ops import render_wear_map

        # Single vertex at curvature 0.5, no UV data
        result_bytes = render_wear_map({0: 0.5}, texture_size=32, uv_data=None)
        result = _img_from_bytes(result_bytes)
        assert result.size == (32, 32)

    def test_hsv_adjust_zero_mask(self):
        """All-zero mask should return image bit-identical to input."""
        from veilbreakers_mcp.shared.texture_ops import apply_hsv_adjustment

        img = PILImage.new("RGB", (16, 16), (100, 150, 200))
        img_bytes = _to_png_bytes(img)
        mask = PILImage.new("L", (16, 16), 0)
        mask_bytes = _to_png_bytes(mask)

        result_bytes = apply_hsv_adjustment(
            img_bytes, mask_bytes, hue_shift=0.5, saturation_scale=2.0
        )
        result = _img_from_bytes(result_bytes)
        original = _img_from_bytes(img_bytes)

        # Every pixel should be identical
        for y in range(16):
            for x in range(16):
                assert result.getpixel((x, y)) == original.getpixel((x, y)), (
                    f"Pixel ({x},{y}) changed with zero mask"
                )

    def test_inpaint_no_image(self):
        """Inpainting with empty image bytes should return error."""
        from veilbreakers_mcp.shared.texture_ops import inpaint_texture

        result = inpaint_texture(b"", b"mask", "prompt", fal_key="key")
        assert result["status"] == "error"

    def test_inpaint_no_mask(self):
        """Inpainting with empty mask bytes should return error."""
        from veilbreakers_mcp.shared.texture_ops import inpaint_texture

        result = inpaint_texture(b"img", b"", "prompt", fal_key="key")
        assert result["status"] == "error"

    def test_inpaint_empty_prompt(self):
        """Inpainting with empty prompt should return error."""
        from veilbreakers_mcp.shared.texture_ops import inpaint_texture

        result = inpaint_texture(b"img", b"mask", "", fal_key="key")
        assert result["status"] == "error"
