"""VFX-Animation Bridge C# template generators for Unity.

Bridges Terminal 2's animation event system with Terminal 3's VFX system.
The generated MonoBehaviour listens for AnimationEvents fired by T2's
animations and spawns the correct T3 VFX at the right bone socket with
proper timing.

Each function returns a dict with ``script_path``, ``script_content``, and
``next_steps``.  Generated C# uses ParticleSystem + PrimeTween + C# events
and targets Unity 2022.3+ URP.

Exports:
    generate_vfx_animation_bridge_script  -- VFXAnimationBridge MonoBehaviour
    generate_vfx_socket_setup_script      -- Editor auto-wiring of bone sockets
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Brand colors -- defined locally to avoid race-condition imports
# ---------------------------------------------------------------------------

BRAND_COLORS: dict[str, list[float]] = {
    "IRON":   [0.55, 0.35, 0.22, 1.0],
    "SAVAGE": [0.71, 0.18, 0.18, 1.0],
    "SURGE":  [0.24, 0.55, 0.86, 1.0],
    "VENOM":  [0.31, 0.71, 0.24, 1.0],
    "DREAD":  [0.24, 0.47, 0.27, 1.0],
    "LEECH":  [0.55, 0.53, 0.20, 1.0],
    "GRACE":  [0.86, 0.86, 0.94, 1.0],
    "MEND":   [0.78, 0.67, 0.31, 1.0],
    "RUIN":   [0.86, 0.47, 0.16, 1.0],
    "VOID":   [0.16, 0.08, 0.24, 1.0],
}

BRAND_GLOW_COLORS: dict[str, list[float]] = {
    "IRON":   [0.80, 0.55, 0.30, 1.0],
    "SAVAGE": [0.86, 0.27, 0.27, 1.0],
    "SURGE":  [0.39, 0.71, 1.00, 1.0],
    "VENOM":  [0.47, 0.86, 0.39, 1.0],
    "DREAD":  [0.35, 0.70, 0.40, 1.0],
    "LEECH":  [0.70, 0.65, 0.25, 1.0],
    "GRACE":  [1.00, 1.00, 1.00, 1.0],
    "MEND":   [0.94, 0.82, 0.47, 1.0],
    "RUIN":   [1.00, 0.63, 0.31, 1.0],
    "VOID":   [0.39, 0.24, 0.55, 1.0],
}

ALL_BRANDS = list(BRAND_COLORS.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]

# ---------------------------------------------------------------------------
# T2 brand VFX param mapping (impact type prefix -> brand)
# ---------------------------------------------------------------------------

IMPACT_PREFIX_TO_BRAND: dict[str, str] = {
    "metallic":    "IRON",
    "blood":       "SAVAGE",
    "electric":    "SURGE",
    "poison":      "VENOM",
    "shadow":      "DREAD",
    "drain":       "LEECH",
    "holy":        "GRACE",
    "heal":        "MEND",
    "explosion":   "RUIN",
    "distortion":  "VOID",
}

# T2 brand trail types
BRAND_TRAIL_TYPES: dict[str, str] = {
    "IRON":   "sparks",
    "SAVAGE": "claw_marks",
    "SURGE":  "lightning",
    "VENOM":  "acid_drip",
    "DREAD":  "dark_mist",
    "LEECH":  "blood_tendrils",
    "GRACE":  "light_ribbons",
    "MEND":   "soft_glow",
    "RUIN":   "fire",
    "VOID":   "void_tears",
}

# Impact type prefix -> default T3 melee skill VFX names
IMPACT_TO_SKILL_MAP: dict[str, list[str]] = {
    "metallic":    ["phantom_cleave", "bonecrusher_slam"],
    "blood":       ["savage_frenzy", "crimson_crescent"],
    "electric":    ["thunderstrike_blade"],
    "poison":      ["venom_fang_strike"],
    "shadow":      ["shadow_step_strike", "abyssal_rend"],
    "drain":       ["bloodletting_strike", "soul_reaver_slash"],
    "holy":        ["moonlight_slash"],
    "heal":        ["restorative_bloom"],
    "explosion":   ["inferno_uppercut"],
    "distortion":  ["dimensional_slash"],
}

# T2 combat timing data (frame-based)
COMBAT_TIMING: dict[str, dict[str, int]] = {
    "light_attack":    {"vfx_frame": 6,  "hit_frame": 7,  "hitstop": 2},
    "heavy_attack":    {"vfx_frame": 12, "hit_frame": 14, "hitstop": 4},
    "charged_attack":  {"vfx_frame": 18, "hit_frame": 20, "hitstop": 6},
    "combo_finisher":  {"vfx_frame": 15, "hit_frame": 18, "hitstop": 5},
}

# T2 bone socket names
BONE_SOCKETS: list[str] = [
    "weapon_hand_R", "weapon_hand_L", "shield_hand_L",
    "spell_hand_R", "spell_hand_L",
    "head", "chest", "back_weapon",
    "hip_L", "hip_R",
]

# Blender DEF- bone -> socket field mapping
BLENDER_BONE_TO_SOCKET: dict[str, str] = {
    "DEF-hand.R":       "weaponHandR",
    "DEF-hand.L":       "weaponHandL",
    "DEF-forearm.L":    "shieldHandL",
    "DEF-hand.R.001":   "spellHandR",
    "DEF-hand.L.001":   "spellHandL",
    "DEF-spine.005":    "headSocket",
    "DEF-spine.003":    "chestSocket",
    "DEF-spine.002":    "backWeaponSocket",
    "DEF-thigh.L":      "hipL",
    "DEF-thigh.R":      "hipR",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_color(rgba: list[float]) -> str:
    """Format RGBA list as C# ``new Color(r, g, b, a)``."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _brand_colors_cs_dict(var_name: str, colors: dict[str, list[float]]) -> str:
    """Build a C# Dictionary<string, Color> initializer for all brands."""
    lines = [
        f"        private static readonly Dictionary<string, Color> {var_name} = new Dictionary<string, Color>"
    ]
    lines.append("        {")
    for brand, rgba in colors.items():
        lines.append(f'            {{ "{brand}", {_fmt_color(rgba)} }},')
    lines.append("        };")
    return "\n".join(lines)


