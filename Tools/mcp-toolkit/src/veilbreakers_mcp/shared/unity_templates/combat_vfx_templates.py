"""Combat VFX C# template generators -- combo chains, channel/sustain effects.

Phase 5: P5-Q3, P5-Q4

Exports:
    generate_combo_vfx_script      -- P5-Q3: Multi-hit combo VFX chains with brand finishers
    generate_channel_vfx_script    -- P5-Q4: Channel/sustain VFX (channel + aura + beam)
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

# Import canonical brand palette from vfx_templates
from .vfx_templates import BRAND_PRIMARY_COLORS, BRAND_GLOW_COLORS, BRAND_DARK_COLORS

ALL_BRANDS = list(BRAND_PRIMARY_COLORS.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_brand_color(brand: str) -> tuple[float, float, float, float]:
    """Return the primary RGBA for a brand, with IRON fallback.

    Args:
        brand: Brand name (IRON, SAVAGE, SURGE, etc.).

    Returns:
        Tuple of (r, g, b, a) floats.
    """
    key = brand.upper()
    rgba = BRAND_PRIMARY_COLORS.get(key, BRAND_PRIMARY_COLORS["IRON"])
    return (rgba[0], rgba[1], rgba[2], rgba[3])


def _get_glow_color(brand: str) -> tuple[float, float, float, float]:
    """Return the glow RGBA for a brand, with IRON fallback."""
    key = brand.upper()
    rgba = BRAND_GLOW_COLORS.get(key, BRAND_GLOW_COLORS["IRON"])
    return (rgba[0], rgba[1], rgba[2], rgba[3])


def _get_dark_color(brand: str) -> tuple[float, float, float, float]:
    """Return the dark RGBA for a brand, with IRON fallback."""
    key = brand.upper()
    rgba = BRAND_DARK_COLORS.get(key, BRAND_DARK_COLORS["IRON"])
    return (rgba[0], rgba[1], rgba[2], rgba[3])


def _fmt_color(rgba: tuple[float, float, float, float]) -> str:
    """Format RGBA tuple as C# ``new Color(r, g, b, a)``."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _brand_colors_cs_dict(color_map: dict[str, list[float]], var_name: str) -> str:
    """Build a C# Dictionary<string, Color> initializer for all brands."""
    lines = [f"        private static readonly Dictionary<string, Color> {var_name} = new Dictionary<string, Color>"]
    lines.append("        {")
    for brand, rgba in color_map.items():
        lines.append(f'            {{ "{brand}", new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f) }},')
    lines.append("        };")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# P5-Q3: Multi-Hit Combo VFX Chains
# ---------------------------------------------------------------------------


