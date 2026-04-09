"""Tests for Bundle B+C+D supplements (Addendum 1.B.2/3/4, 2.B.1, 2.C.2, 2.J).

Covers:
  * terrain_materials_ext       (MaterialChannelExt, texel density,
                                 height-blended gamma, cliff silhouette)
  * terrain_waterfalls_volumetric (volumetric profile, 7 functional
                                   objects, anchor screen-space, naming)
  * terrain_quality_profiles    (4 profiles + inheritance merge)
  * terrain_checkpoints_ext     (lock, filename, retention, autosave)
  * terrain_legacy_bug_fixes    (np.clip static auditor)
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pytest

from blender_addon.handlers.terrain_materials_v2 import MaterialChannel
from blender_addon.handlers.terrain_materials_ext import (
    HERO_CLIFF_MIN_FRAC,
    SECONDARY_CLIFF_MIN_FRAC,
    MaterialChannelExt,
    compute_height_blended_weights,
    validate_cliff_silhouette_area,
    validate_texel_density_coherency,
)
from blender_addon.handlers.terrain_waterfalls_volumetric import (
    FUNCTIONAL_SUFFIXES,
    WaterfallFunctionalObjects,
    WaterfallVolumetricProfile,
    build_waterfall_functional_object_names,
    enforce_functional_object_naming,
    validate_waterfall_anchor_screen_space,
    validate_waterfall_volumetric,
)
from blender_addon.handlers.terrain_quality_profiles import (
    AAA_OPEN_WORLD_PROFILE,
    HERO_SHOT_PROFILE,
    PREVIEW_PROFILE,
    PRODUCTION_PROFILE,
    TerrainQualityProfile,
    list_quality_profiles,
    load_quality_profile,
    write_profile_jsons,
)
from blender_addon.handlers.terrain_checkpoints_ext import (
    PresetLocked,
    assert_preset_unlocked,
    enforce_retention_policy,
    generate_checkpoint_filename,
    is_preset_locked,
    lock_preset,
    save_every_n_operations,
    unlock_preset,
)
from blender_addon.handlers.terrain_legacy_bug_fixes import (
    TARGET_LINES,
    audit_np_clip_in_file,
    audit_terrain_advanced_world_units,
)


# ---------------------------------------------------------------------------
# MaterialChannelExt + validators
# ---------------------------------------------------------------------------


def _ch(name: str, **kw) -> MaterialChannelExt:
    return MaterialChannelExt(base=MaterialChannel(channel_id=name), **kw)


def test_material_channel_ext_defaults():
    ext = _ch("ground")
    assert ext.height_blend_gamma == 1.0
    assert ext.texel_density_m == 64.0
    assert ext.micro_normal_texture is None
    assert ext.micro_normal_strength == 0.8
    assert ext.respects_displacement is True
    assert ext.channel_id == "ground"


def test_material_channel_ext_override():
    ext = _ch(
        "cliff",
        height_blend_gamma=2.5,
        texel_density_m=128.0,
        micro_normal_texture="cliff_detail.png",
        micro_normal_strength=0.6,
        respects_displacement=False,
    )
    assert ext.height_blend_gamma == 2.5
    assert ext.micro_normal_texture == "cliff_detail.png"
    assert ext.respects_displacement is False


def test_texel_density_coherent_ok():
    chans = [_ch("a", texel_density_m=64.0), _ch("b", texel_density_m=96.0)]
    issues = validate_texel_density_coherency(chans, max_ratio=2.0)
    assert issues == []


def test_texel_density_flags_high_ratio():
    chans = [_ch("a", texel_density_m=32.0), _ch("b", texel_density_m=128.0)]
    issues = validate_texel_density_coherency(chans, max_ratio=2.0)
    codes = [i.code for i in issues]
    assert "MAT_TEXEL_DENSITY_INCOHERENT" in codes
    # The offending channel is "b"
    assert any(i.affected_feature == "b" for i in issues)


def test_texel_density_rejects_nonpositive():
    chans = [_ch("a", texel_density_m=0.0), _ch("b", texel_density_m=64.0)]
    issues = validate_texel_density_coherency(chans)
    assert any(i.code == "MAT_TEXEL_DENSITY_INVALID" for i in issues)


def test_texel_density_single_channel_ok():
    issues = validate_texel_density_coherency([_ch("only")])
    assert issues == []


def test_height_blend_gamma_shape_and_normalization():
    h, w, L = 4, 5, 3
    base = np.full((h, w, L), 1.0 / L, dtype=np.float32)
    heights = np.linspace(0.0, 100.0, h * w).reshape(h, w)
    out = compute_height_blended_weights(base, heights, [1.0, 2.0, 0.5])
    assert out.shape == (h, w, L)
    # Each cell should sum to ~1
    sums = out.sum(axis=2)
    assert np.allclose(sums, 1.0, atol=1e-5)


def test_height_blend_gamma_affects_layers_nonuniformly():
    h, w, L = 2, 2, 2
    base = np.full((h, w, L), 0.5, dtype=np.float32)
    heights = np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float64)
    # Layer 0 gamma=4 (biased to peaks), layer 1 gamma=0.25 (biased to valleys)
    out = compute_height_blended_weights(base, heights, [4.0, 0.25])
    # At the top (h=30), layer 0 should exceed layer 1
    assert out[1, 1, 0] > out[1, 1, 1]


def test_height_blend_wrong_shape_raises():
    base = np.zeros((3, 3, 2), dtype=np.float32)
    heights = np.zeros((4, 4), dtype=np.float64)
    with pytest.raises(ValueError):
        compute_height_blended_weights(base, heights, [1.0, 1.0])


def test_height_blend_wrong_gamma_count_raises():
    base = np.zeros((2, 2, 3), dtype=np.float32)
    heights = np.zeros((2, 2), dtype=np.float64)
    with pytest.raises(ValueError):
        compute_height_blended_weights(base, heights, [1.0, 1.0])


def test_cliff_silhouette_hero_below_threshold_rejected():
    issues = validate_cliff_silhouette_area(0.05, tier="hero")
    assert any(i.code == "CLIFF_SILHOUETTE_TOO_SMALL" for i in issues)
    # 0.05 is above secondary threshold (0.03), so secondary should pass
    assert validate_cliff_silhouette_area(0.05, tier="secondary") == []


def test_cliff_silhouette_hero_above_threshold_ok():
    assert validate_cliff_silhouette_area(HERO_CLIFF_MIN_FRAC + 0.01, tier="hero") == []


def test_cliff_silhouette_secondary_below_threshold_rejected():
    issues = validate_cliff_silhouette_area(0.01, tier="secondary")
    assert any(i.code == "CLIFF_SILHOUETTE_TOO_SMALL" for i in issues)


def test_cliff_silhouette_unknown_tier():
    issues = validate_cliff_silhouette_area(0.5, tier="cinematic")
    assert any(i.code == "CLIFF_SILHOUETTE_UNKNOWN_TIER" for i in issues)


# ---------------------------------------------------------------------------
# Waterfall volumetric + functional objects
# ---------------------------------------------------------------------------


def test_waterfall_volumetric_profile_defaults():
    p = WaterfallVolumetricProfile()
    assert p.vertex_density_per_meter == 48.0
    assert p.front_curvature_radius_ratio == 0.15
    assert p.min_non_coplanar_front_fraction == 0.30


def test_build_waterfall_functional_objects_returns_seven_named():
    names = build_waterfall_functional_object_names("alpha")
    lst = names.as_list()
    assert len(lst) == 7
    assert all(n.startswith("WF_alpha_") for n in lst)
    suffixes = [n.split("WF_alpha_", 1)[1] for n in lst]
    assert set(suffixes) == set(FUNCTIONAL_SUFFIXES)


def test_build_waterfall_empty_id_raises():
    with pytest.raises(ValueError):
        build_waterfall_functional_object_names("")


def test_validate_waterfall_volumetric_rejects_low_vertex_count():
    profile = WaterfallVolumetricProfile()
    # Need 48 * 10 = 480 verts minimum
    issues = validate_waterfall_volumetric(
        profile, vertex_count=100, drop_m=10.0,
        front_normals_cos=[0.1, 0.2, 0.3, 0.4],
    )
    assert any(i.code == "WATERFALL_VERTEX_DENSITY_TOO_LOW" for i in issues)


def test_validate_waterfall_volumetric_rejects_coplanar_front():
    profile = WaterfallVolumetricProfile()
    # All cosines ~1 means coplanar
    cos = [0.99, 0.995, 1.0, 0.99, 0.998] * 20
    issues = validate_waterfall_volumetric(
        profile, vertex_count=5000, drop_m=10.0, front_normals_cos=cos,
    )
    assert any(i.code == "WATERFALL_FRONT_COPLANAR" for i in issues)


def test_validate_waterfall_volumetric_passes_good_geometry():
    profile = WaterfallVolumetricProfile()
    # Half the normals strongly non-coplanar
    cos = [0.5] * 50 + [0.99] * 50
    issues = validate_waterfall_volumetric(
        profile, vertex_count=10000, drop_m=10.0, front_normals_cos=cos,
    )
    codes = {i.code for i in issues}
    assert "WATERFALL_VERTEX_DENSITY_TOO_LOW" not in codes
    assert "WATERFALL_FRONT_COPLANAR" not in codes


def test_validate_waterfall_empty_normals_fails():
    profile = WaterfallVolumetricProfile()
    issues = validate_waterfall_volumetric(
        profile, vertex_count=10000, drop_m=5.0, front_normals_cos=[],
    )
    assert any(i.code == "WATERFALL_FRONT_NORMALS_MISSING" for i in issues)


def test_anchor_screen_space_detects_drift():
    issues = validate_waterfall_anchor_screen_space(
        chain_lip_pos=(0.0, 0.0, 10.0),
        anchor_pos=(50.0, 0.0, 10.0),
        anchor_radius=5.0,
        vantage_position=(100.0, 0.0, 10.0),
    )
    assert any(i.code == "WATERFALL_ANCHOR_DRIFT" for i in issues)


def test_anchor_screen_space_within_radius_ok():
    issues = validate_waterfall_anchor_screen_space(
        chain_lip_pos=(0.0, 0.0, 10.0),
        anchor_pos=(2.0, 1.0, 10.0),
        anchor_radius=5.0,
        vantage_position=(30.0, 0.0, 10.0),
    )
    assert all(i.code != "WATERFALL_ANCHOR_DRIFT" for i in issues)


def test_anchor_invalid_radius():
    issues = validate_waterfall_anchor_screen_space(
        (0, 0, 0), (0, 0, 0), -1.0, (1, 0, 0),
    )
    assert any(i.code == "WATERFALL_ANCHOR_RADIUS_INVALID" for i in issues)


def test_enforce_functional_object_naming_all_present():
    names = build_waterfall_functional_object_names("alpha").as_list()
    issues = enforce_functional_object_naming(names, "alpha")
    assert issues == []


def test_enforce_functional_object_naming_missing_suffix():
    names = build_waterfall_functional_object_names("alpha").as_list()
    # Drop one object
    names = [n for n in names if "impact_pool" not in n]
    issues = enforce_functional_object_naming(names, "alpha")
    assert any(
        i.code == "WATERFALL_FUNCTIONAL_OBJECT_MISSING"
        and "impact_pool" in i.message
        for i in issues
    )


def test_enforce_functional_object_naming_wrong_chain():
    names = ["WF_alpha_river_surface"]
    issues = enforce_functional_object_naming(names, "beta")
    assert any(i.code == "WATERFALL_OBJECT_WRONG_CHAIN" for i in issues)


def test_enforce_functional_object_naming_unknown_suffix():
    names = build_waterfall_functional_object_names("x").as_list() + [
        "WF_x_rainbow_vfx"
    ]
    issues = enforce_functional_object_naming(names, "x")
    assert any(i.code == "WATERFALL_OBJECT_UNKNOWN_SUFFIX" for i in issues)


# ---------------------------------------------------------------------------
# Quality profiles
# ---------------------------------------------------------------------------


def test_list_quality_profiles_order():
    assert list_quality_profiles() == [
        "preview",
        "production",
        "hero_shot",
        "aaa_open_world",
    ]


def test_load_quality_profile_all_four():
    for name in list_quality_profiles():
        p = load_quality_profile(name)
        assert isinstance(p, TerrainQualityProfile)
        assert p.name == name


def test_load_quality_profile_unknown_raises():
    with pytest.raises(KeyError):
        load_quality_profile("cinematic_2050")


def test_profile_inheritance_hero_floors_production():
    """hero_shot must have erosion_iterations >= production's value."""
    production = load_quality_profile("production")
    hero = load_quality_profile("hero_shot")
    assert hero.erosion_iterations >= production.erosion_iterations
    assert hero.checkpoint_retention >= production.checkpoint_retention
    assert hero.splatmap_bit_depth >= production.splatmap_bit_depth


