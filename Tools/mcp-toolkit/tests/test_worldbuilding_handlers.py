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
