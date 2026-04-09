"""Bundle E/G/J/N supplements — regression tests.

Covers:
- terrain_asset_metadata (Bundle E / Addendum 1.B.5)
- terrain_banded_advanced (Bundle G / Addendum 1.B.7)
- terrain_readability_semantic (Bundle N / Addendum 1.B.8)
- terrain_unity_export_contracts (§33 / Addendum 1.B.9)
- terrain_performance_report (Addendum 3.B.4)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from blender_addon.handlers.terrain_asset_metadata import (
    LOCATION_TAGS,
    ROLE_TAGS,
    SIZE_TAGS,
    CONTEXT_TAGS,
    AssetContextRuleExt,
    AssetMetadata,
    classify_size_from_bounds,
    validate_asset_metadata,
)
from blender_addon.handlers.terrain_banded_advanced import (
    apply_anti_grain_smoothing,
    compute_anisotropic_breakup,
)
from blender_addon.handlers.terrain_readability_semantic import (
    check_cave_framing_presence,
    check_cliff_silhouette_readability,
    check_focal_composition,
    check_waterfall_chain_completeness,
    run_semantic_readability_audit,
)
from blender_addon.handlers.terrain_unity_export_contracts import (
    REQUIRED_MESH_ATTRIBUTES,
    UnityExportContract,
    validate_bit_depth_contract,
    validate_mesh_attributes_present,
    write_export_manifest,
)
from blender_addon.handlers.terrain_performance_report import (
    DEFAULT_BUDGETS,
    collect_performance_report,
    serialize_performance_report,
)
from blender_addon.handlers.terrain_semantics import TerrainMaskStack


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _tiny_stack(size: int = 8) -> TerrainMaskStack:
    h = np.linspace(0.0, 10.0, size * size, dtype=np.float32).reshape(size, size)
    return TerrainMaskStack(
        tile_size=0,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )


# ---------------------------------------------------------------------------
# Bundle E — asset metadata taxonomy
# ---------------------------------------------------------------------------


class TestAssetMetadataTaxonomy:
    def test_constants_have_expected_sizes(self):
        assert len(LOCATION_TAGS) == 10
        assert len(ROLE_TAGS) == 3
        assert len(SIZE_TAGS) == 3
        assert len(CONTEXT_TAGS) == 4

    def test_required_location_tags_present(self):
        for needed in (
            "cliff",
            "riverbank",
            "waterfall_base",
            "cave_entrance",
            "plateau",
            "forest_floor",
            "beach",
            "wetland",
            "alpine",
            "cultivated",
        ):
            assert needed in LOCATION_TAGS

    def test_valid_metadata_yields_no_issues(self):
        meta = AssetMetadata(
            location_tags=("cliff",),
            role_tag="hero",
            size_tag="large",
            context_tags=("silhouette_critical",),
        )
        assert validate_asset_metadata(meta) == []

    def test_missing_location_fails_hard(self):
        meta = AssetMetadata(
            location_tags=(),
            role_tag="hero",
            size_tag="large",
            context_tags=("silhouette_critical",),
        )
        issues = validate_asset_metadata(meta)
        codes = [i.code for i in issues]
        assert "ASSET_META_NO_LOCATION" in codes
        assert all(i.is_hard() for i in issues)

    def test_invalid_role_fails_hard(self):
        meta = AssetMetadata(
            location_tags=("cliff",),
            role_tag="boss",
            size_tag="large",
            context_tags=("silhouette_critical",),
        )
        issues = validate_asset_metadata(meta)
        assert any(i.code == "ASSET_META_INVALID_ROLE" for i in issues)

    def test_invalid_size_fails_hard(self):
        meta = AssetMetadata(
            location_tags=("cliff",),
            role_tag="hero",
            size_tag="giant",
            context_tags=("silhouette_critical",),
        )
        issues = validate_asset_metadata(meta)
        assert any(i.code == "ASSET_META_INVALID_SIZE" for i in issues)

    def test_missing_context_fails_hard(self):
        meta = AssetMetadata(
            location_tags=("cliff",),
            role_tag="hero",
            size_tag="large",
            context_tags=(),
        )
        issues = validate_asset_metadata(meta)
        assert any(i.code == "ASSET_META_NO_CONTEXT" for i in issues)

    def test_unknown_location_tag_fails_hard(self):
        meta = AssetMetadata(
            location_tags=("bogus",),
            role_tag="hero",
            size_tag="large",
            context_tags=("silhouette_critical",),
        )
        issues = validate_asset_metadata(meta)
        assert any(i.code == "ASSET_META_INVALID_LOCATION" for i in issues)

    def test_classify_size_from_bounds(self):
        assert classify_size_from_bounds(4.0) == "large"
        assert classify_size_from_bounds(1.5) == "medium"
        assert classify_size_from_bounds(0.1) == "small"
        assert classify_size_from_bounds(0.5) == "medium"  # boundary


class TestAssetContextRuleExt:
    def test_defaults(self):
        rule = AssetContextRuleExt(asset_id="rock_01")
        assert rule.scale_variance_by_role == 0.2
        assert rule.camera_priority_weight == 0.0

    def test_hero_variance_is_smaller(self):
        rule = AssetContextRuleExt(asset_id="hero_rock", scale_variance_by_role=0.4)
        assert rule.effective_variance("hero") < rule.effective_variance("support")

    def test_filler_variance_is_larger(self):
        rule = AssetContextRuleExt(asset_id="filler_rock", scale_variance_by_role=0.4)
        assert rule.effective_variance("filler") > rule.effective_variance("support")


# ---------------------------------------------------------------------------
# Bundle G — banded advanced
# ---------------------------------------------------------------------------


class TestBandedAdvanced:
    def test_anti_grain_smoothing_preserves_shape(self):
        rng = np.random.default_rng(0)
        hm = rng.standard_normal((16, 16)).astype(np.float32)
        out = apply_anti_grain_smoothing(hm, sigma=0.8)
        assert out.shape == hm.shape
        assert out.dtype == hm.dtype

    def test_anti_grain_smoothing_reduces_variance(self):
        rng = np.random.default_rng(1)
        hm = rng.standard_normal((32, 32)).astype(np.float32) * 2.0
        out = apply_anti_grain_smoothing(hm, sigma=1.5)
        assert out.var() < hm.var()

    def test_anti_grain_smoothing_zero_sigma_is_noop(self):
        hm = np.ones((8, 8), dtype=np.float32)
        out = apply_anti_grain_smoothing(hm, sigma=0.0)
        np.testing.assert_allclose(out, hm)

    def test_anti_grain_smoothing_rejects_non_2d(self):
        with pytest.raises(ValueError):
            apply_anti_grain_smoothing(np.zeros((4, 4, 4)))

    def test_anisotropic_breakup_deterministic(self):
        base = np.zeros((16, 16), dtype=np.float32)
        a = compute_anisotropic_breakup(base, (1.0, 0.0), 0.5)
        b = compute_anisotropic_breakup(base, (1.0, 0.0), 0.5)
        np.testing.assert_array_equal(a, b)

    def test_anisotropic_breakup_zero_strength_is_copy(self):
        rng = np.random.default_rng(3)
        base = rng.standard_normal((8, 8)).astype(np.float32)
        out = compute_anisotropic_breakup(base, (1.0, 0.0), 0.0)
        np.testing.assert_array_equal(out, base)

    def test_anisotropic_breakup_zero_direction_is_noop(self):
        base = np.ones((8, 8), dtype=np.float32)
        out = compute_anisotropic_breakup(base, (0.0, 0.0), 1.0)
        np.testing.assert_array_equal(out, base)

    def test_anisotropic_breakup_direction_matters(self):
        base = np.zeros((16, 16), dtype=np.float32)
        x_break = compute_anisotropic_breakup(base, (1.0, 0.0), 0.5)
        y_break = compute_anisotropic_breakup(base, (0.0, 1.0), 0.5)
        assert not np.allclose(x_break, y_break)

    def test_anisotropic_breakup_preserves_shape_and_dtype(self):
        base = np.zeros((8, 12), dtype=np.float32)
        out = compute_anisotropic_breakup(base, (0.5, 0.5), 0.3)
        assert out.shape == base.shape
        assert out.dtype == base.dtype


# ---------------------------------------------------------------------------
# Bundle N — semantic readability
# ---------------------------------------------------------------------------


class TestSemanticReadability:
    def test_no_cliffs_is_vacuously_readable(self):
        stack = _tiny_stack()
        assert check_cliff_silhouette_readability(stack) == []

    def test_cliff_without_slope_fails(self):
        stack = _tiny_stack()
        stack.cliff_candidate = np.ones((8, 8), dtype=np.float32)
        issues = check_cliff_silhouette_readability(stack)
        assert any(i.code == "CLIFF_READABILITY_NO_SLOPE" for i in issues)

    def test_sparse_cliff_footprint_fails(self):
        stack = _tiny_stack(size=64)
        cliff = np.zeros((64, 64), dtype=np.float32)
        cliff[0, 0] = 1.0  # 1 out of 4096 < 0.5%
        stack.cliff_candidate = cliff
        stack.slope = np.full((64, 64), 1.0, dtype=np.float32)
        issues = check_cliff_silhouette_readability(stack)
        assert any(i.code == "CLIFF_READABILITY_UNDERFOOTED" for i in issues)

    def test_soft_lip_cliff_fails(self):
        stack = _tiny_stack(size=32)
        stack.cliff_candidate = np.ones((32, 32), dtype=np.float32)
        stack.slope = np.full((32, 32), 0.1, dtype=np.float32)
        issues = check_cliff_silhouette_readability(stack)
        assert any(i.code == "CLIFF_READABILITY_SOFT_LIP" for i in issues)

    def test_good_cliff_passes(self):
        stack = _tiny_stack(size=32)
        stack.cliff_candidate = np.ones((32, 32), dtype=np.float32)
        stack.slope = np.full((32, 32), 1.2, dtype=np.float32)
        assert check_cliff_silhouette_readability(stack) == []

    def test_waterfall_chain_complete(self):
        stack = _tiny_stack()
        chains = [
            {"source": (0, 0, 0), "lip": (1, 0, 0), "pool": (2, 0, 0), "outflow": (3, 0, 0)}
        ]
        assert check_waterfall_chain_completeness(stack, chains) == []

    def test_waterfall_chain_missing_pool_fails(self):
        stack = _tiny_stack()
        chains = [{"source": (0, 0, 0), "lip": (1, 0, 0), "outflow": (3, 0, 0)}]
        issues = check_waterfall_chain_completeness(stack, chains)
        assert any(i.code == "WATERFALL_CHAIN_INCOMPLETE" for i in issues)

    def test_cave_framing_insufficient_fails(self):
        stack = _tiny_stack()
        caves = [{"framing_markers": [("r1",)], "damp_signal": 0.5}]
        issues = check_cave_framing_presence(stack, caves)
        assert any(i.code == "CAVE_FRAMING_INSUFFICIENT" for i in issues)

    def test_cave_missing_damp_fails(self):
        stack = _tiny_stack()
        caves = [{"framing_markers": ["r1", "r2"], "damp_signal": None}]
        issues = check_cave_framing_presence(stack, caves)
        assert any(i.code == "CAVE_DAMP_MISSING" for i in issues)

    def test_cave_ok(self):
        stack = _tiny_stack()
        caves = [{"framing_markers": ["r1", "r2"], "damp_signal": 0.4}]
        assert check_cave_framing_presence(stack, caves) == []

    def test_focal_composition_on_thirds_passes(self):
        stack = _tiny_stack()
        assert check_focal_composition(stack, (1 / 3, 1 / 3)) == []

    def test_focal_composition_centered_fails(self):
        stack = _tiny_stack()
        issues = check_focal_composition(stack, (0.5, 0.5))
        assert any(i.code == "FOCAL_COMPOSITION_OFF_THIRDS" for i in issues)

    def test_focal_out_of_frame_fails(self):
        stack = _tiny_stack()
        issues = check_focal_composition(stack, (1.5, 0.5))
        assert any(i.code == "FOCAL_OUT_OF_FRAME" for i in issues)

    def test_run_semantic_readability_audit_aggregates(self):
        stack = _tiny_stack(size=32)
        stack.cliff_candidate = np.ones((32, 32), dtype=np.float32)
        stack.slope = np.full((32, 32), 0.1, dtype=np.float32)
        chains = [{"source": 1, "lip": 1, "pool": None, "outflow": 1}]
        caves = [{"framing_markers": [], "damp_signal": None}]
        issues = run_semantic_readability_audit(
            stack, chains=chains, caves=caves, focal=(0.5, 0.5)
        )
        codes = {i.code for i in issues}
        assert "CLIFF_READABILITY_SOFT_LIP" in codes
        assert "WATERFALL_CHAIN_INCOMPLETE" in codes
        assert "CAVE_FRAMING_INSUFFICIENT" in codes
        assert "FOCAL_COMPOSITION_OFF_THIRDS" in codes


# ---------------------------------------------------------------------------
# §33 — Unity export contracts
# ---------------------------------------------------------------------------


class TestUnityExportContracts:
    def test_required_mesh_attributes_exact_set(self):
        assert len(REQUIRED_MESH_ATTRIBUTES) == 6
        for attr in (
            "slope_angle",
            "flow_accumulation",
            "wetness",
            "biome_id",
            "cliff_mask",
            "protected_zone_id",
        ):
            assert attr in REQUIRED_MESH_ATTRIBUTES

    def test_all_attrs_present_no_issues(self):
        assert validate_mesh_attributes_present(REQUIRED_MESH_ATTRIBUTES) == []

    def test_missing_attr_emits_hard_issue(self):
        present = [a for a in REQUIRED_MESH_ATTRIBUTES if a != "wetness"]
        issues = validate_mesh_attributes_present(present)
        assert len(issues) == 1
        assert issues[0].code == "MESH_ATTR_MISSING"
        assert issues[0].affected_feature == "wetness"
        assert issues[0].is_hard()

    def test_unity_contract_defaults(self):
        c = UnityExportContract()
        assert c.heightmap_bit_depth == 32
        assert c.heightmap_encoding == "float"
        assert c.splatmap_bit_depth == 16
        assert c.shadow_clipmap_bit_depth == 32
        assert c.mask_stack_preserves_dtype is True

    def test_bit_depth_contract_passes_on_compliant(self):
        c = UnityExportContract()
        meta = {
            "heightmap.exr": {"bit_depth": 32, "encoding": "float"},
            "splatmap.exr": {"bit_depth": 16, "encoding": "float"},
            "shadow_clipmap.exr": {"bit_depth": 32, "encoding": "float"},
        }
        assert validate_bit_depth_contract(c, meta) == []

    def test_bit_depth_violation_detected(self):
        c = UnityExportContract()
        meta = {
            "heightmap.exr": {"bit_depth": 8, "encoding": "float"},
        }
        issues = validate_bit_depth_contract(c, meta)
        assert any(i.code == "BIT_DEPTH_VIOLATION" for i in issues)

    def test_heightmap_encoding_violation_detected(self):
        c = UnityExportContract()
        meta = {
            "heightmap.exr": {"bit_depth": 32, "encoding": "int"},
        }
        issues = validate_bit_depth_contract(c, meta)
        assert any(i.code == "HEIGHTMAP_ENCODING_VIOLATION" for i in issues)

    def test_write_export_manifest(self, tmp_path: Path):
        files = {
            "heightmap.exr": {"bit_depth": 32, "channels": 1, "encoding": "float"},
            "splatmap.exr": {"bit_depth": 16, "channels": 4, "encoding": "float"},
        }
        manifest_path = write_export_manifest(tmp_path, files)
        assert manifest_path.exists()
        payload = json.loads(manifest_path.read_text())
        assert "files" in payload
        assert "heightmap.exr" in payload["files"]

    def test_write_export_manifest_rejects_missing_keys(self, tmp_path: Path):
        with pytest.raises(ValueError):
            write_export_manifest(tmp_path, {"h.exr": {"bit_depth": 32}})


# ---------------------------------------------------------------------------
# Addendum 3.B.4 — Real performance report
# ---------------------------------------------------------------------------


class TestPerformanceReport:
    def test_none_stack_not_available(self):
        # Invalid stack triggers the not_available guard
        rep = collect_performance_report(None)  # type: ignore[arg-type]
        assert rep.status == "not_available"

    def test_empty_height_not_available(self):
        # Build a stack, then null out height to simulate unpopulated
        stack = _tiny_stack()
        stack.height = np.zeros((0, 0), dtype=np.float32)
        rep = collect_performance_report(stack)
        assert rep.status == "not_available"

    def test_basic_stack_reports_triangles(self):
        stack = _tiny_stack(size=8)
        rep = collect_performance_report(stack)
        assert rep.triangle_count["terrain"] == 8 * 8 * 2
        # Small tile fits within default terrain budget
        assert rep.within_budget["terrain"] is True

    def test_never_fake_ok_when_height_zero(self):
        stack = _tiny_stack()
        stack.height = np.zeros((0, 0), dtype=np.float32)
        rep = collect_performance_report(stack)
        assert rep.status != "ok"

    def test_over_budget_detected(self):
        # 8x8 tile = 128 terrain triangles; set terrain budget to 10
        stack = _tiny_stack(size=8)
        budgets = dict(DEFAULT_BUDGETS)
        budgets["terrain"] = 10
        rep = collect_performance_report(stack, budgets=budgets)
        assert rep.status == "over_budget"
        assert rep.within_budget["terrain"] is False

    def test_material_count_from_splatmap(self):
        stack = _tiny_stack(size=8)
        stack.splatmap_weights_layer = np.zeros((8, 8, 4), dtype=np.float32)
        rep = collect_performance_report(stack)
        assert rep.material_count == 4

    def test_tree_instance_count(self):
        stack = _tiny_stack(size=8)
        stack.tree_instance_points = np.zeros((17, 5), dtype=np.float32)
        rep = collect_performance_report(stack)
        assert rep.instance_count["trees"] == 17

    def test_serialize_report_round_trip(self):
        stack = _tiny_stack(size=8)
        rep = collect_performance_report(stack)
        payload = serialize_performance_report(rep)
        assert "triangle_count" in payload
        assert "status" in payload
        assert payload["status"] in ("ok", "over_budget", "not_available")

    def test_default_budgets_keys(self):
        for key in ("terrain", "water", "foliage", "rock", "cliff"):
            assert key in DEFAULT_BUDGETS