def test_profile_inheritance_aaa_floors_hero():
    hero = load_quality_profile("hero_shot")
    aaa = load_quality_profile("aaa_open_world")
    assert aaa.erosion_iterations >= hero.erosion_iterations
    assert aaa.checkpoint_retention >= hero.checkpoint_retention
    assert aaa.erosion_margin_cells >= hero.erosion_margin_cells


def test_write_profile_jsons(tmp_path: Path):
    written = write_profile_jsons(tmp_path)
    assert len(written) == 4
    for p in written:
        data = json.loads(p.read_text())
        assert "name" in data
        assert "erosion_iterations" in data
        assert "splatmap_bit_depth" in data


def test_preset_jsons_on_disk():
    """The 4 preset JSONs shipped with the repo must exist."""
    root = Path(__file__).resolve().parents[1] / "presets" / "terrain" / "quality_profiles"
    for name in ("preview", "production", "hero_shot", "aaa_open_world"):
        p = root / f"{name}.json"
        assert p.exists(), f"missing preset JSON: {p}"
        data = json.loads(p.read_text())
        assert data["name"] == name


# ---------------------------------------------------------------------------
# Checkpoint extensions
# ---------------------------------------------------------------------------


def test_generate_checkpoint_filename_format():
    fn = generate_checkpoint_filename(1, "macro", "abcdef1234567890")
    assert fn == "terrain_01_macro_abcdef12.blend"


