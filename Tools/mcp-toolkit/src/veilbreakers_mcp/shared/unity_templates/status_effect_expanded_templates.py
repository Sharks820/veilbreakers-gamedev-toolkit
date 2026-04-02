"""Expanded status effect VFX C# template generators for Unity.

Covers all 65+ VeilBreakers status effects NOT already in vfx_mastery_templates.py
(which handles the 10 brand-specific status VFX and base CC effects).

Three function groups:
    generate_defensive_buff_vfx_script   -- shield/barrier/regen/fortify/thorns/etc.
    generate_debuff_vfx_script           -- expose/fragile/armor_shred/doom/petrify/etc.
    generate_stat_modifier_vfx_script    -- attack_up/down, speed_up/down, berserk, etc.

All scripts are MonoBehaviours using ParticleSystem (not VisualEffect), PrimeTween
(not DOTween), and C# events (not EventBus).  Targets Unity 2022.3+ URP with
shader ``Universal Render Pipeline/Particles/Unlit``.
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

STANDARD_NEXT_STEPS = [
    "Open Unity Editor and wait for compilation",
    "Attach the generated MonoBehaviour to the affected character",
    "Call the public API methods from your combat/buff system",
]

URP_PARTICLE_SHADER = "Universal Render Pipeline/Particles/Unlit"
FALLBACK_SHADER = "Particles/Standard Unlit"

_SHADER_FIND = (
    f'Shader.Find("{URP_PARTICLE_SHADER}") '
    f'?? Shader.Find("{FALLBACK_SHADER}")'
)


# ---------------------------------------------------------------------------
# Defensive buff configs
# ---------------------------------------------------------------------------

def _bc(d, de, c, g, r, lifetime, sz, ra, sh):
    """Shorthand defensive buff config constructor."""
    return {"display": d, "desc": de, "color": c, "glow": g, "rate": r,
            "lifetime": lifetime, "size": sz, "radius": ra, "shape": sh}

DEFENSIVE_BUFF_CONFIGS: dict[str, dict[str, Any]] = {
    "shield": _bc("Hex Shield", "Blue-white hexagonal shield sphere, absorption ripple on hit",
                   [0.3,0.6,1.0,0.6],[0.5,0.8,1.0,0.8], 80,0.8,0.15,1.2,"sphere"),
    "barrier": _bc("Golden Barrier", "Golden flat dome, damage cap indicator, sparkle fade",
                    [0.9,0.78,0.3,0.5],[1.0,0.9,0.5,0.7], 60,1.2,0.1,1.5,"hemisphere"),
    "regen": _bc("Regeneration", "Green healing ticks rising from feet, pulse ring every tick",
                  [0.2,0.85,0.3,0.7],[0.4,1.0,0.5,0.9], 40,1.5,0.12,0.6,"circle"),
    "fortify": _bc("Fortify", "Steel-gray armor plates materializing, CC resist flash",
                    [0.6,0.62,0.65,0.8],[0.75,0.78,0.82,1.0], 30,2.0,0.25,0.8,"box"),
    "thorns": _bc("Thorns", "Sharp red spike particles on surface, damage reflection flash",
                   [0.8,0.15,0.1,0.9],[1.0,0.3,0.2,1.0], 50,0.6,0.18,0.9,"sphere"),
    "second_wind": _bc("Second Wind", "Golden auto-revive aura, angelic flash on trigger",
                        [1.0,0.85,0.3,0.6],[1.0,1.0,0.7,1.0], 35,2.0,0.2,1.0,"sphere"),
    "undying": _bc("Undying", "Dark red survival aura, defiance particles at lethal threshold",
                    [0.6,0.05,0.05,0.7],[0.9,0.15,0.1,1.0], 45,1.5,0.15,0.9,"sphere"),
    "reflect": _bc("Reflect", "Mirror/chrome particles rotating, damage bounce flash",
                    [0.85,0.88,0.92,0.5],[1.0,1.0,1.0,0.8], 70,0.5,0.08,1.1,"sphere"),
    "immunity": _bc("Immunity", "White cleanse bubble, debuff-absorb sparkle, purity glow",
                     [0.95,0.95,1.0,0.4],[1.0,1.0,1.0,1.0], 90,0.7,0.06,1.3,"sphere"),
    "stealth": _bc("Stealth", "Alpha fade-out particles, shimmer distortion, shadow wisps",
                    [0.2,0.2,0.25,0.3],[0.4,0.4,0.5,0.4], 25,2.5,0.3,0.7,"sphere"),
}


# ---------------------------------------------------------------------------
# Debuff configs
# ---------------------------------------------------------------------------

def _dc(d, de, c, g, r, lifetime, sz, sh):
    """Shorthand debuff config constructor."""
    return {"display": d, "desc": de, "color": c, "glow": g,
            "rate": r, "lifetime": lifetime, "size": sz, "shape": sh}

DEBUFF_CONFIGS: dict[str, dict[str, Any]] = {
    "expose": _dc("Expose", "Red target reticle, vulnerability cracks, amplified damage flash",
                   [0.9,0.2,0.15,0.8],[1.0,0.35,0.25,1.0], 40,1.0,0.12,"circle"),
    "fragile": _dc("Fragile", "Glass-crack particles, shatter risk shimmer, crit amp glow",
                    [0.8,0.85,0.9,0.6],[1.0,1.0,1.0,0.8], 35,1.5,0.1,"sphere"),
    "armor_shred": _dc("Armor Shred", "Metal stripping particles, defense torn VFX",
                        [0.6,0.55,0.45,0.9],[0.85,0.75,0.6,1.0], 60,0.8,0.15,"sphere"),
    "brand_weakness": _dc("Brand Weakness", "Brand-colored vulnerability mark, 2x damage pulse",
                           [0.7,0.3,0.9,0.7],[0.85,0.5,1.0,1.0], 30,2.0,0.2,"circle"),
    "exhausted": _dc("Exhausted", "Gray desaturation, heavy breathing particles, no-buff seal",
                      [0.5,0.5,0.5,0.6],[0.65,0.65,0.65,0.7], 20,2.5,0.18,"sphere"),
    "sealed": _dc("Sealed", "Purple chain lock above head, ultimate sealed icon",
                   [0.55,0.2,0.75,0.8],[0.7,0.35,0.9,1.0], 25,3.0,0.22,"circle"),
    "grounded": _dc("Grounded", "Stone weight on feet, earth anchor particles",
                     [0.5,0.4,0.3,0.9],[0.65,0.55,0.4,1.0], 30,2.0,0.2,"circle"),
    "heal_block": _dc("Heal Block", "Red X over health bar, anti-heal rejection flash",
                       [0.85,0.1,0.1,0.8],[1.0,0.2,0.15,1.0], 35,1.0,0.14,"circle"),
    "cursed": _dc("Cursed", "Dark purple curse marks, healing reduction, affliction glow",
                   [0.4,0.1,0.5,0.7],[0.6,0.2,0.7,0.9], 30,2.5,0.16,"sphere"),
    "decay": _dc("Decay", "Brown-gray stat decay particles, progressive weakening",
                  [0.5,0.4,0.3,0.7],[0.6,0.5,0.35,0.8], 25,3.0,0.12,"sphere"),
    "wither": _dc("Wither", "Green-to-black regen reversal, anti-life glow",
                   [0.15,0.4,0.1,0.8],[0.1,0.15,0.05,0.9], 35,2.0,0.14,"sphere"),
    "doom": _dc("Doom", "Red countdown timer above head, death sentence ring, urgency pulse",
                 [0.9,0.05,0.05,0.9],[1.0,0.15,0.1,1.0], 50,1.0,0.18,"circle"),
    "marked_death": _dc("Marked for Death", "Skull mark above target, execute threshold glow",
                         [0.7,0.05,0.05,0.85],[0.9,0.1,0.08,1.0], 20,3.0,0.25,"circle"),
    "condemned": _dc("Condemned", "Purple hourglass particles, cleanse-or-die timer",
                      [0.6,0.15,0.65,0.8],[0.8,0.3,0.85,1.0], 40,1.5,0.16,"circle"),
    "petrify": _dc("Petrify", "Gray stone spread from feet, crystallization, immobile VFX",
                    [0.55,0.52,0.5,0.9],[0.7,0.68,0.65,1.0], 60,2.0,0.1,"cone"),
    "bound": _dc("Bound", "Chain/rope particles wrapping body, struggle shake",
                  [0.45,0.35,0.25,0.9],[0.6,0.5,0.35,1.0], 45,1.5,0.08,"sphere"),
    "confuse": _dc("Confuse", "Spiral dizzy particles, question marks, random arrows",
                    [0.9,0.8,0.2,0.7],[1.0,0.9,0.4,0.9], 35,2.0,0.2,"circle"),
}


# ---------------------------------------------------------------------------
# Stat modifier configs
# ---------------------------------------------------------------------------

def _sm(d, uc, dc, pos):
    """Shorthand stat mod config constructor."""
    return {"display": d, "up_color": uc, "down_color": dc, "position": pos}

STAT_MOD_CONFIGS: dict[str, dict[str, Any]] = {
    "attack":      _sm("Attack",      [0.9,0.2,0.15,0.8],[0.2,0.3,0.8,0.8],"weapon_hand"),
    "defense":     _sm("Defense",     [0.3,0.6,1.0,0.8],[0.6,0.4,0.3,0.8],"torso"),
    "speed":       _sm("Speed",       [0.2,0.85,0.3,0.8],[0.5,0.5,0.5,0.8],"feet"),
    "accuracy":    _sm("Accuracy",    [1.0,0.9,0.2,0.8],[0.4,0.4,0.5,0.6],"eyes"),
    "evasion":     _sm("Evasion",     [0.3,0.9,0.85,0.7],[0.5,0.4,0.35,0.7],"body"),
    "crit_rate":   _sm("Crit Rate",   [1.0,0.8,0.1,0.8],[0.4,0.35,0.3,0.7],"weapon"),
    "crit_damage": _sm("Crit Damage", [1.0,0.5,0.1,0.9],[0.4,0.3,0.3,0.7],"weapon"),
}

def _sp(d, c, g, de):
    """Shorthand special stat config constructor."""
    return {"display": d, "color": c, "glow": g, "desc": de}

SPECIAL_STAT_CONFIGS: dict[str, dict[str, Any]] = {
    "lifesteal": _sp("Lifesteal", [0.7,0.1,0.15,0.8],[0.9,0.2,0.2,1.0],
                      "Red drain particles from target to self on each hit"),
    "empower": _sp("Empower", [0.95,0.85,0.3,0.8],[1.0,0.95,0.5,1.0],
                    "Golden glow on weapon, next skill amplification aura"),
    "focus": _sp("Focus", [0.3,0.5,1.0,0.7],[0.5,0.7,1.0,0.9],
                  "Crosshair + lens flare, precision targeting visual"),
    "berserk": _sp("Berserk", [0.9,0.1,0.05,0.9],[1.0,0.25,0.1,1.0],
                    "Red rage aura, pulsing veins, uncontrollable fire particles"),
    "haste": _sp("Haste", [0.2,0.9,0.3,0.7],[0.4,1.0,0.5,0.9],
                  "Green speed lines, afterimage trail, clock-fast particles"),
    "quicken": _sp("Quicken", [0.3,0.7,1.0,0.7],[0.5,0.85,1.0,0.9],
                    "Blue instant-reset flash, cooldown clear visual"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(rgba: list[float]) -> str:
    """Format RGBA list as C# ``new Color(r, g, b, a)``."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _cs_shape_block(shape: str) -> str:
    """Return C# code that configures ParticleSystem.ShapeModule."""
    shape_map = {
        "sphere": "shape.shapeType = ParticleSystemShapeType.Sphere;",
        "hemisphere": (
            "shape.shapeType = ParticleSystemShapeType.Hemisphere;\n"
            "            shape.rotation = new Vector3(-90f, 0f, 0f);"
        ),
        "circle": (
            "shape.shapeType = ParticleSystemShapeType.Circle;\n"
            "            shape.rotation = new Vector3(-90f, 0f, 0f);"
        ),
        "box": "shape.shapeType = ParticleSystemShapeType.Box;",
        "cone": "shape.shapeType = ParticleSystemShapeType.Cone;",
    }
    return shape_map.get(shape, shape_map["sphere"])


