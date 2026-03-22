"""Unit tests for Phase 23 VFX Mastery C# template generators.

Tests that each generator function:
1. Returns a dict with script_path, script_content, next_steps
2. Produces valid C# source with balanced braces and proper syntax
3. Contains expected Unity API calls, classes, and parameter substitutions
4. Handles custom parameters correctly

Requirements covered:
    VFX3-01: Flipbook texture sheets (generate_flipbook_script)
    VFX3-02: VFX Graph composition (generate_vfx_graph_composition_script)
    VFX3-03: Projectile VFX chains (generate_projectile_vfx_chain_script)
    VFX3-04: Area-of-effect VFX (generate_aoe_vfx_script)
    VFX3-05: Per-brand status effect VFX (generate_status_effect_vfx_script)
    VFX3-06: Environmental VFX depth (generate_environmental_vfx_script)
    VFX3-07: Directional combat hit VFX (generate_directional_hit_vfx_script)
    VFX3-08: Boss phase transition VFX (generate_boss_transition_vfx_script)
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.vfx_mastery_templates import (
    generate_flipbook_script,
    generate_vfx_graph_composition_script,
    generate_projectile_vfx_chain_script,
    generate_aoe_vfx_script,
    generate_status_effect_vfx_script,
    generate_environmental_vfx_script,
    generate_directional_hit_vfx_script,
    generate_boss_transition_vfx_script,
    BRAND_COLORS,
    ALL_BRANDS,
    FLIPBOOK_EFFECT_TYPES,
    AOE_TYPES,
    ENV_VFX_TYPES,
    BOSS_TRANSITION_TYPES,
    BRAND_STATUS_CONFIGS,
)


# ---------------------------------------------------------------------------
# Helpers for C# validation
# ---------------------------------------------------------------------------


def _check_balanced_braces(code: str) -> bool:
    """Verify that curly braces are balanced in the generated C# code."""
    count = 0
    for ch in code:
        if ch == "{":
            count += 1
        elif ch == "}":
            count -= 1
        if count < 0:
            return False
    return count == 0


def _check_output_structure(result: dict) -> None:
    """Assert that a generator result has the correct dict structure."""
    assert isinstance(result, dict), "Result must be a dict"
    assert "script_path" in result, "Missing script_path"
    assert "script_content" in result, "Missing script_content"
    assert "next_steps" in result, "Missing next_steps"
    assert isinstance(result["script_path"], str), "script_path must be str"
    assert isinstance(result["script_content"], str), "script_content must be str"
    assert isinstance(result["next_steps"], list), "next_steps must be list"
    assert len(result["next_steps"]) > 0, "next_steps must not be empty"
    assert len(result["script_content"]) > 100, "script_content too short"


def _check_cs_path(result: dict) -> None:
    """Assert that script_path ends with .cs."""
    assert result["script_path"].endswith(".cs"), "script_path must end with .cs"


# ===========================================================================
# Module-level constants tests
# ===========================================================================


class TestModuleConstants:
    """Tests for module-level constants and brand data."""

    def test_all_10_brands_present(self):
        expected = {"IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
                    "LEECH", "GRACE", "MEND", "RUIN", "VOID"}
        assert set(BRAND_COLORS.keys()) == expected

    def test_all_brands_list(self):
        assert len(ALL_BRANDS) == 10
        assert set(ALL_BRANDS) == set(BRAND_COLORS.keys())

    def test_brand_color_structure(self):
        for brand, data in BRAND_COLORS.items():
            assert "rgba" in data, f"{brand} missing rgba"
            assert "glow" in data, f"{brand} missing glow"
            assert "desc" in data, f"{brand} missing desc"
            assert len(data["rgba"]) == 4, f"{brand} rgba must have 4 values"
            assert len(data["glow"]) == 4, f"{brand} glow must have 4 values"
            assert "dark" in data, f"{brand} missing dark"
            assert len(data["dark"]) == 4, f"{brand} dark must have 4 values"

    def test_brand_rgba_values_valid(self):
        for brand, data in BRAND_COLORS.items():
            for i, v in enumerate(data["rgba"]):
                assert 0.0 <= v <= 1.0, f"{brand} rgba[{i}]={v} out of range"
            for i, v in enumerate(data["glow"]):
                assert 0.0 <= v <= 1.0, f"{brand} glow[{i}]={v} out of range"

    def test_flipbook_effect_types(self):
        expected = {"fire", "smoke", "energy", "sparks", "blood", "magic"}
        assert set(FLIPBOOK_EFFECT_TYPES.keys()) == expected

    def test_flipbook_type_structure(self):
        for etype, cfg in FLIPBOOK_EFFECT_TYPES.items():
            assert "base_color" in cfg, f"{etype} missing base_color"
            assert "particle_type" in cfg, f"{etype} missing particle_type"
            assert "emission_intensity" in cfg, f"{etype} missing emission_intensity"
            assert "noise_scale" in cfg, f"{etype} missing noise_scale"
            assert len(cfg["base_color"]) == 4

    def test_aoe_types(self):
        assert AOE_TYPES == {"ground_circle", "expanding_dome", "cone_blast", "ring_wave"}

    def test_env_vfx_types(self):
        assert ENV_VFX_TYPES == {"volumetric_fog", "god_rays", "heat_distortion", "water_caustics"}

    def test_boss_transition_types(self):
        assert BOSS_TRANSITION_TYPES == {"corruption_wave", "power_surge", "arena_transformation"}

    def test_brand_status_configs_all_brands(self):
        assert set(BRAND_STATUS_CONFIGS.keys()) == set(BRAND_COLORS.keys())

    def test_brand_status_config_structure(self):
        required_keys = {"effect_name", "description", "orbit_speed", "orbit_radius",
                         "particle_shape", "particle_speed", "glow_pulse_speed", "secondary_effect"}
        for brand, cfg in BRAND_STATUS_CONFIGS.items():
            for key in required_keys:
                assert key in cfg, f"{brand} status config missing {key}"