def test_generate_checkpoint_filename_pads():
    fn = generate_checkpoint_filename(7, "erosion", "0123456789")
    assert fn.startswith("terrain_07_erosion_")
    assert fn.endswith(".blend")


def test_generate_checkpoint_filename_sanitizes_passname():
    fn = generate_checkpoint_filename(2, "hot/reload pass!", "deadbeefcafebabe")
    assert "/" not in fn
    assert " " not in fn
    assert fn.endswith("_deadbeef.blend")


def test_generate_checkpoint_filename_empty_hash():
    fn = generate_checkpoint_filename(3, "macro", "")
    assert fn == "terrain_03_macro_00000000.blend"


def test_generate_checkpoint_filename_negative_pass_raises():
    with pytest.raises(ValueError):
        generate_checkpoint_filename(-1, "macro", "abcd1234")


def test_preset_lock_roundtrip():
    lock_preset("__test_lock__")
    assert is_preset_locked("__test_lock__")
    with pytest.raises(PresetLocked):
        assert_preset_unlocked("__test_lock__")
    unlock_preset("__test_lock__")
    assert not is_preset_locked("__test_lock__")


def test_enforce_retention_policy_deletes_oldest(tmp_path: Path):
    # Per Addendum 1.B.4 production profile keeps 20 most-recent checkpoints.
    profile = PRODUCTION_PROFILE
    total = profile.checkpoint_retention + 6
    for i in range(total):
        p = tmp_path / f"terrain_{i:02d}_macro_{i:08x}.blend"
        p.write_text("data")
        # Stagger mtime so ordering is deterministic
        os_time = time.time() - (total - i)
        import os
        os.utime(p, (os_time, os_time))
    deleted = enforce_retention_policy(tmp_path, profile)
    assert len(deleted) == 6
    remaining = sorted(tmp_path.iterdir())
    assert len(remaining) == profile.checkpoint_retention