def _impact_map_cs_dict() -> str:
    """Build C# Dictionary<string, string[]> for impact prefix -> skill names."""
    lines = [
        "        private static readonly Dictionary<string, string[]> ImpactToSkillMap = new Dictionary<string, string[]>"
    ]
    lines.append("        {")
    for prefix, skills in IMPACT_TO_SKILL_MAP.items():
        skill_arr = ", ".join(f'"{s}"' for s in skills)
        lines.append(f'            {{ "{prefix}", new string[] {{ {skill_arr} }} }},')
    lines.append("        };")
    return "\n".join(lines)


def _impact_to_brand_cs_dict() -> str:
    """Build C# Dictionary<string, string> for impact prefix -> brand."""
    lines = [
        "        private static readonly Dictionary<string, string> ImpactToBrand = new Dictionary<string, string>"
    ]
    lines.append("        {")
    for prefix, brand in IMPACT_PREFIX_TO_BRAND.items():
        lines.append(f'            {{ "{prefix}", "{brand}" }},')
    lines.append("        };")
    return "\n".join(lines)


def _brand_trail_cs_dict() -> str:
    """Build C# Dictionary<string, string> for brand -> trail type."""
    lines = [
        "        private static readonly Dictionary<string, string> BrandTrailType = new Dictionary<string, string>"
    ]
    lines.append("        {")
    for brand, trail in BRAND_TRAIL_TYPES.items():
        lines.append(f'            {{ "{brand}", "{trail}" }},')
    lines.append("        };")
    return "\n".join(lines)


def _combat_timing_cs_dict() -> str:
    """Build C# Dictionary<string, CombatTiming> initializer."""
    lines = [
        "        private static readonly Dictionary<string, CombatTiming> CombatTimingData = new Dictionary<string, CombatTiming>"
    ]
    lines.append("        {")
    for attack, data in COMBAT_TIMING.items():
        lines.append(
            f'            {{ "{attack}", new CombatTiming({data["vfx_frame"]}, {data["hit_frame"]}, {data["hitstop"]}) }},'
        )
    lines.append("        };")
    return "\n".join(lines)


# ===================================================================
# 1. generate_vfx_animation_bridge_script
# ===================================================================


