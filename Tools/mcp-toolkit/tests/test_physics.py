"""Unit tests for physics simulation validation logic.

Tests the validate_* pure-logic validators from handlers/physics.py
-- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# validate_rigid_body_params tests
# ---------------------------------------------------------------------------


class TestValidateRigidBodyParams:
    """Test rigid body parameter validation."""

    def _valid_params(self, **overrides):
        base = {
            "name": "Cube",
            "body_type": "ACTIVE",
            "mass": 1.0,
            "friction": 0.5,
            "restitution": 0.0,
            "collision_shape": "CONVEX_HULL",
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        assert validate_rigid_body_params(self._valid_params()) == []

    def test_passive_body_type(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        assert validate_rigid_body_params(
            self._valid_params(body_type="PASSIVE")
        ) == []

    def test_missing_name(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(self._valid_params(name=None))
        assert any("name" in e for e in errors)

    def test_empty_name(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(self._valid_params(name=""))
        assert any("name" in e for e in errors)

    def test_invalid_body_type(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(
            self._valid_params(body_type="KINEMATIC")
        )
        assert any("body_type" in e for e in errors)

    def test_mass_zero(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(self._valid_params(mass=0))
        assert any("mass" in e for e in errors)

    def test_mass_negative(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(self._valid_params(mass=-1.0))
        assert any("mass" in e for e in errors)

    def test_friction_negative(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(self._valid_params(friction=-0.1))
        assert any("friction" in e for e in errors)

    def test_restitution_negative(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(self._valid_params(restitution=-0.1))
        assert any("restitution" in e for e in errors)

    def test_restitution_over_one(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(self._valid_params(restitution=1.5))
        assert any("restitution" in e for e in errors)

    def test_restitution_boundaries(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        assert validate_rigid_body_params(
            self._valid_params(restitution=0.0)
        ) == []
        assert validate_rigid_body_params(
            self._valid_params(restitution=1.0)
        ) == []

    def test_all_collision_shapes_valid(self):
        from blender_addon.handlers.physics import (
            validate_rigid_body_params,
            _COLLISION_SHAPES,
        )

        for shape in _COLLISION_SHAPES:
            errors = validate_rigid_body_params(
                self._valid_params(collision_shape=shape)
            )
            assert errors == [], f"collision_shape={shape} should be valid"

    def test_invalid_collision_shape(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params(
            self._valid_params(collision_shape="CYLINDER")
        )
        assert any("collision_shape" in e for e in errors)

    def test_multiple_errors(self):
        from blender_addon.handlers.physics import validate_rigid_body_params

        errors = validate_rigid_body_params({
            "name": "",
            "body_type": "BAD",
            "mass": -1,
            "friction": -1,
            "restitution": 2.0,
            "collision_shape": "BAD",
        })
        assert len(errors) >= 5


# ---------------------------------------------------------------------------
# validate_cloth_params tests
# ---------------------------------------------------------------------------


class TestValidateClothParams:
    """Test cloth simulation parameter validation."""

    def _valid_params(self, **overrides):
        base = {
            "name": "Plane",
            "quality": 5,
            "mass": 0.3,
            "air_damping": 1.0,
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.physics import validate_cloth_params

        assert validate_cloth_params(self._valid_params()) == []

    def test_missing_name(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(name=None))
        assert any("name" in e for e in errors)

    def test_quality_below_min(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(quality=0))
        assert any("quality" in e for e in errors)

    def test_quality_above_max(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(quality=11))
        assert any("quality" in e for e in errors)

    def test_quality_float(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(quality=5.5))
        assert any("quality" in e for e in errors)

    def test_quality_boundaries(self):
        from blender_addon.handlers.physics import validate_cloth_params

        assert validate_cloth_params(self._valid_params(quality=1)) == []
        assert validate_cloth_params(self._valid_params(quality=10)) == []

    def test_mass_zero(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(mass=0))
        assert any("mass" in e for e in errors)

    def test_mass_negative(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(mass=-0.5))
        assert any("mass" in e for e in errors)

    def test_air_damping_negative(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(air_damping=-1.0))
        assert any("air_damping" in e for e in errors)

    def test_pin_group_not_string(self):
        from blender_addon.handlers.physics import validate_cloth_params

        errors = validate_cloth_params(self._valid_params(pin_group=123))
        assert any("pin_group" in e for e in errors)

    def test_pin_group_string_valid(self):
        from blender_addon.handlers.physics import validate_cloth_params

        assert validate_cloth_params(
            self._valid_params(pin_group="TopVertices")
        ) == []

    def test_pin_group_none_valid(self):
        from blender_addon.handlers.physics import validate_cloth_params

        assert validate_cloth_params(
            self._valid_params(pin_group=None)
        ) == []


# ---------------------------------------------------------------------------
# validate_soft_body_params tests
# ---------------------------------------------------------------------------


class TestValidateSoftBodyParams:
    """Test soft body parameter validation."""

    def _valid_params(self, **overrides):
        base = {
            "name": "Sphere",
            "mass": 1.0,
            "friction": 0.5,
            "speed": 1.0,
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.physics import validate_soft_body_params

        assert validate_soft_body_params(self._valid_params()) == []

    def test_missing_name(self):
        from blender_addon.handlers.physics import validate_soft_body_params

        errors = validate_soft_body_params(self._valid_params(name=None))
        assert any("name" in e for e in errors)

    def test_mass_zero(self):
        from blender_addon.handlers.physics import validate_soft_body_params

        errors = validate_soft_body_params(self._valid_params(mass=0))
        assert any("mass" in e for e in errors)

    def test_friction_negative(self):
        from blender_addon.handlers.physics import validate_soft_body_params

        errors = validate_soft_body_params(self._valid_params(friction=-0.1))
        assert any("friction" in e for e in errors)

    def test_speed_zero(self):
        from blender_addon.handlers.physics import validate_soft_body_params

        errors = validate_soft_body_params(self._valid_params(speed=0))
        assert any("speed" in e for e in errors)

    def test_speed_negative(self):
        from blender_addon.handlers.physics import validate_soft_body_params

        errors = validate_soft_body_params(self._valid_params(speed=-1.0))
        assert any("speed" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_bake_physics_params tests
# ---------------------------------------------------------------------------


class TestValidateBakePhysicsParams:
    """Test physics bake parameter validation."""

    def _valid_params(self, **overrides):
        base = {
            "start_frame": 1,
            "end_frame": 250,
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        assert validate_bake_physics_params(self._valid_params()) == []

    def test_start_frame_negative(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        errors = validate_bake_physics_params(self._valid_params(start_frame=-1))
        assert any("start_frame" in e for e in errors)

    def test_start_frame_float(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        errors = validate_bake_physics_params(self._valid_params(start_frame=1.5))
        assert any("start_frame" in e for e in errors)

    def test_end_frame_zero(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        errors = validate_bake_physics_params(self._valid_params(end_frame=0))
        assert any("end_frame" in e for e in errors)

    def test_end_frame_before_start(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        errors = validate_bake_physics_params(
            self._valid_params(start_frame=100, end_frame=50)
        )
        assert any("end_frame" in e for e in errors)

    def test_end_frame_equal_start(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        errors = validate_bake_physics_params(
            self._valid_params(start_frame=100, end_frame=100)
        )
        assert any("end_frame" in e for e in errors)

    def test_start_frame_zero_valid(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        assert validate_bake_physics_params(
            self._valid_params(start_frame=0, end_frame=100)
        ) == []

    def test_defaults_valid(self):
        from blender_addon.handlers.physics import validate_bake_physics_params

        assert validate_bake_physics_params({}) == []
