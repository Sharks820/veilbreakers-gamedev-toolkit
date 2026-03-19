"""Tests for animation handler parameter validation and pure-logic helpers.

Tests cover:
- Walk handler param validation (gait types, speed, frame_count)
- Fly handler param validation (frequency, amplitude, glide_ratio)
- Idle handler param validation (breathing_intensity, frame_count)
- Attack handler param validation (8 attack types, intensity bounds)
- Reaction handler param validation (reaction types, hit directions)
- Custom handler param validation (empty description, non-string)
- Constant sets (VALID_GAITS, VALID_ATTACK_TYPES, etc.)

All pure-logic -- no Blender required.
"""

import pytest

from blender_addon.handlers.animation import (
    VALID_ATTACK_TYPES,
    VALID_GAITS,
    VALID_HIT_DIRECTIONS,
    VALID_REACTION_TYPES,
    VALID_SPEEDS,
    _validate_attack_params,
    _validate_custom_params,
    _validate_fly_params,
    _validate_idle_params,
    _validate_reaction_params,
    _validate_walk_params,
)


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    """Test that handler constant sets match expected values."""

    def test_valid_gaits_contains_all_five(self):
        expected = {"biped", "quadruped", "hexapod", "arachnid", "serpent"}
        assert VALID_GAITS == expected

    def test_valid_speeds(self):
        assert VALID_SPEEDS == {"walk", "run"}

    def test_valid_attack_types_count(self):
        assert len(VALID_ATTACK_TYPES) == 8

    def test_valid_attack_types_has_melee_swing(self):
        assert "melee_swing" in VALID_ATTACK_TYPES

    def test_valid_attack_types_has_breath_attack(self):
        assert "breath_attack" in VALID_ATTACK_TYPES

    def test_valid_attack_types_all_present(self):
        expected = {
            "melee_swing", "thrust", "slam", "bite",
            "claw", "tail_whip", "wing_buffet", "breath_attack",
        }
        assert VALID_ATTACK_TYPES == expected

    def test_valid_reaction_types(self):
        assert VALID_REACTION_TYPES == {"death", "hit", "spawn"}

    def test_valid_hit_directions(self):
        assert VALID_HIT_DIRECTIONS == {"front", "back", "left", "right"}


# ---------------------------------------------------------------------------
# TestWalkParams
# ---------------------------------------------------------------------------


class TestWalkParams:
    """Test _validate_walk_params pure-logic validation."""

    def test_valid_defaults(self):
        result = _validate_walk_params({"object_name": "MyArmature"})
        assert result["object_name"] == "MyArmature"
        assert result["gait"] == "biped"
        assert result["speed"] == "walk"
        assert result["frame_count"] == 24

    def test_valid_all_params(self):
        result = _validate_walk_params({
            "object_name": "Creature",
            "gait": "quadruped",
            "speed": "run",
            "frame_count": 32,
        })
        assert result["gait"] == "quadruped"
        assert result["speed"] == "run"
        assert result["frame_count"] == 32

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_walk_params({})

    def test_empty_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_walk_params({"object_name": ""})

    def test_invalid_gait_raises(self):
        with pytest.raises(ValueError, match="Invalid gait"):
            _validate_walk_params({
                "object_name": "X",
                "gait": "centipede",
            })

    def test_invalid_speed_raises(self):
        with pytest.raises(ValueError, match="Invalid speed"):
            _validate_walk_params({
                "object_name": "X",
                "speed": "sprint",
            })

    def test_frame_count_too_small_raises(self):
        with pytest.raises(ValueError, match="frame_count must be >= 4"):
            _validate_walk_params({
                "object_name": "X",
                "frame_count": 2,
            })

    @pytest.mark.parametrize("gait", sorted(VALID_GAITS))
    def test_all_gaits_accepted(self, gait):
        result = _validate_walk_params({
            "object_name": "X",
            "gait": gait,
        })
        assert result["gait"] == gait

    @pytest.mark.parametrize("speed", sorted(VALID_SPEEDS))
    def test_all_speeds_accepted(self, speed):
        result = _validate_walk_params({
            "object_name": "X",
            "speed": speed,
        })
        assert result["speed"] == speed

    def test_frame_count_cast_to_int(self):
        result = _validate_walk_params({
            "object_name": "X",
            "frame_count": "16",
        })
        assert result["frame_count"] == 16
        assert isinstance(result["frame_count"], int)