def test_enforce_retention_policy_under_limit_noop(tmp_path: Path):
    for i in range(2):
        (tmp_path / f"terrain_{i:02d}_macro_{i:08x}.blend").write_text("data")
    deleted = enforce_retention_policy(tmp_path, PRODUCTION_PROFILE)
    assert deleted == []


def test_enforce_retention_policy_missing_dir(tmp_path: Path):
    missing = tmp_path / "does_not_exist"
    assert enforce_retention_policy(missing, PRODUCTION_PROFILE) == []


def test_save_every_n_operations_monkey_patches():
    saves: list = []

    class FakeController:
        def __init__(self):
            self.counter = 0

        def run_pass(self, name):
            self.counter += 1

            class R:
                pass_name = name

            return R()

        def _save_checkpoint(self, pass_name):
            saves.append(pass_name)

    c = FakeController()
    unpatch = save_every_n_operations(c, n=3)
    for i in range(6):
        c.run_pass(f"p{i}")
    assert len(saves) == 2  # every 3rd
    unpatch()
    # After unpatch, run_pass is the original and no more saves
    c.run_pass("after")
    assert len(saves) == 2


def test_save_every_n_operations_invalid_n():
    class C:
        def run_pass(self, x):
            return None

    with pytest.raises(ValueError):
        save_every_n_operations(C(), n=0)


# ---------------------------------------------------------------------------
# Legacy np.clip auditor
# ---------------------------------------------------------------------------


def test_audit_np_clip_in_file_format(tmp_path: Path):
    src = tmp_path / "t.py"
    src.write_text("a = 1\nb = np.clip(x, 0, 1)\nc = 2\n")
    results = audit_np_clip_in_file(src)
    assert len(results) == 1
    entry = results[0]
    assert entry["file"] == str(src)
    assert entry["line"] == 2
    assert "np.clip" in entry["snippet"]


def test_audit_np_clip_missing_file(tmp_path: Path):
    assert audit_np_clip_in_file(tmp_path / "nope.py") == []


def test_audit_terrain_advanced_reports_target_lines():
    result = audit_terrain_advanced_world_units()
    assert result["target_lines"] == list(TARGET_LINES)
    # The auditor must report all 4 target entries (even if not exact match)
    assert len(result["targets"]) == 4
    for tgt in TARGET_LINES:
        assert str(tgt) in result["targets"]
    # At least some np.clip calls exist in the file
    assert result["summary"]["clip_count"] > 0
