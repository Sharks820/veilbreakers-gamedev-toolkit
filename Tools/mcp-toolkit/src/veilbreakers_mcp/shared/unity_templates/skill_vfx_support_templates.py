"""Defensive, healing, summon, and transform skill VFX C# template generators.

Comprehensive VFX library for non-offensive skill categories in VeilBreakers:
  - Defensive skills (20): shields, barriers, armor, wards, cloaks
  - Healing skills (15): restoration, siphon, renewal, aura, purification
  - Summon skills (20): undead, elementals, constructs, familiars, clones
  - Transform skills (15): demon trigger, berserk, shapeshift, ascension

Each function returns a dict with ``script_path``, ``script_content``, and
``next_steps``.  Generated C# uses ParticleSystem (NOT VisualEffect),
PrimeTween (NOT DOTween), C# events (NOT EventBus), and targets Unity
2022.3+ URP with ``Universal Render Pipeline/Particles/Unlit`` shader.

Exports:
    generate_defensive_skill_vfx_script   -- DefensiveSkillVFXController (20 skills)
    generate_healing_skill_vfx_script     -- HealingSkillVFXController (15 skills)
    generate_summon_skill_vfx_script      -- SummonSkillVFXController (20 skills)
    generate_transform_skill_vfx_script   -- TransformSkillVFXController (15 skills)
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

# ---------------------------------------------------------------------------
# Canonical brand color palette -- defined locally to avoid circular imports
# ---------------------------------------------------------------------------

BRAND_PRIMARY_COLORS: dict[str, list[float]] = {
    "IRON":   [0.55, 0.59, 0.65, 1.0],
    "SAVAGE": [0.71, 0.18, 0.18, 1.0],
    "SURGE":  [0.24, 0.55, 0.86, 1.0],
    "VENOM":  [0.31, 0.71, 0.24, 1.0],
    "DREAD":  [0.47, 0.24, 0.63, 1.0],
    "LEECH":  [0.55, 0.16, 0.31, 1.0],
    "GRACE":  [0.86, 0.86, 0.94, 1.0],
    "MEND":   [0.78, 0.67, 0.31, 1.0],
    "RUIN":   [0.86, 0.47, 0.16, 1.0],
    "VOID":   [0.16, 0.08, 0.24, 1.0],
}

BRAND_GLOW_COLORS: dict[str, list[float]] = {
    "IRON":   [0.71, 0.75, 0.80, 1.0],
    "SAVAGE": [0.86, 0.27, 0.27, 1.0],
    "SURGE":  [0.39, 0.71, 1.00, 1.0],
    "VENOM":  [0.47, 0.86, 0.39, 1.0],
    "DREAD":  [0.63, 0.39, 0.78, 1.0],
    "LEECH":  [0.71, 0.24, 0.43, 1.0],
    "GRACE":  [1.00, 1.00, 1.00, 1.0],
    "MEND":   [0.94, 0.82, 0.47, 1.0],
    "RUIN":   [1.00, 0.63, 0.31, 1.0],
    "VOID":   [0.39, 0.24, 0.55, 1.0],
}

ALL_BRANDS = list(BRAND_PRIMARY_COLORS.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_color(rgba: list[float]) -> str:
    """Format RGBA list as C# Color constructor."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _brand_color_dict_cs(var_name: str, color_map: dict[str, list[float]]) -> str:
    """Build C# Dictionary<string, Color> initializer from brand palette."""
    lines = [f"        private static readonly Dictionary<string, Color> {var_name} = new Dictionary<string, Color>"]
    lines.append("        {")
    for brand, rgba in color_map.items():
        lines.append(f'            {{ "{brand}", {_fmt_color(rgba)} }},')
    lines.append("        };")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shared C# code blocks -- particle helpers, screen shake, coroutine delay
# ---------------------------------------------------------------------------

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
            _particleMat.SetFloat("_Surface", 1f);
            _particleMat.SetFloat("_Blend", 0f);
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
            _additiveMat.SetFloat("_Surface", 1f);
            _additiveMat.SetFloat("_Blend", 1f);
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

_CS_WRITE_RESULT = '''
#if UNITY_EDITOR
    private static void WriteResult(string msg)
    {
        var json = JsonUtility.ToJson(new VBResult { success = true, message = msg });
        System.IO.File.WriteAllText(
            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"), json);
    }

    [System.Serializable]
    private class VBResult { public bool success; public string message; }
#endif
'''


# ---------------------------------------------------------------------------
# Defensive skill VFX configuration -- 20 named skills
# ---------------------------------------------------------------------------

DEFENSIVE_SKILL_CONFIGS: dict[str, dict[str, Any]] = {
    "void_barrier": {
        "color": [0.16, 0.08, 0.24, 0.7],
        "glow": [0.39, 0.24, 0.55, 1.0],
        "rate": 120, "lifetime": 1.5, "size": 0.15,
        "shape": "Sphere", "radius": 2.0,
        "burst": 80, "speed": 1.5, "gravity": 0.0,
        "secondary_color": [0.55, 0.35, 0.75, 0.5],
        "desc": "Dark dome shield with void particles and ripple on hit",
    },
    "crystal_ward": {
        "color": [0.7, 0.85, 1.0, 0.8],
        "glow": [0.9, 0.95, 1.0, 1.0],
        "rate": 60, "lifetime": 2.0, "size": 0.2,
        "shape": "Sphere", "radius": 1.5,
        "burst": 30, "speed": 0.8, "gravity": 0.0,
        "secondary_color": [1.0, 1.0, 1.0, 0.6],
        "desc": "Rotating crystal fragments refracting attacks into light",
    },
    "blood_shield": {
        "color": [0.6, 0.02, 0.02, 0.8],
        "glow": [0.8, 0.1, 0.1, 1.0],
        "rate": 80, "lifetime": 1.8, "size": 0.12,
        "shape": "Sphere", "radius": 1.8,
        "burst": 60, "speed": 1.0, "gravity": 0.0,
        "secondary_color": [0.9, 0.2, 0.2, 0.4],
        "desc": "Crimson barrier with heartbeat pulse and red mist absorb",
    },
    "frost_armor": {
        "color": [0.5, 0.8, 1.0, 0.9],
        "glow": [0.7, 0.9, 1.0, 1.0],
        "rate": 50, "lifetime": 2.5, "size": 0.06,
        "shape": "Sphere", "radius": 0.8,
        "burst": 40, "speed": 0.3, "gravity": 0.1,
        "secondary_color": [0.85, 0.95, 1.0, 0.5],
        "desc": "Ice crystallizes across model, cracks on damage",
    },
    "iron_skin": {
        "color": [0.55, 0.59, 0.65, 1.0],
        "glow": [0.71, 0.75, 0.80, 1.0],
        "rate": 40, "lifetime": 3.0, "size": 0.04,
        "shape": "Sphere", "radius": 0.6,
        "burst": 20, "speed": 0.2, "gravity": 0.0,
        "secondary_color": [0.9, 0.9, 0.95, 0.3],
        "desc": "Metallic sheen spreads across body with steel glow",
    },
    "divine_shield": {
        "color": [1.0, 0.9, 0.5, 0.7],
        "glow": [1.0, 1.0, 0.8, 1.0],
        "rate": 100, "lifetime": 1.5, "size": 0.18,
        "shape": "Sphere", "radius": 2.2,
        "burst": 100, "speed": 1.0, "gravity": -0.2,
        "secondary_color": [1.0, 1.0, 1.0, 0.6],
        "desc": "Golden dome with warm light and invulnerability glow",
    },
    "bone_cage": {
        "color": [0.85, 0.82, 0.75, 0.9],
        "glow": [0.6, 0.9, 0.3, 1.0],
        "rate": 45, "lifetime": 2.0, "size": 0.1,
        "shape": "Circle", "radius": 1.5,
        "burst": 50, "speed": 2.5, "gravity": -0.8,
        "secondary_color": [0.3, 0.7, 0.15, 0.5],
        "desc": "Skeletal ribcage shield that cracks and regenerates on hit",
    },
    "shadow_cloak": {
        "color": [0.1, 0.08, 0.15, 0.6],
        "glow": [0.25, 0.18, 0.35, 0.8],
        "rate": 90, "lifetime": 2.0, "size": 0.25,
        "shape": "Sphere", "radius": 0.7,
        "burst": 40, "speed": 0.5, "gravity": -0.1,
        "secondary_color": [0.15, 0.1, 0.2, 0.3],
        "desc": "Dark smoke wreath providing semi-transparent damage reduction",
    },
    "parry_flash": {
        "color": [1.0, 1.0, 1.0, 1.0],
        "glow": [1.0, 1.0, 0.9, 1.0],
        "rate": 500, "lifetime": 0.15, "size": 0.3,
        "shape": "Sphere", "radius": 0.5,
        "burst": 200, "speed": 8.0, "gravity": 0.0,
        "secondary_color": [0.9, 0.9, 1.0, 0.8],
        "desc": "White flash with time-slow and counter window indicator",
    },
    "earth_bulwark": {
        "color": [0.55, 0.4, 0.25, 1.0],
        "glow": [0.7, 0.55, 0.35, 1.0],
        "rate": 150, "lifetime": 1.0, "size": 0.2,
        "shape": "Circle", "radius": 2.5,
        "burst": 120, "speed": 6.0, "gravity": -2.0,
        "secondary_color": [0.4, 0.3, 0.2, 0.7],
        "desc": "Stone wall erupting from ground that cracks and crumbles",
    },
    "wind_wall": {
        "color": [0.8, 0.9, 1.0, 0.4],
        "glow": [0.9, 0.95, 1.0, 0.7],
        "rate": 200, "lifetime": 0.8, "size": 0.08,
        "shape": "Box", "radius": 3.0,
        "burst": 60, "speed": 12.0, "gravity": 0.0,
        "secondary_color": [1.0, 1.0, 1.0, 0.2],
        "desc": "Air current barrier deflecting projectiles with wind streaks",
    },
    "spirit_guard": {
        "color": [0.5, 0.75, 1.0, 0.6],
        "glow": [0.7, 0.9, 1.0, 0.9],
        "rate": 35, "lifetime": 3.0, "size": 0.3,
        "shape": "Circle", "radius": 1.8,
        "burst": 15, "speed": 2.0, "gravity": -0.3,
        "secondary_color": [0.6, 0.8, 1.0, 0.4],
        "desc": "Ghostly familiar orbiting and intercepting attacks",
    },
    "corruption_shell": {
        "color": [0.2, 0.05, 0.15, 0.9],
        "glow": [0.4, 0.1, 0.3, 1.0],
        "rate": 70, "lifetime": 2.5, "size": 0.1,
        "shape": "Sphere", "radius": 0.9,
        "burst": 50, "speed": 0.4, "gravity": 0.0,
        "secondary_color": [0.5, 0.15, 0.3, 0.6],
        "desc": "Dark organic carapace with pulsing veins",
    },
    "reflect_barrier": {
        "color": [0.9, 0.9, 1.0, 0.5],
        "glow": [1.0, 1.0, 1.0, 1.0],
        "rate": 80, "lifetime": 1.0, "size": 0.12,
        "shape": "Sphere", "radius": 2.0,
        "burst": 150, "speed": 5.0, "gravity": 0.0,
        "secondary_color": [0.8, 0.6, 1.0, 0.6],
        "desc": "Mirror surface bouncing projectiles back with prismatic flash",
    },
    "thorn_mantle": {
        "color": [0.2, 0.5, 0.1, 0.9],
        "glow": [0.4, 0.7, 0.2, 1.0],
        "rate": 55, "lifetime": 2.0, "size": 0.08,
        "shape": "Sphere", "radius": 0.8,
        "burst": 35, "speed": 0.6, "gravity": 0.1,
        "secondary_color": [0.8, 0.1, 0.1, 0.7],
        "desc": "Thorny vine covering, attackers take red thorn flash",
    },
    "phase_shift": {
        "color": [0.6, 0.7, 1.0, 0.3],
        "glow": [0.8, 0.85, 1.0, 0.6],
        "rate": 100, "lifetime": 0.8, "size": 0.15,
        "shape": "Sphere", "radius": 0.7,
        "burst": 80, "speed": 2.0, "gravity": 0.0,
        "secondary_color": [0.7, 0.8, 1.0, 0.2],
        "desc": "Semi-transparent shimmer where attacks pass through",
    },
    "runic_ward": {
        "color": [0.4, 0.5, 0.9, 0.8],
        "glow": [0.6, 0.7, 1.0, 1.0],
        "rate": 65, "lifetime": 2.5, "size": 0.2,
        "shape": "Circle", "radius": 1.5,
        "burst": 40, "speed": 1.5, "gravity": -0.2,
        "secondary_color": [0.5, 0.6, 1.0, 0.5],
        "desc": "Floating rune shield orbit that intensifies before breaking",
    },
    "magnetic_field": {
        "color": [0.6, 0.6, 0.7, 0.7],
        "glow": [0.8, 0.8, 0.9, 1.0],
        "rate": 150, "lifetime": 1.0, "size": 0.05,
        "shape": "Sphere", "radius": 2.5,
        "burst": 100, "speed": 3.0, "gravity": 0.0,
        "secondary_color": [0.7, 0.7, 0.8, 0.5],
        "desc": "Metal particle sphere deflecting physical attacks",
    },
    "soul_shroud": {
        "color": [0.4, 0.6, 0.9, 0.5],
        "glow": [0.6, 0.8, 1.0, 0.8],
        "rate": 50, "lifetime": 3.0, "size": 0.18,
        "shape": "Sphere", "radius": 1.0,
        "burst": 25, "speed": 0.8, "gravity": -0.15,
        "secondary_color": [0.5, 0.7, 1.0, 0.3],
        "desc": "Soul wisps in protective swirl forming ghostly veil",
    },
    "mending_bark": {
        "color": [0.4, 0.3, 0.15, 0.9],
        "glow": [0.3, 0.6, 0.15, 1.0],
        "rate": 40, "lifetime": 3.0, "size": 0.08,
        "shape": "Sphere", "radius": 0.7,
        "burst": 30, "speed": 0.3, "gravity": -0.1,
        "secondary_color": [0.3, 0.7, 0.2, 0.5],
        "desc": "Tree bark growing over body with leaf particles",
    },
}