# ---------------------------------------------------------------------------
# TestFlyParams
# ---------------------------------------------------------------------------


class TestFlyParams:
    """Test _validate_fly_params pure-logic validation."""

    def test_valid_defaults(self):
        result = _validate_fly_params({"object_name": "Dragon"})
        assert result["object_name"] == "Dragon"
        assert result["frequency"] == 2.0
        assert result["amplitude"] == 0.8
        assert result["glide_ratio"] == 0.3
        assert result["frame_count"] == 24

    def test_valid_all_params(self):
        result = _validate_fly_params({
            "object_name": "Bird",
            "frequency": 3.0,
            "amplitude": 1.2,
            "glide_ratio": 0.5,
            "frame_count": 32,
        })
        assert result["frequency"] == 3.0
        assert result["amplitude"] == 1.2
        assert result["glide_ratio"] == 0.5
        assert result["frame_count"] == 32

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_fly_params({})

    def test_negative_frequency_raises(self):
        with pytest.raises(ValueError, match="frequency must be > 0"):
            _validate_fly_params({
                "object_name": "X",
                "frequency": -1.0,
            })

    def test_zero_frequency_raises(self):
        with pytest.raises(ValueError, match="frequency must be > 0"):
            _validate_fly_params({
                "object_name": "X",
                "frequency": 0,
            })

    def test_negative_amplitude_raises(self):
        with pytest.raises(ValueError, match="amplitude must be > 0"):
            _validate_fly_params({
                "object_name": "X",
                "amplitude": -0.5,
            })

    def test_glide_ratio_below_zero_raises(self):
        with pytest.raises(ValueError, match="glide_ratio must be between"):
            _validate_fly_params({
                "object_name": "X",
                "glide_ratio": -0.1,
            })

    def test_glide_ratio_above_one_raises(self):
        with pytest.raises(ValueError, match="glide_ratio must be between"):
            _validate_fly_params({
                "object_name": "X",
                "glide_ratio": 1.1,
            })

    def test_glide_ratio_zero_valid(self):
        result = _validate_fly_params({
            "object_name": "X",
            "glide_ratio": 0.0,
        })
        assert result["glide_ratio"] == 0.0

    def test_glide_ratio_one_valid(self):
        result = _validate_fly_params({
            "object_name": "X",
            "glide_ratio": 1.0,
        })
        assert result["glide_ratio"] == 1.0

    def test_frame_count_too_small_raises(self):
        with pytest.raises(ValueError, match="frame_count must be >= 4"):
            _validate_fly_params({
                "object_name": "X",
                "frame_count": 3,
            })


# ---------------------------------------------------------------------------
# TestIdleParams
# ---------------------------------------------------------------------------


class TestIdleParams:
    """Test _validate_idle_params pure-logic validation."""

    def test_valid_defaults(self):
        result = _validate_idle_params({"object_name": "Creature"})
        assert result["object_name"] == "Creature"
        assert result["frame_count"] == 48
        assert result["breathing_intensity"] == 1.0

    def test_valid_all_params(self):
        result = _validate_idle_params({
            "object_name": "NPC",
            "frame_count": 64,
            "breathing_intensity": 0.5,
        })
        assert result["frame_count"] == 64
        assert result["breathing_intensity"] == 0.5

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_idle_params({})

    def test_negative_breathing_intensity_raises(self):
        with pytest.raises(ValueError, match="breathing_intensity must be > 0"):
            _validate_idle_params({
                "object_name": "X",
                "breathing_intensity": -1.0,
            })

    def test_zero_breathing_intensity_raises(self):
        with pytest.raises(ValueError, match="breathing_intensity must be > 0"):
            _validate_idle_params({
                "object_name": "X",
                "breathing_intensity": 0.0,
            })

    def test_frame_count_too_small_raises(self):
        with pytest.raises(ValueError, match="frame_count must be >= 4"):
            _validate_idle_params({
                "object_name": "X",
                "frame_count": 2,
            })

    def test_high_breathing_intensity_valid(self):
        result = _validate_idle_params({
            "object_name": "X",
            "breathing_intensity": 3.0,
        })
        assert result["breathing_intensity"] == 3.0


# ---------------------------------------------------------------------------
# TestAttackParams
# ---------------------------------------------------------------------------


