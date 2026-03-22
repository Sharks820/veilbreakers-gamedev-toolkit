"""Tests for eye mesh generation.

Validates:
- Eye mesh geometry is valid (non-empty, valid indices)
- Inner eyeball + outer cornea are separate layers
- UV coordinates are valid (within [0, 1])
- Iris UVs map to a centered circle
- Material regions cover every face
- Eye pair positioning is symmetric
- Cornea is larger than eyeball
- Parameter edge cases work
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.eye_mesh import (
    generate_eye_mesh,
    generate_eye_pair,
    _uv_sphere,
    _compute_iris_uvs,
    _assign_eye_material_regions,
)


# ---------------------------------------------------------------------------
# Helper validation
# ---------------------------------------------------------------------------


def validate_eye_mesh(result: dict, label: str) -> None:
    """Validate an eye mesh result has all required fields and valid data."""
    required_keys = [
        "inner_vertices", "inner_faces", "inner_uvs",
        "outer_vertices", "outer_faces", "outer_uvs",
        "material_regions", "material_slots",
        "center", "radius", "cornea_radius", "metadata",
    ]
    for key in required_keys:
        assert key in result, f"{label}: missing key '{key}'"

    # Inner mesh validity
    inner_v = result["inner_vertices"]
    inner_f = result["inner_faces"]
    inner_uv = result["inner_uvs"]
    assert len(inner_v) > 0, f"{label}: empty inner vertices"
    assert len(inner_f) > 0, f"{label}: empty inner faces"
    assert len(inner_uv) == len(inner_v), (
        f"{label}: inner UV count {len(inner_uv)} != vertex count {len(inner_v)}"
    )

    n_inner = len(inner_v)
    for fi, face in enumerate(inner_f):
        assert len(face) >= 3, f"{label}: inner face {fi} has < 3 verts"
        for idx in face:
            assert 0 <= idx < n_inner, (
                f"{label}: inner face {fi} index {idx} out of range [0, {n_inner})"
            )

    # Outer mesh validity
    outer_v = result["outer_vertices"]
    outer_f = result["outer_faces"]
    outer_uv = result["outer_uvs"]
    assert len(outer_v) > 0, f"{label}: empty outer vertices"
    assert len(outer_f) > 0, f"{label}: empty outer faces"
    assert len(outer_uv) == len(outer_v), (
        f"{label}: outer UV count {len(outer_uv)} != vertex count {len(outer_v)}"
    )

    n_outer = len(outer_v)
    for fi, face in enumerate(outer_f):
        assert len(face) >= 3, f"{label}: outer face {fi} has < 3 verts"
        for idx in face:
            assert 0 <= idx < n_outer, (
                f"{label}: outer face {fi} index {idx} out of range [0, {n_outer})"
            )

    # All vertices are valid 3-tuples
    for i, v in enumerate(inner_v):
        assert len(v) == 3, f"{label}: inner vertex {i} not 3D"
        for c in v:
            assert math.isfinite(c), f"{label}: inner vertex {i} non-finite"

    for i, v in enumerate(outer_v):
        assert len(v) == 3, f"{label}: outer vertex {i} not 3D"
        for c in v:
            assert math.isfinite(c), f"{label}: outer vertex {i} non-finite"


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------


class TestEyeMeshStructure:
    """Validate eye mesh output structure."""

    def test_generates_valid_mesh(self):
        result = generate_eye_mesh()
        validate_eye_mesh(result, "default")

    def test_has_four_material_slots(self):
        result = generate_eye_mesh()
        slots = result["material_slots"]
        assert len(slots) == 4
        assert "eye_pupil" in slots
        assert "eye_iris" in slots
        assert "eye_sclera" in slots
        assert "eye_cornea" in slots

    def test_metadata_counts_correct(self):
        result = generate_eye_mesh()
        meta = result["metadata"]
        assert meta["inner_vertex_count"] == len(result["inner_vertices"])
        assert meta["inner_face_count"] == len(result["inner_faces"])
        assert meta["outer_vertex_count"] == len(result["outer_vertices"])
        assert meta["outer_face_count"] == len(result["outer_faces"])
        assert meta["total_vertex_count"] == (
            len(result["inner_vertices"]) + len(result["outer_vertices"])
        )
        assert meta["total_face_count"] == (
            len(result["inner_faces"]) + len(result["outer_faces"])
        )

    def test_center_and_radius(self):
        result = generate_eye_mesh(radius=0.015, cx=1.0, cy=2.0, cz=3.0)
        assert result["center"] == (1.0, 2.0, 3.0)
        assert result["radius"] == 0.015

    def test_cornea_larger_than_eyeball(self):
        result = generate_eye_mesh(radius=0.012, cornea_scale=1.03)
        assert result["cornea_radius"] > result["radius"]
        assert abs(result["cornea_radius"] - 0.012 * 1.03) < 1e-6


# ---------------------------------------------------------------------------
# UV coordinate tests
# ---------------------------------------------------------------------------


class TestEyeUVs:
    """Validate UV coordinates are valid and iris maps correctly."""

    def test_inner_uvs_in_range(self):
        result = generate_eye_mesh()
        for i, (u, v) in enumerate(result["inner_uvs"]):
            assert 0.0 <= u <= 1.0, f"Inner UV {i}: u={u} out of [0,1]"
            assert 0.0 <= v <= 1.0, f"Inner UV {i}: v={v} out of [0,1]"

    def test_outer_uvs_in_range(self):
        result = generate_eye_mesh()
        for i, (u, v) in enumerate(result["outer_uvs"]):
            assert 0.0 <= u <= 1.0, f"Outer UV {i}: u={u} out of [0,1]"
            assert 0.0 <= v <= 1.0, f"Outer UV {i}: v={v} out of [0,1]"

    def test_iris_uvs_centered(self):
        """Front-facing vertices should have UVs near (0.5, 0.5)."""
        result = generate_eye_mesh(
            cx=0, cy=0, cz=0,
            forward_axis=1, forward_sign=-1.0,
        )
        # Find vertices that face forward (negative Y)
        center = result["center"]
        radius = result["radius"]
        front_uvs = []
        for i, (vx, vy, vz) in enumerate(result["inner_vertices"]):
            dx = vx - center[0]
            dy = vy - center[1]
            dz = vz - center[2]
            length = math.sqrt(dx*dx + dy*dy + dz*dz)
            if length > 1e-10:
                # Check if facing forward (-Y)
                forward_dot = (-dy / length)
                if forward_dot > 0.8:  # strongly forward-facing
                    front_uvs.append(result["inner_uvs"][i])

        assert len(front_uvs) > 0, "No forward-facing vertices found"
        # These should be near center of UV space
        for u, v in front_uvs:
            dist = math.sqrt((u - 0.5)**2 + (v - 0.5)**2)
            assert dist < 0.3, f"Forward-facing UV ({u}, {v}) too far from center"

    def test_iris_uvs_form_circle(self):
        """UV coordinates of front-hemisphere vertices should cluster in a circle."""
        result = generate_eye_mesh(iris_radius_ratio=0.45)
        iris_uv_radius = 0.45 * 0.5  # expected UV radius for iris

        center = result["center"]
        front_uv_distances = []
        for i, (vx, vy, vz) in enumerate(result["inner_vertices"]):
            dx = vx - center[0]
            dy = vy - center[1]
            dz = vz - center[2]
            length = math.sqrt(dx*dx + dy*dy + dz*dz)
            if length > 1e-10:
                forward_dot = (-dy / length)
                if forward_dot > 0.5:  # front hemisphere
                    u, v = result["inner_uvs"][i]
                    front_uv_distances.append(
                        math.sqrt((u - 0.5)**2 + (v - 0.5)**2)
                    )

        assert len(front_uv_distances) > 0
        # All front-hemisphere UV distances should be <= iris_uv_radius
        for dist in front_uv_distances:
            assert dist <= iris_uv_radius + 0.05, (
                f"Front UV distance {dist} exceeds iris UV radius {iris_uv_radius}"
            )


# ---------------------------------------------------------------------------
# Material region tests
# ---------------------------------------------------------------------------


class TestEyeMaterialRegions:
    """Validate material region coverage."""

    def test_every_face_has_region(self):
        """Every face (inner + outer) should have a material region assigned."""
        result = generate_eye_mesh()
        regions = result["material_regions"]
        total_faces = len(result["inner_faces"]) + len(result["outer_faces"])
        assert len(regions) == total_faces, (
            f"Material regions cover {len(regions)} faces, expected {total_faces}"
        )
        for fi in range(total_faces):
            assert fi in regions, f"Face {fi} has no material region"

    def test_inner_faces_have_eye_regions(self):
        """Inner faces should be eye_pupil, eye_iris, or eye_sclera."""
        result = generate_eye_mesh()
        regions = result["material_regions"]
        inner_count = len(result["inner_faces"])
        valid_inner = {"eye_pupil", "eye_iris", "eye_sclera"}
        for fi in range(inner_count):
            assert regions[fi] in valid_inner, (
                f"Inner face {fi} has region '{regions[fi]}', "
                f"expected one of {valid_inner}"
            )

    def test_outer_faces_are_cornea(self):
        """All outer (cornea) faces should be 'eye_cornea'."""
        result = generate_eye_mesh()
        regions = result["material_regions"]
        inner_count = len(result["inner_faces"])
        outer_count = len(result["outer_faces"])
        for fi in range(inner_count, inner_count + outer_count):
            assert regions[fi] == "eye_cornea", (
                f"Outer face {fi} has region '{regions[fi]}', expected 'eye_cornea'"
            )

    def test_all_three_inner_regions_present(self):
        """Inner mesh should have pupil, iris, and sclera regions."""
        result = generate_eye_mesh()
        regions = result["material_regions"]
        inner_count = len(result["inner_faces"])
        inner_regions = {regions[fi] for fi in range(inner_count)}
        assert "eye_pupil" in inner_regions, "No pupil region found"
        assert "eye_iris" in inner_regions, "No iris region found"
        assert "eye_sclera" in inner_regions, "No sclera region found"

    def test_region_names_match_slots(self):
        """All region names should be in the material_slots list."""
        result = generate_eye_mesh()
        slots = set(result["material_slots"])
        region_names = set(result["material_regions"].values())
        assert region_names.issubset(slots), (
            f"Regions {region_names - slots} not in material_slots {slots}"
        )


# ---------------------------------------------------------------------------
# Eye pair tests
# ---------------------------------------------------------------------------


class TestEyePair:
    """Validate eye pair generation and positioning."""

    def test_generates_two_eyes(self):
        pair = generate_eye_pair()
        assert "left_eye" in pair
        assert "right_eye" in pair
        assert "eye_positions" in pair

    def test_both_eyes_valid(self):
        pair = generate_eye_pair()
        validate_eye_mesh(pair["left_eye"], "left_eye")
        validate_eye_mesh(pair["right_eye"], "right_eye")

    def test_eyes_symmetric_x(self):
        """Left and right eyes should be symmetric about X=0."""
        pair = generate_eye_pair(head_center=(0, 0, 1.64))
        left_pos = pair["eye_positions"]["left"]
        right_pos = pair["eye_positions"]["right"]

        # X should be negated
        assert abs(left_pos[0] + right_pos[0]) < 1e-6, (
            f"X not symmetric: left={left_pos[0]}, right={right_pos[0]}"
        )
        # Y and Z should be equal
        assert abs(left_pos[1] - right_pos[1]) < 1e-6
        assert abs(left_pos[2] - right_pos[2]) < 1e-6

    def test_eyes_forward_of_head_center(self):
        """Eyes should be positioned forward (-Y) of head center."""
        pair = generate_eye_pair(head_center=(0, 0, 1.64))
        left_pos = pair["eye_positions"]["left"]
        right_pos = pair["eye_positions"]["right"]
        assert left_pos[1] < 0, "Left eye should be forward (-Y)"
        assert right_pos[1] < 0, "Right eye should be forward (-Y)"

    def test_eyes_above_head_center(self):
        """Eyes should be slightly above head center (+Z offset)."""
        hc = (0, 0, 1.64)
        pair = generate_eye_pair(head_center=hc)
        left_pos = pair["eye_positions"]["left"]
        assert left_pos[2] > hc[2], "Eyes should be above head center"

    def test_custom_head_dimensions(self):
        """Custom head center/radius should position eyes accordingly."""
        pair = generate_eye_pair(
            head_center=(1.0, 2.0, 3.0),
            head_radius=0.15,
            eye_radius=0.015,
        )
        left = pair["left_eye"]
        assert left["radius"] == 0.015
        # Eyes should be near the head center
        lpos = pair["eye_positions"]["left"]
        dist = math.sqrt(
            (lpos[0] - 1.0)**2 + (lpos[1] - 2.0)**2 + (lpos[2] - 3.0)**2
        )
        assert dist < 0.15 * 1.5, f"Eye too far from head center: {dist}"


# ---------------------------------------------------------------------------
# Geometry validity tests
# ---------------------------------------------------------------------------


class TestEyeGeometry:
    """Validate eye mesh geometry properties."""

    def test_inner_vertices_on_sphere(self):
        """Inner vertices should be approximately on a sphere."""
        result = generate_eye_mesh(radius=0.012, cx=0, cy=0, cz=0)
        center = result["center"]
        radius = result["radius"]
        for i, v in enumerate(result["inner_vertices"]):
            dist = math.sqrt(
                (v[0] - center[0])**2 +
                (v[1] - center[1])**2 +
                (v[2] - center[2])**2
            )
            assert abs(dist - radius) < radius * 0.01, (
                f"Inner vertex {i} at distance {dist}, expected {radius}"
            )

    def test_outer_vertices_on_larger_sphere(self):
        """Outer vertices should be on the cornea sphere (larger)."""
        result = generate_eye_mesh(radius=0.012, cornea_scale=1.03)
        center = result["center"]
        cornea_r = result["cornea_radius"]
        for i, v in enumerate(result["outer_vertices"]):
            dist = math.sqrt(
                (v[0] - center[0])**2 +
                (v[1] - center[1])**2 +
                (v[2] - center[2])**2
            )
            assert abs(dist - cornea_r) < cornea_r * 0.01, (
                f"Outer vertex {i} at distance {dist}, expected {cornea_r}"
            )

    def test_no_degenerate_faces(self):
        """No face should have duplicate vertex indices."""
        result = generate_eye_mesh()
        for fi, face in enumerate(result["inner_faces"]):
            assert len(set(face)) == len(face), (
                f"Inner face {fi} has duplicate indices: {face}"
            )
        for fi, face in enumerate(result["outer_faces"]):
            assert len(set(face)) == len(face), (
                f"Outer face {fi} has duplicate indices: {face}"
            )


# ---------------------------------------------------------------------------
# Parameter variation tests
# ---------------------------------------------------------------------------


class TestEyeParameters:
    """Test parameter variations and edge cases."""

    def test_different_radii(self):
        small = generate_eye_mesh(radius=0.008)
        large = generate_eye_mesh(radius=0.020)
        validate_eye_mesh(small, "small")
        validate_eye_mesh(large, "large")
        assert small["radius"] < large["radius"]

    def test_different_iris_ratios(self):
        narrow = generate_eye_mesh(iris_radius_ratio=0.2)
        wide = generate_eye_mesh(iris_radius_ratio=0.7)
        validate_eye_mesh(narrow, "narrow_iris")
        validate_eye_mesh(wide, "wide_iris")

    def test_clamped_iris_ratio(self):
        """Extreme iris ratios should be clamped."""
        result = generate_eye_mesh(iris_radius_ratio=0.01)
        assert result["metadata"]["iris_radius_ratio"] >= 0.1
        result = generate_eye_mesh(iris_radius_ratio=0.99)
        assert result["metadata"]["iris_radius_ratio"] <= 0.9

    def test_different_resolution(self):
        low = generate_eye_mesh(rings=4, sectors=6)
        high = generate_eye_mesh(rings=12, sectors=16)
        validate_eye_mesh(low, "low_res")
        validate_eye_mesh(high, "high_res")
        assert len(low["inner_vertices"]) < len(high["inner_vertices"])

    def test_positioned_at_offset(self):
        result = generate_eye_mesh(cx=5.0, cy=-3.0, cz=10.0)
        validate_eye_mesh(result, "offset")
        # All inner vertices should be near (5, -3, 10)
        for v in result["inner_vertices"]:
            dist = math.sqrt((v[0]-5)**2 + (v[1]+3)**2 + (v[2]-10)**2)
            assert dist < 0.02, f"Vertex too far from center: {dist}"


# ---------------------------------------------------------------------------
# Low-level function tests
# ---------------------------------------------------------------------------


class TestUVSphere:
    """Test the UV sphere generator."""

    def test_vertex_count(self):
        verts, faces, uvs = _uv_sphere(0, 0, 0, 1.0, rings=6, sectors=8)
        # 2 poles + (rings-1) * sectors intermediate
        expected = 2 + (6 - 1) * 8
        assert len(verts) == expected

    def test_uv_count_matches_verts(self):
        verts, faces, uvs = _uv_sphere(0, 0, 0, 1.0, rings=8, sectors=12)
        assert len(uvs) == len(verts)

    def test_uvs_in_range(self):
        _, _, uvs = _uv_sphere(0, 0, 0, 1.0, rings=8, sectors=12)
        for i, (u, v) in enumerate(uvs):
            assert 0.0 <= u <= 1.0, f"UV {i}: u={u} out of range"
            assert 0.0 <= v <= 1.0, f"UV {i}: v={v} out of range"

    def test_face_indices_valid(self):
        verts, faces, _ = _uv_sphere(0, 0, 0, 1.0, rings=8, sectors=12)
        n = len(verts)
        for fi, face in enumerate(faces):
            for idx in face:
                assert 0 <= idx < n, f"Face {fi} index {idx} out of range"


class TestIrisUVMapping:
    """Test iris UV computation."""

    def test_forward_vertex_maps_to_center(self):
        """A vertex directly in front should map near UV center."""
        verts = [(0.0, -1.0, 0.0)]  # directly forward (-Y)
        center = (0.0, 0.0, 0.0)
        uvs = _compute_iris_uvs(verts, center, 1.0, 0.45, 0.2)
        u, v = uvs[0]
        assert abs(u - 0.5) < 0.01, f"Forward vertex U={u}, expected ~0.5"
        assert abs(v - 0.5) < 0.01, f"Forward vertex V={v}, expected ~0.5"

    def test_backward_vertex_maps_away_from_center(self):
        """A vertex directly behind should map far from UV center."""
        verts = [(0.0, 1.0, 0.0)]  # directly backward (+Y)
        center = (0.0, 0.0, 0.0)
        uvs = _compute_iris_uvs(verts, center, 1.0, 0.45, 0.2)
        u, v = uvs[0]
        dist = math.sqrt((u - 0.5)**2 + (v - 0.5)**2)
        assert dist > 0.15, f"Backward vertex UV dist={dist}, expected > 0.15"


class TestMaterialRegionAssignment:
    """Test face material region assignment."""

    def test_outer_layer_all_cornea(self):
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        faces = [(0, 1, 2)]
        regions = _assign_eye_material_regions(
            verts, faces, (0.5, 0.5, 0), 1.0, 0.45,
            layer="outer",
        )
        assert regions[0] == "eye_cornea"

    def test_inner_layer_has_mixed_regions(self):
        """Inner layer with a full sphere should have multiple region types."""
        verts, faces, _ = _uv_sphere(0, 0, 0, 1.0, rings=8, sectors=12)
        regions = _assign_eye_material_regions(
            verts, faces, (0, 0, 0), 1.0, 0.45,
            forward_axis=1, forward_sign=-1.0,
            layer="inner",
        )
        region_set = set(regions.values())
        assert "eye_sclera" in region_set, "Expected sclera region"
        # At least sclera + one of iris/pupil should exist
        assert len(region_set) >= 2, f"Expected >= 2 regions, got {region_set}"
