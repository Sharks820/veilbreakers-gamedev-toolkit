"""Multi-phase VFX skill composition generators for VeilBreakers.

Unlike single-ParticleSystem templates, these generate COMPLETE cinematic skill
sequences.  Each skill is a choreographed composition of ParticleSystems,
LineRenderers, TrailRenderers, Lights, mesh primitives, and screen-space
effects — orchestrated through coroutine timelines with C# events for every
phase transition.

Three flagship skills:
    generate_lightning_skill_vfx   -- SURGE chain-lightning (charge/arc/impact/chain)
    generate_shield_dome_skill_vfx -- IRON dome barrier (activate/sustain/hit/break)
    generate_void_rend_skill_vfx   -- VOID reality-tear  (tear/rift/pulse/collapse)

Unity 2022.3+ URP.  PrimeTween for procedural animation.  Cinemachine 3.x for
camera impulse.  URP Volume for post-processing spikes.
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

# ---------------------------------------------------------------------------
# Brand palette (canonical RGBA) for all 10 brands
# ---------------------------------------------------------------------------

BRAND_PRIMARY: dict[str, list[float]] = {
    "IRON": [0.55, 0.59, 0.65, 1.0], "SAVAGE": [0.71, 0.18, 0.18, 1.0],
    "SURGE": [0.24, 0.55, 0.86, 1.0], "VENOM": [0.31, 0.71, 0.24, 1.0],
    "DREAD": [0.47, 0.24, 0.63, 1.0], "LEECH": [0.55, 0.16, 0.31, 1.0],
    "GRACE": [0.86, 0.86, 0.94, 1.0], "MEND": [0.78, 0.67, 0.31, 1.0],
    "RUIN": [0.86, 0.47, 0.16, 1.0], "VOID": [0.16, 0.08, 0.24, 1.0],
}
BRAND_GLOW: dict[str, list[float]] = {
    "IRON": [0.71, 0.75, 0.80, 1.0], "SAVAGE": [0.86, 0.27, 0.27, 1.0],
    "SURGE": [0.39, 0.71, 1.00, 1.0], "VENOM": [0.47, 0.86, 0.39, 1.0],
    "DREAD": [0.63, 0.39, 0.78, 1.0], "LEECH": [0.71, 0.24, 0.43, 1.0],
    "GRACE": [1.00, 1.00, 1.00, 1.0], "MEND": [0.94, 0.82, 0.47, 1.0],
    "RUIN": [1.00, 0.63, 0.31, 1.0], "VOID": [0.39, 0.24, 0.55, 1.0],
}
BRAND_DARK: dict[str, list[float]] = {
    "IRON": [0.31, 0.35, 0.39, 1.0], "SAVAGE": [0.47, 0.10, 0.10, 1.0],
    "SURGE": [0.12, 0.31, 0.55, 1.0], "VENOM": [0.16, 0.39, 0.12, 1.0],
    "DREAD": [0.27, 0.12, 0.39, 1.0], "LEECH": [0.35, 0.08, 0.20, 1.0],
    "GRACE": [0.63, 0.63, 0.71, 1.0], "MEND": [0.55, 0.43, 0.16, 1.0],
    "RUIN": [0.63, 0.27, 0.08, 1.0], "VOID": [0.06, 0.02, 0.10, 1.0],
}

ALL_BRANDS = list(BRAND_PRIMARY.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from the VeilBreakers menu to instantiate the prefab",
]


def _c(rgba: list[float], hdr_mult: float = 1.0) -> str:
    """Format RGBA list as C# Color constructor with optional HDR multiplier."""
    r, g, b, a = rgba
    return f"new Color({r * hdr_mult:.2f}f, {g * hdr_mult:.2f}f, {b * hdr_mult:.2f}f, {a:.2f}f)"


# ===================================================================
# 1. CHAIN LIGHTNING SKILL VFX
# ===================================================================

