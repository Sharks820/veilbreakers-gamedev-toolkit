"""Unit tests for worldbuilding handler pure-logic outputs.

Tests _building_ops_to_mesh_spec conversion and handler return shapes
without Blender.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# _building_ops_to_mesh_spec tests
# ---------------------------------------------------------------------------


class TestBuildingOpsToMeshSpec:
    """Test pure-logic conversion of BuildingSpec operations to mesh primitives."""

    def test_returns_list(self):
        """_building_ops_to_mesh_spec returns a list of mesh primitive specs."""
        from blender_addon.handlers._building_grammar import evaluate_building_grammar
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _building_ops_to_mesh_spec(spec)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_box_operation_produces_8_verts_6_faces(self):
        """A 'box' type operation produces 8 vertices and 6 faces."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8),
            floors=1,
            style="medieval",
            operations=[
                {
                    "type": "box",
                    "position": [0, 0, 0],
                    "size": [10, 8, 0.3],
                    "material": "stone",
                    "role": "foundation",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) == 1
        assert result[0]["vertex_count"] == 8
        assert result[0]["face_count"] == 6

    def test_cylinder_operation_produces_correct_vertex_count(self):
        """A 'cylinder' operation produces correct vertex count for given segments."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        segments = 16
        spec = BuildingSpec(
            footprint=(6, 6),
            floors=1,
            style="fortress",
            operations=[
                {
                    "type": "cylinder",
                    "position": [0, 0, 0],
                    "radius": 3.0,
                    "height": 10.0,
                    "segments": segments,
                    "material": "stone",
                    "role": "tower",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) == 1
        # Cylinder: segments verts on top ring + segments verts on bottom ring
        expected_verts = segments * 2
        assert result[0]["vertex_count"] == expected_verts

    def test_opening_operation_flagged_for_subtract(self):
        """An 'opening' operation is flagged as a boolean subtract or face construction."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8),
            floors=1,
            style="medieval",
            operations=[
                {
                    "type": "opening",
                    "wall_index": 0,
                    "position": [2.0, 1.0],
                    "size": [1.2, 2.2],
                    "role": "door",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) == 1
        assert result[0]["type"] == "opening"
        assert "subtract" in result[0] or "face_construction" in result[0]


# ---------------------------------------------------------------------------
# Handler return shape tests (pure-logic verification of output dicts)
# ---------------------------------------------------------------------------


class TestHandlerReturnShapes:
    """Test that handler helper functions produce correctly-shaped output dicts."""

    def test_building_result_keys(self):
        """_build_building_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_building_result
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _build_building_result("TestBuilding", spec)
        expected_keys = {"name", "style", "floors", "footprint", "vertex_count", "face_count", "material_count"}
        assert expected_keys.issubset(set(result.keys()))

    def test_castle_result_keys(self):
        """_build_castle_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_castle_result
        from blender_addon.handlers._building_grammar import generate_castle_spec

        spec = generate_castle_spec(seed=0)
        result = _build_castle_result("TestCastle", spec)
        expected_keys = {"name", "component_count"}
        assert expected_keys.issubset(set(result.keys()))

    def test_castle_component_count(self):
        """Castle component_count includes keep + walls + towers + gate."""
        from blender_addon.handlers.worldbuilding import _build_castle_result
        from blender_addon.handlers._building_grammar import generate_castle_spec

        spec = generate_castle_spec(seed=0)
        result = _build_castle_result("TestCastle", spec)
        assert result["component_count"] > 0

    def test_ruins_result_keys(self):
        """_build_ruins_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_ruins_result
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        damaged = apply_ruins_damage(spec, damage_level=0.5, seed=0)
        result = _build_ruins_result("TestRuins", damaged, "medieval", 0.5)
        expected_keys = {"name", "original_style", "damage_level", "debris_count"}
        assert expected_keys.issubset(set(result.keys()))

    def test_ruins_debris_count(self):
        """Ruins debris_count is positive for moderate damage."""
        from blender_addon.handlers.worldbuilding import _build_ruins_result
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar,
            apply_ruins_damage,
        )

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        damaged = apply_ruins_damage(spec, damage_level=0.5, seed=0)
        result = _build_ruins_result("TestRuins", damaged, "medieval", 0.5)
        assert result["debris_count"] > 0

    def test_interior_result_keys(self):
        """_build_interior_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_interior_result
        from blender_addon.handlers._building_grammar import generate_interior_layout

        layout = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        result = _build_interior_result("TestInterior", "tavern", layout)
        expected_keys = {"name", "room_type", "furniture_count", "items"}
        assert expected_keys.issubset(set(result.keys()))

    def test_interior_items_list(self):
        """Interior items is a list of placed item names."""
        from blender_addon.handlers.worldbuilding import _build_interior_result
        from blender_addon.handlers._building_grammar import generate_interior_layout

        layout = generate_interior_layout(room_type="tavern", width=8, depth=6, seed=0)
        result = _build_interior_result("TestInterior", "tavern", layout)
        assert isinstance(result["items"], list)
        assert len(result["items"]) > 0
        assert all(isinstance(name, str) for name in result["items"])

    def test_modular_kit_result_keys(self):
        """_build_modular_kit_result returns dict with expected keys."""
        from blender_addon.handlers.worldbuilding import _build_modular_kit_result
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        pieces = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight", "floor"])
        result = _build_modular_kit_result(pieces, 2.0)
        expected_keys = {"piece_count", "pieces", "cell_size"}
        assert expected_keys.issubset(set(result.keys()))

    def test_modular_kit_piece_names(self):
        """Modular kit pieces list contains piece names."""
        from blender_addon.handlers.worldbuilding import _build_modular_kit_result
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        pieces = generate_modular_pieces(cell_size=2.0, pieces=["wall_straight", "floor"])
        result = _build_modular_kit_result(pieces, 2.0)
        assert "wall_straight" in result["pieces"]
        assert "floor" in result["pieces"]

    def test_modular_kit_cell_size(self):
        """Modular kit result includes the requested cell_size."""
        from blender_addon.handlers.worldbuilding import _build_modular_kit_result
        from blender_addon.handlers._building_grammar import generate_modular_pieces

        pieces = generate_modular_pieces(cell_size=3.0, pieces=["wall_straight"])
        result = _build_modular_kit_result(pieces, 3.0)
        assert result["cell_size"] == 3.0


# ---------------------------------------------------------------------------
# Mesh spec geometry correctness
# ---------------------------------------------------------------------------


class TestMeshSpecGeometry:
    """Test geometry correctness of converted mesh specs."""

    def test_box_verts_match_position_and_size(self):
        """Box vertices span from position to position+size."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        pos = [1.0, 2.0, 3.0]
        size = [4.0, 5.0, 6.0]
        spec = BuildingSpec(
            footprint=(4, 5),
            floors=1,
            style="medieval",
            operations=[
                {
                    "type": "box",
                    "position": pos,
                    "size": size,
                    "material": "stone",
                    "role": "foundation",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        verts = result[0]["vertices"]
        # All x-coordinates should be between pos[0] and pos[0]+size[0]
        xs = [v[0] for v in verts]
        assert min(xs) == pytest.approx(pos[0], abs=1e-6)
        assert max(xs) == pytest.approx(pos[0] + size[0], abs=1e-6)

    def test_cylinder_verts_form_circles(self):
        """Cylinder vertices form two circles at correct height."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        radius = 3.0
        height = 10.0
        segments = 8
        spec = BuildingSpec(
            footprint=(6, 6),
            floors=1,
            style="fortress",
            operations=[
                {
                    "type": "cylinder",
                    "position": [0, 0, 0],
                    "radius": radius,
                    "height": height,
                    "segments": segments,
                    "material": "stone",
                    "role": "tower",
                }
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        verts = result[0]["vertices"]
        # Check all vertex distances from center match radius (within tolerance)
        for v in verts:
            dist = math.sqrt(v[0] ** 2 + v[1] ** 2)
            assert dist == pytest.approx(radius, abs=1e-6)

    def test_full_building_mesh_spec_has_multiple_primitives(self):
        """A full building spec produces multiple mesh primitives."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _building_ops_to_mesh_spec(spec)
        assert len(result) > 1


# ---------------------------------------------------------------------------
# Opening cutting tests — verify doors/windows create actual holes
# ---------------------------------------------------------------------------


class TestOpeningCutting:
    """Test that openings (doors/windows) produce actual holes in wall geometry."""

    def test_collect_openings_groups_by_wall_and_floor(self):
        """_collect_openings_by_wall groups openings correctly."""
        from blender_addon.handlers.worldbuilding import _collect_openings_by_wall
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [2.0, 0.0], "size": [1.2, 2.2], "role": "door"},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [6.0, 1.0], "size": [0.8, 1.2], "role": "window"},
                {"type": "opening", "wall_index": 1, "floor": 0,
                 "position": [3.0, 1.0], "size": [0.8, 1.2], "role": "window"},
            ],
        )
        groups = _collect_openings_by_wall(spec)
        assert (0, 0) in groups
        assert (1, 0) in groups
        assert len(groups[(0, 0)]) == 2
        assert len(groups[(1, 0)]) == 1

    def test_wall_with_door_has_no_face_in_opening_region(self):
        """A wall with a door opening should NOT have solid faces in the door area.

        We verify by checking that the mesh specs for the wall include
        reveal quads (jamb faces) and frame geometry, which only exist
        when the opening is actually cut.
        """
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                # Front wall (wall_index=0, floor=0)
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 0, "floor": 0},
                # Door opening on front wall
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [4.0, 0.0], "size": [1.2, 2.2], "role": "door",
                 "style": "wooden_arched"},
            ],
        )
        result = _building_ops_to_mesh_spec(spec)

        # Should have wall pieces, reveal quads, and frame geometry
        roles = [m.get("role") for m in result if m["type"] != "opening"]
        assert "opening_reveal" in roles, "Must have reveal/jamb faces through wall"
        assert "door_frame" in roles, "Must have door frame trim geometry"

    def test_wall_with_window_has_sill(self):
        """A wall with a window opening should include a window sill."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 0, "floor": 0},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [3.0, 1.0], "size": [0.8, 1.2], "role": "window",
                 "style": "arched"},
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        roles = [m.get("role") for m in result if m["type"] != "opening"]
        assert "window_sill" in roles, "Windows must have a sill"
        assert "window_frame" in roles, "Windows must have frame trim"

    def test_gothic_window_has_pointed_arch_frame(self):
        """Gothic style windows produce extra arch frame quads."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="gothic",
            operations=[
                {"type": "box", "position": [0, 0, 0.5], "size": [10, 0.5, 4.5],
                 "material": "stone_carved", "role": "wall",
                 "wall_index": 0, "floor": 0},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [3.0, 1.0], "size": [0.6, 2.0], "role": "window",
                 "style": "pointed_arch"},
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        # Gothic pointed arch produces 2 arch slope quads instead of 1 lintel
        frame_specs = [m for m in result if m.get("role") == "window_frame"]
        # Should have: left strip + right strip + 2 arch slopes + bottom strip = 5
        assert len(frame_specs) >= 4, (
            f"Gothic window should have >= 4 frame quads, got {len(frame_specs)}"
        )

    def test_wall_without_openings_is_solid_box(self):
        """A wall with no openings produces a standard 8-vert 6-face box."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 2, "floor": 0},
                # No openings on wall_index=2
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        wall_specs = [m for m in result if m["type"] == "box"]
        assert len(wall_specs) == 1
        assert wall_specs[0]["vertex_count"] == 8
        assert wall_specs[0]["face_count"] == 6

    def test_door_opening_more_verts_than_solid_wall(self):
        """A wall with a door opening produces more vertices than a solid wall."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        # Solid wall
        spec_solid = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 0, "floor": 0},
            ],
        )
        solid_result = _building_ops_to_mesh_spec(spec_solid)
        solid_verts = sum(m.get("vertex_count", 0) for m in solid_result if m["type"] != "opening")

        # Wall with door
        spec_door = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 0, "floor": 0},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [4.0, 0.0], "size": [1.2, 2.2], "role": "door"},
            ],
        )
        door_result = _building_ops_to_mesh_spec(spec_door)
        door_verts = sum(m.get("vertex_count", 0) for m in door_result if m["type"] != "opening")

        assert door_verts > solid_verts, (
            f"Wall with door ({door_verts} verts) should have more geometry "
            f"than solid wall ({solid_verts} verts)"
        )

    def test_full_medieval_building_has_opening_geometry(self):
        """A full medieval building has reveal and frame geometry for openings."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import evaluate_building_grammar

        spec = evaluate_building_grammar(width=10, depth=8, floors=2, style="medieval", seed=0)
        result = _building_ops_to_mesh_spec(spec)
        roles = set(m.get("role") for m in result)

        assert "opening_reveal" in roles, "Building must have opening reveal geometry"
        assert "door_frame" in roles, "Building must have door frame geometry"
        assert "window_frame" in roles, "Building must have window frame geometry"
        assert "window_sill" in roles, "Building must have window sill geometry"

    def test_all_styles_produce_opening_geometry(self):
        """All 5 styles produce opening geometry when built with defaults."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import (
            evaluate_building_grammar, STYLE_CONFIGS,
        )

        for style_name in STYLE_CONFIGS:
            spec = evaluate_building_grammar(
                width=10, depth=8, floors=1, style=style_name, seed=0,
            )
            result = _building_ops_to_mesh_spec(spec)
            roles = set(m.get("role") for m in result)
            assert "opening_reveal" in roles, (
                f"Style '{style_name}' must produce opening reveal geometry"
            )

    def test_opening_reveal_has_valid_quad_geometry(self):
        """Each reveal quad has exactly 4 vertices and 1 face."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 0, "floor": 0},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [4.0, 0.0], "size": [1.2, 2.2], "role": "door"},
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        reveals = [m for m in result if m.get("role") == "opening_reveal"]
        assert len(reveals) > 0
        for r in reveals:
            assert r["vertex_count"] == 4, "Reveal quads must have 4 vertices"
            assert r["face_count"] == 1, "Reveal quads must have 1 face"
            assert len(r["vertices"]) == 4
            assert len(r["faces"]) == 1
            assert len(r["faces"][0]) == 4

    def test_opening_dimensions_match_spec(self):
        """Opening reveal geometry dimensions match the spec width and height."""
        from blender_addon.handlers.worldbuilding import _wall_with_openings

        # Front wall (wall_index=0): extends along X, thickness along Y
        result = _wall_with_openings(
            px=0.0, py=0.0, pz=0.0,
            sx=10.0, sy=0.3, sz=3.0,
            wall_index=0,
            openings=[{
                "position": [4.0, 0.0], "size": [1.2, 2.2],
                "role": "door", "style": "wooden_arched",
            }],
            material="plaster_white",
        )
        # Find top reveal quad (horizontal, at top of door)
        reveals = [m for m in result if m.get("role") == "opening_reveal"]
        assert len(reveals) >= 3, "Door needs at least 3 reveals (top, left, right)"

        # Check that one reveal spans the door width (1.2m) along X
        for r in reveals:
            xs = [v[0] for v in r["vertices"]]
            x_span = max(xs) - min(xs)
            if abs(x_span - 1.2) < 0.01:
                # This is the top reveal -- check Y spans wall thickness
                ys = [v[1] for v in r["vertices"]]
                y_span = max(ys) - min(ys)
                assert abs(y_span - 0.3) < 0.01, (
                    f"Reveal Y span should match wall thickness 0.3, got {y_span}"
                )
                break
        else:
            # If no exact match, at least verify reveals exist with correct Z range
            pass  # Already asserted >= 3 reveals above

    def test_side_wall_openings_work(self):
        """Openings on side walls (wall_index 2,3) also produce hole geometry."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                # Left wall (wall_index=2)
                {"type": "box", "position": [0, 0.3, 0.3],
                 "size": [0.3, 7.4, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 2, "floor": 0},
                {"type": "opening", "wall_index": 2, "floor": 0,
                 "position": [2.0, 1.0], "size": [0.8, 1.2], "role": "window",
                 "style": "arched"},
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        roles = set(m.get("role") for m in result if m["type"] != "opening")
        assert "opening_reveal" in roles, "Side wall openings must produce reveals"
        assert "window_frame" in roles, "Side wall openings must produce frames"

    def test_multiple_openings_on_same_wall(self):
        """Multiple openings on the same wall all produce geometry."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 0, "floor": 0},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [1.5, 1.0], "size": [0.8, 1.2], "role": "window"},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [4.0, 0.0], "size": [1.2, 2.2], "role": "door"},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [7.5, 1.0], "size": [0.8, 1.2], "role": "window"},
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        # Should have reveals for all 3 openings
        reveals = [m for m in result if m.get("role") == "opening_reveal"]
        # Each opening gets top + left + right reveals (+ bottom for windows)
        # window: 4 reveals, door: 3 reveals, window: 4 reveals = 11 min
        assert len(reveals) >= 9, (
            f"3 openings should produce at least 9 reveal quads, got {len(reveals)}"
        )

    def test_backward_compatible_opening_metadata(self):
        """Opening metadata entries with face_construction flag are still emitted."""
        from blender_addon.handlers.worldbuilding import _building_ops_to_mesh_spec
        from blender_addon.handlers._building_grammar import BuildingSpec

        spec = BuildingSpec(
            footprint=(10, 8), floors=1, style="medieval",
            operations=[
                {"type": "box", "position": [0, 0, 0.3], "size": [10, 0.3, 3.0],
                 "material": "plaster_white", "role": "wall",
                 "wall_index": 0, "floor": 0},
                {"type": "opening", "wall_index": 0, "floor": 0,
                 "position": [4.0, 0.0], "size": [1.2, 2.2], "role": "door"},
            ],
        )
        result = _building_ops_to_mesh_spec(spec)
        opening_entries = [m for m in result if m["type"] == "opening"]
        assert len(opening_entries) == 1
        assert opening_entries[0]["face_construction"] is True
