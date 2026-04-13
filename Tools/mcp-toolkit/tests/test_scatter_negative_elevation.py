"""Addendum 3.A regression canary — scatter must place in negative elevations.

Every refactor touching scatter has historically regressed to
``heights / heights.max()`` or ``altitude / height_scale`` clamped to [0, 1],
collapsing negative-elevation lowlands to zero. This canary generates a
terrain that spans min=-40m, max=20m and asserts:

1. WorldHeightTransform round-trips signed elevations
2. Scatter placements EXIST in cells whose z < 0
3. place_assets_by_zone (Bundle E) honors min_altitude_m below zero
4. audit_scatter_altitude_conversion finds known bad patterns in synthetic source
"""

from __future__ import annotations

import math

import numpy as np

from blender_addon.handlers.terrain_assets import (
    AssetContextRule,
    AssetRole,
    place_assets_by_zone,
)
from blender_addon.handlers.terrain_scatter_altitude_safety import (
    WORLD_HEIGHT_TRANSFORM_WARNING,
    audit_scatter_altitude_conversion,
)
from blender_addon.handlers.terrain_semantics import (
    BBox,
    TerrainIntentState,
    TerrainMaskStack,
    WorldHeightTransform,
)


def _make_negative_terrain(tile_size: int = 32) -> TerrainMaskStack:
    """Build a synthetic terrain with min=-40m, max=20m.

    Heightfield is a tilted plane from -40 (north) to +20 (south) so a
    clear negative-elevation band exists.
    """
    n = tile_size + 1
    # Linear ramp from -40 to +20 along the y axis
    z = np.linspace(-40.0, 20.0, n)
    height = np.tile(z[:, None], (1, n)).astype(np.float64)
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    # Flat slope (0 rad) — below every rule's max_slope
    stack.set("slope", np.zeros_like(height, dtype=np.float32), "test_fixture")
    # Moderate wetness so ground-cover rules pass
    stack.set("wetness", np.full_like(height, 0.5, dtype=np.float32), "test_fixture")
    return stack


def test_world_height_transform_preserves_sign_on_negative_terrain():
    stack = _make_negative_terrain()
    wht = WorldHeightTransform(
        world_min=float(stack.height.min()),
        world_max=float(stack.height.max()),
    )
    normalized = wht.to_normalized(stack.height)
    restored = wht.from_normalized(normalized)
    np.testing.assert_allclose(restored, stack.height, atol=1e-9)
    # The most negative cell must round-trip to exactly its original value
    assert float(restored.min()) < 0.0
    assert math.isclose(float(restored.min()), -40.0, abs_tol=1e-6)


def test_scatter_placements_exist_in_negative_elevation_cells():
    stack = _make_negative_terrain()
    intent = TerrainIntentState(
        seed=2026,
        region_bounds=BBox(0.0, 0.0, 100.0, 100.0),
        tile_size=stack.tile_size,
        cell_size=stack.cell_size,
    )
    # Rule allows cells from -100m to +100m altitude — full range
    rule = AssetContextRule(
        asset_id="grass_clump",
        role=AssetRole.GROUND_COVER,
        min_slope_rad=0.0,
        max_slope_rad=math.pi * 0.5,
        min_altitude_m=-100.0,
        max_altitude_m=100.0,
        wetness_min=0.0,
        wetness_max=1.0,
        cluster_radius_m=1.5,
    )
    results = place_assets_by_zone(stack, intent, [rule])
    placements = results["grass_clump"]
    assert len(placements) > 0, "no scatter placements in negative-elevation terrain"

    # At least one placement must be in a cell whose z < 0 (proves the bug fix)
    negative_placements = [p for p in placements if p[2] < 0.0]
    assert negative_placements, (
        f"scatter collapsed: no placements with z<0, but terrain spans "
        f"[{stack.height.min()}, {stack.height.max()}]"
    )


def test_scatter_respects_negative_min_altitude_bound():
    stack = _make_negative_terrain()
    intent = TerrainIntentState(
        seed=2026,
        region_bounds=BBox(0.0, 0.0, 100.0, 100.0),
        tile_size=stack.tile_size,
        cell_size=stack.cell_size,
    )
    # Rule that explicitly requires z >= -20m; half the terrain qualifies
    rule = AssetContextRule(
        asset_id="grass_clump",
        role=AssetRole.GROUND_COVER,
        min_slope_rad=0.0,
        max_slope_rad=math.pi * 0.5,
        min_altitude_m=-20.0,
        max_altitude_m=100.0,
        wetness_min=0.0,
        wetness_max=1.0,
        cluster_radius_m=1.5,
    )
    results = place_assets_by_zone(stack, intent, [rule])
    for (x, y, z) in results["grass_clump"]:
        assert z >= -20.0 - 1e-6, (
            f"placement at z={z} violates min_altitude_m=-20.0 — scatter code "
            "is likely normalizing heights and losing signed elevation"
        )


def test_audit_detects_heights_div_heights_max():
    src = "    normalized = heights / heights.max()  # BAD\n"
    offenders = audit_scatter_altitude_conversion(src)
    assert offenders, "audit failed to detect heights / heights.max() idiom"
    assert "heights_div_heights_max" in offenders[0]


def test_audit_detects_altitude_div_height_scale():
    src = "altitude = center.z / height_scale\n"
    offenders = audit_scatter_altitude_conversion(src)
    assert any("center_z_div_height_scale" in o or "altitude_div_height_scale" in o for o in offenders)


def test_audit_clean_source():
    src = "from terrain_semantics import WorldHeightTransform\nnorm = wht.to_normalized(h)\n"
    assert audit_scatter_altitude_conversion(src) == []


def test_world_height_transform_warning_mentions_safe_replacement():
    assert "WorldHeightTransform" in WORLD_HEIGHT_TRANSFORM_WARNING
