"""Monster VFX C# template generators for Unity -- VeilBreakers named monsters.

Covers signature VFX for all 20 named monsters, hybrid brand VFX for 6
hybrid brands, and execute threshold visual mechanics.

Each function returns a dict with ``script_path``, ``script_content``, and
``next_steps``.  Generated C# uses ParticleSystem (NOT VisualEffect),
PrimeTween (NOT DOTween), C# events (NOT EventBus), and targets Unity
2022.3+ URP with ``Universal Render Pipeline/Particles/Unlit`` shader.

Exports:
    generate_monster_signature_vfx_script   -- per-monster signature VFX
    generate_hybrid_brand_vfx_script        -- 6 hybrid brand VFX
    generate_execute_threshold_vfx_script   -- execute threshold indicators
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

# ---------------------------------------------------------------------------
# Canonical brand color palette from BrandSystem.cs -- ALL VFX must use these
# Defined locally to avoid circular/missing imports across template modules.
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

BRAND_DARK_COLORS: dict[str, list[float]] = {
    "IRON":   [0.31, 0.35, 0.39, 1.0],
    "SAVAGE": [0.47, 0.10, 0.10, 1.0],
    "SURGE":  [0.12, 0.31, 0.55, 1.0],
    "VENOM":  [0.16, 0.39, 0.12, 1.0],
    "DREAD":  [0.27, 0.12, 0.39, 1.0],
    "LEECH":  [0.35, 0.08, 0.20, 1.0],
    "GRACE":  [0.63, 0.63, 0.71, 1.0],
    "MEND":   [0.55, 0.43, 0.16, 1.0],
    "RUIN":   [0.63, 0.27, 0.08, 1.0],
    "VOID":   [0.06, 0.02, 0.10, 1.0],
}

ALL_BRANDS = list(BRAND_PRIMARY_COLORS.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]

# ---------------------------------------------------------------------------
# Brand helpers
# ---------------------------------------------------------------------------


def _fmt_color(rgba: list[float] | tuple[float, ...]) -> str:
    """Format RGBA as C# ``new Color(r, g, b, a)``."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _blend_colors(a: list[float], b: list[float], t: float = 0.5) -> list[float]:
    """Linearly blend two RGBA color lists."""
    return [a[i] * (1.0 - t) + b[i] * t for i in range(4)]


def _brand_colors_cs_dict(color_map: dict[str, list[float]], var_name: str) -> str:
    """Build a C# Dictionary<string, Color> initializer."""
    lines = [f"        private static readonly Dictionary<string, Color> {var_name} = new Dictionary<string, Color>"]
    lines.append("        {")
    for brand, rgba in color_map.items():
        lines.append(f'            {{ "{brand}", {_fmt_color(rgba)} }},')
    lines.append("        };")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Monster VFX configuration data -- all 20 named monsters
# ---------------------------------------------------------------------------

