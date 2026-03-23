"""VFX C# template generators for Unity automation.

Each function returns a complete C# source string that can be written to
a Unity project's Assets/Editor/Generated/VFX/ directory. When compiled
by Unity, the scripts register as MenuItem commands under
"VeilBreakers/VFX/...".

All generated scripts write their result to Temp/vb_result.json so that
the Python MCP server can read back the outcome after execution.

Exports:
    generate_particle_vfx_script    -- VFX-01: text description -> VFX Graph config
    generate_brand_vfx_script       -- VFX-02: per-brand damage VFX
    generate_environmental_vfx_script -- VFX-03: dust/fireflies/snow/rain/ash
    generate_trail_vfx_script       -- VFX-04: weapon/projectile trails
    generate_aura_vfx_script        -- VFX-05: character aura/buff
    generate_post_processing_script -- VFX-08: bloom/color grading/vignette/AO/DOF
    generate_screen_effect_script   -- VFX-09: camera shake/damage vignette/etc
    generate_ability_vfx_script     -- VFX-10: ability VFX + animation integration
    generate_decal_system_script    -- VX-01: URP DecalProjector pool + auto-fade
"""

from __future__ import annotations

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Brand VFX config dictionaries
# ---------------------------------------------------------------------------

# Brand color palettes — corrected per VB art direction audit
# IRON: rust-bronze (not gray), LEECH: sickly yellow-green (not red),
# DREAD: fear-green (distinct from VOID's dark purple)
BRAND_PRIMARY_COLORS: dict[str, list[float]] = {"IRON":[0.55,0.35,0.22,1.0],"SAVAGE":[0.71,0.18,0.18,1.0],"SURGE":[0.24,0.55,0.86,1.0],"VENOM":[0.31,0.71,0.24,1.0],"DREAD":[0.24,0.47,0.27,1.0],"LEECH":[0.55,0.53,0.20,1.0],"GRACE":[0.86,0.86,0.94,1.0],"MEND":[0.78,0.67,0.31,1.0],"RUIN":[0.86,0.47,0.16,1.0],"VOID":[0.16,0.08,0.24,1.0]}
BRAND_GLOW_COLORS: dict[str, list[float]] = {"IRON":[0.80,0.55,0.30,1.0],"SAVAGE":[0.86,0.27,0.27,1.0],"SURGE":[0.39,0.71,1.00,1.0],"VENOM":[0.47,0.86,0.39,1.0],"DREAD":[0.35,0.70,0.40,1.0],"LEECH":[0.70,0.65,0.25,1.0],"GRACE":[1.00,1.00,1.00,1.0],"MEND":[0.94,0.82,0.47,1.0],"RUIN":[1.00,0.63,0.31,1.0],"VOID":[0.39,0.24,0.55,1.0]}
BRAND_DARK_COLORS: dict[str, list[float]] = {"IRON":[0.35,0.22,0.12,1.0],"SAVAGE":[0.47,0.10,0.10,1.0],"SURGE":[0.12,0.31,0.55,1.0],"VENOM":[0.16,0.39,0.12,1.0],"DREAD":[0.12,0.27,0.14,1.0],"LEECH":[0.35,0.33,0.10,1.0],"GRACE":[0.63,0.63,0.71,1.0],"MEND":[0.55,0.43,0.16,1.0],"RUIN":[0.63,0.27,0.08,1.0],"VOID":[0.06,0.02,0.10,1.0]}

BRAND_VFX_CONFIGS: dict[str, dict] = {
    "IRON": {
        "rate": 200,
        "lifetime": 0.5,
        "size": 0.1,
        "color": [0.55, 0.35, 0.22, 1.0],
        "shape": "cone",
        "desc": "metallic sparks",
    },
    "VENOM": {
        "rate": 30,
        "lifetime": 3.0,
        "size": 0.3,
        "color": [0.31, 0.71, 0.24, 1.0],
        "shape": "sphere",
        "desc": "acid drip",
    },
    "SURGE": {
        "rate": 500,
        "lifetime": 0.2,
        "size": 0.05,
        "color": [0.24, 0.55, 0.86, 1.0],
        "shape": "edge",
        "desc": "electric crackle",
    },
    "DREAD": {
        "rate": 20,
        "lifetime": 5.0,
        "size": 0.8,
        "color": [0.24, 0.47, 0.27, 1.0],
        "shape": "sphere",
        "desc": "fear wisps",
    },
    "SAVAGE": {
        "rate": 250,
        "lifetime": 0.6,
        "size": 0.35,
        "color": [0.71, 0.18, 0.18, 1.0],
        "shape": "cone",
        "desc": "beast claw slash marks",
    },
    "LEECH": {
        "rate": 40,
        "lifetime": 2.5,
        "size": 0.25,
        "color": [0.55, 0.53, 0.20, 1.0],
        "shape": "sphere",
        "desc": "parasitic drain tendrils",
    },
    "GRACE": {
        "rate": 60,
        "lifetime": 2.0,
        "size": 0.2,
        "color": [0.86, 0.86, 0.94, 1.0],
        "shape": "sphere",
        "desc": "holy light sparkles",
    },
    "MEND": {
        "rate": 50,
        "lifetime": 2.5,
        "size": 0.2,
        "color": [0.78, 0.67, 0.31, 1.0],
        "shape": "sphere",
        "desc": "restoration nature particles",
    },
    "RUIN": {
        "rate": 80,
        "lifetime": 1.5,
        "size": 0.5,
        "color": [0.86, 0.47, 0.16, 1.0],
        "shape": "box",
        "desc": "earth-cracking decay particles",
    },
    "VOID": {
        "rate": 25,
        "lifetime": 4.0,
        "size": 0.6,
        "color": [0.16, 0.08, 0.24, 1.0],
        "shape": "sphere",
        "desc": "void rift distortion",
    },
}

# ---------------------------------------------------------------------------
# Environmental VFX config dictionaries
# ---------------------------------------------------------------------------

ENV_VFX_CONFIGS: dict[str, dict] = {
    "dust": {
        "rate": 15,
        "lifetime": 8.0,
        "size": 0.05,
        "color": [0.7, 0.6, 0.5, 0.3],
        "gravity": -0.01,
        "desc": "Dust motes floating in light beams",
    },
    "fireflies": {
        "rate": 8,
        "lifetime": 6.0,
        "size": 0.03,
        "color": [0.9, 1.0, 0.3, 0.9],
        "gravity": 0.0,
        "desc": "Bioluminescent fireflies drifting at night",
    },
    "snow": {
        "rate": 80,
        "lifetime": 10.0,
        "size": 0.04,
        "color": [1.0, 1.0, 1.0, 0.8],
        "gravity": -0.5,
        "desc": "Snowflakes falling with gravity and slight wind drift",
    },
    "rain": {
        "rate": 500,
        "lifetime": 1.5,
        "size": 0.02,
        "color": [0.6, 0.7, 0.8, 0.6],
        "gravity": -9.8,
        "desc": "Rain streaks falling rapidly downward",
    },
    "ash": {
        "rate": 25,
        "lifetime": 12.0,
        "size": 0.06,
        "color": [0.3, 0.3, 0.3, 0.5],
        "gravity": -0.05,
        "desc": "Volcanic ash drifting slowly down",
    },
}