def generate_combo_vfx_script(brand: str = "IRON") -> dict[str, Any]:
    """Generate ComboVFXController MonoBehaviour with brand-specific combo VFX.

    Tracks combo count, escalates VFX intensity per hit, and triggers
    brand-specific finisher explosions at combo count 5+.

    Args:
        brand: Combat brand (IRON, SAVAGE, SURGE, etc.). Defaults to IRON.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    brand = brand.upper()
    if brand not in BRAND_PRIMARY_COLORS:
        brand = "IRON"

    safe_brand = sanitize_cs_identifier(brand)
    pr = _get_brand_color(brand)
    gl = _get_glow_color(brand)
    dk = _get_dark_color(brand)

    # Build per-brand finisher particle config blocks -- each brand is
    # visually distinct with unique shapes, sizes, speeds, and sub-emitters.
    finisher_blocks = _build_all_finisher_blocks()

    primary_dict = _brand_colors_cs_dict(BRAND_PRIMARY_COLORS, "BrandPrimary")
    glow_dict = _brand_colors_cs_dict(BRAND_GLOW_COLORS, "BrandGlow")

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Multi-hit combo VFX controller for the {brand} brand.
/// Tracks combo count with timeout, escalates VFX per hit tier,
/// and triggers brand-specific finisher explosions at combo 5+.
/// Phase 5 -- P5-Q3
/// </summary>
public class VB_ComboVFX_{safe_brand} : MonoBehaviour
{{
    [Header("Combo Settings")]
    [SerializeField] private float comboTimeout = 2.0f;
    [SerializeField] private int finisherThreshold = 5;
    [SerializeField] private string currentBrand = "{brand}";

    [Header("VFX Scaling")]
    [SerializeField] private float baseParticleCount = 50f;
    [SerializeField] private float baseLifetime = 0.3f;
    [SerializeField] private float baseSize = 0.15f;
    [SerializeField] private float escalationMultiplier = 1.5f;

    [Header("Screen Effects")]
    [SerializeField] private float shakeAmplitude = 0.3f;
    [SerializeField] private float chromaticAberrationPeak = 0.6f;
    [SerializeField] private float chromaticDuration = 0.25f;

    [Header("Timing Data")]
    [Tooltip("Single VFX trigger frame (fallback)")]
    [SerializeField] private int vfxFrame = 5;
    [Tooltip("Multi-hit VFX trigger frames")]
    [SerializeField] private int[] vfxFrames;

    // Events
    public event Action<int> OnComboHit;
    public event Action<string> OnComboFinisher;

    // State
    private int comboCount;
    private float lastHitTime;
    private bool isInCombo;
    private Coroutine comboTimeoutCoroutine;

    // Runtime VFX references
    private ParticleSystem hitBurstPS;
    private ParticleSystem finisherPS;
    private ParticleSystem finisherSubPS;

    // Post-processing
    private UnityEngine.Rendering.Volume postVolume;
    private UnityEngine.Rendering.VolumeProfile postProfile;

    // Cinemachine impulse (optional, null-safe)
    private Component impulseSource;
    private System.Reflection.MethodInfo impulseMethod;

    // Brand palettes
{primary_dict}

{glow_dict}

    // Cancel window state for chain-cancel crossfade
    private bool inCancelWindow;
    private float cancelWindowStart;
    private float cancelWindowEnd;

    private void Awake()
    {{
        CreateHitBurstParticleSystem();
        CreateFinisherParticleSystem();
        SetupPostProcessing();
        TrySetupCinemachineImpulse();
    }}

    private void Update()
    {{
        if (isInCombo && Time.time - lastHitTime > comboTimeout)
        {{
            ResetCombo();
        }}
    }}

    /// <summary>
    /// Called by the combat system when a hit lands.
    /// Pass timing data dict or null to use serialized defaults.
    /// </summary>
    public void RegisterHit(Dictionary<string, object> timingData = null)
    {{
        // Parse timing data
        int[] triggerFrames = GetVFXFrames(timingData);
        ParseCancelWindow(timingData);

        // Advance combo
        comboCount++;
        lastHitTime = Time.time;
        isInCombo = true;

        // Fire event
        OnComboHit?.Invoke(comboCount);

        // Trigger VFX for each hit frame
        foreach (int frame in triggerFrames)
        {{
            float delay = frame / 60f; // assume 60fps anim
            StartCoroutine(DelayedHitVFX(delay));
        }}

        // Check finisher
        if (comboCount >= finisherThreshold)
        {{
            float finisherDelay = triggerFrames.Length > 0 ? triggerFrames[triggerFrames.Length - 1] / 60f + 0.05f : 0.1f;
            StartCoroutine(DelayedFinisherVFX(finisherDelay));
        }}
    }}

    /// <summary>
    /// Notify the controller that the next attack in the chain is starting
    /// within the cancel window, enabling smooth VFX crossfade.
    /// </summary>
    public void NotifyChainCancel()
    {{
        inCancelWindow = true;
        // Fade out current burst smoothly instead of hard stop
        if (hitBurstPS != null && hitBurstPS.isPlaying)
        {{
            var emission = hitBurstPS.emission;
            StartCoroutine(CrossfadeParticles(hitBurstPS, 0.1f));
        }}
    }}

    public void ResetCombo()
    {{
        comboCount = 0;
        isInCombo = false;
        inCancelWindow = false;
    }}

    // ------------------------------------------------------------------
    // VFX trigger coroutines
    // ------------------------------------------------------------------

    private IEnumerator DelayedHitVFX(float delay)
    {{
        if (delay > 0f)
            yield return new WaitForSeconds(delay);

        Color primary = GetBrandColor(currentBrand, BrandPrimary);
        Color glow = GetBrandColor(currentBrand, BrandGlow);
        int tier = Mathf.Clamp(comboCount, 1, 5);

        // Scale VFX by combo tier
        float burstCount = baseParticleCount * Mathf.Pow(escalationMultiplier, tier - 1);
        float lifetime = baseLifetime * (1f + (tier - 1) * 0.2f);
        float size = baseSize * (1f + (tier - 1) * 0.15f);

        // Configure and play hit burst
        ConfigureHitBurst(primary, glow, (int)burstCount, lifetime, size, tier);
        hitBurstPS.Play();

        // Tier 2+: screen shake
        if (tier >= 2)
        {{
            TriggerScreenShake(shakeAmplitude * (0.5f + tier * 0.25f));
        }}

        // Tier 3+: chromatic aberration pulse
        if (tier >= 3)
        {{
            StartCoroutine(ChromaticAberrationPulse(chromaticAberrationPeak * (tier / 5f), chromaticDuration));
        }}
    }}

    private IEnumerator DelayedFinisherVFX(float delay)
    {{
        if (delay > 0f)
            yield return new WaitForSeconds(delay);

        OnComboFinisher?.Invoke(currentBrand);

        Color primary = GetBrandColor(currentBrand, BrandPrimary);
        Color glow = GetBrandColor(currentBrand, BrandGlow);

        ConfigureFinisher(currentBrand, primary, glow);
        finisherPS.Play();
        if (finisherSubPS != null)
            finisherSubPS.Play();

        // Full screen shake on finisher
        TriggerScreenShake(shakeAmplitude * 3f);

        // Chromatic aberration burst
        StartCoroutine(ChromaticAberrationPulse(chromaticAberrationPeak, 0.4f));

        // Reset combo after finisher
        yield return new WaitForSeconds(0.5f);
        ResetCombo();
    }}

    private IEnumerator CrossfadeParticles(ParticleSystem ps, float duration)
    {{
        // PrimeTween crossfade: ramp emission down while next attack ramps up
        float elapsed = 0f;
        var emission = ps.emission;
        float startRate = emission.rateOverTime.constant;
        while (elapsed < duration)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / duration;
            // Smooth step for natural crossfade
            float smoothT = t * t * (3f - 2f * t);
            var rateOT = emission.rateOverTime;
            emission.rateOverTime = new ParticleSystem.MinMaxCurve(Mathf.Lerp(startRate, 0f, smoothT));
            yield return null;
        }}
        ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    // ------------------------------------------------------------------
    // Timing data parsing
    // ------------------------------------------------------------------

    private int[] GetVFXFrames(Dictionary<string, object> timingData)
    {{
        if (timingData != null)
        {{
            // Check for multi-hit vfx_frames list first
            if (timingData.ContainsKey("vfx_frames") && timingData["vfx_frames"] is IList<object> frameList)
            {{
                int[] frames = new int[frameList.Count];
                for (int i = 0; i < frameList.Count; i++)
                    frames[i] = Convert.ToInt32(frameList[i]);
                return frames;
            }}
            // Fall back to single vfx_frame
            if (timingData.ContainsKey("vfx_frame"))
            {{
                return new int[] {{ Convert.ToInt32(timingData["vfx_frame"]) }};
            }}
        }}
        // Fall back to serialized fields
        if (vfxFrames != null && vfxFrames.Length > 0)
            return vfxFrames;
        return new int[] {{ vfxFrame }};
    }}

    private void ParseCancelWindow(Dictionary<string, object> timingData)
    {{
        if (timingData == null) return;
        if (timingData.ContainsKey("cancel_window_start"))
            cancelWindowStart = Convert.ToSingle(timingData["cancel_window_start"]) / 60f;
        if (timingData.ContainsKey("cancel_window_end"))
            cancelWindowEnd = Convert.ToSingle(timingData["cancel_window_end"]) / 60f;
    }}

    // ------------------------------------------------------------------
    // Particle system creation
    // ------------------------------------------------------------------

    private void CreateHitBurstParticleSystem()
    {{
        GameObject hitObj = new GameObject("ComboHitBurst");
        hitObj.transform.SetParent(transform, false);
        hitBurstPS = hitObj.AddComponent<ParticleSystem>();

        var main = hitBurstPS.main;
        main.playOnAwake = false;
        main.loop = false;
        main.startLifetime = baseLifetime;
        main.startSize = baseSize;
        main.startSpeed = 5f;
        main.maxParticles = 500;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 0.3f;

        var emission = hitBurstPS.emission;
        emission.enabled = true;
        emission.rateOverTime = 0f;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, (short)baseParticleCount)
        }});

        var shape = hitBurstPS.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 35f;
        shape.radius = 0.2f;

        var col = hitBurstPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(Color.white, 0.3f),
                new GradientColorKey(Color.white, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0.8f, 0.5f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOL = hitBurstPS.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        // Renderer
        var renderer = hitBurstPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void CreateFinisherParticleSystem()
    {{
        GameObject finObj = new GameObject("ComboFinisher");
        finObj.transform.SetParent(transform, false);
        finisherPS = finObj.AddComponent<ParticleSystem>();

        var main = finisherPS.main;
        main.playOnAwake = false;
        main.loop = false;
        main.startLifetime = 1.2f;
        main.startSize = 0.4f;
        main.startSpeed = 8f;
        main.maxParticles = 1000;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 0.5f;

        var emission = finisherPS.emission;
        emission.enabled = true;
        emission.rateOverTime = 0f;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, 200)
        }});

        var shape = finisherPS.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.5f;

        var col = finisherPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(Color.white, 0.5f),
                new GradientColorKey(Color.white, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0.6f, 0.6f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOL = finisherPS.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.8f, 1f, 0.1f));

        // Sub-emitter for secondary particles
        GameObject subObj = new GameObject("FinisherSub");
        subObj.transform.SetParent(finObj.transform, false);
        finisherSubPS = subObj.AddComponent<ParticleSystem>();

        var subMain = finisherSubPS.main;
        subMain.playOnAwake = false;
        subMain.loop = false;
        subMain.startLifetime = 0.8f;
        subMain.startSize = 0.1f;
        subMain.startSpeed = 12f;
        subMain.maxParticles = 300;
        subMain.gravityModifier = 1.0f;

        var subEmission = finisherSubPS.emission;
        subEmission.enabled = true;
        subEmission.rateOverTime = 0f;
        subEmission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, 100)
        }});

        var subShape = finisherSubPS.shape;
        subShape.enabled = true;
        subShape.shapeType = ParticleSystemShapeType.Sphere;
        subShape.radius = 0.3f;

        var subRenderer = finisherSubPS.GetComponent<ParticleSystemRenderer>();
        subRenderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        subRenderer.renderMode = ParticleSystemRenderMode.Stretch;
        subRenderer.lengthScale = 2f;

        // Renderer for main finisher
        var renderer = finisherPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    // ------------------------------------------------------------------
    // Hit burst configuration (scales by tier)
    // ------------------------------------------------------------------

    private void ConfigureHitBurst(Color primary, Color glow, int burstCount, float lifetime, float size, int tier)
    {{
        var main = hitBurstPS.main;
        main.startLifetime = lifetime;
        main.startSize = size;
        main.startColor = primary;

        // Speed increases with tier
        main.startSpeed = new ParticleSystem.MinMaxCurve(3f + tier * 1.5f, 6f + tier * 2f);

        var emission = hitBurstPS.emission;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, (short)burstCount)
        }});

        // Gradient: primary -> glow -> fade
        var col = hitBurstPS.colorOverLifetime;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glow, 0f),
                new GradientColorKey(primary, 0.4f),
                new GradientColorKey(primary * 0.5f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0.7f, 0.6f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        // Tier 3+: wider cone for bigger impact feel
        if (tier >= 3)
        {{
            var shape = hitBurstPS.shape;
            shape.angle = 35f + (tier - 2) * 10f;
            shape.radius = 0.2f + (tier - 2) * 0.1f;
        }}

        // Update material emission
        var renderer = hitBurstPS.GetComponent<ParticleSystemRenderer>();
        if (renderer.material != null)
        {{
            renderer.material.SetColor("_EmissionColor", glow * (2f + tier * 0.5f));
            renderer.material.EnableKeyword("_EMISSION");
        }}
    }}

    // ------------------------------------------------------------------
    // Brand-specific finisher configuration
    // ------------------------------------------------------------------

    private void ConfigureFinisher(string brand, Color primary, Color glow)
    {{
        var main = finisherPS.main;
        var subMain = finisherSubPS.main;
        var shape = finisherPS.shape;
        var subShape = finisherSubPS.shape;
        var emission = finisherPS.emission;
        var subEmission = finisherSubPS.emission;
        var renderer = finisherPS.GetComponent<ParticleSystemRenderer>();
        var subRenderer = finisherSubPS.GetComponent<ParticleSystemRenderer>();

        // Base finisher config
        main.startColor = primary;
        subMain.startColor = glow;
        renderer.material.SetColor("_EmissionColor", glow * 3f);
        renderer.material.EnableKeyword("_EMISSION");
        subRenderer.material.SetColor("_EmissionColor", glow * 2f);
        subRenderer.material.EnableKeyword("_EMISSION");

{finisher_blocks}
    }}

    // ------------------------------------------------------------------
    // Screen effects
    // ------------------------------------------------------------------

    private void SetupPostProcessing()
    {{
        // Find or create post-processing volume for screen effects
        postVolume = GetComponentInChildren<UnityEngine.Rendering.Volume>();
        if (postVolume == null)
        {{
            GameObject volObj = new GameObject("ComboVFX_PostProcess");
            volObj.transform.SetParent(transform, false);
            postVolume = volObj.AddComponent<UnityEngine.Rendering.Volume>();
            postVolume.isGlobal = true;
            postVolume.weight = 0f;
            postVolume.priority = 100;
            postProfile = ScriptableObject.CreateInstance<UnityEngine.Rendering.VolumeProfile>();
            postVolume.profile = postProfile;
        }}
        else
        {{
            postProfile = postVolume.sharedProfile;
        }}
    }}

    private IEnumerator ChromaticAberrationPulse(float intensity, float duration)
    {{
        if (postVolume == null) yield break;

        // PrimeTween-style ease: ramp up then down
        float halfDuration = duration * 0.5f;
        float elapsed = 0f;

        // Ramp up
        while (elapsed < halfDuration)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / halfDuration;
            float smoothT = t * t * (3f - 2f * t); // smoothstep
            postVolume.weight = smoothT * intensity;
            yield return null;
        }}

        // Ramp down
        elapsed = 0f;
        while (elapsed < halfDuration)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / halfDuration;
            float smoothT = t * t * (3f - 2f * t);
            postVolume.weight = (1f - smoothT) * intensity;
            yield return null;
        }}
        postVolume.weight = 0f;
    }}

    private void TrySetupCinemachineImpulse()
    {{
        // Reflect CinemachineImpulseSource to avoid hard dependency
        var impulseType = System.Type.GetType("Cinemachine.CinemachineImpulseSource, Cinemachine");
        if (impulseType != null)
        {{
            impulseSource = GetComponent(impulseType);
            if (impulseSource == null)
                impulseSource = gameObject.AddComponent(impulseType);
            impulseMethod = impulseType.GetMethod("GenerateImpulse", new System.Type[] {{ typeof(Vector3) }});
        }}
    }}

    private void TriggerScreenShake(float amplitude)
    {{
        if (impulseSource != null && impulseMethod != null)
        {{
            impulseMethod.Invoke(impulseSource, new object[] {{ Vector3.one * amplitude }});
        }}
    }}

    // ------------------------------------------------------------------
    // Utility
    // ------------------------------------------------------------------

    private Color GetBrandColor(string brand, Dictionary<string, Color> palette)
    {{
        if (palette.TryGetValue(brand, out Color c))
            return c;
        return palette["IRON"];
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Setup Combo VFX ({brand})")]
    public static void SetupComboVFX()
    {{
        try
        {{
            GameObject go = Selection.activeGameObject;
            if (go == null)
            {{
                go = new GameObject("ComboVFX_{brand}");
            }}
            var controller = go.GetComponent<VB_ComboVFX_{safe_brand}>();
            if (controller == null)
                controller = go.AddComponent<VB_ComboVFX_{safe_brand}>();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"combo_vfx\\", \\"brand\\": \\"{brand}\\", \\"object\\": \\"" + go.name + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Combo VFX controller added to " + go.name);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"combo_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Combo VFX setup failed: " + ex.Message);
        }}
    }}
#endif
}}
'''

    return {
        "script_path": f"Assets/Editor/Generated/VFX/VB_ComboVFX_{safe_brand}.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            f"Use menu: VeilBreakers > VFX > Setup Combo VFX ({brand})",
            "Select a GameObject first, or a new one will be created",
            "Call RegisterHit() from your combat system to trigger combo VFX",
            "Wire OnComboHit / OnComboFinisher events to your UI or game systems",
        ],
    }


def _build_all_finisher_blocks() -> str:
    """Build the C# switch block for per-brand finisher configuration.

    Each brand has completely distinct visual behavior -- unique particle
    shapes, emission counts, speeds, gravity, sizes, color gradients,
    and sub-emitter behavior.
    """
    blocks = []
    blocks.append('        switch (brand)')
    blocks.append('        {')

    # IRON: metal shrapnel burst + sparks
    blocks.append('            case "IRON":')
    blocks.append('                // Metal shrapnel burst + grinding sparks')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.5f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.25f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(6f, 14f);')
    blocks.append('                main.gravityModifier = 1.8f;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 150),')
    blocks.append('                    new ParticleSystem.Burst(0.05f, 80)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Cone;')
    blocks.append('                shape.angle = 60f;')
    blocks.append('                shape.radius = 0.3f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                renderer.lengthScale = 3f;')
    blocks.append('                // Sub: tiny sparks with high gravity')
    blocks.append('                subMain.startLifetime = 0.4f;')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.06f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(8f, 18f);')
    blocks.append('                subMain.gravityModifier = 2.5f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0f, 200) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 0.15f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                subRenderer.lengthScale = 4f;')
    blocks.append('                break;')
    blocks.append('')

    # SAVAGE: blood splatter + bone fragments
    blocks.append('            case "SAVAGE":')
    blocks.append('                // Blood splatter + bone fragments')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(1.0f, 2.0f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.1f, 0.5f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(4f, 10f);')
    blocks.append('                main.gravityModifier = 1.2f;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 120),')
    blocks.append('                    new ParticleSystem.Burst(0.08f, 60)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Cone;')
    blocks.append('                shape.angle = 45f;')
    blocks.append('                shape.radius = 0.5f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                // Sub: bone fragments -- heavy, tumbling')
    blocks.append('                subMain.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.5f);')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.08f, 0.2f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(3f, 8f);')
    blocks.append('                subMain.gravityModifier = 2.0f;')
    blocks.append('                subMain.startRotation3D = true;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0f, 40) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 0.2f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Mesh;')
    blocks.append('                break;')
    blocks.append('')

    # SURGE: lightning strike + electrical discharge
    blocks.append('            case "SURGE":')
    blocks.append('                // Lightning strike + electrical discharge arcs')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(0.1f, 0.3f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.08f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(15f, 30f);')
    blocks.append('                main.gravityModifier = 0f;')
    blocks.append('                main.maxParticles = 2000;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 300),')
    blocks.append('                    new ParticleSystem.Burst(0.02f, 200),')
    blocks.append('                    new ParticleSystem.Burst(0.05f, 150)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                shape.radius = 0.1f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                renderer.lengthScale = 6f;')
    blocks.append('                // Sub: lingering static discharge')
    blocks.append('                subMain.startLifetime = new ParticleSystem.MinMaxCurve(0.2f, 0.6f);')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.01f, 0.04f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(5f, 15f);')
    blocks.append('                subMain.gravityModifier = 0f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 100),')
    blocks.append('                    new ParticleSystem.Burst(0.1f, 80),')
    blocks.append('                    new ParticleSystem.Burst(0.15f, 60)')
    blocks.append('                });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 0.8f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                subRenderer.lengthScale = 5f;')
    blocks.append('                break;')
    blocks.append('')

    # VENOM: toxic cloud explosion
    blocks.append('            case "VENOM":')
    blocks.append('                // Toxic cloud explosion -- slow billowing poison')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(2.0f, 4.0f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.5f, 1.5f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(1f, 4f);')
    blocks.append('                main.gravityModifier = -0.1f;')
    blocks.append('                main.maxParticles = 500;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 80),')
    blocks.append('                    new ParticleSystem.Burst(0.2f, 50),')
    blocks.append('                    new ParticleSystem.Burst(0.5f, 30)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                shape.radius = 0.8f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                // Sub: dripping toxic droplets')
    blocks.append('                subMain.startLifetime = new ParticleSystem.MinMaxCurve(1.0f, 2.0f);')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.08f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 2f);')
    blocks.append('                subMain.gravityModifier = 1.5f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0.1f, 60) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 1.0f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                break;')
    blocks.append('')

    # DREAD: shadow nova + fear pulse ring
    blocks.append('            case "DREAD":')
    blocks.append('                // Shadow nova + expanding fear pulse ring')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(1.5f, 3.0f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.3f, 1.0f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(2f, 6f);')
    blocks.append('                main.gravityModifier = -0.05f;')
    blocks.append('                main.maxParticles = 600;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 100),')
    blocks.append('                    new ParticleSystem.Burst(0.1f, 80)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                shape.radius = 0.4f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                // Sub: fear pulse ring -- fast outward ring')
    blocks.append('                subMain.startLifetime = 0.6f;')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.1f, 0.3f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(10f, 16f);')
    blocks.append('                subMain.gravityModifier = 0f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0f, 150) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Circle;')
    blocks.append('                subShape.radius = 0.2f;')
    blocks.append('                subShape.arc = 360f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                subRenderer.lengthScale = 2f;')
    blocks.append('                break;')
    blocks.append('')

    # LEECH: crimson energy drain spiral
    blocks.append('            case "LEECH":')
    blocks.append('                // Crimson energy drain spiral -- inward vortex')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(1.0f, 2.0f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.2f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(-2f, -6f);')
    blocks.append('                main.gravityModifier = 0f;')
    blocks.append('                main.maxParticles = 800;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 60),')
    blocks.append('                    new ParticleSystem.Burst(0.15f, 60),')
    blocks.append('                    new ParticleSystem.Burst(0.3f, 60)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                shape.radius = 2.5f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                renderer.lengthScale = 3f;')
    blocks.append('                // Sub: blood orb coalescing at center')
    blocks.append('                subMain.startLifetime = 1.5f;')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.3f, 0.6f);')
    blocks.append('                subMain.startSpeed = 0f;')
    blocks.append('                subMain.gravityModifier = 0f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0.3f, 5) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 0.1f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                break;')
    blocks.append('')

    # GRACE: divine judgment rays
    blocks.append('            case "GRACE":')
    blocks.append('                // Divine judgment rays -- upward light pillars')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(0.6f, 1.2f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.1f, 0.4f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(8f, 15f);')
    blocks.append('                main.gravityModifier = -0.5f;')
    blocks.append('                main.maxParticles = 800;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 200),')
    blocks.append('                    new ParticleSystem.Burst(0.1f, 100)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Cone;')
    blocks.append('                shape.angle = 10f;')
    blocks.append('                shape.radius = 0.6f;')
    blocks.append('                shape.rotation = new Vector3(-90f, 0f, 0f);')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                renderer.lengthScale = 5f;')
    blocks.append('                // Sub: sparkle falloff -- tiny glitter drifting down')
    blocks.append('                subMain.startLifetime = new ParticleSystem.MinMaxCurve(1.0f, 2.5f);')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.08f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 2f);')
    blocks.append('                subMain.gravityModifier = 0.3f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0.05f, 120) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 1.5f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                break;')
    blocks.append('')

    # MEND: restoration nova
    blocks.append('            case "MEND":')
    blocks.append('                // Restoration nova -- warm golden expanding wave')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(1.5f, 2.5f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.1f, 0.35f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(3f, 7f);')
    blocks.append('                main.gravityModifier = -0.2f;')
    blocks.append('                main.maxParticles = 600;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 120),')
    blocks.append('                    new ParticleSystem.Burst(0.2f, 80)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                shape.radius = 0.3f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                // Sub: golden leaf-like particles drifting upward')
    blocks.append('                subMain.startLifetime = new ParticleSystem.MinMaxCurve(2.0f, 3.5f);')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.15f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(1f, 3f);')
    blocks.append('                subMain.gravityModifier = -0.3f;')
    blocks.append('                subMain.startRotation3D = true;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0.1f, 80) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 1.0f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                break;')
    blocks.append('')

    # RUIN: seismic shockwave + debris
    blocks.append('            case "RUIN":')
    blocks.append('                // Seismic shockwave + burning debris')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.8f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.15f, 0.6f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(5f, 12f);')
    blocks.append('                main.gravityModifier = 1.5f;')
    blocks.append('                main.maxParticles = 800;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 180),')
    blocks.append('                    new ParticleSystem.Burst(0.05f, 100),')
    blocks.append('                    new ParticleSystem.Burst(0.1f, 60)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Hemisphere;')
    blocks.append('                shape.radius = 0.5f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                // Sub: ground crack shockwave ring')
    blocks.append('                subMain.startLifetime = 0.5f;')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.1f, 0.3f);')
    blocks.append('                subMain.startSpeed = new ParticleSystem.MinMaxCurve(12f, 20f);')
    blocks.append('                subMain.gravityModifier = 0f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0f, 200) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Circle;')
    blocks.append('                subShape.radius = 0.2f;')
    blocks.append('                subShape.arc = 360f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Stretch;')
    blocks.append('                subRenderer.lengthScale = 3f;')
    blocks.append('                break;')
    blocks.append('')

    # VOID: dimensional collapse + suction
    blocks.append('            case "VOID":')
    blocks.append('                // Dimensional collapse -- inward suction + dark implosion')
    blocks.append('                main.startLifetime = new ParticleSystem.MinMaxCurve(1.5f, 3.0f);')
    blocks.append('                main.startSize = new ParticleSystem.MinMaxCurve(0.2f, 0.8f);')
    blocks.append('                main.startSpeed = new ParticleSystem.MinMaxCurve(-3f, -8f);')
    blocks.append('                main.gravityModifier = 0f;')
    blocks.append('                main.maxParticles = 1000;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] {')
    blocks.append('                    new ParticleSystem.Burst(0f, 100),')
    blocks.append('                    new ParticleSystem.Burst(0.1f, 80),')
    blocks.append('                    new ParticleSystem.Burst(0.3f, 60),')
    blocks.append('                    new ParticleSystem.Burst(0.5f, 40)')
    blocks.append('                });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                shape.radius = 3.0f;')
    blocks.append('                renderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                // Sub: void tear fragments at implosion center')
    blocks.append('                subMain.startLifetime = 2.0f;')
    blocks.append('                subMain.startSize = new ParticleSystem.MinMaxCurve(0.5f, 1.2f);')
    blocks.append('                subMain.startSpeed = 0f;')
    blocks.append('                subMain.gravityModifier = 0f;')
    blocks.append('                subEmission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0.5f, 8) });')
    blocks.append('                subShape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                subShape.radius = 0.05f;')
    blocks.append('                subRenderer.renderMode = ParticleSystemRenderMode.Billboard;')
    blocks.append('                break;')
    blocks.append('')

    # Default fallback (same as IRON)
    blocks.append('            default:')
    blocks.append('                // Fallback: generic burst')
    blocks.append('                main.startLifetime = 1.0f;')
    blocks.append('                main.startSize = 0.2f;')
    blocks.append('                main.startSpeed = 6f;')
    blocks.append('                emission.SetBursts(new ParticleSystem.Burst[] { new ParticleSystem.Burst(0f, 150) });')
    blocks.append('                shape.shapeType = ParticleSystemShapeType.Sphere;')
    blocks.append('                shape.radius = 0.4f;')
    blocks.append('                break;')

    blocks.append('        }')
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# P5-Q4: Channel/Sustain VFX System
# ---------------------------------------------------------------------------


def generate_channel_vfx_script() -> dict[str, Any]:
    """Generate C# file with three channel/sustain VFX MonoBehaviours.

    Contains:
    - ChannelVFXController: looping particles while ability held, intensity ramp, release burst
    - AuraVFXController: persistent halo, brand-colored, enable/disable with fade
    - BeamVFXController: line renderer + particles between caster and target

    All use ParticleSystem, PrimeTween for animations, C# events for state.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    primary_dict = _brand_colors_cs_dict(BRAND_PRIMARY_COLORS, "BrandPrimary")
    glow_dict = _brand_colors_cs_dict(BRAND_GLOW_COLORS, "BrandGlow")
    dark_dict = _brand_colors_cs_dict(BRAND_DARK_COLORS, "BrandDark")

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using PrimeTween;
#if UNITY_EDITOR
using UnityEditor;
#endif

