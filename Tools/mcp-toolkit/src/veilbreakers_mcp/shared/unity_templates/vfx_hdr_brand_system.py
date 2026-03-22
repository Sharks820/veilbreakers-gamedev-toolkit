"""VFX HDR Brand System -- definitive brand color + HDR system for VeilBreakers.

This is the SINGLE SOURCE OF TRUTH for all brand colors in VFX.  Every other
VFX template should import from this module rather than defining its own
brand color dictionaries.

Generates a ``VBBrandHDR`` static utility class containing:
- Per-brand ``BrandProfile`` structs (10 base + 6 hybrids)
- HDR-ready color values tuned for URP bloom
- Per-brand blend mode recommendations
- Gradient factory methods (lifetime, smoke, flash)
- Standard animation curves (size, speed over lifetime)
- Performance budget constants

Unity 2022.3+ URP.

Exports:
    generate_hdr_brand_system_script -- VBBrandHDR static utility class
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Brand profile data (Python-side canonical source)
# ---------------------------------------------------------------------------

_BASE_BRANDS: dict[str, dict[str, Any]] = {
    "IRON": {
        "primary": [0.55, 0.59, 0.65, 1.0],
        "glow": [0.71, 0.75, 0.80, 1.0],
        "dark": [0.31, 0.35, 0.39, 1.0],
        "flash": [0.90, 0.45, 0.12, 1.0],
        "bloom": 3.0,
        "core_blend": "Additive",
        "texture": "SoftGlow",
        "runic_glow": [0.90, 0.45, 0.12, 1.0],
        "runic_bloom": 5.0,
        "desc": "Steel gray metal with orange-red runic glow",
    },
    "SURGE": {
        "primary": [0.24, 0.55, 0.86, 1.0],
        "glow": [0.39, 0.71, 1.00, 1.0],
        "dark": [0.12, 0.31, 0.55, 1.0],
        "flash": [0.85, 0.93, 1.00, 1.0],
        "bloom": 5.0,
        "core_blend": "Additive",
        "texture": "ElectricArc",
        "desc": "Electric blue-white with branching arcs",
    },
    "SAVAGE": {
        "primary": [0.71, 0.18, 0.18, 1.0],
        "glow": [0.86, 0.27, 0.27, 1.0],
        "dark": [0.47, 0.10, 0.10, 1.0],
        "flash": [1.00, 0.40, 0.20, 1.0],
        "bloom": 5.0,
        "core_blend": "Additive",
        "texture": "BloodSplatter",
        "desc": "Blood red, aggressive",
    },
    "VENOM": {
        "primary": [0.31, 0.71, 0.24, 1.0],
        "glow": [0.47, 0.86, 0.39, 1.0],
        "dark": [0.16, 0.39, 0.12, 1.0],
        "flash": [0.70, 1.00, 0.40, 1.0],
        "bloom": 4.0,
        "core_blend": "AlphaBlend",
        "texture": "AcidDrip",
        "desc": "Toxic green with acid drip",
    },
    "DREAD": {
        "primary": [0.47, 0.24, 0.63, 1.0],
        "glow": [0.63, 0.39, 0.78, 1.0],
        "dark": [0.27, 0.12, 0.39, 1.0],
        "flash": [0.80, 0.50, 1.00, 1.0],
        "bloom": 5.0,
        "core_blend": "Additive",
        "texture": "ShadowWisp",
        "desc": "Deep purple fear",
    },
    "LEECH": {
        "primary": [0.55, 0.16, 0.31, 1.0],
        "glow": [0.71, 0.24, 0.43, 1.0],
        "dark": [0.35, 0.08, 0.20, 1.0],
        "flash": [0.90, 0.35, 0.50, 1.0],
        "bloom": 4.0,
        "core_blend": "AlphaBlend",
        "texture": "DrainTendril",
        "desc": "Dark crimson drain",
    },
    "GRACE": {
        "primary": [0.86, 0.86, 0.94, 1.0],
        "glow": [1.00, 1.00, 1.00, 1.0],
        "dark": [0.63, 0.63, 0.71, 1.0],
        "flash": [1.00, 1.00, 1.00, 1.0],
        "bloom": 6.0,
        "core_blend": "Additive",
        "texture": "HolyMotes",
        "desc": "Holy white-silver (highest bloom)",
    },
    "MEND": {
        "primary": [0.78, 0.67, 0.31, 1.0],
        "glow": [0.94, 0.82, 0.47, 1.0],
        "dark": [0.55, 0.43, 0.16, 1.0],
        "flash": [1.00, 0.90, 0.50, 1.0],
        "bloom": 4.0,
        "core_blend": "Additive",
        "texture": "HealingRing",
        "desc": "Golden healing warmth",
    },
    "RUIN": {
        "primary": [0.86, 0.47, 0.16, 1.0],
        "glow": [1.00, 0.63, 0.31, 1.0],
        "dark": [0.63, 0.27, 0.08, 1.0],
        "flash": [1.00, 0.70, 0.30, 1.0],
        "bloom": 5.0,
        "core_blend": "Additive",
        "texture": "EmberBurst",
        "desc": "Destruction fire orange",
    },
    "VOID": {
        "primary": [0.16, 0.08, 0.24, 1.0],
        "glow": [0.39, 0.24, 0.55, 1.0],
        "dark": [0.06, 0.02, 0.10, 1.0],
        "flash": [0.86, 0.08, 0.08, 1.0],
        "bloom": 4.0,
        "core_blend": "AlphaBlend",
        "texture": "VoidRift",
        "void_core_bloom": 6.0,
        "desc": "Void dark with red core",
    },
}

_HYBRID_DEFS: list[tuple[str, str, str, int]] = [
    ("BLOODIRON", "SAVAGE", "IRON", 11),
    ("RAVENOUS", "SAVAGE", "LEECH", 12),
    ("CORROSIVE", "VENOM", "RUIN", 13),
    ("TERRORFLUX", "DREAD", "SURGE", 14),
    ("VENOMSTRIKE", "VENOM", "SAVAGE", 15),
    ("NIGHTLEECH", "DREAD", "LEECH", 16),
]

ALL_BASE_BRANDS = list(_BASE_BRANDS.keys())


def _lerp_color(a: list[float], b: list[float], t: float = 0.5) -> list[float]:
    """Lerp two RGBA color lists."""
    return [a[i] + (b[i] - a[i]) * t for i in range(4)]


def _build_hybrid_brands() -> dict[str, dict[str, Any]]:
    """Build hybrid brand profiles as 50/50 blends of parent brands."""
    hybrids: dict[str, dict[str, Any]] = {}
    for name, parent_a, parent_b, index in _HYBRID_DEFS:
        a = _BASE_BRANDS[parent_a]
        b = _BASE_BRANDS[parent_b]
        hybrids[name] = {
            "primary": _lerp_color(a["primary"], b["primary"]),
            "glow": _lerp_color(a["glow"], b["glow"]),
            "dark": _lerp_color(a["dark"], b["dark"]),
            "flash": _lerp_color(a["flash"], b["flash"]),
            "bloom": (a["bloom"] + b["bloom"]) / 2.0,
            "core_blend": "Additive",
            "texture": "SoftGlow",
            "index": index,
            "desc": f"Hybrid of {parent_a} + {parent_b}",
        }
    return hybrids


HYBRID_BRANDS = _build_hybrid_brands()
ALL_BRANDS = ALL_BASE_BRANDS + list(HYBRID_BRANDS.keys())
ALL_BRAND_DATA: dict[str, dict[str, Any]] = {**_BASE_BRANDS, **HYBRID_BRANDS}


# ---------------------------------------------------------------------------
# C# code generation helpers
# ---------------------------------------------------------------------------

def _fmt_color(rgba: list[float]) -> str:
    """Format [r, g, b, a] to C# ``new Color(r, g, b, a)``."""
    r, g, b, a = (round(v, 3) for v in rgba)
    return f"new Color({r}f, {g}f, {b}f, {a}f)"