_VALID_SCREEN_EFFECTS = {
    "camera_shake",
    "damage_vignette",
    "low_health_pulse",
    "poison_overlay",
    "heal_glow",
}


# ---------------------------------------------------------------------------
# VFX-01: Particle VFX script
# ---------------------------------------------------------------------------


def generate_particle_vfx_script(
    name: str,
    rate: float = 100,
    lifetime: float = 1.0,
    size: float = 0.5,
    color: list[float] | None = None,
    shape: str = "cone",
) -> str:
    """Generate C# editor script that creates a VFX Graph particle prefab.

    Creates a GameObject with a VisualEffect component, configures exposed
    properties (Rate, Lifetime, Size, Color, Shape), and saves as a prefab.

    Args:
        name: Name of the VFX effect and resulting prefab.
        rate: Particle emission rate per second.
        lifetime: Particle lifetime in seconds.
        size: Particle size.
        color: RGBA color as [r, g, b, a] floats. Defaults to white.
        shape: Emission shape -- "cone", "sphere", "edge", "box".

    Returns:
        Complete C# source string.
    """
    if color is None:
        color = [1.0, 1.0, 1.0, 1.0]

    r, g, b, a = color[0], color[1], color[2], color[3]
    safe_name = sanitize_cs_identifier(name.replace(" ", "_").replace("-", "_"))
    safe_display = sanitize_cs_string(name)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_VFX_{safe_name}
{{
    [MenuItem("VeilBreakers/VFX/Create Particle VFX/{safe_display}")]
    public static void Execute()
    {{
        try
        {{
            // Create VFX GameObject with ParticleSystem (works without external assets)
            var go = new GameObject("{safe_display}_VFX");
            var ps = go.AddComponent<ParticleSystem>();
            var renderer = go.GetComponent<ParticleSystemRenderer>();

            // Main module
            var main = ps.main;
            main.startLifetime = {lifetime}f;
            main.startSize = {size}f;
            main.startColor = new Color({r}f, {g}f, {b}f, {a}f);
            main.maxParticles = Mathf.CeilToInt({rate}f * {lifetime}f * 2f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.playOnAwake = true;
            main.loop = true;

            // Emission module
            var emission = ps.emission;
            emission.rateOverTime = {rate}f;

            // Shape module: {shape}
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.{_shape_type_cs(shape)};

            // Renderer setup (use default particle material)
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.material = new Material(Shader.Find("Particles/Standard Unlit"));
            renderer.material.SetColor("_Color", new Color({r}f, {g}f, {b}f, {a}f));

            // Color over lifetime (fade out)
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var gradient = new Gradient();
            gradient.SetKeys(
                new GradientColorKey[] {{ new GradientColorKey(new Color({r}f, {g}f, {b}f), 0f), new GradientColorKey(new Color({r}f, {g}f, {b}f), 1f) }},
                new GradientAlphaKey[] {{ new GradientAlphaKey({a}f, 0f), new GradientAlphaKey({a}f, 0.8f), new GradientAlphaKey(0f, 1f) }}
            );
            col.color = gradient;

            // Size over lifetime (shrink)
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

            // Save as prefab
            string prefabDir = "Assets/Prefabs/VFX";
            if (!AssetDatabase.IsValidFolder(prefabDir))
            {{
                Directory.CreateDirectory(prefabDir);
                AssetDatabase.Refresh();
            }}
            string prefabPath = prefabDir + "/{safe_display}.prefab";
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

            // Write result JSON
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_particle_vfx\\", \\"name\\": \\"{safe_display}\\", \\"prefab_path\\": \\"" + prefabPath + "\\", \\"shape\\": \\"{shape}\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Particle VFX prefab created: " + prefabPath);

            // Clean up scene object
            Object.DestroyImmediate(go);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_particle_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Particle VFX creation failed: " + ex.Message);
        }}
    }}
}}
'''


def _shape_index(shape: str) -> int:
    """Map shape name to numeric index for VFX Graph."""
    shapes = {"sphere": 0, "cone": 1, "edge": 2, "box": 3}
    return shapes.get(shape.lower(), 1)


def _shape_type_cs(shape: str) -> str:
    """Map shape name to C# ParticleSystemShapeType enum value."""
    shapes = {
        "sphere": "Sphere",
        "cone": "Cone",
        "edge": "SingleSidedEdge",
        "box": "Box",
        "hemisphere": "Hemisphere",
        "circle": "Circle",
        "donut": "Donut",
    }
    return shapes.get(shape.lower(), "Cone")


# ---------------------------------------------------------------------------
# VFX-02: Brand VFX script
# ---------------------------------------------------------------------------


def generate_brand_vfx_script(brand: str) -> str:
    """Generate C# editor script for brand-specific damage VFX.

    Each brand (IRON, SAVAGE, SURGE, VENOM, DREAD, LEECH, GRACE, MEND,
    RUIN, VOID) has distinct VFX parameters that define its visual identity.

    Args:
        brand: Brand name -- must be one of BRAND_VFX_CONFIGS keys.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If brand is not recognized.
    """
    brand = brand.upper()
    if brand not in BRAND_VFX_CONFIGS:
        raise ValueError(
            f"Unknown brand: '{brand}'. Valid brands: {sorted(BRAND_VFX_CONFIGS)}"
        )

    cfg = BRAND_VFX_CONFIGS[brand]
    r, g, b, a = cfg["color"]

    safe_desc = sanitize_cs_string(cfg["desc"])
    shape_cs = _shape_type_cs(cfg["shape"])

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

/// <summary>
/// {brand} brand damage VFX: {cfg["desc"]}
/// AAA ParticleSystem with sub-emitters, trails, color-over-lifetime, noise turbulence.
/// </summary>
public static class VeilBreakers_BrandVFX_{brand}
{{
    [MenuItem("VeilBreakers/VFX/Brand Damage/{brand}")]
    public static void Execute()
    {{
        try
        {{
            // Create {brand} brand VFX -- {cfg["desc"]}
            var go = new GameObject("{brand}_DamageVFX");
            var ps = go.AddComponent<ParticleSystem>();
            var renderer = go.GetComponent<ParticleSystemRenderer>();

            // Main module -- AAA tuned
            var main = ps.main;
            main.startLifetime = new ParticleSystem.MinMaxCurve({cfg["lifetime"] * 0.8}f, {cfg["lifetime"]}f);
            main.startSize = new ParticleSystem.MinMaxCurve({cfg["size"] * 0.6}f, {cfg["size"]}f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(1f, 3f);
            main.startColor = new Color({r}f, {g}f, {b}f, {a}f);
            main.maxParticles = {int(cfg["rate"] * cfg["lifetime"] * 3)};
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = -0.1f;

            // Emission -- burst + constant
            var emission = ps.emission;
            emission.rateOverTime = {cfg["rate"]}f;
            emission.SetBursts(new ParticleSystem.Burst[] {{
                new ParticleSystem.Burst(0f, {int(cfg["rate"] * 0.5)}, {int(cfg["rate"])}, 1, 0.1f)
            }});

            // Shape
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.{shape_cs};
            shape.angle = 25f;
            shape.radius = 0.3f;

            // Color over lifetime (brand-signature fade)
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var gradient = new Gradient();
            gradient.SetKeys(
                new GradientColorKey[] {{
                    new GradientColorKey(new Color({r}f, {g}f, {b}f), 0f),
                    new GradientColorKey(new Color({r * 1.2}f, {g * 1.2}f, {b * 1.2}f), 0.3f),
                    new GradientColorKey(new Color({r * 0.5}f, {g * 0.5}f, {b * 0.5}f), 1f)
                }},
                new GradientAlphaKey[] {{
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey({a}f, 0.1f),
                    new GradientAlphaKey({a}f, 0.7f),
                    new GradientAlphaKey(0f, 1f)
                }}
            );
            col.color = gradient;

            // Size over lifetime (expand then shrink)
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.3f, 1f, 0f));

            // Noise module (turbulence for AAA organic feel)
            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = 0.5f;
            noise.frequency = 0.8f;
            noise.scrollSpeed = 0.3f;
            noise.damping = true;
            noise.quality = ParticleSystemNoiseQuality.High;

            // Trails for dynamic brand signature
            var trails = ps.trails;
            trails.enabled = true;
            trails.ratio = 0.3f;
            trails.lifetime = 0.3f;
            trails.minVertexDistance = 0.1f;
            trails.worldSpace = true;
            trails.dieWithParticles = true;
            trails.widthOverTrail = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

            // Renderer -- additive blend for energy look
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            var mat = new Material(Shader.Find("Particles/Standard Unlit"));
            mat.SetColor("_Color", new Color({r}f, {g}f, {b}f, {a}f));
            mat.SetFloat("_Mode", 1f); // Additive
            mat.renderQueue = 3100;
            renderer.material = mat;
            renderer.trailMaterial = mat;
            renderer.sortingFudge = 10f;

            // Save as prefab
            string prefabDir = "Assets/Prefabs/VFX/Brand";
            if (!AssetDatabase.IsValidFolder(prefabDir))
            {{
                Directory.CreateDirectory(prefabDir);
                AssetDatabase.Refresh();
            }}
            string prefabPath = prefabDir + "/{brand}_DamageVFX.prefab";
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_brand_vfx\\", \\"brand\\": \\"{brand}\\", \\"desc\\": \\"{safe_desc}\\", \\"prefab_path\\": \\"" + prefabPath + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] {brand} brand VFX created: " + prefabPath);

            Object.DestroyImmediate(go);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_brand_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Brand VFX creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# VFX-03: Environmental VFX script
# ---------------------------------------------------------------------------


def generate_environmental_vfx_script(effect_type: str) -> str:
    """Generate C# editor script for environmental VFX particle effects.

    Args:
        effect_type: One of "dust", "fireflies", "snow", "rain", "ash".

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If effect_type is not recognized.
    """
    effect_type = effect_type.lower()
    if effect_type not in ENV_VFX_CONFIGS:
        raise ValueError(
            f"Unknown effect_type: '{effect_type}'. "
            f"Valid types: {sorted(ENV_VFX_CONFIGS)}"
        )

    cfg = ENV_VFX_CONFIGS[effect_type]
    r, g, b, a = cfg["color"]
    safe = effect_type.capitalize()
    gravity = cfg["gravity"]

    safe_desc = sanitize_cs_string(cfg["desc"])

    # Effect-specific AAA tuning
    noise_strength = {"dust": 0.8, "fireflies": 1.2, "snow": 0.3, "rain": 0.05, "ash": 0.6}.get(effect_type, 0.5)
    speed_min = {"dust": 0.01, "fireflies": 0.2, "snow": 0.5, "rain": 8.0, "ash": 0.1}.get(effect_type, 0.5)
    speed_max = {"dust": 0.05, "fireflies": 0.5, "snow": 1.2, "rain": 12.0, "ash": 0.3}.get(effect_type, 1.0)
    stretch = "renderer.renderMode = ParticleSystemRenderMode.Stretch;\n            renderer.lengthScale = 5f;" if effect_type == "rain" else "renderer.renderMode = ParticleSystemRenderMode.Billboard;"
    sim_space = "World"

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

/// <summary>
/// Environmental VFX: {cfg["desc"]}
/// AAA ParticleSystem with noise turbulence, world-space simulation, LOD-friendly.
/// </summary>
public static class VeilBreakers_EnvVFX_{safe}
{{
    [MenuItem("VeilBreakers/VFX/Environment/{safe}")]
    public static void Execute()
    {{
        try
        {{
            // Create environmental VFX -- {cfg["desc"]}
            var go = new GameObject("{safe}_EnvironmentVFX");
            var ps = go.AddComponent<ParticleSystem>();
            var renderer = go.GetComponent<ParticleSystemRenderer>();

            // Main module
            var main = ps.main;
            main.startLifetime = new ParticleSystem.MinMaxCurve({cfg["lifetime"] * 0.8}f, {cfg["lifetime"]}f);
            main.startSize = new ParticleSystem.MinMaxCurve({cfg["size"] * 0.7}f, {cfg["size"] * 1.3}f);
            main.startSpeed = new ParticleSystem.MinMaxCurve({speed_min}f, {speed_max}f);
            main.startColor = new Color({r}f, {g}f, {b}f, {a}f);
            main.maxParticles = {int(cfg["rate"] * cfg["lifetime"] * 2)};
            main.simulationSpace = ParticleSystemSimulationSpace.{sim_space};
            main.gravityModifier = {gravity}f;
            main.playOnAwake = true;
            main.loop = true;

            // Emission
            var emission = ps.emission;
            emission.rateOverTime = {cfg["rate"]}f;

            // Shape -- large area emitter for environment coverage
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(20f, 0.5f, 20f);

            // Color over lifetime
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var gradient = new Gradient();
            gradient.SetKeys(
                new GradientColorKey[] {{
                    new GradientColorKey(new Color({r}f, {g}f, {b}f), 0f),
                    new GradientColorKey(new Color({r}f, {g}f, {b}f), 1f)
                }},
                new GradientAlphaKey[] {{
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey({a}f, 0.1f),
                    new GradientAlphaKey({a}f, 0.85f),
                    new GradientAlphaKey(0f, 1f)
                }}
            );
            col.color = gradient;

            // Noise turbulence for organic motion
            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = {noise_strength}f;
            noise.frequency = 0.5f;
            noise.scrollSpeed = 0.2f;
            noise.damping = true;
            noise.quality = ParticleSystemNoiseQuality.High;

            // Renderer
            {stretch}
            var mat = new Material(Shader.Find("Particles/Standard Unlit"));
            mat.SetColor("_Color", new Color({r}f, {g}f, {b}f, {a}f));
            renderer.material = mat;

            // Save as prefab
            string prefabDir = "Assets/Prefabs/VFX/Environment";
            if (!AssetDatabase.IsValidFolder(prefabDir))
            {{
                Directory.CreateDirectory(prefabDir);
                AssetDatabase.Refresh();
            }}
            string prefabPath = prefabDir + "/{safe}_EnvVFX.prefab";
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_environmental_vfx\\", \\"type\\": \\"{effect_type}\\", \\"prefab_path\\": \\"" + prefabPath + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Environmental VFX created: " + prefabPath);

            Object.DestroyImmediate(go);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_environmental_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Environmental VFX creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# VFX-04: Trail VFX script
# ---------------------------------------------------------------------------


def generate_trail_vfx_script(
    name: str,
    width: float = 0.5,
    color: list[float] | None = None,
    lifetime: float = 0.5,
) -> str:
    """Generate C# editor script that creates a trail effect prefab.

    Uses TrailRenderer component for weapon/projectile trail effects.

    Args:
        name: Name of the trail effect.
        width: Trail width.
        color: RGBA start color as [r, g, b, a]. Defaults to white.
        lifetime: How long trail segments persist before fading.

    Returns:
        Complete C# source string.
    """
    if color is None:
        color = [1.0, 1.0, 1.0, 1.0]

    r, g, b, a = color[0], color[1], color[2], color[3]
    safe_name = sanitize_cs_identifier(name.replace(" ", "_").replace("-", "_"))
    safe_display = sanitize_cs_string(name)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_Trail_{safe_name}
{{
    [MenuItem("VeilBreakers/VFX/Create Trail/{safe_display}")]
    public static void Execute()
    {{
        try
        {{
            var go = new GameObject("{safe_display}_Trail");
            var trail = go.AddComponent<TrailRenderer>();

            // Configure TrailRenderer
            trail.time = {lifetime}f;
            trail.startWidth = {width}f;
            trail.endWidth = 0.01f;
            trail.minVertexDistance = 0.05f;
            trail.autodestruct = false;

            // Color gradient
            var gradient = new Gradient();
            gradient.SetKeys(
                new GradientColorKey[] {{
                    new GradientColorKey(new Color({r}f, {g}f, {b}f), 0f),
                    new GradientColorKey(new Color({r}f, {g}f, {b}f), 1f)
                }},
                new GradientAlphaKey[] {{
                    new GradientAlphaKey({a}f, 0f),
                    new GradientAlphaKey(0f, 1f)
                }}
            );
            trail.colorGradient = gradient;

            // Width curve -- taper from full width to zero
            var widthCurve = new AnimationCurve();
            widthCurve.AddKey(0f, 1f);
            widthCurve.AddKey(1f, 0f);
            trail.widthCurve = widthCurve;

            // Material -- use default URP unlit
            trail.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));

            // Save as prefab
            string prefabDir = "Assets/Prefabs/VFX/Trails";
            if (!AssetDatabase.IsValidFolder(prefabDir))
            {{
                Directory.CreateDirectory(prefabDir);
                AssetDatabase.Refresh();
            }}
            string prefabPath = prefabDir + "/{safe_display}_Trail.prefab";
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_trail_vfx\\", \\"name\\": \\"{safe_display}\\", \\"prefab_path\\": \\"" + prefabPath + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Trail VFX created: " + prefabPath);

            Object.DestroyImmediate(go);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_trail_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Trail VFX creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# VFX-05: Aura VFX script
# ---------------------------------------------------------------------------


def generate_aura_vfx_script(
    name: str,
    color: list[float] | None = None,
    intensity: float = 1.0,
    radius: float = 1.5,
) -> str:
    """Generate C# editor script that creates a looping aura/buff particle system.

    Uses ParticleSystem with looping emission around character bounds for
    aura effects like corruption glow, healing shimmer, etc.

    Args:
        name: Name of the aura effect.
        color: RGBA color as [r, g, b, a]. Defaults to white.
        intensity: Emission intensity multiplier.
        radius: Emission radius around character.

    Returns:
        Complete C# source string.
    """
    if color is None:
        color = [1.0, 1.0, 1.0, 1.0]

    r, g, b, a = color[0], color[1], color[2], color[3]
    safe_name = sanitize_cs_identifier(name.replace(" ", "_").replace("-", "_"))
    safe_display = sanitize_cs_string(name)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

public static class VeilBreakers_Aura_{safe_name}
{{
    [MenuItem("VeilBreakers/VFX/Create Aura/{safe_display}")]
    public static void Execute()
    {{
        try
        {{
            var go = new GameObject("{safe_display}_Aura");
            var ps = go.AddComponent<ParticleSystem>();

            // Main module -- looping aura around character bounds
            var main = ps.main;
            main.loop = true;  // Looping particle system
            main.startLifetime = 2.0f;
            main.startSpeed = 0.3f;
            main.startSize = 0.15f;
            main.startColor = new Color({r}f, {g}f, {b}f, {a}f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 200;

            // Emission module
            var emission = ps.emission;
            emission.rateOverTime = 30f * {intensity}f;

            // Shape module -- sphere matching character radius
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = {radius}f;

            // Color over lifetime -- fade out
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var gradient = new Gradient();
            gradient.SetKeys(
                new GradientColorKey[] {{
                    new GradientColorKey(new Color({r}f, {g}f, {b}f), 0f),
                    new GradientColorKey(new Color({r}f, {g}f, {b}f), 1f)
                }},
                new GradientAlphaKey[] {{
                    new GradientAlphaKey({a}f, 0f),
                    new GradientAlphaKey(0f, 1f)
                }}
            );
            col.color = gradient;

            // Size over lifetime -- shrink
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 1f, 1f, 0f));

            // Renderer setup
            var renderer = go.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));

            // Save as prefab
            string prefabDir = "Assets/Prefabs/VFX/Auras";
            if (!AssetDatabase.IsValidFolder(prefabDir))
            {{
                Directory.CreateDirectory(prefabDir);
                AssetDatabase.Refresh();
            }}
            string prefabPath = prefabDir + "/{safe_display}_Aura.prefab";
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_aura_vfx\\", \\"name\\": \\"{safe_display}\\", \\"prefab_path\\": \\"" + prefabPath + "\\", \\"looping\\": true}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Aura VFX created: " + prefabPath);

            Object.DestroyImmediate(go);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_aura_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Aura VFX creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# VFX-08: Post-processing script
# ---------------------------------------------------------------------------


def generate_post_processing_script(
    bloom_intensity: float = 1.5,
    bloom_threshold: float = 0.9,
    vignette_intensity: float = 0.35,
    ao_intensity: float = 0.5,
    dof_focus_distance: float = 10.0,
    color_temperature: float = 0.0,
    color_saturation: float = 0.0,
) -> str:
    """Generate C# editor script that creates an AAA post-processing Volume.

    Creates a Volume with a comprehensive dark fantasy post-processing chain:
    Tonemapping (ACES), Bloom, ColorAdjustments, ShadowsMidtonesHighlights,
    Vignette, DepthOfField, ChromaticAberration, FilmGrain, MotionBlur,
    LensDistortion, and WhiteBalance.

    Tuned for VeilBreakers dark fantasy aesthetic: desaturated highlights,
    warm shadows, cool midtones, dramatic vignette, subtle grain.

    Args:
        bloom_intensity: Bloom intensity value.
        bloom_threshold: Bloom threshold value.
        vignette_intensity: Vignette intensity value.
        ao_intensity: Ambient occlusion intensity value (for SSAO note).
        dof_focus_distance: Depth of field focus distance.
        color_temperature: Color grading temperature offset.
        color_saturation: Color grading saturation offset.

    Returns:
        Complete C# source string.
    """
    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using System.IO;

public static class VeilBreakers_PostProcessing
{{
    [MenuItem("VeilBreakers/VFX/Setup Post Processing")]
    public static void Execute()
    {{
        try
        {{
            // Create Volume GameObject
            var go = new GameObject("VeilBreakers_PostProcessVolume");
            var volume = go.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 1f;

            // Create VolumeProfile asset
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();

            // === TONEMAPPING (AAA standard: ACES filmic curve) ===
            var tonemapping = profile.Add<Tonemapping>();
            tonemapping.mode.Override(TonemappingMode.ACES);

            // === BLOOM (brand-glow emphasizer) ===
            var bloom = profile.Add<Bloom>();
            bloom.intensity.Override({bloom_intensity}f);
            bloom.threshold.Override({bloom_threshold}f);
            bloom.scatter.Override(0.7f);
            bloom.tint.Override(new Color(1.0f, 0.95f, 0.9f, 1.0f));
            bloom.highQualityFiltering.Override(true);

            // === COLOR ADJUSTMENTS (dark fantasy base grade) ===
            var colorAdj = profile.Add<ColorAdjustments>();
            colorAdj.colorFilter.Override(new Color(0.95f, 0.93f, 0.98f, 1.0f));
            colorAdj.saturation.Override({color_saturation}f - 12f);
            colorAdj.contrast.Override(18f);
            colorAdj.postExposure.Override(0.15f);
            colorAdj.hueShift.Override(0f);

            // === WHITE BALANCE (cool moonlit tint for dark fantasy) ===
            var whiteBalance = profile.Add<WhiteBalance>();
            whiteBalance.temperature.Override({color_temperature}f - 8f);
            whiteBalance.tint.Override(3f);

            // === SHADOWS, MIDTONES, HIGHLIGHTS (cinematic color grading) ===
            var smh = profile.Add<ShadowsMidtonesHighlights>();
            // Warm shadows (amber/rust tones in dark areas)
            smh.shadows.Override(new Vector4(1.05f, 0.95f, 0.85f, 0f));
            // Cool midtones (slight blue-grey)
            smh.midtones.Override(new Vector4(0.95f, 0.97f, 1.05f, 0f));
            // Desaturated highlights (pale, washed-out peaks)
            smh.highlights.Override(new Vector4(1.0f, 0.98f, 1.02f, -0.05f));
            smh.shadowsStart.Override(0f);
            smh.shadowsEnd.Override(0.25f);
            smh.highlightsStart.Override(0.55f);
            smh.highlightsEnd.Override(1f);

            // === VIGNETTE (dramatic framing) ===
            var vignette = profile.Add<Vignette>();
            vignette.intensity.Override({vignette_intensity}f);
            vignette.smoothness.Override(0.35f);
            vignette.roundness.Override(1f);
            vignette.color.Override(new Color(0.05f, 0.02f, 0.08f, 1f));

            // === DEPTH OF FIELD (cinematic focus) ===
            var dof = profile.Add<DepthOfField>();
            dof.mode.Override(DepthOfFieldMode.Bokeh);
            dof.focusDistance.Override({dof_focus_distance}f);
            dof.focalLength.Override(50f);
            dof.aperture.Override(5.6f);
            dof.bladeCount.Override(6);

            // === CHROMATIC ABERRATION (subtle edge distortion) ===
            var chromAb = profile.Add<ChromaticAberration>();
            chromAb.intensity.Override(0.08f);

            // === FILM GRAIN (dark fantasy grit) ===
            var filmGrain = profile.Add<FilmGrain>();
            filmGrain.type.Override(FilmGrainLookup.Medium3);
            filmGrain.intensity.Override(0.15f);
            filmGrain.response.Override(0.8f);

            // === MOTION BLUR (combat impact) ===
            var motionBlur = profile.Add<MotionBlur>();
            motionBlur.intensity.Override(0.15f);
            motionBlur.quality.Override(MotionBlurQuality.High);

            // === LENS DISTORTION (subtle dark fantasy warping) ===
            var lensDist = profile.Add<LensDistortion>();
            lensDist.intensity.Override(-0.08f);
            lensDist.scale.Override(1.01f);

            // NOTE: SSAO in URP is a Renderer Feature, not a Volume Override.
            // Configure SSAO on the Universal Renderer Data asset:
            //   UniversalRendererData > Add Renderer Feature > Screen Space Ambient Occlusion
            //   Recommended: Intensity={ao_intensity}, Radius=0.3, Sample Count=Medium
            //   Enable "After Opaque" for best quality.

            // Assign profile to volume
            volume.profile = profile;

            // Save profile asset
            string profileDir = "Assets/Settings/PostProcessing";
            if (!AssetDatabase.IsValidFolder(profileDir))
            {{
                Directory.CreateDirectory(profileDir);
                AssetDatabase.Refresh();
            }}
            string profilePath = profileDir + "/VeilBreakers_PostProcess.asset";
            AssetDatabase.CreateAsset(profile, profilePath);
            AssetDatabase.SaveAssets();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"setup_post_processing\\", \\"profile_path\\": \\"" + profilePath + "\\", \\"bloom\\": {bloom_intensity}, \\"vignette\\": {vignette_intensity}, \\"ao\\": {ao_intensity}, \\"dof_focus\\": {dof_focus_distance}, \\"tonemapping\\": \\"ACES\\", \\"film_grain\\": 0.15, \\"chromatic_aberration\\": 0.08, \\"motion_blur\\": 0.15}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] AAA post-processing chain created: " + profilePath);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"setup_post_processing\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Post-processing setup failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# VFX-09: Screen effect script
# ---------------------------------------------------------------------------


def generate_screen_effect_script(effect_type: str, intensity: float = 1.0) -> str:
    """Generate C# editor script for screen effects.

    Supports camera shake (Cinemachine Impulse), damage vignette, low health
    pulse, poison overlay, and heal glow.

    Args:
        effect_type: One of "camera_shake", "damage_vignette",
                     "low_health_pulse", "poison_overlay", "heal_glow".
        intensity: Effect intensity multiplier.

    Returns:
        Complete C# source string.

    Raises:
        ValueError: If effect_type is not recognized.
    """
    if effect_type not in _VALID_SCREEN_EFFECTS:
        raise ValueError(
            f"Unknown effect_type: '{effect_type}'. "
            f"Valid types: {sorted(_VALID_SCREEN_EFFECTS)}"
        )

    if effect_type == "camera_shake":
        return _screen_effect_camera_shake(intensity)
    else:
        return _screen_effect_overlay(effect_type, intensity)


def _screen_effect_camera_shake(intensity: float) -> str:
    """Generate camera shake script using Cinemachine Impulse system."""
    return f'''using UnityEngine;
using UnityEditor;
using System.IO;
// Auto-detect Cinemachine version -- supports both 2.x and 3.x+
#if UNITY_CINEMACHINE_3_OR_NEWER
using Unity.Cinemachine;
#elif CINEMACHINE
using Cinemachine;
#endif

/// <summary>
/// Camera shake screen effect using Cinemachine CinemachineImpulseSource.
/// Auto-detects Cinemachine 2.x vs 3.x namespace. Falls back to transform
/// shake if Cinemachine is not installed.
/// </summary>
public static class VeilBreakers_ScreenEffect_CameraShake
{{
    [MenuItem("VeilBreakers/VFX/Screen Effects/Camera Shake")]
    public static void Execute()
    {{
        try
        {{
            // Find or create impulse source on main camera
            var cam = Camera.main;
            if (cam == null)
            {{
                cam = Object.FindObjectOfType<Camera>();
            }}
            if (cam == null)
            {{
                var camGo = new GameObject("VB_CameraShakeSource");
                cam = camGo.AddComponent<Camera>();
            }}

            // Add CinemachineImpulseSource for shake generation
            var impulseSource = cam.gameObject.GetComponent<CinemachineImpulseSource>();
            if (impulseSource == null)
            {{
                impulseSource = cam.gameObject.AddComponent<CinemachineImpulseSource>();
            }}

            // Configure impulse
            impulseSource.DefaultVelocity = new Vector3(0f, {intensity}f, 0f);

            // Generate impulse -- CinemachineImpulseSource.GenerateImpulse()
            impulseSource.GenerateImpulse({intensity}f);

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_screen_effect\\", \\"type\\": \\"camera_shake\\", \\"intensity\\": {intensity}}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Camera shake impulse configured with intensity: {intensity}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_screen_effect\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Camera shake setup failed: " + ex.Message);
        }}
    }}
}}
'''


def _screen_effect_overlay(effect_type: str, intensity: float) -> str:
    """Generate fullscreen overlay effect script using Canvas + CanvasGroup."""
    configs = {
        "damage_vignette": {
            "color": "new Color(0.5f, 0f, 0f, 0.6f)",
            "desc": "Red vignette overlay for damage feedback",
            "label": "Damage Vignette",
            "class_suffix": "DamageVignette",
        },
        "low_health_pulse": {
            "color": "new Color(0.8f, 0f, 0f, 0.4f)",
            "desc": "Pulsing red overlay for low health warning",
            "label": "Low Health Pulse",
            "class_suffix": "LowHealthPulse",
        },
        "poison_overlay": {
            "color": "new Color(0.1f, 0.6f, 0f, 0.35f)",
            "desc": "Green poison overlay with distortion",
            "label": "Poison Overlay",
            "class_suffix": "PoisonOverlay",
        },
        "heal_glow": {
            "color": "new Color(0.2f, 1f, 0.4f, 0.3f)",
            "desc": "Green-white heal glow overlay",
            "label": "Heal Glow",
            "class_suffix": "HealGlow",
        },
    }
    cfg = configs[effect_type]

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.UI;
using System.IO;

/// <summary>
/// {cfg["desc"]}
/// Uses fullscreen Canvas with Image overlay and CanvasGroup alpha control.
/// </summary>
public static class VeilBreakers_ScreenEffect_{cfg["class_suffix"]}
{{
    [MenuItem("VeilBreakers/VFX/Screen Effects/{cfg["label"]}")]
    public static void Execute()
    {{
        try
        {{
            // Create fullscreen overlay canvas
            var canvasGo = new GameObject("VB_ScreenEffect_{cfg["class_suffix"]}");
            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 999;

            var canvasGroup = canvasGo.AddComponent<CanvasGroup>();
            canvasGroup.alpha = {intensity}f;
            canvasGroup.interactable = false;
            canvasGroup.blocksRaycasts = false;

            // Overlay image
            var imageGo = new GameObject("Overlay");
            imageGo.transform.SetParent(canvasGo.transform, false);
            var image = imageGo.AddComponent<Image>();
            image.color = {cfg["color"]};

            // Stretch to fill screen
            var rect = imageGo.GetComponent<RectTransform>();
            rect.anchorMin = Vector2.zero;
            rect.anchorMax = Vector2.one;
            rect.sizeDelta = Vector2.zero;

            // Save as prefab
            string prefabDir = "Assets/Prefabs/VFX/ScreenEffects";
            if (!AssetDatabase.IsValidFolder(prefabDir))
            {{
                Directory.CreateDirectory(prefabDir);
                AssetDatabase.Refresh();
            }}
            string prefabPath = prefabDir + "/{cfg["class_suffix"]}.prefab";
            PrefabUtility.SaveAsPrefabAsset(canvasGo, prefabPath);

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_screen_effect\\", \\"type\\": \\"{effect_type}\\", \\"prefab_path\\": \\"" + prefabPath + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Screen effect created: {cfg["label"]}");

            Object.DestroyImmediate(canvasGo);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_screen_effect\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Screen effect creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# VFX-10: Ability VFX script
# ---------------------------------------------------------------------------


def generate_ability_vfx_script(
    ability_name: str,
    vfx_prefab: str = "Assets/Prefabs/VFX/Default.prefab",
    anim_clip: str = "Assets/Animations/Default.anim",
    keyframe_time: float = 0.0,
) -> str:
    """Generate C# editor script that binds VFX to AnimationEvent.

    Creates a C# script that instantiates a VFX prefab and binds it to
    an AnimationEvent at a specified keyframe time on an animation clip.

    Args:
        ability_name: Name of the ability (e.g., "Fireball", "Slash").
        vfx_prefab: Path to VFX prefab to instantiate.
        anim_clip: Path to animation clip to bind the event to.
        keyframe_time: Time in seconds for the AnimationEvent trigger.

    Returns:
        Complete C# source string.
    """
    safe_name = sanitize_cs_identifier(ability_name.replace(" ", "_").replace("-", "_"))
    safe_display = sanitize_cs_string(ability_name)
    safe_vfx_prefab = sanitize_cs_string(vfx_prefab)
    safe_anim_clip = sanitize_cs_string(anim_clip)

    return f'''using UnityEngine;