def generate_vfx_animation_bridge_script() -> dict[str, Any]:
    """Generate VFXAnimationBridge MonoBehaviour.

    Bridges T2's AnimationEvent system to T3's VFX system.  Receives all
    five T2 animation event handlers (OnAnimVFXSpawn, OnAnimHit,
    OnAnimCameraShake, OnAnimHitstop, OnAnimFootstep) and maps them to
    T3's VFX controllers with proper bone socket attachment, timing
    alignment, and brand-aware color selection.

    Returns:
        Dict with script_path, script_content, next_steps.
    """

    brand_primary_dict = _brand_colors_cs_dict("BrandPrimaryColors", BRAND_COLORS)
    brand_glow_dict = _brand_colors_cs_dict("BrandGlowColors", BRAND_GLOW_COLORS)
    impact_map_dict = _impact_map_cs_dict()
    impact_brand_dict = _impact_to_brand_cs_dict()
    trail_dict = _brand_trail_cs_dict()
    timing_dict = _combat_timing_cs_dict()

    script = f'''using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
#if PRIME_TWEEN
using PrimeTween;
#endif
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace VeilBreakers.VFX
{{
    /// <summary>
    /// Bridges Terminal 2's AnimationEvent system with Terminal 3's VFX system.
    /// Attach to any character with an Animator. Receives animation events fired
    /// by T2's combat/locomotion animations and spawns the correct VFX at the
    /// proper bone socket with brand-aware color selection.
    /// </summary>
    [RequireComponent(typeof(Animator))]
    public class VFXAnimationBridge : MonoBehaviour
    {{
        // =================================================================
        // Serialized fields
        // =================================================================

        [Header("Brand Configuration")]
        [Tooltip("Current combat brand — determines VFX color/style")]
        [SerializeField] private string currentBrand = "IRON";

        [Header("Bone Socket References")]
        [SerializeField] private Transform weaponHandR;
        [SerializeField] private Transform weaponHandL;
        [SerializeField] private Transform shieldHandL;
        [SerializeField] private Transform spellHandR;
        [SerializeField] private Transform spellHandL;
        [SerializeField] private Transform headSocket;
        [SerializeField] private Transform chestSocket;
        [SerializeField] private Transform backWeaponSocket;
        [SerializeField] private Transform hipL;
        [SerializeField] private Transform hipR;

        [Header("VFX Prefab References")]
        [Tooltip("Pool of impact burst particle systems — keyed by brand")]
        [SerializeField] private ParticleSystem impactVFXPrefab;
        [Tooltip("Pool of trail particle systems — keyed by brand")]
        [SerializeField] private ParticleSystem trailVFXPrefab;
        [Tooltip("Footstep dust/splash particle system")]
        [SerializeField] private ParticleSystem footstepVFXPrefab;

        [Header("Camera Shake")]
        [Tooltip("Cinemachine impulse source for screen shake (optional)")]
        [SerializeField] private Component cinemachineImpulseSource;

        [Header("Timing")]
        [Tooltip("Assumed animation framerate for frame-to-seconds conversion")]
        [SerializeField] private float animationFPS = 30f;

        [Header("Debug")]
        [SerializeField] private bool debugLogging = false;

        // =================================================================
        // Events for external game systems
        // =================================================================

        /// <summary>Fired when a VFX is spawned. Args: vfxName, worldPosition.</summary>
        public event Action<string, Vector3> OnVFXSpawned;

        /// <summary>Fired when hitstop is triggered. Args: attackType, durationSeconds.</summary>
        public event Action<string, float> OnHitstopTriggered;

        /// <summary>Fired when camera shake is triggered. Args: impactType, intensity.</summary>
        public event Action<string, float> OnCameraShakeTriggered;

        // =================================================================
        // Brand color data
        // =================================================================

{brand_primary_dict}

{brand_glow_dict}

        // =================================================================
        // Impact type -> T3 skill VFX mapping
        // =================================================================

{impact_map_dict}

{impact_brand_dict}

{trail_dict}

        // =================================================================
        // Combat timing data (frame-based from T2)
        // =================================================================

        [Serializable]
        private struct CombatTiming
        {{
            public int vfxFrame;
            public int hitFrame;
            public int hitstopFrames;

            public CombatTiming(int vfx, int hit, int hitstop)
            {{
                vfxFrame = vfx;
                hitFrame = hit;
                hitstopFrames = hitstop;
            }}

            public float VfxTime(float fps) => vfxFrame / fps;
            public float HitTime(float fps) => hitFrame / fps;
            public float HitstopDuration(float fps) => hitstopFrames / fps;
        }}

{timing_dict}

        // =================================================================
        // Socket lookup
        // =================================================================

        private Dictionary<string, Transform> _socketLookup;
        private Animator _animator;

        // Active trail coroutine tracking
        private Coroutine _activeTrailCoroutine;
        private ParticleSystem _activeTrailInstance;

        private void Awake()
        {{
            _animator = GetComponent<Animator>();
            BuildSocketLookup();
        }}

        private void BuildSocketLookup()
        {{
            _socketLookup = new Dictionary<string, Transform>(StringComparer.OrdinalIgnoreCase)
            {{
                {{ "weapon_hand_R", weaponHandR }},
                {{ "weapon_hand_L", weaponHandL }},
                {{ "shield_hand_L", shieldHandL }},
                {{ "spell_hand_R",  spellHandR }},
                {{ "spell_hand_L",  spellHandL }},
                {{ "head",          headSocket }},
                {{ "chest",         chestSocket }},
                {{ "back_weapon",   backWeaponSocket }},
                {{ "hip_L",         hipL }},
                {{ "hip_R",         hipR }},
            }};
        }}

        /// <summary>Get socket transform by name, falls back to this.transform.</summary>
        private Transform GetSocket(string socketName)
        {{
            if (!string.IsNullOrEmpty(socketName) &&
                _socketLookup.TryGetValue(socketName, out var t) && t != null)
            {{
                return t;
            }}
            return transform;
        }}

        // =================================================================
        // Brand helpers
        // =================================================================

        /// <summary>Set the active brand (called by combat system).</summary>
        public void SetBrand(string brand)
        {{
            if (!string.IsNullOrEmpty(brand))
            {{
                currentBrand = brand.ToUpperInvariant();
                if (debugLogging) Debug.Log($"[VFXAnimBridge] Brand set to {{currentBrand}}");
            }}
        }}

        public string GetCurrentBrand() => currentBrand;

        private Color GetBrandPrimary()
        {{
            return BrandPrimaryColors.TryGetValue(currentBrand, out var c) ? c : Color.white;
        }}

        private Color GetBrandGlow()
        {{
            return BrandGlowColors.TryGetValue(currentBrand, out var c) ? c : Color.white;
        }}

        /// <summary>Resolve impact type prefix to brand name.</summary>
        private string ResolveBrandFromImpact(string impactType)
        {{
            if (string.IsNullOrEmpty(impactType)) return currentBrand;
            // Extract prefix before underscore: "metallic_light" -> "metallic"
            string prefix = impactType;
            int idx = impactType.IndexOf('_');
            if (idx > 0) prefix = impactType.Substring(0, idx);
            return ImpactToBrand.TryGetValue(prefix, out var brand) ? brand : currentBrand;
        }}

        /// <summary>Resolve impact prefix to T3 skill VFX names.</summary>
        private string[] ResolveSkillsFromImpact(string impactType)
        {{
            if (string.IsNullOrEmpty(impactType)) return Array.Empty<string>();
            string prefix = impactType;
            int idx = impactType.IndexOf('_');
            if (idx > 0) prefix = impactType.Substring(0, idx);
            return ImpactToSkillMap.TryGetValue(prefix, out var skills) ? skills : Array.Empty<string>();
        }}

        // =================================================================
        // T2 AnimationEvent handlers
        // =================================================================

        /// <summary>
        /// Called by T2 AnimationEvent: spawns a named VFX at the weapon socket.
        /// The vfxName can be a socket-qualified name "vfxName@socket" or just "vfxName".
        /// </summary>
        public void OnAnimVFXSpawn(string vfxName)
        {{
            if (string.IsNullOrEmpty(vfxName)) return;
            if (debugLogging) Debug.Log($"[VFXAnimBridge] OnAnimVFXSpawn: {{vfxName}}");

            // Parse optional socket qualifier: "trail_sparks@weapon_hand_R"
            string effectName = vfxName;
            string socketName = "weapon_hand_R";
            int atIdx = vfxName.IndexOf('@');
            if (atIdx > 0)
            {{
                effectName = vfxName.Substring(0, atIdx);
                socketName = vfxName.Substring(atIdx + 1);
            }}

            Transform socket = GetSocket(socketName);
            SpawnGenericVFX(effectName, socket.position, socket.forward);
            OnVFXSpawned?.Invoke(effectName, socket.position);
        }}

        /// <summary>
        /// Called by T2 AnimationEvent: maps impact type to T3 VFX skills and
        /// spawns the correct brand-aware impact burst.
        /// </summary>
        public void OnAnimHit(string impactType)
        {{
            if (string.IsNullOrEmpty(impactType)) return;
            if (debugLogging) Debug.Log($"[VFXAnimBridge] OnAnimHit: {{impactType}}");

            string resolvedBrand = ResolveBrandFromImpact(impactType);
            string[] skills = ResolveSkillsFromImpact(impactType);

            // Determine intensity from suffix: _light=0.5, _medium=0.75, _heavy=1.0
            float intensity = 0.75f;
            if (impactType.EndsWith("_light")) intensity = 0.5f;
            else if (impactType.EndsWith("_heavy")) intensity = 1.0f;
            else if (impactType.EndsWith("_medium")) intensity = 0.75f;

            Transform socket = GetSocket("weapon_hand_R");
            SpawnImpactVFX(resolvedBrand, socket.position, socket.forward, intensity);

            // Notify melee skill VFX controller if present
            if (skills.Length > 0)
            {{
                string selectedSkill = skills[0];
                if (debugLogging)
                    Debug.Log($"[VFXAnimBridge] Mapped {{impactType}} -> brand={{resolvedBrand}}, skill={{selectedSkill}}");
            }}

            OnVFXSpawned?.Invoke($"impact_{{impactType}}", socket.position);
        }}

        /// <summary>
        /// Called by T2 AnimationEvent: triggers camera shake via Cinemachine
        /// impulse or fallback PrimeTween screen shake.
        /// </summary>
        public void OnAnimCameraShake(string impactType)
        {{
            if (string.IsNullOrEmpty(impactType)) return;
            if (debugLogging) Debug.Log($"[VFXAnimBridge] OnAnimCameraShake: {{impactType}}");

            // Determine shake intensity from impact type
            float intensity = ResolveShakeIntensity(impactType);

            // Try Cinemachine impulse first
            if (cinemachineImpulseSource != null)
            {{
                TryCinemachineShake(intensity);
            }}
            else
            {{
                // Fallback: PrimeTween camera shake
                Camera cam = Camera.main;
                if (cam != null)
                {{
                    float duration = Mathf.Lerp(0.1f, 0.4f, intensity);
                    float strength = Mathf.Lerp(0.05f, 0.3f, intensity);
#if PRIME_TWEEN
                    Tween.ShakeLocalPosition(cam.transform, strength: strength, duration: duration);
#endif
                }}
            }}

            OnCameraShakeTriggered?.Invoke(impactType, intensity);
        }}

        /// <summary>
        /// Called by T2 AnimationEvent: applies hitstop (time freeze) using
        /// PrimeTween timeScale manipulation. Duration comes from T2's combat
        /// timing data.
        /// </summary>
        public void OnAnimHitstop(string attackType)
        {{
            if (string.IsNullOrEmpty(attackType)) return;
            if (debugLogging) Debug.Log($"[VFXAnimBridge] OnAnimHitstop: {{attackType}}");

            float duration = ResolveHitstopDuration(attackType);
            if (duration <= 0f) return;

            StartCoroutine(HitstopCoroutine(duration));
            OnHitstopTriggered?.Invoke(attackType, duration);
        }}

        /// <summary>
        /// Called by T2 AnimationEvent: spawns footstep dust/splash VFX at
        /// the named foot bone.
        /// </summary>
        public void OnAnimFootstep(string footName)
        {{
            if (string.IsNullOrEmpty(footName)) return;
            if (debugLogging) Debug.Log($"[VFXAnimBridge] OnAnimFootstep: {{footName}}");

            // Map foot names to hip sockets as approximation
            string socketName = footName.Contains("L") ? "hip_L" : "hip_R";
            Transform socket = GetSocket(socketName);

            // Raycast down from socket to find ground
            Vector3 groundPos = socket.position;
            if (Physics.Raycast(socket.position, Vector3.down, out RaycastHit hit, 2f))
            {{
                groundPos = hit.point;
            }}

            SpawnFootstepVFX(groundPos, hit.normal);
            OnVFXSpawned?.Invoke($"footstep_{{footName}}", groundPos);
        }}

        // =================================================================
        // Trail VFX management (start/stop during attack windows)
        // =================================================================

        /// <summary>
        /// Start a brand-aware trail VFX at the given socket. Called at vfx_frame.
        /// </summary>
        public void StartTrailVFX(string socketName = "weapon_hand_R")
        {{
            StopTrailVFX();
            Transform socket = GetSocket(socketName);
            if (trailVFXPrefab == null) return;

            _activeTrailInstance = Instantiate(trailVFXPrefab, socket);
            _activeTrailInstance.transform.localPosition = Vector3.zero;
            _activeTrailInstance.transform.localRotation = Quaternion.identity;

            // Configure brand color
            var main = _activeTrailInstance.main;
            main.startColor = GetBrandPrimary();

            // Configure trail renderer if present
            var trail = _activeTrailInstance.GetComponent<TrailRenderer>();
            if (trail != null)
            {{
                Gradient g = new Gradient();
                g.SetKeys(
                    new GradientColorKey[] {{
                        new GradientColorKey(GetBrandGlow(), 0f),
                        new GradientColorKey(GetBrandPrimary(), 1f)
                    }},
                    new GradientAlphaKey[] {{
                        new GradientAlphaKey(1f, 0f),
                        new GradientAlphaKey(0f, 1f)
                    }}
                );
                trail.colorGradient = g;
            }}

            _activeTrailInstance.Play();
            if (debugLogging) Debug.Log($"[VFXAnimBridge] Trail started at {{socketName}}, brand={{currentBrand}}");
        }}

        /// <summary>Stop and destroy the active trail VFX.</summary>
        public void StopTrailVFX()
        {{
            if (_activeTrailInstance != null)
            {{
                _activeTrailInstance.Stop(true, ParticleSystemStopBehavior.StopEmitting);
                Destroy(_activeTrailInstance.gameObject, 2f); // let particles fade
                _activeTrailInstance = null;
            }}
        }}

        /// <summary>
        /// Runs a full attack VFX sequence: trail at vfx_frame, impact burst
        /// at hit_frame, hitstop, then trail stop.
        /// </summary>
        public void PlayAttackVFXSequence(string attackType, string impactType, string socketName = "weapon_hand_R")
        {{
            if (_activeTrailCoroutine != null) StopCoroutine(_activeTrailCoroutine);
            _activeTrailCoroutine = StartCoroutine(AttackVFXSequenceCoroutine(attackType, impactType, socketName));
        }}

        private IEnumerator AttackVFXSequenceCoroutine(string attackType, string impactType, string socketName)
        {{
            CombatTiming timing = GetCombatTiming(attackType);
            float vfxTime = timing.VfxTime(animationFPS);
            float hitTime = timing.HitTime(animationFPS);
            float hitstopDur = timing.HitstopDuration(animationFPS);

            // Wait until vfx_frame then start trail
            yield return new WaitForSeconds(vfxTime);
            StartTrailVFX(socketName);

            // Wait until hit_frame then burst impact
            float waitToHit = hitTime - vfxTime;
            if (waitToHit > 0f) yield return new WaitForSeconds(waitToHit);

            OnAnimHit(impactType);
            OnAnimCameraShake(impactType);

            // Hitstop
            if (hitstopDur > 0f)
            {{
                OnAnimHitstop(attackType);
                yield return new WaitForSecondsRealtime(hitstopDur);
            }}

            // Let trail linger briefly then stop
            yield return new WaitForSeconds(0.15f);
            StopTrailVFX();
            _activeTrailCoroutine = null;
        }}

        // =================================================================
        // VFX spawning helpers
        // =================================================================

        private void SpawnImpactVFX(string brand, Vector3 position, Vector3 direction, float intensity)
        {{
            if (impactVFXPrefab == null) return;

            ParticleSystem ps = Instantiate(impactVFXPrefab, position, Quaternion.LookRotation(direction));

            // Brand coloring
            Color brandColor = BrandPrimaryColors.TryGetValue(brand, out var bc) ? bc : Color.white;
            Color glowColor = BrandGlowColors.TryGetValue(brand, out var gc) ? gc : Color.white;

            var main = ps.main;
            main.startColor = brandColor;
            main.startSizeMultiplier *= intensity;

            // Emission burst scaled by intensity
            var emission = ps.emission;
            emission.rateOverTimeMultiplier *= intensity;

            ps.Play();
            Destroy(ps.gameObject, main.startLifetime.constantMax + 0.5f);
        }}

        private void SpawnGenericVFX(string effectName, Vector3 position, Vector3 direction)
        {{
            if (impactVFXPrefab == null) return;

            ParticleSystem ps = Instantiate(impactVFXPrefab, position, Quaternion.LookRotation(direction));
            var main = ps.main;
            main.startColor = GetBrandPrimary();
            ps.Play();
            Destroy(ps.gameObject, main.startLifetime.constantMax + 0.5f);
        }}

        private void SpawnFootstepVFX(Vector3 position, Vector3 normal)
        {{
            if (footstepVFXPrefab == null) return;

            Quaternion rot = normal != Vector3.zero ? Quaternion.LookRotation(normal) : Quaternion.identity;
            ParticleSystem ps = Instantiate(footstepVFXPrefab, position, rot);
            ps.Play();
            Destroy(ps.gameObject, ps.main.startLifetime.constantMax + 0.5f);
        }}

        // =================================================================
        // Hitstop
        // =================================================================

        private float ResolveHitstopDuration(string attackType)
        {{
            if (CombatTimingData.TryGetValue(attackType, out var timing))
            {{
                return timing.HitstopDuration(animationFPS);
            }}
            // Fallback: 2 frames at animation FPS
            return 2f / animationFPS;
        }}

        private IEnumerator HitstopCoroutine(float duration)
        {{
            float prevTimeScale = Time.timeScale;
            Time.timeScale = 0.02f;

            // Use Tween for smooth recovery
            yield return new WaitForSecondsRealtime(duration);

            // Smoothly restore time scale
#if PRIME_TWEEN
            Tween.Custom(0.02f, prevTimeScale, 0.08f,
                onValueChange: val => Time.timeScale = val,
                useUnscaledTime: true
            );
#else
            Time.timeScale = prevTimeScale;
#endif
        }}

        // =================================================================
        // Camera shake helpers
        // =================================================================

        private float ResolveShakeIntensity(string impactType)
        {{
            // Intensity from suffix
            if (impactType.EndsWith("_heavy")) return 1.0f;
            if (impactType.EndsWith("_medium")) return 0.6f;
            if (impactType.EndsWith("_light")) return 0.3f;

            // Intensity from attack type
            if (CombatTimingData.TryGetValue(impactType, out var timing))
            {{
                return Mathf.Clamp01(timing.hitstopFrames / 6f);
            }}
            return 0.5f;
        }}

        private void TryCinemachineShake(float intensity)
        {{
            // Use reflection to call GenerateImpulse without hard Cinemachine dependency
            var method = cinemachineImpulseSource.GetType().GetMethod(
                "GenerateImpulse",
                new Type[] {{ typeof(Vector3) }}
            );
            if (method != null)
            {{
                method.Invoke(cinemachineImpulseSource, new object[]
                {{
                    Vector3.one * intensity
                }});
            }}
        }}

        // =================================================================
        // Timing helpers
        // =================================================================

        private CombatTiming GetCombatTiming(string attackType)
        {{
            if (CombatTimingData.TryGetValue(attackType, out var t)) return t;
            // Default: light_attack timing
            return new CombatTiming(6, 7, 2);
        }}

        /// <summary>Convert frame number to seconds at current animation FPS.</summary>
        public float FrameToSeconds(int frame) => frame / animationFPS;

        // =================================================================
        // Public API for combat system integration
        // =================================================================

        /// <summary>
        /// One-call API: plays the full attack VFX chain for a given attack.
        /// Handles trail, impact, hitstop, and camera shake automatically.
        /// </summary>
        public void TriggerAttackVFX(string attackType, string impactType,
                                      string socketName = "weapon_hand_R")
        {{
            PlayAttackVFXSequence(attackType, impactType, socketName);
        }}

        /// <summary>Spawn brand-aware VFX at a named socket.</summary>
        public void SpawnAtSocket(string socketName, float intensity = 1f)
        {{
            Transform socket = GetSocket(socketName);
            SpawnImpactVFX(currentBrand, socket.position, socket.forward, intensity);
            OnVFXSpawned?.Invoke($"socket_{{socketName}}", socket.position);
        }}

#if UNITY_EDITOR
        // =================================================================
        // Editor gizmos — show socket positions
        // =================================================================

        private void OnDrawGizmosSelected()
        {{
            if (_socketLookup == null) BuildSocketLookup();
            Gizmos.color = Color.cyan;
            foreach (var kvp in _socketLookup)
            {{
                if (kvp.Value != null)
                {{
                    Gizmos.DrawWireSphere(kvp.Value.position, 0.05f);
#if UNITY_EDITOR
                    UnityEditor.Handles.Label(kvp.Value.position + Vector3.up * 0.08f, kvp.Key);
#endif
                }}
            }}
        }}
#endif
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/VFXAnimationBridge.cs",
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 2. generate_vfx_socket_setup_script
# ===================================================================


def generate_vfx_socket_setup_script() -> dict[str, Any]:
    """Generate VFXSocketSetup editor script.

    Creates an Editor window/menu item that auto-discovers the 10 standard
    bone sockets on a character rig and assigns them to the VFXAnimationBridge
    component.  Works with T2's Blender bone naming convention (DEF-hand.R,
    DEF-spine.005, etc.) and creates empty GameObjects as socket markers if
    the bone exists but has no socket child.

    Returns:
        Dict with script_path, script_content, next_steps.
    """

    # Build C# dictionary literal for bone -> field mapping
    bone_map_lines = []
    for bone, field in BLENDER_BONE_TO_SOCKET.items():
        bone_map_lines.append(f'            {{ "{bone}", "{field}" }},')
    bone_map_cs = "\n".join(bone_map_lines)

    # Build C# dictionary for Humanoid avatar bone -> field mapping
    humanoid_map = {
        "RightHand":       "weaponHandR",
        "LeftHand":        "weaponHandL",
        "LeftLowerArm":    "shieldHandL",
        "RightIndexProximal": "spellHandR",
        "LeftIndexProximal":  "spellHandL",
        "Head":            "headSocket",
        "UpperChest":      "chestSocket",
        "Spine":           "backWeaponSocket",
        "LeftUpperLeg":    "hipL",
        "RightUpperLeg":   "hipR",
    }
    humanoid_map_lines = []
    for hbone, field in humanoid_map.items():
        humanoid_map_lines.append(f'            {{ "{hbone}", "{field}" }},')
    humanoid_map_cs = "\n".join(humanoid_map_lines)

    # Socket field -> display name (for creating markers)
    socket_display = {
        "weaponHandR":     "VFX_Socket_WeaponR",
        "weaponHandL":     "VFX_Socket_WeaponL",
        "shieldHandL":     "VFX_Socket_ShieldL",
        "spellHandR":      "VFX_Socket_SpellR",
        "spellHandL":      "VFX_Socket_SpellL",
        "headSocket":      "VFX_Socket_Head",
        "chestSocket":     "VFX_Socket_Chest",
        "backWeaponSocket": "VFX_Socket_BackWeapon",
        "hipL":            "VFX_Socket_HipL",
        "hipR":            "VFX_Socket_HipR",
    }
    socket_display_lines = []
    for field, display in socket_display.items():
        socket_display_lines.append(f'            {{ "{field}", "{display}" }},')
    socket_display_cs = "\n".join(socket_display_lines)

    script = f'''using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;