# ===========================================================================
# VFX3-01: Flipbook Texture Sheets
# ===========================================================================


class TestGenerateFlipbookScript:
    """Tests for generate_flipbook_script() -- VFX3-01."""

    def test_output_structure(self):
        result = generate_flipbook_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_flipbook_script()
        _check_cs_path(result)

    def test_path_contains_editor(self):
        result = generate_flipbook_script()
        assert "Editor" in result["script_path"]

    def test_balanced_braces(self):
        result = generate_flipbook_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_editor_window(self):
        result = generate_flipbook_script()
        assert "EditorWindow" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_flipbook_script()
        assert "MenuItem" in result["script_content"]

    def test_default_effect_type_fire(self):
        result = generate_flipbook_script()
        assert "fire" in result["script_content"]

    def test_custom_effect_type(self):
        result = generate_flipbook_script(effect_type="smoke")
        assert "smoke" in result["script_content"]

    def test_custom_grid_dimensions(self):
        result = generate_flipbook_script(rows=8, columns=8, resolution_per_frame=64)
        content = result["script_content"]
        assert "Rows = 8" in content
        assert "Columns = 8" in content
        assert "FrameRes = 64" in content

    def test_atlas_size_calculation(self):
        result = generate_flipbook_script(rows=4, columns=4, resolution_per_frame=128)
        content = result["script_content"]
        assert "AtlasWidth = 512" in content
        assert "AtlasHeight = 512" in content

    def test_frame_count_clamped(self):
        # 4x4 grid = max 16 frames, request 20
        result = generate_flipbook_script(rows=4, columns=4, frame_count=20)
        content = result["script_content"]
        assert "FrameCount = 16" in content

    def test_contains_render_texture(self):
        result = generate_flipbook_script()
        assert "RenderTexture" in result["script_content"]

    def test_contains_particle_system(self):
        result = generate_flipbook_script()
        assert "ParticleSystem" in result["script_content"]

    def test_contains_encode_to_png(self):
        result = generate_flipbook_script()
        assert "EncodeToPNG" in result["script_content"]

    def test_contains_texture_importer(self):
        result = generate_flipbook_script()
        assert "TextureImporter" in result["script_content"]

    def test_all_effect_types(self):
        for etype in FLIPBOOK_EFFECT_TYPES:
            result = generate_flipbook_script(effect_type=etype)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), f"Unbalanced for {etype}"

    def test_invalid_effect_type_fallback(self):
        result = generate_flipbook_script(effect_type="invalid_type")
        assert "fire" in result["script_content"]

    def test_custom_output_path(self):
        result = generate_flipbook_script(output_path="Assets/Custom/VFX")
        assert "Assets/Custom/VFX" in result["script_content"]

    def test_next_steps_mention_menu(self):
        result = generate_flipbook_script()
        assert any("VeilBreakers" in s for s in result["next_steps"])

    def test_result_json_write(self):
        result = generate_flipbook_script()
        assert "vb_result.json" in result["script_content"]

    def test_color_over_lifetime(self):
        result = generate_flipbook_script()
        assert "colorOverLifetime" in result["script_content"]

    def test_noise_module(self):
        result = generate_flipbook_script()
        assert "noise" in result["script_content"].lower()


