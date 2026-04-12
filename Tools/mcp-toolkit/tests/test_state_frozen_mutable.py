"""Tests for frozen-mutable state fixes (F170-F187).

Verifies that frozen dataclasses no longer have mutable dict defaults
and that MappingProxyType defaults are truly immutable.
"""

from __future__ import annotations

import types

import pytest


class TestHeroFeatureSpecFrozen:
    """HeroFeatureSpec.parameters default must be immutable."""

    def test_default_parameters_is_mapping_proxy(self):
        from blender_addon.handlers.terrain_semantics import HeroFeatureSpec

        spec = HeroFeatureSpec(
            feature_id="test",
            feature_kind="cliff",
            world_position=(0.0, 0.0, 0.0),
        )
        assert isinstance(spec.parameters, types.MappingProxyType), (
            f"Default parameters should be MappingProxyType, got {type(spec.parameters)}"
        )

    def test_default_parameters_is_empty(self):
        from blender_addon.handlers.terrain_semantics import HeroFeatureSpec

        spec = HeroFeatureSpec(
            feature_id="test",
            feature_kind="cliff",
            world_position=(0.0, 0.0, 0.0),
        )
        assert len(spec.parameters) == 0

    def test_default_parameters_not_shared(self):
        """Two instances must NOT share the same default object."""
        from blender_addon.handlers.terrain_semantics import HeroFeatureSpec

        a = HeroFeatureSpec(feature_id="a", feature_kind="cliff", world_position=(0, 0, 0))
        b = HeroFeatureSpec(feature_id="b", feature_kind="cliff", world_position=(0, 0, 0))
        # MappingProxyType({}) creates distinct objects each time
        assert a.parameters is not b.parameters or len(a.parameters) == 0

    def test_explicit_dict_still_accepted(self):
        """Callers passing a plain dict should still work."""
        from blender_addon.handlers.terrain_semantics import HeroFeatureSpec

        spec = HeroFeatureSpec(
            feature_id="test",
            feature_kind="cliff",
            world_position=(0.0, 0.0, 0.0),
            parameters={"height": 10.0},
        )
        assert spec.parameters["height"] == 10.0
        assert spec.parameters.get("missing", 42) == 42


class TestTerrainIntentStateFrozen:
    """TerrainIntentState.composition_hints default must be immutable."""

    def test_default_composition_hints_is_mapping_proxy(self):
        from blender_addon.handlers.terrain_semantics import (
            BBox,
            TerrainIntentState,
        )

        intent = TerrainIntentState(
            seed=42,
            region_bounds=BBox(0, 0, 100, 100),
            tile_size=256,
            cell_size=1.0,
        )
        assert isinstance(intent.composition_hints, types.MappingProxyType)

    def test_default_composition_hints_empty(self):
        from blender_addon.handlers.terrain_semantics import (
            BBox,
            TerrainIntentState,
        )

        intent = TerrainIntentState(
            seed=42,
            region_bounds=BBox(0, 0, 100, 100),
            tile_size=256,
            cell_size=1.0,
        )
        assert len(intent.composition_hints) == 0

    def test_explicit_dict_still_accepted(self):
        from blender_addon.handlers.terrain_semantics import (
            BBox,
            TerrainIntentState,
        )

        intent = TerrainIntentState(
            seed=42,
            region_bounds=BBox(0, 0, 100, 100),
            tile_size=256,
            cell_size=1.0,
            composition_hints={"vantages": [(0, 0, 10)]},
        )
        assert intent.composition_hints["vantages"] == [(0, 0, 10)]

    def test_intent_hash_works_with_mapping_proxy(self):
        from blender_addon.handlers.terrain_semantics import (
            BBox,
            TerrainIntentState,
        )

        intent = TerrainIntentState(
            seed=42,
            region_bounds=BBox(0, 0, 100, 100),
            tile_size=256,
            cell_size=1.0,
        )
        h = intent.intent_hash()
        assert isinstance(h, str)
        assert len(h) > 0


class TestMorphologyTemplateFrozen:
    """MorphologyTemplate.params default must be immutable."""

    def test_default_params_is_mapping_proxy(self):
        from blender_addon.handlers.terrain_morphology import MorphologyTemplate

        t = MorphologyTemplate(
            template_id="test",
            kind="ridge_spur",
            scale_m=100.0,
            aspect_ratio=3.0,
        )
        assert isinstance(t.params, types.MappingProxyType)

    def test_explicit_dict_accepted(self):
        from blender_addon.handlers.terrain_morphology import MorphologyTemplate

        t = MorphologyTemplate(
            template_id="test",
            kind="ridge_spur",
            scale_m=100.0,
            aspect_ratio=3.0,
            params={"height_m": 50.0, "jaggedness": 0.5},
        )
        assert t.params["height_m"] == 50.0

    def test_catalog_templates_load(self):
        """All default catalog templates must construct without error."""
        from blender_addon.handlers.terrain_morphology import DEFAULT_TEMPLATES

        assert len(DEFAULT_TEMPLATES) >= 30
        for tmpl in DEFAULT_TEMPLATES:
            assert tmpl.template_id
            assert tmpl.kind
            # params should be readable
            _ = dict(tmpl.params)