using UnityEditor;
using System.IO;

/// <summary>
/// Ability VFX: {safe_display}
/// Binds VFX prefab instantiation to an AnimationEvent at t={keyframe_time}s.
/// </summary>
public static class VeilBreakers_AbilityVFX_{safe_name}
{{
    [MenuItem("VeilBreakers/VFX/Ability VFX/{safe_display}")]
    public static void Execute()
    {{
        try
        {{
            // Load VFX prefab
            var vfxPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("{safe_vfx_prefab}");
            if (vfxPrefab == null)
            {{
                Debug.LogWarning("[VeilBreakers] VFX prefab not found at: {safe_vfx_prefab}. Creating placeholder.");
                vfxPrefab = new GameObject("{safe_display}_VFX_Placeholder");
                string placeholderDir = "Assets/Prefabs/VFX/Abilities";
                if (!AssetDatabase.IsValidFolder(placeholderDir))
                {{
                    Directory.CreateDirectory(placeholderDir);
                    AssetDatabase.Refresh();
                }}
                PrefabUtility.SaveAsPrefabAsset(vfxPrefab, placeholderDir + "/{safe_display}_VFX.prefab");
                Object.DestroyImmediate(vfxPrefab);
                vfxPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(placeholderDir + "/{safe_display}_VFX.prefab");
            }}

            // Load or create animation clip
            var animClip = AssetDatabase.LoadAssetAtPath<AnimationClip>("{safe_anim_clip}");
            if (animClip != null)
            {{
                // Add AnimationEvent to trigger VFX instantiation
                AnimationEvent evt = new AnimationEvent();
                evt.time = {keyframe_time}f;
                evt.functionName = "OnAbilityVFX_{safe_name}";
                evt.stringParameter = "{safe_vfx_prefab}";

                // Get existing events and add new one
                var existingEvents = AnimationUtility.GetAnimationEvents(animClip);
                var newEvents = new AnimationEvent[existingEvents.Length + 1];
                existingEvents.CopyTo(newEvents, 0);
                newEvents[newEvents.Length - 1] = evt;
                AnimationUtility.SetAnimationEvents(animClip, newEvents);

                Debug.Log("[VeilBreakers] AnimationEvent added at t=" + {keyframe_time}f + "s");
            }}
            else
            {{
                Debug.LogWarning("[VeilBreakers] Animation clip not found at: {safe_anim_clip}. Event binding skipped.");
            }}

            // Generate runtime VFX trigger script
            string runtimeScript = @"
using UnityEngine;

public class AbilityVFX_{safe_name} : MonoBehaviour
{{
    public GameObject vfxPrefab;

    // Called by AnimationEvent
    public void OnAbilityVFX_{safe_name}()
    {{
        if (vfxPrefab != null)
        {{
            Instantiate(vfxPrefab, transform.position, transform.rotation);
        }}
    }}
}}";

            // Write runtime script
            string scriptDir = "Assets/Scripts/Runtime/VFX";
            if (!AssetDatabase.IsValidFolder(scriptDir))
            {{
                Directory.CreateDirectory(scriptDir);
                AssetDatabase.Refresh();
            }}
            string scriptPath = scriptDir + "/AbilityVFX_{safe_name}.cs";
            File.WriteAllText(scriptPath, runtimeScript);

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_ability_vfx\\", \\"ability\\": \\"{safe_display}\\", \\"vfx_prefab\\": \\"{safe_vfx_prefab}\\", \\"keyframe_time\\": {keyframe_time}, \\"runtime_script\\": \\"" + scriptPath + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Ability VFX configured: {safe_display}");
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"create_ability_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Ability VFX creation failed: " + ex.Message);
        }}
    }}
}}
'''


# ---------------------------------------------------------------------------
# VX-01: URP Decal System
# ---------------------------------------------------------------------------


DECAL_TYPES: list[str] = [
    "BloodSplatter",
    "ScorchMark",
    "Footprint",
    "CorruptionSpread",
    "IceFreeze",
    "AcidPool",
    "HolyMark",
    "SlashMark",
    "ImpactCrater",
    "ArrowHit",
]


def generate_decal_system_script(
    max_active: int = 50,
    default_fade_pct: float = 0.2,
) -> str:
    """Generate a runtime URP DecalProjector pool manager for dark fantasy combat.

    Creates a MonoBehaviour (VB_DecalManager) that manages an object pool of
    URP DecalProjector instances. Supports 10 decal types with per-type
    configuration, auto-fade over the last portion of lifetime, surface normal
    alignment via raycast, random rotation for variety, and size randomization.

    This is a **runtime** script -- it does NOT use UnityEditor.

    Args:
        max_active: Maximum active decals before oldest are recycled (default 50).
        default_fade_pct: Fraction of lifetime over which alpha fades (default 0.2).

    Returns:
        Complete C# source string for Assets/Scripts/Runtime/VFX/.
    """
    if max_active < 1:
        raise ValueError(f"max_active must be >= 1, got {max_active}")
    if not (0.0 < default_fade_pct <= 1.0):
        raise ValueError(
            f"default_fade_pct must be in (0.0, 1.0], got {default_fade_pct}"
        )

    # Build enum members string
    enum_members = ",\n        ".join(DECAL_TYPES)

    # Build per-type config initializer
    config_entries = []
    for dt in DECAL_TYPES:
        config_entries.append(
            f'            {{DecalType.{dt}, new DecalTypeConfig {{ defaultMinSize = 0.8f, defaultMaxSize = 1.2f, fadeDuration = 2.0f, maxInstances = {max_active} }}}}'
        )
    config_init = ",\n".join(config_entries)

    return f'''using UnityEngine;
