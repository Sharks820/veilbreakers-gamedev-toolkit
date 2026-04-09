"""Bundle H — Composition & Intent tests.

Covers saliency refinement, morphology templates, framing sightlines,
feature hierarchy/budget, rhythm analysis, and negative-space enforcement.
"""

from __future__ import annotations

import numpy as np
import pytest

from blender_addon.handlers.terrain_semantics import (
    BBox,
    HeroFeatureSpec,
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
    TerrainSceneRead,
)
from blender_addon.handlers import terrain_masks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_height(tile: int = 32, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # Low frequency hill plus noise
    xs = np.linspace(-1.0, 1.0, tile + 1)
    ys = np.linspace(-1.0, 1.0, tile + 1)
    xv, yv = np.meshgrid(xs, ys)
    base = 50.0 * np.exp(-(xv ** 2 + yv ** 2) * 2.0)
    noise = rng.standard_normal((tile + 1, tile + 1)) * 1.5
    return (base + noise).astype(np.float64)


def _make_stack(tile: int = 32) -> TerrainMaskStack:
    h = _make_height(tile)
    stack = TerrainMaskStack(
        tile_size=tile,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=h,
    )
    terrain_masks.compute_base_masks(h, 1.0, (0, 0), stack=stack, pass_name="test")
    return stack


def _make_intent(
    *,
    vantages=(),
    hero_features=(),
    framing_clearance=3.0,
) -> TerrainIntentState:
    return TerrainIntentState(
        seed=1234,
        region_bounds=BBox(0.0, 0.0, 32.0, 32.0),
        tile_size=32,
        cell_size=1.0,
        hero_feature_specs=tuple(hero_features),
        composition_hints={
            "vantages": list(vantages),
            "framing_clearance_m": framing_clearance,
        },
        scene_read=TerrainSceneRead(
            timestamp=0.0,
            major_landforms=("hill",),
            focal_point=(16.0, 16.0, 50.0),
            hero_features_present=(),
            hero_features_missing=(),
            waterfall_chains=(),
            cave_candidates=(),
            protected_zones_in_region=(),
            edit_scope=BBox(0.0, 0.0, 32.0, 32.0),
            success_criteria=(),
            reviewer="test",
        ),
    )


def _make_state(stack: TerrainMaskStack, intent: TerrainIntentState) -> TerrainPipelineState:
    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# Saliency tests
# ---------------------------------------------------------------------------


class TestSaliency:
    def test_compute_vantage_silhouettes_shape(self):
        from blender_addon.handlers.terrain_saliency import compute_vantage_silhouettes

        stack = _make_stack()
        vantages = [(0.0, 0.0, 60.0), (30.0, 30.0, 60.0)]
        s = compute_vantage_silhouettes(stack, vantages, ray_count=32)
        assert s.shape == (2, 32)
        assert s.dtype == np.float64
        assert np.all(s >= 0.0)

    def test_compute_vantage_silhouettes_empty(self):
        from blender_addon.handlers.terrain_saliency import compute_vantage_silhouettes

        stack = _make_stack()
        s = compute_vantage_silhouettes(stack, [], ray_count=16)
        assert s.shape == (0, 16)

    def test_auto_sculpt_positive_kind(self):
        from blender_addon.handlers.terrain_saliency import auto_sculpt_around_feature

        stack = _make_stack()
        delta = auto_sculpt_around_feature(stack, (16.0, 16.0, 50.0), "pinnacle", 10.0)
        # Max is at the feature center region — must be positive
        assert float(delta.max()) > 0.0
        assert float(delta.min()) >= 0.0

    def test_auto_sculpt_negative_kind(self):
        from blender_addon.handlers.terrain_saliency import auto_sculpt_around_feature

        stack = _make_stack()
        delta = auto_sculpt_around_feature(stack, (16.0, 16.0, 50.0), "canyon", 15.0)
        assert float(delta.min()) < 0.0

    def test_pass_saliency_refine_noop_without_vantages(self):
        from blender_addon.handlers.terrain_saliency import pass_saliency_refine

        stack = _make_stack()
        intent = _make_intent(vantages=())
        state = _make_state(stack, intent)
        before = stack.saliency_macro.copy()
        result = pass_saliency_refine(state, None)
        assert result.status == "ok"
        assert result.metrics.get("noop") is True
        np.testing.assert_array_equal(stack.saliency_macro, before)

    def test_pass_saliency_refine_changes_with_vantages(self):
        from blender_addon.handlers.terrain_saliency import pass_saliency_refine

        stack = _make_stack()
        intent = _make_intent(vantages=[(0.0, 0.0, 70.0), (32.0, 32.0, 70.0)])
        state = _make_state(stack, intent)
        before = stack.saliency_macro.copy()
        result = pass_saliency_refine(state, None)
        assert result.status == "ok"
        assert result.metrics["vantage_count"] == 2
        # Should modify saliency meaningfully
        assert not np.allclose(stack.saliency_macro, before)
        assert stack.saliency_macro.max() <= 1.0
        assert stack.saliency_macro.min() >= 0.0

    def test_register_saliency_pass(self):
        from blender_addon.handlers.terrain_pipeline import TerrainPassController
        from blender_addon.handlers.terrain_saliency import register_saliency_pass

        TerrainPassController.clear_registry()
        register_saliency_pass()
        assert "saliency_refine" in TerrainPassController.PASS_REGISTRY
        TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# Morphology tests
# ---------------------------------------------------------------------------


class TestMorphology:
    def test_default_templates_count(self):
        from blender_addon.handlers.terrain_morphology import DEFAULT_TEMPLATES

        assert len(DEFAULT_TEMPLATES) >= 30
        # Ensure we have the 6 required kinds
        kinds = {t.kind for t in DEFAULT_TEMPLATES}
        for k in ("ridge_spur", "canyon", "mesa", "pinnacle", "spur", "valley"):
            assert k in kinds, f"missing kind {k}"

    def test_template_ids_unique(self):
        from blender_addon.handlers.terrain_morphology import DEFAULT_TEMPLATES

        ids = [t.template_id for t in DEFAULT_TEMPLATES]
        assert len(ids) == len(set(ids))

    def test_apply_ridge_produces_positive_delta(self):
        from blender_addon.handlers.terrain_morphology import (
            DEFAULT_TEMPLATES,
            apply_morphology_template,
        )

        stack = _make_stack(tile=48)
        ridge = next(t for t in DEFAULT_TEMPLATES if t.kind == "ridge_spur")
        delta = apply_morphology_template(stack, ridge, (24.0, 24.0, 50.0), seed=42)
        assert delta.shape == stack.height.shape
        assert float(delta.max()) > 0.0

    def test_apply_canyon_produces_negative_delta(self):
        from blender_addon.handlers.terrain_morphology import (
            DEFAULT_TEMPLATES,
            apply_morphology_template,
        )

        stack = _make_stack(tile=48)
        canyon = next(t for t in DEFAULT_TEMPLATES if t.kind == "canyon")
        delta = apply_morphology_template(stack, canyon, (24.0, 24.0, 50.0), seed=42)
        assert float(delta.min()) < 0.0

    def test_template_deterministic(self):
        from blender_addon.handlers.terrain_morphology import (
            DEFAULT_TEMPLATES,
            apply_morphology_template,
        )

        stack = _make_stack(tile=32)
        t = DEFAULT_TEMPLATES[0]
        d1 = apply_morphology_template(stack, t, (16.0, 16.0, 50.0), seed=100)
        d2 = apply_morphology_template(stack, t, (16.0, 16.0, 50.0), seed=100)
        np.testing.assert_array_equal(d1, d2)

    def test_list_templates_for_biome(self):
        from blender_addon.handlers.terrain_morphology import list_templates_for_biome

        alpine = list_templates_for_biome("alpine")
        desert = list_templates_for_biome("desert")
        unknown = list_templates_for_biome("???")
        assert len(alpine) > 0
        assert len(desert) > 0
        # Desert should contain at least one mesa
        assert any(t.kind == "mesa" for t in desert)
        # Unknown returns the full catalog
        assert len(unknown) >= 30


# ---------------------------------------------------------------------------
# Framing tests
# ---------------------------------------------------------------------------


class TestFraming:
    def test_enforce_sightline_nonzero_for_obstructed(self):
        from blender_addon.handlers.terrain_framing import enforce_sightline

        stack = _make_stack(tile=48)
        # Vantage at low altitude looking at a target across the hill crest
        delta = enforce_sightline(stack, (4.0, 24.0, 20.0), (44.0, 24.0, 20.0), clearance_m=2.0)
        assert delta.shape == stack.height.shape
        # Should cut something (hill in the middle is ~50m tall)
        assert float(delta.min()) < 0.0

    def test_enforce_sightline_zero_for_coincident(self):
        from blender_addon.handlers.terrain_framing import enforce_sightline

        stack = _make_stack()
        delta = enforce_sightline(stack, (5.0, 5.0, 10.0), (5.0, 5.0, 10.0), clearance_m=2.0)
        assert float(np.abs(delta).max()) == 0.0

    def test_pass_framing_noop_when_no_features(self):
        from blender_addon.handlers.terrain_framing import pass_framing

        stack = _make_stack()
        intent = _make_intent(vantages=[(0.0, 0.0, 20.0)], hero_features=())
        state = _make_state(stack, intent)
        before = stack.height.copy()
        result = pass_framing(state, None)
        assert result.status == "ok"
        assert result.metrics.get("noop") is True
        np.testing.assert_array_equal(stack.height, before)

    def test_pass_framing_cuts_obstacles(self):
        from blender_addon.handlers.terrain_framing import pass_framing

        stack = _make_stack(tile=48)
        hero = HeroFeatureSpec(
            feature_id="h1",
            feature_kind="pinnacle",
            world_position=(44.0, 24.0, 20.0),
        )
        intent = _make_intent(
            vantages=[(4.0, 24.0, 20.0)],
            hero_features=(hero,),
            framing_clearance=3.0,
        )
        state = _make_state(stack, intent)
        before = stack.height.copy()
        result = pass_framing(state, None)
        assert result.status == "ok"
        assert result.metrics["sightlines_applied"] == 1
        assert result.metrics["max_cut_m"] >= 0.0
        # Height must not have risen anywhere
        assert float((stack.height - before).max()) <= 1e-9

    def test_register_framing_pass(self):
        from blender_addon.handlers.terrain_framing import register_framing_pass
        from blender_addon.handlers.terrain_pipeline import TerrainPassController

        TerrainPassController.clear_registry()
        register_framing_pass()
        assert "framing" in TerrainPassController.PASS_REGISTRY
        TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# Hierarchy tests
# ---------------------------------------------------------------------------


class TestHierarchy:
    def test_feature_tier_from_str(self):
        from blender_addon.handlers.terrain_hierarchy import FeatureTier

        assert FeatureTier.from_str("primary") == FeatureTier.PRIMARY
        assert FeatureTier.from_str("AMBIENT") == FeatureTier.AMBIENT
        assert FeatureTier.from_str("nonsense") == FeatureTier.SECONDARY

    def test_classify_cinematic_kind_forced_primary(self):
        from blender_addon.handlers.terrain_hierarchy import FeatureTier, classify_feature_tier

        f = HeroFeatureSpec(
            feature_id="c",
            feature_kind="canyon",
            world_position=(1.0, 1.0, 1.0),
            tier="tertiary",
        )
        tier = classify_feature_tier(f)
        assert tier == FeatureTier.PRIMARY

    def test_classify_saliency_promotion(self):
        from blender_addon.handlers.terrain_hierarchy import FeatureTier, classify_feature_tier

        stack = _make_stack()
        # Force saliency high at a known position
        stack.saliency_macro[16, 16] = 0.95
        f = HeroFeatureSpec(
            feature_id="s",
            feature_kind="spire",
            world_position=(16.0, 16.0, 50.0),
            tier="tertiary",
        )
        tier = classify_feature_tier(f, stack=stack)
        # Expect promotion from tertiary -> secondary
        assert tier in (FeatureTier.SECONDARY, FeatureTier.PRIMARY)

    def test_enforce_feature_budget_prunes(self):
        from blender_addon.handlers.terrain_hierarchy import (
            DEFAULT_BUDGETS,
            FeatureTier,
            enforce_feature_budget,
        )

        features = [
            {"feature_id": f"f{i}", "footprint_m": 50.0} for i in range(50)
        ]
        pruned = enforce_feature_budget(features, DEFAULT_BUDGETS[FeatureTier.PRIMARY])
        # Primary tier max is 0.5 per km² -> rounds to 1
        assert len(pruned) <= 1

    def test_enforce_feature_budget_drops_oversized(self):
        from blender_addon.handlers.terrain_hierarchy import (
            DEFAULT_BUDGETS,
            FeatureTier,
            enforce_feature_budget,
        )

        features = [
            {"feature_id": "small", "footprint_m": 20.0},
            {"feature_id": "giant", "footprint_m": 9999.0},
        ]
        pruned = enforce_feature_budget(features, DEFAULT_BUDGETS[FeatureTier.AMBIENT])
        ids = {f["feature_id"] for f in pruned}
        assert "giant" not in ids
        assert "small" in ids


# ---------------------------------------------------------------------------
# Rhythm tests
# ---------------------------------------------------------------------------


class TestRhythm:
    def test_empty_rhythm(self):
        from blender_addon.handlers.terrain_rhythm import analyze_feature_rhythm

        bounds = BBox(0.0, 0.0, 1000.0, 1000.0)
        result = analyze_feature_rhythm([], bounds)
        assert result["count"] == 0
        assert result["rhythm"] == 0.0

    def test_regular_grid_has_high_rhythm(self):
        from blender_addon.handlers.terrain_rhythm import analyze_feature_rhythm

        # 5x5 perfect grid
        pts = [(float(x * 100), float(y * 100)) for x in range(5) for y in range(5)]
        bounds = BBox(0.0, 0.0, 500.0, 500.0)
        result = analyze_feature_rhythm(pts, bounds)
        # Perfectly regular grid nn distances are all equal -> cv ~0 -> rhythm ~1
        assert result["rhythm"] > 0.9

    def test_random_has_lower_rhythm(self):
        from blender_addon.handlers.terrain_rhythm import analyze_feature_rhythm

        rng = np.random.default_rng(99)
        pts = [(float(x), float(y)) for x, y in rng.uniform(0, 500, size=(25, 2))]
        bounds = BBox(0.0, 0.0, 500.0, 500.0)
        result = analyze_feature_rhythm(pts, bounds)
        assert result["rhythm"] < 0.9

    def test_enforce_rhythm_with_dicts(self):
        from blender_addon.handlers.terrain_rhythm import enforce_rhythm

        rng = np.random.default_rng(5)
        features = [
            {"feature_id": f"f{i}", "world_position": (float(x), float(y), 0.0)}
            for i, (x, y) in enumerate(rng.uniform(0, 200, size=(10, 2)))
        ]
        out = enforce_rhythm(features)
        assert len(out) == len(features)
        assert all("world_position" in f for f in out)

    def test_validate_rhythm_flags_random(self):
        from blender_addon.handlers.terrain_rhythm import validate_rhythm

        rng = np.random.default_rng(1)
        pts = [(float(x), float(y)) for x, y in rng.uniform(0, 500, size=(30, 2))]
        bounds = BBox(0.0, 0.0, 500.0, 500.0)
        issues = validate_rhythm(pts, bounds, min_rhythm=0.99)
        assert len(issues) >= 1
        assert issues[0].code == "rhythm.too_random"


# ---------------------------------------------------------------------------
# Negative space tests
# ---------------------------------------------------------------------------


class TestNegativeSpace:
    def test_compute_quiet_zone_ratio_empty(self):
        from blender_addon.handlers.terrain_negative_space import compute_quiet_zone_ratio

        tile = 16
        stack = TerrainMaskStack(
            tile_size=tile,
            cell_size=1.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            tile_x=0,
            tile_y=0,
            height=np.zeros((tile + 1, tile + 1), dtype=np.float64),
        )
        # No saliency_macro yet -> 0
        assert compute_quiet_zone_ratio(stack) == 0.0

    def test_quiet_zone_ratio_with_saliency(self):
        from blender_addon.handlers.terrain_negative_space import compute_quiet_zone_ratio

        stack = _make_stack()
        stack.saliency_macro = np.zeros_like(stack.saliency_macro)
        stack.saliency_macro[:16, :] = 0.9  # half busy
        ratio = compute_quiet_zone_ratio(stack)
        assert ratio == pytest.approx(
            (stack.saliency_macro < 0.3).sum() / stack.saliency_macro.size
        )

    def test_enforce_quiet_zone_meets_min_ratio(self):
        from blender_addon.handlers.terrain_negative_space import enforce_quiet_zone

        stack = _make_stack()
        # Force everything busy
        stack.saliency_macro = np.ones_like(stack.saliency_macro) * 0.9
        mask = enforce_quiet_zone(stack, min_ratio=0.5)
        assert mask.dtype == bool
        assert mask.sum() / mask.size >= 0.5

    def test_validate_negative_space_passes_when_quiet(self):
        from blender_addon.handlers.terrain_negative_space import validate_negative_space

        stack = _make_stack()
        stack.saliency_macro = np.zeros_like(stack.saliency_macro)
        issues = validate_negative_space(stack, min_ratio=0.4)
        # A fully quiet saliency map must not trip any validator:
        # no insufficient quiet zone, no density budget overflow, no
        # peak-spacing violation (there are no peaks at all).
        assert issues == []

    def test_validate_negative_space_flags_busy(self):
        from blender_addon.handlers.terrain_negative_space import validate_negative_space

        stack = _make_stack()
        stack.saliency_macro = np.ones_like(stack.saliency_macro) * 0.9
        issues = validate_negative_space(stack, min_ratio=0.4)
        # A fully busy map trips quiet-zone, feature-density, AND
        # peak-spacing validators — all three signals are legitimate
        # for a "wall of detail" scene.
        codes = {i.code for i in issues}
        assert "negative_space.insufficient" in codes
        assert "negative_space.feature_density_too_high" in codes
        assert "negative_space.peaks_too_close" in codes