# Each entry: brands, abilities list of (name, description, particle config)
MONSTER_VFX_CONFIGS: dict[str, dict[str, Any]] = {
    "bloodshade": {
        "brands": ["VOID", "DREAD"],
        "abilities": [
            ("ShadowPhase", "Shadow phase teleport VFX", {"rate": 80, "lifetime": 1.2, "size": 0.6, "shape": "Sphere", "gravity": 0.0, "burst": 60, "speed": 3.0}),
            ("SoulSiphon", "Drain beam from target to self", {"rate": 120, "lifetime": 0.8, "size": 0.15, "shape": "Cone", "gravity": 0.0, "burst": 0, "speed": 8.0}),
            ("ChoirOfDying", "AOE fear ring expanding outward", {"rate": 200, "lifetime": 2.0, "size": 0.4, "shape": "Circle", "gravity": 0.0, "burst": 150, "speed": 5.0}),
        ],
    },
    "chainbound": {
        "brands": ["IRON", "CORROSIVE"],
        "abilities": [
            ("ChainTrail", "Rusty chain particle trail on movement", {"rate": 60, "lifetime": 1.5, "size": 0.2, "shape": "Edge", "gravity": -0.5, "burst": 0, "speed": 1.0}),
            ("IronBind", "Shackle VFX locking target in place", {"rate": 100, "lifetime": 0.6, "size": 0.3, "shape": "Circle", "gravity": 0.0, "burst": 80, "speed": 6.0}),
            ("EternalImprisonment", "Cage of iron bars rising from ground", {"rate": 150, "lifetime": 2.5, "size": 0.15, "shape": "Cone", "gravity": -1.0, "burst": 120, "speed": 4.0}),
        ],
    },
    "corrodex": {
        "brands": ["GRACE", "SAVAGE"],
        "abilities": [
            ("AcidDrip", "Acid drip particles falling from body", {"rate": 40, "lifetime": 2.0, "size": 0.1, "shape": "Sphere", "gravity": -2.0, "burst": 0, "speed": 0.5}),
            ("CorrosionSpread", "Dissolving corrosion spreading on surface", {"rate": 90, "lifetime": 3.0, "size": 0.35, "shape": "Circle", "gravity": 0.0, "burst": 60, "speed": 2.0}),
            ("NobleSacrifice", "Golden burst of purifying energy", {"rate": 300, "lifetime": 1.0, "size": 0.5, "shape": "Sphere", "gravity": 0.0, "burst": 250, "speed": 8.0}),
        ],
    },
    "crackling": {
        "brands": ["SURGE", "CORROSIVE"],
        "abilities": [
            ("StaticDischarge", "Electric arc sparks jumping randomly", {"rate": 400, "lifetime": 0.15, "size": 0.05, "shape": "Edge", "gravity": 0.0, "burst": 80, "speed": 20.0}),
            ("ChainLightning", "Lightning bounce VFX hitting 3 targets", {"rate": 300, "lifetime": 0.1, "size": 0.04, "shape": "Edge", "gravity": 0.0, "burst": 200, "speed": 30.0}),
            ("TempestIncarnate", "Storm transformation engulfing area", {"rate": 500, "lifetime": 0.8, "size": 0.3, "shape": "Sphere", "gravity": 0.0, "burst": 400, "speed": 12.0}),
        ],
    },
    "flicker": {
        "brands": ["SURGE"],
        "abilities": [
            ("SpeedBlur", "Afterimage trail while moving fast", {"rate": 60, "lifetime": 0.4, "size": 0.8, "shape": "Box", "gravity": 0.0, "burst": 0, "speed": 0.5}),
            ("PhaseShift", "Dodge shimmer VFX on evasion", {"rate": 200, "lifetime": 0.2, "size": 0.3, "shape": "Sphere", "gravity": 0.0, "burst": 150, "speed": 6.0}),
            ("QuicksilverBlitz", "Multi-strike speed trails converging", {"rate": 350, "lifetime": 0.15, "size": 0.1, "shape": "Cone", "gravity": 0.0, "burst": 100, "speed": 25.0}),
        ],
    },
    "gluttony_polyp": {
        "brands": ["LEECH", "DREAD"],
        "abilities": [
            ("BloatExpand", "Bloating size increase VFX", {"rate": 50, "lifetime": 2.0, "size": 0.5, "shape": "Sphere", "gravity": 0.0, "burst": 30, "speed": 1.0}),
            ("HungeringTendrils", "Dark tendrils reaching for targets", {"rate": 80, "lifetime": 1.5, "size": 0.2, "shape": "Cone", "gravity": 0.0, "burst": 0, "speed": 4.0}),
            ("DevouringCare", "Consumption sphere pulling in particles", {"rate": 120, "lifetime": 1.8, "size": 0.4, "shape": "Sphere", "gravity": 0.0, "burst": 100, "speed": -3.0}),
        ],
    },
    "grimthorn": {
        "brands": ["SAVAGE"],
        "abilities": [
            ("ThornEruption", "Thorns bursting from ground", {"rate": 150, "lifetime": 0.8, "size": 0.25, "shape": "Cone", "gravity": -1.5, "burst": 120, "speed": 7.0}),
            ("ToxicSporeCloud", "Spore cloud lingering in area", {"rate": 30, "lifetime": 5.0, "size": 0.6, "shape": "Sphere", "gravity": 0.1, "burst": 0, "speed": 0.3}),
            ("NaturesWrath", "Root explosion ripping ground", {"rate": 250, "lifetime": 1.2, "size": 0.4, "shape": "Circle", "gravity": -0.5, "burst": 200, "speed": 6.0}),
        ],
    },
    "hollow": {
        "brands": ["VOID", "DREAD"],
        "abilities": [
            ("VoidRift", "Portal tear in space VFX", {"rate": 100, "lifetime": 2.0, "size": 0.7, "shape": "Sphere", "gravity": 0.0, "burst": 80, "speed": 2.0}),
            ("ConsumingVortex", "Suction vortex pulling particles inward", {"rate": 150, "lifetime": 1.5, "size": 0.3, "shape": "Sphere", "gravity": 0.0, "burst": 0, "speed": -5.0}),
            ("AbyssalUnraveling", "Reality tear ripping outward", {"rate": 300, "lifetime": 1.0, "size": 0.5, "shape": "Sphere", "gravity": 0.0, "burst": 250, "speed": 10.0}),
        ],
    },
    "ironjaw": {
        "brands": ["LEECH", "IRON"],
        "abilities": [
            ("MetalJawSnap", "Metallic jaw snap crunch VFX", {"rate": 180, "lifetime": 0.4, "size": 0.2, "shape": "Cone", "gravity": -1.0, "burst": 150, "speed": 8.0}),
            ("SteelRend", "Armor strip sparks flying off target", {"rate": 200, "lifetime": 0.5, "size": 0.12, "shape": "Cone", "gravity": -0.8, "burst": 160, "speed": 10.0}),
            ("UnstoppableMaw", "Charge trail of metal debris", {"rate": 100, "lifetime": 1.0, "size": 0.3, "shape": "Edge", "gravity": -0.5, "burst": 0, "speed": 3.0}),
        ],
    },
    "mawling": {
        "brands": ["LEECH"],
        "abilities": [
            ("GnawBite", "Quick gnaw bite blood splatter", {"rate": 150, "lifetime": 0.5, "size": 0.2, "shape": "Cone", "gravity": -1.5, "burst": 100, "speed": 5.0}),
            ("FrenzyBite", "Rapid bite multi-hit VFX", {"rate": 250, "lifetime": 0.3, "size": 0.15, "shape": "Cone", "gravity": -1.0, "burst": 80, "speed": 7.0}),
            ("EternalHunger", "Growth expansion body surge", {"rate": 60, "lifetime": 2.0, "size": 0.5, "shape": "Sphere", "gravity": 0.0, "burst": 40, "speed": 1.5}),
        ],
    },
    "needlefang": {
        "brands": ["VENOM", "SURGE"],
        "abilities": [
            ("NeedleStorm", "Rapid needle projectiles", {"rate": 400, "lifetime": 0.3, "size": 0.05, "shape": "Cone", "gravity": 0.0, "burst": 80, "speed": 25.0}),
            ("SpineFlurry", "Spread of venomous spines", {"rate": 250, "lifetime": 0.5, "size": 0.08, "shape": "Cone", "gravity": -0.3, "burst": 120, "speed": 18.0}),
            ("ThousandStings", "Rain of poisoned needles from above", {"rate": 500, "lifetime": 0.6, "size": 0.04, "shape": "Box", "gravity": -3.0, "burst": 300, "speed": 15.0}),
        ],
    },
    "ravener": {
        "brands": ["SAVAGE", "VOID"],
        "abilities": [
            ("PredatorPounce", "Savage leap impact VFX", {"rate": 200, "lifetime": 0.6, "size": 0.35, "shape": "Sphere", "gravity": -2.0, "burst": 180, "speed": 8.0}),
            ("BloodscenTracking", "Tracking mark over prey", {"rate": 30, "lifetime": 3.0, "size": 0.2, "shape": "Circle", "gravity": 0.0, "burst": 20, "speed": 0.5}),
            ("ApexStrike", "Execution slash with dark energy", {"rate": 300, "lifetime": 0.4, "size": 0.4, "shape": "Cone", "gravity": 0.0, "burst": 250, "speed": 12.0}),
        ],
    },
    "skitter_teeth": {
        "brands": ["IRON"],
        "abilities": [
            ("BoneSnapCrunch", "Bone crunch impact sparks", {"rate": 180, "lifetime": 0.4, "size": 0.15, "shape": "Cone", "gravity": -2.0, "burst": 140, "speed": 6.0}),
            ("BoneWallShield", "Bone wall rising as shield", {"rate": 100, "lifetime": 2.0, "size": 0.25, "shape": "Edge", "gravity": -1.0, "burst": 80, "speed": 4.0}),
            ("FinalForm", "Transformation burst with bone shards", {"rate": 350, "lifetime": 0.8, "size": 0.3, "shape": "Sphere", "gravity": -1.5, "burst": 300, "speed": 10.0}),
        ],
    },
    "sporecaller": {
        "brands": ["SAVAGE", "CORROSIVE"],
        "abilities": [
            ("SporeCloud", "Spore cloud AOE lingering", {"rate": 40, "lifetime": 6.0, "size": 0.5, "shape": "Sphere", "gravity": 0.05, "burst": 0, "speed": 0.3}),
            ("FungalTouch", "Infection spread on contact", {"rate": 70, "lifetime": 2.5, "size": 0.2, "shape": "Circle", "gravity": 0.0, "burst": 50, "speed": 2.0}),
            ("MyceliumNetwork", "Ground lines of fungal spread", {"rate": 80, "lifetime": 4.0, "size": 0.1, "shape": "Edge", "gravity": 0.0, "burst": 0, "speed": 1.5}),
        ],
    },
    "the_broodmother": {
        "brands": ["SAVAGE", "CORROSIVE"],
        "abilities": [
            ("ParasiticInjection", "Worm projectile VFX", {"rate": 60, "lifetime": 1.0, "size": 0.12, "shape": "Cone", "gravity": -0.5, "burst": 40, "speed": 12.0}),
            ("BroodlingSpawn", "Emergence burst from ground", {"rate": 200, "lifetime": 0.8, "size": 0.3, "shape": "Sphere", "gravity": -1.0, "burst": 150, "speed": 5.0}),
            ("HiveQueenAscension", "Swarm cloud engulfing area", {"rate": 400, "lifetime": 3.0, "size": 0.15, "shape": "Sphere", "gravity": 0.1, "burst": 300, "speed": 3.0}),
        ],
    },
    "the_bulwark": {
        "brands": ["IRON", "CORROSIVE"],
        "abilities": [
            ("FortressBody", "Armor plate materialization VFX", {"rate": 80, "lifetime": 1.5, "size": 0.25, "shape": "Box", "gravity": 0.0, "burst": 60, "speed": 2.0}),
            ("ImmovableWill", "Stance glow aura pulsing", {"rate": 40, "lifetime": 3.0, "size": 0.8, "shape": "Sphere", "gravity": 0.0, "burst": 0, "speed": 0.5}),
            ("CitadelEternal", "Ultimate shield dome VFX", {"rate": 150, "lifetime": 4.0, "size": 0.6, "shape": "Sphere", "gravity": 0.0, "burst": 120, "speed": 1.0}),
        ],
    },
    "the_congregation": {
        "brands": ["DREAD"],
        "abilities": [
            ("SmithHammer", "Hammer impact shockwave", {"rate": 250, "lifetime": 0.5, "size": 0.4, "shape": "Sphere", "gravity": -2.0, "burst": 200, "speed": 8.0}),
            ("ElderWisdom", "Buff aura golden particles", {"rate": 30, "lifetime": 4.0, "size": 0.3, "shape": "Sphere", "gravity": 0.1, "burst": 0, "speed": 0.8}),
            ("MotherEmbrace", "Grab tendrils reaching out", {"rate": 60, "lifetime": 1.5, "size": 0.2, "shape": "Cone", "gravity": 0.0, "burst": 40, "speed": 5.0}),
            ("ChorusOfNames", "Mass fear wave expanding", {"rate": 200, "lifetime": 1.5, "size": 0.5, "shape": "Circle", "gravity": 0.0, "burst": 180, "speed": 10.0}),
            ("FinalAbsolution", "Divine judgment pillar of light", {"rate": 400, "lifetime": 2.0, "size": 0.7, "shape": "Cone", "gravity": 0.0, "burst": 350, "speed": 6.0}),
        ],
    },
    "the_vessel": {
        "brands": ["DREAD", "MEND"],
        "abilities": [
            ("StolenGrace", "Drain+shield dual stream", {"rate": 100, "lifetime": 1.2, "size": 0.2, "shape": "Cone", "gravity": 0.0, "burst": 0, "speed": 7.0}),
            ("MercifulCocoon", "Healing wrap encasing target", {"rate": 80, "lifetime": 3.0, "size": 0.4, "shape": "Sphere", "gravity": 0.0, "burst": 60, "speed": 1.0}),
            ("DivineDevotion", "Ultimate heal burst outward", {"rate": 300, "lifetime": 1.0, "size": 0.5, "shape": "Sphere", "gravity": 0.0, "burst": 250, "speed": 8.0}),
        ],
    },
    "the_weeping": {
        "brands": ["VENOM"],
        "abilities": [
            ("ManyEyedGaze", "Debuff cone of baleful eyes", {"rate": 50, "lifetime": 2.0, "size": 0.3, "shape": "Cone", "gravity": 0.0, "burst": 30, "speed": 3.0}),
            ("GlimpseOfDeath", "Fear projectile with trail", {"rate": 100, "lifetime": 0.8, "size": 0.2, "shape": "Cone", "gravity": 0.0, "burst": 60, "speed": 15.0}),
            ("AbsoluteVision", "All-seeing dome expanding", {"rate": 150, "lifetime": 3.0, "size": 0.6, "shape": "Sphere", "gravity": 0.0, "burst": 120, "speed": 2.0}),
        ],
    },
    "voltgeist": {
        "brands": ["RUIN", "SURGE"],
        "abilities": [
            ("LightningHaunt", "Lightning ghost flicker VFX", {"rate": 300, "lifetime": 0.2, "size": 0.1, "shape": "Sphere", "gravity": 0.0, "burst": 80, "speed": 15.0}),
            ("StormTerror", "AOE storm expanding outward", {"rate": 400, "lifetime": 1.0, "size": 0.4, "shape": "Sphere", "gravity": 0.0, "burst": 300, "speed": 8.0}),
            ("ThunderwraithScream", "Shockwave scream ring", {"rate": 250, "lifetime": 0.6, "size": 0.5, "shape": "Circle", "gravity": 0.0, "burst": 200, "speed": 12.0}),
        ],
    },
}

