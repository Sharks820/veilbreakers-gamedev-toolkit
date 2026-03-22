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
"""

from __future__ import annotations

import re


def _sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal."""
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


def _sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "", value)


# ---------------------------------------------------------------------------
# Brand VFX config dictionaries
# ---------------------------------------------------------------------------

BRAND_PRIMARY_COLORS: dict[str, list[float]] = {"IRON":[0.55,0.59,0.65,1.0],"SAVAGE":[0.71,0.18,0.18,1.0],"SURGE":[0.24,0.55,0.86,1.0],"VENOM":[0.31,0.71,0.24,1.0],"DREAD":[0.47,0.24,0.63,1.0],"LEECH":[0.55,0.16,0.31,1.0],"GRACE":[0.86,0.86,0.94,1.0],"MEND":[0.78,0.67,0.31,1.0],"RUIN":[0.86,0.47,0.16,1.0],"VOID":[0.16,0.08,0.24,1.0]}
BRAND_GLOW_COLORS: dict[str, list[float]] = {"IRON":[0.71,0.75,0.80,1.0],"SAVAGE":[0.86,0.27,0.27,1.0],"SURGE":[0.39,0.71,1.00,1.0],"VENOM":[0.47,0.86,0.39,1.0],"DREAD":[0.63,0.39,0.78,1.0],"LEECH":[0.71,0.24,0.43,1.0],"GRACE":[1.00,1.00,1.00,1.0],"MEND":[0.94,0.82,0.47,1.0],"RUIN":[1.00,0.63,0.31,1.0],"VOID":[0.39,0.24,0.55,1.0]}
BRAND_DARK_COLORS: dict[str, list[float]] = {"IRON":[0.31,0.35,0.39,1.0],"SAVAGE":[0.47,0.10,0.10,1.0],"SURGE":[0.12,0.31,0.55,1.0],"VENOM":[0.16,0.39,0.12,1.0],"DREAD":[0.27,0.12,0.39,1.0],"LEECH":[0.35,0.08,0.20,1.0],"GRACE":[0.63,0.63,0.71,1.0],"MEND":[0.55,0.43,0.16,1.0],"RUIN":[0.63,0.27,0.08,1.0],"VOID":[0.06,0.02,0.10,1.0]}