# Triggered effect params: (burst_count, speed, lifetime, size, color_override_or_None)
_TRIGGERED_PARAMS: dict[str, tuple] = {
    "shield":      (20, 4.0, 0.4, 0.08, None),
    "barrier":     (30, 1.5, 0.8, 0.05, None),
    "regen":       (40, 3.0, 0.5, 0.04, None),
    "fortify":     (15, 5.0, 0.3, 0.20, None),
    "thorns":      (35, 6.0, 0.3, 0.12, "new Color(1f, 0.4f, 0.2f, 1f)"),
    "second_wind": (80, 8.0, 1.0, 0.15, "new Color(1f, 1f, 0.8f, 1f)"),
    "undying":     (50, 5.0, 0.6, 0.18, None),
    "reflect":     (25, 7.0, 0.3, 0.10, "new Color(1f, 1f, 1f, 0.9f)"),
    "immunity":    (60, 3.0, 0.7, 0.06, "new Color(1f, 1f, 1f, 1f)"),
    "stealth":     (15, 1.0, 1.5, 0.40, "new Color(0.3f, 0.3f, 0.35f, 0.2f)"),
}


def _build_secondary_method_defensive(buff_type: str, cfg: dict) -> str:
    """Return C# PlayTriggeredEffect method for the buff type."""
    p = _TRIGGERED_PARAMS.get(buff_type, (20, 3.0, 0.5, 0.1, None))
    color_line = f"main.startColor = {p[4]};" if p[4] else "main.startColor = glowColor;"
    return f'''
    private void PlayTriggeredEffect()
    {{
        if (triggeredPS == null) return;
        var burst = new ParticleSystem.Burst(0f, {p[0]});
        triggeredPS.emission.SetBursts(new[] {{ burst }});
        var main = triggeredPS.main;
        main.startSpeed = {p[1]}f;
        main.startLifetime = {p[2]}f;
        main.startSize = {p[3]}f;
        {color_line}
        triggeredPS.Play();
    }}'''