VALID_MONSTER_NAMES = set(MONSTER_VFX_CONFIGS.keys())

# ---------------------------------------------------------------------------
# Hybrid brand color data -- 6 hybrids
# ---------------------------------------------------------------------------

HYBRID_BRAND_COLORS: dict[str, dict[str, Any]] = {
    "BLOODIRON": {
        "id": 11,
        "parents": ("IRON", "SAVAGE"),
        "primary": _blend_colors(BRAND_PRIMARY_COLORS["IRON"], BRAND_PRIMARY_COLORS["SAVAGE"]),
        "glow": _blend_colors(BRAND_GLOW_COLORS["IRON"], BRAND_GLOW_COLORS["SAVAGE"]),
        "dark": _blend_colors(BRAND_DARK_COLORS["IRON"], BRAND_DARK_COLORS["SAVAGE"]),
        "desc": "rusty crimson metal-blood swirl",
    },
    "RAVENOUS": {
        "id": 12,
        "parents": ("SAVAGE", "LEECH"),
        "primary": _blend_colors(BRAND_PRIMARY_COLORS["SAVAGE"], BRAND_PRIMARY_COLORS["LEECH"]),
        "glow": _blend_colors(BRAND_GLOW_COLORS["SAVAGE"], BRAND_GLOW_COLORS["LEECH"]),
        "dark": _blend_colors(BRAND_DARK_COLORS["SAVAGE"], BRAND_DARK_COLORS["LEECH"]),
        "desc": "hunger-black devouring red",
    },
    "CORROSIVE": {
        "id": 13,
        "parents": ("VENOM", "RUIN"),
        "primary": _blend_colors(BRAND_PRIMARY_COLORS["VENOM"], BRAND_PRIMARY_COLORS["RUIN"]),
        "glow": _blend_colors(BRAND_GLOW_COLORS["VENOM"], BRAND_GLOW_COLORS["RUIN"]),
        "dark": _blend_colors(BRAND_DARK_COLORS["VENOM"], BRAND_DARK_COLORS["RUIN"]),
        "desc": "acid-green decay-brown dissolve",
    },
    "TERRORFLUX": {
        "id": 14,
        "parents": ("DREAD", "SURGE"),
        "primary": _blend_colors(BRAND_PRIMARY_COLORS["DREAD"], BRAND_PRIMARY_COLORS["SURGE"]),
        "glow": _blend_colors(BRAND_GLOW_COLORS["DREAD"], BRAND_GLOW_COLORS["SURGE"]),
        "dark": _blend_colors(BRAND_DARK_COLORS["DREAD"], BRAND_DARK_COLORS["SURGE"]),
        "desc": "chaos purple-blue unstable flicker",
    },
    "VENOMSTRIKE": {
        "id": 15,
        "parents": ("VENOM", "SURGE"),
        "primary": _blend_colors(BRAND_PRIMARY_COLORS["VENOM"], BRAND_PRIMARY_COLORS["SURGE"]),
        "glow": _blend_colors(BRAND_GLOW_COLORS["VENOM"], BRAND_GLOW_COLORS["SURGE"]),
        "dark": _blend_colors(BRAND_DARK_COLORS["VENOM"], BRAND_DARK_COLORS["SURGE"]),
        "desc": "toxic-green speed-blue poison trail",
    },
    "NIGHTLEECH": {
        "id": 16,
        "parents": ("LEECH", "VOID"),
        "primary": _blend_colors(BRAND_PRIMARY_COLORS["LEECH"], BRAND_PRIMARY_COLORS["VOID"]),
        "glow": _blend_colors(BRAND_GLOW_COLORS["LEECH"], BRAND_GLOW_COLORS["VOID"]),
        "dark": _blend_colors(BRAND_DARK_COLORS["LEECH"], BRAND_DARK_COLORS["VOID"]),
        "desc": "vampiric crimson-black drain shadow",
    },
}

VALID_HYBRID_BRANDS = set(HYBRID_BRAND_COLORS.keys())

# ---------------------------------------------------------------------------
# Hybrid ability configs per hybrid brand
# ---------------------------------------------------------------------------

HYBRID_ABILITY_CONFIGS: dict[str, list[tuple[str, str, dict]]] = {
    "BLOODIRON": [
        ("RustyBloodSwirl", "Metal+blood swirling particles", {"rate": 120, "lifetime": 1.0, "size": 0.25, "burst": 80, "speed": 4.0}),
        ("IronCrimsonSlash", "Metallic blood-streaked slash", {"rate": 200, "lifetime": 0.4, "size": 0.2, "burst": 150, "speed": 10.0}),
    ],
    "RAVENOUS": [
        ("GnashingAura", "Gnashing hunger particles", {"rate": 60, "lifetime": 2.0, "size": 0.3, "burst": 40, "speed": 1.5}),
        ("DevouringSurge", "Devouring rush forward VFX", {"rate": 180, "lifetime": 0.6, "size": 0.25, "burst": 120, "speed": 8.0}),
    ],
    "CORROSIVE": [
        ("AcidRustDrip", "Acid+rust dripping particles", {"rate": 50, "lifetime": 2.5, "size": 0.15, "burst": 0, "speed": 0.8}),
        ("DissolvingBurst", "Corrosive explosion dissolving matter", {"rate": 250, "lifetime": 0.8, "size": 0.35, "burst": 200, "speed": 7.0}),
    ],
    "TERRORFLUX": [
        ("FearDistortion", "Reality distortion fear waves", {"rate": 80, "lifetime": 1.5, "size": 0.5, "burst": 60, "speed": 3.0}),
        ("ChaosLightning", "Multi-color unstable lightning", {"rate": 350, "lifetime": 0.2, "size": 0.08, "burst": 150, "speed": 20.0}),
    ],
    "VENOMSTRIKE": [
        ("ToxicSpeedLine", "Poison trail speed lines", {"rate": 100, "lifetime": 0.5, "size": 0.1, "burst": 0, "speed": 15.0}),
        ("VenomBoltRain", "Rapid venomous bolt barrage", {"rate": 300, "lifetime": 0.3, "size": 0.06, "burst": 100, "speed": 22.0}),
    ],
    "NIGHTLEECH": [
        ("VampiricShadow", "Drain+shadow swirling particles", {"rate": 70, "lifetime": 2.0, "size": 0.4, "burst": 50, "speed": 2.0}),
        ("DarkSiphon", "Vampiric drain beam with dark glow", {"rate": 140, "lifetime": 0.8, "size": 0.18, "burst": 0, "speed": 9.0}),
    ],
}


# ---------------------------------------------------------------------------
# Helper: build C# ability config struct entries
# ---------------------------------------------------------------------------


def _build_monster_config_entries() -> str:
    """Build C# dictionary initializer for all monster VFX configs."""
    lines = []
    for monster, cfg in MONSTER_VFX_CONFIGS.items():
        brands = cfg["brands"]
        primary_brand = brands[0]
        primary_rgba = BRAND_PRIMARY_COLORS.get(primary_brand, BRAND_PRIMARY_COLORS["IRON"])
        glow_rgba = BRAND_GLOW_COLORS.get(primary_brand, BRAND_GLOW_COLORS["IRON"])
        dark_rgba = BRAND_DARK_COLORS.get(primary_brand, BRAND_DARK_COLORS["IRON"])
        # Secondary brand color (or same as primary if single-brand)
        sec_brand = brands[1] if len(brands) > 1 else brands[0]
        sec_rgba = BRAND_PRIMARY_COLORS.get(sec_brand, BRAND_PRIMARY_COLORS["IRON"])

        ability_entries = []
        for ab_name, ab_desc, ab_cfg in cfg["abilities"]:
            ability_entries.append(
                f'                    new AbilityVFXConfig("{ab_name}", "{ab_desc}", '
                f'{ab_cfg["rate"]}, {ab_cfg["lifetime"]}f, {ab_cfg["size"]}f, '
                f'ParticleSystemShapeType.{ab_cfg["shape"]}, {ab_cfg["gravity"]}f, '
                f'{ab_cfg["burst"]}, {ab_cfg["speed"]}f)'
            )

        brands_str = ", ".join(f'"{b}"' for b in brands)
        lines.append(f'            {{ "{monster}", new MonsterVFXConfig(')
        lines.append(f'                "{monster}",')
        lines.append(f'                new string[] {{ {brands_str} }},')
        lines.append(f"                {_fmt_color(primary_rgba)},")
        lines.append(f"                {_fmt_color(glow_rgba)},")
        lines.append(f"                {_fmt_color(dark_rgba)},")
        lines.append(f"                {_fmt_color(sec_rgba)},")
        lines.append(f"                new AbilityVFXConfig[] {{")
        lines.append(",\n".join(ability_entries))
        lines.append(f"                }}")
        lines.append(f"            ) }},")
    return "\n".join(lines)


