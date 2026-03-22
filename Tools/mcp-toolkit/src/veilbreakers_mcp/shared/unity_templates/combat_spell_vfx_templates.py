"""Combat spell, melee, and monster ability VFX C# template generators.

Generates ParticleSystem-based VFX controllers for:
  - Spell casting (fireball, ice_shard, lightning_bolt, etc.)
  - Melee combat (weapon trail, impact sparks, cleave arc, etc.)
  - Monster abilities (breath weapon, charge, ground pound, etc.)

Uses PrimeTween for animation, C# events for callbacks, Unity 2022.3+ URP.

Exports:
    generate_spell_vfx_script          -- SpellVFXController MonoBehaviour
    generate_melee_combat_vfx_script   -- MeleeCombatVFXController MonoBehaviour
    generate_monster_ability_vfx_script -- MonsterAbilityVFXController MonoBehaviour
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

# Brand palette -- canonical RGBA colors for all 10 VeilBreakers brands.
# Defined inline because vfx_templates only exports BRAND_VFX_CONFIGS (not
# separate primary/glow dicts).  Matches the values used in vfx_mastery_templates.
BRAND_PRIMARY_COLORS: dict[str, list[float]] = {
    "IRON": [0.55, 0.59, 0.65, 1.0], "SAVAGE": [0.71, 0.18, 0.18, 1.0],
    "SURGE": [0.24, 0.55, 0.86, 1.0], "VENOM": [0.31, 0.71, 0.24, 1.0],
    "DREAD": [0.47, 0.24, 0.63, 1.0], "LEECH": [0.55, 0.16, 0.31, 1.0],
    "GRACE": [0.86, 0.86, 0.94, 1.0], "MEND": [0.78, 0.67, 0.31, 1.0],
    "RUIN": [0.86, 0.47, 0.16, 1.0], "VOID": [0.16, 0.08, 0.24, 1.0],
}
BRAND_GLOW_COLORS: dict[str, list[float]] = {
    "IRON": [0.71, 0.75, 0.80, 1.0], "SAVAGE": [0.86, 0.27, 0.27, 1.0],
    "SURGE": [0.39, 0.71, 1.00, 1.0], "VENOM": [0.47, 0.86, 0.39, 1.0],
    "DREAD": [0.63, 0.39, 0.78, 1.0], "LEECH": [0.71, 0.24, 0.43, 1.0],
    "GRACE": [1.00, 1.00, 1.00, 1.0], "MEND": [0.94, 0.82, 0.47, 1.0],
    "RUIN": [1.00, 0.63, 0.31, 1.0], "VOID": [0.39, 0.24, 0.55, 1.0],
}

ALL_BRANDS = list(BRAND_PRIMARY_COLORS.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]


# ---------------------------------------------------------------------------
# Spell config data
# ---------------------------------------------------------------------------

SPELL_CONFIGS: dict[str, dict[str, Any]] = {
    "fireball": {
        "color": [1.0, 0.45, 0.1, 1.0],
        "glow": [1.0, 0.7, 0.2, 1.0],
        "rate": 300, "lifetime": 0.8, "size": 0.4, "speed": 18.0,
        "impact_radius": 3.0, "linger_time": 2.0,
        "desc": "Blazing fireball with flame trail and explosion impact",
    },
    "ice_shard": {
        "color": [0.4, 0.75, 1.0, 1.0],
        "glow": [0.7, 0.9, 1.0, 1.0],
        "rate": 200, "lifetime": 0.6, "size": 0.25, "speed": 22.0,
        "impact_radius": 2.0, "linger_time": 3.0,
        "desc": "Crystal ice projectile with frost trail and shatter",
    },
    "lightning_bolt": {
        "color": [0.6, 0.85, 1.0, 1.0],
        "glow": [1.0, 1.0, 1.0, 1.0],
        "rate": 500, "lifetime": 0.15, "size": 0.1, "speed": 50.0,
        "impact_radius": 1.5, "linger_time": 0.5,
        "desc": "Electric arc from sky with ground scorch",
    },
    "shadow_bolt": {
        "color": [0.25, 0.1, 0.35, 1.0],
        "glow": [0.5, 0.2, 0.7, 1.0],
        "rate": 150, "lifetime": 1.0, "size": 0.35, "speed": 15.0,
        "impact_radius": 2.5, "linger_time": 2.5,
        "desc": "Dark void projectile with shadow trail",
    },
    "holy_smite": {
        "color": [1.0, 0.95, 0.7, 1.0],
        "glow": [1.0, 1.0, 1.0, 1.0],
        "rate": 400, "lifetime": 0.5, "size": 0.6, "speed": 40.0,
        "impact_radius": 3.5, "linger_time": 1.5,
        "desc": "Golden beam from above with radiant burst",
    },
    "poison_cloud": {
        "color": [0.3, 0.7, 0.15, 1.0],
        "glow": [0.5, 0.9, 0.3, 1.0],
        "rate": 80, "lifetime": 4.0, "size": 1.2, "speed": 2.0,
        "impact_radius": 5.0, "linger_time": 6.0,
        "desc": "Expanding toxic cloud with lingering poison fog",
    },
    "earth_spike": {
        "color": [0.55, 0.4, 0.25, 1.0],
        "glow": [0.7, 0.55, 0.35, 1.0],
        "rate": 250, "lifetime": 0.7, "size": 0.3, "speed": 25.0,
        "impact_radius": 2.0, "linger_time": 1.0,
        "desc": "Ground eruption with rock debris shower",
    },
    "arcane_missile": {
        "color": [0.6, 0.3, 1.0, 1.0],
        "glow": [0.8, 0.5, 1.0, 1.0],
        "rate": 350, "lifetime": 0.5, "size": 0.2, "speed": 20.0,
        "impact_radius": 1.5, "linger_time": 1.0,
        "desc": "Homing arcane orbs with magic trail",
    },
}

# ---------------------------------------------------------------------------
# Melee VFX config data
# ---------------------------------------------------------------------------

MELEE_CONFIGS: dict[str, dict[str, Any]] = {
    "weapon_trail": {"desc": "Trail per weapon type", "duration": 0.3},
    "impact_sparks": {"desc": "Directional metal sparks", "rate": 400, "lifetime": 0.3},
    "cleave_arc": {"desc": "Sweeping particle arc", "rate": 300, "lifetime": 0.4},
    "ground_slam": {"desc": "Shockwave ring + debris", "rate": 500, "lifetime": 0.6},
    "parry_flash": {"desc": "Bright flash + metallic particles", "rate": 200, "lifetime": 0.2},
    "critical_hit": {"desc": "Slow-mo flash + burst + shake", "rate": 600, "lifetime": 0.5},
    "block_impact": {"desc": "Shield ripple + absorption", "rate": 150, "lifetime": 0.4},
}

WEAPON_TRAIL_COLORS: dict[str, list[float]] = {
    "sword": [0.9, 0.92, 0.95, 0.8],
    "axe": [1.0, 0.6, 0.2, 0.8],
    "hammer": [0.6, 0.6, 0.6, 0.8],
    "dagger": [0.7, 0.7, 0.8, 0.6],
    "spear": [0.8, 0.85, 0.9, 0.7],
}

# ---------------------------------------------------------------------------
# Monster ability config data
# ---------------------------------------------------------------------------

MONSTER_ABILITY_CONFIGS: dict[str, dict[str, Any]] = {
    "breath_weapon": {
        "desc": "Cone particles (fire/ice/poison via brand)", "rate": 600,
        "lifetime": 0.8, "size": 0.5, "angle": 35.0,
    },
    "charge": {
        "desc": "Dust trail, impact shockwave", "rate": 300,
        "lifetime": 0.6, "size": 0.3, "speed": 15.0,
    },
    "tail_swipe": {
        "desc": "Wind arc, debris scatter", "rate": 250,
        "lifetime": 0.5, "size": 0.4,
    },
    "ground_pound": {
        "desc": "Seismic wave, flying rocks", "rate": 500,
        "lifetime": 0.7, "size": 0.6,
    },
    "summon_circle": {
        "desc": "Magic circle, portal particles", "rate": 200,
        "lifetime": 2.0, "size": 0.15,
    },
    "roar": {
        "desc": "Shockwave ring, fear particles", "rate": 350,
        "lifetime": 0.8, "size": 0.8,
    },
    "enrage": {
        "desc": "Red pulsing aura, fire particles", "rate": 400,
        "lifetime": 1.5, "size": 0.3,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_color(rgba: list[float]) -> str:
    """Format RGBA list as C# Color constructor."""
    r, g, b, a = rgba[0], rgba[1], rgba[2], rgba[3]
    return f"new Color({r}f, {g}f, {b}f, {a}f)"