# ===========================================================================
# VFX3-02: VFX Graph Composition
# ===========================================================================


class TestGenerateVFXGraphCompositionScript:
    """Tests for generate_vfx_graph_composition_script() -- VFX3-02."""

    def test_output_structure(self):
        result = generate_vfx_graph_composition_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_vfx_graph_composition_script()
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_vfx_graph_composition_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_vfx_graph_api(self):
        result = generate_vfx_graph_composition_script()
        content = result["script_content"]
        assert "UnityEditor.VFX" in content
        assert "UnityEngine.VFX" in content

    def test_contains_menu_item(self):
        result = generate_vfx_graph_composition_script()
        assert "MenuItem" in result["script_content"]

    def test_custom_graph_name(self):
        result = generate_vfx_graph_composition_script(graph_name="FireEffect")
        content = result["script_content"]
        assert "FireEffect" in content

    def test_custom_spawn_config(self):
        result = generate_vfx_graph_composition_script(
            spawn_config={"rate": 500.0, "burst_count": 50}
        )
        content = result["script_content"]
        assert "500" in content

    def test_custom_init_config(self):
        result = generate_vfx_graph_composition_script(
            init_config={"position_mode": "box", "lifetime": 5.0, "size": 0.3}
        )
        content = result["script_content"]
        assert "box" in content
        assert "5" in content

    def test_custom_update_config(self):
        result = generate_vfx_graph_composition_script(
            update_config={"gravity": -5.0, "turbulence_intensity": 2.0}
        )
        content = result["script_content"]
        assert "-5" in content

    def test_custom_output_config(self):
        result = generate_vfx_graph_composition_script(
            output_config={"output_type": "trail", "blend_mode": "Alpha"}
        )
        content = result["script_content"]
        assert "trail" in content
        assert "Alpha" in content

    def test_default_output_type(self):
        result = generate_vfx_graph_composition_script()
        assert "particle" in result["script_content"]

    def test_context_connection(self):
        result = generate_vfx_graph_composition_script()
        assert "TryConnect" in result["script_content"]

    def test_exposed_parameters(self):
        result = generate_vfx_graph_composition_script()
        assert "AddExposedParameter" in result["script_content"]

    def test_four_contexts_created(self):
        result = generate_vfx_graph_composition_script()
        content = result["script_content"]
        assert "Spawner" in content
        assert "Initialize" in content
        assert "Update" in content
        assert "Output" in content

    def test_invalid_position_mode_fallback(self):
        result = generate_vfx_graph_composition_script(
            init_config={"position_mode": "invalid"}
        )
        assert "sphere" in result["script_content"]

    def test_invalid_output_type_fallback(self):
        result = generate_vfx_graph_composition_script(
            output_config={"output_type": "invalid"}
        )
        assert "particle" in result["script_content"]

    def test_invalid_blend_mode_fallback(self):
        result = generate_vfx_graph_composition_script(
            output_config={"blend_mode": "invalid"}
        )
        assert "Additive" in result["script_content"]

    def test_result_json(self):
        result = generate_vfx_graph_composition_script()
        assert "vb_result.json" in result["script_content"]

    def test_asset_path_in_content(self):
        result = generate_vfx_graph_composition_script(graph_name="TestGraph")
        assert "Assets/Art/VFX/Graphs" in result["script_content"]


# ===========================================================================
# VFX3-03: Projectile VFX Chains
# ===========================================================================


