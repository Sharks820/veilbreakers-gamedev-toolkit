"""Audio middleware C# template generators for Unity.

Implements Wwise/FMOD-level audio architecture without middleware cost:
spatial audio with propagation/occlusion, layered sound design, audio event
chains, dynamic music (horizontal re-sequencing, vertical layering, combat
stingers), portal-based sound propagation, audio LOD, dialogue/VO pipeline,
and procedural foley.

Each function returns a dict with ``script_path``, ``script_content``, and
``next_steps``.  The C# source is built via line-based string concatenation
following the established VeilBreakers template convention.

Phase 21 -- Audio Middleware Architecture
Requirements: AUDM-01 through AUDM-08
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier."""
    result = re.sub(r"[^a-zA-Z0-9_]", "", value)
    if not result:
        return "Default"
    if result[0].isdigit():
        result = "_" + result
    return result


# ---------------------------------------------------------------------------
# AUDM-01: Spatial Audio System
# ---------------------------------------------------------------------------


def generate_spatial_audio_script(
    source_name: str = "SpatialAudioSource",
    min_distance: float = 1.0,
    max_distance: float = 50.0,
    occlusion_enabled: bool = True,
    occlusion_layers: str = "Default",
    rolloff_mode: str = "Logarithmic",
    doppler_level: float = 0.5,
    spread_angle: float = 60.0,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for 3D spatial audio with occlusion.

    Creates a component that wraps Unity's AudioSource with advanced spatial
    features: configurable distance attenuation curves, geometry-based
    occlusion via raycasting, and customizable rolloff.

    Args:
        source_name: Name for the generated component class.
        min_distance: Minimum distance for audio rolloff.
        max_distance: Maximum distance for audio rolloff.
        occlusion_enabled: Whether to enable geometry occlusion.
        occlusion_layers: Layer name for occlusion raycasts.
        rolloff_mode: Rolloff mode -- Logarithmic, Linear, or Custom.
        doppler_level: Doppler effect intensity (0-5).
        spread_angle: 3D sound spread angle in degrees.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = _sanitize_cs_identifier(source_name)
    class_name = f"VeilBreakers_{safe_name}"

    # Map rolloff mode string to Unity enum
    rolloff_map = {
        "Logarithmic": "AudioRolloffMode.Logarithmic",
        "Linear": "AudioRolloffMode.Linear",
        "Custom": "AudioRolloffMode.Custom",
    }
    rolloff_enum = rolloff_map.get(rolloff_mode, "AudioRolloffMode.Logarithmic")

    occlusion_block = ""
    if occlusion_enabled:
        occlusion_block = f'''
    [Header("Occlusion")]
    [SerializeField] private bool occlusionEnabled = true;
    [SerializeField] private LayerMask occlusionLayers = ~0;
    [SerializeField] private float occlusionDamping = 0.15f;
    [SerializeField] private float occlusionLowPassFreq = 800f;
    [SerializeField] private int maxOcclusionRays = 3;

    private AudioLowPassFilter _lowPassFilter;
    private float _currentOcclusionFactor = 0f;
    private float _targetOcclusionFactor = 0f;

    private void UpdateOcclusion()
    {{
        if (!occlusionEnabled || _listener == null) return;

        Vector3 listenerPos = _listener.transform.position;
        Vector3 sourcePos = transform.position;
        Vector3 direction = listenerPos - sourcePos;
        float distance = direction.magnitude;

        if (distance < 0.01f)
        {{
            _targetOcclusionFactor = 0f;
            return;
        }}

        // Cast rays to detect occluding geometry
        int hitCount = 0;
        RaycastHit[] hits = Physics.RaycastAll(sourcePos, direction.normalized, distance, occlusionLayers);
        hitCount = hits.Length;

        // Additional rays for more accurate occlusion sampling
        if (maxOcclusionRays > 1)
        {{
            Vector3 right = Vector3.Cross(direction, Vector3.up).normalized * 0.5f;
            Vector3 up = Vector3.Cross(direction, right).normalized * 0.5f;

            for (int i = 1; i < maxOcclusionRays && i < 3; i++)
            {{
                Vector3 offset = (i == 1) ? right : up;
                Vector3 offsetDir = (listenerPos - (sourcePos + offset)).normalized;
                RaycastHit[] offsetHits = Physics.RaycastAll(
                    sourcePos + offset, offsetDir, distance, occlusionLayers);
                hitCount = Mathf.Max(hitCount, offsetHits.Length);
            }}
        }}

        // Each wall hit adds occlusion
        _targetOcclusionFactor = Mathf.Clamp01(hitCount * 0.35f);
    }}

    private void ApplyOcclusion()
    {{
        _currentOcclusionFactor = Mathf.Lerp(
            _currentOcclusionFactor, _targetOcclusionFactor,
            Time.deltaTime / Mathf.Max(occlusionDamping, 0.01f));

        // Reduce volume based on occlusion
        _audioSource.volume = _baseVolume * (1f - _currentOcclusionFactor * 0.7f);

        // Apply low-pass filter for muffled sound through walls
        if (_lowPassFilter != null)
        {{
            float targetFreq = Mathf.Lerp(22000f, occlusionLowPassFreq, _currentOcclusionFactor);
            _lowPassFilter.cutoffFrequency = targetFreq;
        }}
    }}'''

    occlusion_init = ""
    if occlusion_enabled:
        occlusion_init = '''
        // Setup low-pass filter for occlusion
        _lowPassFilter = GetComponent<AudioLowPassFilter>();
        if (_lowPassFilter == null)
            _lowPassFilter = gameObject.AddComponent<AudioLowPassFilter>();
        _lowPassFilter.cutoffFrequency = 22000f;'''

    occlusion_update = ""
    if occlusion_enabled:
        occlusion_update = '''
        UpdateOcclusion();
        ApplyOcclusion();'''

    script = f'''// VeilBreakers Auto-Generated: Spatial Audio System
// 3D sound propagation with distance attenuation and geometry occlusion
using UnityEngine;

/// <summary>
/// Spatial audio source with 3D propagation, distance attenuation curves,
/// and geometry-based occlusion via raycasting. Attach to any GameObject
/// that emits positional sound.
/// </summary>
[RequireComponent(typeof(AudioSource))]
public class {class_name} : MonoBehaviour
{{
    [Header("Spatial Configuration")]
    [SerializeField] private float minDistance = {min_distance}f;
    [SerializeField] private float maxDistance = {max_distance}f;
    [SerializeField] private float dopplerLevel = {doppler_level}f;
    [SerializeField] private float spreadAngle = {spread_angle}f;
    [SerializeField] private AudioRolloffMode rolloffMode = {rolloff_enum};

    [Header("Custom Rolloff Curve")]
    [SerializeField] private AnimationCurve customRolloffCurve = AnimationCurve.EaseInOut(0f, 1f, 1f, 0f);

    [Header("Runtime")]
    [SerializeField] private float volumeScale = 1.0f;
{occlusion_block}

    private AudioSource _audioSource;
    private AudioListener _listener;
    private float _baseVolume = 1.0f;

    private void Awake()
    {{
        _audioSource = GetComponent<AudioSource>();
        if (_audioSource == null)
            _audioSource = gameObject.AddComponent<AudioSource>();

        // Configure for full 3D spatialization
        _audioSource.spatialBlend = 1.0f;
        _audioSource.dopplerLevel = dopplerLevel;
        _audioSource.spread = spreadAngle;
        _audioSource.minDistance = minDistance;
        _audioSource.maxDistance = maxDistance;
        _audioSource.rolloffMode = rolloffMode;

        if (rolloffMode == AudioRolloffMode.Custom && customRolloffCurve != null)
        {{
            _audioSource.SetCustomCurve(AudioSourceCurveType.CustomRolloff, customRolloffCurve);
        }}

        _baseVolume = _audioSource.volume;
{occlusion_init}
    }}

    private void Start()
    {{
        _listener = FindAnyObjectByType<AudioListener>();
    }}

    private void Update()
    {{
        if (_listener == null)
        {{
            _listener = FindAnyObjectByType<AudioListener>();
            if (_listener == null) return;
        }}
{occlusion_update}
    }}

    /// <summary>
    /// Play a clip through this spatial audio source.
    /// </summary>
    public void PlayClip(AudioClip clip, float volume = 1.0f)
    {{
        if (clip == null || _audioSource == null) return;
        _baseVolume = volume * volumeScale;
        _audioSource.volume = _baseVolume;
        _audioSource.clip = clip;
        _audioSource.Play();
    }}

    /// <summary>
    /// Play a one-shot clip without interrupting the current clip.
    /// </summary>
    public void PlayOneShot(AudioClip clip, float volume = 1.0f)
    {{
        if (clip == null || _audioSource == null) return;
        _audioSource.PlayOneShot(clip, volume * volumeScale);
    }}

    /// <summary>
    /// Update spatial parameters at runtime.
    /// </summary>
    public void SetSpatialParams(float newMinDist, float newMaxDist, float newSpread)
    {{
        minDistance = newMinDist;
        maxDistance = newMaxDist;
        spreadAngle = newSpread;

        if (_audioSource != null)
        {{
            _audioSource.minDistance = minDistance;
            _audioSource.maxDistance = maxDistance;
            _audioSource.spread = spreadAngle;
        }}
    }}

    /// <summary>
    /// Get the current distance from this source to the active listener.
    /// </summary>
    public float GetDistanceToListener()
    {{
        if (_listener == null) return float.MaxValue;
        return Vector3.Distance(transform.position, _listener.transform.position);
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/Runtime/Audio/{class_name}.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Attach the component to any audio-emitting GameObject",
            "Configure occlusion layers to match your level geometry",
            "Test with AudioListener on the player camera",
        ],
    }


# ---------------------------------------------------------------------------
# AUDM-06: Audio LOD System
# ---------------------------------------------------------------------------


def generate_audio_lod_script(
    lod_distances: list[float] | None = None,
    channel_reduction: bool = True,
    priority_scaling: bool = True,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for distance-based audio quality tiers.

    Creates an audio LOD system that reduces quality, channels, and priority
    at greater distances for performance optimization.

    LOD Tiers:
        - Full (0-15m): all channels, full sample rate, highest priority
        - Reduced (15-30m): mono downmix, lower priority
        - Minimal (30-50m): simplified sound, lowest priority
        - Culled (50m+): AudioSource disabled entirely

    Args:
        lod_distances: Distance thresholds for [reduced, minimal, culled].
                       Defaults to [15, 30, 50].
        channel_reduction: Enable mono downmix at distance.
        priority_scaling: Enable priority reduction at distance.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if not lod_distances:
        lod_distances = [15.0, 30.0, 50.0]

    # Ensure we have exactly 3 thresholds
    while len(lod_distances) < 3:
        lod_distances.append(lod_distances[-1] + 15.0)

    d_reduced = lod_distances[0]
    d_minimal = lod_distances[1]
    d_culled = lod_distances[2]

    channel_block = ""
    if channel_reduction:
        channel_block = '''
    private void ApplyChannelReduction(AudioLODTier tier)
    {
        if (_audioSource == null) return;

        switch (tier)
        {
            case AudioLODTier.Full:
                _audioSource.spatialBlend = _originalSpatialBlend;
                break;
            case AudioLODTier.Reduced:
                // Force mono for distant sources
                _audioSource.spatialBlend = 1.0f;
                break;
            case AudioLODTier.Minimal:
                _audioSource.spatialBlend = 1.0f;
                break;
            case AudioLODTier.Culled:
                break;
        }
    }'''

    priority_block = ""
    if priority_scaling:
        priority_block = '''
    private void ApplyPriorityScaling(AudioLODTier tier)
    {
        if (_audioSource == null) return;

        switch (tier)
        {
            case AudioLODTier.Full:
                _audioSource.priority = _originalPriority;
                break;
            case AudioLODTier.Reduced:
                _audioSource.priority = Mathf.Min(_originalPriority + 64, 256);
                break;
            case AudioLODTier.Minimal:
                _audioSource.priority = Mathf.Min(_originalPriority + 128, 256);
                break;
            case AudioLODTier.Culled:
                _audioSource.priority = 256;
                break;
        }
    }'''

    apply_channel = "\n        ApplyChannelReduction(newTier);" if channel_reduction else ""
    apply_priority = "\n        ApplyPriorityScaling(newTier);" if priority_scaling else ""

    script = f'''// VeilBreakers Auto-Generated: Audio LOD System
// Distance-based audio quality tiers for performance optimization
using UnityEngine;

/// <summary>
/// Audio quality tiers based on distance from the listener.
/// </summary>
public enum AudioLODTier
{{
    Full,       // All channels, full quality
    Reduced,    // Mono downmix, lower priority
    Minimal,    // Simplified, lowest priority
    Culled      // AudioSource disabled
}}

/// <summary>
/// Audio LOD system that adjusts quality, channels, and priority based on
/// distance to the AudioListener. Attach alongside an AudioSource.
/// </summary>
[RequireComponent(typeof(AudioSource))]
public class VeilBreakers_AudioLOD : MonoBehaviour
{{
    [Header("LOD Distance Thresholds")]
    [Tooltip("Distance for Reduced tier (mono, lower priority)")]
    [SerializeField] private float reducedDistance = {d_reduced}f;
    [Tooltip("Distance for Minimal tier (simplified, lowest priority)")]
    [SerializeField] private float minimalDistance = {d_minimal}f;
    [Tooltip("Distance for Culled tier (AudioSource disabled)")]
    [SerializeField] private float culledDistance = {d_culled}f;

    [Header("LOD Settings")]
    [SerializeField] private float updateInterval = 0.25f;
    [SerializeField] private float volumeReductionMinimal = 0.5f;

    [Header("Debug")]
    [SerializeField] private AudioLODTier currentTier = AudioLODTier.Full;

    private AudioSource _audioSource;
    private AudioListener _listener;
    private float _originalVolume;
    private float _originalSpatialBlend;
    private int _originalPriority;
    private float _nextUpdateTime;

    private void Awake()
    {{
        _audioSource = GetComponent<AudioSource>();
        _originalVolume = _audioSource.volume;
        _originalSpatialBlend = _audioSource.spatialBlend;
        _originalPriority = _audioSource.priority;
    }}

    private void Start()
    {{
        _listener = FindAnyObjectByType<AudioListener>();
    }}

    private void Update()
    {{
        if (Time.time < _nextUpdateTime) return;
        _nextUpdateTime = Time.time + updateInterval;

        if (_listener == null)
        {{
            _listener = FindAnyObjectByType<AudioListener>();
            if (_listener == null) return;
        }}

        float distance = Vector3.Distance(
            transform.position, _listener.transform.position);

        AudioLODTier newTier = CalculateTier(distance);
        if (newTier != currentTier)
        {{
            ApplyTier(newTier);
        }}
    }}

    /// <summary>
    /// Determine which LOD tier applies at the given distance.
    /// </summary>
    public AudioLODTier CalculateTier(float distance)
    {{
        if (distance >= culledDistance) return AudioLODTier.Culled;
        if (distance >= minimalDistance) return AudioLODTier.Minimal;
        if (distance >= reducedDistance) return AudioLODTier.Reduced;
        return AudioLODTier.Full;
    }}

    private void ApplyTier(AudioLODTier newTier)
    {{
        currentTier = newTier;

        switch (newTier)
        {{
            case AudioLODTier.Full:
                _audioSource.enabled = true;
                _audioSource.volume = _originalVolume;
                break;
            case AudioLODTier.Reduced:
                _audioSource.enabled = true;
                _audioSource.volume = _originalVolume * 0.85f;
                break;
            case AudioLODTier.Minimal:
                _audioSource.enabled = true;
                _audioSource.volume = _originalVolume * volumeReductionMinimal;
                break;
            case AudioLODTier.Culled:
                _audioSource.enabled = false;
                break;
        }}
{apply_channel}{apply_priority}
    }}
{channel_block}
{priority_block}

    /// <summary>
    /// Get the current LOD tier.
    /// </summary>
    public AudioLODTier GetCurrentTier()
    {{
        return currentTier;
    }}

    /// <summary>
    /// Force a specific LOD tier (overrides distance calculation).
    /// </summary>
    public void ForceSetTier(AudioLODTier tier)
    {{
        ApplyTier(tier);
    }}

    /// <summary>
    /// Update the LOD distance thresholds at runtime.
    /// </summary>
    public void SetDistances(float reduced, float minimal, float culled)
    {{
        reducedDistance = reduced;
        minimalDistance = minimal;
        culledDistance = culled;
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/Audio/VeilBreakers_AudioLOD.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Attach VeilBreakers_AudioLOD to any distant AudioSource",
            "Adjust distance thresholds based on your level scale",
            "Use profile_scene to verify audio performance gains",
        ],
    }


# ---------------------------------------------------------------------------
# AUDM-02: Layered Sound Design
# ---------------------------------------------------------------------------


def generate_layered_sound_script(
    sound_name: str = "LayeredSound",
    layers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate C# class for composite layered sound design.

    Creates a system where multiple AudioClips are combined into complex
    sounds (e.g., sword_impact = metal_clang + bone_crack + cloth_rustle),
    each with independent volume, pitch, delay, and randomization.

    Args:
        sound_name: Name for the layered sound asset.
        layers: List of layer dicts with keys: clip_path, volume, pitch,
                delay, random_pitch, random_volume.  Defaults to example
                impact layers.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = _sanitize_cs_identifier(sound_name)

    if layers is None:
        layers = [
            {"clip_path": "Audio/SFX/metal_clang", "volume": 1.0, "pitch": 1.0,
             "delay": 0.0, "random_pitch": 0.1, "random_volume": 0.05},
            {"clip_path": "Audio/SFX/bone_crack", "volume": 0.7, "pitch": 0.9,
             "delay": 0.02, "random_pitch": 0.15, "random_volume": 0.1},
            {"clip_path": "Audio/SFX/cloth_rustle", "volume": 0.4, "pitch": 1.1,
             "delay": 0.05, "random_pitch": 0.2, "random_volume": 0.1},
        ]

    # Build the default layers array for the inspector
    layer_defaults = ""
    for i, layer in enumerate(layers):
        clip_path = layer.get("clip_path", "")
        vol = layer.get("volume", 1.0)
        pitch = layer.get("pitch", 1.0)
        delay = layer.get("delay", 0.0)
        rp = layer.get("random_pitch", 0.1)
        rv = layer.get("random_volume", 0.05)
        layer_defaults += f'''
            // Layer {i}: {clip_path.split("/")[-1] if "/" in clip_path else clip_path}
            // Volume={vol}, Pitch={pitch}, Delay={delay}s
            // RandomPitch=+/-{rp}, RandomVolume=+/-{rv}'''

    script = f'''// VeilBreakers Auto-Generated: Layered Sound System
// Composite sound design -- combine multiple clips into complex sounds
using UnityEngine;
using System;
using System.Collections;

/// <summary>
/// Defines a single audio layer within a layered sound.
/// </summary>
[Serializable]
public class VB_SoundLayer
{{
    [Tooltip("AudioClip for this layer")]
    public AudioClip clip;

    [Range(0f, 1f)]
    [Tooltip("Base volume for this layer")]
    public float volume = 1.0f;

    [Range(0.1f, 3f)]
    [Tooltip("Base pitch for this layer")]
    public float pitch = 1.0f;

    [Tooltip("Delay in seconds before this layer plays")]
    public float delay = 0.0f;

    [Range(0f, 1f)]
    [Tooltip("Random pitch variation (+/-)")]
    public float randomPitch = 0.1f;

    [Range(0f, 0.5f)]
    [Tooltip("Random volume variation (+/-)")]
    public float randomVolume = 0.05f;
}}

/// <summary>
/// ScriptableObject defining a layered sound preset.
/// Create via Assets > Create > VeilBreakers > Audio > Layered Sound.
/// </summary>
[CreateAssetMenu(fileName = "LayeredSound_{safe_name}", menuName = "VeilBreakers/Audio/Layered Sound")]
public class VeilBreakers_LayeredSoundData : ScriptableObject
{{
    [Tooltip("Human-readable name for this layered sound")]
    public string soundName = "{safe_name}";

    [Tooltip("Individual sound layers that compose this sound")]
    public VB_SoundLayer[] layers = new VB_SoundLayer[0];
    {layer_defaults}
}}

/// <summary>
/// Plays layered sounds by triggering all layers with timing offsets.
/// Attach to a GameObject with an AudioSource (or one will be created).
/// </summary>
public class VeilBreakers_LayeredSoundPlayer : MonoBehaviour
{{
    [Header("Sound Data")]
    [SerializeField] private VeilBreakers_LayeredSoundData soundData;

    [Header("Playback")]
    [SerializeField] private bool playOnStart = false;
    [SerializeField] private float spatialBlend = 1.0f;

    private AudioSource _primarySource;

    private void Awake()
    {{
        _primarySource = GetComponent<AudioSource>();
        if (_primarySource == null)
            _primarySource = gameObject.AddComponent<AudioSource>();

        _primarySource.playOnAwake = false;
        _primarySource.spatialBlend = spatialBlend;
    }}

    private void Start()
    {{
        if (playOnStart && soundData != null)
            Play();
    }}

    /// <summary>
    /// Play all layers of the current sound data.
    /// </summary>
    public void Play()
    {{
        if (soundData == null || soundData.layers == null) return;
        PlayLayeredSound(soundData);
    }}

    /// <summary>
    /// Play a specific layered sound data asset.
    /// </summary>
    public void PlayLayeredSound(VeilBreakers_LayeredSoundData data)
    {{
        if (data == null || data.layers == null) return;

        foreach (VB_SoundLayer layer in data.layers)
        {{
            if (layer.clip == null) continue;

            if (layer.delay <= 0f)
            {{
                PlaySingleLayer(layer);
            }}
            else
            {{
                StartCoroutine(PlayLayerDelayed(layer));
            }}
        }}
    }}

    private IEnumerator PlayLayerDelayed(VB_SoundLayer layer)
    {{
        yield return new WaitForSeconds(layer.delay);
        PlaySingleLayer(layer);
    }}

    private void PlaySingleLayer(VB_SoundLayer layer)
    {{
        float finalVolume = layer.volume +
            UnityEngine.Random.Range(-layer.randomVolume, layer.randomVolume);
        finalVolume = Mathf.Clamp01(finalVolume);

        float finalPitch = layer.pitch +
            UnityEngine.Random.Range(-layer.randomPitch, layer.randomPitch);
        finalPitch = Mathf.Max(0.1f, finalPitch);

        // Use PlayOneShot for overlapping layers
        _primarySource.pitch = finalPitch;
        _primarySource.PlayOneShot(layer.clip, finalVolume);
    }}

    /// <summary>
    /// Set the layered sound data at runtime.
    /// </summary>
    public void SetSoundData(VeilBreakers_LayeredSoundData data)
    {{
        soundData = data;
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/Audio/VeilBreakers_LayeredSoundPlayer.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Create a LayeredSound asset: Assets > Create > VeilBreakers > Audio > Layered Sound",
            "Assign AudioClips to each layer with volume/pitch/delay settings",
            "Attach VeilBreakers_LayeredSoundPlayer to the emitting GameObject",
        ],
    }


# ---------------------------------------------------------------------------
# AUDM-03: Audio Event Chains
# ---------------------------------------------------------------------------


def generate_audio_event_chain_script(
    chain_name: str = "ImpactChain",
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate C# ScriptableObject for sequenced audio event chains.

    Creates a data-driven system for ordered audio event sequences with
    timing, conditions, and trigger logic (e.g., impact -> reverb tail ->
    debris scatter).

    Args:
        chain_name: Name for the event chain asset.
        events: List of event dicts with keys: clip_path, delay_ms, volume,
                condition.  Defaults to example impact chain.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = _sanitize_cs_identifier(chain_name)

    if events is None:
        events = [
            {"clip_path": "Audio/SFX/impact_hit", "delay_ms": 0, "volume": 1.0,
             "condition": ""},
            {"clip_path": "Audio/SFX/reverb_tail", "delay_ms": 50, "volume": 0.6,
             "condition": ""},
            {"clip_path": "Audio/SFX/debris_scatter", "delay_ms": 200, "volume": 0.4,
             "condition": ""},
        ]

    # Build comment block showing the chain structure
    chain_comment = ""
    for i, evt in enumerate(events):
        clip = evt.get("clip_path", "unknown")
        delay = evt.get("delay_ms", 0)
        cond = evt.get("condition", "")
        arrow = " -> " if i < len(events) - 1 else ""
        cond_str = f" [if {cond}]" if cond else ""
        chain_comment += f"//   {i}: {clip} @ {delay}ms{cond_str}{arrow}\n"

    script = f'''// VeilBreakers Auto-Generated: Audio Event Chain System
// Sequenced audio events with timing and conditions
// Chain "{safe_name}":
{chain_comment}using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Single audio event within a chain -- clip + timing + condition.
/// </summary>
[Serializable]
public class VB_AudioEvent
{{
    [Tooltip("AudioClip to play")]
    public AudioClip clip;

    [Tooltip("Delay in milliseconds before this event triggers")]
    public float delayMs = 0f;

    [Range(0f, 1f)]
    [Tooltip("Playback volume")]
    public float volume = 1.0f;

    [Range(0.5f, 2f)]
    [Tooltip("Playback pitch")]
    public float pitch = 1.0f;

    [Range(0f, 1f)]
    [Tooltip("Spatial blend (0=2D, 1=3D)")]
    public float spatialBlend = 1.0f;

    [Tooltip("Optional condition tag -- empty means always play")]
    public string condition = "";

    [Tooltip("Whether to skip this event if the chain is interrupted")]
    public bool skippable = false;
}}

/// <summary>
/// ScriptableObject defining an ordered sequence of audio events.
/// Create via Assets > Create > VeilBreakers > Audio > Audio Event Chain.
/// </summary>
[CreateAssetMenu(fileName = "AudioEventChain_{safe_name}", menuName = "VeilBreakers/Audio/Audio Event Chain")]
public class VeilBreakers_AudioEventChainData : ScriptableObject
{{
    [Tooltip("Unique name for this chain")]
    public string chainName = "{safe_name}";

    [Tooltip("Ordered list of audio events in this chain")]
    public VB_AudioEvent[] events = new VB_AudioEvent[0];

    [Tooltip("Whether this chain can be interrupted by a new trigger")]
    public bool interruptible = true;

    [Tooltip("Cooldown before this chain can be triggered again (seconds)")]
    public float cooldown = 0.1f;
}}

/// <summary>
/// Plays audio event chains with precise timing. Supports multiple
/// concurrent chains, interruption, cooldowns, and conditional events.
/// </summary>
public class VeilBreakers_AudioEventChainPlayer : MonoBehaviour
{{
    [Header("Chain Data")]
    [SerializeField] private VeilBreakers_AudioEventChainData defaultChain;

    [Header("Audio Sources")]
    [SerializeField] private int maxConcurrentSources = 4;

    private List<AudioSource> _sourcePool = new List<AudioSource>();
    private Dictionary<string, float> _cooldowns = new Dictionary<string, float>();
    private Dictionary<string, Coroutine> _activeChains = new Dictionary<string, Coroutine>();
    private HashSet<string> _activeConditions = new HashSet<string>();

    private void Awake()
    {{
        // Pre-create audio source pool
        for (int i = 0; i < maxConcurrentSources; i++)
        {{
            GameObject child = new GameObject("VB_ChainSource_" + i);
            child.transform.SetParent(transform);
            AudioSource src = child.AddComponent<AudioSource>();
            src.playOnAwake = false;
            _sourcePool.Add(src);
        }}
    }}

    /// <summary>
    /// Trigger the default event chain.
    /// </summary>
    public void TriggerChain()
    {{
        if (defaultChain != null)
            TriggerChain(defaultChain);
    }}

    /// <summary>
    /// Trigger a specific event chain.
    /// </summary>
    public void TriggerChain(VeilBreakers_AudioEventChainData chainData)
    {{
        if (chainData == null) return;

        string key = chainData.chainName;

        // Check cooldown
        if (_cooldowns.ContainsKey(key) && Time.time < _cooldowns[key])
            return;

        // Handle existing chain
        if (_activeChains.ContainsKey(key))
        {{
            if (!chainData.interruptible)
                return;  // Non-interruptible: skip if already playing
            if (_activeChains[key] != null)
                StopCoroutine(_activeChains[key]);
            _activeChains.Remove(key);
        }}

        // Start new chain
        Coroutine routine = StartCoroutine(PlayChainSequence(chainData));
        _activeChains[key] = routine;
        _cooldowns[key] = Time.time + chainData.cooldown;
    }}

    private IEnumerator PlayChainSequence(VeilBreakers_AudioEventChainData chainData)
    {{
        string key = chainData.chainName;

        foreach (VB_AudioEvent evt in chainData.events)
        {{
            // Check condition
            if (!string.IsNullOrEmpty(evt.condition) &&
                !_activeConditions.Contains(evt.condition))
            {{
                continue;
            }}

            // Wait for delay
            if (evt.delayMs > 0f)
            {{
                yield return new WaitForSeconds(evt.delayMs / 1000f);
            }}

            // Play the event
            if (evt.clip != null)
            {{
                AudioSource source = GetAvailableSource();
                if (source != null)
                {{
                    source.clip = evt.clip;
                    source.volume = evt.volume;
                    source.pitch = evt.pitch;
                    source.spatialBlend = evt.spatialBlend;
                    source.transform.position = transform.position;
                    source.Play();
                }}
            }}
        }}

        _activeChains.Remove(key);
    }}

    private AudioSource GetAvailableSource()
    {{
        foreach (AudioSource src in _sourcePool)
        {{
            if (!src.isPlaying) return src;
        }}
        // All sources busy -- return the first one (interrupt oldest)
        return _sourcePool.Count > 0 ? _sourcePool[0] : null;
    }}

    /// <summary>
    /// Set a condition as active (allows conditional events to play).
    /// </summary>
    public void SetCondition(string condition, bool active)
    {{
        if (active)
            _activeConditions.Add(condition);
        else
            _activeConditions.Remove(condition);
    }}

    /// <summary>
    /// Stop all currently playing chains.
    /// </summary>
    public void StopAllChains()
    {{
        StopAllCoroutines();
        _activeChains.Clear();
        foreach (AudioSource src in _sourcePool)
        {{
            src.Stop();
        }}
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/Audio/VeilBreakers_AudioEventChainPlayer.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Create chain assets: Assets > Create > VeilBreakers > Audio > Audio Event Chain",
            "Define events with clips, delays, and optional conditions",
            "Attach VeilBreakers_AudioEventChainPlayer and call TriggerChain()",
        ],
    }


# ---------------------------------------------------------------------------
# AUDM-08: Procedural Foley
# ---------------------------------------------------------------------------


def generate_procedural_foley_script(
    character_name: str = "Player",
    armor_type: str = "plate",
    surface_materials: list[str] | None = None,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for movement-based procedural foley.

    Creates a system that generates realistic movement sounds based on:
    - Surface material (via Physics.Raycast + PhysicMaterial detection)
    - Movement speed (walk/run/sprint intensity scaling)
    - Animation events (footstep, cloth_rustle, armor_clink triggers)
    - Armor type (plate=heavy_clinks, leather=creaks, cloth=rustles)

    Args:
        character_name: Character identifier for the foley system.
        armor_type: Default armor type -- plate, leather, cloth, chain.
        surface_materials: List of surface material names.
                          Defaults to stone, wood, metal, dirt, grass, water, snow.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = _sanitize_cs_identifier(character_name)

    if not surface_materials:
        surface_materials = ["stone", "wood", "metal", "dirt", "grass", "water", "snow"]

    # Build surface enum entries
    surface_enum = ",\n    ".join(s.capitalize() for s in surface_materials)

    # Build surface detection cases
    surface_cases = ""
    for i, mat in enumerate(surface_materials):
        keyword = "if" if i == 0 else "else if"
        surface_cases += f'''
            {keyword} (matName.Contains("{mat.lower()}"))
                return SurfaceMaterial.{mat.capitalize()};'''

    # Build armor type handling
    armor_types = ["plate", "leather", "cloth", "chain"]
    armor_enum = ",\n    ".join(a.capitalize() for a in armor_types)

    script = f'''// VeilBreakers Auto-Generated: Procedural Foley System
// Movement-based sound generation with surface/armor/speed awareness
using UnityEngine;
using System;
using System.Collections.Generic;

/// <summary>
/// Surface materials for foley sound selection.
/// </summary>
public enum SurfaceMaterial
{{
    {surface_enum}
}}

/// <summary>
/// Armor types that influence movement foley.
/// </summary>
public enum ArmorFoleyType
{{
    {armor_enum}
}}

/// <summary>
/// Speed categories for movement intensity scaling.
/// </summary>
public enum MovementSpeed
{{
    Idle,
    Walk,
    Run,
    Sprint
}}

/// <summary>
/// Foley sound bank per surface material.
/// </summary>
[Serializable]
public class VB_FoleySurfaceBank
{{
    public SurfaceMaterial surface;
    public AudioClip[] footstepClips;
    public AudioClip[] scuffClips;
    [Range(0f, 1f)] public float baseVolume = 0.8f;
    [Range(0.5f, 2f)] public float basePitch = 1.0f;
}}

/// <summary>
/// Foley sound bank per armor type.
/// </summary>
[Serializable]
public class VB_FoleyArmorBank
{{
    public ArmorFoleyType armorType;
    public AudioClip[] movementClips;    // Continuous movement sounds
    public AudioClip[] impactClips;      // Landing / sudden stop
    public AudioClip[] rustleClips;      // Subtle cloth/material sounds
    [Range(0f, 1f)] public float volume = 0.5f;
}}

/// <summary>
/// Procedural foley system that generates realistic movement sounds.
/// Detects surface via raycasting, scales intensity by speed, and
/// layers armor-specific sounds on top. Trigger via animation events
/// or call methods directly from a movement controller.
/// </summary>
public class VeilBreakers_ProceduralFoley : MonoBehaviour
{{
    [Header("Character")]
    [SerializeField] private string characterName = "{safe_name}";
    [SerializeField] private ArmorFoleyType currentArmorType = ArmorFoleyType.{armor_type.capitalize()};

    [Header("Surface Detection")]
    [SerializeField] private float raycastDistance = 1.5f;
    [SerializeField] private LayerMask groundLayer = ~0;

    [Header("Sound Banks")]
    [SerializeField] private VB_FoleySurfaceBank[] surfaceBanks;
    [SerializeField] private VB_FoleyArmorBank[] armorBanks;

    [Header("Speed Thresholds")]
    [SerializeField] private float walkSpeedThreshold = 0.5f;
    [SerializeField] private float runSpeedThreshold = 3.0f;
    [SerializeField] private float sprintSpeedThreshold = 6.0f;

    [Header("Volume Scaling")]
    [SerializeField] private float walkVolumeScale = 0.6f;
    [SerializeField] private float runVolumeScale = 0.85f;
    [SerializeField] private float sprintVolumeScale = 1.0f;

    [Header("Audio")]
    [SerializeField] private AudioSource footstepSource;
    [SerializeField] private AudioSource armorSource;

    private SurfaceMaterial _currentSurface = SurfaceMaterial.{surface_materials[0].capitalize()};
    private MovementSpeed _currentSpeed = MovementSpeed.Idle;
    private Dictionary<SurfaceMaterial, VB_FoleySurfaceBank> _surfaceLookup =
        new Dictionary<SurfaceMaterial, VB_FoleySurfaceBank>();
    private Dictionary<ArmorFoleyType, VB_FoleyArmorBank> _armorLookup =
        new Dictionary<ArmorFoleyType, VB_FoleyArmorBank>();

    private void Awake()
    {{
        // Setup audio sources
        if (footstepSource == null)
        {{
            GameObject fsObj = new GameObject("VB_FootstepSource");
            fsObj.transform.SetParent(transform);
            footstepSource = fsObj.AddComponent<AudioSource>();
        }}
        footstepSource.playOnAwake = false;
        footstepSource.spatialBlend = 1.0f;

        if (armorSource == null)
        {{
            GameObject arObj = new GameObject("VB_ArmorSource");
            arObj.transform.SetParent(transform);
            armorSource = arObj.AddComponent<AudioSource>();
        }}
        armorSource.playOnAwake = false;
        armorSource.spatialBlend = 1.0f;

        // Build lookup dictionaries
        if (surfaceBanks != null)
        {{
            foreach (var bank in surfaceBanks)
                _surfaceLookup[bank.surface] = bank;
        }}
        if (armorBanks != null)
        {{
            foreach (var bank in armorBanks)
                _armorLookup[bank.armorType] = bank;
        }}
    }}

    /// <summary>
    /// Call from animation event: plays a footstep sound.
    /// </summary>
    public void OnFootstep()
    {{
        DetectSurface();
        PlayFootstepFoley();
        PlayArmorFoley();
    }}

    /// <summary>
    /// Call from animation event: plays cloth rustle sound.
    /// </summary>
    public void OnClothRustle()
    {{
        PlayArmorRustle();
    }}

    /// <summary>
    /// Call from animation event: plays armor clink/creak sound.
    /// </summary>
    public void OnArmorClink()
    {{
        PlayArmorFoley();
    }}

    /// <summary>
    /// Update movement speed category based on velocity magnitude.
    /// Call this from your movement controller each frame.
    /// </summary>
    public void UpdateMovementSpeed(float speed)
    {{
        if (speed < walkSpeedThreshold)
            _currentSpeed = MovementSpeed.Idle;
        else if (speed < runSpeedThreshold)
            _currentSpeed = MovementSpeed.Walk;
        else if (speed < sprintSpeedThreshold)
            _currentSpeed = MovementSpeed.Run;
        else
            _currentSpeed = MovementSpeed.Sprint;
    }}

    /// <summary>
    /// Set armor type at runtime (e.g., when equipment changes).
    /// </summary>
    public void SetArmorType(ArmorFoleyType type)
    {{
        currentArmorType = type;
    }}

    private void DetectSurface()
    {{
        if (Physics.Raycast(transform.position, Vector3.down,
            out RaycastHit hit, raycastDistance, groundLayer))
        {{
            if (hit.collider.sharedMaterial != null)
            {{
                string matName = hit.collider.sharedMaterial.name.ToLower();
                _currentSurface = ParseSurfaceMaterial(matName);
            }}
        }}
    }}

    private SurfaceMaterial ParseSurfaceMaterial(string matName)
    {{{surface_cases}
        return SurfaceMaterial.{surface_materials[0].capitalize()};
    }}

    private float GetVolumeScale()
    {{
        switch (_currentSpeed)
        {{
            case MovementSpeed.Walk: return walkVolumeScale;
            case MovementSpeed.Run: return runVolumeScale;
            case MovementSpeed.Sprint: return sprintVolumeScale;
            default: return 0f;
        }}
    }}

    private void PlayFootstepFoley()
    {{
        if (!_surfaceLookup.ContainsKey(_currentSurface)) return;

        VB_FoleySurfaceBank bank = _surfaceLookup[_currentSurface];
        if (bank.footstepClips == null || bank.footstepClips.Length == 0) return;

        AudioClip clip = bank.footstepClips[UnityEngine.Random.Range(0, bank.footstepClips.Length)];
        float volume = bank.baseVolume * GetVolumeScale();
        float pitch = bank.basePitch + UnityEngine.Random.Range(-0.1f, 0.1f);

        footstepSource.pitch = pitch;
        footstepSource.PlayOneShot(clip, volume);
    }}

    private void PlayArmorFoley()
    {{
        if (!_armorLookup.ContainsKey(currentArmorType)) return;

        VB_FoleyArmorBank bank = _armorLookup[currentArmorType];
        if (bank.movementClips == null || bank.movementClips.Length == 0) return;

        AudioClip clip = bank.movementClips[UnityEngine.Random.Range(0, bank.movementClips.Length)];
        float volume = bank.volume * GetVolumeScale();

        armorSource.PlayOneShot(clip, volume);
    }}

    private void PlayArmorRustle()
    {{
        if (!_armorLookup.ContainsKey(currentArmorType)) return;

        VB_FoleyArmorBank bank = _armorLookup[currentArmorType];
        if (bank.rustleClips == null || bank.rustleClips.Length == 0) return;

        AudioClip clip = bank.rustleClips[UnityEngine.Random.Range(0, bank.rustleClips.Length)];
        float volume = bank.volume * GetVolumeScale() * 0.6f;

        armorSource.PlayOneShot(clip, volume);
    }}

    /// <summary>
    /// Get the currently detected surface material.
    /// </summary>
    public SurfaceMaterial GetCurrentSurface()
    {{
        return _currentSurface;
    }}

    /// <summary>
    /// Get the current movement speed category.
    /// </summary>
    public MovementSpeed GetCurrentMovementSpeed()
    {{
        return _currentSpeed;
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/Runtime/Audio/VeilBreakers_ProceduralFoley.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Attach VeilBreakers_ProceduralFoley to your character",
            "Create PhysicMaterials named after surface types (stone, wood, etc.)",
            "Add animation events calling OnFootstep(), OnClothRustle(), OnArmorClink()",
            "Call UpdateMovementSpeed() from your movement controller each frame",
        ],
    }


# ---------------------------------------------------------------------------
# AUDM-04: Dynamic Music System
# ---------------------------------------------------------------------------


def generate_dynamic_music_script(
    music_name: str = "DynamicMusic",
    sections: list[str] | None = None,
    stems: list[str] | None = None,
    stingers: list[str] | None = None,
    crossfade_duration: float = 2.0,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for adaptive dynamic music.

    Creates a full dynamic music system with:
    - Horizontal re-sequencing: sections (intro, verse, chorus, etc.) with
      transition rules
    - Vertical layering: stems (drums, bass, melody, pads, percussion) with
      independent volume control
    - Combat stingers: one-shot clips triggered by game events
    - Crossfade between sections with configurable duration
    - Game state hooks: exploration -> combat -> boss -> victory

    Args:
        music_name: Name for the music system.
        sections: List of music section names.
        stems: List of stem/instrument names.
        stingers: List of stinger event names.
        crossfade_duration: Default crossfade time in seconds.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = _sanitize_cs_identifier(music_name)

    if not sections:
        sections = ["Intro", "Exploration", "Tension", "Combat", "BossPhase1",
                     "BossPhase2", "Victory", "Defeat"]
    if not stems:
        stems = ["Drums", "Bass", "Melody", "Pads", "Percussion"]
    if not stingers:
        stingers = ["EnemySpotted", "BossPhaseChange", "PlayerDeath",
                     "LootDrop", "QuestComplete"]

    section_enum = ",\n    ".join(sections)
    stem_enum = ",\n    ".join(stems)
    stinger_enum = ",\n    ".join(stingers)
    num_stems = len(stems)
    num_sections = len(sections)

    # Build stem source initialization
    stem_init = ""
    for i, stem in enumerate(stems):
        stem_init += f'''
            // Stem {i}: {stem}
            _stemSources[{i}] = gameObject.AddComponent<AudioSource>();
            _stemSources[{i}].loop = true;
            _stemSources[{i}].playOnAwake = false;
            _stemSources[{i}].spatialBlend = 0f;
            _stemSources[{i}].volume = 0f;'''

    script = f'''// VeilBreakers Auto-Generated: Dynamic Music System
// Horizontal re-sequencing + vertical layering + combat stingers
using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Music sections for horizontal re-sequencing.
/// </summary>
public enum MusicSection
{{
    {section_enum}
}}

/// <summary>
/// Music stems for vertical layering.
/// </summary>
public enum MusicStem
{{
    {stem_enum}
}}

/// <summary>
/// Combat stinger event types.
/// </summary>
public enum StingerEvent
{{
    {stinger_enum}
}}

/// <summary>
/// Defines the stem mix for a specific music section.
/// </summary>
[Serializable]
public class VB_StemMix
{{
    public MusicSection section;
    [Range(0f, 1f)] public float[] stemVolumes = new float[{num_stems}];
}}

/// <summary>
/// Defines a transition rule between sections.
/// </summary>
[Serializable]
public class VB_MusicTransition
{{
    public MusicSection fromSection;
    public MusicSection toSection;
    public float crossfadeDuration = {crossfade_duration}f;
    [Tooltip("If true, wait for current bar to end before transitioning")]
    public bool waitForBar = false;
    public float barDuration = 2.0f;
}}

/// <summary>
/// Dynamic music manager with horizontal re-sequencing, vertical stem
/// layering, and combat stingers.  Singleton -- persists across scenes.
/// </summary>
public class VeilBreakers_DynamicMusic : MonoBehaviour
{{
    [Header("Section Clips")]
    [Tooltip("One AudioClip per section (horizontal re-sequencing)")]
    public AudioClip[] sectionClips = new AudioClip[{num_sections}];

    [Header("Stem Clips")]
    [Tooltip("One AudioClip per stem (vertical layering)")]
    public AudioClip[] stemClips = new AudioClip[{num_stems}];

    [Header("Stinger Clips")]
    [Tooltip("One-shot clips for combat/game events")]
    public AudioClip[] stingerClips = new AudioClip[{len(stingers)}];

    [Header("Stem Mixes")]
    [Tooltip("Volume mix per section -- defines which stems are active")]
    public VB_StemMix[] stemMixes;

    [Header("Transitions")]
    [Tooltip("Custom transition rules between sections")]
    public VB_MusicTransition[] transitions;

    [Header("Settings")]
    public float defaultCrossfadeDuration = {crossfade_duration}f;
    public float stingerVolume = 0.8f;

    private AudioSource _sectionSource;
    private AudioSource _sectionSourceB; // For crossfading
    private AudioSource[] _stemSources;
    private AudioSource _stingerSource;
    private bool _useSourceA = true;
    private MusicSection _currentSection = MusicSection.{sections[0]};
    private Coroutine _transitionCoroutine;

    private static VeilBreakers_DynamicMusic _instance;
    public static VeilBreakers_DynamicMusic Instance => _instance;

    private void Awake()
    {{
        if (_instance != null && _instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        _instance = this;
        DontDestroyOnLoad(gameObject);

        // Section sources (A/B for crossfading)
        _sectionSource = gameObject.AddComponent<AudioSource>();
        _sectionSource.loop = true;
        _sectionSource.playOnAwake = false;
        _sectionSource.spatialBlend = 0f;

        _sectionSourceB = gameObject.AddComponent<AudioSource>();
        _sectionSourceB.loop = true;
        _sectionSourceB.playOnAwake = false;
        _sectionSourceB.spatialBlend = 0f;
        _sectionSourceB.volume = 0f;

        // Stem sources (vertical layering)
        _stemSources = new AudioSource[{num_stems}];
{stem_init}

        // Stinger source
        _stingerSource = gameObject.AddComponent<AudioSource>();
        _stingerSource.playOnAwake = false;
        _stingerSource.spatialBlend = 0f;
        _stingerSource.loop = false;
    }}

    private void Start()
    {{
        // Start stems playing (volumes at 0 until a section activates them)
        for (int i = 0; i < stemClips.Length && i < _stemSources.Length; i++)
        {{
            if (stemClips[i] != null)
            {{
                _stemSources[i].clip = stemClips[i];
                _stemSources[i].Play();
            }}
        }}

        // Start default section
        TransitionToSection(MusicSection.{sections[0]});
    }}

    /// <summary>
    /// Transition to a new music section with crossfade.
    /// </summary>
    public void TransitionToSection(MusicSection section)
    {{
        // Check whichever source is currently active (crossfade alternates A/B)
        AudioSource activeSource = _useSourceA ? _sectionSource : _sectionSourceB;
        if (section == _currentSection && activeSource.isPlaying) return;

        MusicSection oldSection = _currentSection;
        _currentSection = section;

        float duration = GetTransitionDuration(oldSection, section);

        if (_transitionCoroutine != null)
            StopCoroutine(_transitionCoroutine);

        _transitionCoroutine = StartCoroutine(
            CrossfadeSection(section, duration));
    }}

    private float GetTransitionDuration(MusicSection from, MusicSection to)
    {{
        if (transitions != null)
        {{
            foreach (var t in transitions)
            {{
                if (t.fromSection == from && t.toSection == to)
                    return t.crossfadeDuration;
            }}
        }}
        return defaultCrossfadeDuration;
    }}

    private IEnumerator CrossfadeSection(MusicSection section, float duration)
    {{
        int sectionIndex = (int)section;
        AudioSource incoming = _useSourceA ? _sectionSource : _sectionSourceB;
        AudioSource outgoing = _useSourceA ? _sectionSourceB : _sectionSource;
        _useSourceA = !_useSourceA;

        // Set up incoming source
        if (sectionIndex < sectionClips.Length && sectionClips[sectionIndex] != null)
        {{
            incoming.clip = sectionClips[sectionIndex];
            incoming.volume = 0f;
            incoming.Play();
        }}

        // Crossfade
        float elapsed = 0f;
        float outStartVol = outgoing.volume;
        while (elapsed < duration)
        {{
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / duration);

            outgoing.volume = Mathf.Lerp(outStartVol, 0f, t);
            incoming.volume = Mathf.Lerp(0f, 1f, t);

            yield return null;
        }}

        outgoing.volume = 0f;
        outgoing.Stop();
        incoming.volume = 1f;

        // Apply stem mix for this section
        ApplyStemMix(section);
    }}

    private void ApplyStemMix(MusicSection section)
    {{
        if (stemMixes == null) return;

        foreach (var mix in stemMixes)
        {{
            if (mix.section == section)
            {{
                for (int i = 0; i < mix.stemVolumes.Length &&
                     i < _stemSources.Length; i++)
                {{
                    StartCoroutine(FadeStemVolume(i, mix.stemVolumes[i],
                        defaultCrossfadeDuration * 0.5f));
                }}
                return;
            }}
        }}
    }}

    private IEnumerator FadeStemVolume(int stemIndex, float targetVolume,
        float duration)
    {{
        float startVol = _stemSources[stemIndex].volume;
        float elapsed = 0f;

        while (elapsed < duration)
        {{
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / duration);
            _stemSources[stemIndex].volume = Mathf.Lerp(startVol, targetVolume, t);
            yield return null;
        }}

        _stemSources[stemIndex].volume = targetVolume;
    }}

    /// <summary>
    /// Play a combat stinger one-shot.
    /// </summary>
    public void PlayStinger(StingerEvent stinger)
    {{
        int index = (int)stinger;
        if (index < stingerClips.Length && stingerClips[index] != null)
        {{
            _stingerSource.PlayOneShot(stingerClips[index], stingerVolume);
        }}
    }}

    /// <summary>
    /// Set an individual stem volume (0-1).
    /// </summary>
    public void SetStemVolume(MusicStem stem, float volume)
    {{
        int index = (int)stem;
        if (index < _stemSources.Length)
        {{
            _stemSources[index].volume = Mathf.Clamp01(volume);
        }}
    }}

    /// <summary>
    /// Get the currently active music section.
    /// </summary>
    public MusicSection GetCurrentSection()
    {{
        return _currentSection;
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/Audio/VeilBreakers_DynamicMusic.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Attach VeilBreakers_DynamicMusic to a persistent AudioManager object",
            "Assign section clips, stem clips, and stinger clips in inspector",
            "Configure stem mixes per section to control vertical layering",
            "Call TransitionToSection() on game state changes",
            "Call PlayStinger() on combat events",
        ],
    }


# ---------------------------------------------------------------------------
# AUDM-05: Portal Audio Propagation
# ---------------------------------------------------------------------------


def generate_portal_audio_script(
    portal_name: str = "AudioPortal",
    room_a: str = "RoomA",
    room_b: str = "RoomB",
    attenuation_closed: float = 0.9,
    attenuation_open: float = 0.1,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for room-based sound propagation via portals.

    Creates a system where sound propagates between rooms through doorways
    and openings, with realistic attenuation based on door state. Includes
    reverb zone blending and low-pass filtering for muffled through-wall
    sound.

    Args:
        portal_name: Name for the portal component.
        room_a: Name of the first connected room.
        room_b: Name of the second connected room.
        attenuation_closed: Volume reduction when door is closed (0-1, higher=more).
        attenuation_open: Volume reduction when door is open (0-1, higher=more).

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = _sanitize_cs_identifier(portal_name)

    script = f'''// VeilBreakers Auto-Generated: Portal Audio Propagation System
// Room-based sound with portal attenuation and reverb blending
using UnityEngine;
using System;
using System.Collections.Generic;

/// <summary>
/// Door state controlling sound propagation through portals.
/// </summary>
public enum PortalDoorState
{{
    Open,
    PartiallyOpen,
    Closed
}}

/// <summary>
/// Defines an audio room with its own reverb characteristics.
/// Attach to a trigger collider encompassing the room volume.
/// </summary>
public class VeilBreakers_AudioRoom : MonoBehaviour
{{
    [Header("Room Identity")]
    public string roomName = "Unnamed Room";

    [Header("Reverb Settings")]
    [SerializeField] private float decayTime = 2.0f;
    [SerializeField] private float roomSize = -1000f;
    [SerializeField] private float reflections = -500f;
    [SerializeField] private float reverb = 200f;

    [Header("Ambient")]
    [SerializeField] private AudioClip ambientClip;
    [SerializeField] private float ambientVolume = 0.3f;

    private AudioReverbZone _reverbZone;
    private AudioSource _ambientSource;
    private List<AudioSource> _roomSources = new List<AudioSource>();

    private void Awake()
    {{
        // Setup reverb zone
        _reverbZone = GetComponent<AudioReverbZone>();
        if (_reverbZone == null)
            _reverbZone = gameObject.AddComponent<AudioReverbZone>();

        _reverbZone.decayTime = decayTime;
        _reverbZone.room = Mathf.RoundToInt(roomSize);
        _reverbZone.reflections = Mathf.RoundToInt(reflections);
        _reverbZone.reverb = Mathf.RoundToInt(reverb);

        // Setup ambient source
        if (ambientClip != null)
        {{
            _ambientSource = gameObject.AddComponent<AudioSource>();
            _ambientSource.clip = ambientClip;
            _ambientSource.loop = true;
            _ambientSource.volume = ambientVolume;
            _ambientSource.spatialBlend = 0.5f;
            _ambientSource.playOnAwake = false;
        }}
    }}

    /// <summary>
    /// Register an audio source as belonging to this room.
    /// </summary>
    public void RegisterSource(AudioSource source)
    {{
        if (!_roomSources.Contains(source))
            _roomSources.Add(source);
    }}

    /// <summary>
    /// Get all audio sources in this room.
    /// </summary>
    public List<AudioSource> GetRoomSources()
    {{
        // Clean up destroyed sources
        _roomSources.RemoveAll(s => s == null);
        return _roomSources;
    }}

    /// <summary>
    /// Set room active state (enables/disables ambient and reverb).
    /// </summary>
    public void SetActive(bool active)
    {{
        if (_reverbZone != null)
            _reverbZone.enabled = active;

        if (_ambientSource != null)
        {{
            if (active && !_ambientSource.isPlaying)
                _ambientSource.Play();
            else if (!active && _ambientSource.isPlaying)
                _ambientSource.Stop();
        }}
    }}

    /// <summary>
    /// Get the reverb zone for blending.
    /// </summary>
    public AudioReverbZone GetReverbZone()
    {{
        return _reverbZone;
    }}
}}

/// <summary>
/// Audio portal placed on doorways/openings between rooms.
/// Controls sound propagation, attenuation, and reverb blending.
/// </summary>
public class VeilBreakers_AudioPortal : MonoBehaviour
{{
    [Header("Connected Rooms")]
    [SerializeField] private VeilBreakers_AudioRoom roomA;
    [SerializeField] private VeilBreakers_AudioRoom roomB;

    [Header("Door State")]
    [SerializeField] private PortalDoorState doorState = PortalDoorState.Open;

    [Header("Attenuation")]
    [Tooltip("Volume reduction when fully closed (0=none, 1=full)")]
    [SerializeField] private float attenuationClosed = {attenuation_closed}f;
    [Tooltip("Volume reduction when fully open (0=none, 1=full)")]
    [SerializeField] private float attenuationOpen = {attenuation_open}f;
    [Tooltip("Volume reduction when partially open")]
    [SerializeField] private float attenuationPartial = {(attenuation_closed + attenuation_open) / 2.0}f;

    [Header("Low-Pass Filter")]
    [Tooltip("Cutoff frequency when sound passes through closed door")]
    [SerializeField] private float closedLowPassFreq = 500f;
    [Tooltip("Cutoff frequency when door is open")]
    [SerializeField] private float openLowPassFreq = 22000f;

    [Header("Reverb Blending")]
    [SerializeField] private float reverbBlendDistance = 3.0f;

    private AudioListener _listener;
    private VeilBreakers_AudioRoom _listenerRoom;
    private Dictionary<AudioSource, float> _originalVolumes = new Dictionary<AudioSource, float>();

    private void Start()
    {{
        _listener = FindAnyObjectByType<AudioListener>();
    }}

    private void Update()
    {{
        if (_listener == null)
        {{
            _listener = FindAnyObjectByType<AudioListener>();
            if (_listener == null) return;
        }}

        UpdateListenerRoom();
        UpdatePortalAttenuation();
    }}

    private void UpdateListenerRoom()
    {{
        // Determine which room the listener is in
        if (roomA != null && roomB != null)
        {{
            float distA = Vector3.Distance(
                _listener.transform.position, roomA.transform.position);
            float distB = Vector3.Distance(
                _listener.transform.position, roomB.transform.position);

            _listenerRoom = distA < distB ? roomA : roomB;
        }}
    }}

    private void UpdatePortalAttenuation()
    {{
        if (roomA == null || roomB == null || _listenerRoom == null) return;

        VeilBreakers_AudioRoom otherRoom =
            (_listenerRoom == roomA) ? roomB : roomA;

        float attenuation = GetCurrentAttenuation();

        // Apply attenuation to sources in the other room
        List<AudioSource> otherSources = otherRoom.GetRoomSources();
        foreach (AudioSource source in otherSources)
        {{
            if (source == null) continue;

            // Track original volume (first time we see this source)
            if (!_originalVolumes.ContainsKey(source))
                _originalVolumes[source] = source.volume;

            // Apply attenuation relative to original volume (not current)
            source.volume = _originalVolumes[source] * (1f - attenuation);

            // Apply low-pass filter
            AudioLowPassFilter lpf = source.GetComponent<AudioLowPassFilter>();
            if (lpf == null)
                lpf = source.gameObject.AddComponent<AudioLowPassFilter>();

            float targetFreq = Mathf.Lerp(
                closedLowPassFreq, openLowPassFreq, 1f - attenuation);
            lpf.cutoffFrequency = Mathf.Lerp(
                lpf.cutoffFrequency, targetFreq, Time.deltaTime * 5f);
        }}
    }}

    /// <summary>
    /// Get the current attenuation factor based on door state.
    /// </summary>
    public float GetCurrentAttenuation()
    {{
        switch (doorState)
        {{
            case PortalDoorState.Open: return attenuationOpen;
            case PortalDoorState.PartiallyOpen: return attenuationPartial;
            case PortalDoorState.Closed: return attenuationClosed;
            default: return attenuationOpen;
        }}
    }}

    /// <summary>
    /// Set the door state (call when door opens/closes).
    /// </summary>
    public void SetDoorState(PortalDoorState state)
    {{
        doorState = state;
    }}

    /// <summary>
    /// Set door openness as a float (0=closed, 1=open).
    /// </summary>
    public void SetDoorOpenness(float openness)
    {{
        openness = Mathf.Clamp01(openness);
        if (openness < 0.1f)
            doorState = PortalDoorState.Closed;
        else if (openness > 0.9f)
            doorState = PortalDoorState.Open;
        else
            doorState = PortalDoorState.PartiallyOpen;

        // Interpolate attenuation for smooth transitions
        attenuationPartial = Mathf.Lerp(attenuationClosed, attenuationOpen, openness);
    }}

    /// <summary>
    /// Get the room the listener is currently in.
    /// </summary>
    public VeilBreakers_AudioRoom GetListenerRoom()
    {{
        return _listenerRoom;
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/Audio/VeilBreakers_AudioPortal.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Attach VeilBreakers_AudioRoom to each room volume trigger",
            "Place VeilBreakers_AudioPortal on doorways between rooms",
            "Connect Room A and Room B references in the inspector",
            "Call SetDoorState() or SetDoorOpenness() from your door controller",
        ],
    }


# ---------------------------------------------------------------------------
# AUDM-07: Dialogue/VO Pipeline
# ---------------------------------------------------------------------------


def generate_vo_pipeline_script(
    database_name: str = "VODatabase",
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate C# system for dialogue and voice-over playback.

    Creates a complete VO pipeline with:
    - VOEntry: AudioClip, subtitle text, emotion tag, lip sync markers
    - VODatabase: ScriptableObject indexing all VO entries by ID
    - VOPlayer: MonoBehaviour for playback with subtitles and lip sync
    - Localization support: locale-indexed clip arrays
    - Queue system: sequential playback with interruption priority

    Args:
        database_name: Name for the VO database asset.
        entries: List of entry dicts with keys: id, subtitle, emotion, duration.
                Defaults to example entries.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = _sanitize_cs_identifier(database_name)

    if entries is None:
        entries = [
            {"id": "greeting_01", "subtitle": "Welcome, traveler.",
             "emotion": "neutral", "duration": 2.0},
            {"id": "combat_01", "subtitle": "You dare challenge me?",
             "emotion": "aggressive", "duration": 1.8},
            {"id": "death_01", "subtitle": "This... cannot be...",
             "emotion": "despair", "duration": 2.5},
        ]

    # Build default entries comment
    entries_comment = ""
    for entry in entries:
        eid = entry.get("id", "unknown")
        sub = entry.get("subtitle", "")
        emo = entry.get("emotion", "neutral")
        dur = entry.get("duration", 2.0)
        entries_comment += f'    // {eid}: "{sub}" [{emo}] ({dur}s)\n'

    script = f'''// VeilBreakers Auto-Generated: Dialogue/VO Pipeline
// Voice-over playback with subtitles, lip sync, emotion tags, localization
using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Emotion tags for VO entries.
/// </summary>
public enum VOEmotion
{{
    Neutral,
    Aggressive,
    Despair,
    Joy,
    Fear,
    Sarcasm,
    Commanding,
    Whisper
}}

/// <summary>
/// Lip sync viseme timing marker.
/// </summary>
[Serializable]
public class VB_VisemeMarker
{{
    [Tooltip("Time in seconds from clip start")]
    public float time;

    [Tooltip("Viseme shape index (0-14 standard visemes)")]
    public int visemeIndex;

    [Range(0f, 1f)]
    [Tooltip("Viseme intensity/weight")]
    public float weight = 1.0f;
}}

/// <summary>
/// Single VO entry with clip, subtitle, emotion, and lip sync data.
/// </summary>
[Serializable]
public class VB_VOEntry
{{
    [Tooltip("Unique identifier for this VO line")]
    public string id;

    [Tooltip("Default AudioClip (primary locale)")]
    public AudioClip clip;

    [Tooltip("Subtitle text")]
    [TextArea(1, 3)]
    public string subtitle = "";

    [Tooltip("Emotion tag for animation/expression")]
    public VOEmotion emotion = VOEmotion.Neutral;

    [Tooltip("Duration in seconds (auto-set from clip if available)")]
    public float duration = 2.0f;

    [Tooltip("Lip sync viseme markers")]
    public VB_VisemeMarker[] visemeMarkers;

    [Tooltip("Interruption priority (higher = less interruptible)")]
    [Range(0, 10)]
    public int priority = 5;
}}

/// <summary>
/// Localized VO clip set for a single entry across locales.
/// </summary>
[Serializable]
public class VB_LocalizedVO
{{
    public string entryId;
    public string locale;
    public AudioClip clip;
    public string subtitle;
}}

/// <summary>
/// ScriptableObject VO database holding all voice entries.
/// Create via Assets > Create > VeilBreakers > Audio > VO Database.
/// </summary>
[CreateAssetMenu(fileName = "VODatabase_{safe_name}", menuName = "VeilBreakers/Audio/VO Database")]
public class VeilBreakers_VODatabase : ScriptableObject
{{
    public string databaseName = "{safe_name}";

    [Header("VO Entries")]
    public VB_VOEntry[] entries = new VB_VOEntry[0];

    [Header("Localization")]
    public VB_LocalizedVO[] localizedClips = new VB_LocalizedVO[0];

    // Default entries for this database:
{entries_comment}

    private Dictionary<string, VB_VOEntry> _lookup;
    private Dictionary<string, Dictionary<string, VB_LocalizedVO>> _localeLookup;

    /// <summary>
    /// Initialize lookup dictionaries.
    /// </summary>
    public void Initialize()
    {{
        _lookup = new Dictionary<string, VB_VOEntry>();
        if (entries != null)
        {{
            foreach (var entry in entries)
            {{
                if (!string.IsNullOrEmpty(entry.id))
                    _lookup[entry.id] = entry;
            }}
        }}

        _localeLookup = new Dictionary<string, Dictionary<string, VB_LocalizedVO>>();
        if (localizedClips != null)
        {{
            foreach (var loc in localizedClips)
            {{
                if (!_localeLookup.ContainsKey(loc.entryId))
                    _localeLookup[loc.entryId] = new Dictionary<string, VB_LocalizedVO>();
                _localeLookup[loc.entryId][loc.locale] = loc;
            }}
        }}
    }}

    /// <summary>
    /// Look up a VO entry by ID.
    /// </summary>
    public VB_VOEntry GetEntry(string id)
    {{
        if (_lookup == null) Initialize();
        return _lookup.ContainsKey(id) ? _lookup[id] : null;
    }}

    /// <summary>
    /// Get localized clip for an entry.
    /// </summary>
    public VB_LocalizedVO GetLocalizedEntry(string id, string locale)
    {{
        if (_localeLookup == null) Initialize();
        if (_localeLookup.ContainsKey(id) && _localeLookup[id].ContainsKey(locale))
            return _localeLookup[id][locale];
        return null;
    }}
}}

/// <summary>
/// VO player with subtitle display, lip sync, and queue management.
/// Attach to a character or dialogue manager GameObject.
/// </summary>
public class VeilBreakers_VOPlayer : MonoBehaviour
{{
    [Header("Database")]
    [SerializeField] private VeilBreakers_VODatabase database;

    [Header("Audio")]
    [SerializeField] private AudioSource voiceSource;

    [Header("Localization")]
    [SerializeField] private string currentLocale = "en";

    [Header("Playback Settings")]
    [SerializeField] private float subtitleDisplayBuffer = 0.5f;

    // Events for UI integration
    public event Action<string, float> OnSubtitleStart;   // subtitle text, duration
    public event Action OnSubtitleEnd;
    public event Action<int, float> OnViseme;             // viseme index, weight
    public event Action<VOEmotion> OnEmotionChange;

    private Queue<VB_VOEntry> _playbackQueue = new Queue<VB_VOEntry>();
    private Coroutine _playbackCoroutine;
    private VB_VOEntry _currentEntry;
    private bool _isPlaying;
    private int _currentPriority;

    private void Awake()
    {{
        if (voiceSource == null)
        {{
            voiceSource = GetComponent<AudioSource>();
            if (voiceSource == null)
                voiceSource = gameObject.AddComponent<AudioSource>();
        }}
        voiceSource.playOnAwake = false;
        voiceSource.spatialBlend = 1.0f;
        voiceSource.priority = 0; // Highest priority for dialogue

        if (database != null)
            database.Initialize();
    }}

    /// <summary>
    /// Play a VO line by ID. Respects interruption priority.
    /// </summary>
    public void PlayVO(string entryId)
    {{
        if (database == null) return;

        VB_VOEntry entry = database.GetEntry(entryId);
        if (entry == null)
        {{
            Debug.LogWarning("[VeilBreakers] VO entry not found: " + entryId);
            return;
        }}

        if (_isPlaying && entry.priority <= _currentPriority)
        {{
            // Queue lower/equal priority entries
            _playbackQueue.Enqueue(entry);
            return;
        }}

        // Interrupt current playback for higher priority
        if (_isPlaying)
            StopCurrentVO();

        StartPlayback(entry);
    }}

    /// <summary>
    /// Queue a VO line for sequential playback.
    /// </summary>
    public void QueueVO(string entryId)
    {{
        if (database == null) return;

        VB_VOEntry entry = database.GetEntry(entryId);
        if (entry == null) return;

        if (!_isPlaying)
            StartPlayback(entry);
        else
            _playbackQueue.Enqueue(entry);
    }}

    private void StartPlayback(VB_VOEntry entry)
    {{
        _currentEntry = entry;
        _isPlaying = true;
        _currentPriority = entry.priority;

        // Get localized clip if available
        AudioClip clip = entry.clip;
        string subtitle = entry.subtitle;

        VB_LocalizedVO localized = database.GetLocalizedEntry(
            entry.id, currentLocale);
        if (localized != null)
        {{
            if (localized.clip != null) clip = localized.clip;
            if (!string.IsNullOrEmpty(localized.subtitle))
                subtitle = localized.subtitle;
        }}

        // Play audio
        if (clip != null)
        {{
            voiceSource.clip = clip;
            voiceSource.Play();
        }}

        // Fire events
        float duration = clip != null ? clip.length : entry.duration;
        OnSubtitleStart?.Invoke(subtitle, duration);
        OnEmotionChange?.Invoke(entry.emotion);

        // Start lip sync and completion tracking
        _playbackCoroutine = StartCoroutine(
            PlaybackRoutine(entry, duration));
    }}

    private IEnumerator PlaybackRoutine(VB_VOEntry entry, float duration)
    {{
        float elapsed = 0f;
        int visemeIndex = 0;

        while (elapsed < duration)
        {{
            elapsed += Time.deltaTime;

            // Process viseme markers
            if (entry.visemeMarkers != null)
            {{
                while (visemeIndex < entry.visemeMarkers.Length &&
                       entry.visemeMarkers[visemeIndex].time <= elapsed)
                {{
                    VB_VisemeMarker marker = entry.visemeMarkers[visemeIndex];
                    OnViseme?.Invoke(marker.visemeIndex, marker.weight);
                    visemeIndex++;
                }}
            }}

            yield return null;
        }}

        // Playback complete
        OnSubtitleEnd?.Invoke();
        _isPlaying = false;
        _currentEntry = null;

        // Play next in queue
        if (_playbackQueue.Count > 0)
        {{
            VB_VOEntry next = _playbackQueue.Dequeue();
            StartPlayback(next);
        }}
    }}

    /// <summary>
    /// Stop current VO playback immediately.
    /// </summary>
    public void StopCurrentVO()
    {{
        if (_playbackCoroutine != null)
            StopCoroutine(_playbackCoroutine);

        voiceSource.Stop();
        OnSubtitleEnd?.Invoke();
        _isPlaying = false;
        _currentEntry = null;
    }}

    /// <summary>
    /// Clear the playback queue.
    /// </summary>
    public void ClearQueue()
    {{
        _playbackQueue.Clear();
    }}

    /// <summary>
    /// Set the locale for localized VO playback.
    /// </summary>
    public void SetLocale(string locale)
    {{
        currentLocale = locale;
    }}

    /// <summary>
    /// Check if VO is currently playing.
    /// </summary>
    public bool IsPlaying()
    {{
        return _isPlaying;
    }}

    /// <summary>
    /// Get the current VO entry being played.
    /// </summary>
    public VB_VOEntry GetCurrentEntry()
    {{
        return _currentEntry;
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/Audio/VeilBreakers_VOPipeline.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Create a VO Database: Assets > Create > VeilBreakers > Audio > VO Database",
            "Populate entries with AudioClips, subtitles, and emotion tags",
            "Attach VeilBreakers_VOPlayer to your dialogue manager",
            "Subscribe to OnSubtitleStart/OnSubtitleEnd for UI display",
            "Subscribe to OnViseme for lip sync animation",
            "Add localized clips for multi-language support",
        ],
    }