// ==========================================================================
// P5-Q4: Channel/Sustain VFX System
// Three MonoBehaviours: ChannelVFXController, AuraVFXController, BeamVFXController
// ==========================================================================

// --------------------------------------------------------------------------
// Shared brand color lookup
// --------------------------------------------------------------------------
public static class CombatVFXBrandColors
{{
{primary_dict}

{glow_dict}

{dark_dict}

    public static Color GetPrimary(string brand)
    {{
        return BrandPrimary.TryGetValue(brand, out Color c) ? c : BrandPrimary["IRON"];
    }}

    public static Color GetGlow(string brand)
    {{
        return BrandGlow.TryGetValue(brand, out Color c) ? c : BrandGlow["IRON"];
    }}

    public static Color GetDark(string brand)
    {{
        return BrandDark.TryGetValue(brand, out Color c) ? c : BrandDark["IRON"];
    }}
}}

// ==========================================================================
// 1) ChannelVFXController
// ==========================================================================

/// <summary>
/// Looping particle VFX while an ability is being channeled/held.
/// Intensity ramps up over time via PrimeTween. On release, fires a
/// burst proportional to accumulated intensity.
/// </summary>
public class ChannelVFXController : MonoBehaviour
{{
    [Header("Channel Settings")]
    [SerializeField] private float maxIntensity = 3.0f;
    [SerializeField] private float rampUpDuration = 2.0f;
    [SerializeField] private float releaseBurstMultiplier = 5.0f;
    [SerializeField] private int baseEmissionRate = 40;
    [SerializeField] private float baseParticleSize = 0.12f;
    [SerializeField] private float baseParticleLifetime = 1.0f;

    // Events
    public event Action<string> OnChannelStarted;
    public event Action<string, float> OnChannelReleased; // brand, accumulated intensity

    // State
    private bool isChanneling;
    private string activeBrand = "IRON";
    private float currentIntensity;
    private Tween intensityTween;

    // VFX
    private ParticleSystem channelPS;
    private ParticleSystem releasePS;

    private void Awake()
    {{
        CreateChannelParticleSystem();
        CreateReleaseParticleSystem();
    }}

    /// <summary>Start channeling with the specified brand.</summary>
    public void StartChannel(string brand)
    {{
        if (isChanneling) StopChannel();

        activeBrand = brand ?? "IRON";
        isChanneling = true;
        currentIntensity = 0f;

        Color primary = CombatVFXBrandColors.GetPrimary(activeBrand);
        Color glow = CombatVFXBrandColors.GetGlow(activeBrand);

        ConfigureChannelPS(primary, glow);
        channelPS.Play();

        // Ramp intensity up via PrimeTween
        intensityTween = Tween.Custom(0f, maxIntensity, rampUpDuration, ease: Ease.InOutSine, onValueChange: val =>
        {{
            currentIntensity = val;
            UpdateChannelIntensity(val, primary, glow);
        }});

        OnChannelStarted?.Invoke(activeBrand);
    }}

    /// <summary>Stop channeling and fire release burst.</summary>
    public void StopChannel()
    {{
        if (!isChanneling) return;
        isChanneling = false;

        // Kill ramp tween
        if (intensityTween.isAlive)
            intensityTween.Stop();

        // Fire release burst scaled by accumulated intensity
        FireReleaseBurst();

        // Stop channel particles with fade
        StartCoroutine(FadeOutChannel(0.3f));

        OnChannelReleased?.Invoke(activeBrand, currentIntensity);
    }}

    private void UpdateChannelIntensity(float intensity, Color primary, Color glow)
    {{
        if (channelPS == null) return;

        var main = channelPS.main;
        // Scale emission rate with intensity
        var emission = channelPS.emission;
        emission.rateOverTime = baseEmissionRate * (1f + intensity * 1.5f);

        // Scale particle size
        main.startSize = baseParticleSize * (1f + intensity * 0.4f);

        // Shift color toward glow at higher intensity
        float t = intensity / maxIntensity;
        Color blended = Color.Lerp(primary, glow, t);
        main.startColor = blended;

        // Scale emission color intensity for bloom
        var renderer = channelPS.GetComponent<ParticleSystemRenderer>();
        if (renderer != null && renderer.material != null)
        {{
            renderer.material.SetColor("_EmissionColor", glow * (1f + intensity * 2f));
            renderer.material.EnableKeyword("_EMISSION");
        }}
    }}

    private void FireReleaseBurst()
    {{
        if (releasePS == null) return;

        Color primary = CombatVFXBrandColors.GetPrimary(activeBrand);
        Color glow = CombatVFXBrandColors.GetGlow(activeBrand);
        float intensityRatio = currentIntensity / maxIntensity;

        var main = releasePS.main;
        main.startColor = glow;
        main.startSize = new ParticleSystem.MinMaxCurve(
            0.15f * (1f + intensityRatio),
            0.5f * (1f + intensityRatio)
        );
        main.startSpeed = new ParticleSystem.MinMaxCurve(
            4f + intensityRatio * 6f,
            8f + intensityRatio * 10f
        );

        var emission = releasePS.emission;
        int burstCount = (int)(baseEmissionRate * releaseBurstMultiplier * (0.5f + intensityRatio));
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, (short)Mathf.Clamp(burstCount, 20, 500))
        }});

        var renderer = releasePS.GetComponent<ParticleSystemRenderer>();
        if (renderer != null && renderer.material != null)
        {{
            renderer.material.SetColor("_EmissionColor", glow * (3f + intensityRatio * 4f));
            renderer.material.EnableKeyword("_EMISSION");
        }}

        releasePS.Play();
    }}

    private IEnumerator FadeOutChannel(float duration)
    {{
        var emission = channelPS.emission;
        float startRate = emission.rateOverTime.constant;
        float elapsed = 0f;
        while (elapsed < duration)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / duration;
            emission.rateOverTime = Mathf.Lerp(startRate, 0f, t * t);
            yield return null;
        }}
        channelPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    private void ConfigureChannelPS(Color primary, Color glow)
    {{
        var main = channelPS.main;
        main.startColor = primary;
        main.startLifetime = baseParticleLifetime;
        main.startSize = baseParticleSize;
        main.startSpeed = new ParticleSystem.MinMaxCurve(1f, 3f);

        var emission = channelPS.emission;
        emission.rateOverTime = baseEmissionRate;

        // Gradient: glow core -> primary -> fade
        var col = channelPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glow, 0f),
                new GradientColorKey(primary, 0.4f),
                new GradientColorKey(primary * 0.6f, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0.9f, 0f),
                new GradientAlphaKey(0.7f, 0.5f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var renderer = channelPS.GetComponent<ParticleSystemRenderer>();
        if (renderer.material != null)
        {{
            renderer.material.SetColor("_EmissionColor", glow * 2f);
            renderer.material.EnableKeyword("_EMISSION");
        }}
    }}

    private void CreateChannelParticleSystem()
    {{
        GameObject obj = new GameObject("ChannelParticles");
        obj.transform.SetParent(transform, false);
        channelPS = obj.AddComponent<ParticleSystem>();

        var main = channelPS.main;
        main.playOnAwake = false;
        main.loop = true;
        main.startLifetime = baseParticleLifetime;
        main.startSize = baseParticleSize;
        main.startSpeed = new ParticleSystem.MinMaxCurve(1f, 3f);
        main.maxParticles = 500;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = -0.1f;

        var emission = channelPS.emission;
        emission.rateOverTime = baseEmissionRate;

        var shape = channelPS.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.5f;

        var sizeOL = channelPS.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.5f, 1f, 0f));

        // Noise for organic movement
        var noise = channelPS.noise;
        noise.enabled = true;
        noise.strength = 0.3f;
        noise.frequency = 1.5f;
        noise.scrollSpeed = 0.5f;
        noise.damping = true;
        noise.octaveCount = 2;

        var renderer = channelPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void CreateReleaseParticleSystem()
    {{
        GameObject obj = new GameObject("ChannelReleaseBurst");
        obj.transform.SetParent(transform, false);
        releasePS = obj.AddComponent<ParticleSystem>();

        var main = releasePS.main;
        main.playOnAwake = false;
        main.loop = false;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.4f, 0.8f);
        main.startSize = new ParticleSystem.MinMaxCurve(0.15f, 0.5f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(4f, 10f);
        main.maxParticles = 600;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 0.2f;

        var emission = releasePS.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new ParticleSystem.Burst[] {{
            new ParticleSystem.Burst(0f, 100)
        }});

        var shape = releasePS.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.3f;

        var col = releasePS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(Color.white, 0.3f),
                new GradientColorKey(Color.gray, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(1f, 0f),
                new GradientAlphaKey(0.5f, 0.5f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOL = releasePS.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        var renderer = releasePS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void OnDestroy()
    {{
        if (intensityTween.isAlive)
            intensityTween.Stop();
    }}
}}

// ==========================================================================
// 2) AuraVFXController
// ==========================================================================

/// <summary>
/// Persistent particle halo attached to a character. Brand-colored,
/// enable/disable with PrimeTween alpha fade. Configurable radius
/// and particle count.
/// </summary>
public class AuraVFXController : MonoBehaviour
{{
    [Header("Aura Settings")]
    [SerializeField] private float auraRadius = 1.2f;
    [SerializeField] private int particleCount = 60;
    [SerializeField] private float particleSize = 0.08f;
    [SerializeField] private float particleLifetime = 2.0f;
    [SerializeField] private float fadeDuration = 0.5f;
    [SerializeField] private float orbitSpeed = 0.8f;

    // Events
    public event Action<string, bool> OnAuraChanged; // brand, enabled

    // State
    private bool isAuraActive;
    private string activeBrand = "IRON";
    private ParticleSystem auraPS;
    private ParticleSystem innerGlowPS;
    private Tween fadeTween;
    private CanvasGroup fadeProxy; // used as a float holder for PrimeTween

    private void Awake()
    {{
        CreateAuraParticleSystem();
        CreateInnerGlowParticleSystem();
    }}

    /// <summary>Enable or disable the aura with the specified brand.</summary>
    public void SetAura(string brand, bool enabled)
    {{
        activeBrand = brand ?? "IRON";

        if (enabled && !isAuraActive)
        {{
            EnableAura();
        }}
        else if (!enabled && isAuraActive)
        {{
            DisableAura();
        }}
        else if (enabled && isAuraActive)
        {{
            // Brand changed while active -- reconfigure
            ReconfigureAuraColors();
        }}

        OnAuraChanged?.Invoke(activeBrand, enabled);
    }}

    private void EnableAura()
    {{
        isAuraActive = true;
        ReconfigureAuraColors();

        // Start with zero emission and fade in via PrimeTween
        var emission = auraPS.emission;
        emission.rateOverTime = 0f;
        auraPS.Play();

        var innerEmission = innerGlowPS.emission;
        innerEmission.rateOverTime = 0f;
        innerGlowPS.Play();

        if (fadeTween.isAlive) fadeTween.Stop();
        fadeTween = Tween.Custom(0f, 1f, fadeDuration, ease: Ease.OutCubic, onValueChange: t =>
        {{
            var em = auraPS.emission;
            em.rateOverTime = particleCount * t;
            var innerEm = innerGlowPS.emission;
            innerEm.rateOverTime = (particleCount * 0.3f) * t;
        }});
    }}

    private void DisableAura()
    {{
        isAuraActive = false;

        if (fadeTween.isAlive) fadeTween.Stop();
        fadeTween = Tween.Custom(1f, 0f, fadeDuration, ease: Ease.InCubic, onValueChange: t =>
        {{
            var em = auraPS.emission;
            em.rateOverTime = particleCount * t;
            var innerEm = innerGlowPS.emission;
            innerEm.rateOverTime = (particleCount * 0.3f) * t;
            if (t <= 0.01f)
            {{
                auraPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
                innerGlowPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            }}
        }});
    }}

    private void ReconfigureAuraColors()
    {{
        Color primary = CombatVFXBrandColors.GetPrimary(activeBrand);
        Color glow = CombatVFXBrandColors.GetGlow(activeBrand);
        Color dark = CombatVFXBrandColors.GetDark(activeBrand);

        // Main aura particles
        var main = auraPS.main;
        main.startColor = new ParticleSystem.MinMaxGradient(primary, glow);

        var col = auraPS.colorOverLifetime;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glow, 0f),
                new GradientColorKey(primary, 0.5f),
                new GradientColorKey(dark, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.6f, 0.2f),
                new GradientAlphaKey(0.4f, 0.8f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var renderer = auraPS.GetComponent<ParticleSystemRenderer>();
        if (renderer.material != null)
        {{
            renderer.material.SetColor("_EmissionColor", glow * 2f);
            renderer.material.EnableKeyword("_EMISSION");
        }}

        // Inner glow
        var innerMain = innerGlowPS.main;
        innerMain.startColor = glow;

        var innerRenderer = innerGlowPS.GetComponent<ParticleSystemRenderer>();
        if (innerRenderer.material != null)
        {{
            innerRenderer.material.SetColor("_EmissionColor", glow * 3f);
            innerRenderer.material.EnableKeyword("_EMISSION");
        }}
    }}

    private void CreateAuraParticleSystem()
    {{
        GameObject obj = new GameObject("AuraParticles");
        obj.transform.SetParent(transform, false);
        auraPS = obj.AddComponent<ParticleSystem>();

        var main = auraPS.main;
        main.playOnAwake = false;
        main.loop = true;
        main.startLifetime = particleLifetime;
        main.startSize = new ParticleSystem.MinMaxCurve(particleSize * 0.5f, particleSize);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.2f, 0.6f);
        main.maxParticles = particleCount * 3;
        main.simulationSpace = ParticleSystemSimulationSpace.Local;
        main.gravityModifier = -0.05f;

        var emission = auraPS.emission;
        emission.rateOverTime = particleCount;

        var shape = auraPS.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = auraRadius;
        shape.radiusThickness = 0.8f;

        // Velocity over lifetime: slow orbit
        var vel = auraPS.velocityOverLifetime;
        vel.enabled = true;
        vel.orbitalY = orbitSpeed;
        vel.radial = -0.1f; // slight inward pull

        var sizeOL = auraPS.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 0.3f, 1f, 0f));

        var col = auraPS.colorOverLifetime;
        col.enabled = true;

        // Noise for organic drift
        var noise = auraPS.noise;
        noise.enabled = true;
        noise.strength = 0.15f;
        noise.frequency = 0.8f;
        noise.scrollSpeed = 0.3f;
        noise.damping = true;

        var renderer = auraPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void CreateInnerGlowParticleSystem()
    {{
        GameObject obj = new GameObject("AuraInnerGlow");
        obj.transform.SetParent(transform, false);
        innerGlowPS = obj.AddComponent<ParticleSystem>();

        var main = innerGlowPS.main;
        main.playOnAwake = false;
        main.loop = true;
        main.startLifetime = new ParticleSystem.MinMaxCurve(1.5f, 2.5f);
        main.startSize = new ParticleSystem.MinMaxCurve(auraRadius * 0.6f, auraRadius * 0.9f);
        main.startSpeed = 0f;
        main.maxParticles = 10;
        main.simulationSpace = ParticleSystemSimulationSpace.Local;

        var emission = innerGlowPS.emission;
        emission.rateOverTime = particleCount * 0.3f;

        var shape = innerGlowPS.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = 0.1f;

        var col = innerGlowPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{ new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.15f, 0.3f),
                new GradientAlphaKey(0.1f, 0.7f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var renderer = innerGlowPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void OnDestroy()
    {{
        if (fadeTween.isAlive)
            fadeTween.Stop();
    }}
}}

// ==========================================================================
// 3) BeamVFXController
// ==========================================================================

/// <summary>
/// Line renderer + particles between caster (this transform) and a target.
/// Tracks target position each frame. Width pulses via PrimeTween sine loop.
/// Brand-colored beam with particles along the beam path.
/// </summary>
public class BeamVFXController : MonoBehaviour
{{
    [Header("Beam Settings")]
    [SerializeField] private float baseWidth = 0.15f;
    [SerializeField] private float pulseAmplitude = 0.06f;
    [SerializeField] private float pulseFrequency = 2.0f;
    [SerializeField] private int beamSegments = 20;
    [SerializeField] private float noiseAmplitude = 0.08f;
    [SerializeField] private float noiseSpeed = 3.0f;

    [Header("Beam Particles")]
    [SerializeField] private int beamParticleRate = 30;
    [SerializeField] private float beamParticleSize = 0.06f;
    [SerializeField] private float beamParticleLifetime = 0.5f;

    // Events
    public event Action<string> OnBeamStarted;
    public event Action OnBeamStopped;

    // State
    private bool isBeamActive;
    private string activeBrand = "IRON";
    private Transform beamTarget;

    // Components
    private LineRenderer lineRenderer;
    private ParticleSystem beamPS;
    private Material beamMaterial;
    private Tween pulseTween;
    private float currentPulseWidth;

    private void Awake()
    {{
        CreateLineRenderer();
        CreateBeamParticleSystem();
        lineRenderer.enabled = false;
    }}

    private void Update()
    {{
        if (!isBeamActive || beamTarget == null) return;
        UpdateBeamPositions();
        UpdateBeamParticleEmission();
    }}

    /// <summary>Start beam to target with specified brand color.</summary>
    public void StartBeam(string brand, Transform target)
    {{
        if (target == null) return;
        if (isBeamActive) StopBeam();

        activeBrand = brand ?? "IRON";
        beamTarget = target;
        isBeamActive = true;

        Color primary = CombatVFXBrandColors.GetPrimary(activeBrand);
        Color glow = CombatVFXBrandColors.GetGlow(activeBrand);

        ConfigureBeamColors(primary, glow);
        lineRenderer.enabled = true;
        beamPS.Play();

        // Start width pulse loop via PrimeTween
        StartWidthPulse();

        OnBeamStarted?.Invoke(activeBrand);
    }}

    /// <summary>Stop the beam.</summary>
    public void StopBeam()
    {{
        if (!isBeamActive) return;
        isBeamActive = false;
        beamTarget = null;

        if (pulseTween.isAlive) pulseTween.Stop();
        lineRenderer.enabled = false;
        beamPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        OnBeamStopped?.Invoke();
    }}

    private void UpdateBeamPositions()
    {{
        Vector3 start = transform.position;
        Vector3 end = beamTarget.position;
        Vector3 dir = (end - start);
        float length = dir.magnitude;

        lineRenderer.positionCount = beamSegments;
        for (int i = 0; i < beamSegments; i++)
        {{
            float t = (float)i / (beamSegments - 1);
            Vector3 basePos = Vector3.Lerp(start, end, t);

            // Add perpendicular noise for electrical/energy look
            // Noise is strongest in the middle of the beam, zero at endpoints
            float noiseFactor = Mathf.Sin(t * Mathf.PI); // 0 at ends, 1 at middle
            float noiseX = Mathf.PerlinNoise(t * 5f + Time.time * noiseSpeed, 0f) - 0.5f;
            float noiseY = Mathf.PerlinNoise(0f, t * 5f + Time.time * noiseSpeed) - 0.5f;

            Vector3 right = Vector3.Cross(dir.normalized, Vector3.up).normalized;
            Vector3 up = Vector3.Cross(dir.normalized, right).normalized;

            basePos += right * noiseX * noiseAmplitude * noiseFactor * 2f;
            basePos += up * noiseY * noiseAmplitude * noiseFactor * 2f;

            lineRenderer.SetPosition(i, basePos);
        }}

        // Update width with pulse
        float width = baseWidth + currentPulseWidth;
        lineRenderer.startWidth = width;
        lineRenderer.endWidth = width * 0.6f;
    }}

    private void UpdateBeamParticleEmission()
    {{
        if (beamPS == null || beamTarget == null) return;

        // Move beam particle shape along the beam
        Vector3 start = transform.position;
        Vector3 end = beamTarget.position;
        Vector3 mid = (start + end) * 0.5f;

        var shape = beamPS.shape;
        shape.position = transform.InverseTransformPoint(mid);
        shape.scale = new Vector3(0.2f, 0.2f, Vector3.Distance(start, end));
        shape.rotation = Quaternion.LookRotation(end - start).eulerAngles;
    }}

    private void StartWidthPulse()
    {{
        if (pulseTween.isAlive) pulseTween.Stop();
        // PrimeTween sine loop for width pulsing
        pulseTween = Tween.Custom(
            -pulseAmplitude, pulseAmplitude, 1f / pulseFrequency,
            cycles: -1, cycleMode: CycleMode.Yoyo, ease: Ease.InOutSine,
            onValueChange: val => {{ currentPulseWidth = val; }}
        );
    }}

    private void ConfigureBeamColors(Color primary, Color glow)
    {{
        // Line renderer gradient
        Gradient lineGrad = new Gradient();
        lineGrad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(glow, 0f),
                new GradientColorKey(primary, 0.5f),
                new GradientColorKey(glow, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0.9f, 0f),
                new GradientAlphaKey(1f, 0.5f),
                new GradientAlphaKey(0.9f, 1f)
            }}
        );
        lineRenderer.colorGradient = lineGrad;

        // Beam material emission
        if (beamMaterial != null)
        {{
            beamMaterial.SetColor("_EmissionColor", glow * 3f);
            beamMaterial.EnableKeyword("_EMISSION");
            beamMaterial.color = primary;
        }}

        // Beam particles
        var main = beamPS.main;
        main.startColor = new ParticleSystem.MinMaxGradient(primary, glow);

        var renderer = beamPS.GetComponent<ParticleSystemRenderer>();
        if (renderer.material != null)
        {{
            renderer.material.SetColor("_EmissionColor", glow * 2f);
            renderer.material.EnableKeyword("_EMISSION");
        }}
    }}

    private void CreateLineRenderer()
    {{
        lineRenderer = gameObject.AddComponent<LineRenderer>();
        lineRenderer.positionCount = beamSegments;
        lineRenderer.startWidth = baseWidth;
        lineRenderer.endWidth = baseWidth * 0.6f;
        lineRenderer.numCornerVertices = 4;
        lineRenderer.numCapVertices = 4;
        lineRenderer.useWorldSpace = true;
        lineRenderer.textureMode = LineTextureMode.Tile;
        lineRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        lineRenderer.receiveShadows = false;

        beamMaterial = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        beamMaterial.SetFloat("_Mode", 1f); // Additive
        lineRenderer.material = beamMaterial;
    }}

    private void CreateBeamParticleSystem()
    {{
        GameObject obj = new GameObject("BeamParticles");
        obj.transform.SetParent(transform, false);
        beamPS = obj.AddComponent<ParticleSystem>();

        var main = beamPS.main;
        main.playOnAwake = false;
        main.loop = true;
        main.startLifetime = beamParticleLifetime;
        main.startSize = new ParticleSystem.MinMaxCurve(beamParticleSize * 0.5f, beamParticleSize);
        main.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 2f);
        main.maxParticles = 200;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 0f;

        var emission = beamPS.emission;
        emission.rateOverTime = beamParticleRate;

        var shape = beamPS.shape;
        shape.enabled = true;
        shape.shapeType = ParticleSystemShapeType.Box;
        shape.scale = new Vector3(0.2f, 0.2f, 1f);

        var col = beamPS.colorOverLifetime;
        col.enabled = true;
        Gradient grad = new Gradient();
        grad.SetKeys(
            new GradientColorKey[] {{
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(Color.white, 0.5f),
                new GradientColorKey(Color.white, 1f)
            }},
            new GradientAlphaKey[] {{
                new GradientAlphaKey(0.8f, 0f),
                new GradientAlphaKey(0.5f, 0.5f),
                new GradientAlphaKey(0f, 1f)
            }}
        );
        col.color = new ParticleSystem.MinMaxGradient(grad);

        var sizeOL = beamPS.sizeOverLifetime;
        sizeOL.enabled = true;
        sizeOL.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0f, 1f, 1f, 0f));

        var noise = beamPS.noise;
        noise.enabled = true;
        noise.strength = 0.1f;
        noise.frequency = 2f;
        noise.scrollSpeed = 1f;

        var renderer = beamPS.GetComponent<ParticleSystemRenderer>();
        renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
        renderer.renderMode = ParticleSystemRenderMode.Billboard;
    }}

    private void OnDestroy()
    {{
        if (pulseTween.isAlive)
            pulseTween.Stop();
        if (beamMaterial != null)
            Destroy(beamMaterial);
    }}
}}