class TestGenerateProjectileVFXChainScript:
    """Tests for generate_projectile_vfx_chain_script() -- VFX3-03."""

    def test_output_structure(self):
        result = generate_projectile_vfx_chain_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_projectile_vfx_chain_script()
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_projectile_vfx_chain_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_monobehaviour(self):
        result = generate_projectile_vfx_chain_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_contains_four_stages(self):
        result = generate_projectile_vfx_chain_script()
        content = result["script_content"]
        assert "SpawnBurst" in content
        assert "TravelTrail" in content
        assert "ImpactExplosion" in content
        assert "AftermathResidue" in content

    def test_default_brand_surge(self):
        result = generate_projectile_vfx_chain_script()
        assert "SURGE" in result["script_content"]

    def test_custom_brand(self):
        result = generate_projectile_vfx_chain_script(brand="IRON")
        assert "IRON" in result["script_content"]

    def test_brand_colors_applied(self):
        for brand_name in ALL_BRANDS:
            result = generate_projectile_vfx_chain_script(brand=brand_name)
            bc = BRAND_COLORS[brand_name]
            # Check that brand color values appear
            assert f"{bc['rgba'][0]}f" in result["script_content"]

    def test_custom_speed(self):
        result = generate_projectile_vfx_chain_script(projectile_speed=50.0)
        assert "50" in result["script_content"]

    def test_custom_stages(self):
        stages = [
            {"duration": 0.5, "rate": 300, "size": 0.2},
            {"duration": -1.0, "rate": 100, "size": 0.1},
            {"duration": 0.8, "rate": 600, "size": 0.5},
            {"duration": 3.0, "rate": 40, "size": 0.3},
        ]
        result = generate_projectile_vfx_chain_script(stages=stages)
        content = result["script_content"]
        assert "300" in content
        assert "600" in content

    def test_contains_coroutine(self):
        result = generate_projectile_vfx_chain_script()
        assert "IEnumerator" in result["script_content"]
        assert "StartCoroutine" in result["script_content"]

    def test_contains_raycast(self):
        result = generate_projectile_vfx_chain_script()
        assert "Raycast" in result["script_content"]

    def test_auto_cleanup(self):
        result = generate_projectile_vfx_chain_script()
        assert "Destroy(gameObject" in result["script_content"]

    def test_invalid_brand_fallback(self):
        result = generate_projectile_vfx_chain_script(brand="INVALID")
        assert "SURGE" in result["script_content"]

    def test_all_brands(self):
        for brand_name in ALL_BRANDS:
            result = generate_projectile_vfx_chain_script(brand=brand_name)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), f"Unbalanced for {brand_name}"

    def test_particle_system_creation(self):
        result = generate_projectile_vfx_chain_script()
        assert "ParticleSystem" in result["script_content"]
        assert "AddComponent<ParticleSystem>" in result["script_content"]

    def test_color_gradient(self):
        result = generate_projectile_vfx_chain_script()
        assert "Gradient" in result["script_content"]
        assert "GradientColorKey" in result["script_content"]


# ===========================================================================
# VFX3-04: Area-of-Effect VFX
# ===========================================================================


class TestGenerateAoEVFXScript:
    """Tests for generate_aoe_vfx_script() -- VFX3-04."""

    def test_output_structure(self):
        result = generate_aoe_vfx_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_aoe_vfx_script()
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_aoe_vfx_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_monobehaviour(self):
        result = generate_aoe_vfx_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_default_type_ground_circle(self):
        result = generate_aoe_vfx_script()
        assert "ground_circle" in result["script_content"]

    def test_all_aoe_types(self):
        for aoe_type in AOE_TYPES:
            result = generate_aoe_vfx_script(aoe_type=aoe_type)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), f"Unbalanced for {aoe_type}"

    def test_ground_circle_shape(self):
        result = generate_aoe_vfx_script(aoe_type="ground_circle")
        assert "Circle" in result["script_content"]

    def test_expanding_dome_shape(self):
        result = generate_aoe_vfx_script(aoe_type="expanding_dome")
        assert "Hemisphere" in result["script_content"]

    def test_cone_blast_shape(self):
        result = generate_aoe_vfx_script(aoe_type="cone_blast")
        assert "Cone" in result["script_content"]

    def test_ring_wave_shape(self):
        result = generate_aoe_vfx_script(aoe_type="ring_wave")
        assert "Circle" in result["script_content"]

    def test_custom_radius(self):
        result = generate_aoe_vfx_script(radius=10.0)
        assert "10" in result["script_content"]

    def test_custom_duration(self):
        result = generate_aoe_vfx_script(duration=5.0)
        assert "5" in result["script_content"]

    def test_custom_particle_count(self):
        result = generate_aoe_vfx_script(particle_count=500)
        assert "500" in result["script_content"]

    def test_brand_color_applied(self):
        result = generate_aoe_vfx_script(brand="GRACE")
        bc = BRAND_COLORS["GRACE"]
        assert f"{bc['rgba'][0]}f" in result["script_content"]

    def test_all_brands(self):
        for brand_name in ALL_BRANDS:
            result = generate_aoe_vfx_script(brand=brand_name)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"])

    def test_invalid_aoe_type_fallback(self):
        result = generate_aoe_vfx_script(aoe_type="invalid")
        assert "ground_circle" in result["script_content"]

    def test_invalid_brand_fallback(self):
        result = generate_aoe_vfx_script(brand="INVALID")
        assert "RUIN" in result["script_content"]

    def test_contains_coroutine(self):
        result = generate_aoe_vfx_script()
        assert "IEnumerator" in result["script_content"]

    def test_fade_out(self):
        result = generate_aoe_vfx_script()
        assert "isFading" in result["script_content"]

    def test_cleanup(self):
        result = generate_aoe_vfx_script()
        assert "Destroy(gameObject" in result["script_content"]


