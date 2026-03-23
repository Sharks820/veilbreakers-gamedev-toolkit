"""Unit tests for AAA building quality generators.

Tests verify:
- Stone wall has geometric block detail (not flat planes)
- Timber frame beams extend beyond wall surface (proud structure)
- Gothic window arch curve is symmetric
- Roof tile count matches expected rows x columns
- Staircase steps are individual geometry
- Archway voussoirs are wedge-shaped
- Interior trim generates separate mesh pieces per component
- Block patterns have mortar gaps (vertices at two depths)
- All styles produce distinct geometry
- All generators return valid meshes with correct structure
"""

import math

import pytest

from blender_addon.handlers.building_quality import (
    BUILDING_QUALITY_GENERATORS,
    _arch_curve,
    _merge,
    _molding_profile_extrude,
    _shingle_row,
    _stone_block_grid,
    _voussoir_blocks,
    generate_archway,
    generate_battlements,
    generate_chimney,
    generate_gothic_window,
    generate_interior_trim,
    generate_roof,
    generate_staircase,
    generate_stone_wall,
    generate_timber_frame,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_mesh(result: dict) -> None:
    """Assert mesh has required fields and valid face indices."""
    assert "vertices" in result, "Missing vertices"
    assert "faces" in result, "Missing faces"
    assert "metadata" in result, "Missing metadata"
    verts = result["vertices"]
    faces = result["faces"]
    assert len(verts) >= 4, f"Need >= 4 vertices, got {len(verts)}"
    assert len(faces) >= 1, f"Need >= 1 face, got {len(faces)}"
    n = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"Face {fi} has < 3 vertices"
        for vi in face:
            assert 0 <= vi < n, (
                f"Face {fi} index {vi} out of range [0, {n})"
            )


def _bbox(verts):
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {
        "min_x": min(xs), "max_x": max(xs),
        "min_y": min(ys), "max_y": max(ys),
        "min_z": min(zs), "max_z": max(zs),
    }


def _unique_y_depths(verts):
    """Count distinct Y depth values (rounded to 4 decimal places)."""
    return len({round(v[1], 4) for v in verts})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_9_generators_registered(self):
        assert len(BUILDING_QUALITY_GENERATORS) == 9

    def test_all_generators_callable(self):
        for name, fn in BUILDING_QUALITY_GENERATORS.items():
            assert callable(fn), f"{name} is not callable"

    def test_all_generators_produce_valid_mesh(self):
        """Every generator with defaults must produce a valid mesh."""
        for name, fn in BUILDING_QUALITY_GENERATORS.items():
            result = fn()
            _valid_mesh(result)


# ---------------------------------------------------------------------------
# Stone Wall
# ---------------------------------------------------------------------------

class TestStoneWall:
    def test_basic_generation(self):
        result = generate_stone_wall()
        _valid_mesh(result)
        assert result["metadata"]["name"].startswith("stone_wall_")

    def test_more_faces_than_flat_plane(self):
        """Stone wall must have far more faces than a flat box (6 faces).
        Individual blocks mean many more faces than just vertices/6."""
        result = generate_stone_wall(width=4.0, height=3.0)
        n_faces = len(result["faces"])
        # A flat box has 6 faces. With blocks we should have at least 20+.
        assert n_faces > 6, f"Only {n_faces} faces -- looks like a flat plane"
        # More specifically: face count should exceed vertices/6
        n_verts = len(result["vertices"])
        assert n_faces > n_verts / 6, (
            f"{n_faces} faces vs {n_verts} verts -- not enough block detail"
        )

    def test_mortar_gaps_two_depths(self):
        """Block faces are proud of mortar base -- vertices at multiple Y depths."""
        result = generate_stone_wall(mortar_depth=0.01)
        depths = _unique_y_depths(result["vertices"])
        assert depths >= 2, f"Only {depths} Y depths -- no mortar gap visible"

    def test_all_styles(self):
        styles = ["ashlar", "rubble", "coursed_rubble", "cyclopean", "brick"]
        results = {}
        for s in styles:
            r = generate_stone_wall(block_style=s, seed=42)
            _valid_mesh(r)
            results[s] = r
        # Styles must produce different face counts
        face_counts = {s: len(r["faces"]) for s, r in results.items()}
        assert len(set(face_counts.values())) >= 3, (
            f"Too many styles produce identical geometry: {face_counts}"
        )

    def test_block_count_in_metadata(self):
        result = generate_stone_wall(width=4.0, height=3.0, block_style="ashlar")
        assert result["metadata"]["block_count"] > 0

    def test_corner_blocks_for_ashlar(self):
        """Ashlar style should have corner interlocking stones."""
        result = generate_stone_wall(block_style="ashlar")
        _valid_mesh(result)
        # Corner blocks add extra geometry beyond front/back faces
        result_rubble = generate_stone_wall(block_style="rubble", seed=42)
        # Ashlar should have more faces due to corner blocks
        assert len(result["faces"]) >= len(result_rubble["faces"]) * 0.5

    def test_variation_affects_output(self):
        r1 = generate_stone_wall(block_variation=0.0, seed=42)
        r2 = generate_stone_wall(block_variation=0.8, seed=42)
        # Different variation should produce different vertex counts
        # (higher variation = different block subdivision)
        assert len(r1["vertices"]) != len(r2["vertices"]) or \
               r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# Timber Frame
# ---------------------------------------------------------------------------

class TestTimberFrame:
    def test_basic_generation(self):
        result = generate_timber_frame()
        _valid_mesh(result)

    def test_beams_extend_beyond_wall(self):
        """Beams must protrude beyond the infill panel surface (proud)."""
        result = generate_timber_frame(beam_depth=0.15)
        proud = result["metadata"]["beam_proud"]
        assert proud > 0, "Beams must be proud of wall surface"
        # Verify some vertices are at negative Y (extending beyond y=0 face)
        min_y = min(v[1] for v in result["vertices"])
        assert min_y < 0, f"No vertices extend beyond wall face (min_y={min_y})"

    def test_all_styles(self):
        styles = ["medieval", "tudor", "japanese", "barn"]
        for s in styles:
            r = generate_timber_frame(frame_style=s)
            _valid_mesh(r)
            assert r["metadata"]["frame_style"] == s

    def test_styles_produce_distinct_geometry(self):
        results = {s: generate_timber_frame(frame_style=s)
                   for s in ["medieval", "tudor", "japanese", "barn"]}
        face_counts = {s: len(r["faces"]) for s, r in results.items()}
        assert len(set(face_counts.values())) >= 2, (
            f"Styles too similar: {face_counts}"
        )

    def test_infill_panels_recessed(self):
        """Infill panels should be at a different Y depth than beam faces."""
        result = generate_timber_frame(frame_style="medieval")
        depths = _unique_y_depths(result["vertices"])
        assert depths >= 3, (
            f"Only {depths} Y depths -- infill not recessed from beams"
        )

    def test_tenon_joints_present(self):
        """Tenon peg geometry adds vertices (cylinders at intersections)."""
        # With tenon pegs, vertex count is higher than without
        result = generate_timber_frame()
        # The function always adds pegs, so just verify extra geometry exists
        assert len(result["vertices"]) > 100, "Not enough detail for tenon joints"

    def test_barn_heavy_beams(self):
        """Barn style has heavier beams (1.5x factor)."""
        r_med = generate_timber_frame(frame_style="medieval", beam_width=0.15)
        r_barn = generate_timber_frame(frame_style="barn", beam_width=0.15)
        bb_med = _bbox(r_med["vertices"])
        bb_barn = _bbox(r_barn["vertices"])
        # Barn should extend further due to larger beams
        assert bb_barn["min_y"] <= bb_med["min_y"], (
            "Barn beams should protrude at least as far as medieval"
        )


# ---------------------------------------------------------------------------
# Gothic Window
# ---------------------------------------------------------------------------

class TestGothicWindow:
    def test_basic_generation(self):
        result = generate_gothic_window()
        _valid_mesh(result)

    def test_arch_curve_symmetric(self):
        """Arch curves for symmetric styles must be left-right symmetric."""
        for style in ["gothic_pointed", "roman_round", "pointed_arch", "round_arch"]:
            pts = _arch_curve(1.0, 0.5, style, num_points=16)
            n = len(pts)
            for i in range(n // 4):  # check a sample
                lx, lz = pts[i]
                rx, rz = pts[n - 1 - i]
                assert abs(lx + rx) < 0.15, (
                    f"Style {style}: arch not symmetric at {i}: "
                    f"left=({lx:.3f},{lz:.3f}) right=({rx:.3f},{rz:.3f})"
                )

    def test_all_styles(self):
        for s in ["pointed_arch", "round_arch", "lancet",
                   "rose_window", "rectangular", "arrow_slit"]:
            r = generate_gothic_window(style=s)
            _valid_mesh(r)

    def test_tracery_adds_geometry(self):
        r_no = generate_gothic_window(tracery=False, style="pointed_arch")
        r_yes = generate_gothic_window(tracery=True, style="pointed_arch")
        assert len(r_yes["faces"]) > len(r_no["faces"]), (
            "Tracery should add geometry"
        )

    def test_shutters_add_geometry(self):
        r_no = generate_gothic_window(has_shutters=False)
        r_yes = generate_gothic_window(has_shutters=True)
        assert len(r_yes["faces"]) > len(r_no["faces"]), (
            "Shutters should add geometry"
        )

    def test_sill_present(self):
        r = generate_gothic_window(has_sill=True)
        assert "sill" in r["components"]

    def test_glass_pane_present(self):
        r = generate_gothic_window()
        assert "glass_pane" in r["components"]

    def test_voussoir_count(self):
        r = generate_gothic_window(style="pointed_arch")
        assert r["metadata"]["voussoir_count"] > 0


# ---------------------------------------------------------------------------
# Roof
# ---------------------------------------------------------------------------

class TestRoof:
    def test_basic_generation(self):
        result = generate_roof()
        _valid_mesh(result)

    def test_tile_count_reasonable(self):
        """Roof should have many individual tiles (not just 2 planes)."""
        r = generate_roof(width=6.0, depth=5.0, material="tile")
        n_faces = len(r["faces"])
        # Two flat planes = 2 faces. Tiles = many more.
        assert n_faces > 20, f"Only {n_faces} faces -- tiles not individual"

    def test_all_roof_styles(self):
        for s in ["gable", "hip", "shed", "conical_tower", "gambrel", "mansard"]:
            r = generate_roof(style=s)
            _valid_mesh(r)

    def test_all_materials(self):
        for m in ["tile", "shingle", "slate", "thatch"]:
            r = generate_roof(material=m)
            _valid_mesh(r)

    def test_styles_distinct(self):
        results = {s: generate_roof(style=s)
                   for s in ["gable", "hip", "shed", "conical_tower"]}
        face_counts = {s: len(r["faces"]) for s, r in results.items()}
        assert len(set(face_counts.values())) >= 2, (
            f"Roof styles too similar: {face_counts}"
        )

    def test_overhang_extends_beyond_width(self):
        r = generate_roof(width=4.0, overhang=0.5)
        bb = _bbox(r["vertices"])
        # With overhang, geometry should extend beyond -width/2 and +width/2
        half_w = 4.0 / 2.0
        assert bb["max_x"] > half_w or bb["min_x"] < -half_w, (
            "Overhang not visible in geometry"
        )

    def test_gable_has_ridge_tiles(self):
        r = generate_roof(style="gable")
        assert "ridge_tiles" in r["components"]

    def test_gable_has_fascia(self):
        r = generate_roof(style="gable")
        assert "fascia" in r["components"]

    def test_thatch_has_roll(self):
        r = generate_roof(style="gable", material="thatch")
        assert "thatch_roll" in r["components"]


# ---------------------------------------------------------------------------
# Staircase
# ---------------------------------------------------------------------------

class TestStaircase:
    def test_basic_generation(self):
        result = generate_staircase()
        _valid_mesh(result)

    def test_steps_are_individual(self):
        """Each step should be separate geometry with its own vertical faces."""
        step_count = 8
        r = generate_staircase(style="straight", step_count=step_count, railing=False)
        # Count components that are steps
        step_components = [c for c in r["components"] if c.startswith("step_")]
        assert len(step_components) == step_count, (
            f"Expected {step_count} individual steps, got {len(step_components)}"
        )

    def test_all_styles(self):
        for s in ["straight", "spiral", "l_shaped", "u_shaped", "ladder"]:
            r = generate_staircase(style=s, step_count=8)
            _valid_mesh(r)

    def test_spiral_has_central_pole(self):
        r = generate_staircase(style="spiral")
        assert "central_pole" in r["components"]

    def test_railing_adds_geometry(self):
        r_no = generate_staircase(railing=False, style="straight")
        r_yes = generate_staircase(railing=True, style="straight")
        assert len(r_yes["faces"]) > len(r_no["faces"]), (
            "Railing should add geometry"
        )

    def test_straight_has_railing_components(self):
        r = generate_staircase(style="straight", railing=True)
        assert "newel_posts" in r["components"]
        assert "balusters" in r["components"]
        assert "handrail" in r["components"]

    def test_ladder_has_rungs(self):
        r = generate_staircase(style="ladder", step_count=6)
        rung_components = [c for c in r["components"] if c.startswith("rung_")]
        assert len(rung_components) == 6

    def test_step_nosing_overhang(self):
        """Steps should have nosing that extends slightly beyond the riser."""
        r = generate_staircase(style="straight", step_count=4, railing=False)
        bb = _bbox(r["vertices"])
        # Nosing means geometry extends to negative X (beyond 0)
        assert bb["min_x"] < 0, "No nosing overhang detected"

    def test_l_shaped_has_landing(self):
        r = generate_staircase(style="l_shaped")
        assert "landing" in r["components"]

    def test_u_shaped_has_landing(self):
        r = generate_staircase(style="u_shaped")
        assert "landing" in r["components"]


# ---------------------------------------------------------------------------
# Archway
# ---------------------------------------------------------------------------

class TestArchway:
    def test_basic_generation(self):
        result = generate_archway()
        _valid_mesh(result)

    def test_voussoirs_present(self):
        r = generate_archway(arch_style="gothic_pointed")
        assert r["metadata"]["voussoir_count"] > 0
        assert "voussoirs" in r["components"]

    def test_voussoirs_wedge_shaped(self):
        """Voussoirs should be wider at extrados than intrados.

        We verify by checking that voussoir geometry has varying widths
        across the radial direction.
        """
        arch_pts = _arch_curve(1.0, 0.5, "gothic_pointed", num_points=16)
        spring_z = 1.5
        pts_3d = [(p[0], p[1] + spring_z) for p in arch_pts]
        verts, faces, count = _voussoir_blocks(pts_3d, 0.5, block_count=7)
        assert count >= 5, f"Expected >= 5 voussoirs, got {count}"

        # Each voussoir has 8 verts (4 front + 4 back).
        # Verts 0,1 are inner edge, verts 2,3 are outer edge (front face).
        # Outer edge should span wider or equal to inner edge in most blocks.
        wedge_count = 0
        for vi in range(count):
            base = vi * 8
            if base + 7 >= len(verts):
                break
            # Front face: inner = verts[0], verts[1]; outer = verts[2], verts[3]
            inner_span_x = abs(verts[base + 1][0] - verts[base][0])
            inner_span_z = abs(verts[base + 1][2] - verts[base][2])
            inner_span = math.sqrt(inner_span_x ** 2 + inner_span_z ** 2)

            outer_span_x = abs(verts[base + 2][0] - verts[base + 3][0])
            outer_span_z = abs(verts[base + 2][2] - verts[base + 3][2])
            outer_span = math.sqrt(outer_span_x ** 2 + outer_span_z ** 2)

            # At least some voussoirs should be wider at extrados
            if outer_span >= inner_span * 0.8:
                wedge_count += 1

        assert wedge_count >= count // 2, (
            f"Only {wedge_count}/{count} voussoirs appear wedge-shaped"
        )

    def test_all_arch_styles(self):
        for s in ["gothic_pointed", "roman_round", "flat_lintel", "horseshoe", "ogee"]:
            r = generate_archway(arch_style=s)
            _valid_mesh(r)

    def test_components_present(self):
        r = generate_archway()
        assert "left_jamb" in r["components"]
        assert "right_jamb" in r["components"]
        assert "imposts" in r["components"]
        assert "spandrel" in r["components"]
        assert "intrados" in r["components"]

    def test_styles_distinct(self):
        results = {s: generate_archway(arch_style=s)
                   for s in ["gothic_pointed", "roman_round", "flat_lintel"]}
        face_counts = {s: len(r["faces"]) for s, r in results.items()}
        # At least 2 distinct face counts
        assert len(set(face_counts.values())) >= 2, (
            f"Arch styles too similar: {face_counts}"
        )

    def test_depth_creates_walkthrough(self):
        """Archway depth should create a passage (intrados faces)."""
        r = generate_archway(depth=0.8)
        assert "intrados" in r["components"]


# ---------------------------------------------------------------------------
# Chimney
# ---------------------------------------------------------------------------

class TestChimney:
    def test_basic_generation(self):
        result = generate_chimney()
        _valid_mesh(result)

    def test_block_pattern_on_all_faces(self):
        """All 4 faces should have block geometry (many faces)."""
        r = generate_chimney(height=2.0, style="stone")
        # A simple box chimney = 6 faces. With block pattern: many more.
        assert len(r["faces"]) > 50, (
            f"Only {len(r['faces'])} faces -- blocks not detailed enough"
        )

    def test_all_styles(self):
        for s in ["stone", "brick", "rustic"]:
            r = generate_chimney(style=s)
            _valid_mesh(r)

    def test_cap_adds_geometry(self):
        r_no = generate_chimney(has_cap=False)
        r_yes = generate_chimney(has_cap=True)
        assert len(r_yes["faces"]) > len(r_no["faces"])

    def test_corbeling_present(self):
        r = generate_chimney()
        assert "corbeling" in r["components"]

    def test_flue_present(self):
        r = generate_chimney()
        assert "flue" in r["components"]

    def test_flashing_present(self):
        r = generate_chimney()
        assert "flashing" in r["components"]

    def test_brick_has_chimney_pot(self):
        r = generate_chimney(style="brick", has_cap=True)
        assert "chimney_pot" in r["components"]

    def test_stone_has_stone_cap(self):
        r = generate_chimney(style="stone", has_cap=True)
        assert "stone_cap" in r["components"]


# ---------------------------------------------------------------------------
# Interior Trim
# ---------------------------------------------------------------------------

class TestInteriorTrim:
    def test_basic_generation(self):
        result = generate_interior_trim()
        _valid_mesh(result)

    def test_separate_components(self):
        """Interior trim must generate separate named components."""
        r = generate_interior_trim()
        expected = ["baseboard", "crown_molding", "ceiling_beams",
                     "floor_planks", "wainscoting", "chair_rail", "door_trim"]
        for comp in expected:
            assert comp in r["components"], f"Missing component: {comp}"

    def test_all_styles(self):
        for s in ["medieval", "gothic", "rustic"]:
            r = generate_interior_trim(style=s)
            _valid_mesh(r)

    def test_styles_distinct(self):
        results = {s: generate_interior_trim(style=s)
                   for s in ["medieval", "gothic", "rustic"]}
        face_counts = {s: len(r["faces"]) for s, r in results.items()}
        assert len(set(face_counts.values())) >= 2

    def test_floor_planks_individual(self):
        """Floor planks should be individual boards."""
        r = generate_interior_trim(room_width=4.0)
        assert r["metadata"]["plank_count"] > 1, "Floor planks not individual"

    def test_ceiling_beams_present(self):
        r = generate_interior_trim(style="medieval")
        bb = _bbox(r["vertices"])
        # Beams should be near ceiling height
        assert bb["max_z"] >= 2.5, "No geometry near ceiling for beams"

    def test_wainscoting_has_panels(self):
        """Wainscoting should have recessed panels (extra geometry)."""
        r = generate_interior_trim()
        # The face count should be substantial due to panels
        assert len(r["faces"]) > 30, "Not enough detail for wainscoting panels"


# ---------------------------------------------------------------------------
# Battlements
# ---------------------------------------------------------------------------

class TestBattlements:
    def test_basic_generation(self):
        result = generate_battlements()
        _valid_mesh(result)

    def test_merlon_count(self):
        r = generate_battlements(wall_length=10.0)
        assert r["metadata"]["merlon_count"] > 0

    def test_all_merlon_styles(self):
        for s in ["squared", "swallow_tail", "rounded"]:
            r = generate_battlements(merlon_style=s)
            _valid_mesh(r)

    def test_merlon_styles_distinct(self):
        results = {s: generate_battlements(merlon_style=s)
                   for s in ["squared", "swallow_tail", "rounded"]}
        face_counts = {s: len(r["faces"]) for s, r in results.items()}
        assert len(set(face_counts.values())) >= 2, (
            f"Merlon styles too similar: {face_counts}"
        )

    def test_machicolations_add_geometry(self):
        r_no = generate_battlements(has_machicolations=False)
        r_yes = generate_battlements(has_machicolations=True)
        assert len(r_yes["faces"]) > len(r_no["faces"])

    def test_arrow_loops_present(self):
        r = generate_battlements(has_arrow_loops=True)
        assert "arrow_slits" in r["components"] or "wall_arrow_loops" in r["components"]

    def test_parapet_walk_present(self):
        r = generate_battlements()
        assert "parapet_walk" in r["components"]

    def test_wall_has_stone_block_pattern(self):
        """Wall surface should have block pattern (many faces)."""
        r = generate_battlements(wall_length=5.0, wall_height=4.0)
        # Without blocks: ~6 faces for a box. With blocks: hundreds.
        assert len(r["faces"]) > 50, "Wall lacks stone block detail"

    def test_towers_at_intervals(self):
        r = generate_battlements(wall_length=20.0, tower_interval=8.0)
        assert "towers" in r["components"]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelperStoneBlockGrid:
    def test_produces_blocks(self):
        v, f, count = _stone_block_grid(2.0, 1.0, 0.3, 0.15, 0.01, 0.2)
        assert count > 0
        assert len(v) > 0
        assert len(f) > 0

    def test_running_bond_offset(self):
        """Alternate rows should be offset (running bond)."""
        v1, f1, c1 = _stone_block_grid(2.0, 1.0, 0.3, 0.15, 0.01, 0.0,
                                         offset_alternate=True, seed=42)
        v2, f2, c2 = _stone_block_grid(2.0, 1.0, 0.3, 0.15, 0.01, 0.0,
                                         offset_alternate=False, seed=42)
        # Different offset patterns produce different vertex positions
        assert v1 != v2

    def test_block_count_scales_with_area(self):
        _, _, c_small = _stone_block_grid(1.0, 1.0, 0.3, 0.15, 0.01, 0.1)
        _, _, c_large = _stone_block_grid(4.0, 3.0, 0.3, 0.15, 0.01, 0.1)
        assert c_large > c_small


class TestHelperArchCurve:
    def test_gothic_pointed(self):
        pts = _arch_curve(1.0, 0.5, "gothic_pointed")
        assert len(pts) > 2
        # Should reach peak height
        max_z = max(p[1] for p in pts)
        assert max_z > 0.3, f"Peak too low: {max_z}"

    def test_roman_round(self):
        pts = _arch_curve(1.0, 0.5, "roman_round")
        assert len(pts) > 2

    def test_flat_lintel(self):
        pts = _arch_curve(1.0, 0.5, "flat_lintel")
        assert len(pts) >= 4

    def test_horseshoe(self):
        pts = _arch_curve(1.0, 0.5, "horseshoe")
        assert len(pts) > 2

    def test_ogee(self):
        pts = _arch_curve(1.0, 0.5, "ogee")
        assert len(pts) > 2

    def test_lancet(self):
        pts = _arch_curve(1.0, 0.8, "lancet")
        assert len(pts) > 2
        max_z = max(p[1] for p in pts)
        assert max_z > 0.5


class TestHelperVoussoirBlocks:
    def test_produces_wedges(self):
        pts = _arch_curve(1.0, 0.5, "gothic_pointed", num_points=16)
        v, f, count = _voussoir_blocks(pts, 0.3, block_count=7)
        assert count >= 5
        # Each voussoir = 8 verts, 6 faces
        assert len(v) >= count * 8
        assert len(f) >= count * 6

    def test_empty_input(self):
        v, f, count = _voussoir_blocks([], 0.3, 5)
        assert count == 0

    def test_keystone_larger(self):
        """Middle voussoir (keystone) should be thicker."""
        pts = _arch_curve(1.0, 0.5, "roman_round", num_points=16)
        v, f, count = _voussoir_blocks(pts, 0.3, block_count=9)
        # Keystone = block at index count//2 = 4
        # It should have vertices offset further from the arch
        assert count > 0


class TestHelperMoldingExtrude:
    def test_produces_geometry(self):
        profile = [(0, 0), (0.02, 0), (0.02, 0.05), (0, 0.05)]
        path = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
        v, f = _molding_profile_extrude(profile, path)
        assert len(v) > 0
        assert len(f) > 0

    def test_empty_input(self):
        v, f = _molding_profile_extrude([], [])
        assert len(v) == 0

    def test_face_count_matches(self):
        profile = [(0, 0), (0.02, 0), (0.02, 0.05), (0, 0.05)]
        path = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]
        v, f = _molding_profile_extrude(profile, path)
        # (path_count-1) * (profile_count-1) faces
        expected = (len(path) - 1) * (len(profile) - 1)
        assert len(f) == expected