// ==========================================================================
// Editor setup menu item
// ==========================================================================

#if UNITY_EDITOR
public static class VB_ChannelSustainVFXSetup
{{
    [MenuItem("VeilBreakers/VFX/Setup Channel-Sustain VFX")]
    public static void SetupChannelSustainVFX()
    {{
        try
        {{
            GameObject go = Selection.activeGameObject;
            if (go == null)
            {{
                go = new GameObject("ChannelSustainVFX");
            }}

            // Add all three controllers if not present
            if (go.GetComponent<ChannelVFXController>() == null)
                go.AddComponent<ChannelVFXController>();
            if (go.GetComponent<AuraVFXController>() == null)
                go.AddComponent<AuraVFXController>();
            if (go.GetComponent<BeamVFXController>() == null)
                go.AddComponent<BeamVFXController>();

            string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"channel_sustain_vfx\\", \\"object\\": \\"" + go.name + "\\", \\"components\\": [\\"ChannelVFXController\\", \\"AuraVFXController\\", \\"BeamVFXController\\"]}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.Log("[VeilBreakers] Channel/Sustain VFX controllers added to " + go.name);
        }}
        catch (System.Exception ex)
        {{
            string json = "{{\\"status\\": \\"error\\", \\"action\\": \\"channel_sustain_vfx\\", \\"message\\": \\"" + ex.Message.Replace("\\"", "\\\\\\"") + "\\"}}";
            File.WriteAllText("Temp/vb_result.json", json);
            Debug.LogError("[VeilBreakers] Channel/Sustain VFX setup failed: " + ex.Message);
        }}
    }}
}}
#endif
'''

    return {
        "script_path": "Assets/Editor/Generated/VFX/VB_ChannelSustainVFX.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Use menu: VeilBreakers > VFX > Setup Channel-Sustain VFX",
            "Select a GameObject first, or a new one will be created",
            "Call StartChannel(brand)/StopChannel() for channel VFX",
            "Call SetAura(brand, true/false) for persistent aura VFX",
            "Call StartBeam(brand, target)/StopBeam() for beam VFX",
            "Wire events (OnChannelStarted, OnAuraChanged, OnBeamStarted) to game systems",
        ],
    }