# ===========================================================================
# VFX3-05: Per-Brand Status Effect VFX
# ===========================================================================


class TestGenerateStatusEffectVFXScript:
    """Tests for generate_status_effect_vfx_script() -- VFX3-05."""

    def test_output_structure(self):
        result = generate_status_effect_vfx_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_status_effect_vfx_script()
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_status_effect_vfx_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_monobehaviour(self):
        result = generate_status_effect_vfx_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_all_10_brands(self):
        """Every brand must produce valid C# with balanced braces."""
        for brand_name in ALL_BRANDS:
            result = generate_status_effect_vfx_script(brand=brand_name)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), \
                f"Unbalanced braces for {brand_name}"
            assert brand_name in result["script_content"]

    def test_iron_grinding_sparks(self):
        result = generate_status_effect_vfx_script(brand="IRON")
        content = result["script_content"]
        assert "Reinforced" in content
        assert "grinding" in content.lower() or "sparks" in content.lower()

    def test_savage_blood_drip(self):
        result = generate_status_effect_vfx_script(brand="SAVAGE")
        content = result["script_content"]
        assert "Bleeding" in content
        assert "blood" in content.lower() or "drip" in content.lower()

    def test_surge_lightning_arcs(self):
        result = generate_status_effect_vfx_script(brand="SURGE")
        content = result["script_content"]
        assert "Shocked" in content
        assert "LineRenderer" in content

    def test_venom_toxic_cloud(self):
        result = generate_status_effect_vfx_script(brand="VENOM")
        content = result["script_content"]
        assert "Poisoned" in content

    def test_dread_shadow_tendrils(self):
        result = generate_status_effect_vfx_script(brand="DREAD")
        content = result["script_content"]
        assert "Terrified" in content

    def test_leech_blood_orbs(self):
        result = generate_status_effect_vfx_script(brand="LEECH")
        content = result["script_content"]
        assert "Draining" in content

    def test_grace_divine_rays(self):
        result = generate_status_effect_vfx_script(brand="GRACE")
        content = result["script_content"]
        assert "Blessed" in content

    def test_mend_healing_particles(self):
        result = generate_status_effect_vfx_script(brand="MEND")
        content = result["script_content"]
        assert "Regenerating" in content

    def test_ruin_ember_cracks(self):
        result = generate_status_effect_vfx_script(brand="RUIN")
        content = result["script_content"]
        assert "Crumbling" in content

    def test_void_gravity_distortion(self):
        result = generate_status_effect_vfx_script(brand="VOID")
        content = result["script_content"]
        assert "Nullified" in content

    def test_intensity_clamped(self):
        result_low = generate_status_effect_vfx_script(intensity=-0.5)
        result_high = generate_status_effect_vfx_script(intensity=5.0)
        assert "0.0f" in result_low["script_content"] or "0f" in result_low["script_content"]
        assert "1.0f" in result_high["script_content"] or "1f" in result_high["script_content"]

    def test_set_intensity_method(self):
        result = generate_status_effect_vfx_script()
        assert "SetIntensity" in result["script_content"]

    def test_material_property_block(self):
        result = generate_status_effect_vfx_script()
        assert "MaterialPropertyBlock" in result["script_content"]

    def test_emission_color(self):
        result = generate_status_effect_vfx_script()
        assert "_EmissionColor" in result["script_content"]

    def test_invalid_brand_fallback(self):
        result = generate_status_effect_vfx_script(brand="INVALID")
        assert "SURGE" in result["script_content"]

    def test_target_transform_path(self):
        result = generate_status_effect_vfx_script(target_transform_path="Spine/Chest")
        assert "Spine/Chest" in result["script_content"]

    def test_secondary_particle_system(self):
        result = generate_status_effect_vfx_script()
        assert "secondaryPS" in result["script_content"]

    def test_orbit_for_applicable_brands(self):
        # Brands with orbit > 0 should have orbit logic
        orbit_brands = [b for b, c in BRAND_STATUS_CONFIGS.items() if c["orbit_speed"] > 0]
        for brand_name in orbit_brands:
            result = generate_status_effect_vfx_script(brand=brand_name)
            assert "orbitSpeed" in result["script_content"]

    def test_on_destroy_cleanup(self):
        result = generate_status_effect_vfx_script()
        assert "OnDestroy" in result["script_content"]


# ===========================================================================
# VFX3-06: Environmental VFX Depth
# ===========================================================================


