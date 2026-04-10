"""Bundle C tests — _water_network_ext.py."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Lightweight WaterNetwork stand-in for testing extensions
# ---------------------------------------------------------------------------


@dataclass
class _FakeSegment:
    segment_id: int
    waypoints: List[Tuple[float, float, float]]
    bank_asymmetry: float = 0.0


@dataclass
class _FakeNode:
    node_id: int
    world_x: float
    world_y: float
    world_z: float


@dataclass
class _FakeNetwork:
    segments: dict = field(default_factory=dict)
    nodes: dict = field(default_factory=dict)


def _straight_segment(n: int = 20) -> _FakeSegment:
    waypoints = [(float(i), 5.0, 0.0) for i in range(n)]
    return _FakeSegment(segment_id=0, waypoints=waypoints)


def _build_network_with_straight_segment(n: int = 20) -> _FakeNetwork:
    net = _FakeNetwork()
    seg = _straight_segment(n)
    net.segments[seg.segment_id] = seg
    return net


def _polyline_length(points) -> float:
    total = 0.0
    for i in range(1, len(points)):
        x0, y0 = points[i - 1][0], points[i - 1][1]
        x1, y1 = points[i][0], points[i][1]
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def _build_stack(size: int = 40):
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    h = np.zeros((size, size), dtype=np.float64)
    return TerrainMaskStack(
        tile_size=size - 1,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_add_meander_increases_path_length():
    from blender_addon.handlers._water_network_ext import add_meander

    net = _build_network_with_straight_segment(n=20)
    orig_len = _polyline_length(net.segments[0].waypoints)
    add_meander(net, amplitude=2.0)
    new_len = _polyline_length(net.segments[0].waypoints)
    assert new_len > orig_len * 1.05, f"expected meander to lengthen path ({orig_len} → {new_len})"


def test_add_meander_preserves_endpoints():
    from blender_addon.handlers._water_network_ext import add_meander

    net = _build_network_with_straight_segment(n=20)
    first = net.segments[0].waypoints[0]
    last = net.segments[0].waypoints[-1]
    add_meander(net, amplitude=1.5)
    assert net.segments[0].waypoints[0] == first
    assert net.segments[0].waypoints[-1] == last


def test_add_meander_zero_amplitude_noop():
    from blender_addon.handlers._water_network_ext import add_meander

    net = _build_network_with_straight_segment(n=10)
    original = list(net.segments[0].waypoints)
    add_meander(net, amplitude=0.0)
    assert net.segments[0].waypoints == original


def test_apply_bank_asymmetry_tags_segments():
    from blender_addon.handlers._water_network_ext import apply_bank_asymmetry

    net = _build_network_with_straight_segment(n=10)
    apply_bank_asymmetry(net, bias=0.6)
    assert net.segments[0].bank_asymmetry == pytest.approx(0.6)

    apply_bank_asymmetry(net, bias=-0.4)
    assert net.segments[0].bank_asymmetry == pytest.approx(-0.4)


def test_apply_bank_asymmetry_clamps_range():
    from blender_addon.handlers._water_network_ext import apply_bank_asymmetry

    net = _build_network_with_straight_segment(n=10)
    apply_bank_asymmetry(net, bias=5.0)
    assert net.segments[0].bank_asymmetry == pytest.approx(1.0)
    apply_bank_asymmetry(net, bias=-5.0)
    assert net.segments[0].bank_asymmetry == pytest.approx(-1.0)


def test_compute_wet_rock_mask_zero_without_seeds():
    from blender_addon.handlers._water_network_ext import compute_wet_rock_mask

    stack = _build_stack(size=20)
    mask = compute_wet_rock_mask(stack, None, radius_m=3.0)
    assert mask.shape == stack.height.shape
    assert float(mask.max()) == 0.0  # no seeds → no wet rock


def test_compute_wet_rock_mask_decays_with_distance():
    from blender_addon.handlers._water_network_ext import compute_wet_rock_mask

    stack = _build_stack(size=30)
    net = _FakeNetwork()
    net.nodes[0] = _FakeNode(node_id=0, world_x=15.0, world_y=15.0, world_z=0.0)
    mask = compute_wet_rock_mask(stack, net, radius_m=4.0)
    # Near-center should be > far-corner
    assert mask[15, 15] > mask[0, 0]
    # Far corner should be zero
    assert mask[0, 0] == 0.0


def test_compute_foam_mask_peaks_at_pool():
    from blender_addon.handlers._water_network_ext import compute_foam_mask
    from blender_addon.handlers.terrain_waterfalls import (
        ImpactPool,
        LipCandidate,
        WaterfallChain,
    )

    stack = _build_stack(size=30)
    chain = WaterfallChain(
        chain_id="test",
        lip=LipCandidate(
            world_position=(15.0, 10.0, 20.0),
            upstream_drainage=1000.0,
            downstream_drop_m=10.0,
            flow_direction_rad=0.0,
            confidence_score=0.8,
        ),
        plunge_path=((15.0, 10.0, 20.0), (15.0, 15.0, 10.0)),
        pool=ImpactPool(
            world_position=(15.0, 15.0, 10.0),
            radius_m=4.0,
            max_depth_m=2.0,
            outflow_direction_rad=0.0,
        ),
        outflow=((15.0, 15.0, 10.0), (15.0, 20.0, 9.0)),
        mist_radius_m=8.0,
        foam_intensity=0.9,
        total_drop_m=10.0,
        drop_segments=(10.0,),
    )
    foam = compute_foam_mask(chain, stack)
    assert foam.max() > 0.0
    # Pool center should be peak
    peak = foam.max()
    assert foam[15, 15] == pytest.approx(peak, rel=1e-5)
    # Far away should be 0
    assert foam[0, 0] == 0.0


def test_compute_mist_mask_is_radial():
    from blender_addon.handlers._water_network_ext import compute_mist_mask
    from blender_addon.handlers.terrain_waterfalls import (
        ImpactPool,
        LipCandidate,
        WaterfallChain,
    )

    stack = _build_stack(size=30)
    chain = WaterfallChain(
        chain_id="test",
        lip=LipCandidate(
            world_position=(15.0, 10.0, 20.0),
            upstream_drainage=1000.0,
            downstream_drop_m=10.0,
            flow_direction_rad=0.0,
            confidence_score=0.8,
        ),
        plunge_path=((15.0, 10.0, 20.0), (15.0, 15.0, 10.0)),
        pool=ImpactPool(
            world_position=(15.0, 15.0, 10.0),
            radius_m=4.0,
            max_depth_m=2.0,
            outflow_direction_rad=0.0,
        ),
        outflow=((15.0, 15.0, 10.0), (15.0, 20.0, 9.0)),
        mist_radius_m=6.0,
        foam_intensity=0.9,
        total_drop_m=10.0,
        drop_segments=(10.0,),
    )
    mist = compute_mist_mask(chain, stack)
    assert mist.max() > 0.0
    assert mist[15, 15] == pytest.approx(mist.max(), rel=1e-5)
    # Cells on the circle boundary should be ~0
    assert mist[15, 22] < mist[15, 15]


def test_solve_outflow_produces_path():
    from blender_addon.handlers._water_network_ext import solve_outflow
    from blender_addon.handlers.terrain_waterfalls import ImpactPool

    pool = ImpactPool(
        world_position=(10.0, 10.0, 0.0),
        radius_m=3.0,
        max_depth_m=1.0,
        outflow_direction_rad=0.0,  # east
    )
    path = solve_outflow(None, pool)
    assert len(path) >= 2
    # First point should be east of pool center
    assert path[0][0] > 10.0
    # Monotonic x since direction is east
    xs = [p[0] for p in path]
    assert xs == sorted(xs)