class TestAttackParams:
    """Test _validate_attack_params pure-logic validation."""

    def test_valid_melee_swing(self):
        result = _validate_attack_params({
            "object_name": "Enemy",
            "attack_type": "melee_swing",
        })
        assert result["attack_type"] == "melee_swing"
        assert result["intensity"] == 1.0
        assert result["frame_count"] == 24

    def test_valid_all_params(self):
        result = _validate_attack_params({
            "object_name": "Boss",
            "attack_type": "breath_attack",
            "frame_count": 36,
            "intensity": 2.5,
        })
        assert result["attack_type"] == "breath_attack"
        assert result["frame_count"] == 36
        assert result["intensity"] == 2.5

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_attack_params({"attack_type": "bite"})

    def test_missing_attack_type_raises(self):
        with pytest.raises(ValueError, match="attack_type is required"):
            _validate_attack_params({"object_name": "X"})

    def test_invalid_attack_type_raises(self):
        with pytest.raises(ValueError, match="Invalid attack_type"):
            _validate_attack_params({
                "object_name": "X",
                "attack_type": "fireball",
            })

    def test_intensity_too_low_raises(self):
        with pytest.raises(ValueError, match="intensity must be between"):
            _validate_attack_params({
                "object_name": "X",
                "attack_type": "bite",
                "intensity": 0.05,
            })

    def test_intensity_too_high_raises(self):
        with pytest.raises(ValueError, match="intensity must be between"):
            _validate_attack_params({
                "object_name": "X",
                "attack_type": "bite",
                "intensity": 5.1,
            })

    def test_intensity_at_minimum_valid(self):
        result = _validate_attack_params({
            "object_name": "X",
            "attack_type": "slam",
            "intensity": 0.1,
        })
        assert result["intensity"] == pytest.approx(0.1)

    def test_intensity_at_maximum_valid(self):
        result = _validate_attack_params({
            "object_name": "X",
            "attack_type": "slam",
            "intensity": 5.0,
        })
        assert result["intensity"] == pytest.approx(5.0)

    @pytest.mark.parametrize("attack_type", sorted(VALID_ATTACK_TYPES))
    def test_all_attack_types_accepted(self, attack_type):
        result = _validate_attack_params({
            "object_name": "X",
            "attack_type": attack_type,
        })
        assert result["attack_type"] == attack_type

    def test_frame_count_too_small_raises(self):
        with pytest.raises(ValueError, match="frame_count must be >= 4"):
            _validate_attack_params({
                "object_name": "X",
                "attack_type": "bite",
                "frame_count": 3,
            })


# ---------------------------------------------------------------------------
# TestReactionParams
# ---------------------------------------------------------------------------


class TestReactionParams:
    """Test _validate_reaction_params pure-logic validation."""

    def test_valid_death(self):
        result = _validate_reaction_params({
            "object_name": "Enemy",
            "reaction_type": "death",
        })
        assert result["reaction_type"] == "death"
        assert result["frame_count"] == 24

    def test_valid_hit_with_direction(self):
        result = _validate_reaction_params({
            "object_name": "Enemy",
            "reaction_type": "hit",
            "direction": "left",
        })
        assert result["reaction_type"] == "hit"
        assert result["direction"] == "left"

    def test_valid_spawn(self):
        result = _validate_reaction_params({
            "object_name": "Enemy",
            "reaction_type": "spawn",
        })
        assert result["reaction_type"] == "spawn"

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_reaction_params({"reaction_type": "death"})

    def test_missing_reaction_type_raises(self):
        with pytest.raises(ValueError, match="reaction_type is required"):
            _validate_reaction_params({"object_name": "X"})

    def test_invalid_reaction_type_raises(self):
        with pytest.raises(ValueError, match="Invalid reaction_type"):
            _validate_reaction_params({
                "object_name": "X",
                "reaction_type": "stun",
            })

    def test_invalid_hit_direction_raises(self):
        with pytest.raises(ValueError, match="Invalid direction"):
            _validate_reaction_params({
                "object_name": "X",
                "reaction_type": "hit",
                "direction": "up",
            })

    @pytest.mark.parametrize("direction", sorted(VALID_HIT_DIRECTIONS))
    def test_all_hit_directions_accepted(self, direction):
        result = _validate_reaction_params({
            "object_name": "X",
            "reaction_type": "hit",
            "direction": direction,
        })
        assert result["direction"] == direction

    @pytest.mark.parametrize("reaction_type", sorted(VALID_REACTION_TYPES))
    def test_all_reaction_types_accepted(self, reaction_type):
        result = _validate_reaction_params({
            "object_name": "X",
            "reaction_type": reaction_type,
        })
        assert result["reaction_type"] == reaction_type

    def test_direction_ignored_for_death(self):
        # Direction param should not cause error for non-hit types
        result = _validate_reaction_params({
            "object_name": "X",
            "reaction_type": "death",
            "direction": "left",
        })
        assert result["reaction_type"] == "death"

    def test_default_direction_is_front(self):
        result = _validate_reaction_params({
            "object_name": "X",
            "reaction_type": "hit",
        })
        assert result["direction"] == "front"

    def test_frame_count_too_small_raises(self):
        with pytest.raises(ValueError, match="frame_count must be >= 4"):
            _validate_reaction_params({
                "object_name": "X",
                "reaction_type": "death",
                "frame_count": 1,
            })