class TestGenerateEnvironmentalVFXScript:
    """Tests for generate_environmental_vfx_script() -- VFX3-06."""

    def test_output_structure(self):
        result = generate_environmental_vfx_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_environmental_vfx_script()
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_environmental_vfx_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_monobehaviour(self):
        result = generate_environmental_vfx_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_all_env_types(self):
        for vfx_type in ENV_VFX_TYPES:
            result = generate_environmental_vfx_script(vfx_type=vfx_type)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), \
                f"Unbalanced for {vfx_type}"

    def test_volumetric_fog(self):
        result = generate_environmental_vfx_script(vfx_type="volumetric_fog")
        content = result["script_content"]
        assert "density" in content.lower()
        assert "noiseSpeed" in content or "NoiseSpeed" in content
        assert "FogVolume" in content or "fogMesh" in content

    def test_god_rays(self):
        result = generate_environmental_vfx_script(vfx_type="god_rays")
        content = result["script_content"]
        assert "LineRenderer" in content
        assert "rayCount" in content or "RayCount" in content

    def test_heat_distortion(self):
        result = generate_environmental_vfx_script(vfx_type="heat_distortion")
        content = result["script_content"]
        assert "distortion" in content.lower()
        assert "turbulenceScale" in content

    def test_water_caustics(self):
        result = generate_environmental_vfx_script(vfx_type="water_caustics")
        content = result["script_content"]
        assert "caustic" in content.lower()
        assert "projector" in content.lower() or "Projector" in content

    def test_custom_intensity(self):
        result = generate_environmental_vfx_script(intensity=0.5)
        assert "0.5" in result["script_content"]

    def test_custom_color(self):
        result = generate_environmental_vfx_script(color=[0.8, 0.2, 0.1, 0.9])
        content = result["script_content"]
        assert "0.8f" in content
        assert "0.2f" in content

    def test_custom_area_size(self):
        result = generate_environmental_vfx_script(area_size=50.0)
        assert "50" in result["script_content"]

    def test_intensity_clamped(self):
        result = generate_environmental_vfx_script(intensity=5.0)
        assert "1" in result["script_content"]  # clamped to 1.0

    def test_invalid_type_fallback(self):
        result = generate_environmental_vfx_script(vfx_type="invalid")
        assert "volumetric_fog" in result["script_content"]

    def test_set_intensity_method(self):
        result = generate_environmental_vfx_script()
        assert "SetIntensity" in result["script_content"]

    def test_default_color_per_type(self):
        # Each type gets its own default color
        fog_result = generate_environmental_vfx_script(vfx_type="volumetric_fog")
        ray_result = generate_environmental_vfx_script(vfx_type="god_rays")
        assert fog_result["script_content"] != ray_result["script_content"]


# ===========================================================================
# VFX3-07: Directional Combat Hit VFX
# ===========================================================================


class TestGenerateDirectionalHitVFXScript:
    """Tests for generate_directional_hit_vfx_script() -- VFX3-07."""

    def test_output_structure(self):
        result = generate_directional_hit_vfx_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_directional_hit_vfx_script()
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_directional_hit_vfx_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_monobehaviour(self):
        result = generate_directional_hit_vfx_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_all_brands(self):
        for brand_name in ALL_BRANDS:
            result = generate_directional_hit_vfx_script(brand=brand_name)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), \
                f"Unbalanced for {brand_name}"
            assert brand_name in result["script_content"]

    def test_trigger_hit_method(self):
        result = generate_directional_hit_vfx_script()
        assert "TriggerHit" in result["script_content"]

    def test_hit_direction_parameter(self):
        result = generate_directional_hit_vfx_script()
        assert "hitDirection" in result["script_content"]

    def test_hit_rotation(self):
        result = generate_directional_hit_vfx_script()
        assert "LookRotation" in result["script_content"]

    def test_screen_effects_enabled(self):
        result = generate_directional_hit_vfx_script(screen_effect_enabled=True)
        content = result["script_content"]
        assert "ScreenFlash" in content or "screenEffect" in content.lower()

    def test_screen_effects_disabled(self):
        result = generate_directional_hit_vfx_script(screen_effect_enabled=False)
        content = result["script_content"]
        assert "TriggerScreenEffect" not in content

    def test_chromatic_aberration(self):
        result = generate_directional_hit_vfx_script(screen_effect_enabled=True)
        assert "ChromaticAberration" in result["script_content"]

    def test_splash_particles(self):
        result = generate_directional_hit_vfx_script()
        assert "Splash" in result["script_content"] or "splash" in result["script_content"]

    def test_burst_emission(self):
        result = generate_directional_hit_vfx_script()
        assert "Burst" in result["script_content"]

    def test_gravity_on_particles(self):
        result = generate_directional_hit_vfx_script()
        assert "gravityModifier" in result["script_content"]

    def test_custom_magnitude(self):
        result = generate_directional_hit_vfx_script(hit_magnitude=2.5)
        assert "2.5" in result["script_content"]

    def test_magnitude_clamped(self):
        result = generate_directional_hit_vfx_script(hit_magnitude=10.0)
        assert "3" in result["script_content"]

    def test_invalid_brand_fallback(self):
        result = generate_directional_hit_vfx_script(brand="INVALID")
        assert "IRON" in result["script_content"]

    def test_world_simulation_space(self):
        result = generate_directional_hit_vfx_script()
        assert "SimulationSpace.World" in result["script_content"]

    def test_auto_destroy_effect(self):
        result = generate_directional_hit_vfx_script()
        assert "Destroy(" in result["script_content"]