def _build_hybrid_config_entries() -> str:
    """Build C# dictionary initializer for all hybrid brand VFX configs."""
    lines = []
    for hybrid, cfg in HYBRID_BRAND_COLORS.items():
        p = cfg["primary"]
        g = cfg["glow"]
        d = cfg["dark"]
        parents = cfg["parents"]

        ability_entries = []
        for ab_name, ab_desc, ab_cfg in HYBRID_ABILITY_CONFIGS.get(hybrid, []):
            ability_entries.append(
                f'                    new HybridAbilityConfig("{ab_name}", "{ab_desc}", '
                f'{ab_cfg["rate"]}, {ab_cfg["lifetime"]}f, {ab_cfg["size"]}f, '
                f'{ab_cfg["burst"]}, {ab_cfg["speed"]}f)'
            )

        lines.append(f'            {{ "{hybrid}", new HybridBrandConfig(')
        lines.append(f'                "{hybrid}", {cfg["id"]},')
        lines.append(f'                "{parents[0]}", "{parents[1]}",')
        lines.append(f"                {_fmt_color(p)}, {_fmt_color(g)}, {_fmt_color(d)},")
        lines.append(f"                new HybridAbilityConfig[] {{")
        lines.append(",\n".join(ability_entries))
        lines.append(f"                }}")
        lines.append(f"            ) }},")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 1. Monster Signature VFX
# ---------------------------------------------------------------------------