def generate_lightning_skill_vfx(brand: str = "SURGE") -> dict:
    """Generate a complete chain-lightning skill VFX composition.

    Four phases:
        1. Charge  -- energy gathering, hand glow, body arcs (0.3s)
        2. Launch  -- main procedural bolt + branches + glow trail (0.1s)
        3. Impact  -- flash, sparks, screen shake, ground scorch (0.15s)
        4. Chain   -- 2-3 jumps to nearest enemies, diminishing intensity
    """
    brand = brand.upper()
    if brand not in BRAND_PRIMARY:
        brand = "SURGE"
    prim = BRAND_PRIMARY[brand]
    glow = BRAND_GLOW[brand]
    dark = BRAND_DARK[brand]
    safe_brand = sanitize_cs_identifier(brand)

    class_name = f"LightningSkillVFX_{safe_brand}"
    script_path = f"Assets/VeilBreakers/Scripts/VFX/Skills/{class_name}.cs"

    cs = f'''using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
#if PRIME_TWEEN
using PrimeTween;
#endif
#if CINEMACHINE
using Unity.Cinemachine;
#endif

namespace VeilBreakers.VFX.Skills
{{
    /// <summary>
    /// Complete chain-lightning skill VFX for the {brand} brand.
    /// Orchestrates charge -> arc -> impact -> chain-jump phases with
    /// LineRenderer procedural bolts, ParticleSystems, Lights, screen FX.
    /// </summary>
    public class {class_name} : MonoBehaviour
    {{
        // ---------------------------------------------------------------
        // Phase events -- subscribe for gameplay hooks
        // ---------------------------------------------------------------
        public event Action OnChargeStart;
        public event Action OnChargeFull;
        public event Action OnLaunch;
        public event Action<Vector3> OnImpact;          // hit world pos
        public event Action<int, Vector3> OnChainJump;   // jump index, pos
        public event Action OnComplete;

        // ---------------------------------------------------------------
        // Tuning -- all serialized for designer override
        // ---------------------------------------------------------------
        [Header("=== Phase Timing ===")]
        [SerializeField] private float chargeDuration   = 0.3f;
        [SerializeField] private float launchDuration   = 0.1f;
        [SerializeField] private float impactDuration   = 0.15f;
        [SerializeField] private float chainJumpDelay   = 0.1f;

        [Header("=== Lightning Bolt ===")]
        [SerializeField] private int   boltSegments     = 22;
        [SerializeField] private float boltJitter       = 0.4f;
        [SerializeField] private float boltJitterY      = 0.2f;
        [SerializeField] private float boltWidthStart   = 0.3f;
        [SerializeField] private float boltWidthEnd     = 0.05f;
        [SerializeField] private float boltFlickerRate  = 0.03f;
        [SerializeField] private float boltFlickerTime  = 0.2f;

        [Header("=== Branch Bolts ===")]
        [SerializeField] private int   branchCount      = 3;
        [SerializeField] private int   branchSegments   = 10;
        [SerializeField] private float branchAlpha      = 0.6f;
        [SerializeField] private float branchWidth      = 0.12f;
        [SerializeField] private float branchLength     = 1.8f;

        [Header("=== Charge Phase ===")]
        [SerializeField] private int   chargeSparkRate  = 80;
        [SerializeField] private float chargeGlowMax    = 5f;
        [SerializeField] private int   bodyArcCount     = 3;
        [SerializeField] private int   bodyArcSegments  = 8;

        [Header("=== Impact Phase ===")]
        [SerializeField] private int   impactSparkCount = 30;
        [SerializeField] private float impactFlashSize  = 2f;
        [SerializeField] private float shakeIntensity   = 0.3f;
        [SerializeField] private float chromaticSpike   = 0.5f;
        [SerializeField] private float scorchSize       = 1.2f;

        [Header("=== Chain Jumps ===")]
        [SerializeField] private int   maxChainJumps    = 3;
        [SerializeField] private float chainSearchRadius = 12f;
        [SerializeField] private float chainIntensityFalloff = 0.7f;

        [Header("=== Brand Colors ===")]
        [SerializeField] private Color brandPrimary = {_c(prim)};
        [SerializeField] private Color brandGlow    = {_c(glow)};
        [SerializeField] private Color brandDark    = {_c(dark)};
        [SerializeField] private Color boltCoreHDR  = {_c(glow, 8.0)};

        // ---------------------------------------------------------------
        // Runtime refs -- built by Setup()
        // ---------------------------------------------------------------
        private LineRenderer           mainBolt;
        private List<LineRenderer>     branches = new List<LineRenderer>();
        private List<LineRenderer>     bodyArcs = new List<LineRenderer>();
        private ParticleSystem         chargeSparks;
        private ParticleSystem         boltGlowTrail;
        private ParticleSystem         impactFlash;
        private ParticleSystem         impactSparks;
        private ParticleSystem         ozoneSmoke;
        private Light                  handGlow;
        private GameObject             groundScorch;
        private Volume                 postVolume;
        private ChromaticAberration    chromAb;
        private Coroutine              activeRoutine;

        // ---------------------------------------------------------------
        // Public API
        // ---------------------------------------------------------------

        /// <summary>Fire the full lightning sequence at a world-space target.</summary>
        public void Play(Vector3 target)
        {{
            if (activeRoutine != null) StopCoroutine(activeRoutine);
            activeRoutine = StartCoroutine(FullSequence(target));
        }}

        /// <summary>Cancel and clean up all active visuals.</summary>
        public void Stop()
        {{
            if (activeRoutine != null) {{ StopCoroutine(activeRoutine); activeRoutine = null; }}
            CleanupVisuals();
        }}

        // ---------------------------------------------------------------
        // Lifecycle
        // ---------------------------------------------------------------

        private void Awake()
        {{
            Setup();
        }}

        private void OnDestroy()
        {{
            CleanupVisuals();
        }}

        // ---------------------------------------------------------------
        // Setup -- build every visual element as child GameObjects
        // ---------------------------------------------------------------

        private void Setup()
        {{
            // === CHARGE: inward-gathering sparks ===
            chargeSparks = CreateParticleChild("ChargeSparks",
                rate: chargeSparkRate, lifetime: 0.3f, startSize: 0.08f,
                startColor: brandGlow, gravityMod: 0f, additive: true);
            // Shape: sphere emitting inward toward hand
            var csShape = chargeSparks.shape;
            csShape.shapeType = ParticleSystemShapeType.Sphere;
            csShape.radius = 1.5f;
            // Velocity toward center (negative radial)
            var csVel = chargeSparks.velocityOverLifetime;
            csVel.enabled = true;
            csVel.radial = -4f;
            chargeSparks.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === CHARGE: hand point light ===
            var handGlowGO = new GameObject("HandGlow");
            handGlowGO.transform.SetParent(transform, false);
            handGlow = handGlowGO.AddComponent<Light>();
            handGlow.type = LightType.Point;
            handGlow.color = brandGlow;
            handGlow.intensity = 0f;
            handGlow.range = 4f;

            // === CHARGE: body arcs (small LineRenderers flickering on caster) ===
            for (int i = 0; i < bodyArcCount; i++)
            {{
                var arc = CreateLineRendererChild($"BodyArc_{{i}}", bodyArcSegments, 0.04f, boltCoreHDR, branchAlpha);
                arc.enabled = false;
                bodyArcs.Add(arc);
            }}

            // === LAUNCH: main lightning bolt ===
            mainBolt = CreateLineRendererChild("MainBolt", boltSegments, boltWidthStart, boltCoreHDR, 1f);
            // Width curve: thick at source, thin at tip
            mainBolt.widthCurve = new AnimationCurve(
                new Keyframe(0f, boltWidthStart),
                new Keyframe(0.3f, boltWidthStart * 0.8f),
                new Keyframe(0.7f, boltWidthEnd * 2f),
                new Keyframe(1f, boltWidthEnd));
            mainBolt.enabled = false;

            // === LAUNCH: branch bolts ===
            for (int i = 0; i < branchCount; i++)
            {{
                var br = CreateLineRendererChild($"Branch_{{i}}", branchSegments, branchWidth, boltCoreHDR, branchAlpha);
                br.enabled = false;
                branches.Add(br);
            }}

            // === LAUNCH: glow trail particles along bolt path ===
            boltGlowTrail = CreateParticleChild("BoltGlowTrail",
                rate: 0, lifetime: 0.2f, startSize: 0.5f,
                startColor: brandGlow, gravityMod: 0f, additive: true);
            boltGlowTrail.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === IMPACT: bright flash burst ===
            impactFlash = CreateParticleChild("ImpactFlash",
                rate: 0, lifetime: 0.15f, startSize: 0.1f,
                startColor: Color.white, gravityMod: 0f, additive: true);
            // Size over lifetime: 0 -> impactFlashSize -> 0
            var ifsol = impactFlash.sizeOverLifetime;
            ifsol.enabled = true;
            ifsol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(
                new Keyframe(0f, 0f), new Keyframe(0.3f, 1f), new Keyframe(1f, 0f)));
            impactFlash.transform.localScale = Vector3.one * impactFlashSize;
            impactFlash.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === IMPACT: sparks radiating outward ===
            impactSparks = CreateParticleChild("ImpactSparks",
                rate: 0, lifetime: 0.6f, startSize: 0.06f,
                startColor: brandGlow, gravityMod: 0.8f, additive: true);
            var isShape = impactSparks.shape;
            isShape.shapeType = ParticleSystemShapeType.Sphere;
            isShape.radius = 0.1f;
            var isMain = impactSparks.main;
            isMain.startSpeed = new ParticleSystem.MinMaxCurve(3f, 8f);
            var isCol = impactSparks.collision;
            isCol.enabled = true;
            isCol.type = ParticleSystemCollisionType.World;
            isCol.bounce = 0.3f;
            isCol.lifetimeLoss = 0.2f;
            impactSparks.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === IMPACT: ozone smoke puff ===
            ozoneSmoke = CreateParticleChild("OzoneSmoke",
                rate: 0, lifetime: 1.2f, startSize: 0.6f,
                startColor: new Color(0.7f, 0.75f, 0.85f, 0.3f),
                gravityMod: -0.05f, additive: false);
            ozoneSmoke.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === IMPACT: ground scorch decal (dark quad) ===
            groundScorch = GameObject.CreatePrimitive(PrimitiveType.Quad);
            groundScorch.name = "GroundScorch";
            groundScorch.transform.SetParent(transform, false);
            groundScorch.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            groundScorch.transform.localScale = Vector3.one * scorchSize;
            var scorchRend = groundScorch.GetComponent<Renderer>();
            var scorchMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            scorchMat.color = new Color(0.05f, 0.03f, 0.02f, 0.85f);
            scorchMat.SetFloat("_Surface", 1f); // Transparent
            scorchMat.SetFloat("_Blend", 0f);
            scorchMat.renderQueue = 2501; // Just above geometry for decal layering
            scorchRend.material = scorchMat;
            Destroy(groundScorch.GetComponent<Collider>());
            groundScorch.SetActive(false);

            // === POST-PROCESSING volume (chromatic aberration spike) ===
            var volGO = new GameObject("LightningPostFX");
            volGO.transform.SetParent(transform, false);
            postVolume = volGO.AddComponent<Volume>();
            postVolume.isGlobal = true;
            postVolume.weight = 0f;
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            chromAb = profile.Add<ChromaticAberration>(false);
            chromAb.intensity.Override(chromaticSpike);
            postVolume.profile = profile;
        }}

        // ---------------------------------------------------------------
        // Full choreography coroutine
        // ---------------------------------------------------------------

        private IEnumerator FullSequence(Vector3 target)
        {{
            Vector3 origin = transform.position;

            // ====== PHASE 1: CHARGE (gather energy, hand glow, body arcs) ======
            OnChargeStart?.Invoke();
            chargeSparks.Play();
            float chargeElapsed = 0f;
            foreach (var arc in bodyArcs) arc.enabled = true;
            while (chargeElapsed < chargeDuration)
            {{
                float t = chargeElapsed / chargeDuration;
                // Ramp hand glow intensity from 0 to max
                handGlow.intensity = Mathf.Lerp(0f, chargeGlowMax, t * t);
                // Flicker body arcs with random mini-lightning on caster
                foreach (var arc in bodyArcs)
                {{
                    GenerateBodyArc(arc);
                }}
                chargeElapsed += Time.deltaTime;
                yield return null;
            }}
            handGlow.intensity = chargeGlowMax;
            OnChargeFull?.Invoke();
            chargeSparks.Stop(true, ParticleSystemStopBehavior.StopEmitting);

            // ====== PHASE 2: LAUNCH ARC (main bolt + branches + glow) ======
            OnLaunch?.Invoke();
            mainBolt.enabled = true;
            foreach (var br in branches) br.enabled = true;

            // Emit glow particles along bolt path
            EmitGlowAlongPath(origin, target);

            // Flicker the bolt for boltFlickerTime seconds
            float flickerElapsed = 0f;
            while (flickerElapsed < boltFlickerTime)
            {{
                // Regenerate jagged path every boltFlickerRate for strobing effect
                GenerateLightningPath(mainBolt, origin, target, boltSegments,
                    boltJitter, boltJitterY);
                GenerateBranches(origin, target);
                flickerElapsed += boltFlickerRate;
                yield return new WaitForSeconds(boltFlickerRate);
            }}

            // Disable bolt after flicker
            mainBolt.enabled = false;
            foreach (var br in branches) br.enabled = false;
            foreach (var arc in bodyArcs) arc.enabled = false;
            handGlow.intensity = 0f;

            // ====== PHASE 3: IMPACT at primary target ======
            yield return StartCoroutine(ImpactSequence(target, 1f));
            OnImpact?.Invoke(target);

            // ====== PHASE 4: CHAIN JUMPS ======
            Vector3 lastHitPos = target;
            float intensity = 1f;
            HashSet<Collider> alreadyHit = new HashSet<Collider>();
            // Mark initial target area
            MarkNearbyAsHit(target, 1f, alreadyHit);

            for (int jump = 0; jump < maxChainJumps; jump++)
            {{
                yield return new WaitForSeconds(chainJumpDelay);
                intensity *= chainIntensityFalloff;

                // Find nearest un-hit enemy
                Vector3 nextTarget;
                if (!FindNextChainTarget(lastHitPos, alreadyHit, out nextTarget))
                    break;

                OnChainJump?.Invoke(jump, nextTarget);

                // Chain bolt (thinner, fewer segments)
                mainBolt.enabled = true;
                int chainSegs = Mathf.Max(8, boltSegments - jump * 4);
                mainBolt.widthMultiplier = intensity;
                float chainFlicker = 0f;
                float chainFlickerDur = boltFlickerTime * intensity;
                while (chainFlicker < chainFlickerDur)
                {{
                    GenerateLightningPath(mainBolt, lastHitPos, nextTarget,
                        chainSegs, boltJitter * intensity, boltJitterY * intensity);
                    chainFlicker += boltFlickerRate;
                    yield return new WaitForSeconds(boltFlickerRate);
                }}
                mainBolt.enabled = false;
                mainBolt.widthMultiplier = 1f;

                // Chain impact (diminished)
                yield return StartCoroutine(ImpactSequence(nextTarget, intensity));

                MarkNearbyAsHit(nextTarget, 1f, alreadyHit);
                lastHitPos = nextTarget;
            }}

            // Fade ground scorch over 2 seconds then disable
            yield return FadeScorch(2f);

            OnComplete?.Invoke();
            activeRoutine = null;
        }}

        // ---------------------------------------------------------------
        // Impact sub-sequence (reused for each chain hit)
        // ---------------------------------------------------------------

        private IEnumerator ImpactSequence(Vector3 pos, float intensity)
        {{
            // Move impact elements to position
            impactFlash.transform.position = pos;
            impactSparks.transform.position = pos;
            ozoneSmoke.transform.position = pos;

            // Flash burst
            var flashMain = impactFlash.main;
            flashMain.startColor = Color.Lerp(Color.white, brandGlow, 0.3f);
            impactFlash.transform.localScale = Vector3.one * impactFlashSize * intensity;
            impactFlash.Emit(1);

            // Spark burst
            int sparkCount = Mathf.RoundToInt(impactSparkCount * intensity);
            impactSparks.Emit(sparkCount);

            // Ozone smoke puff
            ozoneSmoke.Emit(Mathf.RoundToInt(5 * intensity));

            // Ground scorch at hit point
            if (intensity > 0.5f)
            {{
                groundScorch.SetActive(true);
                groundScorch.transform.position = pos + Vector3.up * 0.02f;
                groundScorch.transform.localScale = Vector3.one * scorchSize * intensity;
            }}

            // Screen shake via Cinemachine impulse
#if CINEMACHINE
            var impulse = FindAnyObjectByType<CinemachineImpulseSource>();
            if (impulse != null)
            {{
                impulse.GenerateImpulse(shakeIntensity * intensity);
            }}
#endif

            // Chromatic aberration spike
            if (chromAb != null && postVolume != null)
            {{
                chromAb.intensity.Override(chromaticSpike * intensity);
                postVolume.weight = 1f;
#if PRIME_TWEEN
                Tween.Custom(postVolume, 1f, 0f, impactDuration,
                    (vol, val) => vol.weight = val);
#else
                yield return StartCoroutine(FadeVolume(impactDuration));
#endif
            }}

            yield return new WaitForSeconds(impactDuration);
        }}

        // ---------------------------------------------------------------
        // Procedural lightning bolt generation
        // ---------------------------------------------------------------

        /// <summary>
        /// Generate a jagged lightning bolt between two points.
        /// Each interior segment is displaced perpendicular to the bolt direction
        /// using a sin-envelope so endpoints stay pinned while the middle is wildest.
        /// Regenerate every frame for a flickering strobe effect.
        /// </summary>
        private void GenerateLightningPath(LineRenderer lr, Vector3 start, Vector3 end,
            int segments, float jitter, float jitterY)
        {{
            lr.positionCount = segments;
            Vector3 dir = (end - start).normalized;
            // Perpendicular axes for displacement
            Vector3 perp = Vector3.Cross(dir, Vector3.up).normalized;
            if (perp.sqrMagnitude < 0.001f)
                perp = Vector3.Cross(dir, Vector3.right).normalized;
            Vector3 perpY = Vector3.Cross(dir, perp).normalized;

            for (int i = 0; i < segments; i++)
            {{
                float t = (float)i / (segments - 1);
                Vector3 basePos = Vector3.Lerp(start, end, t);

                // Sin envelope: max displacement at middle, zero at endpoints
                float envelope = Mathf.Sin(t * Mathf.PI);
                float dx = envelope * UnityEngine.Random.Range(-jitter, jitter);
                float dy = envelope * UnityEngine.Random.Range(-jitterY, jitterY);

                lr.SetPosition(i, basePos + perp * dx + perpY * dy);
            }}
        }}

        /// <summary>
        /// Generate branch bolts that fork off the main bolt at random points.
        /// Each branch is shorter, thinner, and more jagged than the main.
        /// </summary>
        private void GenerateBranches(Vector3 origin, Vector3 target)
        {{
            if (mainBolt.positionCount < 2) return;

            for (int b = 0; b < branches.Count && b < branchCount; b++)
            {{
                // Pick a random point along the main bolt (not endpoints)
                int branchIdx = UnityEngine.Random.Range(3, mainBolt.positionCount - 2);
                Vector3 branchStart = mainBolt.GetPosition(branchIdx);

                // Branch direction: mostly perpendicular to bolt + slight forward
                Vector3 boltDir = (target - origin).normalized;
                Vector3 bPerp = Vector3.Cross(boltDir, Vector3.up).normalized;
                float side = UnityEngine.Random.value > 0.5f ? 1f : -1f;
                Vector3 branchDir = (bPerp * side + boltDir * 0.3f +
                    Vector3.up * UnityEngine.Random.Range(-0.3f, 0.3f)).normalized;
                Vector3 branchEnd = branchStart + branchDir * branchLength;

                GenerateLightningPath(branches[b], branchStart, branchEnd,
                    branchSegments, boltJitter * 1.3f, boltJitterY * 1.3f);
            }}
        }}

        /// <summary>Generate small random arcs on the caster body during charge.</summary>
        private void GenerateBodyArc(LineRenderer arc)
        {{
            Vector3 center = transform.position + Vector3.up * 1f;
            Vector3 start = center + UnityEngine.Random.insideUnitSphere * 0.4f;
            Vector3 end   = center + UnityEngine.Random.insideUnitSphere * 0.5f;
            GenerateLightningPath(arc, start, end, bodyArcSegments, 0.15f, 0.1f);
        }}

        /// <summary>Emit soft glow particles at each bolt segment position.</summary>
        private void EmitGlowAlongPath(Vector3 start, Vector3 end)
        {{
            int count = Mathf.Min(boltSegments, 20);
            var emitParams = new ParticleSystem.EmitParams();
            emitParams.startColor = brandGlow;
            emitParams.startSize = 0.5f;
            emitParams.startLifetime = 0.2f;
            for (int i = 0; i < count; i++)
            {{
                float t = (float)i / (count - 1);
                emitParams.position = Vector3.Lerp(start, end, t);
                boltGlowTrail.Emit(emitParams, 1);
            }}
        }}

        // ---------------------------------------------------------------
        // Chain target search
        // ---------------------------------------------------------------

        private bool FindNextChainTarget(Vector3 from, HashSet<Collider> exclude,
            out Vector3 target)
        {{
            target = Vector3.zero;
            Collider[] hits = Physics.OverlapSphere(from, chainSearchRadius);
            float bestDist = float.MaxValue;
            Collider best = null;
            foreach (var hit in hits)
            {{
                if (exclude.Contains(hit)) continue;
                // Look for anything tagged Enemy or with a Health component
                if (!hit.CompareTag("Enemy") && hit.GetComponent<MonoBehaviour>() == null)
                    continue;
                float d = Vector3.Distance(from, hit.transform.position);
                if (d < bestDist && d > 0.5f)
                {{
                    bestDist = d;
                    best = hit;
                }}
            }}
            if (best != null)
            {{
                target = best.transform.position + Vector3.up * 1f;
                exclude.Add(best);
                return true;
            }}
            return false;
        }}

        private void MarkNearbyAsHit(Vector3 pos, float radius, HashSet<Collider> set)
        {{
            foreach (var c in Physics.OverlapSphere(pos, radius))
                set.Add(c);
        }}

        // ---------------------------------------------------------------
        // Utility: fade post-processing volume weight (non-PrimeTween fallback)
        // ---------------------------------------------------------------

        private IEnumerator FadeVolume(float duration)
        {{
            float elapsed = 0f;
            while (elapsed < duration)
            {{
                postVolume.weight = Mathf.Lerp(1f, 0f, elapsed / duration);
                elapsed += Time.deltaTime;
                yield return null;
            }}
            postVolume.weight = 0f;
        }}

        /// <summary>Fade the ground scorch decal alpha then disable.</summary>
        private IEnumerator FadeScorch(float duration)
        {{
            if (!groundScorch.activeSelf) yield break;
            var rend = groundScorch.GetComponent<Renderer>();
            Color c = rend.material.color;
            float startAlpha = c.a;
            float elapsed = 0f;
            while (elapsed < duration)
            {{
                c.a = Mathf.Lerp(startAlpha, 0f, elapsed / duration);
                rend.material.color = c;
                elapsed += Time.deltaTime;
                yield return null;
            }}
            groundScorch.SetActive(false);
            c.a = startAlpha;
            rend.material.color = c;
        }}

        // ---------------------------------------------------------------
        // Cleanup
        // ---------------------------------------------------------------

        private void CleanupVisuals()
        {{
            if (chargeSparks != null) chargeSparks.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (impactFlash != null) impactFlash.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (impactSparks != null) impactSparks.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (ozoneSmoke != null) ozoneSmoke.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (boltGlowTrail != null) boltGlowTrail.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (mainBolt != null) mainBolt.enabled = false;
            foreach (var br in branches) {{ if (br != null) br.enabled = false; }}
            foreach (var arc in bodyArcs) {{ if (arc != null) arc.enabled = false; }}
            if (handGlow != null) handGlow.intensity = 0f;
            if (groundScorch != null) groundScorch.SetActive(false);
            if (postVolume != null) postVolume.weight = 0f;
        }}

        // ---------------------------------------------------------------
        // Factory helpers
        // ---------------------------------------------------------------

        private ParticleSystem CreateParticleChild(string name, float rate,
            float lifetime, float startSize, Color startColor,
            float gravityMod, bool additive)
        {{
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = lifetime;
            main.startSize = startSize;
            main.startColor = startColor;
            main.gravityModifier = gravityMod;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 500;

            var emission = ps.emission;
            if (rate > 0)
            {{
                emission.rateOverTime = rate;
            }}
            else
            {{
                emission.rateOverTime = 0;
            }}

            // Renderer: additive or alpha-blend
            var rend = go.GetComponent<ParticleSystemRenderer>();
            rend.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
            if (additive)
            {{
                rend.material.SetFloat("_Surface", 1f);
                rend.material.SetFloat("_Blend", 1f); // Additive
            }}
            else
            {{
                rend.material.SetFloat("_Surface", 1f);
                rend.material.SetFloat("_Blend", 0f); // Alpha
            }}
            rend.material.SetColor("_BaseColor", startColor);

            return ps;
        }}

        private LineRenderer CreateLineRendererChild(string name, int segments,
            float width, Color color, float alpha)
        {{
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = segments;
            lr.startWidth = width;
            lr.endWidth = width * 0.3f;
            lr.numCapVertices = 4;
            lr.numCornerVertices = 4;
            lr.useWorldSpace = true;

            // HDR emissive material for bloom glow
            var mat = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
            mat.SetFloat("_Surface", 1f);
            mat.SetFloat("_Blend", 1f); // Additive
            Color c = color;
            c.a = alpha;
            mat.SetColor("_BaseColor", c);
            mat.SetColor("_EmissionColor", c);
            lr.material = mat;

            return lr;
        }}

#if UNITY_EDITOR
        [UnityEditor.MenuItem("VeilBreakers/VFX/Skills/Create Lightning Skill VFX ({brand})")]
        private static void CreateInScene()
        {{
            var go = new GameObject("{class_name}");
            go.AddComponent<{class_name}>();
            UnityEditor.Selection.activeGameObject = go;
            Debug.Log("[VeilBreakers] Created {class_name} in scene. Call Play(target) to fire.");
        }}
#endif
    }}
}}
'''

    return {
        "script_path": script_path,
        "script_content": cs.strip(),
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 2. SHIELD DOME SKILL VFX
# ===================================================================

def generate_shield_dome_skill_vfx(brand: str = "IRON") -> dict:
    """Generate a complete shield/barrier dome skill VFX composition.

    Four phases:
        1. Activate   -- dome mesh expands, ring particles sweep upward (0.3s)
        2. Sustain    -- dome pulses, surface sparkles, interior glow (duration)
        3. Hit React  -- ripple at impact point, opacity spike, wobble (per hit)
        4. Break      -- dome shatters into fragments, flash, dissolve (0.3s)
    """
    brand = brand.upper()
    if brand not in BRAND_PRIMARY:
        brand = "IRON"
    prim = BRAND_PRIMARY[brand]
    glow = BRAND_GLOW[brand]
    dark = BRAND_DARK[brand]
    safe_brand = sanitize_cs_identifier(brand)

    class_name = f"ShieldDomeVFX_{safe_brand}"
    script_path = f"Assets/VeilBreakers/Scripts/VFX/Skills/{class_name}.cs"

    cs = f'''using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
#if PRIME_TWEEN
using PrimeTween;
#endif

namespace VeilBreakers.VFX.Skills
{{
    /// <summary>
    /// Complete shield-dome VFX for the {brand} brand.
    /// Visible transparent sphere with fresnel rim, activation ring,
    /// sustain pulse, per-hit ripple reactions, and shattering break.
    /// </summary>
    public class {class_name} : MonoBehaviour
    {{
        // ---------------------------------------------------------------
        // Phase events
        // ---------------------------------------------------------------
        public event Action OnActivate;
        public event Action OnSustainStart;
        public event Action<Vector3> OnHitReaction;    // world-space hit point
        public event Action OnBreak;
        public event Action OnDeactivate;

        // ---------------------------------------------------------------
        // Tuning
        // ---------------------------------------------------------------
        [Header("=== Dome Geometry ===")]
        [SerializeField] private float domeRadius       = 2.5f;
        [SerializeField] private float activateDuration = 0.3f;
        [SerializeField] private float breakDuration    = 0.3f;

        [Header("=== Dome Material ===")]
        [SerializeField] private float baseAlpha        = 0.15f;
        [SerializeField] private float hitAlphaSpike    = 0.4f;
        [SerializeField] private float fresnelPower     = 3.5f;
        [SerializeField] private float emissionMult     = 3f;

        [Header("=== Sustain Pulse ===")]
        [SerializeField] private float pulseMinAlpha    = 0.10f;
        [SerializeField] private float pulseMaxAlpha    = 0.20f;
        [SerializeField] private float pulseFrequency   = 2f;

        [Header("=== Surface Particles ===")]
        [SerializeField] private int   surfaceSparkRate = 15;
        [SerializeField] private float surfaceSparkLife = 1.2f;
        [SerializeField] private float surfaceSparkSize = 0.08f;

        [Header("=== Activation Ring ===")]
        [SerializeField] private int   ringParticleCount = 60;
        [SerializeField] private float ringExpandSpeed   = 5f;

        [Header("=== Hit Reaction ===")]
        [SerializeField] private float hitRippleDuration = 0.2f;
        [SerializeField] private int   hitSparkCount     = 12;
        [SerializeField] private float wobbleIntensity   = 0.05f;

        [Header("=== Shatter ===")]
        [SerializeField] private int   shardCount       = 20;
        [SerializeField] private float shardSpeed       = 4f;
        [SerializeField] private float shardFadeTime    = 0.5f;
        [SerializeField] private float residualSparkleTime = 1f;
        [SerializeField] private int   residualSparkleRate = 25;

        [Header("=== Interior Light ===")]
        [SerializeField] private float interiorIntensity = 1.5f;

        [Header("=== Brand Colors ===")]
        [SerializeField] private Color brandPrimary = {_c(prim)};
        [SerializeField] private Color brandGlow    = {_c(glow)};
        [SerializeField] private Color brandDark    = {_c(dark)};

        // ---------------------------------------------------------------
        // Runtime refs
        // ---------------------------------------------------------------
        private GameObject        domeMesh;
        private Material          domeMaterial;
        private ParticleSystem    activationRing;
        private ParticleSystem    surfaceSparkles;
        private ParticleSystem    hitSparks;
        private ParticleSystem    shatterFragments;
        private ParticleSystem    residualSparkles;
        private Light             interiorLight;
        private Light             activationFlash;
        private bool              isActive;
        private Coroutine         sustainRoutine;

        // ---------------------------------------------------------------
        // Public API
        // ---------------------------------------------------------------

        /// <summary>Activate the shield dome.</summary>
        public void Play()
        {{
            if (isActive) return;
            StartCoroutine(ActivateSequence());
        }}

        /// <summary>Call when the shield is hit at a world position.</summary>
        public void OnHitReactionAt(Vector3 hitWorldPos)
        {{
            if (!isActive) return;
            StartCoroutine(HitReactionSequence(hitWorldPos));
        }}

        /// <summary>Break/deactivate the shield.</summary>
        public void Stop()
        {{
            if (!isActive) return;
            StartCoroutine(BreakSequence());
        }}

        // ---------------------------------------------------------------
        // Lifecycle
        // ---------------------------------------------------------------

        private void Awake()
        {{
            Setup();
        }}

        private void OnDestroy()
        {{
            if (domeMaterial != null) Destroy(domeMaterial);
        }}

        // ---------------------------------------------------------------
        // Setup
        // ---------------------------------------------------------------

        private void Setup()
        {{
            // === DOME MESH: transparent sphere with fresnel rim ===
            domeMesh = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            domeMesh.name = "ShieldDome";
            domeMesh.transform.SetParent(transform, false);
            domeMesh.transform.localScale = Vector3.zero; // starts collapsed
            Destroy(domeMesh.GetComponent<Collider>());

            // Build dome material: transparent, brand-colored, rim glow
            domeMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            domeMaterial.SetFloat("_Surface", 1f);   // Transparent
            domeMaterial.SetFloat("_Blend", 0f);     // Alpha
            domeMaterial.SetOverrideTag("RenderType", "Transparent");
            domeMaterial.renderQueue = 3000;
            domeMaterial.SetFloat("_ZWrite", 0f);
            domeMaterial.SetFloat("_Cull", 0f);      // Double-sided for inside view
            // Base color: brand primary with low alpha (see-through center)
            Color baseCol = brandPrimary;
            baseCol.a = baseAlpha;
            domeMaterial.SetColor("_BaseColor", baseCol);
            // Emission for the glow (fresnel is approximated by rim emission)
            domeMaterial.EnableKeyword("_EMISSION");
            domeMaterial.SetColor("_EmissionColor", brandGlow * emissionMult);
            domeMaterial.SetFloat("_Smoothness", 0.95f);
            domeMesh.GetComponent<Renderer>().material = domeMaterial;
            domeMesh.SetActive(false);

            // === ACTIVATION RING: ring of particles sweeping upward ===
            activationRing = CreateParticle("ActivationRing", 0, 0.5f, 0.12f,
                brandGlow, 0f, true);
            var arShape = activationRing.shape;
            arShape.shapeType = ParticleSystemShapeType.Circle;
            arShape.radius = domeRadius;
            var arVel = activationRing.velocityOverLifetime;
            arVel.enabled = true;
            arVel.y = ringExpandSpeed;
            arVel.radial = 1.5f;
            activationRing.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === SUSTAIN: surface sparkles drifting on sphere ===
            surfaceSparkles = CreateParticle("SurfaceSparkles", surfaceSparkRate,
                surfaceSparkLife, surfaceSparkSize, brandGlow, 0f, true);
            var ssShape = surfaceSparkles.shape;
            ssShape.shapeType = ParticleSystemShapeType.Sphere;
            ssShape.radius = domeRadius;
            var ssMain = surfaceSparkles.main;
            ssMain.startSpeed = 0f;
            surfaceSparkles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === HIT: spark burst at impact point ===
            hitSparks = CreateParticle("HitSparks", 0, 0.4f, 0.06f,
                brandGlow, 0.3f, true);
            var hsShape = hitSparks.shape;
            hsShape.shapeType = ParticleSystemShapeType.Hemisphere;
            hsShape.radius = 0.3f;
            var hsMain = hitSparks.main;
            hsMain.startSpeed = new ParticleSystem.MinMaxCurve(2f, 5f);
            hitSparks.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === SHATTER: mesh fragment particles flying outward ===
            shatterFragments = CreateParticle("ShatterFragments", 0, shardFadeTime + 0.3f,
                0.15f, brandGlow, 0.4f, true);
            var sfShape = shatterFragments.shape;
            sfShape.shapeType = ParticleSystemShapeType.Sphere;
            sfShape.radius = domeRadius * 0.9f;
            var sfMain = shatterFragments.main;
            sfMain.startSpeed = new ParticleSystem.MinMaxCurve(shardSpeed * 0.5f, shardSpeed);
            // Size over lifetime: fade out
            var sfSol = shatterFragments.sizeOverLifetime;
            sfSol.enabled = true;
            sfSol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(
                new Keyframe(0f, 1f), new Keyframe(0.5f, 0.8f), new Keyframe(1f, 0f)));
            // Color over lifetime: fade alpha
            var sfCol = shatterFragments.colorOverLifetime;
            sfCol.enabled = true;
            Gradient grad = new Gradient();
            grad.SetKeys(
                new GradientColorKey[] {{ new GradientColorKey(brandGlow, 0f), new GradientColorKey(brandGlow, 1f) }},
                new GradientAlphaKey[] {{ new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0f, 1f) }}
            );
            sfCol.color = grad;
            shatterFragments.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === RESIDUAL: slow-falling sparkles after break ===
            residualSparkles = CreateParticle("ResidualSparkles", 0, residualSparkleTime,
                0.05f, brandGlow, 0.15f, true);
            var rsMain = residualSparkles.main;
            rsMain.startSpeed = new ParticleSystem.MinMaxCurve(0.2f, 0.8f);
            var rsShape = residualSparkles.shape;
            rsShape.shapeType = ParticleSystemShapeType.Sphere;
            rsShape.radius = domeRadius;
            residualSparkles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === INTERIOR LIGHT ===
            var lightGO = new GameObject("InteriorLight");
            lightGO.transform.SetParent(transform, false);
            interiorLight = lightGO.AddComponent<Light>();
            interiorLight.type = LightType.Point;
            interiorLight.color = brandGlow;
            interiorLight.intensity = 0f;
            interiorLight.range = domeRadius * 2f;

            // === ACTIVATION FLASH (bright, brief) ===
            var flashGO = new GameObject("ActivationFlash");
            flashGO.transform.SetParent(transform, false);
            activationFlash = flashGO.AddComponent<Light>();
            activationFlash.type = LightType.Point;
            activationFlash.color = brandGlow;
            activationFlash.intensity = 0f;
            activationFlash.range = domeRadius * 4f;
        }}

        // ---------------------------------------------------------------
        // Phase 1: Activation
        // ---------------------------------------------------------------

        private IEnumerator ActivateSequence()
        {{
            isActive = true;
            OnActivate?.Invoke();

            // Show dome and expand from zero
            domeMesh.SetActive(true);
            domeMesh.transform.localScale = Vector3.zero;

            // Activation flash
            activationFlash.intensity = 8f;

            // Ring burst
            activationRing.Emit(ringParticleCount);

            // Expand dome over activateDuration
            float elapsed = 0f;
            float targetScale = domeRadius * 2f; // diameter
            while (elapsed < activateDuration)
            {{
                float t = elapsed / activateDuration;
                // Ease out cubic for satisfying snap
                float eased = 1f - Mathf.Pow(1f - t, 3f);
                float s = eased * targetScale;
                domeMesh.transform.localScale = Vector3.one * s;

                // Fade flash out
                activationFlash.intensity = Mathf.Lerp(8f, 0f, t);

                elapsed += Time.deltaTime;
                yield return null;
            }}
            domeMesh.transform.localScale = Vector3.one * targetScale;
            activationFlash.intensity = 0f;

            // Begin sustain
            interiorLight.intensity = interiorIntensity;
            surfaceSparkles.Play();
            OnSustainStart?.Invoke();
            sustainRoutine = StartCoroutine(SustainPulse());
        }}

        // ---------------------------------------------------------------
        // Phase 2: Sustain — continuous pulse
        // ---------------------------------------------------------------

        private IEnumerator SustainPulse()
        {{
            while (isActive)
            {{
                // Oscillate dome alpha between pulseMin and pulseMax
                float t = (Mathf.Sin(Time.time * pulseFrequency * Mathf.PI * 2f) + 1f) * 0.5f;
                float alpha = Mathf.Lerp(pulseMinAlpha, pulseMaxAlpha, t);
                Color c = domeMaterial.GetColor("_BaseColor");
                c.a = alpha;
                domeMaterial.SetColor("_BaseColor", c);

                // Interior light subtle pulse
                interiorLight.intensity = Mathf.Lerp(interiorIntensity * 0.8f,
                    interiorIntensity * 1.2f, t);

                yield return null;
            }}
        }}

        // ---------------------------------------------------------------
        // Phase 3: Hit reaction at specific point
        // ---------------------------------------------------------------

        private IEnumerator HitReactionSequence(Vector3 hitPos)
        {{
            OnHitReaction?.Invoke(hitPos);

            // Sparks at hit point on dome surface
            hitSparks.transform.position = hitPos;
            hitSparks.Emit(hitSparkCount);

            // Opacity spike on dome material
            Color c = domeMaterial.GetColor("_BaseColor");
            float origAlpha = c.a;
            c.a = hitAlphaSpike;
            domeMaterial.SetColor("_BaseColor", c);

            // Scale wobble: 1.0 -> 1.05 -> 0.98 -> 1.0 via coroutine
            float targetScale = domeRadius * 2f;
            float wobbleElapsed = 0f;
            while (wobbleElapsed < hitRippleDuration)
            {{
                float t = wobbleElapsed / hitRippleDuration;
                // Damped oscillation for wobble
                float wobble = Mathf.Sin(t * Mathf.PI * 4f) * wobbleIntensity *
                    (1f - t); // decay
                float s = targetScale * (1f + wobble);
                domeMesh.transform.localScale = Vector3.one * s;

                // Fade alpha back
                float alphaT = t;
                c.a = Mathf.Lerp(hitAlphaSpike, origAlpha, alphaT);
                domeMaterial.SetColor("_BaseColor", c);

                wobbleElapsed += Time.deltaTime;
                yield return null;
            }}
            domeMesh.transform.localScale = Vector3.one * targetScale;
            c.a = origAlpha;
            domeMaterial.SetColor("_BaseColor", c);
        }}

        // ---------------------------------------------------------------
        // Phase 4: Break / Shatter
        // ---------------------------------------------------------------

        private IEnumerator BreakSequence()
        {{
            isActive = false;
            OnBreak?.Invoke();

            if (sustainRoutine != null) StopCoroutine(sustainRoutine);
            surfaceSparkles.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            interiorLight.intensity = 0f;

            // Hide dome mesh, emit shatter fragments
            domeMesh.SetActive(false);
            shatterFragments.Emit(shardCount);

            // Bright flash at break moment
            activationFlash.intensity = 12f;

            // Residual slow-falling sparkles
            var resEmission = residualSparkles.emission;
            resEmission.rateOverTime = residualSparkleRate;
            residualSparkles.Play();

            // Fade flash
            float elapsed = 0f;
            while (elapsed < breakDuration)
            {{
                float t = elapsed / breakDuration;
                activationFlash.intensity = Mathf.Lerp(12f, 0f, t);
                elapsed += Time.deltaTime;
                yield return null;
            }}
            activationFlash.intensity = 0f;

            // Let residual sparkles linger
            yield return new WaitForSeconds(residualSparkleTime);
            residualSparkles.Stop(true, ParticleSystemStopBehavior.StopEmitting);

            OnDeactivate?.Invoke();
        }}

        // ---------------------------------------------------------------
        // Factory helper
        // ---------------------------------------------------------------

        private ParticleSystem CreateParticle(string name, float rate,
            float lifetime, float startSize, Color startColor,
            float gravityMod, bool additive)
        {{
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = lifetime;
            main.startSize = startSize;
            main.startColor = startColor;
            main.gravityModifier = gravityMod;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 300;

            var emission = ps.emission;
            emission.rateOverTime = rate;

            var rend = go.GetComponent<ParticleSystemRenderer>();
            rend.material = new Material(
                Shader.Find("Universal Render Pipeline/Particles/Unlit"));
            if (additive)
            {{
                rend.material.SetFloat("_Surface", 1f);
                rend.material.SetFloat("_Blend", 1f);
            }}
            else
            {{
                rend.material.SetFloat("_Surface", 1f);
                rend.material.SetFloat("_Blend", 0f);
            }}
            rend.material.SetColor("_BaseColor", startColor);
            return ps;
        }}

#if UNITY_EDITOR
        [UnityEditor.MenuItem("VeilBreakers/VFX/Skills/Create Shield Dome VFX ({brand})")]
        private static void CreateInScene()
        {{
            var go = new GameObject("{class_name}");
            go.AddComponent<{class_name}>();
            UnityEditor.Selection.activeGameObject = go;
            Debug.Log("[VeilBreakers] Created {class_name}. Call Play() to activate, OnHitReactionAt(pos) for hits, Stop() to break.");
        }}
#endif
    }}
}}
'''

    return {
        "script_path": script_path,
        "script_content": cs.strip(),
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 3. VOID REND SKILL VFX
# ===================================================================

def generate_void_rend_skill_vfx(brand: str = "VOID") -> dict:
    """Generate a complete void/reality-tear skill VFX composition.

    Four phases:
        1. Tear     -- reality crack lines, distortion ripple (0.2s)
        2. Rift     -- dark portal sphere, suction particles, light drain (0.5s)
        3. Pulse    -- damage shockwave, dark tendrils to targets, screen FX (0.1s)
        4. Collapse -- implosion, inverted flash, residual void sparks (0.3s)
    """
    brand = brand.upper()
    if brand not in BRAND_PRIMARY:
        brand = "VOID"
    prim = BRAND_PRIMARY[brand]
    glow = BRAND_GLOW[brand]
    dark = BRAND_DARK[brand]
    safe_brand = sanitize_cs_identifier(brand)

    class_name = f"VoidRendVFX_{safe_brand}"
    script_path = f"Assets/VeilBreakers/Scripts/VFX/Skills/{class_name}.cs"

    cs = f'''using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
#if PRIME_TWEEN
using PrimeTween;
#endif
#if CINEMACHINE
using Unity.Cinemachine;
#endif

namespace VeilBreakers.VFX.Skills
{{
    /// <summary>
    /// Complete void/reality-tear skill VFX for the {brand} brand.
    /// Tears a rift in space: crack lines, dark portal, suction, damage
    /// tendrils, gravitational light drain, implosion collapse.
    /// </summary>
    public class {class_name} : MonoBehaviour
    {{
        // ---------------------------------------------------------------
        // Phase events
        // ---------------------------------------------------------------
        public event Action OnTearStart;
        public event Action OnRiftOpen;
        public event Action OnDamagePulse;
        public event Action OnCollapse;
        public event Action OnComplete;

        // ---------------------------------------------------------------
        // Tuning
        // ---------------------------------------------------------------
        [Header("=== Phase Timing ===")]
        [SerializeField] private float tearDuration     = 0.2f;
        [SerializeField] private float riftDuration     = 0.5f;
        [SerializeField] private float pulseDuration    = 0.1f;
        [SerializeField] private float collapseDuration = 0.3f;

        [Header("=== Tear Crack Lines ===")]
        [SerializeField] private int   crackSegments     = 14;
        [SerializeField] private float crackLength       = 2.5f;
        [SerializeField] private float crackWidthStart   = 0.02f;
        [SerializeField] private float crackWidthEnd     = 0.18f;
        [SerializeField] private float crackAngleDeg     = 35f;

        [Header("=== Rift Portal ===")]
        [SerializeField] private float riftRadius        = 1.2f;
        [SerializeField] private float riftEdgeGlowMult  = 6f;
        [SerializeField] private int   orbitParticleRate  = 40;
        [SerializeField] private float suctionRadius     = 6f;
        [SerializeField] private float suctionForce      = 5f;

        [Header("=== Damage Pulse ===")]
        [SerializeField] private float shockwaveRadius   = 8f;
        [SerializeField] private float shockwaveSpeed    = 20f;
        [SerializeField] private int   tendrilSegments   = 12;
        [SerializeField] private float tendrilJitter     = 0.25f;
        [SerializeField] private float desaturationAmount = 0.6f;
        [SerializeField] private float vignetteSpike     = 0.6f;

        [Header("=== Collapse ===")]
        [SerializeField] private float residualSparkTime = 2f;
        [SerializeField] private int   residualSparkRate = 15;
        [SerializeField] private float groundScarRadius  = 1.5f;

        [Header("=== Light Drain ===")]
        [SerializeField] private float drainLightRange   = 8f;
        [SerializeField] private float drainIntensity    = 2f;

        [Header("=== Brand Colors ===")]
        [SerializeField] private Color brandPrimary = {_c(prim)};
        [SerializeField] private Color brandGlow    = {_c(glow)};
        [SerializeField] private Color brandDark    = {_c(dark)};
        [SerializeField] private Color voidBlack    = new Color(0.01f, 0.005f, 0.02f, 1f);
        [SerializeField] private Color edgeGlowHDR  = {_c(glow, 6.0)};

        // ---------------------------------------------------------------
        // Runtime refs
        // ---------------------------------------------------------------
        private LineRenderer        crackLeft;
        private LineRenderer        crackRight;
        private GameObject          riftCoreSphere;     // inner darkness
        private GameObject          riftEdgeSphere;     // edge glow shell
        private Material            riftCoreMat;
        private Material            riftEdgeMat;
        private ParticleSystem      orbitParticles;     // void fragments orbiting inward
        private ParticleSystem      suctionDust;        // debris pulled toward rift
        private ParticleSystem      shockwaveRing;      // expanding dark ring
        private ParticleSystem      residualSparks;
        private List<LineRenderer>  tendrils = new List<LineRenderer>();
        private Light               drainLight;         // negative-apparent light (dark area)
        private Light               edgePulseLight;     // glow at rift edge
        private GameObject          groundScar;
        private Volume              postVolume;
        private ColorAdjustments    colorAdj;
        private Vignette            vignette;
        private Coroutine           activeRoutine;

        // ---------------------------------------------------------------
        // Public API
        // ---------------------------------------------------------------

        /// <summary>Tear reality at the specified world position.</summary>
        public void Play(Vector3 riftPosition)
        {{
            transform.position = riftPosition;
            if (activeRoutine != null) StopCoroutine(activeRoutine);
            activeRoutine = StartCoroutine(FullSequence());
        }}

        /// <summary>Force-cancel the entire effect.</summary>
        public void Stop()
        {{
            if (activeRoutine != null) {{ StopCoroutine(activeRoutine); activeRoutine = null; }}
            CleanupAll();
        }}

        // ---------------------------------------------------------------
        // Lifecycle
        // ---------------------------------------------------------------

        private void Awake()
        {{
            Setup();
        }}

        private void OnDestroy()
        {{
            if (riftCoreMat != null) Destroy(riftCoreMat);
            if (riftEdgeMat != null) Destroy(riftEdgeMat);
        }}

        // ---------------------------------------------------------------
        // Setup
        // ---------------------------------------------------------------

        private void Setup()
        {{
            // === TEAR: two LineRenderers forming a V-slash ===
            crackLeft  = CreateLineChild("CrackLeft", crackSegments, crackWidthStart, edgeGlowHDR, 1f);
            crackRight = CreateLineChild("CrackRight", crackSegments, crackWidthStart, edgeGlowHDR, 1f);
            crackLeft.enabled = false;
            crackRight.enabled = false;

            // === RIFT: inner darkness sphere (pure black, zero emission) ===
            riftCoreSphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            riftCoreSphere.name = "RiftCore";
            riftCoreSphere.transform.SetParent(transform, false);
            riftCoreSphere.transform.localScale = Vector3.zero;
            Destroy(riftCoreSphere.GetComponent<Collider>());
            riftCoreMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            riftCoreMat.SetColor("_BaseColor", voidBlack);
            // Render in front of edge sphere
            riftCoreMat.renderQueue = 3001;
            riftCoreSphere.GetComponent<Renderer>().material = riftCoreMat;
            riftCoreSphere.SetActive(false);

            // === RIFT: edge glow shell (slightly larger, transparent, HDR emission) ===
            riftEdgeSphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            riftEdgeSphere.name = "RiftEdge";
            riftEdgeSphere.transform.SetParent(transform, false);
            riftEdgeSphere.transform.localScale = Vector3.zero;
            Destroy(riftEdgeSphere.GetComponent<Collider>());
            riftEdgeMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            riftEdgeMat.SetFloat("_Surface", 1f);
            riftEdgeMat.SetOverrideTag("RenderType", "Transparent");
            riftEdgeMat.renderQueue = 3000;
            riftEdgeMat.SetFloat("_ZWrite", 0f);
            riftEdgeMat.SetFloat("_Cull", 0f); // double-sided
            Color edgeBase = brandGlow;
            edgeBase.a = 0.3f;
            riftEdgeMat.SetColor("_BaseColor", edgeBase);
            riftEdgeMat.EnableKeyword("_EMISSION");
            riftEdgeMat.SetColor("_EmissionColor", edgeGlowHDR);
            riftEdgeMat.SetFloat("_Smoothness", 0.9f);
            riftEdgeSphere.GetComponent<Renderer>().material = riftEdgeMat;
            riftEdgeSphere.SetActive(false);

            // === RIFT: orbiting void fragments (sucked inward) ===
            orbitParticles = CreateParticleChild("OrbitFragments", orbitParticleRate,
                1.5f, 0.1f, brandDark, 0f, false);
            var opShape = orbitParticles.shape;
            opShape.shapeType = ParticleSystemShapeType.Sphere;
            opShape.radius = riftRadius * 1.5f;
            var opVel = orbitParticles.velocityOverLifetime;
            opVel.enabled = true;
            opVel.radial = -2f;     // pulled inward
            opVel.orbitalY = 3f;    // spinning orbit
            // Size over lifetime: shrink as they approach center
            var opSol = orbitParticles.sizeOverLifetime;
            opSol.enabled = true;
            opSol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(
                new Keyframe(0f, 1f), new Keyframe(1f, 0.1f)));
            orbitParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === RIFT: suction dust from environment ===
            suctionDust = CreateParticleChild("SuctionDust", 0, 0.8f, 0.04f,
                new Color(0.4f, 0.35f, 0.3f, 0.5f), 0f, false);
            var sdShape = suctionDust.shape;
            sdShape.shapeType = ParticleSystemShapeType.Sphere;
            sdShape.radius = suctionRadius;
            var sdVel = suctionDust.velocityOverLifetime;
            sdVel.enabled = true;
            sdVel.radial = -suctionForce; // pulled toward center
            suctionDust.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === PULSE: expanding dark shockwave ring ===
            shockwaveRing = CreateParticleChild("ShockwaveRing", 0, 0.3f, 0.3f,
                brandDark, 0f, false);
            var swShape = shockwaveRing.shape;
            swShape.shapeType = ParticleSystemShapeType.Circle;
            swShape.radius = 0.5f;
            var swMain = shockwaveRing.main;
            swMain.startSpeed = shockwaveSpeed;
            shockwaveRing.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === PULSE: dark tendrils to targets (LineRenderers) ===
            for (int i = 0; i < 5; i++)
            {{
                var t = CreateLineChild($"Tendril_{{i}}", tendrilSegments, 0.06f,
                    brandGlow, 0.8f);
                t.enabled = false;
                tendrils.Add(t);
            }}

            // === RESIDUAL: floating void sparks ===
            residualSparks = CreateParticleChild("ResidualSparks", 0, residualSparkTime,
                0.04f, brandGlow, -0.1f, true);
            var rsShape = residualSparks.shape;
            rsShape.shapeType = ParticleSystemShapeType.Sphere;
            rsShape.radius = riftRadius;
            residualSparks.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            // === LIGHT DRAIN: dark-tinted point light to suppress local brightness ===
            var drainGO = new GameObject("DrainLight");
            drainGO.transform.SetParent(transform, false);
            drainLight = drainGO.AddComponent<Light>();
            drainLight.type = LightType.Point;
            // Dark purple tint with low intensity — creates "light absorbed" feel
            drainLight.color = brandDark;
            drainLight.intensity = 0f;
            drainLight.range = drainLightRange;

            // === EDGE PULSE LIGHT ===
            var edgeGO = new GameObject("EdgePulseLight");
            edgeGO.transform.SetParent(transform, false);
            edgePulseLight = edgeGO.AddComponent<Light>();
            edgePulseLight.type = LightType.Point;
            edgePulseLight.color = brandGlow;
            edgePulseLight.intensity = 0f;
            edgePulseLight.range = riftRadius * 3f;

            // === GROUND SCAR: dark mark on ground ===
            groundScar = GameObject.CreatePrimitive(PrimitiveType.Quad);
            groundScar.name = "GroundScar";
            groundScar.transform.SetParent(transform, false);
            groundScar.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            groundScar.transform.localPosition = Vector3.up * 0.02f;
            groundScar.transform.localScale = Vector3.one * groundScarRadius;
            Destroy(groundScar.GetComponent<Collider>());
            var scarRend = groundScar.GetComponent<Renderer>();
            var scarMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            scarMat.SetColor("_BaseColor", new Color(0.03f, 0.01f, 0.05f, 0.9f));
            scarMat.SetFloat("_Surface", 1f);
            scarMat.renderQueue = 2501;
            scarRend.material = scarMat;
            groundScar.SetActive(false);

            // === POST-PROCESSING volume (desaturation + vignette) ===
            var volGO = new GameObject("VoidPostFX");
            volGO.transform.SetParent(transform, false);
            postVolume = volGO.AddComponent<Volume>();
            postVolume.isGlobal = true;
            postVolume.weight = 0f;
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            colorAdj = profile.Add<ColorAdjustments>(false);
            colorAdj.saturation.Override(-desaturationAmount * 100f);
            vignette = profile.Add<Vignette>(false);
            vignette.intensity.Override(vignetteSpike);
            postVolume.profile = profile;
        }}

        // ---------------------------------------------------------------
        // Full choreography
        // ---------------------------------------------------------------

        private IEnumerator FullSequence()
        {{
            // ====== PHASE 1: TEAR — crack lines rip open ======
            OnTearStart?.Invoke();
            crackLeft.enabled = true;
            crackRight.enabled = true;

            float tearElapsed = 0f;
            while (tearElapsed < tearDuration)
            {{
                float t = tearElapsed / tearDuration;
                // Cracks widen over time: width goes from thin start to thick end
                float w = Mathf.Lerp(crackWidthStart, crackWidthEnd, t);
                crackLeft.startWidth = w;
                crackLeft.endWidth = w * 0.3f;
                crackRight.startWidth = w;
                crackRight.endWidth = w * 0.3f;

                // Generate V-shape crack geometry expanding outward
                float len = crackLength * t;
                float angle = crackAngleDeg * Mathf.Deg2Rad;
                Vector3 center = transform.position;
                Vector3 leftDir  = (Vector3.up + Vector3.left * Mathf.Sin(angle)).normalized;
                Vector3 rightDir = (Vector3.up + Vector3.right * Mathf.Sin(angle)).normalized;
                GenerateCrackPath(crackLeft, center, center + leftDir * len, crackSegments);
                GenerateCrackPath(crackRight, center, center + rightDir * len, crackSegments);

                tearElapsed += Time.deltaTime;
                yield return null;
            }}

            // ====== PHASE 2: RIFT OPEN — dark sphere, orbiting fragments, suction ======
            OnRiftOpen?.Invoke();

            riftCoreSphere.SetActive(true);
            riftEdgeSphere.SetActive(true);
            orbitParticles.Play();

            // Suction dust (80 particles per second during rift)
            var sdEmission = suctionDust.emission;
            sdEmission.rateOverTime = 80;
            suctionDust.Play();

            // Edge pulse light
            edgePulseLight.intensity = riftEdgeGlowMult;

            // Drain light: starts dimming the surroundings
            drainLight.intensity = drainIntensity;

            // Expand rift spheres over first half of rift duration
            float riftExpandTime = riftDuration * 0.4f;
            float riftElapsed = 0f;
            float coreScale = riftRadius * 2f;
            float edgeScale = riftRadius * 2.3f;
            while (riftElapsed < riftExpandTime)
            {{
                float t = riftElapsed / riftExpandTime;
                float eased = 1f - Mathf.Pow(1f - t, 2f);
                riftCoreSphere.transform.localScale = Vector3.one * coreScale * eased;
                riftEdgeSphere.transform.localScale = Vector3.one * edgeScale * eased;
                riftElapsed += Time.deltaTime;
                yield return null;
            }}
            riftCoreSphere.transform.localScale = Vector3.one * coreScale;
            riftEdgeSphere.transform.localScale = Vector3.one * edgeScale;

            // Sustain rift for remaining time with pulsing edge glow
            float sustainTime = riftDuration - riftExpandTime;
            float sustainElapsed = 0f;
            while (sustainElapsed < sustainTime)
            {{
                float t = sustainElapsed / sustainTime;
                // Pulsing edge emission
                float pulse = 1f + Mathf.Sin(Time.time * 8f) * 0.3f;
                edgePulseLight.intensity = riftEdgeGlowMult * pulse;
                Color edgeEmit = edgeGlowHDR * pulse;
                riftEdgeMat.SetColor("_EmissionColor", edgeEmit);

                // Cracks flicker during rift
                crackLeft.startWidth = crackWidthEnd * UnityEngine.Random.Range(0.7f, 1.3f);
                crackRight.startWidth = crackWidthEnd * UnityEngine.Random.Range(0.7f, 1.3f);

                sustainElapsed += Time.deltaTime;
                yield return null;
            }}

            // ====== PHASE 3: DAMAGE PULSE — shockwave, tendrils, screen FX ======
            OnDamagePulse?.Invoke();

            // Dark shockwave ring
            shockwaveRing.transform.position = transform.position;
            shockwaveRing.Emit(40);

            // Tendrils reaching from rift to nearby enemies
            Collider[] nearby = Physics.OverlapSphere(transform.position, shockwaveRadius);
            int tendrilIdx = 0;
            foreach (var col in nearby)
            {{
                if (tendrilIdx >= tendrils.Count) break;
                if (col.CompareTag("Enemy") || col.GetComponentInParent<MonoBehaviour>() != null)
                {{
                    if (col.transform == transform) continue;
                    tendrils[tendrilIdx].enabled = true;
                    Vector3 targetPos = col.transform.position + Vector3.up * 1f;
                    GenerateTendrilPath(tendrils[tendrilIdx], transform.position, targetPos);
                    tendrilIdx++;
                }}
            }}

            // Screen effects: desaturation + vignette spike
            postVolume.weight = 1f;

            // Camera shake
#if CINEMACHINE
            var impulse = FindAnyObjectByType<CinemachineImpulseSource>();
            if (impulse != null) impulse.GenerateImpulse(0.4f);
#endif

            yield return new WaitForSeconds(pulseDuration);

            // Disable tendrils and fade screen FX
            foreach (var t in tendrils) t.enabled = false;

#if PRIME_TWEEN
            Tween.Custom(postVolume, 1f, 0f, 0.3f, (vol, val) => vol.weight = val);
#else
            yield return StartCoroutine(FadePostVolume(0.3f));
#endif

            // ====== PHASE 4: COLLAPSE — implosion, inverted flash, residual ======
            OnCollapse?.Invoke();

            // Reverse suction: all particles pulled back to center
            suctionDust.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            orbitParticles.Stop(true, ParticleSystemStopBehavior.StopEmitting);

            // Cracks disappear
            crackLeft.enabled = false;
            crackRight.enabled = false;

            // Implode rift spheres to zero
            float collapseElapsed = 0f;
            float startCore = coreScale;
            float startEdge = edgeScale;
            while (collapseElapsed < collapseDuration)
            {{
                float t = collapseElapsed / collapseDuration;
                // Accelerating collapse (ease in)
                float eased = t * t;
                riftCoreSphere.transform.localScale = Vector3.one * Mathf.Lerp(startCore, 0f, eased);
                riftEdgeSphere.transform.localScale = Vector3.one * Mathf.Lerp(startEdge, 0f, eased);

                // Edge glow intensifies during collapse then snaps off
                edgePulseLight.intensity = Mathf.Lerp(riftEdgeGlowMult, riftEdgeGlowMult * 3f, eased);
                drainLight.intensity = Mathf.Lerp(drainIntensity, 0f, eased);

                collapseElapsed += Time.deltaTime;
                yield return null;
            }}

            // SNAP — everything off at once for dramatic punctuation
            riftCoreSphere.SetActive(false);
            riftEdgeSphere.SetActive(false);
            edgePulseLight.intensity = 0f;
            drainLight.intensity = 0f;

            // Ground scar at rift location
            groundScar.SetActive(true);

            // Residual void sparks dissipating over time
            var rsEmission = residualSparks.emission;
            rsEmission.rateOverTime = residualSparkRate;
            residualSparks.Play();

            yield return new WaitForSeconds(residualSparkTime);
            residualSparks.Stop(true, ParticleSystemStopBehavior.StopEmitting);

            // Fade ground scar
            yield return StartCoroutine(FadeGroundScar(2f));

            OnComplete?.Invoke();
            activeRoutine = null;
        }}

        // ---------------------------------------------------------------
        // Crack / tendril path generation
        // ---------------------------------------------------------------

        /// <summary>
        /// Generate a jagged crack line between two points. Like lightning but
        /// with smaller displacement — looks like a fracture in reality.
        /// </summary>
        private void GenerateCrackPath(LineRenderer lr, Vector3 start, Vector3 end,
            int segments)
        {{
            lr.positionCount = segments;
            Vector3 dir = (end - start).normalized;
            Vector3 perp = Vector3.Cross(dir, Vector3.forward).normalized;
            if (perp.sqrMagnitude < 0.001f)
                perp = Vector3.Cross(dir, Vector3.right).normalized;

            for (int i = 0; i < segments; i++)
            {{
                float t = (float)i / (segments - 1);
                Vector3 basePos = Vector3.Lerp(start, end, t);
                float envelope = Mathf.Sin(t * Mathf.PI);
                float dx = envelope * UnityEngine.Random.Range(-0.15f, 0.15f);
                lr.SetPosition(i, basePos + perp * dx);
            }}
        }}

        /// <summary>
        /// Generate jagged dark tendril from rift center to a target.
        /// More organic and erratic than lightning — irregular displacements.
        /// </summary>
        private void GenerateTendrilPath(LineRenderer lr, Vector3 start, Vector3 end)
        {{
            lr.positionCount = tendrilSegments;
            Vector3 dir = (end - start).normalized;
            Vector3 perp = Vector3.Cross(dir, Vector3.up).normalized;
            if (perp.sqrMagnitude < 0.001f)
                perp = Vector3.Cross(dir, Vector3.right).normalized;
            Vector3 perpY = Vector3.Cross(dir, perp).normalized;

            for (int i = 0; i < tendrilSegments; i++)
            {{
                float t = (float)i / (tendrilSegments - 1);
                Vector3 basePos = Vector3.Lerp(start, end, t);
                // Irregular displacement: not sine-enveloped, just random with slight bias
                float dx = UnityEngine.Random.Range(-tendrilJitter, tendrilJitter);
                float dy = UnityEngine.Random.Range(-tendrilJitter * 0.5f, tendrilJitter * 0.5f);
                // Taper displacement at endpoints
                float taper = Mathf.Clamp01(Mathf.Min(t * 4f, (1f - t) * 4f));
                lr.SetPosition(i, basePos + perp * dx * taper + perpY * dy * taper);
            }}
        }}

        // ---------------------------------------------------------------
        // Utility
        // ---------------------------------------------------------------

        private IEnumerator FadePostVolume(float duration)
        {{
            float elapsed = 0f;
            while (elapsed < duration)
            {{
                postVolume.weight = Mathf.Lerp(1f, 0f, elapsed / duration);
                elapsed += Time.deltaTime;
                yield return null;
            }}
            postVolume.weight = 0f;
        }}

        private IEnumerator FadeGroundScar(float duration)
        {{
            if (!groundScar.activeSelf) yield break;
            var rend = groundScar.GetComponent<Renderer>();
            Color c = rend.material.GetColor("_BaseColor");
            float startAlpha = c.a;
            float elapsed = 0f;
            while (elapsed < duration)
            {{
                c.a = Mathf.Lerp(startAlpha, 0f, elapsed / duration);
                rend.material.SetColor("_BaseColor", c);
                elapsed += Time.deltaTime;
                yield return null;
            }}
            groundScar.SetActive(false);
            c.a = startAlpha;
            rend.material.SetColor("_BaseColor", c);
        }}

        private void CleanupAll()
        {{
            if (crackLeft != null) crackLeft.enabled = false;
            if (crackRight != null) crackRight.enabled = false;
            if (riftCoreSphere != null) riftCoreSphere.SetActive(false);
            if (riftEdgeSphere != null) riftEdgeSphere.SetActive(false);
            if (orbitParticles != null) orbitParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (suctionDust != null) suctionDust.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (shockwaveRing != null) shockwaveRing.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (residualSparks != null) residualSparks.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            foreach (var t in tendrils) {{ if (t != null) t.enabled = false; }}
            if (drainLight != null) drainLight.intensity = 0f;
            if (edgePulseLight != null) edgePulseLight.intensity = 0f;
            if (groundScar != null) groundScar.SetActive(false);
            if (postVolume != null) postVolume.weight = 0f;
        }}

        // ---------------------------------------------------------------
        // Factory helpers
        // ---------------------------------------------------------------

        private ParticleSystem CreateParticleChild(string name, float rate,
            float lifetime, float startSize, Color startColor,
            float gravityMod, bool additive)
        {{
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = lifetime;
            main.startSize = startSize;
            main.startColor = startColor;
            main.gravityModifier = gravityMod;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 400;

            var emission = ps.emission;
            emission.rateOverTime = rate;

            var rend = go.GetComponent<ParticleSystemRenderer>();
            rend.material = new Material(
                Shader.Find("Universal Render Pipeline/Particles/Unlit"));
            if (additive)
            {{
                rend.material.SetFloat("_Surface", 1f);
                rend.material.SetFloat("_Blend", 1f);
            }}
            else
            {{
                rend.material.SetFloat("_Surface", 1f);
                rend.material.SetFloat("_Blend", 0f);
            }}
            rend.material.SetColor("_BaseColor", startColor);
            return ps;
        }}

        private LineRenderer CreateLineChild(string name, int segments,
            float width, Color color, float alpha)
        {{
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = segments;
            lr.startWidth = width;
            lr.endWidth = width * 0.4f;
            lr.numCapVertices = 3;
            lr.numCornerVertices = 3;
            lr.useWorldSpace = true;

            var mat = new Material(
                Shader.Find("Universal Render Pipeline/Particles/Unlit"));
            mat.SetFloat("_Surface", 1f);
            mat.SetFloat("_Blend", 1f); // Additive for glow
            Color c = color;
            c.a = alpha;
            mat.SetColor("_BaseColor", c);
            mat.SetColor("_EmissionColor", c);
            lr.material = mat;
            return lr;
        }}

#if UNITY_EDITOR
        [UnityEditor.MenuItem("VeilBreakers/VFX/Skills/Create Void Rend VFX ({brand})")]
        private static void CreateInScene()
        {{
            var go = new GameObject("{class_name}");
            go.AddComponent<{class_name}>();
            UnityEditor.Selection.activeGameObject = go;
            Debug.Log("[VeilBreakers] Created {class_name}. Call Play(position) to tear reality.");
        }}
#endif
    }}
}}
'''

    return {
        "script_path": script_path,
        "script_content": cs.strip(),
        "next_steps": STANDARD_NEXT_STEPS,
    }
