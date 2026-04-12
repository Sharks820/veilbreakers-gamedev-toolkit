"""Tests for morphology template upgrades (55-03 Task 4).

Verifies new volcanic/glacial/karst templates, compose_morphology,
select_templates_for_terrain, and updated biome mappings.
"""

import numpy as np
import pytest

from blender_addon.handlers.terrain_semantics import (
    BBox,
    TerrainMaskStack,
)
from blender_addon.handlers.terrain_morphology import (
    DEFAULT_TEMPLATES,
    MorphologyTemplate,
    apply_morphology_template,
    compose_morphology,
    list_templates_for_biome,
    select_templates_for_terrain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stack(size: int = 32) -> TerrainMaskStack:
    rng = np.random.default_rng(42)
    height = rng.uniform(10.0, 50.0, size=(size, size)).astype(np.float64)
    return TerrainMaskStack(
        tile_size=size - 1,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )


# ---------------------------------------------------------------------------
# Template catalog
# ---------------------------------------------------------------------------


class TestTemplateCatalog:
    """Verify the expanded template catalog."""

    def test_at_least_45_templates(self):
        assert len(DEFAULT_TEMPLATES) >= 45

    def test_volcanic_templates_exist(self):
        volcanic = [t for t in DEFAULT_TEMPLATES if t.kind == "volcanic"]
        assert len(volcanic) >= 5

    def test_glacial_templates_exist(self):
        glacial = [t for t in DEFAULT_TEMPLATES if t.kind == "glacial"]
        assert len(glacial) >= 5

    def test_karst_templates_exist(self):
        karst = [t for t in DEFAULT_TEMPLATES if t.kind == "karst"]
        assert len(karst) >= 5

    def test_all_templates_have_valid_fields(self):
        for t in DEFAULT_TEMPLATES:
            assert t.template_id, f"Empty template_id"
            assert t.kind, f"Empty kind for {t.template_id}"
            assert t.scale_m > 0, f"Invalid scale for {t.template_id}"
            assert t.aspect_ratio >= 1.0, f"Invalid aspect for {t.template_id}"

    def test_unique_template_ids(self):
        ids = [t.template_id for t in DEFAULT_TEMPLATES]
        assert len(ids) == len(set(ids)), "Duplicate template IDs"


# ---------------------------------------------------------------------------
# apply_morphology_template for new kinds
# ---------------------------------------------------------------------------


class TestApplyNewTemplates:
    """New template kinds must produce non-zero height deltas."""

    def test_volcanic_caldera_produces_delta(self):
        stack = _make_stack()
        t = [t for t in DEFAULT_TEMPLATES if t.template_id == "volcanic_caldera"][0]
        pos = (16.0, 16.0, 30.0)
        delta = apply_morphology_template(stack, t, pos, seed=42)
        assert delta.shape == stack.height.shape
        assert np.abs(delta).max() > 1.0, "Caldera delta too small"

    def test_glacial_cirque_produces_depression(self):
        stack = _make_stack()
        t = [t for t in DEFAULT_TEMPLATES if t.template_id == "glacial_cirque"][0]
        pos = (16.0, 16.0, 30.0)
        delta = apply_morphology_template(stack, t, pos, seed=42)
        # Cirque should create a depression (negative sign)
        assert delta.min() < -1.0, "Cirque should produce negative delta"

    def test_karst_sinkhole_produces_depression(self):
        stack = _make_stack()
        t = [t for t in DEFAULT_TEMPLATES if t.template_id == "karst_sinkhole"][0]
        pos = (16.0, 16.0, 30.0)
        delta = apply_morphology_template(stack, t, pos, seed=42)
        assert delta.min() < -1.0, "Sinkhole should produce negative delta"

    def test_karst_tower_produces_peak(self):
        stack = _make_stack()
        t = [t for t in DEFAULT_TEMPLATES if t.template_id == "karst_tower"][0]
        pos = (16.0, 16.0, 30.0)
        delta = apply_morphology_template(stack, t, pos, seed=42)
        assert delta.max() > 1.0, "Tower should produce positive delta"

    def test_glacial_arete_produces_ridge(self):
        stack = _make_stack()
        t = [t for t in DEFAULT_TEMPLATES if t.template_id == "glacial_arete"][0]
        pos = (16.0, 16.0, 30.0)
        delta = apply_morphology_template(stack, t, pos, seed=42)
        assert delta.max() > 1.0, "Arete should produce positive delta"

    def test_volcanic_maar_produces_depression(self):
        stack = _make_stack()
        t = [t for t in DEFAULT_TEMPLATES if t.template_id == "volcanic_maar"][0]
        pos = (16.0, 16.0, 30.0)
        delta = apply_morphology_template(stack, t, pos, seed=42)
        # Maar is a depression (sign=-1)
        assert delta.min() < -1.0

    def test_karst_doline_field_has_multiple_depressions(self):
        stack = _make_stack(64)
        t = [t for t in DEFAULT_TEMPLATES if t.template_id == "karst_doline_field"][0]
        pos = (32.0, 32.0, 30.0)
        delta = apply_morphology_template(stack, t, pos, seed=42)
        # Multiple depressions: several local minima
        negative_cells = (delta < -0.5).sum()
        assert negative_cells > 5, "Doline field should have multiple depressions"

    def test_deterministic_with_seed(self):
        stack = _make_stack()
        t = DEFAULT_TEMPLATES[-1]  # Any template
        pos = (16.0, 16.0, 30.0)
        d1 = apply_morphology_template(stack, t, pos, seed=123)
        d2 = apply_morphology_template(stack, t, pos, seed=123)
        np.testing.assert_array_equal(d1, d2)


# ---------------------------------------------------------------------------
# compose_morphology
# ---------------------------------------------------------------------------


class TestComposeMorphology:
    """Multi-template composition must blend correctly."""

    def test_additive_mode_sums(self):
        stack = _make_stack()
        t1 = DEFAULT_TEMPLATES[0]  # ridge
        t2 = DEFAULT_TEMPLATES[5]  # canyon
        positions = [(10.0, 10.0, 30.0), (20.0, 20.0, 30.0)]
        composed = compose_morphology(stack, [t1, t2], positions, seed=42)
        assert composed.shape == stack.height.shape
        # Should have both positive and negative regions
        assert composed.max() > 0.5
        assert composed.min() < -0.5

    def test_max_mode_preserves_peaks(self):
        stack = _make_stack()
        t1 = DEFAULT_TEMPLATES[0]
        positions = [(16.0, 16.0, 30.0), (16.0, 16.0, 30.0)]
        additive = compose_morphology(stack, [t1, t1], positions, seed=42, blend_mode="additive")
        maxed = compose_morphology(stack, [t1, t1], positions, seed=42, blend_mode="max")
        # Max should be <= additive peak (same location, same template)
        assert maxed.max() <= additive.max() + 1e-6

    def test_global_scale(self):
        stack = _make_stack()
        t = DEFAULT_TEMPLATES[0]
        pos = [(16.0, 16.0, 30.0)]
        d1 = compose_morphology(stack, [t], pos, seed=42, global_scale=1.0)
        d2 = compose_morphology(stack, [t], pos, seed=42, global_scale=2.0)
        np.testing.assert_allclose(d2, d1 * 2.0, atol=1e-10)

    def test_mismatched_lengths_raises(self):
        stack = _make_stack()
        with pytest.raises(ValueError, match="same length"):
            compose_morphology(stack, [DEFAULT_TEMPLATES[0]], [], seed=42)

    def test_empty_input(self):
        stack = _make_stack()
        result = compose_morphology(stack, [], [], seed=42)
        assert np.all(result == 0.0)


# ---------------------------------------------------------------------------
# list_templates_for_biome (updated mappings)
# ---------------------------------------------------------------------------


class TestBiomeMappings:
    """New biome mappings must include volcanic/glacial/karst kinds."""

    def test_volcanic_biome_includes_volcanic(self):
        templates = list_templates_for_biome("volcanic")
        kinds = {t.kind for t in templates}
        assert "volcanic" in kinds

    def test_glacial_biome_includes_glacial(self):
        templates = list_templates_for_biome("glacial")
        kinds = {t.kind for t in templates}
        assert "glacial" in kinds

    def test_karst_biome_includes_karst(self):
        templates = list_templates_for_biome("karst")
        kinds = {t.kind for t in templates}
        assert "karst" in kinds

    def test_alpine_includes_glacial(self):
        templates = list_templates_for_biome("alpine")
        kinds = {t.kind for t in templates}
        assert "glacial" in kinds

    def test_unknown_biome_returns_all(self):
        templates = list_templates_for_biome("xyzzy")
        assert len(templates) == len(DEFAULT_TEMPLATES)


# ---------------------------------------------------------------------------
# select_templates_for_terrain
# ---------------------------------------------------------------------------


class TestSelectTemplatesForTerrain:
    """Terrain-aware template selection."""

    def test_returns_requested_count(self):
        stack = _make_stack()
        selections = select_templates_for_terrain(stack, max_templates=3, seed=42)
        assert len(selections) == 3

    def test_returns_template_and_position(self):
        stack = _make_stack()
        selections = select_templates_for_terrain(stack, max_templates=1, seed=42)
        tmpl, pos = selections[0]
        assert isinstance(tmpl, MorphologyTemplate)
        assert len(pos) == 3

    def test_positions_within_terrain_bounds(self):
        stack = _make_stack(64)
        selections = select_templates_for_terrain(stack, max_templates=5, seed=42)
        for tmpl, pos in selections:
            wx, wy, wz = pos
            assert wx >= stack.world_origin_x
            assert wx <= stack.world_origin_x + stack.tile_size * stack.cell_size
            assert wy >= stack.world_origin_y
            assert wy <= stack.world_origin_y + stack.tile_size * stack.cell_size

    def test_deterministic_with_seed(self):
        stack = _make_stack()
        s1 = select_templates_for_terrain(stack, max_templates=3, seed=42)
        s2 = select_templates_for_terrain(stack, max_templates=3, seed=42)
        assert [t.template_id for t, _ in s1] == [t.template_id for t, _ in s2]

    def test_biome_filter_applies(self):
        stack = _make_stack()
        selections = select_templates_for_terrain(
            stack, biome="volcanic", max_templates=5, seed=42,
        )
        kinds = {t.kind for t, _ in selections}
        # Should use templates from the volcanic biome pool
        allowed = {"volcanic", "canyon", "ridge_spur", "pinnacle"}
        assert kinds.issubset(allowed), f"Unexpected kinds {kinds - allowed}"