def _brand_profile_cs(name: str, data: dict[str, Any]) -> str:
    """Return a C# BrandProfile readonly static field for one brand."""
    lines: list[str] = []
    lines.append(f"        // {name} -- {data['desc']}")
    lines.append(f"        public static readonly BrandProfile {name} = new BrandProfile {{")
    lines.append(f"            primary = {_fmt_color(data['primary'])},")
    lines.append(f"            glow = {_fmt_color(data['glow'])},")
    lines.append(f"            dark = {_fmt_color(data['dark'])},")
    lines.append(f"            flash = {_fmt_color(data['flash'])},")
    lines.append(f"            bloomMultiplier = {data['bloom']}f,")
    lines.append(f'            coreBlendMode = "{data.get("core_blend", "Additive")}",')
    lines.append(f'            smokeBlendMode = "AlphaBlend",')
    lines.append(f'            particleTexture = "{data.get("texture", "SoftGlow")}",')
    # IRON has runic glow fields
    if "runic_glow" in data:
        lines.append(f"            runicGlow = {_fmt_color(data['runic_glow'])},")
        lines.append(f"            runicBloomMultiplier = {data['runic_bloom']}f,")
    # VOID has separate core bloom
    if "void_core_bloom" in data:
        lines.append(f"            voidCoreBloomMultiplier = {data['void_core_bloom']}f,")
    lines.append("        };")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_hdr_brand_system_script() -> dict[str, Any]:
    """Generate VBBrandHDR static utility class -- single source of truth for brand colors in VFX.

    Returns:
        Dict with ``script_path``, ``script_content``, ``next_steps``.
    """
    # Build all brand profile C# blocks
    brand_blocks: list[str] = []
    for name in ALL_BASE_BRANDS:
        brand_blocks.append(_brand_profile_cs(name, _BASE_BRANDS[name]))
    brand_blocks.append("")
    brand_blocks.append("        // --- Hybrid Brands (50/50 blends) ---")
    for name in HYBRID_BRANDS:
        brand_blocks.append(_brand_profile_cs(name, HYBRID_BRANDS[name]))

    brand_profiles_cs = "\n\n".join(brand_blocks)

    # Build lookup dictionary entries
    lookup_entries: list[str] = []
    for name in ALL_BRANDS:
        lookup_entries.append(f'            {{ "{name}", {name} }},')
    lookup_cs = "\n".join(lookup_entries)

    script = f'''// =============================================================================
// VBBrandHDR.cs -- Auto-generated by VeilBreakers MCP Toolkit
// SINGLE SOURCE OF TRUTH for all brand colors, HDR values, and VFX utilities.
// Do NOT hand-edit -- regenerate via vfx_hdr_brand_system.py
// =============================================================================
using UnityEngine;
using System.Collections.Generic;

namespace VeilBreakers.VFX
{{
    /// <summary>
    /// Brand profile data container. Each brand has primary, glow, dark, and
    /// flash colors plus bloom multiplier and blend mode recommendations.
    /// </summary>
    [System.Serializable]
    public struct BrandProfile
    {{
        public Color primary;
        public Color glow;
        public Color dark;
        public Color flash;
        public float bloomMultiplier;
        public string coreBlendMode;
        public string smokeBlendMode;
        public string particleTexture;

        // IRON-specific: runic orange glow (separate from main glow)
        public Color runicGlow;
        public float runicBloomMultiplier;

        // VOID-specific: red core uses higher bloom than dark body
        public float voidCoreBloomMultiplier;
    }}

    /// <summary>
    /// VBBrandHDR -- static utility class providing HDR-ready brand colors,
    /// gradient factories, animation curves, and performance budgets for all
    /// VeilBreakers VFX. Every VFX system should reference this class instead
    /// of defining its own brand colors.
    /// </summary>
    public static class VBBrandHDR
    {{
        // =====================================================================
        // Performance Budgets
        // =====================================================================

        /// <summary>Max particles per individual VFX effect.</summary>
        public const int MAX_PARTICLES_PER_EFFECT = 55;

        /// <summary>Max simultaneously active VFX effects.</summary>
        public const int MAX_ACTIVE_EFFECTS = 40;

        /// <summary>Global particle budget across all active effects.</summary>
        public const int GLOBAL_PARTICLE_BUDGET = 2000;

        /// <summary>LOD distance threshold: close (full quality).</summary>
        public const float LOD_CLOSE_DISTANCE = 15f;

        /// <summary>LOD distance threshold: medium (reduced particles).</summary>
        public const float LOD_MEDIUM_DISTANCE = 40f;

        /// <summary>LOD distance threshold: far (minimal particles).</summary>
        public const float LOD_FAR_DISTANCE = 80f;

        // =====================================================================
        // Brand Profiles -- 10 Base Brands
        // =====================================================================

{brand_profiles_cs}

        // =====================================================================
        // Brand Lookup Dictionary
        // =====================================================================

        private static readonly Dictionary<string, BrandProfile> _profiles =
            new Dictionary<string, BrandProfile>
        {{
{lookup_cs}
        }};

        /// <summary>
        /// Get a brand profile by name. Returns IRON as fallback for unknown brands.
        /// </summary>
        public static BrandProfile GetProfile(string brandName)
        {{
            if (_profiles.TryGetValue(brandName.ToUpperInvariant(), out var profile))
                return profile;
            Debug.LogWarning($"[VBBrandHDR] Unknown brand '{{brandName}}', falling back to IRON.");
            return IRON;
        }}

        /// <summary>All registered brand names.</summary>
        public static IReadOnlyCollection<string> AllBrandNames => _profiles.Keys;

        // =====================================================================
        // HDR Emission Helpers
        // =====================================================================

        /// <summary>
        /// Get the HDR emission color for bloom. Multiplies glow by bloomMultiplier.
        /// Feed this to material _EmissionColor or particle color-over-lifetime HDR peak.
        /// </summary>
        public static Color GetHDREmission(BrandProfile brand)
        {{
            return brand.glow * brand.bloomMultiplier;
        }}

        /// <summary>
        /// Get the momentary flash emission (1-2 frames at birth/impact).
        /// 1.5x stronger than standard emission for burst visibility.
        /// </summary>
        public static Color GetFlashEmission(BrandProfile brand)
        {{
            return brand.flash * (brand.bloomMultiplier * 1.5f);
        }}

        /// <summary>
        /// Get IRON-specific runic glow emission. Returns zero color for non-IRON brands.
        /// </summary>
        public static Color GetRunicEmission(BrandProfile brand)
        {{
            if (brand.runicBloomMultiplier > 0f)
                return brand.runicGlow * brand.runicBloomMultiplier;
            return Color.clear;
        }}

        /// <summary>
        /// Get VOID-specific red core emission. Returns standard emission for non-VOID brands.
        /// </summary>
        public static Color GetVoidCoreEmission(BrandProfile brand)
        {{
            if (brand.voidCoreBloomMultiplier > 0f)
                return brand.flash * brand.voidCoreBloomMultiplier;
            return GetHDREmission(brand);
        }}

        // =====================================================================
        // Gradient Factory Methods
        // =====================================================================

        /// <summary>
        /// Creates the AAA 3-phase lifetime gradient: birth flash -> sustain -> dissipate.
        /// Use this for core particle color-over-lifetime.
        /// </summary>
        public static Gradient CreateLifetimeGradient(BrandProfile brand)
        {{
            var grad = new Gradient();
            grad.SetKeys(
                new GradientColorKey[] {{
                    new GradientColorKey(Color.white, 0f),
                    new GradientColorKey(brand.glow, 0.05f),
                    new GradientColorKey(brand.primary, 0.15f),
                    new GradientColorKey(brand.primary, 0.60f),
                    new GradientColorKey(brand.dark, 0.85f),
                    new GradientColorKey(Color.black, 1f),
                }},
                new GradientAlphaKey[] {{
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(1f, 0.05f),
                    new GradientAlphaKey(0.8f, 0.15f),
                    new GradientAlphaKey(0.6f, 0.60f),
                    new GradientAlphaKey(0.15f, 0.85f),
                    new GradientAlphaKey(0f, 1f),
                }}
            );
            return grad;
        }}

        /// <summary>
        /// Creates smoke/trail dissipation gradient. Never use for core particles --
        /// only for trail, smoke, and ground fog layers.  Always AlphaBlend.
        /// </summary>
        public static Gradient CreateSmokeGradient(BrandProfile brand)
        {{
            var grad = new Gradient();
            grad.SetKeys(
                new GradientColorKey[] {{
                    new GradientColorKey(brand.dark, 0f),
                    new GradientColorKey(brand.dark, 0.3f),
                    new GradientColorKey(brand.dark * 0.5f, 0.7f),
                    new GradientColorKey(Color.black, 1f),
                }},
                new GradientAlphaKey[] {{
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(0.35f, 0.1f),
                    new GradientAlphaKey(0.25f, 0.4f),
                    new GradientAlphaKey(0.08f, 0.75f),
                    new GradientAlphaKey(0f, 1f),
                }}
            );
            return grad;
        }}

        /// <summary>
        /// Creates impact/birth flash gradient -- very short, for 1-3 frame bursts.
        /// </summary>
        public static Gradient CreateFlashGradient(BrandProfile brand)
        {{
            var grad = new Gradient();
            var hdrFlash = brand.flash * (brand.bloomMultiplier * 1.5f);
            grad.SetKeys(
                new GradientColorKey[] {{
                    new GradientColorKey(hdrFlash, 0f),
                    new GradientColorKey(brand.glow, 0.3f),
                    new GradientColorKey(brand.primary * 0.3f, 0.7f),
                    new GradientColorKey(Color.black, 1f),
                }},
                new GradientAlphaKey[] {{
                    new GradientAlphaKey(1f, 0f),
                    new GradientAlphaKey(0.7f, 0.15f),
                    new GradientAlphaKey(0.2f, 0.5f),
                    new GradientAlphaKey(0f, 1f),
                }}
            );
            return grad;
        }}

        // =====================================================================
        // Standard Animation Curves
        // =====================================================================

        /// <summary>
        /// AAA standard size-over-lifetime curve.
        /// Start small -> quick grow -> peak at 30% -> slow shrink -> zero.
        /// </summary>
        public static AnimationCurve StandardSizeCurve()
        {{
            return new AnimationCurve(
                new Keyframe(0f, 0.1f),
                new Keyframe(0.15f, 0.8f),
                new Keyframe(0.3f, 1f),
                new Keyframe(0.7f, 0.9f),
                new Keyframe(1f, 0f)
            );
        }}

        /// <summary>
        /// AAA standard speed-over-lifetime curve.
        /// Full speed at birth -> decelerate -> slow -> near stop at death.
        /// </summary>
        public static AnimationCurve StandardSpeedCurve()
        {{
            return new AnimationCurve(
                new Keyframe(0f, 1f),
                new Keyframe(0.3f, 0.5f),
                new Keyframe(0.7f, 0.2f),
                new Keyframe(1f, 0.05f)
            );
        }}

        /// <summary>
        /// Burst flash size curve -- quick expand then instant collapse.
        /// Use for impact/birth flash particles with very short lifetime.
        /// </summary>
        public static AnimationCurve FlashSizeCurve()
        {{
            return new AnimationCurve(
                new Keyframe(0f, 0.5f),
                new Keyframe(0.1f, 1f),
                new Keyframe(0.3f, 0.6f),
                new Keyframe(1f, 0f)
            );
        }}

        /// <summary>
        /// Smoke size curve -- starts medium, expands slowly, lingers.
        /// </summary>
        public static AnimationCurve SmokeSizeCurve()
        {{
            return new AnimationCurve(
                new Keyframe(0f, 0.3f),
                new Keyframe(0.2f, 0.6f),
                new Keyframe(0.5f, 0.85f),
                new Keyframe(0.8f, 1f),
                new Keyframe(1f, 1.1f)
            );
        }}

        // =====================================================================
        // Blend Mode Helpers
        // =====================================================================

        /// <summary>
        /// Returns true if the brand's core particles should use additive blending.
        /// </summary>
        public static bool IsAdditiveCore(BrandProfile brand)
        {{
            return brand.coreBlendMode == "Additive";
        }}

        /// <summary>
        /// Get the ParticleSystemRenderMode appropriate for the brand's core particles.
        /// </summary>
        public static ParticleSystemRenderMode GetCoreRenderMode(BrandProfile brand)
        {{
            return ParticleSystemRenderMode.Billboard;
        }}

        /// <summary>
        /// Get LOD particle multiplier based on camera distance.
        /// Returns 1.0 at close, 0.5 at medium, 0.15 at far.
        /// </summary>
        public static float GetLODParticleMultiplier(float distance)
        {{
            if (distance <= LOD_CLOSE_DISTANCE) return 1f;
            if (distance <= LOD_MEDIUM_DISTANCE) return 0.5f;
            if (distance <= LOD_FAR_DISTANCE) return 0.15f;
            return 0f;
        }}

        /// <summary>
        /// Get LOD size multiplier based on camera distance.
        /// Particles grow slightly at distance to maintain screen presence.
        /// </summary>
        public static float GetLODSizeMultiplier(float distance)
        {{
            if (distance <= LOD_CLOSE_DISTANCE) return 1f;
            if (distance <= LOD_MEDIUM_DISTANCE) return 1.3f;
            if (distance <= LOD_FAR_DISTANCE) return 1.8f;
            return 2.5f;
        }}
    }}
}}
'''

    script_path = "Assets/Scripts/VFX/VBBrandHDR.cs"

    return {
        "script_path": script_path,
        "script_content": script.strip() + "\n",
        "next_steps": [
            "Call unity_editor action='recompile' to compile VBBrandHDR.cs",
            "All VFX scripts can now reference VeilBreakers.VFX.VBBrandHDR",
            "Use VBBrandHDR.GetProfile(\"SURGE\") to get any brand profile",
            "Use VBBrandHDR.GetHDREmission(profile) for bloom-ready emission colors",
            "Use VBBrandHDR.CreateLifetimeGradient(profile) for color-over-lifetime",
        ],
    }