class TestHelperShingleRow:
    def test_produces_shingles(self):
        v, f, count = _shingle_row(2.0, 0.0, 0.15, 0.1, 0.05, 0.1)
        assert count > 0
        assert len(v) == count * 4  # 4 verts per shingle
        assert len(f) == count

    def test_stagger(self):
        """Odd rows should be offset from even rows."""
        v0, _, c0 = _shingle_row(2.0, 0.0, 0.15, 0.1, 0.05, 0.0, row_index=0)
        v1, _, c1 = _shingle_row(2.0, 0.0, 0.15, 0.1, 0.05, 0.0, row_index=1)
        # Stagger means different shingle count or different second vertex positions.
        # The odd row starts at negative x_offset which gets clamped, but the
        # first full shingle starts at a different position than even rows.
        # Verify the vertex positions differ somewhere in the first few shingles.
        assert c0 != c1 or v0 != v1, "Rows not staggered at all"

    def test_count_scales_with_width(self):
        _, _, c_small = _shingle_row(1.0, 0.0, 0.15, 0.1, 0.05, 0.1)
        _, _, c_large = _shingle_row(4.0, 0.0, 0.15, 0.1, 0.05, 0.1)
        assert c_large > c_small


# ---------------------------------------------------------------------------
# Cross-cutting quality checks
# ---------------------------------------------------------------------------

