"""Tests for monster-specific animation generators. Pure-logic."""
import pytest
from blender_addon.handlers.animation_monster import (
    VALID_MONSTER_ANIMS, validate_monster_anim_params, generate_monster_anim_keyframes,
    generate_reassemble_keyframes, generate_burrow_enter_keyframes, generate_burrow_exit_keyframes,
    generate_phase_shift_keyframes, generate_bloat_inflate_keyframes, generate_regurgitate_keyframes,
    generate_entangle_keyframes, generate_boss_phase_transition_keyframes,
    generate_gnaw_loop_keyframes, generate_shadow_embrace_keyframes, generate_chorus_keyframes,
    generate_plant_growth_keyframes, generate_spawn_broodling_keyframes,
)
from blender_addon.handlers.animation_gaits import Keyframe


class TestValidation:
    def test_valid(self):
        r = validate_monster_anim_params({"object_name": "X", "anim_type": "reassemble"})
        assert r["anim_type"] == "reassemble"

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_monster_anim_params({"object_name": "X", "anim_type": "fly"})

    @pytest.mark.parametrize("at", sorted(VALID_MONSTER_ANIMS))
    def test_all_types(self, at):
        r = validate_monster_anim_params({"object_name": "X", "anim_type": at})
        assert r["anim_type"] == at


class TestReassemble:
    def test_returns_keyframes(self):
        kfs = generate_reassemble_keyframes()
        assert len(kfs) > 0
    def test_converges_to_rest(self):
        kfs = generate_reassemble_keyframes(frame_count=36)
        final_locs = [kf.value for kf in kfs if kf.frame == 36 and kf.channel == "location"]
        assert all(abs(v) < 0.05 for v in final_locs), "Should converge to rest"


class TestBurrow:
    def test_enter_sinks(self):
        kfs = generate_burrow_enter_keyframes()
        z_vals = [kf.value for kf in kfs if kf.bone_name == "DEF-spine" and kf.channel == "location" and kf.axis == 2]
        assert min(z_vals) < -0.5
    def test_exit_rises(self):
        kfs = generate_burrow_exit_keyframes()
        assert len(kfs) > 0


class TestPhaseShift:
    def test_vanishes_and_reappears(self):
        kfs = generate_phase_shift_keyframes()
        scales = [kf.value for kf in kfs if kf.channel == "scale"]
        assert min(scales) < 0.1, "Should vanish"
        assert max(scales) > 0.8, "Should reappear"


class TestBloat:
    def test_inflates(self):
        kfs = generate_bloat_inflate_keyframes()
        scales = [kf.value for kf in kfs if kf.channel == "scale" and kf.frame > 20]
        assert max(scales) > 1.3


class TestRegurgitate:
    def test_has_jaw(self):
        kfs = generate_regurgitate_keyframes()
        jaw = [kf for kf in kfs if kf.bone_name == "DEF-jaw"]
        assert len(jaw) > 0


class TestEntangle:
    def test_arms_reach(self):
        kfs = generate_entangle_keyframes()
        arm = [kf for kf in kfs if "upper_arm" in kf.bone_name]
        assert any(kf.value < -0.5 for kf in arm)


class TestBossTransition:
    def test_scale_increases(self):
        kfs = generate_boss_phase_transition_keyframes()
        final_scales = [kf.value for kf in kfs if kf.channel == "scale" and kf.frame == 60]
        assert any(v > 1.2 for v in final_scales)


class TestGnawLoop:
    def test_jaw_oscillates(self):
        kfs = generate_gnaw_loop_keyframes()
        jaw = [kf.value for kf in kfs if kf.bone_name == "DEF-jaw"]
        assert max(jaw) > 0.2 and min(jaw) < 0.1


class TestShadowEmbrace:
    def test_expands(self):
        kfs = generate_shadow_embrace_keyframes()
        scales = [kf.value for kf in kfs if kf.channel == "scale" and kf.axis == 0]
        assert max(scales) > 1.2


class TestChorus:
    def test_jaw_chants(self):
        kfs = generate_chorus_keyframes()
        jaw = [kf for kf in kfs if kf.bone_name == "DEF-jaw"]
        assert len(jaw) > 0


class TestPlantGrowth:
    def test_grows_from_ground(self):
        kfs = generate_plant_growth_keyframes()
        z_vals = [kf.value for kf in kfs if kf.channel == "location" and kf.axis == 2]
        assert min(z_vals) < -0.5, "Should start below ground"


class TestSpawnBroodling:
    def test_has_contraction(self):
        kfs = generate_spawn_broodling_keyframes()
        spine = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        assert any(kf.value > 0.2 for kf in spine)


class TestDispatch:
    @pytest.mark.parametrize("at", sorted(VALID_MONSTER_ANIMS))
    def test_all_dispatch(self, at):
        params = {"anim_type": at, "frame_count": 12, "intensity": 1.0}
        kfs = generate_monster_anim_keyframes(params)
        assert len(kfs) > 0


class TestConstants:
    def test_count(self):
        assert len(VALID_MONSTER_ANIMS) == 17
