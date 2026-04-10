"""Bundle F — tests for terrain_caves.py.

Pure-numpy cave archetype analysis. Fixtures construct deterministic
heightmaps that bias each archetype's scoring heuristic so tests can
assert per-archetype behavior.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Registry isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_pass_registry():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    yield
    TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _build_state(
    *,
    tile_size: int = 48,
    seed: int = 1234,
    mode: str = "mixed",
    cave_candidates=(),
    protected_zones=(),
):
    from blender_addon.handlers.terrain_masks import compute_base_masks
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    N = tile_size + 1
    if mode == "flat_mid":
        height = np.full((N, N), 50.0, dtype=np.float64)
    elif mode == "steep":
        # Strong slope — biases FISSURE
        cols = np.arange(N).astype(np.float64)
        height = np.tile(cols * 3.0, (N, 1))
    elif mode == "low_coastal":
        # Low altitude + basin center — biases SEA_GROTTO
        height = np.full((N, N), 5.0, dtype=np.float64)
        cy, cx = N // 2, N // 2
        yy, xx = np.mgrid[0:N, 0:N]
        bowl = -((xx - cx) ** 2 + (yy - cy) ** 2) * 0.02
        height += bowl
    elif mode == "high_plateau":
        # High altitude flat — biases GLACIAL_MELT (with damp injected)
        height = np.full((N, N), 180.0, dtype=np.float64)
    else:  # "mixed"
        xs = np.linspace(0.0, 1.0, N)
        ys = np.linspace(0.0, 1.0, N)
        xg, yg = np.meshgrid(xs, ys)
        height = (
            20.0
            + 30.0 * np.sin(xg * 6.0)
            + 15.0 * np.cos(yg * 4.0)
        )

    # Tiny jitter so slope/curvature don't degenerate
    rng = np.random.default_rng(seed)
    height = height + rng.normal(0.0, 0.02, size=height.shape)

    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    compute_base_masks(
        height,
        cell_size=1.0,
        tile_coords=(0, 0),
        stack=stack,
        pass_name="structural_masks",
    )

    region_bounds = BBox(0.0, 0.0, float(N), float(N))

    scene_read = TerrainSceneRead(
        timestamp=time.time(),
        major_landforms=("plateau",),
        focal_point=(N * 0.5, N * 0.5, float(height.mean())),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=tuple(cave_candidates),
        protected_zones_in_region=tuple(z.zone_id for z in protected_zones),
        edit_scope=region_bounds,
        success_criteria=("caves_placed",),
        reviewer="test",
    )

    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
        protected_zones=tuple(protected_zones),
        scene_read=scene_read,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


def _inject_channel(stack, channel: str, value: float) -> None:
    """Overwrite a mask channel with a constant array to bias the archetype pick."""
    arr = np.full_like(stack.height, float(value), dtype=np.float64)
    stack.set(channel, arr, "test_inject")


# ---------------------------------------------------------------------------
# Archetype enum / spec tests
# ---------------------------------------------------------------------------


def test_archetype_enum_has_five_members():
    from blender_addon.handlers.terrain_caves import CaveArchetype

    members = set(CaveArchetype)
    assert len(members) == 5
    assert {a.value for a in members} == {
        "lava_tube",
        "fissure",
        "karst_sinkhole",
        "glacial_melt",
        "sea_grotto",
    }


def test_make_archetype_spec_defaults_per_archetype():
    from blender_addon.handlers.terrain_caves import CaveArchetype, make_archetype_spec

    for archetype in CaveArchetype:
        spec = make_archetype_spec(archetype)
        assert spec.archetype == archetype
        assert spec.entrance_width_m > 0
        assert spec.entrance_height_m > 0
        assert spec.interior_length_m > 0
        assert 0.0 <= spec.damp_intensity <= 1.0


def test_make_archetype_spec_overrides_applied():
    from blender_addon.handlers.terrain_caves import CaveArchetype, make_archetype_spec

    spec = make_archetype_spec(
        CaveArchetype.FISSURE, entrance_width_m=9.9
    )
    assert spec.entrance_width_m == pytest.approx(9.9)


# ---------------------------------------------------------------------------
# pick_cave_archetype tests
# ---------------------------------------------------------------------------


def test_pick_archetype_coastal_picks_sea_grotto():
    from blender_addon.handlers.terrain_caves import CaveArchetype, pick_cave_archetype

    state = _build_state(mode="low_coastal")
    _inject_channel(state.mask_stack, "wetness", 0.95)
    _inject_channel(state.mask_stack, "basin", 0.15)
    _inject_channel(state.mask_stack, "concavity", 0.0)
    state.mask_stack.height_min_m = 0.0
    state.mask_stack.height_max_m = 100.0
    # Low altitude with mild basin + very wet -> SEA_GROTTO
    choice = pick_cave_archetype(state.mask_stack, (24.0, 24.0, 0.0), seed=1)
    assert choice == CaveArchetype.SEA_GROTTO


def test_pick_archetype_high_wet_plateau_picks_glacial_melt():
    from blender_addon.handlers.terrain_caves import CaveArchetype, pick_cave_archetype

    state = _build_state(mode="high_plateau")
    _inject_channel(state.mask_stack, "wetness", 0.85)
    # Force range so altitude_norm is mid/high
    state.mask_stack.height_min_m = 0.0
    state.mask_stack.height_max_m = 250.0
    choice = pick_cave_archetype(state.mask_stack, (24.0, 24.0, 180.0), seed=1)
    assert choice == CaveArchetype.GLACIAL_MELT


def test_pick_archetype_steep_dry_picks_fissure():
    from blender_addon.handlers.terrain_caves import CaveArchetype, pick_cave_archetype

    state = _build_state(mode="steep")
    _inject_channel(state.mask_stack, "wetness", 0.0)
    _inject_channel(state.mask_stack, "slope", math.radians(72.0))
    _inject_channel(state.mask_stack, "basin", 0.0)
    choice = pick_cave_archetype(state.mask_stack, (24.0, 24.0, 0.0), seed=7)
    assert choice == CaveArchetype.FISSURE


def test_pick_archetype_basin_mid_picks_karst():
    from blender_addon.handlers.terrain_caves import CaveArchetype, pick_cave_archetype

    state = _build_state(mode="flat_mid")
    _inject_channel(state.mask_stack, "basin", 1.0)
    _inject_channel(state.mask_stack, "concavity", 0.6)
    _inject_channel(state.mask_stack, "wetness", 0.1)
    _inject_channel(state.mask_stack, "slope", math.radians(5.0))
    state.mask_stack.height_min_m = 0.0
    state.mask_stack.height_max_m = 100.0
    choice = pick_cave_archetype(state.mask_stack, (24.0, 24.0, 50.0), seed=3)
    assert choice == CaveArchetype.KARST_SINKHOLE


def test_pick_archetype_deterministic():
    from blender_addon.handlers.terrain_caves import pick_cave_archetype

    state = _build_state(mode="mixed")
    a = pick_cave_archetype(state.mask_stack, (10.0, 10.0, 0.0), seed=99)
    b = pick_cave_archetype(state.mask_stack, (10.0, 10.0, 0.0), seed=99)
    assert a == b


# ---------------------------------------------------------------------------
# generate_cave_path tests
# ---------------------------------------------------------------------------


def test_generate_cave_path_deterministic_same_seed():
    from blender_addon.handlers.terrain_caves import CaveArchetype, generate_cave_path

    state = _build_state()
    path_a = generate_cave_path(
        state.mask_stack, CaveArchetype.LAVA_TUBE, (20.0, 20.0, 10.0), seed=42
    )
    path_b = generate_cave_path(
        state.mask_stack, CaveArchetype.LAVA_TUBE, (20.0, 20.0, 10.0), seed=42
    )
    assert len(path_a) == len(path_b)
    for (pa, pb) in zip(path_a, path_b):
        assert pa == pytest.approx(pb)


def test_generate_cave_path_differs_per_seed():
    from blender_addon.handlers.terrain_caves import CaveArchetype, generate_cave_path

    state = _build_state()
    path_a = generate_cave_path(
        state.mask_stack, CaveArchetype.LAVA_TUBE, (20.0, 20.0, 10.0), seed=1
    )
    path_b = generate_cave_path(
        state.mask_stack, CaveArchetype.LAVA_TUBE, (20.0, 20.0, 10.0), seed=2
    )
    # Different heading => at least one point differs
    assert path_a != path_b


def test_generate_cave_path_sinkhole_starts_vertical():
    from blender_addon.handlers.terrain_caves import CaveArchetype, generate_cave_path

    state = _build_state()
    path = generate_cave_path(
        state.mask_stack,
        CaveArchetype.KARST_SINKHOLE,
        (24.0, 24.0, 100.0),
        seed=5,
    )
    assert len(path) >= 6
    # First segment: x,y should be ~constant (vertical plunge)
    assert path[0][0] == pytest.approx(24.0, abs=0.1)
    assert path[0][1] == pytest.approx(24.0, abs=0.1)
    # And z strictly decreases
    assert path[1][2] < path[0][2]


def test_generate_cave_path_all_archetypes_nonempty():
    from blender_addon.handlers.terrain_caves import CaveArchetype, generate_cave_path

    state = _build_state()
    for archetype in CaveArchetype:
        path = generate_cave_path(
            state.mask_stack, archetype, (20.0, 20.0, 10.0), seed=11
        )
        assert len(path) >= 6, f"archetype {archetype} returned empty path"


# ---------------------------------------------------------------------------
# carve_cave_volume tests
# ---------------------------------------------------------------------------


def test_carve_cave_volume_populates_cave_candidate():
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        carve_cave_volume,
        generate_cave_path,
        make_archetype_spec,
    )

    state = _build_state()
    spec = make_archetype_spec(CaveArchetype.LAVA_TUBE)
    path = generate_cave_path(
        state.mask_stack, CaveArchetype.LAVA_TUBE, (24.0, 24.0, 20.0), seed=7
    )
    _ = carve_cave_volume(state.mask_stack, path, spec)

    candidate = state.mask_stack.get("cave_candidate")
    assert candidate is not None
    assert candidate.dtype == bool
    assert int(candidate.sum()) > 0


# ---------------------------------------------------------------------------
# build_cave_entrance_frame tests
# ---------------------------------------------------------------------------


def test_build_entrance_frame_has_min_two_rocks():
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        build_cave_entrance_frame,
        make_archetype_spec,
    )

    state = _build_state()
    for archetype in CaveArchetype:
        spec = make_archetype_spec(archetype)
        frame = build_cave_entrance_frame(
            state.mask_stack, (20.0, 20.0, 10.0), spec
        )
        assert len(frame["framing_rocks"]) >= 2
        assert frame["lip_height_m"] > 1.0
        assert "occlusion_shelf" in frame


def test_build_entrance_frame_lintel_for_wide_archetypes():
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        build_cave_entrance_frame,
        make_archetype_spec,
    )

    state = _build_state()
    for archetype in (
        CaveArchetype.LAVA_TUBE,
        CaveArchetype.SEA_GROTTO,
        CaveArchetype.KARST_SINKHOLE,
    ):
        spec = make_archetype_spec(archetype)
        frame = build_cave_entrance_frame(
            state.mask_stack, (20.0, 20.0, 10.0), spec
        )
        roles = {r["role"] for r in frame["framing_rocks"]}
        assert "lintel" in roles, f"{archetype} missing lintel"


# ---------------------------------------------------------------------------
# scatter_collapse_debris tests
# ---------------------------------------------------------------------------


def test_scatter_collapse_debris_deterministic():
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        generate_cave_path,
        make_archetype_spec,
        scatter_collapse_debris,
    )

    state = _build_state()
    spec = make_archetype_spec(CaveArchetype.KARST_SINKHOLE)
    path = generate_cave_path(
        state.mask_stack, CaveArchetype.KARST_SINKHOLE, (20.0, 20.0, 30.0), seed=5
    )
    a = scatter_collapse_debris(state.mask_stack, path, spec, seed=111)
    b = scatter_collapse_debris(state.mask_stack, path, spec, seed=111)
    assert a == b
    assert len(a) > 0


def test_scatter_collapse_debris_density_scales():
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        generate_cave_path,
        make_archetype_spec,
        scatter_collapse_debris,
    )

    state = _build_state()
    path = generate_cave_path(
        state.mask_stack, CaveArchetype.KARST_SINKHOLE, (20.0, 20.0, 30.0), seed=5
    )
    heavy = make_archetype_spec(CaveArchetype.KARST_SINKHOLE)  # density 0.85
    light = make_archetype_spec(CaveArchetype.LAVA_TUBE)       # density 0.15
    a = scatter_collapse_debris(state.mask_stack, path, heavy, seed=1)
    b = scatter_collapse_debris(state.mask_stack, path, light, seed=1)
    assert len(a) > len(b)


# ---------------------------------------------------------------------------
# generate_damp_mask tests
# ---------------------------------------------------------------------------


def test_generate_damp_mask_populates_wet_rock():
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        generate_cave_path,
        generate_damp_mask,
        make_archetype_spec,
    )

    state = _build_state()
    spec = make_archetype_spec(CaveArchetype.SEA_GROTTO)
    path = generate_cave_path(
        state.mask_stack, CaveArchetype.SEA_GROTTO, (24.0, 24.0, 5.0), seed=9
    )
    damp = generate_damp_mask(state.mask_stack, path, spec)
    assert damp.shape == state.mask_stack.height.shape
    assert (damp > 0).any()
    # Written to the stack
    wet = state.mask_stack.get("wet_rock")
    assert wet is not None
    assert (np.asarray(wet) > 0).any()


# ---------------------------------------------------------------------------
# validate_cave_entrance tests
# ---------------------------------------------------------------------------


def test_validate_entrance_accepts_good_frame():
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        build_cave_entrance_frame,
        generate_cave_path,
        generate_damp_mask,
        make_archetype_spec,
        validate_cave_entrance,
    )

    state = _build_state()
    spec = make_archetype_spec(CaveArchetype.LAVA_TUBE)
    frame = build_cave_entrance_frame(
        state.mask_stack, (24.0, 24.0, 10.0), spec
    )
    path = generate_cave_path(
        state.mask_stack, CaveArchetype.LAVA_TUBE, (24.0, 24.0, 10.0), seed=1
    )
    generate_damp_mask(state.mask_stack, path, spec)

    issues = validate_cave_entrance(frame, state.mask_stack)
    assert not any(i.is_hard() for i in issues)


def test_validate_entrance_rejects_no_framing():
    from blender_addon.handlers.terrain_caves import validate_cave_entrance

    state = _build_state()
    bad_frame = {
        "archetype": "fissure",
        "world_pos": (0.0, 0.0, 0.0),
        "lip_height_m": 5.0,
        "framing_rocks": [],
        "occlusion_shelf": {"depth_m": 1.0},
    }
    issues = validate_cave_entrance(bad_frame, state.mask_stack)
    codes = [i.code for i in issues]
    assert "CAVE_NO_FRAMING" in codes
    assert any(i.is_hard() for i in issues)


def test_validate_entrance_rejects_short_lip():
    from blender_addon.handlers.terrain_caves import validate_cave_entrance

    state = _build_state()
    bad = {
        "archetype": "fissure",
        "world_pos": (0.0, 0.0, 0.0),
        "lip_height_m": 0.3,
        "framing_rocks": [{"role": "a"}, {"role": "b"}],
        "occlusion_shelf": {"depth_m": 1.0},
    }
    issues = validate_cave_entrance(bad, state.mask_stack)
    assert any(i.code == "CAVE_LIP_TOO_SHORT" for i in issues)


# ---------------------------------------------------------------------------
# pass_caves integration tests
# ---------------------------------------------------------------------------


def test_register_bundle_f_passes_adds_caves():
    from blender_addon.handlers.terrain_caves import register_bundle_f_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_f_passes()
    assert "caves" in TerrainPassController.PASS_REGISTRY
    definition = TerrainPassController.PASS_REGISTRY["caves"]
    assert definition.requires_scene_read is True
    assert "cave_candidate" in definition.produces_channels
    assert "wet_rock" in definition.produces_channels


def test_pass_caves_requires_scene_read():
    from blender_addon.handlers.terrain_caves import register_bundle_f_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        SceneReadRequired,
    )

    register_bundle_f_passes()
    height = np.zeros((33, 33), dtype=np.float64)
    stack = TerrainMaskStack(
        tile_size=32,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    intent = TerrainIntentState(
        seed=1,
        region_bounds=BBox(0.0, 0.0, 33.0, 33.0),
        tile_size=32,
        cell_size=1.0,
    )
    state = TerrainPipelineState(intent=intent, mask_stack=stack)
    controller = TerrainPassController(state)
    with pytest.raises(SceneReadRequired):
        controller.run_pass("caves")


def test_pass_caves_populates_channels_and_structures():
    from blender_addon.handlers.terrain_caves import register_bundle_f_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_f_passes()
    state = _build_state(
        cave_candidates=(
            (10.0, 10.0, 20.0),
            (30.0, 30.0, 20.0),
        ),
    )
    controller = TerrainPassController(state, checkpoint_dir=None)
    result = controller.run_pass("caves", checkpoint=False)

    assert result.status in ("ok", "warning")
    assert state.mask_stack.get("cave_candidate") is not None
    assert state.mask_stack.get("wet_rock") is not None
    assert result.metrics["cave_count"] == 2
    # side_effects recorded on state
    assert any("cave_structure:" in s for s in state.side_effects)


def test_pass_caves_region_scoping_filters_entrances():
    from blender_addon.handlers.terrain_caves import register_bundle_f_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import BBox

    register_bundle_f_passes()
    state = _build_state(
        cave_candidates=(
            (5.0, 5.0, 10.0),      # inside the small region
            (40.0, 40.0, 10.0),    # OUTSIDE
        ),
    )
    controller = TerrainPassController(state, checkpoint_dir=None)
    region = BBox(0.0, 0.0, 15.0, 15.0)
    result = controller.run_pass("caves", region=region, checkpoint=False)
    assert result.metrics["cave_count"] == 1


def test_pass_caves_respects_protected_zones():
    from blender_addon.handlers.terrain_caves import register_bundle_f_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController
    from blender_addon.handlers.terrain_semantics import BBox, ProtectedZoneSpec

    register_bundle_f_passes()

    zone = ProtectedZoneSpec(
        zone_id="sacred_grove",
        bounds=BBox(0.0, 0.0, 20.0, 20.0),
        kind="no_caves",
        forbidden_mutations=frozenset({"caves"}),
    )
    state = _build_state(
        cave_candidates=(
            (10.0, 10.0, 20.0),   # inside protected zone -> should be skipped
            (35.0, 35.0, 20.0),   # outside -> kept
        ),
        protected_zones=(zone,),
    )
    controller = TerrainPassController(state, checkpoint_dir=None)
    result = controller.run_pass("caves", checkpoint=False)
    assert result.metrics["cave_count"] == 1
    # cave_candidate mask must not overlap the protected zone
    cc = np.asarray(state.mask_stack.get("cave_candidate"), dtype=bool)
    # cells 0..19 (inclusive) are inside the zone — check no True there
    assert not cc[:20, :20].any()


def test_pass_caves_empty_scene_read_still_ok():
    from blender_addon.handlers.terrain_caves import register_bundle_f_passes
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    register_bundle_f_passes()
    state = _build_state(cave_candidates=())
    controller = TerrainPassController(state, checkpoint_dir=None)
    result = controller.run_pass("caves", checkpoint=False)
    assert result.status == "ok"
    assert result.metrics["cave_count"] == 0
