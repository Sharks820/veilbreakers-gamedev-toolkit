"""Unit tests for advanced sculpt system (MESH-04b..f).

Tests the pure-logic validation helpers from handlers/mesh.py that do NOT
require bpy/Blender. Covers:
- Mesh filter operation validation (expanded from 4 to 11)
- Sculpt brush type validation (32 brush types)
- Dynamic topology action/mode validation
- Voxel remesh parameter validation
- Face set action validation
- Multires action/subdivision validation
- Brush strength/radius/direction validation

All tests are deterministic and run without Blender.
"""

import pytest


# ---------------------------------------------------------------------------
# Mesh filter operation tests (expanded _SCULPT_OPERATIONS)
# ---------------------------------------------------------------------------


class TestSculptOperations:
    """Test the expanded _SCULPT_OPERATIONS dict and filter type mapping."""

    def test_all_operations_are_strings_or_none(self):
        """Every value in _SCULPT_OPERATIONS must be a string or None."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        for key, value in _SCULPT_OPERATIONS.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert value is None or isinstance(value, str), (
                f"Value for {key!r} must be str or None, got {type(value)}"
            )

    def test_operation_count_at_least_11(self):
        """Must have at least 11 sculpt operations (expanded from 4)."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        assert len(_SCULPT_OPERATIONS) >= 11

    def test_original_operations_preserved(self):
        """Original 4 operations must still be present."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        assert "smooth" in _SCULPT_OPERATIONS
        assert "inflate" in _SCULPT_OPERATIONS
        assert "flatten" in _SCULPT_OPERATIONS
        assert "crease" in _SCULPT_OPERATIONS

    def test_smooth_maps_to_none(self):
        """Smooth operation maps to None (bmesh path)."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        assert _SCULPT_OPERATIONS["smooth"] is None

    def test_new_operations_present(self):
        """All new mesh filter operations must be present."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        new_ops = [
            "relax", "enhance_details", "random", "scale", "sphere",
            "surface_smooth", "sharpen",
        ]
        for op in new_ops:
            assert op in _SCULPT_OPERATIONS, f"Missing operation: {op!r}"

    def test_relax_maps_to_RELAX(self):
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS
        assert _SCULPT_OPERATIONS["relax"] == "RELAX"

    def test_enhance_details_maps_to_ENHANCE_DETAILS(self):
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS
        assert _SCULPT_OPERATIONS["enhance_details"] == "ENHANCE_DETAILS"

    def test_random_maps_to_RANDOM(self):
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS
        assert _SCULPT_OPERATIONS["random"] == "RANDOM"

    def test_scale_maps_to_SCALE(self):
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS
        assert _SCULPT_OPERATIONS["scale"] == "SCALE"

    def test_sphere_maps_to_SPHERE(self):
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS
        assert _SCULPT_OPERATIONS["sphere"] == "SPHERE"

    def test_surface_smooth_alias(self):
        """surface_smooth is an explicit alias for SURFACE_SMOOTH."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS
        assert _SCULPT_OPERATIONS["surface_smooth"] == "SURFACE_SMOOTH"

    def test_sharpen_alias(self):
        """sharpen is an explicit alias for SHARPEN."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS
        assert _SCULPT_OPERATIONS["sharpen"] == "SHARPEN"

    def test_filter_type_mapping_valid_op(self):
        """_sculpt_operation_to_filter_type returns correct type for valid op."""
        from blender_addon.handlers.mesh import _sculpt_operation_to_filter_type

        assert _sculpt_operation_to_filter_type("inflate") == "INFLATE"
        assert _sculpt_operation_to_filter_type("relax") == "RELAX"
        assert _sculpt_operation_to_filter_type("smooth") is None

    def test_filter_type_mapping_invalid_op(self):
        """_sculpt_operation_to_filter_type raises ValueError for invalid op."""
        from blender_addon.handlers.mesh import _sculpt_operation_to_filter_type

        with pytest.raises(ValueError, match="Unknown sculpt operation"):
            _sculpt_operation_to_filter_type("nonexistent_op")

    def test_all_filter_types_are_uppercase(self):
        """All non-None filter types must be uppercase (Blender enum convention)."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        for key, value in _SCULPT_OPERATIONS.items():
            if value is not None:
                assert value == value.upper(), (
                    f"Filter type for {key!r} must be uppercase: {value!r}"
                )


# ---------------------------------------------------------------------------
# Sculpt brush type validation tests
# ---------------------------------------------------------------------------