def _build_debuff_update_method(debuff_type: str, cfg: dict) -> str:
    """Return C# method body for debuff-specific per-frame update."""
    methods: dict[str, str] = {
        "expose": '''
    private void UpdateDebuffVisual()
    {
        // Rotating reticle overhead
        reticleAngle += Time.deltaTime * 120f;
        if (secondaryPS != null && Random.value < 0.15f)
        {
            float rad = reticleAngle * Mathf.Deg2Rad;
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(Mathf.Cos(rad) * 0.3f, 2.0f, Mathf.Sin(rad) * 0.3f);
            ep.velocity = Vector3.down * 0.5f;
            secondaryPS.Emit(ep, 2);
        }
    }
    private float reticleAngle;''',
        "fragile": '''
    private void UpdateDebuffVisual()
    {
        // Glass crack shimmer on body surface
        if (secondaryPS != null && Random.value < 0.08f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + Random.insideUnitSphere * 0.6f;
            ep.velocity = Random.onUnitSphere * 0.3f;
            ep.startSize = 0.06f;
            secondaryPS.Emit(ep, 3);
        }
    }''',
        "armor_shred": '''
    private void UpdateDebuffVisual()
    {
        // Metal stripping particles falling off
        if (secondaryPS != null && Random.value < 0.1f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(
                Random.Range(-0.4f, 0.4f), Random.Range(0.3f, 1.5f), Random.Range(-0.4f, 0.4f));
            ep.velocity = Vector3.down * 2f + Random.insideUnitSphere * 0.5f;
            ep.startSize = 0.12f;
            secondaryPS.Emit(ep, 1);
        }
    }''',
        "brand_weakness": '''
    private void UpdateDebuffVisual()
    {
        // Pulsing brand-colored vulnerability mark
        pulseTimer += Time.deltaTime * 3f;
        float pulse = 0.7f + 0.3f * Mathf.Sin(pulseTimer);
        if (mainPS != null)
        {
            var main = mainPS.main;
            Color c = baseColor;
            c.a *= pulse;
            main.startColor = c;
        }
    }
    private float pulseTimer;''',
        "exhausted": '''
    private void UpdateDebuffVisual()
    {
        // Heavy breathing particles and gray motes
        if (secondaryPS != null && Random.value < 0.06f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(0f, 1.4f, 0.3f);
            ep.velocity = new Vector3(Random.Range(-0.2f, 0.2f), 0.5f, 0.5f);
            ep.startSize = 0.15f;
            secondaryPS.Emit(ep, 2);
        }
    }''',
        "sealed": '''
    private void UpdateDebuffVisual()
    {
        // Mystical lock particles circling above head
        sealAngle += Time.deltaTime * 60f;
        if (secondaryPS != null && Random.value < 0.1f)
        {
            float rad = sealAngle * Mathf.Deg2Rad;
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(Mathf.Cos(rad) * 0.4f, 2.2f, Mathf.Sin(rad) * 0.4f);
            ep.velocity = Vector3.up * 0.3f;
            secondaryPS.Emit(ep, 1);
        }
    }
    private float sealAngle;''',
        "grounded": '''
    private void UpdateDebuffVisual()
    {
        // Earth anchor particles at feet
        if (secondaryPS != null && Random.value < 0.12f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(
                Random.Range(-0.5f, 0.5f), -0.1f, Random.Range(-0.5f, 0.5f));
            ep.velocity = Vector3.up * 0.5f;
            ep.startSize = 0.15f;
            secondaryPS.Emit(ep, 2);
        }
    }''',
        "heal_block": '''
    private void UpdateDebuffVisual()
    {
        // Anti-heal particles forming X pattern
        healBlockTimer += Time.deltaTime;
        if (secondaryPS != null && Random.value < 0.1f)
        {
            float t = healBlockTimer * 2f;
            float xOff = Mathf.Sin(t) * 0.3f;
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(xOff, 1.8f, 0f);
            ep.velocity = new Vector3(-xOff * 2f, 0f, 0f);
            secondaryPS.Emit(ep, 1);
        }
    }
    private float healBlockTimer;''',
        "cursed": '''
    private void UpdateDebuffVisual()
    {
        // Dark curse marks orbiting body
        curseAngle += Time.deltaTime * 45f;
        if (secondaryPS != null && Random.value < 0.08f)
        {
            float rad = curseAngle * Mathf.Deg2Rad;
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(Mathf.Cos(rad) * 0.7f, 0.8f, Mathf.Sin(rad) * 0.7f);
            ep.velocity = Vector3.up * 0.2f;
            secondaryPS.Emit(ep, 2);
        }
    }
    private float curseAngle;''',
        "decay": '''
    private void UpdateDebuffVisual()
    {
        // Deterioration particles drifting downward
        if (secondaryPS != null && Random.value < 0.07f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(
                Random.Range(-0.5f, 0.5f), Random.Range(0.5f, 1.8f), Random.Range(-0.5f, 0.5f));
            ep.velocity = Vector3.down * 0.8f + Random.insideUnitSphere * 0.2f;
            ep.startSize = 0.08f;
            secondaryPS.Emit(ep, 1);
        }
    }''',
        "wither": '''
    private void UpdateDebuffVisual()
    {
        // Anti-life: green-to-black particles sinking
        if (secondaryPS != null && Random.value < 0.09f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + Random.insideUnitSphere * 0.8f;
            ep.velocity = Vector3.down * 1.2f;
            ep.startColor = Color.Lerp(new Color(0.2f, 0.5f, 0.1f, 0.8f), Color.black, Random.value);
            secondaryPS.Emit(ep, 2);
        }
    }''',
        "doom": '''
    private void UpdateDebuffVisual()
    {
        // Countdown ring pulsing with urgency
        doomPulse += Time.deltaTime * 4f;
        float pulse = 0.5f + 0.5f * Mathf.Abs(Mathf.Sin(doomPulse));
        if (mainPS != null)
        {
            var main = mainPS.main;
            main.startSize = 0.18f * (1f + pulse * 0.5f);
        }
        if (secondaryPS != null && Random.value < 0.15f * pulse)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + Vector3.up * 2.2f + Random.insideUnitSphere * 0.3f;
            ep.velocity = Vector3.up * 0.5f;
            secondaryPS.Emit(ep, 1);
        }
    }
    private float doomPulse;''',
        "marked_death": '''
    private void UpdateDebuffVisual()
    {
        // Skull mark hovering above
        if (secondaryPS != null && Random.value < 0.05f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + Vector3.up * 2.5f + Random.insideUnitSphere * 0.15f;
            ep.velocity = Random.insideUnitSphere * 0.2f;
            ep.startSize = 0.06f;
            secondaryPS.Emit(ep, 3);
        }
    }''',
        "condemned": '''
    private void UpdateDebuffVisual()
    {
        // Hourglass particles draining downward
        condemnTimer += Time.deltaTime;
        if (secondaryPS != null && Random.value < 0.12f)
        {
            bool topHalf = Random.value > 0.5f;
            float yBase = topHalf ? 2.4f : 2.0f;
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(
                Random.Range(-0.15f, 0.15f), yBase, Random.Range(-0.15f, 0.15f));
            ep.velocity = topHalf ? Vector3.down * 1.5f : Vector3.down * 0.3f;
            ep.startSize = 0.04f;
            secondaryPS.Emit(ep, 1);
        }
    }
    private float condemnTimer;''',
        "petrify": '''
    private void UpdateDebuffVisual()
    {
        // Stone spread creeping up from feet
        petrifyProgress = Mathf.Min(petrifyProgress + Time.deltaTime * 0.3f, 1f);
        float stoneHeight = Mathf.Lerp(0f, 1.8f, petrifyProgress);
        if (secondaryPS != null && Random.value < 0.15f)
        {
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(
                Random.Range(-0.4f, 0.4f), Random.Range(0f, stoneHeight), Random.Range(-0.4f, 0.4f));
            ep.velocity = Random.insideUnitSphere * 0.2f;
            ep.startSize = 0.08f;
            ep.startColor = new Color(0.55f, 0.52f, 0.5f, 0.9f);
            secondaryPS.Emit(ep, 3);
        }
    }
    private float petrifyProgress;''',
        "bound": '''
    private void UpdateDebuffVisual()
    {
        // Chain particles wrapping around body
        chainAngle += Time.deltaTime * 90f;
        if (secondaryPS != null && Random.value < 0.12f)
        {
            float rad = chainAngle * Mathf.Deg2Rad;
            float y = Mathf.PingPong(Time.time * 0.5f, 1.5f);
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(Mathf.Cos(rad) * 0.5f, y, Mathf.Sin(rad) * 0.5f);
            ep.velocity = new Vector3(-Mathf.Sin(rad), 0f, Mathf.Cos(rad)) * 1f;
            ep.startSize = 0.06f;
            secondaryPS.Emit(ep, 2);
        }
    }
    private float chainAngle;''',
        "confuse": '''
    private void UpdateDebuffVisual()
    {
        // Spiral dizzy particles above head
        dizzyAngle += Time.deltaTime * 180f;
        if (secondaryPS != null && Random.value < 0.15f)
        {
            float rad = dizzyAngle * Mathf.Deg2Rad;
            float r2 = 0.3f + 0.1f * Mathf.Sin(dizzyAngle * 0.5f * Mathf.Deg2Rad);
            var ep = new ParticleSystem.EmitParams();
            ep.position = transform.position + new Vector3(Mathf.Cos(rad) * r2, 2.0f + 0.1f * Mathf.Sin(dizzyAngle * 2f * Mathf.Deg2Rad), Mathf.Sin(rad) * r2);
            ep.velocity = Vector3.up * 0.2f;
            ep.startSize = 0.15f;
            secondaryPS.Emit(ep, 1);
        }
    }
    private float dizzyAngle;''',
    }
    return methods.get(debuff_type, '''
    private void UpdateDebuffVisual()
    {
        // Default debuff visual update
    }''')