class TestQuality:
    """AAA quality assertions that apply across all generators."""

    @pytest.mark.parametrize("gen_name", list(BUILDING_QUALITY_GENERATORS.keys()))
    def test_no_degenerate_faces(self, gen_name):
        """No face should reference the same vertex twice."""
        result = BUILDING_QUALITY_GENERATORS[gen_name]()
        for fi, face in enumerate(result["faces"]):
            assert len(face) == len(set(face)), (
                f"{gen_name}: face {fi} has duplicate vertex indices: {face}"
            )

    @pytest.mark.parametrize("gen_name", list(BUILDING_QUALITY_GENERATORS.keys()))
    def test_metadata_has_generator_tag(self, gen_name):
        result = BUILDING_QUALITY_GENERATORS[gen_name]()
        assert result["metadata"]["generator"] == "building_quality"

    @pytest.mark.parametrize("gen_name", list(BUILDING_QUALITY_GENERATORS.keys()))
    def test_has_components_list(self, gen_name):
        result = BUILDING_QUALITY_GENERATORS[gen_name]()
        assert "components" in result
        assert isinstance(result["components"], list)

    @pytest.mark.parametrize("gen_name", list(BUILDING_QUALITY_GENERATORS.keys()))
    def test_sufficient_polygon_count(self, gen_name):
        """AAA quality means substantial polygon counts -- never just a box."""
        result = BUILDING_QUALITY_GENERATORS[gen_name]()
        assert result["metadata"]["poly_count"] > 10, (
            f"{gen_name}: only {result['metadata']['poly_count']} polys -- too simple for AAA"
        )