class TestBrushTypeValidation:
    """Test _validate_brush_type and _SCULPT_BRUSH_TYPES."""

    def test_brush_types_count_at_least_30(self):
        """Must have at least 30 valid brush types."""
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES

        assert len(_SCULPT_BRUSH_TYPES) >= 30

    def test_core_brush_types_present(self):
        """Core sculpt brushes must be present."""
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES

        core = [
            "DRAW", "DRAW_SHARP", "CLAY", "CLAY_STRIPS", "SMOOTH",
            "FLATTEN", "INFLATE", "GRAB", "PINCH", "CREASE", "BLOB",
            "MASK", "CLOTH", "SNAKE_HOOK", "POSE",
        ]
        for brush in core:
            assert brush in _SCULPT_BRUSH_TYPES, f"Missing brush: {brush!r}"

    def test_all_brush_types_are_uppercase(self):
        """All brush type strings must be uppercase."""
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES

        for brush in _SCULPT_BRUSH_TYPES:
            assert brush == brush.upper(), f"Brush type must be uppercase: {brush!r}"

    def test_validate_brush_type_valid(self):
        """Valid brush type passes validation."""
        from blender_addon.handlers.mesh import _validate_brush_type

        assert _validate_brush_type("DRAW") == "DRAW"
        assert _validate_brush_type("CLAY_STRIPS") == "CLAY_STRIPS"

    def test_validate_brush_type_case_insensitive(self):
        """Brush type validation is case-insensitive."""
        from blender_addon.handlers.mesh import _validate_brush_type

        assert _validate_brush_type("draw") == "DRAW"
        assert _validate_brush_type("Clay_Strips") == "CLAY_STRIPS"
        assert _validate_brush_type("smooth") == "SMOOTH"

    def test_validate_brush_type_invalid(self):
        """Invalid brush type raises ValueError."""
        from blender_addon.handlers.mesh import _validate_brush_type

        with pytest.raises(ValueError, match="Unknown sculpt brush type"):
            _validate_brush_type("INVALID_BRUSH")

    def test_validate_brush_type_empty(self):
        """Empty string raises ValueError."""
        from blender_addon.handlers.mesh import _validate_brush_type

        with pytest.raises(ValueError, match="Unknown sculpt brush type"):
            _validate_brush_type("")

    def test_all_32_brush_types(self):
        """All 32 documented brush types must be present."""
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES

        expected = {
            "DRAW", "DRAW_SHARP", "CLAY", "CLAY_STRIPS", "CLAY_THUMB",
            "LAYER", "INFLATE", "BLOB", "CREASE", "SMOOTH", "FLATTEN",
            "FILL", "SCRAPE", "MULTIPLANE_SCRAPE", "PINCH", "GRAB",
            "ELASTIC_DEFORM", "SNAKE_HOOK", "THUMB", "POSE", "NUDGE",
            "ROTATE", "TOPOLOGY", "BOUNDARY", "CLOTH", "SIMPLIFY",
            "MASK", "DRAW_FACE_SETS", "DISPLACEMENT_ERASER",
            "DISPLACEMENT_SMEAR", "PAINT", "SMEAR",
        }
        assert _SCULPT_BRUSH_TYPES == expected


# ---------------------------------------------------------------------------
# Brush direction validation tests
# ---------------------------------------------------------------------------


class TestBrushDirectionValidation:
    """Test _validate_brush_direction."""

    def test_add_direction(self):
        from blender_addon.handlers.mesh import _validate_brush_direction
        assert _validate_brush_direction("ADD") == "ADD"

    def test_subtract_direction(self):
        from blender_addon.handlers.mesh import _validate_brush_direction
        assert _validate_brush_direction("SUBTRACT") == "SUBTRACT"

    def test_case_insensitive(self):
        from blender_addon.handlers.mesh import _validate_brush_direction
        assert _validate_brush_direction("add") == "ADD"
        assert _validate_brush_direction("subtract") == "SUBTRACT"

    def test_invalid_direction(self):
        from blender_addon.handlers.mesh import _validate_brush_direction
        with pytest.raises(ValueError, match="Invalid brush direction"):
            _validate_brush_direction("INWARD")


# ---------------------------------------------------------------------------
# Brush strength/radius validation tests
# ---------------------------------------------------------------------------


