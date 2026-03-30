"""Status effect and crowd control VFX C# template generators for Unity.

Generates MonoBehaviours for per-effect status VFX (stun, root, burn, etc.)
and AoE crowd control VFX (mass_stun, earthquake, ice_storm, etc.).
All use ParticleSystem, PrimeTween for animations, C# events for state.

Exports:
    generate_status_effect_controller_script  -- Status effect VFX controller
    generate_crowd_control_vfx_script         -- AoE crowd control VFX controller
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Status effect configuration table
# ---------------------------------------------------------------------------

STATUS_EFFECTS: dict[str, dict[str, Any]] = {
    "stun": {
        "color": [1.0, 0.9, 0.2, 1.0],
        "glow": [1.0, 1.0, 0.5, 1.0],
        "rate": 40, "lifetime": 1.2, "size": 0.12,
        "shape": "circle", "shape_radius": 0.3,
        "gravity": -0.3, "speed": 0.8,
        "orbit": True, "orbit_speed": 180.0,
        "secondary_rate": 20, "secondary_size": 0.05,
        "secondary_color": [1.0, 1.0, 0.7, 0.6],
        "desc": "yellow stars orbiting head, daze sparkles",
        "offset_y": 1.8,
    },
    "root": {
        "color": [0.2, 0.6, 0.15, 1.0],
        "glow": [0.3, 0.8, 0.2, 1.0],
        "rate": 30, "lifetime": 2.0, "size": 0.08,
        "shape": "circle", "shape_radius": 0.5,
        "gravity": 0.1, "speed": 0.4,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 15, "secondary_size": 0.15,
        "secondary_color": [0.15, 0.45, 0.1, 0.8],
        "desc": "green vines from ground, anchor particles",
        "offset_y": 0.0,
    },
    "sleep": {
        "color": [0.3, 0.4, 0.9, 1.0],
        "glow": [0.5, 0.6, 1.0, 1.0],
        "rate": 8, "lifetime": 3.0, "size": 0.25,
        "shape": "sphere", "shape_radius": 0.2,
        "gravity": -0.5, "speed": 0.3,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 5, "secondary_size": 0.4,
        "secondary_color": [0.4, 0.5, 0.9, 0.3],
        "desc": "blue ZZZ particles floating up, dream clouds",
        "offset_y": 1.9,
    },
    "freeze": {
        "color": [0.6, 0.85, 1.0, 1.0],
        "glow": [0.8, 0.95, 1.0, 1.0],
        "rate": 60, "lifetime": 1.5, "size": 0.06,
        "shape": "sphere", "shape_radius": 0.6,
        "gravity": 0.2, "speed": 0.5,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 25, "secondary_size": 0.04,
        "secondary_color": [0.7, 0.9, 1.0, 0.5],
        "desc": "ice crystals, frost particles, blue tint",
        "offset_y": 0.9,
    },
    "burn": {
        "color": [1.0, 0.4, 0.05, 1.0],
        "glow": [1.0, 0.6, 0.1, 1.0],
        "rate": 80, "lifetime": 0.8, "size": 0.15,
        "shape": "sphere", "shape_radius": 0.4,
        "gravity": -0.6, "speed": 1.2,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 30, "secondary_size": 0.08,
        "secondary_color": [0.3, 0.3, 0.3, 0.6],
        "desc": "flames on body, smoke, ember shower",
        "offset_y": 0.5,
    },
    "bleed": {
        "color": [0.6, 0.02, 0.02, 1.0],
        "glow": [0.8, 0.1, 0.1, 1.0],
        "rate": 25, "lifetime": 1.5, "size": 0.06,
        "shape": "sphere", "shape_radius": 0.3,
        "gravity": 0.8, "speed": 0.6,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 10, "secondary_size": 0.04,
        "secondary_color": [0.4, 0.01, 0.01, 0.8],
        "desc": "red drip particles, blood trail",
        "offset_y": 0.8,
    },
    "poison": {
        "color": [0.2, 0.7, 0.1, 1.0],
        "glow": [0.3, 0.9, 0.2, 1.0],
        "rate": 20, "lifetime": 2.5, "size": 0.18,
        "shape": "sphere", "shape_radius": 0.5,
        "gravity": -0.2, "speed": 0.4,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 12, "secondary_size": 0.35,
        "secondary_color": [0.15, 0.5, 0.05, 0.25],
        "desc": "green bubbles, toxic cloud",
        "offset_y": 0.6,
    },
    "silence": {
        "color": [0.5, 0.15, 0.7, 1.0],
        "glow": [0.65, 0.3, 0.85, 1.0],
        "rate": 35, "lifetime": 1.8, "size": 0.07,
        "shape": "circle", "shape_radius": 0.4,
        "gravity": 0.0, "speed": 0.6,
        "orbit": True, "orbit_speed": 120.0,
        "secondary_rate": 18, "secondary_size": 0.04,
        "secondary_color": [0.6, 0.2, 0.8, 0.5],
        "desc": "purple seal ring, anti-magic sparks",
        "offset_y": 1.6,
    },
    "slow": {
        "color": [0.5, 0.5, 0.5, 0.7],
        "glow": [0.6, 0.6, 0.6, 0.5],
        "rate": 45, "lifetime": 0.6, "size": 0.1,
        "shape": "cone", "shape_radius": 0.3,
        "gravity": 0.0, "speed": 2.0,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 15, "secondary_size": 0.06,
        "secondary_color": [0.4, 0.4, 0.4, 0.4],
        "desc": "gray drag particles, movement resistance",
        "offset_y": 0.5,
    },
    "haste": {
        "color": [0.9, 0.95, 1.0, 0.6],
        "glow": [1.0, 1.0, 1.0, 0.8],
        "rate": 100, "lifetime": 0.3, "size": 0.04,
        "shape": "cone", "shape_radius": 0.2,
        "gravity": 0.0, "speed": 4.0,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 30, "secondary_size": 0.08,
        "secondary_color": [0.8, 0.9, 1.0, 0.3],
        "desc": "speed lines, afterimage trail",
        "offset_y": 0.5,
    },
    "shield": {
        "color": [0.3, 0.7, 1.0, 0.5],
        "glow": [0.5, 0.85, 1.0, 0.7],
        "rate": 50, "lifetime": 2.0, "size": 0.05,
        "shape": "sphere", "shape_radius": 0.8,
        "gravity": 0.0, "speed": 0.2,
        "orbit": True, "orbit_speed": 60.0,
        "secondary_rate": 10, "secondary_size": 0.15,
        "secondary_color": [0.4, 0.8, 1.0, 0.3],
        "desc": "hex barrier, absorption ripples",
        "offset_y": 0.9,
    },
    "fear": {
        "color": [0.15, 0.05, 0.2, 0.9],
        "glow": [0.3, 0.1, 0.4, 1.0],
        "rate": 35, "lifetime": 1.8, "size": 0.12,
        "shape": "sphere", "shape_radius": 0.4,
        "gravity": -0.3, "speed": 0.7,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 15, "secondary_size": 0.2,
        "secondary_color": [0.1, 0.02, 0.15, 0.4],
        "desc": "shadow fleeing particles, terror wisps",
        "offset_y": 1.2,
    },
    "taunt": {
        "color": [0.9, 0.15, 0.1, 1.0],
        "glow": [1.0, 0.3, 0.2, 1.0],
        "rate": 25, "lifetime": 1.0, "size": 0.2,
        "shape": "sphere", "shape_radius": 0.3,
        "gravity": -0.4, "speed": 0.5,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 12, "secondary_size": 0.15,
        "secondary_color": [1.0, 0.2, 0.15, 0.6],
        "desc": "red aggro marks, attention pulse",
        "offset_y": 2.0,
    },
    "charm": {
        "color": [1.0, 0.4, 0.6, 1.0],
        "glow": [1.0, 0.6, 0.75, 1.0],
        "rate": 15, "lifetime": 2.5, "size": 0.18,
        "shape": "sphere", "shape_radius": 0.4,
        "gravity": -0.3, "speed": 0.5,
        "orbit": False, "orbit_speed": 0.0,
        "secondary_rate": 20, "secondary_size": 0.06,
        "secondary_color": [1.0, 0.7, 0.8, 0.5],
        "desc": "pink hearts, enchant sparkles",
        "offset_y": 1.8,
    },
}

ALL_EFFECTS = list(STATUS_EFFECTS.keys())

# ---------------------------------------------------------------------------
# Crowd control AoE configuration table
# ---------------------------------------------------------------------------

CC_TYPES: dict[str, dict[str, Any]] = {
    "mass_stun": {
        "color": [1.0, 0.9, 0.2, 1.0],
        "glow": [1.0, 1.0, 0.5, 1.0],
        "ring_rate": 200, "ring_lifetime": 0.8, "ring_speed": 8.0,
        "pillar_rate": 60, "pillar_lifetime": 1.5,
        "ground_color": [1.0, 0.85, 0.3, 0.4],
        "desc": "expanding ring + light pillars",
    },
    "mass_fear": {
        "color": [0.15, 0.05, 0.25, 1.0],
        "glow": [0.3, 0.1, 0.45, 1.0],
        "ring_rate": 150, "ring_lifetime": 1.2, "ring_speed": 6.0,
        "pillar_rate": 40, "pillar_lifetime": 2.0,
        "ground_color": [0.1, 0.02, 0.15, 0.5],
        "desc": "dark shockwave + shadow tendrils",
    },
    "mass_root": {
        "color": [0.2, 0.6, 0.15, 1.0],
        "glow": [0.3, 0.8, 0.2, 1.0],
        "ring_rate": 100, "ring_lifetime": 0.5, "ring_speed": 10.0,
        "pillar_rate": 50, "pillar_lifetime": 2.5,
        "ground_color": [0.15, 0.4, 0.1, 0.6],
        "desc": "ground crack + vine eruption",
    },
    "knockback": {
        "color": [0.9, 0.85, 0.7, 1.0],
        "glow": [1.0, 0.95, 0.8, 1.0],
        "ring_rate": 300, "ring_lifetime": 0.4, "ring_speed": 15.0,
        "pillar_rate": 80, "pillar_lifetime": 0.6,
        "ground_color": [0.6, 0.55, 0.4, 0.3],
        "desc": "force ring + dust trail",
    },
    "gravity_well": {
        "color": [0.1, 0.05, 0.2, 1.0],
        "glow": [0.25, 0.15, 0.4, 1.0],
        "ring_rate": 120, "ring_lifetime": 2.0, "ring_speed": -5.0,
        "pillar_rate": 60, "pillar_lifetime": 3.0,
        "ground_color": [0.05, 0.02, 0.12, 0.7],
        "desc": "suction particles + dark sphere",
    },
    "earthquake": {
        "color": [0.55, 0.4, 0.2, 1.0],
        "glow": [0.7, 0.55, 0.3, 1.0],
        "ring_rate": 250, "ring_lifetime": 0.6, "ring_speed": 12.0,
        "pillar_rate": 100, "pillar_lifetime": 1.0,
        "ground_color": [0.4, 0.3, 0.15, 0.5],
        "desc": "ground cracks + flying debris",
    },
    "ice_storm": {
        "color": [0.6, 0.85, 1.0, 1.0],
        "glow": [0.8, 0.95, 1.0, 1.0],
        "ring_rate": 180, "ring_lifetime": 1.0, "ring_speed": 3.0,
        "pillar_rate": 70, "pillar_lifetime": 2.0,
        "ground_color": [0.5, 0.75, 0.9, 0.4],
        "desc": "hail + frost ground + ice spikes",
    },
    "fire_storm": {
        "color": [1.0, 0.4, 0.05, 1.0],
        "glow": [1.0, 0.6, 0.1, 1.0],
        "ring_rate": 200, "ring_lifetime": 0.8, "ring_speed": 5.0,
        "pillar_rate": 90, "pillar_lifetime": 1.5,
        "ground_color": [0.8, 0.3, 0.05, 0.5],
        "desc": "rain of fire + ground scorch",
    },
}

ALL_CC_TYPES = list(CC_TYPES.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt(v: float) -> str:
    """Format float for C# literal."""
    return f"{v}f"