# ---------------------------------------------------------------------------
# TestCustomParams
# ---------------------------------------------------------------------------


class TestCustomParams:
    """Test _validate_custom_params pure-logic validation."""

    def test_valid_basic(self):
        result = _validate_custom_params({
            "object_name": "Creature",
            "description": "raise wings then swing arms",
        })
        assert result["object_name"] == "Creature"
        assert result["description"] == "raise wings then swing arms"
        assert result["frame_count"] == 48

    def test_valid_all_params(self):
        result = _validate_custom_params({
            "object_name": "NPC",
            "description": "nod head",
            "frame_count": 24,
        })
        assert result["frame_count"] == 24

    def test_missing_object_name_raises(self):
        with pytest.raises(ValueError, match="object_name is required"):
            _validate_custom_params({"description": "raise arms"})

    def test_missing_description_raises(self):
        with pytest.raises(ValueError, match="description is required"):
            _validate_custom_params({"object_name": "X"})

    def test_empty_description_raises(self):
        with pytest.raises(ValueError, match="description is required"):
            _validate_custom_params({
                "object_name": "X",
                "description": "",
            })

    def test_whitespace_only_description_raises(self):
        with pytest.raises(ValueError, match="description is required"):
            _validate_custom_params({
                "object_name": "X",
                "description": "   ",
            })

    def test_non_string_description_raises(self):
        with pytest.raises(ValueError, match="description is required"):
            _validate_custom_params({
                "object_name": "X",
                "description": 42,
            })

    def test_description_stripped(self):
        result = _validate_custom_params({
            "object_name": "X",
            "description": "  raise arms  ",
        })
        assert result["description"] == "raise arms"

    def test_frame_count_too_small_raises(self):
        with pytest.raises(ValueError, match="frame_count must be >= 4"):
            _validate_custom_params({
                "object_name": "X",
                "description": "nod head",
                "frame_count": 2,
            })

    def test_frame_count_cast_to_int(self):
        result = _validate_custom_params({
            "object_name": "X",
            "description": "wave hand",
            "frame_count": "32",
        })
        assert result["frame_count"] == 32
        assert isinstance(result["frame_count"], int)


# ---------------------------------------------------------------------------
# TestNoBlenderImportsInValidation
# ---------------------------------------------------------------------------


class TestNoBlenderImportsInValidation:
    """Verify pure-logic validators work without Blender."""

    def test_walk_validator_is_pure_logic(self):
        """Walk validator should not touch bpy."""
        result = _validate_walk_params({
            "object_name": "Test",
            "gait": "biped",
            "speed": "walk",
        })
        assert result is not None

    def test_attack_validator_is_pure_logic(self):
        """Attack validator should not touch bpy."""
        result = _validate_attack_params({
            "object_name": "Test",
            "attack_type": "melee_swing",
        })
        assert result is not None

    def test_custom_validator_is_pure_logic(self):
        """Custom validator should not touch bpy."""
        result = _validate_custom_params({
            "object_name": "Test",
            "description": "raise arms",
        })
        assert result is not None

    def test_all_validators_callable_without_bpy(self):
        """All 6 validators should be callable without Blender."""
        validators = [
            (_validate_walk_params, {"object_name": "X"}),
            (_validate_fly_params, {"object_name": "X"}),
            (_validate_idle_params, {"object_name": "X"}),
            (_validate_attack_params, {"object_name": "X", "attack_type": "bite"}),
            (_validate_reaction_params, {"object_name": "X", "reaction_type": "death"}),
            (_validate_custom_params, {"object_name": "X", "description": "nod head"}),
        ]
        for validator, params in validators:
            result = validator(params)
            assert isinstance(result, dict)
            assert "object_name" in result