def generate_monster_signature_vfx_script(
    monster_name: str = "bloodshade",
) -> dict[str, Any]:
    """Generate MonsterSignatureVFXController for per-monster signature VFX.

    Creates a single MonoBehaviour that switches behavior based on monster
    name, with unique particle configs for all 20 named VeilBreakers monsters.

    Args:
        monster_name: Default monster to configure. Any of the 20 names.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    monster_name = monster_name.lower().replace(" ", "_")
    if monster_name not in VALID_MONSTER_NAMES:
        monster_name = "bloodshade"

    safe_name = sanitize_cs_identifier(monster_name)
    monster_configs_cs = _build_monster_config_entries()

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Signature VFX controller for VeilBreakers named monsters.
/// Supports all 20 monsters with unique particle configs per ability.
/// Uses ParticleSystem + PrimeTween for URP.
/// </summary>
public class MonsterSignatureVFXController : MonoBehaviour
{{
    // -------------------------------------------------------------------
    // Config structs
    // -------------------------------------------------------------------

    [Serializable]
    public struct AbilityVFXConfig
    {{
        public string Name;
        public string Description;
        public int Rate;
        public float Lifetime;
        public float Size;
        public ParticleSystemShapeType Shape;
        public float Gravity;
        public int BurstCount;
        public float Speed;

        public AbilityVFXConfig(string name, string desc, int rate, float lifetime,
            float size, ParticleSystemShapeType shape, float gravity, int burst, float speed)
        {{
            Name = name; Description = desc; Rate = rate; Lifetime = lifetime;
            Size = size; Shape = shape; Gravity = gravity; BurstCount = burst; Speed = speed;
        }}
    }}

    [Serializable]
    public struct MonsterVFXConfig
    {{
        public string MonsterName;
        public string[] Brands;
        public Color PrimaryColor;
        public Color GlowColor;
        public Color DarkColor;
        public Color SecondaryBrandColor;
        public AbilityVFXConfig[] Abilities;

        public MonsterVFXConfig(string name, string[] brands, Color primary, Color glow,
            Color dark, Color secondary, AbilityVFXConfig[] abilities)
        {{
            MonsterName = name; Brands = brands; PrimaryColor = primary;
            GlowColor = glow; DarkColor = dark; SecondaryBrandColor = secondary;
            Abilities = abilities;
        }}
    }}

    // -------------------------------------------------------------------
    // Inspector
    // -------------------------------------------------------------------

    [Header("Monster Identity")]
    [SerializeField] private string monsterName = "{monster_name}";

    [Header("VFX Settings")]
    [SerializeField] private float vfxScale = 1.0f;
    [SerializeField] private float intensityMultiplier = 1.0f;

    // -------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------

    public event Action<string, string> OnSignatureAbilityTriggered;

    // -------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------

    private MonsterVFXConfig currentConfig;
    private bool isConfigured;
    private readonly Dictionary<string, ParticleSystem> abilityParticleSystems = new Dictionary<string, ParticleSystem>();
    private ParticleSystem ambientPS;
    private Material particleMaterial;

    // -------------------------------------------------------------------
    // Monster config database
    // -------------------------------------------------------------------

    private static readonly Dictionary<string, MonsterVFXConfig> MonsterConfigs = new Dictionary<string, MonsterVFXConfig>
    {{
{monster_configs_cs}
    }};

    // -------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------

    private void Awake()
    {{
        CreateParticleMaterial();
        if (!string.IsNullOrEmpty(monsterName))
            SetupMonsterVFX(monsterName);
    }}

    private void OnDestroy()
    {{
        foreach (var kvp in abilityParticleSystems)
        {{
            if (kvp.Value != null) Destroy(kvp.Value.gameObject);
        }}
        abilityParticleSystems.Clear();
        if (ambientPS != null) Destroy(ambientPS.gameObject);
        if (particleMaterial != null) Destroy(particleMaterial);
    }}

    // -------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------

    /// <summary>Configure VFX for a specific monster by name.</summary>
    public void SetupMonsterVFX(string name)
    {{
        string key = name.ToLowerInvariant().Replace(" ", "_");
        if (!MonsterConfigs.TryGetValue(key, out currentConfig))
        {{
            Debug.LogWarning($"[MonsterVFX] Unknown monster: {{name}}, falling back to bloodshade");
            currentConfig = MonsterConfigs["bloodshade"];
        }}

        monsterName = key;
        isConfigured = true;

        // Destroy old systems
        foreach (var kvp in abilityParticleSystems)
        {{
            if (kvp.Value != null) Destroy(kvp.Value.gameObject);
        }}
        abilityParticleSystems.Clear();

        // Create ambient idle particles
        SetupAmbientParticles();

        // Pre-create ability particle systems
        foreach (var ability in currentConfig.Abilities)
        {{
            var ps = CreateAbilityParticleSystem(ability);
            abilityParticleSystems[ability.Name] = ps;
        }}

        Debug.Log($"[MonsterVFX] Configured for {{key}} with {{currentConfig.Abilities.Length}} abilities");
    }}

    /// <summary>Trigger a named signature ability VFX.</summary>
    public void TriggerSignatureAbility(string abilityName)
    {{
        if (!isConfigured)
        {{
            Debug.LogWarning("[MonsterVFX] Not configured. Call SetupMonsterVFX first.");
            return;
        }}

        if (abilityParticleSystems.TryGetValue(abilityName, out var ps))
        {{
            ps.Clear();
            ps.Play();
            OnSignatureAbilityTriggered?.Invoke(monsterName, abilityName);
            StartCoroutine(AutoStopParticles(ps, GetAbilityLifetime(abilityName)));
        }}
        else
        {{
            Debug.LogWarning($"[MonsterVFX] Unknown ability: {{abilityName}} for {{monsterName}}");
        }}
    }}

    /// <summary>Stop all active ability VFX.</summary>
    public void StopAllAbilities()
    {{
        foreach (var kvp in abilityParticleSystems)
        {{
            if (kvp.Value != null && kvp.Value.isPlaying)
                kvp.Value.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }}
    }}

    /// <summary>Get the current monster name.</summary>
    public string GetMonsterName() => monsterName;

    /// <summary>Get list of available ability names for current monster.</summary>
    public string[] GetAbilityNames()
    {{
        if (!isConfigured) return Array.Empty<string>();
        var names = new string[currentConfig.Abilities.Length];
        for (int i = 0; i < currentConfig.Abilities.Length; i++)
            names[i] = currentConfig.Abilities[i].Name;
        return names;
    }}

    // -------------------------------------------------------------------
    // Internal: particle system creation
    // -------------------------------------------------------------------

    private void CreateParticleMaterial()
    {{
        particleMaterial = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        particleMaterial.SetFloat("_Surface", 1); // Transparent
        particleMaterial.SetFloat("_Blend", 0);   // Alpha
        particleMaterial.renderQueue = 3000;
    }}

    private void SetupAmbientParticles()
    {{
        if (ambientPS != null) Destroy(ambientPS.gameObject);

        var go = new GameObject($"{{monsterName}}_AmbientVFX");
        go.transform.SetParent(transform, false);
        ambientPS = go.AddComponent<ParticleSystem>();

        var main = ambientPS.main;
        main.startLifetime = 3.0f;
        main.startSize = 0.15f * vfxScale;
        main.startSpeed = 0.5f;
        main.startColor = currentConfig.PrimaryColor;
        main.maxParticles = 100;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 0f;
        main.loop = true;

        var emission = ambientPS.emission;
        emission.rateOverTime = 15f;

        var shape = ambientPS.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 1.0f * vfxScale;

        var col = ambientPS.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(currentConfig.GlowColor, 0f),
                new GradientColorKey(currentConfig.PrimaryColor, 0.5f),
                new GradientColorKey(currentConfig.DarkColor, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.6f, 0.3f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOverLife = ambientPS.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.5f, 1f, 0f));

        var renderer = ambientPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = ParticleSystemRenderMode.Billboard;

        ambientPS.Play();
    }}

    private ParticleSystem CreateAbilityParticleSystem(AbilityVFXConfig config)
    {{
        var go = new GameObject($"{{monsterName}}_{{config.Name}}_VFX");
        go.transform.SetParent(transform, false);
        var ps = go.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.startLifetime = config.Lifetime;
        main.startSize = config.Size * vfxScale;
        main.startSpeed = Mathf.Abs(config.Speed);
        main.startColor = currentConfig.PrimaryColor;
        main.maxParticles = Mathf.Max(500, config.Rate * 3);
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = config.Gravity;
        main.loop = false;
        main.playOnAwake = false;

        // Negative speed = inward pull (consuming effects)
        if (config.Speed < 0)
        {{
            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.radial = config.Speed;
        }}

        var emission = ps.emission;
        emission.rateOverTime = config.Rate * intensityMultiplier;
        if (config.BurstCount > 0)
        {{
            emission.SetBursts(new ParticleSystem.Burst[] {{
                new ParticleSystem.Burst(0f, (short)(config.BurstCount * intensityMultiplier))
            }});
        }}

        var shape = ps.shape;
        shape.shapeType = config.Shape;
        switch (config.Shape)
        {{
            case ParticleSystemShapeType.Sphere:
                shape.radius = 0.5f * vfxScale;
                break;
            case ParticleSystemShapeType.Cone:
                shape.angle = 25f;
                shape.radius = 0.3f * vfxScale;
                break;
            case ParticleSystemShapeType.Circle:
                shape.radius = 1.5f * vfxScale;
                shape.arc = 360f;
                break;
            case ParticleSystemShapeType.Box:
                shape.scale = new Vector3(1f, 0.2f, 1f) * vfxScale;
                break;
        }}

        // Dual-brand color gradient
        var col = ps.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(currentConfig.GlowColor, 0f),
                new GradientColorKey(currentConfig.PrimaryColor, 0.4f),
                new GradientColorKey(currentConfig.SecondaryBrandColor, 0.7f),
                new GradientColorKey(currentConfig.DarkColor, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(1f, 0.15f),
                new GradientAlphaKey(0.8f, 0.6f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOverLife = ps.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = (config.Shape == ParticleSystemShapeType.SingleSidedEdge)
            ? ParticleSystemRenderMode.Stretch
            : ParticleSystemRenderMode.Billboard;
        if (renderer.renderMode == ParticleSystemRenderMode.Stretch)
            renderer.lengthScale = 3f;

        return ps;
    }}

    private float GetAbilityLifetime(string abilityName)
    {{
        foreach (var ab in currentConfig.Abilities)
        {{
            if (ab.Name == abilityName) return ab.Lifetime + 0.5f;
        }}
        return 2.0f;
    }}

    private IEnumerator AutoStopParticles(ParticleSystem ps, float delay)
    {{
        yield return new WaitForSeconds(delay);
        if (ps != null && ps.isPlaying)
            ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}
}}

// ======================================================================
// Editor setup menu
// ======================================================================
#if UNITY_EDITOR
public static class VB_MonsterSignatureVFXSetup
{{
    [MenuItem("VeilBreakers/VFX/Monster Signature VFX/Setup {safe_name}")]
    public static void Setup()
    {{
        try
        {{
            var selected = Selection.activeGameObject;
            GameObject go;
            if (selected != null)
            {{
                go = selected;
            }}
            else
            {{
                go = new GameObject("MonsterSignatureVFX_{safe_name}");
            }}

            var ctrl = go.GetComponent<MonsterSignatureVFXController>();
            if (ctrl == null)
                ctrl = go.AddComponent<MonsterSignatureVFXController>();

            ctrl.SetupMonsterVFX("{monster_name}");

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"monster_signature_vfx\\", \\"monster\\": \\"{monster_name}\\", \\"object\\": \\"" + go.name + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Monster Signature VFX set up for {monster_name} on " + go.name);
        }}
        catch (Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"monster_signature_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Monster Signature VFX setup failed: " + ex.Message);
        }}
    }}
}}
#endif
'''

    return {
        "script_path": f"Assets/Editor/Generated/VFX/VB_MonsterSignatureVFX_{safe_name}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Use menu: VeilBreakers > VFX > Monster Signature VFX > Setup {safe_name}",
            "Select a monster GameObject first, or a new one will be created",
            f"Call SetupMonsterVFX(\"{monster_name}\") to configure for any of the 20 monsters",
            "Call TriggerSignatureAbility(abilityName) to fire ability VFX",
            "Subscribe to OnSignatureAbilityTriggered for game system integration",
            "All 20 monsters are supported -- call SetupMonsterVFX with any monster name at runtime",
        ],
    }


# ---------------------------------------------------------------------------
# 2. Hybrid Brand VFX
# ---------------------------------------------------------------------------


def generate_hybrid_brand_vfx_script(
    hybrid_brand: str = "BLOODIRON",
) -> dict[str, Any]:
    """Generate HybridBrandVFXController for 6 hybrid brand VFX.

    Each hybrid blends two parent brand colors with PrimeTween color lerp
    and has unique particle behavior mixing both brand identities.

    Args:
        hybrid_brand: Hybrid brand name (BLOODIRON, RAVENOUS, CORROSIVE,
            TERRORFLUX, VENOMSTRIKE, NIGHTLEECH).

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    hybrid_brand = hybrid_brand.upper()
    if hybrid_brand not in VALID_HYBRID_BRANDS:
        hybrid_brand = "BLOODIRON"

    safe_brand = sanitize_cs_identifier(hybrid_brand)
    hybrid_configs_cs = _build_hybrid_config_entries()

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Hybrid brand VFX controller for VeilBreakers 6 hybrid brands.
/// Blends parent brand colors with PrimeTween and provides unique
/// particle behavior per hybrid identity.
/// </summary>
public class HybridBrandVFXController : MonoBehaviour
{{
    // -------------------------------------------------------------------
    // Config structs
    // -------------------------------------------------------------------

    [Serializable]
    public struct HybridAbilityConfig
    {{
        public string Name;
        public string Description;
        public int Rate;
        public float Lifetime;
        public float Size;
        public int BurstCount;
        public float Speed;

        public HybridAbilityConfig(string name, string desc, int rate, float lifetime,
            float size, int burst, float speed)
        {{
            Name = name; Description = desc; Rate = rate; Lifetime = lifetime;
            Size = size; BurstCount = burst; Speed = speed;
        }}
    }}

    [Serializable]
    public struct HybridBrandConfig
    {{
        public string BrandName;
        public int BrandId;
        public string ParentA;
        public string ParentB;
        public Color PrimaryColor;
        public Color GlowColor;
        public Color DarkColor;
        public HybridAbilityConfig[] Abilities;

        public HybridBrandConfig(string name, int id, string parentA, string parentB,
            Color primary, Color glow, Color dark, HybridAbilityConfig[] abilities)
        {{
            BrandName = name; BrandId = id; ParentA = parentA; ParentB = parentB;
            PrimaryColor = primary; GlowColor = glow; DarkColor = dark; Abilities = abilities;
        }}
    }}

    // -------------------------------------------------------------------
    // Inspector
    // -------------------------------------------------------------------

    [Header("Hybrid Brand")]
    [SerializeField] private string hybridBrand = "{hybrid_brand}";

    [Header("VFX Settings")]
    [SerializeField] private float vfxScale = 1.0f;
    [SerializeField] private float colorLerpSpeed = 2.0f;
    [SerializeField] private float colorLerpAmplitude = 0.3f;

    // -------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------

    public event Action<string, string> OnHybridAbilityTriggered;

    // -------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------

    private HybridBrandConfig currentConfig;
    private bool isConfigured;
    private readonly Dictionary<string, ParticleSystem> abilityParticleSystems = new Dictionary<string, ParticleSystem>();
    private ParticleSystem ambientPS;
    private Material particleMaterial;
    private float colorLerpTimer;

    // -------------------------------------------------------------------
    // Hybrid brand config database
    // -------------------------------------------------------------------

    private static readonly Dictionary<string, HybridBrandConfig> HybridConfigs = new Dictionary<string, HybridBrandConfig>
    {{
{hybrid_configs_cs}
    }};

    // -------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------

    private void Awake()
    {{
        CreateParticleMaterial();
        if (!string.IsNullOrEmpty(hybridBrand))
            SetHybridBrand(hybridBrand);
    }}

    private void Update()
    {{
        if (!isConfigured || ambientPS == null) return;

        // PrimeTween-style color oscillation between parent brand colors
        colorLerpTimer += Time.deltaTime * colorLerpSpeed;
        float t = (Mathf.Sin(colorLerpTimer) * 0.5f + 0.5f) * colorLerpAmplitude + (0.5f - colorLerpAmplitude * 0.5f);
        Color lerpedColor = Color.Lerp(currentConfig.PrimaryColor, currentConfig.GlowColor, t);

        var main = ambientPS.main;
        main.startColor = lerpedColor;

        // Also update particle material emission for glow pulse
        if (particleMaterial != null)
        {{
            particleMaterial.SetColor("_BaseColor", lerpedColor);
            particleMaterial.SetColor("_EmissionColor", lerpedColor * (1.5f + Mathf.Sin(colorLerpTimer * 1.5f) * 0.5f));
        }}
    }}

    private void OnDestroy()
    {{
        foreach (var kvp in abilityParticleSystems)
        {{
            if (kvp.Value != null) Destroy(kvp.Value.gameObject);
        }}
        abilityParticleSystems.Clear();
        if (ambientPS != null) Destroy(ambientPS.gameObject);
        if (particleMaterial != null) Destroy(particleMaterial);
    }}

    // -------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------

    /// <summary>Set the active hybrid brand and rebuild VFX.</summary>
    public void SetHybridBrand(string brand)
    {{
        string key = brand.ToUpperInvariant();
        if (!HybridConfigs.TryGetValue(key, out currentConfig))
        {{
            Debug.LogWarning($"[HybridVFX] Unknown hybrid brand: {{brand}}, falling back to BLOODIRON");
            currentConfig = HybridConfigs["BLOODIRON"];
            key = "BLOODIRON";
        }}

        hybridBrand = key;
        isConfigured = true;
        colorLerpTimer = 0f;

        // Rebuild particle systems
        foreach (var kvp in abilityParticleSystems)
        {{
            if (kvp.Value != null) Destroy(kvp.Value.gameObject);
        }}
        abilityParticleSystems.Clear();

        SetupAmbientHybridParticles();

        foreach (var ability in currentConfig.Abilities)
        {{
            var ps = CreateHybridAbilityPS(ability);
            abilityParticleSystems[ability.Name] = ps;
        }}

        Debug.Log($"[HybridVFX] Configured for {{key}} ({{currentConfig.ParentA}}+{{currentConfig.ParentB}})");
    }}

    /// <summary>Trigger a named hybrid ability VFX.</summary>
    public void TriggerHybridAbility(string abilityName)
    {{
        if (!isConfigured)
        {{
            Debug.LogWarning("[HybridVFX] Not configured. Call SetHybridBrand first.");
            return;
        }}

        if (abilityParticleSystems.TryGetValue(abilityName, out var ps))
        {{
            ps.Clear();
            ps.Play();
            OnHybridAbilityTriggered?.Invoke(hybridBrand, abilityName);
            StartCoroutine(AutoStopParticles(ps, GetAbilityLifetime(abilityName)));
        }}
        else
        {{
            Debug.LogWarning($"[HybridVFX] Unknown ability: {{abilityName}} for {{hybridBrand}}");
        }}
    }}

    /// <summary>Stop all active VFX.</summary>
    public void StopAll()
    {{
        foreach (var kvp in abilityParticleSystems)
        {{
            if (kvp.Value != null && kvp.Value.isPlaying)
                kvp.Value.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }}
    }}

    /// <summary>Get current hybrid brand name.</summary>
    public string GetHybridBrand() => hybridBrand;

    // -------------------------------------------------------------------
    // Internal: particle system creation
    // -------------------------------------------------------------------

    private void CreateParticleMaterial()
    {{
        particleMaterial = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        particleMaterial.SetFloat("_Surface", 1);
        particleMaterial.SetFloat("_Blend", 0);
        particleMaterial.renderQueue = 3000;
    }}

    private void SetupAmbientHybridParticles()
    {{
        if (ambientPS != null) Destroy(ambientPS.gameObject);

        var go = new GameObject($"{{hybridBrand}}_HybridAmbientVFX");
        go.transform.SetParent(transform, false);
        ambientPS = go.AddComponent<ParticleSystem>();

        var main = ambientPS.main;
        main.startLifetime = 2.5f;
        main.startSize = new ParticleSystem.MinMaxCurve(0.08f * vfxScale, 0.2f * vfxScale);
        main.startSpeed = 0.8f;
        main.startColor = currentConfig.PrimaryColor;
        main.maxParticles = 150;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.loop = true;

        var emission = ambientPS.emission;
        emission.rateOverTime = 25f;

        var shape = ambientPS.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.8f * vfxScale;

        // Dual-parent brand color gradient
        var col = ambientPS.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(currentConfig.GlowColor, 0f),
                new GradientColorKey(currentConfig.PrimaryColor, 0.5f),
                new GradientColorKey(currentConfig.DarkColor, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.7f, 0.25f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOverLife = ambientPS.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.3f, 1f, 0f));

        var renderer = ambientPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = ParticleSystemRenderMode.Billboard;

        ambientPS.Play();
    }}