def _brand_color_dict_cs(var_name: str, color_map: dict[str, list[float]]) -> str:
    """Build C# Dictionary<string, Color> initializer from brand palette."""
    lines = [f"        private static readonly Dictionary<string, Color> {var_name} = new Dictionary<string, Color>"]
    lines.append("        {")
    for brand, rgba in color_map.items():
        lines.append(f'            {{ "{brand}", new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f) }},')
    lines.append("        };")
    return "\n".join(lines)


def _spell_configs_cs() -> str:
    """Build C# spell config dictionary initializer."""
    lines = []
    lines.append("        private static readonly Dictionary<string, SpellConfig> SpellConfigs = new Dictionary<string, SpellConfig>")
    lines.append("        {")
    for name, cfg in SPELL_CONFIGS.items():
        c = cfg["color"]
        g = cfg["glow"]
        lines.append(f'            {{ "{name}", new SpellConfig {{')
        lines.append(f"                color = new Color({c[0]}f, {c[1]}f, {c[2]}f, {c[3]}f),")
        lines.append(f"                glow = new Color({g[0]}f, {g[1]}f, {g[2]}f, {g[3]}f),")
        lines.append(f"                rate = {cfg['rate']}, lifetime = {cfg['lifetime']}f,")
        lines.append(f"                size = {cfg['size']}f, speed = {cfg['speed']}f,")
        lines.append(f"                impactRadius = {cfg['impact_radius']}f, lingerTime = {cfg['linger_time']}f,")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


def _weapon_trail_colors_cs() -> str:
    """Build C# weapon trail color dict."""
    lines = []
    lines.append("        private static readonly Dictionary<string, Color> WeaponTrailColors = new Dictionary<string, Color>")
    lines.append("        {")
    for wtype, rgba in WEAPON_TRAIL_COLORS.items():
        lines.append(f'            {{ "{wtype}", new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f) }},')
    lines.append("        };")
    return "\n".join(lines)


def _monster_ability_configs_cs() -> str:
    """Build C# monster ability config dictionary initializer."""
    lines = []
    lines.append("        private static readonly Dictionary<string, MonsterAbilityConfig> AbilityConfigs = new Dictionary<string, MonsterAbilityConfig>")
    lines.append("        {")
    for name, cfg in MONSTER_ABILITY_CONFIGS.items():
        lines.append(f'            {{ "{name}", new MonsterAbilityConfig {{')
        lines.append(f"                rate = {cfg['rate']}, lifetime = {cfg['lifetime']}f,")
        lines.append(f"                size = {cfg['size']}f,")
        if "speed" in cfg:
            lines.append(f"                speed = {cfg['speed']}f,")
        if "angle" in cfg:
            lines.append(f"                coneAngle = {cfg['angle']}f,")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


# ===================================================================
# CS code block helpers -- reusable particle setup snippets
# ===================================================================

_CS_PARTICLE_HELPER = '''
    // ---- Shared particle helpers ----
    private ParticleSystem CreatePS(string psName, Transform parent, int maxParticles = 1000)
    {
        var go = new GameObject(psName);
        go.transform.SetParent(parent, false);
        var ps = go.AddComponent<ParticleSystem>();
        var main = ps.main;
        main.playOnAwake = false;
        main.maxParticles = maxParticles;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        var emission = ps.emission;
        emission.enabled = false;
        var renderer = go.GetComponent<ParticleSystemRenderer>();
        renderer.material = GetParticleMaterial();
        return ps;
    }

    private void ConfigPS(ParticleSystem ps, Color color, float rate, float lifetime,
                          float size, ParticleSystemShapeType shape = ParticleSystemShapeType.Cone)
    {
        var main = ps.main;
        main.startColor = color;
        main.startLifetime = lifetime;
        main.startSize = size;
        var emission = ps.emission;
        emission.enabled = true;
        emission.rateOverTime = rate;
        var sh = ps.shape;
        sh.enabled = true;
        sh.shapeType = shape;
    }

    private void BurstPS(ParticleSystem ps, int count, Color color, float lifetime,
                         float sizeMin, float sizeMax, float speedMin, float speedMax)
    {
        var main = ps.main;
        main.startColor = color;
        main.startLifetime = lifetime;
        main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
        main.startSpeed = new ParticleSystem.MinMaxCurve(speedMin, speedMax);
        var emission = ps.emission;
        emission.enabled = true;
        emission.SetBursts(new ParticleSystem.Burst[] {
            new ParticleSystem.Burst(0f, (short)count)
        });
    }

    private Material GetParticleMaterial()
    {
        if (_particleMat == null)
        {
            var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
            _particleMat = new Material(shader);
            _particleMat.SetFloat("_Surface", 1f); // Transparent
            _particleMat.SetFloat("_Blend", 0f);   // Alpha
            _particleMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        }
        return _particleMat;
    }
    private Material _particleMat;

    private Material GetAdditiveMaterial()
    {
        if (_additiveMat == null)
        {
            var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
            _additiveMat = new Material(shader);
            _additiveMat.SetFloat("_Surface", 1f); // Transparent
            _additiveMat.SetFloat("_Blend", 1f);   // Additive
            _additiveMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        }
        return _additiveMat;
    }
    private Material _additiveMat;
'''

_CS_SCREEN_SHAKE = '''
    private void DoScreenShake(float intensity, float duration)
    {
        if (Camera.main == null) return;
        // PrimeTween camera shake
        PrimeTween.Tween.ShakeCamera(Camera.main, intensity, duration: duration);
    }
'''

_CS_COROUTINE_DELAY = '''
    private System.Collections.IEnumerator DelayedAction(float delay, System.Action action)
    {
        yield return new WaitForSeconds(delay);
        action?.Invoke();
    }
'''

# ===================================================================
# 1. generate_spell_vfx_script
# ===================================================================