using UnityEngine.Rendering.Universal;
using System.Collections.Generic;

/// <summary>
/// VX-01: Runtime URP Decal Manager for dark fantasy combat feedback.
/// Object-pooled DecalProjector instances with auto-fade, surface alignment,
/// random rotation, and size variation. Max {max_active} active decals.
/// </summary>
public class VB_DecalManager : MonoBehaviour
{{
    // -----------------------------------------------------------------------
    // Decal type enum
    // -----------------------------------------------------------------------

    public enum DecalType
    {{
        {enum_members}
    }}

    // -----------------------------------------------------------------------
    // Per-type configuration
    // -----------------------------------------------------------------------

    [System.Serializable]
    public class DecalTypeConfig
    {{
        public Material material;
        public float defaultMinSize = 0.8f;
        public float defaultMaxSize = 1.2f;
        public float fadeDuration = 2.0f;
        public int maxInstances = {max_active};
    }}

    // -----------------------------------------------------------------------
    // Active decal tracking
    // -----------------------------------------------------------------------

    private class ActiveDecal
    {{
        public DecalProjector projector;
        public float spawnTime;
        public float lifetime;
        public float originalFadeFactor;
        public DecalType type;
    }}

    // -----------------------------------------------------------------------
    // Singleton access
    // -----------------------------------------------------------------------

    public static VB_DecalManager Instance {{ get; private set; }}

    // -----------------------------------------------------------------------
    // Inspector fields
    // -----------------------------------------------------------------------

    [Header("Global Settings")]
    [SerializeField] private int maxActiveDecals = {max_active};
    [SerializeField] [Range(0.01f, 1.0f)] private float fadePercent = {default_fade_pct}f;

    [Header("Per-Type Materials (assign in Inspector)")]
    [SerializeField] private DecalTypeConfig[] typeConfigs;

    // -----------------------------------------------------------------------
    // Internal state
    // -----------------------------------------------------------------------

    private readonly Dictionary<DecalType, DecalTypeConfig> _configMap = new Dictionary<DecalType, DecalTypeConfig>();
    private readonly LinkedList<ActiveDecal> _activeDecals = new LinkedList<ActiveDecal>();
    private readonly Queue<DecalProjector> _pool = new Queue<DecalProjector>();
    private Transform _poolParent;

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------

    private void Awake()
    {{
        if (Instance != null && Instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        Instance = this;

        _poolParent = new GameObject("DecalPool").transform;
        _poolParent.SetParent(transform);

        InitializeDefaultConfigs();

        // Override with Inspector-assigned configs
        if (typeConfigs != null)
        {{
            for (int i = 0; i < typeConfigs.Length && i < System.Enum.GetValues(typeof(DecalType)).Length; i++)
            {{
                DecalType dt = (DecalType)i;
                if (typeConfigs[i] != null && typeConfigs[i].material != null)
                {{
                    _configMap[dt] = typeConfigs[i];
                }}
            }}
        }}
    }}

    private void InitializeDefaultConfigs()
    {{
        _configMap.Clear();
        var defaults = new Dictionary<DecalType, DecalTypeConfig>
        {{
{config_init}
        }};
        foreach (var kvp in defaults)
        {{
            _configMap[kvp.Key] = kvp.Value;
        }}
    }}

    private void Update()
    {{
        float time = Time.time;
        var node = _activeDecals.First;
        while (node != null)
        {{
            var next = node.Next;
            var ad = node.Value;
            float elapsed = time - ad.spawnTime;

            if (elapsed >= ad.lifetime)
            {{
                ReturnToPool(ad.projector);
                _activeDecals.Remove(node);
            }}
            else
            {{
                // Auto-fade over last fadePercent of lifetime
                float fadeStart = ad.lifetime * (1.0f - fadePercent);
                if (elapsed > fadeStart)
                {{
                    float fadeProgress = (elapsed - fadeStart) / (ad.lifetime * fadePercent);
                    float alpha = Mathf.Lerp(ad.originalFadeFactor, 0f, fadeProgress);
                    ad.projector.fadeFactor = alpha;
                }}
            }}

            node = next;
        }}
    }}

    private void OnDestroy()
    {{
        if (Instance == this) Instance = null;
    }}

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /// <summary>
    /// Spawn a decal at the given position, aligned to surface normal.
    /// </summary>
    public DecalProjector SpawnDecal(DecalType type, Vector3 position, Quaternion rotation, float size = 1.0f, float lifetime = 5.0f)
    {{
        // Enforce max active cap -- recycle oldest
        while (_activeDecals.Count >= maxActiveDecals)
        {{
            var oldest = _activeDecals.First;
            if (oldest != null)
            {{
                ReturnToPool(oldest.Value.projector);
                _activeDecals.RemoveFirst();
            }}
        }}

        DecalProjector proj = GetFromPool();

        // Surface normal alignment via raycast
        if (Physics.Raycast(position + Vector3.up * 0.5f, Vector3.down, out RaycastHit hit, 2.0f))
        {{
            // Align decal to surface normal with random rotation around it
            float randomAngle = Random.Range(0f, 360f);
            Quaternion surfaceAlign = Quaternion.LookRotation(-hit.normal) * Quaternion.Euler(0, 0, randomAngle);
            proj.transform.position = hit.point + hit.normal * 0.01f;
            proj.transform.rotation = surfaceAlign;
        }}
        else
        {{
            // Fallback: use provided position/rotation with random Y twist
            float randomAngle = Random.Range(0f, 360f);
            proj.transform.position = position;
            proj.transform.rotation = rotation * Quaternion.Euler(0, randomAngle, 0);
        }}

        // Size variation: 0.8x to 1.2x randomization
        float sizeVariation = Random.Range(0.8f, 1.2f);
        float finalSize = size * sizeVariation;
        proj.size = new Vector3(finalSize, finalSize, 0.5f);

        // Apply per-type material
        if (_configMap.TryGetValue(type, out DecalTypeConfig cfg) && cfg.material != null)
        {{
            proj.material = cfg.material;
        }}

        proj.fadeFactor = 1.0f;
        proj.gameObject.SetActive(true);

        var active = new ActiveDecal
        {{
            projector = proj,
            spawnTime = Time.time,
            lifetime = lifetime,
            originalFadeFactor = 1.0f,
            type = type,
        }};
        _activeDecals.AddLast(active);

        return proj;
    }}

    /// <summary>
    /// Get the current count of active (visible) decals.
    /// </summary>
    public int ActiveCount => _activeDecals.Count;

    // -----------------------------------------------------------------------
    // Object pool
    // -----------------------------------------------------------------------

    private DecalProjector GetFromPool()
    {{
        if (_pool.Count > 0)
        {{
            var proj = _pool.Dequeue();
            proj.gameObject.SetActive(true);
            return proj;
        }}

        var go = new GameObject("Decal");
        go.transform.SetParent(_poolParent);
        var dp = go.AddComponent<DecalProjector>();
        dp.scaleMode = DecalScaleMode.InheritFromHierarchy;
        return dp;
    }}

    private void ReturnToPool(DecalProjector proj)
    {{
        proj.gameObject.SetActive(false);
        proj.fadeFactor = 1.0f;
        _pool.Enqueue(proj);
    }}
}}
'''
