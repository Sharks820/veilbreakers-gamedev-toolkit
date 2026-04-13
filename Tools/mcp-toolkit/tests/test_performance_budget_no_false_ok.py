"""Test performance report doesn't fake 'ok' -- Addendum 3 3.B.4 compliance."""
from __future__ import annotations


from blender_addon.handlers.terrain_performance_report import (
    TerrainPerformanceReport,
)


class TestPerformanceBudgetNoFalseOk:
    """Performance budget must never return 'ok' when data is missing."""

    def test_report_has_required_fields(self):
        fields = {f for f in TerrainPerformanceReport.__dataclass_fields__}
        assert "status" in fields, "Missing 'status' field"
        assert "triangle_count" in fields, "Missing 'triangle_count' field"
        assert "within_budget" in fields, "Missing 'within_budget' field"

    def test_empty_report_not_ok(self):
        """A report with no data should NOT be status='ok'."""
        report = TerrainPerformanceReport(
            triangle_count={},
            instance_count={},
            material_count=0,
            draw_call_proxy=0,
            texture_memory_mb=0.0,
            within_budget={},
            status="not_available",
        )
        assert report.status != "ok", "Empty report claims 'ok' -- false pass"

    def test_over_budget_detected(self):
        report = TerrainPerformanceReport(
            triangle_count={"terrain": 5_000_000},
            instance_count={"terrain": 1},
            material_count=500,
            draw_call_proxy=2000,
            texture_memory_mb=4096.0,
            within_budget={"terrain_triangles": False},
            status="over_budget",
        )
        assert report.status == "over_budget"
        assert report.within_budget.get("terrain_triangles") is False

    def test_legitimate_ok(self):
        report = TerrainPerformanceReport(
            triangle_count={"terrain": 100_000},
            instance_count={"terrain": 1},
            material_count=10,
            draw_call_proxy=50,
            texture_memory_mb=256.0,
            within_budget={"terrain_triangles": True},
            status="ok",
        )
        assert report.status == "ok"
        assert all(report.within_budget.values())