# ---------------------------------------------------------------------------
# Healing skill VFX configuration -- 15 named skills
# ---------------------------------------------------------------------------

HEALING_SKILL_CONFIGS: dict[str, dict[str, Any]] = {
    "restorative_bloom": {
        "color": [0.3, 0.8, 0.2, 0.8],
        "glow": [0.6, 1.0, 0.4, 1.0],
        "rate": 80, "lifetime": 2.0, "size": 0.15,
        "shape": "Sphere", "radius": 1.5,
        "burst": 60, "speed": 1.5, "gravity": -0.5,
        "secondary_color": [0.9, 0.85, 0.4, 0.6],
        "desc": "Green-gold flower with petals rising and warm glow",
    },
    "blood_siphon": {
        "color": [0.7, 0.02, 0.02, 0.9],
        "glow": [0.9, 0.15, 0.15, 1.0],
        "rate": 100, "lifetime": 1.2, "size": 0.08,
        "shape": "Cone", "radius": 0.5,
        "burst": 40, "speed": 6.0, "gravity": 0.0,
        "secondary_color": [0.5, 0.0, 0.0, 0.7],
        "desc": "Red tendrils from enemy to caster with visible life flow",
    },
    "phoenix_renewal": {
        "color": [1.0, 0.5, 0.1, 1.0],
        "glow": [1.0, 0.85, 0.3, 1.0],
        "rate": 150, "lifetime": 1.5, "size": 0.2,
        "shape": "Cone", "radius": 1.0,
        "burst": 120, "speed": 4.0, "gravity": -1.0,
        "secondary_color": [1.0, 0.9, 0.5, 0.7],
        "desc": "Flame wings transition from fire to healing warmth orange-to-gold",
    },
    "sacred_rain": {
        "color": [1.0, 0.9, 0.5, 0.6],
        "glow": [1.0, 1.0, 0.8, 1.0],
        "rate": 60, "lifetime": 2.5, "size": 0.04,
        "shape": "Box", "radius": 4.0,
        "burst": 80, "speed": 3.0, "gravity": 1.5,
        "secondary_color": [1.0, 1.0, 0.9, 0.4],
        "desc": "Golden light drops with sparkle particles from above",
    },
    "spirit_mend": {
        "color": [0.5, 0.8, 1.0, 0.6],
        "glow": [0.7, 0.9, 1.0, 0.9],
        "rate": 25, "lifetime": 3.0, "size": 0.15,
        "shape": "Circle", "radius": 3.0,
        "burst": 15, "speed": 3.0, "gravity": -0.3,
        "secondary_color": [0.6, 0.85, 1.0, 0.4],
        "desc": "Ghost butterflies fly to allies and dissolve into heal",
    },
    "regen_aura": {
        "color": [0.2, 0.8, 0.3, 0.5],
        "glow": [0.4, 1.0, 0.5, 0.8],
        "rate": 70, "lifetime": 1.8, "size": 0.1,
        "shape": "Circle", "radius": 3.5,
        "burst": 50, "speed": 2.0, "gravity": 0.0,
        "secondary_color": [0.3, 0.9, 0.4, 0.3],
        "desc": "Green circular pulse with rhythmic healing wave",
    },
    "vampiric_feast": {
        "color": [0.5, 0.0, 0.05, 0.9],
        "glow": [0.7, 0.1, 0.15, 1.0],
        "rate": 130, "lifetime": 1.5, "size": 0.1,
        "shape": "Sphere", "radius": 5.0,
        "burst": 100, "speed": 5.0, "gravity": 0.0,
        "secondary_color": [0.8, 0.15, 0.2, 0.5],
        "desc": "Dark red from all nearby enemies with crimson mist",
    },
    "natures_embrace": {
        "color": [0.2, 0.6, 0.1, 0.8],
        "glow": [0.4, 0.8, 0.2, 1.0],
        "rate": 45, "lifetime": 2.5, "size": 0.12,
        "shape": "Circle", "radius": 1.5,
        "burst": 35, "speed": 0.8, "gravity": -0.3,
        "secondary_color": [0.9, 0.8, 0.3, 0.5],
        "desc": "Vine tendrils with flowers blooming and releasing pollen",
    },
    "soul_harvest": {
        "color": [0.5, 0.6, 1.0, 0.7],
        "glow": [0.7, 0.8, 1.0, 1.0],
        "rate": 40, "lifetime": 2.0, "size": 0.12,
        "shape": "Sphere", "radius": 4.0,
        "burst": 30, "speed": 4.0, "gravity": 0.0,
        "secondary_color": [0.8, 0.85, 1.0, 0.5],
        "desc": "Blue-white wisps from fallen absorbed with glow",
    },
    "purifying_light": {
        "color": [1.0, 1.0, 0.9, 0.8],
        "glow": [1.0, 1.0, 1.0, 1.0],
        "rate": 120, "lifetime": 1.5, "size": 0.15,
        "shape": "Cone", "radius": 0.8,
        "burst": 100, "speed": 5.0, "gravity": -1.5,
        "secondary_color": [0.2, 0.1, 0.3, 0.6],
        "desc": "White-gold column removing debuffs with dark particles rising",
    },
    "corruption_drain": {
        "color": [0.5, 0.15, 0.6, 0.8],
        "glow": [0.7, 0.3, 0.8, 1.0],
        "rate": 60, "lifetime": 1.8, "size": 0.1,
        "shape": "Cone", "radius": 0.5,
        "burst": 45, "speed": 3.0, "gravity": -1.0,
        "secondary_color": [0.6, 0.2, 0.7, 0.5],
        "desc": "Purple particles extracted from ally rising upward",
    },
    "tidal_restoration": {
        "color": [0.1, 0.5, 0.6, 0.7],
        "glow": [0.2, 0.7, 0.8, 1.0],
        "rate": 100, "lifetime": 2.0, "size": 0.2,
        "shape": "Circle", "radius": 3.0,
        "burst": 70, "speed": 2.5, "gravity": 0.3,
        "secondary_color": [0.3, 0.7, 0.75, 0.4],
        "desc": "Water washing over from ground with blue-green flow",
    },
    "bone_knit": {
        "color": [0.85, 0.8, 0.7, 0.9],
        "glow": [0.95, 0.9, 0.8, 1.0],
        "rate": 50, "lifetime": 1.5, "size": 0.06,
        "shape": "Sphere", "radius": 0.5,
        "burst": 40, "speed": 0.5, "gravity": 0.0,
        "secondary_color": [0.9, 0.6, 0.5, 0.6],
        "desc": "Visible bone and flesh mending with skeletal repair particles",
    },
    "moonlit_recovery": {
        "color": [0.7, 0.75, 0.9, 0.6],
        "glow": [0.85, 0.9, 1.0, 0.9],
        "rate": 35, "lifetime": 3.0, "size": 0.1,
        "shape": "Cone", "radius": 1.0,
        "burst": 25, "speed": 1.5, "gravity": -0.4,
        "secondary_color": [0.8, 0.82, 0.95, 0.4],
        "desc": "Silver moonlight beam with gentle silver particles",
    },
    "heartbeat_pulse": {
        "color": [0.8, 0.1, 0.1, 0.8],
        "glow": [1.0, 0.3, 0.3, 1.0],
        "rate": 90, "lifetime": 0.8, "size": 0.2,
        "shape": "Sphere", "radius": 1.0,
        "burst": 80, "speed": 3.0, "gravity": 0.0,
        "secondary_color": [1.0, 0.5, 0.5, 0.5],
        "desc": "Red pulse from chest with rhythmic HP restore wave",
    },
}


# ---------------------------------------------------------------------------
# Summon skill VFX configuration -- 20 named skills
# ---------------------------------------------------------------------------

