"""Tests for phase 58-01 cleanup: silent swallows, frozen-mutable, Bundle H wiring,
side-effect retrieval.

Every test must FAIL if the corresponding fix is reverted.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import logging
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HANDLERS_DIR = Path(__file__).resolve().parent.parent / "blender_addon" / "handlers"


# ===========================================================================
# Cluster A: Silent swallows now log
# ===========================================================================


class TestSilentSwallowsReplaced:
    """Verify that bare `except Exception: pass` has been replaced with logging."""

    MODULES_WITH_LOGGING = [
        "terrain_addon_health",
        "terrain_banded",
        "terrain_checkpoints",
        "terrain_checkpoints_ext",
        "terrain_hot_reload",
        "terrain_region_exec",
        "terrain_golden_snapshots",
        "terrain_waterfalls",
    ]

    @pytest.mark.parametrize("module_name", MODULES_WITH_LOGGING)
    def test_module_has_logger(self, module_name: str) -> None:
        """Every fixed module must declare a module-level logger."""
        src = (HANDLERS_DIR / f"{module_name}.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        has_logger = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "logger":
                        has_logger = True
        assert has_logger, f"{module_name}.py must define module-level `logger`"

    @pytest.mark.parametrize("module_name", MODULES_WITH_LOGGING)
    def test_no_bare_except_pass(self, module_name: str) -> None:
        """No `except Exception: pass` without a logging call or explanatory comment."""
        src = (HANDLERS_DIR / f"{module_name}.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if body is just `pass` with no preceding logger call
                body = node.body
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    # This is a bare except: pass — should not exist in fixed modules
                    pytest.fail(
                        f"{module_name}.py line {node.lineno}: bare `except: pass` found"
                    )


# ===========================================================================
# Cluster B: Frozen-mutable fix in MorphologyTemplate
# ===========================================================================


class TestFrozenMutableFix:
    def test_morphology_params_is_immutable_mapping(self) -> None:
        """MorphologyTemplate.params must use an immutable Mapping type."""
        from blender_addon.handlers.terrain_morphology import MorphologyTemplate

        t = MorphologyTemplate("test", "ridge_spur", 100.0, 3.0)
        # Default params should be a MappingProxyType (read-only)
        with pytest.raises(TypeError):
            t.params["new_key"] = "value"  # type: ignore[index]

    def test_morphology_params_accepts_dict_at_construction(self) -> None:
        """Callers can still pass a plain dict — it's stored as-is (Mapping supertype)."""
        from blender_addon.handlers.terrain_morphology import MorphologyTemplate

        t = MorphologyTemplate("test", "ridge_spur", 100.0, 3.0, {"height_m": 50.0})
        assert t.params["height_m"] == 50.0

    def test_default_templates_load(self) -> None:
        """DEFAULT_TEMPLATES must load without error and contain 30+ entries."""
        from blender_addon.handlers.terrain_morphology import DEFAULT_TEMPLATES

        assert len(DEFAULT_TEMPLATES) >= 30


# ===========================================================================
# Cluster D: Bundle H wiring
# ===========================================================================


class TestBundleHWiring:
    def test_hierarchy_has_register_function(self) -> None:
        from blender_addon.handlers.terrain_hierarchy import register_bundle_h_hierarchy

        assert callable(register_bundle_h_hierarchy)
        register_bundle_h_hierarchy()  # no-op, should not raise

    def test_rhythm_has_register_function(self) -> None:
        from blender_addon.handlers.terrain_rhythm import register_bundle_h_rhythm

        assert callable(register_bundle_h_rhythm)
        register_bundle_h_rhythm()

    def test_negative_space_has_register_function(self) -> None:
        from blender_addon.handlers.terrain_negative_space import (
            register_bundle_h_negative_space,
        )

        assert callable(register_bundle_h_negative_space)
        register_bundle_h_negative_space()

    def test_master_registrar_lists_bundle_h_modules(self) -> None:
        """Master registrar must reference all 5 Bundle H sub-modules."""
        src = (HANDLERS_DIR / "terrain_master_registrar.py").read_text(encoding="utf-8")
        for label in ["H-saliency", "H-framing", "H-hierarchy", "H-rhythm", "H-negative_space"]:
            assert label in src, f"Master registrar missing Bundle {label}"

    def test_validation_suite_includes_negative_space(self) -> None:
        from blender_addon.handlers.terrain_validation import DEFAULT_VALIDATORS

        names = [name for name, _ in DEFAULT_VALIDATORS]
        assert "validate_negative_space" in names

    def test_validation_suite_includes_feature_rhythm(self) -> None:
        from blender_addon.handlers.terrain_validation import DEFAULT_VALIDATORS

        names = [name for name, _ in DEFAULT_VALIDATORS]
        assert "validate_feature_rhythm" in names

    def test_negative_space_adapter_skips_without_saliency(self) -> None:
        """Adapter must return [] when saliency_macro is None."""
        from blender_addon.handlers.terrain_validation import (
            _validate_negative_space_adapter,
        )
        from blender_addon.handlers.terrain_semantics import (
            BBox,
            TerrainIntentState,
            TerrainMaskStack,
        )

        stack = TerrainMaskStack(
            height=np.zeros((64, 64), dtype=np.float32),
            tile_size=64, cell_size=1.0,
            world_origin_x=0.0, world_origin_y=0.0,
            tile_x=0, tile_y=0,
        )
        intent = TerrainIntentState(
            seed=42,
            region_bounds=BBox(min_x=0, min_y=0, max_x=64, max_y=64),
            tile_size=64, cell_size=1.0,
        )
        assert stack.saliency_macro is None
        issues = _validate_negative_space_adapter(stack, intent)
        assert issues == []


# ===========================================================================
# Cluster E: Side-effect retrieval
# ===========================================================================


class TestBandedCacheRetrieval:
    def test_get_banded_cache_returns_none_without_cache(self) -> None:
        from blender_addon.handlers.terrain_banded import get_banded_cache

        state = types.SimpleNamespace()
        assert get_banded_cache(state) is None

    def test_get_banded_cache_returns_cache_when_present(self) -> None:
        from blender_addon.handlers.terrain_banded import get_banded_cache

        sentinel = {"token": MagicMock()}
        state = types.SimpleNamespace(banded_cache=sentinel)
        assert get_banded_cache(state) is sentinel

    def test_get_banded_cache_returns_none_for_empty_dict(self) -> None:
        """Empty dict is falsy — should return None to indicate no data."""
        from blender_addon.handlers.terrain_banded import get_banded_cache

        state = types.SimpleNamespace(banded_cache={})
        assert get_banded_cache(state) is None

    def test_get_banded_cache_in_all(self) -> None:
        """get_banded_cache must be exported in __all__."""
        from blender_addon.handlers import terrain_banded

        assert "get_banded_cache" in terrain_banded.__all__