BRAND_VFX_CONFIGS: dict[str, dict] = {
    "IRON": {
        "rate": 200,
        "lifetime": 0.5,
        "size": 0.1,
        "color": [0.55, 0.59, 0.65, 1.0],
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
        "color": [0.47, 0.24, 0.63, 1.0],
        "shape": "sphere",
        "desc": "shadow wisps",
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
        "color": [0.55, 0.16, 0.31, 1.0],
        "shape": "sphere",
        "desc": "dark drain tendrils",
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
    safe_name = _sanitize_cs_identifier(name.replace(" ", "_").replace("-", "_"))
    safe_display = _sanitize_cs_string(name)

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.VFX;
using System.IO;

public static class VeilBreakers_VFX_{safe_name}
{{
    [MenuItem("VeilBreakers/VFX/Create Particle VFX/{safe_display}")]
    public static void Execute()
    {{
        try
        {{
            // Create VFX GameObject
            var go = new GameObject("{safe_display}_VFX");
            var vfx = go.AddComponent<VisualEffect>();

            // Configure exposed properties via VFX Graph API
            vfx.SetFloat("Rate", {rate}f);
            vfx.SetFloat("Lifetime", {lifetime}f);
            vfx.SetFloat("Size", {size}f);
            vfx.SetVector4("Color", new Vector4({r}f, {g}f, {b}f, {a}f));

            // Shape configuration: {shape}
            vfx.SetFloat("ShapeIndex", {_shape_index(shape)}f);  // 0=Sphere, 1=Cone, 2=Edge, 3=Box

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

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.VFX;
using System.IO;

/// <summary>
/// {brand} brand damage VFX: {cfg["desc"]}
/// Rate={cfg["rate"]}, Lifetime={cfg["lifetime"]}, Size={cfg["size"]}, Shape={cfg["shape"]}
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
            var vfx = go.AddComponent<VisualEffect>();

            // Brand-specific parameters
            vfx.SetFloat("Rate", {cfg["rate"]}f);
            vfx.SetFloat("Lifetime", {cfg["lifetime"]}f);
            vfx.SetFloat("Size", {cfg["size"]}f);
            vfx.SetVector4("Color", new Vector4({r}f, {g}f, {b}f, {a}f));
            vfx.SetFloat("ShapeIndex", {_shape_index(cfg["shape"])}f);

            // Save as prefab
            string prefabDir = "Assets/Prefabs/VFX/Brand";
            if (!AssetDatabase.IsValidFolder(prefabDir))
            {{
                Directory.CreateDirectory(prefabDir);
                AssetDatabase.Refresh();
            }}
            string prefabPath = prefabDir + "/{brand}_DamageVFX.prefab";
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

            // Write result
            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"create_brand_vfx\\", \\"brand\\": \\"{brand}\\", \\"desc\\": \\"{cfg["desc"]}\\", \\"prefab_path\\": \\"" + prefabPath + "\\"}}";
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

    return f'''using UnityEngine;
using UnityEditor;
using UnityEngine.VFX;
using System.IO;

/// <summary>
/// Environmental VFX: {cfg["desc"]}
/// Gravity={gravity}, Rate={cfg["rate"]}, Lifetime={cfg["lifetime"]}
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
            var vfx = go.AddComponent<VisualEffect>();

            // Configure environment-specific parameters
            vfx.SetFloat("Rate", {cfg["rate"]}f);
            vfx.SetFloat("Lifetime", {cfg["lifetime"]}f);
            vfx.SetFloat("Size", {cfg["size"]}f);
            vfx.SetVector4("Color", new Vector4({r}f, {g}f, {b}f, {a}f));

            // Gravity / downward velocity for {effect_type}
            vfx.SetFloat("Gravity", {gravity}f);
            vfx.SetVector3("GravityDirection", new Vector3(0f, {gravity}f, 0f));
            // Y-axis gravity ensures downward motion for snow/rain/ash

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
    safe_name = _sanitize_cs_identifier(name.replace(" ", "_").replace("-", "_"))
    safe_display = _sanitize_cs_string(name)

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
    safe_name = _sanitize_cs_identifier(name.replace(" ", "_").replace("-", "_"))
    safe_display = _sanitize_cs_string(name)

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
    """Generate C# editor script that creates a post-processing Volume.

    Creates a Volume GameObject with VolumeProfile containing Bloom,
    ColorAdjustments, Vignette, ScreenSpaceAmbientOcclusion, and
    DepthOfField overrides.

    Args:
        bloom_intensity: Bloom intensity value.
        bloom_threshold: Bloom threshold value.
        vignette_intensity: Vignette intensity value.
        ao_intensity: Ambient occlusion intensity value.
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

            // Bloom
            var bloom = profile.Add<Bloom>();
            bloom.intensity.Override({bloom_intensity}f);
            bloom.threshold.Override({bloom_threshold}f);
            bloom.scatter.Override(0.7f);

            // ColorAdjustments (color grading)
            var colorAdj = profile.Add<ColorAdjustments>();
            colorAdj.colorFilter.Override(Color.white);
            colorAdj.saturation.Override({color_saturation}f);
            colorAdj.postExposure.Override(0f);

            // Vignette
            var vignette = profile.Add<Vignette>();
            vignette.intensity.Override({vignette_intensity}f);
            vignette.smoothness.Override(0.3f);

            // NOTE: SSAO in URP is a Renderer Feature, not a Volume Override.
            // Configure SSAO on the Universal Renderer Data asset instead:
            //   UniversalRendererData > Add Renderer Feature > Screen Space Ambient Occlusion
            //   Set intensity to {ao_intensity}

            // DepthOfField
            var dof = profile.Add<DepthOfField>();
            dof.mode.Override(DepthOfFieldMode.Bokeh);
            dof.focusDistance.Override({dof_focus_distance}f);
            dof.focalLength.Override(50f);
            dof.aperture.Override(5.6f);

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

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"setup_post_processing\\", \\"profile_path\\": \\"" + profilePath + "\\", \\"bloom\\": {bloom_intensity}, \\"vignette\\": {vignette_intensity}, \\"ao\\": {ao_intensity}, \\"dof_focus\\": {dof_focus_distance}}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Post-processing volume created with profile: " + profilePath);
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
#if CINEMACHINE_AVAILABLE
using Unity.Cinemachine;
#endif

/// <summary>
/// Camera shake screen effect using Cinemachine CinemachineImpulseSource.
/// Generates a one-shot impulse with configurable intensity.
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
    safe_name = _sanitize_cs_identifier(ability_name.replace(" ", "_").replace("-", "_"))
    safe_display = _sanitize_cs_string(ability_name)
    safe_vfx_prefab = _sanitize_cs_string(vfx_prefab)
    safe_anim_clip = _sanitize_cs_string(anim_clip)

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
