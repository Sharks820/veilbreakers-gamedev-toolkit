"""Unit tests for mesh topology grading and game-readiness logic.

Tests the _compute_grade, _list_issues, and game-readiness check logic
using synthetic metric dicts -- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# _compute_grade tests
# ---------------------------------------------------------------------------


class TestComputeGrade:
    """Test A-F grading thresholds from 02-RESEARCH.md."""

    def test_clean_cube_grades_a(self):
        """A clean cube (all quads, no issues) grades A."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 6,
            "vertex_count": 8,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "A"

    def test_many_non_manifold_grades_f(self):
        """A mesh with >20 non-manifold edges grades F."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 25,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "F"

    def test_mixed_issues_grades_c(self):
        """A mesh with 3% n-gons, 8% poles, 15% tris grades C."""
        from blender_addon.handlers.mesh import _compute_grade

        # 100 faces, 100 verts: 3% ngon, 8 poles (8%), 15 tris (15%)
        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 3.0,
            "non_manifold_edges": 0,
            "pole_count": 8,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 15,
        }
        assert _compute_grade(metrics) == "C"

    def test_grade_f_high_ngon_percentage(self):
        """N-gon % > 25 triggers F grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 30.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "F"

    def test_grade_f_high_poles(self):
        """Pole % > 50 triggers F grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 55,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "F"

    def test_grade_f_high_loose(self):
        """Loose > 50 triggers F grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 30,
            "loose_edges": 25,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "F"

    def test_grade_e_moderate_non_manifold(self):
        """Non-manifold edges 6-20 triggers E grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 10,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "E"

    def test_grade_e_moderate_ngon(self):
        """N-gon % 10-25 triggers E grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 15.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "E"

    def test_grade_e_moderate_poles(self):
        """Pole % 30-50 triggers E grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 35,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "E"

    def test_grade_e_moderate_loose(self):
        """Loose 10-50 triggers E grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 15,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "E"

    def test_grade_d_any_non_manifold(self):
        """Even 1 non-manifold edge triggers D grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 1,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "D"

    def test_grade_d_any_loose(self):
        """Even 1 loose vertex triggers D grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 1,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "D"

    def test_grade_d_high_tri_percentage(self):
        """Tri % > 40 triggers D grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 45,
        }
        assert _compute_grade(metrics) == "D"

    def test_grade_d_moderate_ngon(self):
        """N-gon % 5-10 triggers D grade (when no higher-grade issues)."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 7.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "D"

    def test_grade_c_small_ngon(self):
        """N-gon % 2-5 triggers C grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 3.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "C"

    def test_grade_c_moderate_tri(self):
        """Tri % 20-40 triggers C grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 25,
        }
        assert _compute_grade(metrics) == "C"

    def test_grade_b_tiny_ngon(self):
        """N-gon % > 0 but <= 2 triggers B grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 1.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "B"

    def test_grade_b_small_tri(self):
        """Tri % > 10 but <= 20 triggers B grade (in the B check, not C)."""
        from blender_addon.handlers.mesh import _compute_grade

        # tri_pct = 15, pole_pct = 0, ngon_pct = 0 -> B check: tri > 10 => B
        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 15,
        }
        assert _compute_grade(metrics) == "B"

    def test_grade_b_moderate_poles(self):
        """Pole % > 5 but <= 10 triggers B grade."""
        from blender_addon.handlers.mesh import _compute_grade

        metrics = {
            "face_count": 100,
            "vertex_count": 100,
            "ngon_percentage": 0.0,
            "non_manifold_edges": 0,
            "pole_count": 7,
            "loose_vertices": 0,
            "loose_edges": 0,
            "tri_count": 0,
        }
        assert _compute_grade(metrics) == "B"

    def test_grade_progression_f_to_a(self):
        """Grades follow F > E > D > C > B > A progression (worst to best)."""
        from blender_addon.handlers.mesh import _compute_grade

        grade_order = {"F": 0, "E": 1, "D": 2, "C": 3, "B": 4, "A": 5}

        # Create increasingly clean meshes
        grades = []
        # F: 25 nm edges
        grades.append(_compute_grade({
            "face_count": 100, "vertex_count": 100, "ngon_percentage": 0.0,
            "non_manifold_edges": 25, "pole_count": 0, "loose_vertices": 0,
            "loose_edges": 0, "tri_count": 0,
        }))
        # E: 10 nm edges
        grades.append(_compute_grade({
            "face_count": 100, "vertex_count": 100, "ngon_percentage": 0.0,
            "non_manifold_edges": 10, "pole_count": 0, "loose_vertices": 0,
            "loose_edges": 0, "tri_count": 0,
        }))
        # D: 1 nm edge
        grades.append(_compute_grade({
            "face_count": 100, "vertex_count": 100, "ngon_percentage": 0.0,
            "non_manifold_edges": 1, "pole_count": 0, "loose_vertices": 0,
            "loose_edges": 0, "tri_count": 0,
        }))
        # C: 3% ngon
        grades.append(_compute_grade({
            "face_count": 100, "vertex_count": 100, "ngon_percentage": 3.0,
            "non_manifold_edges": 0, "pole_count": 0, "loose_vertices": 0,
            "loose_edges": 0, "tri_count": 0,
        }))
        # B: 1% ngon
        grades.append(_compute_grade({
            "face_count": 100, "vertex_count": 100, "ngon_percentage": 1.0,
            "non_manifold_edges": 0, "pole_count": 0, "loose_vertices": 0,
            "loose_edges": 0, "tri_count": 0,
        }))
        # A: all clean
        grades.append(_compute_grade({
            "face_count": 100, "vertex_count": 100, "ngon_percentage": 0.0,
            "non_manifold_edges": 0, "pole_count": 0, "loose_vertices": 0,
            "loose_edges": 0, "tri_count": 0,
        }))

        for i in range(len(grades) - 1):
            assert grade_order[grades[i]] < grade_order[grades[i + 1]], (
                f"Expected {grades[i]} < {grades[i+1]} in progression"
            )


# ---------------------------------------------------------------------------
# _list_issues tests
# ---------------------------------------------------------------------------


class TestListIssues:
    """Test human-readable issue generation."""

    def test_clean_mesh_no_issues(self):
        """A clean mesh produces no issues."""
        from blender_addon.handlers.mesh import _list_issues

        metrics = {
            "non_manifold_edges": 0,
            "ngon_count": 0,
            "ngon_percentage": 0.0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "pole_count": 0,
            "vertex_count": 100,
            "e_poles": 0,
            "n_poles": 0,
        }
        issues = _list_issues(metrics)
        assert issues == []

    def test_non_manifold_issue_string(self):
        """Non-manifold edges produce a human-readable issue string."""
        from blender_addon.handlers.mesh import _list_issues

        metrics = {
            "non_manifold_edges": 5,
            "ngon_count": 0,
            "ngon_percentage": 0.0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "pole_count": 0,
            "vertex_count": 100,
            "e_poles": 0,
            "n_poles": 0,
        }
        issues = _list_issues(metrics)
        assert len(issues) >= 1
        assert "non-manifold" in issues[0].lower()
        assert "5" in issues[0]

    def test_ngon_issue_string(self):
        """N-gons produce a human-readable issue string."""
        from blender_addon.handlers.mesh import _list_issues

        metrics = {
            "non_manifold_edges": 0,
            "ngon_count": 10,
            "ngon_percentage": 5.0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "pole_count": 0,
            "vertex_count": 100,
            "e_poles": 0,
            "n_poles": 0,
        }
        issues = _list_issues(metrics)
        assert len(issues) >= 1
        assert any("n-gon" in i.lower() for i in issues)

    def test_loose_vertices_issue_string(self):
        """Loose vertices produce a human-readable issue string."""
        from blender_addon.handlers.mesh import _list_issues

        metrics = {
            "non_manifold_edges": 0,
            "ngon_count": 0,
            "ngon_percentage": 0.0,
            "loose_vertices": 3,
            "loose_edges": 0,
            "pole_count": 0,
            "vertex_count": 100,
            "e_poles": 0,
            "n_poles": 0,
        }
        issues = _list_issues(metrics)
        assert len(issues) >= 1
        assert any("loose" in i.lower() for i in issues)

    def test_multiple_issues_all_reported(self):
        """Multiple issues are all reported."""
        from blender_addon.handlers.mesh import _list_issues

        metrics = {
            "non_manifold_edges": 3,
            "ngon_count": 5,
            "ngon_percentage": 10.0,
            "loose_vertices": 2,
            "loose_edges": 4,
            "pole_count": 15,
            "vertex_count": 100,
            "e_poles": 5,
            "n_poles": 10,
        }
        issues = _list_issues(metrics)
        assert len(issues) >= 4  # nm, ngon, loose verts, loose edges, poles


# ---------------------------------------------------------------------------
# Game-readiness check logic tests
# ---------------------------------------------------------------------------


class TestGameReadinessLogic:
    """Test game-readiness pass/fail conditions without Blender."""

    def test_game_ready_returns_structured_dict(self):
        """Game-readiness check returns dict with required sub-check keys."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "A",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=True,
            has_material=True,
            location=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        assert "game_ready" in result
        assert "checks" in result
        checks = result["checks"]
        assert "topology" in checks
        assert "poly_budget" in checks
        assert "uv" in checks
        assert "materials" in checks
        assert "naming" in checks
        assert "transform" in checks

    def test_fails_when_topology_grade_d_or_worse(self):
        """Game-readiness fails when topology grade is D or worse."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "D",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=True,
            has_material=True,
            location=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        assert result["game_ready"] is False
        assert result["checks"]["topology"]["passed"] is False

    def test_fails_when_over_poly_budget(self):
        """Game-readiness fails when tri count exceeds poly_budget."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "A",
            "face_count": 30000,
            "tri_count": 0,
            "quad_count": 30000,
            "ngon_count": 0,
        }
        # 30000 quads * 2 = 60000 tris, over budget of 50000
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=True,
            has_material=True,
            location=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        assert result["game_ready"] is False
        assert result["checks"]["poly_budget"]["passed"] is False

    def test_fails_when_no_uv(self):
        """Game-readiness fails when mesh has no UV layer."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "A",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=False,
            has_material=True,
            location=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        assert result["game_ready"] is False
        assert result["checks"]["uv"]["passed"] is False

    def test_fails_when_no_material(self):
        """Game-readiness fails when mesh has no material."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "A",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=True,
            has_material=False,
            location=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        assert result["game_ready"] is False
        assert result["checks"]["materials"]["passed"] is False

    def test_fails_when_default_name(self):
        """Game-readiness fails when object has default Blender name."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "A",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        for default_name in ["Cube", "Sphere", "Cylinder", "Cube.001"]:
            result = _evaluate_game_readiness(
                topology_result=topology_result,
                object_name=default_name,
                poly_budget=50000,
                has_uv=True,
                has_material=True,
                location=(0.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0),
                scale=(1.0, 1.0, 1.0),
            )
            assert result["game_ready"] is False, f"Should fail for name: {default_name}"
            assert result["checks"]["naming"]["passed"] is False

    def test_fails_when_transforms_not_applied(self):
        """Game-readiness fails when transforms are not applied."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "A",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=True,
            has_material=True,
            location=(0.0, 0.0, 0.0),
            rotation=(0.5, 0.0, 0.0),
            scale=(2.0, 2.0, 2.0),
        )
        assert result["game_ready"] is False
        assert result["checks"]["transform"]["passed"] is False

    def test_passes_when_all_checks_pass(self):
        """Game-readiness passes when all sub-checks pass."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "B",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=True,
            has_material=True,
            location=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        assert result["game_ready"] is True

    def test_grade_c_still_passes_topology(self):
        """Grade C passes topology check (only D and worse fail)."""
        from blender_addon.handlers.mesh import _evaluate_game_readiness

        topology_result = {
            "grade": "C",
            "face_count": 100,
            "tri_count": 0,
            "quad_count": 100,
            "ngon_count": 0,
        }
        result = _evaluate_game_readiness(
            topology_result=topology_result,
            object_name="MyWeapon",
            poly_budget=50000,
            has_uv=True,
            has_material=True,
            location=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
        )
        assert result["checks"]["topology"]["passed"] is True


class TestBuildTopologyDelta:
    """Test topology delta summaries for cleanup/remesh operations."""

    def test_flags_improved_topology(self):
        from blender_addon.handlers.mesh import _build_topology_delta

        before = {
            "grade": "D",
            "face_count": 1200,
            "vertex_count": 900,
            "non_manifold_edges": 6,
            "boundary_edges": 12,
            "ngon_count": 18,
            "loose_vertices": 3,
            "loose_edges": 2,
        }
        after = {
            "grade": "B",
            "face_count": 800,
            "vertex_count": 700,
            "non_manifold_edges": 0,
            "boundary_edges": 4,
            "ngon_count": 2,
            "loose_vertices": 0,
            "loose_edges": 0,
        }

        delta = _build_topology_delta(before, after)

        assert delta["quality_change"] == "improved"
        assert delta["improved"] is True
        assert delta["regressed"] is False
        assert delta["grade_before"] == "D"
        assert delta["grade_after"] == "B"
        assert delta["face_count_delta"] == -400
        assert delta["vertex_count_delta"] == -200
        assert delta["non_manifold_edge_delta"] == -6
        assert delta["boundary_edge_delta"] == -8
        assert delta["ngon_delta"] == -16
        assert delta["loose_geometry_delta"] == -5

    def test_flags_regressed_topology(self):
        from blender_addon.handlers.mesh import _build_topology_delta

        before = {
            "grade": "B",
            "face_count": 500,
            "vertex_count": 420,
            "non_manifold_edges": 0,
            "boundary_edges": 0,
            "ngon_count": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
        }
        after = {
            "grade": "E",
            "face_count": 750,
            "vertex_count": 610,
            "non_manifold_edges": 4,
            "boundary_edges": 7,
            "ngon_count": 9,
            "loose_vertices": 2,
            "loose_edges": 1,
        }

        delta = _build_topology_delta(before, after)

        assert delta["quality_change"] == "regressed"
        assert delta["improved"] is False
        assert delta["regressed"] is True
        assert delta["face_count_delta"] == 250
        assert delta["vertex_count_delta"] == 190
        assert delta["non_manifold_edge_delta"] == 4
        assert delta["boundary_edge_delta"] == 7
        assert delta["ngon_delta"] == 9
        assert delta["loose_geometry_delta"] == 3

    def test_flags_unchanged_grade(self):
        from blender_addon.handlers.mesh import _build_topology_delta

        before = {
            "grade": "C",
            "face_count": 100,
            "vertex_count": 80,
            "non_manifold_edges": 0,
            "boundary_edges": 2,
            "ngon_count": 1,
            "loose_vertices": 0,
            "loose_edges": 0,
        }
        after = {
            "grade": "C",
            "face_count": 120,
            "vertex_count": 90,
            "non_manifold_edges": 0,
            "boundary_edges": 2,
            "ngon_count": 1,
            "loose_vertices": 0,
            "loose_edges": 0,
        }

        delta = _build_topology_delta(before, after)

        assert delta["quality_change"] == "unchanged"
        assert delta["improved"] is False
        assert delta["regressed"] is False


class TestKnifeParamValidation:
    """Test knife parameter validation and traceback preservation."""

    def test_invalid_plane_point_preserves_cause(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError) as exc_info:
            _validate_knife_params({
                "name": "Cube",
                "plane_point": ["bad", 0.0, 0.0],
            })

        assert "plane_point must be a 3-element list of numbers" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    def test_invalid_plane_normal_preserves_cause(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError) as exc_info:
            _validate_knife_params({
                "name": "Cube",
                "plane_normal": [0.0, object(), 1.0],
            })

        assert "plane_normal must be a 3-element list of numbers" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None