    private ParticleSystem CreateHybridAbilityPS(HybridAbilityConfig config)
    {{
        var go = new GameObject($"{{hybridBrand}}_{{config.Name}}_VFX");
        go.transform.SetParent(transform, false);
        var ps = go.AddComponent<ParticleSystem>();

        var main = ps.main;
        main.startLifetime = config.Lifetime;
        main.startSize = config.Size * vfxScale;
        main.startSpeed = config.Speed;
        main.startColor = currentConfig.PrimaryColor;
        main.maxParticles = Mathf.Max(300, config.Rate * 2);
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.loop = false;
        main.playOnAwake = false;

        var emission = ps.emission;
        emission.rateOverTime = config.Rate;
        if (config.BurstCount > 0)
        {{
            emission.SetBursts(new ParticleSystem.Burst[] {{
                new ParticleSystem.Burst(0f, (short)config.BurstCount)
            }});
        }}

        var shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.5f * vfxScale;

        // Hybrid dual-color gradient
        var col = ps.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(currentConfig.GlowColor, 0f),
                new GradientColorKey(currentConfig.PrimaryColor, 0.35f),
                new GradientColorKey(currentConfig.DarkColor, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(1f, 0.1f),
                new GradientAlphaKey(0.6f, 0.7f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOverLife = ps.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        var renderer = ps.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = ParticleSystemRenderMode.Billboard;

        return ps;
    }}

    private float GetAbilityLifetime(string abilityName)
    {{
        foreach (var ab in currentConfig.Abilities)
        {{
            if (ab.Name == abilityName) return ab.Lifetime + 0.5f;
        }}
        return 2.0f;
    }}

    private IEnumerator AutoStopParticles(ParticleSystem ps, float delay)
    {{
        yield return new WaitForSeconds(delay);
        if (ps != null && ps.isPlaying)
            ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}
}}

// ======================================================================
// Editor setup menu
// ======================================================================
#if UNITY_EDITOR
public static class VB_HybridBrandVFXSetup
{{
    [MenuItem("VeilBreakers/VFX/Hybrid Brand VFX/Setup {safe_brand}")]
    public static void Setup()
    {{
        try
        {{
            var selected = Selection.activeGameObject;
            GameObject go;
            if (selected != null)
            {{
                go = selected;
            }}
            else
            {{
                go = new GameObject("HybridBrandVFX_{safe_brand}");
            }}

            var ctrl = go.GetComponent<HybridBrandVFXController>();
            if (ctrl == null)
                ctrl = go.AddComponent<HybridBrandVFXController>();

            ctrl.SetHybridBrand("{hybrid_brand}");

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"hybrid_brand_vfx\\", \\"hybrid\\": \\"{hybrid_brand}\\", \\"object\\": \\"" + go.name + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Hybrid Brand VFX set up for {hybrid_brand} on " + go.name);
        }}
        catch (Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"hybrid_brand_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Hybrid Brand VFX setup failed: " + ex.Message);
        }}
    }}
}}
#endif
'''

    return {
        "script_path": f"Assets/Editor/Generated/VFX/VB_HybridBrandVFX_{safe_brand}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Use menu: VeilBreakers > VFX > Hybrid Brand VFX > Setup {safe_brand}",
            "Select a GameObject first, or a new one will be created",
            f"Call SetHybridBrand(\"{hybrid_brand}\") to set hybrid brand at runtime",
            "Call TriggerHybridAbility(abilityName) to fire hybrid VFX",
            "Color lerp between parent brands runs automatically in Update",
            "All 6 hybrids supported: BLOODIRON, RAVENOUS, CORROSIVE, TERRORFLUX, VENOMSTRIKE, NIGHTLEECH",
        ],
    }


# ---------------------------------------------------------------------------
# 3. Execute Threshold VFX
# ---------------------------------------------------------------------------

# Brand-specific execute VFX configs
BRAND_EXECUTE_CONFIGS: dict[str, dict[str, Any]] = {
    "SAVAGE": {"desc": "blood splatter execution", "burst": 300, "size": 0.4, "speed": 12.0, "gravity": -2.0},
    "VOID": {"desc": "dimensional collapse", "burst": 200, "size": 0.7, "speed": 3.0, "gravity": 0.0},
    "IRON": {"desc": "shrapnel burst", "burst": 250, "size": 0.15, "speed": 15.0, "gravity": -3.0},
    "SURGE": {"desc": "electric overload", "burst": 400, "size": 0.08, "speed": 25.0, "gravity": 0.0},
    "VENOM": {"desc": "toxic rupture", "burst": 180, "size": 0.3, "speed": 5.0, "gravity": -0.5},
    "DREAD": {"desc": "soul rend", "burst": 150, "size": 0.5, "speed": 4.0, "gravity": 0.0},
    "LEECH": {"desc": "vampiric drain burst", "burst": 200, "size": 0.25, "speed": -4.0, "gravity": 0.0},
    "GRACE": {"desc": "holy smite", "burst": 350, "size": 0.35, "speed": 10.0, "gravity": 0.0},
    "MEND": {"desc": "nature reclaim", "burst": 160, "size": 0.3, "speed": 3.0, "gravity": 0.1},
    "RUIN": {"desc": "infernal detonation", "burst": 280, "size": 0.45, "speed": 8.0, "gravity": -1.0},
}


def _build_brand_execute_cs_entries() -> str:
    """Build C# dictionary initializer for brand-specific execute VFX configs."""
    lines = []
    for brand, cfg in BRAND_EXECUTE_CONFIGS.items():
        rgba = BRAND_PRIMARY_COLORS.get(brand, BRAND_PRIMARY_COLORS["IRON"])
        glow = BRAND_GLOW_COLORS.get(brand, BRAND_GLOW_COLORS["IRON"])
        lines.append(f'            {{ "{brand}", new BrandExecuteConfig(')
        lines.append(f'                "{brand}", "{cfg["desc"]}",')
        lines.append(f"                {_fmt_color(rgba)}, {_fmt_color(glow)},")
        lines.append(f'                {cfg["burst"]}, {cfg["size"]}f, {cfg["speed"]}f, {cfg["gravity"]}f')
        lines.append(f"            ) }},")
    return "\n".join(lines)


def generate_execute_threshold_vfx_script() -> dict[str, Any]:
    """Generate ExecuteThresholdVFXController for execute mechanics VFX.

    Provides visual indicators when enemies drop below execute threshold,
    pulsing ring, skull particles, execution flash, brand-specific kill
    VFX, and Marked_Death debuff threshold adjustments.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    brand_execute_cs = _build_brand_execute_cs_entries()
    primary_dict = _brand_colors_cs_dict(BRAND_PRIMARY_COLORS, "BrandPrimaryColors")
    glow_dict = _brand_colors_cs_dict(BRAND_GLOW_COLORS, "BrandGlowColors")

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Execute threshold VFX controller for VeilBreakers.
/// Visual indicator when enemies drop below execute HP threshold.
/// Supports pulsing ring, skull icon particles, execution flash,
/// Marked_Death debuff, and brand-specific execution VFX.
/// </summary>
public class ExecuteThresholdVFXController : MonoBehaviour
{{
    // -------------------------------------------------------------------
    // Config struct for brand-specific execute VFX
    // -------------------------------------------------------------------

    [Serializable]
    public struct BrandExecuteConfig
    {{
        public string Brand;
        public string Description;
        public Color PrimaryColor;
        public Color GlowColor;
        public int BurstCount;
        public float Size;
        public float Speed;
        public float Gravity;

        public BrandExecuteConfig(string brand, string desc, Color primary, Color glow,
            int burst, float size, float speed, float gravity)
        {{
            Brand = brand; Description = desc; PrimaryColor = primary; GlowColor = glow;
            BurstCount = burst; Size = size; Speed = speed; Gravity = gravity;
        }}
    }}

    // -------------------------------------------------------------------
    // Inspector
    // -------------------------------------------------------------------

    [Header("Threshold Settings")]
    [SerializeField] private float executeThreshold = 0.10f;
    [SerializeField] private float markedDeathBonusThreshold = 0.15f;

    [Header("Pulsing Ring")]
    [SerializeField] private float ringRadius = 1.2f;
    [SerializeField] private float ringPulseSpeed = 3.0f;
    [SerializeField] private float ringPulseAmplitude = 0.2f;
    [SerializeField] private Color ringColor = new Color(0.8f, 0.1f, 0.1f, 0.7f);

    [Header("Skull Particles")]
    [SerializeField] private float skullSpawnRate = 5f;
    [SerializeField] private float skullRiseSpeed = 1.0f;
    [SerializeField] private float skullSize = 0.3f;

    [Header("Execution Flash")]
    [SerializeField] private float heroFlashDuration = 0.4f;
    [SerializeField] private Color heroFlashColor = new Color(1.0f, 0.85f, 0.3f, 1.0f);
    [SerializeField] private Color monsterFlashColor = new Color(0.2f, 0.05f, 0.15f, 1.0f);

    [Header("VFX Scale")]
    [SerializeField] private float vfxScale = 1.0f;

    // -------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------

    public event Action OnThresholdEntered;
    public event Action OnThresholdExited;
    public event Action<string> OnExecuteTriggered;

    // -------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------

    private bool isInThreshold;
    private bool isMarkedForDeath;
    private float currentHPPercent = 1.0f;
    private float effectiveThreshold;

    // VFX references
    private ParticleSystem ringPS;
    private ParticleSystem skullPS;
    private ParticleSystem executeFlashPS;
    private ParticleSystem brandExecutePS;
    private Material particleMaterial;
    private float pulseTimer;

    // Brand colors
{primary_dict}

{glow_dict}

    // Brand execute configs
    private static readonly Dictionary<string, BrandExecuteConfig> BrandExecuteConfigs = new Dictionary<string, BrandExecuteConfig>
    {{
{brand_execute_cs}
    }};

    // -------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------

    private void Awake()
    {{
        CreateParticleMaterial();
        effectiveThreshold = executeThreshold;
        CreateRingParticleSystem();
        CreateSkullParticleSystem();
        CreateExecuteFlashPS();
        CreateBrandExecutePS();
    }}

    private void Update()
    {{
        if (!isInThreshold) return;

        // Pulse the ring
        pulseTimer += Time.deltaTime * ringPulseSpeed;
        float pulseScale = 1.0f + Mathf.Sin(pulseTimer) * ringPulseAmplitude;

        if (ringPS != null)
        {{
            var shape = ringPS.shape;
            shape.radius = ringRadius * pulseScale * vfxScale;

            // Intensify pulse rate as HP gets lower
            float urgency = 1.0f - (currentHPPercent / effectiveThreshold);
            var emission = ringPS.emission;
            emission.rateOverTime = 30f + urgency * 50f;
        }}
    }}

    private void OnDestroy()
    {{
        if (ringPS != null) Destroy(ringPS.gameObject);
        if (skullPS != null) Destroy(skullPS.gameObject);
        if (executeFlashPS != null) Destroy(executeFlashPS.gameObject);
        if (brandExecutePS != null) Destroy(brandExecutePS.gameObject);
        if (particleMaterial != null) Destroy(particleMaterial);
    }}

    // -------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------

    /// <summary>Set the base execute threshold (0-1 HP percentage).</summary>
    public void SetThreshold(float hpPercent)
    {{
        executeThreshold = Mathf.Clamp01(hpPercent);
        RecalculateEffectiveThreshold();
    }}

    /// <summary>Update HP and trigger threshold VFX changes.</summary>
    public void UpdateHP(float currentHP, float maxHP)
    {{
        if (maxHP <= 0f) return;
        currentHPPercent = Mathf.Clamp01(currentHP / maxHP);

        bool wasInThreshold = isInThreshold;
        isInThreshold = currentHPPercent <= effectiveThreshold && currentHPPercent > 0f;

        if (isInThreshold && !wasInThreshold)
        {{
            EnterThreshold();
        }}
        else if (!isInThreshold && wasInThreshold)
        {{
            ExitThreshold();
        }}
    }}

    /// <summary>Trigger execute kill VFX with brand-specific effects.</summary>
    public void OnExecuteKill(string brand)
    {{
        string key = brand?.ToUpperInvariant() ?? "IRON";
        bool isHeroKill = true; // Default; caller can extend

        // Flash
        StartCoroutine(ExecuteFlash(isHeroKill));

        // Brand-specific execute VFX
        if (BrandExecuteConfigs.TryGetValue(key, out var config))
        {{
            TriggerBrandExecuteVFX(config);
        }}
        else
        {{
            TriggerBrandExecuteVFX(BrandExecuteConfigs["IRON"]);
        }}

        // Exit threshold state
        isInThreshold = false;
        StopThresholdVFX();

        OnExecuteTriggered?.Invoke(key);
        Debug.Log($"[ExecuteVFX] Execute kill triggered with brand {{key}}");
    }}

    /// <summary>Apply Marked_Death debuff, raising effective threshold.</summary>
    public void ApplyMarkedDeath(bool active)
    {{
        isMarkedForDeath = active;
        RecalculateEffectiveThreshold();

        // Re-evaluate current HP against new threshold
        bool wasInThreshold = isInThreshold;
        isInThreshold = currentHPPercent <= effectiveThreshold && currentHPPercent > 0f;

        if (isInThreshold && !wasInThreshold)
            EnterThreshold();
        else if (!isInThreshold && wasInThreshold)
            ExitThreshold();
    }}

    /// <summary>Get the current effective execute threshold.</summary>
    public float GetEffectiveThreshold() => effectiveThreshold;

    /// <summary>Check if currently in execute threshold.</summary>
    public bool IsInThreshold() => isInThreshold;

    // -------------------------------------------------------------------
    // Internal: threshold transitions
    // -------------------------------------------------------------------

    private void RecalculateEffectiveThreshold()
    {{
        effectiveThreshold = executeThreshold;
        if (isMarkedForDeath)
            effectiveThreshold += markedDeathBonusThreshold;
        effectiveThreshold = Mathf.Clamp01(effectiveThreshold);
    }}

    private void EnterThreshold()
    {{
        pulseTimer = 0f;
        if (ringPS != null) ringPS.Play();
        if (skullPS != null) skullPS.Play();
        OnThresholdEntered?.Invoke();
    }}

    private void ExitThreshold()
    {{
        StopThresholdVFX();
        OnThresholdExited?.Invoke();
    }}

    private void StopThresholdVFX()
    {{
        if (ringPS != null && ringPS.isPlaying)
            ringPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        if (skullPS != null && skullPS.isPlaying)
            skullPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // -------------------------------------------------------------------
    // Internal: particle system creation
    // -------------------------------------------------------------------

    private void CreateParticleMaterial()
    {{
        particleMaterial = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        particleMaterial.SetFloat("_Surface", 1);
        particleMaterial.SetFloat("_Blend", 0);
        particleMaterial.renderQueue = 3000;
    }}

    private void CreateRingParticleSystem()
    {{
        var go = new GameObject("ExecuteThreshold_Ring");
        go.transform.SetParent(transform, false);
        ringPS = go.AddComponent<ParticleSystem>();

        var main = ringPS.main;
        main.startLifetime = 1.5f;
        main.startSize = new ParticleSystem.MinMaxCurve(0.05f * vfxScale, 0.12f * vfxScale);
        main.startSpeed = 0.3f;
        main.startColor = ringColor;
        main.maxParticles = 200;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.loop = true;
        main.playOnAwake = false;

        var emission = ringPS.emission;
        emission.rateOverTime = 40f;

        var shape = ringPS.shape;
        shape.shapeType = ParticleSystemShapeType.Circle;
        shape.radius = ringRadius * vfxScale;
        shape.arc = 360f;
        shape.arcMode = ParticleSystemShapeMultiModeValue.Random;

        var col = ringPS.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(ringColor, 0f),
                new GradientColorKey(new Color(1f, 0.2f, 0.2f, 1f), 0.5f),
                new GradientColorKey(ringColor, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.8f, 0.3f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOverLife = ringPS.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0.3f));

        var renderer = ringPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void CreateSkullParticleSystem()
    {{
        var go = new GameObject("ExecuteThreshold_Skulls");
        go.transform.SetParent(transform, false);
        go.transform.localPosition = new Vector3(0f, 2.0f, 0f);
        skullPS = go.AddComponent<ParticleSystem>();

        var main = skullPS.main;
        main.startLifetime = 2.0f;
        main.startSize = skullSize * vfxScale;
        main.startSpeed = skullRiseSpeed;
        main.startColor = new Color(0.9f, 0.1f, 0.1f, 0.8f);
        main.maxParticles = 30;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = -0.3f;
        main.loop = true;
        main.playOnAwake = false;

        var emission = skullPS.emission;
        emission.rateOverTime = skullSpawnRate;

        var shape = skullPS.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.3f * vfxScale;

        var col = skullPS.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(new Color(0.9f, 0.2f, 0.2f, 1f), 0f),
                new GradientColorKey(new Color(0.5f, 0.05f, 0.05f, 1f), 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.9f, 0.2f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var renderer = skullPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void CreateExecuteFlashPS()
    {{
        var go = new GameObject("ExecuteThreshold_Flash");
        go.transform.SetParent(transform, false);
        executeFlashPS = go.AddComponent<ParticleSystem>();

        var main = executeFlashPS.main;
        main.startLifetime = heroFlashDuration;
        main.startSize = 3.0f * vfxScale;
        main.startSpeed = 0f;
        main.startColor = heroFlashColor;
        main.maxParticles = 5;
        main.simulationSpace = ParticleSystemSimulationSpace.Local;
        main.loop = false;
        main.playOnAwake = false;

        var emission = executeFlashPS.emission;
        emission.rateOverTime = 0;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, 3)
        }});

        var sizeOverLife = executeFlashPS.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0f, 1f, 3f));

        var col = executeFlashPS.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(heroFlashColor, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var renderer = executeFlashPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void CreateBrandExecutePS()
    {{
        var go = new GameObject("ExecuteThreshold_BrandKill");
        go.transform.SetParent(transform, false);
        brandExecutePS = go.AddComponent<ParticleSystem>();

        var main = brandExecutePS.main;
        main.startLifetime = 0.8f;
        main.startSize = 0.3f * vfxScale;
        main.startSpeed = 8f;
        main.maxParticles = 500;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.loop = false;
        main.playOnAwake = false;

        var emission = brandExecutePS.emission;
        emission.rateOverTime = 0;

        var shape = brandExecutePS.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.3f * vfxScale;

        var sizeOverLife = brandExecutePS.sizeOverLifetime;
        sizeOverLife.enabled = true;
        sizeOverLife.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        var renderer = brandExecutePS.GetComponent<ParticleSystemRenderer>();
        renderer.material = particleMaterial;
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    // -------------------------------------------------------------------
    // Internal: execute effects
    // -------------------------------------------------------------------

    private IEnumerator ExecuteFlash(bool isHeroKill)
    {{
        if (executeFlashPS == null) yield break;

        var main = executeFlashPS.main;
        main.startColor = isHeroKill ? heroFlashColor : monsterFlashColor;
        main.startLifetime = heroFlashDuration;
        executeFlashPS.Clear();
        executeFlashPS.Play();

        yield return new WaitForSeconds(heroFlashDuration + 0.1f);
    }}

    private void TriggerBrandExecuteVFX(BrandExecuteConfig config)
    {{
        if (brandExecutePS == null) return;

        var main = brandExecutePS.main;
        main.startColor = config.PrimaryColor;
        main.startSize = config.Size * vfxScale;
        main.startSpeed = Mathf.Abs(config.Speed);
        main.gravityModifier = config.Gravity;
        main.startLifetime = 0.8f;

        var emission = brandExecutePS.emission;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, (short)config.BurstCount)
        }});

        // Inward pull for drain-type brands
        var vel = brandExecutePS.velocityOverLifetime;
        if (config.Speed < 0)
        {{
            vel.enabled = true;
            vel.radial = config.Speed;
        }}
        else
        {{
            vel.enabled = false;
        }}

        // Brand glow gradient
        var col = brandExecutePS.colorOverLifetime;
        col.enabled = true;
        var grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(config.GlowColor, 0f),
                new GradientColorKey(config.PrimaryColor, 0.5f),
                new GradientColorKey(config.PrimaryColor * 0.5f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0.8f, 0.4f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        brandExecutePS.Clear();
        brandExecutePS.Play();
    }}
}}

// ======================================================================
// Editor setup menu
// ======================================================================
#if UNITY_EDITOR
public static class VB_ExecuteThresholdVFXSetup
{{
    [MenuItem("VeilBreakers/VFX/Execute Threshold VFX/Setup")]
    public static void Setup()
    {{
        try
        {{
            var selected = Selection.activeGameObject;
            GameObject go;
            if (selected != null)
            {{
                go = selected;
            }}
            else
            {{
                go = new GameObject("ExecuteThresholdVFX");
            }}

            var ctrl = go.GetComponent<ExecuteThresholdVFXController>();
            if (ctrl == null)
                ctrl = go.AddComponent<ExecuteThresholdVFXController>();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"execute_threshold_vfx\\", \\"object\\": \\"" + go.name + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Execute Threshold VFX set up on " + go.name);
        }}
        catch (Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"execute_threshold_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Execute Threshold VFX setup failed: " + ex.Message);
        }}
    }}
}}
#endif
'''

    return {
        "script_path": "Assets/Editor/Generated/VFX/VB_ExecuteThresholdVFX.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Use menu: VeilBreakers > VFX > Execute Threshold VFX > Setup",
            "Select an enemy GameObject first, or a new one will be created",
            "Call SetThreshold(0.10f) to set execute HP threshold (10%)",
            "Call UpdateHP(currentHP, maxHP) each frame to drive threshold VFX",
            "Call OnExecuteKill(brand) when execute kill triggers to play brand VFX",
            "Call ApplyMarkedDeath(true) when Marked_Death debuff is applied",
            "Subscribe to OnThresholdEntered/OnThresholdExited/OnExecuteTriggered events",
            "All 10 brands have unique execution VFX (SAVAGE=blood splatter, VOID=dimensional collapse, etc.)",
        ],
    }