# ---------------------------------------------------------------------------
# 1. Defensive Buff VFX
# ---------------------------------------------------------------------------


def generate_defensive_buff_vfx_script(
    buff_type: str = "shield",
) -> dict[str, Any]:
    """Generate DefensiveBuffVFXController MonoBehaviour.

    Covers: shield, barrier, regen, fortify, thorns, second_wind, undying,
    reflect, immunity, stealth.  Each buff type has unique primary particle
    visuals and a triggered secondary effect (e.g., absorption ripple,
    reflect flash, cleanse sparkle).

    Args:
        buff_type: One of the supported defensive buff types.  Defaults to
            ``shield``.

    Returns:
        Dict with ``script_path``, ``script_content``, ``next_steps``.
    """
    buff_type = buff_type.lower().strip()
    if buff_type not in DEFENSIVE_BUFF_CONFIGS:
        buff_type = "shield"
    cfg = DEFENSIVE_BUFF_CONFIGS[buff_type]
    buff_type = sanitize_cs_identifier(buff_type)
    triggered_method = _build_secondary_method_defensive(buff_type, cfg)
    shape_code = _cs_shape_block(cfg["shape"])

    # Build the buff config dictionary as a C# initializer
    buff_entries: list[str] = []
    for bt, bc in DEFENSIVE_BUFF_CONFIGS.items():
        bt = sanitize_cs_identifier(bt)
        buff_entries.append(
            f'            {{ "{bt}", new BuffConfig("{bc["display"]}", '
            f'{_fmt(bc["color"])}, {_fmt(bc["glow"])}, '
            f'{bc["rate"]}, {bc["lifetime"]}f, {bc["size"]}f, '
            f'{bc["radius"]}f) }},'
        )
    buff_dict_body = "\n".join(buff_entries)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Defensive buff VFX controller.  Supports: shield, barrier, regen,
/// fortify, thorns, second_wind, undying, reflect, immunity, stealth.
/// Default buff type: {buff_type} -- {cfg["desc"]}.
/// </summary>
public class DefensiveBuffVFXController : MonoBehaviour
{{
    // ----- Serialized -----
    [Header("Buff Settings")]
    [SerializeField] private string activeBuff = "{buff_type}";
    [SerializeField] private float intensity = 1.0f;

    [Header("Colors")]
    [SerializeField] private Color baseColor = {_fmt(cfg["color"])};
    [SerializeField] private Color glowColor = {_fmt(cfg["glow"])};

    // ----- Events (C# events, not EventBus) -----
    public event Action<string> OnBuffApplied;
    public event Action<string> OnBuffRemoved;
    public event Action<string> OnBuffTriggered;

    // ----- Runtime -----
    private ParticleSystem mainPS;
    private ParticleSystem triggeredPS;
    private Dictionary<string, Coroutine> activeBuffs = new Dictionary<string, Coroutine>();
    private float pulseTimer;

    // ----- Buff config struct -----
    [Serializable]
    private struct BuffConfig
    {{
        public string display;
        public Color color;
        public Color glow;
        public int rate;
        public float lifetime;
        public float size;
        public float radius;

        public BuffConfig(string display, Color color, Color glow, int rate, float lifetime, float size, float radius)
        {{
            this.display = display;
            this.color = color;
            this.glow = glow;
            this.rate = rate;
            this.lifetime = lifetime;
            this.size = size;
            this.radius = radius;
        }}
    }}

    private static readonly Dictionary<string, BuffConfig> BuffConfigs = new Dictionary<string, BuffConfig>
    {{
{buff_dict_body}
    }};

    // ================================================================
    // Lifecycle
    // ================================================================

    private void Awake()
    {{
        CreateMainParticleSystem();
        CreateTriggeredParticleSystem();
    }}

    private void Update()
    {{
        // Gentle pulse on the main emitter
        pulseTimer += Time.deltaTime * 2f;
        if (mainPS != null && mainPS.isPlaying)
        {{
            float pulse = 0.85f + 0.15f * Mathf.Sin(pulseTimer);
            var main = mainPS.main;
            main.startSizeMultiplier = GetCurrentConfig().size * pulse * intensity;
        }}
    }}

    // ================================================================
    // Public API
    // ================================================================

    /// <summary>Apply a defensive buff with optional duration (0 = permanent).</summary>
    public void ApplyDefensiveBuff(string buffType, float duration = 0f)
    {{
        buffType = buffType.ToLower();
        if (!BuffConfigs.ContainsKey(buffType)) buffType = "shield";

        // Remove previous instance if active
        if (activeBuffs.ContainsKey(buffType))
        {{
            if (activeBuffs[buffType] != null) StopCoroutine(activeBuffs[buffType]);
            activeBuffs.Remove(buffType);
        }}

        activeBuff = buffType;
        var cfg = BuffConfigs[buffType];
        baseColor = cfg.color;
        glowColor = cfg.glow;
        ConfigureMainPS(cfg);

        if (mainPS != null)
        {{
            mainPS.Clear();
            mainPS.Play();
        }}

        OnBuffApplied?.Invoke(buffType);

        if (duration > 0f)
        {{
            activeBuffs[buffType] = StartCoroutine(BuffDurationCoroutine(buffType, duration));
        }}
        else
        {{
            activeBuffs[buffType] = null;
        }}
    }}

    /// <summary>Remove a defensive buff.</summary>
    public void RemoveDefensiveBuff(string buffType)
    {{
        buffType = buffType.ToLower();
        if (activeBuffs.ContainsKey(buffType))
        {{
            if (activeBuffs[buffType] != null) StopCoroutine(activeBuffs[buffType]);
            activeBuffs.Remove(buffType);
        }}

        if (mainPS != null) mainPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        OnBuffRemoved?.Invoke(buffType);
    }}

    /// <summary>Signal that the buff was triggered (absorbed hit, reflected, etc.).</summary>
    public void TriggerBuff(string buffType)
    {{
        PlayTriggeredEffect();
        OnBuffTriggered?.Invoke(buffType);
    }}

    /// <summary>Set visual intensity (0-1).</summary>
    public void SetIntensity(float value)
    {{
        intensity = Mathf.Clamp01(value);
    }}

    // ================================================================
    // Internal
    // ================================================================

    private BuffConfig GetCurrentConfig()
    {{
        if (BuffConfigs.ContainsKey(activeBuff)) return BuffConfigs[activeBuff];
        return BuffConfigs["shield"];
    }}

    private IEnumerator BuffDurationCoroutine(string buffType, float duration)
    {{
        yield return new WaitForSeconds(duration);
        RemoveDefensiveBuff(buffType);
    }}

    private void ConfigureMainPS(BuffConfig cfg)
    {{
        if (mainPS == null) return;
        var main = mainPS.main;
        main.startLifetime = cfg.lifetime;
        main.startSize = cfg.size * intensity;
        main.startColor = cfg.color;
        main.maxParticles = Mathf.CeilToInt(cfg.rate * cfg.lifetime * 1.5f);

        var emission = mainPS.emission;
        emission.rateOverTime = cfg.rate * intensity;

        var shape = mainPS.shape;
        shape.radius = cfg.radius;
    }}

    private void CreateMainParticleSystem()
    {{
        GameObject psObj = new GameObject("DefBuff_Main");
        psObj.transform.SetParent(transform, false);
        mainPS = psObj.AddComponent<ParticleSystem>();

        var main = mainPS.main;
        main.duration = 5f;
        main.loop = true;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startLifetime = {cfg["lifetime"]}f;
        main.startSpeed = 1.0f;
        main.startSize = {cfg["size"]}f;
        main.startColor = baseColor;
        main.maxParticles = 500;

        var emission = mainPS.emission;
        emission.rateOverTime = {cfg["rate"]}f;

        var shape = mainPS.shape;
        {shape_code}
        shape.radius = {cfg["radius"]}f;

        var col = mainPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(baseColor, 0f), new GradientColorKey(glowColor, 0.5f), new GradientColorKey(baseColor, 1f) }},
            new GradientAlphaKey[] {{ new GradientAlphaKey(0f, 0f), new GradientAlphaKey(baseColor.a, 0.2f), new GradientAlphaKey(baseColor.a, 0.7f), new GradientAlphaKey(0f, 1f) }}
        );
        col.color = grad;