# ===========================================================================
# VFX3-08: Boss Phase Transition VFX
# ===========================================================================


class TestGenerateBossTransitionVFXScript:
    """Tests for generate_boss_transition_vfx_script() -- VFX3-08."""

    def test_output_structure(self):
        result = generate_boss_transition_vfx_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_boss_transition_vfx_script()
        _check_cs_path(result)

    def test_balanced_braces(self):
        result = generate_boss_transition_vfx_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_monobehaviour(self):
        result = generate_boss_transition_vfx_script()
        assert "MonoBehaviour" in result["script_content"]

    def test_all_transition_types(self):
        for trans_type in BOSS_TRANSITION_TYPES:
            result = generate_boss_transition_vfx_script(transition_type=trans_type)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), \
                f"Unbalanced for {trans_type}"

    def test_all_brands(self):
        for brand_name in ALL_BRANDS:
            result = generate_boss_transition_vfx_script(boss_brand=brand_name)
            _check_output_structure(result)
            assert _check_balanced_braces(result["script_content"]), \
                f"Unbalanced for {brand_name}"

    def test_corruption_wave(self):
        result = generate_boss_transition_vfx_script(transition_type="corruption_wave")
        content = result["script_content"]
        assert "CorruptionWave" in content or "corruption_wave" in content
        assert "arenaRadius" in content

    def test_power_surge(self):
        result = generate_boss_transition_vfx_script(transition_type="power_surge")
        content = result["script_content"]
        assert "PowerSurge" in content or "power_surge" in content
        assert "columnPS" in content

    def test_arena_transformation(self):
        result = generate_boss_transition_vfx_script(transition_type="arena_transformation")
        content = result["script_content"]
        assert "ArenaTransformation" in content or "arena_transformation" in content
        assert "fogColor" in content.lower() or "FogColor" in content or "RenderSettings" in content

    def test_trigger_transition_method(self):
        result = generate_boss_transition_vfx_script()
        assert "TriggerTransition" in result["script_content"]

    def test_phase_numbers(self):
        result = generate_boss_transition_vfx_script()
        content = result["script_content"]
        assert "currentPhase" in content
        assert "phase1Intensity" in content or "phase2Intensity" in content

    def test_event_callback(self):
        result = generate_boss_transition_vfx_script()
        assert "OnTransitionFinished" in result["script_content"]

    def test_screen_shake(self):
        result = generate_boss_transition_vfx_script()
        assert "ApplyScreenShake" in result["script_content"]

    def test_glow_application(self):
        result = generate_boss_transition_vfx_script()
        assert "ApplyGlow" in result["script_content"]
        assert "MaterialPropertyBlock" in result["script_content"]

    def test_custom_duration(self):
        result = generate_boss_transition_vfx_script(duration=5.0)
        assert "5" in result["script_content"]

    def test_custom_arena_radius(self):
        result = generate_boss_transition_vfx_script(arena_radius=30.0)
        assert "30" in result["script_content"]

    def test_invalid_transition_type_fallback(self):
        result = generate_boss_transition_vfx_script(transition_type="invalid")
        assert "corruption_wave" in result["script_content"]

    def test_invalid_brand_fallback(self):
        result = generate_boss_transition_vfx_script(boss_brand="INVALID")
        assert "DREAD" in result["script_content"]

    def test_three_phase_stages(self):
        result = generate_boss_transition_vfx_script()
        content = result["script_content"]
        # Should reference stage transitions
        assert "Stage 1" in content or "chargePS" in content
        assert "wavePS" in content
        assert "aftermathPS" in content

    def test_coroutine_based(self):
        result = generate_boss_transition_vfx_script()
        assert "IEnumerator" in result["script_content"]
        assert "StartCoroutine" in result["script_content"]

    def test_is_transitioning_flag(self):
        result = generate_boss_transition_vfx_script()
        assert "isTransitioning" in result["script_content"]