SUMMON_SKILL_CONFIGS: dict[str, dict[str, Any]] = {
    "skeletal_rising": {
        "color": [0.3, 0.7, 0.15, 0.8],
        "glow": [0.5, 0.9, 0.3, 1.0],
        "rate": 80, "lifetime": 2.0, "size": 0.15,
        "shape": "Circle", "radius": 2.0,
        "burst": 100, "speed": 2.0, "gravity": -1.5,
        "secondary_color": [0.8, 0.75, 0.65, 0.7],
        "desc": "Bony hands from cracking ground with green necro fog",
    },
    "draconic_summon": {
        "color": [0.8, 0.3, 0.05, 1.0],
        "glow": [1.0, 0.5, 0.1, 1.0],
        "rate": 200, "lifetime": 1.5, "size": 0.25,
        "shape": "Circle", "radius": 3.0,
        "burst": 250, "speed": 8.0, "gravity": -2.0,
        "secondary_color": [1.0, 0.7, 0.2, 0.8],
        "desc": "Magic circle with energy pillar as dragon materializes",
    },
    "phoenix_rebirth": {
        "color": [1.0, 0.5, 0.05, 1.0],
        "glow": [1.0, 0.8, 0.2, 1.0],
        "rate": 250, "lifetime": 1.2, "size": 0.2,
        "shape": "Sphere", "radius": 2.0,
        "burst": 200, "speed": 6.0, "gravity": -0.8,
        "secondary_color": [1.0, 0.9, 0.4, 0.6],
        "desc": "Flame burst phoenix silhouette with feathers scattering",
    },
    "familiar_bond": {
        "color": [1.0, 0.7, 0.8, 0.7],
        "glow": [1.0, 0.85, 0.9, 1.0],
        "rate": 40, "lifetime": 2.5, "size": 0.12,
        "shape": "Sphere", "radius": 0.5,
        "burst": 30, "speed": 2.0, "gravity": -0.3,
        "secondary_color": [1.0, 0.8, 0.6, 0.5],
        "desc": "Heart energy from chest with warm glow creature forming",
    },
    "shadow_clone": {
        "color": [0.1, 0.08, 0.15, 0.8],
        "glow": [0.25, 0.2, 0.35, 1.0],
        "rate": 100, "lifetime": 0.8, "size": 0.3,
        "shape": "Box", "radius": 0.8,
        "burst": 80, "speed": 1.5, "gravity": 0.0,
        "secondary_color": [0.15, 0.1, 0.2, 0.5],
        "desc": "Dark afterimage separates into autonomous duplicate",
    },
    "spectre_raise": {
        "color": [0.3, 0.7, 0.6, 0.5],
        "glow": [0.5, 0.9, 0.8, 0.8],
        "rate": 60, "lifetime": 2.5, "size": 0.18,
        "shape": "Cone", "radius": 1.0,
        "burst": 50, "speed": 1.5, "gravity": -0.5,
        "secondary_color": [0.4, 0.8, 0.7, 0.3],
        "desc": "Ghostly blue-green on corpse as translucent spectre rises",
    },
    "totem_plant": {
        "color": [0.5, 0.35, 0.15, 1.0],
        "glow": [0.7, 0.5, 0.2, 1.0],
        "rate": 70, "lifetime": 1.5, "size": 0.1,
        "shape": "Cone", "radius": 0.5,
        "burst": 90, "speed": 5.0, "gravity": 0.5,
        "secondary_color": [0.4, 0.6, 0.9, 0.7],
        "desc": "Wooden totem slams down with glowing runes and area effect",
    },
    "golem_forge": {
        "color": [0.55, 0.4, 0.25, 1.0],
        "glow": [0.8, 0.6, 0.3, 1.0],
        "rate": 120, "lifetime": 2.0, "size": 0.2,
        "shape": "Sphere", "radius": 2.5,
        "burst": 150, "speed": 3.0, "gravity": 0.5,
        "secondary_color": [0.6, 0.02, 0.02, 0.7],
        "desc": "Earth, bones, and blood coalesce into construct",
    },
    "spirit_wolf_pack": {
        "color": [0.3, 0.8, 0.5, 0.6],
        "glow": [0.5, 1.0, 0.7, 0.9],
        "rate": 55, "lifetime": 2.0, "size": 0.15,
        "shape": "Circle", "radius": 3.0,
        "burst": 40, "speed": 4.0, "gravity": 0.0,
        "secondary_color": [0.4, 0.9, 0.6, 0.4],
        "desc": "Ghostly wolves materialize from green mist, howl and hunt",
    },
    "drone_deploy": {
        "color": [0.3, 0.6, 0.9, 0.9],
        "glow": [0.5, 0.8, 1.0, 1.0],
        "rate": 80, "lifetime": 1.0, "size": 0.06,
        "shape": "Sphere", "radius": 0.5,
        "burst": 60, "speed": 3.0, "gravity": -0.5,
        "secondary_color": [0.2, 0.5, 0.8, 0.6],
        "desc": "Mechanical drones activate with tech-energy links",
    },
    "corruption_spawn": {
        "color": [0.2, 0.05, 0.1, 1.0],
        "glow": [0.4, 0.1, 0.25, 1.0],
        "rate": 100, "lifetime": 2.0, "size": 0.2,
        "shape": "Sphere", "radius": 1.5,
        "burst": 120, "speed": 1.5, "gravity": 0.3,
        "secondary_color": [0.5, 0.15, 0.3, 0.7],
        "desc": "Dark organic mass from which creature tears free",
    },
    "captured_monster_release": {
        "color": [0.8, 0.85, 1.0, 0.8],
        "glow": [1.0, 1.0, 1.0, 1.0],
        "rate": 150, "lifetime": 1.0, "size": 0.15,
        "shape": "Sphere", "radius": 1.0,
        "burst": 200, "speed": 6.0, "gravity": 0.0,
        "secondary_color": [0.6, 0.7, 1.0, 0.5],
        "desc": "Sphere opens as creature materializes with energy burst",
    },
    "turret_construct": {
        "color": [0.4, 0.5, 0.6, 0.9],
        "glow": [0.6, 0.7, 0.8, 1.0],
        "rate": 90, "lifetime": 1.2, "size": 0.08,
        "shape": "Cone", "radius": 0.8,
        "burst": 70, "speed": 2.5, "gravity": -1.0,
        "secondary_color": [0.5, 0.6, 0.7, 0.6],
        "desc": "Turret assembles from energy and auto-targets enemies",
    },
    "plague_swarm": {
        "color": [0.15, 0.15, 0.1, 0.9],
        "glow": [0.3, 0.35, 0.2, 1.0],
        "rate": 200, "lifetime": 1.5, "size": 0.04,
        "shape": "Sphere", "radius": 2.0,
        "burst": 300, "speed": 5.0, "gravity": 0.0,
        "secondary_color": [0.2, 0.25, 0.1, 0.7],
        "desc": "Dark insect cloud dispersing to attack targets",
    },
    "mirror_image": {
        "color": [0.7, 0.8, 1.0, 0.5],
        "glow": [0.9, 0.95, 1.0, 0.8],
        "rate": 80, "lifetime": 0.6, "size": 0.2,
        "shape": "Sphere", "radius": 0.6,
        "burst": 100, "speed": 3.0, "gravity": 0.0,
        "secondary_color": [0.8, 0.85, 1.0, 0.3],
        "desc": "Prismatic split producing 2-3 illusory copies",
    },
    "bone_sentinel": {
        "color": [0.8, 0.78, 0.7, 0.9],
        "glow": [0.3, 0.9, 0.2, 1.0],
        "rate": 70, "lifetime": 2.0, "size": 0.12,
        "shape": "Circle", "radius": 1.5,
        "burst": 80, "speed": 2.5, "gravity": -1.0,
        "secondary_color": [0.2, 0.7, 0.1, 0.7],
        "desc": "Skeletal knight assembles with green-fire eyes",
    },
    "elemental_spirit": {
        "color": [0.3, 0.6, 1.0, 0.8],
        "glow": [0.5, 0.8, 1.0, 1.0],
        "rate": 130, "lifetime": 1.8, "size": 0.15,
        "shape": "Sphere", "radius": 1.5,
        "burst": 100, "speed": 2.5, "gravity": 0.0,
        "secondary_color": [1.0, 0.5, 0.1, 0.6],
        "desc": "Pure element coalesces into creature form",
    },
    "vine_treant": {
        "color": [0.25, 0.5, 0.1, 0.9],
        "glow": [0.4, 0.7, 0.2, 1.0],
        "rate": 60, "lifetime": 2.5, "size": 0.15,
        "shape": "Cone", "radius": 1.5,
        "burst": 80, "speed": 3.0, "gravity": -1.5,
        "secondary_color": [0.5, 0.35, 0.15, 0.7],
        "desc": "Tree grows from ground and becomes guardian treant",
    },
    "blood_familiar": {
        "color": [0.5, 0.0, 0.02, 0.9],
        "glow": [0.7, 0.1, 0.1, 1.0],
        "rate": 90, "lifetime": 2.0, "size": 0.12,
        "shape": "Circle", "radius": 1.0,
        "burst": 70, "speed": 1.5, "gravity": -0.5,
        "secondary_color": [0.8, 0.15, 0.15, 0.6],
        "desc": "Blood pools and rises into creature shape",
    },
    "sword_constellation": {
        "color": [0.6, 0.7, 1.0, 0.8],
        "glow": [0.8, 0.9, 1.0, 1.0],
        "rate": 50, "lifetime": 3.0, "size": 0.1,
        "shape": "Circle", "radius": 2.0,
        "burst": 30, "speed": 1.0, "gravity": -0.2,
        "secondary_color": [0.7, 0.8, 1.0, 0.5],
        "desc": "Spectral swords form in orbit around caster",
    },
}


# ---------------------------------------------------------------------------
# Transform skill VFX configuration -- 15 named skills
# ---------------------------------------------------------------------------