def generate_spell_vfx_script(spell_type: str = "fireball") -> dict[str, Any]:
    """Generate SpellVFXController MonoBehaviour for spell casting VFX.

    Supports 8 spell types each with 4 phases: cast, travel, impact, linger.
    Uses a config-driven approach so all spells share the same setup/play logic.

    Args:
        spell_type: Default spell type to configure. One of: fireball,
            ice_shard, lightning_bolt, shadow_bolt, holy_smite, poison_cloud,
            earth_spike, arcane_missile. Defaults to fireball.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    spell_type = spell_type.lower().replace(" ", "_")
    if spell_type not in SPELL_CONFIGS:
        spell_type = "fireball"

    safe_spell = sanitize_cs_identifier(spell_type)
    spell_configs_block = _spell_configs_cs()

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Spell VFX controller for VeilBreakers.
/// Supports 8 spell types with 4 phases each: cast, travel, impact, linger.
/// Default spell: {spell_type}
/// API: CastSpell(spellType, origin, target) -- events OnSpellCast / OnSpellImpact
/// </summary>
public class SpellVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct SpellConfig
    {{
        public Color color;
        public Color glow;
        public int rate;
        public float lifetime;
        public float size;
        public float speed;
        public float impactRadius;
        public float lingerTime;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSpellType = "{spell_type}";

    // Events
    public event Action<string, Vector3> OnSpellCast;
    public event Action<string, Vector3> OnSpellImpact;

    // Spell configs
{spell_configs_block}

    // Runtime PS pools -- one set per phase, recycled across casts
    private ParticleSystem castCirclePS;
    private ParticleSystem castRunePS;
    private ParticleSystem castGatherPS;
    private ParticleSystem travelCorePS;
    private ParticleSystem travelTrailPS;
    private ParticleSystem impactBurstPS;
    private ParticleSystem impactDebrisPS;
    private ParticleSystem lingerPS;
    private Light castLight;
    private Light impactLight;

    private Coroutine activeSpellRoutine;
{_CS_PARTICLE_HELPER}
{_CS_SCREEN_SHAKE}
{_CS_COROUTINE_DELAY}

    private void Awake()
    {{
        InitializeParticleSystems();
    }}

    private void InitializeParticleSystems()
    {{
        var root = transform;
        // Cast phase
        castCirclePS = CreatePS("SpellCastCircle", root, 500);
        castRunePS = CreatePS("SpellCastRunes", root, 200);
        castGatherPS = CreatePS("SpellCastGather", root, 300);
        // Travel phase
        travelCorePS = CreatePS("SpellTravelCore", root, 500);
        travelTrailPS = CreatePS("SpellTravelTrail", root, 800);
        // Impact phase
        impactBurstPS = CreatePS("SpellImpactBurst", root, 1000);
        impactDebrisPS = CreatePS("SpellImpactDebris", root, 500);
        // Linger phase
        lingerPS = CreatePS("SpellLinger", root, 300);
        // Lights
        var castLightGo = new GameObject("SpellCastLight");
        castLightGo.transform.SetParent(root, false);
        castLight = castLightGo.AddComponent<Light>();
        castLight.type = LightType.Point;
        castLight.intensity = 0f;
        castLight.range = 5f;
        castLight.enabled = false;

        var impactLightGo = new GameObject("SpellImpactLight");
        impactLightGo.transform.SetParent(root, false);
        impactLight = impactLightGo.AddComponent<Light>();
        impactLight.type = LightType.Point;
        impactLight.intensity = 0f;
        impactLight.range = 8f;
        impactLight.enabled = false;
    }}

    /// <summary>Cast a spell from origin toward target.</summary>
    public void CastSpell(string spellType, Vector3 origin, Vector3 target)
    {{
        spellType = spellType.ToLowerInvariant().Replace(" ", "_");
        if (!SpellConfigs.ContainsKey(spellType))
        {{
            Debug.LogWarning($"[SpellVFX] Unknown spell type: {{spellType}}, using {spell_type}");
            spellType = "{spell_type}";
        }}
        if (activeSpellRoutine != null) StopCoroutine(activeSpellRoutine);
        activeSpellRoutine = StartCoroutine(SpellSequence(spellType, origin, target));
    }}

    private IEnumerator SpellSequence(string spellType, Vector3 origin, Vector3 target)
    {{
        var cfg = SpellConfigs[spellType];
        var dir = (target - origin).normalized;
        var dist = Vector3.Distance(origin, target);

        // ==== Phase 1: CAST (magic circle + rune particles + energy gather) ====
        OnSpellCast?.Invoke(spellType, origin);
        yield return StartCoroutine(CastPhase(cfg, origin));

        // ==== Phase 2: TRAVEL (projectile core + trail) ====
        if (spellType == "lightning_bolt")
        {{
            // Instant -- arc from sky
            yield return StartCoroutine(LightningStrike(cfg, origin, target));
        }}
        else if (spellType == "holy_smite")
        {{
            // Beam from above
            yield return StartCoroutine(BeamFromAbove(cfg, target));
        }}
        else if (spellType == "earth_spike")
        {{
            // Ground eruption at target
            yield return StartCoroutine(GroundEruption(cfg, target));
        }}
        else if (spellType == "poison_cloud")
        {{
            // Slow expanding cloud
            yield return StartCoroutine(TravelPhase(cfg, origin, target, dir, dist));
        }}
        else
        {{
            // Standard projectile travel
            yield return StartCoroutine(TravelPhase(cfg, origin, target, dir, dist));
        }}

        // ==== Phase 3: IMPACT (explosion + debris) ====
        yield return StartCoroutine(ImpactPhase(cfg, target, spellType));

        // ==== Phase 4: LINGER (residual particles) ====
        yield return StartCoroutine(LingerPhase(cfg, target, spellType));

        activeSpellRoutine = null;
    }}

    // ---- CAST PHASE ----
    private IEnumerator CastPhase(SpellConfig cfg, Vector3 origin)
    {{
        // Magic circle on ground
        castCirclePS.transform.position = origin;
        ConfigPS(castCirclePS, cfg.glow, cfg.rate * 0.3f, 0.8f, cfg.size * 3f,
                 ParticleSystemShapeType.Circle);
        var circleShape = castCirclePS.shape;
        circleShape.radius = 1.2f;
        castCirclePS.Play();

        // Rune particles rising
        castRunePS.transform.position = origin;
        ConfigPS(castRunePS, cfg.color, cfg.rate * 0.2f, 1.0f, cfg.size * 0.5f,
                 ParticleSystemShapeType.Circle);
        var runeVel = castRunePS.velocityOverLifetime;
        runeVel.enabled = true;
        runeVel.y = new ParticleSystem.MinMaxCurve(1f, 2f);
        castRunePS.Play();

        // Energy gathering inward
        castGatherPS.transform.position = origin + Vector3.up * 1.2f;
        ConfigPS(castGatherPS, cfg.glow, cfg.rate * 0.5f, 0.5f, cfg.size * 0.3f,
                 ParticleSystemShapeType.Sphere);
        var gatherShape = castGatherPS.shape;
        gatherShape.radius = 2.5f;
        var gatherMain = castGatherPS.main;
        gatherMain.startSpeed = new ParticleSystem.MinMaxCurve(-4f, -2f);
        castGatherPS.Play();

        // Cast light
        castLight.transform.position = origin + Vector3.up;
        castLight.color = cfg.glow;
        castLight.enabled = true;
        PrimeTween.Tween.Custom(castLight, 0f, 4f, duration: 0.5f,
            onValueChange: (target, val) => target.intensity = val);

        yield return new WaitForSeconds(0.6f);

        castCirclePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        castRunePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        castGatherPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        PrimeTween.Tween.Custom(castLight, 4f, 0f, duration: 0.2f,
            onValueChange: (target, val) => target.intensity = val);
        yield return new WaitForSeconds(0.2f);
        castLight.enabled = false;
    }}

    // ---- TRAVEL PHASE (standard projectile) ----
    private IEnumerator TravelPhase(SpellConfig cfg, Vector3 origin, Vector3 target,
                                     Vector3 dir, float dist)
    {{
        var projectilePos = origin + Vector3.up * 1.2f;
        travelCorePS.transform.position = projectilePos;
        ConfigPS(travelCorePS, cfg.color, cfg.rate, cfg.lifetime * 0.5f, cfg.size,
                 ParticleSystemShapeType.Sphere);
        var coreShape = travelCorePS.shape;
        coreShape.radius = cfg.size * 0.5f;
        travelCorePS.Play();

        travelTrailPS.transform.position = projectilePos;
        ConfigPS(travelTrailPS, cfg.glow * 0.7f, cfg.rate * 0.6f, cfg.lifetime, cfg.size * 0.3f,
                 ParticleSystemShapeType.Cone);
        var trailShape = travelTrailPS.shape;
        trailShape.angle = 5f;
        travelTrailPS.Play();

        // Move projectile
        float travelTime = dist / cfg.speed;
        float elapsed = 0f;
        while (elapsed < travelTime)
        {{
            elapsed += Time.deltaTime;
            float t = Mathf.Clamp01(elapsed / travelTime);
            var pos = Vector3.Lerp(origin + Vector3.up * 1.2f, target, t);
            travelCorePS.transform.position = pos;
            travelTrailPS.transform.position = pos;
            yield return null;
        }}

        travelCorePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        travelTrailPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- LIGHTNING STRIKE (instant arc) ----
    private IEnumerator LightningStrike(SpellConfig cfg, Vector3 origin, Vector3 target)
    {{
        // Flash from sky to target
        var skyPos = target + Vector3.up * 20f;
        travelCorePS.transform.position = target;
        BurstPS(travelCorePS, 300, cfg.glow, 0.15f, 0.02f, 0.08f, 5f, 15f);
        travelCorePS.Play();

        // Bright flash light
        impactLight.transform.position = target + Vector3.up;
        impactLight.color = cfg.glow;
        impactLight.range = 15f;
        impactLight.enabled = true;
        PrimeTween.Tween.Custom(impactLight, 8f, 0f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);

        DoScreenShake(0.5f, 0.15f);

        yield return new WaitForSeconds(0.15f);
        travelCorePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- BEAM FROM ABOVE (holy smite) ----
    private IEnumerator BeamFromAbove(SpellConfig cfg, Vector3 target)
    {{
        var beamTop = target + Vector3.up * 15f;
        travelCorePS.transform.position = beamTop;
        ConfigPS(travelCorePS, cfg.glow, cfg.rate * 2, 0.4f, cfg.size * 0.8f,
                 ParticleSystemShapeType.Cone);
        var shape = travelCorePS.shape;
        shape.angle = 3f;
        shape.rotation = new Vector3(180f, 0f, 0f);
        var main = travelCorePS.main;
        main.startSpeed = new ParticleSystem.MinMaxCurve(30f, 45f);
        travelCorePS.Play();

        impactLight.transform.position = target + Vector3.up * 2f;
        impactLight.color = cfg.glow;
        impactLight.range = 12f;
        impactLight.enabled = true;
        PrimeTween.Tween.Custom(impactLight, 0f, 6f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);

        yield return new WaitForSeconds(0.5f);
        travelCorePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        PrimeTween.Tween.Custom(impactLight, 6f, 0f, duration: 0.4f,
            onValueChange: (target, val) => target.intensity = val);
        yield return new WaitForSeconds(0.4f);
        impactLight.enabled = false;
    }}

    // ---- GROUND ERUPTION (earth spike) ----
    private IEnumerator GroundEruption(SpellConfig cfg, Vector3 target)
    {{
        travelCorePS.transform.position = target;
        BurstPS(travelCorePS, 200, cfg.color, 0.6f, 0.1f, 0.4f, 8f, 18f);
        var vel = travelCorePS.velocityOverLifetime;
        vel.enabled = true;
        vel.y = new ParticleSystem.MinMaxCurve(5f, 15f);
        vel.x = new ParticleSystem.MinMaxCurve(-3f, 3f);
        vel.z = new ParticleSystem.MinMaxCurve(-3f, 3f);
        travelCorePS.Play();

        DoScreenShake(0.6f, 0.3f);

        yield return new WaitForSeconds(0.5f);
        travelCorePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- IMPACT PHASE ----
    private IEnumerator ImpactPhase(SpellConfig cfg, Vector3 target, string spellType)
    {{
        OnSpellImpact?.Invoke(spellType, target);

        impactBurstPS.transform.position = target;
        BurstPS(impactBurstPS, Mathf.RoundToInt(cfg.rate * 1.5f), cfg.glow,
                cfg.lifetime * 0.6f, cfg.size * 0.5f, cfg.size * 2f, 3f, 12f);
        var shape = impactBurstPS.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = cfg.impactRadius * 0.3f;
        impactBurstPS.Play();

        impactDebrisPS.transform.position = target;
        BurstPS(impactDebrisPS, 80, cfg.color * 0.6f, cfg.lifetime, cfg.size * 0.3f,
                cfg.size * 0.8f, 2f, 8f);
        var debrisMain = impactDebrisPS.main;
        debrisMain.gravityModifier = 0.8f;
        impactDebrisPS.Play();

        // Impact light flash
        impactLight.transform.position = target + Vector3.up * 0.5f;
        impactLight.color = cfg.glow;
        impactLight.range = cfg.impactRadius * 2f;
        impactLight.enabled = true;
        PrimeTween.Tween.Custom(impactLight, 5f, 0f, duration: 0.4f,
            onValueChange: (target, val) => target.intensity = val);

        // Screen shake scaled to impact
        float shakeIntensity = spellType == "lightning_bolt" ? 0.6f :
                               spellType == "earth_spike" ? 0.7f : 0.35f;
        DoScreenShake(shakeIntensity, 0.25f);

        yield return new WaitForSeconds(0.5f);
        impactBurstPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        impactDebrisPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        impactLight.enabled = false;
    }}

    // ---- LINGER PHASE ----
    private IEnumerator LingerPhase(SpellConfig cfg, Vector3 target, string spellType)
    {{
        lingerPS.transform.position = target;

        // Spell-specific linger behavior
        if (spellType == "poison_cloud")
        {{
            ConfigPS(lingerPS, cfg.color * 0.5f, 40f, cfg.lingerTime, cfg.size * 2f,
                     ParticleSystemShapeType.Sphere);
            var lShape = lingerPS.shape;
            lShape.radius = cfg.impactRadius;
        }}
        else if (spellType == "lightning_bolt")
        {{
            // Ground scorch sparks
            ConfigPS(lingerPS, cfg.color * 0.3f, 20f, 0.3f, 0.05f,
                     ParticleSystemShapeType.Circle);
        }}
        else
        {{
            ConfigPS(lingerPS, cfg.glow * 0.3f, 15f, cfg.lingerTime * 0.5f,
                     cfg.size * 0.4f, ParticleSystemShapeType.Hemisphere);
            var lShape = lingerPS.shape;
            lShape.radius = cfg.impactRadius * 0.5f;
        }}
        lingerPS.Play();

        yield return new WaitForSeconds(cfg.lingerTime);
        lingerPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Spell VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("SpellVFXController");
        go.AddComponent<SpellVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("SpellVFXController created in scene");
    }}

    private static void WriteResult(string msg)
    {{
        var json = JsonUtility.ToJson(new VBResult {{ success = true, message = msg }});
        System.IO.File.WriteAllText(
            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"), json);
    }}

    [System.Serializable]
    private class VBResult {{ public bool success; public string message; }}
#endif
}}
'''

    script_path = "Assets/Editor/Generated/VFX/SpellVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 2. generate_melee_combat_vfx_script
# ===================================================================


def generate_melee_combat_vfx_script() -> dict[str, Any]:
    """Generate MeleeCombatVFXController MonoBehaviour.

    Covers weapon trails, impact sparks, cleave arcs, ground slam, parry flash,
    critical hit, and block impact -- all via TriggerMeleeVFX API.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    weapon_colors_block = _weapon_trail_colors_cs()

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Melee combat VFX controller for VeilBreakers.
/// Weapon trails, impact sparks, cleave arcs, ground slam, parry, crit, block.
/// API: TriggerMeleeVFX(vfxType, position, direction) -- event OnMeleeVFXTriggered
/// </summary>
public class MeleeCombatVFXController : MonoBehaviour
{{
    [Header("Trail Settings")]
    [SerializeField] private float trailDuration = 0.3f;
    [SerializeField] private float trailWidth = 0.15f;
    [SerializeField] private string weaponType = "sword";

    [Header("Impact Settings")]
    [SerializeField] private float sparkCount = 30;
    [SerializeField] private float critSlowMoDuration = 0.15f;
    [SerializeField] private float critSlowMoScale = 0.1f;

    // Events
    public event Action<string, Vector3, Vector3> OnMeleeVFXTriggered;

    // Weapon trail colors
{weapon_colors_block}

    // Runtime refs
    private TrailRenderer weaponTrail;
    private ParticleSystem sparkPS;
    private ParticleSystem cleavePS;
    private ParticleSystem slamWavePS;
    private ParticleSystem slamDebrisPS;
    private ParticleSystem parryFlashPS;
    private ParticleSystem critBurstPS;
    private ParticleSystem blockRipplePS;
    private Light flashLight;
{_CS_PARTICLE_HELPER}
{_CS_SCREEN_SHAKE}
{_CS_COROUTINE_DELAY}

    private void Awake()
    {{
        InitializeMeleeVFX();
    }}

    private void InitializeMeleeVFX()
    {{
        var root = transform;

        // Weapon trail
        var trailGo = new GameObject("WeaponTrail");
        trailGo.transform.SetParent(root, false);
        weaponTrail = trailGo.AddComponent<TrailRenderer>();
        weaponTrail.time = trailDuration;
        weaponTrail.startWidth = trailWidth;
        weaponTrail.endWidth = 0.01f;
        weaponTrail.material = GetAdditiveMaterial();
        weaponTrail.emitting = false;
        weaponTrail.numCornerVertices = 4;
        weaponTrail.numCapVertices = 4;
        SetTrailColor(weaponType);

        // Particle systems
        sparkPS = CreatePS("ImpactSparks", root, 500);
        cleavePS = CreatePS("CleaveArc", root, 400);
        slamWavePS = CreatePS("SlamWave", root, 600);
        slamDebrisPS = CreatePS("SlamDebris", root, 300);
        parryFlashPS = CreatePS("ParryFlash", root, 200);
        critBurstPS = CreatePS("CritBurst", root, 800);
        blockRipplePS = CreatePS("BlockRipple", root, 200);

        // Flash light
        var lightGo = new GameObject("MeleeFlashLight");
        lightGo.transform.SetParent(root, false);
        flashLight = lightGo.AddComponent<Light>();
        flashLight.type = LightType.Point;
        flashLight.intensity = 0f;
        flashLight.range = 6f;
        flashLight.enabled = false;
    }}

    private void SetTrailColor(string wType)
    {{
        Color c = WeaponTrailColors.ContainsKey(wType)
            ? WeaponTrailColors[wType]
            : new Color(0.9f, 0.9f, 0.9f, 0.8f);
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(c, 0f),
                new GradientColorKey(c * 0.5f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(c.a, 0f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        weaponTrail.colorGradient = grad;
    }}

    /// <summary>Trigger melee VFX by type name.</summary>
    public void TriggerMeleeVFX(string vfxType, Vector3 position, Vector3 direction)
    {{
        OnMeleeVFXTriggered?.Invoke(vfxType, position, direction);

        switch (vfxType.ToLowerInvariant().Replace(" ", "_"))
        {{
            case "weapon_trail": StartWeaponTrail(); break;
            case "impact_sparks": PlayImpactSparks(position, direction); break;
            case "cleave_arc": PlayCleaveArc(position, direction); break;
            case "ground_slam": PlayGroundSlam(position); break;
            case "parry_flash": PlayParryFlash(position); break;
            case "critical_hit": StartCoroutine(PlayCriticalHit(position, direction)); break;
            case "block_impact": PlayBlockImpact(position, direction); break;
            default:
                Debug.LogWarning($"[MeleeCombatVFX] Unknown type: {{vfxType}}");
                break;
        }}
    }}

    /// <summary>Set weapon type and update trail color.</summary>
    public void SetWeaponType(string wType)
    {{
        weaponType = wType.ToLowerInvariant();
        SetTrailColor(weaponType);
    }}

    // ---- WEAPON TRAIL ----
    public void StartWeaponTrail()
    {{
        weaponTrail.emitting = true;
        StartCoroutine(StopTrailAfter(trailDuration + 0.1f));
    }}

    private IEnumerator StopTrailAfter(float delay)
    {{
        yield return new WaitForSeconds(delay);
        weaponTrail.emitting = false;
    }}

    // ---- IMPACT SPARKS ----
    private void PlayImpactSparks(Vector3 position, Vector3 direction)
    {{
        sparkPS.transform.position = position;
        sparkPS.transform.forward = direction;
        BurstPS(sparkPS, (int)sparkCount, new Color(1f, 0.85f, 0.5f, 1f),
                0.3f, 0.02f, 0.06f, 5f, 15f);
        var shape = sparkPS.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 25f;
        var main = sparkPS.main;
        main.gravityModifier = 0.5f;
        sparkPS.Play();
        FlashLight(position, new Color(1f, 0.85f, 0.5f), 3f, 0.15f);
    }}

    // ---- CLEAVE ARC ----
    private void PlayCleaveArc(Vector3 position, Vector3 direction)
    {{
        cleavePS.transform.position = position;
        cleavePS.transform.forward = direction;
        BurstPS(cleavePS, 200, new Color(0.9f, 0.9f, 0.95f, 0.7f),
                0.4f, 0.05f, 0.15f, 3f, 8f);
        var shape = cleavePS.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 60f;
        shape.arc = 180f;
        shape.arcMode = ParticleSystemShapeMultiModeValue.Random;
        cleavePS.Play();
    }}

    // ---- GROUND SLAM ----
    private void PlayGroundSlam(Vector3 position)
    {{
        // Shockwave ring
        slamWavePS.transform.position = position;
        BurstPS(slamWavePS, 400, new Color(0.8f, 0.7f, 0.5f, 0.6f),
                0.6f, 0.3f, 0.8f, 8f, 16f);
        var waveShape = slamWavePS.shape;
        waveShape.shapeType = ParticleSystemShapeType.Circle;
        waveShape.radius = 0.5f;
        var waveVel = slamWavePS.velocityOverLifetime;
        waveVel.enabled = true;
        waveVel.radial = new ParticleSystem.MinMaxCurve(8f, 14f);
        waveVel.y = new ParticleSystem.MinMaxCurve(0.5f, 2f);
        slamWavePS.Play();

        // Debris
        slamDebrisPS.transform.position = position;
        BurstPS(slamDebrisPS, 60, new Color(0.5f, 0.4f, 0.3f, 1f),
                0.8f, 0.1f, 0.3f, 4f, 10f);
        var debrisMain = slamDebrisPS.main;
        debrisMain.gravityModifier = 1.2f;
        slamDebrisPS.Play();

        DoScreenShake(0.7f, 0.3f);
        FlashLight(position, new Color(1f, 0.9f, 0.7f), 4f, 0.25f);
    }}

    // ---- PARRY FLASH ----
    private void PlayParryFlash(Vector3 position)
    {{
        parryFlashPS.transform.position = position;
        BurstPS(parryFlashPS, 150, new Color(1f, 1f, 1f, 1f),
                0.2f, 0.1f, 0.3f, 4f, 10f);
        parryFlashPS.Play();
        FlashLight(position, Color.white, 6f, 0.1f);
        DoScreenShake(0.2f, 0.1f);
    }}

    // ---- CRITICAL HIT ----
    private IEnumerator PlayCriticalHit(Vector3 position, Vector3 direction)
    {{
        // Slow-mo
        Time.timeScale = critSlowMoScale;
        Time.fixedDeltaTime = 0.02f * critSlowMoScale;

        // Big burst
        critBurstPS.transform.position = position;
        BurstPS(critBurstPS, 500, new Color(1f, 0.9f, 0.3f, 1f),
                0.5f, 0.1f, 0.5f, 8f, 20f);
        critBurstPS.Play();

        FlashLight(position, new Color(1f, 0.95f, 0.7f), 8f, 0.3f);
        DoScreenShake(0.8f, 0.3f);

        yield return new WaitForSecondsRealtime(critSlowMoDuration);

        // Restore time
        Time.timeScale = 1f;
        Time.fixedDeltaTime = 0.02f;
    }}

    // ---- BLOCK IMPACT ----
    private void PlayBlockImpact(Vector3 position, Vector3 direction)
    {{
        blockRipplePS.transform.position = position;
        blockRipplePS.transform.forward = direction;
        BurstPS(blockRipplePS, 100, new Color(0.5f, 0.7f, 1f, 0.6f),
                0.4f, 0.2f, 0.6f, 2f, 5f);
        var shape = blockRipplePS.shape;
        shape.shapeType = ParticleSystemShapeType.Hemisphere;
        shape.radius = 0.5f;
        blockRipplePS.Play();
        FlashLight(position, new Color(0.5f, 0.7f, 1f), 3f, 0.2f);
    }}

    // ---- Light flash utility ----
    private void FlashLight(Vector3 pos, Color color, float intensity, float duration)
    {{
        flashLight.transform.position = pos + Vector3.up * 0.3f;
        flashLight.color = color;
        flashLight.enabled = true;
        PrimeTween.Tween.Custom(flashLight, intensity, 0f, duration: duration,
            onValueChange: (target, val) => target.intensity = val)
            .OnComplete(flashLight, t => t.enabled = false);
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Melee Combat VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("MeleeCombatVFXController");
        go.AddComponent<MeleeCombatVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("MeleeCombatVFXController created in scene");
    }}

    private static void WriteResult(string msg)
    {{
        var json = JsonUtility.ToJson(new VBResult {{ success = true, message = msg }});
        System.IO.File.WriteAllText(
            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"), json);
    }}

    [System.Serializable]
    private class VBResult {{ public bool success; public string message; }}
#endif
}}
'''

    script_path = "Assets/Editor/Generated/VFX/MeleeCombatVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 3. generate_monster_ability_vfx_script
# ===================================================================


def generate_monster_ability_vfx_script(ability_type: str = "breath_weapon") -> dict[str, Any]:
    """Generate MonsterAbilityVFXController MonoBehaviour.

    Supports 7 monster ability types with brand-colored variants.
    API: TriggerAbility(abilityType, brand) -- event OnAbilityTriggered.

    Args:
        ability_type: Default ability type. One of: breath_weapon, charge,
            tail_swipe, ground_pound, summon_circle, roar, enrage.
            Defaults to breath_weapon.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    ability_type = ability_type.lower().replace(" ", "_")
    if ability_type not in MONSTER_ABILITY_CONFIGS:
        ability_type = "breath_weapon"

    safe_ability = sanitize_cs_identifier(ability_type)
    ability_configs_block = _monster_ability_configs_cs()
    brand_primary_block = _brand_color_dict_cs("BrandPrimary", BRAND_PRIMARY_COLORS)
    brand_glow_block = _brand_color_dict_cs("BrandGlow", BRAND_GLOW_COLORS)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Monster ability VFX controller for VeilBreakers.
/// 7 ability types with brand-colored variants.
/// Default: {ability_type}
/// API: TriggerAbility(abilityType, brand) -- event OnAbilityTriggered
/// </summary>
public class MonsterAbilityVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct MonsterAbilityConfig
    {{
        public int rate;
        public float lifetime;
        public float size;
        public float speed;
        public float coneAngle;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultAbilityType = "{ability_type}";
    [SerializeField] private string defaultBrand = "IRON";

    // Events
    public event Action<string, string> OnAbilityTriggered;

    // Ability configs
{ability_configs_block}

    // Brand palettes
{brand_primary_block}

{brand_glow_block}

    // Runtime PS refs
    private ParticleSystem primaryPS;
    private ParticleSystem secondaryPS;
    private ParticleSystem wavePS;
    private ParticleSystem debrisPS;
    private ParticleSystem auraPS;
    private ParticleSystem circlePS;
    private Light abilityLight;

    private Coroutine activeAbilityRoutine;
{_CS_PARTICLE_HELPER}
{_CS_SCREEN_SHAKE}
{_CS_COROUTINE_DELAY}

    private void Awake()
    {{
        InitializeAbilityVFX();
    }}

    private void InitializeAbilityVFX()
    {{
        var root = transform;
        primaryPS = CreatePS("AbilityPrimary", root, 1000);
        secondaryPS = CreatePS("AbilitySecondary", root, 500);
        wavePS = CreatePS("AbilityWave", root, 600);
        debrisPS = CreatePS("AbilityDebris", root, 400);
        auraPS = CreatePS("AbilityAura", root, 300);
        circlePS = CreatePS("AbilityCircle", root, 400);

        var lightGo = new GameObject("AbilityLight");
        lightGo.transform.SetParent(root, false);
        abilityLight = lightGo.AddComponent<Light>();
        abilityLight.type = LightType.Point;
        abilityLight.intensity = 0f;
        abilityLight.range = 8f;
        abilityLight.enabled = false;
    }}

    private Color GetBrandColor(string brand)
    {{
        return BrandPrimary.ContainsKey(brand) ? BrandPrimary[brand] : BrandPrimary["IRON"];
    }}

    private Color GetBrandGlow(string brand)
    {{
        return BrandGlow.ContainsKey(brand) ? BrandGlow[brand] : BrandGlow["IRON"];
    }}

    /// <summary>Trigger a monster ability VFX with brand coloring.</summary>
    public void TriggerAbility(string abilityType, string brand = "IRON")
    {{
        abilityType = abilityType.ToLowerInvariant().Replace(" ", "_");
        brand = brand.ToUpperInvariant();
        OnAbilityTriggered?.Invoke(abilityType, brand);

        if (activeAbilityRoutine != null) StopCoroutine(activeAbilityRoutine);
        activeAbilityRoutine = StartCoroutine(AbilitySequence(abilityType, brand));
    }}

    private IEnumerator AbilitySequence(string abilityType, string brand)
    {{
        if (!AbilityConfigs.ContainsKey(abilityType))
        {{
            Debug.LogWarning($"[MonsterAbilityVFX] Unknown ability: {{abilityType}}");
            yield break;
        }}

        var cfg = AbilityConfigs[abilityType];
        var col = GetBrandColor(brand);
        var glow = GetBrandGlow(brand);
        var pos = transform.position;
        var fwd = transform.forward;

        switch (abilityType)
        {{
            case "breath_weapon":
                yield return StartCoroutine(BreathWeapon(cfg, col, glow, pos, fwd));
                break;
            case "charge":
                yield return StartCoroutine(Charge(cfg, col, glow, pos, fwd));
                break;
            case "tail_swipe":
                yield return StartCoroutine(TailSwipe(cfg, col, glow, pos, fwd));
                break;
            case "ground_pound":
                yield return StartCoroutine(GroundPound(cfg, col, glow, pos));
                break;
            case "summon_circle":
                yield return StartCoroutine(SummonCircle(cfg, col, glow, pos));
                break;
            case "roar":
                yield return StartCoroutine(Roar(cfg, col, glow, pos));
                break;
            case "enrage":
                yield return StartCoroutine(Enrage(cfg, col, glow, pos));
                break;
        }}

        activeAbilityRoutine = null;
    }}

    // ---- BREATH WEAPON (cone particles, brand colored) ----
    private IEnumerator BreathWeapon(MonsterAbilityConfig cfg, Color col, Color glow,
                                      Vector3 pos, Vector3 fwd)
    {{
        primaryPS.transform.position = pos + fwd * 0.5f + Vector3.up * 1.5f;
        primaryPS.transform.forward = fwd;
        ConfigPS(primaryPS, col, cfg.rate, cfg.lifetime, cfg.size,
                 ParticleSystemShapeType.Cone);
        var shape = primaryPS.shape;
        shape.angle = cfg.coneAngle > 0 ? cfg.coneAngle : 35f;
        var main = primaryPS.main;
        main.startSpeed = new ParticleSystem.MinMaxCurve(10f, 18f);
        primaryPS.Play();

        // Secondary embers/frost/droplets
        secondaryPS.transform.position = primaryPS.transform.position;
        secondaryPS.transform.forward = fwd;
        ConfigPS(secondaryPS, glow * 0.6f, cfg.rate * 0.3f, cfg.lifetime * 1.5f,
                 cfg.size * 0.3f, ParticleSystemShapeType.Cone);
        var secShape = secondaryPS.shape;
        secShape.angle = cfg.coneAngle > 0 ? cfg.coneAngle + 10f : 45f;
        var secMain = secondaryPS.main;
        secMain.startSpeed = new ParticleSystem.MinMaxCurve(6f, 12f);
        secMain.gravityModifier = 0.3f;
        secondaryPS.Play();

        FlashAbilityLight(pos + fwd + Vector3.up, glow, 5f, cfg.lifetime + 0.5f);

        yield return new WaitForSeconds(cfg.lifetime + 0.3f);
        primaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        secondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        yield return new WaitForSeconds(0.5f);
    }}

    // ---- CHARGE (dust trail + impact shockwave) ----
    private IEnumerator Charge(MonsterAbilityConfig cfg, Color col, Color glow,
                                Vector3 pos, Vector3 fwd)
    {{
        // Dust trail during charge
        primaryPS.transform.position = pos;
        ConfigPS(primaryPS, new Color(0.6f, 0.5f, 0.4f, 0.5f), cfg.rate, cfg.lifetime,
                 cfg.size, ParticleSystemShapeType.Circle);
        var shape = primaryPS.shape;
        shape.radius = 0.8f;
        primaryPS.Play();

        // Simulate forward movement
        float chargeDist = cfg.speed > 0 ? cfg.speed : 15f;
        float chargeDuration = 0.8f;
        float elapsed = 0f;
        while (elapsed < chargeDuration)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / chargeDuration;
            primaryPS.transform.position = pos + fwd * (chargeDist * t);
            yield return null;
        }}
        primaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        // Impact shockwave
        var impactPos = pos + fwd * chargeDist;
        wavePS.transform.position = impactPos;
        BurstPS(wavePS, 300, col, 0.5f, 0.2f, 0.6f, 6f, 14f);
        var waveVel = wavePS.velocityOverLifetime;
        waveVel.enabled = true;
        waveVel.radial = new ParticleSystem.MinMaxCurve(6f, 12f);
        wavePS.Play();

        DoScreenShake(0.6f, 0.25f);
        FlashAbilityLight(impactPos + Vector3.up, glow, 4f, 0.3f);

        yield return new WaitForSeconds(0.6f);
        wavePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- TAIL SWIPE (wind arc + debris scatter) ----
    private IEnumerator TailSwipe(MonsterAbilityConfig cfg, Color col, Color glow,
                                    Vector3 pos, Vector3 fwd)
    {{
        // Wind arc
        primaryPS.transform.position = pos - fwd * 0.5f;
        primaryPS.transform.forward = -fwd;
        BurstPS(primaryPS, 200, new Color(0.8f, 0.85f, 0.9f, 0.4f),
                cfg.lifetime, 0.1f, 0.4f, 5f, 12f);
        var shape = primaryPS.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 80f;
        shape.arc = 180f;
        shape.arcMode = ParticleSystemShapeMultiModeValue.Random;
        primaryPS.Play();

        // Debris scatter
        debrisPS.transform.position = pos;
        BurstPS(debrisPS, 50, col * 0.5f, 0.8f, 0.05f, 0.2f, 3f, 8f);
        var debrisMain = debrisPS.main;
        debrisMain.gravityModifier = 1.0f;
        debrisPS.Play();

        DoScreenShake(0.3f, 0.15f);

        yield return new WaitForSeconds(cfg.lifetime + 0.3f);
        primaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        debrisPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- GROUND POUND (seismic wave + flying rocks) ----
    private IEnumerator GroundPound(MonsterAbilityConfig cfg, Color col, Color glow,
                                     Vector3 pos)
    {{
        // Seismic wave ring
        wavePS.transform.position = pos;
        BurstPS(wavePS, 500, col, cfg.lifetime, 0.3f, 1.0f, 10f, 20f);
        var waveShape = wavePS.shape;
        waveShape.shapeType = ParticleSystemShapeType.Circle;
        waveShape.radius = 0.5f;
        var waveVel = wavePS.velocityOverLifetime;
        waveVel.enabled = true;
        waveVel.radial = new ParticleSystem.MinMaxCurve(10f, 18f);
        waveVel.y = new ParticleSystem.MinMaxCurve(1f, 3f);
        wavePS.Play();

        // Flying rocks
        debrisPS.transform.position = pos;
        BurstPS(debrisPS, 80, new Color(0.5f, 0.4f, 0.3f, 1f),
                1.0f, 0.15f, 0.5f, 6f, 15f);
        var debrisMain = debrisPS.main;
        debrisMain.gravityModifier = 1.5f;
        var debrisVel = debrisPS.velocityOverLifetime;
        debrisVel.enabled = true;
        debrisVel.y = new ParticleSystem.MinMaxCurve(8f, 16f);
        debrisPS.Play();

        DoScreenShake(0.9f, 0.4f);
        FlashAbilityLight(pos + Vector3.up, glow, 5f, 0.4f);

        // Dust cloud follow-up
        yield return new WaitForSeconds(0.3f);
        secondaryPS.transform.position = pos;
        ConfigPS(secondaryPS, new Color(0.6f, 0.5f, 0.4f, 0.3f), 80f, 2.0f,
                 1.5f, ParticleSystemShapeType.Circle);
        var secShape = secondaryPS.shape;
        secShape.radius = 3f;
        secondaryPS.Play();

        yield return new WaitForSeconds(1.5f);
        wavePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        debrisPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        secondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- SUMMON CIRCLE (magic circle + portal particles) ----
    private IEnumerator SummonCircle(MonsterAbilityConfig cfg, Color col, Color glow,
                                      Vector3 pos)
    {{
        // Ground circle
        circlePS.transform.position = pos;
        ConfigPS(circlePS, glow, cfg.rate, cfg.lifetime, cfg.size,
                 ParticleSystemShapeType.Circle);
        var circShape = circlePS.shape;
        circShape.radius = 2f;
        circShape.radiusThickness = 0f; // edge only
        circlePS.Play();

        // Rising portal particles
        primaryPS.transform.position = pos;
        ConfigPS(primaryPS, col, cfg.rate * 0.5f, cfg.lifetime * 0.8f,
                 cfg.size * 2f, ParticleSystemShapeType.Circle);
        var primShape = primaryPS.shape;
        primShape.radius = 1.5f;
        var primVel = primaryPS.velocityOverLifetime;
        primVel.enabled = true;
        primVel.y = new ParticleSystem.MinMaxCurve(2f, 5f);
        primaryPS.Play();

        FlashAbilityLight(pos + Vector3.up * 0.5f, glow, 3f, cfg.lifetime);

        yield return new WaitForSeconds(cfg.lifetime);

        // Final burst
        secondaryPS.transform.position = pos + Vector3.up;
        BurstPS(secondaryPS, 200, glow, 0.5f, 0.1f, 0.4f, 3f, 8f);
        secondaryPS.Play();

        yield return new WaitForSeconds(0.8f);
        circlePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        primaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        secondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- ROAR (shockwave ring + fear particles) ----
    private IEnumerator Roar(MonsterAbilityConfig cfg, Color col, Color glow,
                              Vector3 pos)
    {{
        var headPos = pos + Vector3.up * 2.5f;

        // Shockwave ring expanding outward
        wavePS.transform.position = headPos;
        BurstPS(wavePS, 300, new Color(col.r, col.g, col.b, 0.3f),
                cfg.lifetime, 0.5f, 1.2f, 12f, 22f);
        var waveShape = wavePS.shape;
        waveShape.shapeType = ParticleSystemShapeType.Sphere;
        waveShape.radius = 0.3f;
        wavePS.Play();

        // Fear particles (wispy trails outward)
        primaryPS.transform.position = headPos;
        BurstPS(primaryPS, 150, glow * 0.5f, cfg.lifetime * 1.5f,
                0.05f, 0.15f, 8f, 15f);
        primaryPS.Play();

        DoScreenShake(0.5f, 0.3f);
        FlashAbilityLight(headPos, glow, 4f, 0.3f);

        yield return new WaitForSeconds(cfg.lifetime + 0.5f);
        wavePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        primaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- ENRAGE (red pulsing aura + fire particles) ----
    private IEnumerator Enrage(MonsterAbilityConfig cfg, Color col, Color glow,
                                Vector3 pos)
    {{
        // Pulsing aura around body
        auraPS.transform.position = pos + Vector3.up;
        ConfigPS(auraPS, col, cfg.rate * 0.4f, cfg.lifetime, cfg.size,
                 ParticleSystemShapeType.Sphere);
        var auraShape = auraPS.shape;
        auraShape.radius = 1.5f;
        var auraMain = auraPS.main;
        auraMain.startSpeed = new ParticleSystem.MinMaxCurve(0.2f, 0.8f);
        auraPS.Play();

        // Fire / energy particles rising
        primaryPS.transform.position = pos;
        ConfigPS(primaryPS, glow, cfg.rate * 0.6f, cfg.lifetime * 0.6f,
                 cfg.size * 0.5f, ParticleSystemShapeType.Circle);
        var primShape = primaryPS.shape;
        primShape.radius = 1f;
        var primVel = primaryPS.velocityOverLifetime;
        primVel.enabled = true;
        primVel.y = new ParticleSystem.MinMaxCurve(3f, 6f);
        primaryPS.Play();

        // Pulsing light
        FlashAbilityLight(pos + Vector3.up, glow, 3f, cfg.lifetime + 1f);

        yield return new WaitForSeconds(cfg.lifetime + 0.5f);

        // Enrage burst at end
        secondaryPS.transform.position = pos + Vector3.up;
        BurstPS(secondaryPS, 300, glow, 0.4f, 0.1f, 0.5f, 5f, 14f);
        secondaryPS.Play();
        DoScreenShake(0.4f, 0.2f);

        yield return new WaitForSeconds(0.6f);
        auraPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        primaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        secondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ---- Light utility ----
    private void FlashAbilityLight(Vector3 pos, Color color, float intensity, float duration)
    {{
        abilityLight.transform.position = pos;
        abilityLight.color = color;
        abilityLight.enabled = true;
        PrimeTween.Tween.Custom(abilityLight, intensity, 0f, duration: duration,
            onValueChange: (target, val) => target.intensity = val)
            .OnComplete(abilityLight, t => t.enabled = false);
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Monster Ability VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("MonsterAbilityVFXController");
        go.AddComponent<MonsterAbilityVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("MonsterAbilityVFXController created in scene");
    }}

    private static void WriteResult(string msg)
    {{
        var json = JsonUtility.ToJson(new VBResult {{ success = true, message = msg }});
        System.IO.File.WriteAllText(
            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"), json);
    }}

    [System.Serializable]
    private class VBResult {{ public bool success; public string message; }}
#endif
}}
'''

    script_path = "Assets/Editor/Generated/VFX/MonsterAbilityVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }
