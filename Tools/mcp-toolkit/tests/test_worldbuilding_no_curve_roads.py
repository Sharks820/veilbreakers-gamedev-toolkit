"""Test that road generation uses mesh roads, not curves -- Addendum 2 D.18."""
from __future__ import annotations

import inspect



class TestWorldbuildingNoCurveRoads:
    """Road generation must use mesh-based approach, not legacy curves."""

    def test_create_road_with_curbs_exists(self):
        """The mesh-based road function must exist."""
        from blender_addon.handlers import worldbuilding
        assert hasattr(worldbuilding, "_create_road_with_curbs"), (
            "_create_road_with_curbs not found -- mesh road function missing"
        )

    def test_create_curve_from_points_deprecated_or_absent(self):
        """Legacy _create_curve_from_points should be gone or deprecated."""
        from blender_addon.handlers import worldbuilding
        if hasattr(worldbuilding, "_create_curve_from_points"):
            source = inspect.getsource(worldbuilding._create_curve_from_points)
            assert "deprecated" in source.lower() or "legacy" in source.lower(), (
                "_create_curve_from_points exists without deprecation marker"
            )

    def test_road_generation_functions_exist(self):
        """Core road generation functions must be importable."""
        from blender_addon.handlers import worldbuilding
        # At minimum the module should have road-related functions
        road_funcs = [
            name for name in dir(worldbuilding)
            if "road" in name.lower() and callable(getattr(worldbuilding, name))
        ]
        assert len(road_funcs) >= 1, "No road generation functions found"