TRANSFORM_SKILL_CONFIGS: dict[str, dict[str, Any]] = {
    "demon_trigger": {
        "color": [0.3, 0.0, 0.1, 1.0],
        "glow": [0.8, 0.15, 0.2, 1.0],
        "rate": 200, "lifetime": 1.5, "size": 0.2,
        "shape": "Sphere", "radius": 1.5,
        "burst": 250, "speed": 5.0, "gravity": -0.5,
        "secondary_color": [0.1, 0.0, 0.05, 0.8],
        "persistent_rate": 60, "persistent_size": 0.1,
        "desc": "Dark energy erupts, horns/wings/claws with persistent aura",
    },
    "berserk_rage": {
        "color": [0.8, 0.1, 0.05, 1.0],
        "glow": [1.0, 0.2, 0.1, 1.0],
        "rate": 180, "lifetime": 1.0, "size": 0.15,
        "shape": "Sphere", "radius": 1.0,
        "burst": 200, "speed": 4.0, "gravity": -0.3,
        "secondary_color": [1.0, 0.3, 0.1, 0.7],
        "persistent_rate": 80, "persistent_size": 0.08,
        "desc": "Red veins visible, character grows, eyes glow red",
    },
    "werebeast_shift": {
        "color": [0.5, 0.35, 0.15, 0.9],
        "glow": [0.7, 0.5, 0.2, 1.0],
        "rate": 150, "lifetime": 1.2, "size": 0.12,
        "shape": "Sphere", "radius": 1.2,
        "burst": 180, "speed": 3.0, "gravity": 0.2,
        "secondary_color": [0.6, 0.4, 0.2, 0.6],
        "persistent_rate": 40, "persistent_size": 0.06,
        "desc": "Fur and features rapidly grow with bone cracking bestial burst",
    },
    "corruption_embrace": {
        "color": [0.15, 0.05, 0.2, 1.0],
        "glow": [0.35, 0.1, 0.45, 1.0],
        "rate": 120, "lifetime": 2.0, "size": 0.15,
        "shape": "Sphere", "radius": 1.0,
        "burst": 150, "speed": 2.0, "gravity": 0.0,
        "secondary_color": [0.25, 0.08, 0.3, 0.7],
        "persistent_rate": 50, "persistent_size": 0.1,
        "desc": "Dark tendrils wrap, absorbed into skin with void particles",
    },
    "elemental_avatar": {
        "color": [0.3, 0.6, 1.0, 0.9],
        "glow": [0.5, 0.8, 1.0, 1.0],
        "rate": 250, "lifetime": 1.5, "size": 0.18,
        "shape": "Sphere", "radius": 1.0,
        "burst": 300, "speed": 4.0, "gravity": 0.0,
        "secondary_color": [1.0, 0.5, 0.1, 0.8],
        "persistent_rate": 120, "persistent_size": 0.12,
        "desc": "Becomes living element with fire/ice/lightning body",
    },
    "spirit_possession": {
        "color": [0.4, 0.6, 0.9, 0.6],
        "glow": [0.6, 0.8, 1.0, 0.9],
        "rate": 80, "lifetime": 2.0, "size": 0.2,
        "shape": "Sphere", "radius": 1.5,
        "burst": 100, "speed": 3.0, "gravity": 0.0,
        "secondary_color": [0.5, 0.7, 1.0, 0.4],
        "persistent_rate": 30, "persistent_size": 0.15,
        "desc": "Ghost enters character, eyes change with spirit overlay",
    },
    "dragon_form": {
        "color": [0.8, 0.4, 0.05, 1.0],
        "glow": [1.0, 0.6, 0.1, 1.0],
        "rate": 200, "lifetime": 1.5, "size": 0.2,
        "shape": "Sphere", "radius": 2.0,
        "burst": 250, "speed": 5.0, "gravity": -0.5,
        "secondary_color": [0.9, 0.5, 0.1, 0.7],
        "persistent_rate": 70, "persistent_size": 0.1,
        "desc": "Scales grow, wings manifest with draconic features",
    },
    "nahobino_awakening": {
        "color": [0.9, 0.85, 0.5, 0.9],
        "glow": [1.0, 1.0, 0.7, 1.0],
        "rate": 250, "lifetime": 1.5, "size": 0.2,
        "shape": "Sphere", "radius": 2.0,
        "burst": 300, "speed": 6.0, "gravity": -0.8,
        "secondary_color": [1.0, 0.95, 0.8, 0.6],
        "persistent_rate": 50, "persistent_size": 0.12,
        "desc": "Divine fusion energy cocoon shattering into new form",
    },
    "evolved_form": {
        "color": [0.6, 0.7, 1.0, 0.8],
        "glow": [0.8, 0.9, 1.0, 1.0],
        "rate": 160, "lifetime": 1.5, "size": 0.15,
        "shape": "Sphere", "radius": 1.5,
        "burst": 180, "speed": 4.0, "gravity": 0.0,
        "secondary_color": [0.7, 0.8, 1.0, 0.5],
        "persistent_rate": 45, "persistent_size": 0.08,
        "desc": "Monster glows and silhouette shifts to larger version",
    },
    "shadow_hunter": {
        "color": [0.08, 0.05, 0.12, 1.0],
        "glow": [0.2, 0.15, 0.3, 1.0],
        "rate": 130, "lifetime": 1.8, "size": 0.2,
        "shape": "Sphere", "radius": 1.0,
        "burst": 150, "speed": 3.0, "gravity": -0.3,
        "secondary_color": [0.15, 0.1, 0.2, 0.7],
        "persistent_rate": 55, "persistent_size": 0.12,
        "desc": "Melds into shadow, dark version rises with demon wings",
    },
    "blood_lord": {
        "color": [0.5, 0.0, 0.02, 1.0],
        "glow": [0.8, 0.1, 0.1, 1.0],
        "rate": 170, "lifetime": 1.5, "size": 0.15,
        "shape": "Sphere", "radius": 1.5,
        "burst": 200, "speed": 4.0, "gravity": 0.2,
        "secondary_color": [0.6, 0.02, 0.05, 0.8],
        "persistent_rate": 65, "persistent_size": 0.1,
        "desc": "Crimson transform with blood armor from absorbed blood",
    },
    "sin_devil_trigger": {
        "color": [0.15, 0.0, 0.08, 1.0],
        "glow": [0.6, 0.1, 0.2, 1.0],
        "rate": 300, "lifetime": 2.0, "size": 0.25,
        "shape": "Sphere", "radius": 2.5,
        "burst": 400, "speed": 7.0, "gravity": -0.5,
        "secondary_color": [0.3, 0.05, 0.15, 0.9],
        "persistent_rate": 90, "persistent_size": 0.15,
        "desc": "Ultimate dark wings/armor with reality-warp aura",
    },
    "mega_evolution": {
        "color": [0.8, 0.3, 1.0, 0.9],
        "glow": [1.0, 0.5, 1.0, 1.0],
        "rate": 250, "lifetime": 1.2, "size": 0.18,
        "shape": "Sphere", "radius": 2.0,
        "burst": 300, "speed": 6.0, "gravity": -0.5,
        "secondary_color": [0.5, 0.8, 0.2, 0.7],
        "persistent_rate": 60, "persistent_size": 0.1,
        "desc": "Keystone activates with rainbow energy and explosive form",
    },
    "corruption_overload": {
        "color": [0.1, 0.02, 0.15, 1.0],
        "glow": [0.45, 0.15, 0.55, 1.0],
        "rate": 220, "lifetime": 2.0, "size": 0.2,
        "shape": "Sphere", "radius": 1.5,
        "burst": 250, "speed": 4.0, "gravity": 0.0,
        "secondary_color": [0.3, 0.08, 0.4, 0.8],
        "persistent_rate": 100, "persistent_size": 0.12,
        "desc": "Too much corruption, body cracks with dark energy leaking",
    },
    "brand_ascension": {
        "color": [0.78, 0.67, 0.31, 1.0],
        "glow": [0.94, 0.82, 0.47, 1.0],
        "rate": 200, "lifetime": 1.8, "size": 0.2,
        "shape": "Sphere", "radius": 2.0,
        "burst": 250, "speed": 5.0, "gravity": -0.5,
        "secondary_color": [1.0, 0.9, 0.6, 0.7],
        "persistent_rate": 70, "persistent_size": 0.12,
        "desc": "Brand mark expands into full-body elemental brand manifestation",
    },
}


# ---------------------------------------------------------------------------
# C# config dict builders
# ---------------------------------------------------------------------------

def _build_skill_configs_cs(
    configs: dict[str, dict[str, Any]],
    struct_name: str,
    var_name: str,
    *,
    include_persistent: bool = False,
) -> str:
    """Build a C# Dictionary<string, SkillConfig> from Python config dict."""
    lines: list[str] = []
    lines.append(f"        private static readonly Dictionary<string, {struct_name}> {var_name} = new Dictionary<string, {struct_name}>")
    lines.append("        {")
    for name, cfg in configs.items():
        c = cfg["color"]
        g = cfg["glow"]
        sc = cfg["secondary_color"]
        lines.append(f'            {{ "{sanitize_cs_string(name)}", new {struct_name} {{')
        lines.append(f"                color = {_fmt_color(c)},")
        lines.append(f"                glow = {_fmt_color(g)},")
        lines.append(f"                secondaryColor = {_fmt_color(sc)},")
        lines.append(f"                rate = {cfg['rate']}, lifetime = {cfg['lifetime']}f,")
        lines.append(f"                size = {cfg['size']}f, speed = {cfg['speed']}f,")
        lines.append(f"                burst = {cfg['burst']}, radius = {cfg['radius']}f,")
        lines.append(f"                gravity = {cfg['gravity']}f,")
        if include_persistent:
            pr = cfg.get("persistent_rate", 40)
            ps = cfg.get("persistent_size", 0.08)
            lines.append(f"                persistentRate = {pr}, persistentSize = {ps}f,")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


# ===================================================================
# 1. generate_defensive_skill_vfx_script
# ===================================================================


def generate_defensive_skill_vfx_script(skill_name: str = "void_barrier") -> dict[str, Any]:
    """Generate DefensiveSkillVFXController MonoBehaviour for 20 defensive skills.

    Each skill creates a shield/barrier/armor VFX with activate, sustain, hit-react,
    and deactivate phases. Config-driven with shared particle helpers.

    Args:
        skill_name: Default active skill. One of 20 defensive skills.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    skill_name = skill_name.lower().replace(" ", "_")
    if skill_name not in DEFENSIVE_SKILL_CONFIGS:
        skill_name = "void_barrier"

    safe_name = sanitize_cs_identifier(skill_name)
    configs_block = _build_skill_configs_cs(
        DEFENSIVE_SKILL_CONFIGS, "DefenseConfig", "DefenseConfigs",
    )

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Defensive skill VFX controller for VeilBreakers -- 20 named defensive skills.
/// Each skill has 4 phases: activate (flash/burst), sustain (looping shield),
/// hit-react (on-damage ripple), and deactivate (shatter/fade).
/// Default: {skill_name}
/// API: ActivateDefense(skillName) / DeactivateDefense() / OnHitReact(hitDir)
/// </summary>
public class DefensiveSkillVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct DefenseConfig
    {{
        public Color color;
        public Color glow;
        public Color secondaryColor;
        public int rate;
        public float lifetime;
        public float size;
        public float speed;
        public int burst;
        public float radius;
        public float gravity;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSkill = "{skill_name}";
    [SerializeField] private float shieldDuration = 8f;

    // Events
    public event Action<string> OnDefenseActivated;
    public event Action<string> OnDefenseDeactivated;
    public event Action<string, Vector3> OnDefenseHitReact;

{configs_block}

    // Runtime particle systems
    private ParticleSystem shieldCorePS;
    private ParticleSystem shieldGlowPS;
    private ParticleSystem shieldSecondaryPS;
    private ParticleSystem activateBurstPS;
    private ParticleSystem hitReactPS;
    private ParticleSystem deactivateShatterPS;
    private Light shieldLight;

    private string activeSkill;
    private Coroutine sustainRoutine;
    private bool isActive;
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
        shieldCorePS = CreatePS("DefShieldCore", root, 1000);
        shieldGlowPS = CreatePS("DefShieldGlow", root, 500);
        shieldSecondaryPS = CreatePS("DefShieldSecondary", root, 300);
        activateBurstPS = CreatePS("DefActivateBurst", root, 800);
        hitReactPS = CreatePS("DefHitReact", root, 600);
        deactivateShatterPS = CreatePS("DefDeactivateShatter", root, 800);

        // Shield glow uses additive
        var glowRenderer = shieldGlowPS.GetComponent<ParticleSystemRenderer>();
        glowRenderer.material = GetAdditiveMaterial();
        var activateRenderer = activateBurstPS.GetComponent<ParticleSystemRenderer>();
        activateRenderer.material = GetAdditiveMaterial();

        var lightGo = new GameObject("DefShieldLight");
        lightGo.transform.SetParent(root, false);
        shieldLight = lightGo.AddComponent<Light>();
        shieldLight.type = LightType.Point;
        shieldLight.intensity = 0f;
        shieldLight.range = 6f;
        shieldLight.enabled = false;
    }}

    /// <summary>Activate a defensive skill VFX by name.</summary>
    public void ActivateDefense(string skillName = null)
    {{
        skillName = (skillName ?? defaultSkill).ToLowerInvariant().Replace(" ", "_");
        if (!DefenseConfigs.ContainsKey(skillName))
        {{
            Debug.LogWarning($"[DefensiveVFX] Unknown skill: {{skillName}}, using {skill_name}");
            skillName = "{skill_name}";
        }}
        if (isActive) DeactivateDefense();
        activeSkill = skillName;
        isActive = true;
        sustainRoutine = StartCoroutine(DefenseSequence(skillName));
    }}

    /// <summary>Deactivate the current defensive VFX.</summary>
    public void DeactivateDefense()
    {{
        if (!isActive) return;
        isActive = false;
        if (sustainRoutine != null) StopCoroutine(sustainRoutine);
        sustainRoutine = null;
        StartCoroutine(DeactivatePhase());
    }}

    /// <summary>Trigger hit reaction on the active shield.</summary>
    public void OnHitReact(Vector3 hitDirection)
    {{
        if (!isActive || activeSkill == null) return;
        if (!DefenseConfigs.ContainsKey(activeSkill)) return;
        var cfg = DefenseConfigs[activeSkill];
        StartCoroutine(HitReactPhase(cfg, hitDirection));
    }}

    private IEnumerator DefenseSequence(string skillName)
    {{
        var cfg = DefenseConfigs[skillName];
        OnDefenseActivated?.Invoke(skillName);

        // ==== Phase 1: ACTIVATE (burst + flash) ====
        yield return StartCoroutine(ActivatePhase(cfg));

        // ==== Phase 2: SUSTAIN (looping shield particles) ====
        yield return StartCoroutine(SustainPhase(cfg));

        // ==== Phase 3: AUTO-DEACTIVATE ====
        if (isActive) DeactivateDefense();
    }}

    private IEnumerator ActivatePhase(DefenseConfig cfg)
    {{
        var pos = transform.position + Vector3.up;
        activateBurstPS.transform.position = pos;
        BurstPS(activateBurstPS, cfg.burst, cfg.glow, 0.6f,
                cfg.size * 0.5f, cfg.size * 2f, cfg.speed, cfg.speed * 2f);
        activateBurstPS.Play();

        shieldLight.transform.position = pos;
        shieldLight.color = cfg.glow;
        shieldLight.enabled = true;
        PrimeTween.Tween.Custom(shieldLight, 0f, 5f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);

        DoScreenShake(0.15f, 0.2f);
        yield return new WaitForSeconds(0.4f);

        PrimeTween.Tween.Custom(shieldLight, 5f, 1.5f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);
    }}

    private IEnumerator SustainPhase(DefenseConfig cfg)
    {{
        var pos = transform.position + Vector3.up;

        // Core shield particles
        shieldCorePS.transform.position = pos;
        ConfigPS(shieldCorePS, cfg.color, cfg.rate, cfg.lifetime, cfg.size,
                 ParticleSystemShapeType.Sphere);
        var coreShape = shieldCorePS.shape;
        coreShape.radius = cfg.radius;
        var coreMain = shieldCorePS.main;
        coreMain.startSpeed = new ParticleSystem.MinMaxCurve(cfg.speed * 0.2f, cfg.speed * 0.5f);
        var coreGrav = shieldCorePS.main;
        coreGrav.gravityModifier = cfg.gravity;
        shieldCorePS.Play();

        // Glow overlay
        shieldGlowPS.transform.position = pos;
        ConfigPS(shieldGlowPS, cfg.glow * 0.6f, cfg.rate * 0.4f, cfg.lifetime * 1.2f,
                 cfg.size * 1.5f, ParticleSystemShapeType.Sphere);
        var glowShape = shieldGlowPS.shape;
        glowShape.radius = cfg.radius * 0.95f;
        shieldGlowPS.Play();

        // Secondary detail particles
        shieldSecondaryPS.transform.position = pos;
        ConfigPS(shieldSecondaryPS, cfg.secondaryColor, cfg.rate * 0.3f, cfg.lifetime * 0.7f,
                 cfg.size * 0.5f, ParticleSystemShapeType.Sphere);
        var secShape = shieldSecondaryPS.shape;
        secShape.radius = cfg.radius * 0.8f;
        shieldSecondaryPS.Play();

        // Pulse the light rhythmically while sustained
        float elapsed = 0f;
        while (isActive && elapsed < shieldDuration)
        {{
            float pulse = 1.0f + 0.5f * Mathf.Sin(elapsed * 2f * Mathf.PI * 0.5f);
            if (shieldLight != null) shieldLight.intensity = pulse;
            elapsed += Time.deltaTime;
            yield return null;
        }}

        shieldCorePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        shieldGlowPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        shieldSecondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator HitReactPhase(DefenseConfig cfg, Vector3 hitDir)
    {{
        OnDefenseHitReact?.Invoke(activeSkill, hitDir);
        var hitPos = transform.position + Vector3.up + hitDir.normalized * cfg.radius;
        hitReactPS.transform.position = hitPos;
        BurstPS(hitReactPS, cfg.burst / 2, cfg.glow, 0.3f,
                cfg.size * 0.3f, cfg.size * 1.5f, cfg.speed * 2f, cfg.speed * 4f);
        hitReactPS.Play();
        DoScreenShake(0.08f, 0.1f);
        if (shieldLight != null)
        {{
            PrimeTween.Tween.Custom(shieldLight, shieldLight.intensity, 4f, duration: 0.05f,
                onValueChange: (target, val) => target.intensity = val);
            yield return new WaitForSeconds(0.08f);
            PrimeTween.Tween.Custom(shieldLight, 4f, 1.5f, duration: 0.15f,
                onValueChange: (target, val) => target.intensity = val);
        }}
        yield return new WaitForSeconds(0.2f);
    }}

    private IEnumerator DeactivatePhase()
    {{
        if (activeSkill == null || !DefenseConfigs.ContainsKey(activeSkill)) yield break;
        var cfg = DefenseConfigs[activeSkill];
        OnDefenseDeactivated?.Invoke(activeSkill);

        shieldCorePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        shieldGlowPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        shieldSecondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        var pos = transform.position + Vector3.up;
        deactivateShatterPS.transform.position = pos;
        BurstPS(deactivateShatterPS, cfg.burst, cfg.color, 0.5f,
                cfg.size * 0.2f, cfg.size * 1.0f, cfg.speed * 2f, cfg.speed * 5f);
        deactivateShatterPS.Play();

        DoScreenShake(0.1f, 0.15f);
        if (shieldLight != null)
        {{
            PrimeTween.Tween.Custom(shieldLight, shieldLight.intensity, 0f, duration: 0.4f,
                onValueChange: (target, val) => target.intensity = val);
        }}
        yield return new WaitForSeconds(0.5f);
        if (shieldLight != null) shieldLight.enabled = false;
        activeSkill = null;
    }}

    /// <summary>Get list of all available defensive skills.</summary>
    public static string[] GetAllSkillNames()
    {{
        var names = new string[DefenseConfigs.Count];
        int i = 0;
        foreach (var kvp in DefenseConfigs) names[i++] = kvp.Key;
        return names;
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Defensive Skill VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("DefensiveSkillVFXController");
        go.AddComponent<DefensiveSkillVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("DefensiveSkillVFXController created in scene with 20 defensive skills");
    }}
#endif
{_CS_WRITE_RESULT}
}}
'''

    script_path = "Assets/Editor/Generated/VFX/DefensiveSkillVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 2. generate_healing_skill_vfx_script
# ===================================================================


def generate_healing_skill_vfx_script(skill_name: str = "restorative_bloom") -> dict[str, Any]:
    """Generate HealingSkillVFXController MonoBehaviour for 15 healing skills.

    Each skill features a charge-up, main heal effect, ally-hit feedback, and
    fade-out phase. Supports self-heal and AoE heal modes.

    Args:
        skill_name: Default active skill. One of 15 healing skills.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    skill_name = skill_name.lower().replace(" ", "_")
    if skill_name not in HEALING_SKILL_CONFIGS:
        skill_name = "restorative_bloom"

    safe_name = sanitize_cs_identifier(skill_name)
    configs_block = _build_skill_configs_cs(
        HEALING_SKILL_CONFIGS, "HealConfig", "HealConfigs",
    )

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Healing skill VFX controller for VeilBreakers -- 15 named healing skills.
/// Each skill has 4 phases: charge (energy gather), heal-main (core effect),
/// ally-hit (per-target feedback), and fade-out (dissipate).
/// Default: {skill_name}
/// API: TriggerHeal(skillName, origin, targets) / TriggerSelfHeal(skillName)
/// </summary>
public class HealingSkillVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct HealConfig
    {{
        public Color color;
        public Color glow;
        public Color secondaryColor;
        public int rate;
        public float lifetime;
        public float size;
        public float speed;
        public int burst;
        public float radius;
        public float gravity;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSkill = "{skill_name}";

    // Events
    public event Action<string, Vector3> OnHealStarted;
    public event Action<string, Transform> OnAllyHealed;
    public event Action<string> OnHealCompleted;

{configs_block}

    // Runtime particle systems
    private ParticleSystem chargePS;
    private ParticleSystem chargeGlowPS;
    private ParticleSystem healMainPS;
    private ParticleSystem healSecondaryPS;
    private ParticleSystem allyHitPS;
    private ParticleSystem fadeOutPS;
    private Light healLight;

    private Coroutine activeHealRoutine;
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
        chargePS = CreatePS("HealCharge", root, 500);
        chargeGlowPS = CreatePS("HealChargeGlow", root, 300);
        healMainPS = CreatePS("HealMain", root, 1000);
        healSecondaryPS = CreatePS("HealSecondary", root, 500);
        allyHitPS = CreatePS("HealAllyHit", root, 400);
        fadeOutPS = CreatePS("HealFadeOut", root, 300);

        var glowRenderer = chargeGlowPS.GetComponent<ParticleSystemRenderer>();
        glowRenderer.material = GetAdditiveMaterial();
        var mainRenderer = healMainPS.GetComponent<ParticleSystemRenderer>();
        mainRenderer.material = GetAdditiveMaterial();

        var lightGo = new GameObject("HealLight");
        lightGo.transform.SetParent(root, false);
        healLight = lightGo.AddComponent<Light>();
        healLight.type = LightType.Point;
        healLight.intensity = 0f;
        healLight.range = 8f;
        healLight.enabled = false;
    }}

    /// <summary>Trigger an AoE or targeted heal with VFX.</summary>
    public void TriggerHeal(string skillName = null, Vector3? origin = null, Transform[] targets = null)
    {{
        skillName = (skillName ?? defaultSkill).ToLowerInvariant().Replace(" ", "_");
        if (!HealConfigs.ContainsKey(skillName))
        {{
            Debug.LogWarning($"[HealVFX] Unknown skill: {{skillName}}, using {skill_name}");
            skillName = "{skill_name}";
        }}
        var pos = origin ?? transform.position;
        if (activeHealRoutine != null) StopCoroutine(activeHealRoutine);
        activeHealRoutine = StartCoroutine(HealSequence(skillName, pos, targets));
    }}

    /// <summary>Trigger self-heal VFX (no targets).</summary>
    public void TriggerSelfHeal(string skillName = null)
    {{
        TriggerHeal(skillName, transform.position, null);
    }}

    private IEnumerator HealSequence(string skillName, Vector3 origin, Transform[] targets)
    {{
        var cfg = HealConfigs[skillName];
        OnHealStarted?.Invoke(skillName, origin);

        // ==== Phase 1: CHARGE (energy gather) ====
        yield return StartCoroutine(ChargePhase(cfg, origin));

        // ==== Phase 2: HEAL-MAIN (core effect expansion) ====
        yield return StartCoroutine(HealMainPhase(cfg, origin));

        // ==== Phase 3: ALLY-HIT (per-target feedback) ====
        if (targets != null)
        {{
            foreach (var target in targets)
            {{
                if (target == null) continue;
                yield return StartCoroutine(AllyHitPhase(cfg, target, skillName));
            }}
        }}

        // ==== Phase 4: FADE-OUT ====
        yield return StartCoroutine(FadeOutPhase(cfg, origin));

        OnHealCompleted?.Invoke(skillName);
        activeHealRoutine = null;
    }}

    private IEnumerator ChargePhase(HealConfig cfg, Vector3 origin)
    {{
        var chargePos = origin + Vector3.up * 1.0f;
        chargePS.transform.position = chargePos;
        ConfigPS(chargePS, cfg.color, cfg.rate * 0.4f, 0.6f, cfg.size * 0.4f,
                 ParticleSystemShapeType.Sphere);
        var chargeShape = chargePS.shape;
        chargeShape.radius = cfg.radius;
        var chargeMain = chargePS.main;
        chargeMain.startSpeed = new ParticleSystem.MinMaxCurve(-cfg.speed, -cfg.speed * 0.5f);
        chargePS.Play();

        chargeGlowPS.transform.position = chargePos;
        ConfigPS(chargeGlowPS, cfg.glow * 0.5f, cfg.rate * 0.2f, 0.8f, cfg.size * 0.8f,
                 ParticleSystemShapeType.Sphere);
        var glowShape = chargeGlowPS.shape;
        glowShape.radius = cfg.radius * 0.3f;
        chargeGlowPS.Play();

        healLight.transform.position = chargePos;
        healLight.color = cfg.glow;
        healLight.enabled = true;
        PrimeTween.Tween.Custom(healLight, 0f, 3f, duration: 0.5f,
            onValueChange: (target, val) => target.intensity = val);

        yield return new WaitForSeconds(0.6f);

        chargePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        chargeGlowPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator HealMainPhase(HealConfig cfg, Vector3 origin)
    {{
        var pos = origin + Vector3.up * 0.5f;

        healMainPS.transform.position = pos;
        ConfigPS(healMainPS, cfg.glow, cfg.rate, cfg.lifetime, cfg.size,
                 ParticleSystemShapeType.Sphere);
        var mainShape = healMainPS.shape;
        mainShape.radius = cfg.radius * 0.5f;
        var mainMain = healMainPS.main;
        mainMain.startSpeed = new ParticleSystem.MinMaxCurve(cfg.speed * 0.5f, cfg.speed);
        mainMain.gravityModifier = cfg.gravity;
        healMainPS.Play();

        healSecondaryPS.transform.position = pos;
        ConfigPS(healSecondaryPS, cfg.secondaryColor, cfg.rate * 0.5f, cfg.lifetime * 1.3f,
                 cfg.size * 0.6f, ParticleSystemShapeType.Sphere);
        var secShape = healSecondaryPS.shape;
        secShape.radius = cfg.radius * 0.3f;
        healSecondaryPS.Play();

        BurstPS(healMainPS, cfg.burst, cfg.glow, cfg.lifetime * 0.5f,
                cfg.size, cfg.size * 2f, cfg.speed, cfg.speed * 2f);

        PrimeTween.Tween.Custom(healLight, healLight.intensity, 5f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);

        yield return new WaitForSeconds(cfg.lifetime * 0.8f);

        healMainPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        healSecondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator AllyHitPhase(HealConfig cfg, Transform allyTarget, string skillName)
    {{
        OnAllyHealed?.Invoke(skillName, allyTarget);
        allyHitPS.transform.position = allyTarget.position + Vector3.up;
        BurstPS(allyHitPS, cfg.burst / 3, cfg.glow, 0.4f,
                cfg.size * 0.3f, cfg.size, cfg.speed * 0.5f, cfg.speed * 1.5f);
        allyHitPS.Play();
        yield return new WaitForSeconds(0.15f);
    }}

    private IEnumerator FadeOutPhase(HealConfig cfg, Vector3 origin)
    {{
        var pos = origin + Vector3.up * 0.5f;
        fadeOutPS.transform.position = pos;
        ConfigPS(fadeOutPS, cfg.color * 0.5f, cfg.rate * 0.2f, cfg.lifetime * 1.5f,
                 cfg.size * 0.3f, ParticleSystemShapeType.Sphere);
        var fadeShape = fadeOutPS.shape;
        fadeShape.radius = cfg.radius;
        var fadeMain = fadeOutPS.main;
        fadeMain.gravityModifier = cfg.gravity - 0.3f;
        fadeOutPS.Play();

        PrimeTween.Tween.Custom(healLight, healLight.intensity, 0f, duration: 0.6f,
            onValueChange: (target, val) => target.intensity = val);

        yield return new WaitForSeconds(1.0f);
        fadeOutPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        healLight.enabled = false;
    }}

    /// <summary>Get list of all available healing skills.</summary>
    public static string[] GetAllSkillNames()
    {{
        var names = new string[HealConfigs.Count];
        int i = 0;
        foreach (var kvp in HealConfigs) names[i++] = kvp.Key;
        return names;
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Healing Skill VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("HealingSkillVFXController");
        go.AddComponent<HealingSkillVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("HealingSkillVFXController created in scene with 15 healing skills");
    }}
#endif
{_CS_WRITE_RESULT}
}}
'''

    script_path = "Assets/Editor/Generated/VFX/HealingSkillVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 3. generate_summon_skill_vfx_script
# ===================================================================


def generate_summon_skill_vfx_script(skill_name: str = "skeletal_rising") -> dict[str, Any]:
    """Generate SummonSkillVFXController MonoBehaviour for 20 summon skills.

    Each summon has 4 phases: portal-open (magic circle / ground crack),
    materialization (entity forms), link-establish (tether to summoner),
    and idle-ambient (persistent looping particles on summoned creature).

    Args:
        skill_name: Default summon skill. One of 20 summon skills.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    skill_name = skill_name.lower().replace(" ", "_")
    if skill_name not in SUMMON_SKILL_CONFIGS:
        skill_name = "skeletal_rising"

    safe_name = sanitize_cs_identifier(skill_name)
    configs_block = _build_skill_configs_cs(
        SUMMON_SKILL_CONFIGS, "SummonConfig", "SummonConfigs",
    )

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Summon skill VFX controller for VeilBreakers -- 20 named summon skills.
/// Each summon has 4 phases: portal-open, materialization, link-establish, idle-ambient.
/// Default: {skill_name}
/// API: TriggerSummon(skillName, summonPos, summonedObj) / DismissSummon()
/// </summary>
public class SummonSkillVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct SummonConfig
    {{
        public Color color;
        public Color glow;
        public Color secondaryColor;
        public int rate;
        public float lifetime;
        public float size;
        public float speed;
        public int burst;
        public float radius;
        public float gravity;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSkill = "{skill_name}";

    // Events
    public event Action<string, Vector3> OnSummonStarted;
    public event Action<string, GameObject> OnSummonMaterialized;
    public event Action<string> OnSummonDismissed;

{configs_block}

    // Runtime particle systems
    private ParticleSystem portalCirclePS;
    private ParticleSystem portalEnergyPS;
    private ParticleSystem materializePS;
    private ParticleSystem materializeBurstPS;
    private ParticleSystem linkTetherPS;
    private ParticleSystem idleAmbientPS;
    private ParticleSystem dismissPS;
    private Light portalLight;
    private Light summonLight;

    private string activeSkill;
    private Coroutine summonRoutine;
    private Coroutine idleRoutine;
    private bool isSummoned;
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
        portalCirclePS = CreatePS("SumPortalCircle", root, 500);
        portalEnergyPS = CreatePS("SumPortalEnergy", root, 800);
        materializePS = CreatePS("SumMaterialize", root, 600);
        materializeBurstPS = CreatePS("SumMaterializeBurst", root, 1000);
        linkTetherPS = CreatePS("SumLinkTether", root, 200);
        idleAmbientPS = CreatePS("SumIdleAmbient", root, 300);
        dismissPS = CreatePS("SumDismiss", root, 600);

        var portalRenderer = portalEnergyPS.GetComponent<ParticleSystemRenderer>();
        portalRenderer.material = GetAdditiveMaterial();
        var burstRenderer = materializeBurstPS.GetComponent<ParticleSystemRenderer>();
        burstRenderer.material = GetAdditiveMaterial();

        var portalLightGo = new GameObject("SumPortalLight");
        portalLightGo.transform.SetParent(root, false);
        portalLight = portalLightGo.AddComponent<Light>();
        portalLight.type = LightType.Point;
        portalLight.intensity = 0f;
        portalLight.range = 5f;
        portalLight.enabled = false;

        var summonLightGo = new GameObject("SumSummonLight");
        summonLightGo.transform.SetParent(root, false);
        summonLight = summonLightGo.AddComponent<Light>();
        summonLight.type = LightType.Point;
        summonLight.intensity = 0f;
        summonLight.range = 4f;
        summonLight.enabled = false;
    }}

    /// <summary>Trigger a summon VFX sequence at the specified position.</summary>
    public void TriggerSummon(string skillName = null, Vector3? summonPos = null, GameObject summonedObj = null)
    {{
        skillName = (skillName ?? defaultSkill).ToLowerInvariant().Replace(" ", "_");
        if (!SummonConfigs.ContainsKey(skillName))
        {{
            Debug.LogWarning($"[SummonVFX] Unknown skill: {{skillName}}, using {skill_name}");
            skillName = "{skill_name}";
        }}
        if (isSummoned) DismissSummon();
        var pos = summonPos ?? (transform.position + transform.forward * 3f);
        activeSkill = skillName;
        summonRoutine = StartCoroutine(SummonSequence(skillName, pos, summonedObj));
    }}

    /// <summary>Dismiss the current summon with VFX.</summary>
    public void DismissSummon()
    {{
        if (!isSummoned) return;
        isSummoned = false;
        if (idleRoutine != null) StopCoroutine(idleRoutine);
        idleRoutine = null;
        StartCoroutine(DismissPhase());
    }}

    private IEnumerator SummonSequence(string skillName, Vector3 summonPos, GameObject summonedObj)
    {{
        var cfg = SummonConfigs[skillName];
        OnSummonStarted?.Invoke(skillName, summonPos);

        // ==== Phase 1: PORTAL OPEN ====
        yield return StartCoroutine(PortalOpenPhase(cfg, summonPos));

        // ==== Phase 2: MATERIALIZATION ====
        yield return StartCoroutine(MaterializePhase(cfg, summonPos));
        OnSummonMaterialized?.Invoke(skillName, summonedObj);

        // ==== Phase 3: LINK ESTABLISH ====
        yield return StartCoroutine(LinkPhase(cfg, summonPos));

        // ==== Phase 4: IDLE AMBIENT (loops until dismissed) ====
        isSummoned = true;
        idleRoutine = StartCoroutine(IdleAmbientPhase(cfg, summonPos));
        summonRoutine = null;
    }}

    private IEnumerator PortalOpenPhase(SummonConfig cfg, Vector3 pos)
    {{
        // Magic circle on ground
        portalCirclePS.transform.position = pos;
        ConfigPS(portalCirclePS, cfg.color, cfg.rate * 0.5f, 1.0f, cfg.size * 0.5f,
                 ParticleSystemShapeType.Circle);
        var circleShape = portalCirclePS.shape;
        circleShape.radius = cfg.radius;
        portalCirclePS.Play();

        // Energy column rising
        portalEnergyPS.transform.position = pos;
        ConfigPS(portalEnergyPS, cfg.glow, cfg.rate, 0.8f, cfg.size * 0.3f,
                 ParticleSystemShapeType.Circle);
        var energyShape = portalEnergyPS.shape;
        energyShape.radius = cfg.radius * 0.5f;
        var energyVel = portalEnergyPS.velocityOverLifetime;
        energyVel.enabled = true;
        energyVel.y = new ParticleSystem.MinMaxCurve(cfg.speed, cfg.speed * 2f);
        portalEnergyPS.Play();

        portalLight.transform.position = pos + Vector3.up * 0.5f;
        portalLight.color = cfg.glow;
        portalLight.enabled = true;
        PrimeTween.Tween.Custom(portalLight, 0f, 4f, duration: 0.5f,
            onValueChange: (target, val) => target.intensity = val);

        DoScreenShake(0.12f, 0.3f);
        yield return new WaitForSeconds(0.8f);

        portalCirclePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        portalEnergyPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator MaterializePhase(SummonConfig cfg, Vector3 pos)
    {{
        var matPos = pos + Vector3.up * 0.5f;

        materializePS.transform.position = matPos;
        ConfigPS(materializePS, cfg.secondaryColor, cfg.rate * 0.6f, cfg.lifetime, cfg.size,
                 ParticleSystemShapeType.Sphere);
        var matShape = materializePS.shape;
        matShape.radius = cfg.radius * 0.4f;
        var matMain = materializePS.main;
        matMain.startSpeed = new ParticleSystem.MinMaxCurve(-cfg.speed * 0.5f, -cfg.speed * 0.2f);
        materializePS.Play();

        yield return new WaitForSeconds(0.4f);

        // Burst on materialization
        materializeBurstPS.transform.position = matPos;
        BurstPS(materializeBurstPS, cfg.burst, cfg.glow, 0.5f,
                cfg.size * 0.5f, cfg.size * 2f, cfg.speed, cfg.speed * 3f);
        materializeBurstPS.Play();

        summonLight.transform.position = matPos;
        summonLight.color = cfg.glow;
        summonLight.enabled = true;
        PrimeTween.Tween.Custom(summonLight, 0f, 6f, duration: 0.2f,
            onValueChange: (target, val) => target.intensity = val);

        DoScreenShake(0.2f, 0.25f);
        yield return new WaitForSeconds(0.5f);

        materializePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        PrimeTween.Tween.Custom(portalLight, portalLight.intensity, 0f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);
        PrimeTween.Tween.Custom(summonLight, summonLight.intensity, 2f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);

        yield return new WaitForSeconds(0.3f);
        portalLight.enabled = false;
    }}

    private IEnumerator LinkPhase(SummonConfig cfg, Vector3 summonPos)
    {{
        var casterPos = transform.position + Vector3.up;
        var targetPos = summonPos + Vector3.up;

        linkTetherPS.transform.position = casterPos;
        ConfigPS(linkTetherPS, cfg.glow * 0.6f, cfg.rate * 0.15f, 0.5f, cfg.size * 0.2f,
                 ParticleSystemShapeType.Cone);
        var tetherShape = linkTetherPS.shape;
        tetherShape.angle = 5f;
        linkTetherPS.transform.LookAt(targetPos);
        linkTetherPS.Play();

        yield return new WaitForSeconds(0.6f);
        linkTetherPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator IdleAmbientPhase(SummonConfig cfg, Vector3 summonPos)
    {{
        var idlePos = summonPos + Vector3.up * 0.5f;
        idleAmbientPS.transform.position = idlePos;
        ConfigPS(idleAmbientPS, cfg.color * 0.7f, cfg.rate * 0.15f, cfg.lifetime * 1.5f,
                 cfg.size * 0.4f, ParticleSystemShapeType.Sphere);
        var idleShape = idleAmbientPS.shape;
        idleShape.radius = cfg.radius * 0.5f;
        var idleMain = idleAmbientPS.main;
        idleMain.gravityModifier = cfg.gravity;
        idleAmbientPS.Play();

        // Pulse light gently while summoned
        while (isSummoned)
        {{
            float pulse = 1.2f + 0.3f * Mathf.Sin(Time.time * 1.5f);
            if (summonLight != null) summonLight.intensity = pulse;
            yield return null;
        }}

        idleAmbientPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator DismissPhase()
    {{
        if (activeSkill == null || !SummonConfigs.ContainsKey(activeSkill)) yield break;
        var cfg = SummonConfigs[activeSkill];
        OnSummonDismissed?.Invoke(activeSkill);

        idleAmbientPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        dismissPS.transform.position = idleAmbientPS.transform.position;
        BurstPS(dismissPS, cfg.burst / 2, cfg.color, 0.6f,
                cfg.size * 0.3f, cfg.size * 1.2f, cfg.speed, cfg.speed * 2f);
        dismissPS.Play();

        if (summonLight != null)
        {{
            PrimeTween.Tween.Custom(summonLight, summonLight.intensity, 0f, duration: 0.5f,
                onValueChange: (target, val) => target.intensity = val);
        }}

        DoScreenShake(0.08f, 0.15f);
        yield return new WaitForSeconds(0.6f);
        if (summonLight != null) summonLight.enabled = false;
        activeSkill = null;
    }}

    /// <summary>Get list of all available summon skills.</summary>
    public static string[] GetAllSkillNames()
    {{
        var names = new string[SummonConfigs.Count];
        int i = 0;
        foreach (var kvp in SummonConfigs) names[i++] = kvp.Key;
        return names;
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Summon Skill VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("SummonSkillVFXController");
        go.AddComponent<SummonSkillVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("SummonSkillVFXController created in scene with 20 summon skills");
    }}
#endif
{_CS_WRITE_RESULT}
}}
'''

    script_path = "Assets/Editor/Generated/VFX/SummonSkillVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 4. generate_transform_skill_vfx_script
# ===================================================================


def generate_transform_skill_vfx_script(skill_name: str = "demon_trigger") -> dict[str, Any]:
    """Generate TransformSkillVFXController MonoBehaviour for 15 transform skills.

    Transformation skills have 5 phases: wind-up (energy builds), eruption
    (explosive burst), morph (body change particles), stabilize (new form
    settles), and persistent-aura (looping VFX while transformed).

    Args:
        skill_name: Default transform skill. One of 15 transform skills.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    skill_name = skill_name.lower().replace(" ", "_")
    if skill_name not in TRANSFORM_SKILL_CONFIGS:
        skill_name = "demon_trigger"

    safe_name = sanitize_cs_identifier(skill_name)
    configs_block = _build_skill_configs_cs(
        TRANSFORM_SKILL_CONFIGS, "TransformConfig", "TransformConfigs",
        include_persistent=True,
    )

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Transform skill VFX controller for VeilBreakers -- 15 named transform skills.
/// Each transform has 5 phases: wind-up, eruption, morph, stabilize, persistent-aura.
/// Default: {skill_name}
/// API: TriggerTransform(skillName) / RevertTransform() / IsTransformed
/// </summary>
public class TransformSkillVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct TransformConfig
    {{
        public Color color;
        public Color glow;
        public Color secondaryColor;
        public int rate;
        public float lifetime;
        public float size;
        public float speed;
        public int burst;
        public float radius;
        public float gravity;
        public int persistentRate;
        public float persistentSize;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSkill = "{skill_name}";
    [SerializeField] private float transformDuration = 15f;

    // Events
    public event Action<string> OnTransformStarted;
    public event Action<string> OnTransformComplete;
    public event Action<string> OnTransformReverted;

    /// <summary>True while the character is in transformed state.</summary>
    public bool IsTransformed {{ get; private set; }}

{configs_block}

    // Runtime particle systems
    private ParticleSystem windUpPS;
    private ParticleSystem windUpGlowPS;
    private ParticleSystem eruptionPS;
    private ParticleSystem eruptionFlashPS;
    private ParticleSystem morphPS;
    private ParticleSystem morphDetailPS;
    private ParticleSystem stabilizePS;
    private ParticleSystem persistentAuraPS;
    private ParticleSystem persistentDetailPS;
    private ParticleSystem revertBurstPS;
    private Light transformLight;
    private Light auraLight;

    private string activeSkill;
    private Coroutine transformRoutine;
    private Coroutine auraRoutine;
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
        windUpPS = CreatePS("TfWindUp", root, 600);
        windUpGlowPS = CreatePS("TfWindUpGlow", root, 400);
        eruptionPS = CreatePS("TfEruption", root, 1500);
        eruptionFlashPS = CreatePS("TfEruptionFlash", root, 800);
        morphPS = CreatePS("TfMorph", root, 800);
        morphDetailPS = CreatePS("TfMorphDetail", root, 400);
        stabilizePS = CreatePS("TfStabilize", root, 500);
        persistentAuraPS = CreatePS("TfPersistentAura", root, 500);
        persistentDetailPS = CreatePS("TfPersistentDetail", root, 300);
        revertBurstPS = CreatePS("TfRevertBurst", root, 800);

        // Additive materials for glow systems
        var glowRenderer = windUpGlowPS.GetComponent<ParticleSystemRenderer>();
        glowRenderer.material = GetAdditiveMaterial();
        var flashRenderer = eruptionFlashPS.GetComponent<ParticleSystemRenderer>();
        flashRenderer.material = GetAdditiveMaterial();
        var auraRenderer = persistentAuraPS.GetComponent<ParticleSystemRenderer>();
        auraRenderer.material = GetAdditiveMaterial();

        var transLightGo = new GameObject("TfTransformLight");
        transLightGo.transform.SetParent(root, false);
        transformLight = transLightGo.AddComponent<Light>();
        transformLight.type = LightType.Point;
        transformLight.intensity = 0f;
        transformLight.range = 10f;
        transformLight.enabled = false;

        var auraLightGo = new GameObject("TfAuraLight");
        auraLightGo.transform.SetParent(root, false);
        auraLight = auraLightGo.AddComponent<Light>();
        auraLight.type = LightType.Point;
        auraLight.intensity = 0f;
        auraLight.range = 6f;
        auraLight.enabled = false;
    }}

    /// <summary>Trigger a transformation VFX sequence.</summary>
    public void TriggerTransform(string skillName = null)
    {{
        skillName = (skillName ?? defaultSkill).ToLowerInvariant().Replace(" ", "_");
        if (!TransformConfigs.ContainsKey(skillName))
        {{
            Debug.LogWarning($"[TransformVFX] Unknown skill: {{skillName}}, using {skill_name}");
            skillName = "{skill_name}";
        }}
        if (IsTransformed) RevertTransform();
        activeSkill = skillName;
        transformRoutine = StartCoroutine(TransformSequence(skillName));
    }}

    /// <summary>Revert the transformation with VFX.</summary>
    public void RevertTransform()
    {{
        if (!IsTransformed) return;
        IsTransformed = false;
        if (auraRoutine != null) StopCoroutine(auraRoutine);
        auraRoutine = null;
        StartCoroutine(RevertPhase());
    }}

    private IEnumerator TransformSequence(string skillName)
    {{
        var cfg = TransformConfigs[skillName];
        OnTransformStarted?.Invoke(skillName);

        // ==== Phase 1: WIND-UP (energy builds around character) ====
        yield return StartCoroutine(WindUpPhase(cfg));

        // ==== Phase 2: ERUPTION (explosive energy release) ====
        yield return StartCoroutine(EruptionPhase(cfg));

        // ==== Phase 3: MORPH (body change particles) ====
        yield return StartCoroutine(MorphPhase(cfg));

        // ==== Phase 4: STABILIZE (new form settles) ====
        yield return StartCoroutine(StabilizePhase(cfg));

        OnTransformComplete?.Invoke(skillName);

        // ==== Phase 5: PERSISTENT AURA (loops until reverted) ====
        IsTransformed = true;
        auraRoutine = StartCoroutine(PersistentAuraPhase(cfg));

        // Auto-revert after duration
        yield return new WaitForSeconds(transformDuration);
        if (IsTransformed) RevertTransform();
        transformRoutine = null;
    }}

    private IEnumerator WindUpPhase(TransformConfig cfg)
    {{
        var pos = transform.position + Vector3.up;

        // Inward-gathering energy
        windUpPS.transform.position = pos;
        ConfigPS(windUpPS, cfg.color, cfg.rate * 0.5f, 0.8f, cfg.size * 0.4f,
                 ParticleSystemShapeType.Sphere);
        var windShape = windUpPS.shape;
        windShape.radius = cfg.radius * 1.5f;
        var windMain = windUpPS.main;
        windMain.startSpeed = new ParticleSystem.MinMaxCurve(-cfg.speed, -cfg.speed * 0.3f);
        windUpPS.Play();

        // Glow intensifying at center
        windUpGlowPS.transform.position = pos;
        ConfigPS(windUpGlowPS, cfg.glow * 0.4f, cfg.rate * 0.3f, 1.0f, cfg.size * 0.6f,
                 ParticleSystemShapeType.Sphere);
        var glowShape = windUpGlowPS.shape;
        glowShape.radius = cfg.radius * 0.3f;
        windUpGlowPS.Play();

        transformLight.transform.position = pos;
        transformLight.color = cfg.glow;
        transformLight.enabled = true;
        PrimeTween.Tween.Custom(transformLight, 0f, 3f, duration: 0.8f,
            onValueChange: (target, val) => target.intensity = val);

        DoScreenShake(0.1f, 0.6f);
        yield return new WaitForSeconds(0.8f);

        windUpPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        windUpGlowPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator EruptionPhase(TransformConfig cfg)
    {{
        var pos = transform.position + Vector3.up;

        // Massive outward burst
        eruptionPS.transform.position = pos;
        BurstPS(eruptionPS, cfg.burst, cfg.color, 0.6f,
                cfg.size * 0.5f, cfg.size * 3f, cfg.speed * 2f, cfg.speed * 4f);
        eruptionPS.Play();

        // White-hot flash at center
        eruptionFlashPS.transform.position = pos;
        BurstPS(eruptionFlashPS, cfg.burst / 2, cfg.glow, 0.3f,
                cfg.size * 2f, cfg.size * 5f, 0.5f, 2f);
        eruptionFlashPS.Play();

        PrimeTween.Tween.Custom(transformLight, transformLight.intensity, 12f, duration: 0.1f,
            onValueChange: (target, val) => target.intensity = val);

        DoScreenShake(0.4f, 0.3f);
        yield return new WaitForSeconds(0.15f);

        PrimeTween.Tween.Custom(transformLight, 12f, 4f, duration: 0.3f,
            onValueChange: (target, val) => target.intensity = val);
        yield return new WaitForSeconds(0.35f);
    }}

    private IEnumerator MorphPhase(TransformConfig cfg)
    {{
        var pos = transform.position + Vector3.up;

        // Body-hugging morph particles
        morphPS.transform.position = pos;
        ConfigPS(morphPS, cfg.secondaryColor, cfg.rate, cfg.lifetime * 0.7f, cfg.size * 0.6f,
                 ParticleSystemShapeType.Sphere);
        var morphShape = morphPS.shape;
        morphShape.radius = 0.5f;
        var morphMain = morphPS.main;
        morphMain.gravityModifier = cfg.gravity;
        morphPS.Play();

        // Detail particles showing the change
        morphDetailPS.transform.position = pos;
        ConfigPS(morphDetailPS, cfg.glow, cfg.rate * 0.4f, cfg.lifetime * 0.5f,
                 cfg.size * 0.3f, ParticleSystemShapeType.Sphere);
        var detailShape = morphDetailPS.shape;
        detailShape.radius = 0.8f;
        morphDetailPS.Play();

        yield return new WaitForSeconds(0.6f);

        morphPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        morphDetailPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private IEnumerator StabilizePhase(TransformConfig cfg)
    {{
        var pos = transform.position + Vector3.up;

        stabilizePS.transform.position = pos;
        ConfigPS(stabilizePS, cfg.glow * 0.6f, cfg.rate * 0.3f, cfg.lifetime, cfg.size * 0.5f,
                 ParticleSystemShapeType.Sphere);
        var stabShape = stabilizePS.shape;
        stabShape.radius = cfg.radius * 0.6f;
        stabilizePS.Play();

        PrimeTween.Tween.Custom(transformLight, transformLight.intensity, 2f, duration: 0.5f,
            onValueChange: (target, val) => target.intensity = val);

        yield return new WaitForSeconds(0.5f);

        stabilizePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        transformLight.enabled = false;
    }}

    private IEnumerator PersistentAuraPhase(TransformConfig cfg)
    {{
        var pos = transform.position + Vector3.up;

        // Persistent aura particles
        persistentAuraPS.transform.position = pos;
        ConfigPS(persistentAuraPS, cfg.glow * 0.4f, cfg.persistentRate, cfg.lifetime * 1.5f,
                 cfg.persistentSize, ParticleSystemShapeType.Sphere);
        var auraShape = persistentAuraPS.shape;
        auraShape.radius = cfg.radius * 0.6f;
        var auraMain = persistentAuraPS.main;
        auraMain.gravityModifier = cfg.gravity;
        persistentAuraPS.Play();

        // Detail particles
        persistentDetailPS.transform.position = pos;
        ConfigPS(persistentDetailPS, cfg.secondaryColor * 0.5f, cfg.persistentRate * 0.3f,
                 cfg.lifetime * 2f, cfg.persistentSize * 0.6f, ParticleSystemShapeType.Sphere);
        var detailShape = persistentDetailPS.shape;
        detailShape.radius = cfg.radius * 0.4f;
        persistentDetailPS.Play();

        // Aura light
        auraLight.transform.position = pos;
        auraLight.color = cfg.glow;
        auraLight.enabled = true;
        auraLight.intensity = 1.5f;

        // Pulse while transformed -- follow the transform
        while (IsTransformed)
        {{
            var currentPos = transform.position + Vector3.up;
            persistentAuraPS.transform.position = currentPos;
            persistentDetailPS.transform.position = currentPos;
            auraLight.transform.position = currentPos;
            auraLight.intensity = 1.2f + 0.4f * Mathf.Sin(Time.time * 2f);
            yield return null;
        }}

        persistentAuraPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        persistentDetailPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        auraLight.enabled = false;
    }}

    private IEnumerator RevertPhase()
    {{
        if (activeSkill == null || !TransformConfigs.ContainsKey(activeSkill)) yield break;
        var cfg = TransformConfigs[activeSkill];
        OnTransformReverted?.Invoke(activeSkill);

        persistentAuraPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        persistentDetailPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        var pos = transform.position + Vector3.up;
        revertBurstPS.transform.position = pos;
        BurstPS(revertBurstPS, cfg.burst / 2, cfg.color, 0.5f,
                cfg.size * 0.3f, cfg.size * 1.5f, cfg.speed, cfg.speed * 2f);
        revertBurstPS.Play();

        transformLight.transform.position = pos;
        transformLight.color = cfg.glow;
        transformLight.enabled = true;
        PrimeTween.Tween.Custom(transformLight, 0f, 4f, duration: 0.15f,
            onValueChange: (target, val) => target.intensity = val);

        DoScreenShake(0.15f, 0.2f);
        yield return new WaitForSeconds(0.2f);

        PrimeTween.Tween.Custom(transformLight, 4f, 0f, duration: 0.4f,
            onValueChange: (target, val) => target.intensity = val);
        if (auraLight != null)
        {{
            PrimeTween.Tween.Custom(auraLight, auraLight.intensity, 0f, duration: 0.3f,
                onValueChange: (target, val) => target.intensity = val);
        }}

        yield return new WaitForSeconds(0.4f);
        transformLight.enabled = false;
        if (auraLight != null) auraLight.enabled = false;
        activeSkill = null;
    }}

    /// <summary>Get list of all available transform skills.</summary>
    public static string[] GetAllSkillNames()
    {{
        var names = new string[TransformConfigs.Count];
        int i = 0;
        foreach (var kvp in TransformConfigs) names[i++] = kvp.Key;
        return names;
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Transform Skill VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("TransformSkillVFXController");
        go.AddComponent<TransformSkillVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("TransformSkillVFXController created in scene with 15 transform skills");
    }}
#endif
{_CS_WRITE_RESULT}
}}
'''

    script_path = "Assets/Editor/Generated/VFX/TransformSkillVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }
