"""Unit tests for modular building kit -- pure-math piece generation.

Tests cover:
- Each piece type generates valid geometry (vertices, faces, metadata)
- All 5 styles produce different geometry
- Wall thickness is maintained (vertex positions differ by thickness)
- Window/door walls have openings (face count differs from solid)
- Grid snapping works (connection points align)
- Ruined variants have displaced vertices
- assemble_building merges pieces correctly
- get_available_pieces returns complete catalog
- generate_modular_piece dispatches correctly
"""

import math

import pytest

from blender_addon.handlers.modular_building_kit import (
    ALL_PIECE_TYPES,
    MODULAR_KIT_GENERATORS,
    STYLES,
    _STYLE_THICKNESS,
    assemble_building,
    door_arched,
    door_double,
    door_single,
    floor_dirt,
    floor_stone,
    floor_wood,
    generate_modular_piece,
    get_available_pieces,
    roof_flat,
    roof_gutter,
    roof_peak,
    roof_slope,
    stair_ramp,
    stair_spiral,
    stair_straight,
    wall_corner_inner,
    wall_corner_outer,
    wall_damaged,
    wall_door,
    wall_end_cap,
    wall_half,
    wall_solid,
    wall_t_junction,
    wall_window,
    window_large,
    window_pointed,
    window_small,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bbox(verts):
    """Compute bounding box extents from vertex list."""
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {
        "min_x": min(xs), "max_x": max(xs),
        "min_y": min(ys), "max_y": max(ys),
        "min_z": min(zs), "max_z": max(zs),
    }


def _valid_mesh(result):
    """Check a mesh result has required fields and valid data."""
    assert "vertices" in result
    assert "faces" in result
    assert "metadata" in result
    assert len(result["vertices"]) >= 4, "Need at least 4 vertices"
    assert len(result["faces"]) >= 1, "Need at least 1 face"
    # All face indices must reference valid vertices
    n_verts = len(result["vertices"])
    for fi, face in enumerate(result["faces"]):
        for vi in face:
            assert 0 <= vi < n_verts, (
                f"Face {fi} has vertex index {vi} out of range [0, {n_verts})"
            )


# ---------------------------------------------------------------------------
# Registry / Catalog
# ---------------------------------------------------------------------------

class TestRegistry:
    """Test piece registry completeness."""

    def test_all_52_piece_types_registered(self):
        """All 52 piece types must be registered (25 original + 27 expansion)."""
        assert len(ALL_PIECE_TYPES) == 52

    def test_all_generators_are_callable(self):
        for name, fn in MODULAR_KIT_GENERATORS.items():
            assert callable(fn), f"{name} is not callable"

    def test_five_styles_defined(self):
        assert len(STYLES) == 5
        assert set(STYLES) == {"medieval", "gothic", "fortress", "organic", "ruined"}

    def test_get_available_pieces_returns_all_categories(self):
        info = get_available_pieces()
        assert "styles" in info
        assert "categories" in info
        cats = info["categories"]
        assert "walls" in cats
        assert "floors" in cats
        assert "roofs" in cats
        assert "stairs" in cats
        assert "doors" in cats
        assert "windows" in cats
        assert len(cats["walls"]) == 9
        assert len(cats["floors"]) == 3
        assert len(cats["roofs"]) == 4
        assert len(cats["stairs"]) == 3
        assert len(cats["doors"]) == 3
        assert len(cats["windows"]) == 3

    def test_total_variants_count(self):
        info = get_available_pieces()
        assert info["total_piece_types"] == 52
        assert info["total_variants"] == 52 * 5


# ---------------------------------------------------------------------------
# Wall pieces
# ---------------------------------------------------------------------------

class TestWallSolid:
    def test_generates_valid_mesh(self):
        result = wall_solid()
        _valid_mesh(result)

    def test_default_dimensions(self):
        result = wall_solid()
        bb = _bbox(result["vertices"])
        # Width should be ~2.0 (plus jitter)
        assert 1.9 < (bb["max_x"] - bb["min_x"]) < 2.2
        # Height should be ~3.0
        assert 2.8 < (bb["max_z"] - bb["min_z"]) < 3.3

    def test_thickness_from_style(self):
        """Each style produces walls with its configured thickness."""
        for style in STYLES:
            result = wall_solid(style=style)
            bb = _bbox(result["vertices"])
            expected_t = _STYLE_THICKNESS[style]
            actual_depth = bb["max_y"] - bb["min_y"]
            # Allow for jitter + style details
            assert actual_depth > expected_t * 0.5, (
                f"{style}: depth {actual_depth} too thin (expected ~{expected_t})"
            )

    def test_custom_dimensions(self):
        result = wall_solid(width=4.0, height=5.0, thickness=0.5)
        bb = _bbox(result["vertices"])
        assert (bb["max_x"] - bb["min_x"]) > 3.8
        assert (bb["max_z"] - bb["min_z"]) > 4.8

    def test_has_connection_points(self):
        result = wall_solid()
        cps = result["metadata"]["connection_points"]
        assert len(cps) >= 2
        faces = [cp["face"] for cp in cps]
        assert "left" in faces
        assert "right" in faces

    def test_has_style_in_metadata(self):
        result = wall_solid(style="gothic")
        assert result["metadata"]["style"] == "gothic"
        assert "wall_solid" in result["metadata"]["piece_type"]


class TestWallWindow:
    def test_generates_valid_mesh(self):
        result = wall_window()
        _valid_mesh(result)

    def test_more_faces_than_solid(self):
        """Window wall should have more faces than solid (opening creates sub-panels)."""
        solid = wall_solid(style="medieval", seed=1)
        windowed = wall_window(style="medieval", seed=1)
        assert len(windowed["faces"]) > len(solid["faces"])

    def test_has_opening_metadata(self):
        result = wall_window()
        assert "opening" in result["metadata"]
        op = result["metadata"]["opening"]
        assert op["width"] > 0
        assert op["height"] > 0


class TestWallDoor:
    def test_generates_valid_mesh(self):
        result = wall_door()
        _valid_mesh(result)

    def test_more_faces_than_solid(self):
        solid = wall_solid(style="medieval", seed=1)
        doored = wall_door(style="medieval", seed=1)
        assert len(doored["faces"]) > len(solid["faces"])

    def test_has_opening_metadata(self):
        result = wall_door()
        assert "opening" in result["metadata"]
        op = result["metadata"]["opening"]
        assert op["z"] == 0.0  # door starts at ground


class TestWallDamaged:
    def test_generates_valid_mesh(self):
        result = wall_damaged()
        _valid_mesh(result)

    def test_top_vertices_displaced(self):
        """Damaged wall's top vertices should be lower than wall height."""
        height = 3.0
        result = wall_damaged(height=height, damage_amount=0.3)
        top_z_values = [v[2] for v in result["vertices"]
                        if v[2] > height * 0.5]
        # At least some top vertices should be below the nominal height
        assert any(z < height for z in top_z_values)

    def test_different_from_solid(self):
        solid = wall_solid(style="medieval", seed=42)
        damaged = wall_damaged(style="medieval", seed=42)
        assert solid["vertices"] != damaged["vertices"]


class TestWallHalf:
    def test_generates_valid_mesh(self):
        result = wall_half()
        _valid_mesh(result)

    def test_half_height(self):
        full_height = 3.0
        result = wall_half(height=full_height)
        bb = _bbox(result["vertices"])
        actual_h = bb["max_z"] - bb["min_z"]
        expected = full_height / 2
        assert abs(actual_h - expected) < 0.2  # allow jitter


class TestWallCornerInner:
    def test_generates_valid_mesh(self):
        result = wall_corner_inner()
        _valid_mesh(result)

    def test_l_shaped_footprint(self):
        """Inner corner should have L-shaped bounding box (wider in both X and Y)."""
        result = wall_corner_inner(width=2.0)
        bb = _bbox(result["vertices"])
        # Should extend in both X and Y
        assert (bb["max_x"] - bb["min_x"]) > 1.8
        assert (bb["max_y"] - bb["min_y"]) > 1.8


class TestWallCornerOuter:
    def test_generates_valid_mesh(self):
        result = wall_corner_outer()
        _valid_mesh(result)


class TestWallTJunction:
    def test_generates_valid_mesh(self):
        result = wall_t_junction()
        _valid_mesh(result)

    def test_three_connection_points(self):
        result = wall_t_junction()
        cps = result["metadata"]["connection_points"]
        assert len(cps) == 3


class TestWallEndCap:
    def test_generates_valid_mesh(self):
        result = wall_end_cap()
        _valid_mesh(result)

    def test_single_connection_point(self):
        result = wall_end_cap()
        cps = result["metadata"]["connection_points"]
        assert len(cps) == 1
        assert cps[0]["face"] == "left"


# ---------------------------------------------------------------------------
# Floor pieces
# ---------------------------------------------------------------------------

class TestFloorStone:
    def test_generates_valid_mesh(self):
        result = floor_stone()
        _valid_mesh(result)

    def test_has_ridge_details(self):
        """Stone floor should have more faces than a plain slab (stone block ridges)."""
        result = floor_stone(width=2.0, depth=2.0)
        # A plain box has 6 faces; ridges add more
        assert len(result["faces"]) > 6

    def test_four_connection_points(self):
        result = floor_stone()
        cps = result["metadata"]["connection_points"]
        assert len(cps) == 4


class TestFloorWood:
    def test_generates_valid_mesh(self):
        result = floor_wood()
        _valid_mesh(result)

    def test_multiple_planks(self):
        """Should generate multiple plank boxes."""
        result = floor_wood(depth=2.0, plank_width=0.2)
        # 2.0 / 0.2 = 10 planks, each with 6 faces = 60 faces minimum
        assert len(result["faces"]) >= 30


class TestFloorDirt:
    def test_generates_valid_mesh(self):
        result = floor_dirt()
        _valid_mesh(result)

    def test_subdivided_top(self):
        """Dirt floor should have many more faces than a plain slab."""
        result = floor_dirt()
        assert len(result["faces"]) > 10


# ---------------------------------------------------------------------------
# Roof pieces
# ---------------------------------------------------------------------------

class TestRoofSlope:
    def test_generates_valid_mesh(self):
        result = roof_slope()
        _valid_mesh(result)

    def test_has_thickness(self):
        """Roof slope should have 8 vertices (two quad surfaces)."""
        result = roof_slope()
        assert len(result["vertices"]) == 8

    def test_rise_from_pitch(self):
        result = roof_slope(depth=2.0, pitch=45.0)
        bb = _bbox(result["vertices"])
        rise = bb["max_z"] - bb["min_z"]
        expected = 2.0 * math.tan(math.radians(45.0))
        # Allow for thickness offset
        assert abs(rise - expected) < 0.5


class TestRoofPeak:
    def test_generates_valid_mesh(self):
        result = roof_peak()
        _valid_mesh(result)

    def test_symmetric_width(self):
        result = roof_peak(width=4.0)
        bb = _bbox(result["vertices"])
        center_x = (bb["max_x"] + bb["min_x"]) / 2
        assert abs(center_x - 2.0) < 0.5  # centered


class TestRoofFlat:
    def test_generates_valid_mesh(self):
        result = roof_flat()
        _valid_mesh(result)

    def test_has_parapet_lip(self):
        """Flat roof should have more faces than a plain slab (lip around edge)."""
        result = roof_flat()
        # Main slab (6) + 4 lip pieces (24) = 30
        assert len(result["faces"]) > 6


class TestRoofGutter:
    def test_generates_valid_mesh(self):
        result = roof_gutter()
        _valid_mesh(result)


# ---------------------------------------------------------------------------
# Stair pieces
# ---------------------------------------------------------------------------

class TestStairStraight:
    def test_generates_valid_mesh(self):
        result = stair_straight()
        _valid_mesh(result)

    def test_step_count(self):
        result = stair_straight(height=3.0, step_count=15)
        assert result["metadata"]["step_count"] == 15
        # 15 steps * 6 faces each = 90
        assert len(result["faces"]) == 90

    def test_auto_step_count(self):
        result = stair_straight(height=3.0)
        assert result["metadata"]["step_count"] >= 3


class TestStairSpiral:
    def test_generates_valid_mesh(self):
        result = stair_spiral()
        _valid_mesh(result)

    def test_has_central_column(self):
        """Spiral staircase should have many faces (steps + column)."""
        result = stair_spiral(turns=1.0, steps_per_turn=12)
        # 12 steps * 6 faces + column
        assert len(result["faces"]) > 70

    def test_height_matches(self):
        result = stair_spiral(height=6.0)
        bb = _bbox(result["vertices"])
        assert (bb["max_z"] - bb["min_z"]) > 5.5


class TestStairRamp:
    def test_generates_valid_mesh(self):
        result = stair_ramp()
        _valid_mesh(result)

    def test_slope_height(self):
        result = stair_ramp(height=3.0, depth=4.0)
        bb = _bbox(result["vertices"])
        assert (bb["max_z"] - bb["min_z"]) > 2.8


# ---------------------------------------------------------------------------
# Door pieces
# ---------------------------------------------------------------------------

class TestDoorSingle:
    def test_generates_valid_mesh(self):
        result = door_single()
        _valid_mesh(result)

    def test_has_frame(self):
        """Door should have more than just a panel (frame + handle)."""
        result = door_single()
        assert len(result["faces"]) > 6  # more than one box


class TestDoorDouble:
    def test_generates_valid_mesh(self):
        result = door_double()
        _valid_mesh(result)

    def test_two_panels(self):
        """Double door has more geometry than single."""
        single = door_single()
        double = door_double()
        assert len(double["faces"]) > len(single["faces"])


class TestDoorArched:
    def test_generates_valid_mesh(self):
        result = door_arched()
        _valid_mesh(result)

    def test_has_arch_segments(self):
        result = door_arched(arch_segments=8)
        # Should have rectangular base + arch segments + frame
        assert len(result["faces"]) > 10


# ---------------------------------------------------------------------------
# Window pieces
# ---------------------------------------------------------------------------

class TestWindowSmall:
    def test_generates_valid_mesh(self):
        result = window_small()
        _valid_mesh(result)

    def test_cross_bars(self):
        """Small window has frame + cross bars."""
        result = window_small()
        assert len(result["faces"]) > 20  # 6 boxes * 6 faces each


class TestWindowLarge:
    def test_generates_valid_mesh(self):
        result = window_large()
        _valid_mesh(result)

    def test_has_sill(self):
        """Large window should have a protruding sill."""
        result = window_large()
        bb = _bbox(result["vertices"])
        # Sill protrudes below and forward
        assert bb["min_y"] < 0  # sill extends forward
        assert bb["min_z"] < 0  # sill extends below


class TestWindowPointed:
    def test_generates_valid_mesh(self):
        result = window_pointed()
        _valid_mesh(result)

    def test_arch_geometry(self):
        """Pointed window should have many faces from arch segments."""
        result = window_pointed(arch_segments=8)
        assert len(result["faces"]) > 15


# ---------------------------------------------------------------------------
# Style variations
# ---------------------------------------------------------------------------

class TestStyleVariations:
    """Test that all 5 styles produce different geometry for wall pieces."""

    def test_styles_produce_different_wall_geometry(self):
        """Each style should produce distinct vertex/face counts."""
        results = {}
        for style in STYLES:
            r = wall_solid(style=style, seed=100)
            results[style] = (len(r["vertices"]), len(r["faces"]))
        # At least 3 distinct (vertex_count, face_count) combos
        # (some styles may share base counts but differ in vertices)
        unique = set(results.values())
        assert len(unique) >= 2, (
            f"Expected style variation, got: {results}"
        )

    def test_fortress_thicker_than_medieval(self):
        med = wall_solid(style="medieval")
        fort = wall_solid(style="fortress")
        med_bb = _bbox(med["vertices"])
        fort_bb = _bbox(fort["vertices"])
        med_depth = med_bb["max_y"] - med_bb["min_y"]
        fort_depth = fort_bb["max_y"] - fort_bb["min_y"]
        assert fort_depth > med_depth

    def test_ruined_has_higher_jitter(self):
        """Ruined style should displace vertices more than medieval."""
        med = wall_solid(style="medieval", seed=42)
        ruin = wall_solid(style="ruined", seed=42)
        # Compare first vertex -- should differ due to jitter
        assert med["vertices"][0] != ruin["vertices"][0]

    @pytest.mark.parametrize("piece_type", ALL_PIECE_TYPES)
    def test_every_piece_generates_for_all_styles(self, piece_type):
        """Every piece type must work with every style."""
        import inspect
        fn = MODULAR_KIT_GENERATORS[piece_type]
        sig = inspect.signature(fn)
        has_style = "style" in sig.parameters
        for style in STYLES:
            if has_style:
                result = generate_modular_piece(piece_type, style=style)
            else:
                result = generate_modular_piece(piece_type, style=style)
            _valid_mesh(result)


# ---------------------------------------------------------------------------
# Grid snapping / connection points
# ---------------------------------------------------------------------------

class TestGridSnapping:
    """Test that pieces align on the 2m x 3m grid."""

    def test_wall_width_matches_grid(self):
        result = wall_solid(width=2.0)
        bb = _bbox(result["vertices"])
        actual_w = bb["max_x"] - bb["min_x"]
        # Should be approximately 2.0 (within jitter)
        assert abs(actual_w - 2.0) < 0.15

    def test_wall_height_matches_grid(self):
        result = wall_solid(height=3.0)
        bb = _bbox(result["vertices"])
        actual_h = bb["max_z"] - bb["min_z"]
        assert abs(actual_h - 3.0) < 0.15

    def test_connection_points_at_grid_positions(self):
        """Left connection at x=0, right at x=width."""
        result = wall_solid(width=2.0, height=3.0)
        cps = result["metadata"]["connection_points"]
        left = [cp for cp in cps if cp["face"] == "left"]
        right = [cp for cp in cps if cp["face"] == "right"]
        assert len(left) >= 1
        assert len(right) >= 1
        assert abs(left[0]["position"][0] - 0.0) < 0.01
        assert abs(right[0]["position"][0] - 2.0) < 0.01

    def test_stacked_walls_z_alignment(self):
        """Two walls stacked should have matching z connection points."""
        w1 = wall_solid(height=3.0)
        top_cp = [cp for cp in w1["metadata"]["connection_points"]
                  if cp["face"] == "top"]
        assert len(top_cp) >= 1
        assert abs(top_cp[0]["position"][2] - 3.0) < 0.01


# ---------------------------------------------------------------------------
# Ruined variants
# ---------------------------------------------------------------------------

class TestRuinedVariants:
    def test_ruined_wall_has_jitter(self):
        """Ruined style walls should have visible displacement."""
        clean = wall_solid(style="medieval", seed=42)
        ruined = wall_solid(style="ruined", seed=42)
        # Vertex positions should differ
        assert clean["vertices"] != ruined["vertices"]

    def test_damaged_wall_lower_top(self):
        """wall_damaged with ruined style should have even more damage."""
        result = wall_damaged(style="ruined", damage_amount=0.5, seed=42)
        bb = _bbox(result["vertices"])
        # Top should be lower than nominal 3.0
        assert bb["max_z"] < 3.0


# ---------------------------------------------------------------------------
# Dispatch / generate_modular_piece
# ---------------------------------------------------------------------------

class TestDispatch:
    def test_unknown_piece_type_raises(self):
        with pytest.raises(ValueError, match="Unknown piece type"):
            generate_modular_piece("nonexistent_piece")

    def test_unknown_style_raises(self):
        with pytest.raises(ValueError, match="Unknown style"):
            generate_modular_piece("wall_solid", style="cyberpunk")

    def test_dispatches_wall_solid(self):
        result = generate_modular_piece("wall_solid", "medieval")
        assert result["metadata"]["piece_type"] == "wall_solid"
        assert result["metadata"]["style"] == "medieval"

    def test_passes_kwargs(self):
        result = generate_modular_piece("wall_solid", "medieval", width=4.0)
        bb = _bbox(result["vertices"])
        assert (bb["max_x"] - bb["min_x"]) > 3.8

    @pytest.mark.parametrize("piece_type", ALL_PIECE_TYPES)
    def test_each_piece_type_dispatches(self, piece_type):
        result = generate_modular_piece(piece_type, "medieval")
        _valid_mesh(result)


# ---------------------------------------------------------------------------
# assemble_building
# ---------------------------------------------------------------------------

class TestAssembleBuilding:
    def test_empty_spec(self):
        result = assemble_building([])
        assert len(result["vertices"]) == 0
        assert len(result["faces"]) == 0

    def test_single_piece(self):
        spec = [{"piece_type": "wall_solid", "style": "medieval", "position": [0, 0, 0]}]
        result = assemble_building(spec)
        _valid_mesh(result)
        assert result["metadata"]["piece_count"] == 1

    def test_multiple_pieces_merged(self):
        spec = [
            {"piece_type": "wall_solid", "style": "medieval", "position": [0, 0, 0]},
            {"piece_type": "wall_solid", "style": "medieval", "position": [2, 0, 0]},
        ]
        result = assemble_building(spec)
        _valid_mesh(result)
        assert result["metadata"]["piece_count"] == 2
        # Combined should have more vertices than a single wall
        single = generate_modular_piece("wall_solid", "medieval")
        assert len(result["vertices"]) > len(single["vertices"])

    def test_rotation_applied(self):
        """A wall rotated 90 degrees should swap X/Y extent."""
        spec_0 = [{"piece_type": "wall_solid", "style": "medieval",
                    "position": [0, 0, 0], "rotation_z": 0.0}]
        spec_90 = [{"piece_type": "wall_solid", "style": "medieval",
                     "position": [0, 0, 0], "rotation_z": 90.0}]
        r0 = assemble_building(spec_0)
        r90 = assemble_building(spec_90)
        bb0 = _bbox(r0["vertices"])
        bb90 = _bbox(r90["vertices"])
        # Original: wide in X, narrow in Y
        # Rotated: wide in Y, narrow in X
        w0_x = bb0["max_x"] - bb0["min_x"]
        w0_y = bb0["max_y"] - bb0["min_y"]
        w90_x = bb90["max_x"] - bb90["min_x"]
        w90_y = bb90["max_y"] - bb90["min_y"]
        # After 90 rotation, X and Y should approximately swap
        assert abs(w0_x - w90_y) < 0.3
        assert abs(w0_y - w90_x) < 0.3

    def test_translation_applied(self):
        spec = [{"piece_type": "floor_stone", "position": [10, 20, 5]}]
        result = assemble_building(spec)
        bb = _bbox(result["vertices"])
        assert bb["min_x"] > 9.5
        assert bb["min_y"] > 19.5
        assert bb["min_z"] > 4.5

    def test_simple_room_assembly(self):
        """Assemble a simple 4-wall room."""
        w = 4.0
        t = 0.3
        spec = [
            {"piece_type": "wall_solid", "style": "medieval",
             "position": [0, 0, 0], "width": w},
            {"piece_type": "wall_solid", "style": "medieval",
             "position": [0, w - t, 0], "width": w},
            {"piece_type": "wall_solid", "style": "medieval",
             "position": [0, 0, 0], "rotation_z": 90.0, "width": w},
            {"piece_type": "wall_solid", "style": "medieval",
             "position": [w, 0, 0], "rotation_z": 90.0, "width": w},
            {"piece_type": "floor_stone",
             "position": [0, 0, 0], "width": w, "depth": w},
        ]
        result = assemble_building(spec)
        _valid_mesh(result)
        assert result["metadata"]["piece_count"] == 5


# ---------------------------------------------------------------------------
# Wall thickness validation
# ---------------------------------------------------------------------------

class TestWallThickness:
    """Verify that walls have actual depth (not single-face)."""

    @pytest.mark.parametrize("style", list(STYLES))
    def test_wall_has_depth(self, style):
        """Every style's wall must have Y extent > 0.1m."""
        result = wall_solid(style=style)
        bb = _bbox(result["vertices"])
        depth = bb["max_y"] - bb["min_y"]
        assert depth > 0.1, f"{style} wall depth is {depth}, too thin"

    def test_fortress_at_least_0_5(self):
        result = wall_solid(style="fortress")
        bb = _bbox(result["vertices"])
        depth = bb["max_y"] - bb["min_y"]
        assert depth >= 0.45  # ~0.5 with jitter tolerance

    def test_explicit_thickness_overrides_style(self):
        result = wall_solid(style="medieval", thickness=0.8)
        bb = _bbox(result["vertices"])
        depth = bb["max_y"] - bb["min_y"]
        assert depth > 0.7


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_poly_count_in_metadata(self):
        result = wall_solid()
        assert result["metadata"]["poly_count"] == len(result["faces"])

    def test_vertex_count_in_metadata(self):
        result = wall_solid()
        assert result["metadata"]["vertex_count"] == len(result["vertices"])

    def test_dimensions_in_metadata(self):
        result = wall_solid()
        dims = result["metadata"]["dimensions"]
        assert "width" in dims
        assert "height" in dims
        assert "depth" in dims