def _fmt_color(rgba: list[float]) -> str:
    """Format RGBA list as C# Color constructor."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _effect_config_entry(name: str, cfg: dict[str, Any]) -> str:
    """Build a single C# dictionary entry for a status effect config."""
    c = cfg["color"]
    g = cfg["glow"]
    sc = cfg["secondary_color"]
    return (
        f'            {{ "{name}", new EffectConfig {{\n'
        f"                primaryColor = {_fmt_color(c)},\n"
        f"                glowColor = {_fmt_color(g)},\n"
        f"                emissionRate = {_fmt(cfg['rate'])},\n"
        f"                lifetime = {_fmt(cfg['lifetime'])},\n"
        f"                startSize = {_fmt(cfg['size'])},\n"
        f'                shapeType = "{cfg["shape"]}",\n'
        f"                shapeRadius = {_fmt(cfg['shape_radius'])},\n"
        f"                gravityModifier = {_fmt(cfg['gravity'])},\n"
        f"                startSpeed = {_fmt(cfg['speed'])},\n"
        f"                useOrbital = {str(cfg['orbit']).lower()},\n"
        f"                orbitalSpeed = {_fmt(cfg['orbit_speed'])},\n"
        f"                secondaryRate = {_fmt(cfg['secondary_rate'])},\n"
        f"                secondarySize = {_fmt(cfg['secondary_size'])},\n"
        f"                secondaryColor = {_fmt_color(sc)},\n"
        f"                offsetY = {_fmt(cfg['offset_y'])}\n"
        f"            }} }}"
    )