using UnityEditor;

namespace VeilBreakers.VFX.Editor
{{
    /// <summary>
    /// Editor utility that auto-discovers bone sockets on a character rig and
    /// assigns them to the VFXAnimationBridge component. Supports both Blender
    /// DEF- bone naming (T2 convention) and Unity Humanoid avatar bone mapping.
    /// </summary>
    public static class VFXSocketSetup
    {{
        // Blender DEF- bone name -> VFXAnimationBridge serialized field name
        private static readonly Dictionary<string, string> BlenderBoneToSocket = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {{
{bone_map_cs}
        }};

        // Unity Humanoid bone name -> VFXAnimationBridge serialized field name
        private static readonly Dictionary<string, string> HumanoidBoneToSocket = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {{
{humanoid_map_cs}
        }};

        // Socket field name -> marker GameObject name
        private static readonly Dictionary<string, string> SocketMarkerNames = new Dictionary<string, string>
        {{
{socket_display_cs}
        }};

        // All 10 standard socket field names in order
        private static readonly string[] AllSocketFields = new string[]
        {{
            "weaponHandR", "weaponHandL", "shieldHandL",
            "spellHandR", "spellHandL",
            "headSocket", "chestSocket", "backWeaponSocket",
            "hipL", "hipR"
        }};

        [MenuItem("VeilBreakers/VFX/Auto-Setup VFX Sockets")]
        public static void AutoSetupSockets()
        {{
            GameObject selected = Selection.activeGameObject;
            if (selected == null)
            {{
                EditorUtility.DisplayDialog("VFX Socket Setup",
                    "Please select a character GameObject in the scene.", "OK");
                return;
            }}

            VFXAnimationBridge bridge = selected.GetComponent<VFXAnimationBridge>();
            if (bridge == null)
            {{
                bridge = Undo.AddComponent<VFXAnimationBridge>(selected);
                Debug.Log("[VFXSocketSetup] Added VFXAnimationBridge component.");
            }}

            SerializedObject so = new SerializedObject(bridge);
            Animator animator = selected.GetComponent<Animator>();
            int assigned = 0;
            int created = 0;
            List<string> warnings = new List<string>();

            // Phase 1: Try Humanoid avatar mapping
            if (animator != null && animator.isHuman)
            {{
                assigned += TryHumanoidMapping(selected, animator, so);
            }}

            // Phase 2: Deep search for Blender DEF- bones
            assigned += TryBlenderBoneSearch(selected, so);

            // Phase 3: Search by socket marker name (VFX_Socket_*)
            assigned += TryMarkerSearch(selected, so);

            // Phase 4: Create missing socket markers
            created = CreateMissingSockets(selected, so, warnings);

            so.ApplyModifiedProperties();
            EditorUtility.SetDirty(bridge);

            string resultJson = JsonUtility.ToJson(new SetupResult
            {{
                status = "success",
                action = "vfx_socket_setup",
                assigned = assigned,
                created = created,
                warnings = warnings.ToArray()
            }});
            System.IO.File.WriteAllText("Temp/vb_result.json", resultJson);

            string msg = $"VFX Socket Setup complete:\\n" +
                         $"  Sockets assigned: {{assigned}}\\n" +
                         $"  Markers created: {{created}}\\n" +
                         $"  Warnings: {{warnings.Count}}";
            Debug.Log($"[VFXSocketSetup] {{msg}}");
            EditorUtility.DisplayDialog("VFX Socket Setup", msg, "OK");
        }}

        // =================================================================
        // Phase 1: Humanoid avatar bone mapping
        // =================================================================

        private static int TryHumanoidMapping(GameObject root, Animator animator, SerializedObject so)
        {{
            int count = 0;
            foreach (HumanBodyBones bone in Enum.GetValues(typeof(HumanBodyBones)))
            {{
                if (bone == HumanBodyBones.LastBone) continue;
                Transform t = animator.GetBoneTransform(bone);
                if (t == null) continue;

                string boneName = bone.ToString();
                if (HumanoidBoneToSocket.TryGetValue(boneName, out string fieldName))
                {{
                    SerializedProperty prop = so.FindProperty(fieldName);
                    if (prop != null && prop.objectReferenceValue == null)
                    {{
                        prop.objectReferenceValue = t;
                        count++;
                        Debug.Log($"[VFXSocketSetup] Humanoid: {{boneName}} -> {{fieldName}}");
                    }}
                }}
            }}
            return count;
        }}

        // =================================================================
        // Phase 2: Blender DEF- bone deep search
        // =================================================================

        private static int TryBlenderBoneSearch(GameObject root, SerializedObject so)
        {{
            int count = 0;
            Transform[] allTransforms = root.GetComponentsInChildren<Transform>(true);

            foreach (Transform t in allTransforms)
            {{
                if (BlenderBoneToSocket.TryGetValue(t.name, out string fieldName))
                {{
                    SerializedProperty prop = so.FindProperty(fieldName);
                    if (prop != null && prop.objectReferenceValue == null)
                    {{
                        prop.objectReferenceValue = t;
                        count++;
                        Debug.Log($"[VFXSocketSetup] Blender bone: {{t.name}} -> {{fieldName}}");
                    }}
                }}
            }}
            return count;
        }}

        // =================================================================
        // Phase 3: Search for existing VFX_Socket_* markers
        // =================================================================

        private static int TryMarkerSearch(GameObject root, SerializedObject so)
        {{
            int count = 0;
            Transform[] allTransforms = root.GetComponentsInChildren<Transform>(true);

            foreach (Transform t in allTransforms)
            {{
                foreach (var kvp in SocketMarkerNames)
                {{
                    if (t.name.Equals(kvp.Value, StringComparison.OrdinalIgnoreCase))
                    {{
                        SerializedProperty prop = so.FindProperty(kvp.Key);
                        if (prop != null && prop.objectReferenceValue == null)
                        {{
                            prop.objectReferenceValue = t;
                            count++;
                            Debug.Log($"[VFXSocketSetup] Marker: {{t.name}} -> {{kvp.Key}}");
                        }}
                    }}
                }}
            }}
            return count;
        }}

        // =================================================================
        // Phase 4: Create missing socket marker GameObjects
        // =================================================================

        private static int CreateMissingSockets(GameObject root, SerializedObject so, List<string> warnings)
        {{
            int count = 0;
            Animator animator = root.GetComponent<Animator>();
            Transform[] allTransforms = root.GetComponentsInChildren<Transform>(true);

            foreach (string field in AllSocketFields)
            {{
                SerializedProperty prop = so.FindProperty(field);
                if (prop == null || prop.objectReferenceValue != null) continue;

                // Find the best parent bone for this socket
                Transform parent = FindBestParentBone(field, animator, allTransforms);
                if (parent == null)
                {{
                    warnings.Add($"Could not find parent bone for socket '{{field}}'. Skipped.");
                    continue;
                }}

                // Create marker GameObject
                string markerName = SocketMarkerNames.TryGetValue(field, out string mn) ? mn : $"VFX_Socket_{{field}}";

                // Check if marker already exists under parent
                Transform existing = parent.Find(markerName);
                if (existing != null)
                {{
                    prop.objectReferenceValue = existing;
                    count++;
                    continue;
                }}

                GameObject marker = new GameObject(markerName);
                Undo.RegisterCreatedObjectUndo(marker, $"Create VFX Socket {{markerName}}");
                marker.transform.SetParent(parent, false);
                marker.transform.localPosition = Vector3.zero;
                marker.transform.localRotation = Quaternion.identity;

                prop.objectReferenceValue = marker.transform;
                count++;
                Debug.Log($"[VFXSocketSetup] Created marker: {{markerName}} under {{parent.name}}");
            }}
            return count;
        }}

        /// <summary>
        /// Find the best parent bone for a socket field, trying Humanoid avatar
        /// first, then Blender bones, then root transform.
        /// </summary>
        private static Transform FindBestParentBone(string fieldName, Animator animator, Transform[] allTransforms)
        {{
            // Try Humanoid mapping
            if (animator != null && animator.isHuman)
            {{
                foreach (var kvp in HumanoidBoneToSocket)
                {{
                    if (kvp.Value == fieldName)
                    {{
                        HumanBodyBones hBone;
                        if (Enum.TryParse(kvp.Key, out hBone))
                        {{
                            Transform t = animator.GetBoneTransform(hBone);
                            if (t != null) return t;
                        }}
                    }}
                }}
            }}

            // Try Blender bone mapping
            foreach (var kvp in BlenderBoneToSocket)
            {{
                if (kvp.Value == fieldName)
                {{
                    foreach (Transform t in allTransforms)
                    {{
                        if (t.name.Equals(kvp.Key, StringComparison.OrdinalIgnoreCase))
                            return t;
                    }}
                }}
            }}

            // Fallback: root transform
            return allTransforms.Length > 0 ? allTransforms[0] : null;
        }}

        [Serializable]
        private struct SetupResult
        {{
            public string status;
            public string action;
            public int assigned;
            public int created;
            public string[] warnings;
        }}
    }}
}}
'''

    return {
        "script_path": "Assets/Editor/Generated/VFX/VFXSocketSetup.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor",
            "Wait for compilation",
            "Select a character GameObject in the scene",
            "Run VeilBreakers > VFX > Auto-Setup VFX Sockets from the menu bar",
        ],
    }