class TestBrushStrengthRadius:
    """Test _validate_brush_strength and _validate_brush_radius."""

    def test_strength_normal(self):
        from blender_addon.handlers.mesh import _validate_brush_strength
        assert _validate_brush_strength(0.5) == 0.5

    def test_strength_clamped_high(self):
        from blender_addon.handlers.mesh import _validate_brush_strength
        assert _validate_brush_strength(1.5) == 1.0

    def test_strength_clamped_low(self):
        from blender_addon.handlers.mesh import _validate_brush_strength
        assert _validate_brush_strength(-0.5) == 0.0

    def test_strength_zero(self):
        from blender_addon.handlers.mesh import _validate_brush_strength
        assert _validate_brush_strength(0.0) == 0.0

    def test_strength_one(self):
        from blender_addon.handlers.mesh import _validate_brush_strength
        assert _validate_brush_strength(1.0) == 1.0

    def test_radius_positive(self):
        from blender_addon.handlers.mesh import _validate_brush_radius
        assert _validate_brush_radius(50) == 50.0

    def test_radius_zero_raises(self):
        from blender_addon.handlers.mesh import _validate_brush_radius
        with pytest.raises(ValueError, match="Brush radius must be > 0"):
            _validate_brush_radius(0)

    def test_radius_negative_raises(self):
        from blender_addon.handlers.mesh import _validate_brush_radius
        with pytest.raises(ValueError, match="Brush radius must be > 0"):
            _validate_brush_radius(-10)

    def test_radius_float_conversion(self):
        from blender_addon.handlers.mesh import _validate_brush_radius
        assert isinstance(_validate_brush_radius(50), float)


# ---------------------------------------------------------------------------
# Dynamic topology validation tests
# ---------------------------------------------------------------------------


class TestDyntopoValidation:
    """Test _validate_dyntopo_action and _validate_dyntopo_detail_mode."""

    def test_valid_actions(self):
        from blender_addon.handlers.mesh import _validate_dyntopo_action

        assert _validate_dyntopo_action("enable") == "enable"
        assert _validate_dyntopo_action("disable") == "disable"
        assert _validate_dyntopo_action("status") == "status"

    def test_invalid_action(self):
        from blender_addon.handlers.mesh import _validate_dyntopo_action

        with pytest.raises(ValueError, match="Unknown dyntopo action"):
            _validate_dyntopo_action("toggle")

    def test_action_count(self):
        from blender_addon.handlers.mesh import _DYNTOPO_ACTIONS
        assert len(_DYNTOPO_ACTIONS) == 3

    def test_valid_detail_modes(self):
        from blender_addon.handlers.mesh import _validate_dyntopo_detail_mode

        modes = [
            "RELATIVE_DETAIL", "CONSTANT_DETAIL",
            "BRUSH_DETAIL", "MANUAL_DETAIL",
        ]
        for mode in modes:
            assert _validate_dyntopo_detail_mode(mode) == mode

    def test_invalid_detail_mode(self):
        from blender_addon.handlers.mesh import _validate_dyntopo_detail_mode

        with pytest.raises(ValueError, match="Unknown dyntopo detail mode"):
            _validate_dyntopo_detail_mode("AUTO_DETAIL")

    def test_detail_mode_count(self):
        from blender_addon.handlers.mesh import _DYNTOPO_DETAIL_MODES
        assert len(_DYNTOPO_DETAIL_MODES) == 4

    def test_detail_modes_are_uppercase(self):
        from blender_addon.handlers.mesh import _DYNTOPO_DETAIL_MODES
        for mode in _DYNTOPO_DETAIL_MODES:
            assert mode == mode.upper()


# ---------------------------------------------------------------------------
# Voxel remesh parameter validation tests
# ---------------------------------------------------------------------------