def _cc_config_entry(name: str, cfg: dict[str, Any]) -> str:
    """Build a single C# dictionary entry for a CC type config."""
    c = cfg["color"]
    g = cfg["glow"]
    gc = cfg["ground_color"]
    return (
        f'            {{ "{name}", new CCConfig {{\n'
        f"                primaryColor = {_fmt_color(c)},\n"
        f"                glowColor = {_fmt_color(g)},\n"
        f"                ringRate = {_fmt(cfg['ring_rate'])},\n"
        f"                ringLifetime = {_fmt(cfg['ring_lifetime'])},\n"
        f"                ringSpeed = {_fmt(cfg['ring_speed'])},\n"
        f"                pillarRate = {_fmt(cfg['pillar_rate'])},\n"
        f"                pillarLifetime = {_fmt(cfg['pillar_lifetime'])},\n"
        f"                groundColor = {_fmt_color(gc)}\n"
        f"            }} }}"
    )


# ---------------------------------------------------------------------------
# 1. Status Effect VFX Controller
# ---------------------------------------------------------------------------


def generate_status_effect_controller_script(
    effect_type: str = "stun",
) -> dict[str, Any]:
    """Generate StatusEffectVFXController MonoBehaviour.

    A single script that manages all 14 status effect types via a config
    dictionary. Each effect gets its own ParticleSystem pair (primary +
    secondary), configured via helper methods to avoid code duplication.

    API:
        ApplyEffect(string effectType, float duration)
        RemoveEffect(string effectType)
        Events: OnEffectApplied, OnEffectRemoved

    Args:
        effect_type: Default effect type for inspector preview.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    effect_type = effect_type.lower()
    if effect_type not in STATUS_EFFECTS:
        effect_type = "stun"
    sanitize_cs_identifier(effect_type)

    # Build config dictionary entries
    config_entries = ",\n".join(
        _effect_config_entry(name, cfg) for name, cfg in STATUS_EFFECTS.items()
    )

    # Build effect names list for inspector dropdown
    effect_names_cs = ", ".join(f'"{n}"' for n in ALL_EFFECTS)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using PrimeTween;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Status effect VFX controller for VeilBreakers.
/// Manages 14 status effect types via ParticleSystem pairs configured from
/// a data-driven config dictionary. Supports stacking, duration tracking,
/// and smooth fade-in/fade-out via PrimeTween.
/// </summary>
public class VB_StatusEffectVFXController : MonoBehaviour
{{
    // -----------------------------------------------------------------
    // Config data structure
    // -----------------------------------------------------------------

    [Serializable]
    public struct EffectConfig
    {{
        public Color primaryColor;
        public Color glowColor;
        public float emissionRate;
        public float lifetime;
        public float startSize;
        public string shapeType;
        public float shapeRadius;
        public float gravityModifier;
        public float startSpeed;
        public bool useOrbital;
        public float orbitalSpeed;
        public float secondaryRate;
        public float secondarySize;
        public Color secondaryColor;
        public float offsetY;
    }}

    // -----------------------------------------------------------------
    // Runtime effect instance
    // -----------------------------------------------------------------

    private class ActiveEffect
    {{
        public string effectType;
        public ParticleSystem primaryPS;
        public ParticleSystem secondaryPS;
        public GameObject root;
        public Coroutine durationCoroutine;
        public float remainingDuration;
    }}

    // -----------------------------------------------------------------
    // Inspector
    // -----------------------------------------------------------------

    [Header("Status Effect Settings")]
    [SerializeField] private string defaultEffect = "{effect_type}";
    [SerializeField] private float fadeInDuration = 0.3f;
    [SerializeField] private float fadeOutDuration = 0.5f;
    [SerializeField] private int maxConcurrentEffects = 5;

    // -----------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------

    public event Action<string, float> OnEffectApplied;
    public event Action<string> OnEffectRemoved;

    // -----------------------------------------------------------------
    // State
    // -----------------------------------------------------------------

    private readonly Dictionary<string, ActiveEffect> activeEffects = new Dictionary<string, ActiveEffect>();

    private static readonly Dictionary<string, EffectConfig> EffectConfigs = new Dictionary<string, EffectConfig>
    {{
{config_entries}
    }};

    // -----------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------

    /// <summary>Apply a status effect with duration. Refreshes if already active.</summary>
    public void ApplyEffect(string effectType, float duration)
    {{
        effectType = effectType.ToLower();
        if (!EffectConfigs.ContainsKey(effectType))
        {{
            Debug.LogWarning($"[StatusEffectVFX] Unknown effect type: {{effectType}}");
            return;
        }}

        if (activeEffects.ContainsKey(effectType))
        {{
            RefreshEffect(effectType, duration);
            return;
        }}

        if (activeEffects.Count >= maxConcurrentEffects)
        {{
            Debug.LogWarning("[StatusEffectVFX] Max concurrent effects reached.");
            return;
        }}

        var config = EffectConfigs[effectType];
        var effect = CreateEffect(effectType, config);
        effect.remainingDuration = duration;
        activeEffects[effectType] = effect;

        // Fade in emission
        FadeEmission(effect.primaryPS, 0f, config.emissionRate, fadeInDuration);
        FadeEmission(effect.secondaryPS, 0f, config.secondaryRate, fadeInDuration);

        // Start duration countdown
        effect.durationCoroutine = StartCoroutine(EffectDurationRoutine(effectType, duration));

        OnEffectApplied?.Invoke(effectType, duration);
    }}

    /// <summary>Remove a status effect immediately with fade-out.</summary>
    public void RemoveEffect(string effectType)
    {{
        effectType = effectType.ToLower();
        if (!activeEffects.TryGetValue(effectType, out var effect)) return;

        if (effect.durationCoroutine != null)
            StopCoroutine(effect.durationCoroutine);

        StartCoroutine(FadeOutAndDestroy(effect));
        activeEffects.Remove(effectType);
        OnEffectRemoved?.Invoke(effectType);
    }}

    /// <summary>Check if an effect is currently active.</summary>
    public bool IsEffectActive(string effectType) => activeEffects.ContainsKey(effectType.ToLower());

    /// <summary>Get remaining duration for an active effect. Returns 0 if not active.</summary>
    public float GetRemainingDuration(string effectType)
    {{
        effectType = effectType.ToLower();
        return activeEffects.TryGetValue(effectType, out var e) ? e.remainingDuration : 0f;
    }}

    /// <summary>Remove all active effects.</summary>
    public void RemoveAllEffects()
    {{
        var keys = new List<string>(activeEffects.Keys);
        foreach (var key in keys)
            RemoveEffect(key);
    }}

    // -----------------------------------------------------------------
    // Effect lifecycle
    // -----------------------------------------------------------------

    private void RefreshEffect(string effectType, float duration)
    {{
        var effect = activeEffects[effectType];
        if (effect.durationCoroutine != null)
            StopCoroutine(effect.durationCoroutine);
        effect.remainingDuration = duration;
        effect.durationCoroutine = StartCoroutine(EffectDurationRoutine(effectType, duration));
        OnEffectApplied?.Invoke(effectType, duration);
    }}

    private IEnumerator EffectDurationRoutine(string effectType, float duration)
    {{
        float elapsed = 0f;
        while (elapsed < duration)
        {{
            elapsed += Time.deltaTime;
            if (activeEffects.TryGetValue(effectType, out var e))
                e.remainingDuration = duration - elapsed;
            yield return null;
        }}
        RemoveEffect(effectType);
    }}

    private IEnumerator FadeOutAndDestroy(ActiveEffect effect)
    {{
        FadeEmission(effect.primaryPS, GetCurrentRate(effect.primaryPS), 0f, fadeOutDuration);
        FadeEmission(effect.secondaryPS, GetCurrentRate(effect.secondaryPS), 0f, fadeOutDuration);
        yield return new WaitForSeconds(fadeOutDuration + effect.primaryPS.main.startLifetime.constantMax);
        if (effect.root != null)
            Destroy(effect.root);
    }}

    // -----------------------------------------------------------------
    // ParticleSystem creation (shared helper)
    // -----------------------------------------------------------------

    private ActiveEffect CreateEffect(string effectType, EffectConfig config)
    {{
        // Root container parented to this transform
        var root = new GameObject($"StatusFX_{{effectType}}");
        root.transform.SetParent(transform, false);
        root.transform.localPosition = new Vector3(0f, config.offsetY, 0f);

        // Primary particle system
        var primaryPS = CreateParticleSystem(root.transform, $"{{effectType}}_primary", config, true);

        // Secondary particle system (accents)
        var secondaryPS = CreateParticleSystem(root.transform, $"{{effectType}}_secondary", config, false);

        return new ActiveEffect
        {{
            effectType = effectType,
            primaryPS = primaryPS,
            secondaryPS = secondaryPS,
            root = root,
        }};
    }}

    private ParticleSystem CreateParticleSystem(Transform parent, string psName, EffectConfig config, bool isPrimary)
    {{
        var go = new GameObject(psName);
        go.transform.SetParent(parent, false);
        var ps = go.AddComponent<ParticleSystem>();

        // Main module
        var main = ps.main;
        main.playOnAwake = true;
        main.loop = true;
        main.simulationSpace = ParticleSystemSimulationSpace.Local;
        main.startLifetime = isPrimary ? config.lifetime : config.lifetime * 0.7f;
        main.startSpeed = isPrimary ? config.startSpeed : config.startSpeed * 0.5f;
        main.startSize = isPrimary ? config.startSize : config.secondarySize;
        main.startColor = isPrimary ? config.primaryColor : config.secondaryColor;
        main.gravityModifier = config.gravityModifier;
        main.maxParticles = isPrimary ? 200 : 100;

        // Emission
        var emission = ps.emission;
        emission.rateOverTime = isPrimary ? config.emissionRate : config.secondaryRate;

        // Shape
        var shape = ps.shape;
        shape.enabled = true;
        ConfigureShape(shape, config.shapeType, config.shapeRadius, isPrimary);

        // Orbital velocity (for stun stars, silence rings, shield hex)
        if (config.useOrbital && isPrimary)
        {{
            var velocity = ps.velocityOverLifetime;
            velocity.enabled = true;
            velocity.orbitalY = config.orbitalSpeed * Mathf.Deg2Rad;
            velocity.radial = -0.5f; // slight inward pull
        }}

        // Size over lifetime (fade out)
        var sol = ps.sizeOverLifetime;
        sol.enabled = true;
        sol.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        // Color over lifetime (fade alpha)
        var col = ps.colorOverLifetime;
        col.enabled = true;
        var gradient = new Gradient();
        gradient.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) }},
            new GradientAlphaKey[] {{ new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.1f), new GradientAlphaKey(1f, 0.7f), new GradientAlphaKey(0f, 1f) }}
        );
        col.color = gradient;

        // Renderer (additive)
        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
        SetupAdditiveMaterial(renderer, isPrimary ? config.glowColor : config.secondaryColor);

        ps.Play();
        return ps;
    }}

    private void ConfigureShape(ParticleSystem.ShapeModule shape, string shapeType, float radius, bool isPrimary)
    {{
        switch (shapeType)
        {{
            case "sphere":
                shape.shapeType = ParticleSystemShapeType.Sphere;
                shape.radius = radius;
                break;
            case "circle":
                shape.shapeType = ParticleSystemShapeType.Circle;
                shape.radius = radius;
                shape.arc = 360f;
                break;
            case "cone":
                shape.shapeType = ParticleSystemShapeType.Cone;
                shape.radius = radius;
                shape.angle = isPrimary ? 15f : 25f;
                break;
            default:
                shape.shapeType = ParticleSystemShapeType.Sphere;
                shape.radius = radius;
                break;
        }}
    }}

    private void SetupAdditiveMaterial(ParticleSystemRenderer renderer, Color glowColor)
    {{
        var mat = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        mat.SetFloat("_Surface", 1f); // transparent
        mat.SetFloat("_Blend", 1f); // additive
        mat.SetColor("_BaseColor", Color.white);
        mat.SetColor("_EmissionColor", glowColor * 2f);
        mat.EnableKeyword("_EMISSION");
        mat.renderQueue = 3100;
        renderer.material = mat;
    }}

    // -----------------------------------------------------------------
    // Emission fade helpers
    // -----------------------------------------------------------------

    private void FadeEmission(ParticleSystem ps, float from, float to, float duration)
    {{
        if (ps == null) return;
        Tween.Custom(from, to, duration, val =>
        {{
            if (ps != null)
            {{
                var emission = ps.emission;
                emission.rateOverTime = val;
            }}
        }});
    }}

    private float GetCurrentRate(ParticleSystem ps)
    {{
        if (ps == null) return 0f;
        return ps.emission.rateOverTime.constantMax;
    }}

    // -----------------------------------------------------------------
    // Cleanup
    // -----------------------------------------------------------------

    private void OnDestroy()
    {{
        StopAllCoroutines();
        foreach (var kvp in activeEffects)
        {{
            if (kvp.Value.root != null)
                Destroy(kvp.Value.root);
        }}
        activeEffects.Clear();
    }}

    // -----------------------------------------------------------------
    // Editor menu item
    // -----------------------------------------------------------------

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Setup Status Effect VFX Controller")]
    private static void SetupFromMenu()
    {{
        var target = Selection.activeGameObject;
        if (target == null)
        {{
            target = new GameObject("StatusEffectVFX_Target");
            Undo.RegisterCreatedObjectUndo(target, "Create Status Effect VFX Target");
        }}

        var controller = target.GetComponent<VB_StatusEffectVFXController>();
        if (controller == null)
            controller = Undo.AddComponent<VB_StatusEffectVFXController>(target);

        // Preview default effect
        controller.ApplyEffect("{effect_type}", 999f);

        // Write result
        var result = new Dictionary<string, object>
        {{
            {{ "status", "ok" }},
            {{ "gameObject", target.name }},
            {{ "effects_available", new string[] {{ {effect_names_cs} }} }},
            {{ "preview_effect", "{effect_type}" }},
        }};
        File.WriteAllText("Temp/vb_result.json", JsonUtility.ToJson(new VBResultWrapper {{ json = Newtonsoft.Json.JsonConvert.SerializeObject(result) }}));
        Debug.Log("[VB] Status Effect VFX Controller attached with preview: {effect_type}");
    }}

    [Serializable]
    private class VBResultWrapper {{ public string json; }}
#endif
}}
'''

    return {
        "script_path": "Assets/Editor/Generated/VFX/VB_StatusEffectVFXController.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Use menu: VeilBreakers > VFX > Setup Status Effect VFX Controller",
            "Select a GameObject first, or a new one will be created",
            f"Preview starts with '{effect_type}' effect",
            "Call ApplyEffect(effectType, duration) to apply any of the 14 effects",
            "Call RemoveEffect(effectType) to remove, or RemoveAllEffects() to clear",
            "Wire OnEffectApplied / OnEffectRemoved events to UI or game systems",
        ],
    }


# ---------------------------------------------------------------------------
# 2. Crowd Control VFX Controller
# ---------------------------------------------------------------------------


def generate_crowd_control_vfx_script(
    cc_type: str = "mass_stun",
) -> dict[str, Any]:
    """Generate CrowdControlVFXController MonoBehaviour for AoE CC effects.

    A single script that manages 8 AoE crowd control VFX types via a config
    dictionary. Each CC trigger creates a ring expansion + vertical pillar
    effect + ground decal, configured per type. Uses PrimeTween for radius
    animation and intensity ramping.

    API:
        TriggerCC(string ccType, Vector3 center, float radius, float duration)
        Event: OnCCTriggered

    Args:
        cc_type: Default CC type for inspector preview.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    cc_type = cc_type.lower()
    if cc_type not in CC_TYPES:
        cc_type = "mass_stun"
    sanitize_cs_identifier(cc_type)

    # Build CC config dictionary entries
    cc_config_entries = ",\n".join(
        _cc_config_entry(name, cfg) for name, cfg in CC_TYPES.items()
    )

    cc_names_cs = ", ".join(f'"{n}"' for n in ALL_CC_TYPES)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using PrimeTween;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Crowd control AoE VFX controller for VeilBreakers.
