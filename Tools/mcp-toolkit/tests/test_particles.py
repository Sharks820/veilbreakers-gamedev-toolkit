"""Unit tests for particle system validation logic.

Tests the validate_* pure-logic validators from handlers/particles.py
-- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# validate_particle_system_params tests
# ---------------------------------------------------------------------------


class TestValidateParticleSystemParams:
    """Test particle system parameter validation."""

    def _valid_params(self, **overrides):
        base = {
            "name": "Cube",
            "particle_type": "EMITTER",
            "count": 1000,
            "lifetime": 50.0,
            "start_frame": 1,
            "end_frame": 200,
            "velocity": 1.0,
            "gravity": 1.0,
            "size": 0.05,
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        assert validate_particle_system_params(self._valid_params()) == []

    def test_valid_hair_type(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        assert validate_particle_system_params(
            self._valid_params(particle_type="HAIR")
        ) == []

    def test_missing_name(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(name=None))
        assert any("name" in e for e in errors)

    def test_empty_name(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(name=""))
        assert any("name" in e for e in errors)

    def test_invalid_particle_type(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(
            self._valid_params(particle_type="FLUID")
        )
        assert any("particle_type" in e for e in errors)

    def test_count_zero(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(count=0))
        assert any("count" in e for e in errors)

    def test_count_negative(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(count=-5))
        assert any("count" in e for e in errors)

    def test_count_float(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(count=1.5))
        assert any("count" in e for e in errors)

    def test_lifetime_zero(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(lifetime=0))
        assert any("lifetime" in e for e in errors)

    def test_lifetime_negative(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(lifetime=-10))
        assert any("lifetime" in e for e in errors)

    def test_end_frame_before_start(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(
            self._valid_params(start_frame=100, end_frame=50)
        )
        assert any("end_frame" in e for e in errors)

    def test_end_frame_equal_start(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(
            self._valid_params(start_frame=100, end_frame=100)
        )
        assert any("end_frame" in e for e in errors)

    def test_size_zero(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(size=0))
        assert any("size" in e for e in errors)

    def test_size_negative(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(self._valid_params(size=-0.1))
        assert any("size" in e for e in errors)

    def test_velocity_non_numeric(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(
            self._valid_params(velocity="fast")
        )
        assert any("velocity" in e for e in errors)

    def test_gravity_non_numeric(self):
        from blender_addon.handlers.particles import validate_particle_system_params

        errors = validate_particle_system_params(
            self._valid_params(gravity="strong")
        )
        assert any("gravity" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_particle_physics_params tests
# ---------------------------------------------------------------------------


class TestValidateParticlePhysicsParams:
    """Test particle physics configuration validation."""

    def _valid_params(self, **overrides):
        base = {
            "name": "Cube",
            "system_name": "ParticleSystem",
            "settings": {"mass": 1.0, "drag": 0.1},
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        assert validate_particle_physics_params(self._valid_params()) == []

    def test_missing_name(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        errors = validate_particle_physics_params(self._valid_params(name=None))
        assert any("name" in e for e in errors)

    def test_missing_system_name(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        errors = validate_particle_physics_params(
            self._valid_params(system_name=None)
        )
        assert any("system_name" in e for e in errors)

    def test_empty_system_name(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        errors = validate_particle_physics_params(
            self._valid_params(system_name="")
        )
        assert any("system_name" in e for e in errors)

    def test_settings_not_dict(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        errors = validate_particle_physics_params(
            self._valid_params(settings="bad")
        )
        assert any("settings" in e for e in errors)

    def test_settings_invalid_key(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        errors = validate_particle_physics_params(
            self._valid_params(settings={"nonexistent_key": 1.0})
        )
        assert any("Invalid settings keys" in e for e in errors)

    def test_settings_non_numeric_value(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        errors = validate_particle_physics_params(
            self._valid_params(settings={"mass": "heavy"})
        )
        assert any("numeric" in e for e in errors)

    def test_all_valid_settings_keys(self):
        from blender_addon.handlers.particles import (
            validate_particle_physics_params,
            _PHYSICS_SETTINGS_KEYS,
        )

        settings = {k: 1.0 for k in _PHYSICS_SETTINGS_KEYS}
        errors = validate_particle_physics_params(
            self._valid_params(settings=settings)
        )
        assert errors == []

    def test_no_settings_is_valid(self):
        from blender_addon.handlers.particles import validate_particle_physics_params

        params = self._valid_params()
        del params["settings"]
        assert validate_particle_physics_params(params) == []


# ---------------------------------------------------------------------------
# validate_hair_grooming_params tests
# ---------------------------------------------------------------------------


class TestValidateHairGroomingParams:
    """Test hair grooming parameter validation."""

    def _valid_params(self, **overrides):
        base = {
            "name": "Cube",
            "operation": "COMB",
            "strength": 0.5,
            "radius": 50.0,
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        assert validate_hair_grooming_params(self._valid_params()) == []

    def test_all_operations_valid(self):
        from blender_addon.handlers.particles import (
            validate_hair_grooming_params,
            _HAIR_OPERATIONS,
        )

        for op in _HAIR_OPERATIONS:
            errors = validate_hair_grooming_params(
                self._valid_params(operation=op)
            )
            assert errors == [], f"operation={op} should be valid"

    def test_missing_name(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        errors = validate_hair_grooming_params(self._valid_params(name=None))
        assert any("name" in e for e in errors)

    def test_missing_operation(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        params = self._valid_params()
        del params["operation"]
        errors = validate_hair_grooming_params(params)
        assert any("operation" in e for e in errors)

    def test_invalid_operation(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        errors = validate_hair_grooming_params(
            self._valid_params(operation="TWIST")
        )
        assert any("operation" in e.lower() or "Invalid" in e for e in errors)

    def test_strength_out_of_range(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        errors = validate_hair_grooming_params(
            self._valid_params(strength=1.5)
        )
        assert any("strength" in e for e in errors)

    def test_strength_negative(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        errors = validate_hair_grooming_params(
            self._valid_params(strength=-0.1)
        )
        assert any("strength" in e for e in errors)

    def test_radius_zero(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        errors = validate_hair_grooming_params(self._valid_params(radius=0))
        assert any("radius" in e for e in errors)

    def test_radius_negative(self):
        from blender_addon.handlers.particles import validate_hair_grooming_params

        errors = validate_hair_grooming_params(self._valid_params(radius=-10))
        assert any("radius" in e for e in errors)
