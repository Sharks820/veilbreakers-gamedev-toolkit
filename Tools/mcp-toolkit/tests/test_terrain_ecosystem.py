"""Bundle J — ecosystem spine tests.

Covers all eight modules + the unity_export manifest + the central
register_bundle_j_passes() entrypoint.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_stack(tile_size: int = 24, seed: int = 7):
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    rng = np.random.default_rng(seed)
    xs = np.linspace(0.0, 1.0, tile_size + 1)
    ys = np.linspace(0.0, 1.0, tile_size + 1)
    xv, yv = np.meshgrid(xs, ys)
    height = (
        50.0
        + 400.0 * (xv ** 2 + yv ** 2)
        + 30.0 * rng.standard_normal((tile_size + 1, tile_size + 1))
    )
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=2.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height.astype(np.float64),
    )
    return stack


def _attach_structural_masks(stack) -> None:
    h = np.asarray(stack.height, dtype=np.float64)
    gy, gx = np.gradient(h, float(stack.cell_size))
    slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    stack.set("slope", slope, "test_fixture")
    # Laplacian as rough curvature
    lap = (
        np.roll(h, 1, 0) + np.roll(h, -1, 0) + np.roll(h, 1, 1) + np.roll(h, -1, 1) - 4 * h
    ) / (stack.cell_size ** 2)
    stack.set("curvature", lap.astype(np.float64), "test_fixture")
    stack.set("ridge", (lap < -0.5).astype(np.float64), "test_fixture")
    stack.set("basin", (lap > 0.5).astype(np.int32), "test_fixture")


def _build_state(tile_size: int = 24, seed: int = 7, structural: bool = True):
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainPipelineState,
    )

    stack = _make_stack(tile_size=tile_size, seed=seed)
    if structural:
        _attach_structural_masks(stack)
    region = BBox(0.0, 0.0, float(tile_size * stack.cell_size), float(tile_size * stack.cell_size))
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region,
        tile_size=tile_size,
        cell_size=stack.cell_size,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


@pytest.fixture
def state():
    return _build_state()


@pytest.fixture
def stack(state):
    return state.mask_stack


# ---------------------------------------------------------------------------
# 1. terrain_audio_zones
# ---------------------------------------------------------------------------


def test_audio_zones_produces_int8_array(stack):
    from blender_addon.handlers.terrain_audio_zones import compute_audio_reverb_zones

    arr = compute_audio_reverb_zones(stack)
    assert arr.dtype == np.int8
    assert arr.shape == stack.height.shape


def test_audio_zones_cave_overrides_open(stack):
    from blender_addon.handlers.terrain_audio_zones import (
        AudioReverbClass,
        compute_audio_reverb_zones,
    )

    cave = np.zeros_like(stack.height, dtype=np.float64)
    cave[5:10, 5:10] = 1.0
    stack.set("cave_candidate", cave, "test")
    arr = compute_audio_reverb_zones(stack)
    assert (arr[5:10, 5:10] == AudioReverbClass.CAVE.value).all()


def test_audio_zones_water_sets_water_near(stack):
    from blender_addon.handlers.terrain_audio_zones import (
        AudioReverbClass,
        compute_audio_reverb_zones,
    )

    water = np.zeros_like(stack.height, dtype=np.float64)
    water[12:15, 12:15] = 1.0
    stack.set("water_surface", water, "test")
    arr = compute_audio_reverb_zones(stack)
    assert (arr[12:15, 12:15] == AudioReverbClass.WATER_NEAR.value).any()


def test_pass_audio_zones_populates_channel(state):
    from blender_addon.handlers.terrain_audio_zones import pass_audio_zones

    result = pass_audio_zones(state, None)
    assert result.status == "ok"
    assert state.mask_stack.audio_reverb_class is not None
    assert "audio_reverb_class" in result.produced_channels


# ---------------------------------------------------------------------------
# 2. terrain_wildlife_zones
# ---------------------------------------------------------------------------


def test_wildlife_affinity_default_rules(stack):
    from blender_addon.handlers.terrain_wildlife_zones import (
        DEFAULT_WILDLIFE_RULES,
        compute_wildlife_affinity,
    )

    rules = [r for r in DEFAULT_WILDLIFE_RULES if r.species != "deer"]
    maps = compute_wildlife_affinity(stack, rules)
    for rule in rules:
        assert rule.species in maps
        arr = maps[rule.species]
        assert arr.shape == stack.height.shape
        assert arr.dtype == np.float32
        assert (arr >= 0).all() and (arr <= 1.01).all()


def test_wildlife_zones_writes_dict_channel(state):
    from blender_addon.handlers.terrain_wildlife_zones import pass_wildlife_zones

    result = pass_wildlife_zones(state, None)
    assert result.status == "ok"
    assert state.mask_stack.wildlife_affinity is not None
    assert len(state.mask_stack.wildlife_affinity) >= 1


def test_wildlife_exclusion_respects_hero_exclusion(stack):
    from blender_addon.handlers.terrain_wildlife_zones import (
        SpeciesAffinityRule,
        compute_wildlife_affinity,
    )

    excl = np.zeros_like(stack.height, dtype=bool)
    excl[:4, :4] = True
    stack.set("hero_exclusion", excl.astype(np.float32), "test")
    rule = SpeciesAffinityRule(
        species="boar",
        preferred_slope=(0.0, 90.0),
        preferred_altitude=(-10000.0, 10000.0),
        exclusion_radius_m=10.0,
    )
    maps = compute_wildlife_affinity(stack, [rule])
    assert maps["boar"][0, 0] == 0.0


# ---------------------------------------------------------------------------
# 3. terrain_gameplay_zones
# ---------------------------------------------------------------------------


def test_gameplay_zones_returns_int32(stack):
    from blender_addon.handlers.terrain_gameplay_zones import compute_gameplay_zones

    zones = compute_gameplay_zones(stack)
    assert zones.dtype == np.int32
    assert zones.shape == stack.height.shape


def test_gameplay_zones_puzzle_from_caves(stack):
    from blender_addon.handlers.terrain_gameplay_zones import (
        GameplayZoneType,
        compute_gameplay_zones,
    )

    cave = np.zeros_like(stack.height, dtype=np.float64)
    cave[3:6, 3:6] = 1.0
    stack.set("cave_candidate", cave, "test")
    zones = compute_gameplay_zones(stack)
    assert (zones[3:6, 3:6] == GameplayZoneType.PUZZLE.value).all()


def test_pass_gameplay_zones_populates(state):
    from blender_addon.handlers.terrain_gameplay_zones import pass_gameplay_zones

    result = pass_gameplay_zones(state, None)
    assert result.status == "ok"
    assert state.mask_stack.gameplay_zone is not None
    assert "gameplay_zone" in result.produced_channels


# ---------------------------------------------------------------------------
# 4. terrain_wind_field
# ---------------------------------------------------------------------------


def test_wind_field_shape_and_dtype(stack):
    from blender_addon.handlers.terrain_wind_field import compute_wind_field

    field = compute_wind_field(stack, 0.5, 6.0)
    assert field.dtype == np.float32
    assert field.shape == stack.height.shape + (2,)


def test_wind_field_faster_at_altitude(stack):
    from blender_addon.handlers.terrain_wind_field import compute_wind_field

    field = compute_wind_field(stack, 0.0, 5.0)
    speed = np.sqrt(field[..., 0] ** 2 + field[..., 1] ** 2)
    h = np.asarray(stack.height)
    top_idx = np.unravel_index(np.argmax(h), h.shape)
    bot_idx = np.unravel_index(np.argmin(h), h.shape)
    # Not strict — perturbation can flip locally, use means of top/bottom quartiles
    top_mask = h >= np.quantile(h, 0.9)
    bot_mask = h <= np.quantile(h, 0.1)
    assert speed[top_mask].mean() >= speed[bot_mask].mean() * 0.95


def test_pass_wind_field_populates(state):
    from blender_addon.handlers.terrain_wind_field import pass_wind_field

    result = pass_wind_field(state, None)
    assert result.status == "ok"
    wf = state.mask_stack.wind_field
    assert wf is not None and wf.shape[-1] == 2


# ---------------------------------------------------------------------------
# 5. terrain_cloud_shadow
# ---------------------------------------------------------------------------


def test_cloud_shadow_range(stack):
    from blender_addon.handlers.terrain_cloud_shadow import compute_cloud_shadow_mask

    mask = compute_cloud_shadow_mask(stack, seed=42, cloud_density=0.5, cloud_scale_m=60.0)
    assert mask.dtype == np.float32
    assert (mask >= 0).all() and (mask <= 1.0001).all()
    assert mask.shape == stack.height.shape


def test_cloud_shadow_determinism(stack):
    from blender_addon.handlers.terrain_cloud_shadow import compute_cloud_shadow_mask

    a = compute_cloud_shadow_mask(stack, seed=123)
    b = compute_cloud_shadow_mask(stack, seed=123)
    np.testing.assert_array_equal(a, b)


def test_pass_cloud_shadow_populates(state):
    from blender_addon.handlers.terrain_cloud_shadow import pass_cloud_shadow

    result = pass_cloud_shadow(state, None)
    assert result.status == "ok"
    assert state.mask_stack.cloud_shadow is not None


# ---------------------------------------------------------------------------
# 6. terrain_decal_placement
# ---------------------------------------------------------------------------


def test_decal_kinds_produce_float32_in_unit_range(stack):
    from blender_addon.handlers.terrain_decal_placement import (
        DecalKind,
        compute_decal_density,
    )

    for kind in DecalKind:
        arr = compute_decal_density(stack, kind)
        assert arr.dtype == np.float32
        assert arr.shape == stack.height.shape
        assert (arr >= 0).all() and (arr <= 1.0001).all()


def test_pass_decals_fills_dict_channel(state):
    from blender_addon.handlers.terrain_decal_placement import DecalKind, pass_decals

    result = pass_decals(state, None)
    assert result.status == "ok"
    assert state.mask_stack.decal_density is not None
    for kind in DecalKind:
        assert kind.value in state.mask_stack.decal_density


# ---------------------------------------------------------------------------
# 7. terrain_navmesh_export
# ---------------------------------------------------------------------------


def test_navmesh_area_id_classification(stack):
    from blender_addon.handlers.terrain_navmesh_export import (
        NAVMESH_SWIM,
        NAVMESH_WALKABLE,
        compute_navmesh_area_id,
    )

    water = np.zeros_like(stack.height, dtype=np.float64)
    water[0:3, 0:3] = 1.0
    stack.set("water_surface", water, "test")
    area = compute_navmesh_area_id(stack, max_walkable_slope_deg=60.0)
    assert area.dtype == np.int8
    assert (area[0:3, 0:3] == NAVMESH_SWIM).all()
    assert (area == NAVMESH_WALKABLE).any()


def test_traversability_is_unit_range_float32(stack):
    from blender_addon.handlers.terrain_navmesh_export import compute_traversability

    trav = compute_traversability(stack)
    assert trav.dtype == np.float32
    assert (trav >= 0).all() and (trav <= 1.0).all()


def test_pass_navmesh_produces_two_channels(state):
    from blender_addon.handlers.terrain_navmesh_export import pass_navmesh

    result = pass_navmesh(state, None)
    assert result.status == "ok"
    assert state.mask_stack.navmesh_area_id is not None
    assert state.mask_stack.traversability is not None
    assert set(result.produced_channels) == {"navmesh_area_id", "traversability"}


def test_export_navmesh_json_writes_file(state):
    from blender_addon.handlers.terrain_navmesh_export import export_navmesh_json

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "navmesh.json"
        descriptor = export_navmesh_json(state.mask_stack, out)
        assert out.exists()
        assert descriptor["schema_version"] == "1.0"
        assert "area_ids" in descriptor
        assert descriptor["tile_x"] == 0
        data = json.loads(out.read_text())
        assert data["area_ids"]["walkable"] == 1


# ---------------------------------------------------------------------------
# 8. terrain_ecotone_graph
# ---------------------------------------------------------------------------


def test_ecotone_graph_empty_without_biome(stack):
    from blender_addon.handlers.terrain_ecotone_graph import build_ecotone_graph

    graph = build_ecotone_graph(stack)
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_ecotone_graph_with_biomes(stack):
    from blender_addon.handlers.terrain_ecotone_graph import build_ecotone_graph

    biome = np.zeros(stack.height.shape, dtype=np.int32)
    biome[:, : stack.height.shape[1] // 2] = 1
    biome[:, stack.height.shape[1] // 2 :] = 2
    stack.set("biome_id", biome, "test")
    graph = build_ecotone_graph(stack)
    assert set(graph["nodes"]) == {1, 2}
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["from_biome"] == 1
    assert graph["edges"][0]["to_biome"] == 2
    assert graph["edges"][0]["shared_cells"] > 0


def test_validate_ecotone_smoothness_flags_narrow(stack):
    from blender_addon.handlers.terrain_ecotone_graph import validate_ecotone_smoothness

    graph = {
        "cell_size_m": 2.0,
        "edges": [
            {
                "from_biome": 1,
                "to_biome": 2,
                "transition_width_m": 1.0,
                "mixing_curve": "smoothstep",
                "shared_cells": 5,
            }
        ],
    }
    issues = validate_ecotone_smoothness(graph)
    assert any(i.code == "ECOTONE_HARD_BOUNDARY" for i in issues)


def test_pass_ecotones_runs_clean(state):
    from blender_addon.handlers.terrain_ecotone_graph import pass_ecotones

    result = pass_ecotones(state, None)
    assert result.status == "ok"
    assert "graph" in result.metrics
    # Ecotones pass guarantees traversability is populated (Unity-ready).
    assert state.mask_stack.traversability is not None


# ---------------------------------------------------------------------------
# 9. terrain_unity_export
# ---------------------------------------------------------------------------


def test_unity_export_manifest_writes_files(state):
    from blender_addon.handlers.terrain_audio_zones import pass_audio_zones
    from blender_addon.handlers.terrain_cloud_shadow import pass_cloud_shadow
    from blender_addon.handlers.terrain_decal_placement import pass_decals
    from blender_addon.handlers.terrain_gameplay_zones import pass_gameplay_zones
    from blender_addon.handlers.terrain_navmesh_export import pass_navmesh
    from blender_addon.handlers.terrain_unity_export import export_unity_manifest
    from blender_addon.handlers.terrain_wildlife_zones import pass_wildlife_zones
    from blender_addon.handlers.terrain_wind_field import pass_wind_field

    for p in (
        pass_audio_zones,
        pass_wildlife_zones,
        pass_gameplay_zones,
        pass_wind_field,
        pass_cloud_shadow,
        pass_decals,
        pass_navmesh,
    ):
        p(state, None)

    with tempfile.TemporaryDirectory() as td:
        manifest = export_unity_manifest(state.mask_stack, Path(td))
        out = Path(td)
        assert (out / "manifest.json").exists()
        assert (out / "heightmap_raw_u16.npy").exists()
        assert (out / "wind_field.npy").exists()
        assert (out / "cloud_shadow.npy").exists()
        assert (out / "navmesh_area_id.npy").exists()
        assert (out / "audio_reverb_class.npy").exists()
        assert (out / "gameplay_zone.npy").exists()
        assert (out / "audio_zones.json").exists()
        assert (out / "gameplay_zones.json").exists()
        assert (out / "wildlife_zones.json").exists()
        assert (out / "decals.json").exists()
        assert (out / "ecosystem_meta.json").exists()
        assert manifest["schema_version"] == "1.0"
        assert "determinism_hash" in manifest
        assert manifest["coordinate_system"] == "z-up"


def test_unity_export_json_schemas(state):
    from blender_addon.handlers.terrain_audio_zones import pass_audio_zones
    from blender_addon.handlers.terrain_gameplay_zones import pass_gameplay_zones
    from blender_addon.handlers.terrain_unity_export import export_unity_manifest

    pass_audio_zones(state, None)
    pass_gameplay_zones(state, None)

    with tempfile.TemporaryDirectory() as td:
        export_unity_manifest(state.mask_stack, Path(td))
        az = json.loads((Path(td) / "audio_zones.json").read_text())
        assert az["schema_version"] == "1.0"
        assert "zones" in az
        if az["zones"]:
            z0 = az["zones"][0]
            assert "bounds" in z0 and "reverb_class" in z0
            assert "wet_mix" in z0 and "early_reflections" in z0 and "tail_length" in z0
        gz = json.loads((Path(td) / "gameplay_zones.json").read_text())
        assert gz["schema_version"] == "1.0"
        assert "zones" in gz


def test_unity_export_heightmap_u16_quantized(state):
    from blender_addon.handlers.terrain_unity_export import export_unity_manifest

    with tempfile.TemporaryDirectory() as td:
        export_unity_manifest(state.mask_stack, Path(td))
        arr = np.load(Path(td) / "heightmap_raw_u16.npy")
        assert arr.dtype == np.uint16
        assert arr.shape == state.mask_stack.height.shape


def test_prepare_heightmap_raw_u16_pass_populates_channel(state):
    from blender_addon.handlers.terrain_unity_export import pass_prepare_heightmap_raw_u16

    result = pass_prepare_heightmap_raw_u16(state, None)

    assert result.status == "ok"
    assert state.mask_stack.heightmap_raw_u16 is not None
    assert state.mask_stack.heightmap_raw_u16.dtype == np.uint16
    assert "heightmap_raw_u16" in result.produced_channels


# ---------------------------------------------------------------------------
# 10. terrain_bundle_j central registrar
# ---------------------------------------------------------------------------


def test_register_bundle_j_passes_lands_all_eight():
    from blender_addon.handlers.terrain_bundle_j import (
        BUNDLE_J_PASSES,
        register_bundle_j_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    try:
        register_bundle_j_passes()
        registry = TerrainPassController.PASS_REGISTRY
        for name in BUNDLE_J_PASSES:
            assert name in registry, f"missing Bundle J pass: {name}"
    finally:
        TerrainPassController.clear_registry()


def test_bundle_j_passes_run_through_controller():
    from blender_addon.handlers.terrain_bundle_j import (
        BUNDLE_J_PASSES,
        register_bundle_j_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    try:
        register_bundle_j_passes()
        state = _build_state(tile_size=16)
        with tempfile.TemporaryDirectory() as td:
            controller = TerrainPassController(state, checkpoint_dir=Path(td))
            for name in BUNDLE_J_PASSES:
                res = controller.run_pass(name, checkpoint=False)
                assert res.status == "ok", f"{name} failed: {res.issues}"
    finally:
        TerrainPassController.clear_registry()


def test_bundle_j_passes_do_not_require_scene_read():
    """Bundle J passes are read-only classification — no scene read needed."""
    from blender_addon.handlers.terrain_bundle_j import (
        BUNDLE_J_PASSES,
        register_bundle_j_passes,
    )
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    try:
        register_bundle_j_passes()
        for name in BUNDLE_J_PASSES:
            defn = TerrainPassController.get_pass(name)
            assert defn.requires_scene_read is False, (
                f"{name} should not require scene read"
            )
    finally:
        TerrainPassController.clear_registry()


def test_bundle_j_does_not_touch_default_passes():
    """Ensure Bundle J registration does not clobber Bundle A passes when
    both are registered in sequence."""
    from blender_addon.handlers.terrain_bundle_j import register_bundle_j_passes
    from blender_addon.handlers.terrain_pipeline import (
        TerrainPassController,
        register_default_passes,
    )

    TerrainPassController.clear_registry()
    try:
        register_default_passes()
        register_bundle_j_passes()
        reg = TerrainPassController.PASS_REGISTRY
        for name in ("macro_world", "structural_masks", "erosion", "validation_minimal"):
            assert name in reg
        for name in (
            "audio_zones",
            "wildlife_zones",
            "gameplay_zones",
            "wind_field",
            "cloud_shadow",
            "decals",
            "navmesh",
            "ecotones",
        ):
            assert name in reg
    finally:
        TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# Cross-cutting: Unity-ready channel coverage
# ---------------------------------------------------------------------------


def test_bundle_j_populates_unity_ready_channels(state):
    """Every Bundle J pass must populate at least one Unity-ready channel."""
    from blender_addon.handlers.terrain_audio_zones import pass_audio_zones
    from blender_addon.handlers.terrain_cloud_shadow import pass_cloud_shadow
    from blender_addon.handlers.terrain_gameplay_zones import pass_gameplay_zones
    from blender_addon.handlers.terrain_navmesh_export import pass_navmesh
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack
    from blender_addon.handlers.terrain_wind_field import pass_wind_field

    unity_channels = set(TerrainMaskStack.UNITY_EXPORT_CHANNELS)
    checks = [
        (pass_audio_zones, "audio_reverb_class"),
        (pass_gameplay_zones, "gameplay_zone"),
        (pass_wind_field, "wind_field"),
        (pass_cloud_shadow, "cloud_shadow"),
        (pass_navmesh, "navmesh_area_id"),
    ]
    for pass_fn, expected in checks:
        assert expected in unity_channels
        pass_fn(state, None)
        assert state.mask_stack.get(expected) is not None


def test_wildlife_affinity_populates_dict_channel_provenance(state):
    from blender_addon.handlers.terrain_wildlife_zones import pass_wildlife_zones

    pass_wildlife_zones(state, None)
    assert "wildlife_affinity" in state.mask_stack.populated_by_pass


def test_decal_density_populates_dict_channel_provenance(state):
    from blender_addon.handlers.terrain_decal_placement import pass_decals

    pass_decals(state, None)
    assert "decal_density" in state.mask_stack.populated_by_pass


def test_audio_zones_metrics_contain_distribution(state):
    from blender_addon.handlers.terrain_audio_zones import pass_audio_zones

    result = pass_audio_zones(state, None)
    assert "class_distribution" in result.metrics


def test_unity_export_manifest_minimal_without_optional_channels():
    """Manifest export works even if only height is populated."""
    from blender_addon.handlers.terrain_unity_export import export_unity_manifest

    state = _build_state(structural=False)
    with tempfile.TemporaryDirectory() as td:
        manifest = export_unity_manifest(state.mask_stack, Path(td))
        assert (Path(td) / "manifest.json").exists()
        assert manifest["files"]["heightmap_raw_u16.npy"]["dtype"] == "uint16"