        var sizeOL = mainPS.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.3f, 1f, 1f));

        var renderer = mainPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material({_SHADER_FIND});
        renderer.material.SetColor("_BaseColor", baseColor);
    }}

    private void CreateTriggeredParticleSystem()
    {{
        GameObject psObj = new GameObject("DefBuff_Triggered");
        psObj.transform.SetParent(transform, false);
        triggeredPS = psObj.AddComponent<ParticleSystem>();

        var main = triggeredPS.main;
        main.duration = 0.5f;
        main.loop = false;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startLifetime = 0.5f;
        main.startSpeed = 3f;
        main.startSize = 0.1f;
        main.startColor = glowColor;
        main.maxParticles = 200;

        var emission = triggeredPS.emission;
        emission.rateOverTime = 0;

        var shape = triggeredPS.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.5f;

        var renderer = triggeredPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material({_SHADER_FIND});
        renderer.material.SetColor("_BaseColor", glowColor);
    }}
{triggered_method}

    private void OnDestroy()
    {{
        if (mainPS != null)
        {{
            var r = mainPS.GetComponent<ParticleSystemRenderer>();
            if (r != null && r.material != null) Destroy(r.material);
        }}
        if (triggeredPS != null)
        {{
            var r = triggeredPS.GetComponent<ParticleSystemRenderer>();
            if (r != null && r.material != null) Destroy(r.material);
        }}
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/StatusEffects/DefensiveBuffVFXController.cs",
        "script_content": script,
        "next_steps": [
            *STANDARD_NEXT_STEPS,
            f"Default buff: {cfg['display']} -- {cfg['desc']}",
            "API: ApplyDefensiveBuff(type, duration), RemoveDefensiveBuff(type), TriggerBuff(type)",
        ],
    }


# ---------------------------------------------------------------------------
# 2. Debuff VFX
# ---------------------------------------------------------------------------


def generate_debuff_vfx_script(
    debuff_type: str = "expose",
) -> dict[str, Any]:
    """Generate DebuffVFXController MonoBehaviour.

    Covers: expose, fragile, armor_shred, brand_weakness, exhausted, sealed,
    grounded, heal_block, cursed, decay, wither, doom, marked_death,
    condemned, petrify, bound, confuse.  Each debuff has unique primary
    particles and a per-frame secondary visual update.

    Args:
        debuff_type: One of the supported debuff types.  Defaults to
            ``expose``.

    Returns:
        Dict with ``script_path``, ``script_content``, ``next_steps``.
    """
    debuff_type = debuff_type.lower().strip()
    if debuff_type not in DEBUFF_CONFIGS:
        debuff_type = "expose"
    cfg = DEBUFF_CONFIGS[debuff_type]
    debuff_type = sanitize_cs_identifier(debuff_type)
    update_method = _build_debuff_update_method(debuff_type, cfg)
    shape_code = _cs_shape_block(cfg["shape"])

    # Build debuff config dictionary as C# initializer
    debuff_entries: list[str] = []
    for dt, dc in DEBUFF_CONFIGS.items():
        debuff_entries.append(
            f'            {{ "{dt}", new DebuffConfig("{dc["display"]}", '
            f'{_fmt(dc["color"])}, {_fmt(dc["glow"])}, '
            f'{dc["rate"]}, {dc["lifetime"]}f, {dc["size"]}f) }},'
        )
    debuff_dict_body = "\n".join(debuff_entries)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Debuff VFX controller.  Supports: expose, fragile, armor_shred,
/// brand_weakness, exhausted, sealed, grounded, heal_block, cursed,
/// decay, wither, doom, marked_death, condemned, petrify, bound, confuse.
/// Default debuff type: {debuff_type} -- {cfg["desc"]}.
/// </summary>
public class DebuffVFXController : MonoBehaviour
{{
    // ----- Serialized -----
    [Header("Debuff Settings")]
    [SerializeField] private string activeDebuff = "{debuff_type}";
    [SerializeField] private float intensity = 1.0f;

    [Header("Colors")]
    [SerializeField] private Color baseColor = {_fmt(cfg["color"])};
    [SerializeField] private Color glowColor = {_fmt(cfg["glow"])};

    // ----- Events -----
    public event Action<string> OnDebuffApplied;
    public event Action<string> OnDebuffRemoved;
    public event Action<string> OnDebuffTriggered;

    // ----- Runtime -----
    private ParticleSystem mainPS;
    private ParticleSystem secondaryPS;
    private Dictionary<string, Coroutine> activeDebuffs = new Dictionary<string, Coroutine>();

    // ----- Config struct -----
    [Serializable]
    private struct DebuffConfig
    {{
        public string display;
        public Color color;
        public Color glow;
        public int rate;
        public float lifetime;
        public float size;

        public DebuffConfig(string display, Color color, Color glow, int rate, float lifetime, float size)
        {{
            this.display = display;
            this.color = color;
            this.glow = glow;
            this.rate = rate;
            this.lifetime = lifetime;
            this.size = size;
        }}
    }}

    private static readonly Dictionary<string, DebuffConfig> DebuffConfigs = new Dictionary<string, DebuffConfig>
    {{
{debuff_dict_body}
    }};

    // ================================================================
    // Lifecycle
    // ================================================================

    private void Awake()
    {{
        CreateMainParticleSystem();
        CreateSecondaryParticleSystem();
    }}

    private void Update()
    {{
        if (mainPS != null && mainPS.isPlaying)
        {{
            UpdateDebuffVisual();
        }}
    }}

    // ================================================================
    // Public API
    // ================================================================

    /// <summary>Apply a debuff with optional duration (0 = permanent until removed).</summary>
    public void ApplyDebuff(string debuffType, float duration = 0f)
    {{
        debuffType = debuffType.ToLower();
        if (!DebuffConfigs.ContainsKey(debuffType)) debuffType = "expose";

        if (activeDebuffs.ContainsKey(debuffType))
        {{
            if (activeDebuffs[debuffType] != null) StopCoroutine(activeDebuffs[debuffType]);
            activeDebuffs.Remove(debuffType);
        }}

        activeDebuff = debuffType;
        var cfg = DebuffConfigs[debuffType];
        baseColor = cfg.color;
        glowColor = cfg.glow;
        ConfigureMainPS(cfg);

        if (mainPS != null)
        {{
            mainPS.Clear();
            mainPS.Play();
        }}

        OnDebuffApplied?.Invoke(debuffType);

        if (duration > 0f)
        {{
            activeDebuffs[debuffType] = StartCoroutine(DebuffDurationCoroutine(debuffType, duration));
        }}
        else
        {{
            activeDebuffs[debuffType] = null;
        }}
    }}

    /// <summary>Remove a debuff.</summary>
    public void RemoveDebuff(string debuffType)
    {{
        debuffType = debuffType.ToLower();
        if (activeDebuffs.ContainsKey(debuffType))
        {{
            if (activeDebuffs[debuffType] != null) StopCoroutine(activeDebuffs[debuffType]);
            activeDebuffs.Remove(debuffType);
        }}

        if (mainPS != null) mainPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        if (secondaryPS != null) secondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        OnDebuffRemoved?.Invoke(debuffType);
    }}

    /// <summary>Signal that the debuff was triggered (e.g. expose damage amp applied).</summary>
    public void TriggerDebuff(string debuffType)
    {{
        // Burst flash on trigger
        if (triggeredBurst != null) return;
        StartCoroutine(TriggerFlash());
        OnDebuffTriggered?.Invoke(debuffType);
    }}

    /// <summary>Set visual intensity (0-1).</summary>
    public void SetIntensity(float value)
    {{
        intensity = Mathf.Clamp01(value);
    }}

    // ================================================================
    // Internal
    // ================================================================

    private Coroutine triggeredBurst;

    private DebuffConfig GetCurrentConfig()
    {{
        if (DebuffConfigs.ContainsKey(activeDebuff)) return DebuffConfigs[activeDebuff];
        return DebuffConfigs["expose"];
    }}

    private IEnumerator DebuffDurationCoroutine(string debuffType, float duration)
    {{
        yield return new WaitForSeconds(duration);
        RemoveDebuff(debuffType);
    }}

    private IEnumerator TriggerFlash()
    {{
        triggeredBurst = StartCoroutine(TriggerFlashInner());
        yield break;
    }}

    private IEnumerator TriggerFlashInner()
    {{
        if (mainPS != null)
        {{
            var emission = mainPS.emission;
            float originalRate = emission.rateOverTime.constant;
            emission.rateOverTime = originalRate * 3f;
            yield return new WaitForSeconds(0.15f);
            emission.rateOverTime = originalRate;
        }}
        triggeredBurst = null;
    }}

    private void ConfigureMainPS(DebuffConfig cfg)
    {{
        if (mainPS == null) return;
        var main = mainPS.main;
        main.startLifetime = cfg.lifetime;
        main.startSize = cfg.size * intensity;
        main.startColor = cfg.color;
        main.maxParticles = Mathf.CeilToInt(cfg.rate * cfg.lifetime * 1.5f);

        var emission = mainPS.emission;
        emission.rateOverTime = cfg.rate * intensity;
    }}

    private void CreateMainParticleSystem()
    {{
        GameObject psObj = new GameObject("Debuff_Main");
        psObj.transform.SetParent(transform, false);
        mainPS = psObj.AddComponent<ParticleSystem>();

        var main = mainPS.main;
        main.duration = 5f;
        main.loop = true;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startLifetime = {cfg["lifetime"]}f;
        main.startSpeed = 0.8f;
        main.startSize = {cfg["size"]}f;
        main.startColor = baseColor;
        main.maxParticles = 400;

        var emission = mainPS.emission;
        emission.rateOverTime = {cfg["rate"]}f;

        var shape = mainPS.shape;
        {shape_code}
        shape.radius = 0.8f;

        var col = mainPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(baseColor, 0f), new GradientColorKey(glowColor, 0.6f), new GradientColorKey(baseColor, 1f) }},
            new GradientAlphaKey[] {{ new GradientAlphaKey(0f, 0f), new GradientAlphaKey(baseColor.a, 0.15f), new GradientAlphaKey(baseColor.a * 0.6f, 0.8f), new GradientAlphaKey(0f, 1f) }}
        );
        col.color = grad;

        var renderer = mainPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material({_SHADER_FIND});
        renderer.material.SetColor("_BaseColor", baseColor);
    }}

    private void CreateSecondaryParticleSystem()
    {{
        GameObject psObj = new GameObject("Debuff_Secondary");
        psObj.transform.SetParent(transform, false);
        secondaryPS = psObj.AddComponent<ParticleSystem>();

        var main = secondaryPS.main;
        main.duration = 5f;
        main.loop = true;
        main.playOnAwake = true;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startLifetime = 1.0f;
        main.startSpeed = 0.5f;
        main.startSize = 0.08f;
        main.startColor = glowColor;
        main.maxParticles = 100;

        var emission = secondaryPS.emission;
        emission.rateOverTime = 0; // Emit manually in UpdateDebuffVisual

        var renderer = secondaryPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material({_SHADER_FIND});
        renderer.material.SetColor("_BaseColor", glowColor);
    }}
{update_method}

    private void OnDestroy()
    {{
        if (mainPS != null)
        {{
            var r = mainPS.GetComponent<ParticleSystemRenderer>();
            if (r != null && r.material != null) Destroy(r.material);
        }}
        if (secondaryPS != null)
        {{
            var r = secondaryPS.GetComponent<ParticleSystemRenderer>();
            if (r != null && r.material != null) Destroy(r.material);
        }}
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/StatusEffects/DebuffVFXController.cs",
        "script_content": script,
        "next_steps": [
            *STANDARD_NEXT_STEPS,
            f"Default debuff: {cfg['display']} -- {cfg['desc']}",
            "API: ApplyDebuff(type, duration), RemoveDebuff(type), TriggerDebuff(type)",
        ],
    }


# ---------------------------------------------------------------------------
# 3. Stat Modifier VFX
# ---------------------------------------------------------------------------


def generate_stat_modifier_vfx_script() -> dict[str, Any]:
    """Generate StatModifierVFXController MonoBehaviour.

    Handles all stat up/down modifiers (attack, defense, speed, accuracy,
    evasion, crit_rate, crit_damage) with consistent arrow-up/arrow-down
    particle templates color-coded per stat, plus unique secondary particles.

    Also handles special stat modifiers: lifesteal, empower, focus,
    berserk, haste, quicken.

    Returns:
        Dict with ``script_path``, ``script_content``, ``next_steps``.
    """
    # Build stat config entries
    stat_entries: list[str] = []
    for sname, sc in STAT_MOD_CONFIGS.items():
        stat_entries.append(
            f'            {{ "{sname}", new StatModConfig("{sc["display"]}", '
            f'{_fmt(sc["up_color"])}, {_fmt(sc["down_color"])}, '
            f'"{sc["position"]}") }},'
        )
    stat_dict_body = "\n".join(stat_entries)

    # Build special stat config entries
    special_entries: list[str] = []
    for sname, sc in SPECIAL_STAT_CONFIGS.items():
        special_entries.append(
            f'            {{ "{sname}", new SpecialModConfig("{sc["display"]}", '
            f'{_fmt(sc["color"])}, {_fmt(sc["glow"])}) }},'
        )
    special_dict_body = "\n".join(special_entries)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Stat modifier VFX controller.  Handles stat up/down (attack, defense,
/// speed, accuracy, evasion, crit_rate, crit_damage) with arrow particles
/// and color coding.  Also handles special modifiers: lifesteal, empower,
/// focus, berserk, haste, quicken.
/// </summary>
public class StatModifierVFXController : MonoBehaviour
{{
    // ----- Serialized -----
    [Header("Settings")]
    [SerializeField] private float intensity = 1.0f;
    [SerializeField] private float arrowSpeed = 2.0f;
    [SerializeField] private float arrowLifetime = 0.8f;

    // ----- Events -----
    public event Action<string, bool> OnStatModApplied;   // (statType, isUp)
    public event Action<string> OnStatModRemoved;

    // ----- Runtime -----
    private Dictionary<string, ActiveModState> activeMods = new Dictionary<string, ActiveModState>();
    private Dictionary<string, ParticleSystem> specialModPS = new Dictionary<string, ParticleSystem>();

    private struct ActiveModState
    {{
        public bool isUp;
        public ParticleSystem arrowPS;
        public ParticleSystem secondaryPS;
        public Coroutine durationCoroutine;
    }}

    // ----- Stat config -----
    [Serializable]
    private struct StatModConfig
    {{
        public string display;
        public Color upColor;
        public Color downColor;
        public string position;

        public StatModConfig(string display, Color upColor, Color downColor, string position)
        {{
            this.display = display;
            this.upColor = upColor;
            this.downColor = downColor;
            this.position = position;
        }}
    }}

    [Serializable]
    private struct SpecialModConfig
    {{
        public string display;
        public Color color;
        public Color glow;

        public SpecialModConfig(string display, Color color, Color glow)
        {{
            this.display = display;
            this.color = color;
            this.glow = glow;
        }}
    }}

    private static readonly Dictionary<string, StatModConfig> StatConfigs = new Dictionary<string, StatModConfig>
    {{
{stat_dict_body}
    }};

    private static readonly Dictionary<string, SpecialModConfig> SpecialConfigs = new Dictionary<string, SpecialModConfig>
    {{
{special_dict_body}
    }};

    // Position offsets for stat VFX attachment points
    private static readonly Dictionary<string, Vector3> PositionOffsets = new Dictionary<string, Vector3>
    {{
        {{ "weapon_hand", new Vector3(0.5f, 0.9f, 0f) }},
        {{ "weapon", new Vector3(0.5f, 0.9f, 0f) }},
        {{ "torso", new Vector3(0f, 1.0f, 0f) }},
        {{ "feet", new Vector3(0f, 0.05f, 0f) }},
        {{ "eyes", new Vector3(0f, 1.7f, 0.15f) }},
        {{ "body", new Vector3(0f, 0.9f, 0f) }},
    }};

    // ================================================================
    // Lifecycle
    // ================================================================

    private void Update()
    {{
        UpdateSpecialModifiers();
    }}

    // ================================================================
    // Public API
    // ================================================================

    /// <summary>Apply a standard stat modifier (up or down) with optional duration.</summary>
    public void ApplyStatMod(string statType, bool isUp, float duration = 0f)
    {{
        statType = statType.ToLower();

        // Check if it is a special modifier
        if (SpecialConfigs.ContainsKey(statType))
        {{
            ApplySpecialMod(statType, duration);
            return;
        }}

        if (!StatConfigs.ContainsKey(statType)) return;

        // Remove existing if present
        RemoveStatMod(statType);

        var cfg = StatConfigs[statType];
        Color color = isUp ? cfg.upColor : cfg.downColor;
        Vector3 offset = GetPositionOffset(cfg.position);

        // Create arrow particle system
        ParticleSystem arrowPS = CreateArrowPS(statType, isUp, color, offset);
        ParticleSystem secPS = CreateStatSecondaryPS(statType, isUp, color, offset);

        var state = new ActiveModState
        {{
            isUp = isUp,
            arrowPS = arrowPS,
            secondaryPS = secPS,
            durationCoroutine = null,
        }};

        if (duration > 0f)
        {{
            state.durationCoroutine = StartCoroutine(StatModDuration(statType, duration));
        }}

        activeMods[statType] = state;
        OnStatModApplied?.Invoke(statType, isUp);
    }}

    /// <summary>Remove a stat modifier.</summary>
    public void RemoveStatMod(string statType)
    {{
        statType = statType.ToLower();

        // Check special mods
        if (specialModPS.ContainsKey(statType))
        {{
            RemoveSpecialMod(statType);
            return;
        }}

        if (!activeMods.ContainsKey(statType)) return;

        var state = activeMods[statType];
        if (state.durationCoroutine != null) StopCoroutine(state.durationCoroutine);
        if (state.arrowPS != null)
        {{
            state.arrowPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            Destroy(state.arrowPS.gameObject, 2f);
        }}
        if (state.secondaryPS != null)
        {{
            state.secondaryPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            Destroy(state.secondaryPS.gameObject, 2f);
        }}
        activeMods.Remove(statType);
        OnStatModRemoved?.Invoke(statType);
    }}

    // ================================================================
    // Arrow Particle System (shared template)
    // ================================================================

    private ParticleSystem CreateArrowPS(string statType, bool isUp, Color color, Vector3 offset)
    {{
        string label = isUp ? "Up" : "Down";
        GameObject psObj = new GameObject($"StatMod_{{statType}}_{{label}}");
        psObj.transform.SetParent(transform, false);
        psObj.transform.localPosition = offset;

        ParticleSystem ps = psObj.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.duration = 5f;
        main.loop = true;
        main.playOnAwake = true;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startLifetime = arrowLifetime;
        main.startSpeed = isUp ? arrowSpeed : -arrowSpeed;
        main.startSize = 0.1f;
        main.startColor = color;
        main.maxParticles = 100;
        main.gravityModifier = isUp ? -0.2f : 0.2f;

        var emission = ps.emission;
        emission.rateOverTime = 15f * intensity;

        var shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = 0.15f;
        shape.rotation = new Vector3(-90f, 0f, 0f);

        // Velocity direction: up arrows go up, down arrows go down
        var vel = ps.velocityOverLifetime;
        vel.enabled = true;
        vel.y = isUp ? new ParticleSystem.MinMaxCurve(1.5f, 2.5f) : new ParticleSystem.MinMaxCurve(-2.5f, -1.5f);

        var col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(color, 0f), new GradientColorKey(color, 1f) }},
            new GradientAlphaKey[] {{ new GradientAlphaKey(0.8f, 0f), new GradientAlphaKey(0f, 1f) }}
        );
        col.color = grad;

        var sizeOL = ps.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material({_SHADER_FIND});
        renderer.material.SetColor("_BaseColor", color);

        return ps;
    }}

    // ================================================================
    // Stat-Specific Secondary Particles
    // ================================================================

    private ParticleSystem CreateStatSecondaryPS(string statType, bool isUp, Color color, Vector3 offset)
    {{
        GameObject psObj = new GameObject($"StatMod_{{statType}}_Sec");
        psObj.transform.SetParent(transform, false);
        psObj.transform.localPosition = offset;

        ParticleSystem ps = psObj.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.duration = 5f;
        main.loop = true;
        main.playOnAwake = true;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startLifetime = 1.0f;
        main.startSpeed = 0.5f;
        main.startSize = 0.06f;
        main.startColor = color;
        main.maxParticles = 60;

        var emission = ps.emission;
        emission.rateOverTime = 8f * intensity;

        var shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.2f;

        // Per-stat secondary customization
        ConfigureStatSecondary(ps, statType, isUp, color);

        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material({_SHADER_FIND});
        Color secColor = color;
        secColor.a *= 0.6f;
        renderer.material.SetColor("_BaseColor", secColor);

        return ps;
    }}

    private void ConfigureStatSecondary(ParticleSystem ps, string statType, bool isUp, Color color)
    {{
        var main = ps.main;
        var emission = ps.emission;

        switch (statType)
        {{
            case "attack":
                // Weapon glow sparks
                main.startSpeed = isUp ? 3f : 0.3f;
                main.startSize = isUp ? 0.08f : 0.04f;
                emission.rateOverTime = isUp ? 20f : 5f;
                break;

            case "defense":
                // Shield icon particles at torso
                main.startSpeed = 0.2f;
                main.startLifetime = 2f;
                main.startSize = isUp ? 0.15f : 0.06f;
                emission.rateOverTime = 10f;
                break;

            case "speed":
                // Wind lines (up) or chain particles (down)
                main.startSpeed = isUp ? 4f : 0.5f;
                main.startLifetime = isUp ? 0.4f : 1.5f;
                main.startSize = isUp ? 0.04f : 0.08f;
                emission.rateOverTime = isUp ? 30f : 8f;
                break;

            case "accuracy":
                // Crosshair tighten (up) or blur (down)
                main.startSpeed = isUp ? 0.1f : 2f;
                main.startLifetime = isUp ? 1.5f : 0.5f;
                main.startSize = isUp ? 0.03f : 0.2f;
                emission.rateOverTime = isUp ? 8f : 15f;
                break;

            case "evasion":
                // Afterimage (up) or slow trail (down)
                main.startSpeed = isUp ? 2f : 0.2f;
                main.startLifetime = isUp ? 0.3f : 2f;
                main.startSize = isUp ? 0.12f : 0.1f;
                emission.rateOverTime = isUp ? 25f : 6f;
                break;

            case "crit_rate":
                // Star sparkle (up) or dim (down)
                main.startSpeed = isUp ? 1.5f : 0.3f;
                main.startLifetime = isUp ? 0.6f : 1.2f;
                main.startSize = isUp ? 0.1f : 0.04f;
                emission.rateOverTime = isUp ? 15f : 4f;
                break;

            case "crit_damage":
                // Explosion glow (up) or fizzle (down)
                main.startSpeed = isUp ? 3f : 0.5f;
                main.startLifetime = isUp ? 0.5f : 1f;
                main.startSize = isUp ? 0.15f : 0.05f;
                emission.rateOverTime = isUp ? 18f : 5f;
                break;
        }}
    }}

    // ================================================================
    // Special Modifiers
    // ================================================================

    private void ApplySpecialMod(string modType, float duration)
    {{
        RemoveSpecialMod(modType);

        if (!SpecialConfigs.ContainsKey(modType)) return;
        var cfg = SpecialConfigs[modType];

        ParticleSystem ps = CreateSpecialModPS(modType, cfg.color, cfg.glow);
        specialModPS[modType] = ps;

        if (duration > 0f)
        {{
            StartCoroutine(SpecialModDuration(modType, duration));
        }}

        OnStatModApplied?.Invoke(modType, true);
    }}

    private void RemoveSpecialMod(string modType)
    {{
        if (!specialModPS.ContainsKey(modType)) return;
        var ps = specialModPS[modType];
        if (ps != null)
        {{
            ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            Destroy(ps.gameObject, 2f);
        }}
        specialModPS.Remove(modType);
        OnStatModRemoved?.Invoke(modType);
    }}

    private ParticleSystem CreateSpecialModPS(string modType, Color color, Color glow)
    {{
        GameObject psObj = new GameObject($"SpecialMod_{{modType}}");
        psObj.transform.SetParent(transform, false);

        ParticleSystem ps = psObj.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.duration = 5f;
        main.loop = true;
        main.playOnAwake = true;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startColor = color;
        main.maxParticles = 200;

        var emission = ps.emission;
        var shape = ps.shape;

        // Type-specific configuration
        switch (modType)
        {{
            case "lifesteal":
                // Red drain particles converging inward
                main.startLifetime = 0.6f;
                main.startSpeed = 3f;
                main.startSize = 0.06f;
                emission.rateOverTime = 25f * intensity;
                shape.shapeType = ParticleSystemShapeType.Sphere;
                shape.radius = 1.5f;
                psObj.transform.localPosition = new Vector3(0f, 0.9f, 0f);
                var velLS = ps.velocityOverLifetime;
                velLS.enabled = true;
                velLS.radial = -4f;
                break;

            case "empower":
                // Golden weapon glow + amplification aura
                main.startLifetime = 1.2f;
                main.startSpeed = 0.5f;
                main.startSize = 0.12f;
                emission.rateOverTime = 20f * intensity;
                shape.shapeType = ParticleSystemShapeType.Sphere;
                shape.radius = 0.3f;
                psObj.transform.localPosition = new Vector3(0.5f, 0.9f, 0f);
                break;

            case "focus":
                // Crosshair lens flare near eyes
                main.startLifetime = 1.5f;
                main.startSpeed = 0.1f;
                main.startSize = 0.04f;
                emission.rateOverTime = 12f * intensity;
                shape.shapeType = ParticleSystemShapeType.Circle;
                shape.radius = 0.1f;
                psObj.transform.localPosition = new Vector3(0f, 1.7f, 0.15f);
                break;

            case "berserk":
                // Red rage aura with pulsing fire
                main.startLifetime = 0.8f;
                main.startSpeed = 2f;
                main.startSize = 0.2f;
                emission.rateOverTime = 50f * intensity;
                shape.shapeType = ParticleSystemShapeType.Sphere;
                shape.radius = 0.8f;
                psObj.transform.localPosition = new Vector3(0f, 0.9f, 0f);
                main.gravityModifier = -0.5f;
                break;

            case "haste":
                // Green speed lines trailing behind
                main.startLifetime = 0.4f;
                main.startSpeed = 5f;
                main.startSize = 0.04f;
                emission.rateOverTime = 40f * intensity;
                shape.shapeType = ParticleSystemShapeType.Cone;
                shape.angle = 10f;
                shape.radius = 0.2f;
                psObj.transform.localPosition = new Vector3(0f, 0.9f, -0.5f);
                psObj.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
                break;

            case "quicken":
                // Blue instant-reset flash burst
                main.startLifetime = 0.5f;
                main.startSpeed = 4f;
                main.startSize = 0.08f;
                emission.rateOverTime = 30f * intensity;
                shape.shapeType = ParticleSystemShapeType.Sphere;
                shape.radius = 0.5f;
                psObj.transform.localPosition = new Vector3(0f, 0.9f, 0f);
                break;
        }}

        // Color over lifetime gradient
        var col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(color, 0f), new GradientColorKey(glow, 0.5f), new GradientColorKey(color, 1f) }},
            new GradientAlphaKey[] {{ new GradientAlphaKey(0.9f, 0f), new GradientAlphaKey(0.6f, 0.5f), new GradientAlphaKey(0f, 1f) }}
        );
        col.color = grad;

        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material({_SHADER_FIND});
        renderer.material.SetColor("_BaseColor", color);

        return ps;
    }}

    // ================================================================
    // Special Modifier Per-Frame Updates
    // ================================================================

    private void UpdateSpecialModifiers()
    {{
        // Lifesteal: pulse inward when active
        if (specialModPS.ContainsKey("lifesteal") && specialModPS["lifesteal"] != null)
        {{
            // Particles already configured with radial velocity inward
        }}

        // Berserk: intensify over time
        if (specialModPS.ContainsKey("berserk") && specialModPS["berserk"] != null)
        {{
            berserkPulse += Time.deltaTime * 6f;
            float pulse = 1f + 0.3f * Mathf.Abs(Mathf.Sin(berserkPulse));
            var main = specialModPS["berserk"].main;
            main.startSizeMultiplier = 0.2f * pulse;
        }}

        // Haste: afterimage shimmer
        if (specialModPS.ContainsKey("haste") && specialModPS["haste"] != null)
        {{
            // Speed lines follow character velocity direction
        }}
    }}
    private float berserkPulse;

    // ================================================================
    // Duration Coroutines
    // ================================================================

    private IEnumerator StatModDuration(string statType, float duration)
    {{
        yield return new WaitForSeconds(duration);
        RemoveStatMod(statType);
    }}

    private IEnumerator SpecialModDuration(string modType, float duration)
    {{
        yield return new WaitForSeconds(duration);
        RemoveSpecialMod(modType);
    }}

    // ================================================================
    // Helpers
    // ================================================================

    private Vector3 GetPositionOffset(string position)
    {{
        if (PositionOffsets.ContainsKey(position)) return PositionOffsets[position];
        return Vector3.up * 0.9f;
    }}

    /// <summary>Set visual intensity (0-1).</summary>
    public void SetIntensity(float value)
    {{
        intensity = Mathf.Clamp01(value);
    }}

    private void OnDestroy()
    {{
        // Clean up all active mod particle systems
        foreach (var kvp in activeMods)
        {{
            if (kvp.Value.arrowPS != null)
            {{
                var r = kvp.Value.arrowPS.GetComponent<ParticleSystemRenderer>();
                if (r != null && r.material != null) Destroy(r.material);
                Destroy(kvp.Value.arrowPS.gameObject);
            }}
            if (kvp.Value.secondaryPS != null)
            {{
                var r = kvp.Value.secondaryPS.GetComponent<ParticleSystemRenderer>();
                if (r != null && r.material != null) Destroy(r.material);
                Destroy(kvp.Value.secondaryPS.gameObject);
            }}
        }}
        foreach (var kvp in specialModPS)
        {{
            if (kvp.Value != null)
            {{
                var r = kvp.Value.GetComponent<ParticleSystemRenderer>();
                if (r != null && r.material != null) Destroy(r.material);
                Destroy(kvp.Value.gameObject);
            }}
        }}
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/StatusEffects/StatModifierVFXController.cs",
        "script_content": script,
        "next_steps": [
            *STANDARD_NEXT_STEPS,
            "Stats: attack, defense, speed, accuracy, evasion, crit_rate, crit_damage",
            "Special: lifesteal, empower, focus, berserk, haste, quicken",
            "API: ApplyStatMod(statType, isUp, duration), RemoveStatMod(statType)",
        ],
    }
