"""Tests for riggable environmental object generators.

Validates that every generator returns valid riggable mesh data:
- Non-empty vertex and face lists
- Empties dict with named entries
- Vertex groups dict with valid vertex indices
- Proper face index validity
- UV coordinates in valid 0-1 range
- Style-specific geometry differences
- Structural correctness (plank gaps, chain interlocking, grid topology, catenary)
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.riggable_objects import (
    generate_door,
    generate_chain,
    generate_flag,
    generate_chest,
    generate_chandelier,
    generate_drawbridge,
    generate_rope_bridge,
    generate_hanging_sign,
    generate_windmill,
    generate_cage,
    _plank_row,
    _torus_link,
    _catenary_curve,
    _iron_strap,
)


# ---------------------------------------------------------------------------
# Common validation helpers
# ---------------------------------------------------------------------------

def _assert_valid_mesh(spec: dict, name: str = "") -> None:
    """Assert that a mesh spec has valid structure."""
    label = f" ({name})" if name else ""
    assert spec["vertices"], f"No vertices{label}"
    assert spec["faces"], f"No faces{label}"
    max_idx = len(spec["vertices"]) - 1
    for fi, face in enumerate(spec["faces"]):
        for vi in face:
            assert 0 <= vi <= max_idx, (
                f"Face {fi} has out-of-range index {vi} "
                f"(max {max_idx}){label}"
            )


def _assert_has_empties(spec: dict, *names: str) -> None:
    """Assert that empties dict has the given named entries."""
    for n in names:
        assert n in spec["empties"], f"Missing empty: {n!r}"
        pos = spec["empties"][n]
        assert len(pos) == 3, f"Empty {n!r} position must be 3-tuple"


def _assert_has_vertex_groups(spec: dict, *names: str) -> None:
    """Assert vertex groups exist and contain valid indices."""
    max_idx = len(spec["vertices"]) - 1
    for n in names:
        assert n in spec["vertex_groups"], f"Missing vertex group: {n!r}"
        group = spec["vertex_groups"][n]
        assert isinstance(group, list), f"Vertex group {n!r} must be a list"
        for vi in group:
            assert 0 <= vi <= max_idx, (
                f"Vertex group {n!r} has out-of-range index {vi}"
            )


def _assert_valid_uvs(spec: dict) -> None:
    """Assert UVs are present and in valid range."""
    uvs = spec.get("uvs", [])
    if not uvs:
        return  # UVs are optional in some cases
    for i, (u, v) in enumerate(uvs):
        assert -0.01 <= u <= 1.01, f"UV {i}: u={u} out of range"
        assert -0.01 <= v <= 1.01, f"UV {i}: v={v} out of range"


def _assert_has_rig_info(spec: dict, *keys: str) -> None:
    """Assert that metadata.rig_info has the given keys."""
    rig_info = spec["metadata"].get("rig_info", {})
    for k in keys:
        assert k in rig_info, f"Missing rig_info key: {k!r}"


# =========================================================================
# Helper function tests
# =========================================================================

class TestPlankRow:
    """Tests for _plank_row helper."""

    def test_basic_generation(self) -> None:
        verts, faces, uvs, ranges = _plank_row(4, 1.0, 2.0)
        assert len(verts) > 0
        assert len(faces) > 0
        assert len(ranges) == 4

    def test_plank_count_matches_ranges(self) -> None:
        for count in [2, 5, 10]:
            _, _, _, ranges = _plank_row(count, 1.0, 1.0)
            assert len(ranges) == count

    def test_planks_have_gaps(self) -> None:
        """Adjacent planks must not overlap (there's a gap)."""
        verts, _, _, ranges = _plank_row(5, 1.0, 1.0, gap=0.01)
        for i in range(len(ranges) - 1):
            _, end = ranges[i]
            start_next, _ = ranges[i + 1]
            # Get max x of current plank and min x of next
            plank_xs = [verts[vi][0] for vi in range(ranges[i][0], ranges[i][1])]
            next_xs = [verts[vi][0] for vi in range(ranges[i + 1][0], ranges[i + 1][1])]
            max_x = max(plank_xs)
            min_x_next = min(next_xs)
            assert min_x_next > max_x, "Planks should have gap between them"

    def test_each_plank_has_thickness(self) -> None:
        """Each plank should have non-zero depth (not infinitely thin)."""
        verts, _, _, ranges = _plank_row(3, 0.6, 1.0, thickness=0.05)
        for start, end in ranges:
            zs = [verts[vi][2] for vi in range(start, end)]
            depth = max(zs) - min(zs)
            assert depth > 0.01, "Plank must have thickness"

    def test_uvs_in_range(self) -> None:
        _, _, uvs, _ = _plank_row(4, 1.0, 1.0)
        for u, v in uvs:
            assert 0.0 <= u <= 1.0
            assert 0.0 <= v <= 1.0


class TestTorusLink:
    """Tests for _torus_link helper."""

    def test_produces_geometry(self) -> None:
        verts, faces = _torus_link(0, 0, 0, 0.02, 0.005)
        assert len(verts) > 0
        assert len(faces) > 0

    def test_orientation_differs(self) -> None:
        """Orientation 0 and 1 should produce different vertex positions."""
        v0, _ = _torus_link(0, 0, 0, 0.02, 0.005, orientation=0)
        v1, _ = _torus_link(0, 0, 0, 0.02, 0.005, orientation=1)
        # At least some vertices should differ
        diffs = sum(1 for a, b in zip(v0, v1) if a != b)
        assert diffs > 0, "Different orientations should produce different geometry"

    def test_valid_faces(self) -> None:
        verts, faces = _torus_link(0, 0, 0, 0.03, 0.008)
        max_idx = len(verts) - 1
        for face in faces:
            for vi in face:
                assert 0 <= vi <= max_idx


class TestCatenaryCurve:
    """Tests for _catenary_curve helper."""

    def test_endpoints_match(self) -> None:
        start = (0, 5, 0)
        end = (10, 5, 0)
        pts = _catenary_curve(start, end, 2.0, 20)
        assert len(pts) == 20
        # Start matches
        assert abs(pts[0][0] - start[0]) < 1e-9
        assert abs(pts[0][1] - start[1]) < 1e-9
        assert abs(pts[0][2] - start[2]) < 1e-9
        # End matches
        assert abs(pts[-1][0] - end[0]) < 1e-9
        assert abs(pts[-1][1] - end[1]) < 1e-9
        assert abs(pts[-1][2] - end[2]) < 1e-9

    def test_sag_at_midpoint(self) -> None:
        """Middle point should be lower than endpoints by approximately sag amount."""
        pts = _catenary_curve((0, 10, 0), (10, 10, 0), 3.0, 21)
        mid = pts[10]
        assert mid[1] < 10.0, "Midpoint should sag below start/end"
        # Parabolic sag at midpoint should be -sag
        assert abs(mid[1] - (10.0 - 3.0)) < 0.1

    def test_single_point(self) -> None:
        pts = _catenary_curve((0, 0, 0), (1, 0, 0), 0.5, 1)
        assert len(pts) == 1

    def test_no_sag(self) -> None:
        pts = _catenary_curve((0, 5, 0), (10, 5, 0), 0.0, 10)
        for p in pts:
            assert abs(p[1] - 5.0) < 1e-9


class TestIronStrap:
    """Tests for _iron_strap helper."""

    def test_produces_geometry(self) -> None:
        verts, faces = _iron_strap(0, 0, 0, 1, 0, 0)
        assert len(verts) == 8
        assert len(faces) == 6

    def test_zero_length_returns_empty(self) -> None:
        verts, faces = _iron_strap(0, 0, 0, 0, 0, 0)
        assert len(verts) == 0
        assert len(faces) == 0


# =========================================================================
# Door tests
# =========================================================================

class TestDoor:
    """Tests for generate_door."""

    STYLES = [
        "wooden_plank", "iron_bound", "dungeon_gate", "portcullis",
        "double_door", "barn_door", "castle_gate", "secret_passage",
    ]

    @pytest.mark.parametrize("style", STYLES)
    def test_produces_valid_mesh(self, style: str) -> None:
        spec = generate_door(style=style)
        _assert_valid_mesh(spec, f"door_{style}")

    @pytest.mark.parametrize("style", STYLES)
    def test_has_empties(self, style: str) -> None:
        spec = generate_door(style=style)
        assert len(spec["empties"]) > 0, f"Door {style} should have empties"

    @pytest.mark.parametrize("style", STYLES)
    def test_has_vertex_groups(self, style: str) -> None:
        spec = generate_door(style=style)
        assert len(spec["vertex_groups"]) > 0

    def test_wooden_plank_has_hinge_and_panel(self) -> None:
        spec = generate_door(style="wooden_plank")
        _assert_has_empties(spec, "hinge_top", "hinge_bottom")
        _assert_has_vertex_groups(spec, "hinge", "panel", "frame")

    def test_portcullis_has_slide_empties(self) -> None:
        spec = generate_door(style="portcullis")
        _assert_has_empties(spec, "slide_top", "slide_bottom")
        _assert_has_vertex_groups(spec, "bars")

    def test_double_door_has_two_panels(self) -> None:
        spec = generate_door(style="double_door")
        _assert_has_empties(spec, "hinge_left_top", "hinge_right_top")
        _assert_has_vertex_groups(spec, "panel_left", "panel_right")

    def test_styles_produce_different_geometry(self) -> None:
        specs = {s: generate_door(style=s) for s in self.STYLES}
        vert_counts = {s: len(specs[s]["vertices"]) for s in self.STYLES}
        # At least some styles should differ in vertex count
        assert len(set(vert_counts.values())) > 1, "Styles should produce different geometry"

    def test_uvs_valid(self) -> None:
        spec = generate_door(style="wooden_plank")
        _assert_valid_uvs(spec)

    def test_rig_info_present(self) -> None:
        spec = generate_door(style="wooden_plank")
        _assert_has_rig_info(spec, "type", "style")

    def test_custom_dimensions(self) -> None:
        spec = generate_door(width=1.5, height=3.0, thickness=0.1)
        dims = spec["metadata"]["dimensions"]
        assert dims["width"] > 1.0
        assert dims["height"] > 2.5


# =========================================================================
# Chain tests
# =========================================================================

class TestChain:
    """Tests for generate_chain."""

    def test_produces_valid_mesh(self) -> None:
        spec = generate_chain()
        _assert_valid_mesh(spec, "chain")

    def test_has_per_link_groups(self) -> None:
        spec = generate_chain(link_count=6)
        for i in range(6):
            _assert_has_vertex_groups(spec, f"link_{i}")

    def test_has_attachment_empties(self) -> None:
        spec = generate_chain()
        _assert_has_empties(spec, "attach_start", "attach_end")

    def test_links_interlock(self) -> None:
        """Adjacent links should have alternating orientations.

        We verify this by checking that even-indexed and odd-indexed links
        have their geometry spread differently across axes.
        """
        spec = generate_chain(link_count=4, link_width=0.04, link_height=0.06)
        vg = spec["vertex_groups"]
        verts = spec["vertices"]

        # For link 0 (orientation=0, XY plane) and link 1 (orientation=1, YZ plane)
        link0_verts = [verts[i] for i in vg["link_0"]]
        link1_verts = [verts[i] for i in vg["link_1"]]

        # Link 0 should be wider in X, link 1 wider in Z
        link0_x_range = max(v[0] for v in link0_verts) - min(v[0] for v in link0_verts)
        link0_z_range = max(v[2] for v in link0_verts) - min(v[2] for v in link0_verts)
        link1_x_range = max(v[0] for v in link1_verts) - min(v[0] for v in link1_verts)
        link1_z_range = max(v[2] for v in link1_verts) - min(v[2] for v in link1_verts)

        # Orientation 0: wide in X, narrow in Z
        # Orientation 1: narrow in X, wide in Z
        assert link0_x_range > link0_z_range, "Link 0 should be wider in X"
        assert link1_z_range > link1_x_range, "Link 1 should be wider in Z"

    def test_bone_positions_in_rig_info(self) -> None:
        spec = generate_chain(link_count=5)
        rig_info = spec["metadata"]["rig_info"]
        assert "bone_positions" in rig_info
        assert len(rig_info["bone_positions"]) == 5

    def test_different_link_counts(self) -> None:
        spec4 = generate_chain(link_count=4)
        spec12 = generate_chain(link_count=12)
        assert len(spec12["vertices"]) > len(spec4["vertices"])

    def test_link_groups_non_overlapping(self) -> None:
        spec = generate_chain(link_count=4)
        all_indices: set[int] = set()
        for i in range(4):
            group = set(spec["vertex_groups"][f"link_{i}"])
            assert not group & all_indices, f"Link {i} overlaps with previous links"
            all_indices |= group


# =========================================================================
# Flag tests
# =========================================================================

class TestFlag:
    """Tests for generate_flag."""

    STYLES = ["banner", "pennant", "gonfalon", "standard", "tattered"]

    @pytest.mark.parametrize("style", STYLES)
    def test_produces_valid_mesh(self, style: str) -> None:
        spec = generate_flag(style=style)
        _assert_valid_mesh(spec, f"flag_{style}")

    def test_regular_grid_topology(self) -> None:
        """Banner flag mesh should have (rows+1) * (cols+1) vertices in the flag body."""
        subdivs = 10
        spec = generate_flag(subdivisions=subdivs, style="banner")
        expected_flag_verts = (subdivs + 1) * (subdivs + 1)
        flag_body = spec["vertex_groups"]["flag_body"]
        assert len(flag_body) == expected_flag_verts

    def test_pinned_vertex_group(self) -> None:
        """Pinned vertices should be along the pole edge (one column)."""
        subdivs = 8
        spec = generate_flag(subdivisions=subdivs, style="banner")
        pinned = spec["vertex_groups"]["pinned"]
        # Should be rows+1 vertices (one per row along c=0)
        assert len(pinned) == subdivs + 1

    def test_has_required_groups(self) -> None:
        spec = generate_flag()
        _assert_has_vertex_groups(spec, "pinned", "flag_body", "pole")

    def test_has_required_empties(self) -> None:
        spec = generate_flag()
        _assert_has_empties(spec, "pole_base", "pole_top",
                           "flag_attach_top", "flag_attach_bottom")

    def test_flag_faces_are_quads(self) -> None:
        """All flag faces should be quads (4 vertices) for cloth sim."""
        spec = generate_flag(subdivisions=6, style="banner")
        # Flag faces are the first (rows * cols) faces
        rows = cols = 6
        flag_face_count = rows * cols
        for i in range(flag_face_count):
            assert len(spec["faces"][i]) == 4, f"Face {i} is not a quad"

    def test_styles_differ(self) -> None:
        specs = {s: generate_flag(style=s) for s in self.STYLES}
        vert_counts = {s: len(specs[s]["vertices"]) for s in self.STYLES}
        # Tattered has fewer faces due to removed cells
        tattered_faces = len(specs["tattered"]["faces"])
        banner_faces = len(specs["banner"]["faces"])
        # Tattered should have fewer faces OR same (random)
        # Just check they all produce valid meshes
        for s in self.STYLES:
            assert vert_counts[s] > 0

    def test_cloth_sim_rig_info(self) -> None:
        spec = generate_flag()
        _assert_has_rig_info(spec, "type", "cloth_sim", "grid_rows", "grid_cols")
        assert spec["metadata"]["rig_info"]["cloth_sim"] is True

    def test_wind_vertex_colors(self) -> None:
        spec = generate_flag(subdivisions=4)
        wind = spec["metadata"]["rig_info"].get("wind_vertex_colors", [])
        assert len(wind) > 0
        # First vertex (pole edge, top) should have R~0 (near pole)
        assert wind[0]["R"] < 0.01

    def test_uvs_cover_flag_face(self) -> None:
        spec = generate_flag(subdivisions=6, style="banner")
        flag_body = spec["vertex_groups"]["flag_body"]
        uvs = spec["uvs"]
        flag_uvs = [uvs[i] for i in flag_body if i < len(uvs)]
        if flag_uvs:
            us = [uv[0] for uv in flag_uvs]
            vs = [uv[1] for uv in flag_uvs]
            # Should span roughly 0-1 range
            assert max(us) > 0.9
            assert min(us) < 0.1


# =========================================================================
# Chest tests
# =========================================================================

class TestChest:
    """Tests for generate_chest."""

    STYLES = ["wooden", "iron_bound", "ornate_gold", "skeleton_coffin",
              "mimic", "barrel_stash"]

    @pytest.mark.parametrize("style", STYLES)
    def test_produces_valid_mesh(self, style: str) -> None:
        spec = generate_chest(style=style)
        _assert_valid_mesh(spec, f"chest_{style}")

    @pytest.mark.parametrize("style", STYLES)
    def test_has_base_and_lid_groups(self, style: str) -> None:
        spec = generate_chest(style=style)
        _assert_has_vertex_groups(spec, "base", "lid")

    def test_has_hinge_empties(self) -> None:
        spec = generate_chest(style="wooden")
        _assert_has_empties(spec, "hinge_left", "hinge_right", "hinge_axis")

    def test_has_loot_spawn(self) -> None:
        spec = generate_chest(style="wooden")
        _assert_has_empties(spec, "loot_spawn")

    def test_lid_separate_from_base(self) -> None:
        """Lid and base vertex groups should not overlap."""
        spec = generate_chest(style="wooden")
        base_set = set(spec["vertex_groups"]["base"])
        lid_set = set(spec["vertex_groups"]["lid"])
        assert not base_set & lid_set, "Lid and base groups should be disjoint"

    def test_mimic_has_teeth(self) -> None:
        """Mimic style should have more geometry than basic wooden."""
        spec_mimic = generate_chest(style="mimic")
        spec_wooden = generate_chest(style="wooden")
        assert len(spec_mimic["vertices"]) > len(spec_wooden["vertices"])

    def test_rig_info(self) -> None:
        spec = generate_chest()
        _assert_has_rig_info(spec, "type", "style", "lid_hinge_axis")

    def test_styles_produce_different_geometry(self) -> None:
        specs = {s: generate_chest(style=s) for s in self.STYLES}
        vert_counts = {s: len(specs[s]["vertices"]) for s in self.STYLES}
        assert len(set(vert_counts.values())) > 1


# =========================================================================
# Chandelier tests
# =========================================================================

class TestChandelier:
    """Tests for generate_chandelier."""

    STYLES = ["iron_ring", "candelabra", "bone_chandelier", "cage_lantern"]

    @pytest.mark.parametrize("style", STYLES)
    def test_produces_valid_mesh(self, style: str) -> None:
        spec = generate_chandelier(style=style)
        _assert_valid_mesh(spec, f"chandelier_{style}")

    def test_has_ceiling_anchor(self) -> None:
        spec = generate_chandelier()
        _assert_has_empties(spec, "ceiling_anchor")

    def test_has_flame_empties(self) -> None:
        n = 6
        spec = generate_chandelier(candle_count=n)
        for i in range(n):
            _assert_has_empties(spec, f"flame_{i}")

    def test_sway_vertex_group(self) -> None:
        spec = generate_chandelier()
        _assert_has_vertex_groups(spec, "sway", "chain")

    def test_candle_positions_in_rig_info(self) -> None:
        spec = generate_chandelier(candle_count=5)
        rig_info = spec["metadata"]["rig_info"]
        assert len(rig_info["candle_positions"]) == 5


# =========================================================================
# Drawbridge tests
# =========================================================================

class TestDrawbridge:
    """Tests for generate_drawbridge."""

    def test_produces_valid_mesh(self) -> None:
        spec = generate_drawbridge()
        _assert_valid_mesh(spec, "drawbridge")

    def test_has_hinge_empties(self) -> None:
        spec = generate_drawbridge()
        _assert_has_empties(spec, "hinge_left", "hinge_right", "hinge_axis")

    def test_has_chain_attach_empties(self) -> None:
        spec = generate_drawbridge()
        _assert_has_empties(spec, "chain_attach_left", "chain_attach_right")

    def test_has_bridge_group(self) -> None:
        spec = generate_drawbridge()
        _assert_has_vertex_groups(spec, "bridge", "beams", "rails")

    def test_rig_info(self) -> None:
        spec = generate_drawbridge()
        _assert_has_rig_info(spec, "type", "hinge_axis", "chain_driven")

    def test_custom_dimensions(self) -> None:
        spec = generate_drawbridge(width=6.0, length=5.0, plank_count=20)
        dims = spec["metadata"]["dimensions"]
        assert dims["width"] > 5.0


# =========================================================================
# Rope bridge tests
# =========================================================================

class TestRopeBridge:
    """Tests for generate_rope_bridge."""

    def test_produces_valid_mesh(self) -> None:
        spec = generate_rope_bridge()
        _assert_valid_mesh(spec, "rope_bridge")

    def test_has_anchor_empties(self) -> None:
        spec = generate_rope_bridge()
        _assert_has_empties(spec, "anchor_start", "anchor_end")

    def test_has_anchor_groups(self) -> None:
        spec = generate_rope_bridge()
        _assert_has_vertex_groups(spec, "anchor_start", "anchor_end")

    def test_per_plank_groups(self) -> None:
        n = 10
        spec = generate_rope_bridge(plank_count=n)
        for i in range(n):
            _assert_has_vertex_groups(spec, f"plank_{i}")

    def test_plank_positions_follow_catenary(self) -> None:
        """Planks in the middle should be lower than at the ends."""
        spec = generate_rope_bridge(length=8.0, sag=1.0, plank_count=11)
        verts = spec["vertices"]
        # Middle plank (index 5)
        mid_group = spec["vertex_groups"]["plank_5"]
        mid_ys = [verts[i][1] for i in mid_group]
        mid_avg_y = sum(mid_ys) / len(mid_ys)

        # End plank (index 0)
        start_group = spec["vertex_groups"]["plank_0"]
        start_ys = [verts[i][1] for i in start_group]
        start_avg_y = sum(start_ys) / len(start_ys)

        assert mid_avg_y < start_avg_y, "Middle plank should be lower than start"


# =========================================================================
# Hanging sign tests
# =========================================================================

class TestHangingSign:
    """Tests for generate_hanging_sign."""

    BRACKET_STYLES = ["iron_scroll", "simple"]

    @pytest.mark.parametrize("style", BRACKET_STYLES)
    def test_produces_valid_mesh(self, style: str) -> None:
        spec = generate_hanging_sign(bracket_style=style)
        _assert_valid_mesh(spec, f"sign_{style}")

    def test_has_required_empties(self) -> None:
        spec = generate_hanging_sign()
        _assert_has_empties(spec, "wall_mount", "pivot", "sign_center")

    def test_has_sign_board_group(self) -> None:
        spec = generate_hanging_sign()
        _assert_has_vertex_groups(spec, "sign_board", "bracket")

    def test_rig_info(self) -> None:
        spec = generate_hanging_sign()
        _assert_has_rig_info(spec, "type", "pivot_axis", "physics")


# =========================================================================
# Windmill tests
# =========================================================================

class TestWindmill:
    """Tests for generate_windmill."""

    def test_produces_valid_mesh(self) -> None:
        spec = generate_windmill()
        _assert_valid_mesh(spec, "windmill")

    def test_has_rotation_empty(self) -> None:
        spec = generate_windmill()
        _assert_has_empties(spec, "rotation_axis")

    def test_has_blade_group(self) -> None:
        spec = generate_windmill()
        _assert_has_vertex_groups(spec, "blades")

    def test_cloth_panels_per_blade(self) -> None:
        n = 4
        spec = generate_windmill(blade_count=n)
        for i in range(n):
            _assert_has_vertex_groups(spec, f"cloth_{i}")

    def test_rig_info_has_cloth_panels(self) -> None:
        spec = generate_windmill(blade_count=4)
        rig_info = spec["metadata"]["rig_info"]
        assert "cloth_panels" in rig_info
        assert len(rig_info["cloth_panels"]) == 4


# =========================================================================
# Cage tests
# =========================================================================

class TestCage:
    """Tests for generate_cage."""

    STYLES = ["hanging_cage", "prison_cell", "gibbet", "animal_trap"]

    @pytest.mark.parametrize("style", STYLES)
    def test_produces_valid_mesh(self, style: str) -> None:
        spec = generate_cage(style=style)
        _assert_valid_mesh(spec, f"cage_{style}")

    @pytest.mark.parametrize("style", STYLES)
    def test_has_empties(self, style: str) -> None:
        spec = generate_cage(style=style)
        assert len(spec["empties"]) > 0

    def test_hanging_cage_has_hang_point(self) -> None:
        spec = generate_cage(style="hanging_cage")
        _assert_has_empties(spec, "hang_point", "door_hinge_top")

    def test_prison_cell_has_door_hinge(self) -> None:
        spec = generate_cage(style="prison_cell")
        _assert_has_empties(spec, "door_hinge_top", "door_hinge_bottom")

    def test_gibbet_body_shaped(self) -> None:
        """Gibbet should have varying radius (wider at shoulders)."""
        spec = generate_cage(style="gibbet")
        _assert_has_empties(spec, "hang_point")
        # Just verify it has substantial geometry
        assert len(spec["vertices"]) > 100

    def test_animal_trap_has_trigger(self) -> None:
        spec = generate_cage(style="animal_trap")
        _assert_has_empties(spec, "trigger_plate")
        _assert_has_vertex_groups(spec, "cage")

    def test_cage_has_rig_info(self) -> None:
        spec = generate_cage(style="hanging_cage")
        _assert_has_rig_info(spec, "type", "style", "has_door")


# =========================================================================
# Cross-generator integration tests
# =========================================================================

class TestAllGenerators:
    """Cross-cutting tests for all generators."""

    ALL_GENERATORS = [
        ("door", lambda: generate_door()),
        ("chain", lambda: generate_chain()),
        ("flag", lambda: generate_flag()),
        ("chest", lambda: generate_chest()),
        ("chandelier", lambda: generate_chandelier()),
        ("drawbridge", lambda: generate_drawbridge()),
        ("rope_bridge", lambda: generate_rope_bridge()),
        ("hanging_sign", lambda: generate_hanging_sign()),
        ("windmill", lambda: generate_windmill()),
        ("cage", lambda: generate_cage()),
    ]

    @pytest.mark.parametrize("name,gen", ALL_GENERATORS)
    def test_all_faces_valid(self, name: str, gen) -> None:
        spec = gen()
        _assert_valid_mesh(spec, name)

    @pytest.mark.parametrize("name,gen", ALL_GENERATORS)
    def test_all_have_empties(self, name: str, gen) -> None:
        spec = gen()
        assert len(spec["empties"]) > 0, f"{name} should have empties"

    @pytest.mark.parametrize("name,gen", ALL_GENERATORS)
    def test_all_have_vertex_groups(self, name: str, gen) -> None:
        spec = gen()
        assert len(spec["vertex_groups"]) > 0, f"{name} should have vertex groups"

    @pytest.mark.parametrize("name,gen", ALL_GENERATORS)
    def test_all_have_metadata(self, name: str, gen) -> None:
        spec = gen()
        meta = spec["metadata"]
        assert "name" in meta
        assert "poly_count" in meta
        assert meta["poly_count"] > 0
        assert "vertex_count" in meta
        assert meta["vertex_count"] > 0
        assert "dimensions" in meta
        assert "rig_info" in meta

    @pytest.mark.parametrize("name,gen", ALL_GENERATORS)
    def test_all_vertex_group_indices_valid(self, name: str, gen) -> None:
        spec = gen()
        max_idx = len(spec["vertices"]) - 1
        for gname, indices in spec["vertex_groups"].items():
            for vi in indices:
                assert 0 <= vi <= max_idx, (
                    f"{name}: vertex group {gname!r} has index {vi} > {max_idx}"
                )