/// Manages 8 AoE CC types via a config dictionary. Each trigger spawns
/// a ring expansion, vertical pillars, and ground decal. Uses PrimeTween
/// for smooth radius animation and intensity ramping.
/// </summary>
public class VB_CrowdControlVFXController : MonoBehaviour
{{
    // -----------------------------------------------------------------
    // Config data structure
    // -----------------------------------------------------------------

    [Serializable]
    public struct CCConfig
    {{
        public Color primaryColor;
        public Color glowColor;
        public float ringRate;
        public float ringLifetime;
        public float ringSpeed;
        public float pillarRate;
        public float pillarLifetime;
        public Color groundColor;
    }}

    // -----------------------------------------------------------------
    // Runtime CC instance
    // -----------------------------------------------------------------

    private class ActiveCC
    {{
        public string ccType;
        public GameObject root;
        public ParticleSystem ringPS;
        public ParticleSystem pillarPS;
        public ParticleSystem groundPS;
        public float radius;
        public float duration;
        public float elapsed;
    }}

    // -----------------------------------------------------------------
    // Inspector
    // -----------------------------------------------------------------

    [Header("Crowd Control Settings")]
    [SerializeField] private string defaultCCType = "{cc_type}";
    [SerializeField] private float defaultRadius = 8f;
    [SerializeField] private float defaultDuration = 2f;
    [SerializeField] private int maxConcurrentCC = 3;
    [SerializeField] private float groundDecalFadeDuration = 1.5f;

    // -----------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------

    public event Action<string, Vector3, float, float> OnCCTriggered;

    // -----------------------------------------------------------------
    // State
    // -----------------------------------------------------------------

    private readonly List<ActiveCC> activeCCs = new List<ActiveCC>();

    private static readonly Dictionary<string, CCConfig> CCConfigs = new Dictionary<string, CCConfig>
    {{
{cc_config_entries}
    }};

    // -----------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------

    /// <summary>Trigger a crowd control AoE VFX at a world position.</summary>
    public void TriggerCC(string ccType, Vector3 center, float radius, float duration)
    {{
        ccType = ccType.ToLower();
        if (!CCConfigs.ContainsKey(ccType))
        {{
            Debug.LogWarning($"[CrowdControlVFX] Unknown CC type: {{ccType}}");
            return;
        }}

        if (activeCCs.Count >= maxConcurrentCC)
        {{
            // Remove oldest
            CleanupCC(activeCCs[0]);
            activeCCs.RemoveAt(0);
        }}

        var config = CCConfigs[ccType];
        var cc = CreateCC(ccType, config, center, radius, duration);
        activeCCs.Add(cc);

        // Animate ring expansion via PrimeTween
        AnimateRingExpansion(cc, config, radius, duration);

        // Start lifecycle coroutine
        StartCoroutine(CCLifecycle(cc, duration));

        OnCCTriggered?.Invoke(ccType, center, radius, duration);
    }}

    /// <summary>Cancel all active CC effects.</summary>
    public void CancelAllCC()
    {{
        foreach (var cc in activeCCs)
            CleanupCC(cc);
        activeCCs.Clear();
    }}

    // -----------------------------------------------------------------
    // CC creation (shared helper)
    // -----------------------------------------------------------------

    private ActiveCC CreateCC(string ccType, CCConfig config, Vector3 center, float radius, float duration)
    {{
        var root = new GameObject($"CC_{{ccType}}_{{Time.frameCount}}");
        root.transform.position = center;

        // 1. Ring expansion particles
        var ringPS = CreateRingParticleSystem(root.transform, config, radius);

        // 2. Vertical pillar particles
        var pillarPS = CreatePillarParticleSystem(root.transform, config, radius);

        // 3. Ground decal particles
        var groundPS = CreateGroundParticleSystem(root.transform, config, radius);

        return new ActiveCC
        {{
            ccType = ccType,
            root = root,
            ringPS = ringPS,
            pillarPS = pillarPS,
            groundPS = groundPS,
            radius = radius,
            duration = duration,
            elapsed = 0f,
        }};
    }}

    private ParticleSystem CreateRingParticleSystem(Transform parent, CCConfig config, float radius)
    {{
        var go = new GameObject("Ring");
        go.transform.SetParent(parent, false);
        var ps = go.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.playOnAwake = true;
        main.loop = false;
        main.duration = 2f;
        main.startLifetime = config.ringLifetime;
        main.startSpeed = Mathf.Abs(config.ringSpeed);
        main.startSize = new ParticleSystem.MinMaxCurve(0.1f, 0.25f);
        main.startColor = config.primaryColor;
        main.gravityModifier = 0f;
        main.maxParticles = 500;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        // Emission burst
        var emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new ParticleSystem.Burst[]
        {{
            new ParticleSystem.Burst(0f, (short)config.ringRate, (short)config.ringRate, 1, 0.01f)
        }});

        // Shape: ring
        var shape = ps.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = 0.5f; // starts small, expands via animation
        shape.arc = 360f;
        shape.radiusThickness = 1f;

        // Velocity: invert for gravity well
        if (config.ringSpeed < 0f)
        {{
            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.radial = config.ringSpeed;
        }}

        // Size over lifetime
        var sol = ps.sizeOverLifetime;
        sol.enabled = true;
        sol.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.5f, 1f, 1.5f));

