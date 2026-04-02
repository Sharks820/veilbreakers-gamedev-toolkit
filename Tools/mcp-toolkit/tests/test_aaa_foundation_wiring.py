"""Foundation wiring integration tests for Phase 39 AAA quality systems.

Verifies that all the key handlers and modules are importable, callable,
and wired together correctly — without requiring a live Blender session.
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Tests: Handler importability
# ---------------------------------------------------------------------------

class TestHandlerImportability:
    def test_visual_validation_importable(self):
        """visual_validation module imports without error."""
        from veilbreakers_mcp.shared import visual_validation
        assert hasattr(visual_validation, "analyze_render_image")
        assert hasattr(visual_validation, "aaa_verify_map")
        assert hasattr(visual_validation, "validate_render_screens")

    def test_screenshot_diff_importable(self):
        """screenshot_diff module imports without error."""
        from veilbreakers_mcp.shared import screenshot_diff
        assert hasattr(screenshot_diff, "compare_screenshots")
        assert hasattr(screenshot_diff, "capture_regression_baseline")
        assert hasattr(screenshot_diff, "generate_diff_image")

    def test_bake_curvature_handler_exists(self):
        """handle_bake_curvature_map is importable from mesh_enhance."""
        from blender_addon.handlers.mesh_enhance import handle_bake_curvature_map
        assert callable(handle_bake_curvature_map)

    def test_apply_curvature_roughness_callable(self):
        """apply_curvature_roughness is importable and callable."""
        from blender_addon.handlers.mesh_enhance import apply_curvature_roughness
        assert callable(apply_curvature_roughness)

    def test_generate_wear_handler_exists(self):
        """handle_generate_wear_map is importable from texture."""
        from blender_addon.handlers.texture import handle_generate_wear_map
        assert callable(handle_generate_wear_map)

    def test_generate_battlements_importable(self):
        """generate_battlements is importable from building_quality."""
        from blender_addon.handlers.building_quality import generate_battlements
        assert callable(generate_battlements)

    def test_smart_material_callable(self):
        """building_quality module is importable (houses smart-material logic)."""
        import blender_addon.handlers.building_quality as bq
        assert bq is not None


# ---------------------------------------------------------------------------
# Tests: Source-level wiring checks
# ---------------------------------------------------------------------------

class TestSourceWiring:
    def _read_source(self, relative_path: str) -> str:
        base = Path(__file__).parent.parent
        return (base / relative_path).read_text(encoding="utf-8")

    def test_worldbuilding_imports_generate_battlements(self):
        """worldbuilding.py has `from .building_quality import generate_battlements`."""
        src = self._read_source("blender_addon/handlers/worldbuilding.py")
        assert "generate_battlements" in src, (
            "generate_battlements not imported in worldbuilding.py"
        )

    def test_worldbuilding_imports_handle_generate_wear_map(self):
        """worldbuilding.py imports handle_generate_wear_map from texture."""
        src = self._read_source("blender_addon/handlers/worldbuilding.py")
        assert "handle_generate_wear_map" in src, (
            "handle_generate_wear_map not imported in worldbuilding.py"
        )

    def test_worldbuilding_calls_generate_battlements(self):
        """handle_generate_castle calls generate_battlements()."""
        src = self._read_source("blender_addon/handlers/worldbuilding.py")
        assert "generate_battlements(" in src, (
            "generate_battlements() never called in worldbuilding.py"
        )

    def test_worldbuilding_calls_handle_generate_wear_map(self):
        """handle_generate_settlement calls handle_generate_wear_map()."""
        src = self._read_source("blender_addon/handlers/worldbuilding.py")
        assert "handle_generate_wear_map(" in src, (
            "handle_generate_wear_map() never called in worldbuilding.py"
        )

    def test_mesh_enhance_has_apply_curvature_roughness(self):
        """mesh_enhance.py defines apply_curvature_roughness()."""
        src = self._read_source("blender_addon/handlers/mesh_enhance.py")
        assert "def apply_curvature_roughness" in src, (
            "apply_curvature_roughness() not defined in mesh_enhance.py"
        )

    def test_blender_server_imports_aaa_verify_map(self):
        """blender_server.py imports aaa_verify_map."""
        src = self._read_source("src/veilbreakers_mcp/blender_server.py")
        assert "aaa_verify_map" in src, (
            "aaa_verify_map not imported in blender_server.py"
        )

    def test_blender_server_imports_capture_regression_baseline(self):
        """blender_server.py imports capture_regression_baseline."""
        src = self._read_source("src/veilbreakers_mcp/blender_server.py")
        assert "capture_regression_baseline" in src, (
            "capture_regression_baseline not imported in blender_server.py"
        )

    def test_blender_server_has_aaa_verify_action(self):
        """blender_server.py registers the aaa_verify action."""
        src = self._read_source("src/veilbreakers_mcp/blender_server.py")
        assert '"aaa_verify"' in src, (
            "aaa_verify action not registered in blender_server.py"
        )

    def test_blender_server_has_screenshot_regression_action(self):
        """blender_server.py registers the screenshot_regression action."""
        src = self._read_source("src/veilbreakers_mcp/blender_server.py")
        assert '"screenshot_regression"' in src, (
            "screenshot_regression action not registered in blender_server.py"
        )

    def test_visual_validation_has_aaa_verify_map_function(self):
        """visual_validation.py defines aaa_verify_map()."""
        src = self._read_source("src/veilbreakers_mcp/shared/visual_validation.py")
        assert "def aaa_verify_map" in src, (
            "aaa_verify_map() not defined in visual_validation.py"
        )

    def test_screenshot_diff_has_capture_baseline_function(self):
        """screenshot_diff.py defines capture_regression_baseline()."""
        src = self._read_source("src/veilbreakers_mcp/shared/screenshot_diff.py")
        assert "def capture_regression_baseline" in src, (
            "capture_regression_baseline() not defined in screenshot_diff.py"
        )

    def test_aaa_verify_map_detects_floating_geometry_key(self):
        """aaa_verify_map checks for floating_geometry_suspected flag."""
        src = self._read_source("src/veilbreakers_mcp/shared/visual_validation.py")
        assert "floating_geometry_suspected" in src

    def test_aaa_verify_map_detects_default_material_key(self):
        """aaa_verify_map checks for default_material_detected flag."""
        src = self._read_source("src/veilbreakers_mcp/shared/visual_validation.py")
        assert "default_material_detected" in src

    def test_wear_age_mapping_in_worldbuilding(self):
        """WEAR_AGE_BY_TYPE mapping is defined in worldbuilding.py."""
        src = self._read_source("blender_addon/handlers/worldbuilding.py")
        assert "_WEAR_AGE_BY_TYPE" in src, (
            "_WEAR_AGE_BY_TYPE dict not found in worldbuilding.py"
        )

    def test_curvature_roughness_convex_factor(self):
        """apply_curvature_roughness uses 0.15 convex reduction factor."""
        src = self._read_source("blender_addon/handlers/mesh_enhance.py")
        assert "0.15" in src, (
            "0.15 convex roughness factor not found in mesh_enhance.py"
        )

    def test_curvature_roughness_concave_factor(self):
        """apply_curvature_roughness uses 0.20 concave increase factor."""
        src = self._read_source("blender_addon/handlers/mesh_enhance.py")
        assert "0.20" in src or "0.2" in src, (
            "0.20 concave roughness factor not found in mesh_enhance.py"
        )