class TestVoxelRemeshValidation:
    """Test _validate_voxel_remesh_params."""

    def test_valid_params(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        # Should not raise
        _validate_voxel_remesh_params(0.05, 0.0)
        _validate_voxel_remesh_params(0.01, 0.5)
        _validate_voxel_remesh_params(1.0, 1.0)

    def test_voxel_size_zero_raises(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        with pytest.raises(ValueError, match="voxel_size must be > 0"):
            _validate_voxel_remesh_params(0.0, 0.0)

    def test_voxel_size_negative_raises(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        with pytest.raises(ValueError, match="voxel_size must be > 0"):
            _validate_voxel_remesh_params(-0.1, 0.0)

    def test_adaptivity_too_high_raises(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        with pytest.raises(ValueError, match="adaptivity must be in"):
            _validate_voxel_remesh_params(0.05, 1.5)

    def test_adaptivity_negative_raises(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        with pytest.raises(ValueError, match="adaptivity must be in"):
            _validate_voxel_remesh_params(0.05, -0.1)

    def test_adaptivity_boundary_values(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        # Boundary values should pass
        _validate_voxel_remesh_params(0.001, 0.0)
        _validate_voxel_remesh_params(0.001, 1.0)

    def test_very_small_voxel_size(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        # Tiny but valid
        _validate_voxel_remesh_params(0.0001, 0.0)

    def test_large_voxel_size(self):
        from blender_addon.handlers.mesh import _validate_voxel_remesh_params

        # Large but valid
        _validate_voxel_remesh_params(100.0, 0.0)


# ---------------------------------------------------------------------------
# Face set action validation tests
# ---------------------------------------------------------------------------


class TestFaceSetValidation:
    """Test _validate_face_set_action and _FACE_SET_ACTIONS."""

    def test_all_valid_actions(self):
        from blender_addon.handlers.mesh import _validate_face_set_action

        actions = [
            "create_from_visible", "create_from_loose_parts",
            "create_from_materials", "create_from_normals",
            "randomize", "init",
        ]
        for action in actions:
            assert _validate_face_set_action(action) == action

    def test_invalid_action(self):
        from blender_addon.handlers.mesh import _validate_face_set_action

        with pytest.raises(ValueError, match="Unknown face set action"):
            _validate_face_set_action("delete")

    def test_action_count(self):
        from blender_addon.handlers.mesh import _FACE_SET_ACTIONS
        assert len(_FACE_SET_ACTIONS) == 6

    def test_empty_string_raises(self):
        from blender_addon.handlers.mesh import _validate_face_set_action

        with pytest.raises(ValueError, match="Unknown face set action"):
            _validate_face_set_action("")


# ---------------------------------------------------------------------------
# Multires validation tests
# ---------------------------------------------------------------------------


class TestMultiresValidation:
    """Test _validate_multires_action and _validate_multires_subdivisions."""

    def test_all_valid_actions(self):
        from blender_addon.handlers.mesh import _validate_multires_action

        actions = [
            "add", "subdivide", "reshape", "delete_higher",
            "delete_lower", "apply_base",
        ]
        for action in actions:
            assert _validate_multires_action(action) == action

    def test_invalid_action(self):
        from blender_addon.handlers.mesh import _validate_multires_action

        with pytest.raises(ValueError, match="Unknown multires action"):
            _validate_multires_action("smooth")

    def test_action_count(self):
        from blender_addon.handlers.mesh import _MULTIRES_ACTIONS
        assert len(_MULTIRES_ACTIONS) == 6

    def test_valid_subdivisions(self):
        from blender_addon.handlers.mesh import _validate_multires_subdivisions

        # Should not raise
        for n in range(1, 11):
            _validate_multires_subdivisions(n)

    def test_subdivisions_zero_raises(self):
        from blender_addon.handlers.mesh import _validate_multires_subdivisions

        with pytest.raises(ValueError, match="subdivisions must be >= 1"):
            _validate_multires_subdivisions(0)

    def test_subdivisions_negative_raises(self):
        from blender_addon.handlers.mesh import _validate_multires_subdivisions

        with pytest.raises(ValueError, match="subdivisions must be >= 1"):
            _validate_multires_subdivisions(-1)

    def test_subdivisions_too_high_raises(self):
        from blender_addon.handlers.mesh import _validate_multires_subdivisions

        with pytest.raises(ValueError, match="subdivisions must be <= 10"):
            _validate_multires_subdivisions(11)

    def test_subdivisions_way_too_high_raises(self):
        from blender_addon.handlers.mesh import _validate_multires_subdivisions

        with pytest.raises(ValueError, match="subdivisions must be <= 10"):
            _validate_multires_subdivisions(100)


# ---------------------------------------------------------------------------
# Constants cross-validation
# ---------------------------------------------------------------------------


class TestConstantsCrossValidation:
    """Verify that all constant sets are internally consistent."""

    def test_sculpt_operations_keys_are_lowercase(self):
        """All sculpt operation keys must be lowercase."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        for key in _SCULPT_OPERATIONS:
            assert key == key.lower(), f"Key must be lowercase: {key!r}"

    def test_no_duplicate_filter_types(self):
        """No two operations should accidentally share a filter type
        (except intentional aliases like flatten/surface_smooth, crease/sharpen)."""
        from blender_addon.handlers.mesh import _SCULPT_OPERATIONS

        # Build reverse map: filter_type -> list of operation names
        reverse: dict = {}
        for key, value in _SCULPT_OPERATIONS.items():
            if value is not None:
                reverse.setdefault(value, []).append(key)

        # Check that aliases are intentional (known pairs)
        known_aliases = {
            "SURFACE_SMOOTH": {"flatten", "surface_smooth"},
            "SHARPEN": {"crease", "sharpen"},
        }
        for filter_type, ops in reverse.items():
            if len(ops) > 1:
                expected = known_aliases.get(filter_type)
                assert expected is not None, (
                    f"Unexpected duplicate filter type {filter_type!r}: {ops}"
                )
                assert set(ops) == expected, (
                    f"Unexpected aliases for {filter_type!r}: {ops} != {expected}"
                )

    def test_brush_types_are_frozen(self):
        """_SCULPT_BRUSH_TYPES must be a frozenset (immutable)."""
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES
        assert isinstance(_SCULPT_BRUSH_TYPES, frozenset)

    def test_dyntopo_actions_are_frozen(self):
        """_DYNTOPO_ACTIONS must be a frozenset."""
        from blender_addon.handlers.mesh import _DYNTOPO_ACTIONS
        assert isinstance(_DYNTOPO_ACTIONS, frozenset)

    def test_face_set_actions_are_frozen(self):
        """_FACE_SET_ACTIONS must be a frozenset."""
        from blender_addon.handlers.mesh import _FACE_SET_ACTIONS
        assert isinstance(_FACE_SET_ACTIONS, frozenset)

    def test_multires_actions_are_frozen(self):
        """_MULTIRES_ACTIONS must be a frozenset."""
        from blender_addon.handlers.mesh import _MULTIRES_ACTIONS
        assert isinstance(_MULTIRES_ACTIONS, frozenset)

    def test_detail_modes_are_frozen(self):
        """_DYNTOPO_DETAIL_MODES must be a frozenset."""
        from blender_addon.handlers.mesh import _DYNTOPO_DETAIL_MODES
        assert isinstance(_DYNTOPO_DETAIL_MODES, frozenset)


# ---------------------------------------------------------------------------
# Handler registration tests
# ---------------------------------------------------------------------------


class TestHandlerRegistration:
    """Verify that all new handlers are registered in COMMAND_HANDLERS."""

    def test_mesh_sculpt_brush_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "mesh_sculpt_brush" in COMMAND_HANDLERS

    def test_mesh_dyntopo_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "mesh_dyntopo" in COMMAND_HANDLERS

    def test_mesh_voxel_remesh_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "mesh_voxel_remesh" in COMMAND_HANDLERS

    def test_mesh_face_sets_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "mesh_face_sets" in COMMAND_HANDLERS

    def test_mesh_multires_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "mesh_multires" in COMMAND_HANDLERS

    def test_original_mesh_sculpt_still_registered(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "mesh_sculpt" in COMMAND_HANDLERS

    def test_handler_functions_are_callable(self):
        from blender_addon.handlers import COMMAND_HANDLERS

        new_keys = [
            "mesh_sculpt_brush", "mesh_dyntopo", "mesh_voxel_remesh",
            "mesh_face_sets", "mesh_multires",
        ]
        for key in new_keys:
            assert callable(COMMAND_HANDLERS[key]), (
                f"Handler for {key!r} must be callable"
            )


# ---------------------------------------------------------------------------
# Handler function importability tests
# ---------------------------------------------------------------------------


class TestHandlerImports:
    """Verify that all new handler functions are importable."""

    def test_import_handle_sculpt_brush(self):
        from blender_addon.handlers.mesh import handle_sculpt_brush
        assert callable(handle_sculpt_brush)

    def test_import_handle_dyntopo(self):
        from blender_addon.handlers.mesh import handle_dyntopo
        assert callable(handle_dyntopo)

    def test_import_handle_voxel_remesh(self):
        from blender_addon.handlers.mesh import handle_voxel_remesh
        assert callable(handle_voxel_remesh)

    def test_import_handle_face_sets(self):
        from blender_addon.handlers.mesh import handle_face_sets
        assert callable(handle_face_sets)

    def test_import_handle_multires(self):
        from blender_addon.handlers.mesh import handle_multires
        assert callable(handle_multires)

    def test_import_all_validators(self):
        """All validation functions must be importable."""
        from blender_addon.handlers.mesh import (
            _validate_brush_type,
            _validate_brush_direction,
            _validate_brush_strength,
            _validate_brush_radius,
            _validate_dyntopo_action,
            _validate_dyntopo_detail_mode,
            _validate_voxel_remesh_params,
            _validate_face_set_action,
            _validate_multires_action,
            _validate_multires_subdivisions,
        )
        # All must be callable
        for fn in [
            _validate_brush_type,
            _validate_brush_direction,
            _validate_brush_strength,
            _validate_brush_radius,
            _validate_dyntopo_action,
            _validate_dyntopo_detail_mode,
            _validate_voxel_remesh_params,
            _validate_face_set_action,
            _validate_multires_action,
            _validate_multires_subdivisions,
        ]:
            assert callable(fn)