# ===========================================================================
# Cross-cutting tests
# ===========================================================================


class TestCrossCutting:
    """Cross-cutting tests across all generators."""

    def test_all_generators_return_dicts(self):
        generators = [
            generate_flipbook_script,
            generate_vfx_graph_composition_script,
            generate_projectile_vfx_chain_script,
            generate_aoe_vfx_script,
            generate_status_effect_vfx_script,
            generate_environmental_vfx_script,
            generate_directional_hit_vfx_script,
            generate_boss_transition_vfx_script,
        ]
        for gen in generators:
            result = gen()
            assert isinstance(result, dict), f"{gen.__name__} did not return dict"
            assert "script_path" in result
            assert "script_content" in result
            assert "next_steps" in result

    def test_all_generators_balanced_braces(self):
        generators = [
            generate_flipbook_script,
            generate_vfx_graph_composition_script,
            generate_projectile_vfx_chain_script,
            generate_aoe_vfx_script,
            generate_status_effect_vfx_script,
            generate_environmental_vfx_script,
            generate_directional_hit_vfx_script,
            generate_boss_transition_vfx_script,
        ]
        for gen in generators:
            result = gen()
            assert _check_balanced_braces(result["script_content"]), \
                f"{gen.__name__} has unbalanced braces"

    def test_all_generators_cs_paths(self):
        generators = [
            generate_flipbook_script,
            generate_vfx_graph_composition_script,
            generate_projectile_vfx_chain_script,
            generate_aoe_vfx_script,
            generate_status_effect_vfx_script,
            generate_environmental_vfx_script,
            generate_directional_hit_vfx_script,
            generate_boss_transition_vfx_script,
        ]
        for gen in generators:
            result = gen()
            assert result["script_path"].endswith(".cs"), \
                f"{gen.__name__} path does not end with .cs"

    def test_no_using_unityeditor_in_runtime_scripts(self):
        """Runtime MonoBehaviours should not import UnityEditor."""
        runtime_generators = [
            generate_projectile_vfx_chain_script,
            generate_aoe_vfx_script,
            generate_status_effect_vfx_script,
            generate_environmental_vfx_script,
            generate_directional_hit_vfx_script,
            generate_boss_transition_vfx_script,
        ]
        for gen in runtime_generators:
            result = gen()
            assert "using UnityEditor" not in result["script_content"], \
                f"{gen.__name__} imports UnityEditor in runtime script"

    def test_editor_scripts_import_unityeditor(self):
        """Editor tools should import UnityEditor."""
        editor_generators = [
            generate_flipbook_script,
            generate_vfx_graph_composition_script,
        ]
        for gen in editor_generators:
            result = gen()
            assert "using UnityEditor" in result["script_content"], \
                f"{gen.__name__} missing UnityEditor import"

    def test_all_brand_permutations_for_status_vfx(self):
        """Status VFX must work for all 10 brands."""
        for brand_name in ALL_BRANDS:
            result = generate_status_effect_vfx_script(brand=brand_name)
            _check_output_structure(result)
            content = result["script_content"]
            assert _check_balanced_braces(content), f"Braces for {brand_name}"
            # Each brand's effect name should appear
            expected_name = BRAND_STATUS_CONFIGS[brand_name]["effect_name"]
            assert expected_name in content, \
                f"Missing effect name {expected_name} for {brand_name}"

    def test_phase23_comment_present(self):
        """All generators should reference Phase 23 in comments."""
        generators = [
            generate_flipbook_script,
            generate_vfx_graph_composition_script,
            generate_projectile_vfx_chain_script,
            generate_aoe_vfx_script,
            generate_status_effect_vfx_script,
            generate_environmental_vfx_script,
            generate_directional_hit_vfx_script,
            generate_boss_transition_vfx_script,
        ]
        for gen in generators:
            result = gen()
            assert "Phase 23" in result["script_content"], \
                f"{gen.__name__} missing Phase 23 reference"

    def test_all_next_steps_nonempty(self):
        generators = [
            generate_flipbook_script,
            generate_vfx_graph_composition_script,
            generate_projectile_vfx_chain_script,
            generate_aoe_vfx_script,
            generate_status_effect_vfx_script,
            generate_environmental_vfx_script,
            generate_directional_hit_vfx_script,
            generate_boss_transition_vfx_script,
        ]
        for gen in generators:
            result = gen()
            assert len(result["next_steps"]) >= 2, \
                f"{gen.__name__} has too few next_steps"