        // Color fade
        SetupAlphaFade(ps);

        // Additive renderer
        SetupRenderer(ps, config.glowColor);

        ps.Play();
        return ps;
    }}

    private ParticleSystem CreatePillarParticleSystem(Transform parent, CCConfig config, float radius)
    {{
        var go = new GameObject("Pillars");
        go.transform.SetParent(parent, false);
        var ps = go.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.playOnAwake = true;
        main.loop = false;
        main.duration = 2f;
        main.startLifetime = config.pillarLifetime;
        main.startSpeed = new ParticleSystem.MinMaxCurve(3f, 6f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.15f);
        main.startColor = config.glowColor;
        main.gravityModifier = -0.5f; // upward
        main.maxParticles = 300;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        // Emission: delayed burst for pillars rising
        var emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new ParticleSystem.Burst[]
        {{
            new ParticleSystem.Burst(0.15f, (short)(config.pillarRate / 2), (short)config.pillarRate, 3, 0.1f)
        }});

        // Shape: circle at radius edge for pillar locations
        var shape = ps.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = radius * 0.8f;
        shape.arc = 360f;
        shape.radiusThickness = 0f; // emit from edge only

        // Stretch towards sky
        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.renderMode = ParticleSystemRenderMode.Stretch;
        renderer.velocityScale = 0.3f;
        renderer.lengthScale = 2f;

        SetupAlphaFade(ps);
        SetupRenderer(ps, config.glowColor, true);

        ps.Play();
        return ps;
    }}

    private ParticleSystem CreateGroundParticleSystem(Transform parent, CCConfig config, float radius)
    {{
        var go = new GameObject("Ground");
        go.transform.SetParent(parent, false);
        go.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
        var ps = go.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.playOnAwake = true;
        main.loop = false;
        main.duration = 1f;
        main.startLifetime = 3f;
        main.startSpeed = 0f;
        main.startSize = radius * 2f;
        main.startColor = config.groundColor;
        main.gravityModifier = 0f;
        main.maxParticles = 5;
        main.simulationSpace = ParticleSystemSimulationSpace.Local;

        // Single burst for ground decal
        var emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new ParticleSystem.Burst[]
        {{
            new ParticleSystem.Burst(0f, 1, 1, 1, 0f)
        }});

        // Shape: flat circle
        var shape = ps.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = 0.01f;

        // Alpha fade for ground decal
        var col = ps.colorOverLifetime;
        col.enabled = true;
        var gradient = new Gradient();
        gradient.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) }},
            new GradientAlphaKey[] {{ new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.6f, 0.1f), new GradientAlphaKey(0.6f, 0.5f), new GradientAlphaKey(0f, 1f) }}
        );
        col.color = gradient;

        // Renderer: horizontal billboard
        SetupRenderer(ps, config.groundColor);
        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.renderMode = ParticleSystemRenderMode.HorizontalBillboard;

        ps.Play();
        return ps;
    }}

    // -----------------------------------------------------------------
    // Shared helpers
    // -----------------------------------------------------------------

    private void SetupAlphaFade(ParticleSystem ps)
    {{
        var col = ps.colorOverLifetime;
        col.enabled = true;
        var gradient = new Gradient();
        gradient.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) }},
            new GradientAlphaKey[] {{ new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.1f), new GradientAlphaKey(0.8f, 0.6f), new GradientAlphaKey(0f, 1f) }}
        );
        col.color = gradient;
    }}

    private void SetupRenderer(ParticleSystem ps, Color glowColor, bool keepExisting = false)
    {{
        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        if (!keepExisting)
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
        var mat = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        mat.SetFloat("_Surface", 1f);
        mat.SetFloat("_Blend", 1f); // additive
        mat.SetColor("_BaseColor", Color.white);
        mat.SetColor("_EmissionColor", glowColor * 2.5f);
        mat.EnableKeyword("_EMISSION");
        mat.renderQueue = 3100;
        renderer.material = mat;
    }}

    // -----------------------------------------------------------------
    // Ring expansion animation
    // -----------------------------------------------------------------

    private void AnimateRingExpansion(ActiveCC cc, CCConfig config, float targetRadius, float duration)
    {{
        float expandDuration = Mathf.Min(duration * 0.4f, 0.8f);

        // Animate ring shape radius from 0 to target
        Tween.Custom(0.5f, targetRadius, expandDuration, val =>
        {{
            if (cc.ringPS != null)
            {{
                var shape = cc.ringPS.shape;
                shape.radius = val;
            }}
        }}, Ease.OutQuad);

        // Animate pillar circle radius to match
        Tween.Custom(0f, targetRadius * 0.8f, expandDuration * 0.8f, val =>
        {{
            if (cc.pillarPS != null)
            {{
                var shape = cc.pillarPS.shape;
                shape.radius = val;
            }}
        }}, Ease.OutCubic);

        // Camera shake via impulse source if available
        TriggerScreenShake(config, targetRadius);
    }}

    private void TriggerScreenShake(CCConfig config, float radius)
    {{
        // Reflection-based Cinemachine impulse (null-safe)
        var impulseType = System.Type.GetType("Cinemachine.CinemachineImpulseSource, Unity.Cinemachine");
        if (impulseType == null) return;

        var impulse = FindAnyObjectByType(impulseType) as Component;
        if (impulse == null) return;

        var method = impulseType.GetMethod("GenerateImpulse", new System.Type[] {{ typeof(float) }});
        method?.Invoke(impulse, new object[] {{ radius * 0.1f }});
    }}

    // -----------------------------------------------------------------
    // CC lifecycle
    // -----------------------------------------------------------------

    private IEnumerator CCLifecycle(ActiveCC cc, float duration)
    {{
        cc.elapsed = 0f;
        while (cc.elapsed < duration)
        {{
            cc.elapsed += Time.deltaTime;
            yield return null;
        }}

        // Fade out ground decal
        if (cc.groundPS != null)
        {{
            var groundEmission = cc.groundPS.emission;
            groundEmission.rateOverTime = 0f;
            cc.groundPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }}

        yield return new WaitForSeconds(groundDecalFadeDuration);
        CleanupCC(cc);
        activeCCs.Remove(cc);
    }}

    private void CleanupCC(ActiveCC cc)
    {{
        if (cc.root != null)
            Destroy(cc.root);
    }}

    private void OnDestroy()
    {{
        StopAllCoroutines();
        foreach (var cc in activeCCs)
            CleanupCC(cc);
        activeCCs.Clear();
    }}

    // -----------------------------------------------------------------
    // Editor menu item
    // -----------------------------------------------------------------

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Setup Crowd Control VFX Controller")]
    private static void SetupFromMenu()
    {{
        var target = Selection.activeGameObject;
        if (target == null)
        {{
            target = new GameObject("CrowdControlVFX_Target");
            Undo.RegisterCreatedObjectUndo(target, "Create Crowd Control VFX Target");
        }}

        var controller = target.GetComponent<VB_CrowdControlVFXController>();
        if (controller == null)
            controller = Undo.AddComponent<VB_CrowdControlVFXController>(target);

        // Preview default CC at object position
        controller.TriggerCC("{cc_type}", target.transform.position, 8f, 3f);

        var result = new Dictionary<string, object>
        {{
            {{ "status", "ok" }},
            {{ "gameObject", target.name }},
            {{ "cc_types_available", new string[] {{ {cc_names_cs} }} }},
            {{ "preview_cc", "{cc_type}" }},
        }};
        File.WriteAllText("Temp/vb_result.json", JsonUtility.ToJson(new VBResultWrapper {{ json = Newtonsoft.Json.JsonConvert.SerializeObject(result) }}));
        Debug.Log("[VB] Crowd Control VFX Controller attached with preview: {cc_type}");
    }}

    [Serializable]
    private class VBResultWrapper {{ public string json; }}
#endif
}}
'''

    return {
        "script_path": "Assets/Editor/Generated/VFX/VB_CrowdControlVFXController.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Use menu: VeilBreakers > VFX > Setup Crowd Control VFX Controller",
            "Select a GameObject first, or a new one will be created",
            f"Preview starts with '{cc_type}' AoE at radius 8",
            "Call TriggerCC(ccType, center, radius, duration) from combat system",
            "Wire OnCCTriggered event to UI or game systems",
        ],
    }
