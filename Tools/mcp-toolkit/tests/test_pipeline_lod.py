"""Unit tests for LOD handler pure-logic helpers.

Tests _validate_lod_ratios and _build_lod_name without Blender.
"""

import pytest


# ---------------------------------------------------------------------------
# _validate_lod_ratios tests
# ---------------------------------------------------------------------------


class TestValidateLodRatios:
    """Test LOD ratio validation logic."""

    def test_valid_standard_ratios(self):
        """Standard [1.0, 0.5, 0.25, 0.1] ratios are valid."""
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        assert _validate_lod_ratios([1.0, 0.5, 0.25, 0.1]) is True

    def test_single_ratio_is_valid(self):
        """A single LOD ratio [1.0] is valid."""
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        assert _validate_lod_ratios([1.0]) is True

    def test_non_descending_raises_error(self):
        """[0.5, 1.0] raises ValueError -- not descending."""
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match="descending"):
            _validate_lod_ratios([0.5, 1.0])

    def test_equal_values_raise_error(self):
        """[1.0, 1.0] raises ValueError -- must be strictly descending."""
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match="descending"):
            _validate_lod_ratios([1.0, 1.0])

    def test_empty_list_raises_error(self):
        """Empty ratios list raises ValueError."""
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match="At least one"):
            _validate_lod_ratios([])

    def test_zero_ratio_raises_error(self):
        """Ratio of 0.0 raises ValueError -- must be > 0."""
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match="ratio must be"):
            _validate_lod_ratios([1.0, 0.0])

    def test_ratio_above_one_raises_error(self):
        """Ratio > 1.0 raises ValueError."""
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match="ratio must be"):
            _validate_lod_ratios([1.5, 1.0])


# ---------------------------------------------------------------------------
# _build_lod_name tests
# ---------------------------------------------------------------------------


class TestBuildLodName:
    """Test LOD naming convention."""

    def test_lod0_naming(self):
        """LOD0 follows {name}_LOD0 pattern."""
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        assert _build_lod_name("Barrel", 0) == "Barrel_LOD0"

    def test_lod3_naming(self):
        """LOD3 follows {name}_LOD3 pattern."""
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        assert _build_lod_name("Barrel", 3) == "Barrel_LOD3"

    def test_name_with_underscores(self):
        """Names with underscores still follow the pattern."""
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        assert _build_lod_name("Dark_Sword", 1) == "Dark_Sword_LOD1"

    def test_sequential_lod_names_are_unique(self):
        """All LOD names for a given object are unique."""
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        names = [_build_lod_name("Weapon", i) for i in range(4)]
        assert len(set(names)) == 4
